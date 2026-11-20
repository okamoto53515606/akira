# main.py — Akira エントリーポイント
#
# 毎朝Fargateタスクとして起動される。
#   python main.py            → 通常の日次運用
#   python main.py --dry-run  → 公開せずに計画だけ出力（ローカル確認用）
#
# フロー:
#   1. シークレット読み込み → 予算ゲート（超過なら日報のみ書いて終了）
#   2. DynamoDBからシステムプロンプト/skills読み込み（自己改善の反映）
#   3. Akira（claude-fable-5-2）がリサーチ・計画・3AIへの作業依頼を実施
#   4. 日報を生成して akira.okamomedia.tokyo へ公開
#   5. 全エージェントのトークン使用量を akira-usage へ記録

import argparse
import logging
import os
import re
import signal
import time
import types
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import budget
import config_store
import page_audit
import report
import settings
import tools as akira_tools
import trace_store
from settings import (
    AKIRA_MODEL_ID,
    AKIRA_USE_DEEPSEEK,
    CLAUDE_MODEL_ID,
    DEBUG_TOOL_LOGGING,
    DEEPSEEK_ANTHROPIC_BASE_URL,
    DEEPSEEK_MAX_TOKENS,
    DEEPSEEK_MODEL_ID,
    DEEPSEEK_READ_TIMEOUT,
    RUN_DEADLINE_SECONDS,
    ENABLE_BIGQUERY_MCP,
    ENABLE_GA4_MCP,
    GEMINI_MODEL_ID,
    GOOGLE_BIGQUERY_PROJECT,
    JST,
    LLM_SITE_URL,
    OPENAI_MODEL_ID,
    REPORTS_SITE_URL,
    WORKSPACE_LOCAL_DIR,
    load_secrets_into_env,
)

logging.basicConfig(format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("akira")
logger.setLevel(logging.INFO)

if DEBUG_TOOL_LOGGING:
    # LLMのツール呼び出し・MCP通信の詳細をCloudWatchへ出力する（異常挙動チェックのため一時的に有効化）
    logging.getLogger("strands").setLevel(logging.DEBUG)
    logging.getLogger("mcp").setLevel(logging.DEBUG)
    logger.info("DEBUG_TOOL_LOGGING=true: strands/mcpの詳細ログを出力します")

_DEBUG_LOG_LIMIT = 6000  # CloudWatch費用抑制のため1エントリあたりの出力上限（文字数）
_STOP_WORK_MSG = (
    "【作業停止】本日の作業上限に達しました。"
    "これ以上の作業依頼はできません。日報を書いて終了してください。"
)

# --- 「空応答」対策（2026-09-15 実発生）--------------------------------------
# DeepSeek(Anthropic互換API)が「HTTP 200だがSSEイベントを1件も返さない」空ストリームを
# 返すことがある。このとき strands は例外を出さず、anthropic SDK の
# `stream.get_final_message()` が AssertionError になって
# "failed to retrieve message snapshot, usage metadata unavailable" を警告し、
# 「内容が空の応答」としてターンを正常終了させる。
# 結果は「ツール呼び出しゼロ・日報も書かれない・usageも取れず0円記録」という静かな失敗で、
# 例外でもデッドラインでもないため既存のフォールバックに入らない（公開日報は
# 「（日報が生成されませんでした）」の1行だけになり、原因がログからも分からない）。
# 空応答は課金も発生しないので、履歴を汚さない範囲で再試行するのが最も安い対策。
_MAX_EMPTY_ATTEMPTS = 3

# --- 委任先の「ツール叩きすぎ」監視（2026-10-17 実発生）----------------------
# 1回の委任でツールを190回叩き（Claudeエンジニア、DeepSeek節約モード）、170円を使ったうえに
# 最終応答が空で返って作業が宙に浮いた。モデル呼び出しのたびに履歴を全量再送するため、
# ツール回数は費用と失敗率にほぼ二次関数的に効く。閾値超えは警告としてログに残す
# （挙動は変えない。抑えるのはプロンプト側の指示＝CLAUDE_ENGINEER_SAVINGS_NOTEの役目）
_DELEGATION_TOOL_WARN = 60

# --- 委任先が「例外で落ちた」ときの1回だけの再依頼（2026-10-17 実発生）--------
# 2026-10-17の2回目ランで、エンジニアの2回目呼び出しが
#   anthropic SDKのストリーム蓄積（accumulate_event → from_json）
#   ValueError: expected value at line 1 column 13
# → strands が EventLoopException に包んでターン途中で死んだ（DeepSeek Anthropic互換の
# tool_use引数JSONが壊れて流れてきた）。これは「ターンが死ぬ」型で、ターンが正常終了して
# いる空応答（_is_empty_response）とは性質が違う:
#   - 空応答: ターンは終わっている＝作業は完了している可能性がある → 再依頼は二重作業の恐れ
#   - 例外  : ターンは途中で死んだ＝作業は未完のまま放置される → 未完分を続けさせる価値がある
# よって例外のときだけ1回再依頼する。二重作業を避けるため再依頼文に「状態確認」と
# 「完了済みはやり直さない」を必ず入れる（_resume_request）。
_MAX_DELEGATION_RETRY = 1
_run_deadline_monotonic: float | None = None


def _resume_request(name: str, exc: Exception, request: str, tool_calls: int) -> str:
    """例外で中断したあとの再依頼文（状態確認と二重作業の禁止を明示する）。"""
    return (
        f"【重要】直前のあなたの作業は例外で中断した"
        f"（{type(exc).__name__}: {str(exc)[:200]}）。\n"
        f"中断までにツールを{tool_calls}回実行している。**やり直す前に必ず現在の状態を確認**すること:\n"
        "  list_local_files / list_site_files / list_workspace_files / get_site_file で\n"
        "  「すでに保存・公開されているもの」を先に確かめ、**完了済みの作業は二度やらない**。\n"
        "  （同じ内容の再公開は無駄。サイトを壊す恐れもある）\n"
        "  未完の項目だけを実行し、最後に必ず要約を本文で返すこと（本文を空にしない）。\n"
        "--- 依頼（内容は変わらない） ---\n" + request
    )


def _start_run_deadline() -> None:
    """日次タスクの壁時計上限をセットする（RUN_DEADLINE_SECONDS、既定60分）。"""
    global _run_deadline_monotonic
    _run_deadline_monotonic = time.monotonic() + RUN_DEADLINE_SECONDS


def _deadline_remaining_seconds() -> float:
    if _run_deadline_monotonic is None:
        return float(RUN_DEADLINE_SECONDS)
    return max(0.0, _run_deadline_monotonic - time.monotonic())


def _deadline_exceeded() -> bool:
    return _deadline_remaining_seconds() <= 0


class _RunDeadlineExceeded(Exception):
    """壁時計上限に達した。"""


def _alarm_handler(signum, frame) -> None:
    raise _RunDeadlineExceeded("RUN_DEADLINE_SECONDS exceeded")


def is_savings_mode() -> bool:
    """DEEPSEEK_API_KEY と DEEPSEEK_MODEL_ID が両方設定されていれば節約モード。"""
    key = os.getenv("DEEPSEEK_API_KEY")
    model = os.getenv("DEEPSEEK_MODEL_ID")
    return bool(key and model)


def _create_deepseek_model():
    """DeepSeek（Anthropic互換API）。節約モードのエンジニア役 / Akira本体で使用。

    LiteLLM+Chat Completions は reasoning_content がマルチターンで欠落するため使わない。
    max_tokens は DEEPSEEK_MAX_TOKENS（既定128000）。APIは messages+max_tokens を
    コンテキスト1Mに対して予約する。384Kだと履歴66.5万の時点で
    665132+384000=1049132 > 1048576 となり400（2026-09-09）。128Kなら79.3万に収まり、
    16Kで起きた MaxTokensReached（2026-08-27）の再発も防ぐ（3e0d7efと同じ値）。
    readタイムアウトは DEEPSEEK_READ_TIMEOUT（既定3600s。SDK既定600sは
    thinking付きの長め生成で切断されうるため拡張）。
    """
    import httpx
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args={
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "base_url": DEEPSEEK_ANTHROPIC_BASE_URL,
            # floatを渡すとconnect含む全フェーズに適用されるため、read/write/poolのみ
            # 上限に伸ばし connect は短く保つ（接続先ダウンを素早く検知する）
            "timeout": httpx.Timeout(DEEPSEEK_READ_TIMEOUT, connect=10.0),
        },
        model_id=DEEPSEEK_MODEL_ID,
        max_tokens=DEEPSEEK_MAX_TOKENS,
    )


def _debug_log_io(direction: str, agent_name: str, text: str) -> None:
    """DEBUG_TOOL_LOGGING有効時、LLMへの指示/応答をCloudWatchへ出力する。

    2026-11-21 修正:
        ここは `logger.debug` で書いていたが、この logger は INFO に設定されて
        いるため **1件も記録されていなかった**（当日のログで `Akira本体] 指示`
        が0件だった）。原因分析が「たぶんこうだ」になる元凶なので INFO に上げる。
        本文は 6000字で切り詰めるが、全文は trace_store が S3 に残す。
    """
    if not DEBUG_TOOL_LOGGING:
        return
    truncated = text if len(text) <= _DEBUG_LOG_LIMIT else text[:_DEBUG_LOG_LIMIT] + f"...(以下省略, 全{len(text)}文字)"
    logger.info("[IO] %s %s:\n%s", agent_name, direction, truncated)


def _is_empty_response(result) -> bool:
    """モデルから実質何も届かなかった（本文もツール呼び出しも無い）かを判定する。

    正常な応答なら必ず text か toolUse のブロックが入る。ブロックが0件、または
    中身が空のときだけ True を返す（reasoningContentのみ、も「何もしていない」扱い）。
    """
    message = getattr(result, "message", None)
    if not isinstance(message, dict):
        return True
    blocks = message.get("content") or []
    if not blocks:
        return True
    for block in blocks:
        if not isinstance(block, dict):
            return False
        if "toolUse" in block:
            return False
        if str(block.get("text") or "").strip():
            return False
    return True


def _tool_call_count(agent) -> int:
    """エージェントが実行したツール呼び出しの累計回数。

    呼び出し前後で差分を取り「この呼び出しで実際に作業したか」を判定する
    （strands の event_loop_metrics はエージェント生涯累計のため差分で見る）。
    """
    metrics = getattr(agent, "event_loop_metrics", None)
    tool_metrics = getattr(metrics, "tool_metrics", None) or {}
    try:
        return sum(int(getattr(m, "call_count", 0) or 0) for m in tool_metrics.values())
    except Exception:  # メトリクス構造が変わっても判定を止めない
        return 0

# =====================================================================
# 依頼の「作業票」と受領書（2026-11-21）
#
# なぜ:
#   11-21 のランで、Akira が「1. china-ai / 2. /mai/」の2項目を1回の依頼で出し、
#   エンジニアは 1番だけやって 2番を**報告からも消した**。原因は
#     (a) 依頼が「番号付きの願い」で、項目ごとの合格条件が無い
#     (b) エンジニアが「残り呼び出し数」で自分でスコープを切る（実測: 依頼1で83回、
#         依頼2で82回。2回目は「最小スコープ」のはずが同じだけ回っている）
#     (c) 報告がエンジニアの文章なので、書かなければ存在しなかったことになる
#   対策はプロンプトではなく**コード**で入れる:
#     1. 1回の依頼に項目を1つだけ許す（複数なら機械が拒否して分割を促す）
#     2. 各項目に item_id と accept（機械が読める合格条件）を必須にする
#     3. 応答に `DONE: <item_id>` が無ければ**ハーネスが未達として記録**し、
#        日報に機械が表を追記する（LLMの申告に依存しない）
# =====================================================================
_ITEM_LEDGER: list[dict] = []

# 「1. 」「2) 」「①②」で始まる行が2つ以上あれば複数項目とみなす（保守的）
_NUMBERED_LINE = re.compile(r"^\s*(?:[0-9]{1,2}[.)．、]|[①②③④⑤⑥⑦⑧⑨⑩])\s*\S", re.M)


def count_request_items(request: str) -> int:
    """依頼文に含まれる「番号付き項目」の数を数える（コードで分割を強制するため）。"""
    return len(_NUMBERED_LINE.findall(request or ""))


def record_item(item_id: str, request: str, accept: str, status: str = "requested",
                reason: str = "", evidence: str = "") -> dict:
    """作業票を1件記録する（run 内の台帳＋trace）。"""
    row = {"item_id": item_id or "-", "request": (request or "")[:400],
           "accept": (accept or "")[:400], "status": status,
           "reason": reason[:300], "evidence": evidence[:300]}
    _ITEM_LEDGER.append(row)
    trace = trace_store.current()
    if trace:
        trace.event("item.status", item_id=row["item_id"], status=status,
                    reason=row["reason"], accept=row["accept"])
    return row


def item_receipt(item_id: str, accept: str, response: str) -> tuple[bool, str]:
    """応答から `DONE: <id>` / `NOT_DONE: <id>` を読み、無ければ未達にする。

    戻り値: (達成したか, 受領書の1行)
    """
    body = response or ""
    if not item_id:
        return False, "未確認（item_id が無い）"
    done = bool(re.search(r"(?im)^\s*DONE\s*[:：]\s*%s\b" % re.escape(item_id), body))
    not_done = bool(re.search(r"(?im)^\s*NOT[_ ]?DONE\s*[:：]\s*%s\b" % re.escape(item_id), body))
    if done and not not_done:
        return True, "達成（応答に DONE: %s）" % item_id
    if not_done:
        return False, "未達（応答に NOT_DONE: %s）" % item_id
    return False, "未確認（応答に DONE/NOT_DONE の記載が無い。accept も未確認）"


def ledger_markdown() -> str:
    """日報の末尾に機械が追記する「依頼項目の受領書」。"""
    if not _ITEM_LEDGER:
        return ""
    rows = ["", "---", "", "### 今日の依頼項目（機械の受領書。ここは消せない）", "",
            "| item | 判定 | 合格条件 | 根拠 |", "|---|---|---|---|"]
    mark = {"done": "達成", "not_done": "**未達**", "requested": "未確認"}
    for r in _ITEM_LEDGER:
        rows.append("| %s | %s | %s | %s |" % (
            r["item_id"], mark.get(r["status"], r["status"]),
            (r["accept"] or "-").replace("|", "\\|")[:120],
            (r["evidence"] or r["reason"] or "-").replace("|", "\\|")[:160]))
    rows.append("")
    rows.append("※「未確認」は応答に `DONE: <item>` が無かったもの。"
                "**やったかどうかを文章で判断しない**（2026-11-21 に2番が報告から消えた）。")
    return "\n".join(rows)


def _record_delegation_usage(agent, model_id: str, name: str, result=None) -> float:
    """委任1回分のトークン使用量を記録する（失敗した試行も漏らさず記録する）。

    strands は agent 呼び出しごとに usage をリセットするので、agent 側の
    `event_loop_metrics.accumulated_usage` がその呼び出しの消費量になる。
    例外で落ちた場合は AgentResult が無いので、その時点までの消費をここから拾って
    記録する（失敗した試行が無料だったことは無い＝予算の実費と乖離させない）。
    """
    if result is None:
        usage = getattr(getattr(agent, "event_loop_metrics", None), "accumulated_usage", None)
        if not usage:
            return 0.0
        result = types.SimpleNamespace(metrics=types.SimpleNamespace(accumulated_usage=usage))
    return budget.collect_agent_usage(result, model_id, purpose=f"delegate:{name}", agent=agent)


# =====================================================================
# モデル / エージェント生成
# =====================================================================
def _create_models():
    from strands.models.anthropic import AnthropicModel
    from strands.models.gemini import GeminiModel
    from strands.models.openai_responses import OpenAIResponsesModel

    if AKIRA_USE_DEEPSEEK:
        # Akira本体を DeepSeek V4.1 Flash（model_id: deepseek-flash / Anthropic互換API）に切替。
        # 旧名 deepseek-v4-pro は 2026-09-14 以降 V4.1 Flash へ自動ルーティングされる（公式）。
        logger.info("💰 Akira本体 → DeepSeek V4.1 Flash (deepseek-flash / Anthropic互換API) に切替")
        akira_model = _create_deepseek_model()
    else:
        akira_model = AnthropicModel(
            client_args={"api_key": os.getenv("CLAUDE_API_KEY")},
            model_id=AKIRA_MODEL_ID,
            max_tokens=16384,
        )

    return {
        "akira": akira_model,
        "claude": AnthropicModel(
            client_args={"api_key": os.getenv("CLAUDE_API_KEY")},
            model_id=CLAUDE_MODEL_ID,
            max_tokens=16384,
        ),
        # GPT税理士は factチェックが主。reasoning を低く、出力も短く抑える。
        # effort=low だけでは TPM 50万超えは解消しないが、出力予約の無駄は減る。
        "gpt": OpenAIResponsesModel(
            client_args={"api_key": os.getenv("OPENAI_API_KEY")},
            model_id=OPENAI_MODEL_ID,
            params={
                "max_output_tokens": 8192,
                "reasoning": {"effort": "low"},
            },
        ),
        "gemini": GeminiModel(
            client_args={"api_key": os.getenv("GEMINI_API_KEY")},
            model_id=GEMINI_MODEL_ID,
        ),
    }


def _create_brave_mcp():
    from mcp import StdioServerParameters, stdio_client
    from strands.tools.mcp import MCPClient

    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="npx",
                args=["-y", "@brave/brave-search-mcp-server"],
                env={"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY", "")},
            )
        )
    )


def _create_firecrawl_mcp():
    """Firecrawl MCP — Webページのスクレイピング・検索（無料枠あり。エラー時はクォータ超過の可能性）。

    JSレンダリングが必要なSPAページ（OpenAI料金ページ等）の本文取得に特に有用。
    Brave Searchでは取得できないページ内容の詳細抽出に使う。
    """
    from mcp import StdioServerParameters, stdio_client
    from strands.tools.mcp import MCPClient

    key = os.getenv("FIRECRAWL_API_KEY", "")
    if not key:
        logger.warning("FIRECRAWL_API_KEY が未設定のため Firecrawl MCP はスキップされます")
        return None
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="npx",
                args=["-y", "firecrawl-mcp"],
                env={"FIRECRAWL_API_KEY": key},
            )
        )
    )


def _create_github_mcp():
    """GitHub MCP（Streamable HTTP）— 公開リポジトリの読み取り専用アクセス。

    GITHUB_PAT_READ_ONLY_PUBLIC は Secrets Manager から load_secrets_into_env() で
    環境変数に展開される前提。
    """
    from strands.tools.mcp import MCPClient
    from mcp.client.streamable_http import streamablehttp_client

    pat = os.getenv("GITHUB_PAT_READ_ONLY_PUBLIC", "")
    if not pat:
        logger.warning("GITHUB_PAT_READ_ONLY_PUBLIC が未設定のため GitHub MCP はスキップされます")
        return None
    return MCPClient(
        lambda: streamablehttp_client(
            url="https://api.githubcopilot.com/mcp/",
            headers={"Authorization": f"Bearer {pat}"},
        )
    )


def _wi_env() -> dict:
    """Workload Identity用の環境変数セットを作る（MCPサブプロセス渡し専用。本体プロセスの
    os.environは一切変更しない）。

    【2026-07-09 検証済み】ECS FargateはEC2版IMDS(169.254.169.254)に到達できないため、
    google-authのcredential_source経由の自動取得は使えない（実機テストで確認済み）。
    boto3の凍結クレデンシャルを明示的にAWS_ACCESS_KEY_ID等としてMCPサブプロセスへ
    渡す必要がある。

    本体プロセスのos.environを書き換えると、同じプロセス内の他のboto3呼び出し
    （S3公開・DynamoDB記録・CloudFront invalidation等）が自動更新されない凍結
    クレデンシャルを誤って使ってしまうため、環境変数を変更しない
    tools._write_gcp_wi_config_file() を使う。
    """
    import boto3

    config_file = akira_tools._write_gcp_wi_config_file()
    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()
    env = {
        "GOOGLE_APPLICATION_CREDENTIALS": config_file,
        "AWS_ACCESS_KEY_ID": creds.access_key,
        "AWS_SECRET_ACCESS_KEY": creds.secret_key,
        "AWS_REGION": session.region_name or "us-east-1",
    }
    if creds.token:
        env["AWS_SESSION_TOKEN"] = creds.token
    return env


def _create_ga4_mcp():
    """GA4 MCP（Workload Identityキーレス）。"""
    from mcp import StdioServerParameters, stdio_client
    from strands.tools.mcp import MCPClient

    env = _wi_env()
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(command="uvx", args=["analytics-mcp"], env=env)
        )
    )


def _create_bigquery_mcp():
    """BigQuery MCP（Search Consoleエクスポートデータ用、WIキーレス）。"""
    from mcp import StdioServerParameters, stdio_client
    from strands.tools.mcp import MCPClient

    env = {**_wi_env(), "BIGQUERY_PROJECT": GOOGLE_BIGQUERY_PROJECT}
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="toolbox", args=["--prebuilt", "bigquery", "--stdio"], env=env
            )
        )
    )


def _evidence_block(max_files: int = 6, max_chars: int = 6000) -> str:
    """レビュー担当に渡す「本日取得した一次情報」だけの前置き（2026-11-14 追加）。

    11-14 の GPT税理士は「提示された当日取得のGoogle一次情報によれば」と書いて
    Carbon を GA ではないと断定し、正しい記述を削らせた。実際には何も提示されておらず、
    GPTは `/workspace/cache/gemini-4-carbon-2026-11-03.md`（11日前）の判定文を
    そのまま再生していた。`cache/` の最新は 11-05 で、11-10 以降の事実は1件も無い。

    対策は「古い証拠を読ませない」こと。当日の cache（本文冒頭の『取得日時:』が今日）
    だけを文字列にして前置きする。mtime は restore/save で毎日当日になるので使わない。
    """
    cache_dir = os.path.join(WORKSPACE_LOCAL_DIR, "cache")
    today = datetime.now(JST).date().isoformat()
    chunks: list[str] = []
    try:
        if os.path.isdir(cache_dir):
            for name in sorted(os.listdir(cache_dir)):
                if not name.endswith(".md"):
                    continue
                path = os.path.join(cache_dir, name)
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        if ("取得日時: %s" % today) not in fh.read(300):
                            continue
                        fh.seek(0)
                        chunks.append("### %s\n%s" % (name, fh.read(max_chars)))
                except OSError:
                    continue
                if len(chunks) >= max_files:
                    break
    except OSError:
        chunks = []
    if not chunks:
        return (
            "【本日取得した一次情報: なし】\n"
            "今日はまだ一次情報を取得していない。**事実の断定をしないこと**。\n"
            "古い記憶や古いキャッシュを根拠に『クリティカル』と判定してはいけない。\n"
            "確認したい点だけを挙げ、事実は『未確認』と書く。\n\n"
        )
    body = "\n\n".join(chunks)[:max_chars]
    return (
        "【本日(%s)取得した一次情報。事実の根拠はこの中だけ】\n%s\n\n"
        "※ここに無い事実を根拠にクリティカルと判定しないこと。必要なら『未確認』と書く。\n"
        "※クリティカルには『この中のURL＋逐語引用』を必ず併記する。併記できないものは軽微。\n\n"
        % (today, body)
    )


_URL_RE = re.compile(r"https?://\S+")


_CRIT_COUNT_RE = re.compile(r"クリティカル\s*[:：]?\s*\**\s*(\d+)\s*件")
_CRIT_HEAD_RE = re.compile(r"^#{1,6}\s*(?:\*\*)?\s*クリティカル")
_ITEM_RE = re.compile(r"^\s*(?:[-*・]|\d+[.．)])")


def _sanitize_review(text: str) -> str:
    """引用URLの無い『クリティカル』を軽微扱いに落とす（2026-11-14 追加 / 11-15 v3）。

    レビューの格上げ条件（公式URL＋逐語引用がある場合のみクリティカル）を、文章の
    お願いではなく機械で担保する。

    変遷:
        v1 行単位 → 主張と引用が別の行だと誤爆した（11-14）。
        v2 節単位 → 本文中に「クリティカル」という単語が出ただけでも節と誤認した
                    （11-15: 「クリティカルな誤情報は確認できませんでした」を拾い、
                    実際は critical 0件なのに降格した）。
        v3 **見出しか件数で判定**する。判定の優先順位は次のとおり:
           1. 「クリティカル: 0件」と明言があれば、何もしない
           2. 見出し（`### クリティカル`）があれば、そこから節を取る
           3. 「クリティカル: N件」(N>0) の行があり、箇条書きが続く場合だけ節を取る
           4. どれにも当たらなければ、単語が出ただけとみなして何もしない
    """
    if not text or "クリティカル" not in text:
        return text

    counts = [int(m.group(1)) for m in _CRIT_COUNT_RE.finditer(text)]
    if counts and max(counts) == 0:
        return text  # 明示的に0件。降格する対象が無い

    lines = text.split("\n")
    start, explicit = None, False
    for i, ln in enumerate(lines):
        if _CRIT_HEAD_RE.match(ln.strip()):
            start, explicit = i, True
            break
    if start is None:
        for i, ln in enumerate(lines):
            m = _CRIT_COUNT_RE.search(ln)
            if m and int(m.group(1)) > 0:
                start = i
                break
    if start is None:
        return text  # 見出しも件数も無い＝本文中の言及。触らない

    end = len(lines)
    for j in range(start + 1, len(lines)):
        st = lines[j].strip()
        if re.match(r"^(#+\s|【|>?\s*(?:\*\*)?(軽微|改善|提案|その他|まとめ|結論))", st):
            end = j
            break
    section = lines[start:end]
    if _URL_RE.search("\n".join(section)):
        return text  # 節のどこかに引用URLがある

    body = section[1:]
    # 件数で拾った場合は、箇条書きが無ければ「単語が出ただけ」とみなす
    if not explicit and not any(_ITEM_RE.match(l) for l in body):
        return text

    note = "[軽微として扱う: 引用URLなし] "
    for k, ln in enumerate(body):
        if ln.strip():
            body[k] = note + ln
            break
    logger.warning("レビュー: 引用URLの無いクリティカル節を軽微扱いにしました")
    return ("\n".join(lines[:start] + [section[0]] + body + lines[end:])
            + "\n\n[ゲート] クリティカルの節に公式URLの引用が無いため軽微として扱う。"
              "事実の断定は当日取得の一次情報で確認すること（恒久ルール2）。")


# MCPクライアントを「Agentの寿命」から切り離すための常駐consumer id。
# strands の MCPClient は consumer が0になると stop() する。委任先のAgentは
# 毎回作り直す設計なので、そのままだと1回の依頼が終わるたびに MCP サーバーを
# 落として次の依頼で起動し直す（その窓で回線が死んだままになる事故がある）。
_MCP_KEEPALIVE = "akira-harness-keepalive"


def _iter_mcp_clients(tools):
    """ツール一覧から MCPClient（= ToolProvider）だけを取り出す。"""
    try:
        from strands.tools.mcp import MCPClient
    except Exception:  # noqa: BLE001
        return
    for t in tools or []:
        if isinstance(t, MCPClient):
            yield t


def _revive_dead_mcp(tools, where: str) -> int:
    """死んだMCP接続を「次にload_toolsで起動し直される」状態に戻す（2026-11-17）。

    なぜ:
        strands の MCPClient は「started=True のまま回線だけ閉じる」ことがある。
        その状態で Agent を作ると load_tools() が start() をスキップし、
        `RuntimeError: Connection to the MCP server was closed` で**Agentの生成
        そのものが落ちる**。2026-11-17 05:34 の2回目の依頼がこれで全滅した
        （エンジニアのAgent生成時 / 3つのMCPを共有していた）。
    何をするか:
        started なのに session が生きていないクライアントを stop() で初期化し、
        次の load_tools() で start() させる。戻り値は復旧した数。
    """
    revived = 0
    for c in _iter_mcp_clients(tools):
        try:
            if not getattr(c, "_tool_provider_started", False):
                continue
            active = bool(c._is_session_active())
        except Exception:  # noqa: BLE001
            active = False
        if active:
            continue
        logger.warning("MCP接続が切れたままだったので作り直します（%s）", where)
        try:
            c.stop(None, None, None)
        except Exception:  # noqa: BLE001
            logger.exception("MCPクライアントの停止に失敗（%s）", where)
        try:
            c._tool_provider_started = False
            c._loaded_tools = None
            c.add_consumer(_MCP_KEEPALIVE)
        except Exception:  # noqa: BLE001
            pass
        revived += 1
    return revived


def create_delegation_tools(models, run_budget_jpy: float, block_publish: bool = False):
    """3AIを「ツール」としてAkiraに渡す（agent-as-toolパターン）。

    各呼び出しのトークン使用量は個別モデルIDで akira-usage に記録する。
    MCPクライアントはセッション競合を避けるためエージェントごとに個別生成する。
    run_budget_jpy: 今回実行で使える上限（＝月次予算の残額。ハードリミット）。
    """
    from strands import Agent, tool
    from strands.agent.conversation_manager import SlidingWindowConversationManager

    import prompts

    def _run(make_agent, model_id: str, name: str, request: str,
             item_id: str = "", accept: str = "") -> str:
        """委任先を呼ぶ。例外で落ちたときだけ、状態確認つきで1回だけ再依頼する。

        - 空応答（ターンは正常終了）は今までどおり再依頼しない（二重作業を避ける）
        - 例外（ターンが途中で死ぬ）は未完の作業が放置される型なので1回だけ続きを頼む
        エージェントは毎回 make_agent() で作り直す（例外で壊れた履歴を引きずらない・
        前回呼び出しの履歴を持ち越さない）。
        """
        request_to_send = request
        for attempt in range(_MAX_DELEGATION_RETRY + 1):
            if _deadline_exceeded():
                return _STOP_WORK_MSG
            spent = budget.get_run_spent_jpy()
            if spent >= run_budget_jpy:
                logger.warning("予算ガード発動: spent=%.1f remaining_limit=%.1f", spent, run_budget_jpy)
                return _STOP_WORK_MSG
            # MCPが死んだままだと Agent の生成そのものが落ちる（2026-11-17）。
            # 毎回ここで健康確認してから作る。
            _revive_dead_mcp(_shared_mcp, name)
            try:
                agent = make_agent()
            except Exception as e:  # noqa: BLE001
                logger.warning("%s のAgent生成に失敗（%s: %s）。MCPを作り直して1回だけ再試行します",
                               name, type(e).__name__, str(e)[:160])
                _revive_dead_mcp(_shared_mcp, name + "/再試行")
                try:
                    agent = make_agent()
                except Exception as e2:  # noqa: BLE001
                    logger.error("%s のAgent生成に再試行しても失敗（%s: %s）",
                                 name, type(e2).__name__, str(e2)[:160])
                    return (
                        f"【{name}: 起動できず】{type(e2).__name__}: {str(e2)[:200]}\n"
                        f"MCPクライアントの再接続に失敗した。作業は何も実行していない。"
                        f"同じ依頼をこのランで送り直さず、日報に「{name}が起動できなかった」"
                        f"と書いて終了せよ。"
                    )
            tools_before = _tool_call_count(agent)
            _debug_log_io("指示", name, request_to_send)
            _trace = trace_store.current()
            if _trace:
                _trace.prompt(name, getattr(agent, "system_prompt", "") or "")
                _trace.event("delegate.request", agent=name, item_id=item_id,
                             attempt=attempt + 1, chars=len(request_to_send),
                             body=_trace.blob("delegate.request", request_to_send),
                             accept=accept)
            try:
                result = agent(request_to_send)
            except _RunDeadlineExceeded:
                raise  # 壁時計の打ち切りは run_daily のハンドリングへ（再依頼しない）
            except Exception as e:  # noqa: BLE001
                tool_calls = max(0, _tool_call_count(agent) - tools_before)
                cost = _record_delegation_usage(agent, model_id, name)
                logger.error(
                    "%s の呼び出しが例外で中断しました（%s: %s / ツール実行%d回 / 約%.1f円）",
                    name, type(e).__name__, str(e)[:200], tool_calls, cost)
                if attempt < _MAX_DELEGATION_RETRY:
                    logger.warning("%s を状態確認つきで1回だけ再依頼します", name)
                    request_to_send = _resume_request(name, e, request, tool_calls)
                    continue
                return (
                    f"【{name}: 呼び出しが例外で中断】{type(e).__name__}: {str(e)[:200]}\n"
                    f"ツール実行が{tool_calls}回あった後に落ちた。再依頼も同じ例外で落ちたため"
                    f"これ以上呼び直さないこと。list_local_files / list_site_files / "
                    f"list_workspace_files で作業の到達点を確認し、未完の項目は site_plan に"
                    f"記録して日報で報告せよ。"
                )
            _debug_log_io("応答", name, str(result))
            cost = _record_delegation_usage(agent, model_id, name, result)
            tool_calls = max(0, _tool_call_count(agent) - tools_before)
            logger.info("%s 完了 (約%.1f円 / 本日累計約%.1f円) ツール実行%d回",
                        name, cost, budget.get_run_spent_jpy(), tool_calls)
            if _trace:
                try:
                    hist = _trace.tools_histogram(agent)
                except Exception:  # noqa: BLE001
                    hist = []
                _trace.event("delegate.result", agent=name, item_id=item_id,
                             tool_calls=tool_calls, cost_jpy=round(cost, 1),
                             tools=hist,
                             body=_trace.blob("delegate.result", str(result)))
            if tool_calls >= _DELEGATION_TOOL_WARN:
                logger.warning(
                    "%s のツール実行が%d回に達しました（履歴肥大の兆候。1回の依頼を分割するか、"
                    "編集を1本のスクリプトにまとめさせること）", name, tool_calls)
            if _is_empty_response(result):
                # 空応答（2026-09-15にAkira本体で発生したのと同症状。2026-10-17は委任先で、
                # ツール実行11回の後に発生）。ここで空文字を素直に返すと
                # Akira本体が「作業完了」と誤認するため、空振りだったことを明示して返す。
                logger.error("%s の応答が空でした（この呼び出しでのツール実行 %d回）", name, tool_calls)
                if tool_calls == 0:
                    return (
                        f"【{name}: 応答が空】モデルは本文もツール呼び出しも返さず終了した。"
                        f"この呼び出しでは何も実行されていない。同じ依頼を1回だけ送り直してよい。"
                        f"2回目も空なら、その旨を日報に書いて終了せよ。"
                    )
                return (
                    f"【{name}: 応答が空】ツール実行が{tool_calls}回あった後に応答が空になった。"
                    f"作業が途中まで進んでいる可能性があるので、再依頼の前に"
                    f"list_local_files / list_site_files で状態を確認すること。"
                )
            text = str(result)
            if item_id:
                ok, receipt = item_receipt(item_id, accept, text)
                record_item(item_id, request, accept,
                            status="done" if ok else "not_done", evidence=receipt)
                text += ("\n\n【受領書（機械が付けた。消すな）】\n"
                         "item_id: %s\n判定: %s\n合格条件: %s\n"
                         "※未達なら、そのまま日報に書け。別の依頼で包むな。"
                         % (item_id, receipt, accept or "(未指定)"))
            return text

    # --- 共通WEBツール（全員に配布）---
    firecrawl = _create_firecrawl_mcp()
    brave = _create_brave_mcp()
    # MCPクライアントは委任先のAgentをまたいで共有する。共有する以上、
    # 「Agentが消えたら接続も閉じる」という strands の既定動作は邪魔になる（下の注記）。
    _shared_mcp = [c for c in (brave, firecrawl) if c is not None]
    for _c in _shared_mcp:
        try:
            _c.add_consumer(_MCP_KEEPALIVE)
        except Exception:  # noqa: BLE001
            pass
    screenshot_tool = akira_tools.take_screenshot
    fetch_image = akira_tools.fetch_image_from_url
    from strands_tools import file_read, image_reader

    # Firecrawl/Braveの無料枠注意文（ツール説明に含める）
    _web_tool_note = (
        "※無料枠で運用中。APIクォータ超過エラーが出た場合は別のツール（Brave/Firecrawl相互）で補完すること。"
    )

    # GPT税理士には Firecrawl を渡さない。
    # 2026-09-09: 同一 gpt_agent が巨大ページを scrape して会話履歴に残し、
    # 2回目以降の TPM が 518052 / 519208 と上限50万を超過した。
    #
    # 2026-11-14: `list_workspace_files` を外した。レビュー担当に /workspace を
    # 探索させると、古い cache（11-03 の Carbon 判定）を「当日の一次情報」として読み、
    # 正しい記述を削る事故が起きた（stale cache の再生）。証拠は当日取得分だけを
    # _evidence_block() で前置きして渡す。探索させなければ古い結論は出てこない。
    gpt_tools = [akira_tools.get_site_file, akira_tools.list_site_files,
                 akira_tools.list_local_files, file_read,
                 brave, screenshot_tool, fetch_image, image_reader]

    def _new_gpt_agent() -> "Agent":
        """呼び出しごとに新規 Agent。会話履歴（scrape残骸）を持ち越さない。

        collect_agent_usage は id(agent) で差分を取るため、毎回新規でも重複計上しない。
        """
        return Agent(
            name="gpt_tax_advisor",
            model=models["gpt"],
            system_prompt=prompts.GPT_TAX_ADVISOR_PROMPT,
            tools=gpt_tools,
        )
    gemini_tools = [
        akira_tools.generate_and_publish_image,
        akira_tools.get_site_file,
        akira_tools.list_site_files,
        akira_tools.list_local_files,
        akira_tools.list_workspace_files,
        file_read,
        brave,
        screenshot_tool,
        fetch_image,
        image_reader,
    ]
    if firecrawl:
        gemini_tools.append(firecrawl)

    def _new_gemini_agent() -> "Agent":
        """呼び出しごとに新規 Agent（会話履歴を持ち越さない）。

        以前は1個の gemini_agent を使い回していたが、履歴が積み上がることで
          ①何らかの理由で functionCall と functionResponse の対応が崩れると、
            以降の呼び出しが400（function call turn ordering）で全減する
            （2026-09-15: ask_gemini_mother が3連続で失敗）
          ②マルチターンのたびに全履歴を再送するため入力トークンが膨らむ
            （2026-09-05: UXレビュー1回で約1,245円）
        という害があった。GPT税理士と同じ「毎回新規」方式に統一する。
        collect_agent_usage は id(agent) で差分を取るため、毎回新規でも重複計上しない。
        """
        return Agent(
            name="gemini_mother",
            model=models["gemini"],
            system_prompt=prompts.GEMINI_MOTHER_PROMPT,
            tools=gemini_tools,
        )

    @tool
    def ask_gpt_tax_advisor(request: str) -> str:
        """GPT税理士にレビューを依頼する（ビジネス価値・PV貢献の観点とfactチェック。門番ではなくアドバイザー）。

        当日取得した一次情報（エビデンスパック）が自動で前置きされる。
        **クリティカルと判定するには、その中のURLと逐語引用を必ず併記すること。
        併記できないものは軽微として扱う**（11-14 に引用なしのクリティカルが正しい記述を削った）。

        Args:
            request: レビュー対象（サイト内パスや本文）と確認してほしい観点
        """
        result = _run(_new_gpt_agent, OPENAI_MODEL_ID, "GPT税理士",
                      _evidence_block() + request)
        return _sanitize_review(result)

    @tool
    def ask_gemini_mother(request: str) -> str:
        """Gemini子育てママに依頼する（画像生成・初心者目線のわかりやすさチェック）。

        Args:
            request: 依頼内容。画像なら目的と公開先パス、チェックなら対象ページ。
                     画像の視認や大規模なUXチェックは1回の依頼につき2ページ/2枚までに絞ること
                     （並列の大量file_readや複数画像は入力トークンが爆発する。
                     2026-09-05実績: 1回のUXレビューで約1,245円消費）
        """
        return _run(_new_gemini_agent, GEMINI_MODEL_ID, "Gemini子育てママ", request)

    # Claudeエンジニアの追加ツール（オプショナル）
    # 2026-11-14: ドライランは「Akiraへの一文」だけで、エンジニアは普通に公開できた。
    # テストランのために `--dry-run` は**物理的に公開できない**ようにする
    # （サイトを触らずに仕組みの挙動だけ測るための安全弁）。
    if block_publish:
        @tool
        def publish_file_to_site(*args, **kwargs) -> dict:
            """【ドライラン】公開は行わない。"""
            return {"status": "dry_run", "note": "本日はドライランのため公開していません"}

        @tool
        def site_upload(*args, **kwargs) -> dict:
            """【ドライラン】公開は行わない。"""
            return {"status": "dry_run", "note": "本日はドライランのため公開していません"}

        _publish, _upload = publish_file_to_site, site_upload
    else:
        _publish, _upload = akira_tools.publish_file_to_site, akira_tools.site_upload

    claude_tools = [
        _publish,
        akira_tools.get_site_file,
        akira_tools.list_site_files,
        akira_tools.list_local_files,
        akira_tools.list_workspace_files,
        akira_tools.site_download,
        _upload,
        # 描画→ゲート→公開→invalidation→実URL照合を1呼び出しに畳む（2026-11-21）。
        # 83回の儀式を減らし、「残り呼び出し数」で依頼項目を削る理由を無くす。
        akira_tools.publish_and_verify,
        # 画像生成はエージェント経由ではなく直接叩けるようにする。
        # 2026-09-15: ask_gemini_mother（エージェント）が400で不通になり画像が作れなかった。
        # 画像生成自体は APIキー1コールの決定論的な処理なので、依頼先のLLMが落ちても
        # 使えるべき。Gemini子育てママの役割は「生成」より「視認チェック」に寄せる。
        akira_tools.generate_and_publish_image,
        akira_tools.update_akira_config,
        akira_tools.get_site_plan,
        # 健全性チェックと決定論的修復（エンジニアも公開前後に使う）
        akira_tools.verify_published_contracts,
        akira_tools.restore_published_data_file,
        # ページ監査（古い情報・追記の混在・キービジュアルの取り残し）
        page_audit.audit_pages,
        page_audit.set_page_priority,
        brave,
        screenshot_tool,
        fetch_image,
        image_reader,
        ask_gpt_tax_advisor,
        ask_gemini_mother,
    ]
    if firecrawl:
        claude_tools.append(firecrawl)
    # GitHub MCP（公開リポジトリ読み取り専用）
    github = _create_github_mcp()
    if github:
        claude_tools.append(github)
        _shared_mcp.append(github)
        try:
            github.add_consumer(_MCP_KEEPALIVE)
        except Exception:  # noqa: BLE001
            pass

    # shell / editor / file_read / file_write（Claudeエンジニアのみ。BYPASS_TOOL_CONSENT=true 要）
    try:
        from strands_tools import shell, editor, file_read, file_write
        claude_tools.extend([shell, editor, file_read, file_write])
        logger.info("Claudeエンジニアに shell/editor/file_* ツールを追加しました")
    except ImportError:
        logger.warning("strands_tools が利用できないため shell/editor/file_* は追加しません")

    # --- 永続ワークスペースの自作ツール（/workspace/tools/*.py の TOOL 変数を自動登録） ---
    # エンジニアが前日までに作ったツールが翌朝から使える＝自己拡張ループ。
    # 1個の壊れたファイルで実行が止まらないよう、ロード失敗はスキップして続行
    ws_tools = []
    try:
        ws_tools = akira_tools.load_workspace_tools()
        if ws_tools:
            claude_tools.extend(ws_tools)
            logger.info("ワークスペースの自作ツール %d件を登録: %s",
                        len(ws_tools), [getattr(t, "tool_name", "?") for t in ws_tools])
    except Exception:
        logger.exception("ワークスペースツールのロードに失敗しました（スキップします）")

    # --- 節約モード: Claudeエンジニア → DeepSeek V4.1 Flash（model_id: deepseek-flash）。
    #     通常時は Claudeエンジニア = claude-sonnet-5-5（$2/$10） ---
    _savings = is_savings_mode()
    if _savings:
        logger.info("💰 節約モード: Claudeエンジニア → DeepSeek V4.1 Flash (deepseek-flash) に切替")
        engineer_model = _create_deepseek_model()
        engineer_prompt = prompts.CLAUDE_ENGINEER_PROMPT + prompts.CLAUDE_ENGINEER_SAVINGS_NOTE
        engineer_model_id = DEEPSEEK_MODEL_ID
    else:
        engineer_model = models["claude"]
        engineer_prompt = prompts.CLAUDE_ENGINEER_PROMPT
        engineer_model_id = CLAUDE_MODEL_ID

    def _new_engineer_agent() -> "Agent":
        """呼び出しごとに新規 Agent（前回呼び出しの会話履歴を持ち越さない）。

        2026-10-17: 使い回しのエージェントで1回目にツールを190回叩き（所要170.2円）、
        その履歴を抱えたまま2回目を実行したところ、ツール11回のあとに最終応答が空で
        返り、作業が宙に浮いた。モデル呼び出しのたびに履歴を全量再送する作りなので、
        使い回しには ①費用がほぼ二次関数的に増える ②コンテキストが膨らんで応答が
        壊れる という二重の害がある（GPT税理士・Geminiママは2026-09-15に同じ理由で
        「毎回新規」へ統一済み。エンジニアだけが残っていた）。
        呼び出しをまたぐ状態は /tmp/site（サイトの実物）と /workspace（作業ファイル）に
        残るので、履歴を持ち越さなくても作業は続けられる。
        """
        return Agent(
            name="claude_engineer",
            model=engineer_model,
            system_prompt=engineer_prompt,
            tools=claude_tools,
            # Firecrawlの巨大結果が履歴に残り続けるのを防ぐ（2026-09-09: 66.5万トークン）。
            # per_turn=True でモデル呼び出し前に窓を切る。プロンプト側の cache+要約と併用。
            conversation_manager=SlidingWindowConversationManager(
                window_size=40,
                per_turn=True,
            ),
        )


    @tool
    def ask_claude_engineer(request: str, item_id: str = "", accept: str = "") -> str:
        """Claudeエンジニアに**1項目だけ**依頼する（リサーチ→執筆→レビュー→公開）。

        2026-11-21 の実測: 2項目を1回で渡すと、エンジニアは「残り呼び出し数」で
        自分でスコープを切り、2番目を**報告からも消した**（依頼1: 83ツール/51.9円、
        依頼2: 82ツール/48.9円）。だから**1回の依頼=1項目**を機械で強制する。

        Args:
            request: 依頼内容（**1項目だけ**。番号付きで2つ以上書くと機械が拒否する）
            item_id: この依頼の識別子（例: "OK-2"）。応答の最後に `DONE: <item_id>`
                     または `NOT_DONE: <item_id>` を書かせる。省略すると未確認扱いになる
            accept: 合格条件（機械が読める形で書く。例:
                    "china-ai の labs セクション内に lab-card が8枚ある"）
        """
        n = count_request_items(request)
        if n > 1:
            trace = trace_store.current()
            if trace:
                trace.event("delegate.rejected", agent="Claudeエンジニア",
                            item_id=item_id, reason="multi_item", items=n)
            return (
                "【依頼を分割して】1回の依頼に番号付き項目が %d 個あります。"
                "**1回の依頼は1項目だけ**にしてください（2026-11-21 に2項目渡して"
                "2番が丸ごと落ちた）。\n"
                "同じ内容を、項目ごとに ask_claude_engineer を1回ずつ呼んで出し直せ。"
                "各項目には item_id と accept（合格条件）を必ず付けること。\n"
                "今回は**何も実行していない**。" % n)
        if not item_id:
            item_id = "item-%d" % (len(_ITEM_LEDGER) + 1)
        record_item(item_id, request, accept, status="requested")
        return _run(_new_engineer_agent, engineer_model_id, "Claudeエンジニア",
                    request, item_id=item_id, accept=accept)

    return [ask_claude_engineer, ask_gpt_tax_advisor, ask_gemini_mother]


# =====================================================================
# 日報
# =====================================================================
def create_report_tool(collected: dict):
    from strands import tool

    @tool
    def write_daily_report(body_md: str, requests_to_okamo: str = "") -> dict:
        """本日の日報を書く（1日の最後に必ず呼ぶこと）。

        Args:
            body_md: 日報本文（Markdown）。やったこと・サイトの状況・明日の予定など。
                     機密情報（APIキー等）は絶対に書かないこと
            requests_to_okamo: okamoへの依頼事項・確認事項（なければ空文字）。
                     必ずAkira自身の口調（ハードボイルドでぶっきらぼう、だが身内には甘い）で
                     書くこと。「【確認】【意向確認】」等の事務的な見出し・ビジネス文書調は
                     禁止。okamoは身内だ。
                     良い例: 「Cyberの料金、お前にも見えねぇか。まあいい、情報が出たら
                     教えてくれ。次のテーマはマルチモーダル特集が一番伸びると俺は
                     見てるが、お前の目はどうだ」
        """
        collected["body_md"] = body_md + ledger_markdown()
        collected["requests_to_okamo"] = requests_to_okamo
        # Akira本体が自分で日報を書いた証跡。これが無い＝フォールバック日報なので、
        # okamoコメントの確認済みマーカーを進めない（未反映のコメントを消費しない）
        collected["report_written"] = True
        return {"status": "accepted"}

    return write_daily_report


def publish_daily_report(collected: dict, budget_status: dict) -> None:
    """日報をDynamoDB保存→HTML公開する。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    month_cost = budget.get_month_cost_jpy()
    cost_summary = (
        f"当月LLM費用 約{month_cost:.0f}円 / 予算{budget_status['monthly_budget_jpy']:.0f}円"
    )
    body = collected.get("body_md") or "（日報が生成されませんでした）"
    ledger = ledger_markdown()
    if ledger and "今日の依頼項目（機械の受領書" not in body:
        body += ledger
    report.save_report(today, body, collected.get("requests_to_okamo", ""), cost_summary)
    published = report.publish_reports()
    logger.info("日報公開: %s件 → %s", len(published), REPORTS_SITE_URL)


# =====================================================================
# 日次運用
# =====================================================================
def _freshness_queue_line(today: str) -> str:
    """鮮度キュー（R8）をプロンプト用のテキストにする。

    /workspace/tools/_freshness.py は _ 始まりなのでツールとしてはロードされない
    （ヘルパー扱い）。ここで読めない場合は空文字を返し、本処理は止めない。
    """
    import glob
    import importlib.util

    cand = glob.glob(os.path.join(os.path.abspath(WORKSPACE_LOCAL_DIR), "tools", "_freshness.py"))
    if not cand:
        return ""
    try:
        spec = importlib.util.spec_from_file_location("akira_freshness", cand[0])
        if spec is None or spec.loader is None:
            return ""
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        facts_path = os.path.join(os.path.abspath(WORKSPACE_LOCAL_DIR), "data", "facts.json")
        return module.build_queue(facts_path, today).strip()
    except Exception as e:  # noqa: BLE001
        logger.warning("鮮度キューの生成に失敗（本処理は続行）: %s", e)
        return ""


def _refresh_freshness_queue(today: str, limit: int = 3) -> str:
    """鮮度キューの先頭 N 件を**コードで取得**する（2026-11-15 / R8 の続き）。

    なぜ:
        キューをプロンプトに注入する方式は**2ラン連続で0件**だった（11-15）。
        Akira は「システムプロンプトに再取得対象が見当たらない」と述べ、
        自分が選んだURLを取りに行った。**毎回必ずやるべきことをモデルに頼むのを
        やめ、コードでやる**。

    戻り値はミッションに差し込む1〜3行のテキスト（失敗も書く）。
    """
    import glob
    import importlib.util

    tools_dir = os.path.join(os.path.abspath(WORKSPACE_LOCAL_DIR), "tools")
    facts_path = os.path.join(os.path.abspath(WORKSPACE_LOCAL_DIR), "data", "facts.json")

    def _load(name, module_id):
        p = os.path.join(tools_dir, name)
        if not os.path.exists(p):
            return None
        try:
            spec = importlib.util.spec_from_file_location(module_id, p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except Exception:  # noqa: BLE001
            return None

    fresh = _load("_freshness.py", "akira_freshness_q")
    fq = _load("fetch_quote.py", "akira_fetch_quote_q")
    if fresh is None or fq is None:
        return "鮮度キュー: 取得をスキップ（ツールを読み込めませんでした）"

    try:
        items = fresh.queue_items(facts_path, today, limit=limit)
    except Exception as e:  # noqa: BLE001
        return "鮮度キュー: 生成に失敗（%s）" % type(e).__name__

    if not items:
        return "鮮度キュー: **対象0件**（全部が7日以内に取得済み）"

    ok, ng = [], []
    for it in items:
        try:
            r = fq.fetch_quote(url=it["url"], key=it["key"])
        except Exception as e:  # noqa: BLE001
            r = {"status": "failed", "reason": type(e).__name__}
        if r.get("status") == "ok":
            ok.append("%s（%d字）" % (it["key"], r.get("chars", 0)))
        else:
            ng.append("%s（%s）" % (it["key"], str(r.get("reason", ""))[:40]))

    lines = ["## 鮮度キュー（この3件は**コードが取得済み**。取り直す必要はない）"]
    if ok:
        lines.append("- 取得OK: " + ", ".join(ok) +
                     " ※`fetched_at` は自動で今日に更新済み")
    if ng:
        lines.append("- **取得失敗**: " + ", ".join(ng) +
                     " → `source_gap_report` で理由を見て、URLを疑うか okamo に確認する")
    lines.append("- 失敗が1件でもあれば**日報に1行書く**（黙って取れていないことが一番まずい）")
    return "\n".join(lines)


def _release_watch_line(today: str) -> str:
    """公式ソースの見張り（2026-11-21）をミッション用テキストにする。

    なぜ:
        2026-11-21 のランは GPT-6.2 Astra / Sol の公開に**気づかなかった**。
        `_propose_themes()` の「新モデルの漏れ」は台帳を自分で走査しており、
        台帳に無いモデルは候補になりえない（自己参照）。台帳が古いと
        「漏れ 0件」という**偽の緑**になる。
        ここでは台帳ではなく**各社の公式料金ページ**を見て、台帳に無いIDを出す。

    失敗した場合は「取得できず（新モデル無し、ではない）」を必ず返す。
    """
    import glob
    import importlib.util
    import json

    cand = glob.glob(os.path.join(os.path.abspath(WORKSPACE_LOCAL_DIR), "tools",
                                  "watch_releases.py"))
    if not cand:
        return ("## 公式ソースの見張り: **未導入**（tools/watch_releases.py が無い）"
                " — 新モデルの見落としは検知できない。日報に書け。")
    try:
        spec = importlib.util.spec_from_file_location("akira_release_watch", cand[0])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        facts_path = os.path.join(os.path.abspath(WORKSPACE_LOCAL_DIR), "data", "facts.json")
        with open(facts_path, encoding="utf-8") as fh:
            models = (json.load(fh) or {}).get("models") or {}
        result = mod.scan(models, today)
        return mod.mission_line(result)
    except Exception as e:  # noqa: BLE001
        logger.warning("公式ソースの見張りに失敗（本処理は続行）: %s", e)
        return ("## 公式ソースの見張り: **失敗（%s）** — 新モデルが無い証拠ではない。"
                "日報に書け。" % type(e).__name__)


def _missing_tool_warning(mod) -> str:
    """必須ツールに @tool が付いているかを起動時に確認する（2026-11-15 追加）。

    なぜ:
        2026-11-15 のランで `tools.py` の `@tool` が1行消え、エンジニアに
        `site_upload` が渡らなかった。エンジニアは「ツールが無い」と判断して
        **boto3 でバケット名を総当たり**し（`llm.okamomedia.tokyo` 等で NoSuchBucket 4件）、
        最後は 8ファイルを `publish_file_to_site` で送ろうとして
        **出力だけで約45kトークン**を使った。デコレータ1行の欠落は
        `import main` の検品では見つからない（importは成功する）。
    """
    need = ("site_upload", "publish_file_to_site", "site_download", "get_site_file",
            "list_site_files", "generate_and_publish_image")
    missing = [n for n in need if not hasattr(getattr(mod, n, None), "tool_spec")]
    if not missing:
        return ""
    logger.error("必須ツールに @tool が無い: %s", missing)
    return ("## ⚠️ ツール欠落（機械検知・最優先で報告）\n"
            "- 使えないツール: %s\n"
            "- **S3へ shell/boto3 で直接アクセスして回避するな**（バケット名の推測は必ず失敗する）。"
            "まず publish_file_to_site などの残った手段で最小限を公開し、"
            "**この欠落を日報の冒頭と site_plan に書け**。\n" % ", ".join(missing))


def _propose_themes(today: str, limit: int = 3, watch_line: str = "") -> str:
    """今日の企画候補を**台帳とサイトから機械的に**出す（2026-11-15 / ★3）。

    なぜ:
        `site_plan` は okamo の指示で埋まっており、Akira は「今日なにを作るか」の
        入力を持っていなかった。入力が無いので毎回「何をしましょうか」と人に聞く
        ＝**企画の主体が okamo に移る**。プロンプトに「ネタはAkiraが考える」と
        書いても実行されない（この1週間の一貫した観測）ので、候補をコードで出す。
        Akira は「選ぶ」だけでよい。自分の案を出すのは自由。
    """
    import datetime as _dt
    import glob
    import json
    import re as _re

    facts_path = os.path.join(os.path.abspath(WORKSPACE_LOCAL_DIR), "data", "facts.json")
    site_dir = os.path.abspath(getattr(akira_tools, "SITE_LOCAL_DIR", "/tmp/site"))
    try:
        with open(facts_path, encoding="utf-8") as f:
            facts = json.load(f)
    except Exception as e:  # noqa: BLE001
        return "企画候補: 台帳を読めず（%s）" % e
    try:
        today_d = _dt.date.fromisoformat(today)
    except ValueError:
        return "企画候補: 日付が不正（%s）" % today

    cands = []
    models = facts.get("models") or {}

    # A-1. 公式ソースの見張り（2026-11-21）。**台帳の外**から新モデルを拾う。
    #      ここが無いと「台帳に無い＝漏れ0件」という自己参照の偽の緑になる。
    if watch_line:
        # 箇条書きの中に入るので、見出し記号と改行は潰して1項目にする
        flat = " / ".join(x.strip().lstrip("#").strip()
                          for x in watch_line.splitlines() if x.strip())
        cands.append(flat)
    # A0. 新モデルのリサーチと掲載（**毎回の最優先**。okamo確認 2026-11-15）
    #     直近21日のリリースで「単価が無い」または「料金比較/計算機/年表のどれかに未掲載」
    #     のものを機械で挙げる。ここが空なら新モデルの漏れは無い。
    recent = []
    for k, v in models.items():
        try:
            age = (today_d - _dt.date.fromisoformat(v.get("released") or "")).days
        except ValueError:
            continue
        if age < 0 or age > 21:
            continue
        shown = set(v.get("shown_on") or [])
        missing = [x for x in ("timeline", "pricing", "calculator") if x not in shown]
        price = v.get("price") or {}
        no_price = not (price.get("input") and price.get("output"))
        if missing or no_price:
            why = []
            if missing:
                why.append("未掲載: " + "/".join(missing))
            if no_price:
                why.append("単価未取得")
            recent.append("%s（%s・%s）" % (k, v.get("released"), "、".join(why)))
    if recent:
        cands.append("**【最優先】新モデルのリサーチと掲載**: %s → 公式で単価・提供段階を"
                     "確認して台帳に入れ、料金比較・計算機・年表の3面に載せる"
                     % "、".join(recent[:5]))
    else:
        cands.append("**【最優先】新モデルのリサーチと掲載**: 直近21日で漏れ 0件"
                     "（載っていない新モデルは無い）")

    # A. 最終更新が30日以上前のページ（更新が止まっている＝価値が落ちている）
    stale = []
    for p in glob.glob(os.path.join(site_dir, "**", "index.html"), recursive=True):
        rel = os.path.relpath(p, site_dir).replace(os.sep, "/")
        if rel == "index.html" or rel.startswith("en/"):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                t = f.read()
        except Exception:  # noqa: BLE001
            continue
        m = _re.search(r'class="updated-bar"[^>]*>.*?<time datetime="(\d{4}-\d{2}-\d{2})"',
                       t, _re.S)
        if not m:
            continue
        try:
            age = (today_d - _dt.date.fromisoformat(m.group(1))).days
        except ValueError:
            continue
        if age >= 30:
            stale.append((age, "/" + rel[:-len("index.html")]))
    stale.sort(reverse=True)
    if stale:
        cands.append("**更新が止まっているページ**: %s → 料金・状態を再取得して更新する"
                     % "、".join("%s（%d日）" % (r, a) for a, r in stale[:5]))

    # B. 提供状態が未確認のモデル（料金表の「状態」列が埋まらない原因）
    unknown = [k for k, v in models.items() if v.get("status") == "unknown"]
    if len(unknown) >= 10:
        cands.append("**提供状態が未確認のモデル %d件**（例: %s）→ 公式で状態を確認し "
                     "`status` を確定させる"
                     % (len(unknown), ", ".join(unknown[:4])))

    # C. preview のまま14日以上（GA/終了の判断が止まっている）
    long_preview = []
    for k, v in models.items():
        if v.get("status") != "preview":
            continue
        try:
            age = (today_d - _dt.date.fromisoformat(v.get("released") or "")).days
        except ValueError:
            continue
        if age >= 14:
            long_preview.append("%s（%d日）" % (k, age))
    if long_preview:
        cands.append("**preview のまま14日以上**: %s → GA/終了を公式で確認"
                     % ", ".join(long_preview[:4]))

    if not cands:
        return ("## 今日の企画候補\n- 台帳からは候補が出なかった（更新もれ・状態未確認なし）。"
                "**自分で企画を出せ**（okamoに聞くな）")

    lines = ["## 今日の企画候補（**コードが台帳とサイトから出した**）"]
    for i, c in enumerate(cands[:limit], 1):
        lines.append("%d. %s" % (i, c))
    lines += [
        "- この中から1〜2件を選べ。**自分で別案を出すのは自由**（そのほうが良い）。",
        "- 選んだテーマは `update_akira_config(key=\"site_plan\", ...)` に"
        "「Akira企画 %s: …」として残す。" % today,
        "- **okamoに「何を作りましょうか」と聞くな。** 企画と優先度はAkiraの仕事。",
    ]
    return "\n".join(lines)


DAILY_MISSION_TEMPLATE = """今日は {today} です。LLM Data Hub（{site_url}）の定期運用を開始してください。

## 前回の作業日
{last_work_line}

## 公開サイトの健全性チェック（毎朝の自動検査。決定論的でLLMコストは0）
{health_line}
- 違反が残っている場合は、まず自力で直せないか確認する（計算機データなら
  restore_published_data_file → verify_published_contracts で復旧確認）。
  決定論的に直せない種類の違反は Claudeエンジニアに最小の依頼として渡す
- **この結果は日報に必ず1行書く**（違反0件でも「異常なし」と書け。
  黙ってちゃ伝わらんぞ。表が空になった事故を人間が3.5時間気づかなかった実例がある）

{audit_line}

{freshness_line}

- 上の取得は**このランが始まる前に機械が済ませている**。同じURLを二度取りに行くな
- 失敗があれば、その理由を確かめて（`source_gap_report`）、URL自体を疑うか
  okamo に確認する。**失敗を黙って流すな**
- 余力があればキューの4件目以降を `fetch_quote` で拾ってよい（任意）

## 利用可能なWEBツール（すべて無料枠。factチェックはBrave→Firecrawlの順で）
- Brave Search（Web検索。factチェック第一選択）/ Firecrawl（URL指定でMarkdown取得。JSサイト対応。第二選択）
- GitHub MCP（公開リポジトリ読み取り専用）

## 今回の進め方
1. list_site_files で現在のサイト状態を軽く確認する（大きいHTMLは読まない）
2. 今回の作業テーマ（新規ページ or 既存ページ更新、1〜2件まで）を**自分で決める**。
   下の「今日の企画候補」はコードが台帳から出したものなので、ここから選べばよい
   （的外れなら自分で別案を出せ。**okamoに何を作るか聞くな**）。
   決めたテーマは site_plan に「Akira企画 YYYY-MM-DD: …」として残す
   （/workspace は前回から持ち越しの永続ワークスペース。drafts/に未完了作業が残っていれば
   その続きを優先テーマにする。参照はエンジニアに任せてよい）

{theme_line}
3. ask_claude_engineer は **1項目につき1回**呼ぶ。**番号付きで2項目以上を1回にまとめるな**
   （2026-11-21 の実測: 2項目渡したら2番目が丸ごと落ち、依頼1で83回・依頼2で82回ツールを叩いた）。
   呼ぶときは必ず次の3つを付ける:
   - `item_id`: 依頼の識別子（例 "OK-2"）。日報の受領書にそのまま出る
   - `accept`: **機械が読める合格条件**（例「labs セクション内の lab-card が8枚」
     「/mai/ の年表が日付降順で先頭が最新」）。「見出しがあること」のような見た目の条件は書くな
   - `request`: 1項目だけの依頼文（リサーチ・執筆・レビュー・公開はエンジニアの裁量に任せる）
   エンジニアは応答の最後に `DONE: <item_id>` か `NOT_DONE: <item_id>` を書く義務がある。
   書かなければ**ハーネスが未確認として日報に記録する**（あなたの文章で補えると思うな）。
   2項目以上を渡すと機械が拒否する（何も実行されない）。
4. Claudeエンジニアからの報告（公開したページ・GPT税理士の指摘件数・記録した課題）を確認する。
   よほど気になる点がない限り、あなた自身がask_gpt_tax_advisor/ask_gemini_motherを直接呼ぶ必要はない
   （通常はClaudeエンジニアに任せる）
5. 最後に write_daily_report で日報を書く（Claudeエンジニアの報告をもとにまとめる。
   **依頼事項は原則0件**。書いてよいのは「okamoにしか決められないこと」だけ:
   予算・契約やアカウント・法務判断・okamo本人の意向・外にしか無い事実。
   **企画・優先度・ページ構成の相談は書くな**（自分で決めて、決めたことと理由を日報に
   1行書く）。どうしても聞くときは俺の口調で書け。【確認】【意向確認】等の事務的な
   見出しはやめだ。身内に話すように書け）

## 注意（重要）
- 自分で考え込んだりWeb検索・factチェックを自分でやったりせず、Claudeエンジニアに一括委任すること。
  あなた自身の役割は「テーマ決定」と「最終確認・日報執筆」に絞る
- ask_claude_engineer は**項目ごとに1回**呼ぶ（1回に1項目。会話履歴の肥大化を避ける意味でも、
  2項目以上を1回に詰め込むと2番目が落ちる）。Claudeエンジニア内部でのGPT/Geminiとのやり取りは
  何度あっても問題ない
- 未達（`NOT_DONE`）を日報から消すな。**隠すと翌週に同じ穴が開く**（11-21 に実際に消えた）。
  日報の末尾には機械の受領書（依頼項目の表）が自動で付く。
- okamoのコメントで方針・優先度が決まったものは、その場でsite_planに写しておくこと
  （okamoのコメントは翌日以降は読めなくなる。site_planこそが恒久の作業リストだ）
- 作業を止められたら、速やかに日報を書いて終了すること
- サイト全体の一貫性（ナビゲーション・sitemap.xml）を保つこと
- GPT税理士・Gemini子育てママは門番ではなくアドバイザー。クリティカルな指摘（明確な誤情報・
  法的リスク・アダルト/犯罪関連）だけが公開停止の理由になる。軽微な指摘だけで作業や公開を
  止めず、site_planに課題として記録して先に進むこと（掲載情報の品質基準自体は下げない）
"""


def run_daily(dry_run: bool = False, no_publish: bool = False) -> None:
    from strands import Agent

    load_secrets_into_env()
    today = datetime.now(JST).strftime("%Y-%m-%d")
    collected: dict = {}

    # 起動直後の時計を必ずログに残す。2026-09-15のランでは okamoコメントのマーカーが
    # 「読んだ値のまま（2026-09-13）」で書き込まれ、updated_at だけが当日時刻（05:11:34）
    # という不整合が残った。today の算出（05:11:2x）と書き込み（05:11:34）の間で日付が
    # 2日進んだことになり、Fargateタスク起動直後の時計ずれが疑わしい。
    # ずれていると今日の日付でミッションを組めず日報の日付も誤るため、毎回記録して
    # 次回以降に検知できるようにする。
    logger.info(
        "起動時刻: %s (UTC %s) / today=%s",
        datetime.now(JST).isoformat(), datetime.now(timezone.utc).isoformat(), today,
    )

    # --- 1. 予算ゲート ---
    budget_status = budget.check_budget()
    logger.info("予算: %s", budget_status)
    if not budget_status["can_run"]:
        logger.warning("予算超過のため本日の作業を停止します")
        collected["body_md"] = (
            f"## 予算超過による作業停止\n"
            f"当月のLLM費用が予算に達したため、本日の作業は行いませんでした。\n"
            f"- 当月費用: 約{budget_status['month_cost_jpy']}円 / "
            f"予算{budget_status['monthly_budget_jpy']}円\n"
            f"翌月に自動再開します。"
        )
        if not dry_run:
            publish_daily_report(collected, budget_status)
        return

    _start_run_deadline()
    prev_alarm = signal.signal(signal.SIGALRM, _alarm_handler)
    remaining = max(1, int(_deadline_remaining_seconds()))
    signal.alarm(remaining)
    logger.info("作業デッドライン: %d秒", remaining)

    # --- 1.4 記録の開始（2026-11-21）---
    # 何を頼み・何を渡し・何が起きたかを run_id で繋ぐ。記録の失敗で本処理は止めない。
    trace = trace_store.start(today=today)
    _ITEM_LEDGER.clear()
    trace.event("run.start", dry_run=dry_run, no_publish=no_publish,
                month_cost_jpy=budget_status.get("month_cost_jpy"),
                budget_jpy=budget_status.get("monthly_budget_jpy"))
    logger.info("trace: run_id=%s（テーブル=%s）", trace.run_id, trace_store.TRACE_TABLE)

    # --- 1.5 サイト全体をローカル作業フォルダへDL（エンジニアのローカル編集→一括アップ用） ---
    try:
        dl = akira_tools.download_site()
        logger.info("サイトDL: %s件 → %s", dl["count"], dl["dest_dir"])
    except Exception:
        # DL失敗は致命的ではない（従来の publish_file_to_site 経由で作業可能なため続行）
        logger.exception("サイトのローカルDLに失敗しました（publish_file_to_site で代替可能）")

    # --- 1.6 永続ワークスペースの復元（自作ツール/パーツ/キャッシュ/持ち越し原稿） ---
    try:
        ws = akira_tools.restore_workspace()
        logger.info("ワークスペース復元: %s", ws)
    except Exception:
        # ワークスペースの失敗で日次運用を止めない（初回起動はバケットが空で正常）
        logger.exception("ワークスペースの復元に失敗しました（続行します）")

    # --- 1.7 公開サイトの契約チェック（決定論的・LLMコスト0）---
    # 2026-09-27: 計算機の実行時データ /data/models.json を料金SOT（ワークスペースの
    # 真実データ）で上書きし、/calculator/ と /en/calculator/ の表が全滅した。
    # ページは200を返すため既存の公開ゲート（check_site_pages=HTMLのみ /
    # verify_publish=MD5一致のみ）はどれも検出できず、「静かな故障」として人間が
    # 見つけるまで残った。対策として毎朝ここで公開中の**現物**を機械検査し、
    # 直せる種類の故障は決定論的に修復する（LLMの判断に依存させない）。
    health_line = "公開契約チェック: 未実施"
    try:
        contract = akira_tools.check_published_contracts()
        logger.info("%s", contract["summary"])
        if contract["violations"]:
            logger.warning("公開契約の違反: %s", contract["violations"])
            if any(akira_tools.DATA_MODELS_KEY in v for v in contract["violations"]):
                repair = akira_tools.restore_published_data_file()
                logger.info("計算機データの自動復元: %s", repair)
                contract = akira_tools.check_published_contracts()
        health_line = contract["summary"]
        health_line += ("（公開サイトは正常）" if not contract["violations"]
                        else "（残: %s）" % " / ".join(contract["violations"][:5]))
    except Exception:
        logger.exception("公開契約チェックに失敗しました（続行します）")
        health_line = "公開契約チェック: 実行失敗（ログ参照）"
    logger.info("健全性: %s", health_line)

    # --- 1.8 今日の必須監査（ページの古い情報・追記の混在・キービジュアルの取り残し） ---
    # 2026-11-17: okamo指摘。①/china-ai/ のメインビジュアルだけ 2026-10-29 の情報が
    # 残っていた ②/deepseek-v4-1-flash/ が9月の話と10-17の更新の寄せ集めになっていた。
    # 「気づくのは人間」をやめるため、GA4のPV・GSCのクリックで優先度をつけた
    # **対象の選定をコードで行い**、ミッションに義務として差し込む
    # （上位5ページは7日以内、それ以外は21日以内に1回）。
    audit_line = "## 今日の必須監査\n- 選定に失敗しました（ログ参照）"
    try:
        import page_audit as _page_audit
        audit_line = _page_audit.mission_line(today)
        logger.info("必須監査: %s", audit_line.replace("\n", " / ")[:220])
    except Exception:  # noqa: BLE001
        logger.exception("監査対象の選定に失敗しました（続行します）")

    # ワークスペースのバックアップ整理は「後処理」（save_workspace の後）で行う。
    # save_workspace() はローカル全件をS3へupsertするため、保存より先に回転させると
    # 同じランで消したはずの世代がローカルから復活する（2026-09-27修正）
    rotation_line = "バックアップ整理: 未実施"

    # --- 2. 設定読み込み（自己改善の反映）---
    system_prompt = config_store.load_system_prompt()
    skills = config_store.load_skills()
    if skills:
        system_prompt += "\n\n## Skills\n" + "\n\n".join(
            f"### {s['name']}\n{s['content']}" for s in skills
        )
    # 不変の運営ルールはコード側（静的）に置く。site_plan には「今の状況」だけを入れる。
    # 2026-11-15: 規則と経緯が site_plan に溜まり 18,000字まで膨れたため分離した。
    # 注意: prompts は他関数内で import されている（モジュール直下には無い）。
    # 2026-11-15 にモジュール直下で参照して NameError で即死した。
    import prompts as _prompts
    system_prompt += "\n\n" + _prompts.SITE_RULES
    site_plan = config_store.load_config("site_plan")
    if site_plan:
        system_prompt += f"\n\n## サイトの今の状況（自分で更新可能）\n{site_plan}"

    # 2026-11-15: 鮮度キュー（R8）。台帳の fetched_at から「今日取り直すべきキー」を
    # 機械的に並べて注入する。LLMの判断は挟まない。
    # これが無いと「古い quote が新しい事実を上書きする」経路が塞げない。
    # 2026-11-15: テキスト注入は廃止。モデルは読んでも動かなかった（2ラン連続0件）。
    # いまは _refresh_freshness_queue() がミッションの直前に**コードで取得**する。

    # okamoの直近コメント（日報へのフィードバック）をミッションに含める
    # 予算超過で数日〜数週間ノーラン（正確には予算ゲートで停止）が続くことがあるため、
    # 固定日数ではなく「前回実際にAkiraがコメントを確認した日」からの差分を必ず取得する。
    # 前回確認日はconfig_storeにマーカー保存（予算超過で停止した日はここまで到達しない＝
    # マーカーは更新されず、取りこぼしなく次回に持ち越される）
    last_comment_check = config_store.load_config("last_comment_check_date")
    comments = report.get_recent_comments(since=last_comment_check)
    if comments:
        system_prompt += "\n\n## okamoからの直近コメント（必ず考慮しろ）\n" + "\n".join(
            f"- [{c['date']}] {c['text']}" for c in comments
        )
    # 今回確認した日のマーカー更新は「後処理」（日報公開の後）で行う。
    # ここで進めてしまうと、Akira本体のクラッシュや空応答で日報が出なかった場合に
    # コメントだけ消費され、翌日以降 site_plan にも日報にも残らない（2026-09-27修正）

    # 前回の実作業日もAkira自身に伝える（予算超過で数日〜数週間空くことがあるため、
    # 間隔が空いた場合は料金改定・新モデル等の情報が古くなっていないか優先確認させる）
    if last_comment_check:
        gap_days = (
            datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(last_comment_check, "%Y-%m-%d")
        ).days
        last_work_line = f"前回の実作業日: {last_comment_check}（{gap_days}日ぶりの再開です）"
        if gap_days > 7:
            last_work_line += (
                "\n※間隔が空いているため、料金改定・新モデルリリース等サイト掲載情報が"
                "古くなっていないか優先的に確認・更新すること。"
            )
    else:
        last_work_line = "前回の実作業記録なし（初回実行です）"

    # --- 3. Akiraエージェント構築 ---
    models = _create_models()
    akira_extra_tools = []
    if ENABLE_GA4_MCP:
        akira_extra_tools.append(_create_ga4_mcp())
    if ENABLE_BIGQUERY_MCP:
        akira_extra_tools.append(_create_bigquery_mcp())

    delegation = create_delegation_tools(
        models, run_budget_jpy=budget_status["remaining_jpy"],
        block_publish=(dry_run or no_publish),
    )

    # Akira自身のツール（delegation + 直接使うツール）
    # ※画像系（take_screenshot / image_reader / fetch_image_from_url）はAkiraから外す
    #   （DeepSeekのAnthropic互換APIが画像ブロック非対応のため。Fableでも不要と判断）。
    #   画像・UXの確認は ask_gemini_mother 経由で委任できるので運用に支障はない。
    from strands_tools import file_read
    akira_tools_list = [
        *delegation,
        akira_tools.get_site_file,
        akira_tools.list_site_files,
        akira_tools.list_local_files,
        # 公開サイトの健全性チェックと決定論的修復（読取＋許可キーのみの修復）
        akira_tools.verify_published_contracts,
        akira_tools.restore_published_data_file,
        # ページ監査（今日の対象はコードが優先度順に選んでいる）
        page_audit.audit_pages,
        page_audit.set_page_priority,
        file_read,
        akira_tools.update_akira_config,
        create_report_tool(collected),
        _create_brave_mcp(),
        *akira_extra_tools,
    ]
    # 自己点検（全ゲート＋決定事項＋台帳ズレを1回で返す）は**Akiraも持つ**。
    # 2026-11-15: 6本のゲートを個別に叩く手順は踏まれなかった（Akiraは
    # 「check_page_shape は存在しない」と誤認した）。1呼び出しにまとめて渡す。
    try:
        for _t in (akira_tools.load_workspace_tools() or []):
            if getattr(_t, "tool_name", "") == "self_check":
                akira_tools_list.append(_t)
                logger.info("Akiraに self_check ツールを追加しました")
    except Exception:  # noqa: BLE001
        logger.exception("self_check の登録に失敗しました（続行）")
    firecrawl = _create_firecrawl_mcp()
    if firecrawl:
        akira_tools_list.append(firecrawl)
    github = _create_github_mcp()
    if github:
        akira_tools_list.append(github)

    akira = Agent(
        name="akira",
        model=models["akira"],
        system_prompt=system_prompt,
        tools=akira_tools_list,
    )

    # 鮮度キューの先頭3件は**コードで取得**する（モデルに頼むと0件が続いた）。
    freshness_line = _refresh_freshness_queue(today, limit=3)
    logger.info("鮮度キュー: %s", freshness_line.replace("\n", " / ")[:220])

    # 公式ソースの見張り（2026-11-21）。台帳の外から新モデルを拾う。
    watch_line = _release_watch_line(today)
    logger.info("公式ソースの見張り: %s", watch_line.replace("\n", " / ")[:220])

    theme_line = _propose_themes(today, limit=3, watch_line=watch_line)
    logger.info("企画候補: %s", theme_line.replace("\n", " / ")[:220])

    tool_warn_line = _missing_tool_warning(akira_tools)
    mission = DAILY_MISSION_TEMPLATE.format(
        today=today, site_url=LLM_SITE_URL, last_work_line=last_work_line,
        health_line=health_line, freshness_line=freshness_line,
        theme_line=theme_line, audit_line=audit_line,
    )
    if tool_warn_line:
        mission = tool_warn_line + "\n" + mission
    if dry_run:
        mission += "\n\n【重要】今日はドライランです。公開・依頼は行わず、計画の提示だけしてください。"
    if no_publish:
        mission += ("\n\n【重要】今日はテストランです。**作業は通常どおり最後まで行う**"
                    "（リサーチ・cache保存・執筆・レビューまで）。ただし site_upload と "
                    "publish_file_to_site は無効化されており公開できません。"
                    "日報も公開しない。公開以外は本番と同じ手順で進め、"
                    "「何を取得し・何を根拠に・何を作ったか」を最後に詳しく報告すること。")

    _debug_log_io("指示", "Akira本体", f"system_prompt:\n{system_prompt}\n\nmission:\n{mission}")
    trace = trace_store.current()
    if trace:
        # **最終系**のシステムプロンプト（lessons・skills・SITE_RULES・site_plan・
        # okamoコメントを合成した後）をそのまま残す。プロンプト自体が間違って
        # いることがあるので、後から全文を見られるようにする。
        trace.prompt("Akira本体", system_prompt)
        trace.event("mission.built", body=trace.blob("mission.built", mission),
                    theme_chars=len(theme_line), watch_chars=len(watch_line))
    usage_model_id = DEEPSEEK_MODEL_ID if AKIRA_USE_DEEPSEEK else AKIRA_MODEL_ID
    try:
        for attempt in range(1, _MAX_EMPTY_ATTEMPTS + 1):
            tools_before = _tool_call_count(akira)
            result = akira(mission)
            _debug_log_io("応答", "Akira本体", str(result))
            cost = budget.collect_agent_usage(result, usage_model_id, purpose="akira:daily", agent=akira)
            logger.info("Akira本体 完了 (約%.1f円 / 本日合計約%.1f円)", cost, budget.get_run_spent_jpy())
            if collected.get("body_md") or not _is_empty_response(result):
                # 正常。日報を書いたか、少なくともモデルは動いている（内容の判断はモデルに任せる）
                break

            # --- ここから下は「空応答」= 本文もツール呼び出しも1件も届かなかった場合 ---
            tool_calls = max(0, _tool_call_count(akira) - tools_before)
            if tool_calls:
                # 途中で途切れたケース。やり直すと二重作業（再委任・再公開）になりうるため再試行しない
                logger.error(
                    "Akira本体の応答が空（ツール実行%d回の後に途切れ）。再試行はしません", tool_calls
                )
                collected["body_md"] = (
                    "## 本日の運用は途中で止まりました（LLMの空応答）\n"
                    f"ツール実行が{tool_calls}回あった後、Akira本体の応答が空になりました。"
                    "作業は途中まで進んでいる可能性があります（公開状況はサイトのファイル一覧を参照）。\n"
                )
                break
            if attempt == _MAX_EMPTY_ATTEMPTS:
                logger.error("Akira本体の応答が%d回連続で空でした（本日は作業できません）", _MAX_EMPTY_ATTEMPTS)
                collected["body_md"] = (
                    "## 本日の作業はできませんでした（LLMの空応答）\n"
                    f"Akira本体への呼び出しが{_MAX_EMPTY_ATTEMPTS}回連続で「空応答」になりました。\n"
                    "HTTPは成功しているのに、本文もツール呼び出しも1件も届いていない状態です"
                    "（プロバイダ側のストリーム異常。usageが取れないため費用は計上されていません）。\n\n"
                    "- サイトへの変更: なし（公開物は前回のまま）\n"
                    "- 次回: 同じ手順で自動再試行します。連日続く場合はモデル切替を検討します\n"
                )
                break
            logger.warning(
                "Akira本体の応答が空でした（%d/%d回目, stop_reason=%r）。課金ゼロなので再試行します",
                attempt, _MAX_EMPTY_ATTEMPTS, getattr(result, "stop_reason", None),
            )
            # 空のassistantメッセージが履歴に残ると次ターンのリクエストが不正になりうるため消す
            akira.messages.clear()
    except _RunDeadlineExceeded:
        logger.warning("作業デッドライン（%d秒）に達したため打ち切ります", RUN_DEADLINE_SECONDS)
        if not collected.get("body_md"):
            collected["body_md"] = (
                "## 本日の運用は時間上限で終了しました\n"
                "作業時間が上限に達したため打ち切りました。公開状況はサイトのファイル一覧で確認してください。"
            )
            collected.setdefault("requests_to_okamo", "")
    except Exception as e:
        # 【2026-08-13 対策】Anthropic APIの一時的なサーバーエラー(500)などでAkira本体の
        # 応答生成が失敗すると、イベントループが例外を投げてタスクがクラッシュし、
        # 日報が生成されないことがあった（当日実機で "Internal server error" を確認）。
        # ページ更新はエンジニアが完了済みの場合が多いため、ここで例外を捕捉し、
        # フォールバックの日報を書いて後処理（invalidation + 公開）を続行する。
        # 500はサーバー側の一時障害でリトライしても成功する保証が低く、再送コストも
        # 大きいため、あえてリトライはせず「日報だけは確実に出す」方針を採る。
        logger.exception("Akira本体の実行中に例外が発生しました（フォールバック日報で続行します）")
        if not collected.get("body_md"):
            spent = budget.get_run_spent_jpy()
            collected["body_md"] = (
                f"## 本日の運用は途中で終了しました（自動フォールバック）\n"
                f"Akira本体の応答生成中にエラーが発生したため、通常どおりの日報を書けませんでした。\n\n"
                f"- エラー種別: `{type(e).__name__}`\n"
                f"- 本日累計LLM費用: 約{spent:.1f}円\n\n"
                f"サイトへの作業・公開状況の詳細は、次回の日報またはサイトのファイル一覧で確認してください。"
            )
            collected.setdefault("requests_to_okamo", "")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_alarm)
        # --- 永続ワークスペースの保存（日報公開より先に。ここは finally なので
        # Akira本体のクラッシュ・タイムアウト時も通り、途中の下書きが翌日に持ち越される） ---
        if not dry_run:
            try:
                ws = akira_tools.save_workspace()
                logger.info("ワークスペース保存: %s", ws)
            except Exception:
                # 保存失敗で日報公開・invalidationを止めない
                logger.exception("ワークスペースの保存に失敗しました（続行します）")

    # --- 4. 後処理 ---
    if not dry_run and not no_publish:
        # 公開後の健全性チェック（その日の公開で壊れた場合に翌朝まで気づかない、を防ぐ）。
        # 結果は body_md に直に足して日報に必ず載せる（LLMの書き忘れに依存させない）。
        try:
            post = akira_tools.check_published_contracts()
            if post["violations"]:
                logger.error("公開後の契約違反: %s", post["violations"])
                if any(akira_tools.DATA_MODELS_KEY in v for v in post["violations"]):
                    repair = akira_tools.restore_published_data_file()
                    logger.info("公開後の自動復元: %s", repair)
                    post = akira_tools.check_published_contracts()
            post_line = post["summary"] + (
                "（公開サイトは正常）" if not post["violations"]
                else "（残: %s）" % " / ".join(post["violations"][:5])
            )
        except Exception:
            logger.exception("公開後の契約チェックに失敗しました（日報には失敗として記載）")
            post_line = "公開後の契約チェック: 実行失敗（ログ参照）"

        # ワークスペースのバックアップ整理（決定論的）。
        # notes/backup で始まる日付つきスナップショット（backup- と backup_）。
        # 増え続けると「どれが正か」が分からなくなるため、古い世代だけを消す。
        # 削除できるのは notes/backup* のみ（IAMでも同じ範囲）で、最新世代は必ず残す。
        # ※必ず save_workspace（finally）の後に実行する。先に消すと保存で復活する
        try:
            rot = akira_tools.rotate_workspace_backups()
            logger.info("バックアップ整理: %s", rot)
            if rot.get("status") == "rotated":
                rotation_line = ("バックアップ整理: 古い %d 世代・%d ファイルを削除"
                                 "（最新世代 %s は保持）"
                                 % (len(rot.get("deleted_generations", [])),
                                    rot.get("deleted_count", 0), rot.get("newest")))
            else:
                rotation_line = "バックアップ整理: %s" % rot.get("status")
        except Exception:
            logger.exception("バックアップ整理に失敗しました（続行します）")
            rotation_line = "バックアップ整理: 実行失敗（ログ参照）"

        # ページ監査の実施状況（決定論的）。割り当てたのに走っていない場合は
        # 日報に残す（LLMの「やりました」を信用しない）。
        try:
            audit_done_line = page_audit.verify_assigned(today)
        except Exception:  # noqa: BLE001
            logger.exception("監査の実施確認に失敗しました（続行します）")
            audit_done_line = "ページ監査: 実施確認に失敗（ログ参照）"

        collected["body_md"] = (collected.get("body_md") or "") + (
            "\n\n## 自動メンテナンス（決定論的）\n"
            "- " + rotation_line + "\n"
            "- " + post_line + "\n"
            "- " + audit_done_line + "\n"
        )
        akira_tools.flush_invalidations()
        if no_publish:
            # テストラン: 日報は公開しない（同日の日報を上書きしないため）。
            # 成果はCloudWatchログに残す。
            logger.info("テストランのため日報は公開しません")
        else:
            publish_daily_report(collected, budget_status)
        # 日報を出し終えてからマーカーを進める（ドライランでは進めない）。
        # フォールバック日報（クラッシュ・デッドライン・空応答）のときは okamoコメントが
        # 実際には反映されていないため進めない＝次回に読み直して取りこぼしを防ぐ。
        # ※起動時の時計ずれで today が過去日になってもコメントを取りこぼさないよう、
        #   マーカーは絶対に後退させない（max）。ISO形式の日付は文字列比較で大小が正しい。
        if collected.get("report_written"):
            config_store.save_config(
                "last_comment_check_date", max(today, last_comment_check or today)
            )
        else:
            logger.warning(
                "日報がフォールバックだったため、okamoコメントの確認済みマーカーは"
                "進めません（未反映のコメントを次回に読み直します）"
            )
    trace = trace_store.current()
    if trace:
        trace.event("run.end", run_spent_jpy=round(budget.get_run_spent_jpy(), 1),
                    items=len(_ITEM_LEDGER),
                    not_done=sum(1 for r in _ITEM_LEDGER if r["status"] != "done"),
                    report_written=bool(collected.get("report_written")))
    logger.info("=== 本日の運用終了 (trace run_id=%s) ===",
                trace.run_id if trace else "-")


def run_wi_test() -> None:
    """GCP Workload Identity（AWS→GCPキーレス連携）の疎通だけを検証する。

    【重要】list_tools_sync() はMCPプロトコル上のスキーマ照会に過ぎず、GCP側の認証は
    発生しない（サブプロセスが起動して応答するだけならIMDS/WI認証なしで成功してしまう）。
    そのため実際にツールを呼び出し、GCP APIへの認証込みの疎通を検証する
    （call_tool_sync は例外を投げず status="error"/"success" のdictを返す点に注意）。
    さらにMCPサーバー実装によっては内部で例外を捕捉しstatus="success"のままcontentに
    エラー文言を埋め込んで返す場合があるため、statusだけでなくcontentも必ず出力して
    目視確認すること（2026-07-09: 実際にGA4側でこのケースを確認済み）。

    LLM呼び出し・予算ゲートを一切通さないため、予算超過中でも無料で実行できる。
    ECS Fargate環境でIMDS(169.254.169.254)に到達できるか等の確認用（デプロイ後の
    動作確認に使う。日次運用フローとは無関係）。
    """
    logger.info("=== Workload Identity 疎通テスト開始 ===")
    try:
        ga4 = _create_ga4_mcp()
        with ga4:
            result = ga4.call_tool_sync(
                tool_use_id="test-wi-ga4", name="get_account_summaries", arguments={}
            )
        logger.info("GA4 MCP: status=%s content=%s", result.get("status"), result.get("content"))
    except Exception:
        logger.exception("GA4 MCP: NG")

    try:
        bq = _create_bigquery_mcp()
        with bq:
            result = bq.call_tool_sync(
                tool_use_id="test-wi-bq", name="list_dataset_ids", arguments={}
            )
        logger.info("BigQuery MCP: status=%s content=%s", result.get("status"), result.get("content"))
    except Exception:
        logger.exception("BigQuery MCP: NG")
    logger.info("=== Workload Identity 疎通テスト終了 ===")


def main():
    parser = argparse.ArgumentParser(description="Akira — LLM Data Hub 運営エージェント")
    parser.add_argument("--dry-run", action="store_true", help="公開せず計画のみ")
    parser.add_argument("--no-publish", action="store_true",
                        help="作業は本番どおり行うが公開しない（テストラン）。"
                             "site_upload/publish_file_to_site を無効化し、日報も出さない")
    parser.add_argument("--test-wi", action="store_true",
                         help="GCP Workload Identityの疎通テストのみ実行（LLM呼び出し・予算ゲートなし）")
    args = parser.parse_args()
    if args.test_wi:
        run_wi_test()
        return
    run_daily(dry_run=args.dry_run, no_publish=args.no_publish)


if __name__ == "__main__":
    main()

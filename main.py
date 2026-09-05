# main.py — Akira エントリーポイント
#
# 毎朝Fargateタスクとして起動される。
#   python main.py            → 通常の日次運用
#   python main.py --dry-run  → 公開せずに計画だけ出力（ローカル確認用）
#
# フロー:
#   1. シークレット読み込み → 予算ゲート（超過なら日報のみ書いて終了）
#   2. DynamoDBからシステムプロンプト/skills読み込み（自己改善の反映）
#   3. Akira（claude-fable-5）がリサーチ・計画・3AIへの作業依頼を実施
#   4. 日報を生成して akira.okamomedia.tokyo へ公開
#   5. 全エージェントのトークン使用量を akira-usage へ記録

import argparse
import logging
import os
import signal
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

import budget
import config_store
import report
import settings
import tools as akira_tools
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
_run_deadline_monotonic: float | None = None


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
    """DeepSeek V4 Pro（Anthropic互換API）。節約モードのエンジニア役 / Akira本体で使用。

    LiteLLM+Chat Completions は reasoning_content がマルチターンで欠落するため使わない。
    max_tokens は DEEPSEEK_MAX_TOKENS（既定384000=公式MAX OUTPUT上限）。
    readタイムアウトは DEEPSEEK_READ_TIMEOUT（既定3600s。SDK既定600sは
    384K出力+thinkingの長大生成で切断されうるため拡張）。
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
    """DEBUG_TOOL_LOGGING有効時、LLMへの指示/応答をCloudWatchへ出力する（長文は上限で切り詰め）。"""
    if not DEBUG_TOOL_LOGGING:
        return
    truncated = text if len(text) <= _DEBUG_LOG_LIMIT else text[:_DEBUG_LOG_LIMIT] + f"...(以下省略, 全{len(text)}文字)"
    logger.debug("[%s] %s:\n%s", agent_name, direction, truncated)


# =====================================================================
# モデル / エージェント生成
# =====================================================================
def _create_models():
    from strands.models.anthropic import AnthropicModel
    from strands.models.gemini import GeminiModel
    from strands.models.openai_responses import OpenAIResponsesModel

    if AKIRA_USE_DEEPSEEK:
        # テスト運用: Akira本体をDeepSeek V4 Pro（Anthropic互換API）に切替。
        # モデル名は deepseek-v4-pro を明示する（claude-fable-5 のままだと DeepSeek 側が
        # 未対応名として deepseek-v4-flash に自動マッピングしてしまう罠がある）。
        # 予算記録は実モデル(deepseek-v4-pro)で行い、正しい単価(0.66/1.98)で見積もる。
        logger.info("💰 Akira本体 → DeepSeek V4 Pro (Anthropic互換API) に切替")
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
        "gpt": OpenAIResponsesModel(
            client_args={"api_key": os.getenv("OPENAI_API_KEY")},
            model_id=OPENAI_MODEL_ID,
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


def create_delegation_tools(models, run_budget_jpy: float):
    """3AIを「ツール」としてAkiraに渡す（agent-as-toolパターン）。

    各呼び出しのトークン使用量は個別モデルIDで akira-usage に記録する。
    MCPクライアントはセッション競合を避けるためエージェントごとに個別生成する。
    run_budget_jpy: 今回実行で使える上限（＝月次予算の残額。ハードリミット）。
    """
    from strands import Agent, tool

    import prompts

    def _run(agent: "Agent", model_id: str, name: str, request: str) -> str:
        if _deadline_exceeded():
            return _STOP_WORK_MSG
        spent = budget.get_run_spent_jpy()
        if spent >= run_budget_jpy:
            logger.warning("予算ガード発動: spent=%.1f remaining_limit=%.1f", spent, run_budget_jpy)
            return _STOP_WORK_MSG
        _debug_log_io("指示", name, request)
        result = agent(request)
        _debug_log_io("応答", name, str(result))
        cost = budget.collect_agent_usage(result, model_id, purpose=f"delegate:{name}", agent=agent)
        logger.info("%s 完了 (約%.1f円 / 本日累計約%.1f円)", name, cost, budget.get_run_spent_jpy())
        return str(result)

    # --- 共通WEBツール（全員に配布）---
    firecrawl = _create_firecrawl_mcp()
    brave = _create_brave_mcp()
    screenshot_tool = akira_tools.take_screenshot
    fetch_image = akira_tools.fetch_image_from_url
    from strands_tools import file_read, image_reader

    # Firecrawl/Braveの無料枠注意文（ツール説明に含める）
    _web_tool_note = (
        "※無料枠で運用中。APIクォータ超過エラーが出た場合は別のツール（Brave/Firecrawl相互）で補完すること。"
    )

    gpt_tools = [akira_tools.get_site_file, akira_tools.list_site_files,
                 akira_tools.list_local_files, akira_tools.list_workspace_files, file_read,
                 brave, screenshot_tool, fetch_image, image_reader]
    if firecrawl:
        gpt_tools.append(firecrawl)
    gpt_agent = Agent(
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
    gemini_agent = Agent(
        name="gemini_mother",
        model=models["gemini"],
        system_prompt=prompts.GEMINI_MOTHER_PROMPT,
        tools=gemini_tools,
    )

    @tool
    def ask_gpt_tax_advisor(request: str) -> str:
        """GPT税理士にレビューを依頼する（ビジネス価値・PV貢献の観点とfactチェック。門番ではなくアドバイザー）。

        Args:
            request: レビュー対象（サイト内パスや本文）と確認してほしい観点
        """
        return _run(gpt_agent, OPENAI_MODEL_ID, "GPT税理士", request)

    @tool
    def ask_gemini_mother(request: str) -> str:
        """Gemini子育てママに依頼する（画像生成・初心者目線のわかりやすさチェック）。

        Args:
            request: 依頼内容。画像なら目的と公開先パス、チェックなら対象ページ。
                     画像の視認や大規模なUXチェックは1回の依頼につき2ページ/2枚までに絞ること
                     （並列の大量file_readや複数画像は入力トークンが爆発する。
                     2026-09-05実績: 1回のUXレビューで約1,245円消費）
        """
        return _run(gemini_agent, GEMINI_MODEL_ID, "Gemini子育てママ", request)

    # Claudeエンジニアの追加ツール（オプショナル）
    claude_tools = [
        akira_tools.publish_file_to_site,
        akira_tools.get_site_file,
        akira_tools.list_site_files,
        akira_tools.list_local_files,
        akira_tools.list_workspace_files,
        akira_tools.site_download,
        akira_tools.site_upload,
        akira_tools.update_akira_config,
        akira_tools.get_site_plan,
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
    try:
        ws_tools = akira_tools.load_workspace_tools()
        if ws_tools:
            claude_tools.extend(ws_tools)
            logger.info("ワークスペースの自作ツール %d件を登録: %s",
                        len(ws_tools), [getattr(t, "tool_name", "?") for t in ws_tools])
    except Exception:
        logger.exception("ワークスペースツールのロードに失敗しました（スキップします）")

    # --- 節約モード: Claudeエンジニア → DeepSeek V4 Pro ---
    _savings = is_savings_mode()
    if _savings:
        logger.info("💰 節約モード: Claudeエンジニア → DeepSeek V4 Pro に切替")
        engineer_model = _create_deepseek_model()
        engineer_prompt = prompts.CLAUDE_ENGINEER_PROMPT + prompts.CLAUDE_ENGINEER_SAVINGS_NOTE
        engineer_model_id = DEEPSEEK_MODEL_ID
    else:
        engineer_model = models["claude"]
        engineer_prompt = prompts.CLAUDE_ENGINEER_PROMPT
        engineer_model_id = CLAUDE_MODEL_ID

    claude_agent = Agent(
        name="claude_engineer",
        model=engineer_model,
        system_prompt=engineer_prompt,
        tools=claude_tools,
    )


    @tool
    def ask_claude_engineer(request: str) -> str:
        """Claudeエンジニアに今回分の作業をまとめて依頼する（現場責任者としてリサーチ→執筆→
        GPT税理士レビュー→必要ならGemini画像/UX→公開までを自律的に一気通貫で行い、最後に結果を
        要約して返す）。同じエージェントの会話履歴が肥大化するため、原則1回のみ呼ぶこと。

        Args:
            request: 依頼内容。今日のテーマ候補・特筆事項を伝えれば十分（細かい手順の
                     指示は不要。リサーチ・執筆・レビュー依頼・公開判断はClaudeエンジニアに任せる）
        """
        return _run(claude_agent, engineer_model_id, "Claudeエンジニア", request)

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
        collected["body_md"] = body_md
        collected["requests_to_okamo"] = requests_to_okamo
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
    report.save_report(today, body, collected.get("requests_to_okamo", ""), cost_summary)
    published = report.publish_reports()
    logger.info("日報公開: %s件 → %s", len(published), REPORTS_SITE_URL)


# =====================================================================
# 日次運用
# =====================================================================
DAILY_MISSION_TEMPLATE = """今日は {today} です。LLM Data Hub（{site_url}）の定期運用を開始してください。

## 前回の作業日
{last_work_line}

## 利用可能なWEBツール（すべて無料枠。factチェックはBrave→Firecrawlの順で）
- Brave Search（Web検索。factチェック第一選択）/ Firecrawl（URL指定でMarkdown取得。JSサイト対応。第二選択）
- GitHub MCP（公開リポジトリ読み取り専用）

## 今回の進め方
1. list_site_files で現在のサイト状態を軽く確認する（大きいHTMLは読まない）
2. 今回の作業テーマ（新規ページ or 既存ページ更新、1〜2件まで）の方向性だけ決める
   （/workspace は前回から持ち越しの永続ワークスペース。drafts/に未完了作業が残っていれば
   その続きを優先テーマにする。参照はエンジニアに任せてよい）
3. ask_claude_engineer に今回分をまとめて1回で依頼する。リサーチ・執筆・GPT税理士へのレビュー
   依頼・（必要なら）Gemini子育てママへの画像/UX依頼・クリティカルな指摘がなければ公開・軽微な
   指摘のsite_plan記録まで、Claudeエンジニアが現場責任者として自律的に行う。テーマ候補
   を伝えるだけでよく、細かい手順の指示や公開可否の判断をあなたが都度行う必要はない
4. Claudeエンジニアからの報告（公開したページ・GPT税理士の指摘件数・記録した課題）を確認する。
   よほど気になる点がない限り、あなた自身がask_gpt_tax_advisor/ask_gemini_motherを直接呼ぶ必要はない
   （通常はClaudeエンジニアに任せる）
5. 最後に write_daily_report で日報を書く（Claudeエンジニアの報告をもとにまとめる。
   okamoへの依頼事項があれば必ず書け。黙ってちゃ伝わらんぞ。依頼事項は俺の口調で書く
   こと。【確認】【意向確認】等の事務的な見出しはやめだ。身内に話すように書け）

## 注意（重要）
- 自分で考え込んだりWeb検索・factチェックを自分でやったりせず、Claudeエンジニアに一括委任すること。
  あなた自身の役割は「テーマ決定」と「最終確認・日報執筆」に絞る
- ask_claude_engineer は原則1回のみ呼ぶ（同じエージェントを何度も呼ぶと会話履歴が肥大化する。
  Claudeエンジニア内部でのGPT/Geminiとのやり取りは何度あっても問題ない）
- okamoのコメントで方針・優先度が決まったものは、その場でsite_planに写しておくこと
  （okamoのコメントは翌日以降は読めなくなる。site_planこそが恒久の作業リストだ）
- 作業を止められたら、速やかに日報を書いて終了すること
- サイト全体の一貫性（ナビゲーション・sitemap.xml）を保つこと
- GPT税理士・Gemini子育てママは門番ではなくアドバイザー。クリティカルな指摘（明確な誤情報・
  法的リスク・アダルト/犯罪関連）だけが公開停止の理由になる。軽微な指摘だけで作業や公開を
  止めず、site_planに課題として記録して先に進むこと（掲載情報の品質基準自体は下げない）
"""


def run_daily(dry_run: bool = False) -> None:
    from strands import Agent

    load_secrets_into_env()
    today = datetime.now(JST).strftime("%Y-%m-%d")
    collected: dict = {}

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

    # --- 2. 設定読み込み（自己改善の反映）---
    system_prompt = config_store.load_system_prompt()
    skills = config_store.load_skills()
    if skills:
        system_prompt += "\n\n## Skills\n" + "\n\n".join(
            f"### {s['name']}\n{s['content']}" for s in skills
        )
    site_plan = config_store.load_config("site_plan")
    if site_plan:
        system_prompt += f"\n\n## サイト運営計画（自分で更新可能）\n{site_plan}"

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
    # 今回確認した日を記録（次回起動時はここからの差分のみ取得すればよい状態にしておく）
    config_store.save_config("last_comment_check_date", today)

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

    delegation = create_delegation_tools(models, run_budget_jpy=budget_status["remaining_jpy"])

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
        file_read,
        akira_tools.update_akira_config,
        create_report_tool(collected),
        _create_brave_mcp(),
        *akira_extra_tools,
    ]
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

    mission = DAILY_MISSION_TEMPLATE.format(
        today=today, site_url=LLM_SITE_URL, last_work_line=last_work_line
    )
    if dry_run:
        mission += "\n\n【重要】今日はドライランです。公開・依頼は行わず、計画の提示だけしてください。"

    _debug_log_io("指示", "Akira本体", f"system_prompt:\n{system_prompt}\n\nmission:\n{mission}")
    try:
        result = akira(mission)
        _debug_log_io("応答", "Akira本体", str(result))
        # DeepSeek切替中は実モデル(deepseek-v4-pro)で記録して正しい単価(0.66/1.98)で見積もる。
        # Fableモードは従来どおり AKIRA_MODEL_ID (claude-fable-5) のまま。
        usage_model_id = DEEPSEEK_MODEL_ID if AKIRA_USE_DEEPSEEK else AKIRA_MODEL_ID
        cost = budget.collect_agent_usage(result, usage_model_id, purpose="akira:daily", agent=akira)
        logger.info("Akira本体 完了 (約%.1f円 / 本日合計約%.1f円)", cost, budget.get_run_spent_jpy())
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
    if not dry_run:
        akira_tools.flush_invalidations()
        publish_daily_report(collected, budget_status)
    logger.info("=== 本日の運用終了 ===")


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
    parser.add_argument("--test-wi", action="store_true",
                         help="GCP Workload Identityの疎通テストのみ実行（LLM呼び出し・予算ゲートなし）")
    args = parser.parse_args()
    if args.test_wi:
        run_wi_test()
        return
    run_daily(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

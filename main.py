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
    CLAUDE_MODEL_ID,
    DEBUG_TOOL_LOGGING,
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
    from strands.models.openai import OpenAIModel

    return {
        "akira": AnthropicModel(
            client_args={"api_key": os.getenv("CLAUDE_API_KEY")},
            model_id=AKIRA_MODEL_ID,
            max_tokens=16384,
        ),
        "claude": AnthropicModel(
            client_args={"api_key": os.getenv("CLAUDE_API_KEY")},
            model_id=CLAUDE_MODEL_ID,
            max_tokens=16384,
        ),
        "gpt": OpenAIModel(
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
    """Workload Identity用の環境変数セットを作る。"""
    import boto3

    config_file = akira_tools._configure_gcp_keyless_env()
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
        spent = budget.get_run_spent_jpy()
        if spent >= run_budget_jpy:
            return (
                f"【予算ガード】今回実行の費用が約{spent:.0f}円となり、月次予算の残額（{run_budget_jpy:.0f}円）に達しました。"
                "これ以上の作業依頼はできません。日報を書いて終了してください。"
            )
        _debug_log_io("指示", name, request)
        result = agent(request)
        _debug_log_io("応答", name, str(result))
        cost = budget.collect_agent_usage(result, model_id, purpose=f"delegate:{name}", agent=agent)
        logger.info("%s 完了 (約%.1f円 / 本日累計約%.1f円)", name, cost, budget.get_run_spent_jpy())
        return str(result)

    # GPT税理士・Gemini子育てママを先に作る（Claudeエンジニアが自分のツールとして使うため）。
    # これによりAkira(高額な$10/$50モデル)が毎回レビュー往復を仲介せずに済み、
    # 安価なClaudeエンジニア($2/$10導入価格)の会話内で完結させてコストを最適化する。

    # --- 共通WEBツール（全員に配布）---
    firecrawl = _create_firecrawl_mcp()
    brave = _create_brave_mcp()
    screenshot_tool = akira_tools.take_screenshot
    fetch_image = akira_tools.fetch_image_from_url
    from strands_tools import image_reader

    # Firecrawl/Braveの無料枠注意文（ツール説明に含める）
    _web_tool_note = (
        "※無料枠で運用中。APIクォータ超過エラーが出た場合は別のツール（Brave/Firecrawl相互）で補完すること。"
    )

    gpt_tools = [akira_tools.get_site_file, akira_tools.list_site_files, brave,
                 screenshot_tool, fetch_image, image_reader]
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
            request: 依頼内容。画像なら目的と公開先パス、チェックなら対象ページ
        """
        return _run(gemini_agent, GEMINI_MODEL_ID, "Gemini子育てママ", request)

    # Claudeエンジニアの追加ツール（オプショナル）
    claude_tools = [
        akira_tools.publish_file_to_site,
        akira_tools.get_site_file,
        akira_tools.list_site_files,
        akira_tools.update_akira_config,
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

    claude_agent = Agent(
        name="claude_engineer",
        model=models["claude"],
        system_prompt=prompts.CLAUDE_ENGINEER_PROMPT,
        tools=claude_tools,
    )


    @tool
    def ask_claude_engineer(request: str) -> str:
        """Claudeエンジニアに今回分の作業をまとめて依頼する（現場責任者としてリサーチ→執筆→
        GPT税理士レビュー→必要ならGemini画像/UX→公開までを自律的に一気通貫で行い、最後に結果を
        要約して返す）。Akira自身の高額な呼び出し回数を減らすため、原則1回のみ呼ぶこと。

        Args:
            request: 依頼内容。今日のテーマ候補・予算感・特筆事項を伝えれば十分（細かい手順の
                     指示は不要。リサーチ・執筆・レビュー依頼・公開判断はClaudeエンジニアに任せる）
        """
        return _run(claude_agent, CLAUDE_MODEL_ID, "Claudeエンジニア", request)

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
            requests_to_okamo: okamoさんへの依頼事項（なければ空文字）
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

## 予算状況
{budget_line}

## 利用可能なWEBツール（すべて無料枠。factチェックはBrave→Firecrawlの順で）
- Brave Search（Web検索。factチェック第一選択）/ Firecrawl（URL指定でMarkdown取得。JSサイト対応。第二選択）
- take_screenshot（ApiFlashで画面キャプチャ→ローカルパス返却。image_readerに渡して視認。UX/デザイン確認用。月100枚無料）
- image_reader（ローカル画像パス→LLM視認可能形式に変換。strands標準ツール）
- fetch_image_from_url（指定URLの画像を直接取得・LLM視認可能形式で返す）
- GitHub MCP（公開リポジトリ読み取り専用）

## 今回の進め方（コスト最適化: あなた自身の高額な呼び出し回数を最小限にする）
1. list_site_files で現在のサイト状態を軽く確認する（大きいHTMLは読まない）
2. 今回の作業テーマ（新規ページ or 既存ページ更新、1〜2件まで）の方向性だけ決める
3. ask_claude_engineer に今回分をまとめて1回で依頼する。リサーチ・執筆・GPT税理士へのレビュー
   依頼・（必要なら）Gemini子育てママへの画像/UX依頼・クリティカルな指摘がなければ公開・軽微な
   指摘のsite_plan記録まで、Claudeエンジニアが現場責任者として自律的に行う。テーマ候補と予算感
   を伝えるだけでよく、細かい手順の指示や公開可否の判断をあなたが都度行う必要はない
4. Claudeエンジニアからの報告（公開したページ・GPT税理士の指摘件数・記録した課題）を確認する。
   よほど気になる点がない限り、あなた自身がask_gpt_tax_advisor/ask_gemini_motherを直接呼ぶ必要はない
   （呼ぶと高額なあなたの会話履歴が伸びてコスト増になるため、通常はClaudeエンジニアに任せる）
5. 最後に write_daily_report で日報を書く（Claudeエンジニアの報告をもとにまとめる。
   okamoさんへの依頼事項があれば必ず記載）

## 注意（重要）
- あなた(Akira)の単価は $10/$50 per MTok と圧倒的に高額（Claudeエンジニアの5倍以上）。
  自分で考え込んだりWeb検索・factチェックを自分でやったりせず、Claudeエンジニアに一括委任すること。
  あなた自身の役割は「テーマ決定」と「最終確認・日報執筆」に絞る
- ask_claude_engineer は原則1回のみ呼ぶ（同じエージェントを何度も呼ぶと会話履歴が肥大化し
  費用が急増する。Claudeエンジニア内部でのGPT/Geminiとのやり取りは何度あってもあなたの費用には響かない）
- 月額予算のハードリミットを超えた場合（予算ガード発動）、速やかに日報を書いて終了すること。
  日報本文に「残予算○円/残り○日」のような詳細な費用規律メッセージを書く必要はない
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
    comments = report.get_recent_comments(days=7)
    if comments:
        system_prompt += "\n\n## okamoさんからの直近コメント（必ず考慮すること）\n" + "\n".join(
            f"- [{c['date']}] {c['text']}" for c in comments
        )

    # --- 3. Akiraエージェント構築 ---
    models = _create_models()
    akira_extra_tools = []
    if ENABLE_GA4_MCP:
        akira_extra_tools.append(_create_ga4_mcp())
    if ENABLE_BIGQUERY_MCP:
        akira_extra_tools.append(_create_bigquery_mcp())

    delegation = create_delegation_tools(models, run_budget_jpy=budget_status["remaining_jpy"])

    # Akira自身のツール（delegation + 直接使うツール）
    from strands_tools import image_reader
    akira_tools_list = [
        *delegation,
        akira_tools.get_site_file,
        akira_tools.list_site_files,
        akira_tools.get_budget_status,
        akira_tools.update_akira_config,
        create_report_tool(collected),
        _create_brave_mcp(),
        akira_tools.take_screenshot,
        akira_tools.fetch_image_from_url,
        image_reader,
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

    budget_line = f"月額予算 {budget_status['monthly_budget_jpy']:.0f}円（超過時は日報のみ書いて即終了）"
    mission = DAILY_MISSION_TEMPLATE.format(
        today=today, site_url=LLM_SITE_URL, budget_line=budget_line
    )
    if dry_run:
        mission += "\n\n【重要】今日はドライランです。公開・依頼は行わず、計画の提示だけしてください。"

    _debug_log_io("指示", "Akira本体", f"system_prompt:\n{system_prompt}\n\nmission:\n{mission}")
    result = akira(mission)
    _debug_log_io("応答", "Akira本体", str(result))
    cost = budget.collect_agent_usage(result, AKIRA_MODEL_ID, purpose="akira:daily", agent=akira)
    logger.info("Akira本体 完了 (約%.1f円 / 本日合計約%.1f円)", cost, budget.get_run_spent_jpy())

    # --- 4. 後処理 ---
    if not dry_run:
        akira_tools.flush_invalidations()
        publish_daily_report(collected, budget_status)
    logger.info("=== 本日の運用終了 ===")


def main():
    parser = argparse.ArgumentParser(description="Akira — LLM Data Hub 運営エージェント")
    parser.add_argument("--dry-run", action="store_true", help="公開せず計画のみ")
    args = parser.parse_args()
    run_daily(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

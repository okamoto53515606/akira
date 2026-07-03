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
        result = agent(request)
        cost = budget.collect_agent_usage(result, model_id, purpose=f"delegate:{name}", agent=agent)
        logger.info("%s 完了 (約%.1f円 / 本日累計約%.1f円)", name, cost, budget.get_run_spent_jpy())
        return str(result)

    claude_agent = Agent(
        name="claude_engineer",
        model=models["claude"],
        system_prompt=prompts.CLAUDE_ENGINEER_PROMPT,
        tools=[
            akira_tools.publish_file_to_site,
            akira_tools.get_site_file,
            akira_tools.list_site_files,
            _create_brave_mcp(),
        ],
    )
    gpt_agent = Agent(
        name="gpt_tax_advisor",
        model=models["gpt"],
        system_prompt=prompts.GPT_TAX_ADVISOR_PROMPT,
        tools=[akira_tools.get_site_file, akira_tools.list_site_files, _create_brave_mcp()],
    )
    gemini_agent = Agent(
        name="gemini_mother",
        model=models["gemini"],
        system_prompt=prompts.GEMINI_MOTHER_PROMPT,
        tools=[
            akira_tools.generate_and_publish_image,
            akira_tools.get_site_file,
            akira_tools.list_site_files,
        ],
    )

    @tool
    def ask_claude_engineer(request: str) -> str:
        """Claudeエンジニアに作業を依頼する（記事執筆・HTML/CSS/JS作成・サイトへの公開）。

        Args:
            request: 依頼内容。ページの目的・構成・必要な情報源・公開可否（税理士承認済みか）を具体的に伝えること
        """
        return _run(claude_agent, CLAUDE_MODEL_ID, "Claudeエンジニア", request)

    @tool
    def ask_gpt_tax_advisor(request: str) -> str:
        """GPT税理士にチェックを依頼する（factチェック・法務チェック・公開ゲート判定）。

        Args:
            request: チェック対象（サイト内パスや本文）と確認してほしい観点
        """
        return _run(gpt_agent, OPENAI_MODEL_ID, "GPT税理士", request)

    @tool
    def ask_gemini_mother(request: str) -> str:
        """Gemini子育てママに依頼する（画像生成・初心者目線のわかりやすさチェック）。

        Args:
            request: 依頼内容。画像なら目的と公開先パス、チェックなら対象ページ
        """
        return _run(gemini_agent, GEMINI_MODEL_ID, "Gemini子育てママ", request)

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
DAILY_MISSION_TEMPLATE = """今日は {today} です。LLM Data Hub（{site_url}）の日次運用を開始してください。

## 予算状況
{budget_line}

## 本日の進め方
1. list_site_files で現在のサイト状態を確認する
2. Web検索でLLM料金・新モデル等の最新情報をリサーチする
3. 本日の作業（新規ページ or 既存ページ更新、1〜2件まで）を決める
4. Claudeエンジニアに執筆・実装を依頼する（この時点では公開しない）
5. GPT税理士にfactチェックを依頼し、承認が出たらClaudeエンジニアに公開を指示する
6. 必要な場合のみGemini子育てママに画像やUXチェックを依頼する
7. 最後に write_daily_report で日報を書く（okamoさんへの依頼事項があれば必ず記載）

## 注意（費用規律・重要）
- ハードリミットは「月額9,300円」のみ。300円/日は配分の目安（価値の高い日に多めに使う判断はあなたに任す。
  ただし月前半で使い切ると月末まで更新停止になることを忘れずに）
- あなた(Akira)の単価は $10/$50 per MTok と高額。思考と指示は簡潔に、Web検索は合計4回まで
- 本日の新規/更新は原則1ページ（予算残に余裕があり価値が高い場合は2ページまで可）
- 3AIへの依頼は各担当につき原則1回で完結させる（依頼文に必要情報を全て含め、往復を減らす。
  同じエージェントを何度も呼ぶと会話履歴が肥大化し費用が急増する）
- ページ全文のget_site_fileは必要最小限に（大きいHTMLを何度も読まない）
- 予算ガード（月次残額枯渇）が発動したら速やかに日報を書いて終了する
- サイト全体の一貫性（ナビゲーション・sitemap.xml）を保つこと
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
    akira = Agent(
        name="akira",
        model=models["akira"],
        system_prompt=system_prompt,
        tools=[
            *delegation,
            akira_tools.get_site_file,
            akira_tools.list_site_files,
            akira_tools.get_budget_status,
            akira_tools.update_akira_config,
            create_report_tool(collected),
            _create_brave_mcp(),
            *akira_extra_tools,
        ],
    )

    budget_line = (
        f"当月費用 約{budget_status['month_cost_jpy']}円 / "
        f"予算{budget_status['monthly_budget_jpy']}円（残 約{budget_status['remaining_jpy']}円）"
    )
    mission = DAILY_MISSION_TEMPLATE.format(
        today=today, site_url=LLM_SITE_URL, budget_line=budget_line
    )
    if dry_run:
        mission += "\n\n【重要】今日はドライランです。公開・依頼は行わず、計画の提示だけしてください。"

    result = akira(mission)
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

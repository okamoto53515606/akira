# settings.py — Akira 共通設定・シークレット読み込み
#
# 命名規約: AWSリソースは akira- プレフィックス（channelとは疎結合）

import json
import os
from datetime import timedelta, timezone

import boto3

JST = timezone(timedelta(hours=9))
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# --- AWSリソース ---
LLM_SITE_BUCKET = os.getenv("LLM_SITE_BUCKET", "akira-llm-site")
REPORTS_BUCKET = os.getenv("REPORTS_BUCKET", "akira-reports-site")
LLM_DIST_ID = os.getenv("LLM_DIST_ID", "")
REPORTS_DIST_ID = os.getenv("REPORTS_DIST_ID", "")
USAGE_TABLE = os.getenv("USAGE_TABLE", "akira-usage")
REPORTS_TABLE = os.getenv("REPORTS_TABLE", "akira-reports")
CONFIG_TABLE = os.getenv("CONFIG_TABLE", "akira-config")
SECRET_ARN = os.getenv("SECRET_ARN", "")

# --- サイト ---
LLM_SITE_URL = "https://llm.okamomedia.tokyo"
REPORTS_SITE_URL = "https://akira.okamomedia.tokyo"

# --- 予算（LLM費用のみ・AWS費用は含まない）---
MONTHLY_BUDGET_JPY = float(os.getenv("MONTHLY_BUDGET_JPY", "9300"))
DAILY_BUDGET_JPY = float(os.getenv("DAILY_BUDGET_JPY", "300"))
USD_JPY = float(os.getenv("USD_JPY", "160"))

# モデル料金（USD / 100万トークン: (入力, 出力)）
# 不明モデルは保守的に高め(DEFAULT)で見積もり、上振れを防ぐ
# 2026-07-02 検証: claude-fable-5 は $10/$50（公式docs確認済み。旧値 3/15 は誤り）
MODEL_PRICING_USD: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-5": (2.0, 10.0),  # 導入価格。2026-09-01以降はbudget.pyが$3/$15で自動計算
    "gpt-5.6-terra": (2.5, 15.0),
    "gemini-3.8-flash": (0.75, 3.75), # 導入価格。2027-01-01以降は2倍
    "gemini-3.1-flash-image": (0.5, 3.0),
    "deepseek-v4-pro": (0.66, 1.98),  # DeepSeek V4 Pro OFF-PEAK（PEAK $1.32/$3.96）
}
DEFAULT_PRICING_USD = (10.0, 50.0)
IMAGE_PRICE_USD = float(os.getenv("IMAGE_PRICE_USD", "0.05"))  # 生成画像1枚あたり

# --- モデルID ---
AKIRA_MODEL_ID = os.getenv("AKIRA_MODEL_ID", "claude-fable-5")
CLAUDE_MODEL_ID = os.getenv("CLAUDE_MODEL_ID", "claude-sonnet-5")
OPENAI_MODEL_ID = os.getenv("OPEN_AI_MODEL_ID", "gpt-5.6-terra")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-3.8-flash")
IMAGE_MODEL_ID = os.getenv("BANNER_MODEL", "gemini-3.1-flash-image")
DEEPSEEK_MODEL_ID = os.getenv("DEEPSEEK_MODEL_ID", "deepseek-v4-pro")

# Akira本体をDeepSeek（Anthropic互換API）に切替えるか（テスト運用用）。trueで切替、false/falsyで従来のFable 5
AKIRA_USE_DEEPSEEK = os.getenv("AKIRA_USE_DEEPSEEK", "false").lower() == "true"
# DeepSeek の Anthropic 互換エンドポイント（https://api-docs.deepseek.com/guides/anthropic_api）
DEEPSEEK_ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"
# DeepSeek V4 Pro の1レスポンス出力上限（公式MAX OUTPUTは384K。巨大file_write対策で128K）
DEEPSEEK_MAX_TOKENS = int(os.getenv("DEEPSEEK_MAX_TOKENS", "128000"))
# 日次タスクの壁時計上限（秒）。超過したら日報を書いて終了する
RUN_DEADLINE_SECONDS = int(os.getenv("RUN_DEADLINE_SECONDS", "3600"))

# --- 機能フラグ ---
ENABLE_GA4_MCP = os.getenv("ENABLE_GA4_MCP", "true").lower() == "true"
ENABLE_BIGQUERY_MCP = os.getenv("ENABLE_BIGQUERY_MCP", "true").lower() == "true"
GOOGLE_BIGQUERY_PROJECT = os.getenv("GOOGLE_BIGQUERY_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))

# LLMのツール/MCP呼び出しの詳細ログをCloudWatchへ出力するか（異常挙動監視のため一時的にtrue）。
# 不要になったらタスク定義の環境変数を "false" にして再デプロイすれば止められる
DEBUG_TOOL_LOGGING = os.getenv("DEBUG_TOOL_LOGGING", "true").lower() == "true"

# --- APIキー（環境変数から直接）---
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
APIFLASH_ACCESS_KEY = os.getenv("APIFLASH_ACCESS_KEY", "")


def load_secrets_into_env() -> None:
    """Secrets ManagerのAPIキー類を環境変数へ展開する（未設定のもののみ）。

    ローカルでは .env が先に読み込まれている前提。Fargateではここで取得する。
    """
    required = ["CLAUDE_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "BRAVE_API_KEY",
                "GITHUB_PAT_READ_ONLY_PUBLIC", "DEEPSEEK_API_KEY"]
    if all(os.getenv(k) for k in required):
        return
    if not SECRET_ARN:
        raise RuntimeError(
            "SECRET_ARN が設定されていません。環境変数 SECRET_ARN に "
            "Secrets Manager の ARN を指定してください。"
        )
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    secret = json.loads(client.get_secret_value(SecretId=SECRET_ARN)["SecretString"])
    for key, value in secret.items():
        os.environ.setdefault(key, value)

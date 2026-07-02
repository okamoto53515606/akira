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
LLM_DIST_ID = os.getenv("LLM_DIST_ID", "E1V1Y3U21T20G")
REPORTS_DIST_ID = os.getenv("REPORTS_DIST_ID", "E1PETXZ81SSGJS")
USAGE_TABLE = os.getenv("USAGE_TABLE", "akira-usage")
REPORTS_TABLE = os.getenv("REPORTS_TABLE", "akira-reports")
CONFIG_TABLE = os.getenv("CONFIG_TABLE", "akira-config")
SECRET_ARN = os.getenv(
    "SECRET_ARN",
    "arn:aws:secretsmanager:us-east-1:210387976006:secret:okamo-channel/secrets-3GPwNw",
)

# --- サイト ---
LLM_SITE_URL = "https://llm.okamomedia.tokyo"
REPORTS_SITE_URL = "https://akira.okamomedia.tokyo"

# --- 予算（LLM費用のみ・AWS費用は含まない）---
MONTHLY_BUDGET_JPY = float(os.getenv("MONTHLY_BUDGET_JPY", "9300"))
DAILY_BUDGET_JPY = float(os.getenv("DAILY_BUDGET_JPY", "300"))
USD_JPY = float(os.getenv("USD_JPY", "155"))

# モデル料金（USD / 100万トークン: (入力, 出力)）
# 不明モデルは保守的に高め(DEFAULT)で見積もり、上振れを防ぐ
# 2026-07-02 検証: claude-fable-5 は $10/$50（公式docs確認済み。旧値 3/15 は誤り）
MODEL_PRICING_USD: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-5": (2.0, 10.0),  # 導入価格。2026-09-01以降はbudget.pyが$3/$15で自動計算
    "gpt-5.4": (1.25, 10.0),
    "gemini-3.5-flash": (0.30, 2.50),
    "gemini-3.1-flash-image": (0.30, 2.50),
}
DEFAULT_PRICING_USD = (10.0, 50.0)
IMAGE_PRICE_USD = float(os.getenv("IMAGE_PRICE_USD", "0.05"))  # 生成画像1枚あたり

# --- モデルID ---
AKIRA_MODEL_ID = os.getenv("AKIRA_MODEL_ID", "claude-fable-5")
CLAUDE_MODEL_ID = os.getenv("CLAUDE_MODEL_ID", "claude-sonnet-4-6")
OPENAI_MODEL_ID = os.getenv("OPEN_AI_MODEL_ID", "gpt-5.4")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-3.5-flash")
IMAGE_MODEL_ID = os.getenv("BANNER_MODEL", "gemini-3.1-flash-image")

# --- 機能フラグ ---
ENABLE_GA4_MCP = os.getenv("ENABLE_GA4_MCP", "false").lower() == "true"
ENABLE_BIGQUERY_MCP = os.getenv("ENABLE_BIGQUERY_MCP", "false").lower() == "true"
GOOGLE_BIGQUERY_PROJECT = os.getenv("GOOGLE_BIGQUERY_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))


def load_secrets_into_env() -> None:
    """Secrets ManagerのAPIキー類を環境変数へ展開する（未設定のもののみ）。

    ローカルでは .env が先に読み込まれている前提。Fargateではここで取得する。
    """
    required = ["CLAUDE_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "BRAVE_API_KEY"]
    if all(os.getenv(k) for k in required):
        return
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    secret = json.loads(client.get_secret_value(SecretId=SECRET_ARN)["SecretString"])
    for key, value in secret.items():
        os.environ.setdefault(key, value)

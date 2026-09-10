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
    # 2026-09-01以降も導入価格を継続。budget.pyでの期間別上書きは行わない。
    "claude-sonnet-5": (2.0, 10.0),
    # 2026-09-05確認の現行料金。新しいモデルIDを料金テーブルに追加。
    "gpt-5.6-luna": (0.2, 1.2),
    "gpt-5.6-terra": (2.0, 12.0),
    # 2026-09-05確認の現行料金。新しいモデルIDを料金テーブルに追加。
    "gemini-3.5-flash-lite": (0.3, 2.5),
    "gemini-3.8-flash": (0.75, 3.75), # 導入価格。2027-01-01以降は2倍
    "gemini-3.1-flash-image": (0.5, 3.0),
    # 2026-09-10: DeepSeek V4.1 Flash に統一（モデル名は deepseek-flash）。
    # 旧名 deepseek-v4-pro / deepseek-v4-flash-vision-exp は退役済み（公式: 旧名は依然受理されるが
    # V4.1 Flash が応答し Flash 価格で課金。V4 Pro は 2026-09-14 以降 V4.1 Flash へルーティング）→ 削除
    # 単価は公式 OFF-PEAK（PEAK $0.30/$1.20）。1Mコンテキスト / 最大出力384K / Vision対応
    "deepseek-flash": (0.15, 0.6),
}
DEFAULT_PRICING_USD = (10.0, 50.0)
IMAGE_PRICE_USD = float(os.getenv("IMAGE_PRICE_USD", "0.05"))  # 生成画像1枚あたり

# --- モデルID ---
AKIRA_MODEL_ID = os.getenv("AKIRA_MODEL_ID", "claude-fable-5")
CLAUDE_MODEL_ID = os.getenv("CLAUDE_MODEL_ID", "claude-sonnet-5")
OPENAI_MODEL_ID = os.getenv("OPEN_AI_MODEL_ID", "gpt-5.6-terra")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-3.8-flash")
IMAGE_MODEL_ID = os.getenv("BANNER_MODEL", "gemini-3.1-flash-image")
DEEPSEEK_MODEL_ID = os.getenv("DEEPSEEK_MODEL_ID", "deepseek-flash")

# Akira本体をDeepSeek（Anthropic互換API）に切替えるか（テスト運用用）。trueで切替、false/falsyで従来のFable 5
AKIRA_USE_DEEPSEEK = os.getenv("AKIRA_USE_DEEPSEEK", "false").lower() == "true"
# DeepSeek の Anthropic 互換エンドポイント（https://api-docs.deepseek.com/guides/anthropic_api）
DEEPSEEK_ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"
# DeepSeek の1レスポンス出力上限。公式MAX OUTPUTは384Kだが、APIは
# 「messages + max_tokens」をコンテキスト1Mに対して予約する。
# 2つの失敗モードの間を取って128K（3e0d7ef と同じ値）:
# - 低すぎ(16K) → 巨大file_writeが途中で切れ MaxTokensReached で回復不能
#   （8/13・8/27に発生。128Kで解消した実績あり）
# - 高すぎ(384K) → 履歴66.5万の時点で 665132+384000=1049132 > 1048576 となり400
#   （2026-09-09に発生）
# 128Kなら最悪時の履歴66.5万+128K=79.3万 < 1M に収まり、出力余裕も十分。
DEEPSEEK_MAX_TOKENS = int(os.getenv("DEEPSEEK_MAX_TOKENS", "128000"))
# DeepSeek API の HTTP read タイムアウト（秒）。anthropic SDK の既定は 600s。
# thinking 付きの長めの生成でも切断されないよう余裕を持たせる。
# RUN_DEADLINE_SECONDS（日次タスクの壁時計上限=3600s）がそれ以上長くても意味がないため同じ値
DEEPSEEK_READ_TIMEOUT = int(os.getenv("DEEPSEEK_READ_TIMEOUT", "3600"))
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

# --- 永続ワークスペース（Fargateの使い捨てFSをS3と同期して翌日に持ち越す）---
# タスク開始時に S3→ローカルへ全件復元、終了時（例外/タイムアウト含む）にローカル→S3へ保存。
# 自作ツール(tools/)・再利用パーツ(parts/)・一次情報キャッシュ(cache/)・持ち越し原稿(drafts/)用。
# バケットは公開サイト用バケットと別の「非公開」バケットを使うこと（機密・作業ファイルを
# CloudFront経由で公開しないため）
WORKSPACE_BUCKET = os.getenv("WORKSPACE_BUCKET", "akira-workspace")
WORKSPACE_LOCAL_DIR = os.getenv("WORKSPACE_LOCAL_DIR", "/workspace")
WORKSPACE_MAX_FILE_BYTES = int(os.getenv("WORKSPACE_MAX_FILE_BYTES", str(10 * 1024 * 1024)))
WORKSPACE_MAX_TOTAL_BYTES = int(os.getenv("WORKSPACE_MAX_TOTAL_BYTES", str(100 * 1024 * 1024)))
# /workspace/tools/*.py から自動登録する自作ツールの上限
WORKSPACE_TOOLS_MAX = int(os.getenv("WORKSPACE_TOOLS_MAX", "20"))


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

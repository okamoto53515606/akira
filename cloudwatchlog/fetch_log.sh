#!/usr/bin/env bash
# CloudWatch Logs を JST の指定日で取得し、cloudwatchlog/<日付>.txt に保存する
#
# Usage:
#   ./fetch_log.sh YYYY-MM-DD [log-group-name] [region]
#
# Example:
#   ./fetch_log.sh 2026-07-02
#   ./fetch_log.sh 2026-07-02 /ecs/akira us-east-1

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 YYYY-MM-DD [log-group-name] [region]" >&2
  exit 1
fi

DATE="$1"
LOG_GROUP="${2:-/ecs/akira}"
REGION="${3:-us-east-1}"

if ! date -d "$DATE" >/dev/null 2>&1; then
  echo "Invalid date: $DATE (expected YYYY-MM-DD)" >&2
  exit 1
fi

# JST(+9:00) の 00:00〜翌日00:00 を UTC epoch ミリ秒に変換
START_MS=$(( $(date -d "$DATE 00:00:00 +0900" +%s) * 1000 ))
END_MS=$(( $(date -d "$DATE 00:00:00 +0900 +1 day" +%s) * 1000 ))

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_FILE="$SCRIPT_DIR/${DATE}.txt"
TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

aws logs filter-log-events \
  --log-group-name "$LOG_GROUP" \
  --region "$REGION" \
  --start-time "$START_MS" \
  --end-time "$END_MS" \
  --output json > "$TMP_FILE"

# ページネーションで複数JSONが連結されていても jq -s (slurp) でまとめて処理する
jq -s -r '
  [.[].events[]] | sort_by(.timestamp)[] |
  "\((.timestamp/1000 + 32400) | gmtime | strftime("%Y-%m-%d %H:%M:%S")) JST [\(.logStreamName)] \(.message)"
' "$TMP_FILE" > "$OUT_FILE"

echo "Saved $(wc -l < "$OUT_FILE") lines to $OUT_FILE"

#!/usr/bin/env bash
# s3-snapshot を最新のS3の内容に更新する（手元で実行する用）
#
#   bash s3-snapshot/refresh.sh
#
# site/      : 公開サイトの全ファイル（S3に合わせて削除も同期）
# workspace/ : AIの作業場。cache/ は外部サイト本文のコピーを含むため意図的に除外
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

aws --region "$REGION" s3 sync s3://akira-llm-site/ "$DIR/site/" --delete --quiet
aws --region "$REGION" s3 sync s3://akira-workspace/ "$DIR/workspace/" --exclude "cache/*" --quiet

echo "更新しました: $(date -Iseconds)"
echo "  site/      $(find "$DIR/site" -type f | wc -l) files / $(du -sh "$DIR/site" | cut -f1)"
echo "  workspace/ $(find "$DIR/workspace" -type f | wc -l) files / $(du -sh "$DIR/workspace" | cut -f1)"
echo "次の手順: git add s3-snapshot && git commit && git push"

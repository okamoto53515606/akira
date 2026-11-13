# 2026-11-07 GPT-6 Cyber 追加便／アンカー検証メモ

- 取得・実測日時: 2026-11-07 (JST) / UTC 2026-11-06 20:2x
- 背景: Akira のライブ directQuote が /en/timeline/ で空振り（S3 は更新済み・verify_publish 一致）
  → 原因は CloudFront エッジの旧版配信。purge → 150秒待ち → verify_publish OK → 再フェッチで解消。
- 再現手順（信頼できる順）: site_upload → purge_cdn → 150秒 sleep → verify_publish → firecrawl で2〜3回ライブ実測
- 局所修正: 日英 timeline の GPT-6 Cyber 記事が「2025年」区切りの直後にあった（2025扱い）→ 2026年ブロック末尾へ移動。article 49件・id 重複0。
- EN description 凍結違反: `Updated Nov 7, 2026` → `Updated Nov 3, 2026.` に復元（backup-20261103-timeline-en-after.html の逐語）。JA は変更なし。
- check_dates: NG 1/82（/en/timeline/ の description 日付 11-03 vs 宣言 11-07）= 凍結のための意図的不一致。11-17 判定まで許容。
- 内部アンカースキャン: 74件 全解決・ghost 0。スクリプトは /workspace/parts/check_anchors.py（3回目で tools/ 化を検討）。
- バックアップ: notes/backup-20261107-timeline-{ja,en}-pre.html

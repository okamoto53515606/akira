# 2026-09-25 Kimi K3 / Amazon Bedrock データ取扱い 追記（一次情報メモ）

## 前提の訂正（重要）
- okamo が引用してきた3点は **Kimi K3 の Bedrock モデルカードには書かれていない**。
  model card（ja_jp / en_us）を maxAge:0 で実取得して全文確認 → データ取扱いセクションは存在しない
  （ja_jp 版は「このページはお客様の言語に翻訳されていません」＝英語本文）。
  model card にあるのは Model Details / Capabilities / Pricing / Programmatic Access / Service Tiers /
  Regional Availability / Quotas / Usage Considerations / Sample Code のみ。
- よって一次情報は **Bedrock の共通ドキュメント群**。当サイトでは「Bedrock共通仕様」と明示して書いた。
- 「推論時にデータを保持しない設定は常時有効」は不正確。正しくは「ZDR が既定のデータセキュリティモデル。
  Kimi K3 は保持必須モデルの例外リストに含まれない。保証が必要なら data_retention_mode: none を明示」。

## 逐語（出典URL / 取得 2026-09-25）
- https://docs.aws.amazon.com/bedrock/latest/userguide/abuse-detection.html
  「Amazon Bedrock uses a zero operator access (ZOA) data security model. This means no operators of the
   service can access model input or output. Also, Amazon Bedrock uses a zero data retention (ZDR) data
   security model. This means that by default, Amazon Bedrock does not store model inputs or outputs.」
  → 保持が必要な例外: OpenAI GPT-6 Astra / GPT-5.4 / 5.5 / 5.6 Sol・Terra・Luna、Daybreak Red: GPT-5.6 Cyber、
    Daybreak Blue: GPT-5.6 Sol、Anthropic Claude Fable 5 / Fable 5.1。**Kimi K3 は含まれない**。
- https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html
  「Model providers don't have any access to those accounts. ... Because the model providers don't have
   access to those accounts, they don't have access to Amazon Bedrock logs or to customer prompts and
   completions.」（Model Deployment Account の説明）
- https://aws.amazon.com/bedrock/faqs/
  「Are user inputs and model outputs made available to third-party model providers? No. Users' inputs and
   model outputs are not shared with any model providers.」
  「Will AWS and third-party model providers use customer inputs to or outputs from Amazon Bedrock to train
   Amazon Nova, Amazon Titan or any third-party models? No, ... will not use any inputs to or outputs from
   Amazon Bedrock to train ...」
  「Any customer content processed by Amazon Bedrock is encrypted and stored at rest in the AWS Region where
   you are using Amazon Bedrock.」
- https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html
  モード: none / default / aws_review / provider_data_share（レガシー）。none = 「No request or response data
  is written to durable storage by AWS or shared with the model provider.」／設定はアカウント・プロジェクト単位（リージョンごと）。
- モデルカード: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-moonshot-ai-kimi-k3.html
  （料金は Global CRIS $3.00/$15.00, cache read $0.30, cache write 30min $3.75。**当サイトは直販標準料金を採用**＝課題23の方針どおり混ぜない）

## キャッシュ（生スナップショット）
- /workspace/cache/aws_en_data-protection.html, aws_ja_data-protection.html, aws_en_security.html
- /workspace/cache/aws_en_data-retention.html, aws_ja_data-retention.html
- /workspace/cache/aws_en_abuse-detection.html, aws_faq.html

## 反映先
- /china-ai/index.html（Kimiカード内 note-bar 1段落）・/en/china-ai/index.html（同）
- updated-bar の「情報取得日」文言と更新履歴の 2026-09-25 行に1行追記。三点日付は元から 2026-09-25 で整合。
- バックアップ: /workspace/notes/backup_20260925/

# 2026-11-10 OG配線修正・重複JSON-LD削除（プロンプトキャッシュ料金比較の2ページ）

## 症状
`/prompt-cache-pricing/` と `/en/prompt-cache-pricing/` の og:image / twitter:image が
実在しないパス（`assets/og-prompt-cache-pricing.png` 等）を指していた。SNS共有時に画像が出ない。

## 実際のS3キー
- assets/og/ja-prompt-cache-pricing.png （実体 1424x752 JPEG、Content-Type: image/jpeg、826,721 bytes）
- assets/og/en-prompt-cache-pricing.png （実体 1424x752 JPEG、Content-Type: image/jpeg、775,345 bytes）

※ 既存22枚のOG画像はすべて 1200x630 PNG（Pillow生成）。この2枚だけ生成元が違う（generate_and_publish_image）。

## 実施した修正（両ページ）
1. og:image / twitter:image → 実在キーに修正（EN側は当初 `...-en.png` と誤記していたのを実キーへ）
2. og:image:width/height → 1200/630（誤）から実寸 1424/752 へ
3. og:image:alt / twitter:image:alt → サイト共通文言からページ固有の説明へ
4. EN title / og:title: 104字 → 61字「Prompt Caching Pricing Side-by-Side (Nov 2026) — LLM Data Hub」
5. JA の <script type="application/ld+json"> が同一内容で2重（GPT税理士の指摘）→ 1つ削除。サイト全体も重複0を確認。

## 検証
- ローカル og:image/twitter:image 全25URL: ライブ200（Content-Type 正常）
- check_site_pages: ERROR 0 / WARN 18（og-wiring の未使用アセットWARNが消えた）
- check_dates: NG 1（/en/timeline/ description 日付 2026-11-03 vs 宣言 2026-11-07、既存・未修正）
- ライブ2回フェッチで head 全項目一致、JSON-LD 1本を確認
- verify_publish: 123/123 OK

## ツール変更（/workspace/tools/check_site_pages.py、翌朝反映）
- EXPECTED_OG_IMAGES に prompt-cache-pricing 2ページを追加
- 画素サイズ検証を「1200x630 固定」から「実ファイルの画素と比較（PIL）」へ変更
- バックアップ: /workspace/notes/backup-20261110/check_site_pages.py.bak

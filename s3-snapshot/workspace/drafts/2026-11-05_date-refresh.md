# 2026-11-05 古いページの日付整合リフレッシュ（追補）

## 実施内容
対象: 個別モデルページ 6モデル × 日英 = 12ページ。本文の料金表・文章は不変、
**JSON-LD dateModified / 本文「最終更新日（Last updated）」/ sitemap lastmod** を 2026-11-05 に揃えた。
（meta description / og:description に「更新日」を持つページは今回の対象には無し。
deepseek-v4-pro の desc にある 2026-09-14 は「V4 Pro 提供継続の起点日」という事実記述なので触らない。）

| slug | 旧更新日 | 本日の一次情報 | 判定 |
|---|---|---|---|
| qwen-3-8-flash (ja/en) | 2026-09-13 | Alibaba Model Studio: $0.15 in / $0.47 out（`cache/20261105-verification.md`） | 変動なし → 更新 |
| grok-4-6 (ja/en) | 2026-09-23 | docs.x.ai: $2.00 / $0.50 cached / $6.00 out | 変動なし → 更新 |
| grok-4-7 (ja/en) | 2026-09-23 | 同上 | 変動なし → 更新 |
| deepseek-v4-pro (ja/en) | 2026-09-13 | api-docs.deepseek.com/quick_start/pricing: deepseek-v4-pro 行あり。cache hit $0.022/$0.044、cache miss $0.66/$1.32、out $1.98/$3.96（off-peak/peak）。モデル版 DeepSeek-V4-Pro-0813 | 変動なし → 更新（取得日も 11-05 に） |
| claude-fable-5-1 (ja/en) | 2026-09-01 | platform.claude.com/docs/en/about-claude/pricing: Fable 5.1 $5 in / $25 out、cache hit 2.5%（$0.25） | 変動なし → 更新 |
| claude-mythos-5-1 (ja/en) | 2026-09-01 | 同上（Mythos 5.1 $5/$25） | 変動なし → 更新 |
| gemini-3-7-flash (ja/en) | 2026-08-19 | ai.google.dev/gemini-api/docs/pricing に **3.7 Flash のセクションも `gemini-3.7` の文字列も存在しない**（掲載: 4 Argon / 3.8 Flash / 3.6 Flash / 3.5 Flash-Lite / Omni Flash / 3.8 Live / 3.1 Flash-Lite / 3.1 Pro Preview / 各TTS） | **未確認 → 日付据え置き**（ルール47） |

## キャッシュ
- `/workspace/cache/raw-2026-11-05b/{google,deepseek,anthropic}.{html,txt}`（取得 2026-11-05 JST）
- 元HTMLのバックアップ: `/workspace/notes/backup-20261105-stale/`

## 検証
- check_site_pages: ERROR 0 / WARN 18（EN title 過長の既存WARNのみ）
- check_dates: NG 0 / 80
- verify_publish: 115 OK / 0 NG
- ライブ実測: 12URL＋sitemap を各3回フェッチし全回同一（dateModified / 最終更新日 / sitemap lastmod = 2026-11-05）

## 残作業（次回）
1. `/gemini-3-7-flash/` の掲載状態の裏取り（退役・legacy 移行の可能性）。モデル一覧・ライフサイクル情報で確認してから本文と日付を更新。
2. 月版ラベル（china-ai 4 / mai 3 / multimodal 1）は **2026年10月版のまま**。一次情報を再取得していないため月版を進めていない。EN側に月版ラベルは無し。取得できた範囲で当月版へ。

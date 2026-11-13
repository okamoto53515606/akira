# 2026-10-17 Gemini 4 Argon（GA）反映 — 作業記録

## 一次情報（本日取得）
- /workspace/cache/gemini-4-argon-2026-10-17.md（逐語スナップショット。出典4本: /docs/models、/docs/models/gemini-4-argon、
  /docs/pricing、/docs/changelog。Firecrawl 実フェッチ＝cacheState hit / cachedAt 2026-10-16T23:12Z = 10-17 JST）
- 古い /workspace/cache/gemini-4-argon-2026-10-03.md（提供前段階の記録）は先頭に SUPERSEDED 警告を付けて無効化。

## 確認した数値（逐語）
- 入力 $2.00 / 出力 $10.00（思考トークン含む）/ コンテキストキャッシュ $0.10（USD・1Mトークン）
  … いずれも **〜2026-11-30 の導入価格**、**12/1 から $4.00 / $20.00 / $0.20**
- Free tier: **Not available**。キャッシュは **Implicit caching only（明示キャッシュ非対応）**
- モデルコード `gemini-4-argon` / Stable（＝GA）/ コンテキスト 1,048,576（入出力統合上限）
- 最大出力 65,536（同期）、long decode で最大 1,048,576 / 公式モデルページ「Latest update: October 2026」
- 位置づけ: flagship reasoning model（複雑なソフトウェアエンジニアリング、数学・科学、マルチステップエージェント、long decode）
- リリース「日」は公式に明記なし → 年表は「2026-10」表記（誤った日付を作らない）

## 公開した変更（日英両方・81ファイル一括 → purge 済み）
- /timeline/ ・/en/timeline/: 10月の GA 項目を追加（id=gemini-4-argon）。既存の 9/30「発表・先行提供」項目は
  **id を gemini-4-argon-announced に改名**（重複ID解消）し、バッジを「GA済」に変更＋「2026年10月にGA／料金比較参照」を追記。
  updated-bar・meta description・og:description も更新（dateModified 2026-10-17）。
- /pricing/ ・/en/pricing/: Google セクション先頭に Gemini 4 Argon 行（導入価格→12/1改定・暗黙キャッシュのみ・無料枠なし）、
  note-bar 追加、Google セクション注記と出典に gemini-4-argon を追記。
- /data/models.json（計算機データ）: Gemini 3.8 Flash の直前に input 2.00 / output 10.00 を追加（note に導入価格を明記）。
- /workspace/data/price-sot.json: `gemini-4-argon` エントリ追加（cache_miss_input 2.0 / cache_hit_input 0.1 / output 10.0、
  12/1〜のキー、batch・priority・cache_write は「記載なし」= null、pages_planned に個別ページ案）。

## 検証
- check_dates: NG 0 / 76URL。verify_price_consistency: 更新漏れなし。
- verify_publish: 91ファイル中 data/models.json のみ NG（purge 後再確認）。
- GPT税理士: 1回目クリティカル1（裏取り不能＝10-03の古いcacheのみ）→ 本日付スナップショット保存で対応。
  2回目クリティカル1（**年表に Gemini 4 の項目が2件ある**＝重複を指摘）→ id改名＋「GA済」追記＋相互参照で解消。

## 残作業（次回）
1. **Gemini 4 Argon 個別ページ化の可否は okamo 判断**（GA 済みなので方針「GA したら検討」に該当）。SOT に pages_planned あり。
2. **Gemini 3.8 Flash のキャッシュ“ストレージ”単価**（$0.50/1Mトークン/時〜12/31 → $1.00）が当サイト未掲載 → 詳細ページ更新時に追記。
3. okamo 10-13 指定の favicon.svg / メインビジュアル / llms.txt は依然未達（site_plan の「次回の最優先1」）。

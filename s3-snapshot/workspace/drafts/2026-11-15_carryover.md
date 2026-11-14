# 2026-11-15（2回目）持ち越し

## 完了（公開済み）
- `/speech-api-pricing/`・`/en/speech-api-pricing/`: 比較軸1本化（TTS=1分 / STT=1時間）。従属単位（1,000字あたり・換算前単位）は `<details>` の内訳表へ機械移送。本文範囲説明・meta description 不変、日付は構造変更扱いで据え置き（2026-11-15 のまま）。
- `assets/og/ja-speech-api-pricing.png`・`en-...png`: 1200×630 を Pillow で再生成、見出し 76→92px（+21%）。Gemini視認OK。
- 用語集8ページ（gpt-6-astra-benchmarks / harness / one-million-context / prompt-cache の ja・en）: 出典を1行リンク行に圧縮。落ちる注記のうち事実は行末に復元済み。
- `sitemap.xml`: `/mai/` lastmod 2026-10-17 → 2026-11-15（三点整合）。

## 次回やる（サイト計画 課題131・134・135）
1. **課題131（EN図）**: ja の図は画像内に和文が焼かれている → EN に流用不可（課題130違反）。EN 用画像を新規生成するか HTML/CSS 図に置換するか、方針決定が必要。
2. **課題134（長文3割減）**: 実測では文単位の完全重複 0〜9.6%、ブロック単位の完全重複 0件。残りは事実のため3割減＝情報削除。「重複除去＋折りたたみ／ページ分割」への目標置換を提案（要判断）。
3. **課題135（出典圧縮の対応表）**: 8ページの「削った地の文」と「本文に残る該当記述」の対応表を `notes/` に作る。現時点のスポットチェックでは responses API / セーフガード / 2025年7月 / 逐語 / 提携 は本文か注記に残存、Gemini 2027改定は注記に復元済み。
4. **課題132**: price-sot.json last_verified 2026-10-29（16日経過）。年表の未収録8件を入れる。
5. **課題108**: `check_site_pages` の og-wiring WARN は誤検知（`/assets/og/` 前置き未考慮）。チェッカー側を直す。

## 今日のゲート実測
check_site_pages ERROR 0 / WARN 23 ・ check_dates NG 0/92 ・ facts_consistency ERROR 0 / WARN 3 ・ verify_price_consistency 更新漏れなし ・ 公開契約 違反0 ・ verify_publish 141一致（初回 sitemap のみ NG → purge）。
※ `check_page_shape` はツールとして存在しない（Unknown tool）。5本ゲートの表記は要修正。

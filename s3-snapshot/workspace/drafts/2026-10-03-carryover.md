# 持ち越し 2026-10-03 → 翌日

## 今日やったこと（結論）
- 用語説明 第10弾 no-training（学ばせない）を **日英公開まで完了**。
  - 公開: `/glossary/no-training/index.html`, `/en/glossary/no-training/index.html`,
    `/glossary/index.html`, `/en/glossary/index.html`, `/index.html`, `/en/index.html`, `/sitemap.xml`（7ファイル）
  - purge_cdn（新規は `index.html` を明示）→ **verify_publish 80/80 OK**
  - check_site_pages ERROR 0 / WARN 19、check_dates NG 0（70URL）
  - GPT税理士: クリティカル0・軽微2（→ 課題37）
  - Gemini初心者目線: 2点（→ 課題38）。※「オプトアウト初出補足」「横スクロールサイン」は既に対応済みと機械確認。
- **重要発見**: 朝の記録が「第10弾は公開済み／Argon追記済み／月版更新済み」と書いていたが、
  実際は 第10弾＝ローカル原稿のみ（live は ERR:403、sitemap未掲載）、Argon＝記載0件、月版＝11ファイル残存。
  → 課題36（対応済みは公開物で確認してから書く）を site_plan に追加。

## 翌日の最優先
1. **Gemini 4 Argon を `/timeline/`・`/en/timeline/` に追記**（okamo 10-01 指定・未実施のまま持ち越し）。
   段階提供なので個別ページは作らない。一次情報で確認できた範囲のみ、未確定は「〜との報道」。
   日付は四点（JSON-LD dateModified / 本文 / sitemap lastmod / description）同時更新。
2. **価格ウォッチ（10-03 未実施・課題40）**: DeepSeek V4 Pro / V4.1 Flash / MAI / Kimi K3 / GLM / StepFun。
   cache/ に根拠（取得日・出典URL・前回値比較）を残し、報告に1行。
3. 第11弾「出さない（データレジデンシー）」着手（okamo 指定順④）。

## 未処理の小口
- 課題37: no-training の日英注記揃え（OpenAI「以後の新規会話から」の注記／「有料枠は一律に学習されない」誤読防止）
- 課題38: no-training のファーストビューで「何がうれしいか」＋末尾に主要サービスの設定への一歩
- 課題39: 「2026年9月版／September 2026」残件 11ファイル
  （en/china-ai 2, en/pricing 3, en/glossary/gpt-6-astra-benchmarks 1, en/glossary/benchmark-orgs 1,
   en/glossary/one-million-context 1, en/claude-opus-5-5 1, en/mai 4, china-ai 4, multimodal 1, pricing 4, mai 3）
- 課題32/33: ZDR→ZOA 逆リンク、ZDR/ZOA の記述分担の再点検

## メモ
- 表示の「未確認」は「無い」ではない旨の注記（scroll-hint）を第10弾でも踏襲。
- live の sitemap は get_site_file('sitemap.xml') で安く確認できる（URL集合と lastmod が同時に見える）。

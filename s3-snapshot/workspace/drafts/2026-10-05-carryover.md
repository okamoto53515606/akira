# 持ち越し 2026-10-05 → 翌日

## 今日やったこと（結論・ライブ実測済み）
- **用語説明 第11弾「出さない（データレジデンシー）」を日英公開まで完了**。
  - 公開: `/glossary/data-residency/index.html`, `/en/glossary/data-residency/index.html`,
    `/glossary/index.html`, `/en/glossary/index.html`, `/index.html`, `/en/index.html`,
    `/timeline/index.html`, `/en/timeline/index.html`, `/sitemap.xml`（他は同梱更新で計83ファイル）
  - **verify_publish 83/83 OK** / **verify_published_contracts 違反0** / check_site_pages ERROR 0 / check_dates NG 0（72URL）
  - purge は `index.html` をキー明示（新規・更新ページとも）
- 記事の軸: **「国外に出さない」は①保存（at rest）②処理（推論）の2つの約束に分かれる**。
  OpenAI は storage/processing を別項目、AWS/Google は endpoint・profile、Microsoft は deployment type 3段階、
  Anthropic は inference_geo と workspace_geo の2設定。第7〜10弾（ZDR/ZOA/no-training/four-data-requirements）と相互リンク。
- **GPT税理士: クリティカル0・軽微4 → 全件当日反映**
  1. Anthropic の米国限定推論 1.1x は **Claude 4.6 以降のモデルが対象**（`inference_geo:"us"`）と日英に明記
  2. 「5社すべてで、保存と処理は別の設定・別の文書で決まります」→「別の設定・別の項目で決まります」に弱めた
  3. 「既定値は『どこでも』側のことが多い」→「global（どこでも）側が既定のことが多い」に限定
  4. /deepseek-v4-1-flash/ の「2026-09-29 再確認」を当日（10-05）に統一。Azure 料金ページは本日再取得
     （改訂トークン `awa-stv=20260930-0214-20260930-2100-183594243`、cache/deepseek-azure-2026-10-05.md）。
     **Learn のモデル一覧は 09-29 取得のまま**として日英の「一次情報の更新状況」ボックスに併記（書き分け）。
- **Gemini初心者目線（デスクトップ1280＋スマホ390の2枚）**: 文字化け・ラベル切れなし／SVG文字は読める／
  ①〜④カードは1列化で崩れず／比較表は横スクロール可／意図しない横スクロールなし（90点）。
- 価格ウォッチ6件（DeepSeek V4 Pro / V4.1 Flash / MAI / Kimi K3 / GLM / StepFun）→ cache/pricing-watch-2026-10-05.md。

## 翌日の最優先
1. **用語説明 第12弾 = 「320B MoE（18B active）って何？」**（okamo指定順⑤・唯一残っている指定テーマ）。
   軸＝総パラメータ数と active は別物。ZOA 第9弾の補足節を独立テーマ化して接続。パスは `/glossary/moe-active-parameters/` 想定。
   横長SVGは `.fig-wrap{overflow-x:auto}`＋`svg{min-width:640px}`、figcaption は枠の外（第11弾で実証済み）。
2. **課題42: 料金SOTに Google 系単価が1件も無い**（Gemini の値下げを機械検知できない穴）。誤情報排除の最優先方針に直結。
3. **価格ウォッチ6件**（変化なしも成果。cache/ に根拠）。

## 未処理の小口（前日からの持ち越し）
- 課題32: ZDR（第7弾）→ ZOA（第9弾）の逆リンク。ZDR ページを触る時に追加。
- 課題33: ZDR/ZOA/no-training/data-residency の記述分担の再点検（「保持/アクセス/学習/所在」の一貫性）。
- 課題37: no-training の日英注記揃え（OpenAI「以後の新規会話から」／「有料枠は一律に学習されない」誤読防止）。
- 課題38: no-training の初心者向け強化（ファーストビューで「何がうれしいか」＋末尾に設定への一歩）。
- 課題39: 「2026年9月版／September 2026」残件（10-03 に /mai/ のみ 10月版化。他はページを触る時に順次）。
- 課題46〜48（今日追加）: 一般化の限定／再確認日の書き分け／第11弾の検索語補強。
- 課題29: WARN 22（EN title 過長17・description 長超過5）。**新規ページの description は 320字以内厳守**
  （第11弾 EN は 319 でぎりぎり。次は310字を目安にする）。

## メモ
- 図は「インラインSVG＋Geminiには視認だけ依頼」が最速・最安（API課金なし）。スマホ幅の実測は take_screenshot(width=390) が効く。
- 当日分の一次情報は cache/data-residency-2026-10-05.md に逐語で保存済み（第12弾の下敷きにもなる）。

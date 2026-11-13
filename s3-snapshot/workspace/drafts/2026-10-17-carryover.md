# 2026-10-17 持ち越し（翌朝の自分へ）

## 完了（公開済み・検証済み）
- Meta Muse Wonder を /pricing/・/en/pricing/・/timeline/・/en/timeline/・index 日英・sitemap に反映
- /mai/・/en/mai/ の Azure 料金表の読み方＋ラベル補強（日付 10-17）
- 公開9ファイルすべて verify_publish OK、check_dates NG 0、verify_published_contracts 違反0
- 詳細は notes/2026-10-17.md、価格ウォッチは cache/pricing-watch-2026-10-17.md

## 明日やる（優先順）
1. **課題56**: ローカルの glossary/index.html・en/glossary/index.html が破損（live は正常）。
   `site_download` でローカルを作り直す。**それまで site_upload('.') は絶対にしない**。
2. **課題57**: /pricing/ の各社確認日の更新判定。cache/raw-2026-10-17/ の保存スナップショットを
   ローカルで解析して（OpenAI/Anthropic は .html のみ＝テキスト抽出が未了）、変動の有無を確定し、
   変動なしなら確認日を 10-17 に更新するか方針を決める。再取得はしない（クレジット節約）。
3. **次回最優先1（CTR改善）**: EN を1〜3ページ。候補は /en/timeline/（1506 imp/1 click）、/en/pricing/（310/0）、
   /en/multimodal/（229/0）。改稿記録は課題55の形式で残す。
4. 課題53（/multimodal/ モバイル視認性）・課題54（/mai/ description 長）。

## 注意
- /tmp/site のローカルは他バッチの未公開編集が77件混在。触ったファイルだけ個別 site_upload。
- check_dates は「四点整合」＋meta/og description の日付まで見る（10-17 は NG 0 を確認済み）。

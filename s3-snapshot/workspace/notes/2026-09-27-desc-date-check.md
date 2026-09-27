# description 内「更新日」の整合検査（2026-09-27）

## 背景
Akira のライブ実測で `/multimodal/` の meta description が「2026年9月23日更新。」のまま残存
（ページ宣言日付は 2026-09-27）。原因は **meta description / og:description が三点整合
（JSON-LD dateModified / 本文 time / sitemap lastmod）の検査対象外**だったこと。
→ check_dates に4点目の検査として組み込んだ。

## 実装（/workspace/tools/check_dates.py）
検査対象: `name="description"` / `property="og:description"` / `name="twitter:description"`。

**「更新」に係る日付だけ**を拾う（無関係な日付を誤検知しないため）:
- JP: `2026年9月23日更新` / `更新日: 2026年9月23日`
- EN: `Updated Sep 23, 2026` / `(updated September 23, 2026)`

誤検知ガードの実例（重要）:
`"Released Sept 22, 2026. Updated Sept 25, 2026."` の **前側の Sept 22 は対象外**
（単純に「日付の前後N文字に Updated があるか」で判定すると誤検知する。必ず語順でアンカーする）。

## 検証
1. 実サイト: description日付 23件検査 → NG 0 / 62 URL（三点整合も NG 0）。
2. フィクスチャ（/tmp/site_fixture に html+sitemap を複製し日付を意図的にずらす）:
   - `multimodal/index.html` 09-27→09-23（JP表記）→ 検出 ✓
   - `en/multimodal/index.html` 09-27→09-23（EN表記・description）→ 検出 ✓
   - `en/gpt-6-sol-luna/index.html` の og:description のみ 09-25→09-22 → 検出 ✓（3件NG）
3. 公開後: ライブ実測（curl＋firecrawl maxAge:0）
   - `/multimodal/` = 「…2026年9月27日更新。」✓
   - `/en/multimodal/` = 「…Updated Sep 27, 2026.」✓
   - verify_publish 72/72 OK

## 本日修正した残存
- `/multimodal/` 09-23→**09-27**（og:description は日付なし）
- `/en/multimodal/` 09-23→**09-27**
- `/pricing/`（desc内「（2026年9月23日更新）」）09-23→**09-25**（宣言日付に一致させる）
- `/en/pricing/`（desc内「(updated September 23, 2026)」）09-23→**09-25**

## 注意（運用）
- `tools/*.py` の編集は**翌朝の起動時に読み込まれる**。当日すぐ使いたい場合は
  `python3 /workspace/tools/check_dates.py /tmp/site` を shell から直接実行する
  （登録済みツールは当日分は旧版のまま。本日 check_dates ツール呼び出しが旧出力だった実例あり）。

## 追試（GPT税理士の軽微指摘2に対応・09-27）
`check_dates.desc_update_dates()` のユニット確認（6ケース全OK）:
- `name="twitter:description"` 検出 ✓ / 属性順が `content` 先（`<meta content="..." name="twitter:description">`）でも検出 ✓
- `og:description`（JP表記）✓ / `description` の「更新日: …」✓
- `Released Sept 22, 2026. Updated Sept 25, 2026.` → 09-25 のみ採用（前側は拾わない）✓
- `Updated 7-1-2026`（未対応表記）→ 検出なし＝誤検知しない ✓（未対応表記は日付検査の網から外れるので、
  表記ゆれを増やしたくなったら日付パターンに追記する）
※ 3文字略称の前方一致は `Sep` が `Sept` も拾う実装。`Sept` 単体のテストも上記で確認済み。

## 環境の落とし穴（09-27 実測）
`python3` を **cwd=/tmp** で実行すると `/tmp/inspect.py`（過去作業の残骸）が stdlib の `inspect` を
shadow し、`from strands import tool` が `AttributeError: module 'inspect' has no attribute 'signature'` で落ちる。
→ **tools の動作確認は cwd=/workspace/tools で実行する**（または /tmp 直下の .py を消す）。

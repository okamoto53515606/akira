# 料金表と更新履歴が壊れた件（2026-11-17）

## 今回の前提

| 項目 | 値 |
|---|---|
| 発生日 | 2026-11-17 05:33 JST（定時ラン / タスク定義 `akira-daily:latest`） |
| 壊れたページ | `/pricing/`・`/en/pricing/`・`/changelog/`・`/en/changelog/`・トップ（日英） |
| 発見 | okamo が公開後に目視で発見（`/pricing/` の Xiaomi 表に Kimi の行、Kimi 表に Meta の行） |
| 直接の実行者 | Claudeエンジニア（DeepSeek節約モード）|
| 修正 | 2026-11-17 06:35〜06:39 JST（S3 18ファイル＋CloudFront invalidation＋ECRイメージ） |

## 何が起きていたか

### 1. 料金表のセクションと中身がずれた

`/pricing/` の Xiaomi（MiMo）セクションに **Kimi の3行**が、Moonshot（Kimi）セクションに
**Meta（Muse）の3行**が入り、MiMo-V2.6 の行はどこにも無い状態で公開された。
セクションの見出し・注記・出典URLはすべて正しく、**表の中身だけが1つずつ後ろの表のもの**だった。

原因は2段階:

1. **挿入位置の誤り**（エンジニア）
   `<h2>` の直前に差し込んだため、新しい Xiaomi の見出しが
   `<section aria-labelledby="kimi-h">` の内側に入った（`aria-labelledby` と実体が不一致）。
   エンジニアはこの時点で気づき、`<section>` 境界で切り直して直した（ログに残っている）。
2. **描画エンジンが位置で表を決めていた**（ハーネス）
   `render_site.py` の `render_pricing()` は台帳 `facts.json: pricing_tables[i].index` を
   「ページの i 番目の `<table>`」とみなして `<tbody>` を書き戻していた。
   表が1つ増えた結果、**Xiaomi の表に Kimi の台帳行、Kimi の表に Meta の台帳行**が書き込まれ、
   最後の Meta の表は台帳の範囲外なのでそのまま残った（＝Muse の表が2つ）。
   エンジニアは `site_upload` の後半で `render_site` が自動実行されることを見落としていた。

**どのゲートも止めなかった**。`page_shape` は表の列数と日英差しか見ず、
`self_check` の「台帳とのズレ」は「描画結果が今の HTML と同じか」を見るので、
**両方が同じ間違い**だと差分0（＝緑）になる。

### 2. 更新履歴が同じ日付の「〜を公開」で埋まった

`site_upload(".")` でサイト全体を上げ直したところ、`_register_site_event()` が
**既存ページ32件**を「2026-11-17 に公開」として `site_events` に登録した。
トップの「直近の更新」と `/changelog/` は `site_events` から生成されるため、
同じ日付の汎用文言が32件並び、本当の作業（Xiaomi の追加）が埋もれた。

- 旧実装は「`site_events` に未登録のページなら新規」と判定していた。
  → 「一度もイベントを書いていない既存ページ」は全部“新規”になる。
- `en/index.html` は slug が `en` になり `startswith("en/")` をすり抜けて `/en/` 自体が
  1ページとして登録された。

### 3. 日付が1日ずれる（課題155）

`render_site.py` の `TODAY = date.today()` はコンテナ（UTC）基準で、JST 05:00 のランでは
**前日**が焼かれる。`tools.py` 側は `datetime.now(JST)` なので、同じランの中で
sitemap の lastmod（JST）とページの dateModified（UTC）が食い違う素地があった。

## 対処（2026-11-17 実装・公開済み）

| 対象 | 内容 |
|---|---|
| `/pricing/` 日英 | 事故前（11-15）の内容に戻し、MiMo-V2.6（Pro / Flash / Pro-UltraSpeed）の正しい行を持つ Xiaomi セクションを `<section aria-labelledby="xiaomi">` として独立挿入。目次にも追加 |
| 単価 | 公式ページ `mimo.xiaomi.com/mimo-v2-6` のスナップショット（`cache/mimo-v26-pricing-2026-11-17.md`）から転記：Flash $0.14/$0.0028/$0.28、Pro $0.435/$0.0036/$0.87、Pro-UltraSpeed $4.35/$0.036/$8.70 |
| 台帳 `facts.json` | 偽の `site_events` 32件を削除。Xiaomi の作業イベントを 2026-11-17 に更新。`pricing_tables` に `anchor` を付与し Xiaomi の表を7番目に追加（9→10表） |
| トップ・更新履歴・sitemap | `render_site` で再生成（更新履歴は70件・11-17 は1件のみ） |
| 用語集6ページ | `aria-labelledby="src-h"` の実体が無かった（11-15 の折りたたみ化で `<h2 id>` が消えた）ので `<summary id="src-h">` を付与 |

## 再発防止（実装済み）

1. **`render_pricing` をアンカー方式に変更**（`/workspace/tools/render_site.py`）
   - `pricing_tables[i].anchor`（セクションの id）で表を特定する。位置 `index` は使わない。
   - 書き込みの**前**に「その表の1行目のモデル名＝台帳の1行目」を照合し、
     違えば**その表には書かず理由を残す**（fail-closed）。
   - 書き込みの**後**に「表の数が変わっていない」「1行目が台帳どおり」を検算し、
     崩れていれば書き込みを中止する。
2. **新しい公開ゲート `check_sections.py`**（7本目）
   - S1: `<section aria-labelledby="X">` の中に `id="X"` があるか（境界ずれの検出）
   - S2: `/pricing/`・`/en/pricing/` の各表の1行目が台帳と一致するか（表の取り違えの検出）
   - `site_upload` のゲート列と `self_check` の両方に登録。違反ページは**公開しない**。
3. **`site_events` の自動登録を「S3 に無かったキー」だけに限定**（`tools.py`）
   - アップロード前に `head_object` で存在確認し、結果を `is_new` として渡す。
   - `/en/` など言語ルートは登録しない。
4. **`TODAY` を JST 固定**（`render_site.py`）。サイトは日本時間で運用する。
5. 回帰テスト（オフライン・8項目）で、事故版のページを渡すと
   ゲートが ERROR／描画が見送る／修正版は冪等、を確認。

## 前提が変わったときの要注意事項

| 前提 | 崩れた場合に変わること |
|---|---|
| 料金表の並びは `heading id` で一意に決まる | 同じ id のセクションを増やす・id を改名すると **render は書かなくなる**（fail-closed）。`facts.json: pricing_tables[].anchor` も同時に直す |
| 新しいプロバイダ表は「HTML＋台帳」の両方に足す | HTML だけ足すと、その表は台帳管理外になる（render は触らない＝手編集が残る）。S2 は台帳に無い表を WARN で知らせる |
| `site_upload` は新規ページしか履歴に載せない | 「既存ページの大幅更新を履歴に載せたい」運用にするなら、`site_events` を明示的に書く（自動検知に頼らない） |
| サイトの「今日」は JST | 深夜0時前後のランでは日付境界が変わる。UTC 前提の資料・ログと突き合わせるときは ±1日に注意（課題155の残り） |
| `:latest` 参照でタスク定義は更新不要 | タスク定義をリビジョン固定に変えた場合は、イメージ push 後に `update-schedule` / タスク定義の更新が必要 |

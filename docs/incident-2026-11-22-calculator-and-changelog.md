# 2026-11-22 の自動ランで見つかった2件（計算機の円換算が全行¥0／更新履歴が0件）

対象ラン: 2026-11-22 05:00 JST（`/ecs/akira` のログ 5,736行）。
7ゲート・ページ監査・公開契約チェックは**すべて ERROR 0**。どちらも「HTTP 200・表も出る・
日付も新しい」状態で、画面の**値**を見ないと分からない故障だった。

## 1. 症状（okamoの指摘）

| # | 症状 | 実測 |
|---|---|---|
| 1 | トークン計算機の「参考円換算」がすべて ¥0 | `/calculator/`・`/en/calculator/` の59行すべて ¥0。為替入力 `#fx-rate` が空 |
| 2 | `/changelog/` に今日の更新が0件 | 最終更新が 2026年11月21日。一方 sitemap の changelog lastmod は 2026-11-22 |

## 2. 円換算が ¥0 だった原因

計算機のJSは為替を **`/data/models.json` の `fx.usd_jpy`** から読む。

```js
if (d && d.fx && d.fx.usd_jpy) { document.getElementById("fx-rate").value = d.fx.usd_jpy; }
// 入力が空なら f = parseFloat("") || 0 → 円換算 = USD × 0 = ¥0
```

ところが公開中の `data/models.json` のトップレベルは `updated` / `source` / `models` だけで、
**`fx` が無い**。`fx` は台帳 `facts.json` にしか無く、`render_models_json` が
`models.json` へ写していなかった。入力欄の初期値も `value=""` だった。

- 2026-11-15 に「HTMLの固定値 155」から「JSONの `fx`」へ移したが、**描画側が追随していない**。
  その日から 11-22 まで、7日間この状態だった。
- 既存の検査は `models` 配列の契約（必須キー・正の単価・行数）と、計算機ページが
  `data/models.json` を参照しているか・GA4タグがあるかだけを見ていた。
  **「計算結果が0でないこと」を誰も見ていなかった。**
- さらに `EN` 側も同じで、日英どちらも「それらしい表」が出るため違和感が出ない。

## 3. 更新履歴が0件だった原因

11-21 に「1依頼83回の儀式」を減らすため `publish_and_verify`（描画→ゲート→公開→
invalidation→実URL照合）を追加した。しかし `site_upload` が持っていた次の2つが
**移されていなかった**。

1. 中身が変わった既存ページを `facts.json` の `site_events` に「更新」として足す
   （`_register_site_updates`）
2. 登録があったらトップ・`/changelog/`・sitemap を描き直して**その場で公開する**
   （`_render_and_publish_entrypoints`）

11-22 のランは `publish_and_verify` を7回だけ使い、`site_upload` は0回。したがって
`site_events` は 11-21 のまま＝`/changelog/` に今日の欄ができない。

加えて、描画は冪等で「**その呼び出しで変わったファイル**」しか返さない。05:16 に別の
`render_site` 呼び出しが changelog の日付行だけ書き換えており、後の `publish_and_verify`
からは「変化なし」に見えたため、changelog は公開対象にすら入らなかった。
sitemap の lastmod だけが 11-22 に進み、**「変わったように見える」静かな偽OK**が残った。

## 4. 直したこと

### 4-1. 検査と公開ゲート（`tools.py`）

| 追加 | 内容 |
|---|---|
| `validate_calculator_models` | `fx.usd_jpy` が正の数値であることを**必須**にした。無い/0/文字列は公開拒否 |
| `check_published_contracts` C2b | 計算機ページの `#fx-rate` の初期値が空/0 なら違反（＝全行¥0になる） |
| `repair_calculator_fx()` | 台帳 `facts.fx`（無ければ155）から `data/models.json` と計算機ページの初期値を**決定論的に**入れ直す。HTMLは `/*` で invalidation |
| `publish_and_verify` | 変更された既存ページの `site_events` 登録、新規ページの登録、入り口の再描画・公開、sitemap lastmod の更新を通すようにした（`site_upload` と同じ経路） |
| `_render_and_publish_entrypoints` | HTMLを含む再公開では invalidation を `/*` にする（viewer-request が `/x/`→`/x/index.html` に書き換えるため、パス指定では落ちない） |

### 4-2. 毎朝の自動修復（`main.py`）

`_repair_contract_violations()` を追加し、**起動時**と**公開後**の契約チェックの両方で呼ぶ。

- `fx`／為替の違反 → `repair_calculator_fx()`（LLMコスト0）
- それ以外の計算機データ破損 → 既存の `restore_published_data_file()`（ベースライン復元）
- 修復した内容はログと日報の「自動メンテナンス」欄に出る

`repair_calculator_fx` は Akira 本体とエンジニアの両方のツールにも配布した。
ただし `--dry-run` / `--no-publish` では**修復ツール自体を渡さない**（従来は
`restore_published_data_file` がテストランでも書き込めた）。

### 4-3. 描画側（workspace `tools/render_site.py`）

`render_models_json` が `fx` を書くようにした（台帳 `facts.fx` が正、無ければ155）。
`fx` の有無も「変更あり」の判定に含めるので、**次に描画した時点で直る**。

## 5. 今日の公開物（実測）

- `data/models.json`: `fx={"usd_jpy":155,...}`、59行
- `/calculator/`・`/en/calculator/`: `value="155"`。ブラウザで実行して **59行・¥28/¥30/¥31**（0円なし）
- `/changelog/`: 2026-11-22 のエントリ4件（料金比較・DeepSeek・Gemini 3.8 Flash・画像/音声API）、最終更新 11-22
- invalidation: `I2O7V1VG21X03EKNLF5F6VNZ8X`（`/*`）
- 計算機データのベースライン（`akira-workspace/data/calculator-models.json`）にも `fx` を入れた
  （復元時に「ベースライン自体が契約違反」で復元できない状態を避けるため）

## 6. 再発防止の考え方

- **「配線」ではなく「値」を検査する。** `data/models.json` を読んでいることは正常の証拠にならない。
  為替が入っているか、計算結果が0でないかを見る。
- **冪等な描画と公開を分けない。** 「描画の差分」を公開対象にすると、先に描いた変更が
  取り残される。公開ツールは**状態**（`site_events`・実ファイルの中身）から対象を決める。
- **lastmod は中身が変わったときだけ動かす。** 日付だけ進むと「更新した」という嘘の信号になる。

## 7. 前提が変わったときの注意

| 前提 | 崩れた場合に変わること |
|---|---|
| 為替は1ドル=155円で固定（`facts.fx`） | 変動させるなら `facts.fx.usd_jpy` を唯一の入口にし、`repair_calculator_fx` と計算機ページの初期値を同時に更新する。ページに「1ドル=155円」と書いた散文も直す |
| 計算機のJSは `models.json` の `fx` を読む | 読まない実装に変えるなら、C2b（初期値の検査）と `repair_calculator_fx` の対象を見直す |
| 公開は `publish_and_verify` か `site_upload` を通る | 第3の公開経路を足すときは、`site_events` 登録と入り口の再描画を必ず同じ場所に入れる（今回の穴） |
| `site_events` が `/changelog/` の唯一の入力 | 手書きの履歴を混ぜるなら、重複判定（同日・同slug）と8件超の集約ルールを維持する |

## 8. 検証とデプロイ

- `test_regression_20261122.py` **16/16 PASS**（fx欠落→契約違反、初期値の修復が冪等、
  中身が変わったページだけ `site_events` に載る／日付だけの変更は載らない）
- 既存: `test_regression_20261121.py` 96/96 PASS、`test_regression_20261119.py` ALL PASS
- イメージ内で同一の検証を実行（`docker run`）
- ECR `akira:latest` digest `sha256:b4d72db9933253a6a3621c0fbdf6b53554ad8f97602efd445ad18262d36c40cb`
- workspace `tools/render_site.py`・`data/facts.json`・`data/calculator-models.json` を更新

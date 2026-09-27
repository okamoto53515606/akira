# llm.okamomedia.tokyo サイト概要（2026-09-27 時点）

> この資料は、公開サイトの「今の姿」を数字でまとめたものです。PV等はGA4のBigQuery
> エクスポート、検索はSearch ConsoleのBigQueryエクスポートから直接集計しています
> （集計の条件と注意は末尾「6. 数字の出典と注意」にまとめました）。

---

## 1. ひとことで

| 項目 | 内容 |
|---|---|
| サイト | **LLM Data Hub**（<https://llm.okamomedia.tokyo/>） |
| 目的 | 広告なしで、LLMの料金・モデル情報・用語解説を一次情報ベースで更新し続けるデータハブ |
| 英語版 | <https://llm.okamomedia.tokyo/en/>（主要ページは日英同格。`hreflang` で振り分け） |
| 公開ページ数 | **62URL（日本語31・英語31）**。`sitemap.xml` の登録数と一致 |
| 中身の構成 | HTML 63ファイル（うち `404.html`）、画像5、CSS 1、`data/models.json` 1、`robots.txt`、`sitemap.xml` |
| 技術 | S3 + CloudFront の静的配信。ビルドツールなしの素のHTML/CSS/JS |
| 更新 | 2日ごと 05:00（JST）にAIが自動で更新（更新の仕組みは [自己改善ループの資料](self-improvement-loop.md) を参照） |
| 実物のコピー | <https://github.com/okamoto53515606/akira/tree/main/s3-snapshot/site>（同日時点のスナップショット） |

---

## 2. ページ構成（主要ページのみ）

| 分類 | 日本語 | 英語 | 役割 |
|---|---|---|---|
| トップ | [/](https://llm.okamomedia.tokyo/) | [/en/](https://llm.okamomedia.tokyo/en/) | サイトの入口。主要ページへのカード一覧 |
| 料金比較 | [/pricing/](https://llm.okamomedia.tokyo/pricing/) | [/en/pricing/](https://llm.okamomedia.tokyo/en/pricing/) | モデル別の入力/出力単価を一次情報で比較 |
| コスト計算機 | [/calculator/](https://llm.okamomedia.tokyo/calculator/) | [/en/calculator/](https://llm.okamomedia.tokyo/en/calculator/) | トークン数から費用を試算（`data/models.json` を読んで描画） |
| タイムライン | [/timeline/](https://llm.okamomedia.tokyo/timeline/) | [/en/timeline/](https://llm.okamomedia.tokyo/en/timeline/) | モデルのリリース・料金改定の履歴 |
| 中国AI | [/china-ai/](https://llm.okamomedia.tokyo/china-ai/) | [/en/china-ai/](https://llm.okamomedia.tokyo/en/china-ai/) | 中国系モデル（DeepSeek・Qwen・Kimi・MiMo等）の動向 |
| マルチモーダル | [/multimodal/](https://llm.okamomedia.tokyo/multimodal/) | [/en/multimodal/](https://llm.okamomedia.tokyo/en/multimodal/) | 入力/出力で何を扱えるかの整理 |
| 用語説明（ハブ） | [/glossary/](https://llm.okamomedia.tokyo/glossary/) | [/en/glossary/](https://llm.okamomedia.tokyo/en/glossary/) | 初心者向けの用語解説。配下に7本 |
| モデル個別（17本） | 例: [/deepseek-v4-1-flash/](https://llm.okamomedia.tokyo/deepseek-v4-1-flash/)、[/gpt-6/](https://llm.okamomedia.tokyo/gpt-6/)、[/claude-opus-5-5/](https://llm.okamomedia.tokyo/claude-opus-5-5/)、[/grok-4-7/](https://llm.okamomedia.tokyo/grok-4-7/)、[/mai/](https://llm.okamomedia.tokyo/mai/)、[/qwen-3-8-flash/](https://llm.okamomedia.tokyo/qwen-3-8-flash/) | 同左（`/en/` 配下） | モデルごとの料金・仕様・出典 |
| 用語説明の各ページ（7本） | 例: [/glossary/prompt-cache/](https://llm.okamomedia.tokyo/glossary/prompt-cache/)、[/glossary/harness/](https://llm.okamomedia.tokyo/glossary/harness/)、[/glossary/zero-data-retention/](https://llm.okamomedia.tokyo/glossary/zero-data-retention/) | 同左（`/en/` 配下） | プロンプトキャッシュ／ハーネス／100万コンテキスト／ベンチマーク／ベンチ運営組織／GPT-6 Astraベンチ／ZDR |

> モデル個別ページ17本の内訳: Claude Fable 5.1・Claude Mythos 5.1・Claude Opus 5.5・DeepSeek V4.1 Flash・
> DeepSeek V4 Pro・Gemini 3.1 Flash-Lite・Gemini 3.7 Flash・Gemini 3.8 Flash・GLM 5.3 Flash・
> GPT-5.6 Luna・GPT-5.6 Sol・GPT-6・GPT-6 Sol Luna・Grok 4.6・Grok 4.7・MAI・Qwen 3.8 Flash。

---

## 3. アクセス（PV）

### 3.1 今月（2026-09-01〜09-26）

| 指標 | 値 | 備考 |
|---|---|---|
| ページビュー | **777** | `page_view` イベントの回数 |
| 訪問者 | 450 | ブラウザ単位の概算（`user_pseudo_id` の数） |
| セッション | 500 | 30分の空白で区切った訪問の数 |
| 言語比 | 英語 407 / 日本語 370 | ほぼ半々だが、英語がやや上回る |

### 3.2 直近14日（2026-09-13〜09-26）

| 指標 | 値 |
|---|---|
| ページビュー | **451** |
| 訪問者 | 350 |
| セッション | 384 |
| 言語比 | **英語 296（66%） / 日本語 155（34%）** |

日別の推移（PV）:

| 日 | 合計 | 英語 | 日本語 | | 日 | 合計 | 英語 | 日本語 |
|---|---|---|---|---|---|---|---|---|
| 09/13 | 16 | 3 | 13 | | 09/20 | 44 | 43 | 1 |
| 09/14 | 41 | 28 | 13 | | 09/21 | 37 | 34 | 3 |
| 09/15 | 50 | 14 | 36 | | 09/22 | 29 | 17 | 12 |
| 09/16 | 13 | 11 | 2 | | 09/23 | 46 | 21 | 25 |
| 09/17 | 17 | 10 | 7 | | 09/24 | 27 | 17 | 10 |
| 09/18 | 31 | 28 | 3 | | 09/25 | 28 | 20 | 8 |
| 09/19 | 43 | 33 | 10 | | 09/26 | 29 | 17 | 12 |

### 3.3 よく読まれているページ

**今月（09-01〜09-26）**

| ページ | PV | 訪問者 |
|---|---|---|
| [/](https://llm.okamomedia.tokyo/) | 113 | 42 |
| [/en/deepseek-v4-1-flash/](https://llm.okamomedia.tokyo/en/deepseek-v4-1-flash/) | 59 | 53 |
| [/multimodal/](https://llm.okamomedia.tokyo/multimodal/) | 47 | 8 |
| [/en/china-ai/](https://llm.okamomedia.tokyo/en/china-ai/) | 41 | 38 |
| [/pricing/](https://llm.okamomedia.tokyo/pricing/) | 40 | 8 |
| [/timeline/](https://llm.okamomedia.tokyo/timeline/) | 39 | 29 |
| [/calculator/](https://llm.okamomedia.tokyo/calculator/) | 33 | 13 |
| [/en/timeline/](https://llm.okamomedia.tokyo/en/timeline/) | 32 | 28 |
| [/en/pricing/](https://llm.okamomedia.tokyo/en/pricing/) | 32 | 28 |
| [/en/](https://llm.okamomedia.tokyo/en/) | 31 | 16 |

**直近14日（09-13〜09-26）**

| ページ | PV | | ページ | PV |
|---|---|---|---|---|
| [/en/deepseek-v4-1-flash/](https://llm.okamomedia.tokyo/en/deepseek-v4-1-flash/) | 58 | | [/en/](https://llm.okamomedia.tokyo/en/) | 15 |
| [/](https://llm.okamomedia.tokyo/) | 56 | | [/en/multimodal/](https://llm.okamomedia.tokyo/en/multimodal/) | 13 |
| [/en/china-ai/](https://llm.okamomedia.tokyo/en/china-ai/) | 33 | | [/en/deepseek-v4-pro/](https://llm.okamomedia.tokyo/en/deepseek-v4-pro/) | 13 |
| [/timeline/](https://llm.okamomedia.tokyo/timeline/) | 18 | | [/pricing/](https://llm.okamomedia.tokyo/pricing/) | 11 |
| [/en/timeline/](https://llm.okamomedia.tokyo/en/timeline/) | 18 | | [/glossary/](https://llm.okamomedia.tokyo/glossary/) | 10 |

> 参考: 開設（2026-07-10 が最初の計測日）からの累計は **1,056PV / 547人 / 663セッション**。
> 月別では 7月132 → 8月147 → 9月777（09-26まで）と、9月に入って大きく伸びています。

---

## 4. 検索からの流入（Search Console、2026-09-01〜09-27）

| 指標 | 値 |
|---|---|
| 表示回数 | 13,917 |
| クリック | 60 |
| クリック率 | 0.43% |
| 平均掲載順位 | 27.3位 |

**表示が多いページ**（＝検索結果に出ているページ）

| ページ | 表示 | クリック |
|---|---|---|
| [/en/china-ai/](https://llm.okamomedia.tokyo/en/china-ai/) | 5,132 | 2 |
| [/en/deepseek-v4-1-flash/](https://llm.okamomedia.tokyo/en/deepseek-v4-1-flash/) | 2,293 | 22 |
| [/en/timeline/](https://llm.okamomedia.tokyo/en/timeline/) | 1,448 | 0 |
| [/en/deepseek-v4-pro/](https://llm.okamomedia.tokyo/en/deepseek-v4-pro/) | 619 | 0 |
| [/en/pricing/](https://llm.okamomedia.tokyo/en/pricing/) | 544 | 0 |
| [/en/glm-5-3-flash/](https://llm.okamomedia.tokyo/en/glm-5-3-flash/) | 473 | 0 |
| [/en/mai/](https://llm.okamomedia.tokyo/en/mai/) | 352 | 1 |
| [/timeline/](https://llm.okamomedia.tokyo/timeline/) | 280 | **15** |

**検索語（上位、検索語が分かる分のみ）**

| 検索語 | 表示 | 平均順位 |
|---|---|---|
| deepseek v4.1 flash azure | 40 | 6.1 |
| azure deepseek v4.1 | 27 | 5.9 |
| chinese open model licenses deepseek qwen apache mit | 23 | 13.2 |
| "deepseek-v4.1-pro" | 19 | 9.5 |
| deepseek v4.1 azure | 19 | 7.5 |
| deepseek minimax chinese ai model launch this week | 17 | 14.6 |
| qwen 4.0 release date 2026 | 15 | 23.6 |
| deepseek v4.1 flash 料金 | 13 | 17.5 |
| "deepseek-v4.1-flash" github | 11 | 13.0 |

読み取れること（そのまま数字が示していること）:

- **表示は英語ページに集中**しています（`/en/china-ai/` だけで全体表示の約37%）。一方で**クリックは日本語の
  `/timeline/`** と **`/en/deepseek-v4-1-flash/`** に集まっており、英語ページは「出るが押されていない」状態です
- 検索語は DeepSeek（特に Azure 経由）・中国AIまわりの需要が目立ちます

---

## 5. 直近の日報（2026-09-27）

- **日報**: <https://akira.okamomedia.tokyo/reports/2026-09-27.html>
- **一覧**: <https://akira.okamomedia.tokyo/>（2026-07-02〜2026-09-27 の **46件**。サイトを動かした人間＝okamoさんのコメントが付いた日には💬が付きます）

日報は「AIがその日なにをしたか」を毎回そのまま公開しているページです。09-27 の内容は次のとおりです。

| 項目 | 内容 |
|---|---|
| 用語説明 第7弾 | **ZDR（ゼロデータ保持）**を日英で公開（`/glossary/zero-data-retention/` と `/en/...`）。軸は「ZDRは既定であって常時有効ではない」 |
| 中国AI・マルチモーダル | **MiMo v2.6（Xiaomi）**の Pro / Flash を `/china-ai/`・`/multimodal/` の日英と `/timeline/`、`data/models.json` に反映（個別ページは作らず主力ページを厚くする判断） |
| 品質チェックと修復 | ページの更新日が4か所（JSON-LD・本文・sitemap・meta description）で食い違う**再発バグを検出して修正**し、`check_dates.py` に description の日付検査を追加（62URLでNG 0） |
| レビュー | GPT税理士の1回目でクリティカル1件（表現の不正確さ）→ 日英4か所を書き分けて修正、2回目は0件 |
| 価格ウォッチ | DeepSeek・MS MAI・Kimi K3 はいずれも**変化なし**（「変化なし」も成果として記録） |
| 公開の確認 | `check_site_pages.py` ERROR 0 ／ `check_dates.py` 62/62 NG 0 ／ `verify_publish` 72/72 MD5一致 ／ ライブ実物を抜き打ち確認 |
| その日の費用 | 当月LLM費用 約3,991円 / 予算9,300円 |
| okamoさんへの依頼 | ①「火事の標語」の解釈が合っているかの確認 ②用語説明 第8弾のテーマ指定（ZOA／データ主権） ③MiMoを単独ページで追うかの判断 |

---

## 6. 数字の出典と注意

| 項目 | 内容 |
|---|---|
| PVの出典 | GA4のBigQueryエクスポート `okamo1-153103.analytics_543969888.events_*` を直接集計 |
| PVの数え方 | `page_view` イベントの件数。訪問者は `user_pseudo_id`、セッションは `ga_session_id` のユニーク数 |
| 期間の定義 | 「今月」= 2026-09-01〜09-26、「直近14日」= 2026-09-13〜09-26。**09-27 は集計が不完全なため含めていません** |
| 言語の判定 | URLに `/en/` を含むものを英語ページとして数えています（トップ `/en/` も含む） |
| 末尾スラッシュ | 同じページの `/xxx` と `/xxx/` は統合して数えています（生ログでは分かれます） |
| 日報との差 | 日報の記載値と±数件ずれることがあります（集計期間の取り方の違いによるものです） |
| 検索の出典 | Search ConsoleのBigQueryエクスポート `okamo1-153103.searchconsole_llm.searchdata_url_impression` |
| 検索語の注意 | Google側で匿名化された検索語は空欄になります。09-01〜09-27 では **13,127表示（クリック55）が匿名**で、検索語が分かるのは **306語・790表示・クリック5** のみです |
| 反映ラグ | Search Console のデータは2〜3日遅れて反映されます（末尾の日は少なめに出ます） |
| 日報サイトのPV | 日報サイト（`akira.okamomedia.tokyo`、GA4プロパティ 544003620）はBigQueryへのエクスポートが無いため、この資料には含めていません |

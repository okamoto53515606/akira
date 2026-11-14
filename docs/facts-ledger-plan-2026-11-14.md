# LLM Data Hub 鮮度・整合性の改善計画（2026-11-14）

## 1. 今回の前提

- サイトの事実は**3系統に分裂**している: 各ページのHTML本文 / `/timeline/` のエントリ / `/workspace/data/price-sot.json`。
- 実行主体は Akira（DeepSeek V4.1 Flash）→ Claudeエンジニア（DeepSeek）。レビューは GPT税理士・Gemini子育てママ。
- 月予算 9,300円。1ランの実費は概ね 50〜60円。
- Akira はHTMLを読まない。エンジニアの**報告（要約）**で判断する。
- 検証に使える材料: CloudWatchログ（`cloudwatchlog/`）、S3スナップショット（`s3-snapshot/`）、DynamoDB `akira-config`（site_plan / lessons）、GA4 + GSC（BigQuery）。
- 本日の判断が正しいかは**後日にならないと分からない**。よって「仮説」と「反証条件」と「経過チェック日」を先に決める（§6）。

---

## 2. 課題（実測した事実）

| # | 事象 | 実測値（2026-11-14 時点） |
|---|---|---|
| K1 | EN `/timeline/` を「drafts退避」した | 退避先 `drafts/2026-11-14_tasks.md` に Hydrogen / Qwen4 の英訳は**無い**。＝退避ではなく消失 |
| K2 | 最新情報の取得に人間のURL指定が必要 | Fable 5.2 のキャッシュ単価は `platform.claude.com/docs/en/about-claude/pricing` を直接叩けば逐語で取れる（$10.00/$16.00/$0.20、0.025x）。**取得能力ではなく探索能力の問題** |
| K3 | GPT税理士が誤指摘し、正しい記述を削らせた | 「Carbon を GA と書くのは誤り」は**誤り**。公式ブログ `gemini-4-carbon-now-available` = Nov 10, 2026 "now available"。GPTは「提示された一次情報によれば」と書きながら引用が無い（＝捏造） |
| K4 | 固有名詞を検証せず計画に写した | 「Underdog Woof Japanese」は okamo の 11-12 コメント由来。実在はする（ConwayResearch / 40.5MB TTS / HuggingFace）が、Akira は存在確認していない |
| K5 | `/timeline/` の並び順が壊れている | ja 54件 / en 49件。両方で**新規が末尾に追記**され降順が崩壊。`2026-10` という不正な日付が日英に存在。`dot-anthropic` + `Alibaba` という誤クラスも1件 |
| K6 | `/china-ai/` で Qwen 4 の記述が二重・矛盾 | 「11-14 追記: プレビュー開始」の直下に「Qwen 4（公式は「学習中」）」が残存。更新履歴も「学習中のみ掲載」のまま＝**同一事実が3箇所で別方向** |
| K7 | Gemini 4 Hydrogen が pricing / 計算機 / トップに無い | `hydrogen` の出現数: `/pricing/` 0, `/en/pricing/` 0, `/` 0, `/en/` 0, `data/models.json` 0。**timeline のみ** |
| K8 | 更新履歴が各ページに分散 | 全ページが独自の `changelog` を持つ。全体を俯瞰した履歴は存在しない |
| K9 | **レビュー担当の証拠が陳腐化している** | `/workspace/cache/` の最新 `取得日時:` は **2026-11-05**。11-10 以降の事実が1件も入っていない。GPT は 11-03 の cache を再生した（§3.1） |
| K10 | **公開ゲートがページ間の整合を見ていない** | `check_site_pages`=単一ページの構造、`check_dates`=日付のみ。timeline の順序・日英差分・反映漏れは検出対象外だった |

補足（決定的）:

```
/workspace/data/price-sot.json : 31モデル / last_verified 2026-10-29
  Fable 5.2 / GPT-6 Astra / Carbon / Hydrogen / Qwen4 / Muse Ember / Kimi K3.1 Pro は未収録
```

SOT は存在するが **16日前で停止し、ページ生成に使われていない**。真実が3系統に分かれたまま、どれも同期していない。

---

## 3. 原因（仮説。まだ確定ではない）

| ID | 仮説 | 支持する観測 | 反証条件 |
|---|---|---|---|
| H1 | **事実の器が「HTMLの文章」**なので、更新が「置換」ではなく「追記」になる | K6（追記だけして旧段落が残る）、K5（末尾追記） | 台帳生成に切り替えた後も同一事実の併存が再発する |
| H2 | **同一事実の出現箇所の一覧が無い**ので、Hydrogen を pricing に載せるべきだと誰も知らない | K7（4ページで0件）、K1（ja だけ更新） | 一覧を機械が持っても反映漏れが続く |
| H3 | **鮮度トリガーが無い**（`fetched_at` を持つ台帳が無い）ので「何が古いか」を機械が言えない | K2（人間がURLを渡す）、SOT が10-29で停止 | 鮮度キューを入れても取得が発生しない |
| H4 | **レビューのクリティカル判定に引用要件が無い**ので、捏造が事実を上書きできる | K3（引用ゼロの critical が正しい記述を削った） | quote 必須化後も捏造 critical が出る |
| H5 | **凍結ルールの適用範囲が広すぎる**（事実追加まで止めた） | K1（「凍結中→drafts」が「事実訂正は例外」に優先した） | 凍結の定義を絞っても同種の保留が起きる |
| H6 | **検証が「単一ページの構造」と「日付」だけ**で、ページ間整合を見ていない | K5/K6/K7 がすべて既存ゲートを通過 | 整合ゲートを入れても検出できない矛盾が出る |

H1〜H3 が主因、H4〜H6 が「検出できず残る」理由、という読み。

### 3.1 K3（GPTの誤指摘）の真因 — 実測で特定

**幻覚ではない。古い証拠の再生である。**

- GPTは10回のツール呼び出しの内訳が `list_local_files` → `list_workspace_files` → `file_read` ×8。**Brave は1回も呼んでいない**（Braveは渡されている）。
- `/workspace/cache/gemini-4-carbon-2026-11-03.md` の判定文はこうなっている:
  > 判定: **限定提供（cyber defenders の一部＋Fairwind Program）**。開発者/企業/消費者向けAPIは未提供。GA でも Preview でもない。
  > → 将来時制（will launch）＝**予告価格**。現時点でAPI未提供のため料金表の「提供中」行としては載せない。

  これは GPT の指摘（「一部のサイバー防御者・Fairwind参加者への限定提供」「予告価格として区別」）と**ほぼ同文**。つまりGPTは 11-03 の cache を読み、その結論をそのまま返した。
- しかも `/workspace/cache/` の**最新は 2026-11-05**。11-10（Carbon GA）・11-12（Hydrogen）・11-14（Fable 5.2 キャッシュ）の事実は **cache に一度も書かれていない**。エンジニアが会話の中で取得しただけで、レビュー担当の証拠置き場に落ちていない。

重なった5つの要因:

| # | 要因 | 実測 |
|---|---|---|
| a | **レビュー証拠の陳腐化** | cache 最新 11-05。当日の事実が無い |
| b | **harness が cache を一次情報とみなす設計** | `main.py` に「一次情報は /workspace/cache のスナップショット + file_read、足りなければ Brave」とコメントされている |
| c | **ファイル更新時刻では鮮度を判定できない** | 毎ランの restore/save で mtime が当日になる（`s3 ls` は全ファイルが 2026-11-14 と表示）。判定材料は本文の `取得日時:` だけ |
| d | **prose の規則は拘束しない** | 「cacheを読むときは先頭の取得日時を必ず確認。今日以内でなければ3へ」は**既にプロンプトにあった**。守られていない |
| e | **検証不能な出力形式** | 自由文なので「提示された当日取得の一次情報によれば」という**虚偽の帰属**が通る。URLも取得日も要求していない |
| f | **衝突解決の規則が無い** | エンジニアは 11-14 の一次情報（blog 11-10 / pricing の行）を持っていたのに、レビューの critical を優先して削った |

まとめ: **古い証拠が「一次情報」として権威づけられ、新しい一次情報を上書きした**。
これはモデルの能力の問題ではなく、**証拠の供給経路の設計**の問題。

---

## 4. 解決案

**2026-11-14 に Phase 1〜6 を実装済み**（実装物と検証は §5.1）。以下は設計の記録。

### Phase 1 — 事実台帳 `data/facts.json`（追記の概念を消す）

1モデル1レコード。**1フィールド1値**しか入らない。

```jsonc
"gemini-4-carbon": {
  "provider": "Google",
  "names": {"ja": "Gemini 4 Carbon", "en": "Gemini 4 Carbon"},
  "status": "ga",                       // announced | preview | ga | retired
  "released": "2026-11-10",
  "price": {"in": 2.00, "out": 10.00, "in_from": 4.00, "out_from": 20.00, "from": "2026-12-01"},
  "cache": {"read": 0.10, "read_from": 0.20, "mode": "implicit"},
  "batch": "unsupported",
  "context": "未確認",
  "shown_on": ["/timeline/", "/pricing/", "/frontier-model-comparison/"],
  "sources": [{"url": "https://blog.google/...", "fetched_at": "2026-11-14",
               "quote": "Today, we're making Gemini 4 Carbon available to developers,..."}],
  "history": [{"date": "2026-10-28", "status": "preview", "note": "発表・限定提供"}]
}
```

- `status` を上書きすれば K6 は構造的に起きない
- ja/en は**同一レコードの別フィールド**。どちらかを正にして他を翻訳する方式は毎回ズレるので採らない
- `shown_on` が K7 を機械可読にする
- `history` は画面に出さない（表示は Phase 2 の changelog 生成へ）

### Phase 2 — 決定論レンダラ `tools/render_site.py`（LLM 0円）

| 生成物 | 解ける課題 |
|---|---|
| `/timeline/` `/en/timeline/`（`released` 降順でソート） | K5 |
| `/pricing/` 表・`/data/models.json`・トップ新着 | K7 |
| `/changelog/`（日英）＋トップに最新5件 | K8 |
| `sitemap.xml` / `llms.txt`（ja/en 両セクション） | 反映漏れ |

HTMLをLLMに書かせないので、出力トークンも減る（本日 エンジニア 40.6円/日の大半が24KB HTML生成）。

### Phase 3 — 整合ゲート `tools/check_facts_consistency.py`（`site_upload` に接続）

1. 生成HTMLの値 == 台帳の値
2. ja/en の**エントリ key 集合が一致**
3. timeline: `YYYY-MM-DD` 形式・降順・id 重複なし
4. **状態語の禁止**: `status != ga` に「GA」「一般提供」／`status == ga` に「学習中」「限定提供」
5. `sources` が空、または `fetched_at` が未来 → ERROR

### Phase 4 — 鮮度キュー（K2 の根本解決）

`sources[].fetched_at` が N 日超のものを毎朝「今日の再取得対象（最大5本）」としてミッション先頭に注入する。**URLは台帳が持つので人間に聞かない**。

新モデルの発見だけ別系統:

```
discover_sources(query)  → GPT Responses の web_search / Gemini grounding で「URL候補だけ」取る
fetch_quote(url)         → Firecrawl で逐語取得し quote を保存
upsert_fact(...)         → 台帳に1レコード
```

**grounding は URL 発見にだけ使う。答えの生成には使わない。** grounding の回答は引用が残らず検証できない（K3 と同じ失敗をする）。DeepSeek には grounding が無いので、GPT / Gemini に薄い `discover_sources` を持たせてエンジニアに配るのが最も安い。

### Phase 5 — レビューの格上げ条件（K3 の再発防止）

GPT税理士の返り値を JSON スキーマで受け、**`severity=critical` は `url` と `quote` が空なら自動的に `minor` へ降格**する。ここは運用ではなくコードで止める。

### Phase 6 — エビデンスパック（K3 の真因に対する本命）

Phase 5 は「怪しい指摘を捨てる」だけで、**古い証拠を読ませる経路自体**は残る。真因（§3.1）に対しては次を入れる。

1. **レビュー担当に `/workspace` を探索させない**。当日取得した `{url, fetched_at, quote}` の一覧（エビデンスパック）を**文字列で渡して**レビューさせる。古いcacheに触れなければ、古い結論は出てこない。
2. **取得したら必ず cache に書く**。`fetch_quote` が `cache/<key>-<today>.md` を書き、同キーの旧ファイルには `SUPERSEDED BY <new>` を1行追記する（または削除）。レビュー担当が読むものは常に最新1枚になる。
3. **衝突したら新しい方で決着させる**。レビューの指摘URLを再取得して一致しなければ指摘を棄却し、**棄却ログを残す**（＝GPTの誤指摘率が測れる）。
4. **鮮度は機械が判定する**。cache本文の `取得日時:` をパースし、当日でなければ「証拠として使うな」と機械が言う（LLMの自己申告に頼らない）。

---

## 5. TODO

### 5.1 本日実施

- [x] **T1** 本計画書を作成（この文書）
- [x] **T2** `/timeline/` を日付降順に再構築し、不正日付 `2026-10` を `2026-10-13` に修正、Qwen4 の誤クラス（`dot-anthropic`＋`Alibaba`）を `dot-other`＋Alibaba/Qwen に修正
- [x] **T3** `/en/timeline/` を再構築し、欠落5件（Muse Ember / Fable 5.2 / Carbon GA / Hydrogen / Qwen4-Max）を英訳して反映。さらに description の「Carbon は限定提供」という**本文と食い違う記述**を GA に修正
- [x] **T4** `/china-ai/` 日英の Qwen 4 二重記述を解消（日付付き追記ブロックを削除し、本文1箇所に統合。更新履歴に1行追加。EN は欠けていた 11-10 の Kimi 行も補完）
- [x] **T5** `/pricing/` `/en/pricing/` に Gemini 4 Hydrogen・Gemini 4 Carbon を追加
- [x] **T6** `/data/models.json`（計算機）に Hydrogen・Carbon を追加（49→51行）
- [x] **T7** 日付五点更新。あわせて `prompt-cache-pricing` 日英の `og:image` サイズ宣言（1424×752）を実ファイル（1200×630）に合わせた（既存の ERROR 2件）
- [x] **T8** `tools/check_facts_consistency.py` を追加し、S3 `akira-workspace/tools/` に配布
- [x] **T9** S3 アップロード＋CloudFront invalidation（`I3MA6CAA55EF0PHNE0W2GLPYFY`）＋ライブ検証
- [x] **T10** 恒久ルールを `site_plan` に追記（凍結の定義／critical の引用要件／日英同時性／反映先の事前列挙）
- [x] **T11** K3 の真因を実測で特定し §3.1 に記録（stale cache の再生であることを cache 本文との一致で確認）
- [x] **T12** レビュー証拠の供給規則を `site_plan` に追記（当日取得のエビデンスパックのみ／cache は当日分を必ず書く／`fetched_at` が当日でない指摘は棄却）
- [x] **T13 / Phase 1** `data/facts.json`（83レコード: timeline 54＋計算機のみ30）を作成。`status` / `released` / `price` / `sources` / `shown_on` を持つ。**文章はまだHTML側**（転記ミスでサイトを壊すリスクを避けるため段階移行）
- [x] **T14 / Phase 2** `tools/render_site.py` を追加。台帳から timeline の並び（日付降順・ja/en 同一順）・`data/models.json`・`/changelog/` `/en/changelog/`・sitemap lastmod を生成。**2回実行して0件＝冪等**を確認
- [x] **T15 / Phase 3** `tools.py` の `site_upload` に timeline 整合ゲートを組み込み。違反時は timeline の2ファイルだけアップロード拒否。**順序破壊・日付破壊・日英差分の3ケースで発火を確認**
- [x] **T16 / Phase 4** `tools/discover_sources.py`（Brave）と `tools/fetch_quote.py`（Firecrawl→cache に当日付で保存）を追加。**実呼び出しで Hydrogen の公式単価を取得→cache生成を確認**
- [x] **T17 / Phase 5** `main.py` に `_sanitize_review()`。引用（URL）の無いクリティカルの行を**機械的に軽微へ降格**。テスト3ケースPASS
- [x] **T18 / Phase 6** `main.py` に `_evidence_block()`。**当日取得の cache だけ**をレビュー依頼の先頭に前置きし、`gpt_tools` から `list_workspace_files` を外した（古い cache を探索できない）。`tools/evidence_pack.py` も配布
- [x] **T19 / デプロイ** イメージ再ビルド（import検品PASS）→ ECR `:latest`（digest `sha256:56d780ff…`）。**イメージ内で降格・エビデンス無し時の挙動・timelineゲートを実行確認**
- [x] **T20 / スケジュール** `cron(0 5 ? * TUE,THU,SAT *)` → **`cron(0 5 ? * SUN,TUE,THU,SAT *)`**（11-15 日曜を検証ランにする）
- [x] **T21** `/changelog/` `/en/changelog/` を公開（55件）。ただし専用OG画像は未生成（この環境にPillowが無い）→ **課題116**

### 5.2 次回以降（今日はやらない）

- [ ] Phase 1 の続き: 各エントリの**文章**を台帳へ移す（timeline の title/desc をJSONに持たせ、HTMLを完全な生成物にする）
- [ ] Phase 2 の続き: `/pricing/` の料金表も台帳から生成（今は表の手書きが残っている）
- [ ] Phase 3 の続き: `check_facts_consistency.py` を `site_upload` から呼ぶ（今は timeline の整合のみ内蔵）
- [ ] Phase 4 の続き: **鮮度キュー**（`sources[].fetched_at` が古い順に「今日の再取得対象」をミッション先頭に注入）
- [ ] **課題116**: `/changelog/` 専用OG（1200×630）。今はホームの画像を指している
- [ ] **課題115 の検証**: `cache/` に当日分が書かれるようになったかを 11-15 のランで確認（今は 11-05 で停止している）

補足: 凍結ルールは `prompts.py` ではなく `site_plan` 側にあった（`main.py` / `prompts.py` に「凍結」の記述は無い）。よって T10 の追記だけで今日から効く。**イメージ再ビルドが必要なのは Phase 5 だけ**。

---

## 6. 経過チェック観点（この案が正しいかを後で判定する）

### 6.1 計測の基準値（2026-11-14 実測。以後この数字と比べる）

| 指標 | 2026-11-14 |
|---|---|
| timeline エントリ数（ja / en） | 54 / 54（id 集合一致） |
| timeline の日付降順・形式 | 正常（不正日付 0件） |
| `/china-ai/` の Qwen 4 記述 | 本文1箇所（プレビュー開始を反映） |
| `/pricing/` の Hydrogen / Carbon | あり |
| `data/models.json` 行数 | 51 |
| `check_site_pages` | ERROR 0 / WARN 22 |
| `check_dates` | NG 0 / 88 |
| `check_facts_consistency` | ERROR 0 / WARN 3 |
| 　└ coverage（直近30日の反映漏れ） | 2件（Qwen4-Max-Preview, GPT-6 Cyber） |
| 　└ sot-drift | `price-sot.json` が 16日前 / 未収録 8件 |
| 　└ append-style（追記ブロックを持つページ） | 8件 |
| **GPTの critical 誤指摘率** | 1/1（11-14 の Carbon。一次情報で否定） |
| `/workspace/cache/` の最新 `取得日時:` | 2026-11-05 |

### 6.2 判定スケジュール

| 実施日 | 見るもの | 合格条件 | 不合格なら次に疑う仮説 |
|---|---|---|---|
| 2026-11-15（日曜・追加した検証ラン） | ①timeline ja/en の件数・順序 ②`/workspace/cache/` に当日分ができたか ③GPTのクリティカルにURLが付いたか ④`render_site` が呼ばれたか | ②が「当日」、③が全件引用付き、①が54件目以降も降順 | **Phase 6-1（エビデンスパック）が効いていない** |
| 2026-11-17（次のラン） | `/timeline/` と `/en/timeline/` のエントリ id 集合・日付順 | 差分0件・全日付が `YYYY-MM-DD`・降順 | H2（出現箇所の一覧が無い）が残っている |
| 2026-11-19（新しいモデルを乗せたラン） | 新規エントリの位置と `append-style` 件数 | 末尾追記が発生せず降順が保たれ、追記ブロックのページ数が 8件から増えない | **H1 が正しい**（＝HTMLが器のままでは直らない。Phase 2 を前倒し） |
| 2026-11-21 | `check_facts_consistency.py` の指摘件数 | ERROR 0 を維持し、WARN が本日の3件より減る | H6（検出しても直す仕組みが無い） |
| 2026-11-28 | `price-sot.json` の `last_verified` / 同一事実の矛盾 | 14日以内・状態語の矛盾0件 | H3（鮮度トリガーが無い） |
| 2026-12-01 | Carbon / Argon の価格が $4/$20 に切り替わったか | サイトが新価格を表示している | 期限付き価格の検知が手動のまま |
| 2026-11-21以降（GSC） | 修正ページの CTR・平均順位 | 改稿していない対照ページと比べて悪化していない | 改稿が順位を落とす（11-07 の3連敗と同じ） |
| 毎ラン | critical 指摘のうち `quote` 無しの件数 | 0件 | H4（引用要件が効いていない） |
| 毎ラン | critical のうち `fetched_at` が当日でない件数 | 0件 | Phase 6-1（エビデンスパック）が入っていない |
| 11-21〜 | **GPTの critical 誤指摘率**（一次情報で否定された数／critical総数） | 分母が増えても 0件 | レビュー担当を替えるか、レビューを「事実確認」から「価値判定」に限定する |
| 毎ラン | `/workspace/cache/` の最新 `取得日時:` | 当日（または前回ラン日） | 取得しても cache を書いていない（Phase 6-2） |

補足: 11-14 時点で **11-10 以降の一次情報が cache に1件も無い**。つまりレビュー担当は「9日前の世界」で判断している。これを直さない限り、引用要件を足しても同じ事故が起きる。

判定の作法: **数値で言える条件だけを合格条件に置く**。「良くなった気がする」は判定にしない。GSC は直近2〜3日が未着地なので、11-21 時点では 11-18 までの確定分で見る。

---

## 7. 前提が変わったときの要注意事項

| 前提 | 崩れた場合に設計がどう変わるか |
|---|---|
| 1日1〜2件の更新頻度 | 1日10件規模になると、手で台帳を直す前提が壊れる。`upsert_fact` の自動化（Phase 4）を先に完成させる必要がある |
| エンジニア = DeepSeek（1回の依頼で40〜80ツール） | 高性能モデルに戻すと「HTMLを直接書く」運用のコストが下がり、Phase 2 の優先度が下がる。ただし整合性の担保は台帳側にしかないので Phase 1 は省略不可 |
| 月予算 9,300円 | 予算が増えると検証回数（`directQuote` の5クレジット）を増やせる。減る場合は Phase 4 の鮮度キューを「週1回・5本」に絞る |
| 日本語＋英語の2言語 | 第3言語を足す場合、`names` / 本文フィールドが言語数だけ増える。台帳方式なら追加は機械的。HTML直書き方式なら破綻する |
| GPT税理士をレビューに使う | 別モデルに替えても Phase 5（quote必須）は必要。むしろレビュー担当が変わると過去の誤指摘の傾向が変わるので、判定ログを残す |
| okamo がURLを渡してくれる | 渡されなくなると Phase 4 が唯一の情報源になる。`discover_sources` が無いと新モデルの初動が遅れる |
| S3 バケットのバージョニング有効 | 無効化されると誤上書きの復旧手段が消える。`facts.json` は**ワークスペース側**に置き、公開バケットには生成物だけ置く |

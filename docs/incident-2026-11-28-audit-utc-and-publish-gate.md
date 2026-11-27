# 2026-11-28 朝のラン点検 — 監査が「未実施」と嘘をつく日付バグと、公開ゲートの外側

2026-11-28 05:11〜05:28 JST の定時ラン（`trace run_id=0511-268c1b`）の日報と
CloudWatch ログを点検して見つけた4件。すべて**コードで塞いだ**（判定をモデルの
注意力に預けない）。

| # | 事象 | 真因 | 打ち手 |
|---|---|---|---|
| 1 | 日報の自動メンテナンス欄が「ページ監査: **未実施 2件**（/claude-mythos-5-1/, /en/deepseek-v4-1-flash/）」と書いた。実際は両方監査して **ERROR 0 / WARN 0** | `page_audit` が `date.today()`（コンテナは UTC）で日付を作る。JST 05:00 のランでは**前日**になる。`main` は `datetime.now(JST)` の `today` で `assignments` を書き、`audit_pages` は UTC の日付で `last_run` を書くので、`verify_assigned` は**永久に一致しない** | `page_audit._today()`（JST）に統一。課題155（`render_site` の UTC バグ、11-17 修正）の同型がここに残っていた |
| 2 | 計算機データの「最後に公開した正常版」（修復の原資）が、**Law 混入の旧版59行**のまま残っていた | 公開経路が4本あるのに、契約ゲートとベースライン保存は**3本にしか無かった**。`publish_and_verify` は `s3.upload_file` 直呼び。今日 Akira はこの経路で `data/models.json` を公開した | `_gate_data_file()` に1本化。`publish_and_verify` も契約を通し、合格時のみベースラインを更新 |
| 3 | 11-26 に「業種別構成（for Law / for Healthcare）は計算機に入れない」と決めたのに、healthcare 2件が計算機データに混入（59→61）。描画の `write_back_shown_on` が「計算機に載っている」ことを根拠に `calculator` を**逆流**させ、除外設定を消していた | 決定を**文章にしか書いていなかった**。台帳の `shown_on` にもゲートにも無い | 公開契約（`validate_calculator_models`）に除外パターンを追加。`for Law` / `for Healthcare` を含む行は**どの経路でも公開できない** |
| 4 | `tools/` の CLIスクリプト4本が毎朝「@tool を付けた TOOL 変数が定義されていません」と警告されていた | ローダーが「ツールでないスクリプト」と「壊れたツール」を区別していない。意味のない警告が並ぶと、2026-11-15 の `site_upload` 欠落のような**本物のスキップが埋もれる** | @tool を1つも持たないファイルは静かに飛ばす。**@tool はあるのに解決できない／import に失敗した場合だけ** WARNING を出し、`workspace_tool_skips()` に残してミッション先頭に出す |

---

## 1. いちばん大きな1件 — 監査の日付が UTC だった

### 事象

日報の末尾（機械が書く欄）は次のとおり。

```
ページ監査: 未実施 2件（/claude-mythos-5-1/, /en/deepseek-v4-1-flash/）
```

同じ日報の本文は「必須監査 `/claude-mythos-5-1/`・`/en/deepseek-v4-1-flash/`、
追加で `/deepseek-v4-1-flash/` → ERROR 0 / WARN 0」と書いている。**同一の日報の
中で矛盾している。**

### 証拠

`/workspace/data/page_audit.json`（S3 復元）がこうなっていた。

```
assignments["2026-11-28"] = ["claude-mythos-5-1/index.html",
                             "en/deepseek-v4-1-flash/index.html"]
last_run = [
  {"page": "claude-mythos-5-1/index.html",      "date": "2026-11-27", "codes": []},
  {"page": "en/deepseek-v4-1-flash/index.html", "date": "2026-11-27", "codes": []},
  {"page": "deepseek-v4-1-flash/index.html",    "date": "2026-11-27", "codes": []}
]
```

`assignments` は **11-28**、`last_run` は **11-27**。`verify_assigned()` は
`date == today` で突き合わせるので、当日実施が0件に見える。

### 真因

`main.run_daily` は `today = datetime.now(JST).date().isoformat()` を作り、
`mission_line(today)` に渡す。一方 `page_audit` は `date.today()` を使っていた。
コンテナは UTC なので、JST 05:00（= UTC 前日 20:00）では `date.today()` が前日。

```
$ docker run --rm --entrypoint /app/.venv/bin/python <image> -c "..."
UTC date.today(): 2026-11-27
page_audit._today(): 2026-11-28
differs (JST vs UTC): True
```

これは**課題155 と同じ型**（`render_site.TODAY = date.today()` が JST 05:00 のランで
1日前になり、2026-11-17 に `datetime.now(JST)` へ直した）。`render_site` だけ直して
`page_audit` を残していたため、今度は逆方向（実施したのに未実施）に転んだ。

11-26 は「`last_run` を呼び出しごとに上書きしていた」ことで同じ欄が嘘をついた。
11-27 に当日分のマージで直したが、**日付そのものが食い違っていれば merge しても
一致しない**。

### 修正

`page_audit.py` に `_today()` を置き、`date.today()` の5箇所を置き換えた
（`note_changed` / `pick_targets` / `verify_assigned` / `audit_pages` /
`set_page_priority`）。

---

## 2. 公開経路が4本あって、ゲートは3本にしか無かった

### 事象

`data/models.json` の「最後に公開した正常版」＝ `akira-workspace/data/calculator-models.json`
は、公開中の58行ではなく **59行・`GPT-6.2 Astra for Law` 入り**だった。

```
$ aws s3 ls akira-workspace/data/calculator-models.json   # 05:26:44 JST に更新
$ md5sum v59(05:22:46に公開した版) baseline
46b81e9329f0d23f18d76ee33eeb35ee  v59
46b81e9329f0d23f18d76ee33eeb35ee  baseline
```

### なぜ危険か

- ベースラインは `_repair_contract_violations` → `restore_published_data_file()` の
  **復元元**。次に計算機データが契約違反になったら、ここから復元されて
  **Law 行が復活する**。
- 新しい契約（下記3）では、このベースライン自体が「業種別構成を含む」で違反に
  なる。復元は fail-closed（復元しない）ので、壊れたまま残る側に倒れる。

### 真因

公開経路は4本:

| 経路 | 契約ゲート | ベースライン保存 |
|---|---|---|
| `publish_file_to_site` | あり | あり |
| `site_upload` | あり | あり |
| `repair_calculator_fx` | あり | あり |
| **`publish_and_verify`** | **なし** | **なし**（`s3.upload_file` 直呼び） |

`publish_and_verify` は「1回の依頼で83回ツールを叩いていた」のを畳むために
2026-11-21 に足した経路で、そのとき `site_upload` 側の防御を移植し忘れた。
11-22 に site_events 登録の移植漏れ（＝更新履歴0件）を直したが、**データ契約と
ベースラインは残っていた**。

### 修正

`_gate_data_file(rel, local_path)` を追加し、`publish_and_verify` の
アップロード（HTML群・HTML以外の両方）が必ずこれを通るようにした。
`data/models.json` は契約を通らなければ **S3 に行かない**。合格時のみ
`_save_models_baseline()` が走る。データ側も、公開中の58行でベースラインを
上書きして揃えた。

---

## 3. 「文章で決めた」は効かない — 業種別構成をゲートにする

11-26 の決定: 「業種別構成（for Law / for Healthcare）は独立モデルIDで台帳に持ち、
**計算機には入れない**」。ところが台帳の `shown_on` には `calculator` が残り、
11-28 の描画で healthcare 2件が `models.json` に混入した（59→61）。
さらに `write_back_shown_on` が「計算機に載っている」ことを根拠に `calculator` を
**逆流**させ、除外設定そのものを消していた（Akira が同日中に発見・修正し、
`tests/test_render_models_json_gate.py` を「修正前実装で FAIL する」ことを実測して
から追加した）。

描画側のゲートは入ったが、**公開契約側には無かった**ので、別の経路（手書き・別ツール）
で混入すれば同じことが起きる。そこで `validate_calculator_models()` に
`CALC_EXCLUDED_NAME_PATTERNS = ("for law", "for healthcare")` を追加した。
契約違反は `check_published_contracts()`（C1）にも効くので、公開後の点検でも鳴る。

```
$ python -c "validate_calculator_models(公開中の58行)"  -> []
$ python -c "validate_calculator_models(旧ベースライン59行)"
["models[2].name='GPT-6.2 Astra for Law' は業種別構成（for law）。
  料金表・年表にだけ載せ、計算機には入れない決定（2026-11-26）"]
```

---

## 4. 「静かなスキップ」を止める

朝のログには毎回これが出ていた（4ファイル × 2回）。

```
[workspace] ツールのロードをスキップ: check_css_contract.py: @tool を付けた TOOL 変数が定義されていません
[workspace] ツールのロードをスキップ: check_page_shape.py: ...
[workspace] ツールのロードをスキップ: check_sections.py: ...
[workspace] ツールのロードをスキップ: check_site_integrity.py: ...
```

実体は `@tool` を持たない**CLIスクリプト**で、`self_check` が subprocess で叩く。
壊れてはいない。しかし 2026-11-15 は `site_upload` の `@tool` が1行消えたことを
この警告の山から見落とし、エンジニアが boto3 でバケット名を総当たりして
出力45kトークンを使った。**ノイズは本物の異常を隠す。**

修正: `@tool` を1つも持たないファイルは静かに飛ばす。`@tool` を持っているのに
`TOOL` を決められない／import に失敗した場合だけ WARNING を出し、
`workspace_tool_skips()` に残してミッションの先頭に出す。

---

## 5. その他（今回は直さないが記録）

- **stdout のバッファで時系列が壊れる**: 05:28:11 の「本日の運用終了」より後に
  05:28:12 の独白が並ぶ。さらに `logging.emit` で
  `BlockingIOError: [Errno 11] write could not complete without blocking` が起き、
  「ワークスペース保存」の行が1件失われた。→ Dockerfile に `PYTHONUNBUFFERED=1`。
- **受領書がまだ通称**: 3件とも `DONE: <通称>` で返り、機械が「書式違い」で解釈した。
  判定は成立しているが、モデルの注意力に依存している（課題58）。
- **WARN 317（site_pages 35 / page_shape 281）**: 「既知の積み残し」として緑に
  混ざっている。棚卸しを site_plan の課題に立てた。
- **`MCP接続が切れたままだったので作り直します（Claudeエンジニア）` が同一秒に3回**:
  共有MCP（brave / firecrawl / github）の数だけ出る。11-24 の「初期化だけ直列化」
  は効いていて、作り直した後にエンジニアは 38 ツールで完走している。**異常ではない**
  が、3行並ぶと異常に見える（同じくノイズ）。

---

## 6. 検証

`test_regression_20261128.py` **38/38 PASS**（ネットワーク・AWS・LLM不要）。

- 監査: 壊れた状態（`last_run` がUTC日付）なら「未実施」になる＝テストが11-28の
  嘘を捉えている／直したコードは `last_run` をJSTで書き「実施済み」になる／
  翌日は「割当なし」（前日の実施を数えない）
- 公開経路: 業種別構成を含む models.json は**公開拒否・S3に行かない・ベースライン
  も書かない**／正しい内容は公開されベースラインが公開版で更新される／
  **ゲートを外した旧経路では公開できてしまいベースラインも古いまま**（穴の再現）
- 契約: `for Law` / `for Healthcare` を検出、正しいデータは合格。
  **C5（台帳のGAモデルが公開中にあるか）は同種を除外する**（C1 が公開を拒否する
  以上、C5 が「無い」と叫ぶと永久に直せない違反になる）
- ローダー: CLIスクリプトは静か、TOOL未定義の異常だけ残す
- 規約の置き場所: title/description 凍結が**エンジニアのプロンプトにも**ある
  （SITE_RULES だけでは実行者に届かない）
- 配線: ミッションのプレースホルダが壊れていない、スキップ0件なら空文字

既存回帰も ALL PASS: 11-19 / 11-21 96/96 / 11-22 20/20 / 11-24 8/8 / 11-27 35/35。

イメージ内でも確認（`page_audit._today()` が JST、`CALC_EXCLUDED_NAME_PATTERNS`、
`_gate_data_file`、`_workspace_tool_skip_line` が生きている）。

## 7. デプロイ

ECR `akira:latest` digest `sha256:f075e749c4509b2afd12b0ee84a86640e45823d6a8a30837c097ece9d1abcc78`
（タスク定義 `akira-daily:23` は `:latest` 参照なので更新不要）。
ベースライン `akira-workspace/data/calculator-models.json` を公開中の58行で上書き
（md5 一致を実測）。

再実行（下記9）を回した時点のイメージは `sha256:20a9edf1…`。その後に足した
「C5 が業種別構成を叫ばない」ガード・「凍結規約をエンジニアのプロンプトへ」・
「出力の伏字（output_guard / redact_rules）」は `sha256:f075e749…` に含まれ、
次回の定時ラン（11-30 05:00）から効く。

## 8. 原則（§4 の核に足す）

- **時刻で突き合わせる検査は、書く側と読む側が同じ時計を使っているかを見る**。
  「マージしたのに一致しない」ときは、まず日付そのものを疑う。
- **公開経路を増やしたら、その経路が既存の防御を通るかを1行ずつ確かめる**。
  経路が4本あればゲートも4本要る。1本化できるなら1本にする。
- **決定はデータとゲートに書く**。文章（lessons / site_plan）は次に描画した瞬間に
  上書きされることがある。
- **規約は「実際に手を動かす人」のプロンプトに置く**（2026-09-05 の原則）。
  title/description 凍結は SITE_RULES（Akira側）にしか無く、**title を書き換える
  のはエンジニア**だった。11-28 の再実行で EN 14ページの title が短縮された。
  → `CLAUDE_ENGINEER_PROMPT` の「編集の鉄則」へ移した（両方に置く）。
- **意味のない警告を出し続けない**。ノイズは異常を隠す（11-15 の再発防止）。

---

## 9. Fargate の Akira に自律的に直させた（07:06〜07:30 の再実行）

修正イメージを `:latest` に置いたうえで、`--no-publish` を付けずに1回だけ
`run-task` した。**依頼文は書いていない**（site_plan に「今回わかったこと」を
追記し、そこから Akira に選ばせた）。これが「自律的に直す」の実体。

```
task/akira/19bfe2ca106447a7b6f7592cde3edad1  07:06:41 → 07:30:15（23分34秒）
exit 0 / run_id=0706-b71ecf / 本日累計 168.1円（朝のラン 72.0円 ＋ 本ラン 約96円）
```

| 項目 | 結果 |
|---|---|
| 機械側の検証 | **修正が実機で効いた**: 日報の機械欄が「ページ監査: **2ページ実施済み**（/gpt-6-1-sol/, /en/multimodal/）」。朝と同じ日・同じラン種別で「未実施」が消えた |
| ツール読込のノイズ | ログの `ツールのロードをスキップ` は**朝の8行のみ**。再実行は0行 |
| 委任（自律選択） | `GPT61SOL-FRESH`（/gpt-6-1-sol/ のキービジュアル欠落・`</ul>`外の裸`<li>`・10-09で止まった日付）／`WARN-TRIAGE-14`（WARN 37→1）／`GEMINI31FL-FRESH`（76日ぶりの鮮度更新）。3件とも DONE |
| 副作用（正直に記録） | 依頼文に凍結を書かなかったため、エンジニアが **EN 14ページの title を短縮**した。Akira は戻さず CTR・imp・順位で14日後に判定すると日報に書いた。→ 規約をエンジニアのプロンプトへ移した（§8）。 |
| 残った課題 | 受領書が今回も `DONE: <通称>`（課題58）。機械は拾えたが、判定がモデルの注意力に依存している |

なお `WARN 37→1` は Akira の報告値。`site_pages` の WARN が「既知の積み残し」と
して緑に混ざる状態は、この棚卸しでかなり減った。

---

## 10. 再実行中に見つかった**セキュリティ事故**（APIキーのログ流出）

### 事象

07:17:05、Claudeエンジニアが `env` を実行し、**`OPENAI_API_KEY` の実値をツール結果に
載せた**。その結果は strands の callback で stdout に書かれ、CloudWatch Logs
（`/ecs/akira`）に**平文で残った**。Akira 自身も次のターンで
「I just leaked an API key into the transcript by running `env | grep`」と気づいている。

```
2026-11-28 07:17:05  OPENAI_API_KEY=sk-proj-（実キー。ここでは伏せています）
```

### なぜ止まらなかったか

- 伏字（`trace_store.redact`）は **trace の記録にしか掛かっていなかった**。
  実際、同じターンの trace 本文（`00716-tool.result.json`）には鍵は残っていない。
- ところが **stdout / stderr は素通し**。CloudWatch にはそちらが流れる。
- プロンプトにも「`env` を叩くな」と書いていなかった（規約が無かった）。

### 打ち手（デプロイ済み）

1. `output_guard.py` を追加し、`main()` の冒頭で `install()`。
   `trace_store.redact()` を **sys.stdout / sys.stderr の write** と
   **logging のレコード（msg と args）**に通す。既存の伏字パターン
   （`sk-` / `AIza` / `ghp_` / `AKIA` / Bearer / `api_key=…` / 秘密鍵）がそのまま効く。
   実測: `KEY=sk-proj-ABC…` → `KEY=sk-***`。
2. `CLAUDE_ENGINEER_PROMPT` に「`env` / `printenv` / `set` / `export -p` を実行しない。
   値を見たいときは長さだけ見る」を追加（**出さないのが原則**、伏字は最後の網）。
3. リポジトリにコミットする `cloudwatchlog/2026-11-28.txt` は該当行を伏字に置換した
   （push 時に GitHub の Push Protection が `OpenAI API Key` として検出して
   ブロックしたため。検出された以上、**公開リポジトリに history を残さない**）。
4. **伏字の定義を1箇所に集約**（`redact_rules.py`）。同じ `REDACT` が
   `trace_store.py` と `scripts/publish_trace.py` に二重管理されていたので、
   trace 記録・公開JSONL・stdout/logging・**ログDL** が同じパターンを使う形にした。
5. **`cloudwatchlog/fetch_log.sh` は保存前に伏字を通す**
   （`jq` の出力を `redact_rules.py` にパイプし、保存後に `sk-` 等が残っていないかを
   毎回検算して、残っていれば**失敗させる**）。実測: 2026-11-28 のログ 8,951 行を
   再取得して伏字後 0 件・行数は不変。

### 残る対応（okamo にしかできない）

- **OpenAI の API キーをローテーションしてください。** CloudWatch Logs には
  07:17:05 の生ログが残っています（ロググループの保持期間中）。S3 の trace 本文には
  残っていないことを確認済み。新キーは Secrets Manager
  （`okamo-channel/secrets`）の `OPENAI_API_KEY` を書き換えるだけで反映されます
  （タスク定義の更新は不要）。
- **2026-11-28 07:53 に `okamo-channel/secrets` が更新済み**（`OPENAI_API_KEY` は
  新キーに差し替わっている。キー名は変わらず `OPENAI_API_KEY`）。タスク定義の
  `environment` に鍵は無く `SECRET_ARN` だけなので、**再起動すれば新キーが使われる**
  （イメージ再ビルドもタスク定義更新も不要）。

### GitHub に残っていないかの確認（実測）

- 一度 push した `41c66ae` には、**テストのダミーとして実キーを貼ってしまっていた**
  （伏字のテストを書くときに実物をコピーした）。これを `reset --soft` で作り直し、
  `--force-with-lease` で `main` を差し替えた（現在の `main` は `2308a44`）。
  ダミーは `"sk-" + "proj-" + …` と**実行時に組み立てる**形にして、ソースに
  連続した鍵文字列を作らない。
- 全コミット（`git rev-list --all`）を再走査して、実キーの断片すら **0件**
  （確認コマンドのパターンは `sk-proj-` までにして、断片を文書に残さない）。
  `git ls-remote` の `refs/heads/main` も差し替え後の SHA。
- ただし GitHub は**未到達になったオブジェクトを SHA 直指定でしばらく保持する**
  （`/commits/41c66ae…` が 200 を返すことを確認）。キーはローテーション済みなので
  実害は無いが、**完全削除したい場合は GitHub サポートに purge を依頼する**のが
  唯一の手段（リポジトリ削除以外では利用者側で消せない）。
- 同種の確認: `ANTHROPIC` / `GEMINI` / `DEEPSEEK` / `BRAVE` / `FIRECRAWL` / `GITHUB`
  のキーは、同日のログに現れていない（grep で0件）。

### 原則（§8 に足す）

- **「記録には伏字がある」は「出力には伏字がある」ではない**。秘匿情報の通り道を
  数えるときは、trace・DynamoDB・S3・**stdout / CloudWatch**・日報を別々に数える。
- **規約（プロンプト）と網（コード）を二重にする**。網だけだと気づかないまま漏れ続け、
  規約だけだと破られる。

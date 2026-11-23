# 2026-11-24 Claudeエンジニアが起動しない（共有MCPの同時起動レース）

## 1. 事象

2026-11-24（火）05:00 JST の定時ランで、**Claudeエンジニアが一度も起動しなかった**。
サイトの健全性（公開契約・self_check・ページ監査）はすべて ERROR 0 で、Akira本体は
日報まで到達している。壊れたのは「委任先を組み立てる」段階だけ。

```
05:14:08 ERROR | strands.tools.mcp.mcp_client | error=<the client session is currently running> | failed to start MCP client
05:14:08 ERROR | strands.tools.registry    | tool_name=<<MCPClient object at 0x7fe742e68890>> | failed to load tool
05:14:08 WARNING | akira | Claudeエンジニア のAgent生成に失敗（ValueError: Failed to load tool
          <MCPClient ...>: Failed to start MCP client: the client session is currently running）。
          MCPを作り直して1回だけ再試行します
05:14:08 ERROR | akira | Claudeエンジニア のAgent生成に再試行しても失敗（同じ例外）
05:14:25 （Gemini子育てママの視認結果が返る＝この時刻まで並列で動いていた）
```

同じ秒に2回失敗し、**同じオブジェクト**（`0x7fe742e68890`）で落ちている。
「接続が死んだ」のではなく「起動中のものをもう一度起動した」形。

被害: 本命だった `qwen4-max-preview` の3面反映（11/25 期限）が未実施。台帳ズレ4件の
解消（描画）も一緒に流れた。日報には「エンジニアが起動できなかった」と記録され、
site_plan の1番に持ち越された（Akiraの判断自体は規定どおり）。

## 2. 原因（ログと strands の実装から）

Akira は 05:13:49 の思考で「エンジニア依頼を先に投げて、その間に Gemini 視認を並行
させる？ 依存関係なし。並列でOK」と判断し、`ask_claude_engineer` と
`ask_gemini_mother` を**同じターンで並列に**呼んだ。

brave / firecrawl の MCPClient は委任先3AIで**共有**している。strands の
`MCPClient.load_tools()` はこうなっている:

```python
if not self._tool_provider_started:
    self.start()                      # ← 起動（サーバープロセスを立てる）
    self._tool_provider_started = True  # ← フラグが立つのは「起動完了後」
```

`start()` は `if self._is_session_active(): raise MCPClientInitializationError(
"the client session is currently running")` で二重起動を拒否する。背景スレッドは
起動した瞬間から生きているので、**2つのスレッドが同時に Agent を生成すると、
後から入った方は「起動中のセッション」を見て必ず落ちる**。

```
thread A: load_tools → _tool_provider_started False → start() ──(起動中)──> True
thread B: load_tools → _tool_provider_started False → start() → 例外
          （A が True を立てる前なので、B からは「未起動」に見える）
```

### 既存の再発防止が効かなかった理由

2026-11-17 の対策 `_revive_dead_mcp()` は「started なのに session が死んでいる」状態
だけを扱っていた。

```python
if not getattr(c, "_tool_provider_started", False):
    continue          # ← 未started は "正常" とみなして素通り
```

今回の状態は「**未started かつ session 生存（＝他スレッドが起動中）**」で、3つ目の
状態だった。素通りした結果、再試行も同じ `start()` に突っ込み、同じ秒に同じ例外で
落ちた。リトライは「原因が解消する経路」を持っていなかった。

## 3. 修正

### 3-1. Agent生成（＝MCP起動）の直列化

```python
_MCP_INIT_LOCK = threading.RLock()   # main.py

with _MCP_INIT_LOCK:
    _revive_dead_mcp(_shared_mcp, name)
    agent = make_agent()             # ← ここで MCP が起動する
```

Akiraは複数の委任を並列に投げられるが、**生成だけ**を直列化する。2人目は起動済みの
ツールを再利用するので、依頼の実行そのものは並列のまま（待ち時間は増えない）。

### 3-2. `_revive_dead_mcp()` を3状態で判定

| 状態 | 判定 | 動作 |
|---|---|---|
| started かつ session 生存 | 正常 | 何もしない |
| started だが session 死亡 | 接続切れ（2026-11-17 の型） | `stop()` で初期化し、次の `load_tools` で起動させる |
| **未started かつ session 生存** | **他スレッドが起動中** | **`stop()` しない**（相手の道具を殺す）。起動完了を最大180秒待つ |

待つのは「相手が立ち上げたMCPサーバーを、自分が落とさない」ため。`stop()` を呼ぶと
`_consumers` も消えるので、常駐consumer（keepalive）も失われる。

## 4. 検証

`test_regression_20261124.py`（8項目・ネットワーク/AWS/LLMなし）

| # | 検査 | 結果 |
|---|---|---|
| 1 | 直す前のコード（直列化なし＋起動中を待たない）では `起動できず` が出る＝**テストが壊れ方を再現できている** | PASS |
| 2 | ロック有りでは2人とも生成でき、共有MCPの `start()` は1回ずつ | PASS |
| 3 | 「起動中」のクライアントを `stop()` しない（待って復旧0件） | PASS |
| 4 | 「起動済みだが死んでいる」クライアントは従来どおり `stop()` して作り直す＋keepalive再付与 | PASS |

- 既存の回帰テスト: `test_regression_20261119.py` ALL PASS / `20261121.py` 96/96 /
  `20261122.py` 20/20
- イメージ内（Python 3.12）でも 8/8 PASS。Dockerfile の import 検品
  （`budget, config_store, prompts, report, settings, tools, main, page_audit, og_card, trace_store`）も通過

## 5. デプロイ

- ECR `akira:latest` digest `sha256:1c45cd9d480a95f4452d257120938ff50d306b26c0d0af5801421bfda7b64564`
- タスク定義 `akira-daily:23` は `:latest` 参照のため**更新不要**
  （スケジュール `cron(0 5 ? * SUN,TUE,THU,SAT *)` / Asia/Tokyo / ENABLED は不変）

## 6. Fargateでの自律的なやり直し

定時ランで落ちた作業（`qwen4-max-preview` の3面反映と台帳ズレの描画）を、
修正済みイメージのFargateタスクでAkiraに**そのまま再開させる**。

```
aws ecs run-task --cluster akira --task-definition akira-daily --launch-type FARGATE \
  --network-configuration '{"awsvpcConfiguration":{"subnets":["subnet-0c90b7ed8de4233e3"],
    "securityGroups":["sg-01d6b6ef85b437cdf"],"assignPublicIp":"ENABLED"}}'
→ task/akira/efc1ec2553a940acb51b2d3510d112fd
```

同一ランの再実行なので、日報（`2026-11-24`）は上書きされる。site_plan の1番に残した
項目をAkira自身が拾うため、依頼文の再設計は不要。

### 結果（06:13:45〜06:32:38 JST / exit 0 / 1ラン約199.2円）

| 検査 | 結果 |
|---|---|
| Claudeエンジニアの起動 | **3回とも成功**（ツール実行 100回 / 76回 / 9回、合計約153.9円）。`起動できず` 0件 |
| 既存の復旧経路 | 「MCP接続が切れたままだったので作り直します」4回（Gemini実行時）→ いずれも復旧して成功 |
| 台帳ズレ | 開始時4件 → 終了時 **0件** |
| ゲート | 公開契約 違反0件／`self_check` 全ゲート ERROR 0 |
| 日報 | 75件を再公開（同日の日報は第2ランの内容に更新） |
| 公開物 | `/glm-5-3-flash/` ja/en の全面刷新、GLM-5.4 を `/timeline/` ja/en・`/china-ai/` に反映、Newバッジ撤去。`/changelog/` 11-24 に3件 |

Akiraは site_plan を自分で読み、**こちらの依頼文を作り直さなくても**作業を再開した。
選んだのは72日停止していた `/glm-5-3-flash/` と、料金ページに載らないため見張りに
映らなかった GLM-5.4（課題196）。`qwen4-max-preview` は台帳と `/pricing/`
（Qwen4-Max 行）に掲載済みであることを実測したうえで後回しにしている。

「FargateのAkiraに自律的に直させる」の実体は、**ハーネスが壊れた原因を取り除けば、
既存の判断ループ（site_plan → 企画 → 委任 → ゲート → 日報）がそのまま回る**こと。
今回の再実行はその確認になった（作業内容の選択はAkiraの裁量で、こちらは指定していない）。

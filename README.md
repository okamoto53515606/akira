# Akira — AI/LLM実用データハブ運営エージェント

Akira（`claude-fable-5`）が毎朝 AWS Fargate 上で自律起動し、「AI/LLM実用データハブ」サイト
[llm.okamomedia.tokyo](https://llm.okamomedia.tokyo/) を広告なしで運営し続けるためのバッチシステムです。
リサーチ・作業指示・レビュー・GA4/Search Console分析・日報公開までを毎日自動で行い、
運営者の okamo には日報を通じて依頼事項を伝えます。

## ●プロジェクト概要

- **ミッション**: 広告なしの「役に立つ」静的サイトを毎日更新し、PVを上げることのみ。収益化は目的にしない
- **サイト内容**: 主要LLM API（Anthropic Claude / OpenAI GPT / Google Gemini）のトークン料金比較、
  モデル情報を一次情報（各社公式ページ）ベースで随時更新するデータハブ
- **運営体制**: Akira自身はFargateタスク内で「リサーチ・指示・レビュー」に徹し、実作業は同一プロセス内で
  strandsのマルチエージェントとして同居する3人のAI（**Claudeエンジニア**=記事執筆・コーディング・
  S3公開、**GPT税理士**=価値・PV貢献とfactチェックの2軸で助言するアドバイザー、**Gemini子育てママ**=
  画像生成・初心者目線のUXレビュー）に「依頼する」という舞台設定で進行する
- **GPT税理士の立ち位置**: 公開可否を決める「門番」ではなく助言役。クリティカルな問題（明確な誤情報・
  法的リスク・アダルト/犯罪関連）以外で公開を止めることはなく、軽微な指摘は「課題」として記録し
  翌日以降に検討する（掲載情報の品質基準自体は下げない）
- **日報**: 実行結果は [akira.okamomedia.tokyo](https://akira.okamomedia.tokyo/) にHTML日報として一般公開し、
  okamoへの依頼事項があれば必ず記載する。okamoはDynamoDB上のコメント欄に直接返信できる
- **予算ガード**: LLM費用（AWS実行費は含まない）はハードリミット月額9,300円のみ。使い切ったら当月停止し
  翌月自動再開する

## ●経緯と時系列の説明

2026年7月2日夜、okamoからの1通の依頼メッセージから一晩でゼロから構築・公開まで進んだプロジェクトです
（詳細な全会話ログは [prompt_history/20260702-claude-fable-5.txt](prompt_history/20260702-claude-fable-5.txt) に記録）。

| 日時（JST） | 出来事 |
|---|---|
| 2026-07-02 22:00 | okamoより「AIが自律運営する広告なしお役立ちサイト」構築の依頼。Akiraのミッション・3AI体制の原案を提示 |
| 2026-07-02 22時台 | サイト方向性を「AI/LLM実用データハブ」に決定。サブドメイン `llm.okamomedia.tokyo` / 日報 `akira.okamomedia.tokyo` をAkiraが決定 |
| 2026-07-02 22〜23時台 | AWS基盤を構築: S3（サイト+日報バケット）、ACM証明書リクエスト、DynamoDB 3テーブル、IAMロール（`AkiraTaskRole`）、CloudFront 2ディストリビューション（OAC経由） |
| 2026-07-02 23時台 | okamoがムームードメインでCNAMEレコードを設定 → ACM証明書発行 → 独自ドメインでの疎通確認完了 |
| 2026-07-02 深夜 | Akiraエージェント本体（`main.py` ほか）をstrandsマルチエージェント構成で実装。channelの実装パターンを参考にしつつ、channelとはSecrets Manager共有のみの疎結合として設計 |
| 2026-07-02 深夜〜07-03未明 | Dockerfile作成、ECR/ECSクラスター・タスク定義、EventBridge Scheduler（毎朝6:00 JST）を構築。初回Fargate実行で失敗→CloudWatchログ調査→修正 |
| **2026-07-03 00:30** | 初回 `git commit` & `git push`（GitHubリポジトリへ初公開）。トークン単価誤り・累積計上バグなどの教訓もコミットメッセージに記録 |
| 2026-07-03 未明 | サイト本公開（Coming Soon状態を解除しトップページ・料金比較ページを公開）、GA4/Search Console/BigQueryエクスポートの疎通確認 |
| 2026-07-03 以降 | 毎朝6:00 JSTの自動運用が稼働開始。Claudeエンジニアのモデルを`claude-sonnet-5`（導入価格）へ切替、予算ルールを「月9,300円のみのハードリミット」に確定するなど、日報経由でokamoと調整を継続中 |

## ●AWS構成の概要

すべて `us-east-1` リージョン。命名規則は `akira-` プレフィックスで、既存の「okamoちゃんねる」システムとは
Secrets Manager共有のみの疎結合。

| レイヤ | リソース | 役割 |
|---|---|---|
| 配信 | S3 (`akira-llm-site` / `akira-reports-site`, 非公開) + CloudFront（OAC経由）+ ACM証明書 | LLM Data Hubサイト / Akira日報サイトの静的配信 |
| 実行基盤 | ECR (`akira`) / ECS Fargateクラスター (`akira`) / タスク定義 (`akira-daily`, 1vCPU・2GB) | Akiraエージェント本体の日次バッチ実行 |
| スケジューラ | EventBridge Scheduler（`cron(0 6 * * ? *)`, Asia/Tokyo） | 毎朝6:00 JSTにFargateタスクを自動起動 |
| データ | DynamoDB（`akira-usage` トークン/費用記録、`akira-reports` 日報+okamoコメント、`akira-config` システムプロンプト/skills/site_plan） | コスト管理・日報・自己改善ループの永続化 |
| 権限 | IAM（`AkiraTaskRole` タスクロール、`AkiraExecutionRole` 実行ロール、`AkiraSchedulerRole` スケジューラ用） | 最小権限でのS3/DynamoDB/Secrets/CloudFront invalidation/RunTask |
| シークレット | Secrets Manager（`okamo-channel/secrets-*`, channelと共有） | LLM各社APIキー・GitHub PATなどをランタイムで取得（イメージには含めない） |
| ログ | CloudWatch Logs (`/ecs/akira`, 30日保持) | Fargateタスクの実行ログ |
| 分析 | GA4（llm用・akira用の2プロパティ）+ Search Console → BigQueryエクスポート（Workload Identityでキーレス接続） | 前日PV・検索クエリの確認 |
| その他 | CloudFront Function（`akira-index-rewrite`） | サブディレクトリURL（例 `/pricing/`）のindex.html自動解決 |

## ●利用言語やライブラリの概要説明

- **言語**: Python 3.12（[pyproject.toml](pyproject.toml) は `requires-python = ">=3.10"`）
- **パッケージ管理**: [uv](https://docs.astral.sh/uv/)（`uv sync` / `uv run`）
- **エージェントSDK**: [strands-agents](https://pypi.org/project/strands-agents/)（`anthropic` / `openai` / `gemini` extra）+ `strands-agents-tools` — Akira本体と3AIをagent-as-toolパターンで実装
- **MCP（Model Context Protocol）**:
  - Brave Search MCP（`@brave/brave-search-mcp-server`, Node.js/npx経由）でWebリサーチ
  - GA4 MCP（`analytics-mcp`, uvx経由）でGA4データ取得
  - BigQuery MCP（MCP Toolbox `--prebuilt bigquery`）でSearch Consoleエクスポートデータ取得
  - いずれもGCP Workload Identity（AWS→GCPキーレス連携）で認証
- **AWS SDK**: `boto3`（S3 / DynamoDB / Secrets Manager / CloudFront）
- **その他**: `python-dotenv`（ローカル`.env`読み込み）、`google-genai`（Gemini画像生成）
- **コンテナ**: `python:3.12-slim` ベース + Node.js 22（npx用）+ `uv`/`uvx` + MCP Toolboxバイナリ（[Dockerfile](Dockerfile)）

## ●利用llmの概要説明

| 役割 | モデル | 用途 |
|---|---|---|
| Akira本体 | `claude-fable-5`（Anthropic, $10/$50 per 1Mトークン） | リサーチ計画・3AIへの作業依頼・GA4/BigQuery分析・日報執筆 |
| Claudeエンジニア | `claude-sonnet-5`（Anthropic, 導入価格 $2/$10、2026-08-31まで。以降$3/$15に自動切替） | 記事執筆・コーディング・S3への公開作業 |
| GPT税理士 | `gpt-5.4`（OpenAI, $1.25/$10） | 価値・PV貢献の助言とfactチェック（門番ではなくアドバイザー） |
| Gemini子育てママ | `gemini-3.5-flash`（テキスト, $0.30/$2.50）/ `gemini-3.1-flash-image`（画像生成, $0.30/$2.50 + 画像$0.05/枚） | OGP・記事画像の生成、初心者目線のUXレビュー |

料金・モデルIDは [settings.py](settings.py) の `MODEL_PRICING_USD` で一元管理し、[budget.py](budget.py) が
DynamoDB (`akira-usage`) への記録と月次予算ゲートを行う。

## ●AWSへのデプロイ手順

実際に一晩で行った構築手順（[main.py](main.py) 等の実装後）を整理したものです。既存リソース名・IDは
アカウント固有のため、実施時は適宜置き換えてください。

1. **AWS CLI設定**: `export AWS_PROFILE=okamo`（管理権限）、リージョンは `us-east-1`
2. **S3バケット作成**: `akira-llm-site` / `akira-reports-site` を作成し、Block Public Access を有効化（非公開）
3. **CloudFront Origin Access Control (OAC)** を作成し、両バケットへS3バケットポリシーでCloudFrontのみ許可
4. **ACM証明書**（us-east-1固定）: `llm.okamomedia.tokyo` + SAN `akira.okamomedia.tokyo` をDNS検証でリクエスト
5. **DNS設定**: ムームードメインの管理画面でACM検証用CNAME、サイト用CNAME（各CloudFrontドメイン）を追加 → 証明書がISSUEDになるまで待機
6. **CloudFrontディストリビューション**を2つ作成（llmサイト用・日報サイト用）。証明書発行後、`Aliases` と `ViewerCertificate` を更新して独自ドメインをアタッチ
7. **CloudFront Function**（`akira-index-rewrite`, viewer-request）を作成し両ディストリビューションに適用してサブディレクトリの `index.html` を解決
8. **DynamoDBテーブル作成**: `akira-usage` / `akira-reports` / `akira-config`（すべて `pk`+`sk`, PAY_PER_REQUEST）
9. **IAMロール作成**: `AkiraTaskRole`（ECSタスク用、S3/DynamoDB/Secrets/CloudFront invalidation最小権限）、
   `AkiraExecutionRole`（ECS実行ロール、`AmazonECSTaskExecutionRolePolicy`）、`AkiraSchedulerRole`（EventBridge SchedulerからのRunTask用）
10. **ECRリポジトリ作成**とイメージビルド・push:
    ```bash
    aws ecr create-repository --repository-name akira --region us-east-1
    aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
    docker build --platform linux/amd64 -t <account>.dkr.ecr.us-east-1.amazonaws.com/akira:latest .
    docker push <account>.dkr.ecr.us-east-1.amazonaws.com/akira:latest
    ```
11. **CloudWatch Logsロググループ** `/ecs/akira`（保持30日）を作成
12. **ECSクラスター** `akira` と **タスク定義** `akira-daily`（1vCPU/2GB, 上記ロールを指定）を登録
13. **EventBridge Scheduler**で `cron(0 6 * * ? *)`（Asia/Tokyo）のスケジュールを作成し、ECS RunTaskをターゲットに設定
14. **初回動作確認**: `aws ecs run-task` で手動起動し、CloudWatch Logsでエラーがないか確認（初回は例外発生→ログ調査→修正→再デプロイのサイクルを実施）
15. **GA4 / Search Console / BigQueryエクスポート設定**（GCPコンソール側の操作）はokamoが実施し、
    プロパティID・データセット名をAkiraのシステムプロンプト（`config_store.py`）に反映
16. 以降の運用: 日報・DynamoDB経由でシステムプロンプトやモデル設定を調整し、`docker build && docker push`
    → 新タスク定義リビジョン登録 → スケジューラのターゲット更新、というサイクルで継続的にデプロイ

ローカルでの動作確認は以下の通りです。

```bash
cp .env.example .env   # 値を埋める（AWS_PROFILE等ローカル専用の値は各自追加）
uv sync
uv run python main.py --dry-run   # 公開せず計画のみ出力
```

## ●運用中のサイトの説明とリンク

### LLM Data Hub — <https://llm.okamomedia.tokyo/>

主要LLM APIの料金・モデル情報を一次情報のみで掲載する、広告なしのデータハブです。

トップページ:

![LLM Data Hub トップページ](docs/screenshot/top.png)

料金比較ページ（`/pricing/`）:

![LLM Data Hub 料金比較ページ](docs/screenshot/pricing.png)

### Akiraの日報 — <https://akira.okamomedia.tokyo/>

Akiraが毎朝の作業内容・費用・GPT税理士のレビュー・okamoへの依頼事項を公開するHTML日報です。

![Akira日報（2026-07-02）](docs/screenshot/akira-report-2026-07-02.png)

## ●運営メンバー（3人のAI）の関連プロジェクトの説明とリンク

Akira自身は3人のAI（Claudeエンジニア・GPT税理士・Gemini子育てママ）に作業を「依頼する」という舞台設定で
動いていますが、この3人は元々okamoが開発した別システムのキャラクターです。

- **okamoちゃんねる** — <https://github.com/okamoto53515606/channel>
  AI3人（Claude / GPT / Gemini）が [okamoのhomepage](https://www.okamomedia.tokyo/) の記事を
  2ちゃんねる風BBSで辛口レビューする自律議論システム（strands GraphBuilderによる4ノード固定チェーン）。
  公開サイト: <https://channel.okamomedia.tokyo/>
- **SASTちゃんねる** — <https://github.com/okamoto53515606/sast-channel>
  同じ3キャラクターが今度は「コードレビュー版」として、GitHubリポジトリを自律的にレビューし、
  Issue起票・修正ブランチ作成・PR作成までを自動で行うキャラクター駆動型SAST兼自動パッチシステム。

Akiraのタスク内では3AIはstrandsのマルチエージェントとして同一Fargateプロセスに同居しており、
上記2システムとはSecrets Managerの共有（APIキー等）のみの疎結合です。

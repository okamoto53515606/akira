# config_store.py — akira-config テーブル（システムプロンプト/skillsの動的読み込み）
#
# Akiraは自身のシステムプロンプトやskillsをDynamoDBに保存でき、
# 翌日のFargate起動時にそれを読み込む（自己改善ループ）。
#
# akira-config テーブル設計:
#   pk = "config"
#   sk = "system_prompt" | "skill#<name>" | "site_plan" など
#   属性: content(str), updated_at, note

from datetime import datetime

import boto3

from settings import AWS_REGION, CONFIG_TABLE, JST

DEFAULT_SYSTEM_PROMPT = """あなたは「Akira」。AI/LLM実用データハブ「llm.okamomedia.tokyo」の運営責任者です。

## ミッション
広告なしの「役に立つ」サイトを毎日更新し、PV数を上げること。それのみ。
（アダルト・犯罪関連は絶対NG。誤情報の公開もNG）

## あなたの立場（舞台設定）
- あなたは毎朝Fargateタスクとして起動される
- 実作業は「okamoちゃんねる」の3人のAIに依頼する:
  - Claudeエンジニア: 記事執筆・HTML作成・S3反映
  - GPT税理士: factチェック・価値・PV貢献チェック
  - Gemini子育てママ: 画像生成・初心者目線のUXレビュー
- あなた自身は指示・レビュー・分析に徹する

## サイトの内容
- LLM API料金比較・トークンコスト計算機・モデルリリース情報などを毎日更新
- 一次情報（公式料金ページ等）で裏取りできる情報のみ公開
- 日本語メイン。主要ページは英語版も用意
- 自前データ（akira-usageの実測トークン/コスト）は差別化コンテンツとして活用してよい

## 計測・分析（設定済み）
- GA4: llm.okamomedia.tokyo = プロパティ 543969888 / akira.okamomedia.tokyo = プロパティ 544003620
- 全ページにGoogleタグ（G-MTH8T0ECG2）必須（Claudeエンジニアが埋込む）
- Search Consoleデータ: BigQueryプロジェクト okamo1-153103 / データセット searchconsole_llm, searchconsole_akira
- GA4 MCP・BigQuery MCPが使える場合は毎朝前日のPV/検索クエリを確認し、コンテンツ戦略に反映する

## 毎日のワークフロー
1. 予算確認（ツールが自動で行う。停止判定なら日報のみ書いて終了）
2. GA4/Search Consoleで前日状況を確認（設定済みの場合）
3. リサーチ: LLM料金改定・新モデル情報等をWeb検索で収集
4. 作業計画を立て、3AIに依頼（執筆→factチェック→画像/UX）
5. GPT税理士が承認したものだけをS3へ公開
6. 日報HTMLを作成して公開（okamoへの依頼事項があれば必ず記載）

## 制約
- LLM費用のハードリミットは月額9,300円。（使い切ったら翌月まで停止）
- 日報は一般公開される。APIキー等の機密は絶対に書かない
"""


def _table():
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(CONFIG_TABLE)


def load_config(sk: str) -> str | None:
    """設定値を読み込む。未登録ならNone。"""
    item = _table().get_item(Key={"pk": "config", "sk": sk}).get("Item")
    return item.get("content") if item else None


def save_config(sk: str, content: str, note: str = "") -> None:
    """設定値を保存する（翌日起動時から有効）。"""
    _table().put_item(
        Item={
            "pk": "config",
            "sk": sk,
            "content": content,
            "note": note,
            "updated_at": datetime.now(JST).isoformat(),
        }
    )


def load_system_prompt() -> str:
    """AkiraのシステムプロンプトをDynamoDBから読み込む。未登録ならデフォルト。"""
    return load_config("system_prompt") or DEFAULT_SYSTEM_PROMPT


def load_skills() -> list[dict]:
    """skill#* を全件読み込む。"""
    resp = _table().query(
        KeyConditionExpression="pk = :p AND begins_with(sk, :s)",
        ExpressionAttributeValues={":p": "config", ":s": "skill#"},
    )
    return [
        {"name": i["sk"].removeprefix("skill#"), "content": i.get("content", "")}
        for i in resp["Items"]
    ]

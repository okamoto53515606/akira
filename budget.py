# budget.py — LLM費用の記録と予算ゲート
#
# ルール（okamo指示）:
# - LLM費用が月額9,300円（1日300円×31日）を超えそうなら当月の作業を停止
# - 翌月には自動再開（月が変われば again 実行可能）
# - 見積もりは厳密でなくてよいが「上振れしない」こと → 不明モデルは高め見積もり
#
# akira-usage テーブル設計:
#   pk = "usage#YYYY-MM"          （月単位パーティション）
#   sk = "YYYY-MM-DDTHH:MM:SS#<uuid>"（記録時刻）
#   属性: model_id, input_tokens, output_tokens, images, cost_jpy, purpose

# モデル料金は settings.MODEL_PRICING_USD を参照。
# claude-sonnet-5: 導入価格 $2/$10 は 2026-08-31 まで（estimate_cost_jpy で日付判定）

import uuid
from datetime import datetime
from decimal import Decimal

import boto3

from settings import (
    AWS_REGION,
    DAILY_BUDGET_JPY,
    DEFAULT_PRICING_USD,
    IMAGE_PRICE_USD,
    JST,
    MODEL_PRICING_USD,
    MONTHLY_BUDGET_JPY,
    USAGE_TABLE,
    USD_JPY,
)


def _table():
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(USAGE_TABLE)


# 今回実行分の累計費用（プロセス内）。日次予算ガードに使う。
_run_spent_jpy = 0.0

# エージェントごとの前回累計値（strandsの accumulated_usage はエージェント生涯累計のため、
# 同一エージェントを複数回呼ぶと重複計上される。差分を記録する）
_prev_usage: dict[int, tuple[int, int]] = {}


def get_run_spent_jpy() -> float:
    """今回の実行で使った費用(JPY)を返す。"""
    return _run_spent_jpy


def estimate_cost_jpy(model_id: str, input_tokens: int, output_tokens: int, images: int = 0) -> float:
    """トークン数からJPY費用を概算する。不明モデルは高め（上振れ防止）。"""
    price_in, price_out = MODEL_PRICING_USD.get(model_id, DEFAULT_PRICING_USD)
    # claude-sonnet-5 の導入価格（$2/$10）は 2026-08-31 で終了 → 以降は通常価格 $3/$15
    if model_id == "claude-sonnet-5" and datetime.now(JST).strftime("%Y-%m-%d") > "2026-08-31":
        price_in, price_out = 3.0, 15.0
    usd = (input_tokens * price_in + output_tokens * price_out) / 1_000_000
    usd += images * IMAGE_PRICE_USD
    return usd * USD_JPY


def record_usage(
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    images: int = 0,
    purpose: str = "",
) -> float:
    """LLM利用をDynamoDBへ記録し、概算費用(JPY)を返す。"""
    global _run_spent_jpy
    now = datetime.now(JST)
    cost = estimate_cost_jpy(model_id, input_tokens, output_tokens, images)
    _run_spent_jpy += cost
    _table().put_item(
        Item={
            "pk": f"usage#{now.strftime('%Y-%m')}",
            "sk": f"{now.strftime('%Y-%m-%dT%H:%M:%S')}#{uuid.uuid4().hex[:8]}",
            "model_id": model_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "images": images,
            "cost_jpy": Decimal(str(round(cost, 4))),
            "purpose": purpose[:500],
        }
    )
    return cost


def get_month_cost_jpy(month: str | None = None) -> float:
    """当月（または指定月 YYYY-MM）の累計LLM費用(JPY)を返す。"""
    month = month or datetime.now(JST).strftime("%Y-%m")
    total = 0.0
    kwargs = {
        "KeyConditionExpression": "pk = :p",
        "ExpressionAttributeValues": {":p": f"usage#{month}"},
    }
    table = _table()
    while True:
        resp = table.query(**kwargs)
        total += sum(float(i.get("cost_jpy", 0)) for i in resp["Items"])
        if "LastEvaluatedKey" not in resp:
            return total
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def check_budget() -> dict:
    """予算ゲート。実行可否と残額を返す。

    ハードリミットは月額予算（9,300円）のみ。日次300円は配分の目安。
    残額が正の間は実行可（例: 4日で使い切ってもOK、使い切ったら翌月まで停止）。
    """
    now = datetime.now(JST)
    month_cost = get_month_cost_jpy()
    remaining = MONTHLY_BUDGET_JPY - month_cost

    can_run = remaining > 0

    return {
        "can_run": can_run,
        "month": now.strftime("%Y-%m"),
        "month_cost_jpy": round(month_cost, 1),
        "monthly_budget_jpy": MONTHLY_BUDGET_JPY,
        "remaining_jpy": round(remaining, 1),
        "daily_budget_jpy": DAILY_BUDGET_JPY,
        "message": (
            "OK: 本日の作業を実行できます"
            if can_run
            else "STOP: 月額予算を使い切ったため本日の作業を停止します（翌月自動再開）"
        ),
    }


def collect_agent_usage(agent_result, model_id: str, purpose: str, agent=None) -> float:
    """strands AgentResult からトークン使用量を抽出して記録する。

    accumulated_usage はエージェント生涯の累計値のため、agentを渡すと
    前回呼び出しからの差分のみを記録する（重複計上防止）。
    """
    usage = None
    metrics = getattr(agent_result, "metrics", None)
    if metrics is not None:
        usage = getattr(metrics, "accumulated_usage", None)
    if usage is None:
        usage = getattr(agent_result, "accumulated_usage", None)
    if not usage:
        return 0.0
    input_tokens = int(usage.get("inputTokens", 0))
    output_tokens = int(usage.get("outputTokens", 0))

    if agent is not None:
        prev_in, prev_out = _prev_usage.get(id(agent), (0, 0))
        _prev_usage[id(agent)] = (input_tokens, output_tokens)
        input_tokens -= prev_in
        output_tokens -= prev_out

    if input_tokens <= 0 and output_tokens <= 0:
        return 0.0
    return record_usage(model_id, input_tokens, output_tokens, purpose=purpose)

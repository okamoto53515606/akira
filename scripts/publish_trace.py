"""trace（実行の記録）を**公開用のJSONL**に変換する（2026-11-21）。

用途:
    akira-trace（DynamoDB）は**内部の観測用**。ここから
      * 公開してよい kind だけ
      * 秘匿情報を伏字にしたもの
    を取り出して1行1イベントの JSONL を作る。これを公開用の場所に置けば
    「エージェントが何を頼まれ、何を渡され、どう動いたか」を外から検証できる。

なぜ生の表を公開しないか:
    * ツール引数には鍵が混ざり得る（モデルが復唱することがある）
    * 取得した第三者ページの本文は著作物で、再配布の条件が別
    * okamoコメント等に個人情報が入り得る
    * 生の表を公開APIにすると、誰でも任意のrunを引ける＝費用と悪用の面でも不利
    よって「許可kindのみ・伏字・静的スナップショット」に寄せる。

使い方:
    python3 scripts/publish_trace.py --date 2026-11-21 --dry
    python3 scripts/publish_trace.py --date 2026-11-21 --out /tmp/trace-2026-11-21.jsonl
    python3 scripts/publish_trace.py --from 2026-11-01 --to 2026-11-21 --out s3://...

    --include-bodies を付けると S3 の本文も取り込むが、**内部調査専用**。
    公開用の出力には使わないこと（スクリプトが警告を出す）。

公開レコードの形（1行）:
    {"date","run_id","seq","ts","kind","agent","item_id","status","tool_calls",
     "cost_jpy","digest","system_prompt"(prompt.system のみ),"note"}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, timedelta

import boto3

TABLE = os.environ.get("TRACE_TABLE", "akira-trace")
REGION = os.environ.get("AWS_REGION", "us-east-1")

# 公開してよい kind と、公開する属性（allowlist。足すときは意味を確認してから）
PUBLIC_FIELDS = {
    "run.start": ("dry_run", "no_publish", "month_cost_jpy", "budget_jpy"),
    "run.end": ("run_spent_jpy", "items", "not_done", "report_written"),
    "mission.built": ("theme_chars", "watch_chars", "body"),
    "prompt.system": ("agent", "chars", "digest", "system_prompt", "extra"),
    "plan.item": ("item_id", "text"),
    "delegate.request": ("agent", "item_id", "attempt", "chars", "body", "accept"),
    "delegate.result": ("agent", "item_id", "tool_calls", "cost_jpy", "tools", "body"),
    "item.status": ("item_id", "status", "reason", "accept"),
    "gate.result": ("ok", "rejected"),
    "publish": ("published", "rejected", "live_mismatch"),
    "report.claim": ("chars", "requests_chars"),
}

# 公開時に**必ず**落とす属性（内部参照・有効期限）
DROP_FIELDS = ("pk", "sk", "ttl")

REDACT = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-***"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "AIza***"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "gh*_***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***"),
    (re.compile(r"ASIA[0-9A-Z]{16}"), "ASIA***"),
    (re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"), "xox*-***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"), r"\1***"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.S), "-----BEGIN PRIVATE KEY-----***"),
    (re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[=:]\s*)[^\s\"',}]{8,}"),
     r"\1***"),
    # メールアドレス（okamoコメント等に混ざる場合の保険）
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "***@***"),
)


def redact(value):
    if isinstance(value, str):
        out = value
        for pat, rep in REDACT:
            out = pat.sub(rep, out)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value


def _json_default(obj):
    """Decimal（DynamoDB の数値）などを素直な型に落とす。"""
    try:
        from decimal import Decimal

        if isinstance(obj, Decimal):
            return int(obj) if obj == obj.to_integral_value() else float(obj)
    except Exception:  # noqa: BLE001
        pass
    return str(obj)


def _dates(args) -> list[str]:
    if args.date:
        return [args.date]
    start = date.fromisoformat(args.from_)
    end = date.fromisoformat(args.to)
    out = []
    while start <= end:
        out.append(start.isoformat())
        start += timedelta(days=1)
    return out


def _runs_for_date(ddb, day: str) -> list[str]:
    """pk = run#<date>#<run_id> を一覧にする（Queryで前方一致）。"""
    table = ddb.Table(TABLE)
    pks, start = [], None
    while True:
        kw = {"KeyConditionExpression": "pk = :p",  # ダミー。実際はscanで前方一致を拾う
              "ExpressionAttributeValues": {":p": "run#%s#" % day}}
        # pk は run_id を含むので完全一致できない。scan + begins_with で拾う。
        kw = {"FilterExpression": "begins_with(pk, :p)",
              "ExpressionAttributeValues": {":p": "run#%s#" % day},
              "ProjectionExpression": "pk"}
        if start:
            kw["ExclusiveStartKey"] = start
        resp = table.scan(**kw)
        for it in resp.get("Items", []):
            if it["pk"] not in pks:
                pks.append(it["pk"])
        start = resp.get("LastEvaluatedKey")
        if not start:
            break
    return sorted(pks)


def export(day: str, include_bodies: bool = False) -> list[dict]:
    ddb = boto3.resource("dynamodb", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    table = ddb.Table(TABLE)
    bucket = os.environ.get("TRACE_BUCKET", "akira-workspace")
    rows = []
    for pk in _runs_for_date(ddb, day):
        kw = {"KeyConditionExpression": "pk = :p",
              "ExpressionAttributeValues": {":p": pk}}
        start = None
        while True:
            if start:
                kw["ExclusiveStartKey"] = start
            resp = table.query(**kw)
            for item in resp.get("Items", []):
                kind = item.get("kind")
                if kind not in PUBLIC_FIELDS:
                    continue
                rec = {"date": item.get("date"), "run_id": item.get("run_id"),
                       "seq": str(item.get("sk", ""))[:5], "kind": kind,
                       "ts": item.get("ts")}
                for f in PUBLIC_FIELDS[kind]:
                    if f in item:
                        rec[f] = item[f]
                body = rec.get("body")
                # event() は dict をJSON文字列にして保存するので、両方の形を受ける
                if isinstance(body, str):
                    try:
                        parsed = json.loads(body)
                    except Exception:  # noqa: BLE001
                        parsed = None
                    if isinstance(parsed, dict) and "key" in parsed:
                        body = parsed
                if isinstance(body, dict) and "key" in body:
                    if include_bodies:
                        try:
                            raw = s3.get_object(Bucket=bucket, Key=body["key"])["Body"].read()
                            rec["body_text"] = raw.decode("utf-8", "replace")
                        except Exception:  # noqa: BLE001
                            rec["body_text"] = None
                    # 公開用: 本文もS3キーも出さず、同一性の検証用に digest だけ残す
                    rec["body"] = {"digest": body.get("digest"),
                                   "chars": body.get("chars")}
                elif isinstance(body, dict):
                    rec["body"] = {"digest": body.get("digest"), "chars": body.get("chars")}
                rows.append(redact(rec))
            start = resp.get("LastEvaluatedKey")
            if not start:
                break
    rows.sort(key=lambda r: (r.get("run_id") or "", r["seq"]))
    return rows


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--from", dest="from_")
    ap.add_argument("--to")
    ap.add_argument("--out")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--include-bodies", action="store_true",
                    help="S3の本文も含める（**内部調査専用**。公開しないこと）")
    args = ap.parse_args(argv)
    if not args.date and not (args.from_ and args.to):
        ap.error("--date か --from/--to が必要")

    all_rows = []
    for day in _dates(args):
        rows = export(day, include_bodies=args.include_bodies)
        print("%s: %d 行（run数 %d）" % (day, len(rows),
                                       len({r["run_id"] for r in rows})))
        all_rows.extend(rows)

    if args.include_bodies:
        print("!! --include-bodies は内部調査用。このファイルは公開するな。", file=sys.stderr)

    if args.dry:
        for r in all_rows[:3]:
            print(json.dumps(r, ensure_ascii=False, default=_json_default)[:400])
        return 0

    payload = "\n".join(json.dumps(r, ensure_ascii=False, default=_json_default)
                        for r in all_rows) + "\n"
    if args.out and args.out.startswith("s3://"):
        bucket, _, key = args.out[5:].partition("/")
        boto3.client("s3", region_name=REGION).put_object(
            Bucket=bucket, Key=key, Body=payload.encode("utf-8"),
            ContentType="application/x-ndjson; charset=utf-8")
        print("書き出し: %s" % args.out)
    elif args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print("書き出し: %s" % args.out)
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

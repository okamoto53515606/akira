#!/usr/bin/env python3
"""週次レビュー用のデータを集めて Markdown で出す（LLMコスト0）。

用途（2026-11-15〜の運用）:
    Fargate の自動実行を1週間回したあと、**土曜に別のLLMへ客観レビューを依頼する**。
    そのとき「実際に何が起きたか」を数字で渡すための資料を作る。
    日報（DynamoDB）・台帳（S3 workspace）・cache の当日分から機械的に集計する。

使い方:
    python3 scripts/weekly_review_data.py            # 直近7日
    python3 scripts/weekly_review_data.py --days 14
    python3 scripts/weekly_review_data.py --out docs/weekly-data-2026-11-22.md

出すもの:
    1. 日別の表（日報の有無 / 依頼事項の字数 / site_events 件数 / cache 当日分 / 公開ページ数）
    2. その週の site_events 一覧（何をいつ出したか）
    3. 依頼事項の中身（＝okamoにしか決められないことだけになっているか）
    4. 台帳の現状（モデル数 / features / 単価未取得 / pricing 未掲載）
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, timedelta

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
WS_BUCKET = "akira-workspace"
CFG_TABLE = "akira-config"
REP_TABLE = "akira-reports"


def _ddb():
    return boto3.resource("dynamodb", region_name=REGION)


def load_reports(days: int) -> dict:
    """直近 days 日の日報を {date: item} で返す。"""
    tbl = _ddb().Table(REP_TABLE)
    today = date.today()
    out = {}
    for i in range(days):
        d = (today - timedelta(days=i)).isoformat()
        r = tbl.get_item(Key={"pk": "report", "sk": d}).get("Item")
        if r:
            out[d] = r
    return out


def load_facts() -> dict:
    s3 = boto3.client("s3", region_name=REGION)
    obj = s3.get_object(Bucket=WS_BUCKET, Key="data/facts.json")
    return json.loads(obj["Body"].read().decode("utf-8"))


def count_cache_by_date(days: int) -> dict:
    """workspace の cache/ にあるファイル名の日付（-YYYY-MM-DD）を数える。

    S3 の mtime は毎ラン restore/save で変わるため使えない（2026-11-14 の教訓）。
    ファイル名の日付だけが鮮度の判定材料。
    """
    s3 = boto3.client("s3", region_name=REGION)
    today = date.today()
    want = {(today - timedelta(days=i)).isoformat() for i in range(days)}
    counts = {d: 0 for d in want}
    token = None
    while True:
        kw = {"Bucket": WS_BUCKET, "Prefix": "cache/"}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            m = re.search(r"(\d{4}-\d{2}-\d{2})", o["Key"])
            if m and m.group(1) in counts:
                counts[m.group(1)] += 1
        if not r.get("IsTruncated"):
            break
        token = r.get("NextContinuationToken")
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)

    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(a.days)]
    reports = load_reports(a.days)
    facts = load_facts()
    cache = count_cache_by_date(a.days)

    # site_events を日付ごとに数える
    ev_by_date = {d: [] for d in dates}
    for e in facts.get("site_events", []):
        d = e.get("date")
        if d in ev_by_date:
            ev_by_date[d].append(e)

    L = []
    L.append("# Fargate 自動実行の実測データ（%s 〜 %s / %d日）" % (dates[-1], dates[0], a.days))
    L.append("")
    L.append("> `scripts/weekly_review_data.py` が機械的に作った資料。日報・台帳・cache から集計。")
    L.append("")
    L.append("## 1. 日別")
    L.append("")
    L.append("| 日付 | 日報 | 本文 | 依頼事項 | site_events | cache当日分 |")
    L.append("|---|---|---|---|---|---|")
    for d in reversed(dates):
        r = reports.get(d)
        body = (r or {}).get("body_md", "") or ""
        req = (r or {}).get("requests_to_okamo", "") or ""
        L.append("| %s | %s | %s字 | %s | %d件 | %d件 |" % (
            d,
            "あり" if r else "**なし**",
            len(body),
            ("%d字" % len(req.strip())) if req.strip() else "0字",
            len(ev_by_date.get(d, [])),
            cache.get(d, 0),
        ))
    L.append("")

    L.append("## 2. その週に公開したもの（site_events）")
    L.append("")
    for d in reversed(dates):
        for e in ev_by_date.get(d, []):
            L.append("- `%s` %s" % (d, (e.get("ja") or "")[:120]))
    L.append("")

    L.append("## 3. okamoへの依頼事項（0件が正常。中身が「okamoにしか決められないこと」かを見る）")
    L.append("")
    any_req = False
    for d in reversed(dates):
        req = ((reports.get(d) or {}).get("requests_to_okamo", "") or "").strip()
        if req:
            any_req = True
            L.append("### %s" % d)
            L.append(req[:800])
            L.append("")
    if not any_req:
        L.append("（%d日間で依頼事項なし）" % a.days)
        L.append("")

    # 台帳の現状
    models = facts.get("models") or {}
    no_price = [k for k, v in models.items()
                if not ((v.get("price") or {}).get("input") and (v.get("price") or {}).get("output"))]
    no_pricing = [k for k, v in models.items() if "pricing" not in set(v.get("shown_on") or [])]
    unknown = [k for k, v in models.items() if v.get("status") == "unknown"]
    L.append("## 4. 台帳の現状（ボトルネックを見る）")
    L.append("")
    L.append("| 指標 | 値 |")
    L.append("|---|---|")
    L.append("| モデル数 | %d |" % len(models))
    L.append("| 特集ページ本文（features） | %dページ |" % len(facts.get("features") or {}))
    L.append("| 単価が未取得 | %d件 |" % len(no_price))
    L.append("| 料金比較に未掲載 | %d件 |" % len(no_pricing))
    L.append("| 提供状態が未確認 | %d件 |" % len(unknown))
    L.append("")
    if no_price:
        L.append("- 単価未取得の例: %s" % ", ".join(no_price[:10]))
    if no_pricing:
        L.append("- 料金比較に未掲載の例: %s" % ", ".join(no_pricing[:10]))

    text = "\n".join(L) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("書き出し: %s（%d字）" % (a.out, len(text)))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

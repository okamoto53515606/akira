"""鮮度キュー（2026-11-15 追加 / R8）。

なぜ要るか:
    `facts.json` の `sources[].fetched_at` は、更新した日だけ書き換わる。
    しかし「どのキーが何日放置されているか」を誰も数えていなかったので、
    古い quote が新しい事実を上書きする事故（11-14 の Carbon GA）が起きた。

やること:
    台帳を読み、**今日いちばん先に取り直すべきキー**を決定論的に並べる。
    LLMは使わない（main.py がプロンプトに注入するだけ）。

並べ方（強い順）:
    1. 料金表に出ているのに price が null → 金額が無い＝ページに出せない。最優先
    2. 料金表に出ているのに逐語 quote が無い → 裏付けが無い
    3. status=preview で30日超 → GA済みのはず。放置すると「preview」のまま古くなる
    4. fetched_at が古い順         → 単純な鮮度切れ

対象外:
    `shown_on` に pricing / calculator が入っていないレコード（年表だけのイベント・
    沿革行）。単価を持たないのが正常なので、キューに入れると埋められない項目で
    埋め尽くされる（実際に一度そうなった）。

出力は最大 12 行。プロンプトを膨らませないため、溢れた分は件数だけ書く。
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime

STALE_DAYS = 14          # これ超えは「古い」
MAX_LINES = 12
PREVIEW_DAYS = 30        # preview のまま放置してよい日数


def _age(fetched_at: str, today: date) -> int | None:
    try:
        return (today - datetime.strptime(str(fetched_at)[:10], "%Y-%m-%d").date()).days
    except Exception:  # noqa: BLE001
        return None


def build_queue(facts_path: str, today_iso: str | None = None) -> str:
    """台帳から鮮度キューのテキストを作る。台帳が無ければ空文字。"""
    try:
        with open(facts_path, encoding="utf-8") as fh:
            facts = json.load(fh)
    except Exception:  # noqa: BLE001
        return ""
    records = facts.get("models") or {}
    if not isinstance(records, dict) or not records:
        return ""

    today = (datetime.strptime(today_iso, "%Y-%m-%d").date()
             if today_iso else date.today())

    rows = []
    for key, rec in records.items():
        if not isinstance(rec, dict):
            continue
        status = str(rec.get("status") or "")
        if status in ("retired", "deprecated"):
            continue  # 終了済みは取り直さない
        shown = rec.get("shown_on") or []
        priced_page = isinstance(shown, list) and (
            "pricing" in shown or "calculator" in shown)
        srcs = [s for s in (rec.get("sources") or []) if isinstance(s, dict)]
        ages = [a for a in (_age(s.get("fetched_at"), today) for s in srcs)]
        ages = [a for a in ages if a is not None]
        age = min(ages) if ages else None          # 一番新しい取得日で測る
        price = rec.get("price")
        # 単価を持たない「イベント行」（値下げのお知らせ等）は取り直しても
        # 埋めるべき数字が無い。キューに入れると毎回同じ面子で埋まるので除く。
        # 11-15 の初回ランで実際にこれが起きた（12件中0件しか消化されず、
        # しかも値下げ告知行が並んでいた）。
        if price is None and not priced_page:
            continue
        if not isinstance(shown, list):
            shown = []
        has_quote = any(isinstance(s.get("quote"), str) and s.get("quote", "").strip()
                        for s in srcs)
        released = _age(rec.get("released"), today)

        reason, rank = None, 0
        if priced_page and price is None:
            reason, rank = "料金表に出ているのに単価が無い", 5
        elif priced_page and srcs and not has_quote:
            reason, rank = "逐語の裏付けが無い", 4
        elif status == "preview" and released is not None and released > PREVIEW_DAYS:
            reason, rank = "preview のまま%d日経過" % released, 3
        elif not srcs:
            reason, rank = "出典URLが未登録", 2
        elif age is None:
            reason, rank = "取得日が未記録", 2
        elif age > STALE_DAYS:
            reason, rank = "%d日未取得" % age, 1
        if reason:
            rows.append((rank, age if age is not None else 999, key, reason, srcs))

    if not rows:
        return ""

    # --- 選び方 ---
    # 全部を毎回見せると「同じ12件が毎回出て、残り66件は永遠に見えない」になる。
    # そこで
    #   CRITICAL（単価が無い / preview放置 / 出典未登録）は每回必ず出す
    #   それ以外（逐語が無い / 鮮度切れ）は日付で回して少しずつ出す
    crit_ranks = (5,)
    crit = [r for r in rows if r[0] in crit_ranks]
    rest = [r for r in rows if r[0] not in crit_ranks]
    rest.sort(key=lambda r: (-r[0], -r[1], r[2]))

    budget = MAX_LINES
    chosen = crit[:budget]
    budget -= len(chosen)
    if rest and budget > 0:
        # 日付で開始位置をずらす（同じ台帳なら同じ日に何度実行しても同じ結果）
        start = (today.toordinal() * MAX_LINES) % len(rest)  # 1日で12件ぶん進める
        rot = rest[start:] + rest[:start]
        chosen += rot[:budget]

    lines = []
    for rank, age, key, reason, srcs in chosen[:MAX_LINES]:
        url = srcs[0].get("url", "") if srcs else ""
        lines.append("- %s — %s%s" % (key, reason, (" " + url) if url else ""))

    head = "## 今日の再取得対象（鮮度キュー・自動生成）\n"
    head += ("台帳 `data/facts.json` の `fetched_at` から機械的に並べたもの。"
             "**上から順に `fetch_quote` で取り直す**。取り直したら `fetched_at` と "
             "`quote` を台帳に書き戻す（これが無いと永久にキューに残る）。\n")
    body = "\n".join(lines)
    body += ("\n（この12件は日替わりで入れ替わる。残り %d 件が待機中。"
             "「料金表なのに単価が無い」だけは毎回出る＝本当に壊れている）"
             % max(0, len(rows) - len(chosen)))
    return head + body + "\n"


def main() -> None:  # 手元確認用
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "s3-snapshot/workspace/data/facts.json"
    print(build_queue(path) or "(キューは空)")


if __name__ == "__main__":
    main()

def queue_items(facts_path: str, today_iso: str | None = None, limit: int = 12) -> list:
    """キューを**構造化した形**で返す（2026-11-15 追加）。

    `build_queue()` はプロンプト用のテキスト。モデルはそれを読んでも動かなかった
    （11-15 の2ラン連続で0件）。**取得そのものをコードでやる**ために、
    key / url / 理由を取り出せる形にする。
    """
    try:
        with open(facts_path, encoding="utf-8") as fh:
            facts = json.load(fh)
    except Exception:  # noqa: BLE001
        return []
    records = facts.get("models") or {}
    today = (datetime.strptime(today_iso, "%Y-%m-%d").date()
             if today_iso else date.today())
    rows = []
    for key, rec in records.items():
        if not isinstance(rec, dict):
            continue
        if str(rec.get("status") or "") in ("retired", "deprecated"):
            continue
        shown = rec.get("shown_on") or []
        priced_page = isinstance(shown, list) and ("pricing" in shown or "calculator" in shown)
        srcs = [s for s in (rec.get("sources") or []) if isinstance(s, dict) and s.get("url")]
        if rec.get("price") is None and not priced_page:
            continue
        if not srcs:
            continue
        ages = [a for a in (_age(s.get("fetched_at"), today) for s in srcs) if a is not None]
        age = min(ages) if ages else None
        reason, rank = None, 0
        if priced_page and rec.get("price") is None:
            reason, rank = "料金表に出ているのに単価が無い", 5
        elif age is None:
            reason, rank = "取得日が未記録", 2
        elif age > STALE_DAYS:
            reason, rank = "%d日未取得" % age, 1
        if reason:
            rows.append({"rank": rank, "age": age if age is not None else 999,
                         "key": key, "reason": reason, "url": srcs[0]["url"]})
    rows.sort(key=lambda r: (-r["rank"], -r["age"], r["key"]))
    return rows[:limit]

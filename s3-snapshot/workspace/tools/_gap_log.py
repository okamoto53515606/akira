"""一次情報にたどり着けなかった回数の記録（2026-11-15 追加 / R4）。

なぜ要るか:
    「公式URLが見つからなかった」「本文が取れなかった」は、いままで**握り潰されて**
    いた。回数が分からないと「検索の使い方を変えるべきか / 人間にURLを聞くべきか /
    そもそもURLは在るのか」を判断できない。判断材料として日別に数えるだけ。

保存先:
    <WORKSPACE>/notes/source-gaps.json
    workspace ごと S3 に保存されるので、日をまたいで溜まる。

入れないもの:
    本文・引用・URL一覧は保存しない（容量とプライバシー）。数と理由の種類だけ。
    30日より古い日は捨てる。

使い方（他ツールから）:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _gap_log import record_call
    record_call("fetch", name=key, ok=False, reason="empty_body")
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
WORKSPACE = os.environ.get("WORKSPACE_LOCAL_DIR", "/workspace")
REPORT_PATH = os.path.join(WORKSPACE, "notes", "source-gaps.json")
KEEP_DAYS = 30
MAX_NAMES = 60


def _empty() -> dict:
    return {"version": 1, "days": {}}


def load() -> dict:
    try:
        with open(REPORT_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("days"), dict):
            return data
    except Exception:  # noqa: BLE001
        pass
    return _empty()


def save(data: dict) -> None:
    cutoff = (datetime.now(JST).date() - timedelta(days=KEEP_DAYS)).isoformat()
    days = {d: v for d, v in data.get("days", {}).items() if d >= cutoff}
    data = {"version": 1, "days": days}
    try:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    except Exception:  # noqa: BLE001
        pass  # 記録に失敗しても本処理は止めない


def record_call(kind: str, name: str = "", ok: bool = True, reason: str = "") -> None:
    """1回分を数える。kind は "fetch" / "discover" など短い語。"""
    today = datetime.now(JST).date().isoformat()
    data = load()
    day = data["days"].setdefault(today, {})
    slot = day.setdefault(kind, {"total": 0, "failed": 0, "names": {}, "reasons": {}})
    slot["total"] = int(slot.get("total", 0)) + 1
    if ok:
        save(data)
        return
    slot["failed"] = int(slot.get("failed", 0)) + 1
    key = (name or "?").strip() or "?"
    names = slot.setdefault("names", {})
    names[key] = int(names.get(key, 0)) + 1
    if len(names) > MAX_NAMES:
        for k in sorted(names, key=lambda x: names[x])[: len(names) - MAX_NAMES]:
            names.pop(k, None)
    if reason:
        reasons = slot.setdefault("reasons", {})
        reasons[reason] = int(reasons.get(reason, 0)) + 1
    save(data)


def summarize(days: int = 7) -> dict:
    """直近 days 日の集計。Akiraが「今日は何件取りこぼしたか」を見るための形。"""
    data = load()
    cutoff = (datetime.now(JST).date() - timedelta(days=days - 1)).isoformat()
    tot = {"total": 0, "failed": 0}
    per_kind: dict = {}
    worst: dict = {}
    reasons: dict = {}
    for d, kinds in sorted(data.get("days", {}).items()):
        if d < cutoff:
            continue
        for kind, slot in kinds.items():
            k = per_kind.setdefault(kind, {"total": 0, "failed": 0})
            k["total"] += int(slot.get("total", 0))
            k["failed"] += int(slot.get("failed", 0))
            tot["total"] += int(slot.get("total", 0))
            tot["failed"] += int(slot.get("failed", 0))
            for n, c in (slot.get("names") or {}).items():
                worst[n] = worst.get(n, 0) + int(c)
            for r, c in (slot.get("reasons") or {}).items():
                reasons[r] = reasons.get(r, 0) + int(c)
    top = sorted(worst.items(), key=lambda x: (-x[1], x[0]))[:10]
    return {
        "since": cutoff,
        "days": days,
        "totals": tot,
        "by_kind": per_kind,
        "worst_sources": [{"key": n, "failures": c} for n, c in top],
        "reasons": sorted(reasons.items(), key=lambda x: -x[1])[:10],
        "path": REPORT_PATH,
    }

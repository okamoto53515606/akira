"""レビュー用のエビデンスパック（2026-11-14 追加）。

背景:
    11-14 の GPT税理士は「提示された当日取得のGoogle一次情報によれば」と書いて
    Carbon を GA ではないと断定し、正しい記述を削らせた。実際には何も提示されておらず、
    GPT は `/workspace/cache/gemini-4-carbon-2026-11-03.md`（11日前）の判定文を
    そのまま再生していた。`cache/` の最新は 11-05 で、11-10 以降の事実は1件も入っていない。

対策:
    レビュー担当に `/workspace` を探索させない。**当日取得した cache だけ**を
    文字列にして渡す。古い証拠に触れなければ、古い結論は出てこない。

鮮度の判定にファイルの mtime を使ってはいけない（毎ランの restore/save で当日になる）。
本文先頭の「取得日時:」だけを見る。

使い方:
    evidence_pack()
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from strands import tool

JST = timezone(timedelta(hours=9))
WORKSPACE = os.environ.get("WORKSPACE_LOCAL_DIR", "/workspace")
CACHE_DIR = os.path.join(WORKSPACE, "cache")


@tool
def evidence_pack(max_files: int = 6, max_chars: int = 6000) -> dict:
    """**本日取得した**一次情報だけを集めて返す（レビュー担当に渡す材料）。

    対象は /workspace/cache/*.md のうち、本文冒頭の「取得日時: <今日>」を持つものだけ。
    1件も無ければ count=0 を返す（その場合はレビューしないほうが安全）。

    Args:
        max_files: 最大何件まで含めるか
        max_chars: 全体の最大文字数
    """
    today = datetime.now(JST).date().isoformat()
    if not os.path.isdir(CACHE_DIR):
        return {"status": "ok", "date": today, "count": 0, "files": [], "text": ""}
    picked = []
    for name in sorted(os.listdir(CACHE_DIR)):
        if not name.endswith(".md"):
            continue
        p = os.path.join(CACHE_DIR, name)
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                head = fh.read(300)
                if ("取得日時: %s" % today) not in head:
                    continue
                fh.seek(0)
                picked.append((name, fh.read(max_chars)))
        except OSError:
            continue
    picked = picked[:max_files]
    text = "\n\n".join("### %s\n%s" % (n, t) for n, t in picked)[:max_chars]
    return {"status": "ok", "date": today, "count": len(picked),
            "files": [n for n, _ in picked], "text": text}


TOOL = evidence_pack

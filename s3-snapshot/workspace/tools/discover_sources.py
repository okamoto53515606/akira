"""公式サイトのURLを探す（2026-11-14 追加）。

「最新の◯◯の料金」のように、まず**どこを見るべきか**を知りたいときに使う。
本文は取らない（取得は fetch_quote）。返すのは title と url だけなので安い。

okamo にURLを教えてもらわないと動けない状態を解消するための入口。
grounding（GPT/GeminiのWeb検索）で「答え」を書かせるのではなく、
**URL候補を出すためだけ**に検索を使い、事実は fetch_quote で逐語取得する。

使い方:
    discover_sources(query="Gemini 4 Hydrogen pricing official blog", count=5)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from strands import tool

import sys as _sys

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gap_log import record_call  # noqa: E402  (R4: 見つからなかった回数を数える)

TIMEOUT = 30


@tool
def discover_sources(query: str, count: int = 5) -> dict:
    """公式サイトのURL候補を検索で探す（本文は取らない。取得は fetch_quote を使う）。

    Args:
        query: 検索語（例: "Gemini 4 Hydrogen pricing official"）
        count: 返す件数（最大10）
    """
    key = os.environ.get("BRAVE_API_KEY", "")
    if not key:
        record_call("discover", query[:40], ok=False, reason="no_api_key")
        return {"status": "failed", "reason": "BRAVE_API_KEY がありません"}
    n = max(1, min(int(count or 5), 10))
    url = ("https://api.search.brave.com/res/v1/web/search?q=%s&count=%d"
           % (urllib.request.quote(query), n))
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "X-Subscription-Token": key})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        record_call("discover", query[:40], ok=False, reason="http_%s" % e.code)
        return {"status": "failed", "reason": "brave http %s" % e.code, "query": query}
    except Exception as e:  # noqa: BLE001
        record_call("discover", query[:40], ok=False, reason=type(e).__name__)
        return {"status": "failed", "reason": "%s: %s" % (type(e).__name__, e), "query": query}
    hits = [{"title": r.get("title", ""), "url": r.get("url", "")}
            for r in (data.get("web") or {}).get("results", [])[:n]]
    # 0件は「検索語が悪い」のか「そもそも情報が無い」のかを分けて数える
    record_call("discover", query[:40], ok=bool(hits), reason="zero_hits" if not hits else "")
    return {"status": "ok", "query": query, "count": len(hits), "results": hits,
            "next": "候補のうち公式ドメインを fetch_quote で取得すること"}


TOOL = discover_sources

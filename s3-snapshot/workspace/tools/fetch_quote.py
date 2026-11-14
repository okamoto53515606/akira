"""一次情報の逐語取得（2026-11-14 追加）。

背景:
    エンジニアは「どのURLを見るべきか」を知らないため、okamo にURLを渡してもらわないと
    最新情報に辿り着けなかった（Fable 5.2 のキャッシュ単価は公式ページを直接叩けば取れた）。
    さらにレビュー担当は /workspace/cache の**古いスナップショット**を「当日の一次情報」と
    して読み、正しい記述を削った（11-14 の Carbon GA）。

    → **取得したら必ず cache に当日の日付で書く**。レビュー担当は当日の cache だけを
      証拠として使う。これで「古い証拠が新しい事実を上書きする」経路を塞ぐ。

自分では判断しない（LLM呼び出しなし）。

使い方:
    fetch_quote(url="https://...", key="gemini-4-hydrogen",
                hint="入力/出力/キャッシュ単価と提供段階を逐語で")
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from strands import tool

JST = timezone(timedelta(hours=9))
WORKSPACE = os.environ.get("WORKSPACE_LOCAL_DIR", "/workspace")
CACHE_DIR = os.path.join(WORKSPACE, "cache")
MAX_CHARS = 400_000
TIMEOUT = 60


@tool
def fetch_quote(url: str, key: str, hint: str = "") -> dict:
    """URLの本文を取得し、cache/<key>-<当日>.md に保存する（逐語の一次情報）。

    取得した本文は返さない（トークンを食うため）。先頭300字と保存先だけ返す。
    同じキーの古いファイルは消さないが、当日のファイルが evidence_pack で優先される。

    Args:
        url: 取得する公式ページのURL
        key: 台帳のキー（例: "gemini-4-hydrogen"）。ファイル名になる
        hint: 抽出したい観点（例: "入力/出力/キャッシュ単価と提供段階"）。空なら本文全体
    """
    api = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api:
        return {"status": "failed", "reason": "FIRECRAWL_API_KEY がありません"}
    today = datetime.now(JST).date().isoformat()
    payload: dict = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    if hint:
        payload["formats"] = [{"type": "query", "prompt": hint}]
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v2/scrape",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer %s" % api,
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"status": "failed", "reason": "firecrawl http %s" % e.code, "url": url}
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "reason": "%s: %s" % (type(e).__name__, e), "url": url}

    d = data.get("data") or data
    body = d.get("markdown") or d.get("answer") or ""
    if not body:
        # directQuote の空応答は「無い」と同義ではない（2026-11-07 教訓）
        return {"status": "failed",
                "reason": "本文が空。空応答＝『存在しない』ではない。URLとformatsを変えて再試行すること",
                "url": url}
    body = body[:MAX_CHARS]
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = re.sub(r"[^a-z0-9._-]+", "-", key.lower()).strip("-") or "source"
    path = os.path.join(CACHE_DIR, "%s-%s.md" % (safe, today))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# %s — 一次情報スナップショット\n" % key)
        fh.write("取得日時: %s (JST)\n" % today)
        fh.write("出典: %s\n" % url)
        fh.write("取得方法: firecrawl scrape / formats=%s\n\n"
                 % ("query" if hint else "markdown"))
        fh.write(body)
    return {"status": "ok", "cache": path, "chars": len(body), "date": today,
            "head": re.sub(r"\s+", " ", body[:300])}


TOOL = fetch_quote

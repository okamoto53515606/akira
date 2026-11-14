"""一次情報の逐語取得（2026-11-14 追加 / 同日 v2）。

背景:
    エンジニアは「どのURLを見るべきか」を知らないため、okamo にURLを渡してもらわないと
    最新情報に辿り着けなかった。さらにレビュー担当は /workspace/cache の**古いスナップ
    ショット**を「当日の一次情報」として読み、正しい記述を削った（11-14 の Carbon GA）。

    → **取得したら必ず cache に当日の日付で書く**。レビュー担当は当日の cache だけを
      証拠として使う。これで「古い証拠が新しい事実を上書きする」経路を塞ぐ。

v2 の変更（2026-11-14、実測にもとづく）:
    11-14 の実行では firecrawl 8回のうち3回が「空」で、その2件は
    「JSページだから取れない」と判断されていた。実際に同じURLで取り比べると

        docs.cloud.google.com/.../gemini-4-hydrogen
            formats:["query"]    →     61字（"料金の情報はありません"） 5クレジット
            formats:["markdown"] → 68,589字（全文）                 1クレジット
        qwencloud.com/benefits/tokenplan
            formats:["query"]    →    128字                          5クレジット
            formats:["markdown"] → 10,683字                          1クレジット

    つまり**ページは取れていた**。要約モード(query)が痩せていただけ。
    キャッシュに落とす用途では全文が正しいので、**markdown を既定**にし、
    空だったときだけ query にフォールバックする（コストも1/5になる）。

自分では判断しない（LLM呼び出しなし）。

使い方:
    fetch_quote(url="https://...", key="gemini-4-hydrogen")
    fetch_quote(url="...", key="...", hint="入力/出力/キャッシュ単価")  # 空応答時の再試行用
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
MIN_USABLE = 300  # これ未満は「取れていない」とみなしてフォールバックする
TIMEOUT = 90


def _scrape(url: str, formats, api: str) -> str:
    payload = {"url": url, "formats": formats, "onlyMainContent": True}
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v2/scrape",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer %s" % api,
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        data = json.loads(res.read().decode("utf-8"))
    d = data.get("data") or data
    return d.get("markdown") or d.get("answer") or ""


@tool
def fetch_quote(url: str, key: str, hint: str = "") -> dict:
    """URLの本文を取得し、cache/<key>-<当日>.md に保存する（逐語の一次情報）。

    既定は**全文（markdown）**。取得した本文は会話に返さない（先頭300字とパスだけ）。
    本文が取れなかった場合のみ、hint があれば要約抽出（query）で再試行する。

    Args:
        url: 取得する公式ページのURL
        key: 台帳のキー（例: "gemini-4-hydrogen"）。ファイル名になる
        hint: 空応答時の再試行に使う観点（例: "入力/出力/キャッシュ単価"）
    """
    api = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api:
        return {"status": "failed", "reason": "FIRECRAWL_API_KEY がありません"}
    today = datetime.now(JST).date().isoformat()
    mode = "markdown"
    try:
        body = _scrape(url, ["markdown"], api)
    except urllib.error.HTTPError as e:
        return {"status": "failed", "reason": "firecrawl http %s" % e.code, "url": url}
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "reason": "%s: %s" % (type(e).__name__, e), "url": url}

    if len(body) < MIN_USABLE and hint:
        try:
            alt = _scrape(url, [{"type": "query", "prompt": hint}], api)
            if len(alt) > len(body):
                body, mode = alt, "query(fallback)"
        except Exception:  # noqa: BLE001
            pass

    if len(body) < MIN_USABLE:
        # 空応答は「無い」と同義ではない（2026-11-07 教訓）。URL自体を疑う。
        return {"status": "failed",
                "reason": "本文が %d 字しか取れませんでした。URL違い（一覧ページ・別ドメイン）か、"
                          "本文が画像/PDFの可能性。discover_sources でURLを探し直すこと" % len(body),
                "url": url, "chars": len(body)}
    body = body[:MAX_CHARS]
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = re.sub(r"[^a-z0-9._-]+", "-", key.lower()).strip("-") or "source"
    path = os.path.join(CACHE_DIR, "%s-%s.md" % (safe, today))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# %s — 一次情報スナップショット\n" % key)
        fh.write("取得日時: %s (JST)\n" % today)
        fh.write("出典: %s\n" % url)
        fh.write("取得方法: firecrawl scrape / %s / %d字\n\n" % (mode, len(body)))
        fh.write(body)
    return {"status": "ok", "cache": path, "chars": len(body), "mode": mode,
            "date": today, "head": re.sub(r"\s+", " ", body[:300])}


TOOL = fetch_quote

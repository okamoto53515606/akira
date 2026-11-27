"""配布元（Azure など）のカタログ掲載状況をコードで見張る（2026-11-27 追加）。

なぜ:
    2026-11-17 に `/deepseek-v4-1-flash/` を「Azure のカタログは Version
    2026-09-10 のまま（本家の 1017 より前の版）」と書いた。ところが同じ日に
    Azure は **`DeepSeek-V4.1-Flash-1017`（Version 2026-10-17）という別エントリ**を
    カタログに出していた。既存エントリの版が上がったのではなく、**新しい名前で
    増えた**ので「2026-09-10 のまま」という記述は事実として古くなっていた。
    11-26 のランでも誰も気づいていない（課題162 が「en/deepseek-v4-pro の取得日が
    2026-09-13 で止まっている」として残っている）。

    この種の事実（他社プラットフォームの掲載状況）は**台帳にもページにも
    「古くなった」と書かれない**。だから機械が見に行って、ページの記述と
    突き合わせるしかない。`tools/watch_releases.py` が「新モデル」を見張るのと
    同じ思想で、こちらは「配布元の版」を見張る。

判定:
    - catalog: 配布元カタログのエントリ（名前 → version / 提供段階）
    - claims : サイトのページが書いている version（`Version <code>…</code>` 等）
    - verdict:
        ok      … 最新エントリの名前と版がページに書かれている
        stale   … 最新エントリがページに無い（**直すべき**）
        unknown … 取得できなかった（「無い」ではない。日報に書く）

呼び出し側（main.py）はミッションに差し込み、実行後にもう一度ローカルだけを
見て「直っていなければ日報に残す」。取得は urllib だけ（追加依存なし）。
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
WORKSPACE = os.environ.get("WORKSPACE_LOCAL_DIR", "/workspace")
STATE_PATH = os.path.join(WORKSPACE, "data", "platform_watch.json")
SITE_DIR = os.environ.get("SITE_LOCAL_DIR", "/tmp/site")
TIMEOUT = 45
UA = "Mozilla/5.0 (akira-platform-watch)"

# 見張る対象。増やすときはここに1件足す（ページのパスはサイト内の相対パス）。
TARGETS = (
    {
        "id": "azure-deepseek-v4-1-flash",
        "label": "Azure（Microsoft Foundry）の DeepSeek V4.1 Flash",
        "query": "DeepSeek-V4.1-Flash",
        "family": "DeepSeek-V4.1-Flash",
        "pages": ("deepseek-v4-1-flash/index.html",
                  "en/deepseek-v4-1-flash/index.html"),
    },
)

LIST_URL = "https://ai.azure.com/catalog/models?search={q}"
MODEL_URL = "https://ai.azure.com/catalog/models/{name}"


# ---------------------------------------------------------------- 取得
def _fetch(url: str, retries: int = 1) -> str:
    """1URLを取得する（5xx・切断は1回だけやり直す）。"""
    last = None
    for _ in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code < 500:
                raise
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last else RuntimeError("fetch failed")


# ---------------------------------------------------------------- 解析
_TAG_RE = re.compile(r"<[^>]+>")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _plain(fragment: str) -> str:
    """タグとコメントを落として空白を畳む（`Version: <!-- -->2026-09-10` 対策）。"""
    text = _TAG_RE.sub(" ", _COMMENT_RE.sub(" ", fragment))
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def parse_entry_names(list_html: str, family: str) -> list:
    """カタログ一覧のHTMLから `family` で始まるモデル名を拾う。

    Azure のカタログは版が上がると**同じ名前のまま**ではなく
    `DeepSeek-V4.1-Flash-1017` のように**別エントリとして増える**ことがある。
    だから「親の名前」だけでなく接尾辞付きも拾う。
    """
    pat = re.compile(re.escape(family) + r"(?:-[0-9]{2,8})?(?![A-Za-z0-9.\-])")
    return sorted({m.group(0) for m in pat.finditer(list_html or "")})


def parse_meta(model_html: str) -> dict:
    """カタログのモデルページから version / 提供段階 / スペックを抜く。

    返すキー: version(YYYY-MM-DD or ""), lifecycle, context, tokens, input
    取れなかった項目は空文字（推測で埋めない）。
    """
    out = {"version": "", "lifecycle": "", "context": "", "tokens": "", "input": ""}
    if not model_html:
        return out
    # version は `Version: <!-- -->2026-09-10` の形で出る（コメントが挟まる）
    m = re.search(r"Version\s*:?\s*(?:<!--.*?-->)?\s*(\d{4}-\d{2}-\d{2})",
                  model_html, re.S)
    if m:
        out["version"] = m.group(1)
    # スペックは version より**後ろ**の仕様ブロックに並ぶ（実測: Version の約20KB後）。
    # ページ全体を素テキストにするとバンドル済みJSの文字列を拾うので、version の
    # 位置から前後を切り出す。
    anchor = model_html.find("Version")
    if anchor < 0:
        anchor = 0
    text = _plain(model_html[max(0, anchor - 3000):anchor + 40000])
    # Lifecycle は既知の語彙だけを受ける。`\S+` にするとバンドルJSの
    # `Lifecycle blah` のような断片を拾って「Preview」を取り逃がす。
    for key, pat in (
        ("lifecycle", r"Lifecycle\s+(Preview|Generally [Aa]vailable|GA|Deprecated|Retired)"),
        ("context", r"Context window\s+(\S+)"),
        ("tokens", r"Token limits\s+([0-9]+[kKmM]? output)"),
        ("input", r"Input type\s+(\S+)"),
    ):
        mm = re.search(pat, text, re.I)
        if mm:
            out[key] = mm.group(1)
    return out


_CLAIM_RE = re.compile(r"Version\s+(20\d{2}-\d{2}-\d{2})", re.I)


def parse_claims(page_html: str) -> list:
    """ページが「カタログの版」として書いている version を拾う（`Version 2026-09-10`）。

    ページ全体の日付を拾うと「本家の 2026-10-17」まで混ざり、**古い主張を見逃す**
    （実際、11-17 のページは Azure を 2026-09-10 と書きながら、同じ本文に
    本家の 2026-10-17 も書いていた）。だから `Version <日付>` の形だけを見る。
    """
    return re.findall(_CLAIM_RE, _plain(page_html or ""))


def compare(newest: dict, page_html: str) -> tuple:
    """(verdict, reason) を返す。"""
    claims = parse_claims(page_html)
    if claims:
        top = max(claims)
        if top < newest["version"]:
            return "stale", ("ページは「Version %s」と書いているが、カタログの最新は "
                              "%s（%s）" % (top, newest["version"], newest["name"]))
        return "ok", "ページの記載（Version %s）はカタログの最新（%s）と一致" % (
            top, newest["version"])
    if newest["name"] in page_html and newest["version"] in page_html:
        return "ok", "ページは最新エントリ（%s / %s）に触れている" % (
            newest["name"], newest["version"])
    return "stale", ("ページに「Version %s」の記載が無い（カタログの最新は %s / %s）"
                     % (newest["version"], newest["name"], newest["version"]))


# ---------------------------------------------------------------- 照合
def _read_page(site_dir: str, rel: str) -> str:
    try:
        with open(os.path.join(site_dir, rel), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def check_target(target: dict, site_dir: str | None = None, fetcher=None) -> dict:
    """1対象を照合する。ネットワーク失敗は verdict="unknown"（「無い」ではない）。"""
    site_dir = site_dir or SITE_DIR
    fetch = fetcher or _fetch
    res = {"id": target["id"], "label": target["label"], "entries": [],
           "newest": None, "claims": {}, "verdict": "unknown", "reason": "",
           "missing_pages": []}
    try:
        listing = fetch(LIST_URL.format(q=target["query"]))
        names = parse_entry_names(listing, target["family"])
        if not names:
            res["reason"] = "カタログ一覧に %s が見つからない" % target["family"]
            return res
        entries = []
        for name in names:
            meta = parse_meta(fetch(MODEL_URL.format(name=name)))
            if meta["version"]:
                meta["name"] = name
                entries.append(meta)
        if not entries:
            res["reason"] = "エントリはあるが version を読めない（%s）" % ", ".join(names)
            return res
        entries.sort(key=lambda e: e["version"], reverse=True)
        res["entries"] = entries
        res["newest"] = entries[0]
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", "")
        res["reason"] = "取得失敗（%s%s）" % (type(e).__name__,
                                            " %s" % code if code else "")
        return res

    newest = res["newest"]
    verdict, reason = _judge(newest, target, site_dir, res)
    res["verdict"], res["reason"] = verdict, reason
    return res


def _judge(newest: dict, target: dict, site_dir: str, res: dict) -> tuple:
    """ページの主張とカタログの最新を突き合わせる（結果の dict を埋める）。"""
    for rel in target["pages"]:
        page = _read_page(site_dir, rel)
        if not page:
            res["missing_pages"].append(rel)
            continue
        verdict, reason = compare(newest, page)
        res["claims"][rel] = {"verdict": verdict, "reason": reason,
                               "versions": parse_claims(page)}
    if not res["claims"]:
        return "unknown", "サイト側のページがローカルに無い（site_download 前？）"
    bad = ["%s: %s" % (rel, c["reason"]) for rel, c in res["claims"].items()
           if c["verdict"] == "stale"]
    if bad:
        return "stale", " / ".join(bad)
    return "ok", " / ".join("%s: %s" % (rel, c["reason"])
                             for rel, c in res["claims"].items())


def recheck_local(result: dict, site_dir: str | None = None) -> dict:
    """取得済みの結果を使い、**ページの記述だけ**を再判定する（再取得しない）。

    実行後に「直ったか」を見るため。Akiraが直していれば verdict が ok に変わる。
    """
    site_dir = site_dir or SITE_DIR
    newest = result.get("newest")
    if not newest or result.get("verdict") == "unknown":
        return result
    target = next((t for t in TARGETS if t["id"] == result["id"]), None)
    if target is None:
        return result
    out = dict(result)
    out["claims"] = {}
    out["missing_pages"] = []
    verdict, reason = _judge(newest, target, site_dir, out)
    out["verdict"], out["reason"] = verdict, reason
    return out


def scan(site_dir: str | None = None, fetcher=None, today: str | None = None) -> dict:
    """全対象を照合して状態を保存する。"""
    today = today or datetime.now(JST).date().isoformat()
    results = [check_target(t, site_dir=site_dir, fetcher=fetcher) for t in TARGETS]
    state = {"updated": today, "results": results}
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    except Exception:  # noqa: BLE001
        pass
    return state


# ---------------------------------------------------------------- 文言
def mission_line(state: dict) -> str:
    """ミッションに差し込む「配布元カタログの見張り」。

    stale は**今日やること**、unknown は**不明**（無いではない）と書く。
    """
    results = (state or {}).get("results") or []
    if not results:
        return ("## 配布元カタログの見張り: **未実施**"
                "（platform_watch の結果が空） — 掲載状況の古さは検知できていない。日報に書け。")
    lines = ["## 配布元カタログの見張り（機械が取得済み。**取り直す必要はない**）"]
    if any(r.get("verdict") == "stale" for r in results):
        lines.append("- **今日の最優先**: 下の「カタログの版が進んでいる」を1項目として"
                     " Claudeエンジニアに渡して直す（新モデルの追加より先にやる。"
                     "ページが古いまま公開され続けるほうが損）")
    for r in results:
        if r.get("verdict") == "unknown":
            lines.append("- %s: **不明**（%s） — 「載っていない」ではない。日報に書け。"
                         % (r["label"], r.get("reason") or "取得失敗"))
            continue
        newest = r["newest"]
        others = [e for e in r["entries"] if e["name"] != newest["name"]]
        detail = " / ".join(
            x for x in (newest.get("lifecycle"), newest.get("context"),
                        newest.get("tokens"), ("input: %s" % newest["input"])
                        if newest.get("input") else "") if x)
        if r["verdict"] == "stale":
            lines.append("- **%s: カタログの版が進んでいる（ページが古い）**" % r["label"])
            lines.append("  - 最新: `%s`（Version %s%s）"
                         % (newest["name"], newest["version"],
                            "・" + detail if detail else ""))
            if others:
                lines.append("  - 同時に載っている旧エントリ: " + ", ".join(
                    "`%s`（Version %s）" % (e["name"], e["version"]) for e in others))
            lines.append("  - ページの状態: %s" % r.get("reason"))
            lines.append("  - **直し方**: 対象ページの該当箇所を「現在の状態だけ」に書き換える。"
                         "「〜のまま」「古い」といった経過の記述は残さない（新しい版があるなら"
                         "事実として消えている）。旧エントリと新エントリが併存しているなら、"
                         "**両方**を今の状態として書き、ページの4点の日付"
                         "（updated-bar・JSON-LD dateModified・meta・sitemap lastmod）を今日に揃える")
        elif r["verdict"] == "ok":
            lines.append("- %s: 一致（最新 `%s` / Version %s%s）"
                         % (r["label"], newest["name"], newest["version"],
                            "・" + detail if detail else ""))
        else:
            lines.append("- %s: 判定できず（%s）" % (r["label"], r.get("reason")))
    lines.append("- この結果は日報に1行書く（一致でも「配布元: 変化なし」と書け）")
    return "\n".join(lines)


def stale_line(state: dict) -> str:
    """実行後に日報へ足す1行（まだ古ければ残す）。"""
    leftovers = [r for r in (state or {}).get("results") or []
                 if r.get("verdict") == "stale"]
    if not leftovers:
        return ""
    return "配布元カタログ: **%s**" % " / ".join(
        "%s が最新（%s / %s）なのにページに記載が無い"
        % (r["label"], r["newest"]["name"], r["newest"]["version"])
        for r in leftovers)

"""事実台帳（data/facts.json）からサイトの構造物を生成する（決定論的・LLMコスト0）。

背景（2026-11-14）:
    /timeline/ は「新規エントリを末尾に追記する」運用だったため日付降順が崩れ、
    /en/timeline/ は凍結中に5件が欠落した。原因は「並び順と日英同期を人の手順に
    任せていた」こと。ここでは台帳を唯一の入力にして、並び順・日英同期・計算機データ・
    更新履歴を機械で決める。

生成するもの:
    1. /timeline/ と /en/timeline/ のエントリ順（released 降順。ja/en で同一順）
    2. /data/models.json（計算機用。既存の並びを保ち、台帳にあって無いものを先頭に追加）
    3. /data/changelog.json と /changelog/ ・ /en/changelog/
    4. sitemap.xml の lastmod / llms.txt の Updated

方針:
    - 文章（title/desc）はまだHTML側にある。ここが並べ替えるだけで、書き換えない。
    - 何度実行しても結果が変わらない（冪等）。変化が無ければファイルを書かない。

使い方:
    python3 render_site.py                     # SITE_LOCAL_DIR or /tmp/site、WORKSPACE_DIR or /workspace
    python3 render_site.py --check             # 変更があるかだけ表示（書き込まない）
    python3 render_site.py --site /path --workspace /path
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from strands import tool

DEFAULT_SITE = os.environ.get("SITE_LOCAL_DIR", "") or "/tmp/site"
DEFAULT_WS = os.environ.get("WORKSPACE_DIR", "") or "/workspace"
FACTS_REL = "data/facts.json"
JST = timezone(timedelta(hours=9))
# 2026-11-17: コンテナは UTC なので date.today() だと JST 05:00 のランで
# 「1日前」の日付が焼かれる（課題155）。サイトは日本時間で運用するので JST 固定。
TODAY = datetime.now(JST).date().isoformat()


def _date_text(lang: str) -> str:
    # 2026-11-17: TODAY と同じく JST 基準（コンテナは UTC）
    d = datetime.now(JST).date()
    return "%d年%d月%d日" % (d.year, d.month, d.day) if lang == "ja" else d.isoformat()

ART_RE = re.compile(r'<article class="tl-item[^"]*" id="([^"]+)">.*?</article>\n?', re.S)
# 見出し・説明文の書き戻し用（本文を取り出すので group が要る）
ART_BODY_RE = re.compile(r'(<article class="tl-item[^"]*" id="([^"]+)">)(.*?)(</article>)', re.S)
DIVIDER_RE = re.compile(r'<div class="year-divider">[^<]*</div>\n?')


# --------------------------------------------------------------------------- 台帳
def load_facts(ws: Path) -> dict:
    p = ws / FACTS_REL
    if not p.exists():
        raise SystemExit("facts.json not found: %s" % p)
    return json.loads(p.read_text(encoding="utf-8"))


def ordered_records(facts: dict):
    """released 降順。日付が無いものは末尾（同日内は id 昇順で安定）。"""
    recs = list(facts.get("models", {}).values())
    return sorted(recs, key=lambda r: (r.get("released") or "0000-00-00", r.get("id", "")), reverse=True)


# --------------------------------------------------------------------------- 1. timeline
def render_timeline_prose(site: Path, rel: str, lang: str, facts: dict) -> list:
    """見出しと説明文を台帳から書き戻す（2026-11-15 / R5）。

    これが無いと、同じ文章が ja/en の2つのHTMLに直書きされたままになり、
    「片方だけ直して片方が漏れる」事故が構造的に消えない（§8.5.3）。
    台帳が正で、HTMLは成果物。手でHTMLを直しても次回の描画で戻る。

    戻り値は「書き換えた記事のid」のリスト（0件なら往復で壊れていない証拠）。
    """
    path = site / rel
    html = path.read_text(encoding="utf-8")
    changed = []

    def patch(m):
        aid, body = m.group(2), m.group(3)
        rec = None
        for r in facts.get("models", {}).values():
            t = r.get("timeline") or {}
            if t.get("ja_id") == aid or t.get("en_id") == aid:
                rec = r
                break
        if rec is None:
            return m.group(0)
        t = rec.get("timeline") or {}
        want_title = (t.get("title_%s" % lang) or "").strip()
        want_desc = (t.get("desc_%s" % lang) or "").strip()
        new_body = body
        if want_title:
            tm = re.search(r'(<h2[^>]*class="tl-title"[^>]*>)(.*?)(</h2>)', new_body, re.S)
            if tm:
                new_body = (new_body[:tm.start(2)] + escape(want_title)
                            + new_body[tm.end(2):])
        if want_desc:
            dm = re.search(r'(<p class="tl-desc">)(.*?)(</p>)', new_body, re.S)
            if dm:
                new_body = new_body[:dm.start(2)] + want_desc + new_body[dm.end(2):]
        if new_body != body:
            changed.append(aid)
        return m.group(1) + new_body + m.group(4)

    out = ART_BODY_RE.sub(patch, html)
    if changed:
        path.write_text(out, encoding="utf-8")
    return changed


def render_timeline(site: Path, rel: str, lang: str, order_ids) -> bool:
    """エントリを released 降順に並べ直す。ja/en で同一順になるよう (日付, id) で決める。

    order_ids は台帳の並び（ログ用）。実際の整列はHTMLの日付を正とする。
    台帳に無い id（手で足された等）も落とさず一緒に並べる。
    """
    path = site / rel
    html = path.read_text(encoding="utf-8")
    start_tag = '<div class="tl-wrap">'
    i = html.index(start_tag) + len(start_tag)
    matches = list(ART_RE.finditer(html, i))
    if not matches:
        return False
    arts = {}
    for m in matches:
        arts[m.group(1)] = m.group(0).rstrip("\n")
    head, tail = html[:i], html[matches[-1].end():]

    def dt(aid):
        m = re.search(r'<div class="tl-date">([0-9-]+)', arts[aid])
        return m.group(1) if m else "0000-00-00"

    ordered = sorted(arts, key=lambda a: (dt(a), a), reverse=True)
    out, cur = [], None
    for aid in ordered:
        y = dt(aid)[:4]
        if y != cur:
            out.append('<div class="year-divider">%s</div>' % ("%s年" % y if lang == "ja" else y))
            cur = y
        out.append(arts[aid])
    new = head + "\n" + "\n".join(out) + "\n" + tail.lstrip("\n")
    if new == html:
        return False
    path.write_text(new, encoding="utf-8")
    return True


# --------------------------------------------------------------------------- 2. 計算機
# --------------------------------------------------------------------- 1b. 料金表
TABLE_RE = re.compile(r"<table[^>]*>.*?</table>", re.S)
TBODY_RE = re.compile(r"(<tbody[^>]*>)(.*?)(</tbody>)", re.S)
# セクションの見出しアンカー（<section aria-labelledby="kimi-h">）
SECTION_RE = re.compile(r'<section\b[^>]*aria-labelledby="([^"]+)"[^>]*>', re.I)
# 表の1行目が「誰の表か」を判定するためのセル
MODEL_CELL_RE = re.compile(r'<td class="model-name">(.*?)</td>', re.S)

# render_pricing が書き込みを見送った理由（run() がログに出す）
PRICING_ERRORS: list[str] = []


def _model_name_of(row_html: str) -> str:
    """`<tr>…</tr>` から model-name セルの文字列だけを取り出す（比較用）。"""
    m = MODEL_CELL_RE.search(row_html or "")
    if not m:
        return ""
    txt = re.sub(r"<[^>]+>", " ", m.group(1))
    return re.sub(r"\s+", " ", txt).strip()


def _first_row_name(tbody_html: str) -> str:
    if "</tr>" not in tbody_html:
        return ""
    return _model_name_of(tbody_html.split("</tr>")[0] + "</tr>")


def _pricing_table_spans(html: str) -> dict:
    """`aria-labelledby` の id → そのセクション内の最初の <table> の (start, end, seg)。

    2026-11-17 追加。以前は「ページの i 番目の表」で書き戻していたため、
    途中に表を1つ挿しただけで以降が全部ずれた（Xiaomi の表に Kimi の行が入った）。
    セクションの id を手掛かりにすれば、表が増えても位置がずれない。
    """
    marks = list(SECTION_RE.finditer(html))
    spans: dict = {}
    for n, m in enumerate(marks):
        anchor = m.group(1)
        seg_end = marks[n + 1].start() if n + 1 < len(marks) else len(html)
        seg = html[m.start():seg_end]
        t = TABLE_RE.search(seg)
        if not t:
            continue
        spans.setdefault(anchor, (m.start() + t.start(), m.start() + t.end(), seg))
    return spans


def render_pricing(site: Path, rel: str, lang: str, facts: dict) -> int:
    """`/pricing/` の各表の <tbody> を台帳から書き戻す（R6）。

    台帳の `pricing_tables[i].rows[j][lang]` は `<tr>…</tr>` ごとの生HTML。
    日英が同じレコードに並んでいるので、片方だけ直す事故が起きない。

    2026-11-17 の事故と対策（重要）:
        旧実装は `pricing_tables[i]["index"]` を「ページの i 番目の <table>」と
        みなしていた。担当AIが Xiaomi の表を**途中に挿し込んだ**ため、以降の表が
        1つずつずれ、**Xiaomi の表に Kimi の行、Kimi の表に Meta の行**が入った
        状態で公開された（人が見るまで気づかない）。
        → 以降は **`anchor`（セクションの id）で表を特定**し、書き込みの前後で
          「1行目のモデル名が台帳と一致するか」を検証する。一致しなければ**その表
          は書かずに理由を残す**（fail-closed。誤った表を黙って上書きしない）。

    戻り値は書き換えた表の数。見送った理由は PRICING_ERRORS に入る。
    """
    tables = facts.get("pricing_tables") or []
    PRICING_ERRORS.clear()
    if not tables:
        return 0
    path = site / rel
    if not path.exists():
        return 0
    html = path.read_text(encoding="utf-8")
    original = html

    anchors = [t.get("anchor") or "" for t in tables]
    if not all(anchors):
        PRICING_ERRORS.append(
            "%s: anchor の無い pricing_tables がある（位置指定 index は廃止）" % rel)
        return 0
    if len(anchors) != len(set(anchors)):
        PRICING_ERRORS.append("%s: 台帳 pricing_tables の anchor が重複" % rel)
        return 0

    spans = _pricing_table_spans(html)
    n_tables_before = len(TABLE_RE.findall(html))
    planned = []            # (tbody_start, tbody_end, 新しい中身, anchor)
    for spec in tables:
        anchor = spec["anchor"]
        rows = [r.get(lang) for r in spec.get("rows", [])]
        if not rows or any(r is None for r in rows):
            continue
        hit = spans.get(anchor)
        if not hit:
            PRICING_ERRORS.append(
                "%s: #%s のセクション（表）が見つからない" % (rel, anchor))
            continue
        tstart, tend, seg = hit
        if ('id="%s"' % anchor) not in seg:
            PRICING_ERRORS.append(
                '%s: #%s のセクション内に id="%s" が無い（セクション境界が壊れて'
                "いる）" % (rel, anchor, anchor))
            continue
        m = TBODY_RE.search(html[tstart:tend])
        if not m:
            PRICING_ERRORS.append("%s: #%s の <tbody> が無い" % (rel, anchor))
            continue
        cur_first = _first_row_name(m.group(2))
        want_first = _model_name_of(rows[0])
        if cur_first and want_first and cur_first != want_first:
            PRICING_ERRORS.append(
                "%s: #%s の1行目が台帳と違う（ページ=%r / 台帳=%r）。"
                "表の取り違えを防ぐため書き込まない"
                % (rel, anchor, cur_first, want_first))
            continue
        planned.append((tstart + m.start(2), tstart + m.end(2),
                        "\n" + "\n".join(rows) + "\n", anchor))

    # 後ろから置換すれば offset がずれない
    for b, e, body, _anchor in sorted(planned, reverse=True):
        html = html[:b] + body + html[e:]

    if html == original:
        return 0

    # 検算: 表の数が変わっていないこと／書いた表の1行目が台帳どおりであること
    if len(TABLE_RE.findall(html)) != n_tables_before:
        PRICING_ERRORS.append(
            "%s: 書き込みで表の数が変わった（%d→%d）。中止"
            % (rel, n_tables_before, len(TABLE_RE.findall(html))))
        return 0
    spans_after = _pricing_table_spans(html)
    for spec in tables:
        anchor = spec["anchor"]
        rows = [r.get(lang) for r in spec.get("rows", [])]
        if not rows or any(r is None for r in rows):
            continue
        hit = spans_after.get(anchor)
        if not hit:
            continue
        m = TBODY_RE.search(html[hit[0]:hit[1]])
        if not m:
            continue
        got = _first_row_name(m.group(2))
        want = _model_name_of(rows[0])
        if got != want:
            PRICING_ERRORS.append(
                "%s: 書き込み後の検算で #%s が台帳と不一致（%r != %r）。中止"
                % (rel, anchor, got, want))
            return 0

    path.write_text(html, encoding="utf-8")
    return len(planned)


def render_models_json(site: Path, facts: dict) -> bool:
    path = site / "data" / "models.json"
    cur = json.loads(path.read_text(encoding="utf-8"))
    rows = cur.get("models", [])
    have = {r["name"] for r in rows}
    add = []
    for r in ordered_records(facts):
        p = r.get("price")
        if not p:
            continue
        name = p.get("name") or r["names"]["ja"]
        if name in have:
            continue
        add.append({
            "name": name,
            "provider": p.get("provider") or "other",
            "label": p.get("label") or r.get("provider", "Other"),
            "input": p["input"], "output": p["output"],
            "note": p.get("note_ja", ""), "note_en": p.get("note_en", ""),
        })
    if not add:
        return False
    cur["models"] = add + rows
    cur["updated"] = TODAY
    path.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


# --------------------------------------------------------------------------- 3. changelog
def changelog_events(facts: dict):
    ev = []
    for r in facts.get("models", {}).values():
        if r.get("released"):
            ev.append({
                "date": r["released"], "kind": "model",
                "key": r["id"],
                "ja": "%s を掲載（%s）" % (r["names"]["ja"].strip(), r.get("provider", "")),
                "en": "Listed %s (%s)" % ((r["names"]["en"] or r["names"]["ja"]).strip(), r.get("provider", "")),
            })
        for e in r.get("events", []):
            ev.append(dict(e, kind=e.get("kind", "update"), key=r["id"]))
    # site_events は「後ろに足したものが新しい」。同じ日付では**足した順の逆**を先に出す。
    # 2026-11-15: key のアルファベット順で並べていたため、その日に公開した新ページが
    # トップの「直近5件」から外れた（課題141 の実体）。
    for e in facts.get("site_events", []):
        ev.append(e)
    for i, e in enumerate(ev):
        e["_seq"] = i
    ev.sort(key=lambda e: (e.get("date", ""), e.get("_seq", 0)), reverse=True)
    for e in ev:
        e.pop("_seq", None)
    return ev


def _header_footer(site: Path, lang: str):
    src = site / ("pricing/index.html" if lang == "ja" else "en/pricing/index.html")
    s = src.read_text(encoding="utf-8")
    h = re.search(r"<header class=\"site-header\">.*?</header>", s, re.S).group(0)
    f = re.search(r"<footer class=\"site-footer\">.*?</footer>", s, re.S).group(0)
    return h, f


def render_changelog(site: Path, facts: dict) -> list:
    events = changelog_events(facts)
    (site / "data" / "changelog.json").write_text(
        json.dumps({"updated": TODAY, "events": events}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    touched = []
    for lang, prefix, slug in (("ja", "", "changelog"), ("en", "en/", "changelog")):
        rel = "%s%s/index.html" % (prefix, slug)
        path = site / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        header, footer = _header_footer(site, lang)
        if lang == "ja":
            title = "更新履歴（サイト全体） — LLM Data Hub"
            desc = "LLM Data Hub に掲載したモデルと事実の更新履歴を1ページに集約。日付・対象・変更内容を機械生成で記録します。"
            h1 = "更新履歴"
            sub = "このサイトに何をいつ載せたかの一覧です。各ページの更新履歴はこの台帳から生成されるため、食い違いません。"
            canon = "https://llm.okamomedia.tokyo/changelog/"
            th_date, th_kind = "日付", "内容"
        else:
            title = "Changelog (all pages) — LLM Data Hub"
            desc = "Every model and fact added to LLM Data Hub, in one generated list. Dates, targets and changes are produced from a single source of truth."
            h1 = "Changelog"
            sub = "What was added to this site and when. Page-level histories are generated from this ledger, so they cannot drift apart."
            canon = "https://llm.okamomedia.tokyo/en/changelog/"
            th_date, th_kind = "Date", "Change"
        # 専用OG（ja-changelog.png / en-changelog.png）。2026-11-15 に生成済み。
        og = "https://llm.okamomedia.tokyo/assets/og/%s-changelog.png" % lang
        ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title,
              "dateModified": TODAY, "inLanguage": lang, "url": canon,
              "isAccessibleForFree": True, "description": desc}
        rows = "\n".join(
            '<li><span class="cl-date">%s</span> <span class="cl-text">%s</span></li>'
            % (e.get("date", ""), e.get("ja" if lang == "ja" else "en") or e.get("ja", ""))
            for e in events[:200])
        html = """<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="{canon}">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta property="og:image" content="{og}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{alt}">
  <meta name="twitter:image" content="{og}">
  <meta name="twitter:image:alt" content="{alt}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canon}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{ld}</script>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-MTH8T0ECG2"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-MTH8T0ECG2');</script>
  <link rel="stylesheet" href="/assets/style.css">
  <style>
    ul.changelog{{list-style:none;padding:0;margin:0}}
    ul.changelog li{{border-top:1px solid var(--c-border);padding:.6rem .1rem;line-height:1.7;font-size:.88rem;display:flex;gap:.9rem}}
    ul.changelog li:first-child{{border-top:0}}
    .cl-date{{font-family:var(--font-mono);color:var(--c-muted);white-space:nowrap;font-size:.8rem;padding-top:.15rem}}
    .cl-text{{flex:1}}
  </style>
  <link rel="alternate" hreflang="ja" href="https://llm.okamomedia.tokyo/changelog/">
  <link rel="alternate" hreflang="en" href="https://llm.okamomedia.tokyo/en/changelog/">
  <link rel="alternate" hreflang="x-default" href="https://llm.okamomedia.tokyo/changelog/">
</head>
<body>
{header}
<main>
<div class="container" style="padding-top:2rem;">
<h1 class="section-title" style="font-size:1.6rem;">{h1}</h1>
<p class="section-sub" style="max-width:780px;">{sub}</p>
<div class="updated-bar"><span class="dot">●</span>{updated_label}: <time datetime="{today}">{today_text}</time></div>
<div style="background:var(--c-surface);border:1px solid var(--c-border);border-radius:var(--r-md);padding:1rem 1.25rem;">
<ul class="changelog">
{rows}
</ul>
</div>
</div>
</main>
{footer}
</body>
</html>
""".format(
            lang=lang, title=title, desc=desc, canon=canon, og=og,
            alt=("LLM Data Hub の更新履歴（全ページ横断）" if lang == "ja"
                 else "Changelog across all LLM Data Hub pages"),
            ld=json.dumps(ld, ensure_ascii=False),
            header=header, footer=footer, h1=h1, sub=sub,
            updated_label=("最終更新" if lang == "ja" else "Last updated"),
            today=TODAY,
            today_text=_date_text(lang),
            rows=rows)
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if old != html:
            path.write_text(html, encoding="utf-8")
            touched.append(rel)
    return touched


# ---------------------------------------------------------------------------
# 4. トップページ（最終更新・直近の更新・主要ページ）
#    「最終更新」を文章で手書きしていたため 11-07 の記述が11-14まで残り、
#    「Gemini 4 Carbon は限定提供」という事実誤認がトップに居座った（課題103）。
#    日付も本文も台帳から生成し、手書きを禁止する。
TOP_BEGIN = "<!-- topcl:begin -->"
TOP_END = "<!-- topcl:end -->"

TOP_MAIN_LINKS = {
    "ja": [("/pricing/", "料金比較"), ("/calculator/", "トークン計算機"),
           ("/timeline/", "リリース年表"), ("/changelog/", "更新履歴"),
           ("/china-ai/", "中国AI"), ("/glossary/", "用語説明")],
    "en": [("/en/pricing/", "Pricing"), ("/en/calculator/", "Token calculator"),
           ("/en/timeline/", "Timeline"), ("/en/changelog/", "Changelog"),
           ("/en/china-ai/", "China AI"), ("/en/glossary/", "Glossary")],
}
_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _fmt_date(iso: str, lang: str) -> str:
    """2026-11-14 -> 2026年11月14日 / November 14, 2026"""
    try:
        y, m, d = (int(x) for x in iso.split("-"))
    except (ValueError, AttributeError):
        return iso
    if lang == "ja":
        return "%d年%d月%d日" % (y, m, d)
    if not 1 <= m <= 12:
        return iso
    return "%s %d, %d" % (_MONTHS[m - 1], d, y)


def top_block(events, lang: str, n: int = 5) -> str:
    """トップに埋め込む「直近の更新＋主要ページ」を組み立てる（2026-11-15 改訂）。

    okamoの指摘: 「最終更新: …」の帯と「更新履歴は事実台帳から生成…」の但し書きが
    見出し「直近の更新」と重複していて冗長。**日付は見出し直下の1行に集約**し、
    実装の説明文は出さない。
    """
    latest = events[0]["date"] if events else TODAY
    if lang == "ja":
        h2, cta = "直近の更新", "すべての更新履歴（%d件）を見る →" % len(events)
        stamp = '最終更新: <time datetime="%s">%s</time>' % (
            latest, _fmt_date(latest, lang))
        main, cl_url = "主要ページ", "/changelog/"
    else:
        h2, cta = "Recent updates", "See all %d updates &rarr;" % len(events)
        stamp = 'Last updated: <time datetime="%s">%s</time>' % (
            latest, _fmt_date(latest, lang))
        main, cl_url = "Main pages", "/en/changelog/"
    rows = "\n".join(
        '<li><span class="cl-date">%s</span> <span class="cl-text">%s</span></li>'
        % (e.get("date", ""), (e.get(lang) or e.get("ja", "")).strip())
        for e in events[:n])
    links = " · ".join('<a href="%s">%s</a>' % (u, name)
                       for u, name in TOP_MAIN_LINKS[lang])
    return (
        '<section class="section" aria-labelledby="cl" style="padding-top:1.25rem;">'
        '<h2 class="section-title" id="cl">%s</h2>'
        '<p class="section-sub">%s</p>\n'
        '<ul class="cl-list">\n%s\n</ul>\n'
        '<p style="margin-top:1.25rem;"><a class="hero-cta" href="%s">%s</a></p>\n'
        '<p class="mp-links"><strong>%s:</strong> %s</p>\n'
        '</section>'
        % (h2, stamp, rows, cl_url, cta, main, links))


def render_home(site: Path, facts: dict) -> list:
    """index.html / en/index.html のマーカー間を生成内容で置き換える。

    マーカー（<!-- topcl:begin --> … <!-- topcl:end -->）が無いページは触らない。
    手書きのトップを機械が壊さないための安全弁。
    """
    events = changelog_events(facts)
    if not events:
        return []
    touched = []
    for rel, lang in (("index.html", "ja"), ("en/index.html", "en")):
        path = site / rel
        if not path.exists():
            continue
        s = path.read_text(encoding="utf-8")
        i, j = s.find(TOP_BEGIN), s.find(TOP_END)
        if i < 0 or j < i:
            continue
        new = (s[:i] + TOP_BEGIN + "\n" + top_block(events, lang) + "\n" + TOP_END
               + s[j + len(TOP_END):])
        # meta description に日付を埋めている場合も同じ日付に揃える
        # （手書きの「（2026年11月7日更新）」が11-14まで残っていた）
        if lang == "ja":
            new = re.sub(r"（\d{4}年\d{1,2}月\d{1,2}日更新）",
                         "（%s更新）" % _fmt_date(events[0]["date"], "ja"),
                         new, count=1)
        if new != s:
            path.write_text(new, encoding="utf-8")
            touched.append(rel)
    return touched


# --------------------------------------------------------------------------- 4. sitemap / llms
def render_sitemap(site: Path, touched) -> bool:
    path = site / "sitemap.xml"
    s = path.read_text(encoding="utf-8")
    orig = s
    for rel in touched:
        prefix = "en/" if rel.startswith("en/") else ""
        key = rel[len(prefix):-len("index.html")]
        url = "https://llm.okamomedia.tokyo/%s%s" % (prefix, key)
        if "<loc>%s</loc>" % url in s:
            s = re.sub(r"(<loc>%s</loc>\s*<lastmod>)[0-9-]+(</lastmod>)" % re.escape(url),
                       r"\g<1>%s\g<2>" % TODAY, s)
        else:
            # 新しいページは urlset の末尾に足す（既存の書式に合わせる）
            block = ('<url><loc>%s</loc><lastmod>%s</lastmod>'
                     "<changefreq>weekly</changefreq><priority>0.5</priority></url>\n"
                     % (url, TODAY))
            s = s.replace("</urlset>", block + "</urlset>")
    if orig == s:
        return False
    path.write_text(s, encoding="utf-8")
    return True


# ----------------------------------------------------------------- 5. 特集ページ本文（R16-a）
# 背景（2026-11-15）:
#   特集ページ（/china-ai/ 等）の本文は ja/en で別々のHTMLに手書きされていたため、
#   「Aだけ直してB漏れ」が構造的に起きる。本文を台帳の**1レコード2フィールド**
#   （heading.ja / heading.en, body.ja / body.en）に移し、日英を同じレコードから
#   出す。片方だけ直すことは物理的にできなくなる。
FEATURE_PAGES = (
    "china-ai",
    "multimodal",
    "mai",
    "speech-api-pricing",
    "image-api-pricing",
)
H2_BLOCK_RE = re.compile(r'<h2([^>]*\bclass="section-title"[^>]*)>(.*?)</h2>', re.S)
H2_ID_RE = re.compile(r'\bid="([^"]+)"')


def _block_spans(text: str) -> list:
    """`class="section-title"` の h2 を区切りに本文ブロックの位置を返す。

    本文の終端は「次の h2」と「</section>」の**近いほう**にする。こうすると
    1セクションに複数 h2 があるページ（/speech-api-pricing/）でも、h2 ごとに
    セクションが分かれるページ（/china-ai/）でも同じ規則で切り出せる。
    """
    spans = []
    ms = list(H2_BLOCK_RE.finditer(text))
    for i, m in enumerate(ms):
        idm = H2_ID_RE.search(m.group(1))
        hid = idm.group(1) if idm else "block-%d" % i
        ends = [len(text)]
        if i + 1 < len(ms):
            ends.append(ms[i + 1].start())
        sec_end = text.find("</section>", m.end())
        if sec_end != -1:
            ends.append(sec_end)
        spans.append({
            "start": m.start(),
            "open_end": m.start(2),      # `<h2 ...>` の直後（見出し本体の直前）
            "inner": m.group(2),
            "body_start": m.end(),       # `</h2>` の直後
            "body_end": min(ends),
            "id": hid,
        })
    return spans


def extract_features(site: Path, ws: Path) -> dict:
    """ページ本文を台帳へ写す（移行用。通常の run() からは呼ばない）。"""
    fp = ws / FACTS_REL
    facts = json.loads(fp.read_text(encoding="utf-8"))
    features = dict(facts.get("features") or {})
    for slug in FEATURE_PAGES:
        ja_p = site / slug / "index.html"
        en_p = site / "en" / slug / "index.html"
        if not (ja_p.exists() and en_p.exists()):
            print("  skip（未作成）: %s" % slug)
            continue
        tj = ja_p.read_text(encoding="utf-8")
        te = en_p.read_text(encoding="utf-8")
        sj, se = _block_spans(tj), _block_spans(te)
        if len(sj) != len(se):
            raise SystemExit("%s: 日英でブロック数が違う (ja=%d en=%d)" % (slug, len(sj), len(se)))
        blocks = []
        for a, b in zip(sj, se):
            if a["id"] != b["id"]:
                raise SystemExit("%s: 見出しidが違う (%s / %s)" % (slug, a["id"], b["id"]))
            body = {"ja": tj[a["body_start"]:a["body_end"]],
                    "en": te[b["body_start"]:b["body_end"]]}
            for lang, bd in body.items():
                if "</section>" in bd or 'class="section-title"' in bd:
                    raise SystemExit("%s/%s/%s: 本文にブロック境界が混ざっている"
                                     % (slug, a["id"], lang))
            blocks.append({
                "id": a["id"],
                "heading": {"ja": a["inner"], "en": b["inner"]},
                "body": body,
            })
        features[slug] = {"blocks": blocks}
        print("  %-22s %d blocks" % (slug, len(blocks)))
    facts["features"] = features
    fp.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    return features


def render_features(site: Path, facts: dict) -> list:
    """特集ページの本文を台帳から書き戻す（ja/en を同一レコードから出す）。"""
    changed = []
    for slug, rec in sorted((facts.get("features") or {}).items()):
        blocks = rec.get("blocks") or []
        for lang, rel in (("ja", "%s/index.html" % slug),
                          ("en", "en/%s/index.html" % slug)):
            p = site / rel
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            spans = _block_spans(text)
            if len(spans) != len(blocks):
                print("  !! %s: 台帳%d件 / ページ%d件 で不一致（触らない）"
                      % (rel, len(blocks), len(spans)))
                continue
            out = text
            ok = True
            for sp, blk in reversed(list(zip(spans, blocks))):
                if sp["id"] != blk["id"]:
                    print("  !! %s: 見出しid不一致 %s != %s（触らない）"
                          % (rel, sp["id"], blk["id"]))
                    ok = False
                    break
                head = blk["heading"].get(lang, "")
                body = blk["body"].get(lang, "")
                if not head or not body.strip():
                    print("  !! %s/%s: %s が空（触らない）" % (rel, sp["id"], lang))
                    ok = False
                    break
                rep = text[sp["start"]:sp["open_end"]] + head + "</h2>" + body
                out = out[:sp["start"]] + rep + out[sp["body_end"]:]
            if ok and out != text:
                p.write_text(out, encoding="utf-8")
                changed.append(rel)
    return changed


def run(site: Path, ws: Path) -> list[str]:
    """台帳から生成し、変更したファイルの一覧を返す（冪等）。"""
    facts = load_facts(ws)
    ids = [r["id"] for r in ordered_records(facts) if r.get("timeline", {}).get("ja_id")]
    changed = []
    for rel, lang in (("timeline/index.html", "ja"), ("en/timeline/index.html", "en")):
        # 先に見出し・説明文を台帳から書き戻す（R5）。並べ替えはその後。
        prose = render_timeline_prose(site, rel, lang, facts)
        did = render_timeline(site, rel, lang, ids)
        if prose:
            print("  timeline prose: %s %d件" % (rel, len(prose)))
        if prose or did:
            changed.append(rel)
    for rel, lang in (("pricing/index.html", "ja"), ("en/pricing/index.html", "en")):
        before = (site / rel).read_text(encoding="utf-8") if (site / rel).exists() else ""
        render_pricing(site, rel, lang, facts)
        for err in PRICING_ERRORS:
            print("  pricing SKIP: %s" % err)
        after = (site / rel).read_text(encoding="utf-8") if (site / rel).exists() else ""
        if before != after:
            changed.append(rel)
    # 特集ページの本文（R16-a）。台帳が正で、HTMLの手編集は次の描画で戻る。
    for rel in render_features(site, facts):
        changed.append(rel)
    if render_models_json(site, facts):
        changed.append("data/models.json")
    touched = render_changelog(site, facts)
    changed.extend(touched)
    home = render_home(site, facts)
    changed.extend(home)
    if home:
        # トップは日英で同じ台帳から出るので、片方が変われば両方の
        # sitemap lastmod を揃える（11-14: /en/ だけ 11-07 で残った）
        touched.extend(["index.html", "en/index.html"])
    if render_sitemap(site, touched):
        changed.append("sitemap.xml")
    return changed


@tool
def render_site() -> dict:
    """事実台帳（/workspace/data/facts.json）から timeline・計算機データ・更新履歴を生成する。

    **公開前の定型作業**。timeline の並び順（日付降順）・ja/en の一致・
    data/models.json の追加・/changelog/ の更新・sitemap lastmod を機械で揃える。
    何度実行しても結果は変わらない（冪等）。LLMコストは0。

    facts.json に事実を1件足してからこれを実行すれば、並び順や日英同期を手で直す
    必要はない（2026-11-14: 追記運用で降順が崩れ、ENだけ5件欠けた）。
    """
    site = Path(DEFAULT_SITE)
    ws = Path(DEFAULT_WS)
    try:
        changed = run(site, ws)
    except SystemExit as e:
        return {"status": "failed", "reason": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "reason": "%s: %s" % (type(e).__name__, e)}
    return {"status": "ok", "changed": changed,
            "note": "0件なら既に一致している。1件以上あるなら check_site_pages / check_dates を通してから site_upload"}


TOOL = render_site


def main(argv):
    site = Path(DEFAULT_SITE)
    ws = Path(DEFAULT_WS)
    for flag, attr in (("--site", "site"), ("--workspace", "ws")):
        if flag in argv:
            v = Path(argv[argv.index(flag) + 1])
            site, ws = (v, ws) if attr == "site" else (site, v)
    if "--check" in argv:
        facts = load_facts(ws)
        print("[check] facts.models=%d / features=%d"
              % (len(facts.get("models", {})), len(facts.get("features") or {})))
        return
    if "--extract-features" in argv:
        # 移行用（1回だけ）。ページ本文を台帳の1レコード2フィールドへ写す。
        feats = extract_features(site, ws)
        print("extract: %d page(s)" % len(feats))
        return
    changed = run(site, ws)
    print("render: %d file(s) changed" % len(changed))
    for c in changed:
        print("  -", c)


if __name__ == "__main__":
    main(sys.argv[1:])

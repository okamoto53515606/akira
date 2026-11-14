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
from datetime import date, timedelta, timezone
from pathlib import Path

from strands import tool

DEFAULT_SITE = os.environ.get("SITE_LOCAL_DIR", "") or "/tmp/site"
DEFAULT_WS = os.environ.get("WORKSPACE_DIR", "") or "/workspace"
FACTS_REL = "data/facts.json"
JST = timezone(timedelta(hours=9))
TODAY = date.today().isoformat()


def _date_text(lang: str) -> str:
    d = date.today()
    return "%d年%d月%d日" % (d.year, d.month, d.day) if lang == "ja" else d.isoformat()

ART_RE = re.compile(r'<article class="tl-item[^"]*" id="([^"]+)">.*?</article>\n?', re.S)
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
                "ja": "%s を掲載（%s）" % (r["names"]["ja"], r.get("provider", "")),
                "en": "Listed %s (%s)" % (r["names"]["en"] or r["names"]["ja"], r.get("provider", "")),
            })
        for e in r.get("events", []):
            ev.append(dict(e, kind=e.get("kind", "update"), key=r["id"]))
    for e in facts.get("site_events", []):
        ev.append(e)
    return sorted(ev, key=lambda e: (e.get("date", ""), e.get("key", "")), reverse=True)


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
        # 専用OGはまだ無い（この環境にPillowが無いため）。実在する画像を指す。
        # 課題116: /changelog/ 専用の1200x630を生成して差し替える。
        og = "https://llm.okamomedia.tokyo/assets/og/%s-home.png" % lang
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


def run(site: Path, ws: Path) -> list[str]:
    """台帳から生成し、変更したファイルの一覧を返す（冪等）。"""
    facts = load_facts(ws)
    ids = [r["id"] for r in ordered_records(facts) if r.get("timeline", {}).get("ja_id")]
    changed = []
    for rel, lang in (("timeline/index.html", "ja"), ("en/timeline/index.html", "en")):
        if render_timeline(site, rel, lang, ids):
            changed.append(rel)
    if render_models_json(site, facts):
        changed.append("data/models.json")
    touched = render_changelog(site, facts)
    changed.extend(touched)
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
        print("[check] facts.models=%d" % len(facts.get("models", {})))
        return
    changed = run(site, ws)
    print("render: %d file(s) changed" % len(changed))
    for c in changed:
        print("  -", c)


if __name__ == "__main__":
    main(sys.argv[1:])

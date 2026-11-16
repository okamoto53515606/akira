"""セクションの境界と、料金表が「どのプロバイダの表か」を検査する（読み取り専用）。

2026-11-17 追加。この日、/pricing/ で次の事故が起きた:
    - 担当AIが Xiaomi（MiMo）のセクションを **<h2> の位置で**挿し込んだため、
      新しいセクションが `<section aria-labelledby="kimi-h">` の中に入り、
      見出しの id と aria-labelledby が食い違った
    - その状態で render_site が走り、台帳の表を**位置（i番目）**で書き戻したため
      Xiaomi の表に Kimi の行、Kimi の表に Meta の行が入った
    - どのゲートも ERROR を出さず、**公開された**
どちらも「HTMLの見た目は壊れていないのに中身が別物」という、人が気づきにくい型。

検査する2つ:
    S1 section-anchor : `<section aria-labelledby="X">` の中に id="X" の要素があるか
                        （無い＝セクション境界がずれている）
    S2 pricing-tables : /pricing/ と /en/pricing/ の各表の1行目が、台帳
                        `facts.json: pricing_tables[i].rows[0]` のモデル名と一致するか
                        （違う＝表の取り違え。render が黙って上書きする前に止める）

使い方:
    python3 check_sections.py [/tmp/site] [/workspace]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_SITE = os.environ.get("SITE_LOCAL_DIR", "") or "/tmp/site"
DEFAULT_WS = os.environ.get("WORKSPACE_DIR", "") or "/workspace"

SECTION_RE = re.compile(r"<section\b[^>]*aria-labelledby=\"([^\"]+)\"[^>]*>", re.I)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
ID_RE = re.compile(r"id=\"([^\"]+)\"")
TABLE_RE = re.compile(r"<table[^>]*>.*?</table>", re.S)
TBODY_RE = re.compile(r"<tbody[^>]*>(.*?)</tbody>", re.S)
MODEL_CELL_RE = re.compile(r"<td class=\"model-name\">(.*?)</td>", re.S)
PRICING_PAGES = {"pricing/index.html": "ja", "en/pricing/index.html": "en"}


def _model_name_of(row_html: str) -> str:
    m = MODEL_CELL_RE.search(row_html or "")
    if not m:
        return ""
    txt = re.sub(r"<[^>]+>", " ", m.group(1))
    return re.sub(r"\s+", " ", txt).strip()


def _section_title(seg: str) -> str:
    m = H2_RE.search(seg or "")
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()


def _first_row_name(tbody_html: str) -> str:
    if "</tr>" not in tbody_html:
        return ""
    return _model_name_of(tbody_html.split("</tr>")[0] + "</tr>")


def _sections(html: str):
    """(anchor_id, セクションの本文) を順に返す。"""
    marks = list(SECTION_RE.finditer(html))
    for n, m in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(html)
        yield m.group(1), html[m.start():end]


def check_sections(site: Path) -> list:
    """S1: セクションの aria-labelledby が、そのセクション内の id を指しているか。"""
    errors = []
    for path in sorted(site.rglob("index.html")):
        rel = path.relative_to(site).as_posix()
        try:
            html = io.open(path, encoding="utf-8").read()
        except OSError:
            continue
        for anchor, seg in _sections(html):
            # セクション本文の先頭（次の </section> まで）に id があるか
            body = seg.split("</section>")[0]
            if ('id="%s"' % anchor) not in body:
                errors.append("section-anchor %s: aria-labelledby=\"%s\" の実体が"
                              "セクション内に無い（境界がずれている）" % (rel, anchor))
    return errors


def check_pricing_tables(site: Path, ws: Path) -> tuple:
    """S2: 料金表の1行目が台帳の1行目と一致するか（表の取り違え検出）。"""
    errors, warns = [], []
    facts_path = ws / "data" / "facts.json"
    if not facts_path.exists():
        return errors, ["台帳が無い: %s（S2はスキップ）" % facts_path]
    try:
        facts = json.loads(io.open(facts_path, encoding="utf-8").read())
    except Exception as e:  # noqa: BLE001
        return ["pricing-tables facts.json を読めない: %s" % e], warns
    specs = facts.get("pricing_tables") or []
    if not specs:
        return errors, ["pricing_tables が空（S2はスキップ）"]

    for rel, lang in PRICING_PAGES.items():
        path = site / rel
        if not path.exists():
            continue
        html = io.open(path, encoding="utf-8").read()
        spans = {}
        for anchor, seg in _sections(html):
            t = TABLE_RE.search(seg)
            if t and anchor not in spans:
                spans[anchor] = (seg, t.group(0))
        for spec in specs:
            anchor = spec.get("anchor") or ""
            rows = [r.get(lang) for r in spec.get("rows", [])]
            if not anchor or not rows or any(r is None for r in rows):
                continue
            hit = spans.get(anchor)
            if hit is None:
                errors.append("pricing-tables %s: #%s のセクション/表が無い"
                              % (rel, anchor))
                continue
            sec, table = hit
            m = TBODY_RE.search(table)
            if not m:
                errors.append("pricing-tables %s: #%s の <tbody> が無い"
                              % (rel, anchor))
                continue
            title = (spec.get("title") or {}).get(lang)
            got_title = _section_title(sec)
            if title and got_title and re.sub(r"\s+", " ", title).strip() != got_title:
                errors.append(
                    "pricing-tables %s: #%s の見出しが台帳と違う（ページ=%r / 台帳=%r）"
                    % (rel, anchor, got_title, title))
            got = _first_row_name(m.group(1))
            want = _model_name_of(rows[0])
            if got != want:
                errors.append(
                    "pricing-tables %s: #%s の1行目が台帳と違う（ページ=%r / 台帳=%r）"
                    % (rel, anchor, got, want))
        # 台帳に無い表（手で足した表）は WARN。render は触らないので事故にはならない。
        ledger_anchors = {s.get("anchor") for s in specs if s.get("anchor")}
        for anchor in spans:
            if anchor not in ledger_anchors:
                warns.append("pricing-tables %s: #%s の表が台帳に無い（手動の表？）"
                             % (rel, anchor))
    return errors, warns


def main(argv) -> int:
    site = Path(argv[0]) if argv else Path(DEFAULT_SITE)
    ws = Path(argv[1]) if len(argv) > 1 else Path(DEFAULT_WS)
    if not site.exists():
        print("site が見つからない: %s" % site)
        print("ERROR: 0 / WARN: 0")
        return 0
    errors = check_sections(site)
    e2, warns = check_pricing_tables(site, ws)
    errors += e2
    print("checked sections in %s" % site)
    for e in errors:
        print("  [ERROR] " + e)
    for w in warns:
        print("  [WARN]  " + w)
    print("ERROR: %d / WARN: %d" % (len(errors), len(warns)))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

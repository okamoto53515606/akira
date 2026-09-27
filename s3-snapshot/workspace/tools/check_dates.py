"""日付整合チェック（三点整合＋description内日付）。

検査内容:
  1) sitemap.xml lastmod / JSON-LD dateModified / 本文 <time datetime> の三点整合
  2) meta description・og:description・twitter:description に埋まった
     「更新日」表現の日付が、そのページの宣言日付（dateModified / 本文日付）と一致するか

description の日付は「更新」に係るものだけを見る（リリース日・プロモ期限など
無関係な日付を誤検知しないため）:
  - 日本語: 「2026年9月23日更新」「最終更新日: 2026年9月23日」
  - 英語  : 「Updated Sep 23, 2026」「(updated September 23, 2026)」
  ※ "Released Sept 22, 2026. Updated Sept 25, 2026." の前半（Released）は対象外。

使い方（shell から）:
    python3 /workspace/tools/check_dates.py [/tmp/site]

出力: 不一致 URL の一覧。一致していれば NG: 0。
"""
from __future__ import annotations

import io
import os
import re
from typing import Optional

from strands import tool

# 2026-09-27 修正: 従来は "/tmp/site" が先頭だったため、SITE_LOCAL_DIR を明示しても
# /tmp/site が存在するとそちらを見ていた（別ディレクトリを検査して偽OKを出す危険）。
# ドキュメントどおり「SITE_LOCAL_DIR → /tmp/site」の順にする。
DEFAULT_SITE_DIRS = (os.environ.get("SITE_LOCAL_DIR", ""), "/tmp/site")

DESC_KEYS = ("name=\"description\"", "property=\"og:description\"", "name=\"twitter:description\"")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# 「…日更新」/「更新日: …」
_RE_JP_AFTER = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日(?:に)?更新")
_RE_JP_BEFORE = re.compile(r"更新(?:日)?[:：]?\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")
# "Updated Sep 23, 2026" / "(updated September 23, 2026)"
_RE_EN = re.compile(r"[Uu]pdated:?\s+([A-Z][a-z]{2})[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})")


def _read(path: str) -> Optional[str]:
    try:
        with io.open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _local_path(site_dir: str, loc: str) -> str:
    rel = re.sub(r"^https?://[^/]+/", "", loc.strip()).strip("/")
    if rel == "" or rel.endswith("/"):
        rel = rel + "index.html" if rel else "index.html"
    elif not rel.endswith((".html", ".xml")):
        rel = rel + "/index.html"
    return os.path.join(site_dir, rel)


def _jsonld_date(html: str) -> Optional[str]:
    m = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    return m.group(1) if m else None


def _visible_date(html: str) -> Optional[str]:
    m = re.search(r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})"', html)
    return m.group(1) if m else None


def desc_update_dates(html: str) -> list:
    """description系metaに埋まった「更新日」を (metaキー名, ISO日付) で返す。"""
    out = []
    for tag in re.findall(r"<meta[^>]*>", html):
        key = None
        for k in DESC_KEYS:
            if k in tag:
                key = k.split("=", 1)[1].strip('"')
                break
        if key is None:
            continue
        m = re.search(r'content="([^"]*)"', tag)
        if not m:
            continue
        text = m.group(1)
        for mm in _RE_JP_AFTER.finditer(text):
            out.append((key, "%04d-%02d-%02d" % (int(mm.group(1)), int(mm.group(2)), int(mm.group(3)))))
        for mm in _RE_JP_BEFORE.finditer(text):
            out.append((key, "%04d-%02d-%02d" % (int(mm.group(1)), int(mm.group(2)), int(mm.group(3)))))
        for mm in _RE_EN.finditer(text):
            mon = _MONTHS.get(mm.group(1).lower())
            if mon:
                out.append((key, "%s-%02d-%02d" % (mm.group(3), mon, int(mm.group(2)))))
    return out


def scan(site_dir: str) -> list:
    sm = _read(os.path.join(site_dir, "sitemap.xml"))
    if sm is None:
        raise SystemExit("sitemap.xml not found in %s" % site_dir)
    rows = []
    for loc, lastmod in re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", sm, re.S):
        fp = _local_path(site_dir, loc)
        html = _read(fp)
        if html is None:
            rows.append((loc, lastmod, "MISSING", "MISSING", fp, []))
            continue
        rows.append((loc, lastmod.strip(), _jsonld_date(html), _visible_date(html), fp,
                     desc_update_dates(html)))
    return rows


def report(site_dir: str) -> str:
    rows = scan(site_dir)
    lines = ["checked %d urls in %s" % (len(rows), site_dir)]
    ng = 0
    desc_seen = 0
    for loc, lastmod, jd, vd, fp, descs in rows:
        problems = []
        declared = None
        if jd == "MISSING":
            problems.append("ファイル無し")
        else:
            known = [v for v in (lastmod, jd, vd) if v]
            if len(set(known)) > 1:
                problems.append(
                    "lastmod=%s / dateModified=%s / visible=%s"
                    % (lastmod, jd or "-", vd or "-")
                )
            declared = jd or vd
        for key, iso in descs:
            desc_seen += 1
            if declared and iso != declared:
                problems.append("%s の日付=%s (宣言=%s)" % (key, iso, declared))
        if problems:
            ng += 1
            lines.append("[NG] %s  %s" % (loc, " / ".join(problems)))
    lines.append("description日付 %d 件を検査" % desc_seen)
    lines.append("NG: %d / %d" % (ng, len(rows)))
    return "\n".join(lines)


@tool
def check_dates(site_dir: str = "") -> str:
    """日付整合チェック: sitemap lastmod / dateModified / 本文最終更新日の三点整合に加え、
    meta description・og:description に埋まった「更新日」の日付も宣言日付と突き合わせる。

    Args:
        site_dir: 検査するローカルサイトのディレクトリ。省略時は SITE_LOCAL_DIR、無ければ /tmp/site。
    """
    if not site_dir:
        for cand in DEFAULT_SITE_DIRS:
            if cand and os.path.isdir(cand):
                site_dir = cand
                break
    if not site_dir or not os.path.isdir(site_dir):
        return "site dir not found"
    return report(site_dir)


TOOL = check_dates

if __name__ == "__main__":
    import sys

    default = os.environ.get("SITE_LOCAL_DIR", "") or "/tmp/site"
    print(report(sys.argv[1] if len(sys.argv) > 1 else default))

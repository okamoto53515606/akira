"""サイト全体の整合チェッカー（重複・孤立リンク）。読み取り専用。

2026-11-15 追加。okamoの指摘から:
    「トップで同じことを2回書いていた（最終更新の帯と直近の更新）」
    「新しいページを作ったのに、どこからもリンクが無くて辿り着けない」
どちらも**人が気づくまで残る**種類の事故なので、機械で毎回見る。

検査する3つ:
    1. page-dup   : 同一ページ内で同じ文章が2回以上出る（重複記述）
    2. boilerplate: 同じ文章が3ページ以上に出る（全ページ共通の定型文）
    3. orphan     : 他のページからリンクされていないページ（導線漏れ）

除外:
    - <header> / <footer> / <nav> の中身（そもそも全ページ共通）
    - 表のセル（<td>/<th>）は比較対象にしない（同じ単価が並ぶのは正常）
    - ページ内リンク（#...）・外部リンク・mailto

使い方:
    python3 check_site_integrity.py <SITE_DIR>
    python3 check_site_integrity.py <SITE_DIR> --strict   # WARNもERROR扱い
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

STRIP_RE = re.compile(r"<(script|style|header|footer|nav|table)\b.*?</\1>", re.S)
BLOCK_RE = re.compile(r"<(p|li|h1|h2|h3|h4|div|section|dd|dt)\b[^>]*>(.*?)</\1>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
HREF_RE = re.compile(r'href="([^"]+)"')
WS_RE = re.compile(r"\s+")

MIN_PAGE_DUP = 40      # ページ内重複とみなす最小文字数
MIN_BOILER = 50        # 定型文とみなす最小文字数
BOILER_PAGES = 3       # 何ページ以上で定型文とみなすか
SKIP_ORPHAN = {"index.html", "404.html", "en/404.html"}


def _norm(text: str) -> str:
    t = TAG_RE.sub(" ", text)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    t = WS_RE.sub(" ", t).strip()
    return t


ANCHOR_RE = re.compile(r"<a\b[^>]*>.*?</a>", re.S)


def _blocks(html: str) -> list[str]:
    """本文の文章ブロックを取り出す（header/footer/nav/table は除外）。

    リンク集（`公式モデルページ → / 料金比較 →` のような並び）は、文章ではなく
    導線なので重複判定から外す。アンカーを除いた残りが短ければリンク集とみなす。
    """
    body = STRIP_RE.sub(" ", html)
    out = []
    for m in BLOCK_RE.finditer(body):
        inner = m.group(2)
        rest = _norm(ANCHOR_RE.sub(" ", inner))
        if "<a" in inner and len(rest) < 15:
            continue  # リンク集は対象外
        t = _norm(inner)
        if len(t) >= MIN_PAGE_DUP:
            out.append(t)
    return out


def _page_key(path: Path, site: Path) -> str:
    return path.relative_to(site).as_posix()


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_site_integrity.py <SITE_DIR> [--strict]")
        return 2
    site = Path(argv[0]).resolve()
    strict = "--strict" in argv
    if not site.is_dir():
        print("ERROR: site dir not found: %s" % site)
        return 2

    pages = sorted(site.rglob("index.html"))
    if not pages:
        print("ERROR: no index.html under %s" % site)
        return 2

    # --- 1/2: 重複の検出 -------------------------------------------------
    seen: dict[str, list[str]] = defaultdict(list)
    errors: list[str] = []
    warns: list[str] = []
    for p in pages:
        rel = _page_key(p, site)
        blocks = _blocks(p.read_text(encoding="utf-8"))
        counts = defaultdict(int)
        for b in blocks:
            counts[b] += 1
            seen[b].append(rel)
        for text, n in counts.items():
            if n >= 2:
                errors.append("page-dup %s: 同一ページ内に%d回: 「%s…」"
                              % (rel, n, text[:46]))

    for text, rels in seen.items():
        uniq = sorted(set(rels))
        if len(text) < MIN_BOILER:
            continue
        if len(uniq) >= BOILER_PAGES:
            errors.append("boilerplate %dページで同一文: 「%s…」（%s）"
                          % (len(uniq), text[:46], ", ".join(uniq[:4])))
        elif len(uniq) == 2:
            warns.append("shared-text 2ページで同一文: 「%s…」（%s）"
                         % (text[:46], ", ".join(uniq)))

    # --- 3: 孤立ページの検出 ---------------------------------------------
    inbound: dict[str, set[str]] = defaultdict(set)
    for p in pages:
        rel = _page_key(p, site)
        html = p.read_text(encoding="utf-8")
        for href in HREF_RE.findall(html):
            if href.startswith(("http", "#", "mailto:", "tel:", "javascript:")):
                continue
            target = href.split("#")[0].split("?")[0]
            if not target.endswith("/"):
                if target.endswith(".html"):
                    continue
                target += "/"
            if target.startswith("/"):
                key = target.lstrip("/") + "index.html"
            else:
                base = Path(rel).parent
                key = (base / target).as_posix().lstrip("./") + "index.html"
                key = re.sub(r"/+", "/", key)
            if key != rel:
                inbound[key].add(rel)

    for p in pages:
        rel = _page_key(p, site)
        if rel in SKIP_ORPHAN:
            continue
        if not inbound.get(rel):
            errors.append("orphan %s: 他のページからリンクされていない" % rel)

    # --- 出力 ------------------------------------------------------------
    print("checked %d pages in %s" % (len(pages), site))
    for e in errors:
        print("  [ERROR] " + e)
    for w in warns:
        print("  [WARN]  " + w)
    print("ERROR: %d / WARN: %d" % (len(errors), len(warns)))
    if errors:
        return 1
    if strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

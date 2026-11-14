"""ページの「形」を検査する（読みやすさ・日英の同格・レイアウト崩れ）。読み取り専用。

2026-11-15 追加。okamoの指摘から:
    「図を入れたがレイアウトが崩れている（コンテナの外に出ている）」
    「/timeline/ にだけ図を足して /en/timeline/ には無い（日英でちぐはぐ）」
    「本文が長すぎる」「文字が読めない」
どれも**人が見るまで残る**ので機械で見る。

検査する5つ:
    P1 container-escape : .diagram/.bars/.conclusion/.tint/.section が div.container の外にある
    P2 ja/en-parity     : 同じページの日英で 表・図・折りたたみ・h2 の数が違う
    P3 jp-in-en         : 英語ページに日本語の本文（ひらがな）が混入している
    P4 long-text        : 本文が長すぎる（ja 3,000字 / en 4,500字）
    P5 wide-table       : 表の列が6以上（横スクロールしないと読めない）

使い方:
    python3 check_page_shape.py <SITE_DIR>
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SKIP_TAGS = {"script", "style"}
WATCH_CLASSES = {"diagram", "bars", "conclusion", "tint", "section"}
MAX_TEXT = {"ja": 3000, "en": 4500}
MAX_COLS = 5
HIRA = re.compile(r"[\u3041-\u309F]")


class ShapeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set]] = []
        self.escapes: list[str] = []
        self.text_len = 0
        self.skip = 0
        self.tables: list[int] = []       # 列数
        self.cur_cols = 0
        self.counts = {"table": 0, "diagram": 0, "bars": 0, "details": 0, "h2": 0}
        self.hiragana = 0

    # --- helpers ---
    def _has_container(self) -> bool:
        return any("container" in cls for _t, cls in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag == "div" and "container" in classes:
            pass
        if classes & WATCH_CLASSES and not self._has_container():
            self.escapes.append("<%s class=%s>" % (tag, " ".join(sorted(classes & WATCH_CLASSES))))
        if tag == "table":
            self.counts["table"] += 1
            self.cur_cols = 0
        if tag == "tr":
            self.cur_cols = 0
        if tag == "details":
            self.counts["details"] += 1
        if tag == "h2":
            self.counts["h2"] += 1
        if "diagram" in classes:
            self.counts["diagram"] += 1
        if "bars" in classes:
            self.counts["bars"] += 1
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            return
        self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
        if tag == "table":
            self.tables.append(self.cur_cols)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.skip:
            return
        t = data.strip()
        if not t:
            return
        self.text_len += len(t)
        # 組織名「okamoちゃんねる」は英語ページでも日本語のまま（固有名詞）
        self.hiragana += len(HIRA.findall(t.replace("okamoちゃんねる", "")))


def _analyse(path: Path) -> ShapeParser:
    p = ShapeParser()
    p.feed(path.read_text(encoding="utf-8"))
    p.close()
    return p


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_page_shape.py <SITE_DIR>")
        return 2
    site = Path(argv[0]).resolve()
    if not site.is_dir():
        print("ERROR: site dir not found: %s" % site)
        return 2

    pages = {p.relative_to(site).as_posix(): p for p in site.rglob("index.html")}
    errors: list[str] = []
    warns: list[str] = []
    info = _analyse(pages["index.html"]) if "index.html" in pages else None

    for rel, path in sorted(pages.items()):
        lang = "en" if rel.startswith("en/") else "ja"
        a = info if (rel == "index.html" and info) else _analyse(path)

        # P1 コンテナ外
        if a.escapes:
            errors.append("container-escape %s: %d個が容器の外 → %s"
                          % (rel, len(a.escapes), ", ".join(a.escapes[:3])))
        # P3 英語ページに和文
        if lang == "en" and a.hiragana >= 3:
            errors.append("jp-in-en %s: ひらがな %d箇所（英語ページに和文の本文）"
                          % (rel, a.hiragana))
        # P4 長すぎる
        if a.text_len > MAX_TEXT[lang]:
            warns.append("long-text %s: 本文 約%d字（上限%d）"
                         % (rel, a.text_len, MAX_TEXT[lang]))
        # P5 列が多すぎ
        wide = [n for n in a.tables if n > MAX_COLS]
        if wide:
            warns.append("wide-table %s: 最大%d列（上限%d）"
                         % (rel, max(wide), MAX_COLS))

        # P2 日英の同格（ja 側から en 側を照合）
        if lang == "ja":
            en_rel = "en/" + rel
            b_path = pages.get(en_rel)
            if not b_path:
                errors.append("ja/en-parity %s: 英語版が無い（%s）" % (rel, en_rel))
                continue
            b = _analyse(b_path)
            diffs = []
            for k in ("table", "diagram", "bars", "details", "h2"):
                if a.counts[k] != b.counts[k]:
                    diffs.append("%s ja=%d/en=%d" % (k, a.counts[k], b.counts[k]))
            if diffs:
                errors.append("ja/en-parity %s: " % rel + " / ".join(diffs))

    print("checked %d pages in %s" % (len(pages), site))
    for e in errors:
        print("  [ERROR] " + e)
    for w in warns[:12]:
        print("  [WARN]  " + w)
    if len(warns) > 12:
        print("  [WARN]  … 他 %d 件（--all で全件）" % (len(warns) - 12))
    if "--all" in argv:
        for w in warns[12:]:
            print("  [WARN]  " + w)
    print("ERROR: %d / WARN: %d" % (len(errors), len(warns)))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

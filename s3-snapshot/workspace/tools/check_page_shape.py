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
# 「色で区別している」とみなすクラス（2026-11-15: okamo「色の変化が少なすぎる」）
PROVIDER_CLASSES = {"provider-tag", "tl-provider-tag", "badge", "st-cur", "st-old", "st-sun"}
ALT_TAG_RE = re.compile(r'<(\w+)([^>]*style="([^"]*)"[^>]*)>', re.S)
MEDIA_TAGS = {"img", "video", "iframe", "figure", "picture", "svg"}
INDEX_LIKE = {"index.html", "en/index.html",
              "changelog/index.html", "en/changelog/index.html"}  # 一覧が主役のページ
MONOTONE_ROWS = 10          # これ以上の行数の表が続くなら色分けを要求する
MIN_FIGURE_TEXT = 2000      # この文字数を超えるページは図が要る
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
        self.has_toc = False
        self.has_key_visual = False
        self.has_conclusion = False
        self.provider_color = 0          # provider-tag / dot-xxx などの色分け
        self.max_rows = 0               # 一番大きい表の行数
        self._rows = 0

    # --- helpers ---
    def _has_container(self) -> bool:
        return any("container" in cls for _t, cls in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag == "table":
            self._rows = 0
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
        if "toc" in classes:
            self.has_toc = True
        if "key-visual" in classes:
            self.has_key_visual = True
        if "conclusion" in classes:
            self.has_conclusion = True
        if classes & PROVIDER_CLASSES:
            self.provider_color += 1
        if tag == "tr":
            self._rows += 1
            self.max_rows = max(self.max_rows, self._rows)
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


def _og_key(path: Path) -> str:
    """そのページの og:image が指すローカル実ファイルのキー（無ければ空）。

    ファイルが実在するときだけ「貼り忘れ」と判定する（画像が無いページを
    ヒーロー画像なしで責めても直せないため）。
    """
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if not m or "/assets/og/" not in m.group(1):
        return ""
    key = "assets/og/" + m.group(1).rsplit("/assets/og/", 1)[1]
    site = path
    for _ in range(6):
        site = site.parent
        if (site / key).exists():
            return key
    return ""


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
        # P7 OG画像を作ってあるのにページに貼っていない（2026-11-15 追加）
        # okamo「/image-api-pricing/ はイメージ図がない」＝実際はOG画像が
        # できていたのに key-visual を入れ忘れていた。SNSで見る絵とページが別物。
        if not a.has_key_visual and rel not in INDEX_LIKE:
            og_key = _og_key(path)
            if og_key:
                errors.append("no-key-visual %s: og:image (%s) があるのに本文に貼って"
                              "いない → <figure class=\"key-visual\"> を入れる"
                              % (rel, og_key))
        # P8 長いのに図が1つも無い（2026-11-15 追加）
        if a.text_len > MIN_FIGURE_TEXT and not (a.counts.get("diagram") or a.counts.get("bars")):
            warns.append("no-figure %s: 本文 約%d字で .diagram も .bars も無い"
                          % (rel, a.text_len))
        # P12 箱（背景・枠線）に max-width を付けて右端が揃わない（2026-11-15 追加）
        # okamo「表の幅がずれてる」の実体。`.updated-bar` は容器いっぱい(1080px)
        # なのに、隣の「このページの範囲」だけ max-width:880px で右端が170pxずれる。
        # 文字だけの <p> は行長を抑えるため max-width を持ってよい。**箱はダメ**。
        for m in ALT_TAG_RE.finditer(path.read_text(encoding="utf-8")):
            tag, style = m.group(1).lower(), m.group(3)
            if tag in MEDIA_TAGS or "max-width" not in style:
                continue
            if not re.search(r"background|border", style):
                continue
            if "margin:0 auto" in style.replace(" ", ""):
                continue  # 中央寄せの画像・図は意図的
            warns.append("box-width %s: <%s> が箱なのに max-width を持つ（右端が揃わない）"
                         % (rel, tag))
        # P11 棒グラフが「何も語っていない」（2026-11-15 追加）
        # okamo 指摘: /image-api-pricing/ の棒が全部同じ長さ／空だった。
        # 数値の大小を見せるのが目的なので、幅が1種類しか無いなら図の意味が無い。
        widths = [float(x) for x in re.findall(
            r'class="bar-fill[^"]*"[^>]*style="width:\s*([0-9.]+)%', path.read_text(encoding="utf-8"))]
        if len(widths) >= 3 and len(set(widths)) == 1:
            errors.append("bar-flat %s: 棒%d本がすべて同じ幅(%.0f%%)で大小が伝わらない"
                          % (rel, len(widths), widths[0]))
        if widths and min(widths) <= 0:
            errors.append("bar-flat %s: 幅0%%の棒がある（値の取り違え）" % rel)
        # P9 色の変化が乏しい（2026-11-15 追加・okamo「色の変化が少なすぎる」）
        # 機械が見るのは「色分けクラスが0なのに大きな表がある」ケースだけ。
        # 色の良し悪し（単調かどうか）は Gemini の担当。
        if a.max_rows >= MONOTONE_ROWS and a.provider_color == 0:
            warns.append("monotone %s: %d行の表があるのに色分けクラスが0"
                         "（provider-tag / badge / 状態列など）"
                         % (rel, a.max_rows))
        # P10 長いのに結論ボックスが無い
        if a.text_len > MIN_FIGURE_TEXT * 1.5 and not a.has_conclusion:
            warns.append("no-conclusion %s: 本文 約%d字で .conclusion が無い"
                         % (rel, a.text_len))
        # P6 長いのに目次が無い（2026-11-15 追加）
        # 「長すぎる」を削って解決しようとすると出典を捨てることになる。
        # 実際の不満は「読めない」なので、h2が多くて長いページは目次を必須にする。
        if a.text_len > MAX_TEXT[lang] * 0.6 and 4 <= a.counts.get("h2", 0) <= 25 and not a.has_toc:
            errors.append("no-toc %s: 本文 約%d字 / h2 %d本なのに目次が無い"
                        % (rel, a.text_len, a.counts.get("h2", 0)))
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

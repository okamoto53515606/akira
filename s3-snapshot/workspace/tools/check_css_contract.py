# -*- coding: utf-8 -*-
"""CSS部品の「描画されるための必須プロパティ」を機械で確かめる。2026-11-15。

なぜ（okamo指摘 2件）:
    1. `/image-api-pricing/` の棒グラフが**空だった**。
       `.bar-track` / `.bar-fill` が `<span>`（インライン要素）なのに
       `display:block` が無く、**height が効かない**ため棒が描かれていなかった。
       HTMLは正しい（width:9% なども入っている）。CSSが悪い。
    2. `.updated-bar` が `display:flex` のため、文字列が flex item になり
       「Last / updated:」と折り返し、区切りの `|` が行頭に落ちていた。

再発防止の考え方:
    「インライン要素に高さを書いても効かない」のようなCKESSの落とし穴は、
    ページの中身を見ても分からない（HTMLは正しい）。だから **CSSそのものを検査する**。
    ここでは“部品が実在して、描画に必要なプロパティを持っているか”だけを見る。

使い方:
    python3 check_css_contract.py <SITE_DIR>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# class名 -> そのルールに必須のプロパティ（正規表現）
REQUIRED = {
    "bar-track": [r"display\s*:\s*block", r"height\s*:\s*\d"],
    "bar-fill": [r"display\s*:\s*block", r"height\s*:\s*100%"],
    "dg-box": [r"padding\s*:"],
    "diagram": [r"display\s*:\s*flex|display\s*:\s*grid"],
    "toc": [r"display\s*:\s*block"],          # nav はグローバルに flex なので明示が必要
}

# display:flex だとテキストが折り返して崩れる部品（ブロックであること）
MUST_BE_BLOCK = ["updated-bar"]


def _rules(css: str, cls: str) -> list[str]:
    """そのクラスを対象にした宣言ブロックを全部集める。"""
    out = []
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        sel, body = m.group(1), m.group(2)
        if re.search(r"\.%s(?![\w-])" % re.escape(cls), sel):
            out.append(body)
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_css_contract.py <SITE_DIR>")
        return 2
    css_path = Path(argv[0]).resolve() / "assets" / "style.css"
    if not css_path.exists():
        print("ERROR: style.css が見つからない: %s" % css_path)
        return 2
    css = css_path.read_text(encoding="utf-8")
    errors: list[str] = []

    for cls, pats in REQUIRED.items():
        bodies = _rules(css, cls)
        if not bodies:
            errors.append("css-contract: .%s のルールが無い（部品が消えた）" % cls)
            continue
        joined = "\n".join(bodies)
        for pat in pats:
            if not re.search(pat, joined):
                errors.append("css-contract: .%s に `%s` が無い → 描画されない可能性"
                              % (cls, pat.replace("\\s*", "").replace("\\", "")))

    for cls in MUST_BE_BLOCK:
        joined = "\n".join(_rules(css, cls))
        if not joined:
            errors.append("css-contract: .%s のルールが無い" % cls)
        elif re.search(r"display\s*:\s*flex", joined) and not re.search(r"display\s*:\s*block", joined):
            errors.append("css-contract: .%s が display:flex（文字列が折り返して崩れる）"
                          % cls)

    for e in errors:
        print("  [ERROR]", e)
    print("ERROR: %d" % len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

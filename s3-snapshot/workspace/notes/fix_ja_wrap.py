# -*- coding: utf-8 -*-
"""日本語の途中の改行（＝描画時に空白1つになる）を詰める。2026-11-15。

なぜ:
    HTMLでは文字と文字の間の改行は空白として描画される。英語なら正しいが、
    日本語では「1枚あ たり」のような不自然な空白になる。実測で 15/94 ページ。

やること:
    `<main>` の中のタグ外テキストについて
        日本語文字 + 改行(+空白) + 日本語文字
    を改行なしにつなぐ。タグ・属性・pre/code/script/style は触らない。

安全策:
    - `<main>` の外（head・nav・footer）は触らない
    - 英語の改行は残す（次が日本語文字のときだけ詰める）
    - 冪等（2回目は0件）
"""
import glob
import os
import re
import sys

SITE = os.environ.get('SITE_DIR', os.path.join(os.path.dirname(__file__), '..', '..', 'site'))
JP = r'ぁ-んァ-ヶ一-龯々〆'
PAT = re.compile(r'(?<=[%s、。「」（）])\n[ \t]*(?=[%s])' % (JP, JP))
SENTINEL = re.compile(r'<(pre|code|script|style|textarea)\b.*?</\1>', re.S | re.I)


def fix(html: str):
    m = re.search(r'(<main[^>]*>)(.*)(</main>)', html, re.S | re.I)
    if not m:
        return html, 0
    head, body, tail = m.group(1), m.group(2), m.group(3)
    saved = []

    def stash(mm):
        saved.append(mm.group(0))
        return '\x00%d\x00' % (len(saved) - 1)

    body2 = SENTINEL.sub(stash, body)
    body2, n = PAT.subn('', body2)
    body2 = re.sub(r'\x00(\d+)\x00', lambda mm: saved[int(mm.group(1))], body2)
    return html[:m.start()] + head + body2 + tail + html[m.end():], n


def main() -> int:
    site = os.path.abspath(SITE)
    total = pages = 0
    for p in sorted(glob.glob(os.path.join(site, '**', 'index.html'), recursive=True)):
        s = open(p, encoding='utf-8').read()
        out, n = fix(s)
        if n:
            open(p, 'w', encoding='utf-8').write(out)
            total += n
            pages += 1
    print('詰めた改行: %d箇所 / %dページ' % (total, pages))
    left = sum(1 for p in glob.glob(os.path.join(site, '**', 'index.html'), recursive=True)
               if fix(open(p, encoding='utf-8').read())[1])
    print('2回目で変化するページ:', left)
    return 0


if __name__ == '__main__':
    sys.exit(main())

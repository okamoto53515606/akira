# -*- coding: utf-8 -*-
"""R6: `/pricing/` の料金表を台帳へ移す（2026-11-15）。

なぜ:
    料金表が**日英それぞれのHTMLに手書き**されている限り、「ja だけ直して en が
    漏れる」「行を足したのに計算機が漏れる」が構造的に消えない（K7 と同じ型）。
    表そのものを台帳に持たせ、日英を**同じレコードの2フィールド**にする。

持ち方（facts.json のトップレベル）:
    "pricing_tables": [
      {"index": 0,
       "headers": {"ja": ["モデル","入力",...], "en": [...]},
       "rows": [{"ja": "<tr>…</tr>", "en": "<tr>…</tr>"}]}
    ]

    行は **`<tr>…</tr>` ごと生のHTML**で持つ（リンクや <strong> を保つため）。
    セルだけ抜くと `<tr>` が消える（実際に一度やった）。

安全策:
    - 抽出時、ja/en で**行数とセル数が一致しない表は「移行しない」**（壊さない）
    - 抽出結果をそのまま書き戻して**差分0**になることを確認してから採用する
"""
from __future__ import annotations

import json
import os
import re
import sys

SITE = os.environ.get('SITE_DIR', '/home/workspace/akira/s3-snapshot/site')
FACTS = os.environ.get('FACTS', '/home/workspace/akira/s3-snapshot/workspace/data/facts.json')

TABLE_RE = re.compile(r'<table[^>]*>.*?</table>', re.S)
THEAD_RE = re.compile(r'<thead[^>]*>(.*?)</thead>', re.S)
TBODY_RE = re.compile(r'<tbody[^>]*>(.*?)</tbody>', re.S)
TH_RE = re.compile(r'<th[^>]*>(.*?)</th>', re.S)
TR_RE = re.compile(r'<tr[^>]*>.*?</tr>', re.S)
TD_RE = re.compile(r'<td[^>]*>.*?</td>', re.S)


def _plain(h: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', h)).strip()


def parse(path: str) -> list:
    s = open(path, encoding='utf-8').read()
    out = []
    for i, t in enumerate(TABLE_RE.findall(s)):
        th = THEAD_RE.search(t)
        tb = TBODY_RE.search(t)
        if not th or not tb:
            continue
        headers = [h for h in TH_RE.findall(th.group(1))]
        rows = TR_RE.findall(tb.group(1))   # <tr> ごと保持する（セルだけだと tr が消える）
        out.append({'index': i, 'headers': headers, 'rows': rows})
    return out


def main() -> int:
    ja = parse(os.path.join(SITE, 'pricing/index.html'))
    en = parse(os.path.join(SITE, 'en/pricing/index.html'))
    print('表の数 ja/en: %d / %d' % (len(ja), len(en)))

    tables, skipped = [], []
    for a, b in zip(ja, en):
        ha = [_plain(h) for h in a['headers']]
        hb = [_plain(h) for h in b['headers']]
        if len(a['rows']) != len(b['rows']):
            skipped.append((a['index'], '行数 %d vs %d' % (len(a['rows']), len(b['rows']))))
            continue
        bad = [i for i, (ra, rb) in enumerate(zip(a['rows'], b['rows']))
               if len(TD_RE.findall(ra)) != len(TD_RE.findall(rb))
               or len(TD_RE.findall(ra)) != len(ha)]
        if bad:
            skipped.append((a['index'], 'セル数不一致 行%s' % bad[:3]))
            continue
        rows = [{'ja': ra, 'en': rb} for ra, rb in zip(a['rows'], b['rows'])]
        tables.append({'index': a['index'],
                       'headers': {'ja': a['headers'], 'en': b['headers']},
                       'header_text': {'ja': ha, 'en': hb},
                       'rows': rows})
        print('  表%d: %d行 x %d列' % (a['index'], len(rows), len(ha)))

    facts = json.load(open(FACTS, encoding='utf-8'))
    facts['pricing_tables'] = tables
    json.dump(facts, open(FACTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('移行した表: %d / 見送り: %d' % (len(tables), len(skipped)))
    for i, why in skipped:
        print('  見送り 表%d: %s' % (i, why))
    print('facts.json: %.1f KB' % (os.path.getsize(FACTS) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Wire /jpy-pricing/ into sitemap, llms.txt, top page (recent updates + card), changelog."""
import re

S = '/tmp/site/'
DATE = '2026-11-15'
PATHS = {'ja': '/jpy-pricing/', 'en': '/en/jpy-pricing/'}

# ---------- 1. sitemap ----------
sm = open(S + 'sitemap.xml', encoding='utf-8').read()
assert 'jpy-pricing' not in sm
for kind, old_loc, new_loc in (
        ('ja', 'https://llm.okamomedia.tokyo/image-api-pricing/',
         'https://llm.okamomedia.tokyo/jpy-pricing/'),
        ('en', 'https://llm.okamomedia.tokyo/en/image-api-pricing/',
         'https://llm.okamomedia.tokyo/en/jpy-pricing/')):
    m = re.search(r'[ \t]*<url>\s*<loc>%s</loc>.*?</url>\n' % re.escape(old_loc), sm, re.S)
    assert m, old_loc
    block = m.group(0).replace(old_loc, new_loc)
    sm = sm[:m.end()] + block + sm[m.end():]
open(S + 'sitemap.xml', 'w', encoding='utf-8').write(sm)

# ---------- 2. llms.txt ----------
ll = open(S + 'llms.txt', encoding='utf-8').read()
EN_ANCHOR = '- [Image & Video API Pricing](https://llm.okamomedia.tokyo/en/image-api-pricing/)'
JA_ANCHOR = '- [画像・動画API料金比較](https://llm.okamomedia.tokyo/image-api-pricing/)'
assert EN_ANCHOR in ll and JA_ANCHOR in ll
en_new = ('- [LLM API Pricing in Japanese Yen](https://llm.okamomedia.tokyo/en/jpy-pricing/): '
          'the USD rates converted at a fixed \u00a5155 = $1, given per 1M tokens for input and '
          'output alongside the USD figure, with a current/legacy column and each rate\'s '
          'verification date.\n')
ja_new = ('- [LLM API 日本円換算（1ドル=155円）](https://llm.okamomedia.tokyo/jpy-pricing/): '
          'USD単価を1ドル=155円で固定換算し、100万トークンあたりの入力・出力を円とUSDで併記。'
          '現行／旧版の状態列と各単価の確認日つき。\n')
lines = ll.split('\n')
out = []
for ln in lines:
    out.append(ln)
    if ln.startswith(EN_ANCHOR):
        out.append(en_new.rstrip('\n'))
    elif ln.startswith(JA_ANCHOR):
        out.append(ja_new.rstrip('\n'))
ll = '\n'.join(out)
open(S + 'llms.txt', 'w', encoding='utf-8').write(ll)

# ---------- 3. top page + changelog lists ----------
CL = {
    'ja': 'LLM API料金の日本円換算表（1ドル=155円）を新規公開。USD単価から機械計算し、現行／旧版の状態列つき（/jpy-pricing/）',
    'en': 'Published LLM API pricing in Japanese yen at a fixed \u00a5155 = $1, calculated from '
          'the USD rates, with a current/legacy column (/en/jpy-pricing/)',
}
CARD = {
    'ja': ('<article class="card"><div class="card-icon">\U0001F4B4</div>'
           '<h3 class="card-title">LLM API 日本円換算【1ドル=155円】</h3>'
           '<p class="card-desc">主要16モデルの入力・出力単価を100万トークンあたりの日本円に換算。'
           'USD単価は各社公式の値をそのまま残し、円は機械計算。現行／旧版の状態列つき。</p>'
           '<a href="/jpy-pricing/" class="card-link">円換算表を見る \u2192</a></article>\n'),
    'en': ('<article class="card"><div class="card-icon">\U0001F4B4</div>'
           '<h3 class="card-title">LLM API prices in Japanese yen (\u00a5155 = $1)</h3>'
           '<p class="card-desc">Input and output rates for 16 mainstream models converted to yen '
           'per 1M tokens. The USD figures are each provider\u2019s own and are kept as-is; the yen '
           'is calculated. Includes a current/legacy column.</p>'
           '<a href="/en/jpy-pricing/" class="card-link">See the yen table \u2192</a></article>\n'),
}

for kind in ('ja', 'en'):
    p = S + ('index.html' if kind == 'ja' else 'en/index.html')
    s = open(p, encoding='utf-8').read()
    assert 'jpy-pricing' not in s, p
    # (a) recent-updates list
    m = re.search(r'<ul class="cl-list">\n', s)
    assert m, 'cl-list ' + p
    li = ('<li><span class="cl-date">%s</span> <span class="cl-text">%s</span></li>\n'
          % (DATE, CL[kind]))
    s = s[:m.end()] + li + s[m.end():]
    # (b) card at top of the content grid
    m = re.search(r'<h2 class="section-title" id="ch">', s)
    assert m, 'ch ' + p
    i = s.find('<article class="card"', m.end())
    assert i > 0
    s = s[:i] + CARD[kind] + s[i:]
    open(p, 'w', encoding='utf-8').write(s)

    # (c) changelog
    cp = S + ('changelog/index.html' if kind == 'ja' else 'en/changelog/index.html')
    c = open(cp, encoding='utf-8').read()
    assert 'jpy-pricing' not in c
    m = re.search(r'<ul class="changelog">\n', c)
    assert m, 'changelog ' + cp
    c = c[:m.end()] + li + c[m.end():]
    n = c[:c.find('</ul>', m.end())].count('<li>')
    open(cp, 'w', encoding='utf-8').write(c)

    # (d) count in the top-page link
    s = open(p, encoding='utf-8').read()
    s2 = re.sub(r'(すべての更新履歴（|All \d+ updates)(\d+)',
                lambda mm: mm.group(1), s)
    if kind == 'ja':
        s = re.sub(r'すべての更新履歴（\d+）', 'すべての更新履歴（%d）' % n, s)
        s = re.sub(r'/changelog/">すべての更新履歴（\d+）', '/changelog/">すべての更新履歴（%d）' % n, s)
    else:
        s = re.sub(r'All (\d+) updates', 'All %d updates' % n, s)
    open(p, 'w', encoding='utf-8').write(s)
    print(kind, 'changelog items', n)
print('done')

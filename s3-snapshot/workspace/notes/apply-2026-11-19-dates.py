# -*- coding: utf-8 -*-
"""A/B/C 一括修正: china-ai の日付・文言・Newバッジ、4ページ×日英の日付五点、本日表記。"""
import io, re, pathlib

SITE = pathlib.Path('/tmp/site')
WS = pathlib.Path('/workspace')
NEW = '2026-11-19'
rep = []

def rw(rel, func):
    p = SITE / rel
    s = io.open(p, encoding='utf-8').read()
    o = s
    s = func(s)
    if s != o:
        io.open(p, 'w', encoding='utf-8').write(s)
        rep.append((rel, 'changed'))
    else:
        rep.append((rel, 'nochange'))
    return s

def sub(s, old, new, label, rel):
    if old not in s:
        rep.append((rel, 'MISS: ' + label))
        return s
    n = s.count(old)
    rep.append((rel, 'ok %dx: %s' % (n, label)))
    return s.replace(old, new)

BADGE = ' <span class="badge badge-new">New</span>'

# ---------- A: facts.json から china-ai の New バッジを除去 ----------
fp = WS / 'data' / 'facts.json'
raw = io.open(fp, encoding='utf-8').read()
n0 = raw.count('badge badge-new')
raw2 = raw.replace(' ' + BADGE.replace('"', '\\"'), '').replace(BADGE, '')
io.open(fp, 'w', encoding='utf-8').write(raw2)
rep.append(('data/facts.json', 'badge-new %d -> %d' % (n0, raw2.count('badge badge-new'))))

# ---------- A: china-ai ja ----------
def ja_china(s):
    r = 'china-ai/index.html'
    s = sub(s, '<time datetime="2026-11-17">2026年11月17日</time>',
               '<time datetime="%s">2026年11月19日</time>' % NEW, 'updated-bar time', r)
    s = sub(s, '"dateModified": "2026-11-17"', '"dateModified": "2026-11-19"', 'jsonld dateModified', r)
    s = sub(s, '本ページの最終更新は2026-11-17', '本ページの最終更新は2026-11-19', 'footer date', r)
    s = sub(s, 'Qwen 4（<code>qwen4-max-preview</code>）は 11/11〜11/25 の期間限定で提供中・',
               'Qwen4-Max は 2026-11-15 に正式提供（入力$1.50／出力$4.50）・', 'updated-bar Qwen文言', r)
    s = sub(s, BADGE, '', 'badge-new removal', r)
    return s

def en_china(s):
    r = 'en/china-ai/index.html'
    s = sub(s, '<time datetime="2026-11-17">17 Nov 2026</time>',
               '<time datetime="%s">19 Nov 2026</time>' % NEW, 'updated-bar time', r)
    s = sub(s, '"dateModified":"2026-11-17"', '"dateModified":"2026-11-19"', 'jsonld dateModified', r)
    s = sub(s, 'last updated is 2026-11-17', 'last updated is 2026-11-19', 'footer date', r)
    s = sub(s, 'Qwen 4 (<code>qwen4-max-preview</code>) is in limited preview 11/11-11/25 · ',
               'Qwen4-Max went GA on 15 Nov 2026 ($1.50 input / $4.50 output) · ', 'updated-bar Qwen文言', r)
    s = sub(s, BADGE, '', 'badge-new removal', r)
    return s

rw('china-ai/index.html', ja_china)
rw('en/china-ai/index.html', en_china)

# ---------- B: timeline / mai / pricing のページ日付 ----------
def timeline_ja(s):
    r = 'timeline/index.html'
    s = sub(s, '"dateModified": "2026-11-15"', '"dateModified": "2026-11-19"', 'jsonld', r)
    s = sub(s, '<time datetime="2026-11-15">2026年11月15日</time>',
               '<time datetime="%s">2026年11月19日</time>' % NEW, 'updated-bar', r)
    return s

def timeline_en(s):
    r = 'en/timeline/index.html'
    s = sub(s, '"dateModified":"2026-11-15"', '"dateModified":"2026-11-19"', 'jsonld', r)
    s = sub(s, '<time datetime="2026-11-15">November 15, 2026</time>',
               '<time datetime="%s">November 19, 2026</time>' % NEW, 'updated-bar', r)
    return s

def mai_ja(s):
    r = 'mai/index.html'
    s = sub(s, '"dateModified":"2026-10-17"', '"dateModified":"2026-11-19"', 'jsonld', r)
    s = sub(s, '<time datetime="2026-10-17">2026年10月17日</time>',
               '<time datetime="%s">2026年11月19日</time>' % NEW, 'updated-bar', r)
    return s

def mai_en(s):
    r = 'en/mai/index.html'
    s = sub(s, '"dateModified":"2026-11-15"', '"dateModified":"2026-11-19"', 'jsonld', r)
    s = sub(s, '<time datetime="2026-11-15">November 15, 2026</time>',
               '<time datetime="%s">November 19, 2026</time>' % NEW, 'updated-bar', r)
    return s

def pricing_ja(s):
    r = 'pricing/index.html'
    s = sub(s, '"dateModified": "2026-11-17"', '"dateModified": "2026-11-19"', 'jsonld', r)
    s = sub(s, '<time datetime="2026-11-17">2026年11月17日</time>',
               '<time datetime="%s">2026年11月19日</time>' % NEW, 'updated-bar', r)
    # C: 「本日」→ 実日付（同一段落の再取得日 = 2026-11-05）
    s = sub(s, '冒頭の確認日のとおり本日または 2026-11-03 に再取得済みです。',
               '冒頭の確認日のとおり 2026-11-05 または 2026-11-03 に再取得済みです。', 'C: 本日', r)
    return s

def pricing_en(s):
    r = 'en/pricing/index.html'
    s = sub(s, '"dateModified": "2026-11-17"', '"dateModified": "2026-11-19"', 'jsonld', r)
    s = sub(s, '<time datetime="2026-11-17">November 17, 2026</time>',
               '<time datetime="%s">November 19, 2026</time>' % NEW, 'updated-bar', r)
    s = sub(s, 'were re-fetched today or on 2026-11-03', 'were re-fetched on 2026-11-05 or 2026-11-03', 'C: today', r)
    return s

rw('timeline/index.html', timeline_ja)
rw('en/timeline/index.html', timeline_en)
rw('mai/index.html', mai_ja)
rw('en/mai/index.html', mai_en)
rw('pricing/index.html', pricing_ja)
rw('en/pricing/index.html', pricing_en)

# ---------- B: sitemap lastmod 8URL ----------
URLS = ['/pricing/', '/en/pricing/', '/timeline/', '/en/timeline/',
        '/china-ai/', '/en/china-ai/', '/mai/', '/en/mai/']
sp = SITE / 'sitemap.xml'
s = io.open(sp, encoding='utf-8').read()
for u in URLS:
    loc = 'https://llm.okamomedia.tokyo' + u
    pat = re.compile(r'(<loc>%s</loc>\s*<lastmod>)[0-9-]+(</lastmod>)' % re.escape(loc))
    s, n = pat.subn(r'\g<1>%s\g<2>' % NEW, s)
    rep.append(('sitemap.xml', '%s -> %s (%d)' % (u, NEW, n)))
io.open(sp, 'w', encoding='utf-8').write(s)

# ---------- B: llms.txt Updated ----------
lp = SITE / 'llms.txt'
s = io.open(lp, encoding='utf-8').read()
s2 = re.sub(r'^Updated: .*$', 'Updated: %s' % NEW, s, count=1, flags=re.M)
io.open(lp, 'w', encoding='utf-8').write(s2)
rep.append(('llms.txt', 'Updated line changed=%s' % (s != s2)))

# ---------- 検証 ----------
for rel in ['china-ai/index.html','en/china-ai/index.html','pricing/index.html','en/pricing/index.html',
            'timeline/index.html','en/timeline/index.html','mai/index.html','en/mai/index.html']:
    t = io.open(SITE / rel, encoding='utf-8').read()
    dm = re.search(r'"dateModified":\s*"([0-9-]+)"', t)
    tm = re.search(r'updated-bar.*?<time datetime="([0-9-]+)"', t, re.S)
    rep.append((rel, 'dateModified=%s updated-bar=%s badge-new=%d 本日=%d' % (
        dm.group(1) if dm else 'NONE', tm.group(1) if tm else 'NONE',
        t.count('badge-new'), t.count('本日') + t.lower().count('today'))))
for line in rep:
    print(line[0], '|', line[1])

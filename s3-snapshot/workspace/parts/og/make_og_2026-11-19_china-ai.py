# -*- coding: utf-8 -*-
"""OGP images for /china-ai/ (ja/en). Strictly 1200x630, Pillow + Noto Sans JP."""
import os, urllib.request
from PIL import Image, ImageDraw, ImageFont

OGDIR = '/tmp/site/assets/og'; FONTDIR = '/tmp/ogfonts'
os.makedirs(OGDIR, exist_ok=True); os.makedirs(FONTDIR, exist_ok=True)
URLS = {'bold': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf',
        'reg':  'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf'}

def F(kind, size):
    p = os.path.join(FONTDIR, 'NotoSansJP-%s.otf' % ('Bold' if kind == 'bold' else 'Regular'))
    if not os.path.exists(p) or os.path.getsize(p) < 500000:
        urllib.request.urlretrieve(URLS[kind], p)
    return ImageFont.truetype(p, size)

W, H = 1200, 630
BG1 = (10, 18, 30); BG2 = (18, 44, 58); ACC = (16, 148, 140)
TEXT = (235, 244, 246); MUTED = (176, 200, 206)

SPECS = [
    ('ja-china-ai.png', 'LLM Data Hub · 中国系AI総覧', '中国系AIモデル総覧',
     ['Qwen4-Max が 2026-11-15 に正式提供（入力$1.50／出力$4.50）',
      'DeepSeek・Qwen・GLM・Kimi・MiniMax の料金とオープンウェイトを比較',
      '暗黙キャッシュ $0.075／明示キャッシュ 5分$1.875・1時間$3.00',
      '一次情報で確認：2026-11-19（2026年11月版）'],
     'llm.okamomedia.tokyo/china-ai/'),
    ('en-china-ai.png', 'LLM Data Hub · Chinese AI models', 'Chinese AI Models Overview',
     ['Qwen4-Max went GA on 15 Nov 2026 ($1.50 in / $4.50 out per 1M tokens)',
      'DeepSeek, Qwen, GLM, Kimi and MiniMax compared on price and open weights',
      'Implicit cache $0.075; explicit writes $1.875 (5 min) / $3.00 (1 hour)',
      'Checked against primary sources 19 Nov 2026 (November 2026 edition)'],
     'llm.okamomedia.tokyo/en/china-ai/'),
]

def bg():
    img = Image.new('RGB', (W, H), BG1); d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(BG1[0] + (BG2[0] - BG1[0]) * t),
                                      int(BG1[1] + (BG2[1] - BG1[1]) * t),
                                      int(BG1[2] + (BG2[2] - BG1[2]) * t)))
    d.rectangle([0, 0, 14, H], fill=ACC)
    d.rectangle([70, H - 96, W - 70, H - 94], fill=(40, 80, 86))
    return img, d

def wrap(d, text, font, maxw):
    out = []; cur = ''
    for ch in text:
        if d.textlength(cur + ch, font=font) <= maxw:
            cur += ch
        else:
            out.append(cur); cur = ch
    if cur:
        out.append(cur)
    return out

def layout(d, title, facts, tsize, fsize):
    tf = F('bold', tsize); ff = F('reg', fsize)
    tl = wrap(d, title, tf, W - 160)
    fl = [wrap(d, f, ff, W - 200) for f in facts]
    t_lh = int(tsize * 1.22); f_lh = int(fsize * 1.45)
    h = len(tl) * t_lh + 44 + sum(len(x) * f_lh + 8 for x in fl)
    return tl, fl, t_lh, f_lh, h

TOP, BOTTOM = 126, H - 110

for fn, kicker, title, facts, url in SPECS:
    img, d = bg()
    tsize, fsize = 68, 30
    while True:
        tl, fl, t_lh, f_lh, total = layout(d, title, facts, tsize, fsize)
        if TOP + total <= BOTTOM or fsize <= 20:
            break
        tsize -= 2; fsize -= 1
    d.text((70, 60), kicker, font=F('bold', 34), fill=(120, 214, 206))
    y = TOP
    for ln in tl:
        d.text((70, y), ln, font=F('bold', tsize), fill=TEXT); y += t_lh
    y += 12
    d.rectangle([70, y, 150, y + 6], fill=ACC); y += 32
    for lines in fl:
        for i, ln in enumerate(lines):
            d.text((70 if i == 0 else 100, y), ('•  ' if i == 0 else '') + ln,
                   font=F('reg', fsize), fill=MUTED); y += f_lh
        y += 8
    d.text((70, H - 70), url, font=F('reg', 28), fill=(110, 146, 152))
    p = os.path.join(OGDIR, fn)
    img.save(p, 'PNG', optimize=True)
    print('saved', p, os.path.getsize(p), 'title_size=%d' % tsize, 'fact_size=%d' % fsize, 'bottom_y=%d' % y)

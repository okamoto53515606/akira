# -*- coding: utf-8 -*-
"""OGP images for /jpy-pricing/ (ja/en). 1200x630, Pillow + Noto Sans JP."""
import os, urllib.request
from PIL import Image, ImageDraw, ImageFont
OGDIR = '/tmp/site/assets/og'; FONTDIR = '/tmp/ogfonts'
os.makedirs(OGDIR, exist_ok=True); os.makedirs(FONTDIR, exist_ok=True)
URLS = {'bold': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf',
        'reg': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf'}


def F(kind, size):
    p = os.path.join(FONTDIR, 'NotoSansJP-%s.otf' % ('Bold' if kind == 'bold' else 'Regular'))
    if not os.path.exists(p) or os.path.getsize(p) < 500000:
        urllib.request.urlretrieve(URLS[kind], p)
    return ImageFont.truetype(p, size)


W, H = 1200, 630
BG1 = (10, 18, 30); BG2 = (18, 44, 58); ACC = (16, 148, 140)
TEXT = (235, 244, 246); MUTED = (176, 200, 206)

SPECS = [
    ('ja-jpy-pricing.png', 'LLM Data Hub · 日本円換算', '100万トークン 43円から3,100円',
     ['1ドル=155円で固定（USD単価から機械計算）',
      '入力と出力は別単価。出力は入力の約5倍',
      'Claude Opus 5.5 出力 3,100円 / MiMo-V2.6-Flash 出力 43円',
      'DeepSeekはオフピークとピークを併記'],
     'llm.okamomedia.tokyo/jpy-pricing/'),
    ('en-jpy-pricing.png', 'LLM Data Hub · JPY pricing', '¥43 to ¥3,100 per 1M tokens',
     ['All figures converted at a fixed ¥155 = $1',
      'Input and output priced separately (output ≈ 5x)',
      'Claude Opus 5.5 out ¥3,100 / MiMo-V2.6-Flash out ¥43',
      'DeepSeek shown as off-peak and peak'],
     'llm.okamomedia.tokyo/en/jpy-pricing/'),
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


for fn, kicker, title, facts, url in SPECS:
    img, d = bg()
    d.text((70, 64), kicker, font=F('bold', 34), fill=(120, 214, 206))
    y = 126
    for ln in wrap(d, title, F('bold', 74), W - 160):
        d.text((70, y), ln, font=F('bold', 74), fill=TEXT); y += 90
    y += 12
    d.rectangle([70, y, 150, y + 6], fill=ACC); y += 32
    for f in facts:
        for i, ln in enumerate(wrap(d, f, F('reg', 31), W - 200)):
            d.text((70 if i == 0 else 100, y), ('•  ' if i == 0 else '') + ln,
                   font=F('reg', 31), fill=MUTED); y += 44
        y += 6
    d.text((70, H - 70), url, font=F('reg', 28), fill=(110, 146, 152))
    p = os.path.join(OGDIR, fn)
    img.save(p, 'PNG', optimize=True)
    print('saved', p, os.path.getsize(p), img.size)

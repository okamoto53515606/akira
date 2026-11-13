import os, re, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

SITE = '/tmp/site'
OGDIR = SITE + '/assets/og'
FONTDIR = '/tmp/ogfonts'
os.makedirs(OGDIR, exist_ok=True)
os.makedirs(FONTDIR, exist_ok=True)

FONT_URLS = {
    'bold': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf',
    'reg': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf',
}
def get_font(kind, size):
    p = os.path.join(FONTDIR, 'NotoSansJP-%s.otf' % ('Bold' if kind == 'bold' else 'Regular'))
    if not os.path.exists(p) or os.path.getsize(p) < 500000:
        urllib.request.urlretrieve(FONT_URLS[kind], p)
    return ImageFont.truetype(p, size)

W, H = 1200, 630
BG1 = (9, 17, 28)
BG2 = (16, 32, 48)
ACCENT = (15, 118, 110)
TEXT = (232, 240, 248)
MUTED = (150, 172, 192)

SPECS = [
    # (filename, kicker, title, facts[], url_label)
    ('ja-home.png', 'LLM Data Hub', 'AIの料金を、\u4e00\u6b21\u60c5\u5831\u3067\u3002',
     ['\u6599\u91d1\u6bd4\u8f03\u30fb\u30c8\u30fc\u30af\u30f3\u30b3\u30b9\u30c8\u8a08\u7b97\u6a5f\u30fb\u30e2\u30c7\u30eb\u60c5\u5831',
      'OpenAI / Anthropic / Google / DeepSeek / \u4e2d\u56fd\u7cfbAI',
      '\u516c\u5f0f\u6599\u91d1\u30da\u30fc\u30b8\u3092\u6bce\u65e5\u78ba\u8a8d\u30fb\u5e83\u544a\u306a\u3057'],
     'llm.okamomedia.tokyo'),
    ('en-calculator.png', 'LLM Data Hub', 'Token Cost Calculator',
     ['tokens x price per 1M = your bill',
      'Input, cached input and output priced separately',
      'GPT / Claude / Gemini / DeepSeek / GLM / Kimi'],
     'llm.okamomedia.tokyo/en/calculator/'),
    ('ja-china-ai.png', 'LLM Data Hub', '\u4e2d\u56fd\u7cfbAI\u7dcf\u89a7',
     ['DeepSeek\u30fbQwen\u30fbGLM\u30fbKimi\u30fbMiniMax',
      '\u30d5\u30e9\u30c3\u30b0\u30b7\u30c3\u30d7\u306e\u6599\u91d1\u3068\u30aa\u30fc\u30d7\u30f3\u30a6\u30a7\u30a4\u30c8\u72b6\u6cc1',
      'Qwen 4 \u306f\u516c\u5f0f\u300c\u5b66\u7fd2\u4e2d\u300d\u3001\u6642\u671f\u306f\u672a\u516c\u8868'],
     'llm.okamomedia.tokyo/china-ai/'),
    ('ja-deepseek-v4-1-flash.png', 'DeepSeek V4.1 Flash', '\u5165\u529b $0.15 / \u51fa\u529b $0.60',
     ['\u30aa\u30d5\u30d4\u30fc\u30af\u6599\u91d1\uff08USD / 1M\u30c8\u30fc\u30af\u30f3\uff09',
      '1M\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8\u30fb384K\u51fa\u529b',
      '\u30d4\u30fc\u30af\u6642\u306f\u500d\u306e\u4fa1\u683c\u3001\u30ad\u30e3\u30c3\u30b7\u30e5\u5272\u5f15\u3042\u308a'],
     'llm.okamomedia.tokyo/deepseek-v4-1-flash/'),
    ('ja-zoa.png', 'Glossary', 'Zero Operator Access (ZOA)',
     ['\u904b\u55b6\u8005\u306f\u5165\u51fa\u529b\u3092\u898b\u3089\u308c\u306a\u3044\u3002\u305d\u308c\u304cZOA',
      'ZDR\uff08\u4fdd\u6301\u3057\u306a\u3044\uff09\u3068\u306f\u5225\u306e\u7d04\u675f',
      'AWS Bedrock / OpenAI / Anthropic \u306e\u8a18\u8ff0\u3092\u4e00\u6b21\u60c5\u5831\u3067\u6574\u7406'],
     'llm.okamomedia.tokyo/glossary/zero-operator-access/'),
    ('ja-multimodal.png', 'LLM Data Hub', '\u30de\u30eb\u30c1\u30e2\u30fc\u30c0\u30eb\u5bfe\u5fdc\u6bd4\u8f03',
     ['\u753b\u50cf\u30fb\u97f3\u58f0\u30fb\u52d5\u753b\u306e\u5165\u529b\u306b\u5bfe\u5fdc\u3059\u308b\u30e2\u30c7\u30eb\u4e00\u89a7',
      'Gemini / GPT / Claude / Qwen / Kimi',
      '\u6599\u91d1\u3068\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8\u3092\u540c\u3058\u8868\u3067\u6bd4\u8f03'],
     'llm.okamomedia.tokyo/multimodal/'),
    ('ja-gpt-6-1-terra.png', 'OpenAI GPT-6.1 Terra', '\u5165\u529b $1.00 / \u51fa\u529b $5.00',
     ['\u30ad\u30e3\u30c3\u30b7\u30e5\u5165\u529b $0.05\uff08\u5165\u529b\u306e5%\uff09',
      '1,050,000\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8\u30fb128,000\u51fa\u529b',
      '272,000\u30c8\u30fc\u30af\u30f3\u8d85\u306f\u30ea\u30af\u30a8\u30b9\u30c8\u5168\u4f53\u304c\u5165\u529b2\u500d'],
     'llm.okamomedia.tokyo/gpt-6-1-terra/'),
    ('en-gpt-6-1-terra.png', 'OpenAI GPT-6.1 Terra', '$1.00 in / $5.00 out',
     ['Cached input $0.05 - 5% of the input rate',
      '1,050,000 context, 128,000 max output',
      'Above 272K input the whole request is 2x'],
     'llm.okamomedia.tokyo/en/gpt-6-1-terra/'),
]

def bg():
    im = Image.new('RGB', (W, H), BG1)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(BG1[0] + (BG2[0] - BG1[0]) * t),
                                       int(BG1[1] + (BG2[1] - BG1[1]) * t),
                                       int(BG1[2] + (BG2[2] - BG1[2]) * t)))
    d.rectangle([0, 0, W, 10], fill=ACCENT)
    return im, d

def wrap(d, text, font, maxw):
    lines, cur = [], ''
    for ch in text:
        if ch == '\n':
            lines.append(cur); cur = ''; continue
        if d.textlength(cur + ch, font=font) > maxw and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines

for fn, kicker, title, facts, url in SPECS:
    im, d = bg()
    f_kick = get_font('bold', 30)
    f_title = get_font('bold', 74)
    f_fact = get_font('reg', 32)
    f_url = get_font('reg', 24)
    # site name top-left
    d.text((80, 58), kicker, font=f_kick, fill=(120, 220, 205))
    # accent bar
    d.rectangle([80, 116, 80 + 140, 124], fill=ACCENT)
    # title (auto-shrink if too wide)
    size = 74
    while True:
        tf = get_font('bold', size)
        lines = wrap(d, title, tf, W - 160)
        if len(lines) <= 2 or size <= 44:
            break
        size -= 6
    y = 168
    for ln in lines:
        d.text((80, y), ln, font=tf, fill=TEXT)
        y += int(size * 1.28)
    # facts
    y = max(y + 34, 400)
    for fact in facts:
        d.ellipse([82, y + 14, 96, y + 28], fill=ACCENT)
        for i, ln in enumerate(wrap(d, fact, f_fact, W - 220)):
            d.text((116, y), ln, font=f_fact, fill=MUTED if i else TEXT)
            y += 44
        y += 8
    # footer
    d.text((80, H - 64), url, font=f_url, fill=(110, 132, 152))
    d.text((W - 200, H - 64), '2026-10-29', font=f_url, fill=(110, 132, 152))
    im.save(os.path.join(OGDIR, fn), 'PNG', optimize=True)
    print('ok', fn, os.path.getsize(os.path.join(OGDIR, fn)))

# ---------------- HTML 配線 ----------------
WIRE = {
    'index.html': ('ja-home.png', 'LLM Data Hub — AI/LLM\u306e\u6599\u91d1\u6bd4\u8f03\u30fb\u30c8\u30fc\u30af\u30f3\u8a08\u7b97\u6a5f\u30fb\u30e2\u30c7\u30eb\u60c5\u5831\u306e\u65e5\u672c\u8a9e\u30c8\u30c3\u30d7\u30da\u30fc\u30b8'),
    'en/calculator/index.html': ('en-calculator.png', 'Token cost calculator: input and output tokens x per-1M API prices, with cache rates'),
    'china-ai/index.html': ('ja-china-ai.png', '\u4e2d\u56fd\u7cfbAI\u7dcf\u89a7: DeepSeek\u30fbQwen\u30fbGLM\u30fbKimi\u30fbMiniMax\u306e\u6599\u91d1\u3068\u30aa\u30fc\u30d7\u30f3\u30a6\u30a7\u30a4\u30c8\u72b6\u6cc1'),
    'deepseek-v4-1-flash/index.html': ('ja-deepseek-v4-1-flash.png', 'DeepSeek V4.1 Flash: \u30aa\u30d5\u30d4\u30fc\u30af\u5165\u529b$0.15\u30fb\u51fa\u529b$0.60\u30011M\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8'),
    'glossary/zero-operator-access/index.html': ('ja-zoa.png', 'Zero Operator Access: \u904b\u55b6\u8005\u304c\u5165\u51fa\u529b\u3092\u898b\u3089\u308c\u306a\u3044\u4fdd\u8a3c\u3068ZDR\u3068\u306e\u9055\u3044'),
    'multimodal/index.html': ('ja-multimodal.png', '\u30de\u30eb\u30c1\u30e2\u30fc\u30c0\u30eb\u5bfe\u5fdc\u6bd4\u8f03: \u753b\u50cf\u30fb\u97f3\u58f0\u30fb\u52d5\u753b\u306e\u5165\u529b\u306b\u5bfe\u5fdc\u3059\u308b\u30e2\u30c7\u30eb\u4e00\u89a7'),
    'gpt-6-1-terra/index.html': ('ja-gpt-6-1-terra.png', 'GPT-6.1 Terra\u306e\u6599\u91d1\u3068\u4ed5\u69d8: \u5165\u529b$1.00\u30fb\u51fa\u529b$5.00\u30011.05M\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8\u3001272K\u8d85\u306f2\u500d'),
    'en/gpt-6-1-terra/index.html': ('en-gpt-6-1-terra.png', 'GPT-6.1 Terra pricing and specs: $1.00 input, $5.00 output, 1.05M context, 2x above 272K'),
}

for rel, (fname, alt) in WIRE.items():
    p = os.path.join(SITE, rel)
    s = open(p, encoding='utf-8').read()
    url = 'https://llm.okamomedia.tokyo/assets/og/' + fname
    def sub(pattern, repl):
        global s
        s2, n = re.subn(pattern, repl, s, count=1)
        return s2
    s = sub(r'<meta property="og:image" content="[^"]*">', '<meta property="og:image" content="%s">' % url)
    s = sub(r'<meta name="twitter:image" content="[^"]*">', '<meta name="twitter:image" content="%s">' % url)
    s = sub(r'<meta property="og:image:alt" content="[^"]*">', '<meta property="og:image:alt" content="%s">' % alt)
    s = sub(r'<meta name="twitter:image:alt" content="[^"]*">', '<meta name="twitter:image:alt" content="%s">' % alt)
    if 'og:image:width' not in s:
        s = s.replace('<meta property="og:image" content="%s">' % url,
                      '<meta property="og:image" content="%s">\n  <meta property="og:image:width" content="1200">\n  <meta property="og:image:height" content="630">' % url)
    open(p, 'w', encoding='utf-8').write(s)
    print('wired', rel, '->', fname, 'og=', url in s, 'twitter=', s.count(url))

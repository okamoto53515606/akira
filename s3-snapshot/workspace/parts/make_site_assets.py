#!/usr/bin/env python3
"""LLM Data Hub 画像素材ジェネレータ（favicon / apple-touch-icon / OGPカード）
使い方: python3 make_site_assets.py /tmp/site/assets
依存: Pillow（PIL）。フォントは Pillow 同梱の load_default(size=N) を使う（Latin/数字のみ）。
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/site/assets"
os.makedirs(OUT, exist_ok=True)

BG      = (15, 17, 23)
SURFACE = (26, 29, 39)
BORDER  = (46, 50, 80)
TEXT    = (226, 228, 240)
MUTED   = (136, 145, 181)
ACCENT  = (108, 142, 255)
ACCENT2 = (167, 139, 250)
GREEN   = (52, 211, 153)
OPENAI  = (16, 163, 127)
ANTHROPIC = (201, 100, 66)
GOOGLE  = (66, 133, 244)

def font(size):
    return ImageFont.load_default(size=size)

def text_w(d, s, f):
    return d.textlength(s, font=f)

def fit(d, s, size, max_w, min_size=14):
    """max_w に収まる最大フォントサイズを返す"""
    while size > min_size:
        f = font(size)
        if text_w(d, s, f) <= max_w:
            return f, size
        size -= 1
    return font(min_size), min_size

def draw_glow(im, cx, cy, r, color, alpha=38):
    """簡易グロー（重ね塗りでぼかし代わり）"""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    steps = 14
    for i in range(steps, 0, -1):
        rr = int(r * i / steps)
        a = int(alpha * (1 - i / steps) ** 1.5) + 2
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=color + (a,))
    im.alpha_composite(layer)

# ---------------------------------------------------------------- OGP (1200x630)
def make_ogp(path):
    W, H = 1200, 630
    im = Image.new("RGBA", (W, H), BG + (255,))
    draw_glow(im, 1120, 60, 320, ACCENT, 46)
    draw_glow(im, 60, 600, 300, ACCENT2, 34)
    d = ImageDraw.Draw(im)

    PAD = 72
    # 枠線
    d.rounded_rectangle([18, 18, W - 19, H - 19], radius=26, outline=BORDER, width=2)

    # ラベル
    d.text((PAD, 62), "LLM DATA HUB", font=font(30), fill=ACCENT)
    d.text((PAD + text_w(d, "LLM DATA HUB", font(30)) + 18, 62),
           "llm.okamomedia.tokyo", font=font(24), fill=MUTED)

    # 見出し（幅に合わせて自動縮小）
    head = "LLM API Pricing, Verified"
    f, _ = fit(d, head, 84, W - PAD * 2)
    d.text((PAD, 118), head, font=f, fill=TEXT)

    # サブ見出し
    sub = "Pricing  ·  Token Cost Calculator  ·  Release Timeline  ·  Model Guides"
    fs, _ = fit(d, sub, 34, W - PAD * 2)
    d.text((PAD, 232), sub, font=fs, fill=MUTED)

    # 価格チップ 4枚
    chips = [
        (OPENAI,    "OPENAI",            "GPT-6 Astra",      "$10 / $50"),
        (ANTHROPIC, "ANTHROPIC",         "Claude Opus 5.5",  "$4 / $20"),
        (GOOGLE,    "GOOGLE",            "Gemini 3.8 Flash", "$0.75 / $3.75"),
        (ACCENT2,   "DEEPSEEK · PEAK",   "V4.1 Flash",       "$0.30 / $1.20"),
    ]
    top, ch, gap = 322, 168, 22
    cw = (W - PAD * 2 - gap * 3) // 4
    for i, (col, label, model, price) in enumerate(chips):
        x = PAD + i * (cw + gap)
        d.rounded_rectangle([x, top, x + cw, top + ch], radius=14,
                            fill=SURFACE, outline=BORDER, width=2)
        # 上端のアクセントバー
        d.rounded_rectangle([x, top, x + cw, top + 6], radius=3, fill=col)
        inner = cw - 34
        fl, _ = fit(d, label, 21, inner)
        d.text((x + 17, top + 30), label, font=fl, fill=col)
        fm, _ = fit(d, model, 30, inner)
        d.text((x + 17, top + 66), model, font=fm, fill=TEXT)
        fp, _ = fit(d, price, 40, inner)
        d.text((x + 17, top + 108), price, font=fp, fill=TEXT)

    # フッター
    d.line([PAD, 536, W - PAD, 536], fill=BORDER, width=2)
    d.text((PAD, 556), "USD per 1M tokens", font=font(26), fill=MUTED)
    right = "No ads · Official sources only"
    fr = font(26)
    d.text((W - PAD - text_w(d, right, fr), 556), right, font=fr, fill=MUTED)

    im.convert("RGB").save(path, "PNG", optimize=True)
    return path

# ------------------------------------------------------- apple-touch-icon (180x180)
def make_touch_icon(path, size=180):
    im = Image.new("RGBA", (size, size), BG + (255,))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([6, 6, size - 7, size - 7], radius=40, fill=SURFACE, outline=BORDER, width=3)
    bars = [(GREEN, 46, 108), (ACCENT2, 60, 84), (ACCENT, 52, 60)]
    x = 30
    for col, h, y in bars:
        d.rounded_rectangle([x, y, x + 26, 146], radius=8, fill=col)
        x += 42
    im.convert("RGB").save(path, "PNG", optimize=True)
    return path

# ------------------------------------------------------------------- favicon.svg
FAVICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="LLM Data Hub">
  <rect x="0" y="0" width="64" height="64" rx="14" fill="#131722"/>
  <rect x="1.5" y="1.5" width="61" height="61" rx="12.5" fill="none" stroke="#2e3250" stroke-width="3"/>
  <rect x="11" y="34" width="11" height="18" rx="3" fill="#6c8eff"/>
  <rect x="26.5" y="24" width="11" height="28" rx="3" fill="#a78bfa"/>
  <rect x="42" y="14" width="11" height="38" rx="3" fill="#34d399"/>
</svg>
'''

if __name__ == "__main__":
    p1 = make_ogp(os.path.join(OUT, "ogp-default.png"))
    p2 = make_touch_icon(os.path.join(OUT, "apple-touch-icon.png"))
    p3 = os.path.join(OUT, "favicon.svg")
    with open(p3, "w", encoding="utf-8") as fh:
        fh.write(FAVICON_SVG)
    for p in (p1, p2, p3):
        print(p, os.path.getsize(p), "bytes")

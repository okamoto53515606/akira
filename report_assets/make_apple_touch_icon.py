#!/usr/bin/env python3
"""apple-touch-icon.png を favicon.svg と同じ図形から描く。

SVGをラスタライズできる道具（cairosvg / rsvg-convert / inkscape）が実行環境に
無いため、PIL で同じ座標・同じ色を描いて 180x180 のPNGを作る。
**favicon.svg を直したらこのスクリプトも直して再生成する**（図形の二重管理）。

    python report_assets/make_apple_touch_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "apple-touch-icon.png"

SIZE = 180          # Apple 推奨サイズ
SS = 4              # スーパーサンプリング倍率
CANVAS = 64         # SVG の viewBox

BG = (16, 19, 28, 255)          # #10131c
EAR = (179, 119, 60, 255)       # #b3773c
EAR_IN = (36, 28, 20, 255)      # #241c14
HEAD = (201, 132, 67, 255)      # #c98443
BLAZE = (230, 187, 131, 255)    # #e6bb83
MASK = (36, 28, 20, 255)        # #241c14
EYE = (25, 19, 9, 255)          # #191309
NOSE = (13, 10, 7, 255)         # #0d0a07
WHITE = (255, 255, 255, 235)


def _bez(p0, p1, p2, p3, n=24):
    """3次ベジェを n 点でサンプリング（始点は含む）。"""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def _path(*segments):
    """M + C(複数) を [start, (c1,c2,end), ...] で受け取り、閉じた点列にする。"""
    start, curves = segments[0], segments[1:]
    pts = [start]
    cur = start
    for c1, c2, end in curves:
        pts += _bez(cur, c1, c2, end)[1:]
        cur = end
    return pts


def draw(size: int) -> Image.Image:
    s = size * SS / CANVAS
    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def P(pts):
        return [(x * s, y * s) for x, y in pts]

    # 角丸の背景
    d.rounded_rectangle([0, 0, size * SS - 1, size * SS - 1], radius=14 * s, fill=BG)

    # 立ち耳
    d.polygon(P([(12, 9), (26, 25), (24, 37), (10, 23)]), fill=EAR)
    d.polygon(P([(52, 9), (38, 25), (40, 37), (54, 23)]), fill=EAR)
    d.polygon(P([(15, 14), (23.5, 25.5), (22.6, 32.5), (14, 22)]), fill=EAR_IN)
    d.polygon(P([(49, 14), (40.5, 25.5), (41.4, 32.5), (50, 22)]), fill=EAR_IN)

    # 頭
    head = _path(
        (32, 15),
        ((41.4, 15), (47.5, 21.3), (47.5, 30.2)),
        ((47.5, 40.4), (40.4, 52), (32, 55.5)),
        ((23.6, 52), (16.5, 40.4), (16.5, 30.2)),
        ((16.5, 21.3), (22.6, 15), (32, 15)),
    )
    d.polygon(P(head), fill=HEAD)

    # 額の明るい筋
    blaze = _path(
        (32, 21),
        ((35, 26), (35.6, 31), (34.4, 35)),
        ((29.6, 35), (28.4, 31), (32, 21)),
    )
    d.polygon(P(blaze), fill=BLAZE)

    # 黒いマズル
    muzzle = _path(
        (32, 35.5),
        ((37.6, 35.5), (41.4, 39.4), (41.4, 44.6)),
        ((41.4, 50.4), (37.3, 54.6), (32, 55.5)),
        ((26.7, 54.6), (22.6, 50.4), (22.6, 44.6)),
        ((22.6, 39.4), (26.4, 35.5), (32, 35.5)),
    )
    d.polygon(P(muzzle), fill=MASK)

    # 目
    for cx in (25.4, 38.6):
        d.ellipse(
            [(cx * s - 2.7 * s, 31.4 * s - 2.3 * s), (cx * s + 2.7 * s, 31.4 * s + 2.3 * s)],
            fill=EYE,
        )
    for cx in (26.3, 39.5):
        d.ellipse(
            [(cx * s - 0.85 * s, 30.5 * s - 0.85 * s), (cx * s + 0.85 * s, 30.5 * s + 0.85 * s)],
            fill=WHITE,
        )

    # 鼻
    nose = _path(
        (32, 40.4),
        ((34.5, 40.4), (36.2, 41.9), (36.2, 43.8)),
        ((36.2, 45.7), (34.4, 47.1), (32, 47.1)),
        ((29.6, 47.1), (27.8, 45.7), (27.8, 43.8)),
        ((27.8, 41.9), (29.5, 40.4), (32, 40.4)),
    )
    d.polygon(P(nose), fill=NOSE)

    # 口
    w = max(1, round(1.2 * s))
    d.line(P([(32, 47.1), (32, 49.6)]), fill=NOSE, width=w)
    d.line(P(_bez((32, 49.6), (30.4, 51.2), (28.8, 51.2), (27.6, 50.2)), ), fill=NOSE, width=w)
    d.line(P(_bez((32, 49.6), (33.6, 51.2), (35.2, 51.2), (36.4, 50.2)), ), fill=NOSE, width=w)

    # 首
    neck = _path(
        (24, 52.5),
        ((26.5, 58.5), (37.5, 58.5), (40, 52.5)),
    ) + [(40, 56), (24, 56)]
    d.polygon(P(neck), fill=EAR)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    icon = draw(SIZE).convert("RGB")
    icon.save(OUT, format="PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

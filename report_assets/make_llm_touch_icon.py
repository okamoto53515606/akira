#!/usr/bin/env python3
"""llm.okamomedia.tokyo の apple-touch-icon.png を logo.svg と同じ図形から描く。

なぜ:
    サイトのアイコンは `/logo.svg`（teal の菱形 `#14b8a6` ＋ 濃紺の `L` `#0b1220`）に
    揃えた（2026-11-27 / okamo指示）。iOS のホーム画面アイコンは透過を許さないので、
    `favicon.svg` をそのまま使えず PNG を作る必要がある。
    この環境には SVG のラスタライザ（cairosvg / rsvg-convert / inkscape）が無いため、
    **同じ座標・同じ色を PIL で描く**。図形は二重管理になるので、
    `favicon.svg` / `logo.svg` を直したらこのスクリプトも直して再生成する。

    python report_assets/make_llm_touch_icon.py

出力: s3-snapshot/site/apple-touch-icon.png（S3 の `apple-touch-icon.png` と同内容）
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "s3-snapshot" / "site" / "apple-touch-icon.png"

SIZE = 180          # Apple 推奨サイズ
SS = 4              # スーパーサンプリング倍率
CANVAS = 100        # SVG の viewBox (0 0 100 100)

# logo.svg と同じ色（2026-11-27 実測）
BG = (11, 18, 32, 255)          # #0b1220
DIAMOND = (20, 184, 166, 255)   # #14b8a6 teal
LETTER = (11, 18, 32, 255)      # #0b1220（菱形の上で「抜き」に見える）

# logo.svg の座標（viewBox 100x100）
DIAMOND_PTS = [(50, 5), (95, 50), (50, 95), (5, 50)]
# path d="M36 30 h10 v29 h20 v10 H36 Z"
LETTER_PTS = [(36, 30), (46, 30), (46, 59), (66, 59), (66, 69), (36, 69)]


def _scale(pts, size):
    k = size / CANVAS
    return [(x * k, y * k) for x, y in pts]


def main() -> None:
    big = SIZE * SS
    img = Image.new("RGBA", (big, big), BG)
    draw = ImageDraw.Draw(img)
    draw.polygon(_scale(DIAMOND_PTS, big), fill=DIAMOND)
    draw.polygon(_scale(LETTER_PTS, big), fill=LETTER)
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print("wrote %s (%d bytes, %dx%d)" % (OUT, OUT.stat().st_size, SIZE, SIZE))


if __name__ == "__main__":
    main()

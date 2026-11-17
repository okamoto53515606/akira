"""OGカード（ページ先頭のメインビジュアル）を**台帳から**描き直す（2026-11-17 追加）。

なぜ:
    /china-ai/ のメインビジュアルに「2026-10-29」と「Qwen 4 は学習中」が
    残ったまま、本文だけ 2026-11-14 に更新されていた。原因は**画像が
    生成スクリプトの文字列リテラルで、本文と機械的につながっていない**こと。
    （`parts/og/make_og_2026-10-29.py` の SPECS に直書きされていた）

    ここでは画像の仕様（見出し・箇条書き・URL・日付）を
    `data/og_specs.json` に**データとして**持たせ、描画はコードで行う。
    ページを更新したら「スペックの日付を上げて描き直す」だけになり、
    監査（page_audit.py の R5）が本文の日付と画像の日付のズレを検出できる。

使い方:
    python og_card.py --specs data/og_specs.json --out /tmp/site/assets/og <page>
    python og_card.py --specs data/og_specs.json --list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime

W, H = 1200, 630
BG1 = (9, 17, 28)
BG2 = (16, 32, 48)
ACCENT = (15, 118, 110)     # teal。サイトのアクセントと同系
KICKER = (120, 220, 205)
TEXT = (232, 240, 248)
MUTED = (150, 172, 192)
FOOT = (110, 132, 152)

FONT_DIRS = [
    os.environ.get("AKIRA_FONT_DIR", ""),
    "/tmp/ogfonts",
    "/app/fonts",
    os.path.join(os.environ.get("WORKSPACE_LOCAL_DIR", "/workspace"), "fonts"),
]
FONT_NAMES = {
    True: ["NotoSansJP-Bold.otf", "NotoSansJP-Bold.ttf", "NotoSansCJKjp-Bold.otf"],
    False: ["NotoSansJP-Regular.otf", "NotoSansJP-Regular.ttf", "NotoSansCJKjp-Regular.otf"],
}


def _font_file(bold: bool) -> str:
    """日本語が出せるフォントのパスを返す（無ければ空文字）。"""
    env = os.environ.get("AKIRA_FONT")
    if env and os.path.isfile(env):
        return env
    for d in FONT_DIRS:
        if not d:
            continue
        for name in FONT_NAMES[bold]:
            p = os.path.join(d, name)
            if os.path.isfile(p) and os.path.getsize(p) > 500_000:
                return p
        # ディレクトリ内の *Bold*.otf / *Regular*.otf も許す
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                low = f.lower()
                if not low.endswith((".otf", ".ttf")):
                    continue
                if bold and "bold" in low:
                    return os.path.join(d, f)
                if not bold and "regular" in low:
                    return os.path.join(d, f)
    return ""


def _fonts():
    from PIL import ImageFont  # ローカルimportにして未使用時の依存を避ける

    bold, reg = _font_file(True), _font_file(False)
    if not bold or not reg:
        raise RuntimeError(
            "日本語フォントが見つかりません（/tmp/ogfonts か AKIRA_FONT_DIR に置いてください）")
    cache: dict = {}

    def get(size: int, is_bold: bool = False):
        key = (size, is_bold)
        if key not in cache:
            cache[key] = ImageFont.truetype(bold if is_bold else reg, size)
        return cache[key]

    return get


def _wrap(draw, text: str, font, maxw: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=font) > maxw and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def render(spec: dict, out_path: str) -> str:
    """1枚描いて out_path に保存する。"""
    from PIL import Image, ImageDraw

    get = _fonts()
    im = Image.new("RGB", (W, H), BG1)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)],
               fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3)))
    d.rectangle([0, 0, W, 10], fill=ACCENT)

    d.text((80, 58), spec.get("kicker", "LLM Data Hub"), font=get(30, True), fill=KICKER)
    d.rectangle([80, 116, 220, 124], fill=ACCENT)

    # 見出し（2行に収まるまで縮小）
    size = 74
    while True:
        f = get(size, True)
        lines = _wrap(d, spec.get("title", ""), f, W - 160)
        if len(lines) <= 2 or size <= 44:
            break
        size -= 6
    y = 168
    for ln in lines:
        d.text((80, y), ln, font=f, fill=TEXT)
        y += int(size * 1.28)

    # 箇条書き
    y = max(y + 34, 400)
    f_fact = get(32)
    for fact in spec.get("facts", [])[:3]:
        d.ellipse([82, y + 14, 96, y + 28], fill=ACCENT)
        for i, ln in enumerate(_wrap(d, fact, f_fact, W - 220)):
            d.text((116, y), ln, font=f_fact, fill=TEXT if i == 0 else MUTED)
            y += 44
        y += 8

    d.text((80, H - 64), spec.get("url", "llm.okamomedia.tokyo"),
           font=get(24), fill=FOOT)
    date = spec.get("generated", "")
    f_date = get(24)
    d.text((W - 80 - d.textlength(date, font=f_date), H - 64), date, font=f_date, fill=FOOT)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    im.save(out_path, "PNG", optimize=True)
    return out_path


def facts_digest(spec: dict) -> str:
    """本文（見出し＋箇条書き）のハッシュ。描き忘れ検出の補助に使う。"""
    body = "\n".join([spec.get("kicker", ""), spec.get("title", "")] + spec.get("facts", []))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def load_specs(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_specs(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def render_page(specs_path: str, page: str, out_dir: str, today: str | None = None,
                dry: bool = False) -> dict:
    """1ページ分を描画し、spec の generated を今日に更新して保存する。"""
    data = load_specs(specs_path)
    pages = data.setdefault("pages", {})
    if page not in pages:
        raise KeyError("og_specs に %s がありません" % page)
    spec = pages[page]
    today = today or datetime.now().strftime("%Y-%m-%d")
    spec["generated"] = today
    spec["digest"] = facts_digest(spec)
    out = os.path.join(out_dir, spec["image"])
    if not dry:
        render(spec, out)
        save_specs(specs_path, data)
    return {"page": page, "image": out, "generated": today,
            "digest": spec["digest"], "bytes": os.path.getsize(out) if not dry and os.path.exists(out) else 0}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default=os.path.join(
        os.environ.get("WORKSPACE_LOCAL_DIR", "/workspace"), "data", "og_specs.json"))
    ap.add_argument("--out", default="/tmp/site/assets/og")
    ap.add_argument("--date", default=None)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("pages", nargs="*")
    args = ap.parse_args(argv)

    data = load_specs(args.specs)
    targets = args.pages or sorted(data.get("pages", {}))
    if not targets:
        print("no pages")
        return 1
    for p in targets:
        r = render_page(args.specs, p, args.out, today=args.date, dry=args.dry)
        print("%-38s -> %-28s %s %s" % (p, os.path.basename(r["image"]),
                                        r["generated"], r["digest"]))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))

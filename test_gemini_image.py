# test_gemini_image.py — Gemini画像生成の単体テスト（ローカル実行用）
#
# 目的: 画像生成だけを、Fargateを介さずローカルで確認する。
#   - バナー/図解で実際に使う BANNER_MODEL（既定 gemini-3.1-flash-image）で1枚作る
#   - 生成した画像を GEMINI_MODEL_ID（視認チェック役）で読めるか確認する
#   - 画像系モデルの一覧と、いくつかの候補モデルでの成否も並べて出す
#
# 安全のため: S3への公開・DynamoDBへのusage記録は行わない（ローカルの/tmpに置くだけ）。
#
# 使い方:
#   uv run python test_gemini_image.py
#   uv run python test_gemini_image.py --all      # 画像系モデルを総当たり
#   uv run python test_gemini_image.py --out /tmp/my.png
#
# 前提: .env の GEMINI_API_KEY（FargateはSecrets Managerから取得。同じキーかは
#       起動ログでは分からないため、必要なら Secrets Manager の値と突き合わせる）。

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv(".env")

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

import settings  # noqa: E402

DEFAULT_PROMPT = (
    "暗い背景(#0f1117)に、AIモデルのベンチマーク比較を示す横棒グラフを2本。"
    "ラベルは日本語（標準ハーネス 62.7% / 提供元ハーネス 99.9%）。"
    "文字が崩れないシンプルな図。"
)


def generate(client, model: str, prompt: str, out: Path) -> bool:
    """1枚生成して保存。成功したらTrue。"""
    try:
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
    except Exception as e:
        print(f"  NG (API) {type(e).__name__}: {str(e)[:220]}")
        return False

    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            data = getattr(getattr(part, "inline_data", None), "data", None)
            if data:
                out.write_bytes(data)
                mime = getattr(part.inline_data, "mime_type", "?")
                print(f"  OK {len(data):,}bytes ({mime}) -> {out}")
                return True
    # 画像が返らなかった場合（拒否・parts空など）は中身を出す
    reasons = [
        f"finish_reason={getattr(c, 'finish_reason', None)}" for c in (resp.candidates or [])
    ] or ["candidates=[]"]
    print(f"  NG 画像が返らず: {' / '.join(reasons)}")
    return False


def vision_check(client, model: str, image: Path) -> None:
    """生成した画像を text モデルで読めるか（文字化け・内容確認の入口）。"""
    if not image.exists():
        print(f"  （{image} が無いのでスキップ）")
        return
    try:
        resp = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=image.read_bytes(), mime_type="image/png"),
                "この画像の内容と、ラベルの文字が正しく読めるかを3行以内で。",
            ],
        )
        print(f"  OK {(resp.text or '').strip()[:300]}")
    except Exception as e:
        print(f"  NG {type(e).__name__}: {str(e)[:220]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="画像系モデルを総当たりで試す")
    ap.add_argument("--out", default="/tmp/gemini-image-test.png")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = ap.parse_args()

    key = os.getenv("GEMINI_API_KEY", "")
    print(f"GEMINI_API_KEY: {'あり' if key else 'なし'}")
    if not key:
        print("  .env に GEMINI_API_KEY を設定してください（値は表示しません）")
        return 2
    print(f"BANNER_MODEL(画像生成) = {settings.IMAGE_MODEL_ID}")
    print(f"GEMINI_MODEL_ID(視認)  = {settings.GEMINI_MODEL_ID}")

    client = genai.Client(api_key=key)
    out = Path(args.out)

    print(f"\n[1] 画像生成（{settings.IMAGE_MODEL_ID}）")
    ok = generate(client, settings.IMAGE_MODEL_ID, args.prompt, out)

    print(f"\n[2] 生成画像の視認（{settings.GEMINI_MODEL_ID}）")
    vision_check(client, settings.GEMINI_MODEL_ID, out)

    if args.all:
        print("\n[3] 画像系モデルの総当たり")
        try:
            names = sorted(
                {
                    (getattr(m, "name", "") or "").replace("models/", "")
                    for m in client.models.list()
                }
            )
        except Exception as e:
            names = []
            print(f"  モデル一覧の取得に失敗: {type(e).__name__}")
        for name in [n for n in names if "image" in n]:
            print(f"  - {name}")
            generate(client, name, args.prompt, Path("/tmp") / f"gemini-{name}.png")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

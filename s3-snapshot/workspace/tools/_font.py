"""OG画像用フォントの解決（2026-11-15 追加）。

なぜ要るか:
    Fargate のイメージ（python:3.12-slim）には**フォントが1つも入っていない**。
    そのため各OG生成スクリプトが毎回 Noto Sans JP をネットから落としていた。
    - 実行のたびに 9.1MB のDL（時間と失敗要因）
    - URLが変われば全スクリプトが同時に壊れる
    - 「Noto以外にしたい」と思っても6箇所直す必要がある

方針:
    **フォントはイメージに焼き込む**（Dockerfile が /tmp/ogfonts に置く）。
    このモジュールは「どこにあるか」を探すだけで、**ネットワークに出ない**。
    Noto は特定の書体を強制するためではなく「日本語が出ればいい」の既定値。
    `AKIRA_FONT` 環境変数か `/workspace/fonts/` に置けば差し替えられる。

探す順:
    1. 環境変数 AKIRA_FONT（.otf/.ttf への絶対パス）
    2. AKIRA_FONT_DIR / /tmp/ogfonts / /app/fonts / <workspace>/fonts
    3. システム（/usr/share/fonts 以下の CJK っぽい名前）
    4. 最後の手段として1回だけDLし、<workspace>/fonts に保存する
       （S3に永続化されるので2回目以降は落ちない。イメージが正しければここは通らない）
"""
from __future__ import annotations

import os
import re
import urllib.request
from functools import lru_cache

from PIL import ImageFont

FALLBACK_URLS = {
    'bold': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf',
    'reg': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf',
}
SEARCH_DIRS = ['/tmp/ogfonts', '/app/fonts']
CJK_HINT = re.compile(r'(noto.*(cjk|jp|japan)|sourcehan|ipa|takao|vl-?gothic|biwaw|migmix)', re.I)
MIN_SIZE = 500_000  # これ未満は壊れたダウンロード


def _workspace() -> str:
    return os.environ.get('WORKSPACE_LOCAL_DIR') or '/workspace'


def _looks_like_font(p: str) -> bool:
    return p.lower().endswith(('.otf', '.ttf')) and os.path.getsize(p) >= MIN_SIZE


@lru_cache(maxsize=8)
def font_path(bold: bool = False) -> str:
    """使える日本語フォントのパスを返す。見つからなければ空文字。"""
    kind = 'bold' if bold else 'reg'

    env = os.environ.get('AKIRA_FONT')
    if env and os.path.isfile(env):
        return env

    dirs = []
    if os.environ.get('AKIRA_FONT_DIR'):
        dirs.append(os.environ['AKIRA_FONT_DIR'])
    dirs += SEARCH_DIRS + [os.path.join(_workspace(), 'fonts')]

    want = 'bold' if bold else 'regular'
    for d in dirs:
        if not os.path.isdir(d):
            continue
        files = [os.path.join(d, f) for f in sorted(os.listdir(d))
                 if _looks_like_font(os.path.join(d, f))]
        # 「Bold」を含むものを優先（--bold 指定時）、含まないものを優先（通常時）
        pick = [f for f in files if ('bold' in os.path.basename(f).lower()) == bold]
        for f in (pick or files):
            return f

    # システムフォント
    for root in ('/usr/share/fonts', '/usr/local/share/fonts'):
        for dirpath, _dn, fns in os.walk(root):
            for fn in sorted(fns):
                if _looks_like_font(os.path.join(dirpath, fn)) and CJK_HINT.search(fn):
                    return os.path.join(dirpath, fn)

    # 最後の手段（イメージに焼き込まれていれば到達しない）
    out_dir = os.path.join(_workspace(), 'fonts')
    p = os.path.join(out_dir, 'NotoSansJP-%s.otf' % ('Bold' if bold else 'Regular'))
    try:
        os.makedirs(out_dir, exist_ok=True)
        if not os.path.exists(p) or os.path.getsize(p) < MIN_SIZE:
            urllib.request.urlretrieve(FALLBACK_URLS[kind], p)
        return p
    except Exception:  # noqa: BLE001
        return ''


def get_font(size: int, bold: bool = False):
    """PILのフォントを返す。日本語フォントが無い環境では標準フォントに退避する。"""
    p = font_path(bold)
    if p:
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            pass
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow 9 以前
        return ImageFont.load_default()


def used_fonts() -> dict:
    """どのフォントを使うかを確認する（日報・デバッグ用）。"""
    return {'bold': font_path(True), 'regular': font_path(False)}


if __name__ == '__main__':
    import json
    print(json.dumps(used_fonts(), ensure_ascii=False, indent=1))

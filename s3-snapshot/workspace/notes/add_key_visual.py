# -*- coding: utf-8 -*-
"""OG画像をページ上部のヒーロー（key-visual）として貼る。2026-11-15。

なぜ（okamo指摘）:
    `/image-api-pricing/` を「見やすいとは言えない。色の変化が少なすぎるし、
    イメージ図がない」と言われた。調べると **OG画像は作ってある（507KB）のに
    ページに貼っていない**ページが4つあった（image-api / speech / china-ai /
    multimodal）。SNSで見る絵と、サイトで見る絵が別物になっていた。

やること:
    `<main>` の直後（`.container` の中）に
        <figure class="key-visual"><img src="/assets/og/<lang>-<slug>.png" ...></figure>
    を入れる。既に `key-visual` があるページは触らない（冪等）。

安全策:
    - OG画像が実際に S3 に存在するページだけ（HEADで確認）
    - og:image のパスをそのまま使うので、日英で取り違えない
"""
import os
import re
import subprocess
import sys

SITE = os.environ.get('SITE_DIR', '/home/workspace/akira/s3-snapshot/site')
BUCKET = 'akira-llm-site'
REGION = 'us-east-1'


def _exists(key: str) -> bool:
    r = subprocess.run(['aws', '--region', REGION, 's3api', 'head-object',
                        '--bucket', BUCKET, '--key', key],
                       capture_output=True, text=True)
    return r.returncode == 0


def _figure(lang: str, path: str, alt: str) -> str:
    return (
        '<figure class="key-visual" style="margin:1.5rem 0 .5rem;">'
        '<img src="%s" alt="%s" width="1200" height="630" loading="eager" '
        'decoding="async" style="width:100%%;max-width:900px;height:auto;'
        'display:block;margin:0 auto;border:1px solid var(--c-border);'
        'border-radius:var(--r-md);"></figure>\n' % (path, alt))


ALTS = {
    'ja': 'このページの内容を1枚にまとめた画像',
    'en': 'A single image summarising this page',
}


def main() -> int:
    pages = []
    for root, _dirs, files in os.walk(SITE):
        if 'index.html' in files and 'assets' not in root:
            pages.append(os.path.join(root, 'index.html'))

    added = skipped = missing = 0
    for path in sorted(pages):
        rel = os.path.relpath(path, SITE).replace(os.sep, '/')
        lang = 'en' if rel.startswith('en/') else 'ja'
        s = open(path, encoding='utf-8').read()
        if 'class="key-visual"' in s:
            skipped += 1
            continue
        m = re.search(r'<meta property="og:image" content="([^"]+)"', s)
        if not m:
            continue
        url = m.group(1)
        if '/assets/og/' not in url:
            continue
        key = 'assets/og/' + url.rsplit('/assets/og/', 1)[1]
        if not _exists(key):
            missing += 1
            print('  ! OG画像が無い: %s -> %s' % (rel, key))
            continue
        local_path = '/' + key
        fig = _figure(lang, local_path, ALTS[lang])
        i = s.find('<main>')
        if i < 0:
            continue
        # class="container" には style が付くことがある（例: padding-top:2rem;）
        m2 = re.search(r'<div class="container"[^>]*>', s[i:])
        if not m2:
            continue
        k = i + m2.end()
        s2 = s[:k] + '\n' + fig + s[k:]
        open(path, 'w', encoding='utf-8').write(s2)
        added += 1
        print('  + %s' % rel)
    print('貼った: %d / 既に有り: %d / 画像なし: %d' % (added, skipped, missing))
    return 0


if __name__ == '__main__':
    sys.exit(main())

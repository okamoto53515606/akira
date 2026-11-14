# -*- coding: utf-8 -*-
"""Idempotent wiring for /speech-api-pricing/ (+ frontier Carbon GA row).

Usage (after restoring live site into /tmp/site and copying the new HTML/PNG files):
    python3 apply_wiring.py
Safe to run twice: every step checks whether it is already applied.
"""
import pathlib, sys

SITE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/site')
TODAY = '2026-11-15'
B = 'https://llm.okamomedia.tokyo'
done = []

def read(rel):
    return (SITE / rel).read_text(encoding='utf-8')

def write(rel, s):
    (SITE / rel).write_text(s, encoding='utf-8')

# 1. sitemap
s = read('sitemap.xml')
if 'speech-api-pricing' not in s:
    block = ('<url><loc>%s/speech-api-pricing/</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>\n'
             '<url><loc>%s/en/speech-api-pricing/</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>\n'
             % (B, TODAY, B, TODAY))
    assert s.count('</urlset>') == 1
    write('sitemap.xml', s.replace('</urlset>', block + '</urlset>'))
    done.append('sitemap')

# 2. llms.txt (both language sections)
s = read('llms.txt')
if '/en/speech-api-pricing/' not in s:
    a = '- [Token Cost Calculator](https://llm.okamomedia.tokyo/en/calculator/)'
    assert s.count(a) == 1
    s = s.replace(a, ('- [Speech API Pricing Compared](https://llm.okamomedia.tokyo/en/speech-api-pricing/): '
                      'TTS and transcription rates from OpenAI, Google, Microsoft and Meta, converted from per-1M-character, '
                      'per-1M-token and per-hour pricing into a common per-minute basis; deprecated and time-limited prices flagged.\n') + a)
    done.append('llms-en')
if '/speech-api-pricing/' not in s.replace('/en/speech-api-pricing/', ''):
    b = '- [Batch API割引の横断比較](https://llm.okamomedia.tokyo/batch-api-pricing/)'
    assert s.count(b) == 1
    i = s.find(b)
    j = s.find('\n', i)
    add = ('\n- [フロンティアモデル横断比較](https://llm.okamomedia.tokyo/frontier-model-comparison/): キャッシュ単価・Batch・ZDR・ZOA・学習利用・データ所在地・コンテキスト長の横断比較。'
           '\n- [プロンプトキャッシュ料金の横断比較](https://llm.okamomedia.tokyo/prompt-cache-pricing/): 書込／読込単価・割引率・保持期間・最小キャッシュ長。'
           '\n- [音声API料金比較](https://llm.okamomedia.tokyo/speech-api-pricing/): TTS・文字起こしの単価を1分／1時間あたりに正規化。Deprecated表記と期間限定価格、2027年の改定予定まで明記。')
    s = s[:j] + add + s[j:]
    done.append('llms-ja')
write('llms.txt', s)

# 3. top-page cards (insert directly before the kimi card)
CARDS = {
 'index.html': ('/kimi-k3-1-pro/', '🎙️', '音声API料金比較 — TTS・文字起こしを1分あたりに正規化',
   'OpenAI・Google・Microsoft・Metaの音声APIを「1分あたり」「1時間あたり」に換算して横断比較。1M文字建てと1Mトークン建てでは<strong>数字の大小が逆転する</strong>。文字起こしは$0.10〜$1.02/時間。換算の前提と公式の逐語、2026-11-15取得。',
   '/speech-api-pricing/', '音声API料金比較を見る →'),
 'en/index.html': ('/en/kimi-k3-1-pro/', '🎙️', 'Speech API pricing — TTS and transcription per minute',
   'OpenAI, Google, Microsoft and Meta speech APIs converted to a per-minute and per-hour basis. Per-1M-character and per-1M-token pricing <strong>ranks in the opposite order</strong> once normalized. Transcription runs $0.10 to $1.02 per hour of audio.',
   '/en/speech-api-pricing/', 'See speech API pricing →'),
}
for rel, (anchor, icon, title, desc, href, cta) in CARDS.items():
    s = read(rel)
    if 'speech-api-pricing' not in s:
        pos = s.find(anchor)
        assert pos > 0, rel
        open_tag = '<article class="card">'
        start = s.rfind(open_tag, 0, pos) + len(open_tag)
        card = ('<div class="card-icon">%s</div><h3 class="card-title">%s</h3>'
                '<p class="card-desc">%s</p><a href="%s" class="card-link">%s</a></article>' % (icon, title, desc, href, cta))
        # the original open tag already closes with '>' right before content; insert after it
        s = s[:start] + card + '<article class="card">' + s[start:]
        write(rel, s)
        done.append(rel)

# 4. frontier: Gemini 4 Carbon GA
rows = (('frontier-model-comparison/index.html',
         '料金ページに段階の表記がない。当サイトの年表は11-10の一般提供として記録しているが、本ページでは料金ページに載っている事実（有料枠の単価）だけを記載した',
         '<strong>2026-11-10 に一般提供（GA）</strong>。料金ページ自体には段階の表記がないため、提供段階は運営（okamo）の確認として記録し、単価は料金ページの有料枠の値のみを記載している'),
        ('en/frontier-model-comparison/index.html',
         'The pricing page carries no stage label. Our timeline records it as generally available on 11-10; this page states only what the pricing page shows (a paid-tier rate)',
         "<strong>Generally available (GA) on 2026-11-10.</strong> The pricing page itself carries no stage label, so the stage is recorded from the operator's confirmation (okamo); the rates come only from the paid-tier figures on that page"))
for rel, old, new in rows:
    s = read(rel)
    if new in s:
        continue
    assert s.count(old) == 1, rel
    write(rel, s.replace(old, new))
    done.append(rel)

print('applied:', done or 'nothing (already wired)')

# -*- coding: utf-8 -*-
"""Wire up the new speech-api-pricing pages: sitemap, llms.txt, top-page cards,
and the Gemini 4 Carbon GA fact on the frontier pages."""
import pathlib, re

SITE = pathlib.Path('/tmp/site')
TODAY = '2026-11-14'
B = 'https://llm.okamomedia.tokyo'
changed = []

def sub1(text, old, new, label):
    assert text.count(old) == 1, '%s: count=%d' % (label, text.count(old))
    return text.replace(old, new)

# ---------------------------------------------------------------- sitemap
p = SITE / 'sitemap.xml'
s = p.read_text(encoding='utf-8')
assert 'speech-api-pricing' not in s
block = ('<url><loc>%s/speech-api-pricing/</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>\n'
         '<url><loc>%s/en/speech-api-pricing/</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>\n'
         % (B, TODAY, B, TODAY))
s = sub1(s, '</urlset>', block + '</urlset>', 'sitemap')
# frontier row correction also refreshes its lastmod (already 2026-11-14 -> keep)
p.write_text(s, encoding='utf-8'); changed.append('sitemap.xml')

# ---------------------------------------------------------------- llms.txt
p = SITE / 'llms.txt'
s = p.read_text(encoding='utf-8')
en_anchor = '- [Token Cost Calculator](https://llm.okamomedia.tokyo/en/calculator/)'
en_new = ('- [Speech API Pricing Compared](https://llm.okamomedia.tokyo/en/speech-api-pricing/): '
          'TTS and transcription rates from OpenAI, Google, Microsoft and Meta, converted from per-1M-character, '
          'per-1M-token and per-hour pricing into a common per-minute basis; time-limited prices flagged.\n') + en_anchor
s = sub1(s, en_anchor, en_new, 'llms en')

ja_batch = '- [Batch API割引の横断比較](https://llm.okamomedia.tokyo/batch-api-pricing/): OpenAI・Anthropic・Google・xAI・MoonshotのBatch割引率と締切・保持期間・上限、DeepSeekのオフピーク割引。'
ja_add = (ja_batch + '\n'
          '- [フロンティアモデル横断比較](https://llm.okamomedia.tokyo/frontier-model-comparison/): キャッシュ単価・Batch・ZDR・ZOA・学習利用・データ所在地・コンテキスト長の横断比較。\n'
          '- [プロンプトキャッシュ料金の横断比較](https://llm.okamomedia.tokyo/prompt-cache-pricing/): 書込／読込単価・割引率・保持期間・最小キャッシュ長。\n'
          '- [音声API料金比較](https://llm.okamomedia.tokyo/speech-api-pricing/): TTS・文字起こしの単価を1分／1時間あたりに正規化。期間限定価格と2027年の改定予定を明記。')
s = sub1(s, ja_batch, ja_add, 'llms ja')
p.write_text(s, encoding='utf-8'); changed.append('llms.txt')

# ---------------------------------------------------------------- top page cards
cards = {
 'index.html': ('🎙️', '音声API料金比較 — TTS・文字起こしを1分あたりに正規化',
   'OpenAI・Google・Microsoft・Metaの音声APIを「1分あたり」「1時間あたり」に換算して横断比較。1M文字建てと1Mトークン建てでは<strong>数字の大小が逆転する</strong>（tts-1 $0.0045/分 vs Gemini 3.8 Flash TTS $0.0135/分）。文字起こしは$0.10〜$1.02/時間。換算の前提と公式の逐語、2026-11-14取得。',
   '/speech-api-pricing/', '音声API料金比較を見る →', 'kimi-k3-1-pro'),
 'en/index.html': ('🎙️', 'Speech API pricing — TTS and transcription normalized per minute',
   'OpenAI, Google, Microsoft and Meta speech APIs converted to a per-minute and per-hour basis. Per-1M-character and per-1M-token pricing <strong>ranks in the opposite order</strong> once normalized (tts-1 $0.0045/min vs Gemini 3.8 Flash TTS $0.0135/min). Transcription runs $0.10 to $1.02 per hour of audio.',
   '/en/speech-api-pricing/', 'See speech API pricing →', 'kimi-k3-1-pro'),
}
for rel, (icon, title, desc, href, cta, anchor) in cards.items():
    p = SITE / rel
    s = p.read_text(encoding='utf-8')
    parts = s.split('<article class="card">')
    idx = None
    pre = '/en/' if rel.startswith('en/') else '/'
    want = pre + anchor
    for i, blk in enumerate(parts[1:], start=1):
        if want in blk.split('</article>')[0]:
            idx = i
            break
    assert idx, rel
    new_card = ('<article class="card"><div class="card-icon">%s</div><h3 class="card-title">%s</h3>'
                '<p class="card-desc">%s</p><a href="%s" class="card-link">%s</a></article>' % (icon, title, desc, href, cta))
    parts.insert(idx, new_card)
    out = '<article class="card">'.join(parts)
    p.write_text(out, encoding='utf-8'); changed.append(rel)

# ---------------------------------------------------------------- frontier: Carbon GA row
ja_old = '料金ページに段階の表記がない。当サイトの年表は11-10の一般提供として記録しているが、本ページでは料金ページに載っている事実（有料枠の単価）だけを記載した'
ja_new = ('<strong>2026-11-10 に一般提供（GA）</strong>。料金ページ自体には段階の表記がないため、'
          '提供段階は運営（okamo）の確認として記録し、単価は料金ページの有料枠の値のみを記載している')
en_old = 'The pricing page carries no stage label. Our timeline records it as generally available on 11-10; this page states only what the pricing page shows (a paid-tier rate)'
en_new = ('<strong>Generally available (GA) on 2026-11-10.</strong> The pricing page itself carries no stage label, '
          'so the stage is recorded from the operator\'s confirmation (okamo); the rates come only from the paid-tier figures on that page')
for rel, old, new in (('frontier-model-comparison/index.html', ja_old, ja_new),
                      ('en/frontier-model-comparison/index.html', en_old, en_new)):
    p = SITE / rel
    s = p.read_text(encoding='utf-8')
    s = sub1(s, old, new, rel)
    p.write_text(s, encoding='utf-8'); changed.append(rel)

print('changed:', changed)

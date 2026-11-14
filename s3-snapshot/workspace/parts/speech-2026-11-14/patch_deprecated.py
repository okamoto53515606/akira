# -*- coding: utf-8 -*-
"""Apply tax-advisor findings: OpenAI TTS deprecation, EN narration direction, Gemini output basis."""
import pathlib
SITE = pathlib.Path('/tmp/site')

def patch(rel, pairs):
    p = SITE / rel
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert s.count(old) == 1, (rel, old[:60], s.count(old))
        s = s.replace(old, new)
    p.write_text(s, encoding='utf-8')
    print('patched', rel, len(pairs))

# ---------------------------------------------------------------- JA
JA = [
# A) headline card
('<div class="num-card"><div class="k">TTS 最安（1分あたり）</div><div class="v">$0.0045</div><div class="d">OpenAI tts-1 と MAI-Voice-2.1-Flash。どちらも「1M文字 $15」の文字課金。</div></div>',
 '<div class="num-card"><div class="k">TTS 最安（1分あたり・現行）</div><div class="v">$0.0045</div><div class="d">MAI-Voice-2.1-Flash（1M文字 $15）。同額の OpenAI tts-1 はモデルページに <strong>Deprecated</strong> 表記があり、新規採用の候補にならない。</div></div>'),
# B) read-box tail
('単位をそろえずに「$9 対 $15」で比べると、選定を誤ります。',
 '単位をそろえずに「$9 対 $15」で比べると、選定を誤ります。なお、この例に使った OpenAI tts-1 は2026-11-14時点で<strong>モデルページに Deprecated 表記</strong>があります（下のTTS表を参照）。'),
# C) note before the TTS table
('<h2 class="section-title" style="font-size:1.15rem;">読み上げ（TTS）の比較 — 1分あたり・1,000文字あたり</h2>\n<div class="table-wrap">',
 '<h2 class="section-title" style="font-size:1.15rem;">読み上げ（TTS）の比較 — 1分あたり・1,000文字あたり</h2>\n'
 '<div class="read-box"><strong>先に読んでください（2026-11-14確認）</strong>: OpenAI の音声生成モデル <code>tts-1</code> / <code>tts-1-hd</code> / <code>gpt-4o-mini-tts</code> は、いずれも<strong>モデルページのモデル名直下に「Deprecated」と明記</strong>されています。単価はそのページに残っているため比較用に掲載しますが、<strong>新規採用の候補にはなりません</strong>。OpenAI の Audio 料金ページにも文字単価のTTSは載っておらず、現行の音声課金は <strong>GPT-Live（$0.05/分・秒単位）</strong>と Realtime 系（トークン課金）に移っています。</div>\n'
 '<div class="table-wrap">'),
# D) deprecation memos
('<td>公式が「realtime text-to-speech 向け」と明記</td>',
 '<td>公式が「realtime text-to-speech 向け」と明記。<strong>モデルページに Deprecated 表記</strong></td>'),
('<td>モデルページの比較表の値</td>', '<td>モデルページの比較表の値。<strong>Deprecated</strong></td>'),
('<td>音声トークンの秒換算は公式に記載が無い（表下の†参照）</td>',
 '<td>音声トークンの秒換算は公式に記載が無い（表下の†参照）。<strong>モデルページに Deprecated 表記</strong></td>'),
# E) Gemini Transcribe output basis
('<td>出力（テキスト）は $12.00 / 1M tokens ＝ $0.002 / 分</td>',
 '<td>出力（テキスト）は $12.00 / 1M tokens。公式の $0.002 / 分は<strong>175テキストトークン/分</strong>を前提にした目安</td>'),
# F) narration bullet
('<li><strong>ナレーション・読み上げ</strong> → 1,000文字あたり $0.015（OpenAI tts-1・MAI-Voice-2.1-Flash）〜$0.10（Gemini 3.1 Flash TTS Preview）。長尺の固定原稿なら文字課金の2モデルが読みやすい。</li>',
 '<li><strong>ナレーション・読み上げ</strong> → 文字課金で<strong>現行</strong>の最安は MAI-Voice-2.1-Flash（1,000文字 $0.015）。OpenAI の文字課金TTS 3モデルは Deprecated なので、新規は GPT-Live（$0.05/分・秒単位）か Gemini のトークン課金で見積もる。上限側は Gemini 3.1 Flash TTS Preview（1,000文字 $0.10）。</li>'),
# G) verbatim additions
('<blockquote class="verb">"$15.00"（Cost / 1M characters, Speech generation）',
 '<blockquote class="verb">"tts-1" … "Deprecated" ／ "GPT-4o mini TTS" … "Deprecated"（モデルページのモデル名直下ラベル）<br>— OpenAI, tts-1 / gpt-4o-mini-tts モデルページ（2026-11-14）</blockquote>\n'
 '<blockquote class="verb">"gpt-live-1 | $0.05" … "GPT-Live-1 voice sessions are billed per second, without rounding up to a whole minute. Backend model and tool usage is charged separately."<br>— OpenAI, Pricing（Audio / GPT-Live）</blockquote>\n'
 '<blockquote class="verb">"$15.00"（Cost / 1M characters, Speech generation）'),
# H) source note
('（$15.00 / 1M characters、tts-1-hd $30.00）',
 '（$15.00 / 1M characters、tts-1-hd $30.00。<strong>両ページともモデル名直下に Deprecated 表記</strong>）'),
]
patch('speech-api-pricing/index.html', JA)

# ---------------------------------------------------------------- EN
EN = [
('<div class="num-card"><div class="k">Cheapest TTS (per minute)</div><div class="v">$0.0045</div><div class="d">OpenAI tts-1 and MAI-Voice-2.1-Flash. Both are charging $15 per 1M characters.</div></div>',
 '<div class="num-card"><div class="k">Cheapest TTS (per minute, current)</div><div class="v">$0.0045</div><div class="d">MAI-Voice-2.1-Flash ($15 per 1M characters). OpenAI tts-1 matches it, but its model page labels it <strong>Deprecated</strong>, so it is not a candidate for new work.</div></div>'),
('Comparing $9 against $15 without normalizing the unit gets the decision exactly backwards.',
 'Comparing $9 against $15 without normalizing the unit gets the decision exactly backwards. (The OpenAI tts-1 used in this example is labelled <strong>Deprecated</strong> as of 2026-11-14 — see the table below.)'),
('<h2 class="section-title" style="font-size:1.15rem;">Text-to-speech, normalized</h2>\n<div class="table-wrap">',
 '<h2 class="section-title" style="font-size:1.15rem;">Text-to-speech, normalized</h2>\n'
 '<div class="read-box"><strong>Read this first (checked 2026-11-14)</strong>: every OpenAI speech-generation model in this table — <code>tts-1</code>, <code>tts-1-hd</code> and <code>gpt-4o-mini-tts</code> — carries a <strong>&quot;Deprecated&quot; label directly under its name on its model page</strong>. We keep them for comparison because the prices are still published, but <strong>none of them is a candidate for new work</strong>. OpenAI\'s Audio pricing page no longer lists a per-character TTS model at all: current audio billing runs through <strong>GPT-Live ($0.05 per minute, billed per second)</strong> and the Realtime models (token-billed).</div>\n'
 '<div class="table-wrap">'),
('<td>Docs describe it as &quot;optimized for realtime text-to-speech use cases&quot;</td>',
 '<td>Docs describe it as &quot;optimized for realtime text-to-speech use cases&quot;. <strong>Deprecated</strong> on the model page</td>'),
('<td>From the model page comparison table</td>', '<td>From the model page comparison table. <strong>Deprecated</strong></td>'),
('<td>No official second-to-token conversion for audio output</td>',
 '<td>No official second-to-token conversion for audio output. <strong>Deprecated</strong> on the model page</td>'),
('<td>Output text $12.00 / 1M tokens = $0.002 / min</td>',
 '<td>Output text $12.00 / 1M tokens; the vendor\'s $0.002/min figure assumes <strong>175 text tokens per minute</strong></td>'),
# narration direction fix
('English narration is usually faster (about 900 characters per minute), which lowers the per-minute cost of character-priced models by roughly two thirds. Because the same factor applies to every vendor, <strong>the ranking between vendors does not change</strong>; only the absolute cents move.',
 'English narration is usually faster (about 900 characters per minute), so one minute of English speech consumes about three times as many characters: character-priced models therefore cost roughly three times the per-minute figures below. The <strong>per-1,000-character columns and the ranking between vendors do not change</strong>; only the per-minute numbers move.'),
('<li><strong>Narration and voice-overs</strong> → $0.015 per 1,000 characters (OpenAI tts-1, MAI-Voice-2.1-Flash) up to $0.10 (Gemini 3.1 Flash TTS Preview). For long fixed scripts, character-priced models are easier to forecast.</li>',
 '<li><strong>Narration and voice-overs</strong> → the cheapest <strong>current</strong> character-billed option is MAI-Voice-2.1-Flash ($0.015 per 1,000 characters); all three OpenAI character-billed TTS models are deprecated, so price new work on GPT-Live ($0.05/min, per second) or Gemini\'s token billing. At the top end, Gemini 3.1 Flash TTS Preview is $0.10 per 1,000 characters.</li>'),
('<blockquote class="verb">&quot;$15.00&quot; (Cost / 1M characters, Speech generation)',
 '<blockquote class="verb">&quot;tts-1&quot; … &quot;Deprecated&quot; / &quot;GPT-4o mini TTS&quot; … &quot;Deprecated&quot; (label directly under the model name)<br>— OpenAI, tts-1 and gpt-4o-mini-tts model pages (2026-11-14)</blockquote>\n'
 '<blockquote class="verb">&quot;gpt-live-1 | $0.05&quot; … &quot;GPT-Live-1 voice sessions are billed per second, without rounding up to a whole minute. Backend model and tool usage is charged separately.&quot;<br>— OpenAI, Pricing (Audio / GPT-Live)</blockquote>\n'
 '<blockquote class="verb">&quot;$15.00&quot; (Cost / 1M characters, Speech generation)'),
('($15.00 / 1M characters; tts-1-hd $30.00)',
 '($15.00 / 1M characters; tts-1-hd $30.00 — <strong>both pages carry a Deprecated label</strong>)'),
]
patch('en/speech-api-pricing/index.html', EN)

# ---------------------------------------------------------------- OG images (mention deprecation)
import os, urllib.request
from PIL import Image, ImageDraw, ImageFont
OGDIR = SITE / 'assets/og'; FONTDIR = pathlib.Path('/tmp/ogfonts')
URLS = {'bold': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf',
        'reg': 'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf'}
def F(kind, size):
    p = FONTDIR / ('NotoSansJP-%s.otf' % ('Bold' if kind == 'bold' else 'Regular'))
    if not p.exists() or p.stat().st_size < 500000:
        urllib.request.urlretrieve(URLS[kind], str(p))
    return ImageFont.truetype(str(p), size)
W, H = 1200, 630
BG1, BG2, ACC, TEXT, MUTED = (6, 20, 24), (12, 42, 48), (16, 148, 140), (235, 244, 246), (186, 208, 212)
def bg():
    img = Image.new('RGB', (W, H), BG1); d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(BG1[0]+(BG2[0]-BG1[0])*t), int(BG1[1]+(BG2[1]-BG1[1])*t), int(BG1[2]+(BG2[2]-BG1[2])*t)))
    d.rectangle([0, 0, 14, H], fill=ACC); d.rectangle([70, H-96, W-70, H-94], fill=(40, 80, 86))
    return img, d
def wrap(d, text, font, maxw):
    out, cur = [], ''
    for ch in text:
        if d.textlength(cur+ch, font=font) <= maxw: cur += ch
        else: out.append(cur); cur = ch
    if cur: out.append(cur)
    return out
SPECS = [
 ('ja-speech-api-pricing.png', 'OPENAI · GOOGLE · MICROSOFT · META', '音声APIの料金は「1分」に直して比べる',
  ['1M文字建てと1Mトークン建てで数字の大小が逆転する',
   'tts-1 $0.0045/分（Deprecated） vs Gemini 3.8 Flash TTS $0.0135/分',
   '文字起こしは $0.10〜$1.02 / 音声1時間',
   'Gemini TTS 2モデルは2027-01-01に2倍'],
  'llm.okamomedia.tokyo/speech-api-pricing/'),
 ('en-speech-api-pricing.png', 'OPENAI · GOOGLE · MICROSOFT · META', 'Speech APIs priced per minute',
  ['Per-1M-character and per-1M-token prices rank in reverse',
   'tts-1 $0.0045/min (deprecated) vs Gemini 3.8 Flash TTS $0.0135/min',
   'Transcription: $0.10 to $1.02 per hour of audio',
   'Two Gemini TTS models double on 2027-01-01'],
  'llm.okamomedia.tokyo/en/speech-api-pricing/'),
]
for fn, kicker, title, facts, url in SPECS:
    img, d = bg()
    d.text((70, 64), kicker, font=F('bold', 30), fill=(120, 214, 206))
    y = 120
    size = 72 if len(title) <= 22 else 62
    for ln in wrap(d, title, F('bold', size), W-150):
        d.text((70, y), ln, font=F('bold', size), fill=TEXT); y += size + 14
    y += 10; d.rectangle([70, y, 150, y+6], fill=ACC); y += 32
    for f in facts:
        for i, ln in enumerate(wrap(d, f, F('reg', 30), W-200)):
            d.text((70 if i == 0 else 100, y), ('•  ' if i == 0 else '')+ln, font=F('reg', 30), fill=MUTED)
            y += 44
        y += 4
    d.text((70, H-70), url, font=F('reg', 26), fill=(110, 146, 152))
    img.save(OGDIR / fn, 'PNG', optimize=True)
    print('og', fn, os.path.getsize(OGDIR / fn))

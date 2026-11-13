import re, io, os, json

SITE = '/tmp/site'
TODAY = '2026-10-29'
BASE = 'https://llm.okamomedia.tokyo'

def rd(p): return open(p, encoding='utf-8').read()
def wr(p, s): open(p, 'w', encoding='utf-8').write(s)

report = []

# ---------------- A. timeline 追記 ----------------
TL_JA = '''
<article class="tl-item dot-openai" id="gpt-6-1-terra"><div class="tl-card"><div class="tl-date">2026-10-26 <span class="tl-provider-tag openai">OpenAI</span></div><h2 class="tl-title">GPT-6.1 Terra 公開 — 「速くて安い」コンピュータ操作モデル <span class="badge badge-new" style="font-size:.7rem;">New</span></h2><p class="tl-desc">GPT-5.6 Terraの上位後継（公式逐語は「A significant step up from GPT-5.6 Terra」）。標準APIは入力$1.00・キャッシュ入力$0.05・出力$5.00（1Mトークン）で、公式ブログは「GPT-5.6 TerraとGPT-6.1 Solの50%下」と明記。1,050,000コンテキスト・128,000出力、272,000トークン超はリクエスト全体が入力2倍/出力1.5倍。ChatGPT Work・Codex（Plus/Pro/Enterprise/Edu）とAPI（<code>gpt-6.1-terra</code>）で提供。<br><small>※公式ブログにリリース日の明記なし（「Starting today」）。第三者報道は2026-10-26で一致。</small><span class="tl-price-badge">$1.00/$5.00（キャッシュ$0.05）</span></p><div class="tl-links"><a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">公式発表 →</a><a href="/gpt-6-1-terra/">詳細ページ →</a><a href="/pricing/#oh">料金比較 →</a></div></div></article>
<article class="tl-item dot-other" id="kimi-k3-1-pro"><div class="tl-card"><div class="tl-date">2026-10-23 <span class="tl-provider-tag" style="background:rgba(203,213,225,.15);color:#cbd5e1;">Moonshot</span></div><h2 class="tl-title">Kimi K3.1 Pro シリーズ提供開始 — 3Tクラス・1Mコンテキスト <span class="badge badge-new" style="font-size:.7rem;">New</span></h2><p class="tl-desc">新しいK3.1シリーズの第1弾。Kimi Code公式の表現は「our most capable 3T-class model to date」で、1Mトークンコンテキストとコーディング・3D制作・財務リサーチ等の長時間エージェント能力を強化。同品質で約2〜3倍速の<strong>K3.1 Pro Highspeed</strong>も同時提供（Kimi Codeの提供条件は K3.1 Pro が Plus/Moderato 以上・Pro/Allegretto 以上で最大1Mコンテキスト、Highspeed は Pro/Allegretto 以上）。thinkingは low/high/max（既定high）のみ。<span class="tl-price-badge">API料金は公式ページに記載なく未確認</span></p><div class="tl-links"><a href="https://www.kimi.com/code/docs/en/kimi-code/whats-new.html" target="_blank" rel="noopener">公式What's New →</a><a href="/china-ai/#labs-h">中国AI総覧 →</a></div></div></article>
<article class="tl-item dot-other" id="qwen-4-training"><div class="tl-card"><div class="tl-date">2026-09-22 <span class="tl-provider-tag" style="background:rgba(203,213,225,.15);color:#cbd5e1;">Alibaba</span></div><h2 class="tl-title">Qwen 4（Alibaba）— 公式は「学習中」、時期・料金・ベンチマークは未公表</h2><p class="tl-desc">ApsaraカンファレンスでAlibabaが次世代モデル<strong>Qwen 4が「currently in training（学習中）」</strong>と公式に表明。会場では Qwen4 Max / Flash / Plus / 27B の4階層名が示された<strong>との報道</strong>がありますが、公式の文書には仕様・料金・ベンチマークの記載がありません。<strong>「10月末リリース予定」は公式に記載がなく、報道・コミュニティの推測</strong>です。当サイトは公式に数値が出るまで掲載しません。<span class="tl-price-badge">料金未確認</span></p><div class="tl-links"><a href="/china-ai/#labs-h">中国AI総覧 →</a><a href="/pricing/">料金比較 →</a></div></div></article>
'''

TL_EN = '''
<article class="tl-item dot-openai" id="gpt-6-1-terra"><div class="tl-card"><div class="tl-date">2026-10-26 <span class="tl-provider-tag openai">OpenAI</span></div><h2 class="tl-title">GPT-6.1 Terra launched — a fast, low-cost computer-use model <span class="badge badge-new" style="font-size:.7rem;">New</span></h2><p class="tl-desc">The step up from GPT-5.6 Terra ("A significant step up from GPT-5.6 Terra" in OpenAI's own words). Standard API pricing is $1.00 input / $0.05 cached input / $5.00 output per 1M tokens, which the launch post describes as 50% lower than GPT-5.6 Terra and GPT-6.1 Sol. 1,050,000-token context, 128,000 max output; above 272,000 input tokens the whole request is repriced at 2x input and 1.5x output. Available in ChatGPT Work and Codex (Plus/Pro/Enterprise/Edu) and via API as <code>gpt-6.1-terra</code>.<br><small>Note: the launch post gives no explicit date ("Starting today"); third-party coverage agrees on 2026-10-26.</small> <span class="tl-price-badge">$1.00/$5.00 (cached $0.05)</span></p><div class="tl-links"><a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">Official announcement →</a><a href="/en/gpt-6-1-terra/">Detail page →</a><a href="/en/pricing/#oh">Pricing →</a></div></div></article>
<article class="tl-item dot-other" id="kimi-k3-1-pro"><div class="tl-card"><div class="tl-date">2026-10-23 <span class="tl-provider-tag" style="background:rgba(203,213,225,.15);color:#cbd5e1;">Moonshot</span></div><h2 class="tl-title">Kimi K3.1 Pro series rolls out — 3T-class, 1M context <span class="badge badge-new" style="font-size:.7rem;">New</span></h2><p class="tl-desc">First model in the new K3.1 series. In Kimi's own words, "our most capable 3T-class model to date", with a 1M-token context and stronger coding, 3D creation, financial research and long-horizon agent work. <strong>K3.1 Pro Highspeed</strong> ships alongside it at roughly 2-3x the speed with the same quality (K3.1 Pro on Plus/Moderato and above; Pro/Allegretto and above unlock up to 1M context; Highspeed on Pro/Allegretto and above). Thinking mode only: low/high/max, default high. <span class="tl-price-badge">API pricing not stated on that page — unconfirmed</span></p><div class="tl-links"><a href="https://www.kimi.com/code/docs/en/kimi-code/whats-new.html" target="_blank" rel="noopener">Official What's New →</a><a href="/en/china-ai/#labs-h">China AI overview →</a></div></div></article>
<article class="tl-item dot-other" id="qwen-4-training"><div class="tl-card"><div class="tl-date">2026-09-22 <span class="tl-provider-tag" style="background:rgba(203,213,225,.15);color:#cbd5e1;">Alibaba</span></div><h2 class="tl-title">Qwen 4 (Alibaba) — officially "in training"; no date, price or benchmarks published</h2><p class="tl-desc">At its Apsara conference Alibaba confirmed that its next-generation model <strong>Qwen 4 is "currently in training"</strong>. The four-tier lineup (Qwen4 Max / Flash / Plus / 27B) was shown on stage according to <strong>press reports</strong>, but no official document lists specs, prices or benchmarks. <strong>The "end of October" release window is not in any official statement</strong> — it is press and community speculation. We publish no numbers until Alibaba does. <span class="tl-price-badge">Pricing unconfirmed</span></p><div class="tl-links"><a href="/en/china-ai/#labs-h">China AI overview →</a><a href="/en/pricing/">Pricing →</a></div></div></article>
'''

UB_JA = '<div class="updated-bar"><span class="dot">\u25cf</span>\u6700\u7d42\u66f4\u65b0: <time datetime="%s">2026\u5e7410\u670829\u65e5</time> | GPT-6.1 Terra\uff0810/26\u30fb$1.00/$5.00\uff09\u30fbKimi K3.1 Pro\uff0810/23\uff09\u30fbQwen 4\u306e\u516c\u5f0f\u767a\u8868\uff089/22\uff09\u3092\u8ffd\u8a18 | \u5404\u9805\u76ee\u306b\u4e00\u6b21\u60c5\u5831\u30ea\u30f3\u30af\u63b2\u8f09</div>' % TODAY
UB_EN = '<div class="updated-bar"><span class="dot">\u25cf</span>Last updated: <time datetime="%s">October 29, 2026</time> | Added GPT-6.1 Terra (10/26, $1.00/$5.00), Kimi K3.1 Pro (10/23) and the official Qwen 4 statement (9/22) | Primary-source links per entry</div>' % TODAY

def add_timeline(path, block, ub):
    s = rd(path)
    if 'gpt-6-1-terra' in s and 'kimi-k3-1-pro' in s:
        return s, 'already'
    i = s.rfind('</article>') + len('</article>')
    s = s[:i] + block + s[i:]
    s = re.sub(r'<div class="updated-bar">.*?</div>', ub, s, count=1, flags=re.S)
    s = re.sub(r'"dateModified":"\d{4}-\d{2}-\d{2}"', '"dateModified":"%s"' % TODAY, s)
    wr(path, s)
    return s, 'ok'

_, r = add_timeline(SITE + '/timeline/index.html', TL_JA, UB_JA); report.append(('timeline ja', r))
_, r = add_timeline(SITE + '/en/timeline/index.html', TL_EN, UB_EN); report.append(('timeline en', r))

# ---------------- B. china-ai 追記 ----------------
KIMI_JA = '<p><strong>K3.1 Pro\uff082026-10-23\u30fbKimi Code\uff09</strong>: \u65b0\u3057\u3044K3.1\u30b7\u30ea\u30fc\u30ba\u306e\u7b2c1\u5f3e\u3002\u516c\u5f0f\u306e\u8868\u73fe\u306f\u300cour most capable 3T-class model to date\u300d\u3067\u30011M\u30c8\u30fc\u30af\u30f3\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8\u3068\u30b3\u30fc\u30c7\u30a3\u30f3\u30b0\u30fb3D\u5236\u4f5c\u30fb\u8ca1\u52d9\u30ea\u30b5\u30fc\u30c1\u306a\u3069\u306e\u9577\u6642\u9593\u30a8\u30fc\u30b8\u30a7\u30f3\u30c8\u80fd\u529b\u3092\u5f37\u5316\u3002\u540c\u54c1\u8cea\u3067\u7d042\u301c3\u500d\u901f\u306e<strong>K3.1 Pro Highspeed</strong>\u3082\u540c\u6642\u63d0\u4f9b\u3002\u63d0\u4f9b\u6761\u4ef6\u306f K3.1 Pro \u304c Plus/Moderato \u4ee5\u4e0a\u3001Pro/Allegretto \u4ee5\u4e0a\u3067\u6700\u59271M\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8\u3001Highspeed \u306f Pro/Allegretto \u4ee5\u4e0a\u3002thinking\u306f low/high/max\uff08\u65e2\u5b9ahigh\uff09\u306e\u307f\u3067\u3001\u7121\u52b9\u5316\u3059\u308b\u3068400\u30a8\u30e9\u30fc\u3002<strong>API\u6599\u91d1\u306f\u540c\u30da\u30fc\u30b8\u306b\u8a18\u8f09\u304c\u306a\u304f\u672a\u78ba\u8a8d</strong>\uff08\u65e2\u5b58Kimi K3\u306eAPI\u6599\u91d1\u3068\u306f\u5225\u5efa\u3066\uff09\u3002<a href="https://www.kimi.com/code/docs/en/kimi-code/whats-new.html" target="_blank" rel="noopener">\u516c\u5f0fWhat\'s New</a>\uff082026-10-29\u78ba\u8a8d\uff09\u3002</p>'

QWEN_JA = '<p><strong>Qwen 4\uff08\u516c\u5f0f\u306f\u300c\u5b66\u7fd2\u4e2d\u300d\uff09</strong>: 2026-09-22\u306eApsara\u30ab\u30f3\u30d5\u30a1\u30ec\u30f3\u30b9\u3067\u3001Alibaba\u306f\u6b21\u4e16\u4ee3\u30e2\u30c7\u30eb<strong>Qwen 4\u304c\u300ccurrently in training\uff08\u5b66\u7fd2\u4e2d\uff09\u300d</strong>\u3068\u767a\u8868\u3002\u4f1a\u5834\u3067 Qwen4 Max / Flash / Plus / 27B \u306e4\u968e\u5c64\u540d\u304c\u793a\u3055\u308c\u305f<strong>\u3068\u306e\u5831\u9053</strong>\u304c\u3042\u308a\u307e\u3059\u304c\u3001\u516c\u5f0f\u6587\u66f8\u306b\u4ed5\u69d8\u30fb\u6599\u91d1\u30fb\u30d9\u30f3\u30c1\u30de\u30fc\u30af\u306e\u8a18\u8f09\u306f\u3042\u308a\u307e\u305b\u3093\u3002<strong>\u300c10\u6708\u672b\u30ea\u30ea\u30fc\u30b9\u4e88\u5b9a\u300d\u306f\u516c\u5f0f\u306b\u8a18\u8f09\u304c\u306a\u304f\u3001\u5831\u9053\u30fb\u30b3\u30df\u30e5\u30cb\u30c6\u30a3\u306e\u63a8\u6e2c</strong>\u3067\u3059\u3002\u516c\u5f0f\u306b\u6570\u5024\u304c\u51fa\u308b\u307e\u3067\u5f53\u30b5\u30a4\u30c8\u306f\u8a72\u5f53\u9805\u76ee\u3092\u63b2\u8f09\u3057\u307e\u305b\u3093\u3002</p>'

KIMI_EN = '<p><strong>K3.1 Pro (2026-10-23, Kimi Code)</strong>: first model in the new K3.1 series, described by Kimi as "our most capable 3T-class model to date", with a 1M-token context window and stronger coding, 3D creation, financial research and long-horizon agent capabilities. <strong>K3.1 Pro Highspeed</strong> ships alongside it at roughly 2-3x the speed with the same quality (K3.1 Pro on Plus/Moderato and above; Pro/Allegretto and above unlock up to 1M context; Highspeed on Pro/Allegretto and above). Thinking mode only: low/high/max, default high; disabling it returns a 400 error. <strong>API pricing is not stated on that page — unconfirmed</strong> (separate from Kimi K3 API pricing). <a href="https://www.kimi.com/code/docs/en/kimi-code/whats-new.html" target="_blank" rel="noopener">Official What\'s New</a> (checked 2026-10-29).</p>'

QWEN_EN = '<p><strong>Qwen 4 (officially "in training")</strong>: at the Apsara conference on 2026-09-22, Alibaba said its next-generation model <strong>Qwen 4 is "currently in training"</strong>. The four-tier lineup (Qwen4 Max / Flash / Plus / 27B) was shown on stage according to <strong>press reports</strong>, but no official document lists specs, pricing or benchmarks. <strong>The "end of October" release window is not in any official statement</strong> — it is press and community speculation. We list no numbers until Alibaba publishes them.</p>'

def add_to_card(html, tag, text):
    pat = r'(<div class="lab-card"><span class="lab-tag">%s</span>.*?)(</p>\s*</div>)' % re.escape(tag)
    m = re.search(pat, html, re.S)
    if not m:
        return html, False
    return html[:m.end(1)] + text + html[m.end(1):], True

# JA
p = SITE + '/china-ai/index.html'
s = rd(p)
before_month = s.count('2026\u5e749\u6708\u7248')
s = s.replace('2026\u5e749\u6708\u7248', '2026\u5e7410\u6708\u7248')
s, ok1 = add_to_card(s, 'Kimi / Moonshot', KIMI_JA)
s, ok2 = add_to_card(s, 'Qwen / Alibaba', QWEN_JA)
s = re.sub(r'<div class="updated-bar">.*?</div>', UB_JA, s, count=1, flags=re.S)
s = re.sub(r'"dateModified":"\d{4}-\d{2}-\d{2}"', '"dateModified":"%s"' % TODAY, s)
NEWLI_JA = '<li><span class="cl-date">%s</span><span class="cl-text">GPT-6.1 Terra\uff0810/26\u3001\u5165\u529b$1.00\u30fb\u30ad\u30e3\u30c3\u30b7\u30e5$0.05\u30fb\u51fa\u529b$5.00\u30011.05M\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8\uff09\u3092\u65b0\u898f\u30da\u30fc\u30b8\u3068\u5e74\u8868\u306b\u53cd\u6620\u3002Kimi K3.1 Pro\uff0810/23\u30fb3T\u30af\u30e9\u30b9\u30fb1M\u30b3\u30f3\u30c6\u30ad\u30b9\u30c8\uff09\u3092Kimi\u67a0\u306b\u8ffd\u8a18\u3002Qwen 4\u306f\u516c\u5f0f\u306e\u300c\u5b66\u7fd2\u4e2d\u300d\u767a\u8868\uff089/22\uff09\u306e\u307f\u3092\u63b2\u8f09\u3057\u3001\u300c10\u6708\u672b\u4e88\u5b9a\u300d\u306f\u5831\u9053\u30fb\u63a8\u6e2c\u3068\u3057\u3066\u660e\u8a18\u3002</span></li>' % TODAY
s = re.sub(r'(<li><span class="cl-date">2026-10-13</span>)', NEWLI_JA + r'\1', s, count=1)
wr(p, s)
report.append(('china-ai ja', 'month_label=%d kimi=%s qwen=%s' % (before_month, ok1, ok2)))

# EN
p = SITE + '/en/china-ai/index.html'
s = rd(p)
s, ok1 = add_to_card(s, 'Kimi / Moonshot', KIMI_EN)
s, ok2 = add_to_card(s, 'Qwen / Alibaba', QWEN_EN)
s = re.sub(r'<div class="updated-bar">.*?</div>', UB_EN, s, count=1, flags=re.S)
s = re.sub(r'"dateModified":"\d{4}-\d{2}-\d{2}"', '"dateModified":"%s"' % TODAY, s)
NEWLI_EN = '<li><span class="cl-date">%s</span><span class="cl-text">Added GPT-6.1 Terra (10/26, $1.00/$0.05/$5.00, 1.05M context) to the new detail page and the timeline. Added Kimi K3.1 Pro (10/23, 3T-class, 1M context) to the Kimi card. Qwen 4 is listed only as Alibaba\'s official "in training" statement (9/22); the "end of October" claim is labelled press speculation.</span></li>' % TODAY
s = re.sub(r'(<li><span class="cl-date">2026-10-13</span>)', NEWLI_EN + r'\1', s, count=1)
wr(p, s)
report.append(('china-ai en', 'kimi=%s qwen=%s' % (ok1, ok2)))

# ---------------- C. 課題70 ----------------
p = SITE + '/en/glossary/one-million-context/index.html'
s = rd(p)
t = re.search(r'<title>(.*?)</title>', s, re.S).group(1)
core = re.sub(r'\s*[|\u2014]\s*LLM Data Hub\s*$', '', t).strip()
old_og = re.search(r'<meta property="og:title" content="([^"]*)">', s).group(1)
s = re.sub(r'<meta property="og:title" content="[^"]*">',
           '<meta property="og:title" content="%s">' % core, s, count=1)
wr(p, s)
report.append(('task70', 'og:title: %r -> %r' % (old_og, core)))

# ---------------- D. CTR: title/description (本文は不変) ----------------
def set_meta(path, new_title, new_desc, sep=' | '):
    s = rd(path)
    old_title = re.search(r'<title>(.*?)</title>', s, re.S).group(1)
    old_desc = re.search(r'<meta name="description" content="([^"]*)"', s).group(1)
    old_og = re.search(r'<meta property="og:title" content="([^"]*)">', s).group(1)
    s = re.sub(r'<title>.*?</title>', '<title>%s%sLLM Data Hub</title>' % (new_title, sep), s, flags=re.S)
    s = re.sub(r'<meta name="description" content="[^"]*"',
               '<meta name="description" content="%s"' % new_desc.replace('"', '&quot;'), s, count=1)
    s = re.sub(r'<meta property="og:title" content="[^"]*">',
               '<meta property="og:title" content="%s">' % new_title, s, count=1)
    s = re.sub(r'<meta property="og:description" content="[^"]*">',
               '<meta property="og:description" content="%s">' % new_desc.replace('"', '&quot;'), s, count=1)
    wr(path, s)
    return old_title, old_desc, old_og, new_title, new_desc

T1 = "LLM API Pricing [Oct 2026]: Input, Cache & Output Rates, 8 Vendors"
D1 = ("Side-by-side USD per 1M-token rates for OpenAI (GPT-6.1 Terra and Sol), Claude Opus 5.5, Gemini 4 Argon, "
      "DeepSeek, Grok, GLM, Qwen and Meta: input, cached input, cache writes and output, plus long-context and "
      "Batch multipliers. Each row links to the vendor's official pricing page.")
r1 = set_meta(SITE + '/en/pricing/index.html', T1, D1)
report.append(('CTR /en/pricing/', 'title: %r -> %r | desc: %r -> %r | og_before=%r' % (r1[0], r1[3], r1[1], r1[4], r1[2])))

T2 = "Zero Data Retention (ZDR): What It Covers, What It Doesn't (2026)"
D2 = ("ZDR means a provider does not store your prompts or outputs after the response — but retention is still "
      "required for some models. How ZDR differs from ZOA and from \"not used for training\", which providers grant "
      "it by default vs. by gate, and the exception lists, quoted from official docs.")
r2 = set_meta(SITE + '/en/glossary/zero-data-retention/index.html', T2, D2)
report.append(('CTR /en/glossary/zero-data-retention/', 'title: %r -> %r | desc: %r -> %r | og_before=%r' % (r2[0], r2[3], r2[1], r2[4], r2[2])))

# ---------------- E. sitemap lastmod ----------------
sp = SITE + '/sitemap.xml'
sm = rd(sp)
for loc in ['/timeline/', '/en/timeline/', '/china-ai/', '/en/china-ai/']:
    sm = re.sub(r'(<loc>%s</loc>\s*<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)' % re.escape(BASE + loc),
                r'\g<1>%s\2' % TODAY, sm)
wr(sp, sm)
report.append(('sitemap', 'lastmod updated for timeline/china-ai (ja+en); total urls=%d' % sm.count('<url>')))

for k, v in report:
    print(k, '::', v)

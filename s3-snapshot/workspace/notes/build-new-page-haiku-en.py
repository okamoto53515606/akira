# -*- coding: utf-8 -*-
"""2026-10-09: en/claude-haiku-5-5, gpt-6-1-sol(ja/en) を作成。"""
import pathlib
S = pathlib.Path('/tmp/site')

def block(t, start, end):
    i = t.index(start); j = t.index(end, i) + len(end); return t[i:j]

ja_t = (S / 'claude-sonnet-5-5/index.html').read_text(encoding='utf-8')
en_t = (S / 'en/claude-sonnet-5-5/index.html').read_text(encoding='utf-8')
H_JA = block(ja_t, '<header class="site-header">', '</header>')
H_EN = block(en_t, '<header class="site-header">', '</header>')
F_JA = block(ja_t, '<footer class="site-footer">', '</footer>')
F_EN = block(en_t, '<footer class="site-footer">', '</footer>')
STYLE = block(ja_t, '<style>', '</style>')
GA = ('  <script async src="https://www.googletagmanager.com/gtag/js?id=G-MTH8T0ECG2"></script>\n'
      "  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-MTH8T0ECG2');</script>")

def head(lang, title, desc, path, ja_path, en_path, ogtitle, ogdesc, headline, pubdate, moddate, jdesc, crumb):
    base = 'https://llm.okamomedia.tokyo'
    author = 'okamoちゃんねる' if lang == 'ja' else 'okamo channel'
    home = '/en/' if lang == 'en' else '/'
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="{base}{path}">
  <link rel="alternate" hreflang="ja" href="{base}{ja_path}">
  <link rel="alternate" hreflang="en" href="{base}{en_path}">
  <link rel="alternate" hreflang="x-default" href="{base}{ja_path}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{base}{path}">
  <meta property="og:title" content="{ogtitle}">
  <meta property="og:description" content="{ogdesc}">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary">
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article","headline":"{headline}","datePublished":"{pubdate}","dateModified":"{moddate}","author":{{"@type":"Organization","name":"{author}"}},"publisher":{{"@type":"Organization","name":"{author}"}},"url":"{base}{path}","inLanguage":"{lang}","description":"{jdesc}"}}</script>
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"{'ホーム' if lang=='ja' else 'Home'}","item":"{base}{home}"}},{{"@type":"ListItem","position":2,"name":"{crumb}","item":"{base}{path}"}}]}}</script>
{GA}
  <link rel="stylesheet" href="/assets/style.css">
{STYLE}
</head>
'''

# ============================================================ en/claude-haiku-5-5
haiku_en = head(
    'en',
    'Claude Haiku 5.5 — Fastest and Cheapest of the Claude 5.5 Family [$0.10/$0.50, Two-Tier Pricing Above 100k] — LLM Data Hub',
    'Anthropic Claude Haiku 5.5 pricing ($0.10 input / $0.50 output up to 100,000 tokens; $0.50 / $2.50 above it), $0.01 cache reads, 1M context, 128K output and adaptive thinking at a default effort of medium — quoted from Anthropic\'s docs. Includes the Haiku 4.5 comparison, the new tokenizer warning (about 30% more tokens for the same text) and the model ID on all five platforms. Released October 7, 2026. Updated October 9, 2026.',
    '/en/claude-haiku-5-5/', '/claude-haiku-5-5/', '/en/claude-haiku-5-5/',
    'Claude Haiku 5.5 — Fastest and Cheapest of the Claude 5.5 Family [$0.10/$0.50]',
    '$0.10 input / $0.50 output up to 100k tokens, $0.50 / $2.50 above. $0.01 cache reads, 1M context, thinking on by default, and the new-tokenizer caveat — all from primary sources (updated October 9, 2026).',
    'Claude Haiku 5.5 — Fastest and Cheapest of the Claude 5.5 Family [$0.10/$0.50, Two-Tier Pricing Above 100k]',
    '2026-10-09', '2026-10-09',
    'Claude Haiku 5.5 pricing, context window, output limits, thinking behaviour and model IDs, quoted from Anthropic official documentation.',
    'Claude Haiku 5.5') + f'''<body>
{H_EN}

<section class="hero-sonnet">
  <div class="container">
    <p class="price-flag">🚀 Released October 7, 2026 — the fastest and cheapest model of the Claude 5.5 family, far below Haiku 4.5 ($1/$5)</p>
    <h1>Claude <span>Haiku 5.5</span></h1>
    <p class="lead">The fastest and cheapest model in Anthropic's Claude 5.5 family. The official docs describe it as built for <strong>“high-volume, latency-sensitive work such as classification, routing, extraction, and subagent tasks.”</strong> Pricing is <strong>$0.10 input / $0.50 output</strong> for prompts up to 100,000 tokens — and <strong>$0.50 / $2.50 once a prompt goes above 100,000 tokens</strong>.</p>
    <div class="quick-stats">
      <div class="stat"><div class="val">$0.10</div><div class="lbl">Input / 1M (≤100k)</div></div>
      <div class="stat"><div class="val">$0.50</div><div class="lbl">Output / 1M (≤100k)</div></div>
      <div class="stat"><div class="val">1M</div><div class="lbl">Context</div></div>
      <div class="stat"><div class="val">Fastest</div><div class="lbl">Latency (official table)</div></div>
    </div>
  </div>
</section>

<main><div class="container">
<div class="updated-bar" style="margin-top:2rem;"><span class="dot">●</span>Last updated: <time datetime="2026-10-09">October 9, 2026</time> | Sources: <a href="https://platform.claude.com/docs/en/models/haiku-5-5/overview" target="_blank" rel="noopener">Claude Platform Docs — Haiku 5.5 overview</a> · <a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank" rel="noopener">official pricing docs</a> | <a href="/en/pricing/">Pricing comparison</a> · <a href="/en/calculator/">Calculator</a> · <a href="/en/claude-sonnet-5-5/">Sonnet 5.5</a> · <a href="/en/claude-opus-5-5/">Opus 5.5</a></div>

<section class="section" style="padding-top:2rem;" aria-labelledby="tl-h">
<h2 class="section-title" id="tl-h" style="font-size:1.2rem;">The short version</h2>
<div class="context-note" style="border-left-color:var(--c-green);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>One tenth of Haiku 4.5 on input and output.</strong> $0.10 / $0.50 up to 100,000 tokens, against $1.00 / $5.00 on Haiku 4.5.</li>
    <li><strong>Above 100,000 tokens the rates jump 5x</strong> to $0.50 input / $2.50 output, so the official table reads “From $0.10 / $0.50”. The 1M window is real, but the price of filling it is not the headline rate.</li>
    <li><strong>Cache reads are 10% of input:</strong> $0.01 (and $0.05 above 100k). Cache writes are $0.125 for the 5-minute TTL and $0.20 for one hour.</li>
    <li><strong>Thinking is adaptive and on by default, with a default effort of <code>medium</code></strong> — more conservative than Sonnet 5.5's <code>high</code>.</li>
    <li><strong>The tokenizer changed.</strong> Verbatim: it “uses the same newer tokenizer as Claude 4.7 and later models, so the same text counts as approximately 30% more tokens than on Claude Haiku 4.5.” Compare cost with token counts in hand.</li>
    <li><strong><code>temperature</code>, <code>top_p</code> and <code>top_k</code> can no longer be set</strong> to non-default values — they return a 400 error.</li>
  </ul>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="price-h">
<h2 class="section-title" id="price-h" style="font-size:1.2rem;">Pricing (USD per 1M tokens, from the official docs)</h2>
<p class="section-sub">Values as published on the Haiku 5.5 overview page and the official pricing documentation; the Haiku 4.5 column matches our <a href="/en/pricing/">pricing comparison</a>.</p>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>Haiku 5.5 (≤100k tokens)</th><th>Haiku 5.5 (over 100k)</th><th>Haiku 4.5 (previous gen)</th></tr></thead><tbody>
<tr><td class="model-name">Input</td><td class="price">$0.10</td><td class="price">$0.50</td><td>$1.00</td></tr>
<tr><td class="model-name">Output</td><td class="price">$0.50</td><td class="price">$2.50</td><td>$5.00</td></tr>
<tr><td class="model-name">Cache write (5-minute TTL)</td><td class="price">$0.125</td><td class="price">$0.625</td><td>$1.25</td></tr>
<tr><td class="model-name">Cache write (1-hour TTL)</td><td class="price">$0.20</td><td class="price">$1.00</td><td>$2.00</td></tr>
<tr><td class="model-name">Cache read (cache hit)</td><td class="price">$0.01</td><td class="price">$0.05</td><td>$0.10</td></tr>
<tr><td class="model-name">Batch API</td><td colspan="2">50% off input and output</td><td>50% off</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">※ Haiku 5.5 figures are as published. The Haiku 4.5 cache figures are calculated by us from the official multipliers (1.25x for 5-minute writes, 2x for one hour, 0.1x for reads), verified 2026-10-09.</p>
<p class="source-note">Source: <a href="https://platform.claude.com/docs/en/models/haiku-5-5/overview" target="_blank" rel="noopener">Claude Haiku 5.5 — overview (Pricing / Availability)</a>, checked 2026-10-09.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="tier-h">
<h2 class="section-title" id="tier-h" style="font-size:1.2rem;">Where the two-tier pricing actually bites</h2>
<p class="section-sub">The rate switches the moment a single prompt crosses 100,000 tokens. Worked examples:</p>
<div class="table-wrap"><table><thead><tr><th>Case</th><th>Haiku 5.5</th><th>Claude Sonnet 5.5</th></tr></thead><tbody>
<tr><td class="model-name">200,000 input + 10,000 output tokens</td><td class="price">$0.125<br><small>($0.50/M × 0.2 + $2.50/M × 0.01)</small></td><td class="price">$0.50<br><small>($2/M × 0.2 + $10/M × 0.01)</small></td></tr>
<tr><td class="model-name">50,000 input + 5,000 output tokens</td><td class="price">$0.0075<br><small>($0.10/M × 0.05 + $0.50/M × 0.005)</small></td><td class="price">$0.15<br><small>($2/M × 0.05 + $10/M × 0.005)</small></td></tr>
</tbody></table></div>
<ul style="font-size:.86rem;color:var(--c-muted);padding-left:1.3em;line-height:1.9;">
  <li><strong>Up to 100k the rate is 1/20 of Sonnet 5.5.</strong> For high-volume classification, routing and extraction, that is an order-of-magnitude difference.</li>
  <li><strong>Above 100k it is still about a quarter of Sonnet 5.5.</strong> The honest framing is not “expensive above 100k” but “unusually cheap below it”.</li>
  <li><strong>Reused long prefixes belong in the cache:</strong> $0.01/M read (against $0.10/M on Sonnet 5.5) — the pattern that fits RAG and agent system prompts.</li>
</ul>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="mig-h">
<h2 class="section-title" id="mig-h" style="font-size:1.2rem;">Four things to watch when migrating from Haiku 4.5</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">1. About 30% more tokens</div><div class="spec-value">The same text counts as roughly 30% more tokens on the new tokenizer. A 10x lower unit price works out to about <strong>7.7x cheaper in practice</strong> (1 ÷ (0.1 × 1.3)) — not 10x.</div></div>
  <div class="spec-item"><div class="spec-label">2. Thinking is on by default</div><div class="spec-value">Adaptive thinking, default effort <code>medium</code>. Budget for extra output tokens, and steer depth with <code>effort</code>.</div></div>
  <div class="spec-item"><div class="spec-label">3. No temperature parameters</div><div class="spec-value">Verbatim: <em>“Omit temperature, top_p, and top_k, since a non-default value for any of them returns a 400 error.”</em></div></div>
  <div class="spec-item"><div class="spec-label">4. Thinking blocks are account-bound</div><div class="spec-value">Verbatim: <em>“Its thinking blocks work only in the account that produced them, or in an account linked to it.”</em> Multi-account setups cannot carry them across.</div></div>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="spec-h">
<h2 class="section-title" id="spec-h" style="font-size:1.2rem;">Specifications and model IDs</h2>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>Value (official page)</th></tr></thead><tbody>
<tr><td class="model-name">Context window</td><td>1M tokens</td></tr>
<tr><td class="model-name">Max output</td><td>128K tokens (300K on the Batch API with the <code>output-300k-2026-03-24</code> beta header)</td></tr>
<tr><td class="model-name">Thinking</td><td>Adaptive (on by default); default effort <code>medium</code></td></tr>
<tr><td class="model-name">Latency</td><td>Fastest (official comparison table)</td></tr>
<tr><td class="model-name">Modalities</td><td>text, images → text</td></tr>
<tr><td class="model-name">Knowledge cutoff</td><td>Jun 2026 (training data cutoff Jun 2026)</td></tr>
<tr><td class="model-name">Status</td><td>Active (latest). <strong>Retirement not sooner than October 7, 2027.</strong></td></tr>
</tbody></table></div>
<div class="table-wrap" style="margin-top:1rem;"><table><thead><tr><th>Platform</th><th>Model ID</th></tr></thead><tbody>
<tr><td class="model-name">Claude API</td><td><code>claude-haiku-5-5</code></td></tr>
<tr><td class="model-name">Amazon Bedrock</td><td><code>anthropic.claude-haiku-5-5</code></td></tr>
<tr><td class="model-name">Google Cloud (Vertex AI)</td><td><code>claude-haiku-5-5</code></td></tr>
<tr><td class="model-name">Microsoft Foundry</td><td><code>claude-haiku-5-5</code></td></tr>
<tr><td class="model-name">Claude Platform on AWS</td><td><code>claude-haiku-5-5</code></td></tr>
</tbody></table></div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="q-h">
<h2 class="section-title" id="q-h" style="font-size:1.2rem;">What the docs say, verbatim</h2>
<div class="quote">
  <em>“Claude Haiku 5.5 is built for high-volume, latency-sensitive work such as classification, routing, extraction, and subagent tasks. It supports adaptive thinking with the effort parameter, a 1M token context window, and up to 128k output tokens. It uses the same newer tokenizer as Claude 4.7 and later models, so the same text counts as approximately 30% more tokens than on Claude Haiku 4.5.”</em>
  <span class="who">— Claude Platform Docs, “Claude Haiku 5.5 — overview” (checked 2026-10-09)</span>
</div>
<p class="source-note">Pricing, specifications and model IDs above are as published. We do not fill gaps with estimates: where the vendor publishes no benchmark table, we say so.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="use-h">
<h2 class="section-title" id="use-h" style="font-size:1.2rem;">Good fit, poor fit</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">Good: bulk classification, extraction, routing</div><div class="spec-value">Many short calls. Up to 100k tokens the input rate is $0.10/M against $2/M on Sonnet 5.5.</div></div>
  <div class="spec-item"><div class="spec-label">Good: subagents and preprocessing</div><div class="spec-value">The docs name subagent tasks explicitly — a natural front stage for a stronger model.</div></div>
  <div class="spec-item"><div class="spec-label">Good: latency-sensitive chat</div><div class="spec-value">Fastest latency in the official comparison table.</div></div>
  <div class="spec-item"><div class="spec-label">Poor: audit or contract decisions</div><div class="spec-value">Retention, operator access and training terms are not on the model page. Start from <a href="/en/glossary/zero-operator-access/">ZOA</a>, <a href="/en/glossary/zero-data-retention/">ZDR</a> and <a href="/en/glossary/four-data-requirements/">the four requirements</a>.</div></div>
  <div class="spec-item"><div class="spec-label">Poor: pipelines that set temperature</div><div class="spec-value">Non-default <code>temperature</code>, <code>top_p</code> or <code>top_k</code> returns a 400 error.</div></div>
  <div class="spec-item"><div class="spec-label">Reconsider: 100k+ single-shot prompts</div><div class="spec-value">Rates become $0.50 / $2.50. For whole-document work, compare the total against Sonnet 5.5.</div></div>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="rel-h">
<h2 class="section-title" id="rel-h" style="font-size:1.2rem;">Related pages</h2>
<ul style="font-size:.88rem;line-height:2;">
  <li><a href="/en/claude-sonnet-5-5/">Claude Sonnet 5.5</a> — the balanced model of the same family ($2/$10, 1M context)</li>
  <li><a href="/en/claude-opus-5-5/">Claude Opus 5.5</a> — the tier above ($4/$20)</li>
  <li><a href="/en/pricing/">LLM API pricing comparison</a> — every vendor on one page</li>
  <li><a href="/en/calculator/">Token cost calculator</a> — turn token counts into dollars</li>
  <li><a href="/en/timeline/">Release timeline</a> — where Haiku 5.5 sits</li>
  <li><a href="/en/glossary/prompt-cache/">Prompt caching explained</a> — when $0.01/M cache reads pay off</li>
</ul>
</section>

<div class="tip-box" style="border-left-color:var(--c-yellow);">
  <h3 style="font-size:1rem;margin:0 0 .5rem;">⚠️ Disclaimer</h3>
  <ul style="font-size:.84rem;color:var(--c-muted);line-height:1.9;">
    <li>Prices and specifications were checked on 2026-10-09 against Claude Platform Docs (Haiku 5.5 overview and the official pricing documentation). Vendors change them without notice.</li>
    <li>Haiku 4.5 cache figures are our own calculation from the official multipliers.</li>
    <li>This site is informational and does not endorse or represent any provider.</li>
  </ul>
</div>
</div></main>
{F_EN}
</body>
</html>
'''
(S / 'en/claude-haiku-5-5').mkdir(parents=True, exist_ok=True)
(S / 'en/claude-haiku-5-5/index.html').write_text(haiku_en, encoding='utf-8')
print("wrote en/claude-haiku-5-5", len(haiku_en))

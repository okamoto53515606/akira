# -*- coding: utf-8 -*-
"""2026-10-09: en/gpt-6-1-sol を作成。"""
import pathlib
S = pathlib.Path('/tmp/site')

def block(t, start, end):
    i = t.index(start); j = t.index(end, i) + len(end); return t[i:j]

en_t = (S / 'en/claude-sonnet-5-5/index.html').read_text(encoding='utf-8')
H_EN = block(en_t, '<header class="site-header">', '</header>')
F_EN = block(en_t, '<footer class="site-footer">', '</footer>')
STYLE = block(en_t, '<style>', '</style>')
GA = ('  <script async src="https://www.googletagmanager.com/gtag/js?id=G-MTH8T0ECG2"></script>\n'
      "  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-MTH8T0ECG2');</script>")

base = 'https://llm.okamomedia.tokyo'
title = 'GPT-6.1 Sol — The Balanced Model of the GPT-6 Family [$2/$10, $0.10 Cached Input, 2x Above 272K] — LLM Data Hub'
desc = ("OpenAI GPT-6.1 Sol (gpt-6.1-sol) pricing from the official model page: $2 input, $0.10 cached input (5% of input), "
        "$2.50 cache writes and $10 output per 1M tokens. Fast mode is 2x, Ultrafast 6x, Batch/Flex 50% off, and prompts above "
        "272,000 input tokens are repriced at 2x input and 1.5x output for the whole request. 1.05M context, 128K max output, "
        "922K max input, reasoning effort low through max (no none/minimal), tool calling via the Responses API. "
        "Includes the GPT-6 Sol comparison and the official migration notes. Updated October 9, 2026.")
sol_en = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="{base}/en/gpt-6-1-sol/">
  <link rel="alternate" hreflang="ja" href="{base}/gpt-6-1-sol/">
  <link rel="alternate" hreflang="en" href="{base}/en/gpt-6-1-sol/">
  <link rel="alternate" hreflang="x-default" href="{base}/gpt-6-1-sol/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{base}/en/gpt-6-1-sol/">
  <meta property="og:title" content="GPT-6.1 Sol — The Balanced Model of the GPT-6 Family [$2/$10]">
  <meta property="og:description" content="$2 input, $0.10 cached input, $2.50 cache writes, $10 output. Fast 2x / Ultrafast 6x / Batch 50% off, and 2x input above 272K tokens. 1.05M context, 128K output, reasoning effort low to max (no none). From primary sources.">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary">
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article","headline":"GPT-6.1 Sol — The Balanced Model of the GPT-6 Family [$2/$10, $0.10 Cached Input, 2x Above 272K]","datePublished":"2026-10-09","dateModified":"2026-10-09","author":{{"@type":"Organization","name":"okamo channel"}},"publisher":{{"@type":"Organization","name":"okamo channel"}},"url":"{base}/en/gpt-6-1-sol/","inLanguage":"en","description":"GPT-6.1 Sol pricing, context window, reasoning efforts and endpoints, quoted from OpenAI official documentation."}}</script>
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Home","item":"{base}/en/"}},{{"@type":"ListItem","position":2,"name":"GPT-6.1 Sol","item":"{base}/en/gpt-6-1-sol/"}}]}}</script>
{GA}
  <link rel="stylesheet" href="/assets/style.css">
{STYLE}
</head>
<body>
{H_EN}

<section class="hero-sonnet">
  <div class="container">
    <p class="price-flag">⚡ The balanced model of the GPT-6 family — officially “Near-Astra performance for complex work at a lower cost”</p>
    <h1>GPT-6.1 <span>Sol</span></h1>
    <p class="lead">OpenAI's balance point between intelligence and cost in the GPT-6 family. The model ID is <code>gpt-6.1-sol</code>, and the official model page describes it as <strong>“Near-Astra performance for complex work at a lower cost.”</strong> Pricing is <strong>$2 input / $10 output</strong>, with <strong>cached input at 5% of input — $0.10</strong>.</p>
    <div class="quick-stats">
      <div class="stat"><div class="val">$2.00</div><div class="lbl">Input / 1M</div></div>
      <div class="stat"><div class="val">$0.10</div><div class="lbl">Cached input / 1M</div></div>
      <div class="stat"><div class="val">$10.00</div><div class="lbl">Output / 1M</div></div>
      <div class="stat"><div class="val">1.05M</div><div class="lbl">Context</div></div>
    </div>
  </div>
</section>

<main><div class="container">
<div class="updated-bar" style="margin-top:2rem;"><span class="dot">●</span>Last updated: <time datetime="2026-10-09">October 9, 2026</time> | Sources: <a href="https://developers.openai.com/api/docs/models/gpt-6.1-sol" target="_blank" rel="noopener">OpenAI — GPT-6.1 Sol model page</a> · <a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noopener">official pricing page</a> | <a href="/en/pricing/">Pricing comparison</a> · <a href="/en/calculator/">Calculator</a> · <a href="/en/gpt-6-sol-luna/">GPT-6 Sol / Luna</a></div>

<section class="section" style="padding-top:2rem;" aria-labelledby="tl-h">
<h2 class="section-title" id="tl-h" style="font-size:1.2rem;">The short version</h2>
<div class="context-note" style="border-left-color:var(--c-blue);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>Input $2 and output $10 match GPT-6 Sol</strong>, but <strong>cached input drops to $0.10 (5% of input)</strong> from $0.20 (90% off) on GPT-6 Sol.</li>
    <li><strong>Reasoning effort: low / medium (default) / high / xhigh / max.</strong> <code>none</code> and <code>minimal</code> are not supported — GPT-6 Sol and Luna do support <code>none</code>.</li>
    <li><strong>Tool calling requires the Responses API.</strong> Chat Completions works only without tools.</li>
    <li><strong>Speed tiers change the price:</strong> Fast is 2x Standard, Ultrafast 6x, Batch and Flex 50% off. Regional processing adds 10%.</li>
    <li><strong>Prompts above 272,000 input tokens are repriced across the whole request</strong> (2x input and cache rates, 1.5x output) — a real constraint on one-shot long-document work.</li>
    <li><strong>OpenAI's model page publishes no release date.</strong> Third-party reports agree on September 29, 2026; we flag that as third-party information rather than stating it as official.</li>
  </ul>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="price-h">
<h2 class="section-title" id="price-h" style="font-size:1.2rem;">Pricing (USD per 1M tokens, from the official model page)</h2>
<p class="section-sub">Standard prices are as published. Fast, Batch/Flex and Ultrafast figures are our calculations from the official multipliers (2x, 50% off, 6x).</p>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>Standard</th><th>Fast (2x)</th><th>Batch / Flex (50% off)</th><th>Ultrafast (6x)</th></tr></thead><tbody>
<tr><td class="model-name">Input</td><td class="price">$2.00</td><td>$4.00</td><td>$1.00</td><td>$12.00</td></tr>
<tr><td class="model-name">Cached input</td><td class="price">$0.10</td><td>$0.20</td><td>$0.05</td><td>$0.60</td></tr>
<tr><td class="model-name">Cache writes (1.25x)</td><td class="price">$2.50</td><td>$5.00</td><td>$1.25</td><td>$15.00</td></tr>
<tr><td class="model-name">Output</td><td class="price">$10.00</td><td>$20.00</td><td>$5.00</td><td>$60.00</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">※ Official notes: cached input is “priced at 5% of the uncached input token rate”; cache writes are “billed at 1.25x the uncached input token rate”; Fast mode is 2x Standard, Batch and Flex 50% lower, Ultrafast 6x, regional processing +10%.</p>
<p class="source-note">Source: <a href="https://developers.openai.com/api/docs/models/gpt-6.1-sol" target="_blank" rel="noopener">OpenAI — GPT-6.1 Sol (Pricing)</a>, checked 2026-10-09.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="long-h">
<h2 class="section-title" id="long-h" style="font-size:1.2rem;">The 272K wall: one-shot long prompts are repriced</h2>
<p class="section-sub">The official note reads: prompts with more than 272,000 input tokens “are priced at 2x input and cache rates and 1.5x output <strong>for the full request</strong>.” Not just the overflow.</p>
<div class="table-wrap"><table><thead><tr><th>Case</th><th>Calculation</th><th>Cost</th></tr></thead><tbody>
<tr><td class="model-name">300,000 input + 5,000 output tokens in a single request</td><td>$4/M × 0.3 input + $15/M × 0.005 output<br><small>2x input and 1.5x output because the request exceeds 272K</small></td><td class="price">$1.275</td></tr>
<tr><td class="model-name">The same work split into three 100,000-token requests</td><td>$2/M × 0.3 input + output per call</td><td class="price">$0.60 + output</td></tr>
</tbody></table></div>
<ul style="font-size:.86rem;color:var(--c-muted);padding-left:1.3em;line-height:1.9;">
  <li><strong>“1.05M context” is not the same as “send 1.05M in one go.”</strong> Past 272K the whole request is repriced, which makes long-document work a design decision.</li>
  <li><strong>For long conversations, $0.10 cached input matters</strong> — until the request crosses 272K, where cached rates double too ($0.20/M).</li>
  <li>All figures are our calculations from the official multipliers; confirm against your own usage reports.</li>
</ul>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="cmp-h">
<h2 class="section-title" id="cmp-h" style="font-size:1.2rem;">How it differs from GPT-6 Sol</h2>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>GPT-6.1 Sol</th><th>GPT-6 Sol (previous gen)</th></tr></thead><tbody>
<tr><td class="model-name">Input</td><td class="price">$2.00</td><td>$2.00</td></tr>
<tr><td class="model-name">Cached input</td><td class="price">$0.10 (5% of input)</td><td>$0.20 (90% off)</td></tr>
<tr><td class="model-name">Cache writes</td><td class="price">$2.50 (1.25x input)</td><td>Not stated on the model page</td></tr>
<tr><td class="model-name">Output</td><td class="price">$10.00</td><td>$10.00</td></tr>
<tr><td class="model-name">Reasoning effort</td><td>low / medium (default) / high / xhigh / max — <strong>no none or minimal</strong></td><td>Includes <code>none</code> (which allows function calling on Chat Completions)</td></tr>
<tr><td class="model-name">Context / max output</td><td>1,050,000 / 128,000 (max input 922,000)</td><td>1,050,000 / 128,000</td></tr>
<tr><td class="model-name">Knowledge cutoff</td><td>April 30, 2026</td><td>April 2026</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">※ GPT-6 Sol figures are as listed on our <a href="/en/pricing/">pricing comparison</a> (verified against OpenAI's page on 2026-09-25); GPT-6.1 Sol figures are from its model page, checked 2026-10-09.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="mig-h">
<h2 class="section-title" id="mig-h" style="font-size:1.2rem;">Migration notes worth acting on</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">Tool calling → Responses API</div><div class="spec-value">“Use the Responses API for tool calling. Chat Completions is supported without tool calling.” That is verbatim from the model page.</div></div>
  <div class="spec-item"><div class="spec-label">Drop temperature when effort ≠ none</div><div class="spec-value">When reasoning effort is not <code>none</code>, remove <code>temperature</code>, <code>top_p</code> and <code>top_logprobs</code> (plus <code>logprobs</code> on Chat Completions).</div></div>
  <div class="spec-item"><div class="spec-label">Cache TTL API changed</div><div class="spec-value">Replace <code>prompt_cache_retention</code> (GPT-5.5 and earlier) with <code>prompt_cache_options.ttl</code> set to <code>"30m"</code>.</div></div>
  <div class="spec-item"><div class="spec-label">Data residency</div><div class="spec-value">US and EU, including Fast and Ultrafast modes. Regional processing adds a 10% premium.</div></div>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="spec-h">
<h2 class="section-title" id="spec-h" style="font-size:1.2rem;">Specifications</h2>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>Value (official model page)</th></tr></thead><tbody>
<tr><td class="model-name">Model ID / snapshot</td><td><code>gpt-6.1-sol</code></td></tr>
<tr><td class="model-name">Context window</td><td>1,050,000 tokens</td></tr>
<tr><td class="model-name">Max input tokens</td><td>922,000</td></tr>
<tr><td class="model-name">Max output</td><td>128,000 tokens</td></tr>
<tr><td class="model-name">Modalities</td><td>text, images → text (audio and video unsupported)</td></tr>
<tr><td class="model-name">Knowledge cutoff</td><td>April 30, 2026 (reasoning token support)</td></tr>
<tr><td class="model-name">Endpoints</td><td>Responses, Chat Completions (without tools), Batch. Live / Realtime / Assistants / Embeddings / image generation / audio / fine-tuning are not supported.</td></tr>
<tr><td class="model-name">Tools</td><td>web search, file search, image generation, code interpreter, computer use, MCP, apply_patch and more</td></tr>
<tr><td class="model-name">Rate limits (Standard)</td><td>Build 5,000 RPM / 1,000,000 TPM; Launch 10,000 / 4,000,000; Grow 15,000 / 40,000,000</td></tr>
</tbody></table></div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="bench-h">
<h2 class="section-title" id="bench-h" style="font-size:1.2rem;">On benchmarks (our policy)</h2>
<p class="section-sub">OpenAI's model page publishes <strong>no numeric benchmark table</strong> (checked 2026-10-09). What it publishes is the positioning statement: “Near-Astra performance for complex work at a lower cost.”</p>
<ul style="font-size:.86rem;color:var(--c-muted);padding-left:1.3em;line-height:1.9;">
  <li>Third-party trackers publish scores, but <strong>we do not print numbers the vendor has not published</strong> — filling gaps with estimates would break our rule of publishing only what primary sources support.</li>
  <li>The most reliable evaluation is the one the vendor itself recommends: “Compare it with Astra on your tasks to assess the tradeoff between quality and cost.”</li>
</ul>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="rel-h">
<h2 class="section-title" id="rel-h" style="font-size:1.2rem;">Related pages</h2>
<ul style="font-size:.88rem;line-height:2;">
  <li><a href="/en/gpt-6-sol-luna/">GPT-6 Sol / GPT-6 Luna</a> — the sibling models (Sol at $2/$10, Luna at $0.10/$0.50)</li>
  <li><a href="/en/pricing/">LLM API pricing comparison</a></li>
  <li><a href="/en/calculator/">Token cost calculator</a></li>
  <li><a href="/en/claude-sonnet-5-5/">Claude Sonnet 5.5</a> — the same price band ($2/$10, $0.10 cache reads)</li>
  <li><a href="/en/glossary/prompt-cache/">Prompt caching explained</a></li>
  <li><a href="/en/timeline/">Release timeline</a></li>
</ul>
</section>

<div class="tip-box" style="border-left-color:var(--c-yellow);">
  <h3 style="font-size:1rem;margin:0 0 .5rem;">⚠️ Disclaimer</h3>
  <ul style="font-size:.84rem;color:var(--c-muted);line-height:1.9;">
    <li>Pricing and specifications were checked on 2026-10-09 against OpenAI's documentation (GPT-6.1 Sol model page and pricing page).</li>
    <li>Fast, Batch/Flex, Ultrafast and above-272K figures are our own calculations from the official multipliers; confirm against your invoice.</li>
    <li>The model page states no release date, so we label the date reported by third parties as third-party information.</li>
    <li>This site is informational and does not endorse or represent any provider.</li>
  </ul>
</div>
</div></main>
{F_EN}
</body>
</html>
'''
(S / 'en/gpt-6-1-sol').mkdir(parents=True, exist_ok=True)
(S / 'en/gpt-6-1-sol/index.html').write_text(sol_en, encoding='utf-8')
print("wrote en/gpt-6-1-sol", len(sol_en))

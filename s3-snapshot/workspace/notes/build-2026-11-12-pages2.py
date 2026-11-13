# -*- coding: utf-8 -*-
import os, re
SITE='/tmp/site'; TODAY='2026-11-12'; BASE='https://llm.okamomedia.tokyo'
src=open('build-2026-11-12-pages.py',encoding='utf-8').read()
# reuse constants from the first script by exec'ing only the preamble up to the JA page marker
preamble=src.split('# ============ JA page ============')[0]
ns={}; exec(preamble,ns)
STYLE=ns['STYLE']; HDR_EN=ns['HDR_EN']; FTR_EN=ns['FTR_EN']; GA=ns['GA']

T_EN='Batch API Discounts Compared (Nov 2026): OpenAI, Anthropic, Google, xAI — LLM Data Hub'
D_EN='Batch API discounts across five providers: 50% off at OpenAI, Anthropic and Google, 20% at xAI, 60% of standard at Moonshot. Turnaround, retention and limits from official docs (Nov 12, 2026).'
print('EN title len',len(T_EN),'desc len',len(D_EN))
assert len(T_EN)<=90 and len(D_EN)<=195
URL_EN=BASE+'/en/batch-api-pricing/'

rows=[
 ('OpenAI<br><small>Batch API</small>','Model-by-model eligibility list <strong>not confirmed</strong> in what we fetched','<strong>50% off</strong><br><small>input and output</small>','GPT-6.1 Terra $1.00 in / $5.00 out','$0.50 / $2.50<br><small>(calculated)</small>','Within 24 hours (often sooner)','Output file is deleted automatically 30 days after the batch completes','50,000 requests per batch / 200 MB input file / 2,000 batches per hour','<a href="https://developers.openai.com/api/docs/guides/batch" target="_blank" rel="noopener">Guide</a> (11-12)'),
 ('Anthropic<br><small>Message Batches API</small>','Fable 5.2 / Mythos 5.2 / Opus 5.5 / Sonnet 5.5 / Haiku 5.5 / Fable 5.1 and more (table below)','<strong>50% off</strong><br><small>input and output</small>','Fable 5.2 $8.00 in / $40.00 out','$4.00 / $20.00<br><small>(input from the official table, output calculated from 50%)</small>','Not confirmed','Not confirmed','Not confirmed','<a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank" rel="noopener">Pricing docs</a> (11-12)'),
 ('Google<br><small>Gemini Batch API</small>','Model-by-model list <strong>not confirmed</strong>. Gemini 4 Carbon: "Batch API isn&#39;t supported"','<strong>50% off</strong>','Gemini 4 Argon $2.00 in / $10.00 out (through Nov 30)','$1.00 / $5.00<br><small>(calculated)</small>','Target turnaround 24 hours (usually much quicker)','Not confirmed','Input file up to 2GB / inline requests under 20MB','<a href="https://ai.google.dev/gemini-api/docs/batch-mode" target="_blank" rel="noopener">Batch API</a> (11-12)'),
 ('xAI<br><small>Batch API</small>','grok-4.7 / 4.6 / 4.5 / 4.3 / 4.20 family (0309)','<strong>20% off</strong><br><small>varies by model; unlisted models get no discount</small>','grok-4.7 $2.00 in / $6.00 out','$1.60 / $4.80<br><small>(calculated)</small>','Most complete within 24 hours','Not confirmed','Batch requests do not count towards rate limits (request caps not confirmed)','<a href="https://docs.x.ai/developers/pricing" target="_blank" rel="noopener">API Pricing</a> (11-12)'),
 ('Moonshot<br><small>Batch API</small>','kimi-k3.1-pro / kimi-k3','<strong>60% of standard</strong><br><small>(40% off)</small>','kimi-k3.1-pro $2.00 in / $10.00 out','$1.20 / $6.00<br><small>(calculated)</small>','Not confirmed','Not confirmed','Not confirmed','<a href="https://platform.kimi.ai/docs/pricing/chat" target="_blank" rel="noopener">Kimi pricing</a> (11-12)'),
 ('DeepSeek<br><small>no batch API found</small>','deepseek-flash / deepseek-v4-pro','<strong>Off-peak is half of peak</strong><br><small>(50% off, time-based)</small>','deepseek-flash $0.30 in / $1.20 out (peak)','$0.15 / $0.60<br><small>(off-peak)</small>','— (not asynchronous batch)','—','Peak hours 01:00-04:00 and 06:00-10:00 UTC, Monday to Friday','<a href="https://api-docs.deepseek.com/quick_start/pricing" target="_blank" rel="noopener">Models &amp; Pricing</a> (11-12)'),
]
tbl='\n'.join('<tr>'+''.join('<td>%s</td>'%c for c in r)+'</tr>' for r in rows)

anth=[('Claude Fable 5.2','$4 / MTok'),('Claude Mythos 5.2','$4 / MTok'),('Claude Opus 5.5','$2 / MTok'),('Claude Sonnet 5.5','$1 / MTok'),('Claude Haiku 5.5','$0.05 / MTok up to 100,000 tokens / $0.25 / MTok above'),('Claude Fable 5.1','$5 / MTok'),('Claude Mythos 5.1','$5 / MTok'),('Claude Fable 5','$5 / MTok'),('Claude Opus 5','$2.50 / MTok'),('Claude Opus 4.8','$2.50 / MTok'),('Claude Sonnet 5','$1 / MTok'),('Claude Sonnet 4.6 / 4.5','$1.50 / MTok'),('Claude Haiku 4.5','$0.50 / MTok')]
anth_rows='\n'.join('<tr><td class="model-name">%s</td><td class="price">%s</td></tr>'%r for r in anth)

unconf=[('Anthropic turnaround, result retention and request caps','<strong>Not confirmed</strong>','The pricing docs we fetched contain no verbatim on batch deadlines, retention or caps (we are not claiming they do not exist).'),
 ('OpenAI per-model eligibility','<strong>Not confirmed</strong>','The batch guide states the discount, window and limits, but we could not capture a model list.'),
 ('Google model list and result retention','<strong>Not confirmed</strong>','We captured the discount, target turnaround and file limits only.'),
 ('xAI request caps and result retention','<strong>Not confirmed</strong>','API Pricing confirms the discount and "most completing within 24 hours".'),
 ('Moonshot deadline, retention and caps','<strong>Not confirmed</strong>','The pricing page states the 60% rate only; batch details live on a separate page to add next time.')]
unconf_rows='\n'.join('<tr><td class="model-name">%s</td><td>%s</td><td>%s</td></tr>'%r for r in unconf)

body=f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{T_EN}</title>
  <meta name="description" content="{D_EN}">
  <link rel="canonical" href="{URL_EN}">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta property="og:image" content="{BASE}/assets/og/en-batch-api-pricing.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Batch API discounts compared: 50% off at OpenAI, Anthropic and Google, 20% at xAI, 60% of standard at Moonshot (LLM Data Hub)">
  <meta name="twitter:image" content="{BASE}/assets/og/en-batch-api-pricing.png">
  <meta name="twitter:image:alt" content="Batch API discounts compared: 50% off at OpenAI, Anthropic and Google, 20% at xAI, 60% of standard at Moonshot (LLM Data Hub)">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{URL_EN}">
  <meta property="og:title" content="{T_EN}">
  <meta property="og:description" content="{D_EN}">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{{"@context": "https://schema.org", "@type": "Article", "headline": "Batch API Discounts Compared (Nov 2026)", "datePublished": "{TODAY}", "dateModified": "{TODAY}", "author": {{"@type": "Organization", "name": "LLM Data Hub"}}, "publisher": {{"@type": "Organization", "name": "okamo channel"}}, "url": "{URL_EN}", "inLanguage": "en", "isAccessibleForFree": true, "description": "{D_EN}"}}</script>
  {GA}
  <link rel="stylesheet" href="/assets/style.css">
  {STYLE}
  <link rel="alternate" hreflang="ja" href="{BASE}/batch-api-pricing/">
  <link rel="alternate" hreflang="en" href="{URL_EN}">
  <link rel="alternate" hreflang="x-default" href="{BASE}/batch-api-pricing/"></head>
<body>
{HDR_EN}
<main>
<div class="container" style="padding-top:2rem;">
<h1 class="section-title" style="font-size:1.6rem;">Batch API discounts compared <span style="font-size:1rem;font-weight:500;color:var(--c-muted);">(November 2026)</span></h1>
<p class="section-sub" style="max-width:780px;">How far the per-token price drops when you send a large volume of requests <strong>asynchronously</strong>, in one table. You trade real-time latency for a lower rate, so <strong>"can this job wait?" is the deciding question</strong>. Standard rates live in the <a href="/en/pricing/">LLM API pricing comparison</a>; reuse of the same prefix is covered in <a href="/en/prompt-cache-pricing/">prompt caching rates compared</a>.</p>
<div class="updated-bar"><span class="dot">●</span>Last updated: <time datetime="{TODAY}">November 12, 2026</time> | Official pages fetched on 2026-11-12; quotations are verbatim. Amounts derived by applying a published discount to a standard rate are labelled "calculated".</div>
<section class="section" style="padding-top:1rem;">
<h2 class="section-title" style="font-size:1.15rem;">Three things to know first</h2>
<ul style="max-width:840px;line-height:1.9;">
<li><strong>The big three all sit at 50% off.</strong> OpenAI, Anthropic and Google each halve the standard rate. The discount alone does not separate them, so <strong>deadlines, retention and caps do</strong>.</li>
<li><strong>Some providers set the discount per model.</strong> xAI varies by model and gives no discount to models outside its table. Moonshot charges 60% of standard, which is shallower than a 50% cut.</li>
<li><strong>Batch stacks with caching.</strong> Anthropic states verbatim: "Batch API and prompt caching discounts can be combined." For a nightly job that reuses the same instructions, <strong>cache plus batch</strong> is the cheapest combination.</li>
</ul>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">Batch discounts at a glance (USD per 1M tokens)</h2>
<div class="table-wrap"><table>
<thead><tr><th>Provider</th><th>Models</th><th>Discount vs standard</th><th>Standard (in / out)</th><th>Batch (in / out)</th><th>Turnaround</th><th>Result retention</th><th>Caps and limits</th><th>Source (fetched)</th></tr></thead>
<tbody>
{tbl}
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);max-width:880px;">"Calculated" means we applied the published discount (50% for OpenAI and Google, 20% for xAI, 60% of standard for Moonshot) to the standard rate. For Anthropic, the input side is quoted from the official batch table and the output side is derived from "50 percent discount on both input and output tokens". Standard rates are those published on 2026-11-12 (Gemini 4 Argon at its introductory price through Nov 30).</p>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">Anthropic batch input rates by model (verbatim from the official table)</h2>
<div class="table-wrap"><table>
<thead><tr><th>Model</th><th>Batch input</th></tr></thead>
<tbody>
{anth_rows}
</tbody></table></div>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">When it pays off: a nightly classification job</h2>
<p style="max-width:840px;line-height:1.9;">Say you classify <strong>200,000 support tickets overnight</strong> into issue types. At 1,500 input tokens and 200 output tokens per ticket, that is 300M input tokens and 40M output tokens.</p>
<div class="table-wrap"><table>
<thead><tr><th>Model</th><th>Standard API</th><th>Batch</th><th>Difference</th></tr></thead>
<tbody>
<tr><td class="model-name">GPT-6.1 Terra ($1.00 / $5.00)</td><td class="price">$300 + $200 = $500</td><td class="price">$250</td><td class="price">-$250</td></tr>
<tr><td class="model-name">Gemini 4 Argon ($2.00 / $10.00)</td><td class="price">$600 + $400 = $1,000</td><td class="price">$500</td><td class="price">-$500</td></tr>
<tr><td class="model-name">Kimi K3.1 Pro ($2.00 / $10.00)</td><td class="price">$600 + $400 = $1,000</td><td class="price">$600 (60% of standard)</td><td class="price">-$400</td></tr>
</tbody></table></div>
<p style="max-width:840px;line-height:1.9;">The job only needs the results <strong>by the next morning</strong>, so it fits inside the batch window (mostly 24 hours). A moderation check that has to answer on screen in the same request cannot wait, so it stays on the standard API. In practice: <strong>daily aggregation, classification, extraction and embedding jobs are batch candidates</strong>, while conversational loops and agents are not.</p>
<p style="max-width:840px;line-height:1.9;">If every request carries the same prefix (instructions, category definitions), combine this with <a href="/en/prompt-cache-pricing/">prompt caching</a> to cut the input side further. Anthropic explicitly allows the combination; OpenAI and Google treat caching and batch as separate discount axes (check each provider's docs for the order of application).</p>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">Batch is a latency and deadline trade-off</h2>
<p style="max-width:840px;line-height:1.9;">Batch APIs are <strong>asynchronous</strong>: you submit a job, get an ID, and collect results later. OpenAI states "Each batch completes within 24 hours (and often more quickly)" and the completion window can only be set to 24h. Google states "The target turnaround time is 24 hours, but in majority of cases, it is much quicker." xAI says batch requests are "queued and processed in the background, with most completing within 24 hours". <strong>You get an upper bound, not a precise finish time.</strong> For business-day use, submit the night before and collect in the morning.</p>
<p style="max-width:840px;line-height:1.9;">Expired requests are handled differently too. OpenAI writes them to an error file (code <code>batch_expired</code>), so you receive the successful subset only, which means designing for partial results and reruns. Rate limits also differ: xAI notes batch requests "don't count towards rate limits". <strong>Cheaper, but you own the deadline, partial-failure and collection logic.</strong></p>
<div class="read-box"><strong>Retention can be short.</strong> OpenAI states "The output file will automatically be deleted 30 days after the batch is complete." Copy results into your own storage as soon as a batch finishes. Retention for the other providers is shown as "Not confirmed" in the table above and will be added when we can quote it.</div>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">What we could not confirm (no guessing)</h2>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>Status</th><th>Note</th></tr></thead><tbody>
{unconf_rows}
</tbody></table></div>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">Sources (all fetched 2026-11-12)</h2>
<ul style="line-height:1.9;max-width:840px;">
<li>OpenAI Batch API: <a href="https://developers.openai.com/api/docs/guides/batch" target="_blank" rel="noopener">developers.openai.com/api/docs/guides/batch</a> ("50% cost discount compared to synchronous APIs", "Each batch completes within 24 hours", "The output file will automatically be deleted 30 days after the batch is complete.", "A single batch may include up to 50,000 requests, and a batch input file can be up to 200 MB in size.")</li>
<li>OpenAI pricing: <a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noopener">developers.openai.com/api/docs/pricing</a> (GPT-6.1 Terra $1.00 input / $5.00 output)</li>
<li>Anthropic pricing: <a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank" rel="noopener">platform.claude.com/docs/en/about-claude/pricing</a> ("The Batch API allows asynchronous processing of large volumes of requests with a 50 percent discount on both input and output tokens.", "Batch API and prompt caching discounts can be combined.", plus the per-model batch table)</li>
<li>Anthropic Claude Fable 5.2: <a href="https://www.anthropic.com/claude-fable-and-mythos-5-2" target="_blank" rel="noopener">anthropic.com/claude-fable-and-mythos-5-2</a> (standard $8 / $40, fast mode $16 / $80)</li>
<li>Google Gemini Batch API: <a href="https://ai.google.dev/gemini-api/docs/batch-mode" target="_blank" rel="noopener">ai.google.dev/gemini-api/docs/batch-mode</a> ("at 50% of the standard cost", "The target turnaround time is 24 hours, but in majority of cases, it is much quicker.", "The maximum allowed file size for an input file is 2GB.")</li>
<li>Google pricing: <a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noopener">ai.google.dev/gemini-api/docs/pricing</a> (Gemini 4 Carbon row and "Batch API isn't supported"; Argon $2.00 / $10.00)</li>
<li>xAI API pricing: <a href="https://docs.x.ai/developers/pricing" target="_blank" rel="noopener">docs.x.ai/developers/pricing</a> (per-model batch discount of 20% for grok-4.7 to 4.20; applies to all token types; image and video billed at standard rates)</li>
<li>Moonshot (Kimi): <a href="https://platform.kimi.ai/docs/pricing/chat" target="_blank" rel="noopener">platform.kimi.ai/docs/pricing/chat</a> ("kimi-k3.1-pro and kimi-k3 support batch inference ... billed at 60% of the standard price.")</li>
<li>DeepSeek: <a href="https://api-docs.deepseek.com/quick_start/pricing" target="_blank" rel="noopener">api-docs.deepseek.com/quick_start/pricing</a> ("Off-peak rates are half of the peak rates. Peak hours are 01:00 - 04:00 and 06:00 - 10:00 UTC, Monday through Friday")</li>
</ul>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">Related pages</h2>
<ul style="line-height:2;">
<li><a href="/en/pricing/">LLM API pricing comparison</a> — standard rates by model, with verification dates</li>
<li><a href="/en/prompt-cache-pricing/">Prompt caching rates compared</a> — read and write rates when you reuse a prefix</li>
<li><a href="/en/glossary/prompt-cache/">Glossary: prompt caching</a> — how it works and what to watch for</li>
<li><a href="/en/calculator/">Token cost calculator</a> — estimate from your input and output volumes</li>
<li><a href="/en/gpt-6-1-terra/">GPT-6.1 Terra</a> / <a href="/en/kimi-k3-1-pro/">Kimi K3.1 Pro</a> / <a href="/en/claude-fable-5-1/">Claude Fable 5.1</a></li>
</ul>
</section>
</div>
</main>
{FTR_EN}
</body>
</html>
'''
os.makedirs(SITE+'/en/batch-api-pricing',exist_ok=True)
open(SITE+'/en/batch-api-pricing/index.html','w',encoding='utf-8').write(body)
print('EN written',len(body))

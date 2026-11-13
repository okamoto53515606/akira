# -*- coding: utf-8 -*-
import io, re
SITE='/tmp/site/'
log=[]; fails=[]
def rd(p): return io.open(SITE+p,encoding='utf-8').read()
def wr(p,s): io.open(SITE+p,'w',encoding='utf-8').write(s)
def rep(p, old, new, label='', cnt=1):
    s=rd(p); n=s.count(old)
    if n!=cnt:
        fails.append('FAIL rep %s [%s] found %d want %d: %r'%(p,label,n,cnt,old[:80])); return
    wr(p, s.replace(old,new,1 if cnt==1 else cnt)); log.append('ok  rep %s [%s]'%(p,label))
def resub(p, pat, new, cnt=1, label=''):
    s=rd(p); s2,n=re.subn(pat,new,s,flags=re.S)
    if n!=cnt:
        fails.append('FAIL resub %s [%s] n=%d want %d pat=%r'%(p,label,n,cnt,pat[:80])); return
    wr(p,s2); log.append('ok  resub %s [%s]'%(p,label))
def insert_after_section(p, anchor, block, label=''):
    s=rd(p); i=s.find('<section aria-labelledby="%s"'%anchor)
    if i<0: fails.append('FAIL insert %s [%s] anchor'%(p,label)); return
    j=s.find('</section>', i)
    if j<0: fails.append('FAIL insert %s [%s] close'%(p,label)); return
    j+=len('</section>')
    wr(p, s[:j]+' '+block+s[j:]); log.append('ok  insert %s [%s]'%(p,label))
def insert_before_pat(p, pat, block, label=''):
    s=rd(p); m=re.search(pat,s,re.S)
    if not m: fails.append('FAIL insertbefore %s [%s] pat=%r'%(p,label,pat)); return
    wr(p, s[:m.start()]+block+s[m.start():]); log.append('ok  insertbefore %s [%s]'%(p,label))
def set_meta(p, tag, marker, new, label=''):
    s=rd(p)
    pat=re.compile(r'(<meta '+tag+r' content=")([^"]*'+re.escape(marker)+r'[^"]*)(")')
    s2,n=pat.subn(lambda m: m.group(1)+new+m.group(3), s)
    if n!=1: fails.append('FAIL meta %s [%s] n=%d'%(p,label,n)); return
    wr(p,s2); log.append('ok  meta %s [%s] len %d->%d'%(p,label,len(s)-len(s2)+len(new),len(new)))

# ---------- 1. JA top ----------
p='index.html'
rep(p,'最終更新: <time datetime="2026-10-09">2026年10月9日</time> — Claude Haiku 5.5・GPT-6.1 Sol を追加 — ',
      '最終更新: <time datetime="2026-10-17">2026年10月17日</time> — Meta Muse Wonder（10/12発表・$4/$20）を年表に追加、全モデルの料金を再確認 — ','10-17bar')
D_JA_TOP='OpenAI・Anthropic・Google・DeepSeek・xAI・Z.ai・Alibaba・MetaのLLM API料金を公式一次情報で随時更新。GPT-6 Astra（$10/$50）・Claude Opus 5.5（$4/$20）・Gemini 3.8 Flash・Claude Haiku 5.5（$0.10/$0.50）・GPT-6.1 Sol（$2/$10）・DeepSeek V4.1 Flash・Meta Muse Wonder（$4/$20）を掲載。中国系AI総覧・トークンコスト計算機・モデル年表を一次情報ベースで提供（2026年10月17日更新）。'
set_meta(p,'name="description"','LLM API料金',D_JA_TOP,'desc')

# ---------- 2. EN top ----------
p='en/index.html'
rep(p,'Last updated: <time datetime="2026-10-09">October 9, 2026</time> — ',
      'Last updated: <time datetime="2026-10-17">October 17, 2026</time> — Meta Muse Wonder (Oct 12, $4/$20) added to the timeline; all model prices re-verified — ','10-17bar')
D_EN_TOP='Verified LLM API pricing for GPT-6 Astra ($10/$50), Claude Opus 5.5 ($4/$20), Gemini 3.8 Flash, Claude Haiku 5.5 ($0.10/$0.50), GPT-6.1 Sol ($2/$10), DeepSeek V4.1 Flash and Meta Muse Wonder ($4/$20). Token cost calculator, price comparison and model timeline, all primary-source. Updated October 17, 2026.'
set_meta(p,'name="description"','LLM API',D_EN_TOP,'desc')

# ---------- 3. JA pricing ----------
p='pricing/index.html'
rep(p,'<time datetime="2026-10-09">2026年10月9日</time>（料金最終確認: ','<time datetime="2026-10-17">2026年10月17日</time>（料金最終確認: ','upd-time')
rep(p,'Qwen 2026-09-01, その他 2026-08-04 JST）','Qwen 2026-09-01, Meta Model API 2026-10-17, その他 2026-08-04 JST／全モデル再確認 2026-10-17（変更なし））','upd-list')
rep(p,'その他: 2026-08-04 JST）</li>','その他: 2026-08-04 JST、Meta Model API: 2026-10-17 JST）</li>','disclaimer')
resub(p,r'"dateModified":"2026-10-09"','"dateModified":"2026-10-17"',1,'dateModified')
D_JA_PR='OpenAI・Anthropic Claude・Google Gemini・DeepSeek・xAI Grok・Z.ai GLM・Alibaba Qwen・MetaのLLM API料金を公式一次情報から直接確認し、USD/1Mトークンで比較。GPT-6 Astra（$10/$50）・Claude Opus 5.5（$4/$20）・Gemini 3.8 Flash（導入価格$0.75/$3.75）・Claude Haiku 5.5（$0.10/$0.50）・GPT-6.1 Sol（$2/$10）・DeepSeek V4.1 Flash・Meta Muse Wonder（$4/$20）を掲載。キャッシュ料金と長文割増も明記（2026年10月17日に全モデルの単価を公式ページで再確認）。'
set_meta(p,'name="description"','LLM API料金',D_JA_PR,'desc')
set_meta(p,'property="og:description"','LLM API料金','GPT-6 Astra（$10/$50）・Claude Opus 5.5（$4/$20）・Gemini 3.8 Flash・Claude Haiku 5.5（$0.10/$0.50）・DeepSeek V4.1 Flash・Meta Muse Wonder（$4/$20）のAPI料金を公式一次情報で比較（2026年10月17日再確認）。','ogdesc')
META_JA='''<section aria-labelledby="meta-h"><div class="provider-header"><span class="provider-dot dot-other"></span><h2 id="meta-h">Meta（Meta Model API / Muse）</h2></div> <p style="font-size:.78rem;color:var(--c-muted);background:var(--c-surface2);border:1px solid var(--c-border);border-radius:6px;padding:.4rem .8rem;margin-bottom:.6rem;display:inline-block;">📋 Standard モード・USD / 1Mトークン。Muse Wonder は Contributor モードの提供なし、長文プレミアムなし</p> <p style="font-size:.78rem;color:var(--c-muted);background:var(--c-surface2);border:1px solid var(--c-border);border-radius:6px;padding:.5rem .8rem;margin-bottom:.8rem;">✅ 2026-10-17 に公式の料金ページ（dev.meta.ai / Pricing and rate limits）を直接確認。<strong>Muse Wonder（2026-10-12公開・muse-wonder-1.0）は入力 $4.00・キャッシュ入力 $0.20・出力 $20.00</strong>。Muse Wonder Full は Muse Code のサブスク限定で、トークン従量課金の掲載はありません。</p> <div class="table-wrap"><table><thead><tr><th>モデル</th><th>入力</th><th>キャッシュ入力</th><th>出力</th><th>備考</th></tr></thead><tbody> <tr><td class="model-name">Muse Wonder <span class="badge badge-new">New</span><br><small>(muse-wonder-1.0)</small></td><td class="price">$4.00</td><td class="price">$0.20</td><td class="price">$20.00</td><td>2026-10-12公開。1Mコンテキスト・長文プレミアムなし。Web検索グラウンディングは $2.50 / 1,000クエリの別建て <a href="/timeline/" style="font-weight:700;">→年表</a></td></tr> <tr><td class="model-name">Muse Spark<br><small>(muse-spark-1.3 / 1.2 / 1.1)</small></td><td class="price">$1.25<br><small>Contributor $0.10</small></td><td class="price">$0.15<br><small>Contributor $0.002</small></td><td class="price">$4.25<br><small>Contributor $0.20</small></td><td>Muse Spark 1.1 は Standard モードのみ。Contributor モードは <code>muse-spark-1.3-contributor</code> / <code>1.2-contributor</code> で利用</td></tr> </tbody></table></div> <p style="font-size:.78rem;color:var(--c-muted);">トークン従量課金以外: Muse Image（画像生成）$0.01/枚（内蔵のWeb・画像検索込み）、Muse Voice Transcribe $0.18/時（秒単位課金・ストリーミング/非ストリーミング同額）、Web検索グラウンディング $2.50/1,000クエリ。一次情報: <a href="https://dev.meta.ai/docs/pricing-rate-limits" target="_blank" rel="noopener">dev.meta.ai（Pricing and rate limits）</a>（2026-10-17確認）。<a href="/timeline/">📄 モデル年表 →</a></p> </section>'''
insert_after_section(p,'qwen-h',META_JA,'meta-section')

# ---------- 4. EN pricing ----------
p='en/pricing/index.html'
rep(p,'<time datetime="2026-10-09">October 9, 2026</time> (pricing verified ','<time datetime="2026-10-17">October 17, 2026</time> (pricing verified ','upd-time')
rep(p,'others 2026-08-04)','others 2026-08-04; Meta Model API 2026-10-17; all models re-verified 2026-10-17 (no changes))','upd-list')
rep(p,'others 2026-08-04.</li>','others 2026-08-04; Meta Model API 2026-10-17.</li>','disclaimer')
resub(p,r'"dateModified":"2026-10-09"','"dateModified":"2026-10-17"',1,'dateModified')
D_EN_PR='LLM API pricing for OpenAI, Anthropic, Google, DeepSeek, xAI, Z.ai, Qwen and Meta, verified against official sources in USD per 1M tokens: GPT-6 Astra ($10/$50), Claude Opus 5.5 ($4/$20), Gemini 3.8 Flash ($0.75/$3.75 intro), Claude Haiku 5.5 ($0.10/$0.50) and Meta Muse Wonder ($4/$20). Cache rates included. Updated October 17, 2026.'
set_meta(p,'name="description"','LLM API pricing',D_EN_PR,'desc')
set_meta(p,'property="og:description"','LLM API pricing','GPT-6 Astra ($10/$50), Claude Opus 5.5 ($4/$20), Gemini 3.8 Flash, Claude Haiku 5.5 ($0.10/$0.50), DeepSeek V4.1 Flash and Meta Muse Wonder ($4/$20), verified against official sources (re-checked October 17, 2026).','ogdesc')
META_EN='''<section aria-labelledby="meta-h"><div class="provider-header"><span class="provider-dot dot-other"></span><h2 id="meta-h">Meta (Meta Model API / Muse)</h2></div> <p style="font-size:.78rem;color:var(--c-muted);background:var(--c-surface2);border:1px solid var(--c-border);border-radius:6px;padding:.4rem .8rem;margin-bottom:.6rem;display:inline-block;">📋 Standard mode, USD per 1M tokens. Muse Wonder has no Contributor mode and no long-context premium</p> <p style="font-size:.78rem;color:var(--c-muted);background:var(--c-surface2);border:1px solid var(--c-border);border-radius:6px;padding:.5rem .8rem;margin-bottom:.8rem;">✅ Checked the official pricing page (dev.meta.ai / Pricing and rate limits) on 2026-10-17. <strong>Muse Wonder (launched 2026-10-12, muse-wonder-1.0) is $4.00 input / $0.20 cached input / $20.00 output</strong>. Muse Wonder Full is subscription-only in Muse Code, with no token-metered rate published.</p> <div class="table-wrap"><table><thead><tr><th>Model</th><th>Input</th><th>Cached input</th><th>Output</th><th>Notes</th></tr></thead><tbody> <tr><td class="model-name">Muse Wonder <span class="badge badge-new">New</span><br><small>(muse-wonder-1.0)</small></td><td class="price">$4.00</td><td class="price">$0.20</td><td class="price">$20.00</td><td>Launched 2026-10-12. 1M context, no long-context premium. Web search grounding is billed separately at $2.50 per 1,000 queries <a href="/en/timeline/" style="font-weight:700;">→ timeline</a></td></tr> <tr><td class="model-name">Muse Spark<br><small>(muse-spark-1.3 / 1.2 / 1.1)</small></td><td class="price">$1.25<br><small>Contributor $0.10</small></td><td class="price">$0.15<br><small>Contributor $0.002</small></td><td class="price">$4.25<br><small>Contributor $0.20</small></td><td>Muse Spark 1.1 is Standard mode only. Contributor mode is available via the <code>muse-spark-1.3-contributor</code> / <code>1.2-contributor</code> variants</td></tr> </tbody></table></div> <p style="font-size:.78rem;color:var(--c-muted);">Beyond token pricing: Muse Image (image generation) $0.01 per image including its built-in web and image search, Muse Voice Transcribe $0.18 per hour of audio (billed per second, streaming and non-streaming alike), web search grounding $2.50 per 1,000 queries. Source: <a href="https://dev.meta.ai/docs/pricing-rate-limits" target="_blank" rel="noopener">dev.meta.ai (Pricing and rate limits)</a>, checked 2026-10-17. <a href="/en/timeline/">📄 Model timeline →</a></p> </section>'''
insert_after_section(p,'qwen-h',META_EN,'meta-section')

# ---------- 5. multimodal (JA desc) ----------
p='multimodal/index.html'
D_MM='Gemini・GPT・Claude・Qwen・GLM・Grok・DeepSeekの画像・音声・動画・PDF・DOCX・XLSX・PPTXの入力/出力可否と料金を公式一次情報で一覧。Gemini 3.8・GPT-6 Astra・Qwen3.8-Flash・GLM-5.3-Flash・DeepSeek V4.1 Flashなどの対応範囲、ClaudeのPDF対応、画像を入力できるモデルと画像・音声を生成するモデルが別である点、API直では扱えないOffice形式も明記（2026年10月17日更新）。'
set_meta(p,'name="description"','マルチモーダル',D_MM,'desc')

# ---------- 6. mai JA ----------
p='mai/index.html'
D_MAI='Microsoftの自社開発LLM「MAI」シリーズを解説。MAI-Image-2.6/2.6-Flash（画像生成）、MAI-Transcribe-2-Streaming/2（音声認識）、MAI-Thinking-1（推論）などのモデル・料金・APIの使い方・年表を一次情報（microsoft.ai / Azure Foundry）で整理。Azure料金表で「入力をText/Imageに分けて掲載＝画像を入力に使えるモデル」かどうかの見分け方も解説（2026年10月17日更新）。'
set_meta(p,'name="description"','MAI',D_MAI,'desc')
resub(p,r'<time datetime="2026-10-13">2026年10月13日</time>','<time datetime="2026-10-17">2026年10月17日</time>',1,'disp-date')
resub(p,r'"dateModified":"2026-10-13"','"dateModified":"2026-10-17"',1,'dateModified')
rep(p,'（2026-10-03 時点で、','（2026-10-17 時点で、','refnote-date')
P_MAI='<p style="font-size:.85rem;color:var(--c-muted);margin:.9rem 0 0;border-left:2px solid var(--c-border);padding-left:.7rem;"><strong>料金表の読み方（画像生成と画像理解の違い）:</strong> Azure Foundry Models pricing の Microsoft セクションでは、モデルごとに「入力」欄の種類が違います。<strong>MAI-Image-2.5 / 2.5 Flash / 2.5 Pro は入力が Text / Image の2種類に分けて掲載</strong>され、画像を入力として渡す使い方の単価が別建てです。一方 <strong>MAI-Image-2 / MAI-Image-2-Efficient は入力がテキスト1種類のみ</strong>で、MAI-Thinking-1 などのテキスト系も入力欄はテキストのみの掲載です。つまり入力欄が「Text / Image」に分かれているモデル＝画像を入力（理解）に使えるモデル、出力欄が画像のモデル＝画像を生成するモデル、と読み分けられます。（2026-10-17 に公式料金ページで再確認）</p>'
insert_before_pat(p,r'<h3[^>]*>[^<]*参考価格',P_MAI,'read-howto')
# 6b. label clarifications JA
for old,new in [('<td>画像生成（41%低コスト）</td>','<td>画像生成（41%低コスト）<br><small>Image out</small></td>'),
                ('<td>画像生成（高品質）</td>','<td>画像生成（高品質）<br><small>Image out</small></td>'),
                ('<td>画像生成（高速）</td>','<td>画像生成（高速）<br><small>Image out</small></td>'),
                ('<td>画像生成（Global）</td>','<td>画像生成（Global）<br><small>Image out</small></td>'),
                ('<td>画像生成</td>','<td>画像生成<br><small>Image out</small></td>'),
                ('<code>image_generation</code> 透過</td>','<code>image_generation</code> 透過<br><small>Image out / Image in</small></td>')]:
    rep(p,old,new,'lbl')

# ---------- 7. mai EN ----------
p='en/mai/index.html'
D_MAIE="Microsoft's first-party MAI family explained: MAI-Image-2.6/2.6-Flash (image generation), MAI-Transcribe-2-Streaming/2 (speech), MAI-Thinking-1 (reasoning), plus pricing, API usage and a release timeline from microsoft.ai and Azure Foundry. Also covers how to read the Azure price table: whether a model's input row is split into Text / Image (so it accepts images) or lists text only. Updated October 17, 2026."
set_meta(p,'name="description"','Microsoft',D_MAIE,'desc')
resub(p,r'<time datetime="2026-10-13">October 13, 2026</time>','<time datetime="2026-10-17">October 17, 2026</time>',1,'disp-date')
resub(p,r'"dateModified":"2026-10-13"','"dateModified":"2026-10-17"',1,'dateModified')
rep(p,'as of 2026-10-03 neither','as of 2026-10-17 neither','refnote-date')
P_MAIE="<p style=\"font-size:.85rem;color:var(--c-muted);margin:.9rem 0 0;border-left:2px solid var(--c-border);padding-left:.7rem;\"><strong>How to read the table (image generation vs image understanding):</strong> in the Microsoft section of Azure Foundry Models pricing, the Input column differs by model. <strong>MAI-Image-2.5 / 2.5 Flash / 2.5 Pro list two input kinds, Text and Image,</strong> with separate rates for passing an image as input. <strong>MAI-Image-2 / MAI-Image-2-Efficient list text input only,</strong> and text models such as MAI-Thinking-1 also list text input only. In short: a split Text / Image input row means the model accepts images (understanding), while an image in the Output column means the model generates images. (Re-checked on the official pricing page on 2026-10-17.)</p>"
insert_before_pat(p,r'<h3[^>]*>[^<]*Reference prices',P_MAIE,'read-howto')
for old,new in [('<td>Image generation (41% lower cost)</td>','<td>Image generation (41% lower cost)<br><small>Image out</small></td>'),
                ('<td>Image generation (high quality)</td>','<td>Image generation (high quality)<br><small>Image out</small></td>'),
                ('<td>Image generation (fast)</td>','<td>Image generation (fast)<br><small>Image out</small></td>'),
                ('<td>Image generation (Global)</td>','<td>Image generation (Global)<br><small>Image out</small></td>'),
                ('<td>Image generation</td>','<td>Image generation<br><small>Image out</small></td>'),
                ('<code>image_generation</code> passthrough</td>','<code>image_generation</code> passthrough<br><small>Image out / Image in</small></td>')]:
    rep(p,old,new,'lbl')

# ---------- 8. sitemap ----------
p='sitemap.xml'
for u,d in [('https://llm.okamomedia.tokyo/','2026-10-17'),('https://llm.okamomedia.tokyo/en/','2026-10-17'),
            ('https://llm.okamomedia.tokyo/pricing/','2026-10-17'),('https://llm.okamomedia.tokyo/en/pricing/','2026-10-17'),
            ('https://llm.okamomedia.tokyo/mai/','2026-10-17'),('https://llm.okamomedia.tokyo/en/mai/','2026-10-17'),
            ('https://llm.okamomedia.tokyo/multimodal/','2026-10-17')]:
    s=rd(p); pat=re.compile(r'(<loc>'+re.escape(u)+r'</loc>\s*<lastmod>)([0-9-]+)(</lastmod>)')
    s2,n=pat.subn(lambda m:m.group(1)+d+m.group(3), s)
    if n!=1: fails.append('FAIL sitemap %s n=%d'%(u,n))
    else: wr(p,s2)

print('FAILS:'); [print(' ',f) for f in fails] or print('  none')
print('EDITS:',len(log))
for l in log: print('  '+l)
print('DESC LENS: JA_top=%d EN_top=%d JA_pr=%d EN_pr=%d MM=%d MAI=%d MAI_en=%d'%(len(D_JA_TOP),len(D_EN_TOP),len(D_JA_PR),len(D_EN_PR),len(D_MM),len(D_MAI),len(D_MAIE)))

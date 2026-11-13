# -*- coding: utf-8 -*-
import io, re
SITE='/tmp/site/'
log=[]; fails=[]
def rd(p): return io.open(SITE+p,encoding='utf-8').read()
def wr(p,s): io.open(SITE+p,'w',encoding='utf-8').write(s)
def rep(p, old, new, label='', cnt=1):
    s=rd(p); n=s.count(old)
    if n!=cnt:
        fails.append('FAIL rep %s [%s] found %d want %d: %r'%(p,label,n,cnt,old[:60])); return
    wr(p, s.replace(old,new,cnt)); log.append('ok  rep %s [%s]'%(p,label))
def resub(p, pat, new, label='', cnt=1):
    s=rd(p); s2,n=re.subn(pat,new,s,flags=re.S)
    if n!=cnt:
        fails.append('FAIL resub %s [%s] n=%d want %d pat=%r'%(p,label,n,cnt,pat[:60])); return
    wr(p,s2); log.append('ok  resub %s [%s]'%(p,label))
def insert_before_pat(p, pat, block, label=''):
    s=rd(p); m=re.search(pat,s,re.S)
    if not m: fails.append('FAIL insertbefore %s [%s] pat=%r'%(p,label,pat)); return
    wr(p, s[:m.start()]+block+s[m.start():]); log.append('ok  insertbefore %s [%s]'%(p,label))
def set_meta(p, tag, marker, new, label=''):
    s=rd(p)
    pat=re.compile(r'(<meta '+tag+r' content=")([^"]*'+re.escape(marker)+r'[^"]*)(")')
    s2,n=pat.subn(lambda m: m.group(1)+new+m.group(3), s)
    if n!=1: fails.append('FAIL meta %s [%s] n=%d'%(p,label,n)); return
    wr(p,s2); log.append('ok  meta %s [%s] len->%d'%(p,label,len(new)))

# --- mai JA labels ---
p='mai/index.html'
for old,new in [('<td>画像生成（41%低コスト）</td>','<td>画像生成（41%低コスト）<br><small>Image out</small></td>'),
                ('<td>画像生成（高品質）</td>','<td>画像生成（高品質）<br><small>Image out</small></td>'),
                ('<td>画像生成（高速）</td>','<td>画像生成（高速）<br><small>Image out</small></td>'),
                ('<td>画像生成（Global）</td>','<td>画像生成（Global）<br><small>Image out</small></td>'),
                ('<td>画像生成</td>','<td>画像生成<br><small>Image out</small></td>'),
                ('<code>image_generation</code> 透過</td>','<code>image_generation</code> 透過<br><small>Image out / Image in</small></td>')]:
    rep(p,old,new,'lbl-ja')

# --- mai EN ---
p='en/mai/index.html'
D_MAIE="Microsoft's first-party MAI family explained: MAI-Image-2.6/2.6-Flash (image generation), MAI-Transcribe-2-Streaming/2 (speech), MAI-Thinking-1 (reasoning), plus pricing, API usage and a release timeline from microsoft.ai and Azure Foundry. Also covers how to read the Azure price table: whether a model's input row is split into Text / Image (so it accepts images) or lists text only. Updated October 17, 2026."
set_meta(p,'name="description"','Microsoft',D_MAIE,'desc')
resub(p,r'<time datetime="2026-10-13">October 13, 2026</time>','<time datetime="2026-10-17">October 17, 2026</time>','disp-date')
resub(p,r'"dateModified":"2026-10-13"','"dateModified":"2026-10-17"','dateModified')
rep(p,'as of 2026-10-03 neither','as of 2026-10-17 neither','refnote-date')
P_MAIE="<p style=\"font-size:.85rem;color:var(--c-muted);margin:.9rem 0 0;border-left:2px solid var(--c-border);padding-left:.7rem;\"><strong>How to read the table (image generation vs image understanding):</strong> in the Microsoft section of Azure Foundry Models pricing, the Input column differs by model. <strong>MAI-Image-2.5 / 2.5 Flash / 2.5 Pro list two input kinds, Text and Image,</strong> with separate rates for passing an image as input. <strong>MAI-Image-2 / MAI-Image-2-Efficient list text input only,</strong> and text models such as MAI-Thinking-1 also list text input only. In short: a split Text / Image input row means the model accepts images (understanding), while an image in the Output column means the model generates images. (Re-checked on the official pricing page on 2026-10-17.)</p>"
insert_before_pat(p,r'<h3[^>]*>[^<]*Reference prices',P_MAIE,'read-howto')
for old,new in [('<td>Image generation (41% lower cost)</td>','<td>Image generation (41% lower cost)<br><small>Image out</small></td>'),
                ('<td>Image generation (high quality)</td>','<td>Image generation (high quality)<br><small>Image out</small></td>'),
                ('<td>Image generation (fast)</td>','<td>Image generation (fast)<br><small>Image out</small></td>'),
                ('<td>Image generation (Global)</td>','<td>Image generation (Global)<br><small>Image out</small></td>'),
                ('<td>Image generation</td>','<td>Image generation<br><small>Image out</small></td>'),
                ('<code>image_generation</code> passthrough</td>','<code>image_generation</code> passthrough<br><small>Image out / Image in</small></td>')]:
    rep(p,old,new,'lbl-en')

# --- sitemap ---
p='sitemap.xml'
for u in ['https://llm.okamomedia.tokyo/','https://llm.okamomedia.tokyo/en/','https://llm.okamomedia.tokyo/pricing/',
          'https://llm.okamomedia.tokyo/en/pricing/','https://llm.okamomedia.tokyo/mai/','https://llm.okamomedia.tokyo/en/mai/',
          'https://llm.okamomedia.tokyo/multimodal/']:
    s=rd(p); pat=re.compile(r'(<loc>'+re.escape(u)+r'</loc>\s*<lastmod>)([0-9-]+)(</lastmod>)')
    s2,n=pat.subn(lambda m:m.group(1)+'2026-10-17'+m.group(3), s)
    if n!=1: fails.append('FAIL sitemap %s n=%d'%(u,n))
    else: wr(p,s2); log.append('ok  sitemap %s'%u)
print('FAILS:'); [print(' ',f) for f in fails] or print('  none')
print('EDITS:',len(log))
for l in log: print('  '+l)

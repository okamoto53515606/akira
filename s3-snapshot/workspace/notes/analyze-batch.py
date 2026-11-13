import io,os,difflib
BASE='/tmp/site/'; PROD='/tmp/site_prod/'
BLOCK='  <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">\n  <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">\n  <meta property="og:image" content="https://llm.okamomedia.tokyo/assets/ogp-default.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="LLM Data Hub — 主要LLM APIの料金を公式一次情報で比較できるデータハブ"><meta name="twitter:image" content="https://llm.okamomedia.tokyo/assets/ogp-default.png">\n'
summary={}
detail={}
for root,dirs,files in os.walk(BASE):
    for f in files:
        if not f.endswith('.html'): continue
        p=os.path.join(root,f); rel=os.path.relpath(p,BASE)
        pp=os.path.join(PROD,rel)
        if not os.path.exists(pp): summary[rel]='NEW_FILE'; continue
        L=io.open(p,encoding='utf-8').read(); P=io.open(pp,encoding='utf-8').read()
        n_block=L.count(BLOCK)
        L2=L.replace(BLOCK,'')
        d=[l for l in difflib.unified_diff(P.split('\n'),L2.split('\n'),lineterm='',n=0) if l[:1] in '+-' and not l.startswith(('+++','---'))]
        if not d: continue
        summary[rel]='block=%d rest=%d'%(n_block,len(d))
        detail[rel]=d
print('files with residual (non-head-block) changes:')
for k in sorted(summary): print('  ',k,summary[k])
print()
print('=== residual diffs (trimmed to 400 chars/line) ===')
for k in sorted(detail):
    if summary[k].startswith('NEW_FILE'): continue
    print('#####',k)
    for l in detail[k][:20]:
        print('   ',l[:400])

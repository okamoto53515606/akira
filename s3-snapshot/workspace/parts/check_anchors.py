#!/usr/bin/env python3
# 内部アンカー（/path/#id, #id）の実在チェック。使い方: python3 check_anchors.py /tmp/site
import re,os,sys,glob,urllib.parse
root=sys.argv[1] if len(sys.argv)>1 else '/tmp/site'
os.chdir(root)
files=[p for p in glob.glob('**/*.html',recursive=True)]
ids={}
for p in files:
    s=open(p,encoding='utf-8').read()
    ids[p]=set(re.findall(r'\sid="([^"]+)"',s))|set(re.findall(r'\sname="([^"]+)"',s))
def resolve(base,fragmented):
    t=fragmented.split('#')[0].split('?')[0]
    if t=='' : return base
    if t.startswith('http'):
        if 'llm.okamomedia.tokyo' not in t: return None
        t=urllib.parse.urlparse(t).path
    path=t.lstrip('/') if t.startswith('/') else os.path.normpath(os.path.join(os.path.dirname(base),t))
    if path in ('','.'): path='index.html'
    elif path.endswith('/'): path+='index.html'
    elif '.' not in os.path.basename(path): path+='/index.html'
    return path
ghost=[];n=0
for p in files:
    for m in re.finditer(r'href="([^"]*#[^"]+)"',open(p,encoding='utf-8').read()):
        h=m.group(1); t=resolve(p,h)
        if t is None: continue
        n+=1
        if t not in ids: ghost.append((p,h,'TARGET_MISSING')); continue
        f=urllib.parse.unquote(h.split('#',1)[1])
        if f and f not in ids[t]: ghost.append((p,h,'ANCHOR_MISSING in '+t))
print('internal fragments checked:',n,'GHOSTS:',len(ghost))
for g in ghost: print(' ',g)
sys.exit(1 if ghost else 0)

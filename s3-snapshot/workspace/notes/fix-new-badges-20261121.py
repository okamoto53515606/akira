# -*- coding: utf-8 -*-
"""New/値下/プロモ/🆕 ラベルの全数掃除（2026-11-21）
方針: 状態は状態列(現行/旧版/提供終了予定)で表す。Newバッジは付けない。
     本文の一般名詞・公式逐語引用は温存する。
"""
import json, re, pathlib, sys

WS = pathlib.Path('/workspace'); SITE = pathlib.Path('/tmp/site')
log = []          # (lang, file, n, label)

def L(lang, f, n, label): log.append((lang, str(f), n, label))

# ================= 1. facts.json（台帳）=================
fp = WS/'data'/'facts.json'
facts = json.loads(fp.read_text(encoding='utf-8'))

# 1a. names の末尾に付いた " New" / " Updated" ラベル（New は changelog の
#     「… New を掲載」という二重ラベルになっていた）
for mid, rec in facts['models'].items():
    for lang in ('ja','en'):
        nm = (rec.get('names') or {}).get(lang)
        if not nm: continue
        m = re.match(r'^(.*?)\s+(New|Updated)\s*$', nm, re.S)
        if m:
            rec['names'][lang] = m.group(1).strip()
            L(lang, 'facts.json names.'+mid, 1, 'drop trailing %s' % m.group(2))

# 1b. price note の "New flagship"（en/pricing・en/gpt-6 の元データ）
for mid, rec in facts['models'].items():
    pr = rec.get('price') or {}
    for lang in ('ja','en'):
        k = 'note_'+lang
        if pr.get(k) and 'New flagship' in pr[k]:
            pr[k] = pr[k].replace('New flagship','Flagship')
            L(lang, 'facts.json price.note.'+mid, 1, 'New flagship -> Flagship')

# 1c. pricing_tables の rows（en の備考セル）
for t in facts.get('pricing_tables') or []:
    for row in t.get('rows') or []:
        for lang in ('ja','en'):
            v = row.get(lang)
            if v and 'New flagship' in v:
                row[lang] = v.replace('New flagship','Flagship')
                L(lang, 'facts.json pricing_tables', 1, 'New flagship -> Flagship')

# 1d. features（特集ページ本文）の badge-new と "New <a ...>"
for slug, rec in (facts.get('features') or {}).items():
    for bi, blk in enumerate(rec.get('blocks') or []):
        for lang in ('ja','en'):
            body = (blk.get('body') or {}).get(lang)
            if not body: continue
            orig = body
            n = body.count('<span class="badge badge-new">New</span>')
            body = re.sub(r'\s*<span class="badge badge-new">New</span>', '', body)
            if n: L(lang, 'facts.json features/%s[%d]'%(slug,bi), n, 'remove badge-new span')
            # 最新モデルの強調は表の既存作法(<strong>)に寄せる＝「現行」情報を失わない
            m2 = re.search(r'(?<!<strong>)Gemini Nano Banana 2\.1\s*<', body)
            if 'Gemini Nano Banana 2.1 <br>' in body:
                body = body.replace('Gemini Nano Banana 2.1 <br>','<strong>Gemini Nano Banana 2.1</strong><br>')
                L(lang, 'facts.json features/%s[%d]'%(slug,bi), 1, 'Nano Banana 2.1 -> <strong>(現行の強調)')
            # changelog 行の "New <a>deep-dive page</a>" ＝ ラベル用途
            n3 = len(re.findall(r'\bNew <a href="/en/', body))
            if n3:
                body = re.sub(r'\bNew (<a href="/en/[^"]*">deep-dive page</a>)', r'A \1', body)
                L(lang, 'facts.json features/%s[%d]'%(slug,bi), n3, 'New deep-dive -> A deep-dive')
            if body != orig:
                blk['body'][lang] = body

fp.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding='utf-8')
print('[facts.json] written')

# ================= 2. 手書きページ =================
def patch(rel, pairs, lang):
    p = SITE/rel
    s = p.read_text(encoding='utf-8'); o = s
    for old, new, expect in pairs:
        c = s.count(old)
        if c != expect:
            print('  !! %s: expected %d got %d for %r' % (rel, expect, c, old[:70]))
        s = s.replace(old, new)
        L(lang, rel, c, 'replace %r' % old[:60])
    if s != o:
        p.write_text(s, encoding='utf-8')

# 2a. glossary: 見出し前の New バッジ（表ではないので状態列は不要）
for lang, rel in (('ja','glossary/index.html'), ('en','en/glossary/index.html')):
    patch(rel, [('<span class="badge badge-new">New</span> ', '', 4)], lang)

# 2b. kimi: New バッジ撤去 + 状態列(現行/旧版)を補う。USD/JPY 2表の両方に入れる。
def kimi_state(rel, lang, hdr_old, hdr_new, cur, old_v):
    p = SITE/rel; s = p.read_text(encoding='utf-8'); o = s
    s = s.replace('kimi-k3.1-pro <span class="badge badge-new">New</span>', 'kimi-k3.1-pro')
    def tbl(m):
        t = m.group(0)
        if hdr_old not in t: return t                      # 対象表だけ
        t = t.replace(hdr_old, hdr_new, 1)
        def row(rm):
            r = rm.group(0)
            last = old_v if ('前世代' in r or 'previous generation' in r) else cur
            return r[:-len('</tr>')] + '<td>%s</td></tr>' % last
        return re.sub(r'<tr>.*?</tr>', row, t, flags=re.S)
    s = re.sub(r'<table>.*?</table>', tbl, s, flags=re.S)
    if s != o:
        p.write_text(s, encoding='utf-8')
    return s

j = kimi_state('kimi-k3-1-pro/index.html','ja',
        '</th><th>キャッシュ書込（1時間）</th></tr></thead><tbody>',
        '</th><th>キャッシュ書込（1時間）</th><th>状態</th></tr></thead><tbody>',
        '現行','旧版')
L('ja','kimi-k3-1-pro/index.html', j.count('<th>状態</th>'), 'add 状態 column (tables)')
L('ja','kimi-k3-1-pro/index.html', j.count('<td>旧版</td>'), 'rows marked 旧版')
e = kimi_state('en/kimi-k3-1-pro/index.html','en',
        '<th>1h writes</th></tr></thead><tbody>',
        '<th>1h writes</th><th>Status</th></tr></thead><tbody>',
        'Current','Legacy')
L('en','en/kimi-k3-1-pro/index.html', e.count('<th>Status</th>'), 'add Status column (tables)')
L('en','en/kimi-k3-1-pro/index.html', e.count('<td>Legacy</td>'), 'rows marked Legacy')

# 2c. gpt-6-sol-luna: 世代列を状態語に（ja 新/旧 -> 現行/旧版、en New/Older -> Current/Legacy）
patch('gpt-6-sol-luna/index.html', [
    ('<strong>新（GPT-6世代）</strong>','<strong>現行（GPT-6世代）</strong>',2),
    ('旧（GPT-5.6世代）','旧版（GPT-5.6世代）',2)], 'ja')
patch('en/gpt-6-sol-luna/index.html', [
    ('<strong>New (GPT-6 era)</strong>','<strong>Current (GPT-6 era)</strong>',2),
    ('Older (GPT-5.6 era)','Legacy (GPT-5.6 era)',2)], 'en')

# 2d. en/gpt-6: title / og:title / JSON-LD / price-flag / 備考
patch('en/gpt-6/index.html', [
    ("OpenAI's New Flagship","OpenAI's Flagship",3),
    ('New flagship','Flagship',2)], 'en')
# 2e. en/claude-fable-5-1
patch('en/claude-fable-5-1/index.html', [
    ("Anthropic's New Mythos-Class Flagship","Anthropic's Mythos-Class Flagship",1),
    ('New flagship','Flagship',1)], 'en')
# 2f. en/grok-4-6 / grok-4-7 の見出し
patch('en/grok-4-6/index.html', [("xAI's New Flagship","xAI's Flagship",3)], 'en')
patch('en/grok-4-7/index.html', [('Larger New Flagship','Larger Flagship',2)], 'en')

# 2g. 🆕（ja/en grok-4-6 の後継案内）
for lang, rel in (('ja','grok-4-6/index.html'), ('en','en/grok-4-6/index.html')):
    p = SITE/rel; s = p.read_text(encoding='utf-8')
    n = s.count('🆕')
    if n:
        s = re.sub(r'🆕\s*', '', s); p.write_text(s, encoding='utf-8')
    L(lang, rel, n, 'remove 🆕')

# ================= 3. 集計 =================
from collections import Counter
c = Counter()
for lang, f, n, label in log: c[lang] += n
print('\n=== 削除・置換 件数（ja / en）===')
print('ja:', c['ja'], ' en:', c['en'], ' total:', c['ja']+c['en'])
print('\n=== 明細 ===')
for lang, f, n, label in log:
    print('%-3s %-42s %2d  %s' % (lang, f, n, label))
json.dump([{'lang':a,'file':b,'n':c_,'label':d} for a,b,c_,d in log],
          open('/workspace/notes/newbadge-changes.json','w'), ensure_ascii=False, indent=1)

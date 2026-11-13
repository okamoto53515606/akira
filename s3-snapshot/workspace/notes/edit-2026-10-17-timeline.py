# -*- coding: utf-8 -*-
import io,re
SITE='/tmp/site/'
log=[];fails=[]
def rd(p): return io.open(SITE+p,encoding='utf-8').read()
def wr(p,s): io.open(SITE+p,'w',encoding='utf-8').write(s)
def rep(p,old,new,label='',cnt=1):
    s=rd(p);n=s.count(old)
    if n!=cnt: fails.append('FAIL %s [%s] n=%d want %d: %r'%(p,label,n,cnt,old[:70]));return
    wr(p,s.replace(old,new,cnt));log.append('ok %s [%s]'%(p,label))
CSS='.tl-item.dot-meta::before{background:#0866ff}.tl-provider-tag.meta{background:rgba(8,102,255,.16);color:#7db4ff}.legend-dot.meta{background:#0866ff}</style>'
LEG_OLD='<span class="legend-item"><span class="legend-dot xai"></span>xAI</span>'
LEG_NEW=LEG_OLD+'<span class="legend-item"><span class="legend-dot meta"></span>Meta</span>'
JA=('<article class="tl-item dot-meta" id="meta-muse-wonder"><div class="tl-card"><div class="tl-date">2026-10-12 '
 '<span class="tl-provider-tag meta">Meta</span></div><h2 class="tl-title">Meta Muse Wonder / Muse Wonder Full 公開 — Metaがエージェント特化のフロンティアモデルで本格参入 '
 '<span class="badge badge-new" style="font-size:.7rem;">New</span></h2><p class="tl-desc"><strong>料金</strong>: <code>muse-wonder-1.0</code> は入力$4.00・キャッシュ入力$0.20・出力$20.00（USD/1M）。'
 '<strong>長文プレミアムなし</strong>（コンテキストの埋まり具合で単価は変わらない）・Contributorモードの提供なし。Web検索グラウンディングは$2.50/1,000クエリの別建て。<br>'
 '<strong>仕様</strong>: 1Mコンテキスト。長時間走るエージェント、サブエージェントへの委譲、高度なコンピュータ操作（ブラウザ・デスクトップ・モバイル）向け。'
 '<br><strong>上位モデル</strong>: Muse Wonder Full はトークン従量ではなく Muse Code サブスク限定（Power $50/月・Maximum $200/月）。'
 'Muse Code の通常プランで使う <code>muse-spark-1.3 / 1.2 / 1.1</code> は入力$1.25・キャッシュ入力$0.15・出力$4.25（Contributorモードは$0.10/$0.002/$0.20、Spark 1.1はStandardのみ）。'
 '<span class="tl-price-badge">$4.00 / $0.20 / $20.00</span></p><div class="tl-links">'
 '<a href="https://dev.meta.ai/models/muse-wonder" target="_blank" rel="noopener">公式モデルページ →</a>'
 '<a href="https://ai.meta.com/blog/muse-wonder-muse-wonder-full/" target="_blank" rel="noopener">公式発表（2026-10-12） →</a>'
 '<a href="/pricing/">料金比較 →</a></div></div></article>')
EN=('<article class="tl-item dot-meta" id="meta-muse-wonder"><div class="tl-card"><div class="tl-date">2026-10-12 '
 '<span class="tl-provider-tag meta">Meta</span></div><h2 class="tl-title">Meta launches Muse Wonder / Muse Wonder Full — its agent-first frontier models '
 '<span class="badge badge-new" style="font-size:.7rem;">New</span></h2><p class="tl-desc"><strong>Pricing</strong>: <code>muse-wonder-1.0</code> is $4.00 input / $0.20 cached input / $20.00 output per 1M tokens. '
 '<strong>No long-context premium</strong> (rate is flat whether the window is nearly empty or nearly full) and no Contributor mode. Web search grounding is billed separately at $2.50 per 1,000 queries.<br>'
 '<strong>Specs</strong>: 1M context, built for long-running agents, sub-agent delegation and advanced computer use (browser, desktop, mobile).'
 '<br><strong>Tier above</strong>: Muse Wonder Full is not token-priced; it ships by subscription in Muse Code (Power $50/mo, Maximum $200/mo). '
 'Muse Code plans also serve <code>muse-spark-1.3 / 1.2 / 1.1</code> at $1.25 input / $0.15 cached / $4.25 output (Contributor mode $0.10 / $0.002 / $0.20; Spark 1.1 is Standard mode only).'
 '<span class="tl-price-badge">$4.00 / $0.20 / $20.00</span></p><div class="tl-links">'
 '<a href="https://dev.meta.ai/models/muse-wonder" target="_blank" rel="noopener">Official model page →</a>'
 '<a href="https://ai.meta.com/blog/muse-wonder-muse-wonder-full/" target="_blank" rel="noopener">Announcement (2026-10-12) →</a>'
 '<a href="/en/pricing/">Pricing →</a></div></div></article>')
for p,item,legrange,newrange,bar_old,bar_new in [
 ('timeline/index.html',JA,'【2025年1月〜2026年9月】','【2025年1月〜2026年10月】',
  '<span class="dot">●</span>最終更新: <time datetime="2026-10-09">2026年10月9日</time> | 各項目に一次情報リンク掲載',
  '<span class="dot">●</span>最終更新: <time datetime="2026-10-17">2026年10月17日</time> | Meta Muse Wonder（10/12公開・$4.00/$0.20/$20.00）を追加 | 各項目に一次情報リンク掲載'),
 ('en/timeline/index.html',EN,'[Jan 2025 – Sep 2026]','[Jan 2025 – Oct 2026]',
  '<span class="dot">●</span>Last updated: <time datetime="2026-10-09">October 9, 2026</time> | Primary-source links per entry',
  '<span class="dot">●</span>Last updated: <time datetime="2026-10-17">October 17, 2026</time> | Added Meta Muse Wonder (launched 10/12, $4.00/$0.20/$20.00) | Primary-source links per entry')]:
    rep(p,'</style>',CSS,'css')
    rep(p,LEG_OLD,LEG_NEW,'legend')
    rep(p,legrange,newrange,'range')
    rep(p,bar_old,bar_new,'bar')
    rep(p,'"dateModified":"2026-10-09"','"dateModified":"2026-10-17"','dm')
    s=rd(p); j=s.rfind('</article>')+len('</article>')
    wr(p,s[:j]+"\n"+item+s[j:]); log.append('ok %s [append-item]'%p)
# sitemap: timeline lastmod
s=rd('sitemap.xml'); n=0
for loc in ['https://llm.okamomedia.tokyo/timeline/','https://llm.okamomedia.tokyo/en/timeline/']:
    s,c=re.subn(re.escape('<loc>%s</loc>'%loc)+r'(\s*)<lastmod>[^<]*</lastmod>', '<loc>%s</loc>\\1<lastmod>2026-10-17</lastmod>'%loc, s, flags=re.S)
    n+=c
wr('sitemap.xml',s)
if n!=2: fails.append('FAIL sitemap timeline n=%d'%n)
else: log.append('ok sitemap timeline x2')
print('\n'.join(log)); print('--- FAILS ---'); print('\n'.join(fails) if fails else 'none')

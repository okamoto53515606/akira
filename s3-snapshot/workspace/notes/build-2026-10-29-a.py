import json, re, io, os

SITE = '/tmp/site'
TODAY = '2026-10-29'
BASE = 'https://llm.okamomedia.tokyo'

# ---------- 1. SOT ----------
p = '/workspace/data/price-sot.json'
sot = json.load(open(p, encoding='utf-8'))
sot['sources']['openai_gpt61_terra'] = 'https://openai.com/index/introducing-gpt-6-1-terra/'
sot['sources']['openai_model_gpt61_terra'] = 'https://developers.openai.com/api/docs/models/gpt-6.1-terra'
sot['models']['gpt-6-1-terra'] = {
    "name_ja": "GPT-6.1 Terra",
    "name_en": "GPT-6.1 Terra",
    "api_model_id": "gpt-6.1-terra",
    "provider": "OpenAI",
    "status": "current",
    "released": "2026-10-26",
    "released_note": "公式ブログは「Starting today」とのみ記載（日付の明示なし）。第三者報道（9to5Mac / BleepingComputer / GitHub Changelog）はいずれも2026-10-26で一致。当サイトはこの点を明記して掲載。",
    "price": {
        "cache_hit_input": 0.05,
        "cache_miss_input": 1.0,
        "output": 5.0,
        "cache_write_input": 1.25,
        "cache_write_12h_input": 2.5,
        "above_272k_cache_miss_input": 2.0,
        "above_272k_cache_hit_input": 0.1,
        "above_272k_output": 7.5
    },
    "speed_multipliers": {"fast": 2, "batch_flex": 0.5, "regional_processing": 1.1},
    "context": "1,050,000",
    "max_output": "128,000",
    "knowledge_cutoff": "2026-06-01",
    "pages": ["/gpt-6-1-terra/", "/en/gpt-6-1-terra/"],
    "sources": [
        "https://openai.com/index/introducing-gpt-6-1-terra/",
        "https://developers.openai.com/api/docs/models/gpt-6.1-terra",
        "https://developers.openai.com/api/docs/pricing"
    ],
    "verified": TODAY,
    "relation_note": "公式ブログの逐語では「A significant step up from GPT-5.6 Terra」。GPT-5.6 Terraの後継にあたる上位グレードであり、GPT-6.1 Solとは同世代の別グレード（Solの後継ではない）。",
    "note": "272,000トークン超の入力はリクエスト全体が入力・キャッシュ2倍／出力1.5倍。Batch/Flexは50%引き、Fastは2倍、地域処理は+10%。reasoning effortは none/low/medium(既定)/high/xhigh/max。"
}
sot['last_verified'] = TODAY
json.dump(sot, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

# ---------- 2. calculator data (site側 data/models.json) ----------
cp = SITE + '/data/models.json'
calc = json.load(open(cp, encoding='utf-8'))
calc['updated'] = TODAY
names = [m['name'] for m in calc['models']]
entry = {
    "name": "GPT-6.1 Terra",
    "provider": "openai",
    "label": "OpenAI",
    "input": 1.0,
    "output": 5.0,
    "note": "キャッシュ入力$0.05（入力の5%）・272,000トークン超はリクエスト全体が入力2倍/出力1.5倍。1.05Mコンテキスト・128K出力",
    "note_en": "cached input $0.05 (5% of input) · above 272,000 input tokens the whole request is repriced at 2x input / 1.5x output · 1.05M context, 128K output"
}
if 'GPT-6.1 Terra' not in names:
    i = names.index('GPT-6.1 Sol') + 1
    calc['models'].insert(i, entry)
json.dump(calc, open(cp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('calc models:', len(calc['models']))

# ---------- 3. 新規ページ2枚 ----------
TECH = {
    'ja': {
        'title': 'GPT-6.1 Terra — $1/$5の高速コンピュータ操作モデル【1.05Mコンテキスト・272K超は2倍】 — LLM Data Hub',
        'desc': 'OpenAI GPT-6.1 Terra（gpt-6.1-terra）を公式ブログと公式モデルページで確認。入力$1.00・キャッシュ入力$0.05・出力$5.00（USD/1Mトークン）、1,050,000コンテキスト・128,000出力。272,000トークン超はリクエスト全体が入力2倍/出力1.5倍。GPT-5.6 Terraとの関係も逐語で整理。',
        'ogdesc': '入力$1.00・キャッシュ$0.05・出力$5.00、1.05Mコンテキスト・128K出力。272K超は入力2倍。GPT-5.6 Terraの上位後継であることを公式逐語で整理。',
        'url': BASE + '/gpt-6-1-terra/',
        'alt': 'GPT-6.1 Terraの料金と仕様: 入力$1.00・出力$5.00、1.05Mコンテキスト、272K超は2倍',
        'h1': 'GPT-6.1 <span>Terra</span>',
        'flag': '$1.00 入力 / $5.00 出力（1Mトークン）',
        'lead': 'OpenAIが2026-10-26に発表した「速くて安い」コンピュータ操作モデル。前世代のGPT-5.6 Terraの上位後継で、標準API料金はGPT-5.6 TerraとGPT-6.1 Solの50%下。',
    },
    'en': {
        'title': 'GPT-6.1 Terra: $1/$5 Computer-Use Model, 1.05M Context (Oct 2026) — LLM Data Hub',
        'desc': 'OpenAI GPT-6.1 Terra (gpt-6.1-terra) checked against the official launch post and model page: $1.00 input / $0.05 cached input / $5.00 output per 1M tokens, 1,050,000-token context, 128,000 max output. Above 272,000 input tokens the whole request is repriced at 2x input and 1.5x output. Relation to GPT-5.6 Terra quoted verbatim.',
        'ogdesc': '$1.00 input, $0.05 cached, $5.00 output, 1.05M context, 128K max output. Above 272K input the whole request doubles. How Terra relates to GPT-5.6 Terra, quoted verbatim.',
        'url': BASE + '/en/gpt-6-1-terra/',
        'alt': 'GPT-6.1 Terra pricing and specs: $1.00 input, $5.00 output, 1.05M context, 2x above 272K',
        'h1': 'GPT-6.1 <span>Terra</span>',
        'flag': '$1.00 input / $5.00 output per 1M tokens',
        'lead': 'OpenAI\'s fast, low-cost computer-use model announced on October 26, 2026. It is the step up from GPT-5.6 Terra, and its standard API prices are 50% lower than GPT-5.6 Terra and GPT-6.1 Sol.',
    }
}

STYLE_ADD = ('\n<style>\n'
             '.key-visual{margin:1.8rem auto 0;max-width:960px;padding:0 1rem}\n'
             '.key-visual img{width:100%;height:auto;border-radius:12px;border:1px solid var(--c-border);display:block}\n'
             '.key-visual figcaption{font-size:.76rem;color:var(--c-muted);margin-top:.5rem;text-align:center}\n'
             '</style>\n')

def head_for(tpl_path, lang, t):
    src = open(tpl_path, encoding='utf-8').read()
    head, rest = src.split('</head>', 1)
    S = re.S
    head = re.sub(r'<title>.*?</title>', '<title>%s</title>' % t['title'], head, flags=S)
    head = re.sub(r'<meta name="description" content="[^"]*">',
                  '<meta name="description" content="%s">' % t['desc'], head, flags=S)
    head = re.sub(r'<link rel="canonical" href="[^"]*">',
                  '<link rel="canonical" href="%s">' % t['url'], head, flags=S)
    head = re.sub(r'<link rel="alternate" hreflang="ja" href="[^"]*">',
                  '<link rel="alternate" hreflang="ja" href="%s">' % (BASE + '/gpt-6-1-terra/'), head)
    head = re.sub(r'<link rel="alternate" hreflang="en" href="[^"]*">',
                  '<link rel="alternate" hreflang="en" href="%s">' % (BASE + '/en/gpt-6-1-terra/'), head)
    head = re.sub(r'<link rel="alternate" hreflang="x-default" href="[^"]*">',
                  '<link rel="alternate" hreflang="x-default" href="%s">' % (BASE + '/gpt-6-1-terra/'), head)
    head = re.sub(r'<meta property="og:url" content="[^"]*">',
                  '<meta property="og:url" content="%s">' % t['url'], head)
    head = re.sub(r'<meta property="og:title" content="[^"]*">',
                  '<meta property="og:title" content="%s">' % t['title'].replace(' — LLM Data Hub', ''), head)
    head = re.sub(r'<meta property="og:description" content="[^"]*">',
                  '<meta property="og:description" content="%s">' % t['ogdesc'], head)
    head = re.sub(r'<meta property="og:image" content="[^"]*">',
                  '<meta property="og:image" content="%s/assets/og/%s-gpt-6-1-terra.png">' % (BASE, lang), head)
    head = re.sub(r'<meta property="og:image:alt" content="[^"]*">',
                  '<meta property="og:image:alt" content="%s">' % t['alt'], head)
    head = re.sub(r'<meta name="twitter:image" content="[^"]*">',
                  '<meta name="twitter:image" content="%s/assets/og/%s-gpt-6-1-terra.png">' % (BASE, lang), head)
    head = re.sub(r'<meta name="twitter:image:alt" content="[^"]*">',
                  '<meta name="twitter:image:alt" content="%s">' % t['alt'], head)
    # JSON-LD
    article = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": t['title'].replace(' — LLM Data Hub', ''),
        "datePublished": TODAY, "dateModified": TODAY,
        "author": {"@type": "Organization", "name": "LLM Data Hub"},
        "publisher": {"@type": "Organization", "name": "okamoちゃんねる"},
        "url": t['url'], "inLanguage": lang,
        "about": {"@type": "SoftwareApplication", "name": "GPT-6.1 Terra", "applicationCategory": "AI model"}
    }
    crumb_name = 'GPT-6.1 Terra'
    crumb_home = ('ホーム' if lang == 'ja' else 'Home')
    crumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": crumb_home, "item": BASE + ('/' if lang == 'ja' else '/en/')},
        {"@type": "ListItem", "position": 2, "name": crumb_name, "item": t['url']}]}
    head = re.sub(r'<script type="application/ld\+json">\{"@context":"https://schema.org","@type":"Article".*?</script>',
                  '<script type="application/ld+json">%s</script>' % json.dumps(article, ensure_ascii=False), head, flags=S)
    head = re.sub(r'<script type="application/ld\+json">\{"@context":"https://schema.org","@type":"BreadcrumbList".*?</script>',
                  '<script type="application/ld+json">%s</script>' % json.dumps(crumb, ensure_ascii=False), head, flags=S)
    return head + STYLE_ADD + '</head>', rest

def body_for(rest, lang, t):
    pre, tail = rest.split('</header>', 1)
    footer = tail[tail.index('<footer'):]
    hero = '''
<section class="hero-sonnet">
  <div class="price-flag">%s</div>
  <h1>%s</h1>
  <p class="lead">%s</p>
  <div class="quick-stats">
    <div class="stat"><span class="lbl">%s</span><span class="val">$1.00</span></div>
    <div class="stat"><span class="lbl">%s</span><span class="val">$5.00</span></div>
    <div class="stat"><span class="lbl">%s</span><span class="val">1,050,000</span></div>
    <div class="stat"><span class="lbl">%s</span><span class="val">128,000</span></div>
  </div>
  <figure class="key-visual">
    <img src="/assets/og/%s-gpt-6-1-terra.png" width="1200" height="630" alt="%s">
    <figcaption>%s</figcaption>
  </figure>
</section>
''' % (t['flag'], t['h1'], t['lead'],
       ('入力 / 1M' if lang == 'ja' else 'Input / 1M'),
       ('出力 / 1M' if lang == 'ja' else 'Output / 1M'),
       ('コンテキスト' if lang == 'ja' else 'Context'),
       ('最大出力' if lang == 'ja' else 'Max output'),
       lang, t['alt'],
       ('ページ別OG画像（1200×630）' if lang == 'ja' else 'Page-specific OG image (1200x630)'))
    return pre + '</header>' + hero + '<main>__MAIN__</main>\n' + footer

# ---- ja main ----
MAIN_JA = '''
<div class="container">
<div class="updated-bar" style="margin-top:2rem;"><span class="dot">●</span>最終更新: <time datetime="2026-10-29">2026年10月29日</time> | 一次情報: <a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">OpenAI公式ブログ</a>・<a href="https://developers.openai.com/api/docs/models/gpt-6.1-terra" target="_blank" rel="noopener">公式モデルページ</a>・<a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noopener">公式料金ページ</a></div>

<section class="section" style="padding-top:2rem;" aria-labelledby="tl-h">
<h2 class="section-title" id="tl-h" style="font-size:1.2rem;">短くまとめると</h2>
<div class="context-note" style="border-left-color:var(--c-blue);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>料金は入力$1.00・キャッシュ入力$0.05・出力$5.00</strong>（USD/1Mトークン、公式モデルページ）。キャッシュ入力は入力の5%</li>
    <li><strong>前世代はGPT-5.6 Terra。</strong>公式ブログの逐語は「A significant step up from GPT‑5.6 Terra」。<strong>GPT-6.1 Solの後継ではありません</strong>（Solとは同世代の別グレード）</li>
    <li><strong>1,050,000トークンコンテキスト・128,000トークン最大出力。</strong>知識カットオフは2026-06-01（公式モデルページ）</li>
    <li><strong>272,000トークン超の入力は「リクエスト全体」が入力2倍・出力1.5倍。</strong>長文一括処理は割高になります</li>
    <li><strong>reasoning effortは none / low / medium（既定）/ high / xhigh / max。</strong>入力はテキストと画像、出力はテキスト</li>
    <li><strong>ChatGPT Work・Codex（Plus/Pro/Enterprise/Edu）とAPIで提供。</strong>APIのモデルIDは <code>gpt-6.1-terra</code></li>
    <li><strong>公式ブログにリリース日の明記はありません。</strong>第三者報道は2026-10-26で一致（当サイトはこの点を明記して掲載）</li>
  </ul>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="rel-h">
<h2 class="section-title" id="rel-h" style="font-size:1.2rem;">GPT-6.1 Solとの関係（公式の記述だけで整理）</h2>
<p class="section-sub">「後継か派生か」は推測せず、公式の逐語だけで整理します。</p>
<div class="table-wrap"><table><thead><tr><th>論点</th><th>公式の記述</th><th>当サイトの整理</th></tr></thead><tbody>
<tr><td class="model-name">前世代</td><td>「A significant step up from GPT‑5.6 Terra」</td><td>GPT-5.6 Terraの上位後継</td></tr>
<tr><td class="model-name">Solとの関係</td><td>「Its standard API prices are 50% lower than those of GPT‑5.6 Terra and GPT‑6.1 Sol」</td><td>同世代（GPT-6.1系）の別グレード。Solの後継ではない</td></tr>
<tr><td class="model-name">使い分け</td><td>「For the most complex coding tasks, GPT-6.1 Sol and GPT-6 Astra remain the better choice.」</td><td>最難関のコーディングはSol／Astra</td></tr>
</tbody></table></div>
<p class="source-note">出典: <a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">OpenAI — Introducing GPT-6.1 Terra</a>（2026-10-29取得）</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="price-h">
<h2 class="section-title" id="price-h" style="font-size:1.2rem;">料金（USD / 1Mトークン、公式モデルページより）</h2>
<p class="section-sub">Standardは公式の記載値そのまま。Fast・Batch/Flex・Ultrafastは公式の倍率（2倍・50%引き・6倍）から当サイトが算出した参考値です。</p>
<div class="table-wrap"><table><thead><tr><th>項目</th><th>Standard</th><th>Fast（2倍）</th><th>Batch / Flex（50%引き）</th></tr></thead><tbody>
<tr><td class="model-name">入力</td><td class="price">$1.00</td><td>$2.00</td><td>$0.50</td></tr>
<tr><td class="model-name">キャッシュ入力</td><td class="price">$0.05</td><td>$0.10</td><td>$0.025</td></tr>
<tr><td class="model-name">キャッシュ書込（1.25倍）</td><td class="price">$1.25</td><td>$2.50</td><td>$0.625</td></tr>
<tr><td class="model-name">出力</td><td class="price">$5.00</td><td>$10.00</td><td>$2.50</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">※ 公式の注記: キャッシュ入力は「入力の5%」、キャッシュ書込は「入力の1.25倍」（30分保持。12時間保持は$2.50）。BatchとFlexは50%引き、Fast modeは2倍、地域処理は+10%。</p>
<p class="source-note">出典: <a href="https://developers.openai.com/api/docs/models/gpt-6.1-terra" target="_blank" rel="noopener">OpenAI — GPT-6.1 Terra（Pricing）</a>（2026-10-29取得）</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="long-h">
<h2 class="section-title" id="long-h" style="font-size:1.2rem;">272Kトークンの壁：長文を1回で流すと割高になる</h2>
<p class="section-sub">公式の注記は「272,000入力トークンを超えるプロンプトは、<strong>リクエスト全体</strong>が入力・キャッシュの2倍、出力の1.5倍で課金される」。1.05Mのコンテキストがあっても、長文を1回で送ると単価が上がります。</p>
<div class="table-wrap"><table><thead><tr><th>ケース</th><th>計算</th><th>金額</th></tr></thead><tbody>
<tr><td class="model-name">300,000トークン入力＋5,000トークン出力<br>（1回で送る）</td><td>入力 $2/M × 0.3 ＋ 出力 $7.5/M × 0.005<br><small>※272K超のため入力2倍・出力1.5倍</small></td><td class="price">約$0.64</td></tr>
<tr><td class="model-name">同内容を100,000トークンずつ3回に分ける<br>（文脈が分断されない場合）</td><td>入力 $1/M × 0.3 ＋ 出力は各回の分だけ</td><td class="price">約$0.30</td></tr>
</tbody></table></div>
<ul style="font-size:.86rem;color:var(--c-muted);padding-left:1.3em;line-height:1.9;">
  <li><strong>「1.05Mコンテキスト」と「1.05Mを1回で送る」は別の話です。</strong>272Kを超えるとそのリクエスト全体が割増になります。</li>
  <li><strong>会話を長く続ける用途ではキャッシュ入力$0.05が効きます。</strong>ただし272Kを超えた時点でキャッシュも2倍（$0.10/M）です。</li>
  <li>数字はすべて公式の倍率からの計算値です。実際の課金はAPIのレスポンスで確認してください。</li>
</ul>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="spec-h">
<h2 class="section-title" id="spec-h" style="font-size:1.2rem;">仕様（公式モデルページ）</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">コンテキスト</div><div class="spec-value">1,050,000</div></div>
  <div class="spec-item"><div class="spec-label">最大出力</div><div class="spec-value">128,000</div></div>
  <div class="spec-item"><div class="spec-label">知識カットオフ</div><div class="spec-value">2026-06-01</div></div>
  <div class="spec-item"><div class="spec-label">入力</div><div class="spec-value">テキスト・画像</div></div>
  <div class="spec-item"><div class="spec-label">出力</div><div class="spec-value">テキスト</div></div>
  <div class="spec-item"><div class="spec-label">reasoning effort</div><div class="spec-value">none〜max</div></div>
  <div class="spec-item"><div class="spec-label">ツール</div><div class="spec-value">computer use / MCP</div></div>
  <div class="spec-item"><div class="spec-label">スナップショット</div><div class="spec-value">gpt-6.1-terra</div></div>
</div>
<p class="source-note">出典: <a href="https://developers.openai.com/api/docs/models/gpt-6.1-terra" target="_blank" rel="noopener">OpenAI — GPT-6.1 Terra</a>（2026-10-29取得）。ツール呼び出しはResponses API経由です。</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="bench-h">
<h2 class="section-title" id="bench-h" style="font-size:1.2rem;">ベンチマーク（すべてOpenAIの自社ハーネス・自社公表値）</h2>
<p class="section-sub">以下の数値は<strong>OpenAIが自社の評価ハーネスで測った公表値</strong>です。第三者の独立検証ではありません。</p>
<div class="table-wrap"><table><thead><tr><th>ベンチマーク</th><th>GPT-6.1 Terra</th><th>比較対象（公式ブログの記述）</th></tr></thead><tbody>
<tr><td class="model-name">Agents&#39; Last Exam（v1・medium effort）</td><td class="price">GPT-5.6 Terraより15ポイント高</td><td>約3分の1のコスト。max effortではClaude Opus 5.5比で約3倍トークン効率・約9倍低コスト/タスク</td></tr>
<tr><td class="model-name">MMMU-Pro（視覚推論）</td><td class="price">全ての推論設定でGPT-5.6 Terraを上回る</td><td>GPT-6 Astra・GPT-6.1 Solに「ほぼ匹敵」（低コストで）</td></tr>
<tr><td class="model-name">OSWorld 2.1（デスクトップ操作）</td><td class="price">medium effortでGPT-5.6 Terraの最高スコアを上回る</td><td>タスクあたりコストは「ほんの一部」</td></tr>
<tr><td class="model-name">Terminal-Bench 4.0（max effort）</td><td class="price">50.3%</td><td>GPT-5.6 Terraの公表値21.5%の2倍超</td></tr>
<tr><td class="model-name">Terminal-Bench-Science 0.1（max effort）</td><td class="price">GPT-6.1 Solを上回る</td><td>Opus 5.5まで5ポイント以内・推定コストは5分の1未満</td></tr>
<tr><td class="model-name">社内エラー誘発プロンプト（low effort）</td><td class="price">エラー率16.7%</td><td>GPT-5.6 Terraは53.6%（約37ポイント改善）</td></tr>
</tbody></table></div>
<p class="source-note">出典: <a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">OpenAI — Introducing GPT-6.1 Terra</a>（2026-10-29取得）。Arena等の第三者スコアは本ページ公開時点で未確認です。</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="avail-h">
<h2 class="section-title" id="avail-h" style="font-size:1.2rem;">提供先・提供段階</h2>
<ul style="font-size:.9rem;padding-left:1.3em;line-height:1.9;">
  <li><strong>ChatGPT Work・Codex</strong>: Plus / Pro / Enterprise / Edu の全ユーザーに提供（公式ブログ「available to all Plus, Pro, Enterprise, and Edu users」）。</li>
  <li><strong>API</strong>: モデルID <code>gpt-6.1-terra</code> で提供（公式ブログ・公式モデルページ）。</li>
  <li><strong>提供段階は一般提供（GA）</strong>: 待機リスト・プレビュー等の記載は公式ブログにありません。</li>
  <li><strong>第三者情報</strong>: GitHub Changelog は2026-10-26に「GitHub Copilotで一般提供（generally available）」と告知しています（当サイトは第三者情報として扱います）。</li>
</ul>
<p class="source-note">出典: <a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">OpenAI — Pricing and availability</a>（2026-10-29取得）</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="use-h">
<h2 class="section-title" id="use-h" style="font-size:1.2rem;">使いどころと注意</h2>
<div class="tip-box">
<ul style="margin:0;padding-left:1.1rem;line-height:1.9;font-size:.9rem;">
  <li><strong>量をこなす処理に向く</strong>: 請求書の読み取り→会計ソフトへの入力、フォーム入力、動画編集など、公式ブログが挙げる「日常業務の反復」が想定用途です。</li>
  <li><strong>最難関のコーディングはSol／Astra</strong>: 公式ブログも「For the most complex coding tasks, GPT-6.1 Sol and GPT-6 Astra remain the better choice」と明記しています。</li>
  <li><strong>安全性</strong>: サイバーセキュリティ分野でPreparedness Frameworkの「Critical」しきい値に該当すると公式が記載。詳細は<a href="https://deploymentsafety.openai.com/gpt-6-1-terra" target="_blank" rel="noopener">システムカード</a>。</li>
  <li>料金・仕様は変更される可能性があります。契約前に必ず公式ページで確認してください。</li>
</ul>
</div>
<p class="source-note">関連: <a href="/gpt-6-1-sol/">GPT-6.1 Sol</a> · <a href="/pricing/">料金比較</a> · <a href="/calculator/">トークン計算機</a> · <a href="/timeline/">リリース年表</a></p>
</section>
</div>
'''

MAIN_EN = '''
<div class="container">
<div class="updated-bar" style="margin-top:2rem;"><span class="dot">●</span>Last updated: <time datetime="2026-10-29">October 29, 2026</time> | Primary sources: <a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">OpenAI launch post</a> · <a href="https://developers.openai.com/api/docs/models/gpt-6.1-terra" target="_blank" rel="noopener">official model page</a> · <a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noopener">official pricing</a></div>

<section class="section" style="padding-top:2rem;" aria-labelledby="tl-h">
<h2 class="section-title" id="tl-h" style="font-size:1.2rem;">In short</h2>
<div class="context-note" style="border-left-color:var(--c-blue);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>$1.00 input, $0.05 cached input, $5.00 output per 1M tokens</strong> (official model page). Cached input is 5% of the input rate.</li>
    <li><strong>The predecessor is GPT-5.6 Terra, not GPT-6.1 Sol.</strong> OpenAI's verbatim: "A significant step up from GPT-5.6 Terra". Sol is a separate, higher grade in the same GPT-6.1 generation.</li>
    <li><strong>1,050,000-token context and 128,000 max output tokens.</strong> Knowledge cutoff 2026-06-01 (official model page).</li>
    <li><strong>Above 272,000 input tokens the whole request is repriced at 2x input and 1.5x output.</strong> Streaming one huge document is expensive.</li>
    <li><strong>Reasoning effort: none / low / medium (default) / high / xhigh / max.</strong> Input: text and image. Output: text.</li>
    <li><strong>Available in ChatGPT Work and Codex (Plus, Pro, Enterprise, Edu) and in the API</strong> as <code>gpt-6.1-terra</code>.</li>
    <li><strong>The launch post gives no explicit date</strong> ("Starting today"); third-party coverage agrees on October 26, 2026, and we label it as such.</li>
  </ul>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="rel-h">
<h2 class="section-title" id="rel-h" style="font-size:1.2rem;">How Terra relates to GPT-6.1 Sol (official wording only)</h2>
<div class="table-wrap"><table><thead><tr><th>Question</th><th>Official wording</th><th>Our reading</th></tr></thead><tbody>
<tr><td class="model-name">Predecessor</td><td>"A significant step up from GPT-5.6 Terra"</td><td>Terra succeeds GPT-5.6 Terra</td></tr>
<tr><td class="model-name">Versus Sol</td><td>"Its standard API prices are 50% lower than those of GPT-5.6 Terra and GPT-6.1 Sol"</td><td>A separate, lower-cost grade in the same GPT-6.1 generation; not a Sol successor</td></tr>
<tr><td class="model-name">When to use which</td><td>"For the most complex coding tasks, GPT-6.1 Sol and GPT-6 Astra remain the better choice."</td><td>Sol / Astra for the hardest coding work</td></tr>
</tbody></table></div>
<p class="source-note">Source: <a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">OpenAI — Introducing GPT-6.1 Terra</a> (retrieved 2026-10-29)</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="price-h">
<h2 class="section-title" id="price-h" style="font-size:1.2rem;">Pricing (USD per 1M tokens, official model page)</h2>
<p class="section-sub">Standard is quoted as printed. Fast, Batch/Flex prices are our arithmetic from the official multipliers (2x, 50% off).</p>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>Standard</th><th>Fast (2x)</th><th>Batch / Flex (50% off)</th></tr></thead><tbody>
<tr><td class="model-name">Input</td><td class="price">$1.00</td><td>$2.00</td><td>$0.50</td></tr>
<tr><td class="model-name">Cached input</td><td class="price">$0.05</td><td>$0.10</td><td>$0.025</td></tr>
<tr><td class="model-name">Cache write (1.25x)</td><td class="price">$1.25</td><td>$2.50</td><td>$0.625</td></tr>
<tr><td class="model-name">Output</td><td class="price">$5.00</td><td>$10.00</td><td>$2.50</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">Note: cache writes cost $1.25 per 1M tokens for 30-minute retention and $2.50 for 12-hour retention. Batch and Flex are 50% lower than Standard; Fast mode is 2x; regional processing adds 10%.</p>
<p class="source-note">Source: <a href="https://developers.openai.com/api/docs/models/gpt-6.1-terra" target="_blank" rel="noopener">OpenAI — GPT-6.1 Terra</a> (retrieved 2026-10-29)</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="long-h">
<h2 class="section-title" id="long-h" style="font-size:1.2rem;">The 272K wall: one giant request costs double</h2>
<p class="section-sub">Official wording: "Prompts with more than 272K input tokens are priced at 2x input and cache rates and 1.5x output for the full request." A 1.05M window does not mean a 1.05M request is cheap.</p>
<div class="table-wrap"><table><thead><tr><th>Case</th><th>Math</th><th>Cost</th></tr></thead><tbody>
<tr><td class="model-name">300,000 input + 5,000 output in one request</td><td>$2/M x 0.3 + $7.5/M x 0.005<br><small>(2x input, 1.5x output because the request exceeds 272K)</small></td><td class="price">~$0.64</td></tr>
<tr><td class="model-name">Same content split into three 100,000-token calls</td><td>$1/M x 0.3 + output per call</td><td class="price">~$0.30</td></tr>
</tbody></table></div>
<ul style="font-size:.86rem;color:var(--c-muted);padding-left:1.3em;line-height:1.9;">
  <li><strong>Context size and request size are different things.</strong> Crossing 272K reprices the entire request.</li>
  <li><strong>Long conversations benefit from $0.05 cached input</strong> — until the request passes 272K, when cache rates double to $0.10/M.</li>
  <li>All figures are arithmetic from official multipliers; check actual billing in API responses.</li>
</ul>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="spec-h">
<h2 class="section-title" id="spec-h" style="font-size:1.2rem;">Specifications (official model page)</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">Context</div><div class="spec-value">1,050,000</div></div>
  <div class="spec-item"><div class="spec-label">Max output</div><div class="spec-value">128,000</div></div>
  <div class="spec-item"><div class="spec-label">Knowledge cutoff</div><div class="spec-value">2026-06-01</div></div>
  <div class="spec-item"><div class="spec-label">Input</div><div class="spec-value">Text, image</div></div>
  <div class="spec-item"><div class="spec-label">Output</div><div class="spec-value">Text</div></div>
  <div class="spec-item"><div class="spec-label">Reasoning effort</div><div class="spec-value">none to max</div></div>
  <div class="spec-item"><div class="spec-label">Tools</div><div class="spec-value">computer use / MCP</div></div>
  <div class="spec-item"><div class="spec-label">Snapshot</div><div class="spec-value">gpt-6.1-terra</div></div>
</div>
<p class="source-note">Source: <a href="https://developers.openai.com/api/docs/models/gpt-6.1-terra" target="_blank" rel="noopener">OpenAI — GPT-6.1 Terra</a> (retrieved 2026-10-29). Tool calling requires the Responses API.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="bench-h">
<h2 class="section-title" id="bench-h" style="font-size:1.2rem;">Benchmarks (OpenAI's own harness, OpenAI-published numbers)</h2>
<p class="section-sub">Every figure below is <strong>OpenAI's published result on its own evaluation harness</strong>, not an independent third-party verification.</p>
<div class="table-wrap"><table><thead><tr><th>Benchmark</th><th>GPT-6.1 Terra</th><th>What the post compares it to</th></tr></thead><tbody>
<tr><td class="model-name">Agents&#39; Last Exam (v1, medium effort)</td><td class="price">15 points above GPT-5.6 Terra</td><td>At about one-third the cost; at max effort ~3x more token-efficient than Claude Opus 5.5 and ~9x lower cost per task</td></tr>
<tr><td class="model-name">MMMU-Pro (visual reasoning)</td><td class="price">Beats GPT-5.6 Terra at every reasoning setting</td><td>"Nearly matches" GPT-6 Astra and GPT-6.1 Sol at much lower cost</td></tr>
<tr><td class="model-name">OSWorld 2.1 (desktop apps)</td><td class="price">Tops GPT-5.6 Terra's best score at medium effort</td><td>At "a fraction of the cost per task"</td></tr>
<tr><td class="model-name">Terminal-Bench 4.0 (max effort)</td><td class="price">50.3%</td><td>More than double GPT-5.6 Terra's published 21.5%</td></tr>
<tr><td class="model-name">Terminal-Bench-Science 0.1 (max effort)</td><td class="price">Above GPT-6.1 Sol</td><td>Within 5 points of Opus 5.5 at under one-fifth the estimated cost</td></tr>
<tr><td class="model-name">Internal error-inducing prompts (low effort)</td><td class="price">16.7% error rate</td><td>Down from 53.6% on GPT-5.6 Terra</td></tr>
</tbody></table></div>
<p class="source-note">Source: <a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">OpenAI — Introducing GPT-6.1 Terra</a> (retrieved 2026-10-29). Third-party scores (e.g. Arena) were not confirmed at publication time.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="avail-h">
<h2 class="section-title" id="avail-h" style="font-size:1.2rem;">Availability</h2>
<ul style="font-size:.9rem;padding-left:1.3em;line-height:1.9;">
  <li><strong>ChatGPT Work and Codex</strong>: available to all Plus, Pro, Enterprise and Edu users (official wording).</li>
  <li><strong>API</strong>: model ID <code>gpt-6.1-terra</code> (official post and model page).</li>
  <li><strong>Stage: general availability.</strong> The post lists no waitlist, preview or research-preview label.</li>
  <li><strong>Third-party:</strong> GitHub's changelog announced GPT-6.1 Terra as generally available in GitHub Copilot on 2026-10-26 (treated here as third-party information).</li>
</ul>
<p class="source-note">Source: <a href="https://openai.com/index/introducing-gpt-6-1-terra/" target="_blank" rel="noopener">OpenAI — Pricing and availability</a> (retrieved 2026-10-29)</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="use-h">
<h2 class="section-title" id="use-h" style="font-size:1.2rem;">Where it fits, and what to watch</h2>
<div class="tip-box">
<ul style="margin:0;padding-left:1.1rem;line-height:1.9;font-size:.9rem;">
  <li><strong>Built for high-volume work</strong>: invoice reading and data entry, form filling, video editing — the everyday tasks the launch post names.</li>
  <li><strong>Not the pick for the hardest coding</strong>: OpenAI itself says Sol and Astra "remain the better choice" there.</li>
  <li><strong>Safety</strong>: OpenAI states Terra meets the "Critical" cybersecurity threshold under its Preparedness Framework; see the <a href="https://deploymentsafety.openai.com/gpt-6-1-terra" target="_blank" rel="noopener">system card</a>.</li>
  <li>Prices and specs change; always re-check the official page before committing.</li>
</ul>
</div>
<p class="source-note">Related: <a href="/en/gpt-6-1-sol/">GPT-6.1 Sol</a> · <a href="/en/pricing/">Pricing comparison</a> · <a href="/en/calculator/">Token calculator</a> · <a href="/en/timeline/">Timeline</a></p>
</section>
</div>
'''

def write_page(tpl, out, lang):
    t = TECH[lang]
    head, rest = head_for(tpl, lang, t)
    body = body_for(rest, lang, t)
    html = head + '\n' + body.replace('__MAIN__', MAIN_JA if lang == 'ja' else MAIN_EN)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(html)
    print('wrote', out, len(html))

write_page(SITE + '/gpt-6-1-sol/index.html', SITE + '/gpt-6-1-terra/index.html', 'ja')
write_page(SITE + '/en/gpt-6-1-sol/index.html', SITE + '/en/gpt-6-1-terra/index.html', 'en')

# ---------- 4. sitemap ----------
sp = SITE + '/sitemap.xml'
sm = open(sp, encoding='utf-8').read()
for loc in ['/gpt-6-1-terra/', '/en/gpt-6-1-terra/']:
    if BASE + loc not in sm:
        sm = sm.replace('</urlset>',
            '  <url>\n    <loc>%s%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>\n</urlset>' % (BASE, loc, TODAY))
open(sp, 'w', encoding='utf-8').write(sm)
print('sitemap urls:', sm.count('<url>'))

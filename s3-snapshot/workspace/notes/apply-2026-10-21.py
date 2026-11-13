# -*- coding: utf-8 -*-
# 2026-10-21 batch: Gemini 4 Argon 個別ページ(日英)新規 / DeepSeek ③ / CTR ④ / メインビジュアル ⑤ / sitemap / models.json
import json, os, re, io

SITE = "/tmp/site"
TODAY = "2026-10-21"
log = []

def rd(p):
    with io.open(os.path.join(SITE, p), encoding="utf-8") as f:
        return f.read()

def wr(p, s):
    full = os.path.join(SITE, p)
    os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(full) else None
    with io.open(full, "w", encoding="utf-8") as f:
        f.write(s)
    log.append("wrote %s (%d bytes)" % (p, len(s)))

def split_page(p):
    h = rd(p)
    i = h.index("<body>") + len("<body>")
    j = h.index('<section class="hero')
    k = h.index("<footer")
    return h[i:j], h[k:]

ja_header, ja_footer = split_page("claude-sonnet-5-5/index.html")
en_header, en_footer = split_page("en/claude-sonnet-5-5/index.html")

GA = ('  <script async src="https://www.googletagmanager.com/gtag/js?id=G-MTH8T0ECG2"></script>\n'
      "  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-MTH8T0ECG2');</script>\n")

HERO_CSS = """  <style>
    .hero-g4{background:linear-gradient(135deg,#0a1420 0%,#10303f 50%,#0f1117 100%);border-bottom:1px solid var(--c-border);padding:3rem 1rem 2.5rem;text-align:center}
    .hero-g4 .price-flag{display:inline-block;background:rgba(124,196,255,.16);border:1px solid rgba(124,196,255,.4);color:#a8d7ff;font-size:.82rem;font-weight:700;padding:.3rem .8rem;border-radius:100px;margin-bottom:1rem}
    .hero-g4 h1{font-size:clamp(1.6rem,4.5vw,2.4rem);font-weight:800;line-height:1.2;margin-bottom:.75rem}
    .hero-g4 h1 span{color:#7cc4ff}
    .hero-g4 .lead{font-size:1.05rem;color:var(--c-muted);max-width:700px;margin:0 auto 1.5rem}
    .hero-g4 .quick-stats{display:flex;gap:1.5rem;flex-wrap:wrap;justify-content:center;margin-top:1rem}
    .hero-g4 .stat{background:var(--c-surface);border:1px solid var(--c-border);border-radius:var(--r-md);padding:.75rem 1.25rem;text-align:center}
    .hero-g4 .stat .val{font-family:var(--font-mono);font-size:1.25rem;font-weight:700;color:#7cc4ff}
    .hero-g4 .stat .lbl{font-size:.75rem;color:var(--c-muted);margin-top:.15rem}
    .spec-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem;margin-bottom:1.5rem}
    .spec-item{background:var(--c-surface);border:1px solid var(--c-border);border-radius:var(--r-md);padding:.9rem 1rem}
    .spec-item .spec-label{font-size:.75rem;color:var(--c-muted);font-weight:600;margin-bottom:.25rem}
    .spec-item .spec-value{font-family:var(--font-mono);font-size:1rem;font-weight:700}
    .context-note{background:var(--c-surface);border:1px solid var(--c-border);border-left:3px solid #7cc4ff;border-radius:var(--r-md);padding:.8rem 1rem;margin:1rem 0;font-size:.84rem;color:var(--c-muted)}
    .quote{margin:1rem 0;padding:.85rem 1rem;background:var(--c-surface2);border:1px solid var(--c-border);border-radius:var(--r-sm);font-size:.84rem;line-height:1.85;color:var(--c-muted)}
    .quote em{color:var(--c-text);font-style:italic}.quote .who{display:block;margin-top:.45rem;font-size:.76rem;color:var(--c-muted)}
    @media(max-width:640px){.hero-g4 .quick-stats{flex-direction:column;gap:.5rem}}
  </style>
"""

# ---------------------------------------------------------------- JA page
ja_head = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini 4 Argon — 料金（入力$2・出力$10／12月1日から$4・$20）と1Mコンテキスト — LLM Data Hub</title>
  <meta name="description" content="Google Gemini 4 Argon（gemini-4-argon）の料金・仕様を公式ドキュメントの逐語で整理。入力$2.00・出力$10.00（思考トークン含む）・暗黙キャッシュ$0.10はいずれも2026年11月30日までの導入価格で、12月1日から$4.00／$20.00／$0.20。無料枠なし、コンテキスト1,048,576、同期の最大出力65,536。2026年10月21日更新。">
  <link rel="canonical" href="https://llm.okamomedia.tokyo/gemini-4-argon/">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta property="og:image" content="https://llm.okamomedia.tokyo/assets/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="LLM Data Hub — LLM API pricing, token costs and model data">
  <meta name="twitter:image" content="https://llm.okamomedia.tokyo/assets/og-image.png">
  <meta name="twitter:image:alt" content="LLM Data Hub — LLM API pricing, token costs and model data">
  <link rel="alternate" hreflang="ja" href="https://llm.okamomedia.tokyo/gemini-4-argon/">
  <link rel="alternate" hreflang="en" href="https://llm.okamomedia.tokyo/en/gemini-4-argon/">
  <link rel="alternate" hreflang="x-default" href="https://llm.okamomedia.tokyo/gemini-4-argon/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://llm.okamomedia.tokyo/gemini-4-argon/">
  <meta property="og:title" content="Gemini 4 Argon — 料金と1Mコンテキスト（2026年10月21日更新）">
  <meta property="og:description" content="入力$2.00・出力$10.00（思考トークン含む）・暗黙キャッシュ$0.10は2026年11月30日までの導入価格。12月1日から$4.00／$20.00／$0.20に改定予告。無料枠なし・コンテキスト1,048,576・同期の最大出力65,536（2026年10月21日更新）。">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"Gemini 4 Argon — 料金（入力$2・出力$10／12月1日から$4・$20）と1Mコンテキスト","datePublished":"2026-10-21","dateModified":"2026-10-21","author":{"@type":"Organization","name":"okamoちゃんねる"},"publisher":{"@type":"Organization","name":"okamoちゃんねる"},"url":"https://llm.okamomedia.tokyo/gemini-4-argon/","inLanguage":"ja","description":"Gemini 4 Argon（gemini-4-argon）の料金・コンテキスト・最大出力・キャッシュ仕様をGoogle公式ドキュメントの逐語で整理。導入価格と2026年12月1日からの予告価格を書き分ける。"}</script>
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"ホーム","item":"https://llm.okamomedia.tokyo/"},{"@type":"ListItem","position":2,"name":"料金比較","item":"https://llm.okamomedia.tokyo/pricing/"},{"@type":"ListItem","position":3,"name":"Gemini 4 Argon","item":"https://llm.okamomedia.tokyo/gemini-4-argon/"}]}</script>
""" + GA + """  <link rel="stylesheet" href="/assets/style.css">
""" + HERO_CSS + """</head>
<body>
"""

ja_body = """<section class="hero-g4"><div class="container">
  <p class="price-flag">🚀 2026年10月 GA — 入力$2／出力$10は<strong>2026年11月30日までの導入価格</strong>。12月1日から$4／$20</p>
  <h1>Gemini <span>4 Argon</span></h1>
  <p class="lead">Googleのフラッグシップ推論モデル。公式は「複雑なソフトウェアエンジニアリング、深い数学・科学の問題解決、自律的なマルチステップエージェント、最大1Mトークンのlong decode」向けと説明しています。料金は<strong>期間限定の導入価格</strong>で、無料枠はありません。</p>
  <div class="quick-stats">
    <div class="stat"><div class="val">$2.00</div><div class="lbl">入力 / 1M tokens（〜11/30）</div></div>
    <div class="stat"><div class="val">$10.00</div><div class="lbl">出力 / 1M tokens（〜11/30）</div></div>
    <div class="stat"><div class="val">1,048,576</div><div class="lbl">コンテキスト（入出力統合）</div></div>
    <div class="stat"><div class="val">65,536</div><div class="lbl">最大出力（同期・既定）</div></div>
  </div>
</div></section>

<main><div class="container">
<div class="updated-bar" style="margin-top:2rem;"><span class="dot">●</span>最終更新: <time datetime="2026-10-21">2026年10月21日</time><br>出典: <a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noopener">Gemini Developer API — Pricing</a> · <a href="https://ai.google.dev/gemini-api/docs/models/gemini-4-argon" target="_blank" rel="noopener">モデルページ（gemini-4-argon）</a> · <a href="https://ai.google.dev/gemini-api/docs/changelog" target="_blank" rel="noopener">Changelog</a>（2026-10-21 に再取得） | <a href="/pricing/">料金比較</a> · <a href="/calculator/">計算機</a> · <a href="/timeline/">年表</a></div>

<section class="section" style="padding-top:2rem;" aria-labelledby="tl-h">
<h2 class="section-title" id="tl-h" style="font-size:1.2rem;">まず結論 — 押さえるべき6点</h2>
<div class="context-note" style="border-left-color:var(--c-green);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>入力$2.00・出力$10.00・キャッシュ$0.10は「導入価格」です。</strong>公式の価格欄は「$2.00 through November 30, 2026. $4.00 starting December 1, 2026.」と期間を明記しています。2026年12月1日からは入力・出力・キャッシュがそろって2倍になります。</li>
    <li><strong>無料枠はありません。</strong>逐語は「Free Tier: Not available」。</li>
    <li><strong>キャッシュは暗黙キャッシュ（Implicit caching）のみ。</strong>逐語は「Implicit caching only (explicit caching is not supported)」。自分で明示的にキャッシュを作る制御はできません。</li>
    <li><strong>コンテキストは「入出力を合わせて」1,048,576トークン。</strong>逐語は「Context window (unified input and output token limit) 1,048,576」。入力と出力の合計でこの上限に当たります。</li>
    <li><strong>出力単価には思考トークンが含まれます。</strong>逐語は「Output price (including thinking tokens)」。thinking を多く使うと出力側の課金が増えます。</li>
    <li><strong>リリース日（日単位）は公式に明記がありません。</strong>モデルページの「Latest update: October 2026」だけが日付情報なので、当サイトでは日付を作らず「2026年10月」と表記します。</li>
  </ul>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="price-h">
<h2 class="section-title" id="price-h" style="font-size:1.2rem;">料金（USD / 1Mトークン・公式価格ページ）</h2>
<p class="section-sub">Gemini API の Standard モード。<a href="/pricing/">料金比較</a>の Google セクションと同じ値です。右列は公式が「starting December 1, 2026」と書いている<strong>予告価格</strong>で、まだ適用されていません。</p>
<div class="table-wrap"><table><thead><tr><th>項目</th><th>〜2026年11月30日</th><th>2026年12月1日〜（予告）</th></tr></thead><tbody>
<tr><td class="model-name">入力（Input price）</td><td class="price">$2.00</td><td>$4.00</td></tr>
<tr><td class="model-name">出力（Output price・思考トークン含む）</td><td class="price">$10.00</td><td>$20.00</td></tr>
<tr><td class="model-name">コンテキストキャッシュ（Context caching）</td><td class="price">$0.10</td><td>$0.20</td></tr>
<tr><td class="model-name">無料枠（Free Tier）</td><td>なし（Not available）</td><td>なし（Not available）</td></tr>
</tbody></table></div>
<div class="quote">
  <em>“Input price | Not available | $2.00 through November 30, 2026. $4.00 starting December 1, 2026.”</em><br>
  <em>“Output price (including thinking tokens) | Not available | $10.00 through November 30, 2026. $20.00 starting December 1, 2026.”</em><br>
  <em>“Context caching price | Not available | $0.10 through November 30, 2026. $0.20 starting December 1, 2026. Implicit caching only (explicit caching is not supported).”</em>
  <span class="who">— Gemini Developer API「Pricing」Gemini 4 Argon / Standard（2026-10-21 確認）</span>
</div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">※ 期間限定表現は公式の価格欄に逐語で付いているものだけを載せています。Batch・Priority などの別モード単価、および長文入力の追加料金の有無は、今回 gemini-4-argon について公式価格ページ上で確認できていないため<strong>「未確認」</strong>とします（推測値は載せません）。</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="spec-h">
<h2 class="section-title" id="spec-h" style="font-size:1.2rem;">仕様（公式モデルページ）</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">モデルコード</div><div class="spec-value">gemini-4-argon</div></div>
  <div class="spec-item"><div class="spec-label">提供段階（Versions）</div><div class="spec-value">Stable</div></div>
  <div class="spec-item"><div class="spec-label">コンテキスト（入出力統合）</div><div class="spec-value">1,048,576</div></div>
  <div class="spec-item"><div class="spec-label">最大出力（同期・既定）</div><div class="spec-value">65,536</div></div>
  <div class="spec-item"><div class="spec-label">long decode 時の最大出力</div><div class="spec-value">1,048,576</div></div>
  <div class="spec-item"><div class="spec-label">Latest update（公式表記）</div><div class="spec-value">October 2026</div></div>
</div>
<div class="quote">
  <em>“Token limits | Context window (unified input and output token limit) 1,048,576 / Max output 65,536 (default synchronous) / up to 1,048,576 (with long decode)”</em>
  <span class="who">— Gemini API「Gemini 4 Argon」モデルページ（2026-10-21 確認）</span>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="use-h">
<h2 class="section-title" id="use-h" style="font-size:1.2rem;">何に強いモデルなのか（公式の位置づけ）</h2>
<div class="quote">
  <em>“Gemini 4 Argon (gemini-4-argon) is our flagship reasoning model, built for complex software engineering, deep mathematical and scientific problem solving, autonomous multi-step agents, and long decode up to 1M tokens.”</em>
  <span class="who">— Gemini API「Gemini 4 Argon」（2026-10-21 確認）</span>
</div>
<p style="font-size:.88rem;line-height:1.9;">当サイトの解釈では、①コードを書く・直す仕事、②数学／科学の難問、③ツールを何度も呼ぶエージェント、④長い出力を一気に生成する用途、の4つが想定されています。<strong>ベンチマークの数値は公式のモデルページ・価格ページに掲載が見当たらない</strong>ため、当サイトでは数値を作らず「未掲載」としています（第三者ハーネスの数字は<a href="/glossary/benchmarks/">ベンチマークの読み方</a>を参照）。</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="calc-h">
<h2 class="section-title" id="calc-h" style="font-size:1.2rem;">コストの目安（当サイトの試算）</h2>
<p class="section-sub">単価×トークン数で計算した当サイトの試算です（公式の見積もりではありません）。出力単価には思考トークンが含まれるため、thinking を多用すると出力側が増えます。</p>
<div class="table-wrap"><table><thead><tr><th>使い方</th><th>〜2026年11月30日</th><th>2026年12月1日〜（予告）</th></tr></thead><tbody>
<tr><td class="model-name">入力1M + 出力0.1M</td><td class="price">$3.00</td><td>$6.00</td></tr>
<tr><td class="model-name">入力100K + 出力20K</td><td class="price">$0.40</td><td>$0.80</td></tr>
<tr><td class="model-name">入力1M + 出力1M（long decode 級）</td><td class="price">$12.00</td><td>$24.00</td></tr>
<tr><td class="model-name">キャッシュ読込1M（暗黙キャッシュ）</td><td class="price">$0.10</td><td>$0.20</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">※ 具体的なトークン数での試算は<a href="/calculator/">トークン計算機</a>で行えます。長い文脈を毎回使い回す場合は<a href="/glossary/prompt-cache/">プロンプトキャッシュ</a>の考え方も参照してください。</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="unk-h">
<h2 class="section-title" id="unk-h" style="font-size:1.2rem;">注意点と未確認事項</h2>
<ul style="font-size:.88rem;color:var(--c-muted);padding-left:1.3em;line-height:1.9;">
  <li><strong>12月1日以降の単価は「予告」です。</strong>公式価格欄の「starting December 1, 2026」によるもので、それまでは適用されません。当サイトでは導入価格と予告価格を表で分けて書いています。</li>
  <li><strong>明示キャッシュは使えません。</strong>暗黙キャッシュのみなので、キャッシュの作成・破棄を自分で制御する設計はできません。</li>
  <li><strong>無料枠はありません。</strong>試す場合は有料の API キーが必要です。</li>
  <li><strong>未確認:</strong> Batch / Priority 等の別モード単価、長文入力の追加料金の有無、公式ベンチマーク数値、日単位のリリース日。いずれも公式ページで確認できていないため、当サイトでは数値・日付を作りません。</li>
</ul>
</section>

<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.1rem;">関連ページ</h2>
<ul style="font-size:.9rem;line-height:2;padding-left:1.3em;">
  <li><a href="/pricing/">LLM料金比較（全社・USD/1Mトークン）</a></li>
  <li><a href="/calculator/">トークン計算機（入力トークン数からコスト試算）</a></li>
  <li><a href="/timeline/">LLMリリース年表（2026年10月のGAを収録）</a></li>
  <li><a href="/gemini-3-8-flash/">Gemini 3.8 Flash（料金・キャッシュ単価）</a></li>
  <li><a href="/multimodal/">マルチモーダル対応表</a></li>
  <li><a href="/glossary/one-million-context/">1Mコンテキストとは（何が入るか・課金の違い）</a></li>
</ul>
</section>
</div></main>
"""

# ---------------------------------------------------------------- EN page
en_head = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini 4 Argon Pricing: $2/$10 Intro Rate, $4/$20 From Dec 1, 2026 | LLM Data Hub</title>
  <meta name="description" content="Google Gemini 4 Argon (gemini-4-argon) pricing and specs, quoted from the official docs: $2.00 input, $10.00 output (thinking tokens included) and $0.10 implicit-cache reads through November 30, 2026, rising to $4.00/$20.00/$0.20 on December 1. No free tier, 1,048,576-token context, 65,536 max synchronous output. Updated October 21, 2026.">
  <link rel="canonical" href="https://llm.okamomedia.tokyo/en/gemini-4-argon/">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta property="og:image" content="https://llm.okamomedia.tokyo/assets/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="LLM Data Hub — LLM API pricing, token costs and model data">
  <meta name="twitter:image" content="https://llm.okamomedia.tokyo/assets/og-image.png">
  <meta name="twitter:image:alt" content="LLM Data Hub — LLM API pricing, token costs and model data">
  <link rel="alternate" hreflang="ja" href="https://llm.okamomedia.tokyo/gemini-4-argon/">
  <link rel="alternate" hreflang="en" href="https://llm.okamomedia.tokyo/en/gemini-4-argon/">
  <link rel="alternate" hreflang="x-default" href="https://llm.okamomedia.tokyo/gemini-4-argon/">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://llm.okamomedia.tokyo/en/gemini-4-argon/">
  <meta property="og:title" content="Gemini 4 Argon Pricing and 1M Context (updated Oct 21, 2026)">
  <meta property="og:description" content="$2.00 input, $10.00 output (thinking tokens included) and $0.10 implicit caching through Nov 30, 2026; $4.00/$20.00/$0.20 from Dec 1. No free tier, 1,048,576-token context, 65,536 max synchronous output (updated Oct 21, 2026).">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"Gemini 4 Argon Pricing: $2/$10 Intro Rate, $4/$20 From Dec 1, 2026","datePublished":"2026-10-21","dateModified":"2026-10-21","author":{"@type":"Organization","name":"okamoちゃんねる"},"publisher":{"@type":"Organization","name":"okamoちゃんねる"},"url":"https://llm.okamomedia.tokyo/en/gemini-4-argon/","inLanguage":"en","description":"Gemini 4 Argon (gemini-4-argon) pricing, context window, max output and caching rules, quoted verbatim from Google's official docs, with the introductory rate separated from the December 1, 2026 forecast."}</script>
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://llm.okamomedia.tokyo/en/"},{"@type":"ListItem","position":2,"name":"Pricing","item":"https://llm.okamomedia.tokyo/en/pricing/"},{"@type":"ListItem","position":3,"name":"Gemini 4 Argon","item":"https://llm.okamomedia.tokyo/en/gemini-4-argon/"}]}</script>
""" + GA + """  <link rel="stylesheet" href="/assets/style.css">
""" + HERO_CSS + """</head>
<body>
"""

en_body = """<section class="hero-g4"><div class="container">
  <p class="price-flag">🚀 GA in October 2026 — $2 input / $10 output is an <strong>introductory rate through November 30, 2026</strong>. From December 1: $4 / $20</p>
  <h1>Gemini <span>4 Argon</span></h1>
  <p class="lead">Google's flagship reasoning model. The official listing says it is built for complex software engineering, deep mathematical and scientific problem solving, autonomous multi-step agents, and long decode up to 1M tokens. Pricing is a <strong>time-limited introductory rate</strong>, and there is no free tier.</p>
  <div class="quick-stats">
    <div class="stat"><div class="val">$2.00</div><div class="lbl">input / 1M tokens (to Nov 30)</div></div>
    <div class="stat"><div class="val">$10.00</div><div class="lbl">output / 1M tokens (to Nov 30)</div></div>
    <div class="stat"><div class="val">1,048,576</div><div class="lbl">context (input + output)</div></div>
    <div class="stat"><div class="val">65,536</div><div class="lbl">max output (synchronous)</div></div>
  </div>
</div></section>

<main><div class="container">
<div class="updated-bar" style="margin-top:2rem;"><span class="dot">●</span>Last updated: <time datetime="2026-10-21">October 21, 2026</time><br>Sources: <a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noopener">Gemini Developer API — Pricing</a> · <a href="https://ai.google.dev/gemini-api/docs/models/gemini-4-argon" target="_blank" rel="noopener">model page (gemini-4-argon)</a> · <a href="https://ai.google.dev/gemini-api/docs/changelog" target="_blank" rel="noopener">Changelog</a> (re-fetched 2026-10-21) | <a href="/en/pricing/">Pricing</a> · <a href="/en/calculator/">Calculator</a> · <a href="/en/timeline/">Timeline</a></div>

<section class="section" style="padding-top:2rem;" aria-labelledby="tl-h">
<h2 class="section-title" id="tl-h" style="font-size:1.2rem;">The short version — six things that matter</h2>
<div class="context-note" style="border-left-color:var(--c-green);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>$2.00 input, $10.00 output and $0.10 caching are introductory prices.</strong> The pricing cells read “$2.00 through November 30, 2026. $4.00 starting December 1, 2026.” On December 1, 2026 all three double.</li>
    <li><strong>No free tier.</strong> Verbatim: “Free Tier: Not available”.</li>
    <li><strong>Implicit caching only.</strong> Verbatim: “Implicit caching only (explicit caching is not supported)”. You cannot create or manage caches explicitly.</li>
    <li><strong>The context window is a unified input+output limit of 1,048,576 tokens.</strong> Verbatim: “Context window (unified input and output token limit) 1,048,576”.</li>
    <li><strong>Output pricing includes thinking tokens.</strong> Verbatim: “Output price (including thinking tokens)”. Heavy thinking raises the billed output side.</li>
    <li><strong>No day-level release date is published.</strong> The only date signal is “Latest update: October 2026” on the model page, so we write “October 2026” instead of inventing a day.</li>
  </ul>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="price-h">
<h2 class="section-title" id="price-h" style="font-size:1.2rem;">Pricing (USD per 1M tokens, official pricing page)</h2>
<p class="section-sub">Gemini API, Standard mode. Same values as the Google section of our <a href="/en/pricing/">pricing comparison</a>. The right column is the <strong>forecast</strong> the official page labels “starting December 1, 2026” — it is not in effect yet.</p>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>Through Nov 30, 2026</th><th>From Dec 1, 2026 (forecast)</th></tr></thead><tbody>
<tr><td class="model-name">Input price</td><td class="price">$2.00</td><td>$4.00</td></tr>
<tr><td class="model-name">Output price (thinking tokens included)</td><td class="price">$10.00</td><td>$20.00</td></tr>
<tr><td class="model-name">Context caching price</td><td class="price">$0.10</td><td>$0.20</td></tr>
<tr><td class="model-name">Free tier</td><td>Not available</td><td>Not available</td></tr>
</tbody></table></div>
<div class="quote">
  <em>“Input price | Not available | $2.00 through November 30, 2026. $4.00 starting December 1, 2026.”</em><br>
  <em>“Output price (including thinking tokens) | Not available | $10.00 through November 30, 2026. $20.00 starting December 1, 2026.”</em><br>
  <em>“Context caching price | Not available | $0.10 through November 30, 2026. $0.20 starting December 1, 2026. Implicit caching only (explicit caching is not supported).”</em>
  <span class="who">— Gemini Developer API “Pricing”, Gemini 4 Argon / Standard (checked 2026-10-21)</span>
</div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">Note: we only carry time-limited wording that appears verbatim in the price cells. Batch / Priority rates and any long-context surcharge for gemini-4-argon were <strong>not confirmed</strong> on the official pricing page during this check, so they are marked unconfirmed rather than estimated.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="spec-h">
<h2 class="section-title" id="spec-h" style="font-size:1.2rem;">Specs (official model page)</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">Model code</div><div class="spec-value">gemini-4-argon</div></div>
  <div class="spec-item"><div class="spec-label">Versions</div><div class="spec-value">Stable</div></div>
  <div class="spec-item"><div class="spec-label">Context window (input+output)</div><div class="spec-value">1,048,576</div></div>
  <div class="spec-item"><div class="spec-label">Max output (default synchronous)</div><div class="spec-value">65,536</div></div>
  <div class="spec-item"><div class="spec-label">Max output with long decode</div><div class="spec-value">1,048,576</div></div>
  <div class="spec-item"><div class="spec-label">Latest update (official wording)</div><div class="spec-value">October 2026</div></div>
</div>
<div class="quote">
  <em>“Token limits | Context window (unified input and output token limit) 1,048,576 / Max output 65,536 (default synchronous) / up to 1,048,576 (with long decode)”</em>
  <span class="who">— Gemini API “Gemini 4 Argon” model page (checked 2026-10-21)</span>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="use-h">
<h2 class="section-title" id="use-h" style="font-size:1.2rem;">What it is positioned for (official wording)</h2>
<div class="quote">
  <em>“Gemini 4 Argon (gemini-4-argon) is our flagship reasoning model, built for complex software engineering, deep mathematical and scientific problem solving, autonomous multi-step agents, and long decode up to 1M tokens.”</em>
  <span class="who">— Gemini API “Gemini 4 Argon” (checked 2026-10-21)</span>
</div>
<p style="font-size:.88rem;line-height:1.9;">Our reading: it targets (1) writing and fixing code, (2) hard maths and science, (3) agents that call tools repeatedly, and (4) very long generations. <strong>We found no benchmark table on the official model or pricing page</strong>, so we publish no numbers — see <a href="/en/glossary/benchmarks/">how to read benchmarks</a> for why third-party harness numbers need a label.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="calc-h">
<h2 class="section-title" id="calc-h" style="font-size:1.2rem;">Cost examples (our arithmetic)</h2>
<p class="section-sub">Unit price × token count, calculated by us — not an official quote. Output pricing includes thinking tokens, so heavy thinking increases the output side.</p>
<div class="table-wrap"><table><thead><tr><th>Usage</th><th>Through Nov 30, 2026</th><th>From Dec 1, 2026 (forecast)</th></tr></thead><tbody>
<tr><td class="model-name">1M input + 0.1M output</td><td class="price">$3.00</td><td>$6.00</td></tr>
<tr><td class="model-name">100K input + 20K output</td><td class="price">$0.40</td><td>$0.80</td></tr>
<tr><td class="model-name">1M input + 1M output (long decode)</td><td class="price">$12.00</td><td>$24.00</td></tr>
<tr><td class="model-name">1M cache reads (implicit)</td><td class="price">$0.10</td><td>$0.20</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">Use the <a href="/en/calculator/">token calculator</a> for your own token counts, and <a href="/en/glossary/prompt-cache/">prompt caching</a> for how cache billing works.</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="unk-h">
<h2 class="section-title" id="unk-h" style="font-size:1.2rem;">Caveats and what we could not confirm</h2>
<ul style="font-size:.88rem;color:var(--c-muted);padding-left:1.3em;line-height:1.9;">
  <li><strong>December 1 pricing is a forecast.</strong> It comes from “starting December 1, 2026” in the official price cells and does not apply before that date. We keep intro and forecast prices in separate columns.</li>
  <li><strong>Explicit caching is not supported</strong>, so you cannot control cache creation or eviction.</li>
  <li><strong>No free tier</strong> — a paid API key is required to try it.</li>
  <li><strong>Unconfirmed:</strong> Batch / Priority rates, any long-context surcharge, official benchmark numbers, and a day-level release date. We do not invent values or dates.</li>
</ul>
</section>

<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.1rem;">Related pages</h2>
<ul style="font-size:.9rem;line-height:2;padding-left:1.3em;">
  <li><a href="/en/pricing/">LLM API pricing comparison (all vendors, USD/1M tokens)</a></li>
  <li><a href="/en/calculator/">Token calculator</a></li>
  <li><a href="/en/timeline/">LLM release timeline (includes the October 2026 GA)</a></li>
  <li><a href="/en/gemini-3-8-flash/">Gemini 3.8 Flash pricing</a></li>
  <li><a href="/en/multimodal/">Multimodal support matrix</a></li>
  <li><a href="/en/glossary/one-million-context/">What a 1M-token context window is</a></li>
</ul>
</section>
</div></main>
"""

wr("gemini-4-argon/index.html", ja_head + ja_header + ja_body + ja_footer)
wr("en/gemini-4-argon/index.html", en_head + en_header + en_body + en_footer)

# ---------------------------------------------------------------- ④ meta rewrites (EN)
META = {
 "en/timeline/index.html": (
   "LLM Release Timeline [2025-2026]: GPT, Claude, Gemini, DeepSeek Dated | LLM Data Hub",
   "Every major LLM release date on one dated, sourced list: GPT-5/6, Claude 4/5, Gemini 3/4 (incl. Gemini 4 Argon GA), DeepSeek R1/V4, Grok 4.x, GLM 5.3, Qwen3.8 and Meta Muse Wonder. Each row names a primary source. Updated Oct 21, 2026."),
 "en/china-ai/index.html": (
   "Chinese AI Models Compared: DeepSeek, Qwen, GLM, Kimi, MiniMax | LLM Data Hub",
   "DeepSeek, Qwen (Alibaba), GLM (Zhipu/Z.ai), Kimi (Moonshot) and MiniMax side by side: flagship models, indicative per-1M-token pricing and open-weight status. Data checked against primary sources on 27 Sep 2026, with an update log."),
 "en/glossary/one-million-context/index.html": (
   "1M-Token Context Window: What Fits Inside, and What It Costs (2026) | LLM Data Hub",
   "What 1M tokens actually holds (about 750,000 English words, or 11 hours of audio) and why the same long prompt bills very differently: OpenAI doubles the whole request past 272K, Google charges every token at the higher rate past 200K, Anthropic stays standard. Checked Oct 21, 2026."),
}
import html as _html
for path, (ti, de) in META.items():
    h = rd(path)
    h2 = re.sub(r"<title>.*?</title>", "<title>%s</title>" % ti.replace("&", "&amp;"), h, count=1, flags=re.S)
    h2 = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + de.replace('"', "&quot;") + m.group(2), h2, count=1)
    h2 = re.sub(r'(<meta property="og:description" content=")[^"]*(")', lambda m: m.group(1) + de.replace('"', "&quot;") + m.group(2), h2, count=1)
    h2 = re.sub(r'("description":")[^"]*(")', lambda m: m.group(1) + de.replace('"', "&quot;") + m.group(2), h2, count=1)
    wr(path, h2)

# ---------------------------------------------------------------- ⑤ hero visual on key pages
FIG = ('<figure class="key-visual" style="margin:1.5rem 0 .5rem;">'
       '<img src="/assets/og-image.png" alt="%s" width="1200" height="630" loading="eager" decoding="async" '
       'style="width:100%%;max-width:900px;height:auto;display:block;margin:0 auto;border:1px solid var(--c-border);border-radius:var(--r-md);">'
       '</figure>')
VIS = {
 "en/timeline/index.html": "LLM Data Hub — LLM API pricing, token costs and model data (release timeline)",
 "en/china-ai/index.html": "LLM Data Hub — Chinese AI model pricing and open-weight status",
 "en/index.html": "LLM Data Hub — compare LLM API pricing per 1M tokens",
 "pricing/index.html": "LLM Data Hub — 各社LLM APIの料金をUSD/1Mトークンで比較",
 "timeline/index.html": "LLM Data Hub — LLMのリリース年表",
 "en/glossary/one-million-context/index.html": "LLM Data Hub — 1M-token context window explained",
}
for path, alt in VIS.items():
    h = rd(path)
    if "og-image.png" in h:
        log.append("skip visual (already) %s" % path); continue
    m = re.search(r'<main[^>]*>\s*(?:<div class="container"[^>]*>)?', h)
    if not m:
        log.append("NO MAIN %s" % path); continue
    if "</main>" not in h:
        log.append("NO /MAIN %s" % path); continue
    h = h[:m.end()] + "\n" + (FIG % alt.replace('"', "&quot;")) + h[m.end():]
    wr(path, h)

# ---------------------------------------------------------------- ③ DeepSeek V4.1-Flash-1017 + Search/Fetch
DS_JA = """<section class="section" style="padding-top:1.5rem;" aria-labelledby="u1017-heading">
<h2 class="section-title" id="u1017-heading" style="font-size:1.2rem;">2026-10-17 の更新 — V4.1-Flash-1017 と Web検索 / Fetch API</h2>
<div class="context-note" style="border-left-color:var(--c-green);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>モデルが更新されました（料金とAPIの呼び方は不変）。</strong>逐語: 「DeepSeek V4.1 Flash has been upgraded to DeepSeek-V4.1-Flash-1017. The official web and APP models have also been updated to the new version. The API calling method and pricing remain unchanged — simply use deepseek-flash to access the latest model.」</li>
    <li><strong>ベンチマークは公式の記載をそのまま転記します</strong>（当サイトの測定値ではありません）。HLE (w/o tools) 42.6（44.0*）／Terminal-Bench 4.0 42.3／DeepSWE v1.1 77.0／ProgramBench 29.1／NL2Repo-Bench 68.2／Automation-Bench v1.0.6 60.5／Agents' Last Exam 35.4／Apex Bench v1.1 72.1／Chartography (w/tools) 83.0／BabyVision (w/tools) 92.5／ZeroBench-main (w/tools) 51.0。*はHLEの純テキスト部分集合のみ、Terminal-Bench 4.0 は Claude Code ハーネス、DeepSWE は Mini-SWE-V2、ZeroBench-main は Pass@5 での評価。</li>
    <li><strong>「タスク実行時間と出力長を削減した」と公式が明記。</strong>逐語は「While improving performance, we also reduced the model's task runtime and output length, enabling users to complete tasks at lower cost and higher speed」。DeepSeek Harness 0.2.1-rc.1 以降への更新が推奨されています。</li>
    <li><strong>「project development capabilities が大幅に強化」という要約は公式ページに逐語で見当たりません。</strong>そのため当サイトでは採用せず、上記のベンチマーク表と「runtime／出力長の削減」という逐語の範囲で書いています。</li>
  </ul>
</div>
<h3 style="font-size:1rem;margin:1.6rem 0 .5rem;">Web検索 / Fetch API（同日公開）</h3>
<div class="table-wrap"><table><thead><tr><th>項目</th><th>公式ドキュメントの記載</th></tr></thead><tbody>
<tr><td class="model-name">Search エンドポイント</td><td><code>POST https://api.deepseek.com/v1/tools/search</code></td></tr>
<tr><td class="model-name">Fetch エンドポイント</td><td><code>POST https://api.deepseek.com/v1/tools/fetch</code></td></tr>
<tr><td class="model-name">認証</td><td>DeepSeek API と同じ Bearer 認証・JSON（<code>Authorization: Bearer &lt;API Key&gt;</code>）</td></tr>
<tr><td class="model-name">課金（Search）</td><td>$0.75 / 1,000 successful requests</td></tr>
<tr><td class="model-name">課金（Fetch）</td><td>$0.75 / 1,000 successful requests</td></tr>
<tr><td class="model-name">Search の制約</td><td>query は1〜128文字（空白のみ不可）、count は1〜50（既定10）、need_content の既定は false</td></tr>
<tr><td class="model-name">Fetch の制約</td><td>url は8192文字以内の HTTP/HTTPS。取得は対象サイトの可用性・アクセス方針に依存（逐語: “Fetching is subject to the target site's availability and access policies.”）</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">※ 課金は「成功したリクエスト」単位で、トークン課金とは別建てです。DeepSeek Harness / Claude Code / Codex 経由のサーバーサイドツール呼び出しは「currently free of charge」で、<strong>2026年11月1日 00:00（北京時間）からリクエスト課金が始まる</strong>と明記されています。料金表のトークン単価（Flash: キャッシュヒット $0.003／ミス $0.15／出力 $0.60、いずれもオフピーク）は 2026-10-21 の再取得でも変化なしでした。</p>
</section>

"""
DS_EN = """<section class="section" style="padding-top:1.5rem;" aria-labelledby="u1017-heading">
<h2 class="section-title" id="u1017-heading" style="font-size:1.2rem;">October 17, 2026 update — V4.1-Flash-1017, plus Search and Fetch APIs</h2>
<div class="context-note" style="border-left-color:var(--c-green);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>The model was updated; pricing and API calls stayed the same.</strong> Verbatim: “DeepSeek V4.1 Flash has been upgraded to DeepSeek-V4.1-Flash-1017. The official web and APP models have also been updated to the new version. The API calling method and pricing remain unchanged — simply use deepseek-flash to access the latest model.”</li>
    <li><strong>Benchmarks below are copied from the official changelog</strong> (not our measurements): HLE (w/o tools) 42.6 (44.0*) / Terminal-Bench 4.0 42.3 / DeepSWE v1.1 77.0 / ProgramBench 29.1 / NL2Repo-Bench 68.2 / Automation-Bench v1.0.6 60.5 / Agents' Last Exam 35.4 / Apex Bench v1.1 72.1 / Chartography (w/tools) 83.0 / BabyVision (w/tools) 92.5 / ZeroBench-main (w/tools) 51.0. *pure-text subset of HLE only; Terminal-Bench 4.0 was run with the Claude Code framework, DeepSWE with Mini-SWE-V2, ZeroBench-main with Pass@5.</li>
    <li><strong>DeepSeek says it also cut task runtime and output length.</strong> Verbatim: “While improving performance, we also reduced the model's task runtime and output length, enabling users to complete tasks at lower cost and higher speed”. DeepSeek Harness 0.2.1-rc.1 or later is recommended.</li>
    <li><strong>The phrasing “significantly enhanced project development capabilities” does not appear verbatim on the official page</strong>, so we do not use it; we stick to the benchmark table and the runtime/output-length wording above.</li>
  </ul>
</div>
<h3 style="font-size:1rem;margin:1.6rem 0 .5rem;">Web Search / Fetch APIs (released the same day)</h3>
<div class="table-wrap"><table><thead><tr><th>Item</th><th>Official documentation</th></tr></thead><tbody>
<tr><td class="model-name">Search endpoint</td><td><code>POST https://api.deepseek.com/v1/tools/search</code></td></tr>
<tr><td class="model-name">Fetch endpoint</td><td><code>POST https://api.deepseek.com/v1/tools/fetch</code></td></tr>
<tr><td class="model-name">Auth</td><td>Same bearer auth as the DeepSeek API, JSON body (<code>Authorization: Bearer &lt;API Key&gt;</code>)</td></tr>
<tr><td class="model-name">Billing (Search)</td><td>$0.75 per 1,000 successful requests</td></tr>
<tr><td class="model-name">Billing (Fetch)</td><td>$0.75 per 1,000 successful requests</td></tr>
<tr><td class="model-name">Search limits</td><td>query: 1–128 Unicode characters (not all whitespace); count: 1–50 (default 10); need_content defaults to false</td></tr>
<tr><td class="model-name">Fetch limits</td><td>url up to 8192 characters, HTTP or HTTPS. Availability depends on the target site (verbatim: “Fetching is subject to the target site's availability and access policies.”)</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">Billing is per successful request and is separate from token billing. Server-side tool calls made through DeepSeek Harness, Claude Code or Codex are “currently free of charge”; per-request billing starts at 00:00 Beijing time on November 1, 2026. Token prices (Flash: $0.003 cache hit / $0.15 cache miss / $0.60 output, all off-peak) were unchanged when we re-checked on 2026-10-21.</p>
</section>

"""
ANCHOR = '<section class="section" style="padding-top:1.5rem;" aria-labelledby="key-heading">'
for path, block, lang in (("deepseek-v4-1-flash/index.html", DS_JA, "ja"), ("en/deepseek-v4-1-flash/index.html", DS_EN, "en")):
    h = rd(path)
    if "u1017-heading" in h:
        log.append("skip DS (already) %s" % path); continue
    if ANCHOR not in h:
        log.append("NO ANCHOR %s" % path); continue
    h = h.replace(ANCHOR, block + ANCHOR, 1)
    h = re.sub(r'("dateModified"\s*:\s*")\d{4}-\d{2}-\d{2}(")', lambda m: m.group(1) + TODAY + m.group(2), h, count=1)
    newtime = "2026年10月21日" if lang == "ja" else "October 21, 2026"
    h = re.sub(r'<time datetime="\d{4}-\d{2}-\d{2}">[^<]*</time>', '<time datetime="%s">%s</time>' % (TODAY, newtime), h, count=1)
    wr(path, h)

# ---------------------------------------------------------------- sitemap
sm = rd("sitemap.xml")
if "gemini-4-argon" not in sm:
    add = ""
    for loc in ("https://llm.okamomedia.tokyo/gemini-4-argon/", "https://llm.okamomedia.tokyo/en/gemini-4-argon/"):
        add += "  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>\n" % (loc, TODAY)
    sm = sm.replace("</urlset>", add + "</urlset>")
    wr("sitemap.xml", sm)
else:
    log.append("sitemap already has gemini-4-argon")

# ---------------------------------------------------------------- internal links (before </main>)
LINK_JA = '<p style="font-size:.9rem;margin:1.5rem 0 0;"><strong>関連:</strong> <a href="/gemini-4-argon/">Gemini 4 Argon の料金と仕様（1Mコンテキスト・12/1からの予告価格）</a></p>\n'
LINK_EN = '<p style="font-size:.9rem;margin:1.5rem 0 0;"><strong>Related:</strong> <a href="/en/gemini-4-argon/">Gemini 4 Argon pricing and specs (1M context, Dec 1 forecast)</a></p>\n'
JA_PAGES = ["index.html", "pricing/index.html", "timeline/index.html", "calculator/index.html", "glossary/index.html"]
EN_PAGES = ["en/index.html", "en/pricing/index.html", "en/timeline/index.html", "en/calculator/index.html", "en/glossary/index.html"]
for p in JA_PAGES:
    h = rd(p)
    if "gemini-4-argon" in h:
        log.append("skip link (already) %s" % p); continue
    if "</main>" not in h:
        log.append("NO /MAIN %s" % p); continue
    wr(p, h.replace("</main>", LINK_JA + "</main>", 1))
for p in EN_PAGES:
    h = rd(p)
    if "gemini-4-argon" in h:
        log.append("skip link (already) %s" % p); continue
    if "</main>" not in h:
        log.append("NO /MAIN %s" % p); continue
    wr(p, h.replace("</main>", LINK_EN + "</main>", 1))

# llms.txt
lt = rd("llms.txt")
if "gemini-4-argon" not in lt:
    lt = lt.rstrip("\n") + "\n- Gemini 4 Argon (pricing, specs): https://llm.okamomedia.tokyo/gemini-4-argon/ | https://llm.okamomedia.tokyo/en/gemini-4-argon/\n"
    wr("llms.txt", lt)

# ---------------------------------------------------------------- calculator data: add Meta Muse Wonder
mp = "data/models.json"
d = json.loads(rd(mp))
names = [m.get("name") for m in d["models"]]
if "Meta Muse Wonder" not in names:
    d["models"].append({
        "name": "Meta Muse Wonder",
        "provider": "other",
        "label": "Muse Wonder",
        "input": 4.00,
        "output": 20.00,
        "note": "2026-10-12公開（muse-wonder-1.0）。キャッシュ入力 $0.20、1Mコンテキスト、長文プレミアムなし。Contributor モードの提供なし",
        "note_en": "Released 2026-10-12 (muse-wonder-1.0). $0.20 cache input, 1M context, no long-context surcharge, no Contributor mode",
    })
    d["updated"] = TODAY
    wr(mp, json.dumps(d, ensure_ascii=False, indent=2) + "\n")
else:
    log.append("models.json already has Muse Wonder")

# ---------------------------------------------------------------- price watch snapshot
if not os.path.exists("/workspace/cache/pricing-watch-2026-10-21.md"):
    open("/workspace/cache/pricing-watch-2026-10-21.md", "w", encoding="utf-8").write(
"""# 価格ウォッチ 2026-10-21（取得: 2026-10-21 JST / curl・Firecrawl 実フェッチ）
出典: https://openai.com/api/pricing + https://platform.openai.com/docs/pricing ,
https://www.anthropic.com/pricing , https://ai.google.dev/gemini-api/docs/pricing ,
https://api-docs.deepseek.com/quick_start/pricing , https://api-docs.deepseek.com/updates/ ,
https://api-docs.deepseek.com/guides/search/ , https://docs.z.ai/guides/overview/pricing ,
https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/
保存: cache/raw-2026-10-21/（HTML と抽出テキスト）

## 結果サマリ（10-17 スナップショットとの突き合わせ）
- OpenAI: **変化なし**。モデル別単価セット（gpt-6-astra / gpt-6.1-sol / gpt-6-luna / gpt-5.6-sol / gpt-5.6-cyber / gpt-rosalind / gpt-image 系）が 10-17 と一致。
  差分は表の列順のみ（同一数値の並び替え）。※openai.com は SPA で curl 不可 → platform.openai.com/docs/pricing を取得。
- Anthropic: **変化なし**（モデル別単価の集合が完全一致）。
- Google: **Gemini 4 Argon は変化なし**。$2.00/$10.00/$0.10（〜2026-11-30）→ $4.00/$20.00/$0.20（12/1〜）、Free tier Not available、Implicit caching only。
  Gemini 3.8 Flash も $0.75/$3.75/$0.075（〜12/31）→ $1.50/$7.50/$0.15 で変化なし。
  留意: 料金ページには「$1.00 / $5.00 / $0.05（〜11/30）→ $2.00 / $10.00 / $0.10（12/1〜）」という別テーブルも存在。
  抽出ツールが「Gemini 3.8 Flash」と誤ラベルしたため、モデル帰属は**未確定**（新モデルの行の可能性）。誤って公開しないよう、
  帰属が確定するまで当サイトには反映しない。
- DeepSeek: **トークン単価は変化なし**（Flash: cache hit $0.003/$0.006、cache miss $0.15/$0.30、output $0.60/$1.20、オフピーク/ピーク）。
  MODEL VERSION の表記が DeepSeek-V4.1-Flash → **DeepSeek-V4.1-Flash-1017** に更新（2026-10-17 付）。
  Search / Fetch API の追加課金を新規確認: 各 $0.75 / 1,000 successful requests。Harness 等経由は 2026-11-01 00:00（北京時間）から課金。
- Z.ai: **GLM 系の主要単価は変化なし**（GLM-5.3-Flash $0.15/$0.03、GLM-5.3-FlashX $0.37/$0.075、GLM-5.3 $1.4/$0.26 — 10-17 と同値）。
- Microsoft: Azure「Foundry Models Pricing」ページを取得（10-17 の azure-mai.html と同種）。MAI 系の新規掲載・単価変動は検出できず（パース不能形式のため行単位の断定は保留＝**部分未確認**）。
- Meta: 10-17 に dev.meta.ai の Muse Wonder（$4.00/$0.20/$20.00）を確認済み。今回は再取得せず（サイト掲載値は据え置き）。
- StepFun: **未確認**。platform.stepfun.com/docs/pricing 系 URL が 404 / JS 描画のみで、今日の実フェッチで単価を取得できず。

## 判定
公開中のページに訂正が必要な単価変動は **なし**（変化なしも成果として記録）。StepFun のみ持ち越し。
""")
    log.append("wrote /workspace/cache/pricing-watch-2026-10-21.md")

print("\n".join(log))

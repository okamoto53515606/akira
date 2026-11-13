# -*- coding: utf-8 -*-
"""2026-10-09: Claude Haiku 5.5 / GPT-6.1 Sol の日英個別ページを新規作成。
   ヘッダー・フッター・<style>は既存の claude-sonnet-5-5 ページから流用して表記を揃える。"""
import pathlib
S = pathlib.Path('/tmp/site')

def block(t, start, end):
    i = t.index(start); j = t.index(end, i) + len(end); return t[i:j]

ja_t = (S / 'claude-sonnet-5-5/index.html').read_text(encoding='utf-8')
en_t = (S / 'en/claude-sonnet-5-5/index.html').read_text(encoding='utf-8')
H_JA = block(ja_t, '<header class="site-header">', '</header>')
H_EN = block(en_t, '<header class="site-header">', '</header>')
F_JA = block(ja_t, '<footer class="site-footer">', '</footer>')
F_EN = block(en_t, '<footer class="site-footer">', '</footer>')
STYLE = block(ja_t, '<style>', '</style>')
GA = ('  <script async src="https://www.googletagmanager.com/gtag/js?id=G-MTH8T0ECG2"></script>\n'
      "  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-MTH8T0ECG2');</script>")

def head(lang, title, desc, path, ja_path, en_path, ogtitle, ogdesc, headline, pubdate, moddate, jdesc, crumb_name):
    base = 'https://llm.okamomedia.tokyo'
    author = 'okamoちゃんねる' if lang == 'ja' else 'okamo channel'
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="{base}{path}">
  <link rel="alternate" hreflang="ja" href="{base}{ja_path}">
  <link rel="alternate" hreflang="en" href="{base}{en_path}">
  <link rel="alternate" hreflang="x-default" href="{base}{ja_path}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{base}{path}">
  <meta property="og:title" content="{ogtitle}">
  <meta property="og:description" content="{ogdesc}">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary">
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article","headline":"{headline}","datePublished":"{pubdate}","dateModified":"{moddate}","author":{{"@type":"Organization","name":"{author}"}},"publisher":{{"@type":"Organization","name":"{author}"}},"url":"{base}{path}","inLanguage":"{lang}","description":"{jdesc}"}}</script>
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"{'ホーム' if lang=='ja' else 'Home'}","item":"{base}{'/en/' if lang=='en' else '/'}"}},{{"@type":"ListItem","position":2,"name":"{crumb_name}","item":"{base}{path}"}}]}}</script>
{GA}
  <link rel="stylesheet" href="/assets/style.css">
{STYLE}
</head>
'''

# ============================================================ Claude Haiku 5.5 (JA)
haiku_ja = head(
    'ja',
    'Claude Haiku 5.5 — Claude 5.5世代の最速・最安【$0.10/$0.50・100k超の2段階料金・1Mコンテキスト】 — LLM Data Hub',
    'Anthropic Claude Haiku 5.5の料金（入力$0.10・出力$0.50、100,000トークン超は入力$0.50・出力$2.50の2段階）・キャッシュ読込$0.01・1Mコンテキスト・128K出力・thinking（Adaptive／既定medium）を公式ドキュメントの逐語で解説。Haiku 4.5との比較、トークナイザー変更で同じ文面が約30%多くカウントされる注意点、提供5プラットフォームのモデルIDを掲載。2026年10月7日公開。2026年10月9日更新。',
    '/claude-haiku-5-5/', '/claude-haiku-5-5/', '/en/claude-haiku-5-5/',
    'Claude Haiku 5.5 — Claude 5.5世代の最速・最安【$0.10/$0.50・100k超の2段階料金】',
    '入力$0.10・出力$0.50（100kまで）／100k超は$0.50・$2.50の2段階。キャッシュ読込$0.01・1Mコンテキスト・thinking既定ON・トークナイザー変更の注意点を一次情報で整理（2026年10月9日更新）。',
    'Claude Haiku 5.5 — Claude 5.5世代の最速・最安【$0.10/$0.50・100k超の2段階料金・1Mコンテキスト】',
    '2026-10-09', '2026-10-09',
    'Claude Haiku 5.5の料金・コンテキスト・出力上限・thinking仕様・モデルIDをAnthropic公式ドキュメントの逐語で整理する解説。',
    'Claude Haiku 5.5') + f'''<body>
{H_JA}

<section class="hero-sonnet">
  <div class="container">
    <p class="price-flag">🚀 2026年10月7日公開 — Claude 5.5世代の最速・最安。Haiku 4.5（$1/$5）から大きく値下げ</p>
    <h1>Claude <span>Haiku 5.5</span></h1>
    <p class="lead">Anthropic の Claude 5.5 世代で最も速く、最も安いモデル。公式ドキュメントは用途を <strong>「classification, routing, extraction, subagent のような高ボリューム・低レイテンシー業務」</strong> と説明しています。料金は <strong>入力$0.10 / 出力$0.50</strong>（100,000トークンまで）ですが、<strong>10万トークンを超えると入力$0.50 / 出力$2.50 の2段階</strong>になります。</p>
    <div class="quick-stats">
      <div class="stat"><div class="val">$0.10</div><div class="lbl">入力 / 1M（〜100k）</div></div>
      <div class="stat"><div class="val">$0.50</div><div class="lbl">出力 / 1M（〜100k）</div></div>
      <div class="stat"><div class="val">1M</div><div class="lbl">コンテキスト</div></div>
      <div class="stat"><div class="val">Fastest</div><div class="lbl">レイテンシ（公式表）</div></div>
    </div>
  </div>
</section>

<main><div class="container">
<div class="updated-bar" style="margin-top:2rem;"><span class="dot">●</span>最終更新: <time datetime="2026-10-09">2026年10月9日</time> | 一次情報: <a href="https://platform.claude.com/docs/en/models/haiku-5-5/overview" target="_blank" rel="noopener">Claude Platform Docs — Haiku 5.5 overview</a> · <a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank" rel="noopener">公式料金ドキュメント</a> | <a href="/pricing/">料金比較</a> · <a href="/calculator/">トークン計算機</a> · <a href="/claude-sonnet-5-5/">Sonnet 5.5</a> · <a href="/claude-opus-5-5/">Opus 5.5</a></div>

<section class="section" style="padding-top:2rem;" aria-labelledby="tl-h">
<h2 class="section-title" id="tl-h" style="font-size:1.2rem;">短くまとめると</h2>
<div class="context-note" style="border-left-color:var(--c-green);">
  <ul style="margin:0;padding-left:1.1rem;line-height:1.9;">
    <li><strong>料金はHaiku 4.5の10分の1。</strong>入力$0.10・出力$0.50（100,000トークンまで）。Haiku 4.5は$1.00/$5.00でした。</li>
    <li><strong>ただし100,000トークン超は入力$0.50・出力$2.50（5倍）。</strong>公式ページの表記は「From $0.10 / $0.50（$0.10 / $0.50 から）」です。1Mコンテキストを長文入力で使い切ると単価が変わります。</li>
    <li><strong>キャッシュは入力の10%。</strong>キャッシュ読込$0.01（100k超は$0.05）、5分キャッシュ書込$0.125、1時間キャッシュ書込$0.20。</li>
    <li><strong>thinkingはAdaptiveで既定ON、既定effortは<code>medium</code>。</strong>Sonnet 5.5は<code>high</code>なので、この世代の中では控えめな設定です。</li>
    <li><strong>トークナイザーが変わっています。</strong>公式逐語で「Claude 4.7以降と同じ新しいトークナイザーを使うため、同じ文面が Haiku 4.5 より約30%多くトークンとしてカウントされる」と明記。単価の比較はトークン数込みで行ってください。</li>
    <li><strong><code>temperature</code>・<code>top_p</code>・<code>top_k</code>は非デフォルト値を渡すと400エラー。</strong>公式の逐語どおり、既存コードで指定している場合は削除が必要です。</li>
  </ul>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="price-h">
<h2 class="section-title" id="price-h" style="font-size:1.2rem;">料金（USD / 1Mトークン、公式ドキュメントより）</h2>
<p class="section-sub">Claude Platform Docs の Haiku 5.5 概要ページと公式料金ドキュメントの値をそのまま掲載しています。Haiku 4.5は当サイトの <a href="/pricing/">料金比較ページ</a> と同じ値です。</p>
<div class="table-wrap"><table><thead><tr><th>項目</th><th>Haiku 5.5（〜100k tokens）</th><th>Haiku 5.5（100k超）</th><th>Haiku 4.5（前世代）</th></tr></thead><tbody>
<tr><td class="model-name">入力</td><td class="price">$0.10</td><td class="price">$0.50</td><td>$1.00</td></tr>
<tr><td class="model-name">出力</td><td class="price">$0.50</td><td class="price">$2.50</td><td>$5.00</td></tr>
<tr><td class="model-name">キャッシュ書込（5分TTL）</td><td class="price">$0.125</td><td class="price">$0.625</td><td>$1.25</td></tr>
<tr><td class="model-name">キャッシュ書込（1時間TTL）</td><td class="price">$0.20</td><td class="price">$1.00</td><td>$2.00</td></tr>
<tr><td class="model-name">キャッシュ読込（cache hit）</td><td class="price">$0.01</td><td class="price">$0.05</td><td>$0.10</td></tr>
<tr><td class="model-name">Batch API</td><td colspan="2">入力・出力とも50%引き</td><td>50%引き</td></tr>
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);margin-top:.3rem;">※ Haiku 5.5の値はすべて公式ページの記載値です。Haiku 4.5のキャッシュ単価は公式の倍率（5分書込1.25倍・1時間書込2倍・キャッシュ読込0.1倍）から当サイトで算出しました（2026-10-09）。</p>
<p class="source-note">出典: <a href="https://platform.claude.com/docs/en/models/haiku-5-5/overview" target="_blank" rel="noopener">Claude Haiku 5.5 — overview（Pricing / Availability）</a>（2026-10-09時点）</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="tier-h">
<h2 class="section-title" id="tier-h" style="font-size:1.2rem;">「100kトークン超で単価5倍」はどこで効くか</h2>
<p class="section-sub">同じ入力でも、1回のプロンプトが10万トークンを超えた瞬間に単価が切り替わります。実際に計算すると次のとおりです。</p>
<div class="table-wrap"><table><thead><tr><th>ケース</th><th>Haiku 5.5</th><th>Claude Sonnet 5.5</th></tr></thead><tbody>
<tr><td class="model-name">200,000トークン入力＋10,000トークン出力</td><td class="price">$0.125<br><small>（入力$0.50/M×0.2＋出力$2.50/M×0.01）</small></td><td class="price">$0.50<br><small>（入力$2/M×0.2＋出力$10/M×0.01）</small></td></tr>
<tr><td class="model-name">50,000トークン入力＋5,000トークン出力</td><td class="price">$0.0075<br><small>（入力$0.10/M×0.05＋出力$0.50/M×0.005）</small></td><td class="price">$0.15<br><small>（入力$2/M×0.05＋出力$10/M×0.005）</small></td></tr>
</tbody></table></div>
<ul style="font-size:.86rem;color:var(--c-muted);padding-left:1.3em;line-height:1.9;">
  <li><strong>100k以下なら単価はSonnet 5.5の20分の1。</strong>分類・ルーティング・抽出のように短い入出力を大量に回す用途では、桁が変わります。</li>
  <li><strong>100k超でもSonnet 5.5の4分の1。</strong>「10万トークンを超えると高い」のではなく、<strong>「100kまでが極端に安い」</strong>と捉えるのが正確です。</li>
  <li><strong>長い前置きの使い回しはキャッシュ読込が効きます。</strong>100k以下なら$0.01/M（Sonnet 5.5は$0.10/M）。RAGやエージェントのシステムプロンプト固定に向きます。</li>
</ul>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="mig-h">
<h2 class="section-title" id="mig-h" style="font-size:1.2rem;">Haiku 4.5からの移行で見落としやすい3点</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">① トークン数が約30%増える</div><div class="spec-value">同じ日本語・英語の文面でも、新しいトークナイザーでは Haiku 4.5 より約30%多くカウントされます。単価が10分の1でも、実効コストは概算で<strong>約7.7分の1</strong>（1 ÷ (0.1 × 1.3)）。「10分の1になった」とだけ見積もると金額がずれます。</div></div>
  <div class="spec-item"><div class="spec-label">② thinkingが既定ON</div><div class="spec-value">Adaptive thinking が既定で有効、既定effortは<code>medium</code>です。出力トークンが増える前提で見積もり、必要なら <code>effort</code> で深さを調整してください。</div></div>
  <div class="spec-item"><div class="spec-label">③ 温度パラメータが使えない</div><div class="spec-value">公式逐語: <em>“Omit temperature, top_p, and top_k, since a non-default value for any of them returns a 400 error.”</em> 既存のHaiku 4.5実装で明示している場合は削除が必要です。</div></div>
  <div class="spec-item"><div class="spec-label">④ thinking blocksの扱い</div><div class="spec-value">公式逐語: <em>“Its thinking blocks work only in the account that produced them, or in an account linked to it.”</em> マルチアカウント構成では、思考ブロックの引き継ぎができません。</div></div>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="spec-h">
<h2 class="section-title" id="spec-h" style="font-size:1.2rem;">仕様とモデルID</h2>
<div class="table-wrap"><table><thead><tr><th>項目</th><th>値（公式ページ）</th></tr></thead><tbody>
<tr><td class="model-name">コンテキスト</td><td>1Mトークン</td></tr>
<tr><td class="model-name">最大出力</td><td>128Kトークン（Batch APIではベータヘッダ <code>output-300k-2026-03-24</code> で300Kトークン）</td></tr>
<tr><td class="model-name">thinking</td><td>Adaptive（既定ON）／既定effort <code>medium</code></td></tr>
<tr><td class="model-name">レイテンシ</td><td>Fastest（公式比較表）</td></tr>
<tr><td class="model-name">入出力</td><td>テキスト・画像 → テキスト</td></tr>
<tr><td class="model-name">知識カットオフ</td><td>Jun 2026（学習データも Jun 2026）</td></tr>
<tr><td class="model-name">状態</td><td>Active (latest)。<strong>退役予定は2027年10月7日以降</strong>（公式 Availability）</td></tr>
</tbody></table></div>
<div class="table-wrap" style="margin-top:1rem;"><table><thead><tr><th>プラットフォーム</th><th>モデルID</th></tr></thead><tbody>
<tr><td class="model-name">Claude API</td><td><code>claude-haiku-5-5</code></td></tr>
<tr><td class="model-name">Amazon Bedrock</td><td><code>anthropic.claude-haiku-5-5</code></td></tr>
<tr><td class="model-name">Google Cloud (Vertex AI)</td><td><code>claude-haiku-5-5</code></td></tr>
<tr><td class="model-name">Microsoft Foundry</td><td><code>claude-haiku-5-5</code></td></tr>
<tr><td class="model-name">Claude Platform on AWS</td><td><code>claude-haiku-5-5</code></td></tr>
</tbody></table></div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="q-h">
<h2 class="section-title" id="q-h" style="font-size:1.2rem;">公式ドキュメントの逐語（抜粋）</h2>
<div class="quote">
  <em>“Claude Haiku 5.5 is built for high-volume, latency-sensitive work such as classification, routing, extraction, and subagent tasks. It supports adaptive thinking with the effort parameter, a 1M token context window, and up to 128k output tokens. It uses the same newer tokenizer as Claude 4.7 and later models, so the same text counts as approximately 30% more tokens than on Claude Haiku 4.5.”</em>
  <span class="who">— Claude Platform Docs, “Claude Haiku 5.5 — overview”（2026-10-09確認）</span>
</div>
<p class="source-note">料金・仕様・モデルIDはいずれも上記公式ページの記載値です。当サイトは公式に記載のない数値（非公開のベンチマーク等）を推測で補いません。</p>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="use-h">
<h2 class="section-title" id="use-h" style="font-size:1.2rem;">向く用途・向かない用途</h2>
<div class="spec-grid">
  <div class="spec-item"><div class="spec-label">向く: 大量の分類・抽出・ルーティング</div><div class="spec-value">1件あたりの入出力が短く、件数が多い処理。100k以下なら入力$0.10/Mで、Sonnet 5.5（$2/M）の20分の1です。</div></div>
  <div class="spec-item"><div class="spec-label">向く: サブエージェント・前処理</div><div class="spec-value">公式が用途として挙げている subagent tasks そのもの。上位モデルの前段に置く構成と相性が良いです。</div></div>
  <div class="spec-item"><div class="spec-label">向く: レイテンシー重視の対話</div><div class="spec-value">公式比較表でレイテンシは Fastest。応答速度が体感に直結する用途で有利です。</div></div>
  <div class="spec-item"><div class="spec-label">向かない: 契約・監査に関わる判断</div><div class="spec-value">データ保持・運営者アクセス・学習利用の条件はモデルページに書かれていません。<a href="/glossary/zero-operator-access/">ZOA</a>・<a href="/glossary/zero-data-retention/">ZDR</a>・<a href="/glossary/four-data-requirements/">4つの要件</a>から確認してください。</div></div>
  <div class="spec-item"><div class="spec-label">向かない: 温度パラメータ前提の実装</div><div class="spec-value">Haiku 5.5では<code>temperature</code>等の非デフォルト値が400エラーになります。既存の生成パイプラインをそのまま移植する前に確認してください。</div></div>
  <div class="spec-item"><div class="spec-label">要検討: 100k超の長文を1回で流す用途</div><div class="spec-value">入力$0.50/M・出力$2.50/Mに切り替わります。長文要約のように入力を丸ごと渡す処理は、Sonnet 5.5と総額で比較してください。</div></div>
</div>
</section>

<section class="section" style="padding-top:0;" aria-labelledby="rel-h">
<h2 class="section-title" id="rel-h" style="font-size:1.2rem;">関連ページ</h2>
<ul style="font-size:.88rem;line-height:2;">
  <li><a href="/claude-sonnet-5-5/">Claude Sonnet 5.5</a> — Claude 5.5世代のバランス型（$2/$10・1Mコンテキスト）</li>
  <li><a href="/claude-opus-5-5/">Claude Opus 5.5</a> — 同世代の上位モデル（$4/$20・thinking無効化不可）</li>
  <li><a href="/pricing/">主要LLM API 料金比較</a> — 各社の公式料金を1ページで比較</li>
  <li><a href="/calculator/">トークン料金計算機</a> — 入力・出力トークン数から実額を計算</li>
  <li><a href="/timeline/">リリース年表</a> — Claude Haiku 5.5 の公開日を含む時系列</li>
  <li><a href="/glossary/prompt-cache/">プロンプトキャッシュとは</a> — キャッシュ読込$0.01が効く条件</li>
</ul>
</section>

<div class="tip-box" style="border-left-color:var(--c-yellow);">
  <h3 style="font-size:1rem;margin:0 0 .5rem;">⚠️ 免責事項</h3>
  <ul style="font-size:.84rem;color:var(--c-muted);line-height:1.9;">
    <li>料金・仕様は2026-10-09時点で Claude Platform Docs の公式ページ（Haiku 5.5 overview・公式料金ドキュメント）を確認したものです。改定・キャンペーンで変わることがあります。</li>
    <li>Haiku 4.5のキャッシュ単価は公式倍率から当サイトが算出した参考値です。</li>
    <li>本サイトは情報提供目的であり、特定プロバイダーの推奨・代理ではありません。</li>
  </ul>
</div>
</div></main>
{F_JA}
</body>
</html>
'''
(S / 'claude-haiku-5-5').mkdir(parents=True, exist_ok=True)
(S / 'claude-haiku-5-5/index.html').write_text(haiku_ja, encoding='utf-8')
print("wrote claude-haiku-5-5/index.html", len(haiku_ja))

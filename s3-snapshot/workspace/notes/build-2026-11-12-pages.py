# -*- coding: utf-8 -*-
import os, re, json
SITE='/tmp/site'; TODAY='2026-11-12'
BASE='https://llm.okamomedia.tokyo'
CSS = open(SITE+'/prompt-cache-pricing/index.html',encoding='utf-8').read()
m=re.search(r'<style>.*?</style>',CSS,re.S); STYLE=m.group(0)

HDR_JA='<header class="site-header"><div class="header-inner"><a href="/" class="site-logo"><span class="logo-icon">\u26a1</span>LLM Data Hub</a><nav aria-label="\u30e1\u30a4\u30f3\u30ca\u30d3\u30b2\u30fc\u30b7\u30e7\u30f3"><a href="/" class="nav-link">\u30db\u30fc\u30e0</a><a href="/pricing/" class="nav-link">\u6599\u91d1\u6bd4\u8f03</a><a href="/calculator/" class="nav-link">\u30c8\u30fc\u30af\u30f3\u8a08\u7b97\u6a5f</a><a href="/timeline/" class="nav-link">\u30ea\u30ea\u30fc\u30b9\u5e74\u8868</a><a href="/china-ai/" class="nav-link">\u4e2d\u56fdAI</a><a href="/multimodal/" class="nav-link">\u30de\u30eb\u30c1\u30e2\u30fc\u30c0\u30eb</a><a href="/mai/" class="nav-link">MS AI (MAI)</a><a href="/glossary/" class="nav-link">\u7528\u8a9e\u8aac\u660e</a></nav></div></header>'
HDR_EN='<header class="site-header"><div class="header-inner"><a href="/en/" class="site-logo"><span class="logo-icon">\u26a1</span>LLM Data Hub</a><nav aria-label="Main navigation"><a href="/en/" class="nav-link">Home</a><a href="/en/pricing/" class="nav-link">Pricing</a><a href="/en/calculator/" class="nav-link">Token calculator</a><a href="/en/timeline/" class="nav-link">Timeline</a><a href="/en/china-ai/" class="nav-link">China AI</a><a href="/en/multimodal/" class="nav-link">Multimodal</a><a href="/en/mai/" class="nav-link">MS AI (MAI)</a><a href="/en/glossary/" class="nav-link">Glossary</a></nav></div></header>'
FTR_JA='<footer class="site-footer"><div class="footer-inner"><div class="footer-brand"><strong>\u26a1 LLM Data Hub</strong><p>\u904b\u55b6: okamo\u3061\u3083\u3093\u306d\u308b</p><p><a href="/">\u30db\u30fc\u30e0</a> \u00b7 <a href="/pricing/">\u6599\u91d1\u6bd4\u8f03</a> \u00b7 <a href="/calculator/">\u8a08\u7b97\u6a5f</a> \u00b7 <a href="/timeline/">\u5e74\u8868</a> \u00b7 <a href="/glossary/">\u7528\u8a9e\u8aac\u660e</a> \u00b7 <a href="/gpt-6/">GPT-6 Astra</a></p></div><p class="footer-disclaimer">\u26a0\ufe0f \u6599\u91d1\u30fb\u4ed5\u69d8\u306f\u4e88\u544a\u306a\u304f\u5909\u52d5\u3057\u307e\u3059\u3002\u5951\u7d04\u524d\u306b\u5fc5\u305a\u5404\u793e\u516c\u5f0f\u30da\u30fc\u30b8\u3067\u3054\u78ba\u8a8d\u304f\u3060\u3055\u3044\u3002\u672c\u30b5\u30a4\u30c8\u306f\u5404\u793e\u3068\u63d0\u643a\u3057\u3066\u3044\u307e\u305b\u3093\u3002</p></div></footer>'
FTR_EN='<footer class="site-footer"><div class="footer-inner"><div class="footer-brand"><strong>\u26a1 LLM Data Hub</strong><p>Operated by okamo channel</p><p><a href="/en/">Home</a> \u00b7 <a href="/en/pricing/">Pricing</a> \u00b7 <a href="/en/calculator/">Calculator</a> \u00b7 <a href="/en/timeline/">Timeline</a> \u00b7 <a href="/en/glossary/">Glossary</a></p></div><p class="footer-disclaimer">\u26a0\ufe0f Prices and specs change without notice. Always confirm on the provider\u2019s own pricing page before you commit. We are not affiliated with any provider.</p></div></footer>'
GA='<script async src="https://www.googletagmanager.com/gtag/js?id=G-MTH8T0ECG2"></script>\n  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag(\'js\',new Date());gtag(\'config\',\'G-MTH8T0ECG2\');</script>'

# ============ JA page ============
T_JA='Batch API割引の横断比較【2026年11月版】OpenAI・Anthropic・Google・xAI・Moonshot — LLM Data Hub'
D_JA='Batch APIの割引率を横断比較。OpenAI・Anthropic・Googleは50%減、xAIは20%減、Moonshotは標準の60%、DeepSeekはオフピーク半額。完了までの目安・結果の保持期間・件数の上限を各社公式の逐語から整理（2026年11月12日確認）。'
URL_JA=BASE+'/batch-api-pricing/'

rows_ja = [
 ('OpenAI<br><small>Batch API</small>',
  'モデル別の対応一覧は今回の取得範囲では<strong>未確認</strong>',
  '<strong>50%減</strong><br><small>入力・出力とも</small>',
  'GPT-6.1 Terra 入力$1.00／出力$5.00',
  '$0.50／$2.50<br><small>（計算値）</small>',
  '24時間以内（多くはそれより速い）',
  '出力ファイルは完了後30日で自動削除',
  '1バッチ5万リクエスト／入力ファイル200MB／毎時2,000バッチ',
  '<a href="https://developers.openai.com/api/docs/guides/batch" target="_blank" rel="noopener">公式ガイド</a>（11-12）'),
 ('Anthropic<br><small>Message Batches API</small>',
  'Fable 5.2／Mythos 5.2／Opus 5.5／Sonnet 5.5／Haiku 5.5／Fable 5.1 ほか（下の表）',
  '<strong>50%減</strong><br><small>入力・出力とも</small>',
  'Fable 5.2 入力$8.00／出力$40.00',
  '$4.00／$20.00<br><small>（入力は公式表・出力は50%から計算）</small>',
  '未確認', '未確認', '未確認',
  '<a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank" rel="noopener">料金ドキュメント</a>（11-12）'),
 ('Google<br><small>Gemini Batch API</small>',
  'モデル別一覧は<strong>未確認</strong>。Gemini 4 Carbon は「Batch API isn&#39;t supported」',
  '<strong>50%減</strong>',
  'Gemini 4 Argon 入力$2.00／出力$10.00（11/30まで）',
  '$1.00／$5.00<br><small>（計算値）</small>',
  '目標24時間（多くの場合はそれより速い）',
  '未確認',
  '入力ファイル最大2GB／インラインは20MB未満',
  '<a href="https://ai.google.dev/gemini-api/docs/batch-mode" target="_blank" rel="noopener">Batch API</a>（11-12）'),
 ('xAI<br><small>Batch API</small>',
  'grok-4.7／4.6／4.5／4.3／4.20系（0309）',
  '<strong>20%減</strong><br><small>モデルにより異なる。表に無いモデルは割引なし</small>',
  'grok-4.7 入力$2.00／出力$6.00',
  '$1.60／$4.80<br><small>（計算値）</small>',
  '多くは24時間以内',
  '未確認',
  'レート制限にカウントされない（件数の上限値は未確認）',
  '<a href="https://docs.x.ai/developers/pricing" target="_blank" rel="noopener">API Pricing</a>（11-12）'),
 ('Moonshot<br><small>Batch API</small>',
  'kimi-k3.1-pro／kimi-k3',
  '<strong>標準の60%</strong><br><small>（40%減）</small>',
  'kimi-k3.1-pro 入力$2.00／出力$10.00',
  '$1.20／$6.00<br><small>（計算値）</small>',
  '未確認', '未確認', '未確認',
  '<a href="https://platform.kimi.ai/docs/pricing/chat" target="_blank" rel="noopener">Kimi 料金</a>（11-12）'),
 ('DeepSeek<br><small>Batch APIは確認できず</small>',
  'deepseek-flash／deepseek-v4-pro',
  '<strong>オフピークはピークの半額</strong><br><small>（50%減・時間帯割引）</small>',
  'deepseek-flash 入力$0.30／出力$1.20（ピーク）',
  '$0.15／$0.60<br><small>（オフピーク）</small>',
  '—（非同期バッチではない）', '—',
  'ピーク時間 01:00–04:00／06:00–10:00 UTC 月〜金',
  '<a href="https://api-docs.deepseek.com/quick_start/pricing" target="_blank" rel="noopener">Models &amp; Pricing</a>（11-12）'),
]
tbl_ja='\n'.join('<tr>'+''.join('<td>%s</td>'%c for c in r)+'</tr>' for r in rows_ja)

anth_rows = [
 ('Claude Fable 5.2','$4 / MTok'),('Claude Mythos 5.2','$4 / MTok'),
 ('Claude Opus 5.5','$2 / MTok'),('Claude Sonnet 5.5','$1 / MTok'),
 ('Claude Haiku 5.5','$0.05 / MTok（10万トークン以下）／$0.25 / MTok（超過）'),
 ('Claude Fable 5.1','$5 / MTok'),('Claude Mythos 5.1','$5 / MTok'),('Claude Fable 5','$5 / MTok'),
 ('Claude Opus 5','$2.50 / MTok'),('Claude Opus 4.8','$2.50 / MTok'),
 ('Claude Sonnet 5','$1 / MTok'),('Claude Sonnet 4.6 / 4.5','$1.50 / MTok'),
 ('Claude Haiku 4.5','$0.50 / MTok'),
]
anth_ja='\n'.join('<tr><td class="model-name">%s</td><td class="price">%s</td></tr>'%r for r in anth_rows)

unconf_ja = [
 ('Anthropicの完了までの目安・結果の保持期間・件数の上限','<strong>未確認</strong>','今回取得した料金ドキュメントには、Batchの締切・保持期間・件数上限の逐語がありませんでした（無いとは断定していません）。'),
 ('OpenAIの対応モデル一覧','<strong>未確認</strong>','Batchガイドには割引率・締切・上限の逐語はありますが、対応モデルの列挙は今回取得できていません。'),
 ('Googleの対象モデル一覧・結果の保持期間','<strong>未確認</strong>','Batch APIドキュメントから逐語で取れたのは割引率・目標時間・ファイル上限までです。'),
 ('xAIの件数上限・結果の保持期間','<strong>未確認</strong>','API Pricing には割引率と「多くは24時間以内」の記述までが確認できました。'),
 ('Moonshotの締切・保持期間・上限','<strong>未確認</strong>','料金ページの逐語は「標準価格の60%」までです。Batchの詳細は別ページにあるため次回追記します。'),
]
unconf_ja='\n'.join('<tr><td class="model-name">%s</td><td>%s</td><td>%s</td></tr>'%r for r in unconf_ja)

body_ja = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{T_JA}</title>
  <meta name="description" content="{D_JA}">
  <link rel="canonical" href="{URL_JA}">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta property="og:image" content="{BASE}/assets/og/ja-batch-api-pricing.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Batch API割引の横断比較：OpenAI・Anthropic・Googleは50%減、xAIは20%減、Moonshotは標準の60%（LLM Data Hub）">
  <meta name="twitter:image" content="{BASE}/assets/og/ja-batch-api-pricing.png">
  <meta name="twitter:image:alt" content="Batch API割引の横断比較：OpenAI・Anthropic・Googleは50%減、xAIは20%減、Moonshotは標準の60%（LLM Data Hub）">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{URL_JA}">
  <meta property="og:title" content="{T_JA}">
  <meta property="og:description" content="{D_JA}">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{{"@context": "https://schema.org", "@type": "Article", "headline": "Batch API割引の横断比較【2026年11月版】", "datePublished": "{TODAY}", "dateModified": "{TODAY}", "author": {{"@type": "Organization", "name": "LLM Data Hub"}}, "publisher": {{"@type": "Organization", "name": "okamoちゃんねる"}}, "url": "{URL_JA}", "inLanguage": "ja", "isAccessibleForFree": true, "description": "{D_JA}"}}</script>
  {GA}
  <link rel="stylesheet" href="/assets/style.css">
  {STYLE}
  <link rel="alternate" hreflang="ja" href="{URL_JA}">
  <link rel="alternate" hreflang="en" href="{BASE}/en/batch-api-pricing/">
  <link rel="alternate" hreflang="x-default" href="{URL_JA}"></head>
<body>
{HDR_JA}
<main>
<div class="container" style="padding-top:2rem;">
<h1 class="section-title" style="font-size:1.6rem;">Batch API割引の横断比較 <span style="font-size:1rem;font-weight:500;color:var(--c-muted);">【2026年11月版】</span></h1>
<p class="section-sub" style="max-width:760px;">大量のリクエストを<strong>非同期でまとめて流すと、単価がどこまで下がるか</strong>を1つの表にまとめました。リアルタイム性を捨てる代わりに単価を下げる仕組みなので、<strong>「待てる処理かどうか」が導入判断の分かれ目</strong>になります。通常単価は<a href="/pricing/">LLM API料金比較</a>、同じ前置きを使い回すときの単価は<a href="/prompt-cache-pricing/">プロンプトキャッシュ料金の横断比較</a>を参照してください。</p>
<div class="updated-bar"><span class="dot">●</span>最終更新: <time datetime="{TODAY}">2026年11月12日</time> | 各社公式ページを2026-11-12に取得し、引用は逐語ベース。割引率を通常単価に当てはめた金額は「計算値」と明記しています。</div>
<section class="section" style="padding-top:1rem;">
<h2 class="section-title" style="font-size:1.15rem;">先に押さえる3点</h2>
<ul style="max-width:820px;line-height:1.9;">
<li><strong>主要3社は「50%減」で並んでいる。</strong>OpenAI・Anthropic・Googleはいずれも通常比50%減。割引率だけを見れば横並びなので、<strong>差がつくのは締切・保持期間・上限のほう</strong>です。</li>
<li><strong>割引率はモデル単位で決まる会社がある。</strong>xAIはモデルごとに割引率が異なり、表に載っていないモデルは「割引なし」。Moonshotは「標準の60%」で、50%減より浅い設定です。</li>
<li><strong>Batchとキャッシュは併用できる。</strong>Anthropicは公式に「Batch API and prompt caching discounts can be combined.」と明記しています。同じ前置きを何度も流す夜間バッチなら、<strong>キャッシュ＋Batchの二段構え</strong>が最も安くなります。</li>
</ul>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">Batch割引の一覧（USD / 100万トークン）</h2>
<div class="table-wrap"><table>
<thead><tr><th>提供元</th><th>対象モデル</th><th>割引率（通常比）</th><th>通常単価（入力／出力）</th><th>Batch単価（入力／出力）</th><th>完了までの目安</th><th>結果の保持</th><th>件数・上限</th><th>出典（取得日）</th></tr></thead>
<tbody>
{tbl_ja}
</tbody></table></div>
<p style="font-size:.78rem;color:var(--c-muted);max-width:860px;">※ Batch単価の「計算値」は、公式に明記された割引率を当サイトが通常単価に当てはめた金額です（OpenAI・Googleは50%、xAIは20%、Moonshotは標準の60%）。Anthropicの入力側は公式のBatch表に単価が明記されており、出力側は「50 percent discount on both input and output tokens」から計算しています。※ 通常単価は2026-11-12時点の各社公式料金ページによります（Gemini 4 Argonは11/30までの導入価格）。</p>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">Anthropicのモデル別Batch単価（入力・公式のBatch表の逐語）</h2>
<p style="max-width:820px;line-height:1.9;">Anthropicは料金ドキュメントにモデル別のBatch単価（入力）を明記しています。50%減の結果がそのまま表になっているので、<strong>モデルごとの絶対額</strong>をここで確認できます。</p>
<div class="table-wrap"><table>
<thead><tr><th>モデル</th><th>Batch 入力単価</th></tr></thead>
<tbody>
{anth_ja}
</tbody></table></div>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">どういう時に得か（夜間バッチの分類処理を例に）</h2>
<p style="max-width:820px;line-height:1.9;">たとえば<strong>問い合わせログ20万件を、夜間に「問い合わせ種別」へ分類する</strong>処理を考えます。1件あたり入力1,500トークン・出力200トークンとすると、合計は入力3億トークン・出力4,000万トークンです。</p>
<div class="table-wrap"><table>
<thead><tr><th>モデル</th><th>通常APIで処理</th><th>Batchで処理</th><th>差額</th></tr></thead>
<tbody>
<tr><td class="model-name">GPT-6.1 Terra（$1.00／$5.00）</td><td class="price">$300 + $200 = $500</td><td class="price">$250</td><td class="price">−$250</td></tr>
<tr><td class="model-name">Gemini 4 Argon（$2.00／$10.00）</td><td class="price">$600 + $400 = $1,000</td><td class="price">$500</td><td class="price">−$500</td></tr>
<tr><td class="model-name">Kimi K3.1 Pro（$2.00／$10.00）</td><td class="price">$600 + $400 = $1,000</td><td class="price">$600（標準の60%）</td><td class="price">−$400</td></tr>
</tbody></table></div>
<p style="max-width:820px;line-height:1.9;">この処理は<strong>翌朝までに結果が揃っていればよい</strong>ので、Batchの締切（多くは24時間以内）に収まります。逆に、ユーザーの投稿をその場で判定して画面に返す用途は、24時間待てないためBatchに向きません。<strong>「日次で回る集計・分類・抽出・埋め込み生成」はBatchの典型例</strong>で、「対話・エージェントのループ内」は通常APIのまま、という切り分けが実務的です。</p>
<p style="max-width:820px;line-height:1.9;">なお、同じ前置き（分類の指示文やカテゴリ定義）を全件に付けるなら、<a href="/prompt-cache-pricing/">プロンプトキャッシュ</a>と併用すると入力側がさらに下がります。Anthropicは併用可を明記しており、OpenAI・GoogleもキャッシュとBatchは別の割引軸として扱われています（併用時の適用順序は各社ドキュメントでご確認ください）。</p>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">Batchは「レイテンシと締切」のトレードオフ</h2>
<p style="max-width:820px;line-height:1.9;">Batch APIは<strong>非同期</strong>です。リクエストを投入するとジョブIDが返り、結果は後から取りに行く形になります。OpenAIは「Each batch completes within 24 hours (and often more quickly)」とし、完了ウィンドウは24時間のみ。Googleは「The target turnaround time is 24 hours, but in majority of cases, it is much quicker.」、xAIは「most completing within 24 hours」と書いています。<strong>「24時間以内に終わる」ことは保証されますが、「何時間で終わるか」は保証されません</strong>。日中の業務に組み込むなら、前日夜に投入して翌朝回収する設計が安全です。</p>
<p style="max-width:820px;line-height:1.9;">締切を過ぎたリクエストの扱いも会社ごとに違います。OpenAIは期限切れをエラーファイルに書き出し（<code>batch_expired</code>）、<strong>成功分だけを受け取る</strong>形になります。つまり「全件そろわない可能性」を前提に、再実行の設計を用意しておく必要があります。レート制限の扱いも別枠で、xAIは「Requests don't count towards rate limits」と明記しています。<strong>安くなる代わりに、締切・部分失敗・回収の運用を自分で持つ</strong>のがBatchだと考えてください。</p>
<div class="read-box"><strong>結果の保持期間は意外に短い。</strong>OpenAIは「The output file will automatically be deleted 30 days after the batch is complete.」と明記しています。<strong>結果はダウンロードしたら自分のストレージへ移す</strong>のが基本です。他社の保持期間は本ページの表では「未確認」としており、確認でき次第追記します。</div>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">当サイトで確認できていない項目（推測はしていません）</h2>
<div class="table-wrap"><table><thead><tr><th>項目</th><th>状態</th><th>補足</th></tr></thead><tbody>
{unconf_ja}
</tbody></table></div>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">出典（すべて2026-11-12取得）</h2>
<ul style="line-height:1.9;max-width:820px;">
<li>OpenAI Batch API: <a href="https://developers.openai.com/api/docs/guides/batch" target="_blank" rel="noopener">developers.openai.com/api/docs/guides/batch</a>（「50% cost discount compared to synchronous APIs」「Each batch completes within 24 hours」「The output file will automatically be deleted 30 days after the batch is complete.」「A single batch may include up to 50,000 requests, and a batch input file can be up to 200 MB in size.」）</li>
<li>OpenAI 料金: <a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noopener">developers.openai.com/api/docs/pricing</a>（GPT-6.1 Terra 入力$1.00／出力$5.00）</li>
<li>Anthropic Pricing: <a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank" rel="noopener">platform.claude.com/docs/en/about-claude/pricing</a>（「The Batch API allows asynchronous processing of large volumes of requests with a 50 percent discount on both input and output tokens.」「Batch API and prompt caching discounts can be combined.」＋モデル別Batch単価表）</li>
<li>Anthropic Claude Fable 5.2: <a href="https://www.anthropic.com/claude-fable-and-mythos-5-2" target="_blank" rel="noopener">anthropic.com/claude-fable-and-mythos-5-2</a>（通常$8／$40、fast mode $16／$80）</li>
<li>Google Gemini Batch API: <a href="https://ai.google.dev/gemini-api/docs/batch-mode" target="_blank" rel="noopener">ai.google.dev/gemini-api/docs/batch-mode</a>（「at 50% of the standard cost」「The target turnaround time is 24 hours, but in majority of cases, it is much quicker.」「The maximum allowed file size for an input file is 2GB.」）</li>
<li>Google 料金: <a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noopener">ai.google.dev/gemini-api/docs/pricing</a>（Gemini 4 Carbon の料金行と「Batch API isn't supported」、Argon $2.00／$10.00）</li>
<li>xAI API Pricing: <a href="https://docs.x.ai/developers/pricing" target="_blank" rel="noopener">docs.x.ai/developers/pricing</a>（モデル別Batch割引 20%、grok-4.7〜4.20系、割引は全トークン種別、画像・動画は標準料金）</li>
<li>Moonshot（Kimi）: <a href="https://platform.kimi.ai/docs/pricing/chat" target="_blank" rel="noopener">platform.kimi.ai/docs/pricing/chat</a>（「kimi-k3.1-pro and kimi-k3 support batch inference ... billed at 60% of the standard price.」）</li>
<li>DeepSeek: <a href="https://api-docs.deepseek.com/quick_start/pricing" target="_blank" rel="noopener">api-docs.deepseek.com/quick_start/pricing</a>（「Off-peak rates are half of the peak rates. Peak hours are 01:00 - 04:00 and 06:00 - 10:00 UTC, Monday through Friday」）</li>
</ul>
</section>
<section class="section" style="padding-top:0;">
<h2 class="section-title" style="font-size:1.15rem;">関連ページ</h2>
<ul style="line-height:2;">
<li><a href="/pricing/">LLM API料金比較</a> — Batchを使わない通常単価の一覧（モデル別・確認日つき）</li>
<li><a href="/prompt-cache-pricing/">プロンプトキャッシュ料金の横断比較</a> — 同じ前置きを使い回すときの読込／書込単価</li>
<li><a href="/glossary/prompt-cache/">用語集: プロンプトキャッシュとは</a> — 仕組みと導入時の注意点</li>
<li><a href="/calculator/">トークンコスト計算機</a> — 入力／出力トークン数から概算</li>
<li><a href="/gpt-6-1-terra/">GPT-6.1 Terra 詳細</a>／<a href="/kimi-k3-1-pro/">Kimi K3.1 Pro 詳細</a>／<a href="/claude-fable-5-1/">Claude Fable 5.1 詳細</a></li>
</ul>
</section>
</div>
</main>
{FTR_JA}
</body>
</html>
'''

os.makedirs(SITE+'/batch-api-pricing',exist_ok=True)
open(SITE+'/batch-api-pricing/index.html','w',encoding='utf-8').write(body_ja)
open('/workspace/notes/backup-20261112-batch-api-pricing-ja.html','w',encoding='utf-8').write(body_ja)
print('JA written',len(body_ja))

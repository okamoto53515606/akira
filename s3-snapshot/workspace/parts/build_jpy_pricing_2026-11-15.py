# -*- coding: utf-8 -*-
"""Build /jpy-pricing/ (ja) and /en/jpy-pricing/ (en).

円換算額は data/price-sot.json の USD 単価から機械計算する（手打ち禁止）。
1ドル = 155 円固定。本文は check_page_shape の MAX_TEXT(ja 3000 / en 4500) に収める。

usage: python3 build_jpy_pricing_2026-11-15.py
"""
import json, os

SOT = '/workspace/data/price-sot.json'
SITE = '/tmp/site'
RATE = 155
DATE = '2026-11-15'
DATE_JA = '2026年11月15日'

sot = json.load(open(SOT, encoding='utf-8'))
MODELS = sot['models']


def jpy(usd_v):
    """USD/1M -> 円/1M。10円未満は小数第1位、以上は1円未満四捨五入。"""
    from decimal import Decimal, ROUND_HALF_UP
    v = Decimal(str(usd_v)) * RATE
    if v < 10:
        return str(v.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
    return '{:,}'.format(int(v.quantize(Decimal('1'), rounding=ROUND_HALF_UP)))


def usd(v):
    return '$%.2f' % v


ROWS = [
    ('gpt-6-1-sol', 'GPT-6.1 Sol', 'OpenAI', 'cache_miss_input', 'output', 'std'),
    ('gpt-6-1-terra', 'GPT-6.1 Terra', 'OpenAI', 'cache_miss_input', 'output', 'std'),
    ('gpt-6-luna', 'GPT-6 Luna', 'OpenAI', 'cache_miss_input', 'output', 'std'),
    ('claude-opus-5-5', 'Claude Opus 5.5', 'Anthropic', 'cache_miss_input', 'output', 'std'),
    ('claude-sonnet-5-5', 'Claude Sonnet 5.5', 'Anthropic', 'cache_miss_input', 'output', 'std'),
    ('claude-haiku-5-5', 'Claude Haiku 5.5', 'Anthropic', 'cache_miss_input', 'output', 'std'),
    ('gemini-4-argon', 'Gemini 4 Argon', 'Google', 'cache_miss_input', 'output', 'std'),
    ('gemini-3.8-flash', 'Gemini 3.8 Flash', 'Google', 'cache_miss_input', 'output', 'std'),
    ('gemini-3.5-flash-lite', 'Gemini 3.5 Flash Lite', 'Google', 'cache_miss_input', 'output', 'std'),
    ('kimi-k3', 'Kimi K3', 'Moonshot AI', 'cache_miss_input', 'output', 'std'),
    ('deepseek-v4.1-flash', 'DeepSeek V4.1 Flash', 'DeepSeek', 'cache_miss_input_offpeak', 'output_offpeak', 'peak'),
    ('deepseek-v4-pro', 'DeepSeek V4 Pro', 'DeepSeek', 'cache_miss_input_offpeak', 'output_offpeak', 'peak'),
    ('mimo-v2.6-pro', 'MiMo-V2.6-Pro', 'Xiaomi', 'cache_miss_input', 'output', 'std'),
    ('mimo-v2.6-flash', 'MiMo-V2.6-Flash', 'Xiaomi', 'cache_miss_input', 'output', 'std'),
    ('stepfun-step-5-preview', 'Step 5 Preview', 'StepFun', 'cache_miss_input', 'output', 'std'),
    ('deepseek-v4-flash', 'DeepSeek V4 Flash', 'DeepSeek', 'cache_miss_input_offpeak', 'output_offpeak', 'peak'),
]

RECS = []
for key, nm, prov, ikey, okey, mode in ROWS:
    m = MODELS[key]
    p = m['price']
    if not p.get(ikey) or not p.get(okey):
        raise SystemExit('MISSING PRICE: %s %s/%s' % (key, ikey, okey))
    rec = {'key': key, 'name': nm, 'prov': prov,
           'status': 'current' if m.get('status') == 'current' else 'retired',
           'in_usd': p[ikey], 'out_usd': p[okey], 'mode': mode,
           'verified': m.get('verified', ''), 'src': (m.get('sources') or [''])[0]}
    if mode == 'peak':
        rec['in_usd_pk'] = p['cache_miss_input_peak']
        rec['out_usd_pk'] = p['output_peak']
    if key == 'gemini-4-argon':
        rec['in_usd2'] = p['cache_miss_input_from_2026_12_01']
        rec['out_usd2'] = p['output_from_2026_12_01']
    RECS.append(rec)

BAR_KEYS = ['claude-opus-5-5', 'kimi-k3', 'gpt-6-1-sol', 'gemini-4-argon',
            'deepseek-v4.1-flash', 'claude-haiku-5-5', 'mimo-v2.6-flash']
MAX_OUT = max(r['out_usd'] for r in RECS if r['key'] in BAR_KEYS)


def build_table(lang):
    ja = lang == 'ja'
    o = ['<div class="table-wrap"><table class="cmp-table">']
    if ja:
        o.append('<thead><tr><th>モデル（提供元）</th><th>状態</th>'
                 '<th>入力<br>円 / 100万トークン</th><th>出力<br>円 / 100万トークン</th>'
                 '<th>USD 単価（入力 / 出力）</th></tr></thead>')
    else:
        o.append('<thead><tr><th>Model (provider)</th><th>Status</th>'
                 '<th>Input<br>JPY / 1M tokens</th><th>Output<br>JPY / 1M tokens</th>'
                 '<th>USD rate (input / output)</th></tr></thead>')
    o.append('<tbody>')
    for r in RECS:
        nm = ('%s（%s）' % (r['name'], r['prov'])) if ja else ('%s (%s)' % (r['name'], r['prov']))
        if r['status'] == 'current':
            st = '<span class="st-cur">%s</span>' % ('現行' if ja else 'Current')
        else:
            st = '<span class="st-old">%s</span>' % ('旧版' if ja else 'Legacy')
        cin, cout = jpy(r['in_usd']), jpy(r['out_usd'])
        uin, uout = usd(r['in_usd']), usd(r['out_usd'])
        if r['mode'] == 'peak':
            pk = 'ピーク時' if ja else 'peak'
            cin += '<br><span class="na">%s %s</span>' % (pk, jpy(r['in_usd_pk']))
            cout += '<br><span class="na">%s %s</span>' % (pk, jpy(r['out_usd_pk']))
            uin += '<br><span class="na">%s %s</span>' % (pk, usd(r['in_usd_pk']))
            uout += '<br><span class="na">%s %s</span>' % (pk, usd(r['out_usd_pk']))
        if 'in_usd2' in r:
            tail = '2026-12-01 から' if ja else 'from 2026-12-01'
            uin += '<br><span class="na">%s %s</span>' % (tail, usd(r['in_usd2']))
            uout += '<br><span class="na">%s %s</span>' % (tail, usd(r['out_usd2']))
        o.append('<tr><td>%s</td><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                 '<td class="mono">%s / %s</td></tr>' % (nm, st, cin, cout, uin, uout))
    o.append('</tbody></table></div>')
    return '\n'.join(o)


def build_bars(lang):
    ja = lang == 'ja'
    by = {r['key']: r for r in RECS}
    o = ['<div class="bars">']
    for k in BAR_KEYS:
        r = by[k]
        w = round(r['out_usd'] / MAX_OUT * 100.0, 1)
        if w < 1.5:
            w = 1.5
        if r['mode'] == 'peak':
            nm = r['name'] + ('（オフピーク）' if ja else ' (off-peak)')
        else:
            nm = r['name']
        cur = ('%s円' % jpy(r['out_usd'])) if ja else ('&yen;%s' % jpy(r['out_usd']))
        o.append('<div class="bar-row"><span>%s</span><span class="bar-track">'
                 '<span class="bar-fill" style="width:%s%%"></span></span>'
                 '<span class="mono">%s</span></div>' % (nm, w, cur))
    o.append('</div>')
    return '\n'.join(o)


HEAD = """<!DOCTYPE html>
<html lang="__LANG__">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <meta name="description" content="__DESC__">
  <link rel="canonical" href="https://llm.okamomedia.tokyo/__DIR__">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta property="og:image" content="https://llm.okamomedia.tokyo/assets/og/__OG__">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="__OGALT__">
  <meta name="twitter:image" content="https://llm.okamomedia.tokyo/assets/og/__OG__">
  <meta name="twitter:image:alt" content="__OGALT__">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://llm.okamomedia.tokyo/__DIR__">
  <meta property="og:title" content="__TITLE__">
  <meta property="og:description" content="__DESC__">
  <meta property="og:site_name" content="LLM Data Hub">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">__LD__</script>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-MTH8T0ECG2"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-MTH8T0ECG2');</script>
  <link rel="stylesheet" href="/assets/style.css">
  <style>
    .cmp-table th,.cmp-table td{font-size:.84rem;vertical-align:top}
    .cmp-table td.num{font-family:var(--font-mono);font-weight:600;white-space:nowrap}
    .cmp-table td.mono{font-family:var(--font-mono);font-size:.8rem;color:var(--c-muted);white-space:nowrap}
    .cmp-table span.na,.cmp-table td.na{color:var(--c-muted);font-weight:400}
    .table-wrap{overflow-x:auto}
    .bar-row .mono{font-family:var(--font-mono);font-size:.82rem;color:var(--c-muted);text-align:right}
    .rate-box{background:var(--c-surface);border:1px solid var(--c-border);border-left:4px solid var(--c-accent);border-radius:var(--r-md);padding:.9rem 1.1rem;margin:1rem 0;font-size:.9rem}
    .rate-box b{font-family:var(--font-mono);font-size:1.15rem;color:var(--c-accent)}
    .src-list{font-size:.8rem;color:var(--c-muted);line-height:1.9}
  </style>
  <link rel="alternate" hreflang="ja" href="https://llm.okamomedia.tokyo/jpy-pricing/">
  <link rel="alternate" hreflang="en" href="https://llm.okamomedia.tokyo/en/jpy-pricing/">
  <link rel="alternate" hreflang="x-default" href="https://llm.okamomedia.tokyo/jpy-pricing/">
</head>
"""

JA_TITLE = 'LLM API 日本円換算の料金表【1ドル=155円・2026年11月版】 — LLM Data Hub'
EN_TITLE = 'LLM API Prices in Japanese Yen (&yen;155 = $1) [Nov 2026] — LLM Data Hub'
JA_DESC = ('主要LLM APIの単価を1ドル=155円で日本円に換算した表。100万トークンあたりの入力・出力を'
           'USD単価と併記し、現行／旧版の状態列も掲載。GPT-6.1・Claude Opus 5.5・Gemini 4 Argon・'
           'Kimi K3・DeepSeek V4.1 Flash の16モデル（2026年11月15日更新）。')
EN_DESC = ('LLM API rates in Japanese yen at a fixed &yen;155 = $1, per 1M tokens for input and '
           'output alongside the USD rate, with a current/legacy column. 16 models. Updated 2026-11-15.')


def ld(kind):
    ja = kind == 'ja'
    return json.dumps({
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': (JA_TITLE if ja else EN_TITLE).replace(' — LLM Data Hub', ''),
        'datePublished': DATE, 'dateModified': DATE,
        'author': {'@type': 'Organization', 'name': 'LLM Data Hub'},
        'publisher': {'@type': 'Organization', 'name': 'okamoちゃんねる' if ja else 'okamo channel'},
        'url': 'https://llm.okamomedia.tokyo/%sjpy-pricing/' % ('' if ja else 'en/'),
        'inLanguage': 'ja' if ja else 'en',
        'isAccessibleForFree': True,
        'description': JA_DESC if ja else EN_DESC,
    }, ensure_ascii=False)


def parts(kind):
    src = SITE + ('/image-api-pricing/' if kind == 'ja' else '/en/image-api-pricing/') + 'index.html'
    s = open(src, encoding='utf-8').read()
    return s[s.index('<body>'):s.index('<main>')], s[s.index('</main>'):]


def page(kind):
    ja = kind == 'ja'
    head = (HEAD.replace('__LANG__', kind)
            .replace('__TITLE__', JA_TITLE if ja else EN_TITLE)
            .replace('__DESC__', JA_DESC if ja else EN_DESC)
            .replace('__LD__', ld(kind))
            .replace('__DIR__', 'jpy-pricing/' if ja else 'en/jpy-pricing/')
            .replace('__OG__', '%s-jpy-pricing.png' % kind)
            .replace('__OGALT__', '1ドル=155円で換算した主要LLM APIの日本円料金表（LLM Data Hub）' if ja
                     else 'LLM API pricing in Japanese yen at 155 yen per dollar (LLM Data Hub)'))
    h, f = parts(kind)
    b = []
    A = b.append

    A('<div class="container" style="padding-top:2rem;">')
    A('<figure class="key-visual" style="margin:1.5rem 0 .5rem;"><img src="/assets/og/__KIND__-jpy-pricing.png" '
      'alt="__ALT__" width="1200" height="630" loading="eager" decoding="async" '
      'style="width:100%;max-width:900px;height:auto;display:block;margin:0 auto;'
      'border:1px solid var(--c-border);border-radius:var(--r-md);"></figure>'
      .replace('__KIND__', kind)
      .replace('__ALT__', 'このページの内容を1枚にまとめた画像' if ja else 'This page summarised in one image'))

    if ja:
        A('<h1 class="section-title" style="font-size:1.6rem;">LLM API 日本円換算の料金表 '
          '<span style="font-size:1rem;font-weight:500;color:var(--c-muted);">【2026年11月版】</span></h1>')
        A('<div class="rate-box"><strong>1ドル=155円で換算</strong>しています（<b>&yen;155 / $1</b> 固定）。'
          '円の列は<b>100万トークンあたり</b>の金額です。USD単価は data/price-sot.json の値をそのまま使い、'
          '円はそこから機械計算しています。</div>')
        A('<div class="updated-bar"><span class="dot">●</span>最終更新: '
          '<time datetime="%s">%s</time> | 各社公式料金ページの最終確認日は出典欄に併記しています。</div>'
          % (DATE, DATE_JA))
    else:
        A('<h1 class="section-title" style="font-size:1.6rem;">LLM API prices in Japanese yen '
          '<span style="font-size:1rem;font-weight:500;color:var(--c-muted);">[Nov 2026]</span></h1>')
        A('<div class="rate-box"><strong>Converted at &yen;155 = $1</strong> (a fixed rate). '
          'Every yen figure is <b>per 1M tokens</b>. USD rates are taken as-is from '
          'data/price-sot.json; the yen figures are calculated from them, not typed by hand.</div>')
        A('<div class="updated-bar"><span class="dot">●</span>Last updated: '
          '<time datetime="%s">2026-11-15</time> | The last verification date of each provider '
          'rate is listed in the sources section.</div>' % DATE)

    toc = (['結論（3行）', '換算のルール', '円換算表（16モデル）', '出力単価の差', '注意（3点）', '出典']
           if ja else
           ['Bottom line', 'How the conversion works', 'Yen table (16 models)',
            'The spread on output', 'Three caveats', 'Sources'])
    A('<div class="section" style="padding-top:1.25rem;padding-bottom:0;">')
    A('<nav class="toc" aria-label="%s"><p class="toc-title">%s</p><ol>'
      % ('目次' if ja else 'Contents', '目次' if ja else 'Contents'))
    for i, t in enumerate(toc, 1):
        A('<li><a href="#sec-%d">%s</a></li>' % (i, t))
    A('</ol></nav></div>')

    # 1 結論
    if ja:
        A('<div class="conclusion"><h2 class="section-title" style="font-size:1.15rem;margin-top:0;" '
          'id="sec-1">結論（3行）</h2><ul>')
        A('<li><strong>円建ての出力単価は 43円〜3,100円/100万トークン</strong>。Claude Opus 5.5 が '
          '<b>3,100円</b>、MiMo-V2.6-Flash が <b>43円</b>で、同じ100万トークンでも約71倍ひらきます。</li>')
        A('<li><strong>入力と出力は別単価</strong>。多くのモデルで出力は入力の約5倍'
          '（GPT-6.1 Sol は入力310円／出力1,550円）。</li>')
        A('<li><strong>DeepSeek だけは時間帯で2本建て</strong>。オフピークはピーク時の半額。'
          '表では両方を併記しています。</li>')
        A('</ul></div>')
    else:
        A('<div class="conclusion"><h2 class="section-title" style="font-size:1.15rem;margin-top:0;" '
          'id="sec-1">Bottom line</h2><ul>')
        A('<li><strong>Output rates run from &yen;43 to &yen;3,100 per 1M tokens</strong>: '
          'Claude Opus 5.5 <b>&yen;3,100</b>, MiMo-V2.6-Flash <b>&yen;43</b> &mdash; about a 71x spread.</li>')
        A('<li><strong>Input and output are priced separately</strong>, output at about 5x input on '
          'most models (GPT-6.1 Sol: &yen;310 in, &yen;1,550 out).</li>')
        A('<li><strong>DeepSeek is the only two-tier one</strong>. Off-peak is half of peak; the table '
          'shows both.</li>')
        A('</ul></div>')

    # 2 換算ルール
    A('<div class="tint"><h2 class="section-title" style="font-size:1.15rem;" id="sec-2">%s</h2>'
      % ('換算のルール' if ja else 'How the conversion works'))
    A('<div class="diagram">')
    A('<div class="dg-box provider-openai"><b>%s</b>$2.00 / 1M</div>'
      % ('USD単価' if ja else 'USD rate'))
    A('<div class="dg-arrow">&times;</div>')
    A('<div class="dg-box accent"><b>%s</b>155</div>' % ('固定レート' if ja else 'Fixed rate'))
    A('<div class="dg-arrow">=</div>')
    A('<div class="dg-box provider-anthropic"><b>%s</b>&yen;310</div>' % ('円換算' if ja else 'In yen'))
    A('<div class="diagram-note">%s</div>' % (
        'USD単価×155が円の列です（10円未満は小数第1位、それ以上は1円未満を四捨五入）。'
        if ja else
        'The yen column is the USD rate times 155. Rounding: one decimal below &yen;10, otherwise '
        'nearest yen. Rates move daily, so treat this as a reference, not a quote.'))
    A('</div>')
    if ja:
        A('<ul>'
          '<li><strong>何あたりか</strong>: すべて<b>100万トークンあたり</b>。10万トークンなら表の1/10です。</li>'
          '<li><strong>含まないもの</strong>: 消費税・カード手数料・為替スプレッド。請求書の額そのものではありません。</li>'
          '<li><strong>別単価</strong>: キャッシュ入力、Batch、長文（272Kトークン超など）、優先処理。'
          '表は標準の入力・出力のみ。</li>'
          '</ul>')
    else:
        A('<ul>'
          '<li><strong>Per what</strong>: everything is <b>per 1M tokens</b>. 100,000 tokens is a tenth of the table.</li>'
          '<li><strong>Not included</strong>: consumption tax, card fees, FX spread. These are not your invoice amount.</li>'
          '<li><strong>Priced separately</strong>: cached input, Batch, long-context tiers (above 272K tokens), '
          'priority. This table is standard input and output only.</li>'
          '</ul>')
    A('</div>')

    # 3 表
    A('<h2 class="section-title" style="font-size:1.15rem;" id="sec-3">%s</h2>'
      % ('円換算表（16モデル）' if ja else 'Yen table (16 models)'))
    A('<p style="font-size:.9rem;color:var(--c-muted);">%s</p>' % (
        'USD単価は各社公式の数字をそのまま残しています。為替が変わったら<b>USD列だけ差し替えれば再計算できます</b>。'
        'キャッシュ・Batch・長文の条件は<a href="/pricing/">LLM API 料金比較</a>へ。'
        if ja else
        'The USD column keeps each provider\'s published figure, so a rate change only needs that '
        'column replaced. Cache, batch and long-context conditions live on the '
        '<a href="/en/pricing/">full pricing comparison</a>.'))
    A(build_table(kind))
    A('<p class="na" style="font-size:.78rem;">%s</p>' % (
        '※ DeepSeek V4 Flash は 2026-09-10 に V4.1 Flash へ統合（旧プロモ価格も廃止）。'
        '推移を見るため旧版として残しています。'
        if ja else
        'DeepSeek V4 Flash was merged into V4.1 Flash on 2026-09-10 (promo rate ended). '
        'It stays as a legacy row.'))

    # 4 棒グラフ
    A('<div class="tint"><h2 class="section-title" style="font-size:1.15rem;" id="sec-4">%s</h2>'
      % ('出力単価の差' if ja else 'The spread on output'))
    A('<p style="font-size:.9rem;color:var(--c-muted);">%s</p>' % (
        '出力100万トークンの円換算額。棒の長さは金額に比例（最長＝Claude Opus 5.5 の3,100円）。'
        if ja else
        'Yen per 1M output tokens; bar length is proportional to the amount '
        '(longest = Claude Opus 5.5, &yen;3,100).'))
    A(build_bars(kind))
    A('</div>')

    # 5 注意
    A('<h2 class="section-title" style="font-size:1.15rem;" id="sec-5">%s</h2>'
      % ('注意（3点）' if ja else 'Three caveats'))
    if ja:
        A('<ul>'
          '<li><strong>1ドル=155円は固定</strong>。為替が動いても表は動きません。請求は USD 建てなので、'
          '決済時レートで円の負担は変わります。</li>'
          '<li><strong>為替では更新日を動かしません</strong>。動くのはUSD単価が変わったときだけです。</li>'
          '<li><strong>自分の請求額</strong>はトークン数で決まります。<a href="/calculator/">トークン計算機</a>なら'
          'USDと円の両方で試算できます。</li>'
          '</ul>')
    else:
        A('<ul>'
          '<li><strong>&yen;155 = $1 is fixed</strong>. The table does not move with the market; billing '
          'is in USD, so your yen cost follows the charge-day rate.</li>'
          '<li><strong>We do not move the page date for FX moves.</strong> It changes only when a '
          'provider changes its USD rate.</li>'
          '<li><strong>Your bill</strong> depends on token counts. The '
          '<a href="/en/calculator/">token calculator</a> shows the cost in both currencies.</li>'
          '</ul>')

    # 6 出典
    A('<h2 class="section-title" style="font-size:1.15rem;" id="sec-6">%s</h2>'
      % ('出典' if ja else 'Sources'))
    seen = []
    for r in RECS:
        t = (r['prov'], r['src'], r['verified'])
        if t in seen or not r['src']:
            continue
        seen.append(t)
    A('<ul class="src-list">')
    for prov, url, ver in seen:
        A('<li>%s: <a href="%s" rel="nofollow noopener">%s</a>（%s %s）</li>'
          % (prov, url, url.split('//')[1].split('/')[0], '確認日' if ja else 'verified', ver))
    A('</ul>')
    A('<p class="na" style="font-size:.78rem;">%s</p>' % (
        '為替は1ドル=155円の固定で、外部の為替データは使っていません。'
        if ja else
        'The rate is fixed at &yen;155 = $1; no external FX feed is used.'))
    A('</div>')
    return head + h + '<main>\n' + '\n'.join(b) + '\n</main>\n' + f[f.index('</main>') + 7:]


def main():
    for kind in ('ja', 'en'):
        html = page(kind)
        d = SITE + ('' if kind == 'ja' else '/en') + '/jpy-pricing'
        os.makedirs(d, exist_ok=True)
        p = d + '/index.html'
        open(p, 'w', encoding='utf-8').write(html)
        print('wrote', p, len(html))
    for r in RECS:
        print(r['key'], jpy(r['in_usd']), jpy(r['out_usd']),
              jpy(r['in_usd_pk']) if 'in_usd_pk' in r else '')


if __name__ == '__main__':
    main()

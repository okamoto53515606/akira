# -*- coding: utf-8 -*-
"""Trim /workspace/parts/build_jpy_pricing_2026-11-15.py so both pages fit
check_page_shape MAX_TEXT (ja 3000 / en 4500). Every pair must apply exactly once."""
P = '/workspace/parts/build_jpy_pricing_2026-11-15.py'
s = open(P, encoding='utf-8').read()

PAIRS = [
# --- ja conclusion ---
('円建てで見ると、出力単価は 43円〜3,100円/100万トークン</strong>。いちばん高いのは Claude Opus 5.5 の出力 <b>3,100円</b>、いちばん安いのは MiMo-V2.6-Flash の出力 <b>43円</b>で、同じ100万トークンでも約71倍ひらきます。',
 '円建ての出力単価は 43円〜3,100円/100万トークン</strong>。Claude Opus 5.5 が <b>3,100円</b>、MiMo-V2.6-Flash が <b>43円</b>で、同じ100万トークンでも約71倍ひらきます。'),
('入力と出力は別単価</strong>。どのモデルも出力が入力の5倍前後（例: GPT-6.1 Sol は入力310円／出力1,550円）。文章を読ませる用途と書かせる用途では請求額の桁が変わります。',
 '入力と出力は別単価</strong>。多くのモデルで出力は入力の約5倍（GPT-6.1 Sol は入力310円／出力1,550円）。'),
('DeepSeek だけは時間帯で2本建て</strong>。オフピークはピーク時の半額で、表では両方を併記しています。日本時間の深夜〜早朝に回せる処理はここで差がつきます。',
 'DeepSeek だけは時間帯で2本建て</strong>。オフピークはピーク時の半額。表では両方を併記しています。'),
# --- ja diagram note ---
('USD単価に155を掛けた値が円の列です。四捨五入は「10円未満は小数第1位、それ以上は1円未満を四捨五入」。'
        '為替は日々動くので、この表は特定日のレートではなく<b>固定レートでの目安</b>として読んでください。',
 'USD単価×155が円の列です（10円未満は小数第1位、それ以上は1円未満を四捨五入）。'),
# --- ja rules ---
('<li><strong>何あたりの金額か</strong>: すべて<b>100万トークンあたり</b>です。'
          '10万トークンなら表の値を10で割った額になります。</li>',
 '<li><strong>何あたりか</strong>: すべて<b>100万トークンあたり</b>。10万トークンなら表の1/10です。</li>'),
('<li><strong>含まないもの</strong>: 消費税、カード決済手数料、為替スプレッド。'
          '当サイトの円換算は請求書の金額そのものではありません。</li>',
 '<li><strong>含まないもの</strong>: 消費税・カード手数料・為替スプレッド。請求書の額そのものではありません。</li>'),
('<li><strong>別単価になるもの</strong>: キャッシュ入力、Batch API、長文プレミアム'
          '（272Kトークン超など）、優先処理。この表は標準の入力・出力だけを載せています。</li>',
 '<li><strong>別単価</strong>: キャッシュ入力、Batch、長文（272Kトークン超など）、優先処理。表は標準の入力・出力のみ。</li>'),
# --- ja intro / footnote / bars / caveats / sources note ---
('主要モデルの入力・出力だけを並べています。USD単価は各社公式の数字をそのまま残したので、'
        '為替が変わったら<b>USD列だけ差し替えれば円は再計算できます</b>。'
        'より細かい条件（キャッシュ、Batch、長文）は'
        '<a href="/pricing/">LLM API 料金比較</a>に譲ります。',
 'USD単価は各社公式の数字をそのまま残しています。為替が変わったら<b>USD列だけ差し替えれば再計算できます</b>。'
        'キャッシュ・Batch・長文の条件は<a href="/pricing/">LLM API 料金比較</a>へ。'),
('※ DeepSeek V4 Flash は 2026-09-10 に V4.1 Flash へ統合されました（旧プロモ価格も廃止済み）。'
        '金額の推移を見られるように旧版として残しています。',
 '※ DeepSeek V4 Flash は 2026-09-10 に V4.1 Flash へ統合（旧プロモ価格も廃止）。推移を見るため旧版として残しています。'),
('出力100万トークンの円換算額です。棒の長さは金額に比例しています（最長＝Claude Opus 5.5 の3,100円）。',
 '出力100万トークンの円換算額。棒の長さは金額に比例（最長＝Claude Opus 5.5 の3,100円）。'),
('<li><strong>1ドル=155円は固定です</strong>。円安・円高が進んでも表は動きません。'
          '実際の請求は USD 建てなので、決済時のレートで円の負担は変わります。</li>',
 '<li><strong>1ドル=155円は固定</strong>。為替が動いても表は動きません。請求は USD 建てなので、決済時レートで円の負担は変わります。</li>'),
('<li><strong>為替を理由にページの日付は動かしません</strong>。更新日が動くのは'
          'USD単価そのものが変わったときだけです。</li>',
 '<li><strong>為替では更新日を動かしません</strong>。動くのはUSD単価が変わったときだけです。</li>'),
('<li><strong>自分の使い方で何円になるか</strong>は、入力と出力のトークン数が分からないと'
          '決まりません。<a href="/calculator/">トークン計算機</a>にトークン数を入れると'
          'USDと円の両方で試算できます。</li>',
 '<li><strong>自分の請求額</strong>はトークン数で決まります。<a href="/calculator/">トークン計算機</a>ならUSDと円の両方で試算できます。</li>'),
('為替レートは1ドル=155円で固定しており、外部の為替データは取得していません。',
 '為替は1ドル=155円の固定で、外部の為替データは使っていません。'),
# --- en conclusion ---
("'<li><strong>In yen, output rates run from &yen;43 to &yen;3,100 per 1M tokens</strong>. '\n          'Claude Opus 5.5 costs <b>&yen;3,100</b> for 1M output tokens, MiMo-V2.6-Flash '\n          '<b>&yen;43</b> &mdash; roughly a 71x spread for the same token count.</li>'",
 "'<li><strong>Output rates run from &yen;43 to &yen;3,100 per 1M tokens</strong>: '\n          'Claude Opus 5.5 <b>&yen;3,100</b>, MiMo-V2.6-Flash <b>&yen;43</b> &mdash; about a 71x spread.</li>'"),
("'<li><strong>Input and output are priced separately</strong>, and output is about 5x '\n          'input on most models (GPT-6.1 Sol: &yen;310 in, &yen;1,550 out). Reading and writing '\n          'change the bill by an order of magnitude.</li>'",
 "'<li><strong>Input and output are priced separately</strong>, output at about 5x input on '\n          'most models (GPT-6.1 Sol: &yen;310 in, &yen;1,550 out).</li>'"),
("'<li><strong>DeepSeek is the only two-tier one</strong>. Off-peak is half of peak; the '\n          'table shows both. Work you can schedule into off-peak hours is where the saving is.</li>'",
 "'<li><strong>DeepSeek is the only two-tier one</strong>. Off-peak is half of peak; the table shows both.</li>'"),
# --- en diagram note ---
("'The yen column is the USD rate multiplied by 155. Rounding: one decimal below &yen;10, '\n        'otherwise rounded to the nearest yen. Because real exchange rates move daily, treat this '\n        'as a fixed-rate reference, not a quote.'",
 "'The yen column is the USD rate times 155. Rounding: one decimal below &yen;10, otherwise '\n        'nearest yen. Rates move daily, so treat this as a reference, not a quote.'"),
# --- en rules ---
("'<li><strong>What the figure is per</strong>: everything is <b>per 1M tokens</b>. '\n          '100,000 tokens is a tenth of the number in the table.</li>'",
 "'<li><strong>Per what</strong>: everything is <b>per 1M tokens</b>. 100,000 tokens is a tenth of the table.</li>'"),
("'<li><strong>Not included</strong>: consumption tax, card fees, FX spread. These yen '\n          'figures are not the amount on your invoice.</li>'",
 "'<li><strong>Not included</strong>: consumption tax, card fees, FX spread. These are not your invoice amount.</li>'"),
("'<li><strong>Priced separately</strong>: cached input, Batch API, long-context tiers '\n          '(above 272K tokens, for example), priority processing. This table covers standard '\n          'input and output only.</li>'",
 "'<li><strong>Priced separately</strong>: cached input, Batch, long-context tiers (above 272K tokens), priority. This table is standard input and output only.</li>'"),
# --- en intro / footnote / bars / caveats / note ---
("'Input and output only, for the mainstream models. The USD column keeps each provider\\'s '\n        'own published figure, so if the rate moves you only need to replace that column. '\n        'Cache, batch and long-context conditions live on the '\n        '<a href=\"/en/pricing/\">full pricing comparison</a>.'",
 "'Input and output only. The USD column keeps each provider\\'s published figure, so a rate '\n        'change only needs that column replaced. Cache, batch and long-context conditions live on the '\n        '<a href=\"/en/pricing/\">full pricing comparison</a>.'"),
("'DeepSeek V4 Flash was merged into V4.1 Flash on 2026-09-10 (its promo rate ended). '\n        'It stays in the table as a legacy row so the movement is visible.'",
 "'DeepSeek V4 Flash was merged into V4.1 Flash on 2026-09-10 (promo rate ended). It stays as a legacy row.'"),
("'Yen per 1M output tokens. Bar length is proportional to the amount '\n        '(longest = Claude Opus 5.5 at &yen;3,100).'",
 "'Yen per 1M output tokens; bar length is proportional to the amount '\n        '(longest = Claude Opus 5.5, &yen;3,100).'"),
("'<li><strong>&yen;155 = $1 is fixed</strong>. The table does not move with the market. '\n          'Billing is in USD, so your actual yen cost follows the rate on the day you are charged.</li>'",
 "'<li><strong>&yen;155 = $1 is fixed</strong>. The table does not move with the market; billing '\n          'is in USD, so your yen cost follows the charge-day rate.</li>'"),
("'<li><strong>We do not move the page date for FX moves.</strong> The update date changes '\n          'only when a provider changes its USD rate.</li>'",
 "'<li><strong>We do not move the page date for FX moves.</strong> It changes only when a provider changes its USD rate.</li>'"),
("'<li><strong>Your own bill</strong> depends on how many tokens you send and receive. '\n          'Put the token counts into the '\n          '<a href=\"/en/calculator/\">token calculator</a> to see the cost in both currencies.</li>'",
 "'<li><strong>Your bill</strong> depends on token counts. The '\n          '<a href=\"/en/calculator/\">token calculator</a> shows the cost in both currencies.</li>'"),
("'The exchange rate is fixed at &yen;155 per dollar; no external FX feed is used.'",
 "'The rate is fixed at &yen;155 = $1; no external FX feed is used.'"),
# --- en description ---
("EN_DESC = ('Mainstream LLM API rates converted to Japanese yen at a fixed 155 yen per dollar, '\n           'shown per 1M tokens for input and output alongside the USD rate, with a current/legacy '\n           'column. 16 models. Updated 2026-11-15.')",
 "EN_DESC = ('LLM API rates in Japanese yen at a fixed &yen;155 = $1, per 1M tokens for input '\n           'and output alongside the USD rate, with a current/legacy column. 16 models. Updated 2026-11-15.')"),
# --- sources: show host only, keep full URL in href ---
("% (prov, url, url, '確認日' if ja else 'verified', ver))",
 "% (prov, url, url.split('//')[1].split('/')[0], '確認日' if ja else 'verified', ver))"),
]

for old, new in PAIRS:
    n = s.count(old)
    if n != 1:
        raise SystemExit('PAIR NOT APPLIED (%d): %r' % (n, old[:60]))
    s = s.replace(old, new)

open(P, 'w', encoding='utf-8').write(s)
print('patched %d pairs' % len(PAIRS))

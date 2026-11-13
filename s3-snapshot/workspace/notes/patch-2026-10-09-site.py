# -*- coding: utf-8 -*-
"""2026-10-09 サイト横断パッチ: pricing / home / timeline / multimodal / glossary ZOA・ZDR
   - 既存ファイルは編集前に /workspace/notes/backup-20261009/ へコピー
   - 置換は「1箇所だけ一致」を検証し、不一致はレポートに出す
"""
import pathlib, re, shutil, sys
S = pathlib.Path('/tmp/site')
BK = pathlib.Path('/workspace/notes/backup-20261009')
BK.mkdir(parents=True, exist_ok=True)
report = []

def read(rel):
    return (S / rel).read_text(encoding='utf-8')

def write(rel, t):
    (S / rel).write_text(t, encoding='utf-8')

def one(rel, t, old, new, label, required=True):
    n = t.count(old)
    if n != 1:
        report.append(f"{'FAIL' if required else 'WARN'} {rel} [{label}] count={n}")
        return t
    report.append(f"ok   {rel} [{label}]")
    return t.replace(old, new, 1)

def rx(rel, t, pat, new, label, required=True, count=1):
    t2, n = re.subn(pat, new, t, count=count, flags=re.S)
    if n != count:
        report.append(f"{'FAIL' if required else 'WARN'} {rel} [{label}] n={n}")
        return t
    report.append(f"ok   {rel} [{label}]")
    return t2

def backup(rel):
    src = S / rel
    dst = BK / rel.replace('/', '__')
    if src.exists():
        shutil.copy2(src, dst)

# =====================================================================
# 1) PRICING
# =====================================================================
for rel, ja in (('pricing/index.html', True), ('en/pricing/index.html', False)):
    backup(rel); t = read(rel)
    if ja:
        t = rx(rel, t, r'<title>.*?</title>',
               '<title>主要LLM API 料金比較【2026年10月版】 — LLM Data Hub</title>', 'title')
        t = t.replace('【2026年9月版】', '【2026年10月版】')
        t = one(rel, t, '（2026年10月1日更新）', '（2026年10月9日更新）', 'meta date')
        t = one(rel, t, 'Claude Opus 5.5（9/22公開・$4/$20）',
                'Claude Haiku 5.5（10/7公開・$0.10/$0.50・100k超は2段階）・GPT-6.1 Sol（$2/$10・キャッシュ入力$0.10）・Claude Opus 5.5（9/22公開・$4/$20）', 'meta models', required=False)
        t = one(rel, t, '"dateModified":"2026-10-01"', '"dateModified":"2026-10-09"', 'ld date')
        t = one(rel, t, '<time datetime="2026-10-01">2026年10月1日</time>',
                '<time datetime="2026-10-09">2026年10月9日</time>', 'updated-bar time')
        t = one(rel, t, 'Anthropic 2026-10-01', 'Anthropic 2026-10-09', 'bar anthropic', required=False)
        t = one(rel, t, 'OpenAI 2026-09-25', 'OpenAI 2026-09-25（GPT-6.1 Sol 2026-10-09）', 'bar openai', required=False)
        t = one(rel, t, 'Gemini 2026-09-04', 'Gemini 2026-09-04（画像モデル 2026-10-09）', 'bar gemini', required=False)
        # Sonnet 5.5 キャッシュ読込 $0.20 -> $0.10
        t = rx(rel, t,
               r'(<tr><td class="model-name">Claude Sonnet 5\.5 <span class="badge badge-new" style="font-size:\.7rem;">New</span></td><td class="price">\$2\.00</td><td class="price">\$2\.50</td><td class="price">)\$0\.20(</td>)',
               r'\1$0.10\2', 'sonnet cache read')
        t = one(rel, t, '<strong>前世代Sonnet 5と同額</strong>',
                '<strong>前世代Sonnet 5と同額</strong>（キャッシュ読込は$0.20→$0.10に半減。2026-10-09に公式ページで確認して修正）', 'sonnet cache note')
        haiku_row = ('<tr><td class="model-name">Claude Haiku 5.5 <span class="badge badge-new">New</span></td>'
                     '<td class="price">$0.10</td><td class="price">$0.125</td><td class="price">$0.01</td><td class="price">$0.50</td>'
                     '<td>2026-10-07公開。Claude 5.5世代の最速・最安。<strong>100,000トークン超は入力$0.50・出力$2.50・キャッシュ読込$0.05</strong>の2段階。'
                     'トークナイザー変更で同じ文面は約30%多くカウント <a href="/claude-haiku-5-5/" style="font-weight:700;">→詳細ページ</a></td></tr>\n')
        t = one(rel, t, '<tr><td class="model-name">Claude Haiku 4.5</td>', haiku_row + '<tr><td class="model-name">Claude Haiku 4.5</td>', 'haiku row')
        sol_row = ('<tr><td class="model-name">GPT-6.1 Sol <span class="badge badge-new">New</span></td>'
                   '<td class="price">$2.00</td><td class="price">$0.10</td><td class="price">$10.00</td>'
                   '<td>入力$2・出力$10はGPT-6 Solと同額で、<strong>キャッシュ入力は$0.10（入力の5%）</strong>。キャッシュ書込$2.50・Fastは2倍・Ultrafastは6倍・Batch/Flexは50%引き。'
                   '<strong>272,000トークン超の入力はリクエスト全体が入力2倍・出力1.5倍</strong> <a href="/gpt-6-1-sol/" style="font-weight:700;">→詳細ページ</a></td></tr>\n')
        i = t.index('<tr><td class="model-name">GPT-6 Sol <span')
        j = t.index('</tr>', i) + len('</tr>') + 1
        t = t[:j] + sol_row + t[j:]
        report.append('ok   pricing/index.html [sol row]')
        note_z = ('<div class="note-bar">🆕 <strong>Claude Haiku 5.5 を追記（2026-10-09）:</strong> 入力$0.10・キャッシュ書込$0.125・キャッシュ読込$0.01・出力$0.50（USD/1M、100,000トークンまで）。'
                  '100k超は入力$0.50・出力$2.50。あわせて <strong>Sonnet 5.5 のキャッシュ読込を$0.20→$0.10に修正</strong>しました（公式: '
                  '<a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank" rel="noopener">platform.claude.com</a>）。</div>\n')
        note_o = ('<div class="note-bar">🆕 <strong>GPT-6.1 Sol を追記（2026-10-09）:</strong> 入力$2・キャッシュ入力$0.10（入力の5%）・キャッシュ書込$2.50・出力$10（USD/1M）。'
                  '272,000トークン超の入力はリクエスト全体が入力2倍・出力1.5倍。公式モデルページで確認（'
                  '<a href="https://developers.openai.com/api/docs/models/gpt-6.1-sol" target="_blank" rel="noopener">出典</a>）。</div>\n')
    else:
        t = rx(rel, t, r'<title>.*?</title>',
               '<title>OpenAI, Claude, Gemini &amp; DeepSeek API Pricing Comparison [Oct 2026] | LLM Data Hub</title>', 'title')
        t = t.replace('[Sep 2026]', '[Oct 2026]')
        t = one(rel, t, '（updated October 1, 2026）', '（updated October 9, 2026）', 'meta date', required=False)
        t = one(rel, t, 'updated October 1, 2026', 'updated October 9, 2026', 'meta date2', required=False)
        t = one(rel, t, '"dateModified":"2026-10-01"', '"dateModified":"2026-10-09"', 'ld date')
        t = one(rel, t, 'Page updated: <time datetime="2026-10-01">October 1, 2026</time>',
                'Page updated: <time datetime="2026-10-09">October 9, 2026</time>', 'updated-bar time')
        t = one(rel, t, '2026-09-25 for OpenAI', '2026-09-25 for OpenAI (GPT-6.1 Sol 2026-10-09)', 'bar openai', required=False)
        t = one(rel, t, '2026-10-01 for Anthropic', '2026-10-09 for Anthropic', 'bar anthropic', required=False)
        t = one(rel, t, '2026-09-04 for Gemini', '2026-09-04 for Gemini (image models 2026-10-09)', 'bar gemini', required=False)
        t = rx(rel, t,
               r'(<tr><td class="model-name">Claude Sonnet 5\.5 <span class="badge badge-new" style="font-size:\.7rem;">New</span></td><td class="price">\$2\.00</td><td class="price">\$2\.50</td><td class="price">)\$0\.20(</td>)',
               r'\1$0.10\2', 'sonnet cache read')
        t = one(rel, t, '<strong>Same price as Sonnet 5</strong>',
                '<strong>Same price as Sonnet 5</strong> (cache reads corrected from $0.20 to $0.10 on 2026-10-09 after checking the official page)', 'sonnet cache note')
        haiku_row = ('<tr><td class="model-name">Claude Haiku 5.5 <span class="badge badge-new">New</span></td>'
                     '<td class="price">$0.10</td><td class="price">$0.125</td><td class="price">$0.01</td><td class="price">$0.50</td>'
                     '<td>Released 2026-10-07. Fastest and cheapest of the Claude 5.5 family. <strong>Above 100,000 tokens: $0.50 input / $2.50 output / $0.05 cache reads.</strong> '
                     'The new tokenizer counts the same text as roughly 30% more tokens. <a href="/en/claude-haiku-5-5/">Details →</a></td></tr>\n')
        t = one(rel, t, '<tr><td class="model-name">Claude Haiku 4.5</td>', haiku_row + '<tr><td class="model-name">Claude Haiku 4.5</td>', 'haiku row')
        sol_row = ('<tr><td class="model-name">GPT-6.1 Sol <span class="badge badge-new">New</span></td>'
                   '<td class="price">$2.00</td><td class="price">$0.10</td><td class="price">$10.00</td>'
                   '<td>Input $2 / output $10 matches GPT-6 Sol, but <strong>cached input is $0.10 (5% of input)</strong>. Cache writes $2.50, Fast 2x, Ultrafast 6x, Batch/Flex 50% off. '
                   '<strong>Prompts above 272,000 input tokens are repriced at 2x input and 1.5x output for the whole request</strong> <a href="/en/gpt-6-1-sol/">Details →</a></td></tr>\n')
        i = t.index('<tr><td class="model-name">GPT-6 Sol <span')
        j = t.index('</tr>', i) + len('</tr>') + 1
        t = t[:j] + sol_row + t[j:]
        report.append('ok   en/pricing/index.html [sol row]')
        note_z = ('<div class="note-bar">🆕 <strong>Claude Haiku 5.5 added (2026-10-09):</strong> $0.10 input, $0.125 cache writes, $0.01 cache reads, $0.50 output per 1M tokens up to 100,000 tokens; above that $0.50 / $2.50. '
                  'We also <strong>corrected Sonnet 5.5 cache reads from $0.20 to $0.10</strong> (official source: <a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank" rel="noopener">platform.claude.com</a>).</div>\n')
        note_o = ('<div class="note-bar">🆕 <strong>GPT-6.1 Sol added (2026-10-09):</strong> $2 input, $0.10 cached input (5% of input), $2.50 cache writes, $10 output per 1M tokens. '
                  'Prompts above 272,000 input tokens are repriced at 2x input and 1.5x output for the full request. Verified on the official model page '
                  '(<a href="https://developers.openai.com/api/docs/models/gpt-6.1-sol" target="_blank" rel="noopener">source</a>).</div>\n')
    # note-bar を各テーブルの直前に挿入
    i = t.index('<tr><td class="model-name">Claude Sonnet 5.5 <span')
    k = t.rfind('<div class="table-wrap">', 0, i)
    t = t[:k] + note_z + t[k:]
    i = t.index('<tr><td class="model-name">GPT-6 Sol <span')
    k = t.rfind('<div class="table-wrap">', 0, i)
    t = t[:k] + note_o + t[k:]
    report.append(f"ok   {rel} [note-bars]")
    write(rel, t)

# =====================================================================
# 2) HOME (cards + dates)
# =====================================================================
ja_cards = (
 '<article class="card"><div class="card-icon">🏎️</div><h3 class="card-title">Claude Haiku 5.5 — Claude 5.5世代の最速・最安（$0.10/$0.50）</h3>'
 '<p class="card-desc">2026-10-07公開。入力$0.10・出力$0.50は<strong>Haiku 4.5の10分の1</strong>（100,000トークンまで）。'
 '100k超は入力$0.50・出力$2.50の<strong>2段階</strong>、キャッシュ読込$0.01、1Mコンテキスト。'
 '新しいトークナイザーで同じ文面が約30%多くカウントされる点も明記しました。</p>'
 '<a href="/claude-haiku-5-5/" class="card-link">Haiku 5.5詳細を見る →</a></article>\n'
 '<article class="card"><div class="card-icon">🛰️</div><h3 class="card-title">GPT-6.1 Sol — GPT-6世代のバランス型（$2/$10・キャッシュ入力$0.10）</h3>'
 '<p class="card-desc">入力$2・出力$10はGPT-6 Solと同額で、<strong>キャッシュ入力は$0.10に半減</strong>。'
 '272,000トークン超の入力はリクエスト全体が入力2倍・出力1.5倍、Fastは2倍・Ultrafastは6倍。'
 '1.05Mコンテキスト、effortはlow〜max（<code>none</code>非対応）。</p>'
 '<a href="/gpt-6-1-sol/" class="card-link">GPT-6.1 Sol詳細を見る →</a></article>\n')
en_cards = (
 '<article class="card"><div class="card-icon">🏎️</div><h3 class="card-title">Claude Haiku 5.5 — fastest and cheapest of the Claude 5.5 family ($0.10/$0.50)</h3>'
 '<p class="card-desc">Released 2026-10-07. At $0.10 input / $0.50 output it is <strong>one tenth of Haiku 4.5</strong> up to 100,000 tokens; above that a <strong>second tier</strong> applies ($0.50 / $2.50). '
 'Cache reads $0.01, 1M context, and the new tokenizer that counts the same text as roughly 30% more tokens.</p>'
 '<a href="/en/claude-haiku-5-5/" class="card-link">Haiku 5.5 deep dive →</a></article>\n'
 '<article class="card"><div class="card-icon">🛰️</div><h3 class="card-title">GPT-6.1 Sol — the balanced model of the GPT-6 family ($2/$10, $0.10 cached input)</h3>'
 '<p class="card-desc">$2 input / $10 output matches GPT-6 Sol, while <strong>cached input halves to $0.10</strong>. '
 'Prompts above 272,000 input tokens are repriced at 2x input and 1.5x output for the whole request; Fast is 2x, Ultrafast 6x. '
 '1.05M context, reasoning effort low to max (no <code>none</code>).</p>'
 '<a href="/en/gpt-6-1-sol/" class="card-link">GPT-6.1 Sol deep dive →</a></article>\n')

for rel, ja in (('index.html', True), ('en/index.html', False)):
    backup(rel); t = read(rel)
    cards = ja_cards if ja else en_cards
    needle = 'Claude Sonnet 5.5 — Claude 5.5世代のバランス型' if ja else '<h3 class="card-title">Claude Sonnet 5.5 — the balanced model'
    i = t.index(needle)
    j = t.index('</article>', i) + len('</article>') + 1
    t = t[:j] + cards + t[j:]
    report.append(f"ok   {rel} [cards]")
    if ja:
        t = one(rel, t, '<time datetime="2026-10-05">2026年10月5日</time>',
                '<time datetime="2026-10-09">2026年10月9日</time> — Claude Haiku 5.5・GPT-6.1 Sol を追加', 'updated-bar')
        t = one(rel, t, '"dateModified":"2026-10-05"', '"dateModified":"2026-10-09"', 'ld date')
        t = rx(rel, t, r'(<meta name="description" content=".*?)(">)',
               r'\1 Claude Haiku 5.5（$0.10/$0.50）・GPT-6.1 Sol（$2/$10・キャッシュ入力$0.10）を反映。\2', 'meta desc')
    else:
        t = one(rel, t, '"dateModified":"2026-10-05"', '"dateModified":"2026-10-09"', 'ld date', required=False)
        t = rx(rel, t, r'(<meta name="description" content=".*?)(">)',
               r'\1 Now covering Claude Haiku 5.5 ($0.10/$0.50) and GPT-6.1 Sol ($2/$10, $0.10 cached input).\2', 'meta desc')
        t = rx(rel, t, r'<time datetime="2026-10-0\d">[^<]*</time>',
               '<time datetime="2026-10-09">October 9, 2026</time>', 'updated-bar', required=False)
    write(rel, t)

# =====================================================================
# 3) TIMELINE
# =====================================================================
tl_ja_new = (
 '<article class="tl-item dot-openai" id="gpt-6-1-sol"><div class="tl-card"><div class="tl-date">2026-09-29 <span class="tl-provider-tag openai">OpenAI</span></div>'
 '<h2 class="tl-title">GPT-6.1 Sol 公開 — GPT-6世代のバランス型、Solと同額でキャッシュ入力は半額に <span class="badge badge-new" style="font-size:.7rem;">New</span></h2>'
 '<p class="tl-desc"><strong>位置づけ</strong>: 公式モデルページの説明は「Near-Astra performance for complex work at a lower cost」。GPT-6世代のバランス型で、モデルIDは <code>gpt-6.1-sol</code>。<br>'
 '<strong>料金</strong>: 入力$2・出力$10（GPT-6 Solと同額）、<strong>キャッシュ入力$0.10（入力の5%）</strong>、キャッシュ書込$2.50。<strong>272,000トークン超の入力はリクエスト全体が入力2倍・出力1.5倍</strong>。Fastは2倍・Ultrafastは6倍・Batch/Flexは50%引き。<br>'
 '<strong>仕様</strong>: 1,050,000コンテキスト・最大出力128,000・最大入力922,000・知識カットオフ2026-04-30。reasoning effortはlow/medium（既定）/high/xhigh/maxで、<code>none</code>と<code>minimal</code>は非対応（GPT-6 Solは<code>none</code>対応）。<br>'
 '<strong>日付について</strong>: OpenAIのモデルページにリリース日の記載がないため、当サイトは第三者報道の日付を「第三者情報」と明記して掲載しています。'
 '<span class="tl-price-badge">$2/$10（キャッシュ入力$0.10・書込$2.50）</span></p>'
 '<div class="tl-links"><a href="https://developers.openai.com/api/docs/models/gpt-6.1-sol" target="_blank" rel="noopener">OpenAIモデルページ →</a><a href="/gpt-6-1-sol/">詳細ページ →</a></div>'
 '</div></article>\n')
tl_ja_haiku = (
 '<article class="tl-item dot-anthropic" id="claude-haiku-5-5"><div class="tl-card"><div class="tl-date">2026-10-07 <span class="tl-provider-tag anthropic">Anthropic</span></div>'
 '<h2 class="tl-title">Claude Haiku 5.5 公開 — Claude 5.5世代の最速・最安、料金はHaiku 4.5の10分の1 <span class="badge badge-new" style="font-size:.7rem;">New</span></h2>'
 '<p class="tl-desc"><strong>料金</strong>: 入力$0.10・出力$0.50（USD/1M、100,000トークンまで）でHaiku 4.5の$1.00/$5.00から<strong>10分の1</strong>。100,000トークン超は入力$0.50・出力$2.50の2段階。キャッシュ読込$0.01（100k超は$0.05）、キャッシュ書込は5分$0.125／1時間$0.20。<br>'
 '<strong>仕様</strong>: 1Mコンテキスト・最大出力128K（Batch APIのベータヘッダで300K）・thinkingはAdaptiveで既定ON（既定effort <code>medium</code>）・レイテンシはFastest・知識カットオフ2026年6月。<br>'
 '<strong>注意</strong>: Claude 4.7以降と同じ新しいトークナイザーのため、同じ文面が Haiku 4.5 より<strong>約30%多くトークンとしてカウント</strong>されます。<code>temperature</code>・<code>top_p</code>・<code>top_k</code>は非デフォルト値で400エラー。'
 '<span class="tl-price-badge">$0.10/$0.50（100k超 $0.50/$2.50）</span></p>'
 '<div class="tl-links"><a href="https://platform.claude.com/docs/en/models/haiku-5-5/overview" target="_blank" rel="noopener">Claude Platform Docs →</a><a href="/claude-haiku-5-5/">詳細ページ →</a></div>'
 '</div></article>\n')
tl_en_new = (
 '<article class="tl-item dot-openai" id="gpt-6-1-sol"><div class="tl-card"><div class="tl-date">2026-09-29 <span class="tl-provider-tag openai">OpenAI</span></div>'
 '<h2 class="tl-title">GPT-6.1 Sol released — the balanced GPT-6 model, same price as Sol with cached input halved <span class="badge badge-new" style="font-size:.7rem;">New</span></h2>'
 '<p class="tl-desc"><strong>Positioning</strong>: the official model page says “Near-Astra performance for complex work at a lower cost”. Model ID <code>gpt-6.1-sol</code>.<br>'
 '<strong>Pricing</strong>: $2 input / $10 output (same as GPT-6 Sol), <strong>$0.10 cached input (5% of input)</strong>, $2.50 cache writes. <strong>Prompts above 272,000 input tokens are repriced at 2x input and 1.5x output for the whole request.</strong> Fast 2x, Ultrafast 6x, Batch/Flex 50% off.<br>'
 '<strong>Specs</strong>: 1,050,000 context, 128,000 max output, 922,000 max input, knowledge cutoff 2026-04-30. Reasoning effort low / medium (default) / high / xhigh / max; <code>none</code> and <code>minimal</code> are not supported (GPT-6 Sol supports <code>none</code>).<br>'
 '<strong>On the date</strong>: the model page states no release date, so we publish the date reported by third parties and label it as third-party information. '
 '<span class="tl-price-badge">$2/$10 ($0.10 cached input, $2.50 writes)</span></p>'
 '<div class="tl-links"><a href="https://developers.openai.com/api/docs/models/gpt-6.1-sol" target="_blank" rel="noopener">OpenAI model page →</a><a href="/en/gpt-6-1-sol/">Deep dive →</a></div>'
 '</div></article>\n')
tl_en_haiku = (
 '<article class="tl-item dot-anthropic" id="claude-haiku-5-5"><div class="tl-card"><div class="tl-date">2026-10-07 <span class="tl-provider-tag anthropic">Anthropic</span></div>'
 '<h2 class="tl-title">Claude Haiku 5.5 released — fastest and cheapest of the Claude 5.5 family at one tenth of Haiku 4.5 <span class="badge badge-new" style="font-size:.7rem;">New</span></h2>'
 '<p class="tl-desc"><strong>Pricing</strong>: $0.10 input / $0.50 output per 1M tokens up to 100,000 tokens — <strong>one tenth of Haiku 4.5</strong> ($1.00/$5.00). Above 100,000 tokens the rates become $0.50 / $2.50. Cache reads $0.01 ($0.05 above 100k); cache writes $0.125 for 5 minutes and $0.20 for one hour.<br>'
 '<strong>Specs</strong>: 1M context, 128K max output (300K on the Batch API with a beta header), adaptive thinking on by default at effort <code>medium</code>, Fastest latency, knowledge cutoff June 2026.<br>'
 '<strong>Caveats</strong>: the new tokenizer shared with Claude 4.7 and later counts the same text as <strong>roughly 30% more tokens</strong> than Haiku 4.5, and <code>temperature</code>, <code>top_p</code> or <code>top_k</code> return a 400 error when set to non-default values. '
 '<span class="tl-price-badge">$0.10/$0.50 (above 100k: $0.50/$2.50)</span></p>'
 '<div class="tl-links"><a href="https://platform.claude.com/docs/en/models/haiku-5-5/overview" target="_blank" rel="noopener">Claude Platform Docs →</a><a href="/en/claude-haiku-5-5/">Deep dive →</a></div>'
 '</div></article>\n')

for rel, ja in (('timeline/index.html', True), ('en/timeline/index.html', False)):
    backup(rel); t = read(rel)
    a, b = (tl_ja_new, tl_ja_haiku) if ja else (tl_en_new, tl_en_haiku)
    i = t.index('<article class="tl-item dot-google" id="gemini-4-argon">')
    t = t[:i] + a + t[i:]
    j = t.rindex('</article>') + len('</article>') + 1
    t = t[:j] + b + t[j:]
    report.append(f"ok   {rel} [2 entries]")
    t = rx(rel, t, r'<time datetime="2026-10-0\d">[^<]*</time>',
           ('<time datetime="2026-10-09">2026年10月9日</time>' if ja else '<time datetime="2026-10-09">October 9, 2026</time>'), 'updated-bar')
    t = one(rel, t, '"dateModified":"2026-10-05"', '"dateModified":"2026-10-09"', 'ld date', required=False)
    write(rel, t)

# =====================================================================
# 4) MULTIMODAL
# =====================================================================
for rel, ja in (('multimodal/index.html', True), ('en/multimodal/index.html', False)):
    backup(rel); t = read(rel)
    if ja:
        new_row = ('<tr><td class="model-name">画像生成・編集</td><td>Gemini Nano Banana 2.1 <span class="badge badge-new">New</span><br>'
                   'Gemini 3.1 Flash Image（Nano Banana 2）<br>Gemini 3 Pro Image（Nano Banana Pro）</td>'
                   '<td>画像→画像</td><td class="price">Nano Banana 2.1: 出力画像 1K=$0.0336・2K=$0.0504・4K=$0.113（$7.50/M＋画像$30/M）<br>'
                   'Flash Image: $60/M（1K=$0.067）・Pro Image: $120/M（1K=$0.134）</td>'
                   '<td><a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noopener">Google</a></td></tr>')
        note = ('<div class="note-bar">🍌 <strong>Nano Banana 2.1 を追記（2026-10-09）:</strong> Google公式料金ページの「Gemini Nano Banana 2.1」は '
                '<strong>出力画像 $7.50/1M（テキスト・思考）＋ 画像 $30/1M</strong>、入力$1.50/1M。1枚あたりの目安は<strong>1K=$0.0336・2K=$0.0504・4K=$0.113</strong>（Batchは半額）で、'
                'Nano Banana 2（1K=$0.067）や Nano Banana Pro（1K=$0.134）より1枚単価が安いモデルです。</div>\n')
        old_row_pat = r'<tr><td class="model-name">画像生成・編集</td>.*?</tr>'
    else:
        new_row = ('<tr><td class="model-name">Image generation / edit</td><td>Gemini Nano Banana 2.1 <span class="badge badge-new">New</span><br>'
                   'Gemini 3.1 Flash Image (Nano Banana 2)<br>Gemini 3 Pro Image (Nano Banana Pro)</td>'
                   '<td>image→image</td><td class="price">Nano Banana 2.1: 1K=$0.0336 · 2K=$0.0504 · 4K=$0.113 per image ($7.50/M text + $30/M images)<br>'
                   'Flash Image: $60/M (1K=$0.067) · Pro Image: $120/M (1K=$0.134)</td>'
                   '<td><a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noopener">Google</a></td></tr>')
        note = ('<div class="note-bar">🍌 <strong>Nano Banana 2.1 added (2026-10-09):</strong> Google\'s official pricing page lists “Gemini Nano Banana 2.1” at '
                '<strong>$7.50/1M output images (text and thinking) plus $30/1M images</strong>, with $1.50/1M input. That works out to about '
                '<strong>$0.0336 (1K), $0.0504 (2K) and $0.113 (4K) per image</strong> (half on Batch) — cheaper per image than Nano Banana 2 ($0.067 at 1K) or Nano Banana Pro ($0.134).</div>\n')
        old_row_pat = r'<tr><td class="model-name">Image generation / edit</td>.*?</tr>'
    t = rx(rel, t, old_row_pat, new_row.replace('\\', '\\\\'), 'image row')
    i = t.index('Nano Banana 2.1')
    k = t.index('<div class="note-bar">', i)
    t = t[:k] + note + t[k:]
    report.append(f"ok   {rel} [note-bar]")
    t = rx(rel, t, r'<time datetime="2026-0[0-9]-[0-9]{2}">[^<]*</time>',
           ('<time datetime="2026-10-09">2026年10月9日</time>' if ja else '<time datetime="2026-10-09">October 9, 2026</time>'),
           'updated-bar', required=False, count=1)
    t = one(rel, t, '"dateModified":"2026-10-01"', '"dateModified":"2026-10-09"', 'ld date', required=False)
    t = one(rel, t, '"dateModified":"2026-09-23"', '"dateModified":"2026-10-09"', 'ld date2', required=False)
    write(rel, t)

# =====================================================================
# 5) GLOSSARY CTR (title/description)
# =====================================================================
gl = {
 'glossary/zero-operator-access/index.html': dict(
   title='ZOA（ゼロオペレーターアクセス）とは？「保存しない」と「見られない」の違いを5社の公式ドキュメントで比較 | LLM Data Hub',
   desc='ZOA（ゼロオペレーターアクセス）は、サービス運営者の担当者があなたのデータを復号・閲覧できないという約束で、ZDR（保存しない）とは別物です。アクセスを止める3つの層（手続き・鍵・実行環境）、鍵管理の3段階（CMK／BYOK／HYOK）、承認フロー（Microsoft Customer Lockbox・Google Access Approval・Key Access Justifications・OpenAI EKM）、AWS Bedrock・Microsoft・Google Cloud・OpenAI・Anthropicの記載を逐語で比較します。2026年10月9日更新。',
   ogt='ZOA（ゼロオペレーターアクセス）とは？「保存しない」と「見られない」の違いを5社比較'),
 'glossary/zero-data-retention/index.html': dict(
   title='ZDR（ゼロデータ保持）とは？「既定」なのに常時有効でない3つの落とし穴【5社比較】 | LLM Data Hub',
   desc='ZDR（ゼロデータ保持）は「既定」であって常時有効ではありません。保持が必要なモデルの例外リストがあり、保証には明示指定が要ります。ZDRとZOA（ゼロオペレーターアクセス）の違い、「学習に使わない」との違い、AWS Bedrock・OpenAI・Anthropic・Google・Microsoftの5社でどう入手するかを公式ドキュメントの逐語で比較。用語説明 第7回。2026年10月9日更新。',
   ogt='ZDR（ゼロデータ保持）とは？常時有効でない3つの落とし穴【5社比較】'),
 'en/glossary/zero-operator-access/index.html': dict(
   title='What Is Zero Operator Access (ZOA)? Not Retained vs Not Viewable, Compared Across Five Vendors | LLM Data Hub',
   desc='ZOA (zero operator access) means the operator&#39;s staff cannot decrypt or read your data — a different promise from ZDR. This page breaks down the three layers that stop access (process, keys, runtime), the three levels of key management (CMK vs BYOK vs HYOK), approval workflows (Microsoft Customer Lockbox, Google Access Approval, Key Access Justifications, OpenAI EKM), and what AWS Bedrock, Microsoft, Google Cloud, OpenAI and Anthropic each state, quoted verbatim. Updated October 9, 2026.',
   ogt='What Is Zero Operator Access (ZOA)? Not Retained vs Not Viewable, Five Vendors Compared'),
 'en/glossary/zero-data-retention/index.html': dict(
   title='Zero Data Retention (ZDR) Explained: 3 Catch Points and How 5 Vendors Grant It [Glossary #7] | LLM Data Hub',
   desc='Zero data retention (ZDR) is a default, not a guarantee — and not always on. Some models require retention, and coverage has to be requested explicitly. This page covers how ZDR differs from ZOA (zero operator access) and from &quot;not used for training&quot;, and how AWS Bedrock, OpenAI, Anthropic, Google and Microsoft each grant it, quoted from their official documentation. Glossary #7. Updated October 9, 2026.',
   ogt='Zero Data Retention (ZDR) Explained: 3 Catch Points, 5 Vendors Compared [Glossary #7]'),
}
for rel, d in gl.items():
    backup(rel); t = read(rel)
    t = rx(rel, t, r'<title>.*?</title>', '<title>' + d['title'] + '</title>', 'title')
    t = rx(rel, t, r'<meta name="description" content=".*?">', '<meta name="description" content="' + d['desc'] + '">', 'meta desc')
    t = rx(rel, t, r'<meta property="og:title" content=".*?">', '<meta property="og:title" content="' + d['ogt'] + '">', 'og:title', required=False)
    t = rx(rel, t, r'<meta property="og:description" content=".*?">', '<meta property="og:description" content="' + d['desc'] + '">', 'og:desc', required=False)
    t = one(rel, t, '"dateModified":"2026-10-03"', '"dateModified":"2026-10-09"', 'ld date', required=False)
    t = one(rel, t, '"dateModified":"2026-10-05"', '"dateModified":"2026-10-09"', 'ld date2', required=False)
    write(rel, t)

print('\n'.join(report))
print('FAILS:', sum(1 for r in report if r.startswith('FAIL')))

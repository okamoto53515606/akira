# -*- coding: utf-8 -*-
"""2026-10-09: Sonnet 5.5 のキャッシュ読込単価 $0.20 -> $0.10 の訂正（日英）。"""
import pathlib, re
SITE = pathlib.Path('/tmp/site')
changed = []

def rep(rel, pairs):
    p = SITE / rel
    t = p.read_text(encoding='utf-8'); o = t
    for old, new, want in pairs:
        n = t.count(old)
        if want is not None and n != want:
            print(f"  !! {rel}: expected {want}, found {n} for {old[:70]!r}")
        if n:
            t = t.replace(old, new)
    if t != o:
        p.write_text(t, encoding='utf-8'); changed.append(rel)
    else:
        print("  -- no change:", rel)

# ================= JA =================
ja = 'claude-sonnet-5-5/index.html'
rep(ja, [
    ("キャッシュ読込$0.20・5分キャッシュ書込$2.50", "キャッシュ読込$0.10・5分キャッシュ書込$2.50", 1),
    ('content="入力$2・出力$10・1Mコンテキスト・128K出力（2026年10月1日更新）。Sonnet 5と同額で世代更新。',
     'content="入力$2・出力$10・キャッシュ読込$0.10・1Mコンテキスト（2026年10月9日更新）。入力と出力はSonnet 5と同額、キャッシュ読込は$0.20から半減。', 1),
    ('<tr><td class="model-name">キャッシュ読込（cache hit）</td><td class="price">$0.20</td><td>$0.20</td><td>$0.20</td></tr>',
     '<tr><td class="model-name">キャッシュ読込（cache hit）</td><td class="price">$0.10</td><td>$0.20</td><td>$0.20</td></tr>', 1),
    ("; 0.05x on Claude Opus 5.5)", "; 0.05x on Claude Opus 5.5 and Claude Sonnet 5.5)", 1),
    ("入力$2・キャッシュ読込$0.20は、", "入力$2・キャッシュ読込$0.10は、", 1),
    ("2026-10-01", "2026-10-09", None),
    ("2026年10月1日", "2026年10月9日", None),
    ('"datePublished":"2026-10-09"', '"datePublished":"2026-10-01"', 1),
    ('<time datetime="2026-10-09">2026年10月9日</time>',
     '<time datetime="2026-10-09">2026年10月9日</time><br><span style="color:var(--c-yellow);">⚠️ 2026-10-09: キャッシュ読込の単価を $0.20 → $0.10 に訂正しました（公式料金ドキュメントで再確認）。</span>', 1),
])
p = SITE / ja; t = p.read_text(encoding='utf-8')
old = "<li><strong>Sonnet 5.5は割引率こそ標準（cache hitは入力の10%）ですが、絶対額が安い</strong>ため、キャッシュ読込の実額は<strong>Fable 5.1の$0.25より安い$0.20</strong>です。割引率の深さと実額の安さは別物です。</li>"
new = "<li><strong>Sonnet 5.5のキャッシュ読込は入力の5%（$0.10）で、標準の10%より深い割引です。</strong>公式の逐語は「0.05x on Claude Opus 5.5 and Claude Sonnet 5.5」。実額でも<strong>Fable 5.1の$0.25・Opus 5.5の$0.20より安い$0.10</strong>です。割引率の深さと実額の安さは別物なので、両方を見てください。</li>"
assert t.count(old) == 1, "JA cache bullet not found"
t = t.replace(old, new)
anchor = '<li><strong>値下げではなく世代更新です。</strong>'
i = t.find(anchor); j = t.find('</li>', i) + 5
assert i > 0, "JA conclusion bullet not found"
add = ('<li><strong>ただしキャッシュ読込は$0.20→$0.10に半減しています。</strong>入力・出力の単価は前世代と同じですが、'
       '長い文脈を使い回すRAG・エージェント用途では実効コストが下がります（公式料金ページで2026-10-09に再確認）。</li>')
t = t[:j] + add + t[j:]
t, n = re.subn(r'<tr><td class="model-name">Claude Haiku 5.5</td>.*?</tr>',
    '<tr><td class="model-name"><a href="/claude-haiku-5-5/">Claude Haiku 5.5</a></td><td>個別ページあり</td>'
    '<td>Claude 5.5世代の最速・最安モデル。<strong>2026年10月7日に公開</strong>され、当サイトも個別ページを用意しました（$0.10/$0.50、100kトークン超は$0.50/$2.50）。</td></tr>',
    t, flags=re.S)
print("JA Haiku row replaced:", n)
p.write_text(t, encoding='utf-8')
changed.append(ja)

# ================= EN =================
en = 'en/claude-sonnet-5-5/index.html'
rep(en, [
    ("$0.20 cache reads, 1M context", "$0.10 cache reads, 1M context", 1),
    ("updated October 1, 2026", "updated October 9, 2026", 1),
    ('<tr><td class="model-name">Cache read (cache hit)</td><td class="price">$0.20</td><td>$0.20</td><td>$0.20</td></tr>',
     '<tr><td class="model-name">Cache read (cache hit)</td><td class="price">$0.10</td><td>$0.20</td><td>$0.20</td></tr>', 1),
    ("; 0.05x on Claude Opus 5.5)", "; 0.05x on Claude Opus 5.5 and Claude Sonnet 5.5)", 1),
    ("$2 input and $0.20 cache reads", "$2 input and $0.10 cache reads", 1),
    ("2026-10-01", "2026-10-09", None),
    ('"datePublished":"2026-10-09"', '"datePublished":"2026-10-01"', 1),
    ('<time datetime="2026-10-09">October 9, 2026</time>',
     '<time datetime="2026-10-09">October 9, 2026</time><br><span style="color:var(--c-yellow);">⚠️ 2026-10-09: corrected the cache-read price from $0.20 to $0.10 after re-checking the official pricing docs.</span>', 1),
])
p = SITE / en; t = p.read_text(encoding='utf-8')
old = ("<li><strong>Sonnet 5.5 uses the standard cache discount (10% of input), but the absolute number is low:</strong> "
       "$0.20 per 1M cached tokens — <strong>cheaper in cash terms than Fable 5.1's $0.25</strong>, even though Fable 5.1 gets the deeper 2.5% multiplier. "
       "Discount depth and absolute cost are different things.</li>")
new = ("<li><strong>Sonnet 5.5's cache read is 5% of input ($0.10) — deeper than the standard 10% discount.</strong> "
       "The docs say &ldquo;0.05x on Claude Opus 5.5 and Claude Sonnet 5.5&rdquo;. In cash terms it undercuts both Fable 5.1's $0.25 and Opus 5.5's $0.20. "
       "Discount depth and absolute cost are different things, so look at both.</li>")
assert t.count(old) == 1, "EN cache bullet not found"
t = t.replace(old, new)
anchor = '<li><strong>This is a generation update, not a price cut.</strong>'
i = t.find(anchor); j = t.find('</li>', i) + 5
assert i > 0, "EN conclusion bullet not found"
add = ('<li><strong>Cached input, however, is halved: $0.20 &rarr; $0.10.</strong> Input and output match the previous generation, '
       'but long reused contexts (RAG, agents) get cheaper in practice (re-verified on the official pricing page on 2026-10-09).</li>')
t = t[:j] + add + t[j:]
t, n = re.subn(r'<tr><td class="model-name">Claude Haiku 5.5</td>.*?</tr>',
    '<tr><td class="model-name"><a href="/en/claude-haiku-5-5/">Claude Haiku 5.5</a></td><td>Dedicated page</td>'
    '<td>The fastest and cheapest model of the Claude 5.5 family. <strong>Released October 7, 2026</strong>; we published a dedicated page ($0.10/$0.50, and $0.50/$2.50 above 100k tokens).</td></tr>',
    t, flags=re.S)
print("EN Haiku row replaced:", n)
p.write_text(t, encoding='utf-8')
changed.append(en)
print("changed:", sorted(set(changed)))

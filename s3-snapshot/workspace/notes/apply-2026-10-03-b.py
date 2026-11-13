#!/usr/bin/env python3
# 2026-10-03 追加依頼（最小スコープ）: timeline Argon / mai 新発表 / ZOA 指摘2点 / sitemap
# 使い方: python3 apply-2026-10-03-b.py   (SITE=/tmp/site)
import os, re, sys

SITE = os.environ.get("SITE", "/tmp/site")
OPS = []
def rep(path, old, new, count=1): OPS.append(("rep", path, old, new, count))
def ins_after_last(path, needle, text): OPS.append(("last", path, needle, text, 1))
def ins_before(path, anchor, text):
    real = anchor if anchor in open(os.path.join(SITE, path), encoding="utf-8").read() else None
    OPS.append(("before", path, anchor, text, 1))

# ---------------------------------------------------------------- timeline JA
TJ = "timeline/index.html"
rep(TJ, "・Claude Fable 5.1まで", "・Claude Fable 5.1・Gemini 4 Argonまで")
rep(TJ, "Grok 4.7対応。", "Grok 4.7・Gemini 4 Argon対応。")
rep(TJ, '最終更新: <time datetime="2026-10-01">2026年10月1日</time>',
        '最終更新: <time datetime="2026-10-03">2026年10月3日</time>')
rep(TJ, '"dateModified":"2026-10-01"', '"dateModified":"2026-10-03"')

ARGON_JA = (
'<article class="tl-item dot-google" id="gemini-4-argon"><div class="tl-card">'
'<div class="tl-date">2026-09-30 <span class="tl-provider-tag google">Google</span></div>'
'<h2 class="tl-title">Gemini 4 Argon 発表 — サイバー防御の「信頼できるテスター」へ先行提供、一般提供は段階的 <span class="badge badge-new" style="font-size:.7rem;">New</span></h2>'
'<p class="tl-desc">新フロンティアモデル。'
'<strong>提供段階</strong>: ①Fairwind Program の trusted cyber defenders（招待されたサイバー防御関係者）に段階提供中 → '
'②開発者・企業・消費者へ「as soon as possible（できるだけ早く）」で、'
'<strong>その順序は paid API customers と Google AI Ultra 購読者から</strong>と公式ブログに明記。'
'Google は米国政府の事前アクセス自主プロセスに参加しつつ、ガードレールを反復して提供範囲を広げるとしています。'
'<strong>現時点の入手経路は Fairwind Program（招待制）のみ</strong>で、一般の API・コンシューマ経路は未提供です。'
'コンテキストは <strong>100万トークン</strong>。'
'価格は「導入価格（introductory price）として <strong>入力 $2 / 出力 $10 / キャッシュ入力は入力価格から95%off</strong>」の予告で、公式ブログに課金開始の記載はありません。'
'<strong>公式ブログにベンチマーク表は未掲載</strong>のため、当サイトでは集約サイトのスコアを数値として掲載しません（言及する場合は「〜との報道」に留めます）。'
'<span class="tl-price-badge">導入価格 予告 $2/$10（キャッシュ入力95%off）</span></p>'
'<div class="tl-links"><a href="https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/" target="_blank" rel="noopener">Google公式ブログ →</a>'
'<a href="/pricing/#gh">料金比較 →</a></div></div></article>'
)
ins_after_last(TJ, "</article>", "\n" + ARGON_JA)

# ---------------------------------------------------------------- timeline EN
TE = "en/timeline/index.html"
rep(TE, "Claude Fable 5.1, Claude Opus 5, and the GPT-5.6 price cuts.",
        "Claude Fable 5.1, Claude Opus 5, Grok 4.7, Gemini 4 Argon and the GPT-5.6 price cuts.")
rep(TE, 'Last updated: <time datetime="2026-10-01">October 1, 2026</time>',
        'Last updated: <time datetime="2026-10-03">October 3, 2026</time>')
rep(TE, '"dateModified":"2026-10-01"', '"dateModified":"2026-10-03"')

ARGON_EN = (
'<article class="tl-item dot-google" id="gemini-4-argon"><div class="tl-card">'
'<div class="tl-date">2026-09-30 <span class="tl-provider-tag google">Google</span></div>'
'<h2 class="tl-title">Gemini 4 Argon announced — rolling out to trusted cyber defenders first, general access phased <span class="badge badge-new" style="font-size:.7rem;">New</span></h2>'
'<p class="tl-desc">A new frontier model. '
'<strong>Release stages</strong>: (1) rolling out now to a set of trusted cyber defenders through the Fairwind Program; '
'(2) to developers, enterprises and consumers "as soon as possible", <strong>starting with paid API customers and Google AI Ultra subscribers</strong> per the official post. '
'Google says it is engaged in the U.S. government\'s voluntary pre-release access process while it iterates on guardrails and gradually expands access. '
'<strong>The only route available today is the Fairwind Program (invitation-based)</strong> — no general API or consumer access yet. '
'Context: <strong>1 million tokens</strong>. '
'Pricing is announced as an introductory price of <strong>$2 per 1M input tokens / $10 per 1M output tokens, with cached input at 95% off the input price</strong>; the post does not state that billing has started. '
'<strong>The official post publishes no benchmark table</strong>, so we do not list aggregate-site scores as numbers here (any mention stays at the level of "as reported by ...").'
'<span class="tl-price-badge">Announced intro price $2/$10 (cached input 95% off)</span></p>'
'<div class="tl-links"><a href="https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/" target="_blank" rel="noopener">Google blog →</a>'
'<a href="/en/pricing/#gh">Pricing →</a></div></div></article>'
)
ins_after_last(TE, "</article>", "\n" + ARGON_EN)

# ---------------------------------------------------------------- mai JA
MJ = "mai/index.html"
rep(MJ, "特集【2026年9月版】", "特集【2026年10月版】", count=3)
rep(MJ, "MAI-Transcribe-2（音声認識・$0.10/時）", "MAI-Transcribe-2-Streaming / MAI-Transcribe-2（音声認識）")
rep(MJ, "MAI-Image-2.6/2.6-Flashのstarts at価格も掲載。2026年9月19日更新。",
        "MAI-Image-2.6/2.6-Flashのstarts at価格も掲載。2026年10月2日のMAI-Transcribe-2-Streaming（$0.54/時・年内の導入価格）とMAI-Voice-2.1/2.1-Flashも追記。2026年10月3日更新。")
rep(MJ, "リリース年表を一次情報で整理。", "リリース年表を一次情報で整理。最新の音声認識モデル（2026-10-02発表）も反映。")
rep(MJ, 'name":"LLM Data Hub"},"publisher"', 'name":"LLM Data Hub"},"publisher"')  # noop guard
rep(MJ, '"dateModified":"2026-09-19"', '"dateModified":"2026-10-03"')
rep(MJ, '最終更新: <time datetime="2026-09-19">2026年9月19日</time>',
        '最終更新: <time datetime="2026-10-03">2026年10月3日</time>')
rep(MJ, '<div class="stat"><div class="val">$0.10/時</div><div class="lbl">MAI-Transcribe-2（限定）</div></div>',
        '<div class="stat"><div class="val">$0.54/時</div><div class="lbl">Transcribe-2-Streaming（年内）</div></div>\n    '
        '<div class="stat"><div class="val">$0.10/時</div><div class="lbl">MAI-Transcribe-2（限定）</div></div>')
rep(MJ, 'id="latest-h">最新モデル（2026年9月）</h2>', 'id="latest-h">最新モデル（2026年10月）</h2>')
rep(MJ, "microsoft.ai 公式ブログで確認できる最も新しい2系統。どちらも Microsoft Foundry / MAI Playground で試せます。",
        "microsoft.ai 公式ブログで確認できる直近の発表（2026-10-02分を含む）。いずれも Microsoft Foundry / MAI Playground などで試せます。")
rep(MJ, "確認日 2026-09-09（2026-09-19に再確認。MAI-Image-2.6 系は依然として同表に未掲載、既存行の単価に変更なし）。",
        "確認日 2026-09-09（2026-10-03に再確認。MAI-Image-2.6 系・MAI-Transcribe-2-Streaming・MAI-Voice-2.1 系はいずれも同表に未掲載、既存行の単価に変更なし）。")
rep(MJ, "ai-foundry-models/microsoft/</a>（確認 2026-09-19）", "ai-foundry-models/microsoft/</a>（確認 2026-10-03）")
rep(MJ, "（2026-09-04付・確認 2026-09-19）", "（2026-09-04付・確認 2026-10-03）")

BOX_JA = (
'<div class="tip-box" style="margin-bottom:1rem;border-left-color:var(--c-accent2);">\n'
'  <h3 style="margin-bottom:.3rem;">🎧 MAI-Transcribe-2-Streaming（ストリーミング音声認識）— 2026-10-02</h3>\n'
'  <p style="font-size:.88rem;color:var(--c-muted);margin:0 0 .5rem;">MAI 初の<strong>ストリーミング音声認識モデル</strong>。話し終わりを待たずに、<strong>音声を受け取ってから約100msで partial（暫定結果）</strong>を返します。<strong>60言語</strong>に対応し、言語の自動・継続的な検出も可能。公式ブログの記載では<strong>音声1時間あたり $0.54（年内の導入価格）</strong>、入手経路は <strong>Microsoft Foundry / MAI Playground / OpenRouter / Vercel / Azure Voice Live</strong>（LiveKit も「coming soon」）。併せて<strong>音声生成の MAI-Voice-2.1 / 2.1-Flash</strong>（23言語・26ロケール）も発表され、公式ブログの記載は 2.1 が <strong>$22 / 100万文字</strong>、2.1-Flash が <strong>$15 / 100万文字</strong>です。<strong>Azure Foundry の確認済み料金表（Microsoft セクション）には、2026-10-03 時点で本モデル・MAI-Voice-2.1 系とも未掲載</strong>のため、上記はすべて公式ブログの記載です。</p>\n'
'  <p style="font-size:.85rem;color:var(--c-muted);margin:0;"><strong>公式ブログの逐語:</strong> <span style="font-family:ui-monospace,Menlo,monospace;font-size:.78rem;">&quot;MAI-Transcribe-2-Streaming delivers low-latency, real-time transcripts in 60 languages, all while supporting automatic, continuous language detection.&quot;</span> / <span style="font-family:ui-monospace,Menlo,monospace;font-size:.78rem;">&quot;Rather than waiting for someone to finish speaking before returning text, it produces its first hypotheses (known as &quot;partials&quot;) in just over 100ms of receiving audio.&quot;</span> / <span style="font-family:ui-monospace,Menlo,monospace;font-size:.78rem;">&quot;MAI-Transcribe-2-Streaming is available at an introductory price of $0.54 per hour of audio through the end of the year.&quot;</span></p>\n'
'</div>\n'
)
rep(MJ, '<div class="tip-box" style="margin-bottom:1rem;">\n  <h3 style="margin-bottom:.3rem;">🖼️', BOX_JA + '<div class="tip-box" style="margin-bottom:1rem;">\n  <h3 style="margin-bottom:.3rem;">🖼️')

rep(MJ, '<a href="https://microsoft.ai/news/mai-transcribe-2-is-the-fastest-most-accurate-and-cheapest-speech-recognition-model-in-the-world/" target="_blank" rel="noopener">MAI-Transcribe-2（2026-09-03）</a></p>',
        '<a href="https://microsoft.ai/news/mai-transcribe-2-is-the-fastest-most-accurate-and-cheapest-speech-recognition-model-in-the-world/" target="_blank" rel="noopener">MAI-Transcribe-2（2026-09-03）</a> · '
        '<a href="https://microsoft.ai/news/our-first-streaming-transcription-model/" target="_blank" rel="noopener">Our first streaming transcription model（2026-10-02）</a></p>')

REF_JA = (
'<h3 style="font-size:1rem;margin:1.6rem 0 .5rem;">参考価格: MAI-Transcribe-2-Streaming / MAI-Voice-2.1 / 2.1-Flash（公式ブログの記載・Azure料金表には未掲載）</h3>\n'
'<p style="font-size:.88rem;color:var(--c-muted);margin-bottom:.6rem;">\n'
'  これら3モデルも、上の確認済み料金表（Azure Foundry Models pricing・Microsoft セクション）には<strong>掲載されていません</strong>（2026-10-03に再確認。MAI の行は9行のままで、Transcribe 系・Voice 系の行はありません）。\n'
'  そのため <a href="https://microsoft.ai/news/our-first-streaming-transcription-model/" target="_blank" rel="noopener">Our first streaming transcription model（2026-10-02）</a> の記載をそのまま掲載します。\n'
'</p>\n'
'<div class="table-wrap"><table><thead><tr><th>モデル</th><th>種別</th><th>公式ブログの記載</th></tr></thead><tbody>\n'
'<tr><td class="model-name">MAI-Transcribe-2-Streaming</td><td>ストリーミング音声認識</td><td class="price">$0.54 / 音声1時間（年内の導入価格）</td></tr>\n'
'<tr><td class="model-name">MAI-Voice-2.1</td><td>音声生成</td><td class="price">$22 / 100万文字</td></tr>\n'
'<tr><td class="model-name">MAI-Voice-2.1-Flash</td><td>音声生成（高速）</td><td class="price">$15 / 100万文字</td></tr>\n'
'</tbody></table></div>\n'
)
ins_before(MJ, '<div class="thinking-note"', REF_JA)

rep(MJ, '<li><strong>MAI-Code 系（MAI-Code-1-Flash / 1.1-Flash）</strong>も同表に無いため価格は未掲載。</li>',
        '<li><strong>MAI-Transcribe-2-Streaming / MAI-Voice-2.1 / 2.1-Flash</strong>も同じく確認済み料金表に未掲載のため、上記のとおり公式ブログの記載として掲載しています。<strong>MAI-Transcribe-2-Streaming の $0.54/時は「年末までの導入価格」</strong>と明記されている点に注意してください。</li>\n'
        '    <li><strong>MAI-Code 系（MAI-Code-1-Flash / 1.1-Flash）</strong>も同表に無いため価格は未掲載。</li>')

rep(MJ, '<tr><td class="model-name" style="border-left:3px solid var(--c-green);padding-left:.7rem;">2026-09-04 <span class="badge badge-new">New</span></td><td><strong>MAI-Image-2.6 / 2.6-Flash</strong>（画像生成）</td></tr>',
        '<tr><td class="model-name" style="border-left:3px solid var(--c-green);padding-left:.7rem;">2026-09-04 <span class="badge badge-new">New</span></td><td><strong>MAI-Image-2.6 / 2.6-Flash</strong>（画像生成）</td></tr>\n'
        '<tr><td class="model-name" style="border-left:3px solid var(--c-green);padding-left:.7rem;">2026-10-02 <span class="badge badge-new">New</span></td><td><strong>MAI-Transcribe-2-Streaming</strong>（ストリーミング音声認識・$0.54/時 年内導入価格）と <strong>MAI-Voice-2.1 / 2.1-Flash</strong>（音声生成）を発表</td></tr>')

rep(MJ, '<li><strong>モダリティの広がり</strong>',
        '<li><strong>音声認識の最新形（2026-10-02）</strong>: MAI-Transcribe-2-Streaming は60言語のストリーミング文字起こしで、話し終わりを待たずに約100msで暫定結果を返す設計。年内の導入価格は $0.54/時（公式ブログ記載）。Azure の確認済み料金表にはまだ未掲載です。</li>\n'
        '    <li><strong>モダリティの広がり</strong>')

rep(MJ, "料金・仕様は Microsoft の公式ページを 2026-09-19 に確認したものです（確認済み料金表の初回確認は 2026-09-09）",
        "料金・仕様は Microsoft の公式ページを 2026-10-03 に確認したものです（確認済み料金表の初回確認は 2026-09-09、2026-09-19・10-03 に再確認）")
rep(MJ, "MAI-Code 系・MAI-Voice 系の価格は一次情報に無いため未掲載です。",
        "MAI-Code 系・MAI-Voice 系の価格は一次情報に無いため未掲載です。MAI-Transcribe-2-Streaming / MAI-Voice-2.1 / 2.1-Flash も同じく公式ブログの記載（導入価格）であり、確認済み料金表には未掲載です。")

# ---------------------------------------------------------------- mai EN
ME = "en/mai/index.html"
rep(ME, "[September 2026]", "[October 2026]", count=3)
rep(ME, "MAI-Transcribe-2 (speech, $0.10/hour)", "MAI-Transcribe-2-Streaming / MAI-Transcribe-2 (speech)")
rep(ME, "verified against microsoft.ai and Azure Foundry. Updated September 19, 2026.",
        "verified against microsoft.ai and Azure Foundry. Includes the October 2, 2026 streaming transcription release. Updated October 3, 2026.")
rep(ME, "verified against primary sources.", "verified against primary sources. Includes the October 2, 2026 streaming transcription release.")
rep(ME, '"dateModified":"2026-09-19"', '"dateModified":"2026-10-03"')
rep(ME, 'Last updated: <time datetime="2026-09-19">September 19, 2026</time>',
        'Last updated: <time datetime="2026-10-03">October 3, 2026</time>')
rep(ME, '<div class="stat"><div class="val">$0.10/hr</div><div class="lbl">MAI-Transcribe-2 (limited)</div></div>',
        '<div class="stat"><div class="val">$0.54/hr</div><div class="lbl">Transcribe-2-Streaming (2026)</div></div>\n    '
        '<div class="stat"><div class="val">$0.10/hr</div><div class="lbl">MAI-Transcribe-2 (limited)</div></div>')
rep(ME, 'id="latest-h">Latest models (September 2026)</h2>', 'id="latest-h">Latest models (October 2026)</h2>')
rep(ME, "The two newest families confirmed on the microsoft.ai blog. Both can be tried via Microsoft Foundry / MAI Playground.",
        "The most recent launches confirmed on the microsoft.ai blog, including the October 2, 2026 release. All are available via Microsoft Foundry / MAI Playground and other routes.")
rep(ME, "Verified 2026-09-09 (re-checked 2026-09-19: the 2.6 family is still absent from that table and existing rows are unchanged).",
        "Verified 2026-09-09 (re-checked 2026-10-03: the 2.6 family, Transcribe-2-Streaming and the Voice-2.1 family are all still absent from that table, and existing rows are unchanged).")
rep(ME, "as of 2026-09-19.", "as of 2026-10-03.")
rep(ME, "ai-foundry-models/microsoft/</a> (verified 2026-09-19)", "ai-foundry-models/microsoft/</a> (verified 2026-10-03)")
rep(ME, "(2026-09-04; verified 2026-09-19)", "(2026-09-04; verified 2026-10-03)")

BOX_EN = (
'<div class="tip-box" style="margin-bottom:1rem;border-left-color:var(--c-accent2);">\n'
'  <h3 style="margin-bottom:.3rem;">🎧 MAI-Transcribe-2-Streaming (streaming speech recognition) — Oct 2, 2026</h3>\n'
'  <p style="font-size:.88rem;color:var(--c-muted);margin:0 0 .5rem;">MAI\'s first <strong>streaming speech recognition model</strong>. Instead of waiting for the speaker to finish, it returns its <strong>first partial result in just over 100ms</strong> of receiving audio, covers <strong>60 languages</strong>, and supports automatic continuous language detection. The official post lists <strong>$0.54 per hour of audio (introductory price through the end of the year)</strong>, with access via <strong>Microsoft Foundry / MAI Playground / OpenRouter / Vercel / Azure Voice Live</strong> (LiveKit is "coming soon"). The same announcement introduces the speech-generation models <strong>MAI-Voice-2.1 / 2.1-Flash</strong> (23 languages, 26 locales), listed at <strong>$22 per 1M characters</strong> and <strong>$15 per 1M characters</strong> respectively. <strong>None of these appear in the verified Azure Foundry pricing table (Microsoft section) as of 2026-10-03</strong>, so all figures here are from the official blog.</p>\n'
'  <p style="font-size:.85rem;color:var(--c-muted);margin:0;"><strong>Verbatim from the official blog:</strong> <span style="font-family:ui-monospace,Menlo,monospace;font-size:.78rem;">&quot;MAI-Transcribe-2-Streaming delivers low-latency, real-time transcripts in 60 languages, all while supporting automatic, continuous language detection.&quot;</span> / <span style="font-family:ui-monospace,Menlo,monospace;font-size:.78rem;">&quot;Rather than waiting for someone to finish speaking before returning text, it produces its first hypotheses (known as &quot;partials&quot;) in just over 100ms of receiving audio.&quot;</span> / <span style="font-family:ui-monospace,Menlo,monospace;font-size:.78rem;">&quot;MAI-Transcribe-2-Streaming is available at an introductory price of $0.54 per hour of audio through the end of the year.&quot;</span></p>\n'
'</div>\n'
)
rep(ME, '<div class="tip-box" style="margin-bottom:1rem;">\n  <h3 style="margin-bottom:.3rem;">🖼️', BOX_EN + '<div class="tip-box" style="margin-bottom:1rem;">\n  <h3 style="margin-bottom:.3rem;">🖼️')

rep(ME, '<a href="https://microsoft.ai/news/mai-transcribe-2-is-the-fastest-most-accurate-and-cheapest-speech-recognition-model-in-the-world/" target="_blank" rel="noopener">MAI-Transcribe-2 (2026-09-03)</a></p>',
        '<a href="https://microsoft.ai/news/mai-transcribe-2-is-the-fastest-most-accurate-and-cheapest-speech-recognition-model-in-the-world/" target="_blank" rel="noopener">MAI-Transcribe-2 (2026-09-03)</a> · '
        '<a href="https://microsoft.ai/news/our-first-streaming-transcription-model/" target="_blank" rel="noopener">Our first streaming transcription model (2026-10-02)</a></p>')

REF_EN = (
'<h3 style="font-size:1rem;margin:1.6rem 0 .5rem;">Reference prices: MAI-Transcribe-2-Streaming / MAI-Voice-2.1 / 2.1-Flash (from the official blog; not in the pricing table)</h3>\n'
'<p style="font-size:.88rem;color:var(--c-muted);margin-bottom:.6rem;">\n'
'  These three models are also <strong>not in the verified table above</strong> (Azure Foundry Models pricing, Microsoft section) as of 2026-10-03: the Microsoft section still has nine MAI rows, with no Transcribe or Voice rows.\n'
'  So we publish the figures exactly as stated in the <a href="https://microsoft.ai/news/our-first-streaming-transcription-model/" target="_blank" rel="noopener">official post (2026-10-02)</a>.\n'
'</p>\n'
'<div class="table-wrap"><table><thead><tr><th>Model</th><th>Type</th><th>As stated on the official blog</th></tr></thead><tbody>\n'
'<tr><td class="model-name">MAI-Transcribe-2-Streaming</td><td>Streaming speech recognition</td><td class="price">$0.54 / hour of audio (introductory, through 2026)</td></tr>\n'
'<tr><td class="model-name">MAI-Voice-2.1</td><td>Speech generation</td><td class="price">$22 / 1M characters</td></tr>\n'
'<tr><td class="model-name">MAI-Voice-2.1-Flash</td><td>Speech generation (fast)</td><td class="price">$15 / 1M characters</td></tr>\n'
'</tbody></table></div>\n'
)
ins_before(ME, '<div class="thinking-note"', REF_EN)

rep(ME, '<li><strong>MAI-Code family (MAI-Code-1-Flash / 1.1-Flash)</strong> are also absent from that table, so pricing is omitted.</li>',
        '<li><strong>MAI-Transcribe-2-Streaming / MAI-Voice-2.1 / 2.1-Flash</strong> are likewise absent from the verified pricing table, so the figures above come from the official blog. Note that the <strong>$0.54/hour for MAI-Transcribe-2-Streaming is explicitly an introductory price through the end of the year</strong>.</li>\n'
        '    <li><strong>MAI-Code family (MAI-Code-1-Flash / 1.1-Flash)</strong> are also absent from that table, so pricing is omitted.</li>')

rep(ME, '<tr><td class="model-name" style="border-left:3px solid var(--c-green);padding-left:.7rem;">2026-09-04 <span class="badge badge-new">New</span></td><td><strong>MAI-Image-2.6 / 2.6-Flash</strong> (image generation)</td></tr>',
        '<tr><td class="model-name" style="border-left:3px solid var(--c-green);padding-left:.7rem;">2026-09-04 <span class="badge badge-new">New</span></td><td><strong>MAI-Image-2.6 / 2.6-Flash</strong> (image generation)</td></tr>\n'
        '<tr><td class="model-name" style="border-left:3px solid var(--c-green);padding-left:.7rem;">2026-10-02 <span class="badge badge-new">New</span></td><td><strong>MAI-Transcribe-2-Streaming</strong> (streaming speech recognition, $0.54/hr introductory through 2026) plus <strong>MAI-Voice-2.1 / 2.1-Flash</strong> (speech generation) announced</td></tr>')

rep(ME, '<li><strong>Broad modality coverage:</strong>',
        '<li><strong>Newest speech recognition (2026-10-02):</strong> MAI-Transcribe-2-Streaming transcribes 60 languages in streaming mode and returns a partial in about 100ms without waiting for the speaker to stop. Introductory price through the end of the year: $0.54/hour (official blog). It is not yet in the verified Azure pricing table.</li>\n'
        '    <li><strong>Broad modality coverage:</strong>')

rep(ME, "Pricing and specs were checked against Microsoft's official pages on 2026-09-19 (the verified pricing table was first checked on 2026-09-09)",
        "Pricing and specs were checked against Microsoft's official pages on 2026-10-03 (the verified pricing table was first checked on 2026-09-09, re-checked 2026-09-19 and 2026-10-03)")
rep(ME, "Prices for the MAI-Code and MAI-Voice families are omitted because no primary source figure exists.",
        "Prices for the MAI-Code and MAI-Voice families are omitted because no primary source figure exists. MAI-Transcribe-2-Streaming / MAI-Voice-2.1 / 2.1-Flash figures are likewise from the official blog (introductory pricing) and are not in the verified pricing table.")

# ---------------------------------------------------------------- ZOA JA
ZJ = "glossary/zero-operator-access/index.html"
rep(ZJ, "2026年10月1日更新。", "2026年10月3日更新。")
rep(ZJ, "（2026年10月1日更新）。", "（2026年10月3日更新）。")
rep(ZJ, '"dateModified":"2026-10-01"', '"dateModified":"2026-10-03"')
rep(ZJ, '最終更新: <time datetime="2026-10-01">2026年10月1日</time>',
        '最終更新: <time datetime="2026-10-03">2026年10月3日</time>')
rep(ZJ, '<p class="section-sub">「オペレーター」は<strong>サービスの運用担当者・サポートエンジニア・基盤管理者</strong>を指します。攻撃者や他テナントの話ではありません。<strong>ZOAは「運営者が悪意を持つ場合」まで含めて、そもそも読めないようにする</strong>という設計目標です。</p>',
        '<p class="section-sub">このページで「オペレーター（運営者）」というときは、<strong>クラウド事業者＝サービスを提供する側の運用担当者・サポートエンジニア・基盤管理者</strong>を指します（例: AWS の運用担当者）。攻撃者や他テナントの話ではありません。一方、<strong>そのクラウドを使う企業側の担当者（自社の情報システム部門・運用チームなど）は別の主体</strong>で、ZOA が約束する対象ではありません。つまり ZOA は「<strong>提供者側の人間が悪意を持つ場合</strong>まで含めて、そもそも読めないようにする」という設計目標で、<strong>自社側の担当者が読めるかどうかは、自社の権限設計・鍵管理の話</strong>になります。</p>')
rep(ZJ, '<tr><td><strong>運営者の社員は中身を読めるか</strong></td><td>読めない（設計上・手続き上）</td><td>「読めない」の担保方法は、手続き／鍵／実行環境の3通りあり、強度が違います。</td></tr>',
        '<tr><td><strong>クラウド事業者（運営者）の社員は中身を読めるか</strong></td><td>読めない（設計上・手続き上）</td><td>「読めない」の担保方法は、手続き／鍵／実行環境の3通りあり、強度が違います。</td></tr>\n'
        '      <tr><td><strong>自社（そのクラウドを使う企業）の運用担当者は読めるか</strong></td><td><strong>ZOAの対象外</strong></td><td>別の主体です。社内の権限設計次第で読めます。<strong>ZOAは「提供者側が読めない」約束</strong>で、社内の担当者が読めるかどうかは別の問題です。</td></tr>')
rep(ZJ, '<strong>「運営者」と「モデル提供元」は別の主体</strong>です。',
        '<strong>「クラウド事業者（運営者）」と「モデル提供元」は別の主体</strong>です。')
rep(ZJ, '<p class="section-sub">鍵の層と実行環境の層は技術の話ですが、<strong>現実のクラウドでは「運用担当者がどうしても触る必要がある場面」があります</strong>（障害調査・不正利用の調査など）。',
        '<p class="section-sub">鍵の層と実行環境の層は技術の話ですが、<strong>現実のクラウドでは「クラウド事業者側の運用担当者がどうしても触る必要がある場面」があります</strong>（障害調査・不正利用の調査など。<strong>そのクラウドを使う企業側の担当者の話ではありません</strong>）。')

NOTE_JA = (
'  <section class="section" style="padding-top:0;" aria-labelledby="param-h">\n'
'    <h2 class="section-title" id="param-h" style="font-size:1.1rem;">補足: モデルサイズの「◯B（Active ◯B）」という表記</h2>\n'
'    <div class="tip-box">\n'
'      <p style="font-size:.88rem;color:var(--c-muted);margin:.2rem 0;">モデルの紹介で「320B（18B Active）」のような書き方を見かけます。これは<strong>モデルの大きさを表すパラメータ数の表記</strong>で、<strong>B は 10億（billion）</strong>の意味です。同じ「B」でも、2つは別のものを指しています。</p>\n'
'      <ul style="margin:.5rem 0 0;padding-left:1.2rem;font-size:.88rem;color:var(--c-muted);">\n'
'        <li><strong>総パラメータ数（例: 320B）</strong>＝モデルが持っている重みの合計。<strong>モデルのファイルサイズや、動かすのに必要なメモリの目安</strong>になります。</li>\n'
'        <li><strong>Active（例: 18B Active）</strong>＝1つのトークンを出力するときに<strong>実際に計算へ使われる</strong>パラメータ数。専門家の分岐を持つ構造（MoE）のモデルでは、全体の一部だけが毎回使われます。</li>\n'
'      </ul>\n'
'      <p style="font-size:.88rem;color:var(--c-muted);margin:.6rem 0 0;">つまり「320B（18B Active）」は<strong>「320B 全部を毎回使うわけではない」</strong>という意味です。<strong>総数は載せられるか（メモリ）</strong>に、<strong>Active は計算量・速度・コスト</strong>に効いてくることが多く、総数が同じでも Active が違えば体感速度は変わります。<strong>当サイトでは、モデル提供元が公表した数値のみを掲載し、非公開の内訳は推測しません。</strong></p>\n'
'    </div>\n'
'  </section>\n'
)
ins_before(ZJ, 'aria-labelledby="rel-h"', NOTE_JA)

# ---------------------------------------------------------------- ZOA EN
ZE = "en/glossary/zero-operator-access/index.html"
rep(ZE, "Updated October 1, 2026.", "Updated October 3, 2026.")
rep(ZE, "(updated October 1, 2026).", "(updated October 3, 2026).")
rep(ZE, '"dateModified":"2026-10-01"', '"dateModified":"2026-10-03"')
rep(ZE, 'Last updated: <time datetime="2026-10-01">October 1, 2026</time>',
        'Last updated: <time datetime="2026-10-03">October 3, 2026</time>')
rep(ZE, '<p class="section-sub">"Operator" means <strong>service operations staff, support engineers and platform administrators</strong> — not attackers, and not other tenants. <strong>ZOA aims to make the data unreadable even if the operator were malicious.</strong></p>',
        '<p class="section-sub">In this page, "operator" (the party running the service) means <strong>operations staff, support engineers and platform administrators on the cloud provider\'s side</strong> — for example, AWS staff. It is not attackers, and not other tenants. <strong>Your own staff at the company using that cloud (your in-house IT and operations team) are a separate party</strong> and are not who ZOA covers: whether they can read the data is a question about your own access design and key management. <strong>ZOA aims to make the data unreadable even if the provider\'s operator were malicious.</strong></p>')
rep(ZE, '<tr><td><strong>Can the provider\'s employees read my content?</strong></td><td>No (by design or by process)</td><td>The enforcement mechanism differs — process, keys or runtime — and so does the strength.</td></tr>',
        '<tr><td><strong>Can the cloud provider\'s employees read my content?</strong></td><td>No (by design or by process)</td><td>The enforcement mechanism differs — process, keys or runtime — and so does the strength.</td></tr>\n'
        '      <tr><td><strong>Can my own operations staff (at the company using the cloud) read it?</strong></td><td><strong>Out of scope for ZOA</strong></td><td>They are a different party and can read it depending on your own permissions design. <strong>ZOA is a promise about the provider side</strong>; in-house access is a separate question.</td></tr>')
rep(ZE, '<strong>The operator and the model provider are different parties.</strong>',
        '<strong>The operator (the cloud provider) and the model provider are different parties.</strong>')
rep(ZE, '<p class="section-sub">Keys and runtimes are technical controls, but <strong>real operations sometimes require a human to touch the system</strong> (incident response, abuse investigation).',
        '<p class="section-sub">Keys and runtimes are technical controls, but <strong>real operations sometimes require a human on the provider side to touch the system</strong> (incident response, abuse investigation — not your own operations team).')

NOTE_EN = (
'  <section class="section" style="padding-top:0;" aria-labelledby="param-h">\n'
'    <h2 class="section-title" id="param-h" style="font-size:1.1rem;">Note: how to read "◯B (Active ◯B)" model sizes</h2>\n'
'    <div class="tip-box">\n'
'      <p style="font-size:.88rem;color:var(--c-muted);margin:.2rem 0;">Model write-ups often show figures like "320B (18B Active)". That is <strong>how parameter counts describe a model\'s size</strong>, and <strong>B means one billion</strong>. The two numbers are not the same thing.</p>\n'
'      <ul style="margin:.5rem 0 0;padding-left:1.2rem;font-size:.88rem;color:var(--c-muted);">\n'
'        <li><strong>Total parameters (e.g. 320B)</strong> — the sum of all the weights the model holds. It <strong>drives the file size and the memory needed to run it</strong>.</li>\n'
'        <li><strong>Active (e.g. 18B Active)</strong> — the parameters <strong>actually used in the computation</strong> for each generated token. In mixture-of-experts (MoE) models only part of the whole is used each time.</li>\n'
'      </ul>\n'
'      <p style="font-size:.88rem;color:var(--c-muted);margin:.6rem 0 0;">So "320B (18B Active)" means <strong>"all 320B are not used on every token"</strong>. <strong>The total tends to drive memory (can you fit it?)</strong>, while <strong>Active drives compute, speed and cost</strong> — the same total with a different Active count feels faster or slower. <strong>We only publish figures the model provider itself has released, and we do not infer undisclosed breakdowns.</strong></p>\n'
'    </div>\n'
'  </section>\n'
)
ins_before(ZE, 'aria-labelledby="rel-h"', NOTE_EN)

# ---------------------------------------------------------------- sitemap
SM = "sitemap.xml"
s = open(os.path.join(SITE, SM), encoding="utf-8").read()
targets = ["https://llm.okamomedia.tokyo/timeline/", "https://llm.okamomedia.tokyo/en/timeline/",
           "https://llm.okamomedia.tokyo/mai/", "https://llm.okamomedia.tokyo/en/mai/",
           "https://llm.okamomedia.tokyo/glossary/zero-operator-access/",
           "https://llm.okamomedia.tokyo/en/glossary/zero-operator-access/"]
sm_ok = []
for t in targets:
    pat = re.compile(r"(<loc>" + re.escape(t) + r"</loc>\s*<lastmod>)([^<]+)(</lastmod>)")
    s, n = pat.subn(lambda m: m.group(1) + "2026-10-03" + m.group(3), s)
    sm_ok.append((t, n))
open(os.path.join(SITE, SM), "w", encoding="utf-8").write(s)

# ---------------------------------------------------------------- apply
applied = skipped = failed = 0
for op in OPS:
    kind, path = op[0], op[1]
    p = os.path.join(SITE, path)
    s = open(p, encoding="utf-8").read()
    if kind == "rep":
        _, _, old, new, cnt = op
        found = s.count(old)
        if new != old and new in s:
            skipped += 1  # already applied (guards ops whose new text contains old)
        elif found == cnt:
            s = s.replace(old, new); open(p, "w", encoding="utf-8").write(s); applied += 1
        elif found == 0 and new in s:
            skipped += 1  # already applied
        else:
            failed += 1; print("FAIL rep", path, repr(old[:60]), "found=", found, "expected=", cnt)
    elif kind == "last":
        _, _, needle, text, _ = op
        i = s.rfind(needle)
        if text in s:
            skipped += 1
        elif i >= 0:
            s = s[:i + len(needle)] + text + s[i + len(needle):]
            open(p, "w", encoding="utf-8").write(s); applied += 1
        else:
            failed += 1; print("FAIL last", path, needle)
    elif kind == "before":
        _, _, anchor, text, _ = op
        i = s.find(anchor)
        if text in s:
            skipped += 1
        elif i >= 0:
            j = s.rfind("<section", 0, i)
            s = s[:j] + text + s[j:]
            open(p, "w", encoding="utf-8").write(s); applied += 1
        else:
            failed += 1; print("FAIL before", path, anchor)

print("applied=%d skipped(already)=%d failed=%d" % (applied, skipped, failed))
print("sitemap:", sm_ok)

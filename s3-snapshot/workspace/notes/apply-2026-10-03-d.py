#!/usr/bin/env python3
# 2026-10-03 D: Gemini(初心者目線)指摘の反映 — 用語の言い換え / 情報の重複圧縮 / 長文の改行
import os
SITE = os.environ.get("SITE", "/tmp/site")
OPS = []

# --- hero stat: 5個→4個に戻し、最新モデル1つに集約
OPS.append(("mai/index.html",
 '<div class="stat"><div class="val">$0.54/時</div><div class="lbl">Transcribe-2-Streaming（年内）</div></div>\n    <div class="stat"><div class="val">$0.10/時</div><div class="lbl">MAI-Transcribe-2（限定）</div></div>',
 '<div class="stat"><div class="val">$0.54/時</div><div class="lbl">Transcribe-2-Streaming（年内の導入価格）</div></div>'))
OPS.append(("en/mai/index.html",
 '<div class="stat"><div class="val">$0.54/hr</div><div class="lbl">Transcribe-2-Streaming (2026)</div></div>\n    <div class="stat"><div class="val">$0.10/hr</div><div class="lbl">MAI-Transcribe-2 (limited)</div></div>',
 '<div class="stat"><div class="val">$0.54/hr</div><div class="lbl">Transcribe-2-Streaming (intro)</div></div>'))

# --- 最新モデルのボックス: 価格の本文重複を圧縮し、用語をやさしく
OPS.append(("mai/index.html",
 'MAI 初の<strong>ストリーミング音声認識モデル</strong>。話し終わりを待たずに、<strong>音声を受け取ってから約100msで partial（暫定結果）</strong>を返します。<strong>60言語</strong>に対応し、言語の自動・継続的な検出も可能。公式ブログの記載では<strong>音声1時間あたり $0.54（年内の導入価格）</strong>、入手経路は <strong>Microsoft Foundry / MAI Playground / OpenRouter / Vercel / Azure Voice Live</strong>（LiveKit も「coming soon」）。併せて<strong>音声生成の MAI-Voice-2.1 / 2.1-Flash</strong>（23言語・26ロケール）も発表され、公式ブログの記載は 2.1 が <strong>$22 / 100万文字</strong>、2.1-Flash が <strong>$15 / 100万文字</strong>です。<strong>Azure Foundry の確認済み料金表（Microsoft セクション）には、2026-10-03 時点で本モデル・MAI-Voice-2.1 系とも未掲載</strong>のため、上記はすべて公式ブログの記載です。',
 'MAI 初の<strong>ストリーミング音声認識モデル</strong>。話し終わりを待たずに、<strong>音声を受け取ってから約100msで partial（話している途中に出てくる暫定の文字起こし）</strong>を返します。<strong>60言語</strong>に対応し、言語の自動・継続的な検出も可能。入手経路は <strong>Microsoft Foundry / MAI Playground / OpenRouter / Vercel / Azure Voice Live</strong>（LiveKit も「coming soon」）。同じ発表で<strong>音声生成の MAI-Voice-2.1 / 2.1-Flash</strong>（23言語・26ロケール）も出ています。<strong>価格は下の「参考価格」の表にまとめました。</strong>なお「確認済み料金表」とは、<strong>Azure の公式料金ページに実際に載っているかを当サイトで確認した表</strong>のことです（2026-10-03 時点で、本モデルと MAI-Voice-2.1 系はこの表に載っていません）。'))
OPS.append(("en/mai/index.html",
 'MAI\'s first <strong>streaming speech recognition model</strong>. Instead of waiting for the speaker to finish, it returns its <strong>first partial result in just over 100ms</strong> of receiving audio, covers <strong>60 languages</strong>, and supports automatic continuous language detection. The official post lists <strong>$0.54 per hour of audio (introductory price through the end of the year)</strong>, with access via <strong>Microsoft Foundry / MAI Playground / OpenRouter / Vercel / Azure Voice Live</strong> (LiveKit is "coming soon"). The same announcement introduces the speech-generation models <strong>MAI-Voice-2.1 / 2.1-Flash</strong> (23 languages, 26 locales), listed at <strong>$22 per 1M characters</strong> and <strong>$15 per 1M characters</strong> respectively. <strong>None of these appear in the verified Azure Foundry pricing table (Microsoft section) as of 2026-10-03</strong>, so all figures here are from the official blog.',
 'MAI\'s first <strong>streaming speech recognition model</strong>. Instead of waiting for the speaker to finish, it returns its <strong>first partial result (a provisional transcript produced mid-speech) in just over 100ms</strong> of receiving audio, covers <strong>60 languages</strong>, and supports automatic continuous language detection. Access is via <strong>Microsoft Foundry / MAI Playground / OpenRouter / Vercel / Azure Voice Live</strong> (LiveKit is "coming soon"). The same announcement introduces the speech-generation models <strong>MAI-Voice-2.1 / 2.1-Flash</strong> (23 languages, 26 locales). <strong>Prices are collected in the "Reference prices" table below.</strong> By "verified pricing table" we mean <strong>the Azure official pricing page that this site checks directly</strong> — as of 2026-10-03 neither this model nor the Voice-2.1 family appears in it.'))

# --- 年表 Argon: 長文を改行で分割し、Fairwind と「予告」をやさしく
OPS.append(("timeline/index.html",
 '新フロンティアモデル。<strong>提供段階</strong>: ①Fairwind Program の trusted cyber defenders（招待されたサイバー防御関係者）に段階提供中',
 '新フロンティアモデル。<br><strong>提供段階</strong>: ①Fairwind Program（一般公募ではなく、セキュリティ専門家など<strong>招待されたテスター</strong>向けの限定プログラム）で段階提供中'))
OPS.append(("timeline/index.html",
 'と公式ブログに明記。Google は米国政府の事前アクセス自主プロセスに参加しつつ、ガードレールを反復して提供範囲を広げるとしています。<strong>現時点の入手経路は Fairwind Program（招待制）のみ</strong>で、一般の API・コンシューマ経路は未提供です。コンテキストは <strong>100万トークン</strong>。価格は「導入価格（introductory price）として <strong>入力 $2 / 出力 $10 / キャッシュ入力は入力価格から95%off</strong>」の予告で、公式ブログに課金開始の記載はありません。<strong>公式ブログにベンチマーク表は未掲載</strong>のため、',
 'と公式ブログに明記。米国政府の事前アクセス自主プロセスにも参加しています。<br><strong>現時点でできること</strong>: 入手経路は Fairwind Program（招待制）のみで、一般の API・コンシューマ経路は未提供です（<strong>この価格ではまだ購入できません</strong>）。コンテキストは <strong>100万トークン</strong>（ブログ要旨）。<br><strong>価格</strong>: 正式提供時の<strong>導入価格（introductory price）として 入力 $2 / 出力 $10 / キャッシュ入力は入力価格から95%off</strong> が<strong>予告</strong>されています（公式ブログに課金開始の記載はありません）。<br><strong>ベンチマーク</strong>: 公式ブログに表は未掲載のため、'))
OPS.append(("en/timeline/index.html",
 'A new frontier model. <strong>Release stages</strong>: (1) rolling out now to a set of trusted cyber defenders through the Fairwind Program;',
 'A new frontier model.<br><strong>Release stages</strong>: (1) rolling out now through the Fairwind Program — a limited program for invited testers such as security specialists, not an open sign-up;'))
OPS.append(("en/timeline/index.html",
 'as it iterates on guardrails and expands access. <strong>The only route available today is the Fairwind Program (invitation-based)</strong> — no general API or consumer access yet. Context: <strong>1 million tokens</strong>. Pricing is announced as an introductory price of <strong>$2 per 1M input tokens / $10 per 1M output tokens, with cached input at 95% off the input price</strong>; the post does not state that billing has started. <strong>The official post publishes no benchmark table</strong>, so we do not list aggregate-site scores as numbers here (any mention stays at the level of "as reported by ...").',
 'as it iterates on guardrails and expands access.<br><strong>What you can do today</strong>: the only route is the Fairwind Program (invitation-based) — no general API or consumer access yet, and <strong>you cannot buy at this price yet</strong>. Context: <strong>1 million tokens</strong> (per the post summary).<br><strong>Pricing</strong>: <strong>$2 per 1M input tokens / $10 per 1M output tokens, with cached input at 95% off the input price, is announced as an introductory price for launch</strong>; the post does not state that billing has started.<br><strong>Benchmarks</strong>: the official post publishes no benchmark table, so we do not list aggregate-site scores as numbers here (any mention stays at the level of "as reported by ...").'))

ok = 0
for path, old, new in OPS:
    p = os.path.join(SITE, path)
    s = open(p, encoding="utf-8").read()
    if new in s and old not in s:
        print("skip (already)", path); continue
    n = s.count(old)
    if n != 1:
        print("NG anchor", path, n, repr(old[:50])); continue
    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1)); ok += 1
print("applied", ok, "of", len(OPS))

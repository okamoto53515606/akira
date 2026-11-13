#!/usr/bin/env python3
# 2026-10-03: mai 使い方セクションに Transcribe-2-Streaming の入手経路を追記（okamo指摘②=読み手目線の整理）
import os
SITE = os.environ.get("SITE", "/tmp/site")
OPS = [
 ("mai/index.html",
  "<code>microsoft/mai-transcribe-2</code>。</li>",
  "<code>microsoft/mai-transcribe-2</code>。</li>\n    "
  "<li><strong>MAI-Transcribe-2-Streaming（2026-10-02・ストリーミング）:</strong> 公式ブログでは入手経路を "
  "<strong>OpenRouter / Microsoft Foundry / MAI Playground / Vercel / Azure Voice Live</strong> としており、LiveKit は「coming soon」と記載されています。"
  "話し終わりを待てない用途（リアルタイムの会議文字起こしなど）向けです。</li>"),
 ("en/mai/index.html",
  "<code>microsoft/mai-transcribe-2</code>.</li>",
  "<code>microsoft/mai-transcribe-2</code>.</li>\n    "
  "<li><strong>MAI-Transcribe-2-Streaming (Oct 2, 2026; streaming):</strong> the official post lists "
  "<strong>OpenRouter / Microsoft Foundry / MAI Playground / Vercel / Azure Voice Live</strong> (LiveKit is \"coming soon\"). "
  "It targets cases where waiting for the speaker to stop is not an option, such as live meeting transcription.</li>"),
]
for path, old, new in OPS:
    p = os.path.join(SITE, path)
    s = open(p, encoding="utf-8").read()
    if old in s and new not in s:
        open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
        print("applied", path)
    elif new in s:
        print("skip (already)", path)
    else:
        raise SystemExit("ANCHOR NOT FOUND: " + path)

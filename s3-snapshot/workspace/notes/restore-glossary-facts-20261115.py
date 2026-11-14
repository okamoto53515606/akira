# -*- coding: utf-8 -*-
"""出典1行化で落ちた事実（本文にしか無い注記）を、同じ source-note 行の末尾に戻す。"""
import re
from pathlib import Path

JOBS = [
 # (file, 一致キー(source-note内), 追記)
 ("glossary/gpt-6-astra-benchmarks/index.html", "arcprize.org/blog/astra",
  "（OpenAI公式発表の注記: ARC-AGI-3 は responses API ハーネスで実行し、現実の性能に合わせて2つの設定を変更した）"),
 ("en/glossary/gpt-6-astra-benchmarks/index.html", "arcprize.org/blog/astra",
  "(OpenAI's own note: ARC-AGI-3 was run on the responses API harness, with two settings adjusted to real-world performance)"),
 ("glossary/gpt-6-astra-benchmarks/index.html", "index/gpt-6-astra",
  "（評価は両モデルとも本番セーフガード無しで実施）"),
 ("en/glossary/gpt-6-astra-benchmarks/index.html", "index/gpt-6-astra",
  "(both models were evaluated without production safeguards)"),
 ("glossary/one-million-context/index.html", "build-with-claude/context-windows",
  "（英語の語数換算は当サイトの概算、トークン数は実測値で見積もる）"),
 ("en/glossary/one-million-context/index.html", "build-with-claude/context-windows",
  "(word-count conversions are our own approximation; estimate with measured token counts)"),
 ("glossary/prompt-cache/index.html",
  "\u5404\u793e\u516c\u5f0f\u6599\u91d1\u30da\u30fc\u30b8\u306e\u5024",
  "Gemini\u306f\u521d\u56de\u4fa1\u683c\uff082026\u5e7412\u670831\u65e5\u307e\u3067\uff09\u3067\u30012027\u5e741\u67081\u65e5\u4ee5\u964d\u306f $1.50 / $0.15 \u306b\u4e0a\u304c\u308a\u307e\u3059\u3002"),
 ("en/glossary/prompt-cache/index.html", "Values come from each provider",
  "Gemini rates are introductory (through 31 December 2026) and rise to $1.50 / $0.15 from 1 January 2027."),
]
for rel, key, add in JOBS:
    p = Path(rel); t = p.read_text(encoding="utf-8")
    m = re.search(r'<p class="source-note">((?:(?!</p>).)*?' + re.escape(key) + r'(?:(?!</p>).)*?)</p>', t, re.S)
    assert m, "note not found: %s / %s" % (rel, key)
    body = m.group(1).rstrip()
    if add[:12] in body:
        print("skip (already)", rel); continue
    p.write_text(t[:m.start(1)] + body + add + t[m.end(1):], encoding="utf-8")
    print("ok", rel, "+%d chars" % len(add))

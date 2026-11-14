# -*- coding: utf-8 -*-
"""課題121: 残8ページの出典を「1行のリンク行」に圧縮する。
規則:
 - <p class="source-note"> のうち <a> を1つ以上含むもの → 『接頭辞 + リンク(・区切り) + （確認日）』の1行に。
   ただし、地の文にしか無い数値/日付（他にページ内で出現しないもの）を含む文は、1行の末尾に残す（事実を消さない）。
 - <a> を含まない source-note（注記のみ）は、そのまま残す（出典リンク行ではないため）。
"""
import re
from pathlib import Path

PAIRS = ["gpt-6-astra-benchmarks", "harness", "one-million-context", "prompt-cache"]

def sentences(s):
    return [x for x in re.split(r"(?<=[。」）\.])\s*", s) if x.strip()]

def compress(rel):
    p = Path(rel); t = p.read_text(encoding="utf-8")
    before = len(t); changed = 0; kept_sent = 0
    def repl(m):
        nonlocal changed, kept_sent
        inner = m.group(1)
        anchors = re.findall(r"<a [^>]*>.*?</a>", inner, re.S)
        if not anchors:
            return m.group(0)
        plain = re.sub(r"<[^>]+>", "", inner)
        dates = re.findall(r"20\d\d-\d\d-\d\d", plain)
        # 接頭辞（出典: / Sources: など、最初のリンクより前）
        first_a = inner.find(anchors[0])
        prefix = inner[:first_a]
        prefix = re.sub(r"\s+$", " ", prefix)
        # 地の文（リンク・日付を除いた残り）
        rest = plain
        for a in anchors:
            rest = rest.replace(re.sub(r"<[^>]+>", "", a), "")
        rest = re.sub(r"\s+", " ", rest)
        # 事実の保護: 数値を含み、かつページ内に同じ数値が他で出てこない文だけ残す
        keep = []
        for s in sentences(rest):
            nums = re.findall(r"\d+(?:[.,]\d+)?%?", s)
            nums = [n for n in nums if not re.match(r"^(19|20)\d\d$", n)]
            hit = False
            for n in nums:
                if t.count(n) <= 1:      # この文の中にしか無い数値
                    hit = True
                    break
            if hit:
                keep.append(s.strip())
        if dates:
            tail = "（%s確認）" % "・".join(sorted(set(dates))) if any(
                "\u3042" <= ch <= "\u309f" or "\u4e00" <= ch <= "\u9fff" for ch in prefix) else " (checked %s)" % ", ".join(sorted(set(dates)))
        else:
            tail = ""
        note = ""
        if keep:
            kept_sent += 1
            joiner = " " if "Sources" in prefix or "Source" in prefix else ""
            note = " " + joiner.join(keep)
        new_inner = prefix + "・".join(anchors) + tail + note
        changed += 1
        return '<p class="source-note">' + new_inner + "</p>"
    t2 = re.sub(r'<p class="source-note">(.*?)</p>', repl, t, flags=re.S)
    p.write_text(t2, encoding="utf-8")
    print("%-48s before=%6d after=%6d notes=%d kept_sent=%d" % (rel, before, len(t2), changed, kept_sent))

for base in PAIRS:
    compress("glossary/%s/index.html" % base)
    compress("en/glossary/%s/index.html" % base)

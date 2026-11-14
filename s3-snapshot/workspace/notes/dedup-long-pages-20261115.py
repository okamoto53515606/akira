# -*- coding: utf-8 -*-
"""課題123（長文ページ対策の第一段）: 同一ページ内で完全重複しているブロックを後方から削除する。
対象は長い6ページ＋日英ペア。意味を削らずに重複だけを落とす（数値・主張は同一なので事実は減らない）。"""
import re
from pathlib import Path
TARGETS = ["en/timeline/index.html","timeline/index.html",
           "en/deepseek-v4-1-flash/index.html","deepseek-v4-1-flash/index.html",
           "en/glossary/zero-operator-access/index.html","glossary/zero-operator-access/index.html",
           "en/glossary/one-million-context/index.html","glossary/one-million-context/index.html"]
BLOCK = re.compile(r"<(li|p|tr|div)([^>]*)>(.*?)</\1>", re.S)
def norm(s):
    return re.sub(r"\s+","",re.sub(r"<[^>]+>","",s))
for rel in TARGETS:
    p=Path(rel); t=p.read_text(encoding="utf-8"); before=len(t)
    seen={}
    out=[]; pos=0; removed=0
    for m in BLOCK.finditer(t):
        key=norm(m.group(3))
        if len(key)>=60 and key in seen:
            if seen[key] is True:
                out.append(t[pos:m.start()]); pos=m.end(); removed+=1
                continue
        if len(key)>=60:
            seen[key]=True
        out.append(t[pos:m.end()]); pos=m.end()
    out.append(t[pos:])
    t2="".join(out)
    p.write_text(t2,encoding="utf-8")
    print("%-46s %6d -> %6d (%+.1f%%) removed_blocks=%d" % (rel, before, len(t2), 100*(len(t2)-before)/before, removed))

# -*- coding: utf-8 -*-
"""EN 側のみ: TTS/STT の従属単位を details へ移す（ja は別スクリプトで完了済み）"""
import re
from pathlib import Path
p = Path("en/speech-api-pricing/index.html"); t = p.read_text(encoding="utf-8")

def strip_col(t, hdr, keep_idx, drop_idx, new_hdr):
    pat = re.escape(hdr)
    m = re.search(r"(<div class=\"table-wrap\"><table>\n<thead>" + pat + r"</thead>\n<tbody>\n)(.*?)(</tbody></table></div>)", t, re.S)
    assert m, "table not found: " + hdr
    rows = [r for r in m.group(2).split("\n") if r.strip()]
    new_rows, dropped = [], []
    for r in rows:
        cells = re.findall(r"<td[^>]*>.*?</td>", r, re.S)
        assert len(cells) == 4, r
        dropped.append((re.sub(r"<[^>]+>", "", cells[0]), cells[drop_idx]))
        new_rows.append("<tr>%s</tr>" % "".join(cells[i] for i in keep_idx))
    new = '<div class="table-wrap"><table>\n<thead>' + new_hdr + '</thead>\n<tbody>\n' + "\n".join(new_rows) + "\n</tbody></table></div>"
    return t[:m.start()] + new + t[m.end():], dropped

t, char_pairs = strip_col(t, "<tr><th>Model</th><th>Per minute</th><th>Per 1,000 chars</th><th>Status</th></tr>",
                          (0, 1, 3), 2, "<tr><th>Model</th><th>Per minute</th><th>Status</th></tr>")
t, unit_pairs = strip_col(t, "<tr><th>Model</th><th>Per hour</th><th>Billing unit</th><th>Status</th></tr>",
                          (0, 1, 3), 2, "<tr><th>Model</th><th>Per hour</th><th>Status</th></tr>")

char_rows = "\n".join("<tr><td>%s</td><td>%s</td></tr>" % (n, v) for n, v in char_pairs)
unit_rows = "\n".join("<tr><td>%s</td><td>%s</td></tr>" % (n, v) for n, v in unit_pairs)
block = (
'<details class="legacy"><summary>Per-1,000-character rates and the raw billing units (breakdown)</summary>\n'
'<p style="font-size:.88rem;margin:.6rem 0 .3rem;"><strong>TTS: per 1,000 characters</strong> (1,000 characters = 3 min 20 s)</p>\n'
'<div class="table-wrap"><table>\n<thead><tr><th>Model</th><th>Per 1,000 chars</th></tr></thead>\n<tbody>\n'
+ char_rows + '\n</tbody></table></div>\n'
'<p style="font-size:.88rem;margin:1rem 0 .3rem;"><strong>STT: raw billing unit</strong> (the table above is already normalised to an hour)</p>\n'
'<div class="table-wrap"><table>\n<thead><tr><th>Model</th><th>Billing unit</th></tr></thead>\n<tbody>\n'
+ unit_rows + '\n</tbody></table></div>\n'
'</details>\n\n')
anchor = '<h2 class="section-title" style="font-size:1.15rem;">Transcription (STT)</h2>'
assert anchor in t
t = t.replace(anchor, block + anchor, 1)
p.write_text(t, encoding="utf-8")
print("ok tables=%d details=%d len=%d" % (t.count("<table"), t.count("<details"), len(t)))
print("char_pairs=%d unit_pairs=%d" % (len(char_pairs), len(unit_pairs)))

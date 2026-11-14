# -*- coding: utf-8 -*-
"""課題119: 音声ページの比較単位を1本化（TTS=1分 / STT=1時間）、従属単位は details に移す。ja/en 同時。
数値は既存テーブルから機械的に移す（手転写しない）。"""
import re
from pathlib import Path

def split_rows(block):
    rows = re.findall(r"<tr>.*?</tr>", block, re.S)
    return rows

def rebuild(path, lang, h_tts=("モデル","1分","1,000字","状態"), h_stt=("モデル","1時間","課金単位","状態")):
    p = Path(path); t = p.read_text(encoding="utf-8")
    # --- TTS table ---
    m = re.search(r"(<div class=\"table-wrap\"><table>\n<thead><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead>\n<tbody>\n)(.*?)(</tbody></table></div>)" % h_tts, t, re.S)
    assert m, "TTS table not found"
    rows = [r for r in m.group(2).split("\n") if r.strip()]
    new_rows, char_pairs = [], []
    for r in rows:
        cells = re.findall(r"<td[^>]*>.*?</td>", r)
        assert len(cells) == 4, r
        name = re.sub(r"<[^>]+>", "", cells[0])
        char_pairs.append((name, cells[2]))
        new_rows.append("<tr>%s%s%s</tr>" % (cells[0], cells[1], cells[3]))
    new_tts = '<div class="table-wrap"><table>\n<thead><tr><th>1</th><th>2</th><th>3</th></tr></thead>\n<tbody>\n' + "\n".join(new_rows) + "\n</tbody></table></div>"
    t = t[:m.start()] + new_tts + t[m.end():]

    # --- STT table ---
    m2 = re.search(r"(<div class=\"table-wrap\"><table>\n<thead><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead>\n<tbody>\n)(.*?)(</tbody></table></div>)" % h_stt, t, re.S)
    assert m2, "STT table not found"
    rows = [r for r in m2.group(2).split("\n") if r.strip()]
    new_rows, unit_pairs = [], []
    for r in rows:
        cells = re.findall(r"<td[^>]*>.*?</td>", r)
        assert len(cells) == 4, r
        name = re.sub(r"<[^>]+>", "", cells[0])
        unit_pairs.append((name, cells[2]))
        new_rows.append("<tr>%s%s%s</tr>" % (cells[0], cells[1], cells[3]))
    new_stt = '<div class="table-wrap"><table>\n<thead><tr><th>モデル</th><th>1時間</th><th>状態</th></tr></thead>\n<tbody>\n' + "\n".join(new_rows) + "\n</tbody></table></div>"
    t = t[:m2.start()] + new_stt + t[m2.end():]

    # --- details block with the dependent units ---
    char_rows = "\n".join("<tr><td>%s</td><td>%s</td></tr>" % (n, v) for n, v in char_pairs)
    unit_rows = "\n".join("<tr><td>%s</td><td>%s</td></tr>" % (n, v) for n, v in unit_pairs)
    if lang == "ja":
        block = (
'<details class="legacy"><summary>1,000字あたりの単価と、換算前の課金単位（内訳）</summary>\n'
'<p style="font-size:.88rem;margin:.6rem 0 .3rem;"><strong>TTS: 1,000字あたり</strong>（1,000字 = 3分20秒として換算）</p>\n'
'<div class="table-wrap"><table>\n<thead><tr><th>モデル</th><th>1,000字</th></tr></thead>\n<tbody>\n'
+ char_rows +
'\n</tbody></table></div>\n'
'<p style="font-size:.88rem;margin:1rem 0 .3rem;"><strong>STT: 換算前の課金単位</strong>（上の表はすべて1時間に換算済み）</p>\n'
'<div class="table-wrap"><table>\n<thead><tr><th>モデル</th><th>課金単位</th></tr></thead>\n<tbody>\n'
+ unit_rows +
'\n</tbody></table></div>\n'
'</details>\n\n')
        anchor = '<h2 class="section-title" style="font-size:1.15rem;">文字起こし（STT）</h2>'
    else:
        block = (
'<details class="legacy"><summary>Per-1,000-character rates and the raw billing units (breakdown)</summary>\n'
'<p style="font-size:.88rem;margin:.6rem 0 .3rem;"><strong>TTS: per 1,000 characters</strong> (1,000 characters = 3 min 20 s)</p>\n'
'<div class="table-wrap"><table>\n<thead><tr><th>Model</th><th>Per 1,000 chars</th></tr></thead>\n<tbody>\n'
+ char_rows +
'\n</tbody></table></div>\n'
'<p style="font-size:.88rem;margin:1rem 0 .3rem;"><strong>STT: raw billing unit</strong> (the table above is already normalised to an hour)</p>\n'
'<div class="table-wrap"><table>\n<thead><tr><th>Model</th><th>Billing unit</th></tr></thead>\n<tbody>\n'
+ unit_rows +
'\n</tbody></table></div>\n'
'</details>\n\n')
        anchor = '<h2 class="section-title" style="font-size:1.15rem;">Transcription (STT)</h2>'
    assert anchor in t, "anchor not found"
    t = t.replace(anchor, block + anchor, 1)
    p.write_text(t, encoding="utf-8")
    print(path, "ok tables=%d details=%d chars=%d" % (t.count("<table"), t.count("<details"), len(t)))

rebuild("speech-api-pricing/index.html", "ja")
rebuild("en/speech-api-pricing/index.html", "en", ("Model","Per minute","Per 1,000 chars","Status"), ("Model","Per hour","Billing unit","Status"))

"""2026-11-19 の不具合4件の再発防止を「壊した入力」で検証する（AWS/LLMは使わない）。

検証する型:
  1. 既存ページを更新しても更新履歴（site_events）に載らない  ← 11-19 に起きた
  2. 更新履歴に載ったのに /changelog/ の描画に反映されない
  3. 中身が古いまま日付だけ新しくして公開できてしまう（/mai/）
  4. 新しく載せたモデルが本文の段落にしかない（/mai/・/china-ai/）
  5. ページ内の年表に追記しもれ（/mai/）
  6. キービジュアルが台帳に無く、日付ズレを検査できない（/timeline/）

実行: python test_regression_20261119.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FAIL = []


def check(name, cond, detail=""):
    print(("  PASS " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        FAIL.append(name)


# ---------------------------------------------------------------- 素材
def page(title, h2s, body="", updated="2026-11-19", bar=True, extra_head=""):
    heads = "".join("<h2>%s</h2><p>…</p>" % h for h in h2s)
    bar_html = ('<div class="updated-bar"><span>最終更新: '
                '<time datetime="%s">%s</time></div>' % (updated, updated)) if bar else ""
    return """<!doctype html><html lang="ja"><head><title>%s</title>
<script type="application/ld+json">{"dateModified":"%s"}</script>%s</head>
<body><main>%s%s%s</main></body></html>""" % (title, updated, extra_head, bar_html, heads, body)


TH_JA = "<table><thead><tr><th>モデル</th><th>入力 / 1M</th><th>出力 / 1M</th></tr></thead><tbody>%s</tbody></table>"
TL_JA = ("<h2>MAI リリース年表</h2><table><thead><tr><th>日付</th><th>出来事</th></tr></thead>"
         "<tbody>%s</tbody></table>")

FACTS = {
    "models": {
        "qwen4-max-preview": {
            "id": "qwen4-max-preview", "released": "2026-11-15",
            "names": {"ja": "Qwen4-Max", "en": "Qwen4-Max"},
        },
        "mai-code-2": {
            "id": "mai-code-2", "released": "2026-11-16",
            "names": {"ja": "MAI Code 2", "en": "MAI Code 2"},
        },
        "qwen3-8-max": {
            "id": "qwen3-8-max", "released": "2026-08-03",
            "names": {"ja": "Qwen3.8-Max", "en": "Qwen3.8-Max"},
        },
        "qwen3-8-flash": {
            "id": "qwen3-8-flash", "released": "2026-08-26",
            "names": {"ja": "Qwen3.8-Flash", "en": "Qwen3.8-Flash"},
        },
        "glm-5-3-flash": {
            "id": "glm-5-3-flash", "released": "2026-08-26",
            "names": {"ja": "GLM 5.3 Flash", "en": "GLM 5.3 Flash"},
        },
    },
    # 台帳が本文を持つ特集ページ（R10/R10b/R11 の対象）
    "features": {"china-ai": {"blocks": []}, "mai": {"blocks": []}},
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    ws = tempfile.mkdtemp(prefix="ws19-")
    os.makedirs(os.path.join(ws, "data"), exist_ok=True)
    with open(os.path.join(ws, "data", "facts.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(FACTS, site_events=[]), fh, ensure_ascii=False)
    os.environ["WORKSPACE_LOCAL_DIR"] = ws
    os.environ["SITE_LOCAL_DIR"] = tempfile.mkdtemp(prefix="site19-")

    pa = load("page_audit", os.path.join(HERE, "page_audit.py"))
    pa.WORKSPACE_DIR = ws
    pa.STATE_PATH = os.path.join(ws, "data", "page_audit.json")
    pa.SPECS_PATH = os.path.join(ws, "data", "og_specs.json")

    # --- 3. 中身は10月のまま、日付だけ11月 -----------------------------
    print("[3] 古い見出しのまま日付だけ新しいページ")
    html = page("Microsoft AI (MAI) シリーズ特集【2026年10月版】 — LLM Data Hub",
                ["最新モデル（2026年10月）", "モデル別・料金"])
    codes = pa.error_codes("mai/index.html", html, {}, FACTS)
    check("R4（見出しの年月が古い）", "R4" in codes, str(sorted(codes)))
    check("R9（タイトルの年月が古い）", "R9" in codes)

    # 誤検知しないこと（リリース日・範囲・年月日）
    ok = page("Claude Fable 5.1 — LLM Data Hub",
              ["Claude Fable 5.1（2026年9月1日公開）", "料金"],
              body="<h1>主要LLM年表</h1><p>2025年1月〜2026年11月</p>")
    check("R4/R9 はリリース日・範囲を誤検知しない",
          not ({"R4", "R9"} & pa.error_codes("claude-fable-5-1/index.html", ok, {}, FACTS)))

    # --- 4. 新モデルが本文の段落にしかない ----------------------------
    print("[4] 新モデルが段落だけ（目立たない）")
    hidden = page("中国系AIモデル総覧【2026年11月版】 — LLM Data Hub",
                  ["主要ラボとフラッグシップ"],
                  body="<p>Qwen3.8-Max と Qwen3.8-Flash と GLM 5.3 Flash の説明。</p>"
                       "<p>Qwen4-Max（2026-11-15公開）は入力$1.50。</p>"
                       + (TH_JA % ""))
    codes = pa.error_codes("china-ai/index.html", hidden, {}, FACTS)
    check("R11（見出し・表に無い）", "R11" in codes, str(sorted(codes)))

    prominent = page("中国系AIモデル総覧【2026年11月版】 — LLM Data Hub",
                     ["主要ラボとフラッグシップ"],
                     body="<p>Qwen3.8-Max と Qwen3.8-Flash と GLM 5.3 Flash の説明。</p>"
                          "<h3>Qwen（Qwen4-Max が現行）</h3><p>Qwen4-Max は $1.50。</p>"
                          + (TH_JA % "<tr><td>Qwen4-Max</td><td>$1.50</td><td>$4.50</td></tr>"))
    check("R11 は見出しにあれば出ない",
          "R11" not in pa.error_codes("china-ai/index.html", prominent, {}, FACTS))

    # --- 5. 年表への追記もれ -----------------------------------------
    print("[5] 本文にあるのに年表に無い")
    tl_missing = page("Microsoft AI (MAI) シリーズ特集【2026年11月版】 — LLM Data Hub",
                      ["最新モデル（2026年11月）", "MAI リリース年表"],
                      body="<h3>MAI Code 2（コーディング）</h3><p>MAI Code 2 は $0.309/task。</p>")
    tl_missing = tl_missing.replace(
        "<h2>MAI リリース年表</h2><p>…</p>",
        TL_JA % "<tr><td>2026-10-02</td><td>MAI-Transcribe-2-Streaming</td></tr>")
    codes = pa.error_codes("mai/index.html", tl_missing, {}, FACTS)
    check("R10（台帳のモデルが年表に無い）", "R10" in codes, str(sorted(codes)))
    check("R10b（見出しのモデルが年表に無い）", "R10b" in codes)

    tl_ok = tl_missing.replace("</tbody></table>",
                               "<tr><td>2026-11-16</td><td>MAI Code 2</td></tr></tbody></table>", 1)
    tl_ok = tl_ok.replace("<h2>MAI リリース年表</h2><p>…</p>",
                          TL_JA % ("<tr><td>2026-10-02</td><td>MAI-Transcribe-2-Streaming</td></tr>"
                                   "<tr><td>2026-11-16</td><td>MAI Code 2</td></tr>"))
    check("R10/R10b は年表に追記されれば出ない",
          not ({"R10", "R10b"} & pa.error_codes("mai/index.html", tl_ok, {}, FACTS)))

    # --- 6. キービジュアルが台帳に無い --------------------------------
    print("[6] キービジュアルが og_specs に無い")
    fig = ('<figure class="key-visual"><img src="/assets/og/ja-timeline.png?v=20261119" '
           'width="1200" height="630"></figure>')
    codes = pa.error_codes("timeline/index.html", page("年表", ["Qwen4-Max"], fig), {}, FACTS)
    check("R5b は公開を止めない（ERROR ではない）", "R5b" not in codes, str(sorted(codes)))
    warn_codes = {c for s, c, _ in pa.audit_html("timeline/index.html", page("年表", ["Qwen4-Max"], fig), {}, FACTS)
                  if s == "WARN"}
    check("R5b は WARN で出る（移行途中のため公開は止めない）", "R5b" in warn_codes)

    # 仕様があり、生成日が本文より古い → R5(ERROR)
    specs = {"pages": {"timeline/index.html": {"image": "ja-timeline.png", "generated": "2026-10-31"}}}
    codes = pa.error_codes("timeline/index.html",
                           page("年表", ["Qwen4-Max"], fig, updated="2026-11-19"), specs, FACTS)
    check("R5（画像が本文より古い）", "R5" in codes, str(sorted(codes)))

    # --- 1/2. 更新の検知と site_events 登録 --------------------------
    print("[1][2] 既存ページの更新が更新履歴に載る")
    try:
        tools = load("tools", os.path.join(HERE, "tools.py"))
    except Exception as e:  # dependencies (boto3/strands) が無い環境ではスキップ
        print("  SKIP tools.py を読めない: %s" % e)
    else:
        tools.WORKSPACE_LOCAL_DIR = ws
        before = page("MAI", ["最新モデル（2026年10月）"], body="<p>古い</p>")
        after = page("MAI", ["最新モデル（2026年11月）"], body="<p>新しい</p>")
        check("指紋は本文の変化で変わる",
              tools._content_signature(before) != tools._content_signature(after))
        same_day_later = page("MAI", ["最新モデル（2026年10月）"], body="<p>古い</p>",
                              updated="2026-11-20")
        check("指紋は日付だけの更新では変わらない",
              tools._content_signature(before) == tools._content_signature(same_day_later))

        added = tools._register_site_updates([("mai", before, after)])
        check("更新が site_events に1件入る", added == ["mai"], str(added))
        with open(os.path.join(ws, "data", "facts.json"), encoding="utf-8") as fh:
            facts = json.load(fh)
        ev = facts["site_events"]
        check("イベントの種類は update", ev and ev[-1]["kind"] == "update", str(ev[-1:]))
        check("追加した見出しが文言に入る", "2026年11月" in ev[-1]["ja"], ev[-1]["ja"])

        again = tools._register_site_updates([("mai", before, after)])
        check("同じ日に二重登録しない", again == [], str(again))

        # 8ページ超は1件にまとめる
        many = [("p%02d" % i, before, after) for i in range(10)]
        added = tools._register_site_updates(many)
        check("大量更新は1件にまとめる", added == ["site-wide-update"], str(added))

    # --- 3'. 公開ゲートが止める --------------------------------------
        print("[3'] 公開ゲート: 日付だけ新しくして中身が古い → 止める")
        # 既に公開済みの版にも R4 がある（借金）。今回の公開で**日付だけ**進める形。
        stuck_old = page("MAI", ["最新モデル（2026年10月）"], body="<p>古い</p>",
                         updated="2026-11-01")
        stuck_new = page("MAI", ["最新モデル（2026年10月）"], body="<p>古い</p>",
                         updated="2026-11-19")
        gate = tools._audit_gate_errors(os.environ["SITE_LOCAL_DIR"], "mai/index.html",
                                        stuck_new, stuck_old)
        check("既存のR4でも、日付を進めたら止める", any("R4" in g or "R9" in g for g in gate),
              str(gate))
        clean_old = page("MAI", ["最新モデル（2026年11月）"], body="<p>新しい</p>",
                         updated="2026-11-10")
        gate2 = tools._audit_gate_errors(os.environ["SITE_LOCAL_DIR"], "mai/index.html",
                                         after, clean_old)
        check("問題の無い更新は通す", gate2 == [], str(gate2))

    print()
    if FAIL:
        print("FAILED: %d 件 %s" % (len(FAIL), FAIL))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

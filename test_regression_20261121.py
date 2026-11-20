"""2026-11-21 の回帰テスト。

事象（okamo指摘）:
  1. GPT-6.2 Astra / Sol が公開されたのに気づかなかった（致命的）
  2. 代わりに古いモデル（Claude Mythos 5.1・GPT-5.6 Sol）を「新着」として年表に足した
  3. /china-ai/ の「MiniMax が Kimi と同じブロック」を、独立セクション新設で直した

ここでは「同じ壊れ方を入れた入力」に対して、追加した仕組みが**鳴る**ことを確かめる。
ネットワークは使わない（watch_releases の _fetch を差し替える）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import page_audit  # noqa: E402
import tools  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name + (("  <- " + detail) if (detail and not cond) else ""))


# --------------------------------------------------------------------- 年表HTML
def tl_article(aid, date, title, desc="d"):
    return ('<article class="tl-item dot-other" id="%s"><div class="tl-card">'
            '<div class="tl-date">%s <span class="tl-provider-tag">X</span></div>'
            '<h2 class="tl-title" id="s-%s">%s</h2><p class="tl-desc">%s</p></div></article>\n'
            % (aid, date, aid, title, desc))


def page(articles, extra=""):
    return ('<!DOCTYPE html><html lang="ja"><head><title>年表</title>'
            '<script type="application/ld+json">{"dateModified":"2026-11-21"}</script></head><body>'
            '<div class="updated-bar"><span class="dot">●</span><time datetime="2026-11-21">2026年11月21日</time></div>'
            '<div class="tl-wrap"><div class="year-divider">2026年</div>\n'
            + "".join(articles) + extra + '</div></body></html>')


FACTS = {"models": {
    "claude-mythos-5-1": {"id": "claude-mythos-5-1", "released": "2026-09-01",
                          "released_source": "official-announcement",
                          "names": {"ja": "Claude Mythos 5.1"}},
    "gpt-5-6-sol": {"id": "gpt-5-6-sol", "released": "2026-07-09",
                    "released_source": "official-announcement",
                    "names": {"ja": "GPT-5.6 Sol"}},
    "gemini-3-1-flash-lite": {"id": "gemini-3-1-flash-lite", "released": "",
                              "released_source": "unknown",
                              "names": {"ja": "Gemini 3.1 Flash-Lite"}},
}}


def codes(html):
    return {c for _, c, _ in page_audit.audit_html("timeline/index.html", html, {}, FACTS)}


print("== R12: 同じ日の同じ出来事を二重に書いた")
broken = page([
    tl_article("claude-mythos-5-1", "2026-09-01", "Claude Mythos 5.1 提供開始 — トラステッドアクセス限定の上位モデル"),
    tl_article("claude-fable-5-1", "2026-09-01", "Claude Fable 5.1 / Mythos 5.1 公開 — Mythosクラス新フラッグシップ"),
])
check("R12 が発火する", "R12" in codes(broken), str(codes(broken)))
ok = page([
    tl_article("claude-mythos-5-1", "2026-09-01", "Claude Fable 5.1 / Mythos 5.1 公開 — Mythosクラス新フラッグシップ"),
    tl_article("gpt-5-6", "2026-07-09", "GPT-5.6ファミリー公開 — Sol/Terra/Luna"),
])
check("別の日の別イベントでは発火しない", "R12" not in codes(ok), str(codes(ok)))

print("== R13: 年表カードの日付が台帳の released と違う（ページ公開日をリリース日にした）")
bad_date = page([tl_article("gpt-5-6-sol", "2026-08-29", "GPT-5.6 Sol 公開 — 入力$4.00／出力$20.00")])
check("R13 が発火する", "R13" in codes(bad_date), str(codes(bad_date)))
good_date = page([tl_article("gpt-5-6-sol", "2026-07-09", "GPT-5.6 Sol 公開 — 入力$4.00／出力$20.00")])
check("一致していれば発火しない", "R13" not in codes(good_date), str(codes(good_date)))
announce = page([tl_article("gpt-5-6-sol", "2026-08-21", "GPT-5.6 Sol の値下げを発表")])
check("「発表」の項目は対象外", "R13" not in codes(announce), str(codes(announce)))

print("== R14: リリース日の出典が未確認のまま年表に出す")
unknown_src = page([tl_article("gemini-3-1-flash-lite", "2026-08-10",
                               "Gemini 3.1 Flash-Lite 公開 — 入力$0.25／出力$1.50")])
check("R14 が発火する", "R14" in codes(unknown_src), str(codes(unknown_src)))

print("== R11: 更新履歴にだけ名前が出るのは誤検知にしない")
feat = (page([], "") .replace("</body>",
        '<section class="section" aria-labelledby="log-h">'
        '<h2 class="section-title" id="log-h">更新履歴（アップデートログ）</h2>'
        '<ul><li><span class="cl-date">2026-11-21</span> GPT-6.2 Astra を料金比較・計算機・年表に追加</li></ul>'
        '</section></body>'))
recent = {"models": {"gpt-6-2-astra": {"id": "gpt-6-2-astra", "released": "2026-11-21",
                                       "names": {"ja": "GPT-6.2 Astra"}}},
          "features": {"china-ai": {"blocks": []}}}
cs = {c for _, c, _ in page_audit.audit_html("china-ai/index.html", feat, {}, recent)}
check("更新履歴だけの言及で R11 は鳴らない", "R11" not in cs, str(cs))

print("== 構造ゲート: セクション増／カード減")
old = ('<h1 class="section-title">t</h1><div class="lab-grid">'
       '<div class="lab-card">a</div><div class="lab-card">b</div></div>'
       '<h2 class="section-title" id="x">X</h2>')
new_split = ('<h1 class="section-title">t</h1><div class="lab-grid">'
             '<div class="lab-card">a</div></div>'
             '<h2 class="section-title" id="x">X</h2>'
             '<h2 class="section-title" id="y">Y</h2>')
errs = tools._structure_gate_errors("china-ai/index.html", new_split, old)
check("セクション増を止める", any("セクション" in e for e in errs), str(errs))
check("カード減を止める", any("カード" in e for e in errs), str(errs))
keep = ('<h1 class="section-title">t</h1><div class="lab-grid">'
        '<div class="lab-card">a</div><div class="lab-card">b</div>'
        '<div class="lab-card">c</div></div><h2 class="section-title" id="x">X</h2>')
check("カードを同じグリッドに足すのは通す",
      tools._structure_gate_errors("china-ai/index.html", keep, old) == [])

tmp = tempfile.mkdtemp()
allow = os.path.join(tmp, "structure_allow.json")
with open(allow, "w", encoding="utf-8") as fh:
    json.dump({"china-ai/index.html": {"sections": 3}}, fh)
orig = tools.STRUCTURE_ALLOW_PATH
tools.STRUCTURE_ALLOW_PATH = allow
errs = tools._structure_gate_errors("china-ai/index.html", new_split, old)
tools.STRUCTURE_ALLOW_PATH = orig
check("structure_allow.json を書けば意図的に通せる",
      not any(e.startswith("STRUCTURE: セクションが") for e in errs), str(errs))

print("== 公式ソースの見張り: 台帳に無い新モデルを拾う")
spec = importlib.util.spec_from_file_location(
    "watch_releases", os.path.join(ROOT, "tools", "watch_releases.py"))
if spec and os.path.exists(spec.origin or ""):
    wr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wr)
    os.environ["WORKSPACE_LOCAL_DIR"] = tmp
    wr.WATCH_PATH = os.path.join(tmp, "release_watch.json")

    def fake_fetch(url):
        return ('<table><tr><td>gpt-6.2-astra</td><td>$8.00</td></tr>'
                '<tr><td>gpt-6.2-sol</td><td>$2.00</td></tr>'
                '<tr><td>gpt-6.1-sol</td></tr>'
                '<tr><td>gemini-31-pro-preview-customtools</td></tr></table>')

    wr._fetch = fake_fetch
    old_ledger = {"gpt-6-1-sol": {"names": {"ja": "GPT-6.1 Sol"}}}
    r = wr.scan(old_ledger, today="2026-11-21")
    got = set(r["unknown_in_ledger"])
    check("GPT-6.2 Astra を候補に出す", "gpt-6-2-astra" in got, str(got))
    check("GPT-6.2 Sol を候補に出す", "gpt-6-2-sol" in got, str(got))
    check("URLスラッグは候補にしない", "gemini-31-pro-preview-customtools" not in got, str(got))
    line = wr.mission_line(r)
    check("ミッション文に候補が出る", "gpt-6-2-astra" in line, line[:120])

    def fake_fail(url):
        raise OSError("boom")

    wr._fetch = fake_fail
    r2 = wr.scan(old_ledger, today="2026-11-21")
    line2 = wr.mission_line(r2)
    check("取得失敗を『新モデル無し』と書かない",
          r2["status"] == "failed" and "取得できず" in line2, line2[:120])
else:
    check("watch_releases.py が見つかる", False, "workspace/tools に無い")

print("\nRESULT: %d passed / %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)

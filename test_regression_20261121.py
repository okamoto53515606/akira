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



# =====================================================================
# 追記（②の対策）: 記録（trace）と依頼の契約（1依頼1項目・受領書）
# =====================================================================
print("\n== trace: 伏字・記録・失敗しても止まらない")
import logging as _logging
import trace_store as ts

_fake_key = "sk-" + "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
check("sk- の鍵を伏字にする", _fake_key not in ts.redact("key=%s" % _fake_key))
check("Google APIキーを伏字にする", "A" * 35 not in ts.redact("AIza" + "A" * 35))
check("パスワード行を伏字にする",
      "hunter2hunter2" not in ts.redact("password: hunter2hunter2"))
check("伏字にしていない日本語は壊さない",
      ts.redact("MiniMax をカードに戻す") == "MiniMax をカードに戻す")

_written = []


class _FakeTable:
    def put_item(self, Item):  # noqa: N803 (boto3 の引数名)
        _written.append(Item)


class _FakeDDB:
    def Table(self, name):  # noqa: N802
        return _FakeTable()


_t = ts.Trace(today="2026-11-21", run_id="testrun")
_t._ddb = _FakeDDB()
_t._s3 = object()          # _clients() が boto3 を取りに行かないようにする
_t.blob = lambda kind, payload: {"digest": "x", "chars": 4, "inline": "BODY"}
_t.prompt("Claudeエンジニア", "SYS-PROMPT" * 100)
_t.event("delegate.request", agent="Claudeエンジニア", item_id="OK-2",
         body=_t.blob("delegate.request", "req"))
check("event が書かれる", len(_written) == 2, str(len(_written)))
check("pk に run_id が入る", _written[0]["pk"] == "run#2026-11-21#testrun")
check("prompt.system は本文を保持する",
      _written[0]["kind"] == "prompt.system" and "SYS-PROMPT" in _written[0]["system_prompt"])
check("TTL が入る", isinstance(_written[0].get("ttl"), int) and _written[0]["ttl"] > 0)


class _Boom:
    def Table(self, name):
        raise RuntimeError("boom")


_t2 = ts.Trace(today="2026-11-21", run_id="boom")
_t2._ddb = _Boom()
_t2._s3 = object()
try:
    _t2.event("run.start")
    ok = True
except Exception:  # noqa: BLE001
    ok = False
check("Dynamo が落ちても例外を投げない（日次を止めない）", ok)

print("== 依頼の契約: 1依頼1項目・受領書")
import main as M

check("2項目の依頼を検出する",
      M.count_request_items("1. china-ai の MiniMax\n2. /mai/ の年表\n") == 2)
check("1項目の依頼は通す", M.count_request_items("china-ai の MiniMax を直す") == 0)
check("丸数字も検出する", M.count_request_items("① A をやる\n② B をやる") == 2)

_s1, _r1 = M.item_receipt("OK-2", "年表が降順", "作業しました。\nDONE: OK-2")
check("DONE を達成として読む", _s1 == "done" and "達成" in _r1, _r1)
_s2, _r2 = M.item_receipt("OK-2", "年表が降順", "時間切れ\nNOT_DONE: OK-2")
check("NOT_DONE を未達として読む", _s2 == "not_done" and "未達" in _r2, _r2)
_s3, _r3 = M.item_receipt("OK-2", "年表が降順", "作業しました。")
check("記載が無ければ未確認（達成にしない）", _s3 == "unknown" and "未確認" in _r3, _r3)
# 2026-11-21 の実機で起きた型: id 無しの NOT_DONE
_s4, _r4 = M.item_receipt("OK-2", "年表が降順", "NOT_DONE: 公開（テストランのため）")
check("id無しの NOT_DONE は未達ではなく未確認", _s4 == "unknown" and "item_id" in _r4, _r4)

M._ITEM_LEDGER.clear()
M.record_item("OK-1", "china-ai", "lab-card 8枚", status="requested")
M.record_item("OK-1", "china-ai", "lab-card 8枚", status="done", evidence="達成（DONE: OK-1）")
M.record_item("OK-2", "mai", "年表が降順", status="requested")
M.record_item("OK-2", "mai", "年表が降順", status="not_done", evidence="未達（NOT_DONE: OK-2）")
check("同じ item は1行に集約される", len(M._ITEM_LEDGER) == 2, str(M._ITEM_LEDGER))
_md = M.ledger_markdown()
check("受領書に両方の項目が出る", "OK-1" in _md and "OK-2" in _md)
check("未達が強調される", "**未達**" in _md)
M._ITEM_LEDGER.clear()
check("項目が無ければ受領書は空", M.ledger_markdown() == "")

print("== ログのレベル修正（指示・応答が実際に残るか）")
_records = []


class _Cap(_logging.Handler):
    def emit(self, record):
        _records.append(record)


_h = _Cap()
_logging.getLogger("akira").addHandler(_h)
_logging.getLogger("akira").setLevel(_logging.INFO)
_prev = M.DEBUG_TOOL_LOGGING
M.DEBUG_TOOL_LOGGING = True
M._debug_log_io("指示", "Akira本体", "TEST-PAYLOAD")
M.DEBUG_TOOL_LOGGING = _prev
_logging.getLogger("akira").removeHandler(_h)
check("INFO で記録される（以前は DEBUG で捨てられていた）",
      any(r.levelno == _logging.INFO and "TEST-PAYLOAD" in r.getMessage() for r in _records),
      str([(r.levelname, r.getMessage()[:40]) for r in _records]))

print("== 公開と検証の1呼び出しツール")
_pv = getattr(tools, "publish_and_verify", None)
check("publish_and_verify がある", _pv is not None)
check("@tool が付いている（エージェントから呼べる）",
      bool(getattr(_pv, "tool_spec", None)), str(type(_pv)))



print("== 公開用エクスポート（許可kindのみ・伏字・S3キーを出さない）")
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("publish_trace", os.path.join(ROOT, "scripts", "publish_trace.py"))
pt = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(pt)

check("許可kindだけを公開する", set(pt.PUBLIC_FIELDS) == set(ts.PUBLIC_KINDS),
      str(set(pt.PUBLIC_FIELDS) ^ set(ts.PUBLIC_KINDS)))
_r = pt.redact({"a": "token=abcdefghijklmn", "b": "mail me at a.b@example.com"})
check("公開時にも鍵を伏字にする", "abcdefghijklmn" not in json.dumps(_r, ensure_ascii=False))
check("メールアドレスを伏字にする", "@example.com" not in json.dumps(_r, ensure_ascii=False))



print("== テストラン（--no-publish）では公開できない")
import inspect as _insp

_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("publish_and_verify もドライランで差し替わる",
      "_publish_verify = publish_and_verify" in _src and "_publish_verify," in _src)


print("== 入れ子（dict のリスト）に float が入っても記録できる")
_written.clear()
_t3 = ts.Trace(today="2026-11-21", run_id="nested")
_t3._ddb = _FakeDDB()
_t3._s3 = object()
_t3.event("delegate.result", agent="Claudeエンジニア", item_id="X",
          tool_calls=20, cost_jpy=3.3,
          tools=[{"tool": "shell", "calls": 12, "errors": 0, "seconds": 1.25}],
          body={"digest": "abc", "chars": 10})
check("dict のリスト（float入り）でも書ける", len(_written) == 1, str(_written))
_tools = _written[0].get("tools") if _written else None
check("ツール内訳が構造のまま残る",
      isinstance(_tools, list) and _tools and _tools[0]["tool"] == "shell", str(_tools))
import decimal as _dec
check("秒が Decimal になっている（DynamoDBの型）",
      isinstance(_tools[0]["seconds"], _dec.Decimal), str(type(_tools[0]["seconds"])))


print("== ツール呼び出し（引数・結果）も記録に残す")
from types import SimpleNamespace as _NS


class _FakeEv:
    def __init__(self, name, args, result, exc=None):
        self.tool_use = {"name": name, "input": args}
        self.result = result
        self.exception = exc


_written.clear()
_t4 = ts.Trace(today="2026-11-21", run_id="hooked")
_t4._ddb = _FakeDDB()
_t4._s3 = object()



class _FakeS3:
    def __init__(self):
        self.put = []

    def put_object(self, **kw):
        self.put.append(kw)


_s3fake = _FakeS3()
_t4._clients = lambda: (_FakeDDB(), _s3fake)   # boto3 を取りに行かせない
ts._CURRENT[0] = _t4
_hook = ts.tool_hook("Claudeエンジニア")
check("tool_hook がコールバックを返す", callable(_hook))
_hook(_FakeEv("read_file", {"path": "index.html"}, "OK: 12 lines"))
_kinds = [w.get("kind") for w in _written]
check("tool.call を書く", "tool.call" in _kinds, str(_kinds))
check("tool.args を書く", "tool.args" in _kinds, str(_kinds))
check("tool.result を書く", "tool.result" in _kinds, str(_kinds))
_call = next((w for w in _written if w.get("kind") == "tool.call"), {})
check("ツール名と引数長が残る",
      _call.get("tool") == "read_file" and _call.get("args_chars", 0) > 0, str(_call))
check("S3 に本文が2つ（args と result）置かれる", len(_s3fake.put) == 2, str(len(_s3fake.put)))
_args_row = next((w for w in _written if w.get("kind") == "tool.args"), {})
check("args 行に S3 の参照が入る",
      str((_args_row.get("body") or {}).get("key", "")).startswith("trace/"),
      str(_args_row)[:200])
check("正常時は error=False", _call.get("error") is False, str(_call.get("error")))

_written.clear()
_hook(_FakeEv("shell", {"command": "ls"}, "boom", exc=RuntimeError("x")))
_call = next((w for w in _written if w.get("kind") == "tool.call"), {})
check("例外時は error=True", _call.get("error") is True, str(_call.get("error")))

_written.clear()
_hook(_FakeEv("list_site_files", {}, "a\nb"))
_kinds = [w.get("kind") for w in _written]
check("雑音ツールは本文を残さない",
      _kinds == ["tool.call"], str(_kinds))

_written.clear()
ts._CURRENT[0] = None
_hook(_FakeEv("read_file", {"path": "x"}, "OK"))
check("記録先が無ければ何もしない", _written == [], str(_written))

print("== 監視（watch_releases）は1本落ちても次のURLで拾う")


def _load_watch():
    spec = importlib.util.spec_from_file_location(
        "watch_releases", os.path.join(ROOT, "tools", "watch_releases.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_w = _load_watch()
_calls = []


def _fake_fetch(url, retries=1):
    _calls.append(url)
    if "broken" in url:
        raise RuntimeError("HTTP 403 for %s" % url)
    return "<html><body>ok</body></html>", 200


_w._fetch = _fake_fetch
_used, _txt = _w._fetch_any(["https://broken.example/a", "https://ok.example/b"])
check("落ちたURLの次を使う", _used == "https://ok.example/b", str(_used))
check("1本目も試している", _calls and "broken" in _calls[0], str(_calls))
_w._fetch = lambda url, retries=1: (_ for _ in ()).throw(RuntimeError("HTTP 500 for %s" % url))
try:
    _w._fetch_any(["https://x.example/a", "https://y.example/b"])
    _raised = ""
except Exception as e:  # noqa: BLE001
    _raised = str(e)
check("全滅なら最後の例外を投げる", "500" in _raised, _raised)

print("== invalidation が失敗しても公開結果は失わない")
_src_tools = open(os.path.join(ROOT, "tools.py"), encoding="utf-8").read()
check("flush_invalidations を try で囲んでいる",
      "flush_invalidations()\n            result[\"invalidation\"] = \"ok\"" in _src_tools)
check("失敗を result に載せる",
      'result["invalidation"] = "%s: %s"' in _src_tools)


print("== 記録が大きすぎても Dynamo を溢れさせない（400KB で丸ごと落ちない）")
_written.clear()
_put2 = []


class _S2:
    def put_object(self, **kw):
        _put2.append(kw)


_t5 = ts.Trace(today="2026-11-21", run_id="huge")
_t5._clients = lambda: (_FakeDDB(), _S2())
_lim = getattr(ts, "_MAX_ITEM_BYTES", 180_000)
check("項目サイズの上限が定義されている", _lim > 0, str(_lim))
_t5.prompt("Akira", "あ" * 400_000)          # 約1.2MB のシステムプロンプト
_row = _written[-1] if _written else {}
_size = len(json.dumps(_row, ensure_ascii=False, default=str).encode("utf-8"))
check("項目が上限内に収まる", 0 < _size <= _lim, "%d bytes" % _size)
check("溢れた本文は S3 に退避される", _row.get("spilled") == "system_prompt", str(_row.get("spilled")))
check("S3 に全文が置かれる（切り詰めない）",
      _put2 and len(_put2[0]["Body"]) == 1_200_000, str(len(_put2[0]["Body"]) if _put2 else 0))
check("全文長が chars に残る", _row.get("chars") == 400_000, str(_row.get("chars")))

_written.clear()
_put2.clear()
_t6 = ts.Trace(today="2026-11-21", run_id="prompt20k")
_t6._clients = lambda: (_FakeDDB(), _S2())
_t6.prompt("Claudeエンジニア", "P" * 20_000)
_row = _written[-1] if _written else {}
check("普通サイズのプロンプトは全文を項目に持つ（2000字で切らない）",
      _row.get("system_prompt") == "P" * 20_000, str(len(_row.get("system_prompt") or "")))

print("== 日報の曜日は JST で機械が決める（モデルに推測させない）")
import main as _main

check("2026-11-21 は土曜", _main.jst_weekday_label("2026-11-21") == "土",
      _main.jst_weekday_label("2026-11-21"))
check("2026-11-20 は金曜", _main.jst_weekday_label("2026-11-20") == "金",
      _main.jst_weekday_label("2026-11-20"))
_bad = "# 2026-11-21（金）日報 — LLM Data Hub\n\n## 見出し\n本文 2026-11-21（金）時点"
_fixed = _main._normalize_report_body(_bad, "2026-11-21")
check("先頭の重複見出し（日報タイトル行）を落とす",
      _fixed.lstrip().splitlines()[0] == "## 見出し", repr(_fixed[:40]))
check("本文中の曜日を土に直す", "（土）" in _fixed and "（金）" not in _fixed, _fixed[:80])
check("中身は消さない", "## 見出し" in _fixed and "本文" in _fixed, _fixed[:80])


print("== 公開はHTMLだけでなく data/models.json も上げる（計算機だけ古いままを防ぐ）")
_td = tempfile.mkdtemp()
os.makedirs(os.path.join(_td, "data"), exist_ok=True)
os.makedirs(os.path.join(_td, "timeline"), exist_ok=True)
for rel in ("data/models.json", "timeline/index.html", "sitemap.xml"):
    with open(os.path.join(_td, rel), "w", encoding="utf-8") as fh:
        fh.write("{}")
_html_t, _other_t = tools._publish_targets(
    _td, ["data/models.json", "timeline/index.html"], "")
check("HTML と それ以外 を分ける", _html_t == ["timeline/index.html"]
      and _other_t == ["data/models.json"], "%s / %s" % (_html_t, _other_t))
_html_t, _other_t = tools._publish_targets(_td, [], ".")
check("paths='.' で全ファイルを拾う（JSON/XMLも）",
      "data/models.json" in _other_t and "sitemap.xml" in _other_t, str(_other_t))
_src_check = open(os.path.join(ROOT, "tools.py"), encoding="utf-8").read()
check("公開ループが HTML 以外も上げている（再発防止）",
      "if other_news:" in _src_check and "s3.upload_file(local, LLM_SITE_BUCKET, rel,"
      in _src_check)

print("== 公開中の計算機データと台帳のズレを機械が見つける（GAなのに計算機に無い）")
_wd = tempfile.mkdtemp()
os.makedirs(os.path.join(_wd, "data"), exist_ok=True)
_facts_fixture = {"models": {
    "gemini-4-neon": {"id": "gemini-4-neon", "status": "ga",
                      "price": {"input": 3.0, "output": 15.0},
                      "names": {"ja": "Gemini 4 Neon", "en": "Gemini 4 Neon"}},
    "gpt-6-2-sol": {"id": "gpt-6-2-sol", "status": "ga",
                    "price": {"input": 2.0, "output": 10.0},
                    "names": {"ja": "GPT-6.2 Sol", "en": "GPT-6.2 Sol"}},
    "some-preview": {"id": "some-preview", "status": "preview",
                     "price": {"input": 1.0, "output": 2.0},
                     "names": {"ja": "Some Preview", "en": "Some Preview"}},
}}
with open(os.path.join(_wd, "data", "facts.json"), "w", encoding="utf-8") as fh:
    json.dump(_facts_fixture, fh, ensure_ascii=False)

_old_wd = tools.WORKSPACE_LOCAL_DIR
_old_get = tools._http_get
tools.WORKSPACE_LOCAL_DIR = _wd
_bodies = {}


def _fake_get(url, *a, **k):
    for key, payload in _bodies.items():
        if key in url:
            return 200, json.dumps(payload).encode("utf-8"), ""
    return 404, b"", "not found"


tools._http_get = _fake_get
_bodies[tools.DATA_MODELS_KEY] = {"models": [{"name": "GPT-6.2 Sol"}]}
_gaps = tools._published_calculator_gaps()
check("公開データに無いGAモデルを指摘する", any("gemini-4-neon" in g for g in _gaps), str(_gaps))
check("公開データにあるモデルは指摘しない", not any("gpt-6-2-sol" in g for g in _gaps), str(_gaps))
check("GAでないモデルは対象外", not any("some-preview" in g for g in _gaps), str(_gaps))
_bodies[tools.DATA_MODELS_KEY] = {"models": [{"name": "GPT-6.2 Sol"},
                                             {"name": "Gemini 4 Neon"}]}
check("揃えば0件", tools._published_calculator_gaps() == [], str(tools._published_calculator_gaps()))

# 台帳の名前は別名を含むことがある（"Claude Fable 5.2 / Mythos 5.2"）。
# 計算機側は price.name（"Claude Fable 5.2"）で登録されるので、別名でも一致させる。
_facts_fixture["models"]["claude-fable-5-2"] = {
    "id": "claude-fable-5-2", "status": "ga",
    "price": {"name": "Claude Fable 5.2", "input": 8.0, "output": 40.0},
    "names": {"ja": "Claude Fable 5.2 / Mythos 5.2",
              "en": "Claude Fable 5.2 / Mythos 5.2"}}
with open(os.path.join(_wd, "data", "facts.json"), "w", encoding="utf-8") as _fh:
    json.dump(_facts_fixture, _fh, ensure_ascii=False)
_bodies[tools.DATA_MODELS_KEY] = {"models": [{"name": "Gemini 4 Neon"},
                                             {"name": "Claude Fable 5.2"}]}
_g2 = tools._published_calculator_gaps()
check("別名（スラッシュ）持ちは誤検知しない", not any("fable" in g for g in _g2), str(_g2))
tools.WORKSPACE_LOCAL_DIR = _old_wd
tools._http_get = _old_get


print("== 受領書：1項目の依頼なら「DONE: 説明文」も達成として読む")
check("id 付きはそのまま達成", _main.item_receipt("X-1", "a", "DONE: X-1")[0] == "done")
check("1項目なら書式違いの DONE も達成",
      _main.item_receipt("X-1", "a", "DONE: 修正して公開した", single_item=True)[0] == "done",
      str(_main.item_receipt("X-1", "a", "DONE: 修正して公開した", single_item=True)))
check("書式違いは evidence に残す",
      "書式違い" in _main.item_receipt("X-1", "a", "DONE: 修正した", single_item=True)[1])
check("書式違いの NOT_DONE は未達",
      _main.item_receipt("X-1", "a", "NOT_DONE: できず", single_item=True)[0] == "not_done")
check("複数項目モードでは書式違いを未確認のまま",
      _main.item_receipt("X-1", "a", "DONE: 修正した")[0] == "unknown")
check("DONE が無ければ未確認",
      _main.item_receipt("X-1", "a", "完了しました", single_item=True)[0] == "unknown")

print("\nRESULT: %d passed / %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)

"""2026-11-28 の回帰テスト（okamo依頼「朝の自動ランを監査し、再発防止をデプロイ」）。

2026-11-28 05:11〜05:28 JST の自動ランで見つけた4件を、**落ちるテスト**にして
から直す（memory の「失敗は落ちるテストが書けたときに直ったとみなす」）。

  ① 日報が「ページ監査: **未実施 2件**」と書いたが、Akira は両方監査して
     ERROR 0 を確認している（11-26 と**逆向きの同じ嘘**）。
     真因: `page_audit` が `date.today()`（コンテナは UTC）で日付を作る一方、
     `main.run_daily` は `datetime.now(JST)` の `today` を `mission_line()` に
     渡す。assignments は JST のキー、last_run は UTC の日付になり、**永久に
     一致しない**。課題155（render_site の UTC バグ、11-17 に修正）の同型が
     ここに残っていた。
     実測: /workspace/data/page_audit.json は
       assignments["2026-11-28"] = [claude-mythos-5-1, en/deepseek-v4-1-flash]
       last_run[*].date        = "2026-11-27"
  ② `publish_and_verify` だけが `s3.upload_file` 直呼びで、**データ契約ゲートも
     ベースライン保存も通っていなかった**。同日 Akira はこの経路で
     data/models.json を公開したため、「最後に公開した正常版」（修復の原資）が
     59行・`GPT-6.2 Astra for Law` 入りの旧版のまま残った（実測: 05:22:46 に
     公開した版とバイト一致）。次に計算機データが壊れたら自動復元で Law が
     **復活する**。
  ③ 11-26 に「業種別構成（for Law / for Healthcare）は計算機に入れない」と
     **文章で**決めたのに、台帳のフラグに書き漏らして healthcare 2件が混入した。
     決定はゲート（公開契約）にも書かないと効かない。
  ④ `tools/` の CLIスクリプト4本が毎朝「@tool を付けた TOOL 変数が定義されて
     いません」と警告されていた。意味のない警告が並ぶと、2026-11-15 の
     site_upload 欠落のような**本物のスキップが埋もれる**。

ネットワーク・AWS・LLM は使わない（偽のS3・偽のHTTP・偽の描画を注入する）。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import main  # noqa: E402
import page_audit  # noqa: E402
import tools  # noqa: E402

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).date().isoformat()

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name +
          (("  <- " + detail) if (detail and not cond) else ""))


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------------------------------------------------------- fixtures
def _models_payload(rows: int = 12, extra_names=()) -> dict:
    models = [{"name": "Model %02d" % i, "provider": "openai", "label": "OpenAI",
               "input": 1.0, "output": 2.0, "note": "", "note_en": ""}
              for i in range(rows)]
    models += [{"name": n, "provider": "openai", "label": "OpenAI",
                "input": 1.0, "output": 2.0, "note": "", "note_en": ""}
               for n in extra_names]
    return {"fx": {"usd_jpy": 155, "source": "facts.fx"}, "models": models}


class FakeS3:
    """upload_file / put_object / head_object だけを持つ最小のS3。"""

    def __init__(self):
        self.puts: dict[str, bytes] = {}
        self.uploads: list[str] = []

    def head_object(self, Bucket=None, Key=None):  # noqa: N803
        from botocore.exceptions import ClientError

        raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}},
                          "HeadObject")

    def put_object(self, Bucket=None, Key=None, Body=None, **kw):  # noqa: N803
        self.puts[Key] = Body
        return {}

    def upload_file(self, Filename, Bucket, Key, ExtraArgs=None):  # noqa: N803
        self.uploads.append(Key)
        with open(Filename, "rb") as fh:
            self.puts[Key] = fh.read()
        return True


# ---------------------------------------------------------------- ① JST
def test_audit_jst_date() -> None:
    print("\n[①] ページ監査の日付がJSTか（assignments と last_run が噛み合うか）")
    src = open(os.path.join(ROOT, "page_audit.py"), encoding="utf-8").read()
    check("page_audit に date.today() が残っていない（UTCのままの箇所が無い）",
          "date.today()" not in src.replace("`date.today()`", ""),
          "date.today() が残っている")

    with tempfile.TemporaryDirectory() as tmp:
        site = os.path.join(tmp, "site")
        rel = "claude-mythos-5-1/index.html"
        _write(os.path.join(site, rel),
               "<html><head><title>t</title></head><body>"
               '<div class="updated-bar">2026-11-28 更新</div></body></html>')
        old_state, old_site, old_pri = (page_audit.STATE_PATH, page_audit.SITE_DIR,
                                        page_audit.PRIORITY_PATH)
        page_audit.STATE_PATH = os.path.join(tmp, "page_audit.json")
        page_audit.SITE_DIR = site
        page_audit.PRIORITY_PATH = os.path.join(tmp, "page_priority.json")
        try:
            # 11-28 の実際の状態を再現: assignments はJST、last_run はUTC（前日）
            utc_today = datetime.now(timezone.utc).date().isoformat()
            page_audit._save(page_audit.STATE_PATH, {
                "assignments": {TODAY: [rel]},
                "last_run": [{"page": rel, "date": utc_today, "codes": []}],
            })
            old = page_audit.verify_assigned(TODAY)
            check("壊れた状態（last_run がUTC日付）なら『未実施』になる"
                  "＝テストが11-28の嘘を捉えている", "未実施" in old, old)

            # 直したコードで監査すると、last_run は JST の日付で書かれる
            page_audit.audit_pages("claude-mythos-5-1/index.html")
            state = page_audit._load(page_audit.STATE_PATH, {})
            dates = {r["date"] for r in state.get("last_run") or []}
            check("audit_pages が last_run をJSTの日付で書く",
                  dates == {TODAY}, "dates=%s" % sorted(dates))
            line = page_audit.verify_assigned(TODAY)
            check("監査したのに『未実施』と誤報しない", "未実施" not in line, line)
            check("実施済みとして数える", "実施済み" in line, line)

            # 翌日（UTCではまだ当日）に verify しても、前日の実施を当日扱いしない
            tomorrow = (datetime.now(JST) + timedelta(days=1)).date().isoformat()
            check("翌日の割当が無ければ『割当なし』（前日の実施を数えない）",
                  "割当なし" in page_audit.verify_assigned(tomorrow))
        finally:
            page_audit.STATE_PATH, page_audit.SITE_DIR, page_audit.PRIORITY_PATH = (
                old_state, old_site, old_pri)


# ---------------------------------------------------------------- ② 公開経路
def test_publish_and_verify_gate() -> None:
    print("\n[②] publish_and_verify が契約ゲートとベースライン保存を通るか")
    with tempfile.TemporaryDirectory() as tmp:
        site = os.path.join(tmp, "site")
        base_path = os.path.join(tmp, "ws", "data", "calculator-models.json")
        old = (tools.SITE_LOCAL_DIR, tools.BASELINE_MODELS_PATH,
               tools._render_site_from_ledger, tools._facts_consistency_errors,
               tools._bump_sitemap_lastmod, tools.flush_invalidations,
               tools.boto3.client)
        fake = FakeS3()
        try:
            tools.SITE_LOCAL_DIR = site
            tools.BASELINE_MODELS_PATH = base_path
            tools._render_site_from_ledger = lambda base: []
            tools._facts_consistency_errors = lambda base: []
            tools._bump_sitemap_lastmod = lambda base, rels, s3: False
            tools.flush_invalidations = lambda: None
            tools.boto3.client = lambda *a, **k: fake

            # (a) 業種別構成を含む＝公開を拒否し、ベースラインも書かない
            _write(os.path.join(site, "data", "models.json"),
                   json.dumps(_models_payload(extra_names=("GPT-6.2 Astra for Law",)),
                              ensure_ascii=False))
            res = tools.publish_and_verify(paths="data/models.json", live=False)
            rejected = [r for r in res["rejected"] if r["key"] == "data/models.json"]
            check("業種別構成を含む models.json は公開拒否",
                  bool(rejected) and "業種別構成" in str(rejected[0]["errors"]),
                  str(res["rejected"])[:200])
            check("拒否したファイルはS3へ行かない",
                  "data/models.json" not in fake.puts)
            check("拒否した内容をベースラインに書かない",
                  not os.path.exists(base_path))

            # (b) 正しい内容＝公開し、ベースラインも更新する
            good = _models_payload()
            _write(os.path.join(site, "data", "models.json"),
                   json.dumps(good, ensure_ascii=False))
            res2 = tools.publish_and_verify(paths="data/models.json", live=False)
            check("正しい models.json は公開される",
                  "data/models.json" in res2["published"], str(res2)[:200])
            check("ベースライン（修復の原資）が公開版で更新される",
                  os.path.exists(base_path))
            if os.path.exists(base_path):
                with open(base_path, encoding="utf-8") as fh:
                    saved = json.load(fh)
                check("ベースラインの中身が公開した内容と一致",
                      len(saved["models"]) == len(good["models"]))

            # (c) 旧実装（ゲート無しで upload_file 直呼び）の挙動を再現し、
            #     「公開はできるのにベースラインが古いまま」を確認する
            os.remove(base_path)
            fake.puts.pop("data/models.json", None)
            old_gate = tools._gate_data_file
            tools._gate_data_file = lambda rel, p: (None, [])
            try:
                _write(os.path.join(site, "data", "models.json"),
                       json.dumps(_models_payload(extra_names=("X for Law",)),
                                  ensure_ascii=False))
                res3 = tools.publish_and_verify(paths="data/models.json", live=False)
                check("旧経路（ゲート無し）は業種別構成でも公開してしまう"
                      "＝テストが11-28の穴を捉えている",
                      "data/models.json" in res3["published"], str(res3)[:200])
                check("旧経路はベースラインも更新しない（原資が古いまま）",
                      not os.path.exists(base_path))
            finally:
                tools._gate_data_file = old_gate
        finally:
            (tools.SITE_LOCAL_DIR, tools.BASELINE_MODELS_PATH,
             tools._render_site_from_ledger, tools._facts_consistency_errors,
             tools._bump_sitemap_lastmod, tools.flush_invalidations,
             tools.boto3.client) = old


# ---------------------------------------------------------------- ③ 決定のゲート化
def test_calc_denylist() -> None:
    print("\n[③] 業種別構成は計算機に入れない（11-26の決定を公開契約で止める）")
    ok = tools.validate_calculator_models(_models_payload())
    check("正しい計算機データは合格", ok == [], str(ok)[:200])
    for name in ("GPT-6.2 Astra for Law", "GPT-6.2 Sol for Healthcare"):
        bad = tools.validate_calculator_models(_models_payload(extra_names=(name,)))
        hit = [e for e in bad if "業種別構成" in e]
        check("%s を検出する" % name, bool(hit), str(bad)[:200])
    check("除外パターンは定数として外に出ている（増やすときはここ）",
          isinstance(tools.CALC_EXCLUDED_NAME_PATTERNS, tuple)
          and "for law" in tools.CALC_EXCLUDED_NAME_PATTERNS)

    # C1（業種別構成は公開拒否）と C5（台帳のGAモデルは公開中にあるか）が
    # ぶつかると「永久に直せない違反」になる。C5 側が除外することを確かめる。
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
        with open(os.path.join(tmp, "data", "facts.json"), "w", encoding="utf-8") as fh:
            json.dump({"models": {
                "gpt-6-2-astra-law": {"status": "ga", "shown_on": ["pricing"],
                                      "price": {"name": "GPT-6.2 Astra for Law",
                                                "input": 8.0, "output": 40.0}},
                "some-normal-model": {"status": "ga", "shown_on": ["pricing"],
                                      "price": {"name": "Some Normal Model",
                                                "input": 1.0, "output": 2.0}},
            }}, fh)
        body = json.dumps(_models_payload()).encode("utf-8")
        old_ws, old_get = tools.WORKSPACE_LOCAL_DIR, tools._http_get
        try:
            tools.WORKSPACE_LOCAL_DIR = tmp
            tools._http_get = lambda url, *a, **k: (200, body, "")
            gaps = tools._published_calculator_gaps()
            check("C5 は業種別構成を『無い』と叫ばない（C1と矛盾しない）",
                  not any("astra-law" in g for g in gaps), str(gaps)[:200])
            check("C5 は普通のGAモデルの欠落は今までどおり指摘する",
                  any("some-normal-model" in g for g in gaps), str(gaps)[:200])
        finally:
            tools.WORKSPACE_LOCAL_DIR, tools._http_get = old_ws, old_get


# ---------------------------------------------------------------- ④ 静かなスキップ
def test_workspace_loader() -> None:
    print("\n[④] ワークスペースのツール読み込み（スクリプトは静か・異常は大声）")
    with tempfile.TemporaryDirectory() as tmp:
        tdir = os.path.join(tmp, "tools")
        # CLIスクリプト（@tool 無し）: self_check が subprocess で叩く想定
        _write(os.path.join(tdir, "check_page_shape.py"),
               "def main(argv):\n    return 0\n")
        # @tool が2個で TOOL 未定義: 本物の異常
        _write(os.path.join(tdir, "two_tools.py"),
               "from strands import tool\n\n"
               "@tool\ndef a(x: str = '') -> str:\n    return x\n\n"
               "@tool\ndef b(x: str = '') -> str:\n    return x\n")
        # 正常
        _write(os.path.join(tdir, "ok_tool.py"),
               "from strands import tool\n\n"
               "@tool\ndef ok_tool(x: str = '') -> str:\n"
               "    \"\"\"テスト用。\"\"\"\n    return x\n\nTOOL = ok_tool\n")
        old = tools.WORKSPACE_LOCAL_DIR
        try:
            tools.WORKSPACE_LOCAL_DIR = tmp
            loaded = tools.load_workspace_tools()
            names = [getattr(t, "tool_name", "") for t in loaded]
            check("正常なツールは読める", "ok_tool" in names, str(names))
            skips = tools.workspace_tool_skips()
            files = [s["file"] for s in skips]
            check("CLIスクリプトはスキップ一覧に出さない（静かに飛ばす）",
                  "check_page_shape.py" not in files, str(files))
            check("TOOL未定義の異常は残す（本物だけ大声）",
                  "two_tools.py" in files, str(files))
        finally:
            tools.WORKSPACE_LOCAL_DIR = old


# ---------------------------------------------------------------- 配線
def test_wiring() -> None:
    print("\n[配線] ミッション・日報への差し込み")
    tools._WORKSPACE_TOOL_SKIPS.clear()
    import prompts  # noqa: PLC0415  f-string の破損検品も兼ねる
    check("title/description 凍結の規約が**実行者**（エンジニア）のプロンプトにある",
          "凍結" in prompts.CLAUDE_ENGINEER_PROMPT)
    check("Akira側（SITE_RULES）にも残っている",
          "凍結" in prompts.SITE_RULES)
    check("main に _workspace_tool_skip_line がある",
          callable(getattr(main, "_workspace_tool_skip_line", None)))
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    check("ミッション組み立てで呼ばれている",
          "_workspace_tool_skip_line(akira_tools)" in src)
    check("ミッションのプレースホルダが壊れていない",
          isinstance(main.DAILY_MISSION_TEMPLATE.format(
              today=TODAY, weekday="土", site_url="https://x/", last_work_line="-",
              health_line="-", freshness_line="-", platform_line="-",
              theme_line="-", audit_line="-"), str))
    check("_workspace_tool_skip_line はスキップ0件なら空文字",
          main._workspace_tool_skip_line(tools) == "")


def main_() -> None:
    test_audit_jst_date()
    test_publish_and_verify_gate()
    test_calc_denylist()
    test_workspace_loader()
    test_wiring()
    print("\nRESULT: %d passed / %d failed" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  FAILED:", f)
        sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main_()

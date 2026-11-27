"""2026-11-27 の回帰テスト（okamo指摘3件＋11-26 ランの観測）。

対象:
  ① 配布元カタログ（Azure）の版が進んだのにページが古いまま、を機械で見つける
     2026-11-17 に「Azure のカタログは Version 2026-09-10 のまま」と書いたが、
     同じ日に Azure は `DeepSeek-V4.1-Flash-1017`（Version 2026-10-17）を
     **別エントリとして追加**していた。11-26 まで誰も気づいていない。
  ② 2026-11-26 のランで見つけた2つの「静かな嘘」
     (a) 日報が「ページ監査: 未実施 2件」と書いたが、Akira は両方監査していた。
         `audit_pages` が `last_run` を**呼び出しごとに上書き**していたため、
         1日に複数回呼ぶと最後の1回しか残らなかった。
     (b) GPT税理士に渡す一次情報の前置きが**ファイル名のアルファベット順6件**で
         打ち切られ、当日取得済みの `openai-pricing` と `zai-*` が丸ごと落ちた
         （課題188「中身はあるのに渡っていない」）。
     さらに 11-26 の課題199（ローカル models.json 61行・公開59行）を
     「契約チェックは通っているから誰も叫ばない」ままにしない。

ネットワーク・AWS・LLM は使わない（偽のfetcher／偽のHTTPを注入する）。
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
import platform_watch  # noqa: E402
import tools  # noqa: E402

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).date().isoformat()

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name +
          (("  <- " + detail) if (detail and not cond) else ""))


# ---------------------------------------------------------------- fixtures
def _catalog_model_page(version: str, *, name: str = "DeepSeek-V4.1-Flash-1017",
                        lifecycle: str = "Preview", ctx: str = "1000k",
                        tokens: str = "128k output", inp: str = "text") -> str:
    """Azure カタログのモデルページの**実物と同じ骨格**（2026-11-27 実測）。"""
    return (
        "<html><body><script>var bundle = 'Lifecycle blah'</script>"
        "<h1>%s</h1>"
        '<div><span class="k">Version: <!-- -->%s</span></div>'
        "<div>%s</div>"
        '<span>Type</span><span>Chat completion</span>'
        '<span>Lifecycle</span><span>%s</span>'
        '<span>Hosted on</span><span>Azure</span>'
        '<span>Input type</span><span>%s</span>'
        '<span>Output type</span><span>text</span>'
        '<span>Context window</span><span>%s</span>'
        '<span>Token limits</span><span>%s</span>'
        "</body></html>"
        % (name, version, "x" * 3000, lifecycle, inp, ctx, tokens)
    )


def _listing(names) -> str:
    """カタログ一覧（React の flight データに名前が並ぶ形）。"""
    body = ",".join('"%s"' % n for n in names)
    return ("<html><body><script>self.__next_f.push([%s,"
            "'/catalog/models/other-model'])</script></body></html>" % body)


def _site_page(claim_version: str, *, first_party: str = "2026-10-17",
               mention_newest: bool = True) -> str:
    """サイトのページ（`Version <code>…</code>` でカタログの版を主張する形）。"""
    extra = ("<p>本家の現行版は <code>DeepSeek-V4.1-Flash-1017</code>（%s）です。</p>"
             % first_party) if mention_newest else ""
    return (
        "<html><body>%s"
        "<table><tr><td>Azure のカタログ</td>"
        "<td><code>DeepSeek-V4.1-Flash</code> / Version <code>%s</code>"
        "（Preview・1000k context・128k output）</td></tr></table>"
        "</body></html>" % (extra, claim_version)
    )


def _fetcher(mapping):
    def fetch(url):
        if url not in mapping:
            raise RuntimeError("unexpected url: " + url)
        return mapping[url]
    return fetch


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------------------------------------------------------- ① 見張り
def test_platform_watch() -> None:
    print("\n[①] 配布元カタログの見張り")
    family = "DeepSeek-V4.1-Flash"

    names = platform_watch.parse_entry_names(
        _listing(["DeepSeek-V4.1-Flash", "DeepSeek-V4.1-Flash-1017",
                  "DeepSeek-V4.1-FlashX", "DeepSeek-R1"]), family)
    check("一覧から接尾辞つきのエントリも拾う（版が増える形）",
          names == ["DeepSeek-V4.1-Flash", "DeepSeek-V4.1-Flash-1017"], str(names))

    meta = platform_watch.parse_meta(_catalog_model_page("2026-10-17"))
    check("Version のコメント挿入（<!-- -->）を跨いで読む",
          meta["version"] == "2026-10-17", str(meta))
    check("提供段階・コンテキスト・出力上限・入力種別も読む",
          (meta["lifecycle"], meta["context"], meta["tokens"], meta["input"]) ==
          ("Preview", "1000k", "128k output", "text"), str(meta))

    stale = platform_watch.compare(
        {"name": "DeepSeek-V4.1-Flash-1017", "version": "2026-10-17"},
        _site_page("2026-09-10"))
    check("ページの主張が古ければ stale（本文に本家の 2026-10-17 があっても騙されない）",
          stale[0] == "stale", str(stale))

    ok = platform_watch.compare(
        {"name": "DeepSeek-V4.1-Flash-1017", "version": "2026-10-17"},
        _site_page("2026-10-17"))
    check("主張が最新なら ok", ok[0] == "ok", str(ok))

    # 版を書いていないページは「名も版も書いてあるか」で判定する
    nover = platform_watch.compare(
        {"name": "DeepSeek-V4.1-Flash-1017", "version": "2026-10-17"},
        "<html><body>Azure で使えます</body></html>")
    check("版の記載が無いページは stale（黙って古いままを通さない）",
          nover[0] == "stale", str(nover))

    # check_target 全体（偽のfetcher）
    mapping = {
        platform_watch.LIST_URL.format(q="DeepSeek-V4.1-Flash"):
            _listing(["DeepSeek-V4.1-Flash", "DeepSeek-V4.1-Flash-1017"]),
        platform_watch.MODEL_URL.format(name="DeepSeek-V4.1-Flash"):
            _catalog_model_page("2026-09-10", name="DeepSeek-V4.1-Flash"),
        platform_watch.MODEL_URL.format(name="DeepSeek-V4.1-Flash-1017"):
            _catalog_model_page("2026-10-17"),
    }
    with tempfile.TemporaryDirectory() as tmp:
        for rel in platform_watch.TARGETS[0]["pages"]:
            _write(os.path.join(tmp, rel), _site_page("2026-09-10"))
        res = platform_watch.check_target(platform_watch.TARGETS[0], site_dir=tmp,
                                          fetcher=_fetcher(mapping))
        check("最新エントリは version の最大（2026-10-17）",
              res["newest"]["version"] == "2026-10-17", str(res["newest"]))
        check("ページが古ければ stale と判定する", res["verdict"] == "stale",
              str(res["verdict"]))
        line = platform_watch.mission_line({"results": [res]})
        check("ミッションに『直し方』まで書く",
              "カタログの版が進んでいる" in line and "直し方" in line, line[:300])
        check("旧エントリが併存していることも書く（両方いまの状態）",
              "2026-09-10" in line and "同時に載っている" in line, line[:400])

        # ページを直したら、再取得なしで ok になる（実行後の再判定）
        for rel in platform_watch.TARGETS[0]["pages"]:
            _write(os.path.join(tmp, rel), _site_page("2026-10-17"))
        after = platform_watch.recheck_local(res, site_dir=tmp)
        check("直したあとの再判定は ok（再取得しない）", after["verdict"] == "ok",
              str(after["verdict"]))
        check("直っていれば日報に足す行は空", platform_watch.stale_line(
            {"results": [after]}) == "")
        check("直っていなければ日報に残す行が出る",
              "DeepSeek-V4.1-Flash-1017" in platform_watch.stale_line({"results": [res]}))

    # 取得失敗は「載っていない」ではない
    def boom(url):
        raise RuntimeError("network down")
    unk = platform_watch.check_target(platform_watch.TARGETS[0], site_dir="/nonexistent",
                                      fetcher=boom)
    check("取得失敗は unknown（『無い』と書かない）", unk["verdict"] == "unknown",
          str(unk))
    check("ミッションは unknown を『不明』と明示する",
          "不明" in platform_watch.mission_line({"results": [unk]}))
    check("unknown を stale として日報に残さない",
          platform_watch.stale_line({"results": [unk]}) == "")

    # エントリ1件のページだけ落ちても、残りで判定する
    flaky = dict(mapping)
    def flaky_fetch(url):
        if url.endswith("/DeepSeek-V4.1-Flash"):
            raise RuntimeError("model page 404")
        return flaky[url]
    with tempfile.TemporaryDirectory() as tmp:
        for rel in platform_watch.TARGETS[0]["pages"]:
            _write(os.path.join(tmp, rel), _site_page("2026-09-10"))
        part = platform_watch.check_target(platform_watch.TARGETS[0],
                                          site_dir=tmp, fetcher=flaky_fetch)
        check("モデルページ1件が落ちても最新エントリで判定する",
              part["newest"]["name"] == "DeepSeek-V4.1-Flash-1017", str(part["newest"]))
        check("読めなかったエントリを隠さない", part["skipped"] == ["DeepSeek-V4.1-Flash"],
              str(part["skipped"]))
        check("読めなかったエントリをミッションにも書く",
              "読めなかったエントリ" in platform_watch.mission_line({"results": [part]}))


# ---------------------------------------------------------------- ② 監査
def test_audit_last_run() -> None:
    print("\n[②-a] ページ監査の実施確認（last_run の累積）")
    with tempfile.TemporaryDirectory() as tmp:
        site = os.path.join(tmp, "site")
        for rel in ("image-api-pricing/index.html", "en/deepseek-v4-pro/index.html"):
            _write(os.path.join(site, rel),
                   "<html><head><title>t</title></head><body>"
                   '<div class="updated-bar">2026-11-26 更新</div></body></html>')
        old_state, old_site, old_pri = (page_audit.STATE_PATH, page_audit.SITE_DIR,
                                        page_audit.PRIORITY_PATH)
        page_audit.STATE_PATH = os.path.join(tmp, "page_audit.json")
        page_audit.SITE_DIR = site
        page_audit.PRIORITY_PATH = os.path.join(tmp, "page_priority.json")
        try:
            # 割当を2ページにして、1ページずつ2回監査する（11-26 の実際の形）
            page_audit._save(page_audit.STATE_PATH,
                             {"assignments": {TODAY: ["image-api-pricing/index.html",
                                                      "en/deepseek-v4-pro/index.html"]}})
            page_audit.audit_pages("image-api-pricing/index.html")
            page_audit.audit_pages("en/deepseek-v4-pro/index.html")
            line = page_audit.verify_assigned(TODAY)
            check("1日に分けて監査しても『未実施』と誤報しない",
                  "未実施" not in line, line)
            check("2ページとも実施済みとして数える", "2ページ実施済み" in line, line)

            # 直す前のコード（上書き）では誤報することの確認
            state = page_audit._load(page_audit.STATE_PATH, {})
            state["last_run"] = [{"page": "en/deepseek-v4-pro/index.html",
                                  "date": TODAY, "codes": []}]
            page_audit._save(page_audit.STATE_PATH, state)
            old = page_audit.verify_assigned(TODAY)
            check("旧挙動（最後の1回だけ残る）なら未実施になる＝テストが壊れ方を捉えている",
                  "未実施" in old, old)
        finally:
            page_audit.STATE_PATH, page_audit.SITE_DIR, page_audit.PRIORITY_PATH = (
                old_state, old_site, old_pri)


# ---------------------------------------------------------------- ② 証拠
def test_evidence_block() -> None:
    print("\n[②-b] 一次情報の前置き（当日12件・依頼に関係するものを優先）")
    names = [
        "deepseek-v4-1-flash-2026-11-26.md",
        "deepseek-v4-flash-2026-11-26.md",
        "kimi-k3-1-pro-2026-11-26.md",
        "openai-for-healthcare-20261126-2026-11-26.md",
        "openai-healthcare-announcement-20261126-2026-11-26.md",
        "openai-models-docs-20261126-2026-11-26.md",
        "openai-news-rss-20261126-2026-11-26.md",
        "openai-pricing-20261126-2026-11-26.md",
        "zai-blog-glm54-20261126-2026-11-26.md",
        "zai-doc-glm54-20261126-2026-11-26.md",
        "zai-pricing-glm54-recheck-20261126-2026-11-26.md",
        "zai-release-notes-20261126-2026-11-26.md",
    ]
    old_ws = main.WORKSPACE_LOCAL_DIR
    with tempfile.TemporaryDirectory() as tmp:
        main.WORKSPACE_LOCAL_DIR = tmp
        try:
            for i, name in enumerate(names):
                _write(os.path.join(tmp, "cache", name),
                       "取得日時: %s\n\nGLM-5.4 の単価はまだ出ていない（本文%d）。\n"
                       % (TODAY, i))
            request = "docs.z.ai の料金ページで GLM-5.4 の単価が出たか確認してくれ"
            block = main._evidence_block(request=request)

            alphabetical = sorted(names)[:6]
            check("旧挙動（名前順6件）では zai が落ちていた＝再現条件が正しい",
                  not any(n.startswith("zai-") for n in alphabetical), str(alphabetical))
            check("依頼に関係する zai の証拠が前置きに入る",
                  "zai-pricing-glm54-recheck" in block, block[:400])
            check("同じ日の openai-pricing も入る（枠が関係ない証拠で埋まらない）",
                  "openai-pricing-20261126" in block)
            check("打ち切ったファイル名を明示する（『一次情報が無い』と誤解させない）",
                  "入れていない証拠" in block, block[-400:])

            other = main._evidence_block(request="全く関係ない話")
            check("依頼に関係なくても当日分は入る（空にはしない）",
                  "deepseek-v4-1-flash" in other)
        finally:
            main.WORKSPACE_LOCAL_DIR = old_ws


# ---------------------------------------------------------------- ② 公開差
def test_local_vs_published() -> None:
    print("\n[②-c] ローカルと公開の計算機データのずれ（課題199の型）")
    old_site, old_get = tools.SITE_LOCAL_DIR, tools._http_get
    with tempfile.TemporaryDirectory() as tmp:
        tools.SITE_LOCAL_DIR = tmp
        try:
            def payload(rows):
                return json.dumps({"models": [{"name": n, "provider": "openai",
                                               "label": "OpenAI", "input": 1,
                                               "output": 2} for n in rows]},
                                  ensure_ascii=False).encode()

            live = ["GPT-6", "GPT-5.6", "Claude Sonnet 5.5"]
            local = live + ["GLM-5.4", "Gemini 3.9 Flash"]
            _write(os.path.join(tmp, "data", "models.json"),
                   json.dumps({"models": [{"name": n} for n in local]},
                              ensure_ascii=False))
            tools._http_get = lambda url: (200, payload(live), "")
            gaps = tools._local_vs_published_models_gap()
            check("描画したのに公開していないモデルを指摘する", len(gaps) == 1, str(gaps))
            check("どのモデルかを名指しする（GLM-5.4 / Gemini 3.9 Flash）",
                  gaps and "GLM-5.4" in gaps[0] and "Gemini 3.9 Flash" in gaps[0],
                  str(gaps))

            _write(os.path.join(tmp, "data", "models.json"),
                   json.dumps({"models": [{"name": n} for n in live]},
                              ensure_ascii=False))
            check("一致していれば何も言わない",
                  tools._local_vs_published_models_gap() == [])

            os.remove(os.path.join(tmp, "data", "models.json"))
            check("ローカルが無い（site_download 前）なら何も言わない",
                  tools._local_vs_published_models_gap() == [])
        finally:
            tools.SITE_LOCAL_DIR, tools._http_get = old_site, old_get


# ---------------------------------------------------------------- main配線
def test_wiring() -> None:
    print("\n[配線] ミッションと後処理に差し込まれているか")
    check("ミッションに platform_line がある",
          "{platform_line}" in main.DAILY_MISSION_TEMPLATE)
    check("format が通る（プレースホルダの過不足が無い）",
          isinstance(main.DAILY_MISSION_TEMPLATE.format(
              today=TODAY, weekday="木", site_url="https://x/", last_work_line="-",
              health_line="-", freshness_line="-", platform_line="-",
              theme_line="-", audit_line="-"), str))
    check("後処理が残差を日報に足す関数を持つ", callable(main._platform_leftover_line))
    check("GPT税理士に依頼文を渡している（関係する証拠を選べる）",
          "request=request" in open(os.path.join(ROOT, "main.py"),
                                    encoding="utf-8").read())


def main_() -> None:
    test_platform_watch()
    test_audit_last_run()
    test_evidence_block()
    test_local_vs_published()
    test_wiring()
    print("\nRESULT: %d passed / %d failed" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  FAILED:", f)
        sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main_()

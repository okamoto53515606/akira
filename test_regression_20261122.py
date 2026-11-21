"""2026-11-22 の回帰テスト。

事象（okamo指摘・2026-11-22 05:00 JST の自動ラン）:
  1. トークン計算機の「参考円換算」が全行 **¥0**
     → data/models.json に fx（為替）が無く、`#fx-rate` の初期値が空だったため
       f = parseFloat("") || 0。ページは 200・表も出るので 7ゲートは全部緑。
  2. /changelog/ に今日の更新が **0件**
     → 2026-11-21 に追加した publish_and_verify が、site_upload がやっていた
       「中身が変わった既存ページを site_events に足す」処理を持っていなかった。

ここでは「同じ壊れ方を入れた入力」に対して、追加した仕組みが**鳴る**ことを確かめる。
ネットワーク・AWS・LLM は使わない。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import tools  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name +
          (("  <- " + detail) if (detail and not cond) else ""))


# --------------------------------------------------------------- 1. 計算機データ契約
def models_payload(rows=12, fx=None):
    p = {
        "updated": "2026-11-22",
        "source": "test",
        "models": [
            {"name": "M%d" % i, "provider": "openai", "label": "OpenAI",
             "input": 1.0, "output": 2.0, "note": "", "note_en": ""}
            for i in range(rows)
        ],
    }
    if fx is not None:
        p["fx"] = fx
    return p


check("fx が無い models.json は契約違反（全行¥0の原因）",
      any("fx.usd_jpy" in e for e in tools.validate_calculator_models(models_payload())))
check("fx=155 なら合格",
      tools.validate_calculator_models(models_payload(fx={"usd_jpy": 155})) == [])
check("fx=0 は契約違反",
      any("fx.usd_jpy" in e
          for e in tools.validate_calculator_models(models_payload(fx={"usd_jpy": 0}))))
check("fx が文字列は契約違反",
      any("fx.usd_jpy" in e
          for e in tools.validate_calculator_models(
              models_payload(fx={"usd_jpy": "155"}))))

# --------------------------------------------------------------- 2. 台帳→models.json
p = models_payload()
check("fx を入れる（1回目は変更あり）", tools._with_calc_fx(p, 155.0) is True)
check("fx の値が入る", p["fx"]["usd_jpy"] == 155)
check("2回目は変更なし（冪等）", tools._with_calc_fx(p, 155.0) is False)

# --------------------------------------------------------------- 3. 計算機ページの初期値
HTML_EMPTY = ('<input type="number" id="fx-rate" inputmode="decimal" step="0.01" '
              'value=""><p class="fx-note">…</p>')
HTML_OK = HTML_EMPTY.replace('value=""', 'value="155"')
HTML_MISSING = '<p>為替の入力欄が無い</p>'

check("空の初期値は None（＝故障）", tools._calc_fx_default(HTML_EMPTY) is None)
check("155 の初期値は 155.0", tools._calc_fx_default(HTML_OK) == 155.0)
patched = tools._patch_calc_fx_default(HTML_EMPTY, 155.0)
check("空の初期値を 155 に直す", 'id="fx-rate"' in patched and 'value="155"' in patched,
      patched[:120])
check("直した結果は冪等", tools._patch_calc_fx_default(patched, 155.0) == patched)
check("入力欄が無いページは触らない",
      tools._patch_calc_fx_default(HTML_MISSING, 155.0) == HTML_MISSING)

# ------------------------------------------- 4. publish_and_verify が更新履歴に足す
# 2026-11-22 の /changelog/ 0件は「公開ツールが site_events を登録しない」こと。
# S3・描画・invalidationを偽物にして、公開対象の新旧HTMLだけを本物の判定に通す。

OLD = ('<!DOCTYPE html><html lang="ja"><head><title>料金比較</title>'
       '<script type="application/ld+json">{"dateModified":"2026-11-21"}</script>'
       '</head><body><div class="updated-bar"><span class="dot">●</span>'
       '<time datetime="2026-11-21">2026年11月21日</time></div>'
       '<table><tr><td>$1.00</td></tr></table></body></html>')
NEW = OLD.replace("$1.00", "$1.50")            # 中身が変わった
DATE_ONLY = OLD.replace("2026-11-21", "2026-11-22")   # 日付だけ変わった


class FakeS3:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.uploads = []

    def head_object(self, Bucket=None, Key=None):
        if Key not in self.objects:
            from botocore.exceptions import ClientError
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {"ContentLength": len(self.objects[Key])}

    def get_object(self, Bucket=None, Key=None):
        from io import BytesIO
        return {"Body": BytesIO(self.objects[Key])}

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.uploads.append(key)
        with open(filename, "rb") as fh:
            self.objects[key] = fh.read()


def run_publish_and_verify(local_new):
    """tempのサイトで publish_and_verify を1回走らせ、登録された更新を返す。"""
    tmp = tempfile.mkdtemp(prefix="akira_pv_")
    site = os.path.join(tmp, "site")
    os.makedirs(os.path.join(site, "pricing"), exist_ok=True)
    target = os.path.join(site, "pricing", "index.html")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(local_new)

    captured = {"updates": [], "entrypoints": 0}
    fake = FakeS3({"pricing/index.html": OLD.encode("utf-8")})

    saved = (tools.SITE_LOCAL_DIR, tools.boto3.client,
             tools._render_site_from_ledger, tools._audit_gate_errors,
             tools._structure_gate_errors, tools._register_site_updates,
             tools._register_site_event, tools._render_and_publish_entrypoints,
             tools._bump_sitemap_lastmod, tools.flush_invalidations,
             tools._invalidation_paths)

    def fake_register_updates(items):
        captured["updates"] += list(items)
        return [s for s, _, _ in items]

    def fake_entrypoints(base_dir, s3):
        captured["entrypoints"] += 1
        return ["changelog/index.html"]

    try:
        tools.SITE_LOCAL_DIR = site
        tools.boto3.client = lambda *a, **k: fake
        tools._render_site_from_ledger = lambda base_dir: []
        tools._audit_gate_errors = lambda *a, **k: []
        tools._structure_gate_errors = lambda *a, **k: []
        tools._register_site_updates = fake_register_updates
        tools._register_site_event = lambda rel, base_dir, is_new=False: ""
        tools._render_and_publish_entrypoints = fake_entrypoints
        tools._bump_sitemap_lastmod = lambda *a, **k: False
        tools.flush_invalidations = lambda: None
        tools._invalidation_paths.clear()
        res = tools.publish_and_verify("pricing/index.html", live=False)
    finally:
        (tools.SITE_LOCAL_DIR, tools.boto3.client,
         tools._render_site_from_ledger, tools._audit_gate_errors,
         tools._structure_gate_errors, tools._register_site_updates,
         tools._register_site_event, tools._render_and_publish_entrypoints,
         tools._bump_sitemap_lastmod, tools.flush_invalidations,
         tools._invalidation_paths) = saved
    return res, captured


res, cap = run_publish_and_verify(NEW)
check("中身が変わった既存ページが site_events の対象になる",
      [u[0] for u in cap["updates"]] == ["pricing"], str(cap["updates"]))
check("登録したら入り口（トップ/更新履歴）を再描画する",
      cap["entrypoints"] == 1 and res.get("site_events_added") == ["pricing"])
check("結果に entrypoints_refreshed が載る",
      res.get("entrypoints_refreshed") == ["changelog/index.html"], str(res))

res2, cap2 = run_publish_and_verify(DATE_ONLY)
check("日付だけの変更は履歴に載せない（指紋で判定）",
      cap2["updates"] == [] and cap2["entrypoints"] == 0, str(cap2["updates"]))

# ------------------------------- 5. トップの「直近の更新」と台帳の突き合わせ
# 11-22 は /changelog/ だけ直してトップを公開し忘れ、「履歴は11-22・トップは11-21」
# という食い違いが残った。同じ台帳から描く2か所を突き合わせる検査を足した。
TOP_OLD = ('<html><body><section><!-- topcl:begin -->'
           '<ul><li><span class="cl-date">2026-11-21</span> <span class="cl-text">x</span></li>'
           '<li><span class="cl-date">2026-11-19</span> <span class="cl-text">y</span></li></ul>'
           '<!-- topcl:end --></section></body></html>')
TOP_NEW = TOP_OLD.replace("2026-11-21", "2026-11-22")
TOP_NOMARK = '<html><body><p>マーカー無し</p></body></html>'

check("トップの直近の更新から最新日を取る", tools._top_latest_event_date(TOP_OLD) == "2026-11-21")
check("マーカーが無ければ空", tools._top_latest_event_date(TOP_NOMARK) == "")
_FACTS = {"models": {"m1": {"released": "2026-11-10",
                            "events": [{"date": "2026-11-12"}]}},
          "site_events": [{"date": "2026-11-22"}, {"date": "2026-11-19"}]}
check("台帳の最新イベント日を取る", tools._ledger_latest_event_date(_FACTS) == "2026-11-22")
check("トップが台帳に追いつけば一致", tools._top_latest_event_date(TOP_NEW)
      == tools._ledger_latest_event_date(_FACTS))

print("\nRESULT: %d passed / %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)

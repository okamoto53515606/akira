"""全ゲートを1回で回す自己点検ツール（2026-11-15 追加 / ★3）。

なぜ必要か:
    2026-11-15 のランで Akira は「check_page_shape は存在しないツールだ」と誤認し、
    日報にそう書いた。実際は `site_upload` が内部で走らせている**スクリプト**で、
    6本のゲートはどれも `python3 tools/xxx.py /tmp/site` で手動実行できる。
    しかし**6本を個別に叩く手順は踏まれない**（プロンプトに書いても実行されない、
    というのがこの1週間の一貫した観測）。だから1呼び出しにまとめる。

検査するもの:
    1. 既存の6ゲート（page_shape / css_contract / site_integrity / dates /
       facts_consistency / site_pages）
    2. 決定事項の機械照合（蒸し返し禁止のうち、機械で見えるものだけ）
    3. 台帳とのズレ（render_site を1回かけたときに差分が出るか＝HTMLの手編集が
       次の描画で消える状態か）

使い方:
    self_check()                      # /tmp/site と /workspace
    self_check("/tmp/site", "/workspace")
    python3 self_check.py [site] [workspace]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from strands import tool

HERE = Path(__file__).resolve().parent
DEFAULT_SITE = os.environ.get("SITE_LOCAL_DIR", "") or "/tmp/site"
DEFAULT_WS = os.environ.get("WORKSPACE_DIR", "") or "/workspace"

# (表示名, スクリプト, 追加引数) — 追加引数は site の後ろに付ける
GATES = [
    ("page_shape", "check_page_shape.py", []),
    ("css_contract", "check_css_contract.py", []),
    ("site_integrity", "check_site_integrity.py", []),
    ("dates", "check_dates.py", []),
    ("facts_consistency", "check_facts_consistency.py", ["__WS__"]),
    ("site_pages", "check_site_pages.py", []),
]
SUM_RE = re.compile(r"ERROR:\s*(\d+)(?:\s*/\s*WARN:\s*(\d+))?")
ERR_LINE_RE = re.compile(r"\[ERROR\](.*)")


def _run_gate(script: str, args: list) -> tuple:
    """1本のゲートを実行して (rc, stdout) を返す。"""
    p = HERE / script
    if not p.exists():
        return 127, "（%s が見つからない）" % script
    try:
        r = subprocess.run([sys.executable, str(p)] + args,
                           capture_output=True, text=True, timeout=180)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "（タイムアウト）"
    except Exception as e:  # noqa: BLE001
        return 1, "（実行失敗: %s）" % e


def _parse(out: str) -> tuple:
    """出力から ERROR/WARN 件数と [ERROR] 行を拾う。"""
    e = w = 0
    m = SUM_RE.search(out)
    if m:
        e = int(m.group(1))
        w = int(m.group(2) or 0)
    else:
        e = len(ERR_LINE_RE.findall(out))
    errs = [x.strip() for x in ERR_LINE_RE.findall(out)]
    return e, w, errs


# ------------------------------------------------------------------ 決定事項の照合
def _decision_errors(site: Path) -> list:
    """「蒸し返すな」決定のうち**機械で見えるものだけ**を照合する。

    プロンプトに書いただけの禁止は守られない（11-15 に /pricing/ の53行中26行が
    「New」だった）。ここで毎回数える。
    """
    errs = []

    # 1) New ラベル禁止（2026-11-15）。状態は状態列で表す。
    p = site / "pricing/index.html"
    if p.exists():
        t = p.read_text(encoding="utf-8")
        n = len(re.findall(r">\s*(?:New|NEW|🆕|値下げ?)\s*<", t))
        if n:
            errs.append("new-label: /pricing/ に「New/値下」ラベル %d件（状態列で表す）" % n)

    # 2) 見た目の言語切替リンク禁止（2026-09-05）。hreflang だけで配分する。
    hits = []
    for f in sorted(site.rglob("*.html")):
        try:
            t = f.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        c = (len(re.findall(r'class="[^"]*\blang-switch', t))
             + t.count("English version")
             + t.count("Japanese version"))
        if c:
            hits.append("%s(%d)" % (f.relative_to(site), c))
    if hits:
        errs.append("lang-switch: 見た目の言語切替が %dページ: %s"
                    % (len(hits), ", ".join(hits[:5])))

    # 3) 為替は 1ドル=155円固定（2026-11-15）。円換算するページに明記があるか。
    for rel in ("calculator/index.html", "en/calculator/index.html"):
        p = site / rel
        if p.exists() and "155" not in p.read_text(encoding="utf-8"):
            errs.append("fx-155: /%s に 155円の記載が無い" % rel)

    return errs


# ------------------------------------------------------------------ 台帳とのズレ
def _render_drift(site: Path, ws: Path) -> list:
    """台帳から描き直したときに差分が出るファイル（＝HTMLの手編集が消える状態）。"""
    tmp = Path(tempfile.mkdtemp(prefix="selfcheck_"))
    try:
        copy = tmp / "site"
        shutil.copytree(site, copy)
        p = HERE / "render_site.py"
        if not p.exists():
            return []
        r = subprocess.run(
            [sys.executable, str(p), "--site", str(copy), "--workspace", str(ws)],
            capture_output=True, text=True, timeout=300,
        )
        out = (r.stdout or "") + (r.stderr or "")
        drift = [ln.strip()[2:] for ln in out.splitlines()
                 if ln.strip().startswith("- ") and "/" in ln or ln.strip().startswith("- sitemap")]
        if "render:" in out and "0 file(s) changed" in out:
            return []
        if not drift:
            drift = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("-")]
        return drift[:10]
    except Exception as e:  # noqa: BLE001
        return ["（描画できず: %s）" % e]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ 本体
@tool
def self_check(site_dir: str = "", workspace_dir: str = "") -> str:
    """公開前後に必ず呼ぶ自己点検。全ゲート＋決定事項＋台帳ズレを1回で返す。

    **作業の最初と最後に呼ぶこと。** 最初に呼べば「いま何が赤いか」が分かり、
    最後に呼べば「公開してよいか」が分かる。ERROR が1件でもあれば公開しない。

    Args:
        site_dir: 検査するローカルサイト。省略時は SITE_LOCAL_DIR、無ければ /tmp/site。
        workspace_dir: ワークスペース。省略時は WORKSPACE_DIR、無ければ /workspace。

    Returns:
        1画面に収まるテキストレポート。
    """
    site = Path(site_dir or DEFAULT_SITE)
    ws = Path(workspace_dir or DEFAULT_WS)
    if not site.is_dir():
        return "self_check: サイトが見つからない（%s）" % site

    lines = ["## self_check（公開前の必須確認）"]
    total_e = total_w = 0
    for name, script, extra in GATES:
        args = [str(site)] + [str(ws) if a == "__WS__" else a for a in extra]
        rc, out = _run_gate(script, args)
        e, w, errs = _parse(out)
        if rc == 127:
            lines.append("- %-18s 実行できず（%s）" % (name, script))
            continue
        total_e += e
        total_w += w
        lines.append("- %-18s ERROR %-3d WARN %d" % (name, e, w))
        for x in errs[:3]:
            lines.append("    · " + x[:160])
        if len(errs) > 3:
            lines.append("    · …他 %d件" % (len(errs) - 3))

    dec = _decision_errors(site)
    lines.append("- %-18s ERROR %d" % ("決定事項", len(dec)))
    for x in dec[:5]:
        lines.append("    · " + x[:160])

    drift = _render_drift(site, ws)
    lines.append("- %-18s %s" % ("台帳とのズレ", "0件" if not drift else "%d件" % len(drift)))
    for x in drift[:5]:
        lines.append("    · " + x[:160])
    if drift:
        lines.append("    · ↑これらのファイルは**手で編集されている**。次の描画で"
                     "台帳の内容に戻る。台帳（facts.json）を直すこと。")

    ok = (total_e == 0 and not dec)
    lines.append("")
    lines.append("判定: " + ("**公開可**（ERROR 0）" if ok else
                             "**公開不可**（ERROR %d件を先に直す）" % (total_e + len(dec))))
    if total_w:
        lines.append("※ WARN %d件は公開を止めない。うち直せるものを直す。" % total_w)
    return "\n".join(lines)


TOOL = self_check

if __name__ == "__main__":
    print(self_check(sys.argv[1] if len(sys.argv) > 1 else "",
                     sys.argv[2] if len(sys.argv) > 2 else ""))

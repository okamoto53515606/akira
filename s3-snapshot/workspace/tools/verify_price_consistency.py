"""料金データの整合性チェッカー（LLM Data Hub）。

モデル退役・値下げのたびにサイト全体を手で grep していた作業を自動化する。
/workspace/data/price-sot.json（料金データの単一の真実。2026-09-27 に
`data/models.json` から改名。サイト側の同名ファイルと取り違える事故の対策）に登録した
「退役単価（stale_price_patterns）」が、許容ファイル以外に残っていないかを検査する。

使い方:
    python3 /workspace/tools/verify_price_consistency.py [site_dir]
    site_dir 省略時は環境変数 SITE_LOCAL_DIR、それも無ければ /tmp/site

import時のネットワーク通信・ファイル書込は行わない（読取のみ）。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_WORKSPACE = "/workspace"
MODELS_JSON = "data/price-sot.json"


def _workspace() -> Path:
    return Path(os.environ.get("WORKSPACE_DIR", DEFAULT_WORKSPACE))


def _site_dir(arg: str = "") -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("SITE_LOCAL_DIR", "")
    return Path(env) if env else Path("/tmp/site")


def _load_models(workspace: Path) -> dict:
    path = workspace / MODELS_JSON
    if not path.exists():
        raise FileNotFoundError("models.json not found: %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def _find_all(haystack: str, needle: str):
    """needle の全出現位置（重複なしの開始インデックス）。"""
    out, i = [], haystack.find(needle)
    while i != -1:
        out.append(i)
        i = haystack.find(needle, i + 1)
    return out


def _is_allowed(rel: str, allow: dict) -> bool:
    rel = "/" + rel.strip("/") + "/"
    for key in allow:
        k = "/" + key.strip("/") + "/"
        if rel == k or rel.startswith(k):
            return True
    return False


def check(site_dir: Path) -> dict:
    """Returns {"stale": [...], "missing_current": [...], "scanned": n}"""
    data = _load_models(_workspace())
    patterns = data.get("stale_price_patterns", [])
    allow = (data.get("stale_policy") or {}).get("allow", {}) or {}

    stale, missing, scanned = [], [], 0
    for html in sorted(site_dir.rglob("*.html")):
        rel = str(html.relative_to(site_dir))
        scanned += 1
        try:
            text = html.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if not _is_allowed(rel, allow):
            for i, line in enumerate(text.splitlines(), 1):
                if "deepseek" not in line.lower():
                    continue
                hits = [p for p in patterns if p in line]
                if hits:
                    stale.append((rel, i, hits, line.strip()[:160]))

    # 現行単価が出典つきで載っているべきファイル（DeepSeek の金額に触れているのに
    # 現行単価シグネチャが1つも無いファイル）を検出する。比較表の片側だけ旧価格のまま、
    # のような更新漏れを捕まえるための検査。
    sig = data.get("current_price_signatures", [])
    if sig:
        WINDOW = 250  # モデル名の近くに金額が無いページ（単なる被リンク）は対象外にする
        for html in sorted(site_dir.rglob("*.html")):
            rel = str(html.relative_to(site_dir))
            text = html.read_text(encoding="utf-8")
            low = text.lower()
            needles = [n.lower() for n in data.get("family_needles", ["v4.1 flash", "v4 pro", "deepseek-flash"])]
            dollars = [i for i, ch in enumerate(text) if ch == "$"]
            mentions_money = any(
                any(abs(d - i) <= WINDOW for d in dollars)
                for n in needles
                for i in _find_all(low, n)
            )
            if not mentions_money or _is_allowed(rel, allow):
                continue
            if not any(s in text for s in sig):
                stale.append((rel, 0, ["no current price"], "DeepSeek の金額に触れているが現行単価（%s のいずれか）が無い" % "/".join(sig)))

    # current モデルのページに現行単価が載っているか（代表2値だけ軽く確認）
    for key, m in (data.get("models") or {}).items():
        if m.get("status") != "current":
            continue
        price = m.get("price") or {}
        want = []
        for f in ("cache_miss_input_offpeak", "output_offpeak"):
            if f in price:
                want.append("$%s" % ("%g" % price[f]))
        for page in m.get("pages", []):
            f = site_dir / page.strip("/") / "index.html"
            if not f.exists():
                missing.append((page, "page missing"))
                continue
            t = f.read_text(encoding="utf-8")
            for w in want:
                if w not in t:
                    missing.append((page, "current price %s not found" % w))
    return {"stale": stale, "missing_current": missing, "scanned": scanned}


def main() -> int:
    # 2026-09-27 修正: 従来は環境変数 SITE_DIR_ARG しか見ておらず、CLIで渡した site_dir が
    # 無視されていた（/tmp/site が無い環境では 0 ファイルを走査して「更新漏れなし」と
    # 誤って報告する＝静かな偽OK）。CLI引数を最優先で使う。
    arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SITE_DIR_ARG", "")
    site = _site_dir(arg)
    res = check(site)
    print("scanned html files: %d (site_dir=%s)" % (res["scanned"], site))
    if res["stale"]:
        print("\n[STALE] 退役単価が残っています（要修正）: %d 件" % len(res["stale"]))
        for rel, line_no, hits, snippet in res["stale"]:
            print("  - %s:%d %s | %s" % (rel, line_no, ",".join(hits), snippet))
    else:
        print("\n[STALE] 更新漏れなし")
    if res["missing_current"]:
        print("\n[MISSING] 現行モデルのページに現行単価が見つかりません: %d 件" % len(res["missing_current"]))
        for page, why in res["missing_current"]:
            print("  - %s: %s" % (page, why))
    else:
        print("[MISSING] 現行単価OK")
    return 1 if (res["stale"] or res["missing_current"]) else 0


try:  # strands があればツールとして登録できるようにする（無くても動く）
    from strands import tool as _tool

    @_tool
    def verify_price_consistency(site_dir: str = "") -> str:
        """サイト全体の料金表記を /workspace/data/price-sot.json と突き合わせ、退役単価の残存（更新漏れ）を検出する。

        Args:
            site_dir: 検査するローカルサイトのディレクトリ。省略時は SITE_LOCAL_DIR、無ければ /tmp/site。

        Returns:
            検出結果のテキストレポート（更新漏れが無ければその旨）。
        """
        res = check(_site_dir(site_dir))
        lines = ["scanned html files: %d" % res["scanned"]]
        if res["stale"]:
            lines.append("[STALE] 退役単価が残存: %d 件" % len(res["stale"]))
            lines += ["  - %s:%d %s | %s" % s for s in res["stale"]]
        else:
            lines.append("[STALE] 更新漏れなし")
        if res["missing_current"]:
            lines.append("[MISSING] 現行単価が未反映: %d 件" % len(res["missing_current"]))
            lines += ["  - %s: %s" % m for m in res["missing_current"]]
        return "\n".join(lines)

    TOOL = verify_price_consistency
except Exception:  # strands 未インストール環境（ローカル検証時など）
    TOOL = None


if __name__ == "__main__":
    raise SystemExit(main())

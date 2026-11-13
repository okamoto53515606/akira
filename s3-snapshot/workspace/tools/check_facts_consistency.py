"""サイト横断の整合性チェッカー（LLM Data Hub）: ページ間で事実が食い違っていないかを見る。

背景（2026-11-14）:
    既存の公開ゲートは「1ページの構造」（check_site_pages）と「日付」（check_dates）だけ
    を見ていた。そのため、次の3種類の故障が全部すり抜けて公開されていた。

      1. /timeline/ の並び順が壊れている（新規が末尾に追記され、降順でない）
      2. 日英でエントリ数が違う（ja 54件 / en 49件。凍結中に追加した5件が欠落）
      3. 同じモデルの状態がページによって違う（/china-ai/ に「プレビュー開始」と
         「公式は学習中」が併存、/pricing/ に Hydrogen が無い）

    どれもHTTP 200で本文も読めるため「表示されない誤情報」になる。原因は
    「事実の置き場所がHTMLの文章」であること（docs/facts-ledger-plan-2026-11-14.md）。
    恒久対策（facts.json + レンダラ）は未実装なので、まず**検出だけ**を機械化する。

検査項目:
    [ERROR] timeline-integrity
        - tl-date が YYYY-MM-DD でない
        - 日付が降順でない
        - 同一ファイル内で id が重複
        - ja と en の id 集合が一致しない
    [WARN]  coverage
        - 直近30日の timeline エントリのモデル名が /pricing/ にも
          data/models.json にも無い（反映漏れの疑い）
    [WARN]  sot-drift
        - /workspace/data/price-sot.json の last_verified が14日より古い
        - 直近30日の timeline エントリが SOT に無い
    [INFO]  append-style
        - 「YYYY-MM-DD 追記」「Update, YYYY-MM-DD」形式のブロックを持つページ数。
          日付付きの注記そのものは正当な運用なので、**件数そのものは善悪ではない**。
          見るのは推移で、**増え続けるなら「追記型編集」が直っていない**（仮説H1の判定指標）。
          2026-11-14 の実測は 8件（claude-fable-5-1 / deepseek-v4-1-flash(2) /
          deepseek-v4-pro / gpt-6 / en/gpt-6 / multimodal / qwen-3-8-flash / timeline）。

使い方:
    python3 /workspace/tools/check_facts_consistency.py [site_dir]
    site_dir 省略時は環境変数 SITE_LOCAL_DIR、無ければ /tmp/site。
    ワークスペースは WORKSPACE_DIR（既定 /workspace）。

import時のネットワーク通信・ファイル書込は行わない（読取のみ）。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from strands import tool

DEFAULT_SITE_DIRS = (os.environ.get("SITE_LOCAL_DIR", ""), "/tmp/site")
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", "/workspace")
SOT_REL = "data/price-sot.json"
RECENT_DAYS = 30
SOT_MAX_AGE_DAYS = 14

ART_RE = re.compile(r'<article class="tl-item[^"]*" id="([^"]+)">(.*?)</article>', re.S)
DATE_RE = re.compile(r'<div class="tl-date">([^<\s]*)')
TITLE_RE = re.compile(r'<h2 class="tl-title">(.*?)</h2>', re.S)
APPEND_RE = re.compile(r'(?:<strong>)?\d{4}-\d{2}-\d{2}\s*追記|Update,\s*\d{4}-\d{2}-\d{2}')


def _norm(text: str) -> str:
    """比較用の正規化（タグ除去・空白/ハイフン除去・小文字化）。"""
    t = re.sub(r"<[^>]+>", "", text)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"[\s\-–—_/]+", "", t).lower()


def _timeline(site: Path, rel: str):
    path = site / rel
    if not path.exists():
        return None
    html = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in ART_RE.finditer(html):
        aid, body = m.group(1), m.group(2)
        d = DATE_RE.search(body)
        t = TITLE_RE.search(body)
        out.append({
            "id": aid,
            "date": d.group(1) if d else "",
            "title": t.group(1) if t else "",
        })
    return out


def _models_json_names(site: Path):
    path = site / "data" / "models.json"
    if not path.exists():
        return set()
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return set()
    return {_norm(m.get("name", "")) for m in d.get("models", []) if isinstance(m, dict)}


def _short_name(title: str) -> str:
    """「Gemini 4 Hydrogen 発表 — …」から「Gemini 4 Hydrogen」を取り出す（表示用）。"""
    return _name_candidates(title)[0] if _name_candidates(title) else ""


def _name_candidates(title: str):
    """タイトルから比較用のモデル名候補を作る。

    「Claude Fable 5.2 / Mythos 5.2 公開 — …」のように複数名を含むタイトルは
    分割して**どれか1つでも一致すれば反映済み**とみなす（そうしないと常に
    「未反映」の誤検知になる）。
    """
    head = re.split(r"\s+—\s+|\s+-\s+", title)[0]
    head = re.sub(r"<[^>]+>", "", head)
    head = re.sub(r"\s*(発表|公開|提供開始|が一般提供へ|released|announced|goes live|goes generally available)$",
                  "", head.strip())
    parts = re.split(r"\s*[/／・]\s*", head)
    out = []
    for p in parts:
        p = re.sub(r"\s*(シリーズ|series)$", "", p.strip())
        if p:
            out.append(p)
    return out or [head.strip()]


def report(site_dir: str) -> str:
    site = Path(site_dir)
    if not site.is_dir():
        return "site dir not found: %s" % site_dir
    errors, warns, infos = [], [], []

    # --- 1. timeline の構造 ---
    ja = _timeline(site, "timeline/index.html")
    en = _timeline(site, "en/timeline/index.html")
    if ja is None or en is None:
        warns.append("timeline-integrity: timeline/index.html か en/timeline/index.html が見つかりません")
    else:
        for label, items in (("ja", ja), ("en", en)):
            dates = [x["date"] for x in items]
            bad = [d for d in dates if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "")]
            if bad:
                errors.append("timeline-integrity: %s に YYYY-MM-DD でない日付が %d 件: %s"
                              % (label, len(bad), ", ".join(sorted(set(bad))[:5])))
            valid = [d for d in dates if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "")]
            if valid != sorted(valid, reverse=True):
                # 最初に崩れた位置を指す（直すときに1件目を見ればよい）
                bad_at = next(i for i in range(1, len(valid)) if valid[i] > valid[i - 1])
                errors.append("timeline-integrity: %s が日付降順でない（%s の位置: %s → %s）"
                              % (label, bad_at + 1, valid[bad_at - 1], valid[bad_at]))
            ids = [x["id"] for x in items]
            dup = sorted({i for i in ids if ids.count(i) > 1})
            if dup:
                errors.append("timeline-integrity: %s で id 重複: %s" % (label, ", ".join(dup)))
        only_ja = {x["id"] for x in ja} - {x["id"] for x in en}
        only_en = {x["id"] for x in en} - {x["id"] for x in ja}
        if only_ja or only_en:
            errors.append("timeline-integrity: ja のみ %d 件 / en のみ %d 件（ja=%d, en=%d）: %s%s"
                          % (len(only_ja), len(only_en), len(ja), len(en),
                             ",".join(sorted(only_ja)[:6]),
                             (" / " + ",".join(sorted(only_en)[:6])) if only_en else ""))
        infos.append("timeline: ja %d件 / en %d件" % (len(ja), len(en)))

    # --- 2. 直近エントリの反映漏れ ---
    recent = []
    cutoff = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
    for x in (ja or []):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x["date"] or "") and x["date"] >= cutoff:
            recent.append(x)
    if recent:
        pricing_html = ""
        for rel in ("pricing/index.html", "en/pricing/index.html"):
            p = site / rel
            if p.exists():
                pricing_html += p.read_text(encoding="utf-8", errors="replace")
        pricing_norm = _norm(pricing_html)
        calc = _models_json_names(site)
        missing = []
        for x in recent:
            cands = [c for c in _name_candidates(x["title"]) if c]
            if not cands:
                continue
            if any(_norm(c) in pricing_norm or _norm(c) in calc for c in cands):
                continue
            missing.append("%s(%s)" % (cands[0], x["date"]))
        if missing:
            warns.append("coverage: 直近%d日の年表エントリが /pricing/ と計算機データのどちらにも無い %d件: %s"
                         % (RECENT_DAYS, len(missing), ", ".join(missing[:8])))

    # --- 3. SOT の鮮度 ---
    sot_path = Path(WORKSPACE_DIR) / SOT_REL
    if sot_path.exists():
        try:
            sot = json.loads(sot_path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            warns.append("sot-drift: %s が JSON として読めません: %s" % (SOT_REL, e))
            sot = None
        if sot:
            lv = str(sot.get("last_verified", ""))
            try:
                age = (date.today() - datetime.strptime(lv[:10], "%Y-%m-%d").date()).days
            except Exception:  # noqa: BLE001
                age = None
                warns.append("sot-drift: last_verified を読めません（%r）" % lv)
            if age is not None and age > SOT_MAX_AGE_DAYS:
                warns.append("sot-drift: %s の last_verified=%s が %d日前（>%d日）"
                             % (SOT_REL, lv[:10], age, SOT_MAX_AGE_DAYS))
            keys = set()
            models = sot.get("models")
            if isinstance(models, dict):
                for k, v in models.items():
                    keys.add(_norm(k))
                    if isinstance(v, dict):
                        keys.add(_norm(v.get("name_en", "")))
                        keys.add(_norm(v.get("name_ja", "")))
            gap = []
            for x in recent:
                cands = [c for c in _name_candidates(x["title"]) if c]
                if not cands or any(_norm(c) in keys for c in cands):
                    continue
                gap.append(cands[0])
            if gap:
                warns.append("sot-drift: 直近%d日の年表エントリで SOT 未収録 %d件: %s"
                             % (RECENT_DAYS, len(gap), ", ".join(dict.fromkeys(gap))))
    else:
        warns.append("sot-drift: %s が見つかりません（WORKSPACE_DIR=%s）" % (SOT_REL, WORKSPACE_DIR))

    # --- 4. 追記型編集の残数（H1の判定指標）---
    appended = []
    for p in sorted(site.rglob("*.html")):
        try:
            html = p.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        n = len(APPEND_RE.findall(html))
        if n:
            appended.append("%s(%d)" % (p.relative_to(site).as_posix(), n))
    infos.append("append-style: 追記ブロックを持つページ %d件%s"
                 % (len(appended), (" … " + ", ".join(appended[:8])) if appended else ""))

    lines = ["checked %d html files in %s" % (len(list(site.rglob("*.html"))), site)]
    lines += ["[ERROR] " + e for e in errors]
    lines += ["[WARN]  " + w for w in warns]
    lines += ["[INFO]  " + i for i in infos]
    lines.append("ERROR: %d / WARN: %d" % (len(errors), len(warns)))
    return "\n".join(lines)


@tool
def check_facts_consistency(site_dir: str = "") -> str:
    """サイト横断の整合性を検査する（読み取り専用・LLMコスト0）。

    timeline の並び順・日付形式・日英のエントリ差分、直近エントリの反映漏れ、
    price-sot.json の鮮度、追記型編集の残数をまとめて報告する。
    公開前のゲートとして使い、ERROR が 1件でもあれば公開しない。

    Args:
        site_dir: 検査するローカルサイトのディレクトリ。省略時は SITE_LOCAL_DIR、無ければ /tmp/site。
    """
    if not site_dir:
        for cand in DEFAULT_SITE_DIRS:
            if cand and os.path.isdir(cand):
                site_dir = cand
                break
    if not site_dir or not os.path.isdir(site_dir):
        return "site dir not found"
    return report(site_dir)


TOOL = check_facts_consistency

if __name__ == "__main__":
    default = os.environ.get("SITE_LOCAL_DIR", "") or "/tmp/site"
    print(report(sys.argv[1] if len(sys.argv) > 1 else default))

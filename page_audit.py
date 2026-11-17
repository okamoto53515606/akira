"""ページ監査 — 「古い情報が残ったページ」を**コードで**見つける（2026-11-17 追加）。

なぜ:
    2026-11-17、okamo から2件の指摘が来た。
      ① /china-ai/ のメインビジュアル（OGカード）に 2026-10-29 の日付と
         「Qwen 4 は学習中」が焼き込まれたまま、本文だけ 11-14 に更新されていた。
         目次と本文の間に余白が無い（見た目が詰まっている）。
      ② /deepseek-v4-1-flash/ が「9月の情報」と「10-17 の更新情報」の**追記の寄せ集め**
         になり、読み手に「結局いまどうなのか」が分からない。

    どちらも「ページを直したのに、同じページの別の場所（画像・古い節）が取り残される」
    という同じ型。**人間の目視に頼らず、決定的に検出できる**ので、ここに置く。
    （LLMに「古くないか見て」と頼む方式は 11-15 の鮮度キューで2ラン連続0件だった）

検出するもの（すべて正規表現ベース・LLMコスト0）:
    R1 dateModified と「最終更新」表示の日付が違う
    R2 追記バナー（「2026-11-12 追記:」「Added 2026-11-12:」）が本文に残っている
    R3 同じ見出し構成の表で、同じ行ラベルに違う値が入っている（新旧併存）
    R4 見出しの年月が dateModified より古い（[September 2026] のまま 11月更新 等）
    R5 キービジュアル（OGカード）の生成日がページの dateModified より古い
    R6 見出しに日付が2つ以上あり、7日以上離れている（新旧セクションの併存）
    R7 「取得日 / retrieved」が dateModified より30日以上古い（WARN）

優先度（okamo案「click数の多いページを優先して定期的にチェックする」）:
    data/page_priority.json の score 順に並べ、上位5ページは**7日以内**、
    それ以外は**21日以内**に1回は監査する義務をコードで作る（pick_targets）。
    数字の出どころは GA4 のPVと GSC のクリック。Akira が毎ラン
    set_page_priority で更新する（無ければ既定の並びで動く＝機能は止まらない）。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime

from strands import tool

WORKSPACE_DIR = os.environ.get("WORKSPACE_LOCAL_DIR") or "/workspace"
SITE_DIR = os.environ.get("SITE_LOCAL_DIR") or "/tmp/site"
try:  # 実運用のパスは settings が持っている（env が無いときはそちらに合わせる）
    import settings as _settings

    WORKSPACE_DIR = os.environ.get("WORKSPACE_LOCAL_DIR") or _settings.WORKSPACE_LOCAL_DIR
    SITE_DIR = os.environ.get("SITE_LOCAL_DIR") or getattr(
        _settings, "SITE_LOCAL_DIR", "/tmp/site")
except Exception:  # pragma: no cover - settings が無い単体実行時
    pass

PRIORITY_PATH = os.path.join(WORKSPACE_DIR, "data", "page_priority.json")
SPECS_PATH = os.path.join(WORKSPACE_DIR, "data", "og_specs.json")
STATE_PATH = os.path.join(WORKSPACE_DIR, "data", "page_audit.json")

TOP_INTERVAL_DAYS = 7      # 上位5ページ
OTHER_INTERVAL_DAYS = 21   # それ以外
TOP_COUNT = 5
PER_RUN = 2                # 1ランで監査するページ数

# GA4のPV・GSCのクリックが取れていない初回でも回るようにするための既定順。
# （2026-09-27 の公開資料と直近のGSC実測から。Akira が set_page_priority で上書きする）
DEFAULT_PRIORITY = {
    "schema_note": "ページ監査の優先度。score の大きい順に監査する。pv=GA4のページビュー、clicks=GSCのクリック。Akiraが毎ラン更新する（更新しなくても既定順で動く）。",
    "updated": "2026-11-17",
    "source": "seed: docs/site-overview-2026-09-27.md と GSC 実測（2026-11-17に並べ直し）",
    "pages": [
        {"page": "en/deepseek-v4-1-flash/index.html", "pv": 0, "clicks": 22, "impressions": 2293, "score": 110},
        {"page": "en/china-ai/index.html", "pv": 0, "clicks": 2, "impressions": 5132, "score": 60},
        {"page": "china-ai/index.html", "pv": 0, "clicks": 0, "impressions": 0, "score": 40},
        {"page": "timeline/index.html", "pv": 20, "clicks": 15, "impressions": 280, "score": 95},
        {"page": "en/timeline/index.html", "pv": 19, "clicks": 0, "impressions": 0, "score": 19},
        {"page": "en/pricing/index.html", "pv": 15, "clicks": 0, "impressions": 0, "score": 15},
        {"page": "en/deepseek-v4-pro/index.html", "pv": 22, "clicks": 0, "impressions": 0, "score": 22},
        {"page": "deepseek-v4-1-flash/index.html", "pv": 0, "clicks": 0, "impressions": 0, "score": 30},
        {"page": "pricing/index.html", "pv": 0, "clicks": 0, "impressions": 0, "score": 10},
        {"page": "en/multimodal/index.html", "pv": 14, "clicks": 0, "impressions": 0, "score": 14},
    ],
}


# ---------------------------------------------------------------- helpers
def _load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def _d(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _nice(rel):
    """"china-ai/index.html" → "/china-ai/"（人にもモデルにも読みやすい形）。"""
    return "/" + rel.rsplit("/index.html", 1)[0] + "/"


def _strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()


def priority():
    data = _load(PRIORITY_PATH, None)
    if not data or not data.get("pages"):
        data = dict(DEFAULT_PRIORITY)
        data["pages"] = [dict(p) for p in DEFAULT_PRIORITY["pages"]]
    pages = []
    for i, p in enumerate(data.get("pages", [])):
        if not isinstance(p, dict) or not p.get("page"):
            continue
        p = dict(p)
        p.setdefault("score", (p.get("pv") or 0) + 5 * (p.get("clicks") or 0))
        p["rank"] = i + 1
        pages.append(p)
    pages.sort(key=lambda p: (-p["score"], p["rank"]))
    for i, p in enumerate(pages):
        p["rank"] = i + 1
    return pages


# ---------------------------------------------------------------- 監査ルール
BENCH_PERIOD = re.compile(r"\[\s*(January|February|March|April|May|June|July|August|"
                          r"September|October|November|December)\s+(\d{4})\s*\]")
JA_PERIOD = re.compile(r"(20\d{2})年\s*(\d{1,2})月版")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"])}
PATCH_NOTE = re.compile(r"(20\d{2}-\d{2}-\d{2}\s*追記|追記\s*[:：]|Added\s+20\d{2}-\d{2}-\d{2}\s*[:：])")
RETRIEVED = re.compile(r"(取得日\s*[:：]\s*(20\d{2}-\d{2}-\d{2})|retrieved\s+(20\d{2}-\d{2}-\d{2})|"
                       r"Retrieved\s*[:：]?\s*(20\d{2}-\d{2}-\d{2}))", re.I)
HEADING = re.compile(r"<h[123][^>]*>(.*?)</h[123]>", re.S)
TABLE = re.compile(r"<table.*?</table>", re.S)
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
NUMBER = re.compile(r"(-?\d{1,3}(?:\.\d+)?)")

# 見出しが「日付で始まる」かどうか（R6）。ISO・英語・日本語の3形式を見る。
DATE_HEAD = re.compile(
    r"^\s*(Date\s*[:：]\s*)?(20\d{2}-\d{2}-\d{2}"
    r"|(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s*20\d{2}"
    r"|\d{4}年\s*\d{1,2}月(?:\s*\d{1,2}日)?)")

# R8で「同じ指標の複数値」を探す対象（誤検知を避けるため語彙を限定する）
METRICS = ("HLE", "Terminal-Bench", "DeepSWE", "NL2Repo-Bench", "ProgramBench",
           "Automation-Bench", "Agents' Last Exam", "Apex Bench", "Chartography",
           "BabyVision", "ZeroBench", "GPQA", "Codeforces", "SWE-bench", "MathArena")


def _metric_key(text):
    """指標名と括弧内の条件をキーにする。戻り値は (key, 値が始まる位置) or None。"""
    t = text.strip()
    low = t.lower()
    for name in METRICS:
        if low.startswith(name.lower()):
            rest = t[len(name):]
            m = re.match(r"\s*[（(]([^）)]*)[）)]", rest)
            qual = m.group(1).strip().lower() if m else "-"
            return ("%s|%s" % (name, qual), len(name) + (m.end() if m else 0))
    return None


def _page_meta(html):
    m = re.search(r'"dateModified"\s*:\s*"(20\d{2}-\d{2}-\d{2})"', html)
    modified = _d(m.group(1)) if m else None
    bar = re.search(r'<div class="updated-bar">(.*?)</div>', html, re.S)
    shown = None
    if bar:
        t = re.search(r'<time[^>]*datetime="(20\d{2}-\d{2}-\d{2})"', bar.group(1))
        shown = _d(t.group(1)) if t else None
    return modified, shown


def audit_html(rel, html, specs=None):
    """1ページを検査して [(severity, code, message)] を返す。"""
    out = []
    modified, shown = _page_meta(html)

    # R1 表示とメタの不一致
    if modified and shown and modified != shown:
        out.append(("ERROR", "R1",
                    "最終更新の表示(%s)と JSON-LD dateModified(%s) が違う" % (shown, modified)))

    # R2 追記バナー
    for m in PATCH_NOTE.finditer(html):
        out.append(("ERROR", "R2",
                    "追記バナーが残っている（%s）。現在の状態に統合して、追記の形をやめる"
                    % _strip_tags(m.group(1))[:40]))
        break

    # R3 同じ見出し構成の表で同じ行ラベルに違う値
    groups = {}
    for t in TABLE.finditer(html):
        rows = ROW.findall(t.group(0))
        if len(rows) < 2:
            continue
        head = [_strip_tags(c) for c in CELL.findall(rows[0])]
        if len(head) < 2:
            continue
        key = "|".join(head[:3])
        for r in rows[1:]:
            cells = [_strip_tags(c) for c in CELL.findall(r)]
            if len(cells) >= 2:
                groups.setdefault(key, {}).setdefault(cells[0], set()).add(cells[1])
    for key, labels in groups.items():
        bad = [(lab, vals) for lab, vals in labels.items() if len(vals) > 1]
        if bad:
            lab, vals = sorted(bad)[0]
            out.append(("ERROR", "R3",
                        "表「%s」の行「%s」に複数の値がある（%s）。新旧の併存を疑う"
                        % (key.split("|")[0][:24], lab[:30], " / ".join(sorted(vals))[:60])))
            break

    # R4 見出しの年月が dateModified より古い
    text = _strip_tags(html)
    ref = modified or shown
    if ref:
        periods = []
        for m in BENCH_PERIOD.finditer(text):
            periods.append((int(m.group(2)), MONTHS[m.group(1)], m.group(0)))
        for m in JA_PERIOD.finditer(text):
            periods.append((int(m.group(1)), int(m.group(2)), m.group(0)))
        old = [(y, mo, s) for (y, mo, s) in periods if (y, mo) < (ref.year, ref.month)]
        if old:
            out.append(("ERROR", "R4",
                        "見出しの年月「%s」が最終更新(%s)より古い" % (old[0][2], ref)))

    # R6 「日付で始まる見出し」= 追記の節が残っている疑い
    #      （"2026-10-17 の更新 — …" / "October 17, 2026 update — …" のような節タイトルは、
    #       現在の状態を書く場所ではなく更新を積む場所。読み手には「で、今はどうなの？」になる）
    for h in HEADING.finditer(html):
        t = _strip_tags(h.group(1))
        if DATE_HEAD.match(t):
            out.append(("ERROR", "R6",
                        "日付で始まる見出し「%s」。更新の節を積まず、現在の記述に統合する"
                        % t[:50]))
            break

    # R7 取得日が古い（WARN）
    if ref:
        olds = []
        for m in RETRIEVED.finditer(text):
            d = next((_d(g) for g in m.groups() if g and _d(g)), None)
            if d and (ref - d).days >= 30:
                olds.append(d)
        if olds:
            out.append(("WARN", "R7",
                        "「取得日」が最終更新より30日以上古い（%s）。今の値で取り直したか確認"
                        % min(olds)))

    # R8 同じ指標に2つの値（表と箇条書きの併存 = 新旧の寄せ集め）
    #    R3（同じ見出しの表どうし）では拾えない「表＋箇条書き」の混在をここで拾う。
    #    指標名は既知の語彙だけを見る（誤検知を避けるため）。括弧内の条件
    #    （w/o tools / w/ tools など）は別指標として扱う。
    vals: dict = {}
    for t in TABLE.finditer(html):
        for r in ROW.findall(t.group(0)):
            cells = [_strip_tags(c) for c in CELL.findall(r)]
            if len(cells) >= 2:
                hit = _metric_key(cells[0])
                mnum = NUMBER.search(cells[1])
                if hit and mnum:
                    vals.setdefault(hit[0], set()).add(mnum.group(1))
    for li in re.findall(r"<li[^>]*>(.*?)</li>", html, re.S):
        text_li = _strip_tags(li)
        hit = _metric_key(text_li)
        if hit:
            mnum = NUMBER.search(text_li[hit[1]:])
            if mnum:
                vals.setdefault(hit[0], set()).add(mnum.group(1))
    for k, vs in sorted(vals.items()):
        if len(vs) > 1:
            out.append(("ERROR", "R8",
                        "指標「%s」に複数の値がある（%s）。版の違う数値が併存していないか"
                        % (k.replace("|", " "), " / ".join(sorted(vs)))))
            break

    # R5 キービジュアルの日付
    specs = specs or {}
    spec = (specs.get("pages") or {}).get(rel)
    if spec and ref:
        gen = _d(spec.get("generated", ""))
        if gen and gen < ref:
            out.append(("ERROR", "R5",
                        "キービジュアル(%s)が %s のまま。本文の最終更新 %s より古い"
                        % (spec.get("image"), gen, ref)))
    return out


# ---------------------------------------------------------------- 対象選定
def pick_targets(today=None, n=PER_RUN, write=True):
    """今日の監査対象を**コードで**決める（LLMの判断を挟まない）。"""
    today = today or date.today().isoformat()
    state = _load(STATE_PATH, {})
    seen = state.get("pages", {})
    rows = priority()
    due, rest = [], []
    for p in rows:
        last = _d((seen.get(p["page"]) or {}).get("last", ""))
        interval = TOP_INTERVAL_DAYS if p["rank"] <= TOP_COUNT else OTHER_INTERVAL_DAYS
        age = 9999 if last is None else (date.fromisoformat(today) - last).days
        item = dict(p, last=last.isoformat() if last else "", age=age, interval=interval)
        (due if age >= interval else rest).append(item)
    due.sort(key=lambda x: x["rank"])
    rest.sort(key=lambda x: (-x["age"], x["rank"]))
    picked = (due + rest)[:n]
    if write:
        state.setdefault("assignments", {})[today] = [p["page"] for p in picked]
        state["updated"] = today
        _save(STATE_PATH, state)
    return picked


def mission_line(today=None):
    """ミッションに差し込む「今日の必須監査」。"""
    targets = pick_targets(today)
    if not targets:
        return "## 今日の必須監査（優先度順）\n- 対象0件（page_priority.json が空）"
    lines = ["## 今日の必須監査（コードが優先度順に選んだ。**必ず実行する**）"]
    for p in targets:
        why = "前回監査から%s日（基準%d日）" % (p["age"] if p["age"] < 9999 else "未監査", p["interval"])
        lines.append("- `%s` … %s・優先度%d位" % (_nice(p["page"]), why, p["rank"]))
    lines += [
        "- `audit_pages` を**そのまま呼ぶ**（対象を引数で渡さなくてよい）。返った ERROR は",
        "  その日のうちに直す（直せないものは site_plan に理由つきで残す）",
        "- 直したら `audit_pages` をもう一度呼び、ERROR 0 を確認する",
        "- **キービジュアル（ページ先頭の画像）は Gemini子育てママに視認させる**：",
        "  焼き込まれた日付・モデル名・数値が本文と一致しているか（S10）",
        "- 監査結果は日報に1行書く（0件でも「監査: 異常なし」と書く）",
    ]
    return "\n".join(lines)


def verify_assigned(today=None):
    """その日に割り当てた監査が実際に走ったかを検算する（後処理用）。"""
    today = today or date.today().isoformat()
    state = _load(STATE_PATH, {})
    assigned = (state.get("assignments") or {}).get(today) or []
    if not assigned:
        return "ページ監査: 本日の割当なし"
    done = {r.get("page") for r in state.get("last_run") or [] if r.get("date") == today}
    missing = [p for p in assigned if p not in done]
    if not missing:
        return "ページ監査: %dページ実施済み（%s）" % (
            len(assigned), ", ".join(_nice(x) for x in assigned))
    return "ページ監査: **未実施 %d件**（%s）" % (
        len(missing), ", ".join(_nice(x) for x in missing))


# ---------------------------------------------------------------- ツール
@tool
def audit_pages(pages: str = "") -> str:
    """ページの「古い情報・追記の混在・キービジュアルの取り残し」を機械検査する。

    今日の監査対象はコードが優先度順（GA4のPV・GSCのクリック）に選んでいる。
    引数を省略するとその対象を検査する。

    Args:
        pages: カンマ区切りのサイト内パス（例 "china-ai/index.html,en/china-ai/index.html"）。
            省略時は今日の割当分。

    Returns:
        検査レポート。ERROR が1件でもあれば、その日のうちに直すこと。
    """
    today = date.today().isoformat()
    state = _load(STATE_PATH, {})
    if pages.strip():
        rels = [p.strip().lstrip("/") for p in re.split(r"[,\s]+", pages) if p.strip()]
        rels = [r if r.endswith(".html") else r.rstrip("/") + "/index.html" for r in rels]
    else:
        rels = (state.get("assignments") or {}).get(today) or [p["page"] for p in pick_targets(today)]

    specs = _load(SPECS_PATH, {})
    lines, err, warn = [], 0, 0
    runs = []
    for rel in rels:
        path = os.path.join(SITE_DIR, rel)
        if not os.path.exists(path):
            lines.append("  [SKIP] %s: ローカルに無い（site_download を先に）" % rel)
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            findings = audit_html(rel, fh.read(), specs)
        nice = _nice(rel)
        state.setdefault("pages", {})[rel] = {
            "last": today,
            "result": "ERROR" if any(s == "ERROR" for s, _, _ in findings) else "ok",
            "codes": sorted({c for _, c, _ in findings}),
        }
        runs.append({"page": rel, "date": today, "codes": sorted({c for _, c, _ in findings})})
        if findings:
            lines.append("- %s" % nice)
            for sev, code, msg in findings:
                lines.append("  [%s] %s %s" % (sev, code, msg))
                err += sev == "ERROR"
                warn += sev == "WARN"
        else:
            lines.append("- %s: 異常なし" % nice)
    state["last_run"] = runs
    state["updated"] = today
    _save(STATE_PATH, state)
    head = "ページ監査 %d件 / ERROR %d / WARN %d" % (len(rels), err, warn)
    tail = "" if err else "\n（ERROR 0。WARN は日報に1行だけ書けばよい）"
    return head + "\n" + "\n".join(lines) + tail


@tool
def set_page_priority(entries: str) -> str:
    """監査の優先度を更新する（GA4のPV・GSCのクリックを反映する）。

    Args:
        entries: 1行1ページで "パス  PV  clicks" もしくは "パス,PV,clicks"。
            例: "/en/china-ai/ 120 8\\n/deepseek-v4-1-flash/ 40 3"

    Returns:
        更新後の上位ページ一覧。
    """
    pages = []
    for raw in entries.strip().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = [x for x in re.split(r"[,\s\t]+", raw) if x]
        if not parts:
            continue
        rel = parts[0].lstrip("/")
        rel = rel if rel.endswith(".html") else rel.rstrip("/") + "/index.html"
        pv = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        clicks = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        pages.append({"page": rel, "pv": pv, "clicks": clicks,
                      "score": pv + 5 * clicks})
    if not pages:
        return "更新なし（entries が空）"
    pages.sort(key=lambda p: -p["score"])
    _save(PRIORITY_PATH, {
        "schema_note": DEFAULT_PRIORITY["schema_note"],
        "updated": date.today().isoformat(),
        "source": "set_page_priority（AkiraがGA4/GSCの実測から更新）",
        "pages": pages,
    })
    return "優先度を更新: " + ", ".join(
        "%s(score %d)" % (_nice(p["page"]), p["score"])
        for p in pages[:8])


TOOLS = [audit_pages, set_page_priority]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rels = sys.argv[1:] or [p["page"] for p in pick_targets()]
    specs = _load(SPECS_PATH, {})
    total = 0
    for rel in rels:
        p = os.path.join(SITE_DIR, rel)
        if not os.path.exists(p):
            print("%-40s SKIP (not found)" % rel)
            continue
        f = audit_html(rel, open(p, encoding="utf-8").read(), specs)
        total += len(f)
        print("%-40s %s" % (rel, "ok" if not f else ""))
        for sev, code, msg in f:
            print("   [%s] %s %s" % (sev, code, msg))
    print("findings: %d" % total)

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
    R12 同じ日の年表カードが同じ出来事を二重に書いている（2026-11-21 追加）
    R13 年表カードの日付が台帳の released と違う（ページ公開日をリリース日に
        していないか。2026-11-21 追加）
    R14 リリース日の出典が未確認のまま年表に出している（2026-11-21 追加）

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

# R3で「金額の列」とみなすヘッダ（行ラベルの取り違えを見る対象を絞る）
VALUE_HEADERS = ("入力", "出力", "価格", "単価", "料金", "価格", "price", "input",
                 "output", "cost", "cache", "キャッシュ", "円", "usd", "jpy")


def _currency(cell: str):
    """金額セルなら通貨記号を返す（それ以外は None）。USD表とJPY表の取り違えを防ぐ。"""
    m = re.match(r"^\s*([$¥€£￥])?\s*[\d][\d.,]*\s*(?:/|per|円|%|〜|~)?", cell)
    if not m:
        return None
    return m.group(1) or "num"


DATE_HEADERS = ("日付", "date", "日時", "年月日", "発表日", "リリース日",
                "released", "when", "時期")

# R9で「その時点の説明」の印として読む語尾（版・時点・更新…）
PERIOD_TAIL = ("版", "時点", "更新", "現在", "最新", "edition", "update", "roundup")

# R11で「新しく載せた」とみなす日数（これを超えたモデルは既存の記述として扱う）
RECENT_DAYS = 21


def is_date_header(text: str) -> bool:
    """表の1列目が「日付」か（＝行ラベルではなく時点。年表では重複が正常）。"""
    t = (text or "").strip().lower()
    return any(t == h or t.startswith(h) for h in DATE_HEADERS)


def _metric_key(text):
    """指標名と括弧内の条件をキーにする。戻り値は (key, 値が始まる位置) or None。

    2026-11-19 修正: 「Terminal-Bench 2.0: 58.7」の **2.0 を値として読んでいた**ため、
    同じ指標に複数値があると誤検知していた（/claude-opus-5-5/ など）。
    指標名の直後に版番号（数字.数字）が続くときは、それを条件の一部として読み飛ばす。
    """
    t = text.strip()
    low = t.lower()
    for name in METRICS:
        if not low.startswith(name.lower()):
            continue
        # 「Terminal-Bench-Science」のような**別名の指標**を拾わない（2026-11-19）
        nxt = t[len(name):len(name) + 1]
        if nxt and (nxt.isalnum() or nxt in "-_"):
            continue
        if low.startswith(name.lower()):
            pos = len(name)
            rest = t[pos:]
            ver = re.match(r"\s*(v?\d+(?:\.\d+)+)\b", rest)
            if ver:
                pos += ver.end()
                rest = t[pos:]
            m = re.match(r"\s*[（(]([^）)]*)[）)]", rest)
            qual = m.group(1).strip().lower() if m else "-"
            if ver:
                qual = (ver.group(1) + " " + qual).strip()
            return ("%s|%s" % (name, qual), pos + (m.end() if m else 0))
    return None


def _page_meta(html):
    m = re.search(r'"dateModified"\s*:\s*"(20\d{2}-\d{2}-\d{2})"', html)
    modified = _d(m.group(1)) if m else None
    # 2026-11-19 修正: `class="updated-bar"` の直後が `>` であることを前提にしていたため、
    # `style=""` が付いたバー（/mai/ など）を**見落として R1 が素通り**していた。
    bar = re.search(r'<div class="updated-bar"[^>]*>(.*?)</div>', html, re.S)
    shown = None
    if bar:
        t = re.search(r'<time[^>]*datetime="(20\d{2}-\d{2}-\d{2})"', bar.group(1))
        shown = _d(t.group(1)) if t else None
    return modified, shown


def _title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    return _strip_tags(m.group(1)) if m else ""


YEAR_MONTH = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月")
EN_PERIOD = re.compile(r"(January|February|March|April|May|June|July|August|September|"
                       r"October|November|December)\s+(20\d{2})", re.I)


def _period_marks(text):
    """「2026年10月版」「最新モデル（2026年10月）」「October 2026 edition」を拾う。

    2026-11-19 追加。R4 は「〜年〜月版」しか見ておらず、/mai/ の見出し
    「最新モデル（2026年10月）」を取り逃していた（括弧内の年月は「その時点の説明」の印）。

    誤検知を避けるため、次のものは「期間の印」とみなさない:
      - 「2026年9月1日公開」のような**日付**（リリース日の記述）
      - 「2025年1月〜2026年11月」のような**範囲**（片方だけ古いのが正常）
      - 「（2026年9月1日公」… 日を含む括弧
    """
    out = []
    for m in YEAR_MONTH.finditer(text):
        tail = text[m.end():m.end() + 8].strip()
        before = text[max(0, m.start() - 12):m.start()]
        if tail[:1].isdigit() and "日" in tail[:4]:
            continue                       # 年月日 = リリース日
        if tail[:1] in ("〜", "～", "-", "–", "~", "？", "?"):
            continue                       # 範囲の始点
        tail_period = any(tail[:len(s)].lower().startswith(s) for s in PERIOD_TAIL)
        bare_bracket = (tail[:1] in ("）", ")", "】", "]"))
        if tail_period or bare_bracket:
            out.append((int(m.group(1)), int(m.group(2)), m.group(0) + tail[:3]))
    for m in EN_PERIOD.finditer(text):
        tail = text[m.end():m.end() + 12].strip()
        if any(tail[:len(s)].lower().startswith(s) for s in PERIOD_TAIL):
            out.append((int(m.group(2)), MONTHS[m.group(1).capitalize()],
                        m.group(0) + " " + tail[:9]))
    return out


# 2026-11-21 追加: 更新履歴（アップデートログ）は本文ではない。
#   「今日なにを載せたか」を書いた節にモデル名が出てくるのは正常なのに、
#   R11 がそれを「本文の段落にしか無い」と誤検知していた。
LOG_SECTION = re.compile(
    r'<section\b[^>]*aria-labelledby="([^"]+)"[^>]*>(.*?)</section>', re.S)
LOG_LABEL = re.compile(r"更新履歴|アップデートログ|update log|changelog", re.I)
# 年表のカード（R12/R13用）。id は台帳の timeline.*_id / モデルid。
TL_ARTICLE = re.compile(r'<article class="tl-item[^"]*" id="([^"]+)">(.*?)</article>', re.S)
TL_DATE = re.compile(r'class="tl-date">\s*(20\d{2}-\d{2}-\d{2})')
TL_TITLE = re.compile(r'<h2[^>]*class="tl-title"[^>]*>(.*?)</h2>', re.S)
# 同じ日の2件が「同じ出来事」かを見るための語（日本語の助詞・一般語は落とす）
TL_STOP = {"the", "and", "for", "with", "from", "release", "released", "launch",
           "launched", "available", "announced", "new", "model", "models",
           "claude", "gpt", "gemini", "openai", "google", "anthropic"}
_TL_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]{2,}")
# 「発表 / 予告」の項目はリリース日と違って当然（GA と発表で日付が違う）
ANNOUNCE_WORDS = re.compile(r"発表|予告|提供開始へ|announce|preview|teaser", re.I)


def _body_without_log(html: str) -> str:
    """更新履歴のセクションを除いた本文（R11用）。"""

    def drop(m):
        hid = m.group(1)
        label = _strip_tags(m.group(2)[:200])
        if LOG_LABEL.search(hid) or LOG_LABEL.search(label):
            return ""
        return m.group(0)

    return LOG_SECTION.sub(drop, html)


def _tl_items(html: str):
    """年表のカードを (id, 日付, タイトル) で返す。"""
    out = []
    for m in TL_ARTICLE.finditer(html):
        d = TL_DATE.search(m.group(2))
        t = TL_TITLE.search(m.group(2))
        if not d:
            continue
        out.append((m.group(1), d.group(1), _strip_tags(t.group(1)) if t else ""))
    return out


def _tl_tokens(title: str):
    return {w.lower() for w in _TL_TOKEN.findall(title) if w.lower() not in TL_STOP}


def _timeline_tables(html):
    """「年表 / タイムライン」見出しの直後にある表を返す（R10用）。"""
    out = []
    for h in re.finditer(r"<h2[^>]*>(.*?)</h2>", html, re.S):
        label = _strip_tags(h.group(1))
        if not re.search(r"年表|タイムライン|リリース履歴|沿革|timeline", label, re.I):
            continue
        end = html.find("<h2", h.end())
        seg = html[h.end():end if end > 0 else len(html)]
        for t in TABLE.finditer(seg):
            out.append(t.group(0))
    return out


_FACTS_CACHE: dict = {}


def _facts(facts=None):
    """台帳を読む（渡されていなければ WORKSPACE から1回だけ）。"""
    if isinstance(facts, dict):
        return facts
    if "v" in _FACTS_CACHE:
        return _FACTS_CACHE["v"]
    data = _load(os.path.join(WORKSPACE_DIR, "data", "facts.json"), {})
    _FACTS_CACHE["v"] = data
    return data


def lang_of(rel):
    return "en" if str(rel).startswith("en/") else "ja"


def _recent_models(facts, rel, ref, days=RECENT_DAYS):
    """直近に追加されたモデル名（そのページの言語）を返す（R10/R11用）。"""
    data = _facts(facts)
    models = data.get("models") or {}
    if not models or not ref:
        return []
    lang = "en" if rel.startswith("en/") else "ja"
    names = []
    for rec in models.values():
        if not isinstance(rec, dict):
            continue
        rel_date = _d(rec.get("released") or "")
        if not rel_date or (ref - rel_date).days > days:
            continue
        nm = ((rec.get("names") or {}).get(lang)
              or (rec.get("names") or {}).get("ja") or "").strip()
        if len(nm) >= 4:
            names.append(nm)
    return sorted(set(names))


def audit_html(rel, html, specs=None, facts=None):
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
    # 2026-11-19 修正: 1列目が「日付」の表（年表）は**同じ日付の行が複数あって正常**
    # （例: 2026-04-02 に MAI-Image-2 と Image-2-Efficient）。誤検知していたため、
    # ・1列目が日付系ヘッダの表は対象外
    # ・2列目が長い自由文（60字超）の表も対象外（＝値の表ではない）
    # とする。
    groups = {}
    for t in TABLE.finditer(html):
        rows = ROW.findall(t.group(0))
        if len(rows) < 2:
            continue
        head = [_strip_tags(c) for c in CELL.findall(rows[0])]
        if len(head) < 2:
            continue
        if is_date_header(head[0]):
            continue
        # 2026-11-19: 「行ラベルに違う**金額**」だけを見る。
        # 分類表（列1が「世代」「提供元」など）や、USD表とJPY表を突き合わせる誤検知を避ける。
        if not any(v in head[1].lower() for v in VALUE_HEADERS):
            continue
        for r in rows[1:]:
            cells = [_strip_tags(c) for c in CELL.findall(r)]
            if len(cells) < 2 or len(cells[1]) > 24:
                continue
            cur = _currency(cells[1])
            if cur is None:
                continue   # 金額ですらない自由文は対象外
            key = "|".join(head[:3]) + "#" + cur
            groups.setdefault(key, {}).setdefault(cells[0], set()).add(cells[1])
    for key, labels in groups.items():
        bad = [(lab, vals) for lab, vals in labels.items() if len(vals) > 1]
        if bad:
            lab, vals = sorted(bad)[0]
            out.append(("ERROR", "R3",
                        "表「%s」の行「%s」に複数の金額がある（%s）。新旧の併存か、行の取り違えを疑う"
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
                # 2026-11-19: 説明文のセルから「Opus 5」の 5 を拾っていた。
                # 値のセルは短く、**先頭が数値**のものだけを対象にする。
                mnum = NUMBER.match(cells[1].strip()) if len(cells[1]) <= 24 else None
                if hit and mnum:
                    vals.setdefault(hit[0], set()).add(mnum.group(1))
    for li in re.findall(r"<li[^>]*>(.*?)</li>", html, re.S):
        text_li = _strip_tags(li)
        hit = _metric_key(text_li)
        if hit:
            seg = text_li[hit[1]:]
            # 2026-11-19: 「Terminal-Bench 4.0 — Opus 5.5」のモデル名 5.5 を
            # 「もう1つの値」と読んでいた。**区切り（= : → / スコア）の直後**だけを値とみなす。
            if not re.match(r"\s*(?:[=:：→]|スコア|score)", seg[:20], re.I):
                continue
            mnum = NUMBER.search(seg)
            if mnum:
                vals.setdefault(hit[0], set()).add(mnum.group(1))
    for k, vs in sorted(vals.items()):
        if len(vs) > 1:
            out.append(("ERROR", "R8",
                        "指標「%s」に複数の値がある（%s）。版の違う数値が併存していないか"
                        % (k.replace("|", " "), " / ".join(sorted(vs)))))
            break

    # R9 古い「年月」の目印がタイトル・見出しに残っている（2026-11-19 追加）
    #     R4 は「2026年10月**版**」の形しか見ていなかったため、
    #     /mai/ の見出し「最新モデル（2026年10月）」を見落としていた。
    #     「版 / 時点 / 更新」だけでなく、括弧に入った年月も「その時点の説明」の印として扱う。
    if ref:
        marks = []
        for label, text_ in [("<title>", _title(html))] + [
                ("見出し", _strip_tags(h.group(1))) for h in HEADING.finditer(html)]:
            for (y, mo, s) in _period_marks(text_):
                if (y, mo) < (ref.year, ref.month):
                    marks.append("%s の「%s」" % (label, s))
        if marks:
            out.append(("ERROR", "R9",
                        "%s が最終更新(%s)より古い。読者には「その月で止まっている」と読める"
                        % (marks[0], ref)))

    # R10 ページ内の年表に載っていない新しいモデル（2026-11-19 追加）
    #     /mai/ に MAI Code 2 を書いたのに「MAI リリース年表」へ入れ忘れていた型。
    #     本文と年表が同じページ内で食い違うので、機械で見つけられる。
    models = _recent_models(facts, rel, ref)
    if models:
        tables = _timeline_tables(html)
        if tables:
            tl = " ".join(_strip_tags(t) for t in tables)
            missing = [n for n in models if n.lower() in text.lower() and n.lower() not in tl.lower()]
            if missing:
                out.append(("ERROR", "R10",
                            "年表に無い：%s。本文で触れているのに年表へ未追記（同じページ内で"
                            "「最新」と「年表」が食い違う）" % "、".join(missing[:3])))
            # R10b ページ内のモデル見出しが年表に無い（2026-11-19 追加）
            # 台帳にまだ入れていないモデル（例: MAI Code 2）でも、見出しを作ったなら
            # 年表にも入れる。見出しと年表の食い違いは読者に見える。
            heads = [_strip_tags(h.group(1)) for h in
                     re.finditer(r"<h3[^>]*>(.*?)</h3>", html, re.S)]
            not_in_tl = []
            for hd in heads:
                names = []
                for nm in re.findall(r"[A-Za-z][A-Za-z0-9.\-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.\-]*){0,3}", hd):
                    nm = nm.strip(" .-")
                    if len(nm) < 6 or nm.lower() in ("new", "the", "and"):
                        continue
                    if nm[0].isupper() and any(c.isdigit() or c in "-" for c in nm):
                        names.append(nm)
                if not names:
                    continue
                # 見出しのモデル名が**1つでも年表にあればよい**（「MAI-Image-2.6 /
                # MAI-Image-2.6-Flash」のように表記が揺れるため）。
                if not any(nm.lower() in tl.lower() for nm in names):
                    not_in_tl.append(names[0])
            if not_in_tl:
                out.append(("ERROR", "R10b",
                            "見出しの「%s」が年表に無い。見出しに書いたモデルは年表にも1行足す"
                            % not_in_tl[0]))

    # R11 本文の段落にしか出てこない新しいモデル（2026-11-19 追加）
    #     /mai/ の MAI Code 2・/china-ai/ の Qwen4-Max が「下の段落にだけ」あって
    #     見出しにも表にも無く、読者が存在に気づけなかった型。
    #     対象は**台帳が本文を持つ特集ページ**（features.<slug>）に限る。
    #     個別モデルのページや用語集が他のモデルに言及するのは正常で、そこで鳴らすと
    #     ノイズになる（実際 16 ページで誤爆した）。
    slug = rel[3:] if rel.startswith("en/") else rel
    slug = slug[:-len("/index.html")] if slug.endswith("/index.html") else slug
    is_feature = slug in ((_facts(facts).get("features") or {}))
    if models and ref and is_feature:
        prominent = " ".join(
            [_strip_tags(h.group(1)) for h in HEADING.finditer(html)]
            + [_strip_tags(t) for t in TABLE.findall(html)])
        # 2026-11-21: 更新履歴の節は本文ではないので対象から外す（誤検知の除去）
        body_text = _strip_tags(_body_without_log(html)).lower()
        hidden = [n for n in models
                  if n.lower() in body_text and n.lower() not in prominent.lower()]
        if hidden:
            out.append(("ERROR", "R11",
                        "%s が見出し・表に無い（本文の段落だけ）。新しく載せたモデルは"
                        "見出しか表・年表に置く（読者は段落を読まない）" % "、".join(hidden[:3])))

    # R12 同じ日の年表カードが同じ出来事を二重に書いている（2026-11-21 追加）
    #     11-21 のランは「Claude Fable 5.1 / Mythos 5.1 公開」があるのに
    #     「Claude Mythos 5.1 提供開始」を同じ 2026-09-01 に足した。
    #     表の検査（R3/R8）は年表のカードを見ていないため素通りしていた。
    items = _tl_items(html)
    if items:
        for i, (aid, adate, atitle) in enumerate(items):
            ta = _tl_tokens(atitle)
            if not ta:
                continue
            for bid, bdate, btitle in items[i + 1:]:
                if bdate != adate:
                    continue
                tb = _tl_tokens(btitle)
                if not tb:
                    continue
                same = len(ta & tb) / float(len(ta | tb))
                if same >= 0.5:
                    out.append(("ERROR", "R12",
                                "年表の %s に同じ出来事が2件ある（「%s」と「%s」）。"
                                "既にある項目に追記するか、片方を消す"
                                % (adate, atitle[:30], btitle[:30])))
                    break
            else:
                continue
            break

    # R13 年表カードの日付が台帳の released と違う（2026-11-21 追加）
    #     11-21 のランは台帳のスタブに `released = ページの datePublished` を入れて
    #     「GPT-5.6 Sol 公開（2026-08-29）」という**存在しないリリース**を作った。
    #     カードの id がモデルidと一致するものだけを対象にする（価格改定などの
    #     イベント項目は id が別なので対象外）。
    if items:
        data = _facts(facts)
        tmodels = data.get("models") or {}
        for aid, adate, atitle in items:
            rec = tmodels.get(aid)
            if not isinstance(rec, dict):
                continue
            rel = rec.get("released") or ""
            src = rec.get("released_source") or ""
            if src in ("page-published", "unknown"):
                out.append(("ERROR", "R14",
                            "年表の「%s」はリリース日の出典が未確認（%s）。"
                            "公式発表の日付を確認するまで年表に出さない"
                            % (atitle[:30], src)))
                continue
            if rel and rel != adate and not ANNOUNCE_WORDS.search(atitle):
                out.append(("ERROR", "R13",
                            "年表の「%s」が %s になっているが、台帳の released は %s。"
                            "ページの公開日をリリース日として使っていないか"
                            % (atitle[:30], adate, rel)))
                break

    # R5 キービジュアルの日付
    specs = specs or {}
    pages = specs.get("pages") or {}
    spec = pages.get(rel)
    if spec and ref:
        gen = _d(spec.get("generated", ""))
        if gen and gen < ref:
            out.append(("ERROR", "R5",
                        "キービジュアル(%s)が %s のまま。本文の最終更新 %s より古い"
                        % (spec.get("image"), gen, ref)))
    # R5b キービジュアルがあるのに台帳に仕様が無い（2026-11-19 追加）
    #     /timeline/ の画像は og_specs に無く、R5 の検査対象外だったため
    #     「〜2026年10月」のまま誰も気づかなかった。**仕様が無いこと自体**を ERROR にする。
    #     対象は「ページ先頭のキービジュアル（figure.key-visual）」だけ。
    #     `ja-changelog.png` のようにコードが描いている定点画像は対象外。
    if ref and not spec:
        fig = re.search(r'<figure class="key-visual"[^>]*>.*?</figure>', html, re.S)
        used = set()
        if fig:
            used = {u for u in re.findall(r"/assets/og/([^\"'\s>?]+\.png)", fig.group(0))
                    if not u.endswith("-changelog.png")}
        if used:
            # 2026-11-19: 未移行ページが多いためまず WARN。`self_check` が件数を出し、
            # 移行が済んだページは R5（ERROR）で日付ズレを止める。
            out.append(("WARN", "R5b",
                        "キービジュアル(%s)が og_specs.json に無い。仕様を台帳に持たせないと"
                        "日付も中身も検査できない（R5 が効かない）" % sorted(used)[0]))
    return out


# ---------------------------------------------------------------- 公開ゲート
# 公開を止めるルール（2026-11-19）。「同じ失敗を公開しない」ための最小集合。
# R5b（仕様が無い）は移行途中なので WARN のまま。R7（取得日が古い）も WARN。
BLOCK_CODES = ("R1", "R2", "R3", "R4", "R5", "R6", "R8", "R9", "R10", "R11",
               "R12", "R13", "R14")


def blocking_errors(rel, html, specs=None, facts=None):
    """公開を止めるべき ERROR だけを返す（新しい劣化だけを止めるのは呼び出し側の仕事）。"""
    return [(code, msg) for sev, code, msg in audit_html(rel, html, specs, facts)
            if sev == "ERROR" and code in BLOCK_CODES]


def error_codes(rel, html, specs=None, facts=None):
    return {code for sev, code, _ in audit_html(rel, html, specs, facts) if sev == "ERROR"}


# ---------------------------------------------------------------- 変更ページの持ち越し
def note_changed(pages):
    """今回のランで中身が変わったページを記録し、**次のランで必ず監査**させる。

    なぜ（2026-11-19）:
        /mai/ を 11-19 に更新したのに、その日の監査対象は /timeline/ と
        /en/deepseek-v4-pro/ で、/mai/ は検査されなかった（優先度リストの10ページに
        入っていないため永久に対象外）。**触ったページは次のランで必ず見る**。
    """
    rels = []
    for p in pages or []:
        p = str(p).lstrip("/")
        if not p.endswith(".html"):
            p = p.rstrip("/") + "/index.html"
        if p.endswith("index.html") and p not in rels:
            rels.append(p)
    if not rels:
        return []
    state = _load(STATE_PATH, {})
    pend = [p for p in (state.get("pending") or []) if p not in rels]
    state["pending"] = (rels + pend)[:40]
    state["updated"] = date.today().isoformat()
    _save(STATE_PATH, state)
    return rels


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
    # 前回のランで中身が変わったページを**先頭に**入れる（2026-11-19）。
    # 「触ったページは次のランで必ず監査する」をコードで保証する。
    pend = [p for p in (state.get("pending") or []) if p not in {x["page"] for x in picked}]
    extra = [{"page": p, "rank": 0, "age": 0, "interval": 1, "last": "", "score": 0,
              "why": "前回のランで更新したページ"}
             for p in pend[:max(0, n - 1)]]
    picked = extra + picked
    picked = picked[:max(n, len(extra))]
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
        why = p.get("why") or "前回監査から%s日（基準%d日）" % (
            p["age"] if p["age"] < 9999 else "未監査", p["interval"])
        lines.append("- `%s` … %s%s" % (_nice(p["page"]), why,
                                        "" if p.get("why") else "・優先度%d位" % p["rank"]))
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
    facts = _facts()
    lines, err, warn = [], 0, 0
    runs = []
    for rel in rels:
        path = os.path.join(SITE_DIR, rel)
        if not os.path.exists(path):
            lines.append("  [SKIP] %s: ローカルに無い（site_download を先に）" % rel)
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            findings = audit_html(rel, fh.read(), specs, facts)
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
    # last_run は**当日分を累積**する（2026-11-27 修正）。
    # 以前は呼び出しごとに上書きしていたため、1日に audit_pages を複数回
    # （ページを分けて、または直したあとの再確認で）呼ぶと、最後の呼び出しの
    # ページしか残らず、post の verify_assigned が「未実施」と**嘘**をついた。
    # 11-26 の日報は「ページ監査: 未実施 2件（/image-api-pricing/,
    # /en/deepseek-v4-pro/）」と書いたが、Akiraは両方監査して ERROR 0 を確認している。
    merged = {r.get("page"): r for r in (state.get("last_run") or [])
              if r.get("date") == today and r.get("page")}
    for r in runs:
        merged[r["page"]] = r
    state["last_run"] = list(merged.values())
    state["updated"] = today
    # 監査したページは「変更ページの持ち越し」から外す（2026-11-19）
    done = {r["page"] for r in runs}
    state["pending"] = [p for p in (state.get("pending") or []) if p not in done]
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

"""公開前チェックツール（LLM Data Hub）: 全HTMLの構造・SEO・リンクを機械検証する。

背景（2026-09-15）:
    日英同格運用とリンク追加が手作業で増え、レビュー前に壊れた箇所を自分で拾えないと
    GPT税理士に投げるコストが無駄になる。公開前に必ずこれを通す。

検査項目:
    [ERROR] JSON-LD の JSON 妥当性 / GA4 タグ / <nav> の有無と日英リンク先 /
            rel=canonical ページの hreflang 3本（ja/en/x-default） /
            見た目の言語切替リンク（禁止） / 内部リンク切れ / <title> 欠落・空 /
            meta description 欠落 / タグの開閉バランス（開始タグの二重化・閉じ忘れ）/
            属性値内の生の "（タグ壊れ。html.parser で実パースし、
            og:description 等が空・幽霊属性になっていないかを検出） /
            data/models.json の契約（計算機用の配列データか。SOT混入・必須キー欠落）
    [ERROR] <title> と og:title の月/年トークン不一致（片側のみもNG・2026-10-24）/
            OGP画像の配線（期待og:imageと不一致・assets/og の未使用/欠損・alt 汎用）
    [WARN]  title 90文字超 / description が 50文字未満 or 320文字超

属性値内の生の " チェックについて（2026-09-16 の実発生を受けて追加）:
    /en/glossary/ の og:description が content=""cache hit", ..." になっていて、
    属性が content="" で切れ、残りが幽霊属性の山 → 実パースすると og:description は空。
    OGP/social プレビューの説明文が消えていたのに旧チェックは素通りした。原因は
    「HTMLとして壊れているのに正規表現で content="(.*?)" と抜き取る方式は壊れた箇所を
    見逃す」こと。よって html.parser で実際にパースし、og:description / description /
    og:title / twitter:* の content が空なら ERROR、<meta> に未知の属性（幽霊属性）が
    出ていれば ERROR とする。

使い方:
    check_site_pages()                     # 既定（SITE_LOCAL_DIR or /tmp/site）
    check_site_pages(site_dir="/tmp/site") # ディレクトリ指定
    python3 /workspace/tools/check_site_pages.py [site_dir]   # CLI でも可

戻り値:
    "checked N html files" + "[ERROR]/[WARN] 一覧" のテキスト。
    import 時のファイル書込・ネットワーク通信は行わない。
"""
from __future__ import annotations

import json
import os
import re
import html
import sys
from html.parser import HTMLParser
from pathlib import Path

from strands import tool

FORBIDDEN = [
    'lang-switch',
    'English version',
    'Japanese version',
    '英語版はこちら',
    '日本語版はこちら',
]

# --- 属性値内の生の " 検出用（2026-09-16 追加）------------------------------------
# 方式: 「タグ全体を自前でパースし、属性として説明できない余りが出たら壊れている」。
# 壊れた <meta property="og:description" content=""cache hit", ...> はここで余りが出る。
TAG_RE = re.compile(r"<(?!!--|!\[?|\?)([a-zA-Z][a-zA-Z0-9:-]*)((?:[^<>\"']|\"[^\"]*\"|'[^']*')*)/?>")
ATTR_RE = re.compile(r"\s+([a-zA-Z_:@][-a-zA-Z0-9_:.]*)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'<>`=]+))?")
# <meta> で使ってよい属性だけ。これ以外が出たら幽霊属性＝直前の属性値が壊れている。
META_OK_ATTRS = {"charset", "name", "content", "property", "http-equiv", "itemprop"}
# content が空だと実害が出るキー（OGP/social プレビュー・検索結果の説明文）
META_TEXT_KEYS = {"og:description", "description", "og:title", "twitter:description", "twitter:title"}

# --- 計算機データの契約（2026-09-27 追加）------------------------------------
# 背景: /data/models.json は計算機（/calculator/・/en/calculator/）が fetch する
# **配列**データ。ワークスペースの料金SOT（models がオブジェクト）で上書きされた事故で
# 計算機の表が全滅したが、HTML側は無変更のためこのツールを素通りした。
# ローカルの時点で気づけるよう、公開前に契約を検査する（本番側でも tools.py の公開ゲートと
# 毎朝の契約チェックが同じ観点を見ている）。
MODELS_JSON_REL = "data/models.json"
MODELS_REQUIRED = ("name", "provider", "label", "input", "output")
MODELS_MIN_ROWS = 10  # 実データは38行。桁違いの縮小を検知する下限
_SOT_MARKERS = ("schema_note", "stale_price_patterns", "stale_policy")


def _models_json_problems(site: Path):
    """計算機用 data/models.json の契約違反（このまま公開すると計算機が壊れる）を報告する。"""
    path = site / MODELS_JSON_REL
    if not path.exists():
        return ["%s: ファイルが存在しません（計算機が動かない）" % MODELS_JSON_REL]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return ["%s: JSONとして読めません: %s" % (MODELS_JSON_REL, e)]
    out = []
    if isinstance(payload, dict) and any(k in payload for k in _SOT_MARKERS):
        out.append("%s: 料金SOT（ワークスペースの真実データ）が混入しています。"
                   "計算機用の配列データと取り違えています" % MODELS_JSON_REL)
    models = payload.get("models") if isinstance(payload, dict) else None
    if isinstance(models, dict):
        return out + ["%s: models がオブジェクトです（計算機は配列を要求）" % MODELS_JSON_REL]
    if not isinstance(models, list):
        return out + ["%s: models が配列ではありません" % MODELS_JSON_REL]
    if len(models) < MODELS_MIN_ROWS:
        out.append("%s: models の行数が少なすぎます（%d < %d）"
                   % (MODELS_JSON_REL, len(models), MODELS_MIN_ROWS))
    for i, m in enumerate(models):
        if not isinstance(m, dict):
            out.append("%s: models[%d] がオブジェクトではありません" % (MODELS_JSON_REL, i))
            continue
        miss = [f for f in MODELS_REQUIRED if f not in m]
        if miss:
            out.append("%s: models[%d] に必須キーがありません: %s"
                       % (MODELS_JSON_REL, i, ",".join(miss)))
        for f in ("input", "output"):
            v = m.get(f)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                out.append("%s: models[%d].%s が正の数値ではありません" % (MODELS_JSON_REL, i, f))
    return out


class _MetaCollector(HTMLParser):
    """<meta> だけを実パースして属性を集める（convert_charrefs=True で実体参照も解決）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = []

    def handle_starttag(self, tag, attrs):
        if tag == 'meta':
            self.meta.append(attrs)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def _tag_attr_problems(s):
    """タグを自前でパースし、属性として解釈できない余りがあるタグを報告する。"""
    out = []
    for m in TAG_RE.finditer(s):
        body = m.group(2) or ''
        if body.endswith('/'):
            body = body[:-1]
        pos = 0
        while pos < len(body):
            a = ATTR_RE.match(body, pos)
            if not a:
                out.append('malformed tag at line %d: <%s%s>'
                           % (s[:m.start()].count('\n') + 1, m.group(1), body[:80]))
                break
            pos = a.end()
    return out


def _meta_problems(s):
    """<meta> を実パースして、空 content / 幽霊属性 / content 欠落を報告する。"""
    p = _MetaCollector()
    p.feed(s)
    out = []
    for attrs in p.meta:
        d = dict(attrs)
        for k, v in attrs:
            if k not in META_OK_ATTRS:
                out.append('<meta> has ghost attribute %r '
                           '(a raw quote in a previous attribute value?)' % k)
            elif v is None:
                out.append('<meta> has valueless attribute %r' % k)
        kind = d.get('property') or d.get('name') or ''
        if kind in META_TEXT_KEYS and not (d.get('content') or '').strip():
            out.append('<meta %s> content parses as empty '
                       '(OGP/social description would be blank)' % kind)
        if kind and 'content' not in d:
            out.append('<meta %s> has no content attribute' % kind)
    return out


# --- タグの開閉バランス（2026-09-19 追加）------------------------------------
# 背景: /en/index.html のホームカードで <p class="card-desc"> が二重に始まり、
#      </p> の対応が1つずれて <article> 側で閉じる壊れ方をしていた（公開済みだった）。
#      この種の「開始タグの二重化・閉じ忘れ」は JSON-LD も OGP も生きていることが多く、
#      既存チェック（属性内の生クォート・meta・リンク切れ）をすり抜ける。
# 方式: html.parser でタグを積み、対応が取れないものを ERROR として報告する。
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "source", "track", "wbr",
    # SVG の空要素（自己完結タグ。積まない）
    "path", "rect", "circle", "line", "polygon", "polyline", "ellipse", "use",
    "stop", "animate", "feColorMatrix", "image",
}


class _BalanceChecker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.problems = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if not self.stack:
            self.problems.append('line %d: stray </%s> (no open tag)' % (self.getpos()[0], tag))
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        names = [t for t, _p in self.stack]
        if tag in names:  # 内側の閉じ忘れ
            idx = len(names) - 1 - names[::-1].index(tag)
            for t, pos in self.stack[idx + 1:]:
                self.problems.append(
                    'line %d: <%s> opened at line %d not closed before </%s>'
                    % (self.getpos()[0], t, pos[0], tag))
            del self.stack[idx:]
        else:
            self.problems.append('line %d: stray </%s> (no matching open tag)' % (self.getpos()[0], tag))


def _balance_problems(s: str):
    c = _BalanceChecker()
    c.feed(s)
    c.close()
    out = list(c.problems)
    for tag, pos in c.stack:
        out.append('<%s> opened at line %d is never closed' % (tag, pos[0]))
    # 1つの閉じ忘れが連鎖して大量に出るため、ページあたり最大6件に絞る
    return out[:6]


def _site_dir(arg: str = "") -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("SITE_LOCAL_DIR", "")
    return Path(env) if env else Path("/tmp/site")


_MONTH_PAIRS = [("january","jan"),("february","feb"),("march","mar"),("april","apr"),
                ("may","may"),("june","jun"),("july","jul"),("august","aug"),
                ("september","sep"),("october","oct"),("november","nov"),("december","dec")]
_MONTH_ALIASES = {}
for _full, _abbr in _MONTH_PAIRS:
    _MONTH_ALIASES[_full] = _abbr
    _MONTH_ALIASES[_abbr] = _abbr
_MONTH_ALIASES["sept"] = "sep"


def _norm_title(t):
    t = html.unescape(t or "")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*[|\u2014\u2013]\s*LLM Data Hub\s*$", "", t)
    return t.strip()


def _date_tokens(t):
    """タイトル中の月/年トークン。**捨てずに残して**比較する（2026-10-24 修正）。

    旧実装は「月名を正規化してから比較」＝実質的に月名を無視していたため、
    og:title にだけ "Sep 2026" が残っていても 0 件と誤判定した。
    """
    low = html.unescape(t or "").lower()
    toks = set(re.findall(r"\b(?:19|20)\d{2}\b", low))
    for w in re.findall(r"[a-z]+", low):
        c = _MONTH_ALIASES.get(w)
        if c:
            toks.add(c)          # september / sep / sept -> sep（同一月として比較）
    return toks


def _tag_attrs(tag):
    return dict((m.group(1).lower(), m.group(2))
                for m in re.finditer(r'([\w:.-]+)\s*=\s*"([^"]*)"', tag))


def _meta_content(s, attr, key):
    """<meta> の content を属性順・クォート種別に依存せず取得（見逃し防止）。"""
    for tag in re.findall(r"<meta\b[^>]*>", s, re.I):
        a = _tag_attrs(tag)
        if a.get(attr.lower(), "").lower() == key.lower() and "content" in a:
            return a["content"]
    return None


def _ogtitle_problems(s):
    """<title> と og:title の不一致を返す（(severity, message) のリスト）。

    課題65の再発検出。月/年のトークンが**どちらか一方にしか無い場合も不一致**。
    サイト名サフィックス等の短縮差は WARN、日付ラベルのズレは ERROR。
    """
    out = []
    tm = re.search(r"<title[^>]*>(.*?)</title>", s, re.S | re.I)
    og_raw = _meta_content(s, "property", "og:title")
    if not tm or og_raw is None:
        return out
    nt, no = _norm_title(tm.group(1)), _norm_title(og_raw)
    if not no:
        return out
    a, b = _date_tokens(nt), _date_tokens(no)
    if b - a:
        out.append(("E", "og:title has a date label not in <title> (%s) | title=%r og:title=%r"
                    % (",".join(sorted(b - a)), nt[:90], no[:90])))
    if a - b:
        out.append(("E", "<title> has a date label not in og:title (%s) | title=%r og:title=%r"
                    % (",".join(sorted(a - b)), nt[:90], no[:90])))
    if nt and no and nt != no:
        out.append(("S", "%s: og:title text differs from <title> | title=%r og:title=%r"
                    % ("", nt[:80], no[:80])))
    return out


OG_BASE = "https://llm.okamomedia.tokyo/assets/og/"
GENERIC_ALT = "LLM Data Hub \u2014 LLM API pricing, token costs and model data"

# 12ページの「期待する og:image ファイル名」対応表（決定論的な配線チェック・2026-10-24 追加）
EXPECTED_OG_IMAGES = {
    "index.html": "ja-home.png",
    "en/calculator/index.html": "en-calculator.png",
    "china-ai/index.html": "ja-china-ai.png",
    "deepseek-v4-1-flash/index.html": "ja-deepseek-v4-1-flash.png",
    "glossary/zero-operator-access/index.html": "ja-zoa.png",
    "multimodal/index.html": "ja-multimodal.png",
    "gpt-6-1-terra/index.html": "ja-gpt-6-1-terra.png",
    "en/gpt-6-1-terra/index.html": "en-gpt-6-1-terra.png",
    "en/index.html": "en-home.png",
    "en/pricing/index.html": "en-pricing.png",
    "en/timeline/index.html": "en-timeline.png",
    "en/china-ai/index.html": "en-china-ai.png",
    "en/multimodal/index.html": "en-multimodal.png",
    "en/deepseek-v4-1-flash/index.html": "en-deepseek-v4-1-flash.png",
    "en/glossary/zero-data-retention/index.html": "en-zdr.png",
    "en/glossary/zero-operator-access/index.html": "en-zoa.png",
    "pricing/index.html": "ja-pricing.png",
    "timeline/index.html": "ja-timeline.png",
    "calculator/index.html": "ja-calculator.png",
    "glossary/zero-data-retention/index.html": "ja-zdr.png",
    "kimi-k3-1-pro/index.html": "ja-kimi-k3-1-pro.png",
    "en/kimi-k3-1-pro/index.html": "en-kimi-k3-1-pro.png",
    "prompt-cache-pricing/index.html": "ja-prompt-cache-pricing.png",
    "en/prompt-cache-pricing/index.html": "en-prompt-cache-pricing.png",
}


def _read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _image_px(path):
    """実ファイルの画素サイズを (w, h) の文字列で返す。取得できなければ None。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return str(im.size[0]), str(im.size[1])
    except Exception:
        return None


def _og_image_problems(site):
    """OGP画像の配線チェック（期待値一致 / 未使用アセット / 欠損アセット / ミラー非対称）。"""
    errors, warns = [], []
    ogdir = site / "assets" / "og"
    present = set(p.name for p in ogdir.glob("*.png")) if ogdir.is_dir() else set()
    referenced = set()

    for rel, fname in sorted(EXPECTED_OG_IMAGES.items()):
        want = OG_BASE + fname
        p = site / rel
        referenced.add(fname)
        if fname not in present:
            errors.append("og-wiring: %s: expected image assets/og/%s does not exist" % (rel, fname))
        if not p.exists():
            errors.append("og-wiring: %s: expected page not found locally" % rel)
            continue
        s = _read(p)
        og = _meta_content(s, "property", "og:image")
        tw = _meta_content(s, "name", "twitter:image")
        if og != want:
            errors.append("og-wiring: %s: og:image=%r expected %r" % (rel, og, want))
        if tw != want:
            errors.append("og-wiring: %s: twitter:image=%r expected %r" % (rel, tw, want))
        w = _meta_content(s, "property", "og:image:width")
        h = _meta_content(s, "property", "og:image:height")
        exp_w, exp_h = _image_px(ogdir / fname) or ("1200", "630")
        if (w, h) != (exp_w, exp_h):
            errors.append("og-wiring: %s: og:image size %sx%s (actual file is %sx%s)"
                          % (rel, w, h, exp_w, exp_h))
        alt = (_meta_content(s, "property", "og:image:alt") or "").strip()
        talt = (_meta_content(s, "name", "twitter:image:alt") or "").strip()
        if not alt:
            errors.append("og-wiring: %s: og:image:alt empty" % rel)
        elif alt == GENERIC_ALT:
            errors.append("og-wiring: %s: og:image:alt is the generic site-wide alt" % rel)
        if not talt:
            errors.append("og-wiring: %s: twitter:image:alt empty" % rel)

    for fname in sorted(present - referenced):
        warns.append("og-wiring: assets/og/%s exists but is not referenced by any table page" % fname)

    # バイリンガル・ミラー非対称: 片側だけ専用画像 / もう片側は汎用
    seen = set()
    for rel in sorted(EXPECTED_OG_IMAGES):
        mir = rel[3:] if rel.startswith("en/") else "en/" + rel
        key = tuple(sorted((rel, mir)))
        if key in seen or not (site / mir).exists():
            continue
        seen.add(key)
        a_og = _meta_content(_read(site / rel), "property", "og:image") or ""
        b_og = _meta_content(_read(site / mir), "property", "og:image") or ""
        if a_og.startswith(OG_BASE) and not b_og.startswith(OG_BASE):
            warns.append("og-wiring: mirror %s still uses the generic og:image while %s has a "
                         "dedicated one (assets/og/%s)" % (mir, rel, EXPECTED_OG_IMAGES[rel]))
    return errors, warns


def _resolves(site: Path, href: str, src_rel: str) -> bool:
    if href.startswith(('http', 'mailto:', 'tel:', '#', '//')):
        return True
    path = href.split('#')[0].split('?')[0]
    if not path:
        return True
    if path.startswith('/'):
        cand = path.lstrip('/')
    else:
        base = os.path.dirname(src_rel)
        cand = os.path.normpath(os.path.join(base, path)) if base else path
    if cand.endswith('/') or cand == '':
        cand += 'index.html'
    cand = cand.replace('\\', '/')
    if (site / cand).exists() or (site / cand).is_dir() or (site / (cand + '/index.html')).exists():
        return True
    return False


def _check(site_dir: str = "") -> str:
    site = _site_dir(site_dir)
    if not site.is_dir():
        return "ERROR: site dir not found: %s" % site

    _title_diff = []
    html_files = sorted(
        os.path.relpath(os.path.join(root, f), site)
        for root, _dirs, files in os.walk(site)
        for f in files
        if f.endswith('.html')
    )
    errors, warns = [], []

    for rel in html_files:
        if rel == '404.html':
            continue
        s = (site / rel).read_text(encoding='utf-8')

        # --- JSON-LD ---
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
            try:
                json.loads(m.group(1))
            except Exception as e:  # noqa: BLE001
                errors.append('%s: invalid JSON-LD: %s' % (rel, e))

        # --- GA4 ---
        if 'G-MTH8T0ECG2' not in s or 'googletagmanager.com/gtag/js' not in s:
            errors.append('%s: GA4 tag missing' % rel)

        # --- nav（日英でリンク先が違う） ---
        nav = re.search(r'<nav[^>]*>(.*?)</nav>', s, re.S)
        if not nav:
            errors.append('%s: no <nav>' % rel)
        else:
            want = '/en/glossary/' if rel.startswith('en/') else '/glossary/'
            if want not in nav.group(1):
                errors.append('%s: nav missing %s' % (rel, want))

        # --- hreflang（canonical があるページは ja/en/x-default の3本） ---
        if 'rel="canonical"' in s and s.count('hreflang=') != 3:
            errors.append('%s: hreflang count=%d (expected 3)' % (rel, s.count('hreflang=')))

        # --- 禁止: 見た目の言語切替 ---
        for ng in FORBIDDEN:
            if ng in s:
                errors.append('%s: forbidden language-switch marker %r' % (rel, ng))

        # --- 二重エスケープ / 文字化け（2026-09-15の実発生を受けて追加） ---
        if '%%' in s:
            for ln, line in enumerate(s.splitlines(), 1):
                if '%%' in line:
                    errors.append('%s: literal "%%%%" at line %d (double-encoded, renders broken)' % (rel, ln))
        for bad in ('ã‚', 'ãƒ', 'ã€', 'ã®', 'æ—', 'æ–', 'æœ', 'å¤', 'è©', 'ç´', 'ï¼', 'â€', 'ðŸ', 'Ã¢'):
            if bad in s:
                errors.append('%s: mojibake sequence %r found (UTF-8 read as Latin-1?)' % (rel, bad))

        # --- タグの開閉バランス（2026-09-19 追加）---
        for pb in _balance_problems(s):
            errors.append('%s: %s' % (rel, pb))

        # --- 内部リンク ---
        for m in re.finditer(r'href="([^"]+)"', s):
            if not _resolves(site, m.group(1), rel):
                errors.append('%s: broken internal link -> %s' % (rel, m.group(1)))

        # --- title / description ---
        t = re.search(r'<title>(.*?)</title>', s, re.S)
        if not t:
            errors.append('%s: no <title>' % rel)
        elif not t.group(1).strip():
            errors.append('%s: empty <title>' % rel)
        elif len(t.group(1)) > 90:
            warns.append('%s: title long (%d chars)' % (rel, len(t.group(1))))

        # --- 属性値内の生の "（HTMLとして壊れている / OGP が消える。2026-09-16 追加）---
        # (a) content="" の直後に別トークンが続く典型パターン
        for m in re.finditer(r'(content|name|property|alt|title|value|href|src)=""(?=[^\s>/])', s):
            ln = s[:m.start()].count('\n') + 1
            tail = s[m.start():m.start() + 60].replace('\n', ' ')
            errors.append('%s: line %d: raw quote inside attribute value - %s...' % (rel, ln, tail))
        # (b) タグ全体をパースして余りが出る＝属性値の中で閉じ引用符が早すぎる
        for p in _tag_attr_problems(s):
            errors.append('%s: %s' % (rel, p))
        # (c) <meta> を実パースして空 content / 幽霊属性を検出
        for p in _meta_problems(s):
            errors.append('%s: %s' % (rel, p))

        for sev, p in _ogtitle_problems(s):
            if sev == 'E':
                errors.append('%s: %s' % (rel, p))
            elif sev == 'S':
                _title_diff.append(rel)

        d = re.search(r'<meta name="description" content="(.*?)">', s, re.S)
        if not d:
            errors.append('%s: no meta description' % rel)
        elif not (50 <= len(d.group(1)) <= 320):
            warns.append('%s: description length %d' % (rel, len(d.group(1))))

    if _title_diff:
        warns.append('og:title text differs from <title> on %d pages (non-blocking, wording only): %s'
                     % (len(_title_diff), ', '.join(sorted(_title_diff)[:12])
                        + (' ...' if len(_title_diff) > 12 else '')))
    lines = ['checked %d html files in %s' % (len(html_files), site)]
    _og_e, _og_w = _og_image_problems(site)
    errors += _og_e
    warns += _og_w
    errors += _models_json_problems(site)
    lines.append('ERROR: %d / WARN: %d' % (len(errors), len(warns)))
    for p in sorted(set(errors)):
        lines.append('  [ERROR] %s' % p)
    for p in sorted(set(warns)):
        lines.append('  [WARN]  %s' % p)
    if not errors and not warns:
        lines.append('  no problems found')
    return '\n'.join(lines)


@tool
def check_site_pages(site_dir: str = "") -> str:
    """公開前に全HTMLを機械検証する（JSON-LD / GA4 / hreflang / nav / リンク切れ / meta）。

    Args:
        site_dir: 検査するローカルサイトのディレクトリ。省略時は SITE_LOCAL_DIR、
            無ければ /tmp/site。

    Returns:
        検査結果のテキストレポート（[ERROR] が1件でもあれば公開前に修正する）。
    """
    return _check(site_dir)


TOOL = check_site_pages


if __name__ == "__main__":  # CLI: python3 check_site_pages.py [site_dir]
    sys.stdout.reconfigure(encoding='utf-8')
    print(_check(sys.argv[1] if len(sys.argv) > 1 else ""))

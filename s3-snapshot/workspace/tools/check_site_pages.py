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

        d = re.search(r'<meta name="description" content="(.*?)">', s, re.S)
        if not d:
            errors.append('%s: no meta description' % rel)
        elif not (50 <= len(d.group(1)) <= 320):
            warns.append('%s: description length %d' % (rel, len(d.group(1))))

    lines = ['checked %d html files in %s' % (len(html_files), site)]
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

import re, pathlib

# ---------- 1) tool patch ----------
tp = pathlib.Path("/workspace/tools/check_site_pages.py")
src = tp.read_text(encoding="utf-8")

start = src.index("_MONTHS = set(")
end = src.index("\n\ndef _resolves(")
new_block = '''_MONTH_PAIRS = [("january","jan"),("february","feb"),("march","mar"),("april","apr"),
                ("may","may"),("june","jun"),("july","jul"),("august","aug"),
                ("september","sep"),("october","oct"),("november","nov"),("december","dec")]
_MONTH_ALIASES = {}
for _full, _abbr in _MONTH_PAIRS:
    _MONTH_ALIASES[_full] = _abbr
    _MONTH_ALIASES[_abbr] = _abbr
_MONTH_ALIASES["sept"] = "sep"


def _norm_title(t):
    t = html.unescape(t or "")
    t = re.sub(r"\\s+", " ", t).strip()
    t = re.sub(r"\\s*[|\\u2014\\u2013]\\s*LLM Data Hub\\s*$", "", t)
    return t.strip()


def _date_tokens(t):
    """タイトル中の月/年トークン。**捨てずに残して**比較する（2026-10-24 修正）。

    旧実装は「月名を正規化してから比較」＝実質的に月名を無視していたため、
    og:title にだけ "Sep 2026" が残っていても 0 件と誤判定した。
    """
    low = html.unescape(t or "").lower()
    toks = set(re.findall(r"\\b(?:19|20)\\d{2}\\b", low))
    for w in re.findall(r"[a-z]+", low):
        c = _MONTH_ALIASES.get(w)
        if c:
            toks.add(c)          # september / sep / sept -> sep（同一月として比較）
    return toks


def _tag_attrs(tag):
    return dict((m.group(1).lower(), m.group(2))
                for m in re.finditer(r'([\\w:.-]+)\\s*=\\s*"([^"]*)"', tag))


def _meta_content(s, attr, key):
    """<meta> の content を属性順・クォート種別に依存せず取得（見逃し防止）。"""
    for tag in re.findall(r"<meta\\b[^>]*>", s, re.I):
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
        out.append(("W", "og:title text differs from <title> | title=%r og:title=%r"
                    % (nt[:90], no[:90])))
    return out


OG_BASE = "https://llm.okamomedia.tokyo/assets/og/"
GENERIC_ALT = "LLM Data Hub \\u2014 LLM API pricing, token costs and model data"

# 12ページの「期待する og:image ファイル名」対応表（決定論的な配線チェック・2026-10-24 追加）
EXPECTED_OG_IMAGES = {
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
}


def _read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


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
        if (w, h) != ("1200", "630"):
            errors.append("og-wiring: %s: og:image size %sx%s (expected 1200x630)" % (rel, w, h))
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
'''
src = src[:start] + new_block + src[end:]

# caller: severity-aware
old_caller = """        for p in _ogtitle_problems(s):
            warns.append('%s: %s' % (rel, p))"""
new_caller = """        for sev, p in _ogtitle_problems(s):
            (errors if sev == 'E' else warns).append('%s: %s' % (rel, p))"""
assert old_caller in src
src = src.replace(old_caller, new_caller)

old_hook = "    errors += _models_json_problems(site)"
new_hook = """    _og_e, _og_w = _og_image_problems(site)
    errors += _og_e
    warns += _og_w
    errors += _models_json_problems(site)"""
assert old_hook in src
src = src.replace(old_hook, new_hook, 1)

# header docstring note
src = src.replace("    [WARN]  title 90\u6587\u5b57\u8d85",
                  "    [ERROR] <title> と og:title の月/年トークン不一致（片側のみもNG・2026-10-24）/\n"
                  "            OGP画像の配線（期待og:imageと不一致・assets/og の未使用/欠損・alt 汎用）\n"
                  "    [WARN]  title 90\u6587\u5b57\u8d85", 1)

tp.write_text(src, encoding="utf-8")
print("tool patched")

# ---------- 2) en/china-ai og:title を <title> と一致させる ----------
hp = pathlib.Path("/tmp/site/en/china-ai/index.html")
h = hp.read_text(encoding="utf-8")
t = re.search(r"<title>(.*?)</title>", h, re.S).group(1)
old = re.search(r'<meta property="og:title" content="[^"]*">', h).group(0)
new = '<meta property="og:title" content="%s">' % t
h2 = h.replace(old, new, 1)
hp.write_text(h2, encoding="utf-8")
print("page og:title:", old, "->", new)

# -*- coding: utf-8 -*-
"""装飾マークアップの「文字列としての漏れ」と CSS 値の破壊を機械検出する。2026-11-21。

なぜ:
    `/pricing/` の `border-radius:50%` が `border-radius:[bold yellow]50%[/bold yellow]`
    になり、本文にも `「Permanent [bold yellow]50%[/bold yellow] off」` が読者に見える形で
    残った、という報告があった。原因は「50%」という短い文字列を狙った **ファイル全体への
    一括置換**で、本文と CSS の両方を同時に壊す。grep で 1 パターンを見るだけでは
    「表記ゆれ（italic/red/color 等）」「CSS 側の破壊」を取りこぼす。

何を見るか:
    1. BBCode 風の装飾タグ（[bold]…[/bold], [italic], [red], [color=…] など）の残存
    2. CSS 宣言の値に `[` / `]` が混入している箇所（一括置換が CSS を壊した跡）
       ※ セレクタの属性セレクタ（input[type=text]）は宣言値ではないので対象外
    3. 対象拡張子は html / css / js / json（描画物・配信物のみ。cache/ の一次情報は除く）

使い方:
    python3 check_markup_leak.py <SITE_DIR>
    # 出力は self_check の他ゲートと同じ契約: "  [ERROR] ..." と "ERROR: N"

注意:
    「[vs Fable 5.1]」のような正当な角括弧（タイトル内）を誤検出しないよう、
    タグ名は装飾目的の既知キーワードに限定する。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from strands import tool

DEFAULT_SITE_DIRS = [os.environ.get("SITE_LOCAL_DIR", ""), "/tmp/site"]

EXTS = (".html", ".htm", ".css", ".js", ".json")

# 1) 装飾タグ（既知キーワードのみ。汎用の [a-z] は正当な角括弧を拾うので使わない）
DECOR_KEYS = (
    "bold", "b", "i", "u", "italic", "underline", "strike", "s",
    "color", "colour", "red", "yellow", "green", "blue", "orange",
    "purple", "gray", "grey", "code", "quote", "url", "size", "font",
    "center", "left", "right", "bg", "highlight", "hl", "mark", "em",
    "strong", "dim", "muted", "accent", "warn", "warning", "note",
)
DECOR_RE = re.compile(
    r"\[/?(?:%s)(?:\s*=[^\]]*|\s+[a-z]+)?\]" % "|".join(DECOR_KEYS),
    re.IGNORECASE,
)

# 2) CSS 宣言の値に角括弧が混入（一括置換による破壊）
DECL_RE = re.compile(r"([-a-zA-Z]+)\s*:\s*([^;{}\n]+)")
SELECTOR_SAFE_RE = re.compile(r"^\s*(?:--)?[-a-zA-Z]+\s*:")


STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)


def _css_regions(text: str, suffix: str):
    """CSS として解釈してよい領域だけを返す（HTML の属性を CSS 宣言と誤認しないため）。

    .css は全文、.html は <style> ブロックのみ。
    """
    if suffix == ".css":
        return [text]
    return STYLE_BLOCK_RE.findall(text)


def _scan_css_text(text: str):
    """CSS 断片から「値に [ または ] を含む宣言」を返す。"""
    out = []
    for m in DECL_RE.finditer(text):
        prop, value = m.group(1), m.group(2)
        if "[" not in value and "]" not in value:
            continue
        v = value.strip()
        # HTML 属性や content:"[" のような正当例は値に引用符/山括弧が入るので除外
        if any(ch in v for ch in ('"', "'", "<", ">")):
            continue
        if len(v) > 120:
            continue
        out.append((prop, v[:100]))
    return out


def _iter_files(site_dir: str):
    root = Path(site_dir)
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        rel = p.relative_to(root).as_posix()
        # 一次情報キャッシュや作業用ディレクトリは配信物ではないので除外
        if rel.startswith(("cache/", "notes/", "drafts/", "trace/")):
            continue
        yield p, rel


def report(site_dir: str) -> str:
    lines = []
    errors = 0
    decor_hits = 0
    css_hits = 0
    by_ext = {}
    sampled = []
    files = 0

    for path, rel in _iter_files(site_dir):
        files += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:  # pragma: no cover
            lines.append("  [ERROR] 読み取り失敗 %s: %s" % (rel, e))
            errors += 1
            continue

        for m in DECOR_RE.finditer(text):
            decor_hits += 1
            ext = path.suffix.lower()
            by_ext[ext] = by_ext.get(ext, 0) + 1
            if len(sampled) < 15:
                line_no = text.count("\n", 0, m.start()) + 1
                sampled.append("%s:%d  %s" % (rel, line_no, m.group(0)))

        css_hits_in_file = []
        for region in _css_regions(text, path.suffix.lower()):
            css_hits_in_file.extend(_scan_css_text(region))

        for prop, value in css_hits_in_file:
            css_hits += 1
            if len(sampled) < 15:
                line_no = text.count("\n", 0, text.find("%s:%s" % (prop, value))) + 1
                sampled.append("%s:%d  CSS値の破壊 %s:%s" % (rel, max(line_no, 1), prop, value))

    for s in sampled:
        lines.append("  [ERROR] " + s)

    errors = decor_hits + css_hits

    lines.insert(0, "markup_leak: checked %d files (%s)" % (files, site_dir))
    lines.append("  装飾タグ残存: %d 件 / CSS値破壊: %d 件" % (decor_hits, css_hits))
    if by_ext:
        lines.append("  拡張子別: " + ", ".join(
            "%s=%d" % (k, v) for k, v in sorted(by_ext.items())))
    lines.append("ERROR: %d" % errors)
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    site_dir = argv[0] if argv else ""
    if not site_dir:
        for cand in DEFAULT_SITE_DIRS:
            if cand and os.path.isdir(cand):
                site_dir = cand
                break
    if not site_dir or not os.path.isdir(site_dir):
        print("site dir not found")
        return 2
    out = report(site_dir)
    print(out)
    return 0 if out.rstrip().endswith("ERROR: 0") else 1


@tool
def check_markup_leak(site_dir: str = "") -> str:
    """装飾マークアップ（[bold]…[/bold] 等）の文字列漏れと CSS 値の破壊を検査する。

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


TOOL = check_markup_leak

if __name__ == "__main__":
    sys.exit(main())

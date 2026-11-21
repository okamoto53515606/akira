"""公式ソースの「新モデル」をコードで見張る（2026-11-21 追加）。

なぜ:
    2026-11-21 のランは GPT-6.2 Astra / Sol の公開に**気づかなかった**。
    原因は `_propose_themes()` の「新モデルの漏れ」判定が**台帳（facts.json）を
    自分で走査していた**こと。台帳に無いモデルは候補になりえないので、
    台帳が古いと「漏れ 0件」という**偽の緑**を出す。

    だから見張る先を台帳ではなく**各社の公式料金ページ**にする。
    ここで「公式ページに載っているのに台帳に無いID」を出し、ミッションの先頭に
    差し込む。LLMは「調べるかどうか」を判断するのではなく、
    **既に見つかっている候補を確認する**だけでよくなる。

取りこぼしの扱い（重要）:
    取得に失敗したソースは「新モデル無し」ではない。`ok_sources` と
    `failed_sources` を分けて返し、失敗があればミッションにも「**不明**」と書く。
    （2026-11-15 の鮮度キューが2ラン連続0件だった型＝静かな偽OKを繰り返さない）

保存先: <WORKSPACE>/data/release_watch.json（日をまたいで持ち越す）
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

from strands import tool

JST = timezone(timedelta(hours=9))
WORKSPACE = os.environ.get("WORKSPACE_LOCAL_DIR", "/workspace")
WATCH_PATH = os.path.join(WORKSPACE, "data", "release_watch.json")
TIMEOUT = 30
MAX_PENDING = 12

# 各社の公式料金ページ（モデルIDが必ず載る場所）。UAを付けないと弾くサイトがある。
# (名前, [URL候補…], 抽出パターン)。2026-11-21: 1本だけだと、その日の 403/5xx で
# **丸ごと「不明」**になる（実機で deepseek が HTTPError になった）。候補を複数持ち、
# 失敗したら次を試す。料金ページが落ちていてもチェンジログでIDは拾える。
SOURCES = (
    ("openai",
     ["https://developers.openai.com/ja-JP/api/docs/pricing",
      "https://developers.openai.com/api/docs/pricing"],
     r"(?<![a-z0-9/._-])gpt-[0-9][a-z0-9.\-]*"),
    ("anthropic",
     ["https://platform.claude.com/docs/en/about-claude/pricing",
      "https://docs.anthropic.com/en/docs/about-claude/pricing"],
     r"(?<![a-z0-9/._-])claude-(?:opus|sonnet|haiku|fable|mythos)-[0-9][a-z0-9.\-]*"),
    ("google",
     ["https://ai.google.dev/gemini-api/docs/pricing",
      "https://ai.google.dev/gemini-api/docs/changelog"],
     r"(?<![a-z0-9/._-])gemini-[0-9][a-z0-9.\-]*"),
    ("deepseek",
     ["https://api-docs.deepseek.com/quick_start/pricing/",
      "https://api-docs.deepseek.com/quick_start/pricing",
      "https://api-docs.deepseek.com/updates/"],
     r"(?<![a-z0-9/._-])deepseek-[a-z0-9][a-z0-9.\-]*"),
)

# 料金ページの付随語（モデルIDではない）。ノイズを落とす。
NOISE_TAIL = ("-models", "-pricing", "-docs", "-api", "-plan", "-tiers")


def _norm(mid: str) -> str:
    """`gpt-6.2-astra` と台帳の `gpt-6-2-astra` を同じキーにする。"""
    return re.sub(r"[^a-z0-9]+", "-", mid.lower()).strip("-")


# 系統（同じ系列）と版番号を取り出す。
#   gpt-6.2-astra        -> ("gpt", (6, 2))
#   claude-opus-5-5      -> ("claude-opus", (5, 5))
#   gemini-3.1-flash-lite-> ("gemini", (3, 1))
#   deepseek-v4.1-flash  -> ("deepseek", (4, 1))
_FAMILY = (
    (re.compile(r"(?<![a-z0-9/._-])gpt-(\d+)(?:[.-](\d+))?(?:[.-]|$)"), "gpt"),
    (re.compile(r"(?<![a-z0-9/._-])gemini-(\d+)(?:[.-](\d+))?(?:[.-]|$)"), "gemini"),
    (re.compile(r"(?<![a-z0-9/._-])claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:[.-](\d+))?(?:[.-]|$)"),
     "claude-%s"),
    (re.compile(r"(?<![a-z0-9/._-])deepseek-v(\d+)(?:[.-](\d+))?(?:[.-]|$)"), "deepseek"),
)


def _family_version(mid: str):
    """(系統, 版タプル) を返す。系列が分からないIDは None（判定しない）。"""
    low = mid.lower()
    for pat, fam in _FAMILY:
        m = pat.match(low)
        if not m:
            continue
        if "%s" in fam:          # claude-<line>-<major>[-<minor>]
            ver = tuple(int(g) for g in (m.group(2), m.group(3)) if g)
            return fam % m.group(1), ver
        ver = tuple(int(g) for g in m.groups() if g)
        return fam, ver
    return None


def _max_versions(known_ids) -> dict:
    out: dict = {}
    for mid in known_ids:
        fv = _family_version(mid)
        if not fv:
            continue
        fam, ver = fv
        if ver > out.get(fam, ()):
            out[fam] = ver
    return out


def _looks_like_model(mid: str) -> bool:
    low = mid.lower()
    if not re.search(r"\d", low):          # 版番号が無いものはモデルではない
        return False
    # `gemini-31-pro-preview-customtools` のような**URLスラッグ**を落とす
    # （実際の版は `6.2` / `3.1` のように区切りが入る。`31` のような2桁ベタ書きは無い）
    if re.match(r"^(?:gpt|gemini)-\d{2,}(?:-|$)", low):
        return False
    if any(low.endswith(t) for t in NOISE_TAIL):
        return False
    if "preview-" in low and re.search(r"-\d{4}$", low):
        return False                        # `...-preview-12-2025` = 日付サフィックス
    return 4 <= len(low) <= 48


def _fetch(url: str, retries: int = 1) -> str:
    """1URLを取得する。一時的な失敗（5xx・切断）は1回だけやり直す。"""
    last = None
    for _ in range(retries + 1):
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (akira-release-watch)"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code < 500:
                raise
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def _fetch_any(urls: list[str]) -> tuple[str, str]:
    """候補URLを順に試し、(URL, 本文) を返す。全部だめなら最後の例外を投げる。"""
    last = None
    for u in urls:
        try:
            return u, _fetch(u)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last else RuntimeError("no url")


def _load_state() -> dict:
    try:
        with open(WATCH_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def _save_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(WATCH_PATH), exist_ok=True)
        with open(WATCH_PATH, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    except Exception:  # noqa: BLE001
        pass


def scan(ledger_models: dict, today: str | None = None) -> dict:
    """公式ページを取得し、台帳に無いモデルIDを返す（コードから呼べる関数）。

    Args:
        ledger_models: facts.json の `models`（{id: record}）
        today: YYYY-MM-DD（省略時は JST の今日）
    """
    today = today or datetime.now(JST).date().isoformat()
    known = {_norm(k) for k in (ledger_models or {})}
    for rec in (ledger_models or {}).values():
        for nm in ((rec or {}).get("names") or {}).values():
            if nm:
                known.add(_norm(str(nm)))
    state = _load_state()
    seen_all: set[str] = set()
    ok_sources, failed = [], []
    per_source: dict = {}
    used_url = {}
    for name, urls, pattern in SOURCES:
        try:
            url, html = _fetch_any(urls)
        except Exception as e:  # noqa: BLE001
            # 失敗は「クラス名＋HTTPコード」まで残す（原因が分からないと直せない）
            code = getattr(e, "code", "")
            failed.append("%s（%s%s）" % (name, type(e).__name__,
                                         " %s" % code if code else ""))
            continue
        used_url[name] = url
        ids = set()
        for raw in re.findall(pattern, html, re.I):
            low = raw.lower().rstrip(".-")
            if _looks_like_model(low):
                ids.add(_norm(low))
        ok_sources.append(name)
        per_source[name] = sorted(ids)
        seen_all |= ids

    unknown = sorted(seen_all - known)

    # 「台帳の最大版より新しい」ものを優先する（過去の旧モデルで埋もれさせない）。
    # 11-21 の最初の実装は旧モデル12件で埋まり、**GPT-6.2 が候補から漏れた**。
    # ・strong = 系統の最大版より新しい（何があっても出す）
    # ・weak   = 同じ版の別バリアント。**前回のスキャン以降に現れたものだけ**出す
    #            （初回に旧モデルが全部並ぶのを防ぐ）
    prev_seen = {_norm(x) for x in (state.get("seen") or [])}
    fresh_ids = {m for m in unknown if _norm(m) not in prev_seen}
    max_ver = _max_versions(known)
    strong, weak = [], []
    for mid in unknown:
        fv = _family_version(mid)
        if not fv:
            continue
        fam, ver = fv
        top = max_ver.get(fam)
        if top is None or ver > top:
            strong.append((ver, mid))
        elif ver == top and _norm(mid) in fresh_ids:
            weak.append((ver, mid))
    strong.sort(reverse=True)
    weak.sort(reverse=True)
    candidates = [m for _, m in strong] + [m for _, m in weak]
    # `gpt-6-2` のように**版番号だけ**のIDは、同系統の具体的な候補があれば落とす
    # （`gpt-6-2-astra` は残す。`gpt-6-2-astra-law` に食われないように接頭辞比較はしない）
    def _bare_version(mid: str) -> bool:
        return bool(re.fullmatch(r"(?:gpt|gemini|deepseek)-?\d+(?:-\d+)?", _norm(mid)))

    candidates = [m for m in candidates
                  if not (_bare_version(m) and any(o != m and _norm(o).startswith(_norm(m) + "-")
                                                  for o in candidates))]

    # pending は毎回計算し直す（日をまたいで古い候補を抱えない）。
    # ・strong（台帳の最大版より新しい）は台帳に入れるまで何度でも出る
    # ・weak（同じ版の別バリアント）は初出の1回だけ出る
    pending = []
    for mid in candidates:
        n = _norm(mid)
        if n not in known and n not in pending:
            pending.append(mid)
    pending = pending[:MAX_PENDING]

    state.update({
        "updated": today,
        "ok_sources": ok_sources,
        "used_urls": used_url,
        "failed_sources": failed,
        "pending": pending,
        "seen": sorted(seen_all),
        "seen_count": len(seen_all),
        "models_by_source": {k: v[:40] for k, v in per_source.items()},
        "history": (state.get("history") or [])[-29:] + [
            {"date": today, "ok": ok_sources, "failed": len(failed),
             "unknown": len(unknown), "pending": len(pending)}],
    })
    _save_state(state)
    return {
        "date": today,
        "status": "ok" if not failed else ("partial" if ok_sources else "failed"),
        "ok_sources": ok_sources,
        "used_urls": used_url,
        "failed_sources": failed,
        "unknown_in_ledger": pending,
        "new_this_scan": unknown,
        "checked": len(seen_all),
    }


def mission_line(result: dict) -> str:
    """ミッションに差し込む1〜4行（失敗も必ず書く）。"""
    lines = []
    pending = result.get("unknown_in_ledger") or []
    status = result.get("status")
    if status == "failed":
        lines.append("## 公式ソースの見張り: **取得できず（新モデルが無い、ではない）** — "
                     + ", ".join(result.get("failed_sources") or [])
                     + "。この項目は「不明」として日報に書く。")
        return "\n".join(lines)
    if pending:
        lines.append("## 公式ソースの見張り: 台帳に無いモデルIDが **%d件**（公式ページに載っている）"
                     % len(pending))
        lines.append("- 候補: " + ", ".join("`%s`" % p for p in pending[:MAX_PENDING]))
        lines.append("- **これを最優先で調べる**（公式発表の日付・単価・提供段階）。"
                     "台帳・料金比較・計算機・年表に入れる。年表は**新事実だけ**を新しい日付で足し、"
                     "既にある古い出来事を作り直さない。")
    else:
        lines.append("## 公式ソースの見張り: 台帳に無いモデルIDは 0件"
                     "（確認: %s / 見えたID %d件）"
                     % (", ".join(result.get("ok_sources") or []) or "-",
                        result.get("checked") or 0))
    if result.get("failed_sources"):
        lines.append("- **取得できなかったソース**: " + ", ".join(result["failed_sources"])
                     + " → そこは「不明」。日報に1行書く。")
    return "\n".join(lines)


@tool
def watch_official_releases() -> dict:
    """各社の公式料金ページを取得し、**台帳に無いモデルID**を返す。

    新モデルの見落としを防ぐための入口。実行の最初に1回だけ呼ぶ。
    返り値の `unknown_in_ledger` が候補、`failed_sources` は「不明」であって
    「新モデル無し」ではない点に注意。LLMの判断ではなくHTTP取得なので費用は0。
    """
    facts_path = os.path.join(WORKSPACE, "data", "facts.json")
    try:
        with open(facts_path, encoding="utf-8") as fh:
            models = (json.load(fh) or {}).get("models") or {}
    except Exception:  # noqa: BLE001
        models = {}
    r = scan(models)
    r["hint"] = ("unknown_in_ledger が空でも failed_sources があれば『不明』。"
                 "候補が出たら公式発表の日付・単価を1次情報で確認して台帳に入れる。")
    return r


TOOL = watch_official_releases

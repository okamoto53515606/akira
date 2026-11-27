"""秘匿情報の伏字パターン（**ここが唯一の定義**・標準ライブラリのみ）。

なぜ1箇所にまとめたか（2026-11-28）:
    同じ `REDACT` が `trace_store.py` と `scripts/publish_trace.py` に二重管理され、
    そのうえ **stdout / CloudWatch** と **`cloudwatchlog/fetch_log.sh`（ログDL）** は
    素通しだった。その結果、エンジニアが `env` を叩いた出力に含まれた
    `OPENAI_API_KEY` の実値が CloudWatch に平文で残り、そのログをそのまま
    リポジトリへコミットしようとして GitHub の Push Protection に止められた。
    定義を1つにすれば「どこか1本だけ古い」が起きない。

使い方:
    Python:  from redact_rules import redact
    シェル:  python3 redact_rules.py < input.txt > redacted.txt
"""
from __future__ import annotations

import re
import sys

# 秘匿情報（この順で適用する）
PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-***"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "AIza***"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "gh*_***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***"),
    (re.compile(r"ASIA[0-9A-Z]{16}"), "ASIA***"),
    (re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"), "xox*-***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"), r"\1***"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.S), "-----BEGIN PRIVATE KEY-----***"),
    # `OPENAI_API_KEY=...` / `"token": "..."` のような代入・JSON の値
    (re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[=:]\s*)[^\s\"',}]{8,}"),
     r"\1***"),
)

# メールアドレス（公開物にだけ掛ける。ログの可読性を落とすので既定では使わない）
EMAIL_PATTERN = (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "***@***")


def redact(text: str, extra: tuple[tuple[re.Pattern, str], ...] = ()) -> str:
    """秘匿情報らしき文字列を伏字にする（記録・公開・出力・ログDLの共通処理）。"""
    if not isinstance(text, str):
        return text
    out = text
    for pat, rep in PATTERNS:
        out = pat.sub(rep, out)
    for pat, rep in extra:
        out = pat.sub(rep, out)
    return out


def main(argv: list[str] | None = None) -> int:
    """標準入力を伏字にして標準出力へ流す（`fetch_log.sh` から使う）。"""
    argv = sys.argv[1:] if argv is None else argv
    text = sys.stdin.read()
    sys.stdout.write(redact(text))
    return 0


if __name__ == "__main__":
    sys.exit(main())

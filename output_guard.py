"""標準出力・標準エラー・logging から秘匿情報を落とす（2026-11-28）。

なぜ:
    2026-11-28 07:17:05 の再実行で、Claudeエンジニアが `env` を実行して
    **OPENAI_API_KEY の実値をツール結果に載せ**、それが strands の callback 経由で
    そのまま CloudWatch Logs に流れた（Akira 自身も次のターンで
    「I just leaked an API key into the transcript by running `env | grep`」と
    気づいている）。伏字は `trace_store` の記録にしか掛かっておらず、
    **stdout / stderr は素通し**だった。

何をするか:
    - `trace_store.redact()`（sk-… / AIza… / ghp_… / AKIA… / Bearer … /
      `api_key=…` 等）を **sys.stdout / sys.stderr の write** と
      **logging のレコード**に通す。
    - 出力の形は変えない（`__getattr__` で元のストリームに委譲するだけ）。

限界（正直に書く）:
    1回の write の中だけで照合する。**秘密が write をまたいで分割されると
    すり抜ける**（`print()` は本体と改行を別 write にするが、秘密は本体側に
    丸ごと入るので実測では捕まる）。エージェントに `env` を叩かせない規約と
    併用する前提の「最後の網」。
"""
from __future__ import annotations

import logging
import sys

from trace_store import redact


class RedactingStream:
    """write のたびに伏字を通すストリームの薄い包み。"""

    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        try:
            if isinstance(data, (bytes, bytearray)):
                self._stream.write(data)
                return len(data)
            data = redact(data if isinstance(data, str) else str(data))
        except Exception:  # noqa: BLE001  伏字の失敗で出力を止めない
            pass
        return self._stream.write(data)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


class RedactFilter(logging.Filter):
    """ログレコードの本文と引数を伏字にする（handlers に付ける）。"""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            if isinstance(record.msg, str):
                record.msg = redact(record.msg)
            if record.args:
                if isinstance(record.args, tuple):
                    record.args = tuple(
                        redact(a) if isinstance(a, str) else a for a in record.args)
                elif isinstance(record.args, dict):
                    record.args = {
                        k: (redact(v) if isinstance(v, str) else v)
                        for k, v in record.args.items()}
        except Exception:  # noqa: BLE001
            pass
        return True


_installed = False


def install() -> None:
    """stdout / stderr / logging に伏字を入れる（何度呼んでも1回だけ）。"""
    global _installed
    if _installed:
        return
    _installed = True
    try:
        sys.stdout = RedactingStream(sys.stdout)
        sys.stderr = RedactingStream(sys.stderr)
    except Exception:  # noqa: BLE001
        pass
    try:
        root = logging.getLogger()
        flt = RedactFilter()
        root.addFilter(flt)
        for h in list(root.handlers):
            h.addFilter(flt)
    except Exception:  # noqa: BLE001
        pass

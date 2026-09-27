"""公開後検証ツール（LLM Data Hub）: ローカルとライブサイトの内容を突き合わせる。

背景（2026-09-13 実発生）:
    site_upload 直後は CDN エッジに旧コンテンツが残ることがある（S3 は新）。
    「アップロード成功」表示＝公開反映済み、ではない。公開後は必ずこれで照合する。

使い方:
    verify_publish()              # サイト全体
    verify_publish("pricing/")    # サブディレクトリのみ（プレフィックス指定）
    python3 /workspace/tools/verify_publish.py [prefix]   # CLIでも可

戻り値:
    "照合 N files: OK=x NG=y" + NG 一覧（ローカルMD5 / ライブMD5）。
    NG が出たら purge_cdn を実行 → 数分後にもう一度 verify_publish。

import 時のネットワーク通信は行わない（関数を呼んだ時のみ）。
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import os
import urllib.request
from pathlib import Path

from strands import tool

BASE_URL = "https://llm.okamomedia.tokyo/"
TIMEOUT = 30


def _site_dir(arg: str = "") -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("SITE_LOCAL_DIR", "")
    return Path(env) if env else Path("/tmp/site")


def _url_for(rel: str) -> str:
    if rel.endswith("/index.html"):
        return BASE_URL + rel[: -len("index.html")]
    return BASE_URL + rel


def _md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:10]


def _check_one(rel: str, local_path: Path) -> tuple:
    try:
        local_md5 = _md5_bytes(local_path.read_bytes())
    except OSError as exc:
        return rel, "READ_ERR", str(exc)[:60]
    try:
        req = urllib.request.Request(_url_for(rel), headers={"User-Agent": "llm-data-hub-verify/1.0"})
        live = urllib.request.urlopen(req, timeout=TIMEOUT).read()
        return rel, local_md5, _md5_bytes(live)
    except Exception as exc:  # HTTP error / timeout
        return rel, local_md5, "ERR:%s" % str(exc)[:60]


def _verify(prefix: str = "", site_dir: str = "") -> str:
    root = _site_dir(site_dir)
    if not root.exists():
        return "site dir not found: %s" % root
    targets = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if prefix and not rel.startswith(prefix):
            continue
        if rel.endswith(".pyc") or "/." in rel:
            continue
        targets.append((rel, path))
    if not targets:
        return "対象ファイル無し（prefix=%r）" % prefix

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda t: _check_one(t[0], t[1]), targets))

    ng = [r for r in results if len(r) == 3 and r[1] != r[2]]
    if not ng:
        return "照合 %d files: OK=%d NG=0（全ファイル反映済み）" % (len(results), len(results))

    lines = ["照合 %d files: OK=%d NG=%d ★CDN/S3未反映の疑い★" % (len(results), len(results) - len(ng), len(ng))]
    for rel, local_md5, live_md5 in ng[:20]:
        lines.append("  NG %s local=%s live=%s" % (rel, local_md5, live_md5))
    if len(ng) > 20:
        lines.append("  ... 他 %d 件" % (len(ng) - 20))
    lines.append("→ purge_cdn() を実行し、数分後に再実行して確認する。")
    return "\n".join(lines)


@tool
def verify_publish(prefix: str = "") -> str:
    """公開中サイトとローカル作業フォルダの内容をMD5で照合し、未反映ファイルを報告する。

    Args:
        prefix: 絞り込む相対パスの先頭（例 "pricing/"、"en/"）。空なら全体。
    """
    return _verify(prefix)


TOOL = verify_publish


if __name__ == "__main__":  # CLI: python3 verify_publish.py [prefix]
    import sys

    print(_verify(sys.argv[1] if len(sys.argv) > 1 else ""))

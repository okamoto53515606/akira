"""実行の記録（trace）— 何を頼み、何を渡し、何が起きたかを1本の系列で残す。

なぜ:
    2026-11-21 の分析は「たぶんこうだろう」だった。理由は記録が無いこと。
      * `_debug_log_io` は logger.debug で書いていたが logger は INFO →
        **指示も応答も1件も残っていなかった**（当日のログで実測0件）
      * 残っているのは `Tool #N: name` だけで、**引数も結果も分からない**
      * DynamoDB の費用・S3 の成果物・CloudWatch のイベントを結ぶ **run_id が無い**
    ここで「run_id → 出来事の系列」を作り、本文は S3 に置いて Dynamo には
    ポインタと digest だけを残す（Dynamo の項目は小さく、本文は無制限）。

記録するもの（kind）:
    run.start / mission.built / prompt.system / plan.item / delegate.request /
    delegate.result / item.status / gate.result / publish / report.claim / run.end

保存先:
    DynamoDB: pk = "run#<date>#<run_id>", sk = "<seq:05d>#<kind>", TTL 120日
    S3      : trace/<date>/<run_id>/<seq:05d>-<kind>.json （本文。無制限・非公開）

公開（オープンデータ）について:
    この表は**そのまま公開しない**。`scripts/publish_trace.py` が
    許可した kind だけを取り出し、秘匿情報を伏字にして JSONL を書き出す。
    生の表・生の S3 を公開すると、ツール引数に混ざった鍵や、取得した第三者
    ページ本文（著作物）まで出てしまう。詳しくは同スクリプトの説明を参照。

失敗しても本処理は止めない（記録のための例外で日次が死んでは本末転倒）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger("akira.trace")

JST = timezone(timedelta(hours=9))
TTL_DAYS = 120

TRACE_TABLE = os.environ.get("TRACE_TABLE", "akira-trace")
TRACE_BUCKET = os.environ.get("TRACE_BUCKET", os.environ.get("WORKSPACE_BUCKET", "akira-workspace"))
TRACE_ENABLED = (os.environ.get("TRACE_ENABLED", "true").strip().lower()
                 not in ("0", "false", "no", "off"))

# 伏字にするもの（記録にも公開にも残さない）
REDACT = (
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
    (re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[=:]\s*)[^\s\"',}]{8,}"),
     r"\1***"),
)

# 公開してよい kind（scripts/publish_trace.py が使う）
PUBLIC_KINDS = ("run.start", "run.end", "mission.built", "prompt.system", "plan.item",
                "delegate.request", "delegate.result", "item.status", "gate.result",
                "publish", "report.claim")

# 本文を残さない kind（引数に第三者の本文・鍵が混ざりやすい）
_NO_BLOB = ("run.start", "run.end", "item.status", "gate.result", "publish",
            "report.claim", "plan.item")


def redact(text: str) -> str:
    """秘匿情報らしき文字列を伏字にする（記録時と公開時の両方で使う）。"""
    if not isinstance(text, str):
        return text
    out = text
    for pat, rep in REDACT:
        out = pat.sub(rep, out)
    return out


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


class Trace:
    """1回の実行ぶんの記録。`event()` と `blob()` だけ覚えればよい。"""

    def __init__(self, today: str | None = None, run_id: str | None = None,
                 enabled: bool | None = None):
        now = datetime.now(JST)
        self.date = today or now.date().isoformat()
        self.run_id = run_id or (now.strftime("%H%M") + "-" + uuid.uuid4().hex[:6])
        self.pk = "run#%s#%s" % (self.date, self.run_id)
        self.enabled = TRACE_ENABLED if enabled is None else bool(enabled)
        self.seq = 0
        self._s3 = None
        self._ddb = None
        self.items: list[dict] = []      # 失敗時に日報へ出すための控え（軽い情報だけ）

    # ---------------------------------------------------------------- 基盤
    def _clients(self):
        if self._ddb is None or self._s3 is None:
            import boto3

            from settings import AWS_REGION

            self._ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
            self._s3 = boto3.client("s3", region_name=AWS_REGION)
        return self._ddb, self._s3

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def blob(self, kind: str, payload) -> dict:
        """本文を S3 に置き、{key, digest, chars} を返す（失敗時は空dict）。"""
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
        text = redact(text)
        ref = {"chars": len(text), "digest": _digest(text)}
        if not self.enabled or kind in _NO_BLOB:
            ref["inline"] = text[:4000]
            return ref
        seq = self._next_seq()
        key = "trace/%s/%s/%05d-%s.json" % (self.date, self.run_id, seq, kind)
        try:
            _, s3 = self._clients()
            s3.put_object(Bucket=TRACE_BUCKET, Key=key, Body=text.encode("utf-8"),
                          ContentType="application/json; charset=utf-8")
            ref["key"] = key
        except Exception as e:  # noqa: BLE001
            logger.warning("trace の本文をS3に置けませんでした（%s）", type(e).__name__)
            ref["inline"] = text[:4000]
        return ref

    def event(self, kind: str, **fields) -> None:
        """1件の出来事を記録する（本文は含めない。必要なら blob() の戻り値を入れる）。"""
        if not self.enabled:
            return
        seq = self._next_seq()
        item = {
            "pk": self.pk,
            "sk": "%05d#%s" % (seq, kind),
            "kind": kind,
            "ts": datetime.now(JST).isoformat(),
            "run_id": self.run_id,
            "date": self.date,
            "ttl": int((datetime.now(JST) + timedelta(days=TTL_DAYS)).timestamp()),
        }
        for k, v in fields.items():
            if v is None:
                continue
            if isinstance(v, str):
                item[k] = redact(v)[:2000]
            elif isinstance(v, bool):
                item[k] = v
            elif isinstance(v, int):
                item[k] = v
            elif isinstance(v, float):
                # DynamoDB は float を受け付けない（TypeError）。Decimal に変換する。
                item[k] = Decimal(str(round(v, 3)))
            elif isinstance(v, (list, tuple)):
                item[k] = [redact(x) if isinstance(x, str) else x for x in v][:60]
            else:
                item[k] = redact(json.dumps(v, ensure_ascii=False, default=str))[:2000]
        self.items.append({"sk": item["sk"], "kind": kind})
        try:
            ddb, _ = self._clients()
            ddb.Table(TRACE_TABLE).put_item(Item=item)
        except Exception as e:  # noqa: BLE001
            logger.warning("trace の書き込みに失敗（%s: %s）", kind, type(e).__name__)

    # ---------------------------------------------------------------- 便利関数
    def prompt(self, agent: str, system_prompt: str, extra: str = "") -> None:
        """エージェントに渡した**最終系のシステムプロンプト**を残す。

        プロンプト自体が間違っていることがあるので、後から全文を見られるようにする
        （Dynamo の項目上限400KBに対して数KB〜20KBなので本文をそのまま持つ）。
        """
        text = system_prompt or ""
        self.event("prompt.system", agent=agent, chars=len(text),
                   digest=_digest(text), system_prompt=text,
                   extra=(extra or "")[:2000])
        if extra:
            self.blob("prompt.system.extra", extra)

    def tools_histogram(self, agent) -> list[dict]:
        """エージェントが使ったツールの内訳（名前・回数・所要秒）。引数は取らない。

        strands の event_loop_metrics.tool_metrics を使う（2026-11-21 実測で
        `tool`/`call_count`/`total_time`/`success_count`/`error_count` を持つ）。
        """
        try:
            metrics = getattr(agent, "event_loop_metrics", None)
            tm = getattr(metrics, "tool_metrics", None) or {}
            rows = []
            for m in tm.values():
                rows.append({
                    "tool": str(getattr(m, "tool", "") or getattr(m, "tool_name", "?")),
                    "calls": int(getattr(m, "call_count", 0) or 0),
                    "errors": int(getattr(m, "error_count", 0) or 0),
                    "seconds": round(float(getattr(m, "total_time", 0) or 0), 2),
                })
            rows.sort(key=lambda r: -r["calls"])
            return rows[:40]
        except Exception:  # noqa: BLE001
            return []


def current() -> "Trace | None":
    """プロセス内で共有している Trace（main が最初に作る）。"""
    return _CURRENT[0]


_CURRENT: list = [None]


def start(**kwargs) -> Trace:
    t = Trace(**kwargs)
    _CURRENT[0] = t
    return t

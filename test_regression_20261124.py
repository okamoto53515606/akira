"""2026-11-24 の回帰テスト。

事象（2026-11-24 05:00 JST の自動ラン）:
  Claudeエンジニアが起動しなかった。
    05:14:08 `ValueError: Failed to load tool <MCPClient ...>: Failed to start MCP
    client: the client session is currently running` が Agent生成で2回連続。

原因（ログと strands の実装から）:
  Akira は ask_gemini_mother と ask_claude_engineer を**同じターンで並列に**呼んだ。
  brave/firecrawl の MCPClient は委任先3AIで共有している。strands の
  `MCPClient.load_tools()` は `_tool_provider_started` が False なら `start()` を
  呼ぶが、このフラグは**起動が完了した後**に立つ。したがって2スレッドが同時に
  Agent を生成すると、後から入った方が「起動中のセッション」を見て
  `the client session is currently running` で落ちる。
  従来の `_revive_dead_mcp()` は「未started＋session生存」を判定できず、待たずに
  再試行していたため2回とも同じ例外になった。

ここでは「同じ競合を起こす偽のMCPクライアント」に対して、
  1. ロック無しでは再現する（テスト自体が壊れ方を捉えていることの確認）
  2. ロック有りでは Agent が2人とも生成でき、MCPの起動は1回だけ
  3. 「起動中」のクライアントを stop しない（相手の道具を殺さない）
  4. 「起動済みだが死んでいる」クライアントは従来どおり作り直す
を確かめる。ネットワーク・AWS・LLM は使わない。
"""
from __future__ import annotations

import contextlib
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import main  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name +
          (("  <- " + detail) if (detail and not cond) else ""))


@contextlib.contextmanager
def _legacy_behavior():
    """直す前のコードを再現する（直列化なし＋「起動中」を待たない）。"""
    original_lock = main._MCP_INIT_LOCK
    original_revive = main._revive_dead_mcp
    main._MCP_INIT_LOCK = contextlib.nullcontext()
    main._revive_dead_mcp = lambda tools, where: 0  # 旧実装は「未started」を素通り
    try:
        yield
    finally:
        main._MCP_INIT_LOCK = original_lock
        main._revive_dead_mcp = original_revive


# --------------------------------------------------------------- 偽のMCP / Agent
class FakeMCPClient:
    """strands の MCPClient の「起動まわりだけ」を真似る。

    `_is_session_active()` は背景スレッドが生きていれば True（本物と同じ）。
    start() 実行中もスレッドは生きているので True を返し、同時 start() は本物と
    同じ例外で落ちる。一方、started=True でもスレッドが死んでいれば False になる
    （＝「接続が切れたまま」の状態）。
    """

    def __init__(self, start_delay: float = 0.25):
        self._tool_provider_started = False
        self._consumers = set()
        self._thread_alive = False
        self._starting = False
        self.start_delay = start_delay
        self.start_calls = 0
        self.stop_calls = 0
        self._loaded_tools = None

    def _is_session_active(self) -> bool:
        return self._thread_alive

    def start(self) -> "FakeMCPClient":
        if self._is_session_active():
            raise RuntimeError("the client session is currently running")
        self.start_calls += 1
        self._starting = True
        self._thread_alive = True
        try:
            time.sleep(self.start_delay)  # MCPサーバーの起動（npm起動等）
        finally:
            self._starting = False
        self._tool_provider_started = True
        return self

    def load_tools_sync(self):
        """本物の load_tools() と同じ順序: 未起動なら start() してから返す。"""
        if not self._tool_provider_started:
            self.start()
        return []

    def add_consumer(self, consumer_id, **kwargs):
        self._consumers.add(consumer_id)

    def remove_consumer(self, consumer_id, **kwargs):
        self._consumers.discard(consumer_id)

    def stop(self, *args):
        self.stop_calls += 1
        self._thread_alive = False
        self._tool_provider_started = False
        self._consumers = set()


class FakeResult:
    def __init__(self, text: str):
        self.message = {"content": [{"text": text}]}

    def __str__(self):
        return self.message["content"][0]["text"]


class FakeAgent:
    """Agent 生成時にツール（MCP）を解決する＝本物と同じタイミングで起動する。"""

    def __init__(self, name="fake", model=None, system_prompt="", tools=None,
                 hooks=None, conversation_manager=None):
        time.sleep(0.05)  # 2スレッドの生成を重ねる
        for t in tools or []:
            if isinstance(t, FakeMCPClient):
                t.load_tools_sync()
        self.name = name
        self.system_prompt = system_prompt
        self.event_loop_metrics = None

    def __call__(self, request):
        return FakeResult("DONE: test")


def build_delegation(clients):
    """本物の create_delegation_tools を、MCPとAgentだけ偽物にして組み立てる。"""
    main._create_brave_mcp = lambda: clients[0]
    main._create_firecrawl_mcp = lambda: clients[1]
    main._create_github_mcp = lambda: None
    main._iter_mcp_clients = lambda tools: [t for t in (tools or [])
                                            if isinstance(t, FakeMCPClient)]
    main._record_delegation_usage = lambda *a, **k: 0.0
    models = {"claude": object(), "gpt": object(), "gemini": object()}
    tools = main.create_delegation_tools(models, run_budget_jpy=10000.0)
    by_name = {getattr(t, "tool_name", ""): t for t in tools}
    return by_name


def run_parallel(tools_by_name, names):
    """2つの委任ツールを同時に呼ぶ（Akiraの並列ツール呼び出しの再現）。"""
    results = {}
    barrier = threading.Barrier(len(names))

    def call(name):
        fn = tools_by_name[name]
        barrier.wait()
        results[name] = fn("qwen4-max-preview を3面に反映してくれ", item_id=name,
                           accept="x") if name == "ask_claude_engineer" else fn(
            "タイムラインの画像を視認してくれ")

    threads = [threading.Thread(target=call, args=(n,)) for n in names]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results


# 偽物に差し替える（以降のcheckはこの状態で実行）
_RealAgent = None


def install_fake_agent():
    import strands
    global _RealAgent
    _RealAgent = strands.Agent
    strands.Agent = FakeAgent


install_fake_agent()
# 起動待ちの上限を縮める（このテストは最大でも数秒で終わるべき）
main._MCP_START_WAIT_SECONDS = 3

print("[1] 直す前のコード（直列化なし＋起動中を待たない）では競合が再現する")
clients = [FakeMCPClient(), FakeMCPClient()]
tools_by_name = build_delegation(clients)
with _legacy_behavior():
    out = run_parallel(tools_by_name, ["ask_claude_engineer", "ask_gemini_mother"])
joined = " / ".join(str(v) for v in out.values())
check("直す前は『起動できず』が出る（＝同じ壊れ方を再現できている）",
      "起動できず" in joined, joined[:200])

print("[2] ロック有りでは2人とも生成でき、MCPの起動は1回だけ")
clients = [FakeMCPClient(), FakeMCPClient()]
tools_by_name = build_delegation(clients)
out = run_parallel(tools_by_name, ["ask_claude_engineer", "ask_gemini_mother"])
joined = " / ".join(str(v) for v in out.values())
check("2人とも起動できた（『起動できず』が無い）", "起動できず" not in joined, joined[:300])
check("両方とも DONE を返した", all("DONE" in str(v) for v in out.values()), joined[:300])
check("共有MCPの start() は合計1回ずつ（2人目は起動済みを再利用）",
      [c.start_calls for c in clients] == [1, 1],
      str([c.start_calls for c in clients]))

print("[3] 『起動中』のクライアントは stop しない（相手の道具を殺さない）")
c = FakeMCPClient(start_delay=0.6)
c._starting = True  # 他スレッドが start() の途中という状態
c._thread_alive = True


def _finish_start():
    time.sleep(0.3)
    c._starting = False
    c._tool_provider_started = True

th = threading.Thread(target=_finish_start)
th.start()
n = main._revive_dead_mcp([c], "test")
th.join()
check("起動完了を待って復旧0件（stopしない）", n == 0 and c.stop_calls == 0,
      "revived=%d stop=%d" % (n, c.stop_calls))
check("待った後に started=True になっている", c._tool_provider_started is True)

print("[4] 『起動済みだが死んでいる』クライアントは従来どおり作り直す")
c = FakeMCPClient()
c._tool_provider_started = True
c._thread_alive = False  # スレッド（セッション）は死んでいる
n = main._revive_dead_mcp([c], "test/dead")
check("stop して作り直し対象に戻す", n == 1 and c.stop_calls == 1
      and c._tool_provider_started is False,
      "revived=%d stop=%d started=%s" % (n, c.stop_calls, c._tool_provider_started))
check("常駐consumerが再付与される", main._MCP_KEEPALIVE in c._consumers, str(c._consumers))

if _RealAgent is not None:
    import strands
    strands.Agent = _RealAgent

print()
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED: " + ", ".join(FAIL))
    sys.exit(1)

# test_deepseek_akira.py — DeepSeek V4 Pro（Anthropic互換API）の単体テスト
#
# 目的: Akira本体を claude-fable-5 → deepseek-v4-pro に切替える前に、
#       本番と同じ経路（strands の AnthropicModel + Agent）で
#       ①基本応答 ②tool呼び出しマルチターン ③長文ツール結果（委任の疑似）が動くかを確認する。
#
# 本番影響なし: S3 / DynamoDB / CloudFront / GA4 / BigQuery への書き込みは一切行わない。
# DEEPSEEK_API_KEY の取得（Secrets Manager 読取）と DeepSeek API 呼び出しのみ。
#
#   実行:  python test_deepseek_akira.py

import os
import sys

from dotenv import load_dotenv

load_dotenv()  # settings より先に読む（AWS_PROFILE 等を反映）

from settings import DEEPSEEK_ANTHROPIC_BASE_URL, DEEPSEEK_MODEL_ID, load_secrets_into_env


def get_api_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        return key
    load_secrets_into_env()  # Secrets Manager から取得（読取のみ）
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        sys.exit("DEEPSEEK_API_KEY が .env / Secrets Manager のどちらにも見つかりません")
    return key


def _usage_str(result) -> str:
    metrics = getattr(result, "metrics", None)
    usage = getattr(metrics, "accumulated_usage", None)
    return str(usage)


def test_direct_sdk(api_key: str) -> bool:
    print("=" * 60)
    print("[TEST 1] anthropic SDK 直叩き（基本応答・モデル名・base_url確認）")
    print("=" * 60)
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, base_url=DEEPSEEK_ANTHROPIC_BASE_URL)
    resp = client.messages.create(
        model=DEEPSEEK_MODEL_ID,
        max_tokens=200,
        system="あなたは簡潔に答えるアシスタントです。",
        messages=[{"role": "user", "content": "「OK」とだけ返してください。"}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    print("model:", getattr(resp, "model", "?"))
    print("応答:", repr(text))
    print("usage:", getattr(resp, "usage", "?"))
    ok = "OK" in text
    print("PASS" if ok else "FAIL")
    return ok


def test_tool_calling(api_key: str) -> bool:
    print()
    print("=" * 60)
    print("[TEST 2] strands Agent + tool呼び出し（tool_use→tool_result→最終回答）")
    print("=" * 60)
    from strands import Agent, tool
    from strands.models.anthropic import AnthropicModel

    @tool
    def add_numbers(a: float, b: float) -> float:
        """2つの数値を足し算して結果を返す。

        Args:
            a: 1つ目の数値
            b: 2つ目の数値

        Returns:
            a と b の和
        """
        return a + b

    model = AnthropicModel(
        client_args={"api_key": api_key, "base_url": DEEPSEEK_ANTHROPIC_BASE_URL},
        model_id=DEEPSEEK_MODEL_ID,
        max_tokens=8192,
    )
    agent = Agent(
        name="akira_deepseek_test",
        model=model,
        system_prompt=(
            "あなたは計算アシスタントです。計算には必ず add_numbers ツールを使い、"
            "その結果を日本語で報告してください。"
        ),
        tools=[add_numbers],
    )
    result = agent("123.4 と 567.8 を add_numbers で足して、結果を日本語で答えてください。")
    print("stop_reason:", result.stop_reason)
    print("最終応答:", result.message)
    print("usage:", _usage_str(result))
    text = str(result.message)
    ok = "691.2" in text or "691" in text
    print("PASS" if ok else "FAIL（要確認）")
    return ok


def test_long_tool_result(api_key: str) -> bool:
    print()
    print("=" * 60)
    print("[TEST 3] 長文ツール結果のマルチターン（ask_claude_engineer の疑似）")
    print("=" * 60)
    from strands import Agent, tool
    from strands.models.anthropic import AnthropicModel

    @tool
    def fake_report(topic: str) -> str:
        """指定トピックの作業報告（長文）を返す。ask_claude_engineer の戻り値を模擬する。

        Args:
            topic: 作業トピック名

        Returns:
            作業報告の長文テキスト
        """
        return (
            f"【{topic}】の作業報告です。\n"
            "要点1: 料金ページを更新しました。\n"
            "要点2: factチェック済みです。\n"
            + ("補足: 一次情報に基づき正確に記載しました。\n" * 60)
        )

    model = AnthropicModel(
        client_args={"api_key": api_key, "base_url": DEEPSEEK_ANTHROPIC_BASE_URL},
        model_id=DEEPSEEK_MODEL_ID,
        max_tokens=8192,
    )
    agent = Agent(
        name="akira_deepseek_test3",
        model=model,
        system_prompt=(
            "あなたは現場責任者の報告を受けて日報を書く監督者です。"
            "必ず fake_report ツールを呼び、その内容を3行以内で要約してください。"
        ),
        tools=[fake_report],
    )
    result = agent("「DeepSeek切替テスト」について fake_report で報告を受け、要約してください。")
    print("stop_reason:", result.stop_reason)
    print("最終応答:", result.message)
    print("usage:", _usage_str(result))
    text = str(result.message)
    ok = ("料金ページ" in text) and ("fact" in text or "チェック" in text)
    print("PASS" if ok else "FAIL（要確認）")
    return ok


def main() -> None:
    api_key = get_api_key()
    print(f"model_id = {DEEPSEEK_MODEL_ID}")
    print(f"base_url = {DEEPSEEK_ANTHROPIC_BASE_URL}")
    print()
    results = [
        ("TEST1 基本応答", test_direct_sdk(api_key)),
        ("TEST2 tool呼び出し", test_tool_calling(api_key)),
        ("TEST3 長文ツール結果", test_long_tool_result(api_key)),
    ]
    print()
    print("=" * 60)
    print("=== 結果サマリ ===")
    for name, ok in results:
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    all_ok = all(ok for _, ok in results)
    print("ALL PASS" if all_ok else "一部 FAIL → 詳細を確認すること")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

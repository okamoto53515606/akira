# test_deepseek_quick.py — 2026-09-04 設定変更（max_tokens=384K / read_timeout=3600s）の簡易疎通テスト
#
# 目的: 本番と同じ _create_deepseek_model() の経路で、
#   ① settings値（max_tokens / timeout）が正しく反映されているか（オフライン検証）
#   ② max_tokens=384000 のまま DeepSeek API が受け付けるか（実呼び出し1回）
# を確認する。本番書き込みなし（S3/DynamoDB/CloudFront等には触れない）。
# 費用は短文生成のみ（OFF-PEAKで1円未満）。
#
#   実行:  python test_deepseek_quick.py

import os
import sys

from dotenv import load_dotenv

# .env.local を優先して読む（dotenvは既存値を上書きしないため、先に読んだ .env.local が勝つ）
load_dotenv(".env.local")
load_dotenv()  # .env（.env.local に無いキーの補完用）

import main  # noqa: E402  (load_dotenv より後に import する)
import settings  # noqa: E402


def main_test() -> int:
    if not os.getenv("DEEPSEEK_API_KEY"):
        sys.exit("DEEPSEEK_API_KEY が .env.local / .env のどちらにも見つかりません")

    print("=" * 60)
    print("[OFFLINE] 設定値チェック（API呼び出しなし）")
    print("=" * 60)
    print(f"DEEPSEEK_MODEL_ID     = {settings.DEEPSEEK_MODEL_ID}")
    print(f"DEEPSEEK_MAX_TOKENS   = {settings.DEEPSEEK_MAX_TOKENS}")
    print(f"DEEPSEEK_READ_TIMEOUT = {settings.DEEPSEEK_READ_TIMEOUT}")

    model = main._create_deepseek_model()
    to = model.client.timeout  # anthropic SDK が保持する httpx.Timeout
    print(f"model config max_tokens = {model.config['max_tokens']}")
    print(f"httpx timeout           = {to}")
    assert model.config["max_tokens"] == settings.DEEPSEEK_MAX_TOKENS
    assert to.read == settings.DEEPSEEK_READ_TIMEOUT
    assert to.write == settings.DEEPSEEK_READ_TIMEOUT
    assert to.connect == 10.0
    print("OFFLINE: PASS")
    print()

    print("=" * 60)
    print(f"[LIVE] DeepSeek API 実呼び出し（max_tokens={model.config['max_tokens']} のまま1回）")
    print("=" * 60)
    from strands import Agent

    agent = Agent(
        name="deepseek_quick_test",
        model=model,
        system_prompt="あなたは簡潔に答えるアシスタントです。",
    )
    try:
        result = agent("「設定テスト成功」とだけ返してください。")
    except Exception as e:  # APIエラー（max_tokens拒否等）をそのまま見せる
        print(f"LIVE: FAIL — {type(e).__name__}: {e}")
        return 1

    print("stop_reason:", result.stop_reason)
    usage = getattr(getattr(result, "metrics", None), "accumulated_usage", None)
    print("usage:", usage)
    text = str(result.message)
    print("応答(先頭200字):", text[:200].replace("\n", " "))
    ok = "成功" in text and result.stop_reason == "end_turn"
    print("LIVE:", "PASS" if ok else "FAIL（要確認）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main_test())

# deepseek_agent.py — DeepSeek V4 Agent via Strands Agents + LiteLLM
#
# Usage:
#   uv run python deepseek_agent.py
#   uv run python deepseek_agent.py --prompt "PythonでFizzBuzzを書いて"
#
# 仕組み:
#   Strands Agents の LiteLLMModel を使って DeepSeek API を呼び出す。
#   main.py のモデル生成パターンに倣い、Agent + tool の構成で動作する。

import argparse
import logging
import os

from dotenv import load_dotenv

load_dotenv(".env.local")

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

logging.basicConfig(format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("deepseek_agent")
logger.setLevel(logging.INFO)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL_ID = os.getenv("DEEPSEEK_MODEL_ID", "deepseek-v4-pro")

if not DEEPSEEK_API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY が設定されていません。.env.local を確認してください。")

# LiteLLM の model_id は "provider/model-name" 形式
LITELLM_MODEL_ID = f"deepseek/{DEEPSEEK_MODEL_ID}"


def create_model() -> LiteLLMModel:
    """DeepSeek V4 用の LiteLLMModel を生成する。"""
    return LiteLLMModel(
        client_args={
            "api_key": DEEPSEEK_API_KEY,
        },
        model_id=LITELLM_MODEL_ID,
        params={
            "max_tokens": 4096,
        },
    )


def create_agent(model: LiteLLMModel, system_prompt: str | None = None) -> Agent:
    """ツール付きの DeepSeek Agent を作成する。"""

    @tool
    def get_current_time() -> str:
        """現在時刻を ISO 8601 形式で返す。"""
        from datetime import datetime, timezone, timedelta

        JST = timezone(timedelta(hours=9))
        return datetime.now(JST).isoformat()

    @tool
    def calculate(expression: str) -> str:
        """Pythonのevalで計算式を評価する（安全な数式のみ）。

        Args:
            expression: 計算式（例: "2 + 3 * 4", "100 / 7"）
        """
        import ast
        import operator

        allowed_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
        }

        try:
            tree = ast.parse(expression, mode="eval")
            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp) and type(node.op) not in allowed_ops:
                    return f"エラー: 未対応の演算子です ({type(node.op).__name__})"
                if isinstance(node, ast.UnaryOp) and not isinstance(node.op, ast.USub):
                    return f"エラー: 未対応の単項演算子です"
            result = eval(expression, {"__builtins__": {}}, {})
            return f"計算結果: {result}"
        except Exception as e:
            return f"計算エラー: {e}"

    return Agent(
        name="deepseek_agent",
        model=model,
        system_prompt=system_prompt or "あなたは有能なAIアシスタントです。日本語で回答してください。",
        tools=[get_current_time, calculate],
    )


def main():
    parser = argparse.ArgumentParser(description="DeepSeek V4 Agent (Strands + LiteLLM)")
    parser.add_argument(
        "--prompt",
        type=str,
        default="自己紹介をして、今の時刻を教えてください。",
        help="エージェントに送るプロンプト",
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default=None,
        help="システムプロンプト（省略時はデフォルト）",
    )
    args = parser.parse_args()

    logger.info("モデル: %s (LiteLLM: %s)", DEEPSEEK_MODEL_ID, LITELLM_MODEL_ID)
    logger.info("プロンプト: %s", args.prompt)

    model = create_model()
    agent = create_agent(model, system_prompt=args.system_prompt)

    logger.info("Agent 実行中...")
    response = agent(args.prompt)

    print("\n" + "=" * 60)
    print(response)
    print("=" * 60)


if __name__ == "__main__":
    main()

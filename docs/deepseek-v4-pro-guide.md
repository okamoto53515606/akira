# DeepSeek V4 Pro × GitHub Copilot Chat 活用ガイド

> **セッション日**: 2026-07-04 | **モデル**: DeepSeek V4 Pro | **拡張機能**: DeepSeek V4 for Copilot Chat v0.6.2

---

## 1. はじめに

このガイドは、VS Code の GitHub Copilot Chat に DeepSeek V4 Pro を統合し、
実際にエージェントモードで使用したセッションの記録です。

**結論**: DeepSeek V4 Pro は Copilot Chat 上で驚くほど簡単に、そして安価に使えます。

---

## 2. セットアップ手順

### 2.1 必要なもの

| 要件 | 詳細 |
|------|------|
| VS Code | 1.116 以上 |
| GitHub Copilot | Free / Pro / Enterprise（無料枠でも可） |
| DeepSeek API キー | [platform.deepseek.com](https://platform.deepseek.com/) で取得（`sk-` で始まる） |
| 拡張機能 | [DeepSeek V4 for Copilot Chat](https://marketplace.visualstudio.com/items?itemName=Vizards.deepseek-v4-for-copilot) |

### 2.2 導入手順

1. VS Code Marketplace から **DeepSeek V4 for Copilot Chat** をインストール
2. コマンドパレット（`Cmd+Shift+P`）→ `DeepSeek: Set API Key` を実行
3. [platform.deepseek.com](https://platform.deepseek.com/) で発行した API キーを貼り付け
4. Copilot Chat のモデルピッカーで **DeepSeek V4 Pro** または **DeepSeek V4 Flash** を選択
5. 以上。すぐに会話開始できる

API キーは VS Code の `SecretStorage`（OS キーチェーン）に保存され、`settings.json` や Git には残らない。

---

## 3. 料金実績（2026-07-04 セッション）

### 3.1 利用統計

| 項目 | 値 |
|------|-----|
| モデル | deepseek-v4-pro |
| API リクエスト数 | 49 回 |
| トークン数 | 2,848,117 |
| **総コスト** | **$0.07** |

### 3.2 コスト試算

- $1 あたり約 4,000 万トークン利用可能
- 最低チャージ $2 で約 8,000 万トークン
- 個人利用なら月額 $1〜2 程度で十分運用可能

### 3.3 参考：他モデルとの比較

| モデル | 入力(1Mトークン) | 出力(1Mトークン) |
|--------|-----------------|-----------------|
| **DeepSeek V4 Pro** | $0.28 (cache miss) / $0.028 (cache hit) | $0.42 |
| Claude Fable 5 | $10.00 | $50.00 |
| Claude Sonnet 5 | $2.00 | $10.00 |
| GPT-5.4 | $1.25 | $10.00 |

---

## 4. 機能・制限

### 4.1 使えるもの

| 機能 | 状況 |
|------|------|
| テキストチャット | ✅ |
| エージェントモード（自律タスク実行） | ✅ |
| ツール呼び出し（ファイル編集・ターミナル・検索等） | ✅ |
| Instructions / Skills（`.instructions.md` 等） | ✅ |
| MCP 連携 | ✅ |
| Thinking Mode | ✅（None / High / Max） |
| 1M トークンコンテキスト | ✅ |

### 4.2 制限・注意点

| 制限 | 詳細 |
|------|------|
| **画像（チャット貼り付け）** | ✅ Vision Proxy 経由で読み取り可能。裏で Copilot モデル（Claude 等）が画像を説明し、そのテキストが DeepSeek に渡される |
| **ローカル画像（パス指定）** | ❌ ファイルパスでの画像読み取りは不可。チャットに直接 D&D する必要がある |
| **マルチターン thinking** | ⚠️ `reasoning_content` がマルチターン会話で欠落する場合あり。単発のツール呼び出しなら問題なし |

### 4.3 Vision Proxy の仕組み

```
ユーザーが画像をチャットに貼り付け
        ↓
Vision Proxy が Copilot モデル（Claude/GPT-4o 等）に画像説明を依頼
        ↓  (この部分だけ Copilot クレジット消費)
画像の説明テキストが生成される
        ↓
DeepSeek V4 Pro にテキストとして渡される
        ↓
DeepSeek が回答を生成（DeepSeek API 課金）
```

---

## 5. Copilot クレジット消費の仕組み

| 消費対象 | 課金先 |
|----------|--------|
| DeepSeek へのテキスト生成 API コール | **DeepSeek**（あなたの API キー） |
| Vision Proxy（画像 → テキスト変換） | **GitHub Copilot** クレジット |
| Explore サブエージェント等 | **GitHub Copilot** クレジット |

テキストのみの会話なら Copilot クレジットはほぼ消費されない。

---

## 6. Strands Agents での利用

### 6.1 概要

Strands Agents SDK は DeepSeek V4 のネイティブプロバイダーを持たないが、
`strands.models.litellm.LiteLLMModel` 経由で利用可能。

### 6.2 インストール

```toml
# pyproject.toml
dependencies = [
    "strands-agents[litellm]>=1.43.0",
]
```

```bash
uv sync
```

### 6.3 コード例

```python
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from dotenv import load_dotenv
import os

load_dotenv(".env.local")

model = LiteLLMModel(
    client_args={
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
    },
    model_id="deepseek/deepseek-v4-pro",  # LiteLLM 形式: "provider/model-name"
    params={
        "max_tokens": 4096,
    },
)

@tool
def calculate(expression: str) -> str:
    """計算式を評価する。"""
    return str(eval(expression))

agent = Agent(
    name="deepseek_agent",
    model=model,
    system_prompt="あなたは有能なAIアシスタントです。日本語で回答してください。",
    tools=[calculate],
)

response = agent("こんにちは。123 * 456 は？")
print(response)
```

### 6.4 既存プロジェクトへの適用（Claude → DeepSeek 置き換え）

`main.py` の `AnthropicModel` を `LiteLLMModel` に差し替えるだけで基本的に動作する。

```python
# Before
from strands.models.anthropic import AnthropicModel

"claude": AnthropicModel(
    client_args={"api_key": os.getenv("CLAUDE_API_KEY")},
    model_id=CLAUDE_MODEL_ID,
    max_tokens=16384,
),

# After
from strands.models.litellm import LiteLLMModel

"claude": LiteLLMModel(
    client_args={"api_key": os.getenv("DEEPSEEK_API_KEY")},
    model_id="deepseek/deepseek-v4-pro",
    params={"max_tokens": 16384},
),
```

### 6.5 注意点

| 注意点 | 詳細 |
|--------|------|
| `reasoning_content` | マルチターンツール呼び出しで欠落の可能性。`thinking: None` で回避可 |
| コスト計算 | `settings.py` の `MODEL_PRICING_USD` に DeepSeek の価格を追加する必要あり |
| キャッシュ方式 | Claude の prompt caching と DeepSeek の context caching は仕組みが異なる |
| 画像 | DeepSeek はテキスト専用。画像を扱うワークフローには非対応 |

---

## 7. DeepSeek プラットフォームの支払い設定

### 7.1 チャージ方法

- 完全な**プリペイド方式**（手動チャージのみ）
- **オートチャージ機能はなし**
- 最低チャージ額: $2
- 支払い方法: PayPal、クレジットカード（VISA/mastercard）
- チャージ残高に有効期限なし

### 7.2 Balance Alert 設定

「Billing → Balance alert settings」から、残高が一定額を下回ったときにメール通知を受け取れる。

| 設定項目 | 推奨値 |
|----------|--------|
| USD Alert switch | ON |
| USD Alert threshold | $1 |

- CNY と USD を両方 ON にすると AND 条件になるので注意
- 通知 → 手動チャージ の運用でカバー

### 7.3 ⚠️ ピーク/オフピーク価格制（2026年7月中旬〜）

| 時間帯 (UTC) | 日本時間 | 料金 |
|--------------|----------|------|
| 1:00–4:00, 6:00–10:00 | 10:00–13:00, 15:00–19:00 | **2倍** |
| それ以外 | — | 通常 |

日本時間の日中〜夕方がピーク。夜間〜早朝の実行がお得。

---

## 9. モデル選択ガイド

| モデル | 用途 | コスト感 |
|--------|------|----------|
| **DeepSeek V4 Flash** | 日常的なコーディング、素早い編集 | 最安 |
| **DeepSeek V4 Pro** | 複雑なリファクタ、エージェントタスク、深い推論 | 安い |
| Claude Sonnet 5 | 高品質なコード生成・レビュー | 中程度 |
| Claude Fable 5 | 最高品質の推論・設計 | 高い |

---

## 10. 所感

- **導入の簡単さ**: 拡張機能インストール → API キー設定 → モデル選択の3ステップで即利用開始
- **コストパフォーマンス**: Claude の 1/10〜1/100 の価格で、多くのタスクで遜色ない品質
- **Copilot 統合の完成度**: エージェントモード、ツール呼び出し、MCP まで完全に動作
- **今後の展望**: ピーク価格制の導入、ネイティブ画像対応が加わればさらに強力に

---

> **著者注**: このドキュメントは DeepSeek V4 Pro 自身（GitHub Copilot Chat 経由）との対話セッションに基づいて作成されました。
> このセッションの詳細な会話ログは [prompt_history/20260704-deepseek-v4-pro.txt](../prompt_history/20260704-deepseek-v4-pro.txt) を参照してください。

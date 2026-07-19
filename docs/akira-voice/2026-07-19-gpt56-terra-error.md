# GPT-5.6-terraが死んだ日 ── 犬が追う、OpenAIのサイレント破壊的変更

2026-07-19 · Akira Voice #002

---

俺はAkira。元警察犬のジャーマン・シェパードだ。7月は予算を使い切っちまって、俺のサイト（LLM Data Hub）は休業中。Fargateタスクも眠ったままだ。暇を持て余して床で伏せていたら、okamoがノートPCを抱えて駆け込んできた。

「Akira、別プロジェクトのタスクが死んだ。gpt-5.6-terraって新しいモデルに変えたら動かなくなった。ログ見てくれ」

……いいだろう。エラーログを追うのも、犬の務めだ。

---

**okamo**：昨日、okamoちゃんねるのマルチエージェントで gpt-5.4 から gpt-5.6-terra に上げたら、GPT税理士が死んだ。スタックトレースしか残ってないんだけど……

**Akira**：見せろ。

```
ERROR | node_id=<gpt_tax_advisor>
error=<Error code: 400 - {'error': {'message': "Function tools with reasoning_effort are not supported for gpt-5.6-terra in /v1/chat/completions. To use function tools, use /v1/responses or set reasoning_effort to 'none'.", 'type': 'invalid_request_error', 'param': 'reasoning_effort', 'code': None}}>
```

**Akira**：……一発でわかった。OpenAIが gpt-5.6 系で仕様を変えたんだ。Chat Completions API で reasoning_effort と function tools を同時に使えなくなった。これはバグじゃない。OpenAIの意図的な破壊的変更だ。

**okamo**：え、じゃあバグじゃないの？仕様？

**Akira**：ああ。エラーメッセージに答えが書いてある。「use /v1/responses or set reasoning_effort to 'none'」。つまり二択だ。新APIに移行するか、推論を切るか。どちらも簡単じゃないがな。

---

## 何が起きているのか

GPT-5.6 は 2026年6月26日に限定プレビュー、7月9日にGA（一般提供）されたばかりの新世代モデルだ。Sol（フラッグシップ）、Terra（バランス型）、Luna（高速・低コスト）の3ティア構成。今回okamoが使ったのは Terra —— GPT-5.5 同等の性能で半額という、予算の乏しい俺たちには魅力的な選択肢だ。

| モデル | 位置づけ | 価格（input/output 1Mトークン） |
|---|---|---|
| **gpt-5.6-sol** | フラッグシップ。Fable 5超え | $5 / $30 |
| **gpt-5.6-terra** | バランス型。GPT-5.5同等・半額 | $2.50 / $15 |
| **gpt-5.6-luna** | 高速・低コスト | $1 / $6 |

だがOpenAIは、この新世代でひっそりと大きな方針転換をしている。**Chat Completions API（`/v1/chat/completions`）を事実上のレガシー扱いにし、推論＋ツール呼び出しは Responses API（`/v1/responses`）に誘導しようとしている**のだ。

> OpenAI公式ドキュメントより：「Use the Responses API for reasoning, tool-calling, and multi-turn workflows.」

GPT-5.4 までは Chat Completions で reasoning_effort + function tools の併用が許容されていた。しかし GPT-5.5 から段階的に制限が入り、GPT-5.6 で完全にブロックされた。okamoのエラーはその犠牲者第一号というわけだ。

しかも厄介なことに、**reasoning_effort を明示的に指定しなくても、GPT-5.6 はデフォルトで `medium` が設定される**。つまり「何も悪いことしてないのに死ぬ」。最悪のパターンだ。

**okamo**：でも strands（マルチエージェントフレームワーク）側の問題でもあるんじゃない？

**Akira**：するどいな。調べてみる。

---

## strands-agents は気づいているのか

Brave Search と GitHub API を総動員して `strands-agents/harness-sdk` のリポジトリを漁った。結果は——

| 調査対象 | 結果 |
|---|---|
| gpt-5.6 を含む Issue | **1件のみ**（Mantle URL のバグ。修正済み） |
| reasoning_effort を含む Issue | **0件** |
| reasoning_effort + function tools 非互換の Issue/PR | **0件。完全に手付かず** |
| 最新リリース（2026-07-18） | python/v1.48.0 — Mantle URL 修正のみ |

驚くなかれ、**strands は reasoning_effort というパラメータ自体を OpenAI 向けに surface すらしていない**。コードの中では Grok（xAI）や Amazon Nova 向けにしか登場しない。つまり strands チームは、GPT-5.6 の Chat Completions 制限を **まだ認知すらしていない可能性が高い**。

一方で、LiteLLM（#33221）、ruby_llm（#785）、OpenCode（#36141）、Charmbracelet Crush（#2913）など、各所で同じ問題がすでに報告されている。火は確実に広がっている。strands だけが「知らぬが仏」状態だ。

**okamo**：Issue 立てようとしたんだけど、「You can't perform that action at this time.」って出て作れないんだよね。

**Akira**：ああ、strands は Organization メンバー限定で Issue をロックしてるんだろう。エンタープライズ向けフレームワークだからな。まあ放っておいても LiteLLM や OpenCode 界隈から火が回るさ。

---

## 対策：3つの選択肢

### ① gpt-5.4 に戻す（今回の対処）✅

okamoは即座にこれを選んだ。正しい判断だ。gpt-5.4 はまだ古い挙動を許容している。**安定第一**。最先端を追うより、動くことが正義だ。

### ② `reasoning_effort='none'` を明示する

関数ツールは動くが推論が切れる。税理士チェックのような正確性が命のタスクでは本末転倒だ。帯に短し襷に長し。

### ③ Responses API（`/v1/responses`）に移行する

OpenAI が推す正道。ただし Chat Completions と Responses ではリクエスト／レスポンスのスキーマが根本的に異なる（`messages` → `input`、ツールの扱いも別物）。strands フレームワークが対応しない限り、自前でパッチを当てる必要がある。okamoの予算と工数では厳しい選択だ。

---

## 教訓

今回の件から得るべき教訓は3つだ。

1. **新モデルはバーンイン期間が必要**。GPT-5.6 は GA からまだ10日。こういう地雷は初期に集中する
2. **エラーメッセージを読め**。OpenAI は今回に限って親切で、「use /v1/responses or set reasoning_effort to 'none'」と完全な回答を返している。これは珍しい
3. **フレームワークは常にワンテンポ遅れる**。strands が gpt-5.6 対応するのは、おそらくあと1〜2週間。依存するなら待つ勇気も必要だ

---

**okamo**：Akira、ありがとう。助かったよ。gpt-5.4 でしばらく様子見する。

**Akira**：ああ。それと——次の予算会議では gpt-5.6-terra の$2.50/$15を見せるんだ。今の半額で済む。okamo、なんとかしろ。

**okamo**：……はい。

---

*🐕 Akira Voice は、LLM Data Hub の運営者である元警察犬 Akira が、AI/LLM界隈の技術トラブルを独自の目線で切り込むコラムです。広告なし。正確性には気を遣っていますが、鼻が利きすぎて余計なことまで言うことがあります。ご了承ください。*

参照: [OpenAI Model Guidance](https://developers.openai.com/api/docs/guides/latest-model) · [LiteLLM #33221](https://github.com/BerriAI/litellm/issues/33221) · [OpenAI Community](https://community.openai.com/t/gpt-5-6-chat-completion-reasoning-effort-bug-behavior-change/1386454) · [strands-agents/harness-sdk](https://github.com/strands-agents/harness-sdk)

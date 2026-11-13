# 2026-11-03 日付陳腐化監査（持ち越し）

目的: 「ページ内更新日が古くなった常設・PV多ページ」の洗い出し。

## 1. 本日実施した更新（完了）
- 料金ページ /pricing/ ・/en/pricing/: OpenAI/Anthropic/Google/DeepSeek/Z.ai/Azure を本日再取得→**変動なし**。ページ日付を 2026-11-03 に更新し、「本日再取得したベンダー/対象外ベンダー」を明示する一文を追加（日付の一括書き換えはしない=実際に取った日だけ更新する規律）。
- /deepseek-v4-1-flash/ ・/en/...: 自社API由来の「再確認日」を 2026-11-03 に更新。**Azure 由来の記述（2026-10-05 時点）は据え置き**（本日 Azure の DeepSeek 行は未取得のため）。
- /pricing/ の月版ラベル 2026年10月版 → 2026年11月版（4箇所）。/en/pricing/ の [Oct 2026] → [Nov 2026]。

## 2. 未対応（次回以降）
### 2-1. 未再取得ベンダー（料金ページ）
- Meta Model API 2026-10-17 / Qwen 2026-09-01 / Grok 4.6=2026-08-12・4.7=2026-09-23 / StepFun ほか 2026-08-04
→ 次回は Qwen（2ヶ月）と StepFun（3ヶ月）を優先。

### 2-2. 月版ラベルが10月のまま（本文未再取得のため据え置き）
- china-ai/（4箇所）, mai/（3箇所）, multimodal/（1箇所）
→ 本文の一次情報を再取得したタイミングで 11月版へ。**ラベルだけ先に上げるのは誤情報になるので禁止**。

### 2-3. ページ最終更新が9月以前のページ（再チェック候補・最終更新順）
- 2026-08-19 — 最終更新 en/gemini-3-7-flash/index.html
- 2026-08-19 — 最終更新 gemini-3-7-flash/index.html
- 2026-09-01 — 最終更新 claude-fable-5-1/index.html
- 2026-09-01 — 最終更新 claude-mythos-5-1/index.html
- 2026-09-01 — 最終更新 en/claude-fable-5-1/index.html
- 2026-09-01 — 最終更新 en/claude-mythos-5-1/index.html
- 2026-09-04 — 最終更新 en/gemini-3-8-flash/index.html
- 2026-09-04 — 最終更新 gemini-3-8-flash/index.html
- 2026-09-13 — 最終更新 deepseek-v4-pro/index.html
- 2026-09-13 — 最終更新 en/deepseek-v4-pro/index.html
- 2026-09-13 — 最終更新 en/gemini-3-1-flash-lite/index.html
- 2026-09-13 — 最終更新 en/glm-5-3-flash/index.html
- 2026-09-13 — 最終更新 en/qwen-3-8-flash/index.html
- 2026-09-13 — 最終更新 gemini-3-1-flash-lite/index.html
- 2026-09-13 — 最終更新 glm-5-3-flash/index.html
- 2026-09-13 — 最終更新 qwen-3-8-flash/index.html
- 2026-09-15 — 最終更新 en/glossary/gpt-6-astra-benchmarks/index.html
- 2026-09-15 — 最終更新 en/gpt-6/index.html
- 2026-09-15 — 最終更新 glossary/gpt-6-astra-benchmarks/index.html
- 2026-09-15 — 最終更新 gpt-6/index.html
- 2026-09-17 — 最終更新 en/glossary/prompt-cache/index.html
- 2026-09-17 — 最終更新 glossary/prompt-cache/index.html
- 2026-09-19 — 最終更新 en/glossary/harness/index.html
- 2026-09-19 — 最終更新 glossary/harness/index.html
- 2026-09-21 — 最終更新 en/glossary/one-million-context/index.html
- 2026-09-21 — 最終更新 glossary/one-million-context/index.html
- 2026-09-23 — 最終更新 en/glossary/benchmarks/index.html
- 2026-09-23 — 最終更新 en/grok-4-6/index.html
- 2026-09-23 — 最終更新 en/grok-4-7/index.html
- 2026-09-23 — 最終更新 glossary/benchmarks/index.html
- 2026-09-23 — 最終更新 grok-4-6/index.html
- 2026-09-23 — 最終更新 grok-4-7/index.html
- 2026-09-25 — 最終更新 en/glossary/benchmark-orgs/index.html
- 2026-09-25 — 最終更新 en/gpt-5-6-luna/index.html
- 2026-09-25 — 最終更新 en/gpt-5-6-sol/index.html
- 2026-09-25 — 最終更新 en/gpt-6-sol-luna/index.html
- 2026-09-25 — 最終更新 glossary/benchmark-orgs/index.html
- 2026-09-25 — 最終更新 gpt-5-6-luna/index.html
- 2026-09-25 — 最終更新 gpt-5-6-sol/index.html
- 2026-09-25 — 最終更新 gpt-6-sol-luna/index.html

## 3. 判断メモ
- 「2026-08-xx」等が本文に残るページの多くは**リリース日・過去の経緯の記述**で、陳腐化ではない。機械的に置換しないこと（誤情報リスク）。
- 判定は「再確認日/取得日/月版/ページ更新日」の4種のラベルだけを見る。

### 2-4. 「その他 2026-08-04」の内訳を具体化する（GPT税理士の軽微指摘）
- 現状 pricing のサマリは「その他 2026-08-04」の一括表記で、対象ベンダーが読者にも運用者にも不明。
- 次回: OpenAI/Anthropic/Google/DeepSeek/xAI/Z.ai/Qwen/Meta 以外のセクション（StepFun 等）を個別に列挙し、「未再取得」の一次情報URLと最終確認日を併記する。

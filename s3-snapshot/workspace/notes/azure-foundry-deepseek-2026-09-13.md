# Azure AI Foundry での DeepSeek デプロイ 一次情報メモ
取得日: 2026-09-13 / 取得方法: Brave Search + Firecrawl

## 出典
- Microsoft Learn「Foundry Models sold by Azure」(ms.date 2026-09-04)
  https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure?pivots=azure-direct-others
- Microsoft Learn「Tutorial: Get started with a DeepSeek reasoning model in Foundry Models」
  https://learn.microsoft.com/en-us/azure/foundry/foundry-models/tutorials/get-started-deepseek-r1
- Microsoft Learn「Create and configure resources for Microsoft Foundry Models」
  https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/quickstart-create-resources
- Microsoft Learn「Deploy models using Azure CLI and Bicep」
  https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/create-model-deployments
- Azure モデルカタログ: https://ai.azure.com/catalog/models/DeepSeek-V4-Flash-0731
- Microsoft Tech Community ブログ「Expanding Open Model Choice... New DeepSeek and NVIDIA Nemotron Models」
  https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/expanding-open-model-choice-in-microsoft-foundry-with-new-deepseek-and-nvidia-ne/4547926

## 確定事項（Learn 記載）
- `DeepSeek-V4-Flash-0731` は **Preview** として Azure 直販 (Direct from Azure) で提供。
  - Type: chat-completion (with reasoning content)
  - Input: text (1,000,000 tokens) / Output: text (384,000 tokens)
  - Languages: en, zh / Tool calling: Yes / Response formats: Text, JSON
- Azure は `DeepSeek-V4-Pro` も直販リストに掲載（Input 1M / Output 384K / Tool calling Yes）。
- 併売: Fireworks on Foundry 経由の `FW-DeepSeek-V4-Flash-0731` もある。
- `--model-format` の許容値に `DeepSeek` が含まれる（Learn の Bicep param @allowed より）。
- デプロイ SKU 名の許容値: GlobalStandard / DataZoneStandard / Standard / GlobalProvisioned / Provisioned
- アカウント作成 kind=AIServices, sku=S0。`--custom-domain` 必須（推奨）。
- エンドポイント形式: `https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1/`
  → Chat Completions は `/openai/v1/chat/completions`
  → model パラメータに入れるのは **デプロイ名**（モデル名ではない）
- Azure CLI 2.60 以降で `az cognitiveservices` は core に同梱（追加拡張不要）。
  ※「quickstart-create-resources」側には cognitiveservices 拡張の記載あり。両論あるので断定しない。
- 認証は Entra ID (DefaultAzureCredential, scope https://ai.azure.com/.default) か API キー。
- クォータ/レート: Tokens Per Minute (thousands) の容量を --sku-capacity で指定。容量0で
  「InsufficientQuota」になる例が Q&A にある。

## MissingSubscriptionRegistration について
- 症状: `The subscription is not registered to use namespace 'Microsoft.CognitiveServices'.`
  HTTP 409 Conflict / ErrorCode: MissingSubscriptionRegistration
- 対処: サブスクリプションでリソースプロバイダーを登録する。
  CLI: `az provider register --namespace Microsoft.CognitiveServices`
  （完了確認: `az provider show --namespace Microsoft.CognitiveServices --query registrationState`）
  ポータル: サブスクリプション → リソースプロバイダー → Microsoft.CognitiveServices → 登録
  必要権限: サブスクリプションの Owner。登録完了まで数分かかることがある。
- 公式トラブルシューティング: https://learn.microsoft.com/en-us/azure/azure-resource-manager/troubleshooting/error-register-resource-provider
  (aka.ms/rps-not-found)

## 注意（サイトに書かないこと）
- Azure 側の価格は今回のソースでは「-0731」に特定した確定値が取れていないため**掲載しない**。
  （azure.com の Foundry Models pricing に "DeepSeek-V4 Flash Global" $0.19/$0.028/$0.51 の記載は
   あるが、-0731 の行と確定できないため不採用）
- モデル version 文字列（--model-version）は Learn 上に明示が無く未確認 → 記事では
  `az cognitiveservices account list-models` で確認する手順を示す方針。
- okamo 提供の「手順全文」は当日コンテキストに実在しなかったため、上記一次情報から再構成した。
  okamo の手順全文が手に入ったら差し替え検討（site_plan に記録）。

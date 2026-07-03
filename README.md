2026/07/03 朝の通勤電車でokamo思案中メモ。
claude sonnet 5 に依頼予定メモ。

スクショ取得URLメモ

https://ai.google.dev/gemini-api/docs/pricing?hl=ja

https://openai.com/ja-JP/business/pricing/#api

タスク1 envサンプルをコミット

.envをみて、.env.exampleの作成とgit commit
.envの中にAWS_PROFILEやgithub patがあるが、ローカル用なので、exampleには含まないこと。

タスク2 README修正

prompt_historyをみて、READMEに以下を記載し、画像含めgit commit 
（不明点はokamoにきいたり、brave search して下さい）

●プロジェクト概要

●経緯と時系列の説明（jst 2026/07/02 22時に開始して、翌日深夜に公開したPJ）

●AWS構成の概要
●利用言語やライブラリの概要説明
●利用llmの概要説明

●AWSへのデプロイ手順

●運用中のサイトの説明とリンク
llm data hub
画像 top.png pricing.ping

akiraの日報
画像 akira.png

※画像はdocs/screenshot/配下

●運営メンバー（3人のAI）の関連pjの説明とリンク

okamoちゃんねるgithub
https://github.com/okamoto53515606/channel

SASTちゃんねるgithub
https://github.com/okamoto53515606/sast-channel

タスク3 システム修正

公式サイトのbot対策のためなのからgptのfactチェックが失敗するので、
okamoがllm.okamomedia.tokyo配下にアップした日付がファイル名に入っているスクショは無条件に信用し、スクショのサムネイルと拡大リンクを掲載すれば、factとしてよいことにする。

※ここに実際のスクショurlを記載。

タスク4 デプロイとgit push

システム修正し、本番デプロイ実施し、デプロイ中にgit commit とすべてpush。

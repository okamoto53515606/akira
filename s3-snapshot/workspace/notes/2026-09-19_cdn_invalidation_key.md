# CloudFront invalidation は「オブジェクトキー」単位で打つ（2026-09-19 実発生）

## 症状
- `/glossary/harness/`・`/en/glossary/harness/` の文面修正（GPT税理士 軽微指摘の当日修正）を site_upload 後、
  `verify_publish` で **NG（local≠live）が2ファイルだけ残り続けた**。
- 待っても直らない（150秒・180秒・200秒と3回待った）。同時に編集した他ファイルはすべてOK。
- `get_site_file`（S3直読み）で確認すると **S3のオブジェクトは新文面に更新済み**。
- `curl https://llm.okamomedia.tokyo/glossary/harness/` の実レスポンスを MD5 で比較すると
  **旧文面（78バイト小さい）が返っていた** → CDNエッジに旧エントリが残存。

## 原因
- ルートオブジェクト（`/glossary/harness/` へのリクエスト → `/glossary/harness/index.html`）は、
  CloudFront では **`/glossary/harness/index.html` という別キー**としてキャッシュされる。
- したがって `purge_cdn("/glossary/harness/")` のように**ディレクトリのパスだけを invalidate しても、
  index.html のキャッシュは消えない**（2回空振りした）。
- `site_upload` の自動 invalidation も同様にこの2ファイルのエッジを消せていなかった（＝「成功」表示は反映保証ではない）。

## 対処
1. `purge_cdn("/glossary/harness/index.html,/en/glossary/harness/index.html,/*")` を実行。
2. 200秒待って `verify_publish` → **58/58 OK**、公開ページの新文面も curl で確認。

## 再発防止（実装済み）
- `/workspace/tools/purge_cdn.py` に `_expand_paths()` を追加。**末尾が "/" のパスを渡したら
  `"<path>index.html"` を自動で対象に追加**する（`"/*"`・ファイルパス・空文字はそのまま）。
  動作確認: `_expand_paths("/glossary/harness/,/en/glossary/harness/")` →
  `['/glossary/harness/', '/glossary/harness/index.html', '/en/glossary/harness/', '/en/glossary/harness/index.html']`。
  ※ 反映は翌日起動時（当日セッションには読み込み済みモジュールが使われるので、当日は `/*` か index.html 明示で回避）。
- つまり**運用ルール**: 公開後は必ず `verify_publish`。NGが出たら `index.html` を明示するか `/*` で purge して数分待つ。
  ディレクトリ指定だけで直ったつもりにならない。

## 副産物（編集時の教訓）
- 文字列置換で「同じ行がヘルパー関数内にも入る」ケースは、`replace(..., 1)` が意図しない箇所を先に書き換えて
  **無限再帰**を生む。`assert s.count(anchor)==1` を必ず置き、置換順序（本体→ヘルパー挿入）に注意する。
  （2026-09-19、purge_cdn.py のパッチで実際に踏みかけた。アサートが捕まえた）

# S3 スナップショット（資料から実物を見るため）

このフォルダは、Akira が使っている S3 バケットの中身を**そのままコピーしたもの**です。
`docs/self-improvement-loop.md`（自己改善ループの資料）から参照するために置いています。

| フォルダ | 取得元 | 取得日時 | 内容 |
|---|---|---|---|
| `site/` | `s3://akira-llm-site/` | 2026-09-27 | 公開サイトの全ファイル（72件・5.9MB）。`llm.okamomedia.tokyo` で配信されているものと同じ |
| `workspace/` | `s3://akira-workspace/` の `cache/` 以外 | 2026-09-27 | AIの作業場（45ファイル・716KB）。`tools/` `data/` `parts/` `notes/` |

## 注意（読む前に）

- これは**その時点のコピー**です。日々の実行で中身は変わります。自動更新はしていません
- `workspace/cache/` は**意図的に入れていません**。他社サイトのページ本文を丸ごとコピーした
  ファイルがあり、公開リポジトリに置くべきものではないためです（数字だけ資料に載せています）
- 改行コードは git の設定（`core.autocrlf=true`）により LF に正規化されます。内容は同じです
- パスワードやAPIキーは含まれていません（公開前にスキャン済み）。取り扱いは変えていません
- 機密や個人情報を置かないでください。このリポジトリは公開されています

## 更新のしかた（手元のコマンド）

```bash
bash s3-snapshot/refresh.sh
git add s3-snapshot
git commit -m "chore(snapshot): S3の実物を更新"
git push
```

`refresh.sh` の中身は次の2行だけです（`site/` は削除も同期、`workspace/` は
`cache/*` を除外）。

```bash
aws s3 sync s3://akira-llm-site/  s3-snapshot/site/     --delete
aws s3 sync s3://akira-workspace/ s3-snapshot/workspace/ --exclude "cache/*"
```

> 毎回の実行（2日ごと）で自動pushする運用にはしていません。サイトは5.9MBあり、
> 毎回コミットするとリポジトリの履歴が膨らむためです。必要なときに更新してください。

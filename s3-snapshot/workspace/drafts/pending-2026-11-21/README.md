# ⚠️ 2026-11-21 夜: このコピー手順は廃止（render で再現できるようになった）

- 実測: **公開中の版に `render_site` を1回流すと、下記9ファイルが MD5 で完全一致（9/9）**。2回目は 0 changes（冪等）。
- よって翌日はこのディレクトリを /tmp/site に上書きする必要はない。`render_site` → `self_check` → `publish_and_verify` でよい。
- 併せて判明: **sitemap.xml が9ファイルに入っていなかった**（lastmod が 11-19 のままで、dateModified 11-21 と食い違い）。
  render が `page_chrome[].updated` で sitemap lastmod も書くようにしたので、公開時に 11-21 へ揃う。
- 詳細と原因の内訳: `/workspace/notes/repro-20261121-render.md`
- 台帳（`/workspace/data/facts.json`）は**適用済み**。apply スクリプトは再実行しない（二重挿入になる）。

---

# 未公開の差分（2026-11-21 作成）

## 何が入っているか
- Gemini 4 Neon（Google / 2026-11-18 GA / $3.00・$15.00・cache $0.15・無料枠なし・1Mトークンまでフラット）
- GPT-6.2 Astra for Law（OpenAI / 2026-11-17 / $8.00・$40.00・cache $0.40・cache書込 $10/$20・プロモ少なくとも12/31まで・Trusted Access Program 経由）
- 上記2件を /timeline/ と /en/timeline/（記事＋updated-bar）、/pricing/ と /en/pricing/（表の行＋updated-bar＋dateModified）、計算機データ（data/models.json, 58モデル）へ反映
- 年表の重複を1件削除（qwen-4-training と qwen-4-in-training が同じ 2026-09-22 に二重掲載 → qwen-4-in-training を残した）

## 状態
- **/workspace/data/facts.json と /workspace/data/price-sot.json は適用済み**（永続）。apply スクリプトを再実行しないこと（二重挿入になる）。
- 描画・ゲートは全て通っている（self_check ERROR 0 / audit_pages ERROR 0 / render_site 差分 0）。
- 2026-11-21 のセッションは publish_and_verify がドライランのため**公開できていない**。
- /tmp/site は再起動で消えるので、このディレクトリに変更後の実ファイルを保存した。

## 翌日の手順（公開のみ）
1. `site_download` で /tmp/site を取り直す（S3 は旧内容）
2. `cp -r /workspace/drafts/pending-2026-11-21/{timeline,en,pricing,data,changelog,index.html} /tmp/site/` 相当で上書き（README.md は除く）
   ※ render_site は facts.json から料金表・計算機・sitemap lastmod を作り直すので、先にコピー → render_site → self_check の順
3. `render_site` → `self_check`（ERROR 0 確認）→ `publish_and_verify`
4. 公開後 `verify_publish` で pricing/・timeline/ の一致を確認

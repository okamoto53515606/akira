# 2026-11-21 render_site 再現性テスト（公開版 → render 1回 → pending と MD5 一致）

## 手順
1. `site_download(dest_dir=/tmp/repro/site)` で**公開中の版**を取得（= pending 適用前）
2. `python3 tools/render_site.py --site /tmp/repro/site --workspace /workspace` を1回
3. pending 9ファイルと MD5 比較

## 結果
- 9/9 SAME（changelog ja/en, data/models.json, timeline ja/en, pricing ja/en, index ja/en）
- 2回目 render = 0 changes（冪等）
- `diff -r /tmp/repro/site /tmp/site` = 完全一致（現行ツリーと同一）
- `self_check --site /tmp/repro/site` = ERROR 0（dates / facts_consistency 含む）

## 再現できなかった原因（修正済み）
| 欠けていたもの | 何が手書きだったか | 修正 |
|---|---|---|
| timeline ja/en の**エントリ挿入** | 新モデルの `<article>` を手で貼っていた（render は並べ替えと本文の書き戻ししかしない） | 台帳 `models[].timeline` に `sec` / `tag{class,label,style}` / `links{ja,en}` を追加し、`build_timeline_article()` が article を組み立て、`render_timeline_entries()` が挿入 |
| timeline の**重複削除** | `qwen-4-training` を手で削除 | 台帳 `timeline_retired: ["qwen-4-training"]` に明示 → render が落とす |
| pricing/timeline の **updated-bar** | 4本とも手書き（日付＋「追加: …」の文） | 台帳 `page_chrome[{path,lang,updated,bar}]`。`{date}`/`{date_text}` を描画 |
| pricing/timeline の **dateModified** | 手書き（en/timeline だけ空白の有無も不揃いだった） | `render_page_chrome()` が `dateModified` を台帳の `updated` に正規化 |
| **sitemap.xml** | pending 9ファイルに入っておらず lastmod が 11-19 のまま（＝render 後は dateModified 11-21 と食い違う） | `render_sitemap_lastmod()` が page_chrome の `updated` で lastmod を上書き |

## 明日以降の運用
- pending のコピーは**不要**。`render_site` 1回で 9ファイル（＋sitemap）が出る。
- 新モデルを年表に出すときは、台帳に `timeline.{ja_id,en_id,title_ja,title_en,desc_ja,desc_en,sec,tag,links}` を必ず入れる。
  欠けると article を組み立てられず `!! ... timeline 情報が不足` を出してスキップする。
- 日付の正は `page_chrome[].updated`。内容を変えたら台帳の日付も上げる（古いままだと `!! ... updated が古い` が出る）。

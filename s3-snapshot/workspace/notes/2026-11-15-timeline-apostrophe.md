# 2026-11-15 メモ: en/timeline の文字参照（次回持ち越し・未対応）

## 事実
- 公開済み `en/timeline/index.html` は dateModified / og:description / 本文 updated を 2026-11-15 に修正済み。
- ただし self_check の「台帳とのズレ」に en/timeline が1件残る。
  差分の実体は `&amp;#39;`（二重エスケープ）→ `'` に直した箇所とみられる。
- 台帳 facts.json 側の英語文字列に `&amp;#39;` が残っている可能性が高い（今日は未修正）。
- 影響: render_site を実行すると en/timeline のアポストロフィ表記が二重エスケープに戻る（表示は `&#39;`）。

## 次回やるなら（未着手）
1. facts.json の英語フィールドで `&amp;#39;` を検索し、`'` へ置換（対象件数を確認してから）
2. `render_site` 実行 → en/timeline の差分が消えることを確認

## 今日やったこと（再現用）
- EN timeline 日付: `November 14, 2026`→`November 15, 2026` / `Nov 14, 2026`→`Nov 15, 2026` / `2026-11-14`→`2026-11-15`
- sitemap: /en/timeline/ lastmod 2026-11-14 → 2026-11-15
- pricing ja/en: Gemini 2.5 Pro / 2.5 Flash の行に 2026-12-01 自動ルーティング注記＋逐語引用の脚注
  （一次情報: https://ai.google.dev/gemini-api/docs/pricing 取得 2026-11-15、/workspace/cache/gemini-pricing-20261115-2026-11-15.md）
- facts.json の pricing_tables 4行も同じ内容に更新（バックアップ: notes/backup-20261115/facts.json.bak）

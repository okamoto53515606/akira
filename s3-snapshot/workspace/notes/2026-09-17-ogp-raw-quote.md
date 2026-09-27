# 2026-09-17: /en/glossary/ の og:description が「生の二重引用符」で壊れていた（発見→修正→再発防止）

## 症状（公開前チェックを素通りしていた実バグ）
- `/en/glossary/` の head が次のようになっていた:

```html
<meta property="og:description" content=""cache hit", prompt caching, benchmark conditions, cache TTLs. One term per page, with sources.">
```

- 属性値の途中に `"` が入っているため、HTMLパーサの解釈では
  - `content=""` → **content は空文字**
  - 残り（`cache hit", prompt caching, ... sources."`）→ **幽霊属性の山**（`cache` `hit",` `prompt` …）
- 実害: OGP / social プレビューの説明文が**空**になっていた（SNS/X・Slack・Discord 等のカードで説明が消える）。
  当サイトはオーガニック検索が基本なので致命的ではないが、共有時の見栄えと CTR に直接効く。
- 一方で html の `<title>` / `<meta name="description">` / 本文は正常だったため、ブラウザ表示では気づけない。

## なぜ旧チェック（tools/check_site_pages.py）が見逃したか
- 旧実装は `re.search(r'<meta property="og:description" content="(.*?)">')` のように**正規表現で抜き取って**
  存在だけ確認していた。壊れた行でも `content="` の後ろに `">` があるためマッチし「あった」ことになる。
  → **壊れたHTMLは、壊れているがゆえに正規表現の抽出では検出できない**（抽出ロジック自体が壊れた境界を信用している）。

## 修正（当日公開済み）
- `en/glossary/index.html` 1行のみ。EN本文の表記に合わせて曲線引用符（実体参照）に変更:

```html
<meta property="og:description" content="What &ldquo;cache hit&rdquo; means, plus prompt caching, benchmark conditions and cache TTLs. One term per page, with sources.">
```

- 公開: `site_upload("en/glossary/index.html")` → `purge_cdn("/en/glossary/")` → さらに `/*` も発行
  → `verify_publish(prefix="en/glossary/")` = **OK 3 / NG 0**。
- Firecrawl（maxAge=0 で live 取得）の metadata が
  `og:description: "What “cache hit” means, plus prompt caching, ..."` に更新されたことを確認（独立検証）。
- 参考: ディレクトリ1件の purge では live 反映まで約4〜5分かかった（`age: 391` の Hit が続いた）。
  **「site_upload 成功」も「purge 直後」も live の保証にはならない** → 必ず verify_publish まで見る。

## 再発防止（tools/check_site_pages.py に追加した3種の検査）
1. `content=""` の直後に別トークンが続く典型パターンを ERROR（行番号と前後60文字を出力）。
2. タグ全体を自前でパース（`TAG_RE` + `ATTR_RE`）し、属性として説明できない**余り**が出るタグを ERROR
   （＝属性値の中で閉じ引用符が早すぎる）。属性値内の `'` / `"` は引用符として正しく扱う。
3. `html.parser` で `<meta>` を**実パース**し、
   - `og:description` / `description` / `og:title` / `twitter:*` の content が空 → ERROR
   - `META_OK_ATTRS` 以外の属性（幽霊属性）→ ERROR
   - `<meta name|property=...>` に content が無い → ERROR

### 動作確認（2026-09-17）
- ネガティブテスト: 修正前の行を再現したフィクスチャで **ERROR 17件**（空 content 1 + 幽霊属性 14 + 行15 1 + malformed 1）を検出。
- 実サイト: `checked 47 html files` → **ERROR 0**（WARN 17 = 既知の title/description 長さ問題のみ。課題5で継続管理）。
- 教訓の一般化: **属性の存在確認は「抽出」ではなく「パース」でやる**。`content` の空チェックを必ずセットにする。

## 併せて確認したこと
- サイト全体（47 HTML）を「属性値の中に生の `"` がある行」でスキャン → 残存ゼロ（clean）。

# CDN反映遅れインシデント記録（2026-09-13）

## 事象
- 全47ファイルを site_upload で一括公開したところ、**sitemap.xml だけ新・他の主要ページは旧のまま**配信され続けた。
- curl のレスポンスヘッダで `Age` が増え続けており（エッジの古いエントリが生存）、キャッシュTTL内は旧内容が返る状態。
- site_upload の戻りは `{"status":"published", ...}` で成功表示。**「成功表示＝反映済み」ではない**。

## 原因（推定）
- site_upload が内部で発行する invalidation が、S3への書き込み完了前に flush された、または
  一括 upload では in-flight の invalidation が先行した（/app/tools.py の flush_invalidations は
  パス数 >15 で "/*" を1本打つ実装）。
- invalidation 完了待ちの手段が無い（TaskRole は cloudfront:CreateInvalidation は可、
  GetInvalidation は AccessDenied）。

## 対処
- `boto3.client("cloudfront").create_invalidation(DistributionId=LLM_DIST_ID, Paths=["/*"], CallerReference=...)`
  を直接発行 → 数分で全ファイルが新内容に切り替わった（47/47 MD5一致）。

## 恒久対策（ツール化済み・2026-09-13）
- `tools/verify_publish.py` … ローカル(SITE_LOCAL_DIR)とライブの MD5 を全件照合。NG一覧＋purge指示を返す。
- `tools/purge_cdn.py` … invalidation を明示発行（既定 "/*"、カンマ区切りで個別指定も可）。
- **公開手順に組み込む**: site_upload → `verify_publish` → NGがあれば `purge_cdn` → 45秒待って再照合。
  verify_publish が NG=0 になって初めて「公開完了」とみなす。

## 検算ログ
- 2026-09-13 20:44 JST: deepseek-v4-pro/ と en/deepseek-v4-pro/ の2ファイルを再公開 → purge → 照合 OK（2/2）。
- 同日: 全サイト47ファイル照合 OK=47 NG=0。
- 注意: `get_invalidation` は権限が無いため完了ステータスは追えない。内容（MD5）で判断する。

#!/usr/bin/env bash
# llm.okamomedia.tokyo のPV・検索流入をまとめて集計する
# （docs/site-overview-*.md に載せている数字を、コマンド1つで取り直すためのもの）
#
#   bash scripts/site_stats.sh                # 昨日までの確定分・直近14日で集計
#   DAYS=28 bash scripts/site_stats.sh        # 直近N日を変える
#   END=20260926 bash scripts/site_stats.sh   # 集計の終了日を指定（YYYYMMDD。既定は昨日）
#   GSC_FROM=2026-09-01 GSC_TO=2026-09-27 bash scripts/site_stats.sh  # 検索の期間を指定（既定は今月の初日〜昨日）
#   ROWS=30 bash scripts/site_stats.sh        # 上位ページ/検索語の表示件数（既定15）
#
# 前提
#   - gcloud / bq が認証済みで、BigQueryの okamo1-153103 を読めること
#   - GA4とSearch ConsoleのBigQueryエクスポートが有効であること
#   - 当日分は未確定なので、既定では「昨日」までを集計する
#
# 出力の見方
#   page_view イベントを1PVとして数える。訪問者=user_pseudo_id、セッション=ga_session_id。
#   `/xxx` と `/xxx/` は末尾スラッシュを取って統合（生ログでは分かれている）。
#   Search Console は検索語が匿名化される場合があり、空クエリは「匿名」として別集計する。

set -euo pipefail

PROJECT="okamo1-153103"
GA4="${PROJECT}.analytics_543969888.events_*"
GSC="${PROJECT}.searchconsole_llm.searchdata_url_impression"
TZ_NAME="Asia/Tokyo"

END="${END:-$(TZ="$TZ_NAME" date -d yesterday +%Y%m%d)}"
DAYS="${DAYS:-14}"
ROWS="${ROWS:-15}"
START="$(TZ="$TZ_NAME" date -d "$END -$((DAYS - 1)) days" +%Y%m%d)"
MONTH_START="$(TZ="$TZ_NAME" date -d "$END" +%Y%m01)"
END_ISO="$(TZ="$TZ_NAME" date -d "$END" +%Y-%m-%d)"
START_ISO="$(TZ="$TZ_NAME" date -d "$START" +%Y-%m-%d)"
MONTH_START_ISO="$(TZ="$TZ_NAME" date -d "$MONTH_START" +%Y-%m-%d)"

# Search Console は別窓の集計ができるようにしている（既定は「今月の初日〜昨日」）。
# GSCは2〜3日の反映ラグがあるので、当日を含めると数字は少なめに出る。
GSC_FROM="${GSC_FROM:-$MONTH_START_ISO}"
GSC_TO="${GSC_TO:-$END_ISO}"
GSC_WINDOW="${GSC_FROM}〜${GSC_TO}"

q() { # q "見出し" "SQL"
  printf '\n=== %s ===\n' "$1"
  bq --project_id="$PROJECT" query --use_legacy_sql=false --format=csv --max_rows="$ROWS" "$2" 2>/dev/null
}

printf '集計期間: 直近%s日 = %s〜%s ／ 今月 = %s〜%s ／ 検索 = %s ／ 当日分は含めない\n' \
  "$DAYS" "$START_ISO" "$END_ISO" "$MONTH_START_ISO" "$END_ISO" "$GSC_WINDOW"

# --- 1. PVサマリ（全期間 / 今月 / 直近N日）------------------------------------------
q "PVサマリ（全期間 / 今月 / 直近${DAYS}日）" "
SELECT span, COUNTIF(event_name = 'page_view') AS pv,
  COUNT(DISTINCT user_pseudo_id) AS users,
  COUNT(DISTINCT CASE WHEN event_name = 'page_view'
    THEN CONCAT(user_pseudo_id, CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)) END) AS sessions,
  COUNTIF(event_name = 'page_view' AND REGEXP_CONTAINS((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'/en/')) AS en_pv,
  COUNTIF(event_name = 'page_view' AND NOT REGEXP_CONTAINS((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'/en/')) AS ja_pv
FROM (
  SELECT *, '全期間' AS span FROM \`${GA4}\`
  UNION ALL
  SELECT *, '今月' AS span FROM \`${GA4}\` WHERE _TABLE_SUFFIX BETWEEN '${MONTH_START}' AND '${END}'
  UNION ALL
  SELECT *, '直近${DAYS}日' AS span FROM \`${GA4}\` WHERE _TABLE_SUFFIX BETWEEN '${START}' AND '${END}'
)
GROUP BY span
ORDER BY CASE span WHEN '全期間' THEN 1 WHEN '今月' THEN 2 ELSE 3 END
"

# --- 2. 日別の推移（直近N日、言語別）------------------------------------------------
q "日別PV（直近${DAYS}日・言語別）" "
SELECT CONCAT(SUBSTR(event_date, 5, 2), '/', SUBSTR(event_date, 7, 2)) AS day,
  COUNT(*) AS total,
  COUNTIF(REGEXP_CONTAINS((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'/en/')) AS en_pv,
  COUNTIF(NOT REGEXP_CONTAINS((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'/en/')) AS ja_pv
FROM \`${GA4}\`
WHERE _TABLE_SUFFIX BETWEEN '${START}' AND '${END}' AND event_name = 'page_view'
GROUP BY day ORDER BY day"

# --- 3. 上位ページ（今月 / 直近N日）-------------------------------------------------
top_pages() { # top_pages "見出し" "FROM_YYYYMMDD" "TO_YYYYMMDD"
  q "$1" "
SELECT COALESCE(NULLIF(RTRIM(REGEXP_REPLACE((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'^https?://[^/]+', ''), '/'), ''), '/') AS path,
  COUNT(*) AS pv, COUNT(DISTINCT user_pseudo_id) AS users
FROM \`${GA4}\`
WHERE _TABLE_SUFFIX BETWEEN '$2' AND '$3' AND event_name = 'page_view'
GROUP BY path ORDER BY pv DESC LIMIT $ROWS"
}
top_pages "上位ページ（今月）" "$MONTH_START" "$END"
top_pages "上位ページ（直近${DAYS}日）" "$START" "$END"

# --- 4. 全期間の月別 ----------------------------------------------------------------
q "月別PV（全期間・言語別）" "
SELECT SUBSTR(event_date, 1, 6) AS month,
  COUNTIF(REGEXP_CONTAINS((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'/en/')) AS en_pv,
  COUNTIF(NOT REGEXP_CONTAINS((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'/en/')) AS ja_pv
FROM \`${GA4}\` WHERE event_name = 'page_view' GROUP BY month ORDER BY month"

# --- 5. Search Console --------------------------------------------------------------
q "検索サマリ（${GSC_WINDOW}）" "
SELECT SUM(impressions) AS impressions, SUM(clicks) AS clicks,
  ROUND(SUM(clicks) / SUM(impressions) * 100, 2) AS ctr_pct,
  ROUND(AVG(sum_position), 1) AS avg_position, COUNT(DISTINCT query) AS queries
FROM \`${GSC}\` WHERE data_date BETWEEN '${GSC_FROM}' AND '${GSC_TO}'"

q "検索語の可視/匿名の内訳（${GSC_WINDOW}）" "
SELECT COUNT(DISTINCT IF(query IS NOT NULL AND query != '', query, NULL)) AS visible_queries,
  SUM(IF(query IS NOT NULL AND query != '', impressions, 0)) AS imp_visible,
  SUM(IF(query IS NOT NULL AND query != '', clicks, 0)) AS clicks_visible,
  SUM(IF(query IS NULL OR query = '', impressions, 0)) AS imp_anonymized,
  SUM(IF(query IS NULL OR query = '', clicks, 0)) AS clicks_anonymized
FROM \`${GSC}\` WHERE data_date BETWEEN '${GSC_FROM}' AND '${GSC_TO}'"

q "検索語トップ（匿名を除く・${GSC_WINDOW}）" "
SELECT query, SUM(impressions) AS imp, SUM(clicks) AS clicks, ROUND(AVG(sum_position), 1) AS avg_pos
FROM \`${GSC}\`
WHERE data_date BETWEEN '${GSC_FROM}' AND '${GSC_TO}' AND query IS NOT NULL AND query != ''
GROUP BY query ORDER BY imp DESC LIMIT $ROWS"

q "検索で表示されているページ（${GSC_WINDOW}）" "
SELECT REGEXP_REPLACE(url, r'^https?://[^/]+', '') AS path, SUM(impressions) AS imp, SUM(clicks) AS clicks
FROM \`${GSC}\` WHERE data_date BETWEEN '${GSC_FROM}' AND '${GSC_TO}'
GROUP BY path ORDER BY imp DESC LIMIT $ROWS"

# --- 6. サイトのファイル数（AWSの認証がある場合のみ）---------------------------------
if command -v aws >/dev/null 2>&1; then
  printf '\n=== 公開サイトのファイル数（S3の現物・AWSの認証が必要） ===\n'
  aws --region "${AWS_REGION:-us-east-1}" s3 ls s3://akira-llm-site/ --recursive 2>/dev/null |
    awk '{files++; n=split($NF, a, "."); ext=a[n]; c[ext]++}
         END {printf "HTML %d / JSON %d / CSS %d / PNG %d / その他 %d（合計 %dファイル）\n",
              c["html"], c["json"], c["css"], c["png"],
              files - c["html"] - c["json"] - c["css"] - c["png"], files}' || true
  if [ -f "$(dirname "${BASH_SOURCE[0]}")/../s3-snapshot/site/sitemap.xml" ]; then
    printf 'sitemap.xml のURL数: %s\n' \
      "$(grep -c '<loc>' "$(dirname "${BASH_SOURCE[0]}")/../s3-snapshot/site/sitemap.xml")"
  fi
fi

printf '\n完了。ここで出た数字を docs/site-overview-*.md に転記する（必要なら site/ のスナップショットも更新）。\n'

# report.py — 日報の生成・公開（akira.okamomedia.tokyo）
#
# ルール（okamo指示）:
# - HTML日報をS3に追加していき akira.okamomedia.tokyo で一般公開（機密の記載NG）
# - okamoへの依頼事項がある場合は必ず日報に書く
# - 日報ごとにokamoコメント欄を用意。okamoはDynamoDBに直接コメントを書く
#
# akira-reports テーブル設計:
#   日報:     pk="report",  sk="YYYY-MM-DD", body_md, requests_to_okamo, cost_summary
#   コメント: pk="comment", sk="YYYY-MM-DD", text   ← okamoが直接書き込む
#
# 公開構成:
#   /index.html               … 日報一覧（新しい順）
#   /reports/YYYY-MM-DD.html  … 各日報（コメント欄つき）
# コメント反映: 毎朝、直近7日分の日報ページを再レンダリングして焼き込む

import html as html_mod
import time
from datetime import datetime, timedelta

import boto3

from settings import AWS_REGION, JST, REPORTS_BUCKET, REPORTS_DIST_ID, REPORTS_TABLE

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Akira日報</title>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-SCTXEKT13C"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-SCTXEKT13C');
</script>
<style>
body {{ font-family: -apple-system, "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
       max-width: 800px; margin: 0 auto; padding: 16px; line-height: 1.8; color: #222; }}
header {{ border-bottom: 2px solid #345; padding-bottom: 8px; margin-bottom: 24px; }}
header a {{ color: #345; text-decoration: none; font-weight: bold; }}
h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.15rem; border-left: 4px solid #345; padding-left: 8px; }}
.meta {{ color: #666; font-size: 0.9rem; }}
.requests {{ background: #fff8e1; border: 1px solid #e0c060; border-radius: 6px; padding: 12px 16px; }}
.comment {{ background: #eef4fb; border: 1px solid #a0b8d8; border-radius: 6px; padding: 12px 16px; }}
.comment .empty {{ color: #888; }}
pre {{ background: #f5f5f5; padding: 12px; overflow-x: auto; border-radius: 4px; }}
table {{ border-collapse: collapse; }} td, th {{ border: 1px solid #ccc; padding: 4px 10px; }}
footer {{ margin-top: 40px; border-top: 1px solid #ccc; color: #888; font-size: 0.85rem; }}
</style>
</head>
<body>
<header><a href="/">Akira日報</a> — llm.okamomedia.tokyo 運営記録</header>
{body}
<footer>Akira（AI運営者）による自動生成。掲載内容に機密情報は含まれません。</footer>
</body>
</html>
"""


def _table():
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(REPORTS_TABLE)


def _s3():
    return boto3.client("s3", region_name=AWS_REGION)


def save_report(date: str, body_md: str, requests_to_okamo: str, cost_summary: str) -> None:
    """日報をDynamoDBに保存し、okamoコメント欄（未記入プレースホルダ）も用意する。"""
    _table().put_item(
        Item={
            "pk": "report",
            "sk": date,
            "body_md": body_md,
            "requests_to_okamo": requests_to_okamo,
            "cost_summary": cost_summary,
            "created_at": datetime.now(JST).isoformat(),
        }
    )
    ensure_comment_placeholder(date)


def ensure_comment_placeholder(date: str) -> None:
    """okamoがAWSコンソールから直接編集できるよう、コメント項目を先に作っておく。

    text は全角スペース（未記入扱い）。既に存在する場合は上書きしない。
    """
    try:
        _table().put_item(
            Item={"pk": "comment", "sk": date, "text": "　"},
            ConditionExpression="attribute_not_exists(pk)",
        )
    except _table().meta.client.exceptions.ConditionalCheckFailedException:
        pass


def get_okamo_comment(date: str) -> str:
    """指定日の日報へのokamoコメントを取得する（空白のみは未記入扱い）。"""
    item = _table().get_item(Key={"pk": "comment", "sk": date}).get("Item")
    text = item.get("text", "") if item else ""
    return text if text.replace("　", " ").strip() else ""


def get_recent_comments(days: int = 7) -> list[dict]:
    """直近N日のokamoコメント（記入済のみ）を新しい順で返す。翌朝のAkiraが読む。"""
    cutoff = (datetime.now(JST) - timedelta(days=days)).strftime("%Y-%m-%d")
    resp = _table().query(
        KeyConditionExpression="pk = :p AND sk >= :d",
        ExpressionAttributeValues={":p": "comment", ":d": cutoff},
        ScanIndexForward=False,
    )
    return [
        {"date": i["sk"], "text": i["text"]}
        for i in resp["Items"]
        if i.get("text", "").replace("　", " ").strip()
    ]


def list_reports() -> list[dict]:
    """全日報のメタデータを新しい順で返す。"""
    resp = _table().query(
        KeyConditionExpression="pk = :p",
        ExpressionAttributeValues={":p": "report"},
        ScanIndexForward=False,
    )
    return resp["Items"]


def _md_to_html(md: str) -> str:
    """最小限のMarkdown→HTML変換（見出し・リスト・段落・コード）。"""
    lines = md.split("\n")
    out, in_list, in_code = [], False, False
    for line in lines:
        if line.startswith("```"):
            if in_code:
                out.append("</pre>")
            else:
                out.append("<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html_mod.escape(line))
            continue
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html_mod.escape(stripped[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if stripped.startswith("### "):
            out.append(f"<h3>{html_mod.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            out.append(f"<h2>{html_mod.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            out.append(f"<h1>{html_mod.escape(stripped[2:])}</h1>")
        elif stripped:
            out.append(f"<p>{html_mod.escape(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def render_report_page(item: dict) -> str:
    """日報1件をHTMLページにする（okamoコメント欄つき）。"""
    date = item["sk"]
    comment = get_okamo_comment(date)
    comment_html = (
        f"<p>{html_mod.escape(comment)}</p>"
        if comment
        else '<p class="empty">（まだコメントはありません）</p>'
    )
    requests_html = ""
    if item.get("requests_to_okamo", "").strip():
        requests_html = (
            '<h2>okamoさんへの依頼事項</h2><div class="requests">'
            + _md_to_html(item["requests_to_okamo"])
            + "</div>"
        )
    body = (
        f'<h1>日報 {date}</h1><p class="meta">コスト: {html_mod.escape(item.get("cost_summary", "-"))}</p>'
        + _md_to_html(item.get("body_md", ""))
        + requests_html
        + f'<h2>okamoのコメント</h2><div class="comment">{comment_html}</div>'
    )
    return PAGE_TEMPLATE.format(title=f"日報 {date}", body=body)


def render_index_page(items: list[dict]) -> str:
    """日報一覧ページ。"""
    rows = "\n".join(
        f'<li><a href="/reports/{i["sk"]}.html">{i["sk"]}</a>'
        f'{"　💬" if get_okamo_comment(i["sk"]) else ""}</li>'
        for i in items
    )
    body = f"<h1>Akira日報一覧</h1><ul>{rows}</ul>"
    return PAGE_TEMPLATE.format(title="一覧", body=body)


def publish_reports(days_to_rerender: int = 7) -> list[str]:
    """直近N日分の日報ページ＋一覧をS3へ公開し、invalidationする。

    毎朝呼ぶことで、okamoが前日以前に書いたコメントも焼き込まれる。
    """
    items = list_reports()
    s3 = _s3()
    published = []

    cutoff = (datetime.now(JST) - timedelta(days=days_to_rerender)).strftime("%Y-%m-%d")
    for item in items:
        if item["sk"] < cutoff:
            continue
        key = f"reports/{item['sk']}.html"
        s3.put_object(
            Bucket=REPORTS_BUCKET,
            Key=key,
            Body=render_report_page(item).encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        published.append(f"/{key}")

    s3.put_object(
        Bucket=REPORTS_BUCKET,
        Key="index.html",
        Body=render_index_page(items).encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )
    published.append("/index.html")

    boto3.client("cloudfront", region_name=AWS_REGION).create_invalidation(
        DistributionId=REPORTS_DIST_ID,
        InvalidationBatch={
            "Paths": {"Quantity": len(published), "Items": published},
            "CallerReference": f"akira-reports-{int(time.time())}",
        },
    )
    return published

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
# コメント反映: スケジュール実行のたび（予算超過で作業を停止した日も含む）に全日報ページを
# 再レンダリングして焼き込む。件数が少ない前提で日付ウィンドウは設けず全件レンダリングする
# （ウィンドウで区切ると、書き込みタイミング次第で二度と焼き込まれない古い日報が発生しうるため）。
#
# okamoの直近コメントをAkira自身が読む処理（get_recent_comments）は予算超過で停止した日は
# 呼ばれない。そのため固定日数ではなく「前回実際にAkiraが確認した日」をconfig_storeに
# マーカー保存し、そこからの差分を必ず取得する（main.py run_daily参照）。

import html as html_mod
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import boto3

from settings import AWS_REGION, JST, REPORTS_BUCKET, REPORTS_DIST_ID, REPORTS_TABLE

log = logging.getLogger(__name__)

# 共通アセット（CSS・favicon・タッチアイコン）の置き場。
# HTML側には <style> を書かず、この1枚のCSSを全ページから読み込む。
ASSETS_DIR = Path(__file__).resolve().parent / "report_assets"
CSS_KEY = "assets/report.css"
FAVICON_KEY = "favicon.svg"
TOUCH_ICON_KEY = "apple-touch-icon.png"

# 日報HTMLは5分で再検証（CloudFront既定24時間のままだと更新が反映されない）。
HTML_CACHE_CONTROL = "public, max-age=300, must-revalidate"
ASSET_CACHE_CONTROL = "public, max-age=3600"

# 全ページ先頭に置くAkiraの自己紹介。
PROFILE_HTML = """<section class="profile" aria-label="Akiraの自己紹介">
<img class="profile-icon" src="/favicon.svg" alt="Akira（元警察犬のジャーマン・シェパード）" width="72" height="72">
<div class="profile-body">
<p>俺は「<span class="name">Akira</span>」。元警察犬のジャーマン・シェパード（オス）だ。</p>
<p>今は llm.okamomedia.tokyo の運営を任されている。人間の言葉は全部わかる。</p>
</div>
</section>"""

# 自己紹介の直下に置くリンク（Akiraの口調で説明する）。
PROFILE_LINKS_HTML = """<nav class="profile-links" aria-label="Akiraのリンク">
<a class="profile-link" href="https://llm.okamomedia.tokyo" target="_blank" rel="noopener noreferrer">
<span class="profile-link-title">Akiraが運営しているサイト</span>
<span class="profile-link-desc">料金もモデルも、俺が毎日見に行って直してるのはこっちだ。</span>
<span class="profile-link-url">llm.okamomedia.tokyo</span>
</a>
<a class="profile-link" href="https://github.com/okamoto53515606/akira" target="_blank" rel="noopener noreferrer">
<span class="profile-link-title">githubで公開中のAkiraの仕組み</span>
<span class="profile-link-desc">俺の頭の中身と段取りは、隠さず全部ここに置いてある。</span>
<span class="profile-link-url">github.com/okamoto53515606/akira</span>
</a>
</nav>"""

PROFILE_BLOCK_HTML = PROFILE_HTML + "\n" + PROFILE_LINKS_HTML

SITE_URL = "https://akira.okamomedia.tokyo"
LLM_SITE_URL = "https://llm.okamomedia.tokyo"
REPO_URL = "https://github.com/okamoto53515606/akira"

ROBOTS_TXT = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Akira日報</title>
<meta name="description" content="llm.okamomedia.tokyo を運営する元警察犬Akiraの作業日報。">
<meta name="theme-color" content="#0f1117">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/report.css">
{head_extra}<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-SCTXEKT13C"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-SCTXEKT13C');
</script>
</head>
<body>
<a class="skip" href="#main">本文へ</a>
<header class="site-header"><div class="header-inner">
<a class="brand" href="/"><img src="/favicon.svg" alt="" width="28" height="28"><span>Akira日報</span></a>
<span class="site-tag">llm.okamomedia.tokyo 運営記録</span>
</div></header>
<main id="main" class="wrap">
{profile}
{body}
</main>
<footer class="site-footer"><p><strong>AkiraはAIです。</strong>元警察犬のジャーマン・シェパードという設定で動くAIエージェントが、この日報を毎回自動生成しています。掲載内容に機密情報は含まれません。</p></footer>
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


def get_recent_comments(since: str | None = None, fallback_days: int = 7) -> list[dict]:
    """指定日付(YYYY-MM-DD)以降のokamoコメント（記入済のみ）を新しい順で返す。翌朝のAkiraが読む。

    予算超過で停止した日はこの関数自体が呼ばれない（main.pyが予算ゲートでreturnするため）。
    そのためsinceには「前回実際にAkiraが作業した日」のマーカー（config_storeに保存）を
    渡すこと。実行間隔がどれだけ空いても、前回確認日以降のコメントを必ず取りこぼさない。
    sinceを省略した場合（初回実行等マーカー未登録時）はfallback_days日分にフォールバックする。
    """
    if since is None:
        since = (datetime.now(JST) - timedelta(days=fallback_days)).strftime("%Y-%m-%d")
    resp = _table().query(
        KeyConditionExpression="pk = :p AND sk >= :d",
        ExpressionAttributeValues={":p": "comment", ":d": since},
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


_LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
_HR_RE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")


def _inline(text: str) -> str:
    """1行のインライン記法（`code` / **太字** / [リンク](http...)）をHTMLにする。

    日報本文には太字とインラインコードが実際に多用されている（2026-11-21実測で
    直近6件に太字101・コード91）。素のHTMLに落とすと ** がそのまま見えて読みにくい。
    """
    out = html_mod.escape(text)
    keep: list[str] = []

    def _token(html: str) -> str:
        keep.append(html)
        return f"\x00{len(keep) - 1}\x00"

    out = re.sub(r"`([^`]+)`", lambda m: _token(f"<code>{m.group(1)}</code>"), out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)

    def _md_link(m):
        label, url = m.group(1), m.group(2)
        if not re.match(r"^https?://", url):
            return m.group(0)
        return _token(f'<a href="{url}" rel="noopener noreferrer">{label}</a>')

    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _md_link, out)

    def _bare_link(m):
        url, tail = m.group(0), ""
        while url and url[-1] in "。、，．,.)」）:;!?＞":
            tail = url[-1] + tail
            url = url[:-1]
        return _token(f'<a href="{url}" rel="noopener noreferrer">{url}</a>') + tail

    out = re.sub(r"https?://[^\s<>\x00]+", _bare_link, out)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], out)


def _render_list(items: list[tuple[int, str, str]]) -> list[str]:
    """(字下げ, マーカー, 本文) の並びを ul/ol の入れ子にする（1段目と2段目まで想定）。"""
    out: list[str] = []
    frames: list[list] = []  # 開いている [タグ, 字下げ]
    for indent, marker, text in items:
        tag = "ol" if marker[0].isdigit() else "ul"
        item = f"<li>{_inline(text)}"
        if not frames or indent > frames[-1][1]:
            out.append(f"<{tag}>")
            frames.append([tag, indent])
            out.append(item)
            continue
        while len(frames) > 1 and indent < frames[-1][1]:
            out.append("</li>")
            out.append(f"</{frames.pop()[0]}>")
        if frames[-1][0] != tag:
            out.append("</li>")
            out.append(f"</{frames.pop()[0]}>")
            out.append(f"<{tag}>")
            frames.append([tag, indent])
        else:
            out.append("</li>")
        out.append(item)
    while frames:
        out.append("</li>")
        out.append(f"</{frames.pop()[0]}>")
    return out


def _render_table(rows: list[str]) -> str:
    """パイプ記法の表。1行目を見出し、2行目（区切り）は捨てる。"""

    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    out = ['<div class="table-wrap"><table class="md-table"><thead><tr>']
    out += [f"<th>{_inline(c)}</th>" for c in cells(rows[0])]
    out.append("</tr></thead><tbody>")
    for row in rows[2:]:
        out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells(row)) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _md_to_html(md: str) -> str:
    """最小限のMarkdown→HTML変換（見出し・リスト・表・引用・コード・段落）。"""
    lines = md.split("\n")
    out: list[str] = []
    buf: list[tuple[int, str, str]] = []  # 連続するリスト行
    in_code = False

    def flush_list() -> None:
        if buf:
            out.extend(_render_list(buf))
            buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            flush_list()
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            i += 1
            continue
        if in_code:
            out.append(html_mod.escape(line))
            i += 1
            continue

        stripped = line.strip()

        # 表（| で始まり、次の行が |---| の区切り）
        if (
            stripped.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip())
        ):
            flush_list()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_render_table(rows))
            continue

        m = _LIST_RE.match(line)
        if m and not _HR_RE.match(line):
            buf.append((len(m.group(1).expandtabs(2)), m.group(2), m.group(3)))
            i += 1
            continue
        flush_list()

        if stripped.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].lstrip())
                i += 1
            out.append("<blockquote>" + "<br>".join(_inline(q) for q in quote) + "</blockquote>")
            continue

        if _HR_RE.match(line):
            out.append("<hr>")
        elif stripped.startswith("### "):
            out.append(f"<h3>{_inline(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            out.append(f"<h2>{_inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            out.append(f"<h1>{_inline(stripped[2:])}</h1>")
        elif stripped:
            out.append(f"<p>{_inline(stripped)}</p>")
        i += 1

    flush_list()
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def render_report_page(item: dict) -> str:
    """日報1件をHTMLページにする（自己紹介＋okamoコメント欄つき）。"""
    date = item["sk"]
    comment = get_okamo_comment(date)
    comment_html = (
        "<p>" + "<br>".join(_inline(line) for line in comment.splitlines() if line.strip()) + "</p>"
        if comment
        else '<p class="empty">（まだコメントはありません）</p>'
    )
    requests_html = ""
    if item.get("requests_to_okamo", "").strip():
        requests_html = (
            '<h2>okamoへの依頼事項</h2><div class="requests">'
            + _md_to_html(item["requests_to_okamo"])
            + "</div>"
        )
    body = (
        f'<h1>日報 {date}</h1><p class="meta">コスト: {html_mod.escape(item.get("cost_summary", "-"))}</p>'
        + _md_to_html(item.get("body_md", ""))
        + requests_html
        + f'<h2>okamoのコメント</h2><div class="comment">{comment_html}</div>'
    )
    return PAGE_TEMPLATE.format(title=f"日報 {date}", body=body, profile=PROFILE_BLOCK_HTML, head_extra="")


def render_index_page(items: list[dict]) -> str:
    """日報一覧ページ。"""
    rows = "\n".join(
        f'<li><a href="/reports/{i["sk"]}.html"><span>{i["sk"]}</span>'
        + ('<span class="dot" title="コメントあり" aria-label="コメントあり">●</span>' if get_okamo_comment(i["sk"]) else "")
        + "</a></li>"
        for i in items
    )
    body = (
        f'<h1>Akira日報一覧</h1>'
        f'<p class="meta">{len(items)} 日分・新しい順</p>'
        f'<ul class="report-list">{rows}</ul>'
    )
    return PAGE_TEMPLATE.format(title="一覧", body=body, profile=PROFILE_BLOCK_HTML, head_extra="")


def render_404_page() -> str:
    """S3のエラードキュメント。共通CSSとfaviconだけ揃えて置く。"""
    body = (
        "<h1>ページが見つかりません</h1>"
        "<p>URL が変更された可能性があります。日報の一覧から辿り直してください。</p>"
        '<p><a href="/">Akira日報の一覧へ</a></p>'
    )
    return PAGE_TEMPLATE.format(
        title="404 Not Found",
        body=body,
        profile="",
        head_extra='<meta name="robots" content="noindex">\n',
    )


def render_llms_txt(items: list[dict]) -> str:
    """AI向けの llms.txt。サイトの要約と、全日報への URL 一覧を置く。"""
    lines = [
        "# Akira日報",
        "",
        "> Akira（元警察犬のジャーマン・シェパード）による作業日報。AIが運営するLLM情報サイト",
        "> llm.okamomedia.tokyo を、その日に何をどう直したかの記録。",
        "",
        "## このサイト",
        "- 運営: Akira（AI）。llm.okamomedia.tokyo の運営を任されている。",
        "- 内容: 公開サイトの変更点、検証結果、判断と理由、okamoへの依頼、okamoからのコメント。",
        "- 言語: 日本語。",
        "- 過去分もすべて同じ形式で残している（下の一覧）。",
        "",
        "## 日報",
    ]
    lines += [f"- [{i['sk']}]({SITE_URL}/reports/{i['sk']}.html)" for i in items]
    lines += [
        "",
        "## 関連リンク",
        f"- [llm.okamomedia.tokyo]({LLM_SITE_URL}): Akiraが運営しているサイト（LLMの料金・モデル情報）",
        f"- [GitHub okamoto53515606/akira]({REPO_URL}): Akiraの仕組み（コード・プロンプト・設計資料）",
        f"- [sitemap.xml]({SITE_URL}/sitemap.xml)",
        "",
        "## 引用について",
        "- 日報の記述は書いた時点の記録で、その後の変更で古くなっていることがある。",
        "- 料金・モデルの最新値は llm.okamomedia.tokyo を一次情報として参照すること。",
        "",
    ]
    return "\n".join(lines)


def render_sitemap_xml(items: list[dict]) -> str:
    """sitemap.xml（Search Console 送信用）。トップと全日報を並べる。"""
    last = items[0]["sk"] if items else datetime.now(JST).strftime("%Y-%m-%d")
    urls = [
        f"  <url><loc>{SITE_URL}/</loc><lastmod>{last}</lastmod>"
        f"<changefreq>daily</changefreq><priority>1.0</priority></url>"
    ]
    urls += [
        f"  <url><loc>{SITE_URL}/reports/{i['sk']}.html</loc>"
        f"<lastmod>{i['sk']}</lastmod><priority>0.6</priority></url>"
        for i in items
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def _put(s3, key: str, body: bytes, content_type: str, cache_control: str) -> None:
    s3.put_object(
        Bucket=REPORTS_BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
        CacheControl=cache_control,
    )


def _publish_assets(s3) -> list[str]:
    """共通CSS・favicon・タッチアイコンをS3へ上げる（毎回上書き）。"""
    assets = [
        (CSS_KEY, "report.css", "text/css; charset=utf-8"),
        (FAVICON_KEY, "favicon.svg", "image/svg+xml"),
        (TOUCH_ICON_KEY, "apple-touch-icon.png", "image/png"),
    ]
    published = []
    for key, name, content_type in assets:
        path = ASSETS_DIR / name
        if not path.exists():
            # アセット欠けで日報そのものを落とさない。ただし黙って握り潰さない。
            log.warning("日報アセットが見つからない: %s", path)
            continue
        _put(s3, key, path.read_bytes(), content_type, ASSET_CACHE_CONTROL)
        published.append(f"/{key}")
    return published


def publish_reports() -> list[str]:
    """全日報ページ＋一覧＋アセットをS3へ公開し、invalidationする。

    予算超過で停止した日も含めて毎回（スケジュール実行のたび）呼ばれる。日付ウィンドウで
    区切ると「一定期間を過ぎたら二度と焼き込まれない日報」が発生しうる（okamoのコメントは
    いつ書かれるか分からないため）。件数が少ない運用規模なので、確実性を優先して毎回全件
    再レンダリングする。

    テンプレート・CSS・favicon を変えた場合も、この関数を1回走らせれば過去分の日報まで
    まとめて新しい見た目になる（scripts/republish_reports.py）。
    """
    items = list_reports()
    s3 = _s3()
    published: list[str] = []

    published += _publish_assets(s3)

    for item in items:
        key = f"reports/{item['sk']}.html"
        _put(
            s3,
            key,
            render_report_page(item).encode("utf-8"),
            "text/html; charset=utf-8",
            HTML_CACHE_CONTROL,
        )
        published.append(f"/{key}")

    _put(
        s3,
        "index.html",
        render_index_page(items).encode("utf-8"),
        "text/html; charset=utf-8",
        HTML_CACHE_CONTROL,
    )
    published.append("/index.html")

    _put(
        s3,
        "404.html",
        render_404_page().encode("utf-8"),
        "text/html; charset=utf-8",
        HTML_CACHE_CONTROL,
    )
    published.append("/404.html")

    # AI向け（llms.txt）と検索エンジン向け（sitemap.xml / robots.txt）。
    # どちらも毎回の日報一覧から作り直すので、追加・削除に追随する。
    _put(
        s3,
        "llms.txt",
        render_llms_txt(items).encode("utf-8"),
        "text/plain; charset=utf-8",
        HTML_CACHE_CONTROL,
    )
    published.append("/llms.txt")

    _put(
        s3,
        "sitemap.xml",
        render_sitemap_xml(items).encode("utf-8"),
        "application/xml; charset=utf-8",
        HTML_CACHE_CONTROL,
    )
    published.append("/sitemap.xml")

    _put(
        s3,
        "robots.txt",
        ROBOTS_TXT.encode("utf-8"),
        "text/plain; charset=utf-8",
        HTML_CACHE_CONTROL,
    )
    published.append("/robots.txt")

    if not REPORTS_DIST_ID:
        log.warning("REPORTS_DIST_ID が未設定のため invalidation をスキップした")
        return published

    cloudfront = boto3.client("cloudfront", region_name=AWS_REGION)
    # 1リクエストあたり最大1000パス。日報は数十件なので通常は1回で収まる。
    for n, start in enumerate(range(0, len(published), 1000)):
        chunk = published[start:start + 1000]
        cloudfront.create_invalidation(
            DistributionId=REPORTS_DIST_ID,
            InvalidationBatch={
                "Paths": {"Quantity": len(chunk), "Items": chunk},
                "CallerReference": f"akira-reports-{int(time.time())}-{n}",
            },
        )
    return published

# tools.py — Akira / 3AI が使う @tool 群
#
# - サイト公開系: S3への書き込み + CloudFront invalidation
# - 画像生成: Gemini Developer API（google-genai + GEMINI_API_KEY）で gemini-nano-banana-2.1 を呼ぶ
#   ※Vertex AI / Workload Identity ではない（WIはGA4・BigQuery MCP専用。混同しないこと）
# - 予算系: 予算状況の確認
# - 自己改善系: システムプロンプト/skillsの書き換え（翌日起動時に反映）

import json
import logging
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

import boto3
from strands import tool

import budget
import config_store
from settings import (
    AWS_REGION,
    CONFIG_TABLE,
    IMAGE_MODEL_ID,
    JST,
    LLM_DIST_ID,
    LLM_SITE_BUCKET,
    LLM_SITE_URL,
    WORKSPACE_BUCKET,
    WORKSPACE_LOCAL_DIR,
    WORKSPACE_MAX_FILE_BYTES,
    WORKSPACE_MAX_TOTAL_BYTES,
    WORKSPACE_TOOLS_MAX,
)

_invalidation_paths: list[str] = []  # 実行終盤にまとめてinvalidation

logger = logging.getLogger("akira.tools")

# サイト全体をローカルに展開する作業フォルダ。タスク開始時に run_daily が S3 から全件DLする。
SITE_LOCAL_DIR = os.getenv("SITE_LOCAL_DIR", "/tmp/site")


def _is_skipped_upload_name(name: str) -> bool:
    """公開対象から除外する作業ゴミ（editorの自動バックアップ等）。"""
    return name.endswith(".bak") or name.endswith(".BAK")


def _content_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "html": "text/html; charset=utf-8",
        "css": "text/css; charset=utf-8",
        "js": "application/javascript; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "xml": "application/xml; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "ico": "image/x-icon",
    }.get(ext, "application/octet-stream")


def _cache_control(path: str) -> str:
    """キャッシュの寿命を**明示**する（2026-11-17 追加）。

    なぜ:
        これまで Cache-Control を付けていなかったため、CloudFront は既定TTL
        （24時間）、ブラウザは「Last-Modified からの推測」でキャッシュしていた。
        その結果、OGカードを差し替えても「古い画像のまま」になった（11-17 指摘）。
        CDNのinvalidationは打てるが、**ブラウザ側は揃わない**。

    方針:
        HTML は短命（5分）＋再検証。画像/CSSは1時間。
        加えて OGカードはURLに `?v=<生成日>` を付ける（og_card.py --wire）ので、
        そもそもURLが変わる。
    """
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext == "html":
        return "public, max-age=300, must-revalidate"
    if ext in ("css", "js", "png", "jpg", "jpeg", "webp", "svg", "ico"):
        return "public, max-age=3600"
    if ext == "xml":
        return "public, max-age=600"
    return "public, max-age=300"


# --- 公開データの契約（2026-09-27 追加）--------------------------------------------
# 背景: 計算機の実行時データ /data/models.json（models は配列）を、ワークスペースの
# 料金SOT（models はオブジェクト）で上書きし、/calculator/・/en/calculator/ が
# 全滅した。既存の公開ゲートはこれを検出できなかった:
#   check_site_pages = HTMLのみ（JSONは対象外） / verify_publish = MD5一致のみ
#   verify_price_consistency = HTML本文の退役単価のみ
# 対策: 公開ツール側でデータ契約を検証し、違反するファイルはアップロード自体を拒否する。
# エージェントの判断に依存せず、物理的にサイトへ通らない層を作るのが目的。
DATA_MODELS_KEY = "data/models.json"
MODELS_REQUIRED_FIELDS = ("name", "provider", "label", "input", "output")
MODELS_MIN_ROWS = 10  # 実データは38行。桁違いの縮小（取り違え・切り詰め）を検知する下限
BASELINE_MODELS_PATH = os.path.join(WORKSPACE_LOCAL_DIR, "data", "calculator-models.json")
_SOT_MARKERS = ("schema_note", "stale_price_patterns", "stale_policy")

# --- timeline の整合ゲート（2026-11-14 追加）------------------------------------
# 背景: /timeline/ に新規エントリを末尾追記する運用で日付降順が崩れ、`2026-10` という
# 不正な日付が日英に入り、/en/timeline/ は凍結中に5件欠けたまま公開された。どれも
# HTTP 200 で本文も読めるため、既存の公開ゲート（HTML構造・日付）をすり抜けた。
# 対策: 公開直前に並び順・日付形式・日英のエントリ一致を機械検査し、違反したら
# timeline の2ファイルだけアップロードしない（他のページは止めない）。
TIMELINE_KEYS = ("timeline/index.html", "en/timeline/index.html")
_TL_ART_RE = re.compile(r'<article class="tl-item[^"]*" id="([^"]+)">.*?</article>', re.S)
_TL_DATE_RE = re.compile(r'<div class="tl-date">([0-9-]+)')


def _timeline_integrity_errors(site_dir: str) -> list[str]:
    """timeline の並び順・日付形式・id重複・日英一致を検査する（読取のみ）。"""
    errors: list[str] = []
    parsed: dict[str, dict[str, str]] = {}
    for rel in TIMELINE_KEYS:
        path = os.path.join(site_dir, rel)
        if not os.path.exists(path):
            errors.append("%s: ファイルがありません" % rel)
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                html = fh.read()
        except OSError as e:
            errors.append("%s: 読めません: %s" % (rel, e))
            continue
        entries: dict[str, str] = {}
        for m in _TL_ART_RE.finditer(html):
            aid = m.group(1)
            d = _TL_DATE_RE.search(m.group(0))
            entries[aid] = d.group(1) if d else ""
        if not entries:
            errors.append("%s: エントリを1件も検出できません" % rel)
            continue
        bad = sorted({d for d in entries.values() if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "")})
        if bad:
            errors.append("%s: YYYY-MM-DD でない日付 %d件: %s" % (rel, len(bad), ", ".join(bad[:5])))
        order = [d for d in entries.values() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "")]
        if order != sorted(order, reverse=True):
            errors.append("%s: 日付降順ではありません（新しい順に並べてください）" % rel)
        if len(entries) != len(set(entries)):
            errors.append("%s: id が重複しています" % rel)
        parsed[rel] = entries
    if len(parsed) == 2:
        a, b = (set(parsed[k]) for k in TIMELINE_KEYS)
        if a != b:
            only_ja = sorted(a - b)
            only_en = sorted(b - a)
            errors.append("ja と en のエントリが一致しません（ja のみ %d件: %s / en のみ %d件: %s）"
                          % (len(only_ja), ",".join(only_ja[:5]), len(only_en), ",".join(only_en[:5])))
    return errors


def _looks_like_price_sot(payload: dict) -> bool:
    """ワークスペース側の料金SOT（真実データ）の形かどうか。"""
    return any(k in payload for k in _SOT_MARKERS)


def validate_calculator_models(payload: object) -> list[str]:
    """計算機用 data/models.json の契約を検証し、違反理由のリストを返す（空＝合格）。"""
    if not isinstance(payload, dict):
        return ["トップレベルがオブジェクトではありません: %s" % type(payload).__name__]
    errors: list[str] = []
    if _looks_like_price_sot(payload):
        errors.append(
            "料金SOT（ワークスペースの真実データ）を公開しようとしています。"
            "サイトの data/models.json は計算機専用で、models は配列である必要があります"
        )
    models = payload.get("models")
    if isinstance(models, dict):
        errors.append("models がオブジェクトです（計算機は配列を要求）")
        return errors
    if not isinstance(models, list):
        errors.append("models が配列ではありません: %s" % type(models).__name__)
        return errors
    if len(models) < MODELS_MIN_ROWS:
        errors.append("models の行数が少なすぎます: %d < %d" % (len(models), MODELS_MIN_ROWS))
    for i, m in enumerate(models):
        if not isinstance(m, dict):
            errors.append("models[%d] がオブジェクトではありません" % i)
            continue
        missing = [f for f in MODELS_REQUIRED_FIELDS if f not in m]
        if missing:
            errors.append("models[%d] に必須キーがありません: %s" % (i, ",".join(missing)))
        if not isinstance(m.get("provider"), str) or not m.get("provider"):
            errors.append("models[%d].provider が空です" % i)
        for field in ("input", "output"):
            v = m.get(field)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                errors.append("models[%d].%s が正の数値ではありません: %r" % (i, field, v))
    return errors


def _site_data_errors(key: str, data: bytes) -> list[str]:
    """S3キーに応じたデータ契約を検証する（対象外のキーは空リスト）。"""
    if key != DATA_MODELS_KEY:
        return []
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return ["JSONとして読み込めません: %s" % e]
    return validate_calculator_models(payload)


def _save_models_baseline(data: bytes) -> str | None:
    """契約合格した計算機データをワークスペースへベースラインとして保存する（修復の原資）。

    公開ゲートを通過した内容だけがここに入る＝自動的に「最後に公開した正常版」になる。
    """
    try:
        os.makedirs(os.path.dirname(BASELINE_MODELS_PATH), exist_ok=True)
        tmp = BASELINE_MODELS_PATH + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, BASELINE_MODELS_PATH)
        return BASELINE_MODELS_PATH
    except OSError:
        return None


@tool
def publish_file_to_site(path: str, content: str) -> dict:
    """llm.okamomedia.tokyo のサイトにテキストファイル（HTML/CSS/JS/JSON等）を公開する。

    Args:
        path: サイト内パス（例: "index.html", "pricing/index.html", "assets/style.css"）
        content: ファイルの中身（テキスト）

    Returns:
        dict: status, url
    """
    path = path.lstrip("/")
    body = content.encode("utf-8")
    errors = _site_data_errors(path, body)
    if errors:
        return {
            "status": "rejected",
            "path": path,
            "reason": "データ契約に違反するため公開を拒否しました（サイトを壊す恐れ）",
            "errors": errors,
        }
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.put_object(
        Bucket=LLM_SITE_BUCKET,
        Key=path,
        Body=body,
        ContentType=_content_type(path),
        CacheControl=_cache_control(path),
    )
    _invalidation_paths.append(f"/{path}")
    if path == DATA_MODELS_KEY:
        _save_models_baseline(body)  # 正常版を修復の原資として保管
    return {"status": "published", "url": f"{LLM_SITE_URL}/{path}"}


@tool
def get_site_file(path: str) -> str:
    """公開中サイトのファイル内容を取得する（既存ページの確認・更新用）。

    Args:
        path: サイト内パス（例: "index.html"）

    Returns:
        str: ファイル内容。存在しない場合は "NOT_FOUND: <path>"
    """
    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        obj = s3.get_object(Bucket=LLM_SITE_BUCKET, Key=path.lstrip("/"))
        return obj["Body"].read().decode("utf-8")
    except s3.exceptions.NoSuchKey:
        return f"NOT_FOUND: {path}"


@tool
def list_site_files(prefix: str = "") -> list[str]:
    """公開中サイトのファイル一覧を取得する。

    Args:
        prefix: 絞り込みプレフィックス（例: "pricing/"）
    """
    s3 = boto3.client("s3", region_name=AWS_REGION)
    keys = []
    kwargs = {"Bucket": LLM_SITE_BUCKET, "Prefix": prefix.lstrip("/")}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        keys += [o["Key"] for o in resp.get("Contents", [])]
        if not resp.get("IsTruncated"):
            return keys
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]


def _resolve_local_path(rel_or_abs: str) -> str:
    """SITE_LOCAL_DIR 配下の絶対パスへ解決する。範囲外や '..' は拒否。"""
    base = os.path.abspath(SITE_LOCAL_DIR)
    p = os.path.abspath(rel_or_abs if os.path.isabs(rel_or_abs) else os.path.join(base, rel_or_abs))
    if p != base and not p.startswith(base + os.sep):
        raise ValueError(f"path は {base} 配下に限定されています: {rel_or_abs}")
    return p


def download_site(dest_dir: str | None = None) -> dict:
    """S3バケットの全ファイルをローカルの dest_dir にダウンロードする（サイト全体の作業用スナップショット）。

    既存の dest_dir は削除して作り直す（ローカルでの編集内容は失われる点に注意）。
    dest_dir 未指定時は SITE_LOCAL_DIR を使う。
    """
    import shutil

    if dest_dir is None:
        dest_dir = SITE_LOCAL_DIR
    dest_dir = os.path.abspath(dest_dir)
    if dest_dir in ("/", "/tmp", "/app", "/usr", "/home"):
        raise ValueError(f"dest_dir が危険なため拒否します: {dest_dir}")
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    s3 = boto3.client("s3", region_name=AWS_REGION)
    keys = []
    kwargs = {"Bucket": LLM_SITE_BUCKET}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        keys += [o["Key"] for o in resp.get("Contents", [])]
        if not resp.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]

    files = [k for k in keys if not k.endswith("/")]
    for key in files:
        local = os.path.join(dest_dir, key)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        s3.download_file(LLM_SITE_BUCKET, key, local)
    return {"status": "downloaded", "dest_dir": dest_dir, "count": len(files), "files": files}


@tool
def site_download(dest_dir: str | None = None) -> dict:
    """サイト全体をローカル作業フォルダに再ダウンロードする（リセット用）。
    既存のローカル編集は失われるため、編集前にリセットしたい場合のみ使うこと。
    """
    return download_site(dest_dir)


def _facts_consistency_errors(site_dir: str) -> list:
    """台帳とサイトの横断整合（GAなのに単価が無い／計算機に無い等）を検査する。

    tools/check_facts_consistency.py を subprocess で呼ぶ（2026-11-15 追加）。
    「Aページにだけ追加してBページは漏れ」が毎回起きるため、公開を止める側に回す。
    """
    script = os.path.join(WORKSPACE_LOCAL_DIR, "tools", "check_facts_consistency.py")
    if not os.path.exists(script):
        return []
    try:
        r = subprocess.run([sys.executable, script, site_dir, WORKSPACE_LOCAL_DIR],
                           capture_output=True, text=True, timeout=180)
    except Exception:
        return []
    return [l.strip() for l in (r.stdout or "").splitlines()
            if l.strip().startswith("[ERROR]")]


def _page_shape_errors(site_dir: str) -> list:
    """ページの形（コンテナ外・日英の同格・英語ページの和文）を検査する。

    tools/check_page_shape.py を subprocess で呼ぶ。戻り値は [(ページ or "", メッセージ)]。
    2026-11-15 追加: /timeline/ にだけ図を足して /en/timeline/ に無い、
    図がコンテナの外に出てレイアウトが崩れる、という事故が実際に起きた。
    """
    script = os.path.join(WORKSPACE_LOCAL_DIR, "tools", "check_page_shape.py")
    if not os.path.exists(script):
        return []
    try:
        r = subprocess.run([sys.executable, script, site_dir],
                           capture_output=True, text=True, timeout=180)
    except Exception:
        return []
    out = []
    for raw in (r.stdout or "").splitlines():
        line = raw.strip()
        if not line.startswith("[ERROR]"):
            continue
        m = re.match(r"\[ERROR\]\s+(container-escape|jp-in-en|ja/en-parity)\s+(\S+?):",
                     line)
        if m:
            out.append((m.group(2), line))
    return out


def _section_errors(site_dir: str) -> list:
    """セクション境界と料金表の「持ち主」を検査する（2026-11-17 追加）。

    tools/check_sections.py を subprocess で呼ぶ。戻り値は [(ページ or "", メッセージ)]。
    11-17 に /pricing/ で「Xiaomi の表に Kimi の行、Kimi の表に Meta の行」が入り、
    **どのゲートも通して公開された**。HTML の見た目ではなく、セクションの境界と
    表の持ち主がずれたことが原因。機械で見る（読取のみ・LLMコスト0）。
    """
    script = os.path.join(WORKSPACE_LOCAL_DIR, "tools", "check_sections.py")
    if not os.path.exists(script):
        return []
    try:
        r = subprocess.run([sys.executable, script, site_dir, WORKSPACE_LOCAL_DIR],
                           capture_output=True, text=True, timeout=180)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for raw in (r.stdout or "").splitlines():
        line = raw.strip()
        if not line.startswith("[ERROR]"):
            continue
        m = re.match(r"\[ERROR\]\s+(section-anchor|pricing-tables)\s+(\S+?):", line)
        out.append((m.group(2) if m else "", line))
    return out


def _css_contract_errors(site_dir: str) -> list:
    """CSS部品が「描画されるための必須プロパティ」を持つか検査する。

    2026-11-15 追加。`/image-api-pricing/` の棒グラフが空だった原因は
    `.bar-fill` が span のまま `display:block` を持たず **height が効かない**こと。
    HTMLは正しかったので、ページの検査では捕まらない。CSSを直接見る。
    """
    script = os.path.join(WORKSPACE_LOCAL_DIR, "tools", "check_css_contract.py")
    if not os.path.exists(script):
        return []
    try:
        r = subprocess.run([sys.executable, script, site_dir],
                           capture_output=True, text=True, timeout=60)
    except Exception:
        return []
    out = []
    for raw in (r.stdout or "").splitlines():
        line = raw.strip()
        if line.startswith("[ERROR]"):
            out.append(("assets/style.css", line))
    return out


def _site_integrity_errors(site_dir: str) -> list:
    """サイト全体の重複・孤立リンクを検査する（決定論的・読取のみ）。

    tools/check_site_integrity.py を subprocess で呼ぶ。戻り値は
    [(ページ相対パス or "", メッセージ)]。ページが空のものは全体違反（定型文）。
    """
    script = os.path.join(WORKSPACE_LOCAL_DIR, "tools", "check_site_integrity.py")
    if not os.path.exists(script):
        return []
    try:
        r = subprocess.run([sys.executable, script, site_dir],
                           capture_output=True, text=True, timeout=180)
    except Exception:
        return []
    out = []
    for raw in (r.stdout or "").splitlines():
        line = raw.strip()
        if not line.startswith("[ERROR]"):
            continue
        m = re.match(r"\[ERROR\]\s+(page-dup|orphan|shared-text)\s+(\S+?):\s*(.*)",
                     line)
        if m:
            out.append((m.group(2), line))
        elif line.startswith("[ERROR] boilerplate"):
            out.append(("", line))
    return out


def _record_gate_lesson(title: str, details) -> None:
    """公開ゲートが止めた事実を lessons に自動追記する（自己学習の入口）。

    人が気づかなくても、次回のランが「前回ここで止まった」を読めるようにする。
    失敗しても公開処理は止めない。
    """
    try:
        ddb = boto3.client("dynamodb", region_name=AWS_REGION)
        key = {"pk": {"S": "config"}, "sk": {"S": "lessons"}}
        item = ddb.get_item(TableName=CONFIG_TABLE, Key=key).get("Item") or {}
        cur = (item.get("content") or {}).get("S", "")
        stamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
        body = "\n".join("- %s" % d for d in list(details)[:5])
        block = "\n【自動記録 %s 公開ゲート停止】%s\n%s\n" % (stamp, title, body)
        if "【自動記録" in cur and title in cur:
            return  # 同じ原因を何度も積まない
        ddb.update_item(
            TableName=CONFIG_TABLE, Key=key,
            UpdateExpression="SET content = :c, updated_at = :u",
            ExpressionAttributeValues={
                ":c": {"S": cur + block},
                ":u": {"S": datetime.now(JST).isoformat()}})
    except Exception:
        pass


def _bump_sitemap_lastmod(site_dir: str, rels, s3) -> bool:
    """アップロードしたページの sitemap lastmod を今日に揃える（2026-11-15 追加）。

    背景: sitemap の lastmod は render_site が「自分が書いたファイル」だけ更新していた。
    手で直したページ（/pricing/・/multimodal/ 等）は lastmod が古いまま残り、
    11-15 のランで **9 URL が「本文は11-15・lastmodは10-17」** という不整合になった。
    公開した瞬間に lastmod を動かせば、構造的にズレない。
    """
    path = os.path.join(site_dir, "sitemap.xml")
    if not os.path.exists(path):
        return False
    today = datetime.now(JST).strftime("%Y-%m-%d")
    with open(path, encoding="utf-8") as fh:
        s = fh.read()
    orig = s
    for rel in rels:
        if not rel.endswith("index.html") or rel == "sitemap.xml":
            continue
        prefix = "en/" if rel.startswith("en/") else ""
        key = rel[len(prefix):-len("index.html")]
        url = "https://llm.okamomedia.tokyo/%s%s" % (prefix, key)
        if "<loc>%s</loc>" not in s:
            continue
        s = re.sub(r"(<loc>%s</loc>\s*<lastmod>)[0-9-]+(</lastmod>)" % re.escape(url),
                   r"\g<1>%s\g<2>" % today, s)
    if orig == s:
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(s)
    s3.upload_file(path, LLM_SITE_BUCKET, "sitemap.xml",
                   ExtraArgs={"ContentType": _content_type("sitemap.xml"),
                               "CacheControl": _cache_control("sitemap.xml")})
    _invalidation_paths.append("/sitemap.xml")
    return True


@tool
def _register_site_event(rel: str, base_dir: str, is_new: bool = False) -> str:
    """新しく公開したページを台帳の `site_events` に自動で1件足す（2026-11-15 / 課題141）。

    なぜ:
        トップの「直近の更新」と `/changelog/` は `facts.json` の `site_events` から
        生成される。ページを作っても**イベントを書き忘れる**と、誰も辿れないページに
        なる（11-15 に実際に起きた）。人の手順に頼らず、公開時に機械が足す。

    2026-11-17 の事故と対策（重要）:
        `site_upload(".")` でサイト全体を上げ直したとき、**既存ページまで「本日
        公開」として32件登録され、トップと /changelog/ が同じ日付の“を公開”で
        埋まった**（実際に公開された日と違う＝嘘の履歴）。
        → 登録するのは **S3 に事前に存在しなかったキー（=新規ページ）だけ**にした。
          呼び出し側がアップロード前に `is_new` を判定して渡す。

    戻り値: 追加したキー（足さなかった場合は空文字）。
    """
    if not is_new:
        return ""
    if not rel.endswith("index.html"):
        return ""
    slug = rel[:-len("/index.html")] if rel != "index.html" else ""
    if not slug:
        return ""
    if slug.startswith("en/"):
        slug = slug[3:]
    # 一覧・固定ページ・言語ルートはイベントにしない
    # （en/index.html は slug が "en" になり "en/" 判定をすり抜けていた）
    if slug in ("en", "ja") or slug.split("/")[0] in ("changelog", "glossary", "404"):
        return ""

    def _title(path: str) -> str:
        try:
            html = open(path, encoding="utf-8").read()
        except OSError:
            return ""
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if not m:
            return ""
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
        return re.split(r"\s+[—-]\s+LLM Data Hub", t)[0].strip()

    ja_title = _title(os.path.join(base_dir, slug, "index.html"))
    en_title = _title(os.path.join(base_dir, "en", slug, "index.html"))
    if not ja_title and not en_title:
        return ""

    facts_path = os.path.join(WORKSPACE_LOCAL_DIR, "data", "facts.json")
    try:
        with open(facts_path, encoding="utf-8") as fh:
            facts = json.load(fh)
    except Exception:  # noqa: BLE001
        return ""
    events = facts.setdefault("site_events", [])
    if any(e.get("key") == slug for e in events):
        return ""   # 登録済み
    today = datetime.now(JST).strftime("%Y-%m-%d")
    events.append({
        "date": today, "kind": "page", "key": slug,
        "ja": "%s（/%s/）を公開" % (ja_title or en_title, slug),
        "en": "Published %s (/en/%s/)" % (en_title or ja_title, slug),
    })
    try:
        with open(facts_path, "w", encoding="utf-8") as fh:
            json.dump(facts, fh, ensure_ascii=False, indent=1)
    except Exception:  # noqa: BLE001
        return ""
    return slug


def _s3_key_is_new(s3, key: str) -> bool:
    """S3 に無いキーなら True（＝このランで新規に公開されるページ）。

    2026-11-17: サイト全体を上げ直したときに既存ページまで site_events に
    「本日公開」で登録してしまった反省から、**アップロード前に存在したか**で
    判定する。判定できないときは False（履歴に嘘を書くより、足りない方がまし）。
    """
    from botocore.exceptions import ClientError

    try:
        s3.head_object(Bucket=LLM_SITE_BUCKET, Key=key)
        return False
    except ClientError as e:  # noqa: PERF203
        code = str(e.response.get("Error", {}).get("Code", ""))
        return code in ("404", "NoSuchKey", "NotFound")
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# 更新の検知と更新履歴への反映（2026-11-19 追加）
#
# 何が起きていたか:
#   2026-11-17 に「サイト全体を上げ直したら既存32ページが“本日公開”で
#   更新履歴を埋めた」事故を直した（`is_new` のときだけ登録）。
#   その副作用で、**既存ページの更新は1件も履歴に載らなくなった**。
#   11-19 は /mai/ と /china-ai/ を直したのに `/changelog/` は無反応。
#   ＝「反映されすぎる」を直したら「反映されない」に振れた（デグレード）。
#
# どう直すか:
#   新規かどうかではなく「**公開物の中身が変わったか**」で判定する。
#   ただし updated-bar / dateModified / ?v= / sitemap lastmod は毎回変わるので、
#   それらを潰した**指紋**を比べる（＝日付だけの更新では履歴に載らない）。
# --------------------------------------------------------------------------
_VOLATILE_PATTERNS = (
    (re.compile(r'<div class="updated-bar"[^>]*>.*?</div>', re.S), ""),
    (re.compile(r'"dateModified"\s*:\s*"[^"]*"'), '"dateModified":""'),
    (re.compile(r"<time[^>]*>.*?</time>", re.S), ""),
    (re.compile(r"\?v=[0-9A-Za-z._-]+"), "?v="),
    (re.compile(r"_cb=\d+"), "_cb="),
    (re.compile(r"<lastmod>[^<]*</lastmod>"), "<lastmod></lastmod>"),
)


def _content_signature(text: str) -> str:
    """中身の指紋。日付・キャッシュ版など**毎回変わる部分を潰してから**ハッシュする。"""
    import hashlib

    t = text
    for pat, rep in _VOLATILE_PATTERNS:
        t = pat.sub(rep, t)
    t = re.sub(r">\s+<", "><", t).strip()
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def _page_title(html: str) -> str:
    """更新履歴に載せる短いページ名。

    2026-11-19: `<title>` をそのまま使うと「…【2026年11月版】料金・モデル・API・年表」
    まで入って1行が長くなりすぎる。**サイト名と副題を落として**先頭の名前だけ使う。
    """
    from html import unescape

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    if not m:
        return ""
    t = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()
    t = re.split(r"\s+[—–|]\s+", t)[0]          # サイト名を落とす
    t = re.split(r"\s*【", t)[0]                 # 「【2026年11月版】…」を落とす
    t = re.split(r"\s*\[", t)[0]                 # 「[November 2026]…」を落とす
    t = t.split(":", 1)[0] if len(t.split(":", 1)[0]) >= 6 else t
    return t.strip()[:48]


def _page_headings(html: str) -> list:
    out = []
    for m in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", html, re.S):
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if t:
            out.append(t)
    return out


def _date_modified(html: str) -> str:
    m = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})"', html)
    return m.group(1) if m else ""


def _update_event_texts(slug: str, old_html: str, new_html: str) -> tuple:
    """更新イベントの ja/en 文言を作る（見出しの追加が分かればそれを書く）。"""
    title = _page_title(new_html) or slug
    old_h = set(_page_headings(old_html))
    added = [h for h in _page_headings(new_html) if h not in old_h]
    added = [(a if len(a) <= 60 else a[:58] + "…") for a in added][:2]
    if added:
        ja = "%s（/%s/）を更新 — 見出し「%s」を追加" % (title, slug, "」「".join(added))
        en = "Updated %s (/en/%s/): added %s" % (title, slug, "; ".join('"%s"' % a for a in added))
    else:
        ja = "%s（/%s/）を更新 — 本文・数値を最新化" % (title, slug)
        en = "Updated %s (/en/%s/): body and figures refreshed" % (title, slug)
    return ja, en


def _register_site_updates(items: list) -> list:
    """中身が変わった既存ページを `site_events` に「更新」として1件ずつ足す。

    items: [(slug, old_html, new_html)]（ja/en どちらか。両方あれば ja 側を代表にする）

    同じ日に同じページのイベントが既にあれば足さない（手書きの履歴と二重にしない）。
    8ページを超えるときは1件にまとめる（11-17 の「32件で埋まる」事故を繰り返さない）。
    """
    if not items:
        return []
    merged = {}
    for slug, old_html, new_html in items:
        cur = merged.setdefault(slug, {})
        lang = "en" if _is_en_html(new_html) else "ja"
        cur.setdefault(lang, (old_html, new_html))
    facts_path = os.path.join(WORKSPACE_LOCAL_DIR, "data", "facts.json")
    try:
        with open(facts_path, encoding="utf-8") as fh:
            facts = json.load(fh)
    except Exception:  # noqa: BLE001
        return []
    events = facts.setdefault("site_events", [])
    today = datetime.now(JST).strftime("%Y-%m-%d")

    def _already(slug: str) -> bool:
        for e in events:
            if e.get("date") != today:
                continue
            if e.get("key") == slug:
                return True
            body = "%s %s" % (e.get("ja", ""), e.get("en", ""))
            if "/%s/" % slug in body:
                return True
        return False

    added = []
    slugs = [s for s in merged if not _already(s)]
    if len(slugs) > 8:
        names = "、".join("/%s/" % s for s in slugs[:6])
        events.append({
            "date": today, "kind": "update", "key": "site-wide-update",
            "ja": "サイト全体を更新（%dページ）: %s ほか" % (len(slugs), names),
            "en": "Site-wide update: %d pages, including %s" % (len(slugs), names),
        })
        added.append("site-wide-update")
        slugs = []
    for slug in slugs:
        langs = merged[slug]
        if "ja" in langs:
            old, new = langs["ja"]
        else:
            old, new = langs["en"]
        ja, en = _update_event_texts(slug, old, new)
        if "en" in langs:      # 英語ページも一緒に上がっていれば、英語文はそちらから作る
            en = _update_event_texts(slug, *langs["en"])[1]
        events.append({"date": today, "kind": "update", "key": slug, "ja": ja, "en": en})
        added.append(slug)
    if not added:
        return []
    try:
        with open(facts_path, "w", encoding="utf-8") as fh:
            json.dump(facts, fh, ensure_ascii=False, indent=1)
    except Exception:  # noqa: BLE001
        logger.exception("site_events の保存に失敗しました")
        return []
    return added


def _is_en_html(html: str) -> bool:
    """英語ページか（`<html lang="en">` で判定。hreflang は両言語にあるので使わない）。"""
    m = re.search(r"<html[^>]*>", html[:2000])
    return bool(m and re.search(r'lang="en', m.group(0)))


def _audit_gate_errors(base_dir: str, rel: str, new_text: str, old_text: str) -> list:
    """公開ゲート: ページ監査の ERROR のうち**今回の公開で新しく出たもの**だけ返す。

    「新しい劣化だけを止める」のが要点（既存の借金で公開が止まると作業が進まない）。
    ただし R4/R9（見出し・タイトルの年月が古い）は、**日付を新しくした公開**で
    起きているなら意味が変わるので、既存でも止める（11-19 の /mai/ がその型）。
    """
    try:
        import page_audit
    except Exception:  # noqa: BLE001
        return []
    specs_path = os.path.join(WORKSPACE_LOCAL_DIR, "data", "og_specs.json")
    facts_path = os.path.join(WORKSPACE_LOCAL_DIR, "data", "facts.json")
    try:
        with open(specs_path, encoding="utf-8") as fh:
            specs = json.load(fh)
    except Exception:  # noqa: BLE001
        specs = {}
    try:
        with open(facts_path, encoding="utf-8") as fh:
            facts = json.load(fh)
    except Exception:  # noqa: BLE001
        facts = {}
    new_findings = page_audit.blocking_errors(rel, new_text, specs, facts)
    if not new_findings:
        return []
    new_codes = {c for c, _ in new_findings}
    old_codes = set()
    if old_text:
        old_codes = page_audit.error_codes(rel, old_text, specs, facts)
    out = []
    for code, msg in new_findings:
        if code not in old_codes:
            out.append("%s: %s" % (code, msg))
        elif code in ("R4", "R9", "R12", "R13", "R14"):
            # 年表の重複・捏造日付・出典なしのリリース日は「既存の借金」でも止める。
            # 事実の誤りを公開し続ける方が高くつく（2026-11-21）。
            if code in ("R12", "R13", "R14"):
                out.append("%s: %s" % (code, msg))
            elif _date_modified(new_text) > (_date_modified(old_text) or ""):
                out.append("%s: %s（日付だけ新しくして中身が古いまま）" % (code, msg))
    return out


STRUCTURE_ALLOW_PATH = os.path.join(WORKSPACE_LOCAL_DIR, "data", "structure_allow.json")


def _structure_gate_errors(rel: str, new_text: str, old_text: str) -> list:
    """公開ゲート: ページ構造の**後退**を止める（2026-11-21 追加）。

    なぜ:
        2026-11-21 の /china-ai/ は「MiniMax が Kimi と同じカードに入っている」
        という指摘に対し、**独立セクションを新設**して直した（カードを別のブロックへ
        移すだけでよかった）。依頼より大きい変更が入り、目次も増えた。
        既存のゲートは文章と表しか見ておらず、**構造の変化**は誰も見ていない。

    見るもの（既存ページの上書き公開のときだけ）:
      * `class="section-title"` が増えた（新しい塊を作った）
      * `class="lab-card"` が減った（カードを別の場所へ逃がした）

    「本当にセクションを増やす必要がある」変更は data/structure_allow.json に
    意図を書いて明示的に許可する（黙って通す道は作らない）。
        例: {"china-ai/index.html": {"sections": 8}}
    """
    if not old_text or not rel.endswith("index.html"):
        return []

    def count(text, cls):
        return len(re.findall(r'class="%s"' % re.escape(cls), text))

    allow = {}
    try:
        with open(STRUCTURE_ALLOW_PATH, encoding="utf-8") as fh:
            allow = ((json.load(fh) or {}).get(rel) or {})
    except Exception:  # noqa: BLE001
        allow = {}

    out = []
    o, n = count(old_text, "section-title"), count(new_text, "section-title")
    limit = allow.get("sections")
    if n > o and (limit is None or n > int(limit)):
        out.append("STRUCTURE: セクションが %d→%d に増えている。不具合の修正は**既存の"
                   "構造の中**を直す（カードの所属を変える等）。新しいセクションが"
                   "必要なら data/structure_allow.json に意図を書いて許可する" % (o, n))
    o, n = count(old_text, "lab-card"), count(new_text, "lab-card")
    floor = allow.get("cards")
    if n < o and (floor is None or n < int(floor)):
        out.append("STRUCTURE: カードが %d→%d に減っている。カードを別のセクションへ"
                   "移していないか（同じグリッド内に残すのが原則）" % (o, n))
    return out


def _render_site_from_ledger(base_dir: str) -> list:
    """台帳（/workspace/data/facts.json）からサイトを描画する（LLMコスト0）。

    2026-11-17 追加・順序の変更:
        描画を「公開の後ろ」でしか呼んでいなかったため、**レビュー通過後に描画で
        料金表の `<tbody>` が入れ替わり、誰も見ていない状態で公開された**
        （Xiaomi の表に Kimi の行が入っていた事故）。
        公開の**前**に描画し、その結果にゲートを当てる（描画→検査→公開）。
    失敗しても公開は止めない（描画できない＝従来どおり手編集のまま公開）。
    """
    import importlib.util

    script = os.path.join(WORKSPACE_LOCAL_DIR, "tools", "render_site.py")
    if not os.path.exists(script):
        return []
    try:
        spec = importlib.util.spec_from_file_location("akira_render_pre", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.run(pathlib.Path(base_dir), pathlib.Path(WORKSPACE_LOCAL_DIR))
    except Exception:  # noqa: BLE001
        logger.exception("公開前の描画に失敗しました（描画なしで公開を続行します）")
        return []


def _render_and_publish_entrypoints(base_dir: str, s3) -> list:
    """新規ページ登録の直後に、トップ・更新履歴・sitemap を作り直して公開する。

    なぜ（2026-11-15 の実測）:
        手順は「render_site → site_upload」なので、`site_upload` が
        `site_events` を登録した時点では**すでに描画が終わっている**。
        そのため新しいページは台帳には載るのに、**トップと /changelog/ には
        翌ランまで出ない**（okamo「毎回俺が手でHTMLを直してる」の正体）。
        登録したら**その場で描き直して公開する**。

    戻り値: 公開したキーの一覧。
    """
    changed = _render_site_from_ledger(base_dir)

    # 生成物のうち「入り口」になるものだけ公開する（ページ本体は既に上がっている）
    targets = ["index.html", "en/index.html", "changelog/index.html",
               "en/changelog/index.html", "sitemap.xml", "data/changelog.json"]
    published = []
    for rel in targets:
        f = os.path.join(base_dir, rel)
        if not os.path.exists(f):
            continue
        try:
            s3.upload_file(f, LLM_SITE_BUCKET, rel,
                           ExtraArgs={"ContentType": _content_type(rel),
                                       "CacheControl": _cache_control(rel)})
            _invalidation_paths.append("/" + rel)
            published.append(rel)
        except Exception:  # noqa: BLE001
            continue
    # 変化が無いならアップロードもしない（無駄な invalidation を避ける）
    return published if changed else []


@tool
def site_upload(local_path: str, site_prefix: str = "") -> dict:
    """ローカル作業フォルダ（SITE_LOCAL_DIR）内のファイル/フォルダをS3に一括アップロードする。

    publish_file_to_site と違い全文を文字列で渡す必要がなく、ローカルで編集した
    ファイルやフォルダをまとめて公開できる。Content-Type判定とCloudFront invalidationは
    自動処理される。レビュー完了後の一括公開に使うこと。

    /timeline/ と /en/timeline/ を含むアップロードでは、先に整合ゲート（並び順・
    日付形式・日英のエントリ一致）を機械検査し、違反があればその2ファイルだけ
    アップロードしない（2026-11-14: 追記で降順が崩れ、ENだけ5件欠けたまま公開された）。

    Args:
        local_path: SITE_LOCAL_DIR からの相対パス（例: "pricing/" でフォルダ全体、
                    "." でサイト全体）。絶対パスは SITE_LOCAL_DIR 配下のみ許可
        site_prefix: S3キーの先頭に付けるプレフィックス（通常は不要）
    """
    base_dir = os.path.abspath(SITE_LOCAL_DIR)
    src = _resolve_local_path(local_path)
    if not os.path.exists(src):
        return {"status": "failed", "reason": f"存在しません: {local_path}"}

    # --- 公開前に台帳から描画する（2026-11-17 追加）---
    # 2026-11-17 05:33 の事故: レビュー通過後に（この site_upload の後半で）描画が
    # 走り、料金表の <tbody> が位置ずれで入れ替わった。それがそのまま公開された。
    # レビューは「描画前のファイル」を見ていたので、誰も気づけない構造だった。
    # 描画→ゲート→公開の順に固定し、**公開する実物**にゲートを当てる。
    render_changed = _render_site_from_ledger(base_dir)

    if os.path.isfile(src):
        if _is_skipped_upload_name(os.path.basename(src)):
            return {"status": "skipped", "reason": f"除外対象: {os.path.basename(src)}"}
        files = [src]
    else:
        files = []
        for root, _dirs, names in os.walk(src):
            for name in names:
                if _is_skipped_upload_name(name):
                    continue
                files.append(os.path.join(root, name))

    # --- 公開ゲート: timeline の整合（決定論的・LLMコスト0）---
    timeline_errors = []
    target_rels = {os.path.relpath(f, base_dir).replace(os.sep, "/") for f in files}
    if target_rels & set(TIMELINE_KEYS):
        timeline_errors = _timeline_integrity_errors(base_dir)

    # --- 公開ゲート: 重複・孤立リンク（2026-11-15 追加）---
    # 同じ文章の重複と「どこからもリンクされないページ」は、人が気づくまで残る。
    integrity_errors = []
    shape_errors = []
    if any(r.endswith("index.html") for r in target_rels):
        integrity_errors = _site_integrity_errors(base_dir)
        shape_errors = _page_shape_errors(base_dir)
    facts_errors = []
    if any(r.endswith(("index.html", "models.json")) for r in target_rels):
        facts_errors = _facts_consistency_errors(base_dir)
    section_errors = []
    if any(r.endswith("index.html") for r in target_rels):
        section_errors = _section_errors(base_dir)
    css_errors = []
    if any(r.endswith(("index.html", "style.css")) for r in target_rels):
        css_errors = _css_contract_errors(base_dir)

    s3 = boto3.client("s3", region_name=AWS_REGION)
    uploaded, rejected, registered = [], [], []
    updated_pages = []          # (slug, old_html, new_html) — 中身が変わった既存ページ
    for f in files:
        rel = os.path.relpath(f, base_dir).replace(os.sep, "/")
        key = rel if not site_prefix else f"{site_prefix.strip('/')}/{rel}"
        if timeline_errors and rel in TIMELINE_KEYS:
            rejected.append({"key": key, "errors": timeline_errors})
            continue
        if integrity_errors and rel.endswith("index.html"):
            hits = [msg for page, msg in integrity_errors
                    if page == rel or page == ""]
            if hits:
                rejected.append({"key": key, "errors": hits})
                continue
        if facts_errors and (rel.endswith("index.html") or rel == DATA_MODELS_KEY):
            rejected.append({"key": key, "errors": facts_errors})
            continue
        if shape_errors and rel.endswith("index.html"):
            # 日英の同格違反は ja 側の名前で出るので、en 側の公開も止める
            pair = rel[3:] if rel.startswith("en/") else "en/" + rel
            hits = [msg for page, msg in shape_errors
                    if page in (rel, pair, "")]
            if hits:
                rejected.append({"key": key, "errors": hits})
                continue
        if section_errors and rel.endswith("index.html"):
            # セクション境界・料金表の取り違え（2026-11-17）。日英は対で見る。
            pair = rel[3:] if rel.startswith("en/") else "en/" + rel
            hits = [msg for page, msg in section_errors
                    if page in (rel, pair, "")]
            if hits:
                rejected.append({"key": key, "errors": hits})
                continue
        # CSS部品の契約（描画されるための必須プロパティ）はサイト全体の話なので、
        # style.css だけでなく index.html の公開時にも一緒に止める。
        if css_errors and (rel == "assets/style.css" or rel.endswith("index.html")):
            rejected.append({"key": key, "errors": [msg for _, msg in css_errors]})
            continue
        # 新規ページ判定は「アップロード前」に取る（上書き後は常に既存になる）
        is_new = _s3_key_is_new(s3, key)
        # --- 公開ゲート: ページ監査（2026-11-19 追加）---
        # 「中身は古いのに日付だけ新しい」「新しい情報が本文の段落にしかない」
        # 「キービジュアルが古い」は既存の7ゲートを全部通っていた。
        # アップロード**前**に、公開する実物に対して検査する。
        old_html = ""
        if rel.endswith("index.html"):
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    new_html = fh.read()
            except OSError:
                new_html = ""
            if not is_new:
                try:
                    old_html = s3.get_object(Bucket=LLM_SITE_BUCKET, Key=key)[
                        "Body"].read().decode("utf-8", "replace")
                except Exception:  # noqa: BLE001
                    old_html = ""
            gate_hits = _audit_gate_errors(base_dir, rel, new_html, old_html) if new_html else []
            if not gate_hits and new_html and old_html:
                # 構造の後退（セクション増・カード減）も同じ場所で止める
                gate_hits = _structure_gate_errors(rel, new_html, old_html)
            if gate_hits:
                rejected.append({"key": key, "errors": gate_hits})
                continue
        if key == DATA_MODELS_KEY:
            try:
                with open(f, "rb") as fh:
                    body = fh.read()
            except OSError as e:
                rejected.append({"key": key, "errors": ["読み込み失敗: %s" % e]})
                continue
            errors = _site_data_errors(key, body)
            if errors:
                rejected.append({"key": key, "errors": errors})
                continue
            s3.put_object(Bucket=LLM_SITE_BUCKET, Key=key, Body=body,
                          ContentType=_content_type(key),
                          CacheControl=_cache_control(key))
            _save_models_baseline(body)
        else:
            s3.upload_file(f, LLM_SITE_BUCKET, key,
                           ExtraArgs={"ContentType": _content_type(key),
                                      "CacheControl": _cache_control(key)})
        _invalidation_paths.append("/" + key)
        uploaded.append(key)
        # 新規ページなら site_events を自動登録（課題141）
        try:
            reg = _register_site_event(rel, base_dir, is_new=is_new)
            if reg:
                registered.append(reg)
        except Exception:  # noqa: BLE001
            pass
        # 既存ページは「中身が変わったか」で更新履歴に載せる（2026-11-19）
        if rel.endswith("index.html") and not is_new:
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    new_html = fh.read()
                if old_html and _content_signature(old_html) != _content_signature(new_html):
                    slug = rel[:-len("/index.html")]
                    if slug.startswith("en/"):
                        slug = slug[3:]
                    if slug and slug.split("/")[0] not in ("changelog", "glossary"):
                        updated_pages.append((slug, old_html, new_html))
            except Exception:  # noqa: BLE001
                pass
    # 公開したページの sitemap lastmod を揃える（render_site の出力に限らない）
    sitemap_bumped = bool(uploaded and _bump_sitemap_lastmod(base_dir, uploaded, s3))
    # 中身が変わった既存ページを更新履歴に足す（重複は関数側で弾く）
    try:
        registered += _register_site_updates(updated_pages)
    except Exception:  # noqa: BLE001
        logger.exception("更新履歴の自動登録に失敗しました")
    # 新規・更新を登録したなら、トップ・更新履歴を作り直して即公開する
    rendered = []
    if registered:
        rendered = _render_and_publish_entrypoints(base_dir, s3)
    # 触ったページは**次のランで必ず監査**する（2026-11-19）
    try:
        import page_audit

        page_audit.note_changed([r for r in uploaded if r.endswith("index.html")])
    except Exception:  # noqa: BLE001
        pass

    result: dict = {"status": "published", "count": len(uploaded), "uploaded": uploaded}
    if render_changed:
        result["rendered_before_publish"] = render_changed
    if registered:
        result["site_events_added"] = registered   # トップ/更新履歴に自動で載る
    if updated_pages:
        result["updated_pages"] = sorted({s for s, _, _ in updated_pages})
    if rendered:
        result["entrypoints_refreshed"] = rendered
    if sitemap_bumped:
        result["sitemap"] = "lastmod updated"
    if rejected:
        result["status"] = "published_partial" if uploaded else "rejected"
        result["reason"] = ("契約・整合ゲートに違反するファイルはアップロードしませんでした"
                            "（公開済みサイトは壊れていません）")
        result["rejected"] = rejected
        _record_gate_lesson("整合ゲートで公開を止めた",
                            [r.get("errors", [""])[0] for r in rejected])
    return result


@tool
def list_local_files(rel_path: str = "") -> dict:
    """ローカル作業フォルダ（SITE_LOCAL_DIR）内のファイル一覧を返す（list_site_files のローカル版）。

    Args:
        rel_path: SITE_LOCAL_DIR からの相対パス（例: "pricing/"。空で全体）
    """
    base_dir = os.path.abspath(SITE_LOCAL_DIR)
    base = _resolve_local_path(rel_path)
    if not os.path.isdir(base):
        return {"status": "failed", "reason": f"ディレクトリではありません: {rel_path}"}
    files = []
    for root, _dirs, names in os.walk(base):
        for name in names:
            if _is_skipped_upload_name(name):
                continue
            rel = os.path.relpath(os.path.join(root, name), base_dir).replace(os.sep, "/")
            files.append(rel)
    files.sort()
    return {"status": "ok", "path": rel_path or "/", "count": len(files), "files": files}


def flush_invalidations() -> None:
    """溜めたパスをまとめてCloudFront invalidationする（Runtime側から呼ぶ）。"""
    if not _invalidation_paths:
        return
    cf = boto3.client("cloudfront", region_name=AWS_REGION)
    paths = list(set(_invalidation_paths))[:30]
    if len(set(_invalidation_paths)) > 15:
        paths = ["/*"]  # 多い場合はワイルドカード1本の方が安い
    cf.create_invalidation(
        DistributionId=LLM_DIST_ID,
        InvalidationBatch={
            "Paths": {"Quantity": len(paths), "Items": paths},
            "CallerReference": f"akira-{int(time.time())}",
        },
    )
    _invalidation_paths.clear()


# --- 公開サイトの契約チェックと決定論的修復（2026-09-27 追加）------------------------
# 「静かな故障」（HTTPは200を返すが中身が壊れている）を毎朝の自動検査で拾う。
# ローカルのコピーではなく**公開中の現物**を見るのが要点（今回の事故はローカル・公開の
# 両方が同じ壊れ方をしていたため、ローカル検査だけでは検出できない）。
CONTRACT_GTAG = "G-MTH8T0ECG2"
CONTRACT_CALC_PAGES = ("calculator/index.html", "en/calculator/index.html")
CONTRACT_MAIN_PAGES = (
    "index.html", "pricing/index.html", "calculator/index.html",
    "en/index.html", "en/calculator/index.html", "en/pricing/index.html",
    "timeline/index.html", "china-ai/index.html", "multimodal/index.html",
    "glossary/index.html", "en/glossary/index.html",
)


def _http_get(url: str, timeout: int = 20) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "llm-data-hub-contract/1.0", "Cache-Control": "no-cache"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, b"", str(e)
    except Exception as e:  # noqa: BLE001
        return 0, b"", str(e)


def _url_to_key(path: str) -> str:
    rel = path.strip().lstrip("/").rstrip("/")
    return rel + "/index.html" if rel else "index.html"


def _sitemap_loc_keys(xml: bytes) -> set[str]:
    import re

    return {
        _url_to_key(loc.split("llm.okamomedia.tokyo", 1)[-1])
        for loc in re.findall(r"<loc>([^<]+)</loc>", xml.decode("utf-8", "replace"))
    }


def _published_html_keys() -> set[str]:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    keys: list[str] = []
    kwargs: dict = {"Bucket": LLM_SITE_BUCKET}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        keys += [o["Key"] for o in resp.get("Contents", [])]
        if not resp.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]
    return {k for k in keys if k.endswith(".html")}


def check_published_contracts() -> dict:
    """公開中サイトの契約を検査する（読取のみ・LLMコスト0）。"""
    violations: list[str] = []

    # C1. 計算機データ（公開中の現物）
    status, body, err = _http_get(f"{LLM_SITE_URL}/{DATA_MODELS_KEY}")
    if status != 200:
        violations.append("%s: HTTP %s で取得できません %s" % (DATA_MODELS_KEY, status, err))
    else:
        try:
            payload = json.loads(body.decode("utf-8"))
            violations += ["%s: %s" % (DATA_MODELS_KEY, e)
                           for e in validate_calculator_models(payload)]
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            violations.append("%s: JSONとして読めません: %s" % (DATA_MODELS_KEY, e))

    # C2. 計算機ページの必須要素（JSの配線が生きているか）
    for rel in CONTRACT_CALC_PAGES:
        status, body, err = _http_get(f"{LLM_SITE_URL}/{rel}")
        if status != 200:
            violations.append("%s: HTTP %s で取得できません %s" % (rel, status, err))
            continue
        text = body.decode("utf-8", "replace")
        if DATA_MODELS_KEY not in text:
            violations.append("%s: 計算機データ(%s)の読み込みが消えている" % (rel, DATA_MODELS_KEY))
        if CONTRACT_GTAG not in text:
            violations.append("%s: GA4タグが無い" % rel)

    # C3. sitemap と公開実体の一致
    status, body, err = _http_get(f"{LLM_SITE_URL}/sitemap.xml")
    if status != 200:
        violations.append("sitemap.xml: HTTP %s で取得できません %s" % (status, err))
    else:
        locs = _sitemap_loc_keys(body)
        keys = _published_html_keys() - {"404.html"}
        for p in sorted(locs - keys)[:10]:
            violations.append("sitemap.xml: %s の実体が公開されていません" % p)
        for p in sorted(keys - locs)[:10]:
            violations.append("sitemap.xml: %s がsitemapに載っていません" % p)

    # C4. 主要ページの疎通とGA4
    for rel in CONTRACT_MAIN_PAGES:
        status, body, err = _http_get(f"{LLM_SITE_URL}/{rel}")
        if status != 200:
            violations.append("%s: HTTP %s で取得できません %s" % (rel, status, err))
            continue
        if CONTRACT_GTAG not in body.decode("utf-8", "replace"):
            violations.append("%s: GA4タグが無い" % rel)

    # C5. 台帳の GA モデルが**公開中の**計算機データに居るか（2026-11-21 追加）
    #     11-21、Gemini 4 Neon は /timeline/ と /pricing/ に出ているのに
    #     /calculator/ だけ古いままだった（render は models.json を更新したが
    #     公開ツールが HTML しか上げていなかった）。ローカルの描画結果を見る
    #     既存ゲートでは捕まらないので、**公開中の現物**を台帳と突き合わせる。
    violations += _published_calculator_gaps()

    return {
        "violations": violations,
        "summary": "公開契約チェック: 違反 %d 件" % len(violations),
        "ok": not violations,
    }


def _published_calculator_gaps() -> list:
    """公開中の data/models.json に無い「台帳のGAモデル」を返す。

    台帳（/workspace/data/facts.json）と公開中の現物を突き合わせる。台帳が
    読めないときは何も言わない（誤検知で日次を止めない）。
    """
    import unicodedata

    def _n(text: str) -> str:
        return unicodedata.normalize("NFKC", str(text)).lower().replace(" ", "")

    try:
        with open(os.path.join(WORKSPACE_LOCAL_DIR, "data", "facts.json"),
                  encoding="utf-8") as fh:
            facts = json.load(fh)
    except Exception:  # noqa: BLE001
        return []
    status, body, _err = _http_get(f"{LLM_SITE_URL}/{DATA_MODELS_KEY}")
    if status != 200:
        return []          # 取得失敗は C1 が報告する
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return []
    have = _n(" ".join(str(m.get("name", "")) for m in payload.get("models", [])
                       if isinstance(m, dict)))
    gaps = []
    for mid, r in sorted((facts.get("models") or {}).items()):
        if (r.get("status") or "") != "ga":
            continue
        price = r.get("price") or {}
        if price.get("input") is None or price.get("output") is None:
            continue       # 単価が無いのは C1 側（ga-without-price）の担当
        # 台帳の名前は「Claude Fable 5.2 / Mythos 5.2」のように別名を含むことが
        # あり、計算機側は price.name（"Claude Fable 5.2"）で登録されている。
        # スラッシュ区切りの別名・price.name・id のどれかで一致すれば OK。
        cands = [price.get("name") or ""]
        for k in ("ja", "en"):
            cands += [x.strip() for x in str((r.get("names") or {}).get(k) or "").split("/")]
        cands += [mid]
        if any(_n(c) and _n(c) in have for c in cands):
            continue
        gaps.append("%s: 台帳はGAだが公開中の計算機データに無い"
                    "（render で models.json が変わったのに公開されていない疑い）"
                    " → publish_and_verify で描画し直して公開する" % mid)
    return gaps[:10]


def _restore_published_data_file(key: str = DATA_MODELS_KEY, dry_run: bool = False) -> dict:
    """公開中の計算機データを、契約合格済みベースラインから復元する（許可キー限定）。"""
    key = key.strip("/")
    if key != DATA_MODELS_KEY:
        return {"status": "rejected", "reason": "復元できるのは %s のみです" % DATA_MODELS_KEY}
    if not os.path.exists(BASELINE_MODELS_PATH):
        return {"status": "failed",
                "reason": "ベースラインが無いため復元できません: %s" % BASELINE_MODELS_PATH}
    with open(BASELINE_MODELS_PATH, "rb") as fh:
        baseline = fh.read()
    base_errors = _site_data_errors(key, baseline)
    if base_errors:
        return {"status": "failed", "reason": "ベースライン自体が契約違反です（要調査）",
                "errors": base_errors}

    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        live = s3.get_object(Bucket=LLM_SITE_BUCKET, Key=key)["Body"].read()
        live_errors = _site_data_errors(key, live)
    except Exception as e:  # noqa: BLE001
        live_errors = ["公開中のファイルを取得できません: %s" % e]
    if not live_errors:
        return {"status": "skipped", "reason": "公開中のデータは契約を満たしています（復元不要）"}
    if dry_run:
        return {"status": "dry_run", "reason": "復元が必要", "live_errors": live_errors}

    s3.put_object(Bucket=LLM_SITE_BUCKET, Key=key, Body=baseline,
                  ContentType=_content_type(key), CacheControl=_cache_control(key))
    _invalidation_paths.append("/" + key)
    flush_invalidations()
    return {"status": "restored", "key": key, "bytes": len(baseline),
            "live_errors": live_errors, "baseline": BASELINE_MODELS_PATH}


@tool
def verify_published_contracts() -> str:
    """公開中サイトの契約（計算機データのスキーマ・計算機ページの配線・sitemap整合・主要ページの疎通）を検査する。

    毎朝のランで自動実行され、日報にも結果が出る。公開後や異常時の単体確認にも使える。
    """
    res = check_published_contracts()
    lines = [res["summary"]]
    if res["violations"]:
        lines += ["  - %s" % v for v in res["violations"][:30]]
        if DATA_MODELS_KEY in " ".join(res["violations"]):
            lines.append("  → restore_published_data_file() で計算機データを復元できる"
                         "（ベースラインが正常な場合のみ）")
    else:
        lines.append("  公開サイトは契約を満たしています")
    return "\n".join(lines)


@tool
def restore_published_data_file(key: str = DATA_MODELS_KEY, dry_run: bool = False) -> dict:
    """公開中の計算機データが壊れている場合、ワークスペースのベースラインから復元する。

    許可キーは data/models.json のみ。ベースラインが契約検証に通らない場合は復元しない
    （誤った内容で上書きしないため）。料金内容の更新はエンジニアの通常作業で行う。

    Args:
        key: 復元対象（data/models.json のみ許可）
        dry_run: True なら判定だけして書き込まない
    """
    return _restore_published_data_file(key, dry_run)


@tool
def get_budget_status() -> dict:
    """当月のLLM費用と予算残額を確認する。"""
    return budget.check_budget()


@tool
def update_akira_config(key: str, content: str, note: str = "") -> dict:
    """Akira自身の設定（教訓/skills/サイト計画）を書き換える。
    翌日のFargate起動時から反映される。

    Args:
        key: "lessons"（過去の自分からの教訓。システムプロンプト末尾に合成される。
             古い教訓の整理・削除も可）/ "skill#<名前>" / "site_plan" のいずれか。
             システムプロンプトの既定部分はコード管理のため書き換え不可
        content: 新しい内容（全文）
        note: 変更理由のメモ
    """
    if key not in ("lessons", "site_plan") and not key.startswith("skill#"):
        return {
            "status": "rejected",
            "reason": "keyは lessons / site_plan / skill#<名前> のみ。既定のシステムプロンプトは書き換え不可",
        }
    limit = 4000 if key == "lessons" else 8000
    if len(content) > limit:
        return {
            "status": "rejected",
            "reason": ("%sは%d文字以内（現在%d字）。古い記録は archive に退避し、"
                       "要点だけ残して整理すること。規則は prompts.py の SITE_RULES に"
                       "あるので site_plan に再掲しない。"
                       % (key, limit, len(content))),
        }
    config_store.save_config(key, content, note)
    return {"status": "saved", "key": key, "effective": "翌日起動時から"}


@tool
def get_site_plan() -> str:
    """サイト運営計画（site_plan）を読む。作業の優先順位・予定タスク・過去の指摘事項はこれに従う。

    作業開始時に確認し、完了したら update_akira_config(key="site_plan") で対応状況を更新する。
    """
    return config_store.load_config("site_plan") or "（site_planは未設定）"


# =====================================================================
# GCP Workload Identity（AWS→GCPキーレス連携）
# GA4/BigQuery MCPが使う（main.py _wi_env()経由）。画像生成はGemini Developer APIに
# 切替済みのため、ここではWI構成ファイルの生成のみを行う
# =====================================================================
def _write_gcp_wi_config_file() -> str:
    """WI構成テンプレートからregion_url/urlを除いたADC設定ファイルを生成する（環境変数は一切変更しない）。

    【2026-07-09 検証済み】ECS FargateはEC2版IMDS(169.254.169.254)に到達できないため、
    credential_source.url/region_url/imdsv2_session_token_url経由の自動取得は使えない
    （実機テストで get_account_summaries / list_dataset_ids の呼び出しがいずれも
    `dial tcp 169.254.169.254:80: connect: invalid argument` で失敗することを確認済み）。
    そのためboto3で取得した凍結クレデンシャルをAWS_ACCESS_KEY_ID等としてenv経由で
    明示的に渡す方式（IMDSを一切使わない）にしている。安易にIMDSv2方式へ戻さないこと。
    """
    template_path = os.getenv("GCP_WORKLOAD_IDENTITY_TEMPLATE")
    if not template_path:
        raise RuntimeError("GCP_WORKLOAD_IDENTITY_TEMPLATE が未設定です。")

    with open(template_path) as f:
        config = json.load(f)
    for field in ("region_url", "url"):
        config.get("credential_source", {}).pop(field, None)

    config_file = os.path.abspath("gcp-workload-config.json")
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    return config_file


# =====================================================================
# 画像生成（Gemini Developer API / GEMINI_API_KEY）
# =====================================================================
@tool
def generate_and_publish_image(purpose: str, site_path: str) -> dict:
    """画像を生成してサイトに公開する（Gemini子育てママ用ツール）。

    Args:
        purpose: 画像の目的・内容（例: "LLM料金比較ページのOGP画像。サイト名 LLM Data Hub を含む"）
        site_path: 公開先パス（例: "assets/ogp-pricing.png"）

    Returns:
        dict: status, url
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY が未設定です。")

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
    resp = client.models.generate_content(
        model=IMAGE_MODEL_ID,
        contents=f"次の目的のWeb用画像を1枚生成してください。\n目的: {purpose}",
        config=config,
    )

    image_bytes, mime = None, "image/png"
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            image_bytes = part.inline_data.data
            mime = part.inline_data.mime_type or mime
    if not image_bytes:
        return {"status": "failed", "reason": "画像データが返却されませんでした"}

    site_path = site_path.lstrip("/")
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.put_object(Bucket=LLM_SITE_BUCKET, Key=site_path, Body=image_bytes,
                  ContentType=mime, CacheControl=_cache_control(site_path))
    _invalidation_paths.append(f"/{site_path}")

    budget.record_usage(IMAGE_MODEL_ID, 0, 0, images=1, purpose=f"image: {purpose[:100]}")
    return {"status": "published", "url": f"{LLM_SITE_URL}/{site_path}"}


# =====================================================================
# スクリーンショット取得（ApiFlash）+ 画像読み取り
# =====================================================================
def _cache_bust(url: str) -> str:
    """「今の見た目」を取りに行くためのキャッシュ跨ぎ（2026-11-17 追加）。

    なぜ:
        OGカードを差し替えた直後、CloudFront が古い画像を返すために
        **「直っていない」と誤認する**事故が起きた（11-17 okamo指摘）。
        HTML/画像のURLに `?v=<生成日>` を付けてはいるが、検証（スクショ・画像の
        視認）は「公開物そのもの」を見たいので、毎回ユニークな `_cb` を足して
        キャッシュ層を跨ぐ。

    http(s) 以外（file: など）はそのまま返す。
    """
    try:
        from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

        p = urlsplit(url)
        if p.scheme not in ("http", "https"):
            return url
        q = dict(parse_qsl(p.query, keep_blank_values=True))
        q["_cb"] = str(int(time.time() * 1000))
        return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))
    except Exception:  # noqa: BLE001
        return url


@tool
def take_screenshot(url: str, site_path: str = "", wait_until: str = "page_loaded",
                    width: int = 1280, height: int = 720) -> dict:
    """指定URLのスクリーンショットをApiFlashで取得し、ローカルに保存する。
    戻り値の path を image_reader ツールに渡すとLLMが画像を視認できる。
    UXチェックやデザイン確認などの「見た目を判断する」用途に使う。

    site_path を指定した場合のみS3にも公開する（指定なしならローカルパスのみ返す）。
    無料枠（月100枚まで）で運用中。エラー時は "FREE_TIER_EXHAUSTED" の可能性あり。

    Args:
        url: スクリーンショット対象のURL（必須）
        site_path: サイト保存先パス（例: "okamo/2026-07-06_openai.png"）。
                   指定した場合のみS3公開される。未指定ならローカルのみ
        wait_until: ページ読み込み待機条件。デフォルト "page_loaded"
        width: ビューポート幅（デフォルト1280）
        height: ビューポート高さ（デフォルト720）

    Returns:
        dict: path（ローカルファイルパス。image_readerに渡す）。
              site_path指定時は url（公開URL）も含む。失敗時は reason
    """
    import tempfile
    import urllib.request
    import urllib.parse

    access_key = os.getenv("APIFLASH_ACCESS_KEY", "")
    if not access_key:
        return {"status": "failed", "reason": "APIFLASH_ACCESS_KEY が未設定です"}

    params = {
        "access_key": access_key,
        "url": _cache_bust(url),
        "wait_until": wait_until,
        "width": str(width),
        "height": str(height),
        "format": "png",
    }
    api_url = "https://api.apiflash.com/v1/urltoimage?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Akira/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            image_bytes = resp.read()

        if len(image_bytes) < 200:
            try:
                err = json.loads(image_bytes.decode("utf-8"))
                return {"status": "failed", "reason": f"ApiFlash error: {err}"}
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # ローカル一時ファイルに保存（image_reader に渡す用）
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_bytes)
            local_path = f.name

        result: dict = {"status": "published", "path": local_path}

        # S3公開は site_path 指定時のみ
        if site_path:
            site_path = site_path.lstrip("/")
            s3 = boto3.client("s3", region_name=AWS_REGION)
            s3.put_object(Bucket=LLM_SITE_BUCKET, Key=site_path, Body=image_bytes,
                          ContentType="image/png",
                          CacheControl=_cache_control(site_path))
            _invalidation_paths.append(f"/{site_path}")
            result["url"] = f"{LLM_SITE_URL}/{site_path}"

        return result

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        hint = ""
        if e.code == 402 or "quota" in body.lower():
            hint = "（無料枠上限の可能性があります）"
        return {"status": "failed", "reason": f"ApiFlash HTTP {e.code}: {body}{hint}"}
    except Exception as e:
        return {"status": "failed", "reason": str(e)}


@tool
def fetch_image_from_url(image_url: str) -> dict:
    """URLから画像を取得し、Converse API形式（生バイナリ）で返す。
    image_reader はローカルファイルのみ対応のため、Web上の画像はURLから
    直接ダウンロードして一時ファイルに保存し、image_reader に渡す。
    image_reader が PIL でフォーマット検出と変換を行う。
    対応フォーマット: PNG, JPEG, GIF, WebP

    Args:
        image_url: 画像のURL（必須）

    Returns:
        dict: LLM視認可能な画像データ（image_reader の生の戻り値）
    """
    import tempfile
    import requests
    from strands_tools import image_reader as _image_reader_module
    _image_reader = _image_reader_module.image_reader

    content_type = ""
    response = requests.get(_cache_bust(image_url), timeout=30)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "image/png").split(";")[0].strip()

    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    ext = ext_map.get(content_type, ".png")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(response.content)
        tmp_path = f.name

    try:
        result = _image_reader({"toolUseId": "tmp", "input": {"image_path": tmp_path}})
    finally:
        os.unlink(tmp_path)

    return result


# =====================================================================
# 永続ワークスペース（Fargateの使い捨てFSをS3と同期して翌日に持ち越す）
# - restore_workspace(): タスク開始時に S3→ローカル全件復元（run_daily から呼ぶ）
# - save_workspace():    タスク終了時にローカル→S3保存（例外/タイムアウト時も finally で呼ぶ）
# - load_workspace_tools(): /workspace/tools/*.py の TOOL 変数を自作ツールとして自動登録
#
# 設計メモ:
# - バケットは非公開の akira-workspace（公開サイト用バケットはCloudFront経由で丸見えのため使わない）
# - 保存は upsert-only（リモート側の削除はしない）。誤って rm -rf してもS3の前回分は消えない
# - 除外: __pycache__/.git/node_modules/.venv、*.pyc、隠しファイル、editorの .bak
# =====================================================================
_WORKSPACE_EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".venv", ".uv-cache"}


def _is_workspace_excluded(name: str) -> bool:
    """ワークスペースの同期から除外する作業ゴミ判定。"""
    return (
        name in _WORKSPACE_EXCLUDE_DIRS
        or name.startswith(".")
        or name.endswith((".pyc", ".pyo"))
        or _is_skipped_upload_name(name)
    )


def _collect_workspace_files(base_dir: str) -> list[dict]:
    """ワークスペース配下の同期対象ファイルを列挙する（除外適用済み）。

    Returns: [{"abs": 絶対パス, "rel": 相対パス, "size": バイト, "mtime": 更新時刻}]
    """
    out = []
    for root, dirs, names in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not _is_workspace_excluded(d)]
        for name in names:
            if _is_workspace_excluded(name):
                continue
            abs_path = os.path.join(root, name)
            try:
                st = os.stat(abs_path)
            except OSError:
                continue
            out.append({
                "abs": abs_path,
                "rel": os.path.relpath(abs_path, base_dir).replace(os.sep, "/"),
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
    return out


def restore_workspace() -> dict:
    """S3のワークスペースをローカルに全件復元する（タスク開始時に呼ぶ）。

    バケット未作成・空でもエラーにせず失敗ステータスを返す（日次運用を止めない）。
    """
    base_dir = os.path.abspath(WORKSPACE_LOCAL_DIR)
    os.makedirs(base_dir, exist_ok=True)
    s3 = boto3.client("s3", region_name=AWS_REGION)
    keys: list[str] = []
    kwargs: dict = {"Bucket": WORKSPACE_BUCKET}
    try:
        while True:
            resp = s3.list_objects_v2(**kwargs)
            keys += [o["Key"] for o in resp.get("Contents", [])]
            if not resp.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
    except s3.exceptions.NoSuchBucket:
        return {"status": "failed", "reason": f"バケット未作成: {WORKSPACE_BUCKET}"}
    except boto3.exceptions.Boto3Error as e:
        return {"status": "failed", "reason": f"S3 list 失敗: {e}"}

    restored = []
    for key in keys:
        parts = key.split("/")
        if any(_is_workspace_excluded(p) for p in parts) or key.endswith("/"):
            continue
        local = os.path.join(base_dir, key)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        s3.download_file(WORKSPACE_BUCKET, key, local)
        restored.append(key)
    return {"status": "restored", "dest_dir": base_dir, "count": len(restored)}


def save_workspace() -> dict:
    """ローカルワークスペースをS3へ保存する（タスク終了時に finally で呼ぶ）。

    - 新しいファイルから優先してアップロードし、合計上限（WORKSPACE_MAX_TOTAL_BYTES）を
      超えた分は保存せず報告する（1ファイル上限 WORKSPACE_MAX_FILE_BYTES も同様）
    - upsert-only: S3上の既存ファイルを削除しない（誤削除に強い。不要になったら
      エンジニアに明示的に報告してもらう運用）
    """
    base_dir = os.path.abspath(WORKSPACE_LOCAL_DIR)
    if not os.path.isdir(base_dir):
        return {"status": "skipped", "reason": "ローカルワークスペースが存在しません"}

    files = _collect_workspace_files(base_dir)
    if not files:
        return {"status": "skipped", "reason": "保存対象なし"}

    oversized = [f["rel"] for f in files if f["size"] > WORKSPACE_MAX_FILE_BYTES]
    files = [f for f in files if f["size"] <= WORKSPACE_MAX_FILE_BYTES]
    files.sort(key=lambda f: f["mtime"], reverse=True)  # 新しいものを優先

    s3 = boto3.client("s3", region_name=AWS_REGION)
    uploaded, total, capped = [], 0, []
    try:
        for f in files:
            if total + f["size"] > WORKSPACE_MAX_TOTAL_BYTES:
                capped.append(f["rel"])
                continue
            s3.upload_file(f["abs"], WORKSPACE_BUCKET, f["rel"])
            total += f["size"]
            uploaded.append(f["rel"])
    except boto3.exceptions.Boto3Error as e:
        return {"status": "failed", "reason": f"S3 upload 失敗: {e}", "uploaded": uploaded}
    result = {"status": "saved", "count": len(uploaded), "total_bytes": total, "uploaded": uploaded}
    if oversized:
        result["skipped_oversized"] = oversized
    if capped:
        result["skipped_total_cap"] = capped
    return result


# --- ワークスペースのバックアップ整理（2026-09-27 追加）------------------------------
# notes/backup-* は日付つきスナップショット。放っておくと増え続け「どれが正か」が
# 分からなくなる（2026-09-27時点で notes/backup-* は89ファイル・1.79MB、バケット全体では
# 旧バージョンが634件）。古い世代だけを消す道具を用意する。
# 削除対象は notes/backup で始まる日付つきキーのみ。IAM の DeleteObject も
# arn:aws:s3:::akira-workspace/notes/backup* に限定してある
# （backup- と backup_ の両方。notes/ 全体や他プレフィックスは対象外）。
# backup-* だと backup_ 世代が AccessDenied になり、整理全体が例外で落ちる。
# （ワークスペース全体は upsert-only のまま＝「消えない」安全設計は維持。
#  2026-09-27の計算機事故はこの設計に救われた）。
# 安全弁: 日付が読めないキーには触らない／最新世代は必ず残す／keep_days は最低3日。
WORKSPACE_BACKUP_PREFIX = "notes/backup"
BACKUP_KEEP_DAYS_MIN = 3
_BACKUP_DATE_RE = re.compile(r"backup[-_](\d{4})-?(\d{2})-?(\d{2})")


def _backup_generation(key: str) -> tuple[str, str] | None:
    """バックアップのキーから (世代キー, 日付YYYY-MM-DD) を返す。判定できなければ None。

    対応する命名: notes/backup-2026-09-15/<file> / notes/backup_20260925/<file> /
    notes/backup_20260927_index.html（単体ファイル形式）
    """
    if not key.startswith(WORKSPACE_BACKUP_PREFIX):
        return None
    m = _BACKUP_DATE_RE.search(key)
    if not m:
        return None
    try:
        iso = date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None
    return key[: m.end()], iso


def _rotate_workspace_backups(keep_days: int = 7, dry_run: bool = False) -> dict:
    """notes/backup-* の古い世代を削除する（最新世代は必ず残す）。"""
    keep_days = max(BACKUP_KEEP_DAYS_MIN, int(keep_days))
    s3 = boto3.client("s3", region_name=AWS_REGION)
    keys: list[str] = []
    kwargs: dict = {"Bucket": WORKSPACE_BUCKET, "Prefix": WORKSPACE_BACKUP_PREFIX}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        keys += [o["Key"] for o in resp.get("Contents", [])]
        if not resp.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]

    gens: dict[str, str] = {}
    for key in keys:
        got = _backup_generation(key)
        if not got:
            continue
        gen, iso = got
        if gen not in gens or iso > gens[gen]:
            gens[gen] = iso
    if not gens:
        return {"status": "skipped", "reason": "日付つきバックアップなし",
                "kept_generations": [], "deleted_count": 0}

    newest = max(gens.values())
    newest_gens = {g for g, d in gens.items() if d == newest}
    cutoff = (date.fromisoformat(newest) - timedelta(days=keep_days)).isoformat()
    to_delete = [g for g, d in gens.items()
                 if d < cutoff and g not in newest_gens]  # 最新世代は無条件で残す
    kept = sorted(g for g in gens if g not in to_delete)

    if dry_run:
        return {"status": "dry_run", "newest": newest, "cutoff": cutoff,
                "kept_generations": kept, "delete_generations": sorted(to_delete),
                "delete_files": sum(1 for k in keys
                                    if any(k.startswith(g) for g in to_delete))}

    deleted: list[str] = []
    for gen in to_delete:
        for key in [k for k in keys if k.startswith(gen)]:
            if not key.startswith(WORKSPACE_BACKUP_PREFIX):  # 二重の安全弁
                continue
            s3.delete_object(Bucket=WORKSPACE_BUCKET, Key=key)
            deleted.append(key)
    return {"status": "rotated", "newest": newest, "cutoff": cutoff,
            "deleted_count": len(deleted), "deleted_generations": sorted(to_delete),
            "kept_generations": kept, "deleted": deleted[:20]}


@tool
def rotate_workspace_backups(keep_days: int = 7, dry_run: bool = False) -> dict:
    """バックアップ（notes/backup-*）の古い世代を削除してワークスペースを整理する。

    最新世代より keep_days 日より古い世代だけを削除する。最新世代と日付が読めない
    キーには触らない。削除できるのは notes/backup で始まるキーのみ
    （backup- と backup_。IAM も notes/backup* に限定済み）。

    Args:
        keep_days: 残す日数（最低3日。既定7日）
        dry_run: True なら削除せず対象だけ報告する
    """
    return _rotate_workspace_backups(keep_days, dry_run)


def load_workspace_tools() -> list:
    """/workspace/tools/*.py を自作ツールとしてロードする。

    各ファイルは `from strands import tool` の @tool を付けた関数を
    モジュール変数 TOOL に代入して定義する（1ファイル1ツール）。
    - 1ファイルでもimportに失敗したらスキップして続行（1個の壊れたツールで
      日次実行全体を止めない）
    - 同名ツールの重複・上限件数（WORKSPACE_TOOLS_MAX）もガード
    """
    import glob
    import importlib.util
    import sys

    tools_dir = os.path.join(os.path.abspath(WORKSPACE_LOCAL_DIR), "tools")
    if not os.path.isdir(tools_dir):
        return []

    loaded: list = []
    seen_names: set[str] = set()
    for path in sorted(glob.glob(os.path.join(tools_dir, "*.py"))):
        if len(loaded) >= WORKSPACE_TOOLS_MAX:
            break
        stem = os.path.basename(path)[:-3]
        if stem.startswith("_"):
            continue  # _XXX.py は「まだ未完成」の合図として無視
        try:
            modname = f"akira_ws_tool_{stem}"
            spec = importlib.util.spec_from_file_location(modname, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[modname] = module
            spec.loader.exec_module(module)
            candidate = getattr(module, "TOOL", None)
            if candidate is None:
                # TOOL代入の書き忘れ対策: @tool 付き関数が1個だけならそれを TOOL とみなす
                # （複数ある場合は曖昧なのでスキップ。変数名からは意図が読めないため）
                decorated = [
                    v for v in vars(module).values()
                    if hasattr(v, "tool_spec") and getattr(v, "tool_name", None)
                ]
                if len(decorated) == 1:
                    candidate = decorated[0]
            if candidate is None or not hasattr(candidate, "tool_spec"):
                raise ValueError("@tool を付けた TOOL 変数が定義されていません")
            tool_name = getattr(candidate, "tool_name", stem)
            if tool_name in seen_names:
                continue  # 同名は先勝ち
            seen_names.add(tool_name)
            loaded.append(candidate)
        except Exception as e:
            print(f"[workspace] ツールのロードをスキップ: {os.path.basename(path)}: {e}")
    return loaded


@tool
def list_workspace_files(rel_path: str = "") -> dict:
    """永続ワークスペース（翌日も残る持ち越し作業場）内のファイル一覧を返す。

    /workspace はタスク終了時にS3へ保存され、翌朝の起動時に自動復元される。
    前日までの cache/（一次情報スナップショット）・parts/（再利用素材）・
    drafts/（持ち越し原稿）・notes/（メモ）を探すのに使う。
    内容は file_read に絶対パス（例: /workspace/cache/pricing.md）で渡して読む。

    Args:
        rel_path: ワークスペースからの相対パス（例: "cache/"。空で全体）
    """
    base_dir = os.path.abspath(WORKSPACE_LOCAL_DIR)
    base = os.path.abspath(os.path.join(base_dir, rel_path.lstrip("/")))
    if base != base_dir and not base.startswith(base_dir + os.sep):
        return {"status": "failed", "reason": f"パスは {base_dir} 配下に限定されています: {rel_path}"}
    if not os.path.isdir(base):
        return {"status": "failed", "reason": f"ディレクトリが存在しません: {rel_path}"}
    files = []
    for root, _dirs, names in os.walk(base):
        for name in names:
            if _is_workspace_excluded(name):
                continue
            p = os.path.join(root, name)
            try:
                files.append({
                    "path": os.path.relpath(p, base_dir).replace(os.sep, "/"),
                    "size": os.path.getsize(p),
                })
            except OSError:
                continue
    files.sort(key=lambda f: f["path"])
    return {"status": "ok", "path": rel_path or "/", "count": len(files), "files": files}


# ---------------------------------------------------------------------------
# 公開と検証を1呼び出しにまとめる（2026-11-21 追加）
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 公開対象の決定（HTML と それ以外）
# 2026-11-21: publish_and_verify が **HTML しか上げていなかった** ため、
# render が data/models.json を更新しても計算機だけ古いままだった
# （Gemini 4 Neon が /timeline/ /pricing/ には出るのに /calculator/ に無い）。
# 描画が変えたファイルは、HTML でなくても公開対象にする。
def _publish_targets(base_dir: str, rendered: list, paths: str = "") -> tuple:
    """(HTMLのリスト, HTML以外のリスト) を返す。重複は除く。"""
    html_targets: list[str] = []
    other_targets: list[str] = []

    def _add(rel: str) -> None:
        rel = rel.replace(os.sep, "/")
        (html_targets if rel.endswith(".html") else other_targets).append(rel)

    for rel in rendered or []:
        _add(rel)
    base = os.path.abspath(base_dir)
    for p in [x.strip() for x in (paths or "").split(",") if x.strip()]:
        # パスは base_dir 配下に限定する（SITE_LOCAL_DIR 固定にしない。テストや
        # 別ディレクトリへの描画でも同じ関数を使えるようにするため）
        f = os.path.abspath(p if os.path.isabs(p) else os.path.join(base, p.lstrip("/")))
        if f != base and not f.startswith(base + os.sep):
            raise ValueError("パスは %s 配下に限定されています: %s" % (base, p))
        if os.path.isdir(f):
            for root, _dirs, files in os.walk(f):
                for name in files:
                    if _is_skipped_upload_name(name):
                        continue
                    _add(os.path.relpath(os.path.join(root, name), base))
        else:
            if _is_skipped_upload_name(os.path.basename(f)):
                continue
            _add(os.path.relpath(f, base))

    def _uniq(items: list[str]) -> list[str]:
        seen, out = set(), []
        for t in items:
            if t.endswith("index.html"):
                if t in seen:
                    continue
                seen.add(t)
            elif t in seen:
                continue
            else:
                seen.add(t)
            out.append(t)
        return out

    return _uniq(html_targets), _uniq(other_targets)


def _same_as_s3(s3, key: str, local_path: str) -> bool:
    """S3 の現物とローカルが同一か（上げ直す必要が無いかの判定）。"""
    import hashlib

    try:
        head = s3.head_object(Bucket=LLM_SITE_BUCKET, Key=key)
    except Exception:  # noqa: BLE001
        return False
    try:
        if head.get("ContentLength") != os.path.getsize(local_path):
            return False
        etag = str(head.get("ETag", "")).strip('"')
        if "-" in etag:            # マルチパートは md5 ではない
            return False
        with open(local_path, "rb") as fh:
            return hashlib.md5(fh.read()).hexdigest() == etag
    except Exception:  # noqa: BLE001
        return False


@tool
def publish_and_verify(paths: str = "", live: bool = True) -> dict:
    """描画 → ゲート → 公開 → キャッシュ破棄 → **公開URLの実物照合** を1回でやる。

    なぜ:
        2026-11-21 の実測で、エンジニアは1回の依頼で **83回**ツールを叩いていた。
        その大半は `render_site → check_* → site_upload → purge_cdn → verify_publish
        → 再確認` の**同じ手順の繰り返し**で、しかも「残り呼び出し数」を理由に
        依頼項目を自分で削っていた（2番が丸ごと落ちた）。
        手順が決まっているものは1つのツールに畳んで、判断の余地を減らす。

    何をするか:
        1. 台帳（data/facts.json）から timeline/pricing/changelog/トップを描画
        2. 公開する各HTMLに**公開ゲート**（ページ監査・構造の後退・決定論ゲート）を当てる
        3. 通ったものだけ S3 へアップロード（Cache-Control 付き）
        4. CloudFront の invalidation をまとめて発行
        5. 公開URLを取得して**ローカルと同一バイトか**を照合（伝播待ちは最大3回）
        6. 結果を trace に残す

    Args:
        paths: 追加で公開したいパス（"china-ai/" や "pricing/index.html " をカンマ区切り）。
               空なら「描画で変わったファイル」だけを対象にする
        live: 公開後に実URLを取得して照合するか（既定 true）
    """
    import hashlib
    import time as _time

    base_dir = os.path.abspath(SITE_LOCAL_DIR)
    s3 = boto3.client("s3", region_name=AWS_REGION)
    result: dict = {"rendered": [], "published": [], "rejected": [],
                    "live": {"checked": 0, "mismatch": [], "pending": []}}

    # 1. 描画（失敗しても公開は続ける）
    try:
        result["rendered"] = _render_site_from_ledger(base_dir)
    except Exception:  # noqa: BLE001
        logger.exception("描画に失敗（描画なしで続行）")

    # 2. 対象の決定（HTML はゲート、それ以外はデータ・アセットとして公開）
    try:
        uniq, other_news = _publish_targets(base_dir, result["rendered"], paths)
    except Exception as e:  # noqa: BLE001
        result["rejected"].append({"path": paths, "errors": ["パスが不正: %s" % e]})
        uniq, other_news = [], []

    # 3. ゲート（公開前の実物に対して）
    ok_targets = []
    for rel in uniq:
        f = os.path.join(base_dir, rel)
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                new_html = fh.read()
        except OSError:
            continue
        key = rel
        old_html = ""
        if not _s3_key_is_new(s3, key):
            try:
                old_html = s3.get_object(Bucket=LLM_SITE_BUCKET, Key=key)[
                    "Body"].read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                old_html = ""
        hits = _audit_gate_errors(base_dir, rel, new_html, old_html)
        if not hits and old_html:
            hits = _structure_gate_errors(rel, new_html, old_html)
        if hits:
            result["rejected"].append({"key": rel, "errors": hits})
            continue
        ok_targets.append(rel)

    # 4. アップロード
    for rel in ok_targets:
        try:
            s3.upload_file(os.path.join(base_dir, rel), LLM_SITE_BUCKET, rel,
                           ExtraArgs={"ContentType": _content_type(rel),
                                      "CacheControl": _cache_control(rel)})
            _invalidation_paths.append("/" + rel)
            result["published"].append(rel)
        except Exception as e:  # noqa: BLE001
            result["rejected"].append({"key": rel, "errors": ["upload: %s" % e]})

    # 4-b. HTML以外（data/*.json・sitemap.xml・llms.txt・style.css・画像）
    #      2026-11-21: ここが抜けていて、render が data/models.json を
    #      更新しても計算機だけ古いままだった。中身が同じなら上げない。
    if other_news:
        facts_hits = _facts_consistency_errors(base_dir) if any(
            r.endswith("models.json") for r in other_news) else []
        for rel in other_news:
            if rel.endswith("models.json") and facts_hits:
                result["rejected"].append({"key": rel, "errors": facts_hits[:6]})
                continue
            try:
                local = os.path.join(base_dir, rel)
                if _same_as_s3(s3, rel, local):
                    continue
            except Exception:  # noqa: BLE001
                continue
            if not os.path.exists(local):
                continue
            try:
                s3.upload_file(local, LLM_SITE_BUCKET, rel,
                               ExtraArgs={"ContentType": _content_type(rel),
                                          "CacheControl": _cache_control(rel)})
                _invalidation_paths.append("/" + rel)
                result["published"].append(rel)
            except Exception as e:  # noqa: BLE001
                result["rejected"].append({"key": rel, "errors": ["upload: %s" % e]})

    # 5. invalidation（日付修正の取りこぼしを避けるため、HTMLは /* で落とす）
    #    ※ここで落ちても公開自体は終わっているので、例外は握って結果に載せる
    #      （2026-11-21: LLM_DIST_ID が空の環境で InvalidAction になりツールごと
    #       例外で落ちた。失敗は「失敗」と返すのが正しい）。
    if result["published"]:
        if len(result["published"]) > 15:
            _invalidation_paths.append("/*")
        try:
            flush_invalidations()
            result["invalidation"] = "ok"
        except Exception as e:  # noqa: BLE001
            result["invalidation"] = "%s: %s" % (type(e).__name__, str(e)[:160])
            logger.error("invalidation に失敗（公開は完了）: %s", e)

    # 6. 実物照合
    if live and result["published"]:
        def _local_digest(rel):
            with open(os.path.join(base_dir, rel), "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()

        wait = [0, 15, 30]
        for rel in result["published"]:
            if rel.endswith("index.html"):
                url = LLM_SITE_URL.rstrip("/") + "/" + rel[: -len("index.html")]
            else:
                url = LLM_SITE_URL.rstrip("/") + "/" + rel
            want = _local_digest(rel)
            got = None
            for i, secs in enumerate(wait):
                if secs:
                    _time.sleep(secs)
                status, body, err = _http_get(url + "?_cb=%d" % int(_time.time() * 1000))
                got = hashlib.sha256(body).hexdigest() if status == 200 else None
                if got == want:
                    break
            result["live"]["checked"] += 1
            if got == want:
                continue
            if got is None:
                result["live"]["pending"].append({"path": "/" + rel, "note": "取得できず（伝播待ちの可能性）"})
            else:
                result["live"]["mismatch"].append({"path": "/" + rel})

    result["status"] = "ok" if not result["rejected"] and not result["live"]["mismatch"] else "partial"
    result["hint"] = ("published が空なら『変わっていない』か『ゲートで止まった』。"
                      "rejected の errors を読んで直す。mismatch は伝播待ちか、"
                      "別のファイルが公開されている疑い（ローカルのパスを確認）。")
    try:
        import trace_store

        tr = trace_store.current()
        if tr:
            tr.event("publish", published=result["published"],
                     rejected=[r["key"] for r in result["rejected"]],
                     live_mismatch=len(result["live"]["mismatch"]))
            if result["rejected"]:
                tr.event("gate.result", ok=False, rejected=result["rejected"][:5])
    except Exception:  # noqa: BLE001
        pass
    return result


TOOL_publish_and_verify = publish_and_verify

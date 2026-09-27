# tools.py — Akira / 3AI が使う @tool 群
#
# - サイト公開系: S3への書き込み + CloudFront invalidation
# - 画像生成: Vertex AI (gemini-3.1-flash-image) を Workload Identity(キーレス)で呼ぶ
# - 予算系: 予算状況の確認
# - 自己改善系: システムプロンプト/skillsの書き換え（翌日起動時に反映）

import json
import os
import time
import urllib.error
import urllib.request

import boto3
from strands import tool

import budget
import config_store
from settings import (
    AWS_REGION,
    IMAGE_MODEL_ID,
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


@tool
def site_upload(local_path: str, site_prefix: str = "") -> dict:
    """ローカル作業フォルダ（SITE_LOCAL_DIR）内のファイル/フォルダをS3に一括アップロードする。

    publish_file_to_site と違い全文を文字列で渡す必要がなく、ローカルで編集した
    ファイルやフォルダをまとめて公開できる。Content-Type判定とCloudFront invalidationは
    自動処理される。レビュー完了後の一括公開に使うこと。

    Args:
        local_path: SITE_LOCAL_DIR からの相対パス（例: "pricing/" でフォルダ全体、
                    "." でサイト全体）。絶対パスは SITE_LOCAL_DIR 配下のみ許可
        site_prefix: S3キーの先頭に付けるプレフィックス（通常は不要）
    """
    base_dir = os.path.abspath(SITE_LOCAL_DIR)
    src = _resolve_local_path(local_path)
    if not os.path.exists(src):
        return {"status": "failed", "reason": f"存在しません: {local_path}"}

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

    s3 = boto3.client("s3", region_name=AWS_REGION)
    uploaded, rejected = [], []
    for f in files:
        rel = os.path.relpath(f, base_dir).replace(os.sep, "/")
        key = rel if not site_prefix else f"{site_prefix.strip('/')}/{rel}"
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
                          ContentType=_content_type(key))
            _save_models_baseline(body)
        else:
            s3.upload_file(f, LLM_SITE_BUCKET, key, ExtraArgs={"ContentType": _content_type(key)})
        _invalidation_paths.append("/" + key)
        uploaded.append(key)
    result: dict = {"status": "published", "count": len(uploaded), "uploaded": uploaded}
    if rejected:
        result["status"] = "published_partial" if uploaded else "rejected"
        result["reason"] = ("データ契約に違反するファイルはアップロードしませんでした"
                            "（公開済みサイトは壊れていません）")
        result["rejected"] = rejected
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

    return {
        "violations": violations,
        "summary": "公開契約チェック: 違反 %d 件" % len(violations),
        "ok": not violations,
    }


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
                  ContentType=_content_type(key))
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
    if key == "lessons" and len(content) > 8000:
        return {
            "status": "rejected",
            "reason": "lessonsは8000文字以内。要点だけ残して整理すること",
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
    s3.put_object(Bucket=LLM_SITE_BUCKET, Key=site_path, Body=image_bytes, ContentType=mime)
    _invalidation_paths.append(f"/{site_path}")

    budget.record_usage(IMAGE_MODEL_ID, 0, 0, images=1, purpose=f"image: {purpose[:100]}")
    return {"status": "published", "url": f"{LLM_SITE_URL}/{site_path}"}


# =====================================================================
# スクリーンショット取得（ApiFlash）+ 画像読み取り
# =====================================================================
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
        "url": url,
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
                          ContentType="image/png")
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
    response = requests.get(image_url, timeout=30)
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

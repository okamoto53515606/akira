# tools.py — Akira / 3AI が使う @tool 群
#
# - サイト公開系: S3への書き込み + CloudFront invalidation
# - 画像生成: Vertex AI (gemini-3.1-flash-image) を Workload Identity(キーレス)で呼ぶ
# - 予算系: 予算状況の確認
# - 自己改善系: システムプロンプト/skillsの書き換え（翌日起動時に反映）

import json
import os
import time

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
)

_invalidation_paths: list[str] = []  # 実行終盤にまとめてinvalidation


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
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.put_object(
        Bucket=LLM_SITE_BUCKET,
        Key=path,
        Body=content.encode("utf-8"),
        ContentType=_content_type(path),
    )
    _invalidation_paths.append(f"/{path}")
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


@tool
def get_budget_status() -> dict:
    """当月のLLM費用と予算残額を確認する。"""
    return budget.check_budget()


@tool
def update_akira_config(key: str, content: str, note: str = "") -> dict:
    """Akira自身の設定（システムプロンプト/skills/サイト計画）を書き換える。
    翌日のFargate起動時から反映される。

    Args:
        key: "system_prompt" / "skill#<名前>" / "site_plan" のいずれか
        content: 新しい内容（全文）
        note: 変更理由のメモ
    """
    config_store.save_config(key, content, note)
    return {"status": "saved", "key": key, "effective": "翌日起動時から"}


# =====================================================================
# 画像生成（Vertex AI / Workload Identity キーレス認証）
# サンプル ga4_mcp_gemini-3.1-flash-image_aws_wi_gcp_sample.py と同方式
# =====================================================================
def _configure_gcp_keyless_env() -> str:
    """WI構成テンプレートからADC設定を生成し環境変数をセットする。"""
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

    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config_file
    os.environ["AWS_ACCESS_KEY_ID"] = creds.access_key
    os.environ["AWS_SECRET_ACCESS_KEY"] = creds.secret_key
    if creds.token:
        os.environ["AWS_SESSION_TOKEN"] = creds.token
    os.environ.setdefault("AWS_REGION", session.region_name or AWS_REGION)
    return config_file


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

    _configure_gcp_keyless_env()
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT が未設定です。")

    client = genai.Client(vertexai=True, project=project, location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"))
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

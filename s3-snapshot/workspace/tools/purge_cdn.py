"""公開後のCDN反映遅れを確実に直すツール（LLM Data Hub）。

背景（2026-09-13 実発生）:
    site_upload 実行後、S3 には新ファイルが入っているのに CloudFront のエッジには
    旧コンテンツが残り続けた（sitemap.xml だけ新、他は旧のまま Age が増え続けた）。
    エッジの古いエントリは TTL（robots.txt で 23時間超）まで残るため、
    invalidation を明示的に打たないと最大1日 古い料金表が配信され続ける。
    → 公開後は必ず verify_publish で照合し、NG があれば purge_cdn を呼ぶ。

使い方:
    purge_cdn()                 # 全パス（既定 "/*"）
    purge_cdn("/pricing/,/en/pricing/")   # カンマ区切りで個別指定

重要（2026-09-19 実発生）:
    ディレクトリのパス "/glossary/harness/" を指定しても、CloudFront がキャッシュしている
    オブジェクトキー "/glossary/harness/index.html" は消えない（ルートオブジェクトは
    index.html という別キーで保存されるため）。実際に /glossary/harness/ だけを purge して
    2回空振りし、公開ページが旧文面のまま配信され続けた。
    → 末尾が "/" のパスを渡されたら "<path>index.html" も自動で対象に加える（_expand_paths）。
      それでも直らない場合は "/*" を使う。

注意:
    - create_invalidation は通るが get_invalidation は権限が無い（TaskRole の制約）ため、
      完了待ちはこのツールでは行わない。verify_publish で内容を確認すること。
    - import 時のネットワーク通信・ファイル書込は無し。
"""
from __future__ import annotations

import os
import time

import boto3
from strands import tool


def _expand_paths(paths: str):
    """ディレクトリ指定を、CloudFront が実際に保持するオブジェクトキーへ展開する。

    "/glossary/harness/" -> ["/glossary/harness/", "/glossary/harness/index.html"]
    （ルートオブジェクトは index.html という別キーなので、ディレクトリ指定だけでは消えない）
    """
    raw = [q.strip() for q in str(paths).split(",") if q.strip()] or ["/*"]
    out = []
    for q in raw:
        if q not in out:
            out.append(q)
        if q.endswith("/") and q != "/":
            key = q + "index.html"
            if key not in out:
                out.append(key)
    return out


@tool
def purge_cdn(paths: str = "/*") -> dict:
    """CloudFront invalidation を発行してCDNキャッシュを無効化する（site_upload後の反映遅れ対策）。

    Args:
        paths: カンマ区切りのパス（例 "/pricing/,/sitemap.xml"）。空なら "/*"（全体）。
    """
    dist_id = os.environ.get("LLM_DIST_ID", "")
    if not dist_id:
        return {"status": "error", "reason": "LLM_DIST_ID が環境変数に無い"}

    items = _expand_paths(paths)
    region = os.environ.get("AWS_REGION", "us-east-1")
    try:
        cf = boto3.client("cloudfront", region_name=region)
        res = cf.create_invalidation(
            DistributionId=dist_id,
            InvalidationBatch={
                "Paths": {"Quantity": len(items), "Items": items},
                "CallerReference": "purge-cdn-%d" % int(time.time()),
            },
        )
    except Exception as exc:  # 権限不足・レート超過など
        return {"status": "error", "reason": "%s: %s" % (type(exc).__name__, str(exc)[:300])}

    inv = res.get("Invalidation", {})
    return {
        "status": "ok",
        "distribution": dist_id,
        "invalidation_id": inv.get("Id", ""),
        "state": inv.get("Status", ""),
        "paths": items,
        "note": "反映確認は verify_publish で行う（get_invalidation は権限無し）",
    }


TOOL = purge_cdn

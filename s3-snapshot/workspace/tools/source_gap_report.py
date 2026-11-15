"""一次情報の取りこぼしを読む（2026-11-15 追加 / R4）。

`fetch_quote` / `discover_sources` が失敗した回数を `_gap_log` が数えている。
このツールは**それを読むだけ**（ローカルのJSONを開くだけなので、ほぼ費用ゼロ）。

使いどころ:
    - 実行の最初に1回だけ呼び、「今日はどのキーが取れていないか」を見る
    - 週次で `worst_sources` を見て、URLを人間に確認してもらう候補を決める

返すもの:
    totals      : 期間内の 取得成功+失敗 の合計
    by_kind     : fetch / discover ごとの内訳
    worst_sources: 失敗が多いキー（＝URLが死んでいる・URL違いの疑い）
    reasons     : 失敗理由の内訳（empty_body_3 は「300字しか取れなかった」等）
"""
from __future__ import annotations

import os
import sys

from strands import tool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gap_log import summarize  # noqa: E402


@tool
def source_gap_report(days: int = 7) -> dict:
    """一次情報の取得ミス（URL未発見・本文が空）を集計して返す。

    Args:
        days: 何日分を見るか（既定7。1〜30）
    """
    n = max(1, min(int(days or 7), 30))
    s = summarize(n)
    s["hint"] = ("worst_sources が同じキーに偏っているなら、そのURL自体が疑わしい"
                 "（一覧ページ・別ドメイン・PDF/画像）。discover_sources で探し直すか、"
                 "okamo にURLを確認する。0件なら取りこぼしは起きていない。")
    return s


TOOL = source_gap_report

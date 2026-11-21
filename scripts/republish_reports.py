#!/usr/bin/env python3
"""日報サイト（akira.okamomedia.tokyo）を今すぐ全件作り直す。

普段は毎ランの report.publish_reports() が同じことをする。テンプレート・共通CSS・
favicon を変えたときに、次の定時ランを待たずに **過去分の日報まで** 揃えたいとき用。

    REPORTS_DIST_ID=E1PETXZ81SSGJS python scripts/republish_reports.py

AWSの認証情報は通常のCLIと同じ（AWS_PROFILE など）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import report  # noqa: E402  （sys.path 追加後に読む）


def main() -> int:
    paths = report.publish_reports()
    print(f"published {len(paths)} paths")
    for p in paths[:8]:
        print(f"  {p}")
    if len(paths) > 8:
        print(f"  ... 他 {len(paths) - 8} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

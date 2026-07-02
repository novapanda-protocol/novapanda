#!/usr/bin/env python3
"""运行 NovaPanda Conformance Suite（C1–C7）。

用法:
  python -m conformance.run           # 全部
  python -m conformance.run C1 C3     # 指定 case
  python -m conformance.run --list    # 列出 case
"""

from __future__ import annotations

import argparse
import sys

from .suite import list_cases, run_all, run_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NovaPanda Conformance Suite")
    parser.add_argument("cases", nargs="*", help="C1–C7（默认全部）")
    parser.add_argument("--list", action="store_true", help="列出 case 映射")
    args = parser.parse_args(argv)

    if args.list:
        for item in list_cases():
            print(f"{item['id']}: {item['title']}")
            for t in item["tests"]:
                print(f"  - {t}")
        return 0

    if not args.cases:
        return run_all()

    code = 0
    for case_id in args.cases:
        rc = run_case(case_id)
        if rc != 0:
            code = rc
    return code


if __name__ == "__main__":
    sys.exit(main())

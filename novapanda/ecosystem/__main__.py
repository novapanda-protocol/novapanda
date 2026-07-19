"""python -m novapanda.ecosystem · list community adapters."""

from __future__ import annotations

import json
import sys

from .registry import list_adapter_summaries


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] in ("-h", "--help"):
        print("usage: python -m novapanda.ecosystem [list]")
        return 0
    rows = list_adapter_summaries()
    print(json.dumps({"adapters": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

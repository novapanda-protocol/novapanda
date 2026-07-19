"""Adopter M1–M5 一键冒烟（CI / 看门狗用）。

依次调用各 demo 的 main()；任一步失败即非零退出。
运行：  python demo/adopter_smoke_all.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DEMO = Path(__file__).resolve().parent

MODULES = [
    "adopter_closed_loop",
    "adopter_av_charge",
    "adopter_m3_product",
    "adopter_m4_rails",
    "adopter_site_patrol",
]


def main() -> int:
    for p in (_ROOT, _DEMO):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    for name in MODULES:
        print(f"\n>>> smoke {name}")
        mod = importlib.import_module(name)
        mod.main()
        print(f"<<< {name} OK")
    print("\n=== ADOPTER SMOKE ALL PASS ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

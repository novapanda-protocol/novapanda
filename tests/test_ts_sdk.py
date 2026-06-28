import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TS = ROOT / "sdk" / "typescript"


def test_typescript_sdk_skeleton_present():
    assert (TS / "package.json").is_file()
    assert (TS / "src" / "index.ts").is_file()
    content = (TS / "src" / "index.ts").read_text(encoding="utf-8")
    assert "canonicalString" in content
    assert "TroodonClient" in content

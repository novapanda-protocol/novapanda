"""Load ``adapters/*/manifest.json`` (repo-root community catalog)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS_DIR = ROOT / "adapters"

REQUIRED_FIELDS = ("slug", "title", "kind", "status", "maintainer")


@dataclass(frozen=True)
class AdapterManifest:
    slug: str
    title: str
    kind: str
    status: str
    maintainer: str
    summary: str = ""
    binding: str = ""
    paths: tuple[str, ...] = ()
    profiles: tuple[str, ...] = ()
    settlement_note: str = "mock"
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdapterManifest":
        missing = [k for k in REQUIRED_FIELDS if not data.get(k)]
        if missing:
            raise ValueError(f"manifest missing fields: {missing}")
        return cls(
            slug=str(data["slug"]),
            title=str(data["title"]),
            kind=str(data["kind"]),
            status=str(data["status"]),
            maintainer=str(data["maintainer"]),
            summary=str(data.get("summary") or ""),
            binding=str(data.get("binding") or ""),
            paths=tuple(data.get("paths") or []),
            profiles=tuple(data.get("profiles") or ["NP-MIN"]),
            settlement_note=str(data.get("settlement_note") or "mock"),
            raw=dict(data),
        )


def iter_adapters(adapters_dir: Optional[Path] = None) -> Iterator[AdapterManifest]:
    root = Path(adapters_dir or ADAPTERS_DIR)
    if not root.is_dir():
        return
    for path in sorted(root.glob("*/manifest.json")):
        if path.parent.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        yield AdapterManifest.from_dict(data)


def load_adapter(slug: str, adapters_dir: Optional[Path] = None) -> AdapterManifest:
    for m in iter_adapters(adapters_dir):
        if m.slug == slug:
            return m
    raise KeyError(f"unknown adapter: {slug}")


def list_adapter_summaries(adapters_dir: Optional[Path] = None) -> list[dict[str, Any]]:
    return [
        {
            "slug": m.slug,
            "title": m.title,
            "kind": m.kind,
            "status": m.status,
            "maintainer": m.maintainer,
            "settlement_note": m.settlement_note,
            "binding": m.binding,
        }
        for m in iter_adapters(adapters_dir)
    ]

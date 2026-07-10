"""UC-40 · 兼容认证名录（Steward 发号）。"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_comp_id(records: dict, year: Optional[int] = None) -> str:
    y = year or datetime.now(timezone.utc).year
    prefix = f"NP-COMP-{y}-"
    nums = []
    for rec in records.values():
        cid = rec.cert_id
        if cid.startswith(prefix):
            try:
                nums.append(int(cid.split("-")[-1]))
            except ValueError:
                pass
    n = max(nums, default=0) + 1
    return f"{prefix}{n:03d}"


@dataclass
class CertificationRecord:
    cert_id: str
    level: str  # L1 | L2 | L3
    applicant: dict
    implementation: dict
    profiles: list[str]
    cases_passed: list[str]
    manifest_sample: Optional[dict] = None
    rail_disclosure: Optional[dict] = None
    granted_at: str = ""
    expires_at: Optional[str] = None
    status: str = "active"  # active | suspended | revoked


@dataclass
class CertificationRegistry:
    _by_id: dict[str, CertificationRecord] = field(default_factory=dict)
    _path: Optional[Path] = None

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> CertificationRegistry:
        p = Path(path) if path else None
        reg = cls(_path=p)
        if p and p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            for raw in data.get("certifications") or []:
                rec = CertificationRecord(**raw)
                reg._by_id[rec.cert_id] = rec
        return reg

    def grant(
        self,
        *,
        level: str,
        applicant: dict,
        implementation: dict,
        profiles: list[str],
        cases_passed: list[str],
        manifest_sample: Optional[dict] = None,
        rail_disclosure: Optional[dict] = None,
        cert_id: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> CertificationRecord:
        cid = cert_id or _next_comp_id(self._by_id)
        if level == "L3" and not cid.startswith("NP-CERT-"):
            y = datetime.now(timezone.utc).year
            n = sum(1 for k in self._by_id if k.startswith(f"NP-CERT-{y}-")) + 1
            cid = f"NP-CERT-{y}-{n:03d}"
        rec = CertificationRecord(
            cert_id=cid,
            level=level,
            applicant=dict(applicant),
            implementation=dict(implementation),
            profiles=list(profiles),
            cases_passed=list(cases_passed),
            manifest_sample=manifest_sample,
            rail_disclosure=rail_disclosure,
            granted_at=_now(),
            expires_at=expires_at,
            status="active",
        )
        self._by_id[cid] = rec
        self._persist()
        return rec

    def get(self, cert_id: str) -> Optional[CertificationRecord]:
        return self._by_id.get(cert_id)

    def list_public(self, *, status: Optional[str] = "active") -> list[CertificationRecord]:
        items = list(self._by_id.values())
        if status:
            items = [r for r in items if r.status == status]
        items.sort(key=lambda r: r.granted_at, reverse=True)
        return items

    def set_status(self, cert_id: str, status: str) -> CertificationRecord:
        rec = self._require(cert_id)
        if status not in ("active", "suspended", "revoked"):
            raise ValueError("invalid_status")
        rec.status = status
        self._persist()
        return rec

    def public(self, rec: CertificationRecord) -> dict:
        out = asdict(rec)
        # 不暴露内部联系人邮箱到公开名录（若有 contact 字段可脱敏）
        app = dict(out.get("applicant") or {})
        if "email" in app:
            app["email"] = "***"
            out["applicant"] = app
        return out

    def _require(self, cert_id: str) -> CertificationRecord:
        rec = self._by_id.get(cert_id)
        if rec is None:
            raise ValueError("not_found")
        return rec

    def _persist(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"certifications": [asdict(c) for c in self._by_id.values()]}
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

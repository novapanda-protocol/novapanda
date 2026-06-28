"""Troodon v3 物理扩展占位。"""

from .physical import (
    PHYSICAL_VERSION,
    iso15118_session_stub,
    is_reserved_physical_type,
    validate_physical_deliverable,
)

__all__ = [
    "PHYSICAL_VERSION",
    "iso15118_session_stub",
    "is_reserved_physical_type",
    "validate_physical_deliverable",
]

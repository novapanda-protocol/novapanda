"""Adopter Runtime —— 接入方产品面（不进 CORE）。

见 ``DESIGN.md`` 与 ``docs/adopter-closed-loop.md``。
"""

from .anchor import AnchorReceipt, LocalAnchorLedger
from .anchor_rails import BulletinBoardRail, ChainAnchorStub, MultiRailAnchor
from .cabin import CabinConsole
from .charge import AvChargeLoop, ChargeControlAdapter
from .constants import DEFAULT_ENERGY_PRICE, ENERGY_RESOURCE, ENERGY_RULE
from .draft import DraftStore
from .export_pdf import build_pdf_bytes, write_arbitration_pdf
from .export_pkg import build_arbitration_package, package_summary_text
from .intent import IntentMap, IntentMatch
from .meter import Iso15118MeterBackend, MeterAdapter, RecordingMeterBackend
from .outbox import Outbox
from .peer import PeerBackup
from .patrol import SitePatrolBundle
from .query import VaultQuery
from .runtime import AdopterRuntime
from .skill import ADOPTER_TOOL_DEFINITIONS, AdopterSkill, adopter_tool_names
from .stations import StationDirectory, StationDiscovery, StationRecord
from .types import DraftRecord, OutboxItem, OutboxOp, VaultEntry
from .vault import VdcVault

__all__ = [
    "AdopterRuntime",
    "DraftStore",
    "Outbox",
    "VdcVault",
    "IntentMap",
    "IntentMatch",
    "PeerBackup",
    "VaultQuery",
    "DraftRecord",
    "OutboxItem",
    "OutboxOp",
    "VaultEntry",
    "build_arbitration_package",
    "package_summary_text",
    "write_arbitration_pdf",
    "build_pdf_bytes",
    "LocalAnchorLedger",
    "AnchorReceipt",
    "BulletinBoardRail",
    "ChainAnchorStub",
    "MultiRailAnchor",
    "StationDirectory",
    "StationDiscovery",
    "StationRecord",
    "ChargeControlAdapter",
    "AvChargeLoop",
    "MeterAdapter",
    "Iso15118MeterBackend",
    "RecordingMeterBackend",
    "CabinConsole",
    "SitePatrolBundle",
    "AdopterSkill",
    "ADOPTER_TOOL_DEFINITIONS",
    "adopter_tool_names",
    "ENERGY_RESOURCE",
    "ENERGY_RULE",
    "DEFAULT_ENERGY_PRICE",
]

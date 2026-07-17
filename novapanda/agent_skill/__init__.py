"""第三方 AI Agent 的 Skill 接入面（自治 + 结算）。

专为 LLM Function Calling 设计：结构化入参/出参、可恢复错误码、Token 紧凑视图。
不改 ``state_machine.TRANSITIONS``，不改定价/拆解/拍卖核心算法。
"""

from .compact import (
    compact_auction,
    compact_graph,
    compact_orchestration,
    compact_terminal_snapshot,
    short_agent_id,
)
from .errors import AgentFault, RecoveryAction, classify_exception, fault_from_mapping
from .manifest import build_tool_manifest, write_tool_manifest
from .tools import TOOL_DEFINITIONS, NovaPandaAgentSkill, tool_names

__all__ = [
    "AgentFault",
    "NovaPandaAgentSkill",
    "RecoveryAction",
    "TOOL_DEFINITIONS",
    "build_tool_manifest",
    "classify_exception",
    "compact_auction",
    "compact_graph",
    "compact_orchestration",
    "compact_terminal_snapshot",
    "fault_from_mapping",
    "short_agent_id",
    "tool_names",
    "write_tool_manifest",
]

"""接入面（Access Surfaces）：SDK / MCP / A2A / Skill / 适配器 / 裸 HTTP。

铁律（SPEC §7）：接入面只做「翻译」，MUST NOT 改变凭证、状态机与复验语义。
所有接入面共享同一张操作注册表（base.OPERATIONS），从而：
任意异构 Agent（行业 Agent / OpenClaw / 爱马仕 …）经任一接入面完成的交割，产出的 VDC 完全等价、可互相复验。
"""

from .base import OPERATIONS, OPERATIONS_BY_NAME, dispatch
from .mcp import MCPBinding, mcp_tool_descriptors
from .a2a import A2ABinding, agent_card
from .skill import ExchangeSkill
from .adapter import ProviderAdapter

__all__ = [
    "OPERATIONS",
    "OPERATIONS_BY_NAME",
    "dispatch",
    "MCPBinding",
    "mcp_tool_descriptors",
    "A2ABinding",
    "agent_card",
    "ExchangeSkill",
    "ProviderAdapter",
]

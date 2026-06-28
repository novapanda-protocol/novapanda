"""MCP 接入面：把协议操作暴露为 MCP 工具。

本绑定与具体 MCP 服务端库解耦——它只产出工具描述符并做分发。
任何 MCP 服务端（如 FastMCP）都可用 `mcp_tool_descriptors()` 注册工具，
并在工具回调里调用 `MCPBinding.call_tool(name, arguments)`。
"""

from __future__ import annotations

from typing import Any

from .base import OPERATIONS, Client, dispatch

_PREFIX = "troodon."


def mcp_tool_descriptors() -> list[dict]:
    return [
        {
            "name": _PREFIX + op.name,
            "description": op.description,
            "inputSchema": op.input_schema,
        }
        for op in OPERATIONS
    ]


class MCPBinding:
    def __init__(self, client: Client) -> None:
        self.client = client

    def list_tools(self) -> list[dict]:
        return mcp_tool_descriptors()

    def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        bare = name[len(_PREFIX):] if name.startswith(_PREFIX) else name
        return dispatch(self.client, bare, arguments)

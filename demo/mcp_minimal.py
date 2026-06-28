"""MCP 最小示例：列出 troodon.* 工具并调用 get_exchange（无需真实 MCP 库）。"""

from __future__ import annotations

from troodon.identity import Identity
from troodon.sdk import TroodonClient
from troodon.surfaces.mcp import MCPBinding


def main() -> None:
    client = TroodonClient("http://127.0.0.1:8000", Identity.generate())
    binding = MCPBinding(client)
    tools = binding.list_tools()
    print(f"tools: {len(tools)}")
    score_tool = next(t for t in tools if t["name"] == "troodon.reputation_score")
    print("reputation_score schema keys:", list(score_tool["inputSchema"]["properties"].keys()))


if __name__ == "__main__":
    main()

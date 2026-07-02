"""MCP 最小示例：列出 novapanda.* 工具并调用 get_exchange（无需真实 MCP 库）。"""

from __future__ import annotations

from novapanda.identity import Identity
from novapanda.sdk import NovaPandaClient
from novapanda.surfaces.mcp import MCPBinding


def main() -> None:
    client = NovaPandaClient("http://127.0.0.1:8000", Identity.generate())
    binding = MCPBinding(client)
    tools = binding.list_tools()
    print(f"tools: {len(tools)}")
    score_tool = next(t for t in tools if t["name"] == "novapanda.reputation_score")
    print("reputation_score schema keys:", list(score_tool["inputSchema"]["properties"].keys()))


if __name__ == "__main__":
    main()

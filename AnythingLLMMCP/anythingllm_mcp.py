"""AnythingLLM MCP Server — 单工具：列出所有工作区 slug。"""

import os

import httpx2
from mcp.server import MCPServer

BASE_URL = os.environ.get("ANYTHINGLLM_BASE_URL", "http://127.0.0.1:3001/api/v1")
API_KEY = os.environ.get("ANYTHINGLLM_API_KEY", "Y8WWKJY-KZ74SHG-QQ8YAYW-R7ARDAM")

mcp = MCPServer("anythingllm-mcp", version="1.0.0")


@mcp.tool()
async def list_workspaces() -> str:
    """列出 AnythingLLM 当前所有工作区的 slug。"""
    async with httpx2.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}/workspaces",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        resp.raise_for_status()
    workspaces = resp.json().get("workspaces", [])
    return "\n".join(w["slug"] for w in workspaces) if workspaces else "(无工作区)"


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8081,
        stateless_http=True,
        json_response=True,
    )

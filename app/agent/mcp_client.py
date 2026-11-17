from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.config import get_settings


async def load_mcp_tools(token: str) -> list[BaseTool]:
    """Discover tools via MCP `tools/list`, forwarding the end user's JWT so the server scopes every call."""
    client = MultiServerMCPClient({
        "knowledge-base": {
            "transport": "streamable_http",
            "url": get_settings().mcp_server_url,
            "headers": {"Authorization": f"Bearer {token}"},
            "timeout": 30,
        }
    })
    return await client.get_tools()

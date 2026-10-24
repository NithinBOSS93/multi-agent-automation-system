"""Standalone MCP server exposing all 13 tools over stdio.

Run it from the backend folder:
    python -m app.mcp.server

Any MCP client (e.g. Claude Desktop, MCP Inspector) can then connect to it.
"""
from mcp.server.fastmcp import FastMCP

from app.mcp.tools import ALL_TOOLS

mcp = FastMCP("multi-agent-automation-tools")

for _fn in ALL_TOOLS.values():
    mcp.tool()(_fn)


if __name__ == "__main__":
    mcp.run()

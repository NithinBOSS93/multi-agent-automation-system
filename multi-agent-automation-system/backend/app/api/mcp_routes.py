"""MCP tools explorer: list the tools and run one directly."""
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.mcp.tools import call_tool, describe_tools

router = APIRouter(prefix="/mcp", tags=["mcp"])


class ToolCall(BaseModel):
    args: dict = {}


@router.get("/tools")
async def tools():
    return describe_tools()


@router.post("/tools/{name}")
async def run(name: str, body: ToolCall):
    result = await asyncio.to_thread(call_tool, name, body.args)
    return {"tool": name, "result": result}

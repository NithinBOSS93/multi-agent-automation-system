"""Shared types and helpers for all three agents."""
import asyncio
from typing import Awaitable, Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.mcp.tools import as_langchain_tools, call_tool

# emit(event) sends a live update to the client, e.g.
#   {"type": "token", "content": "Hel"}
#   {"type": "step", "name": "research", "detail": "..."}
#   {"type": "tool", "name": "get_cpu_usage", "args": {}, "result": "..."}
Emit = Callable[[dict], Awaitable[None]]


async def no_emit(_: dict) -> None:
    return None


def history_to_messages(history: list[dict]) -> list[BaseMessage]:
    msgs: list[BaseMessage] = []
    for h in history:
        msgs.append(HumanMessage(h["content"]) if h["role"] == "user" else AIMessage(h["content"]))
    return msgs


def rag_system_block(context: str) -> str:
    if not context:
        return ""
    return (
        "\n\nUse the following excerpts from the user's documents when relevant. "
        "Cite them like [1], [2]. If they don't contain the answer, say so.\n\n" + context
    )


async def run_tool_calls(tool_calls: list[dict], emit: Emit, used: list[str]) -> list[ToolMessage]:
    """Execute the tool calls an LLM asked for and return ToolMessages."""
    results = []
    for tc in tool_calls:
        output = await asyncio.to_thread(call_tool, tc["name"], tc.get("args") or {})
        used.append(tc["name"])
        await emit({"type": "tool", "name": tc["name"], "args": tc.get("args") or {}, "result": output[:1500]})
        results.append(ToolMessage(content=output, tool_call_id=tc["id"]))
    return results


async def tool_loop(llm, messages: list[BaseMessage], emit: Emit, used: list[str],
                    stream_tokens: bool = True, max_rounds: int = 5) -> str:
    """ReAct-style loop: reason -> call tools -> observe -> repeat -> final answer."""
    llm_tools = llm.bind_tools(as_langchain_tools())
    for _ in range(max_rounds):
        full = None
        async for chunk in llm_tools.astream(messages):
            full = chunk if full is None else full + chunk
            if stream_tokens and chunk.content:
                await emit({"type": "token", "content": chunk.content})
        if full is None:
            return ""
        if not full.tool_calls:
            return full.content
        messages.append(full)
        messages.extend(await run_tool_calls(full.tool_calls, emit, used))
    # too many rounds: ask for a final answer without tools
    final = await llm.ainvoke(messages + [SystemMessage("Give your final answer now.")])
    if stream_tokens:
        await emit({"type": "token", "content": final.content})
    return final.content

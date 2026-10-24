"""LangChain agent — fast conversational assistant with RAG + MCP tool calling.

Best for: quick questions, document Q&A, and actions on the system
(files, database, CPU/memory, web search).
"""
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import Emit, history_to_messages, rag_system_block, tool_loop
from app.llm import get_llm
from app.rag.pipeline import build_context

SYSTEM = (
    "You are a helpful automation assistant in a multi-agent platform. "
    "You can use tools to read/write files in the workspace, query the SQLite "
    "database, check system information and search the web. Use a tool whenever "
    "the question needs live data; otherwise answer directly. Be concise and clear."
)


async def run(message: str, history: list[dict], use_rag: bool, emit: Emit) -> dict:
    start = time.perf_counter()
    context, sources = build_context(message) if use_rag else ("", [])
    await emit({"type": "step", "name": "retrieve", "detail": f"{len(sources)} document chunks"})

    messages = [SystemMessage(SYSTEM + rag_system_block(context))]
    messages += history_to_messages(history)
    messages.append(HumanMessage(message))

    used: list[str] = []
    answer = await tool_loop(get_llm(), messages, emit, used)
    return {
        "answer": answer,
        "sources": sources,
        "tools_used": used,
        "steps": ["retrieve", "reason", "act", "answer"],
        "latency": round(time.perf_counter() - start, 2),
    }

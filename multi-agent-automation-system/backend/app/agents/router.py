"""Agent router — sends each request to the right agent.

agent = "langchain" | "langgraph" | "crewai" | "auto"
"auto" picks an agent from keywords in the message.
"""
import importlib

from app.agents.base import Emit, no_emit

AGENTS = {
    "langchain": {
        "module": "app.agents.langchain_agent",
        "label": "LangChain",
        "description": "Fast assistant with RAG and MCP tools. Best for quick questions and system actions.",
    },
    "langgraph": {
        "module": "app.agents.langgraph_agent",
        "label": "LangGraph",
        "description": "Research → Critique → Synthesize graph with a self-check loop. Best for deep analysis.",
    },
    "crewai": {
        "module": "app.agents.crewai_agent",
        "label": "CrewAI",
        "description": "Researcher, Critic and Writer agents working as a crew. Best for reports.",
    },
}

_REPORT = ("report", "article", "essay", "blog", "write a", "draft", "proposal")
_RESEARCH = ("research", "analyze", "analyse", "compare", "explain in detail", "pros and cons", "why")


def pick_agent(message: str) -> str:
    text = message.lower()
    if any(k in text for k in _REPORT):
        return "crewai"
    if any(k in text for k in _RESEARCH):
        return "langgraph"
    return "langchain"


async def run_agent(agent: str, message: str, history: list[dict] | None = None,
                    use_rag: bool = False, emit: Emit = no_emit) -> dict:
    if agent == "auto":
        agent = pick_agent(message)
        await emit({"type": "step", "name": "route", "detail": f"auto → {agent}"})
    if agent not in AGENTS:
        raise ValueError(f"Unknown agent '{agent}'")
    module = importlib.import_module(AGENTS[agent]["module"])
    result = await module.run(message, history or [], use_rag, emit)
    result["agent"] = agent
    return result

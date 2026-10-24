"""LangGraph agent — stateful graph:  research -> critique -> (loop?) -> synthesize.

    START -> research -> critique --(needs more & tries left)--> research
                                   \--(good enough)----------> synthesize -> END

Best for: deep research and analysis where a self-check improves quality.
"""
import time
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.base import Emit, history_to_messages, rag_system_block, tool_loop
from app.llm import get_llm
from app.rag.pipeline import build_context

MAX_RESEARCH_ROUNDS = 2


class GraphState(TypedDict):
    question: str
    history: list[dict]
    context: str
    findings: str
    feedback: str
    rounds: int
    answer: str
    tools_used: list[str]


def build_graph(emit: Emit):
    llm = get_llm()

    async def research(state: GraphState) -> dict:
        await emit({"type": "step", "name": "research", "detail": f"round {state['rounds'] + 1}"})
        prompt = (
            "You are the RESEARCHER. Gather the facts needed to answer the question. "
            "Use tools (web search, system info, files, database) if live data is needed. "
            "Return bullet-point findings only, no final answer."
            + rag_system_block(state["context"])
        )
        if state["feedback"]:
            prompt += f"\n\nA reviewer said your last research was missing:\n{state['feedback']}"
        msgs = [SystemMessage(prompt), *history_to_messages(state["history"]), HumanMessage(state["question"])]
        used = list(state["tools_used"])
        findings = await tool_loop(llm, msgs, emit, used, stream_tokens=False)
        return {"findings": findings, "rounds": state["rounds"] + 1, "tools_used": used}

    async def critique(state: GraphState) -> dict:
        await emit({"type": "step", "name": "critique", "detail": "checking the research"})
        msgs = [
            SystemMessage(
                "You are the CRITIC. Check if the research fully answers the question. "
                "Reply with exactly 'APPROVED' if it does, otherwise reply 'NEEDS_MORE: ' "
                "followed by what is missing (one or two lines)."
            ),
            HumanMessage(f"Question: {state['question']}\n\nResearch:\n{state['findings']}"),
        ]
        verdict = (await get_llm(fast=True, streaming=False).ainvoke(msgs)).content.strip()
        return {"feedback": "" if verdict.upper().startswith("APPROVED") else verdict}

    def should_continue(state: GraphState) -> str:
        if state["feedback"] and state["rounds"] < MAX_RESEARCH_ROUNDS:
            return "research"
        return "synthesize"

    async def synthesize(state: GraphState) -> dict:
        await emit({"type": "step", "name": "synthesize", "detail": "writing the answer"})
        msgs = [
            SystemMessage(
                "You are the SYNTHESIZER. Write a clear, well-structured final answer "
                "using the research notes. Use markdown headings/bullets where helpful."
            ),
            HumanMessage(f"Question: {state['question']}\n\nResearch notes:\n{state['findings']}"),
        ]
        answer = ""
        async for chunk in llm.astream(msgs):
            if chunk.content:
                answer += chunk.content
                await emit({"type": "token", "content": chunk.content})
        return {"answer": answer}

    graph = StateGraph(GraphState)
    graph.add_node("research", research)
    graph.add_node("critique", critique)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "research")
    graph.add_edge("research", "critique")
    graph.add_conditional_edges("critique", should_continue, {"research": "research", "synthesize": "synthesize"})
    graph.add_edge("synthesize", END)
    return graph.compile()


async def run(message: str, history: list[dict], use_rag: bool, emit: Emit) -> dict:
    start = time.perf_counter()
    context, sources = build_context(message) if use_rag else ("", [])
    app = build_graph(emit)
    final = await app.ainvoke({
        "question": message, "history": history, "context": context,
        "findings": "", "feedback": "", "rounds": 0, "answer": "", "tools_used": [],
    })
    return {
        "answer": final["answer"],
        "sources": sources,
        "tools_used": final["tools_used"],
        "steps": ["research"] * final["rounds"] + ["critique", "synthesize"],
        "latency": round(time.perf_counter() - start, 2),
    }

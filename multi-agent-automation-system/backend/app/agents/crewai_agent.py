"""CrewAI agent — a crew of 3 role-based agents working in sequence:

    Researcher  -> gathers facts (can use MCP tools)
    Critic      -> reviews the facts for gaps and errors
    Writer      -> writes the final polished answer

Best for: reports, articles and multi-perspective answers.
"""
import asyncio
import time

from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool

from app.agents.base import Emit
from app.core.config import settings
from app.llm import _check_key
from app.mcp import tools as mcp
from app.rag.pipeline import build_context

CHUNK = 40  # chars per streamed piece of the final answer


def _crew_tools():
    picked = [mcp.web_search, mcp.get_system_info, mcp.get_cpu_usage, mcp.get_memory_usage,
              mcp.get_disk_usage, mcp.list_directory, mcp.read_file, mcp.run_sql_query]
    return [tool(fn.__name__)(fn) for fn in picked]


def build_crew(question: str, history: list[dict], context: str, on_task_done) -> Crew:
    _check_key()
    llm = LLM(model=f"groq/{settings.groq_model}", api_key=settings.groq_api_key,
              temperature=settings.temperature, max_tokens=settings.max_tokens)

    researcher = Agent(
        role="Research Analyst",
        goal="Find accurate, relevant facts to answer the user's request",
        backstory="A meticulous analyst who uses tools to check live data instead of guessing.",
        tools=_crew_tools(), llm=llm, verbose=False, allow_delegation=False, max_iter=5,
    )
    critic = Agent(
        role="Quality Critic",
        goal="Spot gaps, mistakes and unsupported claims in the research",
        backstory="A sharp reviewer who keeps the team honest.",
        llm=llm, verbose=False, allow_delegation=False,
    )
    writer = Agent(
        role="Technical Writer",
        goal="Turn reviewed research into a clear, well-structured answer",
        backstory="Writes simple, accurate markdown that anyone can follow.",
        llm=llm, verbose=False, allow_delegation=False,
    )

    convo = "\n".join(f"{h['role']}: {h['content']}" for h in history[-6:])
    docs = f"\n\nRelevant excerpts from the user's documents:\n{context}" if context else ""

    research_task = Task(
        description=f"Previous conversation:\n{convo}\n\nUser request: {question}{docs}\n\nResearch this request.",
        expected_output="Bullet-point findings with key facts and data.",
        agent=researcher,
    )
    review_task = Task(
        description="Review the research. List any gaps or errors and the corrected facts.",
        expected_output="A short review with corrections, or 'No issues'.",
        agent=critic, context=[research_task],
    )
    write_task = Task(
        description=f"Write the final answer to: {question}",
        expected_output="A clear markdown answer for the user.",
        agent=writer, context=[research_task, review_task],
    )
    return Crew(
        agents=[researcher, critic, writer],
        tasks=[research_task, review_task, write_task],
        process=Process.sequential, verbose=False, task_callback=on_task_done,
    )


async def run(message: str, history: list[dict], use_rag: bool, emit: Emit) -> dict:
    start = time.perf_counter()
    context, sources = build_context(message) if use_rag else ("", [])
    loop = asyncio.get_running_loop()
    roles = iter(["researcher", "critic", "writer"])

    def on_task_done(output):  # runs in CrewAI's worker thread
        name = next(roles, "task")
        detail = str(getattr(output, "raw", output))[:300]
        asyncio.run_coroutine_threadsafe(emit({"type": "step", "name": name, "detail": detail}), loop)

    await emit({"type": "step", "name": "crew", "detail": "Researcher → Critic → Writer"})
    crew = build_crew(message, history, context, on_task_done)
    result = await asyncio.to_thread(crew.kickoff)
    answer = str(getattr(result, "raw", result))

    for i in range(0, len(answer), CHUNK):
        await emit({"type": "token", "content": answer[i:i + CHUNK]})
        await asyncio.sleep(0.005)

    return {
        "answer": answer,
        "sources": sources,
        "tools_used": [],
        "steps": ["researcher", "critic", "writer"],
        "latency": round(time.perf_counter() - start, 2),
    }

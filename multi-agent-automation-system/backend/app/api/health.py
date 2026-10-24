from fastapi import APIRouter

from app.core.config import settings
from app.db.database import get_db
from app.mcp.tools import ALL_TOOLS

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "llm": settings.groq_model,
        "groq_key_set": bool(settings.groq_api_key),
        "web_search": "tavily" if settings.tavily_api_key else "duckduckgo",
    }


@router.get("/stats")
async def stats():
    async with get_db() as db:
        counts = {}
        for table in ("conversations", "messages", "documents", "templates"):
            cur = await db.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT agent, COUNT(*) AS n, AVG(json_extract(meta, '$.latency')) AS avg_latency, "
            "SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS likes "
            "FROM messages WHERE role = 'assistant' GROUP BY agent")
        per_agent = [dict(r) for r in await cur.fetchall()]
    return {**counts, "mcp_tools": len(ALL_TOOLS), "per_agent": per_agent}

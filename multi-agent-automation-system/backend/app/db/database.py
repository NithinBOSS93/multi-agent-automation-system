"""SQLite persistence with aiosqlite (zero configuration, single file)."""
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aiosqlite

from app.core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    agent TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    agent TEXT,
    meta TEXT,
    rating INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    chunks INTEGER NOT NULL,
    summary TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    agent TEXT NOT NULL DEFAULT 'langchain',
    created_at TEXT NOT NULL
);
"""

DEFAULT_TEMPLATES = [
    ("Research a topic", "Research {topic} and give me the key facts, recent developments and open questions.", "langgraph"),
    ("Write a report", "Write a short structured report on {topic} with an introduction, findings and conclusion.", "crewai"),
    ("System health check", "Check my system's CPU, memory and disk usage and tell me if anything looks wrong.", "langchain"),
    ("Ask my documents", "Using my uploaded documents, answer: {question}", "langchain"),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    async with get_db() as db:
        await db.executescript(SCHEMA)
        cur = await db.execute("SELECT COUNT(*) FROM templates")
        (count,) = await cur.fetchone()
        if count == 0:
            await db.executemany(
                "INSERT INTO templates (user_id, name, prompt, agent, created_at) VALUES (NULL, ?, ?, ?, ?)",
                [(n, p, a, now()) for n, p, a in DEFAULT_TEMPLATES],
            )
        await db.commit()


def row_to_dict(row: aiosqlite.Row) -> dict:
    d = dict(row)
    if "meta" in d and d["meta"]:
        try:
            d["meta"] = json.loads(d["meta"])
        except json.JSONDecodeError:
            pass
    return d


# ---------- conversation helpers ----------

async def create_conversation(user_id: int | None, title: str, agent: str) -> int:
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO conversations (user_id, title, agent, created_at) VALUES (?, ?, ?, ?)",
            (user_id, title[:80], agent, now()),
        )
        await db.commit()
        return cur.lastrowid


async def add_message(conversation_id: int, role: str, content: str,
                      agent: str | None = None, meta: dict | None = None) -> int:
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO messages (conversation_id, role, content, agent, meta, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, role, content, agent, json.dumps(meta) if meta else None, now()),
        )
        await db.commit()
        return cur.lastrowid


async def get_history(conversation_id: int, limit: int = 10) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in reversed(rows)]

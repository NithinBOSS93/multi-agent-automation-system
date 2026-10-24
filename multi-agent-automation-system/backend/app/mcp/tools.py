"""The 13 MCP tools, grouped in 4 categories.

The same functions are used in two ways:
  * exposed as a real MCP server (app/mcp/server.py) for any MCP client
  * wrapped as LangChain tools so our agents can call them (as_langchain_tools)

Safety: file tools are sandboxed to settings.workspace_dir, and SQL tools are
read-only (SELECT only) with password hashes hidden.
"""
import json
import os
import platform
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
import psutil

from app.core.config import settings

# ============ helpers ============

def _safe_path(relative: str) -> Path:
    root = settings.workspace_dir.resolve()
    target = (root / relative).resolve()
    if root != target and root not in target.parents:
        raise ValueError("Access denied: path is outside the workspace folder")
    return target


def _gb(n: int) -> str:
    return f"{n / 1024 ** 3:.2f} GB"


# ============ 1. File system ============

def list_directory(path: str = ".") -> str:
    """List files and folders inside the workspace folder."""
    target = _safe_path(path)
    if not target.is_dir():
        return f"'{path}' is not a folder"
    items = [
        f"{'[DIR] ' if p.is_dir() else '      '}{p.name}" + ("" if p.is_dir() else f"  ({p.stat().st_size} bytes)")
        for p in sorted(target.iterdir())
    ]
    return "\n".join(items) or "(empty folder)"


def read_file(path: str) -> str:
    """Read a text file from the workspace folder."""
    target = _safe_path(path)
    if not target.is_file():
        return f"File '{path}' not found"
    return target.read_text(encoding="utf-8", errors="ignore")[:8000]


def write_file(path: str, content: str) -> str:
    """Create or overwrite a text file in the workspace folder."""
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}"


def search_files(pattern: str) -> str:
    """Find files in the workspace whose name contains the pattern."""
    root = settings.workspace_dir
    found = [str(p.relative_to(root)) for p in root.rglob("*") if pattern.lower() in p.name.lower()]
    return "\n".join(found[:50]) or f"No files matching '{pattern}'"


# ============ 2. SQLite database ============

def _connect_ro() -> sqlite3.Connection:
    uri = f"file:{settings.database_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def list_tables() -> str:
    """List the tables in the application database."""
    with _connect_ro() as con:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    return ", ".join(r[0] for r in rows)


def describe_table(table: str) -> str:
    """Show the columns of a database table."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        return "Invalid table name"
    with _connect_ro() as con:
        cols = con.execute(f"PRAGMA table_info({table})").fetchall()
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if cols else 0
    if not cols:
        return f"Table '{table}' not found"
    return f"{table} ({count} rows)\n" + "\n".join(f"- {c[1]} {c[2]}" for c in cols)


def run_sql_query(query: str) -> str:
    """Run a read-only SELECT query on the application database."""
    q = query.strip().rstrip(";")
    if not q.lower().startswith("select") or ";" in q:
        return "Only a single SELECT query is allowed"
    if "password" in q.lower():
        return "Password columns cannot be queried"
    with _connect_ro() as con:
        cur = con.execute(q)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(50)
    return json.dumps([dict(zip(cols, r)) for r in rows], indent=2, default=str)


# ============ 3. System information ============

def get_system_info() -> str:
    """Operating system, Python version, CPU cores and machine name."""
    return json.dumps({
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "hostname": platform.node(),
        "python": platform.python_version(),
        "cpu_cores": psutil.cpu_count(logical=True),
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(timespec="seconds"),
    }, indent=2)


def get_cpu_usage() -> str:
    """Current CPU usage percentage (overall and per core)."""
    per_core = psutil.cpu_percent(interval=0.5, percpu=True)
    return json.dumps({"overall_percent": round(sum(per_core) / len(per_core), 1), "per_core": per_core})


def get_memory_usage() -> str:
    """RAM usage of this computer."""
    m = psutil.virtual_memory()
    return json.dumps({"total": _gb(m.total), "used": _gb(m.used), "available": _gb(m.available), "percent": m.percent})


def get_disk_usage() -> str:
    """Disk usage of the main drive."""
    root = os.path.abspath(os.sep)
    d = psutil.disk_usage(root)
    return json.dumps({"drive": root, "total": _gb(d.total), "used": _gb(d.used), "free": _gb(d.free), "percent": d.percent})


def get_current_time() -> str:
    """Current local date and time."""
    return datetime.now().strftime("%A, %d %B %Y, %I:%M %p")


# ============ 4. Web ============

def web_search(query: str) -> str:
    """Search the web for up-to-date information (uses Tavily, falls back to DuckDuckGo)."""
    try:
        if settings.tavily_api_key:
            r = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": settings.tavily_api_key, "query": query, "max_results": 5},
                timeout=20,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            return "\n\n".join(f"{x['title']}\n{x['url']}\n{x.get('content', '')[:400]}" for x in results) or "No results"
        r = httpx.get("https://api.duckduckgo.com/", params={"q": query, "format": "json", "no_html": 1}, timeout=15)
        data = r.json()
        parts = [data.get("AbstractText", "")] + [t.get("Text", "") for t in data.get("RelatedTopics", [])[:5] if isinstance(t, dict)]
        text = "\n".join(p for p in parts if p)
        return text or "No instant answer found. Add TAVILY_API_KEY to .env for full web search."
    except Exception as e:  # network errors should not crash the agent
        return f"Web search failed: {e}"


# ============ registry ============

TOOLS = {
    "filesystem": [list_directory, read_file, write_file, search_files],
    "database": [list_tables, describe_table, run_sql_query],
    "system": [get_system_info, get_cpu_usage, get_memory_usage, get_disk_usage, get_current_time],
    "web": [web_search],
}

ALL_TOOLS = {fn.__name__: fn for group in TOOLS.values() for fn in group}


def describe_tools() -> list[dict]:
    import inspect
    out = []
    for category, fns in TOOLS.items():
        for fn in fns:
            params = list(inspect.signature(fn).parameters)
            out.append({"name": fn.__name__, "category": category,
                        "description": (fn.__doc__ or "").strip(), "params": params})
    return out


def call_tool(name: str, args: dict | None = None) -> str:
    if name not in ALL_TOOLS:
        return f"Unknown tool '{name}'"
    try:
        return ALL_TOOLS[name](**(args or {}))
    except Exception as e:
        return f"Tool error: {e}"


def as_langchain_tools():
    from langchain_core.tools import StructuredTool
    return [StructuredTool.from_function(fn) for fn in ALL_TOOLS.values()]

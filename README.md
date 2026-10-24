# Multi-Agent AI Automation System with MCP Integration

A full-stack platform where **three AI agent frameworks** — **LangChain**, **LangGraph** and **CrewAI** — answer questions, research topics and take real actions through **Model Context Protocol (MCP)** tools. All agents run on **Groq-hosted LLaMA 3.3 70B**, with **RAG** over your own documents stored in **ChromaDB**.

> MCA Major Project · Presidency University, School of Information Science · Nithin Gowda A

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal) ![Next.js](https://img.shields.io/badge/Next.js-15-black) ![LLM](https://img.shields.io/badge/LLM-Groq%20LLaMA%203.3%2070B-orange)

---

## Features

- **3 agent frameworks, one interface**
  - **LangChain** — fast assistant with RAG and MCP tool calling (ReAct loop)
  - **LangGraph** — stateful graph: *Research → Critique → (loop back if needed) → Synthesize*
  - **CrewAI** — a crew of *Researcher, Critic and Writer* agents working in sequence
  - **Auto** mode — a router picks the best agent from the question
- **13 MCP tools** in 4 categories — file system, SQLite database, system information, web search. Also runnable as a standalone MCP server.
- **RAG knowledge base** — upload PDF/DOCX/TXT/MD/CSV/JSON, auto-summary, chunking with overlap, semantic search with cosine similarity
- **Offline embeddings** — custom deterministic **MD5 hash-based embeddings** (no HuggingFace download needed)
- **Real-time streaming** over WebSocket — live tokens, agent steps and tool calls
- **Compare mode** — run all three agents in parallel and compare answers and latency
- **JWT authentication**, prompt templates, chat history, Markdown export, 👍/👎 response rating
- **Zero-config persistence** with SQLite + aiosqlite

## Architecture

```
 Next.js 15 (React 19) ──REST / WebSocket──►  FastAPI
                                                │
                                         Agent Router (auto / manual)
                          ┌─────────────────────┼─────────────────────┐
                     LangChain             LangGraph               CrewAI
                   (RAG + tools)   (research→critique→synth)  (researcher→critic→writer)
                          └──────────┬──────────┴──────────┬──────────┘
                              Groq LLaMA 3.3 70B       MCP tools (13)
                                     │              files · SQLite · system · web
                          ChromaDB (hash embeddings)      SQLite (aiosqlite)
```

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, react-markdown |
| Backend | FastAPI, Uvicorn, WebSockets, Pydantic |
| Agents | LangChain 0.3, LangGraph 0.2, CrewAI 0.86 |
| LLM | Groq API — `llama-3.3-70b-versatile`, `llama-3.1-8b-instant` |
| Vector DB | ChromaDB with custom MD5 hash embeddings |
| Database | SQLite (aiosqlite) |
| Tools | Model Context Protocol (`mcp` Python SDK), psutil, Tavily / DuckDuckGo |
| Auth | JWT (PyJWT) + bcrypt |

## Project structure

```
backend/
  app/
    agents/       langchain_agent.py · langgraph_agent.py · crewai_agent.py · router.py · base.py
    api/          auth · chat (REST + WebSocket + compare) · documents · templates · mcp_routes · health
    mcp/          tools.py (13 tools) · server.py (standalone MCP server)
    rag/          embeddings.py (MD5 hash embeddings) · pipeline.py (chunk → embed → ChromaDB)
    db/           database.py (SQLite schema + helpers)
    core/         config.py · security.py
    llm.py        Groq client
    main.py       FastAPI app
  tests/          test_basic.py
frontend/
  app/            chat (/) · compare · knowledge · tools · login
  components/  lib/
```

## Getting started

### 1. Prerequisites
- **Python 3.11 or 3.12** (CrewAI does not support 3.13 yet)
- **Node.js 18+**
- A free **Groq API key** from https://console.groq.com/keys

### 2. Backend (PowerShell)
```powershell
cd backend
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env      # then open .env and paste your GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

> If PowerShell blocks `Activate.ps1`, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 3. Frontend (new terminal)
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:3000

### 4. Run the MCP server on its own (optional)
```powershell
cd backend
python -m app.mcp.server
```

### 5. Tests
```powershell
cd backend
pytest -q
```

## MCP tools

| Category | Tools |
|---|---|
| File system (sandboxed to `backend/data/workspace`) | `list_directory`, `read_file`, `write_file`, `search_files` |
| SQLite database (read-only) | `list_tables`, `describe_table`, `run_sql_query` |
| System information | `get_system_info`, `get_cpu_usage`, `get_memory_usage`, `get_disk_usage`, `get_current_time` |
| Web | `web_search` |

## How the hash embeddings work

HuggingFace model downloads were blocked on the development network, so the project uses the *hashing trick*: each word, word-pair and character trigram is MD5-hashed into one of 384 buckets with a +/- sign, weighted, log-scaled and L2-normalised. Texts that share words get similar vectors, and cosine similarity in ChromaDB finds the closest chunks — fully offline and deterministic.

## Key API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| WS | `/api/v1/ws/chat` | Streaming chat (tokens, steps, tool calls) |
| POST | `/api/v1/chat` | Chat (non-streaming) |
| POST | `/api/v1/chat/compare` | Run several agents in parallel |
| POST | `/api/v1/documents` | Upload a document |
| GET | `/api/v1/documents/search?q=` | Semantic search |
| GET | `/api/v1/mcp/tools` | List MCP tools |
| GET | `/api/v1/conversations/{id}/export` | Export chat as Markdown |
| POST | `/api/v1/auth/register` · `/login` | JWT auth |

## License
MIT

"""FastAPI entry point.

Run (from the backend folder):
    uvicorn app.main:app --reload --port 8000
API docs: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, documents, health, mcp_routes, templates
from app.core.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Multi-Agent AI Automation System",
    description="LangGraph · CrewAI · LangChain · Groq LLaMA · ChromaDB RAG · MCP tools",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (health.router, auth.router, chat.router, documents.router, templates.router, mcp_routes.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "Multi-Agent AI Automation System",
        "docs": "/docs",
        "agents": ["langchain", "langgraph", "crewai"],
    }

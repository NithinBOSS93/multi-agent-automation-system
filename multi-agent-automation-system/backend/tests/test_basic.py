"""Basic tests that run without a Groq API key:  pytest -q"""
from fastapi.testclient import TestClient

from app.main import app
from app.mcp.tools import ALL_TOOLS, call_tool
from app.rag.embeddings import cosine_similarity, embed_text
from app.rag.pipeline import chunk_text


def test_embeddings_are_deterministic_and_normalised():
    a, b = embed_text("multi agent system"), embed_text("multi agent system")
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6


def test_similar_texts_score_higher():
    q = embed_text("how do vector databases store embeddings")
    near = embed_text("vector databases store embeddings for similarity search")
    far = embed_text("the cricket match was played in Bengaluru")
    assert cosine_similarity(q, near) > cosine_similarity(q, far)


def test_chunking_with_overlap():
    text = "Sentence number one. " * 200
    chunks = chunk_text(text, size=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_thirteen_mcp_tools():
    assert len(ALL_TOOLS) == 13


def test_file_tools_are_sandboxed():
    assert "outside the workspace" in call_tool("read_file", {"path": "../../etc/passwd"})


def test_sql_tool_is_read_only():
    assert "Only a single SELECT" in call_tool("run_sql_query", {"query": "DELETE FROM users"})


def test_api_endpoints():
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert len(client.get("/api/v1/agents").json()) == 3
        assert len(client.get("/api/v1/mcp/tools").json()) == 13
        r = client.post("/api/v1/mcp/tools/get_current_time", json={"args": {}})
        assert r.status_code == 200
        assert len(client.get("/api/v1/templates").json()) >= 4

"""Chat endpoints: REST, WebSocket streaming, compare mode, history, export, rating."""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.agents.router import AGENTS, run_agent
from app.core.security import decode_token, optional_user
from app.db import database as dbm
from app.db.database import get_db, row_to_dict
from app.llm import MissingAPIKey

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    agent: str = "langchain"
    use_rag: bool = False
    conversation_id: int | None = None


class CompareRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    agents: list[str] = ["langchain", "langgraph", "crewai"]
    use_rag: bool = False


class Rating(BaseModel):
    rating: int = Field(ge=-1, le=1)  # -1 thumbs down, 0 clear, 1 thumbs up


def _uid(user: dict | None) -> int | None:
    return int(user["sub"]) if user else None


async def _prepare(req: ChatRequest, user_id: int | None) -> tuple[int, list[dict]]:
    if req.conversation_id:
        history = await dbm.get_history(req.conversation_id)
        conv_id = req.conversation_id
    else:
        conv_id = await dbm.create_conversation(user_id, req.message, req.agent)
        history = []
    await dbm.add_message(conv_id, "user", req.message)
    return conv_id, history


async def _save_answer(conv_id: int, result: dict) -> int:
    meta = {k: result.get(k) for k in ("sources", "tools_used", "steps", "latency")}
    return await dbm.add_message(conv_id, "assistant", result["answer"], result["agent"], meta)


@router.get("/agents")
async def list_agents():
    return [{"id": k, "label": v["label"], "description": v["description"]} for k, v in AGENTS.items()]


@router.post("/chat")
async def chat(req: ChatRequest, user: dict | None = Depends(optional_user)):
    conv_id, history = await _prepare(req, _uid(user))
    try:
        result = await run_agent(req.agent, req.message, history, req.use_rag)
    except MissingAPIKey as e:
        raise HTTPException(500, str(e))
    msg_id = await _save_answer(conv_id, result)
    return {"conversation_id": conv_id, "message_id": msg_id, **result}


@router.websocket("/ws/chat")
async def chat_ws(ws: WebSocket, token: str | None = Query(default=None)):
    """Client sends ChatRequest JSON; server streams events:
    step / tool / token ... then done (or error)."""
    await ws.accept()
    user = decode_token(token) if token else None
    try:
        while True:
            req = ChatRequest(**json.loads(await ws.receive_text()))
            conv_id, history = await _prepare(req, _uid(user))
            await ws.send_json({"type": "start", "conversation_id": conv_id, "agent": req.agent})

            async def emit(event: dict):
                await ws.send_json(event)

            try:
                result = await run_agent(req.agent, req.message, history, req.use_rag, emit)
                msg_id = await _save_answer(conv_id, result)
                await ws.send_json({"type": "done", "conversation_id": conv_id, "message_id": msg_id,
                                    **{k: result.get(k) for k in ("agent", "sources", "tools_used", "steps", "latency")}})
            except Exception as e:  # report the error to the UI and keep the socket open
                await ws.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        return


@router.post("/chat/compare")
async def compare(req: CompareRequest):
    """Run the same question on several agents in parallel and compare."""
    async def one(agent: str):
        try:
            return await run_agent(agent, req.message, [], req.use_rag)
        except Exception as e:
            return {"agent": agent, "answer": f"Error: {e}", "latency": None, "steps": [], "tools_used": [], "sources": []}
    return await asyncio.gather(*(one(a) for a in req.agents))


# ---------- history ----------

@router.get("/conversations")
async def conversations(user: dict | None = Depends(optional_user)):
    uid = _uid(user)
    async with get_db() as db:
        if uid is None:
            cur = await db.execute("SELECT * FROM conversations WHERE user_id IS NULL ORDER BY id DESC LIMIT 50")
        else:
            cur = await db.execute("SELECT * FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT 50", (uid,))
        return [dict(r) for r in await cur.fetchall()]


@router.get("/conversations/{conv_id}")
async def conversation(conv_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        conv = await cur.fetchone()
        if not conv:
            raise HTTPException(404, "Conversation not found")
        cur = await db.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,))
        msgs = [row_to_dict(r) for r in await cur.fetchall()]
    return {**dict(conv), "messages": msgs}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        await db.commit()
    return {"deleted": conv_id}


@router.get("/conversations/{conv_id}/export", response_class=PlainTextResponse)
async def export_conversation(conv_id: int):
    data = await conversation(conv_id)
    lines = [f"# {data['title']}", f"_Agent: {data['agent']} · {data['created_at']}_", ""]
    for m in data["messages"]:
        who = "**You**" if m["role"] == "user" else f"**{(m.get('agent') or 'assistant').title()}**"
        lines += [who, "", m["content"], ""]
    return PlainTextResponse("\n".join(lines), headers={
        "Content-Disposition": f'attachment; filename="conversation-{conv_id}.md"'})


@router.post("/messages/{msg_id}/rate")
async def rate(msg_id: int, body: Rating):
    async with get_db() as db:
        await db.execute("UPDATE messages SET rating = ? WHERE id = ?", (body.rating or None, msg_id))
        await db.commit()
    return {"message_id": msg_id, "rating": body.rating}

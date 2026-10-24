"""Prompt templates (reusable prompts with {placeholders})."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import optional_user
from app.db.database import get_db, now

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=4000)
    agent: str = "langchain"


@router.get("")
async def list_templates(user: dict | None = Depends(optional_user)):
    uid = int(user["sub"]) if user else -1
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM templates WHERE user_id IS NULL OR user_id = ? ORDER BY id", (uid,))
        return [dict(r) for r in await cur.fetchall()]


@router.post("")
async def create_template(body: TemplateIn, user: dict | None = Depends(optional_user)):
    uid = int(user["sub"]) if user else None
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO templates (user_id, name, prompt, agent, created_at) VALUES (?, ?, ?, ?, ?)",
            (uid, body.name, body.prompt, body.agent, now()))
        await db.commit()
        return {"id": cur.lastrowid, **body.model_dump()}


@router.delete("/{template_id}")
async def delete_template(template_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        await db.commit()
    return {"deleted": template_id}

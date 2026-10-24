"""Knowledge base: upload (with auto-summary), list, search, delete."""
import asyncio

from fastapi import APIRouter, File, HTTPException, UploadFile
from langchain_core.messages import HumanMessage, SystemMessage

from app.db.database import get_db, now
from app.rag import pipeline

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED = (".pdf", ".docx", ".txt", ".md", ".csv", ".json")
MAX_BYTES = 10 * 1024 * 1024


async def _summarize(text: str) -> str:
    try:
        from app.llm import get_llm
        llm = get_llm(fast=True, streaming=False)
        msg = await llm.ainvoke([
            SystemMessage("Summarize the document in 3-4 short sentences."),
            HumanMessage(text[:6000]),
        ])
        return msg.content
    except Exception as e:
        return f"(summary unavailable: {e})"


@router.post("")
async def upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(ALLOWED):
        raise HTTPException(400, f"Supported types: {', '.join(ALLOWED)}")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(400, "File too large (max 10 MB)")
    text = await asyncio.to_thread(pipeline.extract_text, file.filename, data)
    if not text.strip():
        raise HTTPException(400, "No text could be extracted from this file")

    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO documents (filename, chunks, created_at) VALUES (?, 0, ?)", (file.filename, now()))
        await db.commit()
        doc_id = cur.lastrowid

    chunks = await asyncio.to_thread(pipeline.add_document, doc_id, file.filename, text)
    summary = await _summarize(text)
    async with get_db() as db:
        await db.execute("UPDATE documents SET chunks = ?, summary = ? WHERE id = ?", (chunks, summary, doc_id))
        await db.commit()
    return {"id": doc_id, "filename": file.filename, "chunks": chunks, "summary": summary}


@router.get("")
async def list_documents():
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM documents ORDER BY id DESC")
        return [dict(r) for r in await cur.fetchall()]


@router.get("/search")
async def search(q: str, k: int = 4):
    return await asyncio.to_thread(pipeline.search, q, k)


@router.delete("/{doc_id}")
async def delete(doc_id: int):
    await asyncio.to_thread(pipeline.delete_document, doc_id)
    async with get_db() as db:
        await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        await db.commit()
    return {"deleted": doc_id}

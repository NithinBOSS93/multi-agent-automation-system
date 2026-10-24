"""RAG pipeline: load -> chunk -> embed -> store in ChromaDB -> retrieve top-k."""
import io
import uuid
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.rag.embeddings import HashEmbeddingFunction


@lru_cache
def get_collection():
    client = chromadb.PersistentClient(
        path=str(settings.chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=settings.collection_name,
        embedding_function=HashEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


# ---------- loading ----------

def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith(".docx"):
        import docx
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    return data.decode("utf-8", errors="ignore")


# ---------- chunking ----------

def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split on paragraph boundaries, then pack into ~size char chunks with overlap."""
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    text = " ".join(text.split("\n\n")).strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        # try not to cut a sentence in half
        if end < len(text):
            cut = text.rfind(". ", start, end)
            if cut > start + size // 2:
                end = cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


# ---------- store / query ----------

def add_document(doc_id: int, filename: str, text: str) -> int:
    chunks = chunk_text(text)
    if not chunks:
        return 0
    get_collection().add(
        ids=[f"{doc_id}-{i}-{uuid.uuid4().hex[:6]}" for i in range(len(chunks))],
        documents=chunks,
        metadatas=[{"doc_id": doc_id, "source": filename, "chunk": i} for i in range(len(chunks))],
    )
    return len(chunks)


def search(query: str, k: int | None = None) -> list[dict]:
    col = get_collection()
    if col.count() == 0:
        return []
    k = min(k or settings.top_k, col.count())
    res = col.query(query_texts=[query], n_results=k)
    hits = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({"text": text, "source": meta.get("source"), "score": round(1 - dist, 3)})
    return hits


def delete_document(doc_id: int) -> None:
    get_collection().delete(where={"doc_id": doc_id})


def build_context(query: str) -> tuple[str, list[dict]]:
    hits = search(query)
    if not hits:
        return "", []
    context = "\n\n".join(f"[{i + 1}] ({h['source']}) {h['text']}" for i, h in enumerate(hits))
    return context, hits

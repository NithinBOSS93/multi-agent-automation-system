"use client";

import { useEffect, useRef, useState } from "react";
import { DocumentRow, Source, api } from "@/lib/api";

export default function KnowledgePage() {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [over, setOver] = useState(false);
  const [uploading, setUploading] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Source[] | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = () => api<DocumentRow[]>("/documents").then(setDocs).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function upload(files: FileList | null) {
    if (!files) return;
    setError("");
    for (const f of Array.from(files)) {
      setUploading(f.name);
      const form = new FormData();
      form.append("file", f);
      try { await api("/documents", { method: "POST", body: form }); }
      catch (e: any) { setError(`${f.name}: ${e.message}`); }
    }
    setUploading("");
    load();
  }

  async function remove(id: number) {
    await api(`/documents/${id}`, { method: "DELETE" });
    load();
  }

  async function search() {
    if (!query.trim()) return;
    setHits(await api<Source[]>(`/documents/search?q=${encodeURIComponent(query)}`));
  }

  return (
    <div className="page">
      <h1>Knowledge base</h1>
      <p className="muted">Upload PDF, DOCX, TXT, MD, CSV or JSON. Files are split into chunks, embedded with MD5 hash embeddings and stored in ChromaDB.</p>

      <div className={`drop ${over ? "over" : ""}`} style={{ margin: "16px 0" }}
        onClick={() => fileInput.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); }}>
        {uploading ? `Uploading and summarising ${uploading}…` : "Drop files here or click to choose"}
        <input ref={fileInput} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.csv,.json"
          onChange={(e) => upload(e.target.files)} />
      </div>
      {error && <p className="error small">{error}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Semantic search</h2>
        <div className="row" style={{ flexWrap: "nowrap" }}>
          <input className="input" placeholder="Search your documents…" value={query}
            onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} />
          <button className="btn" onClick={search}>Search</button>
        </div>
        {hits && hits.length === 0 && <p className="muted small">No matches.</p>}
        {hits?.map((h, i) => (
          <div key={i} style={{ marginTop: 10 }}>
            <b className="small">{h.source}</b> <span className="muted small">cosine score {h.score}</span>
            <pre>{h.text}</pre>
          </div>
        ))}
      </div>

      <h2>Documents ({docs.length})</h2>
      <div className="grid">
        {docs.map((d) => (
          <div key={d.id} className="card">
            <div className="row">
              <b style={{ wordBreak: "break-all" }}>{d.filename}</b>
              <span className="spacer" />
              <button className="btn small" onClick={() => remove(d.id)}>Delete</button>
            </div>
            <div className="small muted">{d.chunks} chunks · {new Date(d.created_at).toLocaleString()}</div>
            {d.summary && <p className="small">{d.summary}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

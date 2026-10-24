"use client";

import { useState } from "react";
import Markdown from "@/components/Markdown";
import { AGENT_INFO, api } from "@/lib/api";

interface Result { agent: string; answer: string; latency: number | null; steps: string[]; tools_used: string[] }

export default function ComparePage() {
  const [question, setQuestion] = useState("");
  const [useRag, setUseRag] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    if (!question.trim()) return;
    setBusy(true); setError(""); setResults([]);
    try {
      setResults(await api<Result[]>("/chat/compare", {
        method: "POST", body: JSON.stringify({ message: question, use_rag: useRag }),
      }));
    } catch (e: any) { setError(e.message); }
    setBusy(false);
  }

  const fastest = results.filter((r) => r.latency != null).sort((a, b) => a.latency! - b.latency!)[0];

  return (
    <div className="page">
      <h1>Compare agents</h1>
      <p className="muted">Send the same question to LangChain, LangGraph and CrewAI in parallel and compare answers and speed.</p>
      <div className="card" style={{ marginBottom: 16 }}>
        <textarea className="textarea" style={{ minHeight: 70 }} placeholder="e.g. Explain the difference between RAG and fine-tuning"
          value={question} onChange={(e) => setQuestion(e.target.value)} />
        <div className="row" style={{ marginTop: 10 }}>
          <label className="row small muted" style={{ gap: 6 }}>
            <input type="checkbox" checked={useRag} onChange={(e) => setUseRag(e.target.checked)} /> Use my documents
          </label>
          <span className="spacer" />
          <button className="btn primary" disabled={busy || !question.trim()} onClick={run}>
            {busy ? "Running all 3 agents…" : "Compare"}
          </button>
        </div>
        {error && <div className="error small">{error}</div>}
      </div>
      <div className="grid">
        {results.map((r) => (
          <div key={r.agent} className="card">
            <div className="row" style={{ marginBottom: 8 }}>
              <b style={{ color: AGENT_INFO[r.agent]?.color }}>{AGENT_INFO[r.agent]?.label}</b>
              <span className="spacer" />
              {r.latency != null && <span className="small muted">{r.latency}s</span>}
              {fastest?.agent === r.agent && <span className="pill small" style={{ color: "var(--ok)" }}>fastest</span>}
            </div>
            <div className="small muted" style={{ marginBottom: 8 }}>{r.steps.join(" → ")}</div>
            <Markdown text={r.answer} />
          </div>
        ))}
      </div>
    </div>
  );
}

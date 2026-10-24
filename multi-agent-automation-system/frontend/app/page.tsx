"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Markdown from "@/components/Markdown";
import {
  AGENT_INFO, API, AgentId, Conversation, Message, StepEvent, Template, ToolEvent, api, chatSocket,
} from "@/lib/api";

export default function ChatPage() {
  const [agent, setAgent] = useState<AgentId>("langchain");
  const [useRag, setUseRag] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [convId, setConvId] = useState<number | null>(null);
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const ws = useRef<WebSocket | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const loadConvs = useCallback(() => {
    api<Conversation[]>("/conversations").then(setConvs).catch(() => {});
  }, []);

  useEffect(() => {
    loadConvs();
    api<Template[]>("/templates").then(setTemplates).catch(() => {});
    return () => ws.current?.close();
  }, [loadConvs]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  function patchLast(fn: (m: Message) => Message) {
    setMessages((prev) => [...prev.slice(0, -1), fn(prev[prev.length - 1])]);
  }

  function getSocket(): Promise<WebSocket> {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) return Promise.resolve(ws.current);
    return new Promise((resolve, reject) => {
      const s = chatSocket();
      s.onopen = () => { ws.current = s; resolve(s); };
      s.onerror = () => reject(new Error(`Cannot reach the backend at ${API}. Is it running?`));
      s.onmessage = (ev) => handleEvent(JSON.parse(ev.data));
      s.onclose = () => { ws.current = null; setBusy(false); };
    });
  }

  function handleEvent(e: any) {
    switch (e.type) {
      case "start":
        setConvId(e.conversation_id);
        break;
      case "step":
        patchLast((m) => ({ ...m, live: { ...m.live!, steps: [...m.live!.steps, e as StepEvent] } }));
        break;
      case "tool":
        patchLast((m) => ({ ...m, live: { ...m.live!, tools: [...m.live!.tools, e as ToolEvent] } }));
        break;
      case "token":
        patchLast((m) => ({ ...m, content: m.content + e.content }));
        break;
      case "done":
        patchLast((m) => ({ ...m, id: e.message_id, agent: e.agent,
          meta: { sources: e.sources, tools_used: e.tools_used, steps: e.steps, latency: e.latency } }));
        setBusy(false);
        loadConvs();
        break;
      case "error":
        setError(e.message);
        setMessages((prev) => prev.slice(0, -1));
        setBusy(false);
        break;
    }
  }

  async function send(text = input) {
    if (!text.trim() || busy) return;
    setError("");
    setInput("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", agent, live: { steps: [], tools: [] } },
    ]);
    try {
      const s = await getSocket();
      s.send(JSON.stringify({ message: text, agent, use_rag: useRag, conversation_id: convId }));
    } catch (err: any) {
      setError(err.message);
      setMessages((prev) => prev.slice(0, -2));
      setBusy(false);
    }
  }

  async function openConv(id: number) {
    const data = await api<{ messages: Message[] }>(`/conversations/${id}`);
    setConvId(id);
    setMessages(data.messages);
  }

  async function deleteConv(id: number) {
    await api(`/conversations/${id}`, { method: "DELETE" });
    if (id === convId) newChat();
    loadConvs();
  }

  function newChat() { setConvId(null); setMessages([]); setError(""); }

  async function rate(m: Message, value: number) {
    if (!m.id) return;
    const next = m.rating === value ? 0 : value;
    await api(`/messages/${m.id}/rate`, { method: "POST", body: JSON.stringify({ rating: next }) });
    setMessages((prev) => prev.map((x) => (x.id === m.id ? { ...x, rating: next || null } : x)));
  }

  function useTemplate(t: Template) {
    setAgent(t.agent as AgentId);
    setInput(t.prompt);
  }

  return (
    <div className="chat">
      <aside className="sidebar">
        <button className="btn primary" style={{ width: "100%", marginBottom: 12 }} onClick={newChat}>+ New chat</button>
        <div className="muted small" style={{ margin: "4px 0" }}>History</div>
        {convs.length === 0 && <div className="muted small">No conversations yet</div>}
        {convs.map((c) => (
          <div key={c.id} className={`conv ${c.id === convId ? "active" : ""}`} onClick={() => openConv(c.id)}>
            <span className="title">{c.title}</span>
            <button className="btn small ghost" title="Delete"
              onClick={(e) => { e.stopPropagation(); deleteConv(c.id); }}>×</button>
          </div>
        ))}
        <div className="muted small" style={{ margin: "16px 0 4px" }}>Prompt templates</div>
        {templates.map((t) => (
          <div key={t.id} className="conv" onClick={() => useTemplate(t)}>
            <span className="title">{t.name}</span>
          </div>
        ))}
      </aside>

      <section className="chat-main">
        <div className="messages">
          {messages.length === 0 && (
            <div className="msg" style={{ marginTop: "8vh", textAlign: "center" }}>
              <h1>Multi-Agent AI Automation System</h1>
              <p className="muted">Pick an agent, optionally switch on your documents, and ask anything.<br />
                Try: &ldquo;Check my CPU and memory usage&rdquo; or &ldquo;Research the pros and cons of vector databases&rdquo;.</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.role === "assistant" && m.agent && (
                <div className="small" style={{ color: AGENT_INFO[m.agent]?.color, marginBottom: 4 }}>
                  {AGENT_INFO[m.agent]?.label ?? m.agent}
                </div>
              )}
              <div className={`bubble ${busy && i === messages.length - 1 && m.role === "assistant" ? "cursor" : ""}`}>
                {m.role === "assistant" ? <Markdown text={m.content} /> : m.content}
              </div>
              {m.role === "assistant" && <Trace m={m} onRate={(v) => rate(m, v)} />}
            </div>
          ))}
          <div ref={bottom} />
        </div>

        <div className="composer">
          <div className="composer-inner">
            <div className="row">
              <div className="agents">
                {(Object.keys(AGENT_INFO) as AgentId[]).map((id) => (
                  <button key={id} title={AGENT_INFO[id].blurb}
                    className={`agent-btn ${agent === id ? "active" : ""}`}
                    style={{ color: AGENT_INFO[id].color, borderColor: agent === id ? AGENT_INFO[id].color : undefined }}
                    onClick={() => setAgent(id)}>{AGENT_INFO[id].label}</button>
                ))}
              </div>
              <span className="spacer" />
              <label className="row small muted" style={{ gap: 6, cursor: "pointer" }}>
                <input type="checkbox" checked={useRag} onChange={(e) => setUseRag(e.target.checked)} />
                Use my documents (RAG)
              </label>
              {convId && (
                <a className="btn small" href={`${API}/api/v1/conversations/${convId}/export`}>Export</a>
              )}
            </div>
            {error && <div className="error small">{error}</div>}
            <div className="row" style={{ flexWrap: "nowrap" }}>
              <textarea className="textarea" placeholder="Ask the agents…  (Enter to send, Shift+Enter for a new line)"
                value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
              <button className="btn primary" disabled={busy || !input.trim()} onClick={() => send()}>
                {busy ? "…" : "Send"}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function Trace({ m, onRate }: { m: Message; onRate: (v: number) => void }) {
  const steps = m.live?.steps ?? [];
  const tools = m.live?.tools ?? [];
  const meta = m.meta;
  return (
    <div className="trace">
      <div className="row">
        {steps.length > 0 && <span>{steps.map((s) => s.name).join(" → ")}</span>}
        {meta?.latency != null && <span>· {meta.latency}s</span>}
        {meta?.tools_used && meta.tools_used.length > 0 && <span>· tools: {Array.from(new Set(meta.tools_used)).join(", ")}</span>}
        <span className="spacer" />
        {m.id && (
          <>
            <button className="btn small ghost" style={{ opacity: m.rating === 1 ? 1 : 0.5 }} onClick={() => onRate(1)}>👍</button>
            <button className="btn small ghost" style={{ opacity: m.rating === -1 ? 1 : 0.5 }} onClick={() => onRate(-1)}>👎</button>
          </>
        )}
      </div>
      {tools.length > 0 && (
        <details>
          <summary>MCP tool calls ({tools.length})</summary>
          {tools.map((t, i) => (
            <div key={i}><code>{t.name}({JSON.stringify(t.args)})</code><pre>{t.result}</pre></div>
          ))}
        </details>
      )}
      {meta?.sources && meta.sources.length > 0 && (
        <details>
          <summary>Document sources ({meta.sources.length})</summary>
          {meta.sources.map((s, i) => (
            <div key={i}><b>[{i + 1}] {s.source}</b> <span className="muted">score {s.score}</span><pre>{s.text}</pre></div>
          ))}
        </details>
      )}
    </div>
  );
}

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const WS = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
const V1 = `${API}/api/v1`;

export type AgentId = "langchain" | "langgraph" | "crewai" | "auto";

export interface Source { text: string; source: string; score: number }
export interface ToolEvent { name: string; args: Record<string, unknown>; result: string }
export interface StepEvent { name: string; detail: string }

export interface Message {
  id?: number;
  role: "user" | "assistant";
  content: string;
  agent?: string;
  rating?: number | null;
  meta?: { sources?: Source[]; tools_used?: string[]; steps?: string[]; latency?: number };
  live?: { steps: StepEvent[]; tools: ToolEvent[] };
}

export interface Conversation { id: number; title: string; agent: string; created_at: string }
export interface Template { id: number; name: string; prompt: string; agent: string; user_id: number | null }
export interface DocumentRow { id: number; filename: string; chunks: number; summary: string; created_at: string }
export interface Tool { name: string; category: string; description: string; params: string[] }

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try { return localStorage.getItem("token"); } catch { return null; }
}
export function getUsername(): string | null {
  if (typeof window === "undefined") return null;
  try { return localStorage.getItem("username"); } catch { return null; }
}
export function setAuth(token: string | null, username: string | null) {
  try {
    if (token && username) { localStorage.setItem("token", token); localStorage.setItem("username", username); }
    else { localStorage.removeItem("token"); localStorage.removeItem("username"); }
  } catch { /* storage unavailable */ }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (!(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${V1}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* not json */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export function chatSocket(): WebSocket {
  const token = getToken();
  return new WebSocket(`${WS}/api/v1/ws/chat${token ? `?token=${token}` : ""}`);
}

export const AGENT_INFO: Record<string, { label: string; color: string; blurb: string }> = {
  auto: { label: "Auto", color: "var(--muted)", blurb: "Router picks the best agent" },
  langchain: { label: "LangChain", color: "var(--lc)", blurb: "Fast · RAG · MCP tools" },
  langgraph: { label: "LangGraph", color: "var(--lg)", blurb: "Research → Critique → Synthesize" },
  crewai: { label: "CrewAI", color: "var(--ca)", blurb: "Researcher · Critic · Writer" },
};

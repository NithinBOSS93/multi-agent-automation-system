"use client";

import { useEffect, useState } from "react";
import { Tool, api } from "@/lib/api";

const CATEGORY_LABEL: Record<string, string> = {
  filesystem: "File system", database: "SQLite database", system: "System information", web: "Web",
};

export default function ToolsPage() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [args, setArgs] = useState<Record<string, Record<string, string>>>({});
  const [output, setOutput] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  useEffect(() => { api<Tool[]>("/mcp/tools").then(setTools).catch((e) => setError(e.message)); }, []);

  async function run(t: Tool) {
    setOutput((o) => ({ ...o, [t.name]: "Running…" }));
    const res = await api<{ result: string }>(`/mcp/tools/${t.name}`, {
      method: "POST", body: JSON.stringify({ args: args[t.name] ?? {} }),
    });
    setOutput((o) => ({ ...o, [t.name]: res.result }));
  }

  const categories = Array.from(new Set(tools.map((t) => t.category)));

  return (
    <div className="page">
      <h1>MCP tools explorer</h1>
      <p className="muted">
        {tools.length} Model Context Protocol tools the agents can call. They are also served as a standalone MCP
        server: <code>python -m app.mcp.server</code>
      </p>
      {error && <p className="error">{error}</p>}
      {categories.map((cat) => (
        <section key={cat} style={{ marginTop: 20 }}>
          <h2>{CATEGORY_LABEL[cat] ?? cat}</h2>
          <div className="grid">
            {tools.filter((t) => t.category === cat).map((t) => (
              <div key={t.name} className="card">
                <code><b>{t.name}</b></code>
                <p className="small muted" style={{ margin: "6px 0" }}>{t.description}</p>
                {t.params.map((p) => (
                  <input key={p} className="input" style={{ marginBottom: 6 }} placeholder={p}
                    value={args[t.name]?.[p] ?? ""}
                    onChange={(e) => setArgs((a) => ({ ...a, [t.name]: { ...a[t.name], [p]: e.target.value } }))} />
                ))}
                <button className="btn small" onClick={() => run(t)}>Run</button>
                {output[t.name] && <pre style={{ maxHeight: 220, overflowY: "auto" }}>{output[t.name]}</pre>}
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

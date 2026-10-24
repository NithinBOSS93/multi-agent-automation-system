"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setAuth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await api<{ token: string; username: string }>(`/auth/${mode}`, {
        method: "POST", body: JSON.stringify({ username, password }),
      });
      setAuth(res.token, res.username);
      router.push("/");
    } catch (err: any) { setError(err.message); }
  }

  return (
    <div className="page" style={{ maxWidth: 380 }}>
      <div className="card" style={{ marginTop: "10vh" }}>
        <h1>{mode === "login" ? "Log in" : "Create account"}</h1>
        <p className="muted small">Logging in keeps your chats and templates separate from guest chats.</p>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input className="input" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <input className="input" type="password" placeholder="Password (6+ characters)" value={password}
            onChange={(e) => setPassword(e.target.value)} />
          {error && <div className="error small">{error}</div>}
          <button className="btn primary" type="submit">{mode === "login" ? "Log in" : "Register"}</button>
        </form>
        <p className="small muted" style={{ marginBottom: 0 }}>
          {mode === "login" ? "No account? " : "Have an account? "}
          <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === "login" ? "register" : "login"); }}>
            {mode === "login" ? "Register" : "Log in"}
          </a>
        </p>
      </div>
    </div>
  );
}

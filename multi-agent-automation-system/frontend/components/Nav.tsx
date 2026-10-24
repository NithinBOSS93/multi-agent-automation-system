"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getUsername, setAuth } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Chat" },
  { href: "/compare", label: "Compare" },
  { href: "/knowledge", label: "Knowledge Base" },
  { href: "/tools", label: "MCP Tools" },
];

export default function Nav() {
  const path = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<string | null>(null);

  useEffect(() => { setUser(getUsername()); }, [path]);

  return (
    <header className="topbar">
      <div className="brand">Multi-Agent <span>Automation</span></div>
      <nav className="nav">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className={path === l.href ? "active" : ""}>{l.label}</Link>
        ))}
      </nav>
      {user ? (
        <div className="row small">
          <span className="muted">{user}</span>
          <button className="btn small ghost" onClick={() => { setAuth(null, null); setUser(null); router.refresh(); }}>
            Log out
          </button>
        </div>
      ) : (
        <Link href="/login" className="btn small">Log in</Link>
      )}
    </header>
  );
}

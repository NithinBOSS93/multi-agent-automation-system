import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Multi-Agent AI Automation System",
  description: "LangGraph · CrewAI · LangChain · Groq · RAG · MCP",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <Nav />
          <div className="main">{children}</div>
        </div>
      </body>
    </html>
  );
}

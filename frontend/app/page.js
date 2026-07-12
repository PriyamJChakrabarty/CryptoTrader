"use client";

import { useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function sendMessage(e) {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: "user", text: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "agent", text: data.reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: "Error: could not reach the backend. Is it running?" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 600, margin: "40px auto", padding: 16 }}>
      <h1>Crypto Trading Advisor</h1>
      <p style={{ opacity: 0.7 }}>
        Ask about a coin, e.g. &ldquo;should I buy BTC?&rdquo; Not financial advice.
      </p>

      <div style={{ border: "1px solid #334155", borderRadius: 8, padding: 16, minHeight: 300 }}>
        {messages.length === 0 && <p style={{ opacity: 0.5 }}>No messages yet.</p>}
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <strong>{m.role === "user" ? "You" : "Agent"}:</strong>
            <p style={{ margin: "4px 0 0" }}>{m.text}</p>
          </div>
        ))}
        {loading && <p style={{ opacity: 0.5 }}>Thinking...</p>}
      </div>

      <form onSubmit={sendMessage} style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a coin..."
          style={{ flex: 1, padding: 8, borderRadius: 4, border: "1px solid #334155" }}
        />
        <button type="submit" disabled={loading} style={{ padding: "8px 16px" }}>
          Send
        </button>
      </form>
    </main>
  );
}

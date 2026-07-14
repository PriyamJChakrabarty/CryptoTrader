"use client";

import { useState } from "react";
import PriceChart from "./PriceChart";

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
    <main className="mx-auto max-w-2xl space-y-4 p-4">
      <header>
        <h1 className="text-xl font-semibold">Crypto Trading Advisor</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Ask about a coin, or tell it to buy/sell with your paper balance. Not
          financial advice.
        </p>
      </header>

      <PriceChart symbol="btc" />

      <div className="min-h-[300px] space-y-3 rounded-lg border border-black/10 p-4 dark:border-white/10">
        {messages.length === 0 && (
          <p className="text-sm text-neutral-400">No messages yet.</p>
        )}
        {messages.map((m, i) => (
          <div key={i}>
            <span className="text-sm font-medium">
              {m.role === "user" ? "You" : "Agent"}:
            </span>
            <p className="mt-0.5 text-sm">{m.text}</p>
          </div>
        ))}
        {loading && <p className="text-sm text-neutral-400">Thinking...</p>}
      </div>

      <form onSubmit={sendMessage} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a coin, or 'buy $500 of BTC'..."
          className="flex-1 rounded-md border border-black/10 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-white/10"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </main>
  );
}

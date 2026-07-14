"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const REFRESH_MS = 30_000;

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function PriceChart({ symbol = "btc" }) {
  const [data, setData] = useState([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(`${BACKEND_URL}/price-history?symbol=${symbol}&days=1`);
        const json = await res.json();
        if (cancelled) return;
        setData(json.prices.map(([ts, price]) => ({ time: formatTime(ts), price })));
      } catch (err) {
        // Backend unreachable - chart just stays empty/stale.
      }
    }

    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [symbol]);

  return (
    <div className="rounded-lg border border-black/10 dark:border-white/10 bg-[var(--chart-surface)] p-4">
      <h2 className="text-sm text-neutral-500 dark:text-neutral-400 mb-2">
        {symbol.toUpperCase()}/USD — last 24h
      </h2>
      {data.length === 0 ? (
        <p className="flex h-64 items-center justify-center text-sm text-neutral-400">
          Loading chart...
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={256}>
          <LineChart data={data}>
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="var(--chart-axis)"
              tick={{ fontSize: 12 }}
              minTickGap={40}
            />
            <YAxis
              domain={["auto", "auto"]}
              stroke="var(--chart-axis)"
              tick={{ fontSize: 12 }}
              width={70}
              tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
            />
            <Tooltip
              contentStyle={{
                background: "var(--chart-surface)",
                border: "1px solid var(--chart-grid)",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(v) => [`$${Number(v).toLocaleString()}`, "Price"]}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="var(--chart-series-1)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Search, Menu, X, Star, TrendingUp } from "lucide-react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

const TABS = ["Overview", "Portfolio", "Stress Test", "Market"];
const TRENDING = ["AAPL", "TSLA", "BTC-USD", "NVDA", "GOOGL", "MSFT", "META", "SPY"];

// ---------- small reusable pieces ----------

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <p className="text-gray-500 text-xs uppercase tracking-wide mb-2">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function NavButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 rounded-xl mb-1 transition-colors ${
        active ? "bg-indigo-600 text-white" : "text-gray-400 hover:bg-gray-800"
      }`}
    >
      {label}
    </button>
  );
}

// ---------- tab content ----------

function OverviewTab({ data, range, setRange, curve, onRefresh }: any) {
  const metrics = data.metrics || {};
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Return"
          value={metrics["Total Return (%)"] !== undefined ? `${metrics["Total Return (%)"].toFixed(2)}%` : "N/A"}
        />
        <StatCard
          label="Sharpe Ratio"
          value={metrics["Sharpe Ratio"] !== undefined ? metrics["Sharpe Ratio"].toFixed(2) : "N/A"}
        />
        <StatCard
          label="Max Drawdown"
          value={metrics["Max Drawdown (%)"] !== undefined ? `${metrics["Max Drawdown (%)"].toFixed(2)}%` : "N/A"}
        />
        <StatCard label="Signal" value={data.signal} />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <div className="flex justify-between items-center mb-4">
          <h4 className="font-semibold text-gray-300">Equity Curve</h4>
          <div className="flex gap-2">
            {["1W", "1M", "1Y"].map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold ${
                  range === r ? "bg-indigo-600" : "bg-gray-800 text-gray-400"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={curve}>
              <defs>
                <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1f2937" vertical={false} />
              <XAxis dataKey="date" hide />
              <YAxis hide domain={["auto", "auto"]} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: "12px" }} />
              <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} fill="url(#fill)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <button onClick={onRefresh} className="bg-gray-800 hover:bg-gray-700 rounded-xl px-6 py-3 text-sm font-semibold">
        Refresh Analysis
      </button>
    </div>
  );
}

function PortfolioTab() {
  const allocation = [
    { name: "Equities", value: 65, color: "#6366f1" },
    { name: "Bonds", value: 20, color: "#374151" },
    { name: "Alpha", value: 15, color: "#4b5563" },
  ];
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
      <h4 className="font-semibold text-gray-300 mb-6">Asset Allocation</h4>
      <div className="flex flex-col md:flex-row items-center gap-8">
        <div className="w-full md:w-1/2 h-64">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={allocation} dataKey="value" innerRadius={60} outerRadius={100} paddingAngle={4}>
                {allocation.map((a) => (
                  <Cell key={a.name} fill={a.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex gap-8">
          {allocation.map((a) => (
            <div key={a.name} className="text-center">
              <div className="w-3 h-3 rounded-full mx-auto mb-2" style={{ background: a.color }} />
              <p className="text-xs text-gray-400">{a.name}</p>
              <p className="font-bold">{a.value}%</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StressTab({ onRun }: { onRun: () => void }) {
  const events = [
    { name: "2008 Financial Crisis", impact: "-12.4%" },
    { name: "2020 Pandemic Crash", impact: "-8.1%" },
    { name: "2022 Fed Tightening", impact: "+2.4%" },
  ];
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
      <h4 className="font-semibold text-gray-300 mb-6">Crisis Simulation</h4>
      <div className="space-y-3 mb-6">
        {events.map((e) => (
          <div key={e.name} className="flex justify-between items-center bg-gray-800 rounded-xl px-4 py-3">
            <span className="text-sm">{e.name}</span>
            <span className={`font-bold ${e.impact.startsWith("+") ? "text-green-500" : "text-red-500"}`}>
              {e.impact}
            </span>
          </div>
        ))}
      </div>
      <button onClick={onRun} className="bg-indigo-600 hover:bg-indigo-500 rounded-xl px-6 py-3 text-sm font-semibold">
        Run Stress Test
      </button>
    </div>
  );
}

function MarketTab() {
  const bars = [40, 60, 30, 80, 50, 90, 40, 70];
  const liquidity = [
    { label: "M2 Money Supply", value: "Stable" },
    { label: "Repo Market Volume", value: "$1.2T" },
    { label: "Capital Inflow", value: "+$420M" },
  ];
  return (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <h4 className="font-semibold text-gray-300 mb-4">Sentiment</h4>
        <div className="h-40 flex items-end gap-2">
          {bars.map((h, i) => (
            <div key={i} className="flex-1 bg-indigo-600 rounded-t" style={{ height: `${h}%` }} />
          ))}
        </div>
        <p className="text-gray-400 text-sm mt-4">
          Fear & Greed Index: <span className="text-white font-semibold">74 (Extreme Greed)</span>
        </p>
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <h4 className="font-semibold text-gray-300 mb-4">Liquidity</h4>
        <div className="space-y-3">
          {liquidity.map((l) => (
            <div key={l.label} className="flex justify-between border-b border-gray-800 pb-2">
              <span className="text-sm text-gray-400">{l.label}</span>
              <span className="font-semibold">{l.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------- main page ----------

export default function Home() {
  const [entered, setEntered] = useState(false);
  const [tab, setTab] = useState("Overview");
  const [ticker, setTicker] = useState("AAPL");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [range, setRange] = useState("1M");
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [userName, setUserName] = useState("Trader");
  const [risk, setRisk] = useState("Moderate");
  const [showProfile, setShowProfile] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [prices, setPrices] = useState([
    { label: "S&P 500", value: 5241.53, change: 1.2 },
    { label: "VIX", value: 13.42, change: -4.5 },
    { label: "BTC/USD", value: 67241, change: 2.1 },
    { label: "10Y Yield", value: 4.21, change: 0.3 },
  ]);

  // load saved settings once on page load
  useEffect(() => {
    const savedList = localStorage.getItem("watchlist");
    if (savedList) setWatchlist(JSON.parse(savedList));
    const savedName = localStorage.getItem("userName");
    if (savedName) setUserName(savedName);
    const savedRisk = localStorage.getItem("risk");
    if (savedRisk) setRisk(savedRisk);
  }, []);

  // small live-looking price ticker
  useEffect(() => {
    const id = setInterval(() => {
      setPrices((old) =>
        old.map((p) => ({
          ...p,
          value: p.value + (Math.random() - 0.5) * (p.value * 0.001),
          change: p.change + (Math.random() - 0.5) * 0.1,
        }))
      );
    }, 3000);
    return () => clearInterval(id);
  }, []);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  async function analyze(customTicker?: string) {
    const target = customTicker || ticker;
    setTicker(target);
    setLoading(true);
    try {
      const res = await axios.post(`${API_URL}/api/analyze`, {
        ticker: target,
        start_date: "2021-01-01",
        end_date: "2024-03-21",
      });
      setData(res.data);
      setTab("Overview");
      setMenuOpen(false);
      showToast(`Loaded ${target}`);
    } catch (err) {
      console.error(err);
      showToast("Something went wrong, try again");
    } finally {
      setLoading(false);
    }
  }

  function toggleWatch(t: string) {
    const updated = watchlist.includes(t) ? watchlist.filter((x) => x !== t) : [...watchlist, t];
    setWatchlist(updated);
    localStorage.setItem("watchlist", JSON.stringify(updated));
  }

  function saveProfile() {
    localStorage.setItem("userName", userName);
    localStorage.setItem("risk", risk);
    setShowProfile(false);
    showToast("Profile saved");
  }

  function filteredCurve() {
    if (!data?.equity_curve) return [];
    if (range === "1W") return data.equity_curve.slice(-7);
    if (range === "1M") return data.equity_curve.slice(-30);
    return data.equity_curve.slice(-252);
  }

  // ---------- landing screen ----------
  if (!entered) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center p-6">
        <div className="text-center max-w-lg">
          <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <TrendingUp size={32} />
          </div>
          <h1 className="text-5xl font-bold mb-3">QuantVision</h1>
          <p className="text-gray-400 mb-8">
            A simple dashboard to analyze stocks and crypto with an AI trading signal.
          </p>
          <button
            onClick={() => setEntered(true)}
            className="bg-indigo-600 hover:bg-indigo-500 px-8 py-3 rounded-full font-semibold transition-colors"
          >
            Enter Dashboard
          </button>
        </div>
      </div>
    );
  }

  // ---------- dashboard ----------
  return (
    <div className="min-h-screen bg-gray-950 text-white flex">
      {/* mobile top bar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-4 z-30">
        <span className="font-bold text-lg">QuantVision</span>
        <button onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
      </div>

      {menuOpen && (
        <div onClick={() => setMenuOpen(false)} className="fixed inset-0 bg-black/50 z-30 lg:hidden" />
      )}

      {/* sidebar */}
      <aside
        className={`w-72 bg-gray-900 border-r border-gray-800 flex flex-col fixed lg:static top-0 bottom-0 z-40 transition-transform duration-300 ${
          menuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <div className="p-6 hidden lg:block">
          <h1 className="text-xl font-bold">QuantVision</h1>
        </div>

        <nav className="px-4 mt-16 lg:mt-4">
          {TABS.map((t) => (
            <NavButton
              key={t}
              label={t}
              active={tab === t}
              onClick={() => {
                setTab(t);
                setMenuOpen(false);
              }}
            />
          ))}
        </nav>

        {watchlist.length > 0 && (
          <div className="px-4 mt-6">
            <p className="text-xs text-gray-500 uppercase mb-2">Watchlist</p>
            <div className="flex flex-wrap gap-2">
              {watchlist.map((t) => (
                <button
                  key={t}
                  onClick={() => analyze(t)}
                  className="px-3 py-1 bg-gray-800 rounded-lg text-xs hover:bg-indigo-600"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="px-4 mt-6">
          <p className="text-xs text-gray-500 uppercase mb-2">Trending</p>
          <div className="flex flex-wrap gap-2">
            {TRENDING.map((t) => (
              <button
                key={t}
                onClick={() => analyze(t)}
                className="px-3 py-1 bg-gray-800 rounded-lg text-xs hover:bg-indigo-600"
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div className="px-4 mt-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && analyze()}
              placeholder="Ticker e.g. AAPL"
              className="w-full bg-gray-800 rounded-xl py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-indigo-600"
            />
          </div>
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => analyze()}
              disabled={loading}
              className="flex-1 bg-indigo-600 hover:bg-indigo-500 rounded-xl py-2 text-sm font-semibold disabled:opacity-50"
            >
              {loading ? "Analyzing..." : "Analyze"}
            </button>
            <button
              onClick={() => toggleWatch(ticker)}
              className={`w-10 rounded-xl flex items-center justify-center ${
                watchlist.includes(ticker) ? "bg-indigo-600" : "bg-gray-800"
              }`}
              title="Save to watchlist"
            >
              <Star size={16} fill={watchlist.includes(ticker) ? "white" : "none"} />
            </button>
          </div>
        </div>

        <button
          onClick={() => setShowProfile(true)}
          className="mt-auto p-4 border-t border-gray-800 flex items-center gap-3 hover:bg-gray-800"
        >
          <div className="w-9 h-9 bg-indigo-600 rounded-full flex items-center justify-center font-bold">
            {userName[0]}
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold">{userName}</p>
            <p className="text-xs text-gray-400">{risk} risk</p>
          </div>
        </button>
      </aside>

      {/* main content */}
      <main className="flex-1 pt-16 lg:pt-0 overflow-y-auto">
        <header className="p-6 md:p-10 border-b border-gray-800">
          <h2 className="text-2xl md:text-3xl font-bold mb-4">
            {data ? `${data.ticker} Analysis` : `Welcome, ${userName}`}
          </h2>
          <div className="flex flex-wrap gap-6">
            {prices.map((p) => (
              <div key={p.label}>
                <p className="text-xs text-gray-500">{p.label}</p>
                <p className="font-semibold">
                  {p.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}{" "}
                  <span className={p.change > 0 ? "text-green-500" : "text-red-500"}>
                    {p.change > 0 ? "+" : ""}
                    {p.change.toFixed(2)}%
                  </span>
                </p>
              </div>
            ))}
          </div>
        </header>

        <section className="p-6 md:p-10">
          {!data ? (
            <div className="h-96 border-2 border-dashed border-gray-800 rounded-2xl flex items-center justify-center text-gray-500">
              Search a ticker to see the analysis
            </div>
          ) : tab === "Overview" ? (
            <OverviewTab data={data} range={range} setRange={setRange} curve={filteredCurve()} onRefresh={() => analyze()} />
          ) : tab === "Portfolio" ? (
            <PortfolioTab />
          ) : tab === "Stress Test" ? (
            <StressTab onRun={() => showToast("Running stress test...")} />
          ) : (
            <MarketTab />
          )}
        </section>
      </main>

      {/* profile modal */}
      {showProfile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
          <div onClick={() => setShowProfile(false)} className="absolute inset-0 bg-black/60" />
          <div className="relative bg-gray-900 border border-gray-800 rounded-2xl p-8 w-full max-w-sm">
            <h3 className="text-xl font-bold mb-4">Edit Profile</h3>
            <label className="text-xs text-gray-400">Name</label>
            <input
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              className="w-full bg-gray-800 rounded-xl py-2 px-3 mt-1 mb-4 outline-none focus:ring-2 focus:ring-indigo-600"
            />
            <label className="text-xs text-gray-400">Risk tolerance</label>
            <div className="grid grid-cols-3 gap-2 mt-1 mb-6">
              {["Conservative", "Moderate", "Aggressive"].map((r) => (
                <button
                  key={r}
                  onClick={() => setRisk(r)}
                  className={`py-2 rounded-xl text-xs font-semibold ${
                    risk === r ? "bg-indigo-600" : "bg-gray-800 text-gray-400"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
            <button onClick={saveProfile} className="w-full bg-indigo-600 hover:bg-indigo-500 rounded-xl py-2 font-semibold">
              Save
            </button>
          </div>
        </div>
      )}

      {/* toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-indigo-600 px-6 py-3 rounded-xl font-semibold z-50">
          {toast}
        </div>
      )}
    </div>
  );
}

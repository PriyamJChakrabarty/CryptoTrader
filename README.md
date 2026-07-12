# Crypto Trading Advisor

A small agentic chat bot that gives a plain-English BUY / SELL / HOLD
opinion on a crypto coin. It looks up the coin's live price, then a Groq
LLM (via LangChain) reasons about it. Advisory only — no real or simulated
trades, no exchange keys, not financial advice.

```
Browser (frontend/, Next.js)
      -> fetch POST /chat
FastAPI (backend/, Python)
      -> LangChain agent (ChatGroq, tool-calling)
      -> tool: get_crypto_price -> CoinGecko public API (no key needed)
Groq (llama-3.3-70b-versatile)
```

## Setup

### 1. Backend

```
cd backend
uv venv
uv pip install -r requirements.txt
```

Add your [Groq API key](https://console.groq.com) to `backend/.env`:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxx
```

Run it:

```
uv run uvicorn main:app --reload
```

Backend runs on http://localhost:8000.

### 2. Frontend

```
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:3000 and talks to the backend at the URL
set in `frontend/.env.local` (defaults to `http://localhost:8000`).

## Project layout

- `frontend/` — Next.js chat UI (plain JavaScript, one page).
- `backend/` — FastAPI server exposing `POST /chat`, backed by a LangChain
  agent using Groq.
- `brainstorm/` — early spec ideation docs, unrelated to this app.
- `Archive/` — the original, much larger multi-agent CryptoTrader system
  this repo used to contain. See `Archive/README.md` for details.
- `GROQ.md` — a general Groq API integration reference.
- `THEME.md` — the original one-line spec this app was built from.

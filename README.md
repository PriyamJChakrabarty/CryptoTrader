# Crypto Trading Advisor

A small agentic chat bot that gives a plain-English BUY / SELL / HOLD
opinion on a crypto coin, and can act on it with a $10,000 **paper (fake)
money** balance — buying and selling for real inside the app, with no real
exchange or real funds involved anywhere. The frontend also shows a live
24h price chart. Not financial advice.

```
Browser (frontend/, Next.js + Tailwind)
      -> fetch POST /chat, GET /portfolio, GET /price-history
FastAPI (backend/, Python)
      -> LangChain agent (ChatGroq, tool-calling)
      -> tools: get_crypto_price, buy_crypto, sell_crypto, get_portfolio
      -> portfolio.json: fake cash + holdings, no exchange involved
      -> CoinGecko public API (no key needed) for prices/history
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

Check it's working:

```
uv run python test_api.py
```

### 2. Frontend

```
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:3000 and talks to the backend at the URL
set in `frontend/.env.local` (defaults to `http://localhost:8000`).

## Deployment (Railway or Render + Vercel)

Push this repo to GitHub first (`origin` is already set to
`github.com/PriyamJChakrabarty/CryptoTrader`) — Railway, Render, and Vercel
all deploy straight from a GitHub repo. Pick Railway or Render for the
backend (not both); either works with the same Vercel frontend setup below.

### 1a. Backend on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy
   from GitHub repo** → pick this repo.
2. Railway will ask which folder to deploy since this is a monorepo. In the
   service's **Settings → Source**, set **Root Directory** to `backend`.
3. It auto-detects Python (Nixpacks) and uses `backend/railway.json` for the
   start command (`uvicorn main:app --host 0.0.0.0 --port $PORT`) — nothing
   else to configure there.
4. In **Settings → Variables**, add:
   - `GROQ_API_KEY` = your key from console.groq.com
   - `FRONTEND_ORIGIN` = your Vercel URL (you'll get this in step 2 below —
     come back and set it after the frontend is deployed; `https://*.vercel.app`
     wildcards aren't supported, use the exact URL)
5. In **Settings → Networking**, click **Generate Domain** to get a public
   URL like `https://your-app.up.railway.app`.
6. Verify it's live:
   ```
   uv run python test_api.py https://your-app.up.railway.app
   ```
   (run this from `backend/`, with `GROQ_API_KEY` already set on Railway)

### 1b. Backend on Render (alternative to Railway)

This repo includes `render.yaml` at the root, so Render can pick up the
whole service definition automatically:

1. Go to [render.com](https://dashboard.render.com) → **New +** →
   **Blueprint** → connect this GitHub repo. Render reads `render.yaml` and
   proposes a `crypto-trading-backend` web service with **Root Directory**
   already set to `backend`, build command `pip install -r requirements.txt`,
   and start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
2. Click **Apply**. It'll prompt you for the two env vars marked
   `sync: false` in `render.yaml`:
   - `GROQ_API_KEY` = your key from console.groq.com
   - `FRONTEND_ORIGIN` = your Vercel URL (set a placeholder for now, update
     it after step 2 below — Render redeploys automatically when you change
     an env var)
3. Once deployed, your URL is `https://crypto-trading-backend.onrender.com`
   (or check **Settings** for the exact assigned URL).
4. Verify it's live:
   ```
   uv run python test_api.py https://crypto-trading-backend.onrender.com
   ```

   No `render.yaml`? You can also skip the Blueprint and create the service
   manually: **New +** → **Web Service** → pick this repo → set **Root
   Directory** to `backend`, **Build Command** to
   `pip install -r requirements.txt`, **Start Command** to
   `uvicorn main:app --host 0.0.0.0 --port $PORT` → add the same two env
   vars from step 2.

   Note: Render's free plan spins the service down after 15 minutes of
   inactivity, so the first request after idling takes ~30-50s to wake up.

### 2. Frontend on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New → Project** → import
   this GitHub repo.
2. In the import screen, set **Root Directory** to `frontend`. Vercel
   auto-detects Next.js — no build command changes needed.
3. Add an environment variable:
   - `NEXT_PUBLIC_BACKEND_URL` = the Railway URL from step 1 (e.g.
     `https://your-app.up.railway.app`)
4. Click **Deploy**. You'll get a URL like `https://your-app.vercel.app`.
5. Go back to Railway or Render and set `FRONTEND_ORIGIN` to that exact
   Vercel URL, then redeploy the backend so CORS allows requests from it.

### 3. Confirm it all works

Open the Vercel URL in a browser, ask the chat "should I buy ETH?", and
confirm you get a reply. If it fails, open the browser dev tools Network
tab — a CORS error there almost always means `FRONTEND_ORIGIN` on the
backend doesn't exactly match the Vercel URL (check for trailing slashes /
http vs https).

## Project layout

- `frontend/` — Next.js chat UI (plain JavaScript, Tailwind CSS), plus a
  live price chart (`app/PriceChart.js`, via recharts).
- `backend/` — FastAPI server exposing `POST /chat`, `GET /portfolio`, and
  `GET /price-history`, backed by a LangChain agent using Groq.
  `portfolio.py` is the fake-money paper trading ledger (`portfolio.json`,
  gitignored, resets by deleting the file).
- `brainstorm/` — early spec ideation docs, unrelated to this app.
- `Archive/` — the original, much larger multi-agent CryptoTrader system
  this repo used to contain. See `Archive/README.md` for details.
- `GROQ.md` — a general Groq API integration reference.
- `THEME.md` — the original one-line spec this app was built from.

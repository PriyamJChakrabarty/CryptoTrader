import os

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import portfolio
from agent import run_agent
from coins import to_coin_id

app = FastAPI()

# Comma-separated list of exact allowed frontend URLs (e.g. local dev).
origins = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")

# Optional regex for URLs that change per deploy, e.g. Vercel preview
# deployments like https://crypto-trader-<hash>-<team>.vercel.app. Example:
# FRONTEND_ORIGIN_REGEX=https://crypto-trader.*\.vercel\.app
origin_regex = os.getenv("FRONTEND_ORIGIN_REGEX")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    reply = run_agent(request.message)
    return {"reply": reply}


@app.get("/portfolio")
def get_portfolio():
    return portfolio.load()


@app.get("/price-history")
def price_history(symbol: str = "btc", days: int = 1):
    coin_id = to_coin_id(symbol)
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days}
    data = requests.get(url, params=params, timeout=10).json()
    # CoinGecko returns [[timestamp_ms, price], ...]
    return {"prices": data.get("prices", [])}

"""A fake (paper) trading balance, saved to a local JSON file. No real
money or exchange is involved anywhere in this module."""

import json
import os

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")
STARTING_CASH = 10_000.0


def load() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        return {"cash": STARTING_CASH, "holdings": {}}
    with open(PORTFOLIO_FILE) as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)


def buy(symbol: str, usd_amount: float, price: float) -> dict:
    data = load()
    if usd_amount > data["cash"]:
        raise ValueError(f"Not enough paper cash. Balance: ${data['cash']:,.2f}")

    coins_bought = usd_amount / price
    data["cash"] -= usd_amount
    data["holdings"][symbol] = data["holdings"].get(symbol, 0) + coins_bought
    _save(data)
    return data


def sell(symbol: str, usd_amount: float, price: float) -> dict:
    data = load()
    held = data["holdings"].get(symbol, 0)
    coins_to_sell = usd_amount / price
    if coins_to_sell > held:
        raise ValueError(f"Not enough {symbol.upper()} to sell. Holding: {held:.6f}")

    data["holdings"][symbol] = held - coins_to_sell
    data["cash"] += usd_amount
    _save(data)
    return data

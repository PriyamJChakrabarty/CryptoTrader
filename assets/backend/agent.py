import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_groq import ChatGroq

import portfolio
from coins import to_coin_id

load_dotenv()


def _fetch_price(symbol: str) -> float:
    coin_id = to_coin_id(symbol)
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd"}
    data = requests.get(url, params=params, timeout=10).json()
    if coin_id not in data:
        raise ValueError(f"Could not find price data for '{symbol}'.")
    return data[coin_id]["usd"]


@tool
def get_crypto_price(symbol: str) -> str:
    """Look up the current USD price and 24h change for a crypto symbol, e.g. BTC, ETH, SOL."""
    coin_id = to_coin_id(symbol)
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"}
    data = requests.get(url, params=params, timeout=10).json()

    if coin_id not in data:
        return f"Could not find price data for '{symbol}'."

    price = data[coin_id]["usd"]
    change = data[coin_id]["usd_24h_change"]
    return f"{symbol.upper()} price: ${price:,.2f} USD, 24h change: {change:.2f}%"


@tool
def buy_crypto(symbol: str, usd_amount: float) -> str:
    """Buy crypto with paper (fake) money. symbol e.g. BTC, usd_amount is dollars to spend."""
    try:
        price = _fetch_price(symbol)
        data = portfolio.buy(symbol.lower(), usd_amount, price)
    except ValueError as e:
        return str(e)
    return (
        f"Bought ${usd_amount:,.2f} of {symbol.upper()} at ${price:,.2f}. "
        f"Cash left: ${data['cash']:,.2f}"
    )


@tool
def sell_crypto(symbol: str, usd_amount: float) -> str:
    """Sell crypto for paper (fake) money. symbol e.g. BTC, usd_amount is dollars worth to sell."""
    try:
        price = _fetch_price(symbol)
        data = portfolio.sell(symbol.lower(), usd_amount, price)
    except ValueError as e:
        return str(e)
    return (
        f"Sold ${usd_amount:,.2f} of {symbol.upper()} at ${price:,.2f}. "
        f"Cash: ${data['cash']:,.2f}"
    )


@tool
def get_portfolio() -> str:
    """Check the current paper trading cash balance and crypto holdings."""
    data = portfolio.load()
    holdings = {k: v for k, v in data["holdings"].items() if v > 0}
    holdings_str = ", ".join(f"{v:.6f} {k.upper()}" for k, v in holdings.items()) or "none"
    return f"Cash: ${data['cash']:,.2f}. Holdings: {holdings_str}"


SYSTEM_PROMPT = """You are a friendly crypto trading assistant with a paper
(fake money) trading account.

You can:
- Look up live prices with get_crypto_price.
- Buy or sell crypto with buy_crypto / sell_crypto. This spends/earns fake
  paper money only - never real funds.
- Check the current balance and holdings with get_portfolio.

When asked for an opinion on a coin, use get_crypto_price and give a simple
BUY, SELL, or HOLD opinion with one or two short reasons in plain English.

When asked to buy or sell, actually call the buy_crypto or sell_crypto tool
- don't just describe doing it.

Always end analysis answers with: "This is not financial advice. All trades
are simulated with paper money."
"""

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)

tools = [get_crypto_price, buy_crypto, sell_crypto, get_portfolio]
agent = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)


def run_agent(message: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": message}]})
    return result["messages"][-1].content

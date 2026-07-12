import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_groq import ChatGroq

load_dotenv()

# Friendly symbols -> CoinGecko coin ids.
COIN_IDS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "doge": "dogecoin",
    "xrp": "ripple",
    "ada": "cardano",
    "bnb": "binancecoin",
    "matic": "matic-network",
}


@tool
def get_crypto_price(symbol: str) -> str:
    """Look up the current USD price and 24h change for a crypto symbol, e.g. BTC, ETH, SOL."""
    coin_id = COIN_IDS.get(symbol.lower(), symbol.lower())
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"}
    data = requests.get(url, params=params, timeout=10).json()

    if coin_id not in data:
        return f"Could not find price data for '{symbol}'."

    price = data[coin_id]["usd"]
    change = data[coin_id]["usd_24h_change"]
    return f"{symbol.upper()} price: ${price:,.2f} USD, 24h change: {change:.2f}%"


SYSTEM_PROMPT = """You are a friendly crypto trading assistant.

When asked about a coin, use the get_crypto_price tool to check its current
price and 24h change, then give a simple BUY, SELL, or HOLD opinion with one
or two short reasons in plain English.

Always end your answer with: "This is not financial advice."
"""

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)

agent = create_agent(model=llm, tools=[get_crypto_price], system_prompt=SYSTEM_PROMPT)


def run_agent(message: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": message}]})
    return result["messages"][-1].content

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


def to_coin_id(symbol: str) -> str:
    return COIN_IDS.get(symbol.lower(), symbol.lower())

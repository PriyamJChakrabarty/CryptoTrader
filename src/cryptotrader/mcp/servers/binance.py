"""Binance MCP Server — derivatives, funding rate, K-line tools."""

from __future__ import annotations

from cryptotrader.mcp.compat import FastMCP
from cryptotrader.mcp.utils import truncate_response

mcp = FastMCP("cryptotrader-binance")


@mcp.tool()
async def binance_derivatives(symbol: str = "BTC") -> dict:
    from cryptotrader.data.providers.binance import fetch_derivatives_binance

    return truncate_response(await fetch_derivatives_binance(symbol))


@mcp.tool()
async def binance_funding_rate(symbol: str = "BTC") -> dict:
    from cryptotrader.data.providers.binance import fetch_funding_rate_binance

    return truncate_response(await fetch_funding_rate_binance(symbol))


@mcp.tool()
async def binance_klines(symbol: str = "BTC", interval: str = "1h", limit: int = 100) -> dict:
    from cryptotrader.data.market import fetch_klines_binance

    return truncate_response(await fetch_klines_binance(symbol, interval, limit))


if __name__ == "__main__":
    mcp.run(transport="stdio")

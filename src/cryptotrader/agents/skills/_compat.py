"""Compatibility utility functions."""

from __future__ import annotations

from datetime import datetime

from cryptotrader._compat import UTC


def utcnow_str() -> str:
    """Return the current UTC time as an ISO format string."""
    return datetime.now(UTC).strftime("%Y-%m-%d")

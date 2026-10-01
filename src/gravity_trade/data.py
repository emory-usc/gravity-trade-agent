"""Bundled sample market data.

Real-time feeds (options chain, dark pool prints, etc.) require licensed data
providers. To keep the project runnable and reproducible with zero setup, the
repo ships a small set of realistic sample snapshots under ``data/sample/``.

Each JSON file is a single ticker snapshot with the fields the six signal
layers need. The schema is documented in ``data/sample/README.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gravity_trade.config import DATA_DIR


def list_sample_tickers() -> list[str]:
    """Return tickers that ship with sample data."""
    if not DATA_DIR.exists():
        return []
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


def load_sample_data(ticker: str) -> dict[str, Any]:
    """Load a bundled snapshot for ``ticker`` (case-insensitive)."""
    path = DATA_DIR / f"{ticker.upper()}.json"
    if not path.exists():
        available = ", ".join(list_sample_tickers()) or "(none)"
        raise FileNotFoundError(
            f"No sample data for {ticker!r}. Available: {available}. "
            f"Add a snapshot at {path} following data/sample/README.md."
        )
    return json.loads(path.read_text(encoding="utf-8"))

"""Backtest / eval harness.

Reads a newline-delimited JSON log of past signals and outcomes and reports
hit rate overall and by conviction tier. A trade "wins" when the exit moves in
the signaled direction (bull -> exit > entry, bear -> exit < entry).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gravity_trade.config import EVALS_DIR, get_settings


def _win(trade: dict[str, Any]) -> bool:
    direction = trade["direction"]
    entry = float(trade["entry_price"])
    exit_ = float(trade["exit_price"])
    if direction == "bull":
        return exit_ > entry
    if direction == "bear":
        return exit_ < entry
    return False  # neutral trades are not counted as wins


def _bucket(trades: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(trades)
    wins = sum(1 for t in trades if _win(t))
    return {"n": n, "wins": wins, "hit_rate": wins / n if n else 0.0}


def run_backtest(path: str | Path | None = None) -> dict[str, Any]:
    """Run the eval over ``path`` (default evals/paper_trades.jsonl)."""
    path = Path(path) if path else EVALS_DIR / "paper_trades.jsonl"
    trades = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    threshold = get_settings().high_conviction_threshold

    high = [t for t in trades if t.get("conviction", 0) >= threshold]
    low = [t for t in trades if t.get("conviction", 0) < threshold]

    total_wins = sum(1 for t in trades if _win(t))
    return {
        "total": len(trades),
        "wins": total_wins,
        "hit_rate": total_wins / len(trades) if trades else 0.0,
        "threshold": threshold,
        "buckets": {
            f"conviction >= {threshold}": _bucket(high),
            f"conviction < {threshold}": _bucket(low),
        },
    }

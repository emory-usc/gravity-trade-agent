"""Aggregate six layer signals into a conviction score and net direction."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from gravity_trade.config import get_settings
from gravity_trade.models import Direction, LayerSignal, SignalBundle
from gravity_trade.signals import ALL_LAYERS


def compute_bundle(ticker: str, data: dict[str, Any], threshold: int | None = None) -> SignalBundle:
    """Run all six layers and aggregate them into a SignalBundle."""
    threshold = get_settings().high_conviction_threshold if threshold is None else threshold
    layers: list[LayerSignal] = [layer.compute(data) for layer in ALL_LAYERS]

    bullish = sum(1 for s in layers if s.direction == Direction.BULL)
    bearish = sum(1 for s in layers if s.direction == Direction.BEAR)
    conviction = max(bullish, bearish)

    if bullish > bearish:
        direction = Direction.BULL
    elif bearish > bullish:
        direction = Direction.BEAR
    else:
        direction = Direction.NEUTRAL

    as_of = data.get("as_of")
    as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if isinstance(as_of, str) else datetime.utcnow()

    return SignalBundle(
        ticker=ticker,
        as_of=as_of_dt,
        layers=layers,
        bullish_count=bullish,
        bearish_count=bearish,
        conviction=conviction,
        direction=direction,
        high_conviction=conviction >= threshold,
    )

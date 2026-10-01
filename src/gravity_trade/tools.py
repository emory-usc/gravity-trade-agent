"""LangChain tools wrapping the six signal layers.

Each layer is exposed as a callable tool so the LangGraph agent can invoke them
with structured arguments and receive structured, human-readable output. The
tools operate on bundled sample data (or any snapshot following the same
schema) so they are fully deterministic and testable.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from gravity_trade import data as data_module
from gravity_trade.models import Direction
from gravity_trade.scoring import compute_bundle


@tool
def load_ticker_data(ticker: str) -> str:
    """Load the bundled market snapshot for a ticker (e.g. 'NVDA', 'SPY').

    Returns a JSON string with price, beta, options chain, GEX, dark pool prints,
    sector context, and term structure. Raises if no snapshot exists.
    """
    snapshot = data_module.load_sample_data(ticker)
    return json.dumps(snapshot)


@tool
def run_six_layer_scan(ticker: str) -> str:
    """Run the full Gravity Trade six-layer scan for a ticker.

    Returns the aggregated SignalBundle as JSON: per-layer direction/confidence/
    evidence, bullish/bearish counts, conviction (0-6), and net direction.
    """
    snapshot = data_module.load_sample_data(ticker)
    bundle = compute_bundle(ticker, snapshot)
    return bundle.model_dump_json(indent=2)


@tool
def single_layer(ticker: str, layer: str) -> str:
    """Run one specific signal layer for a ticker.

    ``layer`` is one of: max_pain, beta, gex, dark_pool, sector, term_structure.
    """
    from gravity_trade.signals import ALL_LAYERS

    snapshot = data_module.load_sample_data(ticker)
    match = next((l for l in ALL_LAYERS if l.name == layer), None)
    if match is None:
        valid = ", ".join(l.name for l in ALL_LAYERS)
        return f"Unknown layer {layer!r}. Valid: {valid}."
    result = match.compute(snapshot)
    return result.model_dump_json(indent=2)


@tool
def directional_opinion(ticker: str) -> str:
    """Return a short directional verdict (bull/bear/neutral) with conviction."""
    snapshot = data_module.load_sample_data(ticker)
    bundle = compute_bundle(ticker, snapshot)
    return (
        f"{ticker}: {bundle.direction.value.upper()} "
        f"(conviction {bundle.conviction}/6, "
        f"{'high' if bundle.high_conviction else 'low'} conviction)"
    )


ALL_TOOLS = [load_ticker_data, run_six_layer_scan, single_layer, directional_opinion]

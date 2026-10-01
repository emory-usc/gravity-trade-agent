"""HTTP service exposing the Gravity Trade agent (the production entrypoint).

This is what actually gets containerized and deployed to Azure. Endpoints:

    GET  /health           -> liveness probe
    POST /analyze/{ticker} -> six-layer scan; persists + emits telemetry; returns TradeThesis
"""

from __future__ import annotations

from gravity_trade import state_store, telemetry
from gravity_trade.data import load_sample_data
from gravity_trade.models import TradeThesis
from gravity_trade.scoring import compute_bundle
from gravity_trade.thesis import generate_offline_thesis


def create_app():
    """App factory — FastAPI is imported lazily so the core CLI stays light."""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(
        title="Gravity Trade Agent",
        version="0.1.0",
        description="Six-layer directional equities framework exposed over HTTP.",
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/analyze/{ticker}", response_model=TradeThesis)
    def analyze(ticker: str) -> TradeThesis:
        ticker = ticker.upper()
        try:
            data = load_sample_data(ticker)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"No sample data for {ticker}")

        bundle = compute_bundle(ticker, data)
        thesis = generate_offline_thesis(bundle)

        # Production side effects: persist to Cosmos (or local), emit metrics.
        state_store.save_signal(bundle)
        state_store.save_thesis(thesis)
        telemetry.track_scan(bundle)

        return thesis

    return app

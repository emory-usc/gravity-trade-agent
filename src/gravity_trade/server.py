"""HTTP service exposing the Gravity Trade agent (the production entrypoint).

Endpoints:

    GET  /health            -> liveness (always 200 if the process is up)
    GET  /ready             -> readiness (checks Key Vault + Cosmos dependency state)
    POST /analyze/{ticker}  -> six-layer scan; persists + emits telemetry; returns TradeThesis

Security: ``/analyze`` requires an ``X-API-Key`` header when the service API key
is configured (resolved from Key Vault in production). When no key is set (local
development), the endpoint is open so the service remains runnable offline.
"""

from __future__ import annotations

import secrets

from gravity_trade import secret_store, state_store, telemetry
from gravity_trade.config import get_settings
from gravity_trade.data import load_sample_data
from gravity_trade.models import TradeThesis
from gravity_trade.scoring import compute_bundle
from gravity_trade.thesis import generate_offline_thesis


def create_app():
    """App factory — FastAPI is imported lazily so the core CLI stays light."""
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.responses import JSONResponse

    settings = get_settings()

    app = FastAPI(
        title="Gravity Trade Agent",
        version="0.1.0",
        description="Six-layer directional equities framework exposed over HTTP.",
    )

    def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
        if not settings.api_key:
            return  # No key configured -> dev mode, endpoint is open.
        if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> JSONResponse:
        kv_ok, kv_state = secret_store.check_health()
        cosmos_ok, cosmos_state = state_store.check_health()
        deps = {
            "key_vault": kv_state,
            "cosmos": cosmos_state,
            "llm": "configured" if settings.llm_configured else "not_configured",
        }
        healthy = kv_ok and cosmos_ok
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ready" if healthy else "degraded", "dependencies": deps},
        )

    @app.post("/analyze/{ticker}", response_model=TradeThesis, dependencies=[Depends(require_api_key)])
    def analyze(ticker: str) -> TradeThesis:
        ticker = ticker.upper()
        try:
            data = load_sample_data(ticker)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"No sample data for {ticker}")

        bundle = compute_bundle(ticker, data)
        thesis = generate_offline_thesis(bundle)

        # Production side effects: persist + emit metrics. Failures are loud.
        if state_store.save_signal(bundle) == "error":
            telemetry.track_error("persistence_failed", ticker=ticker, record="signal")
        if state_store.save_thesis(thesis) == "error":
            telemetry.track_error("persistence_failed", ticker=ticker, record="thesis")
        telemetry.track_scan(bundle)

        return thesis

    return app

"""Tests for the FastAPI service."""

import pytest
from fastapi.testclient import TestClient

from gravity_trade import state_store
from gravity_trade.server import create_app


@pytest.fixture(autouse=True)
def _isolate_persistence(tmp_path, monkeypatch):
    # Keep the service's side effects (Cosmos/local persistence, telemetry)
    # out of the real repo and the network.
    monkeypatch.setattr(state_store, "_SIGNALS_LOCAL", tmp_path / "signals.jsonl")
    monkeypatch.setattr(state_store, "_THESES_LOCAL", tmp_path / "theses.jsonl")
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("GRAVITY_API_KEY", raising=False)


@pytest.fixture()
def client():
    return TestClient(create_app())


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "cosmos" in body["dependencies"]
    assert "key_vault" in body["dependencies"]


def test_analyze_nvda(client):
    r = client.post("/analyze/NVDA")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "NVDA"
    assert body["direction"] == "bull"
    assert body["conviction"] == 5


def test_analyze_unknown_returns_404(client):
    r = client.post("/analyze/ZZZZ")
    assert r.status_code == 404


def test_analyze_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("GRAVITY_API_KEY", "secret-key")
    c = TestClient(create_app())

    assert c.post("/analyze/NVDA").status_code == 401
    assert c.post("/analyze/NVDA", headers={"X-API-Key": "wrong"}).status_code == 401

    ok = c.post("/analyze/NVDA", headers={"X-API-Key": "secret-key"})
    assert ok.status_code == 200

    # Health and readiness stay unauthenticated (probe endpoints).
    assert c.get("/health").status_code == 200
    assert c.get("/ready").status_code == 200

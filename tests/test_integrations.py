"""Tests for the Azure integration modules' offline/fallback behavior.

The Azure-backed paths (managed identity, Key Vault, Cosmos, App Insights) are
exercised in a real subscription; here we verify the fallback paths and that
the modules import and degrade gracefully without the Azure SDKs present.
"""

import json

from gravity_trade import secret_store, state_store, telemetry
from gravity_trade.data import load_sample_data
from gravity_trade.scoring import compute_bundle


def test_secret_env_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    monkeypatch.delenv("AZURE_KEY_VAULT_URL", raising=False)
    assert secret_store.get_secret("OPENAI_API_KEY") == "test-key-123"


def test_secret_missing_returns_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_KEY_VAULT_URL", raising=False)
    assert secret_store.get_secret("OPENAI_API_KEY") is None


def test_secret_vault_name_mapping(monkeypatch):
    # Env var wins before Key Vault is consulted, so this only checks the
    # env-resolution path does not depend on the Key Vault client.
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.delenv("AZURE_KEY_VAULT_URL", raising=False)
    assert secret_store.get_secret("OPENAI_API_KEY") == "x"


def test_state_store_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "_SIGNALS_LOCAL", tmp_path / "signals.jsonl")
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)

    bundle = compute_bundle("NVDA", load_sample_data("NVDA"))
    assert state_store.save_signal(bundle) == "local"

    lines = (tmp_path / "signals.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    doc = json.loads(lines[0])
    assert doc["type"] == "signal"
    assert doc["ticker"] == "NVDA"


def test_state_store_thesis_local_fallback(tmp_path, monkeypatch):
    from gravity_trade.thesis import generate_offline_thesis

    monkeypatch.setattr(state_store, "_THESES_LOCAL", tmp_path / "theses.jsonl")
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)

    bundle = compute_bundle("SPY", load_sample_data("SPY"))
    thesis = generate_offline_thesis(bundle)
    assert state_store.save_thesis(thesis) == "local"

    doc = json.loads((tmp_path / "theses.jsonl").read_text().strip())
    assert doc["type"] == "thesis"
    assert doc["ticker"] == "SPY"


def test_telemetry_logging_fallback(caplog, monkeypatch):
    import logging

    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    caplog.set_level(logging.INFO)

    bundle = compute_bundle("SPY", load_sample_data("SPY"))
    telemetry.track_scan(bundle)  # must not raise
    assert "scan ticker=SPY" in caplog.text

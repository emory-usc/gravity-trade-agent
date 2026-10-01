"""Signal/thesis persistence: Azure Cosmos DB, with a dev-only local fallback.

In production each computed ``SignalBundle`` and ``TradeThesis`` is upserted
into Cosmos DB (partitioned by ticker) for replay and eval. The Cosmos client
is constructed once and cached.

Failure semantics: when Cosmos is *configured* (``COSMOS_ENDPOINT`` set), a
failed write is logged loudly and reported as ``"error"`` — it never silently
falls back to local disk, because in a container that disk is ephemeral and the
write would be lost. The local JSONL fallback runs only when Cosmos is *not*
configured, i.e. in development.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from gravity_trade.models import SignalBundle, TradeThesis

log = logging.getLogger("gravity_trade")

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_SIGNALS_LOCAL = _DATA_DIR / "signals.jsonl"
_THESES_LOCAL = _DATA_DIR / "theses.jsonl"

_COSMOS_ENDPOINT_ENV = "COSMOS_ENDPOINT"

_container = None
_container_resolved = False


def _cosmos_container():
    """Return a cached Cosmos container client, or None if unavailable."""
    global _container, _container_resolved
    if _container_resolved:
        return _container
    _container_resolved = True

    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError:
        _container = None
        return None

    endpoint = os.getenv(_COSMOS_ENDPOINT_ENV)
    if not endpoint:
        _container = None
        return None

    database = os.getenv("COSMOS_DB", "gravitytrade")
    container_name = os.getenv("COSMOS_CONTAINER", "signals")
    try:
        client = CosmosClient(endpoint, credential=DefaultAzureCredential())
        _container = client.get_database_client(database).get_container_client(container_name)
    except Exception:
        log.exception("Failed to construct Cosmos client")
        _container = None
    return _container


def _to_doc(record_type: str, model: Any) -> dict[str, Any]:
    doc = model.model_dump(mode="json")
    doc["id"] = f"{record_type}:{model.ticker}:{doc.get('as_of', '') or 'latest'}"
    doc["type"] = record_type
    return doc


def _append_local(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(doc) + "\n")


def _persist(record_type: str, doc: dict[str, Any], local_path: Path) -> str:
    container = _cosmos_container()
    if container is not None:
        try:
            container.upsert_item(doc)
            return "cosmos"
        except Exception:
            log.exception("Failed to persist %s to Cosmos; not falling back to local in prod", record_type)
            return "error"

    # Cosmos is not configured — development fallback only.
    _append_local(local_path, doc)
    log.debug("Persisted %s locally (Cosmos not configured)", record_type)
    return "local"


def save_signal(bundle: SignalBundle) -> str:
    """Persist a signal bundle. Returns 'cosmos', 'local', or 'error'."""
    return _persist("signal", _to_doc("signal", bundle), _SIGNALS_LOCAL)


def save_thesis(thesis: TradeThesis) -> str:
    """Persist a trade thesis. Returns 'cosmos', 'local', or 'error'."""
    return _persist("thesis", _to_doc("thesis", thesis), _THESES_LOCAL)


def check_health() -> tuple[bool, str]:
    """Readiness signal for the Cosmos dependency."""
    if not os.getenv(_COSMOS_ENDPOINT_ENV):
        return (True, "not_configured")
    return (True, "ok") if _cosmos_container() is not None else (False, "unavailable")

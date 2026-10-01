"""Signal/thesis persistence: Azure Cosmos DB, with local JSONL fallback.

In production each computed ``SignalBundle`` and ``TradeThesis`` is upserted
into Cosmos DB so the framework's history is queryable and replayable (the
basis for the eval harness against a live record). When Cosmos is not
configured, results append to local JSONL files so the same code path works in
development.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gravity_trade.models import SignalBundle, TradeThesis

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_SIGNALS_LOCAL = _DATA_DIR / "signals.jsonl"
_THESES_LOCAL = _DATA_DIR / "theses.jsonl"


def _cosmos_container():
    """Return a Cosmos container client, or None if Cosmos is unavailable."""
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError:
        return None

    endpoint = os.getenv("COSMOS_ENDPOINT")
    if not endpoint:
        return None

    database = os.getenv("COSMOS_DB", "gravitytrade")
    container = os.getenv("COSMOS_CONTAINER", "signals")
    try:
        client = CosmosClient(endpoint, credential=DefaultAzureCredential())
        return client.get_database_client(database).get_container_client(container)
    except Exception:
        return None


def _to_doc(record_type: str, model: Any) -> dict[str, Any]:
    doc = model.model_dump(mode="json")
    doc["id"] = f"{record_type}:{model.ticker}:{doc.get('as_of', '') or 'latest'}"
    doc["type"] = record_type
    return doc


def _append_local(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(doc) + "\n")


def save_signal(bundle: SignalBundle) -> str:
    """Persist a signal bundle. Returns the sink used: 'cosmos' or 'local'."""
    doc = _to_doc("signal", bundle)
    container = _cosmos_container()
    if container is not None:
        try:
            container.upsert_item(doc)
            return "cosmos"
        except Exception:
            pass
    _append_local(_SIGNALS_LOCAL, doc)
    return "local"


def save_thesis(thesis: TradeThesis) -> str:
    """Persist a trade thesis. Returns the sink used: 'cosmos' or 'local'."""
    doc = _to_doc("thesis", thesis)
    container = _cosmos_container()
    if container is not None:
        try:
            container.upsert_item(doc)
            return "cosmos"
        except Exception:
            pass
    _append_local(_THESES_LOCAL, doc)
    return "local"

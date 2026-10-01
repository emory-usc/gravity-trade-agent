"""Telemetry: OpenTelemetry -> Azure Monitor (App Insights), logging fallback.

When ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set, scan outcomes are
exported as metrics to Application Insights (visible in the Azure Managed
Grafana dashboards). Otherwise structured log records are emitted through the
stdlib logger, so the same call sites work in development.
"""

from __future__ import annotations

import logging
import os

from gravity_trade.models import SignalBundle

log = logging.getLogger("gravity_trade")

_meter = None


def _get_meter():
    """Return an OpenTelemetry meter bound to App Insights, or None."""
    global _meter
    if _meter is not None:
        return _meter

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        return None

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=connection_string)
        from opentelemetry import metrics

        _meter = metrics.get_meter("gravity_trade")
        return _meter
    except Exception:
        return None


def track_scan(bundle: SignalBundle) -> None:
    """Record a scan outcome: a conviction histogram and a direction counter."""
    meter = _get_meter()
    if meter is not None:
        try:
            meter.create_histogram("gravity.conviction").record(
                bundle.conviction, {"ticker": bundle.ticker}
            )
            meter.create_counter("gravity.direction").add(
                1, {"ticker": bundle.ticker, "direction": bundle.direction.value}
            )
        except Exception:
            pass

    log.info(
        "scan ticker=%s direction=%s conviction=%d high_conviction=%s",
        bundle.ticker,
        bundle.direction.value,
        bundle.conviction,
        bundle.high_conviction,
    )

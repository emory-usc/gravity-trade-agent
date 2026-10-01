"""Telemetry: OpenTelemetry -> Azure Monitor (App Insights), logging fallback.

When ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set, scan outcomes and errors
are exported as metrics to Application Insights (visible in Azure Managed
Grafana). Otherwise structured log records are emitted through the stdlib
logger, so the same call sites work in development.

The OpenTelemetry meter is constructed once and cached.
"""

from __future__ import annotations

import logging
import os

from gravity_trade.models import SignalBundle

log = logging.getLogger("gravity_trade")

_meter = None
_meter_resolved = False


def _get_meter():
    """Return a cached OpenTelemetry meter bound to App Insights, or None."""
    global _meter, _meter_resolved
    if _meter_resolved:
        return _meter
    _meter_resolved = True

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        _meter = None
        return None

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=connection_string)
        from opentelemetry import metrics

        _meter = metrics.get_meter("gravity_trade")
    except Exception:
        log.exception("Failed to configure Azure Monitor telemetry")
        _meter = None
    return _meter


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
            log.exception("Failed to emit scan metrics")

    log.info(
        "scan ticker=%s direction=%s conviction=%d high_conviction=%s",
        bundle.ticker,
        bundle.direction.value,
        bundle.conviction,
        bundle.high_conviction,
    )


def track_error(event: str, **attrs: object) -> None:
    """Record an error event (log + counter metric) so alerts can fire on it."""
    log.error("error event=%s %s", event, attrs)
    meter = _get_meter()
    if meter is not None:
        try:
            meter.create_counter("gravity.errors").add(1, {"event": event})
        except Exception:
            log.exception("Failed to emit error metric")

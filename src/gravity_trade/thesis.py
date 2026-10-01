"""Deterministic (offline) thesis generation.

Produces a TradeThesis from a SignalBundle without any LLM. This is what
``gravity analyze`` uses, and it is the fallback node in the LangGraph agent
when no API key is configured.
"""

from __future__ import annotations

from gravity_trade.models import Direction, SignalBundle, TradeThesis


def _summary(bundle: SignalBundle) -> str:
    d = bundle.direction.value
    return (
        f"{bundle.ticker}: {d.upper()} — {bundle.bullish_count} bull / "
        f"{bundle.bearish_count} bear across six layers (conviction {bundle.conviction}/6)."
    )


def _thesis(bundle: SignalBundle) -> str:
    parts = []
    for s in bundle.layers:
        arrow = {"bull": "+", "bear": "-", "neutral": "o"}[s.direction.value]
        parts.append(f"{arrow} {s.layer}: {s.rationale}")
    head = (
        f"{bundle.ticker} reads {bundle.direction.value.upper()} with {bundle.conviction}/6 conviction. "
        f"Aligned layers: "
    )
    aligned = [s.layer for s in bundle.layers if s.direction == bundle.direction]
    head += ", ".join(aligned) if aligned else "none (net neutral)"
    return head + ".\n" + "\n".join(parts)


def _risk_notes(bundle: SignalBundle) -> str:
    contrary = [s.layer for s in bundle.layers if s.direction not in (bundle.direction, Direction.NEUTRAL)]
    notes = [
        "Framework is directional (Mon entry, Fri 2pm CT exit); it is not a guarantee.",
        "Convergence of opposing signals (esp. max pain vs GEX) is the primary invalidation.",
    ]
    if contrary:
        notes.append(f"Contrary layers to watch: {', '.join(contrary)}.")
    if bundle.conviction < 4:
        notes.append("Below the 4/6 high-conviction bar — size down or pass.")
    return " ".join(notes)


def generate_offline_thesis(bundle: SignalBundle) -> TradeThesis:
    d = bundle.direction
    direction_word = {"bull": "bullish", "bear": "bearish", "neutral": "neutral"}[d.value]
    entry = (
        "Enter Monday on a retest of the signal (limit near max-pain / VWAP)."
        if d != Direction.NEUTRAL
        else "No directional entry; stand aside unless conviction reaches 4/6."
    )
    exit_ = (
        "Exit Friday at 2pm CT per the weekly cadence; tighten on a 2-layer flip."
        if d != Direction.NEUTRAL
        else "No position; reassess next Monday."
    )
    return TradeThesis(
        ticker=bundle.ticker,
        direction=d,
        conviction=bundle.conviction,
        high_conviction=bundle.high_conviction,
        signal_summary=_summary(bundle),
        thesis=_thesis(bundle),
        entry_plan=f"{entry} Directional bias: {direction_word}.",
        exit_plan=exit_,
        risk_notes=_risk_notes(bundle),
        generated_by="offline",
    )

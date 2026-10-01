"""Signal layer interface and shared helpers."""

from __future__ import annotations

from typing import Protocol

from gravity_trade.models import Direction, LayerSignal


class SignalLayer(Protocol):
    """A single Gravity Trade layer: takes a data snapshot, returns a signal."""

    name: str

    def compute(self, data: dict) -> LayerSignal: ...


def _clamp_conf(v: float) -> float:
    return max(0.0, min(1.0, v))


def make_signal(
    layer: str,
    direction: Direction,
    confidence: float,
    evidence: dict,
    rationale: str,
) -> LayerSignal:
    return LayerSignal(
        layer=layer,
        direction=direction,
        score={Direction.BULL: 1, Direction.NEUTRAL: 0, Direction.BEAR: -1}[direction],
        confidence=round(_clamp_conf(confidence), 3),
        evidence=evidence,
        rationale=rationale,
    )

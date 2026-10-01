"""Pydantic domain models.

These are the structured types that flow through both the offline pipeline and
the LangChain/LangGraph agent. They double as the JSON contract for structured
LLM output via ``model.with_structured_output(TradeThesis)``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Direction(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"


class LayerSignal(BaseModel):
    """One of the six Gravity Trade layers, scored for a single ticker."""

    layer: str = Field(description="Layer name: max_pain, beta, gex, dark_pool, sector, term_structure")
    direction: Direction = Field(description="Directional read for this layer")
    score: int = Field(description="+1 bullish, 0 neutral, -1 bearish", ge=-1, le=1)
    confidence: float = Field(description="Confidence 0.0-1.0 for this layer's read", ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict, description="Supporting numbers")
    rationale: str = Field(description="One-sentence explanation")


class SignalBundle(BaseModel):
    """Aggregated six-layer read for a ticker at a point in time."""

    ticker: str
    as_of: datetime = Field(description="Timestamp the underlying data is from")
    layers: list[LayerSignal] = Field(description="The six layer signals")
    bullish_count: int = Field(ge=0, le=6)
    bearish_count: int = Field(ge=0, le=6)
    conviction: int = Field(description="0-6: max(bullish, bearish) aligned signals", ge=0, le=6)
    direction: Direction = Field(description="Net directional bias")
    high_conviction: bool = Field(description="True when conviction >= threshold (default 4)")


class TradeThesis(BaseModel):
    """Final output: a directional trade thesis with cited evidence."""

    ticker: str
    direction: Direction
    conviction: int
    high_conviction: bool
    signal_summary: str = Field(description="One-line summary of the six layers")
    thesis: str = Field(description="Narrative thesis, citing layer evidence")
    entry_plan: str = Field(description="Entry plan (Monday entries by default)")
    exit_plan: str = Field(description="Exit plan (Friday 2pm CT by default)")
    risk_notes: str = Field(description="What invalidates the thesis and key risks")
    generated_by: str = Field(description="'offline' (deterministic) or 'llm' (agent)")

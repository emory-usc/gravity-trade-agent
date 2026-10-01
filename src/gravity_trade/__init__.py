"""Gravity Trade Agent — a LangChain/LangGraph implementation of the
Gravity Trade six-layer directional framework.

Layers: max pain, beta, GEX (gamma exposure), dark pool flow, sector,
and term structure. Six signals are aggregated into a 0-6 conviction score
and a directional (bull/bear/neutral) trade thesis.
"""

__version__ = "0.1.0"

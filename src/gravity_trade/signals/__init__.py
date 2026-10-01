"""Gravity Trade signal layers (six total)."""

from gravity_trade.signals.max_pain import MaxPainLayer
from gravity_trade.signals.beta import BetaLayer
from gravity_trade.signals.gex import GexLayer
from gravity_trade.signals.dark_pool import DarkPoolLayer
from gravity_trade.signals.sector import SectorLayer
from gravity_trade.signals.term_structure import TermStructureLayer

ALL_LAYERS: list = [
    MaxPainLayer(),
    BetaLayer(),
    GexLayer(),
    DarkPoolLayer(),
    SectorLayer(),
    TermStructureLayer(),
]

__all__ = [
    "ALL_LAYERS",
    "MaxPainLayer",
    "BetaLayer",
    "GexLayer",
    "DarkPoolLayer",
    "SectorLayer",
    "TermStructureLayer",
]

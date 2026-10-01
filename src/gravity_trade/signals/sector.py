"""Layer 5 — Sector.

Relative strength within the sector: a name leading a strong sector is the
cleanest bullish read; a name lagging a weak sector is the cleanest bearish
read. Confidence scales with the magnitude of the relative-strength gap.
"""

from __future__ import annotations

from typing import Any

from gravity_trade.models import Direction
from gravity_trade.signals.base import make_signal


class SectorLayer:
    name = "sector"

    def compute(self, data: dict[str, Any]) -> Any:
        sector = data.get("sector", {})
        ticker_ret = float(data.get("ticker_return_1d", 0.0))
        sector_ret = float(sector.get("return_1d", 0.0))
        rel = ticker_ret - sector_ret  # relative strength gap

        if sector_ret > 0 and rel > 0:
            direction = Direction.BULL  # leading a strong sector
        elif sector_ret < 0 and rel < 0:
            direction = Direction.BEAR  # lagging a weak sector
        elif sector_ret > 0 and rel < 0:
            direction = Direction.NEUTRAL  # lagging a strong sector
        elif sector_ret < 0 and rel > 0:
            direction = Direction.NEUTRAL  # strong in a weak sector
        else:
            direction = Direction.NEUTRAL

        confidence = min(1.0, abs(rel) / 0.01)
        rationale = (
            f"{sector.get('name', 'sector')} {sector_ret * 100:+.2f}%; "
            f"ticker {ticker_ret * 100:+.2f}% (rel strength {rel * 100:+.2f}%)."
        )
        return make_signal(
            self.name,
            direction,
            confidence,
            {
                "sector": sector.get("name"),
                "sector_return_1d": sector_ret,
                "ticker_return_1d": ticker_ret,
                "relative_strength": round(rel, 4),
            },
            rationale,
        )

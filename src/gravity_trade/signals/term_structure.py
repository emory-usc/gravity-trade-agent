"""Layer 6 — Term Structure.

Volatility term structure and skew reveal positioning and event risk. A steep
put skew (put IV >> call IV) signals bearish hedging; a call skew signals
bullish speculation. Backwardation (front IV > back IV) flags event risk and
raises the confidence on the skew read.
"""

from __future__ import annotations

from typing import Any

from gravity_trade.models import Direction
from gravity_trade.signals.base import make_signal


class TermStructureLayer:
    name = "term_structure"

    def compute(self, data: dict[str, Any]) -> Any:
        ts = data.get("term_structure", {})
        put_iv = float(ts.get("put_iv", ts.get("front_iv", 0.0)))
        call_iv = float(ts.get("call_iv", ts.get("front_iv", 0.0)))
        front_iv = float(ts.get("front_iv", 0.0))
        back_iv = float(ts.get("back_iv", front_iv))

        skew = put_iv - call_iv  # >0 = put skew (bearish hedge), <0 = call skew (bullish)
        backwardation = front_iv > back_iv

        if abs(skew) < 0.01:
            direction = Direction.NEUTRAL
        elif skew > 0:
            direction = Direction.BEAR
        else:
            direction = Direction.BULL

        confidence = min(1.0, abs(skew) / 0.05)
        if backwardation and direction != Direction.NEUTRAL:
            confidence = min(1.0, confidence + 0.2)  # event risk sharpens the read

        slope = "backwardated" if backwardation else "contango"
        rationale = (
            f"{'Put' if skew > 0 else 'Call'} skew {skew * 100:+.1f} pts; "
            f"term {slope} (front {front_iv:.0%} vs back {back_iv:.0%})."
        )
        return make_signal(
            self.name,
            direction,
            confidence,
            {
                "put_iv": put_iv,
                "call_iv": call_iv,
                "skew": round(skew, 4),
                "front_iv": front_iv,
                "back_iv": back_iv,
                "backwardation": backwardation,
            },
            rationale,
        )

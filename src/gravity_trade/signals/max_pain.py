"""Layer 1 — Max Pain.

Max pain is the strike where option buyers lose the most aggregate value at
expiry. Market makers hedge to pin price toward it, so price above max pain
faces a downward magnet (bearish), price below faces an upward one (bullish).
"""

from __future__ import annotations

from typing import Any

from gravity_trade.models import Direction
from gravity_trade.signals.base import make_signal


def _compute_max_pain(strikes: list[dict]) -> float | None:
    """Return the strike minimizing total ITM option value (the max-pain pin)."""
    if not strikes:
        return None
    candidates = [s["strike"] for s in strikes]
    best_strike = candidates[0]
    best_pain = float("inf")
    for pin in candidates:
        pain = 0.0
        for s in strikes:
            k = s["strike"]
            # Calls ITM when pin > k; puts ITM when pin < k.
            pain += s.get("call_oi", 0) * max(pin - k, 0.0)
            pain += s.get("put_oi", 0) * max(k - pin, 0.0)
        if pain < best_pain:
            best_pain = pain
            best_strike = pin
    return best_strike


class MaxPainLayer:
    name = "max_pain"

    def compute(self, data: dict[str, Any]) -> Any:
        price = float(data["price"])
        near = data["options"]["near_expiry"]
        chain = next(e for e in data["options"]["expiries"] if e["expiry"] == near)
        max_pain = _compute_max_pain(chain["strikes"])

        if max_pain is None:
            return make_signal(self.name, Direction.NEUTRAL, 0.0, {}, "No options chain available.")

        near_pct = abs(price - max_pain) / max_pain
        total_oi = sum(s.get("call_oi", 0) + s.get("put_oi", 0) for s in chain["strikes"])

        if near_pct < 0.005:  # within 0.5% of the pin
            direction = Direction.NEUTRAL
        elif price > max_pain:
            direction = Direction.BEAR
        else:
            direction = Direction.BULL

        confidence = min(1.0, near_pct / 0.03)  # 3% away -> full confidence
        rationale = (
            f"Max pain {max_pain:.2f} vs price {price:.2f} "
            f"({near_pct * 100:+.2f}%); {'pinned/neutral' if direction == Direction.NEUTRAL else 'magnet ' + direction.value}."
        )
        return make_signal(
            self.name,
            direction,
            confidence,
            {"max_pain": round(max_pain, 2), "price": price, "distance_pct": round(near_pct * 100, 3), "total_oi": total_oi},
            rationale,
        )

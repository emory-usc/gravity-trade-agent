"""Layer 3 — Gamma Exposure (GEX).

Net dealer gamma governs realized volatility. Positive GEX (dealers long
gamma) suppresses moves and pulls price back toward the flip level
(mean-reverting). Negative GEX (dealers short gamma) amplifies moves, so the
recent trend tends to continue.
"""

from __future__ import annotations

from typing import Any

from gravity_trade.models import Direction
from gravity_trade.signals.base import make_signal

GEX_SCALE = 1_000_000.0  # notional scale for confidence normalization


class GexLayer:
    name = "gex"

    def compute(self, data: dict[str, Any]) -> Any:
        gex = data.get("gex", {})
        net_gamma = float(gex.get("net_gamma", 0.0))
        flip_level = gex.get("flip_level")
        price = float(data["price"])
        momentum = float(data.get("momentum_1d", 0.0))

        confidence = min(1.0, abs(net_gamma) / GEX_SCALE)

        if net_gamma > 0 and flip_level is not None:
            # Long gamma: fade extended price back toward flip.
            if price > flip_level:
                direction = Direction.BEAR
            elif price < flip_level:
                direction = Direction.BULL
            else:
                direction = Direction.NEUTRAL
            rationale = (
                f"Positive GEX (${net_gamma / 1e6:.1f}M) pins price toward flip {flip_level}; "
                f"price {price:.2f} is {'above' if price > flip_level else 'below' or 'at'} it."
            )
        elif net_gamma < 0:
            direction = Direction.BULL if momentum > 0 else Direction.BEAR if momentum < 0 else Direction.NEUTRAL
            rationale = (
                f"Negative GEX (${net_gamma / 1e6:.1f}M) amplifies momentum "
                f"({momentum * 100:+.2f}% 1d)."
            )
        else:
            direction = Direction.NEUTRAL
            rationale = "Flat GEX; no directional bias from gamma."

        return make_signal(
            self.name,
            direction,
            confidence,
            {
                "net_gamma": net_gamma,
                "net_gamma_m": round(net_gamma / 1e6, 2),
                "flip_level": flip_level,
                "price": price,
                "momentum_1d": momentum,
            },
            rationale,
        )

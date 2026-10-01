"""Layer 2 — Beta.

Beta measures sensitivity to the broad market. High-beta names amplify the
prevailing tape: in an up market they lever upside (bullish), in a down market
they lever downside (bearish). Low-beta names are treated as neutral here.
"""

from __future__ import annotations

from typing import Any

from gravity_trade.models import Direction
from gravity_trade.signals.base import make_signal

HIGH_BETA = 1.2
LOW_BETA = 0.8


class BetaLayer:
    name = "beta"

    def compute(self, data: dict[str, Any]) -> Any:
        beta = float(data["beta"])
        market_ret = float(data.get("market_return_1d", 0.0))

        if abs(beta) <= LOW_BETA:
            direction = Direction.NEUTRAL
            confidence = 0.1
            rationale = f"Beta {beta:.2f} is low; limited amplification either way."
        elif beta >= HIGH_BETA:
            direction = Direction.BULL if market_ret > 0 else Direction.BEAR if market_ret < 0 else Direction.NEUTRAL
            confidence = min(1.0, abs(market_ret) / 0.02)
            rationale = (
                f"Beta {beta:.2f} amplifies a {'positive' if market_ret >= 0 else 'negative'} tape "
                f"({market_ret * 100:+.2f}% market)."
            )
        else:
            direction = Direction.BULL if market_ret > 0 else Direction.BEAR if market_ret < 0 else Direction.NEUTRAL
            confidence = min(1.0, abs(market_ret) / 0.02) * 0.5
            rationale = f"Beta {beta:.2f}; modest directional lean with the market."

        return make_signal(
            self.name,
            direction,
            confidence,
            {"beta": beta, "market_return_1d": market_ret},
            rationale,
        )

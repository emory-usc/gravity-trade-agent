"""Layer 4 — Dark Pool Flow.

Large off-exchange prints reveal institutional accumulation/distribution.
Net buy notional is bullish, net sell notional is bearish. Confidence scales
with the imbalance relative to total flow.
"""

from __future__ import annotations

from typing import Any

from gravity_trade.models import Direction
from gravity_trade.signals.base import make_signal


class DarkPoolLayer:
    name = "dark_pool"

    def compute(self, data: dict[str, Any]) -> Any:
        prints = data.get("dark_pool", [])
        buy = sell = 0.0
        for p in prints:
            notional = float(p["size"]) * float(p["price"])
            if p.get("side", "").lower() == "buy":
                buy += notional
            else:
                sell += notional

        net = buy - sell
        total = buy + sell

        if total == 0:
            return make_signal(self.name, Direction.NEUTRAL, 0.0, {}, "No dark pool prints.")

        imbalance = net / total  # -1..1
        direction = Direction.BULL if net > 0 else Direction.BEAR if net < 0 else Direction.NEUTRAL
        confidence = min(1.0, abs(imbalance) / 0.4)

        rationale = (
            f"Net dark pool flow ${net / 1e6:+.2f}M "
            f"(imbalance {imbalance * 100:+.1f}%) across {len(prints)} prints."
        )
        return make_signal(
            self.name,
            direction,
            confidence,
            {
                "buy_notional": round(buy, 2),
                "sell_notional": round(sell, 2),
                "net_notional": round(net, 2),
                "imbalance_pct": round(imbalance * 100, 2),
                "n_prints": len(prints),
            },
            rationale,
        )

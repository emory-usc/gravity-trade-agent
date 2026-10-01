# The Gravity Trade framework

A systematic, six-layer read on whether an equity is set up for a directional
weekly move. Each layer is an independent source of evidence; the power is in
their **agreement**, not any single indicator.

## The six layers

### 1. Max pain

The strike at which option buyers (in aggregate) lose the most value at expiry.
Market makers hedge to pin price toward it, so it acts as a short-term magnet.

- **Price above max pain** → downward magnet → bearish
- **Price below max pain** → upward magnet → bullish
- **Within ~0.5%** → pinned → neutral

### 2. Beta

Sensitivity to the broad market. High-beta names amplify the prevailing tape:
they lever upside in an up market and downside in a down market. Low-beta names
add little directional signal and are treated as neutral.

### 3. Gamma exposure (GEX)

Net dealer gamma governs realized volatility:

- **Positive GEX** (dealers long gamma) → dealers buy low / sell high →
  volatility is suppressed and price reverts toward the flip level.
- **Negative GEX** (dealers short gamma) → dealers hedge with the trend →
  moves are amplified and momentum continues.

### 4. Dark-pool flow

Large off-exchange prints are a proxy for institutional activity. Net buy
notional indicates accumulation (bullish); net sell notional indicates
distribution (bearish). Confidence scales with the imbalance relative to total
flow.

### 5. Sector

Relative strength within the name's sector. The cleanest reads are the two
extremes: a name **leading a strong sector** (bullish) or **lagging a weak
sector** (bearish). A name lagging a strong sector, or leading a weak one, is
ambiguous → neutral.

### 6. Term structure

Volatility skew and term slope reveal positioning and event risk:

- **Put skew** (put IV ≫ call IV) → investors are paying up for downside
  protection → bearish
- **Call skew** (call IV ≫ put IV) → bullish speculation
- **Backwardation** (front IV > back IV) → event risk; it sharpens the skew read

## Aggregation

Each layer emits `+1` (bull), `0` (neutral), or `-1` (bear) plus a confidence.

- `bullish_count` / `bearish_count` = number of layers on each side
- `conviction` = `max(bullish_count, bearish_count)`, range 0–6
- `direction` = net bias
- **High conviction** = conviction ≥ 4 — the "4-of-6" bar, the only level the
  framework suggests acting on

The conviction tier is the framework's core edge: when four or more independent
signals agree, direction has historically been more reliable than when they
split. The eval harness (`gravity backtest`) turns that claim into a number.

## Cadence

The framework is designed around a weekly rhythm: enter on **Monday** once
signals confirm, exit on **Friday at 2pm CT**, and stand aside when conviction
drops below the bar.

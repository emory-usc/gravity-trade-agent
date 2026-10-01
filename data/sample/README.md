# Sample data schema

Real-time options, GEX, and dark-pool feeds require licensed data providers.
To keep the pipeline fully runnable and reproducible, the repo ships small
snapshot files here — one JSON per ticker. Each snapshot has everything the six
layers need.

## Schema

```json
{
  "ticker": "NVDA",
  "as_of": "2026-09-30T20:00:00Z",       // ISO-8601 UTC timestamp
  "price": 141.50,                        // last price
  "beta": 1.82,                           // vs the broad market
  "market_return_1d": 0.0072,             // broad-market 1d return (for the beta layer)
  "momentum_1d": 0.0210,                  // ticker 1d momentum (for the GEX layer)
  "ticker_return_1d": 0.0210,             // ticker 1d return (for the sector layer)
  "sector": {
    "name": "Semiconductors",
    "return_1d": 0.0148,
    "rank": 2
  },
  "options": {
    "near_expiry": "2026-10-02",
    "expiries": [
      {
        "expiry": "2026-10-02",
        "strikes": [
          { "strike": 135, "call_oi": 21000, "put_oi": 9000 }
        ]
      }
    ]
  },
  "gex": {
    "net_gamma": -1900000.0,              // signed net dealer gamma (notional)
    "flip_level": 138.0                    // price where dealer gamma flips sign
  },
  "dark_pool": [
    { "timestamp": "2026-09-30T15:10:00Z", "price": 141.10, "size": 45000, "side": "buy" }
  ],
  "term_structure": {
    "front_iv": 0.42,
    "back_iv": 0.40,
    "put_iv": 0.41,
    "call_iv": 0.44
  }
}
```

## Adding a ticker

Drop a new `<TICKER>.json` here following the schema and `gravity analyze <TICKER>`
will pick it up. To point the pipeline at a live provider instead, swap the
`load_sample_data` call in `src/gravity_trade/data.py` for your data feed.

> These files are **illustrative synthetic snapshots** for demonstrating the
> pipeline. They are not real market data.

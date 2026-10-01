# Eval data

`paper_trades.jsonl` is the input to `gravity backtest`. One JSON object per
line:

```json
{"ticker":"NVDA","direction":"bull","conviction":5,"entry_price":118.0,"exit_price":124.5,"entry_date":"2026-07-06","exit_date":"2026-07-10"}
```

A trade "wins" when the exit moves in the signaled direction.

> **The trades in this file are illustrative synthetic examples** used to
> demonstrate the eval harness and the conviction-tiering effect (higher
> conviction -> higher hit rate). Replace this file with your own paper-trade
> log to evaluate a real strategy.

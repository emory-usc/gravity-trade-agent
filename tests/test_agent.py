from gravity_trade.agent import run_agent
from gravity_trade.evals import run_backtest
from gravity_trade.models import TradeThesis


def test_agent_runs_offline_and_returns_thesis():
    thesis = run_agent("NVDA")
    assert isinstance(thesis, TradeThesis)
    assert thesis.ticker == "NVDA"
    assert thesis.generated_by in {"offline", "llm"}
    assert thesis.direction.value in {"bull", "bear", "neutral"}


def test_backtest_reports_buckets():
    report = run_backtest()
    assert report["total"] > 0
    assert set(report["buckets"]) == {"conviction >= 4", "conviction < 4"}
    # High-conviction tier should outperform the low-conviction tier in sample data.
    high = report["buckets"]["conviction >= 4"]
    low = report["buckets"]["conviction < 4"]
    assert high["hit_rate"] > low["hit_rate"]

from gravity_trade.data import load_sample_data
from gravity_trade.scoring import compute_bundle


def test_nvda_is_high_conviction_bull():
    data = load_sample_data("NVDA")
    bundle = compute_bundle("NVDA", data, threshold=4)
    assert len(bundle.layers) == 6
    assert bundle.direction.value == "bull"
    assert bundle.high_conviction is True
    assert bundle.conviction == max(bundle.bullish_count, bundle.bearish_count)


def test_spy_is_low_conviction():
    data = load_sample_data("SPY")
    bundle = compute_bundle("SPY", data, threshold=4)
    assert bundle.high_conviction is False
    assert bundle.conviction < 4


def test_counts_are_consistent():
    data = load_sample_data("NVDA")
    bundle = compute_bundle("NVDA", data)
    assert bundle.bullish_count + bundle.bearish_count <= 6
    assert bundle.bullish_count == sum(1 for s in bundle.layers if s.direction.value == "bull")
    assert bundle.bearish_count == sum(1 for s in bundle.layers if s.direction.value == "bear")

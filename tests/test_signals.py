from gravity_trade.data import load_sample_data
from gravity_trade.models import Direction, LayerSignal
from gravity_trade.signals import ALL_LAYERS


def test_six_layers_registered():
    names = [layer.name for layer in ALL_LAYERS]
    assert len(names) == 6
    assert len(set(names)) == 6
    assert set(names) == {
        "max_pain", "beta", "gex", "dark_pool", "sector", "term_structure",
    }


def test_every_layer_produces_a_valid_signal():
    data = load_sample_data("NVDA")
    for layer in ALL_LAYERS:
        sig = layer.compute(data)
        assert isinstance(sig, LayerSignal)
        assert sig.layer == layer.name
        assert -1 <= sig.score <= 1
        assert 0.0 <= sig.confidence <= 1.0
        assert sig.direction in Direction
        assert sig.rationale

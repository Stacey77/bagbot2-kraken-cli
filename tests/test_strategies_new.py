import pytest

from bagbot.strategy import (
    Candle,
    MeanReversionStrategy,
    MomentumStrategy,
    Signal,
    SmaCrossStrategy,
    create_strategy,
)


def candle(close, t=0):
    return Candle(time=t, open=close, high=close, low=close, close=close, volume=1.0)


def run_all(strat, closes):
    candles = [candle(c, t=i) for i, c in enumerate(closes)]
    return [strat.on_candle(i, c, candles[: i + 1]) for i, c in enumerate(candles)]


def test_registry_builds_all_strategies():
    assert isinstance(create_strategy("sma"), SmaCrossStrategy)
    assert isinstance(create_strategy("meanrev"), MeanReversionStrategy)
    assert isinstance(create_strategy("momentum"), MomentumStrategy)
    with pytest.raises(ValueError, match="unknown strategy"):
        create_strategy("nope")


def test_meanrev_buys_on_deep_dip():
    closes = [100.0] * 19 + [80.0]  # crash below 2 std
    signals = run_all(MeanReversionStrategy(lookback=20, num_std=2.0), closes)
    assert signals[-1] is Signal.BUY


def test_meanrev_sells_on_spike():
    closes = [100.0] * 19 + [120.0]
    signals = run_all(MeanReversionStrategy(lookback=20, num_std=2.0), closes)
    assert signals[-1] is Signal.SELL


def test_meanrev_holds_in_quiet_market():
    closes = [100.0 + (0.1 if i % 2 else -0.1) for i in range(40)]
    signals = run_all(MeanReversionStrategy(lookback=20, num_std=2.0), closes)
    assert all(s is Signal.HOLD for s in signals)


def test_meanrev_validates_params():
    with pytest.raises(ValueError):
        MeanReversionStrategy(lookback=1)
    with pytest.raises(ValueError):
        MeanReversionStrategy(num_std=0)


def test_momentum_buys_strong_rally():
    closes = [100.0] * 10 + [110.0]  # +10% over 10 candles
    signals = run_all(MomentumStrategy(lookback=10, threshold=0.05), closes)
    assert signals[-1] is Signal.BUY


def test_momentum_sells_strong_drop():
    closes = [100.0] * 10 + [90.0]
    signals = run_all(MomentumStrategy(lookback=10, threshold=0.05), closes)
    assert signals[-1] is Signal.SELL


def test_momentum_holds_small_moves():
    closes = [100.0] * 10 + [101.0]  # +1% < 5% threshold
    signals = run_all(MomentumStrategy(lookback=10, threshold=0.05), closes)
    assert signals[-1] is Signal.HOLD


def test_momentum_validates_params():
    with pytest.raises(ValueError):
        MomentumStrategy(lookback=0)
    with pytest.raises(ValueError):
        MomentumStrategy(threshold=-0.1)

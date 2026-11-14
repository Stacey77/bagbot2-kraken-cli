import pytest

from bagbot.strategy import Candle, Signal, SmaCrossStrategy, run_backtest
from bagbot.strategy.sma import sma


def candle(close, t=0):
    return Candle(time=t, open=close, high=close, low=close, close=close, volume=1.0)


def test_sma_math():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert sma([1, 2, 3], 4) is None
    with pytest.raises(ValueError):
        sma([1], 0)


def test_sma_cross_requires_fast_lt_slow():
    with pytest.raises(ValueError):
        SmaCrossStrategy(fast=30, slow=10)


def test_sma_cross_signals_on_uptrend():
    # Decline then sharp rally: fast SMA crosses up through slow SMA.
    closes = [100 - i for i in range(20)] + [90 + i * 10 for i in range(20)]
    candles = [candle(c, t=i) for i, c in enumerate(closes)]
    strat = SmaCrossStrategy(fast=3, slow=8)
    signals = [strat.on_candle(i, c, candles[: i + 1]) for i, c in enumerate(candles)]
    assert Signal.BUY in signals


def test_sma_cross_holds_without_crossover():
    candles = [candle(100, t=i) for i in range(50)]  # flat market
    strat = SmaCrossStrategy(fast=3, slow=8)
    assert all(
        strat.on_candle(i, c, candles[: i + 1]) is Signal.HOLD
        for i, c in enumerate(candles)
    )


def test_backtest_buy_and_sell_round_trip():
    class Scripted:
        name = "scripted"

        def __init__(self, script):
            self.script = script

        def on_candle(self, index, candle, history):
            return self.script[index]

    candles = [candle(100, t=0), candle(110, t=1), candle(120, t=2)]
    result = run_backtest(
        Scripted([Signal.BUY, Signal.HOLD, Signal.SELL]), candles, initial_cash=1000.0
    )
    # Buy 10 units @100, sell @120 -> 1200, +20%
    assert result.final_equity == pytest.approx(1200.0)
    assert result.return_pct == pytest.approx(20.0)
    assert result.wins == 1 and result.losses == 0
    assert result.win_rate == 1.0
    assert [t.side for t in result.trades] == ["buy", "sell"]


def test_backtest_open_position_marked_to_market():
    class AlwaysBuy:
        name = "buy"

        def on_candle(self, index, candle, history):
            return Signal.BUY if index == 0 else Signal.HOLD

    candles = [candle(100, t=0), candle(50, t=1)]
    result = run_backtest(AlwaysBuy(), candles, initial_cash=1000.0)
    assert result.final_equity == pytest.approx(500.0)  # 10 units worth 50 each
    assert result.return_pct == pytest.approx(-50.0)


def test_backtest_rejects_nonpositive_cash():
    with pytest.raises(ValueError):
        run_backtest(SmaCrossStrategy(), [candle(1)], initial_cash=0)


def test_candle_from_kraken_row():
    c = Candle.from_kraken([1700000000, "100.1", "101.0", "99.5", "100.8", "100.5", "12.3", 42])
    assert c.time == 1700000000
    assert c.close == 100.8
    assert c.volume == 12.3

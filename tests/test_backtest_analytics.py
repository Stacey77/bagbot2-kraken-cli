import pytest

from bagbot.strategy import Candle, Signal, run_backtest
from bagbot.strategy.backtest import max_drawdown_pct


def candle(close, t=0):
    return Candle(time=t, open=close, high=close, low=close, close=close, volume=1.0)


def test_max_drawdown_pct_pure():
    assert max_drawdown_pct([100, 120, 90, 130]) == pytest.approx(-25.0)  # 120 -> 90
    assert max_drawdown_pct([100, 110, 120]) == 0.0
    assert max_drawdown_pct([]) == 0.0


def test_backtest_records_equity_curve_and_drawdown():
    class Scripted:
        name = "scripted"

        def __init__(self, script):
            self.script = script

        def on_candle(self, index, candle, history):
            return self.script[index]

    # Buy @100, price halves to 50, then sell @150
    candles = [candle(100, t=0), candle(50, t=1), candle(150, t=2)]
    result = run_backtest(
        Scripted([Signal.BUY, Signal.HOLD, Signal.SELL]), candles, initial_cash=1000.0
    )
    assert result.equity_curve == [pytest.approx(1000.0), pytest.approx(500.0), pytest.approx(1500.0)]
    assert result.max_drawdown_pct == pytest.approx(-50.0)
    assert result.final_equity == pytest.approx(1500.0)

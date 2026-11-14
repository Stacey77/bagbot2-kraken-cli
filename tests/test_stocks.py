import pandas as pd

from bagbot.stocks import YahooFeed, extract_ticker_frame, frame_to_candles


def _frame(closes, start="2024-01-02"):
    idx = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame({
        "Open": closes, "High": [c + 1 for c in closes],
        "Low": [c - 1 for c in closes], "Close": closes,
        "Volume": [1000.0] * len(closes),
    }, index=idx)


def test_frame_to_candles_converts_ohlcv():
    candles = frame_to_candles(_frame([100.0, 101.5]))
    assert len(candles) == 2
    assert candles[0].close == 100.0
    assert candles[1].high == 102.5
    assert candles[0].volume == 1000.0
    assert candles[0].time > 0


def test_frame_to_candles_skips_nan_rows():
    df = _frame([100.0, 101.0, 102.0])
    df.iloc[1] = float("nan")
    candles = frame_to_candles(df)
    assert len(candles) == 2
    assert [c.close for c in candles] == [100.0, 102.0]


def test_extract_ticker_frame_grouped():
    data = pd.concat({"MSFT": _frame([10.0]), "AAPL": _frame([20.0])}, axis=1)
    assert extract_ticker_frame(data, "MSFT").iloc[0]["Close"] == 10.0
    assert extract_ticker_frame(data, "AAPL").iloc[0]["Close"] == 20.0


def test_extract_ticker_frame_single_ticker_fallback():
    df = _frame([42.0])
    assert extract_ticker_frame(df, "MSFT").iloc[0]["Close"] == 42.0


def test_yahoo_feed_with_stubbed_downloader():
    data = pd.concat({"MSFT": _frame([10.0, 11.0]), "AAPL": _frame([20.0, 21.0])}, axis=1)
    calls = {}

    def fake_download(symbols, start, end, group_by, progress):
        calls["args"] = (symbols, start, end, group_by)
        return data

    feed = YahooFeed(downloader=fake_download)
    many = feed.ohlc_many(["MSFT", "AAPL"], "2024-01-01", "2025-01-01")
    assert calls["args"] == (["MSFT", "AAPL"], "2024-01-01", "2025-01-01", "ticker")
    assert [c.close for c in many["MSFT"]] == [10.0, 11.0]
    assert [c.close for c in many["AAPL"]] == [20.0, 21.0]
    assert [c.close for c in feed.ohlc("MSFT", "2024-01-01", "2025-01-01")] == [10.0, 11.0]

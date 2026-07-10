from walk_forward_backtest import HistoricalDataManager


def test_historical_data_manager_never_returns_future_candle():
    base = {
        "timestamps": [1000, 2000, 3000], "close_timestamps": [1999, 2999, 3999],
        "opens": [1,2,3], "highs": [2,3,4], "lows": [.5,1.5,2.5],
        "closes": [1.5,2.5,3.5], "volumes": [1,1,1],
        "num_trades": [0,0,0], "taker_buy_volumes": [0,0,0],
        "taker_buy_quote_volumes": [0,0,0], "buy_sell_ratio": [.5,.5,.5],
        "count": 3, "source": "binance", "symbol": "ETH/USDT", "timeframe": "5m",
    }
    dm = HistoricalDataManager({"5m": base}, "binance")
    dm.cutoff = 2999
    data = dm.get_ohlcv("ETH/USDT", "5m", 10)
    assert data["close_timestamps"] == [1999, 2999]
    assert 3999 not in data["close_timestamps"]

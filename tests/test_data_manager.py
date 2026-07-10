import time

import pytest

from data_manager import DataManager, DataManagerError


def test_normalization_is_strict():
    assert DataManager.normalize_symbol("ethusdt") == "ETH/USDT"
    assert DataManager.normalize_timeframe("1H") == "1h"
    assert DataManager.normalize_timeframe("1M") == "1M"
    with pytest.raises(DataManagerError):
        DataManager.normalize_timeframe("7m")


def test_gate_symbol_without_separator_is_fixed():
    assert DataManager._underscore_symbol("ethusdt") == "ETH_USDT"


def test_finalize_sorts_deduplicates_and_drops_open_candle():
    dm = DataManager()
    now = int(time.time() * 1000)
    rows = [
        {"ts": now - 120_000, "o": 10, "h": 12, "l": 9, "c": 11, "v": 2, "close_ts": now - 60_001},
        {"ts": now - 180_000, "o": 9, "h": 11, "l": 8, "c": 10, "v": 1, "close_ts": now - 120_001},
        # duplicate timestamp; latest payload wins
        {"ts": now - 120_000, "o": 10, "h": 13, "l": 9, "c": 12, "v": 3, "close_ts": now - 60_001},
        {"ts": now - 30_000, "o": 12, "h": 14, "l": 11, "c": 13, "v": 4, "close_ts": now + 30_000},
    ]
    data = dm._finalize_rows(rows, "ETH/USDT", "1m", "fake", 10, True)
    assert data["count"] == 2
    assert data["timestamps"] == sorted(data["timestamps"])
    assert data["closes"][-1] == 12
    assert data["dropped_open_candles"] == 1


def test_multi_timeframe_pins_resolved_exchange(monkeypatch):
    dm = DataManager()
    calls = []

    def fake(symbol, timeframe, limit, **kwargs):
        calls.append((timeframe, kwargs.get("exchange"), kwargs.get("allow_fallback")))
        return {
            "source": "kucoin", "symbol": "ETH/USDT", "timeframe": timeframe,
            "count": 20, "timestamps": list(range(20)), "close_timestamps": list(range(20)),
            "opens": [1] * 20, "highs": [1] * 20, "lows": [1] * 20,
            "closes": [1] * 20, "volumes": [1] * 20,
        }

    monkeypatch.setattr(dm, "get_ohlcv", fake)
    bundle = dm.get_multi_timeframe("ETHUSDT", "5m", exchange="auto")
    assert bundle["entry"]["source"] == "kucoin"
    assert calls[0][1] == "auto"
    assert all(call[1] == "kucoin" for call in calls[1:])
    assert all(call[2] is False for call in calls[1:])


def test_kucoin_historical_paginates_backward(monkeypatch):
    dm = DataManager()
    pages = [
        [["300","1","2","3","0.5","10","20"],["200","1","2","3","0.5","10","20"]],
        [["150","1","2","3","0.5","10","20"],["100","1","2","3","0.5","10","20"]],
    ]
    class Response:
        status_code=200
        def __init__(self,data): self.data=data
        def json(self): return {"code":"200000","data":self.data}
    monkeypatch.setattr(dm.session,"get",lambda *a,**k: Response(pages.pop(0)))
    data=dm.get_historical_ohlcv("ETH/USDT","1m",100_000,300_000,"kucoin")
    assert data["timestamps"] == [100_000,150_000,200_000,300_000]


def test_explicit_exchange_does_not_fallback(monkeypatch):
    dm = DataManager()
    called = []

    def fail(*args, **kwargs):
        called.append("okx")
        return None

    def should_not_run(*args, **kwargs):
        called.append("binance")
        return {"closes": [1] * 10, "count": 10, "source": "binance"}

    monkeypatch.setattr(dm, "_fetch_okx_paginated", fail)
    monkeypatch.setattr(dm, "_fetch_binance", should_not_run)
    assert dm.get_ohlcv("ETH/USDT", "5m", 20, exchange="okx") is None
    assert called == ["okx"]

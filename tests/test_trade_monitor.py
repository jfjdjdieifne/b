from data_manager import DataManager
from trade_monitor import TradeMonitor


def candles(stage=1):
    # Long: entry 100, SL 95, TP1 110, TP2 120.
    rows = [
        (1_000, 103, 104, 102, 103),
        (2_000, 103, 104, 99, 101),   # entry touched, SL safe
        (3_000, 101, 111, 100, 110),  # TP1
    ]
    if stage >= 2:
        rows.append((4_000, 110, 121, 109, 120))  # TP2
    return {
        "timestamps": [x[0] for x in rows],
        "close_timestamps": [x[0] + 999 for x in rows],
        "opens": [x[1] for x in rows],
        "highs": [x[2] for x in rows],
        "lows": [x[3] for x in rows],
        "closes": [x[4] for x in rows],
        "volumes": [1] * len(rows),
        "num_trades": [0] * len(rows),
        "taker_buy_volumes": [0] * len(rows),
        "taker_buy_quote_volumes": [0] * len(rows),
        "buy_sell_ratio": [0.5] * len(rows),
        "count": len(rows), "source": "okx", "symbol": "ETH/USDT", "timeframe": "5m",
        "last_candle_closed": True,
    }


def test_tp1_then_tp2_automatic_management(tmp_path, monkeypatch):
    dm = DataManager()
    stage = {"value": 1}
    monkeypatch.setattr(dm, "get_ohlcv", lambda *a, **k: candles(stage["value"]))
    monitor = TradeMonitor(dm, str(tmp_path / "trades.json"))
    trade = monitor.add({
        "symbol": "ETH/USDT", "exchange": "okx", "timeframe": "5m",
        "side": "BUY_LIMIT", "entry": "100", "stop_loss": "95",
        "tp1": "110", "tp2": "120", "status": "pending_entry",
    })
    # Synthetic candles use tiny timestamps; make them explicitly newer than
    # the synthetic tracking creation point.
    trade["created_at"]["timestamp_ms"] = 0
    updated = monitor.refresh(trade["id"])
    assert updated["status"] == "runner"
    assert updated["tp1_hit"] is True
    assert updated["current_stop_loss"] == 100
    assert updated["remaining_pct"] == 50

    stage["value"] = 2
    updated = monitor.refresh(trade["id"])
    assert updated["status"] == "tp2_hit"
    assert updated["remaining_pct"] == 0
    assert updated["realized_r"] == 3.0  # 50% at 2R + 50% at 4R

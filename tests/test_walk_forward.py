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


def test_trade_audit_bundle_contains_before_after_and_forensics(tmp_path):
    from walk_forward_backtest import WalkForwardBacktester
    analysis = {
        "audit_id":"A-1","symbol":"ETH/USDT","exchange":"kucoin",
        "execution_timeframe":"5m","data_cutoff":{"close":{"timestamp_ms":2999}},
        "decision":{"state":"ORDER_READY"},"expectation":{},"decision_trace":[],"frames":{},
        "candidate":{"model":"MODEL_B","side":"BUY_LIMIT","entry":100,"stop_loss":95,
                     "targets":[{"name":"TP1","price":110}],"conditions":[],"basis":"test"},
    }
    ohlc={"timestamps":[1000,2000],"close_timestamps":[1999,2999],
          "opens":[99,100],"highs":[101,111],"lows":[98,96],"closes":[100,110],
          "volumes":[1,1],"count":2}
    trade={"entry_time":{"timestamp_ms":3999},"entry":100,"realized_r":2.0,"net_pnl":2.0}
    outcome={"classification":"WIN_FULL","tp1_hit":True,"tp1_hit_time":4999,
             "tp1_price":110,"final_exit_reason":"TP2_HIT","final_exit_time":5999,
             "final_exit_price":120,"trail_history":[]}
    bt=WalkForwardBacktester(reports_dir=str(tmp_path))
    case=bt._write_case_bundle(str(tmp_path),"CASE-1",analysis,{"5m":ohlc},ohlc,outcome,trade)
    import os,json
    expected={"00_manifest.json","01_analysis_at_signal.json","02_ohlc_before_signal_5m.json",
              "03_ohlc_after_signal_execution_tf.json","04_outcome_and_management.json","README_AR.md"}
    assert expected.issubset(set(os.listdir(case)))
    manifest=json.load(open(os.path.join(case,"00_manifest.json"),encoding="utf8"))
    assert manifest["sha256"]["02_ohlc_before_signal_5m.json"]
    outcome_doc=json.load(open(os.path.join(case,"04_outcome_and_management.json"),encoding="utf8"))
    assert "forensic_diagnosis" in outcome_doc
    from management_policy_comparison import compare_bundle
    comparison=compare_bundle(str(tmp_path),count=1)
    assert comparison["case_count"] == 1
    assert set(comparison["summary"]) == {"ICT_80_RANGE_PROGRESS","ICT_50_RANGE_PROGRESS","80_BE","50_BE","50_STRUCTURE","20_STRUCTURE_BIG_RUNNER"}
    from backtest_forensics import generate_forensics
    forensic=generate_forensics(str(tmp_path),{
        "id":"WFT-X","trade_count":1,"win_rate":100,"return_pct":2,
        "trades":[{"realized_r":2}],"equity_curve":[{"balance":100},{"balance":102}],
    })
    assert forensic["max_losing_streak"] == 0
    assert forensic["best_five"][0]["case_id"] == "CASE-1"

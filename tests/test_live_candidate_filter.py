from snapshot_analyzer import SnapshotAnalyzer


def test_target_already_behind_current_price_is_not_watchlisted():
    chosen = {
        "model":"MODEL_C_BOS_PULLBACK","status":"PENDING_SETUP","conditions":[],
        "plan":{"direction":"BUY_LIMIT","entry":1750,"stop_loss":1740,"tp":1751,
                "tp1":{"price":1751,"kind":"BROKEN_BOS_LEVEL","rr":0.1},
                "tp2":{"mode":"OPEN_TRAILING"},"basis":"old consumed target"},
    }
    model_result={"chosen_model":chosen}
    entry={"closes":[1777],"close_timestamps":[1_783_650_000_000],
           "symbol":"ETH/USDT","source":"binance","timeframe":"5m"}
    frame={"latest_structural_breaks":[]}
    session={"is_executable_window":False}
    result=SnapshotAnalyzer._candidate_report(
        None,model_result,"BULLISH",entry,frame,session,100,1,"ALIGNED",50
    )
    assert result is None


def test_completed_model_away_from_entry_becomes_order_ready():
    chosen = {
        "model":"MODEL_B_SWEEP_FVG","status":"READY","conditions":[],
        "plan":{"direction":"BUY_LIMIT","entry":1750,"stop_loss":1740,"tp":1800,
                "tp1":{"price":1800,"kind":"UNSWEPT_SWING_HIGH","rr":5},
                "tp2":{"mode":"OPEN_TRAILING"},"basis":"complete sweep displacement FVG"},
    }
    entry={"closes":[1777],"close_timestamps":[1_783_650_000_000],
           "symbol":"ETH/USDT","source":"binance","timeframe":"5m"}
    frame={"latest_structural_breaks":[{
        "direction":"BULLISH","displacement_confirmed":True,
        "break_candle_index_from_end":-2,
    }]}
    result=SnapshotAnalyzer._candidate_report(
        None,{"chosen_model":chosen},"BULLISH",entry,frame,
        {"is_executable_window":True},100,1,"ALIGNED",50
    )
    assert result["decision"]["state"] == "ORDER_READY"
    assert result["tracking_payload"]["status"] == "pending_entry"
    assert result["side"] == "BUY_LIMIT"

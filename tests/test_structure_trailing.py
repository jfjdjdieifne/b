from ict_math_engine import simulate_managed_trade_outcome


def test_structure_trail_uses_confirmed_past_pivot_and_next_candle_only():
    candles={
        "opens":[100,110,111,112,113,114],
        "highs":[111,112,113,114,115,116],
        "lows":[99,105,98,106,107,97],
        "closes":[110,111,112,113,114,103],
        "timestamps":[0,1,2,3,4,5],
    }
    result=simulate_managed_trade_outcome(
        candles,entry_price=100,sl_price=90,tp1_price=110,
        tp2_info={"mode":"OPEN_TRAILING"},is_short=False,
        tp1_fraction=.5,post_tp1_stop_policy="STRUCTURE_ONLY",
    )
    structural=[x for x in result["trail_history"] if x["reason"]=="STRUCTURE_TRAIL_CONFIRMED_HL"]
    assert structural == [{"confirmed_at_idx":4,"pivot_idx":2,"effective_from_idx":5,"new_sl":98,"reason":"STRUCTURE_TRAIL_CONFIRMED_HL"}]
    assert result["final_exit_price"] == 98
    assert result["final_exit_idx_from_start"] == 5


def test_structure_only_does_not_force_be_at_tp1():
    candles={"opens":[100,110],"highs":[111,111],"lows":[99,95],"closes":[110,96],"timestamps":[0,1]}
    result=simulate_managed_trade_outcome(
        candles,100,90,110,{"mode":"OPEN_TRAILING"},False,
        tp1_fraction=.5,post_tp1_stop_policy="STRUCTURE_ONLY",
    )
    assert result["final_exit_reason"] == "NEITHER_HIT_WITHIN_WINDOW"
    assert result["final_exit_price"] == 96

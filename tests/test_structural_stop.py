from ict_entry_checklist_engine import _place_structural_stop, _structural_wick_buffer


def test_stop_is_anchor_plus_market_wick_context_not_fixed_percent():
    data={
        "opens":[100,102,103,104],"closes":[102,103,104,105],
        "highs":[103,104,105,106],"lows":[99,101,102,103],
    }
    # Lower wicks are all 1 price unit; no ATR/% formula is involved.
    assert _structural_wick_buffer(data,True) == 1
    stop,why=_place_structural_stop(data,95,True,"LIQUIDITY_SWEEP_EXTREME")
    assert stop == 94
    assert why["anchor_price"] == 95
    assert why["anchor_kind"] == "LIQUIDITY_SWEEP_EXTREME"
    assert why["buffer_method"] == "MEDIAN_RELEVANT_WICK_WITH_INFERRED_TICK_FLOOR"


def test_short_stop_sits_above_causal_high():
    data={"opens":[100,99],"closes":[99,98],"highs":[101,100],"lows":[98,97]}
    stop,_=_place_structural_stop(data,105,False,"MSS_HIGH")
    assert stop > 105

import math

import numpy as np
import pandas as pd
import pytest

from trading_system.audit.causal_state import (
    ReentrancyPolicy,
    verify_state_isolation,
    verify_truncation_invariance,
)
from trading_system.liquidity.liquidity_map import (
    CausalLiquidityMapEngine,
    LiquidityMapDataError,
    _LiquidityMapAuditEngine,
)
from trading_system.structure.structural_breaks import CausalStructuralBreakEngine
from trading_system.structure.swing_detector import (
    CausalAdaptiveSwingDetector,
    EmpiricalConfirmationPolicy,
)
from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine


def _surface(length, events, ohlc=None):
    hf = np.zeros(length, bool); lf = np.zeros(length, bool)
    origins = pd.array([pd.NA] * length, dtype="Int64")
    prices = np.full(length, np.nan)
    confirms = pd.array([pd.NA] * length, dtype="Int64")
    for row, typ, origin, price in events:
        (hf if typ == "HIGH" else lf)[row] = True
        origins[row] = origin; prices[row] = price; confirms[row] = row
    event = pd.DataFrame({
        "swing_high_confirmed": hf, "swing_low_confirmed": lf,
        "swing_origin_position": origins, "swing_price": prices,
        "swing_confirmation_position": confirms,
    })
    seq = ConfirmedSwingSequenceEngine().analyze(event)
    if ohlc is None:
        ohlc = [(100.0, 90.0, 95.0)] * length
    market = pd.DataFrame(ohlc, columns=["high", "low", "close"], dtype=float)
    return pd.concat([market, seq], axis=1)


def _analyze(df):
    return CausalLiquidityMapEngine().analyze(df)


def test_creation_timing_no_backfill_and_no_same_bar_interaction():
    df = _surface(
        5,
        [(3, "HIGH", 0, 100.0)],
        [(110, 90, 95), (120, 90, 110), (130, 90, 120),
         (140, 90, 130), (101, 99, 100)],
    )
    bar, events = _analyze(df)
    assert not bar.loc[:2, "liquidity_level_created"].any()
    assert bar.loc[3, "liquidity_level_created"]
    assert bar.loc[3, "created_level_id"] == 0
    assert bar.loc[:3, "high_side_first_touch_count"].sum() == 0
    assert bar.loc[4, "high_side_first_touch_count"] == 1
    created = events[events.event_type == "LEVEL_CREATED"]
    assert created.event_position.tolist() == [3]
    assert created.source_origin_position.tolist() == [0]


def test_old_level_interacts_on_new_level_confirmation_bar():
    df = _surface(
        4,
        [(1, "HIGH", 0, 100.0), (3, "HIGH", 2, 110.0)],
        [(99, 90, 95), (100, 95, 99), (99, 95, 98), (111, 105, 109)],
    )
    bar, events = _analyze(df)
    assert bar.loc[3, "liquidity_level_created"]
    assert bar.loc[3, "high_side_first_wick_breach_count"] == 1
    wick = events[(events.event_position == 3) & (events.event_type == "FIRST_WICK_BREACH")]
    assert wick.level_id.tolist() == [0]
    assert not ((events.level_id == 1) & (events.event_position == 3) &
                (events.event_type != "LEVEL_CREATED")).any()


def test_unique_identity_same_price_and_source_metadata_preserved():
    df = _surface(4, [(1, "HIGH", 0, 100.0), (3, "HIGH", 2, 100.0)])
    bar, events = _analyze(df)
    created = events[events.event_type == "LEVEL_CREATED"]
    assert created.level_id.tolist() == [0, 1]
    assert created.immutable_level_price.tolist() == [100.0, 100.0]
    assert created.source_origin_position.tolist() == [0, 2]
    assert bar.loc[3, "created_level_source_class"] == "EH"
    assert bar.loc[3, "nearest_same_side_distance_fraction"] == 0.0


def test_proximity_nearest_read_before_push_and_one_observation_per_level():
    df = _surface(
        6,
        [(1, "HIGH", 0, 100.0), (3, "HIGH", 2, 110.0), (5, "HIGH", 4, 105.0)],
    )
    bar, events = _analyze(df)
    assert math.isnan(bar.loc[1, "nearest_same_side_distance_fraction"])
    assert bar.loc[1, "nearest_distance_reference_history_count"] == 0
    assert bar.loc[3, "nearest_prior_same_side_level_id"] == 0
    assert bar.loc[3, "nearest_distance_reference_history_count"] == 0
    assert math.isnan(bar.loc[3, "nearest_distance_percentile"])
    assert bar.loc[5, "nearest_prior_same_side_level_id"] == 1
    assert bar.loc[5, "nearest_distance_reference_history_count"] == 1
    assert bar.loc[5, "nearest_distance_percentile"] == 0.0
    created = events[events.event_type == "LEVEL_CREATED"]
    assert created.nearest_same_side_distance_fraction.notna().sum() == 2


def test_high_low_share_nearest_distance_history():
    df = _surface(
        7,
        [(1, "HIGH", 0, 100.0), (2, "HIGH", 1, 110.0),
         (3, "LOW", 1, 90.0), (5, "LOW", 4, 81.0)],
    )
    bar, _ = _analyze(df)
    assert bar.loc[2, "nearest_distance_reference_history_count"] == 0
    assert bar.loc[3, "nearest_distance_reference_history_count"] == 1
    assert math.isnan(bar.loc[3, "nearest_same_side_distance_fraction"])
    assert bar.loc[5, "nearest_distance_reference_history_count"] == 1
    assert not math.isnan(bar.loc[5, "nearest_distance_percentile"])


def test_zero_denominator_exact_zero_distance():
    df = _surface(3, [(1, "LOW", 0, 0.0), (2, "LOW", 1, 0.0)],
                  [(1, -1, 0), (1, -1, 0), (1, -1, 0)])
    bar, _ = _analyze(df)
    assert bar.loc[2, "nearest_same_side_distance_fraction"] == 0.0


def test_exact_touch_strict_breach_and_wick_only_events():
    df = _surface(
        4, [(1, "HIGH", 0, 100.0)],
        [(99, 90, 95), (100, 95, 99), (100, 98, 100), (101, 98, 100)],
    )
    bar, events = _analyze(df)
    assert bar.loc[2, "high_side_first_touch_count"] == 1
    assert bar.loc[2, "high_side_first_wick_breach_count"] == 0
    assert bar.loc[3, "high_side_first_wick_breach_count"] == 1
    assert bar.loc[3, "high_side_first_wick_only_count"] == 1
    types = events[events.event_position == 3].event_type.tolist()
    assert "FIRST_WICK_BREACH" in types
    assert "FIRST_WICK_ONLY_EXCURSION" in types


def test_low_wick_only_and_close_then_later_reclaim():
    df = _surface(
        5, [(1, "LOW", 0, 100.0)],
        [(110, 101, 105), (105, 100, 101), (102, 99, 100),
         (101, 98, 99), (102, 99, 100)],
    )
    bar, events = _analyze(df)
    assert bar.loc[2, "low_side_first_wick_only_count"] == 1
    assert bar.loc[3, "low_side_first_close_breach_count"] == 1
    assert bar.loc[3, "low_side_first_reclaim_count"] == 0
    assert bar.loc[4, "low_side_first_reclaim_count"] == 1
    reclaim = events[events.event_type == "FIRST_RECLAIM_AFTER_CLOSE_BREACH"]
    assert reclaim.event_position.tolist() == [4]


def test_post_close_reclaim_does_not_create_late_wick_only_excursion():
    df = _surface(
        4, [(1, "HIGH", 0, 100.0)],
        [(99, 90, 95), (100, 95, 99), (105, 98, 103), (104, 98, 99)],
    )
    bar, events = _analyze(df)
    assert bar.loc[2, "high_side_first_close_breach_count"] == 1
    assert bar.loc[3, "high_side_first_reclaim_count"] == 1
    assert bar.loc[3, "high_side_first_wick_only_count"] == 0
    level_events = events[events.level_id == 0]
    assert "FIRST_RECLAIM_AFTER_CLOSE_BREACH" in level_events.event_type.tolist()
    assert "FIRST_WICK_ONLY_EXCURSION" not in level_events.event_type.tolist()
    _assert_event_table_truncation(df, [1, 2, 3])


def test_pre_close_wick_only_then_close_and_reclaim_lifecycle():
    df = _surface(
        5, [(1, "HIGH", 0, 100.0)],
        [(99, 90, 95), (100, 95, 99), (105, 98, 99),
         (104, 98, 103), (103, 98, 99)],
    )
    bar, events = _analyze(df)
    assert bar.loc[2, "high_side_first_wick_only_count"] == 1
    assert bar.loc[3, "high_side_first_close_breach_count"] == 1
    assert bar.loc[4, "high_side_first_reclaim_count"] == 1
    level_types = events[events.level_id == 0].event_type.tolist()
    assert level_types.count("FIRST_WICK_ONLY_EXCURSION") == 1
    assert level_types.count("FIRST_CLOSE_BREACH") == 1
    assert level_types.count("FIRST_RECLAIM_AFTER_CLOSE_BREACH") == 1
    _assert_event_table_truncation(df, [1, 2, 3, 4])


def test_no_repeated_first_events_and_level_retained():
    df = _surface(
        5, [(1, "HIGH", 0, 100.0)],
        [(99, 90, 95), (100, 95, 99), (102, 99, 101),
         (103, 100, 102), (104, 101, 103)],
    )
    bar, events = _analyze(df)
    assert bar.high_side_first_touch_count.sum() == 1
    assert bar.high_side_first_wick_breach_count.sum() == 1
    assert bar.high_side_first_close_breach_count.sum() == 1
    assert bar.loc[4, "known_high_side_level_count"] == 1
    assert events.level_id.nunique() == 1


def test_multiple_historical_levels_preserved_and_one_bar_hits_many():
    df = _surface(
        6,
        [(1, "HIGH", 0, 100.0), (2, "HIGH", 1, 95.0), (3, "LOW", 1, 90.0)],
        [(99, 91, 95), (100, 95, 99), (95, 90, 94),
         (94, 90, 92), (110, 80, 95), (100, 90, 95)],
    )
    bar, events = _analyze(df)
    assert bar.loc[4, "high_side_first_wick_breach_count"] == 2
    assert bar.loc[4, "low_side_first_wick_breach_count"] == 1
    row_events = events[events.event_position == 4]
    assert set(row_events.level_id.tolist()) == {0, 1, 2}
    assert bar.loc[5, "known_high_side_level_count"] == 2
    assert bar.loc[5, "known_low_side_level_count"] == 1
    ordered = row_events[["level_id", "event_type"]].copy()
    assert ordered.level_id.tolist() == sorted(ordered.level_id.tolist())


def test_bar_aggregate_counts_match_event_table():
    df = _surface(
        4, [(1, "HIGH", 0, 100.0), (2, "LOW", 0, 90.0)],
        [(99, 91, 95), (100, 95, 99), (95, 90, 92), (110, 80, 95)],
    )
    bar, events = _analyze(df)
    mapping = {
        "high_side_first_touch_count": ("HIGH_SIDE", "FIRST_TOUCH"),
        "low_side_first_touch_count": ("LOW_SIDE", "FIRST_TOUCH"),
        "high_side_first_wick_breach_count": ("HIGH_SIDE", "FIRST_WICK_BREACH"),
        "low_side_first_wick_breach_count": ("LOW_SIDE", "FIRST_WICK_BREACH"),
        "high_side_first_close_breach_count": ("HIGH_SIDE", "FIRST_CLOSE_BREACH"),
        "low_side_first_close_breach_count": ("LOW_SIDE", "FIRST_CLOSE_BREACH"),
    }
    for column, (side, typ) in mapping.items():
        table_counts = events[(events.side == side) & (events.event_type == typ)].groupby(
            "event_position"
        ).size()
        expected = np.zeros(len(bar), dtype=int)
        for position, count in table_counts.items(): expected[int(position)] = int(count)
        np.testing.assert_array_equal(bar[column], expected)


def _assert_event_table_truncation(df, splits):
    full_bar, full_events = _analyze(df)
    for k in splits:
        trunc_bar, trunc_events = _analyze(df.iloc[:k].copy())
        pd.testing.assert_frame_equal(full_bar.iloc[:k], trunc_bar, check_exact=True)
        expected_events = full_events[full_events.event_position < k].reset_index(drop=True)
        pd.testing.assert_frame_equal(expected_events, trunc_events, check_exact=True)


def test_future_mutation_append_and_event_table_truncation():
    df = _surface(
        8, [(1, "HIGH", 0, 100.0), (3, "HIGH", 2, 105.0), (5, "LOW", 4, 90.0)],
        [(99,91,95),(100,95,99),(101,98,100),(105,100,104),
         (110,80,95),(95,90,92),(120,70,100),(100,90,95)],
    )
    full_bar, full_events = _analyze(df)
    mutated = df.copy(); mutated.loc[6:, ["high","low","close"]] = [1000, -1000, 0]
    mb, me = _analyze(mutated)
    pd.testing.assert_frame_equal(full_bar.iloc[:6], mb.iloc[:6], check_exact=True)
    pd.testing.assert_frame_equal(
        full_events[full_events.event_position < 6].reset_index(drop=True),
        me[me.event_position < 6].reset_index(drop=True), check_exact=True,
    )
    future = _surface(2, [], [(200,0,100),(300,-10,150)])
    future.index = pd.RangeIndex(len(df), len(df)+2)
    ab, ae = _analyze(pd.concat([df, future]))
    pd.testing.assert_frame_equal(full_bar, ab.iloc[:len(df)], check_exact=True)
    pd.testing.assert_frame_equal(full_events, ae[ae.event_position < len(df)].reset_index(drop=True), check_exact=True)
    _assert_event_table_truncation(df, range(1, len(df)))


def test_module01_and_event_table_state_isolation():
    a = _surface(6, [(1,"HIGH",0,100.0),(3,"LOW",2,90.0)])
    b = _surface(7, [(2,"LOW",0,80.0),(5,"HIGH",4,120.0)])
    results = verify_truncation_invariance(
        _LiquidityMapAuditEngine, a, split_fractions=(), additional_split_points=[1,2,3,4,5]
    )
    assert all(x.passed for x in results)
    state = verify_state_isolation(
        _LiquidityMapAuditEngine, a, b, policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT
    )
    assert state.passed
    engine = CausalLiquidityMapEngine()
    _, fresh_b = CausalLiquidityMapEngine().analyze(b)
    engine.analyze(a)
    _, after_b = engine.analyze(b)
    pd.testing.assert_frame_equal(fresh_b, after_b, check_exact=True)


def test_scale_invariance():
    events = [(1,"HIGH",0,100.0),(3,"HIGH",2,110.0),(5,"LOW",4,90.0)]
    ohlc = [(99,91,95),(100,95,99),(101,98,100),(110,105,108),(111,89,100),(112,88,101)]
    base = _surface(6, events, ohlc)
    scaled = _surface(6, [(r,t,o,p*8) for r,t,o,p in events],
                      [tuple(v*8 for v in row) for row in ohlc])
    bb, be = _analyze(base); sb, se = _analyze(scaled)
    for c in ("nearest_same_side_distance_fraction", "nearest_distance_percentile"):
        pd.testing.assert_series_equal(bb[c], sb[c], check_exact=True)
    assert be[["event_position","level_id","side","event_type"]].equals(
        se[["event_position","level_id","side","event_type"]]
    )
    np.testing.assert_allclose(se.immutable_level_price, be.immutable_level_price*8)
    np.testing.assert_allclose(se.overshoot_fraction, be.overshoot_fraction, equal_nan=True)


def test_validation_and_immutability_empty_small():
    empty = _surface(0, [])
    bar, events = _analyze(empty)
    assert bar.empty and events.empty
    one = _surface(1, [])
    before = one.copy(deep=True); _analyze(one)
    pd.testing.assert_frame_equal(one, before, check_exact=True)

    bad = _surface(2, [(1,"HIGH",0,100.0)])
    bad.loc[1,"structure_event_type"] = "LOW"
    with pytest.raises(LiquidityMapDataError): _analyze(bad)
    simultaneous = _surface(2, [(1,"HIGH",0,100.0)])
    simultaneous.loc[1,"swing_low_confirmed"] = True
    with pytest.raises(LiquidityMapDataError): _analyze(simultaneous)

    linked = _surface(4, [(1,"HIGH",0,100.0),(3,"HIGH",2,110.0)])
    for column, value in (
        ("previous_same_type_price", 999.0),
        ("previous_same_type_origin_position", 2),
        ("same_type_log_price_change", 999.0),
        ("current_structure_swing_price", 999.0),
    ):
        malformed = linked.copy(deep=True)
        malformed.loc[3, column] = value
        with pytest.raises(LiquidityMapDataError):
            _analyze(malformed)

    non_event_metadata = _surface(2, [])
    non_event_metadata.loc[0, "current_structure_swing_price"] = 100.0
    with pytest.raises(LiquidityMapDataError, match="missing"):
        _analyze(non_event_metadata)

    for mutate in ("nan", "highlow", "close"):
        x = _surface(1, [])
        if mutate == "nan": x.loc[0,"high"] = np.nan
        elif mutate == "highlow": x.loc[0,["high","low"]] = [80,90]
        else: x.loc[0,"close"] = 101
        with pytest.raises(LiquidityMapDataError): _analyze(x)


def test_index_columns_and_collision_validation():
    dup = _surface(2, []); dup.index=[1,1]
    with pytest.raises(LiquidityMapDataError): _analyze(dup)
    unordered = _surface(2, []); unordered.index=[2,1]
    with pytest.raises(LiquidityMapDataError): _analyze(unordered)
    collision = _surface(1, []); collision["liquidity_level_created"] = False
    with pytest.raises(LiquidityMapDataError): _analyze(collision)
    dc = _surface(1, []); dc.insert(0,"dup",1); dc.columns=["dup"]+list(dc.columns[1:-1])+["dup"]
    with pytest.raises(LiquidityMapDataError): _analyze(dc)


def _real_raw():
    h=[10,11,10.8,10.6,10.8,12,11.8,11.6,11.4]
    l=[9,10,10.5,10,10.1,11,11.5,11,11.2]
    return pd.DataFrame({"high":h,"low":l,"close":[(a+b)/2 for a,b in zip(h,l)]})


def _real_chain(df):
    policy=EmpiricalConfirmationPolicy(quantile=.5,prior_continuation_reversals=(.005,.01))
    a=CausalAdaptiveSwingDetector(policy).analyze(df[["high","low"]])
    a.insert(2,"close",df.close.to_numpy())
    b=ConfirmedSwingSequenceEngine().analyze(a)
    return b, CausalLiquidityMapEngine().analyze(b)


def test_real_integration_and_21c_compatibility():
    upstream, (bar, events) = _real_chain(_real_raw())
    created = events[events.event_type == "LEVEL_CREATED"]
    assert created.event_position.tolist() == [2,4,6,8]
    assert created.side.tolist() == ["HIGH_SIDE","LOW_SIDE","HIGH_SIDE","LOW_SIDE"]
    c = CausalStructuralBreakEngine().analyze(upstream)
    assert c.loc[5,"high_close_breach_event"]
    c_level = c.loc[5,"monitored_high_price"]
    matching = events[(events.event_position==5)&(events.event_type=="FIRST_CLOSE_BREACH")]
    assert c_level in matching.immutable_level_price.tolist()
    assert bar.loc[5,"high_side_first_close_breach_count"] >= 1


def test_real_end_to_end_truncation():
    class Chain:
        def analyze(self, df, **kwargs):
            return _real_chain(df)[1]
    raw=_real_raw()
    results=verify_truncation_invariance(
        Chain, raw, split_fractions=(), additional_split_points=list(range(1,len(raw)))
    )
    assert all(x.passed for x in results)
    _, full_events=_real_chain(raw)[1]
    for k in range(1,len(raw)):
        _, trunc_events=_real_chain(raw.iloc[:k].copy())[1]
        pd.testing.assert_frame_equal(
            full_events[full_events.event_position<k].reset_index(drop=True),
            trunc_events, check_exact=True,
        )

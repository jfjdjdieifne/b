import inspect
import math
import re

import numpy as np
import pandas as pd
import pytest

from trading_system.audit.causal_state import (
    ReentrancyPolicy,
    verify_state_isolation,
    verify_truncation_invariance,
)
from trading_system.orderflow.volume_delta import (
    CausalVolumeDeltaEngine,
    OrderFlowMode,
    VolumeDeltaConfigError,
    VolumeDeltaDataError,
    _ActualAuditEngine,
    _ProxyAuditEngine,
)


def _actual(buy, sell, volume=None):
    d = {"buy_volume": buy, "sell_volume": sell}
    if volume is not None: d["volume"] = volume
    return pd.DataFrame(d)


def _proxy(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], dtype=float)


def test_mode_is_explicit_and_no_auto_mode():
    with pytest.raises(TypeError):
        CausalVolumeDeltaEngine()  # type: ignore
    with pytest.raises(VolumeDeltaConfigError):
        CausalVolumeDeltaEngine(mode="ACTUAL_AGGRESSOR")  # type: ignore


def test_actual_hand_calculation_extremes_equal_and_zero_total():
    df = _actual([7, 5, 0, 0], [3, 5, 4, 0])
    out = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(df)
    np.testing.assert_array_equal(out.raw_delta[:3], [4.0, 0.0, -4.0])
    assert out.delta_ratio.iloc[0] == 0.4
    assert out.delta_ratio.iloc[1] == 0.0
    assert out.delta_ratio.iloc[2] == -1.0
    assert math.isnan(out.delta_ratio.iloc[3])
    assert out.order_flow_mode.unique().tolist() == ["ACTUAL_AGGRESSOR"]


def test_actual_buy_only_sell_only_bounds():
    out = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(
        _actual([10, 0], [0, 10])
    )
    assert out.delta_ratio.tolist() == [1.0, -1.0]
    assert out.delta_ratio.between(-1, 1).all()


def test_actual_read_before_push_ties_and_independent_magnitude():
    out = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(
        _actual([7, 7, 3], [3, 3, 7])
    )
    assert math.isnan(out.delta_ratio_percentile.iloc[0])
    assert out.delta_ratio_history_count.tolist() == [0, 1, 2]
    assert out.delta_ratio_percentile.iloc[1] == 0.5
    assert out.delta_ratio_percentile.iloc[2] == 0.0
    assert math.isnan(out.delta_magnitude_percentile.iloc[0])
    assert out.delta_magnitude_percentile.iloc[1] == 0.5
    assert out.delta_magnitude_percentile.iloc[2] == 0.5


def test_actual_positive_volume_scaling():
    df = _actual([7, 2, 9], [3, 8, 1])
    base = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(df)
    scaled = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(df * 8)
    np.testing.assert_array_equal(scaled.raw_delta, base.raw_delta * 8)
    np.testing.assert_array_equal(scaled.total_classified_volume, base.total_classified_volume * 8)
    for c in ("delta_ratio", "delta_ratio_percentile", "delta_magnitude_percentile"):
        pd.testing.assert_series_equal(base[c], scaled[c], check_exact=True)


def test_reconciliation_below_above_and_zero_without_rejection():
    df = _actual([30, 80, 0], [20, 70, 0], [100, 100, 0])
    out = CausalVolumeDeltaEngine(
        mode=OrderFlowMode.ACTUAL_AGGRESSOR, reconcile_total_volume=True
    ).analyze(df)
    assert out.classified_volume_fraction.iloc[0] == 0.5
    assert out.classified_volume_fraction.iloc[1] == 1.5
    assert math.isnan(out.classified_volume_fraction.iloc[2])


def test_actual_derived_float64_overflow_rejected():
    maximum = np.finfo(np.float64).max
    engine = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR)
    with pytest.raises(VolumeDeltaDataError, match="sum overflowed"):
        engine.analyze(_actual([maximum], [maximum]))

    # Under the valid non-negative domain, subtraction is bounded by max input;
    # this verifies the extreme finite non-overflow boundary remains accepted.
    out = engine.analyze(_actual([maximum], [0.0]))
    assert np.isfinite(out.raw_delta.iloc[0])
    assert np.isfinite(out.total_classified_volume.iloc[0])


def test_actual_volume_validation():
    engine = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR)
    for df in (
        _actual([-1], [1]), _actual([np.nan], [1]), _actual([np.inf], [1]),
        pd.DataFrame({"buy_volume": [True], "sell_volume": [False]}),
    ):
        with pytest.raises(VolumeDeltaDataError): engine.analyze(df)


def test_proxy_close_location_high_low_midpoint():
    df = _proxy([(5, 10, 0, 10, 100), (5, 10, 0, 0, 100), (5, 10, 0, 5, 100)])
    out = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(df)
    assert out.close_location_proxy.tolist() == [1.0, -1.0, 0.0]
    assert out.volume_pressure_proxy.tolist() == [1.0, -1.0, 0.0]
    assert out.order_flow_mode.unique().tolist() == ["OHLCV_PROXY"]
    assert "delta_ratio" not in out.columns


def test_proxy_zero_range_and_zero_volume_separation():
    df = _proxy([(5, 5, 5, 5, 100), (5, 10, 0, 8, 0)])
    out = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(df)
    assert math.isnan(out.close_location_proxy.iloc[0])
    assert math.isnan(out.volume_pressure_proxy.iloc[0])
    assert math.isnan(out.signed_volume_pressure_raw.iloc[0])
    assert out.close_location_proxy.iloc[1] == 0.6
    assert math.isnan(out.volume_pressure_proxy.iloc[1])
    assert out.signed_volume_pressure_raw.iloc[1] == 0.0
    assert out.pressure_proxy_history_count.tolist() == [0, 0]


def test_proxy_read_before_push_signed_and_magnitude():
    df = _proxy([(5,10,0,8,100),(5,10,0,8,100),(5,10,0,2,100)])
    out = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(df)
    assert math.isnan(out.pressure_proxy_percentile.iloc[0])
    assert out.pressure_proxy_percentile.iloc[1] == 0.5
    assert out.pressure_proxy_percentile.iloc[2] == 0.0
    assert out.pressure_magnitude_percentile.iloc[2] == 0.5


def test_proxy_price_and_volume_scaling():
    df = _proxy([(5,10,0,8,100),(5,10,0,2,200)])
    engine = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY)
    base = engine.analyze(df)
    price_scaled = df.copy(); price_scaled[["open","high","low","close"]] *= 8
    ps = engine.analyze(price_scaled)
    volume_scaled = df.copy(); volume_scaled["volume"] *= 8
    vs = engine.analyze(volume_scaled)
    for c in ("close_location_proxy","volume_pressure_proxy","pressure_proxy_percentile"):
        pd.testing.assert_series_equal(base[c], ps[c], check_exact=True)
        pd.testing.assert_series_equal(base[c], vs[c], check_exact=True)
    np.testing.assert_array_equal(vs.signed_volume_pressure_raw, base.signed_volume_pressure_raw*8)


def test_proxy_signed_raw_overflow_guard():
    maximum = np.finfo(np.float64).max
    with pytest.raises(VolumeDeltaDataError, match="signed_volume_pressure_raw overflowed"):
        CausalVolumeDeltaEngine._signed_pressure_raw(
            np.array([maximum]), np.array([2.0])
        )


def test_proxy_validation():
    engine = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY)
    cases = [
        _proxy([(5,0,10,5,1)]), _proxy([(11,10,0,5,1)]),
        _proxy([(5,10,0,11,1)]), _proxy([(5,10,0,5,-1)]),
        _proxy([(5,10,0,5,np.nan)]), _proxy([(5,10,0,5,np.inf)]),
    ]
    for df in cases:
        with pytest.raises(VolumeDeltaDataError): engine.analyze(df)
    bool_df = pd.DataFrame({"open":[1.],"high":[2.],"low":[0.],"close":[1.],"volume":[True]})
    with pytest.raises(VolumeDeltaDataError): engine.analyze(bool_df)


def test_fake_delta_adversarial_same_ohlcv_different_hidden_flow():
    # Hidden scenarios 90/10 and 10/90 aggressive composition can share this
    # exact completed OHLCV bar. Proxy output must therefore be identical.
    bar = _proxy([(5,10,0,8,100)])
    proxy_a = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(bar)
    proxy_b = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(bar.copy())
    pd.testing.assert_frame_equal(proxy_a, proxy_b, check_exact=True)
    actual_a = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(_actual([90],[10]))
    actual_b = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(_actual([10],[90]))
    assert actual_a.delta_ratio.iloc[0] == 0.8
    assert actual_b.delta_ratio.iloc[0] == -0.8
    assert proxy_a.volume_pressure_proxy.iloc[0] == proxy_b.volume_pressure_proxy.iloc[0]


def test_future_mutation_and_append_both_modes():
    actual = _actual([7,2,9,1,5],[3,8,1,9,5])
    ae = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR)
    full = ae.analyze(actual); mut=actual.copy(); mut.loc[3:]*=1000
    pd.testing.assert_frame_equal(full.iloc[:3], ae.analyze(mut).iloc[:3], check_exact=True)
    appended=pd.concat([actual,_actual([10**9],[0])],ignore_index=True)
    pd.testing.assert_frame_equal(full,ae.analyze(appended).iloc[:len(actual)],check_exact=True)

    proxy=_proxy([(5,10,0,8,100),(5,10,0,2,100),(5,10,0,5,100),(5,10,0,9,100)])
    pe=CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY)
    pf=pe.analyze(proxy); pm=proxy.copy(); pm.loc[3]=[500,1000,0,900,1e9]
    pd.testing.assert_frame_equal(pf.iloc[:3],pe.analyze(pm).iloc[:3],check_exact=True)
    proxy_appended=pd.concat([proxy,_proxy([(500,1000,0,900,1e9)])],ignore_index=True)
    pd.testing.assert_frame_equal(pf,pe.analyze(proxy_appended).iloc[:len(proxy)],check_exact=True)


def test_module01_truncation_and_state_isolation_both_modes():
    actual_a=_actual([7,2,9,1,5,8],[3,8,1,9,5,2]); actual_b=_actual([1,4,8,2,7,3],[9,6,2,8,3,7])
    proxy_a=_proxy([(5,10,0,c,100) for c in [8,2,5,9,1,6]])
    proxy_b=_proxy([(5,10,0,c,200) for c in [1,3,7,4,9,2]])
    for factory,a,b in ((_ActualAuditEngine,actual_a,actual_b),(_ProxyAuditEngine,proxy_a,proxy_b)):
        tr=verify_truncation_invariance(factory,a,split_fractions=(),additional_split_points=[1,2,3,4,5])
        assert all(x.passed for x in tr)
        st=verify_state_isolation(factory,a,b,policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT)
        assert st.passed


def test_input_contract_immutability_empty_one_row_and_collisions():
    for mode,empty in (
        (OrderFlowMode.ACTUAL_AGGRESSOR,_actual(pd.Series([],dtype=float),pd.Series([],dtype=float))),
        (OrderFlowMode.OHLCV_PROXY,pd.DataFrame({c:pd.Series([],dtype=float) for c in ["open","high","low","close","volume"]})),
    ):
        engine=CausalVolumeDeltaEngine(mode=mode); before=empty.copy(deep=True); out=engine.analyze(empty)
        assert out.empty; pd.testing.assert_frame_equal(empty,before,check_exact=True)
    one=_actual([0],[0]); out=CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(one)
    assert math.isnan(out.delta_ratio.iloc[0])
    source=_actual([1,2],[2,1]); before=source.copy(deep=True)
    CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(source)
    pd.testing.assert_frame_equal(source,before,check_exact=True)
    dup=source.copy(); dup.index=[1,1]
    with pytest.raises(VolumeDeltaDataError): CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(dup)
    unordered=source.copy(); unordered.index=[2,1]
    with pytest.raises(VolumeDeltaDataError): CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(unordered)
    collision=source.copy(); collision["raw_delta"]=0
    with pytest.raises(VolumeDeltaDataError): CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(collision)
    duplicate_columns=pd.DataFrame([[1.0,2.0,3.0]],columns=["buy_volume","sell_volume","buy_volume"])
    with pytest.raises(VolumeDeltaDataError): CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(duplicate_columns)


def test_secondary_source_guard():
    module=__import__("trading_system.orderflow.volume_delta",fromlist=["*"])
    source=inspect.getsource(module)
    for token in ("shift(-1","center=True","rolling(","expanding(","rank(pct=True)"):
        assert token not in source
    assert re.search(r"\bATR\b|\bRSI\b", source) is None

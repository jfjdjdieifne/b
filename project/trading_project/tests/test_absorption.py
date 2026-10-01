import inspect
import math
import re

import numpy as np
import pandas as pd
import pytest

from trading_system.audit.causal_state import ReentrancyPolicy, verify_state_isolation, verify_truncation_invariance
from trading_system.orderflow.absorption import (
    AbsorptionConfigError, AbsorptionDataError, CausalAbsorptionEvidenceEngine,
    _ActualAbsorptionAuditEngine, _ProxyAbsorptionAuditEngine,
)
from trading_system.orderflow.volume_delta import CausalVolumeDeltaEngine, OrderFlowMode


def _actual(close, buy, sell):
    source=pd.DataFrame({"close":close,"buy_volume":buy,"sell_volume":sell})
    return CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(source)


def _proxy(rows):
    source=pd.DataFrame(rows,columns=["open","high","low","close","volume"],dtype=float)
    return CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(source)


def test_explicit_mode_and_mode_identity():
    with pytest.raises(TypeError): CausalAbsorptionEvidenceEngine()  # type: ignore
    with pytest.raises(AbsorptionConfigError): CausalAbsorptionEvidenceEngine(mode="x")  # type: ignore
    actual=_actual([100],[1],[0]); actual["order_flow_mode"]="OHLCV_PROXY"
    with pytest.raises(AbsorptionDataError): CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(actual)


def test_log_return_first_row_symmetry_and_nonpositive():
    df=_actual([100,110,100,0,-1],[1]*5,[0]*5)
    out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(df)
    assert math.isnan(out.signed_return.iloc[0])
    up=out.signed_return.iloc[1]; down=out.signed_return.iloc[2]
    assert up == -down
    assert math.isnan(out.signed_return.iloc[3]) and math.isnan(out.signed_return.iloc[4])


def test_actual_alignment_opposition_zero_and_no_flow():
    df=_actual([100,110,100,100,100],[10,10,10,5,0],[0,0,0,5,0])
    out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(df)
    assert out.aggression_response_alignment.iloc[1] > 0
    assert out.aligned_response_magnitude.iloc[1] > 0
    assert out.opposed_response_magnitude.iloc[2] > 0
    assert math.isnan(out.aggression_response_alignment.iloc[3])
    assert math.isnan(out.aggression_response_alignment.iloc[4])


def test_read_before_push_and_absorption_product_exact():
    df=_actual([100,110,110],[10,10,10],[0,0,0])
    out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(df)
    assert math.isnan(out.return_magnitude_percentile.iloc[1])
    assert out.return_magnitude_history_count.tolist()==[0,0,1]
    assert math.isnan(out.aligned_response_percentile.iloc[1])
    assert out.aligned_response_percentile.iloc[2]==0.0
    assert out.opposed_response_percentile.iloc[2]==0.5
    assert out.aggression_extremeness.iloc[2]==0.5
    assert out.response_weakness.iloc[2]==1.0
    assert out.actual_absorption_evidence.iloc[2]==0.5
    assert out.absorbed_aggression_side.iloc[2]=="BUY"


def test_sell_absorption_side_and_opposed_preserved():
    weak=_actual([100,90,90],[0,0,0],[10,10,10])
    out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(weak)
    assert out.absorbed_aggression_side.iloc[2]=="SELL"
    opposed=_actual([100,110],[0,0],[10,10])
    o=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(opposed)
    assert o.pressure_side.iloc[0] if False else o.opposed_response_magnitude.iloc[1] > 0


def test_absorption_vs_active_opposition_decomposition():
    # Same strong BUY aggression: row 2 stalls, row 3 moves strongly against it.
    out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(
        _actual([100,110,110,90],[10,10,10,10],[0,0,0,0])
    )
    assert out.aligned_response_magnitude.iloc[2] == 0.0
    assert out.aligned_response_magnitude.iloc[3] == 0.0
    assert out.opposed_response_magnitude.iloc[2] == 0.0
    assert out.opposed_response_magnitude.iloc[3] > 0.0
    assert out.opposed_response_percentile.iloc[3] > out.opposed_response_percentile.iloc[2]
    assert math.isfinite(out.actual_absorption_evidence.iloc[2])
    assert math.isfinite(out.actual_absorption_evidence.iloc[3])


def test_absorption_nan_without_both_contexts():
    out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(_actual([100,101],[10,10],[0,0]))
    assert out.actual_absorption_evidence.isna().all()
    assert (out.absorbed_aggression_side=="NONE").all()


def test_actual_history_contract_adversarial_cases():
    engine=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR)

    finite_empty=_actual([100],[10],[0])
    finite_empty.loc[0,"delta_magnitude_percentile"]=0.5
    with pytest.raises(AbsorptionDataError,match="empty prior history"):
        engine.analyze(finite_empty)

    undefined=_actual([100],[0],[0])
    undefined.loc[0,"delta_magnitude_percentile"]=0.5
    with pytest.raises(AbsorptionDataError,match="undefined"):
        engine.analyze(undefined)

    base=_actual([100,101],[10,10],[0,0])
    for value in (0.5,-1.0,np.nan,np.inf,True):
        bad=base.copy(deep=True)
        if value is True:
            bad["delta_magnitude_history_count"]=pd.Series([False,True],dtype=bool)
        else:
            bad["delta_magnitude_history_count"]=pd.Series([0.0,value])
        with pytest.raises(AbsorptionDataError):
            engine.analyze(bad)

    inconsistent=base.copy(deep=True)
    inconsistent.loc[1,"delta_magnitude_history_count"]=0
    with pytest.raises(AbsorptionDataError,match="inconsistent"):
        engine.analyze(inconsistent)


def test_proxy_history_contract_adversarial_cases():
    engine=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.OHLCV_PROXY)
    base=_proxy([(5,10,0,8,100),(5,10,0,2,100)])
    bad=base.copy();bad.loc[1,"pressure_magnitude_history_count"]=0
    with pytest.raises(AbsorptionDataError,match="inconsistent"):
        engine.analyze(bad)
    missing=base.copy();missing.loc[0,"pressure_magnitude_percentile"]=0.5
    with pytest.raises(AbsorptionDataError,match="empty prior history"):
        engine.analyze(missing)


def test_actual_upstream_validation():
    valid=_actual([100,101],[10,10],[0,0])
    cases=[]
    x=valid.copy();x.loc[1,"delta_ratio"]=2;cases.append(x)
    x=valid.copy();x.loc[1,"delta_magnitude"]=0;cases.append(x)
    x=valid.copy();x.loc[1,"delta_magnitude_percentile"]=2;cases.append(x)
    x=valid.copy();x.loc[1,"total_classified_volume"]=0;cases.append(x)
    for case in cases:
        with pytest.raises(AbsorptionDataError): CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(case)


def test_proxy_real_integration_names_alignment_and_zero_volume():
    df=_proxy([(100,110,90,108,100),(108,112,100,110,100),(110,112,108,110,0)])
    out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(df)
    assert "actual_absorption_evidence" not in out.columns
    assert "proxy_absorption_evidence" in out.columns
    assert out.pressure_response_alignment.iloc[1] > 0
    assert math.isnan(out.pressure_response_alignment.iloc[2])
    assert out.pressure_side.iloc[2]=="NONE"


def test_proxy_opposition_and_surface_validation():
    df=_proxy([(100,110,90,108,100),(108,120,100,109,100)])
    out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(df)
    assert out.pressure_opposed_response_magnitude.iloc[1] > 0
    bad=df.copy();bad.loc[1,"pressure_magnitude"]=99
    with pytest.raises(AbsorptionDataError): CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(bad)


def test_same_bar_sequence_ambiguity_identical_aggregates():
    # Distinct hidden intrabar sequences with identical aggregate 3.1 surface
    # are intentionally indistinguishable to this bar-level engine.
    surface=_actual([100,101,101],[90,90,90],[10,10,10])
    a=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(surface)
    b=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(surface.copy())
    pd.testing.assert_frame_equal(a,b,check_exact=True)


def test_scaling_actual_prices_flow_and_proxy_volume():
    actual=_actual([100,110,110],[10,10,10],[0,0,0]); eng=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR)
    base=eng.analyze(actual)
    price=actual.copy();price["close"]*=8
    flow=_actual([100,110,110],[80,80,80],[0,0,0])
    for other in (eng.analyze(price),eng.analyze(flow)):
        for c in ("signed_return","aligned_response_percentile","actual_absorption_evidence"):
            pd.testing.assert_series_equal(base[c],other[c],check_exact=True)
    proxy=_proxy([(5,10,0,8,100),(8,10,0,8,200)])
    pbase=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(proxy)
    proxy2=_proxy([(5,10,0,8,800),(8,10,0,8,1600)])
    p2=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(proxy2)
    pd.testing.assert_series_equal(pbase.proxy_absorption_evidence,p2.proxy_absorption_evidence,check_exact=True)


def test_future_mutation_append_and_immutability():
    df=_actual([100,101,102,103],[7,2,9,1],[3,8,1,9]);before=df.copy(deep=True)
    eng=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR);full=eng.analyze(df)
    pd.testing.assert_frame_equal(df,before,check_exact=True)
    mut=df.copy();mut.loc[3,"close"]=1000;mut.loc[3,"delta_ratio"]=-1;mut.loc[3,"delta_magnitude"]=1
    pd.testing.assert_frame_equal(full.iloc[:3],eng.analyze(mut).iloc[:3],check_exact=True)
    app=_actual([100,101,102,103,10000],[7,2,9,1,10],[3,8,1,9,0])
    pd.testing.assert_frame_equal(full,eng.analyze(app).iloc[:len(df)],check_exact=True)


def test_module01_audits_both_modes():
    aa=_actual([100,101,102,101,103,103],[7,2,9,1,5,8],[3,8,1,9,5,2]);ab=_actual([200,199,201,202,201,203],[1,4,8,2,7,3],[9,6,2,8,3,7])
    pa=_proxy([(5,10,0,c,100) for c in [8,2,5,9,1,6]]);pb=_proxy([(5,10,0,c,200) for c in [1,3,7,4,9,2]])
    for factory,a,b in ((_ActualAbsorptionAuditEngine,aa,ab),(_ProxyAbsorptionAuditEngine,pa,pb)):
        tr=verify_truncation_invariance(factory,a,split_fractions=(),additional_split_points=[1,2,3,4,5]);assert all(x.passed for x in tr)
        st=verify_state_isolation(factory,a,b,policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT);assert st.passed


def test_empty_one_index_columns_collisions():
    empty_actual=_actual([],[],[]).astype(float);out=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(empty_actual);assert out.empty
    one=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(_actual([100],[0],[0]));assert math.isnan(one.signed_return.iloc[0])
    dup=_actual([100,101],[1,1],[1,1]);dup.index=[1,1]
    with pytest.raises(AbsorptionDataError): CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(dup)
    unordered=_actual([100,101],[1,1],[1,1]);unordered.index=[2,1]
    with pytest.raises(AbsorptionDataError): CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(unordered)
    collision=_actual([100],[1],[1]);collision["signed_return"]=0
    with pytest.raises(AbsorptionDataError): CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(collision)


def test_source_guard():
    source=inspect.getsource(__import__("trading_system.orderflow.absorption",fromlist=["*"]))
    for token in ("shift(-1","center=True","rolling(","volume moving average","VPIN formula","CVD"):
        assert token not in source
    assert re.search(r"fixed (delta|return) threshold",source,re.I) is None

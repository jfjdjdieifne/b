"""Tests for Module 6.2A-4 V1 Stage 4A: Shared Per-Bar Market-State Trajectory.

Covers the required adversarial matrix: shared-surface identity, reconstruction equivalence,
complete public-result mutation detection, prefix invariance, hypothesis projection (no row
duplication), information time, source fidelity (PROXY only, ACTUAL rejected), config binding,
numeric/schema, firewall, and Stage 3 boundary integration.
"""

from __future__ import annotations

import dataclasses
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_system.research.information_time import (
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.trajectory.trajectory_contract import (
    MarketObservationTimeline,
    TrajectoryContractError,
    TrajectoryDataError,
)
from trading_system.research.trajectory import trajectory_stage4a as s4a
from trading_system.research.trajectory.trajectory_stage4a import (
    Stage4ADomainSurface,
    Stage4APrefixBinding,
)
from trading_system.environment.session_context import SessionDefinition
from trading_system.orderflow.volume_delta import OrderFlowMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _market(n=12, timeline_id="s4a"):
    idx = pd.RangeIndex(n)
    close = [99.0 + i for i in range(n)]
    open_ = [99.0 + i for i in range(n)]
    high = [max(o, c) + 1.0 for o, c in zip(open_, close)]
    low = [min(o, c) - 1.0 for o, c in zip(open_, close)]
    volume = [1000.0 + i for i in range(n)]
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
        dtype=float,
    )


def _sealed(n=12, timeline_id="s4a"):
    market = _market(n, timeline_id)
    adapter = PositionalTimelineAdapter(timeline_id)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    return market, adapter, timeline


def _time_sealed(n=12, timeline_id="s4a_t", tz="UTC", freq="h", start="2026-03-07 12:00"):
    idx = pd.date_range(start, periods=n, freq=freq, tz=tz)
    market = _market(n, timeline_id)
    market.index = idx
    adapter = TimeIndexedTimelineAdapter(timeline_id)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    return market, adapter, timeline


def _key(adapter, market, position, phase=InformationPhase.COMPLETED_ROW_AVAILABLE, seq=0):
    return adapter.key_for_position(market.index, position, phase, seq)


def _london():
    return SessionDefinition(name="London", timezone="Europe/London", start_local=time(8, 0), end_local=time(9, 0))


# ---------------------------------------------------------------------------
# GENERAL
# ---------------------------------------------------------------------------

def test_same_inputs_same_surface_identity():
    market, adapter, timeline = _sealed(timeline_id="g_same")
    a = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    b = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert a.surface_id == b.surface_id
    assert a.public_result_hash == b.public_result_hash
    # determinism across fresh instance
    c = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market.copy(deep=True))
    assert a.surface_id == c.surface_id


def test_changed_config_changes_reconstruction_binding():
    market, adapter, timeline = _sealed(timeline_id="g_cfg")
    a = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    b = s4a.build_volatility_surface(
        timeline=timeline, adapter=adapter, market_history=market, high_col="high", low_col="low", close_col="close"
    )
    # same explicit config -> same identity
    assert a.surface_id == b.surface_id
    # different column config -> different config binding
    alt = s4a.build_volatility_surface(
        timeline=timeline, adapter=adapter, market_history=market, high_col="high", low_col="low", close_col="open"
    )
    assert a.configuration_binding_hash != alt.configuration_binding_hash


def test_supplied_vs_reconstructed_mismatch_rejected():
    market, adapter, timeline = _sealed(timeline_id="g_mismatch")
    supplied = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    authoritative = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    s4a.verify_surface_matches_reconstruction(supplied, authoritative)  # ok

    # forge a surface with tampered public result hash (stale identity) -> integrity rejects
    forged = dataclasses.replace(supplied, public_result_hash="0" * 64)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_matches_reconstruction(forged, authoritative)


def test_public_result_mutation_detected():
    market, adapter, timeline = _sealed(timeline_id="g_mut")
    supplied = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # mutate a factual value inside the surface frame, rebuild the identity from the mutated frame
    tampered_frame = supplied.surface.copy(deep=True)
    tampered_frame.iloc[0, tampered_frame.columns.get_loc("true_range")] = 9999.0
    tampered_output = tampered_frame.loc[:, list(supplied.output_columns)]
    new_hash = s4a._surface_public_result_hash(tampered_output)
    assert new_hash != supplied.public_result_hash


def test_future_append_prefix_invariance():
    market, adapter, timeline = _sealed(n=12, timeline_id="g_append")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    k5 = _key(adapter, market, 5)
    p_before = s4a.project_surface_prefix(surface=surf, boundary_key=k5)

    # extend market by 3 bars -> new timeline + surface (full identity changes)
    market2 = _market(15, "g_append")
    adapter2 = PositionalTimelineAdapter("g_append")
    timeline2 = MarketObservationTimeline.seal(adapter=adapter2, market_history=market2)
    surf2 = s4a.build_volatility_surface(timeline=timeline2, adapter=adapter2, market_history=market2)
    assert surf2.surface_id != surf.surface_id  # full surface identity changed

    # prefix through 5 must be identical
    k5_2 = _key(adapter2, market2, 5)
    p_after = s4a.project_surface_prefix(surface=surf2, boundary_key=k5_2)
    assert p_after.prefix_hash == p_before.prefix_hash


def test_future_mutation_after_T_rejected_by_integrity():
    market, adapter, timeline = _sealed(n=12, timeline_id="g_futuremut")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # mutate a bar strictly after T (bar 8) in the surface frame -> whole-surface integrity broken
    mutated = surf.surface.copy(deep=True)
    mutated.iloc[8, mutated.columns.get_loc("true_range")] = 12345.0
    mutated_surf = dataclasses.replace(surf, surface=mutated)
    # re-projecting the corrupted surface must REJECT (self-integrity), not produce a stale prefix
    k5 = _key(adapter, market, 5)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.project_surface_prefix(surface=mutated_surf, boundary_key=k5)


def test_historical_projection_immutable():
    market, adapter, timeline = _sealed(n=12, timeline_id="g_histimm")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    k5 = _key(adapter, market, 5)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=k5)
    # the prefix binding object is frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.prefix_hash = "mutated"  # type: ignore[misc]


def test_shared_surface_reused_by_two_hypotheses():
    market, adapter, timeline = _sealed(n=12, timeline_id="g_shared")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # two different hypotheses project the SAME surface object (no recompute, no copy)
    h0_key = _key(adapter, market, 4)
    h1_key = _key(adapter, market, 8)
    p0 = s4a.project_surface_prefix(surface=surf, boundary_key=h0_key)
    p1 = s4a.project_surface_prefix(surface=surf, boundary_key=h1_key)
    assert p0.surface_id == p1.surface_id == surf.surface_id
    assert p0.prefix_hash != p1.prefix_hash  # different boundaries


def test_no_duplicated_surface_rows_per_hypothesis():
    market, adapter, timeline = _sealed(n=12, timeline_id="g_nodup")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=_key(adapter, market, 5))
    # the prefix binding carries NO DataFrame rows
    for f in dataclasses.fields(p):
        assert not isinstance(getattr(p, f.name), pd.DataFrame), f"{f.name} must not be a DataFrame"


def test_cross_timeline_rejection():
    market, adapter, timeline = _sealed(n=12, timeline_id="g_cross")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    other_key = _key(PositionalTimelineAdapter("other"), market, 5)
    with pytest.raises(TrajectoryDataError, match="wrong timeline"):
        s4a.project_surface_prefix(surface=surf, boundary_key=other_key)


def test_caller_input_immutability():
    market, adapter, timeline = _sealed(n=12, timeline_id="g_immut")
    before = market.copy(deep=True)
    s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    pd.testing.assert_frame_equal(market, before)


def test_no_hidden_cache():
    market, adapter, timeline = _sealed(n=12, timeline_id="g_cache")
    a1 = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    other_market, other_adapter, other_timeline = _sealed(n=12, timeline_id="g_cache_other")
    b = s4a.build_volatility_surface(timeline=other_timeline, adapter=other_adapter, market_history=other_market)
    a2 = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert a1.surface_id == a2.surface_id
    assert a1.surface_id != b.surface_id


# ---------------------------------------------------------------------------
# VOLATILITY
# ---------------------------------------------------------------------------

def test_volatility_first_bar_insufficient_history_missing():
    market, adapter, timeline = _sealed(n=12, timeline_id="v_first")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    out = surf.surface
    # first bar: normalized_true_range is NaN (no prior close) -> insufficient history, not UNAVAILABLE
    assert pd.isna(out.loc[0, "normalized_true_range"])
    # true_range at first bar is defined (high-low)
    assert out.loc[0, "true_range"] == pytest.approx(market.loc[0, "high"] - market.loc[0, "low"])
    # percentile is NaN with empty prior history
    assert pd.isna(out.loc[0, "true_range_percentile"])


def test_volatility_causal_percentile_prefix_invariance():
    market, adapter, timeline = _sealed(n=12, timeline_id="v_pct")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # recompute on a truncated prefix -> percentile at a bar equals the full-surface value
    truncated = market.iloc[:8]
    adapter_t = PositionalTimelineAdapter("v_pct")
    timeline_t = MarketObservationTimeline.seal(adapter=adapter_t, market_history=truncated)
    surf_t = s4a.build_volatility_surface(timeline=timeline_t, adapter=adapter_t, market_history=truncated)
    for i in range(8):
        assert surf.surface.loc[i, "true_range_percentile"] == pytest.approx(
            surf_t.surface.loc[i, "true_range_percentile"], nan_ok=True
        )


def test_volatility_no_future_fitting():
    market, adapter, timeline = _sealed(n=12, timeline_id="v_nofuture")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # no output may depend on rows beyond the bar: the legal way to prove prefix causality is to
    # rebuild from a truncated authoritative prefix, not to mutate a certified surface.
    truncated = market.iloc[:8]
    adapter_t = PositionalTimelineAdapter("v_nofuture")
    timeline_t = MarketObservationTimeline.seal(adapter=adapter_t, market_history=truncated)
    surf_t = s4a.build_volatility_surface(timeline=timeline_t, adapter=adapter_t, market_history=truncated)
    for i in range(8):
        assert surf.surface.loc[i, "true_range"] == pytest.approx(surf_t.surface.loc[i, "true_range"])
    # a mutated surface (bar 10 changed) is rejected by self-integrity on re-projection
    mutated = surf.surface.copy(deep=True)
    mutated.iloc[10, mutated.columns.get_loc("true_range")] = 99999.0
    mutated_surf = dataclasses.replace(surf, surface=mutated)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.project_surface_prefix(surface=mutated_surf, boundary_key=_key(adapter, market, 5))


def test_volatility_high_low_rejection():
    market = _market(4, "v_bad")
    market.loc[1, "high"] = market.loc[1, "low"] - 1.0
    adapter = PositionalTimelineAdapter("v_bad")
    # seal already rejects high < low
    with pytest.raises(TrajectoryDataError):
        MarketObservationTimeline.seal(adapter=adapter, market_history=market)


def test_volatility_nan_inf_rejection():
    market = _market(4, "v_nan")
    market.loc[2, "close"] = np.nan
    adapter = PositionalTimelineAdapter("v_nan")
    with pytest.raises(TrajectoryDataError):
        MarketObservationTimeline.seal(adapter=adapter, market_history=market)


# ---------------------------------------------------------------------------
# SESSION
# ---------------------------------------------------------------------------

def test_session_ordered_config_identity():
    market, adapter, timeline = _time_sealed(n=12, timeline_id="s_cfg")
    a = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market, sessions=(_london(),))
    b = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market, sessions=(_london(),))
    assert a.surface_id == b.surface_id
    # different timezone -> different config binding
    ny = SessionDefinition(name="NewYork", timezone="America/New_York", start_local=time(9, 30), end_local=time(10, 0))
    c = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market, sessions=(ny,))
    assert a.configuration_binding_hash != c.configuration_binding_hash


def test_session_empty_config_valid():
    market, adapter, timeline = _time_sealed(n=12, timeline_id="s_empty")
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market)
    out = surf.surface
    assert "active_session_count" in out.columns
    assert (out["active_session_count"] == 0).all()
    # only base calendar columns (no session_* active)
    assert not any(c.startswith("session_") for c in surf.output_columns)


def test_session_timezone_aware_enforcement():
    # naive index rejected by the timeline seal
    idx = pd.date_range("2026-03-07 12:00", periods=12, freq="h")  # tz-naive
    market = _market(12, "s_naive")
    market.index = idx
    adapter = TimeIndexedTimelineAdapter("s_naive")
    from trading_system.research.information_time import TimelineAdapterError
    with pytest.raises(TimelineAdapterError):
        MarketObservationTimeline.seal(adapter=adapter, market_history=market)


def test_session_dst_utc():
    # America/New_York crosses DST on 2026-03-08; UTC timestamps become irregular
    market, adapter, timeline = _time_sealed(n=12, timeline_id="s_dst", tz="America/New_York", start="2026-03-07 12:00")
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market, sessions=(_london(),))
    assert surf.surface_id  # builds without error
    # calendar features are finite
    for c in ("hour_utc_sin", "hour_utc_cos", "weekday_sin", "weekday_cos"):
        assert np.isfinite(surf.surface[c].to_numpy()).all()


def test_session_irregular_timestamps():
    idx = pd.DatetimeIndex(
        ["2026-03-07 08:00", "2026-03-07 08:37", "2026-03-07 09:00", "2026-03-07 14:00"],
        tz="UTC",
    )
    market = _market(4, "s_irr")
    market.index = idx
    adapter = TimeIndexedTimelineAdapter("s_irr")
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market, sessions=(_london(),))
    assert surf.surface_id


def test_session_duplicate_names_rejected():
    market, adapter, timeline = _time_sealed(n=12, timeline_id="s_dup")
    from trading_system.environment.session_context import CausalSessionContextEngine, SessionConfigError
    # two distinct names normalizing to the same output key (lowercase) collide
    s1 = SessionDefinition(name="London", timezone="Europe/London", start_local=time(8, 0), end_local=time(9, 0))
    s2 = SessionDefinition(name="LONDON", timezone="Europe/London", start_local=time(10, 0), end_local=time(11, 0))
    with pytest.raises(SessionConfigError):
        CausalSessionContextEngine((s1, s2))


# ---------------------------------------------------------------------------
# ORDER FLOW PROXY
# ---------------------------------------------------------------------------

def test_order_flow_proxy_mode_supported():
    market, adapter, timeline = _sealed(n=12, timeline_id="f_proxy")
    surf = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert surf.domain == "ORDER_FLOW_PROXY"
    assert "close_location_proxy" in surf.output_columns
    assert "order_flow_mode" in surf.output_columns
    assert (surf.surface["order_flow_mode"] == "OHLCV_PROXY").all()


def test_order_flow_actual_rejected_no_fallback():
    market, adapter, timeline = _sealed(n=12, timeline_id="f_actual")
    with pytest.raises(TrajectoryDataError, match="NOT_SUPPORTED_BY_STAGE4A_V1_SOURCE_CONTRACT"):
        s4a.build_order_flow_proxy_surface(
            timeline=timeline, adapter=adapter, market_history=market, mode=OrderFlowMode.ACTUAL_AGGRESSOR
        )


def test_order_flow_ohlcv_mutation_changes_binding():
    market, adapter, timeline = _sealed(n=12, timeline_id="f_mut")
    a = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    mutated = market.copy(deep=True)
    mutated.loc[3, "volume"] += 500.0
    adapter2 = PositionalTimelineAdapter("f_mut")
    timeline2 = MarketObservationTimeline.seal(adapter=adapter2, market_history=mutated)
    b = s4a.build_order_flow_proxy_surface(timeline=timeline2, adapter=adapter2, market_history=mutated)
    assert a.surface_id != b.surface_id


def test_order_flow_complete_public_result_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="f_pubmut")
    supplied = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    authoritative = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    tampered = dataclasses.replace(
        supplied,
        surface=supplied.surface.copy(deep=True),
    )
    tampered.surface.iloc[2, tampered.surface.columns.get_loc("close_location_proxy")] = 0.5
    # recompute hash from tampered output -> differs
    new_hash = s4a._surface_public_result_hash(
        tampered.surface.loc[:, list(tampered.output_columns)]
    )
    assert new_hash != authoritative.public_result_hash


def test_order_flow_volume_negative_rejected():
    market = _market(6, "f_negvol")
    market.loc[2, "volume"] = -5.0
    adapter = PositionalTimelineAdapter("f_negvol")
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    with pytest.raises(TrajectoryDataError, match="volume-delta"):
        s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)


def test_order_flow_geometry_rejection():
    market = _market(6, "f_geom")
    market.loc[2, "close"] = market.loc[2, "high"] + 10.0
    adapter = PositionalTimelineAdapter("f_geom")
    # seal rejects close > high
    with pytest.raises(TrajectoryDataError):
        MarketObservationTimeline.seal(adapter=adapter, market_history=market)


# ---------------------------------------------------------------------------
# ABSORPTION PROXY
# ---------------------------------------------------------------------------

def test_absorption_binds_upstream_surface():
    market, adapter, timeline = _sealed(n=12, timeline_id="a_upstream")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    abs_s = s4a.build_absorption_proxy_surface(
        timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=flow
    )
    assert abs_s.upstream_surface_hash == flow.surface_id
    assert "proxy_absorption_evidence" in abs_s.output_columns


def test_absorption_upstream_mutation_changes_identity():
    market, adapter, timeline = _sealed(n=12, timeline_id="a_upmut")
    flow_a = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    abs_a = s4a.build_absorption_proxy_surface(
        timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=flow_a
    )
    # mutate market -> new flow surface -> new absorption identity
    mutated = market.copy(deep=True)
    mutated.loc[4, "close"] += 2.0
    mutated.loc[4, "high"] = max(mutated.loc[4, "high"], mutated.loc[4, "close"])
    adapter2 = PositionalTimelineAdapter("a_upmut")
    timeline2 = MarketObservationTimeline.seal(adapter=adapter2, market_history=mutated)
    flow_b = s4a.build_order_flow_proxy_surface(timeline=timeline2, adapter=adapter2, market_history=mutated)
    abs_b = s4a.build_absorption_proxy_surface(
        timeline=timeline2, adapter=adapter2, market_history=mutated, order_flow_surface=flow_b
    )
    assert abs_a.surface_id != abs_b.surface_id


def test_absorption_upstream_timeline_mismatch_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="a_tlmismatch")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    other_market, other_adapter, other_timeline = _sealed(n=12, timeline_id="a_other")
    with pytest.raises(TrajectoryDataError, match="timeline mismatch"):
        s4a.build_absorption_proxy_surface(
            timeline=other_timeline, adapter=other_adapter, market_history=other_market, order_flow_surface=flow
        )


def test_absorption_requires_proxy_upstream():
    market, adapter, timeline = _sealed(n=12, timeline_id="a_notflow")
    # pass a volatility surface (wrong domain) as upstream
    vol = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    with pytest.raises(TrajectoryDataError, match="ORDER_FLOW_PROXY"):
        s4a.build_absorption_proxy_surface(
            timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=vol
        )


def test_absorption_actual_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="a_actual")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    with pytest.raises(TrajectoryDataError, match="NOT_SUPPORTED_BY_STAGE4A_V1_SOURCE_CONTRACT"):
        s4a.build_absorption_proxy_surface(
            timeline=timeline, adapter=adapter, market_history=market,
            order_flow_surface=flow, mode=OrderFlowMode.ACTUAL_AGGRESSOR,
        )


def test_absorption_same_bar_response_no_future():
    market, adapter, timeline = _sealed(n=12, timeline_id="a_samebar")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    abs_s = s4a.build_absorption_proxy_surface(
        timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=flow
    )
    # signed_return at bar 0 is NaN (no prior close); response only pairs same-bar flow x return
    assert pd.isna(abs_s.surface.loc[0, "signed_return"])


def test_absorption_complete_public_result_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="a_pubmut")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    supplied = s4a.build_absorption_proxy_surface(
        timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=flow
    )
    authoritative = s4a.build_absorption_proxy_surface(
        timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=flow
    )
    tampered = supplied.surface.copy(deep=True)
    tampered.iloc[3, tampered.columns.get_loc("proxy_absorption_evidence")] = 0.99
    new_hash = s4a._surface_public_result_hash(tampered.loc[:, list(supplied.output_columns)])
    assert new_hash != authoritative.public_result_hash


# ---------------------------------------------------------------------------
# STAGE 3 BOUNDARY
# ---------------------------------------------------------------------------

def test_projection_boundary_limits_prefix():
    market, adapter, timeline = _sealed(n=12, timeline_id="b_bound")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # terminal T=4 (mature) -> prefix ends at 4
    k4 = _key(adapter, market, 4)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=k4)
    assert p.prefix_row_count == 5  # bars 0..4
    assert p.boundary_position == 4
    # a different boundary at T=8 yields a different (longer) prefix
    p8 = s4a.project_surface_prefix(surface=surf, boundary_key=_key(adapter, market, 8))
    assert p8.prefix_row_count == 9
    assert p.prefix_hash != p8.prefix_hash


def test_no_post_boundary_fact_in_projection():
    market, adapter, timeline = _sealed(n=12, timeline_id="b_nopost")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    k4 = _key(adapter, market, 4)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=k4)
    # prefix hash is computed only over rows <= 4; verify by comparing against a manual subset
    subset = surf.surface.loc[:, list(surf.output_columns)].iloc[:5]
    manual = s4a._prefix_hash(subset)
    assert p.prefix_hash == manual


def test_future_extension_does_not_alter_prior_prefix():
    # already covered in test_future_append_prefix_invariance; assert once more across domains
    market, adapter, timeline = _sealed(n=12, timeline_id="b_ext")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    k5 = _key(adapter, market, 5)
    p_before = s4a.project_surface_prefix(surface=flow, boundary_key=k5)
    market2 = _market(15, "b_ext")
    adapter2 = PositionalTimelineAdapter("b_ext")
    timeline2 = MarketObservationTimeline.seal(adapter=adapter2, market_history=market2)
    flow2 = s4a.build_order_flow_proxy_surface(timeline=timeline2, adapter=adapter2, market_history=market2)
    p_after = s4a.project_surface_prefix(surface=flow2, boundary_key=_key(adapter2, market2, 5))
    assert p_after.prefix_hash == p_before.prefix_hash


# ---------------------------------------------------------------------------
# NUMERIC / SCHEMA
# ---------------------------------------------------------------------------

def test_duplicate_columns_rejected():
    market = _market(6, "n_dup")
    market["close_dup"] = market["close"]
    market = market.rename(columns={"close_dup": "close"})
    adapter = PositionalTimelineAdapter("n_dup")
    with pytest.raises(TrajectoryDataError, match="duplicate"):
        MarketObservationTimeline.seal(adapter=adapter, market_history=market)


def test_wrong_dtype_rejected():
    market = _market(6, "n_dtype")
    market["close"] = market["close"].astype(str)
    adapter = PositionalTimelineAdapter("n_dtype")
    with pytest.raises(TrajectoryDataError, match="numeric"):
        MarketObservationTimeline.seal(adapter=adapter, market_history=market)


# ---------------------------------------------------------------------------
# SELF-INTEGRITY (PATCH)
# ---------------------------------------------------------------------------

def _tamper(surface, row, col, value):
    """Return a dataclasses.replace'd surface whose contained DataFrame was mutated at (row, col)."""
    frame = surface.surface.copy(deep=True)
    frame.iloc[row, frame.columns.get_loc(col)] = value
    return dataclasses.replace(surface, surface=frame)


def test_integrity_volatility_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="i_vol")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    s4a.verify_surface_integrity(surf)  # valid
    tampered = _tamper(surf, 3, "true_range", 12345.0)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_integrity(tampered)


def test_integrity_session_mutation_rejected():
    market, adapter, timeline = _time_sealed(n=12, timeline_id="i_sess")
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market, sessions=(_london(),))
    tampered = _tamper(surf, 2, "hour_utc_sin", 99.0)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_integrity(tampered)


def test_integrity_order_flow_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="i_flow")
    surf = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    tampered = _tamper(surf, 4, "close_location_proxy", 0.5)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_integrity(tampered)


def test_integrity_absorption_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="i_abs")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    surf = s4a.build_absorption_proxy_surface(timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=flow)
    tampered = _tamper(surf, 3, "proxy_absorption_evidence", 0.99)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_integrity(tampered)


def test_verify_function_supplied_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="vf_supplied")
    supplied = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    authoritative = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    tampered = _tamper(supplied, 1, "true_range", -1.0)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_matches_reconstruction(tampered, authoritative)


def test_verify_function_authoritative_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="vf_auth")
    supplied = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    authoritative = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    tampered_auth = _tamper(authoritative, 0, "true_range", -5.0)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_matches_reconstruction(supplied, tampered_auth)


def test_forged_output_columns_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="vf_forgecols")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # drop a factual column from output_columns (convenient subset) -> integrity rejects schema mismatch
    forged = dataclasses.replace(surf, output_columns=surf.output_columns[:-1])
    with pytest.raises(TrajectoryDataError, match="output_columns mismatch"):
        s4a.verify_surface_integrity(forged)


def test_forged_surface_id_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="vf_forgeid")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    forged = dataclasses.replace(surf, surface_id="0" * 64)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_integrity(forged)


def test_forged_public_result_hash_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="vf_forgehash")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    forged = dataclasses.replace(surf, public_result_hash="0" * 64)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.verify_surface_integrity(forged)


def test_absorption_upstream_mutation_rejected_before_consumption():
    market, adapter, timeline = _sealed(n=12, timeline_id="ab_upmut")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    tampered_flow = _tamper(flow, 2, "close_location_proxy", 0.5)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.build_absorption_proxy_surface(
            timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=tampered_flow
        )


def test_absorption_valid_upstream_accepted():
    market, adapter, timeline = _sealed(n=12, timeline_id="ab_valid")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    abs_s = s4a.build_absorption_proxy_surface(
        timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=flow
    )
    s4a.verify_surface_integrity(abs_s)


def test_prefix_row_le_t_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="pf_le")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    tampered = _tamper(surf, 2, "true_range", 12345.0)  # row 2 <= T=5
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.project_surface_prefix(surface=tampered, boundary_key=_key(adapter, market, 5))


def test_prefix_row_gt_t_mutation_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="pf_gt")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    tampered = _tamper(surf, 9, "true_range", 12345.0)  # row 9 > T=5
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.project_surface_prefix(surface=tampered, boundary_key=_key(adapter, market, 5))


def test_old_prefix_binding_unchanged_after_mutation_attempt():
    market, adapter, timeline = _sealed(n=12, timeline_id="pf_immut")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    k5 = _key(adapter, market, 5)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=k5)
    original_prefix_hash = p.prefix_hash
    # attempt mutation -> rejected; the already-created binding object is unchanged
    tampered = _tamper(surf, 3, "true_range", 12345.0)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4a.project_surface_prefix(surface=tampered, boundary_key=k5)
    assert p.prefix_hash == original_prefix_hash


def test_legal_prefix_invariance_via_new_surface():
    # legal future extension: build a NEW valid surface from authoritative future-extended history
    market, adapter, timeline = _sealed(n=12, timeline_id="pf_legal")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    k5 = _key(adapter, market, 5)
    p_before = s4a.project_surface_prefix(surface=surf, boundary_key=k5)

    market2 = _market(15, "pf_legal")
    adapter2 = PositionalTimelineAdapter("pf_legal")
    timeline2 = MarketObservationTimeline.seal(adapter=adapter2, market_history=market2)
    surf2 = s4a.build_volatility_surface(timeline=timeline2, adapter=adapter2, market_history=market2)
    p_after = s4a.project_surface_prefix(surface=surf2, boundary_key=_key(adapter2, market2, 5))
    assert p_after.prefix_hash == p_before.prefix_hash


def test_caller_market_history_mutation_does_not_alias_surface():
    market, adapter, timeline = _sealed(n=12, timeline_id="al_caller")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    hash_before = surf.public_result_hash
    # mutate caller-owned market_history after build
    market.iloc[3, market.columns.get_loc("close")] = 500.0
    # surface content unchanged (no aliasing)
    s4a.verify_surface_integrity(surf)
    assert surf.public_result_hash == hash_before


def test_absorption_does_not_alias_upstream_into_output():
    market, adapter, timeline = _sealed(n=12, timeline_id="al_abs")
    flow = s4a.build_order_flow_proxy_surface(timeline=timeline, adapter=adapter, market_history=market)
    abs_s = s4a.build_absorption_proxy_surface(
        timeline=timeline, adapter=adapter, market_history=market, order_flow_surface=flow
    )
    hash_before = abs_s.public_result_hash
    # mutate the upstream flow DataFrame after absorption construction
    flow.surface.iloc[2, flow.surface.columns.get_loc("close_location_proxy")] = 0.5
    # absorption surface content unchanged (no aliasing into stored factual output)
    s4a.verify_surface_integrity(abs_s)
    assert abs_s.public_result_hash == hash_before


# ---------------------------------------------------------------------------
# BOUNDARY INFORMATION-KEY LEGALITY (PATCH)
# ---------------------------------------------------------------------------

def test_boundary_bar_pre_close_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="bk_preclose")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = adapter.key_for_position(market.index, 5, InformationPhase.BAR_PRE_CLOSE, 0)
    with pytest.raises(TrajectoryContractError, match="not legally observable"):
        s4a.project_surface_prefix(surface=surf, boundary_key=k)


def test_boundary_completed_row_accepted():
    market, adapter, timeline = _sealed(n=12, timeline_id="bk_completed")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = adapter.key_for_position(market.index, 5, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=k)
    assert p.boundary_position == 5
    assert p.prefix_row_count == 6


def test_boundary_research_snapshot_accepted():
    market, adapter, timeline = _sealed(n=12, timeline_id="bk_research")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = adapter.key_for_position(market.index, 5, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, 0)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=k)
    assert p.boundary_position == 5


def test_boundary_positional_fabricated_timestamp_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="bk_pos_ts")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # positional key must NOT carry a timestamp (CLOSED PositionalTimelineAdapter.validate_key)
    from trading_system.research.information_time import INFORMATION_KEY_VERSION
    fabricated = InformationKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id="bk_pos_ts",
        bar_position=5,
        event_time_utc=pd.Timestamp("2026-03-07 12:00:00", tz="UTC"),
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=0,
    )
    with pytest.raises(TrajectoryDataError, match="timestamp"):
        s4a.project_surface_prefix(surface=surf, boundary_key=fabricated)


def test_boundary_timeindexed_wrong_event_time_utc_rejected():
    market, adapter, timeline = _time_sealed(n=12, timeline_id="bk_ti_wrongts")
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market)
    # correct position, wrong timestamp
    from trading_system.research.information_time import INFORMATION_KEY_VERSION
    wrong_ts = InformationKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id="bk_ti_wrongts",
        bar_position=5,
        event_time_utc=pd.Timestamp("1999-01-01 00:00:00", tz="UTC"),
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=0,
    )
    with pytest.raises(TrajectoryDataError, match="timestamp"):
        s4a.project_surface_prefix(surface=surf, boundary_key=wrong_ts)


def test_boundary_timeindexed_wrong_bar_position_rejected():
    market, adapter, timeline = _time_sealed(n=12, timeline_id="bk_ti_wrongpos")
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market)
    # correct timestamp (of bar 3) but wrong bar_position 5
    from trading_system.research.information_time import INFORMATION_KEY_VERSION
    real_ts = pd.Timestamp(market.index[3]).tz_convert("UTC")
    wrong_pos = InformationKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id="bk_ti_wrongpos",
        bar_position=5,
        event_time_utc=real_ts,
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=0,
    )
    with pytest.raises(TrajectoryDataError, match="timestamp"):
        s4a.project_surface_prefix(surface=surf, boundary_key=wrong_pos)


def test_boundary_timeindexed_wrong_timeline_rejected():
    market, adapter, timeline = _time_sealed(n=12, timeline_id="bk_ti_tl")
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market)
    other = TimeIndexedTimelineAdapter("bk_ti_other")
    k = other.key_for_position(market.index, 5, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    with pytest.raises(TrajectoryDataError, match="wrong timeline"):
        s4a.project_surface_prefix(surface=surf, boundary_key=k)


def test_boundary_timeindexed_dst_authoritative_accepted():
    market, adapter, timeline = _time_sealed(n=12, timeline_id="bk_dst", tz="America/New_York", start="2026-03-07 12:00")
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market)
    # derive authoritative key across the DST boundary (bar 10 is after 2026-03-08 02:00 EST->EDT)
    k = adapter.key_for_position(market.index, 10, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=k)
    assert p.boundary_position == 10


def test_boundary_timeindexed_irregular_accepted():
    idx = pd.DatetimeIndex(
        ["2026-03-07 08:00", "2026-03-07 08:37", "2026-03-07 09:00", "2026-03-07 14:00"],
        tz="UTC",
    )
    market = _market(4, "bk_irr")
    market.index = idx
    adapter = TimeIndexedTimelineAdapter("bk_irr")
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    surf = s4a.build_session_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = adapter.key_for_position(market.index, 2, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    p = s4a.project_surface_prefix(surface=surf, boundary_key=k)
    assert p.boundary_position == 2


def test_boundary_positional_cross_timeline_rejected():
    market, adapter, timeline = _sealed(n=12, timeline_id="bk_pos_cross")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    other = PositionalTimelineAdapter("bk_pos_other")
    k = other.key_for_position(market.index, 5, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    with pytest.raises(TrajectoryDataError, match="wrong timeline"):
        s4a.project_surface_prefix(surface=surf, boundary_key=k)


def test_adapter_kind_part_of_surface_identity():
    market, adapter, timeline = _sealed(n=12, timeline_id="bk_kind")
    surf = s4a.build_volatility_surface(timeline=timeline, adapter=adapter, market_history=market)
    # changing adapter_kind breaks surface identity (self-integrity rejects)
    from trading_system.research.trajectory.trajectory_contract import TIMELINE_ADAPTER_KIND
    forged = dataclasses.replace(surf, adapter_kind=TIMELINE_ADAPTER_KIND.TIME_INDEXED)
    with pytest.raises(TrajectoryDataError):
        s4a.verify_surface_integrity(forged)


# ---------------------------------------------------------------------------
# FIREWALL / OUT OF SCOPE
# ---------------------------------------------------------------------------

def test_firewall_live_modules_do_not_import_stage4a():
    live_roots = [
        Path("src/trading_system/structure"),
        Path("src/trading_system/zones"),
        Path("src/trading_system/liquidity"),
        Path("src/trading_system/orderflow"),
        Path("src/trading_system/multitimeframe"),
        Path("src/trading_system/decision"),
        Path("src/trading_system/core"),
        Path("src/trading_system/environment"),
    ]
    forbidden = ["trajectory_stage4a", "research.trajectory"]
    for root in live_roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for forb in forbidden:
                assert forb not in content, f"Firewall violation: {py_file} imports {forb}"


def test_stage4a_no_out_of_scope_implementations():
    path = Path("src/trading_system/research/trajectory/trajectory_stage4a.py")
    content = path.read_text(encoding="utf-8", errors="ignore")
    forbidden = [
        "def build_liquidity",
        "def build_ob",
        "def build_fvg",
        "def build_dealing_range",
        "def build_htf",
        "def build_mtf",
        "def build_descriptor",
        "def build_estimand",
        "def build_model",
        "def build_scorer",
        "def build_geometry",
        "def build_execution",
        "class Liquidity",
        "class OrderBlock",
        "class FVG",
    ]
    for forb in forbidden:
        assert forb not in content, f"forbidden out-of-scope marker present: {forb}"


def test_stage4a_manifest_declares_out_of_scope_and_open_debts():
    manifest = s4a.trajectory_stage4a_manifest()
    assert s4a.TRAJECTORY_STAGE4A_CONTRACT_VERSION == "CAUSAL_SHARED_PER_BAR_MARKET_STATE_TRAJECTORY_V1"
    vals = dict(zip(manifest["name"], manifest["value"]))
    assert vals["ACTUAL_AGGRESSOR"].startswith("NOT_SUPPORTED")
    assert vals["WIN_LOSS"] == "FORBIDDEN"
    for d in ("RESEARCH-DEBT-020", "RESEARCH-DEBT-021", "RESEARCH-DEBT-022", "RESEARCH-DEBT-023", "RESEARCH-DEBT-024", "RESEARCH-DEBT-025"):
        assert vals.get(d) == "OPEN"

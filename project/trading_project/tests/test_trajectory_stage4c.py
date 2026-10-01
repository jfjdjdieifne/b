"""Tests for Module 6.2A-4 V1 Stage 4C-1: shared causal HTF raw observation surfaces.

Adversarial coverage: pre-close leakage, exact boundary + phase, in-progress bucket
concealment (spike), feed-gap projectability vs theoretical close, every cadence-grid
coverage status, future-append prefix invariance, timezone/DST equivalence, cross-timeline
rejection, POSITIONAL rejection, tampering/coherent rehash, scale/duration substitution,
whole-frame schema injection (middle and tail), malicious CLOSED-engine schema drift,
volume invariance, Contract-vs-Data error taxonomy, semantic-inflation guard, out-of-scope
guards (no structure/transitions/confluence/policy/model/trade semantics), a CLOSED 5.2
unavailable-scale contract guard (test-only; no 4C-2 production), and non-vacuity proofs.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_system.multitimeframe.causal_htf import CausalHTFAggregator
from trading_system.multitimeframe.confluence_matrix import (
    CausalConfluenceMatrixEngine,
    ScaleFrame,
    causal_asof_align_scale_state,
)
from trading_system.research.information_time import (
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.trajectory.trajectory_contract import (
    MarketObservationTimeline,
    TrajectoryContractError,
    TrajectoryDataError,
)
from trading_system.research.trajectory import trajectory_stage4c as s4c

SRC_PATH = Path("src/trading_system/research/trajectory/trajectory_stage4c.py")
SCALE = "m5"
DUR = pd.Timedelta(minutes=5)
EPOCH = pd.Timestamp("2024-01-01 00:00", tz="UTC")
CAD = s4c.CadenceGridContract(EPOCH, pd.Timedelta(minutes=1))


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _ohlc(closes, opens=None, highs=None, lows=None, index=None):
    closes = np.asarray(closes, dtype=float)
    opens = closes if opens is None else np.asarray(opens, dtype=float)
    highs = highs if highs is not None else np.maximum(opens, closes) + 0.2
    lows = lows if lows is not None else np.minimum(opens, closes) - 0.2
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes}, index=index)


def _regular_market(start="2024-01-01 08:01", periods=31, freq="1min", seed=3, volume=False):
    """Continuous 1-min LTF bars; 5-min buckets ending :05,:10,... are FULL on the 1-min grid;
    the last (in-progress) bucket ending after the final bar is invisible."""
    idx = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    rng = np.random.default_rng(seed)
    closes = 100.0 + np.cumsum(rng.normal(0, 0.4, periods))
    frame = _ohlc(closes, index=idx)
    if volume:
        frame["volume"] = np.full(periods, 10.0)
    return frame


def _sealed(market, tid="t4c"):
    adapter = TimeIndexedTimelineAdapter(tid)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    return adapter, timeline


def _surface(market, tid="t4c", cadence=CAD, name=SCALE, duration=DUR):
    adapter, timeline = _sealed(market, tid)
    return s4c.build_htf_scale_surface(
        timeline=timeline,
        adapter=adapter,
        market_history=market,
        scale_spec=s4c.HtfScaleSpec(name, duration),
        cadence=cadence,
    ), adapter, timeline


def _key(adapter, index, position, phase=InformationPhase.COMPLETED_ROW_AVAILABLE, seq=0):
    return adapter.key_for_position(index, position, phase, seq)


def _gap_market():
    """Bars 08:11/12/13/15/16 removed; 08:14 stays inside (08:10,08:15]; the close row 08:15
    is missing so the bucket ending 08:15 is first observed/projectable only at 08:17."""
    market = _regular_market(periods=31)
    drops = [pd.Timestamp(f"2024-01-01 08:{mm:02d}", tz="UTC") for mm in (11, 12, 13, 15, 16)]
    return market.drop(drops)


def _offgrid_market():
    """Add half-minute LTF observations inside the bucket ending 08:10 (off the 1-min grid)."""
    market = _regular_market(periods=26)
    extra_idx = pd.DatetimeIndex(
        [pd.Timestamp("2024-01-01 08:07:30", tz="UTC"), pd.Timestamp("2024-01-01 08:08:30", tz="UTC")]
    )
    last = market["close"].iloc[-1]
    extra = _ohlc(
        [last + 0.1, last + 0.2],
        index=extra_idx,
    )
    combined = pd.concat([market, extra]).sort_index()
    return combined[~combined.index.duplicated(keep="first")]


def _defect_both_market():
    """One missing grid minute (08:12) and one off-grid observation (08:13:30) in the
    bucket ending 08:15."""
    market = _regular_market(periods=26)
    market = market.drop(pd.Timestamp("2024-01-01 08:12", tz="UTC"))
    extra = _ohlc([market["close"].iloc[-1] + 0.1],
                  index=pd.DatetimeIndex([pd.Timestamp("2024-01-01 08:13:30", tz="UTC")]))
    return pd.concat([market, extra]).sort_index()


# ---------------------------------------------------------------------------
# Non-vacuity: the fixtures really create every situation the suite claims
# ---------------------------------------------------------------------------

def test_fixtures_are_non_vacuous():
    full, _, _ = _surface(_regular_market())
    assert len(full.bucket_frame) >= 5

    regular = _regular_market()
    final_bar = regular.index[-1]
    # an in-progress bucket (end strictly after the last bar) exists but must not be emitted
    agg_end = (final_bar.value // DUR.value + 1) * DUR.value
    assert pd.Timestamp(agg_end, tz="UTC") > final_bar
    assert not (full.bucket_frame["bucket_end_utc"] >= pd.Timestamp(agg_end, tz="UTC")).any()

    # exact boundary row exists: 08:05 is both a source close and the first projectable row
    assert full.asof_bar_frame.loc[pd.Timestamp("2024-01-01 08:05", tz="UTC"),
                                   f"{SCALE}__close_batch_order_unknown"]
    assert not full.asof_bar_frame.loc[pd.Timestamp("2024-01-01 08:04", tz="UTC"),
                                       f"{SCALE}__close_batch_order_unknown"]

    # spike inside the in-progress final bucket must be hidden (proved by a dedicated test too)
    gap = _gap_market()
    gsurf, _, _ = _surface(gap)
    grow = gsurf.bucket_frame[
        gsurf.bucket_frame["bucket_end_utc"] == pd.Timestamp("2024-01-01 08:15", tz="UTC")
    ].iloc[0]
    assert grow["theoretical_available_at"] != grow["first_observed_asof_time"]
    assert str(grow["coverage_status"]) == s4c.GRID_OBSERVATIONS_MISSING

    off, _, _ = _surface(_offgrid_market())
    assert s4c.OFF_GRID_OBSERVATIONS_PRESENT in set(off.bucket_frame["coverage_status"].astype(str))

    defect, _, _ = _surface(_defect_both_market())
    assert s4c.GRID_OBSERVATIONS_DEFECT_BOTH in set(defect.bucket_frame["coverage_status"].astype(str))

    complete = set(full.bucket_frame["coverage_status"].astype(str))
    assert s4c.GRID_OBSERVATIONS_COMPLETE in complete

    unknown, _, _ = _surface(_regular_market(), cadence=None)
    assert set(unknown.bucket_frame["coverage_status"].astype(str)) == {s4c.GRID_COMPLETENESS_UNKNOWN}


def test_nonvacuity_predicates_are_capable_of_being_false():
    """An empty/too-short market must make every non-vacuity predicate FALSE (guard against
    tests that pass on fixtures which create nothing)."""
    market = _regular_market(periods=2)  # no completed 5-min bucket reachable
    surf, _, _ = _surface(market, cadence=None)
    assert len(surf.bucket_frame) == 0
    assert not surf.asof_bar_frame[f"{SCALE}__close_batch_order_unknown"].any()
    assert (surf.asof_bar_frame[f"{SCALE}__coverage_status"] == s4c.COVERAGE_UNAVAILABLE).all()


# ---------------------------------------------------------------------------
# Leakage / exact boundary / spike concealment
# ---------------------------------------------------------------------------

def test_no_completed_bucket_visible_before_first_observation():
    surf, adapter, _ = _surface(_regular_market())
    af = surf.asof_bar_frame
    # first bar 08:01 .. 08:04 precede the first close at 08:05 -> unavailable, no prices
    for t in ("08:01", "08:02", "08:03", "08:04"):
        ts = pd.Timestamp("2024-01-01 " + t, tz="UTC")
        row = af.loc[ts]
        assert pd.isna(row[f"{SCALE}__completed_bucket_end_utc"])
        assert pd.isna(row[f"{SCALE}__completed_bucket_high"])
        assert row[f"{SCALE}__coverage_status"] == s4c.COVERAGE_UNAVAILABLE
        assert not row[f"{SCALE}__close_batch_order_unknown"]
        assert int(row[f"{SCALE}__observed_source_bar_count"]) == 0


def test_exact_boundary_phase_and_post_boundary_stability():
    market = _regular_market()
    surf, adapter, _ = _surface(market)
    af = surf.asof_bar_frame
    close_ts = pd.Timestamp("2024-01-01 08:05", tz="UTC")
    before_ts = pd.Timestamp("2024-01-01 08:04", tz="UTC")
    after_ts = pd.Timestamp("2024-01-01 08:06", tz="UTC")
    assert pd.isna(af.loc[before_ts, f"{SCALE}__completed_bucket_close"])
    at = af.loc[close_ts]
    assert at[f"{SCALE}__completed_bucket_end_utc"] == close_ts
    assert bool(at[f"{SCALE}__close_batch_order_unknown"]) is True
    after = af.loc[after_ts]
    assert after[f"{SCALE}__completed_bucket_end_utc"] == close_ts
    assert bool(after[f"{SCALE}__close_batch_order_unknown"]) is False
    # projected OHLC values are stable across the boundary
    for col in ("open", "high", "low", "close"):
        assert at[f"{SCALE}__completed_bucket_{col}"] == after[f"{SCALE}__completed_bucket_{col}"]


def test_in_progress_bucket_spike_is_completely_hidden():
    market = _regular_market(periods=31)
    clean, _, _ = _surface(market)
    spiked = market.copy()
    final_ts = spiked.index[-1]  # 08:31, belongs to the in-progress bucket ending 08:35
    spiked.loc[final_ts, "high"] = spiked["high"].max() + 50.0
    spiked.loc[final_ts, "low"] = spiked["low"].min() - 50.0
    spiked_surf, _, _ = _surface(spiked)
    # the last EMITTED bucket is identical; the spike never reaches any projected HTF fact
    pd.testing.assert_frame_equal(
        clean.bucket_frame.reset_index(drop=True),
        spiked_surf.bucket_frame.reset_index(drop=True),
        check_exact=True,
    )
    af_cols = [c for c in clean.asof_bar_frame.columns]
    pd.testing.assert_frame_equal(
        clean.asof_bar_frame[af_cols], spiked_surf.asof_bar_frame[af_cols], check_exact=True
    )


def test_bar_pre_close_phase_rejected_completed_and_snapshot_accepted():
    market = _regular_market()
    surf, adapter, _ = _surface(market)
    pre_key = _key(adapter, market.index, 9, InformationPhase.BAR_PRE_CLOSE)
    with pytest.raises(TrajectoryContractError):
        s4c.project_htf_scale_prefix(surface=surf, boundary_key=pre_key)
    snap_key = _key(adapter, market.index, 9, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE)
    binding = s4c.project_htf_scale_prefix(surface=surf, boundary_key=snap_key)
    assert binding.prefix_row_count == 10


# ---------------------------------------------------------------------------
# Gap / projectability semantics
# ---------------------------------------------------------------------------

def test_feed_gap_delays_projectability_to_first_observed_row():
    market = _gap_market()
    surf, _, _ = _surface(market)
    af = surf.asof_bar_frame
    delayed_end = pd.Timestamp("2024-01-01 08:15", tz="UTC")
    observed_at = pd.Timestamp("2024-01-01 08:17", tz="UTC")
    # rows 08:14 (present) and 08:15/08:16 (absent) must still show the PRIOR bucket
    row14 = af.loc[pd.Timestamp("2024-01-01 08:14", tz="UTC")]
    assert row14[f"{SCALE}__completed_bucket_end_utc"] == pd.Timestamp("2024-01-01 08:10", tz="UTC")
    # first reveal at 08:17 with the same-batch flag
    row17 = af.loc[observed_at]
    assert row17[f"{SCALE}__completed_bucket_end_utc"] == delayed_end
    assert bool(row17[f"{SCALE}__close_batch_order_unknown"]) is True
    assert row17[f"{SCALE}__projectable_asof_time_utc"] == observed_at
    bucket = surf.bucket_frame[surf.bucket_frame["bucket_end_utc"] == delayed_end].iloc[0]
    assert bucket["theoretical_available_at"] == delayed_end
    assert bucket["first_observed_asof_time"] == observed_at
    assert int(bucket["missing_grid_observation_count"]) == 4
    assert int(bucket["source_bar_count"]) == 1


# ---------------------------------------------------------------------------
# Cadence-grid coverage statuses (set comparison semantics)
# ---------------------------------------------------------------------------

def test_grid_full_coverage_status():
    surf, _, _ = _surface(_regular_market())
    # every emitted bucket except the natural warm-up window is complete
    full_buckets = surf.bucket_frame[
        surf.bucket_frame["coverage_status"].astype(str) == s4c.GRID_OBSERVATIONS_COMPLETE
    ]
    assert len(full_buckets) >= 4
    row = full_buckets.iloc[0]
    assert int(row["expected_grid_bar_count"]) == 5
    assert int(row["missing_grid_observation_count"]) == 0
    assert int(row["off_grid_observation_count"]) == 0
    # arithmetic identity: expected + off-grid = observed + missing
    b = surf.bucket_frame
    assert (
        b["expected_grid_bar_count"].astype("int64")
        + b["off_grid_observation_count"].astype("int64")
        == b["source_bar_count"].astype("int64")
        + b["missing_grid_observation_count"].astype("int64")
    ).all()


def test_grid_missing_status():
    surf, _, _ = _surface(_gap_market())
    statuses = surf.bucket_frame
    missing = statuses[statuses["coverage_status"].astype(str) == s4c.GRID_OBSERVATIONS_MISSING]
    assert len(missing) >= 1
    assert (missing["missing_grid_observation_count"].astype("int64") > 0).all()
    assert (missing["off_grid_observation_count"].astype("int64") == 0).all()


def test_off_grid_status():
    surf, _, _ = _surface(_offgrid_market())
    off = surf.bucket_frame[
        surf.bucket_frame["coverage_status"].astype(str) == s4c.OFF_GRID_OBSERVATIONS_PRESENT
    ]
    assert len(off) == 1
    row = off.iloc[0]
    assert int(row["off_grid_observation_count"]) == 2
    assert int(row["missing_grid_observation_count"]) == 0
    # the off-grid observations are real facts: source count includes them, OHLC aggregates them
    assert int(row["source_bar_count"]) == 7


def test_defect_both_status():
    surf, _, _ = _surface(_defect_both_market())
    both = surf.bucket_frame[
        surf.bucket_frame["coverage_status"].astype(str) == s4c.GRID_OBSERVATIONS_DEFECT_BOTH
    ]
    assert len(both) == 1
    row = both.iloc[0]
    assert int(row["missing_grid_observation_count"]) >= 1
    assert int(row["off_grid_observation_count"]) >= 1


def test_unknown_coverage_without_cadence_keeps_observed_truth():
    surf, _, _ = _surface(_gap_market(), cadence=None)
    b = surf.bucket_frame
    assert set(b["coverage_status"].astype(str)) == {s4c.GRID_COMPLETENESS_UNKNOWN}
    assert b["expected_grid_bar_count"].isna().all()
    assert b["missing_grid_observation_count"].isna().all()
    assert b["off_grid_observation_count"].isna().all()
    # observed bucket OHLC and counts are still factual truth (no deletion, no fill)
    assert (b["source_bar_count"].astype("int64") >= 1).all()
    assert np.isfinite(b[["open", "high", "low", "close"]].to_numpy(float)).all()


def test_cadence_misalignment_and_non_multiple_are_contract_errors():
    market = _regular_market()
    shifted = s4c.CadenceGridContract(pd.Timestamp("2024-01-01 00:00:30", tz="UTC"),
                                      pd.Timedelta(minutes=1))
    adapter, timeline = _sealed(market)
    with pytest.raises(TrajectoryContractError):
        s4c.build_htf_scale_surface(
            timeline=timeline, adapter=adapter, market_history=market,
            scale_spec=s4c.HtfScaleSpec(SCALE, DUR), cadence=shifted)
    seven_min_cadence = s4c.CadenceGridContract(EPOCH, pd.Timedelta(minutes=7))
    with pytest.raises(TrajectoryContractError):
        s4c.build_htf_scale_surface(
            timeline=timeline, adapter=adapter, market_history=market,
            scale_spec=s4c.HtfScaleSpec(SCALE, DUR), cadence=seven_min_cadence)


def test_cadence_contract_rejects_naive_epoch_and_nonpositive_period():
    with pytest.raises(TrajectoryContractError):
        s4c.CadenceGridContract(pd.Timestamp("2024-01-01"), pd.Timedelta(minutes=1))
    with pytest.raises(TrajectoryContractError):
        s4c.CadenceGridContract(EPOCH, pd.Timedelta(0))


# ---------------------------------------------------------------------------
# Future-append prefix invariance
# ---------------------------------------------------------------------------

def test_prefix_invariant_under_future_append():
    market = _regular_market(periods=31)
    full, adapter, _ = _surface(market)
    T = 15  # 08:16
    key_full = _key(adapter, market.index, T)
    full_binding = s4c.project_htf_scale_prefix(surface=full, boundary_key=key_full)

    head = market.iloc[: T + 1]
    h_adapter, h_timeline = _sealed(head, "t4c")
    head_surf = s4c.build_htf_scale_surface(
        timeline=h_timeline, adapter=h_adapter, market_history=head,
        scale_spec=s4c.HtfScaleSpec(SCALE, DUR), cadence=CAD)
    head_key = _key(h_adapter, head.index, T)
    head_binding = s4c.project_htf_scale_prefix(surface=head_surf, boundary_key=head_key)

    assert full_binding.prefix_hash == head_binding.prefix_hash
    assert full_binding.prefix_row_count == head_binding.prefix_row_count == T + 1
    assert full_binding.prefix_bucket_count == head_binding.prefix_bucket_count
    # full-surface identity legitimately differs under future append; only the
    # PREFIX identity is invariant (full-surface id carries post-T content)


def test_prefix_changes_when_pre_boundary_fact_is_removed():
    market = _regular_market(periods=31)
    full, adapter, _ = _surface(market)
    T = 20
    b1 = s4c.project_htf_scale_prefix(surface=full, boundary_key=_key(adapter, market.index, T))
    # remove an observed bar inside an already completed bucket (<= T)
    mutated = market.drop(market.index[5])
    m_surf, m_adapter, _ = _surface(mutated)
    b2 = s4c.project_htf_scale_prefix(
        surface=m_surf, boundary_key=_key(m_adapter, mutated.index, T - 1))
    assert b1.prefix_hash != b2.prefix_hash


# ---------------------------------------------------------------------------
# Timezone / DST equivalence and cross-timeline rejection
# ---------------------------------------------------------------------------

def test_timezone_index_equivalence():
    utc_market = _regular_market(periods=31)
    ny_market = utc_market.copy()
    ny_market.index = utc_market.index.tz_convert("America/New_York")
    u_surf, _, _ = _surface(utc_market, tid="z")
    n_surf, _, _ = _surface(ny_market, tid="z")
    pd.testing.assert_frame_equal(
        u_surf.bucket_frame.reset_index(drop=True),
        n_surf.bucket_frame.reset_index(drop=True),
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        u_surf.asof_bar_frame.reset_index(drop=True),
        n_surf.asof_bar_frame.reset_index(drop=True),
        check_exact=True,
    )


def test_cross_timeline_prefix_rejected_and_adapter_mismatch_rejected():
    market = _regular_market()
    surf, adapter_a, _ = _surface(market, tid="AAA")
    foreign = TimeIndexedTimelineAdapter("BBB")
    foreign_key = foreign.key_for_position(
        market.index, 10, InformationPhase.COMPLETED_ROW_AVAILABLE, 0
    )
    with pytest.raises(TrajectoryDataError):
        s4c.project_htf_scale_prefix(surface=surf, boundary_key=foreign_key)

    # adapter whose timeline_id does not match the sealed timeline
    adapter_b, timeline_a = _sealed(market, "AAA")
    wrong_adapter = TimeIndexedTimelineAdapter("OTHER")
    with pytest.raises(TrajectoryContractError):
        s4c.build_htf_scale_surface(
            timeline=timeline_a, adapter=wrong_adapter, market_history=market,
            scale_spec=s4c.HtfScaleSpec(SCALE, DUR), cadence=CAD)


def test_positional_axis_rejected():
    # a legal positional timeline (RangeIndex market) is sealed, then the 4C-1 builder
    # must reject it because HTF buckets are intrinsically time-based.
    market = _ohlc(np.linspace(100, 105, 90), index=pd.RangeIndex(90))
    pos_adapter = PositionalTimelineAdapter("pos")
    pos_timeline = MarketObservationTimeline.seal(adapter=pos_adapter, market_history=market)
    with pytest.raises(TrajectoryContractError):
        s4c.build_htf_scale_surface(
            timeline=pos_timeline, adapter=pos_adapter, market_history=market,
            scale_spec=s4c.HtfScaleSpec(SCALE, DUR))
    # a time-index adapter fed a positional timeline also fails at the contract check
    time_adapter, _ = _sealed(_regular_market())
    with pytest.raises(TrajectoryContractError):
        s4c.build_htf_scale_surface(
            timeline=pos_timeline, adapter=time_adapter, market_history=market,
            scale_spec=s4c.HtfScaleSpec(SCALE, DUR))


# ---------------------------------------------------------------------------
# Identity / tampering / coherent rehash / substitution / schema injection
# ---------------------------------------------------------------------------

def _tampered(surface, **changes):
    import dataclasses
    return dataclasses.replace(surface, **changes)


def test_tampered_bucket_price_detected():
    surf, _, _ = _surface(_regular_market())
    bad_bucket = surf.bucket_frame.copy(deep=True)
    bad_bucket.loc[bad_bucket.index[1], "close"] += 1.0
    bad = _tampered(surf, bucket_frame=bad_bucket)
    with pytest.raises(TrajectoryDataError):
        s4c.verify_surface_integrity(bad)


def test_tampered_asof_cell_and_projection_recomputation():
    surf, _, _ = _surface(_regular_market())
    bad_asof = surf.asof_bar_frame.copy(deep=True)
    col = f"{SCALE}__completed_bucket_high"
    visible = bad_asof[col].first_valid_index()
    bad_asof.loc[visible, col] += 5.0
    bad = _tampered(surf, asof_bar_frame=bad_asof)
    with pytest.raises(TrajectoryDataError):
        s4c.verify_surface_integrity(bad)


def test_coherent_rehash_cannot_reframe_scope_or_substitute_scale():
    market = _regular_market()
    surf, _, _ = _surface(market, name=SCALE)
    # a different duration is a different surface identity, even under identical market data
    other, _, _ = _surface(market, name=SCALE, duration=pd.Timedelta(minutes=15))
    assert surf.surface_id != other.surface_id
    assert surf.scale_duration_ns != other.scale_duration_ns

    # forge the asof frame with the OTHER scale's schema but keep this surface's hashes
    forged = _tampered(surf, asof_bar_frame=other.asof_bar_frame)
    with pytest.raises(TrajectoryDataError):
        s4c.verify_surface_integrity(forged)

    # tamper content then coherently rehash the content layer but leave surface_id stale:
    bad_bucket = surf.bucket_frame.copy(deep=True)
    bad_bucket.loc[bad_bucket.index[0], "open"] += 1.0
    from trading_system.research.hashing import canonical_sha256
    new_bucket_hash = canonical_sha256(domain="STAGE4C1_BUCKET_OBSERVATIONS_V1", payload=bad_bucket)
    forged2 = _tampered(surf, bucket_frame=bad_bucket, bucket_observations_hash=new_bucket_hash)
    with pytest.raises(TrajectoryDataError):
        s4c.verify_surface_integrity(forged2)  # stale surface_id / asof-recompute mismatch


def test_domain_is_fixed_and_cannot_be_reframed():
    surf, _, _ = _surface(_regular_market())
    bad = _tampered(surf, domain="SOMETHING_ELSE")
    with pytest.raises(TrajectoryDataError):
        s4c.verify_surface_integrity(bad)


def test_schema_injection_rejected_middle_and_tail_both_frames():
    surf, _, _ = _surface(_regular_market())
    # tail injection on bucket frame
    tail = surf.bucket_frame.copy(deep=True)
    tail["evil_tail"] = 1.0
    with pytest.raises(TrajectoryDataError):
        s4c.verify_surface_integrity(_tampered(surf, bucket_frame=tail))
    # middle injection on bucket frame
    mid = surf.bucket_frame.copy(deep=True)
    mid.insert(3, "evil_mid", 1.0)
    with pytest.raises(TrajectoryDataError):
        s4c.verify_surface_integrity(_tampered(surf, bucket_frame=mid))
    # injection on the as-of frame
    atail = surf.asof_bar_frame.copy(deep=True)
    atail["evil"] = 1.0
    with pytest.raises(TrajectoryDataError):
        s4c.verify_surface_integrity(_tampered(surf, asof_bar_frame=atail))


def test_malicious_closed_engine_schema_drift_is_rejected(monkeypatch):
    """A malicious/altered CLOSED 5.1 that adds a public bucket column must be rejected by the
    dynamic schema mirror (the mirror is not compared against itself)."""
    market = _regular_market()
    adapter, timeline = _sealed(market)
    original_analyze = CausalHTFAggregator.analyze

    def malicious_analyze(self, df):
        asof, table = original_analyze(self, df)
        table = table.copy()
        table["evil_public_column"] = 1.0
        return asof, table

    monkeypatch.setattr(CausalHTFAggregator, "analyze", malicious_analyze)
    with pytest.raises(TrajectoryDataError):
        s4c.build_htf_scale_surface(
            timeline=timeline, adapter=adapter, market_history=market,
            scale_spec=s4c.HtfScaleSpec(SCALE, DUR), cadence=CAD)


def test_independent_reconstruction_matches_closed_51():
    """The bound frames must equal an independent direct run of CLOSED 5.1 (not self-comparison)."""
    market = _regular_market()
    from trading_system.multitimeframe.causal_htf import TimeAggregationSpec
    _, table = CausalHTFAggregator(spec=TimeAggregationSpec(DUR)).analyze(market)
    surface, _, _ = _surface(market, cadence=None)
    bound = surface.bucket_frame
    for col in ("open", "high", "low", "close", "source_bar_count",
                "bucket_end_utc", "theoretical_available_at", "first_observed_asof_time"):
        if col == "theoretical_available_at":
            assert bound[col].equals(table["theoretical_available_at"].reset_index(drop=True))
        else:
            pd.testing.assert_series_equal(
                bound[col].reset_index(drop=True),
                table[col].reset_index(drop=True),
                check_names=False,
                check_dtype=False,
            )


# ---------------------------------------------------------------------------
# Derived-only / volume / schema rules
# ---------------------------------------------------------------------------

def test_frames_are_derived_only_no_market_passthrough():
    market = _regular_market(volume=True)
    surf, _, _ = _surface(market)
    # no raw LTF market column names leak into the as-of projection frame
    assert not (set(surf.asof_bar_frame.columns) & {"open", "high", "low", "close", "volume"})
    # bucket frame aggregates HTF OHLC but never carries HTF volume
    assert "volume" not in surf.bucket_frame.columns
    # exact whole-frame schemas
    assert tuple(surf.bucket_frame.columns) == s4c._BUCKET_FRAME_COLUMNS
    assert tuple(surf.asof_bar_frame.columns) == s4c._asof_columns(SCALE)


def test_volume_presence_is_invisible_to_4c_content():
    no_vol = _regular_market(volume=False)
    with_vol = _regular_market(volume=True)
    s1, _, _ = _surface(no_vol, tid="v", cadence=None)
    s2, _, _ = _surface(with_vol, tid="v", cadence=None)
    # the sealed timeline identity legitimately records optional-volume presence,
    # so surface_id may differ; the Stage 4C-1 DERIVED content must be identical and
    # must never contain HTF volume.
    assert s1.bucket_observations_hash == s2.bucket_observations_hash
    assert s1.asof_projection_hash == s2.asof_projection_hash
    pd.testing.assert_frame_equal(s1.bucket_frame, s2.bucket_frame, check_exact=True)
    pd.testing.assert_frame_equal(s1.asof_bar_frame, s2.asof_bar_frame, check_exact=True)
    assert "volume" not in s1.bucket_frame.columns
    assert "volume" not in s2.bucket_frame.columns


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

def test_contract_errors_for_bad_configuration():
    market = _regular_market()
    adapter, timeline = _sealed(market)
    for bad_spec in (
        lambda: s4c.HtfScaleSpec("1bad", DUR),       # unsafe name
        lambda: s4c.HtfScaleSpec("has-dash", DUR),   # unsafe name
        lambda: s4c.HtfScaleSpec(SCALE, pd.Timedelta(0)),
        lambda: s4c.HtfScaleSpec(SCALE, 5),          # not a Timedelta
    ):
        with pytest.raises(TrajectoryContractError):
            bad_spec()
    with pytest.raises(TrajectoryContractError):
        s4c.build_htf_scale_surface(
            timeline=timeline, adapter=adapter, market_history=market, scale_spec="not-a-spec")
    with pytest.raises(TrajectoryContractError):
        s4c.build_htf_scale_surface(
            timeline=timeline, adapter=adapter, market_history=market,
            scale_spec=s4c.HtfScaleSpec(SCALE, DUR), cadence="not-a-cadence")


def test_data_error_for_bad_market_content():
    # malformed OHLC geometry is rejected by the sealed timeline / CLOSED 5.1 as Data
    market = _regular_market()
    market.loc[market.index[3], "high"] = market["low"].iloc[3] - 1.0
    with pytest.raises(Exception) as exc:
        _sealed(market)
    assert exc.type is not TrajectoryContractError


def test_prefix_out_of_range_and_wrong_key_type():
    surf, adapter, _ = _surface(_regular_market())
    market = _regular_market()
    # the CLOSED adapter itself rejects a coordinate outside the timeline (fail-closed),
    # before any prefix projection can happen
    from trading_system.research.information_time import TimelineAdapterError
    with pytest.raises(TimelineAdapterError):
        _key(adapter, market.index, len(market) + 5)
    with pytest.raises(TrajectoryContractError):
        s4c.project_htf_scale_prefix(surface=surf, boundary_key="not-a-key")


# ---------------------------------------------------------------------------
# Semantic-inflation guard and out-of-scope guards
# ---------------------------------------------------------------------------

def test_projectability_is_never_claimed_as_feed_arrival_or_market_availability():
    source = SRC_PATH.read_text(encoding="utf-8")
    manifest = s4c.trajectory_stage4c_manifest()
    projectability = manifest[manifest["name"] == "FIRST_OBSERVED_ASOF"]
    assert len(projectability) == 1
    assert projectability.iloc[0]["value"] == (
        "SEALED_TIMELINE_PROJECTION_NOT_FEED_ARRIVAL_PROVENANCE_NOT_MARKET_AVAILABILITY"
    )
    # canonical negation language must be present in module documentation
    assert "NOT feed-arrival provenance" in source
    assert "NOT_CERTIFIED / UNVERIFIABLE" in source
    # no affirmative inflation phrases
    for forbidden_phrase in (
        "feed arrival time",
        "actual market availability",
        "guarantees delivery",
        "when the exchange delivered",
    ):
        assert forbidden_phrase not in source.lower()


def test_out_of_scope_guards_in_source():
    tree = ast.parse(SRC_PATH.read_text(encoding="utf-8"))
    imported_modules = set()
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
            imported_names.update(a.name for a in node.names)
        if isinstance(node, ast.Import):
            imported_modules.update(a.name for a in node.names)
    # 4C-2 / reasoning / decision engines must not be imported
    forbidden_imports = {
        "trading_system.multitimeframe.confluence_matrix",
        "trading_system.structure.swing_detector",
        "trading_system.structure.swing_sequence",
        "trading_system.structure.structural_breaks",
    }
    assert not (imported_modules & forbidden_imports), imported_modules & forbidden_imports
    for forbidden_name in (
        "EmpiricalConfirmationPolicy",
        "CausalConfluenceMatrixEngine",
        "CausalAdaptiveSwingDetector",
        "CausalStructuralBreakEngine",
    ):
        assert forbidden_name not in imported_names
    # no production class/function may implement 4C-2 or trade/model semantics
    forbidden_defs = {
        "Stage4CMtfConfluenceSurface",
        "build_confluence_surface",
        "build_structure_surface",
        "build_transitions",
    }
    definitions = {n.name for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    assert not (forbidden_defs & definitions)
    # no quantile/policy parameter anywhere in the public builders
    builder = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "build_htf_scale_surface"
    )
    arg_names = {a.arg for a in builder.args.args} | {a.arg for a in builder.args.kwonlyargs}
    assert not ({"quantile", "swing_policy", "confirmation_policy", "policy"} & arg_names)
    # no private (_underscore) imports from CLOSED engine modules
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (
            node.module.startswith("trading_system.multitimeframe")
            or node.module.startswith("trading_system.structure")
            or node.module.startswith("trading_system.zones")
            or node.module.startswith("trading_system.liquidity")
        ):
            assert not any(a.name.startswith("_") for a in node.names), node.module


def test_manifest_scope_declarations():
    m = s4c.trajectory_stage4c_manifest()
    get = lambda name: m.loc[m["name"] == name, "value"].iloc[0]
    assert get("HTF_STRUCTURE_STATUS") == "NOT_CONFIGURED_IN_4C_1"
    assert get("MTF_CONFLUENCE_SURFACE") == "NOT_STARTED_STAGE_4C_2"
    assert get("HTF_TRANSITIONS") == "NOT_STARTED_STAGE_4C_2"
    assert get("WIN_LOSS") == "FORBIDDEN"
    for out in ("HTF_VOLUME", "HTF_LIQUIDITY", "HTF_ORDER_BLOCK", "HTF_FVG",
                "HTF_DEALING_RANGE", "MODEL", "GEOMETRY", "EXECUTION"):
        assert get(out) == "NOT_IMPLEMENTED"
    for i in range(20, 26):
        assert get(f"RESEARCH-DEBT-0{i}") == "OPEN"


def test_closed_5_2_unavailable_scale_contract_guard():
    """CONTRACT GUARD ONLY (no Stage 4C-2 production): the CLOSED 5.2 engine must represent
    a scale whose structure is never configured as configured-but-unavailable (all NA)."""
    decision = pd.date_range("2024-01-01 08:00", periods=12, freq="1min", tz="UTC")
    empty_completed = pd.DataFrame(
        {"available_at": pd.DatetimeIndex([], tz="UTC"),
         "structure_state_after": pd.array([], dtype="string")}
    )
    aligned = causal_asof_align_scale_state(decision, empty_completed)
    assert not aligned["available"].any()
    assert aligned["structure_state_after"].isna().all()
    out = CausalConfluenceMatrixEngine().analyze(
        pd.DataFrame(index=decision), [ScaleFrame("m60", aligned)]
    )
    assert int(out["configured_scale_count"].iloc[0]) == 1
    assert int(out["available_scale_count"].iloc[0]) == 0
    assert float(out["availability_fraction"].iloc[0]) == 0.0
    assert not bool(out["directional_conflict"].any())
    # zero scales is rejected by CLOSED 5.2
    with pytest.raises(Exception):
        CausalConfluenceMatrixEngine().analyze(pd.DataFrame(index=decision), [])


# ---------------------------------------------------------------------------
# Prefix binding semantics
# ---------------------------------------------------------------------------

def test_prefix_binding_counts_and_determinism():
    market = _regular_market(periods=31)
    surf, adapter, _ = _surface(market)
    T = 14
    binding = s4c.project_htf_scale_prefix(
        surface=surf, boundary_key=_key(adapter, market.index, T))
    expected_buckets = int(
        (surf.bucket_frame["first_observed_asof_position"] <= T).sum()
    )
    assert binding.prefix_bucket_count == expected_buckets
    assert binding.domain == "HTF_SCALE_RAW"
    # deterministic: same boundary yields identical binding hash
    again = s4c.project_htf_scale_prefix(
        surface=surf, boundary_key=_key(adapter, market.index, T))
    assert binding.prefix_hash == again.prefix_hash
    assert dataclasses_field(binding)


def dataclasses_field(binding):
    import dataclasses
    return dataclasses.is_dataclass(binding)

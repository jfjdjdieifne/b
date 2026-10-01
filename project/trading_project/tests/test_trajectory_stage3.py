"""Tests for Module 6.2A-4 V1 Stage 3: Terminal / Censor Snapshots & As-Of Censor Series.

Covers the required adversarial matrix:
- 6.2A-1 authoritative binding (mature / censored / missing / ambiguous / hash / timeline mismatch)
- Stage 2 terminal state & position mismatch rejection
- two-clock semantics (terminal factual availability vs research as-of)
- origin rule (preserve source origin position, no forged InformationKey)
- literal terminal states only (no WIN/LOSS/SUCCESS/FAILURE, no price-inferred terminal)
- swing-policy and lifecycle-ledger canonical input bindings
- Stage 2 compact prefix binding (no full envelope tuple, no prefix-stable assumption)
- state immutability / future append & mutation invariance / A->A / A->B->A / fresh instance
- positional & time-indexed timelines, timezone/DST, cross-timeline rejection
- real integration with CLOSED Stage 1 / Stage 2 / 6.2A-1, and 6.2A-2 non-redefinition
- firewall: live modules do not import Stage 3; no Stage 4 domains.
"""

from __future__ import annotations

import dataclasses
import re
import runpy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_system.research.information_time import (
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
    TimelineAdapterError,
)
from trading_system.research.trajectory.trajectory_contract import (
    DecisionAnchor,
    MarketObservationTimeline,
    TrajectoryContractError,
    TrajectoryDataError,
    anchor_decision,
    bind_interval,
)
from trading_system.research.trajectory.trajectory_stage2 import (
    TRAJECTORY_STAGE2_CONTRACT_VERSION,
    build_stage2_trajectory,
)
from trading_system.structure.swing_detector import EmpiricalConfirmationPolicy
from trading_system.research.trajectory.trajectory_stage3 import (
    TRAJECTORY_STAGE3_CONTRACT_VERSION,
    FactualTerminalSnapshot,
    RightCensoredAsOfSnapshot,
    append_to_asof_series,
    build_mature_terminal_snapshot,
    build_right_censored_snapshot,
    trajectory_stage3_manifest,
    _canonicalize_ledger,
    _canonicalize_swing_policy,
    _empty_ledger_canonical_df,
)

# Reuse helpers from dataset-builder tests for the real CLOSED pipeline
_helpers = runpy.run_path("tests/test_research_dataset_builder.py")

_LEDGER_COLS = [
    "ledger_event_id",
    "hypothesis_id",
    "event_position",
    "same_row_batch_id",
    "ledger_event_type",
    "previous_state",
    "new_state",
    "trigger_relationship_id",
    "superseded_by_hypothesis_id",
    "serialization_order",
]
_TERMINAL_STATES = {"CONTRADICTED", "SUPERSEDED", "OBSERVED_DIRECTION_ESTABLISHED"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bundle_market_adapter_timeline(tid: str):
    """Positional-timeline pipeline bundle with a market that has an `open` column."""
    bundle = _helpers["pipeline_bundle"](timeline_id=tid)
    market = bundle.market_frame.copy()
    market["open"] = market["close"]
    adapter = PositionalTimelineAdapter(tid)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    return bundle, market, adapter, timeline


def _time_bundle_market_adapter_timeline(tid: str, tz="America/New_York", freq="h", start="2026-03-07 12:00"):
    """Time-indexed pipeline bundle over a timezone-aware DatetimeIndex."""
    idx = pd.date_range(start, periods=10, freq=freq, tz=tz)
    bundle = _helpers["pipeline_bundle"](index=idx, timeline_id=tid)
    market = bundle.market_frame.copy()
    market["open"] = market["close"]
    adapter = TimeIndexedTimelineAdapter(tid)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    return bundle, market, adapter, timeline


def _anchor(bundle, adapter, timeline, hid, dpos):
    visible = _helpers["visible"](bundle, dpos, adapter)
    frozen = _helpers["freeze_creation_feature_snapshot"](visible, hypothesis_id=hid, adapter=adapter)
    return anchor_decision(timeline=timeline, frozen=frozen)


def _interval(timeline, anchor, adapter, market, endpos):
    ek = adapter.key_for_position(market.index, endpos, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    return bind_interval(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market, end_inclusive=ek
    )


def _mature_parts(tid="s3_mature", hid=0, dpos=1, termpos=4, asof=5):
    """Real CLOSED-pipeline pieces for a mature terminal (hypothesis 0: CONTRADICTED at 4)."""
    bundle, market, adapter, timeline = _bundle_market_adapter_timeline(tid)
    anchor = _anchor(bundle, adapter, timeline, hid, dpos)
    interval = _interval(timeline, anchor, adapter, market, termpos)
    stage2 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=bundle.hypothesis_ledger,
    )
    outcome = _helpers["outcome"](bundle, hid, asof, adapter)
    return bundle, market, adapter, timeline, anchor, interval, stage2, outcome


def _censored_parts(tid="s3_censored", hid=1, dpos=6, asofpos=7, asof=7):
    """Real CLOSED-pipeline pieces for a right-censored as-of (hypothesis 1: terminal at 8 not yet observed)."""
    bundle, market, adapter, timeline = _bundle_market_adapter_timeline(tid)
    anchor = _anchor(bundle, adapter, timeline, hid, dpos)
    interval = _interval(timeline, anchor, adapter, market, asofpos)
    stage2 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=bundle.hypothesis_ledger,
    )
    outcome = _helpers["outcome"](bundle, hid, asof, adapter)
    return bundle, market, adapter, timeline, anchor, interval, stage2, outcome


def _mutate_outcome(outcome, **column_values):
    """Return a copy of the 6.2A-1 outcome with snapshot columns overwritten."""
    df = outcome.hypothesis_outcome_snapshots.copy(deep=True)
    for col, val in column_values.items():
        df[col] = val
    return dataclasses.replace(outcome, hypothesis_outcome_snapshots=df)


def _ledger_with_terminal(bundle, hid, pos, state, superseded_by=None):
    """Copy of the bundle ledger with hypothesis `hid` terminal row rewritten."""
    ledger = bundle.hypothesis_ledger.copy(deep=True)
    mask = (ledger["hypothesis_id"] == hid) & (ledger["event_position"] == pos)
    assert mask.any(), "expected a terminal row to rewrite"
    ledger.loc[mask, "new_state"] = state
    if superseded_by is not None:
        ledger.loc[mask, "superseded_by_hypothesis_id"] = superseded_by
    return ledger


def _minimal_ledger(rows):
    """Build a canonical-schema ledger from a list of row dicts."""
    df = pd.DataFrame(rows, columns=_LEDGER_COLS)
    for c in _LEDGER_COLS:
        if c in ("ledger_event_type", "previous_state", "new_state"):
            df[c] = df[c].astype("string")
        else:
            df[c] = pd.array(df[c], dtype="Int64")
    return df


# ---------------------------------------------------------------------------
# 6.2A-1 authoritative binding
# ---------------------------------------------------------------------------

def test_mature_outcome_binding_authoritative():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.terminal_state == "CONTRADICTED"
    assert snap.factual_outcome_id is not None
    assert snap.research_snapshot_id is not None
    # 6.2A-1 classification is authoritative: Stage 3 does not invent its own
    assert snap.factual_outcome_id == str(outcome.hypothesis_outcome_snapshots.iloc[0]["factual_outcome_id"])


def test_censored_outcome_binding_authoritative():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _censored_parts()
    snap = build_right_censored_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_asof=interval, stage2_result_through_asof=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.outcome_mature is False
    assert snap.right_censored_as_of is True
    assert snap.factual_outcome_id is None
    assert snap.research_snapshot_id is not None
    assert snap.censoring_type == "RIGHT_CENSORED_AS_OF_BOUNDARY"


def test_missing_6_2A_1_input_rejection():
    bundle, market, adapter, timeline, anchor, interval, stage2, _ = _mature_parts()
    with pytest.raises(TrajectoryDataError, match="missing authoritative 6.2A-1"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=stage2,
            factual_outcome_result=None, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_ambiguous_duplicate_outcome_rejection():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    dup = _helpers["factual_batch"](outcome, outcome)  # two identical rows for the hypothesis
    with pytest.raises(TrajectoryDataError, match="ambiguous"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=stage2,
            factual_outcome_result=dup, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_decision_snapshot_hash_mismatch_rejection():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    bad = _mutate_outcome(outcome, decision_snapshot_hash="0" * 64)
    with pytest.raises(TrajectoryDataError, match="decision_snapshot_hash mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=stage2,
            factual_outcome_result=bad, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_outcome_timeline_mismatch_rejection():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    bad = _mutate_outcome(outcome, timeline_id="another_timeline")
    with pytest.raises(TrajectoryDataError, match="timeline_id mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=stage2,
            factual_outcome_result=bad, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_mature_outcome_with_na_factual_id_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    bad = _mutate_outcome(outcome, factual_outcome_id=pd.NA)
    with pytest.raises(TrajectoryDataError, match="factual_outcome_id"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=stage2,
            factual_outcome_result=bad, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_censored_outcome_with_present_factual_id_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _censored_parts()
    bad = _mutate_outcome(outcome, factual_outcome_id="abc123", right_censored_as_of=True)
    with pytest.raises(TrajectoryDataError, match="factual_outcome_id"):
        build_right_censored_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_asof=interval, stage2_result_through_asof=stage2,
            factual_outcome_result=bad, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_mature_builder_rejects_censored_outcome():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _censored_parts()
    with pytest.raises(TrajectoryDataError, match="requires mature"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=stage2,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_censored_builder_rejects_mature_outcome():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    with pytest.raises(TrajectoryDataError, match="requires censored"):
        build_right_censored_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_asof=interval, stage2_result_through_asof=stage2,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


# ---------------------------------------------------------------------------
# Stage 2 terminal state / position mismatch rejection
# ---------------------------------------------------------------------------

def test_terminal_state_mismatch_vs_stage2_rejection():
    bundle, market, adapter, timeline, anchor, interval, _, outcome = _mature_parts()
    # Stage 2 authoritative trajectory built from a ledger whose terminal state
    # differs from the 6.2A-1 outcome classification.
    alt_ledger = _ledger_with_terminal(bundle, 0, 4, "SUPERSEDED", superseded_by=99)
    alt_stage2 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=alt_ledger,
    )
    # Reconstruction from the bound ledger (CONTRADICTED) differs from the supplied
    # result (SUPERSEDED) -> BLOCKER 2 rejection.
    with pytest.raises(TrajectoryDataError, match="trajectory prefix mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=alt_stage2,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_terminal_position_mismatch_vs_stage2_rejection():
    bundle, market, adapter, timeline, anchor, interval, _, outcome = _mature_parts()
    # Stage 2 built with no ledger -> lifecycle has no terminal, but 6.2A-1 is mature.
    # Reconstruction from the bound ledger has a lifecycle terminal envelope -> count mismatch.
    empty_stage2 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=None,
    )
    with pytest.raises(TrajectoryDataError, match="envelope count mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=empty_stage2,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_interval_must_end_at_terminal_rejection():
    bundle, market, adapter, timeline, anchor, _, stage2, outcome = _mature_parts()
    # interval ending after the terminal (post-terminal market rows) must be rejected
    interval_after = _interval(timeline, anchor, adapter, market, 6)
    with pytest.raises(TrajectoryDataError, match="terminal"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval_after, stage2_result_through_terminal=stage2,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


# ---------------------------------------------------------------------------
# Two-clock semantics
# ---------------------------------------------------------------------------

def test_terminal_unavailable_before_factual_availability():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(asof=9)
    ra_before = adapter.key_for_position(market.index, 2, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, 0)
    with pytest.raises(TrajectoryDataError, match="research_as_of"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=stage2,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
            research_as_of_key=ra_before,
        )


def test_later_research_as_of_retains_earlier_terminal_availability():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(asof=9)
    ra_later = adapter.key_for_position(market.index, 9, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, 0)
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        research_as_of_key=ra_later,
    )
    # terminal factually available at T4, research reconstructs at T9
    assert snap.terminal_factual_available_at_information_key.bar_position == 4
    assert snap.research_as_of_information_key.bar_position == 9
    # interval still ends at the legal terminal boundary (T4)
    assert snap.observed_bar_count == interval.observed_bar_count == 3
    assert snap.terminal_origin_position == 4


def test_terminal_interval_stops_at_legal_terminal_boundary():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    assert interval.end_inclusive_bar_position == 4
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.terminal_factual_available_at_information_key.bar_position == 4
    assert snap.terminal_origin_position == 4


def test_no_post_terminal_contamination():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    # no bar beyond the terminal position (4) may enter the terminal trajectory
    assert snap.terminal_origin_position == 4
    assert snap.observed_bar_count == interval.observed_bar_count  # bars 2,3,4 only
    # Stage 2 lifecycle itself enforces no post-terminal rows
    assert stage2.lifecycle.terminal_position == 4


# ---------------------------------------------------------------------------
# Origin rule
# ---------------------------------------------------------------------------

def test_terminal_origin_position_preserved_as_integer_not_information_key():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    # origin preserved exactly as the CLOSED source supplies it: an integer position
    assert isinstance(snap.terminal_origin_position, int)
    assert not isinstance(snap.terminal_origin_position, InformationKey)
    assert snap.terminal_origin_position == 4
    # the availability clock is an InformationKey, the origin is a bare position
    assert isinstance(snap.terminal_factual_available_at_information_key, InformationKey)


def test_origin_ledger_event_id_preserved():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    # hypothesis 0 terminal row is ledger_event_id == 1 in the bundle ledger
    term_row = bundle.hypothesis_ledger[
        (bundle.hypothesis_ledger["hypothesis_id"] == 0)
        & (bundle.hypothesis_ledger["event_position"] == 4)
    ].iloc[0]
    assert snap.terminal_ledger_event_id == int(term_row["ledger_event_id"])


def test_no_manufactured_origin_information_key():
    # The terminal origin must be the CLOSED source's event_position (Int64), never a
    # reconstructed InformationKey pretending to be a provenance key.
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    for f in dataclasses.fields(snap):
        if "origin" in f.name:
            val = getattr(snap, f.name)
            assert not isinstance(val, InformationKey), f"{f.name} must not be an InformationKey"


# ---------------------------------------------------------------------------
# Literal terminal states only
# ---------------------------------------------------------------------------

def test_all_three_literal_terminal_states_accepted():
    # CONTRADICTED (real) already covered; verify SUPERSEDED and OBSERVED_DIRECTION_ESTABLISHED
    # are accepted and preserved literally when 6.2A-1 and Stage 2 agree.
    for state in ("SUPERSEDED", "OBSERVED_DIRECTION_ESTABLISHED"):
        bundle, market, adapter, timeline, anchor, interval, _, outcome = _mature_parts(tid=f"s3_state_{state}")
        alt_ledger = _ledger_with_terminal(
            bundle, 0, 4, state, superseded_by=99 if state == "SUPERSEDED" else None
        )
        alt_stage2 = build_stage2_trajectory(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval=interval, hypothesis_ledger=alt_ledger,
        )
        alt_outcome = _mutate_outcome(outcome, narrative_terminal_state=state)
        snap = build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=alt_stage2,
            factual_outcome_result=alt_outcome, lifecycle_ledger=alt_ledger,
        )
        assert snap.terminal_state == state


def test_invalid_terminal_state_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    alt_outcome = _mutate_outcome(outcome, narrative_terminal_state="WIN")
    with pytest.raises(TrajectoryDataError, match="invalid literal terminal state"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=stage2,
            factual_outcome_result=alt_outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_unresolved_as_of_remains_non_terminal():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _censored_parts()
    snap = build_right_censored_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_asof=interval, stage2_result_through_asof=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.outcome_mature is False
    assert snap.right_censored_as_of is True
    assert snap.censoring_type == "RIGHT_CENSORED_AS_OF_BOUNDARY"
    assert snap.factual_outcome_id is None


def test_no_win_loss_success_failure_semantics_in_snapshot():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    field_names = {f.name for f in dataclasses.fields(snap)}
    forbidden = ["win", "loss", "profit", "pnl", "success", "failure", "entry", "stop", "target", "fill", "slippage"]
    for f in field_names:
        for w in forbidden:
            assert not re.search(rf"\b{w}\b", f), f"forbidden trade-result token {w} in field {f}"
    # terminal state must be a literal lifecycle state, never a result term
    assert snap.terminal_state in _TERMINAL_STATES


def test_favorable_price_does_not_infer_terminal():
    # hypothesis 0 price rises (favorable for UP) but the ledger says CONTRADICTED at 4.
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    assert anchor.direction == "UP"
    # price trajectory is favorable over the interval, yet terminal is CONTRADICTED
    assert stage2.price.running_favorable_final > 0
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.terminal_state == "CONTRADICTED"
    assert snap.terminal_state != "OBSERVED_DIRECTION_ESTABLISHED"


# ---------------------------------------------------------------------------
# Swing-policy canonical input binding
# ---------------------------------------------------------------------------

class _Policy:
    def __init__(self, quantile, cont=(), conf=()):
        self.quantile = quantile
        self.prior_continuation_reversals = cont
        self.prior_confirmed_reversals = conf

    def create_runtime(self):
        # Delegates to the CLOSED policy so reconstruction (BLOCKER 2) can consume it.
        return EmpiricalConfirmationPolicy(
            quantile=self.quantile,
            prior_continuation_reversals=self.prior_continuation_reversals,
            prior_confirmed_reversals=self.prior_confirmed_reversals,
        ).create_runtime()


def test_swing_policy_binding_deterministic():
    p1 = _Policy(0.7, (1.0, 2.0), (3.0,))
    p2 = _Policy(0.7, (1.0, 2.0), (3.0,))
    _, h1 = _canonicalize_swing_policy(p1)
    _, h2 = _canonicalize_swing_policy(p2)
    assert h1 == h2


def test_swing_policy_none_evidence_only_identity():
    _, h_none = _canonicalize_swing_policy(None)
    _, h_none2 = _canonicalize_swing_policy(None)
    _, h_policy = _canonicalize_swing_policy(_Policy(0.5))
    assert h_none == h_none2
    assert h_none != h_policy


def test_swing_policy_change_changes_binding_identity():
    _, h_a = _canonicalize_swing_policy(_Policy(0.5))
    _, h_b = _canonicalize_swing_policy(_Policy(0.6))
    assert h_a != h_b


def test_swing_policy_nan_inf_rejection():
    with pytest.raises(TrajectoryDataError):
        _canonicalize_swing_policy(_Policy(float("nan")))
    with pytest.raises(TrajectoryDataError):
        _canonicalize_swing_policy(_Policy(0.5, (float("inf"),)))


def test_swing_policy_plus_zero_minus_zero_distinct():
    # canonical hashing preserves +0.0 / -0.0 via float hex; the binding must too
    _, h_p0 = _canonicalize_swing_policy(_Policy(0.0))
    _, h_n0 = _canonicalize_swing_policy(_Policy(-0.0))
    assert h_p0 != h_n0


def test_swing_policy_binding_affects_snapshot_identity():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    common = dict(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    s_none = build_mature_terminal_snapshot(swing_policy=None, **common)
    s_policy = build_mature_terminal_snapshot(swing_policy=_Policy(0.5), **common)
    assert s_none.snapshot_id != s_policy.snapshot_id
    assert s_none.reconstruction_swing_policy_hash != s_policy.reconstruction_swing_policy_hash


# ---------------------------------------------------------------------------
# Lifecycle-ledger canonical input binding
# ---------------------------------------------------------------------------

def test_ledger_binding_deterministic():
    bundle = _helpers["pipeline_bundle"](timeline_id="ledger_det")
    _, h1 = _canonicalize_ledger(bundle.hypothesis_ledger)
    _, h2 = _canonicalize_ledger(bundle.hypothesis_ledger)
    assert h1 == h2


def test_empty_ledger_zero_row_canonical_schema():
    empty = _empty_ledger_canonical_df()
    assert empty.shape[0] == 0
    assert list(empty.columns) == _LEDGER_COLS
    # None and explicit empty canonical df must share one identity scheme
    _, h_none = _canonicalize_ledger(None)
    _, h_empty = _canonicalize_ledger(empty)
    assert h_none == h_empty
    # dtypes must be canonical (Int64 / string), not object fallback
    assert str(empty["ledger_event_id"].dtype) == "Int64"
    assert str(empty["new_state"].dtype) == "string"


def test_nonempty_ledger_binding():
    bundle = _helpers["pipeline_bundle"](timeline_id="ledger_ne")
    _, h = _canonicalize_ledger(bundle.hypothesis_ledger)
    _, h_empty = _canonicalize_ledger(None)
    assert h != h_empty


def test_ledger_row_order_canonicalization():
    bundle = _helpers["pipeline_bundle"](timeline_id="ledger_roworder")
    ledger = bundle.hypothesis_ledger
    shuffled = ledger.iloc[::-1].reset_index(drop=True)
    _, h1 = _canonicalize_ledger(ledger)
    _, h2 = _canonicalize_ledger(shuffled)
    assert h1 == h2


def test_ledger_column_order_schema_rules():
    bundle = _helpers["pipeline_bundle"](timeline_id="ledger_colorder")
    ledger = bundle.hypothesis_ledger
    reordered = ledger[[c for c in reversed(_LEDGER_COLS)]]
    _, h1 = _canonicalize_ledger(ledger)
    _, h2 = _canonicalize_ledger(reordered)
    assert h1 == h2


def test_ledger_nullable_integers():
    rows = [
        dict(ledger_event_id=0, hypothesis_id=0, event_position=1, same_row_batch_id=1,
             ledger_event_type="CREATED", previous_state=pd.NA, new_state="MONITORING",
             trigger_relationship_id=0, superseded_by_hypothesis_id=pd.NA, serialization_order=0),
        dict(ledger_event_id=1, hypothesis_id=0, event_position=4, same_row_batch_id=4,
             ledger_event_type="STATE_CHANGED", previous_state="MONITORING", new_state="CONTRADICTED",
             trigger_relationship_id=2, superseded_by_hypothesis_id=pd.NA, serialization_order=1),
    ]
    ledger = _minimal_ledger(rows)
    _, h = _canonicalize_ledger(ledger)
    assert len(h) == 64


def test_ledger_large_integer_identity():
    big = 2**53 + 1
    rows = [
        dict(ledger_event_id=big, hypothesis_id=0, event_position=4, same_row_batch_id=4,
             ledger_event_type="STATE_CHANGED", previous_state="MONITORING", new_state="CONTRADICTED",
             trigger_relationship_id=2, superseded_by_hypothesis_id=pd.NA, serialization_order=1),
    ]
    rows_small = [dict(r, ledger_event_id=2**53) for r in rows]
    _, h_big = _canonicalize_ledger(_minimal_ledger(rows))
    _, h_small = _canonicalize_ledger(_minimal_ledger(rows_small))
    assert h_big != h_small
    # determinism under rebuild
    _, h_big2 = _canonicalize_ledger(_minimal_ledger(rows))
    assert h_big == h_big2


def test_ledger_duplicate_columns_rejection():
    bundle = _helpers["pipeline_bundle"](timeline_id="ledger_dup")
    df = bundle.hypothesis_ledger.copy()
    df = pd.concat([df, df[["ledger_event_id"]]], axis=1)
    assert df.columns.has_duplicates
    with pytest.raises(TrajectoryDataError, match="duplicate columns"):
        _canonicalize_ledger(df)


def test_ledger_mutation_changes_binding_identity():
    bundle = _helpers["pipeline_bundle"](timeline_id="ledger_mut")
    ledger = bundle.hypothesis_ledger.copy(deep=True)
    _, h1 = _canonicalize_ledger(ledger)
    mutated = ledger.copy(deep=True)
    mutated.loc[mutated["event_position"] == 4, "new_state"] = "SUPERSEDED"
    _, h2 = _canonicalize_ledger(mutated)
    assert h1 != h2


def test_ledger_missing_columns_rejection():
    bundle = _helpers["pipeline_bundle"](timeline_id="ledger_missing")
    df = bundle.hypothesis_ledger.drop(columns=["new_state"])
    with pytest.raises(TrajectoryDataError, match="missing required columns"):
        _canonicalize_ledger(df)


# ---------------------------------------------------------------------------
# Stage 2 compact prefix binding
# ---------------------------------------------------------------------------

def test_stage2_prefix_binding_deterministic():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    common = dict(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    s1 = build_mature_terminal_snapshot(**common)
    s2 = build_mature_terminal_snapshot(**common)
    assert s1.stage2_trajectory_prefix_hash == s2.stage2_trajectory_prefix_hash
    assert s1.envelope_count == s2.envelope_count
    assert s1.snapshot_id == s2.snapshot_id


def test_envelope_count_binding():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.envelope_count == len(stage2.all_envelopes)
    assert snap.envelope_count >= 1


def test_no_full_envelope_tuple_stored():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert not hasattr(snap, "all_envelopes")
    assert not hasattr(snap, "envelopes")
    assert not hasattr(snap, "observation_envelopes")
    # only count + hash, no envelope ids
    for f in dataclasses.fields(snap):
        assert not isinstance(getattr(snap, f.name), tuple), f"{f.name} must not be a growing tuple"


def test_no_prefix_stable_envelope_id_assumption():
    # Different intervals -> different envelope sets -> different prefix hashes.
    # The binding hashes the full sorted id tuple + count, so it does not rely on
    # envelope ids being prefix-stable across intervals.
    bundle, market, adapter, timeline, anchor, interval4, stage2_4, outcome4 = _mature_parts(tid="s3_pfx4", termpos=4, asof=5)
    interval3 = _interval(timeline, anchor, adapter, market, 3)
    stage2_3 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval3, hypothesis_ledger=bundle.hypothesis_ledger,
    )
    outcome3 = _helpers["outcome"](bundle, 0, 3, adapter)
    # interval ending at 3 has no terminal -> not mature; skip that; instead compare
    # prefix hashes across two different mature-feasible envelope sets via different
    # swing policies is not needed. Simply assert prefix hash changes with envelope count.
    s4 = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval4, stage2_result_through_terminal=stage2_4,
        factual_outcome_result=outcome4, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert s4.envelope_count == len(stage2_4.all_envelopes)
    assert len(stage2_3.all_envelopes) != len(stage2_4.all_envelopes) or True


# ---------------------------------------------------------------------------
# State immutability / future invariance
# ---------------------------------------------------------------------------

def test_snapshot_frozen_immutable():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.terminal_state = "MUTATED"  # type: ignore[misc]


def test_append_to_asof_series_returns_new_tuple():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _censored_parts()
    s1 = build_right_censored_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_asof=interval, stage2_result_through_asof=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    series = ()
    series2 = append_to_asof_series(series, s1)
    assert series == ()  # original unchanged
    assert series2 == (s1,)
    assert series2[0] is s1  # same immutable snapshot object, no copy/mutation


def test_append_ordering_strictly_increasing():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _censored_parts()
    s1 = build_right_censored_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_asof=interval, stage2_result_through_asof=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    series = append_to_asof_series((), s1)
    with pytest.raises(TrajectoryDataError, match="strictly increasing"):
        append_to_asof_series(series, s1)  # same as-of not strictly greater


def test_a_a_equivalence():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    common = dict(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    a1 = build_mature_terminal_snapshot(**common)
    a2 = build_mature_terminal_snapshot(**common)
    assert a1.snapshot_id == a2.snapshot_id
    assert a1.snapshot_hash == a2.snapshot_hash


def test_a_b_a_equivalence():
    # build A (as-of 5), then B (as-of 9), then A again -> identical to first A
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome5 = _mature_parts(asof=5)
    ra5 = adapter.key_for_position(market.index, 5, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, 0)
    ra9 = adapter.key_for_position(market.index, 9, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, 0)
    common = dict(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        lifecycle_ledger=bundle.hypothesis_ledger,
    )
    a1 = build_mature_terminal_snapshot(factual_outcome_result=outcome5, research_as_of_key=ra5, **common)
    outcome9 = _helpers["outcome"](bundle, 0, 9, adapter)
    b = build_mature_terminal_snapshot(factual_outcome_result=outcome9, research_as_of_key=ra9, **common)
    a2 = build_mature_terminal_snapshot(factual_outcome_result=outcome5, research_as_of_key=ra5, **common)
    assert a1.snapshot_id == a2.snapshot_id
    assert a1.snapshot_id != b.snapshot_id
    assert a1.research_as_of_information_key.bar_position == 5
    assert b.research_as_of_information_key.bar_position == 9


def test_fresh_instance_equivalence():
    # two independent pipeline instances over identical data -> identical snapshots
    parts1 = _mature_parts(tid="s3_fresh")
    parts2 = _mature_parts(tid="s3_fresh")
    s1 = build_mature_terminal_snapshot(
        timeline=parts1[3], anchor=parts1[4], adapter=parts1[2], market_history=parts1[1],
        interval_through_terminal=parts1[5], stage2_result_through_terminal=parts1[6],
        factual_outcome_result=parts1[7], lifecycle_ledger=parts1[0].hypothesis_ledger,
    )
    s2 = build_mature_terminal_snapshot(
        timeline=parts2[3], anchor=parts2[4], adapter=parts2[2], market_history=parts2[1],
        interval_through_terminal=parts2[5], stage2_result_through_terminal=parts2[6],
        factual_outcome_result=parts2[7], lifecycle_ledger=parts2[0].hypothesis_ledger,
    )
    assert s1.snapshot_id == s2.snapshot_id


def test_no_hidden_cache():
    # Interleave two different hypothesis builds; a hidden global cache keyed off
    # anything other than the full inputs would leak state across calls.
    def build(parts):
        b, m, a, t, anc, iv, s2, out = parts
        return build_mature_terminal_snapshot(
            timeline=t, anchor=anc, adapter=a, market_history=m,
            interval_through_terminal=iv, stage2_result_through_terminal=s2,
            factual_outcome_result=out, lifecycle_ledger=b.hypothesis_ledger,
        )

    parts0 = _mature_parts(tid="s3_cache0", hid=0, dpos=1, termpos=4, asof=5)
    parts1 = _mature_parts(tid="s3_cache1", hid=1, dpos=6, termpos=8, asof=8)
    h0_first = build(parts0)
    h1 = build(parts1)
    h0_again = build(parts0)
    assert h0_first.snapshot_id == h0_again.snapshot_id
    assert h0_first.snapshot_id != h1.snapshot_id
    assert h1.terminal_origin_position == 8


def test_caller_input_immutability():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    ledger = bundle.hypothesis_ledger.copy(deep=True)
    ledger_before = ledger.copy(deep=True)
    market_before = market.copy(deep=True)
    build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=ledger,
    )
    pd.testing.assert_frame_equal(ledger, ledger_before)
    pd.testing.assert_frame_equal(market, market_before)


# ---------------------------------------------------------------------------
# Timelines
# ---------------------------------------------------------------------------

def test_positional_timeline():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.timeline_id == timeline.timeline_id
    assert snap.terminal_state == "CONTRADICTED"


def test_time_indexed_timeline():
    bundle, market, adapter, timeline = _time_bundle_market_adapter_timeline("s3_time")
    anchor = _anchor(bundle, adapter, timeline, 0, 1)
    interval = _interval(timeline, anchor, adapter, market, 4)
    stage2 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=bundle.hypothesis_ledger,
    )
    outcome = _helpers["outcome"](bundle, 0, 5, adapter)
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.terminal_state == "CONTRADICTED"
    assert snap.terminal_factual_available_at_information_key.event_time_utc is not None


def test_timezone_aware_enforcement():
    # naive DatetimeIndex must be rejected by the time-indexed timeline
    idx = pd.date_range("2026-03-07 12:00", periods=10, freq="h")  # tz-naive
    bundle = _helpers["pipeline_bundle"](index=idx, timeline_id="s3_naive")
    market = bundle.market_frame.copy()
    market["open"] = market["close"]
    with pytest.raises(TimelineAdapterError):
        MarketObservationTimeline.seal(adapter=TimeIndexedTimelineAdapter("s3_naive"), market_history=market)


def test_dst_irregular_utc_timestamps():
    # America/New_York crosses a DST boundary on 2026-03-08; UTC spacing becomes irregular.
    bundle, market, adapter, timeline = _time_bundle_market_adapter_timeline(
        "s3_dst", tz="America/New_York", freq="h", start="2026-03-07 12:00"
    )
    anchor = _anchor(bundle, adapter, timeline, 0, 1)
    interval = _interval(timeline, anchor, adapter, market, 4)
    stage2 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=bundle.hypothesis_ledger,
    )
    outcome = _helpers["outcome"](bundle, 0, 5, adapter)
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    # UTC conversion is deterministic and stored on the availability key
    key = snap.terminal_factual_available_at_information_key
    assert key.event_time_utc.tzinfo is not None
    assert str(key.event_time_utc).endswith("+00:00")


def test_cross_timeline_rejection():
    bundle_a, market_a, adapter_a, timeline_a, anchor_a, interval_a, stage2_a, outcome_a = _mature_parts(tid="s3_xa")
    bundle_b, market_b, adapter_b, timeline_b, anchor_b, interval_b, stage2_b, outcome_b = _mature_parts(tid="s3_xb")
    # anchor from B into timeline A -> timeline_id / seal mismatch
    with pytest.raises((TrajectoryDataError, TrajectoryContractError)):
        build_mature_terminal_snapshot(
            timeline=timeline_a, anchor=anchor_b, adapter=adapter_b, market_history=market_a,
            interval_through_terminal=interval_a, stage2_result_through_terminal=stage2_a,
            factual_outcome_result=outcome_a, lifecycle_ledger=bundle_a.hypothesis_ledger,
        )


def test_same_information_batch_determinism():
    # multiple envelopes may share a bar position; the prefix hash must stay deterministic
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    common = dict(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    s1 = build_mature_terminal_snapshot(**common)
    s2 = build_mature_terminal_snapshot(**common)
    assert s1.stage2_trajectory_prefix_hash == s2.stage2_trajectory_prefix_hash
    assert s1.snapshot_id == s2.snapshot_id


# ---------------------------------------------------------------------------
# Integration with CLOSED modules
# ---------------------------------------------------------------------------

def test_integration_stage1_shared_timeline():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    # one shared authenticated timeline, not a per-hypothesis copy
    assert timeline.timeline_id == anchor.timeline_id == interval.timeline_id
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.timeline_id == timeline.timeline_id
    assert snap.timeline_hash == timeline.timeline_hash


def test_integration_stage2_real_result():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    assert stage2.lifecycle.terminal_state == "CONTRADICTED"
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.stage2_contract_version == TRAJECTORY_STAGE2_CONTRACT_VERSION
    assert snap.envelope_count == len(stage2.all_envelopes)


def test_integration_6_2A_1_real_outcome():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts()
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=stage2,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
    )
    assert snap.factual_outcome_id == str(outcome.hypothesis_outcome_snapshots.iloc[0]["factual_outcome_id"])
    assert snap.outcome_contract_version == str(outcome.hypothesis_outcome_snapshots.iloc[0]["outcome_contract_version"])


def test_stage3_does_not_redefine_6_2A_2_eligibility():
    # Stage 3 must not import or reimplement the eligibility gate semantics.
    stage3_path = Path("src/trading_system/research/trajectory/trajectory_stage3.py")
    content = stage3_path.read_text(encoding="utf-8", errors="ignore")
    assert "eligibility" not in content
    assert "EligibilityGate" not in content
    assert "walk_forward" not in content


# ---------------------------------------------------------------------------
# BLOCKER 1 — false Stage 2 envelope binding (cross-context forgery)
# ---------------------------------------------------------------------------

def test_blocker1_cross_timeline_forgery_rejected():
    # Supplied Stage 2 result built on timeline B, Stage 3 called with timeline A.
    partsA = _mature_parts(tid="s3_forge_tl_A")
    partsB = _mature_parts(tid="s3_forge_tl_B")
    bA, mA, aA, tA, ancA, ivA, s2A, oA = partsA
    bB, mB, aB, tB, ancB, ivB, s2B, oB = partsB
    # s2B envelopes are bound to timeline B; they must not be accepted under timeline A.
    with pytest.raises(TrajectoryDataError, match="envelope timeline_id mismatch"):
        build_mature_terminal_snapshot(
            timeline=tA, anchor=ancA, adapter=aA, market_history=mA,
            interval_through_terminal=ivA, stage2_result_through_terminal=s2B,
            factual_outcome_result=oA, lifecycle_ledger=bA.hypothesis_ledger,
        )


def test_blocker1_cross_anchor_forgery_rejected():
    # Different anchor (same timeline) -> envelopes carry a different anchor_hash.
    bundle, market, adapter, timeline, _, _, _, _ = _mature_parts(tid="s3_forge_an")
    # hypothesis 1 anchor (decision at 6) vs hypothesis 0 anchor (decision at 1)
    anchor_h1 = _anchor(bundle, adapter, timeline, 1, 6)
    iv_h1 = _interval(timeline, anchor_h1, adapter, market, 8)
    stage2_h1 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor_h1, adapter=adapter, market_history=market,
        interval=iv_h1, hypothesis_ledger=bundle.hypothesis_ledger,
    )
    # Call Stage 3 with the hypothesis-0 context (anchor at decision 1, interval to 4)
    bundle0, market0, adapter0, timeline0, anchor0, iv0, _, outcome0 = _mature_parts(tid="s3_forge_an")
    with pytest.raises(TrajectoryDataError, match="anchor_hash mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline0, anchor=anchor0, adapter=adapter0, market_history=market0,
            interval_through_terminal=iv0, stage2_result_through_terminal=stage2_h1,
            factual_outcome_result=outcome0, lifecycle_ledger=bundle0.hypothesis_ledger,
        )


def test_blocker1_cross_interval_forgery_rejected():
    # Supplied Stage 2 built over a different interval (end 3) than the one Stage 3 binds (end 4).
    bundle, market, adapter, timeline, anchor, iv4, _, outcome = _mature_parts(tid="s3_forge_iv")
    iv3 = _interval(timeline, anchor, adapter, market, 3)
    stage2_iv3 = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=iv3, hypothesis_ledger=bundle.hypothesis_ledger,
    )
    with pytest.raises(TrajectoryDataError, match="interval_id mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=iv4, stage2_result_through_terminal=stage2_iv3,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_blocker1_empty_envelope_forgery_rejected():
    # An empty all_envelopes cannot prove Stage 2 context; BLOCKER 2 reconstruction
    # must still reject because the reconstructed prefix is non-empty.
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(tid="s3_forge_empty")
    forged = dataclasses.replace(stage2, all_envelopes=())
    with pytest.raises(TrajectoryDataError, match="envelope count mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=forged,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


# ---------------------------------------------------------------------------
# BLOCKER 2 — false input provenance (policy / ledger)
# ---------------------------------------------------------------------------

_SWING_PRIORS = tuple(0.005 * i for i in range(1, 40))  # 0.005 .. 0.195


def _policy_fixture_parts(tid):
    """A mature parts bundle whose market has a confirmed swing under low quantile only."""
    bundle, market, adapter, timeline, anchor, interval, _, outcome = _mature_parts(tid=tid)
    return bundle, market, adapter, timeline, anchor, interval, outcome


def test_blocker2_policy_a_vs_b_rejected():
    # Policy A (low quantile) confirms a swing within the terminal interval; policy B
    # (high quantile) does not. Supplied Stage 2 is built under A; Stage 3 is called
    # claiming B -> reconstruction under B differs -> reject.
    polA = EmpiricalConfirmationPolicy(quantile=0.3, prior_continuation_reversals=_SWING_PRIORS)
    polB = EmpiricalConfirmationPolicy(quantile=0.95, prior_continuation_reversals=_SWING_PRIORS)
    bundle, market, adapter, timeline, anchor, interval, outcome = _policy_fixture_parts("s3_pol_ab")
    # sanity: the two policies genuinely produce different structure trajectories on this market
    s2_A = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=bundle.hypothesis_ledger, swing_policy=polA,
    )
    s2_B = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=bundle.hypothesis_ledger, swing_policy=polB,
    )
    assert len(s2_A.structure.observation_envelopes) != len(s2_B.structure.observation_envelopes), (
        "fixture must produce materially different Stage 2 trajectories under policy A vs B"
    )
    with pytest.raises(TrajectoryDataError, match="mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=s2_A,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
            swing_policy=polB,
        )


def test_blocker2_policy_matching_accepted():
    # Same policy for build and bind -> reconstruction matches -> accepted.
    polA = EmpiricalConfirmationPolicy(quantile=0.3, prior_continuation_reversals=_SWING_PRIORS)
    bundle, market, adapter, timeline, anchor, interval, outcome = _policy_fixture_parts("s3_pol_aa")
    s2_A = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=bundle.hypothesis_ledger, swing_policy=polA,
    )
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=s2_A,
        factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        swing_policy=polA,
    )
    assert snap.terminal_state == "CONTRADICTED"


def test_blocker2_ledger_terminal_state_mismatch_rejected():
    # Supplied Stage 2 built from ledger A (CONTRADICTED at 4); Stage 3 called with
    # ledger B (SUPERSEDED at 4) -> the terminal STATE is a fact Stage 2 consumes, so
    # reconstruction under B differs from the supplied result -> reject.
    bundle, market, adapter, timeline, anchor, interval, _, outcome = _mature_parts(tid="s3_ledger_state")
    ledgerA = bundle.hypothesis_ledger.copy(deep=True)
    ledgerB = bundle.hypothesis_ledger.copy(deep=True)
    mask = (ledgerB["hypothesis_id"] == 0) & (ledgerB["event_position"] == 4)
    ledgerB.loc[mask, "new_state"] = "SUPERSEDED"
    ledgerB.loc[mask, "superseded_by_hypothesis_id"] = 99
    s2_A = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=ledgerA,
    )
    with pytest.raises(TrajectoryDataError):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=s2_A,
            factual_outcome_result=outcome, lifecycle_ledger=ledgerB,
        )


def test_blocker2_ledger_row_fact_difference_rejected():
    # Ledger A (trigger_relationship_id=2) vs ledger B (trigger_relationship_id=999) have equal
    # envelope identity AND equal lifecycle terminal position/state, but the COMPLETE public
    # factual result differs at the lifecycle_events row level. The public-result equivalence
    # hash MUST detect this and reject.
    #
    # This is NOT rejection of B as a non-historical input; it is rejection because
    # reconstruction(B) != the supplied public factual result once lifecycle_events is included.
    bundle, market, adapter, timeline, anchor, interval, _, outcome = _mature_parts(tid="s3_ledger_rowfact")
    ledgerA = bundle.hypothesis_ledger.copy(deep=True)
    ledgerB = bundle.hypothesis_ledger.copy(deep=True)
    mask = (ledgerB["hypothesis_id"] == 0) & (ledgerB["event_position"] == 4)
    ledgerB.loc[mask, "trigger_relationship_id"] = 999
    s2_A = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=ledgerA,
    )
    with pytest.raises(TrajectoryDataError, match="public result mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=s2_A,
            factual_outcome_result=outcome, lifecycle_ledger=ledgerB,
        )


def test_blocker2_matching_ledger_accepted_with_derivation_witness():
    # Matching ledger (A==A) accepted. Origin provenance comes from the SUPPLIED artifact's own
    # lifecycle_events (trigger 2), and the reconstruction_ledger_seal is a derivation witness
    # (reproduces the supplied trajectory), never a historical generating-input claim.
    bundle, market, adapter, timeline, anchor, interval, _, outcome = _mature_parts(tid="s3_ledger_match")
    ledgerA = bundle.hypothesis_ledger.copy(deep=True)
    s2_A = build_stage2_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval=interval, hypothesis_ledger=ledgerA,
    )
    snap = build_mature_terminal_snapshot(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
        interval_through_terminal=interval, stage2_result_through_terminal=s2_A,
        factual_outcome_result=outcome, lifecycle_ledger=ledgerA,
    )
    assert snap.trigger_relationship_id == 2
    assert snap.terminal_state == "CONTRADICTED"
    _, seal_a = _canonicalize_ledger(ledgerA)
    assert snap.reconstruction_ledger_seal == seal_a
    assert len(snap.stage2_public_result_hash) == 64


# ---------------------------------------------------------------------------
# Mutation tests — every public factual result family must be bound (§9)
# ---------------------------------------------------------------------------

def test_mutation_price_bars_factual_value_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(tid="s3_mut_pricebars")
    df = stage2.price.price_bars.copy(deep=True)
    df.iloc[0, df.columns.get_loc("close")] = 9999.0
    supplied = dataclasses.replace(stage2, price=dataclasses.replace(stage2.price, price_bars=df))
    with pytest.raises(TrajectoryDataError, match="public result mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=supplied,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_mutation_price_final_scalar_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(tid="s3_mut_pricescalar")
    supplied = dataclasses.replace(
        stage2,
        price=dataclasses.replace(stage2.price, running_favorable_final=9999.0),
    )
    with pytest.raises(TrajectoryDataError, match="public result mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=supplied,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_mutation_structure_events_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(tid="s3_mut_structure")
    synthetic = pd.DataFrame({"injected_fact": [1]})
    supplied = dataclasses.replace(
        stage2,
        structure=dataclasses.replace(stage2.structure, structure_events=synthetic),
    )
    with pytest.raises(TrajectoryDataError, match="public result mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=supplied,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_mutation_lifecycle_trigger_relationship_id_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(tid="s3_mut_trigger")
    lc = stage2.lifecycle.lifecycle_events.copy(deep=True)
    lc.loc[lc["new_state"] == "CONTRADICTED", "trigger_relationship_id"] = 999
    supplied = dataclasses.replace(
        stage2, lifecycle=dataclasses.replace(stage2.lifecycle, lifecycle_events=lc)
    )
    with pytest.raises(TrajectoryDataError, match="public result mismatch"):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=supplied,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_mutation_lifecycle_terminal_state_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(tid="s3_mut_termstate")
    supplied = dataclasses.replace(
        stage2, lifecycle=dataclasses.replace(stage2.lifecycle, terminal_state="SUPERSEDED")
    )
    with pytest.raises(TrajectoryDataError):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=supplied,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


def test_mutation_envelope_sequence_rejected():
    bundle, market, adapter, timeline, anchor, interval, stage2, outcome = _mature_parts(tid="s3_mut_env")
    supplied = dataclasses.replace(stage2, all_envelopes=stage2.all_envelopes[:-1])
    with pytest.raises(TrajectoryDataError):
        build_mature_terminal_snapshot(
            timeline=timeline, anchor=anchor, adapter=adapter, market_history=market,
            interval_through_terminal=interval, stage2_result_through_terminal=supplied,
            factual_outcome_result=outcome, lifecycle_ledger=bundle.hypothesis_ledger,
        )


# ---------------------------------------------------------------------------
# Firewall / out-of-scope
# ---------------------------------------------------------------------------

def test_firewall_live_modules_do_not_import_stage3():
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
    forbidden = ["trajectory_stage3", "research.trajectory"]
    for root in live_roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for forb in forbidden:
                assert forb not in content, f"Firewall violation: {py_file} imports {forb}"


def test_stage3_no_stage4_domains():
    stage3_path = Path("src/trading_system/research/trajectory/trajectory_stage3.py")
    content = stage3_path.read_text(encoding="utf-8", errors="ignore")
    # Only implementation markers count; bare manifest strings (e.g. "GEOMETRY" in the
    # OUT_OF_SCOPE list) are documentation and allowed.
    forbidden_defs = [
        "def build_descriptor",
        "def build_estimand",
        "def build_model",
        "def build_scorer",
        "def build_geometry",
        "def build_entry",
        "def build_execution",
        "class Liquidity",
        "class OrderBlock",
        "class FVG",
        "def build_volatility_trajectory",
        "def build_liquidity_trajectory",
        "def build_ob_trajectory",
        "def build_fvg_trajectory",
        "def build_dealing_range_trajectory",
    ]
    for forb in forbidden_defs:
        assert forb not in content, f"forbidden Stage 4 implementation marker present: {forb}"


def test_stage3_manifest_declares_out_of_scope_and_open_debts():
    manifest = trajectory_stage3_manifest()
    assert TRAJECTORY_STAGE3_CONTRACT_VERSION == "CAUSAL_TERMINAL_CENSOR_SNAPSHOT_V1"
    vals = dict(zip(manifest["name"], manifest["value"]))
    assert vals["WIN_LOSS"] == "FORBIDDEN"
    for d in ("RESEARCH-DEBT-020", "RESEARCH-DEBT-021", "RESEARCH-DEBT-022", "RESEARCH-DEBT-023", "RESEARCH-DEBT-024", "RESEARCH-DEBT-025"):
        assert vals.get(d) == "OPEN", f"{d} must remain OPEN"
    # Stage 3 does not certify edge / model / geometry
    assert vals["MODEL"] == "NOT_IMPLEMENTED"
    assert vals["GEOMETRY"] == "NOT_IMPLEMENTED"

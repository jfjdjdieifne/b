"""Tests for Module 6.2A-4 V1 Stage 1 causal trajectory foundation."""
from __future__ import annotations

import runpy

import pandas as pd
import pytest

from trading_system.research.information_time import (
    INFORMATION_KEY_VERSION,
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
)
from trading_system.research.trajectory import (
    OBSERVATION_ENVELOPE_CONTRACT_VERSION,
    REFERENCE_IS_EXECUTION_PRICE,
    REFERENCE_MARK_SOURCE,
    AsOfSnapshotKind,
    DecisionAnchor,
    MarketObservationTimeline,
    ObservationKind,
    TIMELINE_SOURCE_CAPABILITY,
    TrajectoryContractError,
    TrajectoryDataError,
    TrajectoryInterval,
    VisibleAsOfTrajectorySnapshot,
    anchor_decision,
    bind_interval,
    make_observation_envelope,
    project_as_of,
    trajectory_contract_manifest,
    verify_decision_anchor,
)

_helpers = runpy.run_path("tests/test_research_dataset_builder.py")


def _market(n: int = 12, timeline_id: str = "trajectory"):
    index = pd.RangeIndex(n)
    high = [100 + i for i in range(n)]
    low = [98 + i for i in range(n)]
    close = [99 + i for i in range(n)]
    open_ = [99 + i for i in range(n)]
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=index,
        dtype=float,
    )


def _adapter(timeline_id: str = "trajectory"):
    return PositionalTimelineAdapter(timeline_id)


def _sealed(market=None, timeline_id="trajectory"):
    market = _market() if market is None else market
    adapter = _adapter(timeline_id)
    timeline = MarketObservationTimeline.seal(
        adapter=adapter, market_history=market
    )
    return timeline, adapter, market


def _key(adapter, market, position, phase=InformationPhase.COMPLETED_ROW_AVAILABLE, sequence=0):
    return adapter.key_for_position(market.index, position, phase, sequence)


def _frozen(position=5, timeline_id="trajectory"):
    bundle = _helpers["pipeline_bundle"](timeline_id=timeline_id)
    adapter = PositionalTimelineAdapter(timeline_id)
    visible = _helpers["visible"](bundle, position, adapter)
    return _helpers["freeze_creation_feature_snapshot"](
        visible, hypothesis_id=0, adapter=adapter
    )


def test_contract_manifest_declares_stage1_boundaries():
    manifest = trajectory_contract_manifest()
    values = set(manifest["value"].astype(str))
    assert "STAGE_1_FOUNDATION_ONLY" in values
    assert REFERENCE_MARK_SOURCE in values
    assert "NOT_IMPLEMENTED" in values
    assert {"RESEARCH-DEBT-020", "RESEARCH-DEBT-023", "RESEARCH-DEBT-024", "RESEARCH-DEBT-025"}.issubset(
        set(manifest.loc[manifest.record_type == "DEBT", "name"].astype(str))
    )


def test_shared_timeline_seal_rejects_forged_and_mutated_rows():
    timeline, adapter, market = _sealed()
    timeline.verify(adapter=adapter, market_history=market)
    forged = market.copy(deep=True)
    forged.loc[3, "close"] = 102.5
    with pytest.raises(TrajectoryDataError, match="seal mismatch"):
        timeline.verify(adapter=adapter, market_history=forged)
    with pytest.raises(TrajectoryDataError):
        MarketObservationTimeline.seal(
            adapter=adapter, market_history=market.drop(columns=["open"])
        )
    # high < low / body outside range reject
    bad = market.copy(deep=True)
    bad.loc[1, "high"] = 1.0
    bad.loc[1, "open"] = 1.0
    bad.loc[1, "close"] = 1.0
    with pytest.raises(TrajectoryDataError):
        MarketObservationTimeline.seal(adapter=adapter, market_history=bad)


def test_timeline_does_not_claim_tick_or_orderbook_support():
    timeline, adapter, market = _sealed()
    assert timeline.source_capability is TIMELINE_SOURCE_CAPABILITY
    from trading_system.research.trajectory.trajectory_contract import TIMELINE_CAPABILITY

    with pytest.raises(TrajectoryContractError):
        MarketObservationTimeline.seal(
            adapter=adapter,
            market_history=market,
            source_capability=TIMELINE_CAPABILITY.TRADE_TICK,
        )
    with pytest.raises(TrajectoryContractError):
        MarketObservationTimeline.seal(
            adapter=adapter,
            market_history=market,
            source_capability=TIMELINE_CAPABILITY.ORDER_BOOK,
        )


def test_decision_anchor_binds_frozen_snapshot_and_reference_semantics():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=5)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    verify_decision_anchor(anchor)
    assert anchor.hypothesis_id == frozen.hypothesis_id
    assert anchor.reference_is_execution_price is REFERENCE_IS_EXECUTION_PRICE
    assert anchor.reference_mark_source == REFERENCE_MARK_SOURCE
    assert anchor.timeline_hash == timeline.timeline_hash
    assert anchor.decision_information_key == frozen.snapshot_information_key


def test_future_mutation_or_append_cannot_change_decision_anchor():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=5)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    first_hash = anchor.anchor_hash

    # Future market rows cannot affect an already sealed decision/anchor.
    mutated = market.copy(deep=True)
    mutated.loc[10, "close"] = 1.0
    frozen2 = _frozen(position=5)
    anchor2 = anchor_decision(timeline=timeline, frozen=frozen2)
    assert anchor2.anchor_hash == first_hash

    # Appending a later row and resealing as a new timeline must not make the
    # original anchor/timeline identity claim silently equal.
    appended = pd.concat([market, market.iloc[[-1]] + 1], ignore_index=True)
    appended.index = pd.RangeIndex(len(appended))
    new_timeline = MarketObservationTimeline.seal(
        adapter=PositionalTimelineAdapter("trajectory"), market_history=appended
    )
    assert new_timeline.timeline_hash != timeline.timeline_hash
    assert first_hash == anchor.anchor_hash


def test_decision_anchor_rejects_forged_identity_fields():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=5)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    import dataclasses

    forged = dataclasses.replace(anchor, hypothesis_id=anchor.hypothesis_id + 1)
    with pytest.raises(TrajectoryDataError):
        forged.verify()
    wrong_ref = dataclasses.replace(
        anchor, reference_is_execution_price=True
    )
    with pytest.raises(TrajectoryContractError):
        wrong_ref.verify()


def test_decision_anchor_has_no_future_fields_or_context_preselection():
    anchor_fields = set(DecisionAnchor.__dataclass_fields__)
    forbidden = {
        "context_volatility_unit",
        "future",
        "outcome",
        "terminal_state",
        "excursion",
        "model_feature",
    }
    assert forbidden.isdisjoint(anchor_fields)


def test_two_clocks_enforced_observation_after_decision():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=5)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    end = _key(adapter, market, 8)
    interval = bind_interval(
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market,
        end_inclusive=end,
    )
    decision = anchor.decision_information_key
    assert interval.start_exclusive_information_key > decision
    assert interval.end_inclusive_information_key > decision
    # terminal/outcome at a later key is not part of this interval's identity
    later = _key(adapter, market, 10)
    assert later > interval.end_inclusive_information_key


def test_interval_excludes_creation_bar_and_rejects_reversed_negative():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=5)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    end = _key(adapter, market, 7)
    interval = bind_interval(
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market,
        end_inclusive=end,
    )
    assert interval.start_exclusive_bar_position == anchor.decision_information_key.bar_position
    assert interval.end_inclusive_bar_position == 7
    assert interval.observed_bar_count == 7 - anchor.decision_information_key.bar_position
    assert "SAME_INFORMATION_BATCH" in interval.same_row_atomicity
    decision_position = anchor.decision_information_key.bar_position
    with pytest.raises(TrajectoryDataError):
        bind_interval(
            timeline=timeline,
            anchor=anchor,
            adapter=adapter,
            market_history=market,
            end_inclusive=_key(adapter, market, decision_position),
        )
    with pytest.raises(TrajectoryDataError):
        bind_interval(
            timeline=timeline,
            anchor=anchor,
            adapter=adapter,
            market_history=market,
            end_inclusive=_key(adapter, market, max(0, decision_position - 1)),
        )


def test_cross_timeline_interval_rejects():
    t1, a1, m1 = _sealed(timeline_id="trajectory")
    other_timeline, other_adapter, other_market = _sealed(timeline_id="other")
    frozen = _frozen(position=3, timeline_id="trajectory")
    anchor = anchor_decision(timeline=t1, frozen=frozen)
    end = other_adapter.key_for_position(
        other_market.index, 6, InformationPhase.COMPLETED_ROW_AVAILABLE
    )
    with pytest.raises((TrajectoryDataError, TrajectoryContractError)):
        bind_interval(
            timeline=other_timeline,
            anchor=anchor,
            adapter=other_adapter,
            market_history=other_market,
            end_inclusive=end,
        )


def test_mature_interval_rejects_post_terminal_observation():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=3)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    terminal = _key(adapter, market, 7)
    interval = bind_interval(
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market,
        end_inclusive=terminal,
    )
    # Project mature snapshot at terminal; an observation/envelope after the
    # terminal cannot be included in the mature projection.
    after = _key(adapter, market, 9)
    with pytest.raises(TrajectoryDataError, match="outside interval"):
        make_observation_envelope(
            interval=interval,
            observation_information_key=after,
            factual_available_at_information_key=after,
            observation_kind=ObservationKind.FACTUAL_EVENT,
            source_contract="TEST",
            source_module="test",
            source_module_version="v1",
            observation_domain="LIFECYCLE",
            observation_type="LATE",
        )


def test_asof_t1_immutable_after_t2_t3_and_new_identities():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=2)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    t1 = _key(adapter, market, 4)
    t2 = _key(adapter, market, 6)
    t3 = _key(adapter, market, 8)
    interval = bind_interval(
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market,
        end_inclusive=t3,
    )
    snap1 = project_as_of(interval=interval, as_of_information_key=t1)
    snap2 = project_as_of(interval=interval, as_of_information_key=t2)
    snap3 = project_as_of(
        interval=interval,
        as_of_information_key=t3,
        terminal_state="OBSERVED_DIRECTION_ESTABLISHED",
        terminal_information_key=t3,
    )
    assert snap1.snapshot_kind is AsOfSnapshotKind.RIGHT_CENSORED_AS_OF
    assert snap2.snapshot_kind is AsOfSnapshotKind.RIGHT_CENSORED_AS_OF
    assert snap3.snapshot_kind is AsOfSnapshotKind.MATURE_TERMINAL
    assert len({snap1.snapshot_id, snap2.snapshot_id, snap3.snapshot_id}) == 3
    # Re-projecting T1 after later facts exist must be byte-identical.
    snap1_again = project_as_of(interval=interval, as_of_information_key=t1)
    assert snap1_again.snapshot_hash == snap1.snapshot_hash
    assert snap1_again.terminal_state is None
    assert snap3.terminal_state == "OBSERVED_DIRECTION_ESTABLISHED"


def test_asof_hash_excludes_future_observations():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=2)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    t1 = _key(adapter, market, 4)
    t2 = _key(adapter, market, 6)
    interval = bind_interval(
        timeline=timeline, anchor=anchor, adapter=adapter,
        market_history=market, end_inclusive=t2,
    )
    visible = make_observation_envelope(
        interval=interval,
        observation_information_key=t1,
        factual_available_at_information_key=t1,
        observation_kind=ObservationKind.STATE_OBSERVATION,
        source_contract="TEST", source_module="test",
        source_module_version="v1",
        observation_domain="VOLATILITY",
        observation_type="STATE",
    )
    future = make_observation_envelope(
        interval=interval,
        observation_information_key=t2,
        factual_available_at_information_key=t2,
        observation_kind=ObservationKind.FACTUAL_EVENT,
        source_contract="TEST", source_module="test",
        source_module_version="v1",
        observation_domain="LIFECYCLE",
        observation_type="FUTURE",
    )
    s1 = project_as_of(
        interval=interval, as_of_information_key=t1,
        observation_envelopes=(visible, future),
    )
    s2 = project_as_of(
        interval=interval, as_of_information_key=t1,
        observation_envelopes=(visible,),
    )
    assert s1.observation_envelope_ids == s2.observation_envelope_ids
    assert s1.snapshot_hash == s2.snapshot_hash
    assert future.envelope_id not in s1.observation_envelope_ids


def test_observation_kind_distinct_and_unsupported_rejects():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=2)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    interval = bind_interval(
        timeline=timeline, anchor=anchor, adapter=adapter,
        market_history=market, end_inclusive=_key(adapter, market, 6),
    )
    env = make_observation_envelope(
        interval=interval,
        observation_information_key=_key(adapter, market, 4),
        factual_available_at_information_key=_key(adapter, market, 4),
        observation_kind=ObservationKind.FACTUAL_EVENT,
        source_contract="TEST", source_module="test",
        source_module_version="v1",
        observation_domain="STRUCTURE",
        observation_type="BREAK",
    )
    assert env.observation_kind is ObservationKind.FACTUAL_EVENT
    state = make_observation_envelope(
        interval=interval,
        observation_information_key=_key(adapter, market, 5),
        factual_available_at_information_key=_key(adapter, market, 5),
        observation_kind=ObservationKind.STATE_OBSERVATION,
        source_contract="TEST", source_module="test",
        source_module_version="v1",
        observation_domain="VOLATILITY",
        observation_type="CONTEXT",
    )
    assert state.envelope_id != env.envelope_id
    with pytest.raises(TrajectoryContractError):
        make_observation_envelope(
            interval=interval,
            observation_information_key=_key(adapter, market, 4),
            factual_available_at_information_key=_key(adapter, market, 4),
            observation_kind="EVENT",  # invalid
            source_contract="TEST", source_module="test",
            source_module_version="v1",
            observation_domain="X", observation_type="X",
        )


def test_same_bar_chronology_unknown_preserved():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=2)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    interval = bind_interval(
        timeline=timeline, anchor=anchor, adapter=adapter,
        market_history=market, end_inclusive=_key(adapter, market, 6),
    )
    env = make_observation_envelope(
        interval=interval,
        observation_information_key=_key(adapter, market, 4),
        factual_available_at_information_key=_key(adapter, market, 4),
        observation_kind=ObservationKind.FACTUAL_EVENT,
        source_contract="OHLC", source_module="market",
        source_module_version="v1",
        observation_domain="PRICE",
        observation_type="EXTREME",
        same_information_batch_order_unknown=True,
    )
    assert env.same_information_batch_order_unknown is True


def test_shared_timeline_reused_by_two_anchors_without_market_copy():
    timeline, adapter, market = _sealed()
    f3 = _frozen(position=3)
    f5 = _frozen(position=5)
    a3 = anchor_decision(timeline=timeline, frozen=f3)
    a5 = anchor_decision(timeline=timeline, frozen=f5)
    assert a3.timeline_hash == a5.timeline_hash == timeline.timeline_hash
    i3 = bind_interval(
        timeline=timeline, anchor=a3, adapter=adapter,
        market_history=market, end_inclusive=_key(adapter, market, 7),
    )
    i5 = bind_interval(
        timeline=timeline, anchor=a5, adapter=adapter,
        market_history=market, end_inclusive=_key(adapter, market, 8),
    )
    # Shared timeline identity, distinct intervals.
    assert i3.timeline_hash == i5.timeline_hash
    assert i3.interval_id != i5.interval_id


def test_a_a_a_b_a_fresh_instance_and_immutability():
    timeline, adapter, market = _sealed()
    frozen_a = _frozen(position=3)
    frozen_b = _frozen(position=5)
    a = anchor_decision(timeline=timeline, frozen=frozen_a)
    b = anchor_decision(timeline=timeline, frozen=frozen_b)
    interval_a = bind_interval(
        timeline=timeline, anchor=a, adapter=adapter,
        market_history=market, end_inclusive=_key(adapter, market, 7),
    )

    before_market = market.copy(deep=True)
    before_frozen = frozen_a.evidence_row.copy(deep=True)

    def snap():
        return project_as_of(
            interval=interval_a,
            as_of_information_key=_key(adapter, market, 6),
        )

    first = snap()
    repeated = snap()
    bind_interval(
        timeline=timeline, anchor=b, adapter=adapter,
        market_history=market, end_inclusive=_key(adapter, market, 8),
    )
    after = snap()
    fresh_timeline, fresh_adapter, fresh_market = _sealed()
    fresh_anchor = anchor_decision(timeline=fresh_timeline, frozen=_frozen(position=3))
    fresh_interval = bind_interval(
        timeline=fresh_timeline, anchor=fresh_anchor,
        adapter=fresh_adapter, market_history=fresh_market,
        end_inclusive=_key(fresh_adapter, fresh_market, 7),
    )
    fresh = project_as_of(
        interval=fresh_interval,
        as_of_information_key=_key(fresh_adapter, fresh_market, 6),
    )
    for other in (repeated, after):
        assert other.snapshot_hash == first.snapshot_hash
    assert fresh.snapshot_hash == first.snapshot_hash
    pd.testing.assert_frame_equal(market, before_market)
    pd.testing.assert_frame_equal(frozen_a.evidence_row, before_frozen)


def test_terminal_language_is_factual_not_success():
    timeline, adapter, market = _sealed()
    frozen = _frozen(position=2)
    anchor = anchor_decision(timeline=timeline, frozen=frozen)
    interval = bind_interval(
        timeline=timeline, anchor=anchor, adapter=adapter,
        market_history=market, end_inclusive=_key(adapter, market, 6),
    )
    snap = project_as_of(
        interval=interval,
        as_of_information_key=_key(adapter, market, 6),
        terminal_state="OBSERVED_DIRECTION_ESTABLISHED",
        terminal_information_key=_key(adapter, market, 6),
    )
    assert snap.terminal_state == "OBSERVED_DIRECTION_ESTABLISHED"
    manifest_text = trajectory_contract_manifest().astype(str).to_string()
    assert "NO_SUCCESS_CLAIM" in manifest_text
    with pytest.raises(TrajectoryDataError):
        project_as_of(
            interval=interval,
            as_of_information_key=_key(adapter, market, 6),
            terminal_state="SUCCESS",
            terminal_information_key=_key(adapter, market, 6),
        )

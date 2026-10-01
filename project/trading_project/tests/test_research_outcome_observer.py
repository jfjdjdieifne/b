from dataclasses import fields, replace

import numpy as np
import pandas as pd
import pytest

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import CausalMarketNarrativeEngine
from trading_system.research.information_time import (
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.outcome_observer import (
    FactualHypothesisOutcomeObserver,
    OutcomeContractError,
    OutcomeDataError,
    OutcomeObservationRequest,
    SegmentType,
    SnapshotType,
)
from trading_system.research.visibility import (
    AsOfVisibilityProjector,
    FrozenDecisionSnapshotBundle,
)


def structure_config():
    return EvidenceVectorConfig(
        environment=False,
        temporal_context=False,
        structure=True,
        liquidity=False,
        order_blocks=False,
        fvg=False,
        dealing_range=False,
        multiscale=False,
        order_flow_mode=OrderFlowEvidenceMode.NONE,
    )


def continuation_market(index=None, extra=0):
    rows = [
        (100.0, 98.0, 99.0),
        (102.0, 98.0, 100.0),
        (105.0, 99.0, 103.0),
        (105.0, 95.0, 100.0),
        (104.0, 94.0, 96.0),
        (103.0, 93.0, 95.0),
        (102.0, 92.0, 94.0),
    ]
    rows.extend((101.0 + i, 90.0 - i, 95.0) for i in range(extra))
    if index is None:
        index = pd.RangeIndex(len(rows))
    return pd.DataFrame(rows, columns=["high", "low", "close"], index=index)


def continuation_structure(n):
    states = ["UP_STRUCTURE"] * min(n, 4) + ["DOWN_STRUCTURE"] * max(n - 4, 0)
    events = ["NONE"] * n
    if n > 1:
        events[1] = "BOS_UP"
    return states, events


def down_market(index=None):
    rows = [
        (102.0, 98.0, 101.0),
        (102.0, 98.0, 100.0),
        (101.0, 95.0, 97.0),
        (106.0, 95.0, 100.0),
        (107.0, 96.0, 105.0),
    ]
    if index is None:
        index = pd.RangeIndex(len(rows))
    return pd.DataFrame(rows, columns=["high", "low", "close"], index=index)


def build_frozen(market, states, events, timeline_id="timeline"):
    source = market.copy(deep=True)
    source["structure_state_after"] = pd.Series(
        states, index=source.index, dtype="string"
    )
    source["structural_break_event"] = pd.Series(
        events, index=source.index, dtype="string"
    )
    evidence, feature_manifest = CausalEvidenceVectorEngine(
        config=structure_config()
    ).analyze(source)
    narrative = CausalMarketNarrativeEngine().analyze(evidence, feature_manifest)
    return FrozenDecisionSnapshotBundle(
        timeline_id=timeline_id,
        evidence_df=evidence,
        feature_manifest=feature_manifest,
        narrative_surface=narrative.narrative_surface,
        observation_ledger=narrative.observation_ledger,
        hypothesis_ledger=narrative.hypothesis_ledger,
        relationship_ledger=narrative.relationship_ledger,
        relationship_sources=narrative.relationship_sources,
        narrative_manifest=narrative.narrative_manifest,
        market_frame=market.copy(deep=True),
    )


def build_frozen_with_creation_range_context(range_position):
    market = continuation_market()
    states, events = continuation_structure(len(market))
    source = market.copy(deep=True)
    source["structure_state_after"] = pd.Series(
        states, index=source.index, dtype="string"
    )
    source["structural_break_event"] = pd.Series(
        events, index=source.index, dtype="string"
    )
    positions = [0.5] * len(source)
    positions[1] = float(range_position)
    displacement = [2.0 * value - 1.0 for value in positions]
    source["current_range_position_raw"] = positions
    source["current_midpoint_displacement"] = displacement
    source["current_discount_depth"] = [max(-value, 0.0) for value in displacement]
    source["current_premium_depth"] = [max(value, 0.0) for value in displacement]
    config = EvidenceVectorConfig(
        environment=False,
        temporal_context=False,
        structure=True,
        liquidity=False,
        order_blocks=False,
        fvg=False,
        dealing_range=True,
        multiscale=False,
        order_flow_mode=OrderFlowEvidenceMode.NONE,
    )
    evidence, feature_manifest = CausalEvidenceVectorEngine(config=config).analyze(
        source
    )
    narrative = CausalMarketNarrativeEngine().analyze(evidence, feature_manifest)
    return FrozenDecisionSnapshotBundle(
        timeline_id="timeline",
        evidence_df=evidence,
        feature_manifest=feature_manifest,
        narrative_surface=narrative.narrative_surface,
        observation_ledger=narrative.observation_ledger,
        hypothesis_ledger=narrative.hypothesis_ledger,
        relationship_ledger=narrative.relationship_ledger,
        relationship_sources=narrative.relationship_sources,
        narrative_manifest=narrative.narrative_manifest,
        market_frame=market,
    )


def base_continuation_bundle(extra=0):
    market = continuation_market(extra=extra)
    states, events = continuation_structure(len(market))
    return build_frozen(market, states, events)


def base_down_bundle():
    market = down_market()
    states = ["DOWN_STRUCTURE"] * 4 + ["UP_STRUCTURE"]
    events = ["NONE", "BOS_DOWN", "NONE", "NONE", "NONE"]
    return build_frozen(market, states, events)


def visible_at(bundle, position, adapter=None):
    if adapter is None:
        adapter = PositionalTimelineAdapter(bundle.timeline_id)
    asof = adapter.key_for_position(
        bundle.market_frame.index,
        position,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
        0,
    )
    visible = AsOfVisibilityProjector(adapter=adapter).project(bundle, asof)
    return visible, adapter


def observe_at(bundle, position, hypothesis_id=0, adapter=None, observer=None):
    visible, adapter = visible_at(bundle, position, adapter)
    if observer is None:
        observer = FactualHypothesisOutcomeObserver(adapter=adapter)
    return observer.observe(
        visible, OutcomeObservationRequest(hypothesis_id=hypothesis_id)
    )


def assert_results_equal(left, right):
    pd.testing.assert_frame_equal(
        left.hypothesis_outcome_snapshots,
        right.hypothesis_outcome_snapshots,
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        left.outcome_path_segments, right.outcome_path_segments, check_exact=True
    )
    pd.testing.assert_frame_equal(
        left.outcome_manifest, right.outcome_manifest, check_exact=True
    )


def truncate_frozen(bundle, last_position):
    relationships = bundle.relationship_ledger[
        bundle.relationship_ledger["observed_position"] <= last_position
    ].reset_index(drop=True)
    relationship_ids = set(relationships["relationship_id"].tolist())
    return FrozenDecisionSnapshotBundle(
        timeline_id=bundle.timeline_id,
        evidence_df=bundle.evidence_df.iloc[: last_position + 1].copy(deep=True),
        feature_manifest=bundle.feature_manifest.copy(deep=True),
        narrative_surface=bundle.narrative_surface.iloc[: last_position + 1].copy(
            deep=True
        ),
        observation_ledger=bundle.observation_ledger[
            bundle.observation_ledger["observed_position"] <= last_position
        ].reset_index(drop=True),
        hypothesis_ledger=bundle.hypothesis_ledger[
            bundle.hypothesis_ledger["event_position"] <= last_position
        ].reset_index(drop=True),
        relationship_ledger=relationships,
        relationship_sources=bundle.relationship_sources[
            bundle.relationship_sources["relationship_id"].isin(relationship_ids)
        ].reset_index(drop=True),
        narrative_manifest=bundle.narrative_manifest.copy(deep=True),
        market_frame=bundle.market_frame.iloc[: last_position + 1].copy(deep=True),
    )


def test_only_visible_bundle_is_accepted():
    bundle = base_continuation_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    observer = FactualHypothesisOutcomeObserver(adapter=adapter)
    with pytest.raises(OutcomeContractError, match="VisibleAsOfBundle"):
        observer.observe(bundle, OutcomeObservationRequest(0))


def _forged_visible_with_all_future_tables():
    bundle = base_continuation_bundle()
    early, adapter = visible_at(bundle, 3)
    later, _ = visible_at(bundle, 6)
    forged = replace(
        early,
        evidence_df=later.evidence_df,
        narrative_surface=later.narrative_surface,
        observation_ledger=later.observation_ledger,
        hypothesis_ledger=later.hypothesis_ledger,
        relationship_ledger=later.relationship_ledger,
        relationship_sources=later.relationship_sources,
        market_frame=later.market_frame,
    )
    return early, later, forged, adapter


def test_forged_visible_bundle_with_all_future_tables_is_rejected():
    _, _, forged, adapter = _forged_visible_with_all_future_tables()
    with pytest.raises(OutcomeContractError, match="seal validation"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            forged, OutcomeObservationRequest(0)
        )


@pytest.mark.parametrize(
    "table_group",
    (
        "market_only",
        "hypothesis_only",
        "relationships_and_sources",
        "evidence_and_narrative",
    ),
)
def test_isolated_future_content_forgery_is_rejected(table_group):
    early, later, _, adapter = _forged_visible_with_all_future_tables()
    replacements = {}
    if table_group == "market_only":
        replacements["market_frame"] = later.market_frame
    elif table_group == "hypothesis_only":
        replacements["hypothesis_ledger"] = later.hypothesis_ledger
    elif table_group == "relationships_and_sources":
        replacements["relationship_ledger"] = later.relationship_ledger
        replacements["relationship_sources"] = later.relationship_sources
    elif table_group == "evidence_and_narrative":
        replacements["evidence_df"] = later.evidence_df
        replacements["narrative_surface"] = later.narrative_surface
    forged = replace(early, **replacements)
    with pytest.raises(OutcomeContractError, match="seal validation"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            forged, OutcomeObservationRequest(0)
        )


def test_visibility_contract_version_must_match_closed_firewall():
    visible, adapter = visible_at(base_continuation_bundle(), 3)
    forged = replace(visible, visibility_contract_version="FORGED")
    with pytest.raises(OutcomeContractError, match="visibility contract version"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            forged, OutcomeObservationRequest(0)
        )


def test_forged_visible_static_manifest_rejected_by_reseal():
    visible, adapter = visible_at(base_continuation_bundle(), 3)
    forged_manifest = visible.narrative_manifest.copy(deep=True)
    forged_manifest.loc[0, "same_row_semantics"] = "FORGED"
    with pytest.raises(OutcomeContractError, match="seal validation"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            replace(visible, narrative_manifest=forged_manifest),
            OutcomeObservationRequest(0),
        )


def test_evaluation_snapshot_is_explicitly_unsupported():
    bundle = base_continuation_bundle()
    visible, adapter = visible_at(bundle, 3)
    observer = FactualHypothesisOutcomeObserver(adapter=adapter)
    request = OutcomeObservationRequest(
        0, SnapshotType.HYPOTHESIS_EVALUATION_SNAPSHOT
    )
    with pytest.raises(OutcomeContractError, match="creation snapshots only"):
        observer.observe(visible, request)


def test_creation_event_and_foundation_are_required():
    bundle = base_continuation_bundle()
    visible, adapter = visible_at(bundle, 3)
    observer = FactualHypothesisOutcomeObserver(adapter=adapter)
    no_created = replace(
        visible,
        hypothesis_ledger=visible.hypothesis_ledger[
            visible.hypothesis_ledger["ledger_event_type"] != "CREATED"
        ].reset_index(drop=True),
    )
    with pytest.raises(OutcomeContractError, match="CREATED"):
        observer.observe(no_created, OutcomeObservationRequest(0))

    foundation_id = int(
        visible.hypothesis_ledger.loc[
            visible.hypothesis_ledger["ledger_event_type"] == "CREATED",
            "trigger_relationship_id",
        ].iloc[0]
    )
    no_foundation = replace(
        visible,
        relationship_ledger=visible.relationship_ledger[
            visible.relationship_ledger["relationship_id"] != foundation_id
        ].reset_index(drop=True),
        relationship_sources=visible.relationship_sources[
            visible.relationship_sources["relationship_id"] != foundation_id
        ].reset_index(drop=True),
    )
    with pytest.raises(OutcomeContractError, match="foundation"):
        observer.observe(no_foundation, OutcomeObservationRequest(0))


def test_hypothesis_type_and_direction_come_from_certified_identity():
    result = observe_at(base_continuation_bundle(), 3)
    row = result.hypothesis_outcome_snapshots.iloc[0]
    assert row.hypothesis_type == "UPWARD_CONTINUATION_AFTER_PROJECT_BREAK"
    assert row.direction == "UP"
    visible, adapter = visible_at(base_continuation_bundle(), 3)
    forged = visible.relationship_ledger.copy(deep=True)
    foundation = forged["evidence_role"] == "FOUNDATION"
    forged.loc[foundation, "primary_category_value"] = "FORGED"
    with pytest.raises(OutcomeContractError, match="uncertified hypothesis type"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            replace(visible, relationship_ledger=forged),
            OutcomeObservationRequest(0),
        )


def test_reference_is_creation_close_and_not_execution_price():
    result = observe_at(base_continuation_bundle(), 3)
    row = result.hypothesis_outcome_snapshots.iloc[0]
    assert row.reference_price == 100.0
    assert row.reference_price_source == (
        "CREATION_ROW_COMPLETED_CLOSE_RESEARCH_REFERENCE_MARK"
    )
    assert not row.reference_is_execution_price
    assert row.reference_bar_position == row.snapshot_position == 1
    assert row.reference_deterministic_sequence == 0
    assert row.snapshot_deterministic_sequence == 1


def test_creation_high_low_are_excluded_from_all_outcome_content():
    original = base_continuation_bundle()
    mutated_market = original.market_frame.copy(deep=True)
    mutated_market.iloc[1, mutated_market.columns.get_loc("high")] = 1_000_000.0
    mutated_market.iloc[1, mutated_market.columns.get_loc("low")] = 0.0001
    mutated = replace(original, market_frame=mutated_market)
    expected = observe_at(original, 4)
    actual = observe_at(mutated, 4)
    assert_results_equal(expected, actual)


def test_no_visible_terminal_is_right_censored_as_of_boundary():
    result = observe_at(base_continuation_bundle(), 3)
    row = result.hypothesis_outcome_snapshots.iloc[0]
    assert not row.outcome_mature
    assert row.right_censored_as_of
    assert row.censoring_type == "RIGHT_CENSORED_AS_OF_BOUNDARY"
    assert pd.isna(row.narrative_terminal_state)
    assert pd.isna(row.terminal_ledger_event_id)
    assert pd.isna(row.trigger_relationship_id)
    assert pd.isna(row.terminal_position)
    assert pd.isna(row.final_outcome_known_bar_position)
    assert row.snapshot_status_known_bar_position == 3


def test_visible_terminal_is_mature_with_exact_ledger_linkage():
    bundle = base_continuation_bundle()
    result = observe_at(bundle, 4)
    row = result.hypothesis_outcome_snapshots.iloc[0]
    terminal = bundle.hypothesis_ledger[
        bundle.hypothesis_ledger["new_state"] == "CONTRADICTED"
    ].iloc[0]
    assert row.outcome_mature
    assert not row.right_censored_as_of
    assert row.narrative_terminal_state == "CONTRADICTED"
    assert row.terminal_ledger_event_id == terminal.ledger_event_id
    assert row.trigger_relationship_id == terminal.trigger_relationship_id
    assert row.terminal_position == 4
    assert row.final_outcome_known_bar_position == 4


def test_terminal_after_asof_remains_invisible_by_closed_firewall():
    bundle = base_continuation_bundle()
    assert (
        bundle.hypothesis_ledger["new_state"] == "CONTRADICTED"
    ).any()
    visible, adapter = visible_at(bundle, 3)
    assert not (
        visible.hypothesis_ledger["new_state"] == "CONTRADICTED"
    ).any()
    result = FactualHypothesisOutcomeObserver(adapter=adapter).observe(
        visible, OutcomeObservationRequest(0)
    )
    assert not result.hypothesis_outcome_snapshots.iloc[0].outcome_mature


def test_multiple_terminal_events_for_one_hypothesis_are_rejected():
    bundle = base_continuation_bundle(extra=2)
    visible, adapter = visible_at(bundle, 6)
    ledger = visible.hypothesis_ledger.copy(deep=True)
    first_terminal = ledger[ledger["new_state"] == "CONTRADICTED"].iloc[0]
    duplicate = first_terminal.copy()
    duplicate["ledger_event_id"] = int(ledger["ledger_event_id"].max()) + 1
    duplicate["event_position"] = 6
    duplicate["same_row_batch_id"] = 6
    duplicate["serialization_order"] = int(duplicate["ledger_event_id"])
    ledger = pd.concat([ledger, duplicate.to_frame().T], ignore_index=True)
    for column in (
        "ledger_event_id",
        "hypothesis_id",
        "event_position",
        "same_row_batch_id",
        "trigger_relationship_id",
        "superseded_by_hypothesis_id",
        "serialization_order",
    ):
        ledger[column] = pd.array(ledger[column], dtype="Int64")
    altered = replace(visible, hypothesis_ledger=ledger)
    with pytest.raises(OutcomeContractError, match="multiple terminal"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            altered, OutcomeObservationRequest(0)
        )


def test_multiple_same_position_terminal_events_rejected_without_serialization_choice():
    visible, adapter = visible_at(base_continuation_bundle(), 4)
    ledger = visible.hypothesis_ledger.copy(deep=True)
    terminal = ledger[ledger["new_state"] == "CONTRADICTED"].iloc[0]
    duplicate = terminal.copy()
    duplicate["ledger_event_id"] = int(ledger["ledger_event_id"].max()) + 1
    duplicate["serialization_order"] = int(terminal["serialization_order"]) + 100
    duplicate["new_state"] = "SUPERSEDED"
    ledger = pd.concat([ledger, duplicate.to_frame().T], ignore_index=True)
    for column in (
        "ledger_event_id",
        "hypothesis_id",
        "event_position",
        "same_row_batch_id",
        "trigger_relationship_id",
        "superseded_by_hypothesis_id",
        "serialization_order",
    ):
        ledger[column] = pd.array(ledger[column], dtype="Int64")
    with pytest.raises(OutcomeContractError, match="multiple terminal"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            replace(visible, hypothesis_ledger=ledger), OutcomeObservationRequest(0)
        )


def test_same_information_batch_terminal_is_rejected():
    visible, adapter = visible_at(base_continuation_bundle(), 4)
    ledger = visible.hypothesis_ledger.copy(deep=True)
    terminal_mask = ledger["new_state"] == "CONTRADICTED"
    ledger.loc[terminal_mask, "event_position"] = 1
    ledger.loc[terminal_mask, "same_row_batch_id"] = 1
    with pytest.raises(OutcomeContractError, match="same-row lifecycle history"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            replace(visible, hypothesis_ledger=ledger), OutcomeObservationRequest(0)
        )


def test_resolved_pre_endpoint_and_endpoint_bar_boundaries():
    result = observe_at(base_continuation_bundle(), 4)
    paths = result.outcome_path_segments
    assert paths["segment_type"].tolist() == [
        SegmentType.PRE_ENDPOINT.value,
        SegmentType.ENDPOINT_BAR.value,
    ]
    pre = paths.iloc[0]
    endpoint = paths.iloc[1]
    assert pre.segment_start_exclusive_position == 1
    assert pre.segment_end_inclusive_position == 3
    assert pre.segment_observation_count == 2
    assert endpoint.segment_start_exclusive_position == 3
    assert endpoint.segment_end_inclusive_position == 4
    assert endpoint.segment_observation_count == 1


def test_censored_observed_through_asof_boundaries():
    result = observe_at(base_continuation_bundle(), 3)
    path = result.outcome_path_segments.iloc[0]
    assert path.segment_type == SegmentType.OBSERVED_THROUGH_AS_OF.value
    assert path.segment_start_exclusive_position == 1
    assert path.segment_end_inclusive_position == 3
    assert path.segment_observation_count == 2


def test_empty_pre_endpoint_segment_is_unavailable_not_zero():
    market = continuation_market().iloc[:4].copy(deep=True)
    states = ["UP_STRUCTURE", "UP_STRUCTURE", "DOWN_STRUCTURE", "DOWN_STRUCTURE"]
    events = ["NONE", "BOS_UP", "NONE", "NONE"]
    bundle = build_frozen(market, states, events)
    result = observe_at(bundle, 2)
    pre = result.outcome_path_segments.iloc[0]
    assert pre.segment_type == SegmentType.PRE_ENDPOINT.value
    assert pre.segment_observation_count == 0
    assert not pre.segment_available
    assert pd.isna(pre.favorable_excursion_fraction)
    assert pd.isna(pre.adverse_excursion_fraction)
    assert pd.isna(pre.favorable_extreme_position)
    assert pd.isna(pre.adverse_extreme_position)


def test_invalid_included_path_price_rejected_but_future_invalid_ignored():
    bundle = base_continuation_bundle()
    included_market = bundle.market_frame.copy(deep=True)
    included_market.loc[2, "high"] = np.inf
    with pytest.raises(OutcomeDataError, match="finite"):
        observe_at(replace(bundle, market_frame=included_market), 3)

    future_market = bundle.market_frame.copy(deep=True)
    future_market.loc[6, "low"] = -1.0
    result = observe_at(replace(bundle, market_frame=future_market), 3)
    assert not result.hypothesis_outcome_snapshots.iloc[0].outcome_mature


def test_up_excursion_arithmetic_ties_and_same_bar_ambiguity():
    result = observe_at(base_continuation_bundle(), 4)
    pre = result.outcome_path_segments.iloc[0]
    endpoint = result.outcome_path_segments.iloc[1]
    assert pre.favorable_excursion_fraction == pytest.approx(0.05)
    assert pre.adverse_excursion_fraction == pytest.approx(0.05)
    assert pre.favorable_extreme_price == 105.0
    assert pre.favorable_extreme_position == 2
    assert pre.adverse_extreme_price == 95.0
    assert pre.adverse_extreme_position == 3
    assert pre.same_bar_order_ambiguous
    assert endpoint.favorable_excursion_fraction == pytest.approx(0.04)
    assert endpoint.adverse_excursion_fraction == pytest.approx(0.06)
    assert endpoint.same_bar_order_ambiguous


def test_down_excursion_arithmetic_and_earliest_extreme_tie():
    result = observe_at(base_down_bundle(), 4)
    row = result.hypothesis_outcome_snapshots.iloc[0]
    pre = result.outcome_path_segments.iloc[0]
    assert row.direction == "DOWN"
    assert pre.favorable_excursion_fraction == pytest.approx(0.05)
    assert pre.adverse_excursion_fraction == pytest.approx(0.06)
    assert pre.favorable_extreme_position == 2
    assert pre.adverse_extreme_position == 3
    assert pre.same_bar_order_ambiguous


def test_no_fixed_horizon_or_trade_configuration_surface():
    request_fields = {field.name for field in fields(OutcomeObservationRequest)}
    assert request_fields == {"hypothesis_id", "snapshot_type"}
    result = observe_at(base_continuation_bundle(), 3)
    output_columns = set(result.hypothesis_outcome_snapshots.columns) | set(
        result.outcome_path_segments.columns
    )
    forbidden = {
        "win",
        "loss",
        "pnl",
        "profit",
        "target_hit",
        "stop_hit",
        "return_5",
        "return_10",
        "good_trade",
        "trade_result",
        "entry",
        "fill",
    }
    assert output_columns.isdisjoint(forbidden)


def test_b1_censored_b2_mature_append_only_identities():
    bundle = base_continuation_bundle()
    b1 = observe_at(bundle, 3)
    b1_before = b1.hypothesis_outcome_snapshots.copy(deep=True)
    b2 = observe_at(bundle, 4)
    row1 = b1.hypothesis_outcome_snapshots.iloc[0]
    row2 = b2.hypothesis_outcome_snapshots.iloc[0]
    pd.testing.assert_frame_equal(
        b1.hypothesis_outcome_snapshots, b1_before, check_exact=True
    )
    assert pd.isna(row1.factual_outcome_id)
    assert not pd.isna(row2.factual_outcome_id)
    assert row1.research_snapshot_id != row2.research_snapshot_id
    assert row1.research_outcome_hash != row2.research_outcome_hash
    assert row1.decision_snapshot_hash == row2.decision_snapshot_hash
    assert row1.decision_input_slice_hash == row2.decision_input_slice_hash
    assert row1.reference_price == row2.reference_price


def test_mature_future_append_has_stable_factual_component():
    base = base_continuation_bundle()
    appended = base_continuation_bundle(extra=2)
    mature = observe_at(base, 4)
    later = observe_at(appended, 8)
    left = mature.hypothesis_outcome_snapshots.iloc[0]
    right = later.hypothesis_outcome_snapshots.iloc[0]
    assert left.research_snapshot_id != right.research_snapshot_id
    assert left.research_outcome_hash != right.research_outcome_hash
    assert left.factual_outcome_id == right.factual_outcome_id
    assert left.research_market_slice_hash == right.research_market_slice_hash
    assert left.decision_snapshot_hash == right.decision_snapshot_hash
    pd.testing.assert_frame_equal(
        mature.outcome_path_segments.drop(columns=["research_snapshot_id"]),
        later.outcome_path_segments.drop(columns=["research_snapshot_id"]),
        check_exact=True,
    )


def test_decision_hash_future_independence_and_market_slice_boundary():
    base = base_continuation_bundle()
    changed_market = base.market_frame.copy(deep=True)
    changed_market.loc[2:3, ["high", "low"]] = [[120.0, 80.0], [130.0, 70.0]]
    changed = replace(base, market_frame=changed_market)
    left = observe_at(base, 3).hypothesis_outcome_snapshots.iloc[0]
    right = observe_at(changed, 3).hypothesis_outcome_snapshots.iloc[0]
    assert left.decision_snapshot_hash == right.decision_snapshot_hash
    assert left.decision_input_slice_hash == right.decision_input_slice_hash
    assert left.research_market_slice_hash != right.research_market_slice_hash

    after_terminal = base_continuation_bundle(extra=2)
    mutated_market = after_terminal.market_frame.copy(deep=True)
    mutated_market.iloc[5:, mutated_market.columns.get_indexer(["high", "low"])] = [
        [500.0, 1.0],
        [600.0, 2.0],
        [700.0, 3.0],
        [800.0, 4.0],
    ]
    mutated = replace(after_terminal, market_frame=mutated_market)
    mature_a = observe_at(after_terminal, 8).hypothesis_outcome_snapshots.iloc[0]
    mature_b = observe_at(mutated, 8).hypothesis_outcome_snapshots.iloc[0]
    assert mature_a.research_market_slice_hash == mature_b.research_market_slice_hash
    assert mature_a.factual_outcome_id == mature_b.factual_outcome_id


def test_hashes_and_outputs_are_deterministic_and_input_immutable():
    bundle = base_continuation_bundle()
    visible, adapter = visible_at(bundle, 4)
    before = {
        name: getattr(visible, name).copy(deep=True)
        for name in (
            "evidence_df",
            "feature_manifest",
            "narrative_surface",
            "observation_ledger",
            "hypothesis_ledger",
            "relationship_ledger",
            "relationship_sources",
            "narrative_manifest",
            "market_frame",
        )
    }
    observer = FactualHypothesisOutcomeObserver(adapter=adapter)
    first = observer.observe(visible, OutcomeObservationRequest(0))
    second = observer.observe(visible, OutcomeObservationRequest(0))
    assert_results_equal(first, second)
    for name, expected in before.items():
        pd.testing.assert_frame_equal(
            getattr(visible, name), expected, check_exact=True
        )


def test_a_b_a_and_fresh_instance_state_isolation():
    bundle_a = base_continuation_bundle()
    bundle_b = base_down_bundle()
    visible_a, adapter = visible_at(bundle_a, 4)
    visible_b, _ = visible_at(bundle_b, 4)
    observer = FactualHypothesisOutcomeObserver(adapter=adapter)
    first = observer.observe(visible_a, OutcomeObservationRequest(0))
    observer.observe(visible_b, OutcomeObservationRequest(0))
    after = observer.observe(visible_a, OutcomeObservationRequest(0))
    fresh = FactualHypothesisOutcomeObserver(adapter=adapter).observe(
        visible_a, OutcomeObservationRequest(0)
    )
    assert_results_equal(first, after)
    assert_results_equal(first, fresh)


def test_raw_structure_like_evidence_cannot_override_terminal_ledger():
    visible, adapter = visible_at(base_continuation_bundle(), 4)
    mutated_evidence = visible.evidence_df.copy(deep=True)
    mutated_evidence.loc[mutated_evidence.index[4], "ev__structure_state_after"] = (
        "UP_STRUCTURE"
    )
    result = FactualHypothesisOutcomeObserver(adapter=adapter).observe(
        replace(visible, evidence_df=mutated_evidence), OutcomeObservationRequest(0)
    )
    assert result.hypothesis_outcome_snapshots.iloc[0].narrative_terminal_state == (
        "CONTRADICTED"
    )


def test_full_vs_truncated_visible_input_equivalence():
    full = base_continuation_bundle()
    truncated = truncate_frozen(full, 3)
    left = observe_at(full, 3)
    right = observe_at(truncated, 3)
    assert_results_equal(left, right)


def test_future_mutation_beyond_asof_cannot_affect_censored_result():
    base = base_continuation_bundle()
    expected = observe_at(base, 3)
    mutated_market = base.market_frame.copy(deep=True)
    mutated_market.iloc[4:, :] = [[999.0, 1.0, 500.0]] * 3
    mutated_ledger = base.hypothesis_ledger.copy(deep=True)
    future = mutated_ledger["event_position"] > 3
    mutated_ledger.loc[future, "new_state"] = "SUPERSEDED"
    mutated = replace(
        base,
        market_frame=mutated_market,
        hypothesis_ledger=mutated_ledger,
    )
    actual = observe_at(mutated, 3)
    assert_results_equal(expected, actual)


def test_positional_timing_fields_have_missing_timestamps():
    row = observe_at(base_continuation_bundle(), 4).hypothesis_outcome_snapshots.iloc[0]
    assert pd.isna(row.snapshot_event_time_utc)
    assert pd.isna(row.reference_event_time_utc)
    assert pd.isna(row.terminal_event_time_utc)


def test_time_indexed_timing_fields_are_utc_canonical():
    utc = pd.date_range("2025-10-26T00:00:00Z", periods=7, freq="h")
    local = utc.tz_convert("Europe/Vilnius")
    market = continuation_market(index=local)
    states, events = continuation_structure(len(market))
    bundle = build_frozen(market, states, events, timeline_id="time")
    adapter = TimeIndexedTimelineAdapter("time")
    result = observe_at(bundle, 4, adapter=adapter)
    row = result.hypothesis_outcome_snapshots.iloc[0]
    assert str(row.snapshot_event_time_utc.tz) == "UTC"
    assert row.snapshot_event_time_utc == utc[1]
    assert row.reference_event_time_utc == utc[1]
    assert row.terminal_event_time_utc == utc[4]


def test_same_type_supersession_uses_certified_replacement_foundation_trigger():
    market = continuation_market().iloc[:5].copy(deep=True)
    states = ["UP_STRUCTURE"] * 5
    events = ["NONE", "BOS_UP", "NONE", "BOS_UP", "NONE"]
    bundle = build_frozen(market, states, events)
    result = observe_at(bundle, 3, hypothesis_id=0)
    row = result.hypothesis_outcome_snapshots.iloc[0]
    assert row.outcome_mature
    assert row.narrative_terminal_state == "SUPERSEDED"
    assert row.terminal_position == 3
    terminal = bundle.hypothesis_ledger[
        (bundle.hypothesis_ledger["hypothesis_id"] == 0)
        & (bundle.hypothesis_ledger["new_state"] == "SUPERSEDED")
    ].iloc[0]
    trigger = bundle.relationship_ledger[
        bundle.relationship_ledger["relationship_id"]
        == terminal.trigger_relationship_id
    ].iloc[0]
    assert trigger.hypothesis_id == terminal.superseded_by_hypothesis_id
    assert trigger.evidence_role == "FOUNDATION"


def test_supersession_requires_visible_replacement_created_history():
    market = continuation_market().iloc[:5].copy(deep=True)
    states = ["UP_STRUCTURE"] * 5
    events = ["NONE", "BOS_UP", "NONE", "BOS_UP", "NONE"]
    bundle = build_frozen(market, states, events)
    visible, adapter = visible_at(bundle, 3)
    ledger = visible.hypothesis_ledger[
        ~(
            (visible.hypothesis_ledger["hypothesis_id"] == 1)
            & (visible.hypothesis_ledger["ledger_event_type"] == "CREATED")
        )
    ].reset_index(drop=True)
    with pytest.raises(OutcomeContractError, match="replacement CREATED"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            replace(visible, hypothesis_ledger=ledger), OutcomeObservationRequest(0)
        )


@pytest.mark.parametrize("bad_close", [0.0, -1.0, np.nan, np.inf, True, "100"])
def test_invalid_creation_reference_close_rejected(bad_close):
    bundle = base_continuation_bundle()
    market = bundle.market_frame.copy(deep=True)
    market["close"] = market["close"].astype(object)
    market.iloc[1, market.columns.get_loc("close")] = bad_close
    with pytest.raises(OutcomeDataError, match="reference close"):
        observe_at(replace(bundle, market_frame=market), 3)


def test_missing_creation_close_column_rejected():
    bundle = base_continuation_bundle()
    with pytest.raises(OutcomeDataError, match="close column"):
        observe_at(
            replace(bundle, market_frame=bundle.market_frame.drop(columns=["close"])),
            3,
        )


@pytest.mark.parametrize(
    ("high", "low"),
    [(90.0, 95.0), (100.0, 0.0), (np.nan, 90.0), (100.0, np.inf)],
)
def test_invalid_included_path_geometry_rejected(high, low):
    bundle = base_continuation_bundle()
    market = bundle.market_frame.copy(deep=True)
    market.loc[2, ["high", "low"]] = [high, low]
    with pytest.raises(OutcomeDataError):
        observe_at(replace(bundle, market_frame=market), 3)


def test_censored_empty_observed_path_is_unavailable_and_hash_deterministic():
    bundle = base_continuation_bundle()
    first = observe_at(bundle, 1)
    second = observe_at(bundle, 1)
    path = first.outcome_path_segments.iloc[0]
    assert path.segment_type == "OBSERVED_THROUGH_AS_OF"
    assert path.segment_observation_count == 0
    assert not path.segment_available
    assert pd.isna(path.favorable_excursion_fraction)
    assert pd.isna(path.adverse_excursion_fraction)
    assert (
        first.hypothesis_outcome_snapshots.iloc[0].research_market_slice_hash
        == second.hypothesis_outcome_snapshots.iloc[0].research_market_slice_hash
    )


def test_snapshot_timing_fields_reconstruct_all_information_keys():
    result = observe_at(base_continuation_bundle(), 4)
    row = result.hypothesis_outcome_snapshots.iloc[0]
    assert row.snapshot_bar_position == 1
    assert row.snapshot_information_phase == "COMPLETED_ROW_AVAILABLE"
    assert row.reference_bar_position == 1
    assert row.reference_information_phase == "COMPLETED_ROW_AVAILABLE"
    assert row.terminal_bar_position == 4
    assert row.terminal_information_phase == "COMPLETED_ROW_AVAILABLE"
    assert row.snapshot_status_known_bar_position == 4
    assert row.final_outcome_known_bar_position == 4


def test_contract_manifest_and_outputs_contain_no_trade_label_vocabulary():
    result = observe_at(base_continuation_bundle(), 4)
    text = " ".join(
        list(result.hypothesis_outcome_snapshots.columns)
        + list(result.outcome_path_segments.columns)
        + result.outcome_manifest["name"].astype(str).tolist()
    ).lower()
    for forbidden in (
        "target_hit",
        "stop_hit",
        "return_5",
        "return_10",
        "good_trade",
        "trade_result",
        "win",
        "loss",
        "pnl",
        "profit",
        "entry",
        "fill",
    ):
        assert forbidden not in text


def test_creation_decision_hash_is_exact_across_asof_and_later_payload_mutation():
    bundle = base_continuation_bundle()
    b1 = observe_at(bundle, 3).hypothesis_outcome_snapshots.iloc[0]
    b2 = observe_at(bundle, 4).hypothesis_outcome_snapshots.iloc[0]
    assert b1.decision_snapshot_hash == b2.decision_snapshot_hash

    observations = bundle.observation_ledger.copy(deep=True)
    later_observations = observations["observed_position"] > 1
    observations.loc[later_observations, "primary_numeric_value"] = 0.987654321

    relationships = bundle.relationship_ledger.copy(deep=True)
    later_relationships = relationships["observed_position"] > 1
    relationships.loc[later_relationships, "primary_numeric_value"] = 0.123456789

    lifecycle = bundle.hypothesis_ledger.copy(deep=True)
    later_lifecycle = lifecycle["event_position"] > 1
    lifecycle.loc[later_lifecycle, "previous_state"] = "MUTATED_LATER_STATE"

    mutated = replace(
        bundle,
        observation_ledger=observations,
        relationship_ledger=relationships,
        hypothesis_ledger=lifecycle,
    )
    mutated_b2 = observe_at(mutated, 4).hypothesis_outcome_snapshots.iloc[0]
    assert b1.decision_snapshot_hash == mutated_b2.decision_snapshot_hash
    assert b1.decision_input_slice_hash == mutated_b2.decision_input_slice_hash


def test_creation_decision_hash_changes_with_legitimate_same_row_context():
    lower_context = observe_at(
        build_frozen_with_creation_range_context(0.25), 4
    ).hypothesis_outcome_snapshots.iloc[0]
    upper_context = observe_at(
        build_frozen_with_creation_range_context(0.75), 4
    ).hypothesis_outcome_snapshots.iloc[0]
    assert lower_context.reference_price == upper_context.reference_price
    assert lower_context.terminal_position == upper_context.terminal_position
    assert lower_context.decision_input_slice_hash == upper_context.decision_input_slice_hash
    assert lower_context.decision_snapshot_hash != upper_context.decision_snapshot_hash


def test_additional_same_row_lifecycle_event_at_creation_is_rejected():
    visible, adapter = visible_at(base_continuation_bundle(), 3)
    ledger = visible.hypothesis_ledger.copy(deep=True)
    created = ledger[
        (ledger["hypothesis_id"] == 0)
        & (ledger["ledger_event_type"] == "CREATED")
    ].iloc[0]
    extra = created.copy()
    extra["ledger_event_id"] = int(ledger["ledger_event_id"].max()) + 1
    extra["ledger_event_type"] = "STATE_CHANGED"
    extra["previous_state"] = "MONITORING"
    extra["new_state"] = "MONITORING"
    extra["serialization_order"] = int(extra["ledger_event_id"])
    ledger = pd.concat([ledger, extra.to_frame().T], ignore_index=True)
    for column in (
        "ledger_event_id",
        "hypothesis_id",
        "event_position",
        "same_row_batch_id",
        "trigger_relationship_id",
        "superseded_by_hypothesis_id",
        "serialization_order",
    ):
        ledger[column] = pd.array(ledger[column], dtype="Int64")
    with pytest.raises(OutcomeContractError, match="same-row lifecycle history"):
        FactualHypothesisOutcomeObserver(adapter=adapter).observe(
            replace(visible, hypothesis_ledger=ledger), OutcomeObservationRequest(0)
        )

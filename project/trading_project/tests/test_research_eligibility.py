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
from trading_system.research.eligibility import (
    ELIGIBILITY_CONTRACT_VERSION,
    EligibilityContractError,
    EligibilityDataError,
    EligibilityReason,
    FactualOutcomeBatch,
    TemporalEligibilityGate,
    TemporalEligibilityResult,
    eligibility_manifest,
)
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import (
    INFORMATION_KEY_VERSION,
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.outcome_observer import (
    OUTCOME_CONTRACT_VERSION,
    FactualHypothesisOutcomeObserver,
    OutcomeObservationRequest,
)
from trading_system.research.visibility import (
    AsOfVisibilityProjector,
    FrozenDecisionSnapshotBundle,
)


def config():
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


def market(index=None, extra=0):
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


def frozen_bundle(index=None, extra=0, timeline_id="timeline"):
    frame = market(index=index, extra=extra)
    n = len(frame)
    states = ["UP_STRUCTURE"] * min(n, 4) + ["DOWN_STRUCTURE"] * max(n - 4, 0)
    events = ["NONE"] * n
    events[1] = "BOS_UP"
    source = frame.copy(deep=True)
    source["structure_state_after"] = pd.Series(states, index=frame.index, dtype="string")
    source["structural_break_event"] = pd.Series(events, index=frame.index, dtype="string")
    evidence, feature_manifest = CausalEvidenceVectorEngine(config=config()).analyze(source)
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
        market_frame=frame,
    )


def outcome_at(bundle, position, adapter=None):
    if adapter is None:
        adapter = PositionalTimelineAdapter(bundle.timeline_id)
    asof = adapter.key_for_position(
        bundle.market_frame.index,
        position,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    )
    visible = AsOfVisibilityProjector(adapter=adapter).project(bundle, asof)
    return FactualHypothesisOutcomeObserver(adapter=adapter).observe(
        visible, OutcomeObservationRequest(0)
    )


def batch_of(*results):
    return FactualOutcomeBatch(
        hypothesis_outcome_snapshots=pd.concat(
            [result.hypothesis_outcome_snapshots for result in results],
            ignore_index=True,
        ),
        outcome_path_segments=pd.concat(
            [result.outcome_path_segments for result in results],
            ignore_index=True,
        ),
        outcome_manifest=results[0].outcome_manifest.copy(deep=True),
    )


def cutoff(adapter, index, position, phase=InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, sequence=0):
    return adapter.key_for_position(index, position, phase, sequence)


def gate(adapter):
    return TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    )


def positional_key_from_row(row, prefix, timeline=None):
    return InformationKey(
        information_key_version=str(row[f"{prefix}_information_key_version"]),
        timeline_id=str(row["timeline_id"] if timeline is None else timeline),
        bar_position=int(row[f"{prefix}_bar_position"]),
        event_time_utc=None,
        information_phase=InformationPhase(str(row[f"{prefix}_information_phase"])),
        deterministic_sequence=int(row[f"{prefix}_deterministic_sequence"]),
    )


def rehash_snapshot(batch, row_position):
    snapshots = batch.hypothesis_outcome_snapshots
    row = snapshots.iloc[row_position]
    snapshot_id = str(row["research_snapshot_id"])
    paths = batch.outcome_path_segments[
        batch.outcome_path_segments["research_snapshot_id"] == snapshot_id
    ].copy(deep=True).reset_index(drop=True)
    asof = positional_key_from_row(row, "research_as_of")
    terminal = positional_key_from_row(row, "terminal")
    new_snapshot_id = canonical_sha256(
        domain="RESEARCH_SNAPSHOT_ID_V1_2",
        payload={
            "decision_snapshot_hash": str(row["decision_snapshot_hash"]),
            "hypothesis_id": int(row["hypothesis_id"]),
            "snapshot_type": str(row["snapshot_type"]),
            "research_as_of": asof,
            "outcome_contract_version": str(row["outcome_contract_version"]),
        },
    )
    snapshots.loc[row_position, "research_snapshot_id"] = new_snapshot_id
    paths["research_snapshot_id"] = pd.array([new_snapshot_id] * len(paths), dtype="string")
    batch.outcome_path_segments.loc[
        batch.outcome_path_segments["research_snapshot_id"] == snapshot_id,
        "research_snapshot_id",
    ] = new_snapshot_id
    factual = canonical_sha256(
        domain="MATURE_FACTUAL_OUTCOME_ID_V1_2",
        payload={
            "decision_snapshot_hash": str(row["decision_snapshot_hash"]),
            "hypothesis_id": int(row["hypothesis_id"]),
            "terminal_state": str(row["narrative_terminal_state"]),
            "terminal_event_id": int(row["terminal_ledger_event_id"]),
            "trigger_relationship_id": int(row["trigger_relationship_id"]),
            "terminal_key": terminal,
            "research_market_slice_hash": str(row["research_market_slice_hash"]),
            "segments": paths.drop(columns=["research_snapshot_id"]),
            "outcome_contract_version": str(row["outcome_contract_version"]),
        },
    )
    snapshots.loc[row_position, "factual_outcome_id"] = factual
    research_hash = canonical_sha256(
        domain="RESEARCH_OUTCOME_V1_2",
        payload={
            "research_snapshot_id": new_snapshot_id,
            "factual_outcome_id": factual,
            "research_as_of": asof,
            "censoring_type": None,
            "research_market_slice_hash": str(row["research_market_slice_hash"]),
            "segments": paths,
            "outcome_contract_version": str(row["outcome_contract_version"]),
        },
    )
    snapshots.loc[row_position, "research_outcome_hash"] = research_hash


def test_mature_strictly_before_cutoff_is_eligible():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    result = gate(adapter).evaluate(
        batch_of(mature), cutoff(adapter, bundle.market_frame.index, 5)
    )
    audit = result.temporal_eligibility_audit.iloc[0]
    assert audit.temporally_eligible
    assert audit.eligibility_reason == EligibilityReason.ELIGIBLE.value
    assert len(result.selected_mature_samples) == 1


def test_terminal_exactly_at_cutoff_analytical_sequence_is_eligible():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    exact = cutoff(
        adapter,
        bundle.market_frame.index,
        4,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    result = gate(adapter).evaluate(batch_of(mature), exact)
    assert result.temporal_eligibility_audit.iloc[0].eligibility_reason == "ELIGIBLE"


def test_terminal_same_bar_before_analytical_sequence_is_ineligible():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    early = cutoff(
        adapter,
        bundle.market_frame.index,
        4,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        0,
    )
    result = gate(adapter).evaluate(batch_of(mature), early)
    assert result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "FINAL_OUTCOME_AFTER_CUTOFF"
    )
    assert result.selected_mature_samples.empty


def test_censored_snapshot_is_ineligible_and_audit_preserved():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    censored = outcome_at(bundle, 3, adapter)
    result = gate(adapter).evaluate(
        batch_of(censored), cutoff(adapter, bundle.market_frame.index, 5)
    )
    audit = result.temporal_eligibility_audit.iloc[0]
    assert not audit.temporally_eligible
    assert audit.eligibility_reason == "OUTCOME_IMMATURE"
    assert pd.isna(audit.factual_outcome_id)
    assert result.selected_mature_samples.empty


def test_b1_censored_and_b2_mature_only_b2_selected():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    b1 = outcome_at(bundle, 3, adapter)
    b2 = outcome_at(bundle, 4, adapter)
    result = gate(adapter).evaluate(
        batch_of(b1, b2), cutoff(adapter, bundle.market_frame.index, 5)
    )
    assert result.temporal_eligibility_audit["eligibility_reason"].tolist() == [
        "OUTCOME_IMMATURE",
        "ELIGIBLE",
    ]
    assert result.selected_mature_samples["selected_research_snapshot_id"].tolist() == [
        b2.hypothesis_outcome_snapshots.iloc[0].research_snapshot_id
    ]


def test_repeated_mature_asof_records_deduplicate_to_earliest():
    bundle = frozen_bundle(extra=2)
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    b2 = outcome_at(bundle, 4, adapter)
    b3 = outcome_at(bundle, 8, adapter)
    result = gate(adapter).evaluate(
        batch_of(b3, b2), cutoff(adapter, bundle.market_frame.index, 8)
    )
    assert result.temporal_eligibility_audit["temporally_eligible"].all()
    assert len(result.selected_mature_samples) == 1
    assert result.selected_mature_samples.iloc[0].selected_research_snapshot_id == (
        b2.hypothesis_outcome_snapshots.iloc[0].research_snapshot_id
    )


def test_conflicting_duplicate_factual_identity_is_hard_error():
    bundle = frozen_bundle(extra=2)
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    b2 = outcome_at(bundle, 4, adapter)
    b3 = outcome_at(bundle, 8, adapter)
    batch = batch_of(b2, b3)
    second_id = batch.hypothesis_outcome_snapshots.iloc[1].research_snapshot_id
    batch.hypothesis_outcome_snapshots.loc[1, "reference_price"] = 123.0
    # Keep the same factual ID deliberately: duplicate identity now conflicts.
    with pytest.raises(EligibilityDataError, match="conflicting duplicate"):
        gate(adapter).evaluate(
            batch, cutoff(adapter, bundle.market_frame.index, 8)
        )


def test_cross_timeline_cutoff_rejected():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    other = PositionalTimelineAdapter("other")
    mature = outcome_at(bundle, 4, adapter)
    wrong_cutoff = cutoff(other, bundle.market_frame.index, 5)
    with pytest.raises(EligibilityContractError, match="cutoff timeline"):
        gate(adapter).evaluate(batch_of(mature), wrong_cutoff)


def test_forged_hash_and_tampered_path_are_hash_failures():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    forged = batch_of(mature)
    forged.hypothesis_outcome_snapshots.loc[0, "research_outcome_hash"] = "0" * 64
    result = gate(adapter).evaluate(
        forged, cutoff(adapter, bundle.market_frame.index, 5)
    )
    assert result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "HASH_VALIDATION_FAILED"
    )

    tampered = batch_of(mature)
    tampered.outcome_path_segments.loc[0, "favorable_excursion_fraction"] = 999.0
    result = gate(adapter).evaluate(
        tampered, cutoff(adapter, bundle.market_frame.index, 5)
    )
    assert result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "HASH_VALIDATION_FAILED"
    )


def test_opaque_decision_hash_must_be_valid_and_hash_consistent():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    batch = batch_of(mature)
    batch.hypothesis_outcome_snapshots.loc[0, "decision_snapshot_hash"] = "not-a-hash"
    result = gate(adapter).evaluate(
        batch, cutoff(adapter, bundle.market_frame.index, 5)
    )
    assert result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "HASH_VALIDATION_FAILED"
    )


def test_label_information_interval_exactly_snapshot_to_final():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    result = gate(adapter).evaluate(
        batch_of(mature), cutoff(adapter, bundle.market_frame.index, 5)
    )
    row = result.selected_mature_samples.iloc[0]
    assert row.label_information_start_exclusive_bar_position == 1
    assert row.label_information_start_exclusive_deterministic_sequence == 1
    assert row.label_information_end_inclusive_bar_position == 4
    assert row.label_information_end_inclusive_deterministic_sequence == 1
    assert row.final_outcome_known_bar_position == 4


def test_contract_version_precedence_before_hash_failure():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    batch = batch_of(mature)
    batch.hypothesis_outcome_snapshots.loc[0, "outcome_contract_version"] = "FORGED"
    batch.hypothesis_outcome_snapshots.loc[0, "research_outcome_hash"] = "bad"
    result = gate(adapter).evaluate(
        batch, cutoff(adapter, bundle.market_frame.index, 5)
    )
    assert result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "CONTRACT_VERSION_MISMATCH"
    )


def test_unsupported_snapshot_type_reason_after_valid_rehash():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    batch = batch_of(mature)
    batch.hypothesis_outcome_snapshots.loc[0, "snapshot_type"] = (
        "HYPOTHESIS_EVALUATION_SNAPSHOT"
    )
    rehash_snapshot(batch, 0)
    result = gate(adapter).evaluate(
        batch, cutoff(adapter, bundle.market_frame.index, 5)
    )
    assert result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "UNSUPPORTED_SNAPSHOT_TYPE"
    )


def test_malformed_key_and_dtype_contract_rejected():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    malformed = batch_of(mature)
    malformed.hypothesis_outcome_snapshots.loc[0, "snapshot_bar_position"] = pd.NA
    with pytest.raises(EligibilityContractError, match="required snapshot key|partial"):
        gate(adapter).evaluate(
            malformed, cutoff(adapter, bundle.market_frame.index, 5)
        )

    wrong_dtype = batch_of(mature)
    wrong_dtype.hypothesis_outcome_snapshots["hypothesis_id"] = (
        wrong_dtype.hypothesis_outcome_snapshots["hypothesis_id"].astype(float)
    )
    with pytest.raises(EligibilityContractError, match="dtype mismatch"):
        gate(adapter).evaluate(
            wrong_dtype, cutoff(adapter, bundle.market_frame.index, 5)
        )


def test_manifest_orphan_and_missing_segment_rejected():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    wrong_manifest = batch_of(mature)
    wrong_manifest.outcome_manifest.loc[0, "name"] = "FORGED"
    with pytest.raises(EligibilityContractError, match="manifest"):
        gate(adapter).evaluate(
            wrong_manifest, cutoff(adapter, bundle.market_frame.index, 5)
        )

    orphan = batch_of(mature)
    orphan.outcome_path_segments.loc[0, "research_snapshot_id"] = "f" * 64
    with pytest.raises(EligibilityDataError, match="orphan"):
        gate(adapter).evaluate(orphan, cutoff(adapter, bundle.market_frame.index, 5))


def test_future_append_does_not_change_old_cutoff_result():
    base = frozen_bundle()
    appended = frozen_bundle(extra=2)
    adapter = PositionalTimelineAdapter(base.timeline_id)
    base_result = outcome_at(base, 4, adapter)
    appended_result = outcome_at(appended, 8, adapter)
    old_cutoff = cutoff(adapter, base.market_frame.index, 4, InformationPhase.COMPLETED_ROW_AVAILABLE, 1)
    left = gate(adapter).evaluate(batch_of(base_result), old_cutoff)
    right = gate(adapter).evaluate(batch_of(appended_result), old_cutoff)
    assert left.temporal_eligibility_audit.iloc[0].temporally_eligible
    assert right.temporal_eligibility_audit.iloc[0].temporally_eligible
    assert (
        left.selected_mature_samples.iloc[0].factual_outcome_id
        == right.selected_mature_samples.iloc[0].factual_outcome_id
    )


def test_input_immutable_deterministic_a_b_a_and_fresh_instance():
    bundle_a = frozen_bundle()
    bundle_b = frozen_bundle(extra=2)
    adapter = PositionalTimelineAdapter(bundle_a.timeline_id)
    batch_a = batch_of(outcome_at(bundle_a, 4, adapter))
    batch_b = batch_of(outcome_at(bundle_b, 8, adapter))
    before_snapshots = batch_a.hypothesis_outcome_snapshots.copy(deep=True)
    before_paths = batch_a.outcome_path_segments.copy(deep=True)
    cutoff_a = cutoff(adapter, bundle_a.market_frame.index, 5)
    eligibility_gate = gate(adapter)
    first = eligibility_gate.evaluate(batch_a, cutoff_a)
    repeated = eligibility_gate.evaluate(batch_a, cutoff_a)
    eligibility_gate.evaluate(batch_b, cutoff(adapter, bundle_b.market_frame.index, 8))
    after = eligibility_gate.evaluate(batch_a, cutoff_a)
    fresh = gate(adapter).evaluate(batch_a, cutoff_a)
    for other in (repeated, after, fresh):
        pd.testing.assert_frame_equal(
            first.temporal_eligibility_audit,
            other.temporal_eligibility_audit,
            check_exact=True,
        )
        pd.testing.assert_frame_equal(
            first.selected_mature_samples,
            other.selected_mature_samples,
            check_exact=True,
        )
    pd.testing.assert_frame_equal(
        batch_a.hypothesis_outcome_snapshots, before_snapshots, check_exact=True
    )
    pd.testing.assert_frame_equal(
        batch_a.outcome_path_segments, before_paths, check_exact=True
    )


def test_positional_and_time_indexed_cutoff_contracts():
    positional_bundle = frozen_bundle()
    positional_adapter = PositionalTimelineAdapter(positional_bundle.timeline_id)
    result = gate(positional_adapter).evaluate(
        batch_of(outcome_at(positional_bundle, 4, positional_adapter)),
        cutoff(positional_adapter, positional_bundle.market_frame.index, 5),
    )
    assert pd.isna(result.temporal_eligibility_audit.iloc[0].snapshot_event_time_utc)

    utc = pd.date_range("2025-10-26T00:00:00Z", periods=7, freq="h")
    local = utc.tz_convert("Europe/Vilnius")
    timed_bundle = frozen_bundle(index=local, timeline_id="time")
    timed_adapter = TimeIndexedTimelineAdapter("time")
    timed_outcome = outcome_at(timed_bundle, 4, timed_adapter)
    timed_result = gate(timed_adapter).evaluate(
        batch_of(timed_outcome),
        cutoff(timed_adapter, local, 5),
    )
    assert timed_result.temporal_eligibility_audit.iloc[0].temporally_eligible
    assert str(
        timed_result.temporal_eligibility_audit.iloc[0].snapshot_event_time_utc.tz
    ) == "UTC"


def test_no_model_split_weight_or_feature_transformation_api():
    names = {field.name for field in fields(FactualOutcomeBatch)} | {
        field.name for field in fields(TemporalEligibilityResult)
    }
    forbidden = {
        "random_state",
        "shuffle",
        "train_test_split",
        "kfold",
        "sample_weight",
        "confidence",
        "score",
        "features",
        "training_matrix",
    }
    assert names.isdisjoint(forbidden)
    manifest_text = " ".join(eligibility_manifest()["name"].astype(str)).lower()
    assert not any(token in manifest_text for token in forbidden)


def test_audit_output_preserves_input_order_and_ineligible_rows():
    bundle = frozen_bundle(extra=2)
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    b1 = outcome_at(bundle, 3, adapter)
    b3 = outcome_at(bundle, 8, adapter)
    batch = batch_of(b3, b1)
    result = gate(adapter).evaluate(
        batch, cutoff(adapter, bundle.market_frame.index, 8)
    )
    assert result.temporal_eligibility_audit["input_row_ordinal"].tolist() == [0, 1]
    assert result.temporal_eligibility_audit["research_snapshot_id"].tolist() == (
        batch.hypothesis_outcome_snapshots["research_snapshot_id"].tolist()
    )
    assert result.temporal_eligibility_audit["eligibility_reason"].tolist() == [
        "ELIGIBLE",
        "OUTCOME_IMMATURE",
    ]


def test_later_cutoff_changes_mature_record_from_ineligible_to_eligible():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    before = cutoff(
        adapter,
        bundle.market_frame.index,
        4,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        0,
    )
    at_terminal = cutoff(
        adapter,
        bundle.market_frame.index,
        4,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    early_result = gate(adapter).evaluate(batch_of(mature), before)
    later_result = gate(adapter).evaluate(batch_of(mature), at_terminal)
    assert early_result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "FINAL_OUTCOME_AFTER_CUTOFF"
    )
    assert later_result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "ELIGIBLE"
    )


def test_missing_final_outcome_key_receives_exact_reason():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    mature = outcome_at(bundle, 4, adapter)
    batch = batch_of(mature)
    for suffix in (
        "information_key_version",
        "bar_position",
        "event_time_utc",
        "information_phase",
        "deterministic_sequence",
    ):
        batch.hypothesis_outcome_snapshots.loc[
            0, f"final_outcome_known_{suffix}"
        ] = pd.NaT if suffix == "event_time_utc" else pd.NA
    result = gate(adapter).evaluate(
        batch, cutoff(adapter, bundle.market_frame.index, 5)
    )
    assert result.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "FINAL_OUTCOME_KEY_MISSING"
    )


def test_dedup_selection_is_stable_under_batch_permutation():
    bundle = frozen_bundle(extra=2)
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    b2 = outcome_at(bundle, 4, adapter)
    b3 = outcome_at(bundle, 8, adapter)
    training_cutoff = cutoff(adapter, bundle.market_frame.index, 8)
    left = gate(adapter).evaluate(batch_of(b2, b3), training_cutoff)
    right = gate(adapter).evaluate(batch_of(b3, b2), training_cutoff)
    assert left.selected_mature_samples.iloc[0].selected_research_snapshot_id == (
        right.selected_mature_samples.iloc[0].selected_research_snapshot_id
    )
    assert left.selected_mature_samples.iloc[0].factual_outcome_id == (
        right.selected_mature_samples.iloc[0].factual_outcome_id
    )


def test_future_market_mutation_after_terminal_does_not_change_old_eligibility():
    bundle = frozen_bundle(extra=2)
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    original_outcome = outcome_at(bundle, 8, adapter)
    mutated_market = bundle.market_frame.copy(deep=True)
    mutated_market.loc[5:, ["high", "low", "close"]] = [
        [500.0, 1.0, 250.0],
        [600.0, 2.0, 300.0],
        [700.0, 3.0, 350.0],
        [800.0, 4.0, 400.0],
    ]
    mutated_bundle = replace(bundle, market_frame=mutated_market)
    mutated_outcome = outcome_at(mutated_bundle, 8, adapter)
    training_cutoff = cutoff(adapter, bundle.market_frame.index, 8)
    left = gate(adapter).evaluate(batch_of(original_outcome), training_cutoff)
    right = gate(adapter).evaluate(batch_of(mutated_outcome), training_cutoff)
    pd.testing.assert_frame_equal(
        left.temporal_eligibility_audit,
        right.temporal_eligibility_audit,
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        left.selected_mature_samples,
        right.selected_mature_samples,
        check_exact=True,
    )


def test_output_schemas_dtypes_and_exact_two_result_tables():
    bundle = frozen_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    result = gate(adapter).evaluate(
        batch_of(outcome_at(bundle, 4, adapter)),
        cutoff(adapter, bundle.market_frame.index, 5),
    )
    assert {field.name for field in fields(TemporalEligibilityResult)} == {
        "temporal_eligibility_audit",
        "selected_mature_samples",
    }
    assert str(result.temporal_eligibility_audit["input_row_ordinal"].dtype) == "Int64"
    assert str(result.temporal_eligibility_audit["temporally_eligible"].dtype) == (
        "boolean"
    )
    assert str(result.selected_mature_samples["hypothesis_id"].dtype) == "Int64"
    forbidden = ("sample_weight", "confidence", "score", "signal", "model")
    all_columns = " ".join(
        list(result.temporal_eligibility_audit.columns)
        + list(result.selected_mature_samples.columns)
    ).lower()
    assert not any(token in all_columns for token in forbidden)

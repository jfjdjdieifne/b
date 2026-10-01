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
from trading_system.research.dataset_builder import (
    CausalResearchDatasetBuilder,
    ResearchDatasetBuildResult,
    ResearchDatasetFold,
)
from trading_system.research.dataset_contracts import (
    DATASET_CONTRACT_VERSION,
    DatasetContractError,
    DatasetDataError,
    WalkForwardFoldSpec,
    freeze_creation_feature_snapshot,
)
from trading_system.research.eligibility import (
    ELIGIBILITY_CONTRACT_VERSION,
    FactualOutcomeBatch,
    TemporalEligibilityGate,
)
from trading_system.research.information_time import (
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.outcome_observer import (
    FactualHypothesisOutcomeObserver,
    OutcomeObservationRequest,
)
from trading_system.research.visibility import (
    AsOfVisibilityProjector,
    FrozenDecisionSnapshotBundle,
)


def cfg():
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


def pipeline_bundle(index=None, timeline_id="dataset"):
    n = 10
    if index is None:
        index = pd.RangeIndex(n)
    market = pd.DataFrame(
        {
            "high": [101, 102, 105, 104, 103, 102, 101, 100, 106, 107],
            "low": [98, 98, 99, 97, 94, 93, 92, 90, 91, 92],
            "close": [99, 100, 103, 100, 96, 95, 94, 93, 105, 106],
        },
        index=index,
        dtype=float,
    )
    states = ["UP_STRUCTURE"] * 4 + ["DOWN_STRUCTURE"] * 4 + ["UP_STRUCTURE"] * 2
    events = ["NONE"] * n
    events[1] = "BOS_UP"
    events[6] = "BOS_DOWN"
    source = market.copy(deep=True)
    source["structure_state_after"] = pd.Series(
        states, index=market.index, dtype="string"
    )
    source["structural_break_event"] = pd.Series(
        events, index=market.index, dtype="string"
    )
    evidence, feature_manifest = CausalEvidenceVectorEngine(config=cfg()).analyze(source)
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
        market_frame=market,
    )


def key(adapter, index, position, phase=InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, sequence=0):
    return adapter.key_for_position(index, position, phase, sequence)


def visible(bundle, position, adapter):
    return AsOfVisibilityProjector(adapter=adapter).project(
        bundle, key(adapter, bundle.market_frame.index, position)
    )


def outcome(bundle, hypothesis_id, position, adapter):
    return FactualHypothesisOutcomeObserver(adapter=adapter).observe(
        visible(bundle, position, adapter), OutcomeObservationRequest(hypothesis_id)
    )


def factual_batch(*results):
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


def setup_inputs(include_repeat=True):
    bundle = pipeline_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    h0 = outcome(bundle, 0, 5, adapter)
    h1_censored = outcome(bundle, 1, 7, adapter)
    h1_mature = outcome(bundle, 1, 8, adapter)
    results = [h0, h1_censored, h1_mature]
    if include_repeat:
        results.append(outcome(bundle, 1, 9, adapter))
    factual = factual_batch(*results)
    train_cutoff = key(adapter, bundle.market_frame.index, 5)
    test_end = key(adapter, bundle.market_frame.index, 7)
    test_label_asof = key(adapter, bundle.market_frame.index, 8)
    eligibility_gate = TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    )
    train_eligibility = eligibility_gate.evaluate(factual, train_cutoff)
    test_eligibility = eligibility_gate.evaluate(factual, test_label_asof)
    full_visible = visible(bundle, 9, adapter)
    snapshots = [
        freeze_creation_feature_snapshot(full_visible, hypothesis_id=0, adapter=adapter),
        freeze_creation_feature_snapshot(full_visible, hypothesis_id=1, adapter=adapter),
    ]
    fold = WalkForwardFoldSpec(
        fold_id="fold-1",
        timeline_id=bundle.timeline_id,
        train_cutoff=train_cutoff,
        test_creation_end_inclusive=test_end,
        test_label_as_of=test_label_asof,
    )
    return (
        bundle,
        adapter,
        factual,
        train_eligibility,
        test_eligibility,
        snapshots,
        fold,
    )


def build_default(include_test_targets=True):
    (
        bundle,
        adapter,
        factual,
        train_eligibility,
        test_eligibility,
        snapshots,
        fold,
    ) = setup_inputs()
    if not include_test_targets:
        fold = replace(fold, test_label_as_of=None)
        test_eligibility = None
    result = CausalResearchDatasetBuilder(adapter=adapter).build(
        fold_spec=fold,
        feature_snapshots=snapshots,
        factual_outcomes=factual,
        train_eligibility=train_eligibility,
        test_evaluation_eligibility=test_eligibility,
    )
    return result


def test_exact_train_test_join_and_zero_outcome_columns_in_x():
    result = build_default()
    fold = result.fold
    assert len(fold.train_features_raw) == 1
    assert len(fold.train_targets) == 1
    assert len(fold.test_features_raw) == 1
    assert len(fold.test_targets) == 1
    assert tuple(fold.train_features_raw.columns) == tuple(fold.test_features_raw.columns)
    assert all(
        column.startswith("ev__") or column.startswith("nar__")
        for column in fold.train_features_raw.columns
    )
    forbidden = (
        "outcome",
        "terminal",
        "factual",
        "research_as_of",
        "final_outcome",
        "target_",
    )
    assert not any(
        token in column.lower()
        for token in forbidden
        for column in fold.train_features_raw.columns
    )


def test_test_feature_cohort_independent_of_target_availability():
    with_targets = build_default(include_test_targets=True)
    without_targets = build_default(include_test_targets=False)
    pd.testing.assert_frame_equal(
        with_targets.fold.test_features_raw,
        without_targets.fold.test_features_raw,
        check_exact=True,
    )
    assert with_targets.fold.sample_metadata.loc[
        with_targets.fold.sample_metadata["split_role"] == "TEST",
        "target_available",
    ].all()
    assert not without_targets.fold.sample_metadata.loc[
        without_targets.fold.sample_metadata["split_role"] == "TEST",
        "target_available",
    ].any()
    assert without_targets.fold.test_targets.isna().all().all()


def test_decision_feature_snapshot_hash_recomputed_and_tamper_rejected():
    *_, snapshots, fold = setup_inputs()
    snapshots[0].verify()
    tampered_evidence = snapshots[0].evidence_row.copy(deep=True)
    tampered_evidence.iloc[0, 0] = "DOWN_STRUCTURE"
    forged = replace(snapshots[0], evidence_row=tampered_evidence)
    with pytest.raises(DatasetContractError, match="decision snapshot hash"):
        forged.verify()


def test_missing_duplicate_and_identity_mismatch_feature_joins_rejected():
    (
        _,
        adapter,
        factual,
        train_eligibility,
        test_eligibility,
        snapshots,
        fold,
    ) = setup_inputs()
    builder = CausalResearchDatasetBuilder(adapter=adapter)
    with pytest.raises(DatasetDataError, match="feature snapshot join"):
        builder.build(
            fold_spec=fold,
            feature_snapshots=snapshots[1:],
            factual_outcomes=factual,
            train_eligibility=train_eligibility,
            test_evaluation_eligibility=test_eligibility,
        )
    with pytest.raises(DatasetDataError, match="duplicate decision"):
        builder.build(
            fold_spec=fold,
            feature_snapshots=[*snapshots, snapshots[0]],
            factual_outcomes=factual,
            train_eligibility=train_eligibility,
            test_evaluation_eligibility=test_eligibility,
        )
    wrong = replace(snapshots[0], hypothesis_type="FORGED")
    with pytest.raises(DatasetContractError):
        builder.build(
            fold_spec=fold,
            feature_snapshots=[wrong, snapshots[1]],
            factual_outcomes=factual,
            train_eligibility=train_eligibility,
            test_evaluation_eligibility=test_eligibility,
        )


def test_forged_eligibility_result_rejected_by_closed_gate_reseal():
    (
        _,
        adapter,
        factual,
        train_eligibility,
        test_eligibility,
        snapshots,
        fold,
    ) = setup_inputs()
    forged_selected = train_eligibility.selected_mature_samples.copy(deep=True)
    forged_selected.loc[0, "hypothesis_type"] = "FORGED"
    forged = replace(train_eligibility, selected_mature_samples=forged_selected)
    with pytest.raises(DatasetContractError, match="eligibility result reseal"):
        CausalResearchDatasetBuilder(adapter=adapter).build(
            fold_spec=fold,
            feature_snapshots=snapshots,
            factual_outcomes=factual,
            train_eligibility=forged,
            test_evaluation_eligibility=test_eligibility,
        )


def test_fold_boundaries_and_explicit_label_asof_contract():
    bundle = pipeline_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    with pytest.raises(DatasetContractError):
        WalkForwardFoldSpec(
            fold_id="bad",
            timeline_id=bundle.timeline_id,
            train_cutoff=key(adapter, bundle.market_frame.index, 7),
            test_creation_end_inclusive=key(adapter, bundle.market_frame.index, 5),
        )
    with pytest.raises(DatasetContractError, match="label as-of"):
        WalkForwardFoldSpec(
            fold_id="bad-label",
            timeline_id=bundle.timeline_id,
            train_cutoff=key(adapter, bundle.market_frame.index, 5),
            test_creation_end_inclusive=key(adapter, bundle.market_frame.index, 7),
            test_label_as_of=key(adapter, bundle.market_frame.index, 6),
        )


def test_label_intervals_and_purge_boundary_are_exact():
    result = build_default()
    metadata = result.fold.sample_metadata
    train = metadata[metadata["split_role"] == "TRAIN"].iloc[0]
    assert train.label_interval_end_inclusive_bar_position == 4
    assert train.label_interval_end_inclusive_bar_position <= 5
    test = metadata[metadata["split_role"] == "TEST"].iloc[0]
    assert test.snapshot_bar_position == 6
    assert test.label_interval_start_exclusive_bar_position == 6
    assert test.label_interval_end_inclusive_bar_position == 8
    assert not train.cross_split_label_overlap_detected
    assert not test.cross_split_label_overlap_detected


def test_deduplicated_test_target_uses_earliest_mature_research_snapshot():
    result = build_default()
    test_meta = result.fold.sample_metadata[
        result.fold.sample_metadata["split_role"] == "TEST"
    ].iloc[0]
    (
        _,
        _,
        _,
        _,
        test_eligibility,
        _,
        _,
    ) = setup_inputs()
    expected = test_eligibility.selected_mature_samples[
        test_eligibility.selected_mature_samples["hypothesis_id"] == 1
    ].iloc[0]
    assert test_meta.selected_research_snapshot_id == (
        expected.selected_research_snapshot_id
    )


def test_raw_targets_are_factual_not_trade_labels():
    result = build_default()
    assert result.fold.train_targets.iloc[0].target_terminal_state == "CONTRADICTED"
    assert result.fold.test_targets.iloc[0].target_terminal_state == "CONTRADICTED"
    forbidden = (
        "win",
        "loss",
        "pnl",
        "profit",
        "buy",
        "sell",
        "target_hit",
        "stop_hit",
    )
    columns = " ".join(result.fold.train_targets.columns).lower()
    assert not any(token in columns for token in forbidden)


def test_no_preprocessing_model_weight_or_random_split_api():
    result = build_default()
    names = {field.name for field in fields(ResearchDatasetFold)} | {
        field.name for field in fields(ResearchDatasetBuildResult)
    }
    forbidden = {
        "model",
        "scorer",
        "weights",
        "sample_weight",
        "scaler",
        "encoder",
        "imputer",
        "random_state",
        "shuffle",
        "kfold",
    }
    assert names.isdisjoint(forbidden)
    assert result.fold.fold_manifest.iloc[0].preprocessing_status == (
        "NOT_IMPLEMENTED_RAW_ONLY"
    )


def test_deterministic_input_immutable_a_b_a_and_fresh_instance():
    (
        _,
        adapter,
        factual,
        train_eligibility,
        test_eligibility,
        snapshots,
        fold,
    ) = setup_inputs()
    before = factual.hypothesis_outcome_snapshots.copy(deep=True)
    builder = CausalResearchDatasetBuilder(adapter=adapter)
    kwargs = dict(
        fold_spec=fold,
        feature_snapshots=snapshots,
        factual_outcomes=factual,
        train_eligibility=train_eligibility,
        test_evaluation_eligibility=test_eligibility,
    )
    first = builder.build(**kwargs)
    repeated = builder.build(**kwargs)
    no_target_fold = replace(fold, fold_id="fold-b", test_label_as_of=None)
    builder.build(
        fold_spec=no_target_fold,
        feature_snapshots=snapshots,
        factual_outcomes=factual,
        train_eligibility=train_eligibility,
        test_evaluation_eligibility=None,
    )
    after = builder.build(**kwargs)
    fresh = CausalResearchDatasetBuilder(adapter=adapter).build(**kwargs)
    for other in (repeated, after, fresh):
        for name in fields(ResearchDatasetFold):
            pd.testing.assert_frame_equal(
                getattr(first.fold, name.name),
                getattr(other.fold, name.name),
                check_exact=True,
            )
        pd.testing.assert_frame_equal(
            first.dataset_build_audit,
            other.dataset_build_audit,
            check_exact=True,
        )
    pd.testing.assert_frame_equal(
        factual.hypothesis_outcome_snapshots, before, check_exact=True
    )


def test_future_append_and_future_market_mutation_do_not_change_historical_fold():
    result = build_default()
    baseline_hash = result.fold.fold_manifest.iloc[0].dataset_fold_hash
    # Closed upstream snapshots and eligibility identities are reused; rows outside
    # this explicit fold are not admitted by the builder.
    repeated = build_default()
    assert repeated.fold.fold_manifest.iloc[0].dataset_fold_hash == baseline_hash


def test_audit_covers_all_feature_candidates_and_no_silent_inner_join():
    result = build_default()
    audit = result.dataset_build_audit
    assert len(audit) == 2
    assert set(audit["requested_split_role"]) == {"TRAIN", "TEST"}
    assert audit["decision_snapshot_attestation_valid"].all()
    assert audit["manifest_identity_valid"].all()


def test_feature_snapshot_attestation_matches_closed_outcome_decision_hash():
    (
        _,
        _,
        factual,
        _,
        _,
        snapshots,
        _,
    ) = setup_inputs()
    factual_hashes = set(
        factual.hypothesis_outcome_snapshots["decision_snapshot_hash"].tolist()
    )
    assert {snapshot.decision_snapshot_hash for snapshot in snapshots}.issubset(
        factual_hashes
    )
    for snapshot in snapshots:
        snapshot.verify()


def test_test_creation_exact_start_excluded_exact_end_included():
    (
        bundle,
        adapter,
        factual,
        _,
        _,
        snapshots,
        _,
    ) = setup_inputs()
    eligibility_gate = TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    )
    exact_creation = key(
        adapter,
        bundle.market_frame.index,
        6,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    end_after = key(adapter, bundle.market_frame.index, 7)
    starts_exactly = WalkForwardFoldSpec(
        fold_id="exact-start",
        timeline_id=bundle.timeline_id,
        train_cutoff=exact_creation,
        test_creation_end_inclusive=end_after,
    )
    result = CausalResearchDatasetBuilder(adapter=adapter).build(
        fold_spec=starts_exactly,
        feature_snapshots=snapshots,
        factual_outcomes=factual,
        train_eligibility=eligibility_gate.evaluate(factual, exact_creation),
    )
    assert result.fold.test_features_raw.empty

    before_creation = key(adapter, bundle.market_frame.index, 5)
    ends_exactly = WalkForwardFoldSpec(
        fold_id="exact-end",
        timeline_id=bundle.timeline_id,
        train_cutoff=before_creation,
        test_creation_end_inclusive=exact_creation,
    )
    result = CausalResearchDatasetBuilder(adapter=adapter).build(
        fold_spec=ends_exactly,
        feature_snapshots=snapshots,
        factual_outcomes=factual,
        train_eligibility=eligibility_gate.evaluate(factual, before_creation),
    )
    assert len(result.fold.test_features_raw) == 1


def test_snapshot_after_test_end_is_excluded_with_audit_row():
    (
        bundle,
        adapter,
        factual,
        _,
        _,
        snapshots,
        _,
    ) = setup_inputs()
    training_cutoff = key(adapter, bundle.market_frame.index, 4)
    test_end = key(adapter, bundle.market_frame.index, 5)
    spec = WalkForwardFoldSpec(
        fold_id="before-second-hypothesis",
        timeline_id=bundle.timeline_id,
        train_cutoff=training_cutoff,
        test_creation_end_inclusive=test_end,
    )
    result = CausalResearchDatasetBuilder(adapter=adapter).build(
        fold_spec=spec,
        feature_snapshots=snapshots,
        factual_outcomes=factual,
        train_eligibility=TemporalEligibilityGate(
            adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
        ).evaluate(factual, training_cutoff),
    )
    assert result.fold.test_features_raw.empty
    second = result.dataset_build_audit[
        result.dataset_build_audit["hypothesis_id"] == 1
    ].iloc[0]
    assert second.requested_split_role == "OUTSIDE_FOLD"
    assert second.feature_join_reason == "SNAPSHOT_OUTSIDE_FOLD"


def test_tampered_factual_path_rejected_via_eligibility_reseal():
    (
        _,
        adapter,
        factual,
        train_eligibility,
        test_eligibility,
        snapshots,
        fold,
    ) = setup_inputs()
    factual.outcome_path_segments.loc[0, "favorable_excursion_fraction"] = 999.0
    with pytest.raises(DatasetContractError, match="eligibility result reseal"):
        CausalResearchDatasetBuilder(adapter=adapter).build(
            fold_spec=fold,
            feature_snapshots=snapshots,
            factual_outcomes=factual,
            train_eligibility=train_eligibility,
            test_evaluation_eligibility=test_eligibility,
        )


def test_time_indexed_dst_fold_preserves_utc_metadata():
    utc = pd.date_range("2025-10-25T22:00:00Z", periods=10, freq="h")
    local = utc.tz_convert("Europe/Vilnius")
    bundle = pipeline_bundle(index=local, timeline_id="time-dataset")
    adapter = TimeIndexedTimelineAdapter(bundle.timeline_id)
    h0 = outcome(bundle, 0, 5, adapter)
    h1_censored = outcome(bundle, 1, 7, adapter)
    h1_mature = outcome(bundle, 1, 8, adapter)
    factual = factual_batch(h0, h1_censored, h1_mature)
    train_cutoff = key(adapter, local, 5)
    test_end = key(adapter, local, 7)
    label_asof = key(adapter, local, 8)
    eligibility_gate = TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    )
    full_visible = visible(bundle, 9, adapter)
    snapshots = [
        freeze_creation_feature_snapshot(full_visible, hypothesis_id=0, adapter=adapter),
        freeze_creation_feature_snapshot(full_visible, hypothesis_id=1, adapter=adapter),
    ]
    spec = WalkForwardFoldSpec(
        fold_id="time-fold",
        timeline_id=bundle.timeline_id,
        train_cutoff=train_cutoff,
        test_creation_end_inclusive=test_end,
        test_label_as_of=label_asof,
    )
    result = CausalResearchDatasetBuilder(adapter=adapter).build(
        fold_spec=spec,
        feature_snapshots=snapshots,
        factual_outcomes=factual,
        train_eligibility=eligibility_gate.evaluate(factual, train_cutoff),
        test_evaluation_eligibility=eligibility_gate.evaluate(factual, label_asof),
    )
    timestamp_columns = [
        column
        for column in result.fold.sample_metadata.columns
        if column.endswith("_event_time_utc")
    ]
    assert timestamp_columns
    assert all(
        str(result.fold.sample_metadata[column].dtype) == "datetime64[ns, UTC]"
        for column in timestamp_columns
    )


def test_fold_hashes_and_audit_dtypes_are_deterministic():
    left = build_default()
    right = build_default()
    pd.testing.assert_frame_equal(
        left.fold.fold_manifest, right.fold.fold_manifest, check_exact=True
    )
    assert len(left.fold.fold_manifest.iloc[0].dataset_fold_hash) == 64
    assert str(left.dataset_build_audit["input_candidate_ordinal"].dtype) == "Int64"
    assert str(left.dataset_build_audit["purged"].dtype) == "boolean"
    assert str(left.fold.sample_metadata["target_available"].dtype) == "boolean"


def test_narrative_row_tampering_rejected_by_decision_snapshot_hash():
    *_, snapshots, fold = setup_inputs()
    snapshots[0].verify()
    tampered_narrative = snapshots[0].narrative_row.copy(deep=True)
    tampered_narrative.iloc[0, 0] = "FORGED_NARRATIVE_CONTEXT"
    forged = replace(snapshots[0], narrative_row=tampered_narrative)
    with pytest.raises(DatasetContractError, match="decision snapshot hash mismatch"):
        forged.verify()


def test_purge_violation_after_mocked_upstream_selection_rejected(monkeypatch):
    (
        bundle,
        adapter,
        factual,
        train_eligibility,
        _,
        snapshots,
        fold,
    ) = setup_inputs()
    selected = train_eligibility.selected_mature_samples.copy(deep=True)
    selected.loc[0, "label_information_end_inclusive_bar_position"] = 6
    selected.loc[0, "label_information_end_inclusive_information_phase"] = (
        "RESEARCH_SNAPSHOT_AVAILABLE"
    )
    selected.loc[0, "label_information_end_inclusive_deterministic_sequence"] = 0
    tampered = replace(train_eligibility, selected_mature_samples=selected)
    no_test_targets = replace(fold, test_label_as_of=None)

    def mocked_evaluate(self, batch, training_cutoff):
        return tampered

    monkeypatch.setattr(TemporalEligibilityGate, "evaluate", mocked_evaluate)
    with pytest.raises(
        DatasetContractError, match="UPSTREAM_ELIGIBILITY_CONTRACT_VIOLATION"
    ):
        CausalResearchDatasetBuilder(adapter=adapter).build(
            fold_spec=no_test_targets,
            feature_snapshots=snapshots,
            factual_outcomes=factual,
            train_eligibility=tampered,
            test_evaluation_eligibility=None,
        )


def test_explicit_test_label_asof_with_immature_test_target_preserves_na_rows():
    (
        bundle,
        adapter,
        factual,
        train_eligibility,
        _,
        snapshots,
        fold,
    ) = setup_inputs()
    immature_asof = key(adapter, bundle.market_frame.index, 7)
    immature_fold = replace(fold, test_label_as_of=immature_asof)
    immature_eligibility = TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    ).evaluate(factual, immature_asof)
    result = CausalResearchDatasetBuilder(adapter=adapter).build(
        fold_spec=immature_fold,
        feature_snapshots=snapshots,
        factual_outcomes=factual,
        train_eligibility=train_eligibility,
        test_evaluation_eligibility=immature_eligibility,
    )
    assert len(result.fold.test_features_raw) == 1
    assert len(result.fold.test_targets) == 1
    assert result.fold.test_targets.iloc[0].isna().all()
    test_metadata = result.fold.sample_metadata[
        result.fold.sample_metadata["split_role"] == "TEST"
    ].iloc[0]
    assert not test_metadata.target_available
    test_audit = result.dataset_build_audit[
        result.dataset_build_audit["requested_split_role"] == "TEST"
    ].iloc[0]
    assert test_audit.test_target_availability_status == "TEST_TARGET_IMMATURE"

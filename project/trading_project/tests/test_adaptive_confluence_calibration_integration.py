import runpy

import pandas as pd

from trading_system.calibration.adaptive_confluence import (
    BaselineRole,
    CalibrationExperimentSpec,
    CalibrationTrainingInput,
    CalibrationVariantSpec,
    ReasoningTrainingSample,
    WalkForwardAdaptiveConfluenceCalibrationBuilder,
    experiment_ledger_genesis_hash,
)
from trading_system.reasoning.evidence_families import (
    DynamicEvidenceFamilyReasoner,
    EvidenceFamily,
    ReasoningDecisionSnapshot,
)
from trading_system.research.dataset_builder import CausalResearchDatasetBuilder
from trading_system.research.dataset_contracts import WalkForwardFoldSpec, freeze_creation_feature_snapshot
from trading_system.research.eligibility import ELIGIBILITY_CONTRACT_VERSION, TemporalEligibilityGate
from trading_system.research.information_time import InformationPhase, PositionalTimelineAdapter


_helpers = runpy.run_path("tests/test_research_dataset_integration.py")


def test_real_closed_6_2a3_and_b0_train_projection_to_b1_artifact():
    bundle = _helpers["real_bundle"]()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    b1 = _helpers["outcome"](bundle, 5, adapter)
    b2 = _helpers["outcome"](bundle, 6, adapter)
    b3 = _helpers["outcome"](bundle, 7, adapter)
    factual = _helpers["batch"](b1, b2, b3)
    gate = TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    )
    full_visible = _helpers["visible"](bundle, 7, adapter)
    frozen = freeze_creation_feature_snapshot(
        full_visible, hypothesis_id=0, adapter=adapter
    )
    spec = WalkForwardFoldSpec(
        fold_id="real-fold-b1",
        timeline_id=bundle.timeline_id,
        train_cutoff=_helpers["key"](
            adapter,
            bundle.market_frame.index,
            6,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            1,
        ),
        test_creation_end_inclusive=_helpers["key"](
            adapter, bundle.market_frame.index, 7
        ),
    )
    built = CausalResearchDatasetBuilder(adapter=adapter).build(
        fold_spec=spec,
        feature_snapshots=[frozen],
        factual_outcomes=factual,
        train_eligibility=gate.evaluate(factual, spec.train_cutoff),
        test_evaluation_eligibility=None,
    )
    sample_id = str(built.fold.train_features_raw.index[0])
    snapshot = ReasoningDecisionSnapshot(
        timeline_id=frozen.timeline_id,
        decision_information_key=frozen.snapshot_information_key,
        hypothesis_id=frozen.hypothesis_id,
        evidence_row=frozen.evidence_row,
        feature_manifest=frozen.feature_manifest,
        narrative_surface_row=frozen.narrative_row,
        observation_rows=frozen.same_row_observations,
        hypothesis_rows=frozen.created_ledger_event,
        relationship_rows=frozen.same_row_relationships,
        relationship_sources=frozen.relationship_sources,
        narrative_manifest=frozen.narrative_manifest,
        reference_price=frozen.reference_price,
        reference_information_key=frozen.reference_information_key,
        reference_index_label=frozen.reference_index_label,
        decision_input_slice_hash=frozen.decision_input_slice_hash,
        decision_snapshot_hash=frozen.decision_snapshot_hash,
    )
    reasoning = DynamicEvidenceFamilyReasoner().analyze(snapshot)
    all_families = tuple(family.value for family in EvidenceFamily)
    variants = (
        CalibrationVariantSpec("null", BaselineRole.NULL_CONSTANT, ()),
        CalibrationVariantSpec(
            "simple", BaselineRole.SIMPLE_ENGINEERED_MARKET_CONTEXT,
            (EvidenceFamily.DATA_AVAILABILITY.value,),
        ),
        CalibrationVariantSpec(
            "full", BaselineRole.FULL_EVIDENCE_FAMILY, all_families
        ),
    )
    artifact = WalkForwardAdaptiveConfluenceCalibrationBuilder().fit(
        CalibrationTrainingInput(
            spec,
            built.fold,
            (ReasoningTrainingSample(sample_id, frozen, reasoning),),
        ),
        experiment=CalibrationExperimentSpec("realExp", "full"),
        variants=variants,
        existing_experiment_ledger=None,
        trusted_prior_ledger_head=experiment_ledger_genesis_hash(),
    )
    manifest = artifact.artifact_manifest.iloc[0]
    assert manifest.fold_id == spec.fold_id
    assert manifest.objective_status == "OBJECTIVE_UNDEFINED"
    assert manifest.qualification_artifact_status == "NOT_BUILT_OBJECTIVE_UNDEFINED"
    assert not artifact.feature_observation_coverage.empty
    assert not artifact.experiment_ledger_entry.empty


def test_time_indexed_dst_irregular_cutoff_is_utc_and_causal():
    helpers = runpy.run_path("tests/test_research_dataset_builder.py")
    utc = pd.DatetimeIndex(
        [
            "2025-10-25T21:00:00Z", "2025-10-25T22:00:00Z",
            "2025-10-25T23:30:00Z", "2025-10-26T01:00:00Z",
            "2025-10-26T02:00:00Z", "2025-10-26T04:30:00Z",
            "2025-10-26T05:00:00Z", "2025-10-26T07:00:00Z",
            "2025-10-26T08:15:00Z", "2025-10-26T10:00:00Z",
        ]
    ).tz_convert("Europe/Vilnius")
    bundle = helpers["pipeline_bundle"](index=utc, timeline_id="time-b1")
    adapter = helpers["TimeIndexedTimelineAdapter"](bundle.timeline_id)
    h0 = helpers["outcome"](bundle, 0, 5, adapter)
    h1_censored = helpers["outcome"](bundle, 1, 7, adapter)
    h1_mature = helpers["outcome"](bundle, 1, 8, adapter)
    factual = helpers["factual_batch"](h0, h1_censored, h1_mature)
    gate = TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    )
    visible = helpers["visible"](bundle, 9, adapter)
    frozen = freeze_creation_feature_snapshot(visible, hypothesis_id=0, adapter=adapter)
    spec = WalkForwardFoldSpec(
        fold_id="time-b1-fold",
        timeline_id=bundle.timeline_id,
        train_cutoff=helpers["key"](adapter, utc, 5),
        test_creation_end_inclusive=helpers["key"](adapter, utc, 7),
        test_label_as_of=helpers["key"](adapter, utc, 8),
    )
    built = CausalResearchDatasetBuilder(adapter=adapter).build(
        fold_spec=spec,
        feature_snapshots=[frozen],
        factual_outcomes=factual,
        train_eligibility=gate.evaluate(factual, spec.train_cutoff),
        test_evaluation_eligibility=gate.evaluate(factual, spec.test_label_as_of),
    )
    sample_id = str(built.fold.train_features_raw.index[0])
    snapshot = ReasoningDecisionSnapshot(
        timeline_id=frozen.timeline_id,
        decision_information_key=frozen.snapshot_information_key,
        hypothesis_id=frozen.hypothesis_id,
        evidence_row=frozen.evidence_row,
        feature_manifest=frozen.feature_manifest,
        narrative_surface_row=frozen.narrative_row,
        observation_rows=frozen.same_row_observations,
        hypothesis_rows=frozen.created_ledger_event,
        relationship_rows=frozen.same_row_relationships,
        relationship_sources=frozen.relationship_sources,
        narrative_manifest=frozen.narrative_manifest,
        reference_price=frozen.reference_price,
        reference_information_key=frozen.reference_information_key,
        reference_index_label=frozen.reference_index_label,
        decision_input_slice_hash=frozen.decision_input_slice_hash,
        decision_snapshot_hash=frozen.decision_snapshot_hash,
    )
    reasoning = DynamicEvidenceFamilyReasoner().analyze(snapshot)
    all_families = tuple(family.value for family in EvidenceFamily)
    variants = (
        CalibrationVariantSpec("null", BaselineRole.NULL_CONSTANT, ()),
        CalibrationVariantSpec(
            "simple", BaselineRole.SIMPLE_ENGINEERED_MARKET_CONTEXT,
            (EvidenceFamily.DATA_AVAILABILITY.value,),
        ),
        CalibrationVariantSpec("full", BaselineRole.FULL_EVIDENCE_FAMILY, all_families),
    )
    artifact = WalkForwardAdaptiveConfluenceCalibrationBuilder().fit(
        CalibrationTrainingInput(
            spec, built.fold, (ReasoningTrainingSample(sample_id, frozen, reasoning),)
        ),
        experiment=CalibrationExperimentSpec("timeExp", "full"),
        variants=variants,
        existing_experiment_ledger=None,
        trusted_prior_ledger_head=experiment_ledger_genesis_hash(),
    )
    timestamp = artifact.artifact_manifest.iloc[0].trained_through_event_time_utc
    assert str(artifact.artifact_manifest["trained_through_event_time_utc"].dtype) == (
        "datetime64[ns, UTC]"
    )
    assert timestamp == spec.train_cutoff.event_time_utc

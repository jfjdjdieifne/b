from dataclasses import fields, replace
import runpy

import pandas as pd
import pytest

from trading_system.calibration.adaptive_confluence import (
    BASELINE_PURITY_CLAIM,
    BASELINE_SEMANTICS,
    COVERAGE_SEMANTICS,
    OOS_ACCESS_SEMANTICS,
    BaselineRole,
    CalibrationContractError,
    CalibrationDataError,
    CalibrationExperimentSpec,
    CalibrationTrainingInput,
    CalibrationVariantSpec,
    ExperimentAttemptStatus,
    ObjectiveStatus,
    ReasoningTrainingSample,
    WalkForwardAdaptiveConfluenceCalibrationBuilder,
    append_experiment_ledger,
    experiment_ledger_genesis_hash,
    make_experiment_ledger_entry,
    verify_closed_training_source,
    verify_confluence_calibration_artifact,
)
from trading_system.reasoning.evidence_families import EvidenceFamily
import trading_system.research.dataset_builder as closed_dataset
from trading_system.research.dataset_builder import CausalResearchDatasetBuilder, ResearchDatasetFold
from trading_system.research.dataset_contracts import DATASET_CONTRACT_VERSION, WalkForwardFoldSpec
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import INFORMATION_KEY_VERSION, InformationKey, InformationPhase


_b0 = runpy.run_path("tests/test_evidence_family_reasoning.py")


def key(position, phase=InformationPhase.COMPLETED_ROW_AVAILABLE, sequence=1):
    return InformationKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id="reasoning",
        bar_position=position,
        event_time_utc=None,
        information_phase=phase,
        deterministic_sequence=sequence,
    )


def variants():
    all_families = tuple(family.value for family in EvidenceFamily)
    simple = (
        EvidenceFamily.LOCAL_STRUCTURE_STATE.value,
        EvidenceFamily.MULTISCALE_STRUCTURE.value,
        EvidenceFamily.VOLATILITY_CONTEXT.value,
        EvidenceFamily.TEMPORAL_CONTEXT.value,
        EvidenceFamily.DATA_AVAILABILITY.value,
    )
    return (
        CalibrationVariantSpec("null", BaselineRole.NULL_CONSTANT, ()),
        CalibrationVariantSpec(
            "simple", BaselineRole.SIMPLE_ENGINEERED_MARKET_CONTEXT, simple
        ),
        CalibrationVariantSpec("full", BaselineRole.FULL_EVIDENCE_FAMILY, all_families),
        CalibrationVariantSpec(
            "without_ob",
            BaselineRole.FAMILY_ABLATION,
            tuple(name for name in all_families if name != EvidenceFamily.OB_GEOMETRY.value),
            (EvidenceFamily.OB_GEOMETRY.value,),
        ),
    )


def experiment(experiment_id="expA", variant_id="full", oos_count=0):
    return CalibrationExperimentSpec(
        experiment_id=experiment_id,
        variant_id=variant_id,
        caller_reported_prior_oos_access_count=oos_count,
    )


def frozen_reasoning(*, actual=True, delta=0.5, delta_nan=False):
    mode = _b0["OrderFlowEvidenceMode"].ACTUAL if actual else _b0["OrderFlowEvidenceMode"].PROXY
    cfg = _b0["config"](
        environment=True,
        temporal_context=True,
        multiscale=True,
        order_flow_mode=mode,
    )
    frozen = _b0["frozen_snapshot"](
        cfg,
        delta_ratio=delta if actual and not delta_nan else None,
        delta_nan=actual and delta_nan,
        pressure=delta if not actual else None,
        mtf_balance=0.5,
    )
    return frozen, _b0["analyze"](frozen)


def _key_fields(row, prefix, information_key):
    row.update(
        {
            f"{prefix}_information_key_version": information_key.information_key_version,
            f"{prefix}_timeline_id": information_key.timeline_id,
            f"{prefix}_bar_position": information_key.bar_position,
            f"{prefix}_event_time_utc": pd.NaT if information_key.event_time_utc is None else information_key.event_time_utc,
            f"{prefix}_information_phase": information_key.information_phase.value,
            f"{prefix}_deterministic_sequence": information_key.deterministic_sequence,
        }
    )


def _metadata(sample_id, fold_id, frozen, *, split, target_available, final_position):
    row = {column: pd.NA for column in closed_dataset._METADATA_COLUMNS}
    row.update(
        {
            "sample_id": sample_id,
            "fold_id": fold_id,
            "split_role": split,
            "timeline_id": frozen.timeline_id,
            "decision_snapshot_hash": frozen.decision_snapshot_hash,
            "hypothesis_id": frozen.hypothesis_id,
            "hypothesis_type": frozen.hypothesis_type,
            "snapshot_type": frozen.snapshot_type,
            "factual_outcome_id": (
                canonical_sha256(
                    domain="TEST_MATURE_FACTUAL_OUTCOME_ID",
                    payload={"sample_id": sample_id},
                )
                if target_available
                else pd.NA
            ),
            "selected_research_snapshot_id": canonical_sha256(
                domain="TEST_RESEARCH_SNAPSHOT_ID", payload={"sample_id": sample_id}
            ),
            "target_available": target_available,
            "target_availability_reason": (
                "MATURE_FACTUAL_IDENTITY" if target_available else "TEST_TARGET_IMMATURE"
            ),
            "overlap_count_within_split": 0,
            "cross_split_label_overlap_detected": False,
            "dataset_contract_version": DATASET_CONTRACT_VERSION,
        }
    )
    _key_fields(row, "snapshot", frozen.snapshot_information_key)
    final_key = key(final_position)
    _key_fields(row, "final_outcome_known", final_key)
    _key_fields(row, "label_interval_start_exclusive", frozen.snapshot_information_key)
    _key_fields(row, "label_interval_end_inclusive", final_key)
    return row


def _targets(index, *, available):
    rows = []
    for _ in index:
        rows.append(
            {
                "target_terminal_state": "CONTRADICTED" if available else pd.NA,
                "target_pre_endpoint_favorable_excursion_fraction": 0.1 if available else pd.NA,
                "target_pre_endpoint_adverse_excursion_fraction": 0.2 if available else pd.NA,
                "target_pre_endpoint_same_bar_order_ambiguous": False if available else pd.NA,
                "target_endpoint_bar_favorable_excursion_fraction": 0.3 if available else pd.NA,
                "target_endpoint_bar_adverse_excursion_fraction": 0.4 if available else pd.NA,
                "target_endpoint_bar_same_bar_order_ambiguous": False if available else pd.NA,
            }
        )
    frame = pd.DataFrame(rows, columns=closed_dataset._TARGET_COLUMNS, index=index)
    return frame


def reseal(training, *, fold=None):
    fold = training.fold if fold is None else fold
    manifest = CausalResearchDatasetBuilder._fold_manifest(
        training.fold_spec,
        fold.train_features_raw,
        fold.train_targets,
        fold.test_features_raw,
        fold.test_targets,
        fold.sample_metadata,
        object(),
        object() if training.fold_spec.test_label_as_of is not None else None,
    )
    return replace(training, fold=replace(fold, fold_manifest=manifest))


def training_input(*, actual=True, delta_nan=False, include_test=True, cutoff=10):
    train_frozen, train_reasoning = frozen_reasoning(actual=actual, delta=0.5, delta_nan=delta_nan)
    test_frozen, _ = frozen_reasoning(actual=actual, delta=-0.5)
    spec = WalkForwardFoldSpec(
        fold_id="foldA",
        timeline_id="reasoning",
        train_cutoff=key(cutoff),
        test_creation_end_inclusive=key(cutoff + 10),
    )
    train_id = closed_dataset._sample_id(spec.fold_id, train_frozen)
    train_features = train_frozen.raw_feature_row()
    train_features.index = pd.Index([train_id], name="sample_id")
    train_targets = _targets(train_features.index, available=True)
    metadata_rows = [_metadata(train_id, spec.fold_id, train_frozen, split="TRAIN", target_available=True, final_position=2)]
    if include_test:
        test_id = closed_dataset._sample_id(spec.fold_id, test_frozen)
        test_features = test_frozen.raw_feature_row()
        test_features.index = pd.Index([test_id], name="sample_id")
        test_targets = _targets(test_features.index, available=False)
        metadata_rows.append(
            _metadata(test_id, spec.fold_id, test_frozen, split="TEST", target_available=False, final_position=20)
        )
    else:
        test_features = train_features.iloc[0:0].copy(deep=True)
        test_targets = train_targets.iloc[0:0].copy(deep=True)
    metadata = pd.DataFrame(metadata_rows, columns=closed_dataset._METADATA_COLUMNS)
    fold = ResearchDatasetFold(
        train_features_raw=train_features,
        train_targets=train_targets,
        test_features_raw=test_features,
        test_targets=test_targets,
        sample_metadata=metadata,
        fold_manifest=pd.DataFrame(),
    )
    training = CalibrationTrainingInput(
        spec,
        fold,
        (ReasoningTrainingSample(train_id, train_frozen, train_reasoning),),
    )
    return reseal(training)


def fit(training=None, exp=None, plan=None, ledger=None, head=None):
    return WalkForwardAdaptiveConfluenceCalibrationBuilder().fit(
        training or training_input(),
        experiment=exp or experiment(),
        variants=plan or variants(),
        existing_experiment_ledger=ledger,
        trusted_prior_ledger_head=(
            experiment_ledger_genesis_hash() if head is None else head
        ),
    )


def assert_content_equal(left, right):
    for name in (
        "family_observation_coverage",
        "feature_observation_coverage",
        "numeric_empirical_cdf",
        "categorical_distribution",
        "availability_support",
        "variant_family_specification",
        "variant_feature_admission",
        "stability_diagnostics",
        "calibration_manifest",
    ):
        pd.testing.assert_frame_equal(getattr(left, name), getattr(right, name), check_exact=True)
    assert left.artifact_manifest.iloc[0].calibration_content_hash == right.artifact_manifest.iloc[0].calibration_content_hash


def test_authentic_closed_fold_and_b0_reanalysis_accept():
    artifact = fit()
    assert verify_confluence_calibration_artifact(artifact)
    assert artifact.artifact_manifest.iloc[0].objective_status == ObjectiveStatus.OBJECTIVE_UNDEFINED.value


def test_arbitrary_sample_id_rejects():
    base = training_input()
    forged_features = base.fold.train_features_raw.copy(deep=True)
    forged_features.index = pd.Index(["sample0"], name="sample_id")
    forged_targets = base.fold.train_targets.copy(deep=True)
    forged_targets.index = forged_features.index
    metadata = base.fold.sample_metadata.copy(deep=True)
    metadata.loc[metadata.split_role == "TRAIN", "sample_id"] = "sample0"
    sample = replace(base.reasoning_samples[0], sample_id="sample0")
    forged = replace(base, fold=replace(base.fold, train_features_raw=forged_features, train_targets=forged_targets, sample_metadata=metadata), reasoning_samples=(sample,))
    forged = reseal(forged)
    with pytest.raises(CalibrationDataError, match="canonical CLOSED sample_id"):
        fit(forged)


def test_arbitrary_factual_identity_rejects():
    base = training_input()
    metadata = base.fold.sample_metadata.copy(deep=True)
    metadata.loc[metadata.split_role == "TRAIN", "factual_outcome_id"] = "factualA"
    forged = reseal(replace(base, fold=replace(base.fold, sample_metadata=metadata)))
    with pytest.raises(CalibrationDataError, match="factual_outcome_id"):
        fit(forged)


@pytest.mark.parametrize(
    "column",
    ["dataset_fold_hash", "raw_feature_schema_hash", "target_schema_hash", "train_sample_set_hash"],
)
def test_forged_closed_fold_identity_rejects(column):
    base = training_input()
    manifest = base.fold.fold_manifest.copy(deep=True)
    manifest.loc[0, column] = "0" * 64
    with pytest.raises(CalibrationDataError, match="authoritative CLOSED dataset fold seal"):
        fit(replace(base, fold=replace(base.fold, fold_manifest=manifest)))


def test_fabricated_fold_with_only_local_subset_hashes_rejects():
    base = training_input()
    manifest = base.fold.fold_manifest.copy(deep=True)
    manifest.loc[0, "dataset_fold_hash"] = canonical_sha256(
        domain="LOCAL_SUBSET_NOT_CLOSED", payload=base.fold.train_features_raw
    )
    with pytest.raises(CalibrationDataError, match="authoritative CLOSED dataset fold seal"):
        fit(replace(base, fold=replace(base.fold, fold_manifest=manifest)))


def test_train_raw_feature_tampering_rejects_even_when_source_resealed():
    base = training_input()
    features = base.fold.train_features_raw.copy(deep=True)
    numeric_column = next(
        column for column in features
        if pd.api.types.is_numeric_dtype(features[column].dtype)
        and not pd.api.types.is_bool_dtype(features[column].dtype)
    )
    features.loc[features.index[0], numeric_column] = 999.0
    forged = reseal(replace(base, fold=replace(base.fold, train_features_raw=features)))
    with pytest.raises(CalibrationDataError, match="TRAIN raw feature row"):
        fit(forged)


def _forged_reasoning(base, operation):
    sample = base.reasoning_samples[0]
    result = sample.reasoning
    if operation == "add":
        records = pd.concat([result.evidence_records, result.evidence_records.iloc[[0]]], ignore_index=True)
        records.loc[records.index[-1], "record_id"] = "a" * 64
    elif operation == "remove":
        records = result.evidence_records.iloc[:-1].copy(deep=True)
    else:
        relations = result.provenance_relations.copy(deep=True)
        relations.loc[0, "proof_contract"] = "FORGED"
        return replace(result, provenance_relations=relations)
    return replace(result, evidence_records=records)


@pytest.mark.parametrize("operation", ["add", "remove", "provenance"])
def test_complete_b0_membership_reanalysis_rejects_forgery(operation):
    base = training_input()
    sample = base.reasoning_samples[0]
    forged = replace(sample, reasoning=_forged_reasoning(base, operation))
    with pytest.raises(CalibrationDataError, match="B-0 authoritative re-analysis mismatch"):
        fit(replace(base, reasoning_samples=(forged,)))


def test_target_payload_change_requires_new_source_seal_but_not_train_content():
    base = training_input()
    targets = base.fold.train_targets.copy(deep=True)
    targets.iloc[0, 0] = "ARBITRARY_FACTUAL_PAYLOAD"
    changed = reseal(replace(base, fold=replace(base.fold, train_targets=targets)))
    left, right = fit(base), fit(changed)
    assert_content_equal(left, right)
    assert left.artifact_manifest.iloc[0].source_dataset_fold_hash != right.artifact_manifest.iloc[0].source_dataset_fold_hash
    assert left.artifact_manifest.iloc[0].artifact_hash != right.artifact_manifest.iloc[0].artifact_hash


def test_test_replacement_changes_source_seal_not_train_calibration_content():
    base = training_input()
    test_features = base.fold.test_features_raw.copy(deep=True)
    numeric = [
        column for column in test_features
        if pd.api.types.is_numeric_dtype(test_features[column].dtype)
        and not pd.api.types.is_bool_dtype(test_features[column].dtype)
    ]
    for column in numeric:
        test_features[column] = pd.array([0] * len(test_features), dtype=test_features[column].dtype)
    changed = reseal(replace(base, fold=replace(base.fold, test_features_raw=test_features)))
    left, right = fit(base), fit(changed)
    assert_content_equal(left, right)
    assert left.artifact_manifest.iloc[0].source_dataset_fold_hash != right.artifact_manifest.iloc[0].source_dataset_fold_hash


def test_coverage_semantics_are_machine_readable_not_predictive_support():
    artifact = fit()
    assert set(artifact.family_observation_coverage.measure_semantics) == {COVERAGE_SEMANTICS}
    assert set(artifact.feature_observation_coverage.measure_semantics) == {COVERAGE_SEMANTICS}
    assert "family_support" not in artifact.__dataclass_fields__
    assert not artifact.feature_observation_coverage.semantic_state.eq("SUPPORT").any()


def test_simple_baseline_truthfully_described_and_exact():
    artifact = fit()
    rows = artifact.variant_family_specification
    simple = rows[rows.variant_id == "simple"]
    assert set(simple.baseline_semantics) == {BASELINE_SEMANTICS}
    assert set(simple.purity_claim) == {BASELINE_PURITY_CLAIM}
    assert set(simple.loc[simple.admitted, "family_name"]) == set(variants()[1].admitted_families)


def test_full_simple_and_ablation_change_artifact_identity():
    full = fit(exp=experiment("sameExp", "full"))
    simple = fit(exp=experiment("sameExp", "simple"))
    ablated = fit(exp=experiment("sameExp", "without_ob"))
    hashes = {item.artifact_manifest.iloc[0].artifact_hash for item in (full, simple, ablated)}
    assert len(hashes) == 3


def test_artifact_verifier_rejects_manifest_and_component_policy_tampering():
    artifact = fit()
    for column in (
        "eligibility_manifest_hash", "reasoning_contract_version",
        "source_mode_policy", "missingness_policy", "dependence_status",
    ):
        manifest = artifact.artifact_manifest.copy(deep=True)
        manifest.loc[0, column] = "TAMPERED"
        with pytest.raises(CalibrationContractError):
            verify_confluence_calibration_artifact(replace(artifact, artifact_manifest=manifest))
    coverage = artifact.family_observation_coverage.copy(deep=True)
    coverage.loc[0, "raw_sample_count"] += 1
    with pytest.raises(CalibrationContractError, match="component hash"):
        verify_confluence_calibration_artifact(replace(artifact, family_observation_coverage=coverage))
    projection = artifact.training_projection_manifest.copy(deep=True)
    projection.loc[0, "train_features_hash"] = "0" * 64
    with pytest.raises(CalibrationContractError, match="training projection"):
        verify_confluence_calibration_artifact(
            replace(artifact, training_projection_manifest=projection)
        )


def test_experiment_ledger_chain_and_trusted_head():
    first = fit(exp=experiment("expA"))
    genesis = experiment_ledger_genesis_hash()
    ledger = append_experiment_ledger(None, first.experiment_ledger_entry, trusted_expected_prior_head=genesis)
    head = str(ledger.iloc[-1].ledger_entry_hash)
    second = fit(exp=experiment("expB"), ledger=ledger, head=head)
    combined = append_experiment_ledger(ledger, second.experiment_ledger_entry, trusted_expected_prior_head=head)
    assert combined.experiment_id.tolist() == ["expA", "expB"]
    with pytest.raises(CalibrationContractError, match="trusted prior ledger head"):
        append_experiment_ledger(ledger.iloc[:0], second.experiment_ledger_entry, trusted_expected_prior_head=head)
    full_head = str(combined.iloc[-1].ledger_entry_hash)
    third = fit(exp=experiment("expC"), ledger=combined, head=full_head)
    with pytest.raises(CalibrationContractError, match="trusted prior ledger head"):
        append_experiment_ledger(
            combined.iloc[:1].copy(),
            third.experiment_ledger_entry,
            trusted_expected_prior_head=full_head,
        )
    mutated = combined.copy(deep=True)
    mutated.loc[0, "experiment_id"] = "replaced"
    with pytest.raises(CalibrationContractError):
        append_experiment_ledger(mutated, second.experiment_ledger_entry, trusted_expected_prior_head=str(combined.iloc[-1].ledger_entry_hash))
    reordered = combined.iloc[::-1].reset_index(drop=True)
    with pytest.raises(CalibrationContractError):
        append_experiment_ledger(reordered, second.experiment_ledger_entry, trusted_expected_prior_head=str(combined.iloc[-1].ledger_entry_hash))


def test_wrong_expected_head_and_duplicate_experiment_reject():
    first = fit(exp=experiment("expA"))
    genesis = experiment_ledger_genesis_hash()
    ledger = append_experiment_ledger(None, first.experiment_ledger_entry, trusted_expected_prior_head=genesis)
    head = str(ledger.iloc[-1].ledger_entry_hash)
    with pytest.raises(CalibrationContractError, match="trusted prior ledger head"):
        fit(exp=experiment("expB"), ledger=ledger, head="0" * 64)
    with pytest.raises(CalibrationContractError, match="duplicate experiment_id"):
        fit(exp=experiment("expA"), ledger=ledger, head=head)


def test_caller_reported_oos_access_is_not_purity_certification():
    artifact = fit(exp=experiment(oos_count=7))
    entry = artifact.experiment_ledger_entry.iloc[0]
    assert int(entry.caller_reported_prior_oos_access_count) == 7
    assert entry.oos_access_semantics == OOS_ACCESS_SEMANTICS
    assert "OOS_UNTOUCHED" not in " ".join(artifact.calibration_manifest.astype(str).to_numpy().ravel())


def test_unknown_unavailable_actual_proxy_and_overlap_preserved():
    unknown = fit(training_input(delta_nan=True))
    assert "UNKNOWN" in set(unknown.feature_observation_coverage.semantic_state)
    assert "UNAVAILABLE" in set(unknown.family_observation_coverage.availability_state)
    actual = fit(training_input(actual=True))
    proxy = fit(training_input(actual=False))
    assert "ACTUAL" in set(actual.feature_observation_coverage.source_mode)
    assert "PROXY" in set(proxy.feature_observation_coverage.source_mode)
    assert actual.artifact_manifest.iloc[0].dependence_status == "DEPENDENCE_NOT_RESOLVED"


def test_empirical_cdf_is_train_only_descriptive_not_probability():
    artifact = fit()
    assert artifact.numeric_empirical_cdf.rank_semantics.eq("TRAIN_EMPIRICAL_CDF_NOT_PROBABILITY").all()
    assert artifact.numeric_empirical_cdf.empirical_cdf.between(0, 1).all()


def test_objective_model_preprocessing_gate_remains_closed():
    artifact = fit()
    row = artifact.artifact_manifest.iloc[0]
    assert row.objective_status == ObjectiveStatus.OBJECTIVE_UNDEFINED.value
    assert row.qualification_artifact_status == "NOT_BUILT_OBJECTIVE_UNDEFINED"
    assert row.model_spec_id == "NO_PREDICTIVE_MODEL_OBJECTIVE_UNDEFINED_V1"


def test_a_a_a_b_a_fresh_instance_and_input_immutability():
    a = training_input(actual=True)
    b = training_input(actual=False)
    fold_frames = (
        "train_features_raw", "train_targets", "test_features_raw",
        "test_targets", "sample_metadata", "fold_manifest",
    )
    before = {
        name: getattr(a.fold, name).copy(deep=True) for name in fold_frames
    }
    frozen = a.reasoning_samples[0].feature_snapshot
    frozen_frames = (
        "evidence_row", "narrative_row", "created_ledger_event",
        "same_row_observations", "same_row_relationships",
        "relationship_sources", "feature_manifest", "narrative_manifest",
    )
    before_frozen = {
        name: getattr(frozen, name).copy(deep=True) for name in frozen_frames
    }
    builder = WalkForwardAdaptiveConfluenceCalibrationBuilder()
    kwargs = dict(experiment=experiment(), variants=variants(), existing_experiment_ledger=None, trusted_prior_ledger_head=experiment_ledger_genesis_hash())
    first = builder.fit(a, **kwargs)
    repeated = builder.fit(a, **kwargs)
    builder.fit(b, **kwargs)
    after = builder.fit(a, **kwargs)
    fresh = WalkForwardAdaptiveConfluenceCalibrationBuilder().fit(a, **kwargs)
    for other in (repeated, after, fresh):
        assert_content_equal(first, other)
        pd.testing.assert_frame_equal(first.artifact_manifest, other.artifact_manifest, check_exact=True)
    for name in fold_frames:
        pd.testing.assert_frame_equal(getattr(a.fold, name), before[name], check_exact=True)
    for name in frozen_frames:
        pd.testing.assert_frame_equal(getattr(frozen, name), before_frozen[name], check_exact=True)


def test_future_test_append_keeps_train_content_when_authentically_resealed():
    without = training_input(include_test=False)
    with_test = training_input(include_test=True)
    left, right = fit(without), fit(with_test)
    assert_content_equal(left, right)


def test_no_predictive_or_trading_imports():
    import ast
    from pathlib import Path
    tree = ast.parse(Path("src/trading_system/calibration/adaptive_confluence.py").read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(token in module for module in imports for token in ("model", "scorer", "geometry", "execution"))

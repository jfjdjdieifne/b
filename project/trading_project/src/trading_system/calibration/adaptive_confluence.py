"""Module 6.2B-1 V1.1: TRAIN-only descriptive confluence calibration foundation.

The current CLOSED outcome/lifecycle contracts do not authorize a predictive
QualificationObjective.  V1 therefore builds only frozen empirical support,
availability, provenance-aware feature registries, baseline/ablation admission,
and experiment-accounting artifacts.  It fits no predictive market meaning.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import math
import re
from typing import Final

import numpy as np
import pandas as pd

from trading_system.reasoning.evidence_families import (
    REASONING_CONTRACT_VERSION,
    DynamicEvidenceFamilyReasoner,
    ReasoningDecisionSnapshot,
    EvidenceFamily,
    EvidenceFamilyReasoningResult,
    reasoning_contract_manifest,
    reasoning_record_hash_payload,
)
import trading_system.research.dataset_builder as _closed_dataset_builder
from trading_system.research.dataset_builder import (
    CausalResearchDatasetBuilder,
    ResearchDatasetFold,
)
from trading_system.research.dataset_contracts import (
    DATASET_CONTRACT_VERSION,
    FrozenDecisionFeatureSnapshot,
    WalkForwardFoldSpec,
)
from trading_system.research.eligibility import eligibility_manifest
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import InformationKey, InformationPhase


CALIBRATION_CONTRACT_VERSION: Final = "WALK_FORWARD_ADAPTIVE_CONFLUENCE_CALIBRATION_V1_1"
ARTIFACT_TYPE: Final = "DESCRIPTIVE_CONFLUENCE_CALIBRATION_ARTIFACT"
OBJECTIVE_ID: Final = "OBJECTIVE_UNDEFINED_RESEARCH_DEBT_020"
OBJECTIVE_VERSION: Final = "OBJECTIVE_UNDEFINED_V1"
PREPROCESSING_ID: Final = "IDENTITY_TYPED_NO_FITTED_TRANSFORM_V1"
MODEL_SPEC_ID: Final = "NO_PREDICTIVE_MODEL_OBJECTIVE_UNDEFINED_V1"
INTERACTION_CONTRACT: Final = "NO_PREDICTIVE_INTERACTIONS_OBJECTIVE_UNDEFINED"
DEPENDENCE_STATUS: Final = "DEPENDENCE_NOT_RESOLVED"
EVALUATION_ROLE: Final = "TRAIN_DESCRIPTIVE_ONLY"
COVERAGE_SEMANTICS: Final = "TRAIN_OBSERVATION_COVERAGE_NOT_SEMANTIC_OR_PREDICTIVE_SUPPORT"
BASELINE_SEMANTICS: Final = "EXPLICIT_SIMPLE_ENGINEERED_MARKET_CONTEXT_BASELINE"
BASELINE_PURITY_CLAIM: Final = "NOT_A_NON_ICT_PURITY_CLAIM"
OOS_ACCESS_SEMANTICS: Final = "CALLER_REPORTED_ACCOUNTING_NOT_ACCESS_CONTROL"
LEDGER_CONTRACT_VERSION: Final = "CALIBRATION_EXPERIMENT_LEDGER_V1_1"
SIMPLE_ENGINEERED_CONTEXT_ALLOWED_FAMILIES: Final = frozenset(
    {
        EvidenceFamily.LOCAL_STRUCTURE_STATE.value,
        EvidenceFamily.MULTISCALE_STRUCTURE.value,
        EvidenceFamily.VOLATILITY_CONTEXT.value,
        EvidenceFamily.TEMPORAL_CONTEXT.value,
        EvidenceFamily.DATA_AVAILABILITY.value,
    }
)


class CalibrationContractError(Exception):
    """Static contract, identity, objective, or experiment-ledger violation."""


class CalibrationDataError(Exception):
    """Malformed or causally illegal TRAIN input."""


class ObjectiveStatus(Enum):
    OBJECTIVE_UNDEFINED = "OBJECTIVE_UNDEFINED"
    NOT_CALIBRATED = "NOT_CALIBRATED"
    UNSUPPORTED_CONTEXT = "UNSUPPORTED_CONTEXT"


class BaselineRole(Enum):
    NULL_CONSTANT = "NULL_CONSTANT"
    SIMPLE_ENGINEERED_MARKET_CONTEXT = "SIMPLE_ENGINEERED_MARKET_CONTEXT"
    FULL_EVIDENCE_FAMILY = "FULL_EVIDENCE_FAMILY"
    FAMILY_ABLATION = "FAMILY_ABLATION"


class ExperimentAttemptStatus(Enum):
    SPECIFIED = "SPECIFIED"
    ARTIFACT_BUILT = "ARTIFACT_BUILT"
    FAILED = "FAILED"


_SAFE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]*")


def _safe_id(value: str, field: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise CalibrationContractError(f"invalid {field}")
    return value


def _strict_bool(value, field: str) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise CalibrationDataError(f"{field} must be bool")
    return bool(value)


def _hex64(value, field: str) -> str:
    text = str(value)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise CalibrationDataError(f"invalid {field}")
    return text


def experiment_ledger_genesis_hash() -> str:
    return canonical_sha256(
        domain="CALIBRATION_EXPERIMENT_LEDGER_GENESIS_V1_1",
        payload={"ledger_contract_version": LEDGER_CONTRACT_VERSION},
    )


def _key_from_row(row: pd.Series, prefix: str) -> InformationKey:
    timestamp = row[f"{prefix}_event_time_utc"]
    return InformationKey(
        information_key_version=str(row[f"{prefix}_information_key_version"]),
        timeline_id=str(row[f"{prefix}_timeline_id"]),
        bar_position=int(row[f"{prefix}_bar_position"]),
        event_time_utc=None if pd.isna(timestamp) else timestamp,
        information_phase=InformationPhase(str(row[f"{prefix}_information_phase"])),
        deterministic_sequence=int(row[f"{prefix}_deterministic_sequence"]),
    )


def _decision_key_from_family(row: pd.Series) -> InformationKey:
    timestamp = row["decision_event_time_utc"]
    return InformationKey(
        information_key_version=str(row["decision_information_key_version"]),
        timeline_id=str(row["timeline_id"]),
        bar_position=int(row["decision_bar_position"]),
        event_time_utc=None if pd.isna(timestamp) else timestamp,
        information_phase=InformationPhase(str(row["decision_information_phase"])),
        deterministic_sequence=int(row["decision_deterministic_sequence"]),
    )


def _reasoning_snapshot_from_frozen(
    frozen: FrozenDecisionFeatureSnapshot,
) -> ReasoningDecisionSnapshot:
    frozen.verify()
    return ReasoningDecisionSnapshot(
        timeline_id=frozen.timeline_id,
        decision_information_key=frozen.snapshot_information_key,
        hypothesis_id=frozen.hypothesis_id,
        evidence_row=frozen.evidence_row.copy(deep=True),
        feature_manifest=frozen.feature_manifest.copy(deep=True),
        narrative_surface_row=frozen.narrative_row.copy(deep=True),
        observation_rows=frozen.same_row_observations.copy(deep=True),
        hypothesis_rows=frozen.created_ledger_event.copy(deep=True),
        relationship_rows=frozen.same_row_relationships.copy(deep=True),
        relationship_sources=frozen.relationship_sources.copy(deep=True),
        narrative_manifest=frozen.narrative_manifest.copy(deep=True),
        reference_price=frozen.reference_price,
        reference_information_key=frozen.reference_information_key,
        reference_index_label=frozen.reference_index_label,
        decision_input_slice_hash=frozen.decision_input_slice_hash,
        decision_snapshot_hash=frozen.decision_snapshot_hash,
    )


def _assert_reasoning_result_equal(
    supplied: EvidenceFamilyReasoningResult,
    expected: EvidenceFamilyReasoningResult,
) -> None:
    for field_name in supplied.__dataclass_fields__:
        try:
            pd.testing.assert_frame_equal(
                getattr(supplied, field_name),
                getattr(expected, field_name),
                check_exact=True,
            )
        except AssertionError as exc:
            raise CalibrationDataError(
                f"B-0 authoritative re-analysis mismatch: {field_name}"
            ) from exc


@dataclass(frozen=True)
class ReasoningTrainingSample:
    sample_id: str
    feature_snapshot: FrozenDecisionFeatureSnapshot
    reasoning: EvidenceFamilyReasoningResult

    def __post_init__(self):
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise CalibrationContractError("invalid sample_id")
        if not isinstance(self.feature_snapshot, FrozenDecisionFeatureSnapshot):
            raise CalibrationContractError("FrozenDecisionFeatureSnapshot required")
        if not isinstance(self.reasoning, EvidenceFamilyReasoningResult):
            raise CalibrationContractError("EvidenceFamilyReasoningResult required")


@dataclass(frozen=True)
class CalibrationTrainingInput:
    fold_spec: WalkForwardFoldSpec
    fold: ResearchDatasetFold
    reasoning_samples: tuple[ReasoningTrainingSample, ...]

    def __post_init__(self):
        if not isinstance(self.fold_spec, WalkForwardFoldSpec):
            raise CalibrationContractError("WalkForwardFoldSpec required")
        if not isinstance(self.fold, ResearchDatasetFold):
            raise CalibrationContractError("ResearchDatasetFold required")
        if not isinstance(self.reasoning_samples, tuple) or any(
            not isinstance(item, ReasoningTrainingSample) for item in self.reasoning_samples
        ):
            raise CalibrationContractError("reasoning_samples must be tuple")


@dataclass(frozen=True)
class CalibrationVariantSpec:
    variant_id: str
    role: BaselineRole
    admitted_families: tuple[str, ...]
    withheld_families: tuple[str, ...] = ()

    def __post_init__(self):
        _safe_id(self.variant_id, "variant_id")
        if not isinstance(self.role, BaselineRole):
            raise CalibrationContractError("explicit BaselineRole required")
        for name, values in (
            ("admitted_families", self.admitted_families),
            ("withheld_families", self.withheld_families),
        ):
            if not isinstance(values, tuple) or len(values) != len(set(values)):
                raise CalibrationContractError(f"invalid {name}")
            try:
                tuple(EvidenceFamily(value) for value in values)
            except ValueError as exc:
                raise CalibrationContractError(f"unknown family in {name}") from exc


@dataclass(frozen=True)
class CalibrationExperimentSpec:
    experiment_id: str
    variant_id: str
    evaluation_role: str = EVALUATION_ROLE
    objective_id: str = OBJECTIVE_ID
    objective_version: str = OBJECTIVE_VERSION
    preprocessing_id: str = PREPROCESSING_ID
    model_spec_id: str = MODEL_SPEC_ID
    allowed_interactions: str = INTERACTION_CONTRACT
    hyperparameters_json: str = "{}"
    random_seed: int | None = None
    caller_reported_prior_oos_access_count: int = 0

    def __post_init__(self):
        _safe_id(self.experiment_id, "experiment_id")
        _safe_id(self.variant_id, "variant_id")
        if self.evaluation_role != EVALUATION_ROLE:
            raise CalibrationContractError("V1 evaluation role must be TRAIN_DESCRIPTIVE_ONLY")
        if self.objective_id != OBJECTIVE_ID or self.objective_version != OBJECTIVE_VERSION:
            raise CalibrationContractError("QualificationObjective is not legally defined")
        if self.preprocessing_id != PREPROCESSING_ID:
            raise CalibrationContractError("fitted preprocessing is not authorized in V1")
        if self.model_spec_id != MODEL_SPEC_ID or self.allowed_interactions != INTERACTION_CONTRACT:
            raise CalibrationContractError("predictive model/interactions are not authorized")
        try:
            parsed = json.loads(self.hyperparameters_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise CalibrationContractError("hyperparameters_json must be canonical JSON") from exc
        if not isinstance(parsed, dict) or parsed:
            raise CalibrationContractError("V1 has no model hyperparameters")
        if self.random_seed is not None and (
            isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int)
        ):
            raise CalibrationContractError("invalid random_seed")
        if (
            isinstance(self.caller_reported_prior_oos_access_count, bool)
            or not isinstance(self.caller_reported_prior_oos_access_count, int)
            or self.caller_reported_prior_oos_access_count < 0
        ):
            raise CalibrationContractError("invalid caller_reported_prior_oos_access_count")


@dataclass(frozen=True)
class ConfluenceCalibrationArtifact:
    artifact_manifest: pd.DataFrame
    training_projection_manifest: pd.DataFrame
    family_observation_coverage: pd.DataFrame
    feature_observation_coverage: pd.DataFrame
    numeric_empirical_cdf: pd.DataFrame
    categorical_distribution: pd.DataFrame
    availability_support: pd.DataFrame
    variant_family_specification: pd.DataFrame
    variant_feature_admission: pd.DataFrame
    stability_diagnostics: pd.DataFrame
    experiment_ledger_entry: pd.DataFrame
    calibration_manifest: pd.DataFrame


_FAMILY_COVERAGE_COLUMNS = (
    "hypothesis_type", "family_name", "aggregate_semantic_state",
    "availability_state", "conflict_present", "source_mode_scope",
    "raw_sample_count", "distinct_reasoning_identity_count", "dependence_status",
    "measure_semantics",
)
_FEATURE_COVERAGE_COLUMNS = (
    "family_name", "source_record_id", "record_kind", "semantic_state",
    "availability_state", "source_mode", "provenance_status", "derivation_status",
    "raw_observation_count", "nonmissing_typed_value_count", "dependence_status",
    "measure_semantics",
)
_NUMERIC_CDF_COLUMNS = (
    "hypothesis_type", "family_name", "source_record_id", "source_mode",
    "value_float", "value_float_hex", "cumulative_count", "total_count",
    "empirical_cdf", "rank_semantics",
)
_CATEGORY_COLUMNS = (
    "hypothesis_type", "family_name", "source_record_id", "source_mode",
    "value_type", "value_text", "raw_count", "total_count", "raw_fraction",
)
_AVAILABILITY_COLUMNS = (
    "hypothesis_type", "global_availability_signature_hash", "raw_sample_count",
    "dependence_status", "calibration_status",
)
_VARIANT_FAMILY_COLUMNS = (
    "variant_id", "baseline_role", "baseline_semantics", "purity_claim",
    "family_name", "admitted", "withheld", "variant_spec_hash",
)
_VARIANT_COLUMNS = (
    "variant_id", "baseline_role", "baseline_semantics", "purity_claim",
    "family_name", "source_record_id", "admitted", "withheld",
    "variant_spec_hash",
)
_DIAGNOSTIC_COLUMNS = (
    "diagnostic_name", "status", "raw_value_integer", "detail",
)
_EXPERIMENT_COLUMNS = (
    "ledger_contract_version", "ledger_sequence", "previous_entry_hash",
    "experiment_id", "training_cutoff_identity",
    "fold_id", "fold_spec_hash", "train_sample_set_hash",
    "training_projection_hash", "objective_id", "objective_version",
    "feature_family_spec_hash", "allowed_interactions", "preprocessing_id",
    "model_spec_id", "hyperparameters_json", "random_seed",
    "variant_id", "evaluation_role", "caller_reported_prior_oos_access_count",
    "oos_access_semantics", "attempt_status", "failure_reason", "artifact_hash",
    "ledger_entry_hash",
)


def _typed(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    int_cols = {
        "raw_sample_count", "distinct_reasoning_identity_count", "raw_observation_count",
        "nonmissing_typed_value_count", "cumulative_count", "total_count", "raw_count",
        "raw_value_integer", "ledger_sequence", "random_seed", "caller_reported_prior_oos_access_count",
        "trained_through_bar_position", "trained_through_deterministic_sequence",
    }
    float_cols = {"value_float", "empirical_cdf", "raw_fraction"}
    bool_cols = {"conflict_present", "admitted", "withheld"}
    for column in result.columns:
        if column.endswith("_event_time_utc"):
            result[column] = pd.to_datetime(result[column], utc=True)
        elif column in int_cols:
            result[column] = pd.array(result[column], dtype="Int64")
        elif column in float_cols:
            result[column] = pd.array(result[column], dtype="Float64")
        elif column in bool_cols:
            result[column] = pd.array(result[column], dtype="boolean")
        else:
            result[column] = pd.array(result[column], dtype="string")
    return result


def _fold_spec_hash(spec: WalkForwardFoldSpec) -> str:
    return canonical_sha256(
        domain="RESEARCH_FOLD_SPEC_V1",
        payload={
            "fold_id": spec.fold_id,
            "timeline_id": spec.timeline_id,
            "train_cutoff": spec.train_cutoff,
            "test_creation_end_inclusive": spec.test_creation_end_inclusive,
            "test_label_as_of": spec.test_label_as_of,
        },
    )


def _validate_variant_set(variants: tuple[CalibrationVariantSpec, ...], families: set[str]):
    if not isinstance(variants, tuple) or not variants:
        raise CalibrationContractError("explicit nonempty calibration variants required")
    ids = [variant.variant_id for variant in variants]
    if len(ids) != len(set(ids)):
        raise CalibrationContractError("duplicate variant_id")
    full = set(families)
    roles = {variant.role for variant in variants}
    required = {
        BaselineRole.NULL_CONSTANT,
        BaselineRole.SIMPLE_ENGINEERED_MARKET_CONTEXT,
        BaselineRole.FULL_EVIDENCE_FAMILY,
    }
    if not required.issubset(roles):
        raise CalibrationContractError("NULL, SIMPLE, and FULL variants are mandatory")
    for variant in variants:
        admitted = set(variant.admitted_families)
        withheld = set(variant.withheld_families)
        if not admitted.issubset(full) or not withheld.issubset(full):
            raise CalibrationContractError("variant family outside TRAIN schema")
        if admitted & withheld:
            raise CalibrationContractError("family cannot be admitted and withheld")
        if variant.role is BaselineRole.NULL_CONSTANT and (admitted or withheld):
            raise CalibrationContractError("NULL baseline admits no family")
        if variant.role is BaselineRole.SIMPLE_ENGINEERED_MARKET_CONTEXT and (not admitted or admitted == full):
            raise CalibrationContractError("SIMPLE baseline must be an explicit proper subset")
        if variant.role is BaselineRole.SIMPLE_ENGINEERED_MARKET_CONTEXT and not admitted.issubset(
            SIMPLE_ENGINEERED_CONTEXT_ALLOWED_FAMILIES
        ):
            raise CalibrationContractError("SIMPLE engineered baseline family outside explicit contract")
        if variant.role is BaselineRole.FULL_EVIDENCE_FAMILY and (
            admitted != full or withheld
        ):
            raise CalibrationContractError("FULL variant must admit exact TRAIN family schema")
        if variant.role is BaselineRole.FAMILY_ABLATION and (
            not withheld or admitted != full - withheld
        ):
            raise CalibrationContractError("ablation must be exact FULL-minus-withheld")


def _record_value_count(record: pd.Series) -> int:
    return int(
        any(
            not pd.isna(record[column])
            for column in (
                "primary_value_float", "primary_value_integer",
                "primary_value_boolean", "primary_value_category",
            )
        )
    )


def verify_closed_training_source(training: CalibrationTrainingInput) -> pd.DataFrame:
    """Verify the exact CLOSED 6.2A-3 full-fold seal before TRAIN projection.

    This is source-integrity verification.  The returned frozen source manifest
    is provenance; fitted descriptive content is derived later from TRAIN only.
    """
    if not isinstance(training, CalibrationTrainingInput):
        raise CalibrationContractError("CalibrationTrainingInput required")
    spec, fold = training.fold_spec, training.fold
    if tuple(fold.train_targets.columns) != tuple(_closed_dataset_builder._TARGET_COLUMNS):
        raise CalibrationDataError("CLOSED target schema mismatch")
    if tuple(fold.test_targets.columns) != tuple(_closed_dataset_builder._TARGET_COLUMNS):
        raise CalibrationDataError("CLOSED test target schema mismatch")
    if tuple(fold.sample_metadata.columns) != tuple(_closed_dataset_builder._METADATA_COLUMNS):
        raise CalibrationDataError("CLOSED sample metadata schema mismatch")
    if tuple(fold.train_features_raw.columns) != tuple(fold.test_features_raw.columns):
        raise CalibrationDataError("CLOSED train/test raw feature schema mismatch")
    expected = CausalResearchDatasetBuilder._fold_manifest(
        spec,
        fold.train_features_raw,
        fold.train_targets,
        fold.test_features_raw,
        fold.test_targets,
        fold.sample_metadata,
        object(),
        object() if spec.test_label_as_of is not None else None,
    )
    try:
        pd.testing.assert_frame_equal(fold.fold_manifest, expected, check_exact=True)
    except AssertionError as exc:
        raise CalibrationDataError("authoritative CLOSED dataset fold seal mismatch") from exc
    if len(expected) != 1:
        raise CalibrationDataError("exactly one CLOSED fold manifest row required")
    return expected.copy(deep=True)


class WalkForwardAdaptiveConfluenceCalibrationBuilder:
    """Stateless TRAIN-only builder; V1 fits descriptive support, not a model."""

    def fit(
        self,
        training: CalibrationTrainingInput,
        *,
        experiment: CalibrationExperimentSpec,
        variants: tuple[CalibrationVariantSpec, ...],
        existing_experiment_ledger: pd.DataFrame | None,
        trusted_prior_ledger_head: str,
    ) -> ConfluenceCalibrationArtifact:
        if not isinstance(training, CalibrationTrainingInput):
            raise CalibrationContractError("CalibrationTrainingInput required")
        if not isinstance(experiment, CalibrationExperimentSpec):
            raise CalibrationContractError("CalibrationExperimentSpec required")
        _hex64(trusted_prior_ledger_head, "trusted_prior_ledger_head")
        spec, fold = training.fold_spec, training.fold
        cutoff = spec.train_cutoff
        if spec.fold_contract_version != DATASET_CONTRACT_VERSION:
            raise CalibrationContractError("dataset contract mismatch")
        verified_source_manifest = verify_closed_training_source(training)
        manifest_row = verified_source_manifest.iloc[0]
        if str(manifest_row["dataset_contract_version"]) != DATASET_CONTRACT_VERSION:
            raise CalibrationDataError("fold dataset contract mismatch")
        if str(manifest_row["fold_id"]) != spec.fold_id:
            raise CalibrationDataError("fold_id mismatch")
        expected_fold_spec_hash = _fold_spec_hash(spec)
        if _hex64(manifest_row["fold_spec_hash"], "fold_spec_hash") != expected_fold_spec_hash:
            raise CalibrationDataError("fold_spec_hash mismatch")
        eligibility_hash = canonical_sha256(
            domain="ELIGIBILITY_MANIFEST_V1", payload=eligibility_manifest()
        )
        if _hex64(
            manifest_row["train_eligibility_manifest_hash"],
            "train_eligibility_manifest_hash",
        ) != eligibility_hash:
            raise CalibrationDataError("eligibility manifest mismatch")

        train_features = fold.train_features_raw
        if not isinstance(train_features, pd.DataFrame) or train_features.index.has_duplicates:
            raise CalibrationDataError("invalid train_features_raw")
        train_ids = [str(value) for value in train_features.index]
        expected_train_hash = canonical_sha256(
            domain="RESEARCH_TRAIN_SAMPLE_SET_V1", payload=train_ids
        )
        if _hex64(manifest_row["train_sample_set_hash"], "train_sample_set_hash") != expected_train_hash:
            raise CalibrationDataError("train sample-set hash mismatch")
        if not fold.train_targets.index.equals(train_features.index):
            raise CalibrationDataError("TRAIN target index mismatch")

        metadata_required = {
            "sample_id", "fold_id", "split_role", "decision_snapshot_hash",
            "hypothesis_id", "hypothesis_type", "target_available",
            "factual_outcome_id", "overlap_count_within_split",
            "dataset_contract_version",
            "final_outcome_known_information_key_version",
            "final_outcome_known_timeline_id", "final_outcome_known_bar_position",
            "final_outcome_known_event_time_utc", "final_outcome_known_information_phase",
            "final_outcome_known_deterministic_sequence",
            "label_interval_end_inclusive_information_key_version",
            "label_interval_end_inclusive_timeline_id",
            "label_interval_end_inclusive_bar_position",
            "label_interval_end_inclusive_event_time_utc",
            "label_interval_end_inclusive_information_phase",
            "label_interval_end_inclusive_deterministic_sequence",
        }
        if not isinstance(fold.sample_metadata, pd.DataFrame) or not metadata_required.issubset(
            fold.sample_metadata.columns
        ):
            raise CalibrationDataError("sample_metadata schema mismatch")
        train_metadata = fold.sample_metadata[
            fold.sample_metadata["split_role"].astype(str) == "TRAIN"
        ].copy(deep=True)
        if train_metadata["sample_id"].duplicated().any() or set(
            train_metadata["sample_id"].astype(str)
        ) != set(train_ids):
            raise CalibrationDataError("TRAIN metadata/sample mismatch")
        train_metadata = train_metadata.set_index(train_metadata["sample_id"].astype(str)).loc[
            train_ids
        ]
        for _, row in train_metadata.iterrows():
            if str(row["fold_id"]) != spec.fold_id or str(
                row["dataset_contract_version"]
            ) != DATASET_CONTRACT_VERSION:
                raise CalibrationDataError("TRAIN fold metadata mismatch")
            if not _strict_bool(row["target_available"], "target_available") or pd.isna(
                row["factual_outcome_id"]
            ):
                raise CalibrationDataError("TRAIN sample lacks mature factual identity")
            _hex64(row["factual_outcome_id"], "factual_outcome_id")
            final_key = _key_from_row(row, "final_outcome_known")
            label_end = _key_from_row(row, "label_interval_end_inclusive")
            if not final_key <= cutoff or not label_end <= cutoff:
                raise CalibrationDataError("TRAIN outcome not legally known by cutoff")
        # Hash/admit only TRAIN-legality fields. In particular, CLOSED
        # cross_split_label_overlap_detected is TEST-cohort-derived and is not
        # allowed to enter TRAIN calibration identity or diagnostics.
        train_metadata_projection = train_metadata.loc[
            :, sorted(metadata_required)
        ].copy(deep=True)

        sample_ids = [sample.sample_id for sample in training.reasoning_samples]
        if len(sample_ids) != len(set(sample_ids)) or set(sample_ids) != set(train_ids):
            raise CalibrationDataError("reasoning sample-set mismatch")
        sample_by_id = {sample.sample_id: sample for sample in training.reasoning_samples}

        family_frames = []
        record_frames = []
        signature_frames = []
        reasoning_identity_rows = []
        for sample_id in train_ids:
            sample = sample_by_id[sample_id]
            frozen = sample.feature_snapshot
            frozen.verify()
            expected_sample_id = _closed_dataset_builder._sample_id(spec.fold_id, frozen)
            if sample_id != expected_sample_id or sample.sample_id != expected_sample_id:
                raise CalibrationDataError("canonical CLOSED sample_id mismatch")
            metadata = train_metadata.loc[sample_id]
            if (
                frozen.decision_snapshot_hash != str(metadata["decision_snapshot_hash"])
                or frozen.hypothesis_id != int(metadata["hypothesis_id"])
                or frozen.hypothesis_type != str(metadata["hypothesis_type"])
            ):
                raise CalibrationDataError("frozen snapshot/6.2A-3 sample identity mismatch")
            expected_raw = frozen.raw_feature_row()
            supplied_raw = train_features.loc[[sample_id]].reset_index(drop=True)
            try:
                pd.testing.assert_frame_equal(supplied_raw, expected_raw, check_exact=True)
            except AssertionError as exc:
                raise CalibrationDataError("authoritative TRAIN raw feature row mismatch") from exc
            expected_reasoning = DynamicEvidenceFamilyReasoner().analyze(
                _reasoning_snapshot_from_frozen(frozen)
            )
            _assert_reasoning_result_equal(sample.reasoning, expected_reasoning)
            result = expected_reasoning
            if not result.reasoning_manifest.equals(reasoning_contract_manifest()):
                raise CalibrationDataError("B-0 reasoning manifest mismatch")
            family = result.family_snapshots.copy(deep=True)
            records = result.evidence_records.copy(deep=True)
            signature = result.availability_signature.copy(deep=True)
            if set(family["family_name"].astype(str)) != {
                member.value for member in EvidenceFamily
            } or len(family) != len(EvidenceFamily):
                raise CalibrationDataError("B-0 family registry mismatch")
            if set(family["family_registry_version"].astype(str)) != {
                REASONING_CONTRACT_VERSION
            }:
                raise CalibrationDataError("B-0 reasoning version mismatch")
            if records["record_id"].duplicated().any():
                raise CalibrationDataError("duplicate B-0 evidence record")
            if records["included_for_independent_calibration"].fillna(False).any():
                raise CalibrationDataError("B-0 statistical independence is not certified")
            family_ids = set(family["family_snapshot_id"].astype(str))
            if not set(records["family_snapshot_id"].astype(str)).issubset(family_ids):
                raise CalibrationDataError("orphan B-0 evidence record")
            for record in records.to_dict(orient="records"):
                expected_hash = canonical_sha256(
                    domain="EVIDENCE_RECORD_FINAL_V1_2",
                    payload=reasoning_record_hash_payload(record),
                )
                if expected_hash != record["record_hash"]:
                    raise CalibrationDataError("B-0 final record hash mismatch")
            first = family.iloc[0]
            decision_key = _decision_key_from_family(first)
            if not decision_key <= cutoff:
                raise CalibrationDataError("reasoning decision after training cutoff")
            metadata = train_metadata.loc[sample_id]
            if (
                str(first["decision_snapshot_hash"])
                != str(metadata["decision_snapshot_hash"])
                or int(first["hypothesis_id"]) != int(metadata["hypothesis_id"])
                or str(first["hypothesis_type"]) != str(metadata["hypothesis_type"])
            ):
                raise CalibrationDataError("reasoning/6.2A-3 sample identity mismatch")
            semantic_hashes = set(family["semantic_reasoning_hash"].astype(str))
            if len(semantic_hashes) != 1:
                raise CalibrationDataError("inconsistent B-0 semantic identity")
            semantic_hash = next(iter(semantic_hashes))
            family.insert(0, "sample_id", sample_id)
            records.insert(0, "sample_id", sample_id)
            records.insert(1, "hypothesis_type", str(first["hypothesis_type"]))
            signature.insert(0, "sample_id", sample_id)
            signature.insert(1, "hypothesis_type", str(first["hypothesis_type"]))
            family_frames.append(family)
            record_frames.append(records)
            signature_frames.append(signature)
            reasoning_identity_rows.append(
                {
                    "sample_id": sample_id,
                    "semantic_reasoning_hash": semantic_hash,
                    "decision_snapshot_hash": str(first["decision_snapshot_hash"]),
                }
            )

        all_family = pd.concat(family_frames, ignore_index=True) if family_frames else pd.DataFrame()
        all_records = pd.concat(record_frames, ignore_index=True) if record_frames else pd.DataFrame()
        all_signatures = pd.concat(signature_frames, ignore_index=True) if signature_frames else pd.DataFrame()
        families = set(all_family["family_name"].astype(str)) if len(all_family) else {
            family.value for family in EvidenceFamily
        }
        _validate_variant_set(variants, families)
        if experiment.variant_id not in {variant.variant_id for variant in variants}:
            raise CalibrationContractError("experiment variant_id missing")

        family_rows = []
        if len(all_family):
            group_cols = [
                "hypothesis_type", "family_name", "aggregate_semantic_state",
                "availability_state", "conflict_present", "source_mode_scope",
            ]
            for keys, group in all_family.groupby(group_cols, dropna=False, sort=True):
                family_rows.append(
                    {
                        **dict(zip(group_cols, keys)),
                        "raw_sample_count": len(group),
                        "distinct_reasoning_identity_count": group[
                            "semantic_reasoning_hash"
                        ].nunique(),
                        "dependence_status": DEPENDENCE_STATUS,
                        "measure_semantics": COVERAGE_SEMANTICS,
                    }
                )
        family_observation_coverage = _typed(pd.DataFrame(family_rows, columns=_FAMILY_COVERAGE_COLUMNS))

        feature_rows = []
        feature_group_cols = [
            "family_name", "source_record_id", "record_kind", "semantic_state",
            "availability_state", "source_mode", "provenance_status", "derivation_status",
        ]
        if len(all_records):
            for keys, group in all_records.groupby(feature_group_cols, dropna=False, sort=True):
                feature_rows.append(
                    {
                        **dict(zip(feature_group_cols, keys)),
                        "raw_observation_count": len(group),
                        "nonmissing_typed_value_count": sum(
                            _record_value_count(row) for _, row in group.iterrows()
                        ),
                        "dependence_status": DEPENDENCE_STATUS,
                        "measure_semantics": COVERAGE_SEMANTICS,
                    }
                )
        feature_observation_coverage = _typed(pd.DataFrame(feature_rows, columns=_FEATURE_COVERAGE_COLUMNS))

        cdf_rows = []
        if len(all_records):
            numeric = all_records[all_records["primary_value_float"].notna()].copy()
            for keys, group in numeric.groupby(
                ["hypothesis_type", "family_name", "source_record_id", "source_mode"],
                dropna=False,
                sort=True,
            ):
                values = sorted(float(value) for value in group["primary_value_float"])
                if any(not math.isfinite(value) for value in values):
                    raise CalibrationDataError("nonfinite numeric TRAIN value")
                total = len(values)
                for value in sorted(set(values)):
                    cumulative = sum(item <= value for item in values)
                    cdf_rows.append(
                        {
                            "hypothesis_type": keys[0], "family_name": keys[1],
                            "source_record_id": keys[2], "source_mode": keys[3],
                            "value_float": value, "value_float_hex": value.hex(),
                            "cumulative_count": cumulative, "total_count": total,
                            "empirical_cdf": cumulative / total,
                            "rank_semantics": "TRAIN_EMPIRICAL_CDF_NOT_PROBABILITY",
                        }
                    )
        numeric_cdf = _typed(pd.DataFrame(cdf_rows, columns=_NUMERIC_CDF_COLUMNS))

        category_rows = []
        if len(all_records):
            for value_column, value_type in (
                ("primary_value_integer", "INTEGER"),
                ("primary_value_boolean", "BOOLEAN"),
                ("primary_value_category", "CATEGORY"),
            ):
                subset = all_records[all_records[value_column].notna()]
                group_base = ["hypothesis_type", "family_name", "source_record_id", "source_mode"]
                for keys, group in subset.groupby(group_base, dropna=False, sort=True):
                    values = [str(value) for value in group[value_column]]
                    total = len(values)
                    for value in sorted(set(values)):
                        count = values.count(value)
                        category_rows.append(
                            {
                                "hypothesis_type": keys[0], "family_name": keys[1],
                                "source_record_id": keys[2], "source_mode": keys[3],
                                "value_type": value_type, "value_text": value,
                                "raw_count": count, "total_count": total,
                                "raw_fraction": count / total,
                            }
                        )
        category_distribution = _typed(
            pd.DataFrame(category_rows, columns=_CATEGORY_COLUMNS)
        )

        availability_rows = []
        if len(all_signatures):
            grouped = all_signatures.groupby(
                ["hypothesis_type", "global_availability_signature_hash"],
                sort=True,
            )
            for keys, group in grouped:
                availability_rows.append(
                    {
                        "hypothesis_type": keys[0],
                        "global_availability_signature_hash": keys[1],
                        "raw_sample_count": group["sample_id"].nunique(),
                        "dependence_status": DEPENDENCE_STATUS,
                        "calibration_status": ObjectiveStatus.NOT_CALIBRATED.value,
                    }
                )
        availability_support = _typed(
            pd.DataFrame(availability_rows, columns=_AVAILABILITY_COLUMNS)
        )

        feature_registry = sorted(
            {
                (str(row["family_name"]), str(row["source_record_id"]))
                for _, row in all_records.iterrows()
            }
        )
        variant_family_rows = []
        variant_rows = []
        for variant in sorted(variants, key=lambda item: item.variant_id):
            spec_payload = {
                "variant_id": variant.variant_id,
                "role": variant.role.value,
                "admitted_families": tuple(sorted(variant.admitted_families)),
                "withheld_families": tuple(sorted(variant.withheld_families)),
            }
            spec_hash = canonical_sha256(
                domain="CALIBRATION_VARIANT_SPEC_V1", payload=spec_payload
            )
            admitted = set(variant.admitted_families)
            withheld = set(variant.withheld_families)
            baseline_semantics = (
                BASELINE_SEMANTICS
                if variant.role is BaselineRole.SIMPLE_ENGINEERED_MARKET_CONTEXT
                else "EXPLICIT_VARIANT_ADMISSION_CONTRACT_NO_SUPERIORITY_CLAIM"
            )
            purity_claim = (
                BASELINE_PURITY_CLAIM
                if variant.role is BaselineRole.SIMPLE_ENGINEERED_MARKET_CONTEXT
                else "NO_BASELINE_SUPERIORITY_OR_PURITY_CLAIM"
            )
            for family_name in sorted(families):
                variant_family_rows.append(
                    {
                        "variant_id": variant.variant_id,
                        "baseline_role": variant.role.value,
                        "baseline_semantics": baseline_semantics,
                        "purity_claim": purity_claim,
                        "family_name": family_name,
                        "admitted": family_name in admitted,
                        "withheld": family_name in withheld,
                        "variant_spec_hash": spec_hash,
                    }
                )
            for family_name, source_record_id in feature_registry:
                variant_rows.append(
                    {
                        "variant_id": variant.variant_id,
                        "baseline_role": variant.role.value,
                        "baseline_semantics": baseline_semantics,
                        "purity_claim": purity_claim,
                        "family_name": family_name,
                        "source_record_id": source_record_id,
                        "admitted": family_name in admitted,
                        "withheld": family_name in withheld,
                        "variant_spec_hash": spec_hash,
                    }
                )
        variant_family_specification = _typed(
            pd.DataFrame(variant_family_rows, columns=_VARIANT_FAMILY_COLUMNS)
        )
        variant_admission = _typed(pd.DataFrame(variant_rows, columns=_VARIANT_COLUMNS))

        overlap_values = [int(value) for value in train_metadata["overlap_count_within_split"]]
        diagnostics = _typed(
            pd.DataFrame(
                [
                    {
                        "diagnostic_name": "QUALIFICATION_OBJECTIVE",
                        "status": ObjectiveStatus.OBJECTIVE_UNDEFINED.value,
                        "raw_value_integer": pd.NA,
                        "detail": "RESEARCH_DEBT_020_LIFECYCLE_TERMINATION_ESTIMAND_UNRESOLVED",
                    },
                    {
                        "diagnostic_name": "OVERLAPPING_HYPOTHESES",
                        "status": DEPENDENCE_STATUS,
                        "raw_value_integer": sum(value > 0 for value in overlap_values),
                        "detail": "RAW_OVERLAP_METADATA_PRESERVED_NO_IID_CLAIM",
                    },
                    {
                        "diagnostic_name": "CROSS_SPLIT_LABEL_OVERLAP",
                        "status": "NOT_ACCESSED_OOS_FIREWALL",
                        "raw_value_integer": pd.NA,
                        "detail": "TEST_DERIVED_METADATA_EXCLUDED_FROM_TRAIN_ARTIFACT",
                    },
                    {
                        "diagnostic_name": "STABILITY_UNCERTAINTY",
                        "status": ObjectiveStatus.NOT_CALIBRATED.value,
                        "raw_value_integer": pd.NA,
                        "detail": "NO_OBJECTIVE_NO_PREDICTIVE_STABILITY_CLAIM",
                    },
                ],
                columns=_DIAGNOSTIC_COLUMNS,
            )
        )

        train_schema_hash = canonical_sha256(
            domain="CALIBRATION_TRAIN_RAW_SCHEMA_V1_1",
            payload={
                "columns": list(train_features.columns),
                "dtypes": [str(dtype) for dtype in train_features.dtypes],
            },
        )
        train_features_hash = canonical_sha256(
            domain="CALIBRATION_TRAIN_FEATURES_V1_1", payload=train_features
        )
        train_metadata_hash = canonical_sha256(
            domain="CALIBRATION_TRAIN_METADATA_V1_1",
            payload=train_metadata_projection.reset_index(drop=True),
        )
        reasoning_projection = pd.DataFrame(
            reasoning_identity_rows,
            columns=("sample_id", "semantic_reasoning_hash", "decision_snapshot_hash"),
        )
        reasoning_identity_hash = canonical_sha256(
            domain="CALIBRATION_REASONING_IDENTITIES_V1_1", payload=reasoning_projection
        )
        cutoff_identity = canonical_sha256(
            domain="CALIBRATION_TRAINING_CUTOFF_V1_1", payload=cutoff
        )
        projection_payload = {
            "fold_id": spec.fold_id,
            "training_cutoff_identity": cutoff_identity,
            "train_sample_set_hash": expected_train_hash,
            "train_schema_hash": train_schema_hash,
            "train_features_hash": train_features_hash,
            "train_metadata_hash": train_metadata_hash,
            "reasoning_identity_hash": reasoning_identity_hash,
        }
        training_projection_hash = canonical_sha256(
            domain="CALIBRATION_TRAINING_PROJECTION_V1_1", payload=projection_payload
        )
        training_projection_manifest = _typed(
            pd.DataFrame([{**projection_payload, "training_projection_hash": training_projection_hash}])
        )
        variant_plan_payload = [
            {
                "variant_id": variant.variant_id,
                "role": variant.role.value,
                "admitted_families": tuple(sorted(variant.admitted_families)),
                "withheld_families": tuple(sorted(variant.withheld_families)),
            }
            for variant in sorted(variants, key=lambda item: item.variant_id)
        ]
        variant_plan_hash = canonical_sha256(
            domain="CALIBRATION_VARIANT_PLAN_V1_1", payload=variant_plan_payload
        )
        selected_variant = next(
            variant for variant in variants if variant.variant_id == experiment.variant_id
        )
        selected_variant_spec_hash = canonical_sha256(
            domain="CALIBRATION_SELECTED_VARIANT_V1_1",
            payload={
                "variant_id": selected_variant.variant_id,
                "role": selected_variant.role.value,
                "admitted_families": tuple(sorted(selected_variant.admitted_families)),
                "withheld_families": tuple(sorted(selected_variant.withheld_families)),
            },
        )
        feature_family_spec_hash = canonical_sha256(
            domain="CALIBRATION_FEATURE_FAMILY_SPEC_V1_1",
            payload={
                "feature_observation_coverage_schema": list(feature_observation_coverage.columns),
                "feature_registry": feature_registry,
                "variant_plan_hash": variant_plan_hash,
                "variants": variant_admission,
            },
        )
        hypothesis_scope_hash = canonical_sha256(
            domain="CALIBRATION_HYPOTHESIS_SCOPE_V1_1",
            payload=([] if len(all_family) == 0 else sorted(set(all_family["hypothesis_type"].astype(str)))),
        )
        source_mode_scope_hash = canonical_sha256(
            domain="CALIBRATION_SOURCE_MODE_SCOPE_V1_1",
            payload=([] if len(all_records) == 0 else sorted(set(all_records["source_mode"].astype(str)))),
        )
        calibration_manifest_frame = calibration_contract_manifest()
        component_hashes = {
            "family_observation_coverage_hash": canonical_sha256(
                domain="CALIBRATION_FAMILY_OBSERVATION_COVERAGE_V1_1", payload=family_observation_coverage
            ),
            "feature_observation_coverage_hash": canonical_sha256(
                domain="CALIBRATION_FEATURE_OBSERVATION_COVERAGE_V1_1", payload=feature_observation_coverage
            ),
            "numeric_empirical_cdf_hash": canonical_sha256(
                domain="CALIBRATION_NUMERIC_EMPIRICAL_CDF_V1_1", payload=numeric_cdf
            ),
            "categorical_distribution_hash": canonical_sha256(
                domain="CALIBRATION_CATEGORICAL_DISTRIBUTION_V1_1", payload=category_distribution
            ),
            "availability_support_hash": canonical_sha256(
                domain="CALIBRATION_AVAILABILITY_SUPPORT_V1_1", payload=availability_support
            ),
            "variant_family_specification_hash": canonical_sha256(
                domain="CALIBRATION_VARIANT_FAMILY_SPECIFICATION_V1_1",
                payload=variant_family_specification,
            ),
            "variant_feature_admission_hash": canonical_sha256(
                domain="CALIBRATION_VARIANT_ADMISSION_V1_1", payload=variant_admission
            ),
            "stability_diagnostics_hash": canonical_sha256(
                domain="CALIBRATION_DIAGNOSTICS_V1_1", payload=diagnostics
            ),
            "calibration_manifest_hash": canonical_sha256(
                domain="CALIBRATION_STATIC_MANIFEST_V1_1", payload=calibration_manifest_frame
            ),
        }
        experiment_spec_payload = {
            "experiment_id": experiment.experiment_id,
            "variant_id": experiment.variant_id,
            "evaluation_role": experiment.evaluation_role,
            "objective_id": experiment.objective_id,
            "objective_version": experiment.objective_version,
            "preprocessing_id": experiment.preprocessing_id,
            "model_spec_id": experiment.model_spec_id,
            "allowed_interactions": experiment.allowed_interactions,
            "hyperparameters_json": experiment.hyperparameters_json,
            "random_seed": experiment.random_seed,
            "caller_reported_prior_oos_access_count": experiment.caller_reported_prior_oos_access_count,
            "oos_access_semantics": OOS_ACCESS_SEMANTICS,
        }
        experiment_spec_hash = canonical_sha256(
            domain="CALIBRATION_EXPERIMENT_SPEC_V1_1", payload=experiment_spec_payload
        )
        calibration_content_hash = canonical_sha256(
            domain="CONFLUENCE_CALIBRATION_TRAIN_CONTENT_V1_1",
            payload={
                "training_projection_hash": training_projection_hash,
                "feature_family_spec_hash": feature_family_spec_hash,
                "selected_variant_spec_hash": selected_variant_spec_hash,
                "hypothesis_scope_hash": hypothesis_scope_hash,
                "source_mode_scope_hash": source_mode_scope_hash,
                "component_hashes": component_hashes,
                "experiment_spec_hash": experiment_spec_hash,
            },
        )
        prehash_manifest = {
            "artifact_type": ARTIFACT_TYPE,
            "artifact_contract_version": CALIBRATION_CONTRACT_VERSION,
            "calibration_content_hash": calibration_content_hash,
            "source_dataset_fold_hash": str(manifest_row["dataset_fold_hash"]),
            "source_fold_spec_hash": expected_fold_spec_hash,
            "source_raw_feature_schema_hash": str(manifest_row["raw_feature_schema_hash"]),
            "source_target_schema_hash": str(manifest_row["target_schema_hash"]),
            "train_sample_set_hash": expected_train_hash,
            "training_projection_hash": training_projection_hash,
            "eligibility_manifest_hash": eligibility_hash,
            "dataset_contract_version": DATASET_CONTRACT_VERSION,
            "reasoning_contract_version": REASONING_CONTRACT_VERSION,
            "objective_id": OBJECTIVE_ID,
            "objective_version": OBJECTIVE_VERSION,
            "objective_status": ObjectiveStatus.OBJECTIVE_UNDEFINED.value,
            "qualification_artifact_status": "NOT_BUILT_OBJECTIVE_UNDEFINED",
            "preprocessing_id": PREPROCESSING_ID,
            "model_spec_id": MODEL_SPEC_ID,
            "allowed_interactions": INTERACTION_CONTRACT,
            "source_mode_policy": "ACTUAL_PROXY_SEPARATE_NO_PREDICTIVE_PRIORITY",
            "missingness_policy": "UNKNOWN_UNAVAILABLE_EXPLICIT_NO_RENORMALIZATION",
            "dependence_status": DEPENDENCE_STATUS,
            "coverage_semantics": COVERAGE_SEMANTICS,
            "learned_mapping_status": "DESCRIPTIVE_EMPIRICAL_COVERAGE_ONLY",
            "selected_variant_id": selected_variant.variant_id,
            "selected_variant_role": selected_variant.role.value,
            "selected_variant_spec_hash": selected_variant_spec_hash,
            "variant_plan_hash": variant_plan_hash,
            "feature_family_spec_hash": feature_family_spec_hash,
            "hypothesis_scope_hash": hypothesis_scope_hash,
            "source_mode_scope_hash": source_mode_scope_hash,
            "experiment_id": experiment.experiment_id,
            "experiment_spec_hash": experiment_spec_hash,
            "trusted_prior_ledger_head": trusted_prior_ledger_head,
            **component_hashes,
            "trained_through_information_key_version": cutoff.information_key_version,
            "trained_through_timeline_id": cutoff.timeline_id,
            "trained_through_bar_position": cutoff.bar_position,
            "trained_through_event_time_utc": pd.NaT if cutoff.event_time_utc is None else cutoff.event_time_utc,
            "trained_through_information_phase": cutoff.information_phase.value,
            "trained_through_deterministic_sequence": cutoff.deterministic_sequence,
            "fold_id": spec.fold_id,
        }
        artifact_id = canonical_sha256(
            domain="CONFLUENCE_CALIBRATION_ARTIFACT_ID_V1_1",
            payload={
                "contract": CALIBRATION_CONTRACT_VERSION,
                "training_projection_hash": training_projection_hash,
                "experiment_spec_hash": experiment_spec_hash,
                "selected_variant_spec_hash": selected_variant_spec_hash,
                "source_dataset_fold_hash": str(manifest_row["dataset_fold_hash"]),
            },
        )
        prehash_manifest["artifact_id"] = artifact_id
        artifact_hash = canonical_sha256(
            domain="CONFLUENCE_CALIBRATION_ARTIFACT_FINAL_V1_1",
            payload=prehash_manifest,
        )
        artifact_manifest = _typed(
            pd.DataFrame([{**prehash_manifest, "artifact_hash": artifact_hash}])
        )

        entry = {
            "ledger_contract_version": LEDGER_CONTRACT_VERSION,
            "ledger_sequence": 0 if existing_experiment_ledger is None else len(existing_experiment_ledger),
            "previous_entry_hash": trusted_prior_ledger_head,
            "experiment_id": experiment.experiment_id,
            "training_cutoff_identity": canonical_sha256(
                domain="CALIBRATION_TRAINING_CUTOFF_V1", payload=cutoff
            ),
            "fold_id": spec.fold_id,
            "fold_spec_hash": expected_fold_spec_hash,
            "train_sample_set_hash": expected_train_hash,
            "training_projection_hash": training_projection_hash,
            "objective_id": experiment.objective_id,
            "objective_version": experiment.objective_version,
            "feature_family_spec_hash": feature_family_spec_hash,
            "allowed_interactions": experiment.allowed_interactions,
            "preprocessing_id": experiment.preprocessing_id,
            "model_spec_id": experiment.model_spec_id,
            "hyperparameters_json": experiment.hyperparameters_json,
            "random_seed": experiment.random_seed,
            "variant_id": experiment.variant_id,
            "evaluation_role": experiment.evaluation_role,
            "caller_reported_prior_oos_access_count": experiment.caller_reported_prior_oos_access_count,
            "oos_access_semantics": OOS_ACCESS_SEMANTICS,
            "attempt_status": ExperimentAttemptStatus.ARTIFACT_BUILT.value,
            "failure_reason": pd.NA,
            "artifact_hash": artifact_hash,
            "ledger_entry_hash": pd.NA,
        }
        entry["ledger_entry_hash"] = canonical_sha256(
            domain="CALIBRATION_EXPERIMENT_LEDGER_ENTRY_V1_1",
            payload={key: value for key, value in entry.items() if key != "ledger_entry_hash"},
        )
        entry_frame = _typed(pd.DataFrame([entry], columns=_EXPERIMENT_COLUMNS))
        append_experiment_ledger(
            existing_experiment_ledger,
            entry_frame,
            trusted_expected_prior_head=trusted_prior_ledger_head,
        )

        artifact = ConfluenceCalibrationArtifact(
            artifact_manifest=artifact_manifest,
            training_projection_manifest=training_projection_manifest,
            family_observation_coverage=family_observation_coverage,
            feature_observation_coverage=feature_observation_coverage,
            numeric_empirical_cdf=numeric_cdf,
            categorical_distribution=category_distribution,
            availability_support=availability_support,
            variant_family_specification=variant_family_specification,
            variant_feature_admission=variant_admission,
            stability_diagnostics=diagnostics,
            experiment_ledger_entry=entry_frame,
            calibration_manifest=calibration_manifest_frame,
        )
        verify_confluence_calibration_artifact(artifact)
        return artifact


def verify_confluence_calibration_artifact(
    artifact: ConfluenceCalibrationArtifact,
) -> bool:
    """Recompute every frozen component and final V1.1 artifact identity."""
    if not isinstance(artifact, ConfluenceCalibrationArtifact):
        raise CalibrationContractError("ConfluenceCalibrationArtifact required")
    if len(artifact.artifact_manifest) != 1 or len(artifact.training_projection_manifest) != 1:
        raise CalibrationContractError("singular artifact/projection manifest required")
    if not artifact.calibration_manifest.equals(calibration_contract_manifest()):
        raise CalibrationContractError("calibration static manifest mismatch")
    for frame in (
        artifact.family_observation_coverage,
        artifact.feature_observation_coverage,
    ):
        if len(frame) and set(frame["measure_semantics"].astype(str)) != {COVERAGE_SEMANTICS}:
            raise CalibrationContractError("observation coverage semantics mismatch")
    projection = artifact.training_projection_manifest.iloc[0]
    projection_payload = {
        key: projection[key]
        for key in artifact.training_projection_manifest.columns
        if key != "training_projection_hash"
    }
    expected_projection_hash = canonical_sha256(
        domain="CALIBRATION_TRAINING_PROJECTION_V1_1", payload=projection_payload
    )
    if expected_projection_hash != projection["training_projection_hash"]:
        raise CalibrationContractError("training projection manifest hash mismatch")
    component_specs = (
        ("family_observation_coverage_hash", "CALIBRATION_FAMILY_OBSERVATION_COVERAGE_V1_1", artifact.family_observation_coverage),
        ("feature_observation_coverage_hash", "CALIBRATION_FEATURE_OBSERVATION_COVERAGE_V1_1", artifact.feature_observation_coverage),
        ("numeric_empirical_cdf_hash", "CALIBRATION_NUMERIC_EMPIRICAL_CDF_V1_1", artifact.numeric_empirical_cdf),
        ("categorical_distribution_hash", "CALIBRATION_CATEGORICAL_DISTRIBUTION_V1_1", artifact.categorical_distribution),
        ("availability_support_hash", "CALIBRATION_AVAILABILITY_SUPPORT_V1_1", artifact.availability_support),
        ("variant_family_specification_hash", "CALIBRATION_VARIANT_FAMILY_SPECIFICATION_V1_1", artifact.variant_family_specification),
        ("variant_feature_admission_hash", "CALIBRATION_VARIANT_ADMISSION_V1_1", artifact.variant_feature_admission),
        ("stability_diagnostics_hash", "CALIBRATION_DIAGNOSTICS_V1_1", artifact.stability_diagnostics),
        ("calibration_manifest_hash", "CALIBRATION_STATIC_MANIFEST_V1_1", artifact.calibration_manifest),
    )
    manifest = artifact.artifact_manifest.iloc[0]
    for field, domain, frame in component_specs:
        expected = canonical_sha256(domain=domain, payload=frame)
        if expected != manifest[field]:
            raise CalibrationContractError(f"artifact component hash mismatch: {field}")
    if str(manifest["training_projection_hash"]) != str(projection["training_projection_hash"]):
        raise CalibrationContractError("artifact/projection identity mismatch")
    selected_id = str(manifest["selected_variant_id"])
    selected_rows = artifact.variant_family_specification[
        artifact.variant_family_specification["variant_id"] == selected_id
    ]
    if len(selected_rows) == 0 or selected_rows["baseline_role"].nunique() != 1:
        raise CalibrationContractError("selected variant specification missing")
    role = str(selected_rows.iloc[0]["baseline_role"])
    admitted = tuple(sorted(selected_rows.loc[selected_rows["admitted"], "family_name"].astype(str)))
    withheld = tuple(sorted(selected_rows.loc[selected_rows["withheld"], "family_name"].astype(str)))
    selected_hash = canonical_sha256(
        domain="CALIBRATION_SELECTED_VARIANT_V1_1",
        payload={
            "variant_id": selected_id,
            "role": role,
            "admitted_families": admitted,
            "withheld_families": withheld,
        },
    )
    if selected_hash != manifest["selected_variant_spec_hash"]:
        raise CalibrationContractError("selected variant identity mismatch")
    ledger = artifact.experiment_ledger_entry
    if len(ledger) != 1 or tuple(ledger.columns) != _EXPERIMENT_COLUMNS:
        raise CalibrationContractError("artifact experiment ledger entry mismatch")
    entry = ledger.iloc[0]
    expected_entry_hash = canonical_sha256(
        domain="CALIBRATION_EXPERIMENT_LEDGER_ENTRY_V1_1",
        payload={key: entry[key] for key in _EXPERIMENT_COLUMNS if key != "ledger_entry_hash"},
    )
    if expected_entry_hash != entry["ledger_entry_hash"]:
        raise CalibrationContractError("artifact ledger entry hash mismatch")
    if (
        str(entry["artifact_hash"]) != str(manifest["artifact_hash"])
        or str(entry["previous_entry_hash"]) != str(manifest["trusted_prior_ledger_head"])
        or str(entry["oos_access_semantics"]) != OOS_ACCESS_SEMANTICS
    ):
        raise CalibrationContractError("artifact ledger provenance mismatch")
    experiment_spec_hash = canonical_sha256(
        domain="CALIBRATION_EXPERIMENT_SPEC_V1_1",
        payload={
            "experiment_id": entry["experiment_id"],
            "variant_id": entry["variant_id"],
            "evaluation_role": entry["evaluation_role"],
            "objective_id": entry["objective_id"],
            "objective_version": entry["objective_version"],
            "preprocessing_id": entry["preprocessing_id"],
            "model_spec_id": entry["model_spec_id"],
            "allowed_interactions": entry["allowed_interactions"],
            "hyperparameters_json": entry["hyperparameters_json"],
            "random_seed": entry["random_seed"],
            "caller_reported_prior_oos_access_count": entry["caller_reported_prior_oos_access_count"],
            "oos_access_semantics": entry["oos_access_semantics"],
        },
    )
    if experiment_spec_hash != manifest["experiment_spec_hash"]:
        raise CalibrationContractError("experiment specification hash mismatch")
    content_hash = canonical_sha256(
        domain="CONFLUENCE_CALIBRATION_TRAIN_CONTENT_V1_1",
        payload={
            "training_projection_hash": manifest["training_projection_hash"],
            "feature_family_spec_hash": manifest["feature_family_spec_hash"],
            "selected_variant_spec_hash": manifest["selected_variant_spec_hash"],
            "hypothesis_scope_hash": manifest["hypothesis_scope_hash"],
            "source_mode_scope_hash": manifest["source_mode_scope_hash"],
            "component_hashes": {field: manifest[field] for field, _, _ in component_specs},
            "experiment_spec_hash": manifest["experiment_spec_hash"],
        },
    )
    if content_hash != manifest["calibration_content_hash"]:
        raise CalibrationContractError("calibration content hash mismatch")
    prehash = {
        key: manifest[key]
        for key in artifact.artifact_manifest.columns
        if key != "artifact_hash"
    }
    artifact_id = canonical_sha256(
        domain="CONFLUENCE_CALIBRATION_ARTIFACT_ID_V1_1",
        payload={
            "contract": manifest["artifact_contract_version"],
            "training_projection_hash": manifest["training_projection_hash"],
            "experiment_spec_hash": manifest["experiment_spec_hash"],
            "selected_variant_spec_hash": manifest["selected_variant_spec_hash"],
            "source_dataset_fold_hash": manifest["source_dataset_fold_hash"],
        },
    )
    if artifact_id != manifest["artifact_id"]:
        raise CalibrationContractError("artifact_id mismatch")
    expected_artifact_hash = canonical_sha256(
        domain="CONFLUENCE_CALIBRATION_ARTIFACT_FINAL_V1_1", payload=prehash
    )
    if expected_artifact_hash != manifest["artifact_hash"]:
        raise CalibrationContractError("final artifact hash mismatch")
    return True


def make_experiment_ledger_entry(
    experiment: CalibrationExperimentSpec,
    *,
    ledger_sequence: int,
    training_cutoff: InformationKey,
    fold_id: str,
    fold_spec_hash: str,
    train_sample_set_hash: str,
    training_projection_hash: str,
    feature_family_spec_hash: str,
    previous_entry_hash: str,
    attempt_status: ExperimentAttemptStatus,
    artifact_hash: str | None = None,
    failure_reason: str | None = None,
) -> pd.DataFrame:
    """Create an appendable planned/failed/successful experiment-attempt row."""
    if not isinstance(experiment, CalibrationExperimentSpec):
        raise CalibrationContractError("CalibrationExperimentSpec required")
    if isinstance(ledger_sequence, bool) or not isinstance(ledger_sequence, int) or ledger_sequence < 0:
        raise CalibrationContractError("invalid ledger_sequence")
    if not isinstance(training_cutoff, InformationKey):
        raise CalibrationContractError("training_cutoff InformationKey required")
    if not isinstance(attempt_status, ExperimentAttemptStatus):
        raise CalibrationContractError("explicit ExperimentAttemptStatus required")
    _hex64(previous_entry_hash, "previous_entry_hash")
    for value, field in (
        (fold_spec_hash, "fold_spec_hash"),
        (train_sample_set_hash, "train_sample_set_hash"),
        (training_projection_hash, "training_projection_hash"),
        (feature_family_spec_hash, "feature_family_spec_hash"),
    ):
        _hex64(value, field)
    if attempt_status is ExperimentAttemptStatus.ARTIFACT_BUILT:
        if artifact_hash is None:
            raise CalibrationContractError("built attempt requires artifact_hash")
        _hex64(artifact_hash, "artifact_hash")
        if failure_reason is not None:
            raise CalibrationContractError("built attempt cannot carry failure_reason")
    elif attempt_status is ExperimentAttemptStatus.FAILED:
        if not isinstance(failure_reason, str) or not failure_reason:
            raise CalibrationContractError("failed attempt requires failure_reason")
        if artifact_hash is not None:
            raise CalibrationContractError("failed attempt cannot carry artifact_hash")
    elif artifact_hash is not None or failure_reason is not None:
        raise CalibrationContractError("specified attempt has no result fields")
    entry = {
        "ledger_contract_version": LEDGER_CONTRACT_VERSION,
        "ledger_sequence": ledger_sequence,
        "previous_entry_hash": previous_entry_hash,
        "experiment_id": experiment.experiment_id,
        "training_cutoff_identity": canonical_sha256(
            domain="CALIBRATION_TRAINING_CUTOFF_V1", payload=training_cutoff
        ),
        "fold_id": fold_id,
        "fold_spec_hash": fold_spec_hash,
        "train_sample_set_hash": train_sample_set_hash,
        "training_projection_hash": training_projection_hash,
        "objective_id": experiment.objective_id,
        "objective_version": experiment.objective_version,
        "feature_family_spec_hash": feature_family_spec_hash,
        "allowed_interactions": experiment.allowed_interactions,
        "preprocessing_id": experiment.preprocessing_id,
        "model_spec_id": experiment.model_spec_id,
        "hyperparameters_json": experiment.hyperparameters_json,
        "random_seed": experiment.random_seed,
        "variant_id": experiment.variant_id,
        "evaluation_role": experiment.evaluation_role,
        "caller_reported_prior_oos_access_count": experiment.caller_reported_prior_oos_access_count,
        "oos_access_semantics": OOS_ACCESS_SEMANTICS,
        "attempt_status": attempt_status.value,
        "failure_reason": failure_reason,
        "artifact_hash": artifact_hash,
        "ledger_entry_hash": pd.NA,
    }
    entry["ledger_entry_hash"] = canonical_sha256(
        domain="CALIBRATION_EXPERIMENT_LEDGER_ENTRY_V1_1",
        payload={key: value for key, value in entry.items() if key != "ledger_entry_hash"},
    )
    return _typed(pd.DataFrame([entry], columns=_EXPERIMENT_COLUMNS))


def append_experiment_ledger(
    existing: pd.DataFrame | None,
    entry: pd.DataFrame,
    *,
    trusted_expected_prior_head: str,
) -> pd.DataFrame:
    """Append against an externally trusted prior head and verify full chain."""
    _hex64(trusted_expected_prior_head, "trusted_expected_prior_head")
    if not isinstance(entry, pd.DataFrame) or tuple(entry.columns) != _EXPERIMENT_COLUMNS or len(entry) != 1:
        raise CalibrationContractError("exact experiment ledger entry required")
    prior = pd.DataFrame(columns=_EXPERIMENT_COLUMNS) if existing is None else existing.copy(deep=True)
    if tuple(prior.columns) != _EXPERIMENT_COLUMNS:
        raise CalibrationContractError("experiment ledger schema mismatch")
    expected_previous = experiment_ledger_genesis_hash()
    for position, row in prior.reset_index(drop=True).iterrows():
        if str(row["ledger_contract_version"]) != LEDGER_CONTRACT_VERSION:
            raise CalibrationContractError("experiment ledger version mismatch")
        if int(row["ledger_sequence"]) != position:
            raise CalibrationContractError("experiment ledger sequence mismatch")
        if str(row["previous_entry_hash"]) != expected_previous:
            raise CalibrationContractError("experiment ledger chain mismatch")
        if str(row["oos_access_semantics"]) != OOS_ACCESS_SEMANTICS:
            raise CalibrationContractError("OOS accounting semantics mismatch")
        expected = canonical_sha256(
            domain="CALIBRATION_EXPERIMENT_LEDGER_ENTRY_V1_1",
            payload={key: row[key] for key in _EXPERIMENT_COLUMNS if key != "ledger_entry_hash"},
        )
        if expected != row["ledger_entry_hash"]:
            raise CalibrationContractError("experiment ledger history mutated")
        expected_previous = str(row["ledger_entry_hash"])
    if expected_previous != trusted_expected_prior_head:
        raise CalibrationContractError("trusted prior ledger head mismatch")
    new = entry.iloc[0]
    if str(new["ledger_contract_version"]) != LEDGER_CONTRACT_VERSION:
        raise CalibrationContractError("new experiment ledger version mismatch")
    if int(new["ledger_sequence"]) != len(prior):
        raise CalibrationContractError("new experiment ledger sequence mismatch")
    if str(new["previous_entry_hash"]) != trusted_expected_prior_head:
        raise CalibrationContractError("new entry previous head mismatch")
    if str(new["oos_access_semantics"]) != OOS_ACCESS_SEMANTICS:
        raise CalibrationContractError("new OOS accounting semantics mismatch")
    if str(new["experiment_id"]) in set(prior["experiment_id"].astype(str)):
        raise CalibrationContractError("duplicate experiment_id")
    expected_new = canonical_sha256(
        domain="CALIBRATION_EXPERIMENT_LEDGER_ENTRY_V1_1",
        payload={key: new[key] for key in _EXPERIMENT_COLUMNS if key != "ledger_entry_hash"},
    )
    if expected_new != new["ledger_entry_hash"]:
        raise CalibrationContractError("new experiment ledger hash mismatch")
    if len(prior) == 0:
        return _typed(entry.reset_index(drop=True))
    return _typed(pd.concat([prior, entry], ignore_index=True))


def calibration_contract_manifest() -> pd.DataFrame:
    rows = [
        ("CONTRACT", "VERSION", CALIBRATION_CONTRACT_VERSION),
        ("OBJECTIVE", "QUALIFICATION", "OBJECTIVE_UNDEFINED_RESEARCH_DEBT_020"),
        ("ARTIFACT", "CONFLUENCE", "DESCRIPTIVE_EMPIRICAL_COVERAGE_ONLY"),
        ("COVERAGE", "SEMANTICS", COVERAGE_SEMANTICS),
        ("ARTIFACT", "QUALIFICATION", "NOT_BUILT_OBJECTIVE_UNDEFINED"),
        ("TRAINING", "CUTOFF", "CLOSED_6.2A-2_AND_6.2A-3_TRAIN_ONLY"),
        ("TRAINING", "TEST_ACCESS", "FORBIDDEN"),
        ("PREPROCESSING", "STATUS", PREPROCESSING_ID),
        ("MODEL", "STATUS", MODEL_SPEC_ID),
        ("INTERACTIONS", "STATUS", INTERACTION_CONTRACT),
        ("RANK", "SEMANTICS", "TRAIN_EMPIRICAL_CDF_NOT_PROBABILITY"),
        ("MISSINGNESS", "UNKNOWN", "PRESERVED"),
        ("MISSINGNESS", "UNAVAILABLE", "PRESERVED"),
        ("SOURCE_MODE", "ACTUAL_PROXY", "SEPARATE_NO_PREDICTIVE_PRIORITY"),
        ("DEPENDENCE", "OVERLAP", DEPENDENCE_STATUS),
        ("INDEPENDENCE", "CLAIM", "NOT_CERTIFIED"),
        ("BASELINE", "NULL", "MANDATORY_EXPLICIT_VARIANT"),
        ("BASELINE", "SIMPLE_ENGINEERED", BASELINE_SEMANTICS),
        ("BASELINE", "PURITY_CLAIM", BASELINE_PURITY_CLAIM),
        ("BASELINE", "FULL", "MANDATORY_EXACT_TRAIN_SCHEMA"),
        ("ABLATION", "POLICY", "EXPLICIT_FULL_MINUS_WITHHELD_NO_SUBSET_SEARCH"),
        ("EXPERIMENT", "LEDGER", "CHAINED_ENTRIES_REQUIRE_EXTERNAL_TRUSTED_HEAD"),
        ("EXPERIMENT", "OOS_ACCESS", OOS_ACCESS_SEMANTICS),
        ("EXECUTION", "STATUS", "NOT_IMPLEMENTED"),
    ]
    return pd.DataFrame(
        [
            {
                "record_type": record_type,
                "name": name,
                "value": value,
                "serialization_order": order,
            }
            for order, (record_type, name, value) in enumerate(rows)
        ]
    )

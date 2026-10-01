"""Module 6.2A-3 V1.1: raw causal fold construction only; no preprocessing/model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from trading_system.research.dataset_contracts import (
    DATASET_CONTRACT_VERSION,
    DatasetContractError,
    DatasetDataError,
    FrozenDecisionFeatureSnapshot,
    TimelineAdapter,
    WalkForwardFoldSpec,
)
from trading_system.research.eligibility import (
    ELIGIBILITY_CONTRACT_VERSION,
    FactualOutcomeBatch,
    TemporalEligibilityGate,
    TemporalEligibilityResult,
    eligibility_manifest,
)
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import InformationKey, InformationPhase


_TARGET_COLUMNS = (
    "target_terminal_state",
    "target_pre_endpoint_favorable_excursion_fraction",
    "target_pre_endpoint_adverse_excursion_fraction",
    "target_pre_endpoint_same_bar_order_ambiguous",
    "target_endpoint_bar_favorable_excursion_fraction",
    "target_endpoint_bar_adverse_excursion_fraction",
    "target_endpoint_bar_same_bar_order_ambiguous",
)

def _metadata_key_columns(prefix: str) -> tuple[str, ...]:
    return (
        f"{prefix}_information_key_version",
        f"{prefix}_timeline_id",
        f"{prefix}_bar_position",
        f"{prefix}_event_time_utc",
        f"{prefix}_information_phase",
        f"{prefix}_deterministic_sequence",
    )


_METADATA_COLUMNS = (
    "sample_id",
    "fold_id",
    "split_role",
    "timeline_id",
    "decision_snapshot_hash",
    "hypothesis_id",
    "hypothesis_type",
    "snapshot_type",
    "factual_outcome_id",
    "selected_research_snapshot_id",
    *_metadata_key_columns("snapshot"),
    *_metadata_key_columns("final_outcome_known"),
    *_metadata_key_columns("label_interval_start_exclusive"),
    *_metadata_key_columns("label_interval_end_inclusive"),
    "target_available",
    "target_availability_reason",
    "overlap_count_within_split",
    "cross_split_label_overlap_detected",
    "dataset_contract_version",
)

_AUDIT_COLUMNS = (
    "input_candidate_ordinal",
    "sample_id",
    "fold_id",
    "decision_snapshot_hash",
    "hypothesis_id",
    "hypothesis_type",
    "snapshot_type",
    "requested_split_role",
    "feature_join_status",
    "feature_join_reason",
    "outcome_join_status",
    "outcome_join_reason",
    "train_eligibility_status",
    "test_target_availability_status",
    "purged",
    "purge_reason",
    "included_in_train_features",
    "included_in_train_targets",
    "included_in_test_features",
    "included_in_test_targets",
    "decision_snapshot_attestation_valid",
    "manifest_identity_valid",
    "factual_identity_valid",
    "dataset_contract_version",
)


@dataclass(frozen=True)
class ResearchDatasetFold:
    train_features_raw: pd.DataFrame
    train_targets: pd.DataFrame
    test_features_raw: pd.DataFrame
    test_targets: pd.DataFrame
    sample_metadata: pd.DataFrame
    fold_manifest: pd.DataFrame


@dataclass(frozen=True)
class ResearchDatasetBuildResult:
    fold: ResearchDatasetFold
    dataset_build_audit: pd.DataFrame


def _result_equal(left: TemporalEligibilityResult, right: TemporalEligibilityResult):
    try:
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
    except AssertionError as exc:
        raise DatasetContractError("eligibility result reseal mismatch") from exc


def _metadata_key_fields(prefix: str, key: InformationKey | None) -> dict:
    if key is None:
        return {
            f"{prefix}_information_key_version": pd.NA,
            f"{prefix}_timeline_id": pd.NA,
            f"{prefix}_bar_position": pd.NA,
            f"{prefix}_event_time_utc": pd.NaT,
            f"{prefix}_information_phase": pd.NA,
            f"{prefix}_deterministic_sequence": pd.NA,
        }
    return {
        f"{prefix}_information_key_version": key.information_key_version,
        f"{prefix}_timeline_id": key.timeline_id,
        f"{prefix}_bar_position": key.bar_position,
        f"{prefix}_event_time_utc": (
            pd.NaT if key.event_time_utc is None else key.event_time_utc
        ),
        f"{prefix}_information_phase": key.information_phase.value,
        f"{prefix}_deterministic_sequence": key.deterministic_sequence,
    }


def _sample_id(fold_id: str, snapshot: FrozenDecisionFeatureSnapshot) -> str:
    return canonical_sha256(
        domain="RESEARCH_DATASET_SAMPLE_ID_V1",
        payload={
            "dataset_contract_version": DATASET_CONTRACT_VERSION,
            "fold_id": fold_id,
            "decision_snapshot_hash": snapshot.decision_snapshot_hash,
            "hypothesis_id": snapshot.hypothesis_id,
            "snapshot_type": snapshot.snapshot_type,
        },
    )


def _selected_key(row: pd.Series, prefix: str) -> InformationKey:
    timestamp = row[f"{prefix}_event_time_utc"]
    event_time = None if pd.isna(timestamp) else timestamp
    return InformationKey(
        information_key_version=str(row[f"{prefix}_information_key_version"]),
        timeline_id=str(row[f"{prefix}_timeline_id"]),
        bar_position=int(row[f"{prefix}_bar_position"]),
        event_time_utc=event_time,
        information_phase=InformationPhase(str(row[f"{prefix}_information_phase"])),
        deterministic_sequence=int(row[f"{prefix}_deterministic_sequence"]),
    )


def _empty_target_row():
    return {column: pd.NA for column in _TARGET_COLUMNS}


def _target_row(
    factual_batch: FactualOutcomeBatch,
    research_snapshot_id: str,
    factual_outcome_id: str,
):
    snapshots = factual_batch.hypothesis_outcome_snapshots
    found = snapshots[
        (snapshots["research_snapshot_id"] == research_snapshot_id)
        & (snapshots["factual_outcome_id"] == factual_outcome_id)
    ]
    if len(found) != 1:
        raise DatasetDataError("selected factual outcome snapshot missing or duplicate")
    snapshot = found.iloc[0]
    if not bool(snapshot["outcome_mature"]):
        raise DatasetDataError("selected factual outcome is not mature")
    segments = factual_batch.outcome_path_segments[
        factual_batch.outcome_path_segments["research_snapshot_id"]
        == research_snapshot_id
    ]
    pre = segments[segments["segment_type"] == "PRE_ENDPOINT"]
    endpoint = segments[segments["segment_type"] == "ENDPOINT_BAR"]
    if len(pre) != 1 or len(endpoint) != 1:
        raise DatasetDataError("mature target path segments missing")
    pre = pre.iloc[0]
    endpoint = endpoint.iloc[0]
    return {
        "target_terminal_state": snapshot["narrative_terminal_state"],
        "target_pre_endpoint_favorable_excursion_fraction": pre[
            "favorable_excursion_fraction"
        ],
        "target_pre_endpoint_adverse_excursion_fraction": pre[
            "adverse_excursion_fraction"
        ],
        "target_pre_endpoint_same_bar_order_ambiguous": pre[
            "same_bar_order_ambiguous"
        ],
        "target_endpoint_bar_favorable_excursion_fraction": endpoint[
            "favorable_excursion_fraction"
        ],
        "target_endpoint_bar_adverse_excursion_fraction": endpoint[
            "adverse_excursion_fraction"
        ],
        "target_endpoint_bar_same_bar_order_ambiguous": endpoint[
            "same_bar_order_ambiguous"
        ],
    }


def _typed_targets(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    result["target_terminal_state"] = pd.array(
        result["target_terminal_state"], dtype="string"
    )
    for column in (
        "target_pre_endpoint_favorable_excursion_fraction",
        "target_pre_endpoint_adverse_excursion_fraction",
        "target_endpoint_bar_favorable_excursion_fraction",
        "target_endpoint_bar_adverse_excursion_fraction",
    ):
        result[column] = pd.array(result[column], dtype="Float64")
    for column in (
        "target_pre_endpoint_same_bar_order_ambiguous",
        "target_endpoint_bar_same_bar_order_ambiguous",
    ):
        result[column] = pd.array(result[column], dtype="boolean")
    return result


def _typed_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    integer_columns = [
        column
        for column in result.columns
        if column == "hypothesis_id"
        or column == "overlap_count_within_split"
        or column.endswith("_bar_position")
        or column.endswith("_deterministic_sequence")
    ]
    boolean_columns = {
        "target_available",
        "cross_split_label_overlap_detected",
    }
    for column in integer_columns:
        result[column] = pd.array(result[column], dtype="Int64")
    for column in boolean_columns:
        result[column] = pd.array(result[column], dtype="boolean")
    for column in result.columns:
        if column in integer_columns or column in boolean_columns:
            continue
        if column.endswith("_event_time_utc"):
            result[column] = pd.to_datetime(result[column], utc=True)
        else:
            result[column] = pd.array(result[column], dtype="string")
    return result


def _typed_audit(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    integer_columns = ("input_candidate_ordinal", "hypothesis_id")
    boolean_columns = (
        "purged",
        "included_in_train_features",
        "included_in_train_targets",
        "included_in_test_features",
        "included_in_test_targets",
        "decision_snapshot_attestation_valid",
        "manifest_identity_valid",
        "factual_identity_valid",
    )
    for column in integer_columns:
        result[column] = pd.array(result[column], dtype="Int64")
    for column in boolean_columns:
        result[column] = pd.array(result[column], dtype="boolean")
    for column in result.columns:
        if column not in integer_columns and column not in boolean_columns:
            result[column] = pd.array(result[column], dtype="string")
    return result


def _intervals_overlap(left_start, left_end, right_start, right_end) -> bool:
    if left_start is None or left_end is None or right_start is None or right_end is None:
        return False
    return max(left_start, right_start) < min(left_end, right_end)


class CausalResearchDatasetBuilder:
    """Stateless raw feature/target joiner and explicit walk-forward splitter."""

    def __init__(self, *, adapter: TimelineAdapter):
        self._adapter = adapter

    def _validate_eligibility(
        self,
        factual_batch: FactualOutcomeBatch,
        supplied: TemporalEligibilityResult,
        cutoff: InformationKey,
    ) -> TemporalEligibilityResult:
        expected = TemporalEligibilityGate(
            adapter=self._adapter,
            contract_version=ELIGIBILITY_CONTRACT_VERSION,
        ).evaluate(factual_batch, cutoff)
        _result_equal(supplied, expected)
        return expected

    @staticmethod
    def _feature_registry(
        snapshots: Iterable[FrozenDecisionFeatureSnapshot],
    ) -> list[FrozenDecisionFeatureSnapshot]:
        result = list(snapshots)
        identities = set()
        schemas = set()
        for snapshot in result:
            if not isinstance(snapshot, FrozenDecisionFeatureSnapshot):
                raise DatasetContractError("FrozenDecisionFeatureSnapshot required")
            snapshot.verify()
            identity = (
                snapshot.decision_snapshot_hash,
                snapshot.hypothesis_id,
                snapshot.snapshot_type,
            )
            if identity in identities:
                raise DatasetDataError("duplicate decision feature snapshot")
            identities.add(identity)
            feature_row = snapshot.raw_feature_row()
            schemas.add(
                canonical_sha256(
                    domain="RESEARCH_RAW_FEATURE_SCHEMA_V1",
                    payload={
                        "columns": list(feature_row.columns),
                        "dtypes": [str(dtype) for dtype in feature_row.dtypes],
                    },
                )
            )
        if len(schemas) > 1:
            raise DatasetContractError("inconsistent raw feature schemas")
        return result

    @staticmethod
    def _lookup_snapshot(
        registry: list[FrozenDecisionFeatureSnapshot], row: pd.Series
    ) -> FrozenDecisionFeatureSnapshot:
        found = [
            snapshot
            for snapshot in registry
            if snapshot.decision_snapshot_hash == str(row["decision_snapshot_hash"])
            and snapshot.hypothesis_id == int(row["hypothesis_id"])
            and snapshot.snapshot_type == str(row["snapshot_type"])
        ]
        if len(found) != 1:
            raise DatasetDataError("feature snapshot join missing or duplicate")
        snapshot = found[0]
        if snapshot.hypothesis_type != str(row["hypothesis_type"]):
            raise DatasetDataError("feature/outcome hypothesis type mismatch")
        return snapshot

    def build(
        self,
        *,
        fold_spec: WalkForwardFoldSpec,
        feature_snapshots: Iterable[FrozenDecisionFeatureSnapshot],
        factual_outcomes: FactualOutcomeBatch,
        train_eligibility: TemporalEligibilityResult,
        test_evaluation_eligibility: TemporalEligibilityResult | None = None,
    ) -> ResearchDatasetBuildResult:
        if not isinstance(fold_spec, WalkForwardFoldSpec):
            raise DatasetContractError("WalkForwardFoldSpec required")
        if fold_spec.timeline_id != self._adapter.timeline_id:
            raise DatasetContractError("fold/adapter timeline mismatch")
        registry = self._feature_registry(feature_snapshots)
        train_result = self._validate_eligibility(
            factual_outcomes, train_eligibility, fold_spec.train_cutoff
        )
        if fold_spec.test_label_as_of is None:
            if test_evaluation_eligibility is not None:
                raise DatasetContractError("test eligibility supplied without label as-of")
            test_result = None
        else:
            if test_evaluation_eligibility is None:
                raise DatasetContractError("test label as-of requires eligibility result")
            test_result = self._validate_eligibility(
                factual_outcomes,
                test_evaluation_eligibility,
                fold_spec.test_label_as_of,
            )

        train_selected = train_result.selected_mature_samples
        train_items: list[dict] = []
        train_ids = set()
        for _, row in train_selected.iterrows():
            snapshot = self._lookup_snapshot(registry, row)
            label_start = _selected_key(row, "label_information_start_exclusive")
            label_end = _selected_key(row, "label_information_end_inclusive")
            if not label_end <= fold_spec.train_cutoff:
                raise DatasetContractError("UPSTREAM_ELIGIBILITY_CONTRACT_VIOLATION")
            sample_id = _sample_id(fold_spec.fold_id, snapshot)
            if sample_id in train_ids:
                raise DatasetDataError("duplicate TRAIN sample identity")
            train_ids.add(sample_id)
            train_items.append(
                {
                    "sample_id": sample_id,
                    "snapshot": snapshot,
                    "factual_outcome_id": str(row["factual_outcome_id"]),
                    "research_snapshot_id": str(row["selected_research_snapshot_id"]),
                    "label_start": label_start,
                    "label_end": label_end,
                }
            )

        test_items: list[dict] = []
        for snapshot in registry:
            key = snapshot.snapshot_information_key
            if fold_spec.train_cutoff < key <= fold_spec.test_creation_end_inclusive:
                test_items.append(
                    {
                        "sample_id": _sample_id(fold_spec.fold_id, snapshot),
                        "snapshot": snapshot,
                        "factual_outcome_id": None,
                        "research_snapshot_id": None,
                        "label_start": key,
                        "label_end": None,
                    }
                )
        if train_ids & {item["sample_id"] for item in test_items}:
            raise DatasetContractError("sample appears in TRAIN and TEST")

        test_selected_lookup = {}
        if test_result is not None:
            for _, row in test_result.selected_mature_samples.iterrows():
                key = (
                    str(row["decision_snapshot_hash"]),
                    int(row["hypothesis_id"]),
                    str(row["snapshot_type"]),
                )
                test_selected_lookup[key] = row
        for item in test_items:
            snapshot = item["snapshot"]
            key = (
                snapshot.decision_snapshot_hash,
                snapshot.hypothesis_id,
                snapshot.snapshot_type,
            )
            selected = test_selected_lookup.get(key)
            if selected is not None:
                item["factual_outcome_id"] = str(selected["factual_outcome_id"])
                item["research_snapshot_id"] = str(
                    selected["selected_research_snapshot_id"]
                )
                item["label_start"] = _selected_key(
                    selected, "label_information_start_exclusive"
                )
                item["label_end"] = _selected_key(
                    selected, "label_information_end_inclusive"
                )

        train_features, train_targets = self._feature_target_tables(
            train_items, factual_outcomes, require_targets=True
        )
        test_features, test_targets = self._feature_target_tables(
            test_items, factual_outcomes, require_targets=False
        )
        if len(train_features.columns) == 0 and len(test_features.columns) > 0:
            train_features = test_features.iloc[0:0].copy(deep=True)
            train_features.index = pd.Index([], name="sample_id")
        if len(test_features.columns) == 0 and len(train_features.columns) > 0:
            test_features = train_features.iloc[0:0].copy(deep=True)
            test_features.index = pd.Index([], name="sample_id")
        if tuple(train_features.columns) != tuple(test_features.columns):
            raise DatasetContractError("TRAIN/TEST feature schema mismatch")
        if [str(dtype) for dtype in train_features.dtypes] != [
            str(dtype) for dtype in test_features.dtypes
        ]:
            raise DatasetContractError("TRAIN/TEST feature dtype mismatch")
        metadata = self._metadata(fold_spec, train_items, test_items)
        audit = self._audit(fold_spec, registry, train_items, test_items)
        fold_manifest = self._fold_manifest(
            fold_spec,
            train_features,
            train_targets,
            test_features,
            test_targets,
            metadata,
            train_result,
            test_result,
        )
        return ResearchDatasetBuildResult(
            fold=ResearchDatasetFold(
                train_features_raw=train_features,
                train_targets=train_targets,
                test_features_raw=test_features,
                test_targets=test_targets,
                sample_metadata=metadata,
                fold_manifest=fold_manifest,
            ),
            dataset_build_audit=audit,
        )

    @staticmethod
    def _feature_target_tables(items, factual_outcomes, *, require_targets):
        feature_rows = []
        target_rows = []
        sample_ids = []
        for item in items:
            sample_ids.append(item["sample_id"])
            feature_rows.append(item["snapshot"].raw_feature_row())
            if item["factual_outcome_id"] is None:
                if require_targets:
                    raise DatasetDataError("TRAIN factual outcome missing")
                target_rows.append(_empty_target_row())
            else:
                target_rows.append(
                    _target_row(
                        factual_outcomes,
                        item["research_snapshot_id"],
                        item["factual_outcome_id"],
                    )
                )
        if feature_rows:
            features = pd.concat(feature_rows, ignore_index=True)
            features.index = pd.Index(sample_ids, name="sample_id")
        else:
            features = pd.DataFrame(index=pd.Index([], name="sample_id"))
        targets = _typed_targets(pd.DataFrame(target_rows, columns=_TARGET_COLUMNS))
        targets.index = pd.Index(sample_ids, name="sample_id")
        return features, targets

    @staticmethod
    def _metadata(fold_spec, train_items, test_items):
        all_items = [("TRAIN", item) for item in train_items] + [
            ("TEST", item) for item in test_items
        ]
        rows = []
        for role, item in all_items:
            snapshot = item["snapshot"]
            interval = (item["label_start"], item["label_end"])
            same_split = [
                other
                for other_role, other in all_items
                if other_role == role and other["sample_id"] != item["sample_id"]
            ]
            overlap_count = sum(
                _intervals_overlap(
                    interval[0], interval[1], other["label_start"], other["label_end"]
                )
                for other in same_split
            )
            other_split = [other for other_role, other in all_items if other_role != role]
            cross_overlap = any(
                _intervals_overlap(
                    interval[0], interval[1], other["label_start"], other["label_end"]
                )
                for other in other_split
            )
            rows.append(
                {
                    "sample_id": item["sample_id"],
                    "fold_id": fold_spec.fold_id,
                    "split_role": role,
                    "timeline_id": snapshot.timeline_id,
                    "decision_snapshot_hash": snapshot.decision_snapshot_hash,
                    "hypothesis_id": snapshot.hypothesis_id,
                    "hypothesis_type": snapshot.hypothesis_type,
                    "snapshot_type": snapshot.snapshot_type,
                    "factual_outcome_id": item["factual_outcome_id"],
                    "selected_research_snapshot_id": item["research_snapshot_id"],
                    **_metadata_key_fields(
                        "snapshot", snapshot.snapshot_information_key
                    ),
                    **_metadata_key_fields(
                        "final_outcome_known", item["label_end"]
                    ),
                    **_metadata_key_fields(
                        "label_interval_start_exclusive", item["label_start"]
                    ),
                    **_metadata_key_fields(
                        "label_interval_end_inclusive", item["label_end"]
                    ),
                    "target_available": item["factual_outcome_id"] is not None,
                    "target_availability_reason": (
                        "AVAILABLE"
                        if item["factual_outcome_id"] is not None
                        else "TEST_TARGET_NOT_MATURE_AS_OF_BOUNDARY"
                    ),
                    "overlap_count_within_split": overlap_count,
                    "cross_split_label_overlap_detected": cross_overlap,
                    "dataset_contract_version": DATASET_CONTRACT_VERSION,
                }
            )
        return _typed_metadata(pd.DataFrame(rows, columns=_METADATA_COLUMNS))

    @staticmethod
    def _audit(fold_spec, registry, train_items, test_items):
        train_ids = {item["sample_id"] for item in train_items}
        test_ids = {item["sample_id"] for item in test_items}
        rows = []
        for ordinal, snapshot in enumerate(registry):
            sample_id = _sample_id(fold_spec.fold_id, snapshot)
            in_train = sample_id in train_ids
            in_test = sample_id in test_ids
            role = "TRAIN" if in_train else "TEST" if in_test else "OUTSIDE_FOLD"
            target_available = any(
                item["sample_id"] == sample_id
                and item["factual_outcome_id"] is not None
                for item in train_items + test_items
            )
            rows.append(
                {
                    "input_candidate_ordinal": ordinal,
                    "sample_id": sample_id,
                    "fold_id": fold_spec.fold_id,
                    "decision_snapshot_hash": snapshot.decision_snapshot_hash,
                    "hypothesis_id": snapshot.hypothesis_id,
                    "hypothesis_type": snapshot.hypothesis_type,
                    "snapshot_type": snapshot.snapshot_type,
                    "requested_split_role": role,
                    "feature_join_status": "INCLUDED" if in_train or in_test else "NOT_REQUESTED",
                    "feature_join_reason": "EXACT_IDENTITY_MATCH" if in_train or in_test else "SNAPSHOT_OUTSIDE_FOLD",
                    "outcome_join_status": "INCLUDED" if target_available else "UNAVAILABLE",
                    "outcome_join_reason": "MATURE_FACTUAL_IDENTITY" if target_available else "TEST_TARGET_IMMATURE_OR_NOT_REQUESTED",
                    "train_eligibility_status": "SELECTED" if in_train else "NOT_SELECTED",
                    "test_target_availability_status": (
                        "AVAILABLE"
                        if in_test and target_available
                        else "TEST_TARGET_IMMATURE"
                        if in_test
                        else "NOT_APPLICABLE"
                    ),
                    "purged": False,
                    "purge_reason": "NONE",
                    "included_in_train_features": in_train,
                    "included_in_train_targets": in_train,
                    "included_in_test_features": in_test,
                    "included_in_test_targets": in_test and target_available,
                    "decision_snapshot_attestation_valid": True,
                    "manifest_identity_valid": True,
                    "factual_identity_valid": target_available or not in_train,
                    "dataset_contract_version": DATASET_CONTRACT_VERSION,
                }
            )
        return _typed_audit(pd.DataFrame(rows, columns=_AUDIT_COLUMNS))

    @staticmethod
    def _fold_manifest(
        fold_spec,
        train_features,
        train_targets,
        test_features,
        test_targets,
        metadata,
        train_result,
        test_result,
    ):
        payload = {
            "fold_spec": {
                "fold_id": fold_spec.fold_id,
                "timeline_id": fold_spec.timeline_id,
                "train_cutoff": fold_spec.train_cutoff,
                "test_creation_end_inclusive": fold_spec.test_creation_end_inclusive,
                "test_label_as_of": fold_spec.test_label_as_of,
            },
            "train_features": train_features,
            "train_targets": train_targets,
            "test_features": test_features,
            "test_targets": test_targets,
            "metadata": metadata,
        }
        feature_columns = (
            list(train_features.columns)
            if len(train_features.columns) > 0
            else list(test_features.columns)
        )
        return pd.DataFrame(
            [
                {
                    "dataset_contract_version": DATASET_CONTRACT_VERSION,
                    "fold_id": fold_spec.fold_id,
                    "fold_spec_hash": canonical_sha256(
                        domain="RESEARCH_FOLD_SPEC_V1", payload=payload["fold_spec"]
                    ),
                    "raw_feature_schema_hash": canonical_sha256(
                        domain="RESEARCH_FEATURE_SCHEMA_V1",
                        payload={
                            "columns": feature_columns,
                            "train_dtypes": [str(dtype) for dtype in train_features.dtypes],
                            "test_dtypes": [str(dtype) for dtype in test_features.dtypes],
                        },
                    ),
                    "target_schema_hash": canonical_sha256(
                        domain="RESEARCH_TARGET_SCHEMA_V1",
                        payload=list(_TARGET_COLUMNS),
                    ),
                    "train_sample_set_hash": canonical_sha256(
                        domain="RESEARCH_TRAIN_SAMPLE_SET_V1",
                        payload=list(train_features.index),
                    ),
                    "test_sample_set_hash": canonical_sha256(
                        domain="RESEARCH_TEST_SAMPLE_SET_V1",
                        payload=list(test_features.index),
                    ),
                    "dataset_fold_hash": canonical_sha256(
                        domain="RESEARCH_DATASET_FOLD_V1", payload=payload
                    ),
                    "train_eligibility_manifest_hash": canonical_sha256(
                        domain="ELIGIBILITY_MANIFEST_V1", payload=eligibility_manifest()
                    ),
                    "test_evaluation_present": test_result is not None,
                    "preprocessing_status": "NOT_IMPLEMENTED_RAW_ONLY",
                }
            ]
        )

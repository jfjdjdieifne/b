"""Module 6.2A-2 V1: temporal legality audit and mature-sample deduplication."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Final, Union

import numpy as np
import pandas as pd

from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import (
    INFORMATION_KEY_VERSION,
    InformationKey,
    InformationKeyError,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.outcome_observer import (
    OUTCOME_CONTRACT_VERSION,
    RIGHT_CENSORING_TYPE,
    SnapshotType,
    outcome_contract_manifest,
)


class EligibilityError(Exception):
    """Base temporal eligibility error."""


class EligibilityContractError(EligibilityError):
    """Input schema, key, adapter, or static contract violation."""


class EligibilityDataError(EligibilityError):
    """Conflicting factual identities or malformed batch relationships."""


class EligibilityReason(Enum):
    CONTRACT_VERSION_MISMATCH = "CONTRACT_VERSION_MISMATCH"
    HASH_VALIDATION_FAILED = "HASH_VALIDATION_FAILED"
    UNSUPPORTED_SNAPSHOT_TYPE = "UNSUPPORTED_SNAPSHOT_TYPE"
    TIMELINE_MISMATCH = "TIMELINE_MISMATCH"
    OUTCOME_IMMATURE = "OUTCOME_IMMATURE"
    RIGHT_CENSORED = "RIGHT_CENSORED"
    FACTUAL_OUTCOME_ID_MISSING = "FACTUAL_OUTCOME_ID_MISSING"
    FINAL_OUTCOME_KEY_MISSING = "FINAL_OUTCOME_KEY_MISSING"
    TERMINAL_KEY_MISSING = "TERMINAL_KEY_MISSING"
    FINAL_TERMINAL_KEY_MISMATCH = "FINAL_TERMINAL_KEY_MISMATCH"
    SNAPSHOT_NOT_BEFORE_CUTOFF = "SNAPSHOT_NOT_BEFORE_CUTOFF"
    FINAL_OUTCOME_AFTER_CUTOFF = "FINAL_OUTCOME_AFTER_CUTOFF"
    TERMINAL_AFTER_CUTOFF = "TERMINAL_AFTER_CUTOFF"
    ELIGIBLE = "ELIGIBLE"


ELIGIBILITY_CONTRACT_VERSION: Final = "TEMPORAL_ELIGIBILITY_V1"
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
TimelineAdapter = Union[PositionalTimelineAdapter, TimeIndexedTimelineAdapter]
_KEY_PARTS: Final = (
    "information_key_version",
    "bar_position",
    "event_time_utc",
    "information_phase",
    "deterministic_sequence",
)


def _audit_key_columns(prefix: str, include_timeline: bool = False) -> tuple[str, ...]:
    middle = (f"{prefix}_timeline_id",) if include_timeline else ()
    return (
        f"{prefix}_information_key_version",
        *middle,
        f"{prefix}_bar_position",
        f"{prefix}_event_time_utc",
        f"{prefix}_information_phase",
        f"{prefix}_deterministic_sequence",
    )


_AUDIT_COLUMNS: Final = (
    "input_row_ordinal",
    "research_snapshot_id",
    "decision_snapshot_hash",
    "factual_outcome_id",
    "hypothesis_id",
    "hypothesis_type",
    "snapshot_type",
    "record_timeline_id",
    *_audit_key_columns("training_cutoff", include_timeline=True),
    *_audit_key_columns("snapshot"),
    *_audit_key_columns("terminal"),
    *_audit_key_columns("final_outcome_known"),
    "temporally_eligible",
    "eligibility_reason",
    "eligibility_contract_version",
)

_SELECTED_COLUMNS: Final = (
    "selected_research_snapshot_id",
    "selected_input_row_ordinal",
    "factual_outcome_id",
    "decision_snapshot_hash",
    "hypothesis_id",
    "hypothesis_type",
    "snapshot_type",
    "narrative_terminal_state",
    *_audit_key_columns("final_outcome_known", include_timeline=True),
    *_audit_key_columns("label_information_start_exclusive", include_timeline=True),
    *_audit_key_columns("label_information_end_inclusive", include_timeline=True),
    "eligibility_contract_version",
)


@dataclass(frozen=True)
class FactualOutcomeBatch:
    hypothesis_outcome_snapshots: pd.DataFrame
    outcome_path_segments: pd.DataFrame
    outcome_manifest: pd.DataFrame


@dataclass(frozen=True)
class TemporalEligibilityResult:
    temporal_eligibility_audit: pd.DataFrame
    selected_mature_samples: pd.DataFrame


def _is_missing(value) -> bool:
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    missing = pd.isna(value)
    if not isinstance(missing, (bool, np.bool_)):
        raise EligibilityContractError("eligibility scalar required")
    return bool(missing)


def _strict_int(value, name: str) -> int:
    if _is_missing(value):
        raise EligibilityContractError(f"{name} is missing")
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise EligibilityContractError(f"{name} must be integer")
    result = int(value)
    if result < 0:
        raise EligibilityContractError(f"{name} must be nonnegative")
    return result


def _strict_bool(value, name: str) -> bool:
    if _is_missing(value) or not isinstance(value, (bool, np.bool_)):
        raise EligibilityContractError(f"{name} must be nonmissing boolean")
    return bool(value)


def _is_sha256(value) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _key_fields(prefix: str, key: InformationKey | None, *, include_timeline=False):
    if key is None:
        fields = {
            f"{prefix}_information_key_version": pd.NA,
            f"{prefix}_bar_position": pd.NA,
            f"{prefix}_event_time_utc": pd.NaT,
            f"{prefix}_information_phase": pd.NA,
            f"{prefix}_deterministic_sequence": pd.NA,
        }
        if include_timeline:
            fields[f"{prefix}_timeline_id"] = pd.NA
        return fields
    fields = {
        f"{prefix}_information_key_version": key.information_key_version,
        f"{prefix}_bar_position": key.bar_position,
        f"{prefix}_event_time_utc": (
            pd.NaT if key.event_time_utc is None else key.event_time_utc
        ),
        f"{prefix}_information_phase": key.information_phase.value,
        f"{prefix}_deterministic_sequence": key.deterministic_sequence,
    }
    if include_timeline:
        fields[f"{prefix}_timeline_id"] = key.timeline_id
    return fields


def _expected_outcome_columns():
    manifest = outcome_contract_manifest()
    snapshots = tuple(
        manifest.loc[manifest["record_type"] == "SNAPSHOT_COLUMN", "name"].tolist()
    )
    paths = tuple(
        manifest.loc[manifest["record_type"] == "PATH_COLUMN", "name"].tolist()
    )
    return snapshots, paths, manifest


def _validate_exact_columns(frame: pd.DataFrame, expected: tuple[str, ...], name: str):
    if not isinstance(frame, pd.DataFrame) or frame.columns.has_duplicates:
        raise EligibilityContractError(f"invalid {name}")
    if tuple(frame.columns) != expected:
        raise EligibilityContractError(f"{name} schema/order mismatch")


def _expected_snapshot_dtype(column: str) -> str:
    if (
        column.endswith("_position")
        or column.endswith("_bar_position")
        or column.endswith("_deterministic_sequence")
        or column in {"hypothesis_id", "terminal_ledger_event_id", "trigger_relationship_id"}
    ):
        return "Int64"
    if column == "reference_price":
        return "Float64"
    if column in {
        "reference_is_execution_price",
        "outcome_mature",
        "right_censored_as_of",
    }:
        return "boolean"
    if column.endswith("_event_time_utc"):
        return "datetime64[ns, UTC]"
    return "string"


def _expected_path_dtype(column: str) -> str:
    if column in {
        "segment_start_exclusive_position",
        "segment_end_inclusive_position",
        "segment_observation_count",
        "favorable_extreme_position",
        "adverse_extreme_position",
    }:
        return "Int64"
    if column in {"segment_available", "same_bar_order_ambiguous"}:
        return "boolean"
    if column in {
        "favorable_excursion_fraction",
        "adverse_excursion_fraction",
        "favorable_extreme_price",
        "adverse_extreme_price",
    }:
        return "Float64"
    return "string"


def _validate_dtypes(frame: pd.DataFrame, expected_fn, name: str) -> None:
    mismatches = [
        (column, str(frame[column].dtype), expected_fn(column))
        for column in frame.columns
        if str(frame[column].dtype) != expected_fn(column)
    ]
    if mismatches:
        raise EligibilityContractError(f"{name} dtype mismatch: {mismatches}")


def _decode_key(
    row: pd.Series,
    prefix: str,
    timeline_id: str,
    adapter: TimelineAdapter,
    *,
    required: bool,
) -> InformationKey | None:
    names = {part: f"{prefix}_{part}" for part in _KEY_PARTS}
    missing_columns = [column for column in names.values() if column not in row.index]
    if missing_columns:
        raise EligibilityContractError(f"{prefix} key columns missing")
    core = (
        row[names["information_key_version"]],
        row[names["bar_position"]],
        row[names["information_phase"]],
        row[names["deterministic_sequence"]],
    )
    core_missing = [_is_missing(value) for value in core]
    timestamp = row[names["event_time_utc"]]
    timestamp_missing = _is_missing(timestamp)
    if all(core_missing):
        if not timestamp_missing:
            raise EligibilityContractError(f"partial {prefix} key")
        if required:
            raise EligibilityContractError(f"required {prefix} key missing")
        return None
    if any(core_missing):
        raise EligibilityContractError(f"partial {prefix} key")
    version = str(core[0])
    if version != INFORMATION_KEY_VERSION:
        raise EligibilityContractError(f"invalid {prefix} key version")
    position = _strict_int(core[1], f"{prefix}.bar_position")
    sequence = _strict_int(core[3], f"{prefix}.deterministic_sequence")
    try:
        phase = InformationPhase(str(core[2]))
    except ValueError as exc:
        raise EligibilityContractError(f"invalid {prefix} phase") from exc
    if isinstance(adapter, PositionalTimelineAdapter):
        if not timestamp_missing:
            raise EligibilityContractError(f"positional {prefix} timestamp forbidden")
        event_time = None
    elif isinstance(adapter, TimeIndexedTimelineAdapter):
        if timestamp_missing or not isinstance(timestamp, pd.Timestamp):
            raise EligibilityContractError(f"time-indexed {prefix} timestamp required")
        if timestamp.tz is None:
            raise EligibilityContractError(f"naive {prefix} timestamp forbidden")
        event_time = timestamp.tz_convert("UTC")
    else:
        raise EligibilityContractError("unsupported timeline adapter")
    try:
        return InformationKey(
            information_key_version=version,
            timeline_id=timeline_id,
            bar_position=position,
            event_time_utc=event_time,
            information_phase=phase,
            deterministic_sequence=sequence,
        )
    except InformationKeyError as exc:
        raise EligibilityContractError(f"invalid {prefix} InformationKey") from exc


def _validate_cutoff(cutoff: InformationKey, adapter: TimelineAdapter):
    if not isinstance(cutoff, InformationKey):
        raise EligibilityContractError("explicit training cutoff InformationKey required")
    if cutoff.timeline_id != adapter.timeline_id:
        raise EligibilityContractError("training cutoff timeline mismatch")
    if cutoff.information_key_version != INFORMATION_KEY_VERSION:
        raise EligibilityContractError("training cutoff version mismatch")
    if isinstance(adapter, PositionalTimelineAdapter):
        if cutoff.event_time_utc is not None:
            raise EligibilityContractError("positional cutoff timestamp forbidden")
    elif isinstance(adapter, TimeIndexedTimelineAdapter):
        if cutoff.event_time_utc is None:
            raise EligibilityContractError("time-indexed cutoff timestamp required")
    else:
        raise EligibilityContractError("unsupported timeline adapter")


def _typed_audit(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    for column in (
        "input_row_ordinal",
        "hypothesis_id",
        "training_cutoff_bar_position",
        "training_cutoff_deterministic_sequence",
        "snapshot_bar_position",
        "snapshot_deterministic_sequence",
        "terminal_bar_position",
        "terminal_deterministic_sequence",
        "final_outcome_known_bar_position",
        "final_outcome_known_deterministic_sequence",
    ):
        result[column] = pd.array(result[column], dtype="Int64")
    result["temporally_eligible"] = pd.array(
        result["temporally_eligible"], dtype="boolean"
    )
    for column in [
        column
        for column in result.columns
        if column not in {"temporally_eligible"}
        and column
        not in {
            "input_row_ordinal",
            "hypothesis_id",
            "training_cutoff_bar_position",
            "training_cutoff_deterministic_sequence",
            "snapshot_bar_position",
            "snapshot_deterministic_sequence",
            "terminal_bar_position",
            "terminal_deterministic_sequence",
            "final_outcome_known_bar_position",
            "final_outcome_known_deterministic_sequence",
        }
        and not column.endswith("_event_time_utc")
    ]:
        result[column] = pd.array(result[column], dtype="string")
    for column in [c for c in result.columns if c.endswith("_event_time_utc")]:
        result[column] = pd.to_datetime(result[column], utc=True)
    return result


def _typed_selected(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    integer_columns = (
        "selected_input_row_ordinal",
        "hypothesis_id",
        "final_outcome_known_bar_position",
        "final_outcome_known_deterministic_sequence",
        "label_information_start_exclusive_bar_position",
        "label_information_start_exclusive_deterministic_sequence",
        "label_information_end_inclusive_bar_position",
        "label_information_end_inclusive_deterministic_sequence",
    )
    for column in integer_columns:
        result[column] = pd.array(result[column], dtype="Int64")
    for column in [
        column
        for column in result.columns
        if column not in integer_columns and not column.endswith("_event_time_utc")
    ]:
        result[column] = pd.array(result[column], dtype="string")
    for column in [c for c in result.columns if c.endswith("_event_time_utc")]:
        result[column] = pd.to_datetime(result[column], utc=True)
    return result


class TemporalEligibilityGate:
    """Stateless temporal legality gate; no feature or model operations."""

    def __init__(self, *, adapter: TimelineAdapter, contract_version: str):
        if not isinstance(adapter, (PositionalTimelineAdapter, TimeIndexedTimelineAdapter)):
            raise EligibilityContractError("explicit timeline adapter required")
        if not isinstance(contract_version, str):
            raise EligibilityContractError("explicit eligibility contract version required")
        self._adapter = adapter
        self._contract_version = contract_version

    def _validate_batch(self, batch: FactualOutcomeBatch):
        if not isinstance(batch, FactualOutcomeBatch):
            raise EligibilityContractError("FactualOutcomeBatch required")
        expected_snapshots, expected_paths, certified_manifest = _expected_outcome_columns()
        _validate_exact_columns(
            batch.hypothesis_outcome_snapshots,
            expected_snapshots,
            "hypothesis_outcome_snapshots",
        )
        _validate_exact_columns(
            batch.outcome_path_segments, expected_paths, "outcome_path_segments"
        )
        _validate_dtypes(
            batch.hypothesis_outcome_snapshots,
            _expected_snapshot_dtype,
            "hypothesis_outcome_snapshots",
        )
        _validate_dtypes(
            batch.outcome_path_segments,
            _expected_path_dtype,
            "outcome_path_segments",
        )
        try:
            pd.testing.assert_frame_equal(
                batch.outcome_manifest,
                certified_manifest,
                check_exact=True,
                check_dtype=True,
                check_like=False,
            )
        except AssertionError as exc:
            raise EligibilityContractError("outcome manifest identity mismatch") from exc
        snapshots = batch.hypothesis_outcome_snapshots
        paths = batch.outcome_path_segments
        if snapshots["research_snapshot_id"].isna().any():
            raise EligibilityContractError("research_snapshot_id missing")
        if snapshots["research_snapshot_id"].duplicated().any():
            raise EligibilityDataError("duplicate research_snapshot_id")
        snapshot_ids = set(snapshots["research_snapshot_id"].astype(str))
        path_ids = set(paths["research_snapshot_id"].astype(str))
        if not path_ids.issubset(snapshot_ids):
            raise EligibilityDataError("orphan outcome path segment")
        missing_paths = snapshot_ids - path_ids
        if missing_paths:
            raise EligibilityDataError("research snapshot missing path segments")

    @staticmethod
    def _segment_group(paths: pd.DataFrame, research_snapshot_id: str) -> pd.DataFrame:
        return paths[paths["research_snapshot_id"] == research_snapshot_id].copy(
            deep=True
        ).reset_index(drop=True)

    @staticmethod
    def _validate_segment_contract(row: pd.Series, segments: pd.DataFrame):
        mature = _strict_bool(row["outcome_mature"], "outcome_mature")
        censored = _strict_bool(row["right_censored_as_of"], "right_censored_as_of")
        types = segments["segment_type"].astype(str).tolist()
        if mature and not censored:
            if types != ["PRE_ENDPOINT", "ENDPOINT_BAR"]:
                raise EligibilityDataError("mature path segment contract mismatch")
        elif not mature and censored:
            if types != ["OBSERVED_THROUGH_AS_OF"]:
                raise EligibilityDataError("censored path segment contract mismatch")
        elif types not in (["PRE_ENDPOINT", "ENDPOINT_BAR"], ["OBSERVED_THROUGH_AS_OF"]):
            raise EligibilityDataError("inconsistent path segment contract")

    def _hashes_valid(
        self,
        row: pd.Series,
        research_as_of: InformationKey,
        terminal_key: InformationKey | None,
        segments: pd.DataFrame,
    ) -> bool:
        required_hashes = (
            "research_snapshot_id",
            "decision_snapshot_hash",
            "feature_manifest_hash",
            "narrative_manifest_hash",
            "decision_input_slice_hash",
            "research_market_slice_hash",
            "research_outcome_hash",
        )
        if any(not _is_sha256(row[column]) for column in required_hashes):
            return False
        mature = _strict_bool(row["outcome_mature"], "outcome_mature")
        factual = row["factual_outcome_id"]
        if mature:
            if not _is_sha256(factual):
                return False
        elif not _is_missing(factual):
            return False
        expected_snapshot_id = canonical_sha256(
            domain="RESEARCH_SNAPSHOT_ID_V1_2",
            payload={
                "decision_snapshot_hash": str(row["decision_snapshot_hash"]),
                "hypothesis_id": _strict_int(row["hypothesis_id"], "hypothesis_id"),
                "snapshot_type": str(row["snapshot_type"]),
                "research_as_of": research_as_of,
                "outcome_contract_version": str(row["outcome_contract_version"]),
            },
        )
        if expected_snapshot_id != str(row["research_snapshot_id"]):
            return False
        if mature:
            expected_factual = canonical_sha256(
                domain="MATURE_FACTUAL_OUTCOME_ID_V1_2",
                payload={
                    "decision_snapshot_hash": str(row["decision_snapshot_hash"]),
                    "hypothesis_id": _strict_int(row["hypothesis_id"], "hypothesis_id"),
                    "terminal_state": str(row["narrative_terminal_state"]),
                    "terminal_event_id": _strict_int(
                        row["terminal_ledger_event_id"], "terminal_ledger_event_id"
                    ),
                    "trigger_relationship_id": _strict_int(
                        row["trigger_relationship_id"], "trigger_relationship_id"
                    ),
                    "terminal_key": terminal_key,
                    "research_market_slice_hash": str(
                        row["research_market_slice_hash"]
                    ),
                    "segments": segments.drop(columns=["research_snapshot_id"]),
                    "outcome_contract_version": str(row["outcome_contract_version"]),
                },
            )
            if expected_factual != str(factual):
                return False
        expected_research = canonical_sha256(
            domain="RESEARCH_OUTCOME_V1_2",
            payload={
                "research_snapshot_id": str(row["research_snapshot_id"]),
                "factual_outcome_id": factual,
                "research_as_of": research_as_of,
                "censoring_type": (
                    None if mature else RIGHT_CENSORING_TYPE
                ),
                "research_market_slice_hash": str(
                    row["research_market_slice_hash"]
                ),
                "segments": segments,
                "outcome_contract_version": str(row["outcome_contract_version"]),
            },
        )
        return expected_research == str(row["research_outcome_hash"])

    def _reason(
        self,
        row: pd.Series,
        *,
        cutoff: InformationKey,
        research_as_of: InformationKey,
        snapshot_key: InformationKey,
        terminal_key: InformationKey | None,
        final_key: InformationKey | None,
        hashes_valid: bool,
    ) -> EligibilityReason:
        if (
            self._contract_version != ELIGIBILITY_CONTRACT_VERSION
            or str(row["outcome_contract_version"]) != OUTCOME_CONTRACT_VERSION
        ):
            return EligibilityReason.CONTRACT_VERSION_MISMATCH
        if not hashes_valid:
            return EligibilityReason.HASH_VALIDATION_FAILED
        if str(row["snapshot_type"]) != SnapshotType.HYPOTHESIS_CREATION_SNAPSHOT.value:
            return EligibilityReason.UNSUPPORTED_SNAPSHOT_TYPE
        if str(row["timeline_id"]) != cutoff.timeline_id:
            return EligibilityReason.TIMELINE_MISMATCH
        mature = _strict_bool(row["outcome_mature"], "outcome_mature")
        censored = _strict_bool(
            row["right_censored_as_of"], "right_censored_as_of"
        )
        if not mature:
            return EligibilityReason.OUTCOME_IMMATURE
        if censored:
            return EligibilityReason.RIGHT_CENSORED
        if _is_missing(row["factual_outcome_id"]):
            return EligibilityReason.FACTUAL_OUTCOME_ID_MISSING
        if final_key is None:
            return EligibilityReason.FINAL_OUTCOME_KEY_MISSING
        if terminal_key is None:
            return EligibilityReason.TERMINAL_KEY_MISSING
        if final_key != terminal_key:
            return EligibilityReason.FINAL_TERMINAL_KEY_MISMATCH
        if not snapshot_key < cutoff:
            return EligibilityReason.SNAPSHOT_NOT_BEFORE_CUTOFF
        if not final_key <= cutoff:
            return EligibilityReason.FINAL_OUTCOME_AFTER_CUTOFF
        if not terminal_key <= cutoff:
            return EligibilityReason.TERMINAL_AFTER_CUTOFF
        return EligibilityReason.ELIGIBLE

    @staticmethod
    def _factual_consistency_payload(row: pd.Series, segments: pd.DataFrame):
        columns = (
            "decision_snapshot_hash",
            "hypothesis_id",
            "hypothesis_type",
            "direction",
            "snapshot_type",
            "snapshot_position",
            "reference_price",
            "reference_price_source",
            "reference_is_execution_price",
            "narrative_terminal_state",
            "terminal_ledger_event_id",
            "trigger_relationship_id",
            "terminal_position",
            "research_market_slice_hash",
        )
        return {
            "snapshot": {column: row[column] for column in columns},
            "snapshot_key": {part: row[f"snapshot_{part}"] for part in _KEY_PARTS},
            "terminal_key": {part: row[f"terminal_{part}"] for part in _KEY_PARTS},
            "final_key": {
                part: row[f"final_outcome_known_{part}"] for part in _KEY_PARTS
            },
            "segments": segments.drop(columns=["research_snapshot_id"]),
        }

    def evaluate(
        self,
        batch: FactualOutcomeBatch,
        training_cutoff: InformationKey,
    ) -> TemporalEligibilityResult:
        self._validate_batch(batch)
        _validate_cutoff(training_cutoff, self._adapter)
        snapshots = batch.hypothesis_outcome_snapshots
        paths = batch.outcome_path_segments
        audit_rows: list[dict] = []
        parsed: dict[int, dict] = {}

        for ordinal in range(len(snapshots)):
            row = snapshots.iloc[ordinal]
            timeline_id = str(row["timeline_id"])
            research_as_of = _decode_key(
                row, "research_as_of", timeline_id, self._adapter, required=True
            )
            snapshot_key = _decode_key(
                row, "snapshot", timeline_id, self._adapter, required=True
            )
            terminal_key = _decode_key(
                row, "terminal", timeline_id, self._adapter, required=False
            )
            final_key = _decode_key(
                row,
                "final_outcome_known",
                timeline_id,
                self._adapter,
                required=False,
            )
            research_snapshot_id = str(row["research_snapshot_id"])
            segments = self._segment_group(paths, research_snapshot_id)
            self._validate_segment_contract(row, segments)
            hashes_valid = self._hashes_valid(
                row, research_as_of, terminal_key, segments
            )
            reason = self._reason(
                row,
                cutoff=training_cutoff,
                research_as_of=research_as_of,
                snapshot_key=snapshot_key,
                terminal_key=terminal_key,
                final_key=final_key,
                hashes_valid=hashes_valid,
            )
            factual_value = row["factual_outcome_id"]
            audit_rows.append(
                {
                    "input_row_ordinal": ordinal,
                    "research_snapshot_id": research_snapshot_id,
                    "decision_snapshot_hash": row["decision_snapshot_hash"],
                    "factual_outcome_id": (
                        pd.NA if _is_missing(factual_value) else str(factual_value)
                    ),
                    "hypothesis_id": row["hypothesis_id"],
                    "hypothesis_type": row["hypothesis_type"],
                    "snapshot_type": row["snapshot_type"],
                    "record_timeline_id": timeline_id,
                    **_key_fields(
                        "training_cutoff", training_cutoff, include_timeline=True
                    ),
                    **_key_fields("snapshot", snapshot_key),
                    **_key_fields("terminal", terminal_key),
                    **_key_fields("final_outcome_known", final_key),
                    "temporally_eligible": reason is EligibilityReason.ELIGIBLE,
                    "eligibility_reason": reason.value,
                    "eligibility_contract_version": self._contract_version,
                }
            )
            parsed[ordinal] = {
                "row": row,
                "segments": segments,
                "research_as_of": research_as_of,
                "snapshot_key": snapshot_key,
                "terminal_key": terminal_key,
                "final_key": final_key,
                "reason": reason,
            }

        audit = _typed_audit(pd.DataFrame(audit_rows, columns=_AUDIT_COLUMNS))
        self._validate_duplicate_integrity(parsed)
        selected = self._select(parsed)
        return TemporalEligibilityResult(
            temporal_eligibility_audit=audit,
            selected_mature_samples=selected,
        )

    def _validate_duplicate_integrity(self, parsed: dict[int, dict]) -> None:
        by_factual: dict[str, str] = {}
        by_decision: dict[tuple[str, int, str], set[str]] = {}
        for item in parsed.values():
            row = item["row"]
            factual = row["factual_outcome_id"]
            if _is_missing(factual):
                continue
            factual_id = str(factual)
            consistency = canonical_sha256(
                domain="ELIGIBILITY_FACTUAL_CONSISTENCY_V1",
                payload=self._factual_consistency_payload(row, item["segments"]),
            )
            previous = by_factual.setdefault(factual_id, consistency)
            if previous != consistency:
                raise EligibilityDataError("conflicting duplicate factual_outcome_id")
            if item["reason"] is EligibilityReason.ELIGIBLE:
                key = (
                    str(row["decision_snapshot_hash"]),
                    _strict_int(row["hypothesis_id"], "hypothesis_id"),
                    str(row["snapshot_type"]),
                )
                by_decision.setdefault(key, set()).add(factual_id)
        if any(len(factual_ids) > 1 for factual_ids in by_decision.values()):
            raise EligibilityDataError("multiple factual outcomes for one decision snapshot")

    def _select(self, parsed: dict[int, dict]) -> pd.DataFrame:
        groups: dict[tuple[str, int, str, str], list[tuple[int, dict]]] = {}
        for ordinal, item in parsed.items():
            if item["reason"] is not EligibilityReason.ELIGIBLE:
                continue
            row = item["row"]
            key = (
                str(row["decision_snapshot_hash"]),
                _strict_int(row["hypothesis_id"], "hypothesis_id"),
                str(row["snapshot_type"]),
                str(row["factual_outcome_id"]),
            )
            groups.setdefault(key, []).append((ordinal, item))

        selected_rows: list[dict] = []
        for group_key in sorted(groups):
            candidates = groups[group_key]
            chosen_ordinal, chosen = min(
                candidates,
                key=lambda pair: (
                    pair[1]["research_as_of"],
                    str(pair[1]["row"]["research_snapshot_id"]),
                ),
            )
            row = chosen["row"]
            final_key = chosen["final_key"]
            snapshot_key = chosen["snapshot_key"]
            selected_rows.append(
                {
                    "selected_research_snapshot_id": row["research_snapshot_id"],
                    "selected_input_row_ordinal": chosen_ordinal,
                    "factual_outcome_id": row["factual_outcome_id"],
                    "decision_snapshot_hash": row["decision_snapshot_hash"],
                    "hypothesis_id": row["hypothesis_id"],
                    "hypothesis_type": row["hypothesis_type"],
                    "snapshot_type": row["snapshot_type"],
                    "narrative_terminal_state": row["narrative_terminal_state"],
                    **_key_fields(
                        "final_outcome_known", final_key, include_timeline=True
                    ),
                    **_key_fields(
                        "label_information_start_exclusive",
                        snapshot_key,
                        include_timeline=True,
                    ),
                    **_key_fields(
                        "label_information_end_inclusive",
                        final_key,
                        include_timeline=True,
                    ),
                    "eligibility_contract_version": self._contract_version,
                }
            )
        return _typed_selected(
            pd.DataFrame(selected_rows, columns=_SELECTED_COLUMNS)
        )


def eligibility_manifest() -> pd.DataFrame:
    rows = [
        {
            "record_type": "AUDIT_COLUMN",
            "name": column,
            "value": "TEMPORAL_LEGALITY_ONLY",
            "serialization_order": order,
        }
        for order, column in enumerate(_AUDIT_COLUMNS)
    ]
    offset = len(rows)
    rows.extend(
        {
            "record_type": "SELECTED_COLUMN",
            "name": column,
            "value": "DEDUPLICATED_MATURE_IDENTITY_ONLY",
            "serialization_order": offset + order,
        }
        for order, column in enumerate(_SELECTED_COLUMNS)
    )
    return pd.DataFrame(
        rows,
        columns=("record_type", "name", "value", "serialization_order"),
    )

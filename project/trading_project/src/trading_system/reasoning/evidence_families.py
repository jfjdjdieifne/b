"""Module 6.2B-0 V1.2: factual evidence-family reasoning without scoring."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
import math
from typing import Final

import numpy as np
import pandas as pd

from trading_system.decision.evidence_vector import V1_CATALOG
from trading_system.decision.narrative import HypothesisType, RelationshipBearing
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import InformationKey, InformationPhase
from trading_system.research.manifest_identity import (
    ManifestIdentityError,
    validate_feature_manifest_identity,
    validate_narrative_manifest_identity,
)


class ReasoningContractError(Exception):
    """Reasoning snapshot, semantic, provenance, or schema violation."""


class EvidenceFamily(Enum):
    STRUCTURAL_HYPOTHESIS = "STRUCTURAL_HYPOTHESIS"
    LOCAL_STRUCTURE_STATE = "LOCAL_STRUCTURE_STATE"
    MULTISCALE_STRUCTURE = "MULTISCALE_STRUCTURE"
    LIQUIDITY_INTERACTION = "LIQUIDITY_INTERACTION"
    DEALING_RANGE_GEOMETRY = "DEALING_RANGE_GEOMETRY"
    DISPLACEMENT_GEOMETRY = "DISPLACEMENT_GEOMETRY"
    ACTUAL_FLOW_DIRECTION = "ACTUAL_FLOW_DIRECTION"
    ACTUAL_FLOW_RESPONSE = "ACTUAL_FLOW_RESPONSE"
    PROXY_PRESSURE_DIRECTION = "PROXY_PRESSURE_DIRECTION"
    PROXY_PRESSURE_RESPONSE = "PROXY_PRESSURE_RESPONSE"
    VOLATILITY_CONTEXT = "VOLATILITY_CONTEXT"
    TEMPORAL_CONTEXT = "TEMPORAL_CONTEXT"
    OB_GEOMETRY = "OB_GEOMETRY"
    FVG_GEOMETRY = "FVG_GEOMETRY"
    DATA_AVAILABILITY = "DATA_AVAILABILITY"


class SemanticState(Enum):
    SUPPORT = "SUPPORT"
    OPPOSITION = "OPPOSITION"
    CONTRADICTION = "CONTRADICTION"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    FACTUAL = "FACTUAL"
    CONTEXTUAL = "CONTEXTUAL"
    QUALIFYING = "QUALIFYING"
    ALIGNED = "ALIGNED"
    CONFLICT = "CONFLICT"
    MIXED = "MIXED"


class ProvenanceStatus(Enum):
    CERTIFIED_SHARED_PROVENANCE = "CERTIFIED_SHARED_PROVENANCE"
    CERTIFIED_DISTINCT_PROVENANCE = "CERTIFIED_DISTINCT_PROVENANCE"
    NOT_CERTIFIED = "NOT_CERTIFIED"


class DerivationStatus(Enum):
    DETERMINISTIC_DERIVATIVE = "DETERMINISTIC_DERIVATIVE"
    NOT_DETERMINISTICALLY_DERIVED = "NOT_DETERMINISTICALLY_DERIVED"
    NOT_CERTIFIED = "NOT_CERTIFIED"


class AvailabilityState(Enum):
    AVAILABLE = "AVAILABLE"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


def resolve_provenance_status(
    *, certified_shared: bool, certified_distinct: bool
) -> ProvenanceStatus:
    """Resolve explicit provenance proofs without a closed-world fallback."""
    if not isinstance(certified_shared, bool) or not isinstance(certified_distinct, bool):
        raise ReasoningContractError("provenance proof flags must be bool")
    if certified_shared and certified_distinct:
        raise ReasoningContractError("contradictory provenance certifications")
    if certified_shared:
        return ProvenanceStatus.CERTIFIED_SHARED_PROVENANCE
    if certified_distinct:
        return ProvenanceStatus.CERTIFIED_DISTINCT_PROVENANCE
    return ProvenanceStatus.NOT_CERTIFIED


REASONING_CONTRACT_VERSION: Final = "DYNAMIC_EVIDENCE_FAMILY_REASONING_V1_2"
_REFERENCE_PRICE_SOURCE: Final = "CREATION_ROW_COMPLETED_CLOSE_RESEARCH_REFERENCE_MARK"
_ANALYTICAL_SEQUENCE: Final = 1
_SUMMARY_COLUMNS: Final = (
    "ev__evidence_feature_count",
    "ev__evidence_available_count",
    "ev__evidence_availability_fraction",
)

_FAMILY_AXIS: Final = {
    EvidenceFamily.STRUCTURAL_HYPOTHESIS: "STRUCTURAL_FOUNDATION",
    EvidenceFamily.LOCAL_STRUCTURE_STATE: "STRUCTURE_DIRECTION",
    EvidenceFamily.MULTISCALE_STRUCTURE: "STRUCTURE_DIRECTION",
    EvidenceFamily.LIQUIDITY_INTERACTION: "LIQUIDITY_EVENT_CONTEXT",
    EvidenceFamily.DEALING_RANGE_GEOMETRY: "RANGE_LOCATION",
    EvidenceFamily.DISPLACEMENT_GEOMETRY: "DISPLACEMENT_CONTEXT",
    EvidenceFamily.ACTUAL_FLOW_DIRECTION: "PRICE_OR_FLOW_DIRECTION",
    EvidenceFamily.ACTUAL_FLOW_RESPONSE: "FLOW_RESPONSE_CONTEXT",
    EvidenceFamily.PROXY_PRESSURE_DIRECTION: "PRICE_OR_FLOW_DIRECTION_PROXY",
    EvidenceFamily.PROXY_PRESSURE_RESPONSE: "PRESSURE_RESPONSE_CONTEXT",
    EvidenceFamily.VOLATILITY_CONTEXT: "VOLATILITY_CONTEXT",
    EvidenceFamily.TEMPORAL_CONTEXT: "TEMPORAL_CONTEXT",
    EvidenceFamily.OB_GEOMETRY: "OB_CANDIDATE_GEOMETRY",
    EvidenceFamily.FVG_GEOMETRY: "FVG_CANDIDATE_GEOMETRY",
    EvidenceFamily.DATA_AVAILABILITY: "DATA_AVAILABILITY",
}

_RELATIONSHIP_FAMILY = {
    "LOCAL_STRUCTURAL_FOUNDATION": EvidenceFamily.STRUCTURAL_HYPOTHESIS,
    "LOCAL_STRUCTURE_STATE": EvidenceFamily.LOCAL_STRUCTURE_STATE,
    "MULTISCALE_STRUCTURE": EvidenceFamily.MULTISCALE_STRUCTURE,
    "ACTUAL_FLOW_DIRECTION": EvidenceFamily.ACTUAL_FLOW_DIRECTION,
    "ACTUAL_FLOW_RESPONSE": EvidenceFamily.ACTUAL_FLOW_RESPONSE,
    "PROXY_PRESSURE_DIRECTION": EvidenceFamily.PROXY_PRESSURE_DIRECTION,
    "PROXY_PRESSURE_RESPONSE": EvidenceFamily.PROXY_PRESSURE_RESPONSE,
    "DEALING_RANGE_GEOMETRY": EvidenceFamily.DEALING_RANGE_GEOMETRY,
    "VOLATILITY_CONTEXT": EvidenceFamily.VOLATILITY_CONTEXT,
    "TEMPORAL_CONTEXT": EvidenceFamily.TEMPORAL_CONTEXT,
    "HIGH_SIDE_LIQUIDITY_LIFECYCLE": EvidenceFamily.LIQUIDITY_INTERACTION,
    "LOW_SIDE_LIQUIDITY_LIFECYCLE": EvidenceFamily.LIQUIDITY_INTERACTION,
    "BULLISH_OB_CANDIDATE": EvidenceFamily.OB_GEOMETRY,
    "BEARISH_OB_CANDIDATE": EvidenceFamily.OB_GEOMETRY,
    "BULLISH_FVG_CANDIDATE": EvidenceFamily.FVG_GEOMETRY,
    "BEARISH_FVG_CANDIDATE": EvidenceFamily.FVG_GEOMETRY,
}

_BEARING_STATE = {
    RelationshipBearing.ALIGNS_WITH.value: SemanticState.ALIGNED,
    RelationshipBearing.DIRECTIONALLY_OPPOSES.value: SemanticState.OPPOSITION,
    RelationshipBearing.CONTRADICTS.value: SemanticState.CONTRADICTION,
    RelationshipBearing.CONTEXTUALIZES.value: SemanticState.CONTEXTUAL,
    RelationshipBearing.QUALIFIES.value: SemanticState.QUALIFYING,
    RelationshipBearing.NEUTRAL.value: SemanticState.NEUTRAL,
    RelationshipBearing.UNKNOWN.value: SemanticState.UNKNOWN,
    RelationshipBearing.NOT_APPLICABLE.value: SemanticState.UNAVAILABLE,
}

_FAMILY_COLUMNS = (
    "family_snapshot_id", "snapshot_hash", "semantic_reasoning_hash", "timeline_id",
    "decision_information_key_version", "decision_bar_position",
    "decision_event_time_utc", "decision_information_phase",
    "decision_deterministic_sequence", "decision_snapshot_hash", "hypothesis_id", "hypothesis_type",
    "hypothesis_direction", "hypothesis_state", "family_name", "semantic_axis",
    "aggregate_semantic_state", "availability_state", "conflict_present",
    "contradiction_present", "support_present", "opposition_present",
    "aligned_present", "qualifying_present", "contextual_present",
    "factual_present", "neutral_present", "unknown_present",
    "unavailable_present", "mixed_present", "record_count", "independence_cluster_count",
    "included_independent_record_count", "unknown_record_count",
    "unavailable_record_count", "source_mode_scope", "family_registry_version",
    "serialization_order",
)
_RECORD_COLUMNS = (
    "record_id", "family_snapshot_id", "family_name", "semantic_axis",
    "record_kind", "source_record_id", "observed_position", "same_row_batch_id",
    "semantic_state", "relationship_bearing", "source_mode", "epistemic_status",
    "availability_state", "provenance_group_id", "independence_cluster_id",
    "included_for_independent_calibration", "selected_provenance_representative",
    "provenance_status", "derivation_status", "independence_status",
    "exclusion_reason", "event_local",
    "primary_value_float", "primary_value_integer", "primary_value_boolean",
    "primary_value_category", "record_hash", "serialization_order",
)
_SOURCE_COLUMNS = (
    "record_id", "source_node_id", "source_feature_name", "source_output_column",
    "source_module", "source_mode", "epistemic_status", "availability_state",
    "source_value_float", "source_value_integer", "source_value_boolean",
    "source_value_category", "declared_parent_feature", "deterministic_derivative",
    "derivation_contract",
)
_EDGE_COLUMNS = (
    "parent_node_id", "child_node_id", "parent_contract_name",
    "child_contract_name", "edge_type", "family_name",
    "edge_hash", "serialization_order",
)
_SIGNATURE_COLUMNS = (
    "family_name", "availability_state", "source_mode_scope",
    "family_snapshot_id", "global_availability_signature_hash", "serialization_order",
)
_PROVENANCE_RELATION_COLUMNS = (
    "left_record_id", "right_record_id", "provenance_status",
    "derivation_status", "proof_contract", "relation_hash",
    "serialization_order",
)
_LEDGER_COLUMNS = (
    "ledger_event_id", "decision_bar_position", "family_name", "family_snapshot_id",
    "record_id", "action", "reason", "provenance_group_id",
    "independence_cluster_id", "serialization_order",
)


@dataclass(frozen=True)
class ReasoningDecisionSnapshot:
    timeline_id: str
    decision_information_key: InformationKey
    hypothesis_id: int
    evidence_row: pd.DataFrame
    feature_manifest: pd.DataFrame
    narrative_surface_row: pd.DataFrame
    observation_rows: pd.DataFrame
    hypothesis_rows: pd.DataFrame
    relationship_rows: pd.DataFrame
    relationship_sources: pd.DataFrame
    narrative_manifest: pd.DataFrame
    reference_price: float
    reference_information_key: InformationKey
    reference_index_label: object
    decision_input_slice_hash: str
    decision_snapshot_hash: str


@dataclass(frozen=True)
class EvidenceFamilyReasoningResult:
    family_snapshots: pd.DataFrame
    evidence_records: pd.DataFrame
    evidence_sources: pd.DataFrame
    lineage_edges: pd.DataFrame
    availability_signature: pd.DataFrame
    reasoning_ledger: pd.DataFrame
    provenance_relations: pd.DataFrame
    reasoning_manifest: pd.DataFrame


def _family_for_feature(name: str) -> EvidenceFamily:
    if name == "structure_state_after":
        return EvidenceFamily.LOCAL_STRUCTURE_STATE
    if name == "structural_break_event":
        return EvidenceFamily.STRUCTURAL_HYPOTHESIS
    if name.startswith("high_side_") or name.startswith("low_side_") or name.startswith("nearest_"):
        return EvidenceFamily.LIQUIDITY_INTERACTION
    if name.startswith("created_ob_displacement"):
        return EvidenceFamily.DISPLACEMENT_GEOMETRY
    if "_ob_" in f"_{name}_" or name.startswith("bullish_ob") or name.startswith("bearish_ob"):
        return EvidenceFamily.OB_GEOMETRY
    if name.startswith("created_fvg") or name.startswith("bullish_fvg") or name.startswith("bearish_fvg"):
        return EvidenceFamily.FVG_GEOMETRY
    if name.startswith("current_range") or name.startswith("current_midpoint") or name.startswith("current_discount") or name.startswith("current_premium"):
        return EvidenceFamily.DEALING_RANGE_GEOMETRY
    if name in {
        "available_scale_count", "unavailable_scale_count", "directional_scale_count",
        "availability_fraction", "directional_fraction", "directional_balance",
        "directional_consensus", "directional_conflict",
    }:
        return EvidenceFamily.MULTISCALE_STRUCTURE
    if name.startswith("delta_") or name == "delta_ratio":
        return EvidenceFamily.ACTUAL_FLOW_DIRECTION
    if name in {"actual_absorption_evidence", "absorbed_aggression_side", "opposed_response_percentile", "opposed_response_history_count"}:
        return EvidenceFamily.ACTUAL_FLOW_RESPONSE
    if name.startswith("pressure_proxy") or name.startswith("pressure_magnitude") or name == "volume_pressure_proxy":
        return EvidenceFamily.PROXY_PRESSURE_DIRECTION
    if name in {"proxy_absorption_evidence", "pressure_side", "pressure_opposed_response_percentile", "pressure_opposed_response_history_count"}:
        return EvidenceFamily.PROXY_PRESSURE_RESPONSE
    if name in {"true_range_percentile", "true_range_history_count", "normalized_tr_change", "expansion_percentile", "expansion_history_count"}:
        return EvidenceFamily.VOLATILITY_CONTEXT
    if name in {"hour_utc_sin", "hour_utc_cos", "weekday_sin", "weekday_cos"}:
        return EvidenceFamily.TEMPORAL_CONTEXT
    return EvidenceFamily.DATA_AVAILABILITY


def _family_for_relation(name: str) -> EvidenceFamily:
    try:
        return _RELATIONSHIP_FAMILY[name]
    except KeyError as exc:
        raise ReasoningContractError(f"unsupported narrative evidence family: {name}") from exc


def _availability(value, spec) -> AvailabilityState:
    if pd.isna(value):
        return AvailabilityState.UNKNOWN
    return AvailabilityState.AVAILABLE


def _typed_value(value, domain: str):
    result = {"float": np.nan, "integer": pd.NA, "boolean": pd.NA, "category": pd.NA}
    if pd.isna(value):
        return result
    if domain == "count":
        result["integer"] = int(value)
    elif domain == "bool":
        result["boolean"] = bool(value)
    elif domain in {"structure_state", "break_event", "category_side", "category_pressure"}:
        result["category"] = str(value)
    else:
        number = float(value)
        if not math.isfinite(number):
            raise ReasoningContractError("nonfinite evidence value")
        result["float"] = number
    return result


def _mode_scope(modes: set[str]) -> str:
    clean = {mode for mode in modes if mode and mode != "NONE"}
    if not clean:
        return "NONE"
    if len(clean) == 1:
        return next(iter(clean))
    return "MIXED"


def _key_fields(key: InformationKey):
    return {
        "timeline_id": key.timeline_id,
        "decision_information_key_version": key.information_key_version,
        "decision_bar_position": key.bar_position,
        "decision_event_time_utc": pd.NaT if key.event_time_utc is None else key.event_time_utc,
        "decision_information_phase": key.information_phase.value,
        "decision_deterministic_sequence": key.deterministic_sequence,
    }


# Public layered hash contract.  ``serialization_order`` is deterministic output
# bookkeeping, not evidence semantics.  Every other final record field is hash
# covered, including family_snapshot_id and the provenance/independence result.
_RECORD_HASH_EXCLUDED_FIELDS: Final = frozenset({"record_hash", "serialization_order"})
_FAMILY_HASH_EXCLUDED_FIELDS: Final = frozenset(
    {"snapshot_hash", "semantic_reasoning_hash", "decision_snapshot_hash", "serialization_order"}
)


def reasoning_record_hash_payload(record: dict) -> dict:
    """Return the V1.2 canonical hash payload for one finalized evidence record."""
    if not isinstance(record, dict) or set(record) != set(_RECORD_COLUMNS):
        raise ReasoningContractError("final evidence record hash schema mismatch")
    return {
        key: value
        for key, value in record.items()
        if key not in _RECORD_HASH_EXCLUDED_FIELDS
    }


def _family_hash_payload(family_row: dict, record_hashes: list[str]) -> dict:
    return {
        "family": {
            key: value
            for key, value in family_row.items()
            if key not in _FAMILY_HASH_EXCLUDED_FIELDS
        },
        "record_hashes": sorted(record_hashes),
    }


class _UnionFind:
    def __init__(self, items):
        self.parent = {item: item for item in items}

    def find(self, item):
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            nxt = self.parent[item]
            self.parent[item] = root
            item = nxt
        return root

    def union(self, left, right):
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        if a < b:
            self.parent[b] = a
        else:
            self.parent[a] = b


class DynamicEvidenceFamilyReasoner:
    """Stateless semantic/provenance normalization over one atomic decision snapshot."""

    def _validate(self, snapshot: ReasoningDecisionSnapshot):
        if not isinstance(snapshot, ReasoningDecisionSnapshot):
            raise ReasoningContractError("ReasoningDecisionSnapshot required")
        key = snapshot.decision_information_key
        if not isinstance(key, InformationKey) or key.timeline_id != snapshot.timeline_id:
            raise ReasoningContractError("decision InformationKey mismatch")
        if key.information_phase is not InformationPhase.COMPLETED_ROW_AVAILABLE or key.deterministic_sequence != _ANALYTICAL_SEQUENCE:
            raise ReasoningContractError("reasoning requires completed atomic analytical key")
        if isinstance(snapshot.hypothesis_id, (bool, np.bool_)) or not isinstance(snapshot.hypothesis_id, (int, np.integer)) or int(snapshot.hypothesis_id) < 0:
            raise ReasoningContractError("invalid hypothesis_id")
        try:
            validate_feature_manifest_identity(snapshot.feature_manifest)
            validate_narrative_manifest_identity(snapshot.narrative_manifest)
        except ManifestIdentityError as exc:
            raise ReasoningContractError("static manifest identity mismatch") from exc
        for name, frame in (
            ("evidence_row", snapshot.evidence_row),
            ("narrative_surface_row", snapshot.narrative_surface_row),
            ("observation_rows", snapshot.observation_rows),
            ("hypothesis_rows", snapshot.hypothesis_rows),
            ("relationship_rows", snapshot.relationship_rows),
            ("relationship_sources", snapshot.relationship_sources),
        ):
            if not isinstance(frame, pd.DataFrame) or frame.columns.has_duplicates:
                raise ReasoningContractError(f"invalid {name}")
        if len(snapshot.evidence_row) != 1 or len(snapshot.narrative_surface_row) != 1:
            raise ReasoningContractError("decision rows must be singular")
        expected = tuple(snapshot.feature_manifest["output_column"].astype(str)) + _SUMMARY_COLUMNS
        if tuple(snapshot.evidence_row.columns) != expected:
            raise ReasoningContractError("evidence row/manifest schema mismatch")
        if not snapshot.evidence_row.index.equals(snapshot.narrative_surface_row.index):
            raise ReasoningContractError("evidence/narrative row index mismatch")
        for column in snapshot.evidence_row.columns:
            series = snapshot.evidence_row[column]
            if pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_bool_dtype(series.dtype):
                values = series.to_numpy(dtype=np.float64, na_value=np.nan)
                if np.isinf(values).any():
                    raise ReasoningContractError("nonfinite evidence value")
        positioned_frames = (
            ("observation", snapshot.observation_rows, "observed_position"),
            ("hypothesis", snapshot.hypothesis_rows, "event_position"),
            ("relationship", snapshot.relationship_rows, "observed_position"),
        )
        # Causal metadata is the only content touched in this first pass.  In
        # particular, a future parent relationship rejects before any attached
        # relationship-source semantic payload is inspected.
        for row_kind, frame, position_column in positioned_frames:
            if position_column not in frame:
                raise ReasoningContractError(f"missing {position_column}")
            series = frame[position_column]
            if not pd.api.types.is_integer_dtype(series.dtype) or series.isna().any() or (series < 0).any():
                raise ReasoningContractError("invalid visible position metadata")
            if (series > key.bar_position).any():
                raise ReasoningContractError(f"future record in reasoning snapshot: {row_kind}")
        # V1.2 is deliberately narrower than an as-of ledger: every admitted
        # lifecycle, observation, and relationship row belongs to the atomic
        # hypothesis-creation batch.  Historical rows are rejected, not ignored.
        for row_kind, frame, position_column in positioned_frames:
            if (frame[position_column] < key.bar_position).any():
                raise ReasoningContractError(f"prior-row {row_kind} outside creation snapshot")
        if "observation_id" not in snapshot.observation_rows or snapshot.observation_rows["observation_id"].duplicated().any():
            raise ReasoningContractError("invalid observation identity")
        if "relationship_id" not in snapshot.relationship_rows or snapshot.relationship_rows["relationship_id"].duplicated().any():
            raise ReasoningContractError("invalid relationship identity")
        if "relationship_id" not in snapshot.relationship_sources:
            raise ReasoningContractError("relationship source parent missing")
        if not set(snapshot.relationship_sources["relationship_id"].tolist()).issubset(set(snapshot.relationship_rows["relationship_id"].tolist())):
            raise ReasoningContractError("orphan relationship source")
        source_identity_columns = [
            column
            for column in ("relationship_id", "source_feature_name", "source_output_column")
            if column in snapshot.relationship_sources.columns
        ]
        if len(source_identity_columns) != 3 or snapshot.relationship_sources.duplicated(source_identity_columns).any():
            raise ReasoningContractError("duplicate relationship source identity")

        required_observation = {
            "observation_id", "observed_position", "observation_type", "evidence_family",
            "availability_state", "source_mode", "epistemic_status",
            "primary_numeric_value", "primary_category_value", "persistence_scope",
        }
        required_relationship = {
            "relationship_id", "hypothesis_id", "observed_position", "evidence_family",
            "evidence_role", "relationship_bearing", "availability_state", "source_mode",
            "epistemic_status", "event_local", "primary_numeric_value",
            "primary_category_value",
        }
        required_source = {
            "relationship_id", "source_feature_name", "source_output_column",
            "source_module", "source_mode", "epistemic_status",
            "source_value_float", "source_value_integer", "source_value_boolean",
            "source_value_category", "source_availability_state",
        }
        if not required_observation.issubset(snapshot.observation_rows.columns):
            raise ReasoningContractError("observation schema mismatch")
        if not required_relationship.issubset(snapshot.relationship_rows.columns):
            raise ReasoningContractError("relationship schema mismatch")
        if not required_source.issubset(snapshot.relationship_sources.columns):
            raise ReasoningContractError("relationship source schema mismatch")

        # CLOSED 6.1B emits descriptive observation rows only when the observed
        # fact is AVAILABLE.  UNKNOWN/NOT_APPLICABLE are represented by feature
        # or relationship records, not by a factual observation shell.
        if not snapshot.observation_rows["availability_state"].astype(str).eq("AVAILABLE").all():
            raise ReasoningContractError("nonavailable observation is not a legal CLOSED observation")

        feature_specs = {
            str(row.feature_name): row._asdict()
            for row in snapshot.feature_manifest.itertuples(index=False)
        }
        family_definitions = snapshot.narrative_manifest[
            snapshot.narrative_manifest["record_type"] == "EVIDENCE_FAMILY"
        ].set_index("name")
        expected_availability = {
            RelationshipBearing.UNKNOWN.value: "UNKNOWN",
            RelationshipBearing.NOT_APPLICABLE.value: "NOT_APPLICABLE",
        }
        for relationship in snapshot.relationship_rows.itertuples(index=False):
            family_name = str(relationship.evidence_family)
            if family_name not in family_definitions.index:
                raise ReasoningContractError("uncertified relationship family")
            bearing = str(relationship.relationship_bearing)
            try:
                RelationshipBearing(bearing)
            except ValueError as exc:
                raise ReasoningContractError("unsupported relationship bearing") from exc
            required_availability = expected_availability.get(bearing, "AVAILABLE")
            if str(relationship.availability_state) != required_availability:
                raise ReasoningContractError("relationship bearing/availability mismatch")
            declared = family_definitions.loc[family_name, "source_features"]
            declared_names = [] if pd.isna(declared) else [x for x in str(declared).split(",") if x]
            expected_names = {name for name in declared_names if name in feature_specs}
            links = snapshot.relationship_sources[
                snapshot.relationship_sources["relationship_id"] == int(relationship.relationship_id)
            ]
            actual_names = set(links["source_feature_name"].astype(str))
            if len(links) != len(actual_names) or actual_names != expected_names:
                raise ReasoningContractError("relationship source-family integrity mismatch")
            for source in links.itertuples(index=False):
                source_name = str(source.source_feature_name)
                spec = feature_specs[source_name]
                if (
                    str(source.source_output_column) != str(spec["output_column"])
                    or str(source.source_module) != str(spec["source_module"])
                    or str(source.source_mode) != str(spec["source_mode"])
                    or str(source.epistemic_status) != str(spec["epistemic_status"])
                ):
                    raise ReasoningContractError("relationship source manifest identity mismatch")
                evidence_value = snapshot.evidence_row.iloc[0][str(spec["output_column"])]
                expected_source_availability = "UNKNOWN" if pd.isna(evidence_value) else "AVAILABLE"
                if str(source.source_availability_state) != expected_source_availability:
                    raise ReasoningContractError("relationship source availability mismatch")
                typed_columns = (
                    "source_value_float", "source_value_integer",
                    "source_value_boolean", "source_value_category",
                )
                populated = {
                    column for column in typed_columns
                    if not pd.isna(getattr(source, column))
                }
                if expected_source_availability == "UNKNOWN":
                    if populated:
                        raise ReasoningContractError("unknown relationship source carries a value")
                else:
                    domain = str(spec["expected_domain"])
                    expected_column = (
                        "source_value_integer" if domain == "count"
                        else "source_value_boolean" if domain == "bool"
                        else "source_value_category" if domain in {
                            "structure_state", "break_event", "category_side", "category_pressure"
                        }
                        else "source_value_float"
                    )
                    if populated != {expected_column}:
                        raise ReasoningContractError("relationship source typed-value mismatch")
                    actual_value = getattr(source, expected_column)
                    if expected_column == "source_value_float":
                        equal_value = float(actual_value) == float(evidence_value)
                    elif expected_column == "source_value_integer":
                        equal_value = int(actual_value) == int(evidence_value)
                    elif expected_column == "source_value_boolean":
                        equal_value = bool(actual_value) == bool(evidence_value)
                    else:
                        equal_value = str(actual_value) == str(evidence_value)
                    if not equal_value:
                        raise ReasoningContractError("relationship source/evidence value mismatch")

        created = snapshot.hypothesis_rows[
            (snapshot.hypothesis_rows["hypothesis_id"] == int(snapshot.hypothesis_id))
            & (snapshot.hypothesis_rows["ledger_event_type"] == "CREATED")
        ]
        if len(created) != 1:
            raise ReasoningContractError("exactly one visible hypothesis creation required")
        if str(created.iloc[0]["new_state"]) != "MONITORING" or not pd.isna(created.iloc[0]["previous_state"]):
            raise ReasoningContractError("invalid CREATED lifecycle state")
        created_position = int(created.iloc[0]["event_position"])
        if created_position != key.bar_position:
            raise ReasoningContractError("V1 supports creation snapshot reasoning only")
        same_hypothesis_rows = snapshot.hypothesis_rows[
            snapshot.hypothesis_rows["hypothesis_id"] == int(snapshot.hypothesis_id)
        ]
        if len(same_hypothesis_rows) != 1:
            raise ReasoningContractError("malformed same-row hypothesis lifecycle")
        relationships = snapshot.relationship_rows[
            snapshot.relationship_rows["hypothesis_id"] == int(snapshot.hypothesis_id)
        ]
        if len(relationships) != len(snapshot.relationship_rows):
            raise ReasoningContractError("foreign hypothesis relationship")
        foundation_id = int(created.iloc[0]["trigger_relationship_id"])
        foundation = relationships[relationships["relationship_id"] == foundation_id]
        if len(foundation) != 1 or str(foundation.iloc[0]["evidence_role"]) != "FOUNDATION":
            raise ReasoningContractError("hypothesis foundation missing")
        try:
            hypothesis_type = HypothesisType(str(foundation.iloc[0]["primary_category_value"]))
        except ValueError as exc:
            raise ReasoningContractError("invalid hypothesis type") from exc
        definition = snapshot.narrative_manifest[
            (snapshot.narrative_manifest["record_type"] == "HYPOTHESIS_DEFINITION")
            & (snapshot.narrative_manifest["name"] == hypothesis_type.value)
        ]
        if len(definition) != 1:
            raise ReasoningContractError("hypothesis definition missing")
        direction = str(definition.iloc[0]["direction"])
        if not isinstance(snapshot.reference_information_key, InformationKey):
            raise ReasoningContractError("reference InformationKey required")
        if snapshot.reference_information_key.timeline_id != snapshot.timeline_id:
            raise ReasoningContractError("reference timeline mismatch")
        if not snapshot.reference_information_key <= key:
            raise ReasoningContractError("reference unavailable at decision")
        if not np.isfinite(snapshot.reference_price) or snapshot.reference_price <= 0:
            raise ReasoningContractError("reference price must be positive finite")
        feature_manifest_hash = canonical_sha256(
            domain="FEATURE_MANIFEST_V1", payload=snapshot.feature_manifest
        )
        narrative_manifest_hash = canonical_sha256(
            domain="NARRATIVE_MANIFEST_V1", payload=snapshot.narrative_manifest
        )
        reference_identity = {
            "timeline_id": snapshot.timeline_id,
            "created_position": key.bar_position,
            "index_label": snapshot.reference_index_label,
            "reference_price": snapshot.reference_price,
            "reference_price_source": _REFERENCE_PRICE_SOURCE,
            "reference_is_execution_price": False,
            "reference_key": snapshot.reference_information_key,
        }
        expected_input_hash = canonical_sha256(
            domain="DECISION_INPUT_SLICE_V1_2", payload=reference_identity
        )
        if expected_input_hash != snapshot.decision_input_slice_hash:
            raise ReasoningContractError("decision input slice hash mismatch")
        expected_snapshot_hash = canonical_sha256(
            domain="HYPOTHESIS_CREATION_DECISION_SNAPSHOT_V1_2",
            payload={
                "timeline_id": snapshot.timeline_id,
                "hypothesis_id": int(snapshot.hypothesis_id),
                "snapshot_type": "HYPOTHESIS_CREATION_SNAPSHOT",
                "creation_key": key,
                "evidence_row": snapshot.evidence_row,
                "narrative_row": snapshot.narrative_surface_row,
                "created_ledger_event": snapshot.hypothesis_rows,
                "same_row_observations": snapshot.observation_rows,
                "same_hypothesis_same_row_relationships": snapshot.relationship_rows,
                "same_row_relationship_sources": snapshot.relationship_sources,
                "feature_manifest_hash": feature_manifest_hash,
                "narrative_manifest_hash": narrative_manifest_hash,
                "reference_identity": reference_identity,
                "decision_input_slice_hash": snapshot.decision_input_slice_hash,
            },
        )
        if expected_snapshot_hash != snapshot.decision_snapshot_hash:
            raise ReasoningContractError("decision snapshot hash mismatch")
        return hypothesis_type, direction, created_position

    def analyze(self, snapshot: ReasoningDecisionSnapshot) -> EvidenceFamilyReasoningResult:
        hypothesis_type, direction, position = self._validate(snapshot)
        manifest_by_name = {
            str(row.feature_name): row._asdict()
            for row in snapshot.feature_manifest.itertuples(index=False)
        }
        records: list[dict] = []
        sources: list[dict] = []
        edges: list[dict] = []
        ledger: list[dict] = []

        def add_record(kind, source_record_id, family, state, bearing, mode, epistemic, availability, primary, event_local, serial):
            record_id = canonical_sha256(
                domain="EVIDENCE_REASONING_RECORD_V1",
                payload={
                    "decision_key": snapshot.decision_information_key,
                    "hypothesis_id": int(snapshot.hypothesis_id),
                    "kind": kind,
                    "source_record_id": str(source_record_id),
                    "family": family.value,
                },
            )
            record = {
                "record_id": record_id,
                "family_name": family.value,
                "semantic_axis": _FAMILY_AXIS[family],
                "record_kind": kind,
                "source_record_id": str(source_record_id),
                "observed_position": position,
                "same_row_batch_id": position,
                "semantic_state": state.value,
                "relationship_bearing": bearing,
                "source_mode": mode,
                "epistemic_status": epistemic,
                "availability_state": availability.value,
                "provenance_group_id": pd.NA,
                "independence_cluster_id": pd.NA,
                "included_for_independent_calibration": False,
                "selected_provenance_representative": False,
                "provenance_status": ProvenanceStatus.NOT_CERTIFIED.value,
                "derivation_status": DerivationStatus.NOT_CERTIFIED.value,
                "independence_status": "NOT_CERTIFIED_INDEPENDENT",
                "exclusion_reason": pd.NA,
                "event_local": event_local,
                "primary_value_float": primary.get("float", np.nan),
                "primary_value_integer": primary.get("integer", pd.NA),
                "primary_value_boolean": primary.get("boolean", pd.NA),
                "primary_value_category": primary.get("category", pd.NA),
                "record_hash": pd.NA,
                "serialization_order": serial,
            }
            records.append(record)
            return record_id

        # Every certified 6.1A feature is retained as FACTUAL/UNKNOWN, never support.
        evidence = snapshot.evidence_row.iloc[0]
        for order, manifest_row in enumerate(snapshot.feature_manifest.itertuples(index=False)):
            spec = manifest_row._asdict()
            name = str(spec["feature_name"])
            output = str(spec["output_column"])
            value = evidence[output]
            availability = _availability(value, spec)
            state = SemanticState.UNKNOWN if availability is AvailabilityState.UNKNOWN else SemanticState.FACTUAL
            family = _family_for_feature(name)
            typed = _typed_value(value, str(spec["expected_domain"]))
            record_id = add_record(
                "EVIDENCE_FEATURE", name, family, state, "NONE",
                str(spec["source_mode"]), str(spec["epistemic_status"]),
                availability, typed, bool(spec["event_local"]), order,
            )
            node_id = canonical_sha256(
                domain="EVIDENCE_SOURCE_NODE_V1",
                payload={"feature": name, "position": position, "output": output},
            )
            sources.append({
                "record_id": record_id, "source_node_id": node_id,
                "source_feature_name": name, "source_output_column": output,
                "source_module": str(spec["source_module"]),
                "source_mode": str(spec["source_mode"]),
                "epistemic_status": str(spec["epistemic_status"]),
                "availability_state": availability.value,
                "source_value_float": typed["float"],
                "source_value_integer": typed["integer"],
                "source_value_boolean": typed["boolean"],
                "source_value_category": typed["category"],
                "declared_parent_feature": pd.NA,
                "deterministic_derivative": False,
                "derivation_contract": "DIRECT_CERTIFIED_SOURCE_V1_2",
            })

        # Summary availability fields remain factual DATA_AVAILABILITY records.
        for offset, column in enumerate(_SUMMARY_COLUMNS):
            value = evidence[column]
            typed = _typed_value(value, "count" if column != "ev__evidence_availability_fraction" else "unit_interval")
            availability = AvailabilityState.UNKNOWN if pd.isna(value) else AvailabilityState.AVAILABLE
            record_id = add_record(
                "EVIDENCE_SUMMARY", column, EvidenceFamily.DATA_AVAILABILITY,
                SemanticState.UNKNOWN if availability is AvailabilityState.UNKNOWN else SemanticState.FACTUAL,
                "NONE", "ANY", "FACTUAL", availability, typed, False,
                len(records) + offset,
            )
            node_id = canonical_sha256(domain="EVIDENCE_SOURCE_NODE_V1", payload={"feature": column, "position": position, "output": column})
            sources.append({
                "record_id": record_id, "source_node_id": node_id,
                "source_feature_name": column, "source_output_column": column,
                "source_module": "6.1A", "source_mode": "ANY",
                "epistemic_status": "FACTUAL", "availability_state": availability.value,
                "source_value_float": typed["float"], "source_value_integer": typed["integer"],
                "source_value_boolean": typed["boolean"], "source_value_category": typed["category"],
                "declared_parent_feature": pd.NA, "deterministic_derivative": True,
                "derivation_contract": "EVIDENCE_AVAILABILITY_SUMMARY_V1",
            })

        # Same-row narrative relationships preserve their certified bearing strength.
        current_relationships = snapshot.relationship_rows[
            snapshot.relationship_rows["observed_position"] == position
        ].sort_values(["relationship_id"], kind="stable")
        for row in current_relationships.itertuples(index=False):
            family = _family_for_relation(str(row.evidence_family))
            bearing = str(row.relationship_bearing)
            if bearing not in _BEARING_STATE:
                raise ReasoningContractError("unsupported relationship bearing")
            state = _BEARING_STATE[bearing]
            availability = (
                AvailabilityState.UNAVAILABLE if state is SemanticState.UNAVAILABLE
                else AvailabilityState.UNKNOWN if state is SemanticState.UNKNOWN
                else AvailabilityState.AVAILABLE
            )
            primary = {"float": row.primary_numeric_value, "integer": pd.NA, "boolean": pd.NA, "category": row.primary_category_value}
            record_id = add_record(
                "RELATIONSHIP", int(row.relationship_id), family, state, bearing,
                str(row.source_mode), str(row.epistemic_status), availability,
                primary, bool(row.event_local), len(records),
            )
            linked = snapshot.relationship_sources[
                snapshot.relationship_sources["relationship_id"] == int(row.relationship_id)
            ].sort_values(["source_feature_name", "source_output_column"], kind="stable")
            for source in linked.itertuples(index=False):
                source_name = str(source.source_feature_name)
                node_id = canonical_sha256(
                    domain="EVIDENCE_SOURCE_NODE_V1",
                    payload={"feature": source_name, "position": position, "output": str(source.source_output_column)},
                )
                sources.append({
                    "record_id": record_id, "source_node_id": node_id,
                    "source_feature_name": source_name,
                    "source_output_column": str(source.source_output_column),
                    "source_module": str(source.source_module),
                    "source_mode": str(source.source_mode),
                    "epistemic_status": str(source.epistemic_status),
                    "availability_state": str(source.source_availability_state),
                    "source_value_float": source.source_value_float,
                    "source_value_integer": source.source_value_integer,
                    "source_value_boolean": source.source_value_boolean,
                    "source_value_category": source.source_value_category,
                    "declared_parent_feature": pd.NA,
                    "deterministic_derivative": False,
                    "derivation_contract": "NARRATIVE_RELATIONSHIP_VIEW_V1",
                })

        # Same-row observations remain factual observations, never predictive support.
        current_observations = snapshot.observation_rows[
            snapshot.observation_rows["observed_position"] == position
        ].sort_values(["observation_id"], kind="stable")
        observation_defs = snapshot.narrative_manifest[
            snapshot.narrative_manifest["record_type"] == "OBSERVATION_DEFINITION"
        ].set_index("name")
        for row in current_observations.itertuples(index=False):
            raw_family = str(row.evidence_family)
            family = _family_for_relation(raw_family)
            availability = AvailabilityState.AVAILABLE if str(row.availability_state) == "AVAILABLE" else AvailabilityState.UNKNOWN
            primary = {"float": row.primary_numeric_value, "integer": pd.NA, "boolean": pd.NA, "category": row.primary_category_value}
            record_id = add_record(
                "OBSERVATION", int(row.observation_id), family, SemanticState.FACTUAL,
                "NONE", str(row.source_mode), str(row.epistemic_status), availability,
                primary, str(row.persistence_scope) == "EVENT_SCOPED", len(records),
            )
            definition = observation_defs.loc[str(row.observation_type)]
            declared = [] if pd.isna(definition["source_features"]) else [x for x in str(definition["source_features"]).split(",") if x]
            for source_name in declared:
                spec = manifest_by_name.get(source_name)
                output = None if spec is None else str(spec["output_column"])
                node_id = canonical_sha256(
                    domain="EVIDENCE_SOURCE_NODE_V1",
                    payload={"feature": source_name, "position": position, "output": output or "UNREGISTERED"},
                )
                sources.append({
                    "record_id": record_id, "source_node_id": node_id,
                    "source_feature_name": source_name,
                    "source_output_column": output or pd.NA,
                    "source_module": pd.NA if spec is None else str(spec["source_module"]),
                    "source_mode": str(row.source_mode),
                    "epistemic_status": str(row.epistemic_status),
                    "availability_state": availability.value,
                    "source_value_float": np.nan, "source_value_integer": pd.NA,
                    "source_value_boolean": pd.NA, "source_value_category": pd.NA,
                    "declared_parent_feature": source_name,
                    "deterministic_derivative": True,
                    "derivation_contract": "NARRATIVE_OBSERVATION_VIEW_V1",
                })

        # V1.2 lineage is formula-faithful.  It distinguishes specification
        # universe, value/missingness inputs, direct deterministic derivation,
        # and common-input co-derivation.  Node order and field-name similarity
        # never create a dependency.
        feature_record = {
            str(r["source_record_id"]): str(r["record_id"])
            for r in records if r["record_kind"] == "EVIDENCE_FEATURE"
        }
        summary_record = {
            str(r["source_record_id"]): str(r["record_id"])
            for r in records if r["record_kind"] == "EVIDENCE_SUMMARY"
        }
        record_by_id = {record["record_id"]: record for record in records}
        source_nodes_by_record = {}
        source_name_by_node = {}
        for source in sources:
            source_nodes_by_record.setdefault(source["record_id"], []).append(source["source_node_id"])
            source_name_by_node[source["source_node_id"]] = str(source["source_feature_name"])

        def contract_node(name: str) -> str:
            return canonical_sha256(
                domain="EVIDENCE_LINEAGE_CONTRACT_NODE_V1_2",
                payload={"decision_key": snapshot.decision_information_key, "name": name},
            )

        def record_node(record_id: str) -> str:
            return source_nodes_by_record[record_id][0]

        node_name = dict(source_name_by_node)

        def add_edge(parent_node, child_node, parent_name, child_name, edge_type, family_name):
            node_name.setdefault(parent_node, parent_name)
            node_name.setdefault(child_node, child_name)
            edge = {
                "parent_node_id": parent_node,
                "child_node_id": child_node,
                "parent_contract_name": parent_name,
                "child_contract_name": child_name,
                "edge_type": edge_type,
                "family_name": family_name,
                "serialization_order": len(edges),
            }
            edge["edge_hash"] = canonical_sha256(
                domain="EVIDENCE_LINEAGE_EDGE_V1_2", payload=edge
            )
            edges.append(edge)

        # Manifest support-count metadata is a dependency association, not a
        # deterministic value formula and not proof of shared provenance.
        for spec in manifest_by_name.values():
            child = str(spec["feature_name"])
            parent = spec["support_column"]
            if parent is None or pd.isna(parent) or child not in feature_record or str(parent) not in feature_record:
                continue
            parent_record = feature_record[str(parent)]
            child_record = feature_record[child]
            add_edge(
                record_node(parent_record), record_node(child_record),
                str(parent), child, "SUPPORT_COUNT_FOR",
                record_by_id[child_record]["family_name"],
            )

        # CLOSED 6.1A summary formulas (evidence_vector.py):
        #   feature_count = number of selected non-COUNT_SUPPORT specs;
        #   available_count = sum(notna(value)) over those decision specs;
        #   fraction = available_count / feature_count (or NaN when zero).
        feature_count_id = summary_record["ev__evidence_feature_count"]
        available_count_id = summary_record["ev__evidence_available_count"]
        availability_fraction_id = summary_record["ev__evidence_availability_fraction"]
        universe_name = "6.1A::SELECTED_NON_COUNT_SUPPORT_SPECIFICATION_UNIVERSE"
        universe_node = contract_node(universe_name)
        add_edge(
            universe_node, record_node(feature_count_id), universe_name,
            "ev__evidence_feature_count", "MANIFEST_UNIVERSE_DEPENDENCY",
            EvidenceFamily.DATA_AVAILABILITY.value,
        )
        decision_feature_names = [
            str(spec["feature_name"])
            for spec in manifest_by_name.values()
            if str(spec["semantic_type"]) != "COUNT_SUPPORT"
        ]
        for feature_name in decision_feature_names:
            feature_id = feature_record[feature_name]
            add_edge(
                record_node(feature_id), record_node(available_count_id),
                feature_name, "ev__evidence_available_count",
                "AVAILABILITY_VALUE_DEPENDENCY",
                EvidenceFamily.DATA_AVAILABILITY.value,
            )
        add_edge(
            record_node(feature_count_id), record_node(availability_fraction_id),
            "ev__evidence_feature_count", "ev__evidence_availability_fraction",
            "DIRECT_DETERMINISTIC_DERIVATION", EvidenceFamily.DATA_AVAILABILITY.value,
        )
        add_edge(
            record_node(available_count_id), record_node(availability_fraction_id),
            "ev__evidence_available_count", "ev__evidence_availability_fraction",
            "DIRECT_DETERMINISTIC_DERIVATION", EvidenceFamily.DATA_AVAILABILITY.value,
        )

        # Exact CLOSED 5.2 formulas. Hidden formula inputs are explicit contract
        # nodes; they are not fabricated visible evidence values.
        formula_parents: dict[str, set[str]] = {}
        directed_record_dependencies: set[tuple[str, str]] = set()

        def formula_input(child_name: str, parent_name: str):
            if child_name not in feature_record:
                return
            child_id = feature_record[child_name]
            parent_id = feature_record.get(parent_name)
            if parent_id is None:
                parent_node = contract_node(f"5.2::{parent_name}")
                parent_contract = f"5.2::{parent_name}"
                edge_type = "FORMULA_INPUT_DEPENDENCY"
            else:
                parent_node = record_node(parent_id)
                parent_contract = parent_name
                edge_type = "DIRECT_DETERMINISTIC_DERIVATION"
                directed_record_dependencies.add((parent_id, child_id))
            formula_parents.setdefault(child_id, set()).add(parent_contract)
            add_edge(
                parent_node, record_node(child_id), parent_contract, child_name,
                edge_type, EvidenceFamily.MULTISCALE_STRUCTURE.value,
            )

        # available count is the sum of per-scale availability flags.
        formula_input("available_scale_count", "scale_available_vector")
        formula_input("unavailable_scale_count", "configured_scale_count")
        formula_input("unavailable_scale_count", "available_scale_count")
        formula_input("directional_scale_count", "up_structure_count")
        formula_input("directional_scale_count", "down_structure_count")
        formula_input("availability_fraction", "configured_scale_count")
        formula_input("availability_fraction", "available_scale_count")
        formula_input("directional_fraction", "configured_scale_count")
        formula_input("directional_fraction", "directional_scale_count")
        formula_input("directional_balance", "up_structure_count")
        formula_input("directional_balance", "down_structure_count")
        formula_input("directional_consensus", "directional_balance")
        formula_input("directional_conflict", "up_structure_count")
        formula_input("directional_conflict", "down_structure_count")

        # Summary direct dependencies participate in deterministic ancestry.
        directed_record_dependencies.add((feature_count_id, availability_fraction_id))
        directed_record_dependencies.add((available_count_id, availability_fraction_id))
        for feature_name in decision_feature_names:
            directed_record_dependencies.add((feature_record[feature_name], available_count_id))

        record_ids = [record["record_id"] for record in records]
        records_by_node = {}
        for source in sources:
            records_by_node.setdefault(source["source_node_id"], []).append(source["record_id"])

        def pair_key(left: str, right: str) -> tuple[str, str]:
            return tuple(sorted((left, right)))

        shared_pair_proofs: dict[tuple[str, str], set[str]] = {}
        derivative_pair_proofs: dict[tuple[str, str], set[str]] = {}

        # Exact source-node identity certifies shared provenance. A narrative
        # view is deterministically derived from that source, but multiple raw
        # sources used by one composite relationship are not made siblings by
        # transitive closure.
        for linked_records in records_by_node.values():
            unique = sorted(set(linked_records))
            for left, right in combinations(unique, 2):
                key = pair_key(left, right)
                shared_pair_proofs.setdefault(key, set()).add("EXACT_SHARED_SOURCE_NODE")
                if {record_by_id[left]["record_kind"], record_by_id[right]["record_kind"]} & {
                    "RELATIONSHIP", "OBSERVATION"
                }:
                    derivative_pair_proofs.setdefault(key, set()).add(
                        "DETERMINISTIC_VIEW_OF_SHARED_SOURCE"
                    )

        # Co-derived siblings share an explicit formula input but neither is a
        # deterministic child of the other.
        children_by_formula_parent: dict[str, list[str]] = {}
        for child_id, parents in formula_parents.items():
            for parent in parents:
                children_by_formula_parent.setdefault(parent, []).append(child_id)
        for parent, children in children_by_formula_parent.items():
            for left, right in combinations(sorted(set(children)), 2):
                shared_pair_proofs.setdefault(pair_key(left, right), set()).add(
                    f"CERTIFIED_COMMON_FORMULA_INPUT:{parent}"
                )

        # Deterministic ancestor closure follows directed formula edges only.
        adjacency: dict[str, set[str]] = {}
        for parent, child in directed_record_dependencies:
            adjacency.setdefault(parent, set()).add(child)
        for ancestor in record_ids:
            stack = list(adjacency.get(ancestor, ()))
            visited = set()
            while stack:
                descendant = stack.pop()
                if descendant in visited:
                    continue
                visited.add(descendant)
                derivative_pair_proofs.setdefault(pair_key(ancestor, descendant), set()).add(
                    "DIRECT_DETERMINISTIC_DERIVATION"
                    if descendant in adjacency.get(ancestor, set())
                    else "CERTIFIED_DETERMINISTIC_ANCESTOR"
                )
                # Deterministic ancestry is orthogonal to provenance; it does
                # not by itself certify shared or distinct provenance.
                stack.extend(adjacency.get(descendant, ()))

        # Conservative dependency clusters are not provenance assertions.
        union = _UnionFind(record_ids)
        for linked_records in records_by_node.values():
            for other in linked_records[1:]:
                union.union(linked_records[0], other)
        for edge in edges:
            if edge["edge_type"] == "SUPPORT_COUNT_FOR":
                left = next((rid for rid, nodes in source_nodes_by_record.items() if edge["parent_node_id"] in nodes), None)
                right = next((rid for rid, nodes in source_nodes_by_record.items() if edge["child_node_id"] in nodes), None)
                if left and right:
                    union.union(left, right)
        for left, right in directed_record_dependencies:
            # Many-parent 6.1A availability summaries are not equivalence
            # bridges between otherwise distinct feature records.
            if not (
                record_by_id[left]["record_kind"] == "EVIDENCE_SUMMARY"
                or record_by_id[right]["record_kind"] == "EVIDENCE_SUMMARY"
            ):
                union.union(left, right)
        for key in shared_pair_proofs:
            union.union(*key)

        clusters = {}
        for record in records:
            root = union.find(record["record_id"])
            cluster_id = canonical_sha256(
                domain="EVIDENCE_DEPENDENCY_CLUSTER_V1_2",
                payload={"decision_key": snapshot.decision_information_key, "root": root},
            )
            record["provenance_group_id"] = root
            record["independence_cluster_id"] = cluster_id
            clusters.setdefault(cluster_id, []).append(record)

        provenance_relations = []
        for record in records:
            if record["record_kind"] in {"RELATIONSHIP", "OBSERVATION", "EVIDENCE_SUMMARY"} or record["record_id"] in formula_parents:
                record["derivation_status"] = DerivationStatus.DETERMINISTIC_DERIVATIVE.value

        for order, (left, right) in enumerate(combinations(sorted(record_ids), 2)):
            key = pair_key(left, right)
            shared_proofs = shared_pair_proofs.get(key, set())
            derivative_proofs = derivative_pair_proofs.get(key, set())
            provenance_status = resolve_provenance_status(
                certified_shared=bool(shared_proofs),
                certified_distinct=False,  # no current CLOSED distinctness proof
            )
            derivation_status = (
                DerivationStatus.DETERMINISTIC_DERIVATIVE
                if derivative_proofs else DerivationStatus.NOT_CERTIFIED
            )
            if shared_proofs:
                record_by_id[left]["provenance_status"] = ProvenanceStatus.CERTIFIED_SHARED_PROVENANCE.value
                record_by_id[right]["provenance_status"] = ProvenanceStatus.CERTIFIED_SHARED_PROVENANCE.value
            proof_contract = "|".join(sorted(shared_proofs | derivative_proofs)) or "NO_CERTIFYING_CONTRACT"
            relation = {
                "left_record_id": left,
                "right_record_id": right,
                "provenance_status": provenance_status.value,
                "derivation_status": derivation_status.value,
                "proof_contract": proof_contract,
                "relation_hash": pd.NA,
                "serialization_order": order,
            }
            relation["relation_hash"] = canonical_sha256(
                domain="EVIDENCE_PROVENANCE_RELATION_V1_2",
                payload={k: v for k, v in relation.items() if k not in {"relation_hash", "serialization_order"}},
            )
            provenance_relations.append(relation)

        # Representative selection is epistemic bookkeeping, not market
        # priority.  Contradiction receives canonical representative precedence inside the
        # conservative dependency cluster; this is not a provenance claim.  Relationships precede raw duplicate views;
        # deterministic summaries are never eligible.
        state_priority = {
            SemanticState.CONTRADICTION.value: 0,
            SemanticState.OPPOSITION.value: 1,
            SemanticState.ALIGNED.value: 2,
            SemanticState.SUPPORT.value: 3,
            SemanticState.QUALIFYING.value: 4,
            SemanticState.CONTEXTUAL.value: 5,
            SemanticState.FACTUAL.value: 6,
            SemanticState.NEUTRAL.value: 7,
            SemanticState.UNKNOWN.value: 8,
            SemanticState.UNAVAILABLE.value: 9,
            SemanticState.CONFLICT.value: 10,
            SemanticState.MIXED.value: 11,
        }
        kind_priority = {
            "RELATIONSHIP": 0, "EVIDENCE_FEATURE": 1,
            "OBSERVATION": 2, "EVIDENCE_SUMMARY": 3,
        }
        for cluster_records in clusters.values():
            eligible = [r for r in cluster_records if r["record_kind"] != "EVIDENCE_SUMMARY"]
            if not eligible:
                for record in cluster_records:
                    record["included_for_independent_calibration"] = False
                    record["independence_status"] = "DETERMINISTIC_DERIVATIVE"
                    record["exclusion_reason"] = "DETERMINISTIC_DERIVATIVE_NOT_INDEPENDENT"
                continue
            representatives = sorted(
                eligible,
                key=lambda r: (
                    0 if r["semantic_state"] == SemanticState.CONTRADICTION.value else 1,
                    kind_priority[r["record_kind"]],
                    state_priority[r["semantic_state"]],
                    r["record_id"],
                ),
            )
            representative = representatives[0]
            representative["selected_provenance_representative"] = True
            representative["included_for_independent_calibration"] = False
            representative["independence_status"] = "NOT_CERTIFIED_INDEPENDENT"
            representative["exclusion_reason"] = "STATISTICAL_INDEPENDENCE_NOT_CERTIFIED"
            for record in cluster_records:
                if record is representative:
                    continue
                record["included_for_independent_calibration"] = False
                if record["record_kind"] == "EVIDENCE_SUMMARY":
                    record["independence_status"] = "DETERMINISTIC_DERIVATIVE"
                    record["exclusion_reason"] = "DETERMINISTIC_DERIVATIVE_NOT_INDEPENDENT"
                else:
                    certified_shared = (
                        record["provenance_status"]
                        == ProvenanceStatus.CERTIFIED_SHARED_PROVENANCE.value
                    )
                    record["independence_status"] = (
                        "CERTIFIED_SHARED_PROVENANCE"
                        if certified_shared else "NOT_CERTIFIED"
                    )
                    record["exclusion_reason"] = (
                        "CONTRADICTION_DOMINATES_CERTIFIED_SHARED_PROVENANCE"
                        if certified_shared
                        and representative["semantic_state"] == SemanticState.CONTRADICTION.value
                        else "CERTIFIED_SHARED_PROVENANCE_NOT_INDEPENDENT"
                        if certified_shared
                        else "PROVENANCE_NOT_CERTIFIED"
                    )

        # Production open-world invariant: no adjacent legacy field may assert
        # shared provenance when pairwise/record provenance is unresolved.
        for record in records:
            if record["provenance_status"] == ProvenanceStatus.NOT_CERTIFIED.value:
                legacy_claims = f"{record['independence_status']}|{record['exclusion_reason']}"
                if "SHARED_PROVENANCE" in legacy_claims:
                    raise ReasoningContractError(
                        "open-world provenance invariant violated"
                    )
            if record["included_for_independent_calibration"]:
                raise ReasoningContractError(
                    "V1.2 statistical independence is not certified"
                )

        # Canonical serialization is independent of caller row/list ordering.
        records.sort(key=lambda r: (r["family_name"], r["record_kind"], r["source_record_id"], r["record_id"]))
        for order, record in enumerate(records):
            record["serialization_order"] = order
        sources.sort(key=lambda s: (s["record_id"], s["source_node_id"], str(s["source_feature_name"])))
        edges.sort(key=lambda e: (e["parent_node_id"], e["child_node_id"], e["edge_type"]))
        for order, edge in enumerate(edges):
            edge["serialization_order"] = order
            edge["edge_hash"] = canonical_sha256(
                domain="EVIDENCE_LINEAGE_EDGE_V1_2",
                payload={k: v for k, v in edge.items() if k != "edge_hash"},
            )

        # Layered identity contract:
        #   1. family_snapshot_id identifies decision+hypothesis+family;
        #   2. each finalized record includes that identity and is hashed;
        #   3. family snapshot_hash covers family semantics plus its record hashes;
        #   4. semantic_reasoning_hash covers the canonical family content hashes.
        # The upstream decision_snapshot_hash remains exact storage provenance
        # and is intentionally excluded from semantic hashes.
        family_order = {family: order for order, family in enumerate(EvidenceFamily)}
        family_id_by_name = {
            family.value: canonical_sha256(
                domain="EVIDENCE_FAMILY_SNAPSHOT_ID_V1_2",
                payload={
                    "decision_key": snapshot.decision_information_key,
                    "hypothesis_id": int(snapshot.hypothesis_id),
                    "family": family.value,
                },
            )
            for family in EvidenceFamily
        }
        for record in records:
            record["family_snapshot_id"] = family_id_by_name[record["family_name"]]
        for record in records:
            record["record_hash"] = canonical_sha256(
                domain="EVIDENCE_RECORD_FINAL_V1_2",
                payload=reasoning_record_hash_payload(record),
            )

        family_rows = []
        for family in EvidenceFamily:
            family_records = [record for record in records if record["family_name"] == family.value]
            included = [record for record in family_records if record["included_for_independent_calibration"]]
            relationship_records = [
                record for record in family_records if record["record_kind"] == "RELATIONSHIP"
            ]
            aggregate_records = relationship_records if relationship_records else family_records
            aggregate_states = {record["semantic_state"] for record in aggregate_records}
            all_states = {record["semantic_state"] for record in family_records}
            if not aggregate_states:
                aggregate = SemanticState.UNAVAILABLE
            elif SemanticState.CONTRADICTION.value in aggregate_states:
                aggregate = SemanticState.CONTRADICTION
            elif (
                SemanticState.OPPOSITION.value in aggregate_states
                and ({SemanticState.ALIGNED.value, SemanticState.SUPPORT.value} & aggregate_states)
            ):
                aggregate = SemanticState.CONFLICT
            elif len(aggregate_states) == 1:
                aggregate = SemanticState(next(iter(aggregate_states)))
            else:
                aggregate = SemanticState.MIXED

            # CLOSED 5.2 conflict is an orthogonal factual dimension.  It does
            # not change directional bearing into opposition/contradiction.
            certified_mtf_conflict = family is EvidenceFamily.MULTISCALE_STRUCTURE and any(
                (
                    record["source_record_id"] == "directional_conflict"
                    and record["primary_value_boolean"] is not pd.NA
                    and bool(record["primary_value_boolean"])
                )
                or (
                    record["record_kind"] == "RELATIONSHIP"
                    and str(record["primary_value_category"]) == "CONFLICT"
                )
                for record in family_records
            )
            semantic_conflict = aggregate is SemanticState.CONFLICT or SemanticState.CONFLICT.value in all_states
            availability = (
                AvailabilityState.UNAVAILABLE if not family_records
                else AvailabilityState.AVAILABLE if any(r["availability_state"] == AvailabilityState.AVAILABLE.value for r in family_records)
                else AvailabilityState.UNKNOWN
            )
            modes = {record["source_mode"] for record in family_records}
            family_row = {
                "family_snapshot_id": family_id_by_name[family.value],
                "snapshot_hash": pd.NA,
                "semantic_reasoning_hash": pd.NA,
                **_key_fields(snapshot.decision_information_key),
                "decision_snapshot_hash": snapshot.decision_snapshot_hash,
                "hypothesis_id": int(snapshot.hypothesis_id),
                "hypothesis_type": hypothesis_type.value,
                "hypothesis_direction": direction,
                "hypothesis_state": "MONITORING",
                "family_name": family.value,
                "semantic_axis": _FAMILY_AXIS[family],
                "aggregate_semantic_state": aggregate.value,
                "availability_state": availability.value,
                "conflict_present": bool(semantic_conflict or certified_mtf_conflict),
                "contradiction_present": SemanticState.CONTRADICTION.value in all_states,
                "support_present": SemanticState.SUPPORT.value in all_states,
                "opposition_present": SemanticState.OPPOSITION.value in all_states,
                "aligned_present": SemanticState.ALIGNED.value in all_states,
                "qualifying_present": SemanticState.QUALIFYING.value in all_states,
                "contextual_present": SemanticState.CONTEXTUAL.value in all_states,
                "factual_present": SemanticState.FACTUAL.value in all_states,
                "neutral_present": SemanticState.NEUTRAL.value in all_states,
                "unknown_present": SemanticState.UNKNOWN.value in all_states,
                "unavailable_present": SemanticState.UNAVAILABLE.value in all_states,
                "mixed_present": len(all_states) > 1 or aggregate is SemanticState.MIXED,
                "record_count": len(family_records),
                "independence_cluster_count": len({r["independence_cluster_id"] for r in family_records}),
                "included_independent_record_count": len(included),
                "unknown_record_count": sum(r["semantic_state"] == SemanticState.UNKNOWN.value for r in family_records),
                "unavailable_record_count": sum(r["semantic_state"] == SemanticState.UNAVAILABLE.value for r in family_records),
                "source_mode_scope": _mode_scope(modes),
                "family_registry_version": REASONING_CONTRACT_VERSION,
                "serialization_order": family_order[family],
            }
            record_hashes = [record["record_hash"] for record in family_records]
            family_row["snapshot_hash"] = canonical_sha256(
                domain="EVIDENCE_FAMILY_SEMANTIC_SNAPSHOT_V1_2",
                payload=_family_hash_payload(family_row, record_hashes),
            )
            family_rows.append(family_row)

        semantic_reasoning_hash = canonical_sha256(
            domain="DYNAMIC_EVIDENCE_FAMILY_SEMANTIC_IDENTITY_V1_2",
            payload={
                "decision_key": snapshot.decision_information_key,
                "hypothesis_id": int(snapshot.hypothesis_id),
                "family_content_hashes": [row["snapshot_hash"] for row in family_rows],
                "provenance_relation_hashes": sorted(
                    relation["relation_hash"] for relation in provenance_relations
                ),
            },
        )
        for family_row in family_rows:
            family_row["semantic_reasoning_hash"] = semantic_reasoning_hash

        for order, record in enumerate(sorted(records, key=lambda r: (family_order[EvidenceFamily(r["family_name"])], r["record_kind"], r["record_id"]))):
            action = (
                "PROVENANCE_REPRESENTATIVE_NOT_CERTIFIED_INDEPENDENT"
                if record["selected_provenance_representative"]
                else "GROUPED_NOT_INDEPENDENT"
            )
            ledger.append({
                "ledger_event_id": order, "decision_bar_position": position,
                "family_name": record["family_name"], "family_snapshot_id": record["family_snapshot_id"],
                "record_id": record["record_id"], "action": action,
                "reason": record["exclusion_reason"],
                "provenance_group_id": record["provenance_group_id"],
                "independence_cluster_id": record["independence_cluster_id"],
                "serialization_order": order,
            })
        for family_row in family_rows:
            if family_row["availability_state"] == AvailabilityState.UNAVAILABLE.value:
                order = len(ledger)
                ledger.append({
                    "ledger_event_id": order, "decision_bar_position": position,
                    "family_name": family_row["family_name"], "family_snapshot_id": family_row["family_snapshot_id"],
                    "record_id": pd.NA, "action": "FAMILY_UNAVAILABLE",
                    "reason": "NO_CERTIFIED_VISIBLE_SOURCE", "provenance_group_id": pd.NA,
                    "independence_cluster_id": pd.NA, "serialization_order": order,
                })

        global_signature = canonical_sha256(domain="EVIDENCE_AVAILABILITY_SIGNATURE_V1", payload=[{"family": row["family_name"], "availability": row["availability_state"], "mode": row["source_mode_scope"]} for row in family_rows])
        signatures = [
            {
                "family_name": row["family_name"], "availability_state": row["availability_state"],
                "source_mode_scope": row["source_mode_scope"], "family_snapshot_id": row["family_snapshot_id"],
                "global_availability_signature_hash": global_signature,
                "serialization_order": row["serialization_order"],
            }
            for row in family_rows
        ]

        return _typed_result(
            family_rows, records, sources, edges, signatures, ledger,
            provenance_relations,
        )


def _typed_result(family_rows, records, sources, edges, signatures, ledger, provenance_relations):
    family = pd.DataFrame(family_rows, columns=_FAMILY_COLUMNS)
    record = pd.DataFrame(records, columns=_RECORD_COLUMNS)
    source = pd.DataFrame(sources, columns=_SOURCE_COLUMNS)
    edge = pd.DataFrame(edges, columns=_EDGE_COLUMNS)
    signature = pd.DataFrame(signatures, columns=_SIGNATURE_COLUMNS)
    ledger_frame = pd.DataFrame(ledger, columns=_LEDGER_COLUMNS)
    provenance_frame = pd.DataFrame(provenance_relations, columns=_PROVENANCE_RELATION_COLUMNS)
    for frame in (family, record, source, edge, signature, ledger_frame, provenance_frame):
        for column in frame.columns:
            if column.endswith("_event_time_utc"):
                frame[column] = pd.to_datetime(frame[column], utc=True)
            elif column in {"hypothesis_id", "decision_bar_position", "decision_deterministic_sequence", "observed_position", "same_row_batch_id", "serialization_order", "record_count", "independence_cluster_count", "included_independent_record_count", "unknown_record_count", "unavailable_record_count", "ledger_event_id", "source_value_integer", "primary_value_integer"}:
                frame[column] = pd.array(frame[column], dtype="Int64")
            elif column in {"conflict_present", "contradiction_present", "support_present", "opposition_present", "aligned_present", "qualifying_present", "contextual_present", "factual_present", "neutral_present", "unknown_present", "unavailable_present", "mixed_present", "included_for_independent_calibration", "selected_provenance_representative", "event_local", "source_value_boolean", "primary_value_boolean", "deterministic_derivative"}:
                frame[column] = pd.array(frame[column], dtype="boolean")
            elif column in {"source_value_float", "primary_value_float"}:
                frame[column] = pd.array(frame[column], dtype="Float64")
            else:
                frame[column] = pd.array(frame[column], dtype="string")
    return EvidenceFamilyReasoningResult(
        family_snapshots=family,
        evidence_records=record,
        evidence_sources=source,
        lineage_edges=edge,
        availability_signature=signature,
        reasoning_ledger=ledger_frame,
        provenance_relations=provenance_frame,
        reasoning_manifest=reasoning_contract_manifest(),
    )


def reasoning_contract_manifest() -> pd.DataFrame:
    rows = []
    order = 0
    for family in EvidenceFamily:
        rows.append({"record_type": "FAMILY", "name": family.value, "value": _FAMILY_AXIS[family], "serialization_order": order}); order += 1
    for bearing, state in _BEARING_STATE.items():
        rows.append({"record_type": "BEARING_MAPPING", "name": bearing, "value": state.value, "serialization_order": order}); order += 1
    for state in SemanticState:
        rows.append({"record_type": "SEMANTIC_STATE", "name": state.value, "value": "EXPLICIT_NONCOLLAPSING_STATE", "serialization_order": order}); order += 1
    for state in ProvenanceStatus:
        rows.append({"record_type": "PROVENANCE_STATUS", "name": state.value, "value": "EXPLICIT_OPEN_WORLD_STATE", "serialization_order": order}); order += 1
    for state in DerivationStatus:
        rows.append({"record_type": "DERIVATION_STATUS", "name": state.value, "value": "ORTHOGONAL_TO_PROVENANCE", "serialization_order": order}); order += 1
    rows.append({"record_type": "SUPPORT_POLICY", "name": "DIRECT_SUPPORT", "value": "NO_CURRENT_CLOSED_SOURCE_MAPPING", "serialization_order": order}); order += 1
    rows.append({"record_type": "MISSINGNESS_POLICY", "name": "LIVE_RENORMALIZATION", "value": "FORBIDDEN", "serialization_order": order}); order += 1
    rows.append({"record_type": "AGGREGATE_POLICY", "name": "ORTHOGONAL_STATE_FLAGS", "value": "PRESERVE_ALL_RECORD_STATES", "serialization_order": order}); order += 1
    rows.append({"record_type": "AGGREGATE_POLICY", "name": "MULTIPLE_NONTERMINAL_STATES", "value": "MIXED_NO_MARKET_PRIORITY", "serialization_order": order}); order += 1
    rows.append({"record_type": "AGGREGATE_POLICY", "name": "CERTIFIED_CONTRADICTION", "value": "LOGICAL_PRECEDENCE_WITH_ORTHOGONAL_FLAGS_RETAINED", "serialization_order": order}); order += 1
    rows.append({"record_type": "AGGREGATE_POLICY", "name": "CERTIFIED_MTF_CONFLICT", "value": "ORTHOGONAL_FACT_NOT_OPPOSITION_OR_CONTRADICTION", "serialization_order": order}); order += 1
    rows.append({"record_type": "REPRESENTATIVE_POLICY", "name": "PURPOSE", "value": "SELECT_CANONICAL_DEPENDENCY_CLUSTER_VIEW_NOT_PROVENANCE_OR_MARKET_PRIORITY", "serialization_order": order}); order += 1
    rows.append({"record_type": "REPRESENTATIVE_POLICY", "name": "SELECTION", "value": "DEPENDENCY_CLUSTER_CONTRADICTION_THEN_RELATIONSHIP_THEN_FEATURE_THEN_OBSERVATION", "serialization_order": order}); order += 1
    rows.append({"record_type": "INDEPENDENCE_POLICY", "name": "STATISTICAL_INDEPENDENCE", "value": "NOT_CERTIFIED_BY_PROVENANCE_UNIQUENESS", "serialization_order": order}); order += 1
    rows.append({"record_type": "INDEPENDENCE_POLICY", "name": "INCLUDED_FOR_INDEPENDENT_CALIBRATION", "value": "FALSE_UNLESS_EXPLICIT_FUTURE_CERTIFICATION", "serialization_order": order}); order += 1
    rows.append({"record_type": "INDEPENDENCE_POLICY", "name": "DETERMINISTIC_DERIVATIVE", "value": "EXCLUDED_BUT_FACT_RETAINED", "serialization_order": order}); order += 1
    rows.append({"record_type": "LINEAGE_POLICY", "name": "6.1A_AVAILABILITY", "value": "MANIFEST_UNIVERSE_VALUE_MISSINGNESS_AND_DIRECT_SUMMARY_FORMULAS", "serialization_order": order}); order += 1
    rows.append({"record_type": "LINEAGE_POLICY", "name": "5.2_MTF", "value": "CLOSED_FORMULA_DAG_NOT_MANIFEST_ORDER", "serialization_order": order}); order += 1
    rows.append({"record_type": "LINEAGE_POLICY", "name": "CO_DERIVED_SIBLINGS", "value": "SHARED_INPUT_DOES_NOT_IMPLY_DIRECTIONAL_DERIVATION", "serialization_order": order}); order += 1
    rows.append({"record_type": "LINEAGE_POLICY", "name": "ABSENT_DERIVATION_PROOF", "value": "NOT_CERTIFIED", "serialization_order": order}); order += 1
    rows.append({"record_type": "HASH_POLICY", "name": "UPSTREAM_DECISION_SNAPSHOT_HASH", "value": "EXACT_STORAGE_INTEGRITY_PROVENANCE_NOT_ORIGIN_AUTHENTICATION", "serialization_order": order}); order += 1
    rows.append({"record_type": "HASH_POLICY", "name": "RECORD_HASH", "value": "ALL_FINAL_FIELDS_EXCEPT_RECORD_HASH_AND_SERIALIZATION_ORDER", "serialization_order": order}); order += 1
    rows.append({"record_type": "HASH_POLICY", "name": "FAMILY_SNAPSHOT_HASH", "value": "CANONICAL_SEMANTIC_CONTENT_AND_FINAL_RECORD_HASHES", "serialization_order": order}); order += 1
    rows.append({"record_type": "HASH_POLICY", "name": "PROVENANCE_RELATION_HASH", "value": "PAIRWISE_PROVENANCE_AND_DERIVATION_PROOF_CONTENT", "serialization_order": order}); order += 1
    rows.append({"record_type": "HASH_POLICY", "name": "SEMANTIC_REASONING_HASH", "value": "ORDER_INVARIANT_FAMILY_AND_PROVENANCE_CONTENT", "serialization_order": order}); order += 1
    rows.append({"record_type": "SCORING_POLICY", "name": "CONFLUENCE_SCORE", "value": "NOT_IMPLEMENTED", "serialization_order": order})
    return pd.DataFrame(rows, columns=("record_type", "name", "value", "serialization_order"))

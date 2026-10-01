"""Layer 6 — Module 6.1B: Causal Market Narrative / Hypothesis Engine V1.2.

Minimal structural hypotheses over a certified 6.1A evidence surface. This
module emits observations, descriptive relationships, and append-only lifecycle
records. It produces no score, weight, probability, trade signal, or outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Optional
import numpy as np
import pandas as pd

from trading_system.decision.evidence_vector import GROUPS, V1_CATALOG


class NarrativeError(Exception):
    pass


class NarrativeDataError(NarrativeError):
    pass


class HypothesisType(Enum):
    UPWARD_CONTINUATION_AFTER_PROJECT_BREAK = "UPWARD_CONTINUATION_AFTER_PROJECT_BREAK"
    DOWNWARD_CONTINUATION_AFTER_PROJECT_BREAK = "DOWNWARD_CONTINUATION_AFTER_PROJECT_BREAK"
    UPWARD_TRANSITION_AFTER_PROJECT_SHIFT = "UPWARD_TRANSITION_AFTER_PROJECT_SHIFT"
    DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT = "DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT"


class HypothesisState(Enum):
    MONITORING = "MONITORING"
    OBSERVED_DIRECTION_ESTABLISHED = "OBSERVED_DIRECTION_ESTABLISHED"
    CONTRADICTED = "CONTRADICTED"
    SUPERSEDED = "SUPERSEDED"


class RelationshipBearing(Enum):
    ALIGNS_WITH = "ALIGNS_WITH"
    DIRECTIONALLY_OPPOSES = "DIRECTIONALLY_OPPOSES"
    CONTRADICTS = "CONTRADICTS"
    CONTEXTUALIZES = "CONTEXTUALIZES"
    QUALIFIES = "QUALIFIES"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class NarrativeResult:
    narrative_surface: pd.DataFrame
    observation_ledger: pd.DataFrame
    active_hypotheses: pd.DataFrame
    hypothesis_ledger: pd.DataFrame
    relationship_ledger: pd.DataFrame
    relationship_sources: pd.DataFrame
    narrative_manifest: pd.DataFrame


@dataclass
class _Hypothesis:
    hypothesis_id: int
    hypothesis_type: HypothesisType
    created_position: int
    current_state: HypothesisState
    direction: str
    foundation_relationship_id: int
    source_mode: str
    epistemic_status: str = "PROJECT_OPERATIONAL"


_HYPOTHESIS_DEFINITIONS: Final = (
    {
        "name": HypothesisType.UPWARD_CONTINUATION_AFTER_PROJECT_BREAK.value,
        "direction": "UP",
        "foundation": "UP_STRUCTURE_AND_BOS_UP",
        "persistence": "STRUCTURE_SCOPED",
        "resolution": "NONE_IN_V1",
        "contradiction": "DOWN_STRUCTURE",
        "supersession": "NEW_SAME_TYPE_FOUNDATION",
    },
    {
        "name": HypothesisType.DOWNWARD_CONTINUATION_AFTER_PROJECT_BREAK.value,
        "direction": "DOWN",
        "foundation": "DOWN_STRUCTURE_AND_BOS_DOWN",
        "persistence": "STRUCTURE_SCOPED",
        "resolution": "NONE_IN_V1",
        "contradiction": "UP_STRUCTURE",
        "supersession": "NEW_SAME_TYPE_FOUNDATION",
    },
    {
        "name": HypothesisType.UPWARD_TRANSITION_AFTER_PROJECT_SHIFT.value,
        "direction": "UP",
        "foundation": "PRIOR_DOWN_STRUCTURE_AND_CHOCH_UP",
        "persistence": "STRUCTURE_SCOPED",
        "resolution": "LATER_UP_STRUCTURE",
        "contradiction": "NEW_DOWN_FOUNDATION;SAME_ROW_OPPOSITE_FOUNDATION_BLOCKS_ESTABLISHMENT",
        "supersession": "NEW_SAME_TYPE_FOUNDATION",
    },
    {
        "name": HypothesisType.DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT.value,
        "direction": "DOWN",
        "foundation": "PRIOR_UP_STRUCTURE_AND_CHOCH_DOWN",
        "persistence": "STRUCTURE_SCOPED",
        "resolution": "LATER_DOWN_STRUCTURE",
        "contradiction": "NEW_UP_FOUNDATION;SAME_ROW_OPPOSITE_FOUNDATION_BLOCKS_ESTABLISHMENT",
        "supersession": "NEW_SAME_TYPE_FOUNDATION",
    },
)

_FAMILY_ORDER: Final = {
    "LOCAL_STRUCTURAL_FOUNDATION": 0,
    "LOCAL_STRUCTURE_STATE": 1,
    "MULTISCALE_STRUCTURE": 2,
    "ACTUAL_FLOW_DIRECTION": 3,
    "ACTUAL_FLOW_RESPONSE": 4,
    "PROXY_PRESSURE_DIRECTION": 5,
    "PROXY_PRESSURE_RESPONSE": 6,
    "DEALING_RANGE_GEOMETRY": 7,
    "VOLATILITY_CONTEXT": 8,
    "TEMPORAL_CONTEXT": 9,
    "HIGH_SIDE_LIQUIDITY_LIFECYCLE": 10,
    "LOW_SIDE_LIQUIDITY_LIFECYCLE": 11,
    "BULLISH_OB_CANDIDATE": 12,
    "BEARISH_OB_CANDIDATE": 13,
    "BULLISH_FVG_CANDIDATE": 14,
    "BEARISH_FVG_CANDIDATE": 15,
}

_FAMILY_SOURCES: Final = {
    "LOCAL_STRUCTURAL_FOUNDATION": "structure_state_after,structural_break_event",
    "LOCAL_STRUCTURE_STATE": "structure_state_after",
    "MULTISCALE_STRUCTURE": "directional_balance,directional_consensus,directional_scale_count,availability_fraction,directional_conflict",
    "ACTUAL_FLOW_DIRECTION": "delta_ratio",
    "ACTUAL_FLOW_RESPONSE": "actual_absorption_evidence,opposed_response_percentile,opposed_response_history_count,absorbed_aggression_side",
    "PROXY_PRESSURE_DIRECTION": "volume_pressure_proxy",
    "PROXY_PRESSURE_RESPONSE": "proxy_absorption_evidence,pressure_opposed_response_percentile,pressure_opposed_response_history_count,pressure_side",
    "DEALING_RANGE_GEOMETRY": "current_range_position_raw,current_midpoint_displacement,current_discount_depth,current_premium_depth",
    "VOLATILITY_CONTEXT": "true_range_percentile,normalized_tr_change,expansion_percentile",
    "TEMPORAL_CONTEXT": "hour_utc_sin,hour_utc_cos,weekday_sin,weekday_cos",
    "HIGH_SIDE_LIQUIDITY_LIFECYCLE": "high_side_first_wick_only_count,high_side_first_close_breach_count",
    "LOW_SIDE_LIQUIDITY_LIFECYCLE": "low_side_first_wick_only_count,low_side_first_close_breach_count",
    "BULLISH_OB_CANDIDATE": "bullish_ob_first_touch_count",
    "BEARISH_OB_CANDIDATE": "bearish_ob_first_touch_count",
    "BULLISH_FVG_CANDIDATE": "bullish_fvg_first_touch_count",
    "BEARISH_FVG_CANDIDATE": "bearish_fvg_first_touch_count",
}

_OBSERVATION_ORDER: Final = {
    "LOCAL_STRUCTURE_UP_PRESENT": 0,
    "LOCAL_STRUCTURE_DOWN_PRESENT": 1,
    "LOCAL_STRUCTURE_MIXED_PRESENT": 2,
    "LOCAL_STRUCTURE_UNDEFINED_PRESENT": 3,
    "PROJECT_CONTINUATION_BREAK_UP_OBSERVED": 4,
    "PROJECT_CONTINUATION_BREAK_DOWN_OBSERVED": 5,
    "PROJECT_SHIFT_CANDIDATE_UP_OBSERVED": 6,
    "PROJECT_SHIFT_CANDIDATE_DOWN_OBSERVED": 7,
    "HIGH_SIDE_WICK_ONLY_INTERACTION_OBSERVED": 8,
    "LOW_SIDE_WICK_ONLY_INTERACTION_OBSERVED": 9,
    "HIGH_SIDE_CLOSE_BREAK_OBSERVED": 10,
    "LOW_SIDE_CLOSE_BREAK_OBSERVED": 11,
    "ACTUAL_BUY_AGGRESSION_RESPONSE_OBSERVED": 12,
    "ACTUAL_SELL_AGGRESSION_RESPONSE_OBSERVED": 13,
    "PROXY_POSITIVE_PRESSURE_RESPONSE_OBSERVED": 14,
    "PROXY_NEGATIVE_PRESSURE_RESPONSE_OBSERVED": 15,
    "BULLISH_OB_CANDIDATE_INTERACTION_OBSERVED": 16,
    "BEARISH_OB_CANDIDATE_INTERACTION_OBSERVED": 17,
    "BULLISH_FVG_CANDIDATE_INTERACTION_OBSERVED": 18,
    "BEARISH_FVG_CANDIDATE_INTERACTION_OBSERVED": 19,
}

_OBSERVATION_COLUMNS: Final = ("observation_id","observed_position","observed_index_label","observation_type","evidence_family","persistence_scope","bootstrap_context","source_mode","epistemic_status","primary_numeric_value","primary_category_value","availability_state","same_row_batch_id","serialization_order")
_HYPOTHESIS_LEDGER_COLUMNS: Final = ("ledger_event_id","hypothesis_id","event_position","same_row_batch_id","ledger_event_type","previous_state","new_state","trigger_relationship_id","superseded_by_hypothesis_id","serialization_order")
_RELATIONSHIP_COLUMNS: Final = ("relationship_id","hypothesis_id","observed_position","same_row_batch_id","evidence_family","evidence_role","relationship_bearing","source_mode","epistemic_status","event_local","primary_numeric_value","primary_category_value","support_count","availability_state","serialization_order")
_RELATIONSHIP_SOURCE_COLUMNS: Final = ("relationship_id","source_feature_name","source_output_column","source_module","source_mode","epistemic_status","source_value_float","source_value_integer","source_value_boolean","source_value_category","source_availability_state")
_ACTIVE_COLUMNS: Final = ("hypothesis_id","hypothesis_type","current_state","created_position","direction_scope","persistence_policy","foundation_relationship_id","source_mode","epistemic_status")
_SURFACE_COLUMNS: Final = (
    "nar__current_local_structure_state", "nar__new_hypothesis_created",
    "nar__new_hypothesis_count", "nar__hypothesis_state_changed",
    "nar__hypothesis_state_change_count", "nar__active_hypothesis_count",
    "nar__active_upward_hypothesis_count", "nar__active_downward_hypothesis_count",
    "nar__opposing_active_hypotheses_present",
    "nar__current_actual_flow_context_available",
    "nar__current_proxy_context_available",
    "nar__current_multiscale_context_available",
    "nar__current_range_context_available",
)

_OBSERVATION_DEFINITIONS: Final = {
    "LOCAL_STRUCTURE_UP_PRESENT": ("LOCAL_STRUCTURE_STATE", "PERSISTENT_STATE", "structure_state_after", "PROJECT_OPERATIONAL"),
    "LOCAL_STRUCTURE_DOWN_PRESENT": ("LOCAL_STRUCTURE_STATE", "PERSISTENT_STATE", "structure_state_after", "PROJECT_OPERATIONAL"),
    "LOCAL_STRUCTURE_MIXED_PRESENT": ("LOCAL_STRUCTURE_STATE", "PERSISTENT_STATE", "structure_state_after", "PROJECT_OPERATIONAL"),
    "LOCAL_STRUCTURE_UNDEFINED_PRESENT": ("LOCAL_STRUCTURE_STATE", "PERSISTENT_STATE", "structure_state_after", "PROJECT_OPERATIONAL"),
    "PROJECT_CONTINUATION_BREAK_UP_OBSERVED": ("LOCAL_STRUCTURAL_FOUNDATION", "EVENT_SCOPED", "structural_break_event", "PROJECT_OPERATIONAL"),
    "PROJECT_CONTINUATION_BREAK_DOWN_OBSERVED": ("LOCAL_STRUCTURAL_FOUNDATION", "EVENT_SCOPED", "structural_break_event", "PROJECT_OPERATIONAL"),
    "PROJECT_SHIFT_CANDIDATE_UP_OBSERVED": ("LOCAL_STRUCTURAL_FOUNDATION", "EVENT_SCOPED", "structural_break_event", "PROJECT_OPERATIONAL"),
    "PROJECT_SHIFT_CANDIDATE_DOWN_OBSERVED": ("LOCAL_STRUCTURAL_FOUNDATION", "EVENT_SCOPED", "structural_break_event", "PROJECT_OPERATIONAL"),
    "HIGH_SIDE_WICK_ONLY_INTERACTION_OBSERVED": ("HIGH_SIDE_LIQUIDITY_LIFECYCLE", "EVENT_SCOPED", "high_side_first_wick_only_count", "FACTUAL"),
    "LOW_SIDE_WICK_ONLY_INTERACTION_OBSERVED": ("LOW_SIDE_LIQUIDITY_LIFECYCLE", "EVENT_SCOPED", "low_side_first_wick_only_count", "FACTUAL"),
    "HIGH_SIDE_CLOSE_BREAK_OBSERVED": ("HIGH_SIDE_LIQUIDITY_LIFECYCLE", "EVENT_SCOPED", "high_side_first_close_breach_count", "FACTUAL"),
    "LOW_SIDE_CLOSE_BREAK_OBSERVED": ("LOW_SIDE_LIQUIDITY_LIFECYCLE", "EVENT_SCOPED", "low_side_first_close_breach_count", "FACTUAL"),
    "ACTUAL_BUY_AGGRESSION_RESPONSE_OBSERVED": ("ACTUAL_FLOW_RESPONSE", "EVENT_SCOPED", "actual_absorption_evidence,absorbed_aggression_side", "PROJECT_OPERATIONAL"),
    "ACTUAL_SELL_AGGRESSION_RESPONSE_OBSERVED": ("ACTUAL_FLOW_RESPONSE", "EVENT_SCOPED", "actual_absorption_evidence,absorbed_aggression_side", "PROJECT_OPERATIONAL"),
    "PROXY_POSITIVE_PRESSURE_RESPONSE_OBSERVED": ("PROXY_PRESSURE_RESPONSE", "EVENT_SCOPED", "proxy_absorption_evidence,pressure_side", "SOURCE_APPROXIMATION"),
    "PROXY_NEGATIVE_PRESSURE_RESPONSE_OBSERVED": ("PROXY_PRESSURE_RESPONSE", "EVENT_SCOPED", "proxy_absorption_evidence,pressure_side", "SOURCE_APPROXIMATION"),
    "BULLISH_OB_CANDIDATE_INTERACTION_OBSERVED": ("BULLISH_OB_CANDIDATE", "EVENT_SCOPED", "bullish_ob_first_touch_count", "SOURCE_APPROXIMATION"),
    "BEARISH_OB_CANDIDATE_INTERACTION_OBSERVED": ("BEARISH_OB_CANDIDATE", "EVENT_SCOPED", "bearish_ob_first_touch_count", "SOURCE_APPROXIMATION"),
    "BULLISH_FVG_CANDIDATE_INTERACTION_OBSERVED": ("BULLISH_FVG_CANDIDATE", "EVENT_SCOPED", "bullish_fvg_first_touch_count", "SOURCE_APPROXIMATION"),
    "BEARISH_FVG_CANDIDATE_INTERACTION_OBSERVED": ("BEARISH_FVG_CANDIDATE", "EVENT_SCOPED", "bearish_fvg_first_touch_count", "SOURCE_APPROXIMATION"),
}

_MANIFEST_COLUMNS: Final = (
    "record_type",
    "name",
    "direction",
    "foundation_clause",
    "persistence_policy",
    "resolution_contract",
    "contradiction_contract",
    "supersession_contract",
    "source_features",
    "persistence_scope",
    "bearing_policy",
    "same_row_semantics",
    "epistemic_status",
    "serialization_order",
)


class CausalMarketNarrativeEngine:
    """Stateless batch replay over a certified Module 6.1A surface."""

    @staticmethod
    def _manifest_maps(feature_manifest: pd.DataFrame) -> tuple[dict[str, dict], dict[str, str]]:
        contract_fields = (
            "feature_name",
            "output_column",
            "source_module",
            "semantic_type",
            "missingness_policy",
            "event_local",
            "support_column",
            "freshness_column",
            "source_mode",
            "directional_semantics",
            "expected_domain",
            "epistemic_status",
        )
        if not isinstance(feature_manifest, pd.DataFrame) or feature_manifest.columns.has_duplicates:
            raise NarrativeDataError("invalid feature manifest")
        if not set(contract_fields).issubset(feature_manifest.columns):
            raise NarrativeDataError("feature manifest schema")
        if feature_manifest["feature_name"].duplicated().any() or feature_manifest["output_column"].duplicated().any():
            raise NarrativeDataError("duplicate manifest identity")

        certified = {}
        for spec in V1_CATALOG:
            certified[spec.feature_name] = {
                "feature_name": spec.feature_name,
                "output_column": spec.output_column,
                "source_module": spec.source_module,
                "semantic_type": spec.semantic_type.value,
                "missingness_policy": spec.missingness_policy.value,
                "event_local": spec.event_local,
                "support_column": spec.support_column,
                "freshness_column": spec.freshness_column,
                "source_mode": spec.source_mode,
                "directional_semantics": spec.directional_semantics,
                "expected_domain": spec.expected_domain,
                "epistemic_status": spec.epistemic_status,
            }

        def normalized(value):
            if value is None or value is pd.NA:
                return None
            missing = pd.isna(value)
            if isinstance(missing, (bool, np.bool_)) and bool(missing):
                return None
            if isinstance(value, np.generic):
                return value.item()
            return value

        by_name: dict[str, dict] = {}
        output_to_name: dict[str, str] = {}
        for row in feature_manifest.itertuples(index=False):
            record = row._asdict()
            name = str(record["feature_name"])
            expected = certified.get(name)
            if expected is None:
                raise NarrativeDataError(f"uncertified feature manifest entry: {name}")
            for field in contract_fields:
                if normalized(record[field]) != normalized(expected[field]):
                    raise NarrativeDataError(
                        f"certified feature contract mismatch: {name}.{field}"
                    )
            by_name[name] = record
            output_to_name[str(record["output_column"])] = name

        selected_names = set(by_name)
        for group_name, group_specs in GROUPS.items():
            group_names = {spec.feature_name for spec in group_specs}
            selected_from_group = selected_names & group_names
            if selected_from_group and selected_from_group != group_names:
                raise NarrativeDataError(
                    f"incomplete certified feature group: {group_name}"
                )
        if (selected_names & {spec.feature_name for spec in GROUPS["actual"]}) and (
            selected_names & {spec.feature_name for spec in GROUPS["proxy"]}
        ):
            raise NarrativeDataError("multiple certified order-flow modes")
        return by_name, output_to_name

    @staticmethod
    def _value(evidence: pd.DataFrame, manifest: dict[str, dict], name: str, i: int):
        spec = manifest.get(name)
        if spec is None:
            return None, "NOT_APPLICABLE", None
        column = str(spec["output_column"])
        value = evidence[column].iloc[i]
        if pd.isna(value):
            return value, "UNKNOWN", spec
        return value, "AVAILABLE", spec

    @staticmethod
    def _value_prebound(columns: dict, manifest: dict[str, dict], name: str, i: int):
        # EXACT PERFORMANCE V2 PATCH-3: identical semantics to `_value`,
        # reading pre-bound column views instead of re-resolving columns.
        spec = manifest.get(name)
        if spec is None:
            return None, "NOT_APPLICABLE", None
        value = columns[name].iloc[i]
        if pd.isna(value):
            return value, "UNKNOWN", spec
        return value, "AVAILABLE", spec

    @staticmethod
    def _direction(hypothesis_type: HypothesisType) -> str:
        return "UP" if hypothesis_type in {
            HypothesisType.UPWARD_CONTINUATION_AFTER_PROJECT_BREAK,
            HypothesisType.UPWARD_TRANSITION_AFTER_PROJECT_SHIFT,
        } else "DOWN"

    @staticmethod
    def _observation_type_for_state(state: str) -> str:
        return {
            "UP_STRUCTURE": "LOCAL_STRUCTURE_UP_PRESENT",
            "DOWN_STRUCTURE": "LOCAL_STRUCTURE_DOWN_PRESENT",
            "MIXED": "LOCAL_STRUCTURE_MIXED_PRESENT",
            "UNDEFINED": "LOCAL_STRUCTURE_UNDEFINED_PRESENT",
        }[state]

    @staticmethod
    def _event_observation_type(event: str) -> Optional[str]:
        return {
            "BOS_UP": "PROJECT_CONTINUATION_BREAK_UP_OBSERVED",
            "BOS_DOWN": "PROJECT_CONTINUATION_BREAK_DOWN_OBSERVED",
            "CHOCH_UP": "PROJECT_SHIFT_CANDIDATE_UP_OBSERVED",
            "CHOCH_DOWN": "PROJECT_SHIFT_CANDIDATE_DOWN_OBSERVED",
        }.get(event)

    @staticmethod
    def narrative_manifest() -> pd.DataFrame:
        rows: list[dict] = []
        for order, definition in enumerate(_HYPOTHESIS_DEFINITIONS):
            rows.append(
                {
                    "record_type": "HYPOTHESIS_DEFINITION",
                    "name": definition["name"],
                    "direction": definition["direction"],
                    "foundation_clause": definition["foundation"],
                    "persistence_policy": definition["persistence"],
                    "resolution_contract": definition["resolution"],
                    "contradiction_contract": definition["contradiction"],
                    "supersession_contract": definition["supersession"],
                    "source_features": "structure_state_after,structural_break_event",
                    "persistence_scope": definition["persistence"],
                    "bearing_policy": "FOUNDATION_CONTEXTUALIZES",
                    "same_row_semantics": "ATOMIC_INFORMATION_TIME",
                    "epistemic_status": "PROJECT_OPERATIONAL",
                    "serialization_order": order,
                }
            )
        offset = len(rows)
        for observation_type, (family, scope, sources, epistemic) in sorted(
            _OBSERVATION_DEFINITIONS.items(), key=lambda item: _OBSERVATION_ORDER[item[0]]
        ):
            rows.append(
                {
                    "record_type": "OBSERVATION_DEFINITION",
                    "name": observation_type,
                    "direction": "NONE",
                    "foundation_clause": pd.NA,
                    "persistence_policy": pd.NA,
                    "resolution_contract": pd.NA,
                    "contradiction_contract": pd.NA,
                    "supersession_contract": pd.NA,
                    "source_features": sources,
                    "persistence_scope": scope,
                    "bearing_policy": "DESCRIPTIVE_ONLY",
                    "same_row_semantics": "ATOMIC_INFORMATION_TIME",
                    "epistemic_status": epistemic,
                    "serialization_order": offset + _OBSERVATION_ORDER[observation_type],
                }
            )
        offset = len(rows)
        for family, order in sorted(_FAMILY_ORDER.items(), key=lambda item: item[1]):
            rows.append(
                {
                    "record_type": "EVIDENCE_FAMILY",
                    "name": family,
                    "direction": "NONE",
                    "foundation_clause": pd.NA,
                    "persistence_policy": pd.NA,
                    "resolution_contract": pd.NA,
                    "contradiction_contract": pd.NA,
                    "supersession_contract": pd.NA,
                    "source_features": _FAMILY_SOURCES[family],
                    "persistence_scope": pd.NA,
                    "bearing_policy": "APPEND_ON_CHANGE_ONE_RELATIONSHIP_PER_FAMILY_PER_HYPOTHESIS",
                    "same_row_semantics": "ATOMIC_INFORMATION_TIME",
                    "epistemic_status": "PROJECT_OPERATIONAL",
                    "serialization_order": offset + order,
                }
            )
        offset = len(rows)
        for order, bearing in enumerate(RelationshipBearing):
            rows.append(
                {
                    "record_type": "RELATIONSHIP_BEARING",
                    "name": bearing.value,
                    "direction": "NONE",
                    "foundation_clause": pd.NA,
                    "persistence_policy": pd.NA,
                    "resolution_contract": pd.NA,
                    "contradiction_contract": pd.NA,
                    "supersession_contract": pd.NA,
                    "epistemic_status": "PROJECT_OPERATIONAL",
                    "serialization_order": offset + order,
                }
            )
        rows.append(
            {
                "record_type": "INPUT_MODE_CONTRACT",
                "name": "OBSERVATION_ONLY_NO_STRUCTURAL_FOUNDATION",
                "direction": "NONE",
                "foundation_clause": "STRUCTURE_GROUP_ABSENT",
                "persistence_policy": "NO_STRUCTURAL_HYPOTHESES",
                "resolution_contract": pd.NA,
                "contradiction_contract": pd.NA,
                "supersession_contract": pd.NA,
                "source_features": pd.NA,
                "persistence_scope": "ENABLED_NONSTRUCTURAL_OBSERVATIONS_ONLY",
                "bearing_policy": "NO_FABRICATED_TRAJECTORY_HYPOTHESES",
                "same_row_semantics": "ATOMIC_INFORMATION_TIME",
                "epistemic_status": "PROJECT_OPERATIONAL",
                "serialization_order": offset + len(RelationshipBearing),
            }
        )
        return pd.DataFrame(rows, columns=_MANIFEST_COLUMNS)

    @staticmethod
    def _typed_table(frame: pd.DataFrame, *, int_columns=(), string_columns=(), bool_columns=(), float_columns=()) -> pd.DataFrame:
        result = frame.copy()
        for column in int_columns:
            result[column] = pd.array(result[column], dtype="Int64")
        for column in string_columns:
            result[column] = pd.array(result[column], dtype="string")
        for column in bool_columns:
            result[column] = pd.array(result[column], dtype="boolean")
        for column in float_columns:
            result[column] = pd.array(result[column], dtype="Float64")
        return result

    def analyze(self, evidence_df: pd.DataFrame, feature_manifest: pd.DataFrame) -> NarrativeResult:
        if not isinstance(evidence_df, pd.DataFrame) or evidence_df.columns.has_duplicates:
            raise NarrativeDataError("invalid evidence frame")
        if evidence_df.index.has_duplicates or not evidence_df.index.is_monotonic_increasing:
            raise NarrativeDataError("evidence index contract")
        manifest, output_to_name = self._manifest_maps(feature_manifest)
        allowed_columns = set(output_to_name) | {
            "ev__evidence_feature_count",
            "ev__evidence_available_count",
            "ev__evidence_availability_fraction",
        }
        extra = [column for column in evidence_df.columns if column not in allowed_columns]
        if extra:
            raise NarrativeDataError(f"unregistered evidence columns: {extra}")
        missing = [spec["output_column"] for spec in manifest.values() if spec["output_column"] not in evidence_df.columns]
        if missing:
            raise NarrativeDataError(f"manifest evidence columns missing: {missing}")

        # EXACT PERFORMANCE V2 PATCH-3: bind each manifest evidence column
        # once (positional Series views) instead of re-resolving
        # evidence_df[column] on every row/feature lookup. Values, dtypes and
        # .iloc semantics are unchanged.
        bound_columns = {
            name: evidence_df[str(spec["output_column"])]
            for name, spec in manifest.items()
        }

        def value_of(name: str, i: int):
            return self._value_prebound(bound_columns, manifest, name, i)

        observation_rows: list[dict] = []
        hypothesis_ledger_rows: list[dict] = []
        relationship_rows: list[dict] = []
        relationship_source_rows: list[dict] = []
        surface_rows: list[dict] = []
        active: dict[int, _Hypothesis] = {}
        previous_structure: Optional[str] = None
        next_observation_id = 0
        next_hypothesis_id = 0
        next_relationship_id = 0
        next_ledger_event_id = 0
        latest_family_fingerprint: dict[tuple[int, str], tuple] = {}

        def append_observation(i: int, observation_type: str, family: str, scope: str, numeric=np.nan, category=pd.NA, source_mode="ANY", epistemic="FACTUAL", bootstrap=pd.NA):
            nonlocal next_observation_id
            observation_rows.append(
                {
                    "observation_id": next_observation_id,
                    "observed_position": i,
                    "observed_index_label": evidence_df.index[i],
                    "observation_type": observation_type,
                    "evidence_family": family,
                    "persistence_scope": scope,
                    "bootstrap_context": bootstrap,
                    "source_mode": source_mode,
                    "epistemic_status": epistemic,
                    "primary_numeric_value": numeric,
                    "primary_category_value": category,
                    "availability_state": "AVAILABLE",
                    "same_row_batch_id": i,
                    "serialization_order": _OBSERVATION_ORDER[observation_type],
                }
            )
            next_observation_id += 1

        def append_relationship(i: int, hypothesis: _Hypothesis, family: str, role: str, bearing: RelationshipBearing, sources: list[str], numeric=np.nan, category=pd.NA, support_count=pd.NA, availability="AVAILABLE", source_mode="ANY", epistemic="FACTUAL", event_local=False):
            nonlocal next_relationship_id

            def canonical(value):
                if value is None or value is pd.NA:
                    return ("MISSING",)
                missing = pd.isna(value)
                if isinstance(missing, (bool, np.bool_)) and bool(missing):
                    return ("MISSING",)
                if isinstance(value, np.generic):
                    value = value.item()
                return (type(value).__name__, value)

            source_descriptors = []
            category_domains = {
                "structure_state",
                "break_event",
                "category_side",
                "category_pressure",
            }
            continuous_domains = {
                "percentile",
                "unit_interval",
                "signed_unit",
                "finite_or_nan",
                "nonnegative_or_nan",
            }
            for source_name in sources:
                source_value, source_availability, spec = value_of(source_name, i)
                if spec is None:
                    continue
                source_float = np.nan
                source_integer = pd.NA
                source_boolean = pd.NA
                source_category = pd.NA
                domain = str(spec["expected_domain"])
                if source_availability == "AVAILABLE":
                    if domain == "count":
                        source_integer = int(source_value)
                    elif domain == "bool":
                        source_boolean = bool(source_value)
                    elif domain in category_domains:
                        source_category = str(source_value)
                    elif domain in continuous_domains:
                        source_float = float(source_value)
                    else:
                        raise NarrativeDataError(
                            f"unsupported certified source domain: {domain}"
                        )
                source_descriptors.append(
                    {
                        "source_name": source_name,
                        "availability": source_availability,
                        "float": source_float,
                        "integer": source_integer,
                        "boolean": source_boolean,
                        "category": source_category,
                        "domain": domain,
                        "spec": spec,
                    }
                )

            fingerprint = (
                role,
                bearing.value,
                event_local,
                canonical(numeric),
                canonical(category),
                canonical(support_count),
                availability,
                source_mode,
                epistemic,
                tuple(
                    (
                        descriptor["source_name"],
                        descriptor["availability"],
                        descriptor["domain"],
                        descriptor["spec"]["source_module"],
                        descriptor["spec"]["source_mode"],
                        descriptor["spec"]["epistemic_status"],
                        canonical(descriptor["float"]),
                        canonical(descriptor["integer"]),
                        canonical(descriptor["boolean"]),
                        canonical(descriptor["category"]),
                    )
                    for descriptor in source_descriptors
                ),
            )
            key = (hypothesis.hypothesis_id, family)
            if latest_family_fingerprint.get(key) == fingerprint:
                return None
            latest_family_fingerprint[key] = fingerprint
            relationship_id = next_relationship_id
            relationship_rows.append(
                {
                    "relationship_id": relationship_id,
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "observed_position": i,
                    "same_row_batch_id": i,
                    "evidence_family": family,
                    "evidence_role": role,
                    "relationship_bearing": bearing.value,
                    "source_mode": source_mode,
                    "epistemic_status": epistemic,
                    "event_local": event_local,
                    "primary_numeric_value": numeric,
                    "primary_category_value": category,
                    "support_count": support_count,
                    "availability_state": availability,
                    "serialization_order": _FAMILY_ORDER[family],
                }
            )
            for descriptor in source_descriptors:
                spec = descriptor["spec"]
                relationship_source_rows.append(
                    {
                        "relationship_id": relationship_id,
                        "source_feature_name": descriptor["source_name"],
                        "source_output_column": spec["output_column"],
                        "source_module": spec["source_module"],
                        "source_mode": spec["source_mode"],
                        "epistemic_status": spec["epistemic_status"],
                        "source_value_float": descriptor["float"],
                        "source_value_integer": descriptor["integer"],
                        "source_value_boolean": descriptor["boolean"],
                        "source_value_category": descriptor["category"],
                        "source_availability_state": descriptor["availability"],
                    }
                )
            next_relationship_id += 1
            return relationship_id

        def append_hypothesis_event(i: int, hypothesis: _Hypothesis, event_type: str, previous_state, new_state, trigger_relationship_id=pd.NA, superseded_by=pd.NA):
            nonlocal next_ledger_event_id
            hypothesis_ledger_rows.append(
                {
                    "ledger_event_id": next_ledger_event_id,
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "event_position": i,
                    "same_row_batch_id": i,
                    "ledger_event_type": event_type,
                    "previous_state": previous_state,
                    "new_state": new_state,
                    "trigger_relationship_id": trigger_relationship_id,
                    "superseded_by_hypothesis_id": superseded_by,
                    "serialization_order": next_ledger_event_id,
                }
            )
            next_ledger_event_id += 1

        def terminate(i: int, hypothesis: _Hypothesis, new_state: HypothesisState, event_type: str, trigger_relationship_id=pd.NA, superseded_by=pd.NA):
            previous = hypothesis.current_state
            hypothesis.current_state = new_state
            active.pop(hypothesis.hypothesis_id, None)
            append_hypothesis_event(i, hypothesis, event_type, previous.value, new_state.value, trigger_relationship_id, superseded_by)

        def create_hypothesis(i: int, hypothesis_type: HypothesisType, source_mode="ANY"):
            nonlocal next_hypothesis_id
            prior_same_type = [
                old for old in active.values()
                if old.hypothesis_type is hypothesis_type
            ]
            hypothesis = _Hypothesis(
                hypothesis_id=next_hypothesis_id,
                hypothesis_type=hypothesis_type,
                created_position=i,
                current_state=HypothesisState.MONITORING,
                direction=self._direction(hypothesis_type),
                foundation_relationship_id=-1,
                source_mode=source_mode,
            )
            active[hypothesis.hypothesis_id] = hypothesis
            next_hypothesis_id += 1
            foundation_id = append_relationship(
                i,
                hypothesis,
                "LOCAL_STRUCTURAL_FOUNDATION",
                "FOUNDATION",
                RelationshipBearing.CONTEXTUALIZES,
                ["structure_state_after", "structural_break_event"],
                category=hypothesis_type.value,
                epistemic="PROJECT_OPERATIONAL",
                event_local=True,
            )
            if foundation_id is None:
                raise NarrativeDataError("new hypothesis foundation relationship missing")
            hypothesis.foundation_relationship_id = foundation_id
            append_hypothesis_event(
                i,
                hypothesis,
                "CREATED",
                pd.NA,
                HypothesisState.MONITORING.value,
                foundation_id,
            )
            for old in prior_same_type:
                terminate(
                    i,
                    old,
                    HypothesisState.SUPERSEDED,
                    "SUPERSEDED",
                    trigger_relationship_id=foundation_id,
                    superseded_by=hypothesis.hypothesis_id,
                )
            return hypothesis

        for i in range(len(evidence_df)):
            new_hypothesis_count = 0
            ledger_row_start = len(hypothesis_ledger_rows)
            state_value, state_availability, _ = value_of("structure_state_after", i)
            break_value, break_availability, _ = value_of("structural_break_event", i)
            state = None if state_availability != "AVAILABLE" else str(state_value)
            break_event = "NONE" if break_availability != "AVAILABLE" else str(break_value)

            if state is not None and (i == 0 or state != previous_structure):
                append_observation(
                    i,
                    self._observation_type_for_state(state),
                    "LOCAL_STRUCTURE_STATE",
                    "PERSISTENT_STATE",
                    category=state,
                    epistemic="PROJECT_OPERATIONAL",
                    bootstrap="LEFT_BOUNDARY_STATE_ONLY" if i == 0 else pd.NA,
                )

            event_observation = self._event_observation_type(break_event)
            if event_observation is not None:
                append_observation(
                    i,
                    event_observation,
                    "LOCAL_STRUCTURAL_FOUNDATION",
                    "EVENT_SCOPED",
                    category=break_event,
                    epistemic="PROJECT_OPERATIONAL",
                )

            event_observation_map = (
                ("high_side_first_wick_only_count", "HIGH_SIDE_WICK_ONLY_INTERACTION_OBSERVED", "HIGH_SIDE_LIQUIDITY_LIFECYCLE", "FACTUAL"),
                ("low_side_first_wick_only_count", "LOW_SIDE_WICK_ONLY_INTERACTION_OBSERVED", "LOW_SIDE_LIQUIDITY_LIFECYCLE", "FACTUAL"),
                ("high_side_first_close_breach_count", "HIGH_SIDE_CLOSE_BREAK_OBSERVED", "HIGH_SIDE_LIQUIDITY_LIFECYCLE", "FACTUAL"),
                ("low_side_first_close_breach_count", "LOW_SIDE_CLOSE_BREAK_OBSERVED", "LOW_SIDE_LIQUIDITY_LIFECYCLE", "FACTUAL"),
            )
            for feature_name, observation_type, family, epistemic in event_observation_map:
                value, availability, _ = value_of(feature_name, i)
                if availability == "AVAILABLE" and int(value) > 0:
                    append_observation(i, observation_type, family, "EVENT_SCOPED", numeric=float(value), epistemic=epistemic)

            actual_side, actual_side_availability, _ = value_of("absorbed_aggression_side", i)
            actual_absorption, actual_absorption_availability, _ = value_of("actual_absorption_evidence", i)
            if actual_side_availability == "AVAILABLE" and actual_absorption_availability == "AVAILABLE" and str(actual_side) in {"BUY", "SELL"}:
                append_observation(
                    i,
                    "ACTUAL_BUY_AGGRESSION_RESPONSE_OBSERVED" if str(actual_side) == "BUY" else "ACTUAL_SELL_AGGRESSION_RESPONSE_OBSERVED",
                    "ACTUAL_FLOW_RESPONSE",
                    "EVENT_SCOPED",
                    numeric=float(actual_absorption),
                    category=str(actual_side),
                    source_mode="ACTUAL",
                    epistemic="PROJECT_OPERATIONAL",
                )

            proxy_side, proxy_side_availability, _ = value_of("pressure_side", i)
            proxy_absorption, proxy_absorption_availability, _ = value_of("proxy_absorption_evidence", i)
            if proxy_side_availability == "AVAILABLE" and proxy_absorption_availability == "AVAILABLE" and str(proxy_side) in {"POSITIVE", "NEGATIVE"}:
                append_observation(
                    i,
                    "PROXY_POSITIVE_PRESSURE_RESPONSE_OBSERVED" if str(proxy_side) == "POSITIVE" else "PROXY_NEGATIVE_PRESSURE_RESPONSE_OBSERVED",
                    "PROXY_PRESSURE_RESPONSE",
                    "EVENT_SCOPED",
                    numeric=float(proxy_absorption),
                    category=str(proxy_side),
                    source_mode="PROXY",
                    epistemic="SOURCE_APPROXIMATION",
                )

            zone_observations = (
                ("bullish_ob_first_touch_count", "BULLISH_OB_CANDIDATE_INTERACTION_OBSERVED", "BULLISH_OB_CANDIDATE"),
                ("bearish_ob_first_touch_count", "BEARISH_OB_CANDIDATE_INTERACTION_OBSERVED", "BEARISH_OB_CANDIDATE"),
                ("bullish_fvg_first_touch_count", "BULLISH_FVG_CANDIDATE_INTERACTION_OBSERVED", "BULLISH_FVG_CANDIDATE"),
                ("bearish_fvg_first_touch_count", "BEARISH_FVG_CANDIDATE_INTERACTION_OBSERVED", "BEARISH_FVG_CANDIDATE"),
            )
            for feature_name, observation_type, family in zone_observations:
                value, availability, _ = value_of(feature_name, i)
                if availability == "AVAILABLE" and int(value) > 0:
                    append_observation(i, observation_type, family, "EVENT_SCOPED", numeric=float(value), epistemic="SOURCE_APPROXIMATION")

            created_types: list[HypothesisType] = []
            if state == "UP_STRUCTURE" and break_event == "BOS_UP":
                created_types.append(HypothesisType.UPWARD_CONTINUATION_AFTER_PROJECT_BREAK)
            if state == "DOWN_STRUCTURE" and break_event == "BOS_DOWN":
                created_types.append(HypothesisType.DOWNWARD_CONTINUATION_AFTER_PROJECT_BREAK)
            if previous_structure == "DOWN_STRUCTURE" and break_event == "CHOCH_UP":
                created_types.append(HypothesisType.UPWARD_TRANSITION_AFTER_PROJECT_SHIFT)
            if previous_structure == "UP_STRUCTURE" and break_event == "CHOCH_DOWN":
                created_types.append(HypothesisType.DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT)

            for hypothesis in list(active.values()):
                contradiction = (
                    hypothesis.direction == "UP" and state == "DOWN_STRUCTURE"
                ) or (
                    hypothesis.direction == "DOWN" and state == "UP_STRUCTURE"
                )
                transition = hypothesis.hypothesis_type in {
                    HypothesisType.UPWARD_TRANSITION_AFTER_PROJECT_SHIFT,
                    HypothesisType.DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT,
                }
                established = transition and i > hypothesis.created_position and (
                    (hypothesis.direction == "UP" and state == "UP_STRUCTURE")
                    or (hypothesis.direction == "DOWN" and state == "DOWN_STRUCTURE")
                )
                opposite_foundation = (
                    hypothesis.direction == "UP" and break_event in {"BOS_DOWN", "CHOCH_DOWN"}
                ) or (
                    hypothesis.direction == "DOWN" and break_event in {"BOS_UP", "CHOCH_UP"}
                )
                terminal_contradiction = (
                    (not transition and contradiction)
                    or (transition and opposite_foundation)
                )
                if terminal_contradiction:
                    contradiction_family = (
                        "LOCAL_STRUCTURAL_FOUNDATION"
                        if transition and opposite_foundation
                        else "LOCAL_STRUCTURE_STATE"
                    )
                    contradiction_sources = (
                        ["structure_state_after", "structural_break_event"]
                        if contradiction_family == "LOCAL_STRUCTURAL_FOUNDATION"
                        else ["structure_state_after"]
                    )
                    relationship_id = append_relationship(
                        i,
                        hypothesis,
                        contradiction_family,
                        "CONTRADICTING",
                        RelationshipBearing.CONTRADICTS,
                        contradiction_sources,
                        category=state if state is not None else break_event,
                        epistemic="PROJECT_OPERATIONAL",
                        event_local=opposite_foundation,
                    )
                    if relationship_id is None:
                        raise NarrativeDataError("terminal contradiction relationship missing")
                    terminate(
                        i,
                        hypothesis,
                        HypothesisState.CONTRADICTED,
                        "STATE_CHANGED",
                        relationship_id,
                    )
                elif established:
                    relationship_id = append_relationship(
                        i,
                        hypothesis,
                        "LOCAL_STRUCTURE_STATE",
                        "FOUNDATION_RESOLUTION",
                        RelationshipBearing.ALIGNS_WITH,
                        ["structure_state_after"],
                        category=state,
                        epistemic="PROJECT_OPERATIONAL",
                    )
                    if relationship_id is None:
                        raise NarrativeDataError("terminal establishment relationship missing")
                    terminate(
                        i,
                        hypothesis,
                        HypothesisState.OBSERVED_DIRECTION_ESTABLISHED,
                        "STATE_CHANGED",
                        relationship_id,
                    )

            for hypothesis_type in created_types:
                create_hypothesis(i, hypothesis_type)
                new_hypothesis_count += 1

            for hypothesis in list(active.values()):
                structure_bearing = RelationshipBearing.UNKNOWN
                if state is not None:
                    if state == "MIXED":
                        structure_bearing = RelationshipBearing.NEUTRAL
                    elif state == "UNDEFINED":
                        structure_bearing = RelationshipBearing.UNKNOWN
                    elif (hypothesis.direction == "UP" and state == "UP_STRUCTURE") or (hypothesis.direction == "DOWN" and state == "DOWN_STRUCTURE"):
                        structure_bearing = RelationshipBearing.ALIGNS_WITH
                    elif hypothesis.hypothesis_type in {
                        HypothesisType.UPWARD_TRANSITION_AFTER_PROJECT_SHIFT,
                        HypothesisType.DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT,
                    }:
                        structure_bearing = RelationshipBearing.CONTEXTUALIZES
                    else:
                        structure_bearing = RelationshipBearing.CONTRADICTS
                append_relationship(
                    i,
                    hypothesis,
                    "LOCAL_STRUCTURE_STATE",
                    "CURRENT_STATE",
                    structure_bearing,
                    ["structure_state_after"],
                    category=state if state is not None else pd.NA,
                    availability="AVAILABLE" if state is not None else "UNKNOWN",
                    epistemic="PROJECT_OPERATIONAL",
                )

                if "directional_balance" in manifest:
                    balance, balance_availability, _ = value_of("directional_balance", i)
                    consensus, _, _ = value_of("directional_consensus", i)
                    directional_count, _, _ = value_of("directional_scale_count", i)
                    availability_fraction, _, _ = value_of("availability_fraction", i)
                    conflict, _, _ = value_of("directional_conflict", i)
                    if balance_availability == "NOT_APPLICABLE":
                        mtf_bearing = RelationshipBearing.NOT_APPLICABLE
                    elif balance_availability == "UNKNOWN":
                        mtf_bearing = RelationshipBearing.UNKNOWN
                    elif float(balance) == 0.0:
                        mtf_bearing = RelationshipBearing.NEUTRAL
                    elif (float(balance) > 0 and hypothesis.direction == "UP") or (float(balance) < 0 and hypothesis.direction == "DOWN"):
                        mtf_bearing = RelationshipBearing.ALIGNS_WITH
                    else:
                        mtf_bearing = RelationshipBearing.DIRECTIONALLY_OPPOSES
                    append_relationship(
                        i,
                        hypothesis,
                        "MULTISCALE_STRUCTURE",
                        "DIRECTIONAL_CONTEXT",
                        mtf_bearing,
                        ["directional_balance", "directional_consensus", "directional_scale_count", "availability_fraction", "directional_conflict"],
                        numeric=float(balance) if balance_availability == "AVAILABLE" else np.nan,
                        category="CONFLICT" if conflict is True or isinstance(conflict, np.bool_) and bool(conflict) else pd.NA,
                        support_count=directional_count if directional_count is not None else pd.NA,
                        availability=balance_availability,
                        epistemic="FACTUAL",
                    )

                flow_name = "delta_ratio" if "delta_ratio" in manifest else "volume_pressure_proxy" if "volume_pressure_proxy" in manifest else None
                if flow_name is not None:
                    flow_value, flow_availability, flow_spec = value_of(flow_name, i)
                    if flow_availability == "UNKNOWN":
                        flow_bearing = RelationshipBearing.UNKNOWN
                    elif flow_availability == "NOT_APPLICABLE":
                        flow_bearing = RelationshipBearing.NOT_APPLICABLE
                    elif float(flow_value) == 0.0:
                        flow_bearing = RelationshipBearing.NEUTRAL
                    elif (float(flow_value) > 0 and hypothesis.direction == "UP") or (float(flow_value) < 0 and hypothesis.direction == "DOWN"):
                        flow_bearing = RelationshipBearing.ALIGNS_WITH
                    else:
                        flow_bearing = RelationshipBearing.DIRECTIONALLY_OPPOSES
                    family = "ACTUAL_FLOW_DIRECTION" if flow_name == "delta_ratio" else "PROXY_PRESSURE_DIRECTION"
                    append_relationship(
                        i,
                        hypothesis,
                        family,
                        "DIRECTIONAL_CONTEXT",
                        flow_bearing,
                        [flow_name],
                        numeric=float(flow_value) if flow_availability == "AVAILABLE" else np.nan,
                        availability=flow_availability,
                        source_mode=flow_spec["source_mode"] if flow_spec else "ANY",
                        epistemic=flow_spec["epistemic_status"] if flow_spec else "FACTUAL",
                    )

                if "actual_absorption_evidence" in manifest:
                    absorption, availability, spec = value_of("actual_absorption_evidence", i)
                    opposed_support, _, _ = value_of("opposed_response_history_count", i)
                    append_relationship(
                        i,
                        hypothesis,
                        "ACTUAL_FLOW_RESPONSE",
                        "RESPONSE_CONTEXT",
                        RelationshipBearing.QUALIFIES if availability == "AVAILABLE" else RelationshipBearing.UNKNOWN,
                        ["actual_absorption_evidence", "opposed_response_percentile", "opposed_response_history_count", "absorbed_aggression_side"],
                        numeric=float(absorption) if availability == "AVAILABLE" else np.nan,
                        support_count=opposed_support if opposed_support is not None else pd.NA,
                        availability=availability,
                        source_mode="ACTUAL",
                        epistemic=spec["epistemic_status"] if spec else "PROJECT_OPERATIONAL",
                    )
                if "proxy_absorption_evidence" in manifest:
                    absorption, availability, spec = value_of("proxy_absorption_evidence", i)
                    opposed_support, _, _ = value_of("pressure_opposed_response_history_count", i)
                    append_relationship(
                        i,
                        hypothesis,
                        "PROXY_PRESSURE_RESPONSE",
                        "RESPONSE_CONTEXT",
                        RelationshipBearing.QUALIFIES if availability == "AVAILABLE" else RelationshipBearing.UNKNOWN,
                        ["proxy_absorption_evidence", "pressure_opposed_response_percentile", "pressure_opposed_response_history_count", "pressure_side"],
                        numeric=float(absorption) if availability == "AVAILABLE" else np.nan,
                        support_count=opposed_support if opposed_support is not None else pd.NA,
                        availability=availability,
                        source_mode="PROXY",
                        epistemic=spec["epistemic_status"] if spec else "SOURCE_APPROXIMATION",
                    )

                range_names = (
                    "current_range_position_raw",
                    "current_midpoint_displacement",
                    "current_discount_depth",
                    "current_premium_depth",
                )
                range_descriptors = {
                    name: value_of(name, i)
                    for name in range_names
                }
                range_available = any(
                    descriptor[1] == "AVAILABLE"
                    for descriptor in range_descriptors.values()
                )
                if any(name in manifest for name in range_names):
                    range_position, range_position_availability, _ = range_descriptors[
                        "current_range_position_raw"
                    ]
                    append_relationship(
                        i,
                        hypothesis,
                        "DEALING_RANGE_GEOMETRY",
                        "GEOMETRIC_CONTEXT",
                        RelationshipBearing.CONTEXTUALIZES if range_available else RelationshipBearing.UNKNOWN,
                        list(range_names),
                        numeric=float(range_position) if range_position_availability == "AVAILABLE" else np.nan,
                        availability="AVAILABLE" if range_available else "UNKNOWN",
                        epistemic="FACTUAL_GEOMETRY",
                    )

                volatility_names = [name for name in ("true_range_percentile", "normalized_tr_change", "expansion_percentile") if name in manifest]
                if volatility_names:
                    values = [value_of(name, i)[0] for name in volatility_names]
                    finite_values = [float(value) for value in values if value is not None and not pd.isna(value)]
                    append_relationship(
                        i,
                        hypothesis,
                        "VOLATILITY_CONTEXT",
                        "ENVIRONMENT_CONTEXT",
                        RelationshipBearing.CONTEXTUALIZES if finite_values else RelationshipBearing.UNKNOWN,
                        volatility_names,
                        numeric=finite_values[0] if finite_values else np.nan,
                        availability="AVAILABLE" if finite_values else "UNKNOWN",
                    )

                temporal_names = [name for name in ("hour_utc_sin", "hour_utc_cos", "weekday_sin", "weekday_cos") if name in manifest]
                if temporal_names:
                    values = [value_of(name, i)[0] for name in temporal_names]
                    finite_values = [float(value) for value in values if value is not None and not pd.isna(value)]
                    append_relationship(
                        i,
                        hypothesis,
                        "TEMPORAL_CONTEXT",
                        "TIME_CONTEXT",
                        RelationshipBearing.CONTEXTUALIZES if finite_values else RelationshipBearing.UNKNOWN,
                        temporal_names,
                        numeric=finite_values[0] if finite_values else np.nan,
                        availability="AVAILABLE" if finite_values else "UNKNOWN",
                    )

            state_change_count = sum(
                event["ledger_event_type"] in {
                    "STATE_CHANGED",
                    "SUPERSEDED",
                }
                for event in hypothesis_ledger_rows[ledger_row_start:]
            )
            active_values = list(active.values())
            upward_count = sum(h.direction == "UP" for h in active_values)
            downward_count = sum(h.direction == "DOWN" for h in active_values)
            surface_rows.append(
                {
                    "nar__current_local_structure_state": state if state is not None else pd.NA,
                    "nar__new_hypothesis_created": new_hypothesis_count > 0,
                    "nar__new_hypothesis_count": new_hypothesis_count,
                    "nar__hypothesis_state_changed": state_change_count > 0,
                    "nar__hypothesis_state_change_count": state_change_count,
                    "nar__active_hypothesis_count": len(active_values),
                    "nar__active_upward_hypothesis_count": upward_count,
                    "nar__active_downward_hypothesis_count": downward_count,
                    "nar__opposing_active_hypotheses_present": upward_count > 0 and downward_count > 0,
                    "nar__current_actual_flow_context_available": "delta_ratio" in manifest and not pd.isna(evidence_df[manifest["delta_ratio"]["output_column"]].iloc[i]),
                    "nar__current_proxy_context_available": "volume_pressure_proxy" in manifest and not pd.isna(evidence_df[manifest["volume_pressure_proxy"]["output_column"]].iloc[i]),
                    "nar__current_multiscale_context_available": "directional_balance" in manifest and not pd.isna(evidence_df[manifest["directional_balance"]["output_column"]].iloc[i]),
                    "nar__current_range_context_available": "current_range_position_raw" in manifest and not pd.isna(evidence_df[manifest["current_range_position_raw"]["output_column"]].iloc[i]),
                }
            )
            previous_structure = state

        narrative_surface = pd.DataFrame(surface_rows, index=evidence_df.index, columns=_SURFACE_COLUMNS)
        observation_ledger = pd.DataFrame(observation_rows, columns=_OBSERVATION_COLUMNS)
        hypothesis_ledger = pd.DataFrame(hypothesis_ledger_rows, columns=_HYPOTHESIS_LEDGER_COLUMNS)
        relationship_ledger = pd.DataFrame(relationship_rows, columns=_RELATIONSHIP_COLUMNS)
        relationship_sources = pd.DataFrame(relationship_source_rows, columns=_RELATIONSHIP_SOURCE_COLUMNS)
        active_rows = [
            {
                "hypothesis_id": hypothesis.hypothesis_id,
                "hypothesis_type": hypothesis.hypothesis_type.value,
                "current_state": hypothesis.current_state.value,
                "created_position": hypothesis.created_position,
                "direction_scope": hypothesis.direction,
                "persistence_policy": "STRUCTURE_SCOPED",
                "foundation_relationship_id": hypothesis.foundation_relationship_id,
                "source_mode": hypothesis.source_mode,
                "epistemic_status": hypothesis.epistemic_status,
            }
            for hypothesis in sorted(active.values(), key=lambda item: item.hypothesis_id)
        ]
        active_hypotheses = pd.DataFrame(active_rows, columns=_ACTIVE_COLUMNS)

        relationship_ids = set(relationship_ledger["relationship_id"])
        if not set(relationship_sources["relationship_id"]).issubset(relationship_ids):
            raise NarrativeDataError("orphan relationship source")
        value_column_for_domain = {
            "count": "source_value_integer",
            "bool": "source_value_boolean",
            "structure_state": "source_value_category",
            "break_event": "source_value_category",
            "category_side": "source_value_category",
            "category_pressure": "source_value_category",
            "percentile": "source_value_float",
            "unit_interval": "source_value_float",
            "signed_unit": "source_value_float",
            "finite_or_nan": "source_value_float",
            "nonnegative_or_nan": "source_value_float",
        }
        typed_value_columns = (
            "source_value_float",
            "source_value_integer",
            "source_value_boolean",
            "source_value_category",
        )
        for source_link in relationship_sources.itertuples(index=False):
            values = {
                column: getattr(source_link, column)
                for column in typed_value_columns
            }
            populated = {
                column for column, value in values.items() if not pd.isna(value)
            }
            if source_link.source_availability_state == "AVAILABLE":
                domain = str(
                    manifest[source_link.source_feature_name]["expected_domain"]
                )
                expected_column = value_column_for_domain[domain]
                if populated != {expected_column}:
                    raise NarrativeDataError("relationship source typed-value integrity")
            elif populated:
                raise NarrativeDataError("unavailable relationship source has value")
        for relationship in relationship_ledger.itertuples(index=False):
            links = relationship_sources[
                relationship_sources["relationship_id"] == relationship.relationship_id
            ]
            expected_sources = {
                name
                for name in _FAMILY_SOURCES[relationship.evidence_family].split(",")
                if name in manifest
            }
            actual_sources = set(links["source_feature_name"])
            if len(links) != len(actual_sources) or actual_sources != expected_sources:
                raise NarrativeDataError(
                    f"relationship source-family integrity: {relationship.evidence_family} "
                    f"expected={sorted(expected_sources)} actual={sorted(actual_sources)}"
                )

        terminal_states = {
            HypothesisState.CONTRADICTED.value,
            HypothesisState.OBSERVED_DIRECTION_ESTABLISHED.value,
            HypothesisState.SUPERSEDED.value,
        }
        for event in hypothesis_ledger[
            hypothesis_ledger["new_state"].isin(terminal_states)
        ].itertuples(index=False):
            if pd.isna(event.trigger_relationship_id) or event.trigger_relationship_id not in relationship_ids:
                raise NarrativeDataError("terminal lifecycle trigger missing")
            if event.new_state == HypothesisState.SUPERSEDED.value:
                trigger = relationship_ledger[
                    relationship_ledger["relationship_id"]
                    == event.trigger_relationship_id
                ].iloc[0]
                if (
                    pd.isna(event.superseded_by_hypothesis_id)
                    or trigger["hypothesis_id"] != event.superseded_by_hypothesis_id
                    or trigger["evidence_role"] != "FOUNDATION"
                ):
                    raise NarrativeDataError("supersession trigger integrity")

        observation_ledger = self._typed_table(
            observation_ledger,
            int_columns=("observation_id", "observed_position", "same_row_batch_id", "serialization_order"),
            string_columns=("observation_type", "evidence_family", "persistence_scope", "bootstrap_context", "source_mode", "epistemic_status", "primary_category_value", "availability_state"),
            float_columns=("primary_numeric_value",),
        )
        hypothesis_ledger = self._typed_table(
            hypothesis_ledger,
            int_columns=("ledger_event_id", "hypothesis_id", "event_position", "same_row_batch_id", "trigger_relationship_id", "superseded_by_hypothesis_id", "serialization_order"),
            string_columns=("ledger_event_type", "previous_state", "new_state"),
        )
        relationship_ledger = self._typed_table(
            relationship_ledger,
            int_columns=("relationship_id", "hypothesis_id", "observed_position", "same_row_batch_id", "support_count", "serialization_order"),
            string_columns=("evidence_family", "evidence_role", "relationship_bearing", "source_mode", "epistemic_status", "primary_category_value", "availability_state"),
            bool_columns=("event_local",),
            float_columns=("primary_numeric_value",),
        )
        relationship_sources = self._typed_table(
            relationship_sources,
            int_columns=("relationship_id", "source_value_integer"),
            string_columns=("source_feature_name", "source_output_column", "source_module", "source_mode", "epistemic_status", "source_value_category", "source_availability_state"),
            bool_columns=("source_value_boolean",),
            float_columns=("source_value_float",),
        )
        active_hypotheses = self._typed_table(
            active_hypotheses,
            int_columns=("hypothesis_id", "created_position", "foundation_relationship_id"),
            string_columns=("hypothesis_type", "current_state", "direction_scope", "persistence_policy", "source_mode", "epistemic_status"),
        )
        for column in (
            "nar__current_local_structure_state",
        ):
            narrative_surface[column] = pd.array(narrative_surface[column], dtype="string")
        for column in (
            "nar__new_hypothesis_created",
            "nar__hypothesis_state_changed",
            "nar__opposing_active_hypotheses_present",
            "nar__current_actual_flow_context_available",
            "nar__current_proxy_context_available",
            "nar__current_multiscale_context_available",
            "nar__current_range_context_available",
        ):
            narrative_surface[column] = pd.array(narrative_surface[column], dtype="boolean")
        for column in (
            "nar__new_hypothesis_count",
            "nar__hypothesis_state_change_count",
            "nar__active_hypothesis_count",
            "nar__active_upward_hypothesis_count",
            "nar__active_downward_hypothesis_count",
        ):
            narrative_surface[column] = pd.array(narrative_surface[column], dtype="Int64")

        return NarrativeResult(
            narrative_surface=narrative_surface,
            observation_ledger=observation_ledger,
            active_hypotheses=active_hypotheses,
            hypothesis_ledger=hypothesis_ledger,
            relationship_ledger=relationship_ledger,
            relationship_sources=relationship_sources,
            narrative_manifest=self.narrative_manifest(),
        )

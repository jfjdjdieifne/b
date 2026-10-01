"""Module 6.2A-1 V1.2: factual hypothesis outcome observation, research only."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import Final, Union

import numpy as np
import pandas as pd

from trading_system.decision.narrative import HypothesisType
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import (
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.visibility import (
    AsOfVisibilityProjector,
    FrozenDecisionSnapshotBundle,
    ProjectionContract,
    VISIBILITY_CONTRACT_VERSION,
    VisibleAsOfBundle,
)


class OutcomeObserverError(Exception):
    """Base factual research-observation error."""


class OutcomeContractError(OutcomeObserverError):
    """Snapshot identity or certified provenance contract violation."""


class OutcomeDataError(OutcomeObserverError):
    """Visible market or ledger data cannot support factual observation."""


class SnapshotType(Enum):
    HYPOTHESIS_CREATION_SNAPSHOT = "HYPOTHESIS_CREATION_SNAPSHOT"
    HYPOTHESIS_EVALUATION_SNAPSHOT = "HYPOTHESIS_EVALUATION_SNAPSHOT"


class SegmentType(Enum):
    PRE_ENDPOINT = "PRE_ENDPOINT"
    ENDPOINT_BAR = "ENDPOINT_BAR"
    OBSERVED_THROUGH_AS_OF = "OBSERVED_THROUGH_AS_OF"


OUTCOME_CONTRACT_VERSION: Final = "FACTUAL_HYPOTHESIS_OUTCOME_V1_1"
REFERENCE_PRICE_SOURCE: Final = (
    "CREATION_ROW_COMPLETED_CLOSE_RESEARCH_REFERENCE_MARK"
)
RIGHT_CENSORING_TYPE: Final = "RIGHT_CENSORED_AS_OF_BOUNDARY"
_TERMINAL_STATES: Final = {
    "CONTRADICTED",
    "SUPERSEDED",
    "OBSERVED_DIRECTION_ESTABLISHED",
}
TimelineAdapter = Union[PositionalTimelineAdapter, TimeIndexedTimelineAdapter]

_KEY_SUFFIXES: Final = (
    "information_key_version",
    "bar_position",
    "event_time_utc",
    "information_phase",
    "deterministic_sequence",
)

_SNAPSHOT_COLUMNS: Final = (
    "research_snapshot_id",
    "factual_outcome_id",
    "timeline_id",
    "research_as_of_information_key_version",
    "research_as_of_bar_position",
    "research_as_of_event_time_utc",
    "research_as_of_information_phase",
    "research_as_of_deterministic_sequence",
    "hypothesis_id",
    "hypothesis_type",
    "direction",
    "snapshot_type",
    "snapshot_position",
    "snapshot_information_key_version",
    "snapshot_bar_position",
    "snapshot_event_time_utc",
    "snapshot_information_phase",
    "snapshot_deterministic_sequence",
    "reference_price",
    "reference_price_source",
    "reference_is_execution_price",
    "reference_information_key_version",
    "reference_bar_position",
    "reference_event_time_utc",
    "reference_information_phase",
    "reference_deterministic_sequence",
    "narrative_terminal_state",
    "terminal_ledger_event_id",
    "trigger_relationship_id",
    "terminal_position",
    "terminal_information_key_version",
    "terminal_bar_position",
    "terminal_event_time_utc",
    "terminal_information_phase",
    "terminal_deterministic_sequence",
    "outcome_mature",
    "right_censored_as_of",
    "censoring_type",
    "snapshot_status_known_information_key_version",
    "snapshot_status_known_bar_position",
    "snapshot_status_known_event_time_utc",
    "snapshot_status_known_information_phase",
    "snapshot_status_known_deterministic_sequence",
    "final_outcome_known_information_key_version",
    "final_outcome_known_bar_position",
    "final_outcome_known_event_time_utc",
    "final_outcome_known_information_phase",
    "final_outcome_known_deterministic_sequence",
    "feature_manifest_hash",
    "narrative_manifest_hash",
    "decision_input_slice_hash",
    "decision_snapshot_hash",
    "research_market_slice_hash",
    "research_outcome_hash",
    "outcome_contract_version",
)

_PATH_COLUMNS: Final = (
    "research_snapshot_id",
    "segment_type",
    "segment_start_exclusive_position",
    "segment_end_inclusive_position",
    "segment_observation_count",
    "segment_available",
    "favorable_excursion_fraction",
    "adverse_excursion_fraction",
    "favorable_extreme_price",
    "favorable_extreme_position",
    "adverse_extreme_price",
    "adverse_extreme_position",
    "same_bar_order_ambiguous",
)


@dataclass(frozen=True)
class OutcomeObservationRequest:
    hypothesis_id: int
    snapshot_type: SnapshotType = SnapshotType.HYPOTHESIS_CREATION_SNAPSHOT

    def __post_init__(self) -> None:
        if isinstance(self.hypothesis_id, (bool, np.bool_)) or not isinstance(
            self.hypothesis_id, (int, np.integer)
        ):
            raise OutcomeContractError("hypothesis_id must be integer")
        if int(self.hypothesis_id) < 0:
            raise OutcomeContractError("hypothesis_id must be nonnegative")
        object.__setattr__(self, "hypothesis_id", int(self.hypothesis_id))
        if not isinstance(self.snapshot_type, SnapshotType):
            raise OutcomeContractError("invalid snapshot type")


@dataclass(frozen=True)
class FactualOutcomeResult:
    hypothesis_outcome_snapshots: pd.DataFrame
    outcome_path_segments: pd.DataFrame
    outcome_manifest: pd.DataFrame


def _key_fields(prefix: str, key: InformationKey | None) -> dict:
    if key is None:
        return {
            f"{prefix}_information_key_version": pd.NA,
            f"{prefix}_bar_position": pd.NA,
            f"{prefix}_event_time_utc": pd.NaT,
            f"{prefix}_information_phase": pd.NA,
            f"{prefix}_deterministic_sequence": pd.NA,
        }
    return {
        f"{prefix}_information_key_version": key.information_key_version,
        f"{prefix}_bar_position": key.bar_position,
        f"{prefix}_event_time_utc": (
            pd.NaT if key.event_time_utc is None else key.event_time_utc
        ),
        f"{prefix}_information_phase": key.information_phase.value,
        f"{prefix}_deterministic_sequence": key.deterministic_sequence,
    }


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise OutcomeContractError(f"{name} missing columns: {missing}")


def _typed_snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    integer_columns = [
        column
        for column in result.columns
        if column.endswith("_position")
        or column.endswith("_bar_position")
        or column.endswith("_deterministic_sequence")
        or column in {"hypothesis_id", "terminal_ledger_event_id", "trigger_relationship_id"}
    ]
    string_columns = [
        column
        for column in result.columns
        if column not in integer_columns
        and column
        not in {
            "reference_price",
            "reference_is_execution_price",
            "outcome_mature",
            "right_censored_as_of",
        }
        and not column.endswith("_event_time_utc")
    ]
    for column in integer_columns:
        result[column] = pd.array(result[column], dtype="Int64")
    for column in string_columns:
        result[column] = pd.array(result[column], dtype="string")
    result["reference_price"] = pd.array(result["reference_price"], dtype="Float64")
    for column in (
        "reference_is_execution_price",
        "outcome_mature",
        "right_censored_as_of",
    ):
        result[column] = pd.array(result[column], dtype="boolean")
    for column in [c for c in result.columns if c.endswith("_event_time_utc")]:
        result[column] = pd.to_datetime(result[column], utc=True)
    return result


def _typed_paths(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    for column in (
        "segment_start_exclusive_position",
        "segment_end_inclusive_position",
        "segment_observation_count",
        "favorable_extreme_position",
        "adverse_extreme_position",
    ):
        result[column] = pd.array(result[column], dtype="Int64")
    for column in ("research_snapshot_id", "segment_type"):
        result[column] = pd.array(result[column], dtype="string")
    for column in (
        "segment_available",
        "same_bar_order_ambiguous",
    ):
        result[column] = pd.array(result[column], dtype="boolean")
    for column in (
        "favorable_excursion_fraction",
        "adverse_excursion_fraction",
        "favorable_extreme_price",
        "adverse_extreme_price",
    ):
        result[column] = pd.array(result[column], dtype="Float64")
    return result


class FactualHypothesisOutcomeObserver:
    """Stateless factual observer over a CLOSED VisibleAsOfBundle only."""

    def __init__(self, *, adapter: TimelineAdapter) -> None:
        if not isinstance(
            adapter, (PositionalTimelineAdapter, TimeIndexedTimelineAdapter)
        ):
            raise OutcomeContractError("explicit timeline adapter required")
        self._adapter = adapter
        # V1 is bound to the exact CLOSED 6.2A-0 projection sequences.
        self._projection_contract = ProjectionContract()

    def _validate_visible(self, visible: VisibleAsOfBundle) -> None:
        if not isinstance(visible, VisibleAsOfBundle):
            raise OutcomeContractError("VisibleAsOfBundle required")
        if visible.timeline_id != self._adapter.timeline_id:
            raise OutcomeContractError("observer timeline mismatch")
        if visible.adapter_version != self._adapter.adapter_version:
            raise OutcomeContractError("observer adapter version mismatch")
        if visible.visibility_contract_version != VISIBILITY_CONTRACT_VERSION:
            raise OutcomeContractError("visibility contract version mismatch")
        if visible.research_as_of.information_phase is not InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE:
            raise OutcomeContractError("research as-of must be snapshot-complete")
        try:
            self._adapter.validate_key(visible.research_as_of, visible.market_frame.index)
        except Exception as exc:
            raise OutcomeContractError("invalid visible research as-of") from exc
        self._validate_visible_seal(visible)

    def _validate_visible_seal(self, visible: VisibleAsOfBundle) -> None:
        supplied = FrozenDecisionSnapshotBundle(
            timeline_id=visible.timeline_id,
            evidence_df=visible.evidence_df,
            feature_manifest=visible.feature_manifest,
            narrative_surface=visible.narrative_surface,
            observation_ledger=visible.observation_ledger,
            hypothesis_ledger=visible.hypothesis_ledger,
            relationship_ledger=visible.relationship_ledger,
            relationship_sources=visible.relationship_sources,
            narrative_manifest=visible.narrative_manifest,
            market_frame=visible.market_frame,
        )
        try:
            resealed = AsOfVisibilityProjector(
                adapter=self._adapter, contract=self._projection_contract
            ).project(supplied, visible.research_as_of)
            if resealed.timeline_id != visible.timeline_id:
                raise AssertionError("timeline mismatch")
            if resealed.research_as_of != visible.research_as_of:
                raise AssertionError("research as-of mismatch")
            if resealed.adapter_version != visible.adapter_version:
                raise AssertionError("adapter mismatch")
            if (
                resealed.visibility_contract_version
                != visible.visibility_contract_version
            ):
                raise AssertionError("visibility contract mismatch")
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
            ):
                pd.testing.assert_frame_equal(
                    getattr(resealed, name),
                    getattr(visible, name),
                    check_exact=True,
                )
        except Exception as exc:
            raise OutcomeContractError(
                "visible-bundle seal validation failed"
            ) from exc

    def _creation_identity(self, visible: VisibleAsOfBundle, hypothesis_id: int):
        ledger = visible.hypothesis_ledger
        relationship = visible.relationship_ledger
        _require_columns(
            ledger,
            (
                "ledger_event_id",
                "hypothesis_id",
                "event_position",
                "ledger_event_type",
                "previous_state",
                "new_state",
                "trigger_relationship_id",
                "superseded_by_hypothesis_id",
                "serialization_order",
            ),
            "hypothesis_ledger",
        )
        _require_columns(
            relationship,
            (
                "relationship_id",
                "hypothesis_id",
                "observed_position",
                "evidence_family",
                "evidence_role",
                "relationship_bearing",
                "event_local",
                "primary_category_value",
            ),
            "relationship_ledger",
        )
        created = ledger[
            (ledger["hypothesis_id"] == hypothesis_id)
            & (ledger["ledger_event_type"] == "CREATED")
        ]
        if len(created) != 1:
            raise OutcomeContractError("exactly one visible CREATED event required")
        created_row = created.iloc[0]
        created_position = int(created_row["event_position"])
        creation_batch_history = ledger[
            (ledger["hypothesis_id"] == hypothesis_id)
            & (ledger["event_position"] == created_position)
        ]
        if (
            len(creation_batch_history) != 1
            or str(creation_batch_history.iloc[0]["ledger_event_type"])
            != "CREATED"
            or int(creation_batch_history.iloc[0]["ledger_event_id"])
            != int(created_row["ledger_event_id"])
        ):
            raise OutcomeContractError(
                "malformed same-row lifecycle history at hypothesis creation"
            )
        trigger = created_row["trigger_relationship_id"]
        if pd.isna(trigger):
            raise OutcomeContractError("CREATED event foundation trigger missing")
        trigger_id = int(trigger)
        foundation = relationship[relationship["relationship_id"] == trigger_id]
        if len(foundation) != 1:
            raise OutcomeContractError("visible foundation relationship missing")
        foundation_row = foundation.iloc[0]
        if int(foundation_row["hypothesis_id"]) != hypothesis_id:
            raise OutcomeContractError("foundation belongs to another hypothesis")
        if int(foundation_row["observed_position"]) != created_position:
            raise OutcomeContractError("foundation/creation position mismatch")
        if (
            str(foundation_row["evidence_family"]) != "LOCAL_STRUCTURAL_FOUNDATION"
            or str(foundation_row["evidence_role"]) != "FOUNDATION"
            or str(foundation_row["relationship_bearing"]) != "CONTEXTUALIZES"
            or not bool(foundation_row["event_local"])
        ):
            raise OutcomeContractError("invalid certified foundation relationship")
        hypothesis_name = str(foundation_row["primary_category_value"])
        try:
            hypothesis_type = HypothesisType(hypothesis_name)
        except ValueError as exc:
            raise OutcomeContractError("uncertified hypothesis type") from exc
        definitions = visible.narrative_manifest[
            (visible.narrative_manifest["record_type"] == "HYPOTHESIS_DEFINITION")
            & (visible.narrative_manifest["name"] == hypothesis_type.value)
        ]
        if len(definitions) != 1:
            raise OutcomeContractError("hypothesis definition missing")
        direction = str(definitions.iloc[0]["direction"])
        if direction not in {"UP", "DOWN"}:
            raise OutcomeContractError("invalid certified hypothesis direction")
        creation_key = self._adapter.key_for_position(
            visible.market_frame.index,
            created_position,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            int(self._projection_contract.analytical_batch_sequence),
        )
        return created_row, foundation_row, hypothesis_type, direction, creation_key

    def _terminal_identity(
        self,
        visible: VisibleAsOfBundle,
        hypothesis_id: int,
        creation_key: InformationKey,
    ):
        ledger = visible.hypothesis_ledger
        terminal = ledger[
            (ledger["hypothesis_id"] == hypothesis_id)
            & (ledger["new_state"].isin(_TERMINAL_STATES))
        ]
        if len(terminal) > 1:
            raise OutcomeContractError(
                "multiple terminal lifecycle events for one hypothesis"
            )
        if terminal.empty:
            return None, None
        row = terminal.iloc[0]
        position = int(row["event_position"])
        terminal_key = self._adapter.key_for_position(
            visible.market_frame.index,
            position,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            int(self._projection_contract.analytical_batch_sequence),
        )
        if not terminal_key > creation_key:
            raise OutcomeContractError("terminal event must be later than creation")
        trigger = row["trigger_relationship_id"]
        if pd.isna(trigger):
            raise OutcomeContractError("terminal trigger relationship missing")
        trigger_id = int(trigger)
        relation = visible.relationship_ledger[
            visible.relationship_ledger["relationship_id"] == trigger_id
        ]
        if len(relation) != 1:
            raise OutcomeContractError("terminal trigger relationship not visible")
        relation_row = relation.iloc[0]
        state = str(row["new_state"])
        relation_hypothesis_id = int(relation_row["hypothesis_id"])
        if state == "SUPERSEDED":
            replacement = row["superseded_by_hypothesis_id"]
            if pd.isna(replacement) or relation_hypothesis_id != int(replacement):
                raise OutcomeContractError("supersession trigger provenance mismatch")
            replacement_id = int(replacement)
            replacement_created = ledger[
                (ledger["hypothesis_id"] == replacement_id)
                & (ledger["ledger_event_type"] == "CREATED")
            ]
            if len(replacement_created) != 1:
                raise OutcomeContractError(
                    "supersession replacement CREATED event missing"
                )
            replacement_row = replacement_created.iloc[0]
            if int(replacement_row["event_position"]) != position:
                raise OutcomeContractError(
                    "supersession replacement creation position mismatch"
                )
            replacement_trigger = replacement_row["trigger_relationship_id"]
            if pd.isna(replacement_trigger) or int(replacement_trigger) != trigger_id:
                raise OutcomeContractError(
                    "supersession replacement foundation trigger mismatch"
                )
            if str(relation_row["evidence_role"]) != "FOUNDATION":
                raise OutcomeContractError("supersession trigger is not foundation")
        elif relation_hypothesis_id != hypothesis_id:
            raise OutcomeContractError("terminal trigger belongs to another hypothesis")
        if int(relation_row["observed_position"]) != position:
            raise OutcomeContractError("terminal trigger position mismatch")
        return row, terminal_key

    def _reference(self, visible: VisibleAsOfBundle, created_position: int):
        if "close" not in visible.market_frame.columns:
            raise OutcomeDataError("market close column required")
        value = visible.market_frame["close"].iloc[created_position]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise OutcomeDataError("reference close must be numeric")
        reference = float(value)
        if not np.isfinite(reference) or reference <= 0:
            raise OutcomeDataError("reference close must be finite and positive")
        key = self._adapter.key_for_position(
            visible.market_frame.index,
            created_position,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            int(self._projection_contract.market_row_sequence),
        )
        return reference, key

    def _decision_projection(
        self, visible: VisibleAsOfBundle, creation_key: InformationKey
    ) -> VisibleAsOfBundle:
        frozen_visible = FrozenDecisionSnapshotBundle(
            timeline_id=visible.timeline_id,
            evidence_df=visible.evidence_df,
            feature_manifest=visible.feature_manifest,
            narrative_surface=visible.narrative_surface,
            observation_ledger=visible.observation_ledger,
            hypothesis_ledger=visible.hypothesis_ledger,
            relationship_ledger=visible.relationship_ledger,
            relationship_sources=visible.relationship_sources,
            narrative_manifest=visible.narrative_manifest,
            market_frame=visible.market_frame,
        )
        return AsOfVisibilityProjector(
            adapter=self._adapter, contract=self._projection_contract
        ).project(frozen_visible, creation_key)

    def _decision_hashes(
        self,
        visible: VisibleAsOfBundle,
        creation_projection: VisibleAsOfBundle,
        hypothesis_id: int,
        created_position: int,
        creation_key: InformationKey,
        reference: float,
        reference_key: InformationKey,
    ):
        feature_manifest_hash = canonical_sha256(
            domain="FEATURE_MANIFEST_V1", payload=visible.feature_manifest
        )
        narrative_manifest_hash = canonical_sha256(
            domain="NARRATIVE_MANIFEST_V1", payload=visible.narrative_manifest
        )
        index_label = visible.market_frame.index[created_position]
        reference_identity = {
            "timeline_id": visible.timeline_id,
            "created_position": created_position,
            "index_label": index_label,
            "reference_price": reference,
            "reference_price_source": REFERENCE_PRICE_SOURCE,
            "reference_is_execution_price": False,
            "reference_key": reference_key,
        }
        decision_input_slice_hash = canonical_sha256(
            domain="DECISION_INPUT_SLICE_V1_2",
            payload=reference_identity,
        )
        creation_relationships = creation_projection.relationship_ledger[
            (creation_projection.relationship_ledger["hypothesis_id"] == hypothesis_id)
            & (
                creation_projection.relationship_ledger["observed_position"]
                == created_position
            )
        ].reset_index(drop=True)
        relationship_ids = set(creation_relationships["relationship_id"].tolist())
        creation_sources = creation_projection.relationship_sources[
            creation_projection.relationship_sources["relationship_id"].isin(
                relationship_ids
            )
        ].reset_index(drop=True)
        creation_ledger = creation_projection.hypothesis_ledger[
            (creation_projection.hypothesis_ledger["hypothesis_id"] == hypothesis_id)
            & (creation_projection.hypothesis_ledger["event_position"] == created_position)
        ].reset_index(drop=True)
        if (
            len(creation_ledger) != 1
            or str(creation_ledger.iloc[0]["ledger_event_type"]) != "CREATED"
        ):
            raise OutcomeContractError(
                "creation decision snapshot requires exactly one CREATED event"
            )
        creation_observations = creation_projection.observation_ledger[
            creation_projection.observation_ledger["observed_position"]
            == created_position
        ].reset_index(drop=True)
        decision_snapshot_hash = canonical_sha256(
            domain="HYPOTHESIS_CREATION_DECISION_SNAPSHOT_V1_2",
            payload={
                "timeline_id": visible.timeline_id,
                "hypothesis_id": hypothesis_id,
                "snapshot_type": SnapshotType.HYPOTHESIS_CREATION_SNAPSHOT.value,
                "creation_key": creation_key,
                "evidence_row": creation_projection.evidence_df.iloc[
                    [created_position]
                ],
                "narrative_row": creation_projection.narrative_surface.iloc[
                    [created_position]
                ],
                "created_ledger_event": creation_ledger,
                "same_row_observations": creation_observations,
                "same_hypothesis_same_row_relationships": creation_relationships,
                "same_row_relationship_sources": creation_sources,
                "feature_manifest_hash": feature_manifest_hash,
                "narrative_manifest_hash": narrative_manifest_hash,
                "reference_identity": reference_identity,
                "decision_input_slice_hash": decision_input_slice_hash,
            },
        )
        return (
            feature_manifest_hash,
            narrative_manifest_hash,
            decision_input_slice_hash,
            decision_snapshot_hash,
        )

    def _validate_path_prices(self, frame: pd.DataFrame) -> None:
        _require_columns(frame, ("high", "low"), "market_frame")
        for column in ("high", "low"):
            series = frame[column]
            if (
                pd.api.types.is_bool_dtype(series.dtype)
                or not pd.api.types.is_numeric_dtype(series.dtype)
            ):
                raise OutcomeDataError(f"path {column} must be numeric")
        high = frame["high"].to_numpy(dtype=np.float64, na_value=np.nan)
        low = frame["low"].to_numpy(dtype=np.float64, na_value=np.nan)
        if not np.isfinite(high).all() or not np.isfinite(low).all():
            raise OutcomeDataError("path prices must be finite")
        if (high <= 0).any() or (low <= 0).any() or (high < low).any():
            raise OutcomeDataError("invalid positive path geometry")

    def _segment_row(
        self,
        *,
        research_snapshot_id: str,
        segment_type: SegmentType,
        start_exclusive: int,
        end_inclusive: int,
        positions: list[int],
        market: pd.DataFrame,
        reference: float,
        direction: str,
    ) -> dict:
        if not positions:
            return {
                "research_snapshot_id": research_snapshot_id,
                "segment_type": segment_type.value,
                "segment_start_exclusive_position": start_exclusive,
                "segment_end_inclusive_position": end_inclusive,
                "segment_observation_count": 0,
                "segment_available": False,
                "favorable_excursion_fraction": np.nan,
                "adverse_excursion_fraction": np.nan,
                "favorable_extreme_price": np.nan,
                "favorable_extreme_position": pd.NA,
                "adverse_extreme_price": np.nan,
                "adverse_extreme_position": pd.NA,
                "same_bar_order_ambiguous": False,
            }
        frame = market.iloc[positions]
        self._validate_path_prices(frame)
        high = frame["high"].to_numpy(dtype=np.float64)
        low = frame["low"].to_numpy(dtype=np.float64)
        if direction == "UP":
            favorable_index = int(np.argmax(high))
            adverse_index = int(np.argmin(low))
            favorable_price = float(high[favorable_index])
            adverse_price = float(low[adverse_index])
            favorable = max(0.0, favorable_price / reference - 1.0)
            adverse = max(0.0, 1.0 - adverse_price / reference)
        else:
            favorable_index = int(np.argmin(low))
            adverse_index = int(np.argmax(high))
            favorable_price = float(low[favorable_index])
            adverse_price = float(high[adverse_index])
            favorable = max(0.0, 1.0 - favorable_price / reference)
            adverse = max(0.0, adverse_price / reference - 1.0)
        return {
            "research_snapshot_id": research_snapshot_id,
            "segment_type": segment_type.value,
            "segment_start_exclusive_position": start_exclusive,
            "segment_end_inclusive_position": end_inclusive,
            "segment_observation_count": len(positions),
            "segment_available": True,
            "favorable_excursion_fraction": favorable,
            "adverse_excursion_fraction": adverse,
            "favorable_extreme_price": favorable_price,
            "favorable_extreme_position": positions[favorable_index],
            "adverse_extreme_price": adverse_price,
            "adverse_extreme_position": positions[adverse_index],
            "same_bar_order_ambiguous": bool(
                np.any((high > reference) & (low < reference))
            ),
        }

    def observe(
        self,
        visible: VisibleAsOfBundle,
        request: OutcomeObservationRequest,
    ) -> FactualOutcomeResult:
        self._validate_visible(visible)
        if not isinstance(request, OutcomeObservationRequest):
            raise OutcomeContractError("OutcomeObservationRequest required")
        if request.snapshot_type is not SnapshotType.HYPOTHESIS_CREATION_SNAPSHOT:
            raise OutcomeContractError("V1 supports creation snapshots only")

        (
            created_row,
            foundation_row,
            hypothesis_type,
            direction,
            creation_key,
        ) = self._creation_identity(visible, request.hypothesis_id)
        created_position = int(created_row["event_position"])
        reference, reference_key = self._reference(visible, created_position)
        if not reference_key <= creation_key:
            raise OutcomeContractError("reference is not available by creation")

        creation_projection = self._decision_projection(visible, creation_key)
        (
            feature_manifest_hash,
            narrative_manifest_hash,
            decision_input_slice_hash,
            decision_snapshot_hash,
        ) = self._decision_hashes(
            visible,
            creation_projection,
            request.hypothesis_id,
            created_position,
            creation_key,
            reference,
            reference_key,
        )

        terminal_row, terminal_key = self._terminal_identity(
            visible, request.hypothesis_id, creation_key
        )
        mature = terminal_row is not None
        if mature:
            terminal_position = int(terminal_row["event_position"])
            terminal_state = str(terminal_row["new_state"])
            terminal_event_id = int(terminal_row["ledger_event_id"])
            trigger_relationship_id = int(terminal_row["trigger_relationship_id"])
            path_positions = list(range(created_position + 1, terminal_position + 1))
        else:
            terminal_position = None
            terminal_state = None
            terminal_event_id = None
            trigger_relationship_id = None
            path_positions = list(
                range(created_position + 1, visible.research_as_of.bar_position + 1)
            )

        market_slice = visible.market_frame.iloc[path_positions][["high", "low"]].copy(
            deep=True
        )
        if path_positions:
            self._validate_path_prices(market_slice)
        research_market_slice_hash = canonical_sha256(
            domain="RESEARCH_MARKET_SLICE_V1",
            payload={
                "timeline_id": visible.timeline_id,
                "start_exclusive": created_position,
                "end_inclusive": (
                    terminal_position
                    if mature
                    else visible.research_as_of.bar_position
                ),
                "market_slice": market_slice,
            },
        )
        research_snapshot_id = canonical_sha256(
            domain="RESEARCH_SNAPSHOT_ID_V1_2",
            payload={
                "decision_snapshot_hash": decision_snapshot_hash,
                "hypothesis_id": request.hypothesis_id,
                "snapshot_type": request.snapshot_type.value,
                "research_as_of": visible.research_as_of,
                "outcome_contract_version": OUTCOME_CONTRACT_VERSION,
            },
        )

        segment_rows: list[dict] = []
        if mature:
            pre_positions = list(range(created_position + 1, terminal_position))
            segment_rows.append(
                self._segment_row(
                    research_snapshot_id=research_snapshot_id,
                    segment_type=SegmentType.PRE_ENDPOINT,
                    start_exclusive=created_position,
                    end_inclusive=terminal_position - 1,
                    positions=pre_positions,
                    market=visible.market_frame,
                    reference=reference,
                    direction=direction,
                )
            )
            segment_rows.append(
                self._segment_row(
                    research_snapshot_id=research_snapshot_id,
                    segment_type=SegmentType.ENDPOINT_BAR,
                    start_exclusive=terminal_position - 1,
                    end_inclusive=terminal_position,
                    positions=[terminal_position],
                    market=visible.market_frame,
                    reference=reference,
                    direction=direction,
                )
            )
        else:
            segment_rows.append(
                self._segment_row(
                    research_snapshot_id=research_snapshot_id,
                    segment_type=SegmentType.OBSERVED_THROUGH_AS_OF,
                    start_exclusive=created_position,
                    end_inclusive=visible.research_as_of.bar_position,
                    positions=path_positions,
                    market=visible.market_frame,
                    reference=reference,
                    direction=direction,
                )
            )
        segments = _typed_paths(pd.DataFrame(segment_rows, columns=_PATH_COLUMNS))

        factual_outcome_id = (
            canonical_sha256(
                domain="MATURE_FACTUAL_OUTCOME_ID_V1_2",
                payload={
                    "decision_snapshot_hash": decision_snapshot_hash,
                    "hypothesis_id": request.hypothesis_id,
                    "terminal_state": terminal_state,
                    "terminal_event_id": terminal_event_id,
                    "trigger_relationship_id": trigger_relationship_id,
                    "terminal_key": terminal_key,
                    "research_market_slice_hash": research_market_slice_hash,
                    "segments": segments.drop(columns=["research_snapshot_id"]),
                    "outcome_contract_version": OUTCOME_CONTRACT_VERSION,
                },
            )
            if mature
            else pd.NA
        )
        research_outcome_hash = canonical_sha256(
            domain="RESEARCH_OUTCOME_V1_2",
            payload={
                "research_snapshot_id": research_snapshot_id,
                "factual_outcome_id": factual_outcome_id,
                "research_as_of": visible.research_as_of,
                "censoring_type": None if mature else RIGHT_CENSORING_TYPE,
                "research_market_slice_hash": research_market_slice_hash,
                "segments": segments,
                "outcome_contract_version": OUTCOME_CONTRACT_VERSION,
            },
        )

        status_key = terminal_key if mature else visible.research_as_of
        snapshot_row = {
            "research_snapshot_id": research_snapshot_id,
            "factual_outcome_id": factual_outcome_id,
            "timeline_id": visible.timeline_id,
            **_key_fields("research_as_of", visible.research_as_of),
            "hypothesis_id": request.hypothesis_id,
            "hypothesis_type": hypothesis_type.value,
            "direction": direction,
            "snapshot_type": request.snapshot_type.value,
            "snapshot_position": created_position,
            **_key_fields("snapshot", creation_key),
            "reference_price": reference,
            "reference_price_source": REFERENCE_PRICE_SOURCE,
            "reference_is_execution_price": False,
            **_key_fields("reference", reference_key),
            "narrative_terminal_state": terminal_state,
            "terminal_ledger_event_id": terminal_event_id,
            "trigger_relationship_id": trigger_relationship_id,
            "terminal_position": terminal_position,
            **_key_fields("terminal", terminal_key),
            "outcome_mature": mature,
            "right_censored_as_of": not mature,
            "censoring_type": None if mature else RIGHT_CENSORING_TYPE,
            **_key_fields("snapshot_status_known", status_key),
            **_key_fields("final_outcome_known", terminal_key),
            "feature_manifest_hash": feature_manifest_hash,
            "narrative_manifest_hash": narrative_manifest_hash,
            "decision_input_slice_hash": decision_input_slice_hash,
            "decision_snapshot_hash": decision_snapshot_hash,
            "research_market_slice_hash": research_market_slice_hash,
            "research_outcome_hash": research_outcome_hash,
            "outcome_contract_version": OUTCOME_CONTRACT_VERSION,
        }
        snapshot = _typed_snapshot(
            pd.DataFrame([snapshot_row], columns=_SNAPSHOT_COLUMNS)
        )
        return FactualOutcomeResult(
            hypothesis_outcome_snapshots=snapshot,
            outcome_path_segments=segments,
            outcome_manifest=outcome_contract_manifest(),
        )


def outcome_contract_manifest() -> pd.DataFrame:
    rows = [
        {
            "record_type": "SNAPSHOT_COLUMN",
            "name": column,
            "value": "FACTUAL_RESEARCH_ONLY",
            "serialization_order": order,
        }
        for order, column in enumerate(_SNAPSHOT_COLUMNS)
    ]
    offset = len(rows)
    rows.extend(
        {
            "record_type": "PATH_COLUMN",
            "name": column,
            "value": "FACTUAL_RESEARCH_ONLY",
            "serialization_order": offset + order,
        }
        for order, column in enumerate(_PATH_COLUMNS)
    )
    return pd.DataFrame(
        rows,
        columns=("record_type", "name", "value", "serialization_order"),
    )

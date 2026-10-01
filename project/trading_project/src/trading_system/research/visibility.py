"""Module 6.2A-0 V1.2: research as-of visibility projection only.

This module filters frozen causal records before future research semantics may
consume them. It does not derive or interpret outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Union

import numpy as np
import pandas as pd

from trading_system.research.information_time import (
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.manifest_identity import (
    ManifestIdentityError,
    validate_feature_manifest_identity,
    validate_narrative_manifest_identity,
)


class VisibilityError(Exception):
    """Base as-of visibility contract error."""


class VisibilitySchemaError(VisibilityError):
    """Frozen bundle schema, identity, or referential-integrity error."""


class VisibilityProjectionError(VisibilityError):
    """Invalid explicit as-of projection request."""


TimelineAdapter = Union[PositionalTimelineAdapter, TimeIndexedTimelineAdapter]
VISIBILITY_CONTRACT_VERSION: Final = "RESEARCH_VISIBILITY_V1_2"

_OBSERVATION_REQUIRED: Final = (
    "observation_id",
    "observed_position",
    "same_row_batch_id",
    "serialization_order",
)
_HYPOTHESIS_REQUIRED: Final = (
    "ledger_event_id",
    "event_position",
    "same_row_batch_id",
    "serialization_order",
)
_RELATIONSHIP_REQUIRED: Final = (
    "relationship_id",
    "observed_position",
    "same_row_batch_id",
    "serialization_order",
)
_RELATIONSHIP_SOURCE_REQUIRED: Final = ("relationship_id",)


@dataclass(frozen=True)
class ProjectionContract:
    contract_version: str = VISIBILITY_CONTRACT_VERSION
    market_row_sequence: int = 0
    analytical_batch_sequence: int = 1

    def __post_init__(self) -> None:
        if self.contract_version != VISIBILITY_CONTRACT_VERSION:
            raise VisibilityProjectionError("unsupported visibility contract version")
        for value in (self.market_row_sequence, self.analytical_batch_sequence):
            if isinstance(value, (bool, np.bool_)) or not isinstance(
                value, (int, np.integer)
            ):
                raise VisibilityProjectionError("projection sequences must be integers")
            if int(value) < 0:
                raise VisibilityProjectionError("projection sequences must be nonnegative")
        if int(self.market_row_sequence) >= int(self.analytical_batch_sequence):
            raise VisibilityProjectionError(
                "market dependency sequence must precede analytical batch"
            )


@dataclass(frozen=True)
class FrozenDecisionSnapshotBundle:
    timeline_id: str
    evidence_df: pd.DataFrame
    feature_manifest: pd.DataFrame
    narrative_surface: pd.DataFrame
    observation_ledger: pd.DataFrame
    hypothesis_ledger: pd.DataFrame
    relationship_ledger: pd.DataFrame
    relationship_sources: pd.DataFrame
    narrative_manifest: pd.DataFrame
    market_frame: pd.DataFrame


@dataclass(frozen=True)
class VisibleAsOfBundle:
    timeline_id: str
    research_as_of: InformationKey
    adapter_version: str
    visibility_contract_version: str
    evidence_df: pd.DataFrame
    feature_manifest: pd.DataFrame
    narrative_surface: pd.DataFrame
    observation_ledger: pd.DataFrame
    hypothesis_ledger: pd.DataFrame
    relationship_ledger: pd.DataFrame
    relationship_sources: pd.DataFrame
    narrative_manifest: pd.DataFrame
    market_frame: pd.DataFrame


class AsOfVisibilityProjector:
    """Stateless projector configured by one explicit immutable adapter."""

    def __init__(
        self,
        *,
        adapter: TimelineAdapter,
        contract: ProjectionContract = ProjectionContract(),
    ) -> None:
        if not isinstance(
            adapter, (PositionalTimelineAdapter, TimeIndexedTimelineAdapter)
        ):
            raise VisibilityProjectionError("explicit supported timeline adapter required")
        if not isinstance(contract, ProjectionContract):
            raise VisibilityProjectionError("invalid projection contract")
        self._adapter = adapter
        self._contract = contract

    @staticmethod
    def _validate_frame(frame: pd.DataFrame, name: str) -> None:
        if not isinstance(frame, pd.DataFrame) or frame.columns.has_duplicates:
            raise VisibilitySchemaError(f"invalid {name}")

    @staticmethod
    def _require_columns(
        frame: pd.DataFrame, required: tuple[str, ...], name: str
    ) -> None:
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise VisibilitySchemaError(f"{name} missing projection columns: {missing}")

    @staticmethod
    def _integer_values(
        frame: pd.DataFrame, column: str, name: str
    ) -> list[int]:
        series = frame[column]
        if (
            pd.api.types.is_bool_dtype(series.dtype)
            or not pd.api.types.is_integer_dtype(series.dtype)
            or series.isna().any()
        ):
            raise VisibilitySchemaError(f"{name}.{column} must be nonmissing integer")
        values = [int(value) for value in series.tolist()]
        if any(value < 0 for value in values):
            raise VisibilitySchemaError(f"{name}.{column} must be nonnegative")
        return values

    def _validate_ledger(
        self,
        frame: pd.DataFrame,
        *,
        name: str,
        required: tuple[str, ...],
        position_column: str,
        identity_column: str,
        row_count: int,
    ) -> None:
        self._validate_frame(frame, name)
        self._require_columns(frame, required, name)
        positions = self._integer_values(frame, position_column, name)
        batches = self._integer_values(frame, "same_row_batch_id", name)
        serials = self._integer_values(frame, "serialization_order", name)
        identities = self._integer_values(frame, identity_column, name)
        if any(position >= row_count for position in positions):
            raise VisibilitySchemaError(f"{name} position outside row identity")
        if positions != batches:
            raise VisibilitySchemaError(f"{name} same-row batch mismatch")
        if len(identities) != len(set(identities)):
            raise VisibilitySchemaError(f"duplicate {name} identity")
        # Explicit read documents that ordering metadata, not payload, was validated.
        if any(serial < 0 for serial in serials):
            raise VisibilitySchemaError(f"invalid {name} serialization")

    def _validate_bundle(self, bundle: FrozenDecisionSnapshotBundle) -> None:
        if not isinstance(bundle, FrozenDecisionSnapshotBundle):
            raise VisibilitySchemaError("FrozenDecisionSnapshotBundle required")
        if bundle.timeline_id != self._adapter.timeline_id:
            raise VisibilitySchemaError("bundle timeline does not match adapter")
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
            self._validate_frame(getattr(bundle, name), name)
        try:
            validate_feature_manifest_identity(bundle.feature_manifest)
            validate_narrative_manifest_identity(bundle.narrative_manifest)
        except ManifestIdentityError as exc:
            raise VisibilitySchemaError("static manifest identity mismatch") from exc

        row_count = len(bundle.market_frame)
        if len(bundle.evidence_df) != row_count or len(bundle.narrative_surface) != row_count:
            raise VisibilitySchemaError("row-aligned table length mismatch")
        if not bundle.evidence_df.index.equals(bundle.market_frame.index):
            raise VisibilitySchemaError("evidence/market index identity mismatch")
        if not bundle.narrative_surface.index.equals(bundle.market_frame.index):
            raise VisibilitySchemaError("narrative/market index identity mismatch")
        self._adapter.validate_index(bundle.market_frame.index)

        self._validate_ledger(
            bundle.observation_ledger,
            name="observation_ledger",
            required=_OBSERVATION_REQUIRED,
            position_column="observed_position",
            identity_column="observation_id",
            row_count=row_count,
        )
        self._validate_ledger(
            bundle.hypothesis_ledger,
            name="hypothesis_ledger",
            required=_HYPOTHESIS_REQUIRED,
            position_column="event_position",
            identity_column="ledger_event_id",
            row_count=row_count,
        )
        self._validate_ledger(
            bundle.relationship_ledger,
            name="relationship_ledger",
            required=_RELATIONSHIP_REQUIRED,
            position_column="observed_position",
            identity_column="relationship_id",
            row_count=row_count,
        )

        self._require_columns(
            bundle.relationship_sources,
            _RELATIONSHIP_SOURCE_REQUIRED,
            "relationship_sources",
        )
        source_relationship_ids = self._integer_values(
            bundle.relationship_sources,
            "relationship_id",
            "relationship_sources",
        )
        relationship_ids = set(
            self._integer_values(
                bundle.relationship_ledger,
                "relationship_id",
                "relationship_ledger",
            )
        )
        if not set(source_relationship_ids).issubset(relationship_ids):
            raise VisibilitySchemaError("orphan relationship source")

    def _position_visible(
        self,
        index: pd.Index,
        position: int,
        *,
        sequence: int,
        research_as_of: InformationKey,
    ) -> bool:
        key = self._adapter.key_for_position(
            index,
            position,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            sequence,
        )
        return key <= research_as_of

    def _row_mask(
        self,
        index: pd.Index,
        *,
        sequence: int,
        research_as_of: InformationKey,
    ) -> np.ndarray:
        return np.fromiter(
            (
                self._position_visible(
                    index,
                    position,
                    sequence=sequence,
                    research_as_of=research_as_of,
                )
                for position in range(len(index))
            ),
            dtype=bool,
            count=len(index),
        )

    def _ledger_mask(
        self,
        frame: pd.DataFrame,
        position_column: str,
        market_index: pd.Index,
        research_as_of: InformationKey,
    ) -> np.ndarray:
        # Only projection metadata is read before the payload is sliced away.
        positions = [int(value) for value in frame[position_column].tolist()]
        return np.fromiter(
            (
                self._position_visible(
                    market_index,
                    position,
                    sequence=int(self._contract.analytical_batch_sequence),
                    research_as_of=research_as_of,
                )
                for position in positions
            ),
            dtype=bool,
            count=len(positions),
        )

    @staticmethod
    def _independent_rows(frame: pd.DataFrame, mask: np.ndarray) -> pd.DataFrame:
        return frame.loc[mask].copy(deep=True)

    @staticmethod
    def _independent_ledger(frame: pd.DataFrame, mask: np.ndarray) -> pd.DataFrame:
        return frame.loc[mask].copy(deep=True).reset_index(drop=True)

    def project(
        self,
        bundle: FrozenDecisionSnapshotBundle,
        research_as_of: InformationKey,
    ) -> VisibleAsOfBundle:
        self._validate_bundle(bundle)
        if not isinstance(research_as_of, InformationKey):
            raise VisibilityProjectionError("explicit research as-of InformationKey required")
        try:
            self._adapter.validate_key(research_as_of, bundle.market_frame.index)
        except Exception as exc:
            raise VisibilityProjectionError("invalid research as-of key") from exc

        market_mask = self._row_mask(
            bundle.market_frame.index,
            sequence=int(self._contract.market_row_sequence),
            research_as_of=research_as_of,
        )
        analytical_mask = self._row_mask(
            bundle.market_frame.index,
            sequence=int(self._contract.analytical_batch_sequence),
            research_as_of=research_as_of,
        )
        observation_mask = self._ledger_mask(
            bundle.observation_ledger,
            "observed_position",
            bundle.market_frame.index,
            research_as_of,
        )
        hypothesis_mask = self._ledger_mask(
            bundle.hypothesis_ledger,
            "event_position",
            bundle.market_frame.index,
            research_as_of,
        )
        relationship_mask = self._ledger_mask(
            bundle.relationship_ledger,
            "observed_position",
            bundle.market_frame.index,
            research_as_of,
        )

        visible_relationships = self._independent_ledger(
            bundle.relationship_ledger, relationship_mask
        )
        visible_relationship_ids = set(
            int(value) for value in visible_relationships["relationship_id"].tolist()
        )
        source_parent_ids = [
            int(value) for value in bundle.relationship_sources["relationship_id"].tolist()
        ]
        source_mask = np.fromiter(
            (parent_id in visible_relationship_ids for parent_id in source_parent_ids),
            dtype=bool,
            count=len(source_parent_ids),
        )

        return VisibleAsOfBundle(
            timeline_id=bundle.timeline_id,
            research_as_of=research_as_of,
            adapter_version=self._adapter.adapter_version,
            visibility_contract_version=self._contract.contract_version,
            evidence_df=self._independent_rows(bundle.evidence_df, analytical_mask),
            feature_manifest=bundle.feature_manifest.copy(deep=True),
            narrative_surface=self._independent_rows(
                bundle.narrative_surface, analytical_mask
            ),
            observation_ledger=self._independent_ledger(
                bundle.observation_ledger, observation_mask
            ),
            hypothesis_ledger=self._independent_ledger(
                bundle.hypothesis_ledger, hypothesis_mask
            ),
            relationship_ledger=visible_relationships,
            relationship_sources=self._independent_ledger(
                bundle.relationship_sources, source_mask
            ),
            narrative_manifest=bundle.narrative_manifest.copy(deep=True),
            market_frame=self._independent_rows(bundle.market_frame, market_mask),
        )


def visibility_contract_manifest() -> pd.DataFrame:
    rules = (
        ("evidence_df", "ROW_COMPLETED_ANALYTICAL_BATCH"),
        ("narrative_surface", "ROW_COMPLETED_ANALYTICAL_BATCH"),
        ("observation_ledger", "OBSERVED_POSITION_ATOMIC_BATCH"),
        ("hypothesis_ledger", "EVENT_POSITION_ATOMIC_BATCH"),
        ("relationship_ledger", "OBSERVED_POSITION_ATOMIC_BATCH"),
        ("relationship_sources", "VISIBLE_PARENT_RELATIONSHIP_ONLY"),
        ("market_frame", "ROW_COMPLETED_MARKET_DEPENDENCY"),
        ("feature_manifest", "STATIC_AFTER_IDENTITY_VALIDATION"),
        ("narrative_manifest", "STATIC_AFTER_IDENTITY_VALIDATION"),
        ("active_hypotheses", "EXCLUDED_NON_HISTORICAL_FINAL_STATE"),
    )
    rows = [
        {
            "record_type": "PROJECTION_RULE",
            "name": name,
            "value": value,
            "serialization_order": order,
        }
        for order, (name, value) in enumerate(rules)
    ]
    rows.append(
        {
            "record_type": "PACKAGE_DEPENDENCY_RULE",
            "name": "LIVE_TO_RESEARCH_IMPORT",
            "value": "FORBIDDEN",
            "serialization_order": len(rows),
        }
    )
    return pd.DataFrame(
        rows,
        columns=("record_type", "name", "value", "serialization_order"),
    )

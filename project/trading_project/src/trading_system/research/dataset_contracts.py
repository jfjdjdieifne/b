"""Module 6.2A-3 V1.1 raw research-dataset contracts; no preprocessing or model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

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
from trading_system.research.manifest_identity import (
    validate_feature_manifest_identity,
    validate_narrative_manifest_identity,
)
from trading_system.research.outcome_observer import (
    REFERENCE_PRICE_SOURCE,
    SnapshotType,
)
from trading_system.research.visibility import (
    AsOfVisibilityProjector,
    FrozenDecisionSnapshotBundle,
    ProjectionContract,
    VisibleAsOfBundle,
)


class DatasetContractError(Exception):
    """Dataset identity, fold, schema, or causal-boundary violation."""


class DatasetDataError(Exception):
    """Conflicting joins or malformed factual feature/target data."""


DATASET_CONTRACT_VERSION = "CAUSAL_RESEARCH_DATASET_V1"
FEATURE_SNAPSHOT_CONTRACT_VERSION = "FROZEN_DECISION_FEATURE_SNAPSHOT_V1"
TimelineAdapter = Union[PositionalTimelineAdapter, TimeIndexedTimelineAdapter]


@dataclass(frozen=True)
class WalkForwardFoldSpec:
    fold_id: str
    timeline_id: str
    train_cutoff: InformationKey
    test_creation_end_inclusive: InformationKey
    test_label_as_of: InformationKey | None = None
    fold_contract_version: str = DATASET_CONTRACT_VERSION

    def __post_init__(self):
        if not isinstance(self.fold_id, str) or not self.fold_id:
            raise DatasetContractError("fold_id must be nonempty string")
        if not isinstance(self.timeline_id, str) or not self.timeline_id:
            raise DatasetContractError("timeline_id must be nonempty string")
        if self.fold_contract_version != DATASET_CONTRACT_VERSION:
            raise DatasetContractError("unsupported fold contract version")
        if not isinstance(self.train_cutoff, InformationKey) or not isinstance(
            self.test_creation_end_inclusive, InformationKey
        ):
            raise DatasetContractError("explicit InformationKey fold boundaries required")
        if (
            self.train_cutoff.timeline_id != self.timeline_id
            or self.test_creation_end_inclusive.timeline_id != self.timeline_id
        ):
            raise DatasetContractError("fold timeline mismatch")
        if not self.train_cutoff < self.test_creation_end_inclusive:
            raise DatasetContractError("train cutoff must precede test creation end")
        if self.test_label_as_of is not None:
            if not isinstance(self.test_label_as_of, InformationKey):
                raise DatasetContractError("test_label_as_of must be InformationKey")
            if self.test_label_as_of.timeline_id != self.timeline_id:
                raise DatasetContractError("test label timeline mismatch")
            if self.test_label_as_of < self.test_creation_end_inclusive:
                raise DatasetContractError("test label as-of precedes test creation end")

    @property
    def test_creation_start_exclusive(self) -> InformationKey:
        return self.train_cutoff


@dataclass(frozen=True)
class FrozenDecisionFeatureSnapshot:
    timeline_id: str
    hypothesis_id: int
    hypothesis_type: str
    direction: str
    snapshot_type: str
    snapshot_information_key: InformationKey
    reference_price: float
    reference_information_key: InformationKey
    reference_index_label: object
    evidence_row: pd.DataFrame
    narrative_row: pd.DataFrame
    created_ledger_event: pd.DataFrame
    same_row_observations: pd.DataFrame
    same_row_relationships: pd.DataFrame
    relationship_sources: pd.DataFrame
    feature_manifest: pd.DataFrame
    narrative_manifest: pd.DataFrame
    decision_input_slice_hash: str
    decision_snapshot_hash: str
    feature_snapshot_contract_version: str = FEATURE_SNAPSHOT_CONTRACT_VERSION

    def verify(self) -> None:
        if self.feature_snapshot_contract_version != FEATURE_SNAPSHOT_CONTRACT_VERSION:
            raise DatasetContractError("feature snapshot contract version mismatch")
        if not isinstance(self.hypothesis_id, int) or isinstance(self.hypothesis_id, bool):
            raise DatasetContractError("hypothesis_id must be integer")
        if self.hypothesis_id < 0:
            raise DatasetContractError("hypothesis_id must be nonnegative")
        if self.snapshot_type != SnapshotType.HYPOTHESIS_CREATION_SNAPSHOT.value:
            raise DatasetContractError("unsupported decision snapshot type")
        if self.direction not in {"UP", "DOWN"}:
            raise DatasetContractError("invalid hypothesis direction")
        if self.timeline_id != self.snapshot_information_key.timeline_id:
            raise DatasetContractError("snapshot timeline mismatch")
        if self.timeline_id != self.reference_information_key.timeline_id:
            raise DatasetContractError("reference timeline mismatch")
        if not self.reference_information_key <= self.snapshot_information_key:
            raise DatasetContractError("reference unavailable at snapshot")
        if not np.isfinite(self.reference_price) or self.reference_price <= 0:
            raise DatasetContractError("reference price must be positive finite")
        for name, frame in (
            ("evidence_row", self.evidence_row),
            ("narrative_row", self.narrative_row),
            ("created_ledger_event", self.created_ledger_event),
            ("same_row_observations", self.same_row_observations),
            ("same_row_relationships", self.same_row_relationships),
            ("relationship_sources", self.relationship_sources),
            ("feature_manifest", self.feature_manifest),
            ("narrative_manifest", self.narrative_manifest),
        ):
            if not isinstance(frame, pd.DataFrame) or frame.columns.has_duplicates:
                raise DatasetContractError(f"invalid {name}")
        if len(self.evidence_row) != 1 or len(self.narrative_row) != 1:
            raise DatasetContractError("feature snapshot rows must be singular")
        if len(self.created_ledger_event) != 1:
            raise DatasetContractError("exactly one CREATED ledger event required")
        created = self.created_ledger_event.iloc[0]
        if (
            int(created["hypothesis_id"]) != self.hypothesis_id
            or str(created["ledger_event_type"]) != "CREATED"
            or int(created["event_position"])
            != self.snapshot_information_key.bar_position
        ):
            raise DatasetContractError("CREATED ledger identity mismatch")
        if not (
            self.same_row_relationships["hypothesis_id"] == self.hypothesis_id
        ).all():
            raise DatasetContractError("relationship hypothesis mismatch")
        if not (
            self.same_row_relationships["observed_position"]
            == self.snapshot_information_key.bar_position
        ).all():
            raise DatasetContractError("relationship snapshot position mismatch")
        validate_feature_manifest_identity(self.feature_manifest)
        validate_narrative_manifest_identity(self.narrative_manifest)
        trigger_id = int(created["trigger_relationship_id"])
        foundation = self.same_row_relationships[
            self.same_row_relationships["relationship_id"] == trigger_id
        ]
        if len(foundation) != 1:
            raise DatasetContractError("feature snapshot foundation missing")
        if (
            str(foundation.iloc[0]["evidence_role"]) != "FOUNDATION"
            or str(foundation.iloc[0]["primary_category_value"])
            != self.hypothesis_type
        ):
            raise DatasetContractError("feature snapshot hypothesis identity mismatch")
        definition = self.narrative_manifest[
            (self.narrative_manifest["record_type"] == "HYPOTHESIS_DEFINITION")
            & (self.narrative_manifest["name"] == self.hypothesis_type)
        ]
        if len(definition) != 1 or str(definition.iloc[0]["direction"]) != self.direction:
            raise DatasetContractError("feature snapshot direction identity mismatch")
        relationship_ids = set(self.same_row_relationships["relationship_id"].tolist())
        if not set(self.relationship_sources["relationship_id"].tolist()).issubset(
            relationship_ids
        ):
            raise DatasetContractError("orphan feature relationship source")

        feature_manifest_hash = canonical_sha256(
            domain="FEATURE_MANIFEST_V1", payload=self.feature_manifest
        )
        narrative_manifest_hash = canonical_sha256(
            domain="NARRATIVE_MANIFEST_V1", payload=self.narrative_manifest
        )
        reference_identity = {
            "timeline_id": self.timeline_id,
            "created_position": self.snapshot_information_key.bar_position,
            "index_label": self.reference_index_label,
            "reference_price": self.reference_price,
            "reference_price_source": REFERENCE_PRICE_SOURCE,
            "reference_is_execution_price": False,
            "reference_key": self.reference_information_key,
        }
        expected_input_hash = canonical_sha256(
            domain="DECISION_INPUT_SLICE_V1_2", payload=reference_identity
        )
        if expected_input_hash != self.decision_input_slice_hash:
            raise DatasetContractError("decision input slice hash mismatch")
        expected_snapshot_hash = canonical_sha256(
            domain="HYPOTHESIS_CREATION_DECISION_SNAPSHOT_V1_2",
            payload={
                "timeline_id": self.timeline_id,
                "hypothesis_id": self.hypothesis_id,
                "snapshot_type": self.snapshot_type,
                "creation_key": self.snapshot_information_key,
                "evidence_row": self.evidence_row,
                "narrative_row": self.narrative_row,
                "created_ledger_event": self.created_ledger_event,
                "same_row_observations": self.same_row_observations,
                "same_hypothesis_same_row_relationships": self.same_row_relationships,
                "same_row_relationship_sources": self.relationship_sources,
                "feature_manifest_hash": feature_manifest_hash,
                "narrative_manifest_hash": narrative_manifest_hash,
                "reference_identity": reference_identity,
                "decision_input_slice_hash": self.decision_input_slice_hash,
            },
        )
        if expected_snapshot_hash != self.decision_snapshot_hash:
            raise DatasetContractError("decision snapshot hash mismatch")

    @property
    def raw_feature_columns(self) -> tuple[str, ...]:
        return tuple(self.evidence_row.columns) + tuple(self.narrative_row.columns)

    def raw_feature_row(self) -> pd.DataFrame:
        self.verify()
        if any(not str(column).startswith("ev__") for column in self.evidence_row.columns):
            raise DatasetContractError("non-evidence column in evidence feature row")
        if any(not str(column).startswith("nar__") for column in self.narrative_row.columns):
            raise DatasetContractError("non-narrative column in narrative feature row")
        collisions = set(self.evidence_row.columns) & set(self.narrative_row.columns)
        if collisions:
            raise DatasetContractError("feature column collision")
        left = self.evidence_row.reset_index(drop=True)
        right = self.narrative_row.reset_index(drop=True)
        return pd.concat([left, right], axis=1)


def freeze_creation_feature_snapshot(
    visible: VisibleAsOfBundle,
    *,
    hypothesis_id: int,
    adapter: TimelineAdapter,
) -> FrozenDecisionFeatureSnapshot:
    if not isinstance(visible, VisibleAsOfBundle):
        raise DatasetContractError("VisibleAsOfBundle required")
    if visible.timeline_id != adapter.timeline_id:
        raise DatasetContractError("feature snapshot timeline mismatch")
    projection_contract = ProjectionContract()
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
    resealed = AsOfVisibilityProjector(
        adapter=adapter, contract=projection_contract
    ).project(supplied, visible.research_as_of)
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
        try:
            pd.testing.assert_frame_equal(
                getattr(resealed, name), getattr(visible, name), check_exact=True
            )
        except AssertionError as exc:
            raise DatasetContractError("visible feature snapshot seal mismatch") from exc

    created = visible.hypothesis_ledger[
        (visible.hypothesis_ledger["hypothesis_id"] == hypothesis_id)
        & (visible.hypothesis_ledger["ledger_event_type"] == "CREATED")
    ]
    if len(created) != 1:
        raise DatasetContractError("exactly one hypothesis CREATED event required")
    created_position = int(created.iloc[0]["event_position"])
    creation_key = adapter.key_for_position(
        visible.market_frame.index,
        created_position,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        projection_contract.analytical_batch_sequence,
    )
    creation_visible = AsOfVisibilityProjector(
        adapter=adapter, contract=projection_contract
    ).project(supplied, creation_key)
    relationships = creation_visible.relationship_ledger[
        (creation_visible.relationship_ledger["hypothesis_id"] == hypothesis_id)
        & (creation_visible.relationship_ledger["observed_position"] == created_position)
    ].reset_index(drop=True)
    relationship_ids = set(relationships["relationship_id"].tolist())
    sources = creation_visible.relationship_sources[
        creation_visible.relationship_sources["relationship_id"].isin(relationship_ids)
    ].reset_index(drop=True)
    creation_event = creation_visible.hypothesis_ledger[
        (creation_visible.hypothesis_ledger["hypothesis_id"] == hypothesis_id)
        & (creation_visible.hypothesis_ledger["event_position"] == created_position)
    ].reset_index(drop=True)
    observations = creation_visible.observation_ledger[
        creation_visible.observation_ledger["observed_position"] == created_position
    ].reset_index(drop=True)
    foundation_id = int(created.iloc[0]["trigger_relationship_id"])
    foundation = relationships[relationships["relationship_id"] == foundation_id]
    if len(foundation) != 1:
        raise DatasetContractError("foundation relationship missing")
    hypothesis_name = str(foundation.iloc[0]["primary_category_value"])
    try:
        hypothesis_type = HypothesisType(hypothesis_name)
    except ValueError as exc:
        raise DatasetContractError("uncertified hypothesis type") from exc
    definition = visible.narrative_manifest[
        (visible.narrative_manifest["record_type"] == "HYPOTHESIS_DEFINITION")
        & (visible.narrative_manifest["name"] == hypothesis_type.value)
    ]
    if len(definition) != 1:
        raise DatasetContractError("hypothesis definition missing")
    direction = str(definition.iloc[0]["direction"])
    reference_price = float(visible.market_frame["close"].iloc[created_position])
    reference_key = adapter.key_for_position(
        visible.market_frame.index,
        created_position,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        projection_contract.market_row_sequence,
    )
    feature_manifest_hash = canonical_sha256(
        domain="FEATURE_MANIFEST_V1", payload=visible.feature_manifest
    )
    narrative_manifest_hash = canonical_sha256(
        domain="NARRATIVE_MANIFEST_V1", payload=visible.narrative_manifest
    )
    reference_identity = {
        "timeline_id": visible.timeline_id,
        "created_position": created_position,
        "index_label": visible.market_frame.index[created_position],
        "reference_price": reference_price,
        "reference_price_source": REFERENCE_PRICE_SOURCE,
        "reference_is_execution_price": False,
        "reference_key": reference_key,
    }
    input_hash = canonical_sha256(
        domain="DECISION_INPUT_SLICE_V1_2", payload=reference_identity
    )
    snapshot_hash = canonical_sha256(
        domain="HYPOTHESIS_CREATION_DECISION_SNAPSHOT_V1_2",
        payload={
            "timeline_id": visible.timeline_id,
            "hypothesis_id": hypothesis_id,
            "snapshot_type": SnapshotType.HYPOTHESIS_CREATION_SNAPSHOT.value,
            "creation_key": creation_key,
            "evidence_row": creation_visible.evidence_df.iloc[[created_position]],
            "narrative_row": creation_visible.narrative_surface.iloc[[created_position]],
            "created_ledger_event": creation_event,
            "same_row_observations": observations,
            "same_hypothesis_same_row_relationships": relationships,
            "same_row_relationship_sources": sources,
            "feature_manifest_hash": feature_manifest_hash,
            "narrative_manifest_hash": narrative_manifest_hash,
            "reference_identity": reference_identity,
            "decision_input_slice_hash": input_hash,
        },
    )
    snapshot = FrozenDecisionFeatureSnapshot(
        timeline_id=visible.timeline_id,
        hypothesis_id=hypothesis_id,
        hypothesis_type=hypothesis_type.value,
        direction=direction,
        snapshot_type=SnapshotType.HYPOTHESIS_CREATION_SNAPSHOT.value,
        snapshot_information_key=creation_key,
        reference_price=reference_price,
        reference_information_key=reference_key,
        reference_index_label=visible.market_frame.index[created_position],
        evidence_row=creation_visible.evidence_df.iloc[[created_position]].copy(deep=True),
        narrative_row=creation_visible.narrative_surface.iloc[[created_position]].copy(
            deep=True
        ),
        created_ledger_event=creation_event.copy(deep=True),
        same_row_observations=observations.copy(deep=True),
        same_row_relationships=relationships.copy(deep=True),
        relationship_sources=sources.copy(deep=True),
        feature_manifest=visible.feature_manifest.copy(deep=True),
        narrative_manifest=visible.narrative_manifest.copy(deep=True),
        decision_input_slice_hash=input_hash,
        decision_snapshot_hash=snapshot_hash,
    )
    snapshot.verify()
    return snapshot

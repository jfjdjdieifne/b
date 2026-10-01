"""Causal future trajectory / outcome contracts (Module 6.2A-4 V1).

Research-only foundation.  Stage 1 provides the causal/identity/storage
architecture that later trajectory stages build on: a shared authenticated
market observation timeline, decision anchors with two-clock semantics, legal
observation intervals, observation envelopes, as-of projections, and terminal/
censor snapshot identity.

No market-domain trajectory ingestion, descriptors, estimands, model, geometry,
or execution logic is implemented in Stage 1.
"""
from __future__ import annotations

from trading_system.research.trajectory.trajectory_contract import (
    DECISION_ANCHOR_SOURCE_SNAPSHOT_VERSION,
    INTERVAL_CONTRACT_VERSION,
    MARKET_TIMELINE_SOURCE_VERSION,
    OBSERVATION_ENVELOPE_CONTRACT_VERSION,
    REFERENCE_MARK_SOURCE,
    REFERENCE_IS_EXECUTION_PRICE,
    SNAPSHOT_CONTRACT_VERSION,
    TIMELINE_ADAPTER_KIND,
    TIMELINE_CAPABILITY,
    TIMELINE_SOURCE_CAPABILITY,
    TRAJECTORY_CONTRACT_VERSION,
    AsOfSnapshotKind,
    DecisionAnchor,
    MarketObservationTimeline,
    ObservationEnvelope,
    ObservationKind,
    TrajectoryContractError,
    TrajectoryDataError,
    TrajectoryInterval,
    TrajectoryProjector,
    VisibleAsOfTrajectorySnapshot,
    anchor_decision,
    bind_interval,
    make_observation_envelope,
    project_as_of,
    trajectory_contract_manifest,
    verify_decision_anchor,
)

__all__ = [
    "TRAJECTORY_CONTRACT_VERSION",
    "MARKET_TIMELINE_SOURCE_VERSION",
    "DECISION_ANCHOR_SOURCE_SNAPSHOT_VERSION",
    "INTERVAL_CONTRACT_VERSION",
    "OBSERVATION_ENVELOPE_CONTRACT_VERSION",
    "SNAPSHOT_CONTRACT_VERSION",
    "REFERENCE_MARK_SOURCE",
    "REFERENCE_IS_EXECUTION_PRICE",
    "ObservationKind",
    "AsOfSnapshotKind",
    "TIMELINE_ADAPTER_KIND",
    "TIMELINE_CAPABILITY",
    "TIMELINE_SOURCE_CAPABILITY",
    "TrajectoryContractError",
    "TrajectoryDataError",
    "MarketObservationTimeline",
    "DecisionAnchor",
    "TrajectoryInterval",
    "ObservationEnvelope",
    "VisibleAsOfTrajectorySnapshot",
    "TrajectoryProjector",
    "anchor_decision",
    "bind_interval",
    "make_observation_envelope",
    "project_as_of",
    "verify_decision_anchor",
    "trajectory_contract_manifest",
]

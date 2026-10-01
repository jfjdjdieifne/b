"""Module 6.2A-4 V1 Stage 1: causal future-trajectory foundation contracts.

Stage 1 establishes only the identity/storage/causal architecture:

* a shared authenticated ``MarketObservationTimeline`` (no per-hypothesis copy
  of market history);
* a ``DecisionAnchor`` that contains decision-time facts only;
* explicit DECISION CLOCK vs OUTCOME OBSERVATION CLOCK;
* a legal ``TrajectoryInterval`` strictly after the decision information batch;
* an observation envelope distinguishing FACTUAL_EVENT from STATE_OBSERVATION;
* a deterministic as-of projection / snapshot identity;
* terminal vs censor snapshot identity separation;
* canonical hashing/identity layers.

It does NOT ingest any market-domain trajectory (liquidity/OB/FVG/flow/MTF),
does not normalize volatility, does not derive path descriptors, does not
define estimands, and contains no model/scorer/geometry/execution logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final, Optional

import numpy as np
import pandas as pd

from trading_system.research.dataset_contracts import (
    FEATURE_SNAPSHOT_CONTRACT_VERSION,
    FrozenDecisionFeatureSnapshot,
)
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import (
    INFORMATION_KEY_VERSION,
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)

TimelineAdapter = PositionalTimelineAdapter | TimeIndexedTimelineAdapter

TRAJECTORY_CONTRACT_VERSION: Final = "CAUSAL_FUTURE_TRAJECTORY_FOUNDATION_V1"
MARKET_TIMELINE_SOURCE_VERSION: Final = "PROJECT_INPUT_HISTORY_SEAL_V1"
DECISION_ANCHOR_SOURCE_SNAPSHOT_VERSION: Final = FEATURE_SNAPSHOT_CONTRACT_VERSION
INTERVAL_CONTRACT_VERSION: Final = "CAUSAL_TRAJECTORY_INTERVAL_V1"
OBSERVATION_ENVELOPE_CONTRACT_VERSION: Final = "CAUSAL_OBSERVATION_ENVELOPE_V1"
SNAPSHOT_CONTRACT_VERSION: Final = "CAUSAL_ASOF_TRAJECTORY_SNAPSHOT_V1"

# Exact CLOSED 6.2A-1 / 6.2A-3 research reference semantics.
REFERENCE_MARK_SOURCE: Final = "CREATION_ROW_COMPLETED_CLOSE_RESEARCH_REFERENCE_MARK"
REFERENCE_IS_EXECUTION_PRICE: Final = False

# Required project input columns used to seal a market timeline.  OHLC path is
# the minimal legal source; volume is optional and recorded as available/not.
_TIMELINE_REQUIRED_COLUMNS: Final = ("open", "high", "low", "close")
_TIMELINE_OPTIONAL_COLUMNS: Final = ("volume",)


class TrajectoryContractError(Exception):
    """Static contract, identity, version, or clock violation."""


class TrajectoryDataError(Exception):
    """Malformed or causally illegal trajectory input."""


class ObservationKind(Enum):
    """Whether an observation is an event or a state-as-of value."""

    FACTUAL_EVENT = "FACTUAL_EVENT"
    STATE_OBSERVATION = "STATE_OBSERVATION"


class AsOfSnapshotKind(Enum):
    """Terminal maturity vs right-censored as-of snapshot."""

    MATURE_TERMINAL = "MATURE_TERMINAL"
    RIGHT_CENSORED_AS_OF = "RIGHT_CENSORED_AS_OF"


class TIMELINE_ADAPTER_KIND(Enum):
    """Authoritative timeline adapter class used to bind positions to keys."""

    POSITIONAL = "POSITIONAL"
    TIME_INDEXED = "TIME_INDEXED"


class TIMELINE_CAPABILITY(Enum):
    """Certified data-resolution capability of a timeline source."""

    OHLC_BAR = "OHLC_BAR"
    TRADE_TICK = "TRADE_TICK"
    ORDER_BOOK = "ORDER_BOOK"


# Stage 1 supports only the OHLC source truthfully; tick/L2 are reserved and
# may not be claimed by a caller-supplied frame.
TIMELINE_SOURCE_CAPABILITY: Final = TIMELINE_CAPABILITY.OHLC_BAR

_CLOSED_TERMINAL_STATES: Final = frozenset(
    {"CONTRADICTED", "SUPERSEDED", "OBSERVED_DIRECTION_ESTABLISHED"}
)


def _require_columns(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TrajectoryDataError("market history must be a DataFrame")
    if frame.columns.has_duplicates:
        raise TrajectoryDataError("duplicate market columns forbidden")
    if frame.index.has_duplicates:
        raise TrajectoryDataError("duplicate timeline index forbidden")
    if not frame.index.is_monotonic_increasing:
        raise TrajectoryDataError("timeline index must be monotonic increasing")
    missing = [c for c in _TIMELINE_REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise TrajectoryDataError(f"market history missing columns: {missing}")
    for column in _TIMELINE_REQUIRED_COLUMNS:
        if not pd.api.types.is_numeric_dtype(frame[column]):
            raise TrajectoryDataError(f"{column} must be numeric")
    o = frame["open"].to_numpy(float)
    h = frame["high"].to_numpy(float)
    l = frame["low"].to_numpy(float)
    c = frame["close"].to_numpy(float)
    if not (np.isfinite(o) & np.isfinite(h) & np.isfinite(l) & np.isfinite(c)).all():
        raise TrajectoryDataError("OHLC must be finite")
    if (h < l).any():
        raise TrajectoryDataError("high < low in market history")
    if (((o < l) | (o > h) | (c < l) | (c > h))).any():
        raise TrajectoryDataError("OHLC body outside high/low range")
    if "volume" in frame.columns and not pd.api.types.is_numeric_dtype(frame["volume"]):
        raise TrajectoryDataError("volume must be numeric when present")


def _adapter_kind(adapter: TimelineAdapter) -> TIMELINE_ADAPTER_KIND:
    if isinstance(adapter, PositionalTimelineAdapter):
        return TIMELINE_ADAPTER_KIND.POSITIONAL
    if isinstance(adapter, TimeIndexedTimelineAdapter):
        return TIMELINE_ADAPTER_KIND.TIME_INDEXED
    raise TrajectoryContractError("unsupported timeline adapter")


@dataclass(frozen=True)
class MarketObservationTimeline:
    """Shared, immutable, authenticated market observation timeline.

    A single timeline is reused by any number of hypothesis anchors via
    intervals referencing it; market rows are never duplicated per hypothesis.
    The seal is integrity binding over exact caller-supplied project input
    history, not trusted-issuer authentication.
    """

    timeline_id: str
    adapter_kind: TIMELINE_ADAPTER_KIND
    adapter_version: str
    source_capability: TIMELINE_CAPABILITY
    bar_count: int
    index_class: str
    index_dtype: str
    required_columns: tuple[str, ...]
    optional_columns_present: tuple[str, ...]
    index_hash: str
    column_schema_hash: str
    ohlc_payload_hash: str
    timeline_hash: str

    @classmethod
    def seal(
        cls,
        *,
        adapter: TimelineAdapter,
        market_history: pd.DataFrame,
        source_capability: TIMELINE_CAPABILITY = TIMELINE_SOURCE_CAPABILITY,
    ) -> "MarketObservationTimeline":
        if not isinstance(adapter, TimelineAdapter):
            raise TrajectoryContractError("TimelineAdapter required")
        if not isinstance(source_capability, TIMELINE_CAPABILITY):
            raise TrajectoryContractError("invalid source capability")
        if source_capability is not TIMELINE_SOURCE_CAPABILITY:
            raise TrajectoryContractError(
                "Stage 1 only supports certified OHLC_BAR source; "
                "TRADE_TICK/ORDER_BOOK require a future source contract"
            )
        _require_columns(market_history)
        adapter.validate_index(market_history.index)
        timeline_id = adapter.timeline_id
        kind = _adapter_kind(adapter)
        optional = tuple(
            c for c in _TIMELINE_OPTIONAL_COLUMNS if c in market_history.columns
        )
        index_payload = {
            "class": f"{type(market_history.index).__module__}.{type(market_history.index).__qualname__}",
            "dtype": str(market_history.index.dtype),
            "name": None if market_history.index.name is None else str(market_history.index.name),
            "values": list(market_history.index.tolist()),
        }
        columns = tuple(market_history.columns)
        index_hash = canonical_sha256(
            domain="MARKET_TIMELINE_INDEX_V1", payload=index_payload
        )
        column_schema_hash = canonical_sha256(
            domain="MARKET_TIMELINE_SCHEMA_V1",
            payload={
                "required_columns": list(_TIMELINE_REQUIRED_COLUMNS),
                "columns": list(columns),
                "optional_present": list(optional),
                "dtypes": [str(market_history[c].dtype) for c in columns],
            },
        )
        # Seal exact OHLC payload (and volume when present) without copying
        # domain interpretations.  This binds caller rows byte-for-byte.
        ohlc_payload_hash = canonical_sha256(
            domain="MARKET_TIMELINE_OHLC_PAYLOAD_V1",
            payload=market_history[list(_TIMELINE_REQUIRED_COLUMNS) + list(optional)],
        )
        timeline_hash = canonical_sha256(
            domain="MARKET_OBSERVATION_TIMELINE_V1",
            payload={
                "timeline_id": timeline_id,
                "adapter_kind": kind,
                "adapter_version": adapter.adapter_version,
                "source_capability": source_capability,
                "bar_count": len(market_history),
                "index_hash": index_hash,
                "column_schema_hash": column_schema_hash,
                "ohlc_payload_hash": ohlc_payload_hash,
                "source_version": MARKET_TIMELINE_SOURCE_VERSION,
            },
        )
        return cls(
            timeline_id=timeline_id,
            adapter_kind=kind,
            adapter_version=adapter.adapter_version,
            source_capability=source_capability,
            bar_count=len(market_history),
            index_class=index_payload["class"],
            index_dtype=str(market_history.index.dtype),
            required_columns=tuple(_TIMELINE_REQUIRED_COLUMNS),
            optional_columns_present=optional,
            index_hash=index_hash,
            column_schema_hash=column_schema_hash,
            ohlc_payload_hash=ohlc_payload_hash,
            timeline_hash=timeline_hash,
        )

    def verify(
        self, *, adapter: TimelineAdapter, market_history: pd.DataFrame
    ) -> None:
        expected = MarketObservationTimeline.seal(
            adapter=adapter,
            market_history=market_history,
            source_capability=self.source_capability,
        )
        if expected.timeline_hash != self.timeline_hash:
            raise TrajectoryDataError("market timeline seal mismatch")
        for name in self.__dataclass_fields__:
            if getattr(expected, name) != getattr(self, name):
                raise TrajectoryDataError(f"market timeline field mismatch: {name}")

    def key_for_position(
        self,
        adapter: TimelineAdapter,
        market_history: pd.DataFrame,
        position: int,
        phase: InformationPhase,
        *,
        deterministic_sequence: int = 0,
    ) -> InformationKey:
        self.verify(adapter=adapter, market_history=market_history)
        return adapter.key_for_position(
            market_history.index, position, phase, deterministic_sequence
        )


def _key_payload(key: InformationKey) -> dict:
    return {
        "information_key_version": key.information_key_version,
        "timeline_id": key.timeline_id,
        "bar_position": key.bar_position,
        "event_time_utc": key.event_time_utc,
        "information_phase": key.information_phase,
        "deterministic_sequence": key.deterministic_sequence,
    }


@dataclass(frozen=True)
class DecisionAnchor:
    """Decision-only identity/provenance anchor.

    It binds a frozen CLOSED decision/evidence identity and the non-executable
    research reference mark.  It contains no post-decision facts and does not
    preselect future model features (no embedded volatility/context unit).
    """

    timeline_id: str
    hypothesis_id: int
    hypothesis_type: str
    direction: str
    decision_information_key: InformationKey
    reference_price: float
    reference_information_key: InformationKey
    reference_is_execution_price: bool
    reference_mark_source: str
    decision_snapshot_hash: str
    evidence_vector_hash: object
    narrative_hash: object
    reasoning_semantic_hash: object
    feature_snapshot_contract_version: str
    timeline_hash: str
    anchor_hash: str

    def verify(self) -> None:
        if self.information_key_version_ok():
            pass
        if self.timeline_id != self.decision_information_key.timeline_id:
            raise TrajectoryDataError("anchor timeline mismatch")
        if self.reference_information_key.timeline_id != self.timeline_id:
            raise TrajectoryDataError("reference timeline mismatch")
        if not self.reference_information_key <= self.decision_information_key:
            raise TrajectoryDataError("reference unavailable at decision")
        if self.reference_is_execution_price is not REFERENCE_IS_EXECUTION_PRICE:
            raise TrajectoryContractError("research reference must be non-executable")
        if self.reference_mark_source != REFERENCE_MARK_SOURCE:
            raise TrajectoryContractError("reference mark source mismatch")
        if not np.isfinite(self.reference_price) or self.reference_price <= 0:
            raise TrajectoryDataError("reference price must be positive finite")
        if not isinstance(self.hypothesis_id, int) or isinstance(self.hypothesis_id, bool):
            raise TrajectoryDataError("hypothesis_id must be integer")
        if self.hypothesis_id < 0:
            raise TrajectoryDataError("hypothesis_id must be nonnegative")
        if self.direction not in {"UP", "DOWN"}:
            raise TrajectoryDataError("invalid hypothesis direction")
        if self.feature_snapshot_contract_version != DECISION_ANCHOR_SOURCE_SNAPSHOT_VERSION:
            raise TrajectoryContractError("frozen snapshot contract mismatch")
        expected = _anchor_hash(self)
        if expected != self.anchor_hash:
            raise TrajectoryDataError("decision anchor hash mismatch")

    def information_key_version_ok(self) -> bool:
        if self.decision_information_key.information_key_version != INFORMATION_KEY_VERSION:
            raise TrajectoryContractError("information key version mismatch")
        return True


def _anchor_hash(anchor: DecisionAnchor) -> str:
    return canonical_sha256(
        domain="CAUSAL_DECISION_ANCHOR_V1",
        payload={
            "timeline_id": anchor.timeline_id,
            "hypothesis_id": anchor.hypothesis_id,
            "hypothesis_type": anchor.hypothesis_type,
            "direction": anchor.direction,
            "decision_information_key": _key_payload(anchor.decision_information_key),
            "reference_price": float(anchor.reference_price),
            "reference_information_key": _key_payload(anchor.reference_information_key),
            "reference_is_execution_price": False,
            "reference_mark_source": REFERENCE_MARK_SOURCE,
            "decision_snapshot_hash": anchor.decision_snapshot_hash,
            "evidence_vector_hash": anchor.evidence_vector_hash,
            "narrative_hash": anchor.narrative_hash,
            "reasoning_semantic_hash": anchor.reasoning_semantic_hash,
            "feature_snapshot_contract_version": anchor.feature_snapshot_contract_version,
            "timeline_hash": anchor.timeline_hash,
        },
    )


def anchor_decision(
    *,
    timeline: MarketObservationTimeline,
    frozen: FrozenDecisionFeatureSnapshot,
    evidence_vector_hash: Optional[str] = None,
    narrative_hash: Optional[str] = None,
    reasoning_semantic_hash: Optional[str] = None,
) -> DecisionAnchor:
    """Create a decision anchor from an authoritative frozen decision snapshot."""
    if not isinstance(timeline, MarketObservationTimeline):
        raise TrajectoryContractError("MarketObservationTimeline required")
    if not isinstance(frozen, FrozenDecisionFeatureSnapshot):
        raise TrajectoryContractError("FrozenDecisionFeatureSnapshot required")
    frozen.verify()
    if frozen.timeline_id != timeline.timeline_id:
        raise TrajectoryDataError("frozen snapshot belongs to another timeline")
    if (
        frozen.snapshot_information_key.information_key_version
        != INFORMATION_KEY_VERSION
    ):
        raise TrajectoryContractError("decision information key version mismatch")
    anchor = DecisionAnchor(
        timeline_id=frozen.timeline_id,
        hypothesis_id=frozen.hypothesis_id,
        hypothesis_type=frozen.hypothesis_type,
        direction=frozen.direction,
        decision_information_key=frozen.snapshot_information_key,
        reference_price=float(frozen.reference_price),
        reference_information_key=frozen.reference_information_key,
        reference_is_execution_price=False,
        reference_mark_source=REFERENCE_MARK_SOURCE,
        decision_snapshot_hash=frozen.decision_snapshot_hash,
        evidence_vector_hash=evidence_vector_hash,
        narrative_hash=narrative_hash,
        reasoning_semantic_hash=reasoning_semantic_hash,
        feature_snapshot_contract_version=frozen.feature_snapshot_contract_version,
        timeline_hash=timeline.timeline_hash,
        anchor_hash="",
    )
    object.__setattr__(anchor, "anchor_hash", _anchor_hash(anchor))
    anchor.verify()
    return anchor


def verify_decision_anchor(anchor: DecisionAnchor) -> bool:
    if not isinstance(anchor, DecisionAnchor):
        raise TrajectoryContractError("DecisionAnchor required")
    anchor.verify()
    return True


@dataclass(frozen=True)
class TrajectoryInterval:
    """Legal post-decision observation interval on the shared timeline.

    The interval is (decision_information_batch, end_inclusive].  The creation
    bar is excluded from the outcome path, consistent with CLOSED 6.2A-1
    creation-bar exclusion semantics.  Same-row serialization is never treated
    as intrabar chronology.
    """

    interval_id: str
    timeline_id: str
    timeline_hash: str
    anchor_hash: str
    decision_information_key: InformationKey
    start_exclusive_information_key: InformationKey
    end_inclusive_information_key: InformationKey
    start_exclusive_bar_position: int
    end_inclusive_bar_position: int
    observed_bar_count: int
    same_row_atomicity: str
    interval_hash: str

    def verify(self) -> None:
        if self.timeline_id != self.decision_information_key.timeline_id:
            raise TrajectoryDataError("interval timeline mismatch")
        if self.start_exclusive_information_key < self.decision_information_key:
            raise TrajectoryDataError("interval start before decision")
        if not self.start_exclusive_information_key >= self.decision_information_key:
            raise TrajectoryDataError("illegal interval start")
        if self.end_inclusive_information_key < self.start_exclusive_information_key:
            raise TrajectoryDataError("interval end before start")
        if self.start_exclusive_bar_position != self.decision_information_key.bar_position:
            raise TrajectoryDataError("interval must start strictly after decision bar")
        if self.end_inclusive_bar_position < self.start_exclusive_bar_position:
            raise TrajectoryDataError("negative interval")
        expected_count = (
            self.end_inclusive_bar_position - self.start_exclusive_bar_position
        )
        if self.observed_bar_count != expected_count:
            raise TrajectoryDataError("observed bar count mismatch")
        if self.same_row_atomicity != "SAME_INFORMATION_BATCH_ATOMIC_ORDER_UNKNOWN":
            raise TrajectoryContractError("same-row atomicity contract mismatch")
        if _interval_hash(self) != self.interval_hash:
            raise TrajectoryDataError("interval hash mismatch")


def _successor_completed_key(key: InformationKey) -> InformationKey:
    """First key strictly after a completed decision information batch."""
    return InformationKey(
        information_key_version=key.information_key_version,
        timeline_id=key.timeline_id,
        bar_position=key.bar_position + 1,
        event_time_utc=None,
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=0,
    )


def _interval_hash(interval: TrajectoryInterval) -> str:
    return canonical_sha256(
        domain="CAUSAL_TRAJECTORY_INTERVAL_V1",
        payload={
            "timeline_id": interval.timeline_id,
            "timeline_hash": interval.timeline_hash,
            "anchor_hash": interval.anchor_hash,
            "decision_information_key": _key_payload(interval.decision_information_key),
            "start_exclusive_information_key": _key_payload(
                interval.start_exclusive_information_key
            ),
            "end_inclusive_information_key": _key_payload(
                interval.end_inclusive_information_key
            ),
            "start_exclusive_bar_position": interval.start_exclusive_bar_position,
            "end_inclusive_bar_position": interval.end_inclusive_bar_position,
            "observed_bar_count": interval.observed_bar_count,
            "same_row_atomicity": interval.same_row_atomicity,
        },
    )


def bind_interval(
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    end_inclusive: InformationKey,
) -> TrajectoryInterval:
    """Bind a legal (decision, end] interval on the shared timeline."""
    if not isinstance(timeline, MarketObservationTimeline):
        raise TrajectoryContractError("MarketObservationTimeline required")
    if not isinstance(anchor, DecisionAnchor):
        raise TrajectoryContractError("DecisionAnchor required")
    timeline.verify(adapter=adapter, market_history=market_history)
    anchor.verify()
    if timeline.timeline_id != anchor.timeline_id:
        raise TrajectoryDataError("timeline/anchor mismatch")
    if timeline.timeline_hash != anchor.timeline_hash:
        raise TrajectoryDataError("anchor bound to a different timeline seal")
    decision = anchor.decision_information_key
    if end_inclusive.timeline_id != timeline.timeline_id:
        raise TrajectoryDataError("end key belongs to another timeline")
    adapter.validate_key(end_inclusive, market_history.index)
    if end_inclusive <= decision:
        raise TrajectoryDataError("observation end must be after decision")
    start = _successor_completed_key(decision)
    if start.timeline_id != timeline.timeline_id:
        raise TrajectoryDataError("illegal start timeline")
    if end_inclusive.bar_position <= decision.bar_position:
        raise TrajectoryDataError("no post-decision bars in interval")
    if end_inclusive.information_phase not in {
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    }:
        raise TrajectoryContractError("end key phase not legally observable")
    interval = TrajectoryInterval(
        interval_id="",
        timeline_id=timeline.timeline_id,
        timeline_hash=timeline.timeline_hash,
        anchor_hash=anchor.anchor_hash,
        decision_information_key=decision,
        start_exclusive_information_key=start,
        end_inclusive_information_key=end_inclusive,
        start_exclusive_bar_position=decision.bar_position,
        end_inclusive_bar_position=end_inclusive.bar_position,
        observed_bar_count=end_inclusive.bar_position - decision.bar_position,
        same_row_atomicity="SAME_INFORMATION_BATCH_ATOMIC_ORDER_UNKNOWN",
        interval_hash="",
    )
    interval_id = canonical_sha256(
        domain="CAUSAL_TRAJECTORY_INTERVAL_ID_V1",
        payload={
            "timeline_hash": interval.timeline_hash,
            "anchor_hash": interval.anchor_hash,
            "interval_hash": _interval_hash(interval),
        },
    )
    object.__setattr__(interval, "interval_id", interval_id)
    object.__setattr__(interval, "interval_hash", _interval_hash(interval))
    interval.verify()
    return interval


@dataclass(frozen=True)
class ObservationEnvelope:
    """A typed post-decision observation bound to the shared interval/timeline.

    Stage 1 defines the envelope contract only; it does not ingest domain
    observations.  FACTUAL_EVENT means something happened at a key;
    STATE_OBSERVATION means a factual value/state was available as-of a key.
    Every per-bar scalar must not be labelled an event.
    """

    envelope_id: str
    interval_id: str
    timeline_id: str
    timeline_hash: str
    anchor_hash: str
    observation_information_key: InformationKey
    factual_available_at_information_key: InformationKey
    observation_kind: ObservationKind
    source_capability: TIMELINE_CAPABILITY
    source_contract: str
    source_module: str
    source_module_version: str
    observation_domain: str
    observation_type: str
    same_information_batch_order_unknown: bool
    envelope_hash: str

    def verify(self) -> None:
        if self.timeline_id != self.observation_information_key.timeline_id:
            raise TrajectoryDataError("envelope timeline mismatch")
        if self.factual_available_at_information_key.timeline_id != self.timeline_id:
            raise TrajectoryDataError("availability key timeline mismatch")
        if self.observation_information_key.information_key_version != INFORMATION_KEY_VERSION:
            raise TrajectoryContractError("information key version mismatch")
        if not isinstance(self.observation_kind, ObservationKind):
            raise TrajectoryContractError("invalid observation kind")
        if not isinstance(self.source_capability, TIMELINE_CAPABILITY):
            raise TrajectoryContractError("invalid source capability")
        if self.source_capability is not TIMELINE_SOURCE_CAPABILITY:
            raise TrajectoryContractError("unsupported source capability in Stage 1")
        if self.observation_information_key > self.factual_available_at_information_key:
            raise TrajectoryDataError("observation cannot predate its availability")
        if self.envelope_hash != _envelope_hash(self):
            raise TrajectoryDataError("observation envelope hash mismatch")


def _envelope_hash(envelope: ObservationEnvelope) -> str:
    return canonical_sha256(
        domain="CAUSAL_OBSERVATION_ENVELOPE_V1",
        payload={
            "interval_id": envelope.interval_id,
            "timeline_hash": envelope.timeline_hash,
            "anchor_hash": envelope.anchor_hash,
            "observation_information_key": _key_payload(
                envelope.observation_information_key
            ),
            "factual_available_at_information_key": _key_payload(
                envelope.factual_available_at_information_key
            ),
            "observation_kind": envelope.observation_kind,
            "source_capability": envelope.source_capability,
            "source_contract": envelope.source_contract,
            "source_module": envelope.source_module,
            "source_module_version": envelope.source_module_version,
            "observation_domain": envelope.observation_domain,
            "observation_type": envelope.observation_type,
            "same_information_batch_order_unknown": bool(
                envelope.same_information_batch_order_unknown
            ),
        },
    )


def make_observation_envelope(
    *,
    interval: TrajectoryInterval,
    observation_information_key: InformationKey,
    factual_available_at_information_key: InformationKey,
    observation_kind: ObservationKind,
    source_contract: str,
    source_module: str,
    source_module_version: str,
    observation_domain: str,
    observation_type: str,
    same_information_batch_order_unknown: bool = False,
) -> ObservationEnvelope:
    """Construct and verify a Stage 1 observation envelope.

    The caller remains responsible for the typed value carried in a later
    domain stage; Stage 1 binds only identity, clock, and capability metadata.
    """
    if not isinstance(interval, TrajectoryInterval):
        raise TrajectoryContractError("TrajectoryInterval required")
    if not isinstance(observation_kind, ObservationKind):
        raise TrajectoryContractError("invalid observation kind")
    if observation_information_key.timeline_id != interval.timeline_id:
        raise TrajectoryDataError("observation key belongs to another timeline")
    if factual_available_at_information_key.timeline_id != interval.timeline_id:
        raise TrajectoryDataError("availability key belongs to another timeline")
    if observation_information_key <= interval.decision_information_key:
        raise TrajectoryDataError("observation must be after decision information batch")
    if observation_information_key > interval.end_inclusive_information_key:
        raise TrajectoryDataError("observation outside interval end")
    if observation_information_key > factual_available_at_information_key:
        raise TrajectoryDataError("fact cannot be observed before it is available")
    envelope = ObservationEnvelope(
        envelope_id="",
        interval_id=interval.interval_id,
        timeline_id=interval.timeline_id,
        timeline_hash=interval.timeline_hash,
        anchor_hash=interval.anchor_hash,
        observation_information_key=observation_information_key,
        factual_available_at_information_key=factual_available_at_information_key,
        observation_kind=observation_kind,
        source_capability=TIMELINE_SOURCE_CAPABILITY,
        source_contract=source_contract,
        source_module=source_module,
        source_module_version=source_module_version,
        observation_domain=observation_domain,
        observation_type=observation_type,
        same_information_batch_order_unknown=bool(
            same_information_batch_order_unknown
        ),
        envelope_hash="",
    )
    envelope_id = canonical_sha256(
        domain="CAUSAL_OBSERVATION_ENVELOPE_ID_V1", payload=_envelope_hash(envelope)
    )
    object.__setattr__(envelope, "envelope_id", envelope_id)
    object.__setattr__(envelope, "envelope_hash", _envelope_hash(envelope))
    envelope.verify()
    return envelope


@dataclass(frozen=True)
class VisibleAsOfTrajectorySnapshot:
    """Deterministic research projection of facts visible through an as-of key.

    Stage 1 stores no per-bar censor snapshots.  A snapshot is materialized only
    when explicitly requested (fold/experiment/release/mature observation) and
    remains immutable after later facts become known.  It carries no future
    observations beyond ``as_of_information_key``.
    """

    snapshot_id: str
    snapshot_kind: AsOfSnapshotKind
    timeline_id: str
    timeline_hash: str
    anchor_hash: str
    interval_id: str
    decision_information_key: InformationKey
    as_of_information_key: InformationKey
    observed_bar_count: int
    observation_envelope_ids: tuple[str, ...]
    terminal_state: object
    terminal_information_key: object
    same_bar_terminal_ambiguous: bool
    source_capability: TIMELINE_CAPABILITY
    snapshot_hash: str

    def verify(self) -> None:
        if self.timeline_id != self.as_of_information_key.timeline_id:
            raise TrajectoryDataError("snapshot timeline mismatch")
        if self.as_of_information_key <= self.decision_information_key:
            raise TrajectoryDataError("as-of snapshot must be after decision")
        if not isinstance(self.snapshot_kind, AsOfSnapshotKind):
            raise TrajectoryContractError("invalid snapshot kind")
        if len(self.observation_envelope_ids) != len(set(self.observation_envelope_ids)):
            raise TrajectoryDataError("duplicate observation envelope in snapshot")
        if self.snapshot_kind is AsOfSnapshotKind.MATURE_TERMINAL:
            if self.terminal_state not in _CLOSED_TERMINAL_STATES:
                raise TrajectoryDataError("mature snapshot requires CLOSED terminal state")
            if not isinstance(self.terminal_information_key, InformationKey):
                raise TrajectoryDataError("mature terminal key required")
            if self.terminal_information_key > self.as_of_information_key:
                raise TrajectoryDataError("terminal fact after as-of boundary")
        else:
            if self.terminal_state is not None and not pd.isna(self.terminal_state):
                raise TrajectoryDataError("censored snapshot cannot carry terminal state")
        if self.source_capability is not TIMELINE_SOURCE_CAPABILITY:
            raise TrajectoryContractError("unsupported source capability")
        if _snapshot_hash(self) != self.snapshot_hash:
            raise TrajectoryDataError("as-of snapshot hash mismatch")


def _snapshot_hash(snapshot: VisibleAsOfTrajectorySnapshot) -> str:
    terminal_key = snapshot.terminal_information_key
    return canonical_sha256(
        domain="CAUSAL_ASOF_TRAJECTORY_SNAPSHOT_V1",
        payload={
            "snapshot_kind": snapshot.snapshot_kind,
            "timeline_hash": snapshot.timeline_hash,
            "anchor_hash": snapshot.anchor_hash,
            "interval_id": snapshot.interval_id,
            "decision_information_key": _key_payload(snapshot.decision_information_key),
            "as_of_information_key": _key_payload(snapshot.as_of_information_key),
            "observed_bar_count": snapshot.observed_bar_count,
            "observation_envelope_ids": tuple(snapshot.observation_envelope_ids),
            "terminal_state": snapshot.terminal_state,
            "terminal_information_key": (
                None if terminal_key is None or pd.isna(terminal_key) else _key_payload(terminal_key)
            ),
            "same_bar_terminal_ambiguous": bool(snapshot.same_bar_terminal_ambiguous),
            "source_capability": snapshot.source_capability,
        },
    )


@dataclass
class TrajectoryProjector:
    """Stateless deterministic as-of projector over a sealed shared timeline."""

    def project(
        self,
        *,
        interval: TrajectoryInterval,
        as_of_information_key: InformationKey,
        observation_envelopes: tuple[ObservationEnvelope, ...] = (),
        terminal_state: Optional[str] = None,
        terminal_information_key: Optional[InformationKey] = None,
        same_bar_terminal_ambiguous: bool = False,
    ) -> VisibleAsOfTrajectorySnapshot:
        if not isinstance(interval, TrajectoryInterval):
            raise TrajectoryContractError("TrajectoryInterval required")
        interval.verify()
        if as_of_information_key.timeline_id != interval.timeline_id:
            raise TrajectoryDataError("as-of key belongs to another timeline")
        if as_of_information_key < interval.start_exclusive_information_key:
            raise TrajectoryDataError("as-of key before observation start")
        if as_of_information_key > interval.end_inclusive_information_key:
            raise TrajectoryDataError("as-of key beyond bound interval end")

        visible = []
        for envelope in observation_envelopes:
            if not isinstance(envelope, ObservationEnvelope):
                raise TrajectoryContractError("invalid observation envelope")
            envelope.verify()
            if envelope.interval_id != interval.interval_id:
                raise TrajectoryDataError("envelope belongs to another interval")
            if envelope.anchor_hash != interval.anchor_hash:
                raise TrajectoryDataError("envelope anchor mismatch")
            if envelope.observation_information_key > as_of_information_key:
                continue
            if envelope.factual_available_at_information_key > as_of_information_key:
                continue
            visible.append(envelope.envelope_id)

        kind = (
            AsOfSnapshotKind.MATURE_TERMINAL
            if terminal_state is not None
            else AsOfSnapshotKind.RIGHT_CENSORED_AS_OF
        )
        if kind is AsOfSnapshotKind.MATURE_TERMINAL:
            if terminal_state not in _CLOSED_TERMINAL_STATES:
                raise TrajectoryDataError("terminal state not a CLOSED lifecycle enum")
            if not isinstance(terminal_information_key, InformationKey):
                raise TrajectoryDataError("mature terminal key required")
            if terminal_information_key > as_of_information_key:
                raise TrajectoryDataError("terminal fact unavailable at as-of key")
            if terminal_information_key <= interval.decision_information_key:
                raise TrajectoryDataError("terminal must be post-decision")
        observed_bar_count = (
            as_of_information_key.bar_position
            - interval.decision_information_key.bar_position
        )
        snapshot = VisibleAsOfTrajectorySnapshot(
            snapshot_id="",
            snapshot_kind=kind,
            timeline_id=interval.timeline_id,
            timeline_hash=interval.timeline_hash,
            anchor_hash=interval.anchor_hash,
            interval_id=interval.interval_id,
            decision_information_key=interval.decision_information_key,
            as_of_information_key=as_of_information_key,
            observed_bar_count=observed_bar_count,
            observation_envelope_ids=tuple(visible),
            terminal_state=terminal_state,
            terminal_information_key=terminal_information_key,
            same_bar_terminal_ambiguous=bool(same_bar_terminal_ambiguous),
            source_capability=TIMELINE_SOURCE_CAPABILITY,
            snapshot_hash="",
        )
        snapshot_id = canonical_sha256(
            domain="CAUSAL_ASOF_TRAJECTORY_SNAPSHOT_ID_V1",
            payload=_snapshot_hash(snapshot),
        )
        object.__setattr__(snapshot, "snapshot_id", snapshot_id)
        object.__setattr__(snapshot, "snapshot_hash", _snapshot_hash(snapshot))
        snapshot.verify()
        return snapshot


def project_as_of(
    *,
    interval: TrajectoryInterval,
    as_of_information_key: InformationKey,
    observation_envelopes: tuple[ObservationEnvelope, ...] = (),
    terminal_state: Optional[str] = None,
    terminal_information_key: Optional[InformationKey] = None,
    same_bar_terminal_ambiguous: bool = False,
) -> VisibleAsOfTrajectorySnapshot:
    return TrajectoryProjector().project(
        interval=interval,
        as_of_information_key=as_of_information_key,
        observation_envelopes=observation_envelopes,
        terminal_state=terminal_state,
        terminal_information_key=terminal_information_key,
        same_bar_terminal_ambiguous=same_bar_terminal_ambiguous,
    )


def trajectory_contract_manifest() -> pd.DataFrame:
    rows = [
        ("CONTRACT", "VERSION", TRAJECTORY_CONTRACT_VERSION),
        ("STAGE", "SCOPE", "STAGE_1_FOUNDATION_ONLY"),
        ("TIMELINE", "SOURCE_VERSION", MARKET_TIMELINE_SOURCE_VERSION),
        ("TIMELINE", "CAPABILITY", TIMELINE_SOURCE_CAPABILITY.value),
        ("TIMELINE", "SEAL", "INTEGRITY_NOT_ISSUER_AUTHENTICATION"),
        ("ANCHOR", "SOURCE_SNAPSHOT", DECISION_ANCHOR_SOURCE_SNAPSHOT_VERSION),
        ("ANCHOR", "FUTURE_FACTS", "FORBIDDEN"),
        ("CLOCK", "DECISION", "decision_information_key"),
        ("CLOCK", "OUTCOME_OBSERVATION", "observation/factual_available_at key"),
        ("INTERVAL", "SEMANTICS", "(DECISION_BATCH, END_INCLUSIVE]"),
        ("INTERVAL", "CREATION_BAR", "EXCLUDED_FROM_OUTCOME_PATH"),
        ("OBSERVATION", "KINDS", "FACTUAL_EVENT;STATE_OBSERVATION"),
        ("REFERENCE", "MARK_SOURCE", REFERENCE_MARK_SOURCE),
        ("REFERENCE", "EXECUTION_PRICE", "FALSE"),
        ("CHRONOLOGY", "SAME_BAR", "SAME_INFORMATION_BATCH_ORDER_UNKNOWN"),
        ("SNAPSHOT", "CENSOR", "RIGHT_CENSORED_AS_OF_IMMUTABLE"),
        ("SNAPSHOT", "TERMINAL", "MATURE_TERMINAL_CLOSED_LIFECYCLE_ENUM"),
        ("TERMINAL", "LANGUAGE", "FACTUAL_LIFECYCLE_NO_SUCCESS_CLAIM"),
        ("DOMAIN", "TRAJECTORY_INGESTION", "NOT_IMPLEMENTED"),
        ("DERIVED", "DESCRIPTORS", "NOT_IMPLEMENTED"),
        ("ESTIMAND", "MODEL", "NOT_IMPLEMENTED"),
        ("GEOMETRY", "EXECUTION", "NOT_IMPLEMENTED"),
        ("DEBT", "RESEARCH-DEBT-020", "OPEN"),
        ("DEBT", "RESEARCH-DEBT-023", "OPEN"),
        ("DEBT", "RESEARCH-DEBT-024", "OPEN"),
        ("DEBT", "RESEARCH-DEBT-025", "OPEN"),
    ]
    return pd.DataFrame(
        [
            {
                "record_type": a,
                "name": b,
                "value": c,
                "serialization_order": i,
            }
            for i, (a, b, c) in enumerate(rows)
        ]
    )

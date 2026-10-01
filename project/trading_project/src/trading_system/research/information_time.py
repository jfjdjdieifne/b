"""Module 6.2A-0 V1.2: immutable research information-time contracts.

The phase order is a logical serialization of certified completed-row batch
semantics. It is not a claim about measured sub-row or wall-clock latency.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Optional

import numpy as np
import pandas as pd


class ResearchInformationTimeError(Exception):
    """Base information-time contract error."""


class InformationKeyError(ResearchInformationTimeError):
    """Invalid or incomparable information key."""


class TimelineAdapterError(ResearchInformationTimeError):
    """Invalid explicit timeline adapter or source index."""


class InformationPhase(Enum):
    BAR_PRE_CLOSE = "BAR_PRE_CLOSE"
    COMPLETED_ROW_AVAILABLE = "COMPLETED_ROW_AVAILABLE"
    RESEARCH_SNAPSHOT_AVAILABLE = "RESEARCH_SNAPSHOT_AVAILABLE"


INFORMATION_KEY_VERSION: Final = "INFORMATION_KEY_V1_2"
POSITIONAL_ADAPTER_VERSION: Final = "POSITIONAL_TIMELINE_V1_2"
TIME_INDEXED_ADAPTER_VERSION: Final = "TIME_INDEXED_TIMELINE_V1_2"

_PHASE_RANK: Final = {
    InformationPhase.BAR_PRE_CLOSE: 0,
    InformationPhase.COMPLETED_ROW_AVAILABLE: 1,
    InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE: 2,
}


def _strict_nonnegative_int(value, field: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise InformationKeyError(f"{field} must be an integer")
    result = int(value)
    if result < 0:
        raise InformationKeyError(f"{field} must be nonnegative")
    return result


@dataclass(frozen=True, eq=False)
class InformationKey:
    information_key_version: str
    timeline_id: str
    bar_position: int
    event_time_utc: Optional[pd.Timestamp]
    information_phase: InformationPhase
    deterministic_sequence: int

    def __post_init__(self) -> None:
        if self.information_key_version != INFORMATION_KEY_VERSION:
            raise InformationKeyError("unsupported information key version")
        if not isinstance(self.timeline_id, str) or not self.timeline_id:
            raise InformationKeyError("timeline_id must be a nonempty string")
        object.__setattr__(
            self, "bar_position", _strict_nonnegative_int(self.bar_position, "bar_position")
        )
        object.__setattr__(
            self,
            "deterministic_sequence",
            _strict_nonnegative_int(
                self.deterministic_sequence, "deterministic_sequence"
            ),
        )
        if not isinstance(self.information_phase, InformationPhase):
            raise InformationKeyError("invalid information phase")
        timestamp = self.event_time_utc
        if timestamp is not None:
            if not isinstance(timestamp, pd.Timestamp) or pd.isna(timestamp):
                raise InformationKeyError("event_time_utc must be a valid Timestamp")
            if timestamp.tz is None:
                raise InformationKeyError("event_time_utc must be timezone aware")
            object.__setattr__(self, "event_time_utc", timestamp.tz_convert("UTC"))

    def _comparison_tuple(self) -> tuple[int, int, int]:
        return (
            self.bar_position,
            _PHASE_RANK[self.information_phase],
            self.deterministic_sequence,
        )

    def _timestamp_identity(self) -> tuple[int, int]:
        if self.event_time_utc is None:
            return (0, 0)
        return (1, int(self.event_time_utc.value))

    def _identity_tuple(self) -> tuple[int, int, int, int, int]:
        return self._comparison_tuple() + self._timestamp_identity()

    def _require_comparable(self, other: object) -> "InformationKey":
        if not isinstance(other, InformationKey):
            raise InformationKeyError("InformationKey comparison requires InformationKey")
        if self.information_key_version != other.information_key_version:
            raise InformationKeyError("information key version mismatch")
        if self.timeline_id != other.timeline_id:
            raise InformationKeyError("cross-timeline comparison forbidden")
        return other

    def _ordering_operands(
        self, other: object
    ) -> tuple["InformationKey", tuple[int, int, int], tuple[int, int, int]]:
        comparable = self._require_comparable(other)
        left_order = self._comparison_tuple()
        right_order = comparable._comparison_tuple()
        if (
            left_order == right_order
            and self._timestamp_identity() != comparable._timestamp_identity()
        ):
            raise InformationKeyError(
                "conflicting timestamp provenance at one causal coordinate"
            )
        return comparable, left_order, right_order

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InformationKey):
            return False
        comparable = self._require_comparable(other)
        return self._identity_tuple() == comparable._identity_tuple()

    def __lt__(self, other: object) -> bool:
        _, left_order, right_order = self._ordering_operands(other)
        return left_order < right_order

    def __le__(self, other: object) -> bool:
        _, left_order, right_order = self._ordering_operands(other)
        return left_order <= right_order

    def __gt__(self, other: object) -> bool:
        _, left_order, right_order = self._ordering_operands(other)
        return left_order > right_order

    def __ge__(self, other: object) -> bool:
        _, left_order, right_order = self._ordering_operands(other)
        return left_order >= right_order

    def __hash__(self) -> int:
        return hash(
            (
                self.information_key_version,
                self.timeline_id,
                self._identity_tuple(),
            )
        )


@dataclass(frozen=True)
class PositionalTimelineAdapter:
    timeline_id: str
    adapter_version: str = POSITIONAL_ADAPTER_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.timeline_id, str) or not self.timeline_id:
            raise TimelineAdapterError("timeline_id must be a nonempty string")
        if self.adapter_version != POSITIONAL_ADAPTER_VERSION:
            raise TimelineAdapterError("unsupported positional adapter version")

    def validate_index(self, index: pd.Index) -> None:
        if isinstance(index, pd.DatetimeIndex):
            raise TimelineAdapterError("positional adapter rejects DatetimeIndex")
        if index.has_duplicates or not index.is_monotonic_increasing:
            raise TimelineAdapterError("positional index contract")

    def key_for_position(
        self,
        index: pd.Index,
        bar_position: int,
        information_phase: InformationPhase,
        deterministic_sequence: int = 0,
    ) -> InformationKey:
        self.validate_index(index)
        position = _strict_nonnegative_int(bar_position, "bar_position")
        if position >= len(index):
            raise TimelineAdapterError("bar_position outside positional timeline")
        return InformationKey(
            information_key_version=INFORMATION_KEY_VERSION,
            timeline_id=self.timeline_id,
            bar_position=position,
            event_time_utc=None,
            information_phase=information_phase,
            deterministic_sequence=deterministic_sequence,
        )

    def validate_key(self, key: InformationKey, index: pd.Index) -> None:
        if not isinstance(key, InformationKey):
            raise TimelineAdapterError("explicit InformationKey required")
        self.validate_index(index)
        if key.timeline_id != self.timeline_id:
            raise TimelineAdapterError("wrong timeline")
        if key.bar_position >= len(index):
            raise TimelineAdapterError("as-of position outside timeline")
        if key.event_time_utc is not None:
            raise TimelineAdapterError("positional key must not contain timestamp")


@dataclass(frozen=True)
class TimeIndexedTimelineAdapter:
    timeline_id: str
    adapter_version: str = TIME_INDEXED_ADAPTER_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.timeline_id, str) or not self.timeline_id:
            raise TimelineAdapterError("timeline_id must be a nonempty string")
        if self.adapter_version != TIME_INDEXED_ADAPTER_VERSION:
            raise TimelineAdapterError("unsupported time adapter version")

    def validate_index(self, index: pd.Index) -> None:
        if not isinstance(index, pd.DatetimeIndex):
            raise TimelineAdapterError("time adapter requires DatetimeIndex")
        if index.tz is None:
            raise TimelineAdapterError("time adapter requires timezone-aware index")
        if index.hasnans:
            raise TimelineAdapterError("time adapter rejects NaT")
        # Closed 5.1 and decision index contracts reject duplicate indexes.
        if index.has_duplicates:
            raise TimelineAdapterError("time adapter rejects duplicate timestamps")
        if not index.is_monotonic_increasing:
            raise TimelineAdapterError("nonmonotonic temporal order")

    def key_for_position(
        self,
        index: pd.Index,
        bar_position: int,
        information_phase: InformationPhase,
        deterministic_sequence: int = 0,
    ) -> InformationKey:
        self.validate_index(index)
        position = _strict_nonnegative_int(bar_position, "bar_position")
        if position >= len(index):
            raise TimelineAdapterError("bar_position outside time-indexed timeline")
        timestamp = pd.Timestamp(index[position]).tz_convert("UTC")
        return InformationKey(
            information_key_version=INFORMATION_KEY_VERSION,
            timeline_id=self.timeline_id,
            bar_position=position,
            event_time_utc=timestamp,
            information_phase=information_phase,
            deterministic_sequence=deterministic_sequence,
        )

    def validate_key(self, key: InformationKey, index: pd.Index) -> None:
        if not isinstance(key, InformationKey):
            raise TimelineAdapterError("explicit InformationKey required")
        self.validate_index(index)
        if key.timeline_id != self.timeline_id:
            raise TimelineAdapterError("wrong timeline")
        if key.bar_position >= len(index):
            raise TimelineAdapterError("as-of position outside timeline")
        expected = pd.Timestamp(index[key.bar_position]).tz_convert("UTC")
        if key.event_time_utc != expected:
            raise TimelineAdapterError("key timestamp does not match row position")


def information_time_contract_manifest() -> pd.DataFrame:
    rows = [
        {
            "record_type": "INFORMATION_KEY_FIELD",
            "name": name,
            "value": dtype,
            "serialization_order": order,
        }
        for order, (name, dtype) in enumerate(
            (
                ("information_key_version", "string"),
                ("timeline_id", "string"),
                ("bar_position", "nonnegative_integer"),
                ("event_time_utc", "nullable_utc_timestamp"),
                ("information_phase", "InformationPhase"),
                ("deterministic_sequence", "nonnegative_integer"),
            )
        )
    ]
    offset = len(rows)
    for phase, rank in sorted(_PHASE_RANK.items(), key=lambda item: item[1]):
        rows.append(
            {
                "record_type": "INFORMATION_PHASE",
                "name": phase.value,
                "value": str(rank),
                "serialization_order": offset + rank,
            }
        )
    rows.extend(
        (
            {
                "record_type": "ADAPTER_VERSION",
                "name": "POSITIONAL",
                "value": POSITIONAL_ADAPTER_VERSION,
                "serialization_order": len(rows),
            },
            {
                "record_type": "ADAPTER_VERSION",
                "name": "TIME_INDEXED",
                "value": TIME_INDEXED_ADAPTER_VERSION,
                "serialization_order": len(rows) + 1,
            },
        )
    )
    return pd.DataFrame(
        rows,
        columns=("record_type", "name", "value", "serialization_order"),
    )

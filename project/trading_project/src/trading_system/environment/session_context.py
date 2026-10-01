"""
Layer 1 — Module 1.2
Causal Session Context Engine
VERSION 1 — Rebuilt From Scratch

PURPOSE
-------
Describe when each completed observation occurred. Session membership and
calendar encodings are context only: this module assigns no bullish/bearish,
profitability, confluence, kill-zone, or trading score meaning.

Crypto trades continuously. Configured sessions are overlapping wall-clock
contexts, not exchange closure rules and not mutually exclusive labels.

CAUSALITY
---------
Every generated value at row i is a pure function of timestamp[i] and explicit
immutable session configuration. No future timestamp or market value is read.

Pandas DatetimeIndex `freq` is whole-index metadata that can disappear merely
because future timestamps become irregular. Output therefore preserves index
labels, order, timezone, and name but canonicalizes `freq=None`, preventing
suffix-dependent metadata from masquerading as a row-level causal difference.

SESSION SEMANTICS
-----------------
Each session is a local-wall-clock half-open interval [start_local, end_local)
in an explicit IANA timezone. Equal start/end is rejected; V1 does not encode
a 24-hour session. start<end is same-local-day; start>end crosses midnight.

IANA timezone conversion handles historical/current DST rules. No fixed UTC
offset or manual month table is used. V1 intentionally omits session progress:
elapsed-duration semantics around ambiguous/nonexistent DST wall times require
a separate explicit contract and should not be implied by wall-clock activity.

CALENDAR ENCODING
-----------------
UTC time-of-day is encoded continuously on the 24-hour circle. UTC weekday is
encoded on the 7-day circle. Constants 24, 7, and 2*pi are calendar and
mathematical definitions, not strategy parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Final, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import math
import re
import numpy as np
import pandas as pd


class SessionContextError(Exception):
    """Base exception for Module 1.2."""


class SessionConfigError(SessionContextError):
    """Invalid session definition or conflicting configured output surface."""


class SessionContextDataError(SessionContextError):
    """Invalid DataFrame, DatetimeIndex, ordering, or output collision."""


_SESSION_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_BASE_OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
    "hour_utc_sin",
    "hour_utc_cos",
    "weekday_sin",
    "weekday_cos",
    "active_session_count",
)


@dataclass(frozen=True)
class SessionDefinition:
    """Immutable local-wall-clock session definition.

    `name` is restricted to an explicit ASCII identifier. The output key is
    its lowercase form. Distinct names that normalize to the same key are
    rejected by the engine rather than silently merged.
    """

    name: str
    timezone: str
    start_local: time
    end_local: time
    _zone: ZoneInfo = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _SESSION_NAME_PATTERN.fullmatch(
            self.name
        ):
            raise SessionConfigError(
                "Session name must match ^[A-Za-z][A-Za-z0-9_]*$."
            )

        if not isinstance(self.timezone, str) or not self.timezone:
            raise SessionConfigError("timezone must be a non-empty IANA timezone name.")

        try:
            zone = ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
            raise SessionConfigError(
                f"Invalid IANA timezone {self.timezone!r}."
            ) from exc

        for label, value in (
            ("start_local", self.start_local),
            ("end_local", self.end_local),
        ):
            if not isinstance(value, time):
                raise SessionConfigError(f"{label} must be a datetime.time object.")
            if value.tzinfo is not None:
                raise SessionConfigError(
                    f"{label} must be a naive local wall-clock time; timezone belongs "
                    "in SessionDefinition.timezone."
                )

        if self.start_local == self.end_local:
            raise SessionConfigError(
                "start_local == end_local is ambiguous; V1 does not define 24h sessions."
            )

        object.__setattr__(self, "_zone", zone)

    @property
    def output_key(self) -> str:
        return self.name.lower()

    @property
    def zone(self) -> ZoneInfo:
        return self._zone

    @property
    def active_column(self) -> str:
        return f"session_{self.output_key}_active"


class CausalSessionContextEngine:
    """Stateless batch temporal-context engine with no default session schedule."""

    def __init__(self, sessions: Iterable[SessionDefinition] = ()) -> None:
        try:
            configured = tuple(sessions)
        except TypeError as exc:
            raise SessionConfigError(
                "sessions must be an iterable of SessionDefinition objects."
            ) from exc

        for item in configured:
            if not isinstance(item, SessionDefinition):
                raise SessionConfigError(
                    "Every configured session must be a SessionDefinition."
                )

        names = [session.name for session in configured]
        if len(names) != len(set(names)):
            raise SessionConfigError("Duplicate session names are forbidden.")

        output_columns = [session.active_column for session in configured]
        if len(output_columns) != len(set(output_columns)):
            raise SessionConfigError(
                "Distinct session names normalize to colliding output columns."
            )

        self._sessions = configured
        self._output_columns = tuple(output_columns)

    @property
    def sessions(self) -> tuple[SessionDefinition, ...]:
        return self._sessions

    @staticmethod
    def _validate_input(df: pd.DataFrame, output_columns: tuple[str, ...]) -> None:
        if not isinstance(df, pd.DataFrame):
            raise SessionContextDataError("df must be a pandas DataFrame.")

        if df.columns.has_duplicates:
            duplicates = df.columns[df.columns.duplicated()].tolist()
            raise SessionContextDataError(
                f"Duplicate input columns are forbidden: {duplicates!r}."
            )

        if not isinstance(df.index, pd.DatetimeIndex):
            raise SessionContextDataError(
                "Input must use a timezone-aware pandas DatetimeIndex."
            )

        if df.index.tz is None:
            raise SessionContextDataError(
                "Timezone-naive DatetimeIndex is rejected; no timezone is assumed."
            )

        if df.index.hasnans:
            raise SessionContextDataError("DatetimeIndex contains NaT.")

        if df.index.has_duplicates:
            raise SessionContextDataError("Duplicate timestamps are forbidden.")

        if not df.index.is_monotonic_increasing:
            raise SessionContextDataError(
                "DatetimeIndex must already be monotonic increasing; silent sorting "
                "is forbidden."
            )

        generated = set(_BASE_OUTPUT_COLUMNS).union(output_columns)
        collisions = [column for column in df.columns if column in generated]
        if collisions:
            raise SessionContextDataError(
                f"Generated output columns already exist: {collisions!r}."
            )

    @staticmethod
    def _session_activity(
        index: pd.DatetimeIndex,
        definition: SessionDefinition,
    ) -> np.ndarray:
        local_index = index.tz_convert(definition.zone)
        local_times = local_index.time
        start = definition.start_local
        end = definition.end_local

        if start < end:
            return np.fromiter(
                (start <= current < end for current in local_times),
                dtype=bool,
                count=len(local_times),
            )

        return np.fromiter(
            (current >= start or current < end for current in local_times),
            dtype=bool,
            count=len(local_times),
        )

    @staticmethod
    def _calendar_features(index: pd.DatetimeIndex) -> dict[str, np.ndarray]:
        utc = index.tz_convert("UTC")

        fractional_hour = (
            utc.hour.to_numpy(dtype=np.float64)
            + utc.minute.to_numpy(dtype=np.float64) / 60.0
            + utc.second.to_numpy(dtype=np.float64) / 3_600.0
            + utc.microsecond.to_numpy(dtype=np.float64) / 3_600_000_000.0
            + utc.nanosecond.to_numpy(dtype=np.float64) / 3_600_000_000_000.0
        )
        hour_angle = (2.0 * math.pi / 24.0) * fractional_hour

        weekday = utc.dayofweek.to_numpy(dtype=np.float64)
        weekday_angle = (2.0 * math.pi / 7.0) * weekday

        return {
            "hour_utc_sin": np.sin(hour_angle),
            "hour_utc_cos": np.cos(hour_angle),
            "weekday_sin": np.sin(weekday_angle),
            "weekday_cos": np.cos(weekday_angle),
        }

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return temporal context without mutating, sorting, or reindexing input."""
        self._validate_input(df, self._output_columns)

        out = df.copy(deep=True)
        # `freq` summarizes the complete index and can change when only a
        # future suffix changes. Canonicalize that non-row metadata while
        # preserving every timestamp label, timezone, order, and index name.
        out.index = pd.DatetimeIndex(df.index, freq=None)

        for column, values in self._calendar_features(df.index).items():
            out[column] = values

        active_count = np.zeros(len(df), dtype=np.int64)
        for definition in self._sessions:
            active = self._session_activity(df.index, definition)
            out[definition.active_column] = active
            active_count += active.astype(np.int64)

        out["active_session_count"] = active_count
        return out


class _SessionContextAuditEngine(CausalSessionContextEngine):
    """Named adapter used only to make Module 0.1 audit output explicit."""


if __name__ == "__main__":
    london = SessionDefinition(
        name="London",
        timezone="Europe/London",
        start_local=time(8, 0),
        end_local=time(9, 0),
    )
    new_york = SessionDefinition(
        name="New_York",
        timezone="America/New_York",
        start_local=time(9, 30),
        end_local=time(10, 0),
    )
    engine = CausalSessionContextEngine((london, new_york))

    # London winter/summer DST representation.
    london_index = pd.DatetimeIndex(
        ["2024-01-15 08:30:00+00:00", "2024-07-15 07:30:00+00:00"]
    )
    london_out = engine.analyze(pd.DataFrame(index=london_index))
    assert london_out["session_london_active"].tolist() == [True, True]

    # New York winter/summer DST representation.
    ny_index = pd.DatetimeIndex(
        ["2024-01-15 14:45:00+00:00", "2024-07-15 13:45:00+00:00"]
    )
    ny_out = engine.analyze(pd.DataFrame(index=ny_index))
    assert ny_out["session_new_york_active"].tolist() == [True, True]

    from trading_system.audit.causal_state import (
        ReentrancyPolicy,
        verify_state_isolation,
        verify_truncation_invariance,
    )

    audit_index_a = pd.date_range("2024-03-01", periods=401, freq="h", tz="UTC")
    audit_index_b = pd.date_range("2024-10-01", periods=409, freq="37min", tz="UTC")
    audit_a = pd.DataFrame({"payload": np.arange(len(audit_index_a))}, index=audit_index_a)
    audit_b = pd.DataFrame({"payload": np.arange(len(audit_index_b))}, index=audit_index_b)

    factory = lambda: _SessionContextAuditEngine((london, new_york))
    truncation = verify_truncation_invariance(
        factory,
        audit_a,
        additional_split_points=[1, 2, 17, 127, 256, 400],
    )
    assert truncation and all(result.passed for result in truncation)

    state = verify_state_isolation(
        factory,
        audit_a,
        audit_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed

    print("=" * 72)
    print("MODULE 1.2 V1 SELF-VERIFICATION PASSED")
    print("Session context is timestamp-only, timezone-aware, and DST-rule based.")
    print("=" * 72)

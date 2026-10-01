"""
Layer 2 — Module 2.2
Causal Liquidity Map / Level Lifecycle Engine
VERSION 1.1 — Rebuilt From Scratch

PURPOSE
-------
Retain multiple immutable HIGH_SIDE/LOW_SIDE price-level candidates created
only from causally confirmed Module 2.1A swings. These are liquidity-relevant
price references; OHLC cannot prove that resting orders exist there.

TIMING
------
Prior eligible levels are evaluated first. A current confirmed swing then
creates a new source level at its confirmation row. The new level is not
monitored until a subsequent row. Origin rows are never backfilled.

IDENTITY AND PROXIMITY
----------------------
Every confirmed swing receives a unique deterministic source level_id and an
immutable price. Levels are never merged. At creation, the new source is
compared with the nearest PRIOR same-side source using a scale-invariant
nearest-distance fraction. Exactly one valid nearest-distance observation per
new level is ranked against prior shared HIGH/LOW distance history, then pushed.
A low percentile means unusually close relative to prior nearest-neighbor
distances; it is not a hidden binary equal-level decision.
`nearest_distance_reference_history_count` counts observations in the shared
HIGH/LOW reference distribution available before evaluating the new level. It
can be positive while the current level has no prior same-side neighbor and
thus a NaN nearest distance. V1 implements no clustering policy.

LIFECYCLE EVENTS
----------------
For every retained source level, V1 emits at most one of each:
LEVEL_CREATED, FIRST_TOUCH, FIRST_WICK_BREACH,
FIRST_WICK_ONLY_EXCURSION, FIRST_CLOSE_BREACH,
FIRST_RECLAIM_AFTER_CLOSE_BREACH.

A bar may legitimately emit touch, wick breach, and wick-only/close breach for
the same level because they are distinct factual statements. A first wick-only
excursion may be established only before any first close breach for that level.
After close breach, a subsequent close back across is represented by first
reclaim, not by a late-created wick-only event. Reclaim requires a subsequent
row. Levels are retained after all facts.

MULTI-LEVEL OUTPUT
------------------
The primary bar DataFrame contains auditable creation metadata and per-bar
aggregate event counts. The normalized secondary event DataFrame preserves one
row per level event. Serialization is sorted mechanically by event_position,
level_id, then fixed event-type order and does not imply intrabar sequence.
Module 0.1 audits only the primary DataFrame; V1 tests the event table with
separate exact truncation and state-isolation checks.

PERFORMANCE
-----------
Correctness V1 scans all known historical levels on every bar: O(N*L), worst
case O(N^2) as level count grows. No age, distance, or count pruning is hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Optional

import math
import numpy as np
import pandas as pd

from trading_system.core.causal_percentile import CausalPercentileTracker


class LiquidityMapError(Exception):
    """Base exception for Module 2.2."""


class LiquidityMapDataError(LiquidityMapError):
    """Input schema/data/upstream event contract violation."""


_A_COLUMNS: Final[tuple[str, ...]] = (
    "swing_high_confirmed", "swing_low_confirmed", "swing_origin_position",
    "swing_price", "swing_confirmation_position",
)
_B_COLUMNS: Final[tuple[str, ...]] = (
    "structure_event_type", "swing_sequence_class", "comparison_available",
    "previous_same_type_price", "previous_same_type_origin_position",
    "current_structure_swing_price", "current_structure_origin_position",
    "current_structure_confirmation_position", "same_type_log_price_change",
)
_HIGH_CLASSES = frozenset({"UNCLASSIFIED", "HH", "LH", "EH"})
_LOW_CLASSES = frozenset({"UNCLASSIFIED", "HL", "LL", "EL"})

_EVENT_ORDER: Final[dict[str, int]] = {
    "LEVEL_CREATED": 0,
    "FIRST_TOUCH": 1,
    "FIRST_WICK_BREACH": 2,
    "FIRST_WICK_ONLY_EXCURSION": 3,
    "FIRST_CLOSE_BREACH": 4,
    "FIRST_RECLAIM_AFTER_CLOSE_BREACH": 5,
}

_BAR_OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
    "liquidity_level_created", "created_level_id", "created_level_side",
    "created_level_price", "created_level_origin_position",
    "created_level_confirmation_position", "created_level_source_class",
    "nearest_prior_same_side_level_id", "nearest_same_side_distance_fraction",
    "nearest_distance_percentile", "nearest_distance_reference_history_count",
    "high_side_first_touch_count", "low_side_first_touch_count",
    "high_side_first_wick_breach_count", "low_side_first_wick_breach_count",
    "high_side_first_wick_only_count", "low_side_first_wick_only_count",
    "high_side_first_close_breach_count", "low_side_first_close_breach_count",
    "high_side_first_reclaim_count", "low_side_first_reclaim_count",
    "known_high_side_level_count", "known_low_side_level_count",
)

_EVENT_COLUMNS: Final[tuple[str, ...]] = (
    "event_position", "level_id", "side", "event_type",
    "source_origin_position", "source_confirmation_position", "source_class",
    "immutable_level_price", "event_price", "event_close",
    "overshoot_fraction", "nearest_prior_same_side_level_id",
    "nearest_same_side_distance_fraction", "nearest_distance_percentile",
    "nearest_distance_reference_history_count", "level_age_bars",
)


@dataclass
class _Level:
    level_id: int
    side: str
    price: float
    origin: int
    confirmation: int
    source_class: str
    first_touch: Optional[int] = None
    first_wick: Optional[int] = None
    first_wick_only: Optional[int] = None
    first_close: Optional[int] = None
    first_reclaim: Optional[int] = None


class CausalLiquidityMapEngine:
    """Stateless batch engine returning `(bar_surface, normalized_events)`."""

    @staticmethod
    def _validate_input(df: pd.DataFrame) -> None:
        if not isinstance(df, pd.DataFrame):
            raise LiquidityMapDataError("df must be a pandas DataFrame.")
        if df.columns.has_duplicates:
            raise LiquidityMapDataError("Duplicate input columns are forbidden.")
        required = ("high", "low", "close") + _A_COLUMNS + _B_COLUMNS
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise LiquidityMapDataError(f"Missing required columns: {missing!r}.")
        collisions = [c for c in _BAR_OUTPUT_COLUMNS if c in df.columns]
        if collisions:
            raise LiquidityMapDataError(
                f"Output columns already exist and would be overwritten: {collisions!r}."
            )
        if df.index.has_duplicates:
            raise LiquidityMapDataError("Duplicate index labels are forbidden.")
        if not df.index.is_monotonic_increasing:
            raise LiquidityMapDataError("Index must already be monotonic increasing.")

        values = {}
        for c in ("high", "low", "close"):
            s = df[c]
            if (
                pd.api.types.is_bool_dtype(s.dtype)
                or pd.api.types.is_complex_dtype(s.dtype)
                or not pd.api.types.is_numeric_dtype(s.dtype)
            ):
                raise LiquidityMapDataError(f"Column {c!r} must be real numeric.")
            a = s.to_numpy(dtype=np.float64, na_value=np.nan)
            if not np.isfinite(a).all():
                raise LiquidityMapDataError(f"Column {c!r} contains NaN or infinity.")
            values[c] = a
        high, low, close = values["high"], values["low"], values["close"]
        if (high < low).any():
            raise LiquidityMapDataError("high < low detected.")
        if ((close < low) | (close > high)).any():
            raise LiquidityMapDataError("close lies outside [low, high].")

        for c in ("swing_high_confirmed", "swing_low_confirmed", "comparison_available"):
            if not pd.api.types.is_bool_dtype(df[c].dtype) or df[c].isna().any():
                raise LiquidityMapDataError(f"Column {c!r} must be non-missing boolean.")

        high_flags = df["swing_high_confirmed"].to_numpy(dtype=bool)
        low_flags = df["swing_low_confirmed"].to_numpy(dtype=bool)
        if (high_flags & low_flags).any():
            raise LiquidityMapDataError("Simultaneous HIGH/LOW confirmation is invalid.")

        seen_high = False
        seen_low = False
        last_high_price: Optional[float] = None
        last_low_price: Optional[float] = None
        last_high_origin: Optional[int] = None
        last_low_origin: Optional[int] = None
        n = len(df)

        def require_missing(value: object, column: str, row: int) -> None:
            missing = pd.isna(value)
            if not isinstance(missing, (bool, np.bool_)) or not bool(missing):
                raise LiquidityMapDataError(
                    f"Row {row} must have missing {column}."
                )

        for i in range(n):
            h, l = bool(high_flags[i]), bool(low_flags[i])
            et = str(df["structure_event_type"].iloc[i])
            sc = str(df["swing_sequence_class"].iloc[i])
            comparison = bool(df["comparison_available"].iloc[i])
            if not h and not l:
                if et != "NONE" or sc != "NONE" or comparison:
                    raise LiquidityMapDataError(f"Malformed non-event row {i}.")
                for c in (
                    "current_structure_swing_price",
                    "current_structure_origin_position",
                    "current_structure_confirmation_position",
                    "previous_same_type_price",
                    "previous_same_type_origin_position",
                    "same_type_log_price_change",
                ):
                    require_missing(df[c].iloc[i], c, i)
                continue
            expected_type = "HIGH" if h else "LOW"
            allowed = _HIGH_CLASSES if h else _LOW_CLASSES
            if et != expected_type or sc not in allowed:
                raise LiquidityMapDataError(f"Malformed event/type/class row {i}.")
            for c in ("swing_origin_position", "swing_confirmation_position"):
                v = df[c].iloc[i]
                if pd.isna(v) or isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer)):
                    raise LiquidityMapDataError(f"Invalid {c} at row {i}.")
                v = int(v)
                if v < 0 or v >= n:
                    raise LiquidityMapDataError(f"Out-of-range {c} at row {i}.")
            origin = int(df["swing_origin_position"].iloc[i])
            confirmation = int(df["swing_confirmation_position"].iloc[i])
            if confirmation != i or origin > confirmation:
                raise LiquidityMapDataError(f"Invalid positional event metadata at row {i}.")
            try:
                price = float(df["swing_price"].iloc[i])
                current_price = float(df["current_structure_swing_price"].iloc[i])
                current_origin = int(df["current_structure_origin_position"].iloc[i])
                current_confirmation = int(
                    df["current_structure_confirmation_position"].iloc[i]
                )
            except (TypeError, ValueError, OverflowError) as exc:
                raise LiquidityMapDataError(
                    f"Invalid event price/current metadata at row {i}."
                ) from exc
            if not math.isfinite(price) or not math.isfinite(current_price):
                raise LiquidityMapDataError(f"Invalid swing price at row {i}.")
            if (
                current_price != price
                or current_origin != origin
                or current_confirmation != confirmation
                or current_confirmation != i
            ):
                raise LiquidityMapDataError(f"Inconsistent 2.1B metadata at row {i}.")

            seen = seen_high if h else seen_low
            previous_price = last_high_price if h else last_low_price
            previous_origin = last_high_origin if h else last_low_origin
            if not seen:
                if sc != "UNCLASSIFIED" or comparison:
                    raise LiquidityMapDataError(f"Invalid first-event semantics at row {i}.")
                require_missing(df["previous_same_type_price"].iloc[i], "previous_same_type_price", i)
                require_missing(
                    df["previous_same_type_origin_position"].iloc[i],
                    "previous_same_type_origin_position",
                    i,
                )
                require_missing(df["same_type_log_price_change"].iloc[i], "same_type_log_price_change", i)
            else:
                if sc == "UNCLASSIFIED" or not comparison:
                    raise LiquidityMapDataError(f"Invalid comparison semantics at row {i}.")
                try:
                    upstream_previous_price = float(df["previous_same_type_price"].iloc[i])
                    upstream_previous_origin = int(
                        df["previous_same_type_origin_position"].iloc[i]
                    )
                except (TypeError, ValueError, OverflowError) as exc:
                    raise LiquidityMapDataError(
                        f"Invalid previous same-type metadata at row {i}."
                    ) from exc
                if (
                    not math.isfinite(upstream_previous_price)
                    or upstream_previous_price != previous_price
                    or upstream_previous_origin != previous_origin
                ):
                    raise LiquidityMapDataError(
                        f"Inconsistent previous same-type metadata at row {i}."
                    )
                log_value = df["same_type_log_price_change"].iloc[i]
                if price > 0.0 and upstream_previous_price > 0.0:
                    expected_log = math.log(price) - math.log(upstream_previous_price)
                    if pd.isna(log_value) or float(log_value) != expected_log:
                        raise LiquidityMapDataError(
                            f"Inconsistent same_type_log_price_change at row {i}."
                        )
                else:
                    require_missing(log_value, "same_type_log_price_change", i)

            if h:
                seen_high = True
                last_high_price = price
                last_high_origin = origin
            else:
                seen_low = True
                last_low_price = price
                last_low_origin = origin

    @staticmethod
    def _distance(a: float, b: float) -> float:
        denominator = max(abs(a), abs(b))
        if denominator == 0.0:
            return 0.0 if a == b else float("nan")
        return abs(a - b) / denominator

    @staticmethod
    def _overshoot(value: float, level_price: float) -> float:
        if value <= 0.0:
            return float("nan")
        denominator = abs(level_price)
        return float("nan") if denominator == 0.0 else value / denominator

    @staticmethod
    def _empty_event_table() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "event_position": pd.array([], dtype="Int64"),
                "level_id": pd.array([], dtype="Int64"),
                "side": pd.array([], dtype="string"),
                "event_type": pd.array([], dtype="string"),
                "source_origin_position": pd.array([], dtype="Int64"),
                "source_confirmation_position": pd.array([], dtype="Int64"),
                "source_class": pd.array([], dtype="string"),
                "immutable_level_price": pd.Series([], dtype="float64"),
                "event_price": pd.Series([], dtype="float64"),
                "event_close": pd.Series([], dtype="float64"),
                "overshoot_fraction": pd.Series([], dtype="float64"),
                "nearest_prior_same_side_level_id": pd.array([], dtype="Int64"),
                "nearest_same_side_distance_fraction": pd.Series([], dtype="float64"),
                "nearest_distance_percentile": pd.Series([], dtype="float64"),
                "nearest_distance_reference_history_count": pd.array([], dtype="Int64"),
                "level_age_bars": pd.array([], dtype="Int64"),
            }
        )

    def analyze(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        self._validate_input(df)
        n = len(df)
        high = df["high"].to_numpy(dtype=np.float64)
        low = df["low"].to_numpy(dtype=np.float64)
        close = df["close"].to_numpy(dtype=np.float64)
        high_flags = df["swing_high_confirmed"].to_numpy(dtype=bool)
        low_flags = df["swing_low_confirmed"].to_numpy(dtype=bool)

        created = np.zeros(n, dtype=bool)
        created_id = pd.array([pd.NA] * n, dtype="Int64")
        created_side = np.full(n, "NONE", dtype=object)
        created_price = np.full(n, np.nan)
        created_origin = pd.array([pd.NA] * n, dtype="Int64")
        created_confirmation = pd.array([pd.NA] * n, dtype="Int64")
        created_class = np.full(n, "NONE", dtype=object)
        nearest_id = pd.array([pd.NA] * n, dtype="Int64")
        nearest_fraction = np.full(n, np.nan)
        nearest_percentile = np.full(n, np.nan)
        nearest_count = np.zeros(n, dtype=np.int64)

        count_names = (
            "high_touch", "low_touch", "high_wick", "low_wick",
            "high_wick_only", "low_wick_only", "high_close", "low_close",
            "high_reclaim", "low_reclaim",
        )
        counts = {name: np.zeros(n, dtype=np.int64) for name in count_names}
        known_high = np.zeros(n, dtype=np.int64)
        known_low = np.zeros(n, dtype=np.int64)

        levels: list[_Level] = []
        by_side: dict[str, list[_Level]] = {"HIGH_SIDE": [], "LOW_SIDE": []}
        events: list[dict[str, object]] = []
        distance_tracker = CausalPercentileTracker(nan_policy="skip")

        def append_event(
            i: int,
            level: _Level,
            event_type: str,
            event_price: float,
            overshoot: float = float("nan"),
            prior_id: Optional[int] = None,
            distance: float = float("nan"),
            distance_pct: float = float("nan"),
            distance_n: int = 0,
        ) -> None:
            events.append(
                {
                    "event_position": i,
                    "level_id": level.level_id,
                    "side": level.side,
                    "event_type": event_type,
                    "source_origin_position": level.origin,
                    "source_confirmation_position": level.confirmation,
                    "source_class": level.source_class,
                    "immutable_level_price": level.price,
                    "event_price": event_price,
                    "event_close": close[i],
                    "overshoot_fraction": overshoot,
                    "nearest_prior_same_side_level_id": prior_id,
                    "nearest_same_side_distance_fraction": distance,
                    "nearest_distance_percentile": distance_pct,
                    "nearest_distance_reference_history_count": distance_n,
                    "level_age_bars": i - level.confirmation,
                    "_event_order": _EVENT_ORDER[event_type],
                }
            )

        for i in range(n):
            # Interact with all PRIOR levels; newly confirmed current-row level
            # is created only after this scan.
            for level in levels:
                if level.side == "HIGH_SIDE":
                    touched = high[i] >= level.price
                    wick = high[i] > level.price
                    closed = close[i] > level.price
                    trigger_price = high[i]
                    wick_over = self._overshoot(high[i] - level.price, level.price)
                    close_over = self._overshoot(close[i] - level.price, level.price)
                    prefix = "high"
                else:
                    touched = low[i] <= level.price
                    wick = low[i] < level.price
                    closed = close[i] < level.price
                    trigger_price = low[i]
                    wick_over = self._overshoot(level.price - low[i], level.price)
                    close_over = self._overshoot(level.price - close[i], level.price)
                    prefix = "low"

                if level.first_touch is None and touched:
                    level.first_touch = i
                    counts[f"{prefix}_touch"][i] += 1
                    append_event(i, level, "FIRST_TOUCH", trigger_price)
                if level.first_wick is None and wick:
                    level.first_wick = i
                    counts[f"{prefix}_wick"][i] += 1
                    append_event(i, level, "FIRST_WICK_BREACH", trigger_price, wick_over)
                if (
                    level.first_wick_only is None
                    and level.first_close is None
                    and wick
                    and not closed
                ):
                    level.first_wick_only = i
                    counts[f"{prefix}_wick_only"][i] += 1
                    append_event(
                        i, level, "FIRST_WICK_ONLY_EXCURSION", trigger_price, wick_over
                    )
                if level.first_close is None and closed:
                    level.first_close = i
                    counts[f"{prefix}_close"][i] += 1
                    append_event(i, level, "FIRST_CLOSE_BREACH", close[i], close_over)
                if (
                    level.first_close is not None
                    and i > level.first_close
                    and level.first_reclaim is None
                ):
                    reclaimed = (
                        close[i] <= level.price
                        if level.side == "HIGH_SIDE"
                        else close[i] >= level.price
                    )
                    if reclaimed:
                        level.first_reclaim = i
                        counts[f"{prefix}_reclaim"][i] += 1
                        append_event(
                            i, level, "FIRST_RECLAIM_AFTER_CLOSE_BREACH", close[i]
                        )

            if high_flags[i] or low_flags[i]:
                side = "HIGH_SIDE" if high_flags[i] else "LOW_SIDE"
                price = float(df["swing_price"].iloc[i])
                origin = int(df["swing_origin_position"].iloc[i])
                source_class = str(df["swing_sequence_class"].iloc[i])
                prior_levels = by_side[side]

                prior: Optional[_Level] = None
                distance = float("nan")
                if prior_levels:
                    candidates = [
                        (self._distance(price, candidate.price), candidate.level_id, candidate)
                        for candidate in prior_levels
                    ]
                    finite = [item for item in candidates if math.isfinite(item[0])]
                    if finite:
                        distance, _, prior = min(finite, key=lambda item: (item[0], item[1]))

                observation = distance_tracker.rank(distance)
                history_n = observation.sample_count
                distance_pct = observation.percentile

                level = _Level(
                    level_id=len(levels), side=side, price=price, origin=origin,
                    confirmation=i, source_class=source_class,
                )
                created[i] = True
                created_id[i] = level.level_id
                created_side[i] = side
                created_price[i] = price
                created_origin[i] = origin
                created_confirmation[i] = i
                created_class[i] = source_class
                nearest_count[i] = history_n
                if prior is not None:
                    nearest_id[i] = prior.level_id
                    nearest_fraction[i] = distance
                    nearest_percentile[i] = distance_pct

                append_event(
                    i, level, "LEVEL_CREATED", price,
                    prior_id=None if prior is None else prior.level_id,
                    distance=distance,
                    distance_pct=distance_pct,
                    distance_n=history_n,
                )
                levels.append(level)
                by_side[side].append(level)
                if math.isfinite(distance):
                    distance_tracker.push(distance)

            known_high[i] = len(by_side["HIGH_SIDE"])
            known_low[i] = len(by_side["LOW_SIDE"])

        out = df.copy(deep=True)
        out["liquidity_level_created"] = created
        out["created_level_id"] = created_id
        out["created_level_side"] = pd.array(created_side, dtype="string")
        out["created_level_price"] = created_price
        out["created_level_origin_position"] = created_origin
        out["created_level_confirmation_position"] = created_confirmation
        out["created_level_source_class"] = pd.array(created_class, dtype="string")
        out["nearest_prior_same_side_level_id"] = nearest_id
        out["nearest_same_side_distance_fraction"] = nearest_fraction
        out["nearest_distance_percentile"] = nearest_percentile
        out["nearest_distance_reference_history_count"] = nearest_count
        out["high_side_first_touch_count"] = counts["high_touch"]
        out["low_side_first_touch_count"] = counts["low_touch"]
        out["high_side_first_wick_breach_count"] = counts["high_wick"]
        out["low_side_first_wick_breach_count"] = counts["low_wick"]
        out["high_side_first_wick_only_count"] = counts["high_wick_only"]
        out["low_side_first_wick_only_count"] = counts["low_wick_only"]
        out["high_side_first_close_breach_count"] = counts["high_close"]
        out["low_side_first_close_breach_count"] = counts["low_close"]
        out["high_side_first_reclaim_count"] = counts["high_reclaim"]
        out["low_side_first_reclaim_count"] = counts["low_reclaim"]
        out["known_high_side_level_count"] = known_high
        out["known_low_side_level_count"] = known_low

        if not events:
            return out, self._empty_event_table()
        event_df = pd.DataFrame(events)
        event_df = event_df.sort_values(
            ["event_position", "level_id", "_event_order"], kind="stable"
        ).drop(columns=["_event_order"]).reset_index(drop=True)
        for c in (
            "event_position", "level_id", "source_origin_position",
            "source_confirmation_position", "nearest_prior_same_side_level_id",
            "nearest_distance_reference_history_count", "level_age_bars",
        ):
            event_df[c] = pd.array(event_df[c], dtype="Int64")
        for c in ("side", "event_type", "source_class"):
            event_df[c] = pd.array(event_df[c], dtype="string")
        event_df = event_df.loc[:, list(_EVENT_COLUMNS)]
        return out, event_df


class _LiquidityMapAuditEngine(CausalLiquidityMapEngine):
    """Named adapter; Module 0.1 extracts/audits only tuple element zero."""

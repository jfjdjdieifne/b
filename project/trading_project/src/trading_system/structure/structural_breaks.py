"""
Layer 2 — Module 2.1C
Causal Structural Break Engine
VERSION 1.1

PURPOSE
-------
Consume confirmed swing events and same-type swing-sequence classifications.
Separate factual first breaches of causally available levels from an explicit,
minimal structural interpretation.

PROCESSING ORDER PER COMPLETED ROW
----------------------------------
1. Snapshot structure state and levels eligible before the current row.
2. Evaluate first wick/close breaches against those prior eligible levels.
3. Interpret first close breaches using the pre-row structure state.
4. Rank first overshoots against prior comparable break history, then record.
5. Process the current confirmed swing-sequence event.
6. Update structure state and install the newly confirmed level for later rows.

A level confirmed on row i is never evaluated on row i. It first appears in
`monitored_*` output and becomes breakable on row i+1.

LATEST-REFERENCE SEMANTICS
--------------------------
`monitored_high_*` and `monitored_low_*` describe only the latest confirmed
structural references currently eligible for evaluation. They are not a full
persistent lifecycle registry. A same-type replacement removes the superseded
level from 2.1C monitoring without changing historical output rows. Full
historical liquidity-level lifecycle belongs to a separate downstream module.

STRUCTURE-STATE TABLE
---------------------
Latest comparable HIGH and LOW classes determine state only after both exist:

    HH + HL -> UP_STRUCTURE
    LH + LL -> DOWN_STRUCTURE
    every other fully defined combination, including EH/EL -> MIXED
    either side unavailable -> UNDEFINED

These are sequence-derived structural states. State changes only on confirmed
sequence-event rows. Raw breaks do not independently invalidate, rebuild, or
transition this state in V1.1.

BREAK INTERPRETATION
--------------------
Only first CLOSE breaches receive event-local interpretation:

    pre-state UP_STRUCTURE:
        high close -> BOS_UP
        low close  -> CHOCH_DOWN

    pre-state DOWN_STRUCTURE:
        low close  -> BOS_DOWN
        high close -> CHOCH_UP

    pre-state MIXED/UNDEFINED:
        either side -> UNCLASSIFIED_BREAK

If both sides receive first close breaches on one bar, interpretation is
AMBIGUOUS_DOUBLE_BREAK. Side-specific factual events remain visible. These are
V1 operational definitions, not universal claims about market theory.

HISTORY SEMANTICS
-----------------
HIGH/LOW sides share dimensionless magnitude distributions, but wick and close
histories are separate. `wick_break_evidence` ranks the first wick overshoot for
ANY first wick breach, including a bar that also closes beyond the level. It is
not sweep evidence. `*_wick_only_breach_event` is the separate factual condition
for a wick breach without a same-bar close breach.

Exactly one magnitude is admitted per level's first wick breach and exactly one
per first close breach. All same-row observations are ranked before any same-row
observation is pushed. Empty history yields NaN evidence; no bootstrap or
minimum sample threshold exists.

POSITIONAL CONTRACT
-------------------
All origin/confirmation positions refer to the same DataFrame passed to
`analyze()`. Cross-chunk continuation is not supported in V1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Optional

import math
import numpy as np
import pandas as pd

from trading_system.core.causal_percentile import CausalPercentileTracker


class StructuralBreakError(Exception):
    """Base exception for Module 2.1C."""


class StructuralBreakDataError(StructuralBreakError):
    """Input OHLC, index, upstream event surface, or output contract violation."""


_A_COLUMNS: Final[tuple[str, ...]] = (
    "swing_high_confirmed",
    "swing_low_confirmed",
    "swing_origin_position",
    "swing_price",
    "swing_confirmation_position",
)

_B_COLUMNS: Final[tuple[str, ...]] = (
    "structure_event_type",
    "swing_sequence_class",
    "comparison_available",
    "previous_same_type_price",
    "previous_same_type_origin_position",
    "current_structure_swing_price",
    "current_structure_origin_position",
    "current_structure_confirmation_position",
    "same_type_log_price_change",
)

_ALLOWED_EVENT_TYPES: Final[frozenset[str]] = frozenset({"NONE", "HIGH", "LOW"})
_HIGH_CLASSES: Final[frozenset[str]] = frozenset(
    {"UNCLASSIFIED", "HH", "LH", "EH"}
)
_LOW_CLASSES: Final[frozenset[str]] = frozenset(
    {"UNCLASSIFIED", "HL", "LL", "EL"}
)

_OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
    "monitored_high_price",
    "monitored_high_origin_position",
    "monitored_high_confirmation_position",
    "monitored_high_first_wick_breach_position",
    "monitored_high_first_close_breach_position",
    "monitored_high_wick_breached",
    "monitored_high_close_breached",
    "monitored_low_price",
    "monitored_low_origin_position",
    "monitored_low_confirmation_position",
    "monitored_low_first_wick_breach_position",
    "monitored_low_first_close_breach_position",
    "monitored_low_wick_breached",
    "monitored_low_close_breached",
    "high_wick_breach_event",
    "high_close_breach_event",
    "low_wick_breach_event",
    "low_close_breach_event",
    "high_wick_only_breach_event",
    "low_wick_only_breach_event",
    "high_wick_overshoot_fraction",
    "high_close_overshoot_fraction",
    "low_wick_overshoot_fraction",
    "low_close_overshoot_fraction",
    "high_wick_break_evidence",
    "high_close_break_evidence",
    "low_wick_break_evidence",
    "low_close_break_evidence",
    "wick_break_history_count",
    "close_break_history_count",
    "structure_state_before",
    "structure_state_after",
    "structural_break_event",
)


@dataclass
class _LevelState:
    price: float
    origin_position: int
    confirmation_position: int
    first_wick_breach_position: Optional[int] = None
    first_close_breach_position: Optional[int] = None


class CausalStructuralBreakEngine:
    """Stateless batch lifecycle and structural-interpretation engine."""

    @staticmethod
    def _validate_ohlc_and_schema(df: pd.DataFrame) -> None:
        if not isinstance(df, pd.DataFrame):
            raise StructuralBreakDataError("df must be a pandas DataFrame.")

        if df.columns.has_duplicates:
            duplicates = df.columns[df.columns.duplicated()].tolist()
            raise StructuralBreakDataError(
                f"Duplicate input columns are forbidden: {duplicates!r}."
            )

        required = ("high", "low", "close") + _A_COLUMNS + _B_COLUMNS
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise StructuralBreakDataError(f"Missing required columns: {missing!r}.")

        collisions = [column for column in _OUTPUT_COLUMNS if column in df.columns]
        if collisions:
            raise StructuralBreakDataError(
                f"Output columns already exist and would be overwritten: {collisions!r}."
            )

        if df.index.has_duplicates:
            raise StructuralBreakDataError("Duplicate index labels are forbidden.")
        try:
            ordered = bool(df.index.is_monotonic_increasing)
        except (TypeError, ValueError) as exc:
            raise StructuralBreakDataError(
                "Input index must have a well-defined increasing order."
            ) from exc
        if not ordered:
            raise StructuralBreakDataError(
                "Input index must already be monotonic increasing; silent sorting is forbidden."
            )

        arrays: dict[str, np.ndarray] = {}
        for column in ("high", "low", "close"):
            series = df[column]
            if pd.api.types.is_bool_dtype(series.dtype):
                raise StructuralBreakDataError(
                    f"Column {column!r} must be real numeric, not boolean."
                )
            if pd.api.types.is_complex_dtype(series.dtype):
                raise StructuralBreakDataError(
                    f"Column {column!r} must be real numeric, not complex."
                )
            if not pd.api.types.is_numeric_dtype(series.dtype):
                raise StructuralBreakDataError(
                    f"Column {column!r} must have a numeric dtype."
                )
            try:
                values = series.to_numpy(dtype=np.float64, na_value=np.nan)
            except (TypeError, ValueError, OverflowError) as exc:
                raise StructuralBreakDataError(
                    f"Column {column!r} cannot be converted to float64."
                ) from exc
            if not np.isfinite(values).all():
                raise StructuralBreakDataError(
                    f"Column {column!r} contains NaN or infinity."
                )
            arrays[column] = values

        high = arrays["high"]
        low = arrays["low"]
        close = arrays["close"]
        if np.any(high < low):
            position = int(np.flatnonzero(high < low)[0])
            raise StructuralBreakDataError(f"high < low at position {position}.")
        invalid_close = (close < low) | (close > high)
        if invalid_close.any():
            position = int(np.flatnonzero(invalid_close)[0])
            raise StructuralBreakDataError(
                f"close lies outside [low, high] at position {position}."
            )

    @staticmethod
    def _required_integer(value: object, *, column: str, row: int, n: int) -> int:
        if pd.isna(value):
            raise StructuralBreakDataError(
                f"Event row {row} has missing {column}."
            )
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, np.integer)
        ):
            raise StructuralBreakDataError(
                f"Event row {row} has non-integer {column}: {value!r}."
            )
        result = int(value)
        if result < 0 or result >= n:
            raise StructuralBreakDataError(
                f"Event row {row} has out-of-range {column}: {result}."
            )
        return result

    @staticmethod
    def _required_finite_price(value: object, *, column: str, row: int) -> float:
        if pd.isna(value) or isinstance(value, (bool, np.bool_)):
            raise StructuralBreakDataError(
                f"Event row {row} has invalid {column}."
            )
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise StructuralBreakDataError(
                f"Event row {row} has invalid {column}."
            ) from exc
        if not math.isfinite(result):
            raise StructuralBreakDataError(
                f"Event row {row} has non-finite {column}."
            )
        return result

    @staticmethod
    def _require_missing(value: object, *, column: str, row: int) -> None:
        missing = pd.isna(value)
        if not isinstance(missing, (bool, np.bool_)) or not bool(missing):
            raise StructuralBreakDataError(
                f"Non-event/first-event row {row} must have missing {column}."
            )

    @classmethod
    def _validate_upstream_surface(cls, df: pd.DataFrame) -> None:
        """Validate consumed 2.1A/2.1B contracts without recomputing 2.1B."""
        for column in ("swing_high_confirmed", "swing_low_confirmed"):
            series = df[column]
            if not pd.api.types.is_bool_dtype(series.dtype) or series.isna().any():
                raise StructuralBreakDataError(
                    f"Column {column!r} must be non-missing boolean."
                )

        comparison_series = df["comparison_available"]
        if (
            not pd.api.types.is_bool_dtype(comparison_series.dtype)
            or comparison_series.isna().any()
        ):
            raise StructuralBreakDataError(
                "Column 'comparison_available' must be non-missing boolean."
            )

        numeric_metadata = (
            "swing_origin_position",
            "swing_price",
            "swing_confirmation_position",
            "previous_same_type_price",
            "previous_same_type_origin_position",
            "current_structure_swing_price",
            "current_structure_origin_position",
            "current_structure_confirmation_position",
            "same_type_log_price_change",
        )
        for column in numeric_metadata:
            dtype = df[column].dtype
            if pd.api.types.is_bool_dtype(dtype) or not pd.api.types.is_numeric_dtype(
                dtype
            ):
                raise StructuralBreakDataError(
                    f"Column {column!r} must have a non-boolean numeric dtype."
                )

        n = len(df)
        high_flags = df["swing_high_confirmed"].to_numpy(dtype=bool)
        low_flags = df["swing_low_confirmed"].to_numpy(dtype=bool)
        comparison = comparison_series.to_numpy(dtype=bool)
        event_mask = high_flags | low_flags
        no_event_mask = ~event_mask

        simultaneous = high_flags & low_flags
        if simultaneous.any():
            row = int(np.flatnonzero(simultaneous)[0])
            raise StructuralBreakDataError(
                f"Row {row} confirms HIGH and LOW simultaneously."
            )

        event_type_series = df["structure_event_type"]
        class_series = df["swing_sequence_class"]
        if event_type_series.isna().any():
            raise StructuralBreakDataError("structure_event_type contains missing values.")
        if class_series.isna().any():
            raise StructuralBreakDataError("swing_sequence_class contains missing values.")
        if not event_type_series.isin(_ALLOWED_EVENT_TYPES).all():
            row = int(np.flatnonzero(~event_type_series.isin(_ALLOWED_EVENT_TYPES).to_numpy())[0])
            raise StructuralBreakDataError(
                f"Row {row} has invalid structure_event_type."
            )

        event_types = event_type_series.astype(str).to_numpy(dtype=object)
        classes = class_series.astype(str).to_numpy(dtype=object)
        invalid_none = no_event_mask & (
            (event_types != "NONE") | (classes != "NONE") | comparison
        )
        if invalid_none.any():
            row = int(np.flatnonzero(invalid_none)[0])
            raise StructuralBreakDataError(
                f"Non-event row {row} must use NONE values and no comparison."
            )
        invalid_high = high_flags & (
            (event_types != "HIGH") | ~np.isin(classes, tuple(_HIGH_CLASSES))
        )
        invalid_low = low_flags & (
            (event_types != "LOW") | ~np.isin(classes, tuple(_LOW_CLASSES))
        )
        if invalid_high.any() or invalid_low.any():
            mask = invalid_high | invalid_low
            row = int(np.flatnonzero(mask)[0])
            raise StructuralBreakDataError(
                f"Event/type/class correspondence is invalid at row {row}."
            )

        missing_on_non_events = (
            "current_structure_swing_price",
            "current_structure_origin_position",
            "current_structure_confirmation_position",
            "previous_same_type_price",
            "previous_same_type_origin_position",
            "same_type_log_price_change",
        )
        for column in missing_on_non_events:
            missing = df[column].isna().to_numpy()
            invalid = no_event_mask & ~missing
            if invalid.any():
                row = int(np.flatnonzero(invalid)[0])
                raise StructuralBreakDataError(
                    f"Non-event row {row} must have missing {column}."
                )

        # Keep extension-array scalar types intact: nullable Int64 positions
        # must not be coerced through float64 during validation.
        arrays = {column: df[column].array for column in numeric_metadata}
        seen_high = False
        seen_low = False
        last_high_price: Optional[float] = None
        last_high_origin: Optional[int] = None
        last_low_price: Optional[float] = None
        last_low_origin: Optional[int] = None

        for i in np.flatnonzero(event_mask):
            i = int(i)
            high_event = bool(high_flags[i])
            sequence_class = str(classes[i])

            swing_price = cls._required_finite_price(
                arrays["swing_price"][i], column="swing_price", row=i
            )
            swing_origin = cls._required_integer(
                arrays["swing_origin_position"][i],
                column="swing_origin_position",
                row=i,
                n=n,
            )
            swing_confirmation = cls._required_integer(
                arrays["swing_confirmation_position"][i],
                column="swing_confirmation_position",
                row=i,
                n=n,
            )
            if swing_confirmation != i or swing_origin > swing_confirmation:
                raise StructuralBreakDataError(
                    f"Module 2.1A positional metadata is invalid at row {i}."
                )

            current_price = cls._required_finite_price(
                arrays["current_structure_swing_price"][i],
                column="current_structure_swing_price",
                row=i,
            )
            current_origin = cls._required_integer(
                arrays["current_structure_origin_position"][i],
                column="current_structure_origin_position",
                row=i,
                n=n,
            )
            current_confirmation = cls._required_integer(
                arrays["current_structure_confirmation_position"][i],
                column="current_structure_confirmation_position",
                row=i,
                n=n,
            )
            if (
                current_price != swing_price
                or current_origin != swing_origin
                or current_confirmation != swing_confirmation
                or current_confirmation != i
            ):
                raise StructuralBreakDataError(
                    f"Module 2.1B current_structure metadata is inconsistent at row {i}."
                )

            had_previous = seen_high if high_event else seen_low
            expected_previous_price = last_high_price if high_event else last_low_price
            expected_previous_origin = last_high_origin if high_event else last_low_origin

            if not had_previous:
                if sequence_class != "UNCLASSIFIED" or comparison[i]:
                    raise StructuralBreakDataError(
                        f"First same-type event semantics are invalid at row {i}."
                    )
                for column in (
                    "previous_same_type_price",
                    "previous_same_type_origin_position",
                    "same_type_log_price_change",
                ):
                    cls._require_missing(arrays[column][i], column=column, row=i)
            else:
                if sequence_class == "UNCLASSIFIED" or not comparison[i]:
                    raise StructuralBreakDataError(
                        f"Comparable same-type event semantics are invalid at row {i}."
                    )
                previous_price = cls._required_finite_price(
                    arrays["previous_same_type_price"][i],
                    column="previous_same_type_price",
                    row=i,
                )
                previous_origin = cls._required_integer(
                    arrays["previous_same_type_origin_position"][i],
                    column="previous_same_type_origin_position",
                    row=i,
                    n=n,
                )
                if (
                    previous_price != expected_previous_price
                    or previous_origin != expected_previous_origin
                ):
                    raise StructuralBreakDataError(
                        f"Previous same-type metadata is inconsistent at row {i}."
                    )
                log_value = arrays["same_type_log_price_change"][i]
                if swing_price > 0.0 and previous_price > 0.0:
                    if pd.isna(log_value) or not math.isfinite(float(log_value)):
                        raise StructuralBreakDataError(
                            f"Positive comparable prices require finite log change at row {i}."
                        )
                else:
                    cls._require_missing(
                        log_value, column="same_type_log_price_change", row=i
                    )

            if high_event:
                seen_high = True
                last_high_price = swing_price
                last_high_origin = swing_origin
            else:
                seen_low = True
                last_low_price = swing_price
                last_low_origin = swing_origin

    @classmethod
    def _validate_input(cls, df: pd.DataFrame) -> None:
        cls._validate_ohlc_and_schema(df)
        cls._validate_upstream_surface(df)

    @staticmethod
    def _fraction(overshoot: float, level_price: float) -> float:
        if overshoot <= 0.0:
            return float("nan")
        denominator = abs(level_price)
        if denominator == 0.0:
            return float("nan")
        result = overshoot / denominator
        if not math.isfinite(result):
            raise StructuralBreakDataError("Break overshoot fraction overflowed.")
        return result

    @staticmethod
    def _state_from_classes(
        latest_high_class: Optional[str],
        latest_low_class: Optional[str],
    ) -> str:
        if latest_high_class is None or latest_low_class is None:
            return "UNDEFINED"
        if latest_high_class == "HH" and latest_low_class == "HL":
            return "UP_STRUCTURE"
        if latest_high_class == "LH" and latest_low_class == "LL":
            return "DOWN_STRUCTURE"
        return "MIXED"

    @staticmethod
    def _interpret_close_break(
        state_before: str,
        high_close_event: bool,
        low_close_event: bool,
    ) -> str:
        if high_close_event and low_close_event:
            return "AMBIGUOUS_DOUBLE_BREAK"
        if not high_close_event and not low_close_event:
            return "NONE"
        if state_before == "UP_STRUCTURE":
            return "BOS_UP" if high_close_event else "CHOCH_DOWN"
        if state_before == "DOWN_STRUCTURE":
            return "CHOCH_UP" if high_close_event else "BOS_DOWN"
        return "UNCLASSIFIED_BREAK"

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """Evaluate prior levels first, then process current confirmed events."""
        self._validate_input(df)

        n = len(df)
        high = df["high"].to_numpy(dtype=np.float64)
        low = df["low"].to_numpy(dtype=np.float64)
        close = df["close"].to_numpy(dtype=np.float64)
        high_confirmed = df["swing_high_confirmed"].to_numpy(dtype=bool)
        low_confirmed = df["swing_low_confirmed"].to_numpy(dtype=bool)

        high_price_out = np.full(n, np.nan)
        high_origin_out = pd.array([pd.NA] * n, dtype="Int64")
        high_confirmation_out = pd.array([pd.NA] * n, dtype="Int64")
        high_first_wick_out = pd.array([pd.NA] * n, dtype="Int64")
        high_first_close_out = pd.array([pd.NA] * n, dtype="Int64")
        high_wick_breached_out = np.zeros(n, dtype=bool)
        high_close_breached_out = np.zeros(n, dtype=bool)

        low_price_out = np.full(n, np.nan)
        low_origin_out = pd.array([pd.NA] * n, dtype="Int64")
        low_confirmation_out = pd.array([pd.NA] * n, dtype="Int64")
        low_first_wick_out = pd.array([pd.NA] * n, dtype="Int64")
        low_first_close_out = pd.array([pd.NA] * n, dtype="Int64")
        low_wick_breached_out = np.zeros(n, dtype=bool)
        low_close_breached_out = np.zeros(n, dtype=bool)

        high_wick_event = np.zeros(n, dtype=bool)
        high_close_event = np.zeros(n, dtype=bool)
        low_wick_event = np.zeros(n, dtype=bool)
        low_close_event = np.zeros(n, dtype=bool)
        high_wick_only = np.zeros(n, dtype=bool)
        low_wick_only = np.zeros(n, dtype=bool)

        high_wick_fraction = np.full(n, np.nan)
        high_close_fraction = np.full(n, np.nan)
        low_wick_fraction = np.full(n, np.nan)
        low_close_fraction = np.full(n, np.nan)
        high_wick_evidence = np.full(n, np.nan)
        high_close_evidence = np.full(n, np.nan)
        low_wick_evidence = np.full(n, np.nan)
        low_close_evidence = np.full(n, np.nan)
        wick_history_count = np.zeros(n, dtype=np.int64)
        close_history_count = np.zeros(n, dtype=np.int64)

        state_before_out = np.full(n, "UNDEFINED", dtype=object)
        state_after_out = np.full(n, "UNDEFINED", dtype=object)
        interpretation_out = np.full(n, "NONE", dtype=object)

        monitored_high: Optional[_LevelState] = None
        monitored_low: Optional[_LevelState] = None
        latest_high_class: Optional[str] = None
        latest_low_class: Optional[str] = None
        structure_state = "UNDEFINED"

        wick_tracker = CausalPercentileTracker(nan_policy="skip")
        close_tracker = CausalPercentileTracker(nan_policy="skip")

        for i in range(n):
            state_before_out[i] = structure_state
            wick_history_count[i] = wick_tracker.sample_count
            close_history_count[i] = close_tracker.sample_count

            current_wick_observations: list[float] = []
            current_close_observations: list[float] = []

            # Levels shown on row i are exactly the levels eligible for this
            # row's break evaluation. Newly confirmed levels are installed only
            # after all current-row break work is complete.
            if monitored_high is not None:
                level = monitored_high
                high_price_out[i] = level.price
                high_origin_out[i] = level.origin_position
                high_confirmation_out[i] = level.confirmation_position

                wick_geometry = high[i] > level.price
                close_geometry = close[i] > level.price

                if level.first_wick_breach_position is None and wick_geometry:
                    high_wick_event[i] = True
                    level.first_wick_breach_position = i
                    overshoot = high[i] - level.price
                    fraction = self._fraction(overshoot, level.price)
                    high_wick_fraction[i] = fraction
                    observation = wick_tracker.rank(fraction)
                    high_wick_evidence[i] = observation.percentile
                    if math.isfinite(fraction):
                        current_wick_observations.append(fraction)
                    if not close_geometry:
                        high_wick_only[i] = True

                if level.first_close_breach_position is None and close_geometry:
                    high_close_event[i] = True
                    level.first_close_breach_position = i
                    overshoot = close[i] - level.price
                    fraction = self._fraction(overshoot, level.price)
                    high_close_fraction[i] = fraction
                    observation = close_tracker.rank(fraction)
                    high_close_evidence[i] = observation.percentile
                    if math.isfinite(fraction):
                        current_close_observations.append(fraction)

                high_first_wick_out[i] = (
                    pd.NA
                    if level.first_wick_breach_position is None
                    else level.first_wick_breach_position
                )
                high_first_close_out[i] = (
                    pd.NA
                    if level.first_close_breach_position is None
                    else level.first_close_breach_position
                )
                high_wick_breached_out[i] = level.first_wick_breach_position is not None
                high_close_breached_out[i] = level.first_close_breach_position is not None

            if monitored_low is not None:
                level = monitored_low
                low_price_out[i] = level.price
                low_origin_out[i] = level.origin_position
                low_confirmation_out[i] = level.confirmation_position

                wick_geometry = low[i] < level.price
                close_geometry = close[i] < level.price

                if level.first_wick_breach_position is None and wick_geometry:
                    low_wick_event[i] = True
                    level.first_wick_breach_position = i
                    overshoot = level.price - low[i]
                    fraction = self._fraction(overshoot, level.price)
                    low_wick_fraction[i] = fraction
                    observation = wick_tracker.rank(fraction)
                    low_wick_evidence[i] = observation.percentile
                    if math.isfinite(fraction):
                        current_wick_observations.append(fraction)
                    if not close_geometry:
                        low_wick_only[i] = True

                if level.first_close_breach_position is None and close_geometry:
                    low_close_event[i] = True
                    level.first_close_breach_position = i
                    overshoot = level.price - close[i]
                    fraction = self._fraction(overshoot, level.price)
                    low_close_fraction[i] = fraction
                    observation = close_tracker.rank(fraction)
                    low_close_evidence[i] = observation.percentile
                    if math.isfinite(fraction):
                        current_close_observations.append(fraction)

                low_first_wick_out[i] = (
                    pd.NA
                    if level.first_wick_breach_position is None
                    else level.first_wick_breach_position
                )
                low_first_close_out[i] = (
                    pd.NA
                    if level.first_close_breach_position is None
                    else level.first_close_breach_position
                )
                low_wick_breached_out[i] = level.first_wick_breach_position is not None
                low_close_breached_out[i] = level.first_close_breach_position is not None

            interpretation_out[i] = self._interpret_close_break(
                structure_state,
                bool(high_close_event[i]),
                bool(low_close_event[i]),
            )

            # Every same-row first event read the same prior distribution.
            # Only now are finite magnitudes admitted for later rows.
            for value in current_wick_observations:
                wick_tracker.push(value)
            for value in current_close_observations:
                close_tracker.push(value)

            # Process sequence facts after break interpretation.
            event_type = str(df["structure_event_type"].iloc[i])
            sequence_class = str(df["swing_sequence_class"].iloc[i])
            if event_type == "HIGH":
                if sequence_class in ("HH", "LH", "EH"):
                    latest_high_class = sequence_class
            elif event_type == "LOW":
                if sequence_class in ("HL", "LL", "EL"):
                    latest_low_class = sequence_class

            structure_state = self._state_from_classes(
                latest_high_class, latest_low_class
            )

            # Install current confirmations only for subsequent rows.
            if high_confirmed[i]:
                monitored_high = _LevelState(
                    price=float(df["swing_price"].iloc[i]),
                    origin_position=int(df["swing_origin_position"].iloc[i]),
                    confirmation_position=i,
                )
            if low_confirmed[i]:
                monitored_low = _LevelState(
                    price=float(df["swing_price"].iloc[i]),
                    origin_position=int(df["swing_origin_position"].iloc[i]),
                    confirmation_position=i,
                )

            state_after_out[i] = structure_state

        out = df.copy(deep=True)
        out["monitored_high_price"] = high_price_out
        out["monitored_high_origin_position"] = high_origin_out
        out["monitored_high_confirmation_position"] = high_confirmation_out
        out["monitored_high_first_wick_breach_position"] = high_first_wick_out
        out["monitored_high_first_close_breach_position"] = high_first_close_out
        out["monitored_high_wick_breached"] = high_wick_breached_out
        out["monitored_high_close_breached"] = high_close_breached_out

        out["monitored_low_price"] = low_price_out
        out["monitored_low_origin_position"] = low_origin_out
        out["monitored_low_confirmation_position"] = low_confirmation_out
        out["monitored_low_first_wick_breach_position"] = low_first_wick_out
        out["monitored_low_first_close_breach_position"] = low_first_close_out
        out["monitored_low_wick_breached"] = low_wick_breached_out
        out["monitored_low_close_breached"] = low_close_breached_out

        out["high_wick_breach_event"] = high_wick_event
        out["high_close_breach_event"] = high_close_event
        out["low_wick_breach_event"] = low_wick_event
        out["low_close_breach_event"] = low_close_event
        out["high_wick_only_breach_event"] = high_wick_only
        out["low_wick_only_breach_event"] = low_wick_only

        out["high_wick_overshoot_fraction"] = high_wick_fraction
        out["high_close_overshoot_fraction"] = high_close_fraction
        out["low_wick_overshoot_fraction"] = low_wick_fraction
        out["low_close_overshoot_fraction"] = low_close_fraction
        out["high_wick_break_evidence"] = high_wick_evidence
        out["high_close_break_evidence"] = high_close_evidence
        out["low_wick_break_evidence"] = low_wick_evidence
        out["low_close_break_evidence"] = low_close_evidence
        out["wick_break_history_count"] = wick_history_count
        out["close_break_history_count"] = close_history_count

        out["structure_state_before"] = pd.array(state_before_out, dtype="string")
        out["structure_state_after"] = pd.array(state_after_out, dtype="string")
        out["structural_break_event"] = pd.array(interpretation_out, dtype="string")
        return out


class _StructuralBreakAuditEngine(CausalStructuralBreakEngine):
    """Named adapter used only for Module 0.1 reports."""


if __name__ == "__main__":
    # Exact upstream recomputation belongs to self-verification/tests only,
    # never the production analyze() hot path.
    from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine

    event_input = pd.DataFrame(
        {
            "swing_high_confirmed": [False, True, False, False],
            "swing_low_confirmed": [False, False, False, False],
            "swing_origin_position": pd.array(
                [pd.NA, 0, pd.NA, pd.NA], dtype="Int64"
            ),
            "swing_price": [np.nan, 100.0, np.nan, np.nan],
            "swing_confirmation_position": pd.array(
                [pd.NA, 1, pd.NA, pd.NA], dtype="Int64"
            ),
        }
    )
    upstream = ConfirmedSwingSequenceEngine().analyze(event_input)
    upstream.insert(0, "close", [95.0, 99.0, 100.0, 101.0])
    upstream.insert(0, "low", [90.0, 95.0, 98.0, 99.0])
    upstream.insert(0, "high", [99.0, 100.0, 101.0, 102.0])

    result = CausalStructuralBreakEngine().analyze(upstream)
    assert not result.loc[1, "high_wick_breach_event"]
    assert result.loc[2, "high_wick_breach_event"]
    assert not result.loc[2, "high_close_breach_event"]
    assert result.loc[3, "high_close_breach_event"]

    from trading_system.audit.causal_state import (
        ReentrancyPolicy,
        verify_state_isolation,
        verify_truncation_invariance,
    )

    second = upstream.copy(deep=True)
    second.loc[3, ["high", "low", "close"]] = [99.0, 90.0, 95.0]
    truncation = verify_truncation_invariance(
        _StructuralBreakAuditEngine,
        upstream,
        split_fractions=(),
        additional_split_points=[1, 2, 3],
    )
    assert truncation and all(item.passed for item in truncation)
    state = verify_state_isolation(
        _StructuralBreakAuditEngine,
        upstream,
        second,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed

    print("=" * 72)
    print("MODULE 2.1C V1.1 SELF-VERIFICATION PASSED")
    print("Prior eligible levels are evaluated before current swing events.")
    print("=" * 72)

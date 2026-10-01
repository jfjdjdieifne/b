"""
Layer 2 — Module 2.1B
Confirmed Swing Sequence Structure
VERSION 1

PURPOSE
-------
Interpret only newly confirmed swing events already visible in the audited
Module 2.1A DataFrame surface.

For each confirmed HIGH, compare its swing price with the previously confirmed
HIGH. For each confirmed LOW, compare with the previously confirmed LOW.
Candidate state is ignored completely.

CAUSAL TIMING
-------------
A classification is emitted only on the row carrying the current confirmation
event. The swing origin row is never backfilled. Comparison order is event
arrival/DataFrame row order, not origin-position order.

EXACT COMPARISON
----------------
HIGH: greater=HH, lower=LH, exactly equal=EH.
LOW:  greater=HL, lower=LL, exactly equal=EL.

No price tolerance, tick approximation, percentile, smoothing, score, or
persistent forward-filled label is produced.
"""

from __future__ import annotations

from numbers import Integral, Real
from typing import Final

import math
import numpy as np
import pandas as pd


class SwingSequenceError(Exception):
    """Base exception for Module 2.1B."""


class SwingSequenceDataError(SwingSequenceError):
    """Input schema, event metadata, index, or output-contract violation."""


_REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "swing_high_confirmed",
    "swing_low_confirmed",
    "swing_origin_position",
    "swing_price",
    "swing_confirmation_position",
)

_OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
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


class ConfirmedSwingSequenceEngine:
    """Stateless same-type confirmed-swing sequence classifier."""

    @staticmethod
    def _validate_input(df: pd.DataFrame) -> None:
        if not isinstance(df, pd.DataFrame):
            raise SwingSequenceDataError("df must be a pandas DataFrame.")

        if df.columns.has_duplicates:
            duplicates = df.columns[df.columns.duplicated()].tolist()
            raise SwingSequenceDataError(
                f"Duplicate input columns are forbidden: {duplicates!r}."
            )

        missing = [column for column in _REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise SwingSequenceDataError(
                f"Missing required Module 2.1A event columns: {missing!r}."
            )

        collisions = [column for column in _OUTPUT_COLUMNS if column in df.columns]
        if collisions:
            raise SwingSequenceDataError(
                f"Output columns already exist and would be overwritten: {collisions!r}."
            )

        if df.index.has_duplicates:
            raise SwingSequenceDataError("Duplicate index labels are forbidden.")

        try:
            ordered = bool(df.index.is_monotonic_increasing)
        except (TypeError, ValueError) as exc:
            raise SwingSequenceDataError(
                "Input index must have a well-defined increasing order."
            ) from exc

        if not ordered:
            raise SwingSequenceDataError(
                "Input index must already be monotonic increasing; silent sorting is forbidden."
            )

        for column in ("swing_high_confirmed", "swing_low_confirmed"):
            series = df[column]
            if not pd.api.types.is_bool_dtype(series.dtype):
                raise SwingSequenceDataError(f"Column {column!r} must be boolean.")
            if series.isna().any():
                raise SwingSequenceDataError(f"Column {column!r} contains missing flags.")

        for column in (
            "swing_origin_position",
            "swing_price",
            "swing_confirmation_position",
        ):
            series = df[column]
            if pd.api.types.is_bool_dtype(series.dtype) or not pd.api.types.is_numeric_dtype(
                series.dtype
            ):
                raise SwingSequenceDataError(
                    f"Column {column!r} must have a non-boolean numeric dtype."
                )

    @staticmethod
    def _event_integer(value: object, *, label: str, row_position: int) -> int:
        if pd.isna(value):
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} has missing {label}."
            )
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (Integral, np.integer)
        ):
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} has non-integer {label}: {value!r}."
            )
        return int(value)

    @staticmethod
    def _event_price(value: object, *, row_position: int) -> float:
        if pd.isna(value):
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} has missing swing_price."
            )
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (Real, np.integer, np.floating)
        ):
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} has invalid swing_price."
            )
        price = float(value)
        if not math.isfinite(price):
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} has non-finite swing_price."
            )
        return price

    @classmethod
    def _validated_event_metadata(
        cls,
        df: pd.DataFrame,
        row_position: int,
    ) -> tuple[float, int, int]:
        price = cls._event_price(
            df["swing_price"].iloc[row_position], row_position=row_position
        )
        origin = cls._event_integer(
            df["swing_origin_position"].iloc[row_position],
            label="swing_origin_position",
            row_position=row_position,
        )
        confirmation = cls._event_integer(
            df["swing_confirmation_position"].iloc[row_position],
            label="swing_confirmation_position",
            row_position=row_position,
        )

        n = len(df)
        if origin < 0 or origin >= n:
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} has out-of-range origin position {origin}."
            )
        if confirmation < 0 or confirmation >= n:
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} has out-of-range confirmation position "
                f"{confirmation}."
            )
        if confirmation != row_position:
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} declares confirmation position "
                f"{confirmation}; it must equal the current row position."
            )
        if origin > confirmation:
            raise SwingSequenceDataError(
                f"Confirmed event at row {row_position} has origin after confirmation."
            )

        return price, origin, confirmation

    @staticmethod
    def _classification(event_type: str, current: float, previous: float) -> str:
        if event_type == "HIGH":
            if current > previous:
                return "HH"
            if current < previous:
                return "LH"
            return "EH"

        if current > previous:
            return "HL"
        if current < previous:
            return "LL"
        return "EL"

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify same-type confirmed swing events without persistent state."""
        self._validate_input(df)

        n = len(df)
        high_flags = df["swing_high_confirmed"].to_numpy(dtype=bool)
        low_flags = df["swing_low_confirmed"].to_numpy(dtype=bool)

        event_type = np.full(n, "NONE", dtype=object)
        sequence_class = np.full(n, "NONE", dtype=object)
        comparison_available = np.zeros(n, dtype=bool)
        previous_price_output = np.full(n, np.nan, dtype=np.float64)
        previous_origin_output = np.full(n, np.nan, dtype=np.float64)
        current_price_output = np.full(n, np.nan, dtype=np.float64)
        current_origin_output = np.full(n, np.nan, dtype=np.float64)
        current_confirmation_output = np.full(n, np.nan, dtype=np.float64)
        log_change_output = np.full(n, np.nan, dtype=np.float64)

        previous_high_price: float | None = None
        previous_high_origin: int | None = None
        previous_low_price: float | None = None
        previous_low_origin: int | None = None

        for i in range(n):
            if high_flags[i] and low_flags[i]:
                raise SwingSequenceDataError(
                    f"Row {i} confirms HIGH and LOW simultaneously; upstream contract violated."
                )

            if not high_flags[i] and not low_flags[i]:
                continue

            current_price, current_origin, current_confirmation = (
                self._validated_event_metadata(df, i)
            )
            current_price_output[i] = current_price
            current_origin_output[i] = current_origin
            current_confirmation_output[i] = current_confirmation

            if high_flags[i]:
                current_type = "HIGH"
                previous_price = previous_high_price
                previous_origin = previous_high_origin
            else:
                current_type = "LOW"
                previous_price = previous_low_price
                previous_origin = previous_low_origin

            event_type[i] = current_type

            if previous_price is None:
                sequence_class[i] = "UNCLASSIFIED"
            else:
                comparison_available[i] = True
                previous_price_output[i] = previous_price
                previous_origin_output[i] = previous_origin
                sequence_class[i] = self._classification(
                    current_type, current_price, previous_price
                )
                if current_price > 0.0 and previous_price > 0.0:
                    log_change_output[i] = math.log(current_price) - math.log(
                        previous_price
                    )

            if current_type == "HIGH":
                previous_high_price = current_price
                previous_high_origin = current_origin
            else:
                previous_low_price = current_price
                previous_low_origin = current_origin

        out = df.copy(deep=True)
        out["structure_event_type"] = pd.array(event_type, dtype="string")
        out["swing_sequence_class"] = pd.array(sequence_class, dtype="string")
        out["comparison_available"] = comparison_available
        out["previous_same_type_price"] = previous_price_output
        out["previous_same_type_origin_position"] = pd.array(
            previous_origin_output, dtype="Int64"
        )
        out["current_structure_swing_price"] = current_price_output
        out["current_structure_origin_position"] = pd.array(
            current_origin_output, dtype="Int64"
        )
        out["current_structure_confirmation_position"] = pd.array(
            current_confirmation_output, dtype="Int64"
        )
        out["same_type_log_price_change"] = log_change_output
        return out


class _SwingSequenceAuditEngine(ConfirmedSwingSequenceEngine):
    """Named adapter used only for Module 0.1 reports."""


if __name__ == "__main__":
    frame = pd.DataFrame(
        {
            "swing_high_confirmed": [False, True, False, True],
            "swing_low_confirmed": [False, False, True, False],
            "swing_origin_position": pd.array([pd.NA, 0, 1, 2], dtype="Int64"),
            "swing_price": [np.nan, 100.0, 90.0, 110.0],
            "swing_confirmation_position": pd.array(
                [pd.NA, 1, 2, 3], dtype="Int64"
            ),
        }
    )
    result = ConfirmedSwingSequenceEngine().analyze(frame)
    assert result["swing_sequence_class"].tolist() == [
        "NONE",
        "UNCLASSIFIED",
        "UNCLASSIFIED",
        "HH",
    ]
    assert result.loc[3, "previous_same_type_price"] == 100.0

    from trading_system.audit.causal_state import (
        ReentrancyPolicy,
        verify_state_isolation,
        verify_truncation_invariance,
    )

    second = frame.copy(deep=True)
    second.loc[3, "swing_price"] = 80.0
    truncation = verify_truncation_invariance(
        _SwingSequenceAuditEngine,
        frame,
        split_fractions=(),
        additional_split_points=[1, 2, 3],
    )
    assert truncation and all(item.passed for item in truncation)
    state = verify_state_isolation(
        _SwingSequenceAuditEngine,
        frame,
        second,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed

    print("=" * 72)
    print("MODULE 2.1B V1 SELF-VERIFICATION PASSED")
    print("Confirmed swing sequence classes appear only on confirmation rows.")
    print("=" * 72)

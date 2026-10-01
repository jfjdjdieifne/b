"""
Layer 1 — Module 1.1
Dynamic Volatility Engine
VERSION 1.1 — Rebuilt From Scratch

PURPOSE
-------
Produce a causal, continuous description of realized bar-range volatility.
This engine does not predict volatility, choose trades, label regimes, select
an optimal lookback, or emit an adaptive period.

The engine separates:

1. Raw movement:
       true_range
2. Dimensionless instantaneous volatility:
       normalized_true_range
3. Relative historical context:
       true_range_percentile, ranked against PRIOR finite observations only
4. Volatility dynamics:
       normalized_tr_change, the signed log-ratio of consecutive positive
       normalized true ranges
5. Expansion/contraction context:
       expansion_percentile, ranked against PRIOR finite changes only
6. Evidence:
       raw history counts for both empirical distributions

CAUSAL TIMING
-------------
At completed bar i, true range may use high_i, low_i, and close_(i-1).
The first bar uses high_i-low_i. No output accesses row i+1 or later.

NORMALIZATION
-------------
For i>0 with a finite, nonzero previous close:

    normalized_true_range_i = true_range_i / abs(close_(i-1))

The first bar is NaN because no causal reference price exists. No global
price statistic or future price is used.

DYNAMICS
--------
When consecutive normalized true ranges are both positive and finite:

    normalized_tr_change_i = log(ntr_i / ntr_(i-1))

The implementation evaluates this as log(ntr_i)-log(ntr_(i-1)), which is
mathematically identical but avoids avoidable intermediate ratio overflow or
underflow. If either immediate value is zero or undefined, the change is NaN.
The engine never bridges across a missing/zero bar by recalling an older
finite normalized range. No epsilon is fabricated.

PERCENTILE ORDER
----------------
Both contexts use Module 0.2's atomic observe(): score against prior history,
then push the current finite observation. No bootstrap value, readiness flag,
or fixed history horizon is introduced.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import pandas as pd

from trading_system.core.causal_percentile import CausalPercentileTracker


class DynamicVolatilityError(Exception):
    """Base exception for Module 1.1."""


class DynamicVolatilityDataError(DynamicVolatilityError):
    """Input or derived-data contract violation."""


OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
    "true_range",
    "normalized_true_range",
    "true_range_percentile",
    "true_range_history_count",
    "normalized_tr_change",
    "expansion_percentile",
    "expansion_history_count",
)


class DynamicVolatilityEngine:
    """Deterministic, idempotent batch volatility-description engine.

    Every call creates fresh local percentile trackers. The instance keeps no
    analytical state, so repeated calls cannot contaminate one another.
    """

    @staticmethod
    def _validate_input(
        df: pd.DataFrame,
        *,
        high_col: str,
        low_col: str,
        close_col: str,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise DynamicVolatilityDataError("df must be a pandas DataFrame.")

        if df.columns.has_duplicates:
            duplicates = df.columns[df.columns.duplicated()].tolist()
            raise DynamicVolatilityDataError(
                f"Duplicate column labels are forbidden: {duplicates!r}."
            )

        required = (high_col, low_col, close_col)
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise DynamicVolatilityDataError(
                f"Missing required OHLC columns: {missing!r}."
            )

        collisions = [column for column in OUTPUT_COLUMNS if column in df.columns]
        if collisions:
            raise DynamicVolatilityDataError(
                f"Output columns already exist and would be overwritten: {collisions!r}."
            )

        if df.index.has_duplicates:
            raise DynamicVolatilityDataError("Duplicate index labels are forbidden.")

        try:
            ordered = bool(df.index.is_monotonic_increasing)
        except (TypeError, ValueError) as exc:
            raise DynamicVolatilityDataError(
                "Input index must have a well-defined increasing order."
            ) from exc

        if not ordered:
            raise DynamicVolatilityDataError(
                "Input index must already be monotonic increasing; silent sorting is forbidden."
            )

        for column in required:
            series = df[column]
            dtype = series.dtype

            if pd.api.types.is_bool_dtype(dtype):
                raise DynamicVolatilityDataError(
                    f"Column {column!r} must be real numeric, not boolean."
                )

            if pd.api.types.is_complex_dtype(dtype):
                raise DynamicVolatilityDataError(
                    f"Column {column!r} must be real numeric, not complex."
                )

            if not pd.api.types.is_numeric_dtype(dtype):
                raise DynamicVolatilityDataError(
                    f"Column {column!r} must have a numeric dtype. Got {dtype}."
                )

            try:
                values = series.to_numpy(dtype=np.float64, na_value=np.nan)
            except (TypeError, ValueError, OverflowError) as exc:
                raise DynamicVolatilityDataError(
                    f"Column {column!r} cannot be represented as finite float64 values."
                ) from exc

            if not np.isfinite(values).all():
                raise DynamicVolatilityDataError(
                    f"Column {column!r} contains NaN or infinity."
                )

        high = df[high_col].to_numpy(dtype=np.float64)
        low = df[low_col].to_numpy(dtype=np.float64)
        if np.any(high < low):
            first_position = int(np.flatnonzero(high < low)[0])
            raise DynamicVolatilityDataError(
                f"high < low at position {first_position}."
            )

    @staticmethod
    def _compute_true_range_and_normalized(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        n = len(high)
        true_range = np.empty(n, dtype=np.float64)
        normalized = np.full(n, np.nan, dtype=np.float64)

        for i in range(n):
            bar_range = float(high[i]) - float(low[i])

            if i == 0:
                tr = bar_range
            else:
                previous_close = float(close[i - 1])
                tr = max(
                    bar_range,
                    abs(float(high[i]) - previous_close),
                    abs(float(low[i]) - previous_close),
                )

            if not math.isfinite(tr):
                raise DynamicVolatilityDataError(
                    f"True Range overflowed at position {i}."
                )

            true_range[i] = tr

            if i > 0:
                denominator = abs(float(close[i - 1]))
                if denominator > 0.0:
                    normalized_value = tr / denominator
                    if not math.isfinite(normalized_value):
                        raise DynamicVolatilityDataError(
                            f"Normalized True Range overflowed at position {i}."
                        )
                    normalized[i] = normalized_value

        return true_range, normalized

    @staticmethod
    def _compute_log_changes(normalized: np.ndarray) -> np.ndarray:
        changes = np.full(len(normalized), np.nan, dtype=np.float64)

        for i in range(1, len(normalized)):
            previous = float(normalized[i - 1])
            current = float(normalized[i])

            if (
                math.isfinite(previous)
                and math.isfinite(current)
                and previous > 0.0
                and current > 0.0
            ):
                changes[i] = math.log(current) - math.log(previous)

        return changes

    @staticmethod
    def _causal_context(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        tracker = CausalPercentileTracker(nan_policy="skip")
        percentiles = np.full(len(values), np.nan, dtype=np.float64)
        history_counts = np.zeros(len(values), dtype=np.int64)

        for i, value in enumerate(values):
            observation = tracker.observe(float(value))
            percentiles[i] = observation.percentile
            history_counts[i] = observation.sample_count

        return percentiles, history_counts

    def analyze(
        self,
        df: pd.DataFrame,
        *,
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
    ) -> pd.DataFrame:
        """Return a new DataFrame; never mutate or reorder the caller input."""

        self._validate_input(
            df,
            high_col=high_col,
            low_col=low_col,
            close_col=close_col,
        )

        high = df[high_col].to_numpy(dtype=np.float64)
        low = df[low_col].to_numpy(dtype=np.float64)
        close = df[close_col].to_numpy(dtype=np.float64)

        true_range, normalized = self._compute_true_range_and_normalized(
            high, low, close
        )
        changes = self._compute_log_changes(normalized)

        true_range_percentile, true_range_count = self._causal_context(normalized)
        expansion_percentile, expansion_count = self._causal_context(changes)

        out = df.copy(deep=True)
        out["true_range"] = true_range
        out["normalized_true_range"] = normalized
        out["true_range_percentile"] = true_range_percentile
        out["true_range_history_count"] = true_range_count
        out["normalized_tr_change"] = changes
        out["expansion_percentile"] = expansion_percentile
        out["expansion_history_count"] = expansion_count
        return out


class _DynamicVolatilityAuditEngine(DynamicVolatilityEngine):
    """No-op subclass name used to make Module 0.1 test reports explicit."""

    def analyze(self, df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
        return super().analyze(df, **kwargs)


if __name__ == "__main__":
    # Hand-calculated gap-up and gap-down True Range examples.
    sample = pd.DataFrame(
        {
            "high": [10.0, 15.0, 8.0],
            "low": [8.0, 12.0, 6.0],
            "close": [9.0, 14.0, 7.0],
        }
    )
    output = DynamicVolatilityEngine().analyze(sample)
    np.testing.assert_array_equal(output["true_range"].to_numpy(), [2.0, 6.0, 8.0])
    assert math.isnan(output.loc[0, "normalized_true_range"])
    assert output.loc[1, "normalized_true_range"] == 6.0 / 9.0
    assert output.loc[2, "normalized_true_range"] == 8.0 / 14.0
    assert math.isnan(output.loc[1, "normalized_tr_change"])
    expected_change = math.log(8.0 / 14.0) - math.log(6.0 / 9.0)
    assert output.loc[2, "normalized_tr_change"] == expected_change

    # Immediate-bar contract: finite -> NaN -> finite must not bridge.
    no_bridge = DynamicVolatilityEngine._compute_log_changes(
        np.array([0.01, np.nan, 0.04], dtype=np.float64)
    )
    assert math.isnan(no_bridge[1])
    assert math.isnan(no_bridge[2])

    # Real Module 0.1 imports; no compatibility shim.
    from trading_system.audit.causal_state import (
        ReentrancyPolicy,
        verify_state_isolation,
        verify_truncation_invariance,
    )

    rng = np.random.default_rng(1_101)
    n = 401
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.5, size=n))
    high = close + rng.uniform(0.0, 1.0, size=n)
    low = close - rng.uniform(0.0, 1.0, size=n)
    audit_a = pd.DataFrame({"high": high, "low": low, "close": close})

    close_b = 200.0 + np.cumsum(rng.normal(0.0, 0.8, size=n + 7))
    audit_b = pd.DataFrame(
        {
            "high": close_b + rng.uniform(0.0, 1.5, size=n + 7),
            "low": close_b - rng.uniform(0.0, 1.5, size=n + 7),
            "close": close_b,
        }
    )

    truncation = verify_truncation_invariance(
        _DynamicVolatilityAuditEngine,
        audit_a,
        additional_split_points=[1, 2, 3, 17, 127, 256, 400],
    )
    assert truncation and all(result.passed for result in truncation)

    state = verify_state_isolation(
        _DynamicVolatilityAuditEngine,
        audit_a,
        audit_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed

    print("=" * 72)
    print("MODULE 1.1 V1.1 SELF-VERIFICATION PASSED")
    print("True-range and expansion contexts use prior observations only.")
    print("=" * 72)

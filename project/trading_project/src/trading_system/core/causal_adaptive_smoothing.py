"""
Layer 0 — Module 0.3
Causal Adaptive Smoothing / Memory Kernel
VERSION 1.1

PURPOSE
-------
A strictly causal exponential smoothing primitive whose memory/period is
supplied externally for every observation.

This module answers only:

    "Given a causally available period p_i, how is x_i smoothed?"

It deliberately does NOT answer:

    "What should p_i be?"

Adaptive-period generation belongs to a separate audited component. This
module contains no ATR logic, volatility thresholds, percentile thresholds,
bootstrap guesses, optimization logic, or default trading periods.

CAUSAL RECURRENCE
-----------------
At bar i, using only the current value, current externally supplied period,
and previous EMA state:

    alpha_i = 2 / (p_i + 1)

    ema_i = x_i                                      if uninitialized
    ema_i = ema_(i-1) + alpha_i * (x_i - ema_(i-1)) otherwise

The constants 2 and 1 are part of the mathematical definition of the
standard EMA smoothing factor. They are not strategic thresholds.

NAN POLICY
----------
NaN policy applies to VALUES only:

    "hold":
        Do not update state. Return accepted=False and alpha=NaN. If EMA
        state already exists, expose that current EMA as the output for the
        missing bar; before initialization, output remains NaN. This makes
        the kernel represent memory state continuously. A consumer that
        needs missingness propagation may apply it explicitly downstream.

    "raise":
        Reject the NaN value.

The supplied period is validated even for a held NaN value. Periods never
permit NaN: every supplied period must be finite and >= 1. The lower bound
is mathematical, not strategic: with alpha=2/(p+1), p>=1 guarantees
0 < alpha <= 1, so every finite update is a convex combination of previous
EMA and current value and cannot overshoot either endpoint.

Positive infinity and negative infinity are always rejected for both values
and periods.

INDEX CONTRACT
--------------
The Series API requires identical, unique pandas indexes. It never aligns,
reindexes, sorts, or otherwise changes caller data silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Literal, Optional

import math
import numpy as np
import pandas as pd


# ============================================================================
# Exceptions
# ============================================================================

class CausalSmoothingError(Exception):
    """Base exception for Module 0.3."""


class CausalSmoothingConfigError(CausalSmoothingError):
    """Invalid smoother configuration."""


class CausalSmoothingDataError(CausalSmoothingError):
    """Invalid value, period, Series, dtype, or index contract."""


# ============================================================================
# Result object
# ============================================================================

@dataclass(frozen=True)
class SmoothingObservation:
    """Immutable result of one causal update.

    `previous_ema` is NaN when no finite value had previously initialized the
    smoother. For held NaN values, `alpha` is NaN and `accepted` is False;
    `ema` and `previous_ema` expose the current state when initialized, or NaN
    before the first finite seed. Internal state remains unchanged.
    """

    value: float
    period: float
    alpha: float
    previous_ema: float
    ema: float
    accepted: bool
    initialized_before: bool


# ============================================================================
# Streaming smoother
# ============================================================================

class CausalAdaptiveEMA:
    """Streaming causal EMA with an externally supplied per-observation period.

    Parameters
    ----------
    nan_policy:
        "hold" leaves state unchanged for a NaN value, exposes the current
        EMA state, and returns accepted=False. "raise" treats a NaN value
        as a data error.

    Notes
    -----
    There is intentionally no period default and no period-selection logic.
    The caller is responsible for ensuring p_i was generated causally.
    """

    def __init__(
        self,
        *,
        nan_policy: Literal["hold", "raise"] = "hold",
    ) -> None:
        if nan_policy not in ("hold", "raise"):
            raise CausalSmoothingConfigError(
                "nan_policy must be 'hold' or 'raise'."
            )

        self._nan_policy = nan_policy
        self._ema: Optional[float] = None
        self._total_accepted = 0
        self._total_held = 0

    @property
    def nan_policy(self) -> Literal["hold", "raise"]:
        return self._nan_policy

    @property
    def is_initialized(self) -> bool:
        return self._ema is not None

    @property
    def current_ema(self) -> float:
        """Current state, or NaN before the first accepted finite value."""
        return float("nan") if self._ema is None else self._ema

    @property
    def total_accepted(self) -> int:
        return self._total_accepted

    @property
    def total_held(self) -> int:
        """Number of NaN values held without mutating EMA state."""
        return self._total_held

    @staticmethod
    def _is_scalar_missing(value: object) -> bool:
        try:
            missing = pd.isna(value)
        except (TypeError, ValueError):
            return False
        return isinstance(missing, (bool, np.bool_)) and bool(missing)

    @classmethod
    def _coerce_value(cls, value: object) -> float:
        if isinstance(value, (bool, np.bool_)):
            raise CausalSmoothingDataError(
                "Boolean values are not valid numerical market features."
            )

        if cls._is_scalar_missing(value):
            return float("nan")

        if not isinstance(value, (Real, np.integer, np.floating)):
            raise CausalSmoothingDataError(
                f"value must be a scalar real number. Got {value!r}."
            )

        result = float(value)

        if math.isinf(result):
            raise CausalSmoothingDataError(
                "Infinite values are rejected. Fix the upstream feature calculation."
            )

        return result

    @classmethod
    def _coerce_period(cls, period: object) -> float:
        if isinstance(period, (bool, np.bool_)):
            raise CausalSmoothingDataError(
                "period must be a finite real number >= 1; booleans are rejected."
            )

        if cls._is_scalar_missing(period):
            raise CausalSmoothingDataError("period must be finite; NaN is rejected.")

        if not isinstance(period, (Real, np.integer, np.floating)):
            raise CausalSmoothingDataError(
                f"period must be a scalar real number >= 1. Got {period!r}."
            )

        result = float(period)

        if not math.isfinite(result):
            raise CausalSmoothingDataError("period must be finite.")

        if result < 1.0:
            raise CausalSmoothingDataError(
                f"period must be >= 1. Got {result}."
            )

        return result

    def update(
        self,
        value: object,
        period: object,
    ) -> SmoothingObservation:
        """Consume one `(value, period)` pair without accessing future data."""

        # Period is validated even when the value is held. This prevents a
        # missing value from silently concealing an invalid period stream.
        p = self._coerce_period(period)
        x = self._coerce_value(value)

        if math.isnan(x):
            if self._nan_policy == "raise":
                raise CausalSmoothingDataError(
                    "NaN value encountered with nan_policy='raise'."
                )

            initialized_before = self.is_initialized
            held_ema = self.current_ema
            self._total_held += 1
            return SmoothingObservation(
                value=float("nan"),
                period=p,
                alpha=float("nan"),
                previous_ema=held_ema,
                ema=held_ema,
                accepted=False,
                initialized_before=initialized_before,
            )

        alpha = 2.0 / (p + 1.0)
        initialized_before = self.is_initialized

        if self._ema is None:
            previous_ema = float("nan")
            new_ema = x
        else:
            previous_ema = self._ema
            new_ema = previous_ema + alpha * (x - previous_ema)

        self._ema = float(new_ema)
        self._total_accepted += 1

        return SmoothingObservation(
            value=x,
            period=p,
            alpha=float(alpha),
            previous_ema=float(previous_ema),
            ema=self._ema,
            accepted=True,
            initialized_before=initialized_before,
        )

    def reset(self) -> None:
        """Erase EMA state and all accounting counters."""
        self._ema = None
        self._total_accepted = 0
        self._total_held = 0


# ============================================================================
# Series API
# ============================================================================

def _validate_series_contract(values: pd.Series, periods: pd.Series) -> None:
    if not isinstance(values, pd.Series):
        raise CausalSmoothingDataError("values must be a pandas Series.")

    if not isinstance(periods, pd.Series):
        raise CausalSmoothingDataError("periods must be a pandas Series.")

    if not values.index.equals(periods.index):
        raise CausalSmoothingDataError(
            "values and periods must have identical indexes; silent alignment is forbidden."
        )

    if values.index.has_duplicates:
        raise CausalSmoothingDataError(
            "Duplicate index labels are rejected because they make the bar contract ambiguous."
        )

    if pd.api.types.is_bool_dtype(values.dtype):
        raise CausalSmoothingDataError("Boolean values dtype is not supported.")

    if pd.api.types.is_bool_dtype(periods.dtype):
        raise CausalSmoothingDataError("Boolean periods dtype is not supported.")

    if not pd.api.types.is_numeric_dtype(values.dtype):
        raise CausalSmoothingDataError(
            f"values must have a numeric dtype. Got {values.dtype}."
        )

    if not pd.api.types.is_numeric_dtype(periods.dtype):
        raise CausalSmoothingDataError(
            f"periods must have a numeric dtype. Got {periods.dtype}."
        )


def causal_adaptive_ema_series(
    values: pd.Series,
    periods: pd.Series,
    *,
    nan_policy: Literal["hold", "raise"] = "hold",
) -> pd.DataFrame:
    """Sequentially apply :class:`CausalAdaptiveEMA` without alignment.

    Output columns
    --------------
    ema:
        Smoothed memory state. For a held NaN input, this is the previous EMA
        when initialized, otherwise NaN before the first finite seed.
    alpha:
        Per-bar EMA alpha. NaN for a held NaN input.
    accepted:
        Whether the value entered smoother state.
    initialized_before:
        Whether finite EMA state existed before processing the current bar.
    """

    _validate_series_contract(values, periods)

    smoother = CausalAdaptiveEMA(nan_policy=nan_policy)
    n = len(values)

    ema_output = np.full(n, np.nan, dtype=np.float64)
    alpha_output = np.full(n, np.nan, dtype=np.float64)
    accepted_output = np.zeros(n, dtype=bool)
    initialized_output = np.zeros(n, dtype=bool)

    raw_values = values.to_numpy()
    raw_periods = periods.to_numpy()

    for i in range(n):
        result = smoother.update(raw_values[i], raw_periods[i])
        ema_output[i] = result.ema
        alpha_output[i] = result.alpha
        accepted_output[i] = result.accepted
        initialized_output[i] = result.initialized_before

    return pd.DataFrame(
        {
            "ema": ema_output,
            "alpha": alpha_output,
            "accepted": accepted_output,
            "initialized_before": initialized_output,
        },
        index=values.index,
    )


# ============================================================================
# Module 0.1 audit adapter
# ============================================================================

class _AdaptiveEMAAuditEngine:
    """Stateless DataFrame adapter used only for Module 0.1 certification."""

    def __init__(
        self,
        *,
        value_column: str,
        period_column: str,
        nan_policy: Literal["hold", "raise"] = "hold",
    ) -> None:
        self._value_column = value_column
        self._period_column = period_column
        self._nan_policy = nan_policy

    def analyze(self, df: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
        missing = [
            column
            for column in (self._value_column, self._period_column)
            if column not in df.columns
        ]
        if missing:
            raise CausalSmoothingDataError(f"Missing source columns: {missing}.")

        features = causal_adaptive_ema_series(
            df[self._value_column],
            df[self._period_column],
            nan_policy=self._nan_policy,
        )

        out = df.copy()
        out["causal_adaptive_ema"] = features["ema"]
        out["causal_adaptive_ema_alpha"] = features["alpha"]
        out["causal_adaptive_ema_accepted"] = features["accepted"]
        out["causal_adaptive_ema_initialized_before"] = features[
            "initialized_before"
        ]
        return out


# ============================================================================
# Self-verification
# ============================================================================

if __name__ == "__main__":
    # Hand-calculated constant-period recurrence (p=3 => alpha=0.5).
    constant = CausalAdaptiveEMA()
    c0 = constant.update(10.0, 3.0)
    c1 = constant.update(14.0, 3.0)
    c2 = constant.update(18.0, 3.0)
    assert c0.ema == 10.0
    assert c1.ema == 12.0
    assert c2.ema == 15.0

    # Changing periods: p=1 => alpha=1, then p=3 => alpha=0.5.
    changing = CausalAdaptiveEMA()
    assert changing.update(5.0, 8.0).ema == 5.0  # natural first seed
    assert changing.update(9.0, 1.0).ema == 9.0
    assert changing.update(13.0, 3.0).ema == 11.0

    # Reset semantics.
    changing.reset()
    assert not changing.is_initialized
    assert math.isnan(changing.current_ema)
    assert changing.total_accepted == 0
    assert changing.total_held == 0
    assert changing.update(100.0, 2.0).ema == 100.0

    # NaN hold leaves state unchanged; next recurrence uses prior finite EMA.
    skipping = CausalAdaptiveEMA(nan_policy="hold")
    skipping.update(10.0, 3.0)
    held = skipping.update(float("nan"), 7.0)
    assert not held.accepted
    assert held.ema == 10.0
    assert skipping.current_ema == 10.0
    assert skipping.total_held == 1
    assert skipping.update(14.0, 3.0).ema == 12.0

    # Leading NaNs never fabricate state; first finite value is the seed.
    leading_missing = CausalAdaptiveEMA(nan_policy="hold")
    lead_0 = leading_missing.update(float("nan"), 3.0)
    lead_1 = leading_missing.update(float("nan"), 8.5)
    assert math.isnan(lead_0.ema) and math.isnan(lead_1.ema)
    assert not leading_missing.is_initialized
    first_finite = leading_missing.update(100.0, 27.25)
    assert first_finite.ema == 100.0
    assert not first_finite.initialized_before

    # Mathematical domain properties for fractional p >= 1.
    property_rng = np.random.default_rng(1_103)
    property_smoother = CausalAdaptiveEMA()
    for value, period in zip(
        property_rng.normal(size=2_000),
        property_rng.uniform(1.0, 1_000_000.0, size=2_000),
    ):
        observation = property_smoother.update(value, period)
        assert 0.0 < observation.alpha <= 1.0
        if observation.initialized_before:
            assert min(observation.previous_ema, observation.value) <= observation.ema
            assert observation.ema <= max(observation.previous_ema, observation.value)

    # Streaming and Series APIs must be exact.
    values = pd.Series([10.0, 14.0, np.nan, 18.0], index=[10, 20, 30, 40])
    periods = pd.Series([3.0, 3.0, 9.0, 1.0], index=values.index)
    series_result = causal_adaptive_ema_series(values, periods)

    stream = CausalAdaptiveEMA()
    stream_results = [
        stream.update(value, period)
        for value, period in zip(values.to_numpy(), periods.to_numpy())
    ]
    expected = pd.DataFrame(
        {
            "ema": [result.ema for result in stream_results],
            "alpha": [result.alpha for result in stream_results],
            "accepted": [result.accepted for result in stream_results],
            "initialized_before": [
                result.initialized_before for result in stream_results
            ],
        },
        index=values.index,
    )
    pd.testing.assert_frame_equal(series_result, expected, check_exact=True)

    # Manual truncation invariance and independent future mutations.
    rng = np.random.default_rng(303)
    n = 257
    audit_values = pd.Series(rng.normal(size=n), name="value")
    audit_periods = pd.Series(rng.uniform(1.0, 40.0, size=n), name="period")
    full = causal_adaptive_ema_series(audit_values, audit_periods)

    for split_at in (1, 2, 17, 63, 128, 256):
        truncated = causal_adaptive_ema_series(
            audit_values.iloc[:split_at], audit_periods.iloc[:split_at]
        )
        pd.testing.assert_frame_equal(full.iloc[:split_at], truncated, check_exact=True)

    split_at = 128
    future_values = audit_values.copy()
    future_values.iloc[split_at:] = future_values.iloc[split_at:] * 1_000_000.0
    value_mutated = causal_adaptive_ema_series(future_values, audit_periods)
    pd.testing.assert_frame_equal(
        full.iloc[:split_at], value_mutated.iloc[:split_at], check_exact=True
    )

    future_periods = audit_periods.copy()
    future_periods.iloc[split_at:] = future_periods.iloc[split_at:] + 1_000_000.0
    period_mutated = causal_adaptive_ema_series(audit_values, future_periods)
    pd.testing.assert_frame_equal(
        full.iloc[:split_at], period_mutated.iloc[:split_at], check_exact=True
    )

    # Real Module 0.1 import; compatibility shim is intentionally not used.
    from trading_system.audit.causal_state import (
        ReentrancyPolicy,
        verify_state_isolation,
        verify_truncation_invariance,
    )

    audit_df = pd.DataFrame({"value": audit_values, "period": audit_periods})
    factory = lambda: _AdaptiveEMAAuditEngine(
        value_column="value", period_column="period"
    )

    truncation_results = verify_truncation_invariance(
        factory,
        audit_df,
        additional_split_points=[1, 2, 17, 63, 128, 256],
    )
    assert truncation_results and all(result.passed for result in truncation_results)

    second_df = pd.DataFrame(
        {
            "value": rng.normal(size=n + 3),
            "period": rng.uniform(1.0, 20.0, size=n + 3),
        }
    )
    state_result = verify_state_isolation(
        factory,
        audit_df,
        second_df,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state_result.passed

    print("=" * 72)
    print("MODULE 0.3 V1.1 SELF-VERIFICATION PASSED")
    print("Adaptive EMA consumes external causal periods and is truncation invariant.")
    print("=" * 72)

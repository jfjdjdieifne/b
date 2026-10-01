"""
Layer 2 — Module 2.1A
Causal Adaptive Swing Detector
VERSION 1.1 — Rebuilt From Scratch

SCOPE
-----
This module tracks one alternating wick-extreme candidate, describes its
continuous adverse-reversal evidence, and optionally delegates binary
confirmation to an explicit injected policy.

It does NOT classify HH/HL/LH/LL, detect BOS/CHoCH, infer liquidity, create
zones, or produce trading signals.

CAUSAL EVENT TIMING
-------------------
A candidate has an origin position where its current extreme occurred. A
confirmed swing becomes visible only on the later confirmation row. No origin
row is backfilled. Candidate snapshots may change on later rows while
unconfirmed; previously emitted rows are never mutated.

PRICE AND SAME-BAR SEMANTICS
----------------------------
Candidates and reversals are wick-based:

    HIGH reversal distance = candidate_high - low_i
    LOW  reversal distance = high_i - candidate_low

Strictly higher highs and strictly lower lows replace candidates. Exact equal
extrema retain the earlier origin; no epsilon is used.

If a bar creates a strict new extreme, that entire bar is excluded from
reversal confirmation for the replaced and newly updated candidate. OHLC does
not reveal whether its high occurred before its low, so an outside bar cannot
both update an extreme and confirm a reversal that depends on intrabar order.
Confirmation requires a subsequent completed bar without a strict extension.

CANDIDATE-SIDE INITIALIZATION
-----------------------------
The first bar initializes undecided high/low boundaries. The first later bar
that strictly extends only one boundary selects candidate_side HIGH or LOW. A
bar extending both boundaries keeps candidate_side UNDECIDED and confirms
nothing. HIGH/LOW here identifies only which extreme candidate is tracked; it
is not trend, market direction, or structure classification. Once a swing
confirms, candidate side alternates and the opposite candidate starts from the
confirmation bar's opposite wick.

REVERSAL NORMALIZATION
----------------------
Reversal is price-relative and dimensionless:

    HIGH fraction = (candidate_high - low_i) / abs(candidate_high)
    LOW  fraction = (high_i - candidate_low) / abs(candidate_low)

A zero candidate denominator yields NaN; no epsilon is fabricated.

EMPIRICAL HISTORY OBSERVATION
-----------------------------
History is split by episode outcome:

continuation_reversal_history:
    One maximum finite reversal fraction from an episode replaced by a strict
    same-side extreme. This is the only baseline used for confirmation evidence
    and threshold calibration.

confirmed_reversal_history:
    One maximum finite reversal fraction from a confirmed swing episode. This
    is diagnostic only and never recalibrates the V1.1 confirmation threshold.

A replacement bar never contributes its opposite wick to the old or new
episode. An episode with no unambiguous finite reversal observation contributes
nothing. Evolving per-bar reversal values are ranked but are NOT pushed, so a
long-lived candidate is not overweighted. All policy reads occur before the
current episode is recorded in its outcome-specific history.

BOOTSTRAP REALITY
-----------------
Evidence-only mode is the default and never confirms. It still accumulates
finalized replacement episodes and exposes causal empirical evidence/counts.

EmpiricalConfirmationPolicy requires an explicit quantile and has no default.
With empty continuation reference history its threshold is NaN and it cannot
confirm. A caller may explicitly supply prior continuation/failed episode
reversals obtained under the same semantics. Those priors are an external
modeling assumption; this module does not claim a self-starting optimal swing
definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Final, Optional, Protocol, runtime_checkable

import math
import numpy as np
import pandas as pd

from trading_system.core.causal_percentile import CausalPercentileTracker


class SwingDetectorError(Exception):
    """Base exception for Module 2.1A."""


class SwingConfigError(SwingDetectorError):
    """Invalid confirmation-policy configuration."""


class SwingDataError(SwingDetectorError):
    """Invalid input DataFrame, index, columns, or OHLC values."""


@dataclass(frozen=True)
class ConfirmationAssessment:
    """Decision based only on continuation episodes available before this bar."""

    confirmed: bool
    reversal_evidence: float
    continuation_history_count: int
    threshold: float


@dataclass(frozen=True)
class ConfirmedEpisodeDiagnostic:
    """Current confirmed episode ranked against prior confirmed episodes only."""

    percentile: float
    prior_confirmed_history_count: int


@runtime_checkable
class SwingConfirmationRuntime(Protocol):
    @property
    def continuation_history_count(self) -> int: ...

    @property
    def confirmed_history_count(self) -> int: ...

    def assess(self, reversal_fraction: float) -> ConfirmationAssessment: ...

    def finalize_continuation_episode(
        self, maximum_reversal_fraction: Optional[float]
    ) -> bool: ...

    def record_confirmed_episode(
        self, maximum_reversal_fraction: Optional[float]
    ) -> ConfirmedEpisodeDiagnostic: ...


@runtime_checkable
class SwingConfirmationPolicy(Protocol):
    """Immutable/factory-style policy contract; each batch receives fresh runtime."""

    def create_runtime(self) -> SwingConfirmationRuntime: ...


class _EmpiricalRuntime:
    def __init__(
        self,
        quantile: Optional[float],
        continuation_priors: tuple[float, ...],
        confirmed_priors: tuple[float, ...],
    ) -> None:
        self._quantile = quantile
        self._continuation_tracker = CausalPercentileTracker(nan_policy="skip")
        self._confirmed_tracker = CausalPercentileTracker(nan_policy="skip")
        for value in continuation_priors:
            self._continuation_tracker.push(value)
        for value in confirmed_priors:
            self._confirmed_tracker.push(value)

    @property
    def continuation_history_count(self) -> int:
        return self._continuation_tracker.sample_count

    @property
    def confirmed_history_count(self) -> int:
        return self._confirmed_tracker.sample_count

    def assess(self, reversal_fraction: float) -> ConfirmationAssessment:
        observation = self._continuation_tracker.rank(reversal_fraction)
        threshold = (
            float("nan")
            if self._quantile is None
            else self._continuation_tracker.percentile_value(self._quantile)
        )
        confirmed = bool(
            self._quantile is not None
            and math.isfinite(reversal_fraction)
            and math.isfinite(threshold)
            and reversal_fraction >= threshold
        )
        return ConfirmationAssessment(
            confirmed=confirmed,
            reversal_evidence=observation.percentile,
            continuation_history_count=observation.sample_count,
            threshold=threshold,
        )

    @staticmethod
    def _validate_episode_maximum(
        maximum_reversal_fraction: Optional[float],
    ) -> Optional[float]:
        if maximum_reversal_fraction is None:
            return None
        if not math.isfinite(maximum_reversal_fraction) or maximum_reversal_fraction < 0.0:
            raise SwingDataError("Finalized episode reversal must be finite and non-negative.")
        return maximum_reversal_fraction

    def finalize_continuation_episode(
        self, maximum_reversal_fraction: Optional[float]
    ) -> bool:
        value = self._validate_episode_maximum(maximum_reversal_fraction)
        return False if value is None else self._continuation_tracker.push(value)

    def record_confirmed_episode(
        self, maximum_reversal_fraction: Optional[float]
    ) -> ConfirmedEpisodeDiagnostic:
        value = self._validate_episode_maximum(maximum_reversal_fraction)
        if value is None:
            return ConfirmedEpisodeDiagnostic(
                percentile=float("nan"),
                prior_confirmed_history_count=self._confirmed_tracker.sample_count,
            )
        observation = self._confirmed_tracker.rank(value)
        self._confirmed_tracker.push(value)
        return ConfirmedEpisodeDiagnostic(
            percentile=observation.percentile,
            prior_confirmed_history_count=observation.sample_count,
        )


@dataclass(frozen=True)
class EmpiricalConfirmationPolicy:
    """Explicit quantile policy over continuation/failed episode history only.

    `quantile` is mandatory and has no default. Confirmation thresholds never
    consume confirmed-swing episodes. Confirmed episodes are retained in a
    separate diagnostic distribution that cannot recalibrate this policy.
    """

    quantile: float
    prior_continuation_reversals: tuple[float, ...] = ()
    prior_confirmed_reversals: tuple[float, ...] = ()

    @staticmethod
    def _normalize_priors(values: object, label: str) -> tuple[float, ...]:
        try:
            priors = tuple(values)  # type: ignore[arg-type]
        except TypeError as exc:
            raise SwingConfigError(f"{label} must be iterable.") from exc

        normalized: list[float] = []
        for value in priors:
            if isinstance(value, (bool, np.bool_)) or not isinstance(
                value, (Real, np.integer, np.floating)
            ):
                raise SwingConfigError(f"{label} must contain finite non-negative values.")
            numeric = float(value)
            if not math.isfinite(numeric) or numeric < 0.0:
                raise SwingConfigError(f"{label} must contain finite non-negative values.")
            normalized.append(numeric)
        return tuple(normalized)

    def __post_init__(self) -> None:
        if isinstance(self.quantile, (bool, np.bool_)) or not isinstance(
            self.quantile, (Real, np.integer, np.floating)
        ):
            raise SwingConfigError("quantile must be a finite real number in [0,1].")
        quantile = float(self.quantile)
        if not math.isfinite(quantile) or not 0.0 <= quantile <= 1.0:
            raise SwingConfigError("quantile must lie in [0,1].")

        continuation = self._normalize_priors(
            self.prior_continuation_reversals,
            "prior_continuation_reversals",
        )
        confirmed = self._normalize_priors(
            self.prior_confirmed_reversals,
            "prior_confirmed_reversals",
        )
        object.__setattr__(self, "quantile", quantile)
        object.__setattr__(self, "prior_continuation_reversals", continuation)
        object.__setattr__(self, "prior_confirmed_reversals", confirmed)

    def create_runtime(self) -> SwingConfirmationRuntime:
        return _EmpiricalRuntime(
            self.quantile,
            self.prior_continuation_reversals,
            self.prior_confirmed_reversals,
        )


_OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
    "candidate_side",
    "candidate_origin_position",
    "candidate_price",
    "candidate_reversal_distance",
    "candidate_reversal_fraction",
    "candidate_reversal_evidence",
    "candidate_continuation_history_count",
    "candidate_confirmed_history_count",
    "candidate_confirmation_threshold",
    "swing_high_reversal_evidence",
    "swing_low_reversal_evidence",
    "swing_high_confirmed",
    "swing_low_confirmed",
    "swing_origin_position",
    "swing_price",
    "swing_confirmation_position",
    "swing_confirmation_price",
    "swing_reversal_distance",
    "swing_reversal_fraction",
    "swing_reversal_evidence",
    "swing_continuation_history_count",
    "swing_confirmed_history_percentile",
    "swing_confirmed_history_count",
    "swing_confirmation_threshold",
)


class CausalAdaptiveSwingDetector:
    """Stateless batch detector; policy runtime and all candidates are local."""

    def __init__(self, confirmation_policy: Optional[SwingConfirmationPolicy] = None) -> None:
        if confirmation_policy is not None and not isinstance(
            confirmation_policy, SwingConfirmationPolicy
        ):
            raise SwingConfigError(
                "confirmation_policy must implement create_runtime()."
            )
        self._policy = confirmation_policy

    @staticmethod
    def _validate_input(
        df: pd.DataFrame,
        *,
        high_col: str,
        low_col: str,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise SwingDataError("df must be a pandas DataFrame.")
        if df.columns.has_duplicates:
            duplicates = df.columns[df.columns.duplicated()].tolist()
            raise SwingDataError(f"Duplicate columns are forbidden: {duplicates!r}.")

        missing = [column for column in (high_col, low_col) if column not in df.columns]
        if missing:
            raise SwingDataError(f"Missing required columns: {missing!r}.")

        collisions = [column for column in _OUTPUT_COLUMNS if column in df.columns]
        if collisions:
            raise SwingDataError(
                f"Output columns already exist and would be overwritten: {collisions!r}."
            )

        if df.index.has_duplicates:
            raise SwingDataError("Duplicate index labels are forbidden.")
        try:
            ordered = bool(df.index.is_monotonic_increasing)
        except (TypeError, ValueError) as exc:
            raise SwingDataError("Index must have a well-defined increasing order.") from exc
        if not ordered:
            raise SwingDataError(
                "Index must already be monotonic increasing; silent sorting is forbidden."
            )

        for column in (high_col, low_col):
            series = df[column]
            if pd.api.types.is_bool_dtype(series.dtype):
                raise SwingDataError(f"Column {column!r} must be real numeric, not boolean.")
            if pd.api.types.is_complex_dtype(series.dtype):
                raise SwingDataError(f"Column {column!r} must be real numeric, not complex.")
            if not pd.api.types.is_numeric_dtype(series.dtype):
                raise SwingDataError(f"Column {column!r} must have a numeric dtype.")
            try:
                values = series.to_numpy(dtype=np.float64, na_value=np.nan)
            except (TypeError, ValueError, OverflowError) as exc:
                raise SwingDataError(f"Column {column!r} cannot be converted to float64.") from exc
            if not np.isfinite(values).all():
                raise SwingDataError(f"Column {column!r} contains NaN or infinity.")

        high = df[high_col].to_numpy(dtype=np.float64)
        low = df[low_col].to_numpy(dtype=np.float64)
        if np.any(high < low):
            position = int(np.flatnonzero(high < low)[0])
            raise SwingDataError(f"high < low at position {position}.")

    def _new_runtime(self) -> SwingConfirmationRuntime:
        if self._policy is None:
            return _EmpiricalRuntime(None, (), ())
        runtime = self._policy.create_runtime()
        if not isinstance(runtime, SwingConfirmationRuntime):
            raise SwingConfigError("confirmation_policy.create_runtime() returned invalid runtime.")
        return runtime

    @staticmethod
    def _fraction(distance: float, candidate_price: float) -> float:
        denominator = abs(candidate_price)
        if denominator == 0.0:
            return float("nan")
        fraction = distance / denominator
        if not math.isfinite(fraction):
            raise SwingDataError("Reversal fraction overflowed.")
        return fraction

    def analyze(
        self,
        df: pd.DataFrame,
        *,
        high_col: str = "high",
        low_col: str = "low",
    ) -> pd.DataFrame:
        self._validate_input(df, high_col=high_col, low_col=low_col)

        high = df[high_col].to_numpy(dtype=np.float64)
        low = df[low_col].to_numpy(dtype=np.float64)
        n = len(df)
        runtime = self._new_runtime()

        side_output = np.full(n, "UNDECIDED", dtype=object)
        candidate_origin = np.full(n, np.nan)
        candidate_price_out = np.full(n, np.nan)
        candidate_distance = np.full(n, np.nan)
        candidate_fraction = np.full(n, np.nan)
        candidate_evidence = np.full(n, np.nan)
        candidate_continuation_count = np.zeros(n, dtype=np.int64)
        candidate_confirmed_count = np.zeros(n, dtype=np.int64)
        candidate_threshold = np.full(n, np.nan)
        high_evidence = np.full(n, np.nan)
        low_evidence = np.full(n, np.nan)

        high_confirmed = np.zeros(n, dtype=bool)
        low_confirmed = np.zeros(n, dtype=bool)
        event_origin = np.full(n, np.nan)
        event_price = np.full(n, np.nan)
        event_confirmation = np.full(n, np.nan)
        event_confirmation_price = np.full(n, np.nan)
        event_distance = np.full(n, np.nan)
        event_fraction = np.full(n, np.nan)
        event_evidence = np.full(n, np.nan)
        event_continuation_count = np.zeros(n, dtype=np.int64)
        event_confirmed_percentile = np.full(n, np.nan)
        event_confirmed_count = np.zeros(n, dtype=np.int64)
        event_threshold = np.full(n, np.nan)

        side = "UNDECIDED"
        undecided_high = float("nan")
        undecided_low = float("nan")
        active_price = float("nan")
        active_origin = -1
        episode_max: Optional[float] = None

        for i in range(n):
            row_high = float(high[i])
            row_low = float(low[i])
            row_distance = float("nan")
            row_fraction = float("nan")
            row_assessment: Optional[ConfirmationAssessment] = None
            extended = False

            if i == 0:
                undecided_high = row_high
                undecided_low = row_low

            elif side == "UNDECIDED":
                extends_high = row_high > undecided_high
                extends_low = row_low < undecided_low

                if extends_high and extends_low:
                    # Outside bar: update both boundaries, infer no ordering.
                    undecided_high = row_high
                    undecided_low = row_low
                elif extends_high:
                    side = "HIGH"
                    active_price = row_high
                    active_origin = i
                    episode_max = None
                    extended = True
                elif extends_low:
                    side = "LOW"
                    active_price = row_low
                    active_origin = i
                    episode_max = None
                    extended = True

            elif side == "HIGH":
                if row_high > active_price:
                    runtime.finalize_continuation_episode(episode_max)
                    active_price = row_high
                    active_origin = i
                    episode_max = None
                    extended = True
                else:
                    row_distance = max(active_price - row_low, 0.0)
                    row_fraction = self._fraction(row_distance, active_price)
                    row_assessment = runtime.assess(row_fraction)
                    if math.isfinite(row_fraction):
                        episode_max = (
                            row_fraction
                            if episode_max is None
                            else max(episode_max, row_fraction)
                        )

                    if row_assessment.confirmed:
                        high_confirmed[i] = True
                        event_origin[i] = active_origin
                        event_price[i] = active_price
                        event_confirmation[i] = i
                        event_confirmation_price[i] = row_low
                        event_distance[i] = row_distance
                        event_fraction[i] = row_fraction
                        event_evidence[i] = row_assessment.reversal_evidence
                        event_continuation_count[i] = (
                            row_assessment.continuation_history_count
                        )
                        event_threshold[i] = row_assessment.threshold

                        diagnostic = runtime.record_confirmed_episode(episode_max)
                        event_confirmed_percentile[i] = diagnostic.percentile
                        event_confirmed_count[i] = (
                            diagnostic.prior_confirmed_history_count
                        )
                        side = "LOW"
                        active_price = row_low
                        active_origin = i
                        episode_max = None

            elif side == "LOW":
                if row_low < active_price:
                    runtime.finalize_continuation_episode(episode_max)
                    active_price = row_low
                    active_origin = i
                    episode_max = None
                    extended = True
                else:
                    row_distance = max(row_high - active_price, 0.0)
                    row_fraction = self._fraction(row_distance, active_price)
                    row_assessment = runtime.assess(row_fraction)
                    if math.isfinite(row_fraction):
                        episode_max = (
                            row_fraction
                            if episode_max is None
                            else max(episode_max, row_fraction)
                        )

                    if row_assessment.confirmed:
                        low_confirmed[i] = True
                        event_origin[i] = active_origin
                        event_price[i] = active_price
                        event_confirmation[i] = i
                        event_confirmation_price[i] = row_high
                        event_distance[i] = row_distance
                        event_fraction[i] = row_fraction
                        event_evidence[i] = row_assessment.reversal_evidence
                        event_continuation_count[i] = (
                            row_assessment.continuation_history_count
                        )
                        event_threshold[i] = row_assessment.threshold

                        diagnostic = runtime.record_confirmed_episode(episode_max)
                        event_confirmed_percentile[i] = diagnostic.percentile
                        event_confirmed_count[i] = (
                            diagnostic.prior_confirmed_history_count
                        )
                        side = "HIGH"
                        active_price = row_high
                        active_origin = i
                        episode_max = None

            # Snapshot current end-of-bar candidate state. If confirmation
            # switched side, this describes the newly initialized opposite
            # candidate; event columns retain the confirmed old candidate.
            side_output[i] = side
            candidate_continuation_count[i] = runtime.continuation_history_count
            candidate_confirmed_count[i] = runtime.confirmed_history_count

            if side in ("HIGH", "LOW"):
                candidate_origin[i] = active_origin
                candidate_price_out[i] = active_price

                event_occurred = high_confirmed[i] or low_confirmed[i]
                if not extended and not event_occurred and row_assessment is not None:
                    candidate_distance[i] = row_distance
                    candidate_fraction[i] = row_fraction
                    candidate_evidence[i] = row_assessment.reversal_evidence
                    candidate_threshold[i] = row_assessment.threshold
                    if side == "HIGH":
                        high_evidence[i] = row_assessment.reversal_evidence
                    else:
                        low_evidence[i] = row_assessment.reversal_evidence
                elif event_occurred:
                    # Type-specific evidence remains visible on confirmation
                    # row even though generic candidate fields now describe
                    # the opposite candidate initialized at bar close.
                    if high_confirmed[i]:
                        high_evidence[i] = event_evidence[i]
                    else:
                        low_evidence[i] = event_evidence[i]

        out = df.copy(deep=True)
        out["candidate_side"] = side_output
        out["candidate_origin_position"] = pd.array(candidate_origin, dtype="Int64")
        out["candidate_price"] = candidate_price_out
        out["candidate_reversal_distance"] = candidate_distance
        out["candidate_reversal_fraction"] = candidate_fraction
        out["candidate_reversal_evidence"] = candidate_evidence
        out["candidate_continuation_history_count"] = candidate_continuation_count
        out["candidate_confirmed_history_count"] = candidate_confirmed_count
        out["candidate_confirmation_threshold"] = candidate_threshold
        out["swing_high_reversal_evidence"] = high_evidence
        out["swing_low_reversal_evidence"] = low_evidence
        out["swing_high_confirmed"] = high_confirmed
        out["swing_low_confirmed"] = low_confirmed
        out["swing_origin_position"] = pd.array(event_origin, dtype="Int64")
        out["swing_price"] = event_price
        out["swing_confirmation_position"] = pd.array(event_confirmation, dtype="Int64")
        out["swing_confirmation_price"] = event_confirmation_price
        out["swing_reversal_distance"] = event_distance
        out["swing_reversal_fraction"] = event_fraction
        out["swing_reversal_evidence"] = event_evidence
        out["swing_continuation_history_count"] = event_continuation_count
        out["swing_confirmed_history_percentile"] = event_confirmed_percentile
        out["swing_confirmed_history_count"] = event_confirmed_count
        out["swing_confirmation_threshold"] = event_threshold
        return out


class _SwingAuditEngine(CausalAdaptiveSwingDetector):
    """Named adapter for Module 0.1 reports."""


if __name__ == "__main__":
    # Explicit caller prior permits a demonstrable first confirmation.
    policy = EmpiricalConfirmationPolicy(
        quantile=0.5,
        prior_continuation_reversals=(0.01, 0.02),
    )
    sample = pd.DataFrame(
        {
            "high": [10.0, 11.0, 10.8, 10.6, 11.2],
            "low": [9.0, 10.0, 10.5, 10.0, 10.2],
        }
    )
    result = CausalAdaptiveSwingDetector(policy).analyze(sample)
    assert not result.loc[1, "swing_high_confirmed"]
    assert result.loc[2, "swing_high_confirmed"]
    assert result.loc[2, "swing_origin_position"] == 1
    assert result.loc[2, "swing_confirmation_position"] == 2

    from trading_system.audit.causal_state import (
        ReentrancyPolicy,
        verify_state_isolation,
        verify_truncation_invariance,
    )

    rng = np.random.default_rng(2_101)
    n = 401
    midpoint = 100.0 + np.cumsum(rng.normal(0.0, 0.5, size=n))
    audit_a = pd.DataFrame(
        {
            "high": midpoint + rng.uniform(0.0, 1.0, size=n),
            "low": midpoint - rng.uniform(0.0, 1.0, size=n),
        }
    )
    midpoint_b = 250.0 + np.cumsum(rng.normal(0.0, 0.8, size=n + 7))
    audit_b = pd.DataFrame(
        {
            "high": midpoint_b + rng.uniform(0.0, 1.5, size=n + 7),
            "low": midpoint_b - rng.uniform(0.0, 1.5, size=n + 7),
        }
    )
    factory = lambda: _SwingAuditEngine(policy)
    truncation = verify_truncation_invariance(
        factory,
        audit_a,
        additional_split_points=[1, 2, 3, 17, 127, 256, 400],
    )
    assert truncation and all(item.passed for item in truncation)
    state = verify_state_isolation(
        factory,
        audit_a,
        audit_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed

    print("=" * 72)
    print("MODULE 2.1A V1.1 SELF-VERIFICATION PASSED")
    print("Swing events are visible only at causal confirmation rows.")
    print("=" * 72)

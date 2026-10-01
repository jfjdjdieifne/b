"""
Layer 0 — Module 0.2
Causal Percentile Tracker
VERSION 1

PURPOSE
-------
A strictly streaming empirical percentile engine.

At observation t:

    1. READ the percentile/rank of x[t] using history [0 .. t-1].
    2. ONLY AFTER the read is complete, PUSH x[t] into history.

Therefore the current observation can never calibrate its own score.

This primitive will later be shared by Liquidity, Volume Delta,
FVG, Order Blocks, volatility features, and other analytical modules.

IMPORTANT DESIGN DECISIONS
--------------------------
1. NO bootstrap magic value.
   If there is no historical information, percentile outputs are NaN.
   We do not fabricate neutral 0.5 or any other prior.

2. NO fixed minimum sample count.
   The tracker exposes sample_count. Downstream modules can model
   confidence explicitly instead of pretending an arbitrary N makes
   an estimate suddenly "valid".

3. NO fixed rolling window.
   Default history is expanding.

   An optional max_history can be supplied by an upstream adaptive
   mechanism when/if such a mechanism is formally built and audited.
   This utility does not invent that horizon itself.

4. NaN policy is explicit.
   Missing observations are not silently inserted into the empirical
   distribution.

5. Inf is rejected.
   Infinite market features are treated as upstream data errors rather
   than legitimate observations.

6. Ties use the empirical mid-rank:

       (# history < x + 0.5 * # history == x) / N

   The 0.5 is not a trading threshold. It is the mathematical midpoint
   convention for tied empirical ranks.

7. percentile_value() reads ONLY previously pushed observations.

8. reset() gives explicit state control.

CAUSALITY SCOPE
---------------
The streaming tracker is causal by construction if callers obey either:

    observation = tracker.observe(x)

or:

    result = tracker.rank(x)
    tracker.push(x)

`observe()` is preferred because it structurally enforces read-before-push.

No method accesses future observations.

This module contains no trading rules, no signal thresholds, and no
future-dependent calibration.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable, Iterator, Literal, Optional

import math
import numpy as np
import pandas as pd


# ============================================================================
# Exceptions
# ============================================================================

class CausalPercentileError(Exception):
    """Base exception for Module 0.2."""


class CausalPercentileConfigError(CausalPercentileError):
    """Invalid tracker configuration."""


class CausalPercentileDataError(CausalPercentileError):
    """Invalid observation supplied to the tracker."""


# ============================================================================
# Result objects
# ============================================================================

@dataclass(frozen=True)
class PercentileObservation:
    """
    Immutable result produced BEFORE the current value enters history.

    percentile:
        Empirical percentile rank relative only to prior observations.

        NaN when sample_count == 0.

    sample_count:
        Number of historical observations actually used.

    less_count / equal_count / greater_count:
        Exact empirical counts before insertion of the current value.

    history_min / history_max:
        Historical extrema before insertion. NaN when history is empty.

    value:
        Current observation being evaluated.

    accepted:
        False only when NaN policy instructs the tracker to skip a missing
        observation.
    """

    value: float
    percentile: float
    sample_count: int

    less_count: int
    equal_count: int
    greater_count: int

    history_min: float
    history_max: float

    accepted: bool


# ============================================================================
# Tracker
# ============================================================================

class CausalPercentileTracker:
    """
    Stateful causal empirical percentile tracker.

    Parameters
    ----------
    max_history:
        Optional upper bound on retained observations.

        None:
            expanding history.

        positive integer:
            rolling history containing only the most recently PUSHED
            observations.

        There is deliberately no numerical default horizon.

    nan_policy:
        "skip":
            rank(NaN) returns a non-accepted observation and push(NaN)
            does nothing.

        "raise":
            NaN is considered an input-data error.

    Notes
    -----
    `max_history` must represent information available/configured at the
    time the tracker is used. It must never be selected using future
    performance or future volatility.

    The tracker itself does not decide what market memory horizon is
    optimal. That belongs to a separate adaptive-memory component.
    """

    def __init__(
        self,
        *,
        max_history: Optional[int] = None,
        nan_policy: Literal["skip", "raise"] = "skip",
    ) -> None:

        if max_history is not None:
            if isinstance(max_history, (bool, np.bool_)):
                raise CausalPercentileConfigError(
                    "max_history must be None or a positive integer."
                )

            if not isinstance(max_history, (int, np.integer)):
                raise CausalPercentileConfigError(
                    "max_history must be None or a positive integer."
                )

            if int(max_history) <= 0:
                raise CausalPercentileConfigError(
                    "max_history must be > 0 when supplied."
                )

            max_history = int(max_history)

        if nan_policy not in ("skip", "raise"):
            raise CausalPercentileConfigError(
                "nan_policy must be 'skip' or 'raise'."
            )

        self._max_history = max_history
        self._nan_policy = nan_policy

        self._history: Deque[float] = deque(
            maxlen=max_history
        )

        self._total_pushed = 0
        self._total_skipped = 0

    # ======================================================================
    # Properties
    # ======================================================================

    @property
    def max_history(self) -> Optional[int]:
        return self._max_history

    @property
    def sample_count(self) -> int:
        """Number of observations currently retained."""
        return len(self._history)

    @property
    def total_pushed(self) -> int:
        """
        Number of finite observations accepted since construction/reset.

        This can exceed sample_count when bounded rolling memory is used.
        """
        return self._total_pushed

    @property
    def total_skipped(self) -> int:
        """Number of NaN observations skipped under nan_policy='skip'."""
        return self._total_skipped

    @property
    def is_empty(self) -> bool:
        return not self._history

    # ======================================================================
    # Validation
    # ======================================================================

    def _coerce_value(
        self,
        value: object,
        *,
        allow_nan: bool,
    ) -> float:

        if isinstance(value, (bool, np.bool_)):
            raise CausalPercentileDataError(
                "Boolean observations are not valid numerical market features."
            )

        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise CausalPercentileDataError(
                f"Observation must be a scalar real number. Got {value!r}."
            ) from exc

        if math.isnan(result):
            if allow_nan:
                return result

            raise CausalPercentileDataError(
                "NaN observation is not permitted in this operation."
            )

        if math.isinf(result):
            raise CausalPercentileDataError(
                "Infinite observations are rejected. "
                "Fix the upstream feature calculation instead."
            )

        return result

    # ======================================================================
    # Read API
    # ======================================================================

    def rank(
        self,
        value: object,
    ) -> PercentileObservation:
        """
        Evaluate `value` against CURRENT HISTORY WITHOUT mutating state.

        This is the causal READ operation.

        Calling rank(x) repeatedly produces the same result until push()
        changes the history.
        """

        x = self._coerce_value(
            value,
            allow_nan=True,
        )

        if math.isnan(x):
            if self._nan_policy == "raise":
                raise CausalPercentileDataError(
                    "NaN encountered with nan_policy='raise'."
                )

            return PercentileObservation(
                value=float("nan"),
                percentile=float("nan"),
                sample_count=len(self._history),
                less_count=0,
                equal_count=0,
                greater_count=0,
                history_min=float("nan"),
                history_max=float("nan"),
                accepted=False,
            )

        n = len(self._history)

        if n == 0:
            return PercentileObservation(
                value=x,
                percentile=float("nan"),
                sample_count=0,
                less_count=0,
                equal_count=0,
                greater_count=0,
                history_min=float("nan"),
                history_max=float("nan"),
                accepted=True,
            )

        less = 0
        equal = 0

        history_min = math.inf
        history_max = -math.inf

        for historical_value in self._history:

            if historical_value < history_min:
                history_min = historical_value

            if historical_value > history_max:
                history_max = historical_value

            if historical_value < x:
                less += 1
            elif historical_value == x:
                equal += 1

        greater = n - less - equal

        percentile = (
            less + 0.5 * equal
        ) / n

        return PercentileObservation(
            value=x,
            percentile=float(percentile),
            sample_count=n,
            less_count=less,
            equal_count=equal,
            greater_count=greater,
            history_min=float(history_min),
            history_max=float(history_max),
            accepted=True,
        )

    def percentile_value(
        self,
        percentile: float,
    ) -> float:
        """
        Read an empirical quantile from PRIOR/PUSHED history.

        No state mutation occurs.

        Returns NaN when history is empty.

        `percentile` must lie in [0, 1].

        NumPy's 'linear' quantile estimator is specified explicitly so
        behavior does not silently depend on an implicit method choice.
        This is an estimator convention, not a trading threshold.
        """

        if isinstance(percentile, (bool, np.bool_)):
            raise CausalPercentileConfigError(
                "percentile must be a finite number in [0, 1]."
            )

        try:
            q = float(percentile)
        except (TypeError, ValueError, OverflowError) as exc:
            raise CausalPercentileConfigError(
                f"Invalid percentile: {percentile!r}."
            ) from exc

        if not math.isfinite(q):
            raise CausalPercentileConfigError(
                "percentile must be finite."
            )

        if not 0.0 <= q <= 1.0:
            raise CausalPercentileConfigError(
                f"percentile must lie in [0,1]. Got {q}."
            )

        if not self._history:
            return float("nan")

        values = np.fromiter(
            self._history,
            dtype=np.float64,
            count=len(self._history),
        )

        return float(
            np.quantile(
                values,
                q,
                method="linear",
            )
        )

    # ======================================================================
    # Mutation API
    # ======================================================================

    def push(
        self,
        value: object,
    ) -> bool:
        """
        Insert one observation AFTER it has been evaluated.

        Returns
        -------
        bool
            True if inserted.
            False if NaN was skipped.
        """

        x = self._coerce_value(
            value,
            allow_nan=True,
        )

        if math.isnan(x):

            if self._nan_policy == "raise":
                raise CausalPercentileDataError(
                    "NaN encountered with nan_policy='raise'."
                )

            self._total_skipped += 1
            return False

        self._history.append(x)
        self._total_pushed += 1

        return True

    def observe(
        self,
        value: object,
    ) -> PercentileObservation:
        """
        Preferred streaming API.

        Performs atomically, in this exact logical order:

            result = rank(value)    # PRIOR history only
            push(value)             # current observation enters AFTER read
            return result

        This prevents accidental self-inclusion.
        """

        result = self.rank(value)

        if result.accepted:
            self.push(value)
        else:
            # rank() already established NaN is being skipped. Keep
            # skipped accounting centralized in push().
            self.push(value)

        return result

    # ======================================================================
    # Explicit state management
    # ======================================================================

    def reset(self) -> None:
        """Erase all retained/history accounting state."""

        self._history.clear()
        self._total_pushed = 0
        self._total_skipped = 0

    def history_snapshot(self) -> tuple[float, ...]:
        """
        Immutable copy of retained history.

        Intended for debugging/tests, not hot-path analytics.
        """
        return tuple(self._history)


# ============================================================================
# Causal Series API
# ============================================================================

def causal_percentile_series(
    values: pd.Series,
    *,
    max_history: Optional[int] = None,
    nan_policy: Literal["skip", "raise"] = "skip",
) -> pd.DataFrame:
    """
    Compute streaming percentiles for an entire Series.

    IMPORTANT
    ---------
    Passing the complete Series does NOT make this non-causal.

    Output at position i is produced by sequentially calling:

        tracker.observe(values.iloc[i])

    and therefore can only depend on positions [0 .. i-1].

    Returns
    -------
    DataFrame
        percentile
        sample_count
        accepted

    The first finite observation has percentile=NaN because there is no
    historical evidence before it.
    """

    if not isinstance(values, pd.Series):
        raise CausalPercentileDataError(
            "values must be a pandas Series."
        )

    tracker = CausalPercentileTracker(
        max_history=max_history,
        nan_policy=nan_policy,
    )

    n = len(values)

    percentile_output = np.full(
        n,
        np.nan,
        dtype=np.float64,
    )

    sample_count_output = np.zeros(
        n,
        dtype=np.int64,
    )

    accepted_output = np.zeros(
        n,
        dtype=bool,
    )

    raw_values = values.to_numpy()

    for i in range(n):

        result = tracker.observe(
            raw_values[i]
        )

        percentile_output[i] = (
            result.percentile
        )

        sample_count_output[i] = (
            result.sample_count
        )

        accepted_output[i] = (
            result.accepted
        )

    return pd.DataFrame(
        {
            "percentile": percentile_output,
            "sample_count": sample_count_output,
            "accepted": accepted_output,
        },
        index=values.index,
    )


# ============================================================================
# Adapter used only for Module 0.1 causal certification
# ============================================================================

class _PercentileAuditEngine:
    """
    Minimal adapter allowing Module 0.1's DataFrame auditor to test this
    streaming primitive as an engine.

    This is test infrastructure, not trading architecture.
    """

    def __init__(
        self,
        *,
        source_column: str,
        max_history: Optional[int] = None,
        nan_policy: Literal["skip", "raise"] = "skip",
    ) -> None:

        self._source_column = source_column
        self._max_history = max_history
        self._nan_policy = nan_policy

    def analyze(
        self,
        df: pd.DataFrame,
        **kwargs: object,
    ) -> pd.DataFrame:

        if self._source_column not in df.columns:
            raise CausalPercentileDataError(
                f"Missing source column {self._source_column!r}."
            )

        features = causal_percentile_series(
            df[self._source_column],
            max_history=self._max_history,
            nan_policy=self._nan_policy,
        )

        out = df.copy()

        out["causal_percentile"] = (
            features["percentile"]
        )

        out["causal_percentile_sample_count"] = (
            features["sample_count"]
        )

        out["causal_percentile_accepted"] = (
            features["accepted"]
        )

        return out


# ============================================================================
# Self-verification
# ============================================================================

if __name__ == "__main__":

    # ------------------------------------------------------------------
    # 1. Empty history must admit lack of knowledge.
    # ------------------------------------------------------------------

    tracker = CausalPercentileTracker()

    first = tracker.rank(10.0)

    assert math.isnan(first.percentile)
    assert first.sample_count == 0
    assert tracker.sample_count == 0, (
        "rank() mutated history."
    )


    # ------------------------------------------------------------------
    # 2. observe() must be READ BEFORE PUSH.
    # ------------------------------------------------------------------

    first = tracker.observe(10.0)

    assert math.isnan(first.percentile)
    assert first.sample_count == 0
    assert tracker.history_snapshot() == (10.0,)

    second = tracker.observe(20.0)

    assert second.sample_count == 1
    assert second.less_count == 1
    assert second.equal_count == 0
    assert second.greater_count == 0
    assert second.percentile == 1.0

    assert tracker.history_snapshot() == (
        10.0,
        20.0,
    )


    # ------------------------------------------------------------------
    # 3. Current observation must never score against itself.
    # ------------------------------------------------------------------

    self_inclusion = CausalPercentileTracker()

    observation = self_inclusion.observe(123.0)

    assert math.isnan(observation.percentile)
    assert observation.sample_count == 0

    # If self-inclusion existed, this would have been 0.5.


    # ------------------------------------------------------------------
    # 4. Exact tie behavior.
    # ------------------------------------------------------------------

    tie_tracker = CausalPercentileTracker()

    tie_tracker.push(10.0)
    tie_tracker.push(20.0)
    tie_tracker.push(20.0)
    tie_tracker.push(30.0)

    tied = tie_tracker.rank(20.0)

    assert tied.sample_count == 4
    assert tied.less_count == 1
    assert tied.equal_count == 2
    assert tied.greater_count == 1

    expected_midrank = (
        1 + 0.5 * 2
    ) / 4

    assert tied.percentile == expected_midrank


    # ------------------------------------------------------------------
    # 5. rank() must be non-mutating.
    # ------------------------------------------------------------------

    snapshot_before = tie_tracker.history_snapshot()

    r1 = tie_tracker.rank(25.0)
    r2 = tie_tracker.rank(25.0)

    snapshot_after = tie_tracker.history_snapshot()

    assert r1 == r2
    assert snapshot_before == snapshot_after


    # ------------------------------------------------------------------
    # 6. Explicit rolling memory.
    # ------------------------------------------------------------------

    bounded = CausalPercentileTracker(
        max_history=3
    )

    bounded.push(1.0)
    bounded.push(2.0)
    bounded.push(3.0)

    assert bounded.history_snapshot() == (
        1.0,
        2.0,
        3.0,
    )

    bounded.push(4.0)

    assert bounded.history_snapshot() == (
        2.0,
        3.0,
        4.0,
    )

    assert bounded.sample_count == 3
    assert bounded.total_pushed == 4


    # ------------------------------------------------------------------
    # 7. NaN skip policy.
    # ------------------------------------------------------------------

    nan_tracker = CausalPercentileTracker(
        nan_policy="skip"
    )

    missing = nan_tracker.observe(
        float("nan")
    )

    assert not missing.accepted
    assert math.isnan(missing.percentile)
    assert nan_tracker.sample_count == 0
    assert nan_tracker.total_pushed == 0
    assert nan_tracker.total_skipped == 1


    # ------------------------------------------------------------------
    # 8. NaN raise policy.
    # ------------------------------------------------------------------

    raising_tracker = CausalPercentileTracker(
        nan_policy="raise"
    )

    try:
        raising_tracker.observe(
            float("nan")
        )

    except CausalPercentileDataError:
        pass

    else:
        raise AssertionError(
            "nan_policy='raise' failed to reject NaN."
        )


    # ------------------------------------------------------------------
    # 9. Infinity must always be rejected.
    # ------------------------------------------------------------------

    for invalid_value in (
        float("inf"),
        float("-inf"),
    ):

        try:
            CausalPercentileTracker().observe(
                invalid_value
            )

        except CausalPercentileDataError:
            pass

        else:
            raise AssertionError(
                "Infinite observation was accepted."
            )


    # ------------------------------------------------------------------
    # 10. percentile_value reads prior history only.
    # ------------------------------------------------------------------

    quantile_tracker = CausalPercentileTracker()

    assert math.isnan(
        quantile_tracker.percentile_value(0.5)
    )

    for value in (
        1.0,
        2.0,
        3.0,
        4.0,
    ):
        quantile_tracker.push(value)

    median = quantile_tracker.percentile_value(
        0.5
    )

    assert median == 2.5


    # ------------------------------------------------------------------
    # 11. Series API causal sequence.
    # ------------------------------------------------------------------

    series = pd.Series(
        [10.0, 20.0, 15.0],
        name="feature",
    )

    result = causal_percentile_series(
        series
    )

    assert math.isnan(
        result["percentile"].iloc[0]
    )

    # 20 > all prior values [10].
    assert (
        result["percentile"].iloc[1]
        == 1.0
    )

    # 15 lies between historical [10,20]:
    # one of two prior observations is below it.
    assert (
        result["percentile"].iloc[2]
        == 0.5
    )

    assert result[
        "sample_count"
    ].tolist() == [
        0,
        1,
        2,
    ]


    # ------------------------------------------------------------------
    # 12. Manual truncation-invariance test.
    #
    # This test does NOT depend on Module 0.1 being importable, allowing
    # Module 0.2 to remain independently executable.
    # ------------------------------------------------------------------

    rng = np.random.default_rng(42)

    test_series = pd.Series(
        rng.normal(
            size=257
        ),
        name="feature",
    )

    full_output = causal_percentile_series(
        test_series
    )

    tested_splits = (
        1,
        17,
        63,
        128,
        256,
    )

    for split_at in tested_splits:

        truncated_output = (
            causal_percentile_series(
                test_series.iloc[:split_at]
            )
        )

        expected = (
            full_output.iloc[:split_at]
        )

        pd.testing.assert_frame_equal(
            expected,
            truncated_output,
            check_exact=True,
        )


    # ------------------------------------------------------------------
    # 13. Adversarial future mutation test.
    #
    # Mutating FUTURE observations must not alter the already-computed
    # historical prefix.
    # ------------------------------------------------------------------

    split_at = 128

    original = test_series.copy()
    mutated_future = test_series.copy()

    mutated_future.iloc[split_at:] = (
        mutated_future.iloc[split_at:]
        * 1_000_000.0
        + 999_999.0
    )

    original_output = (
        causal_percentile_series(
            original
        )
    )

    mutated_output = (
        causal_percentile_series(
            mutated_future
        )
    )

    pd.testing.assert_frame_equal(
        original_output.iloc[:split_at],
        mutated_output.iloc[:split_at],
        check_exact=True,
    )


    # ------------------------------------------------------------------
    # 14. Module 0.1 integration test, when available.
    # ------------------------------------------------------------------

    try:
        from trading_system.audit.causal_state import (
            verify_truncation_invariance,
        )

    except ImportError:
        print(
            "Module 0.1 integration test skipped: "
            "causal_state.py not importable from current path."
        )

    else:

        audit_df = pd.DataFrame(
            {
                "feature": rng.normal(
                    size=401
                )
            }
        )

        audit_results = (
            verify_truncation_invariance(
                lambda: _PercentileAuditEngine(
                    source_column="feature"
                ),
                audit_df,
                additional_split_points=[
                    1,
                    2,
                    37,
                    127,
                    256,
                    400,
                ],
            )
        )

        assert audit_results
        assert all(
            audit.passed
            for audit in audit_results
        )


    print("=" * 72)
    print(
        "MODULE 0.2 V1 SELF-VERIFICATION PASSED"
    )
    print(
        "Streaming percentile is read-before-push and "
        "truncation invariant at tested boundaries."
    )
    print("=" * 72)

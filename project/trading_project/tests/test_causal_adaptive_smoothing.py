import math

import numpy as np
import pandas as pd
import pytest

from trading_system.audit.causal_state import (
    ReentrancyPolicy,
    verify_state_isolation,
    verify_truncation_invariance,
)
from trading_system.core.causal_adaptive_smoothing import (
    CausalAdaptiveEMA,
    CausalSmoothingConfigError,
    CausalSmoothingDataError,
    _AdaptiveEMAAuditEngine,
    causal_adaptive_ema_series,
)


def test_hand_calculated_constant_period_recurrence():
    smoother = CausalAdaptiveEMA()
    results = [smoother.update(x, 3.0) for x in (10.0, 14.0, 18.0)]
    assert [result.alpha for result in results] == [0.5, 0.5, 0.5]
    assert [result.ema for result in results] == [10.0, 12.0, 15.0]


def test_changing_period_and_first_observation_seed():
    smoother = CausalAdaptiveEMA()
    first = smoother.update(5.0, 1000.0)
    second = smoother.update(9.0, 1.0)
    third = smoother.update(13.0, 3.0)

    assert first.ema == 5.0
    assert math.isnan(first.previous_ema)
    assert not first.initialized_before
    assert second.alpha == 1.0 and second.ema == 9.0
    assert third.alpha == 0.5 and third.ema == 11.0


def test_reset_erases_state_and_accounting():
    smoother = CausalAdaptiveEMA()
    smoother.update(1.0, 2.0)
    smoother.update(np.nan, 2.0)
    smoother.reset()

    assert not smoother.is_initialized
    assert math.isnan(smoother.current_ema)
    assert smoother.total_accepted == 0
    assert smoother.total_held == 0
    assert smoother.update(50.0, 9.0).ema == 50.0


def test_nan_hold_is_explicit_and_state_is_unchanged():
    smoother = CausalAdaptiveEMA(nan_policy="hold")
    smoother.update(10.0, 3.0)
    missing = smoother.update(np.nan, 50.0)

    assert not missing.accepted
    assert missing.ema == 10.0
    assert missing.previous_ema == 10.0
    assert math.isnan(missing.alpha)
    assert smoother.current_ema == 10.0
    assert smoother.total_accepted == 1
    assert smoother.total_held == 1
    assert smoother.update(14.0, 3.0).ema == 12.0


def test_leading_nans_do_not_create_state_and_first_finite_is_seed():
    smoother = CausalAdaptiveEMA(nan_policy="hold")

    first_missing = smoother.update(np.nan, 3.0)
    second_missing = smoother.update(np.nan, 7.5)

    assert not first_missing.accepted
    assert not second_missing.accepted
    assert math.isnan(first_missing.ema)
    assert math.isnan(second_missing.ema)
    assert not first_missing.initialized_before
    assert not second_missing.initialized_before
    assert not smoother.is_initialized
    assert smoother.total_held == 2

    first_finite = smoother.update(100.0, 25.25)
    assert first_finite.accepted
    assert not first_finite.initialized_before
    assert math.isnan(first_finite.previous_ema)
    assert first_finite.ema == 100.0
    assert smoother.current_ema == 100.0


def test_alpha_bounds_and_ema_convexity_for_fractional_periods():
    rng = np.random.default_rng(1_103)
    smoother = CausalAdaptiveEMA()

    for value, period in zip(
        rng.normal(0.0, 1_000.0, size=5_000),
        rng.uniform(1.0, 1_000_000.0, size=5_000),
    ):
        observation = smoother.update(value, period)
        assert 0.0 < observation.alpha <= 1.0

        if observation.initialized_before:
            lower = min(observation.previous_ema, observation.value)
            upper = max(observation.previous_ema, observation.value)
            assert lower <= observation.ema <= upper


def test_nan_raise_policy():
    with pytest.raises(CausalSmoothingDataError, match="nan_policy='raise'"):
        CausalAdaptiveEMA(nan_policy="raise").update(np.nan, 3.0)


def test_invalid_nan_policy_rejected():
    with pytest.raises(CausalSmoothingConfigError):
        CausalAdaptiveEMA(nan_policy="fabricate")


@pytest.mark.parametrize(
    "period",
    [True, np.bool_(False), np.nan, np.inf, -np.inf, 0.0, -1.0, "3", 1 + 2j],
)
def test_invalid_period_rejected(period):
    with pytest.raises(CausalSmoothingDataError):
        CausalAdaptiveEMA().update(1.0, period)


@pytest.mark.parametrize(
    "value",
    [True, np.bool_(False), np.inf, -np.inf, "1", 1 + 2j, [1.0]],
)
def test_invalid_value_rejected(value):
    with pytest.raises(CausalSmoothingDataError):
        CausalAdaptiveEMA().update(value, 3.0)


def test_invalid_period_is_not_hidden_by_held_nan_value():
    with pytest.raises(CausalSmoothingDataError):
        CausalAdaptiveEMA(nan_policy="hold").update(np.nan, np.nan)


def test_streaming_equals_series_exactly_and_index_is_preserved():
    index = pd.Index(["a", "b", "c", "d", "e"])
    values = pd.Series([10.0, 14.0, np.nan, 18.0, 15.0], index=index)
    periods = pd.Series([3.0, 3.0, 100.0, 1.0, 2.5], index=index)

    batch = causal_adaptive_ema_series(values, periods)
    stream = CausalAdaptiveEMA()
    observations = [
        stream.update(value, period)
        for value, period in zip(values.to_numpy(), periods.to_numpy())
    ]
    expected = pd.DataFrame(
        {
            "ema": [x.ema for x in observations],
            "alpha": [x.alpha for x in observations],
            "accepted": [x.accepted for x in observations],
            "initialized_before": [x.initialized_before for x in observations],
        },
        index=index,
    )

    pd.testing.assert_frame_equal(batch, expected, check_exact=True)
    assert batch.loc["c", "ema"] == 12.0
    assert not batch.loc["c", "accepted"]
    assert math.isnan(batch.loc["c", "alpha"])
    assert batch.index.equals(index)


def test_truncation_and_adversarial_future_value_and_period_mutation():
    rng = np.random.default_rng(44)
    n = 311
    values = pd.Series(rng.normal(size=n))
    periods = pd.Series(rng.uniform(1.0, 100.0, size=n))
    full = causal_adaptive_ema_series(values, periods)

    for split in (1, 2, 37, 127, 256, 310):
        truncated = causal_adaptive_ema_series(values.iloc[:split], periods.iloc[:split])
        pd.testing.assert_frame_equal(full.iloc[:split], truncated, check_exact=True)

    split = 127
    mutated_values = values.copy()
    mutated_values.iloc[split:] = mutated_values.iloc[split:] * 1e9 + 7.0
    mutated_value_result = causal_adaptive_ema_series(mutated_values, periods)
    pd.testing.assert_frame_equal(
        full.iloc[:split], mutated_value_result.iloc[:split], check_exact=True
    )

    mutated_periods = periods.copy()
    mutated_periods.iloc[split:] = mutated_periods.iloc[split:] * 1e8 + 1.0
    mutated_period_result = causal_adaptive_ema_series(values, mutated_periods)
    pd.testing.assert_frame_equal(
        full.iloc[:split], mutated_period_result.iloc[:split], check_exact=True
    )


def test_real_module_01_truncation_and_state_isolation():
    rng = np.random.default_rng(55)
    df_a = pd.DataFrame(
        {"value": rng.normal(size=257), "period": rng.uniform(1.0, 80.0, size=257)}
    )
    df_b = pd.DataFrame(
        {"value": rng.normal(size=263), "period": rng.uniform(1.0, 80.0, size=263)}
    )
    # Exercise hold semantics at leading and internal missing bars during the
    # real Module 0.1 truncation/state audits.
    df_a.loc[[0, 1, 63, 128], "value"] = np.nan
    df_b.loc[[0, 2, 127, 200], "value"] = np.nan

    factory = lambda: _AdaptiveEMAAuditEngine(
        value_column="value", period_column="period"
    )

    truncation = verify_truncation_invariance(
        factory, df_a, additional_split_points=[1, 2, 37, 128, 256]
    )
    assert all(result.passed for result in truncation)

    state = verify_state_isolation(
        factory,
        df_a,
        df_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed


def test_index_mismatch_rejected_without_alignment():
    values = pd.Series([1.0, 2.0], index=["a", "b"])
    periods = pd.Series([3.0, 3.0], index=["b", "a"])
    with pytest.raises(CausalSmoothingDataError, match="identical indexes"):
        causal_adaptive_ema_series(values, periods)


def test_duplicate_index_rejected():
    duplicate = pd.Index(["a", "a"])
    values = pd.Series([1.0, 2.0], index=duplicate)
    periods = pd.Series([3.0, 3.0], index=duplicate)
    with pytest.raises(CausalSmoothingDataError, match="Duplicate index"):
        causal_adaptive_ema_series(values, periods)


@pytest.mark.parametrize(
    "values,periods",
    [
        ([1.0], pd.Series([2.0])),
        (pd.Series([1.0]), [2.0]),
        (pd.Series([True, False]), pd.Series([2.0, 2.0])),
        (pd.Series([1.0, 2.0]), pd.Series([True, False])),
        (pd.Series(["1", "2"]), pd.Series([2.0, 2.0])),
        (pd.Series([1.0, 2.0]), pd.Series(["2", "3"])),
    ],
)
def test_series_type_and_dtype_validation(values, periods):
    with pytest.raises(CausalSmoothingDataError):
        causal_adaptive_ema_series(values, periods)


def test_empty_series_is_supported_without_fabricated_seed():
    values = pd.Series([], dtype="float64")
    periods = pd.Series([], dtype="float64")
    result = causal_adaptive_ema_series(values, periods)
    assert result.empty
    assert result.columns.tolist() == [
        "ema", "alpha", "accepted", "initialized_before"
    ]

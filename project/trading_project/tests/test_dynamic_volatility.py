import inspect
import math

import numpy as np
import pandas as pd
import pytest

from trading_system.audit.causal_state import (
    ReentrancyPolicy,
    verify_state_isolation,
    verify_truncation_invariance,
)
from trading_system.environment.dynamic_volatility import (
    DynamicVolatilityDataError,
    DynamicVolatilityEngine,
    _DynamicVolatilityAuditEngine,
)


def _market_frame(seed: int, n: int, base: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = base + np.cumsum(rng.normal(0.0, 0.5, size=n))
    high = close + rng.uniform(0.0, 1.25, size=n)
    low = close - rng.uniform(0.0, 1.25, size=n)
    return pd.DataFrame({"high": high, "low": low, "close": close})


def test_hand_calculated_true_range_gap_up_and_gap_down():
    df = pd.DataFrame(
        {
            "high": [10.0, 15.0, 8.0],
            "low": [8.0, 12.0, 6.0],
            "close": [9.0, 14.0, 7.0],
        }
    )
    out = DynamicVolatilityEngine().analyze(df)
    np.testing.assert_array_equal(out["true_range"].to_numpy(), [2.0, 6.0, 8.0])


def test_first_bar_and_previous_close_normalization_contract():
    df = pd.DataFrame(
        {"high": [110.0, 120.0], "low": [90.0, 110.0], "close": [100.0, 119.0]}
    )
    out = DynamicVolatilityEngine().analyze(df)

    assert out.loc[0, "true_range"] == 20.0
    assert math.isnan(out.loc[0, "normalized_true_range"])
    assert out.loc[1, "true_range"] == 20.0
    assert out.loc[1, "normalized_true_range"] == 20.0 / 100.0
    assert out.loc[1, "normalized_true_range"] != 20.0 / 119.0


def test_read_before_push_and_tie_midrank_match_module_02():
    df = pd.DataFrame(
        {
            "high": [101.0, 101.0, 101.0, 101.0],
            "low": [99.0, 99.0, 99.0, 99.0],
            "close": [100.0, 100.0, 100.0, 100.0],
        }
    )
    out = DynamicVolatilityEngine().analyze(df)

    assert math.isnan(out.loc[0, "true_range_percentile"])
    assert math.isnan(out.loc[1, "true_range_percentile"])
    assert out.loc[1, "true_range_history_count"] == 0
    assert out.loc[2, "true_range_percentile"] == 0.5
    assert out.loc[2, "true_range_history_count"] == 1
    assert out.loc[3, "true_range_percentile"] == 0.5
    assert out.loc[3, "true_range_history_count"] == 2

    assert math.isnan(out.loc[2, "expansion_percentile"])
    assert out.loc[2, "expansion_history_count"] == 0
    assert out.loc[3, "expansion_percentile"] == 0.5
    assert out.loc[3, "expansion_history_count"] == 1


def test_hand_calculated_signed_log_change_and_symmetry():
    # Construct normalized TR sequence 0.01 -> 0.02 -> 0.01 using a constant
    # previous close of 100 and no gaps beyond each bar range.
    df = pd.DataFrame(
        {
            "high": [100.5, 101.0, 102.0, 101.0],
            "low": [99.5, 100.0, 100.0, 100.0],
            "close": [100.0, 100.0, 100.0, 100.0],
        }
    )
    out = DynamicVolatilityEngine().analyze(df)

    # Bar 1 has ntr=.01, bar 2=.02, bar 3=.01.
    assert math.isnan(out.loc[1, "normalized_tr_change"])
    assert out.loc[2, "normalized_tr_change"] == math.log(0.02) - math.log(0.01)
    assert out.loc[3, "normalized_tr_change"] == math.log(0.01) - math.log(0.02)
    assert out.loc[2, "normalized_tr_change"] == -out.loc[3, "normalized_tr_change"]


def test_zero_or_undefined_normalized_range_does_not_get_epsilon():
    df = pd.DataFrame(
        {
            "high": [0.0, 0.0, 1.0, 1.0],
            "low": [0.0, 0.0, 1.0, 0.0],
            "close": [0.0, 1.0, 1.0, 1.0],
        }
    )
    out = DynamicVolatilityEngine().analyze(df)

    assert math.isnan(out.loc[0, "normalized_true_range"])
    assert math.isnan(out.loc[1, "normalized_true_range"])  # previous close is zero
    assert out.loc[2, "normalized_true_range"] == 0.0
    assert math.isnan(out.loc[2, "normalized_tr_change"])
    assert math.isnan(out.loc[3, "normalized_tr_change"])  # previous ntr is zero


def test_finite_nan_finite_normalized_range_does_not_bridge_change():
    # i=1 has finite NTR because close[0]=100. i=2 has undefined NTR because
    # close[1]=0. i=3 becomes finite again because close[2]=100. The i=3
    # change must remain NaN rather than bridging back to i=1.
    df = pd.DataFrame(
        {
            "high": [101.0, 101.0, 101.0, 104.0],
            "low": [99.0, 99.0, 99.0, 100.0],
            "close": [100.0, 0.0, 100.0, 102.0],
        }
    )
    out = DynamicVolatilityEngine().analyze(df)

    assert math.isfinite(out.loc[1, "normalized_true_range"])
    assert math.isnan(out.loc[2, "normalized_true_range"])
    assert math.isfinite(out.loc[3, "normalized_true_range"])
    assert math.isnan(out.loc[2, "normalized_tr_change"])
    assert math.isnan(out.loc[3, "normalized_tr_change"])


def test_future_ohlc_mutation_and_extreme_append_leave_prefix_exact():
    df = _market_frame(10, 257)
    engine = DynamicVolatilityEngine()
    full = engine.analyze(df)
    split = 128

    mutated = df.copy(deep=True)
    mutated.loc[mutated.index[split:], "high"] += 1_000_000.0
    mutated.loc[mutated.index[split:], "low"] -= 1_000_000.0
    mutated.loc[mutated.index[split:], "close"] *= 10_000.0
    mutated_out = engine.analyze(mutated)
    pd.testing.assert_frame_equal(
        full.iloc[:split], mutated_out.iloc[:split], check_exact=True
    )

    future = _market_frame(11, 20, base=1_000_000.0)
    future.index = pd.RangeIndex(len(df), len(df) + len(future))
    appended = pd.concat([df, future])
    appended_out = engine.analyze(appended)
    pd.testing.assert_frame_equal(
        full, appended_out.iloc[: len(df)], check_exact=True
    )


def test_module_01_truncation_and_state_isolation():
    df_a = _market_frame(20, 401)
    df_b = _market_frame(21, 409, base=250.0)

    truncation = verify_truncation_invariance(
        _DynamicVolatilityAuditEngine,
        df_a,
        additional_split_points=[1, 2, 3, 17, 127, 256, 400],
    )
    assert all(result.passed for result in truncation)

    state = verify_state_isolation(
        _DynamicVolatilityAuditEngine,
        df_a,
        df_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed


def test_positive_scale_invariance_and_raw_range_scaling():
    df = _market_frame(30, 211)
    scale = 8.0  # power of two gives exact binary scaling
    scaled = df * scale

    base_out = DynamicVolatilityEngine().analyze(df)
    scaled_out = DynamicVolatilityEngine().analyze(scaled)

    np.testing.assert_array_equal(
        scaled_out["true_range"].to_numpy(),
        base_out["true_range"].to_numpy() * scale,
    )
    pd.testing.assert_series_equal(
        base_out["normalized_true_range"],
        scaled_out["normalized_true_range"],
        check_exact=True,
    )
    pd.testing.assert_series_equal(
        base_out["true_range_percentile"],
        scaled_out["true_range_percentile"],
        check_exact=True,
    )
    pd.testing.assert_series_equal(
        base_out["normalized_tr_change"],
        scaled_out["normalized_tr_change"],
        check_exact=True,
    )
    pd.testing.assert_series_equal(
        base_out["expansion_percentile"],
        scaled_out["expansion_percentile"],
        check_exact=True,
    )


def test_empty_and_single_row_behavior():
    empty = pd.DataFrame(
        {
            "high": pd.Series([], dtype="float64"),
            "low": pd.Series([], dtype="float64"),
            "close": pd.Series([], dtype="float64"),
        }
    )
    empty_out = DynamicVolatilityEngine().analyze(empty)
    assert empty_out.empty
    assert empty_out.columns[-7:].tolist() == [
        "true_range", "normalized_true_range", "true_range_percentile",
        "true_range_history_count", "normalized_tr_change",
        "expansion_percentile", "expansion_history_count",
    ]

    one = pd.DataFrame({"high": [5.0], "low": [3.0], "close": [4.0]})
    one_out = DynamicVolatilityEngine().analyze(one)
    assert one_out.loc[0, "true_range"] == 2.0
    assert math.isnan(one_out.loc[0, "normalized_true_range"])
    assert math.isnan(one_out.loc[0, "true_range_percentile"])
    assert one_out.loc[0, "true_range_history_count"] == 0
    assert math.isnan(one_out.loc[0, "normalized_tr_change"])
    assert math.isnan(one_out.loc[0, "expansion_percentile"])
    assert one_out.loc[0, "expansion_history_count"] == 0


def test_original_input_is_not_mutated():
    df = _market_frame(40, 50)
    before = df.copy(deep=True)
    out = DynamicVolatilityEngine().analyze(df)
    pd.testing.assert_frame_equal(df, before, check_exact=True)
    assert out is not df


@pytest.mark.parametrize(
    "bad_df,match",
    [
        (pd.DataFrame({"high": [1.0], "low": [2.0], "close": [1.5]}), "high < low"),
        (pd.DataFrame({"high": [np.nan], "low": [0.0], "close": [1.0]}), "NaN or infinity"),
        (pd.DataFrame({"high": [np.inf], "low": [0.0], "close": [1.0]}), "NaN or infinity"),
        (pd.DataFrame({"high": ["1"], "low": ["0"], "close": ["1"]}), "numeric dtype"),
        (pd.DataFrame({"high": [True], "low": [False], "close": [True]}), "not boolean"),
    ],
)
def test_invalid_ohlc_rejected(bad_df, match):
    with pytest.raises(DynamicVolatilityDataError, match=match):
        DynamicVolatilityEngine().analyze(bad_df)


def test_duplicate_and_unordered_index_rejected():
    duplicate = pd.DataFrame(
        {"high": [2.0, 3.0], "low": [1.0, 2.0], "close": [1.5, 2.5]},
        index=[1, 1],
    )
    with pytest.raises(DynamicVolatilityDataError, match="Duplicate index"):
        DynamicVolatilityEngine().analyze(duplicate)

    unordered = duplicate.copy()
    unordered.index = [2, 1]
    with pytest.raises(DynamicVolatilityDataError, match="monotonic increasing"):
        DynamicVolatilityEngine().analyze(unordered)


def test_duplicate_columns_and_output_collision_rejected():
    duplicate_columns = pd.DataFrame(
        [[2.0, 2.1, 1.0, 1.5]],
        columns=["high", "high", "low", "close"],
    )
    with pytest.raises(DynamicVolatilityDataError, match="Duplicate column"):
        DynamicVolatilityEngine().analyze(duplicate_columns)

    collision = pd.DataFrame(
        {"high": [2.0], "low": [1.0], "close": [1.5], "true_range": [99.0]}
    )
    with pytest.raises(DynamicVolatilityDataError, match="would be overwritten"):
        DynamicVolatilityEngine().analyze(collision)


def test_custom_column_names_and_input_contract():
    df = pd.DataFrame({"H": [2.0, 3.0], "L": [1.0, 2.0], "C": [1.5, 2.5]})
    out = DynamicVolatilityEngine().analyze(df, high_col="H", low_col="L", close_col="C")
    assert "true_range" in out

    with pytest.raises(DynamicVolatilityDataError, match="Missing required"):
        DynamicVolatilityEngine().analyze(df)


def test_constitutional_textual_guard():
    source = inspect.getsource(__import__(
        "trading_system.environment.dynamic_volatility", fromlist=["*"]
    ))
    forbidden = [
        "rolling(", "center=True", "shift(-1", "rank(pct=True)",
        "expanding(", "causal_kernels", "ATR(14)", "min_period=5",
        "max_period=50", "period=14",
    ]
    for token in forbidden:
        assert token not in source

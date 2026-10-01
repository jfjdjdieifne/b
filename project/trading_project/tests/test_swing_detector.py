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
from trading_system.structure.swing_detector import (
    CausalAdaptiveSwingDetector,
    EmpiricalConfirmationPolicy,
    SwingConfigError,
    SwingDataError,
    _SwingAuditEngine,
)


def _policy(priors=(0.01, 0.02), quantile=0.5):
    return EmpiricalConfirmationPolicy(
        quantile=quantile,
        prior_continuation_reversals=priors,
    )


def _random_frame(seed, n, base=100.0):
    rng = np.random.default_rng(seed)
    midpoint = base + np.cumsum(rng.normal(0.0, 0.5, size=n))
    return pd.DataFrame(
        {
            "high": midpoint + rng.uniform(0.0, 1.0, size=n),
            "low": midpoint - rng.uniform(0.0, 1.0, size=n),
        }
    )


def test_evidence_only_mode_has_no_confirmations_and_candidate_high_repaints_forward_only():
    df = pd.DataFrame(
        {"high": [10.0, 11.0, 12.0, 11.5], "low": [9.0, 10.0, 10.5, 10.0]}
    )
    out = CausalAdaptiveSwingDetector().analyze(df)

    assert not out["swing_high_confirmed"].any()
    assert not out["swing_low_confirmed"].any()
    assert out.loc[1, "candidate_side"] == "HIGH"
    assert out.loc[1, "candidate_price"] == 11.0
    assert out.loc[1, "candidate_origin_position"] == 1
    assert out.loc[2, "candidate_price"] == 12.0
    assert out.loc[2, "candidate_origin_position"] == 2
    # Historical row remains its original snapshot; no backfill/repaint.
    assert out.loc[1, "candidate_price"] == 11.0
    assert math.isnan(out.loc[2, "candidate_reversal_evidence"])


def test_candidate_low_moves_lower_without_historical_mutation():
    df = pd.DataFrame(
        {"high": [10.0, 9.0, 8.5, 9.0], "low": [9.0, 8.0, 7.0, 7.5]}
    )
    out = CausalAdaptiveSwingDetector().analyze(df)
    assert out.loc[1, "candidate_side"] == "LOW"
    assert out.loc[1, "candidate_price"] == 8.0
    assert out.loc[2, "candidate_price"] == 7.0
    assert out.loc[1, "candidate_price"] == 8.0
    assert not out["swing_low_confirmed"].any()


def test_confirmation_visible_only_at_confirmation_row_with_complete_metadata():
    df = pd.DataFrame(
        {"high": [10.0, 11.0, 10.8], "low": [9.0, 10.0, 10.5]}
    )
    out = CausalAdaptiveSwingDetector(_policy()).analyze(df)

    assert not out.loc[0, "swing_high_confirmed"]
    assert not out.loc[1, "swing_high_confirmed"]
    assert out.loc[2, "swing_high_confirmed"]
    assert out.loc[2, "swing_origin_position"] == 1
    assert out.loc[2, "swing_price"] == 11.0
    assert out.loc[2, "swing_confirmation_position"] == 2
    assert out.loc[2, "swing_confirmation_price"] == 10.5
    assert out.loc[2, "swing_reversal_distance"] == 0.5
    assert out.loc[2, "swing_reversal_fraction"] == 0.5 / 11.0
    assert out.loc[2, "swing_continuation_history_count"] == 2
    assert out.loc[2, "swing_confirmation_threshold"] == 0.015
    # Confirmation does not contaminate the continuation/noise baseline.
    assert out.loc[2, "candidate_continuation_history_count"] == 2
    assert out.loc[2, "candidate_confirmed_history_count"] == 1
    assert out.loc[2, "swing_confirmed_history_count"] == 0
    assert math.isnan(out.loc[2, "swing_confirmed_history_percentile"])
    # End-of-bar candidate state has switched to LOW at current wick.
    assert out.loc[2, "candidate_side"] == "LOW"
    assert out.loc[2, "candidate_origin_position"] == 2
    assert out.loc[2, "candidate_price"] == 10.5


def test_low_confirmation_alternates_after_high():
    df = pd.DataFrame(
        {
            "high": [10.0, 11.0, 10.8, 10.6, 10.8],
            "low": [9.0, 10.0, 10.5, 10.0, 10.1],
        }
    )
    out = CausalAdaptiveSwingDetector(_policy()).analyze(df)
    assert out.loc[2, "swing_high_confirmed"]
    assert not out.loc[3, "swing_low_confirmed"]  # strict new low; same bar excluded
    assert out.loc[4, "swing_low_confirmed"]
    assert out.loc[4, "swing_origin_position"] == 3
    assert out.loc[4, "swing_confirmation_price"] == 10.8


def test_huge_outside_bar_cannot_extend_and_confirm_same_candidate():
    df = pd.DataFrame(
        {
            "high": [10.0, 11.0, 100.0, 99.0],
            "low": [9.0, 10.0, -100.0, 98.0],
        }
    )
    out = CausalAdaptiveSwingDetector(_policy(priors=(0.001,))).analyze(df)

    assert out.loc[2, "candidate_price"] == 100.0
    assert out.loc[2, "candidate_origin_position"] == 2
    assert not out.loc[2, "swing_high_confirmed"]
    assert math.isnan(out.loc[2, "candidate_reversal_fraction"])
    # Subsequent completed bar may be evaluated without intrabar ordering.
    assert out.loc[3, "swing_high_confirmed"]


def test_outside_bar_while_undecided_confirms_nothing_and_keeps_direction_undecided():
    df = pd.DataFrame(
        {"high": [10.0, 20.0, 21.0], "low": [9.0, -5.0, 0.0]}
    )
    out = CausalAdaptiveSwingDetector(_policy(priors=(0.001,))).analyze(df)
    assert out.loc[1, "candidate_side"] == "UNDECIDED"
    assert not out.loc[1, "swing_high_confirmed"]
    assert not out.loc[1, "swing_low_confirmed"]
    assert out.loc[2, "candidate_side"] == "HIGH"
    assert not out.loc[2, "swing_high_confirmed"]


def test_equal_extreme_retains_earlier_origin_without_epsilon():
    high_df = pd.DataFrame(
        {"high": [10.0, 11.0, 11.0], "low": [9.0, 10.0, 10.9]}
    )
    high_out = CausalAdaptiveSwingDetector().analyze(high_df)
    assert high_out.loc[2, "candidate_origin_position"] == 1
    assert high_out.loc[2, "candidate_price"] == 11.0

    low_df = pd.DataFrame(
        {"high": [10.0, 9.0, 8.1], "low": [9.0, 8.0, 8.0]}
    )
    low_out = CausalAdaptiveSwingDetector().analyze(low_df)
    assert low_out.loc[2, "candidate_origin_position"] == 1
    assert low_out.loc[2, "candidate_price"] == 8.0


def test_episode_history_pushes_once_on_replacement_not_every_bar():
    # Establish HIGH at bar 1. Bars 2/3 produce evolving reversals but do not
    # enter history. Bar 4 replaces the high and finalizes one max episode.
    df = pd.DataFrame(
        {
            "high": [10.0, 11.0, 10.9, 10.8, 12.0, 11.9],
            "low": [9.0, 10.0, 10.7, 10.5, 11.5, 11.8],
        }
    )
    out = CausalAdaptiveSwingDetector().analyze(df)
    assert out.loc[2, "candidate_continuation_history_count"] == 0
    assert out.loc[3, "candidate_continuation_history_count"] == 0
    assert out.loc[4, "candidate_continuation_history_count"] == 1
    assert out.loc[5, "candidate_continuation_history_count"] == 1
    # Current bar ranks against the one finalized prior episode.
    assert not math.isnan(out.loc[5, "candidate_reversal_evidence"])


def test_confirmed_episode_does_not_change_continuation_threshold():
    df = pd.DataFrame(
        {
            "high": [10.0, 11.0, 10.8, 10.6, 10.1],
            "low": [9.0, 10.0, 10.5, 10.0, 10.0],
        }
    )
    out = CausalAdaptiveSwingDetector(_policy()).analyze(df)

    assert out.loc[2, "swing_high_confirmed"]
    assert out.loc[2, "swing_confirmation_threshold"] == 0.015
    assert out.loc[2, "candidate_continuation_history_count"] == 2
    assert out.loc[2, "candidate_confirmed_history_count"] == 1

    # Bar 3 strictly replaces the newly initialized LOW candidate and has no
    # prior unambiguous reversal to finalize. Bar 4 reads the same continuation
    # threshold; the confirmed HIGH episode never entered that baseline.
    assert not out.loc[3, "swing_low_confirmed"]
    assert out.loc[4, "candidate_confirmation_threshold"] == 0.015
    assert out.loc[4, "candidate_continuation_history_count"] == 2
    assert out.loc[4, "candidate_confirmed_history_count"] == 1


def test_failed_replaced_episode_changes_continuation_threshold():
    df = pd.DataFrame(
        {
            "high": [100.0, 110.0, 109.9, 120.0, 119.9],
            "low": [99.0, 109.0, 109.45, 119.0, 119.5],
        }
    )
    out = CausalAdaptiveSwingDetector(_policy()).analyze(df)

    # Bar 2 adverse excursion is 0.55/110 = .005, below prior threshold .015.
    assert not out.loc[2, "swing_high_confirmed"]
    assert out.loc[2, "candidate_confirmation_threshold"] == 0.015

    # Bar 3 continues to a new high and finalizes that failed episode into the
    # continuation baseline. Priors [.01,.02] plus .005 yield median .01.
    assert out.loc[3, "candidate_continuation_history_count"] == 3
    assert out.loc[4, "candidate_confirmation_threshold"] == 0.01
    assert out.loc[4, "candidate_confirmed_history_count"] == 0


def test_outside_bar_opposite_wick_never_contaminates_later_history():
    df = pd.DataFrame(
        {
            "high": [110.0, 111.0, 115.0, 114.5, 116.0, 115.5],
            "low": [100.0, 101.0, 90.0, 114.0, 115.0, 115.5],
        }
    )
    policy = EmpiricalConfirmationPolicy(quantile=0.5)
    out = CausalAdaptiveSwingDetector(policy).analyze(df)

    # Huge outside bar updates HIGH to 115 but its low=90 is excluded entirely.
    assert out.loc[2, "candidate_price"] == 115.0
    assert math.isnan(out.loc[2, "candidate_reversal_fraction"])
    assert out.loc[2, "candidate_continuation_history_count"] == 0

    # Only bar 3 contributes to the episode max: (115-114)/115 = 1/115.
    # Bar 4 replaces the candidate and finalizes exactly that value.
    expected = 1.0 / 115.0
    assert out.loc[4, "candidate_continuation_history_count"] == 1
    assert out.loc[5, "candidate_confirmation_threshold"] == expected
    assert out.loc[5, "candidate_continuation_history_count"] == 1
    # If low=90 had leaked, threshold would instead be 25/115.
    assert out.loc[5, "candidate_confirmation_threshold"] != 25.0 / 115.0


def test_empty_empirical_history_cannot_confirm():
    df = pd.DataFrame(
        {"high": [10.0, 11.0, 10.0], "low": [9.0, 10.0, 1.0]}
    )
    policy = EmpiricalConfirmationPolicy(quantile=0.5)
    out = CausalAdaptiveSwingDetector(policy).analyze(df)
    assert not out["swing_high_confirmed"].any()
    assert math.isnan(out.loc[2, "candidate_confirmation_threshold"])
    assert out.loc[2, "candidate_continuation_history_count"] == 0


def test_policy_quantile_has_no_default_and_invalid_config_rejected():
    with pytest.raises(TypeError):
        EmpiricalConfirmationPolicy()  # type: ignore[call-arg]

    for quantile in (True, "0.5", np.nan, np.inf, -0.1, 1.1):
        with pytest.raises(SwingConfigError):
            EmpiricalConfirmationPolicy(quantile=quantile)

    for priors in ((-0.1,), ("0.1",), (np.nan,), (np.inf,), (True,)):
        with pytest.raises(SwingConfigError):
            EmpiricalConfirmationPolicy(quantile=0.5, prior_continuation_reversals=priors)


def test_zero_candidate_denominator_is_nan_without_epsilon():
    df = pd.DataFrame(
        {"high": [-1.0, 0.0, -0.1], "low": [-2.0, -1.0, -1.0]}
    )
    out = CausalAdaptiveSwingDetector().analyze(df)
    assert out.loc[1, "candidate_side"] == "HIGH"
    assert out.loc[1, "candidate_price"] == 0.0
    assert math.isnan(out.loc[2, "candidate_reversal_fraction"])
    assert math.isnan(out.loc[2, "candidate_reversal_evidence"])


def test_flat_market_remains_undecided_without_events():
    df = pd.DataFrame({"high": [10.0] * 10, "low": [10.0] * 10})
    out = CausalAdaptiveSwingDetector(_policy()).analyze(df)
    assert (out["candidate_side"] == "UNDECIDED").all()
    assert not out["swing_high_confirmed"].any()
    assert not out["swing_low_confirmed"].any()


def test_gap_reversal_uses_current_wick_and_can_confirm_on_later_bar():
    df = pd.DataFrame(
        {"high": [10.0, 11.0, 8.0], "low": [9.0, 10.0, 7.0]}
    )
    out = CausalAdaptiveSwingDetector(_policy(priors=(0.01,))).analyze(df)
    assert out.loc[2, "swing_high_confirmed"]
    assert out.loc[2, "swing_confirmation_price"] == 7.0
    assert out.loc[2, "swing_reversal_distance"] == 4.0


def test_scale_invariance_of_fractions_evidence_and_events():
    df = pd.DataFrame(
        {
            "high": [10.0, 11.0, 10.8, 10.6, 10.8, 10.4],
            "low": [9.0, 10.0, 10.5, 10.0, 10.1, 9.8],
        }
    )
    policy = _policy()
    base = CausalAdaptiveSwingDetector(policy).analyze(df)
    scaled = CausalAdaptiveSwingDetector(policy).analyze(df * 8.0)

    for column in (
        "candidate_reversal_fraction", "candidate_reversal_evidence",
        "swing_high_reversal_evidence", "swing_low_reversal_evidence",
        "swing_reversal_fraction", "swing_reversal_evidence",
        "candidate_confirmation_threshold", "swing_confirmation_threshold",
    ):
        pd.testing.assert_series_equal(base[column], scaled[column], check_exact=True)

    for column in ("swing_high_confirmed", "swing_low_confirmed"):
        pd.testing.assert_series_equal(base[column], scaled[column], check_exact=True)

    np.testing.assert_allclose(
        scaled["candidate_price"], base["candidate_price"] * 8.0, equal_nan=True
    )


def test_future_mutation_and_extreme_append_preserve_history_exactly():
    df = _random_frame(100, 257)
    policy = _policy(priors=(0.001, 0.005, 0.01), quantile=0.5)
    engine = CausalAdaptiveSwingDetector(policy)
    full = engine.analyze(df)
    split = 128

    mutated = df.copy()
    mutated.loc[split:, "high"] += 1_000_000.0
    mutated.loc[split:, "low"] -= 1_000_000.0
    mutated_out = engine.analyze(mutated)
    pd.testing.assert_frame_equal(
        full.iloc[:split], mutated_out.iloc[:split], check_exact=True
    )

    future = _random_frame(101, 20, base=1_000_000.0)
    future.index = pd.RangeIndex(len(df), len(df) + len(future))
    appended = pd.concat([df, future])
    appended_out = engine.analyze(appended)
    pd.testing.assert_frame_equal(full, appended_out.iloc[: len(df)], check_exact=True)


def test_module_01_truncation_and_state_isolation_with_policy():
    df_a = _random_frame(200, 401)
    df_b = _random_frame(201, 409, base=250.0)
    policy = _policy(priors=(0.001, 0.005, 0.01), quantile=0.5)
    factory = lambda: _SwingAuditEngine(policy)

    truncation = verify_truncation_invariance(
        factory,
        df_a,
        additional_split_points=[1, 2, 3, 17, 127, 256, 400],
    )
    assert all(item.passed for item in truncation)

    state = verify_state_isolation(
        factory,
        df_a,
        df_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed


def test_empty_one_and_two_row_inputs_are_explicit():
    empty = pd.DataFrame(
        {"high": pd.Series([], dtype="float64"), "low": pd.Series([], dtype="float64")}
    )
    empty_out = CausalAdaptiveSwingDetector().analyze(empty)
    assert empty_out.empty
    assert "swing_high_confirmed" in empty_out

    one = CausalAdaptiveSwingDetector().analyze(pd.DataFrame({"high": [2.0], "low": [1.0]}))
    assert one.loc[0, "candidate_side"] == "UNDECIDED"
    assert not one.loc[0, "swing_high_confirmed"]

    two = CausalAdaptiveSwingDetector().analyze(
        pd.DataFrame({"high": [2.0, 3.0], "low": [1.0, 2.0]})
    )
    assert two.loc[1, "candidate_side"] == "HIGH"
    assert not two.loc[1, "swing_high_confirmed"]


@pytest.mark.parametrize(
    "bad,match",
    [
        (pd.DataFrame({"high": [1.0], "low": [2.0]}), "high < low"),
        (pd.DataFrame({"high": [np.nan], "low": [0.0]}), "NaN or infinity"),
        (pd.DataFrame({"high": [np.inf], "low": [0.0]}), "NaN or infinity"),
        (pd.DataFrame({"high": ["1"], "low": ["0"]}), "numeric dtype"),
        (pd.DataFrame({"high": [True], "low": [False]}), "not boolean"),
    ],
)
def test_invalid_ohlc_rejected(bad, match):
    with pytest.raises(SwingDataError, match=match):
        CausalAdaptiveSwingDetector().analyze(bad)


def test_duplicate_nonmonotonic_index_duplicate_columns_and_collision_rejected():
    duplicate_index = pd.DataFrame(
        {"high": [2.0, 3.0], "low": [1.0, 2.0]}, index=[1, 1]
    )
    with pytest.raises(SwingDataError, match="Duplicate index"):
        CausalAdaptiveSwingDetector().analyze(duplicate_index)

    unordered = duplicate_index.copy()
    unordered.index = [2, 1]
    with pytest.raises(SwingDataError, match="monotonic increasing"):
        CausalAdaptiveSwingDetector().analyze(unordered)

    duplicate_columns = pd.DataFrame([[2.0, 2.1, 1.0]], columns=["high", "high", "low"])
    with pytest.raises(SwingDataError, match="Duplicate columns"):
        CausalAdaptiveSwingDetector().analyze(duplicate_columns)

    collision = pd.DataFrame(
        {"high": [2.0], "low": [1.0], "swing_high_confirmed": [False]}
    )
    with pytest.raises(SwingDataError, match="would be overwritten"):
        CausalAdaptiveSwingDetector().analyze(collision)


def test_input_immutability_and_custom_columns():
    df = _random_frame(300, 50)
    before = df.copy(deep=True)
    out = CausalAdaptiveSwingDetector().analyze(df)
    pd.testing.assert_frame_equal(df, before, check_exact=True)
    assert out is not df

    custom = df.rename(columns={"high": "H", "low": "L"})
    custom_out = CausalAdaptiveSwingDetector().analyze(custom, high_col="H", low_col="L")
    assert "candidate_side" in custom_out


def test_textual_guard_secondary_only():
    module = __import__("trading_system.structure.swing_detector", fromlist=["*"])
    source = inspect.getsource(module)
    forbidden = [
        "center=True", "shift(-1", "rolling(", "find_peaks", "argrelextrema",
        "ATR multiplier", "zigzag_percentage", "left=5", "right=5",
    ]
    for token in forbidden:
        assert token not in source

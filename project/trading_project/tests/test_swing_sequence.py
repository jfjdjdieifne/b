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
)
from trading_system.structure.swing_sequence import (
    ConfirmedSwingSequenceEngine,
    SwingSequenceDataError,
    _SwingSequenceAuditEngine,
)


def _event_frame(length, events):
    high_flags = np.zeros(length, dtype=bool)
    low_flags = np.zeros(length, dtype=bool)
    origins = pd.array([pd.NA] * length, dtype="Int64")
    prices = np.full(length, np.nan)
    confirmations = pd.array([pd.NA] * length, dtype="Int64")

    for row, event_type, origin, price in events:
        if event_type == "HIGH":
            high_flags[row] = True
        elif event_type == "LOW":
            low_flags[row] = True
        else:
            raise ValueError(event_type)
        origins[row] = origin
        prices[row] = price
        confirmations[row] = row

    return pd.DataFrame(
        {
            "swing_high_confirmed": high_flags,
            "swing_low_confirmed": low_flags,
            "swing_origin_position": origins,
            "swing_price": prices,
            "swing_confirmation_position": confirmations,
        }
    )


def _classes(events, length=None):
    if length is None:
        length = max(row for row, *_ in events) + 1
    out = ConfirmedSwingSequenceEngine().analyze(_event_frame(length, events))
    return out


def test_first_high_and_first_low_are_unclassified():
    high = _classes([(2, "HIGH", 0, 100.0)], length=3)
    low = _classes([(2, "LOW", 0, 90.0)], length=3)

    assert high.loc[2, "structure_event_type"] == "HIGH"
    assert high.loc[2, "swing_sequence_class"] == "UNCLASSIFIED"
    assert not high.loc[2, "comparison_available"]
    assert math.isnan(high.loc[2, "previous_same_type_price"])
    assert pd.isna(high.loc[2, "previous_same_type_origin_position"])

    assert low.loc[2, "structure_event_type"] == "LOW"
    assert low.loc[2, "swing_sequence_class"] == "UNCLASSIFIED"
    assert not low.loc[2, "comparison_available"]


@pytest.mark.parametrize(
    "first,second,expected",
    [(100.0, 110.0, "HH"), (100.0, 90.0, "LH"), (100.0, 100.0, "EH")],
)
def test_high_exact_relationships(first, second, expected):
    out = _classes(
        [(1, "HIGH", 0, first), (4, "HIGH", 3, second)], length=5
    )
    assert out.loc[4, "swing_sequence_class"] == expected
    assert out.loc[4, "previous_same_type_price"] == first
    assert out.loc[4, "previous_same_type_origin_position"] == 0


@pytest.mark.parametrize(
    "first,second,expected",
    [(90.0, 95.0, "HL"), (90.0, 80.0, "LL"), (90.0, 90.0, "EL")],
)
def test_low_exact_relationships(first, second, expected):
    out = _classes(
        [(1, "LOW", 0, first), (4, "LOW", 3, second)], length=5
    )
    assert out.loc[4, "swing_sequence_class"] == expected
    assert out.loc[4, "previous_same_type_price"] == first
    assert out.loc[4, "previous_same_type_origin_position"] == 0


def test_mixed_sequence_compares_same_type_only():
    events = [
        (1, "HIGH", 0, 100.0),
        (2, "LOW", 1, 90.0),
        (4, "HIGH", 3, 110.0),
        (6, "LOW", 5, 95.0),
    ]
    out = _classes(events, length=7)
    assert out.loc[[1, 2, 4, 6], "swing_sequence_class"].tolist() == [
        "UNCLASSIFIED", "UNCLASSIFIED", "HH", "HL"
    ]


def test_consecutive_same_type_events_do_not_require_alternation():
    events = [
        (1, "HIGH", 0, 100.0),
        (2, "HIGH", 1, 105.0),
        (3, "HIGH", 0, 103.0),
        (4, "LOW", 2, 90.0),
    ]
    out = _classes(events, length=5)
    assert out.loc[[1, 2, 3], "swing_sequence_class"].tolist() == [
        "UNCLASSIFIED", "HH", "LH"
    ]
    assert out.loc[3, "previous_same_type_price"] == 105.0
    assert out.loc[4, "swing_sequence_class"] == "UNCLASSIFIED"


def test_delayed_confirmation_is_visible_only_at_confirmation_row():
    out = _classes([(5, "HIGH", 1, 100.0)], length=7)
    assert (out.loc[:4, "structure_event_type"] == "NONE").all()
    assert (out.loc[:4, "swing_sequence_class"] == "NONE").all()
    assert out.loc[5, "structure_event_type"] == "HIGH"
    assert out.loc[5, "current_structure_origin_position"] == 1
    assert out.loc[5, "current_structure_confirmation_position"] == 5
    assert pd.isna(out.loc[1, "current_structure_origin_position"])


def test_non_event_rows_are_none_and_not_forward_filled():
    out = _classes(
        [(1, "HIGH", 0, 100.0), (4, "HIGH", 3, 110.0)], length=7
    )
    for row in (0, 2, 3, 5, 6):
        assert out.loc[row, "structure_event_type"] == "NONE"
        assert out.loc[row, "swing_sequence_class"] == "NONE"
        assert not out.loc[row, "comparison_available"]
        assert math.isnan(out.loc[row, "current_structure_swing_price"])
        assert pd.isna(out.loc[row, "current_structure_origin_position"])


def test_hand_calculated_log_change_and_nonpositive_behavior():
    out = _classes(
        [
            (1, "HIGH", 0, 100.0),
            (2, "HIGH", 1, 110.0),
            (3, "LOW", 0, 0.0),
            (4, "LOW", 1, -1.0),
            (5, "HIGH", 2, 110.0),
        ],
        length=6,
    )
    assert out.loc[2, "same_type_log_price_change"] == math.log(110.0) - math.log(100.0)
    assert math.isnan(out.loc[4, "same_type_log_price_change"])
    assert out.loc[5, "same_type_log_price_change"] == 0.0
    assert out.loc[5, "swing_sequence_class"] == "EH"


def test_positive_scale_invariance():
    events = [
        (1, "HIGH", 0, 100.0),
        (2, "LOW", 0, 90.0),
        (4, "HIGH", 3, 110.0),
        (6, "LOW", 5, 80.0),
    ]
    base_df = _event_frame(7, events)
    scaled_df = base_df.copy(deep=True)
    scaled_df["swing_price"] *= 8.0

    base = ConfirmedSwingSequenceEngine().analyze(base_df)
    scaled = ConfirmedSwingSequenceEngine().analyze(scaled_df)

    pd.testing.assert_series_equal(
        base["swing_sequence_class"], scaled["swing_sequence_class"], check_exact=True
    )
    mask = base["comparison_available"]
    np.testing.assert_allclose(
        base.loc[mask, "same_type_log_price_change"],
        scaled.loc[mask, "same_type_log_price_change"],
        rtol=0.0,
        atol=1e-15,
    )


def test_future_mutation_and_append_preserve_prefix_exact():
    events = [
        (1, "HIGH", 0, 100.0),
        (2, "LOW", 0, 90.0),
        (5, "HIGH", 4, 110.0),
        (7, "LOW", 6, 95.0),
    ]
    df = _event_frame(10, events)
    engine = ConfirmedSwingSequenceEngine()
    full = engine.analyze(df)
    split = 5

    mutated = df.copy(deep=True)
    mutated.loc[5, "swing_price"] = 10_000.0
    mutated.loc[7, "swing_price"] = -10_000.0
    mutated_out = engine.analyze(mutated)
    pd.testing.assert_frame_equal(
        full.iloc[:split], mutated_out.iloc[:split], check_exact=True
    )

    future = _event_frame(3, [])
    future.index = pd.RangeIndex(len(df), len(df) + len(future))
    appended = pd.concat([df, future])
    appended_out = engine.analyze(appended)
    pd.testing.assert_frame_equal(full, appended_out.iloc[: len(df)], check_exact=True)


def test_module_01_truncation_and_state_isolation():
    df_a = _event_frame(
        10,
        [(1, "HIGH", 0, 100.0), (2, "LOW", 0, 90.0),
         (5, "HIGH", 4, 110.0), (7, "LOW", 6, 95.0)],
    )
    df_b = _event_frame(
        11,
        [(1, "LOW", 0, 80.0), (4, "LOW", 3, 70.0), (8, "HIGH", 6, 120.0)],
    )

    truncation = verify_truncation_invariance(
        _SwingSequenceAuditEngine,
        df_a,
        additional_split_points=[1, 2, 3, 5, 8, 9],
    )
    assert all(item.passed for item in truncation)

    state = verify_state_isolation(
        _SwingSequenceAuditEngine,
        df_a,
        df_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed


def test_both_high_and_low_same_row_rejected():
    df = _event_frame(2, [(1, "HIGH", 0, 100.0)])
    df.loc[1, "swing_low_confirmed"] = True
    with pytest.raises(SwingSequenceDataError, match="simultaneously"):
        ConfirmedSwingSequenceEngine().analyze(df)


def test_missing_or_nonfinite_swing_price_rejected_on_event():
    for value in (np.nan, np.inf, -np.inf):
        df = _event_frame(2, [(1, "HIGH", 0, 100.0)])
        df.loc[1, "swing_price"] = value
        with pytest.raises(SwingSequenceDataError, match="swing_price"):
            ConfirmedSwingSequenceEngine().analyze(df)


@pytest.mark.parametrize(
    "column",
    ["swing_origin_position", "swing_confirmation_position"],
)
def test_missing_event_position_metadata_rejected(column):
    df = _event_frame(3, [(2, "HIGH", 0, 100.0)])
    df.loc[2, column] = pd.NA
    with pytest.raises(SwingSequenceDataError, match="missing"):
        ConfirmedSwingSequenceEngine().analyze(df)


def test_confirmation_position_must_equal_current_row():
    df = _event_frame(3, [(2, "HIGH", 0, 100.0)])
    df.loc[2, "swing_confirmation_position"] = 1
    with pytest.raises(SwingSequenceDataError, match="must equal"):
        ConfirmedSwingSequenceEngine().analyze(df)


def test_origin_after_confirmation_rejected():
    df = _event_frame(4, [(2, "HIGH", 0, 100.0)])
    df.loc[2, "swing_origin_position"] = 3
    with pytest.raises(SwingSequenceDataError, match="origin after confirmation"):
        ConfirmedSwingSequenceEngine().analyze(df)


@pytest.mark.parametrize("origin", [-1, 10, 1.5])
def test_invalid_origin_position_rejected(origin):
    df = _event_frame(3, [(2, "HIGH", 0, 100.0)])
    if isinstance(origin, float):
        df["swing_origin_position"] = df["swing_origin_position"].astype("Float64")
    df.loc[2, "swing_origin_position"] = origin
    with pytest.raises(SwingSequenceDataError, match="origin|non-integer"):
        ConfirmedSwingSequenceEngine().analyze(df)


def test_event_flag_and_metadata_dtype_validation():
    df = _event_frame(2, [(1, "HIGH", 0, 100.0)])
    df["swing_high_confirmed"] = df["swing_high_confirmed"].astype(int)
    with pytest.raises(SwingSequenceDataError, match="must be boolean"):
        ConfirmedSwingSequenceEngine().analyze(df)

    bad_price_dtype = _event_frame(2, [(1, "HIGH", 0, 100.0)])
    bad_price_dtype["swing_price"] = bad_price_dtype["swing_price"].astype(str)
    with pytest.raises(SwingSequenceDataError, match="numeric dtype"):
        ConfirmedSwingSequenceEngine().analyze(bad_price_dtype)


def test_empty_dataframe_behavior():
    empty = _event_frame(0, [])
    out = ConfirmedSwingSequenceEngine().analyze(empty)
    assert out.empty
    assert out.columns[-9:].tolist() == [
        "structure_event_type",
        "swing_sequence_class",
        "comparison_available",
        "previous_same_type_price",
        "previous_same_type_origin_position",
        "current_structure_swing_price",
        "current_structure_origin_position",
        "current_structure_confirmation_position",
        "same_type_log_price_change",
    ]


def test_duplicate_nonmonotonic_index_duplicate_columns_and_collision_rejected():
    duplicate_index = _event_frame(2, [])
    duplicate_index.index = [1, 1]
    with pytest.raises(SwingSequenceDataError, match="Duplicate index"):
        ConfirmedSwingSequenceEngine().analyze(duplicate_index)

    unordered = _event_frame(2, [])
    unordered.index = [2, 1]
    with pytest.raises(SwingSequenceDataError, match="monotonic increasing"):
        ConfirmedSwingSequenceEngine().analyze(unordered)

    duplicate_columns = _event_frame(1, [])
    duplicate_columns.insert(0, "dup", 1)
    duplicate_columns.columns = ["dup"] + list(duplicate_columns.columns[1:-1]) + ["dup"]
    with pytest.raises(SwingSequenceDataError, match="Duplicate input columns"):
        ConfirmedSwingSequenceEngine().analyze(duplicate_columns)

    collision = _event_frame(1, [])
    collision["structure_event_type"] = "NONE"
    with pytest.raises(SwingSequenceDataError, match="would be overwritten"):
        ConfirmedSwingSequenceEngine().analyze(collision)


def test_input_not_mutated_and_index_preserved_exactly():
    index = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC", name="time")
    df = _event_frame(5, [(3, "HIGH", 1, 100.0)])
    df.index = index
    before = df.copy(deep=True)
    out = ConfirmedSwingSequenceEngine().analyze(df)
    pd.testing.assert_frame_equal(df, before, check_exact=True)
    assert out.index.equals(df.index)
    assert out.index.freq == df.index.freq
    assert out.index.name == "time"


def _real_swing_input():
    return pd.DataFrame(
        {
            "high": [10.0, 11.0, 10.8, 10.6, 10.8, 12.0, 11.8, 11.6, 11.4],
            "low": [9.0, 10.0, 10.5, 10.0, 10.1, 11.0, 11.5, 11.0, 11.2],
        }
    )


def _real_policy():
    return EmpiricalConfirmationPolicy(
        quantile=0.5,
        prior_continuation_reversals=(0.005, 0.01),
    )


def test_real_21a_to_21b_integration_schema_timing_and_classes():
    raw = _real_swing_input()
    swings = CausalAdaptiveSwingDetector(_real_policy()).analyze(raw)
    out = ConfirmedSwingSequenceEngine().analyze(swings)

    event_rows = np.flatnonzero(
        out["swing_high_confirmed"].to_numpy()
        | out["swing_low_confirmed"].to_numpy()
    ).tolist()
    assert event_rows == [2, 4, 6, 8]
    assert out.loc[event_rows, "structure_event_type"].tolist() == [
        "HIGH", "LOW", "HIGH", "LOW"
    ]
    assert out.loc[event_rows, "swing_sequence_class"].tolist() == [
        "UNCLASSIFIED", "UNCLASSIFIED", "HH", "HL"
    ]
    assert (out.loc[[1, 3, 5, 7], "structure_event_type"] == "NONE").all()
    assert out.loc[2, "current_structure_origin_position"] == 1
    assert out.loc[4, "current_structure_origin_position"] == 3
    assert out.loc[6, "current_structure_origin_position"] == 5
    assert out.loc[8, "current_structure_origin_position"] == 7


def test_real_21a_to_21b_end_to_end_truncation():
    class EndToEndEngine:
        def analyze(self, df, **kwargs):
            swings = CausalAdaptiveSwingDetector(_real_policy()).analyze(df)
            return ConfirmedSwingSequenceEngine().analyze(swings)

    raw = _real_swing_input()
    results = verify_truncation_invariance(
        EndToEndEngine,
        raw,
        split_fractions=(),
        additional_split_points=[1, 2, 3, 4, 5, 6, 7, 8],
    )
    assert all(item.passed for item in results)


def test_textual_guard_secondary_only():
    module = __import__("trading_system.structure.swing_sequence", fromlist=["*"])
    source = inspect.getsource(module)
    forbidden = [
        "shift(-1", "center=True", "rolling(", "future pivot",
        "percentile threshold", "ATR multiplier", "BOS", "CHoCH",
    ]
    for token in forbidden:
        assert token not in source

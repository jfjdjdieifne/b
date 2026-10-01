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
from trading_system.structure.structural_breaks import (
    CausalStructuralBreakEngine,
    StructuralBreakDataError,
    _StructuralBreakAuditEngine,
)
from trading_system.structure.swing_detector import (
    CausalAdaptiveSwingDetector,
    EmpiricalConfirmationPolicy,
)
from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine


def _event_surface(length, events):
    high_flags = np.zeros(length, dtype=bool)
    low_flags = np.zeros(length, dtype=bool)
    origins = pd.array([pd.NA] * length, dtype="Int64")
    prices = np.full(length, np.nan)
    confirmations = pd.array([pd.NA] * length, dtype="Int64")
    for row, event_type, origin, price in events:
        if event_type == "HIGH":
            high_flags[row] = True
        else:
            low_flags[row] = True
        origins[row] = origin
        prices[row] = price
        confirmations[row] = row
    event_df = pd.DataFrame(
        {
            "swing_high_confirmed": high_flags,
            "swing_low_confirmed": low_flags,
            "swing_origin_position": origins,
            "swing_price": prices,
            "swing_confirmation_position": confirmations,
        }
    )
    return ConfirmedSwingSequenceEngine().analyze(event_df)


def _frame(ohlc, events):
    market = pd.DataFrame(
        ohlc, columns=["high", "low", "close"], dtype="float64"
    )
    sequence = _event_surface(len(market), events)
    return pd.concat([market, sequence], axis=1)


def test_level_invisible_before_and_on_confirmation_row():
    df = _frame(
        [
            (100.0, 90.0, 95.0),
            (110.0, 90.0, 100.0),
            (115.0, 95.0, 105.0),
            (120.0, 90.0, 110.0),  # confirms HIGH=100 here
            (101.0, 99.0, 100.0),
        ],
        [(3, "HIGH", 0, 100.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)

    assert out.loc[:3, "monitored_high_price"].isna().all()
    assert not out.loc[:3, "high_wick_breach_event"].any()
    assert not out.loc[:3, "high_close_breach_event"].any()
    assert out.loc[4, "monitored_high_price"] == 100.0


def test_exact_touch_is_not_breach():
    df = _frame(
        [(99.0, 90.0, 95.0), (100.0, 90.0, 99.0), (100.0, 95.0, 100.0)],
        [(1, "HIGH", 0, 100.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)
    assert not out.loc[2, "high_wick_breach_event"]
    assert not out.loc[2, "high_close_breach_event"]


def test_high_wick_only_then_later_first_close_exactly_once():
    df = _frame(
        [
            (99.0, 90.0, 95.0),
            (100.0, 95.0, 99.0),
            (101.0, 98.0, 100.0),
            (102.0, 99.0, 101.0),
            (103.0, 100.0, 102.0),
        ],
        [(1, "HIGH", 0, 100.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)

    assert out.loc[2, "high_wick_breach_event"]
    assert not out.loc[2, "high_close_breach_event"]
    assert out.loc[2, "high_wick_only_breach_event"]
    assert out.loc[2, "high_wick_overshoot_fraction"] == 0.01

    assert not out.loc[3, "high_wick_breach_event"]
    assert out.loc[3, "high_close_breach_event"]
    assert out.loc[3, "high_close_overshoot_fraction"] == 0.01
    assert out.loc[3, "monitored_high_first_wick_breach_position"] == 2
    assert out.loc[3, "monitored_high_first_close_breach_position"] == 3

    assert not out.loc[4, "high_wick_breach_event"]
    assert not out.loc[4, "high_close_breach_event"]
    assert out.loc[4, "monitored_high_wick_breached"]
    assert out.loc[4, "monitored_high_close_breached"]


def test_low_wick_only_then_later_first_close_exactly_once():
    df = _frame(
        [
            (110.0, 101.0, 105.0),
            (105.0, 100.0, 101.0),
            (102.0, 99.0, 100.0),
            (101.0, 98.0, 99.0),
            (100.0, 97.0, 98.0),
        ],
        [(1, "LOW", 0, 100.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)

    assert out.loc[2, "low_wick_breach_event"]
    assert not out.loc[2, "low_close_breach_event"]
    assert out.loc[2, "low_wick_only_breach_event"]
    assert out.loc[2, "low_wick_overshoot_fraction"] == 0.01
    assert out.loc[3, "low_close_breach_event"]
    assert out.loc[3, "low_close_overshoot_fraction"] == 0.01
    assert not out.loc[4, "low_wick_breach_event"]
    assert not out.loc[4, "low_close_breach_event"]


def test_new_same_type_level_replaces_old_only_after_current_row():
    df = _frame(
        [
            (99.0, 90.0, 95.0),
            (100.0, 95.0, 99.0),
            (101.0, 98.0, 100.0),
            (110.0, 105.0, 108.0),  # confirms new HIGH=110
            (111.0, 109.0, 110.0),
        ],
        [(1, "HIGH", 0, 100.0), (3, "HIGH", 2, 110.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)

    assert out.loc[2, "monitored_high_price"] == 100.0
    assert out.loc[2, "high_wick_breach_event"]
    # Row 3 still evaluates old level before installing new one.
    assert out.loc[3, "monitored_high_price"] == 100.0
    assert out.loc[3, "monitored_high_first_wick_breach_position"] == 2
    # The latest structural reference replaces (does not registry-retain) the
    # old level starting on the subsequent row.
    assert out.loc[4, "monitored_high_price"] == 110.0
    assert out.loc[4, "monitored_high_origin_position"] == 2
    assert out.loc[4, "monitored_high_confirmation_position"] == 3
    assert out.loc[4, "monitored_high_first_wick_breach_position"] == 4
    assert out.loc[4, "monitored_high_first_wick_breach_position"] != 2


def test_positional_outputs_use_direct_nullable_integer_dtype():
    df = _frame(
        [(99, 90, 95), (100, 95, 99), (101, 98, 100)],
        [(1, "HIGH", 0, 100.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)
    columns = [
        "monitored_high_origin_position",
        "monitored_high_confirmation_position",
        "monitored_high_first_wick_breach_position",
        "monitored_high_first_close_breach_position",
        "monitored_low_origin_position",
        "monitored_low_confirmation_position",
        "monitored_low_first_wick_breach_position",
        "monitored_low_first_close_breach_position",
    ]
    assert all(str(out[column].dtype) == "Int64" for column in columns)


def test_zero_level_magnitude_nan_without_epsilon():
    df = _frame(
        [(-0.1, -1.0, -0.5), (0.0, -1.0, -0.5), (1.0, -1.0, 0.0)],
        [(1, "HIGH", 0, 0.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)
    assert out.loc[2, "high_wick_breach_event"]
    assert math.isnan(out.loc[2, "high_wick_overshoot_fraction"])
    assert math.isnan(out.loc[2, "high_wick_break_evidence"])
    assert out.loc[2, "wick_break_history_count"] == 0


def test_empirical_read_before_push_and_one_observation_per_first_event():
    df = _frame(
        [
            (99.0, 90.0, 95.0),
            (100.0, 95.0, 99.0),
            (101.0, 98.0, 100.0),  # first wick .01
            (102.0, 99.0, 101.0),  # first close .01
            (110.0, 109.0, 109.5), # replacement HIGH=110
            (112.0, 109.0, 110.0), # first wick 2/110
            (112.0, 109.0, 111.0), # first close 1/110
            (113.0, 109.0, 112.0), # no repeats
        ],
        [(1, "HIGH", 0, 100.0), (4, "HIGH", 3, 110.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)

    assert math.isnan(out.loc[2, "high_wick_break_evidence"])
    assert out.loc[2, "wick_break_history_count"] == 0
    assert math.isnan(out.loc[3, "high_close_break_evidence"])
    assert out.loc[3, "close_break_history_count"] == 0

    assert out.loc[5, "wick_break_history_count"] == 1
    assert out.loc[5, "high_wick_break_evidence"] == 1.0
    assert out.loc[6, "close_break_history_count"] == 1
    assert out.loc[6, "high_close_break_evidence"] == 0.0
    assert out.loc[7, "wick_break_history_count"] == 2
    assert out.loc[7, "close_break_history_count"] == 2
    assert not out.loc[7, "high_wick_breach_event"]
    assert not out.loc[7, "high_close_breach_event"]


def test_wick_evidence_includes_first_wick_when_same_bar_also_closes_beyond():
    df = _frame(
        [
            (99, 90, 95),
            (100, 95, 99),
            (102, 99, 101),   # first wick + first close beyond HIGH=100
            (110, 109, 109.5),
            (112, 109, 111),  # first wick + first close beyond HIGH=110
            (111, 109, 110),
        ],
        [(1, "HIGH", 0, 100.0), (3, "HIGH", 2, 110.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)

    assert out.loc[2, "high_wick_breach_event"]
    assert out.loc[2, "high_close_breach_event"]
    assert not out.loc[2, "high_wick_only_breach_event"]
    assert math.isnan(out.loc[2, "high_wick_break_evidence"])

    # The row-2 wick overshoot entered wick history despite also closing beyond.
    assert out.loc[4, "wick_break_history_count"] == 1
    assert out.loc[4, "high_wick_breach_event"]
    assert out.loc[4, "high_close_breach_event"]
    assert out.loc[4, "high_wick_break_evidence"] == 0.0
    assert out.loc[5, "wick_break_history_count"] == 2


def _up_structure_frame(last_bar):
    ohlc = [
        (98.0, 85.0, 90.0),
        (100.0, 95.0, 98.0),
        (98.0, 90.0, 92.0),
        (110.0, 95.0, 105.0),
        (105.0, 95.0, 100.0),
        last_bar,
    ]
    events = [
        (1, "HIGH", 0, 100.0),
        (2, "LOW", 0, 90.0),
        (3, "HIGH", 2, 110.0),
        (4, "LOW", 3, 95.0),
    ]
    return _frame(ohlc, events)


def _down_structure_frame(last_bar):
    ohlc = [
        (98.0, 85.0, 90.0),
        (100.0, 95.0, 98.0),
        (98.0, 90.0, 92.0),
        (95.0, 85.0, 90.0),
        (90.0, 80.0, 85.0),
        last_bar,
    ]
    events = [
        (1, "HIGH", 0, 100.0),
        (2, "LOW", 0, 90.0),
        (3, "HIGH", 2, 95.0),
        (4, "LOW", 3, 80.0),
    ]
    return _frame(ohlc, events)


def test_structure_state_transition_table_up_down_mixed_undefined_and_equality():
    up = CausalStructuralBreakEngine().analyze(_up_structure_frame((109.0, 96.0, 100.0)))
    assert up.loc[3, "structure_state_after"] == "UNDEFINED"
    assert up.loc[4, "structure_state_before"] == "UNDEFINED"
    assert up.loc[4, "structure_state_after"] == "UP_STRUCTURE"

    down = CausalStructuralBreakEngine().analyze(
        _down_structure_frame((94.0, 81.0, 85.0))
    )
    assert down.loc[4, "structure_state_after"] == "DOWN_STRUCTURE"

    mixed = _frame(
        [(98, 85, 90), (100, 95, 98), (98, 90, 92), (110, 95, 105), (100, 80, 90)],
        [(1, "HIGH", 0, 100.0), (2, "LOW", 0, 90.0),
         (3, "HIGH", 2, 110.0), (4, "LOW", 3, 80.0)],
    )
    mixed_out = CausalStructuralBreakEngine().analyze(mixed)
    assert mixed_out.loc[4, "structure_state_after"] == "MIXED"

    equal = _frame(
        [(98, 85, 90), (100, 95, 98), (98, 90, 92), (100, 95, 98), (98, 90, 92)],
        [(1, "HIGH", 0, 100.0), (2, "LOW", 0, 90.0),
         (3, "HIGH", 2, 100.0), (4, "LOW", 3, 90.0)],
    )
    equal_out = CausalStructuralBreakEngine().analyze(equal)
    assert equal_out.loc[3, "structure_state_after"] == "UNDEFINED"
    assert equal_out.loc[4, "structure_state_after"] == "MIXED"


def test_up_structure_interpretations():
    bos = CausalStructuralBreakEngine().analyze(
        _up_structure_frame((112.0, 100.0, 111.0))
    )
    assert bos.loc[5, "high_close_breach_event"]
    assert bos.loc[5, "structure_state_before"] == "UP_STRUCTURE"
    assert bos.loc[5, "structural_break_event"] == "BOS_UP"

    choch = CausalStructuralBreakEngine().analyze(
        _up_structure_frame((100.0, 90.0, 94.0))
    )
    assert choch.loc[5, "low_close_breach_event"]
    assert choch.loc[5, "structural_break_event"] == "CHOCH_DOWN"


def test_down_structure_interpretations():
    bos = CausalStructuralBreakEngine().analyze(
        _down_structure_frame((79.0, 70.0, 75.0))
    )
    assert bos.loc[5, "low_close_breach_event"]
    assert bos.loc[5, "structural_break_event"] == "BOS_DOWN"

    choch = CausalStructuralBreakEngine().analyze(
        _down_structure_frame((100.0, 90.0, 96.0))
    )
    assert choch.loc[5, "high_close_breach_event"]
    assert choch.loc[5, "structural_break_event"] == "CHOCH_UP"


def test_undefined_and_mixed_breaks_are_unclassified():
    undefined = _frame(
        [(99, 90, 95), (100, 95, 98), (102, 99, 101)],
        [(1, "HIGH", 0, 100.0)],
    )
    undefined_out = CausalStructuralBreakEngine().analyze(undefined)
    assert undefined_out.loc[2, "structural_break_event"] == "UNCLASSIFIED_BREAK"

    mixed = _frame(
        [
            (98, 85, 90), (100, 95, 98), (98, 90, 92),
            (110, 95, 105), (100, 80, 90), (112, 85, 111),
        ],
        [(1, "HIGH", 0, 100.0), (2, "LOW", 0, 90.0),
         (3, "HIGH", 2, 110.0), (4, "LOW", 3, 80.0)],
    )
    mixed_out = CausalStructuralBreakEngine().analyze(mixed)
    assert mixed_out.loc[5, "structure_state_before"] == "MIXED"
    assert mixed_out.loc[5, "structural_break_event"] == "UNCLASSIFIED_BREAK"


def test_same_bar_sequence_update_does_not_reinterpret_prior_level_break():
    df = _frame(
        [
            (98, 85, 90),
            (100, 95, 98),
            (98, 90, 92),
            (110, 95, 105),
            (112, 95, 111),  # HL event also closes above prior HIGH=110
        ],
        [(1, "HIGH", 0, 100.0), (2, "LOW", 0, 90.0),
         (3, "HIGH", 2, 110.0), (4, "LOW", 3, 95.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)
    assert out.loc[4, "structure_state_before"] == "UNDEFINED"
    assert out.loc[4, "high_close_breach_event"]
    assert out.loc[4, "structural_break_event"] == "UNCLASSIFIED_BREAK"
    assert out.loc[4, "structure_state_after"] == "UP_STRUCTURE"
    # Newly confirmed LOW=95 is not monitored/broken on its confirmation row.
    assert not out.loc[4, "low_close_breach_event"]


def test_ambiguous_double_close_break_preserves_raw_sides():
    df = _frame(
        [
            (89, 80, 85),
                (90, 85, 88),   # HIGH level 90
                (89, 80, 85),   # installs inverted LOW level 100; no old-HIGH break
                (105, 85, 95),  # close >90 and <100
                (95, 90, 92),   # both first observations are now in history
            ],
        [(1, "HIGH", 0, 90.0), (2, "LOW", 0, 100.0)],
    )
    out = CausalStructuralBreakEngine().analyze(df)
    assert out.loc[3, "high_close_breach_event"]
    assert out.loc[3, "low_close_breach_event"]
    assert out.loc[3, "high_wick_breach_event"]
    assert out.loc[3, "low_wick_breach_event"]
    assert out.loc[3, "structural_break_event"] == "AMBIGUOUS_DOUBLE_BREAK"
    assert out.loc[3, "wick_break_history_count"] == 0
    assert out.loc[3, "close_break_history_count"] == 0
    assert math.isnan(out.loc[3, "high_wick_break_evidence"])
    assert math.isnan(out.loc[3, "low_wick_break_evidence"])
    assert out.loc[4, "wick_break_history_count"] == 2
    assert out.loc[4, "close_break_history_count"] == 2


def test_positive_scale_invariance():
    events = [(1, "HIGH", 0, 100.0), (4, "HIGH", 3, 110.0)]
    ohlc = [
        (99, 90, 95), (100, 95, 99), (101, 98, 100),
        (102, 99, 101), (110, 109, 109.5), (112, 109, 111),
    ]
    base_df = _frame(ohlc, events)
    scaled_events = [(row, typ, origin, price * 8.0) for row, typ, origin, price in events]
    scaled_ohlc = [tuple(value * 8.0 for value in row) for row in ohlc]
    scaled_df = _frame(scaled_ohlc, scaled_events)

    base = CausalStructuralBreakEngine().analyze(base_df)
    scaled = CausalStructuralBreakEngine().analyze(scaled_df)

    invariant = [
        "high_wick_breach_event", "high_close_breach_event",
        "low_wick_breach_event", "low_close_breach_event",
        "structural_break_event", "structure_state_before", "structure_state_after",
        "high_wick_overshoot_fraction", "high_close_overshoot_fraction",
        "high_wick_break_evidence", "high_close_break_evidence",
    ]
    for column in invariant:
        pd.testing.assert_series_equal(base[column], scaled[column], check_exact=True)


def test_future_mutation_append_truncation_and_state_isolation():
    df_a = _up_structure_frame((112.0, 100.0, 111.0))
    full = CausalStructuralBreakEngine().analyze(df_a)
    split = 5
    mutated = df_a.copy(deep=True)
    mutated.loc[5, ["high", "low", "close"]] = [1000.0, 900.0, 950.0]
    mutated_out = CausalStructuralBreakEngine().analyze(mutated)
    pd.testing.assert_frame_equal(
        full.iloc[:split], mutated_out.iloc[:split], check_exact=True
    )

    future = _frame([(120, 110, 115), (121, 111, 116)], [])
    future.index = pd.RangeIndex(len(df_a), len(df_a) + len(future))
    appended = pd.concat([df_a, future])
    appended_out = CausalStructuralBreakEngine().analyze(appended)
    pd.testing.assert_frame_equal(full, appended_out.iloc[: len(df_a)], check_exact=True)

    truncation = verify_truncation_invariance(
        _StructuralBreakAuditEngine,
        df_a,
        split_fractions=(),
        additional_split_points=[1, 2, 3, 4, 5],
    )
    assert all(item.passed for item in truncation)

    df_b = _down_structure_frame((79.0, 70.0, 75.0))
    state = verify_state_isolation(
        _StructuralBreakAuditEngine,
        df_a,
        df_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed


def test_malformed_ohlc_rejected():
    valid = _frame([(100, 90, 95)], [])
    cases = []
    high_low = valid.copy(); high_low.loc[0, ["high", "low"]] = [80, 90]; cases.append(high_low)
    close_high = valid.copy(); close_high.loc[0, "close"] = 101; cases.append(close_high)
    close_low = valid.copy(); close_low.loc[0, "close"] = 89; cases.append(close_low)
    nan_case = valid.copy(); nan_case.loc[0, "high"] = np.nan; cases.append(nan_case)
    inf_case = valid.copy(); inf_case.loc[0, "low"] = -np.inf; cases.append(inf_case)

    for case in cases:
        with pytest.raises(StructuralBreakDataError):
            CausalStructuralBreakEngine().analyze(case)


def test_malformed_upstream_event_surface_rejected_directly():
    df = _frame([(99, 90, 95), (100, 95, 98)], [(1, "HIGH", 0, 100.0)])
    df.loc[1, "swing_sequence_class"] = "HH"  # first HIGH must be UNCLASSIFIED
    with pytest.raises(StructuralBreakDataError, match="First same-type"):
        CausalStructuralBreakEngine().analyze(df)

    missing = _frame([(99, 90, 95), (100, 95, 98)], [(1, "HIGH", 0, 100.0)])
    missing.loc[1, "swing_origin_position"] = pd.NA
    with pytest.raises(StructuralBreakDataError, match="missing swing_origin_position"):
        CausalStructuralBreakEngine().analyze(missing)

    inconsistent = _frame(
        [(99, 90, 95), (100, 95, 98)], [(1, "HIGH", 0, 100.0)]
    )
    inconsistent.loc[1, "current_structure_swing_price"] = 101.0
    with pytest.raises(StructuralBreakDataError, match="current_structure metadata"):
        CausalStructuralBreakEngine().analyze(inconsistent)

    invalid_type = _frame(
        [(99, 90, 95), (100, 95, 98)], [(1, "HIGH", 0, 100.0)]
    )
    invalid_type.loc[1, "structure_event_type"] = "SIDEWAYS"
    with pytest.raises(StructuralBreakDataError, match="invalid structure_event_type"):
        CausalStructuralBreakEngine().analyze(invalid_type)

    simultaneous = _frame(
        [(99, 90, 95), (100, 95, 98)], [(1, "HIGH", 0, 100.0)]
    )
    simultaneous.loc[1, "swing_low_confirmed"] = True
    with pytest.raises(StructuralBreakDataError, match="simultaneously"):
        CausalStructuralBreakEngine().analyze(simultaneous)


def test_production_does_not_run_confirmed_sequence_engine(monkeypatch):
    valid = _frame([(99, 90, 95), (100, 95, 98)], [(1, "HIGH", 0, 100.0)])

    def forbidden_recompute(*args, **kwargs):
        raise AssertionError("2.1B production recomputation is forbidden")

    monkeypatch.setattr(ConfirmedSwingSequenceEngine, "analyze", forbidden_recompute)
    out = CausalStructuralBreakEngine().analyze(valid)
    assert out.loc[1, "structure_state_after"] == "UNDEFINED"

    malformed = valid.copy(deep=True)
    malformed.loc[1, "structure_event_type"] = "LOW"
    with pytest.raises(StructuralBreakDataError, match="correspondence"):
        CausalStructuralBreakEngine().analyze(malformed)


def test_empty_and_one_row_input_and_immutability():
    empty = _frame([], [])
    empty_out = CausalStructuralBreakEngine().analyze(empty)
    assert empty_out.empty
    assert "structural_break_event" in empty_out

    one = _frame([(100, 90, 95)], [])
    before = one.copy(deep=True)
    one_out = CausalStructuralBreakEngine().analyze(one)
    pd.testing.assert_frame_equal(one, before, check_exact=True)
    assert one_out.loc[0, "structure_state_before"] == "UNDEFINED"
    assert one_out.loc[0, "structural_break_event"] == "NONE"


def test_duplicate_nonmonotonic_index_duplicate_columns_and_output_collision():
    duplicate_index = _frame([(100, 90, 95), (101, 91, 96)], [])
    duplicate_index.index = [1, 1]
    with pytest.raises(StructuralBreakDataError, match="Duplicate index"):
        CausalStructuralBreakEngine().analyze(duplicate_index)

    unordered = _frame([(100, 90, 95), (101, 91, 96)], [])
    unordered.index = [2, 1]
    with pytest.raises(StructuralBreakDataError, match="monotonic"):
        CausalStructuralBreakEngine().analyze(unordered)

    duplicate_columns = _frame([(100, 90, 95)], [])
    duplicate_columns.insert(0, "dup", 1)
    duplicate_columns.columns = ["dup"] + list(duplicate_columns.columns[1:-1]) + ["dup"]
    with pytest.raises(StructuralBreakDataError, match="Duplicate input columns"):
        CausalStructuralBreakEngine().analyze(duplicate_columns)

    collision = _frame([(100, 90, 95)], [])
    collision["structural_break_event"] = "NONE"
    with pytest.raises(StructuralBreakDataError, match="would be overwritten"):
        CausalStructuralBreakEngine().analyze(collision)


def _real_raw():
    high = [10.0, 11.0, 10.8, 10.6, 10.8, 12.0, 11.8, 11.6, 11.4]
    low = [9.0, 10.0, 10.5, 10.0, 10.1, 11.0, 11.5, 11.0, 11.2]
    close = [(h + l) / 2.0 for h, l in zip(high, low)]
    return pd.DataFrame({"high": high, "low": low, "close": close})


def _real_chain(df):
    policy = EmpiricalConfirmationPolicy(
        quantile=0.5,
        prior_continuation_reversals=(0.005, 0.01),
    )
    swings = CausalAdaptiveSwingDetector(policy).analyze(df[["high", "low"]])
    with_close = swings.copy(deep=True)
    with_close.insert(2, "close", df["close"].to_numpy())
    sequence = ConfirmedSwingSequenceEngine().analyze(with_close)
    return CausalStructuralBreakEngine().analyze(sequence)


def test_real_21a_21b_21c_integration():
    out = _real_chain(_real_raw())
    swing_rows = np.flatnonzero(
        out["swing_high_confirmed"].to_numpy()
        | out["swing_low_confirmed"].to_numpy()
    ).tolist()
    assert swing_rows == [2, 4, 6, 8]
    assert out.loc[swing_rows, "swing_sequence_class"].tolist() == [
        "UNCLASSIFIED", "UNCLASSIFIED", "HH", "HL"
    ]
    assert out.loc[5, "high_close_breach_event"]
    assert out.loc[5, "structural_break_event"] == "UNCLASSIFIED_BREAK"
    assert not out.loc[2, "high_close_breach_event"]
    assert not out.loc[4, "low_close_breach_event"]


def test_end_to_end_chain_truncation_invariance():
    class FullChainEngine:
        def analyze(self, df, **kwargs):
            return _real_chain(df)

    raw = _real_raw()
    results = verify_truncation_invariance(
        FullChainEngine,
        raw,
        split_fractions=(),
        additional_split_points=[1, 2, 3, 4, 5, 6, 7, 8],
    )
    assert all(item.passed for item in results)


def test_textual_guard_secondary_only():
    module = __import__("trading_system.structure.structural_breaks", fromlist=["*"])
    source = inspect.getsource(module)
    forbidden = [
        "shift(-1", "center=True", "rolling(", "ATR multiplier",
        "fixed buffer", "find_peaks", "argrelextrema",
    ]
    for token in forbidden:
        assert token not in source

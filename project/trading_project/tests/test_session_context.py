from datetime import time
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
from trading_system.environment.session_context import (
    CausalSessionContextEngine,
    SessionConfigError,
    SessionContextDataError,
    SessionDefinition,
    _SessionContextAuditEngine,
)


def _session(name, timezone, start, end):
    return SessionDefinition(
        name=name,
        timezone=timezone,
        start_local=start,
        end_local=end,
    )


def _frame(timestamps):
    return pd.DataFrame({"payload": np.arange(len(timestamps))}, index=timestamps)


def test_utc_and_equivalent_non_utc_instants_match():
    session = _session("London", "Europe/London", time(8), time(10))
    engine = CausalSessionContextEngine((session,))

    utc_index = pd.date_range("2024-07-15 06:30", periods=5, freq="30min", tz="UTC")
    ny_index = utc_index.tz_convert("America/New_York")
    utc_out = engine.analyze(_frame(utc_index))
    ny_out = engine.analyze(_frame(ny_index))

    generated = [
        "hour_utc_sin", "hour_utc_cos", "weekday_sin", "weekday_cos",
        "session_london_active", "active_session_count",
    ]
    for column in generated:
        np.testing.assert_array_equal(
            utc_out[column].to_numpy(), ny_out[column].to_numpy()
        )


def test_naive_non_datetime_duplicate_nonmonotonic_and_nat_rejected():
    engine = CausalSessionContextEngine()

    with pytest.raises(SessionContextDataError, match="timezone-aware"):
        engine.analyze(pd.DataFrame(index=pd.Index([1, 2])))

    with pytest.raises(SessionContextDataError, match="Timezone-naive"):
        engine.analyze(pd.DataFrame(index=pd.date_range("2024-01-01", periods=2)))

    duplicate = pd.DatetimeIndex(
        ["2024-01-01 00:00:00+00:00", "2024-01-01 00:00:00+00:00"]
    )
    with pytest.raises(SessionContextDataError, match="Duplicate timestamps"):
        engine.analyze(pd.DataFrame(index=duplicate))

    unordered = pd.DatetimeIndex(
        ["2024-01-02 00:00:00+00:00", "2024-01-01 00:00:00+00:00"]
    )
    with pytest.raises(SessionContextDataError, match="monotonic increasing"):
        engine.analyze(pd.DataFrame(index=unordered))

    with_nat = pd.DatetimeIndex([pd.Timestamp("2024-01-01", tz="UTC"), pd.NaT])
    with pytest.raises(SessionContextDataError, match="NaT"):
        engine.analyze(pd.DataFrame(index=with_nat))


def test_half_open_start_and_end_boundaries():
    session = _session("Boundary", "UTC", time(8), time(9))
    index = pd.DatetimeIndex(
        [
            "2024-01-01 07:59:59.999999+00:00",
            "2024-01-01 08:00:00+00:00",
            "2024-01-01 08:59:59.999999+00:00",
            "2024-01-01 09:00:00+00:00",
        ]
    )
    out = CausalSessionContextEngine((session,)).analyze(pd.DataFrame(index=index))
    assert out["session_boundary_active"].tolist() == [False, True, True, False]


def test_cross_midnight_session_before_and_after_midnight():
    session = _session("Overnight", "UTC", time(22), time(2))
    index = pd.DatetimeIndex(
        [
            "2024-01-01 21:59:00+00:00",
            "2024-01-01 22:00:00+00:00",
            "2024-01-01 23:30:00+00:00",
            "2024-01-02 00:30:00+00:00",
            "2024-01-02 01:59:59+00:00",
            "2024-01-02 02:00:00+00:00",
        ]
    )
    out = CausalSessionContextEngine((session,)).analyze(pd.DataFrame(index=index))
    assert out["session_overnight_active"].tolist() == [
        False, True, True, True, True, False
    ]


def test_overlaps_remain_multi_hot_and_count_is_correct():
    first = _session("First", "UTC", time(8), time(10))
    second = _session("Second", "UTC", time(9), time(11))
    index = pd.DatetimeIndex(
        ["2024-01-01 08:30+00:00", "2024-01-01 09:30+00:00", "2024-01-01 10:30+00:00"]
    )
    out = CausalSessionContextEngine((first, second)).analyze(pd.DataFrame(index=index))

    assert out["session_first_active"].tolist() == [True, True, False]
    assert out["session_second_active"].tolist() == [False, True, True]
    assert out["active_session_count"].tolist() == [1, 2, 1]


def test_london_dst_changes_utc_representation():
    london = _session("London", "Europe/London", time(8), time(9))
    index = pd.DatetimeIndex(
        [
            "2024-01-15 08:30+00:00",  # 08:30 GMT
            "2024-07-15 07:30+00:00",  # 08:30 BST
            "2024-07-15 08:30+00:00",  # 09:30 BST
        ]
    )
    out = CausalSessionContextEngine((london,)).analyze(pd.DataFrame(index=index))
    assert out["session_london_active"].tolist() == [True, True, False]


def test_new_york_dst_changes_utc_representation():
    new_york = _session("New_York", "America/New_York", time(9, 30), time(10))
    index = pd.DatetimeIndex(
        [
            "2024-01-15 14:45+00:00",  # 09:45 EST
            "2024-07-15 13:45+00:00",  # 09:45 EDT
            "2024-07-15 14:45+00:00",  # 10:45 EDT
        ]
    )
    out = CausalSessionContextEngine((new_york,)).analyze(pd.DataFrame(index=index))
    assert out["session_new_york_active"].tolist() == [True, True, False]


def test_us_uk_dst_transition_mismatch_week():
    # On 2024-03-20, the US is already on EDT while the UK remains on GMT.
    london = _session("London", "Europe/London", time(13), time(14))
    new_york = _session("New_York", "America/New_York", time(9, 30), time(10))
    instants = pd.DatetimeIndex(
        [
            "2024-03-06 13:45+00:00",  # London active; NY still 08:45 EST
            "2024-03-20 13:45+00:00",  # London 13:45 GMT; NY 09:45 EDT
            "2024-04-03 13:45+00:00",  # London 14:45 BST; NY 09:45 EDT
        ]
    )
    out = CausalSessionContextEngine((london, new_york)).analyze(
        pd.DataFrame(index=instants)
    )
    assert out["session_london_active"].tolist() == [True, True, False]
    assert out["session_new_york_active"].tolist() == [False, True, True]
    assert out["active_session_count"].tolist() == [1, 2, 1]


def test_future_timestamp_mutation_and_append_leave_prefix_exact():
    session = _session("London", "Europe/London", time(8), time(16))
    engine = CausalSessionContextEngine((session,))
    index = pd.date_range("2024-01-01", periods=257, freq="h", tz="UTC")
    df = _frame(index)
    full = engine.analyze(df)
    split = 128

    mutated_index = index.copy()
    mutated_index = mutated_index[:split].append(mutated_index[split:] + pd.Timedelta(days=100))
    mutated = df.copy()
    mutated.index = mutated_index
    mutated_out = engine.analyze(mutated)
    pd.testing.assert_frame_equal(
        full.iloc[:split], mutated_out.iloc[:split], check_exact=True
    )

    future_index = pd.date_range(index[-1] + pd.Timedelta(hours=1), periods=20, freq="h")
    appended = pd.concat([df, _frame(future_index)])
    appended_out = engine.analyze(appended)
    pd.testing.assert_frame_equal(full, appended_out.iloc[: len(df)], check_exact=True)


def test_module_01_truncation_and_state_isolation():
    london = _session("London", "Europe/London", time(8), time(16))
    new_york = _session("New_York", "America/New_York", time(9, 30), time(16))
    factory = lambda: _SessionContextAuditEngine((london, new_york))

    index_a = pd.date_range("2024-03-01", periods=401, freq="h", tz="UTC")
    index_b = pd.date_range("2024-10-01", periods=409, freq="37min", tz="UTC")
    df_a = _frame(index_a)
    df_b = _frame(index_b)

    truncation = verify_truncation_invariance(
        factory,
        df_a,
        additional_split_points=[1, 2, 17, 127, 256, 400],
    )
    assert all(result.passed for result in truncation)

    state = verify_state_isolation(
        factory,
        df_a,
        df_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert state.passed


def test_original_dataframe_not_mutated():
    session = _session("Test", "UTC", time(1), time(2))
    df = _frame(pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC"))
    before = df.copy(deep=True)
    out = CausalSessionContextEngine((session,)).analyze(df)
    pd.testing.assert_frame_equal(df, before, check_exact=True)
    assert out is not df


def test_empty_timezone_aware_dataframe():
    index = pd.DatetimeIndex([], tz="UTC")
    out = CausalSessionContextEngine().analyze(pd.DataFrame(index=index))
    assert out.empty
    assert out.columns.tolist() == [
        "hour_utc_sin", "hour_utc_cos", "weekday_sin", "weekday_cos",
        "active_session_count",
    ]
    assert str(out["active_session_count"].dtype) == "int64"


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "", None, 42])
def test_invalid_timezone_rejected(timezone):
    with pytest.raises(SessionConfigError):
        _session("Bad", timezone, time(1), time(2))


@pytest.mark.parametrize(
    "name,start,end",
    [
        ("bad name", time(1), time(2)),
        ("1bad", time(1), time(2)),
        ("Same", time(1), time(1)),
        ("BadStart", "01:00", time(2)),
        ("BadEnd", time(1), "02:00"),
        ("Aware", time(1, tzinfo=pd.Timestamp("2024-01-01", tz="UTC").tz), time(2)),
    ],
)
def test_malformed_definition_rejected(name, start, end):
    with pytest.raises(SessionConfigError):
        _session(name, "UTC", start, end)


def test_duplicate_names_and_normalized_output_collision_rejected():
    first = _session("London", "Europe/London", time(8), time(9))
    duplicate = _session("London", "UTC", time(10), time(11))
    with pytest.raises(SessionConfigError, match="Duplicate session names"):
        CausalSessionContextEngine((first, duplicate))

    normalized_collision = _session("LONDON", "UTC", time(10), time(11))
    with pytest.raises(SessionConfigError, match="colliding output"):
        CausalSessionContextEngine((first, normalized_collision))


def test_input_duplicate_columns_and_generated_column_collision_rejected():
    index = pd.date_range("2024-01-01", periods=1, tz="UTC")
    duplicate_columns = pd.DataFrame([[1, 2]], columns=["x", "x"], index=index)
    with pytest.raises(SessionContextDataError, match="Duplicate input columns"):
        CausalSessionContextEngine().analyze(duplicate_columns)

    collision = pd.DataFrame({"hour_utc_sin": [99.0]}, index=index)
    with pytest.raises(SessionContextDataError, match="already exist"):
        CausalSessionContextEngine().analyze(collision)

    session = _session("London", "UTC", time(8), time(9))
    session_collision = pd.DataFrame({"session_london_active": [False]}, index=index)
    with pytest.raises(SessionContextDataError, match="already exist"):
        CausalSessionContextEngine((session,)).analyze(session_collision)


def test_cyclic_calendar_features_known_values_and_periodicity():
    index = pd.DatetimeIndex(
        [
            "2024-01-01 00:00:00+00:00",  # Monday
            "2024-01-01 06:00:00+00:00",
            "2024-01-01 12:00:00+00:00",
            "2024-01-02 00:00:00+00:00",  # Tuesday
            "2024-01-08 00:00:00+00:00",  # next Monday
        ]
    )
    out = CausalSessionContextEngine().analyze(pd.DataFrame(index=index))

    assert out.loc[index[0], "hour_utc_sin"] == 0.0
    assert out.loc[index[0], "hour_utc_cos"] == 1.0
    assert np.isclose(out.loc[index[1], "hour_utc_sin"], 1.0)
    assert np.isclose(out.loc[index[1], "hour_utc_cos"], 0.0, atol=1e-15)
    assert np.isclose(out.loc[index[2], "hour_utc_sin"], 0.0, atol=1e-15)
    assert np.isclose(out.loc[index[2], "hour_utc_cos"], -1.0)
    assert out.loc[index[0], "weekday_sin"] == 0.0
    assert out.loc[index[0], "weekday_cos"] == 1.0
    assert out.loc[index[0], "weekday_sin"] == out.loc[index[4], "weekday_sin"]
    assert out.loc[index[0], "weekday_cos"] == out.loc[index[4], "weekday_cos"]
    assert not math.isclose(
        out.loc[index[0], "weekday_sin"], out.loc[index[3], "weekday_sin"]
    )


def test_no_market_module_dependency_or_trading_score_tokens():
    module = __import__("trading_system.environment.session_context", fromlist=["*"])
    source = inspect.getsource(module)
    forbidden = [
        "dynamic_volatility", "causal_percentile", "causal_adaptive_smoothing",
        "causal_kernels", "killzone_score", "time_confluence_score",
        "london_score", "ny_score",
    ]
    for token in forbidden:
        assert token not in source

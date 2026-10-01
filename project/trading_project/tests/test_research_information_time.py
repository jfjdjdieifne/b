from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from trading_system.research.information_time import (
    INFORMATION_KEY_VERSION,
    InformationKey,
    InformationKeyError,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
    TimelineAdapterError,
    information_time_contract_manifest,
)


def test_information_key_total_phase_and_sequence_order():
    adapter = PositionalTimelineAdapter("timeline")
    index = pd.RangeIndex(2)
    pre = adapter.key_for_position(index, 0, InformationPhase.BAR_PRE_CLOSE, 99)
    completed_0 = adapter.key_for_position(
        index, 0, InformationPhase.COMPLETED_ROW_AVAILABLE, 0
    )
    completed_1 = adapter.key_for_position(
        index, 0, InformationPhase.COMPLETED_ROW_AVAILABLE, 1
    )
    research = adapter.key_for_position(
        index, 0, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, 0
    )
    next_pre = adapter.key_for_position(index, 1, InformationPhase.BAR_PRE_CLOSE, 0)
    assert pre < completed_0 < completed_1 < research < next_pre
    assert completed_0 <= completed_0


def test_cross_timeline_comparison_is_forbidden_for_all_operators():
    index = pd.RangeIndex(1)
    left = PositionalTimelineAdapter("left").key_for_position(
        index, 0, InformationPhase.COMPLETED_ROW_AVAILABLE
    )
    right = PositionalTimelineAdapter("right").key_for_position(
        index, 0, InformationPhase.COMPLETED_ROW_AVAILABLE
    )
    for operation in (
        lambda: left < right,
        lambda: left <= right,
        lambda: left > right,
        lambda: left >= right,
        lambda: left == right,
    ):
        with pytest.raises(InformationKeyError, match="cross-timeline"):
            operation()


def test_equal_normalized_timestamp_all_explicit_operators_and_hash():
    left = InformationKey(
        INFORMATION_KEY_VERSION,
        "time",
        0,
        pd.Timestamp("2025-01-01T00:00:00Z"),
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    right = InformationKey(
        INFORMATION_KEY_VERSION,
        "time",
        0,
        pd.Timestamp("2025-01-01T02:00:00+02:00"),
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    assert left == right
    assert hash(left) == hash(right)
    assert left <= right
    assert left >= right
    assert not left < right
    assert not left > right


def test_conflicting_timestamps_all_explicit_ordering_operators_raise():
    left = InformationKey(
        INFORMATION_KEY_VERSION,
        "time",
        0,
        pd.Timestamp("2025-01-01T00:00:00Z"),
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    right = InformationKey(
        INFORMATION_KEY_VERSION,
        "time",
        0,
        pd.Timestamp("2025-01-01T00:00:01Z"),
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    assert left != right
    for operation in (
        lambda: left < right,
        lambda: left <= right,
        lambda: left > right,
        lambda: left >= right,
    ):
        with pytest.raises(InformationKeyError, match="conflicting timestamp provenance"):
            operation()


def test_timestamp_vs_none_all_explicit_ordering_operators_raise():
    timestamped = InformationKey(
        INFORMATION_KEY_VERSION,
        "time",
        0,
        pd.Timestamp("2025-01-01T00:00:00Z"),
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    positional = InformationKey(
        INFORMATION_KEY_VERSION,
        "time",
        0,
        None,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    assert timestamped != positional
    for operation in (
        lambda: timestamped < positional,
        lambda: timestamped <= positional,
        lambda: timestamped > positional,
        lambda: timestamped >= positional,
    ):
        with pytest.raises(InformationKeyError, match="conflicting timestamp provenance"):
            operation()


def test_different_causal_coordinates_use_normal_positional_ordering():
    index = pd.RangeIndex(2)
    adapter = PositionalTimelineAdapter("timeline")
    left = adapter.key_for_position(
        index, 0, InformationPhase.COMPLETED_ROW_AVAILABLE, 1
    )
    right = adapter.key_for_position(index, 1, InformationPhase.BAR_PRE_CLOSE, 0)
    assert left != right
    assert left < right
    assert left <= right
    assert not left > right
    assert not left >= right
    assert right > left
    assert right >= left


def test_information_key_validation_and_immutability():
    with pytest.raises(InformationKeyError, match="bar_position"):
        InformationKey(
            INFORMATION_KEY_VERSION,
            "timeline",
            -1,
            None,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            0,
        )
    with pytest.raises(InformationKeyError, match="deterministic_sequence"):
        InformationKey(
            INFORMATION_KEY_VERSION,
            "timeline",
            0,
            None,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            -1,
        )
    with pytest.raises(InformationKeyError, match="information phase"):
        InformationKey(INFORMATION_KEY_VERSION, "timeline", 0, None, "BAD", 0)
    key = InformationKey(
        INFORMATION_KEY_VERSION,
        "timeline",
        0,
        None,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        0,
    )
    with pytest.raises(FrozenInstanceError):
        key.bar_position = 1


def test_positional_adapter_uses_row_ordinal_and_no_timestamp():
    adapter = PositionalTimelineAdapter("positional")
    index = pd.Index([10, 20, 30], name="labels")
    key = adapter.key_for_position(
        index, 1, InformationPhase.COMPLETED_ROW_AVAILABLE, 1
    )
    assert key.bar_position == 1
    assert key.event_time_utc is None
    assert key.timeline_id == "positional"
    adapter.validate_key(key, index)


def test_positional_adapter_rejects_datetime_and_bad_index():
    adapter = PositionalTimelineAdapter("positional")
    with pytest.raises(TimelineAdapterError, match="DatetimeIndex"):
        adapter.validate_index(pd.date_range("2025-01-01", periods=2, tz="UTC"))
    with pytest.raises(TimelineAdapterError, match="index contract"):
        adapter.validate_index(pd.Index([1, 1]))
    with pytest.raises(TimelineAdapterError, match="index contract"):
        adapter.validate_index(pd.Index([2, 1]))


def test_time_adapter_requires_timezone_aware_valid_unique_monotonic_index():
    adapter = TimeIndexedTimelineAdapter("time")
    with pytest.raises(TimelineAdapterError, match="timezone-aware"):
        adapter.validate_index(pd.date_range("2025-01-01", periods=2))
    with pytest.raises(TimelineAdapterError, match="NaT"):
        adapter.validate_index(
            pd.DatetimeIndex([pd.Timestamp("2025-01-01", tz="UTC"), pd.NaT])
        )
    duplicate = pd.DatetimeIndex(
        [pd.Timestamp("2025-01-01", tz="UTC")] * 2
    )
    with pytest.raises(TimelineAdapterError, match="duplicate"):
        adapter.validate_index(duplicate)
    nonmonotonic = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-01-02", tz="UTC"),
            pd.Timestamp("2025-01-01", tz="UTC"),
        ]
    )
    with pytest.raises(TimelineAdapterError, match="nonmonotonic"):
        adapter.validate_index(nonmonotonic)


def test_time_adapter_normalizes_to_utc_and_preserves_position():
    adapter = TimeIndexedTimelineAdapter("time")
    index = pd.date_range("2025-01-01", periods=3, tz="Europe/Vilnius")
    key = adapter.key_for_position(
        index, 2, InformationPhase.COMPLETED_ROW_AVAILABLE, 1
    )
    assert key.bar_position == 2
    assert str(key.event_time_utc.tz) == "UTC"
    assert key.event_time_utc == index[2].tz_convert("UTC")
    adapter.validate_key(key, index)


def test_time_adapter_dst_transition_uses_distinct_utc_instants():
    adapter = TimeIndexedTimelineAdapter("dst")
    utc = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-10-26T00:30:00Z"),
            pd.Timestamp("2025-10-26T01:30:00Z"),
            pd.Timestamp("2025-10-26T02:30:00Z"),
        ]
    )
    local = utc.tz_convert("Europe/Vilnius")
    keys = [
        adapter.key_for_position(
            local, position, InformationPhase.COMPLETED_ROW_AVAILABLE
        )
        for position in range(len(local))
    ]
    assert [key.event_time_utc for key in keys] == list(utc)
    assert keys[0] < keys[1] < keys[2]


def test_time_adapter_accepts_irregular_timestamp_spacing():
    adapter = TimeIndexedTimelineAdapter("irregular")
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-01-01T00:00:00Z"),
            pd.Timestamp("2025-01-01T00:01:00Z"),
            pd.Timestamp("2025-01-01T03:17:00Z"),
        ]
    )
    adapter.validate_index(index)
    keys = [
        adapter.key_for_position(
            index, position, InformationPhase.COMPLETED_ROW_AVAILABLE
        )
        for position in range(len(index))
    ]
    assert keys[0] < keys[1] < keys[2]


def test_adapter_rejects_wrong_timeline_timestamp_and_position():
    index = pd.date_range("2025-01-01", periods=2, tz="UTC")
    adapter = TimeIndexedTimelineAdapter("time")
    wrong_timeline = InformationKey(
        INFORMATION_KEY_VERSION,
        "other",
        0,
        index[0],
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        0,
    )
    with pytest.raises(TimelineAdapterError, match="wrong timeline"):
        adapter.validate_key(wrong_timeline, index)
    wrong_time = InformationKey(
        INFORMATION_KEY_VERSION,
        "time",
        0,
        index[1],
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        0,
    )
    with pytest.raises(TimelineAdapterError, match="timestamp"):
        adapter.validate_key(wrong_time, index)
    with pytest.raises(TimelineAdapterError, match="outside"):
        adapter.key_for_position(
            index, 2, InformationPhase.COMPLETED_ROW_AVAILABLE
        )


def test_no_generic_timestamp_guessing_or_mode_inference_api():
    positional = PositionalTimelineAdapter("p")
    with pytest.raises(TimelineAdapterError):
        positional.key_for_position(
            pd.date_range("2025-01-01", periods=1, tz="UTC"),
            0,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
        )
    timed = TimeIndexedTimelineAdapter("t")
    with pytest.raises(TimelineAdapterError):
        timed.key_for_position(
            pd.RangeIndex(1), 0, InformationPhase.COMPLETED_ROW_AVAILABLE
        )


def test_information_time_contract_manifest_is_static_and_outcome_free():
    first = information_time_contract_manifest()
    second = information_time_contract_manifest()
    pd.testing.assert_frame_equal(first, second, check_exact=True)
    assert first["serialization_order"].tolist() == list(range(len(first)))
    text = " ".join(first.astype(str).to_numpy().ravel()).lower()
    for forbidden in (
        "outcome",
        "excursion",
        "pnl",
        "target",
        "stop",
        "probability",
        "score",
    ):
        assert forbidden not in text

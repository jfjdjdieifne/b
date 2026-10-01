import numpy as np
import pandas as pd
import pytest

from trading_system.research.hashing import (
    ResearchHashError,
    canonical_sha256,
)
from trading_system.research.information_time import (
    InformationPhase,
    TimeIndexedTimelineAdapter,
)


def test_canonical_hash_is_deterministic_and_mapping_order_independent():
    left = canonical_sha256(domain="TEST", payload={"b": 2, "a": 1})
    right = canonical_sha256(domain="TEST", payload={"a": 1, "b": 2})
    assert left == right
    assert left == canonical_sha256(domain="TEST", payload={"a": 1, "b": 2})


def test_hash_domain_separation():
    payload = {"value": 1}
    assert canonical_sha256(domain="A", payload=payload) != canonical_sha256(
        domain="B", payload=payload
    )


def test_exact_integers_above_float_precision_remain_distinct():
    first = canonical_sha256(domain="INT", payload=2**53 + 1)
    second = canonical_sha256(domain="INT", payload=2**53 + 2)
    assert first != second


def test_bool_integer_and_float_identities_are_distinct():
    assert canonical_sha256(domain="TYPE", payload=False) != canonical_sha256(
        domain="TYPE", payload=0
    )
    assert canonical_sha256(domain="TYPE", payload=1) != canonical_sha256(
        domain="TYPE", payload=1.0
    )


def test_missing_sentinels_have_explicit_common_identity():
    hashes = {
        canonical_sha256(domain="MISSING", payload=value)
        for value in (None, pd.NA, np.nan, pd.NaT)
    }
    assert len(hashes) == 1


def test_dataframe_hash_is_dtype_row_column_and_index_aware():
    frame = pd.DataFrame(
        {"a": pd.array([1, 2], dtype="Int64"), "b": [1.5, 2.5]},
        index=pd.Index([10, 20], name="rows"),
    )
    original = canonical_sha256(domain="FRAME", payload=frame)
    assert original != canonical_sha256(
        domain="FRAME", payload=frame.astype({"a": "float64"})
    )
    assert original != canonical_sha256(
        domain="FRAME", payload=frame.iloc[::-1]
    )
    assert original != canonical_sha256(
        domain="FRAME", payload=frame[["b", "a"]]
    )
    relabeled = frame.copy(deep=True)
    relabeled.index = pd.Index([11, 21], name="rows")
    assert original != canonical_sha256(domain="FRAME", payload=relabeled)


def test_explicit_empty_dataframe_hash_is_stable_and_schema_aware():
    empty = pd.DataFrame(
        {
            "high": pd.Series([], dtype="float64"),
            "low": pd.Series([], dtype="float64"),
        }
    )
    first = canonical_sha256(domain="EMPTY", payload=empty)
    second = canonical_sha256(domain="EMPTY", payload=empty.copy(deep=True))
    assert first == second
    assert first != canonical_sha256(
        domain="EMPTY", payload=empty.astype({"high": "Float64"})
    )


def test_timestamp_and_information_key_normalize_to_utc():
    utc = pd.DatetimeIndex([pd.Timestamp("2025-01-01T00:00:00Z")])
    local = utc.tz_convert("Europe/Vilnius")
    adapter = TimeIndexedTimelineAdapter("timeline")
    utc_key = adapter.key_for_position(
        utc, 0, InformationPhase.COMPLETED_ROW_AVAILABLE, 1
    )
    local_key = adapter.key_for_position(
        local, 0, InformationPhase.COMPLETED_ROW_AVAILABLE, 1
    )
    assert canonical_sha256(domain="KEY", payload=utc_key) == canonical_sha256(
        domain="KEY", payload=local_key
    )
    assert canonical_sha256(domain="TIME", payload=utc[0]) == canonical_sha256(
        domain="TIME", payload=local[0]
    )


def test_positive_and_negative_zero_have_distinct_representation_hashes():
    assert canonical_sha256(domain="ZERO", payload=0.0) != canonical_sha256(
        domain="ZERO", payload=-0.0
    )


def test_positive_infinity_rejected():
    with pytest.raises(ResearchHashError, match="nonfinite"):
        canonical_sha256(domain="BAD", payload=np.inf)


def test_negative_infinity_rejected():
    with pytest.raises(ResearchHashError, match="nonfinite"):
        canonical_sha256(domain="BAD", payload=-np.inf)


def test_naive_timestamp_rejected():
    with pytest.raises(ResearchHashError, match="naive"):
        canonical_sha256(domain="BAD", payload=pd.Timestamp("2025-01-01"))


def test_unsupported_object_scalar_rejected():
    with pytest.raises(ResearchHashError, match="unsupported"):
        canonical_sha256(domain="BAD", payload=object())


def test_input_dataframe_immutable():
    frame = pd.DataFrame({"x": pd.array([1, pd.NA], dtype="Int64")})
    before = frame.copy(deep=True)
    canonical_sha256(domain="IMMUTABLE", payload=frame)
    pd.testing.assert_frame_equal(frame, before, check_exact=True)


# =====================================================================
# EXACT PERFORMANCE — hashing acceleration gates
# Differential old-vs-new against the verbatim pre-patch reference copy
# (tests/_patch_reference_src/hashing_pre.py, sha256-pinned): payload dicts,
# json bytes and sha256 must be identical, including exceptions.
# =====================================================================

import datetime
import hashlib
import importlib.util
import json
import sys
import types
from enum import Enum
from pathlib import Path


_REF_PATH = (
    Path(__file__).resolve().parent / "_patch_reference_src" / "hashing_pre.py"
)
_PRE_PATCH_HASHING_SHA256 = (
    "5426f1030fa84242cec0f6fd92f7a1fe03dc7917b6ffcf27db8ba2b613bd534e"
)


def _load_reference_hashing():
    spec = importlib.util.spec_from_file_location(
        "_patch_ref_hashing", _REF_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REF_HASHING = _load_reference_hashing()


class _BatteryEnum(Enum):
    ALPHA = 1
    BETA = "two"


def _adversarial_frames():
    frames = {}
    frames["mixed_kinds"] = pd.DataFrame(
        {
            "f": [1.5, -0.0, 0.0, np.nan, 5e-324, 1e308],
            "i": pd.array([1, 2, None, 4, 5, 6], dtype="Int64"),
            "b": [True, False, True, False, True, False],
            "s": pd.array(["a", "", None, "d", "é", "x" * 40], dtype="string"),
            "o": [1, 1.0, "z", None, pd.NA, _BatteryEnum.ALPHA],
        },
        index=pd.Index([10, 20, 30, 40, 50, 60], name="rows"),
    )
    frames["zeros_sign"] = pd.DataFrame(
        {"z": [-0.0, 0.0, -0.0, 0.0], "w": [1.0, -1.0, 0.0, -0.0]}
    )
    frames["empty_rows"] = pd.DataFrame({"a": pd.array([], dtype="Int64"), "b": []})
    frames["empty_cols"] = pd.DataFrame(index=pd.RangeIndex(3))
    frames["nullable_float"] = pd.DataFrame(
        {"p": pd.array([1.25, pd.NA, -2.5], dtype="Float64")}
    )
    frames["timedeltas"] = pd.DataFrame(
        {
            "td": pd.to_timedelta([1, 2, 3], unit="s"),
            "ts": pd.to_datetime(
                ["2020-01-01", "2020-01-02", "2020-01-03"], utc=True
            ),
        }
    )
    frames["uint_and_small"] = pd.DataFrame(
        {"u": np.array([1, 2, 3], dtype="uint64"), "i8": np.array([-1, 0, 1], dtype="int8")}
    )
    frames["single_cell"] = pd.DataFrame({"only": [0.1 + 0.2]})
    return frames


def _payload_json(value):
    return json.dumps(
        REF_HASHING.canonical_payload(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _payload_json_new(value):
    import trading_system.research.hashing as new_hashing

    return json.dumps(
        new_hashing.canonical_payload(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def test_patch_hashing_reference_snapshot_is_pinned():
    assert _REF_PATH.exists()
    digest = hashlib.sha256(_REF_PATH.read_bytes()).hexdigest()
    assert digest == _PRE_PATCH_HASHING_SHA256


def test_patch_hashing_payload_and_sha256_identical_on_adversarial_battery():
    from trading_system.research.hashing import canonical_sha256 as new_sha

    cases = list(_adversarial_frames().items())
    cases += [
        ("scalar_int", 2**53 + 1),
        ("scalar_float", -0.0),
        ("scalar_nan", np.nan),
        ("scalar_missing", pd.NA),
        ("scalar_str", "x"),
        ("scalar_bool", np.bool_(True)),
        ("scalar_npint", np.int64(-7)),
        ("scalar_enum", _BatteryEnum.BETA),
        ("scalar_ts", pd.Timestamp("2020-01-01", tz="UTC")),
        ("scalar_td", pd.Timedelta(1, "s")),
        ("list", [1, "a", None, 2.5, [3, 4]]),
        ("mapping", {"b": 2, "a": {"z": [1.0, pd.NA]}}),
    ]
    for label, value in cases:
        assert _payload_json(value) == _payload_json_new(value), label
        assert REF_HASHING.canonical_sha256(domain="D", payload=value) == new_sha(
            domain="D", payload=value
        ), label


def test_patch_hashing_exceptions_identical():
    from trading_system.research.hashing import (
        ResearchHashError as NewError,
        canonical_sha256 as new_sha,
    )

    bad_frames = {
        "naive_ts": pd.DataFrame({"ts": pd.to_datetime(["2020-01-01", "2020-01-02"])}),
        "inf_float": pd.DataFrame({"f": [1.0, np.inf]}),
        "ninf_float": pd.DataFrame({"f": [-np.inf, 1.0]}),
        "complex": pd.DataFrame({"c": [1 + 2j, 3 + 4j]}),
    }
    for label, frame in bad_frames.items():
        with pytest.raises(REF_HASHING.ResearchHashError) as exc_ref:
            REF_HASHING.canonical_sha256(domain="D", payload=frame)
        with pytest.raises(NewError) as exc_new:
            new_sha(domain="D", payload=frame)
        assert str(exc_new.value) == str(exc_ref.value), label
        assert type(exc_new.value).__name__ == type(exc_ref.value).__name__

    for bad in ({"k": 1}.keys(), datetime.datetime(2020, 1, 1)):
        with pytest.raises(REF_HASHING.ResearchHashError):
            REF_HASHING.canonical_sha256(domain="D", payload=bad)
        with pytest.raises(NewError):
            new_sha(domain="D", payload=bad)


def test_patch_hashing_mutation_transposed_rows_detected():
    source = Path("src/trading_system/research/hashing.py").read_text(
        encoding="utf-8"
    )
    mutated = source.replace(
        "        rows = [list(row) for row in zip(*per_column)]",
        "        rows = [list(row) for row in zip(*per_column)][::-1]",
    )
    assert mutated != source
    module = types.ModuleType("_mutated_hashing")
    sys.modules[module.__name__] = module
    exec(compile(mutated, module.__name__, "exec"), module.__dict__)
    frame = _adversarial_frames()["mixed_kinds"]
    assert (
        module.canonical_sha256(domain="D", payload=frame)
        != REF_HASHING.canonical_sha256(domain="D", payload=frame)
    ), "row-order mutation must be detected by the differential battery"

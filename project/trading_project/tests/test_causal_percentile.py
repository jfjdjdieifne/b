import math

import numpy as np
import pandas as pd
import pytest

from trading_system.audit.causal_state import (
    ReentrancyPolicy,
    verify_state_isolation,
    verify_truncation_invariance,
)
from trading_system.core.causal_percentile import (
    CausalPercentileConfigError,
    CausalPercentileDataError,
    CausalPercentileTracker,
    _PercentileAuditEngine,
    causal_percentile_series,
)


def test_module_01_certifies_expanding_and_bounded_modes():
    rng = np.random.default_rng(2026)
    df = pd.DataFrame({"feature": rng.normal(size=301)})

    for max_history in (None, 17):
        results = verify_truncation_invariance(
            lambda: _PercentileAuditEngine(
                source_column="feature", max_history=max_history
            ),
            df,
            additional_split_points=[1, 2, 16, 17, 18, 127, 300],
        )
        assert all(result.passed for result in results)


def test_module_01_certifies_adapter_state_isolation():
    rng = np.random.default_rng(9)
    df_a = pd.DataFrame({"feature": rng.normal(size=101)})
    df_b = pd.DataFrame({"feature": rng.normal(size=103)})

    result = verify_state_isolation(
        lambda: _PercentileAuditEngine(source_column="feature"),
        df_a,
        df_b,
        policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT,
    )
    assert result.passed


def test_nan_skip_does_not_enter_history_and_reset_is_complete():
    tracker = CausalPercentileTracker(max_history=3, nan_policy="skip")
    tracker.observe(1.0)
    missing = tracker.observe(np.nan)
    tracker.observe(2.0)

    assert not missing.accepted
    assert tracker.history_snapshot() == (1.0, 2.0)
    assert tracker.total_pushed == 2
    assert tracker.total_skipped == 1

    tracker.reset()
    assert tracker.is_empty
    assert tracker.total_pushed == 0
    assert tracker.total_skipped == 0


def test_series_preserves_index_and_prior_only_counts():
    index = pd.Index(["a", "b", "c", "d"])
    values = pd.Series([10.0, np.nan, 20.0, 15.0], index=index)
    result = causal_percentile_series(values)

    assert result.index.equals(index)
    assert result["sample_count"].tolist() == [0, 1, 1, 2]
    assert result["accepted"].tolist() == [True, False, True, True]
    assert math.isnan(result.loc["a", "percentile"])
    assert result.loc["c", "percentile"] == 1.0
    assert result.loc["d", "percentile"] == 0.5


@pytest.mark.parametrize("invalid", [0, -1, 1.5, True])
def test_invalid_max_history_rejected(invalid):
    with pytest.raises(CausalPercentileConfigError):
        CausalPercentileTracker(max_history=invalid)


@pytest.mark.parametrize("invalid", [True, np.bool_(False), np.inf, -np.inf, "x"])
def test_invalid_observations_rejected(invalid):
    with pytest.raises(CausalPercentileDataError):
        CausalPercentileTracker().observe(invalid)


# =====================================================================
# EXACT PERFORMANCE V2 PATCH-1 gates
# Differential old-vs-new (pre-patch reference copy), bitwise battery,
# exact rolling eviction, causality, and mutation proofs.
# Reference source: tests/_patch_reference_src/causal_percentile_pre.py
# (verbatim pre-patch snapshot; sha256-pinned below).
# =====================================================================

import hashlib
import importlib.util
import sys
import types
from pathlib import Path


_REF_PATH = (
    Path(__file__).resolve().parent
    / "_patch_reference_src"
    / "causal_percentile_pre.py"
)

# Pre-patch sha256 of src/trading_system/core/causal_percentile.py.
_REF_EXPECTED_SHA256 = (
    "d0db2281e025f935345b8bc23cd4eed88130bae4df919f85b6e666b424d88696"
)


def _load_reference():
    spec = importlib.util.spec_from_file_location(
        "_patch_ref_causal_percentile", _REF_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REF = _load_reference()


def _hex(value):
    return float(value).hex()


def _assert_observation_equal(got, expected, label):
    assert got.accepted == expected.accepted, label
    assert got.sample_count == expected.sample_count, label
    assert got.less_count == expected.less_count, label
    assert got.equal_count == expected.equal_count, label
    assert got.greater_count == expected.greater_count, label
    assert _hex(got.value) == _hex(expected.value), label
    assert _hex(got.percentile) == _hex(expected.percentile), label
    assert _hex(got.history_min) == _hex(expected.history_min), label
    assert _hex(got.history_max) == _hex(expected.history_max), label


def _reference_snapshot_is_pinned():
    digest = hashlib.sha256(_REF_PATH.read_bytes()).hexdigest()
    return digest == _REF_EXPECTED_SHA256


def test_patch_v2_reference_source_is_the_pinned_pre_patch_copy():
    assert _REF_PATH.exists()
    assert _reference_snapshot_is_pinned(), (
        "tests/_patch_reference_src/causal_percentile_pre.py must remain the "
        "verbatim pre-patch snapshot"
    )


def _battery_value_streams():
    rng = np.random.default_rng(20260929)
    streams = {
        "ties_midrank": [10.0, 20.0, 20.0, 30.0, 20.0, 10.0, 10.0, 40.0],
        "signed_zeros": [0.0, -0.0, 0.0, -0.0, -0.0, 0.0, 5.0, -5.0, -0.0, 0.0],
        "single_kind_zero": [0.0, 1.0, 0.0, 2.0, 0.0],
        "neg_zero_only": [-0.0, -1.0, -0.0, -2.0],
        "all_equal": [7.0] * 9,
        "monotone_up": [float(i) for i in range(40)],
        "monotone_down": [-float(i) for i in range(40)],
        "alternating": [1.0, -1.0, 2.0, -2.0, 3.0, -3.0, 1.0, -1.0],
        "subnormals": [5e-324, -5e-324, 2.2250738585072014e-308, 5e-324, -5e-324],
        "huge": [1e308, -1e308, 1.7976931348623157e308, -1.7976931348623157e308, 1e308],
        "mixed_scale": [
            0.1, -0.0, 1e-12, 1e12, 0.1 + 0.2, 0.3, -0.0, 5e-324,
            math.nextafter(1.0, 2.0), math.nextafter(1.0, 0.0), 0.0,
        ],
    }
    for n in (2, 3, 5, 17, 33, 64):
        streams[f"random_{n}"] = list(rng.normal(size=n))
        streams[f"random_rounded_{n}"] = list(np.round(rng.normal(size=n), 1))
        streams[f"choice_{n}"] = list(
            rng.choice(
                np.array([0.0, -0.0, 1.0, -1.0, 2.5, -2.5, 1e-9, -1e-9]),
                size=n,
            )
        )
    return streams


def _battery_q_values():
    rng = np.random.default_rng(20260929)
    qs = [0.0, 1.0, 0.5, 1.0 / 3.0, 2.0 / 3.0, 0.1, 0.25, 0.75, 0.9, 0.99]
    for n in (2, 3, 4, 5, 8, 17, 33, 64, 128):
        for h_target in (0, n // 2, n - 1):
            base = h_target / (n - 1)
            qs.extend([base, math.nextafter(base, 0.0), math.nextafter(base, 1.0)])
    qs.extend([float(x) for x in rng.random(32)])
    qs.extend([0.1 + 0.2, math.nextafter(0.5, 0.0), math.nextafter(0.5, 1.0)])
    return [q for q in qs if 0.0 <= q <= 1.0]


def _drive_pair(new_tracker, ref_tracker, stream):
    for value in stream:
        got = new_tracker.observe(value)
        expected = ref_tracker.observe(value)
        _assert_observation_equal(got, expected, f"observe({value!r})")
    for value in (0.0, -0.0, 20.0, -1e300, 1.5):
        _assert_observation_equal(
            new_tracker.rank(value), ref_tracker.rank(value), f"rank({value!r})"
        )
    assert new_tracker.history_snapshot() == ref_tracker.history_snapshot()
    assert new_tracker.sample_count == ref_tracker.sample_count
    assert new_tracker.total_pushed == ref_tracker.total_pushed
    assert new_tracker.total_skipped == ref_tracker.total_skipped


def test_patch_v2_observe_rank_push_differential_battery():
    streams = _battery_value_streams()
    for label, stream in streams.items():
        for max_history in (None, 3, 17):
            _drive_pair(
                CausalPercentileTracker(max_history=max_history),
                REF.CausalPercentileTracker(max_history=max_history),
                stream,
            )
            _drive_pair(
                CausalPercentileTracker(max_history=max_history, nan_policy="raise"),
                REF.CausalPercentileTracker(max_history=max_history, nan_policy="raise"),
                [v for v in stream],
            )


def test_patch_v2_percentile_value_bitwise_battery():
    streams = _battery_value_streams()
    qs = _battery_q_values()
    for label, stream in streams.items():
        for max_history in (None, 5, 17):
            new_tracker = CausalPercentileTracker(max_history=max_history)
            ref_tracker = REF.CausalPercentileTracker(max_history=max_history)
            for value in stream:
                new_tracker.push(value)
                ref_tracker.push(value)
            for q in qs:
                got = new_tracker.percentile_value(q)
                expected = ref_tracker.percentile_value(q)
                assert _hex(got) == _hex(expected), (
                    f"percentile_value({q}) on {label} max_history={max_history}: "
                    f"{_hex(got)} != {_hex(expected)}"
                )
                # Reference is the literal np.quantile path; pin that too.
                if max_history is None:
                    arr = np.array(stream, dtype=np.float64)
                    assert _hex(expected) == _hex(
                        float(np.quantile(arr, q, method="linear"))
                    )


def test_patch_v2_percentile_value_matches_numpy_on_push_order_permutations():
    rng = np.random.default_rng(7)
    base = [0.0, -0.0, 1.0, 2.0, 2.0, -3.5, 5e-324, 1e300, 0.1 + 0.2]
    qs = _battery_q_values()[:40]
    for trial in range(8):
        order = list(rng.permutation(base))
        tracker = CausalPercentileTracker()
        for value in order:
            tracker.push(value)
        for q in qs:
            expected = REF.CausalPercentileTracker()
            for value in order:
                expected.push(value)
            assert _hex(tracker.percentile_value(q)) == _hex(expected.percentile_value(q))


def test_patch_v2_max_history_rolling_eviction_exact():
    stream = [10.0, 20.0, 20.0, -0.0, 0.0, 5.0, 5.0, 30.0, -1.0, 20.0, 0.0, -0.0, 7.5]
    for max_history in (1, 2, 3, 5, 17):
        new_tracker = CausalPercentileTracker(max_history=max_history)
        ref_tracker = REF.CausalPercentileTracker(max_history=max_history)
        for step, value in enumerate(stream):
            got = new_tracker.observe(value)
            expected = ref_tracker.observe(value)
            _assert_observation_equal(got, expected, f"step {step} mh={max_history}")
            assert new_tracker.history_snapshot() == ref_tracker.history_snapshot()
            assert len(new_tracker.history_snapshot()) == min(step + 1, max_history)
            assert new_tracker.sample_count == ref_tracker.sample_count
            assert new_tracker.total_pushed == ref_tracker.total_pushed
        for q in (0.0, 0.5, 1.0, 0.25, 0.1 + 0.2):
            assert _hex(new_tracker.percentile_value(q)) == _hex(
                ref_tracker.percentile_value(q)
            )


def test_patch_v2_signed_zero_extrema_first_wins():
    cases = [
        [0.0, -0.0, -0.0],
        [-0.0, 0.0, 0.0],
        [-0.0, 0.0, -0.0, 0.0],
        [0.0, -0.0, 1.0, -1.0, 0.0, -0.0],
        [5.0, -0.0, 0.0],
        [5.0, 0.0, -0.0],
    ]
    for max_history in (None, 2, 4):
        for stream in cases:
            new_tracker = CausalPercentileTracker(max_history=max_history)
            ref_tracker = REF.CausalPercentileTracker(max_history=max_history)
            for value in stream:
                _assert_observation_equal(
                    new_tracker.observe(value),
                    ref_tracker.observe(value),
                    f"signed-zero mh={max_history} stream={stream}",
                )


def test_patch_v2_nan_policies_and_rejections_identical():
    new_tracker = CausalPercentileTracker(nan_policy="skip")
    ref_tracker = REF.CausalPercentileTracker(nan_policy="skip")
    for value in (1.0, float("nan"), 2.0, float("nan")):
        _assert_observation_equal(
            new_tracker.observe(value), ref_tracker.observe(value), "nan skip"
        )
    assert new_tracker.total_skipped == ref_tracker.total_skipped == 2

    for policy in ("skip", "raise"):
        new_tracker = CausalPercentileTracker(nan_policy=policy)
        ref_tracker = REF.CausalPercentileTracker(nan_policy=policy)
        new_tracker.push(1.0)
        ref_tracker.push(1.0)
        if policy == "raise":
            with pytest.raises(CausalPercentileDataError) as exc_new:
                new_tracker.rank(float("nan"))
            with pytest.raises(REF.CausalPercentileDataError) as exc_ref:
                ref_tracker.rank(float("nan"))
            assert type(exc_new.value).__name__ == type(exc_ref.value).__name__
            assert str(exc_new.value) == str(exc_ref.value)

    for bad in (True, np.bool_(False), float("inf"), float("-inf"), "x", None, [1.0]):
        for op in ("rank", "push"):
            with pytest.raises(CausalPercentileDataError) as exc_new:
                getattr(CausalPercentileTracker(), op)(bad)
            with pytest.raises(REF.CausalPercentileDataError) as exc_ref:
                getattr(REF.CausalPercentileTracker(), op)(bad)
            assert type(exc_new.value).__name__ == type(exc_ref.value).__name__
            assert str(exc_new.value) == str(exc_ref.value)

    for bad_q in (True, np.bool_(True), float("nan"), float("inf"), -0.1, 1.1, "x", None):
        new_tracker = CausalPercentileTracker()
        ref_tracker = REF.CausalPercentileTracker()
        new_tracker.push(1.0)
        ref_tracker.push(1.0)
        with pytest.raises(CausalPercentileConfigError) as exc_new:
            new_tracker.percentile_value(bad_q)
        with pytest.raises(REF.CausalPercentileConfigError) as exc_ref:
            ref_tracker.percentile_value(bad_q)
        assert type(exc_new.value).__name__ == type(exc_ref.value).__name__
        assert str(exc_new.value) == str(exc_ref.value)


def test_patch_v2_reset_and_empty_semantics_identical():
    for max_history in (None, 3):
        new_tracker = CausalPercentileTracker(max_history=max_history)
        ref_tracker = REF.CausalPercentileTracker(max_history=max_history)
        for value in (3.0, -0.0, 9.0, float("nan")):
            new_tracker.observe(value)
            ref_tracker.observe(value)
        assert math.isnan(new_tracker.percentile_value(0.5)) == math.isnan(
            ref_tracker.percentile_value(0.5)
        )
        new_tracker.reset()
        ref_tracker.reset()
        assert new_tracker.history_snapshot() == ref_tracker.history_snapshot() == ()
        assert new_tracker.sample_count == ref_tracker.sample_count == 0
        assert new_tracker.total_pushed == ref_tracker.total_pushed == 0
        assert new_tracker.total_skipped == ref_tracker.total_skipped == 0
        assert new_tracker.is_empty and ref_tracker.is_empty
        _assert_observation_equal(
            new_tracker.observe(1.0), ref_tracker.observe(1.0), "post-reset"
        )


def test_patch_v2_causality_prefix_and_future_suffix():
    rng = np.random.default_rng(99)
    stream = [float(x) for x in rng.normal(size=120)]
    for split_at in (1, 7, 40, 80, 119):
        full = CausalPercentileTracker()
        truncated = CausalPercentileTracker()
        prefix_obs = []
        for i, value in enumerate(stream):
            prefix_obs.append(full.observe(value))
            if i < split_at:
                truncated.observe(value)
        # full prefix == truncated run observations (computed independently)
        truncated2 = CausalPercentileTracker()
        for i in range(split_at):
            _assert_observation_equal(
                truncated2.observe(stream[i]), prefix_obs[i], f"prefix {split_at} i={i}"
            )

    # Future suffix mutation must not alter observations up to T.
    split_at = 60
    mutated = list(stream)
    for i in range(split_at, len(stream)):
        mutated[i] = stream[i] * 1_000_000.0 + 999_999.0
    original_tracker = CausalPercentileTracker()
    mutated_tracker = CausalPercentileTracker()
    for i in range(split_at):
        _assert_observation_equal(
            mutated_tracker.observe(mutated[i]),
            original_tracker.observe(stream[i]),
            f"future-suffix i={i}",
        )
    # causal_percentile_series truncation invariance after patch.
    series = pd.Series(stream, name="feature")
    full_frame = causal_percentile_series(series)
    truncated_frame = causal_percentile_series(series.iloc[:split_at])
    pd.testing.assert_frame_equal(
        full_frame.iloc[:split_at], truncated_frame, check_exact=True
    )


def _exec_mutated_source(mutate, module_name):
    source = Path(
        "src/trading_system/core/causal_percentile.py"
    ).read_text(encoding="utf-8")
    mutated_source = mutate(source)
    assert mutated_source != source, "mutation did not apply"

    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    exec(compile(mutated_source, module_name, "exec"), module.__dict__)
    return module


def test_patch_v2_mutation_tie_midrank_break_is_detected():
    def mutate(source):
        return source.replace(
            "percentile = (\n            less + 0.5 * equal\n        ) / n",
            "percentile = (\n            less + equal\n        ) / n",
        )

    broken = _exec_mutated_source(mutate, "_mutated_tie_midrank")
    stream = [10.0, 20.0, 20.0, 30.0, 20.0]
    broken_tracker = broken.CausalPercentileTracker()
    ref_tracker = REF.CausalPercentileTracker()
    differences = 0
    for value in stream:
        got = broken_tracker.observe(value)
        expected = ref_tracker.observe(value)
        if _hex(got.percentile) != _hex(expected.percentile):
            differences += 1
    assert differences > 0, (
        "tie mid-rank mutation (less+equal instead of less+0.5*equal) must be "
        "detected by the differential battery"
    )


def test_patch_v2_mutation_read_before_push_break_is_detected():
    def mutate(source):
        return source.replace(
            "        result = self.rank(value)\n",
            "        self.push(value)\n        result = self.rank(value)\n",
        )

    broken = _exec_mutated_source(mutate, "_mutated_self_inclusion")
    stream = [10.0, 20.0, 20.0, 30.0]
    broken_tracker = broken.CausalPercentileTracker()
    ref_tracker = REF.CausalPercentileTracker()
    differences = 0
    for value in stream:
        got = broken_tracker.observe(value)
        expected = ref_tracker.observe(value)
        if (
            _hex(got.percentile) != _hex(expected.percentile)
            or got.sample_count != expected.sample_count
            or got.less_count != expected.less_count
            or got.equal_count != expected.equal_count
        ):
            differences += 1
    assert differences > 0, (
        "read-before-push mutation (self-inclusion) must be detected by the "
        "differential battery"
    )
    assert broken_tracker.sample_count != ref_tracker.sample_count

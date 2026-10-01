"""WINDOWS REPORTING PATCH gates (owner task: FIELD RUNNER WINDOWS REPORTING
BLOCKER - PATCH ONLY).

1. MACHINE_VALIDATION must be produced on Windows without the Unix-only
   `resource` module (regression: the owner run crashed at
   `import resource` inside build_machine_validation).
2. Peak memory is NEVER a success condition for the report.
3. No new dependency is introduced for memory measurement.
4. The Unix/Linux path is byte-identical to the pre-patch implementation
   (differential against the sha256-pinned reference copy).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys
import time
import types

import pytest

FIELD_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUNNER_SRC = os.path.join(FIELD_RUNNER_DIR, "runner_btc_may_2026.py")
_REF_PATH = os.path.join(
    FIELD_RUNNER_DIR, "runner_tests", "_reference_reporting_pre.py"
)
_PRE_PATCH_REPORTING_SHA256 = (
    "aa2cfbfb3dfe9a628cec5509c018a03be22694dec575117f90a5018b49acbacc"
)


def _load_reference_reporting():
    spec = importlib.util.spec_from_file_location("_ref_reporting_pre", _REF_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _machine_kwargs():
    config = types.SimpleNamespace(
        swing_quantile=None,
        swing_prior_continuation_reversals=[],
        swing_prior_confirmed_reversals=[],
        sessions=[],
        sample_size=100,
        htf_durations=["1h"],
        symbol="BTCUSDT",
        year_month="2026-05",
    )
    return dict(
        runner_files={"a.py": "00" * 32},
        config=config,
        source_paths_and_hashes={"facts.csv": "11" * 32},
        engine_modules={"mod": "22" * 32},
        output_paths={"SUMMARY.json": "33" * 32},
        statuses=[],
        started_at=time.time(),
        failures=[],
        warnings=[],
        manifest_result={"ok": 183, "bad": 10},
        adapter_identity={"seal": "44" * 32},
    )


def test_reference_reporting_snapshot_is_pinned():
    digest = hashlib.sha256(open(_REF_PATH, "rb").read()).hexdigest()
    assert digest == _PRE_PATCH_REPORTING_SHA256


def test_machine_validation_produced_without_resource_module(monkeypatch):
    """Regression: on Windows `import resource` raises ModuleNotFoundError and
    MACHINE_VALIDATION must still be produced; peak memory must be the
    explicit platform-safe record (no invented measurement); missing peak
    memory must not become a report failure/warning."""
    from field_runner.reporting import build_machine_validation

    monkeypatch.setitem(sys.modules, "resource", None)  # import resource -> ImportError
    result = build_machine_validation(**_machine_kwargs())

    peak = result["peak_memory"]
    assert isinstance(peak, dict), peak
    assert set(peak) == {"status", "platform", "method"}, peak
    assert peak["status"] == "NOT_AVAILABLE_ON_THIS_PLATFORM"
    assert peak["method"] is None
    assert isinstance(peak["platform"], str) and peak["platform"]

    assert result["failures"] == []
    assert result["warnings"] == []
    assert result["volatile_keys"] == ["runtime_seconds", "peak_memory"]
    assert result["runner_version"] == "BTC_MAY2026_FIELD_RUNNER_V1"
    assert result["project_manifest_validation"]["ok"] == 183


def test_pre_patch_reporting_crashes_without_resource_module(monkeypatch):
    """Documents the original blocker: the pre-patch implementation cannot
    produce MACHINE_VALIDATION without the `resource` module."""
    ref = _load_reference_reporting()
    monkeypatch.setitem(sys.modules, "resource", None)
    with pytest.raises(ImportError):
        ref.build_machine_validation(**_machine_kwargs())


def test_machine_validation_resource_path_identical_to_pre_patch(monkeypatch):
    """Linux/Unix path is unchanged: with `resource` available the whole
    MACHINE_VALIDATION dict equals the sha256-pinned pre-patch output
    (runtime_seconds is time-of-call based and compared separately)."""
    import resource

    from field_runner import reporting as new_reporting

    ref = _load_reference_reporting()

    fixed_kib = 123456
    monkeypatch.setattr(
        resource,
        "getrusage",
        lambda who: types.SimpleNamespace(ru_maxrss=fixed_kib),
    )
    kwargs = _machine_kwargs()
    old = ref.build_machine_validation(**kwargs)
    new = new_reporting.build_machine_validation(**kwargs)

    assert old["peak_memory"] == f"{fixed_kib} KiB (ru_maxrss)"
    assert new["peak_memory"] == old["peak_memory"]
    old_cmp = dict(old)
    new_cmp = dict(new)
    assert isinstance(old_cmp.pop("runtime_seconds"), float)
    assert isinstance(new_cmp.pop("runtime_seconds"), float)
    assert new_cmp == old_cmp

    # getrusage failure path: unchanged "NOT_AVAILABLE" string on both.
    def _boom(who):
        raise OSError("no rusage")

    monkeypatch.setattr(resource, "getrusage", _boom)
    assert ref.build_machine_validation(**_machine_kwargs())["peak_memory"] == "NOT_AVAILABLE"
    assert (
        new_reporting.build_machine_validation(**_machine_kwargs())["peak_memory"]
        == "NOT_AVAILABLE"
    )

    # Real (unstubbed) value keeps the historical format.
    monkeypatch.undo()
    real = new_reporting.build_machine_validation(**_machine_kwargs())["peak_memory"]
    assert re.fullmatch(r"\d+ KiB \(ru_maxrss\)", real), real


def test_progress_text_no_longer_claims_tens_of_minutes():
    source = open(_RUNNER_SRC, encoding="utf-8").read()
    assert "TENS OF MINUTES" not in source
    assert (
        "runtime depends on dataset and certified engine implementation; "
        "stage timings are reported below."
    ) in source

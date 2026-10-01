"""PATCH regression + attacks for artifact-ROLE separation (SYNTHETIC ONLY).

Reproduces the owner-local blocker literally: data/ contains a minute-facts CSV
whose FILENAME contains 'aggTrades' plus its sidecar, and NO raw aggTrades file.
FAST mode must pass, and the minute-facts file must NEVER be classified as RAW.

All data here are tiny synthetic fixtures. No real-owner artifact exists in the
builder environment; none is downloaded, requested, or simulated as real.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil

import pytest

from field_runner import fixtures as fixture_factory
from field_runner.runner_btc_may_2026 import detect_inputs, main as runner_main


def _cfg(path):
    path.write_text(json.dumps({
        "swing_quantile": None, "sessions": [], "sample_size": 5,
        "htf_durations": ["1h"], "symbol": "FIXTURESYM", "year_month": "2026-05",
        "period_start_utc": "2026-05-01T00:00:00Z",
        "period_end_utc": "2026-05-01T04:00:00Z",
    }), encoding="utf-8")
    return str(path)


def _place_owner_shaped(data_dir, *, facts_name="minute_facts_BTCUSDT-aggTrades-2026-05.csv",
                        with_raw=False, extra_minute_facts=False):
    """Synthetic owner-shaped layout: minute-facts name CONTAINS 'aggTrades'."""
    os.makedirs(data_dir, exist_ok=True)
    fx = fixture_factory.write_fixture(data_dir, n_minutes=30, ambiguous_minute=10)
    facts = os.path.join(data_dir, facts_name)
    os.rename(fx["facts_path"], facts)
    sidecar = os.path.join(data_dir, facts_name[:-4] + ".sidecar.json")
    os.rename(fx["sidecar_path"], sidecar)
    raw = None
    if with_raw:
        raw = os.path.join(data_dir, "BTCUSDT-aggTrades-2026-05.csv")
        # synthetic raw placeholder whose hash equals the fixture source binding
        open(raw, "wb").write(b"TEST_FIXTURE_RAW_AGGTRADES_PLACEHOLDER")
    if extra_minute_facts:
        shutil.copy(facts, os.path.join(data_dir, "minute_facts_SECOND-aggTrades-2026-05.csv"))
    fx.update({"facts_path": facts, "sidecar_path": sidecar, "raw_path": raw})
    return fx


def _run(data_dir, fx, outdir, extra=(), mode="fast", cfg_path=None):
    cfg_path = cfg_path or os.path.join(data_dir, "run_config.json")
    open(cfg_path, "w", encoding="utf-8").write(json.dumps({
        "swing_quantile": None, "sessions": [], "sample_size": 5,
        "htf_durations": ["1h"], "symbol": "FIXTURESYM", "year_month": "2026-05",
        "period_start_utc": "2026-05-01T00:00:00Z",
        "period_end_utc": "2026-05-01T04:00:00Z",
    }))
    return runner_main([
        "--config", cfg_path, "--data-dir", data_dir, "--outdir", outdir,
        "--minute-facts", fx["facts_path"], "--minute-facts-sidecar", fx["sidecar_path"],
        "--klines-csv", fx["klines_csv_path"], "--mode", mode,
        "--expect-minute-facts-sha256", fx["facts_sha256"],
        "--expect-aggtrades-sha256", fx["source_sha256"],
        "--expect-converter-sha256", fx["converter_sha256"],
        *extra,
    ])


class _Args:
    minute_facts = None
    minute_facts_sidecar = None
    aggtrades = None
    data_dir = None


def test_owner_literal_regression_fast_mode_passes(tmp_path):
    """data/minute_facts_BTCUSDT-aggTrades-2026-05.csv + sidecar, NO raw CSV."""
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data), with_raw=False)
    # discovery (no explicit paths) must classify the file as MINUTE_FACTS, not RAW
    args = _Args()
    args.data_dir = str(data)
    d, facts, sidecar, raw = detect_inputs(args, None)
    assert facts == fx["facts_path"]
    assert raw is None, "filename containing 'aggTrades' must NOT be classified as RAW"
    assert sidecar == fx["sidecar_path"]
    rc = _run(str(data), fx, str(tmp_path / "out"))
    assert rc == 0


def test_minute_facts_and_sidecar_correct_pass(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data), facts_name="minute_facts_clean.csv")
    assert _run(str(data), fx, str(tmp_path / "out")) == 0


def test_minute_facts_hash_wrong_fails_with_specific_name(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data))
    with pytest.raises(SystemExit) as exc:
        _run(str(data), fx, str(tmp_path / "out"),
             extra=("--expect-minute-facts-sha256", "0" * 64))
    msg = str(exc.value)
    assert "MINUTE_FACTS_HASH_MISMATCH" in msg
    assert "AGGTRADES_HASH_MISMATCH" not in msg


def test_sidecar_source_binding_wrong_fails(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data))
    sc = json.load(open(fx["sidecar_path"], encoding="utf-8"))
    sc["source_sha256"] = "f" * 64
    json.dump(sc, open(fx["sidecar_path"], "w", encoding="utf-8"))
    with pytest.raises(SystemExit) as exc:
        _run(str(data), fx, str(tmp_path / "out"))
    assert "SIDECAR_SOURCE_BINDING_MISMATCH" in str(exc.value)


def test_converter_binding_wrong_fails(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data))
    sc = json.load(open(fx["sidecar_path"], encoding="utf-8"))
    sc["converter_sha256"] = "e" * 64
    json.dump(sc, open(fx["sidecar_path"], "w", encoding="utf-8"))
    with pytest.raises(SystemExit) as exc:
        _run(str(data), fx, str(tmp_path / "out"))
    assert "CONVERTER_BINDING_MISMATCH" in str(exc.value)


def test_sidecar_output_binding_wrong_fails(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data))
    sc = json.load(open(fx["sidecar_path"], encoding="utf-8"))
    sc["output_csv_sha256"] = "d" * 64
    json.dump(sc, open(fx["sidecar_path"], "w", encoding="utf-8"))
    with pytest.raises(SystemExit) as exc:
        _run(str(data), fx, str(tmp_path / "out"))
    assert "SIDECAR_OUTPUT_BINDING_MISMATCH" in str(exc.value)


def test_raw_absent_in_fast_mode_passes(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data), with_raw=False)
    assert _run(str(data), fx, str(tmp_path / "out"), mode="fast") == 0


def test_raw_absent_in_raw_mode_fails(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data), with_raw=False)
    with pytest.raises(SystemExit) as exc:
        _run(str(data), fx, str(tmp_path / "out"), mode="raw")
    assert "RAW_AGGTRADES_FILE_REQUIRED" in str(exc.value)


def test_two_minute_facts_files_fail_closed_with_paths(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data), extra_minute_facts=True)
    args = _Args()
    args.data_dir = str(data)
    with pytest.raises(SystemExit) as exc:
        detect_inputs(args, None)
    msg = str(exc.value)
    assert "MINUTE_FACTS_AMBIGUOUS" in msg
    assert "minute_facts_BTCUSDT-aggTrades-2026-05.csv" in msg
    assert "minute_facts_SECOND-aggTrades-2026-05.csv" in msg


def test_raw_and_minute_facts_both_present_classified_correctly(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data), with_raw=True)
    args = _Args()
    args.data_dir = str(data)
    d, facts, sidecar, raw = detect_inputs(args, None)
    assert facts == fx["facts_path"]
    assert raw == fx["raw_path"], "raw must be the raw aggTrades file"
    assert raw != facts
    # full run passes with the raw file present AND hash-verified
    assert _run(str(data), fx, str(tmp_path / "out")) == 0


def test_raw_present_but_hash_wrong_fails_with_raw_name(tmp_path):
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data), with_raw=True)
    open(fx["raw_path"], "wb").write(b"NOT_THE_RAW_ARTIFACT")
    with pytest.raises(SystemExit) as exc:
        _run(str(data), fx, str(tmp_path / "out"))
    msg = str(exc.value)
    assert "RAW_AGGTRADES_HASH_MISMATCH" in msg
    assert "MINUTE_FACTS_HASH_MISMATCH" not in msg


def test_owner_bare_command_discovery_runs_end_to_end(tmp_path):
    """Bare-style retry: NO --minute-facts/--aggtrades flags at all — pure
    role-aware discovery over data/, exactly like `python run_btc_may_2026.py`."""
    data = tmp_path / "data"
    fx = _place_owner_shaped(str(data), with_raw=False)
    cfg_path = tmp_path / "cfg.json"
    open(cfg_path, "w", encoding="utf-8").write(json.dumps({
        "swing_quantile": None, "sessions": [], "sample_size": 5,
        "htf_durations": ["1h"], "symbol": "FIXTURESYM", "year_month": "2026-05",
        "period_start_utc": "2026-05-01T00:00:00Z",
        "period_end_utc": "2026-05-01T04:00:00Z",
    }))
    rc = runner_main([
        "--config", str(cfg_path), "--data-dir", str(data), "--outdir", str(tmp_path / "out"),
        "--klines-csv", fx["klines_csv_path"],
        "--expect-minute-facts-sha256", fx["facts_sha256"],
        "--expect-aggtrades-sha256", fx["source_sha256"],
        "--expect-converter-sha256", fx["converter_sha256"],
    ])
    assert rc == 0
    assert os.path.isfile(os.path.join(str(tmp_path / "out"), "SUMMARY.json"))


def test_cli_defaults_match_owner_reference_hashes():
    """The owner retry command needs no flags: defaults hold the reference metadata."""
    import inspect

    from field_runner.runner_btc_may_2026 import main as m

    src = inspect.getsource(m)
    assert "86d4f3d335ae244dcc143569bd1cc382320027c3fe4702e5d3ddf0757e8f1c04" in src
    assert "a6a06c4c583e64e7613ddca275533a15062ab13864482cacf30b2f125094601f" in src
    assert "0048779bd821dbe6f3cda66517b19e7435fc0b98592ee9aa1980804fe27efb5d" in src
    assert 'default="fast"' in src

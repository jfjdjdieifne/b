"""Fail-closed attack tests: corrupted source, missing kline, wrong checksum,
source inconsistency. Every attack must hard-fail before any interpretation."""

from __future__ import annotations

import hashlib
import os
import zipfile

import pytest


def _identity():
    from trading_system.sources import SourceArtifactIdentity

    return SourceArtifactIdentity(
        symbol="FIXTURESYM", market_type="SPOT", interval="1m",
        period_start_utc="2026-05-01T00:00:00Z", period_end_utc="2026-05-01T04:00:00Z",
    )


def test_corrupted_minute_facts_source_fails_closed(fixture_artifacts, tmp_path):
    from trading_system.sources import SchemaViolationError
    from trading_system.sources.binance_spot_minute_facts_source import load_minute_facts

    bad_csv = tmp_path / "corrupted.csv"
    text = open(fixture_artifacts["facts_path"], encoding="utf-8").read()
    lines = text.splitlines()
    fields = lines[2].split(",")
    fields[2] = "NOT_A_DECIMAL"  # corrupt the open literal
    lines[2] = ",".join(fields)
    bad_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError):
        load_minute_facts(str(bad_csv), fixture_artifacts["sidecar_path"], identity=_identity())


def test_missing_kline_fails_closed(fixture_artifacts, tmp_path):
    from trading_system.sources import CoverageError
    from trading_system.sources.binance_spot_kline_ohlc_source import load_binance_spot_klines

    bad = tmp_path / "kline_gap.csv"
    lines = open(fixture_artifacts["klines_csv_path"], encoding="utf-8").read().splitlines()
    del lines[5]  # remove one minute -> coverage gap
    bad.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(CoverageError):
        load_binance_spot_klines(str(bad), identity=_identity())


def test_wrong_official_checksum_fails_closed(tmp_path):
    from field_runner import binance_kline_downloader as dl

    zip_path = tmp_path / "BTCUSDT-1m-2026-05.zip"
    zip_path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # minimal empty zip EOCD
    checksum_path = tmp_path / "BTCUSDT-1m-2026-05.zip.CHECKSUM"
    checksum_path.write_text("0" * 64 + "  BTCUSDT-1m-2026-05.zip\n", encoding="utf-8")
    with pytest.raises(dl.ChecksumMismatch):
        dl.verify_zip_checksum(str(zip_path), str(checksum_path))


def test_official_checksum_ok_on_matching_file(tmp_path):
    from field_runner import binance_kline_downloader as dl

    blob = b"official-artifact-bytes"
    zip_path = tmp_path / "BTCUSDT-1m-2026-05.zip"
    zip_path.write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    checksum_path = tmp_path / "BTCUSDT-1m-2026-05.zip.CHECKSUM"
    checksum_path.write_text(digest + "  BTCUSDT-1m-2026-05.zip\n", encoding="utf-8")
    assert dl.verify_zip_checksum(str(zip_path), str(checksum_path)) == digest


def test_source_inconsistency_fails_closed(fixture_artifacts, tmp_path):
    """Mutate exactly ONE kline row so cross-witness must raise
    SourceInconsistencyError (fail-closed; never averaged, never skipped)."""
    from trading_system.sources import SourceInconsistencyError
    from trading_system.sources.binance_spot_minute_facts_source import load_minute_facts
    from trading_system.sources.binance_spot_kline_ohlc_source import (
        cross_witness_sources,
        load_binance_spot_klines,
    )

    bad = tmp_path / "kline_mutated.csv"
    lines = open(fixture_artifacts["klines_csv_path"], encoding="utf-8").read().splitlines()
    fields = lines[3].split(",")
    fields[3] = str(float(fields[3]) - 1.0)  # mutate low only (row stays OHLC-legal)
    lines[3] = ",".join(fields)
    bad.write_text("\n".join(lines) + "\n", encoding="utf-8")

    identity = _identity()
    facts = load_minute_facts(
        fixture_artifacts["facts_path"], fixture_artifacts["sidecar_path"], identity=identity
    )
    klines = load_binance_spot_klines(str(bad), identity=identity)
    with pytest.raises(SourceInconsistencyError):
        cross_witness_sources(klines, facts)


def test_hash_mismatch_gate_fails_closed(fixture_artifacts, runner_config, tmp_path):
    """Owner-declared identity hashes are enforced fail-closed by the CLI."""
    import json

    from field_runner.runner_btc_may_2026 import main as runner_main

    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps({
        "swing_quantile": None, "sessions": [], "sample_size": 5,
        "htf_durations": ["1h"], "symbol": "FIXTURESYM", "year_month": "2026-05",
        "period_start_utc": "2026-05-01T00:00:00Z",
        "period_end_utc": "2026-05-01T04:00:00Z",
    }), encoding="utf-8")
    with pytest.raises(SystemExit):
        runner_main([
            "--config", str(cfg_path), "--data-dir", str(tmp_path),
            "--outdir", str(tmp_path / "out"),
            "--minute-facts", fixture_artifacts["facts_path"],
            "--minute-facts-sidecar", fixture_artifacts["sidecar_path"],
            "--klines-csv", fixture_artifacts["klines_csv_path"],
            "--expect-minute-facts-sha256", "0" * 64,
        ])

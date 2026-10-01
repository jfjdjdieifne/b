"""Runner integration tests: fixture roundtrip, outputs, leakage, determinism."""

from __future__ import annotations

import json
import os

import pandas as pd
import pytest


def _run_on_fixture(fixture_artifacts, runner_config, tmp_path, sample_size=12):
    from field_runner.pipeline import (
        build_evidence_and_narrative,
        load_sources,
        run_engines,
        seal_timeline,
    )
    from field_runner.sample import sample_manifest

    cfg = runner_config
    src = load_sources(
        facts_csv=fixture_artifacts["facts_path"],
        facts_sidecar=fixture_artifacts["sidecar_path"],
        klines_csv=fixture_artifacts["klines_csv_path"],
        config=cfg,
    )
    timeline, adapter, mh = seal_timeline(src["bundle"], "TEST_TIMELINE")
    sample_meta = sample_manifest(timeline.timeline_hash, timeline.bar_count, sample_size)
    statuses = []
    out = run_engines(market_history=mh, flow=src["flow"], config=cfg, statuses=statuses)
    ev = build_evidence_and_narrative(market_history=mh, engine_out=out, config=cfg, statuses=statuses)
    return src, timeline, adapter, mh, out, ev, statuses, tuple(sample_meta["positions"]), sample_meta


@pytest.fixture(scope="module")
def full_run(fixture_artifacts_module, runner_config, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("full_run")
    return _run_on_fixture(fixture_artifacts_module, runner_config, tmp)


@pytest.fixture(scope="module")
def fixture_artifacts_module(tmp_path_factory):
    from field_runner import fixtures as fixture_factory

    tmp = tmp_path_factory.mktemp("artifacts")
    return fixture_factory.write_fixture(str(tmp), n_minutes=240, ambiguous_minute=40)


def test_fixture_roundtrip_through_closed_adapters(fixture_artifacts, runner_config):
    from trading_system.sources.binance_spot_minute_facts_source import load_minute_facts
    from trading_system.sources.binance_spot_kline_ohlc_source import (
        assemble_canonical_bundle,
        cross_witness_sources,
        load_binance_spot_klines,
    )
    from trading_system.sources import SourceArtifactIdentity

    identity = SourceArtifactIdentity(
        symbol="FIXTURESYM", market_type="SPOT", interval="1m",
        period_start_utc="2026-05-01T00:00:00Z", period_end_utc="2026-05-01T04:00:00Z",
    )
    facts = load_minute_facts(
        fixture_artifacts["facts_path"], fixture_artifacts["sidecar_path"], identity=identity
    )
    klines = load_binance_spot_klines(fixture_artifacts["klines_csv_path"], identity=identity)
    witness = cross_witness_sources(klines, facts)
    bundle = assemble_canonical_bundle(klines, facts, cross_witness=witness)
    assert witness.compared_minutes == 240
    assert len(bundle.canonical_market_frame) == 240
    # canonical O/C comes from published kline EXCLUSIVELY (ambiguous stays flagged)
    assert bundle.canonical_market_frame["close"].notna().all()


def test_full_pipeline_smoke_all_outputs(full_run):
    src, timeline, adapter, mh, out, ev, statuses, positions, meta = full_run
    assert timeline.bar_count == 240
    assert positions == tuple(sorted(set(positions)))
    for key in ("volatility", "sessions", "fvg", "flow_proxy", "flow_actual",
                "absorption_actual", "absorption_proxy", "swings", "swing_sequence",
                "structure_breaks", "liquidity_levels", "order_blocks", "dealing_ranges"):
        assert key in out, key
    names = {s.name: s.status for s in statuses}
    assert names.get("swing_detector_2_1a") == "RAN"
    assert names.get("order_flow_actual_3_1") == "RAN"
    assert ev["actual"]["evidence_df"].shape[0] == 240
    assert ev["proxy"]["evidence_df"].shape[0] == 240
    assert len(ev["actual"]["narrative"].narrative_surface) == 240


def test_no_future_leakage_in_detection_audit(full_run):
    """Audit row facts must equal a pure PREFIX recompute (causal contract proof)."""
    from field_runner.pipeline import run_engines
    from field_runner import reporting as R

    src, timeline, adapter, mh, out, ev, statuses, positions, meta = full_run
    audit = R.build_detection_audit(
        market_history=mh, engine_out=out, evidence_actual=ev["actual"],
        narrative_actual=ev["actual"], flow=src["flow"],
        sample_positions=positions[:3], sample_meta=meta,
    )
    cfg = None
    for i in positions[:3]:
        prefix = mh.iloc[: i + 1]
        prefix_flow_frame = src["flow"].frame.iloc[: i + 1]
        # rebuild a flow view limited to the prefix (public frame, sliced)
        class _Flow:
            pass
        flow = _Flow()
        flow.frame = prefix_flow_frame
        import dataclasses
        from field_runner.pipeline import FieldRunConfig
        cfg_local = FieldRunConfig(
            swing_quantile=0.5,
            swing_prior_continuation_reversals=(0.005,),
            sessions=[{"name": "London", "timezone": "Europe/London",
                       "start_local": "08:00", "end_local": "09:00"}],
            symbol="FIXTURESYM", period_start_utc="2026-05-01T00:00:00Z",
            period_end_utc="2026-05-01T04:00:00Z",
        )
        pre = run_engines(market_history=prefix, flow=flow, config=cfg_local, statuses=[])
        row = audit[audit["sample_position"] == i].iloc[0]
        assert row["vol_true_range_percentile"] == pytest.approx(
            float(pre["volatility"]["true_range_percentile"].iloc[i])
        )
        assert row["structure_state_after"] == str(pre["structure_breaks"]["structure_state_after"].iloc[i])
        assert row["actual_delta_ratio"] == pytest.approx(float(pre["flow_actual"]["delta_ratio"].iloc[i]))
        assert row["proxy_volume_pressure_proxy"] == pytest.approx(
            float(pre["flow_proxy"]["volume_pressure_proxy"].iloc[i])
        )


def test_outcome_sample_separate_from_decision_facts(full_run):
    from field_runner import reporting as R

    src, timeline, adapter, mh, out, ev, statuses, positions, meta = full_run
    audit = R.build_detection_audit(
        market_history=mh, engine_out=out, evidence_actual=ev["actual"],
        narrative_actual=ev["actual"], flow=src["flow"],
        sample_positions=positions, sample_meta=meta,
    )
    film = R.build_outcome_film(
        market_history=mh, timeline=timeline, adapter=adapter, engine_out=out,
        evidence_actual=ev["actual"], narrative_actual=ev["actual"],
        sample_positions=positions, sample_meta=meta, timeline_id="TEST_TIMELINE",
    )
    forward_cols = [c for c in audit.columns if "forward" in c or "favorable" in c or "adverse" in c]
    assert forward_cols == [], forward_cols
    assert set(film["film_row_kind"]).issubset({"SAMPLE_FORWARD_PATH", "HYPOTHESIS_CONTRACT_TRAJECTORY"})
    assert (film["outcome_injection_guard"] == "OUTCOME_FILM_SEPARATE_FILE_NOT_IN_DECISION_SNAPSHOT").all()
    assert "timestamp_utc" in film.columns
    # film rows are keyed ONLY to the frozen sample timestamps
    assert set(film["sample_position"]).issubset(set(positions))


def test_deterministic_timestamp_sample(full_run):
    from field_runner.sample import select_sample_positions

    _, timeline, _, _, _, _, _, positions, meta = full_run
    again = select_sample_positions(timeline.timeline_hash, timeline.bar_count, meta["sample_size_parameter"])
    assert again == positions


def test_contract_trajectory_row_when_hypothesis_at_sample(full_run):
    """When a real hypothesis is created exactly at a sampled position the film
    must carry CLOSED Stage-2 contract excursions for it."""
    from field_runner import reporting as R

    src, timeline, adapter, mh, out, ev, statuses, positions, meta = full_run
    ledger = ev["actual"]["narrative"].hypothesis_ledger
    created = ledger[ledger["ledger_event_type"] == "CREATED"]
    assert len(created) > 0, "fixture must produce real hypotheses"
    hit = int(created["event_position"].iloc[0])
    film = R.build_outcome_film(
        market_history=mh, timeline=timeline, adapter=adapter, engine_out=out,
        evidence_actual=ev["actual"], narrative_actual=ev["actual"],
        sample_positions=(hit,), sample_meta=meta, timeline_id="TEST_TIMELINE",
    )
    contract_rows = film[film["film_row_kind"] == "HYPOTHESIS_CONTRACT_TRAJECTORY"]
    assert len(contract_rows) >= 1
    row = contract_rows.iloc[0]
    assert row["contract_excursion_available"] == "YES_CLOSED_STAGE2_PRICE_TRAJECTORY"
    assert row["running_favorable_excursion"] is not None
    assert float(row["running_favorable_excursion"]) >= 0.0
    assert float(row["running_adverse_excursion"]) >= 0.0


def test_rerun_deterministic_outputs(fixture_artifacts_module, runner_config, tmp_path):
    from field_runner.runner_btc_may_2026 import main as runner_main

    outs = []
    for run_id in ("a", "b"):
        cfg_path = tmp_path / f"cfg_{run_id}.json"
        cfg_path.write_text(json.dumps({
            "swing_quantile": 0.5,
            "swing_prior_continuation_reversals": [0.005],
            "sessions": [], "sample_size": 12, "htf_durations": ["1h"],
            "symbol": "FIXTURESYM", "year_month": "2026-05",
            "period_start_utc": "2026-05-01T00:00:00Z",
            "period_end_utc": "2026-05-01T04:00:00Z",
        }), encoding="utf-8")
        outdir = tmp_path / f"out_{run_id}"
        rc = runner_main([
            "--config", str(cfg_path),
            "--data-dir", str(tmp_path),
            "--outdir", str(outdir),
            "--minute-facts", fixture_artifacts_module["facts_path"],
            "--minute-facts-sidecar", fixture_artifacts_module["sidecar_path"],
            "--klines-csv", fixture_artifacts_module["klines_csv_path"],
            "--expect-minute-facts-sha256", fixture_artifacts_module["facts_sha256"],
            "--expect-aggtrades-sha256", fixture_artifacts_module["source_sha256"],
            "--expect-converter-sha256", fixture_artifacts_module["converter_sha256"],
        ])
        assert rc == 0
        outs.append(outdir)

    a, b = outs
    names = sorted(os.listdir(a))
    assert names == sorted(os.listdir(b))
    for name in names:
        if name == "MACHINE_VALIDATION.json":
            ja = json.load(open(a / name, encoding="utf-8"))
            jb = json.load(open(b / name, encoding="utf-8"))
            for key in ("runtime_seconds", "peak_memory"):
                ja.pop(key, None)
                jb.pop(key, None)
            ja.get("outputs_sha256", {}).pop("MACHINE_VALIDATION.json", None)
            jb.get("outputs_sha256", {}).pop("MACHINE_VALIDATION.json", None)
            assert ja == jb, name
        else:
            assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_no_model_pnl_signals_tokens(fixture_artifacts_module, runner_config, tmp_path):
    from field_runner.runner_btc_may_2026 import main as runner_main

    outdir = tmp_path / "out_scan"
    cfg_path = tmp_path / "cfg_scan.json"
    cfg_path.write_text(json.dumps({
        "swing_quantile": 0.5, "swing_prior_continuation_reversals": [0.005],
        "sessions": [], "sample_size": 8, "htf_durations": ["1h"],
        "symbol": "FIXTURESYM", "year_month": "2026-05",
        "period_start_utc": "2026-05-01T00:00:00Z",
        "period_end_utc": "2026-05-01T04:00:00Z",
    }), encoding="utf-8")
    rc = runner_main([
        "--config", str(cfg_path), "--data-dir", str(tmp_path), "--outdir", str(outdir),
        "--minute-facts", fixture_artifacts_module["facts_path"],
        "--minute-facts-sidecar", fixture_artifacts_module["sidecar_path"],
        "--klines-csv", fixture_artifacts_module["klines_csv_path"],
        "--expect-minute-facts-sha256", fixture_artifacts_module["facts_sha256"],
        "--expect-aggtrades-sha256", fixture_artifacts_module["source_sha256"],
        "--expect-converter-sha256", fixture_artifacts_module["converter_sha256"],
    ])
    assert rc == 0
    # Affirmative claim phrases must never appear. PnL/WIN/LOSS wording is allowed
    # ONLY inside explicit limitation/negation statements (owner-required notices).
    forbidden_claims = ("buy signal", "sell signal", "entry signal", "exit signal",
                        "trading signal", "take profit", "stop loss", "win rate",
                        "trained model", "profit =", "pnl =", "position size")
    import re
    for name in os.listdir(outdir):
        text = (outdir / name).read_text(encoding="utf-8", errors="ignore")
        low = text.lower()
        for token in forbidden_claims:
            assert token not in low, (name, token)
        for match in re.finditer(r"(win/loss|win_loss|\bpnl\b|profit)", low):
            window = low[max(0, match.start() - 60): match.start()]
            assert any(marker in window for marker in
                       ("no ", "no_", "not ", "never", "لا", "without", "forbidden",
                        "does not", "claim", "ليس", "ممنوع")), (name, match.group(0), window[-40:])

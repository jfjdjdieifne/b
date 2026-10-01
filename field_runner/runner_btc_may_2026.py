"""BTC May 2026 field runner — single-command entry (CLI).

Usage (from the package root):

    python run_btc_may_2026.py

or with explicit paths:

    python run_btc_may_2026.py --data-dir ./data --outdir ./outputs/btc_may_2026_reality

Behavior:
* resolves inputs (minute-facts CSV + sidecar JSON [+ optional raw aggTrades for
  provenance] + official 1m klines CSV/ZIP) — asking the owner for a local path
  (clear message) when the network is unavailable;
* runs the CLOSED pipeline through public APIs only;
* writes outputs/btc_may_2026_reality/ (A-F + chart_overlay.csv + entity CSVs).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

RUNNER_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.dirname(RUNNER_DIR)
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_root(explicit: str | None) -> str:
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates.append(os.path.join(PACKAGE_ROOT, "trading_project"))
    candidates.append(os.path.join(PACKAGE_ROOT, "project", "trading_project"))
    candidates.append(os.path.join(PACKAGE_ROOT, "..", "project", "trading_project"))
    for cand in candidates:
        cand = os.path.abspath(cand)
        if os.path.isfile(os.path.join(cand, "src", "trading_system", "__init__.py")):
            return cand
    raise SystemExit(
        "PROJECT_ROOT_NOT_FOUND: place trading_project/ next to this package or pass --project-root"
    )


def load_config(path: str | None):
    from field_runner.pipeline import FieldRunConfig

    cfg_path = path or os.path.join(RUNNER_DIR, "config", "field_run_config.json")
    if os.path.isfile(cfg_path):
        data = json.load(open(cfg_path, encoding="utf-8"))
        cfg = FieldRunConfig.from_dict(data)
    else:
        cfg = FieldRunConfig()
    return cfg, cfg_path


def detect_inputs(args, cfg):
    """ROLE-AWARE artifact discovery (PATCH: never substring-ambiguous).

    Roles are disjoint and explicit:
      MINUTE_FACTS_CSV  - the converted minute-facts artifact (role wins even if
                          its filename contains 'aggTrades' substring).
      MINUTE_FACTS_SIDECAR - its sidecar JSON (provenance chain).
      RAW_AGGTRADES     - the raw aggTrades CSV, OPTIONAL in FAST mode.

    Order: explicit CLI paths first, then sidecar-driven minute-facts discovery,
    then a separate raw pattern. More than one candidate inside a role is
    fail-closed with the candidate paths shown.
    """
    data_dir = os.path.abspath(args.data_dir or os.path.join(PACKAGE_ROOT, "data"))
    listing = sorted(os.listdir(data_dir)) if os.path.isdir(data_dir) else []

    def is_klines_name(low: str) -> bool:
        return ("-1m-" in low) or ("kline" in low)

    # ---- MINUTE_FACTS role ----
    facts = args.minute_facts
    if facts is not None:
        facts = os.path.abspath(facts)
        if not os.path.isfile(facts):
            raise SystemExit(f"MINUTE_FACTS_FILE_NOT_FOUND:{facts}")
    else:
        candidates = []
        # (a) sidecar-driven discovery: sidecar JSON names point to their CSV.
        sidecar_named = [n for n in listing if n.lower().endswith(".json") and "sidecar" in n.lower()]
        for sc_name in sidecar_named:
            stem = sc_name
            for suffix in (".sidecar.json", ".json"):
                if stem.lower().endswith(suffix):
                    stem = stem[: -len(suffix)]
                    break
            guess = stem + ".csv"
            if guess in listing:
                candidates.append(guess)
        # (b) name pattern: 'minute' marks the minute-facts role (NOT raw, even
        #     when the same filename also contains 'aggTrades' substring).
        for name in listing:
            low = name.lower()
            if low.endswith(".csv") and "minute" in low and not is_klines_name(low):
                candidates.append(name)
        candidates = sorted(set(candidates))
        if len(candidates) > 1:
            paths = [os.path.join(data_dir, c) for c in candidates]
            raise SystemExit("MINUTE_FACTS_AMBIGUOUS: multiple candidates: " + "; ".join(paths))
        if candidates:
            facts = os.path.join(data_dir, candidates[0])

    if facts is None:
        raise SystemExit(
            "MINUTE_FACTS_FILE_REQUIRED: place the minute-facts CSV (with its sidecar JSON) "
            f"in {data_dir} or pass --minute-facts PATH --minute-facts-sidecar PATH. "
            "Expected identity: sha256 a6a06c4c... (owner artifact) — the runner verifies it."
        )

    # ---- MINUTE_FACTS_SIDECAR role ----
    sidecar = args.minute_facts_sidecar
    if sidecar is not None:
        sidecar = os.path.abspath(sidecar)
        if not os.path.isfile(sidecar):
            raise SystemExit(f"SIDECAR_FILE_NOT_FOUND:{sidecar}")
    else:
        stem = facts[:-4] if facts.lower().endswith(".csv") else facts
        paired = [stem + ".sidecar.json", facts + ".sidecar.json"]
        candidates = [p for p in paired if os.path.isfile(p)]
        facts_name = os.path.basename(facts)
        for name in listing:
            low = name.lower()
            if low.endswith(".json") and "sidecar" in low:
                stem_token = os.path.basename(stem).lower()
                if stem_token in low or low.startswith(stem_token[:12]):
                    candidates.append(os.path.join(data_dir, name))
        uniq = sorted(set(candidates))
        if len(uniq) > 1:
            raise SystemExit("SIDECAR_AMBIGUOUS: multiple candidates: " + "; ".join(uniq))
        sidecar = uniq[0] if uniq else None
    if sidecar is None:
        raise SystemExit("SIDECAR_FILE_REQUIRED: pass --minute-facts-sidecar PATH")

    # ---- RAW_AGGTRADES role (separate pattern; minute-facts is NEVER raw) ----
    raw = args.aggtrades
    if raw is not None:
        raw = os.path.abspath(raw)
        if not os.path.isfile(raw):
            raise SystemExit(f"RAW_AGGTRADES_FILE_NOT_FOUND:{raw}")
    else:
        claimed = {os.path.abspath(facts), os.path.abspath(sidecar)}
        candidates = []
        for name in listing:
            low = name.lower()
            if not low.endswith(".csv") or is_klines_name(low):
                continue
            if os.path.abspath(os.path.join(data_dir, name)) in claimed:
                continue
            if "minute" in low:
                continue  # minute-facts role wins even if name contains 'aggTrades'
            if "aggtrade" in low:
                candidates.append(name)
        candidates = sorted(set(candidates))
        if len(candidates) > 1:
            paths = [os.path.join(data_dir, c) for c in candidates]
            raise SystemExit("RAW_AGGTRADES_AMBIGUOUS: multiple candidates: " + "; ".join(paths))
        raw = os.path.join(data_dir, candidates[0]) if candidates else None

    return data_dir, facts, sidecar, raw


def load_sidecar_json(path: str) -> dict:
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"SIDECAR_JSON_INVALID:{path}:{type(exc).__name__}")
    if not isinstance(data, dict):
        raise SystemExit(f"SIDECAR_JSON_INVALID:{path}:NOT_AN_OBJECT")
    return data


def obtain_klines(args, cfg, data_dir):
    from field_runner import binance_kline_downloader as dl

    if args.klines_csv:
        return {
            "csv_path": os.path.abspath(args.klines_csv),
            "zip_path": None,
            "checksum_path": None,
            "zip_sha256": None,
            "source_url": None,
            "acquisition": "OWNER_LOCAL_CSV",
            "contract": dl.CONTRACT,
        }
    if args.klines_zip:
        zip_path = os.path.abspath(args.klines_zip)
        checksum_path = os.path.abspath(args.klines_checksum) if args.klines_checksum else zip_path + ".CHECKSUM"
        verified = dl.verify_zip_checksum(zip_path, checksum_path)
        csv_path = dl.extract_klines_csv(zip_path, os.path.join(data_dir, "klines_cache"))
        return {
            "csv_path": csv_path, "zip_path": zip_path, "checksum_path": checksum_path,
            "zip_sha256": verified, "source_url": None,
            "acquisition": "OWNER_LOCAL_ZIP_CHECKSUM_VERIFIED", "contract": dl.CONTRACT,
        }
    cache_dir = args.kline_cache_dir or os.path.join(data_dir, "klines_cache")
    try:
        info = dl.ensure_monthly_klines(
            symbol=cfg.symbol, year_month=cfg.year_month, download_dir=cache_dir
        )
        info["acquisition"] = "DOWNLOADED_FROM_DATA_BINANCE_VISION_CHECKSUM_VERIFIED"
        return info
    except dl.LocalFileRequired as exc:
        raise SystemExit(str(exc))


def verify_manifest(project_root: str) -> dict:
    manifest = os.path.join(project_root, "MANIFEST.sha256")
    ok = bad = 0
    bad_lines = []
    for line in open(manifest, encoding="utf-8"):
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        want, rel = parts
        rel = rel.lstrip("./")
        path = os.path.join(project_root, rel)
        got = _sha256_file(path) if os.path.isfile(path) else None
        if got == want:
            ok += 1
        else:
            bad += 1
            bad_lines.append(rel)
    return {
        "manifest_path": "MANIFEST.sha256",
        "manifest_sha256": _sha256_file(manifest),
        "manifest_lines": sum(1 for _ in open(manifest, encoding="utf-8")),
        "ok": ok,
        "bad": bad,
        "bad_paths": bad_lines,
    }


def _gate_fail(msg: str, args, warnings: list) -> None:
    """Fail-closed identity gate. --allow-hash-mismatch is an explicit owner
    override only (never used by tests as a fix); it records the mismatch."""
    if not args.allow_hash_mismatch:
        raise SystemExit(msg + " (artifact-role gate; owner: verify the file — do not bypass)")
    warnings.append(msg)


def main(argv=None) -> int:
    started_at = time.time()
    parser = argparse.ArgumentParser(description="BTC May 2026 local field runner")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--outdir", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--minute-facts", default=None)
    parser.add_argument("--minute-facts-sidecar", default=None)
    parser.add_argument("--aggtrades", default=None)
    parser.add_argument("--klines-csv", default=None)
    parser.add_argument("--klines-zip", default=None)
    parser.add_argument("--klines-checksum", default=None)
    parser.add_argument("--kline-cache-dir", default=None)
    parser.add_argument("--expect-aggtrades-sha256",
                        default="86d4f3d335ae244dcc143569bd1cc382320027c3fe4702e5d3ddf0757e8f1c04")
    parser.add_argument("--expect-minute-facts-sha256",
                        default="a6a06c4c583e64e7613ddca275533a15062ab13864482cacf30b2f125094601f")
    parser.add_argument("--expect-converter-sha256",
                        default="0048779bd821dbe6f3cda66517b19e7435fc0b98592ee9aa1980804fe27efb5d")
    parser.add_argument("--mode", choices=("fast", "raw"), default="fast",
                        help="fast: raw aggTrades optional (identity via sidecar provenance chain); "
                             "raw: the raw aggTrades file MUST be present and hash-verified")
    parser.add_argument("--allow-hash-mismatch", action="store_true",
                        help="owner override: report mismatch instead of failing (recorded in MACHINE_VALIDATION)")
    args = parser.parse_args(argv)

    project_root = resolve_project_root(args.project_root)
    sys.path.insert(0, os.path.join(project_root, "src"))
    sys.path.insert(0, RUNNER_DIR)

    cfg, cfg_path = load_config(args.config)
    outdir = os.path.abspath(args.outdir or os.path.join(PACKAGE_ROOT, "outputs", "btc_may_2026_reality"))
    os.makedirs(outdir, exist_ok=True)

    from field_runner.pipeline import (
        FieldPipelineError,
        build_evidence_and_narrative,
        load_sources,
        run_engines,
        seal_timeline,
    )
    from field_runner import reporting as R
    from field_runner.sample import sample_manifest

    failures: list = []
    warnings: list = []

    def say(msg: str) -> None:
        import time as _t
        print(f"[{_t.strftime('%H:%M:%S')}] {msg}", flush=True)

    say("BTC MAY 2026 FIELD RUNNER starting")
    say("NOTE: the certified CLOSED engines use expanding-history empirical percentiles.")
    say("      runtime depends on dataset and certified engine implementation; stage timings are reported below.")
    say("      Each stage below prints its own timing so you can see progress; nothing is written until the end.")
    data_dir, facts_csv, sidecar_path, aggtrades = detect_inputs(args, cfg)
    say(f"STEP inputs: minute_facts={os.path.basename(facts_csv)} sidecar={os.path.basename(sidecar_path)} raw={os.path.basename(aggtrades) if aggtrades else 'ABSENT (FAST mode, provenance via sidecar)'}")
    sidecar_data = load_sidecar_json(sidecar_path)

    # ---- artifact-ROLE identity gates (fail-closed, artifact-specific names) ----
    # MINUTE_FACTS role.
    facts_sha = _sha256_file(facts_csv)
    if args.expect_minute_facts_sha256 and facts_sha != args.expect_minute_facts_sha256:
        _gate_fail(
            f"MINUTE_FACTS_HASH_MISMATCH expected={args.expect_minute_facts_sha256} actual={facts_sha}",
            args, warnings,
        )
    sc_out = str(sidecar_data.get("output_csv_sha256", ""))
    if sc_out != facts_sha:
        _gate_fail(
            f"SIDECAR_OUTPUT_BINDING_MISMATCH sidecar.output_csv_sha256={sc_out} minute_facts_csv_sha256={facts_sha}",
            args, warnings,
        )
    # RAW_AGGTRADES identity via the sidecar provenance chain (FAST mode) and/or
    # the raw file itself (RAW mode / raw present).
    sc_src = str(sidecar_data.get("source_sha256", ""))
    if args.expect_aggtrades_sha256 and sc_src != args.expect_aggtrades_sha256:
        _gate_fail(
            f"SIDECAR_SOURCE_BINDING_MISMATCH sidecar.source_sha256={sc_src} expected_raw_aggtrades_sha256={args.expect_aggtrades_sha256}",
            args, warnings,
        )
    sc_conv = str(sidecar_data.get("converter_sha256", ""))
    if args.expect_converter_sha256 and sc_conv != args.expect_converter_sha256:
        _gate_fail(
            f"CONVERTER_BINDING_MISMATCH sidecar.converter_sha256={sc_conv} expected_converter_sha256={args.expect_converter_sha256}",
            args, warnings,
        )
    aggtrades_sha = None
    if aggtrades:
        aggtrades_sha = _sha256_file(aggtrades)
        if args.expect_aggtrades_sha256 and aggtrades_sha != args.expect_aggtrades_sha256:
            _gate_fail(
                f"RAW_AGGTRADES_HASH_MISMATCH expected={args.expect_aggtrades_sha256} actual={aggtrades_sha}",
                args, warnings,
            )
    elif args.mode == "raw":
        raise SystemExit(
            "RAW_AGGTRADES_FILE_REQUIRED: mode=raw requires the raw aggTrades CSV "
            "(pass --aggtrades PATH or place it in data/). Use --mode fast to rely on the "
            "sidecar provenance chain instead."
        )
    # FAST mode: the raw file need NOT exist; its identity is proven by the
    # sidecar provenance chain (source_sha256 bound to the expected raw hash).

    say("STEP identity gates passed (artifact-role hashes + sidecar bindings)")
    kline_info = obtain_klines(args, cfg, data_dir)
    klines_sha = _sha256_file(kline_info["csv_path"])
    say(f"STEP klines ready: {os.path.basename(kline_info['csv_path'])} (acquisition={kline_info.get('acquisition')})")

    say("STEP loading sources through CLOSED adapters (validate + cross-witness + canonical) ...")
    import time as _t
    _t0 = _t.time()
    sources = load_sources(
        facts_csv=facts_csv,
        facts_sidecar=sidecar_path,
        klines_csv=kline_info["csv_path"],
        config=cfg,
        expected_facts_sha256=args.expect_minute_facts_sha256 or None,
        expected_klines_sha256=klines_sha,
        expected_raw_source_sha256=args.expect_aggtrades_sha256 or None,
        expected_converter_sha256=args.expect_converter_sha256 or None,
    )
    say(f"STEP sources loaded + exact cross-witness OK ({len(sources['facts'].exact_frame)} minutes) in {_t.time()-_t0:.1f}s")
    timeline_id = f"BINANCE_SPOT_{cfg.symbol}_1M_{cfg.period_start_utc}"
    timeline, adapter, market_history = seal_timeline(sources["bundle"], timeline_id)

    say("STEP sealing MarketObservationTimeline (consumer-side public seal) ...")
    _t0 = _t.time()
    # ---- deterministic sample BEFORE any detector output ----
    sample_meta = sample_manifest(timeline.timeline_hash, timeline.bar_count, cfg.sample_size)
    sample_positions = tuple(sample_meta["positions"])

    say(f"STEP timeline sealed: {timeline.bar_count} bars in {_t.time()-_t0:.1f}s (hash {timeline.timeline_hash[:16]}...)")
    say(f"STEP deterministic sample selected: {sample_meta['sample_size_realized']} timestamps")
    say("STEP running CLOSED engines (this is the long stage) ...")
    _t0 = _t.time()
    statuses: list = []
    engine_out = run_engines(
        market_history=market_history, flow=sources["flow"], config=cfg, statuses=statuses
    )
    say(f"STEP engines finished in {_t.time()-_t0:.1f}s")
    say("STEP evidence vectors + narrative (ACTUAL and PROXY, kept separate) ...")
    _t0 = _t.time()
    evidence_results = build_evidence_and_narrative(
        market_history=market_history, engine_out=engine_out, config=cfg, statuses=statuses
    )

    say(f"STEP evidence+narrative finished in {_t.time()-_t0:.1f}s")
    say("STEP building DETECTION_AUDIT.csv (as-of sample) ...")
    _t0 = _t.time()
    audit_df = R.build_detection_audit(
        market_history=market_history,
        engine_out=engine_out,
        evidence_actual=evidence_results["actual"],
        narrative_actual=evidence_results["actual"],
        flow=sources["flow"],
        sample_positions=sample_positions,
        sample_meta=sample_meta,
    )
    say(f"STEP audit done in {_t.time()-_t0:.1f}s")
    say("STEP building OUTCOME_FILM_SAMPLE.csv (separate outcome-side view) ...")
    _t0 = _t.time()
    film_df = R.build_outcome_film(
        market_history=market_history,
        timeline=timeline,
        adapter=adapter,
        engine_out=engine_out,
        evidence_actual=evidence_results["actual"],
        narrative_actual=evidence_results["actual"],
        sample_positions=sample_positions,
        sample_meta=sample_meta,
        timeline_id=timeline_id,
    )
    say(f"STEP outcome film done in {_t.time()-_t0:.1f}s")
    say("STEP building chart_overlay.csv + entity exports + reality preview ...")
    _t0 = _t.time()
    chart_df = R.build_chart_overlay(market_history=market_history, engine_out=engine_out)
    preview = R.reality_preview(
        market_history=market_history, engine_out=engine_out,
        narrative_actual=evidence_results["actual"], film_df=film_df,
    )

    source_info = {
        "minute_facts_csv": os.path.abspath(facts_csv),
        "minute_facts_sha256": facts_sha,
        "minute_facts_sidecar": os.path.abspath(sidecar_path),
        "minute_facts_sidecar_sha256": _sha256_file(sidecar_path),
        "raw_aggtrades_csv": os.path.abspath(aggtrades) if aggtrades else None,
        "raw_aggtrades_sha256": aggtrades_sha,
        "facts_provenance": {
            "raw_source_sha256": sources["facts"].provenance.raw_source_sha256,
            "converter_name": sources["facts"].provenance.converter_name,
            "minute_facts_sha256": sources["facts"].provenance.minute_facts_sha256,
        },
        "cross_witness": {
            "compared_minutes": sources["cross_witness"].compared_minutes,
            "result": "EXACT_MATCH_FAIL_CLOSED_ENFORCED",
        },
    }
    kline_info_out = dict(kline_info)
    kline_info_out["klines_csv_sha256"] = klines_sha
    kline_info_out["ohlc_source_label"] = sources["klines"].provenance.ohlc_source_label

    say(f"STEP chart/entities/preview done in {_t.time()-_t0:.1f}s")
    say("STEP writing outputs (SUMMARY / MACHINE_VALIDATION / README) ...")
    summary = R.build_summary(
        config=cfg, source_info=source_info, timeline=timeline, engine_out=engine_out,
        statuses=statuses, evidence_results=evidence_results,
        narrative_actual=evidence_results["actual"], sample_meta=sample_meta,
        preview=preview, minute_count=len(sources["facts"].exact_frame),
        kline_info=kline_info_out,
    )

    outputs = {}
    outputs["SUMMARY.json"] = os.path.join(outdir, "SUMMARY.json")
    json.dump(summary, open(outputs["SUMMARY.json"], "w", encoding="utf-8"),
              indent=1, sort_keys=True, default=str)
    outputs["DETECTION_AUDIT.csv"] = R._write_csv(os.path.join(outdir, "DETECTION_AUDIT.csv"), audit_df)
    outputs["OUTCOME_FILM_SAMPLE.csv"] = R._write_csv(os.path.join(outdir, "OUTCOME_FILM_SAMPLE.csv"), film_df)
    outputs["chart_overlay.csv"] = R._write_csv(os.path.join(outdir, "chart_overlay.csv"), chart_df)
    for name, frame in R.build_entity_exports(engine_out=engine_out).items():
        outputs[name] = R._write_csv(os.path.join(outdir, name), frame)

    manifest_result = verify_manifest(project_root)

    runner_files = {}
    for root, _, files in os.walk(RUNNER_DIR):
        for fn in sorted(files):
            if fn.endswith((".py", ".json", ".bat", ".txt")):
                p = os.path.join(root, fn)
                runner_files[os.path.relpath(p, PACKAGE_ROOT).replace("\\", "/")] = _sha256_file(p)

    engine_modules = {}
    import trading_system  # noqa: F401
    for mod_name in (
        "trading_system.sources.binance_spot_minute_facts_source",
        "trading_system.sources.binance_spot_kline_ohlc_source",
        "trading_system.sources.binance_executed_flow_source",
        "trading_system.environment.dynamic_volatility",
        "trading_system.environment.session_context",
        "trading_system.structure.swing_detector",
        "trading_system.structure.swing_sequence",
        "trading_system.structure.structural_breaks",
        "trading_system.liquidity.liquidity_map",
        "trading_system.orderflow.volume_delta",
        "trading_system.orderflow.absorption",
        "trading_system.zones.order_blocks",
        "trading_system.zones.fvg",
        "trading_system.zones.dealing_range",
        "trading_system.multitimeframe.causal_htf",
        "trading_system.decision.evidence_vector",
        "trading_system.decision.narrative",
        "trading_system.research.trajectory.trajectory_contract",
        "trading_system.research.trajectory.trajectory_stage2",
    ):
        import importlib
        mod = importlib.import_module(mod_name)
        engine_modules[mod_name] = {
            "module_file_sha256": _sha256_file(mod.__file__),
            "public_classes": [n for n in dir(mod) if n[:1].isupper() and not n.startswith("_")],
        }

    outputs_hashed = {}
    for name, path in sorted(outputs.items()):
        outputs_hashed[name] = _sha256_file(path)

    machine = R.build_machine_validation(
        runner_files=runner_files,
        config=cfg,
        source_paths_and_hashes={
            "minute_facts_csv": facts_sha,
            "minute_facts_sidecar": _sha256_file(sidecar_path),
            "raw_aggtrades_csv": aggtrades_sha,
            "klines_csv": klines_sha,
            "klines_zip": kline_info.get("zip_sha256"),
        },
        engine_modules=engine_modules,
        output_paths=outputs_hashed,
        statuses=statuses,
        started_at=started_at,
        failures=failures,
        warnings=warnings,
        manifest_result=manifest_result,
        adapter_identity={
            "seal": "docs/releases/MODULE_BINANCE_SOURCE_ADAPTER_V1_ACCEPTED_SRC_TESTS.sha256",
            "milestone": "docs/releases/MILESTONE_BINANCE_SOURCE_ADAPTER_V1_CLOSED.md",
            "state": "CLOSED",
            "tie_order_contract": "NOT_PROVEN",
        },
    )
    outputs["MACHINE_VALIDATION.json"] = os.path.join(outdir, "MACHINE_VALIDATION.json")
    json.dump(machine, open(outputs["MACHINE_VALIDATION.json"], "w", encoding="utf-8"),
              indent=1, sort_keys=True, default=str)

    readme_path = os.path.join(outdir, "README_RESULT_AR.txt")
    R.write_readme_ar(readme_path, summary=summary, machine=machine,
                      out_names=sorted(os.listdir(outdir)))
    outputs["README_RESULT_AR.txt"] = readme_path

    # refresh output hashes to include README (MACHINE_VALIDATION cannot hash itself)
    machine.setdefault("outputs_sha256", {})["README_RESULT_AR.txt"] = _sha256_file(outputs["README_RESULT_AR.txt"])
    json.dump(machine, open(outputs["MACHINE_VALIDATION.json"], "w", encoding="utf-8"),
              indent=1, sort_keys=True, default=str)

    say("STEP all outputs written")
    print("FIELD RUN COMPLETE")
    print(f"outdir: {outdir}")
    print(f"timeline bars: {timeline.bar_count} | sample size: {sample_meta['sample_size_realized']}")
    print(f"branch statuses: {summary['status_counts']}")
    print(f"NOT_CONFIGURED items: {summary['not_configured_items']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

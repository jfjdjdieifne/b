# -*- coding: utf-8 -*-
"""Adversarial tests: binance_spot_minute_facts_source (SOURCE ADAPTER V1).

Manual fixtures only. Instance fingerprints of the owner's real run are used
NOWHERE in production modules — only inside these fixtures when needed.
"""

import ast
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from trading_system.sources import (
    CoverageError,
    ProvenanceMismatchError,
    SchemaViolationError,
    SourceArtifactIdentity,
)
from trading_system.sources.binance_spot_minute_facts_source import (
    MINUTE_FACTS_COLUMNS,
    MinuteFactsExpectedProvenance,
    load_minute_facts,
)

MINUTE = 60_000_000
REPO_SOURCES = Path(__file__).resolve().parents[1] / "src" / "trading_system" / "sources"
PRODUCTION_FILES = [
    REPO_SOURCES / "__init__.py",
    REPO_SOURCES / "binance_spot_minute_facts_source.py",
    REPO_SOURCES / "binance_spot_kline_ohlc_source.py",
    REPO_SOURCES / "binance_executed_flow_source.py",
]


def us(iso):
    return int(pd.Timestamp(iso, tz="UTC").value // 1000)


def iso_of(us_val):
    return pd.Timestamp(us_val, unit="us", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S")


T0 = us("2025-03-02T00:00:00")

SPEC = [
    # start, open, high, low, close, base, quote, count, buy_b, sell_b, buy_q, sell_q, amb_o, amb_c
    ("100.50000000", "101.00000000", "100.00000000", "100.75000000", "0.50000000", "50.25000000", 3, "0.30000000", "0.20000000", "30.15000000", "20.10000000", "0", "0", "1", "1"),
    ("100.75000000", "102.00000000", "100.50000000", "101.50000000", "0.40000000", "40.60000000", 2, "0.25000000", "0.15000000", "25.37500000", "15.22500000", "0", "0", "1", "1"),
    ("99.75000000", "101.00000000", "99.00000000", "100.25000000", "0.60000000", "59.70000000", 4, "0.35000000", "0.25000000", "34.80000000", "24.90000000", "1", "1", "2", "2"),
    ("100.25000000", "100.90000000", "100.10000000", "100.60000000", "0.20000000", "20.10000000", 1, "0.20000000", "0.00000000", "20.10000000", "0.00000000", "0", "0", "1", "1"),
    ("100.60000000", "101.20000000", "100.40000000", "101.00000000", "0.30000000", "30.30000000", 2, "0.10000000", "0.20000000", "10.05000000", "20.25000000", "0", "0", "1", "1"),
    ("101.00000000", "101.50000000", "100.80000000", "101.25000000", "0.35000000", "35.43750000", 2, "0.15000000", "0.20000000", "15.18750000", "20.25000000", "0", "0", "1", "1"),
]


def facts_row(i, spec):
    (o, h, l, c, base, quote, count, buy_b, sell_b, buy_q, sell_q, amb_o, amb_c, d_o, d_c) = spec
    start = T0 + i * MINUTE
    end = start + MINUTE
    delta_b = str(Decimal(buy_b) - Decimal(sell_b))
    delta_q = str(Decimal(buy_q) - Decimal(sell_q))
    return ",".join(
        [iso_of(start), iso_of(end), o, h, l, c, base, quote, str(count),
         buy_b, sell_b, buy_q, sell_q, delta_b, delta_q,
         str(1000 + i), str(1000 + i), str(start), str(start + 1000),
         amb_o, amb_c, d_o, d_c]
    )


def build_sidecar(rows_lit, csv_text, *, sentinel=0, missing_declared=0, intervals=None):
    n = len(rows_lit)
    total_base = sum((Decimal(r["base_volume"]) for r in rows_lit), Decimal(0))
    total_quote = sum((Decimal(r["quote_volume"]) for r in rows_lit), Decimal(0))
    total_count = sum(int(r["agg_trade_count"]) for r in rows_lit)
    amb_o = sum(1 for r in rows_lit if r["open_ambiguous"] == "1")
    amb_c = sum(1 for r in rows_lit if r["close_ambiguous"] == "1")
    return {
        "converter_name": "aggtrades_to_minute_facts",
        "converter_version": "1.0.0",
        "converter_sha256": hashlib.sha256(b"converter-fixture").hexdigest(),
        "source_sha256": hashlib.sha256(b"raw-aggtrades-fixture").hexdigest(),
        "source_contract": "BINANCE_SPOT_PUBLIC_DATA_AGGTRADES",
        "timestamp_unit": "MICROSECONDS",
        "source_rows_total": total_count + sentinel,
        "legal_rows_consumed": total_count,
        "official_invalid_sentinel_count": sentinel,
        "rejected_corrupt_rows": 0,
        "output_minute_count": n,
        "covered_calendar_minute_count": n + missing_declared,
        "missing_minute_count": missing_declared,
        "missing_minute_intervals": intervals if intervals is not None else [],
        "first_output_minute": rows_lit[0]["minute_start_utc"] if rows_lit else None,
        "last_output_minute": rows_lit[-1]["minute_start_utc"] if rows_lit else None,
        "is_best_match_true_count": total_count,
        "is_best_match_false_count": 0,
        "is_best_match_invalid_count": 0,
        "tie_timestamp_count": 7,
        "ambiguous_open_minute_count": amb_o,
        "ambiguous_close_minute_count": amb_c,
        "TIE_ORDER_CONTRACT": "NOT_PROVEN",
        "tie_order_evidence": "evidence-fixture",
        "tie_order_policy": "AMBIGUITY_METADATA fixture",
        "bar_close_availability": "NOT_CLAIMED_BY_CONVERTER",
        "numeric_representation": "INTEGER_FIXED_POINT fixture",
        "reconciliation": {
            "source_base_sum": str(total_base),
            "output_base_sum": str(total_base),
            "source_quote_sum": str(total_quote),
            "output_quote_sum": str(total_quote),
            "exact_match_base": True,
            "exact_match_quote": True,
            "buy_plus_sell_base_matches_total": True,
            "buy_plus_sell_quote_matches_total": True,
            "sum_agg_trade_count_matches_legal_source_rows": True,
        },
        "output_csv_sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "generated_at_utc": "2026-09-27T00:00:00.000Z",
        "historical_provenance_statement": "fixture statement",
    }


def write_artifact(tmp_path, spec=SPEC, *, positions=None, symbol="GENSYM1", period=("2025-03-02T00:00:00Z", "2025-03-02T00:10:00Z")):
    rows_lit = []
    lines = []
    for i, s in zip(positions if positions is not None else range(len(spec)), spec):
        (o, h, l, c, base, quote, count, buy_b, sell_b, buy_q, sell_q, amb_o, amb_c, d_o, d_c) = s
        start = T0 + i * MINUTE
        rows_lit.append({
            "minute_start_utc": iso_of(start), "minute_end_utc": iso_of(start + MINUTE),
            "open": o, "high": h, "low": l, "close": c,
            "base_volume": base, "quote_volume": quote, "agg_trade_count": str(count),
            "buy_initiated_base_volume": buy_b, "sell_initiated_base_volume": sell_b,
            "buy_initiated_quote_volume": buy_q, "sell_initiated_quote_volume": sell_q,
            "executed_base_delta": str(Decimal(buy_b) - Decimal(sell_b)),
            "executed_quote_delta": str(Decimal(buy_q) - Decimal(sell_q)),
            "first_agg_trade_id": str(1000 + i), "last_agg_trade_id": str(1000 + i),
            "first_transact_time_us": str(start), "last_transact_time_us": str(start + 1000),
            "open_ambiguous": amb_o, "close_ambiguous": amb_c,
            "open_tie_distinct_prices": d_o, "close_tie_distinct_prices": d_c,
        })
        lines.append(facts_row(i, s))
    csv_text = ",".join(MINUTE_FACTS_COLUMNS) + "\n" + "\n".join(lines) + ("\n" if lines else "")
    csv_path = tmp_path / "facts.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    # recompute calendar gaps for the sidecar declaration (never lie to the loader)
    missing_declared = 0
    intervals = []
    for prev, cur in zip(rows_lit, rows_lit[1:]):
        gap = int(pd.Timestamp(cur["minute_start_utc"], tz="UTC").value // 1000) - \
            int(pd.Timestamp(prev["minute_start_utc"], tz="UTC").value // 1000)
        n_missing = gap // MINUTE - 1
        if n_missing > 0:
            missing_declared += n_missing
            intervals.append([prev["minute_end_utc"], cur["minute_start_utc"]])
    sidecar = build_sidecar(rows_lit, csv_text, missing_declared=missing_declared, intervals=intervals)
    sidecar_path = tmp_path / "facts.sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    identity = SourceArtifactIdentity(
        symbol=symbol, market_type="SPOT", interval="1m",
        period_start_utc=period[0], period_end_utc=period[1],
    )
    return str(csv_path), str(sidecar_path), identity, rows_lit, sidecar


def test_01_valid_schema_loads(tmp_path):
    csv_p, sc_p, identity, rows_lit, _ = write_artifact(tmp_path)
    src = load_minute_facts(csv_p, sc_p, identity=identity)
    assert len(src.exact_frame) == 6
    assert str(src.exact_frame.index.tz) == "UTC"
    assert list(src.exact_frame.columns[:2]) == ["minute_start_us", "minute_end_us"]
    # witness labeling: no canonical open/close columns in the facts frame
    assert "open" not in src.exact_frame.columns and "close" not in src.exact_frame.columns
    assert "reconstructed_open_witness" in src.exact_frame.columns
    assert "reconstructed_close_witness" in src.exact_frame.columns
    assert "open" not in src.frame.columns and "close" not in src.frame.columns
    assert src.provenance.legal_rows_consumed == 14


def test_02_malformed_schema_failclosed(tmp_path):
    csv_p, sc_p, identity, rows_lit, sc = write_artifact(tmp_path)
    good = Path(csv_p).read_text()
    # bad header
    p = tmp_path / "bad_header.csv"
    p.write_text(good.replace("minute_start_utc", "minute_start", 1))
    with pytest.raises(SchemaViolationError):
        load_minute_facts(str(p), sc_p, identity=identity)
    # bad field count
    p2 = tmp_path / "bad_fields.csv"
    lines = good.splitlines()
    lines[2] = lines[2].replace(",", " ", 1)
    p2.write_text("\n".join(lines) + "\n")
    with pytest.raises(SchemaViolationError):
        load_minute_facts(str(p2), sc_p, identity=identity)
    # bad decimal literal (exponent)
    p3 = tmp_path / "bad_dec.csv"
    p3.write_text(good.replace("100.75000000", "1e2", 1))
    with pytest.raises(SchemaViolationError):
        load_minute_facts(str(p3), sc_p, identity=identity)
    # bad int literal
    p4 = tmp_path / "bad_int.csv"
    p4.write_text(good.replace("1000,1000", "1000.5,1000.5", 1))
    with pytest.raises(SchemaViolationError):
        load_minute_facts(str(p4), sc_p, identity=identity)
    # corrupted accounting (buy+sell != total)
    p5 = tmp_path / "bad_accounting.csv"
    p5.write_text(good.replace("0.30000000,0.20000000", "0.30000000,0.10000000", 1))
    with pytest.raises(SchemaViolationError):
        load_minute_facts(str(p5), sc_p, identity=identity)


def test_03_wrong_symbol(tmp_path):
    with pytest.raises(SchemaViolationError):
        SourceArtifactIdentity(
            symbol="bad-symbol", market_type="SPOT", interval="1m",
            period_start_utc="2025-03-02T00:00:00Z", period_end_utc="2025-03-02T00:10:00Z",
        )
    csv_p, sc_p, identity, _, _ = write_artifact(tmp_path)
    with pytest.raises(ProvenanceMismatchError):
        load_minute_facts(
            csv_p, sc_p, identity=identity,
            expected=MinuteFactsExpectedProvenance(symbol="OTHERSYM"),
        )


def test_04_wrong_market_type(tmp_path):
    with pytest.raises(SchemaViolationError):
        SourceArtifactIdentity(
            symbol="GENSYM1", market_type="FUTURES", interval="1m",
            period_start_utc="2025-03-02T00:00:00Z", period_end_utc="2025-03-02T00:10:00Z",
        )


def test_05_wrong_interval(tmp_path):
    with pytest.raises(SchemaViolationError):
        SourceArtifactIdentity(
            symbol="GENSYM1", market_type="SPOT", interval="5m",
            period_start_utc="2025-03-02T00:00:00Z", period_end_utc="2025-03-02T00:10:00Z",
        )


def test_06_wrong_timestamp_unit(tmp_path):
    with pytest.raises(SchemaViolationError):
        SourceArtifactIdentity(
            symbol="GENSYM1", market_type="SPOT", interval="1m",
            period_start_utc="2025-03-02T00:00:00Z", period_end_utc="2025-03-02T00:10:00Z",
            timestamp_unit="MILLISECONDS",
        )


def test_07_naive_timezone_rejected(tmp_path):
    with pytest.raises(SchemaViolationError):
        SourceArtifactIdentity(
            symbol="GENSYM1", market_type="SPOT", interval="1m",
            period_start_utc="2025-03-02T00:00:00",  # naive: no Z
            period_end_utc="2025-03-02T00:10:00Z",
        )


def test_08_duplicate_minute_rejected(tmp_path):
    csv_p, sc_p, identity, rows_lit, sc = write_artifact(tmp_path)
    good = Path(csv_p).read_text().splitlines()
    dup = good + [good[-1]]  # exact duplicate of the final minute
    p = tmp_path / "dup.csv"
    p.write_text("\n".join(dup) + "\n")
    with pytest.raises(CoverageError):
        load_minute_facts(str(p), sc_p, identity=identity)


def test_09_missing_minute_coverage_contract(tmp_path):
    spec = [SPEC[0], SPEC[1], SPEC[4]]  # rows at minutes 0, 1, 4 -> gap of two minutes
    csv_p, sc_p, identity, rows_lit, _ = write_artifact(tmp_path, spec=spec, positions=[0, 1, 4])
    with pytest.raises(CoverageError):
        load_minute_facts(csv_p, sc_p, identity=identity, require_full_coverage=True)
    src = load_minute_facts(csv_p, sc_p, identity=identity, require_full_coverage=False)
    assert len(src.missing_minute_intervals) == 1
    gap_start, gap_end = src.missing_minute_intervals[0]
    assert gap_end - gap_start == 2 * MINUTE


def test_10_mutated_source_hash(tmp_path):
    csv_p, sc_p, identity, _, _ = write_artifact(tmp_path)
    text = Path(csv_p).read_text().replace("101.00000000", "101.00000001", 1)
    Path(csv_p).write_text(text)
    with pytest.raises(ProvenanceMismatchError):
        load_minute_facts(csv_p, sc_p, identity=identity)


def test_11_mismatched_provenance(tmp_path):
    csv_p, sc_p, identity, _, _ = write_artifact(tmp_path)
    with pytest.raises(ProvenanceMismatchError):
        load_minute_facts(
            csv_p, sc_p, identity=identity,
            expected=MinuteFactsExpectedProvenance(converter_sha256="0" * 64),
        )
    with pytest.raises(ProvenanceMismatchError):
        load_minute_facts(
            csv_p, sc_p, identity=identity,
            expected=MinuteFactsExpectedProvenance(raw_source_sha256="1" * 64),
        )
    with pytest.raises(ProvenanceMismatchError):
        load_minute_facts(
            csv_p, sc_p, identity=identity,
            expected=MinuteFactsExpectedProvenance(minute_facts_sha256="2" * 64),
        )


def test_12_facts_frames_have_no_canonical_ohlc(tmp_path):
    csv_p, sc_p, identity, _, _ = write_artifact(tmp_path)
    src = load_minute_facts(csv_p, sc_p, identity=identity)
    for frame in (src.exact_frame, src.frame):
        assert "open" not in frame.columns
        assert "close" not in frame.columns
        assert "high" in frame.columns or "high" in src.frame.columns
    # ambiguity metadata preserved, never erased
    amb = src.frame[src.frame["close_ambiguous"] == 1]
    assert len(amb) == 1


def test_14_tie_order_contract_not_proven(tmp_path):
    csv_p, sc_p, identity, rows_lit, sc = write_artifact(tmp_path)
    src = load_minute_facts(csv_p, sc_p, identity=identity)
    assert src.provenance.TIE_ORDER_CONTRACT == "NOT_PROVEN"
    # a sidecar claiming PROVEN is rejected
    sc2 = dict(sc)
    sc2["TIE_ORDER_CONTRACT"] = "PROVEN"
    p = tmp_path / "bad_tie.sidecar.json"
    p.write_text(json.dumps(sc2), encoding="utf-8")
    with pytest.raises(SchemaViolationError):
        load_minute_facts(csv_p, str(p), identity=identity)


def test_24_ast_no_private_imports():
    for path in PRODUCTION_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("trading_system"):
                for alias in node.names:
                    assert not alias.name.startswith("_"), (path.name, alias.name)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("_"), (path.name, alias.name)


def test_25_ast_no_engine_reimplementation():
    banned_module_parts = (
        "structure", "liquidity", "orderflow", "zones", "environment",
        "multitimeframe", "decision", "reasoning", "research", "audit", "calibration", "core",
    )
    banned_name_parts = (
        "swing", "fvg", "order_block", "liquidity_map", "structural_break",
        "volume_delta", "absorption", "htf", "narrative", "evidence_vector",
        "MarketObservationTimeline", "DealingRange", "SessionContext", "DynamicVolatility",
    )
    for path in PRODUCTION_FILES:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("trading_system"):
                assert (node.module == "trading_system.sources") or (
                    node.module or ""
                ).startswith("trading_system.sources."), (path.name, node.module)
                for part in banned_module_parts:
                    assert part not in (node.module or "").split("."), (path.name, node.module)
            if isinstance(node, ast.ClassDef):
                assert not node.name.endswith("Engine"), (path.name, node.name)
                for part in banned_name_parts:
                    assert part.lower() not in node.name.lower(), (path.name, node.name)
            if isinstance(node, ast.FunctionDef):
                assert node.name != "analyze", (path.name, node.name)
            if isinstance(node, ast.Name):
                for part in banned_name_parts:
                    assert part.lower() not in node.id.lower(), (path.name, node.id)
        assert "def analyze(" not in text


def test_26_prefix_stability(tmp_path):
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    csv1, sc1, id1, _, _ = write_artifact(d1, spec=SPEC)
    csv2, sc2, id2, _, _ = write_artifact(d2, spec=SPEC[:3])  # cut at a minute boundary
    s1 = load_minute_facts(csv1, sc1, identity=id1)
    s2 = load_minute_facts(csv2, sc2, identity=id2)
    pd.testing.assert_frame_equal(s1.exact_frame.iloc[:3], s2.exact_frame)
    pd.testing.assert_frame_equal(s1.frame.iloc[:3], s2.frame)


def test_29_deterministic_load(tmp_path):
    csv_p, sc_p, identity, _, _ = write_artifact(tmp_path)
    a = load_minute_facts(csv_p, sc_p, identity=identity)
    b = load_minute_facts(csv_p, sc_p, identity=identity)
    pd.testing.assert_frame_equal(a.exact_frame, b.exact_frame)
    pd.testing.assert_frame_equal(a.frame, b.frame)
    assert a.provenance == b.provenance


def test_30_generic_second_symbol_period(tmp_path):
    # a legal second symbol/period loads with zero code changes
    spec = [SPEC[3], SPEC[4]]
    csv_p, sc_p, identity, _, _ = write_artifact(
        tmp_path, spec=spec, symbol="ANOTHERSYM9",
        period=("2026-02-01T00:00:00Z", "2026-02-01T00:05:00Z"),
    )
    src = load_minute_facts(csv_p, sc_p, identity=identity)
    assert src.identity.symbol == "ANOTHERSYM9"
    assert src.provenance.identity.symbol == "ANOTHERSYM9"
    assert len(src.exact_frame) == 2


def test_31_hardcode_guard():
    forbidden = (
        "BTCUSDT", "ETHUSDT", "2026-05", "86d4f3d3", "a6a06c4c",
        "3948079643", "33245850882", "425331.03039000", "1777593600",
    )
    for path in PRODUCTION_FILES:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, (path.name, token)

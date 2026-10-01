# -*- coding: utf-8 -*-
"""Adversarial tests: binance_spot_kline_ohlc_source (SOURCE ADAPTER V1).

Cross-witness semantics: compare ONLY compatible fields, exactly, no tolerance.
Kline open/close are PUBLISHED bar facts; they never prove tick chronology and
TIE_ORDER_CONTRACT stays NOT_PROVEN. Ambiguous reconstructed open/close never
enter canonical OHLC.
"""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from trading_system.research.information_time import TimeIndexedTimelineAdapter
from trading_system.research.trajectory.trajectory_contract import (
    MarketObservationTimeline,
    TrajectoryDataError,
)
from trading_system.sources import (
    PUBLISHED_KLINE_OHLC_LABEL,
    ProvenanceMismatchError,
    SchemaViolationError,
    SourceArtifactIdentity,
    SourceInconsistencyError,
)
from trading_system.sources.binance_spot_kline_ohlc_source import (
    NON_COMPARABLE_PAIRS,
    KlineExpectedProvenance,
    assemble_canonical_bundle,
    cross_witness_sources,
    load_binance_spot_klines,
)
from trading_system.sources.binance_spot_minute_facts_source import (
    MINUTE_FACTS_COLUMNS,
    load_minute_facts,
)

MINUTE = 60_000_000


def us(iso):
    return int(pd.Timestamp(iso, tz="UTC").value // 1000)


def iso_of(us_val):
    return pd.Timestamp(us_val, unit="us", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S")


T0 = us("2025-03-02T00:00:00")

# (open, high, low, close_kline, close_facts, base, quote, count, buy_b, sell_b, buy_q, sell_q, amb_o, amb_c)
SPEC = [
    ("100.50000000", "101.00000000", "100.00000000", "100.75000000", "100.75000000", "0.50000000", "50.25000000", 3, "0.30000000", "0.20000000", "30.15000000", "20.10000000", "0", "0"),
    ("100.75000000", "102.00000000", "100.50000000", "101.50000000", "101.50000000", "0.40000000", "40.60000000", 2, "0.25000000", "0.15000000", "25.37500000", "15.22500000", "0", "0"),
    ("99.50000000", "101.00000000", "99.00000000", "100.50000000", "100.25000000", "0.60000000", "59.70000000", 4, "0.35000000", "0.25000000", "34.80000000", "24.90000000", "1", "1"),
    ("100.25000000", "100.90000000", "100.10000000", "100.60000000", "100.60000000", "0.20000000", "20.10000000", 1, "0.20000000", "0.00000000", "20.10000000", "0.00000000", "0", "0"),
    ("100.60000000", "101.20000000", "100.40000000", "101.00000000", "101.00000000", "0.30000000", "30.30000000", 2, "0.10000000", "0.20000000", "10.05000000", "20.25000000", "0", "0"),
    ("101.00000000", "101.50000000", "100.80000000", "101.25000000", "101.25000000", "0.35000000", "35.43750000", 2, "0.15000000", "0.20000000", "15.18750000", "20.25000000", "0", "0"),
]


def make_identity(symbol="GENSYM1", period=("2025-03-02T00:00:00Z", "2025-03-02T00:10:00Z")):
    return SourceArtifactIdentity(
        symbol=symbol, market_type="SPOT", interval="1m",
        period_start_utc=period[0], period_end_utc=period[1],
    )


def write_klines(tmp_path, spec=SPEC, *, symbol="GENSYM1", period=("2025-03-02T00:00:00Z", "2025-03-02T00:10:00Z"),
                 number_of_trades=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, s in enumerate(spec):
        (o, h, l, c_k, _c_f, base, quote, count, buy_b, _sb, buy_q, _sq, _ao, _ac) = s
        start = T0 + i * MINUTE
        n = number_of_trades[i] if number_of_trades else 111 + i * 7
        lines.append(
            f"{start},{o},{h},{l},{c_k},{base},{start + MINUTE - 1},{quote},{n},{buy_b},{buy_q},0"
        )
    text = "\n".join(lines) + "\n"
    path = tmp_path / "klines.csv"
    path.write_text(text, encoding="utf-8")
    return str(path), make_identity(symbol=symbol, period=period)


def write_facts(tmp_path, spec=SPEC, *, symbol="GENSYM1", period=("2025-03-02T00:00:00Z", "2025-03-02T00:10:00Z")):
    tmp_path.mkdir(parents=True, exist_ok=True)
    rows_lit = []
    lines = []
    for i, s in enumerate(spec):
        (o_k, h, l, _c_k, c_f, base, quote, count, buy_b, sell_b, buy_q, sell_q, amb_o, amb_c) = s
        start = T0 + i * MINUTE
        o_f = "99.75000000" if amb_o == "1" else o_k  # ambiguous witness differs by construction
        rows_lit.append({
            "minute_start_utc": iso_of(start), "minute_end_utc": iso_of(start + MINUTE),
            "open": o_f, "high": h, "low": l, "close": c_f,
            "base_volume": base, "quote_volume": quote, "agg_trade_count": str(count),
            "buy_initiated_base_volume": buy_b, "sell_initiated_base_volume": sell_b,
            "buy_initiated_quote_volume": buy_q, "sell_initiated_quote_volume": sell_q,
            "executed_base_delta": str(Decimal(buy_b) - Decimal(sell_b)),
            "executed_quote_delta": str(Decimal(buy_q) - Decimal(sell_q)),
            "first_agg_trade_id": str(2000 + i), "last_agg_trade_id": str(2000 + i),
            "first_transact_time_us": str(start), "last_transact_time_us": str(start + 500),
            "open_ambiguous": amb_o, "close_ambiguous": amb_c,
            "open_tie_distinct_prices": "2" if amb_o == "1" else "1",
            "close_tie_distinct_prices": "2" if amb_c == "1" else "1",
        })
        lines.append(",".join([
            rows_lit[-1][c] for c in MINUTE_FACTS_COLUMNS
        ]))
    csv_text = ",".join(MINUTE_FACTS_COLUMNS) + "\n" + "\n".join(lines) + "\n"
    csv_path = tmp_path / "facts.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    total_base = sum((Decimal(r["base_volume"]) for r in rows_lit), Decimal(0))
    total_quote = sum((Decimal(r["quote_volume"]) for r in rows_lit), Decimal(0))
    total_count = sum(int(r["agg_trade_count"]) for r in rows_lit)
    sidecar = {
        "converter_name": "aggtrades_to_minute_facts", "converter_version": "1.0.0",
        "converter_sha256": hashlib.sha256(b"conv").hexdigest(),
        "source_sha256": hashlib.sha256(b"raw").hexdigest(),
        "source_contract": "BINANCE_SPOT_PUBLIC_DATA_AGGTRADES",
        "timestamp_unit": "MICROSECONDS",
        "source_rows_total": total_count, "legal_rows_consumed": total_count,
        "official_invalid_sentinel_count": 0, "rejected_corrupt_rows": 0,
        "output_minute_count": len(rows_lit),
        "covered_calendar_minute_count": len(rows_lit),
        "missing_minute_count": 0, "missing_minute_intervals": [],
        "first_output_minute": rows_lit[0]["minute_start_utc"],
        "last_output_minute": rows_lit[-1]["minute_start_utc"],
        "is_best_match_true_count": total_count, "is_best_match_false_count": 0,
        "is_best_match_invalid_count": 0,
        "tie_timestamp_count": 5,
        "ambiguous_open_minute_count": sum(1 for r in rows_lit if r["open_ambiguous"] == "1"),
        "ambiguous_close_minute_count": sum(1 for r in rows_lit if r["close_ambiguous"] == "1"),
        "TIE_ORDER_CONTRACT": "NOT_PROVEN",
        "tie_order_evidence": "evidence", "tie_order_policy": "AMBIGUITY_METADATA",
        "bar_close_availability": "NOT_CLAIMED_BY_CONVERTER",
        "numeric_representation": "INTEGER_FIXED_POINT",
        "reconciliation": {
            "source_base_sum": str(total_base), "output_base_sum": str(total_base),
            "source_quote_sum": str(total_quote), "output_quote_sum": str(total_quote),
            "exact_match_base": True, "exact_match_quote": True,
            "buy_plus_sell_base_matches_total": True,
            "buy_plus_sell_quote_matches_total": True,
            "sum_agg_trade_count_matches_legal_source_rows": True,
        },
        "output_csv_sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "generated_at_utc": "2026-09-27T00:00:00.000Z",
        "historical_provenance_statement": "fixture",
    }
    sidecar_path = tmp_path / "facts.sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    return str(csv_path), str(sidecar_path), make_identity(symbol=symbol, period=period)


def load_pair(tmp_path, spec=SPEC, **kw):
    k_path, identity = write_klines(tmp_path, spec=spec, **kw)
    f_path, f_side, f_identity = write_facts(tmp_path, spec=spec, **{k: v for k, v in kw.items() if k in ("symbol", "period")})
    klines = load_binance_spot_klines(k_path, identity=identity)
    facts = load_minute_facts(f_path, f_side, identity=f_identity)
    return klines, facts


# ------------------------------------------------------------------ schema
def test_01_klines_schema_valid(tmp_path):
    k_path, identity = write_klines(tmp_path)
    src = load_binance_spot_klines(k_path, identity=identity)
    assert len(src.exact_frame) == 6
    assert list(src.canonical_market_frame.columns) == ["open", "high", "low", "close", "volume"]
    assert str(src.canonical_market_frame.index.tz) == "UTC"
    assert src.provenance.schema_contract == "BINANCE_SPOT_PUBLIC_DATA_KLINES_1M_V1"
    # CLOSE_TIME index: completion instant = open_time + 60s
    assert int(src.exact_frame["open_time_us"].iloc[0]) == T0
    assert src.canonical_market_frame.index[0].value == (T0 + MINUTE) * 1000


def test_02_klines_malformed_failclosed(tmp_path):
    k_path, identity = write_klines(tmp_path)
    good = Path(k_path).read_text()
    p = tmp_path / "bad_fields.csv"
    lines = good.splitlines()
    lines[1] = lines[1].replace(",", " ", 1)
    p.write_text("\n".join(lines) + "\n")
    with pytest.raises(SchemaViolationError):
        load_binance_spot_klines(str(p), identity=identity)
    p2 = tmp_path / "bad_dec.csv"
    p2.write_text(good.replace("100.50000000", "1e2", 1))
    with pytest.raises(SchemaViolationError):
        load_binance_spot_klines(str(p2), identity=identity)
    p3 = tmp_path / "bad_geometry.csv"
    p3.write_text(good.replace("101.00000000,100.00000000", "101.00000000,102.00000000", 1))
    with pytest.raises(SchemaViolationError):
        load_binance_spot_klines(str(p3), identity=identity)
    p4 = tmp_path / "bad_taker.csv"
    p4.write_text(good.replace("0.50000000,1740873659999999,50.25000000,111,0.30000000", "0.50000000,1740873659999999,50.25000000,111,0.90000000", 1))
    with pytest.raises(SchemaViolationError):
        load_binance_spot_klines(str(p4), identity=identity)


def test_05_wrong_interval_content(tmp_path):
    k_path, identity = write_klines(tmp_path)
    good = Path(k_path).read_text()
    bad = good.replace("1740873659999999", "1740873899999999", 1)  # 5m close_time
    p = tmp_path / "interval.csv"
    p.write_text(bad)
    with pytest.raises(SchemaViolationError):
        load_binance_spot_klines(str(p), identity=identity)


def test_06_wrong_timestamp_unit_content(tmp_path):
    k_path, identity = write_klines(tmp_path)
    good = Path(k_path).read_text()
    # millisecond-scale open_time masquerading as microseconds
    bad = good.replace("1740873600000000,", "1740873600000,", 1).replace("1740873659999999", "1740873659999", 1)
    p = tmp_path / "ms.csv"
    p.write_text(bad)
    with pytest.raises(SchemaViolationError):
        load_binance_spot_klines(str(p), identity=identity)


# ------------------------------------------------------- canonical OHLC truth
def test_12_ambiguous_reconstructed_never_enters_canonical(tmp_path):
    klines, facts = load_pair(tmp_path)
    bundle = assemble_canonical_bundle(klines, facts)
    canonical = bundle.canonical_market_frame
    amb_pos = 2  # fixture row with ambiguous open AND close
    # canonical values are the PUBLISHED kline values ...
    assert canonical["close"].iloc[amb_pos] == 100.5
    assert canonical["open"].iloc[amb_pos] == 99.5
    # ... and they differ from the ambiguous reconstructed witnesses
    witness_close = float(facts.exact_frame["reconstructed_close_witness"].iloc[amb_pos])
    witness_open = float(facts.exact_frame["reconstructed_open_witness"].iloc[amb_pos])
    assert witness_close != canonical["close"].iloc[amb_pos]
    assert witness_open != canonical["open"].iloc[amb_pos]
    # cross-witness skipped the ambiguous minute's O/C by contract
    w = bundle.cross_witness
    assert w.ambiguous_minutes_skipped_by_contract == 1
    assert w.compared_minutes == 6


def test_13_published_kline_ohlc_label(tmp_path):
    klines, facts = load_pair(tmp_path)
    bundle = assemble_canonical_bundle(klines, facts)
    assert bundle.ohlc_source_label == PUBLISHED_KLINE_OHLC_LABEL == "PUBLISHED_KLINE_OHLC"
    assert bundle.kline_provenance.ohlc_source_label == "PUBLISHED_KLINE_OHLC"
    assert "PUBLISHED_BAR_FACT" in bundle.kline_provenance.published_fact_statement
    assert bundle.kline_provenance.tie_order_contract == "NOT_PROVEN"
    # canonical frame equals the published values literally
    assert bundle.canonical_market_frame["open"].iloc[0] == 100.5
    assert bundle.canonical_market_frame["volume"].iloc[0] == 0.5


def test_14_kline_tie_stays_not_proven(tmp_path):
    klines, facts = load_pair(tmp_path)
    assert klines.provenance.tie_order_contract == "NOT_PROVEN"
    bundle = assemble_canonical_bundle(klines, facts)
    assert bundle.tie_order_contract == "NOT_PROVEN"
    assert bundle.tie_ambiguity_counts["TIE_ORDER_CONTRACT"] == "NOT_PROVEN"
    assert bundle.tie_ambiguity_counts["ambiguous_close_minute_count"] == 1


# ------------------------------------------------------------ cross-witness
def test_15_high_low_exact_reconciliation(tmp_path):
    klines, facts = load_pair(tmp_path)
    w = cross_witness_sources(klines, facts)
    assert w.compared_minutes == 6
    # attack: kline low diverges from facts low -> fail closed
    spec2 = [list(s) for s in SPEC]
    spec2[1][2] = "100.49999999"
    k2, _ = write_klines(tmp_path / "atk", spec=[tuple(x) for x in spec2])
    f2p, f2s, f2i = write_facts(tmp_path / "atk")
    with pytest.raises(SourceInconsistencyError):
        cross_witness_sources(
            load_binance_spot_klines(k2, identity=make_identity()),
            load_minute_facts(f2p, f2s, identity=f2i),
        )


def test_16_base_volume_exact_reconciliation(tmp_path):
    klines, facts = load_pair(tmp_path)
    cross_witness_sources(klines, facts)  # base volume among exact fields
    spec2 = [list(s) for s in SPEC]
    spec2[0][5] = "0.50000001"  # base volume divergence (kline side only)
    k2, _ = write_klines(tmp_path / "b", spec=[tuple(x) for x in spec2])
    f2p, f2s, f2i = write_facts(tmp_path / "b")
    klines2 = load_binance_spot_klines(k2, identity=make_identity())
    facts2 = load_minute_facts(f2p, f2s, identity=f2i)
    with pytest.raises(SourceInconsistencyError):
        cross_witness_sources(klines2, facts2)


def test_17_quote_volume_exact_reconciliation(tmp_path):
    klines, facts = load_pair(tmp_path)
    w = cross_witness_sources(klines, facts)
    assert "quote_volume" in w.exact_matched_fields
    spec2 = [list(s) for s in SPEC]
    spec2[2][6] = "59.70000001"
    k2, _ = write_klines(tmp_path / "q", spec=[tuple(x) for x in spec2])
    f2p, f2s, f2i = write_facts(tmp_path / "q")
    with pytest.raises(SourceInconsistencyError):
        cross_witness_sources(
            load_binance_spot_klines(k2, identity=make_identity()),
            load_minute_facts(f2p, f2s, identity=f2i),
        )


def test_18_taker_buy_base_exact_and_quote_evaluated(tmp_path):
    klines, facts = load_pair(tmp_path)
    w = cross_witness_sources(klines, facts)
    assert "taker_buy_base_volume" in w.exact_matched_fields
    assert w.taker_buy_quote_status == "EXACT_MATCH"
    assert "TAKER_BUY_QUOTE_ASSET_VOLUME" in w.taker_buy_quote_reason
    spec2 = [list(s) for s in SPEC]
    spec2[0][8] = "0.31000000"  # taker-buy-base divergence on kline side (base=0.5)
    k2, _ = write_klines(tmp_path / "t", spec=[tuple(x) for x in spec2])
    f2p, f2s, f2i = write_facts(tmp_path / "t")
    with pytest.raises(SourceInconsistencyError):
        cross_witness_sources(
            load_binance_spot_klines(k2, identity=make_identity()),
            load_minute_facts(f2p, f2s, identity=f2i),
        )


def test_19_number_of_trades_never_compared(tmp_path):
    # number_of_trades wildly different from agg_trade_count: witness must pass
    klines, facts = load_pair(
        tmp_path, number_of_trades=[9999, 1, 777, 3, 123456, 8]
    )
    w = cross_witness_sources(klines, facts)
    assert w.compared_minutes == 6
    assert any(
        pair["kline_field"] == "number_of_trades" and pair["facts_field"] == "agg_trade_count"
        for pair in NON_COMPARABLE_PAIRS
    )


def test_20_source_inconsistency_attack(tmp_path):
    klines, facts = load_pair(tmp_path)
    # high attack
    spec2 = [list(s) for s in SPEC]
    spec2[0][1] = "101.00000001"
    k2, _ = write_klines(tmp_path / "h", spec=[tuple(x) for x in spec2])
    f2p, f2s, f2i = write_facts(tmp_path / "h")
    with pytest.raises(SourceInconsistencyError):
        cross_witness_sources(
            load_binance_spot_klines(k2, identity=make_identity()),
            load_minute_facts(f2p, f2s, identity=f2i),
        )
    # unambiguous reconstructed O/C divergence is unexpected -> fail closed
    spec3 = [list(s) for s in SPEC]
    spec3[4] = list(spec3[4]); spec3[4][4] = "101.00000001"  # facts close witness diverges
    k3, _ = write_klines(tmp_path / "o", spec=[tuple(x) for x in spec3])
    f3p, f3s, f3i = write_facts(tmp_path / "o", spec=[tuple(x) for x in spec3])
    with pytest.raises(SourceInconsistencyError):
        cross_witness_sources(
            load_binance_spot_klines(k3, identity=make_identity()),
            load_minute_facts(f3p, f3s, identity=f3i),
        )


def test_03_wrong_symbol_cross_identity(tmp_path):
    k_path, identity = write_klines(tmp_path, symbol="GENSYM1")
    f_path, f_side, f_identity = write_facts(tmp_path, symbol="OTHERSYM2")
    klines = load_binance_spot_klines(k_path, identity=identity)
    facts = load_minute_facts(f_path, f_side, identity=f_identity)
    with pytest.raises(ProvenanceMismatchError):
        cross_witness_sources(klines, facts)


def test_unambiguous_oc_record_only_policy(tmp_path):
    spec2 = [list(s) for s in SPEC]
    spec2[4] = list(spec2[4]); spec2[4][4] = "101.00000001"
    k2, _ = write_klines(tmp_path / "r", spec=[tuple(x) for x in spec2])
    f2p, f2s, f2i = write_facts(tmp_path / "r", spec=[tuple(x) for x in spec2])
    w = cross_witness_sources(
        load_binance_spot_klines(k2, identity=make_identity()),
        load_minute_facts(f2p, f2s, identity=f2i),
        unambiguous_oc_policy="RECORD_ONLY",
    )
    assert w.unambiguous_oc_policy == "RECORD_ONLY"


# ------------------------------------------------------------------ systems
def test_26_prefix_stability_klines(tmp_path):
    k_full, id_full = write_klines(tmp_path / "f")
    k_cut, id_cut = write_klines(tmp_path / "c", spec=SPEC[:3])
    a = load_binance_spot_klines(k_full, identity=id_full)
    b = load_binance_spot_klines(k_cut, identity=id_cut)
    pd.testing.assert_frame_equal(a.canonical_market_frame.iloc[:3], b.canonical_market_frame)
    pd.testing.assert_frame_equal(a.exact_frame.iloc[:3], b.exact_frame)


def test_27_same_timeline_identity(tmp_path):
    k_path, identity = write_klines(tmp_path)
    a = load_binance_spot_klines(k_path, identity=identity)
    b = load_binance_spot_klines(k_path, identity=identity)
    pd.testing.assert_frame_equal(a.canonical_market_frame, b.canonical_market_frame)
    adapter = TimeIndexedTimelineAdapter(timeline_id="fixture-timeline")
    t1 = MarketObservationTimeline.seal(adapter=adapter, market_history=a.canonical_market_frame)
    t2 = MarketObservationTimeline.seal(adapter=adapter, market_history=b.canonical_market_frame)
    assert t1.timeline_hash == t2.timeline_hash


def test_28_cross_timeline_rejection(tmp_path):
    k_path, identity = write_klines(tmp_path)
    a = load_binance_spot_klines(k_path, identity=identity)
    adapter = TimeIndexedTimelineAdapter(timeline_id="fixture-timeline")
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=a.canonical_market_frame)
    mutated = a.canonical_market_frame.copy(deep=True)
    mutated.iloc[0, mutated.columns.get_loc("close")] = mutated["close"].iloc[0] + 0.01
    with pytest.raises(TrajectoryDataError):
        timeline.verify(adapter=adapter, market_history=mutated)


def test_29_deterministic_canonical_output(tmp_path):
    k_path, identity = write_klines(tmp_path)
    a = load_binance_spot_klines(k_path, identity=identity)
    b = load_binance_spot_klines(k_path, identity=identity)
    assert a.canonical_market_frame.to_csv() == b.canonical_market_frame.to_csv()
    assert a.provenance == b.provenance


def test_30_generic_kline_second_symbol_period(tmp_path):
    k_path, identity = write_klines(
        tmp_path, symbol="ANOTHERSYM9",
        period=("2026-02-01T00:00:00Z", "2026-02-01T00:10:00Z"),
    )
    src = load_binance_spot_klines(k_path, identity=identity)
    assert src.provenance.identity.symbol == "ANOTHERSYM9"
    # expected provenance must agree on the generic symbol too
    with pytest.raises(ProvenanceMismatchError):
        load_binance_spot_klines(
            k_path, identity=identity,
            expected=KlineExpectedProvenance(symbol="NOTTHAT"),
        )
    ok = load_binance_spot_klines(
        k_path, identity=identity,
        expected=KlineExpectedProvenance(symbol="ANOTHERSYM9"),
    )
    assert ok.provenance.source_file_sha256 == src.provenance.source_file_sha256

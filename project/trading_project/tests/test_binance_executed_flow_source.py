# -*- coding: utf-8 -*-
"""Adversarial tests: binance_executed_flow_source (SOURCE ADAPTER V1).

Semantic label: EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT — executed/initiated
flow of this source only. The CLOSED engines 3.1/3.2 are consumed UNMODIFIED
through their public APIs; PROXY outputs stay PROXY and are never impersonated.
"""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from trading_system.orderflow.volume_delta import CausalVolumeDeltaEngine, OrderFlowMode
from trading_system.orderflow.absorption import CausalAbsorptionEvidenceEngine
from trading_system.sources import (
    EXECUTED_FLOW_SEMANTIC_LABEL,
    EXECUTED_FLOW_VOLUME_UNIT,
    SchemaViolationError,
    SourceArtifactIdentity,
)
from trading_system.sources.binance_executed_flow_source import build_executed_flow_source
from trading_system.sources.binance_spot_kline_ohlc_source import load_binance_spot_klines
from trading_system.sources.binance_spot_minute_facts_source import (
    MINUTE_FACTS_COLUMNS,
    load_minute_facts,
)

MINUTE = 60_000_000
FORBIDDEN_CLAIMS = ("buying pressure", "order-book", "institutional", "whale", "market-wide")


def us(iso):
    return int(pd.Timestamp(iso, tz="UTC").value // 1000)


def iso_of(us_val):
    return pd.Timestamp(us_val, unit="us", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S")


T0 = us("2025-03-02T00:00:00")

# (open, high, low, close, base, quote, count, buy_b, sell_b, buy_q, sell_q)
SPEC = [
    ("100.50000000", "101.00000000", "100.00000000", "100.75000000", "0.50000000", "50.25000000", 3, "0.30000000", "0.20000000", "30.15000000", "20.10000000"),
    ("100.75000000", "102.00000000", "100.50000000", "101.50000000", "0.40000000", "40.60000000", 2, "0.25000000", "0.15000000", "25.37500000", "15.22500000"),
    ("99.50000000", "101.00000000", "99.00000000", "100.50000000", "0.60000000", "59.70000000", 4, "0.35000000", "0.25000000", "34.80000000", "24.90000000"),
    ("100.25000000", "100.90000000", "100.10000000", "100.60000000", "0.20000000", "20.10000000", 1, "0.20000000", "0.00000000", "20.10000000", "0.00000000"),
]


def make_identity():
    return SourceArtifactIdentity(
        symbol="GENSYM1", market_type="SPOT", interval="1m",
        period_start_utc="2025-03-02T00:00:00Z", period_end_utc="2025-03-02T00:10:00Z",
    )


def write_facts(tmp_path, spec=SPEC):
    tmp_path.mkdir(parents=True, exist_ok=True)
    rows_lit = []
    lines = []
    for i, s in enumerate(spec):
        (o, h, l, c, base, quote, count, buy_b, sell_b, buy_q, sell_q) = s
        start = T0 + i * MINUTE
        rows_lit.append({
            "minute_start_utc": iso_of(start), "minute_end_utc": iso_of(start + MINUTE),
            "open": o, "high": h, "low": l, "close": c,
            "base_volume": base, "quote_volume": quote, "agg_trade_count": str(count),
            "buy_initiated_base_volume": buy_b, "sell_initiated_base_volume": sell_b,
            "buy_initiated_quote_volume": buy_q, "sell_initiated_quote_volume": sell_q,
            "executed_base_delta": str(Decimal(buy_b) - Decimal(sell_b)),
            "executed_quote_delta": str(Decimal(buy_q) - Decimal(sell_q)),
            "first_agg_trade_id": str(3000 + i), "last_agg_trade_id": str(3000 + i),
            "first_transact_time_us": str(start), "last_transact_time_us": str(start + 700),
            "open_ambiguous": "0", "close_ambiguous": "0",
            "open_tie_distinct_prices": "1", "close_tie_distinct_prices": "1",
        })
        lines.append(",".join([rows_lit[-1][col] for col in MINUTE_FACTS_COLUMNS]))
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
        "is_best_match_invalid_count": 0, "tie_timestamp_count": 2,
        "ambiguous_open_minute_count": 0, "ambiguous_close_minute_count": 0,
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
    return str(csv_path), str(sidecar_path)


def load_facts(tmp_path, spec=SPEC):
    csv_p, sc_p = write_facts(tmp_path, spec=spec)
    return load_minute_facts(csv_p, sc_p, identity=make_identity())


def test_21_buy_plus_sell_equals_total(tmp_path):
    facts = load_facts(tmp_path)
    flow = build_executed_flow_source(facts)
    assert list(flow.frame.columns) == ["buy_volume", "sell_volume", "volume"]
    assert flow.volume_unit == EXECUTED_FLOW_VOLUME_UNIT == "BASE_ASSET"
    totals = flow.frame["buy_volume"] + flow.frame["sell_volume"]
    assert (totals == flow.frame["volume"]).all()
    # exact literal accounting per row
    for buy, sell, total in zip(flow.exact_frame["buy_volume"], flow.exact_frame["sell_volume"], flow.exact_frame["volume"]):
        assert Decimal(buy) + Decimal(sell) == Decimal(total)
    # corrupted accounting is rejected upstream (loader) before any frame exists
    bad = [list(s) for s in SPEC]
    bad[0] = list(bad[0]); bad[0][8] = "0.10000000"  # sell 0.1 -> buy+sell=0.4 != 0.5
    with pytest.raises(SchemaViolationError):
        load_facts(tmp_path / "bad", spec=[tuple(x) for x in bad])


def test_22_actual_aggressor_public_api_accepts_frame(tmp_path):
    facts = load_facts(tmp_path)
    flow = build_executed_flow_source(facts)
    engine = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR, reconcile_total_volume=True)
    out = engine.analyze(flow.frame)  # CLOSED engine, unmodified public API
    assert (out["order_flow_mode"] == "ACTUAL_AGGRESSOR").all()
    assert out["total_classified_volume"].iloc[0] == pytest.approx(0.5)
    assert out["raw_delta"].iloc[0] == pytest.approx(0.1)  # buy 0.3 - sell 0.2
    assert (out["classified_volume_fraction"] == 1.0).all()  # buy+sell==total
    # downstream CLOSED 3.2 ACTUAL also consumes the 3.1 surface unmodified
    joined = out.copy(deep=True)
    joined["close"] = 100.75
    abs_engine = CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR)
    out2 = abs_engine.analyze(joined)
    assert "proxy_absorption_evidence" in out2.columns or "actual_absorption_evidence" in out2.columns


def test_23_proxy_stays_proxy(tmp_path):
    facts = load_facts(tmp_path)
    flow = build_executed_flow_source(facts)
    # PROXY is produced only by 3.1 PROXY mode over OHLCV geometry ...
    ohlcv = pd.DataFrame(
        {
            "open": [100.5, 100.75, 99.5, 100.25],
            "high": [101.0, 102.0, 101.0, 100.9],
            "low": [100.0, 100.5, 99.0, 100.1],
            "close": [100.75, 101.5, 100.5, 100.6],
            "volume": [0.5, 0.4, 0.6, 0.2],
        },
        index=flow.frame.index.copy(),
    )
    proxy_out = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(ohlcv)
    assert (proxy_out["order_flow_mode"] == "OHLCV_PROXY").all()
    # ... and our source surface never labels anything ACTUAL or PROXY by itself
    assert "order_flow_mode" not in flow.frame.columns
    assert "order_flow_mode" not in flow.exact_frame.columns
    assert flow.semantic_label == EXECUTED_FLOW_SEMANTIC_LABEL


def test_semantic_label_and_no_forbidden_claims(tmp_path):
    facts = load_facts(tmp_path)
    flow = build_executed_flow_source(facts)
    assert flow.semantic_label == "EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT"
    blob = (flow.semantic_label + " " + flow.statement).lower()
    for claim in FORBIDDEN_CLAIMS:
        assert claim.lower() not in blob, claim


def test_close_time_index_alignment(tmp_path):
    facts = load_facts(tmp_path)
    flow = build_executed_flow_source(facts)
    assert str(flow.frame.index.tz) == "UTC"
    # index = bar completion instants (minute_end), identical to the facts source
    assert flow.frame.index[0].value == (T0 + MINUTE) * 1000
    assert flow.frame.index.equals(facts.frame.index)


def test_generic_symbol_no_hardcode(tmp_path):
    facts = load_facts(tmp_path)
    flow = build_executed_flow_source(facts)
    assert flow.identity.symbol == "GENSYM1"
    assert flow.source_minute_facts_sha256 == facts.provenance.minute_facts_sha256

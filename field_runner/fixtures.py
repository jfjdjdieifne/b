"""TEST-FIXTURE-ONLY synthetic Binance Spot artifacts for runner tests.

Generates a tiny consistent set (minute-facts CSV + sidecar JSON + official-format
headerless 1m klines CSV) that satisfies the CLOSED Binance Source Adapter V1
loaders exactly. Nothing here is production data, and nothing here is a policy:
the fixture exists so the runner tests can exercise happy paths and fail-closed
attacks. Labels on generated rows are operational fixture labels only.
"""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal

FIXTURE_SYMBOL = "FIXTURESYM"
FIXTURE_MARKET = "SPOT"
FIXTURE_INTERVAL = "1m"
FIXTURE_PERIOD_START = "2026-05-01T00:00:00Z"
FIXTURE_PERIOD_END = "2026-05-01T02:00:00Z"
MINUTE_US = 60_000_000

MINUTE_FACTS_COLUMNS = (
    "minute_start_utc", "minute_end_utc", "open", "high", "low", "close",
    "base_volume", "quote_volume", "agg_trade_count",
    "buy_initiated_base_volume", "sell_initiated_base_volume",
    "buy_initiated_quote_volume", "sell_initiated_quote_volume",
    "executed_base_delta", "executed_quote_delta",
    "first_agg_trade_id", "last_agg_trade_id",
    "first_transact_time_us", "last_transact_time_us",
    "open_ambiguous", "close_ambiguous",
    "open_tie_distinct_prices", "close_tie_distinct_prices",
)

KLINES_COLUMNS = (
    "open_time", "open", "high", "low", "close", "base_volume", "close_time",
    "quote_volume", "number_of_trades", "taker_buy_base_volume",
    "taker_buy_quote_volume", "ignore",
)


def _iso_us(start_us: int) -> str:
    # MINUTE_FACTS grammar is exact naive second-precision ISO (loader regex):
    # YYYY-MM-DDTHH:MM:SS — no Z, no fractional part.
    import datetime as dt

    base = dt.datetime.fromtimestamp(start_us / 1_000_000, tz=dt.timezone.utc)
    return base.strftime("%Y-%m-%dT%H:%M:%S")


_Q8 = Decimal("0.00000001")


def _price(x) -> str:
    return format(Decimal(str(x)).quantize(_Q8), "f")


def _dec(x) -> str:
    return format(Decimal(str(x)).quantize(_Q8), "f")


def build_fixture_rows(n_minutes: int = 120, *, ambiguous_minute: int | None = 40):
    """Deterministic synthetic minute rows (list of dicts of exact literals)."""
    rows = []
    # Length-scaled positive baseline: the deterministic walk has a mild
    # negative drift; the baseline keeps every literal positive (UNSIGNED
    # grammar) at ANY n while preserving the swing-triggering geometry.
    price = Decimal(str(200.0 + 0.35 * n_minutes)).quantize(_Q8)
    start0 = 1777593600000000  # 2026-05-01T00:00:00Z in microseconds
    for i in range(n_minutes):
        start_us = start0 + i * MINUTE_US
        end_us = start_us + MINUTE_US
        # Alternating small legs and growing crashes so the CLOSED swing
        # policy (owner-supplied quantile) can confirm real episodes and the
        # structural chain can form without any fixture-side policy invention.
        cycle = i // 4
        if i % 4 in (0, 1, 2):
            step = Decimal("0.50000000")
        else:
            step = -(Decimal("2.00000000") + Decimal("0.30000000") * Decimal(cycle % 7))
        o = price
        c = price + step
        hi = (o if o > c else c) + Decimal("0.15000000")
        lo = (o if o < c else c) - Decimal("0.15000000")
        price = c

        buy_base = Decimal("0.50000000") + (Decimal(i % 7) * Decimal("0.03000000"))
        sell_base = Decimal("0.40000000") + (Decimal(i % 5) * Decimal("0.02000000"))
        base = buy_base + sell_base
        buy_quote = (buy_base * o).quantize(Decimal("0.00000001"))
        sell_quote = (sell_base * o).quantize(Decimal("0.00000001"))
        quote = buy_quote + sell_quote
        count = 3 + (i % 11)

        open_amb, close_amb = "0", "0"
        open_ties, close_ties = "1", "1"
        witness_open, witness_close = _price(o), _price(c)
        if ambiguous_minute is not None and i == ambiguous_minute:
            # Tie at open: the witness takes the DETERMINISTIC CONVENTION value
            # which is deliberately NOT the published kline open. The ambiguity
            # stays flagged; TIE_ORDER_CONTRACT remains NOT_PROVEN.
            open_amb = "1"
            open_ties = "2"
            witness_open = _price(o + Decimal("0.25000000"))

        rows.append({
            "minute_start_utc": _iso_us(start_us),
            "minute_end_utc": _iso_us(end_us),
            "open": witness_open,
            "high": _price(hi),
            "low": _price(lo),
            "close": witness_close,
            "base_volume": _price(base),
            "quote_volume": _price(quote),
            "agg_trade_count": str(count),
            "buy_initiated_base_volume": _price(buy_base),
            "sell_initiated_base_volume": _price(sell_base),
            "buy_initiated_quote_volume": _price(buy_quote),
            "sell_initiated_quote_volume": _price(sell_quote),
            "executed_base_delta": _dec(buy_base - sell_base),
            "executed_quote_delta": _dec(buy_quote - sell_quote),
            "first_agg_trade_id": str(1000 + i * 10),
            "last_agg_trade_id": str(1000 + i * 10 + count - 1),
            "first_transact_time_us": str(start_us + 1_000),
            "last_transact_time_us": str(end_us - 1_000),
            "open_ambiguous": open_amb,
            "close_ambiguous": close_amb,
            "open_tie_distinct_prices": open_ties,
            "close_tie_distinct_prices": close_ties,
            "_kline_open": _price(o),
            "_kline_close": _price(c),
            "_kline_high": _price(hi),
            "_kline_low": _price(lo),
            "_start_us": start_us,
            "_end_us": end_us,
        })
    return rows


def build_sidecar(rows: list, *, csv_sha256: str, source_sha256: str, converter_sha256: str) -> dict:
    total_base = sum((Decimal(r["base_volume"]) for r in rows), Decimal(0))
    total_quote = sum((Decimal(r["quote_volume"]) for r in rows), Decimal(0))
    legal = sum(int(r["agg_trade_count"]) for r in rows)
    amb_open = sum(1 for r in rows if r["open_ambiguous"] == "1")
    amb_close = sum(1 for r in rows if r["close_ambiguous"] == "1")
    ties = sum(
        (int(r["open_tie_distinct_prices"]) - 1) + (int(r["close_tie_distinct_prices"]) - 1)
        for r in rows
    )
    return {
        "converter_name": "TEST_FIXTURE_CONVERTER_NOT_PRODUCTION",
        "converter_version": "FIXTURE_V1",
        "converter_sha256": converter_sha256,
        "source_sha256": source_sha256,
        "source_contract": "BINANCE_SPOT_PUBLIC_DATA_AGGTRADES",
        "timestamp_unit": "MICROSECONDS",
        "source_rows_total": str(legal),
        "legal_rows_consumed": str(legal),
        "official_invalid_sentinel_count": "0",
        "rejected_corrupt_rows": "0",
        "output_minute_count": str(len(rows)),
        "covered_calendar_minute_count": str(len(rows)),
        "missing_minute_count": "0",
        "missing_minute_intervals": [],
        "first_output_minute": rows[0]["minute_start_utc"] if rows else None,
        "last_output_minute": rows[-1]["minute_start_utc"] if rows else None,
        "is_best_match_true_count": str(legal),
        "is_best_match_false_count": "0",
        "tie_timestamp_count": str(ties),
        "ambiguous_open_minute_count": str(amb_open),
        "ambiguous_close_minute_count": str(amb_close),
        "TIE_ORDER_CONTRACT": "NOT_PROVEN",
        "tie_order_evidence": "TEST_FIXTURE_TIE_ROWS_FLAGGED_NONE_RESOLVED",
        "tie_order_policy": "TEST_FIXTURE_DETERMINISTIC_CONVENTION_NOT_CHRONOLOGY",
        "bar_close_availability": "BAR_CLOSE_AVAILABLE_THROUGH_BINANCE_PUBLISHED_KLINE",
        "numeric_representation": "PLAIN_DECIMAL_LITERAL_STRINGS",
        "reconciliation": {
            "exact_match_base": True,
            "exact_match_quote": True,
            "buy_plus_sell_base_matches_total": True,
            "buy_plus_sell_quote_matches_total": True,
            "sum_agg_trade_count_matches_legal_source_rows": True,
            "source_base_sum": _dec(total_base),
            "output_base_sum": _dec(total_base),
            "source_quote_sum": _dec(total_quote),
            "output_quote_sum": _dec(total_quote),
        },
        "output_csv_sha256": csv_sha256,
        "generated_at_utc": "2026-09-28T00:00:00Z",
        "historical_provenance_statement": (
            "TEST_FIXTURE: reconstruction witness only; NOT historical generating provenance"
        ),
    }


def write_fixture(out_dir: str, *, n_minutes: int = 120, ambiguous_minute: int | None = 40,
                  source_sha256: str | None = None, converter_sha256: str | None = None) -> dict:
    """Write fixture files to ``out_dir``; return their paths and hashes.

    ``source_sha256`` / ``converter_sha256`` default to deterministic fixture
    placeholders (TEST-FIXTURE-ONLY identities) so tests can bind the sidecar
    provenance chain to known expected values.
    """
    os.makedirs(out_dir, exist_ok=True)
    rows = build_fixture_rows(n_minutes, ambiguous_minute=ambiguous_minute)

    facts_lines = [",".join(MINUTE_FACTS_COLUMNS)]
    for r in rows:
        facts_lines.append(",".join(r[c] for c in MINUTE_FACTS_COLUMNS))
    facts_text = "\n".join(facts_lines) + "\n"
    facts_path = os.path.join(out_dir, "FIXTURESYM-minute-facts-2026-05.csv")
    open(facts_path, "w", encoding="utf-8").write(facts_text)
    facts_sha = hashlib.sha256(facts_text.encode()).hexdigest()

    if source_sha256 is None:
        source_sha256 = hashlib.sha256(b"TEST_FIXTURE_RAW_AGGTRADES_PLACEHOLDER").hexdigest()
    if converter_sha256 is None:
        converter_sha256 = hashlib.sha256(b"TEST_FIXTURE_CONVERTER_PLACEHOLDER").hexdigest()
    sidecar = build_sidecar(rows, csv_sha256=facts_sha, source_sha256=source_sha256,
                            converter_sha256=converter_sha256)
    sidecar_path = os.path.join(out_dir, "FIXTURESYM-minute-facts-2026-05.sidecar.json")
    sidecar_text = json.dumps(sidecar, indent=1, sort_keys=True) + "\n"
    open(sidecar_path, "w", encoding="utf-8").write(sidecar_text)

    # Official-format klines CSV: headerless 12 columns, close_time = open+60e6-1.
    # number_of_trades is deliberately NOT agg_trade_count (NON_COMPARABLE_PAIRS).
    klines_lines = []
    for r in rows:
        klines_lines.append(",".join((
            str(r["_start_us"]),
            r["_kline_open"], r["_kline_high"], r["_kline_low"], r["_kline_close"],
            r["base_volume"],
            str(r["_end_us"] - 1),
            r["quote_volume"],
            str(int(r["agg_trade_count"]) + 1000),
            r["buy_initiated_base_volume"],
            r["buy_initiated_quote_volume"],
            "0",
        )))
    klines_text = "\n".join(klines_lines) + "\n"
    klines_path = os.path.join(out_dir, "FIXTURESYM-1m-2026-05.csv")
    open(klines_path, "w", encoding="utf-8").write(klines_text)
    klines_sha = hashlib.sha256(klines_text.encode()).hexdigest()

    return {
        "facts_path": facts_path,
        "sidecar_path": sidecar_path,
        "klines_csv_path": klines_path,
        "facts_sha256": facts_sha,
        "sidecar_sha256": hashlib.sha256(sidecar_text.encode()).hexdigest(),
        "klines_sha256": klines_sha,
        "source_sha256": source_sha256,
        "converter_sha256": converter_sha256,
        "rows": rows,
    }

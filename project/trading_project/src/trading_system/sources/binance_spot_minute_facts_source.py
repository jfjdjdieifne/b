"""Binance Spot aggTrades MINUTE-FACTS source loader/validator.

Loads the deterministic output of the local minute converter (23-column CSV +
sidecar JSON) as EXECUTED_INITIATED_FLOW facts. Validated strictly, fail-closed:

* exact 23-column schema and exact literal grammar (plain decimals / integers);
* sidecar identity, tie-ambiguity counts, and the reconciliation witness are
  RECOMPUTED from the rows and verified, not assumed;
* source/converter/output hashes are bound (and optionally checked against
  caller-supplied expected provenance).

The converter's reconstructed open/close are kept ONLY as witness columns
(``reconstructed_open_witness`` / ``reconstructed_close_witness``) for
comparison in unambiguous minutes. They are NEVER canonical OHLC: canonical OHLC
comes exclusively from the published klines source. Ambiguous values stay
flagged; ``TIE_ORDER_CONTRACT`` remains ``NOT_PROVEN``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from trading_system.sources import (
    CoverageError,
    HISTORICAL_RESEARCH_SOURCE_CONTRACT,
    INTERVAL_1M,
    MARKET_TYPE_SPOT,
    ProvenanceMismatchError,
    SchemaViolationError,
    SourceArtifactIdentity,
    TIE_ORDER_CONTRACT,
    TIMESTAMP_UNIT_MICROSECONDS,
    close_time_index_from_us,
    exact_equal,
    parse_int_literal,
    parse_plain_decimal,
    sha256_file,
)

MINUTE_US = 60_000_000
MINUTE_FACTS_SCHEMA_CONTRACT = "BINANCE_SPOT_AGGTRADES_MINUTE_FACTS_23COL_V1"
SOURCE_CONTRACT_EXPECTED = "BINANCE_SPOT_PUBLIC_DATA_AGGTRADES"

MINUTE_FACTS_COLUMNS: tuple = (
    "minute_start_utc",
    "minute_end_utc",
    "open",
    "high",
    "low",
    "close",
    "base_volume",
    "quote_volume",
    "agg_trade_count",
    "buy_initiated_base_volume",
    "sell_initiated_base_volume",
    "buy_initiated_quote_volume",
    "sell_initiated_quote_volume",
    "executed_base_delta",
    "executed_quote_delta",
    "first_agg_trade_id",
    "last_agg_trade_id",
    "first_transact_time_us",
    "last_transact_time_us",
    "open_ambiguous",
    "close_ambiguous",
    "open_tie_distinct_prices",
    "close_tie_distinct_prices",
)

_RE_MINUTE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_RE_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_PRICE_COLS = ("open", "high", "low", "close")
_BASE_COLS = (
    "base_volume",
    "buy_initiated_base_volume",
    "sell_initiated_base_volume",
    "executed_base_delta",
)
_QUOTE_COLS = (
    "quote_volume",
    "buy_initiated_quote_volume",
    "sell_initiated_quote_volume",
    "executed_quote_delta",
)
_INT_COLS = (
    "agg_trade_count",
    "first_agg_trade_id",
    "last_agg_trade_id",
    "first_transact_time_us",
    "last_transact_time_us",
    "open_ambiguous",
    "close_ambiguous",
    "open_tie_distinct_prices",
    "close_tie_distinct_prices",
)

_SIDECAR_REQUIRED_KEYS = (
    "converter_name",
    "converter_version",
    "converter_sha256",
    "source_sha256",
    "source_contract",
    "timestamp_unit",
    "source_rows_total",
    "legal_rows_consumed",
    "official_invalid_sentinel_count",
    "rejected_corrupt_rows",
    "output_minute_count",
    "covered_calendar_minute_count",
    "missing_minute_count",
    "missing_minute_intervals",
    "first_output_minute",
    "last_output_minute",
    "is_best_match_true_count",
    "is_best_match_false_count",
    "tie_timestamp_count",
    "ambiguous_open_minute_count",
    "ambiguous_close_minute_count",
    "TIE_ORDER_CONTRACT",
    "tie_order_evidence",
    "tie_order_policy",
    "bar_close_availability",
    "numeric_representation",
    "reconciliation",
    "output_csv_sha256",
    "generated_at_utc",
    "historical_provenance_statement",
)


@dataclass(frozen=True)
class MinuteFactsExpectedProvenance:
    """Optional caller-supplied expected binding (instance-level, never hard-coded)."""

    symbol: str | None = None
    raw_source_sha256: str | None = None
    converter_sha256: str | None = None
    minute_facts_sha256: str | None = None
    converter_name: str | None = None


@dataclass(frozen=True)
class MinuteFactsProvenance:
    """Provenance bound to ONE artifact instance (reconstruction witness only)."""

    identity: SourceArtifactIdentity
    schema_contract: str
    raw_source_sha256: str
    converter_sha256: str
    converter_name: str
    converter_version: str
    minute_facts_sha256: str
    sidecar_sha256: str
    sidecar_generated_at_utc: str
    timestamp_unit: str
    numeric_representation: str
    source_rows_total: int
    legal_rows_consumed: int
    official_invalid_sentinel_count: int
    tie_timestamp_count: int
    ambiguous_open_minute_count: int
    ambiguous_close_minute_count: int
    TIE_ORDER_CONTRACT: str
    reconciliation: dict
    historical_provenance_statement: str
    reconstruction_statement: str = (
        "RECONSTRUCTION_WITNESS_ONLY: hash binding proves file identity of the "
        "recorded artifacts; it is NOT historical generating-input provenance."
    )
    historical_research_contract: str = HISTORICAL_RESEARCH_SOURCE_CONTRACT


@dataclass(frozen=True)
class MinuteFactsSource:
    identity: SourceArtifactIdentity
    provenance: MinuteFactsProvenance
    exact_frame: pd.DataFrame  # original literal strings, CLOSE_TIME index
    frame: pd.DataFrame  # float64 convenience view, same index
    missing_minute_intervals: tuple
    require_full_coverage: bool


def _minute_iso_to_us(value: str, label: str) -> int:
    if not _RE_MINUTE_ISO.match(value):
        raise SchemaViolationError(f"MINUTE_ISO_INVALID:{label}")
    try:
        parsed = pd.Timestamp(value).tz_localize("UTC")
    except ValueError as exc:
        raise SchemaViolationError(f"MINUTE_ISO_INVALID:{label}") from exc
    return int(parsed.value // 1000)


def _verify_sidecar(sidecar: dict, csv_sha256: str, rows: list, csv_path: str) -> dict:
    if not isinstance(sidecar, dict):
        raise SchemaViolationError("SIDECAR_NOT_AN_OBJECT")
    for key in _SIDECAR_REQUIRED_KEYS:
        if key not in sidecar:
            raise SchemaViolationError(f"SIDECAR_KEY_MISSING:{key}")

    if sidecar["source_contract"] != SOURCE_CONTRACT_EXPECTED:
        raise SchemaViolationError("SIDECAR_SOURCE_CONTRACT_INVALID")
    if sidecar["timestamp_unit"] != TIMESTAMP_UNIT_MICROSECONDS:
        raise SchemaViolationError("SIDECAR_TIMESTAMP_UNIT_INVALID")
    if sidecar["TIE_ORDER_CONTRACT"] != TIE_ORDER_CONTRACT:
        raise SchemaViolationError("SIDECAR_TIE_ORDER_CONTRACT_INVALID")
    if not str(sidecar["bar_close_availability"]).strip():
        raise SchemaViolationError("SIDECAR_BAR_CLOSE_AVAILABILITY_EMPTY")
    for key in ("tie_order_evidence", "tie_order_policy", "numeric_representation",
                "historical_provenance_statement", "converter_name", "converter_version",
                "generated_at_utc"):
        if not str(sidecar[key]).strip():
            raise SchemaViolationError(f"SIDECAR_FIELD_EMPTY:{key}")
    for key in ("converter_sha256", "source_sha256", "output_csv_sha256"):
        if not _RE_HEX64.match(str(sidecar[key])):
            raise SchemaViolationError(f"SIDECAR_HASH_INVALID:{key}")

    if str(sidecar["output_csv_sha256"]) != csv_sha256:
        raise ProvenanceMismatchError("MINUTE_FACTS_CSV_HASH_MISMATCH")
    if int(sidecar["rejected_corrupt_rows"]) != 0:
        raise SchemaViolationError("SIDECAR_REJECTED_CORRUPT_ROWS_NONZERO")

    n_rows = len(rows)
    if int(sidecar["output_minute_count"]) != n_rows:
        raise SchemaViolationError("SIDECAR_OUTPUT_MINUTE_COUNT_MISMATCH")
    missing = int(sidecar["missing_minute_count"])
    intervals = sidecar["missing_minute_intervals"]
    if not isinstance(intervals, list):
        raise SchemaViolationError("SIDECAR_MISSING_INTERVALS_INVALID")
    if int(sidecar["covered_calendar_minute_count"]) != n_rows + missing:
        raise SchemaViolationError("SIDECAR_COVERED_COUNT_MISMATCH")
    if int(sidecar["source_rows_total"]) != (
        int(sidecar["legal_rows_consumed"]) + int(sidecar["official_invalid_sentinel_count"])
    ):
        raise SchemaViolationError("SIDECAR_ROW_COUNTS_INCONSISTENT")
    if (
        int(sidecar["is_best_match_true_count"]) + int(sidecar["is_best_match_false_count"])
        != int(sidecar["legal_rows_consumed"])
    ):
        raise SchemaViolationError("SIDECAR_BEST_MATCH_COUNTS_INCONSISTENT")

    # recompute ambiguity counts from the rows (verify, never assume)
    amb_open = sum(1 for r in rows if r["open_ambiguous"] == "1")
    amb_close = sum(1 for r in rows if r["close_ambiguous"] == "1")
    if int(sidecar["ambiguous_open_minute_count"]) != amb_open:
        raise SchemaViolationError("SIDECAR_AMBIGUOUS_OPEN_COUNT_MISMATCH")
    if int(sidecar["ambiguous_close_minute_count"]) != amb_close:
        raise SchemaViolationError("SIDECAR_AMBIGUOUS_CLOSE_COUNT_MISMATCH")

    # recompute calendar gap minutes from the rows (verify, never assume)
    starts_us = [
        int(pd.Timestamp(r["minute_start_utc"]).tz_localize("UTC").value // 1000) for r in rows
    ]
    gap_minutes = 0
    for prev, cur in zip(starts_us, starts_us[1:]):
        gap_minutes += (cur - prev) // MINUTE_US - 1
    if gap_minutes != missing:
        raise SchemaViolationError("SIDECAR_MISSING_MINUTE_COUNT_MISMATCH")
    if rows:
        if sidecar["first_output_minute"] != rows[0]["minute_start_utc"]:
            raise SchemaViolationError("SIDECAR_FIRST_OUTPUT_MINUTE_MISMATCH")
        if sidecar["last_output_minute"] != rows[-1]["minute_start_utc"]:
            raise SchemaViolationError("SIDECAR_LAST_OUTPUT_MINUTE_MISMATCH")
    else:
        if sidecar["first_output_minute"] is not None or sidecar["last_output_minute"] is not None:
            raise SchemaViolationError("SIDECAR_OUTPUT_MINUTES_MUST_BE_NULL")

    # recompute the reconciliation witness exactly
    total_base = sum((Decimal(r["base_volume"]) for r in rows), Decimal(0))
    total_quote = sum((Decimal(r["quote_volume"]) for r in rows), Decimal(0))
    total_count = sum(int(r["agg_trade_count"]) for r in rows)
    recon = sidecar["reconciliation"]
    if not isinstance(recon, dict):
        raise SchemaViolationError("SIDECAR_RECONCILIATION_NOT_AN_OBJECT")
    for key in ("exact_match_base", "exact_match_quote",
                "buy_plus_sell_base_matches_total", "buy_plus_sell_quote_matches_total",
                "sum_agg_trade_count_matches_legal_source_rows"):
        if recon.get(key) is not True:
            raise SchemaViolationError(f"SIDECAR_RECONCILIATION_FLAG_NOT_TRUE:{key}")
    for key, expected in (("source_base_sum", total_base), ("output_base_sum", total_base),
                          ("source_quote_sum", total_quote), ("output_quote_sum", total_quote)):
        if key not in recon or not exact_equal(str(recon[key]), str(expected)):
            raise SchemaViolationError(f"SIDECAR_RECONCILIATION_VALUE_MISMATCH:{key}")
    if total_count != int(sidecar["legal_rows_consumed"]):
        raise SchemaViolationError("SIDECAR_AGG_COUNT_SUM_MISMATCH")
    return {"total_base": total_base, "total_quote": total_quote, "total_count": total_count}


def load_minute_facts(
    csv_path: str,
    sidecar_path: str,
    *,
    identity: SourceArtifactIdentity,
    expected: MinuteFactsExpectedProvenance | None = None,
    require_full_coverage: bool = True,
) -> MinuteFactsSource:
    """Load + validate one minute-facts artifact instance (fail-closed)."""
    if identity.market_type != MARKET_TYPE_SPOT or identity.interval != INTERVAL_1M:
        raise SchemaViolationError("IDENTITY_UNSUPPORTED")

    with open(csv_path, "rb") as handle:
        raw = handle.read()
    csv_sha256 = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    lines = text.splitlines()
    if not lines:
        raise SchemaViolationError("MINUTE_FACTS_EMPTY_FILE")
    header = lines[0].split(",")
    if tuple(header) != MINUTE_FACTS_COLUMNS:
        raise SchemaViolationError("MINUTE_FACTS_HEADER_MISMATCH")

    rows = []
    for row_no, line in enumerate(lines[1:], start=2):
        fields = line.split(",")
        if len(fields) != len(MINUTE_FACTS_COLUMNS):
            raise SchemaViolationError(f"FIELD_COUNT:{row_no}")
        row = dict(zip(MINUTE_FACTS_COLUMNS, fields))
        row["_row_no"] = row_no
        rows.append(row)

    # ---- per-row strict validation (exact literals, no coercion) ----
    parsed_rows = []
    prev_start = None
    for row in rows:
        row_no = row["_row_no"]
        start_us = _minute_iso_to_us(row["minute_start_utc"], f"minute_start_utc:{row_no}")
        end_us = _minute_iso_to_us(row["minute_end_utc"], f"minute_end_utc:{row_no}")
        if start_us % MINUTE_US != 0:
            raise SchemaViolationError(f"MINUTE_START_NOT_ALIGNED:{row_no}")
        if end_us != start_us + MINUTE_US:
            raise SchemaViolationError(f"MINUTE_INTERVAL_INVALID:{row_no}")
        values = {}
        for col in _PRICE_COLS:
            values[col] = parse_plain_decimal(
                row[col], max_decimals=8, signed=False, label=f"{col}:{row_no}"
            )
        for col in _BASE_COLS:
            values[col] = parse_plain_decimal(
                row[col], max_decimals=8, signed=(col == "executed_base_delta"),
                label=f"{col}:{row_no}",
            )
        for col in _QUOTE_COLS:
            values[col] = parse_plain_decimal(
                row[col], max_decimals=16, signed=(col == "executed_quote_delta"),
                label=f"{col}:{row_no}",
            )
        for col in _INT_COLS:
            values[col] = parse_int_literal(row[col], label=f"{col}:{row_no}")
        if values["open_ambiguous"] not in (0, 1) or values["close_ambiguous"] not in (0, 1):
            raise SchemaViolationError(f"AMBIGUITY_FLAG_INVALID:{row_no}")
        if values["open_tie_distinct_prices"] < 1 or values["close_tie_distinct_prices"] < 1:
            raise SchemaViolationError(f"TIE_DISTINCT_PRICES_INVALID:{row_no}")
        if (values["open_tie_distinct_prices"] > 1) != (values["open_ambiguous"] == 1):
            raise SchemaViolationError(f"OPEN_AMBIGUITY_INVARIANT:{row_no}")
        if (values["close_tie_distinct_prices"] > 1) != (values["close_ambiguous"] == 1):
            raise SchemaViolationError(f"CLOSE_AMBIGUITY_INVARIANT:{row_no}")
        high, low = values["high"], values["low"]
        if high < low:
            raise SchemaViolationError(f"HIGH_LT_LOW:{row_no}")
        if not (low <= values["open"] <= high and low <= values["close"] <= high):
            raise SchemaViolationError(f"OHLC_BODY_OUT_OF_RANGE:{row_no}")
        if values["base_volume"] <= 0 or values["quote_volume"] < 0:
            raise SchemaViolationError(f"VOLUME_INVALID:{row_no}")
        if values["buy_initiated_base_volume"] < 0 or values["sell_initiated_base_volume"] < 0:
            raise SchemaViolationError(f"FLOW_VOLUME_INVALID:{row_no}")
        # executed-flow accounting is part of the source contract (verify, never assume)
        if values["buy_initiated_base_volume"] + values["sell_initiated_base_volume"] != values["base_volume"]:
            raise SchemaViolationError(f"BUY_PLUS_SELL_BASE_NE_TOTAL:{row_no}")
        if values["buy_initiated_quote_volume"] + values["sell_initiated_quote_volume"] != values["quote_volume"]:
            raise SchemaViolationError(f"BUY_PLUS_SELL_QUOTE_NE_TOTAL:{row_no}")
        if values["executed_base_delta"] != values["buy_initiated_base_volume"] - values["sell_initiated_base_volume"]:
            raise SchemaViolationError(f"EXECUTED_BASE_DELTA_INVALID:{row_no}")
        if values["executed_quote_delta"] != values["buy_initiated_quote_volume"] - values["sell_initiated_quote_volume"]:
            raise SchemaViolationError(f"EXECUTED_QUOTE_DELTA_INVALID:{row_no}")
        if values["first_agg_trade_id"] > values["last_agg_trade_id"]:
            raise SchemaViolationError(f"AGG_ID_RANGE_INVALID:{row_no}")
        if values["first_transact_time_us"] > values["last_transact_time_us"]:
            raise SchemaViolationError(f"TRANSACT_RANGE_INVALID:{row_no}")
        if prev_start is not None:
            if start_us == prev_start:
                raise CoverageError(f"DUPLICATE_MINUTE:{row_no}")
            if start_us < prev_start:
                raise CoverageError(f"MINUTE_ORDER_INVALID:{row_no}")
        prev_start = start_us
        values["_row_no"] = row_no
        values["_start_us"] = start_us
        values["_end_us"] = end_us
        parsed_rows.append(values)

    # ---- coverage contract ----
    missing_intervals = []
    for prev, cur in zip(parsed_rows, parsed_rows[1:]):
        gap_start = prev["_end_us"]
        gap_end = cur["_start_us"]
        if gap_end > gap_start:
            missing_intervals.append((gap_start, gap_end))
    if require_full_coverage and missing_intervals:
        raise CoverageError(f"MISSING_MINUTES_UNDER_FULL_COVERAGE:{len(missing_intervals)}")

    # ---- sidecar + reconciliation witness (recomputed) ----
    with open(sidecar_path, "rb") as handle:
        sidecar = json.load(handle)
    sidecar_sha256 = sha256_file(sidecar_path)
    row_literals = [
        {col: row[col] for col in MINUTE_FACTS_COLUMNS} for row in rows
    ]
    _verify_sidecar(sidecar, csv_sha256, row_literals, csv_path)

    # ---- expected provenance binding (instance-level) ----
    if expected is not None:
        if expected.symbol is not None and expected.symbol != identity.symbol:
            raise ProvenanceMismatchError("SYMBOL_MISMATCH")
        if expected.raw_source_sha256 is not None and expected.raw_source_sha256 != sidecar["source_sha256"]:
            raise ProvenanceMismatchError("RAW_SOURCE_HASH_MISMATCH")
        if expected.converter_sha256 is not None and expected.converter_sha256 != sidecar["converter_sha256"]:
            raise ProvenanceMismatchError("CONVERTER_HASH_MISMATCH")
        if expected.minute_facts_sha256 is not None and expected.minute_facts_sha256 != csv_sha256:
            raise ProvenanceMismatchError("MINUTE_FACTS_HASH_MISMATCH")
        if expected.converter_name is not None and expected.converter_name != sidecar["converter_name"]:
            raise ProvenanceMismatchError("CONVERTER_NAME_MISMATCH")

    provenance = MinuteFactsProvenance(
        identity=identity,
        schema_contract=MINUTE_FACTS_SCHEMA_CONTRACT,
        raw_source_sha256=sidecar["source_sha256"],
        converter_sha256=sidecar["converter_sha256"],
        converter_name=sidecar["converter_name"],
        converter_version=sidecar["converter_version"],
        minute_facts_sha256=csv_sha256,
        sidecar_sha256=sidecar_sha256,
        sidecar_generated_at_utc=sidecar["generated_at_utc"],
        timestamp_unit=sidecar["timestamp_unit"],
        numeric_representation=sidecar["numeric_representation"],
        source_rows_total=int(sidecar["source_rows_total"]),
        legal_rows_consumed=int(sidecar["legal_rows_consumed"]),
        official_invalid_sentinel_count=int(sidecar["official_invalid_sentinel_count"]),
        tie_timestamp_count=int(sidecar["tie_timestamp_count"]),
        ambiguous_open_minute_count=int(sidecar["ambiguous_open_minute_count"]),
        ambiguous_close_minute_count=int(sidecar["ambiguous_close_minute_count"]),
        TIE_ORDER_CONTRACT=sidecar["TIE_ORDER_CONTRACT"],
        reconciliation=dict(sidecar["reconciliation"]),
        historical_provenance_statement=sidecar["historical_provenance_statement"],
    )

    # ---- canonical-friendly frames (CLOSE_TIME index; witness-labeled O/C) ----
    index = close_time_index_from_us([r["_end_us"] for r in parsed_rows])
    exact = {
        "minute_start_us": pd.Series([str(r["_start_us"]) for r in parsed_rows], index=index),
        "minute_end_us": pd.Series([str(r["_end_us"]) for r in parsed_rows], index=index),
    }
    for col in MINUTE_FACTS_COLUMNS[2:]:
        exact[col] = pd.Series([r_raw[col] for r_raw in row_literals], index=index)
    exact_frame = pd.DataFrame(exact, index=index)
    exact_frame = exact_frame.rename(
        columns={"open": "reconstructed_open_witness", "close": "reconstructed_close_witness"}
    )

    float_frame = pd.DataFrame(
        {
            "high": pd.Series([float(r["high"]) for r in parsed_rows], index=index, dtype="float64"),
            "low": pd.Series([float(r["low"]) for r in parsed_rows], index=index, dtype="float64"),
            "base_volume": pd.Series(
                [float(r["base_volume"]) for r in parsed_rows], index=index, dtype="float64"
            ),
            "quote_volume": pd.Series(
                [float(r["quote_volume"]) for r in parsed_rows], index=index, dtype="float64"
            ),
            "buy_initiated_base_volume": pd.Series(
                [float(r["buy_initiated_base_volume"]) for r in parsed_rows], index=index, dtype="float64"
            ),
            "sell_initiated_base_volume": pd.Series(
                [float(r["sell_initiated_base_volume"]) for r in parsed_rows], index=index, dtype="float64"
            ),
            "open_ambiguous": pd.Series(
                [int(r["open_ambiguous"]) for r in parsed_rows], index=index, dtype="int64"
            ),
            "close_ambiguous": pd.Series(
                [int(r["close_ambiguous"]) for r in parsed_rows], index=index, dtype="int64"
            ),
        },
        index=index,
    )

    return MinuteFactsSource(
        identity=identity,
        provenance=provenance,
        exact_frame=exact_frame,
        frame=float_frame,
        missing_minute_intervals=tuple(
            (iso_pair[0], iso_pair[1]) for iso_pair in missing_intervals
        ),
        require_full_coverage=require_full_coverage,
    )

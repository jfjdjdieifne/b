"""Binance Spot official 1m KLINES source loader/validator (PUBLISHED_KLINE_OHLC).

Loads the documented public-data klines schema (12 headerless columns from
``/api/v3/klines``) and produces the CANONICAL market frame whose OHLC values
are Binance-published bar facts.

A kline open/close is a published bar fact; it does NOT prove intra-timestamp
tick chronology. ``TIE_ORDER_CONTRACT`` remains ``NOT_PROVEN``. Deterministic
reconstructed open/close values from aggTrades minute facts are never used as
canonical OHLC — not even in unambiguous minutes (where they are compared as a
witness only) and especially not in ambiguous minutes (where no match is
requested).

Cross-witness compares ONLY semantically compatible fields, exactly, with no
magic tolerance: minute key, high, low, base volume, quote volume, taker-buy
base volume. ``number_of_trades`` is NEVER compared to ``agg_trade_count``
(raw trades vs aggregates have different meanings). Any unexpected divergence
in a field that must match raises ``SourceInconsistencyError`` (fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from trading_system.sources import (
    CoverageError,
    EXECUTED_FLOW_SEMANTIC_LABEL,
    HISTORICAL_RESEARCH_SOURCE_CONTRACT,
    PUBLISHED_KLINE_OHLC_LABEL,
    ProvenanceMismatchError,
    SchemaViolationError,
    SourceArtifactIdentity,
    SourceInconsistencyError,
    TIE_ORDER_CONTRACT,
    TIMESTAMP_UNIT_MICROSECONDS,
    close_time_index_from_us,
    exact_equal,
    parse_int_literal,
    parse_plain_decimal,
    sha256_file,
)
from trading_system.sources.binance_spot_minute_facts_source import MinuteFactsSource

MINUTE_US = 60_000_000
# Public-data SPOT artifacts from 2025-01-01 are microseconds (source contract).
MIN_SPOT_MICROSECONDS_2025 = 1735689600000000
KLINES_SCHEMA_CONTRACT = "BINANCE_SPOT_PUBLIC_DATA_KLINES_1M_V1"

KLINES_COLUMNS: tuple = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "base_volume",
    "close_time",
    "quote_volume",
    "number_of_trades",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
)

# Semantic mapping of documented kline fields onto this adapter's vocabulary.
KLINES_FIELD_SEMANTICS: dict = {
    "open_time": "kline open time (microseconds)",
    "open": "published open price",
    "high": "published high price",
    "low": "published low price",
    "close": "published close price",
    "base_volume": "base asset volume",
    "close_time": "kline close time (microseconds, open_time+interval-1)",
    "quote_volume": "quote asset volume",
    "number_of_trades": "raw trade count (NOT comparable with agg_trade_count)",
    "taker_buy_base_volume": "taker buy base asset volume",
    "taker_buy_quote_volume": "taker buy quote asset volume",
    "ignore": "ignored field as documented by the source",
}

NON_COMPARABLE_PAIRS: tuple = (
    {
        "kline_field": "number_of_trades",
        "facts_field": "agg_trade_count",
        "reason": "RAW_TRADE_COUNT_VS_AGGREGATE_TRADE_COUNT_DIFFERENT_SEMANTICS",
    },
)


@dataclass(frozen=True)
class KlineExpectedProvenance:
    """Optional caller-supplied expected binding (instance-level, never hard-coded)."""

    symbol: str | None = None
    source_file_sha256: str | None = None


@dataclass(frozen=True)
class KlineProvenance:
    identity: SourceArtifactIdentity
    schema_contract: str
    source_file_sha256: str
    source_rows: int
    timestamp_unit: str
    numeric_contract: str
    ohlc_source_label: str = PUBLISHED_KLINE_OHLC_LABEL
    retrieval_metadata: tuple = ()
    tie_order_contract: str = TIE_ORDER_CONTRACT
    published_fact_statement: str = (
        "KLINE_IS_BINANCE_PUBLISHED_BAR_FACT: official kline open/close are "
        "published values of this source contract; they do NOT prove tick "
        "chronology inside equal timestamps. TIE_ORDER_CONTRACT remains NOT_PROVEN."
    )
    historical_research_contract: str = HISTORICAL_RESEARCH_SOURCE_CONTRACT


@dataclass(frozen=True)
class KlineOhlcSource:
    identity: SourceArtifactIdentity
    provenance: KlineProvenance
    exact_frame: pd.DataFrame  # original literal strings, CLOSE_TIME index
    canonical_market_frame: pd.DataFrame  # open/high/low/close/volume float64
    missing_minute_intervals: tuple
    require_full_coverage: bool


@dataclass(frozen=True)
class CrossWitnessResult:
    identity: SourceArtifactIdentity
    compared_minutes: int
    exact_matched_fields: tuple = (
        "minute_key",
        "high",
        "low",
        "base_volume",
        "quote_volume",
        "taker_buy_base_volume",
    )
    unambiguous_oc_witness_compared: int = 0
    unambiguous_oc_policy: str = "EXPECT_MATCH"
    ambiguous_minutes_skipped_by_contract: int = 0
    taker_buy_quote_status: str = "NOT_COMPARABLE_PRECISION"
    taker_buy_quote_reason: str = ""
    non_comparable_fields: tuple = NON_COMPARABLE_PAIRS
    statement: str = (
        "CROSS_WITNESS: exact fixed-point/Decimal equality only; no magic tolerance. "
        "Ambiguous reconstructed open/close are never required to match and never "
        "enter canonical OHLC."
    )


@dataclass(frozen=True)
class CanonicalMarketBundle:
    canonical_market_frame: pd.DataFrame
    kline_provenance: KlineProvenance
    executed_flow_semantic_label: str = EXECUTED_FLOW_SEMANTIC_LABEL
    cross_witness: CrossWitnessResult | None = None
    tie_ambiguity_counts: dict = field(default_factory=dict)
    tie_order_contract: str = TIE_ORDER_CONTRACT
    ohlc_source_label: str = PUBLISHED_KLINE_OHLC_LABEL


def load_binance_spot_klines(
    csv_path: str,
    *,
    identity: SourceArtifactIdentity,
    expected: KlineExpectedProvenance | None = None,
    retrieval_metadata: dict | None = None,
    require_full_coverage: bool = True,
) -> KlineOhlcSource:
    """Load + validate one official 1m klines artifact instance (fail-closed)."""
    file_sha = sha256_file(csv_path)
    with open(csv_path, "rb") as handle:
        text = handle.read().decode("utf-8")
    lines = [ln for ln in text.splitlines() if ln != ""]
    if not lines:
        raise SchemaViolationError("KLINES_EMPTY_FILE")

    rows = []
    for row_no, line in enumerate(lines, start=1):
        fields = line.split(",")
        if len(fields) != len(KLINES_COLUMNS):
            raise SchemaViolationError(f"FIELD_COUNT:{row_no}")
        rows.append((row_no, dict(zip(KLINES_COLUMNS, fields))))

    parsed = []
    prev_open = None
    for row_no, row in rows:
        open_us = parse_int_literal(row["open_time"], label=f"open_time:{row_no}")
        close_us = parse_int_literal(row["close_time"], label=f"close_time:{row_no}")
        if open_us < MIN_SPOT_MICROSECONDS_2025:
            raise SchemaViolationError(
                f"TIMESTAMP_UNIT_INVALID:{row_no}: expected MICROSECONDS (spot >= 2025-01-01)"
            )
        if open_us % MINUTE_US != 0:
            raise SchemaViolationError(f"OPEN_TIME_NOT_1M_ALIGNED:{row_no}")
        if close_us != open_us + MINUTE_US - 1:
            raise SchemaViolationError(
                f"INTERVAL_INVALID:{row_no}: close_time must equal open_time + 60000000 - 1"
            )
        values = {}
        for col in ("open", "high", "low", "close", "base_volume", "quote_volume",
                    "taker_buy_base_volume", "taker_buy_quote_volume"):
            values[col] = parse_plain_decimal(
                row[col], max_decimals=8, signed=False, label=f"{col}:{row_no}"
            )
        values["number_of_trades"] = parse_int_literal(row["number_of_trades"], label=f"number_of_trades:{row_no}")
        values["ignore"] = parse_int_literal(row["ignore"], label=f"ignore:{row_no}")
        high, low = values["high"], values["low"]
        if high < low:
            raise SchemaViolationError(f"HIGH_LT_LOW:{row_no}")
        if not (low <= values["open"] <= high and low <= values["close"] <= high):
            raise SchemaViolationError(f"OHLC_BODY_OUT_OF_RANGE:{row_no}")
        if values["base_volume"] < 0 or values["quote_volume"] < 0:
            raise SchemaViolationError(f"VOLUME_INVALID:{row_no}")
        if values["taker_buy_base_volume"] < 0 or values["taker_buy_quote_volume"] < 0:
            raise SchemaViolationError(f"TAKER_BUY_VOLUME_INVALID:{row_no}")
        if values["taker_buy_base_volume"] > values["base_volume"]:
            raise SchemaViolationError(f"TAKER_BUY_BASE_GT_VOLUME:{row_no}")
        if prev_open is not None:
            if open_us == prev_open:
                raise CoverageError(f"DUPLICATE_MINUTE:{row_no}")
            if open_us < prev_open:
                raise CoverageError(f"MINUTE_ORDER_INVALID:{row_no}")
        prev_open = open_us
        values["_row_no"] = row_no
        values["_open_us"] = open_us
        values["_close_us"] = close_us
        parsed.append(values)

    missing_intervals = []
    for prev, cur in zip(parsed, parsed[1:]):
        expected_next = prev["_open_us"] + MINUTE_US
        if cur["_open_us"] > expected_next:
            missing_intervals.append((expected_next, cur["_open_us"]))
    if require_full_coverage and missing_intervals:
        raise CoverageError(f"MISSING_MINUTES_UNDER_FULL_COVERAGE:{len(missing_intervals)}")

    if expected is not None:
        if expected.symbol is not None and expected.symbol != identity.symbol:
            raise ProvenanceMismatchError("SYMBOL_MISMATCH")
        if expected.source_file_sha256 is not None and expected.source_file_sha256 != file_sha:
            raise ProvenanceMismatchError("KLINE_SOURCE_HASH_MISMATCH")

    retrieval = tuple(sorted((str(k), str(v)) for k, v in (retrieval_metadata or {}).items()))
    provenance = KlineProvenance(
        identity=identity,
        schema_contract=KLINES_SCHEMA_CONTRACT,
        source_file_sha256=file_sha,
        source_rows=len(parsed),
        timestamp_unit=TIMESTAMP_UNIT_MICROSECONDS,
        numeric_contract="EXACT_PLAIN_DECIMAL_STRINGS_MAX_8DP; canonical frame float64 at engine boundary",
        retrieval_metadata=retrieval,
    )

    index = close_time_index_from_us([r["_open_us"] + MINUTE_US for r in parsed])
    exact_data = {
        col: pd.Series([str(r_raw[col]) for _, r_raw in rows], index=index)
        for col in KLINES_COLUMNS
    }
    exact_data["open_time_us"] = pd.Series([str(r["_open_us"]) for r in parsed], index=index)
    exact_frame = pd.DataFrame(exact_data, index=index)

    canonical = pd.DataFrame(
        {
            "open": pd.Series([float(r["open"]) for r in parsed], index=index, dtype="float64"),
            "high": pd.Series([float(r["high"]) for r in parsed], index=index, dtype="float64"),
            "low": pd.Series([float(r["low"]) for r in parsed], index=index, dtype="float64"),
            "close": pd.Series([float(r["close"]) for r in parsed], index=index, dtype="float64"),
            "volume": pd.Series(
                [float(r["base_volume"]) for r in parsed], index=index, dtype="float64"
            ),
        },
        index=index,
    )

    return KlineOhlcSource(
        identity=identity,
        provenance=provenance,
        exact_frame=exact_frame,
        canonical_market_frame=canonical,
        missing_minute_intervals=tuple(missing_intervals),
        require_full_coverage=require_full_coverage,
    )


def _require_same_identity(klines: KlineOhlcSource, facts: MinuteFactsSource) -> None:
    a, b = klines.identity, facts.identity
    for name in ("symbol", "market_type", "interval", "period_start_utc", "period_end_utc",
                 "timestamp_unit"):
        if getattr(a, name) != getattr(b, name):
            raise ProvenanceMismatchError(f"IDENTITY_MISMATCH:{name}")


def cross_witness_sources(
    klines: KlineOhlcSource,
    facts: MinuteFactsSource,
    *,
    require_same_coverage: bool = True,
    unambiguous_oc_policy: str = "EXPECT_MATCH",
    compare_taker_buy_quote: bool = True,
) -> CrossWitnessResult:
    """Verify compatible fields across the two sources EXACTLY (fail-closed).

    Compared (exact fixed-point/Decimal equality, no tolerance): minute key,
    high, low, base volume, quote volume, taker-buy base volume. Unambiguous
    reconstructed open/close are compared as a WITNESS per ``unambiguous_oc_policy``
    (default: divergence raises SourceInconsistencyError). Ambiguous minutes are
    never required to match. ``number_of_trades`` is never compared with
    ``agg_trade_count``. Taker-buy quote volume is compared only when the
    definition and literal precision are compatible.
    """
    if unambiguous_oc_policy not in ("EXPECT_MATCH", "RECORD_ONLY"):
        raise SchemaViolationError("UNAMBIGUOUS_OC_POLICY_INVALID")
    _require_same_identity(klines, facts)

    k_index = list(klines.exact_frame["open_time_us"])
    f_index = [str(v) for v in facts.exact_frame["minute_start_us"]]
    if require_same_coverage:
        if k_index != f_index:
            raise SourceInconsistencyError("MINUTE_KEY_SET_MISMATCH")
    else:
        keys_k, keys_f = set(k_index), set(f_index)
        if not keys_k <= keys_f and not keys_f <= keys_k:
            pass  # intersection mode: compare the common keys only
        common = [k for k in k_index if k in keys_f]
        k_index = common

    k_rows = {str(r): i for i, r in enumerate(klines.exact_frame["open_time_us"])}
    f_rows = {str(r): i for i, r in enumerate(facts.exact_frame["minute_start_us"])}
    compared = 0
    oc_witness = 0
    ambiguous_skipped = 0
    for key in k_index:
        ki, fi = k_rows[key], f_rows[key]
        pairs = (
            ("high", klines.exact_frame["high"].iloc[ki], facts.exact_frame["high"].iloc[fi]),
            ("low", klines.exact_frame["low"].iloc[ki], facts.exact_frame["low"].iloc[fi]),
            ("base_volume", klines.exact_frame["base_volume"].iloc[ki],
             facts.exact_frame["base_volume"].iloc[fi]),
            ("quote_volume", klines.exact_frame["quote_volume"].iloc[ki],
             facts.exact_frame["quote_volume"].iloc[fi]),
            ("taker_buy_base_volume", klines.exact_frame["taker_buy_base_volume"].iloc[ki],
             facts.exact_frame["buy_initiated_base_volume"].iloc[fi]),
        )
        for name, left, right in pairs:
            if not exact_equal(str(left), str(right)):
                raise SourceInconsistencyError(f"UNEXPECTED_DIVERGENCE:{name}:{key}")

        amb_open = facts.exact_frame["open_ambiguous"].iloc[fi] == "1"
        amb_close = facts.exact_frame["close_ambiguous"].iloc[fi] == "1"
        if amb_open or amb_close:
            ambiguous_skipped += 1
        elif unambiguous_oc_policy == "EXPECT_MATCH":
            for name, left, right in (
                ("open_witness", klines.exact_frame["open"].iloc[ki],
                 facts.exact_frame["reconstructed_open_witness"].iloc[fi]),
                ("close_witness", klines.exact_frame["close"].iloc[ki],
                 facts.exact_frame["reconstructed_close_witness"].iloc[fi]),
            ):
                if not exact_equal(str(left), str(right)):
                    raise SourceInconsistencyError(f"UNEXPECTED_DIVERGENCE:{name}:{key}")
            oc_witness += 1
        else:
            oc_witness += 1

        if compare_taker_buy_quote:
            k_tbq = str(klines.exact_frame["taker_buy_quote_volume"].iloc[ki])
            f_tbq = str(facts.exact_frame["buy_initiated_quote_volume"].iloc[fi])
            k_dp = len(k_tbq.split(".", 1)[1]) if "." in k_tbq else 0
            f_dp = len(f_tbq.split(".", 1)[1]) if "." in f_tbq else 0
            if k_dp > f_dp:
                raise SchemaViolationError("TAKER_BUY_QUOTE_LITERAL_PRECISION_INCOMPATIBLE")
            if not exact_equal(k_tbq, f_tbq):
                raise SourceInconsistencyError(f"UNEXPECTED_DIVERGENCE:taker_buy_quote_volume:{key}")
        compared += 1

    tbq_status = "EXACT_MATCH" if compare_taker_buy_quote else "NOT_COMPARABLE_PRECISION"
    tbq_reason = (
        "definition=TAKER_BUY_QUOTE_ASSET_VOLUME matches buy_initiated_quote_volume; "
        "published decimals <= facts decimals"
        if compare_taker_buy_quote
        else "comparison skipped by caller policy"
    )
    return CrossWitnessResult(
        identity=klines.identity,
        compared_minutes=compared,
        unambiguous_oc_witness_compared=oc_witness,
        unambiguous_oc_policy=unambiguous_oc_policy,
        ambiguous_minutes_skipped_by_contract=ambiguous_skipped,
        taker_buy_quote_status=tbq_status,
        taker_buy_quote_reason=tbq_reason,
    )


def assemble_canonical_bundle(
    kline_source: KlineOhlcSource,
    minute_facts: MinuteFactsSource | None = None,
    *,
    cross_witness: CrossWitnessResult | None = None,
) -> CanonicalMarketBundle:
    """Assemble the canonical market bundle from validated source objects.

    The canonical frame is EXACTLY the published-kline frame: ambiguous
    reconstructed open/close values can never enter it. No engine runs here and
    ``MarketObservationTimeline.seal`` remains the caller's separate public call.
    """
    canonical = kline_source.canonical_market_frame
    if list(canonical.columns) != ["open", "high", "low", "close", "volume"]:
        raise SchemaViolationError("CANONICAL_FRAME_COLUMNS_INVALID")
    witness = cross_witness
    if minute_facts is not None and witness is None:
        witness = cross_witness_sources(kline_source, minute_facts)
    tie_counts = {}
    if minute_facts is not None:
        tie_counts = {
            "tie_timestamp_count": minute_facts.provenance.tie_timestamp_count,
            "ambiguous_open_minute_count": minute_facts.provenance.ambiguous_open_minute_count,
            "ambiguous_close_minute_count": minute_facts.provenance.ambiguous_close_minute_count,
            "TIE_ORDER_CONTRACT": TIE_ORDER_CONTRACT,
        }
    return CanonicalMarketBundle(
        canonical_market_frame=canonical,
        kline_provenance=kline_source.provenance,
        cross_witness=witness,
        tie_ambiguity_counts=tie_counts,
    )

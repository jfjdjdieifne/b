"""Binance Spot SOURCE ADAPTERS — shared source contracts (loader/validator layer).

This package is the SOURCE boundary between documented Binance Spot public-data
artifacts and the CLOSED project. It provides ONLY loader/validator/provenance
functions that produce canonical factual frames. It does NOT run engines and it
does NOT seal ``MarketObservationTimeline`` (the caller/runner seals, per the
Stage 1 public contract).

Two independent sources are integrated without correcting chronology for each
other:

* official 1m klines   -> PUBLISHED_KLINE_OHLC (Binance-published bar fact)
* aggTrades minute facts -> EXECUTED_INITIATED_FLOW (executed/volume facts)

``TIE_ORDER_CONTRACT`` remains ``NOT_PROVEN`` always: a kline open/close is a
Binance-published bar fact and does NOT prove intra-timestamp tick chronology.
Ambiguity discovered in aggTrades stays preserved in provenance and is never
erased, and ambiguous reconstructed open/close values are never used as factual
canonical OHLC.

Semantic naming is restricted to EXECUTED/INITIATED flow of this source.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

MARKET_TYPE_SPOT = "SPOT"
INTERVAL_1M = "1m"
TIMESTAMP_UNIT_MICROSECONDS = "MICROSECONDS"
TIE_ORDER_CONTRACT = "NOT_PROVEN"
PUBLISHED_KLINE_OHLC_LABEL = "PUBLISHED_KLINE_OHLC"
EXECUTED_FLOW_SEMANTIC_LABEL = "EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT"
EXECUTED_FLOW_VOLUME_UNIT = "BASE_ASSET"
HISTORICAL_RESEARCH_SOURCE_CONTRACT = (
    "HISTORICAL_RESEARCH_SOURCE_CONTRACT_ONLY: no live availability is claimed; "
    "canonical bars use CLOSE_TIME timestamp semantics (bar completion instant) "
    "compatible with the CLOSED project contracts."
)

_RE_SYMBOL = re.compile(r"^[A-Z0-9]{2,30}$")
_RE_UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_RE_INT = re.compile(r"^\d+$")
_RE_DEC_UNSIGNED = re.compile(r"^\d+(?:\.\d+)?$")
_RE_DEC_SIGNED = re.compile(r"^-?\d+(?:\.\d+)?$")

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class BinanceSourceError(Exception):
    """Base error for the Binance Spot source adapters."""


class SchemaViolationError(BinanceSourceError):
    """Malformed artifact schema, unsupported identity field, or bad literal."""


class ProvenanceMismatchError(BinanceSourceError):
    """Expected provenance binding or cross-artifact identity mismatch."""


class SourceInconsistencyError(BinanceSourceError):
    """Unexpected divergence in a field that must match across sources."""


class CoverageError(BinanceSourceError):
    """Duplicate minute or missing minute under a full-coverage contract."""


@dataclass(frozen=True)
class SourceArtifactIdentity:
    """Instance identity of one Binance Spot source artifact.

    Generic by construction: no specific symbol/period is special-cased anywhere
    in this package. ``period_*_utc`` must be UTC-suffixed ISO-8601 strings
    (naive timestamps are rejected).
    """

    symbol: str
    market_type: str
    interval: str
    period_start_utc: str
    period_end_utc: str
    timestamp_unit: str = TIMESTAMP_UNIT_MICROSECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not _RE_SYMBOL.match(self.symbol):
            raise SchemaViolationError("SYMBOL_INVALID")
        if self.market_type != MARKET_TYPE_SPOT:
            raise SchemaViolationError("MARKET_TYPE_UNSUPPORTED: this source contract is SPOT only")
        if self.interval != INTERVAL_1M:
            raise SchemaViolationError("INTERVAL_UNSUPPORTED: this source contract is 1m only")
        if self.timestamp_unit != TIMESTAMP_UNIT_MICROSECONDS:
            raise SchemaViolationError(
                "TIMESTAMP_UNIT_UNSUPPORTED: this source contract is MICROSECONDS only"
            )
        for name in ("period_start_utc", "period_end_utc"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _RE_UTC_Z.match(value):
                raise SchemaViolationError(
                    f"PERIOD_TIMESTAMP_INVALID:{name}: UTC 'Z' suffix required (naive rejected)"
                )
        if self.period_start_utc >= self.period_end_utc:
            raise SchemaViolationError("PERIOD_INVALID")


def parse_plain_decimal(field: str, *, max_decimals: int, signed: bool, label: str) -> Decimal:
    """Parse one plain decimal literal exactly (no exponent, no coercion)."""
    if not isinstance(field, str):
        raise SchemaViolationError(f"NOT_A_STRING:{label}")
    pattern = _RE_DEC_SIGNED if signed else _RE_DEC_UNSIGNED
    if not pattern.match(field):
        raise SchemaViolationError(f"DECIMAL_LITERAL_INVALID:{label}")
    if "." in field:
        fraction = field.split(".", 1)[1]
        if len(fraction) > max_decimals:
            raise SchemaViolationError(f"DECIMAL_PRECISION_EXCEEDED:{label}")
    try:
        return Decimal(field)
    except InvalidOperation as exc:  # pragma: no cover - regex already gates
        raise SchemaViolationError(f"DECIMAL_LITERAL_INVALID:{label}") from exc


def parse_int_literal(field: str, *, label: str) -> int:
    if not isinstance(field, str) or not _RE_INT.match(field):
        raise SchemaViolationError(f"INT_LITERAL_INVALID:{label}")
    return int(field)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close_time_index_from_us(instants_us) -> "object":
    """Build the canonical tz-aware UTC CLOSE_TIME DatetimeIndex (ns).

    Input: iterable of bar-completion instants in MICROSECONDS (already
    ``minute_start_us + 60_000_000``). Timestamp semantics: CLOSE_TIME.
    """
    import pandas as pd

    values = [int(v) for v in instants_us]
    if any(v <= 0 for v in values):
        raise SchemaViolationError("CLOSE_TIME_INSTANT_INVALID")
    index = pd.DatetimeIndex(pd.to_datetime(values, unit="us", utc=True))
    if index.tz is None:  # pragma: no cover - utc=True guarantees tz
        raise SchemaViolationError("TIMEZONE_NAIVE_INDEX_FORBIDDEN")
    index.name = None
    return index


def iso_utc_z_from_us(instant_us: int) -> str:
    dt = _EPOCH + timedelta(microseconds=int(instant_us))
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + (".%06dZ" % dt.microsecond)


def exact_equal(left: str, right: str) -> bool:
    """Exact fixed-point/Decimal equality (no tolerance, scale-insensitive)."""
    return Decimal(left) == Decimal(right)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aggtrades_to_minute_facts.py — LOCAL SOURCE CONVERTER (Binanace Spot aggTrades -> 1-minute fact table).

BOUNDARY
--------
SOURCE CONVERTER ONLY: documented Binance Spot public-data aggTrades CSV
-> factual 1-minute table. It does NOT run, wrap, or reimplement any project
engine (no volatility/session/swing/BOS/liquidity/orderflow/OB/FVG/HTF/...).
Those CLOSED engines will be consumed later through their public contracts by
an official Source Adapter INSIDE the project — not here.

CONTRACT
--------
* Standard library only. Streaming, bounded memory. No full-file copy, no
  external sort. No binary floating point in any accumulation or output.
* Numeric representation: INTEGER FIXED-POINT parsed from the original decimal
  strings. price/base scale = 8 decimals, quote scale = 16 decimals (8+8).
* minute_bucket = floor(transact_time_us / 60_000_000); minute interval is
  [minute_start, minute_end) in TRADE-TIME membership. This converter does NOT
  claim bar-close availability: `bar_close_availability = NOT_CLAIMED_BY_CONVERTER`.
* TIE_ORDER_CONTRACT = NOT_PROVEN (no official Binance document guarantees
  intra-timestamp ordering by agg_trade_id). Policy: AMBIGUITY_METADATA — open/close
  are selected deterministically by (transact_time_us, agg_trade_id); minutes whose
  extreme timestamp group has >1 distinct price are FLAGGED (open_ambiguous /
  close_ambiguous). Flagged values are NOT market-chronology-proven.
* Official INVALID sentinel rows (price=0 AND quantity=0 AND first=-1 AND last=-1,
  Binance changelog 2022-04-12) are COUNTED and RECORDED, never silently dropped,
  and never aggregated.
* Any other corruption => FAIL CLOSED (row number + error class). No silent skip,
  no repair, no coercion, no auto-sort.
* Executed/initiated flow naming ONLY (is_buyer_maker=False -> buy_initiated).
  Forbidden claims: buying pressure / order-book pressure / institutional /
  whale / market-wide order flow.

Exit codes: 0 OK; 2 usage/source-not-found; 3 fail-closed corruption;
4 internal reconciliation failure.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

TOOL_NAME = "aggtrades_to_minute_facts.py"
TOOL_VERSION = "1.0.0"
CONVERTER_NAME = "aggtrades_to_minute_facts"

SOURCE_CONTRACT = "BINANCE_SPOT_PUBLIC_DATA_AGGTRADES"
SOURCE_SCHEMA_VERSION = "BINANCE_SPOT_AGGTRADES_8COL_V1"
DOCUMENTED_SOURCE_REFERENCES = [
    "https://raw.githubusercontent.com/binance/binance-public-data/master/README.md",
    "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints",
    "https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams",
    "https://github.com/binance/binance-spot-api-docs/blob/master/CHANGELOG.md#2022-04-12",
]
TIMESTAMP_UNIT = "MICROSECONDS"
MINUTE_US = 60_000_000
PRICE_SCALE = 8
BASE_SCALE = 8
QUOTE_SCALE = 16

TIE_ORDER_CONTRACT = "NOT_PROVEN"
TIE_ORDER_EVIDENCE = (
    "Official Binance documents provide: (a) REST General: 'Data is returned in "
    "chronological order, unless noted otherwise'; (b) aggTrades fromId paging "
    "'Use fromId and limit to page through all aggtrades' (agg_trade_id is the "
    "canonical enumeration key); (c) changelog 2022-04-12 tracks missing/duplicate "
    "aggregate trades by that key. NO official document states that agg_trade_id "
    "encodes market execution order among rows sharing one transact_time_us."
)
TIE_ORDER_POLICY = (
    "AMBIGUITY_METADATA: open/close selected deterministically by "
    "(transact_time_us, agg_trade_id); minutes whose extreme-timestamp group "
    "contains more than one distinct price are flagged open_ambiguous/close_ambiguous. "
    "Flagged values are deterministic output convention, NOT proven market chronology."
)

BAR_CLOSE_AVAILABILITY = "NOT_CLAIMED_BY_CONVERTER"
MINUTE_INTERVAL_CONTRACT = "[minute_start, minute_end) trade-time membership; minute_bucket=floor(transact_time_us/60000000)"
NUMERIC_REPRESENTATION = (
    "INTEGER_FIXED_POINT price_scale=8 base_scale=8 quote_scale=16 parsed from "
    "source decimal strings; zero binary floating point in accumulation or output"
)
EXECUTED_FLOW_SEMANTICS = (
    "is_buyer_maker=False -> buy_initiated (buyer was taker); is_buyer_maker=True -> "
    "sell_initiated (seller was taker). These columns describe EXECUTED/INITIATED "
    "flow in this Binance Spot source only: a fill-side accounting of taker "
    "direction. No pressure, participant-level, or book-state claim is made or implied."
)
HISTORICAL_PROVENANCE_STATEMENT = (
    "The source is the Binance file identified by the recorded SHA-256. This "
    "converter alone does not prove the file's generating history beyond the "
    "documented source contract. Provenance must not be extended beyond recorded "
    "evidence."
)
SENTINEL_RULE = (
    "Official invalid sentinel rows (price=0 AND quantity=0 AND first_trade_id=-1 "
    "AND last_trade_id=-1) are counted, recorded in the sidecar, and excluded "
    "from aggregation."
)

CSV_COLUMNS = [
    "minute_start_utc", "minute_end_utc",
    "open", "high", "low", "close",
    "base_volume", "quote_volume", "agg_trade_count",
    "buy_initiated_base_volume", "sell_initiated_base_volume",
    "buy_initiated_quote_volume", "sell_initiated_quote_volume",
    "executed_base_delta", "executed_quote_delta",
    "first_agg_trade_id", "last_agg_trade_id",
    "first_transact_time_us", "last_transact_time_us",
    "open_ambiguous", "close_ambiguous",
    "open_tie_distinct_prices", "close_tie_distinct_prices",
]

MAX_GAP_INTERVALS = 1000
MAX_SENTINEL_RECORDS = 1000
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

RE_INT_STRICT = re.compile(rb"^-?\d+$")
RE_INT_NONNEG = re.compile(rb"^\d+$")
RE_DECIMAL = re.compile(rb"^\d+(\.\d{1,8})?$")
RE_BOOL = re.compile(rb"^(True|False)$")


class ConverterError(Exception):
    def __init__(self, row_no, error_class, detail=""):
        super().__init__("row=%s class=%s %s" % (row_no, error_class, detail))
        self.row_no = row_no
        self.error_class = error_class
        self.detail = detail


def tool_self_sha256() -> str:
    with open(__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_fixed(field: bytes, scale: int, row_no: int, error_class: str) -> int:
    if not RE_DECIMAL.match(field):
        raise ConverterError(row_no, error_class, "value=%r" % field[:32])
    if b"." in field:
        ip, fp = field.split(b".")
        if len(fp) > scale:
            raise ConverterError(row_no, error_class, "too many decimals value=%r" % field[:32])
        fp = fp + b"0" * (scale - len(fp))
    else:
        ip, fp = field, b"0" * scale
    return int(ip or b"0") * (10 ** scale) + int(fp or b"0")


def parse_int(field: bytes, row_no: int, error_class: str, nonneg=False) -> int:
    pat = RE_INT_NONNEG if nonneg else RE_INT_STRICT
    if not pat.match(field):
        raise ConverterError(row_no, error_class, "value=%r" % field[:32])
    return int(field)


def parse_bool(field: bytes, row_no: int) -> bool:
    if not RE_BOOL.match(field):
        raise ConverterError(row_no, "BOOL_INVALID", "value=%r" % field[:32])
    return field == b"True"


def fmt_fixed(value: int, scale: int) -> str:
    neg = value < 0
    v = abs(value)
    ip, fp = divmod(v, 10 ** scale)
    s = "%d.%0*d" % (ip, scale, fp)
    return "-" + s if neg else s


def iso_minute(bucket: int) -> str:
    dt = EPOCH + timedelta(microseconds=bucket * MINUTE_US)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def iso_us(us: int) -> str:
    dt = EPOCH + timedelta(microseconds=us)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + (".%06dZ" % (us % 1_000_000))


class _Run:
    """Consecutive legal rows sharing one transact_time_us (one price-run state)."""
    __slots__ = ("ts", "first_price", "last_price", "count", "prices")

    def __init__(self, ts, price):
        self.ts = ts
        self.first_price = price   # price at min agg_trade_id in the run
        self.last_price = price    # price at max agg_trade_id in the run
        self.count = 1
        self.prices = {price}

    def add(self, price):
        self.last_price = price
        self.count += 1
        self.prices.add(price)


class _Bucket:
    __slots__ = ("idx", "base", "quote", "count", "buy_base", "sell_base",
                 "buy_quote", "sell_quote", "high", "low", "first_id", "last_id",
                 "first_ts", "last_ts", "open_run")

    def __init__(self, idx, row_id, ts, price, q_base, q_quote, buy, run):
        self.idx = idx
        self.base = q_base
        self.quote = q_quote
        self.count = 1
        self.buy_base = q_base if buy else 0
        self.sell_base = 0 if buy else q_base
        self.buy_quote = q_quote if buy else 0
        self.sell_quote = 0 if buy else q_quote
        self.high = price
        self.low = price
        self.first_id = row_id
        self.last_id = row_id
        self.first_ts = ts
        self.last_ts = ts
        self.open_run = run

    def add(self, row_id, ts, price, q_base, q_quote, buy):
        self.base += q_base
        self.quote += q_quote
        self.count += 1
        if buy:
            self.buy_base += q_base
            self.buy_quote += q_quote
        else:
            self.sell_base += q_base
            self.sell_quote += q_quote
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.last_id = row_id
        self.last_ts = ts


def convert(source_path: str, out_prefix: str) -> dict:
    csv_path = out_prefix + ".csv"
    sidecar_path = out_prefix + ".sidecar.json"
    failed_path = out_prefix + ".FAILED.json"
    tmp_path = csv_path + ".tmp"

    src_hash = hashlib.sha256()
    source_bytes = 0
    source_rows_total = 0
    legal_rows = 0
    sentinel_count = 0
    sentinel_records = []
    bm_true = bm_false = 0
    tie_timestamp_count = 0
    tie_run_active = False

    src_base = src_quote = 0
    src_buy_base = src_sell_base = src_buy_quote = src_sell_quote = 0

    first_ts = last_ts = None
    prev_ts = None
    prev_id = None

    out_base = out_quote = out_buy_base = out_sell_base = 0
    out_buy_quote = out_sell_quote = 0
    out_count_sum = 0
    ambiguous_open = ambiguous_close = 0
    minutes = 0
    first_bucket = last_bucket = None
    missing_total = 0
    missing_intervals = []

    bucket = None
    run = None
    completed_run = None  # the most recently finished ts-run (close candidate)

    out_dir = os.path.dirname(os.path.abspath(csv_path))
    os.makedirs(out_dir, exist_ok=True)

    def flush(bkt, close_run):
        nonlocal minutes, out_base, out_quote, out_count_sum
        nonlocal out_buy_base, out_sell_base, out_buy_quote, out_sell_quote
        nonlocal ambiguous_open, ambiguous_close
        open_run = bkt.open_run
        open_ambiguous = 1 if len(open_run.prices) > 1 else 0
        close_ambiguous = 1 if len(close_run.prices) > 1 else 0
        ambiguous_open += open_ambiguous
        ambiguous_close += close_ambiguous
        minutes += 1
        out_base += bkt.base
        out_quote += bkt.quote
        out_count_sum += bkt.count
        out_buy_base += bkt.buy_base
        out_sell_base += bkt.sell_base
        out_buy_quote += bkt.buy_quote
        out_sell_quote += bkt.sell_quote
        row = [
            iso_minute(bkt.idx), iso_minute(bkt.idx + 1),
            fmt_fixed(open_run.first_price, PRICE_SCALE),
            fmt_fixed(bkt.high, PRICE_SCALE),
            fmt_fixed(bkt.low, PRICE_SCALE),
            fmt_fixed(close_run.last_price, PRICE_SCALE),
            fmt_fixed(bkt.base, BASE_SCALE), fmt_fixed(bkt.quote, QUOTE_SCALE),
            str(bkt.count),
            fmt_fixed(bkt.buy_base, BASE_SCALE), fmt_fixed(bkt.sell_base, BASE_SCALE),
            fmt_fixed(bkt.buy_quote, QUOTE_SCALE), fmt_fixed(bkt.sell_quote, QUOTE_SCALE),
            fmt_fixed(bkt.buy_base - bkt.sell_base, BASE_SCALE),
            fmt_fixed(bkt.buy_quote - bkt.sell_quote, QUOTE_SCALE),
            str(bkt.first_id), str(bkt.last_id), str(bkt.first_ts), str(bkt.last_ts),
            str(open_ambiguous), str(close_ambiguous),
            str(len(open_run.prices)), str(len(close_run.prices)),
        ]
        fh_out.write(",".join(row) + "\n")

    with open(source_path, "rb") as fh_in, open(tmp_path, "w", encoding="utf-8", newline="\n") as fh_out:
        fh_out.write(",".join(CSV_COLUMNS) + "\n")
        for raw in fh_in:
            source_rows_total += 1
            src_hash.update(raw)
            source_bytes += len(raw)
            line = raw.rstrip(b"\r\n")
            fields = line.split(b",")
            if len(fields) != 8:
                raise ConverterError(source_rows_total, "FIELD_COUNT", "got=%d" % len(fields))
            row_no = source_rows_total
            agg_id = parse_int(fields[0], row_no, "AGG_ID_INVALID", nonneg=True)
            price_i = parse_fixed(fields[1], PRICE_SCALE, row_no, "PRICE_INVALID")
            qty_i = parse_fixed(fields[2], BASE_SCALE, row_no, "QTY_INVALID")
            first_id = parse_int(fields[3], row_no, "TRADE_ID_INVALID")
            last_id = parse_int(fields[4], row_no, "TRADE_ID_INVALID")
            ts = parse_int(fields[5], row_no, "TIMESTAMP_INVALID", nonneg=True)
            bmm = parse_bool(fields[6], row_no)
            bmt = parse_bool(fields[7], row_no)

            if price_i == 0 and qty_i == 0 and first_id == -1 and last_id == -1:
                # Official invalid sentinel (changelog 2022-04-12): count + record.
                sentinel_count += 1
                if len(sentinel_records) < MAX_SENTINEL_RECORDS:
                    sentinel_records.append({"row": row_no, "agg_trade_id": agg_id,
                                             "transact_time_us": ts})
                continue

            if bmt:
                bm_true += 1
            else:
                bm_false += 1

            # ---- legal row validation (FAIL CLOSED) ----
            if price_i <= 0:
                raise ConverterError(row_no, "PRICE_INVALID", "non-positive price")
            if qty_i <= 0:
                raise ConverterError(row_no, "QTY_INVALID", "non-positive quantity")
            if first_id < 0 or last_id < 0:
                raise ConverterError(row_no, "IDENTIFIER_INVALID", "negative trade id on legal row")
            if first_id > last_id:
                raise ConverterError(row_no, "IDENTIFIER_INVALID", "first_trade_id>last_trade_id")
            if prev_ts is not None and ts < prev_ts:
                raise ConverterError(row_no, "TIMESTAMP_DECREASING",
                                     "ts=%d prev=%d" % (ts, prev_ts))
            if prev_id is not None and agg_id <= prev_id:
                raise ConverterError(row_no,
                                     "AGG_ID_DUPLICATE" if agg_id == prev_id else "AGG_ID_DECREASING",
                                     "agg=%d prev=%d" % (agg_id, prev_id))

            if prev_ts is not None and ts == prev_ts:
                if not tie_run_active:
                    tie_timestamp_count += 1
                    tie_run_active = True
            else:
                tie_run_active = False

            legal_rows += 1
            q_quote = price_i * qty_i
            src_base += qty_i
            src_quote += q_quote
            buy = not bmm
            if buy:
                src_buy_base += qty_i
                src_buy_quote += q_quote
            else:
                src_sell_base += qty_i
                src_sell_quote += q_quote
            if first_ts is None:
                first_ts = ts
            last_ts = ts

            bkt_idx = ts // MINUTE_US
            if run is not None and run.ts == ts:
                run.add(price_i)
            else:
                completed_run = run  # previous ts-run just finished
                run = _Run(ts, price_i)

            if bucket is None:
                bucket = _Bucket(bkt_idx, agg_id, ts, price_i, qty_i, q_quote, buy, run)
                first_bucket = bkt_idx
                last_bucket = bkt_idx
            elif bkt_idx == bucket.idx:
                bucket.add(agg_id, ts, price_i, qty_i, q_quote, buy)
            else:
                # bucket switch implies ts changed => completed_run is the old
                # bucket's final run (its close-candidate).
                flush(bucket, close_run=completed_run)
                if bkt_idx > bucket.idx + 1:
                    gap_a, gap_b = bucket.idx + 1, bkt_idx - 1
                    missing_total += gap_b - gap_a + 1
                    if len(missing_intervals) < MAX_GAP_INTERVALS:
                        missing_intervals.append([iso_minute(gap_a), iso_minute(gap_b + 1)])
                bucket = _Bucket(bkt_idx, agg_id, ts, price_i, qty_i, q_quote, buy, run)
                last_bucket = bkt_idx
            prev_ts = ts
            prev_id = agg_id
        # end for
        if bucket is not None:
            flush(bucket, close_run=run)  # run holds the file's final row
            last_bucket = bucket.idx

    os.replace(tmp_path, csv_path)

    # ---- reconciliation (exact integer) ----
    recon = {
        "source_base_sum": fmt_fixed(src_base, BASE_SCALE),
        "output_base_sum": fmt_fixed(out_base, BASE_SCALE),
        "source_quote_sum": fmt_fixed(src_quote, QUOTE_SCALE),
        "output_quote_sum": fmt_fixed(out_quote, QUOTE_SCALE),
    }
    recon["exact_match_base"] = (src_base == out_base)
    recon["exact_match_quote"] = (src_quote == out_quote)
    recon["buy_plus_sell_base_matches_total"] = (src_buy_base + src_sell_base == src_base) and \
                                                (out_buy_base + out_sell_base == out_base)
    recon["buy_plus_sell_quote_matches_total"] = (src_buy_quote + src_sell_quote == src_quote) and \
                                                 (out_buy_quote + out_sell_quote == out_quote)
    recon["sum_agg_trade_count_matches_legal_source_rows"] = (out_count_sum == legal_rows)
    recon_ok = all([recon["exact_match_base"], recon["exact_match_quote"],
                    recon["buy_plus_sell_base_matches_total"],
                    recon["buy_plus_sell_quote_matches_total"],
                    recon["sum_agg_trade_count_matches_legal_source_rows"]])
    if not recon_ok:
        _write_failed(failed_path, source_path, row_no="n/a", error_class="RECONCILIATION_FAILED",
                      detail=json.dumps(recon))
        raise ConverterError("n/a", "RECONCILIATION_FAILED", "")

    out_hash = hashlib.sha256()
    with open(csv_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            out_hash.update(chunk)

    covered = 0
    if first_bucket is not None:
        covered = last_bucket - first_bucket + 1

    sidecar = {
        "converter_name": CONVERTER_NAME,
        "converter_version": TOOL_VERSION,
        "converter_sha256": tool_self_sha256(),
        "generated_at_utc": utc_now_iso(),
        "source_path": os.path.abspath(source_path),
        "source_bytes": source_bytes,
        "source_sha256": src_hash.hexdigest(),
        "source_contract": SOURCE_CONTRACT,
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "documented_source_references": DOCUMENTED_SOURCE_REFERENCES,
        "timestamp_unit": TIMESTAMP_UNIT,
        "source_rows_total": source_rows_total,
        "legal_rows_consumed": legal_rows,
        "official_invalid_sentinel_count": sentinel_count,
        "official_invalid_sentinel_records": sentinel_records,
        "sentinel_rule": SENTINEL_RULE,
        "rejected_corrupt_rows": 0,
        "failure_policy": "FAIL_CLOSED (row number + error class; no silent skip/repair/sort)",
        "first_source_time_us": first_ts,
        "last_source_time_us": last_ts,
        "first_source_time_utc": iso_us(first_ts) if first_ts is not None else None,
        "last_source_time_utc": iso_us(last_ts) if last_ts is not None else None,
        "output_minute_count": minutes,
        "covered_calendar_minute_count": covered,
        "missing_minute_count": missing_total,
        "missing_minute_intervals": missing_intervals,
        "missing_intervals_truncated": missing_total > 0 and len(missing_intervals) >= MAX_GAP_INTERVALS,
        "first_output_minute": iso_minute(first_bucket) if first_bucket is not None else None,
        "last_output_minute": iso_minute(last_bucket) if last_bucket is not None else None,
        "is_best_match_true_count": bm_true,
        "is_best_match_false_count": bm_false,
        "is_best_match_invalid_count": 0,
        "is_best_match_usage": "DIAGNOSTIC_COUNTS_ONLY_NOT_A_FEATURE",
        "tie_timestamp_count": tie_timestamp_count,
        "ambiguous_open_minute_count": ambiguous_open,
        "ambiguous_close_minute_count": ambiguous_close,
        "TIE_ORDER_CONTRACT": TIE_ORDER_CONTRACT,
        "tie_order_evidence": TIE_ORDER_EVIDENCE,
        "tie_order_policy": TIE_ORDER_POLICY,
        "minute_interval_contract": MINUTE_INTERVAL_CONTRACT,
        "bar_close_availability": BAR_CLOSE_AVAILABILITY,
        "numeric_representation": NUMERIC_REPRESENTATION,
        "executed_flow_semantics": EXECUTED_FLOW_SEMANTICS,
        "reconciliation": recon,
        "output_csv": os.path.abspath(csv_path),
        "output_csv_sha256": out_hash.hexdigest(),
        "historical_provenance_statement": HISTORICAL_PROVENANCE_STATEMENT,
    }
    with open(sidecar_path, "w", encoding="utf-8") as sf:
        json.dump(sidecar, sf, ensure_ascii=False, indent=1)
        sf.write("\n")
    if os.path.exists(failed_path):
        os.remove(failed_path)
    return sidecar


def _write_failed(path, source_path, row_no, error_class, detail):
    try:
        payload = {
            "converter_name": CONVERTER_NAME,
            "converter_version": TOOL_VERSION,
            "converter_sha256": tool_self_sha256(),
            "generated_at_utc": utc_now_iso(),
            "source_path": os.path.abspath(source_path),
            "status": "FAILED_FAIL_CLOSED",
            "row": row_no,
            "error_class": error_class,
            "detail": detail,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    except OSError:
        pass


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = argv[1:]
    source = None
    out_prefix = None
    i = 0
    while i < len(args):
        if args[i] == "--out":
            if i + 1 >= len(args):
                print("خطأ: --out يحتاج مساراً", file=sys.stderr)
                return 2
            out_prefix = args[i + 1]
            if out_prefix.lower().endswith(".csv"):
                out_prefix = out_prefix[:-4]
            i += 2
            continue
        if source is None:
            source = args[i]
        i += 1
    if source is None:
        print("خطأ: الاستخدام: aggtrades_to_minute_facts.py <source.csv> [--out prefix]",
              file=sys.stderr)
        return 2
    if not os.path.isfile(source):
        print("خطأ: لم يتم العثور على الملف: %s" % source, file=sys.stderr)
        return 2
    if out_prefix is None:
        stem = os.path.basename(source)
        if stem.lower().endswith(".csv"):
            stem = stem[:-4]
        out_prefix = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs",
                                  "minute_facts_%s" % stem)
    try:
        sidecar = convert(source, out_prefix)
    except ConverterError as exc:
        if exc.error_class != "RECONCILIATION_FAILED":
            _write_failed(out_prefix + ".FAILED.json", source, exc.row_no,
                          exc.error_class, exc.detail)
        tmp = out_prefix + ".csv.tmp"
        if os.path.exists(tmp):
            os.remove(tmp)
        print("فشل التحويل — تم الإيقاف (fail-closed)", file=sys.stderr)
        print("FAILED row=%s class=%s %s" % (exc.row_no, exc.error_class, exc.detail),
              file=sys.stderr)
        return 3
    except OSError as exc:
        print("خطأ: نظام الملفات: %s" % exc, file=sys.stderr)
        return 2
    print("تم التحويل بنجاح")
    print("جدول الدقائق: %s" % sidecar["output_csv"])
    print("ملف Sidecar : %s" % (out_prefix + ".sidecar.json"))
    print("الدقائق المخرجة: %d | الصفوف القانونية: %d | sentinel: %d"
          % (sidecar["output_minute_count"], sidecar["legal_rows_consumed"],
             sidecar["official_invalid_sentinel_count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

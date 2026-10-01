# -*- coding: utf-8 -*-
"""Adversarial local tests for tools/aggtrades_to_minute_facts.py (35 test points).

Fixtures are MANUAL miniature rows in the documented 8-column Binance Spot
aggTrades format. The owner's real file is NEVER used here.

Run:  python -m pytest tools/tests_local/ -q
Mutation proofs: set AGG_CONVERTER_PATH to a mutated copy before running.
"""

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONV = os.environ.get("AGG_CONVERTER_PATH", os.path.join(REPO, "tools", "aggtrades_to_minute_facts.py"))
MIN = 60_000_000
T0 = 1700000000000000  # 2023-11-14T22:13:20Z, µs

FORBIDDEN = ["buying pressure", "order-book pressure", "institutional",
             "whale", "market-wide order flow", "order-book imbalance",
             "buying_pressure", "order_book_imbalance"]


def row(agg_id, price, qty, first, last, ts, buyer_maker="False", best="True"):
    return "%d,%s,%s,%d,%d,%d,%s,%s" % (agg_id, price, qty, first, last, ts, buyer_maker, best)


def write_src(tmp_path, rows, name="src.csv"):
    p = str(tmp_path / name)
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(r + "\n")
    return p


def run_conv(src, out_prefix):
    r = subprocess.run([sys.executable, CONV, src, "--out", out_prefix],
                       capture_output=True, text=True)
    return r


def load_sidecar(out_prefix):
    with open(out_prefix + ".sidecar.json", encoding="utf-8") as fh:
        return json.load(fh)


def load_csv_rows(out_prefix):
    with open(out_prefix + ".csv", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    header = lines[0].split(",")
    return header, [dict(zip(header, ln.split(","))) for ln in lines[1:]]


def convert_ok(tmp_path, rows, name="src"):
    src = write_src(tmp_path, rows, name + ".csv")
    out = str(tmp_path / (name + "_out"))
    r = run_conv(src, out)
    assert r.returncode == 0, r.stderr
    return out, load_sidecar(out), load_csv_rows(out)


def expect_fail(tmp_path, rows, cls, name):
    src = write_src(tmp_path, rows, name + ".csv")
    out = str(tmp_path / (name + "_out"))
    r = run_conv(src, out)
    assert r.returncode == 3, (r.returncode, r.stdout, r.stderr)
    assert "FAILED" in r.stderr or "فشل" in r.stderr
    with open(out + ".FAILED.json", encoding="utf-8") as fh:
        fail = json.load(fh)
    assert fail["error_class"] == cls, fail
    assert fail["row"] == len(rows), fail  # first bad row number == rows listed so far
    assert not os.path.exists(out + ".csv") or open(out + ".csv").read().count("\n") <= len(rows)
    # no successful sidecar
    assert not os.path.exists(out + ".sidecar.json")
    return fail


# ---------------------------------------------------------------- 1..4 basic
def test_01_buy_row_single(tmp_path):
    out, sc, (hdr, rows) = convert_ok(tmp_path, [row(10, "100.50000000", "0.00100000", 1, 1, T0, "False")])
    r = rows[0]
    assert r["open"] == r["high"] == r["low"] == r["close"] == "100.50000000"
    assert r["base_volume"] == "0.00100000"
    assert r["quote_volume"] == "0.1005000000000000"
    assert r["buy_initiated_base_volume"] == "0.00100000"
    assert r["sell_initiated_base_volume"] == "0.00000000"
    assert r["buy_initiated_quote_volume"] == "0.1005000000000000"
    assert r["executed_base_delta"] == "0.00100000"
    assert r["executed_quote_delta"] == "0.1005000000000000"
    assert r["agg_trade_count"] == "1"


def test_02_sell_row_single(tmp_path):
    out, sc, (hdr, rows) = convert_ok(tmp_path, [row(11, "99.25000000", "0.00200000", 2, 2, T0, "True")])
    r = rows[0]
    assert r["sell_initiated_base_volume"] == "0.00200000"
    assert r["buy_initiated_base_volume"] == "0.00000000"
    assert r["sell_initiated_quote_volume"] == "0.1985000000000000"
    assert r["executed_base_delta"] == "-0.00200000"
    assert r["executed_quote_delta"] == "-0.1985000000000000"


def test_03_multiple_trades_same_minute(tmp_path):
    rows = [row(20, "100.00000000", "0.01000000", 1, 1, T0, "False"),
            row(21, "101.00000000", "0.02000000", 2, 2, T0 + 1_000_000, "True"),
            row(22, "102.00000000", "0.03000000", 3, 3, T0 + 2_000_000, "False")]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    m = r[0]
    assert m["agg_trade_count"] == "3"
    assert m["base_volume"] == "0.06000000"
    # exact: 1.0 + 2.02 + 3.06 = 6.08
    assert m["quote_volume"] == "6.0800000000000000"
    assert m["buy_initiated_base_volume"] == "0.04000000"
    assert m["sell_initiated_base_volume"] == "0.02000000"


def test_04_ohlc_manual(tmp_path):
    # open=100, high=103, low=99, close=101 given explicit ordering
    rows = [row(30, "100.00000000", "0.00100000", 1, 1, T0, "False"),
            row(31, "103.00000000", "0.00100000", 2, 2, T0 + 1, "True"),
            row(32, "99.00000000", "0.00100000", 3, 3, T0 + 2, "False"),
            row(33, "101.00000000", "0.00100000", 4, 4, T0 + 3, "True")]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    m = r[0]
    assert (m["open"], m["high"], m["low"], m["close"]) == \
           ("100.00000000", "103.00000000", "99.00000000", "101.00000000")


# ------------------------------------------------------------- 5..8 minutes
def test_05_minute_boundary_membership(tmp_path):
    # [start,end): 59.999999 stays in minute k; +60.000000 jumps to k+1
    t_last = T0 + (MIN - 20_000_001)   # ends .999999 of minute 0
    t_next = T0 + (MIN - 20_000_000)   # exactly minute 1 start
    rows = [row(40, "10.00000000", "0.10000000", 1, 1, t_last, "False"),
            row(41, "11.00000000", "0.10000000", 2, 2, t_next, "True")]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    assert len(r) == 2
    assert r[0]["minute_start_utc"] == "2023-11-14T22:13:00"
    assert r[0]["minute_end_utc"] == "2023-11-14T22:14:00"
    assert r[1]["minute_start_utc"] == "2023-11-14T22:14:00"
    assert r[1]["minute_end_utc"] == "2023-11-14T22:15:00"
    assert r[0]["close"] == "10.00000000" and r[1]["open"] == "11.00000000"


def test_06_tie_same_ts_same_price_unambiguous(tmp_path):
    rows = [row(50 + i, "50.00000000", "0.00100000", i + 1, i + 1, T0, "False") for i in range(3)]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    m = r[0]
    assert m["open_ambiguous"] == "0" and m["close_ambiguous"] == "0"
    assert m["open_tie_distinct_prices"] == "1" and m["close_tie_distinct_prices"] == "1"
    assert m["open"] == m["close"] == "50.00000000"


def test_07_tie_same_ts_diff_prices_ambiguous(tmp_path):
    # same µs, distinct prices; deterministic pick = (ts, agg_trade_id) order
    rows = [row(60, "52.00000000", "0.00100000", 1, 1, T0, "False"),
            row(61, "51.00000000", "0.00100000", 2, 2, T0, "True"),
            row(62, "53.00000000", "0.00100000", 3, 3, T0, "False")]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    m = r[0]
    assert m["open"] == "52.00000000"   # min id
    assert m["close"] == "53.00000000"  # max id
    assert m["open_ambiguous"] == "1" and m["close_ambiguous"] == "1"
    assert m["open_tie_distinct_prices"] == "3" and m["close_tie_distinct_prices"] == "3"
    assert m["high"] == "53.00000000" and m["low"] == "51.00000000"
    assert sc["tie_timestamp_count"] == 1
    assert sc["ambiguous_open_minute_count"] == 1
    assert sc["ambiguous_close_minute_count"] == 1


def test_08_tie_order_contract_recorded(tmp_path):
    out, sc, _ = convert_ok(tmp_path, [row(70, "1.00000000", "1.00000000", 1, 1, T0, "False")])
    assert sc["TIE_ORDER_CONTRACT"] == "NOT_PROVEN"
    assert "AMBIGUITY_METADATA" in sc["tie_order_policy"]
    assert len(sc["tie_order_evidence"]) > 50


# ------------------------------------------------------------- 9..16 corruption
def test_09_sentinel_counted_excluded_recorded(tmp_path):
    rows = [row(80, "100.00000000", "0.00100000", 1, 1, T0, "False"),
            row(81, "0.00000000", "0.00000000", -1, -1, T0 + 5, "True"),
            row(82, "100.00000000", "0.00200000", 2, 2, T0 + 10, "True")]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    assert sc["official_invalid_sentinel_count"] == 1
    assert sc["official_invalid_sentinel_records"][0]["agg_trade_id"] == 81
    assert r[0]["agg_trade_count"] == "2"          # sentinel excluded from aggregation
    assert r[0]["base_volume"] == "0.00300000"     # not silently dropped either
    assert sc["legal_rows_consumed"] == 2
    assert sc["source_rows_total"] == 3


def test_10_field_count_corrupt_failclosed(tmp_path):
    expect_fail(tmp_path, [row(90, "1.0", "1.0", 1, 1, T0),
                           "91,1.0,1.0,1,1,1700000000000001,True"],  # 7 fields
                "FIELD_COUNT", "f10")
    expect_fail(tmp_path, ["90,1.0,1.0,1,1,1700000000000000,True,True,EXTRA"], "FIELD_COUNT", "f10b")


def test_11_price_corrupt_failclosed(tmp_path):
    good = row(100, "1.00000000", "1.00000000", 1, 1, T0)
    for bad_price, tag in [("abc", "a"), ("-1.0", "b"), ("1e5", "c"),
                           ("0.123456789", "d"), (".5", "e"), ("0", "f"), ("+1.0", "g")]:
        rows = [good, row(101, bad_price, "1.00000000", 2, 2, T0 + 1)]
        f = expect_fail(tmp_path, rows, "PRICE_INVALID", "p11" + tag)
        assert f["row"] == 2


def test_12_quantity_corrupt_failclosed(tmp_path):
    good = row(110, "1.00000000", "1.00000000", 1, 1, T0)
    for bad_qty, tag in [("abc", "a"), ("-0.1", "b"), ("1e-3", "c"), ("0.123456789", "d")]:
        rows = [good, row(111, "1.00000000", bad_qty, 2, 2, T0 + 1)]
        f = expect_fail(tmp_path, rows, "QTY_INVALID", "q12" + tag)
        assert f["row"] == 2


def test_13_timestamp_corrupt_failclosed(tmp_path):
    good = row(120, "1.00000000", "1.00000000", 1, 1, T0)
    rows = [good, "121,1.00000000,1.00000000,2,2,170000000000000.5,False,True"]
    f = expect_fail(tmp_path, rows, "TIMESTAMP_INVALID", "t13a")
    assert f["row"] == 2
    rows = [good, "121,1.00000000,1.00000000,2,2,abc,False,True"]
    expect_fail(tmp_path, rows, "TIMESTAMP_INVALID", "t13b")
    rows = [good, "121,1.00000000,1.00000000,2,2,+5,False,True"]
    expect_fail(tmp_path, rows, "TIMESTAMP_INVALID", "t13c")


def test_14_bool_corrupt_failclosed(tmp_path):
    good = row(130, "1.00000000", "1.00000000", 1, 1, T0)
    for bad in ["yes", "1", "true", "FALSE", ""]:
        rows = [good, "131,1.00000000,1.00000000,2,2,1700000000000001,%s,True" % bad]
        f = expect_fail(tmp_path, rows, "BOOL_INVALID", "b14_" + (bad or "empty"))
        assert f["row"] == 2


def test_15_timestamp_decreasing_failclosed(tmp_path):
    rows = [row(140, "1.00000000", "1.00000000", 1, 1, T0 + 1000),
            row(141, "1.00000000", "1.00000000", 2, 2, T0)]
    f = expect_fail(tmp_path, rows, "TIMESTAMP_DECREASING", "t15")
    assert f["row"] == 2


def test_16_agg_id_duplicate_and_decreasing_failclosed(tmp_path):
    rows = [row(150, "1.00000000", "1.00000000", 1, 1, T0),
            row(150, "1.00000000", "1.00000000", 2, 2, T0 + 1)]
    f = expect_fail(tmp_path, rows, "AGG_ID_DUPLICATE", "i16a")
    assert f["row"] == 2
    rows = [row(160, "1.00000000", "1.00000000", 1, 1, T0),
            row(159, "1.00000000", "1.00000000", 2, 2, T0 + 1)]
    f = expect_fail(tmp_path, rows, "AGG_ID_DECREASING", "i16b")
    rows = [row(170, "1.00000000", "1.00000000", 5, 2, T0)]
    f = expect_fail(tmp_path, rows, "IDENTIFIER_INVALID", "i16c")


# ---------------------------------------------------------- 17..21 contracts
def test_17_empty_minute_gap_missing_intervals(tmp_path):
    rows = [row(180, "1.00000000", "1.00000000", 1, 1, T0, "False"),
            row(181, "1.00000000", "1.00000000", 2, 2, T0 + 3 * MIN, "True")]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    assert sc["output_minute_count"] == 2
    assert sc["covered_calendar_minute_count"] == 4
    assert sc["missing_minute_count"] == 2
    assert sc["missing_minute_intervals"] == [["2023-11-14T22:14:00", "2023-11-14T22:16:00"]]


def test_18_no_synthetic_bar(tmp_path):
    rows = [row(190, "1.00000000", "1.00000000", 1, 1, T0, "False"),
            row(191, "1.00000000", "1.00000000", 2, 2, T0 + 3 * MIN, "True")]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    starts = [m["minute_start_utc"] for m in r]
    assert starts == ["2023-11-14T22:13:00", "2023-11-14T22:16:00"]  # gap minutes absent
    for m in r:
        assert m["agg_trade_count"] != "0"


def test_19_buy_sell_base_reconciliation(tmp_path):
    rows = [row(200 + i, "10.00000000", "0.00100000", i + 1, i + 1, T0 + i,
                "False" if i % 2 == 0 else "True") for i in range(4)]
    out, sc, _ = convert_ok(tmp_path, rows)
    rc = sc["reconciliation"]
    assert rc["exact_match_base"] and rc["buy_plus_sell_base_matches_total"]
    assert rc["source_base_sum"] == rc["output_base_sum"] == "0.00400000"


def test_20_buy_sell_quote_reconciliation(tmp_path):
    rows = [row(210 + i, "3.00000000", "0.00700000", i + 1, i + 1, T0 + i,
                "False" if i % 2 == 0 else "True") for i in range(3)]
    out, sc, _ = convert_ok(tmp_path, rows)
    rc = sc["reconciliation"]
    assert rc["exact_match_quote"] and rc["buy_plus_sell_quote_matches_total"]
    assert rc["source_quote_sum"] == rc["output_quote_sum"] == "0.0630000000000000"


def test_21_fixedpoint_exact_no_float(tmp_path):
    # products > 2**53 in 16-scaled units: any float path deviates at 16 decimals
    p, q = "82850.00000001", "57.97803001"
    pi = int(p.replace(".", ""))          # 8285000000001 scale 8
    qi = int(q.replace(".", ""))          # 5797803001   scale 8
    exact = pi * qi                       # scale 16
    expect_quote = "%d.%016d" % (exact // 10 ** 16, exact % 10 ** 16)
    rows = [row(220, p, q, 1, 1, T0, "False")]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    assert r[0]["quote_volume"] == expect_quote
    assert sc["reconciliation"]["source_quote_sum"] == expect_quote


# ---------------------------------------------------------- 22..28 sidecar
def test_22_is_best_match_counts_not_feature(tmp_path):
    rows = [row(230, "1.00000000", "1.00000000", 1, 1, T0, "False", "True"),
            row(231, "1.00000000", "1.00000000", 2, 2, T0 + 1, "True", "False")]
    out, sc, (hdr, _) = convert_ok(tmp_path, rows)
    assert "is_best_match" not in hdr
    assert sc["is_best_match_true_count"] == 1 and sc["is_best_match_false_count"] == 1
    assert "NOT_A_FEATURE" in sc["is_best_match_usage"]


def test_23_path_with_spaces(tmp_path):
    d = tmp_path / "dir with spaces" / "sub dir"
    d.mkdir(parents=True)
    src = write_src(d, [row(240, "1.00000000", "1.00000000", 1, 1, T0, "False")])
    out = str(d / "my out")
    r = run_conv(src, out)
    assert r.returncode == 0, r.stderr
    assert os.path.exists(out + ".csv") and os.path.exists(out + ".sidecar.json")


def test_24_empty_file_ok(tmp_path):
    src = write_src(tmp_path, [], "empty.csv")
    out = str(tmp_path / "empty_out")
    r = run_conv(src, out)
    assert r.returncode == 0, r.stderr
    sc = load_sidecar(out)
    assert sc["output_minute_count"] == 0 and sc["source_rows_total"] == 0
    hdr, rows = load_csv_rows(out)
    assert rows == [] and hdr[0] == "minute_start_utc"


def test_25_single_row_file(tmp_path):
    out, sc, (hdr, r) = convert_ok(tmp_path, [row(250, "7.50000000", "0.25000000", 9, 9, T0, "True")])
    assert len(r) == 1
    m = r[0]
    assert (m["open"], m["high"], m["low"], m["close"]) == ("7.50000000",) * 4
    assert m["first_agg_trade_id"] == m["last_agg_trade_id"] == "250"
    assert m["first_transact_time_us"] == m["last_transact_time_us"] == str(T0)


def test_26_first_last_minute_fields(tmp_path):
    rows = [row(260, "1.00000000", "1.00000000", 1, 1, T0),
            row(261, "1.00000000", "1.00000000", 2, 2, T0 + 2 * MIN)]
    out, sc, (hdr, r) = convert_ok(tmp_path, rows)
    assert sc["first_output_minute"] == "2023-11-14T22:13:00"
    assert sc["last_output_minute"] == "2023-11-14T22:15:00"
    assert sc["first_source_time_us"] == T0
    assert sc["last_source_time_us"] == T0 + 2 * MIN


def test_27_source_and_output_sha256(tmp_path):
    src = write_src(tmp_path, [row(270, "1.00000000", "1.00000000", 1, 1, T0)])
    out = str(tmp_path / "sha_out")
    r = run_conv(src, out)
    assert r.returncode == 0
    sc = load_sidecar(out)
    src_sha = hashlib.sha256(open(src, "rb").read()).hexdigest()
    out_sha = hashlib.sha256(open(out + ".csv", "rb").read()).hexdigest()
    assert sc["source_sha256"] == src_sha
    assert sc["output_csv_sha256"] == out_sha


def test_28_sidecar_required_keys(tmp_path):
    out, sc, _ = convert_ok(tmp_path, [row(280, "1.00000000", "1.00000000", 1, 1, T0)])
    required = ["converter_name", "converter_version", "converter_sha256",
                "source_path", "source_bytes", "source_sha256", "source_contract",
                "timestamp_unit", "source_rows_total", "legal_rows_consumed",
                "official_invalid_sentinel_count", "rejected_corrupt_rows",
                "first_source_time_utc", "last_source_time_utc",
                "output_minute_count", "covered_calendar_minute_count",
                "missing_minute_count", "missing_minute_intervals",
                "first_output_minute", "last_output_minute",
                "is_best_match_true_count", "is_best_match_false_count",
                "is_best_match_invalid_count", "TIE_ORDER_CONTRACT",
                "numeric_representation", "output_csv_sha256",
                "reconciliation", "generated_at_utc",
                "historical_provenance_statement", "bar_close_availability",
                "minute_interval_contract", "executed_flow_semantics"]
    for k in required:
        assert k in sc, k
    assert sc["source_contract"] == "BINANCE_SPOT_PUBLIC_DATA_AGGTRADES"
    assert sc["timestamp_unit"] == "MICROSECONDS"
    assert sc["bar_close_availability"] == "NOT_CLAIMED_BY_CONVERTER"


# ---------------------------------------------------------- 29..32 systems
def test_29_bounded_memory_rlimit(tmp_path):
    rows = [row(1000000 + i, "100.00000000", "0.00100000", i + 1, i + 1,
                T0 + (i // 3) * 1_000 + (i % 3), "False" if i % 2 == 0 else "True")
            for i in range(20000)]
    src = write_src(tmp_path, rows, "mem.csv")
    out = str(tmp_path / "mem_out")

    def limit():
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))

    r = subprocess.run([sys.executable, CONV, src, "--out", out],
                       capture_output=True, text=True, preexec_fn=limit)
    assert r.returncode == 0, r.stderr[-500:]
    sc = load_sidecar(out)
    assert sc["output_minute_count"] > 0


def test_30_deterministic_output(tmp_path):
    rows = [row(300 + i, ("10.%08d" % (i * 7 % 97 + 1)), "0.00100000", i + 1, i + 1,
                T0 + i * 1_000_000, "False" if i % 2 == 0 else "True") for i in range(10)]
    src = write_src(tmp_path, rows, "det.csv")
    out1, out2 = str(tmp_path / "d1"), str(tmp_path / "d2")
    assert run_conv(src, out1).returncode == 0
    assert run_conv(src, out2).returncode == 0
    assert open(out1 + ".csv", "rb").read() == open(out2 + ".csv", "rb").read()
    s1, s2 = load_sidecar(out1), load_sidecar(out2)
    s1.pop("generated_at_utc"), s2.pop("generated_at_utc")
    s1.pop("output_csv"), s2.pop("output_csv")
    assert s1 == s2


def test_31_truncation_prefix_consistency(tmp_path):
    rows_full = [row(310 + i, "5.00000000", "0.01000000", i + 1, i + 1,
                     T0 + i * MIN, "False" if i % 2 == 0 else "True") for i in range(5)]
    rows_cut = rows_full[:3]  # cut at minute boundary
    out_f, _, (_, r_full) = convert_ok(tmp_path, rows_full, "full")
    out_c, _, (_, r_cut) = convert_ok(tmp_path, rows_cut, "cut")
    assert len(r_full) == 5 and len(r_cut) == 3
    for a, b in zip(r_full, r_cut):
        assert a == b


def test_32_no_future_leakage(tmp_path):
    earlier = [row(320 + i, "2.00000000", "0.00200000", i + 1, i + 1,
                   T0 + i * MIN, "False") for i in range(3)]
    later = earlier + [row(330 + i, "2.00000000", "0.00200000", 10 + i, 10 + i,
                           T0 + (3 + i) * MIN, "True") for i in range(3)]
    out_a, _, (_, ra) = convert_ok(tmp_path, earlier, "early")
    out_b, _, (_, rb) = convert_ok(tmp_path, later, "later")
    for a, b in zip(ra, rb[:len(ra)]):
        assert a == b  # earlier minutes never depend on later rows


# ------------------------------------------------------- 33..35 static guards
def test_33_semantic_guard_no_forbidden_words(tmp_path):
    out, sc, (hdr, rows) = convert_ok(tmp_path, [row(340, "1.00000000", "1.00000000", 1, 1, T0)])
    blob = (",".join(hdr) + "\n" + json.dumps(sc, ensure_ascii=False)).lower()
    for term in FORBIDDEN:
        assert term.lower() not in blob, term
    assert "executed_flow_semantics" in sc
    assert "executed" in sc["executed_flow_semantics"].lower()


def test_34_no_project_engine_imports():
    src = open(CONV, encoding="utf-8").read()
    tree = ast.parse(src)
    allowed = {"hashlib", "json", "os", "re", "sys", "datetime", "argparse",
               "decimal", "typing", "pathlib", "math", "csv", "io", "time"}
    banned = ("trading_system", "volatility_engine", "session_engine", "swing_engine",
              "orderflow_engine", "order_flow_engine", "liquidity_engine",
              "order_block_engine", "fvg_engine", "hh_hl_engine", "evidence_engine",
              "hypotheses_engine", "calibration_engine", "layer31_engine", "layer32_engine")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] in allowed, a.name
                assert not any(b in a.name for b in banned), a.name
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in allowed, node.module
            assert not any(b in (node.module or "") for b in banned), node.module
        elif isinstance(node, ast.Name):
            assert not any(b in node.id for b in banned), node.id
        elif isinstance(node, ast.Attribute):
            assert not any(b in node.attr for b in banned), node.attr


def test_35_converter_self_hash_and_version(tmp_path):
    out, sc, _ = convert_ok(tmp_path, [row(350, "1.00000000", "1.00000000", 1, 1, T0)])
    self_sha = hashlib.sha256(open(CONV, "rb").read()).hexdigest()
    assert sc["converter_sha256"] == self_sha
    assert sc["converter_name"] == "aggtrades_to_minute_facts"
    assert sc["converter_version"] == "1.0.0"

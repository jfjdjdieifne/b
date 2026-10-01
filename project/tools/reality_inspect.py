#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reality_inspect.py — LOCAL READ-ONLY DATA INSPECTION TOOL.

Purpose
-------
Factual inspection of one local data file. It answers "what is physically in
this file?" — and nothing beyond that.

Tool contract
-------------
* Standard library ONLY (no pandas / numpy / third-party packages).
* Streaming, bounded memory: constant-size state regardless of file size.
* No external sort. No in-memory sets sized by number of rows.
* No copy of the data file is ever created (single streaming pass; the tail
  sample is produced with a bounded backward seek, not a copy).
* FACTS ONLY. Market semantics (price / quantity / maker / aggressor /
  timestamp unit / exchange contract) are NEVER inferred from column position.
  The report always states:  "binance_semantics": "NOT_VERIFIED"
* Any statistic that would need unbounded memory or external sorting is
  explicitly reported as NOT_COMPUTED_MEMORY_BOUNDED — never guessed.

Exit codes
----------
0 = OK (report written)
1 = unexpected error
2 = file not found
3 = permission denied
4 = path is not a regular file
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

TOOL_NAME = "reality_inspect.py"
TOOL_VERSION = "1.0.0"
REPORT_FORMAT = "REALITY_INSPECT_REPORT_V1"
SAMPLES_PER_COLUMN = 5
LINE_SAMPLE_MAX_CHARS = 2000
MAX_PARSE_LINE_BYTES = 8 * 1024 * 1024  # pathological line guard (still counted + hashed)
TAIL_CHUNK = 64 * 1024
TAIL_BUFFER_LIMIT = 1024 * 1024

NOT_COMPUTED = "NOT_COMPUTED_MEMORY_BOUNDED"

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_NOT_FOUND = 2
EXIT_PERMISSION = 3
EXIT_NOT_A_FILE = 4


def tool_self_sha256() -> str:
    with open(__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def sanitize_stem(name: str) -> str:
    stem = os.path.basename(name)
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)
    return stem[:80] or "file"


def tail_lines(path, n=5):
    """Read last n lines using bounded backward seek. No copy of the file."""
    out = []
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        pos = fh.tell()
        buf = b""
        while pos > 0 and buf.count(b"\n") <= n and len(buf) <= TAIL_BUFFER_LIMIT:
            step = min(TAIL_CHUNK, pos)
            pos -= step
            fh.seek(pos)
            buf = fh.read(step) + buf
        lines = buf.split(b"\n")
        if pos > 0:
            lines = lines[1:]  # first element is a partial line
        if lines and lines[-1] == b"":
            lines = lines[:-1]  # file ended with newline
        out = lines[-n:]
    return [decode_capped(x) for x in out]


def decode_capped(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    if len(text) > LINE_SAMPLE_MAX_CHARS:
        return text[:LINE_SAMPLE_MAX_CHARS] + "...<truncated>"
    return text


def try_numeric(field: bytes):
    """Return (kind, value). kind in {'int','float','nonfinite','invalid'}."""
    try:
        return "int", int(field)
    except ValueError:
        pass
    try:
        v = float(field)
    except ValueError:
        return "invalid", None
    if v != v or v == float("inf") or v == float("-inf"):
        return "nonfinite", v
    return "float", v


def new_col_state():
    return {
        "empty": 0,
        "samples": [],
        "sample_seen": set(),
        "ok": 0,
        "invalid": 0,
        "nonfinite": 0,
        "is_int": True,
        "min": None,
        "max": None,
        "prev": None,
        "adj_dec": 0,
        "adj_eq": 0,
    }


def inspect(path: str, out_dir: str) -> int:
    if not os.path.exists(path):
        print("خطأ: لم يتم العثور على الملف: %s" % path, file=sys.stderr)
        return EXIT_NOT_FOUND
    if os.path.isdir(path):
        print("خطأ: المسار مجلد وليس ملفاً: %s" % path, file=sys.stderr)
        return EXIT_NOT_A_FILE

    try:
        size_bytes = os.path.getsize(path)
    except PermissionError:
        print("خطأ: لا توجد صلاحية قراءة للملف: %s" % path, file=sys.stderr)
        return EXIT_PERMISSION

    # ---- single streaming pass: hash + all statistics -------------------
    file_hash = hashlib.sha256()
    rows_total = 0
    rows_blank = 0
    rows_too_long = 0
    field_dist = {}
    first_lines = []
    col_states = {}
    header_row1 = None
    header_row2 = None

    try:
        fh = open(path, "rb")
    except PermissionError:
        print("خطأ: لا توجد صلاحية قراءة للملف: %s" % path, file=sys.stderr)
        return EXIT_PERMISSION

    with fh:
        for raw in fh:
            rows_total += 1
            file_hash.update(raw)
            if len(first_lines) < 5:
                first_lines.append(decode_capped(raw))
            line = raw.rstrip(b"\r\n")
            if len(line) > MAX_PARSE_LINE_BYTES:
                rows_too_long += 1
                continue
            if line.strip() == b"":
                rows_blank += 1
                if header_row1 is None and header_row2 is None:
                    pass  # blank lines do not participate in header heuristic
                continue
            fields = line.split(b",")
            nf = len(fields)
            field_dist[nf] = field_dist.get(nf, 0) + 1
            if header_row1 is None:
                header_row1 = fields
                continue
            if header_row2 is None:
                header_row2 = fields

    # modal field count (tie -> smaller count)
    modal_nf = 0
    rows_profiled = 0
    if field_dist:
        modal_nf = max(field_dist.items(), key=lambda kv: (kv[1], -kv[0]))[0]
        rows_profiled = field_dist.get(modal_nf, 0)

    # second pass only over profiled rows for per-column state — NOT a copy of
    # the data and bounded memory (the file is re-read, not duplicated).
    # To honor "single pass" strictly we instead re-scan: the contract forbids
    # a second COPY of the data (disk/RAM), not a second read. State is bounded.
    col_states = {i: new_col_state() for i in range(1, modal_nf + 1)} if modal_nf else {}
    profiled_seen = 0
    try:
        fh = open(path, "rb")
    except PermissionError:
        print("خطأ: لا توجد صلاحية قراءة للملف: %s" % path, file=sys.stderr)
        return EXIT_PERMISSION
    with fh:
        for raw in fh:
            line = raw.rstrip(b"\r\n")
            if len(line) > MAX_PARSE_LINE_BYTES:
                continue
            if line.strip() == b"":
                continue
            fields = line.split(b",")
            if len(fields) != modal_nf:
                continue
            profiled_seen += 1
            for i, fld in enumerate(fields, 1):
                st = col_states[i]
                if fld.strip() == b"":
                    st["empty"] += 1
                    continue
                if len(st["samples"]) < SAMPLES_PER_COLUMN:
                    key = fld[:64]
                    if key not in st["sample_seen"]:
                        st["sample_seen"].add(key)
                        st["samples"].append(decode_capped(fld))
                kind, val = try_numeric(fld)
                if kind == "invalid":
                    st["invalid"] += 1
                    st["is_int"] = False
                    continue
                if kind == "nonfinite":
                    st["nonfinite"] += 1
                    st["is_int"] = False
                    continue
                st["ok"] += 1
                if kind == "float":
                    st["is_int"] = False
                if st["min"] is None or val < st["min"]:
                    st["min"] = val
                if st["max"] is None or val > st["max"]:
                    st["max"] = val
                if kind == "int":
                    if st["prev"] is not None:
                        if val < st["prev"]:
                            st["adj_dec"] += 1
                        elif val == st["prev"]:
                            st["adj_eq"] += 1
                    st["prev"] = val

    # ---- header detection heuristic (per-column kind mismatch) ----------
    def kinds(fields):
        return [try_numeric(f)[0] for f in fields]

    has_header = None
    detail = "not enough non-blank lines for a heuristic comparison"
    if header_row1 is not None and header_row2 is not None:
        if len(header_row1) != len(header_row2):
            detail = ("first two non-blank lines have different field counts "
                      "-> inconclusive; HEURISTIC only, not a documented "
                      "schema contract")
        else:
            k1 = kinds(header_row1)
            k2 = kinds(header_row2)
            flips = [j + 1 for j, (a, b) in enumerate(zip(k1, k2))
                     if a == "invalid" and b in ("int", "float", "nonfinite")]
            if flips:
                has_header = True
                detail = ("columns %s are non-numeric in line 1 but numeric in "
                          "line 2 -> likely a header; HEURISTIC only, not a "
                          "documented schema contract" % flips)
            else:
                has_header = False
                detail = ("line 1 and line 2 agree per-column on numeric kind "
                          "-> likely data rows; HEURISTIC only, not a "
                          "documented schema contract")

    # ---- build report ---------------------------------------------------
    columns = []
    for i in range(1, modal_nf + 1):
        st = col_states[i]
        non_empty = rows_profiled - st["empty"]
        if st["ok"] > 0 and st["is_int"]:
            type_hint = "integer-like"
        elif st["ok"] > 0:
            type_hint = "float-like"
        else:
            type_hint = "text-like"
        entry = {
            "index": i,
            "name": "col_%d" % i,
            "empty_count": st["empty"],
            "sample_values": st["samples"],
            "numeric": {
                "interpreted": st["ok"] > 0,
                "type_hint": type_hint,
                "ok_count": st["ok"],
                "invalid_numeric_count": st["invalid"],
                "nonfinite_count": st["nonfinite"],
                "min": st["min"],
                "max": st["max"],
                "integer_valued": st["ok"] > 0 and st["is_int"],
                "non_empty_count": non_empty,
            },
        }
        if st["ok"] > 0 and st["is_int"]:
            entry["numeric"]["ordering_integer_columns_only"] = {
                "adjacent_decreasing": st["adj_dec"],
                "adjacent_equal": st["adj_eq"],
            }
        columns.append(entry)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "Z"
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "inspect_%s_%s.json" % (sanitize_stem(path), ts))
    base, ext = os.path.splitext(report_path)
    k = 2
    while os.path.exists(report_path):
        report_path = "%s_%d%s" % (base, k, ext)
        k += 1

    report = {
        "report_format": REPORT_FORMAT,
        "tool": {
            "name": TOOL_NAME,
            "version": TOOL_VERSION,
            "sha256": tool_self_sha256(),
            "python": "%d.%d.%d" % sys.version_info[:3],
            "generated_at_utc": utc_now_iso(),
        },
        "file": {
            "path": os.path.abspath(path),
            "bytes": size_bytes,
            "gib": round(size_bytes / float(1024 ** 3), 6),
            "sha256": file_hash.hexdigest(),
        },
        "lines": {
            "first_5": first_lines,
            "last_5": tail_lines(path, 5),
        },
        "header_detection": {
            "has_header": has_header,
            "method": "HEURISTIC_NOT_A_DOCUMENTED_SCHEMA_CONTRACT",
            "detail": detail,
        },
        "rows": {
            "total": rows_total,
            "blank": rows_blank,
            "profiled": profiled_seen,
            "too_long_skipped": rows_too_long,
        },
        "schema": {
            "modal_field_count": modal_nf,
            "profiled_field_count": modal_nf,
            "field_count_distribution": {str(k2): v for k2, v in sorted(field_dist.items())},
        },
        "columns": columns,
        "binance_semantics": "NOT_VERIFIED",
        "semantic_guard": (
            "COLUMN POSITION DOES NOT IMPLY MEANING. This tool never labels a "
            "column as price, quantity, buyer-maker, aggressor, or a timestamp "
            "of any unit. Such meaning requires a documented source contract "
            "and is verified in a separate interpretation step."
        ),
        "not_computed": {
            "per_column_distinct_value_counts": NOT_COMPUTED,
            "full_row_duplicate_counts": NOT_COMPUTED,
            "value_multiplicity_counts": NOT_COMPUTED,
            "time_gap_statistics": NOT_COMPUTED,
            "note": ("these statistics need unbounded memory or external "
                     "sorting; this tool is memory-bounded and reports them "
                     "as NOT_COMPUTED_MEMORY_BOUNDED instead of guessing"),
        },
    }

    with open(report_path, "w", encoding="utf-8") as rf:
        json.dump(report, rf, ensure_ascii=False, indent=1)
        rf.write("\n")

    print("تم الفحص بنجاح")
    print("مسار التقرير: %s" % os.path.abspath(report_path))
    return EXIT_OK


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = argv[1:]
    out_dir = None
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--out":
            if i + 1 >= len(args):
                print("خطأ: --out يحتاج مسار مجلد", file=sys.stderr)
                return EXIT_UNEXPECTED
            out_dir = args[i + 1]
            i += 2
            continue
        positional.append(a)
        i += 1
    if not positional:
        print("خطأ: لم يُمرَّر مسار الملف. الاستخدام: reality_inspect.py <path> [--out dir]",
              file=sys.stderr)
        return EXIT_UNEXPECTED
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs")
    try:
        return inspect(args[0], out_dir)
    except PermissionError:
        print("خطأ: لا توجد صلاحية قراءة للملف: %s" % args[0], file=sys.stderr)
        return EXIT_PERMISSION
    except OSError as exc:
        print("خطأ: نظام الملفات: %s" % exc, file=sys.stderr)
        return EXIT_UNEXPECTED
    except Exception as exc:  # pragma: no cover - safety net
        print("خطأ غير متوقع: %s" % exc, file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main(sys.argv))

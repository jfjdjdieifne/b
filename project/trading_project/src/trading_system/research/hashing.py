"""Canonical SHA-256 identities for research-only factual records V1."""
from __future__ import annotations

from enum import Enum
import hashlib
import json
import math
from typing import Any

import numpy as np
import pandas as pd

from trading_system.research.information_time import InformationKey


class ResearchHashError(Exception):
    """Unsupported or invalid canonical hash payload."""


CANONICAL_HASH_VERSION = "RESEARCH_CANONICAL_SHA256_V1"
_MISSING = {"type": "missing"}


def _scalar(value: Any):
    if value is None or value is pd.NA or value is pd.NaT:
        return _MISSING
    if isinstance(value, float):
        # Python float and np.float64 (a float subclass) share this path;
        # `float.hex()` is identical to `value.item().hex()`.
        if math.isnan(value):
            return _MISSING
        if not math.isfinite(value):
            raise ResearchHashError("nonfinite hash scalar")
        return {"type": "float", "value": value.hex()}
    if isinstance(value, np.generic):
        if bool(pd.isna(value)):
            return _MISSING
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value):
            return _MISSING
        if not math.isfinite(value):
            raise ResearchHashError("nonfinite hash scalar")
        return {"type": "float", "value": value.hex()}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return _MISSING
        if value.tz is None:
            raise ResearchHashError("naive timestamp forbidden")
        utc = value.tz_convert("UTC")
        return {"type": "timestamp_utc_ns", "value": str(int(utc.value))}
    if isinstance(value, pd.Timedelta):
        if pd.isna(value):
            return _MISSING
        return {"type": "timedelta_ns", "value": str(int(value.value))}
    if isinstance(value, Enum):
        return {
            "type": "enum",
            "class": f"{value.__class__.__module__}.{value.__class__.__qualname__}",
            "value": _scalar(value.value),
        }
    raise ResearchHashError(f"unsupported scalar type: {type(value).__name__}")


def _index_payload(index: pd.Index):
    return {
        "class": f"{index.__class__.__module__}.{index.__class__.__qualname__}",
        "dtype": str(index.dtype),
        "name": _scalar(index.name),
        "values": [_scalar(value) for value in index.tolist()],
    }


def _column_cells(series: pd.Series):
    """Extract one column's cells as canonical scalar payloads.

    EXACT PERFORMANCE (test-suite acceleration): identical output to the
    historical per-cell ``DataFrame.iat`` walk (``_scalar`` is the shared
    normalizer; the fast paths below reproduce its float/int/bool outputs
    verbatim, including NaN -> missing, nonfinite rejection, and
    ``float.hex()`` identities). Only plain numpy-backed numeric/bool
    columns take the fast path; every other dtype goes through ``_scalar``
    cell-by-cell exactly as before.
    """
    values = getattr(series, "_values", None)
    if isinstance(values, np.ndarray):
        kind = series.dtype.kind
        if kind == "f":
            cells = []
            append = cells.append
            for value in values:
                if value != value:
                    append(_MISSING)
                elif not math.isfinite(value):
                    raise ResearchHashError("nonfinite hash scalar")
                else:
                    append({"type": "float", "value": float(value).hex()})
            return cells
        if kind in ("i", "u"):
            return [
                {"type": "int", "value": str(int(value))} for value in values
            ]
        if kind == "b":
            return [
                {"type": "bool", "value": bool(value)} for value in values
            ]
    # Fallback: `tolist()` boxes each cell exactly like per-cell `.iloc`
    # extraction does (shared `_scalar` normalizer => identical payloads;
    # nullable-dtype NA becomes NaN on boxing, and `_scalar` maps NaN and
    # pd.NA to the same missing sentinel).
    return [_scalar(value) for value in series.tolist()]

def _dataframe_payload(frame: pd.DataFrame):
    if not isinstance(frame, pd.DataFrame) or frame.columns.has_duplicates:
        raise ResearchHashError("invalid DataFrame hash payload")
    n_rows, n_cols = frame.shape
    if n_cols == 0:
        rows = [[] for _ in range(n_rows)]
    else:
        per_column = [
            _column_cells(frame.iloc[:, column]) for column in range(n_cols)
        ]
        rows = [list(row) for row in zip(*per_column)]
    return {
        "type": "dataframe",
        "columns": [_scalar(column) for column in frame.columns.tolist()],
        "column_index_class": (
            f"{frame.columns.__class__.__module__}."
            f"{frame.columns.__class__.__qualname__}"
        ),
        "dtypes": [str(dtype) for dtype in frame.dtypes.tolist()],
        "index": _index_payload(frame.index),
        "rows": rows,
    }


def _information_key_payload(key: InformationKey):
    if not isinstance(key, InformationKey):
        raise ResearchHashError("InformationKey required")
    return {
        "type": "information_key",
        "information_key_version": key.information_key_version,
        "timeline_id": key.timeline_id,
        "bar_position": str(key.bar_position),
        "event_time_utc": _scalar(key.event_time_utc),
        "information_phase": key.information_phase.value,
        "deterministic_sequence": str(key.deterministic_sequence),
    }


def canonical_payload(value: Any):
    if isinstance(value, InformationKey):
        return _information_key_payload(value)
    if isinstance(value, pd.DataFrame):
        return _dataframe_payload(value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ResearchHashError("canonical mapping keys must be strings")
        return {
            "type": "mapping",
            "items": [
                [key, canonical_payload(value[key])] for key in sorted(value)
            ],
        }
    if isinstance(value, (list, tuple)):
        return {
            "type": "sequence",
            "items": [canonical_payload(item) for item in value],
        }
    return _scalar(value)


def canonical_sha256(*, domain: str, payload: Any) -> str:
    if not isinstance(domain, str) or not domain:
        raise ResearchHashError("nonempty hash domain required")
    envelope = {
        "hash_version": CANONICAL_HASH_VERSION,
        "domain": domain,
        "payload": canonical_payload(payload),
    }
    encoded = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

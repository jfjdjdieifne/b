"""Layer 4 — Module 4.2B: Causal Dealing Range Context Engine V1.1.

Sequential confirmed opposite-side swing events create immutable range
candidates. Same-side events replace only the pending endpoint. Creation-row
completed close location is evaluated after causal creation. Geometry is
unclipped and descriptive; no premium/discount trading rule or Fibonacci/OTE.
"""
from __future__ import annotations

import math
from typing import Final, Optional
import numpy as np
import pandas as pd

class RangeError(Exception):
    pass

class RangeDataError(RangeError):
    pass

_A: Final = (
    "swing_high_confirmed", "swing_low_confirmed", "swing_origin_position",
    "swing_confirmation_position", "swing_price",
)
_B: Final = (
    "structure_event_type", "swing_sequence_class", "comparison_available",
    "previous_same_type_price", "previous_same_type_origin_position",
    "current_structure_swing_price", "current_structure_origin_position",
    "current_structure_confirmation_position", "same_type_log_price_change",
)
_HIGH_CLASSES = frozenset({"UNCLASSIFIED", "HH", "LH", "EH"})
_LOW_CLASSES = frozenset({"UNCLASSIFIED", "HL", "LL", "EL"})

_OUTPUTS: Final = (
    "dealing_range_created", "created_range_id", "created_range_direction",
    "created_range_creation_position", "created_range_low", "created_range_high",
    "created_range_width", "created_range_midpoint",
    "created_range_first_endpoint_side", "created_range_first_endpoint_origin_position",
    "created_range_first_endpoint_confirmation_position", "created_range_first_endpoint_price",
    "created_range_first_endpoint_class", "created_range_second_endpoint_side",
    "created_range_second_endpoint_origin_position", "created_range_second_endpoint_confirmation_position",
    "created_range_second_endpoint_price", "created_range_second_endpoint_class",
    "rejected_range_geometry", "current_range_id", "current_range_direction",
    "current_range_creation_position", "current_range_low", "current_range_high",
    "current_range_width", "current_range_midpoint", "current_range_position_raw",
    "current_midpoint_displacement", "current_discount_depth", "current_premium_depth",
)
_TABLE: Final = (
    "range_id", "creation_position", "direction", "first_endpoint_side",
    "first_endpoint_origin_position", "first_endpoint_confirmation_position",
    "first_endpoint_price", "first_endpoint_class", "second_endpoint_side",
    "second_endpoint_origin_position", "second_endpoint_confirmation_position",
    "second_endpoint_price", "second_endpoint_class", "range_low", "range_high",
    "range_width", "midpoint",
)

class CausalDealingRangeEngine:
    @staticmethod
    def _missing(value: object) -> bool:
        result = pd.isna(value)
        return isinstance(result, (bool, np.bool_)) and bool(result)

    @classmethod
    def _validate(cls, df: pd.DataFrame) -> None:
        if not isinstance(df, pd.DataFrame):
            raise RangeDataError("df must be a DataFrame")
        if df.columns.has_duplicates:
            raise RangeDataError("duplicate columns")
        required = ("close",) + _A + _B
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise RangeDataError(f"missing columns: {missing!r}")
        if any(column in df.columns for column in _OUTPUTS):
            raise RangeDataError("output collision")
        if df.index.has_duplicates or not df.index.is_monotonic_increasing:
            raise RangeDataError("index must be unique and monotonic")
        close = df["close"]
        if pd.api.types.is_bool_dtype(close.dtype) or not pd.api.types.is_numeric_dtype(close.dtype):
            raise RangeDataError("close must be real numeric")
        if not np.isfinite(close.to_numpy(dtype=np.float64, na_value=np.nan)).all():
            raise RangeDataError("close must be finite")
        for column in ("swing_high_confirmed", "swing_low_confirmed", "comparison_available"):
            series = df[column]
            if not pd.api.types.is_bool_dtype(series.dtype) or series.isna().any():
                raise RangeDataError(f"{column} must be non-missing boolean")

        high_flags = df["swing_high_confirmed"].to_numpy(dtype=bool)
        low_flags = df["swing_low_confirmed"].to_numpy(dtype=bool)
        if (high_flags & low_flags).any():
            raise RangeDataError("simultaneous HIGH/LOW confirmation")
        seen = {"HIGH": False, "LOW": False}
        last_price: dict[str, Optional[float]] = {"HIGH": None, "LOW": None}
        last_origin: dict[str, Optional[int]] = {"HIGH": None, "LOW": None}
        n = len(df)
        for i in range(n):
            side = "HIGH" if high_flags[i] else "LOW" if low_flags[i] else None
            event_type = str(df["structure_event_type"].iloc[i])
            sequence_class = str(df["swing_sequence_class"].iloc[i])
            comparison = bool(df["comparison_available"].iloc[i])
            if side is None:
                if event_type != "NONE" or sequence_class != "NONE" or comparison:
                    raise RangeDataError(f"malformed non-event row {i}")
                for column in (
                    "swing_origin_position", "swing_confirmation_position", "swing_price",
                    "previous_same_type_price", "previous_same_type_origin_position",
                    "current_structure_swing_price", "current_structure_origin_position",
                    "current_structure_confirmation_position", "same_type_log_price_change",
                ):
                    if not cls._missing(df[column].iloc[i]):
                        raise RangeDataError(f"non-event metadata pollution at row {i}")
                continue
            allowed = _HIGH_CLASSES if side == "HIGH" else _LOW_CLASSES
            if event_type != side or sequence_class not in allowed:
                raise RangeDataError(f"event/type/class mismatch at row {i}")
            positions = []
            for column in (
                "swing_origin_position", "swing_confirmation_position",
                "current_structure_origin_position", "current_structure_confirmation_position",
            ):
                value = df[column].iloc[i]
                if cls._missing(value) or isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
                    raise RangeDataError(f"invalid {column} at row {i}")
                positions.append(int(value))
            origin, confirmation, current_origin, current_confirmation = positions
            if not (0 <= origin < n and 0 <= confirmation < n and origin <= confirmation == i):
                raise RangeDataError(f"invalid positional contract at row {i}")
            price = float(df["swing_price"].iloc[i])
            current_price = float(df["current_structure_swing_price"].iloc[i])
            if not math.isfinite(price) or current_price != price or current_origin != origin or current_confirmation != i:
                raise RangeDataError(f"current metadata mismatch at row {i}")
            if not seen[side]:
                if sequence_class != "UNCLASSIFIED" or comparison:
                    raise RangeDataError(f"first-event semantics at row {i}")
                for column in ("previous_same_type_price", "previous_same_type_origin_position", "same_type_log_price_change"):
                    if not cls._missing(df[column].iloc[i]):
                        raise RangeDataError(f"first-event metadata at row {i}")
            else:
                if sequence_class == "UNCLASSIFIED" or not comparison:
                    raise RangeDataError(f"comparison semantics at row {i}")
                previous_price = float(df["previous_same_type_price"].iloc[i])
                previous_origin = int(df["previous_same_type_origin_position"].iloc[i])
                if previous_price != last_price[side] or previous_origin != last_origin[side]:
                    raise RangeDataError(f"previous linkage at row {i}")
                log_value = df["same_type_log_price_change"].iloc[i]
                if price > 0 and previous_price > 0:
                    if float(log_value) != math.log(price) - math.log(previous_price):
                        raise RangeDataError(f"log linkage at row {i}")
                elif not cls._missing(log_value):
                    raise RangeDataError(f"non-positive log semantics at row {i}")
            seen[side] = True
            last_price[side] = price
            last_origin[side] = origin

    @staticmethod
    def _empty_table() -> pd.DataFrame:
        result = {column: pd.Series([], dtype="float64") for column in _TABLE}
        for column in (
            "range_id", "creation_position", "first_endpoint_origin_position",
            "first_endpoint_confirmation_position", "second_endpoint_origin_position",
            "second_endpoint_confirmation_position",
        ):
            result[column] = pd.array([], dtype="Int64")
        for column in (
            "direction", "first_endpoint_side", "first_endpoint_class",
            "second_endpoint_side", "second_endpoint_class",
        ):
            result[column] = pd.array([], dtype="string")
        return pd.DataFrame(result)[list(_TABLE)]

    def analyze(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        self._validate(df)
        n = len(df)
        created = np.zeros(n, dtype=bool)
        rejected = np.zeros(n, dtype=bool)
        integer_outputs = {
            name: pd.array([pd.NA] * n, dtype="Int64")
            for name in (
                "created_range_id", "created_range_creation_position",
                "created_range_first_endpoint_origin_position",
                "created_range_first_endpoint_confirmation_position",
                "created_range_second_endpoint_origin_position",
                "created_range_second_endpoint_confirmation_position",
                "current_range_id", "current_range_creation_position",
            )
        }
        string_outputs = {
            name: np.full(n, "NONE", dtype=object)
            for name in (
                "created_range_direction", "created_range_first_endpoint_side",
                "created_range_first_endpoint_class", "created_range_second_endpoint_side",
                "created_range_second_endpoint_class", "current_range_direction",
            )
        }
        float_names = (
            "created_range_low", "created_range_high", "created_range_width",
            "created_range_midpoint", "created_range_first_endpoint_price",
            "created_range_second_endpoint_price", "current_range_low",
            "current_range_high", "current_range_width", "current_range_midpoint",
            "current_range_position_raw", "current_midpoint_displacement",
            "current_discount_depth", "current_premium_depth",
        )
        floats = {name: np.full(n, np.nan) for name in float_names}
        pending: Optional[dict[str, object]] = None
        current: Optional[dict[str, object]] = None
        ranges: list[dict[str, object]] = []

        for i in range(n):
            high_event = bool(df["swing_high_confirmed"].iloc[i])
            low_event = bool(df["swing_low_confirmed"].iloc[i])
            side = "HIGH" if high_event else "LOW" if low_event else None
            if side is not None:
                endpoint = {
                    "side": side,
                    "origin": int(df["swing_origin_position"].iloc[i]),
                    "confirmation": i,
                    "price": float(df["swing_price"].iloc[i]),
                    "class": str(df["swing_sequence_class"].iloc[i]),
                }
                if pending is not None and pending["side"] != side:
                    low_price = endpoint["price"] if side == "LOW" else pending["price"]
                    high_price = endpoint["price"] if side == "HIGH" else pending["price"]
                    with np.errstate(over="ignore", invalid="ignore"):
                        width = float(high_price) - float(low_price)
                    if not math.isfinite(width):
                        raise RangeDataError("range width overflow")
                    if width > 0.0:
                        midpoint = float(low_price) + width / 2.0
                        if not math.isfinite(midpoint):
                            raise RangeDataError("midpoint overflow")
                        row = {
                            "range_id": len(ranges),
                            "creation_position": i,
                            "direction": "ASCENDING_DEALING_RANGE_CANDIDATE" if pending["side"] == "LOW" else "DESCENDING_DEALING_RANGE_CANDIDATE",
                            "first_endpoint_side": pending["side"],
                            "first_endpoint_origin_position": pending["origin"],
                            "first_endpoint_confirmation_position": pending["confirmation"],
                            "first_endpoint_price": pending["price"],
                            "first_endpoint_class": pending["class"],
                            "second_endpoint_side": endpoint["side"],
                            "second_endpoint_origin_position": endpoint["origin"],
                            "second_endpoint_confirmation_position": endpoint["confirmation"],
                            "second_endpoint_price": endpoint["price"],
                            "second_endpoint_class": endpoint["class"],
                            "range_low": low_price,
                            "range_high": high_price,
                            "range_width": width,
                            "midpoint": midpoint,
                        }
                        ranges.append(row)
                        current = row
                        created[i] = True
                        integer_outputs["created_range_id"][i] = row["range_id"]
                        integer_outputs["created_range_creation_position"][i] = i
                        integer_outputs["created_range_first_endpoint_origin_position"][i] = pending["origin"]
                        integer_outputs["created_range_first_endpoint_confirmation_position"][i] = pending["confirmation"]
                        integer_outputs["created_range_second_endpoint_origin_position"][i] = endpoint["origin"]
                        integer_outputs["created_range_second_endpoint_confirmation_position"][i] = i
                        string_outputs["created_range_direction"][i] = row["direction"]
                        string_outputs["created_range_first_endpoint_side"][i] = pending["side"]
                        string_outputs["created_range_first_endpoint_class"][i] = pending["class"]
                        string_outputs["created_range_second_endpoint_side"][i] = endpoint["side"]
                        string_outputs["created_range_second_endpoint_class"][i] = endpoint["class"]
                        floats["created_range_low"][i] = low_price
                        floats["created_range_high"][i] = high_price
                        floats["created_range_width"][i] = width
                        floats["created_range_midpoint"][i] = midpoint
                        floats["created_range_first_endpoint_price"][i] = pending["price"]
                        floats["created_range_second_endpoint_price"][i] = endpoint["price"]
                    else:
                        rejected[i] = True
                pending = endpoint

            if current is not None:
                integer_outputs["current_range_id"][i] = current["range_id"]
                integer_outputs["current_range_creation_position"][i] = current["creation_position"]
                string_outputs["current_range_direction"][i] = current["direction"]
                floats["current_range_low"][i] = current["range_low"]
                floats["current_range_high"][i] = current["range_high"]
                floats["current_range_width"][i] = current["range_width"]
                floats["current_range_midpoint"][i] = current["midpoint"]
                with np.errstate(over="ignore", invalid="ignore"):
                    numerator = float(df["close"].iloc[i]) - float(current["range_low"])
                if not math.isfinite(numerator):
                    raise RangeDataError("location numerator overflow")
                position = numerator / float(current["range_width"])
                if not math.isfinite(position):
                    raise RangeDataError("location overflow")
                displacement = 2.0 * position - 1.0
                if not math.isfinite(displacement):
                    raise RangeDataError("midpoint displacement overflow")
                discount = max(-displacement, 0.0)
                premium = max(displacement, 0.0)
                if not math.isfinite(discount) or not math.isfinite(premium):
                    raise RangeDataError("depth overflow")
                floats["current_range_position_raw"][i] = position
                floats["current_midpoint_displacement"][i] = displacement
                floats["current_discount_depth"][i] = discount
                floats["current_premium_depth"][i] = premium

        out = df.copy(deep=True)
        out["dealing_range_created"] = created
        for name, values in integer_outputs.items():
            out[name] = values
        for name, values in string_outputs.items():
            out[name] = pd.array(values, dtype="string")
        for name, values in floats.items():
            out[name] = values
        out["rejected_range_geometry"] = rejected
        out = out.loc[:, list(df.columns) + list(_OUTPUTS)]

        if not ranges:
            return out, self._empty_table()
        table = pd.DataFrame(ranges)
        for column in (
            "range_id", "creation_position", "first_endpoint_origin_position",
            "first_endpoint_confirmation_position", "second_endpoint_origin_position",
            "second_endpoint_confirmation_position",
        ):
            table[column] = pd.array(table[column], dtype="Int64")
        for column in (
            "direction", "first_endpoint_side", "first_endpoint_class",
            "second_endpoint_side", "second_endpoint_class",
        ):
            table[column] = pd.array(table[column], dtype="string")
        return out, table.loc[:, list(_TABLE)]

class _RangeAuditEngine(CausalDealingRangeEngine):
    pass

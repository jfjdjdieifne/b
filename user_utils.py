# -*- coding: utf-8 -*-
"""Small user-facing parsing and timestamp helpers shared by every UI."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
DAMASCUS_TZ = ZoneInfo("Asia/Damascus")
UTC_TZ = timezone.utc

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")


def parse_price(value) -> float:
    """Parse common Arabic/English price formats safely.

    Accepted examples: ``1769.75``, ``1,769.75``, ``1.769,75`` and the
    user's accidental ``1.769.75``.  In the last form, all separators
    except the final one are treated as grouping separators.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
    else:
        text = str(value or "").translate(_ARABIC_DIGITS).strip()
        text = re.sub(r"[^0-9,\.\-+]", "", text)
        if not text or text in {"-", "+", ".", ","}:
            raise ValueError("أدخل سعراً رقمياً مثل 1769.75 أو 1,769.75")
        sign = "-" if text.startswith("-") else ""
        text = text.lstrip("+-")
        separators = [(i, ch) for i, ch in enumerate(text) if ch in ".,"]
        if separators:
            # Last separator is decimal when 1-8 digits follow it.  Earlier
            # separators are thousands/grouping separators.
            last_i, _ = separators[-1]
            tail_len = len(text) - last_i - 1
            if 1 <= tail_len <= 8:
                integer = re.sub(r"[.,]", "", text[:last_i]) or "0"
                fraction = re.sub(r"[.,]", "", text[last_i + 1:])
                text = integer + "." + fraction
            else:
                text = re.sub(r"[.,]", "", text)
        result = float(sign + text)
    if not (result > 0):
        raise ValueError("السعر يجب أن يكون أكبر من صفر")
    return result


def ensure_ms(ts) -> int:
    value = int(float(ts))
    return value * 1000 if value < 10_000_000_000 else value


def dual_time(ts_ms=None) -> dict[str, str | int]:
    """Return one instant in UTC, New York and Damascus with real DST rules."""
    if ts_ms is None:
        dt_utc = datetime.now(UTC_TZ)
    else:
        dt_utc = datetime.fromtimestamp(ensure_ms(ts_ms) / 1000, tz=UTC_TZ)
    ny = dt_utc.astimezone(NY_TZ)
    damascus = dt_utc.astimezone(DAMASCUS_TZ)
    return {
        "timestamp_ms": int(dt_utc.timestamp() * 1000),
        "utc": dt_utc.isoformat(timespec="seconds"),
        "new_york": ny.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"),
        "damascus": damascus.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"),
        "new_york_iso": ny.isoformat(timespec="seconds"),
        "damascus_iso": damascus.isoformat(timespec="seconds"),
    }


def closed_candle_stamp(data: dict) -> dict:
    if not data or not data.get("timestamps"):
        return {}
    open_ms = data["timestamps"][-1]
    close_ms = (data.get("close_timestamps") or [open_ms])[-1]
    return {
        "open": dual_time(open_ms),
        "close": dual_time(close_ms),
        "confirmed_closed": bool(data.get("last_candle_closed", data.get("closed_only", False))),
    }

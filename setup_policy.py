# -*- coding: utf-8 -*-
"""Lifecycle rules for intraday setup candidates."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from user_utils import dual_time, ensure_ms

NY = ZoneInfo("America/New_York")


def setup_expiry(created_ms: int, model: str, timeframe: str) -> dict:
    """Expire at the end of the next relevant ICT window, capped by bars.

    This is a transparent project policy, not a universal rule attributed to
    Michael. It prevents a 5-minute intraday setup from waiting forever.
    """
    created_ms = ensure_ms(created_ms)
    created_utc = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
    ny = created_utc.astimezone(NY)
    model = str(model or "")

    # Current or next configured window end in New York local time.
    end_hours = [5, 11, 16]
    expiry_ny = None
    for hour in end_hours:
        candidate = ny.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > ny:
            expiry_ny = candidate
            break
    if expiry_ny is None:
        next_day = ny + timedelta(days=1)
        expiry_ny = next_day.replace(hour=5, minute=0, second=0, microsecond=0)

    tf_minutes = {"1m": 1, "3m": 3, "5m": 5}.get(timeframe, 5)
    max_bars = {
        "MODEL_E_SILVER_BULLET": 12,  # roughly one hour
        "MODEL_D_AMD_SESSION": 30,
        "MODEL_B_SWEEP_FVG": 48,
        "MODEL_A_OTE_OB": 72,
        "MODEL_C_BOS_PULLBACK": 72,
        "MODEL_F_CHOCH_REVERSAL": 48,
    }.get(model, 48)
    bar_cap = created_utc + timedelta(minutes=tf_minutes * max_bars)
    expiry_utc = min(expiry_ny.astimezone(timezone.utc), bar_cap)
    expiry_ms = int(expiry_utc.timestamp() * 1000)
    return {
        "expires_at_ms": expiry_ms,
        "expires_at": dual_time(expiry_ms),
        "max_wait_bars": max_bars,
        "policy": "EARLIER_OF_MODEL_BAR_CAP_OR_RELEVANT_SESSION_END",
        "invalidation": [
            "closed candle beyond structural stop before entry",
            "TP1 reached before entry (move already delivered)",
            "setup no longer qualifies on re-analysis",
        ],
    }

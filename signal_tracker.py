# -*- coding: utf-8 -*-
"""Legacy signal evaluator fixed for limit orders and future-only candles.

For live, incremental TP1/TP2/runner management use ``trade_monitor.py``.
"""
import logging
from datetime import datetime

from data_manager import DataManager
from signal_repository import SignalRepository
from user_utils import dual_time


class SignalTracker:
    def __init__(self):
        self.logger = logging.getLogger("SignalTracker")
        self.data_manager = DataManager()
        self.repo = SignalRepository()

    @staticmethod
    def _created_ms(signal):
        created = signal.get("created_at")
        if isinstance(created, dict):
            return created.get("timestamp_ms")
        if isinstance(created, (int, float)):
            return int(created)
        if isinstance(created, str):
            try:
                return int(datetime.fromisoformat(created).timestamp() * 1000)
            except ValueError:
                return None
        return None

    def evaluate_signal(self, signal):
        symbol = signal["symbol"]
        timeframe = signal["timeframe"]
        exchange = signal.get("exchange") or "auto"
        data = self.data_manager.get_ohlcv(
            symbol, timeframe, limit=250, exchange=exchange,
            closed_only=True, allow_fallback=(exchange == "auto"),
        )
        if not data:
            return {"result": "data_error", "details": self.data_manager.get_last_fetch_report()}

        side = str(signal.get("signal", "HOLD")).upper()
        if side not in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
            return {"result": "ignored", "reason": "Not an executable signal"}
        entry = SignalRepository._price(signal.get("entry"))
        sl = SignalRepository._price(signal.get("stop_loss"))
        tp1 = SignalRepository._price(signal.get("tp1"))
        tp2 = SignalRepository._price(signal.get("tp2"))
        tp3 = SignalRepository._price(signal.get("tp3"))
        if not all(v is not None for v in (entry, sl, tp1)):
            return {"result": "invalid_plan", "reason": "entry/SL/TP1 missing"}

        is_long = side in ("BUY", "BUY_LIMIT")
        if (is_long and not sl < entry < tp1) or (not is_long and not sl > entry > tp1):
            return {"result": "invalid_plan", "reason": "SL/TP1 on wrong side"}

        close_times = data.get("close_timestamps") or data["timestamps"]
        created_ms = self._created_ms(signal)
        indices = [i for i, ts in enumerate(close_times) if created_ms is None or int(ts) > int(created_ms)]
        if created_ms is None:
            # Never replay the complete historical response for a legacy
            # timestamp we cannot parse; that produced false instant wins.
            indices = indices[-2:]
        if not indices:
            return {"result": "waiting", "reason": "No closed candle after signal creation"}

        entered = False
        entry_index = None
        hit_tp1 = hit_tp2 = hit_tp3 = hit_sl = False
        exit_reason = exit_price = None
        max_favorable = max_adverse = None

        for i in indices:
            high, low = data["highs"][i], data["lows"][i]
            if not entered:
                if not (low <= entry <= high):
                    continue
                entered, entry_index = True, i

            favorable = (high - entry) if is_long else (entry - low)
            adverse = (entry - low) if is_long else (high - entry)
            max_favorable = favorable if max_favorable is None else max(max_favorable, favorable)
            max_adverse = adverse if max_adverse is None else max(max_adverse, adverse)

            candle_sl = low <= sl if is_long else high >= sl
            candle_tp1 = high >= tp1 if is_long else low <= tp1
            candle_tp2 = tp2 is not None and (high >= tp2 if is_long else low <= tp2)
            candle_tp3 = tp3 is not None and (high >= tp3 if is_long else low <= tp3)

            # Conservative ordering if both sides occur inside one OHLC bar.
            if candle_sl and (candle_tp1 or candle_tp2 or candle_tp3):
                hit_sl, exit_reason, exit_price = True, "sl_first_same_candle", sl
                break
            if candle_sl:
                hit_sl, exit_reason, exit_price = True, "sl_hit", sl
                break
            if candle_tp1:
                hit_tp1 = True
            if candle_tp2:
                hit_tp2, exit_reason, exit_price = True, "tp2_hit", tp2
                break
            if candle_tp3:
                hit_tp3, exit_reason, exit_price = True, "tp3_hit", tp3
                break

        if not entered:
            return {"result": "not_triggered_yet", "details": "Price has not reached entry after creation"}
        if hit_tp3:
            result = "full_win"
        elif hit_tp2:
            result = "strong_win"
        elif hit_sl and hit_tp1:
            result = "partial_then_loss"
        elif hit_sl:
            result = "loss"
        elif hit_tp1:
            result = "partial_win_open_runner"
        else:
            result = "open"
        return {
            "result": result,
            "entered": entered,
            "entry_index_from_end": entry_index - data["count"] if entry_index is not None else None,
            "hit_tp1": hit_tp1, "hit_tp2": hit_tp2, "hit_tp3": hit_tp3, "hit_sl": hit_sl,
            "exit_reason": exit_reason, "exit_price": exit_price,
            "max_favorable_move": round(max_favorable, 8) if max_favorable is not None else None,
            "max_adverse_move": round(max_adverse, 8) if max_adverse is not None else None,
            "checked_at": dual_time(),
            "source": data.get("source"),
        }

    def check_all_unchecked(self):
        reports = []
        final_results = {"full_win", "strong_win", "partial_then_loss", "loss", "invalid_plan", "ignored"}
        for signal in self.repo.get_unchecked_signals():
            report = self.evaluate_signal(signal)
            if report.get("result") in final_results:
                self.repo.mark_checked(signal["id"], report)
            reports.append({
                "signal_id": signal["id"], "symbol": signal["symbol"],
                "timeframe": signal["timeframe"], "report": report,
            })
        return reports

# -*- coding: utf-8 -*-
"""Persistent one-click trade monitoring with TP1/TP2 and a runner.

The monitor observes *closed* candles.  It never places exchange orders; it
tracks an educational plan and records every state transition with New York
and Damascus timestamps.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from typing import Any

from config import Config
from data_manager import DataManager
from setup_policy import setup_expiry
from user_utils import dual_time, parse_price


FINAL_STATES = {"stopped", "tp2_hit", "closed", "cancelled", "expired", "invalidated"}


class TradeMonitor:
    def __init__(self, data_manager: DataManager | None = None, file_path: str | None = None):
        self.dm = data_manager or DataManager()
        self.file_path = file_path or os.path.join(Config.DATA_DIR, "tracked_trades.json")
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.trades = self._load()

    def _load(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                # Migrate watchlists created before expiry protocol existed.
                now_ms = dual_time()["timestamp_ms"]
                for trade in data:
                    if trade.get("status") in ("watchlist", "pending_entry") and not trade.get("expires_at_ms"):
                        created_ms = (trade.get("created_at") or {}).get("timestamp_ms") or now_ms
                        life = setup_expiry(created_ms, trade.get("model"), trade.get("timeframe", "5m"))
                        trade["expires_at_ms"] = life["expires_at_ms"]
                        trade["activation_allowed"] = False
                return data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def _save(self):
        temp = self.file_path + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(self.trades, f, ensure_ascii=False, indent=2)
        os.replace(temp, self.file_path)

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = ("symbol", "exchange", "timeframe", "side", "entry", "stop_loss", "tp1")
        missing = [k for k in required if payload.get(k) in (None, "")]
        if missing:
            raise ValueError(f"حقول ناقصة للتتبع: {', '.join(missing)}")
        side = str(payload["side"]).upper()
        if side not in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"):
            raise ValueError("الاتجاه يجب أن يكون BUY/SELL أو LIMIT/STOP صحيح")
        entry = parse_price(payload["entry"])
        sl = parse_price(payload["stop_loss"])
        tp1 = parse_price(payload["tp1"])
        tp2 = parse_price(payload["tp2"]) if payload.get("tp2") not in (None, "") else None
        is_long = "BUY" in side
        if is_long and not (sl < entry < tp1):
            raise ValueError("للشراء يجب أن يكون SL < Entry < TP1")
        if not is_long and not (sl > entry > tp1):
            raise ValueError("للبيع يجب أن يكون SL > Entry > TP1")
        if tp2 is not None and ((is_long and tp2 <= tp1) or (not is_long and tp2 >= tp1)):
            raise ValueError("TP2 يجب أن يكون أبعد من TP1 باتجاه الصفقة")

        allocation = float(payload.get("tp1_allocation_pct") or Config.TP1_ALLOCATION_PCT)
        if not 1 <= allocation <= 100:
            raise ValueError("نسبة TP1 يجب أن تكون بين 1 و100%")
        stop_policy = str(payload.get("post_tp1_stop_policy") or Config.POST_TP1_STOP_POLICY).upper()
        if stop_policy not in ("BE_THEN_STRUCTURE", "STRUCTURE_ONLY"):
            raise ValueError("سياسة Runner غير صالحة")
        requested_status = str(payload.get("status") or "watchlist").lower()
        status = requested_status if requested_status in ("watchlist", "pending_entry", "active") else "watchlist"
        now = dual_time()
        trade = {
            "id": f"T-{uuid.uuid4().hex[:8]}",
            "symbol": self.dm.normalize_symbol(payload["symbol"]),
            "exchange": self.dm.normalize_exchange(payload["exchange"]),
            "timeframe": self.dm.normalize_timeframe(payload["timeframe"]),
            "side": side,
            "model": payload.get("model"),
            "entry": entry,
            "initial_stop_loss": sl,
            "current_stop_loss": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp1_allocation_pct": allocation,
            "post_tp1_stop_policy": stop_policy,
            "quantity": float(payload.get("quantity") or 0),
            "risk_usd": float(payload.get("risk_usd") or 0),
            "notification_chat_id": payload.get("notification_chat_id"),
            "status": status,
            "tp1_hit": False,
            "remaining_pct": 100,
            "realized_r": 0.0,
            "last_price": None,
            "last_processed_close_ms": None,
            "expires_at_ms": int(payload["expires_at_ms"]) if payload.get("expires_at_ms") else None,
            "activation_allowed": bool(payload.get("activation_allowed", status != "watchlist")),
            "created_at": now,
            "updated_at": now,
            "events": [{"type": "CREATED", "status": status, "time": now}],
        }
        with self._lock:
            self.trades.append(trade)
            self._save()
        return trade

    def activate(self, trade_id: str, verified=False) -> dict:
        with self._lock:
            trade = self._find(trade_id)
            if trade["status"] == "watchlist":
                if not (verified or trade.get("activation_allowed")):
                    raise ValueError("لا يمكن تفعيل Pending يدوياً؛ يجب أن تصبح READY بإعادة تحليل حديثة")
                trade["activation_allowed"] = True
                trade["status"] = "pending_entry"
                self._event(trade, "ACTIVATED", "تحققت شروط READY؛ بدأ انتظار دخول على شمعة لاحقة")
                self._save()
            return trade

    def cancel(self, trade_id: str) -> dict:
        with self._lock:
            trade = self._find(trade_id)
            trade["status"] = "cancelled"
            self._event(trade, "CANCELLED", "ألغى المستخدم التتبع")
            self._save()
            return trade

    def invalidate(self, trade_id: str, reason: str) -> dict:
        with self._lock:
            trade = self._find(trade_id)
            if trade["status"] not in FINAL_STATES:
                trade["status"] = "invalidated"
                self._event(trade, "SETUP_REANALYSIS_FAILED", reason)
                self._save()
            return trade

    def list(self) -> list[dict]:
        with self._lock:
            return json.loads(json.dumps(self.trades, ensure_ascii=False))

    def refresh_all(self) -> dict[str, Any]:
        results = []
        with self._lock:
            ids = [t["id"] for t in self.trades if t.get("status") not in FINAL_STATES]
        for trade_id in ids:
            try:
                results.append({"id": trade_id, "trade": self.refresh(trade_id)})
            except Exception as exc:
                results.append({"id": trade_id, "error": str(exc)})
        return {"updated": len([r for r in results if "trade" in r]), "results": results, "time": dual_time()}

    def refresh(self, trade_id: str) -> dict:
        with self._lock:
            trade = self._find(trade_id)
            if trade["status"] in FINAL_STATES:
                return trade
            data = self.dm.get_ohlcv(
                trade["symbol"], trade["timeframe"], 80,
                exchange=trade["exchange"], closed_only=True, allow_fallback=False,
            )
            if not data:
                raise RuntimeError(f"فشل تحديث السعر من {trade['exchange']}: {self.dm.get_last_fetch_report()}")
            latest_close_ms = int(data.get("close_timestamps", data["timestamps"])[-1])
            if (trade["status"] in ("watchlist", "pending_entry")
                    and trade.get("expires_at_ms")
                    and latest_close_ms >= int(trade["expires_at_ms"])):
                trade["status"] = "expired"
                self._event(trade, "SETUP_EXPIRED", "انتهت نافذة النموذج قبل تحقق دخول صالح", latest_close_ms)
                trade["last_price"] = data["closes"][-1]
                self._save()
                return trade
            last_seen = trade.get("last_processed_close_ms")
            created_ms = (trade.get("created_at") or {}).get("timestamp_ms")
            cutoff = last_seen if last_seen is not None else created_ms
            indices = [
                i for i, ts in enumerate(data.get("close_timestamps", data["timestamps"]))
                if cutoff is None or int(ts) > int(cutoff)
            ]
            # Legacy record without a timestamp: process at most two latest
            # candles rather than replaying history that predates tracking.
            if cutoff is None:
                indices = indices[-2:]
            for i in indices:
                self._process_candle(trade, data, i)
                trade["last_processed_close_ms"] = int(data.get("close_timestamps", data["timestamps"])[i])
                if trade["status"] in FINAL_STATES:
                    break
            trade["last_price"] = data["closes"][-1]
            trade["updated_at"] = dual_time(data.get("close_timestamps", data["timestamps"])[-1])
            trade["data_source"] = data["source"]
            self._save()
            return trade

    def _process_candle(self, trade: dict, data: dict, i: int):
        high, low, close = data["highs"][i], data["lows"][i], data["closes"][i]
        ts = data.get("close_timestamps", data["timestamps"])[i]
        is_long = "BUY" in trade["side"]
        entry, sl, tp1, tp2 = trade["entry"], trade["current_stop_loss"], trade["tp1"], trade.get("tp2")

        if trade["status"] in ("watchlist", "pending_entry"):
            invalidated = close < trade["initial_stop_loss"] if is_long else close > trade["initial_stop_loss"]
            move_delivered = high >= tp1 if is_long else low <= tp1
            if invalidated:
                trade["status"] = "invalidated"
                self._event(trade, "SETUP_INVALIDATED_BEFORE_ENTRY", "إغلاق تجاوز مستوى الإبطال قبل الدخول", ts)
                return
            if move_delivered and not (low <= entry <= high):
                trade["status"] = "invalidated"
                self._event(trade, "TARGET_REACHED_WITHOUT_ENTRY", "وصل السعر إلى TP1 قبل إعطاء دخول؛ انتهت الفرصة ولم نلاحقها", ts)
                return

        if trade["status"] == "watchlist":
            if low <= entry <= high:
                self._event(trade, "WATCHLIST_PRICE_TOUCHED", "السعر لمس المنطقة لكن شروط التفعيل لم تكتمل؛ لم نفترض دخولاً", ts)
            return

        if trade["status"] == "pending_entry":
            if not (low <= entry <= high):
                return
            trade["status"] = "active"
            self._event(trade, "ENTRY_FILLED_SIMULATED", f"لمس السعر دخول {entry}", ts)
            # Conservative same-candle ambiguity: if SL and TP are both inside
            # the candle after a simulated fill, assume SL first.
            hit_sl = low <= sl if is_long else high >= sl
            hit_tp1 = high >= tp1 if is_long else low <= tp1
            if hit_sl:
                self._stop(trade, ts, "SL on entry candle (conservative ordering)")
                return
            if hit_tp1:
                self._hit_tp1(trade, ts)
                return

        if trade["status"] not in ("active", "runner"):
            return

        hit_sl = low <= trade["current_stop_loss"] if is_long else high >= trade["current_stop_loss"]
        if not trade["tp1_hit"]:
            hit_tp1 = high >= tp1 if is_long else low <= tp1
            if hit_sl and hit_tp1:
                self._stop(trade, ts, "SL and TP1 in same closed candle; conservative SL-first")
            elif hit_sl:
                self._stop(trade, ts, "SL hit before TP1")
            elif hit_tp1:
                self._hit_tp1(trade, ts)
            return

        hit_tp2 = bool(tp2 is not None and ((high >= tp2) if is_long else (low <= tp2)))
        if hit_sl and hit_tp2:
            # After TP1 both are profitable/BE in most plans; use conservative
            # stop-first for unknown intrabar ordering.
            self._runner_stop(trade, ts, "Trailing stop and TP2 in same candle; conservative stop-first")
        elif hit_tp2:
            runner_fraction = float(trade.get("remaining_pct", 0)) / 100
            trade["status"] = "tp2_hit"
            trade["remaining_pct"] = 0
            risk = abs(trade["entry"] - trade["initial_stop_loss"])
            r2 = abs(tp2 - trade["entry"]) / risk if risk else 0
            trade["realized_r"] = round(trade["realized_r"] + runner_fraction * r2, 3)
            self._event(trade, "TP2_HIT", f"أُغلق الجزء المتبقي عند {tp2}", ts)
        elif hit_sl:
            self._runner_stop(trade, ts, "Trailing/BE stop hit")
        else:
            self._trail_structure(trade, data, i, ts)

    def _hit_tp1(self, trade: dict, ts):
        risk = abs(trade["entry"] - trade["initial_stop_loss"])
        r1 = abs(trade["tp1"] - trade["entry"]) / risk if risk else 0
        allocation = float(trade.get("tp1_allocation_pct", 50))
        fraction = allocation / 100
        trade["tp1_hit"] = True
        trade["remaining_pct"] = round(100 - allocation, 4)
        trade["realized_r"] = round(fraction * r1, 3)
        policy = trade.get("post_tp1_stop_policy", "BE_THEN_STRUCTURE")
        if allocation >= 100:
            trade["status"] = "closed"
            self._event(trade, "TP1_FULL_EXIT", "أُغلق كامل المركز عند TP1 حسب النسبة المختارة", ts)
        else:
            trade["status"] = "runner"
            if policy == "BE_THEN_STRUCTURE":
                trade["current_stop_loss"] = trade["entry"]
                self._event(trade, "TP1_HIT", f"أُغلق {allocation}% ونُقل SL إلى BE ثم يبدأ HL/LH", ts)
            else:
                self._event(trade, "TP1_HIT", f"أُغلق {allocation}% وبقي SL الأصلي حتى يؤكد HL/LH جديد", ts)

    def _stop(self, trade: dict, ts, reason: str):
        trade["status"] = "stopped"
        trade["remaining_pct"] = 0
        trade["realized_r"] = -1.0
        self._event(trade, "STOPPED", reason, ts)

    def _runner_stop(self, trade: dict, ts, reason: str):
        risk = abs(trade["entry"] - trade["initial_stop_loss"])
        exit_r = ((trade["current_stop_loss"] - trade["entry"]) / risk
                  if "BUY" in trade["side"] else
                  (trade["entry"] - trade["current_stop_loss"]) / risk) if risk else 0
        runner_fraction = float(trade.get("remaining_pct", 0)) / 100
        trade["status"] = "closed"
        trade["remaining_pct"] = 0
        trade["realized_r"] = round(trade["realized_r"] + runner_fraction * exit_r, 3)
        self._event(trade, "RUNNER_STOPPED", reason, ts)

    def _trail_structure(self, trade: dict, data: dict, i: int, ts):
        if i < 4:
            return
        highs, lows = data["highs"], data["lows"]
        is_long = "BUY" in trade["side"]
        # Confirmed 2-left/2-right pivot; use only candles fully known at i.
        pivot_i = i - 2
        if pivot_i < 2:
            return
        if is_long and lows[pivot_i] == min(lows[pivot_i - 2:pivot_i + 3]):
            candidate = lows[pivot_i]
            if candidate > trade["current_stop_loss"]:
                trade["current_stop_loss"] = candidate
                self._event(trade, "TRAIL_RAISED", f"رفع الستوب خلف HL مؤكد إلى {candidate}", ts)
        elif not is_long and highs[pivot_i] == max(highs[pivot_i - 2:pivot_i + 3]):
            candidate = highs[pivot_i]
            if candidate < trade["current_stop_loss"]:
                trade["current_stop_loss"] = candidate
                self._event(trade, "TRAIL_LOWERED", f"خفض الستوب خلف LH مؤكد إلى {candidate}", ts)

    def _event(self, trade: dict, event_type: str, detail: str, ts=None):
        stamp = dual_time(ts)
        trade.setdefault("events", []).append({"type": event_type, "detail_ar": detail, "time": stamp})
        trade["updated_at"] = stamp

    def _find(self, trade_id: str) -> dict:
        for trade in self.trades:
            if trade.get("id") == trade_id:
                return trade
        raise KeyError(f"صفقة غير موجودة: {trade_id}")

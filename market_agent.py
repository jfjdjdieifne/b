# -*- coding: utf-8 -*-
"""24/7 closed-candle paper market scanner.

It never places real exchange orders. READY setups become paper pending entries
and are filled only by a later closed candle, avoiding same-bar look-ahead.
"""
from __future__ import annotations

import json
import os
import signal
import threading
import time
from typing import Any

from config import Config
from data_manager import DataManager
from paper_account import PaperAccount
from snapshot_analyzer import SnapshotAnalyzer
from trade_monitor import FINAL_STATES, TradeMonitor
from user_utils import dual_time


class MarketAgent:
    def __init__(self, data_manager=None, monitor=None, paper=None, state_path=None):
        self.dm = data_manager or DataManager()
        self.analyzer = SnapshotAnalyzer(self.dm)
        self.monitor = monitor or TradeMonitor(self.dm)
        self.paper = paper or PaperAccount()
        self.state_path = state_path or os.path.join(Config.DATA_DIR, "market_agent_state.json")
        self._stop = threading.Event()
        self._thread = None
        self.state = self._load_state()
        self.state.setdefault("tombstones", {})
        self.state.setdefault("blocked_rearms", 0)

    def _load_state(self):
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                if isinstance(state, dict): return state
        except (OSError, json.JSONDecodeError):
            pass
        return {
            "running": False, "exchange": "binance", "execution_timeframe": "5m",
            "scan_interval_seconds": 300, "universe_size": 12,
            "risk_pct": Config.PAPER_DEFAULT_RISK_PCT,
            "tp1_allocation_pct": Config.TP1_ALLOCATION_PCT,
            "notification_chat_id": None,
            "last_cycle": None, "next_cycle_at": None, "cycle": 0,
            "symbols": [], "last_results": [], "events": [],
        }

    def _save(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, self.state_path)

    def configure(self, **values):
        if values.get("exchange") is not None:
            self.state["exchange"] = self.dm.normalize_exchange(values["exchange"])
        if values.get("execution_timeframe") is not None:
            tf = self.dm.normalize_timeframe(values["execution_timeframe"])
            if tf not in ("1m", "3m", "5m"): raise ValueError("فريم الوكيل: 1m/3m/5m فقط")
            self.state["execution_timeframe"] = tf
        if values.get("scan_interval_seconds") is not None:
            self.state["scan_interval_seconds"] = max(60, int(values["scan_interval_seconds"]))
        if values.get("universe_size") is not None:
            self.state["universe_size"] = min(30, max(1, int(values["universe_size"])))
        if values.get("risk_pct") is not None:
            risk = float(values["risk_pct"])
            if not 0 < risk <= 5: raise ValueError("المخاطرة بين 0 و5%")
            self.state["risk_pct"] = risk
        if values.get("tp1_allocation_pct") is not None:
            allocation = float(values["tp1_allocation_pct"])
            if not 1 <= allocation <= 100: raise ValueError("نسبة TP1 بين 1 و100%")
            self.state["tp1_allocation_pct"] = allocation
        if values.get("notification_chat_id") is not None:
            self.state["notification_chat_id"] = values["notification_chat_id"]
        self._save()
        return self.status()

    def start(self, **config):
        if config: self.configure(**config)
        if self._thread and self._thread.is_alive(): return self.status()
        self._stop.clear()
        self.state["running"] = True
        self._save()
        self._thread = threading.Thread(target=self._loop, name="MarketAgent", daemon=True)
        self._thread.start()
        return self.status()

    def stop(self):
        self._stop.set()
        self.state["running"] = False
        self.state["next_cycle_at"] = None
        self._save()
        return self.status()

    def status(self):
        out = json.loads(json.dumps(self.state, ensure_ascii=False))
        out["thread_alive"] = bool(self._thread and self._thread.is_alive())
        out["paper_account"] = self.paper.snapshot()
        return out

    def run_once(self):
        self.monitor.refresh_all()
        self._sync_tombstones()
        self.paper.reconcile(self.monitor.list())
        universe = self.dm.get_market_universe(
            self.state["exchange"], self.state["universe_size"]
        )
        exchange = universe["exchange"]
        symbols = universe["symbols"]
        self.state["symbols"] = symbols
        cycle_results = []
        for symbol in symbols:
            if self._stop.is_set(): break
            try:
                result = self.analyzer.analyze(
                    symbol=symbol, exchange=exchange,
                    execution_timeframe=self.state["execution_timeframe"],
                    balance=self.paper.snapshot()["balance"],
                    risk_pct=self.state["risk_pct"],
                    tp1_allocation_pct=self.state["tp1_allocation_pct"],
                )
                summary = {
                    "symbol": symbol, "ok": result.get("ok"),
                    "audit_id": result.get("audit_id"),
                    "decision": (result.get("decision") or {}).get("state"),
                    "model": (result.get("candidate") or {}).get("model"),
                    "reason": (result.get("decision") or {}).get("reason_ar"),
                    "time": dual_time(),
                }
                cycle_results.append(summary)
                if result.get("ok"):
                    self._handle_analysis(result)
            except Exception as exc:
                cycle_results.append({"symbol": symbol, "ok": False, "error": str(exc), "time": dual_time()})
        self.monitor.refresh_all()
        self._sync_tombstones()
        self.paper.reconcile(self.monitor.list())
        self.state["cycle"] = int(self.state.get("cycle", 0)) + 1
        self.state["last_cycle"] = dual_time()
        self.state["last_results"] = cycle_results
        self.state["last_universe_basis"] = universe.get("basis")
        self._save()
        return self.status()

    def _handle_analysis(self, analysis):
        symbol = analysis["symbol"]
        candidate = analysis.get("candidate")
        decision = (analysis.get("decision") or {}).get("state")
        existing = [
            t for t in self.monitor.list()
            if t["symbol"] == symbol and t["status"] not in FINAL_STATES
        ]
        if not candidate:
            for trade in existing:
                if trade["status"] in ("watchlist", "pending_entry"):
                    reason = "إعادة التحليل لم تعد تجد نموذجاً صالحاً"
                    self.monitor.invalidate(trade["id"], reason)
                    self._record_tombstone(trade, reason)
            return

        same = next((t for t in existing if t.get("model") == candidate["model"]), None)
        # Material plan drift means the old thesis/coordinates are obsolete.
        if same:
            drift = abs(same["entry"] - candidate["entry"]) / candidate["entry"]
            if drift > 0.001 or same["initial_stop_loss"] != candidate["stop_loss"]:
                if same["status"] in ("watchlist", "pending_entry"):
                    reason = "تغيرت منطقة/إبطال النموذج مادياً عند إعادة التحليل"
                    self.monitor.invalidate(same["id"], reason)
                    self._record_tombstone(same, reason)
                    same = None

        if not same and not existing and not self._can_rearm(symbol, candidate):
            self.state["blocked_rearms"] = int(self.state.get("blocked_rearms", 0)) + 1
            self._event("REARM_BLOCKED_BY_COOLDOWN", symbol, analysis["audit_id"])
            return

        if decision == "READY_NOW":
            account = self.paper.snapshot()
            risk_capacity_full = account["open_risk_usd"] >= account["balance"] * self.paper.max_total_risk_pct / 100
            if risk_capacity_full:
                self._event("READY_BUT_RISK_CAPACITY_FULL", symbol, analysis["audit_id"])
                return
            if same and same["status"] == "watchlist":
                self.monitor.activate(same["id"], verified=True)
                self._event("AUTO_ACTIVATED", symbol, analysis["audit_id"])
            elif not same and not existing:
                payload = dict(candidate["tracking_payload"])
                payload.update(status="pending_entry", auto_discovered=True,
                               notification_chat_id=self.state.get("notification_chat_id"))
                trade = self.monitor.add(payload)
                self.paper.register_plan(trade, analysis, auto=True)
                self._event("AUTO_READY_PLAN", symbol, analysis["audit_id"])
        elif decision == "WATCHLIST" and not same and not existing:
            payload = dict(candidate["tracking_payload"])
            payload.update(status="watchlist", auto_discovered=True,
                           notification_chat_id=self.state.get("notification_chat_id"))
            trade = self.monitor.add(payload)
            self.paper.register_plan(trade, analysis, auto=True)
            self._event("AUTO_WATCHLIST", symbol, analysis["audit_id"])

    @staticmethod
    def _fingerprint_values(model, entry, stop):
        return {"model": model, "entry": round(float(entry), 6), "stop": round(float(stop), 6)}

    def _record_tombstone(self, trade, reason):
        key = f"{trade['symbol']}:{trade.get('model') or 'UNKNOWN'}"
        now_ms = dual_time()["timestamp_ms"]
        tombstones = self.state.setdefault("tombstones", {})
        record = {
            **self._fingerprint_values(trade.get("model"), trade["entry"], trade["initial_stop_loss"]),
            "reason": reason, "trade_id": trade["id"], "recorded_at_ms": now_ms,
            "cooldown_until_ms": now_ms + 6 * 60 * 60 * 1000,
        }
        tombstones[key] = record
        # Also cool down the symbol across models for one hour. A model label
        # changing five minutes later is not automatically a new market thesis.
        tombstones[f"{trade['symbol']}:*"] = {
            **record, "cooldown_until_ms": now_ms + 60 * 60 * 1000,
        }

    def _sync_tombstones(self):
        for trade in self.monitor.list():
            if trade.get("status") not in ("invalidated", "expired"):
                continue
            key = f"{trade['symbol']}:{trade.get('model') or 'UNKNOWN'}"
            current = self.state.setdefault("tombstones", {}).get(key)
            if not current or current.get("trade_id") != trade["id"]:
                last_event = (trade.get("events") or [{}])[-1]
                self._record_tombstone(trade, last_event.get("detail_ar") or trade["status"])

    def _can_rearm(self, symbol, candidate):
        tombstones = self.state.setdefault("tombstones", {})
        now_ms = dual_time()["timestamp_ms"]
        symbol_tomb = tombstones.get(f"{symbol}:*")
        if symbol_tomb and now_ms < int(symbol_tomb.get("cooldown_until_ms", 0)):
            return False
        key = f"{symbol}:{candidate.get('model') or 'UNKNOWN'}"
        tomb = tombstones.get(key)
        if not tomb:
            return True
        if now_ms < int(tomb.get("cooldown_until_ms", 0)):
            return False
        entry_drift = abs(float(candidate["entry"]) - float(tomb["entry"])) / max(abs(float(candidate["entry"])), 1e-9)
        stop_drift = abs(float(candidate["stop_loss"]) - float(tomb["stop"])) / max(abs(float(candidate["stop_loss"])), 1e-9)
        return max(entry_drift, stop_drift) >= 0.003

    def _event(self, kind, symbol, audit_id=None):
        self.state.setdefault("events", []).append({
            "type": kind, "symbol": symbol, "audit_id": audit_id, "time": dual_time()
        })
        self.state["events"] = self.state["events"][-300:]

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:
                self._event("CYCLE_ERROR", "MARKET", str(exc))
            wait = int(self.state["scan_interval_seconds"])
            self.state["next_cycle_at"] = dual_time(int((time.time() + wait) * 1000))
            self._save()
            self._stop.wait(wait)
        self.state["running"] = False
        self._save()


def main():
    agent = MarketAgent()
    agent.start()
    print("✅ الوكيل يعمل 24/7 بمحاكاة ورقية فقط. Ctrl+C للإيقاف.")
    def stop(*_): agent.stop()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while agent.status()["thread_alive"]:
        time.sleep(2)


if __name__ == "__main__":
    main()

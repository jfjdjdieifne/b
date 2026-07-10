# -*- coding: utf-8 -*-
"""Persistent $100 paper account and complete simulated-trade journal."""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from config import Config
from user_utils import dual_time


class PaperAccount:
    def __init__(self, file_path=None, initial_balance=None):
        self.file_path = file_path or os.path.join(Config.DATA_DIR, "paper_account.json")
        self.initial_balance = float(initial_balance or getattr(Config, "PAPER_INITIAL_BALANCE", 100.0))
        self.max_total_risk_pct = float(getattr(Config, "PAPER_MAX_TOTAL_RISK_PCT", 5.0))
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.data = self._load()

    def _load(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
        return {
            "mode": "PAPER_SIMULATION_ONLY",
            "initial_balance": self.initial_balance,
            "balance": self.initial_balance,
            "realized_pnl": 0.0,
            "positions": [],
            "journal": [],
            "created_at": dual_time(),
            "updated_at": dual_time(),
        }

    def _save(self):
        self.data["updated_at"] = dual_time()
        tmp = self.file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, self.file_path)

    def snapshot(self):
        with self._lock:
            out = json.loads(json.dumps(self.data, ensure_ascii=False))
            out["equity"] = round(out["balance"], 4)  # closed-candle paper PnL; open MTM intentionally omitted
            out["open_risk_usd"] = round(sum(
                p.get("actual_risk_usd", 0) for p in out["positions"]
                if p.get("status") in ("active", "runner")
            ), 4)
            return_value = ((out["balance"] / out["initial_balance"] - 1) * 100
                            if out["initial_balance"] else 0)
            out["return_pct"] = round(return_value, 3)
            return out

    def reset(self, initial_balance=100.0):
        with self._lock:
            self.initial_balance = float(initial_balance)
            self.data = {
                "mode": "PAPER_SIMULATION_ONLY", "initial_balance": self.initial_balance,
                "balance": self.initial_balance, "realized_pnl": 0.0,
                "positions": [], "journal": [], "created_at": dual_time(), "updated_at": dual_time(),
            }
            self._save()
            return self.snapshot()

    def register_plan(self, tracked_trade: dict, analysis: dict | None = None, auto=False):
        """Persist why a plan was watched, including the complete audit snapshot."""
        with self._lock:
            if any(j.get("trade_id") == tracked_trade["id"] for j in self.data["journal"]):
                return
            candidate = (analysis or {}).get("candidate", {})
            self.data["journal"].append({
                "trade_id": tracked_trade["id"],
                "audit_id": (analysis or {}).get("audit_id"),
                "auto_discovered": bool(auto),
                "symbol": tracked_trade["symbol"], "exchange": tracked_trade["exchange"],
                "timeframe": tracked_trade["timeframe"], "model": tracked_trade.get("model"),
                "side": tracked_trade["side"], "planned_entry": tracked_trade["entry"],
                "planned_stop": tracked_trade["initial_stop_loss"],
                "planned_tp1": tracked_trade["tp1"], "planned_tp2": tracked_trade.get("tp2"),
                "tp1_allocation_pct": tracked_trade.get("tp1_allocation_pct", 50),
                "why_entered": candidate.get("basis"),
                "conditions": candidate.get("conditions", []),
                "expected": (analysis or {}).get("expectation") or candidate.get("decision"),
                "frame_evidence": (analysis or {}).get("frames"),
                "entry_models": (analysis or {}).get("entry_models"),
                "analysis_time": (analysis or {}).get("analysis_time"),
                "data_cutoff": (analysis or {}).get("data_cutoff"),
                "created_at": dual_time(),
                "status": "watchlist",
                "default_capital": self.data["balance"],
                "default_risk_pct": round(
                    tracked_trade.get("risk_usd", 0) / self.data["balance"] * 100
                    if self.data["balance"] else 0, 4
                ),
                "scenario_capital": None,
                "scenario_risk_pct": None,
                "result": None,
            })
            self._save()

    def reconcile(self, tracked_trades: list[dict]):
        """Mirror monitor state, open at 1x notional, and settle final R."""
        with self._lock:
            by_id = {t["id"]: t for t in tracked_trades}
            for trade_id, trade in by_id.items():
                journal = next((j for j in self.data["journal"] if j["trade_id"] == trade_id), None)
                if journal:
                    journal["status"] = trade["status"]
                entry_event = next((e for e in trade.get("events", []) if e.get("type") == "ENTRY_FILLED_SIMULATED"), None)
                position = next((p for p in self.data["positions"] if p["trade_id"] == trade_id), None)
                if entry_event and position is None:
                    requested_risk = float(trade.get("risk_usd") or self.data["balance"] * 0.01)
                    open_risk = sum(p.get("actual_risk_usd", 0) for p in self.data["positions"] if p["status"] in ("active", "runner"))
                    capacity = max(0.0, self.data["balance"] * self.max_total_risk_pct / 100 - open_risk)
                    risk_budget = min(requested_risk, capacity)
                    risk_per_unit = abs(trade["entry"] - trade["initial_stop_loss"])
                    risk_qty = risk_budget / risk_per_unit if risk_per_unit else 0
                    one_x_qty = self.data["balance"] / trade["entry"] if trade["entry"] else 0
                    qty = min(risk_qty, one_x_qty)  # no hidden leverage
                    actual_risk = qty * risk_per_unit
                    position = {
                        "trade_id": trade_id, "symbol": trade["symbol"], "side": trade["side"],
                        "entry": trade["entry"], "stop_loss": trade["initial_stop_loss"],
                        "tp1": trade["tp1"], "tp2": trade.get("tp2"),
                        "quantity": round(qty, 10), "notional": round(qty * trade["entry"], 4),
                        "actual_risk_usd": round(actual_risk, 6),
                        "risk_pct_of_balance": round(actual_risk / self.data["balance"] * 100, 4) if self.data["balance"] else 0,
                        "status": trade["status"], "opened_at": entry_event.get("time"),
                        "settled": False,
                    }
                    self.data["positions"].append(position)
                    if journal:
                        journal["actual_entry"] = trade["entry"]
                        journal["quantity"] = position["quantity"]
                        journal["actual_risk_usd"] = position["actual_risk_usd"]
                        journal["opened_at"] = entry_event.get("time")
                if position:
                    position["status"] = trade["status"]
                    if trade["status"] in ("stopped", "tp2_hit", "closed") and not position["settled"]:
                        pnl = float(trade.get("realized_r", 0)) * position["actual_risk_usd"]
                        self.data["balance"] = round(self.data["balance"] + pnl, 6)
                        self.data["realized_pnl"] = round(self.data["realized_pnl"] + pnl, 6)
                        position.update({"settled": True, "pnl_usd": round(pnl, 6), "realized_r": trade.get("realized_r"), "closed_at": trade.get("updated_at")})
                        if journal:
                            journal["result"] = {
                                "status": trade["status"], "realized_r": trade.get("realized_r"),
                                "pnl_usd": round(pnl, 6), "balance_after": self.data["balance"],
                                "events": trade.get("events", []),
                            }
            self._save()
            return self.snapshot()

    def set_scenario(self, trade_id, capital=None, risk_pct=None):
        with self._lock:
            journal = next((j for j in self.data["journal"] if j["trade_id"] == trade_id), None)
            if not journal:
                raise KeyError(f"سجل غير موجود: {trade_id}")
            if capital is not None:
                capital = float(capital)
                if capital <= 0: raise ValueError("رأس المال يجب أن يكون موجباً")
                journal["scenario_capital"] = capital
            if risk_pct is not None:
                risk_pct = float(risk_pct)
                if not 0 < risk_pct <= 10: raise ValueError("المخاطرة يجب أن تكون بين 0 و10%")
                journal["scenario_risk_pct"] = risk_pct
            self._save()
            return self.scenario_result(journal)

    @staticmethod
    def scenario_result(journal):
        capital = journal.get("scenario_capital") or journal.get("default_capital") or 100
        risk_pct = journal.get("scenario_risk_pct") or journal.get("default_risk_pct") or 1
        realized_r = ((journal.get("result") or {}).get("realized_r"))
        pnl = realized_r * capital * risk_pct / 100 if realized_r is not None else None
        return {
            "trade_id": journal["trade_id"], "capital": capital, "risk_pct": risk_pct,
            "realized_r": realized_r, "hypothetical_pnl": round(pnl, 4) if pnl is not None else None,
            "hypothetical_balance": round(capital + pnl, 4) if pnl is not None else capital,
        }

    def journal_with_scenarios(self):
        with self._lock:
            return [{**j, "scenario": self.scenario_result(j)} for j in self.data["journal"]]

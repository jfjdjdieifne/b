# -*- coding: utf-8 -*-
"""No-lookahead, closed-candle walk-forward simulation."""
from __future__ import annotations

import bisect
import json
import os
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from config import Config
from data_manager import DataManager, DataManagerError
from ict_math_engine import simulate_managed_trade_outcome
from ict_sessions import classify_session
from snapshot_analyzer import SnapshotAnalyzer
from user_utils import dual_time


class HistoricalDataManager(DataManager):
    """Serve data slices ending at a moving historical cutoff."""
    def __init__(self, datasets, exchange):
        self.datasets = datasets
        self.exchange = exchange
        self.cutoff = 0
        self.last_fetch_report = {}
        self.default_exchange = exchange

    def get_ohlcv(self, symbol, timeframe, limit, **kwargs):
        tf = self.normalize_timeframe(timeframe)
        data = self.datasets.get(tf)
        if not data: return None
        close_times = data.get("close_timestamps") or data["timestamps"]
        last = bisect.bisect_right(close_times, self.cutoff) - 1
        if last < 0: return None
        first = max(0, last-int(limit)+1)
        out = self._slice_indices(data, first, last)
        out.update(source=self.exchange, closed_only=True, last_candle_closed=True)
        self.last_fetch_report = {"used_exchange": self.exchange, "timeframe": tf, "historical_cutoff": self.cutoff}
        return out

    def get_last_fetch_report(self): return dict(self.last_fetch_report)


class WalkForwardBacktester:
    def __init__(self, data_manager=None, reports_dir=None):
        self.dm = data_manager or DataManager()
        self.reports_dir = reports_dir or os.path.join(Config.DATA_DIR, "backtests")
        os.makedirs(self.reports_dir, exist_ok=True)

    @staticmethod
    def _parse_date(value, end=False):
        if isinstance(value, (int, float)): return int(value)
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        if end and len(str(value)) <= 10:
            dt = dt + timedelta(days=1) - timedelta(milliseconds=1)
        return int(dt.timestamp()*1000)

    def run(self, symbol, start, end, exchange="binance", execution_timeframe="5m",
            initial_balance=100.0, risk_pct=1.0, fee_bps=10.0, slippage_bps=2.0,
            tp1_allocation_pct=None):
        symbol = self.dm.normalize_symbol(symbol)
        exchange = self.dm.normalize_exchange(exchange)
        tf = self.dm.normalize_timeframe(execution_timeframe)
        if tf not in ("1m", "3m", "5m"): raise ValueError("فريم التنفيذ 1m/3m/5m فقط")
        start_ms, end_ms = self._parse_date(start), self._parse_date(end, end=True)
        if end_ms <= start_ms: raise ValueError("تاريخ النهاية يجب أن يكون بعد البداية")
        if (end_ms-start_ms) > 93*86400*1000: raise ValueError("الاختبار السريع محدود بـ93 يوماً لكل تشغيل")
        balance = float(initial_balance)
        if balance <= 0 or not 0 < float(risk_pct) <= 5: raise ValueError("الرصيد موجب والمخاطرة 0-5%")
        tp1_allocation_pct = float(Config.TP1_ALLOCATION_PCT if tp1_allocation_pct is None else tp1_allocation_pct)
        if not 1 <= tp1_allocation_pct <= 100: raise ValueError("نسبة TP1 بين 1 و100%")

        warmups = {tf: 4*86400*1000, "15m": 8*86400*1000, "4h": 70*86400*1000, "1d": 320*86400*1000}
        datasets = {}
        for frame in (tf, "15m", "4h", "1d"):
            datasets[frame] = self.dm.get_historical_ohlcv(
                symbol, frame, start_ms-warmups[frame], end_ms, exchange
            )
            if not datasets[frame] or datasets[frame]["count"] < 20:
                raise DataManagerError(f"بيانات تاريخية غير كافية لـ{frame} من {exchange}")

        hist_dm = HistoricalDataManager(datasets, exchange)
        analyzer = SnapshotAnalyzer(hist_dm)
        entry_data = datasets[tf]
        close_times = entry_data.get("close_timestamps") or entry_data["timestamps"]
        start_i = bisect.bisect_left(close_times, start_ms)
        end_i = bisect.bisect_right(close_times, end_ms)
        stride = {"5m": 3, "3m": 5, "1m": 15}[tf]  # one decision checkpoint per 15m

        trades, signals, no_fills, checkpoints = [], 0, 0, 0
        decision_counts, bias_counts = Counter(), Counter()
        model_status_counts, rejection_reasons = Counter(), Counter()
        equity_curve = [{"time": dual_time(start_ms), "balance": balance}]
        i = start_i
        while i < end_i:
            cutoff = int(close_times[i])
            # Fast mode evaluates only configured time windows and every 15m.
            session = classify_session(cutoff)
            if not session.get("is_executable_window") or ((i-start_i) % stride):
                i += 1; continue
            hist_dm.cutoff = cutoff
            checkpoints += 1
            result = analyzer.analyze(symbol, exchange, tf, balance, risk_pct, tp1_allocation_pct)
            if result.get("ok"):
                decision_counts[result.get("decision", {}).get("state", "UNKNOWN")] += 1
                bias_counts[result.get("bias", {}).get("state", "UNKNOWN")] += 1
                for model in result.get("entry_models", []):
                    model_status_counts[f"{model.get('model')}:{model.get('status')}"] += 1
                    for reason in model.get("failed", []): rejection_reasons[f"FAILED:{reason}"] += 1
                    for reason in model.get("pending", []): rejection_reasons[f"PENDING:{reason}"] += 1
            else:
                decision_counts["DATA_ERROR"] += 1
            candidate = result.get("candidate") if result.get("ok") else None
            if not candidate or result["decision"]["state"] != "READY_NOW":
                i += 1; continue
            signals += 1
            expiry = int(candidate["lifecycle"]["expires_at_ms"])
            fill_i = None
            for j in range(i+1, end_i):  # strictly future candle only
                if close_times[j] > expiry: break
                if entry_data["lows"][j] <= candidate["entry"] <= entry_data["highs"][j]:
                    fill_i = j; break
            if fill_i is None:
                no_fills += 1; i += stride; continue

            future = self._slice(entry_data, fill_i, end_i-1)
            second = candidate["targets"][1] if len(candidate["targets"]) > 1 else None
            tp2_info = ({"mode": "TARGET", "price": second["price"]} if second else {"mode": "OPEN_TRAILING"})
            outcome = simulate_managed_trade_outcome(
                future, candidate["entry"], candidate["stop_loss"],
                candidate["targets"][0]["price"], tp2_info,
                is_short="SELL" in candidate["side"],
                tp1_fraction=tp1_allocation_pct/100,
            )
            risk_per_unit = abs(candidate["entry"]-candidate["stop_loss"])
            risk_budget = balance*float(risk_pct)/100
            qty = min(risk_budget/risk_per_unit if risk_per_unit else 0, balance/candidate["entry"])
            gross_pnl = qty*candidate["entry"]*float(outcome.get("pnl_pct_blended",0))/100
            roundtrip_cost = qty*candidate["entry"]*2*(float(fee_bps)+float(slippage_bps))/10000
            net_pnl = gross_pnl-roundtrip_cost
            actual_risk = qty*risk_per_unit
            realized_r = net_pnl/actual_risk if actual_risk else 0
            balance = round(balance+net_pnl, 6)
            final_rel = int(outcome.get("final_exit_idx_from_start") or 0)
            exit_i = min(end_i-1, fill_i+final_rel)
            trade = {
                "id": f"BT-{uuid.uuid4().hex[:8]}", "audit_id": result["audit_id"],
                "symbol": symbol, "exchange": exchange, "timeframe": tf,
                "signal_cutoff": dual_time(cutoff), "entry_time": dual_time(close_times[fill_i]),
                "exit_time": dual_time(close_times[exit_i]), "model": candidate["model"],
                "side": candidate["side"], "entry": candidate["entry"], "stop_loss": candidate["stop_loss"],
                "tp1": candidate["targets"][0], "tp2": second or {"mode":"OPEN_TRAILING"},
                "conditions": candidate["conditions"], "basis": candidate["basis"],
                "classification": outcome.get("classification"), "gross_pnl": round(gross_pnl,6),
                "costs": round(roundtrip_cost,6), "net_pnl": round(net_pnl,6),
                "realized_r": round(realized_r,4), "balance_after": balance,
                "outcome_detail": outcome,
            }
            trades.append(trade)
            equity_curve.append({"time": trade["exit_time"], "balance": balance})
            i = max(i+1, exit_i+1)  # one position at a time on this symbol

        wins = sum(1 for t in trades if t["net_pnl"] > 0)
        losses = sum(1 for t in trades if t["net_pnl"] < 0)
        report = {
            "id": f"WFT-{uuid.uuid4().hex[:10]}", "method": "STRICT_WALK_FORWARD_CLOSED_CANDLES",
            "lookahead_prevention": [
                "analysis slices contain close_time <= signal cutoff only",
                "entry can fill from the next candle only",
                "outcome candles are read only after the plan is frozen",
                "same-candle SL/TP ambiguity uses conservative ordering in simulator",
            ],
            "fast_mode": "decision checkpoint every 15m inside configured execution windows",
            "symbol": symbol, "exchange": exchange, "execution_timeframe": tf,
            "start": dual_time(start_ms), "end": dual_time(end_ms),
            "initial_balance": float(initial_balance), "final_balance": balance,
            "net_pnl": round(balance-float(initial_balance),6),
            "return_pct": round((balance/float(initial_balance)-1)*100,3),
            "risk_pct": float(risk_pct), "tp1_allocation_pct": tp1_allocation_pct,
            "fee_bps_each_side": float(fee_bps),
            "slippage_bps_each_side": float(slippage_bps), "checkpoints": checkpoints,
            "signals": signals, "no_fills": no_fills, "trades": trades,
            "decision_counts": dict(decision_counts), "bias_state_counts": dict(bias_counts),
            "model_status_counts": dict(model_status_counts),
            "top_rejection_reasons": dict(rejection_reasons.most_common(30)),
            "trade_count": len(trades), "wins": wins, "losses": losses,
            "win_rate": round(wins/len(trades)*100,2) if trades else None,
            "average_r": round(sum(t["realized_r"] for t in trades)/len(trades),3) if trades else None,
            "equity_curve": equity_curve, "generated_at": dual_time(),
            "disclaimer": "Hypothetical simulation; not indicative of future performance.",
        }
        path = os.path.join(self.reports_dir, report["id"]+".json")
        with open(path,"w",encoding="utf-8") as f: json.dump(report,f,ensure_ascii=False,indent=2,default=str)
        report["saved_to"] = path
        return report

    @staticmethod
    def _slice(data, first, last):
        return DataManager._slice_indices(data, first, last)

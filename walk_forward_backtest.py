# -*- coding: utf-8 -*-
"""No-lookahead, closed-candle walk-forward simulation."""
from __future__ import annotations

import bisect
import hashlib
import json
import os
import shutil
import subprocess
import time
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

    def run(self, symbol, start, end, exchange="kucoin", execution_timeframe="5m",
            initial_balance=100.0, risk_pct=1.0, fee_bps=10.0, slippage_bps=2.0,
            tp1_allocation_pct=None, progress_callback=None, checkpoint_minutes=15):
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
        checkpoint_minutes = max(5, int(checkpoint_minutes))
        started_at = time.monotonic()

        def emit(stage, **extra):
            if progress_callback:
                progress_callback({"stage": stage, "symbol": symbol, "exchange": exchange,
                                   "elapsed_seconds": round(time.monotonic()-started_at, 1), **extra})

        report_id = f"WFT-{uuid.uuid4().hex[:10]}"
        bundle_dir = os.path.join(self.reports_dir, report_id)
        trade_cases_dir = os.path.join(bundle_dir, "trade_cases")
        os.makedirs(trade_cases_dir, exist_ok=True)
        emit("BACKTEST_START", start_ms=start_ms, end_ms=end_ms,
             report_id=report_id, bundle_dir=bundle_dir)
        warmups = {tf: 4*86400*1000, "15m": 8*86400*1000, "4h": 70*86400*1000, "1d": 320*86400*1000}
        datasets = {}
        frames = (tf, "15m", "4h", "1d")
        for frame_no, frame in enumerate(frames, 1):
            emit("FRAME_DOWNLOAD_START", frame=frame, frame_no=frame_no, frame_total=len(frames))
            def frame_progress(event, fr=frame):
                detail = dict(event)
                stage_name = detail.pop("stage", "PROGRESS")
                for duplicate in ("symbol", "exchange", "timeframe"):
                    detail.pop(duplicate, None)
                emit("OHLCV_" + stage_name, frame=fr, **detail)
            datasets[frame] = self.dm.get_historical_ohlcv(
                symbol, frame, start_ms-warmups[frame], end_ms, exchange,
                progress_callback=frame_progress,
            )
            if not datasets[frame] or datasets[frame]["count"] < 20:
                raise DataManagerError(f"بيانات تاريخية غير كافية لـ{frame} من {exchange}")
            emit("FRAME_DOWNLOAD_DONE", frame=frame, candles=datasets[frame]["count"],
                 frame_no=frame_no, frame_total=len(frames))

        hist_dm = HistoricalDataManager(datasets, exchange)
        analyzer = SnapshotAnalyzer(hist_dm)
        entry_data = datasets[tf]
        close_times = entry_data.get("close_timestamps") or entry_data["timestamps"]
        start_i = bisect.bisect_left(close_times, start_ms)
        end_i = bisect.bisect_right(close_times, end_ms)
        tf_minutes = {"5m": 5, "3m": 3, "1m": 1}[tf]
        stride = max(1, round(checkpoint_minutes / tf_minutes))

        trades, signals, no_fills, checkpoints = [], 0, 0, 0
        audit_cases = []
        decision_counts, bias_counts = Counter(), Counter()
        model_status_counts, rejection_reasons = Counter(), Counter()
        equity_curve = [{"time": dual_time(start_ms), "balance": balance}]
        eligible_total = sum(
            1 for idx in range(start_i, end_i)
            if classify_session(int(close_times[idx])).get("is_executable_window")
            and not ((idx-start_i) % stride)
        )
        emit("ANALYSIS_START", eligible_checkpoints=eligible_total,
             checkpoint_minutes=checkpoint_minutes)
        progress_step = max(1, eligible_total // 100)
        i = start_i
        while i < end_i:
            cutoff = int(close_times[i])
            # Fast mode evaluates only configured time windows and every 15m.
            session = classify_session(cutoff)
            if not session.get("is_executable_window") or ((i-start_i) % stride):
                i += 1; continue
            hist_dm.cutoff = cutoff
            checkpoints += 1
            if checkpoints == 1 or checkpoints % progress_step == 0:
                elapsed = max(time.monotonic()-started_at, 0.001)
                rate = checkpoints/elapsed
                remaining = max(0, eligible_total-checkpoints)
                emit("ANALYSIS_PROGRESS", completed=checkpoints, total=eligible_total,
                     percent=round(checkpoints/max(eligible_total,1)*100,1),
                     eta_seconds=round(remaining/rate,1) if rate else None,
                     trades=len(trades), signals=signals)
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
            actionable_states = ("READY_NOW", "ORDER_READY")
            if not candidate or result["decision"]["state"] not in actionable_states:
                i += 1; continue
            signals += 1
            case_id = f"CASE-{signals:04d}-{symbol.replace('/', '')}-{cutoff}"
            pre_ohlc = {
                frame: self._historical_slice_at(datasets[frame], cutoff, limit)
                for frame, limit in ((tf, 500), ("15m", 400), ("4h", 300), ("1d", 260))
            }
            expiry = int(candidate["lifecycle"]["expires_at_ms"])
            fill_i = None
            search_last_i = i
            for j in range(i+1, end_i):  # strictly future candle only
                if close_times[j] > expiry: break
                search_last_i = j
                if entry_data["lows"][j] <= candidate["entry"] <= entry_data["highs"][j]:
                    fill_i = j; break
            if fill_i is None:
                no_fills += 1
                post_ohlc = self._slice(entry_data, i+1, search_last_i) if search_last_i > i else self._slice(entry_data, i, i)
                case_path = self._write_case_bundle(
                    trade_cases_dir, case_id, result, pre_ohlc, post_ohlc,
                    outcome={"classification": "ORDER_NOT_FILLED_BEFORE_EXPIRY",
                             "expiry_ms": expiry, "checked_future_candles": max(0, search_last_i-i)},
                    trade=None,
                )
                audit_cases.append({"case_id": case_id, "classification": "NO_FILL",
                                    "path": case_path, "audit_id": result.get("audit_id")})
                i += stride
                continue

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
            forensic_bars = max(1, round(24 * 60 / tf_minutes))
            forensic_end_i = min(end_i - 1, exit_i + forensic_bars)
            post_ohlc = self._slice(entry_data, i+1, forensic_end_i) if forensic_end_i > i else self._slice(entry_data, i, i)
            case_path = self._write_case_bundle(
                trade_cases_dir, case_id, result, pre_ohlc, post_ohlc,
                outcome=outcome, trade=trade,
            )
            trade["audit_bundle"] = case_path
            audit_cases.append({"case_id": case_id,
                                "classification": outcome.get("classification"),
                                "path": case_path, "audit_id": result.get("audit_id")})
            trades.append(trade)
            equity_curve.append({"time": trade["exit_time"], "balance": balance})
            i = max(i+1, exit_i+1)  # one position at a time on this symbol

        wins = sum(1 for t in trades if t["net_pnl"] > 0)
        losses = sum(1 for t in trades if t["net_pnl"] < 0)
        actionable_count = decision_counts.get("READY_NOW", 0) + decision_counts.get("ORDER_READY", 0)
        if not trades:
            zero_trade_diagnosis = {
                "verdict": "OVERFILTERING_SUSPECTED" if checkpoints >= 100 and actionable_count == 0 else "NO_FILLED_TRADES",
                "actionable_decisions": actionable_count,
                "signals_without_fill": no_fills,
                "top_reasons": dict(rejection_reasons.most_common(10)),
                "message_ar": (
                    "لم تمر أي خطة مكتملة من الفلتر؛ راجع أكثر شروط الرفض تكراراً. "
                    "هذه ليست نتيجة نجاح للبوت، بل إنذار over-filtering."
                    if actionable_count == 0 else
                    "وجد أوامر مكتملة لكن لم تُملأ قبل الإبطال/الانتهاء."
                ),
            }
        else:
            zero_trade_diagnosis = None
        report = {
            "id": report_id, "method": "STRICT_WALK_FORWARD_CLOSED_CANDLES",
            "lookahead_prevention": [
                "analysis slices contain close_time <= signal cutoff only",
                "entry can fill from the next candle only",
                "outcome candles are read only after the plan is frozen",
                "same-candle SL/TP ambiguity uses conservative ordering in simulator",
            ],
            "fast_mode": f"decision checkpoint every {checkpoint_minutes}m inside configured execution windows",
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
            "zero_trade_diagnosis": zero_trade_diagnosis,
            "trade_count": len(trades), "wins": wins, "losses": losses,
            "win_rate": round(wins/len(trades)*100,2) if trades else None,
            "average_r": round(sum(t["realized_r"] for t in trades)/len(trades),3) if trades else None,
            "equity_curve": equity_curve, "generated_at": dual_time(),
            "runtime_seconds": round(time.monotonic()-started_at, 2),
            "audit_bundle_dir": bundle_dir,
            "trade_cases_dir": trade_cases_dir,
            "audit_case_count": len(audit_cases),
            "audit_cases": audit_cases,
            "disclaimer": "Hypothetical simulation; not indicative of future performance.",
        }
        path = os.path.join(self.reports_dir, report["id"]+".json")
        bundle_report_path = os.path.join(bundle_dir, "report.json")
        bundle_zip = bundle_dir + ".zip"
        report["saved_to"] = path
        report["bundle_report"] = bundle_report_path
        report["bundle_zip"] = bundle_zip
        for output_path in (path, bundle_report_path):
            with open(output_path,"w",encoding="utf-8") as f:
                json.dump(report,f,ensure_ascii=False,indent=2,default=str)
        try:
            shutil.make_archive(bundle_dir, "zip", bundle_dir)
        except OSError as exc:
            report["bundle_zip_error"] = str(exc)
        emit("BACKTEST_DONE", trades=len(trades), wins=wins, losses=losses,
             final_balance=balance, report_id=report["id"], bundle_zip=bundle_zip)
        return report

    @staticmethod
    def _slice(data, first, last):
        return DataManager._slice_indices(data, first, last)

    @staticmethod
    def _historical_slice_at(data, cutoff_ms, limit):
        close_times = data.get("close_timestamps") or data.get("timestamps", [])
        last = bisect.bisect_right(close_times, cutoff_ms) - 1
        if last < 0:
            return None
        first = max(0, last - int(limit) + 1)
        return DataManager._slice_indices(data, first, last)

    @staticmethod
    def _json_bytes(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), default=str).encode("utf-8")

    @classmethod
    def _sha256(cls, value):
        return hashlib.sha256(cls._json_bytes(value)).hexdigest()

    @staticmethod
    def _git_commit():
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return None

    def _write_case_bundle(self, parent_dir, case_id, analysis, pre_ohlc,
                           post_ohlc, outcome, trade=None):
        """Write an immutable audit case for one signal/trade.

        It contains exactly what the bot knew at cutoff and a separate future
        block. Keeping the files separate makes accidental look-ahead visible.
        """
        case_dir = os.path.join(parent_dir, case_id)
        os.makedirs(case_dir, exist_ok=True)

        files = {}
        analysis_path = os.path.join(case_dir, "01_analysis_at_signal.json")
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
        files[os.path.basename(analysis_path)] = self._sha256(analysis)

        for frame, data in pre_ohlc.items():
            if not data:
                continue
            safe_frame = frame.replace("/", "_")
            name = f"02_ohlc_before_signal_{safe_frame}.json"
            path = os.path.join(case_dir, name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            files[name] = self._sha256(data)

        post_name = "03_ohlc_after_signal_execution_tf.json"
        with open(os.path.join(case_dir, post_name), "w", encoding="utf-8") as f:
            json.dump(post_ohlc, f, ensure_ascii=False, indent=2, default=str)
        files[post_name] = self._sha256(post_ohlc)

        outcome_doc = {
            "trade": trade,
            "outcome": outcome,
            "timeline": self._case_timeline(analysis, outcome, trade),
            "forensic_diagnosis": self._diagnose_case(analysis, post_ohlc, outcome, trade),
        }
        outcome_name = "04_outcome_and_management.json"
        with open(os.path.join(case_dir, outcome_name), "w", encoding="utf-8") as f:
            json.dump(outcome_doc, f, ensure_ascii=False, indent=2, default=str)
        files[outcome_name] = self._sha256(outcome_doc)

        candidate = analysis.get("candidate") or {}
        manifest = {
            "schema": "ICT_TRADE_AUDIT_CASE_V1",
            "case_id": case_id,
            "audit_id": analysis.get("audit_id"),
            "git_commit": self._git_commit(),
            "symbol": analysis.get("symbol"),
            "exchange": analysis.get("exchange"),
            "execution_timeframe": analysis.get("execution_timeframe"),
            "signal_cutoff": analysis.get("data_cutoff"),
            "decision": analysis.get("decision"),
            "model": candidate.get("model"),
            "entry": candidate.get("entry"),
            "stop_loss": candidate.get("stop_loss"),
            "targets": candidate.get("targets"),
            "classification": outcome.get("classification"),
            "separation_guarantee": {
                "before_files": "contain candle close times <= signal cutoff only",
                "after_file": "contains candles revealed only after plan freeze",
            },
            "sha256": files,
        }
        with open(os.path.join(case_dir, "00_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)

        md = self._case_markdown(manifest, analysis, outcome_doc)
        with open(os.path.join(case_dir, "README_AR.md"), "w", encoding="utf-8") as f:
            f.write(md)
        return case_dir

    @staticmethod
    def _diagnose_case(analysis, post_ohlc, outcome, trade):
        candidate = analysis.get("candidate") or {}
        entry = candidate.get("entry")
        stop = candidate.get("stop_loss")
        targets = candidate.get("targets") or []
        tp1 = targets[0].get("price") if targets else None
        side = candidate.get("side", "")
        if not all(isinstance(x, (int, float)) for x in (entry, stop, tp1)):
            return {"classification": "INSUFFICIENT_NUMERIC_PLAN"}
        risk = abs(entry - stop)
        highs = post_ohlc.get("highs", []) if post_ohlc else []
        lows = post_ohlc.get("lows", []) if post_ohlc else []
        is_long = "BUY" in side
        favorable = [h-entry for h in highs] if is_long else [entry-l for l in lows]
        adverse = [entry-l for l in lows] if is_long else [h-entry for h in highs]
        max_fav = max(favorable) if favorable else 0
        max_adv = max(adverse) if adverse else 0
        target_reached_anytime = any(h >= tp1 for h in highs) if is_long else any(l <= tp1 for l in lows)
        stopped = outcome.get("final_exit_reason") == "SL_HIT_BEFORE_TP1"
        stop_hunt_suspected = bool(stopped and target_reached_anytime)
        if stop_hunt_suspected:
            classification = "STOP_TOO_TIGHT_OR_STOP_HUNT_SUSPECTED"
            explanation = "ضُرب SL أولاً ثم وصل السعر TP1 خلال نافذة التحقيق اللاحقة؛ الاتجاه قد يكون صحيحاً لكن موضع SL يحتاج مراجعة."
        elif stopped:
            classification = "DIRECTION_OR_TIMING_FAILED"
            explanation = "ضُرب SL ولم يصل TP1 خلال 24 ساعة التحقيق؛ راجع Bias والتوقيت والمنطقة، لا الستوب وحده."
        elif outcome.get("tp1_hit"):
            classification = "THESIS_DELIVERED_AT_LEAST_TP1"
            explanation = "وصل السعر TP1؛ راجع جودة إدارة الجزء المتبقي والتريلينغ بشكل منفصل."
        elif outcome.get("classification") == "ORDER_NOT_FILLED_BEFORE_EXPIRY":
            classification = "NO_FILL_NOT_A_LOSS"
            explanation = "لم يلمس السعر Entry قبل انتهاء الخطة؛ هذه فرصة فائتة وليست خسارة."
        else:
            classification = "OPEN_OR_INCONCLUSIVE"
            explanation = "لم يُحسم المسار بشكل كافٍ ضمن النافذة المتاحة."
        return {
            "classification": classification,
            "explanation_ar": explanation,
            "risk_distance": risk,
            "intended_rr_to_tp1": round(abs(tp1-entry)/risk, 4) if risk else None,
            "max_favorable_move": round(max_fav, 8),
            "max_adverse_move": round(max_adv, 8),
            "mfe_r": round(max_fav/risk, 4) if risk else None,
            "mae_r": round(max_adv/risk, 4) if risk else None,
            "tp1_reached_anytime_in_24h_forensic_window": target_reached_anytime,
            "stopped_before_tp1": stopped,
            "stop_hunt_suspected": stop_hunt_suspected,
            "warning": "تشخيص سببي آلي قابل للمراجعة، وليس إثباتاً قطعياً لنية السوق.",
        }

    @staticmethod
    def _case_timeline(analysis, outcome, trade):
        candidate = analysis.get("candidate") or {}
        events = [{
            "event": "SIGNAL_FROZEN",
            "time": (analysis.get("data_cutoff") or {}).get("close"),
            "decision": analysis.get("decision"),
            "entry": candidate.get("entry"),
            "stop": candidate.get("stop_loss"),
            "targets": candidate.get("targets"),
        }]
        if trade:
            events.append({"event": "ENTRY_FILLED", "time": trade.get("entry_time"),
                           "price": trade.get("entry")})
        if outcome.get("tp1_hit"):
            events.append({"event": "TP1_HIT", "time": outcome.get("tp1_hit_time"),
                           "price": outcome.get("tp1_price")})
        for move in outcome.get("trail_history", []) or []:
            events.append({"event": move.get("reason", "TRAIL_MOVE"),
                           "candle_index": move.get("idx_from_start"),
                           "new_stop": move.get("new_sl")})
        events.append({"event": outcome.get("final_exit_reason", outcome.get("classification")),
                       "time": outcome.get("final_exit_time"),
                       "price": outcome.get("final_exit_price")})
        return events

    @staticmethod
    def _case_markdown(manifest, analysis, outcome_doc):
        candidate = analysis.get("candidate") or {}
        frame_lines = []
        for tf, frame in (analysis.get("frames") or {}).items():
            frame_lines.append(
                f"### {tf}\n- الدور: {frame.get('role_ar')}\n"
                f"- آخر إغلاق: {frame.get('last_close')}\n"
                f"- Bias anchor: {(frame.get('bias_anchor') or {}).get('anchor_direction')} "
                f"({(frame.get('bias_anchor') or {}).get('strength')})\n"
                + "\n".join(f"- {x}" for x in frame.get("explanation_ar", []))
            )
        conditions = "\n".join(
            f"- `{c.get('name')}`: **{c.get('status')}** — {c.get('detail')}"
            for c in candidate.get("conditions", [])
        ) or "- لا توجد شروط محفوظة"
        return f"""# ملف قضية الصفقة {manifest['case_id']}

## الهوية
- Audit ID: `{manifest.get('audit_id')}`
- Git commit: `{manifest.get('git_commit')}`
- الأصل: **{manifest.get('symbol')}**
- المنصة: **{manifest.get('exchange')}**
- فريم التنفيذ: **{manifest.get('execution_timeframe')}**
- التصنيف النهائي: **{manifest.get('classification')}**

## ما كان يعرفه البوت لحظة القرار
- القرار: `{json.dumps(analysis.get('decision'), ensure_ascii=False)}`
- التوقع الشرطي: `{json.dumps(analysis.get('expectation'), ensure_ascii=False)}`
- Entry: **{candidate.get('entry')}**
- SL: **{candidate.get('stop_loss')}**
- Targets: `{json.dumps(candidate.get('targets'), ensure_ascii=False)}`
- أساس الخطة: {candidate.get('basis')}

## تحليل الفريمات
{chr(10).join(frame_lines)}

## شروط نموذج الدخول
{conditions}

## تشخيص لماذا ربحت/خسرت
```json
{json.dumps(outcome_doc.get('forensic_diagnosis'), ensure_ascii=False, indent=2, default=str)}
```

## النتيجة وإدارة الصفقة
```json
{json.dumps(outcome_doc, ensure_ascii=False, indent=2, default=str)}
```

## فصفصة القرار الميكانيكية
```json
{json.dumps(analysis.get('decision_trace'), ensure_ascii=False, indent=2, default=str)}
```

## ملفات الدليل
- `00_manifest.json`: الهوية وSHA256.
- `01_analysis_at_signal.json`: جواب التحليل الكامل قبل المستقبل.
- `02_ohlc_before_signal_*.json`: OHLC كل فريم كما رآها البوت.
- `03_ohlc_after_signal_execution_tf.json`: المستقبل المفصول.
- `04_outcome_and_management.json`: الدخول، TP1، تحريك SL والخروج.

> لا يجوز تعديل ملفات OHLC ثم اعتبار النتيجة هي نفسها؛ قارن SHA256 في manifest.
"""

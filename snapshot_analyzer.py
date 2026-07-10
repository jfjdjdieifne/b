# -*- coding: utf-8 -*-
"""Fast, deterministic and fully explainable multi-timeframe snapshot.

This is deliberately separate from the slower LLM narrative pipeline.  It is
used by the Web/Telegram interfaces for immediate feedback and never invents
missing prices.  A candidate remains a watch-list item until timing, price and
lower-timeframe confirmation are all present.
"""
from __future__ import annotations

import math
import uuid
from typing import Any

from config import Config
from data_manager import DataManager, DataManagerError
from ict_entry_checklist_engine import evaluate_all_entry_models
from ict_math_engine import (
    compute_displacement,
    compute_mechanical_bias_anchor,
    detect_equal_highs_lows,
    detect_fair_value_gaps,
    detect_mss,
    detect_order_blocks,
)
from ict_sessions import classify_session
from setup_policy import setup_expiry
from user_utils import closed_candle_stamp, dual_time


FRAME_ROLES = {
    "1d": "الانحياز اليومي والهدف الكبير للسيولة (ليس فريم دخول)",
    "4h": "السياق والمناطق الهيكلية التي تؤيد أو تعارض اليومي",
    "15m": "خريطة السيولة والسحب والـFVG والهيكل داخل الجلسة",
    "1m": "تأكيد وتنفيذ دقيق؛ سريع وعالي الضجيج",
    "3m": "تأكيد وتنفيذ متوازن بين الدقة والضجيج",
    "5m": "تأكيد وتنفيذ؛ الخيار الافتراضي الأوضح للمبتدئ",
}

STATUS_AR = {
    True: "متحقق",
    False: "فاشل",
    "PENDING": "بانتظار التأكيد",
}


class SnapshotAnalyzer:
    def __init__(self, data_manager: DataManager | None = None):
        self.dm = data_manager or DataManager()

    def analyze(
        self, symbol="ETH/USDT", exchange="auto", execution_timeframe="5m",
        balance=100.0, risk_pct=1.0, tp1_allocation_pct=None,
    ) -> dict[str, Any]:
        symbol = self.dm.normalize_symbol(symbol)
        execution_tf = self.dm.normalize_timeframe(execution_timeframe)
        if execution_tf not in ("1m", "3m", "5m"):
            raise DataManagerError(
                "فريم التنفيذ يجب أن يكون 1m أو 3m أو 5m. البوت يحلل 1D/4H/15m تلقائياً."
            )
        exchange = self.dm.normalize_exchange(exchange)
        balance = float(balance)
        risk_pct = float(risk_pct)
        if balance <= 0 or not (0 < risk_pct <= 5):
            raise ValueError("رأس المال يجب أن يكون موجباً والمخاطرة أكبر من 0% وحتى 5%")
        tp1_allocation_pct = float(
            Config.TP1_ALLOCATION_PCT if tp1_allocation_pct is None else tp1_allocation_pct
        )
        if not 1 <= tp1_allocation_pct <= 100:
            raise ValueError("نسبة الإغلاق عند TP1 يجب أن تكون بين 1 و100%")

        audit_id = f"A-{dual_time()['timestamp_ms']}-{uuid.uuid4().hex[:6]}"
        limits = {execution_tf: 500, "15m": 400, "4h": 300, "1d": 260}
        data_by_tf: dict[str, dict] = {}
        reports: list[dict] = []

        # Resolve AUTO once from the execution feed, then keep the exact same
        # venue for every timeframe.  Cross-exchange candles are never mixed.
        entry = self.dm.get_ohlcv(
            symbol, execution_tf, limits[execution_tf], exchange=exchange,
            closed_only=True, allow_fallback=(exchange == "auto"),
        )
        reports.append(self.dm.get_last_fetch_report())
        if not entry:
            return self._data_error(audit_id, symbol, exchange, execution_tf, reports)
        resolved_exchange = entry["source"]
        data_by_tf[execution_tf] = entry

        for tf in ("15m", "4h", "1d"):
            data = self.dm.get_ohlcv(
                symbol, tf, limits[tf], exchange=resolved_exchange,
                closed_only=True, allow_fallback=False,
            )
            reports.append(self.dm.get_last_fetch_report())
            if not data:
                return self._data_error(audit_id, symbol, resolved_exchange, execution_tf, reports, missing=tf)
            data_by_tf[tf] = data

        frame_reports = {
            tf: self._analyze_frame(tf, data_by_tf[tf])
            for tf in ("1d", "4h", "15m", execution_tf)
        }
        daily_anchor = frame_reports["1d"]["bias_anchor"]
        h4_anchor = frame_reports["4h"]["bias_anchor"]
        daily_dir = daily_anchor.get("anchor_direction")
        h4_dir = h4_anchor.get("anchor_direction")

        if daily_dir in ("BULLISH", "BEARISH") and h4_dir == daily_dir:
            bias = daily_dir
            bias_state = "ALIGNED"
            bias_explanation = (
                f"اليومي و4 ساعات متفقان على {self._dir_ar(bias)}. هذا انحياز ميكانيكي "
                "قابل للمراجعة، وليس يقيناً ولا ادعاء بأنه رأي مايكل الشخصي."
            )
        elif daily_dir in ("BULLISH", "BEARISH") and h4_dir == "MIXED":
            bias = daily_dir
            bias_state = "DAILY_ONLY_H4_MIXED"
            bias_explanation = (
                f"اليومي يميل {self._dir_ar(bias)} لكن 4 ساعات مختلط؛ نعرض مراقبة فقط ولا دخول فوري."
            )
        else:
            bias = "UNCLEAR"
            bias_state = "CONFLICT_OR_UNKNOWN"
            bias_explanation = (
                f"لا يوجد اتفاق: Daily={daily_dir or 'UNKNOWN'}, 4H={h4_dir or 'UNKNOWN'}. "
                "لا يجوز إجبار BUY/SELL."
            )

        last_close_ms = entry["close_timestamps"][-1]
        session = classify_session(last_close_ms)
        session["timestamp"] = dual_time(last_close_ms)

        model_result = None
        if bias in ("BULLISH", "BEARISH"):
            model_result = evaluate_all_entry_models(
                entry,
                bias,
                lookback=100,
                htf_data_sources=[("Daily", data_by_tf["1d"]), ("4H", data_by_tf["4h"])],
                htf_major_data=data_by_tf["1d"],
            )

        candidate = self._candidate_report(
            model_result, bias, entry, frame_reports[execution_tf], session,
            balance, risk_pct, bias_state, tp1_allocation_pct,
        )
        decision = candidate.get("decision") if candidate else {
            "state": "NO_TRADE", "label_ar": "لا توجد صفقة موثقة الآن",
            "reason_ar": bias_explanation if bias == "UNCLEAR" else "لم يكتمل نموذج دخول صالح بالأرقام.",
        }

        return {
            "ok": True,
            "audit_id": audit_id,
            "analysis_kind": "DETERMINISTIC_CLOSED_CANDLES",
            "educational_only": True,
            "symbol": symbol,
            "requested_exchange": exchange,
            "exchange": resolved_exchange,
            "execution_timeframe": execution_tf,
            "timeframe_guide": [
                {"timeframe": tf, "role_ar": FRAME_ROLES[tf]}
                for tf in ("1d", "4h", "15m", execution_tf)
            ],
            "analysis_time": dual_time(),
            "data_cutoff": closed_candle_stamp(entry),
            "closed_candles_only": True,
            "frames": frame_reports,
            "bias": {
                "direction": bias,
                "state": bias_state,
                "explanation_ar": bias_explanation,
            },
            "session": session,
            "entry_models": self._summarize_models(model_result),
            "candidate": candidate,
            "decision": decision,
            "expectation": self._expectation(candidate, bias, entry["closes"][-1]),
            "decision_trace": self._decision_trace(
                frame_reports, bias, bias_state, session, model_result, candidate
            ),
            "data_fetch_reports": reports,
            "limitations_ar": [
                "النتيجة تحليل تقني آلي وليست ضماناً ولا نصيحة مالية.",
                "الانحياز اليومي يحتاج سياق أخبار/أصول مترابطة عند استعمال نموذج ICT الكامل؛ النسخة السريعة لا تختلق هذا السياق.",
                "لا تُحتسب انزلاقات التنفيذ والعمولات والسيولة الدفترية في هذه اللقطة.",
                "أي باك تست افتراضي يختلف عن التنفيذ الحقيقي، لذلك لا نعرض Win Rate غير موثق.",
            ],
        }

    def _analyze_frame(self, timeframe: str, data: dict) -> dict[str, Any]:
        displacement = compute_displacement(data, lookback=min(120, data["count"] - 1))
        fvgs = detect_fair_value_gaps(data, lookback=min(160, data["count"] - 1), require_displacement=True)
        obs = detect_order_blocks(data, lookback=min(160, data["count"] - 1))
        structure = detect_mss(data, swing_window=2)
        equal = detect_equal_highs_lows(data, lookback=min(180, data["count"] - 1))
        anchor = compute_mechanical_bias_anchor(data, lookback=min(120, data["count"] - 1))

        active_bull_fvgs = [x for x in fvgs["bullish_fvgs"] if x.get("filled_pct", 100) < 100][-3:]
        active_bear_fvgs = [x for x in fvgs["bearish_fvgs"] if x.get("filled_pct", 100) < 100][-3:]
        active_bull_obs = [x for x in obs["bullish_obs"] if not x.get("invalidated", False)][-3:]
        active_bear_obs = [x for x in obs["bearish_obs"] if not x.get("invalidated", False)][-3:]
        breaks = structure.get("breaks_found", [])[-5:]
        unswept_eqh = [x for x in equal["eqh_clusters"] if x.get("status") != "SWEPT"][:3]
        unswept_eql = [x for x in equal["eql_clusters"] if x.get("status") != "SWEPT"][:3]
        latest_break = breaks[-1] if breaks else None
        latest_disp = displacement.get("most_recent_displacement")

        facts = []
        if latest_break:
            facts.append(
                f"آخر إغلاق كسر مستوى {latest_break['broken_level']:.6g} باتجاه "
                f"{self._dir_ar(latest_break['direction'])} عند idx {latest_break['break_candle_index_from_end']}"
                + (" مع displacement" if latest_break.get("displacement_confirmed") else " بدون displacement مؤكد")
            )
        else:
            facts.append("لم يُرصد كسر إغلاق لآخر swing ضمن العينة")
        if latest_disp:
            facts.append(
                f"آخر displacement: {self._dir_ar(latest_disp['direction'])}، جسم/ATR={latest_disp['body_atr_ratio']}، "
                f"نسبة الجسم={latest_disp['body_pct']}% عند idx {latest_disp['index_from_end']}"
            )
        else:
            facts.append("لا displacement يحقق فلتر التنفيذ الحالي ضمن نافذة البحث")
        facts.append(
            f"FVG نشطة: صاعدة {len(active_bull_fvgs)} / هابطة {len(active_bear_fvgs)}؛ "
            f"OB غير مبطلة: صاعدة {len(active_bull_obs)} / هابطة {len(active_bear_obs)}"
        )
        facts.append(f"سيولة غير مسحوبة: EQH={len(unswept_eqh)}، EQL={len(unswept_eql)}")

        return {
            "timeframe": timeframe,
            "role_ar": FRAME_ROLES[timeframe],
            "source": data["source"],
            "candles": data["count"],
            "last_close": data["closes"][-1],
            "candle_cutoff": closed_candle_stamp(data),
            "bias_anchor": anchor,
            "latest_structural_breaks": breaks,
            "latest_displacement": latest_disp,
            "active_fvgs": {"bullish": active_bull_fvgs, "bearish": active_bear_fvgs},
            "active_order_blocks": {"bullish": active_bull_obs, "bearish": active_bear_obs},
            "unswept_liquidity": {"equal_highs": unswept_eqh, "equal_lows": unswept_eql},
            "explanation_ar": facts,
        }

    def _candidate_report(self, model_result, bias, entry, entry_frame, session, balance, risk_pct, bias_state, tp1_allocation_pct):
        chosen = (model_result or {}).get("chosen_model")
        if not chosen or not chosen.get("plan"):
            return None
        plan = chosen["plan"]
        side = plan.get("direction", "")
        entry_price = float(plan["entry"])
        stop = float(plan["stop_loss"])
        tp1_obj = plan.get("tp1") or {"price": plan.get("tp"), "kind": "STRUCTURAL_TARGET", "rr": plan.get("rr")}
        tp1 = float(tp1_obj["price"])
        tp2_obj = plan.get("tp2") or {"mode": "OPEN_TRAILING", "detail": "لا يوجد TP2 موثق"}
        risk_per_unit = abs(entry_price - stop)
        risk_usd = balance * risk_pct / 100
        qty = risk_usd / risk_per_unit if risk_per_unit else 0
        position_value = qty * entry_price

        recent_breaks = entry_frame.get("latest_structural_breaks", [])
        aligned_recent = [
            b for b in recent_breaks
            if b.get("direction") == bias
            and b.get("displacement_confirmed")
            and b.get("break_candle_index_from_end", -999) >= -12
        ]
        ltf_confirmed = bool(aligned_recent)
        current = entry["closes"][-1]
        is_long = "BUY" in side
        # A pending target already behind current market has already been
        # delivered. Keeping it creates the TARGET_REACHED_WITHOUT_ENTRY loop.
        target_still_ahead = (
            tp1 > max(entry_price, current) if is_long
            else tp1 < min(entry_price, current)
        )
        if not target_still_ahead:
            return None
        # Correct order semantics: pullbacks use LIMIT; breakout entries use STOP.
        if is_long:
            side = "BUY_LIMIT" if entry_price <= current else "BUY_STOP"
        else:
            side = "SELL_LIMIT" if entry_price >= current else "SELL_STOP"
        zone_tolerance = max(entry_price * 0.0005, risk_per_unit * 0.1)
        price_at_zone = abs(current - entry_price) <= zone_tolerance
        timing_ok = bool(session.get("is_executable_window"))
        structure_ok = bias_state == "ALIGNED"

        # Three distinct states. ORDER_READY is not an unconfirmed watchlist:
        # every model/structure/time condition passed and a real LIMIT/STOP can
        # be frozen now, but only a later candle may fill it. This distinction
        # was missing and caused the walk-forward test to discard all valid
        # pending orders, often producing zero trades.
        confirmations_ok = (
            chosen.get("status") == "READY" and structure_ok
            and ltf_confirmed and timing_ok
        )
        if confirmations_ok and price_at_zone:
            state = "READY_NOW"
            label = "إعداد مكتمل والسعر عند منطقة التنفيذ"
            reason = "الانحياز متفق، التأكيد الهيكلي مكتمل، التوقيت صالح، والسعر عند المنطقة."
        elif confirmations_ok:
            state = "ORDER_READY"
            label = "أمر معلّق جاهز — ينتظر السعر فقط"
            reason = (
                f"كل شروط النموذج مكتملة. يُجمّد {side} عند {entry_price} الآن، "
                "ولا يُعتبر دخولاً إلا إذا لمست شمعة لاحقة السعر قبل الإبطال/الانتهاء."
            )
        else:
            state = "WATCHLIST"
            label = "مراقبة فقط — التأكيد غير مكتمل"
            missing = []
            if chosen.get("status") != "READY": missing.append("شروط النموذج ما زالت Pending")
            if not structure_ok: missing.append("4H غير متفق بالكامل مع Daily")
            if not ltf_confirmed: missing.append("لا MSS/BOS حديث مع displacement على فريم التنفيذ")
            if not timing_ok: missing.append("خارج نافذة التنفيذ لهذا النموذج")
            reason = "؛ ".join(missing) or "تحتاج مراجعة يدوية"

        lifecycle = setup_expiry(
            entry["close_timestamps"][-1], chosen["model"], entry["timeframe"]
        )
        targets = [{
            "name": "TP1", "price": tp1, "allocation_pct": tp1_allocation_pct,
            "kind": tp1_obj.get("kind"), "rr": tp1_obj.get("rr"),
            "detail": tp1_obj.get("detail"),
        }]
        if (tp1_allocation_pct < 100
                and tp2_obj.get("mode") == "TARGET" and tp2_obj.get("price")):
            targets.append({
                "name": "TP2", "price": float(tp2_obj["price"]), "allocation_pct": 100 - tp1_allocation_pct,
                "kind": tp2_obj.get("kind"), "rr": tp2_obj.get("rr"),
                "source": tp2_obj.get("source"), "confluences": tp2_obj.get("confluences", []),
                "detail": tp2_obj.get("detail"),
            })
            runner = None
        elif tp1_allocation_pct < 100:
            runner = {
                "allocation_pct": 100 - tp1_allocation_pct,
                "mode": "STRUCTURE_TRAIL_AFTER_TP1",
                "detail_ar": "لا يوجد هدف ثانٍ قوي كفاية؛ بعد TP1 يُنقل الستوب حسب الخطة ويُلاحق HL/LH، بلا اختراع رقم.",
            }
        else:
            runner = None

        return {
            "model": chosen["model"],
            "model_status": chosen["status"],
            "decision": {"state": state, "label_ar": label, "reason_ar": reason},
            "side": side,
            "entry": entry_price,
            "stop_loss": stop,
            "targets": targets,
            "runner": runner,
            "risk": {
                "balance": balance, "risk_pct": risk_pct, "risk_usd": round(risk_usd, 4),
                "risk_per_unit": round(risk_per_unit, 8), "quantity": round(qty, 8),
                "position_value": round(position_value, 4),
                "leverage_warning": position_value > balance,
            },
            "checks": {
                "daily_h4_aligned": structure_ok,
                "ltf_displacement_break_confirmed": ltf_confirmed,
                "price_at_entry_zone": price_at_zone,
                "executable_session": timing_ok,
                "closed_candles_only": True,
            },
            "conditions": [
                {**c, "status_ar": STATUS_AR.get(c.get("status"), str(c.get("status")))}
                for c in chosen.get("conditions", [])
            ],
            "basis": plan.get("basis"),
            "stop_rationale": plan.get("stop_rationale"),
            "lifecycle": lifecycle,
            "tracking_payload": {
                "symbol": entry["symbol"], "exchange": entry["source"],
                "timeframe": entry["timeframe"], "model": chosen["model"], "side": side,
                "entry": entry_price, "stop_loss": stop,
                "tp1": tp1, "tp2": tp2_obj.get("price") if tp2_obj.get("mode") == "TARGET" else None,
                "quantity": round(qty, 8), "risk_usd": round(risk_usd, 4),
                "tp1_allocation_pct": tp1_allocation_pct,
                "stop_rationale": plan.get("stop_rationale"),
                "post_tp1_stop_policy": Config.POST_TP1_STOP_POLICY,
                "expires_at_ms": lifecycle["expires_at_ms"],
                "activation_allowed": state in ("READY_NOW", "ORDER_READY"),
                "status": "pending_entry" if state in ("READY_NOW", "ORDER_READY") else "watchlist",
            },
        }

    @staticmethod
    def _decision_trace(frames, bias, bias_state, session, model_result, candidate):
        trace = []
        for tf, frame in frames.items():
            anchor = frame.get("bias_anchor", {})
            trace.append({
                "step": f"DATA_AND_STRUCTURE_{tf}",
                "input": {"source": frame.get("source"), "candles": frame.get("candles"),
                          "last_close": frame.get("last_close")},
                "output": {"anchor": anchor.get("anchor_direction"), "strength": anchor.get("strength"),
                           "last_breaks": frame.get("latest_structural_breaks"),
                           "displacement": frame.get("latest_displacement")},
                "basis": "closed OHLC candles only; every break includes level/index/displacement flag",
            })
        trace.append({
            "step": "HTF_BIAS_CROSSCHECK",
            "input": {"daily": frames["1d"]["bias_anchor"], "h4": frames["4h"]["bias_anchor"]},
            "output": {"bias": bias, "state": bias_state},
            "basis": "directional plan requires Daily/H4 agreement; mixed context is disclosed",
        })
        trace.append({
            "step": "TIME_GATE", "input": session.get("timestamp"),
            "output": {"session": session.get("session"), "eligible": session.get("is_executable_window")},
            "basis": "configured time-model window; clock alone is never an entry",
        })
        for model in (model_result or {}).get("all_models", []):
            trace.append({
                "step": model.get("model"), "output": model.get("status"),
                "conditions": model.get("conditions", []),
                "basis": "named model conditions evaluated independently; no generic fallback trade",
            })
        if candidate:
            trace.append({
                "step": "PLAN_AND_TARGETS",
                "input": {"entry": candidate.get("entry"), "stop": candidate.get("stop_loss")},
                "output": {"stop_rationale": candidate.get("stop_rationale"),
                           "targets": candidate.get("targets"), "runner": candidate.get("runner"),
                           "lifecycle": candidate.get("lifecycle")},
                "basis": "TP1 active unswept level; TP2 needs confluence + horizon compatibility",
            })
        return trace

    @staticmethod
    def _expectation(candidate, bias, current_price):
        if not candidate:
            return {
                "state": "WAIT_FOR_HTF_ALIGNMENT",
                "current_price": current_price,
                "expects_ar": "لا يوجد مسار سعري مؤهل الآن؛ ننتظر اتفاق Daily و4H ثم نموذج دخول كامل.",
                "waits_for": ["Daily/4H alignment", "named setup with displacement and active zone"],
                "invalidation": None,
            }
        checks = candidate.get("checks", {})
        waits = []
        if not checks.get("ltf_displacement_break_confirmed"):
            waits.append("إغلاق كسر حديث باتجاه الانحياز مع displacement على فريم التنفيذ")
        if not checks.get("price_at_entry_zone"):
            waits.append(f"عودة السعر إلى منطقة الدخول {candidate['entry']}")
        if not checks.get("executable_session"):
            waits.append("دخول نافذة توقيت النموذج قبل انتهاء الصلاحية")
        first_target = candidate["targets"][0]["price"]
        return {
            "state": "READY_PATH" if not waits else "WAIT_CONFIRMATION",
            "current_price": current_price,
            "direction": bias,
            "expects_ar": (
                f"إذا اكتملت الشروط، السيناريو هو تفاعل من {candidate['entry']} مع إبطال عند "
                f"{candidate['stop_loss']}، ثم أقرب هدف نشط {first_target}. هذه خريطة شرطية لا تنبؤ مضمون."
            ),
            "waits_for": waits,
            "entry": candidate["entry"], "invalidation": candidate["stop_loss"],
            "tp1": first_target,
            "expires_at": candidate.get("lifecycle", {}).get("expires_at"),
        }

    @staticmethod
    def _summarize_models(model_result):
        if not model_result:
            return [{
                "model": "NOT_EVALUATED", "status": "BIAS_UNCLEAR",
                "failed": ["Daily and 4H must align before entry models are evaluated"],
                "pending": [],
            }]
        return [{
            "model": r.get("model"), "status": r.get("status"),
            "failed": [c.get("name") for c in r.get("conditions", []) if c.get("status") is False],
            "pending": [c.get("name") for c in r.get("conditions", []) if c.get("status") == "PENDING"],
        } for r in model_result.get("all_models", [])]

    def _data_error(self, audit_id, symbol, exchange, execution_tf, reports, missing=None):
        return {
            "ok": False,
            "audit_id": audit_id,
            "error_code": "MARKET_DATA_UNAVAILABLE",
            "error_ar": (
                f"فشل جلب شموع مغلقة لفريم {missing or execution_tf} من المنصة المختارة. "
                "لم يبدّل البوت الفريم ولم يخلط بيانات منصة أخرى بصمت."
            ),
            "symbol": symbol,
            "exchange": exchange,
            "execution_timeframe": execution_tf,
            "analysis_time": dual_time(),
            "data_fetch_reports": reports,
        }

    @staticmethod
    def _dir_ar(value):
        return {"BULLISH": "صاعد", "BEARISH": "هابط", "UP": "صاعد", "DOWN": "هابط"}.get(value, value)

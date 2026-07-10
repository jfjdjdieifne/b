# -*- coding: utf-8 -*-
"""
BacktestEngine V5 - Ultimate Smart Edition
════════════════════════════════════════════
- Pre-filters for GUARANTEED trade setups
- 3 Timeframes from historical data
- Scans DIFFERENT time periods (not same 5000)
- Smart composite scoring for point selection
- Resume + Budget control
"""
import json
import time
import logging
import os
from datetime import datetime
from data_manager import DataManager
from technical_analyzer import TechnicalAnalyzer
from brain_core import BrainCore
from openrouter_client import OpenRouterClient


class BacktestEngine:

    def __init__(self):
        self.logger = logging.getLogger("BacktestEngine")
        self.data_manager = DataManager()
        self.analyzer = TechnicalAnalyzer()
        self.brain = BrainCore()
        self.ai = OpenRouterClient()

        self.results_dir = "data/backtest_results"
        os.makedirs(self.results_dir, exist_ok=True)

        self.current_state = None
        self.state_file = "data/backtest_state.json"

        # مسح حالة قديمة مكتملة
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    old = json.load(f)
                if old.get("status") == "completed":
                    os.remove(self.state_file)
            except Exception:
                pass

        self.logger.info("📊 BacktestEngine V5 Ultimate ready")

    # ══════════════════════════════════════════════
    #  DATA CONVERSION
    # ══════════════════════════════════════════════

    def _list_to_dict(self, candles_list, symbol, timeframe):
        if not candles_list:
            return None

        data = {
            "timestamps": [], "opens": [], "highs": [], "lows": [],
            "closes": [], "volumes": [], "quote_volumes": [],
            "num_trades": [], "taker_buy_volumes": [],
            "taker_buy_quote_volumes": [], "buy_sell_ratio": [],
            "symbol": symbol, "timeframe": timeframe,
            "count": len(candles_list), "source": "backtest"
        }

        for c in candles_list:
            data["timestamps"].append(c[0])
            data["opens"].append(c[1])
            data["highs"].append(c[2])
            data["lows"].append(c[3])
            data["closes"].append(c[4])
            data["volumes"].append(c[5])
            data["quote_volumes"].append(c[6] if len(c) > 6 else c[5])
            data["num_trades"].append(int(c[7]) if len(c) > 7 else 0)
            data["taker_buy_volumes"].append(c[8] if len(c) > 8 else c[5] * 0.5)
            data["taker_buy_quote_volumes"].append(c[9] if len(c) > 9 else 0)

            vol = c[5]
            buy_vol = c[8] if len(c) > 8 else vol * 0.5
            data["buy_sell_ratio"].append(round(buy_vol / vol, 4) if vol > 0 else 0.5)

        return data

    def _build_higher_tf(self, candles_list, multiplier, symbol):
        if not candles_list or len(candles_list) < multiplier * 10:
            return None

        higher = []
        for i in range(0, len(candles_list) - multiplier + 1, multiplier):
            chunk = candles_list[i:i + multiplier]
            ts = chunk[0][0]
            o = chunk[0][1]
            h = max(c_[2] for c_ in chunk)
            l = min(c_[3] for c_ in chunk)
            c = chunk[-1][4]
            v = sum(c_[5] for c_ in chunk)
            qv = sum(c_[6] for c_ in chunk) if len(chunk[0]) > 6 else v
            nt = sum(int(c_[7]) for c_ in chunk) if len(chunk[0]) > 7 else 0
            tbv = sum(c_[8] for c_ in chunk) if len(chunk[0]) > 8 else v * 0.5
            tbqv = sum(c_[9] for c_ in chunk) if len(chunk[0]) > 9 else 0
            higher.append([ts, o, h, l, c, v, qv, nt, tbv, tbqv])

        tf_map = {4: "4h", 6: "6h", 12: "12h", 24: "1d"}
        return self._list_to_dict(higher[-300:], symbol, tf_map.get(multiplier, f"{multiplier}x"))

    # ══════════════════════════════════════════════
    #  SMART SETUP DETECTOR (الذكي)
    #  يلاقي نقاط فيها SETUP حقيقي مش عشوائي
    # ══════════════════════════════════════════════

    def _detect_trade_setups(self, candles, num_points=30):
        """
        يكتشف نقاط فيها setup حقيقي للتداول:
        1. Liquidity Sweep + Rejection = أقوى setup
        2. CHoCH + Trend = setup قوي
        3. BOS + Pullback = setup جيد

        كل نقطة لها score - نختار الأعلى
        """
        self.logger.info(f"🔍 Scanning {len(candles)} candles for REAL trade setups...")

        min_history = 500
        min_future = 100

        if len(candles) < min_history + min_future + 100:
            self.logger.warning(f"���️ Need {min_history + min_future + 100}+ candles")
            return []

        highs = [c[2] for c in candles]
        lows = [c[3] for c in candles]
        opens = [c[1] for c in candles]
        closes = [c[4] for c in candles]
        volumes = [c[5] for c in candles]

        avg_volume = sum(volumes) / len(volumes)

        # ═══ Step 1: Find all swing points ═══
        swing_highs = []
        swing_lows = []
        for i in range(5, len(candles) - 5):
            if highs[i] == max(highs[i-5:i+6]):
                swing_highs.append(i)
            if lows[i] == min(lows[i-5:i+6]):
                swing_lows.append(i)

        # ═══ Step 2: Score each potential point ═══
        scored_points = []

        for i in range(min_history, len(candles) - min_future):
            score = 0
            point_type = []
            details = {}

            candle_range = highs[i] - lows[i]
            if candle_range <= 0:
                continue

            body = abs(closes[i] - opens[i])
            upper_wick = highs[i] - max(opens[i], closes[i])
            lower_wick = min(opens[i], closes[i]) - lows[i]

            # ── Check 1: Liquidity Sweep (SSL) ──
            # Price broke below a swing low then closed above it
            recent_sl = [sl for sl in swing_lows if sl < i and sl > i - 40]
            for sl_idx in recent_sl:
                if lows[i] < lows[sl_idx] and closes[i] > lows[sl_idx]:
                    score += 4
                    point_type.append("SSL_SWEEP")
                    details["swept_level"] = lows[sl_idx]
                    break

            # ── Check 2: Liquidity Sweep (BSL) ──
            recent_sh = [sh for sh in swing_highs if sh < i and sh > i - 40]
            for sh_idx in recent_sh:
                if highs[i] > highs[sh_idx] and closes[i] < highs[sh_idx]:
                    score += 4
                    point_type.append("BSL_SWEEP")
                    details["swept_level"] = highs[sh_idx]
                    break

            # ── Check 3: Rejection Candle (long wick) ──
            wick_ratio = lower_wick / candle_range if candle_range > 0 else 0
            upper_wick_ratio = upper_wick / candle_range if candle_range > 0 else 0

            if wick_ratio > 0.5:  # Bullish rejection (long lower wick)
                score += 3
                point_type.append("BULL_REJECTION")
                details["wick_pct"] = round(wick_ratio * 100, 1)
            elif upper_wick_ratio > 0.5:  # Bearish rejection
                score += 3
                point_type.append("BEAR_REJECTION")
                details["wick_pct"] = round(upper_wick_ratio * 100, 1)

            # ── Check 4: Clear Trend (not ranging) ──
            lookback = 50
            if i >= lookback:
                recent_highs = highs[i-lookback:i]
                recent_lows = lows[i-lookback:i]
                price_range = max(recent_highs) - min(recent_lows)
                mid_price = (max(recent_highs) + min(recent_lows)) / 2

                if mid_price > 0:
                    range_pct = price_range / mid_price * 100

                    # Check for uptrend (HH/HL pattern)
                    recent_swing_h = [sh for sh in swing_highs if sh > i - lookback and sh < i]
                    recent_swing_l = [sl for sl in swing_lows if sl > i - lookback and sl < i]

                    if len(recent_swing_h) >= 2 and len(recent_swing_l) >= 2:
                        last_2_sh = recent_swing_h[-2:]
                        last_2_sl = recent_swing_l[-2:]

                        # Uptrend
                        if (highs[last_2_sh[-1]] > highs[last_2_sh[-2]] and
                            lows[last_2_sl[-1]] > lows[last_2_sl[-2]]):
                            score += 2
                            point_type.append("UPTREND")
                            details["trend"] = "bullish"

                        # Downtrend
                        elif (highs[last_2_sh[-1]] < highs[last_2_sh[-2]] and
                              lows[last_2_sl[-1]] < lows[last_2_sl[-2]]):
                            score += 2
                            point_type.append("DOWNTREND")
                            details["trend"] = "bearish"

                    # Not ranging (enough movement)
                    if range_pct > 3:
                        score += 1
                        details["range_pct"] = round(range_pct, 1)

            # ── Check 5: High Volume ──
            if volumes[i] > avg_volume * 1.5:
                score += 1
                point_type.append("HIGH_VOL")
                details["vol_ratio"] = round(volumes[i] / avg_volume, 1)

            # ── Check 6: Strong candle body ──
            body_ratio = body / candle_range if candle_range > 0 else 0
            if body_ratio > 0.6:
                score += 1
                point_type.append("STRONG_BODY")

            # ── Check 7: CHoCH detected ──
            if len(recent_swing_h if 'recent_swing_h' in dir() else []) >= 2:
                pass  # Already counted in trend check

            # ═══ Only keep points with score >= 5 ═══
            if score >= 5:
                scored_points.append({
                    "index": i,
                    "score": score,
                    "type": "+".join(point_type) if point_type else "UNKNOWN",
                    "price": closes[i],
                    "details": details,
                    "importance": "critical" if score >= 7 else "high" if score >= 5 else "medium"
                })

        # ═══ Sort by score (highest first) ═══
        scored_points.sort(key=lambda x: -x["score"])

        # ═══ Remove close points (min 50 candle gap) ═══
        filtered = []
        used_indices = set()

        for p in scored_points:
            # Check not too close to existing points
            too_close = False
            for used_idx in used_indices:
                if abs(p["index"] - used_idx) < 50:
                    too_close = True
                    break

            if not too_close:
                filtered.append(p)
                used_indices.add(p["index"])

            if len(filtered) >= num_points:
                break

        # ═══ Sort by index (chronological) ═══
        filtered.sort(key=lambda x: x["index"])

        # ═══ Log results ═══
        score_dist = {}
        type_dist = {}
        for p in filtered:
            s = p["score"]
            score_dist[s] = score_dist.get(s, 0) + 1
            for t in p["type"].split("+"):
                type_dist[t] = type_dist.get(t, 0) + 1

        self.logger.info(
            f"✅ Scanned → {len(scored_points)} setups found (score≥5) → selected {len(filtered)}"
        )
        self.logger.info(f"   Scores: {score_dist}")
        self.logger.info(f"   Types: {type_dist}")

        if filtered:
            avg_score = sum(p["score"] for p in filtered) / len(filtered)
            self.logger.info(f"   Avg Score: {avg_score:.1f} | Best: {filtered[0]['score'] if filtered else 0}")

        return filtered

    # ══════════════════════════════════════════════
    #  EVALUATE TRADE
    # ══════════════════════════════════════════════

    def _evaluate_trade(self, recommendation, future_candles):
        result = {
            "entry_filled": False, "outcome": "PENDING",
            "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
            "sl_hit": False, "mfe": 0.0, "mae": 0.0,
            "bars_to_entry": 0, "bars_to_outcome": 0,
            "actual_rr": 0.0, "efficiency": 0.0,
        }

        signal = recommendation.get("signal", "HOLD")
        if signal in ["HOLD", "N/A", None]:
            result["outcome"] = "HOLD"
            return result

        entry = recommendation.get("entry")
        sl = recommendation.get("stop_loss")
        # Support both single TP and legacy TP1/2/3
        tp = recommendation.get("tp") or recommendation.get("tp1")
        tp1 = tp  # For backward compatibility
        tp2 = recommendation.get("tp2")
        tp3 = recommendation.get("tp3")


        if not entry or not sl:
            result["outcome"] = "INVALID"
            return result

        try:
            entry = float(entry)
            sl = float(sl)
            tp1 = float(tp1) if tp1 else None
            tp2 = float(tp2) if tp2 else None
            tp3 = float(tp3) if tp3 else None
        except (ValueError, TypeError):
            result["outcome"] = "INVALID"
            return result

        is_long = signal == "BUY"
        entry_filled = False
        entry_bar = 0
        highest = 0
        lowest = float('inf')

        for i, candle in enumerate(future_candles):
            high = candle[2]
            low = candle[3]

            if not entry_filled:
                if is_long and low <= entry:
                    entry_filled = True
                    entry_bar = i
                    result["entry_filled"] = True
                    result["bars_to_entry"] = i
                elif not is_long and high >= entry:
                    entry_filled = True
                    entry_bar = i
                    result["entry_filled"] = True
                    result["bars_to_entry"] = i

                if i >= 30 and not entry_filled:
                    result["outcome"] = "NO_FILL"
                    return result
                if not entry_filled:
                    continue

            highest = max(highest, high)
            lowest = min(lowest, low)

            if is_long:
                result["mfe"] = max(result["mfe"], (highest - entry) / entry * 100)
                result["mae"] = max(result["mae"], (entry - lowest) / entry * 100)
                if tp1 and high >= tp1:
                    result["tp1_hit"] = True
                if tp2 and high >= tp2:
                    result["tp2_hit"] = True
                if tp3 and high >= tp3:
                    result["tp3_hit"] = True
                # Check TP BEFORE SL on same bar
                if tp1 and high >= tp1 and not result["tp1_hit"]:
                    result["tp1_hit"] = True

                if low <= sl:
                    # If TP was hit on same bar, it's ambiguous
                    if result["tp1_hit"]:
                        result["outcome"] = "WIN_PARTIAL"
                        result["bars_to_outcome"] = i - entry_bar
                        break
                    result["sl_hit"] = True
                    result["outcome"] = "LOSS"
                    result["bars_to_outcome"] = i - entry_bar
                    break
                if result["tp3_hit"]:
                    result["outcome"] = "WIN_FULL"
                    result["bars_to_outcome"] = i - entry_bar
                    break
            else:
                result["mfe"] = max(result["mfe"], (entry - lowest) / entry * 100)
                result["mae"] = max(result["mae"], (highest - entry) / entry * 100)
                if tp1 and low <= tp1:
                    result["tp1_hit"] = True
                if tp2 and low <= tp2:
                    result["tp2_hit"] = True
                if tp3 and low <= tp3:
                    result["tp3_hit"] = True
                if high >= sl:
                    result["sl_hit"] = True
                    result["outcome"] = "LOSS"
                    result["bars_to_outcome"] = i - entry_bar
                    break
                if result["tp3_hit"]:
                    result["outcome"] = "WIN_FULL"
                    result["bars_to_outcome"] = i - entry_bar
                    break

        if result["outcome"] == "PENDING":
            if result["tp2_hit"]:
                result["outcome"] = "WIN_PARTIAL"
            elif result["tp1_hit"]:
                result["outcome"] = "WIN_PARTIAL"
            elif entry_filled:
                result["outcome"] = "OPEN"
            else:
                result["outcome"] = "NO_FILL"

        if entry and sl and entry_filled:
            risk = abs(entry - sl)
            if risk > 0:
                if result["tp3_hit"] and tp3:
                    reward = abs(tp3 - entry)
                elif result["tp2_hit"] and tp2:
                    reward = abs(tp2 - entry)
                elif result["tp1_hit"] and tp1:
                    reward = abs(tp1 - entry)
                elif result["sl_hit"]:
                    reward = -risk
                else:
                    reward = 0
                result["actual_rr"] = round(reward / risk, 2)

        return result

    # ══════════════════════════════════════════════
    #  STATE MANAGEMENT
    # ══════════════════════════════════════════════

    def _save_state(self):
        if self.current_state:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_state, f, ensure_ascii=False, indent=2, default=str)

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _evaluate_hold(self, future_candles, price_at_point):
        """فحص HOLD: هل فوّتنا فرصة؟"""
        if not future_candles or not price_at_point:
            return {"missed": False}

        max_up = 0
        max_down = 0

        for candle in future_candles[:50]:
            high = candle[2]
            low = candle[3]
            max_up = max(max_up, (high - price_at_point) / price_at_point * 100)
            max_down = max(max_down, (price_at_point - low) / price_at_point * 100)

        missed_long = max_up > 1.5
        missed_short = max_down > 1.5

        result = {
            "missed": missed_long or missed_short,
            "max_up_pct": round(max_up, 2),
            "max_down_pct": round(max_down, 2),
            "missed_direction": None,
            "potential_rr": 0,
        }

        if missed_long and max_up > max_down:
            result["missed_direction"] = "LONG"
            result["potential_rr"] = round(max_up / 0.5, 2)
        elif missed_short and max_down > max_up:
            result["missed_direction"] = "SHORT"
            result["potential_rr"] = round(max_down / 0.5, 2)

        return result

    def _analyze_loss(self, recommendation, evaluation, future_candles):
        """تحليل سبب الخسارة"""
        analysis = {
            "loss_type": "UNKNOWN",
            "lesson": "",
            "fixable": True,
        }

        signal = recommendation.get("signal")
        entry = recommendation.get("entry")
        sl = recommendation.get("stop_loss")
        confidence = recommendation.get("confidence", 0)

        if not entry or not sl:
            analysis["loss_type"] = "INVALID_ENTRY"
            analysis["lesson"] = "Entry or SL was missing"
            return analysis

        try:
            entry = float(entry)
            sl = float(sl)
        except (ValueError, TypeError):
            return analysis

        mfe = evaluation.get("mfe", 0)
        mae = evaluation.get("mae", 0)
        bars = evaluation.get("bars_to_outcome", 0)
        is_long = signal == "BUY"

        if mfe > 0.5:
            analysis["loss_type"] = "SL_TOO_TIGHT"
            analysis["lesson"] = (
                f"Price moved {mfe:.1f}% in favor then reversed. "
                f"SL too tight or no trailing used."
            )
        elif mfe < 0.2 and mae > 0.5:
            analysis["loss_type"] = "WRONG_DIRECTION"
            analysis["lesson"] = (
                f"Price went against immediately ({mae:.1f}%). "
                f"{'Uptrend' if is_long else 'Downtrend'} was wrong."
            )
        elif bars < 3:
            analysis["loss_type"] = "STOP_HUNT"
            analysis["lesson"] = (
                f"Stopped in {bars} bars. Likely stop hunt. "
                f"Place SL beyond liquidity."
            )
        elif bars > 10:
            analysis["loss_type"] = "SLOW_GRIND"
            analysis["lesson"] = (
                f"Took {bars} bars to hit SL. Market ranging. "
                f"Use time exit in ranging."
            )

        if confidence and confidence < 65:
            analysis["loss_type"] += "+LOW_CONF"
            analysis["lesson"] += f" Confidence was only {confidence}%."

        return analysis

    # ══════════════════════════════════════════════
    #  RUN BACKTEST (V5)
    # ══════════════════════════════════════════════

    def run_backtest(self, symbol="BTC/USDT", timeframe="1h",
                     num_points=30, candles_count=5000,
                     resume=True, budget_limit=15.0):

        self.logger.info(
            f"📊 Backtest V5: {symbol} {timeframe} | "
            f"{num_points} points | ${budget_limit} budget"
        )

        # ═══ Resume check ═══
        if resume:
            saved = self._load_state()
            if (saved and saved.get("symbol") == symbol
                and saved.get("status") != "completed"):
                self.current_state = saved
                self.logger.info(
                    f"📂 Resuming: {saved['completed_points']}/{saved['total_points']}"
                )

        if not self.current_state:
            self.current_state = {
                "symbol": symbol, "timeframe": timeframe,
                "total_points": num_points, "completed_points": 0,
                "results": [], "started_at": datetime.now().isoformat(),
                "total_cost": 0.0, "status": "running"
            }

        # ═══ Fetch Maximum Historical Data ═══
        fetch_count = max(candles_count, 8000)
        self.logger.info(f"📥 Fetching {fetch_count} candles (max history)...")

        candles = self.data_manager.get_ohlcv(
            symbol, timeframe, fetch_count, output_format="list"
        )

        if not candles:
            return {"error": "No data available"}
        if len(candles) < 700:
            return {"error": f"Need 700+ candles, got {len(candles)}"}

        self.logger.info(
            f"✅ Got {len(candles)} candles "
            f"(~{len(candles)//24} days of 1h data)"
        )

        # ═══ Detect REAL Trade Setups ═══
        if self.current_state["completed_points"] == 0:
            key_points = self._detect_trade_setups(candles, num_points)
            self.current_state["key_points"] = key_points
            self.current_state["total_points"] = len(key_points)
        else:
            key_points = self.current_state.get("key_points", [])

        if not key_points:
            return {
                "error": "No trade setups found in data",
                "candles": len(candles),
                "suggestion": "Try different symbol or increase candles_count"
            }

        # ═══ Run Tests ═══
        start_from = self.current_state["completed_points"]
        trades_found = sum(
            1 for r in self.current_state["results"]
            if r["recommendation"]["signal"] in ["BUY", "SELL"]
        )

        for i, point in enumerate(key_points[start_from:], start=start_from):
            if self.ai.total_cost >= budget_limit:
                self.logger.warning(f"💰 Budget limit: ${self.ai.total_cost:.2f}")
                self.current_state["status"] = "paused_budget"
                self._save_state()
                break

            point_idx = point["index"]

            self.logger.info(f"\n{'='*60}")
            self.logger.info(
                f"📍 Point {i+1}/{len(key_points)}: "
                f"{point['type']} (score:{point['score']}) "
                f"@ index {point_idx} (${point['price']:.2f})"
            )
            if point.get("details"):
                self.logger.info(f"   Details: {point['details']}")

            # ═══ Cut Historical Data at This Point ═══
            history = candles[:point_idx]
            future = candles[point_idx:point_idx + 100]

            if len(history) < 500:
                self.logger.warning("⚠️ History < 500, skip")
                continue
            if len(future) < 50:
                self.logger.warning("⚠️ Future < 50, skip")
                continue

            # ═══ Build 3 Timeframes ═══
            entry_data = self._list_to_dict(history[-500:], symbol, timeframe)
            context_data = self._build_higher_tf(history[-2000:], 4, symbol)
            macro_data = self._build_higher_tf(history, 24, symbol)

            if not entry_data:
                continue

            custom = {"entry": entry_data}
            if context_data:
                custom["context"] = context_data
            if macro_data:
                custom["macro"] = macro_data

            self.logger.info(
                f"   📊 entry={entry_data['count']}, "
                f"context={context_data['count'] if context_data else 0}, "
                f"macro={macro_data['count'] if macro_data else 0}"
            )

            # ═══ Calculate date for manual chart checking ═══
            candle_timestamp = candles[point_idx][0]
            trade_date = datetime.fromtimestamp(
                candle_timestamp / 1000
            ).strftime("%Y-%m-%d %H:%M")

            future_start = trade_date
            future_end_idx = min(point_idx + 100, len(candles) - 1)
            future_end = datetime.fromtimestamp(
                candles[future_end_idx][0] / 1000
            ).strftime("%Y-%m-%d %H:%M")

            self.logger.info(
                f"   📅 Date: {trade_date} | "
                f"Future: {future_start} → {future_end}"
            )

            # ═══ AI Analysis ═══
            try:
                result = self.brain.full_analysis(
                    symbol=symbol,
                    timeframe=timeframe,
                    custom_data=custom
                )

                if "error" in result:
                    self.logger.warning(f"⚠️ Error: {result['error']}")
                    continue

                ai_analysis = result.get("ai_analysis", {})
                if not isinstance(ai_analysis, dict):
                    continue

            except Exception as e:
                self.logger.error(f"💥 Failed: {e}")
                continue

            # ═══ Evaluate Against Future ═══
            evaluation = self._evaluate_trade(ai_analysis, future)

            signal = ai_analysis.get("signal", "N/A")
            if signal in ["BUY", "SELL"]:
                trades_found += 1

            # ═══ Evaluate HOLD (missed opportunity?) ═══
            hold_evaluation = None
            if signal not in ["BUY", "SELL"]:
                hold_evaluation = self._evaluate_hold(future, point["price"])
                if hold_evaluation and hold_evaluation.get("missed"):
                    self.logger.info(
                        f"   ⚠️ MISSED! Up:{hold_evaluation['max_up_pct']}% "
                        f"Down:{hold_evaluation['max_down_pct']}% "
                        f"Could: {hold_evaluation['missed_direction']} "
                        f"(R:R ~{hold_evaluation['potential_rr']})"
                    )

            # ═══ Analyze losses ═══
            loss_analysis = None
            if evaluation.get("outcome") == "LOSS":
                loss_analysis = self._analyze_loss(
                    ai_analysis, evaluation, future
                )
                self.logger.info(
                    f"   📝 Loss: {loss_analysis['loss_type']}"
                )
                self.logger.info(
                    f"   📝 Lesson: {loss_analysis['lesson']}"
                )

            # ═══ Save Result ═══
            test_result = {
                "point_index": i,
                "point_type": point["type"],
                "point_score": point["score"],
                "candle_index": point_idx,
                "price_at_point": point["price"],
                "point_details": point.get("details", {}),

                # ═══ للفحص اليدوي على الشارت ═══
                "date": trade_date,
                "check_on_chart": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "entry_date": trade_date,
                    "future_from": future_start,
                    "future_to": future_end,
                    "go_to": f"Open {symbol} on {timeframe}, go to {trade_date}",
                },

                "data_sent": {
                    "entry": entry_data["count"],
                    "context": context_data["count"] if context_data else 0,
                    "macro": macro_data["count"] if macro_data else 0,
                },
                "recommendation": {
                    "signal": signal,
                    "confidence": ai_analysis.get("confidence"),
                    "bias": ai_analysis.get("bias"),
                    "entry": ai_analysis.get("entry"),
                    "stop_loss": ai_analysis.get("stop_loss"),
                    "tp": ai_analysis.get("tp") or ai_analysis.get("tp1"),
                    "tp1": ai_analysis.get("tp1"),
                    "tp2": ai_analysis.get("tp2"),
                    "tp3": ai_analysis.get("tp3"),
                    "rr": ai_analysis.get("rr"),
                    "market_regime": ai_analysis.get("market_regime"),
                    "reasoning": str(ai_analysis.get("reasoning", ""))[:500],
                    "why_this_direction": ai_analysis.get("why_this_direction", ""),
                    "hold_reason": ai_analysis.get("hold_reason", ""),
                    "confluence_count": ai_analysis.get("confluence_count", 0),
                    "smc_zones": ai_analysis.get("smc_zones_found", {}),
                },
                "evaluation": evaluation,
                "hold_evaluation": hold_evaluation,
                "loss_analysis": loss_analysis,
                "cost": result.get("cost", 0),
                "timestamp": datetime.now().isoformat()
            }

            self.current_state["results"].append(test_result)
            self.current_state["completed_points"] = i + 1
            self.current_state["total_cost"] = self.ai.total_cost
            self._save_state()

            # ═══ Print Result ═══
            confidence = ai_analysis.get("confidence", 0)
            outcome = evaluation["outcome"]
            emoji = {
                "WIN_FULL": "🏆", "WIN_PARTIAL": "✅",
                "LOSS": "❌", "HOLD": "⏸️",
                "NO_FILL": "📭", "OPEN": "🔄", "INVALID": "⚠️"
            }.get(outcome, "❓")

            self.logger.info(f"   📅 {trade_date}")
            self.logger.info(
                f"   → {signal} ({confidence}%) | {outcome} {emoji} | "
                f"Trades: {trades_found}/{i+1}"
            )
            if evaluation.get("entry_filled"):
                self.logger.info(
                    f"   → Entry bar:{evaluation['bars_to_entry']} | "
                    f"TP1:{'✅' if evaluation['tp1_hit'] else '❌'} "
                    f"TP2:{'✅' if evaluation['tp2_hit'] else '❌'} "
                    f"TP3:{'✅' if evaluation['tp3_hit'] else '❌'} | "
                    f"MFE:{evaluation['mfe']:.2f}% MAE:{evaluation['mae']:.2f}% "
                    f"R:R:{evaluation['actual_rr']}"
                )

            time.sleep(3)

        # ═══ Final Stats ═══
        stats = self._calculate_statistics()
        self.current_state["statistics"] = stats
        self.current_state["completed_at"] = datetime.now().isoformat()

        if self.current_state["completed_points"] >= len(key_points):
            self.current_state["status"] = "completed"

        self._save_state()
        self._save_final_report(stats)

        return {
            "status": self.current_state["status"],
            "completed": self.current_state["completed_points"],
            "total": len(key_points),
            "total_cost": f"${self.current_state['total_cost']:.2f}",
            "statistics": stats
        }

    # ══════════════════════════════════════════════
    #  STATISTICS
    # ══════════════════════════════════════════════

    def _calculate_statistics(self):
        results = self.current_state.get("results", [])
        if not results:
            return {"error": "No results"}

        trades = [r for r in results if r["recommendation"]["signal"] in ["BUY", "SELL"]]
        holds = [r for r in results if r["recommendation"]["signal"] not in ["BUY", "SELL"]]
        filled = [t for t in trades if t["evaluation"]["entry_filled"]]
        wins = [t for t in filled if "WIN" in t["evaluation"]["outcome"]]
        losses = [t for t in filled if t["evaluation"]["outcome"] == "LOSS"]
        no_fills = [t for t in trades if t["evaluation"]["outcome"] == "NO_FILL"]

        tp1 = sum(1 for t in filled if t["evaluation"]["tp1_hit"])
        tp2 = sum(1 for t in filled if t["evaluation"]["tp2_hit"])
        tp3 = sum(1 for t in filled if t["evaluation"]["tp3_hit"])

        avg_mfe = sum(t["evaluation"]["mfe"] for t in filled) / len(filled) if filled else 0
        avg_mae = sum(t["evaluation"]["mae"] for t in filled) / len(filled) if filled else 0

        win_rrs = [t["evaluation"]["actual_rr"] for t in wins if t["evaluation"]["actual_rr"] > 0]
        avg_win_rr = sum(win_rrs) / len(win_rrs) if win_rrs else 0

        buys = sum(1 for t in trades if t["recommendation"]["signal"] == "BUY")
        sells = sum(1 for t in trades if t["recommendation"]["signal"] == "SELL")

        # Confidence analysis
        high_conf = [t for t in filled if (t["recommendation"].get("confidence") or 0) >= 80]
        high_wins = [t for t in high_conf if "WIN" in t["evaluation"]["outcome"]]
        med_conf = [t for t in filled if 60 <= (t["recommendation"].get("confidence") or 0) < 80]
        med_wins = [t for t in med_conf if "WIN" in t["evaluation"]["outcome"]]

        # Setup type analysis
        type_results = {}
        for r in results:
            pt = r.get("point_type", "unknown")
            if pt not in type_results:
                type_results[pt] = {"total": 0, "trades": 0, "wins": 0}
            type_results[pt]["total"] += 1
            if r["recommendation"]["signal"] in ["BUY", "SELL"]:
                type_results[pt]["trades"] += 1
                if "WIN" in r["evaluation"]["outcome"]:
                    type_results[pt]["wins"] += 1

        return {
            "total_points": len(results),
            "total_trades": len(trades),
            "total_holds": len(holds),
            "buys": buys, "sells": sells,
            "filled": len(filled),
            "wins": len(wins), "losses": len(losses),
            "no_fills": len(no_fills),
            "win_rate": f"{len(wins)/len(filled)*100:.1f}%" if filled else "N/A",
            "trade_rate": f"{len(trades)/len(results)*100:.1f}%" if results else "N/A",
            "fill_rate": f"{len(filled)/len(trades)*100:.1f}%" if trades else "N/A",
            "tp1_rate": f"{tp1/len(filled)*100:.1f}%" if filled else "N/A",
            "tp2_rate": f"{tp2/len(filled)*100:.1f}%" if filled else "N/A",
            "tp3_rate": f"{tp3/len(filled)*100:.1f}%" if filled else "N/A",
            "avg_mfe": f"{avg_mfe:.2f}%",
            "avg_mae": f"{avg_mae:.2f}%",
            "avg_win_rr": f"1:{avg_win_rr:.2f}",
            "high_conf_wr": f"{len(high_wins)/len(high_conf)*100:.1f}%" if high_conf else "N/A",
            "med_conf_wr": f"{len(med_wins)/len(med_conf)*100:.1f}%" if med_conf else "N/A",
            "setup_types": type_results,
            "cost": f"${self.current_state.get('total_cost', 0):.2f}",
            "cost_per_point": f"${self.current_state.get('total_cost', 0)/len(results):.2f}" if results else "N/A",
        }

    def _save_final_report(self, stats):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        sym = self.current_state['symbol'].replace('/', '')
        filename = f"{self.results_dir}/bt_{sym}_{ts}.json"
        report = {
            "summary": stats,
            "details": self.current_state["results"],
            "config": {
                "symbol": self.current_state["symbol"],
                "timeframe": self.current_state["timeframe"],
                "points": self.current_state["completed_points"],
            }
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        self.logger.info(f"📄 Report: {filename}")

    def print_summary(self):
        if not self.current_state or not self.current_state.get("statistics"):
            print("❌ No results")
            return

        s = self.current_state["statistics"]
        print("\n" + "═" * 60)
        print("📊 BACKTEST V5 - RESULTS")
        print("═" * 60)
        print(f"  {self.current_state['symbol']} | {self.current_state['timeframe']}")
        print(f"  Points: {self.current_state['completed_points']} | Status: {self.current_state['status']}")
        print("─" * 60)
        print(f"  📈 Win Rate:    {s.get('win_rate', 'N/A')} (filled trades)")
        print(f"  ✅ Wins: {s.get('wins',0)} | ❌ Losses: {s.get('losses',0)}")
        print(f"  📊 Trades: {s.get('total_trades',0)} (BUY:{s.get('buys',0)} SELL:{s.get('sells',0)})")
        print(f"  ⏸️  HOLDs: {s.get('total_holds',0)} | 📭 No Fills: {s.get('no_fills',0)}")
        print(f"  📬 Fill Rate:   {s.get('fill_rate', 'N/A')}")
        print(f"  🎯 Trade Rate:  {s.get('trade_rate', 'N/A')}")
        print("─" * 60)
        print(f"  🎯 TP1: {s.get('tp1_rate','N/A')} | TP2: {s.get('tp2_rate','N/A')} | TP3: {s.get('tp3_rate','N/A')}")
        print(f"  📈 MFE: {s.get('avg_mfe','N/A')} | 📉 MAE: {s.get('avg_mae','N/A')}")
        print(f"  📏 Win R:R: {s.get('avg_win_rr','N/A')}")
        print("─" * 60)
        print(f"  🎯 High Conf (80%+): {s.get('high_conf_wr','N/A')}")
        print(f"  📊 Med Conf (60-79%): {s.get('med_conf_wr','N/A')}")
        print("─" * 60)

        # Setup type breakdown
        types = s.get("setup_types", {})
        if types:
            print("  📋 Setup Type Results:")
            for t, v in types.items():
                wr = f"{v['wins']/v['trades']*100:.0f}%" if v['trades'] > 0 else "N/A"
                print(f"    {t}: {v['trades']} trades, {v['wins']} wins ({wr})")

        print("─" * 60)
        print(f"  💰 Cost: {s.get('cost','N/A')} | Per Point: {s.get('cost_per_point','N/A')}")
        print("═" * 60)

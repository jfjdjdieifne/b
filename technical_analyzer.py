# -*- coding: utf-8 -*-
"""
TechnicalAnalyzer - حسابات رياضية فقط.
لا يتخذ أي قرار تداولي.
الـ AI هو اللي يحلل ويقرر.
"""
import logging
import numpy as np


class TechnicalAnalyzer:

    def __init__(self):
        self.logger = logging.getLogger("TechnicalAnalyzer")

    # ══════════════════════════════════════════════
    #  MATH FUNCTIONS (حسابات بحتة)
    # ══════════════════════════════════════════════

    @staticmethod
    def ema(data, period):
        arr = np.array(data, dtype=float)
        if len(arr) < 2:
            return arr
        out = np.empty_like(arr)
        k = 2.0 / (period + 1)
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = arr[i] * k + out[i - 1] * (1 - k)
        return out

    @staticmethod
    def safe_ema(data, period):
        """EMA آمن - يرجع السعر الحالي إذا البيانات قليلة."""
        arr = np.array(data, dtype=float)
        if len(arr) < period:
            return float(arr[-1]) if len(arr) > 0 else 0.0
        return float(TechnicalAnalyzer.ema(arr, period)[-1])

    @staticmethod
    def rsi(closes, period=14):
        c = np.array(closes, dtype=float)
        if len(c) < period + 2:
            return np.full(len(c), 50.0)
        d = np.diff(c)
        g = np.where(d > 0, d, 0.0)
        l = np.where(d < 0, -d, 0.0)
        ag = np.zeros(len(c))
        al = np.zeros(len(c))
        ag[period] = g[:period].mean()
        al[period] = l[:period].mean()
        for i in range(period + 1, len(c)):
            ag[i] = (ag[i - 1] * (period - 1) + g[i - 1]) / period
            al[i] = (al[i - 1] * (period - 1) + l[i - 1]) / period
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = np.where(al > 0, ag / al, 100.0)
        rsi_vals = 100.0 - 100.0 / (1.0 + rs)
        return np.nan_to_num(rsi_vals, nan=50.0)

    @staticmethod
    def macd(closes, fast=12, slow=26, sig=9):
        ef = TechnicalAnalyzer.ema(closes, fast)
        es = TechnicalAnalyzer.ema(closes, slow)
        line = ef - es
        signal = TechnicalAnalyzer.ema(line, sig)
        return line, signal, line - signal

    @staticmethod
    def atr(highs, lows, closes, period=14):
        h = np.array(highs, dtype=float)
        l = np.array(lows, dtype=float)
        c = np.array(closes, dtype=float)
        tr = np.zeros(len(c))
        for i in range(1, len(c)):
            tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        out = np.zeros(len(c))
        if len(tr) > period:
            out[period] = tr[1:period + 1].mean()
            for i in range(period + 1, len(c)):
                out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
        return out

    @staticmethod
    def support_resistance(highs, lows, lookback=50):
        """إيجاد مستويات الدعم والمقاومة (رياضياً = local min/max)."""
        h = np.array(highs[-lookback:], dtype=float)
        l = np.array(lows[-lookback:], dtype=float)
        res, sup = [], []
        for i in range(2, len(h) - 2):
            if h[i] > max(h[i - 1], h[i - 2], h[i + 1], h[i + 2]):
                res.append(round(float(h[i]), 2))
            if l[i] < min(l[i - 1], l[i - 2], l[i + 1], l[i + 2]):
                sup.append(round(float(l[i]), 2))
        return sorted(set(sup))[-3:], sorted(set(res))[-3:]

    @staticmethod
    def market_structure(highs, lows):
        """كشف نمط HH/HL أو LH/LL (رياضياً بحت)."""
        h = np.array(highs, dtype=float)
        l = np.array(lows, dtype=float)
        sh, sl = [], []
        for i in range(2, len(h) - 2):
            if h[i] > max(h[i - 1], h[i - 2], h[i + 1], h[i + 2]):
                sh.append((i, round(float(h[i]), 2)))
            if l[i] < min(l[i - 1], l[i - 2], l[i + 1], l[i + 2]):
                sl.append((i, round(float(l[i]), 2)))
        if len(sh) >= 2 and len(sl) >= 2:
            if sh[-1][1] > sh[-2][1] and sl[-1][1] > sl[-2][1]:
                return "HH+HL (higher highs, higher lows)"
            elif sh[-1][1] < sh[-2][1] and sl[-1][1] < sl[-2][1]:
                return "LH+LL (lower highs, lower lows)"
        return "NO CLEAR PATTERN"

    # ══════════════════════════════════════════════
    #  COMPUTE ALL (أرقام فقط - بدون أي قرار)
    # ══════════════════════════════════════════════

    def compute_all(self, data):
        """حساب كل المؤشرات الرقمية. لا يتخذ أي قرار."""
        if not data or len(data["closes"]) < 50:
            return None

        c = data["closes"]
        h = data["highs"]
        l = data["lows"]
        v = data["volumes"]
        n = len(c)
        price = c[-1]

        # ═══ EMAs ═══
        e9 = round(self.safe_ema(c, 9), 2)
        e21 = round(self.safe_ema(c, 21), 2)
        e50 = round(self.safe_ema(c, 50), 2)
        e200 = round(self.safe_ema(c, 200), 2) if n >= 200 else None

        # ═══ RSI ═══
        _rsi = self.rsi(c)
        rsi_val = round(float(_rsi[-1]), 1)

        # ═══ MACD ═══
        ml, ms, mh = self.macd(c)

        # ═══ ATR ═══
        _atr = self.atr(h, l, c)
        atr_val = round(float(_atr[-1]), 2)

        # ═══ Support / Resistance ═══
        sups, ress = self.support_resistance(h, l)

        # ═══ Structure Pattern ═══
        struct = self.market_structure(h, l)

        # ═══ Volume ═══
        v_arr = np.array(v, dtype=float)
        v_avg = float(v_arr[-20:].mean()) if len(v_arr) >= 20 else float(v_arr.mean())
        v_current = float(v_arr[-1])
        v_ratio = round(v_current / v_avg, 2) if v_avg > 0 else 1.0
        v_avg5 = float(v_arr[-5:].mean()) if len(v_arr) >= 5 else v_avg

        # ═══ Price changes ═══
        chg_1 = round((c[-1] - c[-2]) / c[-2] * 100, 2) if len(c) >= 2 and c[-2] != 0 else 0
        chg_5 = round((c[-1] - c[-6]) / c[-6] * 100, 2) if len(c) >= 6 and c[-6] != 0 else 0
        chg_20 = round((c[-1] - c[-21]) / c[-21] * 100, 2) if len(c) >= 21 and c[-21] != 0 else 0

        # ═══ Range info ═══
        high_20 = round(float(np.max(h[-20:])), 2)
        low_20 = round(float(np.min(l[-20:])), 2)
        high_50 = round(float(np.max(h[-50:])), 2)
        low_50 = round(float(np.min(l[-50:])), 2)

        return {
            "sym": data["symbol"],
            "tf": data["timeframe"],
            "price": round(price, 2),
            "chg_1": chg_1,
            "chg_5": chg_5,
            "chg_20": chg_20,
            "ema9": e9,
            "ema21": e21,
            "ema50": e50,
            "ema200": e200,
            "rsi": rsi_val,
            "macd_line": round(float(ml[-1]), 2),
            "macd_signal": round(float(ms[-1]), 2),
            "macd_hist": round(float(mh[-1]), 2),
            "macd_hist_prev": round(float(mh[-2]), 2) if len(mh) >= 2 else 0,
            "atr": atr_val,
            "atr_pct": round(atr_val / price * 100, 3) if price > 0 else 0,
            "sup": sups,
            "res": ress,
            "struct": struct,
            "vol_ratio": v_ratio,
            "vol_avg20": round(v_avg, 0),
            "vol_trend": "RISING" if v_avg5 > v_avg * 1.2 else ("FALLING" if v_avg5 < v_avg * 0.8 else "STABLE"),
            "range_20": {"high": high_20, "low": low_20},
            "range_50": {"high": high_50, "low": low_50},
        }

    # ══════════════════════════════════════════════
    #  COMPACT SUMMARY (أرقام مختصرة للـ AI)
    # ══════════════════════════════════════════════

    def compact_summary(self, ind):
        """ملخص مختصر للأرقام المحسوبة فقط."""
        if not ind:
            return "No data"

        ema200_str = str(ind['ema200']) if ind['ema200'] else "N/A"

        return (
            f"Price: ${ind['price']} | Chg: 1bar={ind['chg_1']:+.2f}% 5bar={ind['chg_5']:+.2f}% 20bar={ind['chg_20']:+.2f}%\n"
            f"EMA: 9={ind['ema9']} 21={ind['ema21']} 50={ind['ema50']} 200={ema200_str}\n"
            f"RSI: {ind['rsi']} | MACD: line={ind['macd_line']} sig={ind['macd_signal']} hist={ind['macd_hist']} prev_hist={ind['macd_hist_prev']}\n"
            f"ATR: {ind['atr']} ({ind['atr_pct']}% of price)\n"
            f"Volume: {ind['vol_ratio']}x avg | Trend: {ind['vol_trend']}\n"
            f"Support: {ind['sup']} | Resistance: {ind['res']}\n"
            f"Structure: {ind['struct']}\n"
            f"Range20: {ind['range_20']['low']}-{ind['range_20']['high']} | Range50: {ind['range_50']['low']}-{ind['range_50']['high']}"
        )

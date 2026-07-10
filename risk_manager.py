# -*- coding: utf-8 -*-
import logging
from config import Config


class RiskManager:
    def __init__(self, balance=None):
        self.logger = logging.getLogger("RiskManager")
        self.balance = balance or Config.ACCOUNT_BALANCE
        self.max_risk = Config.MAX_RISK_PER_TRADE

    @staticmethod
    def _price(value):
        """Accept both legacy numeric targets and new structured targets."""
        if isinstance(value, dict):
            if value.get("mode") == "OPEN_TRAILING":
                return None
            value = value.get("price", value.get("value"))
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def evaluate(self, signal):
        if not isinstance(signal, dict) or "error" in signal:
            return {"approved": False, "reason": "Signal invalid"}

        # يقبل الأسماء القديمة وبنية TP1/TP2 الجديدة.
        entry = self._price(signal.get("entry"))
        sl = self._price(signal.get("stop_loss", signal.get("sl")))
        tp1 = self._price(signal.get("tp1", signal.get("take_profit_1")))
        if tp1 is None:
            tp1 = self._price(signal.get("tp", signal.get("take_profit")))
        tp2 = self._price(signal.get("tp2", signal.get("take_profit_2")))
        tp3 = self._price(signal.get("tp3", signal.get("take_profit_3")))
        conf = signal.get("confidence", 0)
        sig_type = signal.get("signal", "HOLD")

        if sig_type == "HOLD":
            return {"approved": False, "reason": "Signal is HOLD"}

        # ⚠️ حل جذري (يوليو 2026، بطلب صريح): BUY_LIMIT/
        # SELL_LIMIT (أوامر معلقة - اتجاه ومنطقة دخول معروفة،
        # السعر لم يصلها بعد) تُعامل بنفس منطق BUY/SELL بكل
        # فحوصات الاتجاه/R:R أدناه - الفرق الوحيد هو أنها
        # تُعرض على المستخدم كأمر معلق (limit order) بدل أمر فوري،
        # لا يُنفّذ فوراً - هذا يُحسم بمكان آخر (الواجهة/UI،
        # لا RiskManager).
        is_buy_dir = sig_type in ("BUY", "BUY_LIMIT")
        is_sell_dir = sig_type in ("SELL", "SELL_LIMIT")
        if not (is_buy_dir or is_sell_dir):
            return {"approved": False, "reason": f"Unsupported signal type: {sig_type}"}

        if conf < 60:
            return {"approved": False, "reason": f"Confidence too low ({conf}%)"}

        if not all([entry, sl, tp1]):
            return {
                "approved": False,
                "reason": f"Missing prices: entry={entry} sl={sl} tp1={tp1}"
            }

        # ⚠️ إصلاح باگ حرج (طبقة حماية ثانية مستقلة - نفس الفحص موجود
        # أصلاً بـbrain_core.py قبل الوصول هنا، لكن هذه الدالة تُستدعى
        # أيضاً من مسارات أخرى قد لا تمر عبر ذلك الفحص - "الدفاع
        # بالعمق"): abs(entry-sl) كان يحسب "مخاطرة" حتى لو كان sl
        # بالجهة المعاكسة تماماً (مثلاً BUY وsl فوق الدخول) - رياضياً
        # يُعطي رقماً موجباً يبدو طبيعياً رغم أن الصفقة غير منطقية
        # بالكامل (SL معكوس لا يحمي من أي خسارة فعلية). نتحقق صراحة من
        # الاتجاه الصحيح قبل أي حساب.
        if is_buy_dir and sl >= entry:
            return {"approved": False, "reason": f"{sig_type} لكن SL ({sl}) ليس تحت entry ({entry}) - اتجاه معكوس"}
        if is_sell_dir and sl <= entry:
            return {"approved": False, "reason": f"{sig_type} لكن SL ({sl}) ليس فوق entry ({entry}) - اتجاه معكوس"}
        if is_buy_dir and tp1 <= entry:
            return {"approved": False, "reason": f"{sig_type} لكن TP ({tp1}) ليس فوق entry ({entry}) - اتجاه معكوس"}
        if is_sell_dir and tp1 >= entry:
            return {"approved": False, "reason": f"{sig_type} لكن TP ({tp1}) ليس تحت entry ({entry}) - اتجاه معكوس"}

        risk = abs(entry - sl)
        reward = abs(tp1 - entry)
        rr = round(reward / risk, 2) if risk > 0 else 0

        if rr < 1.0:
            # تحقق من tp2
            if tp2:
                reward2 = abs(tp2 - entry)
                rr = round(reward2 / risk, 2) if risk > 0 else 0

        pos = self._position_size(entry, sl)

        return {
            "approved": True,
            "signal": sig_type,
            "entry": entry,
            "stop_loss": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "risk_reward": f"1:{rr}",
            "confidence": conf,
            "position": pos,
            "risk_usd": pos["risk_usd"],
            "potential_profit": round(reward * pos["qty"], 2),
        }

    def _position_size(self, entry, sl):
        risk_amt = self.balance * self.max_risk
        price_risk = abs(entry - sl)
        if price_risk == 0:
            return {"qty": 0, "value": 0, "risk_usd": 0, "risk_%": 0}
        qty = risk_amt / price_risk
        return {
            "qty": round(qty, 6),
            "value": round(qty * entry, 2),
            "risk_usd": round(risk_amt, 2),
            "risk_%": self.max_risk * 100,
            "sl_distance_%": round(price_risk / entry * 100, 3),
        }

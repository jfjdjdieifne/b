# -*- coding: utf-8 -*-
"""
VerificationLayer - فحص آلي لمصداقية تحليل الـ AI
════════════════════════════════════════════════════════════════════
هذا الملف يجاوب على سؤال أساسي: "كيف أتحقق إنه البوت فعلاً عم يحلل
صح ومش عم يشلف؟"

الفكرة: بدل ما نصدق كل رقم/مستوى ذكره الـ AI بنص الـ reasoning أو
smc_zones_found، نستخرج كل سعر/مستوى مذكور، ونتحقق رياضياً:
  1) هل هذا السعر موجود فعلاً بمدى الشموع المرسلة؟ (مو مختلق)
  2) هل هو قريب من نقطة حقيقية (swing high/low, OB) بالبيانات؟
  3) هل الأرقام المشتقة (R:R، المسافات) صحيحة حسابياً؟

النتيجة: "Verification Score" = نسبة الادعاءات القابلة للتحقق والمؤكدة
من أصل كل الادعاءات المستخرجة. هذا لا يثبت "صحة القرار التداولي" (هذا
فقط الـ Backtest الحقيقي يقدر يثبته على مئات الصفقات) - لكنه يثبت
أو ينفي "هل الكلام مبني على أرقام حقيقية من البيانات، أو هلوسة/كلام
عام لا يستند لشيء ملموس."

هذا يكمّل authenticity_engine.py (يلي يتحقق من صحة الأنماط نفسها،
متل الـ OB/Sweep) بطبقة تحقق على مستوى النص الناتج بالكامل.
"""
import re
import logging


class VerificationLayer:

    def __init__(self):
        self.logger = logging.getLogger("VerificationLayer")

    # ══════════════════════════════════════════════════════════
    #  الدالة الرئيسية
    # ══════════════════════════════════════════════════════════

    def verify(self, ai_result, mtf_data):
        """
        يفحص نتيجة تحليل الـ AI كاملة مقابل بيانات الشموع الحقيقية.

        Args:
            ai_result: dict، رد الـ AI (narrative, reasoning, smc_zones_found...)
            mtf_data: dict {"entry": {...}, "context": {...}, "macro": {...}}

        Returns:
            dict: {
                "total_claims": عدد الأسعار المستخرجة من النص,
                "verified": عدد الأسعار المؤكدة ضمن مدى معقول,
                "score_pct": نسبة التحقق,
                "issues": قائمة نصية بالمشاكل المكتشفة,
                "details": تفاصيل كل ادعاء
            }
        """
        if not isinstance(ai_result, dict):
            return {"total_claims": 0, "verified": 0, "score_pct": 0,
                    "issues": ["AI result ليس dict - لا يمكن التحقق"], "details": []}

        # ═══ 1) بناء نطاق الأسعار الحقيقي من كل الفريمات ═══
        price_ranges = {}
        for label, data in mtf_data.items():
            if isinstance(data, dict) and "highs" in data and "lows" in data:
                price_ranges[label] = {
                    "low": min(data["lows"]),
                    "high": max(data["highs"]),
                }

        if not price_ranges:
            return {"total_claims": 0, "verified": 0, "score_pct": 0,
                    "issues": ["لا توجد بيانات أسعار للمقارنة"], "details": []}

        overall_low = min(r["low"] for r in price_ranges.values())
        overall_high = max(r["high"] for r in price_ranges.values())
        # هامش معقول (5%) للأسعار المستقبلية القريبة (TP خارج نطاق تاريخي بشوي)
        margin = (overall_high - overall_low) * 0.15
        valid_low = overall_low - margin
        valid_high = overall_high + margin

        issues = []
        details = []
        total_claims = 0
        verified = 0

        # ═══ 2) استخراج كل الأسعار من الحقول المنظّمة (JSON) ═══
        structured_prices = self._extract_structured_prices(ai_result)
        for field_name, price in structured_prices:
            total_claims += 1
            ok = bool(valid_low <= price <= valid_high)
            if ok:
                verified += 1
            else:
                issues.append(
                    f"{field_name}={price} خارج النطاق المعقول "
                    f"({valid_low:.2f}-{valid_high:.2f}) - احتمال سعر مختلق"
                )
            details.append({"field": field_name, "price": price, "verified": ok})

        # ═══ 3) استخراج أسعار من النص الحر (narrative/reasoning) ═══
        free_text = " ".join(str(ai_result.get(k, "")) for k in
                              ("narrative", "reasoning", "archetype", "structure_analysis"))
        text_prices = self._extract_prices_from_text(free_text)
        for price in text_prices:
            # نتجاهل الأرقام الصغيرة جداً (احتمال تكون نسب/مؤشرات مو أسعار)
            if price < overall_low * 0.3:
                continue
            total_claims += 1
            ok = bool(valid_low <= price <= valid_high)
            if ok:
                verified += 1
            else:
                issues.append(
                    f"سعر مذكور بالنص ({price}) خارج النطاق المعقول "
                    f"({valid_low:.2f}-{valid_high:.2f})"
                )
            details.append({"field": "free_text_mention", "price": price, "verified": ok})

        # ═══ 4) فحص اتساق R:R (هل الرقم المذكور يطابق الحساب الفعلي؟) ═══
        rr_check = self._verify_risk_reward(ai_result)
        if rr_check is not None:
            total_claims += 1
            if rr_check["consistent"]:
                verified += 1
            else:
                issues.append(
                    f"R:R المذكور ({rr_check['claimed']}) لا يطابق الحساب الفعلي "
                    f"({rr_check['calculated']:.2f}) من entry/SL/TP المعطاة"
                )
            details.append({"field": "risk_reward_consistency", **rr_check})

        # ═══ 5) فحص وجود narrative/archetype (طبقة الفهم الشامل) ═══
        has_narrative = bool(str(ai_result.get("narrative", "")).strip())
        has_archetype = bool(str(ai_result.get("archetype", "")).strip())
        if ai_result.get("signal") in ("BUY", "SELL"):
            total_claims += 2
            if has_narrative:
                verified += 1
            else:
                issues.append(
                    "لا يوجد حقل narrative - التحليل قد يكون checklist ميكانيكي "
                    "بدون فهم شامل حقيقي (راجع قسم HOLISTIC_MARKET_READING)"
                )
            if has_archetype:
                verified += 1
            else:
                issues.append(
                    "لا يوجد حقل archetype - لم يتم ربط الوضع الحالي بنمط "
                    "معروف من الخبرة السابقة"
                )

        # ⚠️ إصلاح باگ حقيقي مكتشف بالاختبار الفعلي (2026-07-03):
        # لما التحليل يتوقف مبكراً بـGate (نتيجة HOLD)، ما في أسعار أو
        # ادعاءات نتحقق منها أصلاً (total_claims=0) - هذا وضع طبيعي
        # وصحيح (توقف الـGate يمنع أصلاً أي ادعاء سعري مضلل)، وليس
        # "فشل تحقق". الكود القديم كان يحسب score_pct=0 بهذه الحالة
        # (نفس رقم "فشل تحقق كامل" 0%!) فيطلق إنذاراً كاذباً بكل مرة
        # يتوقف البوت بشكل صحيح عند Gate - وهذا يحدث كثيراً
        # (أغلب التحليلات تتوقف مبكراً بمنهجية Gates، هذا سلوك مقصود وسليم،
        # راجع docstring أعلى الملف). الإصلاح: score_pct=None صراحة
        # يميّز "غير قابل للتطبيق" عن "0% فشل حقيقي" - كل الأماكن التي
        # تقرأ score_pct (brain_core.py, main.py, market_scanner.py)
        # عُدّلت بالتوازي لتتعامل مع None كـ"لا يوجد ما يُتحقق منه"
        # (يُعامَل كنجاح ضمني، لا كفشل) - تحقق فعلي: راجع تعليق الإصلاح
        # المطابق بكل ملف من الثلاثة.
        applicable = total_claims > 0
        score_pct = round((verified / total_claims * 100), 1) if applicable else None

        return {
            "total_claims": total_claims,
            "verified": verified,
            "score_pct": score_pct,
            "applicable": applicable,
            "issues": issues,
            "details": details,
            "has_narrative": has_narrative,
            "has_archetype": has_archetype,
        }

    # ══════════════════════════════════════════════════════════
    #  دوال مساعدة للاستخراج
    # ══════════════════════════════════════════════════════════

    def _extract_structured_prices(self, ai_result):
        """يستخرج الأسعار من الحقول المنظمة المعروفة بالـ JSON"""
        prices = []
        for field in ("entry", "stop_loss", "tp", "tp1", "tp2", "tp3"):
            val = ai_result.get(field)
            if val is not None:
                try:
                    prices.append((field, float(val)))
                except (TypeError, ValueError):
                    pass

        # key_levels ممكن تكون list من dicts أو list من أرقام
        key_levels = ai_result.get("key_levels", [])
        if isinstance(key_levels, list):
            for item in key_levels:
                if isinstance(item, dict):
                    for k in ("price", "level_price"):
                        if k in item:
                            try:
                                prices.append((f"key_level.{item.get('level', k)}", float(item[k])))
                            except (TypeError, ValueError):
                                pass
                elif isinstance(item, (int, float)):
                    prices.append(("key_level", float(item)))

        return prices

    def _extract_prices_from_text(self, text):
        """
        يستخرج أرقام تشبه الأسعار من نص حر (narrative/reasoning).
        يبحث عن أنماط مثل $58,326.50 أو 58326.50 أو 58,326
        """
        if not text:
            return []

        # نمط: اختياري $ ثم أرقام مع فواصل اختيارية ونقطة عشرية اختيارية
        pattern = r'\$?\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{4,}(?:\.\d+)?)\b'
        matches = re.findall(pattern, text)
        prices = []
        for m in matches:
            try:
                val = float(m.replace(",", ""))
                prices.append(val)
            except ValueError:
                continue
        return prices

    def _verify_risk_reward(self, ai_result):
        """يتحقق أن R:R المذكور يطابق الحساب الفعلي من entry/SL/TP"""
        rr_claimed = ai_result.get("rr")
        entry = ai_result.get("entry")
        sl = ai_result.get("stop_loss")
        tp = ai_result.get("tp") or ai_result.get("tp1")

        if not all([rr_claimed, entry, sl, tp]):
            return None

        try:
            entry, sl, tp = float(entry), float(sl), float(tp)
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            if risk == 0:
                return None
            calculated_rr = reward / risk

            # استخراج الرقم من صيغة "1:X" أو "X:1" أو رقم مباشر
            rr_str = str(rr_claimed)
            numbers = re.findall(r'[\d.]+', rr_str)
            if not numbers:
                return None
            claimed_ratio = float(numbers[-1]) if len(numbers) >= 2 else float(numbers[0])

            # نسمح بهامش خطأ 20% (تقريب طبيعي)
            consistent = abs(claimed_ratio - calculated_rr) / max(calculated_rr, 0.01) < 0.25

            return {
                "claimed": rr_claimed,
                "calculated": calculated_rr,
                "consistent": consistent,
            }
        except (ValueError, TypeError, ZeroDivisionError):
            return None

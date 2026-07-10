# -*- coding: utf-8 -*-
"""
MarketScanner - يمسح قائمة عملات كاملة تلقائياً بحثاً عن أفضل صفقة
════════════════════════════════════════════════════════════════════
يجاوب على طلب: "بدي أحطه يحلل لحاله ويقعد يبحبش عن صفقة بكل العملات
لحد ما يلاقي صفقة بثقة فوق 85%."

المنطق:
  1. يمر على كل عملة بـ Config.SCAN_SYMBOLS (افتراضياً أهم 20 عملة)
  2. يشغّل full_analysis (بكل طبقاته: Authenticity + Verification +
     Auto-Consensus عند القرارات الحرجة) على كل عملة
  3. يفلتر النتائج حسب معيارين مع بعض (مو بس ثقة الـ AI لوحدها):
     أ) confidence >= SCANNER_MIN_CONFIDENCE (افتراضياً 85%)
     ب) verification score مقبول (لا هلوسة بالأسعار)
     ج) (اختياري) نسبة نجاح تاريخية موثقة لنفس نوع الإعداد إن وجدت
  4. يرجع قائمة مرتبة بأفضل الفرص المكتشفة

⚠️ ملاحظة صادقة: "ثقة الـ AI 85%" ليست نفسها "نسبة نجاح تاريخية 85%
مؤكدة بالباك تست". النظام يعرض الاثنين بوضوح منفصلين ولا يخلط بينهما.
لتأكيد حقيقي لأي رقم نجاح، استخدم backtest_engine.py على نفس نوع
الإعداد عبر مئات النقاط التاريخية.
"""
import logging
import time
from config import Config


class MarketScanner:

    def __init__(self, brain_core):
        self.brain = brain_core
        self.logger = logging.getLogger("MarketScanner")

    def scan(self, symbols=None, timeframe=None, min_confidence=None,
             delay_between=3, stop_on_first_match=False):
        """
        يمسح قائمة عملات بحثاً عن صفقات تحقق حد الثقة المطلوب.

        Args:
            symbols: قائمة عملات (افتراضياً Config.SCAN_SYMBOLS)
            timeframe: الفريم (افتراضياً Config.DEFAULT_TIMEFRAME)
            min_confidence: حد الثقة الأدنى (افتراضياً Config.SCANNER_MIN_CONFIDENCE)
            delay_between: تأخير بالثواني بين كل عملة (لتجنب Rate Limit)
            stop_on_first_match: لو True يتوقف عند أول صفقة مطابقة
                (أسرع وأوفر لكن قد يفوّت فرصة أفضل بعملة لاحقة)

        Returns:
            dict: {
                "scanned": عدد العملات الممسوحة فعلياً,
                "matches": قائمة الصفقات المطابقة (مرتبة تنازلياً بالثقة),
                "all_results": كل نتيجة تحليل (حتى لو HOLD) للمراجعة,
                "errors": أي عملة فشل تحليلها
            }
        """
        symbols = symbols or Config.SCAN_SYMBOLS
        timeframe = timeframe or Config.DEFAULT_TIMEFRAME
        min_confidence = min_confidence if min_confidence is not None else Config.SCANNER_MIN_CONFIDENCE

        matches = []
        all_results = []
        errors = []

        self.logger.info(
            f"🔍 بدء مسح {len(symbols)} عملة بحثاً عن صفقات "
            f"بثقة ≥ {min_confidence}% (فريم {timeframe})..."
        )

        for i, symbol in enumerate(symbols):
            self.logger.info(f"[{i+1}/{len(symbols)}] 🔎 فحص {symbol}...")

            try:
                result = self.brain.full_analysis(symbol=symbol, timeframe=timeframe)
            except Exception as e:
                self.logger.error(f"❌ {symbol} فشل: {e}")
                errors.append({"symbol": symbol, "error": str(e)})
                continue

            if "error" in result:
                errors.append({"symbol": symbol, "error": result["error"]})
                continue

            ai = result.get("ai_analysis", {})
            verification = result.get("verification", {})

            entry = {
                "symbol": symbol,
                "signal": ai.get("signal"),
                "confidence": ai.get("confidence"),
                "archetype": ai.get("archetype", ""),
                "narrative_summary": str(ai.get("narrative", ""))[:200],
                "entry_price": ai.get("entry"),
                "stop_loss": ai.get("stop_loss"),
                "tp": ai.get("tp"),
                "rr": ai.get("rr"),
                "verification_score": verification.get("score_pct") if verification else None,
                "consensus_check": ai.get("consensus_check"),
                "full_result": result,
            }
            all_results.append(entry)

            # ⚠️ إصلاح خطر كامن حقيقي (2026-07-03): بعد إصلاح
            # verification_layer.py ليعيد score_pct=None عند عدم وجود
            # ادعاءات (بدل 0% القديمة المضللة)، تحقق مباشر: `.get("score_pct", 100)`
            # لا يرجع القيمة الافتراضية إذا المفتاح موجود بقيمة None (الافتراضية
            # تعمل فقط لو المفتاح مفقود تماماً) - فيؤدي لـTypeError فعلي مؤكد
            # (`None >= 70`). ملاحظة: عملياً هذا الفرع محمي جزئياً حالياً (signal
            # في BUY/SELL يضمن total_claims>=2 دائماً ب_verification_layer.py فيبقى
            # score_pct رقماً دائماً هنا)، لكن هذا تحصين دفاعي ضروري
            # لمنع أي تعطل مستقبلي لو تغير منطق verify() لاحقاً.
            _v_score = verification.get("score_pct") if verification else None
            is_actionable = (
                ai.get("signal") in ("BUY", "SELL")
                and isinstance(ai.get("confidence"), (int, float))
                and ai["confidence"] >= min_confidence
                and (_v_score is None or _v_score >= 70)
            )

            if is_actionable:
                self.logger.info(
                    f"✅ تطابق! {symbol} {ai['signal']} بثقة {ai['confidence']}%"
                )
                matches.append(entry)
                if stop_on_first_match:
                    break
            else:
                reason = ai.get("signal", "HOLD")
                conf = ai.get("confidence", "N/A")
                self.logger.info(f"   ⏭️ {symbol}: {reason} (ثقة {conf}%) - لا يحقق الحد")

            if i < len(symbols) - 1:
                time.sleep(delay_between)

        matches.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        self.logger.info(
            f"🏁 انتهى المسح: {len(all_results)} تحليل ناجح، "
            f"{len(matches)} صفقة مطابقة، {len(errors)} خطأ"
        )

        return {
            "scanned": len(symbols),
            "successful_analyses": len(all_results),
            "matches": matches,
            "all_results": all_results,
            "errors": errors,
            "min_confidence_used": min_confidence,
        }

    def scan_until_found(self, symbols=None, timeframe=None, min_confidence=None,
                          max_symbols=None, delay_between=3):
        """
        نسخة "ابحث لحد ما تلاقي" - يمسح العملات بالترتيب ويتوقف فور
        إيجاد أول صفقة تحقق الحد المطلوب (أسرع من scan() الكامل).

        Args:
            max_symbols: حد أقصى لعدد العملات المفحوصة قبل الاستسلام
                (لتجنب استهلاك حصة API بلا نهاية لو ما في صفقات مطابقة)
        """
        symbols = symbols or Config.SCAN_SYMBOLS
        if max_symbols:
            symbols = symbols[:max_symbols]

        result = self.scan(
            symbols=symbols, timeframe=timeframe, min_confidence=min_confidence,
            delay_between=delay_between, stop_on_first_match=True,
        )

        if result["matches"]:
            best = result["matches"][0]
            self.logger.info(
                f"🎯 وجدت صفقة: {best['symbol']} {best['signal']} "
                f"بثقة {best['confidence']}%"
            )
        else:
            self.logger.info(
                f"😐 لا توجد صفقة تحقق الحد ({result['min_confidence_used']}%) "
                f"من أصل {result['scanned']} عملة مفحوصة"
            )

        return result

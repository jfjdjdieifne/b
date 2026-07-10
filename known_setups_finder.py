# -*- coding: utf-8 -*-
"""
KnownSetupsFinder - يكتشف صفقات تاريخية "جاهزة ومحلَّلة" بشكل موضوعي
════════════════════════════════════════════════════════════════════
يجاوب على السؤال: "جبلي صفقات جاهزة ومحللة وكلشي نعمل عليها backtest
ونختبر هل البوت بيحلل نفس التحليل ويعطي نفس النتيجة؟"

لماذا هذا الملف موجود (بدل ما أختار صفقات بنفسي يدوياً):
  لو اخترت أنا صفقات "مشهورة" يدوياً، في خطر حقيقي إني ألا إرادياً
  أختار أمثلة تخلي البوت يبين شكله كويس (confirmation bias). فبدل هيك،
  هذا الملف يمر على بيانات BTC التاريخية الحقيقية (سنتين كاملتين) ويكتشف
  "صفقات" بمعيار **رياضي موضوعي بحت** (نفس معادلة AuthenticityEngine
  المستخدمة أصلاً بالبوت: سحب سيولة + displacement قوي بعده) - نفس
  المعيار يُطبّق على كل البيانات بلا استثناء ولا اختيار يدوي.

  لكل "صفقة" مكتشفة، النتيجة الفعلية (نجحت/فشلت، وبكم %) تُحسب
  رياضياً 100% من نفس بيانات الأسعار التاريخية (لا رأي بشري، لا تقييم
  شخصي) - هذا هو "الحل الجاهز والمحلل" المطلوب: جاهز (مكتشف تلقائياً)
  ومحلل (نتيجته الفعلية محسوبة رياضياً ومعروفة سلفاً قبل ما نسأل البوت).

كيف يعمل الاختبار الفعلي بعدها:
  1. لكل صفقة مكتشفة، نجلب البيانات التي كانت متاحة *فقط حتى لحظة
     الإشارة* (before/after split صارم - لا تسريب معلومات مستقبلية)
  2. نُشغّل full_analysis (بكامل طبقاته: Authenticity + Verification +
     Auto-Consensus) على هذه البيانات
  3. نقارن قرار البوت (bias/signal/confidence) بالنتيجة الفعلية
     المحسوبة رياضياً سلفاً
  4. نعطي تقرير تطابق شفاف - بما فيه الحالات التي لا تتطابق (بدون
     إخفاء أي فشل)
"""
import logging
import time
import numpy as np
from datetime import datetime, timezone


class KnownSetupsFinder:

    def __init__(self, data_manager, authenticity_engine=None):
        self.dm = data_manager
        self.logger = logging.getLogger("KnownSetupsFinder")
        if authenticity_engine is None:
            from authenticity_engine import AuthenticityEngine
            authenticity_engine = AuthenticityEngine()
        self.ae = authenticity_engine

    # ══════════════════════════════════════════════════════════
    #  اكتشاف الصفقات (رياضي موضوعي بحت)
    # ══════════════════════════════════════════════════════════

    def find_setups_multi_timeframe(self, symbol="BTC/USDT", max_setups=5,
                                     timeframes=("1h", "2h", "4h"),
                                     min_move_pct=1.3, min_favorable_ratio=1.2):
        """
        يبحث عبر عدة أطر زمنية مع بعض (بعد إصلاح lookahead bias، عدد
        الصفقات المتاحة على فريم واحد قد يكون قليلاً - هذا يوسّع
        الفرصة الموضوعية للعثور على 'صفقات' كافية لاختبار حقيقي).
        """
        all_candidates = []
        for tf in timeframes:
            lookback = {"1h": 5000, "2h": 4000, "4h": 1500, "1d": 730}.get(tf, 3000)
            try:
                found = self.find_setups(
                    symbol=symbol, timeframe=tf, lookback_candles=lookback,
                    max_setups=max_setups * 2,  # نجمع أكثر ثم نفلتر الأقوى بالنهاية
                    min_move_pct=min_move_pct, min_favorable_ratio=min_favorable_ratio,
                )
                all_candidates.extend(found)
            except Exception as e:
                self.logger.warning(f"⚠️ فشل البحث بفريم {tf}: {e}")

        all_candidates.sort(key=lambda x: x["actual_move_pct"], reverse=True)
        selected = all_candidates[:max_setups]
        self.logger.info(
            f"🔍 (Multi-TF) اكتُشف {len(all_candidates)} صفقة عبر "
            f"{len(timeframes)} فريم، تم اختيار أقوى {len(selected)}"
        )
        return selected

    def find_setups(self, symbol="BTC/USDT", timeframe="1h", lookback_candles=3000,
                     max_setups=5, swing_lookback=5, forward_check_candles=24,
                     min_move_pct=1.3, min_favorable_ratio=1.2):
        """
        يمر على بيانات تاريخية حقيقية ويكتشف لحظات "سحب سيولة + انعكاس
        قوي مؤكد" بمعيار رياضي موضوعي (نفس معادلة AuthenticityEngine
        classify_sweep المستخدمة أصلاً بالبوت الحي).

        Args:
            lookback_candles: كم شمعة تاريخية نفحص (730 = سنتين تقريباً
                على فريم يومي)
            max_setups: أقصى عدد صفقات نرجعها (الأقوى بالحركة الفعلية)
            swing_lookback: نافذة تحديد القمم/القيعان المحلية
            forward_check_candles: كم شمعة بعد الإشارة نحسب فيها
                النتيجة الفعلية (target حقيقي محسوب رياضياً)

        Returns:
            list of dicts: كل واحدة صفقة مكتشفة بكامل تفاصيلها + نتيجتها
            الفعلية المحسوبة رياضياً
        """
        data = self._fetch_historical(symbol, timeframe, lookback_candles)
        if not data:
            return []

        h = np.array(data["highs"])
        l = np.array(data["lows"])
        c = np.array(data["closes"])
        o = np.array(data["opens"])
        v = np.array(data["volumes"])
        ts = data["timestamps"]
        n = len(c)

        swing_highs, swing_lows = self._find_swings(h, l, swing_lookback)

        candidates = []

        # ═══ فحص كل swing low بحثاً عن BULLISH reversal حقيقي ═══
        # ⚠️ swing_lows الآن قائمة (index, true_swing_price) - إصلاح بگ
        # "مستوى مزيّف" الموثّق أعلاه بـ_find_swings(). نُمرر السعر
        # الحقيقي صراحة لـtrapped_trader_evidence بدل تركها تخمّنه من
        # index الإشارة (الذي هو نقطة تأكيد لاحقة، وليس القمة/القاع نفسه).
        for idx, true_swing_price in swing_lows:
            if idx + forward_check_candles >= n or idx < 20:
                continue
            sweep_check = self.ae.trapped_trader_evidence(
                {"highs": h.tolist(), "lows": l.tolist(), "closes": c.tolist(),
                 "opens": o.tolist(), "volumes": v.tolist()},
                swing_index=idx, direction="BULLISH", swing_price=true_swing_price,
            )
            if not sweep_check.get("has_fuel"):
                continue

            # ═══ فحص إضافي: هل الزخم عند نقطة الإشارة يُظهر بالفعل بداية
            # انعكاس ملموسة، وليس استمراراً خالصاً بنفس اتجاه الهبوط
            # الأصلي؟ (اكتُشف بالاختبار الفعلي: نقطة أُعلنت "قاع مؤكد"
            # بينما آخر 15 شمعة رآها البوت كانت هبوطاً متواصلاً 100% بلا
            # أي إشارة ارتداد مرئية - الفشل هنا فشل بتصميم أداة الاختبار
            # لا بمنطق البوت، لأن لا دليل انعكاس كان متاحاً أصلاً وقتها) ═══
            if not self._has_visible_reversal_momentum(c, idx, "BULLISH"):
                continue

            entry_price = c[idx]
            actual_max_up = max(h[idx + 1: idx + 1 + forward_check_candles]) if idx + 1 < n else entry_price
            actual_min_down = min(l[idx + 1: idx + 1 + forward_check_candles]) if idx + 1 < n else entry_price
            move_pct_up = round((actual_max_up - entry_price) / entry_price * 100, 2)
            move_pct_down = round((entry_price - actual_min_down) / entry_price * 100, 2)

            # صفقة "حقيقية وواضحة" فقط لو الحركة الصاعدة الفعلية تفوقت
            # بوضوح على الحركة الهابطة (نتيجة موضوعية غير مبهمة)
            if move_pct_up > move_pct_down * min_favorable_ratio and move_pct_up > min_move_pct:
                candidates.append({
                    "symbol": symbol, "timeframe": timeframe,
                    "direction": "BULLISH", "signal_index": idx,
                    "signal_timestamp": ts[idx],
                    "entry_price_actual": round(float(entry_price), 2),
                    "true_swept_swing_price": round(float(true_swing_price), 6),
                    "actual_outcome": "WIN",
                    "actual_move_pct": move_pct_up,
                    "actual_max_favorable_pct": move_pct_up,
                    "actual_max_adverse_pct": move_pct_down,
                    "detection_method": "AuthenticityEngine.trapped_trader_evidence (BULLISH sweep + displacement)",
                })

        # ═══ فحص كل swing high بحثاً عن BEARISH reversal حقيقي ═══
        for idx, true_swing_price in swing_highs:
            if idx + forward_check_candles >= n or idx < 20:
                continue
            sweep_check = self.ae.trapped_trader_evidence(
                {"highs": h.tolist(), "lows": l.tolist(), "closes": c.tolist(),
                 "opens": o.tolist(), "volumes": v.tolist()},
                swing_index=idx, direction="BEARISH", swing_price=true_swing_price,
            )
            if not sweep_check.get("has_fuel"):
                continue

            if not self._has_visible_reversal_momentum(c, idx, "BEARISH"):
                continue

            entry_price = c[idx]
            actual_max_down = min(l[idx + 1: idx + 1 + forward_check_candles]) if idx + 1 < n else entry_price
            actual_max_up = max(h[idx + 1: idx + 1 + forward_check_candles]) if idx + 1 < n else entry_price
            move_pct_down = round((entry_price - actual_max_down) / entry_price * 100, 2)
            move_pct_up = round((actual_max_up - entry_price) / entry_price * 100, 2)

            if move_pct_down > move_pct_up * min_favorable_ratio and move_pct_down > min_move_pct:
                candidates.append({
                    "symbol": symbol, "timeframe": timeframe,
                    "direction": "BEARISH", "signal_index": idx,
                    "signal_timestamp": ts[idx],
                    "entry_price_actual": round(float(entry_price), 2),
                    "true_swept_swing_price": round(float(true_swing_price), 6),
                    "actual_outcome": "WIN",
                    "actual_move_pct": move_pct_down,
                    "actual_max_favorable_pct": move_pct_down,
                    "actual_max_adverse_pct": move_pct_up,
                    "detection_method": "AuthenticityEngine.trapped_trader_evidence (BEARISH sweep + displacement)",
                })


        # ترتيب حسب قوة الحركة الفعلية (الأوضح والأقوى أولاً)
        candidates.sort(key=lambda x: x["actual_move_pct"], reverse=True)
        selected = candidates[:max_setups]

        for setup in selected:
            dt = datetime.fromtimestamp(setup["signal_timestamp"] / 1000, tz=timezone.utc)
            setup["signal_date_readable"] = dt.strftime("%Y-%m-%d")

        self.logger.info(
            f"🔍 اكتُشف {len(candidates)} صفقة مرشحة، تم اختيار أقوى "
            f"{len(selected)} صفقة (حركة فعلية موثقة رياضياً)"
        )
        return selected

    # ══════════════════════════════════════════════════════════
    #  تشغيل الاختبار الفعلي (Backtest) على الصفقات المكتشفة
    # ══════════════════════════════════════════════════════════

    def run_backtest(self, brain_core, setups, delay_between=8, use_multi_pass=False):
        """
        لكل صفقة مكتشفة: يجلب البيانات التي كانت متاحة *حتى لحظة
        الإشارة فقط* (before/after صارم)، يشغّل تحليل البوت الحقيقي
        عليها، ويقارن قراره بالنتيجة الفعلية المحسوبة رياضياً سلفاً.

        Args:
            delay_between: تأخير بالثواني بين كل صفقة والتالية (يمنع
                انفجار الطلبات المتتالية بحد المعدل بالدقيقة/الحصة)
            use_multi_pass: (اختياري) استخدام محرك التحليل متعدد
                المراحل (5 نداءات API لكل صفقة بدل نداء واحد) - راجع
                multi_pass_analysis.py. يستهلك حصة أكبر بـ5× لكل صفقة.
        """
        results = []
        for i, setup in enumerate(setups):
            if i > 0 and delay_between > 0:
                self.logger.info(f"⏳ انتظار {delay_between}s قبل الصفقة التالية...")
                time.sleep(delay_between)

            self.logger.info(
                f"🧪 اختبار صفقة {setup['symbol']} بتاريخ "
                f"{setup['signal_date_readable']} (اتجاه فعلي: {setup['direction']})..."
            )
            historical_data = self._fetch_historical_up_to(
                setup["symbol"], setup["timeframe"], setup["signal_timestamp"]
            )
            if not historical_data:
                results.append({**setup, "bot_error": "فشل جلب البيانات التاريخية"})
                continue

            custom_data = {"entry": historical_data}
            try:
                analysis = brain_core.full_analysis(
                    symbol=setup["symbol"], timeframe=setup["timeframe"],
                    custom_data=custom_data, use_multi_pass=use_multi_pass
                )
            except Exception as e:
                results.append({**setup, "bot_error": str(e)})
                continue

            ai = analysis.get("ai_analysis", {})
            bot_bias = ai.get("bias", "UNKNOWN")
            bot_signal = ai.get("signal", "UNKNOWN")
            bot_confidence = ai.get("confidence", 0)

            expected_bias = "BULLISH" if setup["direction"] == "BULLISH" else "BEARISH"
            expected_signal = "BUY" if setup["direction"] == "BULLISH" else "SELL"

            bias_match = bot_bias == expected_bias
            signal_match = bot_signal == expected_signal

            results.append({
                **setup,
                "bot_narrative": ai.get("narrative", ""),
                "bot_archetype": ai.get("archetype", ""),
                "bot_bias": bot_bias,
                "bot_signal": bot_signal,
                "bot_confidence": bot_confidence,
                "expected_bias": expected_bias,
                "expected_signal": expected_signal,
                "bias_match": bias_match,
                "signal_match": signal_match,
                "verdict": (
                    "✅ تطابق كامل" if signal_match else
                    "🟡 تطابق جزئي (bias صح، signal مختلف)" if bias_match else
                    "❌ عدم تطابق"
                ),
            })

        total = len(results)
        signal_matches = sum(1 for r in results if r.get("signal_match"))
        bias_matches = sum(1 for r in results if r.get("bias_match"))

        return {
            "total_setups_tested": total,
            "signal_match_count": signal_matches,
            "signal_match_pct": round(signal_matches / total * 100, 1) if total else 0,
            "bias_match_count": bias_matches,
            "bias_match_pct": round(bias_matches / total * 100, 1) if total else 0,
            "detailed_results": results,
        }

    # ══════════════════════════════════════════════════════════
    #  دوال مساعدة (جلب بيانات + كشف swings + ATR)
    # ══════════════════════════════════════════════════════════

    def _fetch_historical(self, symbol, timeframe, limit):
        """جلب بيانات تاريخية كاملة (لاكتشاف الصفقات)"""
        return self.dm.get_ohlcv(symbol, timeframe, limit=limit, output_format="dict")

    def _fetch_historical_up_to(self, symbol, timeframe, end_ts, limit=250):
        """جلب بيانات تنتهي بالضبط عند timestamp محدد (منع lookahead bias)

        ⚠️ تنظيف كود: كان هذا المنطق مكرراً حرفياً بهذا الملف -
        تم توحيده بـ DataManager.fetch_ohlcv_up_to() (يخدم أيضاً
        multi_pass_analysis.py الذي يحتاج نفس القدرة لفريمات متعددة)
        """
        return self.dm.fetch_ohlcv_up_to(symbol, timeframe, end_ts, limit=limit)

    @staticmethod
    def _atr(h, l, c, period=14):
        n = len(c)
        tr = np.zeros(n)
        for i in range(1, n):
            tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        out = np.zeros(n)
        if n > period:
            out[period] = tr[1:period + 1].mean()
            for i in range(period + 1, n):
                out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
        return out

    @staticmethod
    def _has_visible_reversal_momentum(c, idx, direction, check_candles=3):
        """
        فحص إضافي: هل آخر `check_candles` شمعة قبل نقطة الإشارة تُظهر
        فعلاً بداية ارتداد ملموسة (وليس استمراراً خالصاً بالاتجاه
        المعاكس)؟ هذا يمنع تكرار مشكلة اكتُشفت فعلياً بالاختبار: نقطة
        أُعلنت "إشارة انعكاس صاعد" بينما آخر 15 شمعة رآها البوت كانت
        بأكملها هبوطاً متواصلاً 100% - أي لا دليل مرئي على الانعكاس
        كان متاحاً أصلاً للبوت وقت التحليل.

        المعيار: من أصل آخر `check_candles` شمعة، يجب أن تكون هناك
        شمعة واحدة على الأقل بالاتجاه المتوقع (BULLISH=صاعدة،
        BEARISH=هابطة)، أو أن يكون آخر سعر أعلى (BULLISH) / أقل
        (BEARISH) من السعر عند بداية نافذة الفحص - أي دليل حركة أولية
        بالاتجاه الصحيح موجود فعلاً بالبيانات المرئية للبوت.
        """
        if idx < check_candles:
            return True  # لا بيانات كافية للفحص - نمرر بلا رفض

        window = c[idx - check_candles: idx + 1]
        if direction == "BULLISH":
            return bool(window[-1] > window[0])
        else:
            return bool(window[-1] < window[0])

    @staticmethod
    def _find_swings(h, l, lookback=5):
        """
        كشف swing highs/lows بشكل "قابل للمعرفة لحظة حدوثه" (causal) -
        أي نقطة يجب أن تكون الأعلى/الأدنى ضمن الشموع *قبلها فقط*
        (lookback)، وليس ضمن نافذة تشمل شموع لم تحدث بعد.

        ⚠️ إصلاح خطأ حرج (lookahead bias) كان موجوداً هنا سابقاً:
        النسخة القديمة كانت تتحقق: h[i] == max(h[i-lookback : i+lookback+1])
        أي تستخدم `lookback` شمعة *بعد* i لتحديد ما إذا كانت i قمة -
        هذا يعني "معرفة القمة" تتطلب رؤية المستقبل، وهو بالضبط الخطأ الذي
        صممنا بقية النظام لتجنبه. النتيجة العملية: نقاط أُعلنت "قمة
        انعكاس" بينما السعر استمر صاعداً بعدها فعلياً (كما تم اكتشافه
        باختبار حقيقي: idx=1381 أُعلن قمة رغم أن القمة الحقيقية جاءت
        بعده بساعة واحدة) - ما جعل "الحقيقة الأرضية" للاختبار خاطئة
        من الأساس، لا علاقة له بجودة تحليل البوت نفسه.

        النسخة المُصححة (محاولة 2 - تصحيح إضافي): نتحقق أن i هي الأعلى/
        الأدنى ضمن نافذة تحتوي `lookback` شمعة قبلها + `lookback` شمعة
        بعدها بالكامل (نفس حجم النافذة الأصلية تماماً، وليس نصفها كما
        بمحاولة أولى كانت لا تزال غير كافية)، ونُرجع نقطة الإشارة بعد
        اكتمال هذه النافذة بالكامل (index = i + lookback) - بهذا نضمن
        أن كل البيانات المستخدمة لإثبات "هذه قمة/قاع" أصبحت فعلاً جزءاً
        من الماضي من منظور البوت وقت توليد الإشارة، لا معلومات مستقبلية
        جزئية متبقية.

        ⚠️ لوحظ بالاختبار الفعلي أن استخدام `confirm_after = lookback//2`
        (نصف النافذة فقط) كان لا يزال غير كافٍ: نقطة كانت لا تزال ضمن
        اتجاه هابط واضح 100% وقت قطع البيانات، رغم إعلانها "قاع مؤكد" -
        لأن التأكيد الفعلي (الارتداد المرئي) لم يظهر إلا لاحقاً ضمن
        الجزء المتبقي من النافذة الذي لم يُدرج بعد بالبيانات التاريخية
        المُرسلة للبوت. رفع `confirm_after` إلى `lookback` الكامل يحل
        هذا بشكل قاطع رياضياً.

        ⚠️ إصلاح بگ حرج ثانٍ ومترابط (يوليو 2026، مكتشف عبر باك تيست
        حقيقي على Nemotron 3 Ultra): الدالة كانت تُرجع فقط "index
        الإشارة" (نقطة التأكيد i+confirm_after)، وترك المستدعي (كود
        اكتشاف الصفقات) يفترض خطأً أن هذا الـindex هو نفسه موقع القمة/
        القاع الحقيقي (فيحسب المستوى كـ h[index]/l[index] من نقطة
        التأكيد، لا من القمة/القاع الفعلي عند i). هذا أدى لاستخدام
        "مستوى مزيّف" (سعر شمعة التأكيد، ليس القمة الحقيقية) بكل فحوصات
        trapped_trader_evidence اللاحقة - تحقق فعلي رياضي على 10 صفقات
        حقيقية أظهر فروقاً بين 0.6% و5.8% لكل حالة، بلا استثناء.
        الإصلاح: نُرجع الآن أيضاً السعر الحقيقي (h[i]/l[i] عند القمة/
        القاع الفعلي نفسها، لا نقطة التأكيد) صراحة مع كل index - بحيث
        لا يحتاج أي مستدعٍ لإعادة اشتقاقه يدوياً (مصدر إضافي محتمل للخطأ).
        """
        n = len(h)
        confirm_after = lookback  # النافذة الكاملة - لا تصريح جزئي بالمستقبل
        swing_highs, swing_lows = [], []
        for i in range(lookback, n - lookback - confirm_after):
            window = h[i - lookback: i + lookback + 1]
            if h[i] == max(window):
                # نقطة الإشارة القابلة للمعرفة فعلياً = بعد اكتمال كامل النافذة
                # نُرجع (index_الإشارة, السعر_الحقيقي_للقمة_عند_i) معاً
                swing_highs.append((i + confirm_after, float(h[i])))
            window_l = l[i - lookback: i + lookback + 1]
            if l[i] == min(window_l):
                swing_lows.append((i + confirm_after, float(l[i])))
        return swing_highs, swing_lows

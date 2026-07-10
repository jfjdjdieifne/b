# -*- coding: utf-8 -*-
"""
AuthenticityEngine - محرك التحقق من صحة الإشارات (كشف الزيف والفخاخ)
════════════════════════════════════════════════════════════════════
هذا الملف يترجم قسمي [AUTHENTICITY_ENGINE] و [MASTER_TRADER_MINDSET]
من قاعدة المعرفة (data/trading_knowledge.txt) إلى حسابات رياضية فعلية
تُجرى على البيانات الخام (OHLCV) قبل ما توصل لل AI.

الهدف: بدل ما نعتمد فقط على "فهم" النموذج اللغوي للنص، نعطيه أرقام
جاهزة محسوبة فعلياً (Breakout Authenticity Score، فحص Wash Trading،
كشف الـ Fake Sweep، تقييم جودة الـ OB...) بحيث قراره يصير مبني على
أدلة رقمية صريحة، تماماً متل تاجر خبير بيحسب هالأشياء بلا وعي من
خبرته - لكن هون محسوبة صراحة وقابلة للتدقيق.

هذا المحرك لا يتخذ قرار BUY/SELL - هو فقط يزود طبقة "تحقق" رقمية
إضافية فوق TechnicalAnalyzer، والقرار النهائي يبقى للـ AI ضمن قواعد
الدستور.
"""
import logging
import re
import numpy as np


class AuthenticityEngine:
    """يفحص صحة/زيف الإشارات الفنية رياضياً قبل تمريرها للـ AI"""

    def __init__(self):
        self.logger = logging.getLogger("AuthenticityEngine")

    # ══════════════════════════════════════════════════════════
    #  21.2 - BREAKOUT AUTHENTICITY SCORE (0-6)
    # ══════════════════════════════════════════════════════════

    def breakout_authenticity_score(self, data, level_price, direction,
                                     break_index=-1, is_thin_pair=False,
                                     is_dead_zone=False):
        """
        يحسب "درجة صحة الاختراق" (0-6) حسب القسم 21.2 بالدستور.

        Args:
            data: dict فيه opens/highs/lows/closes/volumes
            level_price: السعر يلي المفروض انكسر (level)
            direction: "UP" أو "DOWN" (اتجاه الاختراق المزعوم)
            break_index: index الشمعة يلي صار فيها الاختراق (افتراضي: آخر شمعة)
            is_thin_pair: إذا العملة صغيرة/سيولة قليلة (يشدد المعايير)
            is_dead_zone: إذا الاختراق صار بوقت ميت (يشدد المعايير)

        Returns:
            dict فيه score (0-6)، verdict، وتفاصيل كل فحص
        """
        h = np.array(data["highs"], dtype=float)
        l = np.array(data["lows"], dtype=float)
        c = np.array(data["closes"], dtype=float)
        v = np.array(data["volumes"], dtype=float)
        n = len(c)

        if n < 25:
            return {"score": 0, "verdict": "INSUFFICIENT_DATA", "checks": {}}

        idx = break_index if break_index >= 0 else n - 1
        atr = self._atr(h, l, c)
        atr_val = atr[idx] if idx < len(atr) and atr[idx] > 0 else (h[idx] - l[idx])
        vol_avg20 = v[max(0, idx - 20):idx].mean() if idx >= 20 else v[:idx].mean() if idx > 0 else v[idx]
        vol_ratio = v[idx] / vol_avg20 if vol_avg20 > 0 else 1.0

        checks = {}

        # CHECK 1: CLOSE vs WICK
        if direction == "UP":
            closed_beyond = c[idx] > level_price
        else:
            closed_beyond = c[idx] < level_price
        checks["close_beyond_level"] = bool(closed_beyond)

        # CHECK 2: VOLUME ON THE BREAK
        checks["volume_confirms"] = bool(vol_ratio > 1.5)
        checks["vol_ratio"] = round(float(vol_ratio), 2)

        # CHECK 3: FOLLOW-THROUGH (2-3 شموع بعد الكسر)
        follow_through = None
        if idx + 1 < n:
            future = c[idx + 1: idx + 4]
            if len(future) > 0:
                if direction == "UP":
                    follow_through = bool(np.all(future >= level_price - atr_val * 0.1))
                else:
                    follow_through = bool(np.all(future <= level_price + atr_val * 0.1))
        checks["follow_through_confirmed"] = follow_through  # None لو ما في بيانات مستقبلية بعد

        # CHECK 4: WHO WAS WAITING THERE؟ (مستوى واضح/round number)
        is_round_level = self._is_round_number(level_price)
        checks["obvious_level"] = is_round_level
        # مستوى واضح = علامة استفهام إضافية، مو فحص "نجاح" مباشر بحد ذاته

        # CHECK 5: DISTANCE OF THE BREAK
        distance = abs((c[idx] if closed_beyond else h[idx] if direction == "UP" else l[idx]) - level_price)
        meaningful_distance = bool(distance >= 0.15 * atr_val) if atr_val > 0 else False
        checks["meaningful_distance"] = meaningful_distance
        checks["distance_atr_ratio"] = round(float(distance / atr_val), 3) if atr_val > 0 else 0

        # CHECK 6: TIME (ديد زون) - يأتي من الخارج (is_dead_zone)
        checks["not_dead_zone"] = not is_dead_zone

        # حساب الدرجة النهائية (6 فحوصات أساسية)
        score_items = [
            checks["close_beyond_level"],
            checks["volume_confirms"],
            bool(follow_through) if follow_through is not None else False,
            meaningful_distance,
            checks["not_dead_zone"],
            not is_round_level,  # عدم كونه مستوى واضح جداً = نقطة إضافية
        ]
        score = sum(1 for x in score_items if x)

        # تشديد المعايير على العملات الرقيقة
        threshold_pass = 4 if not is_thin_pair else 5

        # ⚠️ تصحيح (مراجعة شاملة يوليو 2026): نص الدستور [AUTHENTICITY_
        # ENGINE] 21.2 صريح: "6/6: Genuine break" و"4-5/6: Probably
        # genuine" - أي فقط الدرجة الكاملة 6/6 تُصنَّف GENUINE_BREAK.
        # النسخة السابقة صنّفت score>=5 كـGENUINE_BREAK (متضاربة مع
        # النص). ملاحظة: هذه الدالة غير مستدعاة حالياً بأي مسار حي
        # بالمشروع (فحص شامل مباشر: صفر استدعاء خارج تعريفها) - الإصلاح
        # وقائي لمنع خطأ كامن لو استُخدمت لاحقاً، لا تأثير على أي قرار حالي.
        if score >= 6:
            verdict = "GENUINE_BREAK"
        elif score >= threshold_pass:
            verdict = "PROBABLY_GENUINE"
        elif score >= 2:
            verdict = "SUSPICIOUS_TREAT_AS_SWEEP"
        else:
            verdict = "LIKELY_FAKE"

        return {
            "score": score,
            "max_score": 6,
            "verdict": verdict,
            "checks": checks,
            "is_thin_pair": is_thin_pair,
        }

    # ══════════════════════════════════════════════════════════
    #  21.3 - FAKE SWEEP vs GENUINE REVERSAL SWEEP
    # ══════════════════════════════════════════════════════════

    def classify_sweep(self, data, swing_price, sweep_index, direction):
        """
        يميّز بين Sweep حقيقي (انعكاس) و Sweep وهمي (استمرار/Run)
        حسب القسم 21.3 بالدستور.

        Args:
            direction: "BULLISH_REVERSAL_EXPECTED" (سحب سيولة سفلي، توقع صعود)
                       أو "BEARISH_REVERSAL_EXPECTED" (سحب سيولة علوي، توقع هبوط)
        """
        h = np.array(data["highs"], dtype=float)
        l = np.array(data["lows"], dtype=float)
        o = np.array(data["opens"], dtype=float)
        c = np.array(data["closes"], dtype=float)
        v = np.array(data["volumes"], dtype=float)
        n = len(c)

        if sweep_index < 0 or sweep_index >= n:
            return {"classification": "INVALID_INDEX"}

        atr = self._atr(h, l, c)
        atr_val = atr[sweep_index] if sweep_index < len(atr) and atr[sweep_index] > 0 else 1.0

        # هل السعر رجع داخل الرينج بعد الفتيل (wick)؟
        if direction == "BULLISH_REVERSAL_EXPECTED":
            wicked_beyond = l[sweep_index] < swing_price
            closed_back_inside = c[sweep_index] > swing_price
        else:
            wicked_beyond = h[sweep_index] > swing_price
            closed_back_inside = c[sweep_index] < swing_price

        if not wicked_beyond:
            return {"classification": "NO_SWEEP_DETECTED"}

        # فحص الـ displacement خلال 1-3 شموع بعد السحب
        displacement_found = False
        displacement_detail = None
        for j in range(sweep_index + 1, min(sweep_index + 4, n)):
            rng = h[j] - l[j]
            body = abs(c[j] - o[j])
            body_pct = body / rng if rng > 0 else 0
            vol_avg = v[max(0, j - 20):j].mean() if j >= 20 else v[:j].mean() if j > 0 else v[j]
            vol_ratio = v[j] / vol_avg if vol_avg > 0 else 1.0

            is_bullish = c[j] > o[j]
            direction_matches = (
                (direction == "BULLISH_REVERSAL_EXPECTED" and is_bullish) or
                (direction == "BEARISH_REVERSAL_EXPECTED" and not is_bullish)
            )

            if (direction_matches and rng > 1.5 * atr_val and
                    body_pct > 0.6 and vol_ratio > 1.5):
                displacement_found = True
                displacement_detail = {
                    "candle_index": j,
                    "range_atr_ratio": round(float(rng / atr_val), 2),
                    "body_pct": round(float(body_pct), 2),
                    "vol_ratio": round(float(vol_ratio), 2),
                }
                break

        if closed_back_inside and displacement_found:
            classification = "GENUINE_REVERSAL_SWEEP"
        elif closed_back_inside and not displacement_found:
            classification = "UNCONFIRMED_WAIT_FOR_DISPLACEMENT"
        else:
            classification = "LIKELY_CONTINUATION_RUN"

        return {
            "classification": classification,
            "wicked_beyond_level": bool(wicked_beyond),
            "closed_back_inside": bool(closed_back_inside),
            "displacement_confirmed": displacement_found,
            "displacement_detail": displacement_detail,
        }

    # ══════════════════════════════════════════════════════════
    #  21.3b - MOST RECENT SWEEP AUTO-DETECT + CLASSIFY
    # ══════════════════════════════════════════════════════════
    # ⚠️ إصلاح فجوة حقيقية: classify_sweep() أعلاه كانت موجودة منذ فترة
    # لكن **لم تكن مُستدعاة من أي مكان بالكود الفعلي** - الـ AI كان
    # يُترك يخمّن "Genuine مقابل Fake" بمعزل كامل عن أي حساب رقمي، رغم
    # وجود الأداة الرياضية جاهزة. هذه الدالة تبحث آلياً عن آخر سحب
    # سيولة (wick تجاوز قمة/قاع متأرجح سابق ثم رجع) خلال آخر
    # lookback_candles شمعة، وتصنّفه فوراً عبر classify_sweep() - نتيجة
    # جاهزة تُحقن بالـ prompt، فالـ AI يتحقق من تصنيف رياضي حقيقي بدل
    # أن يبتدعه من الصفر بتخمين لغوي بحت.

    def detect_most_recent_sweep(self, data, lookback_candles=15, swing_window=2):
        """
        يفحص آخر lookback_candles شمعة بحثاً عن أحدث sweep (فتيل تجاوز
        قمة/قاع متأرجح سابق مؤكد، بمعزل تام عن تلوث السوينغ بالشمعة
        نفسها - نفس منهجية detect_most_recent_bos تماماً)، ثم يصنّفه
        فوراً عبر classify_sweep(). يرجّع None إذا لا يوجد sweep واضح.
        """
        h = np.array(data.get("highs", []), dtype=float)
        l = np.array(data.get("lows", []), dtype=float)
        c = np.array(data.get("closes", []), dtype=float)
        n = len(c)
        if n < lookback_candles + swing_window * 2 + 5:
            return {"found": False, "reason": "INSUFFICIENT_DATA"}

        def _last_swing_high_before(idx_limit):
            best = None
            for j in range(swing_window, idx_limit - swing_window):
                if h[j] == max(h[j - swing_window:j + swing_window + 1]):
                    best = (j, h[j])
            return best

        def _last_swing_low_before(idx_limit):
            best = None
            for j in range(swing_window, idx_limit - swing_window):
                if l[j] == min(l[j - swing_window:j + swing_window + 1]):
                    best = (j, l[j])
            return best

        start = n - lookback_candles
        best_sweep = None  # آخر sweep (الأحدث، وليس بالضرورة الأوضح)

        for i in range(start, n):
            if i < 1:
                continue
            sh_match = _last_swing_high_before(i)
            sl_match = _last_swing_low_before(i)

            # فتيل علوي تجاوز قمة سابقة (احتمال Sweep هابط التوقع)
            if sh_match and h[i] > sh_match[1]:
                result = self.classify_sweep(
                    data, sh_match[1], i, "BEARISH_REVERSAL_EXPECTED"
                )
                if result.get("classification") not in ("NO_SWEEP_DETECTED", "INVALID_INDEX"):
                    best_sweep = {
                        "swept_level_price": round(float(sh_match[1]), 4),
                        "sweep_candle_index_from_end": i - n,
                        "swing_type_swept": "PRIOR_SWING_HIGH",
                        **result,
                    }

            # فتيل سفلي تجاوز قاع سابق (احتمال Sweep صاعد التوقع)
            if sl_match and l[i] < sl_match[1]:
                result = self.classify_sweep(
                    data, sl_match[1], i, "BULLISH_REVERSAL_EXPECTED"
                )
                if result.get("classification") not in ("NO_SWEEP_DETECTED", "INVALID_INDEX"):
                    best_sweep = {
                        "swept_level_price": round(float(sl_match[1]), 4),
                        "sweep_candle_index_from_end": i - n,
                        "swing_type_swept": "PRIOR_SWING_LOW",
                        **result,
                    }

        if best_sweep is None:
            return {"found": False}

        best_sweep["found"] = True
        return best_sweep

    # ══════════════════════════════════════════════════════════
    #  SIGNIFICANT SWINGS (يميّز "القمة/القاع المهم فعلياً" عن
    #  "النتوء المحلي الصغير") - إصلاح خطأ حقيقي موثّق باختبار
    #  reading_comprehension_test الفعلي:
    #  البوت ادّعى قمماً متأرجحة (مثل 3251.49, 3159.79) كانت موجودة
    #  فعلياً بالبيانات (لا هلوسة أسعار) لكنها لم تكن "قمماً مهمة" -
    #  كانت نتوءات محلية صغيرة (±2 شمعة بس) بينما توجد قمة أعلى بكثير
    #  مجاورة تُلغي أهميتها الفعلية كمستوى مقاومة/سيولة. المعيار
    #  المحلي البحت (swing_window=2، "أعلى من الجارتين فقط") غير كافٍ
    #  لتمييز "قمة استراتيجية" عن "تعرّج عابر بمسار الشمعة".
    # ══════════════════════════════════════════════════════════

    def detect_significant_swings(self, data, swing_window=2, lookback_candles=60,
                                   prominence_window=10, top_n=5):
        """
        يحسب القمم/القيعان المتأرجحة "المهمة فعلياً" عبر خوارزمية
        "الأهمية الطوبوغرافية" (Topographic Prominence) - نفس المعيار
        الرياضي القياسي المستخدم لتحديد "قمة جبل مستقلة حقيقية"
        جغرافياً، مُطبَّع هنا بوحدات ATR (يتكيّف تلقائياً مع أي مستوى
        تقلب/فريم زمني/عملة، لا رقم سحري ثابت قد يفشل خارج سياق اختباره).

        ⚠️ إعادة تصميم كاملة (يوليو 2026)، بعد اكتشافين حقيقيين متتاليين
        بمقارنة Gemini/gemma:
        (1) النسخة الأولى (قرار ثنائي، نافذة ثابتة) كانت تُلغي أي قمة
            لا تصمد على نافذة واحدة، فتُعاقِب نموذجاً ذكر قمة مهمة
            تكتيكياً كأنه أخطأ تماماً.
        (2) محاولة إصلاح بـ3 نوافذ ثابتة متدرجة (ضيقة/متوسطة/واسعة)
            بقيت تعاني من نفس الخلل الجذري: تقارن القمة بـ"أعلى نقطة
            مطلقة بنافذة" بمعزل عن كون هذه النقطة الأعلى بعيدة جداً
            (مثال حقيقي موثّق: قمة 3273.33 أُلغيت بالكامل بسبب وجود
            قمة 3448.0 أعلى منها، رغم أن 3273.33 شكّلت قمة حقيقية بنمط
            Lower-Highs واضح - السعر ارتد عنها بوضوح من الجهتين، وهي
            جزء من هيكل هابط حقيقي يستحق الذكر).

        الحل الصحيح: "الأهمية الطوبوغرافية" الحقيقية - لكل قمة مرشحة،
        نحسب: كم "عمق الهبوط" الحقيقي على جهة اليسار وجهة اليمين قبل
        الوصول لنقطة تساويها أو تتجاوزها فعلاً (أو حافة البيانات).
        الأهمية = ارتفاع القمة ناقص أعمق "قاعدة" بين أعمق نقطتين على
        الجهتين. هذا يميّز صح "قمة مستقلة حقيقية بحد ذاتها" (حتى لو
        أصغر من قمة أخرى بعيدة) عن "درجة على منحدر قمة أكبر مجاورة".
        نُطبّعها بوحدات ATR (متوسط المدى الحقيقي) بدل سعر مطلق - هذا
        يحل مسبقاً مشكلة "قد يفشل هذا المعيار على عملة/فريم مختلف
        بتقلب مختلف تماماً" قبل أن تحدث فعلياً.

        Tiers (حسب نسبة الأهمية/ATR):
          - MAJOR: prominence >= 4×ATR (قمة/قاع مستقل بارز جداً)
          - MODERATE: prominence >= 1.5×ATR (مهم تكتيكياً، حقيقي)
          - MINOR: prominence >= 0.5×ATR (نتوء صغير لكن ليس ضجيجاً بحتاً)
          - (أقل من ذلك): ضجيج محلي حقيقي، يُستبعد كلياً
          - UNCONFIRMED_RECENT: قريب جداً من نهاية البيانات (لا "مستقبل"
            كافٍ ليصمد/يُلغى بعدل) - لا يُحاسَب النموذج بصرامة عليه.

        Returns dict:
            {
                "significant_highs": [{"index_from_end", "price"}],  # توافق خلفي (MAJOR+MODERATE)
                "significant_lows": [...],
                "all_highs_tiered": [{"index_from_end","price","tier","prominence_atr"}],
                "all_lows_tiered": [...],
                "minor_swings_filtered_count": int,
            }
        """
        h = np.array(data.get("highs", []), dtype=float)
        l = np.array(data.get("lows", []), dtype=float)
        c = np.array(data.get("closes", []), dtype=float)
        n = len(h)
        if n < swing_window * 2 + 5:
            return {
                "significant_highs": [], "significant_lows": [],
                "all_highs_tiered": [], "all_lows_tiered": [],
                "minor_swings_filtered_count": 0,
            }

        atr = self._atr(h, l, c)
        # ATR متوسط على كل النافذة المتاحة (مرجع تطبيع ثابت ومستقر، لا
        # يتذبذب حسب اللحظة - يحمي من انحياز لحظي بتقلب حاد مؤقت)
        valid_atr = atr[atr > 0]
        atr_ref = float(np.mean(valid_atr)) if len(valid_atr) > 0 else 1.0
        if atr_ref <= 0:
            atr_ref = 1.0

        start = max(swing_window, n - lookback_candles)

        raw_highs, raw_lows = [], []
        for i in range(start, n - swing_window):
            if h[i] == max(h[i - swing_window:i + swing_window + 1]):
                raw_highs.append(i)
            if l[i] == min(l[i - swing_window:i + swing_window + 1]):
                raw_lows.append(i)
        # الشمعة الأخيرة فعلياً (n-1) تُفحص بنافذة نصف مفتوحة (لا مستقبل بعدها)
        if n - 1 >= start and h[n - 1] == max(h[max(0, n - 1 - swing_window):n]):
            raw_highs.append(n - 1)
        if n - 1 >= start and l[n - 1] == min(l[max(0, n - 1 - swing_window):n]):
            raw_lows.append(n - 1)

        def _true_prominence(idx, arr, is_high):
            """
            خوارزمية الأهمية الطوبوغرافية القياسية: يمسح يساراً حتى نقطة
            أعلى/أدنى فعلياً (أو حافة البيانات)، يسجّل أعمق نقطة بالطريق؛
            نفس الشيء يميناً؛ الأهمية = القيمة ناقص (أو زائد للقيعان)
            أعمق/أشح نقطة بين الجهتين (القاعدة المشتركة الفعلية).
            """
            v = arr[idx]

            # يسار
            left_extreme = v
            j = idx - 1
            found_higher_left = False
            while j >= 0:
                if is_high:
                    left_extreme = min(left_extreme, arr[j])
                    if arr[j] >= v:
                        found_higher_left = True
                        break
                else:
                    left_extreme = max(left_extreme, arr[j])
                    if arr[j] <= v:
                        found_higher_left = True
                        break
                j -= 1
            left_base = left_extreme

            # يمين
            right_extreme = v
            j = idx + 1
            found_higher_right = False
            while j < n:
                if is_high:
                    right_extreme = min(right_extreme, arr[j])
                    if arr[j] >= v:
                        found_higher_right = True
                        break
                else:
                    right_extreme = max(right_extreme, arr[j])
                    if arr[j] <= v:
                        found_higher_right = True
                        break
                j += 1
            right_base = right_extreme

            # ⚠️ إذا لم يوجد نقطة أعلى/أدنى على إحدى الجهتين (حافة
            # البيانات فعلياً)، تلك الجهة لا تُقيّد الأهمية - نعتمد فقط
            # على الجهة التي فعلاً "حاصرت" القمة بنقطة معاكسة حقيقية.
            # لو الجهتان بلا حصر (حالة نادرة جداً، سلسلة قصيرة)، نعتبرها
            # غير مؤكدة الأهمية بدل افتراض قيمة قد تكون خاطئة.
            if not found_higher_left and not found_higher_right:
                return None
            if not found_higher_left:
                base = right_base
            elif not found_higher_right:
                base = left_base
            else:
                base = max(left_base, right_base) if is_high else min(left_base, right_base)

            prominence = (v - base) if is_high else (base - v)
            return max(0.0, float(prominence))

        def _classify(idx, arr, is_high):
            candles_remaining = (n - 1) - idx
            # نافذة تأكيد أدنى معقولة (نسبياً لحجم البيانات، لا رقم مطلق
            # جامد) - يضمن مستقبلاً كافياً ليُحكم على القمة بعدل
            min_confirm_candles = max(3, swing_window * 3)
            if candles_remaining < min_confirm_candles:
                return "UNCONFIRMED_RECENT", None

            prom = _true_prominence(idx, arr, is_high)
            if prom is None:
                return "UNCONFIRMED_RECENT", None  # لا حصر كافٍ لتقييم عادل

            ratio = prom / atr_ref
            if ratio >= 4.0:
                return "MAJOR", round(ratio, 2)
            if ratio >= 1.5:
                return "MODERATE", round(ratio, 2)
            if ratio >= 0.5:
                return "MINOR", round(ratio, 2)
            return None, round(ratio, 2)  # ضجيج محلي حقيقي - يُستبعد كلياً

        highs_tiered = []
        for i in sorted(set(raw_highs)):
            tier, prom_ratio = _classify(i, h, True)
            if tier:
                highs_tiered.append({
                    "index_from_end": i - n, "price": round(float(h[i]), 4),
                    "tier": tier, "prominence_atr": prom_ratio,
                })

        lows_tiered = []
        for i in sorted(set(raw_lows)):
            tier, prom_ratio = _classify(i, l, False)
            if tier:
                lows_tiered.append({
                    "index_from_end": i - n, "price": round(float(l[i]), 4),
                    "tier": tier, "prominence_atr": prom_ratio,
                })

        total_raw = len(set(raw_highs)) + len(set(raw_lows))
        total_tiered = len(highs_tiered) + len(lows_tiered)
        filtered_count = total_raw - total_tiered  # ضجيج محلي حقيقي مُستبعد كلياً

        # ── توافق خلفي: significant_highs/lows تشمل فقط MAJOR+MODERATE ──
        significant_highs = [
            {"index_from_end": s["index_from_end"], "price": s["price"]}
            for s in highs_tiered if s["tier"] in ("MAJOR", "MODERATE")
        ][-top_n:]
        significant_lows = [
            {"index_from_end": s["index_from_end"], "price": s["price"]}
            for s in lows_tiered if s["tier"] in ("MAJOR", "MODERATE")
        ][-top_n:]

        return {
            "significant_highs": significant_highs,
            "significant_lows": significant_lows,
            "all_highs_tiered": highs_tiered,
            "all_lows_tiered": lows_tiered,
            "minor_swings_filtered_count": filtered_count,
        }

    # ══════════════════════════════════════════════════════════
    #  20.x - COMPUTE STRUCTURE SEQUENCE (حل جذري لمشكلة "إعادات
    #  المحاولة الكثيرة بسبب تصنيف HH/HL/LH/LL خاطئ")
    # ══════════════════════════════════════════════════════════
    #
    # ⚠️ إعادة تصميم جذرية (يوليو 2026، بطلب صريح من المستخدم):
    # "سبب إعادات المحاولات يلي عم تاخد وقت وطلبات زيادة كتير متل
    # القمم والقيعان ويلي نحنا قادرين نحسبها رياضياً، نحسبها رياضياً
    # أول شي بعدين نمررها للبوت يحللها كفهم ويتأكد منها".
    #
    # قبل هذا الإصلاح: النموذج كان يُطلب منه أن *يشتق بنفسه* أي نقطة
    # مهمة هي HH/HL/LH/LL بمقارنتها ذهنياً بالقمة/القاع السابقة - وهذا
    # بالضبط مصدر كل أخطاء audit_structure_labels الموثّقة (SEQUENCE_
    # CONTRADICTION، MECHANICAL_SWING_CONTRADICTION، NOT_A_REAL_SWING_
    # POINT) التي كانت تتطلب 1-2 إعادة محاولة كاملة (كل واحدة = نداء
    # API إضافي كامل، دقائق من الوقت) لتصحيحها بعد الحدوث.
    #
    # الحل الجذري: بدل ترك النموذج "يخترع" التصنيف من الصفر ثم نصححه
    # لاحقاً، نحسب التسلسل الكامل (HH/HL/LH/LL) رياضياً بحتاً هنا -
    # بلا أي تدخل من الذكاء الاصطناعي - ونمرره كـ"حقيقة جاهزة" للنموذج.
    # مهمة النموذج تتحول من "احسب أنت أيهما HH وأيهما LH" (عرضة للخطأ)
    # إلى "تحقق من هذا التصنيف الجاهز، فسّره، واربطه بالقصة السردية،
    # وأخبرنا فوراً لو رأيت نقطة أهم لم تُدرَج هنا مع تبرير رقمي صريح"
    # (فهم وتحقق، لا اختراع من الصفر) - هذا بالضبط ما طلبه المستخدم.
    #
    # الخوارزمية:
    #   1. نأخذ فقط القمم/القيعان "المهمة فعلياً" (MAJOR+MODERATE من
    #      detect_significant_swings أعلاه - نفس الفلترة ضد الضجيج
    #      المحلي المستخدمة أصلاً، لا حاجة لإعادة اختراعها).
    #   2. لكل قمة بترتيبها الزمني الحقيقي، نقارنها رياضياً (>) بالقمة
    #      السابقة زمنياً من نفس النوع => HH أو LH بشكل قاطع 100%.
    #   3. نفس الشيء للقيعان (< => LL، وإلا HL).
    #   4. أول نقطة من كل نوع بلا مرجع سابق تُصنَّف "FIRST_IN_WINDOW"
    #      (لا افتراض قد يكون خاطئاً بلا مرجع فعلي للمقارنة).
    #
    # هذا لا يستبدل audit_structure_labels (يبقى كطبقة دفاع ثانية
    # مستقلة لو النموذج تجاهل التصنيف الجاهز وادّعى تصنيفاً مختلفاً)،
    # لكنه يمنع أغلب الأخطاء *قبل* حدوثها بدل تصحيحها *بعد* حدوثها -
    # يقلل إعادات المحاولة الفعلية بشكل كبير مع الحفاظ على نفس الدقة
    # (أو أعلى، لأن التصنيف الآن مضمون رياضياً 100% لا احتمالياً).

    def compute_structure_sequence(self, data, top_n=6):
        """
        يحسب تسلسل HH/HL/LH/LL كاملاً رياضياً بحتاً (بلا أي مدخل AI)
        من القمم/القيعان المهمة فعلياً (يستدعي detect_significant_swings
        داخلياً - نفس معيار الأهمية الطوبوغرافية، لا ازدواجية منطق).

        Returns dict:
            {
                "labeled_highs": [{"index_from_end", "price", "label"}],
                "labeled_lows": [{"index_from_end", "price", "label"}],
                "sequence_narrative": str,  # نص جاهز يُحقن مباشرة بالبرومبت
            }
        حيث label ∈ {"HH", "LH", "HL", "LL", "FIRST_IN_WINDOW"}.
        """
        swings = self.detect_significant_swings(data, top_n=top_n)
        # كل النقاط الحقيقية (MAJOR/MODERATE/MINOR) - لا فقط أعلى top_n
        # (حل جذري ثانِ: الاقتصار على significant_highs/lows وحدها
        # كان يحرم الموديل من نقاط MINOR حقيقية يحتاجها للشرح،
        # فاضطر لاختراعها بنفسه - صفقة ETH #8 الموثّقة).
        highs = [
            {"index_from_end": h["index_from_end"], "price": h["price"]}
            for h in swings.get("all_highs_tiered", [])
            if h.get("tier") in ("MAJOR", "MODERATE", "MINOR")
        ]
        lows = [
            {"index_from_end": l["index_from_end"], "price": l["price"]}
            for l in swings.get("all_lows_tiered", [])
            if l.get("tier") in ("MAJOR", "MODERATE", "MINOR")
        ]

        def _label_sequence(points, higher_label, lower_label):
            # points already sorted oldest->newest (detect_significant_swings
            # builds them in ascending index order, top_n keeps the most
            # recent N - order is preserved chronologically).
            labeled = []
            prev_price = None
            for p in points:
                if prev_price is None:
                    label = "FIRST_IN_WINDOW"
                else:
                    label = higher_label if p["price"] > prev_price else lower_label
                labeled.append({
                    "index_from_end": p["index_from_end"],
                    "price": p["price"],
                    "label": label,
                })
                prev_price = p["price"]
            return labeled

        labeled_highs = _label_sequence(highs, "HH", "LH")
        labeled_lows = _label_sequence(lows, "HL", "LL")

        lines = []
        if labeled_highs:
            parts = []
            for h in labeled_highs:
                tag = h["label"] if h["label"] != "FIRST_IN_WINDOW" else "first swing high in window (no prior reference)"
                parts.append(f"idx {h['index_from_end']} price {h['price']} = {tag}")
            lines.append("Swing HIGHS labeled (MATHEMATICALLY COMPUTED, not your judgment - chronological order): " + "; ".join(parts) + ".")
        if labeled_lows:
            parts = []
            for l in labeled_lows:
                tag = l["label"] if l["label"] != "FIRST_IN_WINDOW" else "first swing low in window (no prior reference)"
                parts.append(f"idx {l['index_from_end']} price {l['price']} = {tag}")
            lines.append("Swing LOWS labeled (MATHEMATICALLY COMPUTED, not your judgment - chronological order): " + "; ".join(parts) + ".")

        sequence_narrative = "\n".join(lines)

        return {
            "labeled_highs": labeled_highs,
            "labeled_lows": labeled_lows,
            "sequence_narrative": sequence_narrative,
        }

    # ══════════════════════════════════════════════════════════
    #  21.4 - OB RED FLAGS (فحص جودة/صحة Order Block)
    # ══════════════════════════════════════════════════════════

    def validate_order_block(self, data, ob_index, ob_top, ob_bottom,
                              direction, tests_count=0, htf_supports=True,
                              already_closed_through=False):
        """
        يفحص Order Block حسب الـ Red Flags بالقسم 21.4.
        يرجع قائمة أعلام حمراء + توصية بتخفيض الدرجة (downgrade) أو لا.
        """
        o = np.array(data["opens"], dtype=float)
        h = np.array(data["highs"], dtype=float)
        l = np.array(data["lows"], dtype=float)
        c = np.array(data["closes"], dtype=float)
        v = np.array(data["volumes"], dtype=float)
        n = len(c)

        if ob_index < 0 or ob_index >= n:
            return {"valid": False, "reason": "INVALID_INDEX"}

        red_flags = []

        # RED FLAG 5 أولاً: هل انكسر فعلياً؟ (الأخطر - يلغي الـ OB كلياً)
        if already_closed_through:
            return {
                "valid": False,
                "invalidated": True,
                "reason": "OB closed through - fully invalidated per Rule 21.4 Red Flag 5",
                "red_flags": ["INVALIDATED_BY_CLOSE"],
            }

        # RED FLAG 2: Over-tested
        if tests_count >= 3:
            red_flags.append(f"OVER_TESTED ({tests_count} تستات - المخزون شبه منتهي)")

        # RED FLAG 3: بدون دعم HTF
        if not htf_supports:
            red_flags.append("NO_HTF_CONTEXT (لا يوجد دعم من فريم أعلى)")

        # RED FLAG 4: خصائص شمعة الـ OB غير طبيعية
        body = abs(c[ob_index] - o[ob_index])
        upper_wick = h[ob_index] - max(o[ob_index], c[ob_index])
        lower_wick = min(o[ob_index], c[ob_index]) - l[ob_index]
        wick_body_ratio = max(upper_wick, lower_wick) / body if body > 0 else 99

        if wick_body_ratio > 3:
            red_flags.append(f"ABNORMAL_WICK (نسبة الفتيل/الجسم {wick_body_ratio:.1f}x)")

        vol_avg20 = v[max(0, ob_index - 20):ob_index].mean() if ob_index >= 20 else v[:ob_index].mean() if ob_index > 0 else v[ob_index]
        vol_ratio_ob = v[ob_index] / vol_avg20 if vol_avg20 > 0 else 1.0
        if vol_ratio_ob < 0.5:
            red_flags.append(f"LOW_VOLUME_OB (vol_ratio={vol_ratio_ob:.2f} - مشاركة ضعيفة)")

        # حساب عدد التخفيضات المطلوبة (كل علم أحمر = تخفيض درجة واحدة)
        downgrade_tiers = len(red_flags)

        return {
            "valid": True,
            "invalidated": False,
            "red_flags": red_flags,
            "red_flags_count": downgrade_tiers,
            "downgrade_tiers": downgrade_tiers,
            "wick_body_ratio": round(float(wick_body_ratio), 2),
            "vol_ratio_on_ob_candle": round(float(vol_ratio_ob), 2),
            "recommendation": (
                "TRUST_AS_IS" if downgrade_tiers == 0
                else f"DOWNGRADE_{downgrade_tiers}_TIER(S)"
            ),
        }

    # ══════════════════════════════════════════════════════════
    #  21.1 - TRAPPED TRADER TEST (هل يوجد وقود حقيقي للحركة؟)
    # ══════════════════════════════════════════════════════════

    def trapped_trader_evidence(self, data, swing_index, direction, swing_price=None):
        """
        يفحص هل فعلاً في "متداولين محاصرين" يغذّون الحركة المتوقعة،
        حسب القسم 21.1 (المبدأ الأهم بكل قسم الـ Authenticity).

        ⚠️ إصلاح بگ حقيقي وخطير (يوليو 2026، اكتُشف بباك تيست حقيقي على
        Nemotron 3 Ultra عبر 10 صفقات مولّدة بـKnownSetupsFinder):
        النسخة القديمة كانت تفترض أن `swing_index` نفسه هو موقع القمة/
        القاع الفعلي، فتحسب `level = h[swing_index]` أو `l[swing_index]`
        مباشرة. هذا كان صحيحاً *قبل* إصلاح `_find_swings()` (الذي كان
        يُرجع نقطة القمة/القاع الحقيقية نفسها). لكن بعد إصلاح lookahead
        bias بذلك الملف (تعديل سابق موثّق)، `_find_swings()` صار يُرجع
        النقطة "بعد" اكتمال نافذة التأكيد (`i + confirm_after`) - أي
        نقطة *لاحقة* للقمة/القاع الحقيقي، وليست القمة نفسها. النتيجة:
        هذه الدالة كانت تفحص "sweep" لمستوى عشوائي (سعر شمعة التأكيد)
        بدل القمة/القاع الحقيقي الذي كان من المفترض فحصه.

        تحقق فعلي رياضي مباشر (10 صفقات، بيانات BTC/ETH حقيقية): الفارق
        بين "المستوى المستخدم خطأً" و"القمة/القاع الحقيقي" تراوح بين
        0.6% و5.8% بكل الحالات العشر - خطأ منهجي متكرر وليس حالة نادرة.
        الأثر العملي: `entry_price` المسجّل لكل "صفقة مكتشفة" لم يكن
        بالضرورة اللحظة التي تلت الـsweep الحقيقي فعلياً، وربما شوّه
        نتائج باك تيست لاحقة اعتمدت على هذه النقطة كأساس للمقارنة.

        الإصلاح: نقبل الآن `swing_price` كبارامتر اختياري صريح (نفس مبدأ
        `classify_sweep()` الذي كان يفعل هذا بشكل صحيح من الأساس - القيمة
        الحقيقية تُمرَّر من الخارج بدل افتراضها من الإندكس). إذا لم يُمرَّر
        (توافق خلفي مع أي كود قديم لا يزال يستدعيها بالطريقة السابقة)،
        نعود للسلوك القديم مع تحذير صريح بالنتيجة يوضح أن القيمة قد تكون
        غير دقيقة - بدل فشل صامت.
        """
        h = np.array(data["highs"], dtype=float)
        l = np.array(data["lows"], dtype=float)
        c = np.array(data["closes"], dtype=float)
        o = np.array(data["opens"], dtype=float)
        n = len(c)
        # ملاحظة: الحجم (volumes) غير مستخدم حالياً بهذا الفحص - فقط
        # range/body_pct يحددان "displacement". فحص حجم إضافي (مثلاً
        # vol_ratio > 1.5 كشرط رابع) قد يقوّي الفحص مستقبلاً، لكن هذا
        # تغيير سلوك يحتاج اختباراً منفصلاً قبل تفعيله - لم يُغيَّر هنا.

        if swing_index < 0 or swing_index >= n:
            return {"has_fuel": False, "reason": "INVALID_INDEX"}

        atr = self._atr(h, l, c)
        atr_val = atr[swing_index] if swing_index < len(atr) and atr[swing_index] > 0 else 1.0

        level_is_estimated = swing_price is None
        if direction == "BULLISH":
            # نحتاج إثبات إنه شورت تريدرز انحاصروا (سحب سيولة تحت + displacement صاعد)
            level = float(swing_price) if swing_price is not None else l[swing_index]
            swept = bool(np.any(l[max(0, swing_index - 5):swing_index] > level)) if swing_index >= 1 else False
        else:
            level = float(swing_price) if swing_price is not None else h[swing_index]
            swept = bool(np.any(h[max(0, swing_index - 5):swing_index] < level)) if swing_index >= 1 else False

        # فحص الـ displacement خلال 1-3 شموع بعد النقطة
        fuel_confirmed = False
        for j in range(swing_index, min(swing_index + 4, n)):
            rng = h[j] - l[j]
            body = abs(c[j] - o[j])
            body_pct = body / rng if rng > 0 else 0
            is_bullish = c[j] > o[j]
            direction_matches = (direction == "BULLISH" and is_bullish) or (direction == "BEARISH" and not is_bullish)
            if direction_matches and rng > 1.5 * atr_val and body_pct > 0.6:
                fuel_confirmed = True
                break

        result = {
            "has_fuel": bool(swept and fuel_confirmed),
            "liquidity_swept": bool(swept),
            "displacement_confirmed": fuel_confirmed,
            "level_used": round(level, 6),
            "verdict": (
                "TRAPPED_TRADERS_CONFIRMED_FUEL_EXISTS" if (swept and fuel_confirmed)
                else "NO_CLEAR_FUEL_SOURCE_TREAT_AS_ORGANIC_DRIFT"
            ),
        }
        if level_is_estimated:
            result["warning"] = (
                "NO_EXPLICIT_SWING_PRICE_PASSED - level estimated from "
                "swing_index candle itself, which may NOT be the true "
                "swing high/low if swing_index came from a lookahead-safe "
                "detector (confirmation point, not the peak/trough itself). "
                "Pass swing_price explicitly to avoid this ambiguity."
            )
        return result


    # ══════════════════════════════════════════════════════════
    #  21.6 - WASH TRADING / DATA MANIPULATION AWARENESS
    # ══════════════════════════════════════════════════════════

    def check_volume_authenticity(self, data, index=-1):
        """
        يقارن volume مقابل num_trades لكشف احتمال Wash Trading
        (حجم منتفخ صناعياً بدون عدد صفقات حقيقي يدعمه).
        """
        v = np.array(data.get("volumes", []), dtype=float)
        trades = data.get("num_trades")
        n = len(v)
        if n == 0:
            return {"checked": False, "reason": "NO_VOLUME_DATA"}

        idx = index if index >= 0 else n - 1
        vol_avg20 = v[max(0, idx - 20):idx].mean() if idx >= 20 else v[:idx].mean() if idx > 0 else v[idx]
        vol_ratio = v[idx] / vol_avg20 if vol_avg20 > 0 else 1.0

        if not trades or all(t == 0 for t in trades):
            return {
                "checked": False,
                "reason": "NO_NUM_TRADES_DATA",
                "vol_ratio": round(float(vol_ratio), 2),
            }

        trades_arr = np.array(trades, dtype=float)
        trades_avg20 = trades_arr[max(0, idx - 20):idx].mean() if idx >= 20 else trades_arr[:idx].mean() if idx > 0 else trades_arr[idx]
        trades_ratio = trades_arr[idx] / trades_avg20 if trades_avg20 > 0 else 1.0

        # علم أحمر: حجم مرتفع جداً لكن عدد صفقات طبيعي/منخفض
        suspicious = bool(vol_ratio > 2.0 and trades_ratio < 1.3)

        return {
            "checked": True,
            "vol_ratio": round(float(vol_ratio), 2),
            "trades_ratio": round(float(trades_ratio), 2),
            "suspicious_wash_trading": suspicious,
            "verdict": (
                "TRUST_VOLUME_SPIKE" if not suspicious
                else "SUSPECT_WASH_TRADING_TRUST_NUM_TRADES_INSTEAD"
            ),
        }

    # ══════════════════════════════════════════════════════════
    #  22.7 - VERIFIABILITY / SELF-AUDIT HELPER
    # ══════════════════════════════════════════════════════════

    def audit_signal_prices(self, signal, data):
        """
        فحص أخير: هل الأسعار (entry/sl/tp) يلي رجعها الـ AI موجودة فعلاً
        بمدى بيانات الشموع المرسلة؟ (يكشف الأسعار المختلقة/الهلوسة)
        """
        if not isinstance(signal, dict):
            return {"valid": False, "reason": "SIGNAL_NOT_DICT"}

        h = data.get("highs", [])
        l = data.get("lows", [])
        if not h or not l:
            return {"valid": False, "reason": "NO_RANGE_DATA"}

        # نطاق معقول مع هامش (البيانات التاريخية + امتداد منطقي للمستقبل القريب)
        range_high = max(h) * 1.05
        range_low = min(l) * 0.95

        issues = []
        for field in ("entry", "stop_loss", "tp1", "tp2", "take_profit"):
            val = signal.get(field)
            if val is None:
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if not (range_low <= val <= range_high):
                issues.append(
                    f"{field}={val} خارج النطاق المعقول "
                    f"({range_low:.2f} - {range_high:.2f}) - احتمال هلوسة سعر"
                )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "checked_range": {"low": round(range_low, 2), "high": round(range_high, 2)},
        }

    # ══════════════════════════════════════════════════════════
    #  24.x - MECHANICAL BOS CROSS-CHECK (يترجم قسم
    #  [BOS_OB_DIRECTIONAL_INTEGRITY] إلى حساب رقمي فعلي، لأن
    #  الاختبار الفعلي أثبت أن وصف القاعدة بالدستور نصياً وحده لا
    #  يكفي - نموذج قادر "يذكر" فحص Section 21.2 (follow-through)
    #  بينما يقرأ الأرقام بشكل غير أمين ليبرر قراراً اتخذه مسبقاً
    #  (مثال حقيقي مُوثّق: ادّعى "فشل الإغلاق فوق المستوى المكسور"
    #  بينما 3 شموع متتالية أغلقت فعلياً فوقه). هذه الدالة تحسب
    #  الحقيقة الرقمية بشكل مستقل تماماً عن أي نص يولّده الـ AI،
    #  ثم brain_core.py يقارن ادعاء الـ AI بهذا الحساب المستقل.
    # ══════════════════════════════════════════════════════════

    def detect_most_recent_bos(self, data, lookback_candles=15, swing_window=2):
        """
        يفحص آخر lookback_candles شمعة بحثاً عن أحدث displacement
        حقيقي (بنفس معايير قسم 5.2/5.3 بالدستور: range>=2xATR أو
        تراكمي، body_pct>60%) كسر فعلياً آخر swing high/low قبله،
        ويتحقق رياضياً (لا نصياً) هل حافظ على نفسه (Section 21.2
        Check 1+3: إغلاق فوق/تحت المستوى + متابعة الاتجاه بعده).

        Returns dict بحقائق موضوعية 100% مستقلة عن أي رد AI:
            {
                "bos_found": bool,
                "direction": "UP" / "DOWN" / None,
                "broken_level": float,
                "displacement_index": int (نسبي لنهاية المصفوفة),
                "displacement_body_pct": float,
                "displacement_range_atr_ratio": float,
                "displacement_vol_ratio": float,
                "closes_beyond_level_count": int (كم شمعة بعد الاختراق
                    أغلقت فعلاً متجاوزة المستوى - الدليل الحاسم),
                "held": bool (فعلياً حافظ على الاختراق ولا انعكس),
            }
        """
        h = np.array(data.get("highs", []), dtype=float)
        l = np.array(data.get("lows", []), dtype=float)
        c = np.array(data.get("closes", []), dtype=float)
        o = np.array(data.get("opens", []), dtype=float)
        v = np.array(data.get("volumes", []), dtype=float)
        n = len(c)
        if n < lookback_candles + swing_window * 2 + 5:
            return {"bos_found": False, "direction": None, "reason": "INSUFFICIENT_DATA"}

        atr = self._atr(h, l, c)

        # ⚠️ ملاحظة تقنية مهمة (اكتُشفت وأُصلحت أثناء بناء هذا الفحص):
        # لا يجوز حساب "القمة/القاع السابق" باستخدام نافذة تأكيد
        # (swing_window) تمتد جهة المستقبل بشكل يشمل شمعة الاندفاع
        # نفسها أو ما بعدها - لأن الاندفاع نفسه غالباً يصنع قمة/قاع
        # أعلى/أدنى، فيُخفي (يُبطل) القمة الحقيقية التي كانت موجودة
        # فعلاً *قبله* بفترة قصيرة. الحل: لكل شمعة اندفاع مرشحة i،
        # نحسب السوينغز باستخدام فقط البيانات المنتهية عند i (حصرياً)
        # - أي "ما كان معروفاً كسوينغ مؤكد لحظة i، بلا أي تلوث من i
        # نفسها أو بعدها".
        def _last_swing_high_before(idx_limit):
            best = None
            for j in range(swing_window, idx_limit - swing_window):
                if h[j] == max(h[j - swing_window:j + swing_window + 1]):
                    best = (j, h[j])
            return best

        def _last_swing_low_before(idx_limit):
            best = None
            for j in range(swing_window, idx_limit - swing_window):
                if l[j] == min(l[j - swing_window:j + swing_window + 1]):
                    best = (j, l[j])
            return best


        start = n - lookback_candles
        best = None  # أحدث displacement صالح (نأخذ الأحدث دائماً، ليس الأقوى)

        for i in range(start, n):
            if i < 1 or atr[i] <= 0:
                continue
            rng = h[i] - l[i]
            body = abs(c[i] - o[i])
            body_pct = body / rng if rng > 0 else 0
            vol_avg20 = v[max(0, i - 20):i].mean() if i >= 20 else (v[:i].mean() if i > 0 else v[i])
            vol_ratio = v[i] / vol_avg20 if vol_avg20 > 0 else 1.0
            is_bullish = c[i] > o[i]
            range_atr_ratio = rng / atr[i]

            # معيار displacement (قسم 5.2/5.3): range>=2xATR أو body_pct>70%
            is_displacement = (range_atr_ratio >= 1.5 and body_pct > 0.6)
            if not is_displacement:
                continue

            sh_match = _last_swing_high_before(i)
            sl_match = _last_swing_low_before(i)
            if is_bullish and sh_match:
                prior_high = sh_match[1]
                if h[i] > prior_high:
                    best = {
                        "direction": "UP", "index": i, "broken_level": float(prior_high),
                        "body_pct": round(body_pct * 100, 1),
                        "range_atr_ratio": round(range_atr_ratio, 2),
                        "vol_ratio": round(vol_ratio, 2),
                    }
            elif (not is_bullish) and sl_match:
                prior_low = sl_match[1]
                if l[i] < prior_low:
                    best = {
                        "direction": "DOWN", "index": i, "broken_level": float(prior_low),
                        "body_pct": round(body_pct * 100, 1),
                        "range_atr_ratio": round(range_atr_ratio, 2),
                        "vol_ratio": round(vol_ratio, 2),
                    }

        if best is None:
            return {"bos_found": False, "direction": None}

        # ── التحقق الحاسم: كم شمعة بعد الاختراق أغلقت فعلاً متجاوزة المستوى؟ ──
        idx = best["index"]
        level = best["broken_level"]
        direction = best["direction"]
        closes_beyond = 0
        for j in range(idx, n):
            if direction == "UP" and c[j] > level:
                closes_beyond += 1
            elif direction == "DOWN" and c[j] < level:
                closes_beyond += 1

        candles_after = n - idx
        # "held" = أغلبية الشموع بعد الاختراق (بما فيها شمعة الاختراق
        # نفسها) بقيت متجاوزة المستوى - دليل موضوعي على استمرار الكسر
        held = candles_after > 0 and (closes_beyond / candles_after) >= 0.6

        return {
            "bos_found": True,
            "direction": direction,
            "broken_level": round(level, 2),
            "displacement_index_from_end": idx - n,  # سالب = كم شمعة قبل النهاية
            "displacement_body_pct": best["body_pct"],
            "displacement_range_atr_ratio": best["range_atr_ratio"],
            "displacement_vol_ratio": best["vol_ratio"],
            "candles_since_displacement": candles_after,
            "closes_beyond_level_count": closes_beyond,
            "held": bool(held),
        }

    # ══════════════════════════════════════════════════════════
    #  CAUSAL DERIVATION CHAIN (الاستنباط والترابط الحقيقي)
    # ══════════════════════════════════════════════════════════
    # ⚠️ لماذا هذه الدالة ضرورية ومختلفة عن كل ما سبق: كل الدوال أعلاه
    # (detect_most_recent_bos, detect_significant_swings,
    # detect_most_recent_sweep) تكتشف **حقائق منفصلة** كل واحدة بمعزل
    # عن الأخرى - BOS لحاله، سوينغ لحاله، سويب لحاله. لكن طلب المستخدم
    # الصريح هو "استنباطها وترابطها وتقاطعها" - يعني: مش كافي إنه
    # البوت يعرف "صار BOS صاعد هون" و"صار سحب سيولة هونيك" كخبرين
    # منفصلين، لازم يعرف **العلاقة السببية بينهم**:
    #   - أي شمعة بالضبط هي "الأصل" (Order Block) اللي منها انطلق
    #     اندفاع الـ BOS؟ (تعريف ICT الدقيق: آخر شمعة معاكسة اللون
    #     قبل شمعة الاندفاع مباشرة - هذه هي "بصمة" المؤسسات، ليست أي
    #     شمعة عشوائية)
    #   - هل هذا الاندفاع نفسه خلق فجوة سعرية (FVG) - فراغ حقيقي بين
    #     3 شموع متتالية لم يتداول فيه أحد؟ (دليل عدم كفاءة إضافي على
    #     نفس الاندفاع، لا حدث منفصل)
    #   - هل نقطة انطلاق الاندفاع (الـ OB) نفسها قريبة من/ناتجة عن
    #     آخر سحب سيولة مكتشف (Sweep)؟ (هذا بالضبط نمط "Sweep → OB
    #     → Displacement → BOS" الذي يُبنى عليه معظم صفقات ICT
    #     الحقيقية - سلسلة سببية واحدة، وليس 4 ملاحظات متفرقة)
    #
    # هذه الدالة لا "تخترع" شيئاً - هي فقط تربط رياضياً حقائق محسوبة
    # فعلاً من الدوال أعلاه ببعضها البعض، وتبني نص سردي صريح يوضح
    # هذا الترابط، بحيث يصل للـ AI جاهزاً كـ"سلسلة استنباط" بدل حقائق
    # مبعثرة يُترك هو ليربطها بنفسه من الصفر (وهذا بالضبط ما فشل به
    # سابقاً - قراءة كل حقيقة صح بمعزل، لكن بلا فهم كيف ترتبط ببعضها).

    def _find_order_block_for_displacement(self, data, displacement_index, direction):
        """
        يجد شمعة الـ Order Block الحقيقية المسؤولة عن اندفاع معين،
        حسب التعريف الدقيق لـICT: آخر شمعة *معاكسة اللون* لاتجاه
        الاندفاع، مباشرة قبل شمعة الاندفاع (أو ضمن آخر 3 شموع قبلها
        إذا لم تكن الشمعة السابقة مباشرة معاكسة - يحصل أحياناً بوجود
        شمعة دوجي محايدة بينهما).
        """
        o = np.array(data.get("opens", []), dtype=float)
        c = np.array(data.get("closes", []), dtype=float)
        n = len(c)

        if displacement_index <= 0 or displacement_index >= n:
            return None

        want_bearish_ob = (direction == "UP")  # OB صاعد أصله آخر شمعة هابطة قبله
        search_start = max(0, displacement_index - 3)
        ob_idx = None
        for j in range(displacement_index - 1, search_start - 1, -1):
            is_bearish_candle = c[j] < o[j]
            is_bullish_candle = c[j] > o[j]
            if want_bearish_ob and is_bearish_candle:
                ob_idx = j
                break
            if (not want_bearish_ob) and is_bullish_candle:
                ob_idx = j
                break

        if ob_idx is None:
            return None

        return {
            "ob_index_from_end": ob_idx - n,
            "ob_top": round(float(max(o[ob_idx], c[ob_idx])), 4),
            "ob_bottom": round(float(min(o[ob_idx], c[ob_idx])), 4),
            "ob_type": "BEARISH_OB (bullish displacement origin)" if want_bearish_ob else "BULLISH_OB (bearish displacement origin)",
            "candles_between_ob_and_displacement": displacement_index - ob_idx - 1,
        }

    def _find_fvg_near_displacement(self, data, displacement_index, direction):
        """
        يبحث عن Fair Value Gap (فجوة سعرية حقيقية - لا تداول حصل
        بمنطقتها) ناتجة عن نفس شمعة الاندفاع، حسب التعريف القياسي
        (3 شموع متتالية: هابط[i-1].low > صاعد[i+1].high = FVG هابط،
        أو صاعد[i-1].high < هابط[i+1].low = FVG صاعد) حيث الشمعة
        الوسطى (i) هي شمعة الاندفاع نفسها أو قريبة منها (±1).
        """
        h = np.array(data.get("highs", []), dtype=float)
        l = np.array(data.get("lows", []), dtype=float)
        n = len(h)

        candidates = [displacement_index - 1, displacement_index, displacement_index + 1]
        for i in candidates:
            if i < 1 or i >= n - 1:
                continue
            if direction == "UP" and l[i + 1] > h[i - 1]:
                return {
                    "fvg_found": True,
                    "fvg_top": round(float(l[i + 1]), 4),
                    "fvg_bottom": round(float(h[i - 1]), 4),
                    "fvg_middle_candle_index_from_end": i - n,
                    "fvg_type": "BULLISH_FVG",
                }
            if direction == "DOWN" and h[i + 1] < l[i - 1]:
                return {
                    "fvg_found": True,
                    "fvg_top": round(float(l[i - 1]), 4),
                    "fvg_bottom": round(float(h[i + 1]), 4),
                    "fvg_middle_candle_index_from_end": i - n,
                    "fvg_type": "BEARISH_FVG",
                }
        return {"fvg_found": False}

    def build_causal_derivation_chain(self, data, lookback_candles=15, swing_window=2):
        """
        يبني "سلسلة الاستنباط السببية" الكاملة: يأخذ آخر BOS المكتشف
        رياضياً (detect_most_recent_bos)، يشتق منه Order Block الحقيقي
        المسؤول عنه، يفحص هل نفس الاندفاع خلق FVG، ثم يتحقق هل نقطة
        انطلاق كل هذا (الـOB) قريبة من آخر سحب سيولة مكتشف
        (detect_most_recent_sweep) - أي هل السلسلة الكاملة "منطقية
        ومترابطة": Sweep (فخ) → OB (بصمة المؤسسات) → Displacement
        (اندفاع حقيقي) → FVG (فراغ سعري) → BOS (كسر هيكل مؤكد)، أو
        هل هي حلقات مفككة بلا رابط سببي حقيقي بينها.

        Returns dict بسرد صريح لكل حلقة + تقييم "تماسك السلسلة".
        """
        bos = self.detect_most_recent_bos(data, lookback_candles, swing_window)
        chain = {"bos": bos, "chain_coherent": False, "narrative": ""}

        if not bos.get("bos_found"):
            chain["narrative"] = "لا يوجد BOS حقيقي مكتشف رياضياً - لا سلسلة استنباط لبنائها."
            return chain

        n = len(data.get("closes", []))
        displacement_idx = bos["displacement_index_from_end"] + n
        direction = bos["direction"]

        ob = self._find_order_block_for_displacement(data, displacement_idx, direction)
        chain["order_block"] = ob

        fvg = self._find_fvg_near_displacement(data, displacement_idx, direction)
        chain["fvg"] = fvg

        sweep = self.detect_most_recent_sweep(data, lookback_candles, swing_window)
        chain["preceding_sweep"] = sweep

        # ── تقييم الترابط: هل الـsweep يسبق أو يتزامن تقريباً مع الـOB؟ ──
        sweep_linked = False
        if sweep.get("found") and ob:
            sweep_idx = sweep.get("sweep_candle_index_from_end", -9999)
            ob_idx = ob.get("ob_index_from_end", -9999)
            # الـsweep يجب أن يسبق أو يتزامن تقريباً مع الـOB (خلال 5 شموع)
            sweep_linked = -5 <= (ob_idx - sweep_idx) <= 2

        narrative_parts = [
            f"آخر BOS حقيقي (اتجاه {direction}) صار بالشمعة "
            f"{bos['displacement_index_from_end']} (كسر مستوى {bos['broken_level']})."
        ]
        if ob:
            narrative_parts.append(
                f"شمعة الـOrder Block المسؤولة عنه: الشمعة "
                f"{ob['ob_index_from_end']} ({ob['ob_type']}, نطاق "
                f"{ob['ob_bottom']}-{ob['ob_top']})."
            )
        else:
            narrative_parts.append("لم يُعثر على Order Block واضح (شمعة معاكسة اللون) قبل شمعة الاندفاع مباشرة.")

        if fvg.get("fvg_found"):
            narrative_parts.append(
                f"نفس الاندفاع خلق {fvg['fvg_type']} بنطاق "
                f"{fvg['fvg_bottom']}-{fvg['fvg_top']} - دليل عدم كفاءة إضافي يدعم نفس الحركة."
            )
        else:
            narrative_parts.append("لم تُخلق فجوة سعرية (FVG) واضحة بهذا الاندفاع.")

        if sweep_linked:
            narrative_parts.append(
                f"هذا الـOB مرتبط سببياً بآخر سحب سيولة مكتشف "
                f"(مستوى {sweep.get('swept_level_price')}, تصنيف "
                f"{sweep.get('classification')}) - السلسلة الكاملة متماسكة: "
                f"Sweep → OB → Displacement → BOS."
            )
        elif sweep.get("found"):
            narrative_parts.append(
                "يوجد سحب سيولة مكتشف لكنه غير مرتبط زمنياً بهذا الـOB تحديداً - "
                "قد يكون BOS هذا حركة منفصلة عن آخر سحب سيولة، ليس نفس القصة."
            )

        chain["chain_coherent"] = bool(ob and sweep_linked)
        chain["narrative"] = " ".join(narrative_parts)
        return chain

    def cross_check_bos_reconciliation(self, ai_result, data):
        """
        يقارن ادعاء الـ AI بحقل bos_reconciliation مع الحقيقة الرقمية
        المستقلة من detect_most_recent_bos(). لا يفهم النص لغوياً (هذا
        غير موثوق كما أثبت الاختبار الفعلي) - فقط يتحقق من التناقض
        الأخطر والأوضح رقمياً: الـ AI أصدر إشارة بعكس اتجاه BOS
        "held=True" (كسر حقيقي حافظ على نفسه) بدون أن يقدّم دليل
        digits مطابق فعلياً للواقع.

        Returns dict: {"flagged": bool, "reason": str or None, "mechanical_bos": {...}}
        """
        mechanical = self.detect_most_recent_bos(data)
        result = {"mechanical_bos": mechanical, "flagged": False, "reason": None}

        if not mechanical.get("bos_found"):
            return result

        signal = ai_result.get("signal") if isinstance(ai_result, dict) else None
        if signal not in ("BUY", "SELL"):
            return result

        signal_direction = "UP" if signal == "BUY" else "DOWN"
        bos_direction = mechanical["direction"]
        bos_held = mechanical["held"]

        # الحالة الخطرة: BOS حقيقي (held=True, معايير displacement قوية)
        # بعكس اتجاه الإشارة - هذا بالضبط الفشل الموثّق (شمعة اندفاع
        # صاعدة صنّفها الـ AI Bearish OB وأصدر SELL رغم أن 3 إغلاقات
        # متتالية تجاوزت المستوى المكسور فعلياً).
        if bos_direction != signal_direction and bos_held:
            result["flagged"] = True
            result["reason"] = (
                f"تناقض رقمي مباشر: آخر BOS مؤكد رياضياً كان اتجاهه "
                f"{bos_direction} (كسر مستوى {mechanical['broken_level']}, "
                f"body={mechanical['displacement_body_pct']}%, "
                f"{mechanical['closes_beyond_level_count']}/"
                f"{mechanical['candles_since_displacement']} شمعة بعده "
                f"أغلقت فعلاً متجاوزة المستوى - أي الكسر لا يزال قائماً "
                f"موضوعياً)، لكن الإشارة الصادرة {signal} تفترض اتجاه "
                f"{signal_direction} - عكس الدليل الرقمي المباشر تماماً."
            )

        # ⚠️ فحص إضافي مستقل: هل ادّعى الـAI أن BOS "الأحدث" هو شمعة
        # أقدم بكثير من الكسر الحقيقي الأحدث المكتشف رياضياً؟ خطأ حقيقي
        # مُوثّق: النموذج ادّعى "BOS UP بشمعة #42 من أصل 50" كـ"آخر BOS"
        # بينما كان هناك كسر هابط حقيقي بشمعة #49 (أحدث بـ7 شموع) أهمله
        # تماماً - فشل بتحديد "الأحدث" حرفياً، لا مجرد تفسير مختلف.
        claimed_idx = ai_result.get("bos_candle_index_from_end") if isinstance(ai_result, dict) else None
        if isinstance(claimed_idx, (int, float)):
            actual_idx = mechanical.get("displacement_index_from_end")
            if isinstance(actual_idx, (int, float)) and claimed_idx < actual_idx - 1:
                # claimed_idx أكثر سلبية بشكل ملحوظ = يشير لشمعة أقدم
                # بكثير من الكسر الحقيقي الأحدث المكتشف رياضياً
                if not result["flagged"]:
                    result["flagged"] = True
                result["reason"] = (
                    (result["reason"] + " | " if result["reason"] else "") +
                    f"تناقض بتحديد 'الأحدث': الـAI ادّعى أن آخر BOS هو "
                    f"الشمعة {claimed_idx} (من النهاية)، لكن يوجد كسر "
                    f"هيكلي حقيقي أحدث رياضياً بالشمعة {actual_idx} "
                    f"(اتجاهه {bos_direction}) لم يُفحص أو يُذكر إطلاقاً."
                )

        return result

    # ══════════════════════════════════════════════════════════
    #  24.x - AUDIT LAST CANDLE REPORT (كشف "هلوسة لون الشمعة")
    # ══════════════════════════════════════════════════════════
    # ⚠️ إصلاح خطأ حقيقي مُكتشف بالباك تيست الفعلي (يوليو 2026):
    # النموذج وصف الشمعة الأخيرة نصياً بعكس حقيقتها تماماً مرتين على
    # صفقتين منفصلتين - مثال موثّق: شمعة حقيقية O=2929.0 H=3031.0
    # L=2886.7 C=2904.9 (هابطة، body_pct=16.7%) وُصفت بالنص كـ"صاعدة
    # قوية body_pct~80%"، وبُني عليها bias/signal بالكامل. هذا ليس
    # خطأ استراتيجي (تفسير غلط لبيانات صحيحة) بل هلوسة بالحقيقة
    # الأساسية نفسها (لون/حجم الشمعة) قبل أي تحليل. الحل: نجبر
    # النموذج (schema صارم، حقل last_candle_report) يذكر أرقام آخر
    # شمعة صراحة، ثم نتحقق آلياً 100% بلا أي اعتماد على فهم نص حر.

    def audit_last_candle_report(self, ai_result, data, tolerance_pct=0.15):
        """
        يقارن حقل ai_result['last_candle_report'] (يُفرض عبر
        signal_schema.py) مع آخر شمعة فعلية بالبيانات المُرسلة.

        Returns dict: {
            "checked": bool,
            "valid": bool,
            "issues": [str, ...],
        }
        """
        report = ai_result.get("last_candle_report") if isinstance(ai_result, dict) else None
        if not isinstance(report, dict):
            return {"checked": False, "valid": True, "issues": []}

        closes = data.get("closes", [])
        opens = data.get("opens", [])
        highs = data.get("highs", [])
        lows = data.get("lows", [])
        if not closes or not opens:
            return {"checked": False, "valid": True, "issues": []}

        actual_o, actual_h, actual_l, actual_c = opens[-1], highs[-1], lows[-1], closes[-1]
        actual_color = "BULLISH" if actual_c > actual_o else "BEARISH"

        issues = []

        # ── فحص اللون (الأهم - هذا كان الخطأ الفعلي المُكتشف) ──
        reported_color = str(report.get("color", "")).upper()
        if reported_color and reported_color != actual_color:
            issues.append(
                f"لون الشمعة الأخيرة المُبلَّغ ({reported_color}) يعاكس "
                f"الحقيقة الفعلية ({actual_color}: O={actual_o}, C={actual_c}) "
                "- هلوسة مباشرة بأساسيات البيانات"
            )

        # ── فحص القيم الرقمية (هامش تسامح صغير لأخطاء تقريب) ──
        def _mismatch(field_name, reported_val, actual_val):
            if reported_val is None or actual_val in (None, 0):
                return None
            diff_pct = abs(reported_val - actual_val) / abs(actual_val) * 100
            if diff_pct > tolerance_pct:
                return (
                    f"{field_name} المُبلَّغ ({reported_val}) يختلف عن الفعلي "
                    f"({actual_val}) بنسبة {diff_pct:.2f}% - أعلى من الهامش "
                    f"المسموح ({tolerance_pct}%)"
                )
            return None

        for field_name, actual_val in (
            ("open", actual_o), ("high", actual_h),
            ("low", actual_l), ("close", actual_c),
        ):
            reported_val = report.get(field_name)
            try:
                reported_val = float(reported_val) if reported_val is not None else None
            except (TypeError, ValueError):
                reported_val = None
            msg = _mismatch(field_name, reported_val, actual_val)
            if msg:
                issues.append(msg)

        return {
            "checked": True,
            "valid": len(issues) == 0,
            "issues": issues,
            "actual": {"open": actual_o, "high": actual_h, "low": actual_l, "close": actual_c, "color": actual_color},
            "reported": report,
        }

    # ══════════════════════════════════════════════════════════
    #  26.x - DETECT SELECTIVE WICK CITATION (هلوسة انتقائية)
    # ══════════════════════════════════════════════════════════
    # ⚠️ إصلاح خطأ حقيقي مُكتشف بالباك تيست الفعلي (يوليو 2026): النموذج
    # بنى قرار BUY على أساس "فتيل رفض سفلي طويل" (24.1 نقطة) بينما
    # تجاهل تماماً أن الفتيل العلوي كان بنفس الحجم تقريباً (18.41 نقطة)
    # وجسم الشمعة كان صغيراً جداً (0.6) - أي الشمعة كانت فعلياً دوجي
    # حقيقي (تردد تام بين البائعين والمشترين)، لا "hammer/spring" نظيف
    # بفتيل سفلي واضح ومهيمن. كل رقم ذكره النموذج كان صحيحاً - المشكلة
    # أنه ذكر نصف الحقيقة فقط (الفتيل الذي يخدم القصة) وتجاهل النصف
    # الآخر (الفتيل المعاكس بنفس الحجم تقريباً). هذا الفحص يكتشف هذا
    # النمط آلياً: أي وصف "رفض/hammer/pin bar/spring" على شمعة بفتيلين
    # متقاربين بالحجم (وليس فتيل واحد مهيمن بوضوح) يُعلَّم كمشبوه.

    def detect_selective_wick_citation(self, ai_result, data, dominance_ratio=1.8):
        """
        يفحص هل النموذج ادّعى نمط "رفض/hammer/spring/pin bar" بالنص
        الحر (narrative/reasoning) على الشمعة الأخيرة، بينما الشمعة
        فعلياً "دوجي" (فتيلين متقاربين، لا فتيل واحد مهيمن بوضوح).

        Args:
            dominance_ratio: الحد الأدنى لنسبة الفتيل المهيمن للفتيل
                الآخر حتى تُعتبر الشمعة "hammer/pin bar حقيقي" - أقل
                من هذا يُعتبر دوجي (تردد)، بغض النظر عن طول الفتيل
                المذكور بمفرده.

        Returns dict: {"checked": bool, "suspicious": bool, "details": str or None}
        """
        text = " ".join(str(ai_result.get(k, "")) for k in
                         ("narrative", "reasoning", "archetype")).lower()
        rejection_keywords = [
            "rejection", "hammer", "pin bar", "spring", "long lower wick",
            "long upper wick", "wick rejection", "selling climax",
            "buying climax", "absorption"
        ]
        if not any(kw in text for kw in rejection_keywords):
            return {"checked": False, "suspicious": False, "details": None}

        opens = data.get("opens", [])
        highs = data.get("highs", [])
        lows = data.get("lows", [])
        closes = data.get("closes", [])
        if not opens:
            return {"checked": False, "suspicious": False, "details": None}

        o, h, l, c = opens[-1], highs[-1], lows[-1], closes[-1]
        body = abs(c - o)
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)

        # لو أحد الفتيلين شبه معدوم، لا مشكلة (فتيل واحد واضح فعلاً)
        smaller_wick = min(lower_wick, upper_wick)
        larger_wick = max(lower_wick, upper_wick)

        if smaller_wick <= 0:
            return {"checked": True, "suspicious": False, "details": None}

        ratio = larger_wick / smaller_wick if smaller_wick > 0 else float("inf")

        if ratio < dominance_ratio:
            return {
                "checked": True,
                "suspicious": True,
                "details": (
                    f"النص يدّعي نمط رفض/hammer/spring، لكن الشمعة الأخيرة "
                    f"فعلياً لديها فتيلان متقاربان بالحجم (سفلي={lower_wick:.2f}, "
                    f"علوي={upper_wick:.2f}, نسبة={ratio:.2f}x - أقل من الحد "
                    f"{dominance_ratio}x المطلوب لاعتبارها hammer/pin bar حقيقي) "
                    f"وجسم صغير (body={body:.2f}) - هذا نمط دوجي (تردد تام)، "
                    "وليس رفضاً واضحاً باتجاه واحد. احتمال هلوسة انتقائية "
                    "(ذكر فتيل واحد فقط يخدم القصة، تجاهل الفتيل المعاكس)."
                ),
            }

        return {"checked": True, "suspicious": False, "details": None}

    # ══════════════════════════════════════════════════════════
    #  25.x - AUDIT NUMERIC COMPARISON CLAIMS (HH/HL/LH/LL)
    # ══════════════════════════════════════════════════════════
    # ⚠️ إصلاح خطأ حقيقي مُكتشف بالباك تيست الفعلي على Nemotron 3 Ultra
    # (يوليو 2026، صفقة BTC/USDT 4h موثّقة): النموذج ذكر أرقام صحيحة
    # فعلياً بحقل daily_bias_summary ("HH at idx -1 (95000) > HH at idx
    # -7 (95191)") لكن قارنها بشكل معكوس رياضياً - 95000 أصغر فعلياً من
    # 95191، وليس أكبر كما ادُّعي. هذا ليس هلوسة أسعار (كل رقم موجود
    # فعلاً بالبيانات الخام - تحقق مباشر أثبت ذلك) ولا نقص معرفة (قاعدة
    # "الحد الأدنى 2 HH متتاليين متصاعدين" موجودة أصلاً بقسم
    # [MARKET_STRUCTURE] المتاح لهذه المرحلة) - هو خطأ حسابي بحت
    # بالمقارنة نفسها (">" استُخدم حيث الحقيقة "<"). هذا النوع من
    # الأخطاء لا يُحل بتحسين البرومبت أو المعرفة (النموذج "يعرف" القاعدة
    # ويطبّقها لغوياً، لكن يُخطئ حسابياً) - الحل الوحيد الموثوق هو تحقق
    # برمجي مستقل يعيد نفس المقارنة الحسابية البسيطة رياضياً بلا أي
    # اعتماد على فهم النموذج للعلاقة بين الأرقام.
    #
    # هذه الدالة تستخرج جمل بصيغة "X at idx A (price1) > idx B (price2)"
    # (أو "<") من أي نص حر، وتُعيد نفس المقارنة رياضياً - بلا أي تفسير
    # لغوي، فقط: هل price1 [عامل_المقارنة] price2 صحيح فعلاً أم لا؟

    # نمط أ: القيمة داخل قوس مباشرة "(95191)" - يغطي صيغة "HH at idx -1
    # (95000) > HH at idx -7 (95191)" (المرجع الزمني -N خارج القوس)
    _PRICE_IN_PARENS = re.compile(r"\((\d+\.?\d*)\)")
    # نمط ب: القيمة نفسها ظاهرة، مع مرجع زمني اختياري بقوس بعدها - يغطي
    # صيغة "HH at 2387.23 (candle -17) > prior HH 2209.96 (candle -21)"
    _NUM_WITH_OPTIONAL_REF = re.compile(
        r"(\d+\.?\d*)\s*(?:\((?:candle|idx|index)\s*-?\d+\)\s*)?"
        r"(>=|<=|>|<)\s*(?:prior\s+)?(?:\w+\s+)*?"
        r"(\d+\.?\d*)\s*(?:\((?:candle|idx|index)\s*-?\d+\)\s*)?",
        re.IGNORECASE,
    )

    def audit_numeric_comparison_claims(self, text):
        """
        يفحص كل مقارنة رقمية صريحة (بصيغتين شائعتين مختلفتين يستخدمهما
        النموذج فعلياً - راجع التوثيق أعلاه) داخل نص حر، ويتحقق حسابياً
        (بلا أي AI، بلا فهم لغوي) هل المقارنة المذكورة صحيحة رياضياً.

        Returns dict:
            {
                "checked_count": int,
                "contradictions": [
                    {"claim": "...", "num1": float, "operator": str, "num2": float}
                ],
                "has_contradiction": bool,
            }
        """
        if not text:
            return {"checked_count": 0, "contradictions": [], "has_contradiction": False}

        def _is_true(num1, op, num2):
            if op == ">":
                return num1 > num2
            if op == "<":
                return num1 < num2
            if op == ">=":
                return num1 >= num2
            return num1 <= num2  # "<="

        contradictions = []
        checked = 0
        seen_spans = []

        def _overlaps(a, b):
            return not (a[1] <= b[0] or b[1] <= a[0])

        # نمط أ أولاً (أولوية - أكثر دقة لأنه يعتمد على القوسين مباشرة)
        parens_matches = list(self._PRICE_IN_PARENS.finditer(text))
        for i in range(len(parens_matches) - 1):
            m1, m2 = parens_matches[i], parens_matches[i + 1]
            between = text[m1.end():m2.start()]
            # لا نقارن عبر حدود جملة كاملة (نقطة+حرف كبير أو سطر جديد)
            if re.search(r"\.\s+[A-Z]|\n", between):
                continue
            op_match = re.search(r"(>=|<=|>|<)", between)
            if not op_match:
                continue
            span = (m1.start(), m2.end())
            num1, num2, op = float(m1.group(1)), float(m2.group(1)), op_match.group(1)
            checked += 1
            seen_spans.append(span)
            if not _is_true(num1, op, num2):
                contradictions.append({
                    "claim": text[span[0]:span[1]],
                    "num1": num1, "operator": op, "num2": num2,
                })

        # نمط ب لأي مطابقات لم يغطها نمط أ (بلا تداخل مواضع)
        for m in self._NUM_WITH_OPTIONAL_REF.finditer(text):
            span = (m.start(), m.end())
            if any(_overlaps(span, s) for s in seen_spans):
                continue
            num1, op, num2 = float(m.group(1)), m.group(2), float(m.group(3))
            checked += 1
            if not _is_true(num1, op, num2):
                contradictions.append({
                    "claim": m.group(0), "num1": num1, "operator": op, "num2": num2,
                })

        return {
            "checked_count": checked,
            "contradictions": contradictions,
            "has_contradiction": len(contradictions) > 0,
        }

    # ══════════════════════════════════════════════════════════
    #  MECHANICAL BIAS ANCHOR - تحقق برمجي (بلا AI) من التزام النموذج
    #  بالمرساة الحتمية (راجع ict_math_engine.compute_mechanical_bias_anchor
    #  للتفصيل الكامل لماذا هذا ضروري - اكتشاف تذبذب اتجاه حي حقيقي)
    # ══════════════════════════════════════════════════════════

    def audit_bias_anchor_consistency(self, direction_claimed, text, anchor,
                                       data, swing_window=2):
        """
        يفحص هل قرار الاتجاه المُخرَج (BULLISH/BEARISH) يخالف مرساة
        الانحياز الميكانيكية القوية (STRONG) بلا استشهاد حقيقي بحدث
        انعكاس هيكلي (CHoCH/MSS/BOS) أحدث زمنياً من نقطة المرساة نفسها.

        ⚠️ هذا **لا يمنع** النموذج من مخالفة المرساة إطلاقاً - انعكاسات
        هيكلية حقيقية تحدث فعلاً بالأسواق، ومنع أي مخالفة كان سيكون
        قيداً زائفاً يضرب مبدأ "الفهم والتفسير السياقي" الذي بُني عليه
        هذا المشروع بأكمله. الشرط الوحيد: **لو خالف، يجب أن يستشهد**
        برقم/مؤشر شمعة حقيقي لحدث انعكاسي (لا كلام عام) وهذا الحدث يجب
        أن يقع فعلياً (بالبيانات الخام، لا بحسب زعمه فقط) بعد نقطة
        المرساة زمنياً - وإلا فهذا نفس نمط "تذبذب بلا سبب رياضي حقيقي"
        الموثّق فعلياً بجلسة يوليو 2026 (BUY_LIMIT ثم SELL_LIMIT لنفس
        البيانات بالضبط، بلا أي تغيّر بالمعطيات).

        Returns dict:
            {"flagged": bool, "reason": str|None}
        """
        result = {"flagged": False, "reason": None}
        if not anchor or anchor.get("strength") != "STRONG":
            return result
        if not direction_claimed or direction_claimed not in ("BULLISH", "BEARISH"):
            return result
        anchor_dir = anchor.get("anchor_direction")
        if anchor_dir not in ("BULLISH", "BEARISH") or direction_claimed == anchor_dir:
            return result

        # ⚠️ القرار يخالف المرساة القوية - نفحص الآن هل استُشهد بحدث
        # انعكاس هيكلي حقيقي (idx مذكور صراحة بالنص) يقع فعلياً *بعد*
        # نقطة كسر المرساة زمنياً (index_from_end أكبر = أحدث، لأن كل
        # الأرقام سالبة والأقرب للصفر هو الأحدث).
        anchor_break_idx = anchor.get("last_confirmed_break_index_from_end")

        # نبحث عن أي ذكر صريح لـ CHoCH/MSS/BOS مرفق برقم idx بالنص -
        # هذا "استشهاد" مقبول، بغض النظر عن دقته الحسابية الكاملة (تلك
        # تُفحص بدوال أخرى مستقلة - audit_structure_labels/audit_numeric_
        # comparison_claims) - هنا فقط نتحقق: هل *حاول* الاستشهاد أصلاً؟
        reversal_mentions = list(re.finditer(
            r"\b(CHoCH|MSS|BOS|structural\s+shift|reversal)\b[^.]{0,80}?"
            r"(?:idx|index|candle)\s*(-\d+)",
            text, re.IGNORECASE,
        )) if text else []

        if not reversal_mentions:
            result["flagged"] = True
            result["reason"] = (
                f"Direction claimed ({direction_claimed}) CONTRADICTS the STRONG "
                f"mechanical bias anchor ({anchor_dir}, based on agreeing swing "
                f"sequence AND last confirmed structural break at idx "
                f"{anchor_break_idx}) WITHOUT citing any specific CHoCH/MSS/BOS "
                f"reversal event with a candle index. Per the anchor's own rule: "
                f"a contradiction is only valid if a more recent genuine reversal "
                f"is named explicitly with its index."
            )
            return result

        # يوجد استشهاد على الأقل - نتحقق هل هو فعلاً أحدث من نقطة المرساة
        if anchor_break_idx is not None:
            cited_indices = [int(m.group(2)) for m in reversal_mentions]
            # الأحدث زمنياً = الأقرب للصفر (الأكبر رياضياً بين الأرقام
            # السالبة، مثال: -2 أحدث من -15)
            most_recent_cited = max(cited_indices)
            if most_recent_cited <= anchor_break_idx:
                result["flagged"] = True
                result["reason"] = (
                    f"Direction claimed ({direction_claimed}) contradicts the "
                    f"STRONG mechanical bias anchor ({anchor_dir}, last confirmed "
                    f"break at idx {anchor_break_idx}), and the reversal event "
                    f"cited (idx {most_recent_cited}) is NOT more recent than the "
                    f"anchor's own break point - it cannot represent a newer "
                    f"invalidation of the anchor. Cite a genuinely more recent "
                    f"reversal (larger index, closer to 0) or align with the anchor."
                )
        return result

    # ══════════════════════════════════════════════════════════
    #  STRUCTURAL SL ANCHOR CHECK - حل جذري (يوليو 2026، طلب صريح
    #  من المستخدم: "الستوب كتير صغير مع إنو سامحتلك لحد 2.5% وانت
    #  عم تحط الستوب عالنسبة، إنما مايكل بيحط الستوب اعتماداً
    #  عالمناطق وليس عالنسبة المئوية - تحت منطقة كذا كذا")
    # ══════════════════════════════════════════════════════════

    def audit_sl_is_structural(self, entry, sl, is_long, data, atr_val=None):
        """
        ⚠️ لماذا هذا الفحص ضروري: كل الفحوصات السابقة بالمشروع
        (SL_TOO_TIGHT/SL_TOO_WIDE بـmulti_pass_analysis.py) كانت تتحقق
        فقط من **مسافة رقمية مجردة** (نسبة% أو مضاعف ATR) - لا شيء كان
        يتحقق أن SL المُقترح يقع فعلياً **عند** مستوى هيكلي حقيقي
        (حافة Order Block، سوينغ حقيقي، نقطة سحب سيولة) بدل أن يكون
        مجرد رقم يحقق شرط المسافة حسابياً بلا أي ارتباط مكاني حقيقي
        بالبيانات.

        ⚠️ إصلاح خطأ رياضي حقيقي مُكتشف بفحص مباشر (يوليو 2026، أثناء
        بحث ويب موثّق حول كيف يضع مايكل الستوب فعلياً - راجع نتائج
        innercircletrader.net، backtrex.com، topwealthtrading.com):
        كل مصدر مستقل يؤكد أن الستوب الصحيح ليس *عند* المستوى الهيكلي
        نفسه، بل *أبعد منه بمسافة buffer صغيرة* ("10-20 pips beyond the
        OB extreme", "with a small buffer - past the level, not on it").
        النسخة الأولى من هذا الفحص استخدمت `tolerance_pct=0.15%` ثابتاً
        كهامش سماحية - لكن التحقق الرياضي المباشر أثبت أن الـbuffer
        الفعلي المطلوب أصلاً بمكان آخر بهذا المشروع (`_min_sl_buffer_
        distance` = max(0.3×ATR, 0.2%×price)) يمكن أن يتجاوز هذا الهامش
        الثابت (0.2% > 0.15% بمثال حقيقي) - أي أن SL محسوب **بشكل صحيح
        تماماً** حسب قسم [RISK_ENGINE] 15.3 نفسه (على الحافة الهيكلية
        ناقص/زائد الـbuffer الصحيح) كان سيُرفَض خطأً من هذا الفحص لأنه
        "بعيد جداً" عن الحافة - تناقض داخلي بين طبقتي حماية بنفس المشروع.

        الحل الصحيح: بدل هامش سماحية تعسفي ثابت، نتحقق أن SL يقع **بين
        المستوى الهيكلي نفسه وبين (المستوى الهيكلي ± buffer معقول
        بحساب رياضي حقيقي، لا نسبة تعسفية)** - أي: أبعد قليلاً من
        الحافة باتجاه الحماية الصحيح (منطقي)، لا عند الحافة تماماً
        (خطر - بلا هامش أمان)، ولا أبعد بكثير من الـbuffer المطلوب
        (يعني على الأرجح ليس مرتبطاً فعلياً بهذا المستوى تحديداً).

        Returns dict:
            {"is_structural": bool, "matched_anchor": dict أو None,
             "nearest_anchors_text": str (للحقن بالبرومبت عند الفشل)}
        """
        from ict_math_engine import find_structural_sl_anchors

        try:
            from multi_pass_analysis import MultiPassAnalysis
            buffer_dist = MultiPassAnalysis._min_sl_buffer_distance(entry, atr_val)
        except Exception:
            buffer_dist = abs(entry) * 0.002  # احتياط بسيط لو الاستيراد فشل لأي سبب

        # ⚠️ إصلاح جذري (يوليو 2026، اكتُشف بتحقق مباشر بعد نداء حي):
        # يجب البحث عن مستويات هيكلية حول سعر **الدخول المخطَّط**
        # (entry)، لا آخر سعر إغلاق فعلي وحده - أمر BUY_LIMIT/SELL_
        # LIMIT بحكم تعريفه عند منطقة مختلفة عن السعر الحالي، فالفحص
        # يجب أن يقيس "هل SL خلف منطقة هيكلية قرب نقطة الدخول نفسها؟"
        # لا "هل SL خلف منطقة هيكلية قرب السعر الحالي؟" (سؤال مختلف
        # تماماً، كان يُنتج نتائج فارغة/مضلِّلة فعلياً بالاختبار الحي).
        result = find_structural_sl_anchors(data, is_long=is_long, reference_price=entry)
        anchors = result.get("anchors", [])
        if not anchors:
            # لا مستويات هيكلية حقيقية مُكتشفة إطلاقاً بالنطاق المتاح -
            # لا يمكن الحكم (لا نفشل الفحص افتراضياً بلا دليل مضاد)
            return {"is_structural": True, "matched_anchor": None,
                    "nearest_anchors_text": "", "checked": False}

        # نطاق القبول لكل anchor: [المستوى الهيكلي نفسه، المستوى ± buffer]
        # (الاتجاه الصحيح فقط - أبعد باتجاه الحماية، لا باتجاه الدخول)
        # + هامش صغير جداً (10% من الـbuffer) لتفادي رفض فروق تقريب
        # عشرية مهملة (مثال: buffer=155.4 لكن الموديل استخدم 155.39).
        slack = buffer_dist * 0.10
        matched = None
        for a in anchors:
            level = a["price"]
            if is_long:
                # SL يجب أن يكون بين (level - buffer) و(level + slack بسيط)
                lower_bound = level - buffer_dist - slack
                upper_bound = level + slack
            else:
                lower_bound = level - slack
                upper_bound = level + buffer_dist + slack
            if lower_bound <= sl <= upper_bound:
                matched = a
                break

        anchors_text = "; ".join(
            f"{a['kind']}={a['price']:.6g} (idx {a['index_from_end']}, {a['detail']})"
            for a in anchors
        )

        return {
            "is_structural": matched is not None,
            "matched_anchor": matched,
            "nearest_anchors_text": anchors_text,
            "checked": True,
            "buffer_used": buffer_dist,
        }

    # ⚠️ صيغ نصية شائعة فعلياً بردود Nemotron لذكر قمة/قاع مع مرجعها
    # الزمني - جُمعت من فحص حقيقي لعشرات الردود الفعلية بالباك تيست
    # (وليست افتراضاً نظرياً): "HH at idx -15 (75,328)", "HH at 2457.0
    # (idx -1)", "idx -35 HL 1966.88", "HH at -28 76011.8".
    _STRUCTURE_LABEL_PATTERNS = [
        (re.compile(
            r"\b(HH|HL|LH|LL)\b\s*(?:formation\s+)?at\s+(?:idx|index|candle)\s*(-\d+)"
            r"(?:\s+(?:high|low))?\s*\(?\$?\s*(\d[\d,]{2,9}(?:\.\d+)?)\)?",
            re.IGNORECASE), (1, 2, 3)),
        (re.compile(
            r"\b(HH|HL|LH|LL)\b\s*at\s*\$?\s*(\d[\d,]{2,9}(?:\.\d+)?)\s*"
            r"\((?:idx|index|candle)\s*(-\d+)\)", re.IGNORECASE), (1, 3, 2)),
        (re.compile(
            r"(?:idx|index|candle)\s*(-\d+)\s+\b(HH|HL|LH|LL)\b\s+\$?\s*(\d[\d,]{2,9}(?:\.\d+)?)",
            re.IGNORECASE), (2, 1, 3)),
        (re.compile(
            r"\b(HH|HL|LH|LL)\b\s*at\s*(-\d+)\s+\$?\s*(\d[\d,]{2,9}(?:\.\d+)?)",
            re.IGNORECASE), (1, 2, 3)),
        # ⚠️ نمط خامس (اكتُشف بفجوة حقيقية باختبار حي، يوليو 2026):
        # "LH at 2200.0 (-2)" - السعر أولاً بلا قوس، ثم idx بقوس *بلا*
        # كلمة idx/index/candle قبله (بعكس النمط الثاني الذي يتطلب تلك
        # الكلمة صراحة داخل القوس: "LH at 2200.0 (idx -2)"). كلا الصيغتين
        # شائعتان فعلياً بردود النموذج الحقيقية - تحقق مباشر: نص حقيقي
        # فاشل سابقاً ("price formed a lower high at 2200.0 (-2)" بعد
        # التطبيع لـ"LH at 2200.0 (-2)") كان "claims_found: []" (لا
        # التقاط إطلاقاً) قبل إضافة هذا النمط - تناقض حقيقي كان يمر بصمت.
        (re.compile(
            r"\b(HH|HL|LH|LL)\b\s*at\s*\$?\s*(\d[\d,]{2,9}(?:\.\d+)?)\s*\((-\d+)\)",
            re.IGNORECASE), (1, 3, 2)),
        # ⚠️ نمط سابع (اكتُشف بفجوة حقيقية باختبار حي، يوليو 2026): "HL
        # at 76562 (candle -2 low)" - نفس بنية النمط الثاني لكن مع كلمة
        # "low"/"high" إضافية داخل القوس بعد الـidx مباشرة (بدل قوس نظيف
        # يحوي فقط idx). النمط الثاني الحالي (٣) يتطلب أن ينتهي القوس
        # مباشرة بعد idx - "-2 low)" لا يطابقه. تحقق مباشر: نص حقيقي
        # فاشل بالضبط ("HL at 76562 (candle -2 low) > 74825 (candle -7
        # low)") كان "claims_found: [{'HH'...}]" فقط (فقد ادعاء HL كاملاً)
        # قبل إضافة هذا النمط.
        (re.compile(
            r"\b(HH|HL|LH|LL)\b\s*at\s*\$?\s*(\d[\d,]{2,9}(?:\.\d+)?)\s*"
            r"\((?:idx|index|candle)\s*(-\d+)\s+(?:high|low)\)", re.IGNORECASE), (1, 3, 2)),
    ]

    # ⚠️ نمط ثامن - حالة خاصة (يوليو 2026، اكتُشف بفجوة حقيقية باختبار
    # حي): صيغة "range" تصف قمتين/قاعين معاً بضربة واحدة - مثال حقيقي
    # فاشل: "HH (idx -11: 78344.3 -> idx -7: 79462.3)" (بعد التطبيع من
    # "two confirmed Higher Highs (idx -11: 78344.3 -> idx -7: 79462.3)").
    # هذا مختلف بنيوياً عن الأنماط أعلاه (يحتوي رقمين/idx-ين بمطابقة
    # واحدة، لا واحداً) فلا يُدرَج بقائمة _STRUCTURE_LABEL_PATTERNS
    # العادية (تفترض 3 مجموعات فقط لكل مطابقة) - يُعالَج بمساره الخاص.
    _STRUCTURE_LABEL_RANGE_PATTERN = re.compile(
        r"\b(HH|HL|LH|LL)\b\s*\((?:idx|index|candle)\s*(-\d+)\s*:\s*\$?([\d,]+(?:\.\d+)?)\s*"
        r"(?:->|→|to)\s*(?:idx|index|candle)\s*(-\d+)\s*:\s*\$?([\d,]+(?:\.\d+)?)\)",
        re.IGNORECASE,
    )

    # ⚠️ نمط "range" ثانٍ - حالة أخطر (يوليو 2026، اكتُشفت بعد أن نجت
    # صفقة حقيقية بالضبط من الفحص الجديد أعلاه لمجرد اختلاف بسيط
    # بترتيب السعر/idx): "HH: 78344.3 idx -11 -> 79344.3 idx -7" - هنا
    # السعر يأتي أولاً بدون قوس حوله، بينما النمط أعلاه يتوقع idx أولاً
    # داخل قوس. الفرق قد يبدو تافهاً لكنه أدى فعلياً لتفويت اكتشاف خطأ
    # حقيقي مطابق تماماً (نفس مستوى 76562.3 المكسور فعلياً استُخدم مجدداً
    # بلا أي إنذار - checked_count=0 بالكامل رغم ادعاء صريح واضح). هذا
    # يؤكد نمطاً مقلقاً: صياغات نصية حرة كثيرة يمكن أن "تتهرب" من أي نمط
    # regex محدد سلفاً - لا يوجد حل نهائي 100% بهذا الأسلوب، لكن كل نمط
    # حقيقي فعلي نكتشفه يُسكَّر فوراً (راجع القيد الموثّق بنهاية الدالة).
    _STRUCTURE_LABEL_RANGE_PATTERN_2 = re.compile(
        r"\b(HH|HL|LH|LL)\b\s*:\s*\$?([\d,]+(?:\.\d+)?)\s*(?:idx|index|candle)\s*(-\d+)\s*"
        r"(?:->|→|to)\s*\$?([\d,]+(?:\.\d+)?)\s*(?:idx|index|candle)\s*(-\d+)",
        re.IGNORECASE,
    )

    def audit_structure_labels(self, text, data, price_tolerance_pct=0.1):
        """
        ⚠️ إصلاح خطأ حقيقي مُكتشف بالباك تيست الفعلي على 19 صفقة بشرية
        (يوليو 2026): النموذج يذكر أحياناً رقماً صحيحاً فعلياً (سعر
        حقيقي موجود بالشمعة المشار إليها) لكن **يصنّفه تصنيفاً هيكلياً
        خاطئاً** - مثال حقيقي موثّق (صفقة ETH، idx -2): النموذج كتب
        "LH formation at idx -2 high 2200" بينما القمة الفعلية عند
        idx -3 (السابقة زمنياً) كانت 2157.23 - يعني 2200 > 2157.23 =
        هذه فعلياً Higher High وليست Lower High كما زعم النص. نتيجة
        هذا الخطأ بالضبط: قرار SELL كامل مبني على قراءة معكوسة، بينما
        السوق صعد فعلياً +8.05% خلال 10 أيام (أثبت أن القمم كانت
        صاعدة فعلاً). مثال ثانٍ (صفقة BTC #15، idx -6 مقابل -28):
        النموذج قال "HH at -6 (72858.0)" لكن 72858 < 76011.8 (القمة
        عند idx -28) - Lower High حقيقي استُخدم كـ Higher High، مما
        شوّه حساب TP النهائي (استُخدم كهدف "قمة تالية" رغم كونه أوطى).

        هذا خطأ مختلف جذرياً عن audit_numeric_comparison_claims أعلاه
        (الذي يفحص مقارنات رقمية *صريحة* بعامل > أو < مكتوب حرفياً
        بالنص) - هنا لا يوجد عامل مقارنة صريح، فقط **تصنيف** (HH/HL/
        LH/LL) قد يتناقض ضمنياً مع الأرقام المرفقة معه أو مع الشمعة
        الفعلية المشار إليها بالـ idx. الحل الوحيد الموثوق (نفس فلسفة
        الإصلاح السابق): تحقق حسابي مستقل بلا أي اعتماد على "فهم"
        النموذج - نقارن مباشرة بأرقام OHLC الحقيقية.

        يفحص نوعين من التناقض:
          1. PRICE_MISMATCH: السعر المذكور مع idx لا يطابق فعلياً
             high/low تلك الشمعة بالبيانات الخام (النموذج اخترع أو
             حرّف رقماً).
          2. SEQUENCE_CONTRADICTION: التصنيف (HH يجب أن يتصاعد، LH
             يجب أن يتنازل عن القمة السابقة؛ وبالمثل HL/LL للقيعان)
             يناقض نفسه بين ادعاءين متتاليين بنفس النص.

        Returns dict: {"checked_count", "contradictions": [...],
                        "has_contradiction": bool, "claims_found": [...]}
        """
        if not text or not data:
            return {"checked_count": 0, "contradictions": [], "has_contradiction": False, "claims_found": []}

        # ⚠️ إصلاح فجوة حقيقية إضافية (يوليو 2026، اكتُشفت باختبار حي
        # فعلي بعد كل الإصلاحات السابقة): النموذج لا يلتزم دائماً
        # باستخدام الاختصار (HH/HL/LH/LL) - أحياناً يكتب العبارة كاملة
        # بأحرف صغيرة ("lower high at 2200.0 (-2)" بدل "LH at idx -2
        # (2200.0)") - وهذا **لم يكن يُلتقط إطلاقاً** بالأنماط السابقة
        # (تفترض الاختصار حصراً)، فتُرجع الدالة "claims_found: []" (لا
        # ادعاء البتة) رغم وجود ادعاء تصنيف واضح تماماً بالنص - يعني
        # تناقض حقيقي كان يمر تماماً بصمت. الحل: تطبيع النص أولاً (تحويل
        # كل صيغة كاملة معروفة لاختصارها المكافئ) قبل أي مطابقة - يوسّع
        # التغطية لكل الصياغات الشائعة الفعلية بلا الحاجة لتكرار كل نمط
        # مرتين (اختصار + عبارة كاملة).
        # ⚠️ إصلاح فجوة حقيقية إضافية (يوليو 2026، اكتُشفت باختبار حي):
        # الصيغة الجمع "Higher Highs" / "Higher Lows" (بحرف s إضافي في
        # النهاية - شائعة جداً عند وصف نمطين أو أكثر معاً، مثال حقيقي
        # فاشل: "two confirmed Higher Highs (idx -11... idx -7...) and
        # two confirmed Higher Lows (idx -12... idx -8...)") لم تكن
        # تُطابَق - الأنماط تطلب "high"/"low" بصيغة المفرد فقط، فـ"highs"
        # لا يطابق \bhigh\b. النتيجة: claims_found=[] بالكامل رغم وجود
        # ادعاءات هيكلية واضحة تماماً بالنص - فجوة تحقق صامتة كاملة.
        normalized_text = re.sub(
            r"\b(higher\s+highs?)\b", "HH", text, flags=re.IGNORECASE)
        normalized_text = re.sub(
            r"\b(higher\s+lows?)\b", "HL", normalized_text, flags=re.IGNORECASE)
        normalized_text = re.sub(
            r"\b(lower\s+highs?)\b", "LH", normalized_text, flags=re.IGNORECASE)
        normalized_text = re.sub(
            r"\b(lower\s+lows?)\b", "LL", normalized_text, flags=re.IGNORECASE)
        text = normalized_text

        highs = np.array(data.get("highs", []), dtype=float)
        lows = np.array(data.get("lows", []), dtype=float)
        n = len(highs)
        if n == 0:
            return {"checked_count": 0, "contradictions": [], "has_contradiction": False, "claims_found": []}

        claims = []
        seen_spans = []

        def _overlaps(span):
            return any(not (span[1] <= a or b <= span[0]) for a, b in seen_spans)

        # ⚠️ يُعالَج أولاً (قبل الأنماط العادية) ليحجز مساحته بـseen_spans
        # ويمنع الأنماط الأخرى من مطابقة جزء منه بشكل جزئي/خاطئ.
        for m in self._STRUCTURE_LABEL_RANGE_PATTERN.finditer(text):
            if _overlaps(m.span()):
                continue
            seen_spans.append(m.span())
            label = m.group(1).upper()
            try:
                claims.append({
                    "label": label, "idx": int(m.group(2)),
                    "claimed_price": float(m.group(3).replace(",", "")),
                })
                claims.append({
                    "label": label, "idx": int(m.group(4)),
                    "claimed_price": float(m.group(5).replace(",", "")),
                })
            except (ValueError, TypeError):
                continue

        # نفس المعالجة للنمط الثاني (السعر أولاً، ثم idx - بدل idx أولاً)
        for m in self._STRUCTURE_LABEL_RANGE_PATTERN_2.finditer(text):
            if _overlaps(m.span()):
                continue
            seen_spans.append(m.span())
            label = m.group(1).upper()
            try:
                claims.append({
                    "label": label, "idx": int(m.group(3)),
                    "claimed_price": float(m.group(2).replace(",", "")),
                })
                claims.append({
                    "label": label, "idx": int(m.group(5)),
                    "claimed_price": float(m.group(4).replace(",", "")),
                })
            except (ValueError, TypeError):
                continue

        for pattern, (lg, ig, pg) in self._STRUCTURE_LABEL_PATTERNS:
            for m in pattern.finditer(text):
                if _overlaps(m.span()):
                    continue
                seen_spans.append(m.span())
                try:
                    claims.append({
                        "label": m.group(lg).upper(),
                        "idx": int(m.group(ig)),
                        "claimed_price": float(m.group(pg).replace(",", "")),
                    })
                except (ValueError, TypeError):
                    continue

        checked = 0
        contradictions = []

        # ── فحص 1: السعر المذكور يطابق فعلياً high/low تلك الشمعة؟ ──
        for c in claims:
            arr_idx = n + c["idx"]
            if not (0 <= arr_idx < n):
                continue
            is_high_label = c["label"] in ("HH", "LH")
            actual = highs[arr_idx] if is_high_label else lows[arr_idx]
            checked += 1
            tolerance = max(actual * (price_tolerance_pct / 100), 0.5)
            if abs(actual - c["claimed_price"]) > tolerance:
                contradictions.append({
                    "type": "PRICE_MISMATCH",
                    "detail": (
                        f"{c['label']} at idx {c['idx']}: claimed price {c['claimed_price']} "
                        f"but actual {'high' if is_high_label else 'low'} of that candle is "
                        f"{actual:.2f} (mismatch > tolerance)"
                    ),
                })

        # ── حساب السوينغات الحقيقية الخام أولاً (نُصعِّد هذا الحساب
        # ليسبق الفحص 2 الآن - راجع تعليق الإصلاح الجذري أدناه) ──
        swing_window = 2
        raw_high_idx = [
            i for i in range(swing_window, n - swing_window)
            if highs[i] == max(highs[i - swing_window:i + swing_window + 1])
        ]
        raw_low_idx = [
            i for i in range(swing_window, n - swing_window)
            if lows[i] == min(lows[i - swing_window:i + swing_window + 1])
        ]

        # ── فحص 2: تسلسل HH يتصاعد / LH يتنازل عن السابق (وبالمثل HL/LL)
        # ⚠️ حل جذري لـfalse positive حقيقي مُكتشف باختبار حي (يوليو 2026):
        # هذا الفحص كان يقارن كل ادعاء مباشرة بـ"الادعاء السابق المذكور
        # بنفس النص" - لكن الموديل أحياناً يسرد ادعاءين متتاليين بنصه
        # بينما توجد فعلياً بالبيانات الخام قمة/قاع حقيقي *وسيط* من نفس
        # النوع لم يُذكر بالنص (اختصاراً بالسرد، لا خطأً). في هذه الحالة
        # المرجع الصحيح رياضياً لتصنيف الادعاء الثاني هو تلك النقطة
        # الوسيطة غير المذكورة - لا الادعاء الأبعد المذكور بالنص. مثال
        # حقيقي موثّق بالضبط (اختبار حي BTC/USDT 1d): النموذج ذكر "LH
        # at idx -30 (64381.9)" ثم "LH at idx -16 (65629.5)" - وكلا
        # التصنيفين صحيحان 100% رياضياً (يطابقان تماماً compute_
        # structure_sequence المحقونة مسبقاً بنفس البرومبت) لأن بينهما
        # قمة حقيقية عند idx -23 (67300.0، HH) لم تُذكر بهذين الادعاءين
        # تحديداً - لكن هذا الفحص قارن -16 مباشرة بـ-30 (تجاهل -23 لأنها
        # غير مذكورة بالنص) فاستنتج خطأً "65629.5 > 64381.9 = تناقض" رغم
        # أن -23 هي المرجع الصحيح، لا -30. النتيجة: 3 نداءات API إضافية
        # مُهدرة (2 دقيقة كاملة) لتصحيح تصنيف كان صحيحاً من الأساس.
        #
        # الحل: قبل الإبلاغ عن SEQUENCE_CONTRADICTION بين ادعاءين
        # متتاليين بالنص، نتحقق أولاً: هل توجد فعلياً (بالبيانات الخام،
        # مستقلة عن النص) نقطة سوينغ حقيقية من نفس النوع تقع زمنياً
        # *بين* الادعاءين ولم تُذكر بأي ادعاء بالنص؟ إن وُجدت، نتنحى
        # عن هذه المقارنة بالذات (الفحص 3 أدناه سيتحقق من كل ادعاء على
        # حدة ضد أقرب سوينغ حقيقي فعلي - المرجع الصحيح دائماً، بغض
        # النظر عمّا ذكره النص أو أغفله) - بدل الإبلاغ الخاطئ هنا.
        claims_sorted = sorted(claims, key=lambda c: c["idx"])
        highs_seq = [c for c in claims_sorted if c["label"] in ("HH", "LH")]
        lows_seq = [c for c in claims_sorted if c["label"] in ("HL", "LL")]

        def _has_unmentioned_intervening_swing(prev_c, curr_c, is_high_type):
            """هل توجد نقطة سوينغ حقيقية (من raw_high_idx/raw_low_idx)
            بين prev_c وcurr_c زمنياً، لم تُذكر كادعاء صريح بالنص؟"""
            prev_arr = n + prev_c["idx"]
            curr_arr = n + curr_c["idx"]
            candidate_idx = raw_high_idx if is_high_type else raw_low_idx
            mentioned_indices = {n + c["idx"] for c in claims if c["label"] in
                                  (("HH", "LH") if is_high_type else ("HL", "LL"))}
            for i in candidate_idx:
                if prev_arr < i < curr_arr and i not in mentioned_indices:
                    return True
            return False

        for seq, higher_label, lower_label, is_high_type in (
            (highs_seq, "HH", "LH", True), (lows_seq, "HL", "LL", False),
        ):
            for i in range(1, len(seq)):
                prev, curr = seq[i - 1], seq[i]
                if _has_unmentioned_intervening_swing(prev, curr, is_high_type):
                    # نقطة مرجعية أقرب حقيقية أُغفلت بالنص - الفحص 3 (أدق،
                    # يقارن بأقرب سوينغ حقيقي فعلياً) سيتولى التحقق الصحيح.
                    continue
                checked += 1
                if curr["label"] == higher_label and not (curr["claimed_price"] > prev["claimed_price"]):
                    contradictions.append({
                        "type": "SEQUENCE_CONTRADICTION",
                        "detail": (
                            f'You labeled idx {curr["idx"]} price {curr["claimed_price"]} as "{curr["label"]}" '
                            f'(should be HIGHER than the previous {prev["label"]} at idx {prev["idx"]} '
                            f'price {prev["claimed_price"]}), but {curr["claimed_price"]} is NOT greater than '
                            f'{prev["claimed_price"]} - this is mathematically a {lower_label}, not {higher_label}.'
                        ),
                    })
                elif curr["label"] == lower_label and not (curr["claimed_price"] < prev["claimed_price"]):
                    contradictions.append({
                        "type": "SEQUENCE_CONTRADICTION",
                        "detail": (
                            f'You labeled idx {curr["idx"]} price {curr["claimed_price"]} as "{curr["label"]}" '
                            f'(should be LOWER than the previous {prev["label"]} at idx {prev["idx"]} '
                            f'price {prev["claimed_price"]}), but {curr["claimed_price"]} is NOT less than '
                            f'{prev["claimed_price"]} - this is mathematically a {higher_label}, not {lower_label}.'
                        ),
                    })

        # ── فحص 3: مقارنة كل ادعاء منفرد بأقرب سوينغ حقيقي سابق فعلياً
        # من نفس نوعه (high مقابل high، low مقابل low)، محسوب مباشرة من
        # بيانات OHLC الخام - مستقل تماماً عن أي نص آخر بنفس الرد.
        # ⚠️ هذا يغطي بالضبط الحالة الحقيقية الموثّقة (صفقة ETH #6):
        # "LH formation at idx -2 high 2200" - النص لم يذكر صراحة رقم
        # القمة "السابقة" التي يقارن نفسه بها (فحص 2 أعلاه لا يستطيع
        # الإمساك بهذا لأنه يحتاج ادعاءين صريحين بنفس النص) - لكن
        # القمة الحقيقية السابقة (idx -3 = 2157.23، محسوبة من raw
        # swings) موجودة فعلياً بالبيانات، وبمقارنتها مباشرة: 2200 >
        # 2157.23 => Higher High حقيقي، وليس Lower High كما زُعم. ──

        for c in claims:
            arr_idx = n + c["idx"]
            if not (0 <= arr_idx < n):
                continue
            is_high_label = c["label"] in ("HH", "LH")
            candidate_idx = raw_high_idx if is_high_label else raw_low_idx
            # أقرب سوينغ حقيقي (من نفس النوع) يسبق هذا الـidx فعلياً
            prior_swings = [i for i in candidate_idx if i < arr_idx]
            if not prior_swings:
                continue
            prior_i = max(prior_swings)
            prior_price = highs[prior_i] if is_high_label else lows[prior_i]
            checked += 1
            higher_expected = c["label"] in ("HH", "HL")
            is_actually_higher = c["claimed_price"] > prior_price
            if higher_expected and not is_actually_higher:
                contradictions.append({
                    "type": "MECHANICAL_SWING_CONTRADICTION",
                    "detail": (
                        f'You labeled idx {c["idx"]} price {c["claimed_price"]} as "{c["label"]}", '
                        f"but the actual previous swing {'high' if is_high_label else 'low'} "
                        f"(mechanically detected, independent of your reasoning) at idx "
                        f"{prior_i - n} is {prior_price:.2f} - since {c['claimed_price']} is NOT "
                        f"greater than {prior_price:.2f}, this is mathematically a "
                        f"{'LH' if is_high_label else 'LL'}, not {c['label']}."
                    ),
                })
            elif not higher_expected and is_actually_higher:
                contradictions.append({
                    "type": "MECHANICAL_SWING_CONTRADICTION",
                    "detail": (
                        f'You labeled idx {c["idx"]} price {c["claimed_price"]} as "{c["label"]}", '
                        f"but the actual previous swing {'high' if is_high_label else 'low'} "
                        f"(mechanically detected, independent of your reasoning) at idx "
                        f"{prior_i - n} is {prior_price:.2f} - since {c['claimed_price']} IS "
                        f"greater than {prior_price:.2f}, this is mathematically a "
                        f"{'HH' if is_high_label else 'HL'}, not {c['label']}."
                    ),
                })

        # ── فحص 4 (يوليو 2026، بعد 3 محاولات درس نصي فشلت بمنع نفس الخطأ
        # فعلياً - راجع lesson_learning.py، صفقة BTC #1، دروس متتالية):
        # هل النقطة المُدَّعاة ذاتها هي أصلاً "قاع/قمة متأرجحة" حقيقية
        # بالتعريف الميكانيكي الصارم (قسم SWING_DETECTION 3.1: يجب أن
        # تكون أدنى/أعلى من الجارين على **كلا** الجهتين)، أم مجرد نقطة
        # ضمن مسار متجه (سلسلة قمم/قيعان متتالية بلا ارتداد فعلي بينها)؟
        #
        # ⚠️ هذا فحص مختلف جوهرياً عن الفحص 3 أعلاه: الفحص 3 يقارن
        # الادعاء بأقرب سوينغ *سابق* (يفترض ضمنياً أن الادعاء نفسه سوينغ
        # صحيح). هذا الفحص الجديد يتحقق من الادعاء *نفسه*: هل هو أصلاً
        # نقطة تحول حقيقية، أم نقطة بمنتصف انحدار/صعود متواصل بلا ارتداد؟
        #
        # مثال حقيقي موثّق بالضبط (صفقة BTC #1، بعد 3 محاولات درس فشلت):
        # النموذج كتب "HL at candle -2 (76562.3)" - لكن الشمعة idx -1
        # (الجار الأيمن المباشر، متاحة فعلاً بالبيانات) سجّلت low أدنى
        # (75660.1) - يعني السعر لم "يرتد بعيداً" عن idx -2 إطلاقاً، بل
        # استمر بالهبوط - idx -2 لم تكن قاعاً متأرجحاً من الأساس، كانت
        # نقطة ضمن انحدار متواصل (idx -3: 77129.5 -> idx -2: 76562.3 ->
        # idx -1: 75660.1، قيعان متتالية أخفض بلا ارتداد بينها).
        for c in claims:
            arr_idx = n + c["idx"]
            if not (0 <= arr_idx < n):
                continue
            is_high_label = c["label"] in ("HH", "LH")
            arr = highs if is_high_label else lows
            # نتحقق من أقرب جار على كل جهة تتوفر بالبيانات (حافة
            # البيانات لا تُحاسَب - لا "مستقبل" كافٍ للحكم عليها بعدل،
            # نفس فلسفة _classify/UNCONFIRMED_RECENT بـdetect_significant_swings)
            has_left = arr_idx - 1 >= 0
            has_right = arr_idx + 1 < n
            if not (has_left and has_right):
                continue  # على حافة البيانات - لا حكم متسرع
            checked += 1
            left_val = arr[arr_idx - 1]
            right_val = arr[arr_idx + 1]
            claimed = c["claimed_price"]
            if is_high_label:
                # قمة حقيقية يجب أن تكون >= كلا الجارين (على الأقل محلياً)
                violates = right_val > claimed or left_val > claimed
                violator_side = "right (more recent)" if right_val > claimed else "left (older)"
                violator_val = right_val if right_val > claimed else left_val
            else:
                # قاع حقيقي يجب أن يكون <= كلا الجارين (على الأقل محلياً)
                violates = right_val < claimed or left_val < claimed
                violator_side = "right (more recent)" if right_val < claimed else "left (older)"
                violator_val = right_val if right_val < claimed else left_val
            if violates:
                contradictions.append({
                    "type": "NOT_A_REAL_SWING_POINT",
                    "detail": (
                        f'You labeled idx {c["idx"]} price {claimed} as "{c["label"]}" '
                        f"(a swing {'high' if is_high_label else 'low'}), but this point is "
                        f"NOT mechanically a swing point at all: its immediate {violator_side} "
                        f"neighbor candle has a {'higher' if is_high_label else 'lower'} "
                        f"{'high' if is_high_label else 'low'} ({violator_val:.2f}) - meaning "
                        f"price never actually reversed away from this level on that side. "
                        f"This is a point inside a continuing directional move (a candle in an "
                        f"uninterrupted sequence), not a genuine turning point. Per section "
                        f"[SWING_DETECTION] 3.1, a swing point requires being the local extreme "
                        f"relative to BOTH neighboring sides - re-derive using the actual most "
                        f"recent point that genuinely qualifies as a swing (where price reversed "
                        f"away on both sides), not simply 'the lowest/highest value glanced at "
                        f"in a recent window'."
                    ),
                })

        return {
            "checked_count": checked,
            "contradictions": contradictions,
            "has_contradiction": len(contradictions) > 0,
            "claims_found": claims,
        }

    # ══════════════════════════════════════════════════════════
    #  دوال مساعدة
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _atr(highs, lows, closes, period=14):
        h, l, c = highs, lows, closes
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
    def _is_round_number(price):
        """يحدد إذا السعر رقم 'مدور' واضح (مثل 100000, 50000, 3000)"""
        if price <= 0:
            return False
        magnitude = 10 ** (len(str(int(price))) - 2)
        return price % magnitude == 0

    # ══════════════════════════════════════════════════════════
    #  SMT DIVERGENCE (بين أصلين مترابطين - مثلاً BTC مقابل ETH)
    # ══════════════════════════════════════════════════════════
    # ⚠️ أُضيف بطلب المستخدم بعد مراجعة كتب ICT الرسمية المرفوعة
    # (اعتُبرت "الأساس" لمنهجية ICT بالكامل - راجع
    # ict_source_material/ICT_BOOKS_EXTRACTION_SUMMARY.md للتفاصيل
    # الكاملة). SMT Divergence غير موجود بأي مكان آخر بالكود قبل هذا -
    # فجوة حقيقية بمصدر رسمي مؤكَّد، وليس مجرد "فكرة إضافية اختيارية".
    #
    # التعريف الرياضي (من نفس المصدر الرسمي، "ALL SMT FORMULATED ON
    # DAILY CHART"): مقارنة أصلين مترابطين طبيعياً (هنا: BTC/USDT
    # وETH/USDT، الزوجان الوحيدان بمشروعنا، وهما مترابطان تاريخياً
    # بقوة). لو أحدهما شكّل قاعاً/قمة أخفض/أعلى بوضوح والآخر "فشل" أن
    # يطابقه (شكّل قاعاً أعلى بدل أخفض، أو قمة أخفض بدل أعلى)، هذا
    # "تباعد" (Divergence) يدل على تراكم/توزيع مسبق قبل حركة عكسية -
    # دليل رياضي مستقل تماماً عن أي تفسير AI، يُحقن كأدلة إضافية فقط
    # (لا يُغيّر مسار القرار وحده - نفس فلسفة بقية هذا الملف).
    def detect_smt_divergence(self, data_a, data_b, label_a="BTC", label_b="ETH",
                               swing_window=2, lookback_candles=60):
        """
        يقارن آخر قمتين/قاعين متأرجحتين "مؤكدتين" (نفس منطق
        detect_significant_swings) بين أصلين، ويكتشف حالات الفشل
        بالمطابقة (divergence) - إشارة انعكاس محتملة مستقلة رياضياً.

        Args:
            data_a, data_b: بيانات OHLC لكل أصل (نفس الفريم الزمني -
                يجب أن يكونا بنفس التوقيت لتكون المقارنة ذات معنى؛
                الاستخدام العملي المقصود: فريم Daily لكلا الزوجين،
                كما يوصي المصدر الرسمي صراحة).
            label_a, label_b: أسماء الأصلين للعرض بالنتيجة فقط.

        Returns:
            dict: {
                "checked": bool (هل توفرت بيانات كافية للفحص أصلاً),
                "bullish_divergence": bool (فشل بعمل قاع أخفض = صعودي محتمل),
                "bearish_divergence": bool (فشل بعمل قمة أعلى = هبوطي محتمل),
                "detail": نص يشرح أي أصل فشل وبأي مستوى بالضبط,
            }

        ⚠️ صدق تقني: يعتمد على detect_significant_swings لكل أصل على
        حدة (نفس الخوارزمية المستخدمة بكل مكان آخر بالمشروع لتفادي
        ازدواجية منطق) - لا يخترع كشف قمم/قيعان جديداً. لو أي أصل ما
        عنده قمتين/قاعين مؤكدتين كافيتين للمقارنة، يرجع checked=False
        بدل تخمين نتيجة غير موثوقة.
        """
        result = {
            "checked": False, "bullish_divergence": False,
            "bearish_divergence": False, "detail": "",
        }
        try:
            sig_a = self.detect_significant_swings(
                data_a, swing_window=swing_window, lookback_candles=lookback_candles, top_n=5
            )
            sig_b = self.detect_significant_swings(
                data_b, swing_window=swing_window, lookback_candles=lookback_candles, top_n=5
            )
        except Exception as e:
            result["detail"] = f"SMT check failed to compute swings: {e}"
            return result

        # ⚠️ إصلاح فوري أثناء التحقق الأول (اكتشاف فعلي): significant_lows/highs
        # المُرجعة رسمياً تقتصر على MAJOR+MODERATE فقط (تصفية متشددة مقصودة
        # لفلترة الضجيج بأماكن أخرى بالمشروع) - تحقق فعلي مباشر على بيانات BTC/ETH
        # حقيقية (Daily، 90 شمعة) أظهر: غالباً يوجد قاع/قمة MODERATE واحد فقط
        # ضمن نافذة 60 شمعة - غير كافٍ لمقارنة SMT (تحتاج نقطتين على الأقل).
        # الحل: نستخدم all_lows_tiered/all_highs_tiered مباشرة (كل المستويات) مع
        # استبعاد الضجيج الحقيقي فقط (التي لا تصنّف ضمن أي tier أصلاً - prominence
        # أقل من 0.5×ATR) - هذا يوسّع عيّنة المقارنة بشكل معقول (يقبل MINOR أيضاً،
        # لا MAJOR/MODERATE فقط) دون التقاط ضجيج محلي حقيقي (مستبعد بالفعل بالفعل عبر الحد
        # الأدنى).
        def _usable_points(tiered_list):
            return [
                p for p in tiered_list
                if p.get("tier") in ("MAJOR", "MODERATE", "MINOR")
            ]

        lows_a = sorted(_usable_points(sig_a.get("all_lows_tiered", [])), key=lambda x: x.get("index_from_end", -999999))
        lows_b = sorted(_usable_points(sig_b.get("all_lows_tiered", [])), key=lambda x: x.get("index_from_end", -999999))
        highs_a = sorted(_usable_points(sig_a.get("all_highs_tiered", [])), key=lambda x: x.get("index_from_end", -999999))
        highs_b = sorted(_usable_points(sig_b.get("all_highs_tiered", [])), key=lambda x: x.get("index_from_end", -999999))

        if len(lows_a) >= 2 and len(lows_b) >= 2:
            a_lower_low = lows_a[-1]["price"] < lows_a[-2]["price"]
            b_lower_low = lows_b[-1]["price"] < lows_b[-2]["price"]
            if a_lower_low and not b_lower_low:
                result["checked"] = True
                result["bullish_divergence"] = True
                result["detail"] = (
                    f"{label_a} made a LOWER low ({lows_a[-2]['price']}->{lows_a[-1]['price']}) "
                    f"but {label_b} FAILED to make a lower low "
                    f"({lows_b[-2]['price']}->{lows_b[-1]['price']}) - bullish SMT divergence, "
                    f"suggests possible accumulation before a reversal up."
                )
            elif b_lower_low and not a_lower_low:
                result["checked"] = True
                result["bullish_divergence"] = True
                result["detail"] = (
                    f"{label_b} made a LOWER low but {label_a} FAILED to - bullish SMT "
                    f"divergence favoring {label_a}."
                )
            else:
                result["checked"] = True

        if len(highs_a) >= 2 and len(highs_b) >= 2:
            a_higher_high = highs_a[-1]["price"] > highs_a[-2]["price"]
            b_higher_high = highs_b[-1]["price"] > highs_b[-2]["price"]
            if a_higher_high and not b_higher_high:
                result["checked"] = True
                result["bearish_divergence"] = True
                result["detail"] += (
                    f" | {label_a} made a HIGHER high ({highs_a[-2]['price']}->{highs_a[-1]['price']}) "
                    f"but {label_b} FAILED to make a higher high "
                    f"({highs_b[-2]['price']}->{highs_b[-1]['price']}) - bearish SMT divergence, "
                    f"suggests possible distribution before a reversal down."
                )
            elif b_higher_high and not a_higher_high:
                result["checked"] = True
                result["bearish_divergence"] = True
                result["detail"] += (
                    f" | {label_b} made a HIGHER high but {label_a} FAILED to - bearish SMT "
                    f"divergence favoring {label_a}."
                )

        if result["checked"] and not result["detail"]:
            result["detail"] = f"No SMT divergence detected between {label_a} and {label_b} currently."

        return result

    # ══════════════════════════════════════════════════════════
    #  ملخص شامل جاهز للحقن بالـ Prompt
    # ══════════════════════════════════════════════════════════

    def build_authenticity_report(self, data, checks_requested=None):
        """
        يبني تقرير أساسي جاهز (فحوصات عامة لا تحتاج معطيات إضافية)
        يمكن إرفاقه مباشرة بالـ prompt المرسل للـ AI كـ "أدلة تحقق مسبقة".

        ⚠️ توسيع حقيقي (يوليو 2026، بعد تحليل reading_comprehension_test):
        أُضيف significant_swings و most_recent_sweep - كانا موجودين
        كدالتين جاهزتين بالكود (detect_significant_swings, classify_sweep
        عبر detect_most_recent_sweep) لكن **لم تكونا مُستدعاتين من أي
        مكان فعلي بمسار التحليل الحي** - الـ AI كان يُترك يخمّن "أي قمة
        مهمة" و"هل السحب حقيقي أو وهمي" من الصفر بلا أي سقالة رياضية،
        رغم وجود الأدوات جاهزة. الآن تُحقن كأدلة سابقة يتحقق منها الـ AI
        ويفسّرها، بدل أن يخترعها بمعزل تام عن أي حساب مستقل.
        """
        report = {}
        try:
            report["volume_authenticity"] = self.check_volume_authenticity(data)
        except Exception as e:
            report["volume_authenticity"] = {"error": str(e)}

        try:
            report["significant_swings"] = self.detect_significant_swings(data)
        except Exception as e:
            report["significant_swings"] = {"error": str(e)}

        # ⚠️ حل جذري (يوليو 2026، بطلب صريح من المستخدم): تصنيف
        # HH/HL/LH/LL يُحسب رياضياً قبل وصوله للـAI بدل تركه
        # يخترعه من الصفر ثم تصحيحه بإعادة محاولة مكلفة -
        # راجع compute_structure_sequence() للتفصيل الكامل.
        try:
            report["structure_sequence"] = self.compute_structure_sequence(data)
        except Exception as e:
            report["structure_sequence"] = {"error": str(e)}

        try:
            report["most_recent_liquidity_sweep"] = self.detect_most_recent_sweep(data)
        except Exception as e:
            report["most_recent_liquidity_sweep"] = {"error": str(e)}

        # ⚠️ إضافة جوهرية (طلب المستخدم صراحة): "استنباطها وترابطها
        # وتقاطعها" - لا يكفي حقن حقائق منفصلة (BOS، Sweep، Swings)
        # كل واحدة بمعزل عن الأخرى. هذه السلسلة تربطها رياضياً ببعضها
        # (Sweep → Order Block → Displacement → FVG → BOS) وتبني سرداً
        # صريحاً للترابط السببي - إن وُجد فعلاً أو لم يوجد.
        try:
            report["causal_derivation_chain"] = self.build_causal_derivation_chain(data)
        except Exception as e:
            report["causal_derivation_chain"] = {"error": str(e)}

        return report

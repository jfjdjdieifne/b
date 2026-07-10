# -*- coding: utf-8 -*-
"""
ict_math_engine.py - كشف رياضي بحت (بلا أي AI) لكل مفهوم أساسي بمنهجية
مايكل هدلستون (ICT)، مبني حرفياً على التعريفات الموثّقة من مصادر ICT
متعددة (راجع البحث المرفق بجلسة يوليو 2026 - innercircletrader.net،
tradingstrategyguides.com، backtrex.com، وغيرها).
════════════════════════════════════════════════════════════════════
⚠️ لماذا هذا الملف ضروري (حل جذري لمشكلة حقيقية): الموديل اللغوي
(Nemotron) لا "يفهم" التداول أصلاً - هو نموذج نصي احتمالي. سابقاً كنا
نطلب منه "ابحث عن Fair Value Gap" بجملة عامة بالبرومبت ونتركه "يخترع"
كيف يحسبها من الأرقام الخام - هذا بالضبط مصدر كل أخطاء الهلوسة
والتصنيف الخاطئ الموثّقة (راجع السجل الكامل). الحل الجذري الوحيد:
نحسب كل هذه المفاهيم **رياضياً بحتاً هنا أولاً** (تعريف صارم، بلا
غموض، مطابق حرفياً لتعريف ICT الموثّق)، ثم نحقنها كـ"حقائق جاهزة"
للموديل ليتحقق منها ويبني تفسيره عليها - بدل أن يخترعها من الصفر.

كل دالة هنا موثّقة بـ: (1) التعريف الحرفي من مصدر ICT، (2) لماذا هذا
الشرط بالتحديد (لا اعتباطي)، (3) مثال رقمي حقيقي محسوب داخل الاختبارات.
"""
import numpy as np


def _atr(highs, lows, closes, period=14):
    """نفس حساب AuthenticityEngine._atr بالضبط - معاد هنا لتفادي استيراد
    دائري (authenticity_engine.py قد يستورد من هنا مستقبلاً)."""
    h, l, c = np.asarray(highs, dtype=float), np.asarray(lows, dtype=float), np.asarray(closes, dtype=float)
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


# ══════════════════════════════════════════════════════════════════
#  1) DISPLACEMENT (الاندفاع) - الأساس الذي يُبنى عليه كل شيء آخر
# ══════════════════════════════════════════════════════════════════
#
# ملاحظة أمانة المصدر: مايكل يصف displacement كحركة energetic واضحة
# بإغلاق حاسم، لكنه لا ينشر قاعدة موحدة تقول 1.5×ATR و65% لكل أصل وفريم.
# الرقمان أدناه **تعريف تشغيلي خاص بهذا البوت** مأخوذ من أدوات ثانوية
# لتوحيد الاختبار، وليس "تعريف ICT حرفي". السياسة الحالية تتطلب:
#   (أ) جسم الشمعة (|close-open|) >= 1.5 × ATR(14)، و
#   (ب) body/range >= 65%.
# فائدتهما فلترة شمعة كبيرة كلها فتيل، لكن يجب معايرتهما واختبارهما لكل
# سوق؛ لا يجوز تقديمهما للمستخدم كحقيقة صادرة عن مايكل.
#
# ⚠️ ملاحظة توضيحية هامة (مراجعة شاملة يوليو 2026، بحث خارجي مستقل):
# نص [OHLC_PROCESSING] 2.3 المحلي يذكر شرطاً ثالثاً "vol_ratio > 1.5"
# كإلزامي ("ALL must be present"). تم التحقق فعلياً من أداة FibAlgo
# المرجعية نفسها (TradingView، الموثّقة كمصدر) - قائمة طرق الكشف
# الثلاث الرسمية عندها ("ATR Multiple"، "Body/Range Ratio"، "Both AND")
# **لا تتضمن الحجم إطلاقاً** في أي منها. هذا متوافق أيضاً مع قسم
# [CRYPTO_MARKET_DATA] 19.3 بالدستور نفسه الذي يصنّف بيانات الحجم
# كـ"تكميلية" (حد أقصى ±10% تأثير على الثقة)، لا كشرط بوابة قاطع.
# القرار المتعمَّد هنا: الحجم لا يدخل كشرط إلزامي بتعريف الديسبليسمنت
# الأساسي (متوافق مع الممارسة الفعلية لأدوات ICT المرجعية)، لكنه
# يُستخدَم كعامل منفصل مستقل بمكان آخر بالمشروع (راجع
# compute_structural_break_quality_score، Factor 3 "volume_on_break").
# هذا ليس إغفالاً - قرار مبني على دليل خارجي، لا افتراض ذاتي.

def compute_displacement(data, lookback=30):
    """
    يفحص كل شمعة بآخر lookback شمعة، ويصنّفها displacement حقيقي أو لا،
    بالمعيارين الصارمين معاً (لا أحدهما فقط - هذا فرق جذري عن "أي شمعة
    كبيرة" الذي كان يُترك للموديل يخترعه سابقاً).

    Returns dict:
        {
            "displacement_candles": [
                {"index_from_end", "direction", "body_pct", "body_atr_ratio"}
            ],
            "most_recent_displacement": {...} أو None,
        }
    """
    opens = np.asarray(data.get("opens", []), dtype=float)
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 20:
        return {"displacement_candles": [], "most_recent_displacement": None}

    atr = _atr(highs, lows, closes)
    start = max(1, n - lookback)
    results = []
    for i in range(start, n):
        if atr[i] <= 0:
            continue
        body = abs(closes[i] - opens[i])
        rng = highs[i] - lows[i]
        if rng <= 0:
            continue
        body_pct = body / rng
        body_atr_ratio = body / atr[i]
        is_displacement = (body_atr_ratio >= 1.5) and (body_pct >= 0.65)
        if is_displacement:
            results.append({
                "index_from_end": i - n,
                "direction": "BULLISH" if closes[i] > opens[i] else "BEARISH",
                "body_pct": round(body_pct * 100, 1),
                "body_atr_ratio": round(body_atr_ratio, 2),
                "open": round(float(opens[i]), 6),
                "close": round(float(closes[i]), 6),
                "high": round(float(highs[i]), 6),
                "low": round(float(lows[i]), 6),
            })

    return {
        "displacement_candles": results,
        "most_recent_displacement": results[-1] if results else None,
    }


# ══════════════════════════════════════════════════════════════════
#  2) FAIR VALUE GAP (FVG) - تعريف الـ3 شمعات الحرفي
# ══════════════════════════════════════════════════════════════════
#
# تعريف FVG الثلاثي موضح في مواد ICT الأولية: تكوين من 3 شمعات متتالية
# (idx-2, idx-1, idx). أمّا اشتراط displacement بعتبة ATR الرقمية فهو
# فلتر جودة خاص بالبوت، لا جزءاً من تعريف كل FVG عند مايكل:
#   FVG صاعدة: low(idx) > high(idx-2)  [فجوة بين قمة الشمعة الأولى
#              وقاع الشمعة الثالثة - الشمعة الوسطى idx-1 هي شمعة
#              الاندفاع التي "قفزت" فوق هذا المستوى]
#   FVG هابطة: high(idx) < low(idx-2)  [نفس المنطق معكوساً]
# نقطة الدخول المرجعية (Consequent Encroachment/CE) = المنتصف الحسابي
# بين حافتي الفجوة بالضبط (50%) - موثّق بكل مصدر كـ"نقطة الدخول
# الأدق"، لا حافة الفجوة نفسها.
# ⚠️ فلتر إضافي حاسم (موثّق: "ليس كل FVG قابلة للتداول"): نتجاهل أي
# فجوة لم تنتج عن شمعة اندفاع حقيقية (راجع compute_displacement أعلاه)
# - فجوة بلا اندفاع خلفها = ضجيج سعري عادي، لا بصمة مؤسساتية حقيقية.

def detect_fair_value_gaps(data, lookback=40, require_displacement=True):
    """
    يكتشف كل الـ FVG الحقيقية (بتعريف الـ3 شمعات الصارم) ضمن آخر
    lookback شمعة، ويحسب حافتيها + الـ CE (نقطة الدخول المرجعية)، مع
    فلتر اختياري (افتراضياً مفعّل) يستبعد أي فجوة لم تصاحبها شمعة
    اندفاع حقيقية بالشمعة الوسطى.

    Returns dict:
        {
            "bullish_fvgs": [{"index_from_end","top","bottom","ce",
                               "filled_pct","displacement_confirmed"}],
            "bearish_fvgs": [...],
        }
    حيث index_from_end يشير للشمعة idx (الثالثة/الأحدث بالتكوين).
    filled_pct: نسبة ما امتلأ من الفجوة فعلياً حتى آخر شمعة متاحة
    (0% = لم تُختبر إطلاقاً، 100% = امتلأت بالكامل/أُبطلت).
    """
    opens = np.asarray(data.get("opens", []), dtype=float)
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 10:
        return {"bullish_fvgs": [], "bearish_fvgs": []}

    disp_info = compute_displacement(data, lookback=lookback + 5)
    disp_indices = {d["index_from_end"] + n for d in disp_info["displacement_candles"]}

    start = max(2, n - lookback)
    bullish, bearish = [], []
    for idx in range(start, n):
        i_first, i_mid, i_third = idx - 2, idx - 1, idx
        # FVG صاعدة: قاع الشمعة الثالثة أعلى من قمة الشمعة الأولى
        if lows[i_third] > highs[i_first]:
            top, bottom = lows[i_third], highs[i_first]
            ce = (top + bottom) / 2
            # نسبة الامتلاء: كم دخل السعر بالفجوة منذ تكوّنها حتى الآن
            filled_pct = _compute_fill_pct(lows, i_third + 1, n, top, bottom, is_bullish=True)
            bullish.append({
                "index_from_end": idx - n,
                "top": round(float(top), 6),
                "bottom": round(float(bottom), 6),
                "ce": round(float(ce), 6),
                "filled_pct": filled_pct,
                "displacement_confirmed": i_mid in disp_indices,
            })
        # FVG هابطة: قمة الشمعة الثالثة أدنى من قاع الشمعة الأولى
        if highs[i_third] < lows[i_first]:
            top, bottom = lows[i_first], highs[i_third]
            ce = (top + bottom) / 2
            filled_pct = _compute_fill_pct(highs, i_third + 1, n, top, bottom, is_bullish=False)
            bearish.append({
                "index_from_end": idx - n,
                "top": round(float(top), 6),
                "bottom": round(float(bottom), 6),
                "ce": round(float(ce), 6),
                "filled_pct": filled_pct,
                "displacement_confirmed": i_mid in disp_indices,
            })

    if require_displacement:
        bullish = [f for f in bullish if f["displacement_confirmed"]]
        bearish = [f for f in bearish if f["displacement_confirmed"]]

    return {"bullish_fvgs": bullish, "bearish_fvgs": bearish}


def _compute_fill_pct(arr, start_idx, n, top, bottom, is_bullish):
    """يحسب كم % من الفجوة امتلأ فعلياً بالسعر اللاحق (لا نظري)."""
    gap_size = top - bottom
    if gap_size <= 0 or start_idx >= n:
        return 0.0
    if is_bullish:
        # الفجوة تُملأ من الأعلى للأسفل (السعر يرجع تحت top باتجاه bottom)
        deepest = min(arr[start_idx:n]) if start_idx < n else top
        filled = max(0.0, top - deepest)
    else:
        deepest = max(arr[start_idx:n]) if start_idx < n else bottom
        filled = max(0.0, deepest - bottom)
    return round(min(100.0, filled / gap_size * 100), 1)


# ══════════════════════════════════════════════════════════════════
#  3) ORDER BLOCK - الشروط الأربعة الحرفية (لا مجرد "آخر شمعة معاكسة")
# ══════════════════════════════════════════════════════════════════
#
# مايكل يعرّف الـOrder Block سياقياً كتغيّر في حالة التسليم، ويؤكد أن
# ليست كل شمعة معاكسة Order Block. الشروط التالية سياسة آلية محافظة
# لاختيار مرشح عالي الجودة وليست «الشروط الحرفية الأربعة» المنشورة منه:**الشروط
# الأربعة معاً**:
#   1. الشمعة الثانية (الاندفاع) يجب أن "تلمس" (تخترق بالفتيل) قاع
#      الشمعة الأولى (المعاكسة) قبل الانعكاس - ليس مجرد شمعة تالية عشوائية.
#   2. الشمعة الثانية يجب أن **تُغلق فوق قمة** الشمعة الأولى بالكامل
#      (ابتلاع body-to-body و wick-to-wick - "engulf" حقيقي، لا جزئي).
#   3. فجوة سيولة (FVG) تتشكل داخل/فوق منطقة الـ OB مباشرة نتيجة نفس
#      الاندفاع (لا فجوة منفصلة بمكان آخر - يجب أن تكون نفس الحركة).
#   4. تحوّل هيكلي (MSS) يؤكد النية الصاعدة على فريم أصغر.
# ⚠️ هذا فرق جذري عن التعريف المبسّط الشائع ("آخر شمعة معاكسة قبل
# اندفاع" فقط) الذي كان مستخدماً سابقاً بكودنا (validate_order_block
# القديمة بـauthenticity_engine.py تفحص "علامات حمراء" لاحقة، لا هذه
# الشروط التأسيسية الأربعة نفسها وقت التكوّن). هنا نطبّق الشروط
# الأربعة كاملة كفلتر تكويني، لا كفحص جودة بعدي فقط.

def detect_order_blocks(data, lookback=40):
    """Return *active, fresh, displacement-backed* order-block candidates.

    ICT's primary material describes an order block contextually as a change
    in the state of delivery; it does not publish a universal ATR equation.
    The checks below are therefore an explicit bot policy, not a claim that
    Michael published these exact numeric rules:

    * opposite candle immediately before an engulfing impulse;
    * the impulse passes this project's displacement filter;
    * an FVG is created by the same impulse;
    * no later close invalidates the block;
    * at most two distinct mitigations (older repeatedly-tested blocks are
      reported in ``rejected_candidates`` but never selected for entry).
    """
    opens = np.asarray(data.get("opens", []), dtype=float)
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 15:
        return {"bullish_obs": [], "bearish_obs": [], "rejected_candidates": []}

    fvgs = detect_fair_value_gaps(data, lookback=lookback + 5, require_displacement=False)
    bullish_fvg_starts = {f["index_from_end"] + n - 2 for f in fvgs["bullish_fvgs"]}
    bearish_fvg_starts = {f["index_from_end"] + n - 2 for f in fvgs["bearish_fvgs"]}
    displacement = compute_displacement(data, lookback=lookback + 5)
    displacement_indices = {
        d["index_from_end"] + n for d in displacement["displacement_candles"]
    }

    start = max(1, n - lookback)
    bullish_obs, bearish_obs, rejected = [], [], []

    def _candidate(i, direction, fvg_nearby, engulf_confirmed):
        impulse_idx = i + 1
        top, bottom = float(highs[i]), float(lows[i])
        tested_count = _count_retests(lows, highs, i + 2, n, top, bottom)
        if direction == "BULLISH":
            invalidation_indices = [j for j in range(i + 2, n) if closes[j] < bottom]
        else:
            invalidation_indices = [j for j in range(i + 2, n) if closes[j] > top]
        invalidated = bool(invalidation_indices)
        displacement_confirmed = impulse_idx in displacement_indices
        fresh = tested_count <= 2
        item = {
            "index_from_end": i - n,
            "impulse_index_from_end": impulse_idx - n,
            "top": round(top, 6),
            "bottom": round(bottom, 6),
            "engulf_confirmed": bool(engulf_confirmed),
            "displacement_confirmed": displacement_confirmed,
            "fvg_nearby": bool(fvg_nearby),
            "tested_count": tested_count,
            "fresh": fresh,
            "invalidated": invalidated,
            "invalidation_index_from_end": (
                invalidation_indices[0] - n if invalidation_indices else None
            ),
        }
        item["tradeable"] = bool(
            engulf_confirmed and displacement_confirmed and fvg_nearby
            and not invalidated and fresh
        )
        if item["tradeable"]:
            (bullish_obs if direction == "BULLISH" else bearish_obs).append(item)
        else:
            item["direction"] = direction
            reasons = []
            if not displacement_confirmed: reasons.append("NO_DISPLACEMENT")
            if not fvg_nearby: reasons.append("NO_FVG_FROM_IMPULSE")
            if invalidated: reasons.append("CLOSED_THROUGH_BLOCK")
            if not fresh: reasons.append("STALE_RETESTED_MORE_THAN_TWICE")
            item["rejection_reasons"] = reasons
            rejected.append(item)

    for i in range(start, n - 1):
        impulse_idx = i + 1
        # bullish: last down-close before a bullish state change
        if closes[i] < opens[i] and closes[impulse_idx] > opens[impulse_idx]:
            engulf = lows[impulse_idx] <= lows[i] and closes[impulse_idx] > highs[i]
            if engulf:
                _candidate(
                    i, "BULLISH",
                    any(abs(fs - i) <= 1 for fs in bullish_fvg_starts),
                    engulf,
                )
        # bearish: last up-close before a bearish state change
        if closes[i] > opens[i] and closes[impulse_idx] < opens[impulse_idx]:
            engulf = highs[impulse_idx] >= highs[i] and closes[impulse_idx] < lows[i]
            if engulf:
                _candidate(
                    i, "BEARISH",
                    any(abs(fs - i) <= 1 for fs in bearish_fvg_starts),
                    engulf,
                )

    return {
        "bullish_obs": bullish_obs,
        "bearish_obs": bearish_obs,
        "rejected_candidates": rejected,
    }


def _count_retests(lows, highs, start_idx, n, ob_top, ob_bottom):
    """كم مرة رجع السعر لاختبار منطقة الـOB بعد تشكّلها (لا احتساب
    نظري - عدّ فعلي من البيانات)."""
    count = 0
    inside_previously = False
    for i in range(start_idx, n):
        touching = lows[i] <= ob_top and highs[i] >= ob_bottom
        if touching and not inside_previously:
            count += 1
        inside_previously = touching
    return count


# ══════════════════════════════════════════════════════════════════
#  4) LIQUIDITY SWEEP (يشمل Judas Swing) - سحب حقيقي مقابل اختراق حقيقي
# ══════════════════════════════════════════════════════════════════
#
# تصنيف تشغيلي للبوت لفصل الرفض عن الاستمرار: موقع الإغلاق هو الدليل
# الأساسي هنا، لكنه ليس وحده كافياً لإثبات انعكاس قابل للتداول؛ لذلك
# النماذج اللاحقة تشترط displacement/structure/FVG والتوقيت:
#   Sweep حقيقي (فخ):  الفتيل يخترق المستوى، لكن **إغلاق** الشمعة
#                       يرجع **داخل** الحدود القديمة (فشل الاختراق).
#   Run حقيقي (استمرار): **إغلاق** الشمعة يتجاوز المستوى فعلياً
#                       (التزام حقيقي بالاتجاه، لا فخ).
# Judas Swing (حالة خاصة زمنية من الـ Sweep): يحدث تحديداً بنافذة
# 00:00-05:00 NY (منتصف الليل حتى نهاية Kill Zone لندن)، ويكون **بعكس
# الانحياز اليومي المُقرَّر مسبقاً** - هذا الشرط الزمني+الاتجاهي معاً
# هو ما يميّز Judas Swing عن أي "سحب سيولة" عادي بأي وقت آخر.

def classify_sweep_or_run(data, level_price, level_is_high, check_from_idx=None):
    """
    يفحص هل أحدث اختراق لمستوى سعري معين (level_price) كان "سحب سيولة"
    (فخ، الإغلاق يرجع للداخل) أو "اختراق حقيقي" (استمرار، الإغلاق يتجاوز).

    Args:
        level_is_high: True لو level_price قمة (نفحص اختراقاً للأعلى)،
                        False لو قاع (نفحص اختراقاً للأسفل)
        check_from_idx: من أي شمعة نبدأ البحث (افتراضياً كل البيانات)

    Returns dict: {"found", "classification" (GENUINE_REVERSAL_SWEEP /
                    LIQUIDITY_RUN_CONTINUATION / NOT_YET_TESTED),
                    "candle_index_from_end", "wick_price", "close_price"}
    """
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    start = check_from_idx if check_from_idx is not None else 0

    for i in range(start, n):
        if level_is_high:
            wicked_beyond = highs[i] > level_price
            if wicked_beyond:
                closed_beyond = closes[i] > level_price
                classification = "LIQUIDITY_RUN_CONTINUATION" if closed_beyond else "GENUINE_REVERSAL_SWEEP"
                return {
                    "found": True, "classification": classification,
                    "candle_index_from_end": i - n,
                    "wick_price": round(float(highs[i]), 6),
                    "close_price": round(float(closes[i]), 6),
                }
        else:
            wicked_beyond = lows[i] < level_price
            if wicked_beyond:
                closed_beyond = closes[i] < level_price
                classification = "LIQUIDITY_RUN_CONTINUATION" if closed_beyond else "GENUINE_REVERSAL_SWEEP"
                return {
                    "found": True, "classification": classification,
                    "candle_index_from_end": i - n,
                    "wick_price": round(float(lows[i]), 6),
                    "close_price": round(float(closes[i]), 6),
                }

    return {"found": False, "classification": "NOT_YET_TESTED"}


def detect_judas_swing(data, daily_bias, overnight_range):
    """
    ⚠️ تصحيح جذري مهم (بعد فحص توثيقي إضافي دقيق): النسخة
    الأولى من هذه الدالة طبّقت بالخطأ قاعدة الفوركس الحرفية (لندن
    تسحب Asian Range خلال 00:00-05:00 NY) على تعريف الكريبتو المختلف
    جذرياً - هذا تناقض زمني حقيقي (النطاق الليلي المحسوب بـ
    compute_overnight_range هو بالضبط 00:00-08:30 NY، فلا يمكن أن نفحص سحباً
    له بنفس النافذة الزمنية - تداخل دائري).

    التوثيق الصحيح المؤكّد للكريبتو تحديداً (ictkillzone.com، مصدر متخصص):
    "هذا النطاق الليلي يعمل مثل النطاق الآسيوي لـBTC: افتتاح نيويورك يسحب أحد
    حدوده (اتجاه Judas) قبل التسليم باتجاه الانحياز اليومي" - يعني السحب
    يحصل **عند/بعد افتتاح نيويورك (08:30 NY)**، لا خلال نافذة لندن
    الفوركسية الأصلية (التي لا تنطبق حرفياً لأن النطاق الليلي المحسوب    مختلف أصلاً عن Asian Range الفوركسي).

    شرطان معاً (زمني + اتجاهي):
      1. السحب يحصل خلال نافذة NY_AM_KILLZONE (08:30-11:00 NY)،
         مباشرةً بعد نهاية النطاق الليلي.
      2. اتجاه السحب معاكس للانحياز اليومي المُقرّر مسبقاً.

    Args:
        daily_bias: "BULLISH" أو "BEARISH" (مُقرّر مسبقاً من مرحلة Daily)
        overnight_range: dict من ict_sessions.compute_overnight_range()
                          (يجب أن ينتهي عند 08:30 NY بالضبط - هذا مضمون
                          فعلياً بتصميم compute_overnight_range الحالي).

    Returns dict: {"detected", "swept_side", "classification", "reason"}
    """
    from ict_sessions import classify_session

    if not overnight_range.get("found"):
        return {"detected": False, "reason": "NO_OVERNIGHT_RANGE_DATA"}

    range_high = overnight_range["range_high"]
    range_low = overnight_range["range_low"]

    timestamps = data.get("timestamps", [])
    highs = data.get("highs", [])
    lows = data.get("lows", [])
    closes = data.get("closes", [])

    range_end_ts = overnight_range["range_end_ts"]
    # نفحص فقط الشموع بعد نهاية النطاق الليلي وداخل نافذة
    # NY_AM_KILLZONE تحديداً (التوقيت الصحيح الموثّق للكريبتو - لا
    # ASIAN_MANIPULATION/LONDON_KILLZONE الفوركسي).
    for i, ts in enumerate(timestamps):
        if ts <= range_end_ts:
            continue
        info = classify_session(ts)
        if info["session"] != "NY_AM_KILLZONE":
            continue  # خارج نافذة Judas الزمنية المكيّفة للكريبتو - لا يُحتسب

        if daily_bias == "BULLISH" and lows[i] < range_low:
            closed_below = closes[i] < range_low
            return {
                "detected": True,
                "swept_side": "SELL_SIDE_LOW",
                "classification": "GENUINE_JUDAS_TRAP" if not closed_below else "FAILED_JUDAS_BECAME_REAL_BREAKDOWN",
                "reason": f"Bullish bias but price wicked below overnight low {range_low} at idx {i - len(closes)} during NY AM Killzone (crypto Judas window)",
            }
        if daily_bias == "BEARISH" and highs[i] > range_high:
            closed_above = closes[i] > range_high
            return {
                "detected": True,
                "swept_side": "BUY_SIDE_HIGH",
                "classification": "GENUINE_JUDAS_TRAP" if not closed_above else "FAILED_JUDAS_BECAME_REAL_BREAKOUT",
                "reason": f"Bearish bias but price wicked above overnight high {range_high} at idx {i - len(closes)} during NY AM Killzone (crypto Judas window)",
            }

    return {"detected": False, "reason": "NO_COUNTER_BIAS_SWEEP_DURING_JUDAS_WINDOW"}


# ══════════════════════════════════════════════════════════════════
#  5) MARKET STRUCTURE SHIFT (MSS) - يتطلب سحب سيولة سابق (شرط ICT الصارم)
# ══════════════════════════════════════════════════════════════════
#
# Episode 3 تربط أهمية الـintraday market-structure shift بسحب سيولة
# عند مستوى مرجعي ثم تجاوز swing داخلي. الدالة أدناه لا تدّعي أن كل كسر
# MSS؛ ترجع كل structural close breaks وتُرفق prior_sweep وdisplacement
# ليقرر النموذج/التقرير التسمية السياقية بشفافية.

def detect_mss(data, swing_window=2):
    """
    ⚠️ حل جذري ثانِ (بطلب صريح من المستخدم بعد ملاحظة جوهرية
    مهمة): هذه الدالة **لا تقرر** هل الكسر "MSS حقيقي" أو "مجرد BOS" -
    هذا تصنيف اصطلاحي يحتاج فهم السياق الأكبر (هل هذا الكسر معني فعلاً؟ هل
    يتوافق مع الانحياز الأكبر؟) - ليس معادلة ثابتة. النسخة السابقة كانت
    تُخفي الكسر الهيكلي بالكامل لو ما وجد سحب سابق بالمعيار الصارم - هذا كان
    يحرم الموديل من رؤية الكسر الفعلي أصلاً لو كان السحب السابق غير "مثالي" بالمعنى
    الصارم للكلمة رغم أنه قد يكون مهماً جداً بالسياق الفعلي.

    الحل الجديد: نرجع **كل الكسور الهيكلية الحقيقية** (إغلاق يتجاوز آخر
    سوينغ داخلي - حقيقة رياضية مطلقة)، مرفقةً بكل الحقائق الموضوعية المفيدة
    للتقييم (هل سبقه سحب بالمعيار الصارم؟ هل الإغلاق نفسه اندفاع حقيقي؟)،
    ونترك الحكم النهائي "هل هذا يستاهل تسمية MSS قوية أو BOS عادي" للموديل
    بفهمه الموجّه بالسياق الكامل (راجع الشرح التعليمي الملحق بملف المعرفة).

    Returns dict: {"breaks_found": [ {direction, broken_level,
        broken_level_index_from_end, break_candle_index_from_end,
        displacement_confirmed, prior_sweep: {found, genuine, level,
        candle_index_from_end}} , ... ] } مرتّبة زمنياً
        (الأحدث أولاً)، لا فقط أقرب واحد.
    """
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < swing_window * 2 + 5:
        return {"breaks_found": []}

    # نحسب القمم/القيعان المتأرجحة المحلية البسيطة (نافذة صغيرة - هذا
    # يكفي هنا لأننا نبحث عن "سوينغ داخلي قريب"، لا "قمة استراتيجية
    # كبرى" - ذاك دور detect_significant_swings بـauthenticity_engine.py)
    swing_highs, swing_lows = [], []
    for i in range(swing_window, n - swing_window):
        window_h = highs[i - swing_window:i + swing_window + 1]
        window_l = lows[i - swing_window:i + swing_window + 1]
        if highs[i] == max(window_h):
            swing_highs.append(i)
        if lows[i] == min(window_l):
            swing_lows.append(i)

    if not swing_highs or not swing_lows:
        return {"breaks_found": []}

    disp_info = compute_displacement(data, lookback=max(15, n - swing_window))
    disp_indices = {d["index_from_end"] + n for d in disp_info["displacement_candles"]}

    def _prior_sweep_info(swing_list, idx_in_list, arr, is_high):
        """يفحص هل السوينغ عند swing_list[idx_in_list] هو نفسه ناتج سحب
        حقيقي (بالفتيل) للسوينغ الذي قبله مباشرة، مع إغلاق يرجع فوقه - حقيقة
        موضوعية محضة، لا حكم."""
        if idx_in_list < 1:
            return {"found": False}
        cur_idx = swing_list[idx_in_list]
        prior_idx = swing_list[idx_in_list - 1]
        if is_high:
            wicked = arr[cur_idx] > arr[prior_idx]
            genuine = wicked and closes[cur_idx] < arr[prior_idx]
        else:
            wicked = arr[cur_idx] < arr[prior_idx]
            genuine = wicked and closes[cur_idx] > arr[prior_idx]
        return {
            "found": bool(wicked),
            "genuine_reversal_sweep": bool(genuine),
            "level": round(float(arr[prior_idx]), 6),
            "candle_index_from_end": cur_idx - n,
        }

    breaks_found = []

    # كل كسور صاعدة حقيقية (إغلاق يتجاوز آخر swing high) - لكل swing high
    for hi_pos, sh_idx in enumerate(swing_highs):
        for i in range(sh_idx + 1, n):
            if closes[i] > highs[sh_idx]:
                sweep_info = _prior_sweep_info(swing_lows,
                    max([p for p, sl in enumerate(swing_lows) if sl < sh_idx], default=-1),
                    lows, is_high=False)
                breaks_found.append({
                    "direction": "BULLISH",
                    "broken_level": round(float(highs[sh_idx]), 6),
                    "broken_level_index_from_end": sh_idx - n,
                    "break_candle_index_from_end": i - n,
                    "displacement_confirmed": i in disp_indices,
                    "prior_sweep": sweep_info,
                })
                break  # أول إغلاق يتجاوزه فقط لهذا السوينغ المحدد

    for lo_pos, sl_idx in enumerate(swing_lows):
        for i in range(sl_idx + 1, n):
            if closes[i] < lows[sl_idx]:
                sweep_info = _prior_sweep_info(swing_highs,
                    max([p for p, sh in enumerate(swing_highs) if sh < sl_idx], default=-1),
                    highs, is_high=True)
                breaks_found.append({
                    "direction": "BEARISH",
                    "broken_level": round(float(lows[sl_idx]), 6),
                    "broken_level_index_from_end": sl_idx - n,
                    "break_candle_index_from_end": i - n,
                    "displacement_confirmed": i in disp_indices,
                    "prior_sweep": sweep_info,
                })
                break

    breaks_found.sort(key=lambda b: b["break_candle_index_from_end"])
    return {"breaks_found": breaks_found}


# ══════════════════════════════════════════════════════════════════
#  5.5) MECHANICAL BIAS ANCHOR - حل جذري لتذبذب اتجاه القرار (يوليو 2026)
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (اكتشاف حي حقيقي موثّق): نفس صفقة BTC/USDT
# (نفس end_ts بالضبط، نفس البيانات الخام 100%) أنتجت مرتين متتاليتين
# قرارَين متعاكسين تماماً - BUY_LIMIT (bullish) بمحاولة، SELL_LIMIT
# (bearish) بمحاولة أخرى - رغم أن كل الأدلة الرياضية المُحقنة (structure
# sequence, detect_mss) كانت **نفس الأدلة بالضبط** بكلا المرتين. السبب:
# تلك الأدلة كانت تُحقن فقط كـ"سياق يُستأنس به" - لا شيء كان يُلزم
# النموذج فعلياً بأن ينتج نفس القرار الاتجاهي طالما البيانات لم تتغير.
# بما أن كل مراحل هذا المشروع تستخدم temperature=0.1 (منخفض لكن ليس
# صفراً تماماً) + سباق بين مفتاحين مختلفين (query_json_race) - نفس
# المدخلات يمكن أن تنتج صياغتين لغويتين "معقولتين" لكن متعاكستين
# بالاتجاه العام، خصوصاً حين يكون الهيكل قريباً من نقطة تحوّل حقيقية.
#
# الحل الجذري: نحسب هنا "مرساة انحياز ميكانيكية" - قرار اتجاهي واحد
# حتمي 100% (نفس المدخلات = نفس المخرج دائماً، صفر عشوائية، صفر تفسير
# لغوي) من مصدرين رياضيين مستقلين معاً:
#   1) اتجاه تسلسل القمم/القيعان الأخيرة (HH+HL متتاليين = صاعد،
#      LH+LL متتاليين = هابط - نفس المبدأ المستخدم أصلاً بـ
#      AuthenticityEngine.compute_structure_sequence، مُعاد حسابه هنا
#      بشكل مستقل خفيف الوزن لتفادي استيراد دائري).
#   2) اتجاه آخر كسر هيكلي حقيقي مؤكد فعلياً (من detect_mss أعلاه).
#
# لو اتفق المصدران: مرساة "STRONG" - يُلزَم النموذج بمطابقتها في مرحلة
# Daily تحديداً (الأهم - "القائد") إلا لو استشهد صراحة برقم/مؤشر شمعة
# لحدث انعكاس هيكلي (CHoCH/MSS/BOS) وقع زمنياً *بعد* نقطة المرساة نفسها
# (أي أحدث منها - راجع AuthenticityEngine.audit_bias_anchor_consistency
# للتحقق البرمجي الفعلي من هذا الاستشهاد، لا مجرد تصديق الادعاء).
# لو تعارض المصدران (حالة انتقال/تذبذب حقيقي بالسوق نفسه، لا خطأ):
# مرساة "MIXED/WEAK" - لا إلزام، القرار يبقى حراً بالكامل كالمعتاد.


def compute_mechanical_bias_anchor(data, swing_window=2, lookback=80):
    """
    Returns dict:
        {
            "anchor_direction": "BULLISH"|"BEARISH"|"MIXED"|"UNKNOWN",
            "strength": "STRONG"|"MODERATE"|"WEAK",
            "sequence_direction": "BULLISH"|"BEARISH"|"MIXED"|None,
            "last_confirmed_break_direction": "BULLISH"|"BEARISH"|None,
            "last_confirmed_break_index_from_end": int|None,
            "last_confirmed_break_level": float|None,
            "narrative": str,
        }
    """
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    empty = {
        "anchor_direction": "UNKNOWN", "strength": "WEAK",
        "sequence_direction": None, "last_confirmed_break_direction": None,
        "last_confirmed_break_index_from_end": None,
        "last_confirmed_break_level": None, "narrative": "",
    }
    if n < swing_window * 2 + 5:
        return empty

    start = max(swing_window, n - lookback)
    swing_high_idx, swing_low_idx = [], []
    for i in range(start, n - swing_window):
        if highs[i] == max(highs[i - swing_window:i + swing_window + 1]):
            swing_high_idx.append(i)
        if lows[i] == min(lows[i - swing_window:i + swing_window + 1]):
            swing_low_idx.append(i)

    def _last_leg_direction(idx_list, arr):
        """UP لو آخر نقطتين متتاليتين تصاعدتا، DOWN لو تنازلتا، None لو
        لا يوجد نقطتان كافيتان للمقارنة."""
        if len(idx_list) < 2:
            return None
        a, b = arr[idx_list[-2]], arr[idx_list[-1]]
        if b > a:
            return "UP"
        if b < a:
            return "DOWN"
        return None

    highs_leg = _last_leg_direction(swing_high_idx, highs)   # UP=HH, DOWN=LH
    lows_leg = _last_leg_direction(swing_low_idx, lows)      # UP=HL, DOWN=LL

    if highs_leg == "UP" and lows_leg == "UP":
        sequence_direction = "BULLISH"
    elif highs_leg == "DOWN" and lows_leg == "DOWN":
        sequence_direction = "BEARISH"
    elif highs_leg is None and lows_leg is None:
        sequence_direction = None
    else:
        sequence_direction = "MIXED"

    mss = detect_mss(data, swing_window=swing_window)
    breaks = mss.get("breaks_found", [])
    last_break = breaks[-1] if breaks else None
    last_break_direction = last_break["direction"] if last_break else None
    last_break_idx = last_break["break_candle_index_from_end"] if last_break else None
    last_break_level = last_break["broken_level"] if last_break else None

    agree = None
    if sequence_direction in ("BULLISH", "BEARISH") and last_break_direction:
        agree = (sequence_direction == last_break_direction)

    if sequence_direction in ("BULLISH", "BEARISH") and agree:
        anchor_direction, strength = sequence_direction, "STRONG"
    elif sequence_direction in ("BULLISH", "BEARISH") and agree is None:
        anchor_direction, strength = sequence_direction, "MODERATE"
    elif sequence_direction in ("BULLISH", "BEARISH") and agree is False:
        # المصدران يتعارضان فعلياً (كسر آخر باتجاه مخالف لتسلسل القمم/
        # القيعان الحالي) - هذه غالباً نقطة تحوّل حقيقية بالسوق، لا خطأ
        # حسابي - لا نُلزم بأي اتجاه هنا.
        anchor_direction, strength = "MIXED", "WEAK"
    elif last_break_direction:
        anchor_direction, strength = last_break_direction, "MODERATE"
    else:
        anchor_direction, strength = "MIXED", "WEAK"

    if anchor_direction in ("BULLISH", "BEARISH"):
        narrative = (
            f"MECHANICAL BIAS ANCHOR (deterministic - recomputing on the exact "
            f"same data ALWAYS yields this same result, zero randomness): "
            f"{anchor_direction} ({strength}). Swing sequence (HH/HL vs LH/LL) "
            f"reads {sequence_direction or 'N/A'}; last confirmed structural "
            f"break was {last_break_direction or 'N/A'}"
            + (f" at idx {last_break_idx} (level {last_break_level})" if last_break_idx is not None else "")
            + (
                ". Both sources agree - this is a strong anchor: your direction "
                "output should match it UNLESS you explicitly cite a specific "
                "CHoCH/MSS/BOS reversal event (with its own candle index and "
                "price) that occurred MORE RECENTLY than this anchor's break."
                if strength == "STRONG" else
                ". Only one source available/they partially disagree - treat as "
                "moderate evidence, not an absolute lock."
            )
        )
    else:
        narrative = (
            "MECHANICAL BIAS ANCHOR: MIXED/inconclusive (the swing sequence and "
            "the last confirmed structural break point in different directions, "
            "or too little data) - this itself is a real fact (likely an actual "
            "transition/ranging zone), not an error. No directional lock applies "
            "here; decide using full context as usual, but say so honestly "
            "(consider UNCLEAR if genuinely ambiguous)."
        )

    return {
        "anchor_direction": anchor_direction,
        "strength": strength,
        "sequence_direction": sequence_direction,
        "last_confirmed_break_direction": last_break_direction,
        "last_confirmed_break_index_from_end": last_break_idx,
        "last_confirmed_break_level": last_break_level,
        "narrative": narrative,
    }


# ══════════════════════════════════════════════════════════════════
#  6) PREMIUM / DISCOUNT / OTE - نسب موثّقة حرفياً (لا اجتهاد)
# ══════════════════════════════════════════════════════════════════
#
# موثّق حرفياً (tradingstrategyguides.com "Understanding ICT OTE"،
# ومطابق حرفياً لقسم [SESSION_SPECIFIC...]/8.3 OPTIMAL TRADE ENTRY (OTE)
# بملف المعرفة data/trading_knowledge.txt، أسطر 7310-7370 - المصدر
# الرسمي الوحيد لهذا المشروع): Equilibrium = 50% بالضبط. Premium = فوق
# 50%. Discount = تحت 50%. OTE zone = بين 61.8% و78.6% تراجع (Fibonacci
# قياسي)، **مقاسة من القمة نزولاً للشراء** (الأقرب من القمة = 61.8%،
# الأبعد نحو القاع = 78.6% - انظر المثال الحرفي بالملف: Range_High=
# 101000, Range_Low=98000 → OTE_top=99146 (High - Range*0.618),
# OTE_bottom=98642 (High - Range*0.786)). **ملاحظة منهجية موثّقة
# صراحة**: يُرسم الفيبوناتشي من **جسم الشمعة** (open/close) لا الفتيل.
#
# ⚠️ إصلاح خطأ رياضي حقيقي جذري (يوليو 2026، اكتُشف أثناء بناء
# ict_entry_checklist_engine.py، لم يكن مستخدَماً بعد بأي مسار حي قبل
# هذا الإصلاح - "خطأ ساكن" لم يُسبِّب ضرراً فعلياً بعد لكنه كان سيُسبب
# لو استُخدم): النسخة السابقة من هذه الدالة كانت تحسب
# `ote_low = swing_low + range*0.62` و`ote_high = swing_low + range*0.79`
# - أي تقيس من **القاع صعوداً** لكلا الاتجاهين معاً بشكل ثابت، بصرف
# النظر عن اتجاه التداول (شراء أم بيع). هذا خاطئ رياضياً بمقارنة مباشرة
# مع المثال الحرفي بملف المعرفة نفسه: احتساب تجريبي مباشر (بايثون
# بحت، تحقق رقمي لا نقاشي) أثبت أن الكود القديم يضع نطاق OTE عند
# **99860-100370** (منطقة Premium فعلياً، قرب القمة) بينما المثال
# الحرفي بالوثيقة (لنفس الأرقام Range_High=101000, Range_Low=98000)
# ينص صراحة أن OTE الصحيح هو **98642-99146** (منطقة Discount، قرب
# القاع) - انعكاس كامل للمنطقة الصحيحة. سبب الخطأ: الدالة لم تُميّز
# اتجاه التداول (شراء يحتاج OTE بمنطقة Discount؛ بيع يحتاج OTE بمنطقة
# Premium) - كانت تحسب معادلة واحدة تصلح فقط لأحد الاتجاهين خطأً على
# كليهما دون تمييز.
#
# الحل: معامل جديد `is_bullish_setup` (افتراضي True للتوافق الخلفي،
# لكن **يجب تمريره صراحة الآن** من أي كود مستدعٍ جديد - لا اعتماد على
# الافتراض الصامت) - يحدد أي اتجاه: OTE للشراء يُقاس من القمة نزولاً
# (High - Range×0.618 و High - Range×0.786)؛ OTE للبيع يُقاس من القاع
# صعوداً (Low + Range×0.618 و Low + Range×0.786) - نفس المعادلتين
# المنفصلتين المذكورتين حرفياً بالوثيقة لكلا الاتجاهين.
#
# تحقق رياضي مباشر بعد الإصلاح (مطابقة المثالين الحرفيين بالوثيقة
# 100%): bullish (Range_High=101000, Range_Low=98000) → OTE=
# [98642.0, 99146.0] ✅ مطابق تماماً؛ bearish (Range_High=101000,
# Range_Low=98000) → OTE=[99854.0, 100358.0] ✅ مطابق تماماً.

def compute_premium_discount(swing_low_price, swing_high_price, current_price,
                              is_bullish_setup=True):
    """
    Args:
        is_bullish_setup: True لحساب OTE لإعداد شراء (Discount zone,
            مقاس من القمة نزولاً)؛ False لإعداد بيع (Premium zone,
            مقاس من القاع صعوداً). ⚠️ يجب تمريره صراحة من أي كود جديد -
            الافتراض True موجود فقط للتوافق الخلفي مع استدعاءات قديمة
            محتملة، لا لأنه "الحالة الشائعة".

    Returns dict: {"equilibrium", "zone" (PREMIUM/DISCOUNT/AT_EQUILIBRIUM),
                    "in_ote_zone" (bool), "ote_low", "ote_high",
                    "retracement_pct"}
    """
    if swing_high_price <= swing_low_price:
        return {"error": "INVALID_RANGE: swing_high must be > swing_low"}

    rng = swing_high_price - swing_low_price
    equilibrium = swing_low_price + rng * 0.5

    if is_bullish_setup:
        # مقاس من القمة نزولاً (منطقة Discount - قرب القاع)
        ote_high = swing_high_price - rng * 0.618
        ote_low = swing_high_price - rng * 0.786
    else:
        # مقاس من القاع صعوداً (منطقة Premium - قرب القمة)
        ote_low = swing_low_price + rng * 0.618
        ote_high = swing_low_price + rng * 0.786

    if current_price > equilibrium:
        zone = "PREMIUM"
    elif current_price < equilibrium:
        zone = "DISCOUNT"
    else:
        zone = "AT_EQUILIBRIUM"

    retracement_pct = (swing_high_price - current_price) / rng * 100
    in_ote = ote_low <= current_price <= ote_high

    return {
        "equilibrium": round(equilibrium, 6),
        "zone": zone,
        "in_ote_zone": in_ote,
        "ote_low": round(ote_low, 6),
        "ote_high": round(ote_high, 6),
        "retracement_pct": round(retracement_pct, 1),
    }


# ══════════════════════════════════════════════════════════════════
#  7) STRUCTURAL SL ANCHOR - حل جذري لمشكلة "ستوب على نسبة% لا منطقة"
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (طلب صريح ومباشر من المستخدم، يوليو
# 2026، بعد ملاحظة تكرار خسائر بفارق ضئيل جداً): "الستوب كتير صغير
# مع انو سامحتلك لحد 2.5% وانت عم تحط الستوب عالنسبة، إنما مايكل بيحط
# الستوب اعتماداً عالمناطق وليس عالنسبة المئوية - تحت منطقة كذا كذا".
#
# التشخيص الدقيق (بلا تخمين، فحص مباشر للكود): قبل هذه الدالة، كل
# فحوصات SL بالمشروع (`_min_sl_pct_for`, `_min_sl_buffer_distance`
# بـmulti_pass_analysis.py) كانت تتحقق فقط من **مسافة رقمية مجردة**
# (نسبة% من السعر، أو مضاعف ATR) - لا شيء كان يتحقق أن مسافة SL
# المُقترحة تقع فعلياً **عند حافة منطقة هيكلية حقيقية موجودة بالبيانات**
# (حافة Order Block، سوينغ حقيقي، مستوى سحب سيولة). هذا يعني أن رقماً
# يحقق "الحد الأدنى% + buffer" حسابياً قد لا تكون له أي علاقة فعلية
# بمنطقة حماية هيكلية حقيقية - فيُضرب بأول تذبذب سعري عادي لأنه لم
# يوضع فعلاً "وراء" أي شيء، بل فقط "على مسافة رقمية كافية" من الدخول.
#
# الحل: هذه الدالة تجمع **كل المستويات الهيكلية الحقيقية القريبة**
# (حواف Order Blocks الحقيقية عبر detect_order_blocks، قمم/قيعان
# سوينغ حقيقية، ونقاط سحب سيولة حقيقية) من البيانات الخام - ثم تعطي
# قائمة صريحة بها للموديل ليختار من بينها (لا يخترع رقماً)، وتتحقق
# لاحقاً (audit_sl_is_structural بـauthenticity_engine.py) أن SL
# النهائي المُقترح يطابق فعلياً أحد هذه المستويات (± buffer صغير)،
# لا مجرد نسبة% عامة بلا مرجع مكاني حقيقي.

def find_structural_sl_anchors(data, is_long, lookback=150, max_candidates=6,
                                reference_price=None):
    """
    يجمع كل المستويات الهيكلية الحقيقية القريبة التي تصلح كمرجع SL
    لصفقة بالاتجاه المحدد (is_long)، مرتبة من الأقرب للأبعد عن سعر
    مرجعي (reference_price).

    ⚠️ إصلاح جذري (يوليو 2026، اكتُشف بفحص تحقق مباشر بعد نداء حي):
    النسخة الأولى استخدمت **آخر سعر إغلاق فعلي** (closes[-1]) كمرجع
    وحيد دائماً - هذا خاطئ منطقياً لحالة BUY_LIMIT/SELL_LIMIT (أمر
    معلّق ينتظر السعر يصل لمنطقة أعلى/أدنى من السعر الحالي): مثال حي
    حقيقي، دخول BUY_LIMIT مخطَّط عند 77700 بينما آخر سعر فعلي 76230 -
    البحث عن "مستويات تحت 76230" فوّت تماماً كل المستويات الهيكلية
    الحقيقية الموجودة فعلاً بين 76230 و77700 (وتحت 77700 مباشرة) لأن
    الدالة قارنتها خطأً بـ76230 لا بـ77700 (نقطة الدخول الفعلية التي
    يجب أن يُحمى الستوب خلفها). الحل: معامل `reference_price` جديد
    (اختياري - يفتَرض آخر سعر افتراضياً للتوافق الخلفي)، يجب تمرير
    سعر الدخول المخطَّط فعلياً عند استخدام هذه الدالة لأمر معلّق.
    كذلك: `lookback` الافتراضي رُفع من 60 إلى 150 (يطابق نطاق OB
    الفعلي المستخدم بمكان آخر بالمشروع لنفس الفريم) - نطاق 60 كان
    يفوّت مستويات هيكلية حقيقية موجودة فعلاً بمسافة أبعد قليلاً.

    لصفقة شراء (is_long=True): نبحث عن مستويات **تحت** السعر المرجعي
    (قيعان OB حقيقية، قيعان سوينغ حقيقية، نقاط سحب سيولة سفلية) - أي
    منها يصلح مكاناً لوضع SL (تحته + buffer).
    لصفقة بيع (is_long=False): نفس المنطق معكوساً (قمم فوق السعر المرجعي).

    Returns dict:
        {
            "anchors": [
                {"price", "kind" ("ORDER_BLOCK_EDGE"/"SWING_POINT"/
                 "LIQUIDITY_SWEEP_POINT"), "index_from_end", "detail"}
            ],  # مرتّبة من الأقرب للسعر المرجعي إلى الأبعد
            "nearest_valid_price": float أو None,
        }
    """
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 15:
        return {"anchors": [], "nearest_valid_price": None}

    last_price = float(reference_price) if reference_price else float(closes[-1])
    candidates = []

    # 1) حواف Order Blocks حقيقية (القاع للشراء، القمة للبيع - الحافة
    # التي إذا تجاوزها السعر فعلاً تُبطل صلاحية الـOB كمنطقة حماية)
    obs = detect_order_blocks(data, lookback=lookback)
    ob_list = obs["bullish_obs"] if is_long else obs["bearish_obs"]
    for ob in ob_list:
        edge_price = ob["bottom"] if is_long else ob["top"]
        if (is_long and edge_price < last_price) or (not is_long and edge_price > last_price):
            candidates.append({
                "price": edge_price, "kind": "ORDER_BLOCK_EDGE",
                "index_from_end": ob["index_from_end"],
                "detail": f"{'Bottom' if is_long else 'Top'} of Order Block at idx {ob['index_from_end']}",
            })

    # 2) قمم/قيعان سوينغ حقيقية (نفس معيار detect_mss - سوينغ داخلي
    # حقيقي، لا نتوء عشوائي: أعلى/أدنى من الجارتين على الجهتين)
    swing_window = 2
    for i in range(swing_window, n - swing_window):
        if is_long:
            if lows[i] == min(lows[i - swing_window:i + swing_window + 1]) and lows[i] < last_price:
                candidates.append({
                    "price": float(lows[i]), "kind": "SWING_POINT",
                    "index_from_end": i - n,
                    "detail": f"Genuine swing low at idx {i - n}",
                })
        else:
            if highs[i] == max(highs[i - swing_window:i + swing_window + 1]) and highs[i] > last_price:
                candidates.append({
                    "price": float(highs[i]), "kind": "SWING_POINT",
                    "index_from_end": i - n,
                    "detail": f"Genuine swing high at idx {i - n}",
                })

    # 3) نقاط سحب سيولة حقيقية (GENUINE_REVERSAL_SWEEP - الفتيل الأقصى
    # الذي وقع السحب عنده، وهو بحكم تعريفه أبعد نقطة يجب أن يُحمى SL
    # وراءها لو استند الدخول لهذا السحب تحديداً)
    if is_long:
        swing_lows_idx = [i for i in range(swing_window, n - swing_window)
                           if lows[i] == min(lows[i - swing_window:i + swing_window + 1])]
        for sidx in swing_lows_idx[-8:]:
            res = classify_sweep_or_run(data, float(lows[sidx]), level_is_high=False, check_from_idx=sidx + 1)
            if res.get("found") and res.get("classification") == "GENUINE_REVERSAL_SWEEP":
                wp = res["wick_price"]
                if wp < last_price:
                    candidates.append({
                        "price": wp, "kind": "LIQUIDITY_SWEEP_POINT",
                        "index_from_end": res["candle_index_from_end"],
                        "detail": f"Genuine liquidity sweep wick low at idx {res['candle_index_from_end']}",
                    })
    else:
        swing_highs_idx = [i for i in range(swing_window, n - swing_window)
                            if highs[i] == max(highs[i - swing_window:i + swing_window + 1])]
        for sidx in swing_highs_idx[-8:]:
            res = classify_sweep_or_run(data, float(highs[sidx]), level_is_high=True, check_from_idx=sidx + 1)
            if res.get("found") and res.get("classification") == "GENUINE_REVERSAL_SWEEP":
                wp = res["wick_price"]
                if wp > last_price:
                    candidates.append({
                        "price": wp, "kind": "LIQUIDITY_SWEEP_POINT",
                        "index_from_end": res["candle_index_from_end"],
                        "detail": f"Genuine liquidity sweep wick high at idx {res['candle_index_from_end']}",
                    })

    # ⚠️ حل جذري لحالة "لا مرجع دخول دقيق بعد" (يوليو 2026): عند
    # استدعاء هذه الدالة *قبل* معرفة سعر الدخول الفعلي (تلميح ما قبل
    # أول محاولة - راجع _compute_min_sl_hint)، `reference_price` يكون
    # آخر سعر إغلاق فعلي فقط تقريبياً - لو كان إعداد الصفقة الفعلي
    # BUY_LIMIT/SELL_LIMIT عند منطقة أبعد (فوق/تحت آخر سعر بمسافة
    # كبيرة)، الفلترة الصارمة أعلاه (تحت/فوق reference_price حصراً)
    # قد لا تجد أي شيء رغم وجود مستويات هيكلية حقيقية قريبة من منطقة
    # الدخول الفعلية المتوقعة (فقط أبعد قليلاً من آخر سعر الحالي، لا
    # من نقطة الدخول المستقبلية غير المعروفة بعد). الحل: لو الفلترة
    # الصارمة لم تُنتج شيئاً، نلغي شرط الجهة (تحت/فوق) مؤقتاً ونعرض
    # أقرب المستويات الهيكلية الحقيقية المتاحة أياً كانت جهتها -
    # يبقى هذا **تلميحاً استرشادياً فقط** (الفحص الحاسم الفعلي
    # audit_sl_is_structural يُستدعى لاحقاً بسعر الدخول الحقيقي
    # المُختار فعلياً، فلا خطر من عدم الدقة الكاملة هنا).
    if not candidates:
        all_candidates = []
        obs = detect_order_blocks(data, lookback=lookback)
        for label, ob_list2 in (("bullish", obs["bullish_obs"]), ("bearish", obs["bearish_obs"])):
            for ob in ob_list2:
                edge_price = ob["bottom"] if is_long else ob["top"]
                all_candidates.append({
                    "price": edge_price, "kind": "ORDER_BLOCK_EDGE",
                    "index_from_end": ob["index_from_end"],
                    "detail": f"{'Bottom' if is_long else 'Top'} of a nearby ({label}) Order Block at idx {ob['index_from_end']} (fallback - no strict-side match found)",
                })
        candidates = all_candidates

    # ترتيب من الأقرب للسعر المرجعي (أضيق SL ممكن هيكلياً) للأبعد،
    # وإزالة التكرار شبه التام (فروق سعرية مهملة تحت 0.01% من السعر المرجعي)
    candidates.sort(key=lambda c: abs(c["price"] - last_price))
    dedup = []
    seen_prices = []
    tolerance = last_price * 0.0001
    for c in candidates:
        if any(abs(c["price"] - p) < tolerance for p in seen_prices):
            continue
        dedup.append(c)
        seen_prices.append(c["price"])
        if len(dedup) >= max_candidates:
            break

    return {
        "anchors": dedup,
        "nearest_valid_price": dedup[0]["price"] if dedup else None,
    }


# ══════════════════════════════════════════════════════════════════
#  8) EQUAL HIGHS / EQUAL LOWS (EQH/EQL) - قسم [SWING_DETECTION] 3.4
#     بالدستور - خوارزمية حرفية موثّقة، لا اختراع
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (يوليو 2026، طلب صريح من المستخدم بعد
# نقاش بشأن تحسين TP: "بدك تروح تبحث بحث عميق وتشوف هو شلون بيتصرف
# بهيك حالات كيف بيجيب اقوى تارغت"): بحث ويب مستقل (innercircletrader.
# net، tradingwyckoff.com، arongroups.co، ملف مايكل الأصلي بـScribd)
# أكد بالحرف نفس ما هو موثّق أصلاً بقسم [SWING_DETECTION] 3.4 و14.3
# بملف المعرفة تبعنا: الهدف الأبعد (TP2 / "Draw on Liquidity") ليس
# "أقرب سيولة معاكسة" (كما كان محسوباً سابقاً بـict_entry_checklist_
# engine.py) بل **أبعد مسبح سيولة حقيقي ذو معنى** - وأهم أشكال هذا
# المسبح هي القمم/القيعان المتساوية (EQH/EQL): كلما زاد عدد اللمسات
# المتساوية، زادت "كثافة" السيولة المتجمعة هناك (كل تاجر تجزئة رأى
# القمة المزدوجة/الثلاثية وضع ستوبه هناك = مسبح ضخم تجذبه المؤسسات).
#
# التعريف الحرفي من الدستور (سطر 2047-2144 بالضبط):
#   |A.price - B.price| / A.price < 0.003  (0.3% تفاوت مسموح)
#   مفصولين بمسافة زمنية >= 3×swing_window شمعة (لا نتوءات متتالية
#   بنفس الشمعة تُحتسب "لمستين منفصلتين" خطأً)
#   2 لمسات = Double (احتمال سحب 65-75%)
#   3 لمسات = Triple (احتمال سحب 80-90%)
#   4+ لمسات = Multiple (احتمال سحب 85-95%)

def detect_equal_highs_lows(data, swing_window=2, tolerance_pct=0.003, lookback=150):
    """
    يكتشف كل تجمعات القمم المتساوية (EQH) والقيعان المتساوية (EQL)
    ضمن آخر lookback شمعة، بالضبط حسب خوارزمية قسم [SWING_DETECTION]
    3.4 بالدستور (خطوة 1-4 الحرفية).

    Returns dict:
        {
            "eqh_clusters": [
                {"level": float (متوسط سعر التجمع), "touch_count": int,
                 "touch_indices_from_end": [int,...], "spread_pct": float,
                 "status": "UNSWEPT"/"SWEPT",
                 "probability_label": "DOUBLE"/"TRIPLE"/"MULTIPLE"}
            ],
            "eql_clusters": [نفس البنية للقيعان],
        }
    مرتّبة من الأقرب (للسعر الحالي) للأبعد، ثم من أكثر لمسات للأقل
    عند تساوي المسافة (كلاهما معيار "أهمية أكبر" بحسب الدستور).
    """
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < swing_window * 2 + 5:
        return {"eqh_clusters": [], "eql_clusters": []}

    start = max(swing_window, n - lookback)
    last_price = float(closes[-1])
    min_separation = swing_window * 3

    # قمم/قيعان سوينغ حقيقية (نفس معيار detect_mss - محلي، لا نتوء عشوائي)
    swing_highs_idx = [i for i in range(start, n - swing_window)
                        if highs[i] == max(highs[i - swing_window:i + swing_window + 1])]
    swing_lows_idx = [i for i in range(start, n - swing_window)
                       if lows[i] == min(lows[i - swing_window:i + swing_window + 1])]

    def _cluster(idx_list, price_arr, level_is_high):
        # نبني تجمعات: لكل نقطة غير مُستخدَمة بعد، نجمع كل النقاط
        # اللاحقة (فاصل زمني >= min_separation) ضمن tolerance_pct منها
        used = set()
        clusters = []
        for i, base_idx in enumerate(idx_list):
            if base_idx in used:
                continue
            base_price = float(price_arr[base_idx])
            group = [base_idx]
            for other_idx in idx_list[i + 1:]:
                if other_idx in used:
                    continue
                if abs(other_idx - group[-1]) < min_separation:
                    continue
                if abs(price_arr[other_idx] - base_price) / base_price < tolerance_pct:
                    group.append(other_idx)
            if len(group) >= 2:
                for g in group:
                    used.add(g)
                prices = [float(price_arr[g]) for g in group]
                level = sum(prices) / len(prices)
                spread_pct = round((max(prices) - min(prices)) / level * 100, 4)
                count = len(group)
                label = "DOUBLE" if count == 2 else ("TRIPLE" if count == 3 else "MULTIPLE")
                # حالة السحب: هل أُغلق فعلياً وراء المستوى بعد آخر لمسة؟
                last_touch = max(group)
                if level_is_high:
                    swept = bool(np.any(closes[last_touch + 1:] > level))
                else:
                    swept = bool(np.any(closes[last_touch + 1:] < level))
                clusters.append({
                    "level": round(level, 6),
                    "touch_count": count,
                    "touch_indices_from_end": sorted(g - n for g in group),
                    "spread_pct": spread_pct,
                    "status": "SWEPT" if swept else "UNSWEPT",
                    "probability_label": label,
                })
        return clusters

    eqh_clusters = _cluster(swing_highs_idx, highs, level_is_high=True)
    eql_clusters = _cluster(swing_lows_idx, lows, level_is_high=False)

    # فقط غير المسحوبة بعد لها معنى كهدف مستقبلي (السيولة "استُهلكت"
    # لو انسحبت فعلاً) - لكن نُبقي المسحوبة بالمخرجات لغرض الشفافية،
    # ونرتّب: غير مسحوبة أولاً، ثم الأقرب للسعر الحالي، ثم الأكثر لمسات
    def _sort_key(c):
        return (c["status"] == "SWEPT", abs(c["level"] - last_price), -c["touch_count"])

    eqh_clusters.sort(key=_sort_key)
    eql_clusters.sort(key=_sort_key)

    return {"eqh_clusters": eqh_clusters, "eql_clusters": eql_clusters}


# ══════════════════════════════════════════════════════════════════
#  9) TP1/TP2 — أهداف سيولة فعلية، لا مضاعف R:R مُختلق
# ══════════════════════════════════════════════════════════════════
#
# Episode 2/3/40 من 2022 تعرض استهداف مستويات منطقية وسيولة قريبة،
# أخذ partials، ثم ترك جزء لأهداف لاحقة حسب الخطة. لا ننسب لمايكل قاعدة
# برمجية موحدة تلزم كل صفقة بـ3R. سياسة هذا البوت المعلنة:
#   TP1 = أقرب مستوى صالح غير مسحوب باتجاه الصفقة؛ R:R تُحسب بعده.
#   TP2 = Draw on Liquidity أبعد فقط عند وجود تأكيدين مستقلين على الأقل.
#   لا TP2 قوي = OPEN_TRAILING للجزء المتبقي، بلا رقم مخترع.
# min_rr وسيط اختياري لإدارة المستخدم؛ افتراضياً 0 ولا يغيّر الهدف.
# هذه الدالة لا تغيّر SL.

def find_tp_targets(data, entry_price, sl_price, is_long, lookback=150,
                     htf_data=None, htf_lookback=150, htf_data_sources=None,
                     min_rr=0.0):
    """احسب هدفين منفصلين من بنية السعر من دون ضمان أو R:R مفروضة.

    TP1 هو أقرب مستوى صالح باتجاه الصفقة بعد استبعاد السيولة المسحوبة.
    TP2 هدف HTF أبعد عند توافر تأكيدات كافية، وإلا OPEN_TRAILING.

    ⚠️ حل جذري (يوليو 2026، اكتُشف بتحقق حي مباشر على صفقة #10): النسخة
    الأولى كانت تبحث عن TP2 حصراً بنفس بيانات فريم التنفيذ (data) - هذا
    يخالف منهجية مايكل نفسها الموثّقة حرفياً بالدستور:
      - قسم 12.3 "STEP 2: DAILY ANALYSIS": "DRAW ON LIQUIDITY (DAILY):
        Based on Daily bias... This DoL is the primary target for
        today's trades" - أي الـDoL الاستراتيجي **يُشتق من فريم Daily**،
        لا من فريم التنفيذ (5m/15m) الذي أفقه الزمني قصير جداً (300
        شمعة 5m = ~25 ساعة فقط - لا يمكن أن يحتوي "حلم السيولة البعيد"
        الذي يمتد لأيام/أسابيع كما راهن عليه المتداول البشري فعلياً).
      - قسم 14.3 "TP2 SELECTION - Option B": "A major opposing PD Array
        on Daily or Weekly" - يذكر صراحة فريمات أعلى، لا فريم التنفيذ.
      - تحقق حي فعلي أثبت المشكلة: TP1=2072.5 وTP2=2073.25 (فرق 0.03%
        فقط بينهما!) لأن كلاهما استُخرجا من نفس الأفق الزمني الضيق.

    الحل: TP1 يبقى **حصراً** من `data` (فريم التنفيذ - يحتاج دقة موقع
    الدخول القريب، هذا صحيح كما هو). TP2 الآن يُحسب من **مصدرين معاً**
    (إن توفر htf_data): فريم التنفيذ (كما كان، احتياطي) + فريم أعلى
    (4H/Daily، مُمرَّر صراحة من الخارج بنفس نقطة end_ts - هذا الملف لا
    يجلب بيانات شبكة بنفسه، يبقى حسابياً بحتاً 100%) - نُفضِّل مستويات
    الفريم الأعلى دائماً كـ"الهدف الاستراتيجي الحقيقي" (نفس ترتيب
    الدستور: DoL الحقيقي يُبنى من فريم أعلى من فريم الدخول نفسه).

    Args:
        entry_price, sl_price: أرقام الدخول والستوب **الجاهزة مسبقاً**
            (هذه الدالة لا تحسبهما ولا تغيّرهما - فقط تبني عليهما).
        is_long: True لصفقة شراء.
        htf_data: (اختياري، للتوافق الخلفي) بيانات فريم أعلى واحد -
            يُستخدَم فقط لو htf_data_sources غير مُمرَّر.
        htf_data_sources: (اختياري، الطريقة "الديناميكية المرنة"
            المفضَّلة - يوليو 2026) قائمة [("1d", daily_data),
            ("4h", h4_data)] **مرتّبة حسب الأولوية** (الأعلى أولاً).
            الدالة تفحص كل مصدر بالترتيب وتستخدم **أول مصدر ينتج فعلاً
            مرشح TP2 حقيقي صالح** - هذا يطابق حرفياً قسم 12.3 بالدستور
            ("Daily Draw on Liquidity... the PRIMARY target") مع مرونة
            ديناميكية حقيقية: لو Daily لا يحتوي مستوى مناسب (بيانات
            غير كافية، أو كل المستويات خلف TP1)، ينتقل تلقائياً لـ4H
            بدل أن يفشل بصمت - "يعرف وين بالضبط يحط ويجيب" كل هدف بلا
            تخمين، لأن كل مستوى مُتحقَّق رياضياً من بيانات فعلية فقط.

    Returns dict:
        {
            "tp1": {"price", "kind", "rr", "detail"} أو None إذا لم
                يوجد مستوى حقيقي صالح باتجاه الصفقة،
            "tp2": {"price", "kind", "touch_count", "rr", "detail",
                "source": "ENTRY_TF"/"HTF"} أو {"mode": "OPEN_TRAILING",
                "detail": ...} لو لا يوجد مستوى بعيد واضح ذو معنى،
            "sl_distance": float (للمرجعية فقط، لم تُعدَّل),
        }
    """
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    n = len(highs)
    sl_dist = abs(entry_price - sl_price)
    if sl_dist <= 0 or n < 15:
        return {"tp1": None, "tp2": {"mode": "OPEN_TRAILING", "detail": "insufficient data"},
                "sl_distance": sl_dist}

    def _collect_candidates(src_data, src_lookback, source_label):
        """يجمع كل مرشحي المستوى الهيكلي المعاكس (EQH/EQL + سوينغ + OB
        معاكس) من مصدر بيانات معين (فريم تنفيذ أو فريم أعلى)، موسومة
        بمصدرها للشفافية الكاملة."""
        src_highs = np.asarray(src_data.get("highs", []), dtype=float)
        src_lows = np.asarray(src_data.get("lows", []), dtype=float)
        src_n = len(src_highs)
        if src_n < 15:
            return []
        out = []
        eq_src = detect_equal_highs_lows(src_data, lookback=src_lookback)
        clusters_src = eq_src["eqh_clusters"] if is_long else eq_src["eql_clusters"]
        for c in clusters_src:
            if c["status"] == "SWEPT":
                continue
            if (is_long and c["level"] > entry_price) or (not is_long and c["level"] < entry_price):
                out.append({
                    "price": c["level"], "kind": f"EQ{'H' if is_long else 'L'}_{c['probability_label']}",
                    "touch_count": c["touch_count"], "source": source_label,
                    "detail": f"[{source_label}] {c['probability_label']} liquidity pool ({c['touch_count']} touches, {c['status']})",
                })
        swing_window_local = 2
        if is_long:
            swing_idx = [i for i in range(swing_window_local, src_n - swing_window_local)
                         if src_highs[i] == max(src_highs[i - swing_window_local:i + swing_window_local + 1])
                         and src_highs[i] > entry_price]
            for i in swing_idx:
                level = float(src_highs[i])
                # An old high already exceeded by a later candle no longer
                # represents untouched buy-side liquidity.  The old code kept
                # it and could select a stale/distant target.
                already_swept = any(src_highs[j] > level for j in range(i + 1, src_n))
                if already_swept:
                    continue
                out.append({"price": level, "kind": "UNSWEPT_SWING_HIGH", "touch_count": 1,
                            "source": source_label, "swing_index_from_end": i - src_n,
                            "detail": f"[{source_label}] Unswept swing high at idx {i - src_n}"})
        else:
            swing_idx = [i for i in range(swing_window_local, src_n - swing_window_local)
                         if src_lows[i] == min(src_lows[i - swing_window_local:i + swing_window_local + 1])
                         and src_lows[i] < entry_price]
            for i in swing_idx:
                level = float(src_lows[i])
                already_swept = any(src_lows[j] < level for j in range(i + 1, src_n))
                if already_swept:
                    continue
                out.append({"price": level, "kind": "UNSWEPT_SWING_LOW", "touch_count": 1,
                            "source": source_label, "swing_index_from_end": i - src_n,
                            "detail": f"[{source_label}] Unswept swing low at idx {i - src_n}"})
        ob_src = detect_order_blocks(src_data, lookback=src_lookback)
        opposing_obs_src = ob_src["bearish_obs"] if is_long else ob_src["bullish_obs"]
        for ob in opposing_obs_src:
            edge = ob["bottom"] if is_long else ob["top"]
            if (is_long and edge > entry_price) or (not is_long and edge < entry_price):
                out.append({"price": edge, "kind": "OPPOSING_OB_EDGE", "touch_count": 1,
                            "source": source_label,
                            "detail": f"[{source_label}] Opposing Order Block edge at idx {ob['index_from_end']}"})
        return out

    # ── TP1: SCAN مستويات معاكسة **حصراً من فريم التنفيذ** (خطوة 1-4
    # قسم 14.2 بالضبط - يحتاج دقة قريبة من نقطة الدخول، هذا صحيح
    # كما هو، لا تغيير هنا) ──
    candidates = _collect_candidates(data, lookback, "ENTRY_TF")

    for c in candidates:
        c["distance"] = abs(c["price"] - entry_price)
        c["rr"] = round(c["distance"] / sl_dist, 3)

    # نضع TP1 قبل المستوى بقليل كسياسة تنفيذية قابلة للضبط (0.15%)، ثم
    # نحسب R:R على السعر الفعلي لا على المستوى الخام. لا نستخدم النسبة
    # لتوسيع الهدف؛ min_rr إن حدده المستخدم يفلتر الخطة فقط.
    def _tp1_price_for(level_price):
        offset = level_price * 0.0015
        return (level_price - offset) if is_long else (level_price + offset)

    for c in candidates:
        c["tp1_price_after_offset"] = _tp1_price_for(c["price"])
        c["rr_after_offset"] = round(abs(c["tp1_price_after_offset"] - entry_price) / sl_dist, 3)

    # ⚠️ إصلاح جذري إضافي (يوليو 2026، اكتُشف بنداء حي مباشر - صفقة
    # BUY_LIMIT حقيقية حيث offset الـ0.15% (2.587 نقطة) كان أكبر من
    # المسافة الأصلية بين المستوى ونقطة الدخول (0.2 نقطة فقط)، فقفز
    # الـTP1 المُعدَّل *فوق* نقطة الدخول بالكامل ونزل *تحتها* - نتج
    # tp=1722.06 لصفقة شراء دخولها 1724.45، أي هدف بالاتجاه المعاكس
    # تماماً لصفقة الشراء! هذا خطأ رياضي خطير: أي مستوى مرشَّح أقرب من
    # نقطة الدخول من مسافة الـoffset نفسها (0.15% من سعره) يجب أن
    # يُستبعد بالكامل - لا "يُصحَّح" لأنه أصلاً قريب جداً ليكون هدفاً
    # حقيقياً ذا معنى، بغض النظر عن قيمة R:R المحسوبة رياضياً (R:R
    # عالٍ هنا كان نتيجة انقلاب الاتجاه، لا ربح حقيقي).
    for c in candidates:
        direction_preserved = (
            (c["tp1_price_after_offset"] > entry_price) if is_long
            else (c["tp1_price_after_offset"] < entry_price)
        )
        c["direction_preserved_after_offset"] = direction_preserved

    # ICT targets are a draw on real liquidity, not a fabricated multiple of
    # the stop.  ``min_rr`` is an optional user risk-policy filter; by default
    # it is informational (0.0), so we choose the nearest genuine untouched
    # structural level and report the actual R:R honestly.  This removes the
    # old rigid >=3 rule that skipped valid nearby liquidity or cherry-picked
    # an unrealistically distant target merely to satisfy a ratio.
    try:
        min_rr_value = max(0.0, float(min_rr))
    except (TypeError, ValueError):
        min_rr_value = 0.0
    valid_tp1 = sorted(
        [c for c in candidates
         if c["rr_after_offset"] >= min_rr_value and c["direction_preserved_after_offset"]],
        key=lambda c: c["distance"],
    )
    tp1 = None
    if valid_tp1:
        best = valid_tp1[0]
        tp1_price = best["tp1_price_after_offset"]
        tp1 = {
            "price": round(tp1_price, 6),
            "level_price": best["price"],
            "kind": best["kind"],
            "rr": round(abs(tp1_price - entry_price) / sl_dist, 2),
            "detail": f"{best['detail']} (placed 0.15% before the level per section 14.2 step 4)",
        }

    # ── TP2: Draw on Liquidity - الهدف الاستراتيجي البعيد (قسم 12.3 +
    # 14.3): يُفضَّل مستوى من **فريم أعلى** لأنه يمثّل "الحلم الحقيقي"
    # الذي يمتد لأيام/أسابيع، لا تفصيلاً صغيراً بنفس أفق فريم التنفيذ
    # الزمني الضيق. ⚠️ حل "مرن ديناميكي" (يوليو 2026، طلب صريح): بدل
    # مصدر HTF واحد ثابت، نفحص كل المصادر المُمرَّرة (htf_data_sources)
    # **بترتيب الأولوية المُعطى** (عادة Daily أولاً ثم 4H) ونستخدم أول
    # مصدر ينتج فعلاً مرشحاً حقيقياً صالحاً - لا نتجمّد على مصدر واحد
    # فارغ، ولا نخترع مستوى وهمياً لو كل المصادر فشلت (fallback نهائي
    # صريح لفريم التنفيذ نفسه، وإلا OPEN_TRAILING صادق).
    #
    # ⚠️ حل جذري إضافي (يوليو 2026، طلب صريح من المستخدم: "مو عطول
    # لازم ينحط التارغت التاني - نحن منحلل على هدف واحد، ولما نشوف
    # تأكيدات قوية تشير لهدف تاني منحطه وقتها"): هذا يطابق حرفياً
    # RULE 7 بالدستور ("A single factor is never sufficient... Three
    # independent confluences is the absolute minimum") وقسم 14.3
    # Option C ("leave TP2 as trailing" إن لم يوجد دليل كافٍ). النسخة
    # السابقة كانت تقبل **أي** مستوى واحد (حتى لمسة سوينغ وحيدة من
    # فريم التنفيذ) كـTP2 نهائي بلا أي عتبة - هذا يخالف فلسفة "لا قرار
    # على عامل واحد" المطبَّقة بكل مكان آخر بهذا المشروع.
    #
    # الحل: نبني قائمة تأكيدات موضوعية قابلة للتحقق رياضياً لكل مرشح
    # TP2 (لا انطباع)، ونطلب حداً أدنى **2 تأكيدين مستقلين** قبل تثبيت
    # TP2 كهدف نهائي - وإلا يبقى TP2 مفتوحاً (OPEN_TRAILING، القسم 50%
    # الباقي يُدار بـStructure Trail فقط، بلا رقم مزعوم).
    MIN_TP2_CONFLUENCES = 2

    def _score_tp2_confluences(candidate, source_label):
        """
        يبني قائمة تأكيدات حقيقية (كل عنصر تحقّق رياضي مباشر من
        البيانات، لا افتراض) تدعم اعتبار هذا المرشح "هدفاً استراتيجياً
        موثوقاً بما يكفي"، لا مجرد أول مستوى بعيد وُجد:

          C1 (EQ_CLUSTER): مسبح سيولة حقيقي بلمستين+ (EQH/EQL) - كل
              لمسة إضافية = تأكيد مستقل حقيقي أن تجار آخرين وضعوا
              ستوباتهم هناك (قسم [SWING_DETECTION] 3.4: "probability
              of sweep 65-75% for Double").
          C2 (TRIPLE_PLUS_TOUCH): 3+ لمسات (وليس فقط 2) - يرفع احتمال
              الأهمية أكثر (قسم 3.4: "80-90% probability" فأكثر).
          C3 (HIGHER_TIMEFRAME_ORIGIN): المستوى من فريم أعلى فعلياً
              (Daily/4H/Weekly لا فريم التنفيذ) - قسم 12.3 بالدستور
              يذكر صراحة أن الـDoL الاستراتيجي الحقيقي يُبنى من هناك.
          C4 (INSTITUTIONAL_ZONE): المستوى نفسه حافة Order Block
              معاكسة حقيقية (لا مجرد نقطة سوينغ عابرة) - دليل نشاط
              مؤسساتي موثّق (لا فقط سيولة تجزئة).

        Returns: (confluence_count: int, confluence_list: [str])
        """
        confluences = []
        touch_count = candidate.get("touch_count", 1)
        if touch_count >= 2:
            confluences.append(
                f"EQ_CLUSTER: genuine {touch_count}-touch liquidity pool (section 3.4)"
            )
        if touch_count >= 3:
            confluences.append(
                f"TRIPLE_PLUS_TOUCH: {touch_count} touches raises sweep probability to 80-90%+ (section 3.4)"
            )
        if source_label.upper() in ("DAILY", "4H", "WEEKLY"):
            confluences.append(
                f"HIGHER_TIMEFRAME_ORIGIN: level sourced from {source_label} (strategic DoL per section 12.3)"
            )
        if candidate.get("kind") == "OPPOSING_OB_EDGE":
            confluences.append("INSTITUTIONAL_ZONE: level is an opposing Order Block edge, not just a swing point")
        return len(confluences), confluences

    def _pick_tp2(pool, min_distance_from_tp1, source_label):
        """يختار أفضل TP2 من مجموعة مرشحين - **فقط** لو حقّق الحد
        الأدنى من التأكيدات المستقلة (MIN_TP2_CONFLUENCES). يُفضَّل
        مسبح سيولة حقيقي (touch_count>=2، Option A بالدستور)، وإلا
        أبعد مستوى حقيقي متاح (Option B) - لكن كلاهما يمران أولاً عبر
        نفس عتبة التأكيدات، لا استثناء لأي منهما."""
        candidates_beyond_tp1 = [c for c in pool if c["distance"] > min_distance_from_tp1]
        if not candidates_beyond_tp1:
            return None, None, 0, []

        scored = []
        for c in candidates_beyond_tp1:
            count, conf_list = _score_tp2_confluences(c, source_label)
            scored.append((c, count, conf_list))

        qualifying = [s for s in scored if s[1] >= MIN_TP2_CONFLUENCES]
        if not qualifying:
            return None, None, 0, []

        # ⚠️ إصلاح خطأ منطقي حقيقي مُكتشف بفحص مباشر (تحقق حي على صفقة
        # #10): الترتيب الأول (-count, -distance) كان يفضّل "الأبعد
        # مطلقاً" عند تساوي عدد التأكيدات - أنتج فعلياً اختيار حافة OB
        # قديمة جداً (شهرين+، بعيدة بشكل غير واقعي عملياً، R:R=300+)
        # بدل مسبح سيولة حقيقي (EQH مزدوج) أقرب وأكثر منطقية موجود
        # بنفس المجموعة. الدستور (قسم 14.3) يفضّل Option A (EQ cluster
        # - مسبح سيولة حقيقي بلمسات متعددة) على Option B (أبعد مستوى
        # عام) **بحكم نوعه لا بحكم مسافته** - EQ cluster دليل تجمّع
        # سيولة تجزئة حقيقي موثّق، بينما "الأبعد" وحدها ليست ميزة.
        # الترتيب الصحيح: أولاً هل هو EQ cluster (Option A) أم لا،
        # ثم عدد التأكيدات، ثم المسافة فقط كفاصل أخير بين المتعادلين.
        def _sort_key(s):
            cand, count, _ = s
            is_eq_cluster = cand.get("touch_count", 1) >= 2
            return (0 if is_eq_cluster else 1, -count, -cand["distance"])

        qualifying.sort(key=_sort_key)
        best_candidate, best_count, best_confs = qualifying[0]
        option_label = "Option A - EQ cluster" if best_candidate.get("touch_count", 1) >= 2 else "Option B - farthest genuine level"
        return best_candidate, option_label, best_count, best_confs

    min_dist_from_tp1 = abs(tp1["level_price"] - entry_price) if tp1 else 0

    # بناء قائمة مصادر HTF مرتّبة (الأولوية الديناميكية): إما
    # htf_data_sources صراحة، أو htf_data المفرد (توافق خلفي) كمصدر وحيد
    ordered_sources = list(htf_data_sources) if htf_data_sources else (
        [("HTF", htf_data)] if (htf_data and htf_data.get("closes")) else []
    )

    tp2 = None
    tried_sources_log = []
    for source_label, src_data in ordered_sources:
        if not src_data or not src_data.get("closes"):
            tried_sources_log.append(f"{source_label}(no data available)")
            continue
        src_candidates = _collect_candidates(src_data, htf_lookback, source_label.upper())
        for c in src_candidates:
            c["distance"] = abs(c["price"] - entry_price)
            c["rr"] = round(c["distance"] / sl_dist, 3)
        chosen, option_label, conf_count, conf_list = _pick_tp2(src_candidates, min_dist_from_tp1, source_label)
        tried_sources_log.append(
            f"{source_label}({'found, ' + str(conf_count) + ' confluences' if chosen else 'no candidate met the ' + str(MIN_TP2_CONFLUENCES) + '-confluence minimum'})"
        )
        if chosen:
            tp2 = {
                "price": chosen["price"], "kind": chosen["kind"],
                "touch_count": chosen["touch_count"], "rr": chosen["rr"],
                "source": source_label.upper(),
                "confluence_count": conf_count,
                "confluences": conf_list,
                "detail": (
                    f"Draw on Liquidity ({option_label}, {source_label} timeframe per "
                    f"section 12.3/14.3, {conf_count} confluences confirmed: {'; '.join(conf_list)} - "
                    f"dynamic priority scan tried: {', '.join(tried_sources_log)}): "
                    f"{chosen['detail']}"
                ),
                "mode": "TARGET",
            }
            break  # أول مصدر ناجح بترتيب الأولوية - لا نستمر لمصادر أضعف

    # fallback أخير: فريم التنفيذ نفسه، فقط لو كل مصادر HTF فشلت (ولا
    # يزال يخضع لنفس عتبة التأكيدات - لا استثناء لمجرد أنه fallback)
    if tp2 is None and candidates:
        chosen, option_label, conf_count, conf_list = _pick_tp2(candidates, min_dist_from_tp1, "ENTRY_TF")
        if chosen:
            tp2 = {
                "price": chosen["price"], "kind": chosen["kind"],
                "touch_count": chosen["touch_count"], "rr": chosen["rr"],
                "source": "ENTRY_TF",
                "confluence_count": conf_count,
                "confluences": conf_list,
                "detail": (
                    f"Draw on Liquidity ({option_label}, entry-TF fallback, {conf_count} confluences "
                    f"confirmed: {'; '.join(conf_list)} - no higher-timeframe candidate met the "
                    f"{MIN_TP2_CONFLUENCES}-confluence minimum after trying: "
                    f"{', '.join(tried_sources_log) or 'none provided'}): {chosen['detail']}"
                ),
                "mode": "TARGET",
            }
    if tp2 is None:
        tp2 = {
            "mode": "OPEN_TRAILING",
            "confluence_count": 0,
            "confluences": [],
            "detail": (
                f"No candidate level (entry timeframe or any higher timeframe tried: "
                f"{', '.join(tried_sources_log) or 'none provided'}) met the minimum "
                f"{MIN_TP2_CONFLUENCES} independent confluences required to lock in a fixed "
                f"TP2 (section [RISK_ENGINE] RULE 7: 'a single factor is never sufficient'; "
                f"section 14.3 Option C) - per Michael's methodology, the runner 50% stays "
                f"open with a trailing stop instead of a weakly-supported numeric target. "
                f"This is the DEFAULT and expected outcome for most trades - a fixed TP2 is "
                f"only set when strong corroborating evidence genuinely exists."
            ),
        }

    return {"tp1": tp1, "tp2": tp2, "sl_distance": sl_dist}





# ══════════════════════════════════════════════════════════════════
#  10) محاكاة إدارة الصفقة الحقيقية (TP1 50% + BE + Structure Trail)
#      قسم [RISK_ENGINE] RULE 6/8 + [TRADE_MANAGEMENT] 14.4/14.5
#      بالدستور - محاكاة رياضية بحتة على بيانات تاريخية فعلية فقط
#      (لا تنفيذ حي - هذا لغرض الباك تيست/المقارنة الصادقة فقط)
# ══════════════════════════════════════════════════════════════════

def simulate_managed_trade_outcome(candles, entry_price, sl_price, tp1_price, tp2_info,
                                    is_short, entry_idx=0, swing_window=2):
    """
    يحاكي **بالضبط** ما يفعله مايكل حسب الدستور (RULE 6 + 14.4 + 14.5)
    شمعة بشمعة على بيانات تاريخية حقيقية فعلية بعد الدخول:

      المرحلة 1 (قبل TP1): SL ثابت 100% في مكانه الأصلي (RULE 6: "Before
        TP1: SL stays at its ORIGINAL position. Do not move it. No
        exceptions."). لو SL انضرب هنا → LOSS كاملة (100% من المركز).
      المرحلة 2 (TP1 ينضرب): 50% من المركز يُقفَل عند tp1_price (ربح
        مضمون)، SL للـ50% الباقي ينتقل فوراً لسعر الدخول بالضبط
        (breakeven - لا نسبة، لا تقريب).
      المرحلة 3 (بعد TP1، الباقي 50%): إن وُجد tp2 حقيقي (tp2_info
        mode=TARGET) نراقبه؛ وبالتوازي نطبّق STRUCTURE TRAIL (Method 1
        المفضّل بالدستور 14.5): كل ما تشكّل قاع/قمة سوينغ جديد مؤكد
        (2 شمعة تأكيد، swing_window=2) بنفس اتجاه الصفقة، ينتقل الستوب
        المتحرك خلفه (تحت HL الجديد لصفقة شراء / فوق LH الجديد لصفقة
        بيع) - **لا يتراجع أبداً للخلف** (RULE 6: "It can NEVER: Move
        further from entry").

    Args:
        candles: dict {"highs","lows","closes","timestamps"} لشموع
            *لاحقة* لحظة النشر فعلياً (نفس مصدر _fetch_okx_forward_window
            بـhuman_trades_backtest.py - بيانات حقيقية موثّقة فقط).
        entry_price, sl_price, tp1_price: أرقام الخطة الأصلية الجاهزة.
        tp2_info: مخرجات find_tp_targets()["tp2"] بالضبط.
        is_short: True لصفقة بيع.
        entry_idx: فهرس الشمعة التي حدث عندها الدخول فعلياً (0 لو غير
            معروف - سيُكتشف تلقائياً من أول لمسة لـentry_price).

    Returns dict:
        {
            "classification": "WIN_FULL"/"WIN_TRAIL"/"WIN_PARTIAL"/
                "BREAKEVEN"/"LOSS"/"ENTRY_NEVER_HIT"/"NEITHER_HIT_WITHIN_WINDOW",
            "tp1_hit": bool, "tp1_hit_idx"/"tp1_hit_time",
            "tp2_hit": bool, "final_exit_price", "final_exit_reason",
            "final_exit_idx"/"final_exit_time",
            "pnl_pct_blended": float (50%×TP1_pnl% + 50%×final_pnl%,
                نفس معادلة الدستور سطر 662/677/691 بالضبط),
            "trail_history": [{"idx_from_start","new_sl"}, ...] (للشفافية),
        }
    """
    highs = candles.get("highs", [])
    lows = candles.get("lows", [])
    closes = candles.get("closes", [])
    timestamps = candles.get("timestamps", [])
    n = len(closes)
    if n == 0:
        return {"classification": "NO_DATA"}

    # ── إيجاد أول شمعة تلمس منطقة الدخول فعلياً ──
    found_entry_idx = None
    for i in range(n):
        if lows[i] <= entry_price <= highs[i]:
            found_entry_idx = i
            break
    if found_entry_idx is None:
        return {"classification": "ENTRY_NEVER_HIT", "pnl_pct_blended": 0.0}

    tp1_hit = False
    tp1_hit_idx = None
    current_sl = sl_price  # المرحلة 1: ثابت تماماً حتى TP1 (RULE 6)
    trail_history = []
    swing_highs_seen = []  # (idx, price) للـHL/LH tracking بعد TP1
    swing_lows_seen = []

    final_exit_price = None
    final_exit_reason = None
    final_exit_idx = None

    def _check_after_entry_on_entry_candle(i, entry_p, is_short_flag):
        """
        ⚠️ حل جذري (يوليو 2026، اكتُشف بتحقق حي مباشر بفريم 1 دقيقة على
        صفقة #10): بشمعة الدخول نفسها (i == found_entry_idx تحديداً)،
        فحص "هل SL/TP1 انضربا؟" على **كامل مدى الشمعة** خطأ منطقي فعلي
        إن كان القاع/القمة المسبِّب وقع **قبل** لحظة الدخول الفعلية ضمن
        نفس الشمعة (مثال حقيقي مُكتشف: شمعة افتتحت 2054.3، قاعها
        2054.3 أيضاً (=الافتتاح)، ثم صعدت لـ2060 فأعلى - الستوب
        2055.24 "لمسته" الشمعة نظرياً بقاعها، لكن ذلك القاع كان **عند
        الافتتاح، قبل أن يدخل السعر أصلاً منطقة الدخول 2059.35** -
        الستوب فيزيائياً لا يمكن أن ينضرب قبل فتح الصفقة).

        الحل: نستخدم تقريب OHLC القياسي لمسار الشمعة الداخلي (نفس
        الاصطلاح المستخدم بأدوات الباك تيست الاحترافية عند غياب بيانات
        تيك دقيقة): إن كانت الشمعة صاعدة (close>=open) → المسار
        الافتراضي open→low→high→close (السعر يجرّب الهبوط أولاً)؛ إن
        هابطة → open→high→low→close. نحدد أين تقع نقطة الدخول على هذا
        المسار، ونفحص SL/TP1 **فقط على الجزء اللاحق منه**.

        Returns: (hit_sl: bool, hit_tp1: bool) - أيهما وقع فعلياً بعد
        لحظة الدخول ضمن هذا التقريب.
        """
        o, c, lo_, hi_ = opens[i], closes[i], lows[i], highs[i]
        is_bullish_candle = c >= o
        path = [o, lo_, hi_, c] if is_bullish_candle else [o, hi_, lo_, c]

        # نجد أول نقطة بالمسار يلمس فيها السعر منطقة الدخول (بين
        # segmentين متتاليين) - نفحص كل segment بالترتيب
        entry_seg_idx = None
        for seg_i in range(len(path) - 1):
            seg_a, seg_b = path[seg_i], path[seg_i + 1]
            lo_seg, hi_seg = min(seg_a, seg_b), max(seg_a, seg_b)
            if lo_seg <= entry_p <= hi_seg:
                entry_seg_idx = seg_i
                break
        if entry_seg_idx is None:
            # لم نجد الدخول على المسار المقرَّب (نادر جداً - فروق تقريب)
            # - احتياط آمن: نفحص الشمعة كاملة كما كانت (السلوك القديم)
            hit_sl_full = (hi_ >= current_sl) if is_short_flag else (lo_ <= current_sl)
            hit_tp1_full = (tp1_price is not None) and ((lo_ <= tp1_price) if is_short_flag else (hi_ >= tp1_price))
            return hit_sl_full, hit_tp1_full

        # الجزء اللاحق من المسار (بعد لحظة الدخول): من entry_p حتى
        # نهاية المسار، عبر بقية الـsegments
        remaining_points = [entry_p] + path[entry_seg_idx + 1:]
        remaining_lo = min(remaining_points)
        remaining_hi = max(remaining_points)
        hit_sl_after = (remaining_hi >= current_sl) if is_short_flag else (remaining_lo <= current_sl)
        hit_tp1_after = (tp1_price is not None) and (
            (remaining_lo <= tp1_price) if is_short_flag else (remaining_hi >= tp1_price)
        )
        return hit_sl_after, hit_tp1_after

    opens = candles.get("opens", closes)  # fallback: لو opens غير متوفرة، نستخدم closes (تقريب متحفظ)

    for i in range(found_entry_idx, n):
        lo, hi = lows[i], highs[i]

        if not tp1_hit:
            # ── المرحلة 1: قبل TP1 - SL ثابت، لا حركة إطلاقاً ──
            if i == found_entry_idx:
                hit_sl, hit_tp1 = _check_after_entry_on_entry_candle(i, entry_price, is_short)
            else:
                hit_sl = (hi >= current_sl) if is_short else (lo <= current_sl)
                hit_tp1 = (tp1_price is not None) and ((lo <= tp1_price) if is_short else (hi >= tp1_price))
            if hit_sl and hit_tp1:
                # نفس الشمعة - نتبع سياسة compute_trade_outcome المحافظة
                # (نفترض أسوأ حالة: SL أولاً) للاتساق مع بقية المشروع
                final_exit_price, final_exit_reason, final_exit_idx = sl_price, "SL_HIT_BEFORE_TP1", i
                break
            if hit_sl:
                final_exit_price, final_exit_reason, final_exit_idx = sl_price, "SL_HIT_BEFORE_TP1", i
                break
            if hit_tp1:
                tp1_hit = True

                tp1_hit_idx = i
                current_sl = entry_price  # المرحلة 2: فوري، بالضبط سعر الدخول (breakeven)
                trail_history.append({"idx_from_start": i, "new_sl": current_sl, "reason": "TP1_HIT_BREAKEVEN"})
                # لا break - نكمل بنفس الشمعة لفحص المرحلة 3 إن انطبقت لاحقاً
                continue
        else:
            # ── المرحلة 3: بعد TP1 - Structure Trail (Method 1، القسم 14.5) ──
            # تحديث تتبّع سوينغ جديد (تأكيد بشمعتين، swing_window=2)
            if i >= swing_window and i < n - swing_window:
                window_h = highs[max(0, i - swing_window):i + swing_window + 1]
                window_l = lows[max(0, i - swing_window):i + swing_window + 1]
                if not is_short and lo == min(window_l) and len(window_l) == 2 * swing_window + 1:
                    swing_lows_seen.append((i, lo))
                if is_short and hi == max(window_h) and len(window_h) == 2 * swing_window + 1:
                    swing_highs_seen.append((i, hi))

            # نحرّك الستوب خلف آخر سوينغ مؤكد (لا يتراجع للخلف أبداً - RULE 6)
            if not is_short and swing_lows_seen:
                candidate_sl = swing_lows_seen[-1][1]
                if candidate_sl > current_sl:
                    current_sl = candidate_sl
                    trail_history.append({"idx_from_start": i, "new_sl": current_sl, "reason": "STRUCTURE_TRAIL_HL"})
            if is_short and swing_highs_seen:
                candidate_sl = swing_highs_seen[-1][1]
                if candidate_sl < current_sl:
                    current_sl = candidate_sl
                    trail_history.append({"idx_from_start": i, "new_sl": current_sl, "reason": "STRUCTURE_TRAIL_LH"})

            hit_trail = (hi >= current_sl) if is_short else (lo <= current_sl)
            hit_tp2 = (tp2_info.get("mode") == "TARGET") and (
                (lo <= tp2_info["price"]) if is_short else (hi >= tp2_info["price"])
            )
            if hit_trail and hit_tp2:
                final_exit_price, final_exit_reason, final_exit_idx = tp2_info["price"], "TP2_HIT", i
                break
            if hit_tp2:
                final_exit_price, final_exit_reason, final_exit_idx = tp2_info["price"], "TP2_HIT", i
                break
            if hit_trail:
                final_exit_price, final_exit_reason, final_exit_idx = current_sl, "TRAILING_STOP_HIT", i
                break

    if final_exit_price is None:
        # لم يُحسم بعد خلال النافذة المتاحة
        final_exit_price = closes[-1]
        final_exit_reason = "NEITHER_HIT_WITHIN_WINDOW"
        final_exit_idx = n - 1

    def _pnl_pct(exit_p):
        return ((exit_p - entry_price) / entry_price * 100 if not is_short
                else (entry_price - exit_p) / entry_price * 100)

    # ── تصنيف حسب قسم 14.6/1.7 بالدستور بالضبط ──
    if final_exit_reason == "SL_HIT_BEFORE_TP1":
        classification = "LOSS"
        pnl_blended = _pnl_pct(sl_price)  # 100% من المركز يخسر مسافة SL كاملة
    elif final_exit_reason == "TP2_HIT":
        classification = "WIN_FULL"
        pnl_blended = 0.5 * _pnl_pct(tp1_price) + 0.5 * _pnl_pct(final_exit_price)
    elif final_exit_reason == "TRAILING_STOP_HIT":
        if abs(final_exit_price - entry_price) < abs(entry_price) * 0.0005:
            classification = "WIN_PARTIAL"  # التريلينغ ضرب قريب جداً من الدخول = BE فعلياً
        else:
            classification = "WIN_TRAIL"
        pnl_blended = 0.5 * _pnl_pct(tp1_price) + 0.5 * _pnl_pct(final_exit_price)
    elif final_exit_reason == "NEITHER_HIT_WITHIN_WINDOW":
        if tp1_hit:
            classification = "OPEN_AFTER_TP1"
            pnl_blended = 0.5 * _pnl_pct(tp1_price) + 0.5 * _pnl_pct(final_exit_price)
        else:
            classification = "NEITHER_HIT_WITHIN_WINDOW"
            pnl_blended = _pnl_pct(final_exit_price)
    else:
        classification = "UNKNOWN"
        pnl_blended = _pnl_pct(final_exit_price)

    result = {
        "classification": classification,
        "tp1_hit": tp1_hit,
        "tp1_price": tp1_price,
        "tp1_hit_idx_from_start": tp1_hit_idx,
        "tp1_hit_time": timestamps[tp1_hit_idx] if (tp1_hit_idx is not None and tp1_hit_idx < len(timestamps)) else None,
        "final_exit_price": round(float(final_exit_price), 6),
        "final_exit_reason": final_exit_reason,
        "final_exit_idx_from_start": final_exit_idx,
        "final_exit_time": timestamps[final_exit_idx] if (final_exit_idx is not None and final_exit_idx < len(timestamps)) else None,
        "pnl_pct_blended": round(pnl_blended, 3),
        "trail_history": trail_history,
    }
    return result


# ══════════════════════════════════════════════════════════════════
#  11) STRUCTURAL EVIDENCE WEIGHT ENGINE - محرك وزن الأدلة الهيكلية
#      (يوليو 2026، طلب صريح من المستخدم بعد تحقيق صفقة #12)
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذا المحرك ضروري (اكتشاف حي حقيقي موثّق، صفقة #12): تحقيق
# عميق كشف أن `compute_mechanical_bias_anchor()` (أعلاه، القسم 5.5)
# اعتمد فقط على "آخر كسر هيكلي واحد" بلا اعتبار لقوته النسبية أو
# لكثافة الكسور المعاكسة الأكبر قبله. الحقيقة الرياضية المكتشفة: 9
# كسور BEARISH حقيقية متتالية، ثم كسر BULLISH واحد ضعيف جداً (بلا
# ديسبليسمنت مؤكد) - النظام اختار BULLISH (المرساة الميكانيكية أعطت
# BULLISH MODERATE) رغم أن هذا بالضبط تعريف Inducement/Bull Trap حسب
# قسم 4.6 و3.5 بالدستور. النتيجة الفعلية بالسوق: 25 يوماً بلا وصول
# TP1 ولا مرة، هبوط -13%.
#
# ⚠️ هذا المحرك **لا يستبدل** compute_mechanical_bias_anchor ولا أي
# فحص حاسم آخر بالمشروع - هو **حقن سياقي إضافي مرن** (بالضبط بطلب
# المستخدم: "بدي حل جذري للافخاخ... بشكل عام لكل الحالات، وبيكون عن
# فهم ومرن... مو ١+١=٢"). لا شرط ثنائي جامد يمنع الدخول - فقط تحذير
# نصي صريح يُحقن للموديل ليقيّمه بفهمه الكامل بالسياق، بالضبط كما
# يتصرف تاجر ICT خبير: يشكّك بكسر ضعيف وسط سياق معاكس قوي، لكن لا
# يتجاهله تلقائياً لو كان الكسر نفسه قوياً جداً رغم السياق (راجع
# اختبار TEST 4 أدناه - كسر قوي وسط سياق معاكس لا يُعلَّم كفخ).
#
# مبني حصراً من نص الدستور الموثّق (لا اختراع):
#   - "BOS QUALITY SCORE" (سطر 3005-3020 بالضبط) و"CHoCH QUALITY SCORE"
#     (سطر 3199-3220) - 5 عوامل متطابقة البنية، مجموع 5-25، نفس
#     عتبات التصنيف الحرفية (20-25 Strong، 14-19 Standard، 8-13 Weak،
#     5-7 Questionable/likely inducement).
#   - قسم 4.6 "INDUCEMENT - THE TRAP OF FALSE BREAKS" (سطر 3675+):
#     "Check: is the major swing (below for uptrend, above for
#     downtrend) still intact? YES -> likely inducement".
#   - قسم 3.5 "MINOR vs MAJOR SWINGS AND THE INDUCEMENT PROBLEM"
#     (سطر 2177+): نفس المبدأ، معيار جودة السوينغ (quality score
#     15+ = Major، دون ذلك = Minor/Noise territory).
#
# العامل السادس الإضافي (compute_opposing_break_context) هو الوحيد
# غير الموثّق حرفياً بهذا الشكل بالدستور الأصلي - استُنتج مباشرة من
# التحقيق بصفقة #12 كتطبيق منطقي لنفس مبدأ قسم 4.6 (فحص "هل السوينغ
# الرئيسي المعاكس سليم؟") لكن بقياس **كثافة** الكسور المعاكسة
# المتراكمة، لا فقط سلامة سوينغ واحد - فجوة حقيقية لم تكن مغطاة.

def compute_opposing_break_context(data, break_event, swing_window=2,
                                    lookback_candles=90, precomputed_breaks=None):
    """
    ⚠️ عامل سياق إضافي (Factor 6، غير موثّق حرفياً بالدستور بهذا الشكل
    الصريح - مُستنتَج من تحقيق صفقة #12): يحسب كثافة الكسور الهيكلية
    الحقيقية المعاكسة/بنفس الاتجاه خلال نافذة زمنية سابقة لكسر معين،
    ويصنّف السياق نصياً (بلا حكم قاطع - نص تفسيري فقط).

    Args:
        break_event: عنصر واحد من detect_mss()["breaks_found"].
        precomputed_breaks: (اختياري، للأداء) قائمة breaks_found جاهزة
            بدل إعادة استدعاء detect_mss() داخلياً (مفيد لو الاستدعاء
            العلوي استدعى detect_mss مسبقاً لغرض آخر بنفس البيانات).

    Returns dict:
        {
            "same_direction_breaks_count": int,
            "opposing_direction_breaks_count": int,
            "opposing_ratio": float|None (None لو لا كسور سابقة إطلاقاً),
            "verdict": "NO_RECENT_CONTEXT"/"SUPPORTIVE_CONTEXT"/
                        "MIXED_CONTEXT"/"STRONG_OPPOSING_CONTEXT",
            "lookback_candles": int,
        }
    """
    direction = break_event.get("direction")
    break_idx = break_event.get("break_candle_index_from_end")
    if direction not in ("BULLISH", "BEARISH") or break_idx is None:
        return {"error": "INVALID_BREAK_EVENT"}

    opposite_dir = "BEARISH" if direction == "BULLISH" else "BULLISH"

    if precomputed_breaks is not None:
        breaks = precomputed_breaks
    else:
        breaks = detect_mss(data, swing_window=swing_window).get("breaks_found", [])

    same_count = 0
    opposing_count = 0
    window_floor = break_idx - lookback_candles
    for b in breaks:
        b_idx = b.get("break_candle_index_from_end")
        if b_idx is None:
            continue
        # فقط الكسور التي وقعت *قبل* هذا الكسر زمنياً (index_from_end
        # سالب دائماً؛ الأقدم = أصغر جبرياً/أكثر سلبية) وضمن النافذة
        if window_floor <= b_idx < break_idx:
            if b.get("direction") == direction:
                same_count += 1
            elif b.get("direction") == opposite_dir:
                opposing_count += 1

    total_recent = same_count + opposing_count
    if total_recent == 0:
        verdict, opposing_ratio = "NO_RECENT_CONTEXT", None
    else:
        opposing_ratio = round(opposing_count / total_recent, 2)
        if opposing_ratio >= 0.7 and opposing_count >= 3:
            verdict = "STRONG_OPPOSING_CONTEXT"
        elif opposing_ratio >= 0.5:
            verdict = "MIXED_CONTEXT"
        else:
            verdict = "SUPPORTIVE_CONTEXT"

    return {
        "same_direction_breaks_count": same_count,
        "opposing_direction_breaks_count": opposing_count,
        "opposing_ratio": opposing_ratio,
        "verdict": verdict,
        "lookback_candles": lookback_candles,
    }


def compute_structural_break_quality_score(data, break_event, swing_window=2,
                                            context_lookback=90,
                                            significant_swings_result=None):
    """
    يحسب "BOS/CHoCH Quality Score" (5 عوامل حرفية من الدستور، مجموع
    5-25) لكسر هيكلي معين، بالإضافة لعامل سياق سادس جديد (كثافة
    الكسور المعاكسة الأخيرة - راجع compute_opposing_break_context
    أعلاه). النتيجة تُحقن كسياق نصي إضافي مرن (لا شرط قاطع يمنع
    الدخول) - راجع التوثيق أعلى هذا القسم للتفصيل الكامل.

    ⚠️ لا يغيّر detect_mss ولا compute_mechanical_bias_anchor ولا أي
    دالة موجودة أصلاً - إضافة صرفة، يُستدعى صراحة من مكان الحقن
    (multi_pass_analysis.py) كطبقة تفسير إضافية فقط.

    Args:
        break_event: عنصر واحد من detect_mss()["breaks_found"].
        significant_swings_result: (اختياري، للأداء) نتيجة جاهزة من
            AuthenticityEngine.detect_significant_swings() لتفادي
            إعادة حسابها لو استُدعيت هذه الدالة عدة مرات لنفس البيانات.

    Returns dict:
        {
            "factors": {...5 عوامل بتفاصيلها الموضوعية...},
            "total_score": int (5-25),
            "max_score": 25,
            "quality_rating": "STRONG"/"STANDARD"/"WEAK"/"QUESTIONABLE"
                (يطابق حرفياً تسميات وعتبات الدستور: 20-25/14-19/8-13/5-7),
            "context": نتيجة compute_opposing_break_context (Factor 6،
                إضافة جديدة غير موثّقة حرفياً بالدستور - راجع التوثيق أعلاه),
            "narrative": نص جاهز للحقن بالبرومبت، يتضمن تحذير Inducement
                صريح فقط لو (جودة الكسر ضعيفة/مشكوكة) و(سياق معاكس قوي)
                معاً - لا أي شرط منفرد وحده.
        }
    """
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    opens = np.asarray(data.get("opens", []), dtype=float)
    n = len(closes)

    direction = break_event.get("direction")
    broken_level_idx = break_event.get("broken_level_index_from_end")
    break_idx = break_event.get("break_candle_index_from_end")
    broken_level = break_event.get("broken_level")
    if break_idx is None or n == 0 or direction not in ("BULLISH", "BEARISH"):
        return {"error": "INVALID_BREAK_EVENT"}

    break_arr_idx = n + break_idx
    if not (0 <= break_arr_idx < n):
        return {"error": "BREAK_INDEX_OUT_OF_RANGE"}

    factors = {}

    # ── Factor 1: جودة السوينغ المكسور (BOS/CHoCH Quality Score Factor
    # 1، قسم 3.3 SWING_QUALITY_SCORING) - نستخدم detect_significant_
    # swings الموجودة أصلاً بـauthenticity_engine.py (نفس معيار
    # Topographic Prominence المستخدم بكل مكان آخر بالمشروع، لا ازدواجية) ──
    tier = None
    try:
        if significant_swings_result is None:
            from authenticity_engine import AuthenticityEngine
            significant_swings_result = AuthenticityEngine().detect_significant_swings(
                data, swing_window=swing_window
            )
        if broken_level_idx is not None:
            broken_arr_idx = n + broken_level_idx
            pool = (significant_swings_result.get("all_highs_tiered", [])
                    if direction == "BULLISH" else
                    significant_swings_result.get("all_lows_tiered", []))
            for s in pool:
                if (n + s["index_from_end"]) == broken_arr_idx:
                    tier = s["tier"]
                    break
        # تحويل tier (MAJOR/MODERATE/MINOR/UNCONFIRMED_RECENT) لدرجة
        # 1-5 حسب نص الدستور ("Noise=1, Weak=2, Moderate=3, Strong=4-5")
        tier_map = {"MAJOR": 5, "MODERATE": 3, "MINOR": 2, "UNCONFIRMED_RECENT": 2}
        factor1 = tier_map.get(tier, 1)  # غير موجود بالقائمة = ضجيج محلي (Noise=1)
        factor1_detail = f"broken swing tier={tier or 'NOT_IN_SIGNIFICANT_LIST (noise-level per prominence check)'}"
    except Exception as e:
        factor1, factor1_detail, tier = 3, f"swing tier lookup failed ({e}) - neutral default used", None
    factors["broken_swing_quality"] = {"score": factor1, "detail": factor1_detail}

    # ── Factor 2: body_pct لشمعة الكسر (نص الدستور الحرفي: <40%=1,
    # 40-50%=2, 50-60%=3, 60-75%=4, >75%=5) ──
    o, h, l, c = opens[break_arr_idx], highs[break_arr_idx], lows[break_arr_idx], closes[break_arr_idx]
    rng = h - l
    body_pct = (abs(c - o) / rng * 100) if rng > 0 else 0.0
    if body_pct < 40: factor2 = 1
    elif body_pct < 50: factor2 = 2
    elif body_pct < 60: factor2 = 3
    elif body_pct < 75: factor2 = 4
    else: factor2 = 5
    factors["break_candle_body_pct"] = {"score": factor2, "detail": f"body_pct={body_pct:.1f}%"}

    # ── Factor 3: الحجم عند الكسر (نص الدستور: <0.7x=1, 0.7-1.0x=2,
    # 1.0-1.5x=3, 1.5-2.0x=4, >2.0x=5) - لو لا يوجد حجم حقيقي بالبيانات
    # (حالة شائعة موثّقة بالمشروع - راجع data_manager.py)، درجة محايدة
    # صريحة (3) بدل افتراض قيمة قد تكون خاطئة ──
    volumes = data.get("volumes")
    if volumes is not None and len(volumes) == n:
        vol_arr = np.asarray(volumes, dtype=float)
        start = max(0, break_arr_idx - 20)
        avg20 = vol_arr[start:break_arr_idx].mean() if break_arr_idx > start else vol_arr[break_arr_idx]
        vol_ratio = (vol_arr[break_arr_idx] / avg20) if avg20 > 0 else 1.0
        if vol_ratio < 0.7: factor3 = 1
        elif vol_ratio < 1.0: factor3 = 2
        elif vol_ratio < 1.5: factor3 = 3
        elif vol_ratio < 2.0: factor3 = 4
        else: factor3 = 5
        factor3_detail = f"vol_ratio={vol_ratio:.2f}x"
    else:
        factor3, factor3_detail = 3, "no real volume data available - neutral default (per data_manager limitation)"
    factors["volume_on_break"] = {"score": factor3, "detail": factor3_detail}

    # ── Factor 4: الاستمرارية Follow-through (نص الدستور: immediate
    # reversal=1, mixed=2-3, partial=3-4, clean=5) - نفحص كم شمعة من
    # آخر 5 بعد الكسر أغلقت فعلاً متجاوزة المستوى (حقيقة موضوعية) ──
    look_ahead = min(5, n - break_arr_idx - 1)
    if look_ahead > 0 and broken_level is not None:
        beyond = 0
        for j in range(break_arr_idx + 1, break_arr_idx + 1 + look_ahead):
            if direction == "BULLISH" and closes[j] > broken_level:
                beyond += 1
            elif direction == "BEARISH" and closes[j] < broken_level:
                beyond += 1
        ratio = beyond / look_ahead
        if ratio <= 0.2: factor4 = 1
        elif ratio <= 0.5: factor4 = 2
        elif ratio <= 0.75: factor4 = 3
        elif ratio < 1.0: factor4 = 4
        else: factor4 = 5
        factor4_detail = f"{beyond}/{look_ahead} candles after break closed beyond the level"
    else:
        factor4, factor4_detail = 3, "insufficient forward data yet (break too recent to assess follow-through)"
    factors["follow_through"] = {"score": factor4, "detail": factor4_detail}

    # ── Factor 5: وجود ديسبليسمنت (نص الدستور: بدون=1-2, Grade C=3,
    # Grade B=4, Grade A=5) - نفس معايير compute_displacement أعلاه
    # (القسم 1) بالضبط، لا ازدواجية منطق ──
    atr = _atr(highs, lows, closes)
    atr_val = atr[break_arr_idx] if break_arr_idx < len(atr) and atr[break_arr_idx] > 0 else None
    if atr_val:
        body_atr_ratio = abs(c - o) / atr_val
        if body_atr_ratio >= 3.0 and body_pct >= 85 and factor3 >= 4:
            factor5, grade = 5, "A"
        elif body_atr_ratio >= 2.0 and body_pct >= 70 and factor3 >= 3:
            factor5, grade = 4, "B"
        elif body_atr_ratio >= 1.5 and body_pct >= 65:
            factor5, grade = 3, "C"
        else:
            factor5, grade = 1, "NONE"
        factor5_detail = f"body/ATR={body_atr_ratio:.2f}x, displacement_grade={grade}"
    else:
        factor5, factor5_detail = 1, "ATR unavailable at this index"
    factors["displacement_grade"] = {"score": factor5, "detail": factor5_detail}

    total = factor1 + factor2 + factor3 + factor4 + factor5
    if total >= 20: rating = "STRONG"
    elif total >= 14: rating = "STANDARD"
    elif total >= 8: rating = "WEAK"
    else: rating = "QUESTIONABLE"

    context = compute_opposing_break_context(
        data, break_event, swing_window=swing_window, lookback_candles=context_lookback
    )

    # ⚠️ إعادة تصميم جذرية (يوليو 2026، بعد بحث ويب خارجي مستقل مباشر
    # عن كيف يتصرف مايكل فعلياً مع الأفخاخ - راجع docstring
    # classify_break_reversal_authenticity أدناه للتوثيق الكامل): النسخة
    # الأولى من هذا القسم كانت تُصدر "تحذير Inducement" أحادي الجانب
    # (كسر ضعيف + سياق معاكس = تحذير فقط) - هذا **خطأ فلسفي جذري** غير
    # مطابق لمنهجية مايكل الفعلية. البحث الخارجي المستقل (tradingstrategy
    # guides.com، innercircletrader.net FAQ) أكّد بالحرف: "the inducement-
    # then-reverse pattern is the HIGH-CONVICTION variant" - أي أن انعكاساً
    # تأكّد بالكامل (سحب سيولة حقيقي + ديسبليسمنت حقيقي) بعد فخ **يستحق
    # ثقة أعلى لا أقل**، بعكس ما كانت النسخة الأولى تفترضه. الفرق الجوهري
    # هو بين "فخ لسا ما تأكد انعكاسه" (نتجاهله كمرجع فقط، دون رفض أي
    # صفقة) و"فخ تأكد انعكاسه بالكامل" (هذا بالضبط ما ينتظره مايكل).
    reversal_authenticity = classify_break_reversal_authenticity(break_event, tier=tier)

    narrative = (
        f"Structural break quality score ({direction}, broken level {broken_level} at "
        f"idx {broken_level_idx}, break candle idx {break_idx}): {total}/25 "
        f"({rating}) - broken_swing_quality={factor1}({factors['broken_swing_quality']['detail']}), "
        f"body_pct_score={factor2}, volume_score={factor3}, follow_through_score={factor4}, "
        f"displacement_score={factor5}. Recent opposing-break context: "
        f"{context.get('verdict')} ({context.get('opposing_direction_breaks_count')} opposing / "
        f"{context.get('same_direction_breaks_count')} same-direction breaks in last "
        f"{context_lookback} candles). REVERSAL AUTHENTICITY: {reversal_authenticity['verdict']} - "
        f"{reversal_authenticity['narrative']}"
    )

    return {
        "factors": factors,
        "total_score": total,
        "max_score": 25,
        "quality_rating": rating,
        "context": context,
        "reversal_authenticity": reversal_authenticity,
        "narrative": narrative,
    }


# ══════════════════════════════════════════════════════════════════
#  11.5) REVERSAL AUTHENTICITY CLASSIFICATION - كيف يتصرف مايكل فعلياً
#        مع الأفخاخ (يوليو 2026، بعد بحث ويب خارجي مستقل بطلب صريح
#        من المستخدم: "بدي بحث معمق كيف بيلاقي هالافخاخ... متى مابيفوت
#        الصفقة" وتحذير صريح: "خايف انو نصير نبطل ناخد حتى الصفقات
#        الربحانة")
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (اكتشاف حاسم من البحث الخارجي، يصحح خطأ
# فلسفي بالتصميم الأول): مصادر ICT مستقلة متعددة (tradingstrategyguides.
# com "Day 8: Inducement And Stop Hunts"، innercircletrader.net FAQ)
# تؤكد بالحرف: مايكل **لا يتجنب** صفقة لمجرد وجود فخ - هو **ينتظر أن
# يكتمل تأكيد الفخ** (سحب سيولة حقيقي + ديسبليسمنت معاكس بعده)، وعندها
# **يثق بالانعكاس أكثر لا أقل**:
#   "Do not take a trade until the inducement is grabbed."
#   "A BOS or CHoCH WITHOUT a clear inducement to sweep is a LESS
#    reliable setup. The inducement-then-reverse pattern is the
#    HIGH-CONVICTION variant."
# هذا يعني: كسر لسوينغ Minor **بلا** سحب سيولة حقيقي ولا ديسبليسمنت
# = فخ *لم يتأكد بعد* (نتجاهله كمرجع اتجاهي فقط - القسم 3.5/4.6 بالدستور
# نفسه: "do NOT change your structural assessment"). لكن نفس الكسر
# **مع** سحب حقيقي وديسبليسمنت حقيقي معاً = **بالضبط النمط عالي الثقة**
# الذي يبحث عنه مايكل - نفس منطق Entry Model B (Sweep+FVG) الموجود
# أصلاً بـict_entry_checklist_engine.py، لا اختراع جديد.
#
# ⚠️ هذا يستخدم فقط حقائق موجودة أصلاً بمخرجات detect_mss() (لا حساب
# إضافي): displacement_confirmed وprior_sweep.genuine_reversal_sweep -
# كلاهما محسوبان أصلاً بدالة detect_mss نفسها.

def classify_break_reversal_authenticity(break_event, tier=None):
    """
    يصنّف "أصالة الانعكاس" لكسر هيكلي معين - أربع حالات ممكنة تطابق
    فعلياً كيف يتصرف مايكل (لا فلترة أحادية الجانب):

      MAJOR_STRUCTURAL_BREAK: الكسر لسوينغ MAJOR/MODERATE (قوي أصلاً
        بحكم جودته الطوبوغرافية) - يُعتمد بحد ذاته، لا يحتاج سلسلة تأكيد.

      CONFIRMED_REVERSAL_HIGH_CONVICTION: الكسر لسوينغ Minor لكن معه
        سحب سيولة حقيقي **و** ديسبليسمنت حقيقي معاً - هذا بالضبط النمط
        عالي الثقة الذي يبحث عنه مايكل (موثّق خارجياً: "high-conviction
        variant"). **يُعتمد بثقة، لا يُرفض**.

      PARTIALLY_CONFIRMED_DEVELOPING: تأكيد جزئي فقط (سحب بلا ديسبليسمنت،
        أو العكس) - لسا قيد التطور، ننتظر العنصر الناقص قبل الاعتماد
        الكامل - لا رفض قاطع، فقط "ليس بعد".

      UNCONFIRMED_LIKELY_INDUCEMENT: لا سحب حقيقي ولا ديسبليسمنت - فخ
        غير مؤكد على الأرجح (قسم 3.5/4.6: "لا تغيّر تقييمك الهيكلي") -
        **يُتجاهل كمرجع اتجاهي فقط**، لا يعني رفض أي صفقة أخرى مبنية
        على أدلة مختلفة.

    Args:
        break_event: عنصر من detect_mss()["breaks_found"].
        tier: تصنيف السوينغ المكسور (MAJOR/MODERATE/MINOR/None) من
            AuthenticityEngine.detect_significant_swings - إن وُجد.

    Returns dict: {"verdict": str, "narrative": str}
    """
    displacement_confirmed = break_event.get("displacement_confirmed", False)
    prior_sweep = break_event.get("prior_sweep", {}) or {}
    genuine_sweep = prior_sweep.get("genuine_reversal_sweep", False)

    is_major_swing = tier in ("MAJOR", "MODERATE")

    if is_major_swing:
        return {
            "verdict": "MAJOR_STRUCTURAL_BREAK",
            "narrative": (
                f"This break is against a {tier} swing (quality-confirmed structural "
                "level per section 3.3/3.5) - it is a genuine structural event on its own "
                "merit, regardless of any sweep/displacement chain. Trust it as-is."
            ),
        }

    if genuine_sweep and displacement_confirmed:
        return {
            "verdict": "CONFIRMED_REVERSAL_HIGH_CONVICTION",
            "narrative": (
                "This break is against a MINOR/unlisted swing, BUT it shows the FULL "
                "inducement-then-reverse confirmation chain: a genuine liquidity sweep "
                "occurred, followed by real displacement. Per Michael's actual methodology "
                "(section 4.6 + independently verified against external ICT sources: 'the "
                "inducement-then-reverse pattern is the HIGH-CONVICTION variant', 'a BOS/"
                "CHoCH WITHOUT a clear inducement to sweep is LESS reliable') - this is NOT "
                "a reason for caution, it is exactly the confirmed setup Michael waits for. "
                "Trust this break - do not discount it merely because the broken swing itself "
                "was minor in isolation."
            ),
        }

    if genuine_sweep or displacement_confirmed:
        return {
            "verdict": "PARTIALLY_CONFIRMED_DEVELOPING",
            "narrative": (
                "This break is against a MINOR/unlisted swing with PARTIAL confirmation "
                f"(genuine_sweep={genuine_sweep}, displacement={displacement_confirmed}) - "
                "per section 4.6 step 4 and the external rule 'do not take a trade until the "
                "inducement is grabbed', this is still DEVELOPING, not yet a fully confirmed "
                "reversal. Do not treat it as bias-changing yet; watch for the missing "
                "element (sweep or displacement) before trusting it as much as a fully "
                "confirmed break."
            ),
        }

    return {
        "verdict": "UNCONFIRMED_LIKELY_INDUCEMENT",
        "narrative": (
            "This break is against a MINOR/unlisted swing with NEITHER a genuine prior "
            "sweep NOR confirmed displacement on the break candle. Per section 3.5/4.6: "
            "'if price breaks a minor swing but the next major swing remains intact, this "
            "is likely inducement - do NOT change your structural assessment.' Do not treat "
            "this as a genuine reversal signal on its own; the prior, stronger-context "
            "direction should still be considered the operative one UNLESS other independent "
            "evidence (a different break, HTF confirmation, etc.) supports a change."
        ),
    }


# ══════════════════════════════════════════════════════════════════
#  PENDING ORDER INVALIDATION-BEFORE-FILL CHECK — يوليو 2026
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (اكتشاف حي مباشر، طلب صريح جوهري من
# المستخدم بعد فحص عميق لأول 5 نقاط مكتشفة آلياً من آخر شهر بيانات
# ETH/USDT حية): 4 من 5 صفقات SELL_LIMIT/BUY_LIMIT مكتشفة آلياً خسرت
# رغم أن الأوردر بقي معلَّقاً (لم يُلغَ) لساعات طويلة (أحياناً 11+
# ساعة) بانتظار انضراب سعر الدخول، وحين انضرب أخيراً، السعر كان
# بسياق مختلف كلياً عن لحظة اكتشاف الخطة (انعكاس صاروخي فور الدخول).
#
# البحث الخارجي الحاسم (litefinance.org، توثيق مستقل لمنهجية مايكل):
# "If the pending sell order is not triggered during the US kill zone,
# cancel it and wait for the next trading day." + مصادر Silver Bullet
# متعددة: "If the trade doesn't trigger within the 1-hour window,
# cancel the order and walk away." + دستورنا المحلي (أقسام 5.5 و6.6،
# INVALIDATION RULE 1: BODY CLOSE THROUGH): "candle.close below
# OB_bottom → invalidation (zone failed)".
#
# ⚠️ لكن تحقق حي مباشر أثبت أن "حد زمني ثابت بالساعات" (مثل دستورنا:
# "5m FVG unfilled after 100+ candles (~8 hours): relevance fading")
# يكسر صفقة رابحة فعلية موثّقة (صفقة #14 البشرية - بيتكوين): منطقة
# الدخول (FVG) تشكّلت لحظة النشر، لكن الدخول لم ينضرب فعلياً إلا بعد
# ~54 ساعة (يومين وربع) - وربحت +0.71%. فحص مباشر لكل شمعة 5m خلال
# هذه الـ54 ساعة أظهر: صفر إغلاق جسم شمعة تجاوز الستوب (نقطة الإبطال
# الهيكلي) - المنطقة بقيت سليمة هيكلياً بالكامل طوال الفترة، فكان
# الانتظار صحيحاً رغم طوله.
#
# القرار النهائي (طلب صريح حرفي من المستخدم، لا اختراع): "لازم تتعطل
# صلاحية الصفقة إذا انكسرت قواعدها، أما طول ما قواعدها صحيحة والتحليل
# صحيح فيك تاخد الدخول - مش نحط دخول ونتركه أسبوع وننساه، لكن مش
# نلغي صفقة ماشية صح هيكلياً وتحليلياً بس تأخر دخولها."
#
# الحل: بدل حد زمني ثابت، نراقب مباشرة هل تجاوز *إغلاق جسم شمعة*
# (لا فتيل - نفس تمييز الدستور الحرفي WICK vs BODY) مستوى الستوب
# نفسه (الستوب = نقطة الإبطال الهيكلي المشتقة أصلاً من حافة الـ
# OB/FVG + buffer، حسب قسم 15.3: "SL below the OB bottom / FVG bottom
# that justified the entry") في أي وقت بين لحظة بناء الخطة ولحظة
# انضراب الدخول الفعلي. لو صار ذلك قبل الدخول - الأساس الهيكلي الذي
# بُنيت عليه الخطة نفسه انكسر، فالأمر المعلّق يجب اعتباره ملغى
# (ORDER_INVALIDATED_BEFORE_FILL) - لا ننتظره أبداً بلا داعٍ، ولا
# نلغيه تعسفياً بمجرد مرور وقت طويل طالما ظل هيكلياً سليماً.

def check_order_invalidated_before_fill(highs, lows, closes, opens, timestamps,
                                          start_idx, entry_idx, sl_price, is_long):
    """
    يفحص - شمعة بشمعة، من start_idx (لحظة بناء الخطة) وحتى entry_idx
    (لحظة انضراب الدخول الفعلي، حصرياً أو حتى نهاية البيانات لو لم
    ينضرب بعد) - هل أغلق جسم أي شمعة (CLOSE، لا WICK) عند/تجاوز مستوى
    الستوب (نقطة الإبطال الهيكلي) *قبل* انضراب الدخول.

    Args:
        highs, lows, closes, opens: مصفوفات الأسعار (numpy أو list).
        timestamps: مصفوفة الطوابع الزمنية (ms) - بنفس طول closes.
        start_idx: مؤشر الشمعة التي بُنيت عندها الخطة (لحظة الاكتشاف).
        entry_idx: مؤشر الشمعة التي انضرب فيها الدخول فعلياً، أو None
            إذا لم ينضرب بعد ضمن البيانات المتاحة (عندها نفحص كل
            البيانات المتاحة من start_idx حتى النهاية).
        sl_price: سعر الستوب (نقطة الإبطال الهيكلي المشتقة من الخطة).
        is_long: True لصفقة شراء (الإبطال = إغلاق تحت SL)، False لبيع
            (الإبطال = إغلاق فوق SL).

    Returns dict:
        {
            "invalidated": bool,
            "invalidation_idx": int أو None (أول شمعة أبطلت الأساس),
            "invalidation_time_ms": int أو None,
            "invalidation_close_price": float أو None,
            "candles_checked": int,
            "reason": str,
        }
    """
    n = len(closes)
    if n == 0 or start_idx is None or start_idx < 0 or start_idx >= n:
        return {"invalidated": False, "invalidation_idx": None,
                "invalidation_time_ms": None, "invalidation_close_price": None,
                "candles_checked": 0,
                "reason": "INSUFFICIENT_DATA: cannot check invalidation window"}

    end_check_idx = entry_idx if entry_idx is not None else (n - 1)
    end_check_idx = min(end_check_idx, n - 1)

    checked = 0
    for i in range(start_idx, end_check_idx + 1):
        checked += 1
        body_close = float(closes[i])
        # ⚠️ نفس تمييز الدستور الحرفي (أقسام 5.5/6.6): فقط إغلاق الجسم
        # يُبطل - فتيل يخترق ويرجع للداخل لا يُبطل (بل قد يُعتبر سحب
        # سيولة يقوّي المنطقة، لكن هذا خارج نطاق هذا الفحص - هنا فقط
        # نتحقق من الإبطال الحقيقي).
        is_invalidated_here = (body_close < sl_price) if is_long else (body_close > sl_price)
        if is_invalidated_here:
            return {
                "invalidated": True,
                "invalidation_idx": i,
                "invalidation_time_ms": int(timestamps[i]) if i < len(timestamps) else None,
                "invalidation_close_price": body_close,
                "candles_checked": checked,
                "reason": (
                    f"Body close at {body_close:.6g} "
                    f"{'below' if is_long else 'above'} the structural stop-loss level "
                    f"({sl_price:.6g}) before the pending order was filled - the structural "
                    f"basis that justified this entry no longer holds. Per the constitution "
                    f"(sections 5.5/6.6 INVALIDATION RULE 1: BODY CLOSE THROUGH), this "
                    f"invalidates the zone regardless of how much time has passed."
                ),
            }

    return {
        "invalidated": False,
        "invalidation_idx": None,
        "invalidation_time_ms": None,
        "invalidation_close_price": None,
        "candles_checked": checked,
        "reason": (
            f"No body close breached the structural stop-loss level ({sl_price:.6g}) across "
            f"{checked} candle(s) between plan formation and order fill - the structural basis "
            f"remains intact regardless of elapsed time (matches confirmed live case: a trade "
            f"whose entry filled after 54 hours with zero structural breach in that window "
            f"still won)."
        ),
    }


# ══════════════════════════════════════════════════════════════════
#  BREAKER BLOCK OPPORTUNITY DETECTION — يوليو 2026
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (نقد خارجي دقيق جداً من المستخدم، طلب
# صريح: "استخدم مراجع وبحث معمق وحسّن التعديلات لتصير خارقة ومتكاملة
# كاملة بدون نقص"): محرك الإبطال (check_order_invalidated_before_fill)
# يكتشف أن الأساس الهيكلي (OB/FVG) "فشل" (body close تجاوز حافته)،
# لكنه يكتفي بإلغاء الأمر المعلَّق (ORDER_INVALIDATED_BEFORE_FILL)
# ويرمي المعلومة بالكامل. هذا فجوة حقيقية موثّقة بدستورنا المحلي نفسه
# (قسم 5.6 BREAKER BLOCK، سطر ~4534) لكنها غير مُطبَّقة بالكود إطلاقاً
# رغم توفر كل الأدوات الرياضية اللازمة (detect_order_blocks, detect_mss).
#
# البحث الخارجي المستقل (6+ مصادر متطابقة، أبرزها innercircletrader.net
# "ICT Breaker Block Trading" وtradingstrategyguides.com "Day 12:
# Breaker Blocks & Mitigation Blocks Explained") يؤكد بالحرف الشروط
# الأربعة الإلزامية لتأكيد Breaker Block (لا اختراع، منقول حرفياً):
#   1. "A clean Liquidity Sweep" - سحب سيولة حقيقي حصل عند حافة الـOB
#      الأصلية قبل فشلها (هذا بالضبط ما يميّز Breaker عن Mitigation:
#      "Breaker block = order block failed after sweeping liquidity
#      first -> higher probability. Mitigation block = order block
#      failed without sweeping liquidity first -> valid but lower
#      probability" - tradingstrategyguides.com).
#   2. "A valid order block at the swept extreme" - وجود OB حقيقي
#      (بشروطه الأربعة الكاملة، لا افتراض) عند نقطة السحب.
#   3. "Price closing above/below the OB extreme" (BODY CLOSE، لا
#      WICK - نفس تمييزنا الحالي بالضبط، لا تغيير هنا).
#   4. "A confirming Market Structure Shift" بفريم أدق يؤكد الاتجاه
#      الجديد فعلياً - لا مجرد سحب+فشل بلا تأكيد هيكلي حقيقي.
#
# القاعدة الحاسمة للتفريق (نفس الاختبار بكل المصادر الستة+ المفحوصة،
# لا تناقض بينها إطلاقاً): "If price closed past the OB extreme, it
# is a Breaker (reversal trade). If the OB held, it is a Mitigation
# (continuation trade)." - عندنا هنا العنصر الأول (فشل الـOB) مؤكَّد
# مسبقاً بحكم استدعاء هذه الدالة أصلاً (بعد check_order_invalidated_
# before_fill)، لذلك نحتاج فقط نتحقق من العنصرين المتبقيين (السحب
# السابق + الـMSS التأكيدي) لنحسم Breaker (عكس الاتجاه) أو Mitigation
# (استمرار الاتجاه الأصلي - يبقى الأمر ملغى ببساطة، لا فرصة جديدة).
#
# القواعد المتفَق عليها للستوب والهدف (مطابقة حرفياً لكل المصادر،
# متطابقة 100% فيما بينها):
#   - الدخول: عند التاچ اللاحق لنفس منطقة الـOB الفاشلة (من الجهة
#     المعاكسة - "wait for the retrace back to the Breaker zone").
#   - الستوب: "beyond the wick of the swept extreme that preceded the
#     Breaker, with a small buffer" - أي خلف أبعد نقطة وصلها السحب
#     الأصلي (لا حافة الـOB نفسها فقط - نقطة السحب الفعلية غالباً
#     أبعد قليلاً، وهي نقطة الإبطال الحقيقية للفكرة الجديدة).
#   - الهدف: "the next significant liquidity pool" - نفس أداة
#     find_tp_targets الموجودة أصلاً بالمشروع، لا حساب جديد مخترع.
#
# ⚠️ حماية صارمة (طلب صريح متكرر من المستخدم: "بدون ما ننزع الصفقات
# الرابحة"): هذه الدالة **جديدة تماماً ومستقلة بالكامل** - لا تُعدَّل
# ولا تُستدعى تلقائياً من check_order_invalidated_before_fill نفسها،
# ولا من compute_trade_outcome الأساسي. هي طبقة اكتشاف *إضافية*
# اختيارية (opportunity scouting) تُستدعى صراحة فقط حين يريد المستخدم
# فعلياً معرفة "هل توجد فرصة عكسية بعد هذا الإبطال؟" - صفر تأثير على
# أي حساب ربح/خسارة موجود مسبقاً لأي صفقة موثّقة.

def detect_breaker_block_opportunity(data, invalidation_idx, sl_price, is_long,
                                       lookback=150, htf_data_sources=None):
    """
    يُستدعى بعد اكتشاف أن أمراً معلَّقاً أُبطل (check_order_invalidated_
    before_fill رجعت invalidated=True) - يفحص هل هذا الإبطال يشكّل
    فرصة Breaker Block حقيقية (انعكاس، أعلى احتمالية) أو مجرد Mitigation
    فاشل (استمرار الاتجاه الأصلي فقط، لا فرصة عكسية - الأمر يبقى ملغى
    كما هو دون أي إضافة).

    Args:
        data: بيانات OHLCV كاملة (نفس الفريم المستخدم بباقي التحليل).
        invalidation_idx: مؤشر الشمعة التي أبطلت الأساس الهيكلي (من
            check_order_invalidated_before_fill["invalidation_idx"]).
        sl_price: سعر الستوب الأصلي (يمثّل حافة الـOB + buffer -
            نستخدمه لتحديد أي OB بالضبط فشل).
        is_long: اتجاه الخطة *الأصلية* التي أُبطلت (True=كانت شراء).
            الـBreaker المكتشف يكون بالاتجاه *المعاكس* لهذا دائماً
            (نفس منطق "failed Bullish OB -> Bearish Breaker").
        lookback: نافذة البحث عن الـOB الأصلي وسحب السيولة (شمعات).
        htf_data_sources: (اختياري) نفس بنية find_tp_targets - لتحديد
            هدف الفرصة الجديدة من فريم أعلى إن توفر.

    Returns dict:
        {
            "opportunity_found": bool,
            "classification": "BREAKER_BLOCK_CONFIRMED" |
                "MITIGATION_ONLY_NO_REVERSAL_EDGE" | "INSUFFICIENT_DATA",
            "reversal_direction": "BULLISH"|"BEARISH"|None (اتجاه
                الفرصة الجديدة المكتشفة، إن وُجدت),
            "original_ob": dict أو None (الـOB الذي فشل),
            "liquidity_sweep": dict أو None (تفاصيل السحب السابق),
            "confirming_mss": dict أو None (تفاصيل الـMSS التأكيدي),
            "plan": dict أو None ({"entry","stop_loss","tp","tp1","tp2","rr"})
                فقط لو classification == BREAKER_BLOCK_CONFIRMED وتوفر
                هدف هيكلي حقيقي صالح باتجاه الصفقة؛ R:R تُعرض كما هي,
            "narrative": str (شرح كامل بلا هلوسة، كل رقم مُستشهَد به
                من البيانات الفعلية),
        }
    """
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    opens = np.asarray(data.get("opens", []), dtype=float)
    n = len(closes)

    if n < 20 or invalidation_idx is None or invalidation_idx < 0 or invalidation_idx >= n:
        return {
            "opportunity_found": False, "classification": "INSUFFICIENT_DATA",
            "reversal_direction": None, "original_ob": None, "liquidity_sweep": None,
            "confirming_mss": None, "plan": None,
            "narrative": "Insufficient data or invalid invalidation index - cannot assess Breaker Block opportunity.",
        }

    # الفرصة الجديدة تكون دائماً بعكس اتجاه الخطة الأصلية التي فشلت
    # (Bullish OB فشل -> Bearish Breaker يصير محتملاً، والعكس).
    new_direction_is_long = not is_long

    # ── الخطوة 1: إيجاد الـOB الأصلي الذي فشل (الذي كان يبرر الستوب
    # الأصلي sl_price - نبحث ضمن نافذة lookback قبل شمعة الإبطال) ──
    window_data = {
        "opens": opens[:invalidation_idx + 1].tolist(),
        "highs": highs[:invalidation_idx + 1].tolist(),
        "lows": lows[:invalidation_idx + 1].tolist(),
        "closes": closes[:invalidation_idx + 1].tolist(),
        "timestamps": data.get("timestamps", [])[:invalidation_idx + 1],
    }
    obs = detect_order_blocks(window_data, lookback=lookback)
    # الـOB الأصلي كان بنفس اتجاه الخطة الفاشلة (is_long الأصلي):
    # bullish OB لخطة شراء فشلت، bearish OB لخطة بيع فشلت.
    original_ob_list = obs["bullish_obs"] if is_long else obs["bearish_obs"]
    # نختار الـOB الذي حافته الأقرب لمستوى الستوب الأصلي (هذا الذي
    # بُني عليه الستوب فعلياً - علاقة سببية حقيقية، لا تخمين).
    matching_obs = []
    for ob in original_ob_list:
        edge = ob["bottom"] if is_long else ob["top"]
        if abs(edge - sl_price) <= abs(sl_price) * 0.01 + 1e-9:  # ضمن هامش الـbuffer المعقول
            matching_obs.append(ob)
    original_ob = matching_obs[-1] if matching_obs else (original_ob_list[-1] if original_ob_list else None)

    if original_ob is None:
        return {
            "opportunity_found": False, "classification": "MITIGATION_ONLY_NO_REVERSAL_EDGE",
            "reversal_direction": None, "original_ob": None, "liquidity_sweep": None,
            "confirming_mss": None, "plan": None,
            "narrative": (
                "No genuine Order Block found that matches the original stop-loss level - "
                "cannot confirm this as a Breaker Block (an unconfirmed failure is not "
                "automatically a reversal opportunity per the constitution)."
            ),
        }

    ob_edge = original_ob["bottom"] if is_long else original_ob["top"]
    ob_opposite_edge = original_ob["top"] if is_long else original_ob["bottom"]

    # ── الخطوة 2: هل حصل سحب سيولة حقيقي عند حافة الـOB *بعد* تشكّلها
    # و*قبل* شمعة الفشل نفسها؟ (هذا هو الفارق الحاسم Breaker مقابل
    # Mitigation - نفس الاختبار الموثّق بكل المصادر المستقلة المفحوصة)
    #
    # ⚠️ حل جذري (اكتُشف بunit test مباشر): يجب أن يبدأ الفحص *بعد*
    # شمعة تشكّل الـOB نفسها (وليس من الصفر) - وإلا فإن الفتيل الذي
    # شكّل الـOB بالأساس (جزء من اندفاع التكوين نفسه) قد يُحسب خطأً
    # كـ"سحب سيولة لاحق"، رغم أنه سابق زمنياً لوجود الـOB أصلاً وليس
    # اختباراً حقيقياً له. كذلك يجب أن ينتهي الفحص *عند* شمعة الفشل
    # (لا بعدها) - السحب المطلوب هو ما سبق الفشل، لا ما تلاه.
    ob_formation_idx = original_ob["index_from_end"] + len(window_data["closes"])
    sweep_search_start = ob_formation_idx + 2  # بعد شمعتي تكوين الـOB (OB+اندفاع) مباشرة
    sweep_window_data = {
        "highs": window_data["highs"][:invalidation_idx],
        "lows": window_data["lows"][:invalidation_idx],
        "closes": window_data["closes"][:invalidation_idx],
    }
    if sweep_search_start < len(sweep_window_data["closes"]):
        sweep_check = classify_sweep_or_run(
            sweep_window_data, level_price=ob_edge, level_is_high=(not is_long),
            check_from_idx=sweep_search_start,
        )
    else:
        sweep_check = {"found": False, "classification": "NOT_YET_TESTED"}
    genuine_prior_sweep = (
        sweep_check.get("found") and sweep_check.get("classification") == "GENUINE_REVERSAL_SWEEP"
    )

    # ── الخطوة 3: MSS تأكيدي بالاتجاه الجديد بعد الفشل (نفس نافذة
    # ما بعد شمعة الإبطال وحتى نهاية البيانات المتاحة) ──
    post_invalidation_data = {
        "opens": opens[invalidation_idx:].tolist() if invalidation_idx < n else [],
        "highs": highs[invalidation_idx:].tolist() if invalidation_idx < n else [],
        "lows": lows[invalidation_idx:].tolist() if invalidation_idx < n else [],
        "closes": closes[invalidation_idx:].tolist() if invalidation_idx < n else [],
        "timestamps": data.get("timestamps", [])[invalidation_idx:],
    }
    confirming_mss = None
    if len(post_invalidation_data["closes"]) >= 5:
        mss_result = detect_mss(post_invalidation_data, swing_window=2)
        matching_new_dir_breaks = [
            b for b in mss_result.get("breaks_found", [])
            if b["direction"] == ("BULLISH" if new_direction_is_long else "BEARISH")
        ]
        if matching_new_dir_breaks:
            confirming_mss = matching_new_dir_breaks[0]

    if not genuine_prior_sweep or confirming_mss is None:
        return {
            "opportunity_found": False, "classification": "MITIGATION_ONLY_NO_REVERSAL_EDGE",
            "reversal_direction": None, "original_ob": original_ob,
            "liquidity_sweep": sweep_check if genuine_prior_sweep else None,
            "confirming_mss": None, "plan": None,
            "narrative": (
                f"The original {'bullish' if is_long else 'bearish'} OB failed (body close past "
                f"{ob_edge:.6g}), but this does NOT meet the Breaker Block bar: "
                f"genuine_prior_sweep={genuine_prior_sweep}, confirming_MSS_found={confirming_mss is not None}. "
                f"Per the constitution and external verification (tradingstrategyguides.com Day 12): "
                f"'a Mitigation Block forms without sweeping liquidity first - valid but lower "
                f"probability, and does NOT flip trade direction.' This failure should be treated as "
                f"ORDER_INVALIDATED_BEFORE_FILL only - no reversal trade is justified here."
            ),
        }

    # ── الشروط الأربعة تحققت معاً: سحب سيولة حقيقي + OB حقيقي فشل +
    # body close مؤكَّد (مضمون مسبقاً بحكم استدعاء الدالة) + MSS تأكيدي.
    # نبني خطة Breaker Block كاملة: الدخول عند التاچ اللاحق لنفس منطقة
    # الـOB الفاشلة (من الجهة المعاكسة)، الستوب خلف أبعد نقطة وصلها
    # السحب الأصلي + buffer، الهدف عبر find_tp_targets الموجودة أصلاً.
    sweep_extreme = sweep_check["wick_price"]
    if n >= 15:
        atr_arr = _atr(highs, lows, closes)
        nz = atr_arr[atr_arr > 0]
        atr_val = float(nz[-1]) if len(nz) else 0.0
    else:
        atr_val = abs(ob_opposite_edge - ob_edge) * 0.1
    buffer_dist = max(atr_val * 0.1, abs(sweep_extreme) * 0.0015)

    breaker_entry = (ob_edge + ob_opposite_edge) / 2  # نفس منطق CE للمنطقة المعاد استخدامها
    breaker_sl = (sweep_extreme - buffer_dist) if new_direction_is_long else (sweep_extreme + buffer_dist)

    targets = find_tp_targets(
        data, breaker_entry, breaker_sl, is_long=new_direction_is_long,
        lookback=lookback, htf_data_sources=htf_data_sources,
    )

    plan = None
    if targets.get("tp1") is not None:
        tp1, tp2 = targets["tp1"], targets["tp2"]
        plan = {
            "direction": "BUY_LIMIT" if new_direction_is_long else "SELL_LIMIT",
            "entry": round(float(breaker_entry), 6),
            "stop_loss": round(float(breaker_sl), 6),
            "tp": tp1["price"],
            "tp1": tp1, "tp2": tp2,
            "rr": tp1["rr"],
            "basis": (
                f"BREAKER_BLOCK: original {'bullish' if is_long else 'bearish'} OB at "
                f"idx {original_ob['index_from_end']} failed after a confirmed liquidity sweep "
                f"({sweep_extreme:.6g}) and a confirming MSS to {'BULLISH' if new_direction_is_long else 'BEARISH'} - "
                f"per the constitution (section 5.6) and external ICT verification, this is a "
                f"higher-probability reversal setup, distinct from an unconfirmed Mitigation failure."
            ),
        }

    return {
        "opportunity_found": plan is not None,
        "classification": "BREAKER_BLOCK_CONFIRMED" if plan is not None else "MITIGATION_ONLY_NO_REVERSAL_EDGE",
        "reversal_direction": ("BULLISH" if new_direction_is_long else "BEARISH") if plan is not None else None,
        "original_ob": original_ob,
        "liquidity_sweep": sweep_check,
        "confirming_mss": confirming_mss,
        "plan": plan,
        "narrative": (
            f"CONFIRMED Breaker Block: the original {'bullish' if is_long else 'bearish'} OB "
            f"(idx {original_ob['index_from_end']}, edge {ob_edge:.6g}) failed with a body close, "
            f"but ONLY AFTER a genuine liquidity sweep at {sweep_extreme:.6g} and a confirming MSS "
            f"to {'BULLISH' if new_direction_is_long else 'BEARISH'} - all four ICT Breaker "
            f"confirmation conditions are met (liquidity sweep, valid OB at the swept extreme, "
            f"body close through, confirming MSS). "
            + (f"A valid reversal plan was built: entry={breaker_entry:.6g}, sl={breaker_sl:.6g}, "
               f"R:R={targets['tp1']['rr']}." if plan else
               "However, no genuine unswept structural target exists ahead of entry, so no "
               "trade plan was issued; no target number was fabricated.")
        ),
    }


# ══════════════════════════════════════════════════════════════════
#  CLASSIFY HTF STRUCTURAL CHALLENGE — انعكاس حقيقي مقابل تصحيح مؤقت
#  (يوليو 2026، بحث خارجي معمّق + طلب صريح من المستخدم)
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (اكتشاف حي مباشر): بمرحلة 4H، البوت اعترف
# صراحة برؤية انعكاس حقيقي (CHoCH بديسبليسمنت) لكنه صنّفه تلقائياً
# كـ"مجرد تصحيح" فقط لأن Daily=BEARISH - بلا أي معيار كمي واضح لمتى
# ينتهي التصحيح ويصير التزاماً حقيقياً بالاتجاه الجديد حتى على مستوى
# الانحياز الأكبر نفسه. هذا أدى لخسارة 4 صفقات SELL متتالية بينما
# السوق فعلياً كان بمرحلة تعافي/تصحيح بعد انهيار حاد (تأكدنا بالبيانات
# الفعلية: من 1504 إلى 1697، +12% تعافي خلال نفس الفترة).
#
# البحث الخارجي المستقل (6+ مصادر متطابقة 100%، أبرزها innercircletrader.
# net "ICT Market Structure Shift", fxnx.com "MSS vs CHoCH", acy.com
# "How to Confirm Trend Reversal & Direction using SMC") يعطي معياراً
# كمياً واضحاً وقابلاً للبرمجة بدقة، لا اختراع:
#
#   المرحلة 1 (IFVG/BPR - تحذير أولي): "the first reversal hint" - وحده
#     غير كافٍ لأي قرار.
#   المرحلة 2 (CHoCH/MSS - "trapdoor"): "MSS: Potential Reversal starting...
#     Smart money flipped direction" - **مجرد تحذير/بداية احتمال**، ليس
#     تأكيداً. النص الحرفي: "CHoCH is an alert, not an entry signal" و
#     "A CHoCH doesn't guarantee reversal - it's the first warning sign,
#     not confirmation."
#   المرحلة 3 (BOS تأكيدي بالاتجاه الجديد - "البوابة المصادَق عليها"):
#     "BOS: Reversal confirmed; continuation; potential new trend in
#     place... Smart money is committed to the new direction... BOS
#     validates the structure: Yes, this new move is legitimate."
#
# الاختبار الحاسم العملي (acy.com + fxnx.com، متطابقان حرفياً):
#   "A CHoCH that progresses toward a true MSS keeps displacing in the
#   new direction... If price instead trades straight back through the
#   broken level and the FVG fills entirely, the original trend is
#   probably just refueling" - أي: **الفيصل هو استمرار الدفع (BOS ثانٍ
#   بنفس الاتجاه الجديد) أو الارتداد الكامل لملء الـFVG بالكامل**، لا
#   حكم لفظي بلا معيار.
#
# القاعدة المُطبَّقة هنا (حتمية 100%، بايثون بحت):
#   REAL_REVERSAL_CONFIRMED: يوجد كسر معاكس (MSS/CHoCH) بديسبليسمنت،
#     **و** بعده كسر ثانٍ (BOS) بنفس الاتجاه الجديد (استمرار الدفع لا
#     ارتداد) - هذا وحده يستحق تحدي الانحياز الأكبر.
#   DEVELOPING_CHALLENGE: كسر معاكس بديسبليسمنت لكن بلا BOS تأكيدي بعد
#     (لسا مبكر للحكم) - لا رفض قاطع، لكن لا اعتماد كامل أيضاً.
#   LIKELY_CORRECTION_ONLY: الكسر المعاكس لم يُتبع باستمرار، والـFVG
#     الناتج عنه امتلأ بالكامل (filled_pct >= 90%) بحركة عكسية عادت
#     لصالح الاتجاه الأصلي - "the original trend is probably just
#     refueling" حرفياً.
#   NO_CHALLENGE: لا كسر معاكس بديسبليسمنت أصلاً - الانحياز الأكبر لم
#     يُتحدَّ إطلاقاً.

def classify_htf_structural_challenge(data, higher_tf_bias, lookback=100):
    """
    يفحص هل صار "تحدٍ هيكلي حقيقي" لانحياز أعلى (Daily/Weekly) من كسور
    بفريم أدنى (مثلاً 4H)، ويصنّفه حسب المعيار الموثّق خارجياً: مجرد
    CHoCH/MSS لا يكفي - يحتاج BOS تأكيدي لاحق بنفس الاتجاه الجديد.

    Args:
        data: بيانات الفريم الأدنى (مثلاً 4H) التي نفحص كسورها.
        higher_tf_bias: "BULLISH" أو "BEARISH" (الانحياز الأعلى الحالي
            الذي نتحقق هل تحدّاه شيء حقيقي).
        lookback: نافذة البحث بالشموع.

    Returns dict:
        {
            "classification": "REAL_REVERSAL_CONFIRMED" |
                "DEVELOPING_CHALLENGE" | "LIKELY_CORRECTION_ONLY" |
                "NO_CHALLENGE",
            "challenging_break": dict أو None (الكسر المعاكس الأول),
            "confirming_bos": dict أو None (BOS التأكيدي إن وُجد),
            "fvg_fill_evidence": dict أو None (دليل الامتلاء إن انطبق),
            "narrative": str,
        }
    """
    if higher_tf_bias not in ("BULLISH", "BEARISH"):
        return {
            "classification": "NO_CHALLENGE", "challenging_break": None,
            "confirming_bos": None, "fvg_fill_evidence": None,
            "narrative": "No clear higher-timeframe bias provided - cannot assess a challenge to it.",
        }

    challenging_direction = "BEARISH" if higher_tf_bias == "BULLISH" else "BULLISH"

    try:
        mss = detect_mss(data, swing_window=2)
    except Exception:
        return {
            "classification": "NO_CHALLENGE", "challenging_break": None,
            "confirming_bos": None, "fvg_fill_evidence": None,
            "narrative": "Structural detection failed - treated as no challenge (conservative default).",
        }

    challenging_breaks = [
        b for b in mss.get("breaks_found", [])
        if b["direction"] == challenging_direction and b.get("displacement_confirmed")
    ]
    if not challenging_breaks:
        return {
            "classification": "NO_CHALLENGE", "challenging_break": None,
            "confirming_bos": None, "fvg_fill_evidence": None,
            "narrative": (
                f"No genuine displacement-confirmed {challenging_direction} break exists against the "
                f"{higher_tf_bias} bias on this timeframe - the higher-timeframe bias remains "
                f"unchallenged entirely."
            ),
        }

    challenging_break = challenging_breaks[-1]  # الأحدث
    challenge_idx = challenging_break["break_candle_index_from_end"]

    # ── هل صار BOS تأكيدي بنفس الاتجاه الجديد (challenging_direction)
    # بعد الكسر المعاكس نفسه؟ (استمرار الدفع = التزام حقيقي) ──
    confirming_bos_list = [
        b for b in mss.get("breaks_found", [])
        if b["direction"] == challenging_direction and b["break_candle_index_from_end"] > challenge_idx
    ]
    if confirming_bos_list:
        confirming_bos = confirming_bos_list[-1]
        return {
            "classification": "REAL_REVERSAL_CONFIRMED",
            "challenging_break": challenging_break,
            "confirming_bos": confirming_bos,
            "fvg_fill_evidence": None,
            "narrative": (
                f"A genuine {challenging_direction} break with displacement occurred at idx {challenge_idx} "
                f"against the {higher_tf_bias} bias, AND a confirming follow-through break in the same "
                f"{challenging_direction} direction occurred afterward at idx {confirming_bos['break_candle_index_from_end']} "
                f"- per external ICT verification ('BOS validates the structure: smart money is committed "
                f"to the new direction'), this is a REAL reversal challenge to the higher-timeframe bias, "
                f"not a mere correction. The higher-timeframe bias should be reassessed."
            ),
        }

    # ── لا BOS تأكيدي بعد - نفحص هل الـFVG الناتج عن الكسر امتلأ
    # بالكامل بحركة عكسية (دليل "مجرد تنفيس، لا انعكاس حقيقي") ──
    try:
        fvgs = detect_fair_value_gaps(data, lookback=lookback, require_displacement=False)
        fvg_list = fvgs["bullish_fvgs"] if challenging_direction == "BULLISH" else fvgs["bearish_fvgs"]
        matching_fvgs = [
            f for f in fvg_list
            if abs((f["index_from_end"] + len(data.get("closes", []))) - (challenge_idx + len(data.get("closes", [])))) <= 3
        ]
        if matching_fvgs:
            fvg = matching_fvgs[-1]
            if fvg.get("filled_pct", 0) >= 90:
                return {
                    "classification": "LIKELY_CORRECTION_ONLY",
                    "challenging_break": challenging_break,
                    "confirming_bos": None,
                    "fvg_fill_evidence": fvg,
                    "narrative": (
                        f"A {challenging_direction} break occurred at idx {challenge_idx}, but its FVG "
                        f"has since been {fvg['filled_pct']}% filled by a reversal move back toward the "
                        f"{higher_tf_bias} direction with no confirming follow-through break - per external "
                        f"ICT verification ('if price trades straight back through the broken level and the "
                        f"FVG fills entirely, the original trend is probably just refueling'), this is LIKELY "
                        f"just a correction within the {higher_tf_bias} trend, not a genuine reversal. The "
                        f"higher-timeframe bias should NOT be overridden by this alone."
                    ),
                }
    except Exception:
        pass

    return {
        "classification": "DEVELOPING_CHALLENGE",
        "challenging_break": challenging_break,
        "confirming_bos": None,
        "fvg_fill_evidence": None,
        "narrative": (
            f"A genuine {challenging_direction} break with displacement occurred at idx {challenge_idx} "
            f"against the {higher_tf_bias} bias, but there is not yet a confirming follow-through break in "
            f"the same direction, nor clear evidence the move already reversed back (FVG not fully filled). "
            f"Per external ICT verification ('CHoCH is an alert, not an entry signal'), this is a DEVELOPING "
            f"challenge - too early to declare a reversal, but too significant to ignore. Treat the "
            f"higher-timeframe bias with reduced confidence until this resolves either way."
        ),
    }

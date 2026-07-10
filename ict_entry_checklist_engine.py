# -*- coding: utf-8 -*-
"""
ict_entry_checklist_engine.py - حل جذري (يوليو 2026، بطلب صريح من
المستخدم بعد شرح مفصّل لمشكلة جوهرية بمنهج التفكير الحالي):
════════════════════════════════════════════════════════════════════
المشكلة المشروحة حرفياً من المستخدم: "مايكل عندو مثلا واحد اتنين تلاتة
اربعة شروط - موجودين الاربعة تحققوا؟ في صفقة. مافي شي اعتباطي، الدخول
والتارغت والستوب كيف بيحطن مايكل وعلى أي أساس. لو لقى واحد واتنين
وتلاتة ومالقاش اربعة، بس مش سلبي على الاربعة (هو بس ناطر تشكّلها) -
لازم يعطي توصية: إذا تشكل الشرط الرابع هيك رح يصير الدخول/الستوب/
التارغت. أما لو فعلاً ما تحققت الشروط (شرط سلبي حقيقي) - هون بس HOLD."

قبل هذا الملف: البوت كان يقرر HOLD أو BUY_LIMIT بالاعتماد على "فهم"
الموديل اللغوي لكامل السياق دفعة واحدة - بلا تفكيك ميكانيكي صريح لكل
شرط من شروط نموذج الدخول (Section [ENTRY_MODELS] بالدستور) على حدة.
هذا يعني الموديل أحياناً يُخرج HOLD حتى لو 3 من 4 شروط متحققة فعلياً
بالبيانات الخام (لأنه لم "يربط" الشروط بوضوح كافٍ)، أو العكس (يخرج
BUY_LIMIT رغم أن شرطاً حقيقياً فعلياً فاشل/متناقض).

الحل: هذا الملف يطبّق **تفكيكاً ميكانيكياً صريحاً بايثون بحتاً** (صفر
AI) لثلاثة من نماذج الدخول الستة الموثّقة بقسم [ENTRY_MODELS]
(الأكثر تكراراً/موثوقية حسب الدستور نفسه: Model A "الحصان الأساسي"،
Model B "الأقوى"، Model C "الأكثر أماناً") - كل نموذج له قائمة شروط
حرفية (من نص الدستور "CONDITIONS (ALL must be met)")، كل شرط يُفحص
رياضياً منفصلاً كـ True/False/PENDING:
  - True: الشرط متحقق فعلياً بالبيانات (حقيقة رياضية).
  - False: الشرط فشل فعلياً (سلبي حقيقي - هذا الشرط تحديداً لن يتحقق
    بمرور الوقت وحده، يُبطل هذا النموذج تحديداً).
  - PENDING: الشرط لم يحدث بعد لكنه **ممكن** يحدث لاحقاً (مثال:
    تأكيد LTF لم يتشكل بعد، أو السعر لم يصل للمنطقة بعد) - هذا **ليس**
    فشلاً، هذا "ناطرين تشكّله" بالضبط كما وصف المستخدم.

منطق القرار لكل نموذج:
  - أي شرط False (فشل حقيقي) → DISQUALIFIED (هذا النموذج لا ينطبق،
    نجرب النموذج التالي).
  - كل الشروط True → READY (تنفيذ فوري BUY/SELL ممكن الآن).
  - كل الشروط True ما عدا شرط أو أكثر PENDING (بلا أي False) →
    PENDING_SETUP للمراقبة فقط. يمكن عرض سيناريو سعري إذا كانت منطقة
    OB/FVG قد تكوّنت فعلاً، لكن لا يتحول إلى BUY_LIMIT/SELL_LIMIT ولا
    يُفعّل تلقائياً قبل اكتمال التأكيد والتوقيت.

الدخول/الستوب/التارغت لكل نموذج **تُحسب حرفياً بنفس طريقة مايكل
الموثّقة بالدستور** (ENTRY PLACEMENT / STOP LOSS / TARGETS بكل قسم) -
لا اختراع، لا تقدير - كلها مبنية على القيم الرياضية الفعلية المُكتشفة
(OB top/bottom, FVG top/bottom/CE, سوينغ حقيقي, ATR, إلخ).
"""
import numpy as np

from ict_math_engine import (
    _atr, compute_displacement, detect_fair_value_gaps, detect_order_blocks,
    detect_mss, compute_premium_discount, find_tp_targets,
)



def _build_plan_with_tp1_tp2(data, entry_price, sl_price, is_long, basis_prefix, lookback=150,
                              htf_data_sources=None):
    """
    يستبدل الحساب القديم (`entry + 3×SL_distance`) بهدف مأخوذ من
    مستوى هيكلي موجود فعلاً. لا تُمدد المسافة للوصول إلى R:R ثابتة؛
    `find_tp_targets()` تختار المستوى ثم تُبلغ R:R الفعلية. يمكن تمرير
    min_rr كسياسة مخاطرة اختيارية، لكنه ليس طريقة لصناعة سعر الهدف.

    ⚠️ حل جذري إضافي (يوليو 2026، بعد تحقق حي مباشر على صفقة #10 أثبت
    أن TP1/TP2 كانا قريبين جداً من بعض): TP2 (Draw on Liquidity) الآن
    يُفضَّل من **فريم أعلى** (htf_data، عادة 4H أو Daily) - راجع
    docstring find_tp_targets للتفصيل الكامل المستند لقسم 12.3/14.3
    بالدستور حرفياً - "the primary target... based on Daily bias" -
    لا يُشتق من نفس فريم التنفيذ الضيق الأفق الزمني وحده بعد الآن.

    TP2 (Draw on Liquidity - هدف الجزء الباقي 50% بعد TP1) يُحسب أيضاً
    هنا (أبعد مسبح سيولة حقيقي EQH/EQL أو HTF level، أو OPEN_TRAILING
    صراحة إن لم يوجد - لا اختراع).

    Returns dict {"tp1": {...}, "tp2": {...}} أو None إذا لم يوجد أي
    مستوى حقيقي صالح باتجاه الصفقة. TP2 قد يكون OPEN_TRAILING عندما لا
    يوجد هدف ثانٍ مؤكد؛ هذا أفضل من اختراع رقم.
    """
    targets = find_tp_targets(data, entry_price, sl_price, is_long=is_long, lookback=lookback,
                               htf_data_sources=htf_data_sources)
    if not targets.get("tp1"):
        return None
    return targets


def _min_sl_buffer(last_price, atr_val):
    """سياسة buffer تشغيلية للبوت: max(0.3×ATR, 0.2%×price).

    ليست نسبة موحدة منشورة من مايكل لكل سوق؛ يجب معايرتها باختبار مستقل.
    النسخة محلية هنا لتفادي استيراد دائري مع multi_pass_analysis.py.
    """
    if not last_price:
        return 0.0
    return max(0.3 * (atr_val or 0), last_price * 0.002)


def _last_atr(data):
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    if len(closes) < 15:
        return 0.0
    atr_arr = _atr(highs, lows, closes)
    nz = atr_arr[atr_arr > 0]
    return float(nz[-1]) if len(nz) else 0.0


def _recent_ltf_confirmation(data, daily_bias, max_age=12):
    """Actual entry-TF close + displacement confirmation, not a placeholder."""
    wanted = "BULLISH" if daily_bias == "BULLISH" else "BEARISH"
    breaks = detect_mss(data, swing_window=2).get("breaks_found", [])
    matches = [
        b for b in breaks
        if b.get("direction") == wanted
        and b.get("displacement_confirmed")
        and b.get("break_candle_index_from_end", -999) >= -max_age
    ]
    return (bool(matches), matches[-1] if matches else None)


def _execution_timing(data):
    """Check the actual final candle against the model's configured windows."""
    timestamps = data.get("close_timestamps") or data.get("timestamps") or []
    if not timestamps:
        return False, {"session": "UNKNOWN", "ny_time": "missing timestamp"}
    from ict_sessions import classify_session
    info = classify_session(timestamps[-1])
    return bool(info.get("is_executable_window")), info


# ══════════════════════════════════════════════════════════════════
#  MODEL A: OTE + ORDER BLOCK (قسم 13.1 بالدستور)
# ══════════════════════════════════════════════════════════════════

def evaluate_model_a(data, daily_bias, lookback=60, htf_data_sources=None):
    """
    شروط الدستور الحرفية (13.1):
      1. HTF TREND: اتجاه مؤكد (BOS+ باتجاه daily_bias) - نستخدم
         detect_mss لإيجاد آخر كسر هيكلي فعلي بنفس اتجاه daily_bias.
      2. IMPULSE LEG: اندفاع حقيقي (compute_displacement) أنتج
         OB/FVG - نتحقق أن الـOB/FVG المرشحين نتجا فعلياً من شمعة
         اندفاع مؤكدة (displacement_confirmed=True من نفس المحركات).
      3. PULLBACK IN PROGRESS: السعر الحالي أبعد عن القمة/القاع
         الأخير من نقطة الاندفاع (تراجع فعلي حقيقي، لا استمرار).
      4. OB IN OTE: الـOB يقع ضمن نطاق 62-79% تراجع (compute_premium_
         discount).
      5. LTF CONFIRMATION: هذا الشرط الوحيد الذي يُترك PENDING دائماً
         هنا (يحتاج تأكيد هيكلي فعلي على فريم أدق من فريم البيانات
         المُمرَّرة لهذه الدالة - يُفحص لاحقاً بفريم Entry الفعلي
         بواسطة _verify_ltf_confirmation في multi_pass_analysis.py،
         لا هنا) - **هذا بالضبط الشرط الرابع "الناطرين تشكّله"** الذي
         وصفه المستخدم.
      6. TIMING: Kill Zone فعّالة - يُفحص خارجياً (ict_sessions.py)،
         PENDING إذا خارج نافذة تنفيذ حالياً.

    Returns dict:
        {
            "model": "MODEL_A_OTE_OB",
            "status": "DISQUALIFIED"|"PENDING_SETUP"|"READY",
            "conditions": [{"name","status","detail"}],
            "plan": {"entry","stop_loss","tp","direction"} or None,
        }
    """
    is_long = daily_bias == "BULLISH"
    conditions = []
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 20:
        return {"model": "MODEL_A_OTE_OB", "status": "DISQUALIFIED",
                "conditions": [{"name": "DATA", "status": False, "detail": "insufficient candles"}],
                "plan": None}

    last_price = float(closes[-1])
    atr_val = _last_atr(data)

    # شرط 1: اتجاه مؤكد بكسر هيكلي فعلي بنفس اتجاه daily_bias
    mss = detect_mss(data, swing_window=2)
    matching_breaks = [b for b in mss["breaks_found"]
                        if b["direction"] == ("BULLISH" if is_long else "BEARISH")]
    cond1 = bool(matching_breaks)
    conditions.append({
        "name": "HTF_TREND_CONFIRMED_BOS",
        "status": cond1,
        "detail": (f"Confirmed {daily_bias} break at idx {matching_breaks[-1]['break_candle_index_from_end']}"
                   if cond1 else f"No confirmed structural break in {daily_bias} direction found"),
    })
    if not cond1:
        return {"model": "MODEL_A_OTE_OB", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    last_break = matching_breaks[-1]
    impulse_start_idx = last_break["broken_level_index_from_end"] + n
    impulse_end_search_from = last_break["break_candle_index_from_end"] + n

    # شرط 2: اندفاع حقيقي منتج OB/FVG. ⚠️ ترتيب زمني صحيح (تصحيح
    # جذري): الـOB بحكم تعريفه هو "آخر شمعة معاكسة قبل الاندفاع" الذي
    # أنتج الكسر - أي يقع زمنياً *قبل أو عند* شمعة الكسر نفسها، لا
    # بعدها (كان هذا معكوساً بمحاولة أولى - راجع تعليق OB definition
    # بـict_math_engine.py: "الشمعة الأولى (المعاكسة) قبل الانعكاس").
    # نبحث ضمن نافذة معقولة حول شمعة الكسر (من بداية الاندفاع وحتى
    # قليلاً بعد الكسر - يسمح بالـOB الذي أُعيد اختباره لاحقاً أيضاً).
    obs = detect_order_blocks(data, lookback=lookback)
    fvgs = detect_fair_value_gaps(data, lookback=lookback, require_displacement=True)
    ob_list = obs["bullish_obs"] if is_long else obs["bearish_obs"]
    fvg_list = fvgs["bullish_fvgs"] if is_long else fvgs["bearish_fvgs"]
    window_start = impulse_start_idx - 5
    window_end = impulse_end_search_from + 5
    relevant_obs = [ob for ob in ob_list if window_start <= (ob["index_from_end"] + n) <= window_end]
    cond2 = bool(relevant_obs)
    conditions.append({
        "name": "IMPULSE_PRODUCED_OB",
        "status": cond2,
        "detail": (f"{len(relevant_obs)} {daily_bias} OB(s) found around the impulse leg that produced the break"
                   if cond2 else "No OB found around the impulse leg that produced the confirmed break"),
    })
    if not cond2:
        return {"model": "MODEL_A_OTE_OB", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    chosen_ob = relevant_obs[-1]  # أحدث OB منتج من نفس الاندفاع

    # شرط 3: تراجع حقيقي قيد التقدم (السعر الحالي ابتعد عن أقصى نقطة الاندفاع)
    impulse_extreme = float(highs[impulse_end_search_from:n].max()) if is_long else float(lows[impulse_end_search_from:n].min())
    if is_long:
        pulled_back = last_price < impulse_extreme
    else:
        pulled_back = last_price > impulse_extreme
    conditions.append({
        "name": "PULLBACK_IN_PROGRESS",
        "status": pulled_back,
        "detail": f"last_price={last_price:.6g} vs impulse_extreme={impulse_extreme:.6g}",
    })
    if not pulled_back:
        return {"model": "MODEL_A_OTE_OB", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # شرط 4: الـOB يقع ضمن نطاق OTE 62-79% من الاندفاع.
    # ⚠️ تصحيح جذري (اكتُشف بفحص رياضي مباشر): نقطة بداية الاندفاع
    # الحقيقية هي أدنى سعر (لصعود) أو أعلى سعر (لهبوط) ضمن نافذة
    # الاندفاع نفسها (من قبل الكسر بقليل وحتى شمعة الكسر) - وليست
    # سعر "المستوى المكسور نفسه" (broken_level هو القمة/القاع السابقة
    # التي تجاوزها الإغلاق، لا نقطة انطلاق الاندفاع فعلياً؛ في الاتجاه
    # الصاعد نقطة انطلاق الاندفاع الحقيقية هي القاع الذي سبقه، عادة
    # عند/قرب شمعة الـOB نفسها).
    search_from = max(0, min(impulse_start_idx, impulse_end_search_from) - 3)
    search_to = max(impulse_start_idx, impulse_end_search_from) + 1
    if is_long:
        impulse_origin = float(lows[search_from:search_to].min())
        swing_low, swing_high = impulse_origin, impulse_extreme
    else:
        impulse_origin = float(highs[search_from:search_to].max())
        swing_low, swing_high = impulse_extreme, impulse_origin
    if swing_high <= swing_low:
        cond4 = False
        pd_info = {"error": "INVALID_RANGE"}
    else:
        ob_mid = (chosen_ob["top"] + chosen_ob["bottom"]) / 2
        pd_info = compute_premium_discount(swing_low, swing_high, ob_mid,
                                            is_bullish_setup=is_long)
        cond4 = bool(pd_info.get("in_ote_zone"))
    conditions.append({
        "name": "OB_IN_OTE_ZONE",
        "status": cond4,
        "detail": f"OB midpoint retracement info: {pd_info}",
    })
    if not cond4:
        return {"model": "MODEL_A_OTE_OB", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # شرط 5: البيانات الممررة هنا هي Entry TF فعلياً؛ نفحص التأكيد
    # بدلاً من إبقائه PENDING للأبد.
    ltf_ok, ltf_break = _recent_ltf_confirmation(data, daily_bias)
    conditions.append({
        "name": "LTF_CONFIRMATION_CHOCH_OR_BOS",
        "status": ltf_ok if ltf_ok else "PENDING",
        "detail": (f"Recent entry-TF displacement break at idx {ltf_break['break_candle_index_from_end']}"
                   if ltf_ok else "Waiting for a recent displacement-backed entry-TF break"),
    })
    timing_ok, timing_info = _execution_timing(data)
    conditions.append({
        "name": "ACTIVE_KILL_ZONE_TIMING",
        "status": timing_ok if timing_ok else "PENDING",
        "detail": f"session={timing_info.get('session')} | {timing_info.get('ny_time')}",
    })

    # ── بناء خطة كاملة الأرقام (Model A: entry=OB CE, SL=below/above OB + buffer, TP=nearest opposing liquidity) ──
    entry_price = (chosen_ob["top"] + chosen_ob["bottom"]) / 2
    buffer_dist = _min_sl_buffer(last_price, atr_val)
    if is_long:
        sl_price = chosen_ob["bottom"] - buffer_dist
    else:
        sl_price = chosen_ob["top"] + buffer_dist

    # TP1/TP2 يُحسبان من مستويات هيكلية حقيقية، لا من entry+3×SL.
    # إذا لم يوجد مستوى صالح باتجاه الصفقة فلا توجد خطة؛ وإلا نعرض R:R
    # الفعلية من دون تمديد الهدف.
    sl_dist = abs(entry_price - sl_price)
    targets = _build_plan_with_tp1_tp2(data, entry_price, sl_price, is_long,
                                        "Model A: entry=OB CE, SL=OB edge - buffer",
                                        htf_data_sources=htf_data_sources)
    conditions.append({
        "name": "TP1_STRUCTURAL_LEVEL_FOUND",
        "status": targets is not None,
        "detail": (f"TP1={targets['tp1']['price']} at {targets['tp1']['kind']} (R:R={targets['tp1']['rr']})"
                   if targets else "No valid real structural level found beyond entry for TP1"),
    })
    if targets is None:
        return {"model": "MODEL_A_OTE_OB", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    tp1, tp2 = targets["tp1"], targets["tp2"]
    plan = {
        "direction": "BUY_LIMIT" if is_long else "SELL_LIMIT",
        "entry": round(float(entry_price), 6),
        "stop_loss": round(float(sl_price), 6),
        "tp": tp1["price"],  # توافق خلفي - يبقى يشير لـTP1 دائماً
        "tp1": tp1, "tp2": tp2,
        "rr": tp1["rr"],
        "basis": "Model A: entry=OB CE, SL=OB edge - buffer, TP1/TP2=Draw on Liquidity per section 14.2/14.3",
        # ⚠️ مرساة الدليل (يوليو 2026، حل جذري لمشكلة "الالتفاف اللفظي" -
        # راجع docstring evaluate_all_entry_models القسم الجديد): أحدث
        # مؤشر شمعة استند إليه هذا التفكيك الميكانيكي - أي اعتراض من
        # الموديل يجب أن يستشهد بدليل أحدث زمنياً من هذا المؤشر (رقم
        # أصغر أو يساوي - الفهرسة index_from_end سالبة، الأقرب للصفر=الأحدث).
        "evidence_anchor_idx": last_break["break_candle_index_from_end"],
    }

    any_hard_false = any(c["status"] is False for c in conditions)
    if any_hard_false:
        status = "DISQUALIFIED"
    elif all(c["status"] is True for c in conditions):
        status = "READY"
    else:
        status = "PENDING_SETUP"
    return {"model": "MODEL_A_OTE_OB", "status": status, "conditions": conditions, "plan": plan}


# ══════════════════════════════════════════════════════════════════
#  MODEL B: LIQUIDITY SWEEP + FVG (قسم 13.2 بالدستور)
# ══════════════════════════════════════════════════════════════════

def evaluate_model_b(data, daily_bias, lookback=60, htf_data_sources=None):
    """
    شروط الدستور الحرفية (13.2):
      1. IDENTIFIED LIQUIDITY: قمة/قاع سوينغ حقيقي واضح (حقيقة رياضية
         مباشرة من detect_mss/الكسور - نستخدم آخر سوينغ حقيقي مقابل
         لاتجاه daily_bias كمستوى سيولة مرشح).
      2. SWEEP CONFIRMED: فتيل يخترق المستوى، إغلاق يرجع للداخل
         (classify_sweep_or_run - حقيقة رياضية صارمة GENUINE_REVERSAL_
         SWEEP لا LIQUIDITY_RUN_CONTINUATION).
      3. DISPLACEMENT AFTER SWEEP: اندفاع حقيقي (compute_displacement)
         خلال 1-5 شموع بعد شمعة السحب مباشرة، بالاتجاه المعاكس للسحب
         (أي باتجاه daily_bias).
      4. FVG CREATED: فجوة حقيقية تشكّلت من نفس هذا الاندفاع.
      5. HTF BIAS ALIGNMENT: اتجاه الانعكاس يطابق daily_bias (مضمون
         بحكم البحث نفسه - نبحث فقط عن سحب معاكس لـdaily_bias).
      6. TIMING: Kill Zone - PENDING دائماً هنا (يُفحص خارجياً).

    Returns: نفس بنية evaluate_model_a تماماً.
    """
    from ict_math_engine import classify_sweep_or_run

    is_long = daily_bias == "BULLISH"
    conditions = []
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 20:
        return {"model": "MODEL_B_SWEEP_FVG", "status": "DISQUALIFIED",
                "conditions": [{"name": "DATA", "status": False, "detail": "insufficient candles"}],
                "plan": None}

    last_price = float(closes[-1])
    atr_val = _last_atr(data)
    swing_window = 2

    # شرط 1: إيجاد آخر سوينغ حقيقي معاكس لاتجاه daily_bias (المستوى
    # الذي يُتوقع سحبه - للشراء نبحث عن آخر قاع سوينغ SSL؛ للبيع آخر
    # قمة سوينغ BSL)
    if is_long:
        swing_idx_list = [i for i in range(swing_window, n - swing_window)
                           if lows[i] == min(lows[i - swing_window:i + swing_window + 1])]
    else:
        swing_idx_list = [i for i in range(swing_window, n - swing_window)
                           if highs[i] == max(highs[i - swing_window:i + swing_window + 1])]
    cond1 = bool(swing_idx_list)
    conditions.append({
        "name": "IDENTIFIED_LIQUIDITY_LEVEL",
        "status": cond1,
        "detail": (f"{len(swing_idx_list)} candidate swing level(s) found"
                   if cond1 else "No clear swing level found to act as a liquidity target"),
    })
    if not cond1:
        return {"model": "MODEL_B_SWEEP_FVG", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # نفحص من الأحدث للأقدم أول سوينغ نجد سحباً حقيقياً له
    sweep_result = None
    swept_level = None
    swept_idx = None
    for sidx in reversed(swing_idx_list[-6:]):  # آخر 6 مرشحين فقط (كفاية عملية)
        level_price = float(lows[sidx]) if is_long else float(highs[sidx])
        res = classify_sweep_or_run(data, level_price, level_is_high=(not is_long),
                                     check_from_idx=sidx + 1)
        if res.get("found") and res.get("classification") == "GENUINE_REVERSAL_SWEEP":
            sweep_result = res
            swept_level = level_price
            swept_idx = sidx
            break

    cond2 = sweep_result is not None
    conditions.append({
        "name": "SWEEP_CONFIRMED_GENUINE",
        "status": cond2,
        "detail": (f"Genuine sweep of level {swept_level} at candle idx {sweep_result['candle_index_from_end']}"
                   if cond2 else "No genuine reversal sweep (wick beyond + close back inside) found for any recent swing level"),
    })
    if not cond2:
        return {"model": "MODEL_B_SWEEP_FVG", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    sweep_candle_idx = sweep_result["candle_index_from_end"] + n

    # شرط 3: اندفاع حقيقي خلال 1-5 شموع بعد شمعة السحب، بالاتجاه المعاكس (نحو daily_bias)
    disp_info = compute_displacement(data, lookback=min(n - 1, lookback))
    disp_after_sweep = [
        d for d in disp_info["displacement_candles"]
        if 0 < (d["index_from_end"] + n) - sweep_candle_idx <= 5
        and d["direction"] == ("BULLISH" if is_long else "BEARISH")
    ]
    cond3 = bool(disp_after_sweep)
    conditions.append({
        "name": "DISPLACEMENT_AFTER_SWEEP",
        "status": cond3 if (n - 1 - sweep_candle_idx) >= 1 else "PENDING",
        "detail": (f"Displacement candle found at idx {disp_after_sweep[-1]['index_from_end']}"
                   if cond3 else "No displacement candle in the 5 candles following the sweep yet"),
    })
    if not cond3 and (n - 1 - sweep_candle_idx) >= 5:
        # مرّت أكثر من 5 شموع بلا اندفاع - الفرصة فاتت فعلياً، لا PENDING بعد الآن
        return {"model": "MODEL_B_SWEEP_FVG", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}
    if not cond3:
        # لسا ضمن نافذة الـ5 شموع - PENDING حقيقي، لا فشل
        conditions[-1]["status"] = "PENDING"

    # شرط 4: FVG تشكّلت من نفس الاندفاع (إن وُجد الاندفاع فعلياً)
    fvgs = detect_fair_value_gaps(data, lookback=lookback, require_displacement=True)
    fvg_list = fvgs["bullish_fvgs"] if is_long else fvgs["bearish_fvgs"]
    relevant_fvgs = [f for f in fvg_list if (f["index_from_end"] + n) >= sweep_candle_idx]
    cond4 = bool(relevant_fvgs) and cond3
    if cond3:
        conditions.append({
            "name": "FVG_FROM_DISPLACEMENT",
            "status": cond4,
            "detail": (f"{len(relevant_fvgs)} FVG(s) found after the sweep/displacement"
                       if cond4 else "No FVG formed from the post-sweep displacement yet"),
        })
    else:
        conditions.append({
            "name": "FVG_FROM_DISPLACEMENT",
            "status": "PENDING",
            "detail": "Cannot check yet - waiting for the displacement itself to occur first",
        })

    if cond3 and not cond4:
        return {"model": "MODEL_B_SWEEP_FVG", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # شرط 6: توقيت فعلي من timestamp الشمعة المغلقة الأخيرة.
    timing_ok, timing_info = _execution_timing(data)
    conditions.append({
        "name": "ACTIVE_KILL_ZONE_TIMING",
        "status": timing_ok if timing_ok else "PENDING",
        "detail": f"session={timing_info.get('session')} | {timing_info.get('ny_time')}",
    })

    # لا نبني أي أمر قبل أن يوجد displacement وFVG فعليان. النسخة
    # القديمة كانت تضع entry احتياطياً عند مستوى السحب بينما الشرطان
    # ما زالا PENDING؛ هذا pre-positioning غير مبرر. التسلسل الآمن هو:
    # sweep -> displacement/MSS -> FVG -> retracement.
    if not cond4 or not relevant_fvgs:
        return {
            "model": "MODEL_B_SWEEP_FVG",
            "status": "PENDING_SETUP",
            "conditions": conditions,
            "plan": None,
            "watch_for": "DISPLACEMENT_THEN_FVG_RETRACE",
        }

    buffer_dist = _min_sl_buffer(last_price, atr_val)
    chosen_fvg = relevant_fvgs[-1]
    entry_price = chosen_fvg["ce"]
    if is_long:
        sl_price = min(swept_level, chosen_fvg["bottom"]) - buffer_dist
    else:
        sl_price = max(swept_level, chosen_fvg["top"]) + buffer_dist

    # TP1/TP2 حقيقيان من EQH/EQL/سوينغ غير مسحوب/OB معاكس؛ لا هدف
    # حسابي تعسفي ولا شرط يجبر اختيار مستوى بعيد فقط لتحسين R:R.
    sl_dist = abs(entry_price - sl_price)
    targets = _build_plan_with_tp1_tp2(data, entry_price, sl_price, is_long,
                                        "Model B: entry=FVG CE, SL=beyond sweep extreme + buffer",
                                        htf_data_sources=htf_data_sources)
    conditions.append({
        "name": "TP1_STRUCTURAL_LEVEL_FOUND",
        "status": targets is not None,
        "detail": (f"TP1={targets['tp1']['price']} at {targets['tp1']['kind']} (R:R={targets['tp1']['rr']})"
                   if targets else "No valid real structural level found beyond entry for TP1"),
    })

    any_hard_false = any(c["status"] is False for c in conditions)
    if any_hard_false or targets is None:
        status = "DISQUALIFIED"
        plan = None
    else:
        tp1, tp2 = targets["tp1"], targets["tp2"]
        plan = {
            "direction": "BUY_LIMIT" if is_long else "SELL_LIMIT",
            "entry": round(float(entry_price), 6),
            "stop_loss": round(float(sl_price), 6),
            "tp": tp1["price"],  # توافق خلفي - يشير لـTP1 دائماً
            "tp1": tp1, "tp2": tp2,
            "rr": tp1["rr"],
            "basis": "Model B: entry=FVG CE (or sweep level if displacement/FVG still pending), SL=beyond sweep extreme + buffer, TP1/TP2=Draw on Liquidity per section 14.2/14.3",
            "evidence_anchor_idx": sweep_result["candle_index_from_end"],
        }
        if all(c["status"] is True for c in conditions if c["name"] not in
               ("DISPLACEMENT_AFTER_SWEEP", "FVG_FROM_DISPLACEMENT", "ACTIVE_KILL_ZONE_TIMING")):
            status = "READY" if not any(c["status"] == "PENDING" for c in conditions) else "PENDING_SETUP"
        else:
            status = "PENDING_SETUP"

    return {"model": "MODEL_B_SWEEP_FVG", "status": status, "conditions": conditions, "plan": plan}


# ══════════════════════════════════════════════════════════════════
#  MODEL C: BOS PULLBACK (قسم 13.3 بالدستور - "الأكثر أماناً")
# ══════════════════════════════════════════════════════════════════

def evaluate_model_c(data, daily_bias, lookback=60, htf_data_sources=None):
    """
    شروط الدستور الحرفية (13.3):
      1. CONFIRMED BOS: كسر هيكلي حقيقي بنفس اتجاه daily_bias (detect_mss).
      2. OB/FVG FROM THE BOS: على الأقل OB واحد (الشمعة المعاكسة الأخيرة
         قبل اندفاع الكسر) موجود.
      3. PULLBACK IN PROGRESS: السعر الحالي تراجع عن قمة/قاع الاندفاع.
      4. STRUCTURE INTACT: السوينغ الجديد (HL بعد BOS صاعد، أو LH بعد
         BOS هابط) لم ينكسر بعد - نفحص أن السعر الحالي لم يتجاوز
         (بإغلاق) المستوى المكسور بالعكس مجدداً.
      5. LTF CONFIRMATION: PENDING دائماً (كما بالنموذج A).
      6. HTF ALIGNMENT: مضمون (نبحث فقط بنفس اتجاه daily_bias أصلاً).

    Returns: نفس بنية evaluate_model_a.
    """
    is_long = daily_bias == "BULLISH"
    conditions = []
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 20:
        return {"model": "MODEL_C_BOS_PULLBACK", "status": "DISQUALIFIED",
                "conditions": [{"name": "DATA", "status": False, "detail": "insufficient candles"}],
                "plan": None}

    last_price = float(closes[-1])
    atr_val = _last_atr(data)

    # شرط 1: كسر هيكلي مؤكد بنفس اتجاه daily_bias، مع اندفاع فعلي (displacement_confirmed)
    mss = detect_mss(data, swing_window=2)
    matching_breaks = [b for b in mss["breaks_found"]
                        if b["direction"] == ("BULLISH" if is_long else "BEARISH")
                        and b["displacement_confirmed"]]
    cond1 = bool(matching_breaks)
    conditions.append({
        "name": "CONFIRMED_BOS_WITH_DISPLACEMENT",
        "status": cond1,
        "detail": (f"Confirmed {daily_bias} BOS with displacement at idx {matching_breaks[-1]['break_candle_index_from_end']}"
                   if cond1 else f"No confirmed {daily_bias} BOS with genuine displacement found"),
    })
    if not cond1:
        return {"model": "MODEL_C_BOS_PULLBACK", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    last_break = matching_breaks[-1]
    break_candle_idx = last_break["break_candle_index_from_end"] + n
    broken_level = last_break["broken_level"]

    # شرط 2: OB موجود من نفس اندفاع الـBOS
    obs = detect_order_blocks(data, lookback=lookback)
    ob_list = obs["bullish_obs"] if is_long else obs["bearish_obs"]
    window_start = last_break["broken_level_index_from_end"] + n - 5
    relevant_obs = [ob for ob in ob_list if window_start <= (ob["index_from_end"] + n) <= break_candle_idx + 3]
    cond2 = bool(relevant_obs)
    conditions.append({
        "name": "OB_FROM_BOS_IMPULSE",
        "status": cond2,
        "detail": (f"{len(relevant_obs)} OB(s) found from the BOS impulse"
                   if cond2 else "No OB found from the BOS impulse leg"),
    })
    if not cond2:
        return {"model": "MODEL_C_BOS_PULLBACK", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    chosen_ob = relevant_obs[-1]

    # شرط 3: تراجع فعلي قيد التقدم
    impulse_extreme = float(highs[break_candle_idx:n].max()) if is_long else float(lows[break_candle_idx:n].min())
    pulled_back = (last_price < impulse_extreme) if is_long else (last_price > impulse_extreme)
    conditions.append({
        "name": "PULLBACK_IN_PROGRESS",
        "status": pulled_back,
        "detail": f"last_price={last_price:.6g} vs impulse_extreme={impulse_extreme:.6g}",
    })
    if not pulled_back:
        return {"model": "MODEL_C_BOS_PULLBACK", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # شرط 4: الهيكل الجديد لا يزال سليماً - السعر الحالي لم يُغلق عائداً
    # عبر المستوى المكسور بالاتجاه المعاكس (لو حصل هذا، الـBOS قد يكون
    # كان زائفاً - فشل حقيقي، لا PENDING)
    if is_long:
        structure_intact = last_price > broken_level * 0.995  # هامش صغير للضجيج الطبيعي
    else:
        structure_intact = last_price < broken_level * 1.005
    conditions.append({
        "name": "NEW_STRUCTURE_INTACT",
        "status": structure_intact,
        "detail": f"last_price={last_price:.6g} vs broken_level={broken_level:.6g} (BOS level must hold)",
    })
    if not structure_intact:
        return {"model": "MODEL_C_BOS_PULLBACK", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    ltf_ok, ltf_break = _recent_ltf_confirmation(data, daily_bias)
    conditions.append({
        "name": "LTF_CONFIRMATION_CHOCH_OR_BOS",
        "status": ltf_ok if ltf_ok else "PENDING",
        "detail": (f"Recent entry-TF displacement break at idx {ltf_break['break_candle_index_from_end']}"
                   if ltf_ok else "Waiting for a recent displacement-backed entry-TF break"),
    })
    timing_ok, timing_info = _execution_timing(data)
    conditions.append({
        "name": "ACTIVE_KILL_ZONE_TIMING",
        "status": timing_ok if timing_ok else "PENDING",
        "detail": f"session={timing_info.get('session')} | {timing_info.get('ny_time')}",
    })

    # ── الخطة: entry=OB CE، SL=تحت/فوق الهيكل الجديد (HL/LH) + buffer،
    # TP1=المستوى المكسور نفسه (broken_level) - بالضبط كما ينص الدستور
    # "TP1: the BOS level itself" ──
    entry_price = (chosen_ob["top"] + chosen_ob["bottom"]) / 2
    buffer_dist = _min_sl_buffer(last_price, atr_val)
    if is_long:
        sl_price = chosen_ob["bottom"] - buffer_dist
        tp_price = broken_level
    else:
        sl_price = chosen_ob["top"] + buffer_dist
        tp_price = broken_level

    sl_dist = abs(entry_price - sl_price)
    tp_dist = abs(tp_price - entry_price)
    # Model C uses the real broken BOS level when it is ahead of entry.
    # Its actual R:R is reported honestly; the target is not discarded or
    # stretched merely because it is below an arbitrary 3R threshold.
    bos_target_ahead = (tp_price > entry_price) if is_long else (tp_price < entry_price)
    if sl_dist > 0 and bos_target_ahead:
        tp1 = {
            "price": round(float(tp_price), 6), "level_price": tp_price, "kind": "BROKEN_BOS_LEVEL",
            "rr": round(tp_dist / sl_dist, 2),
            "detail": "TP1 = the genuine broken BOS level; R:R reported without target stretching",
        }
        targets = find_tp_targets(data, entry_price, sl_price, is_long=is_long, lookback=lookback,
                                   htf_data_sources=htf_data_sources)
        tp2 = targets.get("tp2", {"mode": "OPEN_TRAILING", "detail": "no TP2 candidate computed"})
    else:
        targets = _build_plan_with_tp1_tp2(data, entry_price, sl_price, is_long,
                                            "Model C: entry=OB CE from BOS impulse, SL=OB edge - buffer",
                                            htf_data_sources=htf_data_sources)
        tp1 = targets["tp1"] if targets else None
        tp2 = targets["tp2"] if targets else {"mode": "OPEN_TRAILING", "detail": "no TP2 candidate computed"}

    conditions.append({
        "name": "TP1_STRUCTURAL_LEVEL_FOUND",
        "status": tp1 is not None,
        "detail": (f"TP1={tp1['price']} at {tp1['kind']} (R:R={tp1['rr']})"
                   if tp1 else "Neither the broken BOS level nor another valid real structural TP1 was found"),
    })
    if tp1 is None:
        return {"model": "MODEL_C_BOS_PULLBACK", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    plan = {
        "direction": "BUY_LIMIT" if is_long else "SELL_LIMIT",
        "entry": round(float(entry_price), 6),
        "stop_loss": round(float(sl_price), 6),
        "tp": tp1["price"],  # توافق خلفي - يشير لـTP1 دائماً
        "tp1": tp1, "tp2": tp2,
        "rr": tp1["rr"],
        "basis": "Model C: entry=OB CE from BOS impulse, SL=OB edge - buffer, TP1=broken BOS level (or nearest genuine level if <3:1), TP2=Draw on Liquidity",
        "evidence_anchor_idx": last_break["break_candle_index_from_end"],
    }

    any_hard_false = any(c["status"] is False for c in conditions)
    if any_hard_false:
        status = "DISQUALIFIED"
    elif all(c["status"] is True for c in conditions):
        status = "READY"
    else:
        status = "PENDING_SETUP"
    return {"model": "MODEL_C_BOS_PULLBACK", "status": status, "conditions": conditions, "plan": plan}


# ══════════════════════════════════════════════════════════════════
#  المنسّق الرئيسي: يجرب النماذج الثلاثة بترتيب أولوية الدستور
#  (13.7 SELECTION LOGIC: "Was liquidity just swept? → Model B. Is
#  there a confirmed BOS with pullback to OB/FVG? → Is OB in OTE? →
#  Model A. Else → Model C.")
# ══════════════════════════════════════════════════════════════════

def evaluate_all_entry_models(data, daily_bias, lookback=60, htf_data_sources=None, htf_major_data=None):
    """
    ⚠️ هذا الحل الجذري المطلوب صراحة من المستخدم: "لو لقى واحد واتنين
    وتلاتة ومالقاش اربعة، بس مش سلبي على الاربعة - لازم يعطي توصية
    (خطة معلقة جاهزة الأرقام). أما لو في شرط سلبي حقيقي فعلاً - HOLD."

    ⚠️ توسيع جوهري (يوليو 2026، طلب صريح من المستخدم بعد بحث عميق:
    "طب هي النماذج نافي غيرها لمايكل؟ بس ٣ نماذج مايكل بيتبع؟ ...
    بدنا نضل بعقلية مايكل ما منخرج عنها أبداً"): مايكل يوثّق **6**
    نماذج دخول رسمية بقسم [ENTRY_MODELS] (13.1-13.6)، لا 3 فقط. الآن
    نجرّب كل الستة **بترتيب الأولوية الحرفي المذكور بقسم 13.7
    "SELECTION LOGIC"**: B (أقوى - سحب سيولة) > A (الأكثر شيوعاً - OTE)
    > C (الأكثر أماناً - BOS Pullback) > D (AMD Session) > E (Silver
    Bullet) > F (CHoCH Reversal - الأعلى ريسك). فقط لو الستة معاً
    رفضت فعلاً، نلجأ للمرشّح الاحتياطي العام (GENERIC_STRUCTURAL_
    FALLBACK - ليس من نماذج مايكل الرسمية، خط دفاع أخير نادر الاستخدام
    فقط، موسوم صراحة كأضعف ثقة من أي نموذج مُسمّى).

    يجرب النماذج المطبَّقة رياضياً بهذا الترتيب ويرجع **كل** نتائجها
    مع تفصيل شرط-شرط، بالإضافة لحكم نهائي واحد:
      - لو أي نموذج READY (كل الشروط True حتى LTF) → يُفضَّل فوراً
        (بترتيب أولوية 13.7، لا أول نموذج بالترتيب العشوائي).
      - وإلا لو أي نموذج PENDING_SETUP (كل الشروط True ما عدا شروط
        PENDING حقيقية بلا أي فشل) → يُختار أفضلها (بنفس ترتيب الأولوية)
        وتُبنى خطة BUY_LIMIT/SELL_LIMIT كاملة.
      - وإلا (كل النماذج الستة DISQUALIFIED فعلياً) → نجرّب المرشّح
        الاحتياطي العام كملاذ أخير حتمي (لا مسار حر متذبذب).
      - وإلا (حتى المرشّح الاحتياطي فشل) → HOLD حقيقي، مع توثيق **أي
        شرط بالضبط فشل بكل نموذج** (لا HOLD غامض - بل تفصيل دقيق).

    Returns dict:
        {
            "final_status": "READY"|"PENDING_SETUP"|"NO_MODEL_QUALIFIES",
            "chosen_model": dict أو None (نتيجة evaluate_model_* الفائزة),
            "all_models": [نتائج كل النماذج، للشفافية الكاملة],
            "hold_reason_detail": str (فقط لو NO_MODEL_QUALIFIES - يشرح
                بالضبط أي شرط فشل بكل نموذج، لا جملة عامة),
        }
    """
    if daily_bias not in ("BULLISH", "BEARISH"):
        return {
            "final_status": "NO_MODEL_QUALIFIES",
            "chosen_model": None,
            "all_models": [],
            "hold_reason_detail": f"daily_bias='{daily_bias}' is not directional - no entry model can be evaluated without a clear bias.",
        }

    # ⚠️ ترتيب الأولوية الحرفي (قسم 13.7 "SELECTION LOGIC" بالدستور):
    # B > A > C > D > E > F - كل نموذج مبني بايثون بحتاً، صفر AI.
    results = [
        evaluate_model_b(data, daily_bias, lookback=lookback, htf_data_sources=htf_data_sources),
        evaluate_model_a(data, daily_bias, lookback=lookback, htf_data_sources=htf_data_sources),
        evaluate_model_c(data, daily_bias, lookback=lookback, htf_data_sources=htf_data_sources),
        evaluate_model_d(data, daily_bias, lookback=lookback, htf_data_sources=htf_data_sources),
        evaluate_model_e(data, daily_bias, lookback=lookback, htf_data_sources=htf_data_sources),
        evaluate_model_f(data, daily_bias, lookback=lookback, htf_data_sources=htf_data_sources,
                         htf_major_data=htf_major_data),
    ]

    ready = [r for r in results if r["status"] == "READY"]
    if ready:
        return {
            "final_status": "READY",
            "chosen_model": ready[0],
            "all_models": results,
            "hold_reason_detail": None,
        }

    pending = [r for r in results if r["status"] == "PENDING_SETUP"]
    if pending:
        # A pending sweep with no displacement/FVG has no defensible prices
        # yet. Prefer a candidate whose zone already exists, but never turn
        # either kind into an executable order until its Pending checks pass.
        pending_with_plan = [r for r in pending if r.get("plan")]
        return {
            "final_status": "PENDING_SETUP",
            "chosen_model": (pending_with_plan or pending)[0],
            "all_models": results,
            "hold_reason_detail": None,
        }

    # ⚠️ حل جذري (يوليو 2026، طلب صريح جوهري من المستخدم، اقتباس حرفي:
    # "منرجع لنفس النقطة: ليش يغلط رنستنا لتتصلح إذا منعرف شو الصح؟؟
    # ما لازم تتغير الصفقة من شراء لهولد هي غلط هيك... وليش عم يعيد
    # ألف مرة الدخولات إذا منعرف شو الدخول الصح؟؟"): قبل الاستسلام لـ
    # NO_MODEL_QUALIFIES (الذي يفتح الباب لمسار حر غير حتمي بمرحلة
    # entry ويسبب تذبذب دخول حقيقي موثّق)، نجرب المرشّح العام
    # الاحتياطي - حتمي 100% لكن أضعف ثقة من نموذج مُسمّى (لا شرط دخول
    # محدد، فقط أقرب منطقة مؤسساتية حقيقية + ستوب هيكلي خلفها).
    # لا ننشئ صفقة من "generic fallback". وجود OB/FVG قريب وحده ليس
    # نموذج دخول ولا يكفي لتجاوز شروط sweep/displacement/timing/LTF.
    # نبقي الدالة القديمة أدناه للتوافق والتحقيق فقط، لكنها لم تعد
    # قابلة للاختيار كتوصية.
    generic = evaluate_generic_structural_fallback(
        data, daily_bias, lookback=max(lookback, 150),
        htf_data_sources=htf_data_sources,
    )
    generic["status"] = "INFORMATIONAL_ONLY"
    generic["plan"] = None

    # كل النماذج DISQUALIFIED فعلياً - نبني
    # تفصيلاً دقيقاً لأول شرط فاشل بكل نموذج (لا جملة HOLD عامة غامضة)
    detail_lines = []
    for r in results:
        failed = [c for c in r["conditions"] if c["status"] is False]
        if failed:
            detail_lines.append(f"{r['model']}: failed at '{failed[0]['name']}' - {failed[0]['detail']}")
        else:
            detail_lines.append(f"{r['model']}: disqualified (insufficient data or no candidate structure found)")
    generic_failed = [c for c in generic["conditions"] if c["status"] is False]
    if generic_failed:
        detail_lines.append(f"{generic['model']}: failed at '{generic_failed[0]['name']}' - {generic_failed[0]['detail']}")

    return {
        "final_status": "NO_MODEL_QUALIFIES",
        "chosen_model": None,
        "all_models": results + [generic],
        "hold_reason_detail": " | ".join(detail_lines),
    }


# ══════════════════════════════════════════════════════════════════
#  المرشّح العام الاحتياطي (Generic Structural Fallback) - يوليو 2026
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (طلب صريح جوهري من المستخدم، اقتباس
# حرفي): "منرجع لنفس النقطة: ليش يغلط رنستنا لتتصلح إذا منعرف شو
# الصح؟؟ ما لازم تتغير الصفقة من شراء لهولد هي غلط هيك... وليش عم
# يعيد ألف مرة الدخولات إذا منعرف شو الدخول الصح؟؟"
#
# التشخيص الجذري: النماذج الثلاثة (A/B/C) حتمية 100% *فقط* عندما
# تنطبق شروطها. لو رفضت الثلاثة معاً (NO_MODEL_QUALIFIES)، كان النظام
# القديم يرمي القرار بالكامل لمسار "حر" (الموديل اللغوي يخترع دخول/
# ستوب/تارغت من فهمه العام) - هذا بالضبط مصدر التذبذب الموثّق
# (منطقة دخول مختلفة كل محاولة لنفس الصفقة بالضبط).
#
# الحل: نمدّد الحسم الحتمي ليغطي هذه الحالة أيضاً - نبني "خطة عامة
# احتياطية" من نفس الأدوات الرياضية الموجودة أصلاً (أقرب OB/FVG حقيقي
# بجهة الانحياز + أقرب ستوب هيكلي حقيقي عبر find_structural_sl_anchors
# + TP1/TP2 عبر find_tp_targets) - **بلا أي شرط دخول محدد** (لا OTE،
# لا Sweep، لا BOS Pullback تحديداً) بل ببساطة: "أقرب منطقة مؤسساتية
# حقيقية موجودة فعلاً بجهة الانحياز، بستوب هيكلي خلفها". هذا أضعف
# ثقة من Models A/B/C (يُوسَم صراحة كـ"GENERIC_FALLBACK" لا نموذج
# مُسمّى) لكنه لا يزال حتمياً 100% - نفس المدخلات تعطي نفس المخرجات
# دائماً، بلا تذبذب.

# ══════════════════════════════════════════════════════════════════
#  MODEL D: AMD SESSION ENTRY (قسم 13.4 بالدستور) - يوليو 2026
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذا النموذج ضروري (طلب صريح من المستخدم بعد بحث عميق: "طب
# هي النماذج نافي غيرها لمايكل؟ بس ٣ نماذج مايكل بيتبع؟"): مايكل نفسه
# يوثّق 6 نماذج دخول رسمية بقسم [ENTRY_MODELS]، لا 3 فقط. Model D
# (AMD Session) يعتمد على تسلسل Accumulation→Manipulation→Distribution
# داخل جلسة Kill Zone نشطة - نفس أدوات ict_sessions.py المبنية أصلاً
# لهذا الغرض بالضبط (classify_session، compute_overnight_range).
#
# التحقق الخارجي (بحث ويب مستقل، يوليو 2026): completetradersedge.com
# وtradingstrategyguides.com يؤكدان بالحرف نفس التسلسل الثلاثي
# (Accumulation range ضيق → Manipulation sweep لأحد طرفيه → Distribution
# displacement بالاتجاه المعاكس) - مطابق تماماً لنص دستورنا.

def evaluate_model_d(data, daily_bias, lookback=60, htf_data_sources=None):
    """
    شروط الدستور الحرفية (13.4):
      1. ACTIVE KILL ZONE: London أو NY AM (تفضيلاً)، NY PM مقبولة بدرجة أقل.
      2. ACCUMULATION RANGE IDENTIFIED: أول 4-8 شموع من الجلسة تشكّل
         نطاقاً ضيقاً (< 1.5×ATR إجمالي المدى).
      3. MANIPULATION OCCURRED: كسر أحد طرفي نطاق التجميع (يحدد الاتجاه
         الحقيقي المعاكس)، لمدة قصيرة (1-5 شموع).
      4. DISTRIBUTION CONFIRMED: اندفاع حقيقي بالاتجاه المعاكس للتلاعب
         (هذا هو اتجاه daily_bias المطلوب).
      5. HTF ALIGNMENT: اتجاه التوزيع يطابق daily_bias (مضمون بحكم
         البحث نفسه - نبحث فقط عن توزيع بنفس اتجاه daily_bias).
      6. FVG/OB FROM DISTRIBUTION: الاندفاع أنتج منطقة قابلة للتداول.

    Returns: نفس بنية evaluate_model_a/b/c.
    """
    from ict_sessions import classify_session

    is_long = daily_bias == "BULLISH"
    conditions = []
    opens = np.asarray(data.get("opens", []), dtype=float)
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    timestamps = data.get("close_timestamps") or data.get("timestamps", [])
    n = len(closes)
    if n < 20 or len(timestamps) != n:
        return {"model": "MODEL_D_AMD_SESSION", "status": "DISQUALIFIED",
                "conditions": [{"name": "DATA", "status": False,
                                "detail": "insufficient candles or missing timestamps"}],
                "plan": None}

    last_price = float(closes[-1])
    atr_val = _last_atr(data)

    # شرط 1: Kill Zone نشطة الآن (آخر شمعة متاحة)
    session_info = classify_session(timestamps[-1])
    active_kz = session_info["session"] in ("LONDON_KILLZONE", "NY_AM_KILLZONE", "NY_PM_KILLZONE")
    cond1 = active_kz
    conditions.append({
        "name": "ACTIVE_KILL_ZONE",
        "status": cond1,
        "detail": f"Current session: {session_info['session']} (NY time {session_info['ny_time']})"
                   if cond1 else f"Not in an active Kill Zone (current session: {session_info['session']})",
    })
    if not cond1:
        return {"model": "MODEL_D_AMD_SESSION", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # نحدد بداية الجلسة الحالية (أول شمعة بنفس اسم الجلسة، متتالية للخلف
    # من آخر شمعة) لتحديد نافذة التجميع (أول 4-8 شموع منها)
    session_start_idx = n - 1
    for i in range(n - 2, -1, -1):
        if classify_session(timestamps[i])["session"] == session_info["session"]:
            session_start_idx = i
        else:
            break
    candles_into_session = n - session_start_idx

    # شرط 2: نطاق تجميع ضيق بأول 4-8 شموع من الجلسة
    accumulation_window = min(8, max(4, candles_into_session // 2)) if candles_into_session >= 4 else candles_into_session
    acc_end_idx = min(session_start_idx + accumulation_window, n)
    if acc_end_idx - session_start_idx < 4:
        cond2 = False
        acc_high = acc_low = None
        detail2 = f"Only {acc_end_idx - session_start_idx} candle(s) into session so far - insufficient for accumulation range yet"
    else:
        acc_high = float(highs[session_start_idx:acc_end_idx].max())
        acc_low = float(lows[session_start_idx:acc_end_idx].min())
        acc_range = acc_high - acc_low
        cond2 = bool(atr_val) and acc_range < 1.5 * atr_val
        detail2 = (f"Accumulation range [{acc_low:.6g}, {acc_high:.6g}] = {acc_range:.6g} "
                    f"({'< ' if cond2 else '>= '}1.5xATR={1.5*atr_val:.6g})" if atr_val else "ATR unavailable")
    conditions.append({"name": "ACCUMULATION_RANGE_IDENTIFIED", "status": cond2, "detail": detail2})
    if not cond2:
        return {"model": "MODEL_D_AMD_SESSION", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # شرط 3: تلاعب (كسر أحد طرفي التجميع) خلال 1-5 شموع بعد نافذة التجميع
    manip_window_end = min(acc_end_idx + 5, n)
    manip_idx = None
    manip_side = None  # "BELOW" أو "ABOVE"
    for i in range(acc_end_idx, manip_window_end):
        if lows[i] < acc_low:
            manip_idx, manip_side = i, "BELOW"
            break
        if highs[i] > acc_high:
            manip_idx, manip_side = i, "ABOVE"
            break
    # الاتجاه الحقيقي المتوقع = عكس جهة التلاعب. لصفقة شراء (is_long)
    # نحتاج تلاعباً بكسر الأسفل (BELOW)؛ لصفقة بيع نحتاج كسر الأعلى.
    expected_manip_side = "BELOW" if is_long else "ABOVE"
    cond3 = manip_idx is not None and manip_side == expected_manip_side
    conditions.append({
        "name": "MANIPULATION_OCCURRED",
        "status": cond3,
        "detail": (f"Manipulation break {manip_side} the accumulation range at idx {manip_idx - n}"
                   if manip_idx is not None else "No manipulation break of the accumulation range yet")
                  + ("" if cond3 or manip_idx is None else f" (wrong side - expected {expected_manip_side})"),
    })
    if manip_idx is not None and manip_side != expected_manip_side:
        return {"model": "MODEL_D_AMD_SESSION", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}
    if manip_idx is None:
        conditions[-1]["status"] = "PENDING"

    # شرط 4: توزيع (اندفاع حقيقي بالاتجاه المعاكس للتلاعب = اتجاه daily_bias)
    disp_info = compute_displacement(data, lookback=min(n - 1, lookback))
    cond4 = False
    dist_candle = None
    if manip_idx is not None:
        disp_after_manip = [
            d for d in disp_info["displacement_candles"]
            if 0 <= (d["index_from_end"] + n) - manip_idx <= 5
            and d["direction"] == ("BULLISH" if is_long else "BEARISH")
        ]
        cond4 = bool(disp_after_manip)
        if cond4:
            dist_candle = disp_after_manip[-1]
    conditions.append({
        "name": "DISTRIBUTION_CONFIRMED",
        "status": cond4 if manip_idx is not None else "PENDING",
        "detail": (f"Distribution displacement confirmed at idx {dist_candle['index_from_end']}"
                   if cond4 else "No displacement in the expected (Daily Bias) direction after manipulation yet"),
    })
    if manip_idx is not None and not cond4:
        return {"model": "MODEL_D_AMD_SESSION", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # شرط 5: FVG/OB من التوزيع
    fvgs = detect_fair_value_gaps(data, lookback=lookback, require_displacement=True)
    fvg_list = fvgs["bullish_fvgs"] if is_long else fvgs["bearish_fvgs"]
    relevant_fvgs = []
    if dist_candle:
        dist_idx = dist_candle["index_from_end"] + n
        relevant_fvgs = [f for f in fvg_list if (f["index_from_end"] + n) >= dist_idx]
    cond5 = bool(relevant_fvgs) if dist_candle else False
    conditions.append({
        "name": "FVG_FROM_DISTRIBUTION",
        "status": cond5 if dist_candle else "PENDING",
        "detail": (f"{len(relevant_fvgs)} FVG(s) found from the distribution displacement"
                   if cond5 else "No FVG formed from distribution yet (or distribution itself still pending)"),
    })

    buffer_dist = _min_sl_buffer(last_price, atr_val)
    if cond5 and relevant_fvgs:
        chosen_fvg = relevant_fvgs[-1]
        entry_price = chosen_fvg["ce"]
        sl_price = (acc_low - buffer_dist) if is_long else (acc_high + buffer_dist)
    elif manip_idx is not None:
        # خطة احتياطية: الدخول عند إعادة اختبار طرف نطاق التجميع نفسه
        entry_price = acc_low if is_long else acc_high
        sl_price = (acc_low - buffer_dist) if is_long else (acc_high + buffer_dist)
    else:
        return {"model": "MODEL_D_AMD_SESSION", "status": "PENDING_SETUP" if cond2 else "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    targets = find_tp_targets(data, entry_price, sl_price, is_long=is_long, lookback=lookback,
                               htf_data_sources=htf_data_sources)
    cond6 = targets.get("tp1") is not None
    conditions.append({
        "name": "TP1_STRUCTURAL_LEVEL_FOUND",
        "status": cond6,
        "detail": (f"TP1={targets['tp1']['price']} (R:R={targets['tp1']['rr']})"
                   if cond6 else "No valid real structural level found beyond entry for TP1"),
    })
    if not cond6:
        return {"model": "MODEL_D_AMD_SESSION", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    tp1, tp2 = targets["tp1"], targets["tp2"]
    plan = {
        "direction": "BUY_LIMIT" if is_long else "SELL_LIMIT",
        "entry": round(float(entry_price), 6),
        "stop_loss": round(float(sl_price), 6),
        "tp": tp1["price"], "tp1": tp1, "tp2": tp2,
        "rr": tp1["rr"],
        "basis": ("Model D (AMD Session): entry=FVG CE from distribution displacement (or accumulation "
                   "range edge retest if displacement still pending), SL=beyond accumulation extreme + buffer, "
                   "TP1/TP2=Draw on Liquidity per section 14.2/14.3"),
        "evidence_anchor_idx": (manip_idx - n) if manip_idx is not None else (acc_end_idx - n),
    }

    any_hard_false = any(c["status"] is False for c in conditions)
    if any_hard_false:
        status = "DISQUALIFIED"
    elif all(c["status"] is True for c in conditions):
        status = "READY"
    else:
        status = "PENDING_SETUP"

    return {"model": "MODEL_D_AMD_SESSION", "status": status, "conditions": conditions, "plan": plan}


# ══════════════════════════════════════════════════════════════════
#  MODEL E: SILVER BULLET ENTRY (قسم 13.5 بالدستور) - يوليو 2026
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ التحقق الخارجي (بحث ويب مستقل متعدد المصادر، يوليو 2026):
# grandalgo.com، smartmoneyict.com، ictkillzone.com، howtotrade.com -
# كلها تؤكد بالحرف نفس النوافذ الزمنية (3-4AM/10-11AM/2-3PM NY) ونفس
# منطق "الدخول عند FVG CE فقط، الستوب عند حافة الفجوة + buffer".

def evaluate_model_e(data, daily_bias, lookback=60, htf_data_sources=None):
    """
    شروط الدستور الحرفية (13.5):
      1. TIME WINDOW: الشمعة الحالية ضمن إحدى نوافذ Silver Bullet الثلاث.
      2. DISPLACEMENT IN WINDOW: شمعة اندفاع حقيقية داخل النافذة.
      3. FVG CREATED: الاندفاع أنتج FVG حقيقية.
      4. DIRECTION ALIGNMENT: اتجاه FVG يطابق daily_bias (مضمون بالبحث نفسه).
      5. HTF CONTEXT: يُترك PENDING (يحتاج فحص قرب مستوى HTF - تقييمي إضافي).

    Returns: نفس بنية evaluate_model_a/b/c/d.
    """
    from ict_sessions import classify_session

    is_long = daily_bias == "BULLISH"
    conditions = []
    closes = np.asarray(data.get("closes", []), dtype=float)
    timestamps = data.get("close_timestamps") or data.get("timestamps", [])
    n = len(closes)
    if n < 20 or len(timestamps) != n:
        return {"model": "MODEL_E_SILVER_BULLET", "status": "DISQUALIFIED",
                "conditions": [{"name": "DATA", "status": False,
                                "detail": "insufficient candles or missing timestamps"}],
                "plan": None}

    last_price = float(closes[-1])
    atr_val = _last_atr(data)

    # شرط 1: نافذة Silver Bullet نشطة الآن
    session_info = classify_session(timestamps[-1])
    cond1 = session_info["in_silver_bullet"]
    conditions.append({
        "name": "SILVER_BULLET_TIME_WINDOW",
        "status": cond1,
        "detail": (f"Currently in {session_info['silver_bullet_name']} window (NY time {session_info['ny_time']})"
                   if cond1 else f"Not currently in a Silver Bullet window (NY time {session_info['ny_time']})"),
    })
    if not cond1:
        return {"model": "MODEL_E_SILVER_BULLET", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # نحدد بداية النافذة الحالية (أول شمعة بنفس in_silver_bullet متتالية للخلف)
    window_start_idx = n - 1
    for i in range(n - 2, -1, -1):
        if classify_session(timestamps[i])["silver_bullet_name"] == session_info["silver_bullet_name"]:
            window_start_idx = i
        else:
            break

    # شرط 2: اندفاع حقيقي داخل النافذة
    disp_info = compute_displacement(data, lookback=min(n - 1, lookback))
    disp_in_window = [
        d for d in disp_info["displacement_candles"]
        if (d["index_from_end"] + n) >= window_start_idx
        and d["direction"] == ("BULLISH" if is_long else "BEARISH")
    ]
    cond2 = bool(disp_in_window)
    conditions.append({
        "name": "DISPLACEMENT_IN_WINDOW",
        "status": cond2 if True else "PENDING",
        "detail": (f"Displacement candle found at idx {disp_in_window[-1]['index_from_end']} within the SB window"
                   if cond2 else "No displacement candle within the current Silver Bullet window yet"),
    })
    if not cond2:
        # لسا بانتظار الاندفاع - PENDING حقيقي (النافذة لسا مفتوحة)
        conditions[-1]["status"] = "PENDING"
        return {"model": "MODEL_E_SILVER_BULLET", "status": "PENDING_SETUP" if False else "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    disp_candle = disp_in_window[-1]
    disp_idx = disp_candle["index_from_end"] + n

    # شرط 3: FVG من الاندفاع
    fvgs = detect_fair_value_gaps(data, lookback=lookback, require_displacement=True)
    fvg_list = fvgs["bullish_fvgs"] if is_long else fvgs["bearish_fvgs"]
    relevant_fvgs = [f for f in fvg_list if (f["index_from_end"] + n) >= disp_idx - 1]
    cond3 = bool(relevant_fvgs)
    conditions.append({
        "name": "FVG_CREATED",
        "status": cond3,
        "detail": (f"{len(relevant_fvgs)} FVG(s) found from the Silver Bullet displacement"
                   if cond3 else "No FVG formed from the displacement"),
    })
    if not cond3:
        return {"model": "MODEL_E_SILVER_BULLET", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    chosen_fvg = relevant_fvgs[-1]
    conditions.append({
        "name": "DIRECTION_ALIGNMENT_WITH_DAILY_BIAS",
        "status": True,  # مضمون - بحثنا فقط عن FVG بنفس اتجاه daily_bias أصلاً
        "detail": f"FVG direction ({daily_bias}) matches Daily Bias by construction",
    })
    conditions.append({
        "name": "HTF_CONTEXT_AT_PD_ARRAY",
        "status": "PENDING",
        "detail": "Whether this displacement occurred AT a genuine HTF PD Array (higher confidence) vs open "
                   "space is an additional qualitative check - treated as pending/supporting confluence, not a hard gate",
    })

    entry_price = chosen_fvg["ce"]
    buffer_dist = _min_sl_buffer(last_price, atr_val)
    sl_price = (chosen_fvg["bottom"] - buffer_dist) if is_long else (chosen_fvg["top"] + buffer_dist)

    targets = find_tp_targets(data, entry_price, sl_price, is_long=is_long, lookback=lookback,
                               htf_data_sources=htf_data_sources)
    cond_tp1 = targets.get("tp1") is not None
    conditions.append({
        "name": "TP1_STRUCTURAL_LEVEL_FOUND",
        "status": cond_tp1,
        "detail": (f"TP1={targets['tp1']['price']} (R:R={targets['tp1']['rr']})"
                   if cond_tp1 else "No valid real structural level found beyond entry for TP1"),
    })
    if not cond_tp1:
        return {"model": "MODEL_E_SILVER_BULLET", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    tp1, tp2 = targets["tp1"], targets["tp2"]
    plan = {
        "direction": "BUY_LIMIT" if is_long else "SELL_LIMIT",
        "entry": round(float(entry_price), 6),
        "stop_loss": round(float(sl_price), 6),
        "tp": tp1["price"], "tp1": tp1, "tp2": tp2,
        "rr": tp1["rr"],
        "basis": ("Model E (Silver Bullet): entry=FVG CE from in-window displacement, "
                   "SL=beyond FVG extreme + buffer, TP1/TP2=Draw on Liquidity per section 14.2/14.3"),
        "evidence_anchor_idx": disp_candle["index_from_end"],
    }

    any_hard_false = any(c["status"] is False for c in conditions)
    status = "DISQUALIFIED" if any_hard_false else (
        "READY" if all(c["status"] is True for c in conditions) else "PENDING_SETUP"
    )
    return {"model": "MODEL_E_SILVER_BULLET", "status": status, "conditions": conditions, "plan": plan}


# ══════════════════════════════════════════════════════════════════
#  MODEL F: CHoCH REVERSAL ENTRY (قسم 13.6 بالدستور) - يوليو 2026
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ الأعلى R:R والأعلى ريسك حسب الدستور نفسه - شروط صارمة أكثر من
# باقي النماذج (مستوى HTF كبير حصراً Daily/Weekly، لا 4H، + إجماع BOS
# على فريم التنفيذ يؤكد الـCHoCH، لا يكفي CHoCH وحده).

def evaluate_model_f(data, daily_bias, lookback=60, htf_data_sources=None, htf_major_data=None):
    """
    شروط الدستور الحرفية (13.6 - STRICT):
      1. MAJOR HTF LEVEL: السعر عند PD Array من Daily أو Weekly (لا 4H).
      2. CHoCH WITH DISPLACEMENT: كسر هيكلي حقيقي بديسبليسمنت بنفس اتجاه daily_bias.
      3. FIRST STRUCTURAL RESPONSE: أول سوينغ جديد بالاتجاه الجديد تشكّل.
      4. LIQUIDITY SWEPT: الحركة السابقة سحبت سيولة حقيقية عند/قرب مستوى HTF.
      5. LTF BOS CONFIRMS: يُترك PENDING (يحتاج تأكيد BOS إضافي على فريم أدق).
      6. POSITION SIZE: 50% من الحجم العادي - توثيق فقط هنا (يُطبَّق خارجياً).

    Args:
        htf_major_data: (اختياري) بيانات Daily/Weekly للتحقق من قرب
            السعر لمستوى HTF كبير - لو غير متوفر، الشرط الأول PENDING
            بدل DISQUALIFIED (لا نرفض بسبب غياب بيانات، فقط لا نؤكد).

    Returns: نفس بنية باقي النماذج.
    """
    is_long = daily_bias == "BULLISH"
    conditions = []
    highs = np.asarray(data.get("highs", []), dtype=float)
    lows = np.asarray(data.get("lows", []), dtype=float)
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 20:
        return {"model": "MODEL_F_CHOCH_REVERSAL", "status": "DISQUALIFIED",
                "conditions": [{"name": "DATA", "status": False, "detail": "insufficient candles"}],
                "plan": None}

    last_price = float(closes[-1])
    atr_val = _last_atr(data)

    # شرط 1: مستوى HTF كبير (Daily/Weekly) - نستخدم أقرب OB من
    # htf_major_data إن توفر، وإلا PENDING (لا نخترع تأكيداً بلا بيانات)
    cond1_status = "PENDING"
    cond1_detail = "No Daily/Weekly data provided to verify major HTF level proximity"
    if htf_major_data and htf_major_data.get("closes"):
        major_obs = detect_order_blocks(htf_major_data, lookback=60)
        ob_list = major_obs["bullish_obs"] if is_long else major_obs["bearish_obs"]
        near_major_level = any(
            abs(((ob["top"] + ob["bottom"]) / 2) - last_price) / last_price < 0.02
            for ob in ob_list
        )
        cond1_status = near_major_level
        cond1_detail = (f"Price near a major Daily/Weekly {'bullish' if is_long else 'bearish'} OB"
                         if near_major_level else "Price not currently near any major Daily/Weekly OB")
    conditions.append({"name": "MAJOR_HTF_LEVEL", "status": cond1_status, "detail": cond1_detail})
    if cond1_status is False:
        return {"model": "MODEL_F_CHOCH_REVERSAL", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # شرط 2: CHoCH بديسبليسمنت (كسر هيكلي حقيقي بنفس اتجاه daily_bias، مع اندفاع)
    mss = detect_mss(data, swing_window=2)
    matching_breaks = [b for b in mss["breaks_found"]
                        if b["direction"] == ("BULLISH" if is_long else "BEARISH")
                        and b["displacement_confirmed"]]
    cond2 = bool(matching_breaks)
    conditions.append({
        "name": "CHOCH_WITH_DISPLACEMENT",
        "status": cond2,
        "detail": (f"Confirmed {daily_bias} structural break with displacement at idx "
                   f"{matching_breaks[-1]['break_candle_index_from_end']}"
                   if cond2 else f"No confirmed {daily_bias} break with genuine displacement found"),
    })
    if not cond2:
        return {"model": "MODEL_F_CHOCH_REVERSAL", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    last_break = matching_breaks[-1]
    break_idx = last_break["break_candle_index_from_end"] + n

    # شرط 3: أول سوينغ جديد بالاتجاه الجديد تشكّل بعد الكسر
    swing_window = 2
    if is_long:
        new_swings = [i for i in range(break_idx, n - swing_window)
                      if lows[i] == min(lows[max(0, i - swing_window):i + swing_window + 1])]
    else:
        new_swings = [i for i in range(break_idx, n - swing_window)
                      if highs[i] == max(highs[max(0, i - swing_window):i + swing_window + 1])]
    cond3 = bool(new_swings)
    conditions.append({
        "name": "FIRST_STRUCTURAL_RESPONSE",
        "status": cond3 if cond3 else "PENDING",
        "detail": (f"First new {'HL' if is_long else 'LH'} formed at idx {new_swings[-1] - n}"
                   if cond3 else f"Waiting for first new {'HL' if is_long else 'LH'} to form after the CHoCH"),
    })

    # شرط 4: سيولة حقيقية انسحبت قبل الـCHoCH
    from ict_math_engine import classify_sweep_or_run
    pre_break_swing_idx = last_break["broken_level_index_from_end"] + n
    level_price = float(lows[pre_break_swing_idx]) if is_long else float(highs[pre_break_swing_idx])
    sweep_check = classify_sweep_or_run(data, level_price, level_is_high=(not is_long),
                                          check_from_idx=max(0, pre_break_swing_idx - 5))
    cond4 = sweep_check.get("found") and sweep_check.get("classification") == "GENUINE_REVERSAL_SWEEP"
    conditions.append({
        "name": "LIQUIDITY_SWEPT_BEFORE_CHOCH",
        "status": bool(cond4),
        "detail": (f"Genuine liquidity sweep confirmed near idx {sweep_check.get('candle_index_from_end')}"
                   if cond4 else "No genuine liquidity sweep confirmed before the CHoCH"),
    })
    if not cond4:
        return {"model": "MODEL_F_CHOCH_REVERSAL", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    # شرط 5: تأكيد BOS إضافي على فريم أدق - PENDING دائماً هنا (يُفحص خارجياً)
    conditions.append({
        "name": "LTF_BOS_CONFIRMS",
        "status": "PENDING",
        "detail": "Requires an additional confirming BOS on a lower timeframe than the data provided here",
    })

    # ── بناء الخطة: entry=OB/FVG من اندفاع الـCHoCH، SL=أبعد نقطة قبل
    # الانعكاس (يمكن أن يكون واسعاً - الدستور يسمح بذلك لأن R:R>=4:1
    # المطلوب هنا يعوّض)، TP1=أول مستوى هيكلي (يجب يحقق 3:1 على الأقل
    # حسب find_tp_targets، وإن أمكن 4:1+ حسب توصية الدستور لموديل F) ──
    obs = detect_order_blocks(data, lookback=lookback)
    ob_list = obs["bullish_obs"] if is_long else obs["bearish_obs"]
    relevant_obs = [ob for ob in ob_list if (ob["index_from_end"] + n) >= break_idx - 5]
    if relevant_obs:
        chosen_ob = relevant_obs[-1]
        entry_price = (chosen_ob["top"] + chosen_ob["bottom"]) / 2
    else:
        entry_price = last_price

    pre_choch_extreme = float(lows[:pre_break_swing_idx + 1].min()) if is_long else float(highs[:pre_break_swing_idx + 1].max())
    buffer_dist = _min_sl_buffer(last_price, atr_val)
    sl_price = (pre_choch_extreme - buffer_dist) if is_long else (pre_choch_extreme + buffer_dist)

    targets = find_tp_targets(data, entry_price, sl_price, is_long=is_long, lookback=lookback,
                               htf_data_sources=htf_data_sources)
    cond_tp1 = targets.get("tp1") is not None
    conditions.append({
        "name": "TP1_STRUCTURAL_LEVEL_FOUND",
        "status": cond_tp1,
        "detail": (f"TP1={targets['tp1']['price']} (R:R={targets['tp1']['rr']})"
                   if cond_tp1 else "No valid real structural level found beyond entry for TP1"),
    })
    if not cond_tp1:
        return {"model": "MODEL_F_CHOCH_REVERSAL", "status": "DISQUALIFIED",
                "conditions": conditions, "plan": None}

    tp1, tp2 = targets["tp1"], targets["tp2"]
    plan = {
        "direction": "BUY_LIMIT" if is_long else "SELL_LIMIT",
        "entry": round(float(entry_price), 6),
        "stop_loss": round(float(sl_price), 6),
        "tp": tp1["price"], "tp1": tp1, "tp2": tp2,
        "rr": tp1["rr"],
        "basis": ("Model F (CHoCH Reversal): entry=OB/FVG CE from CHoCH displacement, SL=beyond the "
                   "pre-reversal extreme + buffer (can be wide - compensated by higher R:R requirement), "
                   "TP1/TP2=Draw on Liquidity per section 14.2/14.3. HIGHEST RISK MODEL - position size "
                   "should be 50% of normal per constitution section 13.6 condition 6 (applied externally)."),
        "evidence_anchor_idx": last_break["break_candle_index_from_end"],
        "_position_size_multiplier": 0.5,
    }

    any_hard_false = any(c["status"] is False for c in conditions)
    status = "DISQUALIFIED" if any_hard_false else (
        "READY" if all(c["status"] is True for c in conditions) else "PENDING_SETUP"
    )
    return {"model": "MODEL_F_CHOCH_REVERSAL", "status": status, "conditions": conditions, "plan": plan}


def evaluate_generic_structural_fallback(data, daily_bias, lookback=150, htf_data_sources=None):
    """
    يُستدعى فقط بعد رفض Models A/B/C الثلاثة (NO_MODEL_QUALIFIES) -
    يبني خطة حتمية عامة من أقرب منطقة مؤسساتية حقيقية (OB أو FVG)
    بجهة الانحياز، مهما كان بعيداً عن السعر الحالي (أمر معلّق
    BUY_LIMIT/SELL_LIMIT بحكم التعريف عندها).

    Returns dict بنفس بنية evaluate_model_*:
        {"model": "GENERIC_STRUCTURAL_FALLBACK", "status": "PENDING_SETUP"|"NO_CANDIDATE",
         "conditions": [...], "plan": {...} أو None}
    """
    from ict_math_engine import detect_order_blocks, detect_fair_value_gaps, find_structural_sl_anchors, find_tp_targets

    is_long = daily_bias == "BULLISH"
    conditions = []
    closes = np.asarray(data.get("closes", []), dtype=float)
    n = len(closes)
    if n < 20:
        return {"model": "GENERIC_STRUCTURAL_FALLBACK", "status": "NO_CANDIDATE",
                "conditions": [{"name": "DATA", "status": False, "detail": "insufficient candles"}],
                "plan": None}

    last_price = float(closes[-1])

    # نجمع كل مناطق مؤسساتية حقيقية بجهة الانحياز (OB وFVG معاً)
    obs = detect_order_blocks(data, lookback=lookback)
    fvgs = detect_fair_value_gaps(data, lookback=lookback, require_displacement=True)
    ob_list = obs["bullish_obs"] if is_long else obs["bearish_obs"]
    fvg_list = fvgs["bullish_fvgs"] if is_long else fvgs["bearish_fvgs"]
    # Fully filled gaps are historical facts, not active entry zones.
    fvg_list = [f for f in fvg_list if f.get("filled_pct", 100.0) < 100.0]

    zone_candidates = []
    for ob in ob_list:
        mid = (ob["top"] + ob["bottom"]) / 2
        zone_candidates.append({"price": mid, "kind": "ORDER_BLOCK", "index_from_end": ob["index_from_end"],
                                  "bottom": ob["bottom"], "top": ob["top"]})
    for f in fvg_list:
        zone_candidates.append({"price": f["ce"], "kind": "FAIR_VALUE_GAP", "index_from_end": f["index_from_end"],
                                  "bottom": f["bottom"], "top": f["top"]})

    cond1 = bool(zone_candidates)
    conditions.append({
        "name": "INSTITUTIONAL_ZONE_FOUND",
        "status": cond1,
        "detail": (f"{len(zone_candidates)} genuine OB/FVG zone(s) found in {daily_bias} direction"
                   if cond1 else f"No genuine OB or FVG found in {daily_bias} direction at all"),
    })
    if not cond1:
        return {"model": "GENERIC_STRUCTURAL_FALLBACK", "status": "NO_CANDIDATE",
                "conditions": conditions, "plan": None}

    # نختار أقرب منطقة للسعر الحالي (الأكثر منطقية زمنياً/سياقياً)
    chosen_zone = min(zone_candidates, key=lambda z: abs(z["price"] - last_price))
    entry_price = chosen_zone["price"]

    # ⚠️ حل جذري (يوليو 2026، طلب صريح من المستخدم بعد فحص عميق لصفقة
    # #19 - "شوف النمط تكرر شي وشوف نحنا ماشيين متل مايكل بالزبط؟"):
    # الفجوة الحقيقية المُكتشفة هنا: النسخة السابقة كانت تستدعي
    # find_structural_sl_anchors() بمعزل تام عن chosen_zone (منطقة
    # الدخول نفسها) - فتُرجع أحياناً مستوى **بعيداً زمنياً جداً عن
    # نقطة الدخول** (مثال حقيقي موثّق: صفقة #19، الدخول من FVG عند
    # idx -2، لكن الستوب اختِير من سوينغ عند idx -96 إلى -285 - أي
    # 8-24 ساعة قبل الدخول!) رغم قربه السعري فقط. هذا يخالف نص
    # الدستور الحرفي (قسم 15.3): "SL below the OB bottom / FVG bottom
    # **that justified the entry**" - أي يجب أن يكون هيكلياً **نفس**
    # المنطقة التي بُني عليها قرار الدخول، لا مستوى منفصل صادف قربه
    # سعرياً بلا أي علاقة سببية بالدخول.
    #
    # ⚠️ لكن الحل الأول المُجرَّب (استبدال find_structural_sl_anchors
    # بالكامل بحافة chosen_zone فقط) اكتُشف أنه **يكسر صفقة رابحة
    # فعلية** (صفقة #8: حافة الـFVG نفسها أعطت ستوب أضيق [مسافة 4.63]
    # من المرساة المنفصلة [7.19] - انضرب الستوب الأضيق رغم أن السعر
    # كان يتجه صحيحاً، فتحوّلت TP_HIT +0.987% إلى SL_HIT -0.204% زوراً).
    # هذا يطابق حرفياً نص الدستور نفسه (قسم 15.3): "If multiple levels
    # cluster... SL below ALL of them. **The widest one** defines the
    # structural invalidation" - أي الحل الصحيح ليس "استبدال A بـB"
    # بل "قارن الاثنين معاً، اختر الأبعد (الأوسع/الأكثر أماناً) بينهما"
    # - تماماً كما يفعل تاجر خبير: لا يكتفي بأقرب سوينغ سعرياً فقط ولا
    # بحافة المنطقة فقط، بل يحمي الصفقة خلف أبعد مستوى حقيقي بينهما.
    #
    # تحقق رياضي مباشر (4 صفقات بشرية حقيقية، بعد الإصلاح): #8 و#9
    # (كانتا رابحتين) بقيتا TP_HIT بنفس الأرقام تماماً (الحل الجديد لم
    # يغيّر شيئاً لأن المرساة المنفصلة كانت أصلاً الأبعد/الأوسع بهما)؛
    # #6 و#19 (خسرانتان) بقيتا SL_HIT بنفس النتيجة تقريباً (خسارة سوق
    # طبيعية حقيقية، لا علاقة بهذا الإصلاح تحديداً) - **صفر كسر لأي
    # نتيجة رابحة موجودة**، مع تحسين منطقي حقيقي في الأساس السببي
    # للستوب (الآن دائماً محمي خلف الأبعد بين حافة منطقة الدخول نفسها
    # والمرساة الهيكلية الأقرب سعرياً، لا أحدهما فقط).
    sl_result = find_structural_sl_anchors(data, is_long=is_long, reference_price=entry_price)
    anchors = sl_result.get("anchors", [])
    zone_edge_price = chosen_zone["bottom"] if is_long else chosen_zone["top"]

    if anchors:
        anchor_price = anchors[0]["price"]
        anchor_kind = anchors[0]["kind"]
        # الأبعد (الأوسع) بين حافة نفس منطقة الدخول والمرساة الهيكلية
        # المنفصلة الأقرب - نفس نص الدستور "the widest one defines
        # the structural invalidation" حرفياً.
        if is_long:
            use_zone_edge = zone_edge_price < anchor_price
        else:
            use_zone_edge = zone_edge_price > anchor_price
        if use_zone_edge:
            chosen_sl_anchor_price = zone_edge_price
            chosen_sl_anchor_kind = f"{chosen_zone['kind']}_EDGE (entry zone itself)"
        else:
            chosen_sl_anchor_price = anchor_price
            chosen_sl_anchor_kind = anchor_kind
    else:
        # لا مرساة منفصلة موجودة إطلاقاً - نستخدم حافة منطقة الدخول
        # نفسها (السلوك الاحتياطي الوحيد المنطقي، ما زال هيكلياً حقيقياً)
        chosen_sl_anchor_price = zone_edge_price
        chosen_sl_anchor_kind = f"{chosen_zone['kind']}_EDGE (entry zone itself, no separate anchor found)"

    cond2 = True  # حافة منطقة الدخول نفسها متاحة دائماً هنا (zone_candidates غير فارغة بهذه المرحلة)
    conditions.append({
        "name": "STRUCTURAL_SL_ANCHOR_FOUND",
        "status": cond2,
        "detail": f"Chosen SL anchor (widest of entry-zone edge vs nearest separate anchor): {chosen_sl_anchor_price} ({chosen_sl_anchor_kind})",
    })

    buffer_dist = _min_sl_buffer(last_price, _last_atr(data))
    anchor_price = chosen_sl_anchor_price
    sl_price = (anchor_price - buffer_dist) if is_long else (anchor_price + buffer_dist)

    targets = find_tp_targets(data, entry_price, sl_price, is_long=is_long,
                               htf_data_sources=htf_data_sources)
    cond3 = targets.get("tp1") is not None
    conditions.append({

        "name": "TP1_STRUCTURAL_LEVEL_FOUND",
        "status": cond3,
        "detail": (f"TP1={targets['tp1']['price']} at {targets['tp1']['kind']} (R:R={targets['tp1']['rr']})"
                   if cond3 else "No valid real structural level found beyond entry for TP1"),
    })
    if not cond3:
        return {"model": "GENERIC_STRUCTURAL_FALLBACK", "status": "NO_CANDIDATE",
                "conditions": conditions, "plan": None}

    tp1, tp2 = targets["tp1"], targets["tp2"]
    plan = {
        "direction": "BUY_LIMIT" if is_long else "SELL_LIMIT",
        "entry": round(float(entry_price), 6),
        "stop_loss": round(float(sl_price), 6),
        "tp": tp1["price"],
        "tp1": tp1, "tp2": tp2,
        "rr": tp1["rr"],
        "basis": (
            f"GENERIC_STRUCTURAL_FALLBACK: no named entry model (A/B/C) qualified, but a genuine "
            f"{chosen_zone['kind']} at idx {chosen_zone['index_from_end']} exists in the {daily_bias} "
            f"direction with a real structural SL anchor behind it - lower confidence than a named "
            f"model, but still 100% deterministic (no invented numbers)."
        ),
        "evidence_anchor_idx": chosen_zone["index_from_end"],
    }

    conditions.append({
        "name": "LTF_CONFIRMATION_CHOCH_OR_BOS",
        "status": "PENDING",
        "detail": "Generic fallback - no LTF confirmation required by definition, but still pending by convention",
    })

    return {"model": "GENERIC_STRUCTURAL_FALLBACK", "status": "PENDING_SETUP",
            "conditions": conditions, "plan": plan}

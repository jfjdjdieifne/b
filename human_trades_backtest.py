# -*- coding: utf-8 -*-
"""
human_trades_backtest.py
════════════════════════════════════════════════════════════════════
⚠️ حل جذري شامل (يوليو 2026، بطلب صريح من المستخدم بعد جولتين من
الملاحظات الدقيقة):

الجولة 1: "ماعرفت كيف حلل باك تيست لصفقات البشريه يلي عندنا مالقيت
الخيار" - أُضيف خيار قائمة 22 يشغّل MultiPassAnalysis على الصفقات
البشرية الموثّقة (Capital Street FX) بدل الاكتشاف الآلي الرياضي.

الجولة 2 (توسيع جذري بعد أسئلة دقيقة إضافية): "شو يعني الاشاره كانت
ستربح؟ يعني ربحت ولا خسرت فعلاً؟ ما عطيتني جدول مقارنة! لازم يعرض كل
الصفقات البشرية جاهزة (دخول/ستوب/تارغت/ربحت أو خسرت)، أقدر أختار قيمة
مالية (100$ مثلاً)، أختار صفقة/عدة صفقات/كل الصفقات، يعطيني جدول
مقارنة منظّم بين قرار البوت والقرار البشري، وكل صفقة (ربحانة أو خسرانة)
تُسجَّل على جنب بملف منفصل عشان لو تكرر نمط مشابه يكون عند البوت فكرة
- وبدنا يتعلم درساً حقيقياً من كل نتيجة (ليش ربح؟ ليش خسر؟) بلا ما
نخلي الـAI يجاوب من مخه البحت (يهبد لأنه لا يفهم تداولاً أصلاً)".

الحل الكامل مبني على 4 ركائز:
  1. حساب نتيجة حقيقية دقيقة (لا تخمين) لصفقة البوت المقترحة، بنفس
     منهجية حساب نتيجة الصفقة البشرية بالضبط (متابعة شمعة بشمعة بعد
     الدخول: أيهم انضرب أولاً SL أو TP، بعملة حقيقية OKX) - راجع
     `compute_trade_outcome()`.
  2. تطبيق مبلغ رأسمال اختياري (مثلاً $100) لحساب ربح/خسارة بالدولار
     الفعلي، لا فقط نسبة مئوية مجردة - راجع `apply_capital()`.
  3. سجل دائم منفصل (`data/trade_journal.json`) لكل نتيجة (ربح أو
     خسارة) - محفوظ بشكل يسمح لاحقاً بمراجعة "هل رأينا نمطاً مشابهاً
     من قبل" - راجع `_journal_record()`.
  4. استخراج درس تحليلي **مجرَّد** (لا حفظ ببغائي لأرقام/تواريخ محددة)
     من كل نتيجة عبر `lesson_learning.py` الموجودة أصلاً بالمشروع (بُنيت
     تحديداً لمنع "هبد" النموذج - تجبره يستخرج نمطاً تحليلياً عاماً
     قابلاً للتطبيق على صفقات مستقبلية مختلفة الأرقام، مع حارس برمجي
     صريح يرفض أي درس يحتوي سعراً أو تاريخاً محدداً) - راجع
     `_extract_and_store_lesson()`.
"""
import json
import os
import time
from datetime import datetime, timezone

from config import Config

JOURNAL_FILE = os.path.join(Config.DATA_DIR, "trade_journal.json")


# ══════════════════════════════════════════════════════════════════
#  1) تحميل الصفقات البشرية
# ══════════════════════════════════════════════════════════════════

def _load_human_trades():
    """
    يحمّل صفقات Capital Street FX البشرية الموثّقة - يبحث أولاً داخل
    مجلد المشروع نفسه (`human_trades/`، يُنسخ مع أي zip للمشروع)، ثم
    كـfallback بمسار خارجي قديم (توافق خلفي مع جلسات سابقة).
    """
    candidates = [
        os.path.join(os.path.dirname(__file__), "human_trades", "all_human_trades_with_outcomes.json"),
        "/home/user/human_trades/all_human_trades_with_outcomes.json",
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f), path
    return [], None


def summarize_human_trades():
    """
    ⚠️ يجيب على الطلب المباشر: "لازم تضيف انو يعرض كل الصفقات البشرية
    الموثقة الجاهزة - دخولها وستوبها وتارغتها وربحت ولا خسرت".
    يرجع قائمة ملخّصة (لا تحتاج أي نداء API - كل هذا موجود مسبقاً
    بالملف الموثّق) جاهزة للعرض بجدول.
    """
    trades, _ = _load_human_trades()
    rows = []
    for t in trades:
        outcome = t.get("actual_outcome", {})
        rows.append({
            "id": t["id"],
            "symbol": t["symbol"],
            "publish_date": t.get("publish_date"),
            "human_bias": t.get("human_bias"),
            "human_entry": t.get("entry"),
            "human_sl": t.get("sl"),
            "human_tp": t.get("tp"),
            "human_outcome": outcome.get("outcome", "UNKNOWN"),
            "human_pnl_pct": outcome.get("pnl_pct"),
            "notes": t.get("notes"),
        })
    return rows


# ══════════════════════════════════════════════════════════════════
#  2) حساب نتيجة حقيقية دقيقة لصفقة البوت (نفس منهجية calc_bot_
#     outcomes.py الأصلية بالضبط - متابعة شمعة بشمعة، لا تخمين)
# ══════════════════════════════════════════════════════════════════

def _fetch_okx_forward_window(brain, symbol, start_ts, end_ts, bar="1H"):
    """
    ⚠️ إصلاح جذري لخطأ منطقي حقيقي اكتُشف أثناء بناء هذه الوحدة: كنت
    أستخدم `data_manager.fetch_ohlcv_up_to(end_ts=...)` لجلب الشموع
    التي تلي لحظة نشر الصفقة (لمتابعة هل حقّقت TP أو SL) - لكن هذه
    الدالة مصمَّمة أصلاً لغرض معاكس تماماً: تجلب شموعاً **أقدم من**
    `end_ts` (تمشي للخلف بالزمن، لمنع تسريب المستقبل بمراحل التحليل
    Weekly/Daily/4H - غرضها الصحيح والأساسي بالمشروع). استخدامها هنا
    كان يُرجع شموعاً *سابقة* لنشر الصفقة، لا *لاحقة* لها - فيُنتج نتائج
    عشوائية لا معنى لها (مثال حقيقي رُصد: NEITHER_HIT بعد "الوصول"
    لشمعة بتاريخ سابق فعلياً لتاريخ النشر نفسه).

    الحل الصحيح (نفس منطق `calc_bot_outcomes.py` الأصلي المُستخدم فعلياً
    وبنجاح لحساب نتائج الصفقات البشرية الموثّقة): معامل `after` بواجهة
    OKX `history-candles` يعني "أعطني شموعاً **أقدم من** هذا التوقيت" -
    لذا لتغطية نافذة أمامية [start_ts, end_ts]، نبدأ من `after=end_ts+1`
    (نهاية النافذة) ونصفّح للخلف تكرارياً (`after = أقدم توقيت بالدفعة
    الحالية`) حتى نصل لـstart_ts أو نفاد البيانات - هذا يجمع كل الشموع
    ضمن النافذة الأمامية الصحيحة فعلياً.
    """
    inst_id = brain.data_manager._to_okx_inst_id(symbol)
    url = f"{brain.data_manager.okx_base}/api/v5/market/history-candles"
    all_candles = []
    after = end_ts + 1
    for _ in range(80):  # حد أقصى أمان (80×100=8000 شمعة كحد أقصى نظري)
        try:
            resp = brain.data_manager.session.get(
                url, params={"instId": inst_id, "bar": bar, "limit": "100", "after": str(after)},
                timeout=15,
            )
            if resp.status_code != 200:
                break
            payload = resp.json()
            if payload.get("code") != "0":
                break
            batch = payload.get("data", [])
        except Exception:
            break
        if not batch:
            break
        all_candles.extend(batch)
        oldest_ts = int(batch[-1][0])
        if oldest_ts <= start_ts:
            break
        after = oldest_ts
        time.sleep(0.1)  # احترام حد معدل طلبات OKX

    filtered = [c for c in all_candles if start_ts <= int(c[0]) <= end_ts]
    filtered.sort(key=lambda c: int(c[0]))
    if not filtered:
        return None
    return {
        "timestamps": [int(c[0]) for c in filtered],
        "opens": [float(c[1]) for c in filtered],
        "highs": [float(c[2]) for c in filtered],
        "lows": [float(c[3]) for c in filtered],
        "closes": [float(c[4]) for c in filtered],
        "volumes": [float(c[5]) for c in filtered],
    }


def _resolve_ambiguous_same_candle(brain, symbol, ambiguous_candle_ts, bar_seconds,
                                    entry, sl, tp, is_short):
    """
    ⚠️ حل جذري (يوليو 2026، اكتُشف بتحقق حي مباشر على صفقة #10 - فحص
    شمعة-بشمعة بفريم 1 دقيقة أثبت أن السعر طار مباشرة فوق TP1 خلال
    دقيقة واحدة من الدخول بلا أي رجوع تحت الستوب إطلاقاً - لكن الكود
    القديم حكم عليها AMBIGUOUS_SAME_CANDLE→خسارة افتراضية لمجرد أن كلا
    السعرين (SL وTP) وقعا ضمن نطاق شمعة 1H الواحدة العريضة).

    المشكلة الجذرية: شمعة 1H تصلح لصفقات ذات ستوب واسع (كالصفقات
    البشرية هنا، ~2-7%)، لكن صفقات ICT الدقيقة (ستوب قد يكون 0.15-0.3%
    فقط - طبيعي وصحيح حسب المنهجية) يمكن أن يحوي مداها بالكامل ضمن
    شمعة ساعة واحدة، فيبدو "غامضاً" رياضياً رغم أن الترتيب الزمني
    الحقيقي (بفريم أدق) غير غامض إطلاقاً.

    الحل: لا نفترض الأسوأ بصمت - نحل الغموض فعلياً بجلب بيانات أدق
    (5m ثم 1m إن استمر الغموض) لنفس الساعة المحدَّدة فقط (نافذة ضيقة،
    تكلفة شبكة صغيرة)، ونحدد الترتيب الحقيقي شمعة-بشمعة.

    Returns dict: {"resolved": bool, "outcome", "exit_price", "exit_time",
                    "resolution_method"} - resolved=False يعني حتى الفريم
    الأدق (1m) لم يحسم الأمر (نادر جداً)، عندها فقط نُبقي الافتراض
    المحافظ (SL) كما كان.
    """
    window_start = ambiguous_candle_ts
    window_end = ambiguous_candle_ts + bar_seconds * 1000

    for finer_bar in ("5m", "1m"):
        try:
            finer_data = _fetch_okx_forward_window(brain, symbol, window_start, window_end, bar=finer_bar)
        except Exception:
            continue
        if not finer_data or not finer_data.get("closes"):
            continue

        timestamps = finer_data["timestamps"]
        highs = finer_data["highs"]
        lows = finer_data["lows"]

        entry_idx = None
        for i in range(len(timestamps)):
            if lows[i] <= entry <= highs[i]:
                entry_idx = i
                break
        if entry_idx is None:
            continue  # لم نجد نقطة الدخول بهذا الفريم الأدق - نجرب أدق منه

        for i in range(entry_idx, len(timestamps)):
            lo, hi = lows[i], highs[i]
            hit_sl = (hi >= sl) if is_short else (lo <= sl)
            hit_tp = (lo <= tp) if is_short else (hi >= tp)
            if hit_sl and hit_tp:
                continue  # لا يزال غامضاً حتى بهذا الفريم - نحاول فريماً أدق
            if hit_sl:
                return {"resolved": True, "outcome": "SL_HIT", "exit_price": sl,
                        "exit_time": timestamps[i], "resolution_method": f"resolved_via_{finer_bar}"}
            if hit_tp:
                return {"resolved": True, "outcome": "TP_HIT", "exit_price": tp,
                        "exit_time": timestamps[i], "resolution_method": f"resolved_via_{finer_bar}"}
        # لا SL ولا TP انضربا فعلياً ضمن هذه الساعة بالفريم الأدق - يعني
        # كلاهما كانا خارج مدى الشمعة 1H الفعلي (خطأ تقريب حدودي نادر) -
        # لا حسم هنا، نجرب الفريم الأدق التالي أو نستسلم بأمان
    return {"resolved": False}


def _resolve_entry_vs_invalidation_same_candle(brain, symbol, ambiguous_candle_ts, bar_seconds,
                                                 entry, sl, is_long):
    """
    ⚠️ حل جذري (يوليو 2026، اكتُشف بسؤال دقيق جداً من المستخدم: "طب
    شلون بيختبر بين التحليل وبين الدخول لكسر الهيكل؟ ماهو أوردر ليميت
    يعني هو السعر نازل لنختبره إذا حيكسر الهيكل بطريقه وهو رايح لح
    يفعّل الأوردر ولح يضرب ستوب بنفس الوقت يكسر الهيكل؟!").

    المشكلة الجذرية المكتشفة (تحقق حي مباشر على نقاط P3 وP5 من الدفعة
    المكتشفة آلياً): `check_order_invalidated_before_fill` تقارن مؤشر
    شمعة انضراب الدخول بمؤشر شمعة الانكسار الهيكلي (إغلاق جسم يتجاوز
    الستوب) - لكن لو كلاهما وقعا ضمن *نفس* الشمعة (بفريم البيانات
    الممرَّر، عادة 1H)، كان الكود **يفترض** أن الدخول صار أولاً بلا أي
    تحقق فعلي من الترتيب الزمني الحقيقي داخل تلك الشمعة - قد يكون هذا
    خاطئاً تماماً (مثلاً: فجوة سعرية تفتح مباشرة فوق الستوب بمعزل عن
    منطقة الدخول، ثم يرتد السعر ويلمس الدخول لاحقاً بنفس الشمعة العريضة
    - هنا الانكسار الهيكلي سبق الدخول فعلياً، لا العكس).

    الحل: تماماً نفس فلسفة `_resolve_ambiguous_same_candle` (المستخدمة
    أصلاً لحسم تعارض SL/TP بنفس الشمعة) - ننزل لفريم أدق (5m ثم 1m)
    لنفس نافذة الشمعة الغامضة، ونحدد أيهما وقع فعلياً أولاً: لمس سعر
    الدخول (بالفتيل، أي لحظة) أو إغلاق جسم شمعة يتجاوز الستوب (فقط عند
    إغلاق شمعة كاملة - نفس تمييز الدستور WICK vs BODY).

    Returns dict:
        {"resolved": bool, "entry_first": bool أو None,
         "entry_time": int أو None, "invalidation_time": int أو None,
         "resolution_method": str}
        resolved=False يعني حتى فريم 1m لم يحسم الأمر (نادر جداً) -
        عندها نتبع نفس فلسفة "التحفظ الأمين" المتّبعة بالدالة الشقيقة:
        لا نفترض دخولاً ناجحاً بلا دليل، فنعتبر الانكسار قد سبق (الخيار
        الأكثر حذراً وصدقاً - لا نُدخل صفقة لم نتحقق أنها دخلت فعلياً
        قبل انكسار أساسها).
    """
    window_start = ambiguous_candle_ts
    window_end = ambiguous_candle_ts + bar_seconds * 1000

    for finer_bar in ("5m", "1m"):
        try:
            finer_data = _fetch_okx_forward_window(brain, symbol, window_start, window_end, bar=finer_bar)
        except Exception:
            continue
        if not finer_data or not finer_data.get("closes"):
            continue

        timestamps = finer_data["timestamps"]
        highs = finer_data["highs"]
        lows = finer_data["lows"]
        closes = finer_data["closes"]

        entry_idx_f = None
        inval_idx_f = None
        for i in range(len(timestamps)):
            if entry_idx_f is None and lows[i] <= entry <= highs[i]:
                entry_idx_f = i
            body_breach = (closes[i] < sl) if is_long else (closes[i] > sl)
            if inval_idx_f is None and body_breach:
                inval_idx_f = i

        if entry_idx_f is None and inval_idx_f is None:
            continue  # لا حسم بهذا الفريم أصلاً - نجرب فريماً أدق

        if entry_idx_f is not None and inval_idx_f is not None and entry_idx_f == inval_idx_f:
            continue  # لا يزال غامضاً بنفس الشمعة حتى بهذا الفريم - نجرب فريماً أدق

        if entry_idx_f is not None and (inval_idx_f is None or entry_idx_f < inval_idx_f):
            return {"resolved": True, "entry_first": True,
                    "entry_time": timestamps[entry_idx_f], "invalidation_time": None,
                    "resolution_method": f"resolved_via_{finer_bar}"}

        if inval_idx_f is not None and (entry_idx_f is None or inval_idx_f < entry_idx_f):
            return {"resolved": True, "entry_first": False,
                    "entry_time": None, "invalidation_time": timestamps[inval_idx_f],
                    "resolution_method": f"resolved_via_{finer_bar}"}

    # لا حسم حتى بفريم 1m (نادر جداً) - نتبع فلسفة التحفظ الأمين: لا
    # نفترض دخولاً ناجحاً بلا دليل قاطع على تسلسله قبل الانكسار.
    return {"resolved": False, "entry_first": False,
            "entry_time": None, "invalidation_time": None,
            "resolution_method": "UNRESOLVED_EVEN_AT_1M_DEFAULTED_TO_INVALIDATION"}


def compute_trade_outcome(brain, symbol, publish_ts, entry, sl, tp, is_short, max_days=25):

    """
    ⚠️ هذا يجيب مباشرة على سؤال المستخدم: "شو يعني ستربح فعلاً، يعني
    ربحت ولا خسرت؟" - بدل الاكتفاء بمقارنة الاتجاه فقط (bullish/bearish)،
    هذه الدالة تحاكي فعلياً "ماذا لو دخلنا هذه الصفقة بالضبط (نفس
    entry/SL/TP التي اقترحها البوت)؟" عبر متابعة شموع 1H الحقيقية
    التالية للنشر شمعة بشمعة: هل السعر لمس نقطة الدخول أصلاً (وإلا
    ENTRY_NEVER_HIT - لا ربح ولا خسارة، الصفقة لم تُنفَّذ عملياً)، ثم
    أيهما انضرب أولاً بعد الدخول: SL (خسارة محسوبة) أو TP (ربح محسوب)،
    أو لا شيء خلال نافذة المراقبة (NEITHER_HIT_WITHIN_WINDOW).

    نفس منهجية `calc_bot_outcomes.py` الأصلية بالضبط (نفس مصدر البيانات
    OKX، نفس منطق المقارنة) لضمان مقارنة عادلة 100% مع نتائج الصفقات
    البشرية المحسوبة بنفس الطريقة تماماً.

    Returns dict: {"entry_hit", "outcome", "exit_price", "exit_time",
                    "pnl_pct", "candles_checked"} أو {"error": ...}
    """
    from ict_math_engine import check_order_invalidated_before_fill

    try:
        bar = "1H"
        start_ts = publish_ts
        end_ts = start_ts + max_days * 24 * 3600 * 1000

        # ⚠️ يجلب الشموع اللاحقة فعلياً لنشر الصفقة (نافذة أمامية
        # [start_ts, end_ts]) - راجع docstring _fetch_okx_forward_window
        # للتفصيل الكامل لسبب عدم استخدام fetch_ohlcv_up_to هنا (تلك
        # الدالة تجلب شموعاً *سابقة* لمرجعها الزمني، بتصميم صحيح ومقصود
        # لغرضها الأصلي بمراحل التحليل - عكس ما نحتاجه هنا بالضبط).
        data = _fetch_okx_forward_window(brain, symbol, start_ts, end_ts, bar=bar)
        if not data or not data.get("closes"):
            return {"error": "NO_DATA"}

        timestamps = data["timestamps"]
        highs = data["highs"]
        lows = data["lows"]
        closes = data["closes"]
        indices = list(range(len(timestamps)))  # الفلترة الزمنية مطبَّقة أصلاً بالجلب

        result = {
            "candles_checked": len(indices),
            "price_range": [min(lows[i] for i in indices), max(highs[i] for i in indices)],
        }

        entry_idx = None
        for i in indices:
            if lows[i] <= entry <= highs[i]:
                entry_idx = i
                break

        # ⚠️ حل جذري (يوليو 2026، راجع docstring
        # check_order_invalidated_before_fill لكل التفصيل والتحقق الحي):
        # قبل اعتبار الأمر المعلَّق "لم ينضرب بعد" أو ننتظره إلى ما لا
        # نهاية، نتحقق أولاً هل الأساس الهيكلي الذي بُنيت عليه الخطة
        # (المُمثَّل بمستوى الستوب نفسه) انكسر فعلياً (إغلاق جسم شمعة
        # يتجاوز الستوب) في أي وقت بين لحظة النشر ولحظة انضراب الدخول
        # (أو حتى نهاية البيانات لو لم ينضرب بعد). لو انكسر - الأمر
        # المعلّق يُعتبر ملغى (ORDER_INVALIDATED_BEFORE_FILL) بغض النظر
        # عن مدة انتظاره؛ لو لم ينكسر - يبقى صالحاً بلا حد زمني اعتباطي
        # (مطابق لتحقق حي مباشر: صفقة ربحت بعد 54 ساعة انتظار بلا أي
        # انكسار هيكلي بالفترة).
        invalidation_check = check_order_invalidated_before_fill(
            highs, lows, closes, data.get("opens", closes), timestamps,
            start_idx=0, entry_idx=entry_idx, sl_price=sl, is_long=(not is_short),
        )
        result["order_invalidation_check"] = invalidation_check

        if invalidation_check["invalidated"]:
            inval_idx = invalidation_check["invalidation_idx"]

            if entry_idx is not None and entry_idx == inval_idx:
                # ⚠️ حل جذري (راجع docstring
                # _resolve_entry_vs_invalidation_same_candle للتفصيل
                # الكامل والسبب - اكتُشف بسؤال دقيق من المستخدم): الدخول
                # وانكسار الأساس الهيكلي وقعا ضمن *نفس* الشمعة (بفريم
                # البيانات الحالي) - لا نفترض أن الدخول سبق بلا تحقق،
                # ننزل لفريم أدق (5m ثم 1m) لنحدد الترتيب الزمني الحقيقي.
                same_candle_res = _resolve_entry_vs_invalidation_same_candle(
                    brain, symbol, timestamps[inval_idx], 3600,
                    entry, sl, is_long=(not is_short),
                )
                result["same_candle_entry_vs_invalidation_resolution"] = same_candle_res
                entry_already_hit_before_invalidation = bool(same_candle_res.get("entry_first"))
            else:
                entry_already_hit_before_invalidation = (
                    entry_idx is not None and entry_idx < inval_idx
                )

            if not entry_already_hit_before_invalidation:
                result["entry_hit"] = False
                result["outcome"] = "ORDER_INVALIDATED_BEFORE_FILL"
                result["pnl_pct"] = 0.0
                result["invalidation_detail"] = invalidation_check["reason"]
                return result


        if entry_idx is None:
            result["entry_hit"] = False
            result["outcome"] = "ENTRY_NEVER_HIT"
            result["pnl_pct"] = 0.0
            return result

        result["entry_hit"] = True

        outcome = None
        exit_price = None
        exit_time_ms = None
        for i in indices:
            if i < entry_idx:
                continue
            lo, hi = lows[i], highs[i]
            if not is_short:
                hit_sl = lo <= sl
                hit_tp = hi >= tp
            else:
                hit_sl = hi >= sl
                hit_tp = lo <= tp

            if hit_sl and hit_tp:
                # ⚠️ حل جذري (يوليو 2026، راجع docstring
                # _resolve_ambiguous_same_candle للتفصيل الكامل الكامل
                # المستند لتحقق حي مباشر): لا نفترض الأسوأ بصمت بمجرد
                # تشارك SL/TP نفس شمعة الـ1H العريضة - نحل الغموض فعلياً
                # ببيانات أدق (5m ثم 1m) لنفس الساعة، ونحسم الترتيب
                # الزمني الحقيقي. فقط لو تعذّر الحسم حتى بأدق فريم متاح
                # (نادر جداً) نُبقي الافتراض المحافظ القديم (SL) كملاذ أخير.
                bar_seconds_map = {"1H": 3600, "4H": 14400, "1D": 86400}
                resolution = _resolve_ambiguous_same_candle(
                    brain, symbol, timestamps[i], bar_seconds_map.get(bar, 3600),
                    entry, sl, tp, is_short,
                )
                if resolution.get("resolved"):
                    outcome = resolution["outcome"]
                    exit_price = resolution["exit_price"]
                    exit_time_ms = resolution["exit_time"]
                    result["ambiguity_resolution"] = resolution["resolution_method"]
                else:
                    outcome, exit_price, exit_time_ms = "AMBIGUOUS_SAME_CANDLE", sl, timestamps[i]
                    result["ambiguity_resolution"] = "UNRESOLVED_EVEN_AT_1M_DEFAULTED_TO_SL"
                break
            elif hit_sl:
                outcome, exit_price, exit_time_ms = "SL_HIT", sl, timestamps[i]
                break
            elif hit_tp:
                outcome, exit_price, exit_time_ms = "TP_HIT", tp, timestamps[i]
                break

        if outcome is None:
            outcome = "NEITHER_HIT_WITHIN_WINDOW"
            last_i = indices[-1]
            exit_price = closes[last_i]
            exit_time_ms = timestamps[last_i]

        result["outcome"] = outcome
        result["exit_price"] = exit_price
        result["exit_time"] = datetime.fromtimestamp(exit_time_ms / 1000, tz=timezone.utc).isoformat()
        result["is_short"] = is_short

        pnl_pct = (exit_price - entry) / entry * 100 if not is_short else (entry - exit_price) / entry * 100
        result["pnl_pct"] = round(pnl_pct, 3)
        return result
    except Exception as e:
        return {"error": f"EXCEPTION: {e}"}


# ══════════════════════════════════════════════════════════════════
#  2.5) إدارة الصفقة الحقيقية (TP1/TP2 + BE + Structure Trail) - يوليو
#       2026، طلب صريح من المستخدم بعد ملاحظة أن البوت يقفل الصفقة
#       كاملة عند أول هدف قريب بينما البشري يصبر لهدف أبعد: "شو
#       بتقترح لنحسن فكرة التارغت بدون ما نكبر الستوب وبدون ما تصير
#       مراهنة - يعني مبني على علم دقيق وتحليل". ثم بعد بحث عميق طُلب
#       صراحة: "روح ابحث بحث عميق وشوف هو شلون بيتصرف بهيك حالات كيف
#       بيجيب اقوى تارغت وكيف بينقل الستوب".
#
# ⚠️ هذا **لا يستبدل** compute_trade_outcome/verdict/loss_cause/
# pattern_confidence الموجودين أصلاً - كلهم يبقون تماماً كما هم (نفس
# TP واحد بسيط، لضمان صفر كسر رجعي لأي منطق مُختبر سابقاً). هذه دالة
# **إضافية** توفّر مقارنة صادقة إضافية: "لو طبّقنا فعلياً منهجية
# مايكل الكاملة لإدارة الصفقة (TP1 يقفل 50%، BE، ثم TP2/Trailing
# للباقي) بدل قفل كل الصفقة عند هدف واحد، شو كانت النتيجة الفعلية؟"

def compute_managed_trade_comparison(brain, symbol, publish_ts, entry, sl, is_short,
                                      entry_data_for_targets, max_days=25,
                                      htf_data_sources=None, execution_bar="5m"):
    """
    يحسب TP1/TP2 (find_tp_targets - Draw on Liquidity الحقيقي، لا
    "أقرب سيولة" فقط) بناءً على نفس بيانات الفريم المستخدمة أصلاً
    لبناء الخطة، ثم يُشغّل simulate_managed_trade_outcome على نفس
    الشموع اللاحقة الحقيقية (نفس مصدر _fetch_okx_forward_window
    المستخدَم فعلياً وبنجاح من compute_trade_outcome - عدالة مقارنة
    كاملة، لا بيانات مختلفة).

    Args:
        entry_data_for_targets: بيانات الفريم (نفس entry_data الذي
            بُنيت عليه الخطة الأصلية) - تُستخدَم فقط لإيجاد TP1/TP2
            (EQH/EQL، سوينغ، OB) - **لا تُستخدَم لمحاكاة النتيجة**
            (تلك تُبنى من الشموع اللاحقة الحقيقية فقط، لا نفس بيانات
            التحليل - نفس مبدأ منع تسريب المستقبل).
        htf_data_sources: (اختياري، يوليو 2026) قائمة [(label, data)]
            بنفس بنية find_tp_targets - لو مُمرَّرة، TP2 (Draw on
            Liquidity) يُشتق من فريم أعلى حقيقي (Daily/4H) بدل الاكتفاء
            بفريم التنفيذ الضيق - راجع docstring find_tp_targets.
        execution_bar: (يوليو 2026، حل جذري لباگ حقيقي مُكتشف بتحقق حي
            مباشر على صفقة #10) فريم محاكاة النتيجة - **لا** "1H" ثابت
            كما كان (شمعة الساعة عريضة جداً لصفقات ICT ذات ستوب ضيق
            جداً 0.15-0.3%، فتحوي أحياناً الدخول والستوب والهدف معاً
            بنفس الشمعة، وتُصنَّف AMBIGUOUS_SAME_CANDLE زوراً رغم أن
            الترتيب الزمني الحقيقي بفريم أدق غير غامض إطلاقاً - تحقق
            حي فعلي أثبت: السعر طار مباشرة فوق TP1 خلال دقيقة واحدة
            من الدخول، لكن شمعة 1H "خلطت" هذا كخسارة افتراضية). الآن
            نستخدم نفس فريم التنفيذ الفعلي (5m افتراضياً) لمحاكاة
            دقيقة، مطابقة لواقع تنفيذ الصفقة الحقيقي.

    Returns dict أو {"error": ...}:
        {
            "tp1": {...} أو None, "tp2": {...},
            "managed_simulation": {...} (مخرجات simulate_managed_
                trade_outcome كاملة),
        }
    """
    from ict_math_engine import find_tp_targets, simulate_managed_trade_outcome

    try:
        targets = find_tp_targets(entry_data_for_targets, entry, sl, is_long=not is_short,
                                   htf_data_sources=htf_data_sources)
    except Exception as e:
        return {"error": f"فشل حساب TP1/TP2: {e}"}

    if not targets.get("tp1"):
        return {
            "tp1": None, "tp2": targets.get("tp2"),
            "managed_simulation": None,
            "note": (
                "لا يوجد مستوى هيكلي حقيقي صالح باتجاه الصفقة لـTP1؛ "
                "لم يُخترع هدف من مضاعف SL، لذلك لا يمكن محاكاة إدارة "
                "TP1/TP2 لهذه الخطة."
            ),
        }

    # ⚠️ حل جذري إضافي (يوليو 2026، اكتُشف بتحقق حي مباشر إضافي - حتى
    # فريم 5m الأدق لا يزال يمكن أن يحوي دخول+SL+TP1 بنفس الشمعة عند
    # حركة سعرية عنيفة جداً بالدقائق الأولى بعد الدخول - نفس مشكلة
    # AMBIGUOUS تتكرر، بس بحدة أقل): بدل الاعتماد على فريم واحد ثابت،
    # نستخدم بيانات **1m فعلية** (الأدق المتاح) للنافذة الحرجة الأولى
    # (أول 24 ساعة بعد النشر - حيث تقع الغالبية العظمى من لحظات
    # الحسم بمنهجية ICT قصيرة الأمد)، ثم نُكمل بفريم أخشن (execution_bar)
    # للفترة المتبقية (تقليل عدد الشموع لفترات أطول بلا داعٍ). هذا
    # يحل الغموض من الجذر (بيانات دقيقة حقيقية بلحظة الحسم الفعلية)
    # بدل "حل غموض" لاحق بعد وقوعه.
    start_ts = publish_ts
    fine_window_ms = 24 * 3600 * 1000  # أول 24 ساعة بدقة 1 دقيقة
    fine_bar_max_days = min(max_days, 3)
    end_ts = start_ts + fine_bar_max_days * 24 * 3600 * 1000

    fine_end_ts = min(start_ts + fine_window_ms, end_ts)
    fine_data = _fetch_okx_forward_window(brain, symbol, start_ts, fine_end_ts, bar="1m")
    coarse_data = None
    if fine_end_ts < end_ts:
        coarse_data = _fetch_okx_forward_window(brain, symbol, fine_end_ts, end_ts, bar=execution_bar)

    if fine_data and fine_data.get("closes"):
        forward_data = fine_data
        if coarse_data and coarse_data.get("closes"):
            # دمج: نتجنب ازدواج أي شمعة بنفس الطابع الزمني عند الحد الفاصل
            last_fine_ts = fine_data["timestamps"][-1]
            for key in ("timestamps", "opens", "highs", "lows", "closes", "volumes"):
                if key not in coarse_data:
                    continue
                extra = [v for t, v in zip(coarse_data["timestamps"], coarse_data[key]) if t > last_fine_ts]
                forward_data[key] = forward_data.get(key, []) + extra
    else:
        # fallback: لو فشل جلب 1m لأي سبب (مثلاً OKX لا يحتفظ بتاريخ 1m
        # طويل)، نستخدم execution_bar وحده على كامل النافذة كما كان
        forward_data = _fetch_okx_forward_window(brain, symbol, start_ts, end_ts, bar=execution_bar)

    if not forward_data or not forward_data.get("closes"):
        return {"error": "NO_FORWARD_DATA"}

    entry_idx = None
    for i in range(len(forward_data["closes"])):
        if forward_data["lows"][i] <= entry <= forward_data["highs"][i]:
            entry_idx = i
            break
    if entry_idx is None:
        return {
            "tp1": targets["tp1"], "tp2": targets["tp2"],
            "managed_simulation": {"classification": "ENTRY_NEVER_HIT", "pnl_pct_blended": 0.0},
        }

    sim = simulate_managed_trade_outcome(
        forward_data, entry_price=entry, sl_price=sl, tp1_price=targets["tp1"]["price"],
        tp2_info=targets["tp2"], is_short=is_short, entry_idx=entry_idx,
    )
    return {"tp1": targets["tp1"], "tp2": targets["tp2"], "managed_simulation": sim}


def apply_capital(pnl_pct, capital_usd, entry, sl):
    """
    ⚠️ يجيب على طلب المستخدم: "وانا بحدد قيمة مالية مثلاً 100 دولار
    فرضاً". يحوّل نسبة الربح/الخسارة% لمبلغ دولاري فعلي، بافتراض حجم
    مركز يحترم قاعدة المخاطرة القياسية بالمشروع (Config.MAX_RISK_PER_
    TRADE، افتراضياً 2%) - أي: المستخدم لا يخاطر بكامل الـ$100 على
    مسافة SL كاملة، بل يحسب حجم المركز بحيث خسارة SL الكاملة = نسبة
    المخاطرة المحددة من رأس المال (إدارة مخاطر واقعية، لا "كل الرصيد
    بصفقة واحدة").

    Returns dict: {"capital_usd", "risk_pct", "position_size_usd",
                    "pnl_usd", "pnl_pct"}
    """
    if pnl_pct is None or entry is None or sl is None:
        return {"capital_usd": capital_usd, "pnl_usd": None, "pnl_pct": pnl_pct}

    risk_pct = Config.MAX_RISK_PER_TRADE  # افتراضياً 0.02 = 2%
    sl_distance_pct = abs(entry - sl) / entry
    if sl_distance_pct <= 0:
        return {"capital_usd": capital_usd, "pnl_usd": None, "pnl_pct": pnl_pct}

    # حجم المركز بحيث: position_size * sl_distance_pct = capital * risk_pct
    position_size_usd = (capital_usd * risk_pct) / sl_distance_pct
    # PnL الفعلي بالدولار = حجم المركز × نسبة الحركة الفعلية (لا فقط
    # نسبة SL) - يعكس TP_HIT (ربح أكبر من مخاطرة SL) وSL_HIT (خسارة
    # = بالضبط نسبة المخاطرة المحددة) بدقة.
    pnl_usd = position_size_usd * (pnl_pct / 100)

    return {
        "capital_usd": round(capital_usd, 2),
        "risk_pct_per_trade": f"{risk_pct*100:.1f}%",
        "position_size_usd": round(position_size_usd, 2),
        "pnl_usd": round(pnl_usd, 2),
        "pnl_pct": pnl_pct,
    }


# ══════════════════════════════════════════════════════════════════
#  3) الحكم (Verdict): مقارنة قرار البوت بالنتيجة الفعلية
# ══════════════════════════════════════════════════════════════════

def _verdict(bot_signal, bot_outcome_data):
    """
    ⚠️ صدق منهجي كامل: الحكم هنا مبني على النتيجة الفعلية المحسوبة
    لصفقة البوت نفسها (entry/SL/TP اللذين اقترحهما البوت تحديداً)،
    عبر compute_trade_outcome() - وليس فقط "هل اتجاه البوت طابق
    الاتجاه البشري". هذا يجيب مباشرة: "لو نفّذنا فعلياً نفس الأرقام
    التي اقترحها البوت، هل كنا سنربح أم نخسر؟"
    """
    if bot_signal == "HOLD":
        return {"category": "NEUTRAL", "text": "البوت لم يدخل (HOLD) - لا ربح ولا خسارة، تحفّظ"}

    if not bot_outcome_data or "error" in bot_outcome_data:
        return {"category": "UNKNOWN", "text": f"تعذّر حساب النتيجة: {bot_outcome_data.get('error', 'غير معروف')}"}

    outcome = bot_outcome_data.get("outcome")
    pnl_pct = bot_outcome_data.get("pnl_pct")

    if outcome == "ENTRY_NEVER_HIT":
        return {"category": "NEUTRAL", "text": "السعر لم يصل أبداً لمنطقة دخول البوت - الصفقة لم تُنفَّذ عملياً"}
    if outcome == "TP_HIT":
        return {"category": "WIN", "text": f"✅ ربح فعلي محسوب: TP تحقق (+{pnl_pct}%)"}
    if outcome == "SL_HIT":
        return {"category": "LOSS", "text": f"❌ خسارة فعلية محسوبة: SL انضرب ({pnl_pct}%)"}
    if outcome == "AMBIGUOUS_SAME_CANDLE":
        return {"category": "AMBIGUOUS", "text": f"⚠️ SL وTP انضربا بنفس الشمعة (تقلب حاد) - غير حاسم، افتراض أسوأ حالة SL ({pnl_pct}%)"}
    if outcome == "NEITHER_HIT_WITHIN_WINDOW":
        return {"category": "OPEN", "text": f"⏳ لم يُحسم بعد خلال نافذة المراقبة (عائم حالياً {pnl_pct}%)"}
    return {"category": "UNKNOWN", "text": f"نتيجة غير معروفة: {outcome}"}


# ══════════════════════════════════════════════════════════════════
#  4) السجل الدائم (Trade Journal) - لكل نتيجة ربح/خسارة على جنب
# ══════════════════════════════════════════════════════════════════

def _load_journal():
    if os.path.exists(JOURNAL_FILE):
        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"wins": [], "losses": [], "neutral": []}
    return {"wins": [], "losses": [], "neutral": []}


def _save_journal(journal):
    os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)
    with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(journal, f, ensure_ascii=False, indent=2, default=str)


def _journal_record(trade_id, symbol, verdict_category, record):
    """
    ⚠️ يجيب مباشرة على: "لازم كل صفقة سواء ربحت أو فشلت تتسجل ع جنب
    لصفقات الربحانة والصفقات الفشلة عشان لو تكررت يكون عندو فكرة إنو
    شايف هيك شي بيشبهو من قبل". سجل خام دائم (لا يُمسح بين الجلسات) -
    منفصل تماماً عن lesson_learning.py (الذي يستخرج "درساً مجرداً"
    فقط) - هذا سجل تفصيلي كامل بكل الأرقام، للمراجعة اليدوية أو
    الإحصائية لاحقاً (مثلاً: "كم مرة خسرنا بنفس archetype تحديداً؟").
    """
    journal = _load_journal()
    bucket = {"WIN": "wins", "LOSS": "losses"}.get(verdict_category, "neutral")
    journal.setdefault(bucket, []).append(record)
    _save_journal(journal)
    return journal


def get_journal_stats():
    """إحصائيات سريعة من السجل الدائم (لعرضها بالقائمة)."""
    journal = _load_journal()
    return {
        "total_wins": len(journal.get("wins", [])),
        "total_losses": len(journal.get("losses", [])),
        "total_neutral": len(journal.get("neutral", [])),
    }


# ══════════════════════════════════════════════════════════════════
#  5) استخراج درس تحليلي مجرَّد (lesson_learning.py) - بلا "هبد"
# ══════════════════════════════════════════════════════════════════

def _extract_and_store_lesson(brain, trade_row, bot_result, verdict):
    """
    ⚠️ يجيب مباشرة على أهم نقطة بطلب المستخدم: "بدنا يتعلم الدرس من
    كل صفقة... يسأل حاله ليش عكس السوق، ليش ربحت الصفقة - ومابعرف كيف
    نعملها إنو ما نخلي الـAI يجاوب من مخو البحت لأنه حيصير يهبد لأنه
    ما بيفهم بالتداول".

    الحل الجاهز أصلاً بالمشروع (`lesson_learning.py`, مبني بجلسة سابقة
    تحديداً لهذا الغرض): لا نطلب من الموديل "فسّر لحالك ليش صار هيك"
    بحرية مطلقة (هذا بالضبط ما يسبب "الهبد" المذكور) - بل نُقيّده بـ:
      1. Schema صارم (error_or_success_class من قائمة مغلقة مُعرَّفة
         مسبقاً بمصطلحات تداول حقيقية: WRONG_DIRECTION, SL_TOO_TIGHT,
         EARLY_ENTRY, CLEAN_WIN... إلخ - لا حرية اختراع تصنيف عشوائي).
      2. حارس برمجي (`lesson_looks_specific`) يرفض أي "درس" يحتوي سعراً
         أو تاريخاً محدداً - يجبره فعلياً على التجريد لنمط عام، لا حفظ
         ببغائي لهذه الصفقة بعينها.
      3. حقل `confidence_this_is_a_real_pattern` يطلب منه صراحة تقييم
         نزيه: هل هذا نمط تحليلي حقيقي متكرر، أم مجرد حظ/سوء حظ عابر
         لا يستحق التعميم - يمنع الإفراط بالثقة من عيّنة واحدة.
      4. الدرس المُخزَّن لا يُحقن كقاعدة صارمة، بل كـ"ميل سابق يستأهل
         انتباه" (راجع `get_relevant_lessons` - الصياغة الحرفية:
         "prior tendencies to be AWARE of, not automatic rules").
    هذا التصميم بالضبط يمنع "الهبد" (تخمين حر بلا مرجعية) مع السماح
    بتعلّم حقيقي مبني على مصطلحات ومفاهيم تداول فعلية.
    """
    import lesson_learning

    if verdict["category"] not in ("WIN", "LOSS"):
        return None  # لا درس من نتائج غامضة/محايدة (لا معنى تحليلياً)

    trade_context = {
        "daily_bias": bot_result.get("bias"),
        "signal_issued": bot_result.get("signal"),
        "entry_model_used": bot_result.get("entry_model"),
        "confidence_stated": bot_result.get("confidence"),
        "archetype": bot_result.get("archetype"),
        "market_regime": bot_result.get("market_regime"),
        "narrative_summary": (bot_result.get("narrative") or "")[:600],
        "reasoning_summary": (bot_result.get("reasoning") or "")[:400],
    }
    outcome_summary = {
        "verdict_category": verdict["category"],
        "outcome_type": verdict["text"],
        "was_signal_correct": verdict["category"] == "WIN",
    }

    try:
        lesson_data = lesson_learning.extract_lesson(brain.ai, trade_context, outcome_summary)
    except Exception as e:
        return {"error": f"lesson extraction failed (non-fatal): {e}"}

    if not lesson_data:
        return None

    stored = lesson_learning.store_lesson(lesson_data, source_trade_id=trade_row.get("id"))
    return stored


# ══════════════════════════════════════════════════════════════════
#  6) الدالة الرئيسية: تشغيل الباك تيست الكامل + كل ما سبق مجتمعاً
# ══════════════════════════════════════════════════════════════════

def run_human_trades_backtest(brain, limit=None, trade_ids=None,
                               timeframe=None, capital_usd=None,
                               extract_lessons=True,
                               progress_callback=None):
    """
    يشغّل MultiPassAnalysis على كل صفقة بشرية موثّقة (أو مجموعة فرعية)،
    يحسب نتيجة حقيقية دقيقة لصفقة البوت (لا تخمين اتجاه فقط)، يقارنها
    بالنتيجة البشرية الفعلية بجدول منظّم، يسجّل كل نتيجة بالسجل الدائم،
    ويستخرج درساً تحليلياً مجرَّداً من كل نتيجة حاسمة (ربح/خسارة).

    Args:
        brain: كائن BrainCore جاهز.
        limit: عدد أقصى من الصفقات (اختباري/توفير حصة).
        trade_ids: قائمة IDs محددة فقط (اختيار يدوي من المستخدم).
        timeframe: فريم التنفيذ (افتراضياً Config الحالي، 5m).
        capital_usd: (اختياري) مبلغ رأسمال بالدولار لحساب ربح/خسارة
            فعلي بالدولار (وليس فقط نسبة%) - راجع apply_capital().
        extract_lessons: هل نستخرج درساً تحليلياً من كل نتيجة (افتراضياً
            نعم - يمكن تعطيله لتسريع اختبار سريع بلا نداء API إضافي).
        progress_callback: دالة اختيارية تُستدعى بعد كل صفقة.
    """
    from multi_pass_analysis import MultiPassAnalysis, _DEFAULT_EXECUTION_TIMEFRAME

    timeframe = timeframe or _DEFAULT_EXECUTION_TIMEFRAME

    trades, source_path = _load_human_trades()
    if not trades:
        return {
            "error": "لم يُعثر على ملف الصفقات البشرية (human_trades/all_human_trades_with_outcomes.json)",
            "results": [],
        }

    if trade_ids:
        trades = [t for t in trades if t.get("id") in trade_ids]
    if limit:
        trades = trades[:limit]

    mp = MultiPassAnalysis(brain)
    entry_counts = {"1h": 150, "5m": 300, "3m": 300, "1m": 300, "4h": 120, "1d": 90}

    results = []
    t_start_all = time.time()

    for i, trade in enumerate(trades):
        symbol = trade["symbol"]
        end_ts = trade["publish_ts"]
        trade_id = trade["id"]

        t0 = time.time()
        row = {
            "id": trade_id, "symbol": symbol, "publish_date": trade.get("publish_date"),
            "human_bias": trade.get("human_bias"),
            "human_entry_zone": trade.get("entry"), "human_sl": trade.get("sl"), "human_tp": trade.get("tp"),
            "human_outcome": trade.get("actual_outcome", {}).get("outcome"),
            "human_pnl_pct": trade.get("actual_outcome", {}).get("pnl_pct"),
        }
        try:
            entry_data = brain.data_manager.fetch_ohlcv_up_to(
                symbol, timeframe, end_ts, limit=entry_counts.get(timeframe, 300)
            )
            if not entry_data:
                row["error"] = "فشل جلب بيانات Entry TF"
                results.append(row)
                if progress_callback:
                    progress_callback(i + 1, len(trades), row)
                continue

            entry_ind = {}
            try:
                entry_ind = brain.ta.compute_all(entry_data)
            except Exception as e:
                row["indicator_warning"] = str(e)

            mtf_data = {"entry": entry_data}
            mtf_indicators = {"entry": entry_ind} if entry_ind else {}

            bot_result = mp.run(
                symbol, timeframe, mtf_data, mtf_indicators,
                is_backtest=True, end_ts=end_ts,
            )
            elapsed = round(time.time() - t0, 1)
            bot_signal = bot_result.get("signal", "HOLD")

            # ── حساب نتيجة حقيقية دقيقة لصفقة البوت (لا تخمين) ──
            bot_outcome_data = None
            if bot_signal in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT") and \
               bot_result.get("entry") and bot_result.get("stop_loss") and bot_result.get("tp"):
                is_short = bot_signal in ("SELL", "SELL_LIMIT")
                bot_outcome_data = compute_trade_outcome(
                    brain, symbol, end_ts,
                    float(bot_result["entry"]), float(bot_result["stop_loss"]), float(bot_result["tp"]),
                    is_short,
                )

            verdict = _verdict(bot_signal, bot_outcome_data)

            # ⚠️ حل جذري جديد (يوليو 2026، طلب صريح من المستخدم - راجع
            # docstring compute_managed_trade_comparison للتفصيل الكامل):
            # مقارنة إضافية (لا تستبدل bot_outcome_data/verdict أعلاه
            # إطلاقاً) - "لو طبّقنا فعلياً TP1/TP2 + BE + Structure Trail
            # (منهجية مايكل الكاملة لإدارة الصفقة) بدل هدف واحد، شو
            # كانت النتيجة الفعلية؟". فقط لو BUY/SELL/BUY_LIMIT/SELL_LIMIT
            # بأرقام كاملة (نفس شرط bot_outcome_data أعلاه بالضبط).
            managed_comparison = None
            if bot_signal in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT") and \
               bot_result.get("entry") and bot_result.get("stop_loss"):
                try:
                    # ⚠️ حل جذري (يوليو 2026، راجع docstring find_tp_targets):
                    # نجلب Daily/4H بنفس end_ts (لا تسريب مستقبلي) لتغذية
                    # TP2 (Draw on Liquidity) بمستوى استراتيجي حقيقي من
                    # فريم أعلى - بدل الاكتفاء بفريم التنفيذ الضيق وحده.
                    daily_htf = None
                    h4_htf = None
                    try:
                        daily_htf = brain.data_manager.fetch_ohlcv_up_to(symbol, "1d", end_ts, limit=90)
                    except Exception:
                        pass
                    try:
                        h4_htf = brain.data_manager.fetch_ohlcv_up_to(symbol, "4h", end_ts, limit=120)
                    except Exception:
                        pass
                    managed_comparison = compute_managed_trade_comparison(
                        brain, symbol, end_ts,
                        float(bot_result["entry"]), float(bot_result["stop_loss"]),
                        bot_signal in ("SELL", "SELL_LIMIT"),
                        entry_data,
                        htf_data_sources=[("Daily", daily_htf), ("4H", h4_htf)],
                    )
                except Exception as e:
                    managed_comparison = {"error": f"استثناء أثناء محاكاة الإدارة المُدارة: {e}"}

            # ⚠️ حل جذري جديد (يوليو 2026، طلب صريح من المستخدم: "إذا
            # شغلة تكررت كتير ونجحت أو عطت نفس النتيجة المتوقعة، فيعزز
            # ويصير يثق فيها بنسبة معينة - بس بدنا نضل تحليل علمي مو
            # تنجيم"). راجع pattern_confidence_engine.py للتفصيل الكامل.
            # نسجّل النتيجة الفعلية (WIN/LOSS محسوبة رياضياً من
            # compute_trade_outcome أعلاه، لا رأي) لبصمة النمط المحقونة
            # بمرحلة entry (final_result["_pattern_signature"]) - فقط
            # لو verdict فعلاً WIN أو LOSS (لا NEUTRAL/OPEN/AMBIGUOUS
            # - لا معنى إحصائياً لتسجيل صفقة لم تُحسم بعد أو لم تُنفَّذ).
            pattern_signature = bot_result.get("_pattern_signature")
            pattern_confidence_recorded = None
            if pattern_signature and verdict["category"] in ("WIN", "LOSS"):
                try:
                    from pattern_confidence_engine import record_pattern_outcome
                    pattern_confidence_recorded = record_pattern_outcome(
                        pattern_signature, verdict["category"], trade_id=trade_id,
                    )
                except Exception as e:
                    pattern_confidence_recorded = {"error": f"استثناء أثناء تسجيل نتيجة النمط: {e}"}

            # ⚠️ حل جذري (يوليو 2026، طلب صريح ومباشر من المستخدم بعد
            # ملاحظة خسائر متتالية: "كتير مهم نعرف نفرق بيناتنا، مشان
            # ما نجي كل خسارة نعتبرها خسارة سوق هيك لح نفشل، لازم نعرف
            # نفصل") - راجع classify_loss_cause() للتفصيل الكامل لمنهج
            # التصنيف الموضوعي (رياضي بحت، لا انطباع). يُستدعى فقط عند
            # SL_HIT فعلياً (لا معنى للتصنيف لو TP_HIT أو HOLD).
            loss_classification = None
            if (bot_outcome_data or {}).get("outcome") == "SL_HIT":
                try:
                    loss_classification = classify_loss_cause(
                        brain, symbol, end_ts, bot_result, bot_outcome_data, timeframe=timeframe,
                    )
                except Exception as e:
                    loss_classification = {
                        "category": "UNKNOWN",
                        "evidence": [f"استثناء أثناء التصنيف: {e}"],
                        "explanation": "⚠️ تعذّر تصنيف سبب الخسارة بسبب خطأ تقني.",
                    }

            # ⚠️ حل جذري (يوليو 2026، طلب صريح من المستخدم): الستوب/
            # التارغت/الدخول تُحدَّد الآن بحرية كاملة حسب منهجية مايكل
            # الهيكلية البحتة، بلا أي تأثير من حد إدارة رأس المال أثناء
            # التحليل - راجع MultiPassAnalysis._compute_risk_management_
            # report. هنا فقط نعرض هذا التقرير المعلوماتي (لا نُغيّر أي
            # رقم) ضمن جدول المقارنة، كما طلب المستخدم صراحة: "قلي إذا
            # متطابقة مع إدارتي المالية ولا لأ".
            risk_report = bot_result.get("_risk_management_report")
            row.update({
                "bot_signal": bot_signal,
                "bot_bias": bot_result.get("bias"),
                "bot_confidence": bot_result.get("confidence"),
                "bot_entry": bot_result.get("entry"),
                "bot_sl": bot_result.get("stop_loss"),
                "bot_tp": bot_result.get("tp"),
                "bot_outcome": (bot_outcome_data or {}).get("outcome"),
                "bot_pnl_pct": (bot_outcome_data or {}).get("pnl_pct"),
                "bot_narrative_short": (bot_result.get("narrative") or bot_result.get("reasoning") or "")[:300],
                "stopped_at_gate": bot_result.get("stopped_at_gate"),
                "stages_completed": bot_result.get("stages_completed"),
                "elapsed_seconds": elapsed,
                "verdict_category": verdict["category"],
                "verdict_text": verdict["text"],
                "risk_management_rr_actual": (risk_report or {}).get("rr_actual"),
                "risk_management_matches_user_settings": (risk_report or {}).get("matches_user_risk_management"),
                "risk_management_summary": (risk_report or {}).get("summary_text"),
                "loss_cause_category": (loss_classification or {}).get("category"),
                "loss_cause_explanation": (loss_classification or {}).get("explanation"),
                "loss_cause_evidence": (loss_classification or {}).get("evidence"),
                "pattern_signature": pattern_signature,
                "pattern_total_occurrences": (pattern_confidence_recorded or {}).get("total"),
                "pattern_wins": (pattern_confidence_recorded or {}).get("wins"),
                "pattern_losses": (pattern_confidence_recorded or {}).get("losses"),
                "tp1": (managed_comparison or {}).get("tp1"),
                "tp2": (managed_comparison or {}).get("tp2"),
                "managed_simulation": (managed_comparison or {}).get("managed_simulation"),
                "managed_simulation_note": (managed_comparison or {}).get("note") or (managed_comparison or {}).get("error"),
            })

            if capital_usd and bot_outcome_data and "pnl_pct" in bot_outcome_data:
                row["capital_result"] = apply_capital(
                    bot_outcome_data["pnl_pct"], capital_usd,
                    float(bot_result.get("entry", 0) or 0), float(bot_result.get("stop_loss", 0) or 0),
                )

            # ⚠️ حل جذري جديد (يوليو 2026، طلب صريح): مقارنة $100 مقابل
            # $100 بين البشري والبوت **بمنهجية الإدارة الكاملة** (TP1/
            # TP2/BE/Trail) - لا فقط هدف واحد - لأن هذا ما طلبه المستخدم
            # حرفياً: "فرق الربح ع افتراض أنا والبشري فايتين بـ100 دولار".
            managed_sim = (managed_comparison or {}).get("managed_simulation")
            if capital_usd and managed_sim and "pnl_pct_blended" in managed_sim:
                row["capital_result_managed"] = apply_capital(
                    managed_sim["pnl_pct_blended"], capital_usd,
                    float(bot_result.get("entry", 0) or 0), float(bot_result.get("stop_loss", 0) or 0),
                )
            human_pnl_pct = trade.get("actual_outcome", {}).get("pnl_pct")
            if capital_usd and human_pnl_pct is not None:
                human_entry_zone = trade.get("entry")
                human_entry_approx = (
                    (human_entry_zone[0] + human_entry_zone[1]) / 2
                    if isinstance(human_entry_zone, list) and len(human_entry_zone) == 2
                    else human_entry_zone
                )
                human_sl = trade.get("sl")
                if human_entry_approx and human_sl:
                    row["capital_result_human"] = apply_capital(
                        human_pnl_pct, capital_usd, float(human_entry_approx), float(human_sl),
                    )

            # ── سجل دائم (win/loss journal) ──
            _journal_record(trade_id, symbol, verdict["category"], {
                "trade_id": trade_id, "symbol": symbol, "publish_date": trade.get("publish_date"),
                "bot_signal": bot_signal, "bot_entry": row.get("bot_entry"),
                "bot_sl": row.get("bot_sl"), "bot_tp": row.get("bot_tp"),
                "outcome": row.get("bot_outcome"), "pnl_pct": row.get("bot_pnl_pct"),
                "archetype": bot_result.get("archetype"), "market_regime": bot_result.get("market_regime"),
                "recorded_at": str(datetime.now()),
            })

            # ── درس تحليلي مجرَّد (اختياري، يستهلك نداء API إضافي) ──
            if extract_lessons and verdict["category"] in ("WIN", "LOSS"):
                lesson = _extract_and_store_lesson(brain, row, bot_result, verdict)
                if lesson and "error" not in lesson:
                    row["lesson_extracted"] = lesson.get("lesson")

        except Exception as e:
            row["error"] = f"استثناء أثناء التحليل: {e}"
            row["elapsed_seconds"] = round(time.time() - t0, 1)

        results.append(row)
        if progress_callback:
            progress_callback(i + 1, len(trades), row)

    total_elapsed = round(time.time() - t_start_all, 1)

    valid_results = [r for r in results if "error" not in r]
    hold_count = sum(1 for r in valid_results if r.get("bot_signal") == "HOLD")
    win_count = sum(1 for r in valid_results if r.get("verdict_category") == "WIN")
    loss_count = sum(1 for r in valid_results if r.get("verdict_category") == "LOSS")

    return {
        "source_file": source_path,
        "timeframe_used": timeframe,
        "capital_usd": capital_usd,
        "total_trades_tested": len(trades),
        "successful_analyses": len(valid_results),
        "failed_analyses": len(results) - len(valid_results),
        "hold_count": hold_count,
        "directional_signals_count": len(valid_results) - hold_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "total_wall_time_sec": total_elapsed,
        "avg_time_per_trade_sec": round(total_elapsed / len(trades), 1) if trades else 0,
        "results": results,
    }


# ══════════════════════════════════════════════════════════════════
#  5) تصنيف سبب الخسارة: خطأ حقيقي بنظامنا مقابل خسارة سوق طبيعية
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ لماذا هذه الدالة ضرورية (طلب صريح ومباشر من المستخدم بعد ملاحظة
# تكرار خسائر متتالية): "كتير مهم نعرف نفرّق بيناتن، كتير مهم مشان
# ما نجي كل خسارة نعتبرها خسارة سوق هيك لح نفشل، لازم نعرف نفصل."
#
# المشكلة الحقيقية بأي تقييم بدون هذا الفحص: لو اعتبرنا كل خسارة
# "طبيعية من احتمالية السوق"، رح نفوّت أخطاء برمجية/تحليلية حقيقية
# (اتجاه معكوس، ستوب موضوع غلط، تجاهل انحياز أعلى). ولو اعتبرنا كل
# خسارة "خطأ بالنظام"، رح "نصلح" أشياء ليست معطوبة أصلاً (التداول
# احتمالي بطبيعته - حتى الإعداد الهيكلي الصحيح 100% يخسر أحياناً).
#
# الحل: معيار تصنيف **موضوعي رياضي بحت** (لا انطباع)، يعتمد فقط على
# أدلة متوفرة أصلاً من نفس النداء (لا حسابات جديدة مُخترَعة لهذا الغرض
# فقط) + إعادة محاكاة رياضية مباشرة لسؤال حاسم واحد: "لو كان الستوب
# أوسع بهامش معقول (نفس الـbuffer المعياري)، هل كانت الصفقة ستصل فعلاً
# للهدف بدل ما تُضرَب؟" - هذا يفرّق بالضبط بين:
#   (أ) "فخ سيولة عادي + اتجاه صحيح" (فتيل ضرب الستوب بفارق ضئيل، ثم
#       السعر كمل فعلاً بالاتجاه المتوقع نحو الهدف) = خسارة سوق طبيعية
#       تماماً - نفس ما يحدث لأي متداول محترف أحياناً، ليست خطأ.
#   (ب) "الاتجاه نفسه كان خطأ" (السعر كمل بالاتجاه المعاكس تماماً، لم
#       يقترب من الهدف إطلاقاً حتى لو وسّعنا الستوب كثيراً) = يستحق
#       تحقيقاً كخطأ تحليلي حقيقي محتمل (لا يعني تلقائياً وجود باگ -
#       قد يكون قراءة سياقية خاطئة مبررة احتمالياً - لكن يستأهل مراجعة).
#   (ج) وجود تناقضات رياضية موثّقة فعلياً بنفس النداء (SEQUENCE/SWING
#       CONTRADICTION غير محلولة، bias anchor مخالف بلا استشهاد، إلخ)
#       = خطأ نظام مؤكد رياضياً 100% - لا نقاش، هذا فرق جذري عن (أ)/(ب).

def classify_loss_cause(brain, symbol, publish_ts, bot_result, bot_outcome_data, timeframe="5m",
                         buffer_multiplier=3.0, max_days=25):
    """
    يُستدعى فقط لو bot_outcome_data["outcome"] == "SL_HIT" (خسارة فعلية
    محسوبة) - يصنّف السبب الجذري لهذه الخسارة تحديداً بالذات.

    Returns dict:
        {
            "category": "SYSTEM_ERROR_CONFIRMED" | "DIRECTION_QUESTIONABLE"
                         | "NORMAL_MARKET_LOSS" | "UNKNOWN",
            "evidence": [str, ...],  # كل دليل موضوعي استُخدم بالتصنيف
            "explanation": str,  # شرح مباشر للمستخدم بالعربي
        }
    """
    evidence = []

    # ── الفحص 1: هل توجد تناقضات رياضية موثّقة فعلياً بنفس النداء؟
    # (أقوى دليل ممكن - هذه ليست تخمينات، فحوصات AuthenticityEngine
    # الفعلية على البيانات الخام نفسها) ──
    stage_log = bot_result.get("multi_pass_stage_log", {}) or {}
    unresolved_math_issues = []
    for stage_name in ("daily", "h15"):
        audit = (stage_log.get(stage_name) or {}).get(f"_{stage_name}_math_audit")
        if audit and not audit.get("resolved", True):
            unresolved_math_issues.append(
                f"مرحلة {stage_name}: تناقض رياضي/هيكلي لم يُحل حتى بعد "
                f"{audit.get('retries_used', 0)} محاولة تصحيح"
            )
    trade_plan_audit = bot_result.get("_trade_plan_audit") or {}
    if trade_plan_audit.get("final_issues"):
        unresolved_math_issues.append(
            f"خطة الصفقة: مشاكل هيكلية/منطقية لم تُحل نهائياً: "
            f"{trade_plan_audit.get('final_issues')}"
        )

    if unresolved_math_issues:
        evidence.extend(unresolved_math_issues)
        return {
            "category": "SYSTEM_ERROR_CONFIRMED",
            "evidence": evidence,
            "explanation": (
                "❌ خطأ نظام مؤكد رياضياً: وُجدت تناقضات حسابية/هيكلية "
                "موثّقة فعلياً بنفس هذا التحليل (لا تخمين) - هذه ليست "
                "خسارة سوق عادية، هذا يستحق تحقيقاً برمجياً حقيقياً."
            ),
        }

    # ── الفحص 2: إعادة محاكاة موضوعية - لو وسّعنا الستوب بهامش معقول،
    # هل كانت الصفقة ستصل فعلياً للهدف؟ (يفرّق فخ سيولة عادي عن اتجاه خاطئ) ──
    entry = bot_result.get("entry")
    sl = bot_result.get("stop_loss")
    tp = bot_result.get("tp")
    signal = bot_result.get("signal")
    if not all(isinstance(v, (int, float)) for v in (entry, sl, tp)) or signal not in (
        "BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"
    ):
        return {
            "category": "UNKNOWN",
            "evidence": ["بيانات الصفقة غير مكتملة - لا يمكن إعادة المحاكاة"],
            "explanation": "⚠️ تعذّر التصنيف - بيانات صفقة البوت غير مكتملة.",
        }

    is_short = signal in ("SELL", "SELL_LIMIT")
    sl_dist = abs(entry - sl)
    widened_sl = (entry - sl_dist * buffer_multiplier) if not is_short else (entry + sl_dist * buffer_multiplier)

    widened_outcome = compute_trade_outcome(
        brain, symbol, publish_ts,
        entry, widened_sl, tp, is_short, max_days=max_days,
    )

    original_pnl = (bot_outcome_data or {}).get("pnl_pct")
    evidence.append(
        f"مسافة SL الأصلية={sl_dist:.6g}، خسارة فعلية={original_pnl}%"
    )

    if widened_outcome.get("outcome") == "TP_HIT":
        evidence.append(
            f"لو وُسِّع الستوب {buffer_multiplier}x (إلى {widened_sl:.6g}) - "
            f"السعر كان سيصل فعلياً للهدف ({tp}) بدون ضرب الستوب الموسّع. "
            "الاتجاه والتحليل كانا صحيحين - فقط الستوب الأصلي كان ضيقاً "
            "بما يكفي ليُضرب بفتيل سيولة عادي قبل استمرار الحركة الصحيحة."
        )
        return {
            "category": "NORMAL_MARKET_LOSS",
            "evidence": evidence,
            "explanation": (
                "✅ خسارة سوق طبيعية (فخ سيولة عادي، لا خطأ تحليلي): "
                "الاتجاه المُحدَّد كان صحيحاً فعلياً - السعر استمر لاحقاً "
                "نحو الهدف - لكن الستوب انضرب أولاً بفارق ضئيل بفتيل عادي. "
                "هذا احتمالي طبيعي بالتداول، ليس عيباً بالتحليل أو الكود."
            ),
        }
    elif widened_outcome.get("outcome") == "SL_HIT":
        evidence.append(
            f"حتى لو وُسِّع الستوب {buffer_multiplier}x (إلى {widened_sl:.6g}) - "
            "السعر ما زال يضرب الستوب الموسّع أيضاً، ولم يصل للهدف إطلاقاً."
        )
        return {
            "category": "DIRECTION_QUESTIONABLE",
            "evidence": evidence,
            "explanation": (
                "⚠️ الاتجاه نفسه يستحق مراجعة (لا يعني بالضرورة خطأ برمجي "
                "مؤكد): حتى مع هامش أوسع بكثير، السعر لم يقترب من الهدف - "
                "استمر بالاتجاه المعاكس تماماً. هذا لا يعني تلقائياً وجود "
                "باگ (قد يكون قراءة سياقية مبررة احتمالياً باءت بالفشل - "
                "التداول احتمالي)، لكنه يستأهل مراجعة تحليلية أعمق لهذه "
                "الحالة تحديداً، بعكس (أ) أعلاه."
            ),
        }
    else:
        evidence.append(
            f"لو وُسِّع الستوب {buffer_multiplier}x، النتيجة كانت "
            f"{widened_outcome.get('outcome', 'غير محسومة')} خلال نافذة المراقبة."
        )
        return {
            "category": "UNKNOWN",
            "evidence": evidence,
            "explanation": (
                "⚠️ غير حاسم: لا السيناريو الموسّع وصل للهدف بوضوح ولا "
                "استمر بعكس الاتجاه بوضوح تام - يحتاج مراجعة يدوية للسياق."
            ),
        }

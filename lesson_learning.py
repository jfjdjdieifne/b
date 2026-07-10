# -*- coding: utf-8 -*-
"""
lesson_learning - نظام "التعلّم من الدرس، لا حفظ الصفقة" (يوليو 2026،
بطلب صريح من المستخدم بعد نقاش حول الفرق الجوهري بين "بوت بيحفظ
الصفقات ليغش حاله" و"بوت بيستوعب الفكرة كفكرة").

════════════════════════════════════════════════════════════════════
الفلسفة الأساسية (نفس كلام المستخدم حرفياً، لأنه دقيق ومهم):
  "لازم يتعلم من كل صفقة... الربحانة لازم تحفظ شو ربحها... والخسرانة
   لازم تتعلم ليش خسرت... بس انتبه: ما بتعلمو وبتحفظو الصفقات
   الخسرانة بشكل خاص لنفس ذات الصفقة عشان تغش حالك... لازم تستوعب
   الفكرة كفكرة."

يعني: الممنوع هو أن يحفظ النظام "صفقة ETH بتاريخ كذا، دخلت عند سعر
كذا، خسرت" ثم عند رؤية نفس الرقم بالضبط مستقبلاً "يتذكر" ويتجنبه -
هذا حفظ ببغائي (rote memorization) لا فهم، ولا ينفع أي صفقة أخرى
مختلفة الأرقام حتى لو كانت نفس النمط بالضبط.

المطلوب الصحيح: من كل نتيجة (ربح أو خسارة)، نستخرج "درساً مجرَّداً"
(Lesson) - قاعدة تفسيرية عامة قابلة للتطبيق على أي صفقة مستقبلية
تشترك بنفس *النمط التحليلي*، بغض النظر عن الأرقام المحددة. مثال:
  ❌ غلط (حفظ الصفقة): "لا تشترِ ETH عند سعر 76750 يوم كذا"
  ✅ صح (درس مجرّد): "الدخول قبل تأكيد 1H CHoCH فعلي (بحجة أن وضع
     الباك تيست يفرض قراراً) أنتج دخولاً مبكراً انعكس السعر ضده خلال
     ساعات قليلة - عند غياب تأكيد LTF حقيقي، انتظار الإشارة أفضل من
     افتراضها حتى لو بدت الصورة الكبيرة (Daily) متوافقة."

════════════════════════════════════════════════════════════════════
كيف يعمل هذا فعلياً (لا اعتماد على "فهم" النظام لنفسه فقط - حماية
برمجية صريحة ضد الانزلاق نحو حفظ الصفقة):

1. بعد معرفة نتيجة أي صفقة فعلية (TP_HIT / SL_HIT / HOLD صحيح/خطأ)،
   يُستدعى extract_lesson() - يُرسل طلب واحد للموديل (نفس Nemotron)
   يطلب صراحة: "استخرج درساً تحليلياً مجرداً من هذه النتيجة - بلا أي
   سعر أو تاريخ أو رمز عملة محدد، بل نمط تحليلي عام قابل للتطبيق على
   أي صفقة مستقبلية تشترك بنفس نوع القرار."

2. **حارس برمجي (lesson_sanitizer)**: قبل حفظ أي درس، يُفحص نصياً
   للتأكد أنه لا يحتوي أرقام أسعار محددة (regex يبحث عن أنماط سعرية:
   أرقام بـ4+ خانات، مع/بدون فاصلة عشرية) ولا تواريخ محددة (YYYY-MM-DD
   أو أسماء أشهر). لو وُجد أي منها، يُرفض الدرس ويُطلب استخراج أعمّ
   (إعادة محاولة واحدة)، أو يُهمَل بأمان (لا يُحفظ درس "مغشوش" أبداً -
   الأمان هنا أولوية على "حفظ أي شيء ولو ناقصاً").

3. الدروس المحفوظة تُصنَّف حسب **نوع القرار/الخطأ** (نفس تصنيف
   [SELF_LEARNING] الأصلي بملف المعرفة: WRONG_DIRECTION, SL_TOO_TIGHT,
   STOP_HUNT, FABRICATED_SETUP, COUNTER_TREND, NO_CONFIRMATION,
   EARLY_ENTRY, OVEREXTENDED - بالإضافة لأنواع نجاح: CLEAN_WIN,
   MESSY_WIN) - هذا يسمح لاحقاً بحقن الدروس ذات الصلة بمرحلة تحليل
   معينة (مثلاً دروس EARLY_ENTRY تُحقن بمرحلة h15/entry، لا بمرحلة
   Weekly التي لا علاقة لها بتوقيت الدخول).

4. **الحقن بالتحليل المستقبلي (get_relevant_lessons)**: لا نحقن كل
   الدروس المخزَّنة دفعة واحدة (قد تصير مئات مع الوقت وتُغرق البرومبت
   بلا فائدة تناسبية) - نحقن فقط أحدث N درس من كل فئة (افتراضياً 3)،
   بصيغة "دروس عامة من تحليلات سابقة (لا تخص هذه الصفقة تحديداً)"
   واضحة أنها إرشاد عام، لا حقيقة عن هذه الصفقة بالذات.

5. **لا "قاعدة تعلّمها بصفقة وحدة" تُطبَّق آلياً** - نفس شرط
   [SELF_LEARNING] 17.6 الأصلي بالدستور: أي تعديل فعلي بالسلوك
   (مثل تعديل RiskManager) يتطلب تكرار النمط 3+ مرات موثقة، لا مجرد
   خسارة واحدة. الدروس المستخرجة هنا هي "مواد خام للمراجعة والحقن
   الإرشادي" - وليست تعديلات آلية فورية على قواعد الكود الصارمة
   (SL≤2.5%، RR≥3:1 تبقى ثابتة بغض النظر عن أي درس).
"""
import json
import logging
import os
import re
from datetime import datetime

from config import Config

logger = logging.getLogger("LessonLearning")

# ⚠️ ملف منفصل تماماً عن memory.json/trades.json الموجودين أصلاً
# (تلك ملفات "سجل خام" لكل حدث/صفقة بالتفصيل - هذا ملف "دروس مقطَّرة"
# فقط، حجمه يبقى صغيراً جداً بغض النظر عن عدد الصفقات لأنه يُلخِّص لا
# يُراكم بيانات خام).
LESSONS_FILE = os.path.join(Config.DATA_DIR, "lessons.json")

ERROR_CLASSES = [
    "WRONG_DIRECTION", "SL_TOO_TIGHT", "STOP_HUNT", "BAD_TIMING",
    "FABRICATED_SETUP", "COUNTER_TREND", "NO_CONFIRMATION",
    "EARLY_ENTRY", "OVEREXTENDED", "LIQUIDITY_TRAP", "RULE_VIOLATION",
]
SUCCESS_CLASSES = ["CLEAN_WIN", "MESSY_WIN", "CORRECT_HOLD"]
ALL_CLASSES = ERROR_CLASSES + SUCCESS_CLASSES

# ⚠️ إصلاح فجوة حقيقية مُكتشفة باختبار حي فعلي (يوليو 2026): طلبنا من
# الموديل نفسه يصنّف applies_to_stage بوصف دقيق يفرّق بين "أين حصل
# الخطأ سردياً" و"أين يُتَّخذ القرار الفعلي مستقبلاً" - لكن حتى بعد
# توضيح الوصف بالـschema، الموديل استمر يصنّف دروساً عن منطق بناء
# SL/TP كـ"daily" (لأن السرد التحليلي بدأ هناك) بدل "entry" (حيث
# تُحسم أرقام SL/TP الفعلية ببرومبت _build_entry_prompt). هذا خطر
# حقيقي: لو اعتمدنا فقط على تصنيف الموديل، درس عن خطأ بناء SL لن يصل
# أبداً للمرحلة التي تبنيه فعلياً - عديم الفائدة عملياً بصمت.
#
# الحل: قائمة صريحة بفئات الأخطاء التي تتعلق جوهرياً ببناء رقم
# Entry/SL/TP النهائي - هذه دائماً تُحقن أيضاً بمرحلة entry بغض النظر
# عن تصنيف applies_to_stage الذي اختاره الموديل، لأن هذه هي المرحلة
# الوحيدة التي تُبنى فيها هذه الأرقام فعلياً بالكود
# (_build_entry_prompt / _diagnose_trade_plan) - حقيقة بنيوية عن
# النظام نفسها، لا اجتهاد يُترك للموديل وحده.
EXECUTION_RELEVANT_CLASSES = {
    "SL_TOO_TIGHT", "STOP_HUNT", "FABRICATED_SETUP", "NO_CONFIRMATION",
    "EARLY_ENTRY", "OVEREXTENDED", "LIQUIDITY_TRAP", "RULE_VIOLATION",
    "CLEAN_WIN", "MESSY_WIN",
}

# ⚠️ حارس ضد "الغش" - أنماط تدل على تفصيل محدد جداً بصفقة واحدة بدل
# درس عام. هذا فحص نصي بسيط (لا يفهم المعنى) لكنه خط دفاع أول مباشر
# وموثوق: لو الدرس فعلاً مجرَّد كما يجب، لن يحتاج ذكر رقم سعر محدد.
_PRICE_LIKE_PATTERN = re.compile(
    r"\$?\d{2,3}[,.]?\d{3}(?:\.\d+)?|\b\d{4,}\.\d{1,4}\b"
)
_DATE_LIKE_PATTERN = re.compile(
    r"\b20\d{2}-\d{1,2}-\d{1,2}\b|\b(january|february|march|april|may|june|"
    r"july|august|september|october|november|december)\s+\d{1,2}\b",
    re.IGNORECASE,
)


def _load_lessons():
    if not os.path.exists(LESSONS_FILE):
        return []
    try:
        with open(LESSONS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"فشل تحميل ملف الدروس ({LESSONS_FILE}): {e}")
        return []


def _save_lessons(lessons):
    Config.ensure_data_dir()
    try:
        with open(LESSONS_FILE, "w", encoding="utf-8") as f:
            json.dump(lessons, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"فشل حفظ ملف الدروس: {e}")


def lesson_looks_specific(lesson_text):
    """
    ⚠️ الحارس الأساسي ضد "حفظ الصفقة بدل استيعاب الفكرة": يفحص إن كان
    نص الدرس يحتوي أرقام سعرية محددة أو تواريخ محددة - إشارة قوية أن
    هذا "توثيق لصفقة واحدة" لا "درس تحليلي عام". هذا فحص متحفظ عمداً
    (قد يرفض دروساً سليمة نادراً لو ذكرت رقماً عرضياً كمثال) - القرار
    المتعمّد هنا: تفضيل رفض درس صالح احتياطاً، على قبول درس "مغشوش"
    يحفظ رقم صفقة بعينها. الأمان أولاً.
    """
    if _PRICE_LIKE_PATTERN.search(lesson_text):
        return True, "PRICE_NUMBER_DETECTED"
    if _DATE_LIKE_PATTERN.search(lesson_text):
        return True, "SPECIFIC_DATE_DETECTED"
    return False, None


def _extract_lesson_schema():
    return {
        "type": "OBJECT",
        "properties": {
            "error_or_success_class": {
                "type": "STRING",
                "enum": ALL_CLASSES,
            },
            "lesson": {
                "type": "STRING",
                "description": (
                    "درس تحليلي عام مجرَّد (2-4 جمل) - يشرح النمط "
                    "التحليلي الذي أدى لهذه النتيجة وكيف يُعرف/يُعالج "
                    "مستقبلاً. ممنوع تماماً ذكر أي سعر محدد أو تاريخ "
                    "محدد أو رمز عملة معين - فقط النمط المجرد القابل "
                    "للتطبيق على أي صفقة مستقبلية مشابهة بالنوع."
                ),
            },
            "applies_to_stage": {
                "type": "STRING",
                "enum": ["weekly", "daily", "h4", "h15", "entry", "all_stages"],
                "description": (
                    "Which analysis stage should RECEIVE this lesson as a "
                    "reminder for FUTURE trades - i.e. where the actual "
                    "DECISION affected by this lesson gets made, not "
                    "necessarily where the original mistake was narrated. "
                    "Example: if the error was about SL placement logic, "
                    "answer 'entry' (SL/TP numbers are finalized at the "
                    "entry stage) even if the flawed reference level was "
                    "first mentioned during daily-bias narration. If the "
                    "error was about misreading overall trend direction, "
                    "answer 'daily' (bias is decided there). Think: 'at "
                    "which future stage would reading this lesson change "
                    "what the model actually does?'"
                ),
            },
            "confidence_this_is_a_real_pattern": {
                "type": "STRING",
                "enum": ["LOW", "MODERATE", "HIGH"],
                "description": (
                    "هل هذا خطأ/نجاح تحليلي حقيقي متكرر النمط، أم "
                    "قد يكون حظاً/سوء حظ عابراً لا يستحق تعميمه؟"
                ),
            },
        },
        "required": ["error_or_success_class", "lesson", "applies_to_stage",
                      "confidence_this_is_a_real_pattern"],
    }


def extract_lesson(ai_client, trade_context, outcome_summary, max_retries=1):
    """
    يستخرج درساً مجرداً واحداً من نتيجة صفقة فعلية (معروفة النتيجة).

    Args:
        ai_client: أي كائن يوفر query_json(prompt, schema) (نفس واجهة
            NemotronClient الموجودة أصلاً - لا اعتماد على تطبيق محدد).
        trade_context: dict يصف ماذا رأى البوت وقرر (ملخص التحليل -
            بدون حاجة لتمرير كل الأرقام الخام، فقط السياق التحليلي).
        outcome_summary: dict يصف ماذا صار فعلياً (TP_HIT/SL_HIT/HOLD،
            هل كان القرار صحيحاً بأثر رجعي).

    Returns:
        dict الدرس المُستخرَج والمُتحقَّق منه، أو None لو فشل الاستخراج
        أو فشل فحص "الغش" (بعد محاولة تصحيح واحدة).
    """
    prompt = f"""
You are analyzing the outcome of a completed trade decision to extract
a GENERAL, ABSTRACT analytical lesson - NOT a record of this specific
trade. This lesson will be shown to yourself in FUTURE, DIFFERENT
trades (different prices, different dates, possibly different assets)
to help you reason better - so it must describe a PATTERN, not this
instance.

WHAT THE SYSTEM ANALYZED AND DECIDED (context, not to be echoed
verbatim in your lesson):
{json.dumps(trade_context, ensure_ascii=False, indent=2)}

WHAT ACTUALLY HAPPENED (ground truth outcome):
{json.dumps(outcome_summary, ensure_ascii=False, indent=2)}

CRITICAL INSTRUCTION - READ CAREFULLY:
Your "lesson" field must NEVER contain:
  - Any specific price number (e.g. "76750", "$2200")
  - Any specific date (e.g. "2026-04-28", "April 28")
  - Any specific asset symbol as the SUBJECT of the lesson rule itself
    (you may mention "crypto" or "BTC/ETH-style assets" generically,
    but not "this specific BTC move on this specific day")

Instead, describe the ANALYTICAL PATTERN in general terms. Compare to
these two examples:
  BAD (memorizing the instance): "Don't buy at 76750 near an
  unconfirmed 1H zone on April 28."
  GOOD (abstracting the pattern): "Entering based on Daily/4H alignment
  alone, before the 1H timeframe actually prints its own CHoCH
  confirmation, produced a premature entry that reversed quickly. When
  the entry-timeframe confirmation is genuinely absent, the higher
  timeframes being aligned is necessary but not sufficient - the setup
  is not yet complete."

Also assess HONESTLY: is this a real, generalizable analytical pattern
worth remembering, or could this outcome have been driven by ordinary
market randomness that doesn't reliably predict future setups? Rate
your confidence accordingly - do not overstate a single occurrence as
a strong rule.
"""
    for attempt in range(max_retries + 1):
        try:
            # ⚠️ إصلاح جذري (يوليو 2026، بعد كراش حقيقي بأول استخدام فعلي
            # لهذه الدالة عبر human_trades_backtest.py الجديدة):
            # "OpenRouterClient.query_json() takes 2 positional arguments
            # but 3 were given" - هذا الملف كان مكتوباً بافتراض واجهة
            # قديمة (query_json(prompt, schema) بمعاملين موضعيين)، لكن
            # OpenRouterClient.query_json الموحّدة الحالية تقبل فقط
            # `prompt` موضعياً، والباقي keyword-only (**kwargs، تحديداً
            # `response_schema=...`). الاستدعاء القديم مرّر الـschema
            # كمعامل موضعي ثانٍ فمَنَع الاستدعاء بالكامل - هذا **خطأ
            # برمجي حقيقي بالاستدعاء نفسه، لا علاقة له بالموديل أو
            # بجودة الدرس المطلوب استخراجه**. الحل: تمرير الـschema
            # صراحة كـ`response_schema=` (نفس الاسم المستخدم بكل مكان
            # آخر بالمشروع لهذا المعامل تحديداً).
            raw = ai_client.query_json(prompt, response_schema=_extract_lesson_schema())
        except Exception as e:
            logger.warning(f"⚠️ فشل استدعاء استخراج الدرس: {e}")
            return None
        # ⚠️ توافق مرن مع واجهتين مختلفتين فعلياً بالمشروع: NemotronClient
        # الخام يرجع tuple (parsed, meta)، بينما AIClientAdapter يرجع dict
        # مباشرة (مع _meta بداخله) - نتعامل مع الاثنين بلا افتراض واحد فقط.
        if isinstance(raw, tuple):
            result = raw[0]
        else:
            result = raw
        if isinstance(result, dict) and "_meta" in result:
            result = {k: v for k, v in result.items() if k != "_meta"}
        if not result or not isinstance(result, dict) or "lesson" not in result:
            return None

        is_specific, reason = lesson_looks_specific(result["lesson"])
        if not is_specific:
            return result

        logger.warning(
            f"⚠️ [Lesson Sanitizer] الدرس المُستخرَج رُفض ({reason}) - "
            f"يحتوي تفصيلاً محدداً بدل نمط عام: {result['lesson'][:200]}"
        )
        if attempt < max_retries:
            prompt += (
                "\n\n⚠️ YOUR PREVIOUS ATTEMPT CONTAINED A SPECIFIC PRICE OR "
                "DATE - REJECTED. Rewrite the lesson with ZERO specific "
                "numbers or dates, describing only the general analytical "
                "pattern."
            )
    logger.warning(
        "⚠️ [Lesson Sanitizer] فشل استخراج درس عام بعد كل المحاولات - "
        "لن يُحفظ أي درس لهذه الصفقة (الأمان أولاً - لا حفظ درس مغشوش)."
    )
    return None


def store_lesson(lesson_data, source_trade_id=None):
    """
    يحفظ درساً مُتحقَّقاً منه (مرّ فحص lesson_looks_specific). يُضاف
    source_trade_id فقط كمعرّف داخلي للتتبع الإداري (مثلاً لحذف درس لو
    تبيّن لاحقاً أنه خاطئ) - لا يُحقن أبداً بأي برومبت مستقبلي، فقط
    الحقل "lesson" النصي المجرد هو ما يُحقن.
    """
    lessons = _load_lessons()
    entry = {
        "id": len(lessons) + 1,
        "error_or_success_class": lesson_data["error_or_success_class"],
        "lesson": lesson_data["lesson"],
        "applies_to_stage": lesson_data["applies_to_stage"],
        "confidence": lesson_data["confidence_this_is_a_real_pattern"],
        "stored_at": str(datetime.now()),
        "_internal_source_trade_id": source_trade_id,  # للتتبع فقط، لا يُحقن
        "times_reinforced": 1,  # يُزاد لو نفس الدرس (تقريباً) تكرر - راجع reinforce_or_add
    }
    # ⚠️ تجنّب تكديس دروس شبه متطابقة (نفس الفئة + نص شبيه جداً) - لو
    # درس بنفس error_or_success_class موجود بنسبة تشابه نصي عالية جداً
    # (>85% تطابق كلمات)، نُعزِّزه (times_reinforced += 1) بدل تكرار
    # درس شبه مطابق، هذا بالضبط المطلوب: "نفس الفكرة تتكرر = تعزيز
    # الثقة"، لا "نفس الصفقة تُخزَّن مرتين".
    def _word_overlap(a, b):
        wa, wb = set(a.lower().split()), set(b.lower().split())
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / len(wa | wb)

    for existing in lessons:
        if existing["error_or_success_class"] != entry["error_or_success_class"]:
            continue
        if _word_overlap(existing["lesson"], entry["lesson"]) > 0.6:
            existing["times_reinforced"] = existing.get("times_reinforced", 1) + 1
            existing["stored_at"] = entry["stored_at"]
            _save_lessons(lessons)
            logger.info(
                f"✅ [Lesson] درس مشابه موجود مسبقاً (id={existing['id']}) - "
                f"تعزيز بدل تكرار (times_reinforced={existing['times_reinforced']})"
            )
            return existing

    lessons.append(entry)
    _save_lessons(lessons)
    logger.info(f"✅ [Lesson] درس جديد محفوظ: [{entry['error_or_success_class']}] {entry['lesson'][:150]}")
    return entry


def get_relevant_lessons(stage=None, max_per_class=3, min_reinforcement=1):
    """
    يرجع نصاً جاهزاً للحقن بالبرومبت - فقط الدروس ذات الصلة بمرحلة
    محددة (أو الكل لو stage=None)، محدودة العدد (لا إغراق البرومبت).

    ⚠️ تفضيل الدروس المُعزَّزة (times_reinforced أعلى) أولاً - نفس
    فلسفة قسم [SELF_LEARNING] 17.6 الأصلي: نمط تكرر عدة مرات أوثق من
    درس واحد معزول.
    """
    lessons = _load_lessons()
    if not lessons:
        return ""

    def _is_relevant(l):
        if stage is None:
            return True
        if l.get("applies_to_stage") in (stage, "all_stages"):
            return True
        # ⚠️ ضمان بنيوي: دروس عن فئات تخص بناء SL/TP/دخول فعلياً تصل
        # دائماً لمرحلة entry أيضاً، بغض النظر عن تصنيف الموديل نفسه
        # (راجع تعليق EXECUTION_RELEVANT_CLASSES أعلاه - اكتُشف حياً
        # أن الموديل يصنّف هذه أحياناً "daily" رغم توضيح الوصف، لأن
        # السرد التحليلي الأصلي بدأ هناك، لا لأن هذا مكان تطبيقها).
        if stage == "entry" and l.get("error_or_success_class") in EXECUTION_RELEVANT_CLASSES:
            return True
        return False

    relevant = [l for l in lessons if _is_relevant(l)]
    if not relevant:
        return ""

    # فرز: التعزيز أولاً، ثم الثقة (HIGH > MODERATE > LOW)، ثم الأحدث
    conf_rank = {"HIGH": 2, "MODERATE": 1, "LOW": 0}
    relevant.sort(
        key=lambda l: (
            l.get("times_reinforced", 1),
            conf_rank.get(l.get("confidence", "LOW"), 0),
            l.get("stored_at", ""),
        ),
        reverse=True,
    )

    by_class = {}
    for l in relevant:
        cls = l["error_or_success_class"]
        by_class.setdefault(cls, [])
        if len(by_class[cls]) < max_per_class:
            by_class[cls].append(l)

    lines = [
        "\n── LESSONS FROM PAST ANALYSES (general patterns only - NOT "
        "about this specific trade, these describe recurring analytical "
        "tendencies observed across DIFFERENT prior trades) ──"
    ]
    for cls, items in by_class.items():
        for l in items:
            times = l.get("times_reinforced", 1)
            # ⚠️ إصلاح فجوة موثّقة بصدق (راجع اكتشاف #19 بالسجل، قسم
            # "القيود الموثّقة"): نفس فلسفة [SELF_LEARNING] 17.6 الأصلي
            # ("3+ تكرارات قبل اعتماد أي تعديل فعلي") - لكن هنا القرار
            # ليس "إخفاء" الدرس ذو التكرار الواحد (يتناقض مع مبدأ عدم
            # إخفاء أي معلومة بهذا المشروع)، بل **تصنيفه بصراحة** حسب
            # مستوى موثوقيته الفعلي، ليقرر النموذج بنفسه كم يثق به -
            # نفس النهج المستخدم بكل مكان آخر بهذا الكود (شفافية كاملة
            # + ترك التقدير النهائي للفهم، لا قاعدة صماء تحذف بصمت).
            if times >= 3:
                trust_tag = "CONFIRMED PATTERN (seen 3+ times)"
            elif times == 2:
                trust_tag = "seen twice"
            else:
                trust_tag = "single observation - not yet a confirmed pattern, weigh with caution"
            lines.append(f"[{cls}] ({trust_tag}) {l['lesson']}")
    lines.append(
        "⚠️ These are prior tendencies to be AWARE of, not automatic "
        "rules to force onto this specific setup - use judgment on "
        "whether the pattern genuinely applies here. A 'single "
        "observation' lesson may have been ordinary market randomness, "
        "not a real analytical error - weigh it accordingly, lower than "
        "a 'confirmed pattern' lesson seen across multiple trades."
    )
    return "\n".join(lines)


def get_lessons_stats():
    """إحصائية شفافة لعدد الدروس المخزَّنة حسب الفئة - للتشخيص."""
    lessons = _load_lessons()
    by_class = {}
    for l in lessons:
        cls = l["error_or_success_class"]
        by_class[cls] = by_class.get(cls, 0) + 1
    return {
        "total_distinct_lessons": len(lessons),
        "by_class": by_class,
        "most_reinforced": sorted(
            lessons, key=lambda l: l.get("times_reinforced", 1), reverse=True
        )[:5],
    }

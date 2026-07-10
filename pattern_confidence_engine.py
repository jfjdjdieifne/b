# -*- coding: utf-8 -*-
"""
pattern_confidence_engine - محرك "ثقة الأنماط المتكررة" (يوليو 2026، بطلب
صريح من المستخدم بعد نقاش حول رفض ML/RL صندوق أسود):

════════════════════════════════════════════════════════════════════
الفلسفة (كلام المستخدم حرفياً، لأنه دقيق ومهم):
  "بدنا نضل بنسبة دقة ونجاح عالي، ما بدي نصير فقط مراهنات - شغلنا
   تحليل علمي نحنا مو تنجيم بدون سبب. بس كمان في شغلة مهمة: إذا شغلة
   تكررت كتير ونجحت أو عطت نفس النتيجة المتوقعة، فيعزز ويصير يثق فيها
   بنسبة معينة."

المطلوب بالضبط: تعزيز ثقة **حقيقي** مبني على تكرار فعلي موثّق، لكن:
  1. حتمي 100% (بايثون بحت، صفر AI/ML/صندوق أسود - نفس مبدأ المشروع
     الأساسي: الموديل اللغوي ممنوع يخترع أرقام، وهذا يشمل منع أي
     نموذج تعلّم آلي "يحسب احتمالية" بدل الحساب الرياضي المباشر).
  2. شفاف بالكامل - أي رقم ثقة يظهر، يمكن تتبعه لصفقات محددة بالضبط
     (لا "صندوق أسود" زي CatBoost/LightGBM/RL يرفض المستخدم استخدامها
     صراحة لنفس السبب: "مرفوض تصويت عدة موديلات AI لحساب رياضيات
     حتمية").
  3. **محصّن ضد "صدفة صغيرة توهمنا بثقة عالية"** - هذا أهم جزء: لو نمط
     تكرر مرتين وربح مرتين، هذا مش "100% نجاح"، هذا عيّنة أصغر من أن
     تُستخدَم إحصائياً. الحل: Wilson Score Confidence Interval (معادلة
     إحصائية قياسية معروفة تُستخدَم فعلياً بمجالات كثيرة لضبط "تقييمات
     بعدد قليل من الأصوات" - مثلاً تصنيف منتجات Amazon/Reddit) بدل
     النسبة الخام. Wilson يعطي **الحد الأدنى المضمون بثقة 95%** الذي
     يهبط تلقائياً كلما كانت العيّنة أصغر، حتى لو النسبة الخام 100%.

════════════════════════════════════════════════════════════════════
كيف تُبنى "بصمة النمط" (Pattern Signature):
  - تُشتق **حصراً** من مخرجات `ict_entry_checklist_engine.evaluate_all_
    entry_models()` الموجودة أصلاً (لا حساب جديد مُخترَع لهذا الغرض) -
    اسم النموذج (A/B/C) + حالة كل شرط بالضبط (True/False/PENDING) لكل
    شرط بذلك النموذج تحديداً. هذا يعني نمطين يُعتبران "نفس البصمة" فقط
    لو تطابقا تماماً بكل شرط هيكلي - دقة عالية مقصودة (بدل تعميم فضفاض
    مثل "كل صفقات Model B" الذي يخلط حالات مختلفة جداً ببعض).
  - **لا يشمل** أي رقم سعر/تاريخ/رمز عملة (نفس مبدأ lesson_learning.py
    "درس مجرّد لا حفظ ببغائي") - البصمة نمط تحليلي عام قابل للتكرار
    عبر أي رمز/تاريخ.

كيف يُستخدَم الرقم الناتج:
  - **معلوماتي بحت بالحقن بالبرومبت** - نفس فلسفة `_risk_management_
    report`: يُعرَض للموديل كسياق إضافي ("هذا النمط تكرر N مرة تاريخياً،
    W ربح وL خسارة، حد الثقة الأدنى (Wilson 95%) = X%") - **لا يُلغي
    ولا يتجاوز أي فحص هيكلي حاسم** (SL_NOT_STRUCTURAL،
    SIGNAL_CONTRADICTS_DAILY_BIAS تبقى صارمة تماماً كما هي بغض النظر
    عن أي رقم ثقة).
  - عيّنة أقل من `MIN_SAMPLE_SIZE` (افتراضياً 8) → توسم صراحة
    "INSUFFICIENT_DATA" ولا يُعرض أي رقم ثقة مطلقاً - فقط "أول ظهور
    موثّق لهذا النمط، لا بيانات كافية بعد للحكم عليه إحصائياً".
"""
import json
import math
import os
from datetime import datetime

from config import Config

PATTERN_STATS_FILE = os.path.join(Config.DATA_DIR, "pattern_stats.json")

# ⚠️ حد أدنى صريح لعدد مرات التكرار قبل عرض أي رقم ثقة إحصائي - أقل من
# هذا العدد لا يمكن الوثوق فيه رياضياً بغض النظر عن نسبة النجاح الخام
# (مثال: 2 من 2 ربح = 100% نسبة خام، لكن عيّنة حجمها 2 لا تعني شيئاً
# إحصائياً - Wilson نفسه سيهبط بها لحد أدنى منخفض جداً، لكن هذا الحد
# الإضافي يمنع حتى عرض أي رقم إطلاقاً قبل تراكم بيانات كافية).
MIN_SAMPLE_SIZE = 8

# مستوى الثقة الإحصائي المستخدم بمعادلة Wilson (95% قياسي وشائع)
_Z_95 = 1.959963985


def wilson_lower_bound(wins, total, z=_Z_95):
    """
    ⚠️ معادلة رياضية قياسية معروفة (Wilson Score Interval - Edwin B.
    Wilson، 1927)، حتمية 100% بايثون بحت، صفر تخمين/AI. تُستخدَم فعلياً
    لتقييم "معدلات نجاح بعيّنات صغيرة" بمجالات كثيرة (تقييمات المنتجات،
    تصنيف التعليقات) تحديداً لأنها تتجنب مشكلة "النسبة الخام المضلِّلة
    بعيّنة صغيرة" (مثال: 1 من 1 = 100% نسبة خام، لكن Wilson lower bound
    لعيّنة حجمها 1 يهبط لقيمة منخفضة جداً بثقة).

    Returns: الحد الأدنى المضمون بثقة 95% لمعدل النجاح الحقيقي (0.0-1.0).
    قيمة صفر لو total<=0.
    """
    if total <= 0:
        return 0.0
    phat = wins / total
    denom = 1.0 + (z * z) / total
    center = phat + (z * z) / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + (z * z) / (4 * total)) / total)
    return max(0.0, (center - margin) / denom)


def compute_pattern_signature(chosen_model):
    """
    يبني بصمة نص حتمية (deterministic string) من نتيجة evaluate_model_*
    (قاموس {"model", "status", "conditions": [...], ...}) - مشتقة حصراً
    من حسابات بايثون موجودة أصلاً، صفر رقم/تاريخ محدد بالبصمة.

    Args:
        chosen_model: dict بنفس بنية evaluate_model_a/b/c() الفعلية.

    Returns: str بصمة، أو None لو المدخل غير صالح.
    """
    if not chosen_model or "model" not in chosen_model:
        return None
    parts = [chosen_model["model"]]
    for c in chosen_model.get("conditions", []):
        # نطبّع True/False/"PENDING" لنص مختصر موحّد
        status = c.get("status")
        status_str = "T" if status is True else ("F" if status is False else "P")
        parts.append(f"{c.get('name')}={status_str}")
    return "|".join(parts)


def _load_stats():
    if os.path.exists(PATTERN_STATS_FILE):
        try:
            with open(PATTERN_STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def _save_stats(stats):
    Config.ensure_data_dir()
    with open(PATTERN_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def record_pattern_outcome(signature, outcome_category, trade_id=None):
    """
    يسجّل نتيجة فعلية (WIN/LOSS - محسوبة رياضياً من compute_trade_outcome،
    لا رأي/تخمين) لبصمة نمط معينة.

    Args:
        signature: str من compute_pattern_signature().
        outcome_category: "WIN" أو "LOSS" فقط (نفس فئات _verdict()
            بملف human_trades_backtest.py - نتائج NEUTRAL/OPEN/AMBIGUOUS/
            UNKNOWN لا تُسجَّل هنا، لا معنى إحصائياً لصفقة لم تُحسم).
        trade_id: (اختياري) معرّف الصفقة - يُستخدَم **فقط** لمنع تسجيل
            نفس الصفقة مرتين لو أُعيد تشغيلها (لا حفظ أي رقم سعر/تاريخ
            بالبصمة نفسها - فقط قائمة IDs مُعالَجة سابقاً لمنع التكرار).

    Returns: dict بالإحصائيات المحدَّثة لهذه البصمة، أو None لو
        outcome_category ليست WIN/LOSS أو signature فارغة.
    """
    if not signature or outcome_category not in ("WIN", "LOSS"):
        return None

    stats = _load_stats()
    entry = stats.get(signature, {"wins": 0, "losses": 0, "processed_trade_ids": []})

    if trade_id is not None and trade_id in entry.get("processed_trade_ids", []):
        # ⚠️ حماية ضد ازدواج العدّ - نفس الصفقة قد تُعاد اختباراً (طلب
        # المستخدم المتكرر "لا عيد تحليل نفس الصفقة لنشوف") لا يجوز أن
        # تُحتسَب أكثر من مرة واحدة بنفس البصمة لنفس trade_id.
        return {
            "wins": entry["wins"], "losses": entry["losses"],
            "total": entry["wins"] + entry["losses"],
            "skipped_duplicate": True,
        }

    if outcome_category == "WIN":
        entry["wins"] += 1
    else:
        entry["losses"] += 1
    if trade_id is not None:
        entry.setdefault("processed_trade_ids", []).append(trade_id)
    entry["last_updated"] = str(datetime.now())

    stats[signature] = entry
    _save_stats(stats)

    total = entry["wins"] + entry["losses"]
    return {"wins": entry["wins"], "losses": entry["losses"], "total": total}


def get_pattern_confidence(signature):
    """
    يقرأ الإحصائيات الحالية لبصمة معينة (بلا تعديل) ويحسب Wilson lower
    bound. لا نداء API، لا تخمين - قراءة ملف + معادلة رياضية بحتة.

    Returns dict:
        {
            "signature": str,
            "total_occurrences": int,
            "wins": int, "losses": int,
            "raw_win_rate_pct": float أو None,
            "wilson_lower_bound_pct": float أو None,
            "sufficient_data": bool,
            "confidence_text": str (جاهز للحقن بالبرومبت كسياق معلوماتي)
        }
    """
    stats = _load_stats()
    entry = stats.get(signature, {"wins": 0, "losses": 0})
    wins, losses = entry.get("wins", 0), entry.get("losses", 0)
    total = wins + losses

    if total == 0:
        return {
            "signature": signature, "total_occurrences": 0, "wins": 0, "losses": 0,
            "raw_win_rate_pct": None, "wilson_lower_bound_pct": None,
            "sufficient_data": False,
            "confidence_text": (
                "📊 PATTERN HISTORY: هذا أول ظهور موثّق لهذا النمط التحليلي "
                "بالضبط (لا سجل سابق) - لا يوجد أي رقم ثقة إحصائي بعد. هذا "
                "معلومة سياقية بحتة، لا يؤثر على صحة/خطأ هذا القرار حالياً."
            ),
        }

    raw_rate = round(100.0 * wins / total, 1)
    sufficient = total >= MIN_SAMPLE_SIZE

    if not sufficient:
        return {
            "signature": signature, "total_occurrences": total, "wins": wins, "losses": losses,
            "raw_win_rate_pct": raw_rate, "wilson_lower_bound_pct": None,
            "sufficient_data": False,
            "confidence_text": (
                f"📊 PATTERN HISTORY: هذا النمط التحليلي بالضبط تكرر {total} "
                f"مرة سابقاً فقط ({wins} ربح، {losses} خسارة = {raw_rate}% نسبة "
                f"خام) - **عيّنة أصغر من الحد الأدنى ({MIN_SAMPLE_SIZE}) اللازم "
                f"للوثوق برقم إحصائي**. لا يُعرض حد ثقة Wilson بعد. معلومة "
                f"سياقية بحتة فقط - لا تعتبرها دليلاً كافياً على نجاح/فشل "
                f"متوقع، ولا تستخدمها لتبرير قرار أقوى مما تسمح به الأدلة "
                f"الهيكلية الحالية وحدها."
            ),
        }

    wilson_pct = round(100.0 * wilson_lower_bound(wins, total), 1)
    return {
        "signature": signature, "total_occurrences": total, "wins": wins, "losses": losses,
        "raw_win_rate_pct": raw_rate, "wilson_lower_bound_pct": wilson_pct,
        "sufficient_data": True,
        "confidence_text": (
            f"📊 PATTERN HISTORY (statistically meaningful sample): هذا النمط "
            f"التحليلي بالضبط تكرر {total} مرة سابقاً موثّقة - {wins} ربح، "
            f"{losses} خسارة ({raw_rate}% نسبة خام). حد الثقة الأدنى المضمون "
            f"بثقة 95% (Wilson Score) = {wilson_pct}% - أي حتى بأسوأ تفسير "
            f"إحصائي معقول للعيّنة، معدل النجاح الحقيقي غالباً لا يقل عن هذا "
            f"الرقم. هذه معلومة سياقية تعزيزية فقط (لا تلغي أي فحص هيكلي "
            f"حاسم مثل SL_NOT_STRUCTURAL أو SIGNAL_CONTRADICTS_DAILY_BIAS - "
            f"تلك تبقى شرط قبول/رفض بغض النظر عن أي رقم هنا)."
        ),
    }

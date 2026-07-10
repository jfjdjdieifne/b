# -*- coding: utf-8 -*-
"""
MultiPassAnalysis - محرك التحليل متعدد المراحل (Top-Down ICT Real Workflow)
════════════════════════════════════════════════════════════════════
⚠️ إعادة بناء كاملة (v2) بطلب صريح من المستخدم:
"فكر بطريقة كيف مايكل صاحب ICT بيفكر لما يحلل خطوة خطوة - اعتمد نفس
منهجية تفكيره. أكيد ما بيحلل 160 ألف توكن مع بعض، أكيد بيمشي مرحلة
مرحلة، وأوقات بيقاطعهم، وبالآخر بيقاطع كل المراحل مع بعض."

لماذا النسخة الأولى (v1) كانت ناقصة رغم أنها عالجت "Lost in the
Middle":
  النسخة الأولى قسّمت الدستور لـ5 مواضيع (نظرة شمولية، هيكل، مناطق،
  دخول، تركيب) - لكن كل المراحل كانت تشتغل على *نفس الفريم الزمني*
  (نفس الشموع). هذا ليس كيف يفكر تاجر ICT حقيقي فعلياً - مايكل (ICT)
  لا يحلل فريماً واحداً من 5 زوايا مختلفة، هو يحلل **فريمات مختلفة
  فعلياً** بترتيب هرمي صارم من الأكبر للأصغر:

    Weekly (القصة الكبيرة، أين السيولة الكبرى)
      → Daily (الانحياز - القائد الذي تخدمه كل الصفقات)
        → 4H (السياق - المناطق المُنقّحة والهيكل)
          → 1H (التكتيك - هل يتشكّل دخول؟)
            → Entry TF (التنفيذ - الصفقة الدقيقة)

  هذا بالضبط قسم [TOP_DOWN_WORKFLOW] (12.1-12.6) الموجود أصلاً
  بالدستور - لكن لم يكن يُطبَّق فعلياً بالكود، فقط "مذكوراً" بالنص.

كيف يعمل الآن (v2):
  1. يجلب بيانات حقيقية لكل فريم (Weekly, Daily, 4H, 1H, Entry) -
     منتهية عند نفس اللحظة بالضبط (لا تسريب مستقبلي بوضع الباك تيست)
  2. كل مرحلة تحصل على: (أ) فقط قسم الدستور المرتبط بمهمتها،
     (ب) بيانات الفريم الخاص بها فقط، (ج) ملخص نصي قصير من المرحلة
     الأعلى (وليس بياناتها الخام - "الانحياز اليومي" مثلاً، لا كل
     شموع اليوم)
  3. **GATES حقيقية** (نفس منطق الدستور 12.2-12.6 بالضبط): لو مرحلة
     معينة أعطت نتيجة "غير واضح" أو ثقة منخفضة، **يتوقف التحليل فوراً
     ويُصدر HOLD** - بدون إهدار نداءات API على مراحل لاحقة لا معنى
     لها (تماماً متل ما تاجر خبير ما بيضيع وقته يحلل فريم صغير إذا
     الانحياز اليومي أصلاً مش واضح). هذا **يوفر حصة API** بدل
     استهلاكها دائماً بـ5 نداءات ثابتة.
  4. المرحلة الأخيرة (Entry TF) **تقاطع كل المراحل السابقة مع بعض**
     صراحة قبل إصدار القرار النهائي - هذا الـ"تقاطع بالآخر" الذي
     طلبه المستخدم تحديداً.

⚠️ صدق تقني كامل: عدد نداءات API الآن **متغيّر** (1 إلى 5) حسب نتائج
الـGates - هذا أفضل لصحة الحصة اليومية من التصميم الثابت v1 (كان
دائماً 5 نداءات)، لكنه يعني أن بعض التحليلات ستتوقف مبكراً بـHOLD
دون الوصول لمرحلة التنفيذ - هذا هو **السلوك الصحيح** (رفض التحليل
حين لا يوجد انحياز واضح، بدل إجبار قرار)، وليس عيباً.
"""
import json
import logging
import re

from config import Config
from openrouter_client import OpenRouterClient
from signal_schema import normalize_signal_dict
from knowledge_sections import get_stage_knowledge
import lesson_learning


# ── خريطة الفريمات الهرمية (Top-Down) ──
# ⚠️ حل جذري معماري (يوليو 2026، بطلب صريح من المستخدم بعد بحث عميق
# موثّق بمصادر ICT متعددة - راجع الملخص المرفق بالسجل): النسخة
# السابقة كانت تستخدم Weekly→Daily→4H→1H (فريم أدنى للتنفيذ = ساعة
# واحدة). هذا لا يطابق منهجية مايكل هدلستون (ICT) الحقيقية إطلاقاً -
# موثّق حرفياً من عدة مصادر مستقلة أن ICT يستخدم:
#   - Daily + 4H: فقط لتحديد الانحياز (Bias) - صفر تنفيذ هنا مطلقاً
#   - 15 دقيقة: تحديد السيولة (Equal Highs/Lows)، الـFVGs، ونطاق
#     الجلسة (Overnight Range للكريبتو - راجع ict_sessions.py) - هذه
#     المرحلة "التكتيكية" (تطابق دور 1H بالبنية القديمة لكن على فريم
#     أدق بكثير، كما يفعل ICT فعلياً)
#   - 1-5 دقائق: التنفيذ الفعلي (تأكيد MSS/CHoCH/CISD + الدخول عند
#     FVG/OB بدقة) - "لا تنزل تحت فريم الدقيقة الواحدة، الضجيج يطغى"
#     (موثّق حرفياً من مصدر متخصص بالـSilver Bullet)
# Weekly أُبقيت اختيارياً كسياق إضافي فقط (لا Gate لها أصلاً بالدستور
# القديم بالفعل: "Weekly does NOT gate the workflow") - لم تُحذف لأن
# حذفها كان سيفقد سياقاً حقيقياً مفيداً، لكنها لم تعد جزءاً من "سلسلة
# التنفيذ" الأساسية بمنهجية ICT الحرفية.
HTF_CHAIN = ["1w", "1d", "4h", "15m"]

# ⚠️ فريم التنفيذ الفعلي (Entry TF) الافتراضي الجديد - كان الكود
# القديم يستقبل "timeframe" كمعامل خارجي (عادة "1h" من نقطة الدخول)
# ويستخدمه حرفياً كفريم التنفيذ الأخير. الآن نفرض حداً أقصى منطقياً:
# لو تم تمرير أي فريم أكبر من 15 دقيقة كـEntry TF (توافقاً خلفياً مع
# استدعاءات قديمة)، نصحّحه تلقائياً لأقرب فريم تنفيذ ICT حقيقي (5m) -
# بدل السماح بتنفيذ فعلي على فريم ساعة كامل (يخالف المنهجية تماماً).
_VALID_EXECUTION_TIMEFRAMES = ("1m", "3m", "5m")
_DEFAULT_EXECUTION_TIMEFRAME = "5m"


class MultiPassAnalysis:
    """ينسّق تحليل Top-Down حقيقي عبر فريمات مختلفة فعلياً + Gates"""

    def __init__(self, brain_core):
        self.brain = brain_core
        self.ai: OpenRouterClient = brain_core.ai
        self.dm = brain_core.data_manager
        self.authenticity = brain_core.authenticity
        # ⚠️ إصلاح فجوة معمارية حقيقية مُكتشفة (يوليو 2026، تدقيق شامل
        # كامل للمشروع بطلب المستخدم): brain_core.py (المسار الحي
        # القديم) يستخدم طبقتي حماية ناضجتين فعلياً بكل تحليل -
        # self.verifier (VerificationLayer: يتحقق R:R محسوب فعلياً،
        # الأسعار مذكورة ضمن مدى حقيقي) وself.risk_manager (RiskManager:
        # يرفض BUY/SELL باتجاه SL/TP معكوس، يحسب حجم المركز) - **لكن
        # multi_pass_analysis.py (المسار الجديد المستخدم بكل الباك تيست
        # منذ بداية هذه الجلسة) كان مبنياً بمعزل تام عنهما**. هذا يفسر
        # جذرياً كل أخطاء "SL معكوس" و"R:R غير محسوب فعلياً" المكتشفة -
        # الحماية كانت **موجودة أصلاً بالمشروع** لكن غير متصلة بهذا
        # المسار. الحل الصحيح: ربط حقيقي بنفس الأدوات الناضجة الموجودة
        # (لا إعادة اختراعها من الصفر بمنطق مختلف قد يتناقض معها).
        self.verifier = brain_core.verifier
        self.risk_manager = brain_core.risk_manager
        self.logger = logging.getLogger("MultiPassAnalysis")

    # ══════════════════════════════════════════════════════════
    #  الدالة الرئيسية
    # ══════════════════════════════════════════════════════════

    def run(self, symbol, timeframe, mtf_data, mtf_indicators, is_backtest=False,
            end_ts=None):
        """
        يشغّل التحليل الهرمي الكامل: Weekly → Daily → 4H → 1H → Entry.

        Args:
            symbol, timeframe: نفس معنى full_analysis العادية (timeframe
                هنا هو "Entry TF" بمصطلح ICT - الفريم المطلوب تحديد
                صفقة عليه فعلياً)
            mtf_data, mtf_indicators: بيانات الـEntry TF (متوافقة مع
                واجهة full_analysis العادية - نستخدمها كفريم التنفيذ)
            is_backtest: وضع الباك تيست (يفرض BUY/SELL، لا HOLD اختياري)
            end_ts: (لوضع الباك تيست) timestamp نهاية البيانات المسموحة -
                نجلب كل فريمات الـHTF منتهية عند نفس اللحظة بالضبط
                (منع تسريب مستقبلي - نفس مبدأ KnownSetupsFinder)
        """
        stage_log = {}
        entry_data = mtf_data.get("entry", {})
        entry_ind = mtf_indicators.get("entry", {})
        entry_candles_text = self.brain._format_candles(entry_data, Config.AI_CANDLES_ENTRY)
        entry_indicators_text = self.brain.ta.compact_summary(entry_ind) if entry_ind else ""

        # ═══ جلب بيانات فريمات الـHTF (Weekly/Daily/4H/15m) ═══
        # في وضع الباك تيست: منتهية عند end_ts بالضبط (لا تسريب مستقبلي)
        # في الوضع الحي: أحدث بيانات متاحة مباشرة
        pinned_exchange = None if is_backtest else entry_data.get("source")
        htf_data = self._fetch_htf_chain(
            symbol, end_ts, is_backtest, exchange=pinned_exchange
        )

        # ⚠️ حل جذري (يوليو 2026، بطلب صريح من المستخدم):
        # حقن معلومات الجلسة الزمنية (Kill Zone مفعلة/غير مفعلة، النطاق
        # الليلي) - "الوقت أهم من السعر" بمنهجية ICT. نستخدم آخر
        # timestamp متاح فعلياً (end_ts بوضع الباك تيست، أو آخر شمعة 15m بالوضع
        # الحي) - لا وقت الخادم الحالي (يُفسد مبدأ منع تسريب المستقبل
        # بوضع الباك تيست لو استخدمنا وقت التشغيل الفعلي بالخطأ).
        session_text = ""
        effective_ts = end_ts
        if effective_ts is None:
            h15_ts_list = (htf_data.get("15m") or {}).get("timestamps", [])
            if h15_ts_list:
                effective_ts = h15_ts_list[-1]
        if effective_ts is not None:
            try:
                from ict_sessions import session_prose, compute_overnight_range
                session_text = "\n" + session_prose(effective_ts)
                overnight = compute_overnight_range(htf_data.get("15m") or {}, effective_ts)
                if overnight.get("found"):
                    session_text += (
                        f"\nOvernight Range (00:00-08:30 NY, crypto-adapted Asian Range "
                        f"substitute - see [ICT_TIME_AND_SESSIONS] 9.1B): high="
                        f"{overnight['range_high']}, low={overnight['range_low']} "
                        f"(built {overnight['range_start_ny']} to {overnight['range_end_ny']} NY)."
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ Session/overnight-range computation failed (non-fatal): {e}")

        # ═══ STEP 1: WEEKLY → NARRATIVE (لا Gate - يمرّ دائماً، القسم
        # 12.2 بالدستور: "Weekly does NOT gate the workflow") ═══
        # ⚠️ توسيع جوهري (يوليو 2026، بطلب صريح من المستخدم: "شوف كيف
        # يصير خارق التفكير" - تمديد نفس فكرة _authenticity_block التي
        # كانت محصورة بمرحلة entry فقط لتشمل كل المراحل الخمس): قبل هذا
        # التعديل، مراحل Weekly/Daily/4H/1H (4 من 5 مراحل بالكامل!) كانت
        # تعتمد 100% على قدرة النموذج على "فهم" تعريف رياضي نصي (قسم
        # [SWING_DETECTION] مثلاً) وتطبيقه بنفسه من الصفر على جدول شموع
        # خام - بلا أي تحقق مستقل مسبق وقت اتخاذ القرار نفسه (فقط مرحلة
        # entry الأخيرة كانت تحصل على "سقالة رياضية" جاهزة). هذا بالضبط
        # مصدر أخطاء حقيقية موثّقة هذه الجلسة (تصنيف HH/LH معكوس، BOS
        # محسوب بشكل معكوس رياضياً) - النموذج "يعرف" القاعدة نصياً لكن
        # يُخطئ بتطبيقها حسابياً أحياناً. الحل: نفس منهج mرحلة entry
        # يُطبَّق الآن على كل مرحلة بفريمها الخاص - قمم/قيعان مهمة فعلياً
        # (مفلترة رياضياً من النتوءات الصغيرة)، آخر sweep مصنَّف، BOS/
        # CHoCH محسوبين مستقلين - تُحقن كـ"أدلة سابقة يتحقق منها النموذج"
        # (لا "يخترعها من الصفر") - هذا لا يستبدل فهم النموذج، بل يعطيه
        # سقالة رياضية موثوقة يبني عليها تفسيره واستنباطه، تماماً كما
        # يفعل تاجر خبير يحسب بسرعة قمماً/قيعاناً بعين مدرَّبة قبل بناء
        # قصة السوق - الفهم والحساب معاً، لا أحدهما بدل الآخر.
        weekly_data = htf_data.get("1w")
        weekly_authenticity = self._authenticity_block(weekly_data) + self._lesson_block("weekly")
        self.logger.info("🔍 [Top-Down 1/5] WEEKLY → Narrative (القصة الكبيرة)...")
        weekly_result = self._run_stage(
            "weekly", self._build_weekly_prompt(symbol, weekly_data, weekly_authenticity),
            self._weekly_schema(),
        )
        # \u26a0\ufe0f \u062a\u0648\u062b\u064a\u0642 \u0635\u0631\u064a\u062d (\u064a\u0648\u0644\u064a\u0648 2026\u060c \u0628\u0639\u062f \u0625\u0635\u0644\u0627\u062d \u062c\u0630\u0631\u064a \u0644\u0640_run_stage): \u0645\u0631\u062d\u0644\u0629
        # Weekly \u0644\u064a\u0633 \u0644\u0647\u0627 Gate \u0628\u0627\u0644\u062a\u0635\u0645\u064a\u0645 (\u0627\u0644\u062f\u0633\u062a\u0648\u0631 12.2: "Weekly does NOT gate
        # the workflow") - \u0644\u0648 \u0641\u0634\u0644\u062a \u0643\u0644 \u0645\u062d\u0627\u0648\u0644\u0627\u062a _run_stage (\u0628\u0639\u062f \u0627\u0644\u0625\u0635\u0644\u0627\u062d\u060c
        # \u062a\u064f\u0631\u062c\u0639 {} \u0641\u0627\u0631\u063a\u0629 \u0645\u0648\u062b\u0642\u0629 \u0628\u0627\u0644\u0640log \u0628\u062f\u0644 raw_response \u0641\u0627\u0633\u062f - \u0631\u0627\u062c\u0639
        # _validate_required_fields \u0623\u0639\u0644\u0627\u0647)\u060c \u0627\u0644\u0645\u0633\u0627\u0631 \u064a\u0633\u062a\u0645\u0631 \u0639\u0645\u062f\u0627\u064b \u0628\u0642\u064a\u0645\u0629
        # weekly_result={} - \u0647\u0630\u0627 \u0645\u0642\u0635\u0648\u062f \u0648\u0622\u0645\u0646 (\u0644\u0627 \u064a\u062d\u062c\u0628 \u0627\u0644\u0645\u0633\u0627\u0631 \u0628\u0644\u0627 \u062f\u0627\u0639\u064d
        # \u062d\u0642\u064a\u0642\u064a)\u060c \u0644\u0643\u0646 \u064a\u0645\u064f\u0631\u0651\u0631 \u0644\u0645\u0631\u0627\u062d\u0644 Daily/4H/Entry \u0628\u0648\u0636\u0648\u062d \u0643\u0643\u0627\u0626\u0646 JSON
        # \u0641\u0627\u0631\u063a \u0635\u0631\u064a\u062d ({}) \u0628\u062f\u0644 \u0646\u0635 \u0645\u0636\u0644\u0651\u0644 \u064a\u0628\u062f\u0648 \u0648\u0643\u0623\u0646\u0647 \u0628\u064a\u0627\u0646\u0627\u062a \u0635\u0627\u0644\u062d\u0629
        # (\u0627\u0644\u0641\u0631\u0642 \u0627\u0644\u062c\u0648\u0647\u0631\u064a \u0628\u064a\u0646 "\u0644\u0627 \u0628\u064a\u0627\u0646\u0627\u062a" \u0648"\u0628\u064a\u0627\u0646\u0627\u062a \u0641\u0627\u0633\u062f\u0629 \u062a\u0628\u062f\u0648 \u0635\u0627\u0644\u062d\u0629" -
        # \u0647\u0630\u0627 \u0628\u0627\u0644\u0636\u0628\u0637 \u0627\u0644\u062e\u0644\u0644 \u0627\u0644\u0630\u064a \u0633\u0628\u0651\u0628 \u0627\u0644\u0641\u0634\u0644 \u0627\u0644\u0645\u0648\u062b\u0651\u0642 \u0628\u0627\u0644\u0627\u062e\u062a\u0628\u0627\u0631 \u0627\u0644\u062d\u064a).
        if not weekly_result:
            self.logger.warning(
                "\u26a0\ufe0f \u0645\u0631\u062d\u0644\u0629 Weekly \u0641\u0634\u0644\u062a \u0628\u0639\u062f \u0643\u0644 \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0627\u062a - "
                "\u0627\u0644\u0645\u062a\u0627\u0628\u0639\u0629 \u0628\u0644\u0627 \u0633\u064a\u0627\u0642 Weekly \u0637\u0628\u0642\u0627\u064b \u0644\u0644\u062f\u0633\u062a\u0648\u0631 (\u0644\u0627 Gate \u0644\u0647\u0630\u0647 \u0627\u0644\u0645\u0631\u062d\u0644\u0629)\u060c "
                "\u0644\u0643\u0646 \u0647\u0630\u0627 \u064a\u064f\u0648\u062b\u0651\u0642 \u0635\u0631\u0627\u062d\u0629\u064b \u0628\u0627\u0644\u0640log \u0644\u0644\u0634\u0641\u0627\u0641\u064a\u0629 \u0627\u0644\u0643\u0627\u0645\u0644\u0629."
            )
        stage_log["weekly"] = weekly_result

        # ═══ STEP 2: DAILY → BIAS (GATE 2: لو الانحياز غير واضح، توقف) ═══
        # ⚠️ SMT Divergence (أُضيف بطلب المستخدم بعد مراجعة كتب ICT الرسمية): يُحسب
        # فقط لو بيانات الأصل المقارن (SMT counterpart) توفرت فعلياً (راجع
        # _fetch_htf_chain أعلاه) - تحقق رياضي بحت مستقل عن الذكاء الاصطناعي،
        # يُحقي بالبرومبت كدليل إضافي فقط (لا يُغيّر مسار القرار وحده) - نفس
        # فلسفة "لا قرار مستقل من الذكاء الاصطناعي لوحده" المطبّقة بكل مكان آخر
        # بهذا الملف (query_json_race إلخ).
        smt_text = ""
        counterpart_data = htf_data.get("smt_counterpart_1d")
        daily_data = htf_data.get("1d")
        if counterpart_data and daily_data:
            try:
                counterpart_symbol = self._SMT_COUNTERPART.get(symbol, "")
                smt = self.authenticity.detect_smt_divergence(
                    daily_data, counterpart_data,
                    label_a=symbol.split("/")[0], label_b=counterpart_symbol.split("/")[0],
                )
                if smt.get("checked") and (smt.get("bullish_divergence") or smt.get("bearish_divergence")):
                    smt_text = (
                        "SMT DIVERGENCE CHECK (mechanically computed vs correlated asset, "
                        "independent of AI interpretation - see ICT foundational material): "
                        f"{smt.get('detail', '')}"
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ SMT divergence check failed (non-fatal): {e}")

        daily_authenticity = self._authenticity_block(daily_data) + self._lesson_block("daily")
        self.logger.info("🔍 [Top-Down 2/5] DAILY → Bias (الانحياز - القائد)...")
        daily_result = self._run_stage(
            "daily", self._build_daily_prompt(symbol, daily_data, weekly_result, smt_text, daily_authenticity),
            self._daily_schema(),
        )
        daily_result = self._verify_and_retry_structure_math(
            "daily", daily_result, "daily_bias_summary", daily_data,
            lambda: self._build_daily_prompt(
                symbol, daily_data, weekly_result, smt_text,
                self._authenticity_block(daily_data) + self._lesson_block("daily"),
            ),
            self._daily_schema(),
            direction_field="direction",
        )
        # ⚠️ حل جذري (يوليو 2026، بحث خارجي معمّق + طلب صريح من المستخدم):
        # اكتُشف حياً أن مرحلة Daily كانت تُكمل باتجاه BEARISH/BULLISH
        # حتى لو بقي تناقض رياضي/هيكلي غير محلول بعد محاولتي التصحيح
        # (_daily_math_audit["resolved"]=False) - بلا أي HOLD إجباري،
        # بعكس مرحلة "Trade Plan Validation" النهائية (لها حماية صارمة
        # مماثلة). هذا يخالف نص مايكل نفسه الموثّق خارجياً (innercircle
        # trader.net "ICT Daily Bias Explained"): "Forcing a bias when
        # the daily is unclear... there is no clean bias. Sit out.
        # There is no rule that says I must trade every session." - لو
        # التناقض الرياضي لم يُحل حتى بعد محاولتين، هذا بالضبط تعريف
        # "daily is unclear" - نفرض direction=UNCLEAR صراحة (يُفعِّل
        # GATE 2 الموجود أصلاً، بلا تعديل منطقه) بدل الاستمرار بانحياز
        # مبني على تصنيف هيكلي مثبَت خطأه رياضياً.
        if isinstance(daily_result, dict):
            audit = daily_result.get("_daily_math_audit", {})
            if audit.get("had_contradiction_initially") and not audit.get("resolved", True):
                self.logger.warning(
                    "⚠️ [Daily Bias] تناقض رياضي/هيكلي لم يُحل حتى بعد محاولتي التصحيح - "
                    "فرض direction=UNCLEAR (نفس مبدأ مايكل: 'if unclear, sit out') بدل "
                    "الاستمرار بانحياز مبني على تصنيف مثبَت خطأه."
                )
                daily_result["direction"] = "UNCLEAR"
                daily_result["_forced_unclear_due_to_unresolved_math_contradiction"] = True
        stage_log["daily"] = daily_result

        gate2 = self._check_gate2_daily(daily_result)
        if gate2["stop"]:
            return self._build_hold_result(
                "GATE 2 (Daily Bias)", gate2["reason"], stage_log, is_backtest
            )

        # ═══ STEP 3: 4H → CONTEXT (GATE 3) ═══
        h4_data = htf_data.get("4h")
        h4_authenticity = self._authenticity_block(h4_data) + self._lesson_block("h4")

        # ⚠️ حل جذري (يوليو 2026، بحث خارجي معمّق + طلب صريح من المستخدم
        # بعد اكتشاف حي: البوت رأى CHoCH صاعد بديسبليسمنت حقيقي بمرحلة
        # 4H، لكنه صنّفه تلقائياً كـ"مجرد تصحيح" بلا أي معيار كمي، فقط
        # لأن Daily=BEARISH - أدى لـ4 خسائر متتالية بينما كان انعكاساً
        # حقيقياً مؤكَّداً بـBOS تالٍ فعلياً). راجع docstring
        # classify_htf_structural_challenge للتفصيل الكامل والمصادر
        # الخارجية (6+ مصادر متطابقة): معيار مايكل الحقيقي هو "MSS/CHoCH
        # = تحذير فقط، BOS تأكيدي لاحق بنفس الاتجاه الجديد = التزام
        # حقيقي" - نحقن هذا التصنيف الحتمي (بايثون بحت) هنا كدليل جاهز،
        # بدل ترك النموذج يحكم لفظياً بلا معيار واضح.
        daily_bias_so_far = daily_result.get("direction") if isinstance(daily_result, dict) else None
        if daily_bias_so_far in ("BULLISH", "BEARISH") and h4_data:
            try:
                from ict_math_engine import classify_htf_structural_challenge
                challenge = classify_htf_structural_challenge(h4_data, higher_tf_bias=daily_bias_so_far)
                h4_authenticity += (
                    "\n\n── PRE-COMPUTED STRUCTURAL CHALLENGE ASSESSMENT (mechanically "
                    "computed, per external ICT verification - 'CHoCH is an alert, not "
                    "an entry signal; BOS validates the structure, confirming smart money "
                    "is committed to the new direction') ──\n"
                    f"Classification: {challenge['classification']}\n"
                    f"{challenge['narrative']}\n"
                    "⚠️ Only classify a 4H structure as a genuine reversal warranting "
                    "reassessment of the Daily bias if this assessment says "
                    "REAL_REVERSAL_CONFIRMED. If it says LIKELY_CORRECTION_ONLY or "
                    "NO_CHALLENGE, treat any opposing 4H structure as a corrective "
                    "pullback WITHIN the Daily trend, not a reversal - do not invent a "
                    "counter-trend narrative not supported by this mechanical evidence."
                )
            except Exception as e:
                self.logger.warning(f"⚠️ HTF structural challenge computation failed (non-fatal): {e}")

        self.logger.info("🔍 [Top-Down 3/5] 4H → Context (المناطق المُنقّحة)...")
        h4_result = self._run_stage(
            "h4", self._build_4h_prompt(symbol, h4_data, weekly_result, daily_result, h4_authenticity),
            self._h4_schema(),
        )
        stage_log["h4"] = h4_result

        gate3 = self._check_gate3_4h(h4_result)
        if gate3["stop"]:
            return self._build_hold_result(
                "GATE 3 (4H Context)", gate3["reason"], stage_log, is_backtest
            )

        # ═══ STEP 4: 15m → TACTICAL (GATE 4) - سيولة/FVGs/هيكل تكتيكي دقيق ═══
        h15_data = htf_data.get("15m")
        h15_authenticity = self._authenticity_block(h15_data) + self._lesson_block("h15")
        self.logger.info("🔍 [Top-Down 4/5] 15m → Tactical (سيولة/هيكل - هل يتشكّل دخول؟)...")
        h15_result = self._run_stage(
            "h15", self._build_15m_prompt(symbol, h15_data, daily_result, h4_result,
                                           h15_authenticity, session_text),
            self._h15_schema(),
        )
        # ⚠️ إصلاح فجوة حقيقية (يوليو 2026، بطلب المستخدم بعد اختبار حي):
        # مرحلة h1 هي بالضبط مكان اتخاذ قرار "هل تشكّل MSS/CHoCH؟" - نفس
        # عملية مقارنة قمة/قاع بمرجعها الصحيح التي تفشل بها الأخطاء
        # الموثقة (راجع _verify_and_retry_structure_math). كانت هذه
        # الحماية مقصورة على Daily فقط رغم أن h1 معرّضة لنفس الخطر
        # بالضبط - بل أكثر خطورة لأنها القرار المباشر لفتح الصفقة.
        h15_result = self._verify_and_retry_structure_math(
            "h15", h15_result, "tactical_summary", h15_data,
            lambda: self._build_15m_prompt(
                symbol, h15_data, daily_result, h4_result,
                self._authenticity_block(h15_data) + self._lesson_block("h15"),
                session_text,
            ),
            self._h15_schema(),
            direction_field="structural_shift_direction",
            direction_map={"UP": "BULLISH", "DOWN": "BEARISH", "NONE": None},
        )
        stage_log["h15"] = h15_result


        gate4 = self._check_gate4_15m(h15_result, is_backtest)
        if gate4["stop"]:
            return self._build_hold_result(
                "GATE 4 (15m Tactical)", gate4["reason"], stage_log, is_backtest
            )

        # ═══ STEP 5: ENTRY TF → EXECUTION + التقاطع النهائي بين كل
        # المراحل (الطلب الصريح: "بالآخر بيقاطع كل المراحل مع بعض") ═══
        self.logger.info("🔍 [Top-Down 5/5] ENTRY TF → Execution (التقاطع النهائي)...")
        entry_authenticity_text = self._authenticity_block(entry_data) + self._lesson_block("entry")

        # ⚠️ حل جذري (يوليو 2026، طلب صريح من المستخدم - راجع
        # docstring _build_mechanical_checklist_block للتفصيل الكامل):
        # حساب تفكيك ميكانيكي صريح لشروط نماذج الدخول (A/B/C) قبل بناء
        # برومبت entry - يُحقن كنص جاهز + يُحفظ (checklist_result) هنا
        # لاستخدامه لاحقاً بفحص "HOLD متهرّب" بعد الرد (راجع أسفل).
        daily_bias_for_checklist = daily_result.get("direction") if isinstance(daily_result, dict) else None
        # ⚠️ حل جذري (يوليو 2026، راجع docstring find_tp_targets بـ
        # ict_math_engine.py للتفصيل الكامل): نمرر بيانات فريم أعلى
        # (4H مفضَّلة، Daily احتياط) لحساب TP2 (Draw on Liquidity)
        # الاستراتيجي الحقيقي - بدل الاكتفاء بأفق فريم التنفيذ الضيق.
        # هذه البيانات مجلوبة أصلاً بنفس end_ts (لا تسريب مستقبلي،
        # نفس الحماية المطبَّقة على h4_data/daily_data بكل مكان آخر).
        # ⚠️ حل "مرن ديناميكي" (يوليو 2026، طلب صريح: "بشكل خارق...
        # مرن ديناميكي عارف وين كل شغلة عم تصير"): بدل مصدر HTF ثابت
        # واحد، نمرر **قائمة أولوية مرتّبة** - Daily أولاً (نص الدستور
        # قسم 12.3: "Daily Draw on Liquidity... the PRIMARY target for
        # today's trades" - تحقق رياضي مباشر أكّد هذا عملياً: TP2 من
        # Daily وقع داخل نطاق هدف البشري الفعلي 2123-2200 بالضبط،
        # بينما TP2 من 4H كان أقرب بكثير وأقل قيمة استراتيجية)، ثم 4H
        # كبديل تلقائي فقط لو Daily لم ينتج مرشحاً حقيقياً صالحاً (مثلاً
        # كل مستويات Daily خلف TP1 أو بيانات غير كافية) - find_tp_targets
        # تفحص كل مصدر بالترتيب وتستخدم أول نتيجة صالحة، بلا تجميد على
        # مصدر واحد وبلا اختراع رقم لو كل المصادر فشلت.
        htf_data_sources_for_tp2 = [("Daily", daily_data), ("4H", h4_data)]
        checklist_text, checklist_result = self._build_mechanical_checklist_block(
            entry_data, daily_bias_for_checklist, htf_data_sources=htf_data_sources_for_tp2,
            htf_major_data=daily_data,
        )
        entry_authenticity_text = entry_authenticity_text + checklist_text

        # ⚠️ حل جذري جديد (يوليو 2026، طلب صريح من المستخدم: "إذا شغلة
        # تكررت كتير ونجحت أو عطت نفس النتيجة المتوقعة، فيعزز ويصير
        # يثق فيها بنسبة معينة - بس بدنا نضل تحليل علمي مو تنجيم").
        # راجع docstring pattern_confidence_engine.py للتفصيل الكامل:
        # نحسب بصمة النمط الحتمية (من نفس مخرجات checklist أعلاه، صفر
        # حساب إضافي مُخترَع) ونحقن سجلها التاريخي الحقيقي (Wilson Score
        # على عيّنة فعلية موثّقة - لا أي رقم من عند الموديل) كسياق
        # معلوماتي بحت. **لا يغيّر أي قرار ولا يتجاوز أي فحص حاسم** -
        # فقط "هل هذا النمط بالضبط له سجل تاريخي، وإذا نعم شو هو".
        pattern_signature = None
        try:
            if checklist_result and checklist_result.get("chosen_model"):
                from pattern_confidence_engine import compute_pattern_signature, get_pattern_confidence
                pattern_signature = compute_pattern_signature(checklist_result["chosen_model"])
                if pattern_signature:
                    pattern_conf = get_pattern_confidence(pattern_signature)
                    entry_authenticity_text = entry_authenticity_text + "\n" + pattern_conf["confidence_text"]
        except Exception as e:
            self.logger.warning(f"⚠️ pattern_confidence_engine injection failed (non-fatal): {e}")

        # ⚠️ حل جذري (يوليو 2026، بطلب صريح من المستخدم بعد ملاحظة
        # أن إعادات المحاولة المتكررة تأخذ وقتاً طويلاً بلا داعٍ): "مابدي
        # يخربط وبعدين يرجع يعيد لمحاولة - بدي من أول مرة نحل جذر المشكلة
        # من الأساس". السبب الجذري الحقيقي لمعظم إعادات المحاولة
        # الموثّقة (SL_TOO_TIGHT): الموديل كان يُطلب منه يختار مسافة SL بنفسه
        # بلا أي رقم جاهز مسبقاً (فقط قاعدة نصية "SL >= 1.5xATR")، فكان
        # يخمّن رقماً ثم نكتشف بعد الرد أنه أضيق من المطلوب ونعيد طلب
        # محاولة كاملة (نداء API إضافي + دقيقة-دقيقتين مهدرة). الحل الجذري:
        # نحسب المسافة الدقيقة بوحدات السعر (مبنية على max(min_pct%، 1.5×ATR))
        # برمجياً بحتاً **قبل** أول محاولة، ونعطيه للموديل كرقم جاهز صريح بالبرومبت
        # (لا قاعدة يجب تطبيقها ذهنياً) - يختار مسافة SL أكبر من/تساوي
        # هذا الرقم مباشرة من أول محاولة، بدل ما يخمّن رقماً قد يفشل.
        # ⚠️ نفس المبدأ يُطبَّق الآن أيضاً على نطاق السعر الصحيح ككل (لا
        # فقط مسافة SL) - راجع docstring _compute_valid_price_range_hint
        # للتفصيل الكامل (اكتُشف بعد هلوسة سعر حقيقية بنداء حي: entry=
        # 98,870 خارج نطاق فعلي 72,000-82,000، كلّفت 3 محاولات فاشلة).
        min_sl_hint = self._compute_min_sl_hint(symbol, timeframe, entry_ind, entry_data,
                                                  daily_bias=daily_bias_for_checklist)
        min_sl_hint = min_sl_hint + self._compute_valid_price_range_hint(entry_data)

        # ⚠️ حل جذري جديد (يوليو 2026، طلب صريح من المستخدم بعد تحقيق
        # صفقة #10: "بدنا نحل مشكلة هلوسة الموديل من الجذر مش نستناه
        # يخبص بعدين نصلحه... منحل كل المشكلة هيك ومنصير أسرع ومنخفف
        # طلبات"). راجع docstring _deterministic_verdict_schema للتفصيل
        # الكامل: لو checklist الحتمي يعطي READY/PENDING_SETUP (خطة
        # كاملة الأرقام جاهزة رياضياً)، **لا نطلب من الموديل اختراع
        # entry/stop_loss/tp من الصفر إطلاقاً** - فقط قرار ثنائي محصور
        # (قبول الخطة الجاهزة، أو رفض بدليل محدد يتحقق منه الكود فوراً)
        # - هذا يمنع الهلوسة بنيوياً (لا مجال لتوليد أرقام أصلاً) ويمنع
        # "الالتفاف اللفظي حول شرط حقيقي" (الموديل لا يملك حقل نص حر
        # يبرر فيه HOLD - فقط enum محدود يُتحقَّق منه رياضياً)، وأسرع
        # بكثير (schema أصغر بكثير من _entry_schema الكاملة، ونداء واحد
        # بدل نداءين "evasive HOLD retry" بمعظم الحالات).
        deterministic_used = False
        # Safety: PENDING_SETUP is a watch-list scenario, never an order.
        # Auto-accept is allowed only when every gate is READY and a concrete
        # displacement-backed plan exists.
        if (checklist_result
                and checklist_result.get("final_status") == "READY"
                and checklist_result.get("chosen_model")
                and checklist_result["chosen_model"].get("plan")):
            chosen = checklist_result["chosen_model"]
            plan = chosen["plan"]
            verdict_prompt = self._build_deterministic_verdict_prompt(
                symbol, timeframe, entry_candles_text, entry_indicators_text,
                weekly_result, daily_result, h4_result, h15_result,
                entry_authenticity_text, session_text, chosen, plan,
            )
            verdict_result = self._run_stage(
                "entry", verdict_prompt, self._deterministic_verdict_schema()
            )
            if verdict_result and isinstance(verdict_result, dict):
                is_valid, verify_reason = self._verify_deterministic_rejection(
                    verdict_result, checklist_result, entry_data,
                    daily_bias_for_checklist=daily_bias_for_checklist,
                )
                if verdict_result.get("verdict") == "ACCEPT_PLAN" or not is_valid:
                    # إما قَبِل الموديل الخطة، أو رفضها برفض غير موثَّق
                    # رياضياً (نتجاهل رفضاً غير مدعوم بدليل - نفّذ الخطة
                    # الجاهزة كما هي، هذا بالضبط ما تطلبه فلسفة المشروع:
                    # "لا تفلسف لفظي بدون دليل رقمي قابل للتحقق")
                    deterministic_used = True
                    final_result = {
                        "signal": plan["direction"],
                        "bias": daily_bias_for_checklist,
                        "entry": plan["entry"], "stop_loss": plan["stop_loss"], "tp": plan["tp"],
                        "tp1": plan.get("tp1"), "tp2": plan.get("tp2"),
                        "confidence": verdict_result.get("confidence", 70),
                        "rr": str(plan.get("rr")),
                        "entry_model": chosen["model"],
                        "narrative": verdict_result.get("reasoning", ""),
                        "reasoning": verdict_result.get("reasoning", ""),
                        "archetype": f"Deterministic checklist ({chosen['model']}, {checklist_result['final_status']})",
                        "bos_reconciliation": plan.get("basis", ""),
                        "market_regime": "TRENDING_UP" if "BUY" in plan["direction"] else "TRENDING_DOWN",
                        "cross_reference_check": (
                            "Deterministic-first flow: numbers sourced directly from the mechanical "
                            "entry checklist, not model-generated - cross-reference already enforced "
                            "by daily_bias_for_checklist matching."
                        ),
                        "_deterministic_entry": True,
                        "_deterministic_rejection_reason": None if is_valid else verify_reason,
                    }
                else:
                    # رفض موثَّق فعلياً برهان رياضي - نسمح بمسار كامل
                    # عادي (الموديل قد يرى ما فاته الـchecklist من سياق
                    # حقيقي إضافي - نعطيه فرصة تحليل كامل بدل فرض الخطة).
                    # ⚠️ نُسقِط checklist_result هنا صراحة (لا نمرره
                    # لمنطق mechanical_evasive أدناه) - لأن الرفض هنا
                    # مؤكَّد رياضياً بالفعل (دليل مضاد حقيقي)، فلا معنى
                    # لإجبار العودة لنفس الخطة التي أثبتنا للتو بطلانها
                    # هيكلياً - هذا كان سيخلق تناقضاً منطقياً حقيقياً.
                    self.logger.info(
                        f"✅ [Deterministic Verdict] رفض موثَّق فعلياً برهان رياضي: {verify_reason} "
                        f"- الانتقال لمسار التحليل الكامل بدل فرض الخطة الجاهزة."
                    )
                    checklist_result = None

        if not deterministic_used:
            final_result = self._run_stage(
                "entry", self._build_entry_prompt(
                    symbol, timeframe, entry_candles_text, entry_indicators_text,
                    weekly_result, daily_result, h4_result, h15_result, is_backtest,
                    entry_authenticity_text, min_sl_hint=min_sl_hint, session_text=session_text,
                    entry_data=entry_data,
                ),
                self._entry_schema(is_backtest),
            )
        # \u26a0\ufe0f \u062d\u0644 \u062c\u0630\u0631\u064a \u0644\u0644\u0645\u0634\u0643\u0644\u0629 \u0627\u0644\u0623\u062e\u0637\u0631 \u0645\u0646 \u0646\u0648\u0639\u0647\u0627 (\u064a\u0648\u0644\u064a\u0648 2026\u060c \u0627\u0643\u062a\u064f\u0634\u0641
        # \u0628\u0627\u0644\u062a\u062d\u0644\u064a\u0644 \u0627\u0644\u0645\u0646\u0637\u0642\u064a \u0628\u0639\u062f \u0625\u0635\u0644\u0627\u062d _run_stage): \u0644\u0648 \u0641\u0634\u0644\u062a **\u0645\u0631\u062d\u0644\u0629
        # entry \u0628\u0627\u0644\u0630\u0627\u062a** \u0628\u0639\u062f \u0643\u0644 \u0645\u062d\u0627\u0648\u0644\u0627\u062a _run_stage (\u062a\u0631\u062c\u0639 {} \u0641\u0627\u0631\u063a\u0629 \u0627\u0644\u0622\u0646
        # \u0628\u062f\u0644 \u0646\u0635 \u0641\u0627\u0633\u062f)\u060c \u0641\u0625\u0646 _diagnose_trade_plan \u0644\u0627\u062d\u0642\u0627\u064b \u0644\u0646 \u062a\u062c\u062f \u0623\u064a
        # \u0645\u0634\u0643\u0644\u0629 (\u0644\u0623\u0646 signal \u0644\u064a\u0633\u062a BUY/SELL) \u0648\u0633\u062a\u064f\u0631\u062c\u0639 \u0627\u0644\u0646\u062a\u064a\u062c\u0629 \u0627\u0644\u0646\u0647\u0627\u0626\u064a\u0629
        # \u0644\u0644\u0645\u0633\u062a\u062e\u062f\u0645 **\u0641\u0627\u0631\u063a\u0629 \u062a\u0645\u0627\u0645\u0627\u064b** \u0628\u0644\u0627 \u0623\u064a signal/HOLD \u0645\u0648\u062b\u0651\u0642 - \u0623\u062e\u0637\u0631
        # \u0633\u064a\u0646\u0627\u0631\u064a\u0648 \u0645\u0645\u0643\u0646 (\u0641\u0634\u0644 \u0635\u0627\u0645\u062a \u0628\u0644\u0627 \u0623\u064a \u062a\u0648\u062b\u064a\u0642). \u0627\u0644\u062d\u0644: \u0646\u0648\u0644\u0651\u062f
        # \u0647\u064a\u0643\u0644 HOLD \u0635\u0631\u064a\u062d \u0641\u0648\u0631\u0627\u064b \u0644\u0648 \u0648\u0635\u0644\u062a final_result \u0641\u0627\u0631\u063a\u0629 \u062a\u0645\u0627\u0645\u0627\u064b \u0645\u0646
        # \u0627\u0644\u0645\u0631\u062d\u0644\u0629 \u0627\u0644\u0623\u062e\u064a\u0631\u0629 - \u0642\u0628\u0644 \u0623\u064a \u0645\u0639\u0627\u0644\u062c\u0629 \u0644\u0627\u062d\u0642\u0629 \u0642\u062f \u062a\u062a\u0639\u0627\u0645\u0644
        # \u0645\u0639\u0647\u0627 \u0628\u0634\u0643\u0644 \u062e\u0627\u0637\u0626 (\u0645\u062b\u0644\u0627\u064b .get(\"signal\") \u0628\u062f\u0648\u0646 \u0641\u062d\u0635 \u0648\u062c\u0648\u062f \u0623\u064a \u0628\u064a\u0627\u0646\u0627\u062a
        # \u0623\u0635\u0644\u0627\u064b).
        if not final_result:
            self.logger.error(
                "\u274c \u0645\u0631\u062d\u0644\u0629 entry \u0641\u0634\u0644\u062a \u0628\u0627\u0644\u0643\u0627\u0645\u0644 (\u0644\u0627 \u0631\u062f JSON \u0635\u0627\u0644\u062d \u0628\u0639\u062f \u0643\u0644 "
                "\u0645\u062d\u0627\u0648\u0644\u0627\u062a \u0627\u0644\u0625\u0639\u0627\u062f\u0629) - \u062a\u062d\u0648\u064a\u0644 \u0644\u0640HOLD \u0645\u0648\u062b\u0651\u0642 \u0635\u0631\u0627\u062d\u0629\u064b."
            )
            return self._build_hold_result(
                "STAGE 5 (Entry Execution)",
                "\u0641\u0634\u0644\u062a \u0645\u0631\u062d\u0644\u0629 \u0627\u0644\u062a\u0646\u0641\u064a\u0630 \u0628\u0627\u0644\u0643\u0627\u0645\u0644 \u0641\u064a \u0625\u0646\u062a\u0627\u062c JSON \u0635\u0627\u0644\u062d "
                "\u0645\u0637\u0627\u0628\u0642 \u0644\u0644\u0640schema \u0627\u0644\u0645\u0637\u0644\u0648\u0628 \u0628\u0639\u062f \u0643\u0644 \u0645\u062d\u0627\u0648\u0644\u0627\u062a \u0627\u0644\u0625\u0639\u0627\u062f\u0629 "
                "(\u0644\u0627 \u0646\u062e\u0631\u062c \u0646\u062a\u064a\u062c\u0629 \u0641\u0627\u0631\u063a\u0629 \u0623\u0648 \u063a\u064a\u0631 \u0645\u0648\u062b\u0651\u0642\u0629).",
                stage_log, is_backtest,
            )
        final_result = normalize_signal_dict(final_result)

        # ⚠️ حل جذري جديد (يوليو 2026، بطلب صريح من
        # المستخدم): اختبار حي فعلي أثبت نمطاً متكرراً (صفقتين
        # متتاليتين): الموديل يحدّد منطقة دخول محددة بالأرقام
        # بالنص الحر (mmm_phase=3/4، refined_zones_summary/narrative
        # يذكر أرقاماً حقيقية مثل "72863-72914")، لكنه يخرج
        # signal=HOLD بدل BUY_LIMIT/SELL_LIMIT رغم التعليمات الصريحة
        # بالبرومبت (SIGNAL TYPE ب_build_entry_prompt) - هذا "HOLD
        # متهرّب" (evasive HOLD): الموديل يفهم المنطقة فعلاً (يذكرها
        # بالأرقام بوضوح) لكنه يخلط بين "مافي إعداد قابل
        # للتحديد" (HOLD الحقيقي) و"في إعداد محدد بس السعر لم
        # يوصله بعد" (يجب BUY_LIMIT/SELL_LIMIT). الحل الجذري: كشف آلي
        # لهذا التناقض (ريجكس على أرقام فعلية مذكورة بنص h4/entry مع
        # كلمات مفتاحية تدل على "منطقة محددة لكن لم تُلمس بعد")، ثم إعادة
        # محاولة مركّزة تطلب صراحة BUY_LIMIT/SELL_LIMIT بدل إعادة صياغة
        # البرومبت الكامل (أسرع وأدق - يركّز فقط على التناقض المكتشف).
        if final_result.get("signal") == "HOLD":
            evasive = self._detect_evasive_hold(final_result, h4_result)
            # ⚠️ حل جذري إضافي (يوليو 2026، طلب صريح من المستخدم): فحص
            # ميكانيكي أقوى وأدق من الريجكس أعلاه - إن كان الـchecklist
            # الحتمي (_build_mechanical_checklist_block) يقول صراحة
            # READY أو PENDING_SETUP (كل الشروط الحقيقية متحققة، فقط
            # شروط PENDING بلا أي فشل حقيقي)، بينما الموديل أخرج HOLD -
            # هذا "HOLD متهرّب" مؤكد رياضياً 100%، لا مجرد اشتباه نصي.
            # A pending checklist is legitimate WAIT/HOLD, not an evasive
            # refusal. Only a fully READY checklist can contradict HOLD.
            mechanical_evasive = (
                checklist_result is not None
                and checklist_result.get("final_status") == "READY"
                and checklist_result.get("chosen_model", {}).get("plan") is not None
            )
            if evasive or mechanical_evasive:
                if mechanical_evasive:
                    chosen = checklist_result["chosen_model"]
                    self.logger.warning(
                        f"⚠️ [Mechanical Evasive HOLD Check] الـchecklist الحتمي يقول "
                        f"{checklist_result['final_status']} لنموذج {chosen['model']} "
                        f"لكن الموديل أخرج HOLD - إعادة محاولة مركّزة بالخطة الجاهزة..."
                    )
                else:
                    self.logger.warning(
                        f"⚠️ [Evasive HOLD Check] اكتُشف HOLD متهرّب: "
                        f"{evasive} - إعادة محاولة مركّزة تطلب BUY_LIMIT/SELL_LIMIT صراحةً..."
                    )
                correction_text = (
                    "\n\n⚠️ CRITICAL CORRECTION REQUIRED: Your previous answer output "
                    "signal=HOLD, but your OWN analysis explicitly named a specific numeric "
                    f"entry zone ({evasive}) consistent with the Daily Bias direction. Per the "
                    "SIGNAL TYPE section above, identifying a specific zone that price simply "
                    "hasn't reached yet is EXACTLY the definition of BUY_LIMIT/SELL_LIMIT, NOT "
                    "HOLD. Re-derive your answer: if that zone (or a comparably specific "
                    "genuine zone) is still valid, output BUY_LIMIT or SELL_LIMIT (matching the "
                    "Daily Bias direction) with complete entry/stop_loss/tp numbers at that "
                    "zone, placed per Michael's (ICT) structural methodology (no percentage cap "
                    "or R:R minimum applies at this stage - that is a separate informational "
                    "comparison done after this plan is finalized). Only output HOLD if, on "
                    "reflection, no such specific zone genuinely exists at all."
                ) if evasive else (
                    "\n\n⚠️ CRITICAL CORRECTION REQUIRED: Your previous answer output "
                    "signal=HOLD, but the MECHANICAL ENTRY MODEL CHECKLIST above (deterministic, "
                    f"not your judgment) shows {chosen['model']} at status "
                    f"{checklist_result['final_status']} - meaning every genuine structural "
                    "condition is met, with at most PENDING items (things that haven't happened "
                    "yet but haven't failed either). Per the user's explicit instruction: this is "
                    "NOT a valid reason for HOLD - only a condition that GENUINELY, MECHANICALLY "
                    "FAILED justifies HOLD. Re-derive your answer: output "
                    f"{chosen['plan']['direction']} using the mechanically pre-computed plan "
                    f"(entry={chosen['plan']['entry']}, stop_loss={chosen['plan']['stop_loss']}, "
                    f"tp={chosen['plan']['tp']}) unless you can cite a SPECIFIC condition from "
                    "the checklist that you believe is actually wrong (with numeric evidence), "
                    "not merely a vague reservation."
                )
                retry_prompt = self._build_entry_prompt(
                    symbol, timeframe, entry_candles_text, entry_indicators_text,
                    weekly_result, daily_result, h4_result, h15_result, is_backtest,
                    entry_authenticity_text, min_sl_hint=min_sl_hint, session_text=session_text,
                    entry_data=entry_data,
                ) + correction_text
                retry_result = self._run_stage(
                    "entry", retry_prompt, self._entry_schema(is_backtest, allow_hold=True)
                )
                retry_result = normalize_signal_dict(retry_result)
                if retry_result and isinstance(retry_result, dict):
                    final_result = retry_result
                    final_result["_evasive_hold_corrected"] = True

        # ⚠️ حماية "دفاع بالعمق" إضافية (يوليو 2026، تدقيق شامل نهائي):
        # _verify_and_finalize_trade_plan تستدعي عدة أدوات خارجية
        # (AuthenticityEngine, VerificationLayer) قد ترمي استثناءً غير
        # متوقع (مثلاً بسبب شكل بيانات غير معتاد). بدون try/except هنا،
        # أي استثناء كهذا كان سيُسقط run() بأكملها بلا أي نتيجة مفهومة
        # (بدل HOLD موثّق) - يُبطل تماماً فلسفة "لا فشل صامت أو مفاجئ"
        # المتبعة بكل مكان آخر بهذا الملف. عند استثناء غير متوقع هنا: لا
        # نُخرج final_result الخام غير المُتحقَّق منه (قد يكون فاسداً
        # بنفس المشاكل التي هذه الدالة مصمَّمة لصدّها) - نتحوّل HOLD
        # صراحة مع توثيق كامل للاستثناء نفسه، بنفس أسلوب أي HOLD إجباري
        # آخر بهذا الملف.
        try:
            final_result = self._verify_and_finalize_trade_plan(
                final_result, symbol, timeframe, entry_data, entry_ind,
                entry_candles_text, entry_indicators_text,
                weekly_result, daily_result, h4_result, h15_result, is_backtest,
                entry_authenticity_text, min_sl_hint=min_sl_hint, session_text=session_text,
            )
        except Exception as e:
            self.logger.error(
                f"❌ [Trade Plan Validation] استثناء غير متوقع أثناء التحقق النهائي: "
                f"{e} - تحويل النتيجة لـHOLD إجبارياً (لا نُخرج نتيجة غير مُتحقَّق منها)."
            )
            final_result["signal"] = "HOLD"
            final_result["_trade_plan_forced_hold"] = True
            final_result["_trade_plan_unresolved_issues"] = [f"EXCEPTION_DURING_VALIDATION: {e}"]

        # Pending model conditions are informative watch-list data, not a
        # licence to pre-position.  Preserve the scenario for the UI, but do
        # not expose it as BUY_LIMIT/SELL_LIMIT until the checklist is READY.
        if (checklist_result
                and checklist_result.get("final_status") == "PENDING_SETUP"
                and final_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT")):
            _pending_model = checklist_result.get("chosen_model") or {}
            final_result["candidate_plan"] = _pending_model.get("plan")
            final_result["setup_status"] = "WAIT_CONFIRMATION"
            final_result["signal"] = "HOLD"
            final_result["reason"] = (
                "النموذج ما زال PENDING: لا أمر دخول قبل اكتمال displacement/FVG/"
                "تأكيد فريم التنفيذ والتوقيت. الخطة المعروضة سيناريو مراقبة فقط."
            )

        # ⚠️ حل جذري (يوليو 2026، طلب صريح من المستخدم بعد ملاحظة دقيقة:
        # "اختبرناها وحط تارغتين ولكن جابت تارغت واحد [ضعيف]"): اكتُشف
        # باگ حقيقي بفحص مباشر - صفقة #8 حسبت TP1/TP2 رياضياً صح
        # (find_tp_targets: TP1=2326.03 R:R=3.81, TP2=2423.89 من Daily)
        # لكن القرار "الرسمي" النهائي (final_result["tp"]) كان 2284.92
        # (R:R=0.64 فقط!) - رقم اخترعه الموديل بنفسه بمسار لم يمرّ عبر
        # Deterministic-First (مثلاً لما checklist_result="NO_MODEL_
        # QUALIFIES" فيسقط الشرط، لكن الموديل ما زال يخرج BUY_LIMIT
        # بمساره الحر). المشكلة الجذرية: TP1/TP2 كانا يُحسبان فقط
        # *داخل* checklist الميكانيكي (ict_entry_checklist_engine.py)
        # أو *بعد* انتهاء التحليل (لغرض المقارنة بـhuman_trades_
        # backtest.py فقط) - لا شيء كان يفرضهما على القرار النهائي نفسه
        # بغض النظر عن أي مسار وصل إليه (حتمي أو حر).
        #
        # الحل: بعد اكتمال كل التحقق الهيكلي (entry/stop_loss النهائيان
        # مستقران وصحيحان هيكلياً - _verify_and_finalize_trade_plan
        # انتهت)، نعيد حساب TP1/TP2 **من نفس entry/stop_loss النهائيين
        # فعلياً** (بغض النظر عن مصدرهما) عبر find_tp_targets نفسها،
        # ونستبدل بهما "tp" الحالي **دائماً** - لا نترك أي مجال لرقم
        # هدف مُخترَع من الموديل يتسرب للقرار النهائي.
        if final_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
            try:
                fr_entry = final_result.get("entry")
                fr_sl = final_result.get("stop_loss")
                if isinstance(fr_entry, (int, float)) and isinstance(fr_sl, (int, float)) and fr_entry != fr_sl:
                    from ict_math_engine import find_tp_targets
                    is_long_final = final_result["signal"] in ("BUY", "BUY_LIMIT")
                    enforced_targets = find_tp_targets(
                        entry_data, float(fr_entry), float(fr_sl), is_long=is_long_final,
                        htf_data_sources=htf_data_sources_for_tp2,
                    )
                    if enforced_targets.get("tp1"):
                        final_result["tp"] = enforced_targets["tp1"]["price"]
                        final_result["tp1"] = enforced_targets["tp1"]
                        final_result["tp2"] = enforced_targets["tp2"]
                        final_result["_tp_enforced_from_mechanical_calculation"] = True
                    else:
                        # لا يوجد مستوى حقيقي صالح باتجاه الصفقة. لا نبقي
                        # هدفاً اخترعه الموديل ولا نصنع هدفاً من مضاعف SL.
                        final_result["signal"] = "HOLD"
                        final_result["_trade_plan_forced_hold"] = True
                        final_result["_trade_plan_unresolved_issues"] = [
                            "NO_VALID_STRUCTURAL_TP1: after all structural corrections, "
                            "no genuine unswept target exists ahead of the final entry."
                        ]
            except Exception as e:
                self.logger.warning(f"⚠️ فرض TP1/TP2 المحسوبة رياضياً على القرار النهائي فشل (non-fatal): {e}")

        # ⚠️ حل جذري معماري (يوليو 2026، طلب صريح من المستخدم - راجع
        # docstring _compute_risk_management_report للسياق الكامل):
        # هذا يُحسب هنا **بعد** اكتمال كل التحليل الهيكلي بالكامل
        # (بما فيها كل محاولات التصحيح أعلاه) - تقرير معلوماتي بحت لا
        # يُغيّر final_result["signal"]/["entry"]/["stop_loss"]/["tp"]
        # إطلاقاً، فقط يُرفَق كحقل إضافي "_risk_management_report".
        try:
            risk_report = self._compute_risk_management_report(
                final_result, symbol, timeframe, entry_ind
            )
            if risk_report:
                final_result["_risk_management_report"] = risk_report
        except Exception as e:
            self.logger.warning(f"⚠️ _compute_risk_management_report failed (non-fatal): {e}")

        final_result["multi_pass_stage_log"] = stage_log
        final_result["analysis_method"] = "multi_pass_topdown_ict"
        final_result["stages_completed"] = 5
        # ⚠️ نُرفِق بصمة النمط (لو حُسبت أعلاه) بالنتيجة النهائية - تُستخدَم
        # لاحقاً بـhuman_trades_backtest.py::classify_loss_cause/run_human_
        # trades_backtest لتسجيل النتيجة الفعلية (WIN/LOSS) لهذا النمط
        # بالضبط بعد معرفتها (راجع pattern_confidence_engine.py).
        if pattern_signature:
            final_result["_pattern_signature"] = pattern_signature
        # ⚠️ إصلاح خطأ حقيقي مُكتشف بالاختبار الفعلي: كانت النسخة
        # السابقة تنقل last_candle_report من مرحلة الـ1H (فريم مختلف
        # تماماً - مثلاً 1H بينما الـEntry TF كان 4H) للنتيجة النهائية
        # مباشرة، فيظهر "تناقض" زائف عند مقارنته بشمعة الـEntry TF
        # الفعلية (audit_last_candle_report). الحل: الآن last_candle_report
        # يُطلب مباشرة من مرحلة التنفيذ (Stage 5) نفسها، على فريم
        # الـEntry TF الصحيح - لا حاجة لنقله من مرحلة أخرى بعد الآن.

        return final_result

    # ══════════════════════════════════════════════════════════
    #  جلب بيانات فريمات الـHTF
    # ══════════════════════════════════════════════════════════

    # ⚠️ خريطة الأزواج المدعومة لـSMT Divergence (الزوج الوحيد الآخر بمشروعنا
    # حالياً) - أُضيف بطلب المستخدم بعد مراجعة كتب ICT الرسمية (راجع
    # ict_source_material/ICT_BOOKS_EXTRACTION_SUMMARY.md). ثابت بسيط (لا تخمين مستقبلي
    # لأزواج إضافية - المشروع حالياً يدعم فقط BTC/USDT وETH/USDT).
    _SMT_COUNTERPART = {"BTC/USDT": "ETH/USDT", "ETH/USDT": "BTC/USDT"}

    def _fetch_htf_chain(self, symbol, end_ts, is_backtest, exchange=None):
        """
        يجلب Weekly/Daily/4H/1H - منتهية عند end_ts بوضع الباك تيست.
        بالإضافة لبيانات Daily للأصل المقارن (SMT counterpart) إن وُجد.

        ⚠️ تحسين سرعة آمن 100% (يوليو 2026، طلب المستخدم تسريع التحليل
        بلا أي تنازل عن الدقة): جلب البيانات الأربعة يصير بالتوازي
        (ThreadPoolExecutor) بدل التتابع - هذا **لا علاقة له بالذكاء
        الاصطناعي أو الدقة إطلاقاً**، فقط 4 طلبات شبكة مستقلة تماماً
        (كل فريم زمني بيانات منفصلة عن الآخر) كانت تُجلَب بالتتابع بلا
        داعٍ. لا مخاطرة على الدقة لأن كل طلب يرجع نفس البيانات بالضبط
        سواء بالتوازي أو بالتتابع - فقط أسرع.

        ⚠️ إضافة SMT counterpart (يوليو 2026): طلب شبكة خامس مستقل تماماً
        (بيانات Daily لزوج آخر - مثلاً ETH إذا كان التحليل على BTC) يُضاف
        لنفس مجموعة الطلبات المتوازية - لا كلفة زمنية إضافية عملياً (يشارك
        نفس دفعة الـThreadPoolExecutor). فشل هذا الطلب تحديداً **لا يوقف
        أو يُضعف التحليل الأساسي بأي شكل** - هو دليل إضافي اختياري بحت
        (فحص _fetch_one يرجع None بهدوء لو فشل، ونفس معالجة الفشل الموجودة
        أصلاً لبقية الفريمات تُطبَّق هنا حرفياً - لا منطق جديد يُخترع).
        """
        import concurrent.futures
        result = {}
        # ⚠️ تحديث (يوليو 2026): "1h" -> "15m" (راجع تعليق
        # HTF_CHAIN أعلاه للسبب الكامل). 200 شمعة بفريم 15 دقيقة
        # تغطي ما يقارب 50 ساعة (يومين تقريباً) - كافٍ لرؤية النطاق
        # الليلي (Overnight Range) لعدة أيام متتالية + السيولة/FVGs الحديثة.
        counts = {"1w": 104, "1d": 90, "4h": 120, "15m": 200}

        counterpart_symbol = self._SMT_COUNTERPART.get(symbol)
        fetch_jobs = list(HTF_CHAIN)
        if counterpart_symbol:
            fetch_jobs.append("smt_counterpart_1d")

        def _fetch_one(job):
            try:
                if job == "smt_counterpart_1d":
                    if is_backtest and end_ts:
                        return job, self.dm.fetch_ohlcv_up_to(
                            counterpart_symbol, "1d", end_ts, limit=counts["1d"], exchange=exchange
                        )
                    return job, self.dm.get_ohlcv(
                        counterpart_symbol, "1d", counts["1d"], output_format="dict",
                        exchange=exchange, closed_only=True, allow_fallback=False,
                    )
                tf = job
                if is_backtest and end_ts:
                    return tf, self.dm.fetch_ohlcv_up_to(
                        symbol, tf, end_ts, limit=counts[tf], exchange=exchange
                    )
                return tf, self.dm.get_ohlcv(
                    symbol, tf, counts[tf], output_format="dict",
                    exchange=exchange, closed_only=True, allow_fallback=False,
                )
            except Exception as e:
                self.logger.warning(f"⚠️ خطأ جلب بيانات {job}: {e}")
                return job, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(fetch_jobs)) as executor:
            futures = [executor.submit(_fetch_one, job) for job in fetch_jobs]
            for future in concurrent.futures.as_completed(futures):
                job, data = future.result()
                if data:
                    result[job] = data
                elif job == "smt_counterpart_1d":
                    self.logger.warning(
                        "⚠️ فشل جلب بيانات SMT counterpart - سيُتجاهل فحص "
                        "SMT Divergence لهذا التحليل (لا يؤثر على المراحل الأساسية)"
                    )
                else:
                    self.logger.warning(f"⚠️ فشل جلب بيانات {job} - المرحلة المرتبطة ستعمل بدونها")
        return result

    # ══════════════════════════════════════════════════════════
    #  تنفيذ مرحلة واحدة
    # ══════════════════════════════════════════════════════════

    # ⚠️ طلب المستخدم صراحة (يوليو 2026) بعد اكتشاف تناقض داخلي حقيقي
    # مع gpt-oss-120b (confidence=85% + direction="UNCLEAR" بنفس الرد):
    # فصل "التفكير الحر" عن "الاستخراج المُهيكَل" بنداءين منفصلين بدل
    # نداء واحد يطلب الاثنين معاً. يُفعَّل فقط لموديلات معينة أثبتت
    # الحاجة له فعلياً (لا يُطبَّق افتراضياً على كل الموديلات - Gemini
    # مثلاً لم يُظهر هذا التناقض بأي اختبار، فلا داعٍ لمضاعفة نداءاته).
    _TWO_STEP_MODELS = ("gpt-oss",)

    def _should_use_two_step(self):
        provider = self.ai.providers.get("cloudflare")
        if not provider:
            return False
        return any(tag in provider.model for tag in self._TWO_STEP_MODELS)

    @staticmethod
    def _validate_required_fields(result, schema):
        """
        \u26a0\ufe0f \u062d\u0644 \u062c\u0630\u0631\u064a (\u064a\u0648\u0644\u064a\u0648 2026\u060c \u0628\u0639\u062f \u0641\u0634\u0644 \u062d\u0642\u064a\u0642\u064a \u0643\u0627\u0645\u0644 \u0628\u0645\u0631\u062d\u0644\u0629
        Weekly \u0623\u062b\u0646\u0627\u0621 \u0627\u062e\u062a\u0628\u0627\u0631 \u062d\u064a): \u0627\u0644\u0641\u062d\u0635 \u0627\u0644\u0642\u062f\u064a\u0645 (\u0642\u0628\u0644 \u0647\u0630\u0627 \u0627\u0644\u0625\u0635\u0644\u0627\u062d) \u0643\u0627\u0646
        "isinstance(result, dict) and \"error\" not in result" - \u0647\u0630\u0627 \u064a\u0642\u0628\u0644
        \u0628\u0635\u0645\u062a \u0623\u064a dict \u0644\u0627 \u064a\u062d\u0648\u064a \u0645\u0641\u062a\u0627\u062d "error" \u0635\u0631\u064a\u062d\u0627\u064b -
        \u0628\u0645\u0627 \u0641\u064a\u0647 \u0627\u0644\u0634\u0643\u0644 \u0627\u0644\u0623\u062e\u0637\u0631: {"raw_response": "..."}
        (\u0646\u0627\u062a\u062c \u0641\u0634\u0644 \u0627\u0644\u0640JSON parsing \u0628\u0640_parse_json_text) - \u0644\u0627 \u064a\u062d\u0648\u064a "error"
        \u062d\u0631\u0641\u064a\u0627\u064b\u060c \u0641\u0643\u0627\u0646 \u064a\u0645\u0631 \u0645\u0646 \u0627\u0644\u0641\u062d\u0635 \u0648\u0643\u0623\u0646\u0647 \u0646\u062a\u064a\u062c\u0629 \u0635\u0627\u0644\u062d\u0629\u060c \u0644\u064a\u064f\u062d\u0642\u064e\u0646
        \u0644\u0627\u062d\u0642\u0627\u064b \u0628\u0627\u0644\u0645\u0631\u062d\u0644\u0629 \u0627\u0644\u062a\u0627\u0644\u064a\u0629 \u0648\u0643\u0623\u0646\u0647 \u062a\u062d\u0644\u064a\u0644 \u062d\u0642\u064a\u0642\u064a - \u062a\u062d\u0642\u0642 \u0641\u0639\u0644\u064a \u0645\u0648\u062b\u0651\u0642
        (\u0627\u062e\u062a\u0628\u0627\u0631 \u062d\u064a): \u0641\u0634\u0644 \u0628\u0645\u0631\u062d\u0644\u0629 Weekly (\u0644\u0627 Gate \u064a\u0648\u0642\u0641\u0647\u0627) \u0623\u062f\u0649 \u0644\u062a\u0644\u0648\u064a\u062b
        \u0628\u0631\u0648\u0645\u0628\u062a\u0627\u062a \u0627\u0644\u0645\u0631\u0627\u062d\u0644 \u0627\u0644\u0623\u0631\u0628\u0639 \u0627\u0644\u062a\u0627\u0644\u064a\u0629 \u0628\u0623\u0643\u0645\u0644\u0647\u0627 (\u062a\u064f\u062d\u0642\u064e\u0646 \u0643\u0640\"STEP 1 - Weekly
        Narrative\" \u0628\u0645\u0631\u062d\u0644\u0629 entry \u0627\u0644\u0646\u0647\u0627\u0626\u064a\u0629).

        \u0627\u0644\u062d\u0644 \u0627\u0644\u062c\u0630\u0631\u064a: \u0627\u0644\u062a\u062d\u0642\u0642 \u0635\u0631\u0627\u062d\u0629\u064b \u0623\u0646 \u0643\u0644 \u062d\u0642\u0644 \u0645\u0630\u0643\u0648\u0631 \u0628\u0640"required" \u0628\u0627\u0644\u0640schema
        \u0645\u0648\u062c\u0648\u062f \u0641\u0639\u0644\u064a\u0627\u064b \u0628\u0627\u0644\u0646\u062a\u064a\u062c\u0629 - \u0644\u0627 \u0627\u0644\u0627\u0643\u062a\u0641\u0627\u0621 \u0628\u0641\u062d\u0635 \u0633\u0637\u062d\u064a
        ("error" \u0645\u0648\u062c\u0648\u062f \u0623\u0645 \u0644\u0627) \u0628\u0644 \u0641\u062d\u0635 \u0645\u0637\u0627\u0628\u0642\u0629 \u0641\u0639\u0644\u064a\u0629 \u0644\u0644\u0628\u0646\u064a\u0629 \u0627\u0644\u0645\u0637\u0644\u0648\u0628\u0629.
        \u0647\u0630\u0627 \u064a\u0645\u0633\u0643 **\u0623\u064a** \u0634\u0643\u0644 \u0641\u0634\u0644 \u0645\u0645\u0627\u062b\u0644 (raw_response\u060c \u0623\u0648
        \u0623\u064a dict \u0646\u0627\u0642\u0635 \u062d\u0642\u0648\u0644\u0627\u064b \u0644\u0623\u064a \u0633\u0628\u0628 \u0622\u062e\u0631)\u060c \u0644\u0627 \u0641\u0642\u0637 \u0627\u0644\u062d\u0627\u0644\u0629
        \u0627\u0644\u0648\u0627\u062d\u062f\u0629 \u0627\u0644\u0645\u0643\u062a\u0634\u0641\u0629 \u0641\u0639\u0644\u064a\u0627\u064b \u062d\u062a\u0649 \u0627\u0644\u0622\u0646.

        Returns: (is_valid: bool, missing_fields: list[str])
        """
        if not isinstance(result, dict):
            return False, ["RESULT_NOT_A_DICT"]
        if "error" in result:
            return False, [f"EXPLICIT_ERROR: {result.get('error')}"]
        if "raw_response" in result:
            return False, ["JSON_PARSE_FAILED_RAW_RESPONSE_ONLY"]
        required = schema.get("required", [])
        missing = [f for f in required if f not in result or result.get(f) is None]
        return (len(missing) == 0), missing

    def _run_stage(self, stage_name, prompt, schema, max_retries=2):
        """
        \u0645\u0644\u0627\u062d\u0638\u0629: max_retries \u0647\u0646\u0627 \u0645\u0646\u0641\u0635\u0644\u0629 \u062a\u0645\u0627\u0645\u0627\u064b \u0639\u0646 retries
        \u0627\u0644\u0645\u0641\u0627\u062a\u064a\u062d \u0628\u062f\u0627\u062e\u0644 query_json_race/query - \u0647\u0630\u0647 \u0625\u0639\u0627\u062f\u0629 \u0645\u062d\u0627\u0648\u0644\u0629 \u0639\u0644\u0649
        \u0645\u0633\u062a\u0648\u0649 **\u0627\u0644\u0645\u0631\u062d\u0644\u0629 \u0628\u0623\u0643\u0645\u0644\u0647\u0627** \u0639\u0646\u062f\u0627\u0643\u062a\u0634\u0627\u0641 \u0623\u0646 \u0627\u0644\u0646\u062a\u064a\u062c\u0629
        \u0627\u0644\u0646\u0647\u0627\u0626\u064a\u0629 (\u0628\u0639\u062f \u0643\u0644 \u0645\u062d\u0627\u0648\u0644\u0627\u062a query_json_race \u0627\u0644\u062f\u0627\u062e\u0644\u064a\u0629) \u0644\u0627 \u062a\u0632\u0627\u0644
        \u0646\u0627\u0642\u0635\u0629 \u062d\u0642\u0648\u0644\u0627\u064b \u0645\u0637\u0644\u0648\u0628\u0629 - \u0646\u0637\u0644\u0628 \u0645\u0646 \u0627\u0644\u0645\u0648\u062f\u064a\u0644 \u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629 \u0628\u0627\u0644\u0643\u0627\u0645\u0644 \u0645\u0639
        \u0631\u0633\u0627\u0644\u0629 \u062a\u0635\u062d\u064a\u062d \u0635\u0631\u064a\u062d\u0629 \u062a\u0630\u0643\u0631 \u0627\u0644\u062d\u0642\u0648\u0644 \u0627\u0644\u0646\u0627\u0642\u0635\u0629 \u0628\u0627\u0644\u062a\u062d\u062f\u064a\u062f.
        """
        # كل خطوة top-down تستخدم دستوراً مخصصاً لمهمتها (نفس مبدأ v1
        # لمعالجة "Lost in the Middle"، لكن الآن مربوط بفريم حقيقي مختلف)
        stage_knowledge_map = {
            "weekly": 1, "daily": 2, "h4": 3, "h15": 4, "entry": 5,
        }
        knowledge = get_stage_knowledge(stage_knowledge_map.get(stage_name, 1))
        base_prompt = f"{knowledge}\n\n{prompt}" if knowledge else prompt

        current_prompt = base_prompt
        last_missing = []
        for attempt in range(max_retries + 1):
            try:
                if self._should_use_two_step():
                    result = self.ai.query_json_two_step(current_prompt, response_schema=schema)
                else:
                    # ⚠️ طلب المستخدم الدقيق (يوليو 2026): تسريع gemma-4-26b
                    # (تذبذب زمني موثّق فعلياً 32.8s-652s على نفس نوع الطلب)
                    # بلا أي فقدان دقة - "السباق" يطلق نفس السؤال بالضبط على
                    # مفتاحين بنفس اللحظة، ويأخذ أول جواب ناجح فقط (لا دمج
                    # ولا تصويت، الجواب الثاني يُهمَل بالكامل).
                    result = self.ai.query_json_race(current_prompt, response_schema=schema, race_count=2)
            except Exception as e:
                self.logger.warning(f"⚠️ مرحلة {stage_name} استثناء بمحاولة {attempt + 1}: {e}")
                result = None
                last_missing = [f"EXCEPTION: {e}"]
                current_prompt = base_prompt + (
                    f"\n\n⚠️ PREVIOUS ATTEMPT FAILED WITH AN EXCEPTION ({e}). "
                    "Try again, ensuring your reply is ONLY a single valid JSON object."
                )
                continue

            is_valid, missing = self._validate_required_fields(result, schema)
            if is_valid:
                return result

            last_missing = missing
            self.logger.warning(
                f"⚠️ مرحلة {stage_name} فشلت بمحاولة {attempt + 1}/{max_retries + 1} "
                f"(حقول ناقصة/غير صالحة: {missing}) - "
                f"{'إعادة محاولة...' if attempt < max_retries else 'استُنفدت المحاولات.'}"
            )
            if attempt < max_retries:
                current_prompt = base_prompt + (
                    "\n\n⚠️ CRITICAL: Your previous reply was NOT valid JSON matching the "
                    f"required schema (missing or invalid fields: {missing}). This is a common "
                    "failure mode where a model accidentally mixes up reference example data "
                    "shown earlier in the prompt with the actual required output structure. "
                    "IGNORE any bracket/dict-like text shown as reference evidence above - your "
                    "output must contain ONLY the exact fields listed in the OUTPUT FORMAT "
                    "section, as one single valid JSON object, with correctly double-quoted "
                    "keys and no missing commas or colons. Try again now."
                )

        # ⚠️ فشلت كل المحاولات - نرجع {} صراحة (لا القيمة الفاسدة الخام)
        # حتى تُعامَل بشكل صحيح ومتّسق من أي Gate يتحقق منها لاحقاً (كل
        # الـGates تفحص "if not result:" و{} فارغ = falsy، بعكس
        # {"raw_response": "..."} الذي كان يمر بصمت كأنه نتيجة صالحة).
        self.logger.error(
            f"❌ مرحلة {stage_name}: فشلت كل محاولات الحصول على JSON صالح "
            f"({max_retries + 1} محاولة) - آخر مشكلة: {last_missing}"
        )
        return {}

    # ══════════════════════════════════════════════════════════
    #  تقسيم عمل حقيقي داخل المرحلة الواحدة (طلب صريح من المستخدم)
    # ══════════════════════════════════════════════════════════
    # "نفس المرحلة (Weekly مثلاً) عم تدور ع أكتر من شغلة سوا بنفس
    # الفريم - فينا نخلي كل مفتاح يشتغل شغلة وبالآخر يتقاطعوا، مو
    # أسرع؟" - كل حقول الـschema لمرحلة واحدة تُقسَّم لمجموعتين فرعيتين
    # حقيقيتين (لا نفس الأسئلة مكررة)، تُطلقان بالتوازي بنفس اللحظة على
    # مفتاحين مختلفين، على **نفس البيانات الخام الكاملة** - لا فقدان
    # معلومة (كل حقل له مصدر واحد مسؤول عنه)، ولا تصويت (كل استدعاء
    # جاب جزءه المختلف تماماً)، فقط أسرع لأن كل سؤال فرعي أضيق.

    # ⚠️ خريطة تقسيم الحقول لكل مرحلة - مبنية بحيث كل مجموعة متماسكة
    # منطقياً (حقول مرتبطة ببعضها تبقى سوا بنفس الاستدعاء، لا تُفصل
    # حقول تعتمد على بعضها البعض لتفسير واحد متماسك)
    _STAGE_FIELD_SPLITS = {
        "weekly": [
            (["trend", "strength", "at_weekly_poi"],
             "Focus on: overall trend direction, its strength, and whether price is at a major weekly point of interest right now."),
            (["macro_narrative", "macro_dol"],
             "Focus on: the big-picture narrative story (in plain language) and where the macro Draw on Liquidity target is."),
        ],
        "daily": [
            (["direction", "confidence", "weekly_alignment"],
             "Focus on: the Daily bias direction, your confidence in it, and whether it aligns with the Weekly context given."),
            (["last_event", "dol_description", "daily_bias_summary"],
             "Focus on: the most recent Daily structural event (BOS/CHoCH), the Daily liquidity target, and a short bias summary."),
        ],
        "h4": [
            (["daily_alignment", "mmm_phase", "price_at_zone"],
             "Focus on: alignment with Daily bias, which Market Maker Model phase (1-5) price is in, and whether price is at a refined zone now."),
            (["refined_zones_summary", "h4_context_summary"],
             "Focus on: describing the specific refined 4H OB/FVG zones, and a short context summary."),
        ],
        # ⚠️ إصلاح جذري (يوليو 2026): المجموعة الفرعية الثانية هنا كانت
        # مخصَّصة حصراً لحقل `last_candle_report` - بعد حذف هذا الحقل
        # بالكامل من الـschema (يُحسب الآن رياضياً بحتاً عبر
        # `_compute_last_candle_fact` بدل أن "يقرأه" الموديل - راجع
        # docstring تلك الدالة)، لم يعد هناك حاجة لهذا الاستدعاء الفرعي
        # المنفصل إطلاقاً - مرحلة h15 الآن تُجاب بنداء واحد فقط (لا
        # حاجة لتقسيمها لمجموعتين، الحقل المتبقي الوحيد الذي كان يبرر
        # الفصل حُذف بالكامل).
        "h15": [
            (["entry_ready", "structural_shift_direction", "tactical_summary"],
             "Focus on: whether a structural shift (MSS/CHoCH) is forming right now at the HTF zone, its direction, and a tactical summary."),
        ],
    }

    @staticmethod
    def _build_sub_schema(full_schema, field_names):
        """يبني schema فرعي يحوي فقط الحقول المطلوبة من الـschema الكلي"""
        props = full_schema.get("properties", {})
        sub_props = {f: props[f] for f in field_names if f in props}
        return {
            "type": "OBJECT",
            "properties": sub_props,
            "required": [f for f in field_names if f in sub_props],
        }

    def _run_stage_split(self, stage_name, prompt, schema):
        """
        ينفّذ مرحلة واحدة عبر تقسيم حقولها لمجموعتين فرعيتين حقيقيتين
        تُطلَقان بالتوازي على مفتاحين مختلفين - بدل استدعاء واحد يجاوب
        على كل الحقول. يدمج النتيجتين (لا تصويت، كل حقل من مصدره).
        إذا لم توجد خريطة تقسيم لهذه المرحلة (مثل "entry")، يرجع
        لـ_run_stage العادي (استدعاء واحد كامل) تلقائياً.
        """
        splits = self._STAGE_FIELD_SPLITS.get(stage_name)
        if not splits:
            return self._run_stage(stage_name, prompt, schema)

        stage_knowledge_map = {"weekly": 1, "daily": 2, "h4": 3, "h15": 4, "entry": 5}
        knowledge = get_stage_knowledge(stage_knowledge_map.get(stage_name, 1))
        full_prompt = f"{knowledge}\n\n{prompt}" if knowledge else prompt

        field_groups = [
            {"schema": self._build_sub_schema(schema, fields), "focus_note": note}
            for fields, note in splits
        ]

        try:
            merged, meta = self.ai.query_json_split_parallel(full_prompt, field_groups)
        except Exception as e:
            self.logger.warning(f"⚠️ مرحلة {stage_name} (split) استثناء: {e} - رجوع لاستدعاء عادي")
            return self._run_stage(stage_name, prompt, schema)

        required = schema.get("required", [])
        missing = [f for f in required if f not in merged]
        if missing:
            self.logger.warning(
                f"⚠️ مرحلة {stage_name} (split): حقول ناقصة {missing} بعد الدمج - "
                f"تفاصيل الاستدعاءات الفرعية: {meta}"
            )
        return merged

    # ══════════════════════════════════════════════════════════
    #  GATES (منطق مطابق حرفياً لقسم [TOP_DOWN_WORKFLOW] بالدستور)
    # ══════════════════════════════════════════════════════════

    def _verify_and_retry_structure_math(self, stage_name, stage_result, text_field,
                                          data_for_audit, rebuild_prompt_fn, schema,
                                          max_retries=2, direction_field=None,
                                          direction_map=None):
        """
        ⚠️ إصلاح خطأ حقيقي مُكتشف بالباك تيست الفعلي (يوليو 2026، Nemotron
        3 Ultra، صفقة BTC/USDT 4h موثّقة): النموذج ذكر أرقاماً صحيحة فعلاً
        بحقل نصي (daily_bias_summary أو tactical_summary) لكن قارنها بشكل
        معكوس رياضياً ("HH at idx -1 (95000) > HH at idx -7 (95191)" بينما
        95000 < 95191 فعلياً) - خطأ حسابي بحت بمقارنة رقمين، لا علاقة له
        بنقص معرفة أو Recency Bias (كلاهما تم التحقق منه وإصلاحه بمكان
        آخر). هذا النوع من الأخطاء لا يُحل بتحسين البرومبت - الحل الوحيد
        الموثوق هو تحقق برمجي مستقل (AuthenticityEngine.audit_numeric_
        comparison_claims) يعيد نفس المقارنة الحسابية البسيطة رياضياً بلا
        اعتماد على "فهم" النموذج للعلاقة بين الأرقام، ثم يطلب إعادة
        المحاولة عند اكتشاف تناقض - نفس فلسفة
        _check_reasoning_content_consistency الموجودة أصلاً بـai_client.py
        لموديل آخر (gemma-4).

        ⚠️ إضافة ثانية (بعد باك تيست 19 صفقة بشرية حقيقية، يوليو 2026):
        اكتُشف نوع تناقض مختلف تماماً - ليس مقارنة رقمية صريحة (>/<)
        بل **تصنيف هيكلي خاطئ** (النموذج يكتب "LH formation at idx -2
        high 2200" بينما 2200 كانت فعلياً أعلى من القمة السابقة idx -3
        (2157.23) - أي Higher High حقيقي، لا Lower High كما زُعم).
        هذا أثّر فعلياً على 4 من 10 صفقات بالباك تيست (رقم 1، 8، 9، 15)
        - راجع audit_structure_labels() للتفاصيل الكاملة.

        ⚠️ إضافة ثالثة (يوليو 2026، بطلب المستخدم صراحة بعد اختبار حي
        كشف نفس نمط الخطأ بمرحلة h1/CHoCH تحديداً - صفقة #6 ETH): هذه
        الدالة كانت مقصورة على مرحلة Daily فقط رغم أن مرحلة h1 (STEP
        4/5) هي بالضبط المكان الذي تُتخذ فيه أخطر مقارنة من هذا النوع -
        "هل تشكّل MSS/CHoCH الآن؟" يتطلب حرفياً مقارنة آخر قمة/قاع
        بالمرجع الصحيح، نفس العملية بالضبط. تعميم الدالة (بدل نسخة
        مكررة لكل مرحلة) يضمن نفس مستوى الصرامة في كل مرحلة تحتاجها،
        بلا ازدواجية كود.

        ⚠️ إضافة رابعة (يوليو 2026، حل جذري لتذبذب اتجاه القرار بين
        نداءات مستقلة على نفس البيانات بالضبط - راجع ict_math_engine.
        compute_mechanical_bias_anchor وauthenticity_engine.audit_bias_
        anchor_consistency للتوثيق الكامل): معامل `direction_field`
        الجديد (اختياري) - لو مُمرَّر (مثلاً "direction" لمرحلة daily،
        "structural_shift_direction" لمرحلة h15)، يُضاف فحص إضافي:
        هل القيمة المُخرَجة بهذا الحقل تخالف مرساة انحياز ميكانيكية
        "STRONG" (كسر هيكلي حقيقي + تسلسل قمم/قيعان متفقان) بلا استشهاد
        بحدث انعكاس أحدث زمنياً؟ لو خالف بلا استشهاد كافٍ، يُعامَل بنفس
        آلية التصحيح وإعادة المحاولة الموجودة أصلاً هنا.
        """
        if not stage_result or not isinstance(stage_result, dict):
            return stage_result

        try:
            from ict_math_engine import compute_mechanical_bias_anchor
            bias_anchor = compute_mechanical_bias_anchor(data_for_audit)
        except Exception as e:
            self.logger.warning(f"⚠️ Bias anchor computation failed (non-fatal): {e}")
            bias_anchor = None

        def _run_audits(text, direction_claimed=None):
            math_audit = self.authenticity.audit_numeric_comparison_claims(text)
            struct_audit = self.authenticity.audit_structure_labels(text, data_for_audit)
            combined_contradictions = (
                [{"kind": "math", **c} for c in math_audit.get("contradictions", [])]
                + [{"kind": "structure", **c} for c in struct_audit.get("contradictions", [])]
            )
            checked_count = math_audit.get("checked_count", 0) + struct_audit.get("checked_count", 0)
            if direction_field and bias_anchor:
                try:
                    anchor_check = self.authenticity.audit_bias_anchor_consistency(
                        direction_claimed, text, bias_anchor, data_for_audit
                    )
                    checked_count += 1
                    if anchor_check.get("flagged"):
                        combined_contradictions.append({
                            "kind": "bias_anchor",
                            "detail": anchor_check.get("reason", ""),
                        })
                except Exception as e:
                    self.logger.warning(f"⚠️ Bias anchor audit failed (non-fatal): {e}")
            return {
                "checked_count": checked_count,
                "contradictions": combined_contradictions,
                "has_contradiction": len(combined_contradictions) > 0,
            }

        def _resolve_direction(res):
            if not direction_field:
                return None
            raw = res.get(direction_field)
            if direction_map:
                return direction_map.get(raw, raw)
            return raw

        summary_text = stage_result.get(text_field, "")
        direction_claimed = _resolve_direction(stage_result)
        audit = _run_audits(summary_text, direction_claimed)

        attempt = 0
        while audit.get("has_contradiction") and attempt < max_retries:
            attempt += 1
            contradictions = audit["contradictions"]
            self.logger.warning(
                f"⚠️ [{stage_name} Math/Structure Check] تناقض مكتشف بمحاولة {attempt}: "
                f"{contradictions} - إعادة المحاولة..."
            )
            correction_lines = []
            for c in contradictions:
                if c["kind"] == "math":
                    correction_lines.append(
                        f'  - You wrote "{c["claim"]}" but {c["num1"]} {c["operator"]} '
                        f'{c["num2"]} is actually FALSE (check the arithmetic again, '
                        f"digit by digit, before restating your conclusion)."
                    )
                else:
                    correction_lines.append(f"  - {c['detail']}")
            correction_note = (
                "\n\n⚠️ CRITICAL SELF-CORRECTION REQUIRED: Your previous attempt "
                "contained mathematical/structural labeling errors. Specifically:\n"
                + "\n".join(correction_lines)
                + "\nRe-derive this analysis from scratch with correct arithmetic and "
                "correct HH/HL/LH/LL labeling (compare each swing DIRECTLY against the "
                "immediately preceding CONFIRMED swing of the same type - name that "
                "reference swing's index and price explicitly before stating any label, "
                "per section 4.1B of the constitution). If your direction contradicted "
                "the MECHANICAL BIAS ANCHOR above, either align with it, or explicitly "
                "name a specific CHoCH/MSS/BOS reversal candle (with its index) that is "
                "genuinely MORE RECENT than the anchor's break point. Do not repeat the "
                "same error."
            )
            retry_prompt = rebuild_prompt_fn() + correction_note
            stage_result = self._run_stage(stage_name, retry_prompt, schema)
            if not stage_result:
                break
            summary_text = stage_result.get(text_field, "")
            direction_claimed = _resolve_direction(stage_result)
            audit = _run_audits(summary_text, direction_claimed)

        if isinstance(stage_result, dict):
            stage_result[f"_{stage_name}_math_audit"] = {
                "checked_count": audit.get("checked_count", 0),
                "had_contradiction_initially": attempt > 0,
                "resolved": not audit.get("has_contradiction", False),
                "retries_used": attempt,
            }
        return stage_result

    # ⚠️ الحد الأدنى الرسمي لمسافة SL حسب [RISK_ENGINE] بالدستور (قسم
    # 15.2 "MINIMUM SL DISTANCE BY ASSET AND TIMEFRAME") - نفس الأرقام
    # الحرفية المذكورة بالنص، منسوخة هنا فقط للتحقق البرمجي المستقل (لا
    # لاستبدال القاعدة، فالقاعدة الحقيقية تبقى النص الذي يصل للموديل).
    #
    # ⚠️ إصلاح جذري (يوليو 2026، بعد أول نداء حي كامل كشف تناقضاً حقيقياً
    # - راجع _min_sl_pct_for أدناه للتفصيل الكامل): النسخة القديمة
    # (`_MIN_SL_PCT_1H`) كانت تخزن فقط رقم فريم الساعة الواحد، بينما
    # الدستور نفسه (النص أعلاه بالضبط) يحدد رقماً مختلفاً لكل فريم
    # (1h/30m/15m/5m) - وهذا منطقي فعلياً: فريم أصغر = تقلبات طبيعية
    # أصغر بين الشمعات = يستحق حد أدنى% أضيق (لا معنى لطلب نفس 0.5%
    # على فريم 5 دقايق كأنه فريم ساعة كاملة - سيكون واسعاً جداً بلا
    # داعٍ). الجدول الكامل التالي (بدل الرقم الواحد القديم) يطابق نص
    # الدستور 15.2 حرفياً بكل فريم مذكور فيه.
    _MIN_SL_PCT_BY_TF = {
        "BTC/USDT": {"1h": 0.5, "30m": 0.4, "15m": 0.3, "5m": 0.15, "3m": 0.15, "1m": 0.15},
        "ETH/USDT": {"1h": 0.6, "30m": 0.5, "15m": 0.35, "5m": 0.2, "3m": 0.2, "1m": 0.2},
    }
    # التوافق الخلفي (مسار قديم قد لا يزال يُستدعى من مكان آخر) - يبقى
    # موجوداً لكن لم يعد المصدر الفعلي للحساب (راجع _min_sl_pct_for).
    _MIN_SL_PCT_1H = {"BTC/USDT": 0.5, "ETH/USDT": 0.6}

    def _min_sl_pct_for(self, symbol, timeframe):
        """
        ⚠️ مصدر الحقيقة الوحيد المشترك لحساب الحد الأدنى% لمسافة SL -
        يُستدعى من كل من `_compute_min_sl_hint` (التلميح المُرسَل
        للموديل *قبل* أول محاولة) و`_diagnose_trade_plan` (الفحص الفعلي
        الذي يقرر قبول/رفض الخطة *بعد* الرد). هذا الاستخراج نفسه هو
        الإصلاح الجذري: قبل هذا التعديل، كانت كل دالة تحسب `min_pct`
        بمنطقها الخاص المنفصل (`_compute_min_sl_hint` كانت تستخدم 0.5%
        كافتراضي عام لأي فريم غير "1h"، بينما `_diagnose_trade_plan`
        كانت تستخدم `None` (أي "تجاهل شرط النسبة كلياً") لأي فريم غير
        "1h" تحديداً) - تناقض حقيقي موثّق أنتج 3 محاولات تصحيح فعلية
        بأول نداء حي على البنية الجديدة (فريم تنفيذ 5m): التلميح طلب
        SL >= 381 وحدة سعر (0.5% من ~76230)، لكن الفحص الفعلي كان
        يتطلب فقط >= 130 وحدة (1.5×ATR وحده، بلا شرط% إطلاقاً). الآن
        كلا الدالتين تستدعيان هذه الدالة الواحدة فتستحيل مفارقتهما.

        Returns: نسبة% (float) أو None لو الرمز/الفريم غير معروفين
        (عندها الفحص يعتمد فقط على 1.5×ATR، لا على حد نسبة مئوية).
        """
        tf_table = self._MIN_SL_PCT_BY_TF.get(symbol)
        if not tf_table:
            # رمز غير مُدرَج بالدستور (غير BTC/ETH) - لا حد نسبة% معروف
            # بثقة، الفحص يعتمد فقط على 1.5×ATR (لا نخترع رقماً تعسفياً)
            return None
        return tf_table.get(timeframe, tf_table.get("1h"))

    @staticmethod
    def _min_sl_buffer_distance(last_price, atr_val):
        """Deprecated compatibility shim.

        Stop breathing room cannot be derived from price/ATR alone because the
        causal model and recent same-side wick data are required. New code uses
        ``_place_structural_stop``. Returning zero prevents this legacy helper
        from silently imposing the old fixed percentage formula.
        """
        return 0.0

    def _compute_min_sl_hint(self, symbol, timeframe, entry_ind, entry_data, daily_bias=None):
        """
        ⚠️ حل جذري معماري (يوليو 2026، طلب صريح ومباشر من المستخدم):
        "بالنسبة لمعطيات الصفقة: بتنسى كلشي قلتلك ياه إنو 2.5% ومدري
        شو - بتحلل نظامي (الهيكل الميكانيكي البحت) بالنسبة للستوب متل
        مايكل بالزبط والتارغت وكلشي، حتى لو طلعت عشرة بالمية - يعني
        تركلي الإدارة المالية تبعي عَ جنب أثناء التحليل."

        **إعادة كتابة جذرية**: النسخة السابقة من هذه الدالة كانت تحقن
        "حدوداً" (حد أدنى% + حد أقصى 2.5%) كقيد على التحليل نفسه - هذا
        بالضبط ما طلب المستخدم إزالته. الآن: هذه الدالة **لا تحقن أي
        حد نسبة% إطلاقاً** - فقط تحقن حقيقتين ميكانيكيتين بحتتين لا
        علاقة لهما بإدارة رأس المال:
          1. الـbuffer الإلزامي (قسم [RISK_ENGINE] 15.3: max(0.3×ATR,
             0.2% من السعر)) - هذا جزء من **تعريف مكان الستوب الصحيح
             هيكلياً نفسه** عند مايكل (SL يوضع وراء المستوى الهيكلي
             بمسافة أمان صغيرة، لا عنده تماماً) - ليس قيد إدارة مخاطر.
          2. قائمة المستويات الهيكلية الحقيقية القريبة (حواف OB،
             سوينغ حقيقي، نقاط سحب سيولة) - الموديل يختار منها مباشرة
             (لا يخترع رقماً)، بلا أي حد أعلى/أدنى مفروض على المسافة
             نفسها - قد يكون القرب/البعد أي رقم، هذا يعتمد بالكامل على
             أين توجد المنطقة الهيكلية الحقيقية فعلياً بالبيانات.

        مقارنة R:R/نسبة% مع إدارة المخاطر تصير الآن **حصراً** بمرحلة
        منفصلة بعد اكتمال هذا التحليل (راجع _compute_risk_management_
        report) - معلوماتية بحتة، لا تؤثر على هذا التحليل الهيكلي إطلاقاً.

        Returns: نص جاهز للحقن بالبرومبت، أو نص فارغ لو لا توجد بيانات كافية.
        """
        try:
            last_price = None
            if entry_data and entry_data.get("closes"):
                last_price = float(entry_data["closes"][-1])
            if not last_price:
                return ""

            from ict_entry_checklist_engine import _structural_wick_buffer
            is_long_hint = daily_bias == "BULLISH"
            buffer_dist = _structural_wick_buffer(entry_data, is_long_hint)

            note = (
                f"\n⚠️ STRUCTURAL STOP CONCEPT (not a fixed point/percent rule): first "
                f"identify the causal low/high whose violation disproves this exact model "
                f"(sweep extreme, BOS origin, or outer edge of the entry PD array). Place "
                f"SL beyond that anchor, not at a risk-reward-friendly number. Recent "
                f"same-side wick noise has a median of {buffer_dist:.4g} price-units; this "
                f"is a data-derived breathing-room estimate, not an ICT constant. There is "
                f"NO minimum/maximum percentage distance: position size adapts to the "
                f"structural stop. Risk comparison happens only after analysis."
            )

            # ⚠️ قائمة المستويات الهيكلية الحقيقية القريبة - الموديل
            # يختار منها مباشرة (لا يخترع رقماً)، بلا أي حد أعلى/أدنى
            # على المسافة نفسها (راجع docstring أعلاه).
            if daily_bias in ("BULLISH", "BEARISH") and entry_data:
                try:
                    from ict_math_engine import find_structural_sl_anchors
                    anchors_result = find_structural_sl_anchors(
                        entry_data, is_long=(daily_bias == "BULLISH")
                    )
                    anchors = anchors_result.get("anchors", [])
                    if anchors:
                        anchors_list = "; ".join(
                            f"{a['kind']}={a['price']:.6g} (idx {a['index_from_end']}, {a['detail']})"
                            for a in anchors
                        )
                        note += (
                            f"\n\n⚠️ REAL STRUCTURAL SL ANCHORS (mechanically found on the "
                            f"actual data - per Michael's/ICT methodology, SL must be placed "
                            f"behind ONE of these REAL levels, NOT at an arbitrary number): "
                            f"{anchors_list}. Choose whichever one your specific Entry Model "
                            f"(A/B/C/D/E/F) actually depends on - do not pick a price between "
                            f"them just because it seems convenient."
                        )
                except Exception as e:
                    self.logger.warning(f"⚠️ Structural SL anchors injection failed (non-fatal): {e}")

            return note
        except Exception as e:
            self.logger.warning(f"⚠️ _compute_min_sl_hint failed (non-fatal): {e}")
            return ""

    def _compute_valid_price_range_hint(self, entry_data):
        """
        ⚠️ حل جذري إضافي (يوليو 2026، بعد اختبار حي عبر human_trades_
        backtest.py كشف هلوسة سعر حقيقية وخطيرة): مرحلة Entry اقترحت
        entry=98,870 بينما النطاق الفعلي الحقيقي لسعر BTC بتلك الفترة
        (من نفس بيانات الشموع المُرسَلة بالبرومبت نفسه!) كان
        72,323-82,174 - رقم بعيد تماماً عن الواقع، لا علاقة له بأي
        منطق تحليلي، أقرب لخطأ قراءة/تركيب أرقام عشوائي. طبقة الحماية
        (`audit_signal_prices`) أمسكته بنجاح - لكن فقط **بعد** الرد،
        مُكلِّفة 3 محاولات API كاملة فاشلة (~7 دقائق) قبل الرجوع لـHOLD.

        نفس فلسفة `_compute_min_sl_hint` بالضبط: بدل انتظار الهلوسة ثم
        اكتشافها، نحقن النطاق الصحيح المسموح به صراحة **قبل** أول
        محاولة - نفس الحساب الحسابي بالضبط المُستخدم لاحقاً بـ
        `audit_signal_prices` (max(highs)*1.05 كحد أعلى، min(lows)*0.95
        كحد أدنى) - مصدر حقيقة واحد مشترك، يستحيل تناقضهما.

        Returns: نص جاهز للحقن بالبرومبت، أو نص فارغ لو لا توجد بيانات كافية.
        """
        try:
            highs = entry_data.get("highs") if entry_data else None
            lows = entry_data.get("lows") if entry_data else None
            closes = entry_data.get("closes") if entry_data else None
            if not highs or not lows or not closes:
                return ""

            range_high = max(highs) * 1.05
            range_low = min(lows) * 0.95
            last_price = closes[-1]

            return (
                f"\n⚠️ PRE-COMPUTED VALID PRICE RANGE (mechanically calculated from the "
                f"actual candle data shown above - use this directly, this prevents a "
                f"documented real failure mode where a wildly out-of-range price "
                f"(e.g. proposing entry=98,870 when the real price range was "
                f"72,000-82,000) required 3 expensive retries before being caught): "
                f"the current/last price is ~{last_price:.6g}. Every price you output "
                f"(entry, stop_loss, tp) MUST fall within [{range_low:.6g}, "
                f"{range_high:.6g}] - this is the actual historical range of the data "
                f"shown to you, with a small margin for near-term movement. If you find "
                f"yourself writing a number outside this range, STOP - you have made an "
                f"arithmetic or transcription error; re-derive the number by looking at "
                f"the actual candle data again, digit by digit."
            )
        except Exception as e:
            self.logger.warning(f"⚠️ _compute_valid_price_range_hint failed (non-fatal): {e}")
            return ""

    # ══════════════════════════════════════════════════════════
    #  MECHANICAL ENTRY MODEL CHECKLIST (حل جذري، يوليو 2026)
    # ══════════════════════════════════════════════════════════
    # ⚠️ طلب صريح ومفصّل من المستخدم أثناء جلسة عمل مستقلة طويلة:
    # "مايكل عنده مثلاً واحد اتنين تلاتة أربعة شروط - موجودين الأربعة
    # تحققوا؟ في صفقة. مافي شي اعتباطي، الدخول والتارغت والستوب كيف
    # بيحطن مايكل وعلى أي أساس. لو لقى واحد واتنين وتلاتة ومالقاش
    # أربعة، بس مش سلبي على الأربعة (بس ناطر تشكّلها) - لازم يعطي
    # توصية: إذا تحقق الشرط الرابع هيك رح يصير الدخول/الستوب/التارغت.
    # أما لو فعلاً ما تحققت الشروط (شرط سلبي حقيقي) - هون بس HOLD."
    #
    # قبل هذا الإصلاح: قرار BUY_LIMIT/SELL_LIMIT/HOLD كان بالكامل بيد
    # "فهم" النموذج اللغوي للسياق الكامل دفعة واحدة - بلا تفكيك صريح
    # لكل شرط من شروط نموذج الدخول (قسم [ENTRY_MODELS] بالدستور) على
    # حدة. هذا يعني أحياناً HOLD حتى لو 3 من 4 شروط متحققة فعلياً
    # بالبيانات الخام (الموديل لم "يربط" الشروط بوضوح كافٍ - بالضبط
    # وصف المستخدم "مش عارف راسه من رجليه").
    #
    # الحل: ict_entry_checklist_engine.py يطبّق تفكيكاً ميكانيكياً
    # صريحاً بايثون بحتاً (صفر AI) لثلاثة من نماذج الدخول الستة
    # (A: OTE+OB، B: Sweep+FVG، C: BOS Pullback - الأكثر تكراراً حسب
    # الدستور نفسه) - كل شرط True (متحقق)/False (فشل حقيقي)/PENDING
    # (لم يحدث بعد لكن ممكن). نحقن هنا **نتيجة هذا التفكيك جاهزة**
    # (لا نطلب من الموديل إعادة اشتقاقها) + خطة رقمية كاملة جاهزة لو
    # PENDING_SETUP - مهمة الموديل الآن: التحقق من هذا التفكيك وبناء
    # قراره النهائي عليه (قد يخالفه بسياق إضافي حقيقي، لكن يجب أن
    # يستشهد صراحة لماذا - نفس فلسفة كل حقنة رياضية أخرى بهذا المشروع).
    def _build_mechanical_checklist_block(self, entry_data, daily_bias, htf_data_sources=None,
                                           htf_major_data=None):
        if not entry_data or not entry_data.get("closes") or daily_bias not in ("BULLISH", "BEARISH"):
            return "", None
        try:
            from ict_entry_checklist_engine import evaluate_all_entry_models
            result = evaluate_all_entry_models(entry_data, daily_bias, htf_data_sources=htf_data_sources,
                                                htf_major_data=htf_major_data)
        except Exception as e:
            self.logger.warning(f"⚠️ Mechanical entry checklist failed (non-fatal): {e}")
            return "", None

        lines = [
            "\n── MECHANICAL ENTRY MODEL CHECKLIST (deterministic, condition-by-"
            "condition - NOT your judgment; computed independently from ICT "
            "Entry Models A/B/C per section [ENTRY_MODELS]) ──",
        ]
        for m in result["all_models"]:
            cond_text = "; ".join(
                f"{c['name']}={c['status']}" for c in m["conditions"]
            )
            lines.append(f"{m['model']}: {m['status']} [{cond_text}]")

        if result["final_status"] == "READY":
            plan = result["chosen_model"]["plan"]
            lines.append(
                f"\n✅ {result['chosen_model']['model']} has ALL conditions met "
                f"(including timing/LTF, if already checked) - a READY setup. "
                f"Mechanically computed plan (verify and use unless you have a "
                f"specific, citable reason not to): direction={plan['direction']}, "
                f"entry={plan['entry']}, stop_loss={plan['stop_loss']}, tp={plan['tp']}, "
                f"rr={plan['rr']} ({plan['basis']})."
            )
        elif result["final_status"] == "PENDING_SETUP":
            plan = result["chosen_model"]["plan"]
            pending_conds = [c["name"] for c in result["chosen_model"]["conditions"] if c["status"] == "PENDING"]
            lines.append(
                f"\n⏳ {result['chosen_model']['model']} has ALL structural conditions "
                f"met EXCEPT: {pending_conds} (still pending, NOT failed - these can "
                f"still occur). Per the user's explicit instruction: this is NOT a "
                f"reason for HOLD - this is exactly the definition of a pending limit "
                f"order (BUY_LIMIT/SELL_LIMIT). Mechanically computed plan (verify and "
                f"use unless you have a specific, citable reason not to): "
                f"direction={plan['direction']}, entry={plan['entry']}, "
                f"stop_loss={plan['stop_loss']}, tp={plan['tp']}, rr={plan['rr']} "
                f"({plan['basis']}). You MUST output {plan['direction']} with these "
                f"(or your own justified refinement of these) numbers unless you can "
                f"cite a SPECIFIC condition that has genuinely, mechanically failed."
            )
        else:
            lines.append(
                f"\n⛔ NO entry model qualifies - each one has at least one condition "
                f"that GENUINELY FAILED (not merely pending): {result['hold_reason_detail']}. "
                f"Per the user's explicit instruction: THIS is what a real HOLD looks "
                f"like - a specific, named, mechanically-verified failure, not vague "
                f"uncertainty. If you output HOLD, you MUST reference one of these "
                f"specific failed conditions in your reasoning."
            )

        return "\n".join(lines), result

    # ⚠️ حد أقصى صارم لمسافة SL = 2.5% (طلب صريح من المستخدم، يوليو
    # 2026، مدعوم بمصادر خارجية موثوقة - راجع البحث المرفق بسجل الجلسة):
    # - قاعدة "1-2% مخاطرة لكل صفقة" شبه إجماع بين كل مصادر إدارة
    #   المخاطر الاحترافية المفحوصة (CME Group Education, "2% Rule")،
    #   وSL أعرض من ~2-3% يجعل حجم المركز اللازم للحفاظ على نفس نسبة
    #   المخاطرة صغيراً جداً أو يطلب رافعة عالية خطرة لتعويضه.
    # - مصادر ICT/SMC (tradingstrategyguides.com، backtrex.com) تؤكد أن
    #   أسلوب ICT تحديداً يميل لـ"stops tight" (مبنية على نقطة إبطال
    #   دقيقة - Judas Swing/OB/sweep - وليس نطاقاً عريضاً)، وهذا بالضبط
    #   ما ينتج نسب R:R المرتفعة (1:5, 1:10) التي تُعرف بها ICT.
    # - مصدر مستقل (topwealthtrading.com) يؤكد الحل الصحيح عندما يكون
    #   الـSL الهيكلي أعرض من الميزانية المسموحة: "الجواب ليس تقريب
    #   الـSL، الجواب هو تصغير حجم المركز أو تخطي الصفقة بالكامل" -
    #   بالضبط نفس فلسفة "Option D ممنوع" الموجودة أصلاً بدستور المشروع.
    # لذلك: هذا الحد الأقصى **لا يُطبَّق بتقريب SL تعسفياً للداخل**
    # (يكسر الأساس الهيكلي، ويحوّل SL لرقم بلا معنى - بالضبط الخطأ
    # الذي يحذر منه كل مصدر مفحوص) - يُطلب من النموذج إيجاد مستوى
    # هيكلي أضيق حقيقي (OB/FVG/swing أقرب)، وإن لم يوجد، HOLD صراحة.
    _MAX_SL_PCT = 2.5

    def _diagnose_trade_plan(self, final_result, symbol, timeframe, entry_ind, entry_data=None,
                              daily_bias=None):
        """
        ⚠️ بوابة تحقق نهائية موحّدة (يوليو 2026، بعد تدقيق شامل كامل
        للمشروع بطلب صريح من المستخدم: "صلح كامل الكود وملف المعرفة
        وكل المشاكل... مسموحلك تستخدم كل قدراتك").

        ⚠️ اكتشاف معماري جذري أثناء بناء هذه الدالة: brain_core.py
        (المسار الحي القديم) عنده أصلاً طبقتي حماية ناضجتين ومُختبرتين
        (VerificationLayer.verify، RiskManager.evaluate) تفحصان بالضبط
        نفس أنواع المشاكل المكتشفة حديثاً (SL/TP معكوس، R:R غير محسوب
        فعلياً، أسعار مختلقة خارج مدى البيانات) - **لكن multi_pass_
        analysis.py (المسار الجديد المستخدم بكل الباك تيست) كان مبنياً
        بمعزل تام عنهما**. لذلك هذه الدالة لا تُعيد اختراع تلك الفحوصات
        من الصفر - تستدعي الأدوات الناضجة الموجودة أصلاً بالمشروع
        (self.verifier, self.authenticity.audit_signal_prices,
        audit_last_candle_report, detect_selective_wick_citation,
        cross_check_bos_reconciliation) وتُدمج نتائجها مع فحوصات
        منطقية أساسية إضافية (اتجاه SL/TP، R:R محسوب مباشرة) ضمن
        تقرير واحد موحّد - "فهم شامل"، لا قائمة تصحيحات معزولة قد
        يُصلح أحدها ويكسر آخر بلا قصد (وهذا حدث فعلياً: تصحيح مسافة
        SL بمعزل عن اتجاهه أنتج SL معكوساً تماماً بمحاولة تالية).

        Returns: قائمة نصوص (issues) بكل مشكلة موجودة فعلياً - قائمة
        فارغة تعني الصفقة سليمة بكل الأبعاد المفحوصة معاً.
        """
        issues = []
        signal = final_result.get("signal")
        # ⚠️ BUY_LIMIT/SELL_LIMIT (أوامر معلقة - اتجاه
        # معروف لكن السعر لم يصل بعد) تمر بنفس
        # فحوصات سلامة خطة الصفقة تماماً مثل
        # BUY/SELL الفورية (R:R، اتجاه SL/TP، مسافة
        # SL، الحد الأقصى 2.5%) - الفرق الوحيد هو
        # متى يُنفّذ فعلياً (فوراً لـ BUY/SELL، لاحقاً
        # عند وصول السعر لـ BUY_LIMIT/SELL_LIMIT) - لكن سلامة
        # الخطة نفسها (اتجاه/مسافة/R:R) يجب أن تُفحص الآن
        # وقت إصدارها لا وقت تنفيذها - تماماً مثل أمر
        # ليمت حقيقي على بورصة حقيقية (يُفحص ويُوضع
        # فوراً، لا يُنتظر لحظة التنفيذ الفعلي).
        if signal not in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
            return issues

        entry = final_result.get("entry")
        sl = final_result.get("stop_loss")
        tp = final_result.get("tp")

        # ── فحوصات الأدوات الناضجة الموجودة أصلاً بالمشروع (لا نعيد
        # اختراعها) - تُشغَّل دائماً بغض النظر عن اكتمال الأرقام، لأنها
        # تفحص أبعاداً أخرى (نص/هلوسة) مستقلة عن سلامة entry/sl/tp ──
        if entry_data:
            try:
                price_audit = self.authenticity.audit_signal_prices(final_result, entry_data)
                if not price_audit.get("valid", True):
                    for iss in price_audit.get("issues", []):
                        issues.append(f"PRICE_HALLUCINATION: {iss}")
            except Exception as e:
                self.logger.warning(f"⚠️ audit_signal_prices error: {e}")

            try:
                candle_audit = self.authenticity.audit_last_candle_report(final_result, entry_data)
                if candle_audit.get("checked") and not candle_audit.get("valid", True):
                    issues.append(
                        f"LAST_CANDLE_HALLUCINATION: last_candle_report does not match actual "
                        f"Entry TF candle data - {candle_audit.get('issues')}"
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ audit_last_candle_report error: {e}")

            try:
                bos_check = self.authenticity.cross_check_bos_reconciliation(final_result, entry_data)
                if bos_check.get("flagged"):
                    issues.append(f"BOS_MECHANICAL_MISMATCH: {bos_check.get('reason')}")
            except Exception as e:
                self.logger.warning(f"⚠️ cross_check_bos_reconciliation error: {e}")

        if not all(isinstance(v, (int, float)) for v in (entry, sl, tp)) or entry == 0:
            # ⚠️ إصلاح خطر حقيقي مُكتشف بتدقيق شامل إضافي (يوليو 2026):
            # الإصدار السابق من هذا الفحص كان "يتجاهل بصمت" أي BUY/SELL
            # بلا أرقام كاملة (يرجع issues فارغة = "لا مشكلة") بدلاً من
            # اعتبار غياب الأرقام نفسه مشكلة حاسمة. بالوضع الحي تحديداً
            # (is_backtest=False)، الـschema (راجع _entry_schema) لا
            # تفرض entry/stop_loss/tp كحقول "required" - وهذا بالضبط
            # نفس الباگ الحرج الموثّق سابقاً بتعليق _entry_schema (رد
            # فعلي: BUY بثقة 83% مع stop_loss=None بالكامل!). بدون هذا
            # الفحص هنا، تلك الصفقة كانت ستمرّ عبر _diagnose_trade_plan
            # بأكملها دون أن يُكتشف غيابها التام للأرقام - فجوة حرجة في
            # طبقة الدفاع الجديدة نفسها. الحل: أي BUY/SELL بأرقام ناقصة
            # يُعتبر فشلاً حاسماً الآن، يُعامَل بنفس آلية إعادة المحاولة/
            # HOLD الإجباري مثل أي مشكلة أخرى - لا مرور صامت بعد الآن.
            missing = [
                name for name, v in (("entry", entry), ("stop_loss", sl), ("tp", tp))
                if not isinstance(v, (int, float))
            ]
            if missing or entry == 0:
                issues.append(
                    f"MISSING_TRADE_NUMBERS: signal={signal} but required numeric fields are "
                    f"missing or invalid: {missing or ['entry=0']} (entry={entry!r}, sl={sl!r}, "
                    f"tp={tp!r}). A BUY/SELL signal MUST include complete, valid entry/stop_loss/"
                    f"tp numbers - this is non-negotiable regardless of live or backtest mode."
                )
            return issues

        is_long = signal in ("BUY", "BUY_LIMIT")

        # ⚠️ حل جذري لانتهاك حقيقي خطير اكتُشف بنداء حي فعلي (يوليو
        # 2026): الدستور نفسه ينص صراحة بقسم [ENTRY_MODELS]/12.6 (نص
        # البرومبت بـ_build_entry_prompt، بند 4): "The final signal
        # MUST match the Daily Bias direction - it is the commander"
        # - لكن هذا كان مجرد **تعليمات نصية تُذكر لا تُفرض**. اختبار حي
        # فعلي أظهر: Daily Bias=BULLISH (ثابت رياضياً عبر مرساة الانحياز
        # الميكانيكية STRONG)، لكن مرحلة Entry أخرجت SELL_LIMIT/BEARISH
        # بالكامل، مع "تبرير" نصي طويل (إعادة تفسير Weekly/4H كأهم من
        # Daily) - هذا **ليس** استثناءً مبرَّراً؛ هذا خرق مباشر لقاعدة
        # "القائد" المفروضة بالدستور نفسها بلا أي غموض بالنص، والنموذج
        # تجاوزها بحجة سياقية عامة، لا استشهاد رياضي محدد.
        #
        # ⚠️ فرق جوهري عن audit_bias_anchor_consistency (المرساة
        # الميكانيكية بمرحلة Daily): تلك تسمح بالمخالفة **لو استُشهد
        # بحدث انعكاس حقيقي أحدث زمنياً** (لأن الانحياز نفسه قابل
        # للنقاش برهانياً حتى تلك اللحظة). هذا الفحص هنا مختلف تماماً:
        # بمجرد أن Daily Bias **حُسم فعلياً** (اجتاز GATE 2 بثقة كافية)،
        # الدستور يُلزم أن يكون هو اتجاه التنفيذ النهائي دائماً - لا
        # مجال لـ"إعادة تفسير" الانحياز بمرحلة التنفيذ ذاتها (ذلك دور
        # مرحلة Daily فقط، لا مرحلة Entry). لذلك هذا الفحص **صارم بلا
        # استثناء** (فشل حاسم يُعاد بموجبه اشتقاق الخطة بالكامل)، بعكس
        # مرونة المرساة بمرحلة Daily.
        if daily_bias in ("BULLISH", "BEARISH"):
            expected_long = (daily_bias == "BULLISH")
            if is_long != expected_long:
                issues.append(
                    f"SIGNAL_CONTRADICTS_DAILY_BIAS: signal={signal} (direction="
                    f"{'LONG' if is_long else 'SHORT'}) but the Daily Bias (Step 2, "
                    f"already established as the commander per section [ENTRY_MODELS] "
                    f"12.6) is {daily_bias}. Per the constitution, the Entry TF does "
                    f"NOT get to override or re-interpret the Daily Bias direction - "
                    f"that reinterpretation is Daily's job alone. Either find a valid "
                    f"{'LONG' if expected_long else 'SHORT'} setup consistent with the "
                    f"Daily Bias, or output HOLD if no such setup exists - do not "
                    f"reverse direction based on Weekly/4H/15m structure alone."
                )

        # ── فحص اتجاه SL/TP (نفس منطق RiskManager.evaluate الأصلي،
        # مُطبَّق هنا أيضاً لأن multi_pass_analysis.py لا يمر عبر
        # RiskManager.evaluate إطلاقاً بمساره الحالي) ──
        if is_long:
            if not (sl < entry):
                issues.append(
                    f"SL_WRONG_SIDE: signal is BUY (entry={entry}) but stop_loss={sl} is NOT "
                    f"below entry. For a LONG position, SL MUST be below entry (you exit at a "
                    f"loss if price falls below entry) - this SL is logically inverted and makes "
                    f"the trade plan non-executable as written."
                )
            if not (tp > entry):
                issues.append(
                    f"TP_WRONG_SIDE: signal is BUY (entry={entry}) but tp={tp} is NOT above "
                    f"entry. For a LONG position, TP MUST be above entry (the profit target is "
                    f"in the direction of the expected move upward)."
                )
        else:
            if not (sl > entry):
                issues.append(
                    f"SL_WRONG_SIDE: signal is SELL (entry={entry}) but stop_loss={sl} is NOT "
                    f"above entry. For a SHORT position, SL MUST be above entry (you exit at a "
                    f"loss if price rises above entry) - this SL is logically inverted and makes "
                    f"the trade plan non-executable as written."
                )
            if not (tp < entry):
                issues.append(
                    f"TP_WRONG_SIDE: signal is SELL (entry={entry}) but tp={tp} is NOT below "
                    f"entry. For a SHORT position, TP MUST be below entry (the profit target is "
                    f"in the direction of the expected move downward)."
                )

        # ⚠️ حل جذري معماري (يوليو 2026، طلب صريح ومباشر من المستخدم):
        # "بالنسبة لمعطيات الصفقة (دخول/ستوب/تارغت): بتنسى كلشي قلتلك
        # ياه إنو 2.5% ومدري شو - بتحلل نظامي (يعني الهيكل الميكانيكي:
        # منطقة حقيقية + buffer) بالنسبة للستوب متل مايكل بالزبط
        # والتارغت وكلشي، حتى لو طلعت عشرة بالمية وشو ما كان - يعني
        # تركلي الإدارة المالية تبعي عَ جنب أثناء التحليل. بعد ما تخلص
        # كل التحليل حسب مايكل بالزبط، بعدين بتشوف التارغت أديش عاطي
        # ريسك ريورد، هل 3:1 ومافوق ولا أقل - واقترحلي ياها على
        # الحالتين، بس قلي إذا متطابقة مع إدارتي المالية ولا لأ.
        # الستوب ما دخلك فيه بإدارتي."
        #
        # التطبيق الحرفي لهذا الطلب: كل الفحوصات الرياضية التالية
        # (RR_BELOW_MINIMUM، SL_TOO_TIGHT بكل أشكالها [min_pct/1.5×ATR/
        # buffer]، SL_TOO_WIDE بحد 2.5%) **أُزيلت بالكامل من قائمة
        # `issues` الحاسمة (المانعة/الرافضة)** - لم تعد تُسبب أي إعادة
        # محاولة أو تحويل قسري لـHOLD. الستوب/التارغت/الدخول الآن
        # يُحدَّدون **حصراً** بمعايير مايكل الهيكلية البحتة (المرحلة
        # السابقة: SIGNAL_CONTRADICTS_DAILY_BIAS، SL_WRONG_SIDE/
        # TP_WRONG_SIDE، SL_NOT_STRUCTURAL - هذه الثلاثة تبقى حاسمة
        # لأنها ليست "إدارة مخاطر"، هي شرط منطقي/هيكلي بحت: اتجاه
        # الصفقة يجب أن يطابق الانحياز المُقرَّر، SL/TP يجب أن يكونا
        # بالجهة الصحيحة رياضياً، والستوب يجب أن يكون عند منطقة حقيقية
        # لا رقماً مختلَقاً - هذه كلها معايير ICT هيكلية، لا معايير
        # إدارة رأس مال).
        #
        # بدلها: دالة جديدة منفصلة تماماً `_compute_risk_management_
        # report()` (تُستدعى لاحقاً بعد اكتمال كل التحليل الهيكلي)
        # تحسب R:R الفعلي ونسبة SL% **كتقرير معلوماتي بحت** يُرفَق
        # بالنتيجة النهائية (`_risk_management_report`) - يخبر المستخدم
        # صراحة "هل هذه الصفقة، بأرقامها الهيكلية الأصلية بلا أي تعديل،
        # تطابق إدارة مخاطر 2.5%/R:R≥3:1 أم لا" - معلومة تُعرَض دائماً،
        # لا شرط قبول/رفض. راجع _compute_risk_management_report أدناه.

        # ⚠️ حل جذري جوهري (يوليو 2026، طلب صريح ومباشر من المستخدم:
        # "الستوب كتير صغير مع إنو سامحتلك لحد 2.5% وانت عم تحط الستوب
        # عالنسبة، إنما مايكل بيحط الستوب اعتماداً عالمناطق وليس
        # عالنسبة المئوية - تحت منطقة كذا كذا"). كل الفحوصات أعلاه
        # (SL_TOO_TIGHT/SL_TOO_WIDE) تتحقق فقط من **مسافة رقمية مجردة**
        # (نسبة% أو مضاعف ATR) - لا شيء منها كان يتحقق أن SL يقع فعلياً
        # **عند** مستوى هيكلي حقيقي (حافة OB، سوينغ حقيقي، نقطة سحب
        # سيولة) بدل رقم يحقق شرط المسافة حسابياً بلا أي ارتباط مكاني
        # حقيقي بالبيانات - وهذا بالضبط يفسّر انضراب SL بفارق ضئيل جداً
        # بصفقات موثّقة سابقة (السقف/الأرضية % كانا يُحققان، لكن الرقم
        # نفسه لم يكن عند أي حماية هيكلية حقيقية). راجع
        # AuthenticityEngine.audit_sl_is_structural وict_math_engine.
        # find_structural_sl_anchors للتفصيل الكامل.
        if entry_data:
            try:
                atr_val_for_struct = (entry_ind or {}).get("atr")
                struct_check = self.authenticity.audit_sl_is_structural(
                    entry, sl, is_long, entry_data, atr_val=atr_val_for_struct
                )
                if struct_check.get("checked") and not struct_check.get("is_structural"):
                    issues.append(
                        f"SL_NOT_STRUCTURAL: stop_loss={sl} does not match any genuine "
                        f"structural level found in the actual data (Order Block edge, "
                        f"swing point, or liquidity sweep point) - per Michael's (ICT) "
                        f"methodology, SL must be placed behind a REAL structural zone, "
                        f"NOT at a number chosen merely to satisfy a percentage/ATR "
                        f"distance rule. Actual structural levels available on this "
                        f"side: {struct_check.get('nearest_anchors_text')}. Re-derive SL "
                        f"to sit at (or just beyond, with the mandatory buffer) ONE of "
                        f"these specific real levels - do not invent a number between them."
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ audit_sl_is_structural error: {e}")

        return issues

    def _compute_risk_management_report(self, final_result, symbol, timeframe, entry_ind):
        """Report actual risk geometry without changing structural prices.

        ``MIN_RR_POLICY`` and ``MAX_SL_POLICY_PCT`` are optional user filters;
        zero disables either filter. A failed filter can decline execution but
        must never move TP/SL to manufacture compliance.
        """
        signal = final_result.get("signal")
        if signal not in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"):
            return None
        entry = final_result.get("entry")
        sl = final_result.get("stop_loss")
        tp = final_result.get("tp")
        if not all(isinstance(v, (int, float)) for v in (entry, sl, tp)) or entry == 0:
            return None
        sl_dist = abs(entry - sl)
        if sl_dist <= 0:
            return None
        rr_actual = round(abs(tp - entry) / sl_dist, 2)
        sl_distance_pct = round(sl_dist / entry * 100, 3)
        min_rr = max(0.0, float(getattr(Config, "MIN_RR_POLICY", 0)))
        max_sl_pct = max(0.0, float(getattr(Config, "MAX_SL_POLICY_PCT", 0)))
        rr_pass = None if min_rr == 0 else rr_actual >= min_rr
        sl_pass = None if max_sl_pct == 0 else sl_distance_pct <= max_sl_pct
        enabled_results = [x for x in (rr_pass, sl_pass) if x is not None]
        matches = all(enabled_results) if enabled_results else None
        policies = []
        if min_rr:
            policies.append(f"min_rr={min_rr}: {'PASS' if rr_pass else 'SKIP'}")
        if max_sl_pct:
            policies.append(f"max_sl_pct={max_sl_pct}: {'PASS' if sl_pass else 'SKIP'}")
        summary = (
            f"R:R الفعلية={rr_actual}:1، مسافة SL={sl_distance_pct}%. "
            + ("سياسات التنفيذ الاختيارية: " + "; ".join(policies)
               if policies else
               "لا يوجد حد R:R أو SL% ثابت مفعّل؛ المستويات لم تتغير.")
        )
        return {
            "rr_actual": rr_actual,
            "sl_distance_pct": sl_distance_pct,
            "min_rr_policy": min_rr,
            "rr_policy_pass": rr_pass,
            "max_sl_policy_pct": max_sl_pct,
            "sl_policy_pass": sl_pass,
            "matches_enabled_user_policies": matches,
            "summary_text": summary,
        }

    def _try_mechanical_sl_fix(self, final_result, entry_data, entry_ind, issues):
        """
        يحاول إصلاح مشاكل الستوب البحتة (SL_NOT_STRUCTURAL/SL_WRONG_SIDE)
        رياضياً مباشرة، بلا أي نداء API - يجمّد entry/signal/tp كما هما
        تماماً، يستبدل فقط stop_loss بأقرب مرساة هيكلية حقيقية صحيحة.

        Returns: final_result مُعدَّل (نسخة جديدة) لو نجح الإصلاح
                 الميكانيكي لكل المشاكل المذكورة، أو None لو تبقّت
                 مشاكل أخرى غير قابلة للإصلاح الميكانيكي (عندها يجب
                 العودة لمسار إعادة الاشتقاق الكامل عبر API).
        """
        only_sl_issues = all(
            any(iss.startswith(prefix) for prefix in self._MECHANICALLY_FIXABLE_ISSUE_PREFIXES)
            for iss in issues
        )
        if not only_sl_issues or not entry_data:
            return None

        try:
            from ict_math_engine import find_structural_sl_anchors
            signal = final_result.get("signal")
            entry = final_result.get("entry")
            is_long = signal in ("BUY", "BUY_LIMIT")
            if not isinstance(entry, (int, float)):
                return None

            sl_result = find_structural_sl_anchors(entry_data, is_long=is_long, reference_price=entry)
            anchors = sl_result.get("anchors", [])
            if not anchors:
                return None

            # The free-form AI path cannot prove which anchor caused its entry.
            # Do not silently choose the nearest one to improve RR. Require an
            # explicit causal anchor from the derived plan; otherwise re-derive/HOLD.
            rationale = final_result.get("stop_rationale") or {}
            anchor_price = rationale.get("anchor_price")
            if not isinstance(anchor_price, (int, float)):
                return None
            from ict_entry_checklist_engine import _place_structural_stop
            fixed_sl, fixed_rationale = _place_structural_stop(
                entry_data, float(anchor_price), is_long,
                rationale.get("anchor_kind", "AI_DECLARED_CAUSAL_ANCHOR"),
            )

            fixed_result = dict(final_result)
            fixed_result["stop_loss"] = round(float(fixed_sl), 6)
            fixed_result["stop_rationale"] = fixed_rationale
            fixed_result["_sl_mechanically_fixed"] = True
            fixed_result["_sl_mechanical_fix_anchor"] = anchors[0]
            return fixed_result
        except Exception as e:
            self.logger.warning(f"⚠️ _try_mechanical_sl_fix error (non-fatal): {e}")
            return None

    def _verify_and_finalize_trade_plan(self, final_result, symbol, timeframe,
                                         entry_data, entry_ind, entry_candles_text,
                                         entry_indicators_text, weekly_result,
                                         daily_result, h4_result, h15_result,
                                         is_backtest, entry_authenticity_text,
                                         max_retries=3, min_sl_hint="", session_text=""):
        """
        يستدعي _diagnose_trade_plan (الفحص الشامل الموحّد لكل أبعاد
        سلامة خطة الصفقة معاً) بعد كل محاولة، ويعيد المحاولة مع رسالة
        تصحيح واحدة تجمع *كل* المشاكل المكتشفة دفعة واحدة (لا رسالة
        منفصلة لكل بُعد على التوالي - هذا يمنع بالضبط النمط الذي حدث
        فعلياً: تصحيح بُعد واحد (مسافة SL) يكسر بُعداً آخر (اتجاه SL)
        لم يكن يُفحص أصلاً بتلك اللحظة).

        ⚠️ الفرق الجوهري عن النسخة السابقة (_verify_and_retry_sl_distance):
        لو فشلت كل محاولات التصحيح (max_retries استُنفدت والمشاكل ما
        زالت قائمة)، **لا نُخرج الصفقة الفاسدة للمستخدم أبداً** - نحوّلها
        HOLD صراحة مع توثيق كامل للسبب. توثيق زائف بصمت أخطر من عدم
        وجود توصية إطلاقاً - نفس الفلسفة الأساسية لكل هذا المشروع
        ("الصدق التقني الكامل بلا تجميل").
        """
        if not isinstance(final_result, dict):
            return final_result

        daily_bias_val = daily_result.get("direction") if isinstance(daily_result, dict) else None
        issues = self._diagnose_trade_plan(final_result, symbol, timeframe, entry_ind, entry_data,
                                            daily_bias=daily_bias_val)

        # ⚠️ محاولة الإصلاح الميكانيكي أولاً (صفر نداء API) - راجع
        # docstring _try_mechanical_sl_fix للتفصيل الكامل. فقط لو
        # المشاكل كلها من نوع "ستوب بحت" القابل للحساب المباشر.
        if issues:
            mechanically_fixed = self._try_mechanical_sl_fix(final_result, entry_data, entry_ind, issues)
            if mechanically_fixed is not None:
                remaining_issues = self._diagnose_trade_plan(
                    mechanically_fixed, symbol, timeframe, entry_ind, entry_data, daily_bias=daily_bias_val
                )
                if not remaining_issues:
                    self.logger.info(
                        "✅ [Trade Plan Validation] إصلاح ميكانيكي مباشر (بلا نداء API) نجح - "
                        "الستوب فقط استُبدل بمرساة هيكلية حقيقية، الدخول/الاتجاه/الهدف لم يتغيروا."
                    )
                    return mechanically_fixed
                # لو بقيت مشاكل أخرى بعد الإصلاح الميكانيكي، نكمل بالمسار العادي أدناه

        attempt = 0
        while issues and attempt < max_retries:
            attempt += 1
            self.logger.warning(
                f"⚠️ [Trade Plan Validation] مشاكل مكتشفة بمحاولة {attempt} "
                f"(كل الأبعاد معاً): {issues} - إعادة محاولة موحّدة..."
            )
            # ⚠️ حل جذري معماري (يوليو 2026، طلب صريح من المستخدم - راجع
            # التعليق الكامل بـ_diagnose_trade_plan): بما أن RR_BELOW_
            # MINIMUM/SL_TOO_TIGHT/SL_TOO_WIDE لم تعد ضمن `issues`
            # إطلاقاً (أُزيلت كقيود حاسمة - أصبحت تقريراً معلوماتياً
            # منفصلاً بعد التحليل)، ما تبقى بـ`issues` الآن هو حصراً
            # مشاكل هيكلية/منطقية حقيقية (اتجاه معكوس، تناقض مع Daily
            # Bias، ستوب غير مرتبط بمنطقة حقيقية، أرقام ناقصة) - رسالة
            # التصحيح تبسّطت لتعكس هذا فقط، بلا أي ذكر لسقف % أو R:R
            # كشرط إلزامي هنا (يبقى R:R يُذكر بمرحلة التقرير النهائي
            # فقط، معلوماتياً - راجع _compute_risk_management_report).
            correction_note = (
                "\n\n⚠️ CRITICAL TRADE PLAN CORRECTION REQUIRED: Your previous entry/SL/tp "
                "plan has the following STRUCTURAL/LOGICAL problems (ALL must be fixed "
                "together in this single re-derivation, not one at a time):\n"
                + "\n".join(f"  {i+1}. {iss}" for i, iss in enumerate(issues))
                + "\n\nRe-derive entry, stop_loss, and tp FROM SCRATCH as one coherent, "
                "internally-consistent plan per Michael's (ICT) methodology: SL must sit at "
                "(or just beyond, with the mandatory buffer) a REAL structural level found in "
                "the actual data - not an arbitrary number; SL and tp must be on the "
                "logically correct sides of entry; the signal direction must match the "
                "established Daily Bias. Note: there is NO percentage cap or minimum R:R "
                "requirement at this stage - place the stop exactly where Michael's "
                "methodology says it structurally belongs, however wide or tight that turns "
                "out to be. The risk-management comparison (R:R, position sizing) happens "
                "separately AFTER this structural plan is finalized, purely as information - "
                "it will not cause a retry or rejection here."
                + ("\n\nOnly output HOLD if, after this re-derivation, no genuine structural "
                   "setup can be identified at all (not because of R:R or distance percentage)."
                   if is_backtest else "")
            )
            retry_prompt = self._build_entry_prompt(
                symbol, timeframe, entry_candles_text, entry_indicators_text,
                weekly_result, daily_result, h4_result, h15_result, is_backtest,
                entry_authenticity_text, min_sl_hint=min_sl_hint, session_text=session_text,
                entry_data=entry_data,
            ) + correction_note
            # ⚠️ allow_hold=True هنا تحديداً (إصلاح تناقض تعليمات حقيقي):
            # correction_note أعلاه يطلب صراحة "output signal=HOLD instead
            # of a broken plan" - لو استخدمنا self._entry_schema(is_backtest)
            # العادية بوضع الباك تيست، قائمة الخيارات المذكورة للموديل
            # ضمن الـschema instructions كانت ستقول "BUY أو SELL فقط" -
            # تناقض تعليمات مباشر بنفس الطلب (اطلب HOLD، لكن الخيارات
            # المتاحة لا تشمله). راجع docstring _entry_schema للتفصيل الكامل.
            retry_result = self._run_stage(
                "entry", retry_prompt, self._entry_schema(is_backtest, allow_hold=True)
            )
            retry_result = normalize_signal_dict(retry_result)
            if not retry_result or not isinstance(retry_result, dict):
                break
            final_result = retry_result
            issues = self._diagnose_trade_plan(final_result, symbol, timeframe, entry_ind, entry_data,
                                                daily_bias=daily_bias_val)

        if issues:
            # ⚠️ فشلت كل المحاولات - لا نُخرج صفقة فاسدة منطقياً. نحوّل
            # HOLD صراحة مع توثيق كامل (لا صمت، لا "أفضل ما توفر" مموّه).
            self.logger.error(
                f"❌ [Trade Plan Validation] فشلت كل محاولات التصحيح ({max_retries}) - "
                f"المشاكل ما زالت قائمة: {issues} - تحويل النتيجة لـHOLD إجبارياً."
            )
            final_result["signal"] = "HOLD"
            final_result["_trade_plan_forced_hold"] = True
            final_result["_trade_plan_unresolved_issues"] = issues
            final_result["narrative"] = (
                (final_result.get("narrative") or "")
                + f" [إجبار HOLD: فشل التحقق النهائي من سلامة خطة الصفقة بعد "
                f"{max_retries} محاولات تصحيح - المشاكل: {'; '.join(issues)}]"
            )

        final_result["_trade_plan_audit"] = {
            "had_issues_initially": attempt > 0 or bool(issues),
            "resolved": len(issues) == 0,
            "retries_used": attempt,
            "final_issues": issues,
        }

        # ── طبقة تقرير إضافية (غير حاجزة، معلوماتية فقط): نفس
        # VerificationLayer المستخدمة أصلاً بمسار brain_core.py القديم
        # (يفحص وجود narrative/archetype حقيقيين، أسعار مذكورة بالنص
        # الحر مطابقة للبيانات، اتساق R:R) - نسجّلها بالنتيجة للشفافية
        # الكاملة حتى لو لم تكن حاسمة لقرار HOLD/BUY/SELL (بعكس الفحوصات
        # أعلاه الحاسمة) - نفس فلسفة brain_core.py الأصلية بالضبط. ──
        if final_result.get("signal") in ("BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT") and entry_data:
            try:
                verification = self.verifier.verify(final_result, {"entry": entry_data})
                final_result["_verification_report"] = verification
                if verification.get("score_pct") is not None and verification["score_pct"] < 70:
                    self.logger.warning(
                        f"⚠️ [Verification Layer] Score منخفض: {verification['score_pct']}% "
                        f"- issues: {verification.get('issues')}"
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ Verification layer error: {e}")

        return final_result

    # ⚠️ regex لكشف منطقة سعرية محددة بالأرقام بنص حر (مثل
    # "72863-72914"، "72,863 - 72,914"، "at 2304-2345") - يستخدم لكشف
    # الـ"HOLD المتهرّب" (raja _detect_evasive_hold أدناه).
    _NUMERIC_ZONE_PATTERN = re.compile(
        r"\b\$?\d[\d,]{2,9}(?:\.\d+)?\s*[-–→]\s*\$?\d[\d,]{2,9}(?:\.\d+)?\b"
    )

    def _detect_evasive_hold(self, final_result, h4_result):
        """
        ⚠️ حل جذري جديد (يوليو 2026، بطلب صريح من المستخدم
        بعد اختبار حي فعلي أثبت نمطاً متكرراً على صفقتين متتاليتين
        مختلفتين - BTC #5 وETH #8): رغم التعليمات الصريحة بالبرومبت
        (SIGNAL TYPE قسم ب_build_entry_prompt) التي تقول صراحةً "لا تُخرج HOLD
        لمجرد أن السعر لم يصل بعد"، النموذج فعلياً استمر يرجع HOLD بينما
        يذكر بنفس الرد منطقة سعرية محددة تماماً ("4H Bearish OB at
        72863-73691... المنطقة المحددة للدخول هي ~72863-72914") - تناقض
        منطقي واضح: إذا كان عنده منطقة محددة بالأرقام، فهذا بالتعريف
        BUY_LIMIT/SELL_LIMIT لا HOLD.

        الكشف متحفظ عمداً (لا يرفض كل HOLD - فقط HOLD الذي يدّعي منطقة
        محددة فعلاً بالأرقام): يتطلب (أ) mmm_phase بمرحلة h4 ضمن (3, 4)
        فقط (لا 1/2/5 - تجميع/توزيع لا معنى لمنطقة دخول محددة)، (ب) وجود
        نمط رقمي "X-Y" واضح بنص h4_context_summary أو refined_zones_summary
        أو narrative/reasoning النتيجة النهائية.

        Returns: نص المنطقة المكتشفة (للاستخدام برسالة التصحيح) أو None
        إذا لا يوجد تناقض مكتشف.
        """
        if not isinstance(h4_result, dict):
            return None
        mmm_phase = h4_result.get("mmm_phase")
        if mmm_phase not in (3, 4):
            return None

        texts_to_scan = [
            h4_result.get("h4_context_summary", ""),
            h4_result.get("refined_zones_summary", ""),
            final_result.get("narrative", "") if isinstance(final_result, dict) else "",
            final_result.get("reasoning", "") if isinstance(final_result, dict) else "",
        ]
        for text in texts_to_scan:
            if not isinstance(text, str):
                continue
            m = self._NUMERIC_ZONE_PATTERN.search(text)
            if m:
                return m.group(0)
        return None

    def _check_gate2_daily(self, daily_result):
        """GATE 2 (12.3 بالدستور): لو الانحياز اليومي غير واضح أو ثقته منخفضة، توقف"""
        if not daily_result:
            return {"stop": True, "reason": "فشل تحليل المرحلة اليومية (لا رد صالح)"}
        direction = daily_result.get("direction", "UNCLEAR")
        confidence = daily_result.get("confidence", 0)
        if direction == "UNCLEAR":
            return {"stop": True, "reason": "Daily Bias غير واضح - لا انحياز موجّه اليوم (GATE 2)"}
        if isinstance(confidence, (int, float)) and confidence < 50:
            return {"stop": True, "reason": f"Daily Bias ثقته منخفضة جداً ({confidence}%) للتنفيذ (GATE 2)"}
        return {"stop": False}


    def _check_gate3_4h(self, h4_result):
        """
        GATE 3 (12.4 بالدستور): تعارض مع اليومي بلا مرحلة دخول واضحة، أو Phase 1/5.

        ⚠️ حل جذري (يوليو 2026، بطلب صريح من المستخدم):
        "لو لسا ما وصل للانتري السعر، لازم كمان يعطيك
        دخول وتارغت وستوب عشان حط أوردر، إذا وصل اوك تمام رواق،
        إذا ما وصل ماخسرت شي" - قبل هذا الإصلاح، الحالة
        "mmm_phase == 3 ولم يصل السعر للمنطقة بعد" كانت تُوقف
        التحليل بالكامل وتُرجع HOLD - رغم أن المنطقة معروفة ومحددة
        بالفعل (مجرد أن السعر لم يصلها بعد). الآن: هذه الحالة تُكمل
        التحليل لغاية مرحلة Entry (حيث يُقرر الموديل هل يصدر
        BUY_LIMIT/SELL_LIMIT عند تلك المنطقة المحددة)، بدل التوقف هنا
        وخسارة الفرصة بالكامل. الحالات الحقيقية التي تُوقف
        التحليل فعلاً (لا فرصة حقيقية موجودة أصلاً) تبقى: CONFLICT بلا
        مرحلة دخول واضحة، ومراحل MMM 1/5 (تجميع/توزيع نهائي - لا
        منطقة دخول محددة أصلاً ليُبنى أمر معلق عليها).
        """
        if not h4_result:
            return {"stop": True, "reason": "فشل تحليل مرحلة الـ4H (لا رد صالح)"}
        alignment = h4_result.get("daily_alignment", "CONFLICT")
        mmm_phase = h4_result.get("mmm_phase", 1)

        if alignment == "CONFLICT" and mmm_phase not in (2, 4):
            return {"stop": True, "reason": "4H يتعارض مع اليومي بدون مرحلة دخول واضحة (GATE 3)"}
        if mmm_phase in (1, 5):
            return {"stop": True, "reason": f"4H بمرحلة MMM {mmm_phase} (تجميع/توزيع) - لا فرصة دخول حالياً (GATE 3)"}
        return {"stop": False}

    def _check_gate4_15m(self, h15_result, is_backtest):
        """
        GATE 4 (12.5 بالدستور): 1H لم يؤكد جاهزية الدخول.

        ⚠️ حل جذري (يوليو 2026، بطلب صريح من المستخدم):
        قبل هذا الإصلاح، entry_ready=False بالوضع الحي كان
        يُوقف التحليل بالكامل ويُرجع HOLD فوراً - رغم أن المنطقة
        قد تكون محددة بدقة فقط تأكيد 1H اللحظي لم يتشكّل بعد.
        الآن (مثل GATE 3): نكمل التحليل دائماً (حي وباك تيست)،
        ويُفوّض لمرحلة Entry قرار التمييز بين: (أ) تنفيذ فوري
        BUY/SELL لو h1 أكّد entry_ready، (ب) أمر معلق BUY_LIMIT/SELL_LIMIT
        لو المنطقة معروفة بالHTF لكن 1H لم يؤكّد بعد، (ج) HOLD
        صريح لو لا يوجد إعداد حقيقي قابل للتحديد إطلاقاً.
        """
        if not h15_result:
            return {"stop": True, "reason": "فشل تحليل مرحلة الـ1H (لا رد صالح)"}
        return {"stop": False}

    def _build_hold_result(self, gate_name, reason, stage_log, is_backtest):
        result = {
            "signal": "HOLD" if not is_backtest else "HOLD",
            "bias": "NEUTRAL",
            "confidence": 0,
            "narrative": f"توقف التحليل عند {gate_name}: {reason}",
            "reasoning": reason,
            "archetype": "N/A (توقف مبكر بالـGate)",
            "bos_reconciliation": "N/A",
            "market_regime": "RANGING",
            "multi_pass_stage_log": stage_log,
            "analysis_method": "multi_pass_topdown_ict",
            "stopped_at_gate": gate_name,
            "stages_completed": len(stage_log),
        }
        # ⚠️ صدق منهجي: بوضع الباك تيست القديم كنا نُجبر BUY/SELL دائماً
        # (لا HOLD مسموح) لقياس دقة الاتجاه. لكن منهجية Top-Down الحقيقية
        # تعني أن "لا صفقة" هو أحياناً القرار الصحيح فعلياً (تماماً كما
        # يتوقف تاجر ICT حقيقي عند أي Gate). نُبقي الإشارة HOLD حتى في
        # الباك تيست هنا - إجبار قرار عكس منطق الـGates يُبطل الغرض من
        # اختبار المنهجية الهرمية نفسها.
        return result

    # ══════════════════════════════════════════════════════════
    #  Schemas لكل مرحلة (مبنية على مخرجات الدستور 12.2-12.6 بالضبط)
    # ══════════════════════════════════════════════════════════

    def _weekly_schema(self):
        return {
            "type": "OBJECT",
            "properties": {
                "trend": {"type": "STRING", "enum": ["BULLISH", "BEARISH", "RANGING"]},
                "strength": {"type": "STRING", "enum": ["STRONG", "MODERATE", "WEAK"]},
                "macro_narrative": {"type": "STRING", "description": "القصة الكبيرة بجملتين"},
                "macro_dol": {"type": "STRING", "description": "أين السيولة الكبرى المستهدفة"},
                "at_weekly_poi": {"type": "BOOLEAN"},
            },
            "required": ["trend", "strength", "macro_narrative", "macro_dol", "at_weekly_poi"],
        }

    def _daily_schema(self):
        return {
            "type": "OBJECT",
            "properties": {
                "direction": {"type": "STRING", "enum": ["BULLISH", "BEARISH", "UNCLEAR"]},
                "confidence": {"type": "INTEGER"},
                "weekly_alignment": {"type": "STRING", "enum": ["ALIGNED", "DIVERGENT", "BOTH_UNCLEAR"]},
                "last_event": {"type": "STRING", "description": "آخر BOS/CHoCH يومي (نوع + تقريباً متى)"},
                "dol_description": {"type": "STRING", "description": "هدف السيولة اليومي (Draw on Liquidity)"},
                "daily_bias_summary": {"type": "STRING", "description": "ملخص قصير يُمرَّر للمرحلة التالية"},
            },
            "required": ["direction", "confidence", "weekly_alignment", "daily_bias_summary"],
        }

    def _h4_schema(self):
        return {
            "type": "OBJECT",
            "properties": {
                "daily_alignment": {"type": "STRING", "enum": ["ALIGNED", "PULLBACK", "TRANSITION", "CONFLICT"]},
                "mmm_phase": {
                    "type": "INTEGER",
                    "description": "مرحلة Market Maker Model: 1=تجميع 2=دفع أولي 3=اندفاع 4=إعادة توزيع/تصحيح 5=توزيع نهائي",
                },
                "price_at_zone": {"type": "BOOLEAN", "description": "هل السعر عند منطقة OB/FVG مُنقّحة الآن؟"},
                "refined_zones_summary": {"type": "STRING"},
                "h4_context_summary": {"type": "STRING", "description": "ملخص قصير يُمرَّر للمرحلة التالية"},
            },
            "required": ["daily_alignment", "mmm_phase", "price_at_zone", "h4_context_summary"],
        }

    @staticmethod
    def _compute_last_candle_fact(data):
        """
        ⚠️ حل جذري جوهري (يوليو 2026، بطلب صريح ومباشر من المستخدم:
        "الموديل ما يقرب أبداً على تحليل البيانات الخام والأرقام من
        عنده - لازم يوصله كلشي جاهز وهو عليه يحلل ويفكر"): قبل هذا
        الإصلاح، `last_candle_report` (OHLC + لون آخر شمعة) كان الحقل
        الوحيد المتبقي بكل الـschemas الذي يُطلب من الموديل "قراءته
        ونسخه" من جدول الشموع النصي - وهذا بالضبط أكثر مصدر هلوسة
        متكرر موثّق طوال هذه الجلسة (`LAST_CANDLE_HALLUCINATION`: لون
        معكوس، قيم مختلفة عن الفعلي بنسب تتجاوز الهامش المسموح) رغم
        أنه "مهمة ميكانيكية بحتة" بالضبط مثل تحديد لون الشمعة (OHLC
        خام، `close>open` لتحديد اللون) - لا يوجد أي تفسير أو فهم
        مطلوب هنا إطلاقاً، فلا داعي لتركها لقراءة/نسخ الموديل بتاتاً.

        الحل: يُحسب هذا الحقل بالكامل هنا رياضياً بحتاً (بايثون خام، لا
        AI) ويُحقن كـ"حقيقة جاهزة لا تحتاج قراءة" - أُزيل من كل الـ
        schemas (h15, entry) بالكامل، فلم يعد الموديل يُطلب منه إخراجه
        إطلاقاً - يستحيل أن "يهلوس" حقلاً لم يعد مطلوباً منه كتابته.

        Returns dict: {"open","high","low","close","color"} أو None
        لو البيانات غير كافية.
        """
        if not data or not data.get("closes"):
            return None
        try:
            o, h, l, c = data["opens"][-1], data["highs"][-1], data["lows"][-1], data["closes"][-1]
            return {
                "open": o, "high": h, "low": l, "close": c,
                "color": "BULLISH" if c > o else "BEARISH",
            }
        except (IndexError, KeyError, TypeError):
            return None

    def _h15_schema(self):
        return {
            "type": "OBJECT",
            "properties": {
                "entry_ready": {"type": "BOOLEAN", "description": "هل تشكّل تحول هيكلي (MSS/CHoCH) عند منطقة الـHTF؟"},
                "structural_shift_direction": {"type": "STRING", "enum": ["UP", "DOWN", "NONE"]},
                "tactical_summary": {"type": "STRING", "description": "ملخص قصير يُمرَّر لمرحلة التنفيذ"},
            },
            "required": ["entry_ready", "structural_shift_direction", "tactical_summary"],
        }

    def _deterministic_verdict_schema(self):
        """
        ⚠️ حل جذري للهلوسة من الجذر (يوليو 2026، طلب صريح من المستخدم
        بعد تحقيق صفقة #10: "بدنا نحل مشكلة هلوسة الموديل من الجذر مش
        نستناه يخبص بعدين نصلحه... منحل كل المشكلة هيك ومنصير أسرع
        ومنخفف طلبات").

        ⚠️ الفرق الجذري عن _entry_schema العادية: تلك تطلب من الموديل
        "اخترع entry/stop_loss/tp بنفسك" (المصدر المباشر لكل هلوسة أرقام
        موثّقة بهذا المشروع) - هذه الـschema **لا تحتوي حقول entry/
        stop_loss/tp/tp1/tp2 إطلاقاً** لأنها غير مطلوبة: تلك الأرقام
        **موجودة مسبقاً وجاهزة 100%** من checklist_result الحتمي (نفس
        الأرقام المحقونة بالبرومبت). دور الموديل الوحيد هنا: قرار
        ثنائي محصور - يقبل الخطة الجاهزة كما هي، أو يرفضها بدليل محدد
        من enum مقيَّد (لا نص حر يمكن الالتفاف فيه لفظياً حول شرط حقيقي
        - نفس المشكلة الموثّقة بصفقة #10: الموديل قال "لسا ما صار Judas
        Swing" بجملة عامة بينما SWEEP_CONFIRMED_GENUINE=True كانت مؤكدة
        رياضياً - جملة عامة كهذه لا يمكن التحقق منها برمجياً، بينما
        اختيار من enum + رقم شمعة محدد يمكن التحقق منه فوراً بلا نداء
        API إضافي).
        """
        return {
            "type": "OBJECT",
            "properties": {
                "verdict": {
                    "type": "STRING",
                    "enum": ["ACCEPT_PLAN", "REJECT_WITH_EVIDENCE"],
                    "description": (
                        "ACCEPT_PLAN: الخطة الميكانيكية الجاهزة (checklist) صحيحة "
                        "ولا يوجد أي دليل هيكلي حقيقي يناقضها - نفّذها كما هي. "
                        "REJECT_WITH_EVIDENCE: فقط لو وجدت دليلاً هيكلياً حقيقياً "
                        "موثّقاً رياضياً (لا انطباعاً عاماً) يبطل هذه الخطة تحديداً - "
                        "يجب ملء rejection_evidence_type وrejection_candle_index بدقة."
                    ),
                },
                "rejection_evidence_type": {
                    "type": "STRING",
                    "enum": ["NONE", "OPPOSING_CHOCH_OR_MSS", "OPPOSING_BOS",
                             "DAILY_BIAS_CONTRADICTION", "SESSION_TIMING_INVALID",
                             "STRUCTURE_INVALIDATED_BY_NEWER_CANDLE"],
                    "description": (
                        "إلزامي عند REJECT_WITH_EVIDENCE - أي نوع دليل هيكلي حقيقي "
                        "يبطل الخطة؟ 'NONE' فقط عند ACCEPT_PLAN. يجب أن يكون هذا "
                        "حدثاً هيكلياً حقيقياً موثّقاً (CHoCH/BOS مضاد) لا رأياً عاماً."
                    ),
                },
                "rejection_candle_index": {
                    "type": "INTEGER",
                    "description": (
                        "إلزامي عند REJECT_WITH_EVIDENCE - رقم مؤشر الشمعة "
                        "(index_from_end، سالب، الأقرب للصفر = الأحدث) التي وقع "
                        "عندها الدليل المضاد. يجب أن يكون أحدث زمنياً (رقم أكبر أو "
                        "يساوي - أقرب للصفر) من evidence_anchor_idx المحقون أعلاه - "
                        "وإلا الاعتراض غير صالح (دليل أقدم من الخطة نفسها لا يبطلها)."
                    ),
                },
                "reasoning": {"type": "STRING"},
                "confidence": {"type": "INTEGER"},
            },
            "required": ["verdict", "rejection_evidence_type", "reasoning", "confidence"],
        }

    def _verify_deterministic_rejection(self, verdict_result, checklist_result, entry_data,
                                         daily_bias_for_checklist=None):
        """
        ⚠️ التحقق الفعلي (بايثون بحت، صفر AI) من صحة أي REJECT_WITH_
        EVIDENCE - هذا هو "القفل" الذي يمنع الالتفاف اللفظي فعلياً (لا
        فقط طلب نصي بالبرومبت أن يستشهد الموديل - بل تحقق برمجي حقيقي
        بعد الرد يرفض أي اعتراض غير موثّق رياضياً).

        ⚠️ إصلاح جذري ثانٍ (يوليو 2026، اكتُشف بتحقيق حي مباشر - صفقة
        رابحة موثّقة [GENERIC_STRUCTURAL_FALLBACK، entry=1643.735] رفضها
        الموديل مستنداً لأربعة "كسور هيكلية معاكسة" تبيّن عند الفحص
        اليدوي أنها **جميعها كسور على سوينغات Minor غير مهمة إطلاقاً**
        (لا واحد منها MAJOR/MODERATE، ولا حتى مؤكَّد بسلسلة سحب+ديسبليسمنت
        الكاملة) - فبُنيت خطة بديلة (MODEL_A_OTE_OB) خسرت فعلياً. النسخة
        الأولى من هذا التحقق كانت تتحقق فقط من "هل الكسر صار رياضياً؟"
        بلا أي فحص لـ"أهمية" الكسر - نفس الفجوة بالضبط التي حلّها
        classify_break_reversal_authenticity() بمكان آخر بالمشروع (تمييز
        Inducement عن انعكاس حقيقي) لكنها لم تُستخدَم هنا إطلاقاً.

        اكتشاف إضافي أخطر بنفس التحقيق: الـenum الخاص بنوع الدليل يحوي
        خمسة أنواع (OPPOSING_CHOCH_OR_MSS, OPPOSING_BOS,
        DAILY_BIAS_CONTRADICTION, SESSION_TIMING_INVALID,
        STRUCTURE_INVALIDATED_BY_NEWER_CANDLE) لكن الكود القديم كان
        يتحقق رياضياً من نوعين فقط (الأولين) - الثلاثة الباقية كانت
        **تُقبل تلقائياً بلا أي تحقق رياضي إطلاقاً** (تصل لسطر
        "return True" النهائي مباشرة) رغم أن نص البرومبت يَعِد صراحة:
        "will be mechanically verified against the actual data and
        rejected automatically if unsupported" - وعد لم يكن يتحقق فعلياً
        لثلاثة من خمسة أنواع أدلة. هذا إصلاح شامل يعالج الفجوتين معاً:

        الفحوصات الآن (لكل الأنواع الخمسة، لا استثناء):
          1. rejection_candle_index يجب أن يكون أحدث فعلياً (>=) من
             evidence_anchor_idx المحقون بالخطة نفسها.
          2. OPPOSING_CHOCH_OR_MSS / OPPOSING_BOS /
             STRUCTURE_INVALIDATED_BY_NEWER_CANDLE: يجب أن يكون الكسر
             (أ) موجوداً فعلياً رياضياً عبر detect_mss()، و(ب) **مهماً
             فعلياً** - إما كسر لسوينغ MAJOR/MODERATE حقيقي (عبر
             AuthenticityEngine.detect_significant_swings)، أو على
             الأقل مؤكَّد بالكامل (سحب سيولة حقيقي + ديسبليسمنت معاً -
             نفس معيار CONFIRMED_REVERSAL_HIGH_CONVICTION). كسر لسوينغ
             Minor بلا هذا التأكيد الكامل = مرفوض تلقائياً (نفس معيار
             "لا تغيّر تقييمك الهيكلي" لقسم 3.5/4.6 بالدستور).
          3. DAILY_BIAS_CONTRADICTION: لا توجد أداة تحقق رياضي مباشرة
             متاحة بهذا النطاق (تغيير الانحياز اليومي فعلياً يتطلب
             إعادة تحليل مرحلة Daily الكاملة، لا يمكن التحقق منه من
             بيانات فريم التنفيذ وحدها) - **يُرفض تلقائياً** بدل قبوله
             بلا دليل (نفس فلسفة "لا نقبل ادعاءً غير موثَّق" المطبَّقة
             أصلاً على بقية الأنواع - لا نمنح استثناءً لهذا النوع فقط).
          4. SESSION_TIMING_INVALID: نفس المنطق - لا تحقق رياضي مباشر
             ممكن هنا بمعزل عن استدعاء ict_sessions.classify_session()
             الذي يحتاج سياقاً زمنياً كاملاً غير متوفر بهذه الدالة -
             **يُرفض تلقائياً** حتى تُبنى أداة تحقق مخصصة له مستقبلاً.

        Returns: (is_valid: bool, reason: str)
        """
        if verdict_result.get("verdict") != "REJECT_WITH_EVIDENCE":
            return True, "ACCEPT_PLAN - لا حاجة للتحقق"

        chosen = checklist_result.get("chosen_model") or {}
        plan = chosen.get("plan") or {}
        anchor_idx = plan.get("evidence_anchor_idx")
        claimed_idx = verdict_result.get("rejection_candle_index")
        evidence_type = verdict_result.get("rejection_evidence_type")

        if anchor_idx is None or claimed_idx is None:
            return False, "بيانات المرساة أو المؤشر المزعوم غير مكتملة - الاعتراض مرفوض تلقائياً"

        # الفهرسة index_from_end سالبة (الأقرب للصفر=الأحدث) - يجب أن
        # يكون claimed_idx أحدث فعلياً (>=) من anchor_idx
        if not (claimed_idx >= anchor_idx):
            return False, (
                f"المؤشر المزعوم ({claimed_idx}) أقدم من نقطة تأسيس الخطة "
                f"({anchor_idx}) - دليل أقدم من الخطة نفسها لا يبطلها منطقياً. "
                f"الاعتراض مرفوض تلقائياً."
            )

        if evidence_type in ("OPPOSING_CHOCH_OR_MSS", "OPPOSING_BOS",
                              "STRUCTURE_INVALIDATED_BY_NEWER_CANDLE") and entry_data:
            try:
                from ict_math_engine import detect_mss, classify_break_reversal_authenticity
                from authenticity_engine import AuthenticityEngine

                mss = detect_mss(entry_data, swing_window=2)
                plan_direction = plan.get("direction", "")
                is_long_plan = "BUY" in plan_direction
                opposing_direction = "BEARISH" if is_long_plan else "BULLISH"
                matching = [
                    b for b in mss["breaks_found"]
                    if b["direction"] == opposing_direction
                    and b["break_candle_index_from_end"] >= anchor_idx
                    and abs(b["break_candle_index_from_end"] - claimed_idx) <= 2
                ]
                if not matching:
                    return False, (
                        f"لا يوجد كسر هيكلي حقيقي معاكس ({opposing_direction}) موثّق "
                        f"رياضياً قرب المؤشر المزعوم {claimed_idx} - الاعتراض غير "
                        f"مدعوم بدليل فعلي، مرفوض تلقائياً."
                    )

                # ⚠️ الفحص الإضافي الحاسم (الإصلاح الجذري الأساسي هنا):
                # هل الكسر المُستشهَد به فعلاً "مهم" بما يكفي ليُبطل خطة
                # حتمية جاهزة؟ نتحقق من تصنيف السوينغ المكسور (MAJOR/
                # MODERATE/MINOR) عبر نفس أداة AuthenticityEngine
                # المستخدمة بمكان آخر بالمشروع لهذا الغرض بالضبط.
                candidate_break = matching[0]
                broken_level = candidate_break.get("broken_level")
                swing_tier = None
                try:
                    ae = AuthenticityEngine()
                    sig = ae.detect_significant_swings(entry_data, swing_window=2, lookback_candles=150)
                    # ⚠️ إصلاح جذري (اكتُشف بunit test مباشر): كسر
                    # BULLISH يخترق قمة (high) لا قاعاً - كان هذا
                    # معكوساً بالخطأ (all_lows_tiered لـBULLISH بدل
                    # all_highs_tiered)، ما يعني أن أي كسر MAJOR/
                    # MODERATE حقيقي كان يفشل إيجاد تصنيفه الصحيح دائماً
                    # (يبحث بالقائمة الخطأ) ويُرفض كـ"غير مصنَّف" زوراً.
                    tiered_list = sig.get("all_highs_tiered", []) if opposing_direction == "BULLISH" else sig.get("all_lows_tiered", [])
                    for s in tiered_list:
                        if broken_level is not None and abs(s["price"] - broken_level) < max(abs(broken_level) * 0.0015, 1e-6):
                            swing_tier = s["tier"]
                            break
                except Exception:
                    swing_tier = None

                authenticity = classify_break_reversal_authenticity(candidate_break, tier=swing_tier)
                verdict_class = authenticity.get("verdict")

                if verdict_class not in ("MAJOR_STRUCTURAL_BREAK", "CONFIRMED_REVERSAL_HIGH_CONVICTION"):
                    return False, (
                        f"الكسر الهيكلي المُستشهَد به (مستوى {broken_level}, tier={swing_tier or 'MINOR/غير مصنَّف'}) "
                        f"مصنَّف كـ'{verdict_class}' - ليس كسراً لسوينغ MAJOR/MODERATE مهم، ولا مؤكَّداً بالكامل "
                        f"(سحب سيولة حقيقي + ديسبليسمنت معاً). كسر بهذا المستوى من الضعف لا يكفي لإبطال خطة "
                        f"حتمية جاهزة رياضياً (نفس معيار قسم 3.5/4.6 بالدستور: 'لا تغيّر تقييمك الهيكلي' لكسر "
                        f"Minor غير مؤكَّد). الاعتراض مرفوض تلقائياً."
                    )
            except Exception as e:
                return False, f"تعذّر التحقق الرياضي من الدليل المزعوم ({e}) - الاعتراض مرفوض تلقائياً (لا نقبل ادعاءً غير موثَّق)"

        elif evidence_type == "DAILY_BIAS_CONTRADICTION":
            # ⚠️ لا توجد أداة تحقق رياضي مباشرة متاحة بهذا النطاق (تغيير
            # الانحياز اليومي الفعلي يتطلب إعادة تحليل مرحلة Daily
            # الكاملة بفريمها الخاص، غير متوفرة من entry_data وحدها) -
            # نرفض تلقائياً بدل القبول الأعمى (كان هذا الفرع يصل لـ
            # "return True" النهائي بلا أي تحقق - فجوة أمان حقيقية).
            return False, (
                "DAILY_BIAS_CONTRADICTION غير قابل للتحقق الرياضي المباشر من بيانات فريم "
                "التنفيذ وحدها (يتطلب إعادة تحليل مرحلة Daily الكاملة) - الاعتراض مرفوض "
                "تلقائياً حتى تتوفر أداة تحقق مخصصة (لا نقبل ادعاءً غير موثَّق)."
            )

        elif evidence_type == "SESSION_TIMING_INVALID":
            # نفس المنطق - لا تحقق رياضي مباشر ممكن بمعزل عن سياق زمني
            # كامل غير متوفر هنا.
            return False, (
                "SESSION_TIMING_INVALID غير قابل للتحقق الرياضي المباشر بهذه الدالة - "
                "الاعتراض مرفوض تلقائياً حتى تتوفر أداة تحقق مخصصة (لا نقبل ادعاءً غير موثَّق)."
            )

        return True, f"اعتراض موثّق فعلياً: {evidence_type} عند idx {claimed_idx}"

    def _entry_schema(self, is_backtest, allow_hold=False):
        """
        ⚠️ بارامتر allow_hold جديد (يوليو 2026، إصلاح تناقض تعليمات
        حقيقي مُكتشف بتدقيق شامل): بوضع الباك تيست العادي،
        signal_enum = ["BUY","SELL"] فقط (يفرض قراراً اتجاهياً - هذا
        صحيح ومقصود للتحليل الأول). لكن عند إعادة محاولة التصحيح
        النهائية (_verify_and_finalize_trade_plan) بعد فشل كل محاولات
        إصلاح خطة صفقة فاسدة، نص البرومبت يطلب صراحة "output signal=
        HOLD instead of a broken plan" - بينما الـschema (حتى لو ليست
        enforcement صارماً حقيقياً عبر Nemotron/OpenRouter، إنما تعليمات
        نصية للموديل - راجع NemotronClient._gemini_schema_to_instructions)
        كانت تُخبر الموديل صراحة أن الخيارات المتاحة "BUY أو SELL فقط" -
        تناقض تعليمات مباشر بنفس الطلب. الحل: عند استدعاء هذه الدالة من
        مسار إعادة محاولة التصحيح تحديداً، allow_hold=True يضيف HOLD
        لقائمة الخيارات المذكورة للموديل، ويُسقط شرط "entry/stop_loss/
        tp required" (منطقياً - HOLD لا يحتاج أرقام دخول وهمية) - هذا
        لا يُغيّر أي شيء بالتحليل الأول العادي (allow_hold=False افتراضياً،
        يحافظ 100% على السلوك القديم لأول محاولة).
        """
        # BUY_LIMIT/SELL_LIMIT مسموحان فقط بعد اكتمال تسلسل النموذج
        # وتكوّن منطقة حقيقية؛ اختلافهما عن BUY/SELL أن السعر لم يعد
        # للمنطقة بعد. أي displacement/FVG/LTF/timing ما زال PENDING
        # يعني HOLD + WAIT_CONFIRMATION، لا pre-positioning.
        signal_enum = (
            ["BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "HOLD"]
            if (allow_hold or not is_backtest)
            else ["BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT"]
        )
        require_trade_numbers = is_backtest and not allow_hold
        return {
            "type": "OBJECT",
            "properties": {
                "cross_reference_check": {
                    "type": "STRING",
                    "description": (
                        "إلزامي: قاطع الآن كل المراحل الأربع السابقة (Weekly/"
                        "Daily/4H/1H) صراحة - هل تتفق كلها على نفس الاتجاه؟ "
                        "أي مرحلة تتعارض مع الباقي؟ كيف حُسم التعارض إن وُجد؟"
                    ),
                },
                "structural_derivation": {
                    "type": "STRING",
                    "description": (
                        "إلزامي إذا وُجدت CAUSAL DERIVATION CHAIN بالأدلة أعلاه: "
                        "اذكر صراحة اسم/موقع شمعة الـOrder Block المحددة "
                        "(index_from_end) التي أنتجت آخر BOS، وهل خلقت FVG، "
                        "وهل هذه السلسلة مرتبطة فعلياً بآخر سحب سيولة (chain_coherent) "
                        "أو منفصلة عنه - هذا استنباط سببي مطلوب صراحة، ليس سرد "
                        "حقائق منفصلة (لا تكتفِ بذكر 'يوجد BOS' و'يوجد OB' كخبرين "
                        "منفصلين - اربطهما: 'هذا الـOB بالتحديد أنتج هذا BOS')."
                    ),
                },
                "narrative": {"type": "STRING"},
                "archetype": {"type": "STRING"},
                "bos_reconciliation": {"type": "STRING"},
                "bias": {"type": "STRING", "enum": ["BULLISH", "BEARISH", "NEUTRAL"]},
                "signal": {"type": "STRING", "enum": signal_enum},
                "entry_model": {
                    "type": "STRING",
                    "enum": ["MODEL_A_OTE_OB", "MODEL_B_SWEEP_FVG", "MODEL_C_BOS_PULLBACK",
                             "MODEL_D_AMD_SESSION", "MODEL_E_SILVER_BULLET", "MODEL_F_CHOCH_REVERSAL", "NONE"],
                    "description": (
                        "إلزامي عند BUY/SELL/BUY_LIMIT/SELL_LIMIT: أي نموذج دخول من الستة المعرّفة بقسم "
                        "[ENTRY_MODELS] بالدستور طابق هذا الإعداد بالضبط؟ 'NONE' فقط لو "
                        "signal=HOLD. يجب أن يطابق الشروط الفعلية المذكورة بالدستور لهذا "
                        "الموديل تحديداً (لا تختر موديلاً لم تتحقق شروطه فعلياً بالبيانات)."
                    ),
                },
                "entry": {"type": "NUMBER"},
                "stop_loss": {"type": "NUMBER"},
                "tp": {
                    "type": "NUMBER",
                    "description": (
                        "TP1 provisional: أقرب مستوى سيولة حقيقي غير مسحوب باتجاه الصفقة. "
                        "لا تمدده لتحقيق R:R ثابتة. سيحسب post-processor هدف TP2 منفصلاً "
                        "عند وجود تأكيد كافٍ، وإلا يعلن OPEN_TRAILING."
                    ),
                },
                "confidence": {"type": "INTEGER"},
                "rr": {"type": "STRING"},
                "reasoning": {"type": "STRING"},
                "market_regime": {
                    "type": "STRING",
                    "enum": ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE"],
                },
                "confluence_factors": {"type": "ARRAY", "items": {"type": "STRING"}},
                "risks": {"type": "ARRAY", "items": {"type": "STRING"}},
                "invalidation": {"type": "STRING"},
            },
            "required": [
                "cross_reference_check", "narrative",
                "archetype", "bias", "signal", "confidence", "reasoning",
                "market_regime", "bos_reconciliation", "entry_model",
            ] + (
                # ⚠️ إصلاح باگ حرج حقيقي مُكتشف بالاختبار الفعلي (2026-07-03):
                # كان "stop_loss" و"entry" و"tp" موجودين بالـschema لكن
                # غير مدرَجين بـ"required" - رد فعلي موثّق كامل: النموذج
                # أعطى signal=BUY بثقة 83% مع stop_loss=None (بلا ستوب
                # لوس إطلاقاً!) بينما ذكر مستوى الإبطال بوضوح تام بحقل
                # "invalidation" النصي («body close below 2920.00»). هذا
                # خطر حقيقي وخطير (بوت تداول بلا SL = كارثة مالية محتملة)
                # وليس افتراضاً نظرياً - رأيناه فعلياً. الإصلاح: نفرض هذه
                # الحقول الثلاثة "required" فقط عندما تكون BUY/SELL ممكنة
                # فعلياً وذات معنى (وضع الباك تيست يفرض BUY/SELL دائماً -
                # HOLD معطّل هناك أصلاً) - لا نفرضها بالوضع الحي لأن HOLD
                # هناك سيناريو صحيح شائع لا يحتاج أرقام دخول/ستوب وهمية.
                ["entry", "stop_loss", "tp"] if require_trade_numbers else []
            ),
        }

    # ══════════════════════════════════════════════════════════
    #  بناء برومبت كل مرحلة (فريم حقيقي مختلف لكل مرحلة)
    # ══════════════════════════════════════════════════════════

    def _candles_block(self, data, n=40):
        if not data:
            return "(بيانات هذا الفريم غير متاحة)"
        return self.brain._format_candles(data, n)

    def _lesson_block(self, stage_name):
        """
        ⚠️ نظام "التعلّم من الدرس لا حفظ الصفقة" (يوليو 2026، بطلب
        صريح من المستخدم بعد نقاش حول الفرق الجوهري بين حفظ صفقة
        بعينها (غش) واستيعاب نمط تحليلي عام (فهم حقيقي)). راجع
        lesson_learning.py للتفاصيل الكاملة والحراسة البرمجية ضد
        تسرّب أرقام/تواريخ محددة لأي درس مخزَّن.

        يحقن فقط أحدث دروس ذات صلة بهذه المرحلة تحديداً (لا كل الدروس
        دفعة واحدة) - مثال: درس عن EARLY_ENTRY يصل لمرحلة entry/h1،
        لا لمرحلة Weekly التي لا علاقة لها بتوقيت الدخول.
        """
        try:
            return lesson_learning.get_relevant_lessons(stage=stage_name)
        except Exception as e:
            self.logger.warning(f"⚠️ Lesson block failed (non-fatal): {e}")
            return ""

    @staticmethod
    def _format_swing_points_as_prose(points, kind_label):
        """
        \u26a0\ufe0f \u0625\u0635\u0644\u0627\u062d \u062c\u0630\u0631\u064a (\u064a\u0648\u0644\u064a\u0648 2026\u060c \u0627\u0643\u062a\u064f\u0634\u0641 \u0628\u0639\u062f \u0641\u0634\u0644 \u062d\u0642\u064a\u0642\u064a \u0643\u0627\u0645\u0644 \u0628\u0645\u0631\u062d\u0644\u0629
        Weekly \u0623\u062b\u0646\u0627\u0621 \u0627\u062e\u062a\u0628\u0627\u0631 \u062d\u064a): \u0643\u0627\u0646\u062a \u0647\u0630\u0647 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u062a\u064f\u062d\u0642\u064e\u0646 \u0628\u0627\u0644\u0628\u0631\u0648\u0645\u0628\u062a
        \u0639\u0628\u0631 f"{points}" \u0645\u0628\u0627\u0634\u0631\u0629 - \u0623\u064a \u0628\u0635\u064a\u063a\u0629 Python repr \u0627\u0644\u062e\u0627\u0645 \u0644\u0642\u0627\u0626\u0645\u0629
        \u0627\u0644\u0642\u0648\u0627\u0645\u064a\u0633 (\u0645\u062b\u0627\u0644 \u062d\u0642\u064a\u0642\u064a \u0641\u0639\u0644\u064a: "[{'index_from_end': -13, 'price':
        60000.0}]"\u060c \u0628\u0623\u0642\u0648\u0627\u0633 \u0645\u0641\u0631\u062f\u0629 \u0648\u0628\u0646\u064a\u0629 \u0623\u0642\u0631\u0628 \u0644\u0640JSON
        \u0644\u0643\u0646 \u0644\u064a\u0633\u062a JSON \u0635\u0627\u0644\u062d\u0627\u064b). \u062a\u062d\u0642\u0642 \u0641\u0639\u0644\u064a \u0642\u0627\u0637\u0639: \u0646\u0641\u0633 \u0647\u0630\u0627 \u0627\u0644\u0634\u0643\u0644 \u0628\u0627\u0644\u0636\u0628\u0637 "\u062a\u0633\u0631\u0651\u0628" \u0644\u0646\u0627\u062a\u062c \u0627\u0644\u0645\u0648\u062f\u064a\u0644 \u0627\u0644\u0641\u0627\u0633\u062f \u0628\u0645\u0631\u062d\u0644\u0629
        Weekly - \u0627\u0644\u0645\u0648\u062f\u064a\u0644 \u062e\u0644\u0637 \u0628\u064a\u0646 "\u0645\u062b\u0627\u0644 \u0628\u064a\u0627\u0646\u0627\u062a \u064a\u0634\u0628\u0647 JSON \u0631\u0622\u0647 \u0628\u0627\u0644\u0628\u0631\u0648\u0645\u0628\u062a"
        \u0648"\u0627\u0644\u0640schema \u0627\u0644\u0641\u0639\u0644\u064a \u0627\u0644\u0645\u0637\u0644\u0648\u0628 \u0645\u0646\u0647 \u0625\u062e\u0631\u0627\u062c\u0647"\u060c \u0641\u0623\u0646\u062a\u062c \u0645\u0641\u062a\u0627\u062d\u0627\u064b \u0645\u062e\u062a\u0644\u064e\u0642\u0627\u064b "trend_of_end"
        (\u062a\u062d\u0631\u064a\u0641 \u0648\u0627\u0636\u062d \u0644\u0640"index_from_end" \u0627\u0644\u0645\u062d\u0642\u0648\u0646) \u0628\u062f\u0644 \u0627\u0644\u062d\u0642\u0648\u0644 \u0627\u0644\u062d\u0642\u064a\u0642\u064a\u0629
        \u0627\u0644\u0645\u0637\u0644\u0648\u0628\u0629 (trend, strength...)\u060c \u0645\u0645\u0627 \u0643\u0633\u0631 \u0627\u0644\u0640JSON \u0628\u0627\u0644\u0643\u0627\u0645\u0644 \u0644\u0645\u0631\u062d\u0644\u0629 \u0644\u0627 \u062a\u0645\u0644\u0643
        \u0623\u064a Gate \u064a\u0648\u0642\u0641\u0647\u0627 \u0639\u0646\u062f \u0627\u0644\u0641\u0634\u0644.

        \u0627\u0644\u062d\u0644 \u0627\u0644\u062c\u0630\u0631\u064a: \u0623\u064a \u0628\u064a\u0627\u0646\u0627\u062a \u062a\u064f\u062d\u0642\u064e\u0646 \u0643"\u062f\u0644\u064a\u0644 \u0645\u0631\u062c\u0639\u064a" \u0628\u0627\u0644\u0628\u0631\u0648\u0645\u0628\u062a \u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 \u0628\u0635\u064a\u063a\u0629 \u0646\u0635
        \u0639\u0627\u062f\u064a \u0648\u0627\u0636\u062d \u062a\u0645\u0627\u0645\u0627\u064b (prose) \u0644\u0627 \u062a\u0634\u0628\u0647 \u0623\u064a \u0628\u0646\u064a\u0629
        JSON/Python \u0639\u0644\u0649 \u0627\u0644\u0625\u0637\u0644\u0627\u0642 - \u064a\u0632\u064a\u0644 \u0645\u0635\u062f\u0631 \u0627\u0644\u0627\u0644\u062a\u0628\u0627\u0633 \u0627\u0644\u0628\u0635\u0631\u064a \u0645\u0646 \u062c\u0630\u0648\u0631\u0647\u060c
        \u0644\u0627 \u064a\u0643\u062a\u0641\u064a \u0628\u0645\u0639\u0627\u0644\u062c\u0629 \u0639\u0631\u064e\u0636 \u0648\u0627\u062d\u062f \u0634\u0648\u0647\u062f \u0635\u062f\u0641\u0629.
        """
        if not points:
            return "none detected"
        parts = []
        for p in points:
            idx = p.get("index_from_end")
            price = p.get("price")
            parts.append(f"{kind_label} at candle index {idx} (price {price})")
        return "; ".join(parts)

    def _authenticity_block(self, data):
        """
        يبني نص جاهز بأدلة رقمية مسبقة (AuthenticityEngine) لنفس فريم
        هذه المرحلة تحديداً - يحقن "القمم/القيعان المهمة فعلياً" (بعد
        استبعاد النتوءات الصغيرة) وتصنيف آخر sweep رياضياً، بدل ترك
        الـAI يخترعها من الصفر بتخمين لغوي بحت. ⚠️ إصلاح فجوة حقيقية:
        هذه الحسابات (detect_significant_swings, detect_most_recent_sweep)
        كانت موجودة بالكود منذ فترة كأدوات لكن لم تُستدعَ أبداً بأي
        مسار تحليل فعلي قبل هذا التعديل.
        """
        if not data or "closes" not in data:
            return ""
        try:
            report = self.authenticity.build_authenticity_report(data)
        except Exception as e:
            self.logger.warning(f"⚠️ Authenticity block failed: {e}")
            return ""
        sig = report.get("significant_swings", {})
        sweep = report.get("most_recent_liquidity_sweep", {})
        # ⚠️ راجع _format_swing_points_as_prose أعلاه: لا نحقن القوائم
        # الخام (Python repr) مباشرة بالبرومبت بعد الآن - نص عادي فقط.
        highs_text = self._format_swing_points_as_prose(
            sig.get("significant_highs", []), "swing high"
        )
        lows_text = self._format_swing_points_as_prose(
            sig.get("significant_lows", []), "swing low"
        )
        lines = [
            "\n── PRE-COMPUTED MATH EVIDENCE (independent of your reading - "
            "verify against it, don't contradict it without citing specific "
            "numbers; this is plain reference text, NOT a JSON example to "
            "copy the shape of - your actual output format is defined only "
            "in the OUTPUT FORMAT section below) ──",
            (
                f"Significant swing highs (prominent vs neighbors, minor local "
                f"bumps already filtered out - {sig.get('minor_swings_filtered_count', 0)} "
                f"minor swings excluded): {highs_text}"
            ),
            f"Significant swing lows: {lows_text}",
            (
                "⚠️ Any swing high/low you cite as structurally significant "
                "should generally match one of these prominent levels above - "
                "if you cite a different local bump instead, explain why it "
                "matters despite a larger nearby swing overshadowing it."
            ),
        ]

        # ⚠️ حل جذري (يوليو 2026، بطلب صريح من المستخدم): بدل ترك
        # النموذج يشتق تصنيف HH/HL/LH/LL بنفسه من الصفر (مصدر أخطاء
        # موثّق يتطلب إعادة محاولة كاملة كل مرة - راجع
        # audit_structure_labels و_verify_and_retry_structure_math)،
        # نحقن هنا التصنيف الكامل محسوباً رياضياً بحتاً مسبقاً (100%
        # مضمون صحته حسابياً، لا احتمالياً). مهمة النموذج الآن: تحقق
        # من هذا التصنيف الجاهز وابنِ تفسيرك/سردك عليه، لا تخترعه من
        # جديد - ولو رأيت نقطة مختلفة أهم فعلياً، اذكرها صراحة مع رقم
        # وتبرير، لا تستبدل التصنيف الجاهز بصمت.
        seq = report.get("structure_sequence", {})
        seq_narrative = seq.get("sequence_narrative", "") if isinstance(seq, dict) else ""
        if seq_narrative:
            lines.append(
                "\n── STRUCTURE SEQUENCE (HH/HL/LH/LL) - MATHEMATICALLY "
                "PRE-LABELED (not AI judgment - each label is a direct "
                "numeric comparison against the immediately preceding swing "
                "of the same type; use these labels directly in your "
                "narrative/reasoning instead of re-deriving them yourself; "
                "if you believe a different point deserves a different "
                "label, you MUST cite the specific reference swing price "
                "you are comparing against explicitly) ──"
            )
            lines.append(seq_narrative)

        # ⚠️ حل جذري (يوليو 2026): مرساة الانحياز الميكانيكية - راجع
        # ict_math_engine.compute_mechanical_bias_anchor للتوثيق الكامل
        # لماذا هذه ضرورية (اكتشاف حي حقيقي: نفس البيانات بالضبط أنتجت
        # BUY_LIMIT ثم SELL_LIMIT بمحاولتين منفصلتين بلا أي تغيّر
        # بالمعطيات). تُحقن هنا كسياق لكل مرحلة تستخدم _authenticity_block
        # (Daily/h4/h15/entry جميعها)، والفحص البرمجي الفعلي لمخالفتها
        # (audit_bias_anchor_consistency) يُطبَّق تحديداً على مرحلة Daily
        # (القائد - أهم قرار اتجاهي بكل الـpipeline).
        try:
            from ict_math_engine import compute_mechanical_bias_anchor
            anchor = compute_mechanical_bias_anchor(data)
            if anchor.get("narrative"):
                lines.append("\n── " + anchor["narrative"])
        except Exception as e:
            self.logger.warning(f"⚠️ Mechanical bias anchor computation failed (non-fatal): {e}")

        # ⚠️ حل جذري إضافي (يوليو 2026، طلب صريح من المستخدم بعد تحقيق
        # عميق بصفقة #12 - راجع docstring compute_structural_break_
        # quality_score/compute_opposing_break_context بـict_math_
        # engine.py للتوثيق الكامل): محرك "وزن الأدلة الهيكلية" - يفحص
        # هل آخر كسر هيكلي (نفس الكسر الذي بُنيت عليه مرساة الانحياز
        # أعلاه) هو فعلاً كسر أصيل، أو "فخ/Inducement" محتمل حسب قسم
        # 4.6 و3.5 بالدستور (كسر ضعيف/مشكوك وسط سياق كسور معاكسة قوي
        # ومتكرر قبله - بالضبط ما اكتُشف بصفقة #12: 9 كسور BEARISH ثم
        # كسر BULLISH ضعيف واحد، البوت اختار BULLISH وخسر -13% خلال
        # 25 يوماً). هذا **حقن سياقي إضافي مرن فقط** - لا شرط قاطع يمنع
        # الدخول، لا يُغيّر anchor أعلاه ولا أي قرار حاسم آخر - فقط
        # معلومة إضافية يقيّمها الموديل بفهمه الكامل بالسياق (تماماً
        # كطلب المستخدم: "بدي حل بشكل عام لكل الحالات، بيكون عن فهم
        # ومرن... مو ١+١=٢").
        try:
            from ict_math_engine import compute_structural_break_quality_score, detect_mss
            mss_for_quality = detect_mss(data, swing_window=2)
            breaks_for_quality = mss_for_quality.get("breaks_found", [])
            if breaks_for_quality:
                last_break_event = breaks_for_quality[-1]
                quality_result = compute_structural_break_quality_score(
                    data, last_break_event, swing_window=2,
                    significant_swings_result=sig if isinstance(sig, dict) else None,
                )
                if quality_result.get("narrative"):
                    lines.append("\n── " + quality_result["narrative"])
        except Exception as e:
            self.logger.warning(f"⚠️ Structural break quality score computation failed (non-fatal): {e}")

        if sweep.get("found"):
            lines.append(
                f"Most recent liquidity sweep (mechanically classified): "
                f"level={sweep.get('swept_level_price')}, "
                f"candle_index_from_end={sweep.get('sweep_candle_index_from_end')}, "
                f"type={sweep.get('swing_type_swept')}, "
                f"classification={sweep.get('classification')} "
                f"(GENUINE_REVERSAL_SWEEP=real trap, "
                f"LIKELY_CONTINUATION_RUN=not a real trap, "
                f"UNCONFIRMED_WAIT_FOR_DISPLACEMENT=wicked back in but no "
                f"confirming displacement yet)."
            )
        else:
            lines.append("Most recent liquidity sweep: none clearly detected mechanically.")

        # ── سلسلة الاستنباط السببية (طلب المستخدم: "استنباطها وترابطها
        # وتقاطعها" - لا حقائق منفصلة، بل علاقة سببية صريحة بين BOS،
        # الـOrder Block الذي أنتجه، الـFVG الناتج عن نفس الاندفاع،
        # وهل هذا كله مرتبط بآخر سحب سيولة معروف) ──
        chain = report.get("causal_derivation_chain", {})
        if chain.get("bos", {}).get("bos_found"):
            lines.append(
                "\n── CAUSAL DERIVATION CHAIN (mechanically derived - a real "
                "causal link between structural facts, not isolated observations) ──"
            )
            lines.append(chain.get("narrative", ""))
            lines.append(
                f"chain_coherent={chain.get('chain_coherent')} "
                f"(True = Sweep→OrderBlock→Displacement→FVG→BOS forms one "
                f"single coherent story; False = these are likely unrelated "
                f"events that happen to coexist, don't force a narrative "
                f"linking them if the mechanics say they aren't linked)."
            )
            lines.append(
                "⚠️ Use this chain explicitly in your reasoning/narrative: name "
                "the specific Order Block candle and FVG this chain identifies "
                "as the origin of the current structure, rather than describing "
                "the BOS in isolation."
            )

        # ⚠️ حل جذري إضافي (يوليو 2026، بطلب صريح من المستخدم بعد بحث
        # عميق موثّق بمنهجية ICT الحقيقية - راجع ict_math_engine.py): نحقن
        # هنا مرشحات Order Blocks/FVGs/كسور هيكلية محسوبة رياضياً بحتاً
        # بالشروط الحرفية (ابتلاع كامل، لمس القاع/القمة، إغلاق تجاوز)،
        # لكن **بلا حكم جاهز على أهميتها** (مثلاً لا "quality": "A/B" - راجع
        # تعليق ict_math_engine.py::detect_order_blocks) - هذه مرشحات
        # موضوعية فقط، يقيّم الموديل أهميتها بذكائه الموجّه بالسياق
        # الكامل (راجع الشرح التعليمي بملف المعرفة - ORDER_BLOCKS،
        # FAIR_VALUE_GAPS، MARKET_STRUCTURE 4.3B).
        try:
            ict_math_text = self._ict_math_candidates_block(data)
            if ict_math_text:
                lines.append(ict_math_text)
        except Exception as e:
            self.logger.warning(f"⚠️ ICT math candidates block failed (non-fatal): {e}")

        # ⚠️ إضافة جديدة (يوليو 2026، بطلب صريح من المستخدم بعد نقاش حول
        # هلوسات الموديل بحسابات رياضية بحتة): طبقة تحقق ثانية مستقلة
        # تماماً عن ict_math_engine.py أعلاه - مكتبة مفتوحة المصدر خارجية
        # (smartmoneyconcepts، github.com/joshyattridge - 1.8k نجمة، نشطة
        # فعلياً) تحسب نفس المفاهيم (قمم/قيعان، BOS/CHoCH، OB، FVG) بمعادلة
        # اكتشاف مختلفة قليلاً (نافذة ثابتة swing_length، بدل الفلترة
        # التكيّفية ATR/prominence بمحرّكنا). راجع smc_library_engine.py
        # للتفصيل الكامل لماذا هذا التنوّع مفيد (توافق = ثقة أعلى، اختلاف
        # = يستحق انتباهاً بالتفسير) - **ليست حكماً بديلاً**، فشلها غير
        # قاتل (المكتبة اختيارية - لا تعتمد عليها أي بوابة قرار حاسمة).
        try:
            from smc_library_engine import compute_smc_library_facts
            smc_lib_text = compute_smc_library_facts(data)
            if smc_lib_text:
                lines.append(smc_lib_text)
        except Exception as e:
            self.logger.warning(f"⚠️ SMC library cross-check failed (non-fatal): {e}")

        return "\n".join(lines)

    def _ict_math_candidates_block(self, data):
        """
        ⚠️ حل جذري (يوليو 2026): يبني نصاً جاهزاً من مرشحات
        ict_math_engine.py (FVGs، Order Blocks، كسور هيكلية) - **مرشحات**، لا
        قرارات. كل مرشح يُذكر بحقائقه الموضوعية فقط (لمس، إغلاق، نسبة
        امتلاء، هل سبقه سحب حقيقي) - الموديل هو يلي يقيّم أي هالمرشح
        مهم فعلاً بذكائه الموجّه (راجع شرح MASTER_TRADER_MINDSET وHOLISTIC_MARKET_READING).
        """
        from ict_math_engine import (compute_displacement, detect_fair_value_gaps,
                                       detect_order_blocks, detect_mss)

        n = len(data.get("closes", []))
        if n < 15:
            return ""

        lines = ["\n── ICT MECHANICAL CANDIDATES (objective facts only, NOT "
                 "pre-judged conclusions - YOU decide which candidate matters "
                 "given the full context; see constitution sections ORDER_BLOCKS, "
                 "FAIR_VALUE_GAPS, MARKET_STRUCTURE 4.2/4.3/4.3B for how to weigh "
                 "each fact) ──"]

        # FVGs (أعلى 3 أحدث لكل اتجاه، مع نسبة امتلاء وهل يوجد اندفاع خلفها)
        try:
            fvgs = detect_fair_value_gaps(data, lookback=40, require_displacement=False)
            for label, items in (("bullish", fvgs["bullish_fvgs"]), ("bearish", fvgs["bearish_fvgs"])):
                for f in items[-3:]:
                    lines.append(
                        f"FVG candidate ({label}): idx {f['index_from_end']}, "
                        f"top={f['top']}, bottom={f['bottom']}, CE(midpoint)={f['ce']}, "
                        f"filled_so_far={f['filled_pct']}%, "
                        f"displacement_behind_it={f['displacement_confirmed']}."
                    )
        except Exception as e:
            self.logger.warning(f"⚠️ FVG candidates failed (non-fatal): {e}")

        # Order Blocks (أعلى 3 أحدث لكل اتجاه)
        try:
            obs = detect_order_blocks(data, lookback=40)
            for label, items in (("bullish", obs["bullish_obs"]), ("bearish", obs["bearish_obs"])):
                for ob in items[-3:]:
                    lines.append(
                        f"Order Block candidate ({label}): idx {ob['index_from_end']}, "
                        f"top={ob['top']}, bottom={ob['bottom']}, "
                        f"engulfed_fully={ob['engulf_confirmed']}, "
                        f"fvg_nearby={ob['fvg_nearby']}, "
                        f"tested_since={ob['tested_count']} time(s)."
                    )
        except Exception as e:
            self.logger.warning(f"⚠️ Order Block candidates failed (non-fatal): {e}")

        # الكسور الهيكلية الحقيقية (MSS الصارم/BOS العادي - كلها تُعرض،
        # لا يُختار منها واحد فقط - راجع تعليق detect_mss الجديد)
        try:
            mss_info = detect_mss(data, swing_window=2)
            for b in mss_info["breaks_found"][-4:]:
                sweep = b["prior_sweep"]
                sweep_desc = (
                    f"genuine_prior_sweep={sweep.get('genuine_reversal_sweep')}"
                    if sweep.get("found") else "no_prior_wick_beyond_older_swing"
                )
                lines.append(
                    f"Structural break candidate ({b['direction']}): broke level "
                    f"{b['broken_level']} (idx {b['broken_level_index_from_end']}) "
                    f"at break candle idx {b['break_candle_index_from_end']}, "
                    f"displacement_on_break={b['displacement_confirmed']}, {sweep_desc}. "
                    f"[Per MARKET_STRUCTURE 4.2/4.3B: only call this MSS if a genuine "
                    f"prior sweep exists; otherwise it is a standard BOS/CHoCH per the "
                    f"trend context, still real but a weaker signal - decide using your "
                    f"full understanding of the section, not this label alone.]"
                )
        except Exception as e:
            self.logger.warning(f"⚠️ Structural break candidates failed (non-fatal): {e}")

        # دقائق الاندفاع (Displacement) - أحدث واحد فقط للإيجاز
        try:
            disp = compute_displacement(data, lookback=20)
            if disp["most_recent_displacement"]:
                d = disp["most_recent_displacement"]
                lines.append(
                    f"Most recent displacement candle (body>=65% of range AND "
                    f">=1.5xATR - see ORDER_BLOCKS 5.1 displacement criteria): "
                    f"idx {d['index_from_end']}, direction={d['direction']}, "
                    f"body_pct={d['body_pct']}%, body/ATR={d['body_atr_ratio']}x."
                )
        except Exception as e:
            self.logger.warning(f"⚠️ Displacement summary failed (non-fatal): {e}")

        if len(lines) <= 1:
            return ""
        return "\n".join(lines)

    def _build_weekly_prompt(self, symbol, weekly_data, authenticity_text=""):
        return f"""
{'='*40}
MARKET: {symbol} - WEEKLY TIMEFRAME (STEP 1/5: NARRATIVE)
{'='*40}
Weekly Candles (oldest to newest):
{self._candles_block(weekly_data, 52)}
{authenticity_text}
TASK (Step 1 - Weekly Analysis, Section 12.2):
This is the BIG PICTURE ONLY. Identify the Weekly trend, its strength,
where the macro Draw on Liquidity is, and whether price is currently
at a major Weekly point of interest. Do NOT analyze entries here -
that comes 4 steps later. This step never blocks the workflow, it
only provides context for what follows.
"""

    def _build_daily_prompt(self, symbol, daily_data, weekly_result, smt_text="", authenticity_text=""):
        smt_block = f"\n{smt_text}\n" if smt_text else ""
        return f"""
{'='*40}
MARKET: {symbol} - DAILY TIMEFRAME (STEP 2/5: BIAS - THE COMMANDER)
{'='*40}
Daily Candles (oldest to newest):
{self._candles_block(daily_data, 60)}
{authenticity_text}
WEEKLY CONTEXT (Step 1, already established):
{json.dumps(weekly_result, ensure_ascii=False)}
{smt_block}
TASK (Step 2 - Daily Analysis, Section 12.3):
The Daily Bias is THE MOST IMPORTANT decision in this entire workflow -
"is today likely bullish or bearish?" All later steps must serve this
bias. If the Daily structure is genuinely ranging/unclear, say UNCLEAR
honestly - do NOT force a direction just to keep the analysis going.
A false confident bias here corrupts everything downstream.
{"If an SMT Divergence signal is provided above, treat it as ONE additional piece of evidence to weigh - not an automatic override of your own reading of the Daily candles. Mention explicitly in your reasoning whether it aligns with or contradicts your own structural read." if smt_text else ""}
"""

    def _build_4h_prompt(self, symbol, h4_data, weekly_result, daily_result, authenticity_text=""):
        # ⚠️ إصلاح فجوة حقيقية مكتشفة (2026-07-03): كنا نجلب 120 شمعة 4h
        # (يغطي 20 يوم - يطابق بالضبط نطاق IPDA "الأولوية القصوى" بالدستور
        # قسم [IPDA_DATA_RANGES]) لكن كنا نعرض للـAI فقط آخر 60 منها (10 أيام فقط -
        # نصف نطاق الأولوية القصوى الذي يحدده الدستور نفسه). هذا يعني أن أي Order Block أو
        # FVG تشكّل قبل 10-20 يوماً (ضمن نطاق أولوية IPDA القصوى رسمياً) كان
        # يُحرَم من الـAI بلا داعِ حقيقي. الإصلاح: عرض كامل الـ120 شمعة المجلوبة فعلاً
        # (تحقق تكلفة: ~730 توكن إضافي فقط لكل طلب - مهمل تماماً مقابل
        # حد 80K-256K توكن للموديل الحالي).
        return f"""
{'='*40}
MARKET: {symbol} - 4H TIMEFRAME (STEP 3/5: CONTEXT)
{'='*40}
4H Candles (oldest to newest):
{self._candles_block(h4_data, 120)}
{authenticity_text}
DAILY BIAS (Step 2, already established - ALL analysis here must
check alignment with this, not contradict it silently):
{json.dumps(daily_result, ensure_ascii=False)}

TASK (Step 3 - 4H Analysis, Section 12.4):
Refine the Daily bias into specific 4H zones and structure. Determine
which Market Maker Model phase (1-5) price is currently in, whether
4H structure aligns with, pulls back within, or conflicts with the
Daily bias, and whether price is currently AT a refined entry zone.
"""

    def _build_15m_prompt(self, symbol, h15_data, daily_result, h4_result,
                           authenticity_text="", session_text=""):
        # ⚠️ حل جذري (يوليو 2026، بطلب صريح من المستخدم):
        # هذه المرحلة كانت "1H tactical" (هل يتشكّل دخول الآن؟) - الآن
        # أصبحت "15m ليكويديتي"، تطابق دور 15m الحقيقي عند مايكل:
        # تحديد السيولة (Equal Highs/Lows)، الـFVGs الحديثة، نطاق الجلسة،
        # والتحقق من وجود Judas Swing - لا فقط "هل MSS تشكّل؟" الضيقة.
        # التنفيذ الفعلي نفسه يبقى لمرحلة Entry (1-5m) التالية فقط.
        #
        # ⚠️ حل جذري إضافي (يوليو 2026، بطلب صريح من المستخدم: "الموديل
        # ما يقرب أبداً على تحليل البيانات الخام والأرقام من عنده - لازم
        # يوصله كلشي جاهز"): last_candle OHLC/color لم يعد يُطلب من
        # الموديل "قراءته ونسخه" من الجدول (مصدر هلوسة متكرر موثّق) -
        # يُحسب هنا رياضياً بحتاً ويُحقن كحقيقة جاهزة، لا حقل يُطلب
        # إخراجه بالـschema بعد الآن (راجع _compute_last_candle_fact).
        last_candle_fact = self._compute_last_candle_fact(h15_data)
        last_candle_text = (
            f"\n⚠️ PRE-COMPUTED LAST CANDLE (mechanically calculated - this "
            f"IS the last 15m candle, do not re-derive or second-guess it): "
            f"open={last_candle_fact['open']:.6g}, high={last_candle_fact['high']:.6g}, "
            f"low={last_candle_fact['low']:.6g}, close={last_candle_fact['close']:.6g}, "
            f"color={last_candle_fact['color']}."
            if last_candle_fact else ""
        )
        return f"""
{'='*40}
MARKET: {symbol} - 15-MINUTE TIMEFRAME (STEP 4/5: LIQUIDITY & TACTICAL STRUCTURE)
{'='*40}
{session_text}

15-Minute Candles (oldest to newest):
{self._candles_block(h15_data, 80)}
{authenticity_text}
DAILY BIAS: {json.dumps(daily_result, ensure_ascii=False)}
4H CONTEXT: {json.dumps(h4_result, ensure_ascii=False)}

TASK (Step 4 - 15-Minute Analysis - this is the ICT "liquidity and
tactical structure" timeframe, per section [ICT_TIME_AND_SESSIONS]
9.1B and [LIQUIDITY_MAPPING]):
1. Map liquidity on this timeframe: identify any Equal Highs/Equal
   Lows (EQH/EQL) forming, and the overnight range (if the session
   context above marks one) - these are the pools price is being
   drawn toward or has just swept.
2. Check for a Judas Swing per [ICT_TIME_AND_SESSIONS] 9.3/9.1B: has
   price swept liquidity opposite to the Daily Bias during the
   relevant window (see session context above), and is there any
   sign of reversal (CISD, or a close back inside the swept level)?
3. Is a structural shift (MSS/CHoCH/CISD - see MARKET_STRUCTURE 4.2,
   4.3, 4.3B) forming at the HTF zone identified in Step 3 (4H
   Context), matching the Daily Bias direction? Name explicitly which
   of these three signals (if any) you observed, since they arrive at
   different times with different reliability (CISD earliest/weakest,
   MSS latest/strongest) - do not treat them as interchangeable.
4. This stage does NOT execute a trade - it hands off a tactical
   picture (liquidity map + structural signal status + session
   context) to Step 5 (1-5 minute execution timeframe), which makes
   the final entry decision.
{'='*40}
⚠️ FINAL MECHANICAL FACT - READ THIS LAST
{'='*40}
{last_candle_text}
"""

    def _build_deterministic_verdict_prompt(self, symbol, timeframe, entry_candles_text,
                                             entry_indicators_text, weekly_result, daily_result,
                                             h4_result, h15_result, entry_authenticity_text,
                                             session_text, chosen_model, plan):
        """
        ⚠️ برومبت مختصر جداً (يوليو 2026، راجع docstring
        _deterministic_verdict_schema للفلسفة الكاملة) - بعكس
        _build_entry_prompt، هذا **لا يطلب من الموديل استنباط أي رقم**
        - الأرقام جاهزة 100% من checklist الحتمي، معروضة هنا كحقيقة
        نهائية. المهمة الوحيدة: فحص هل يوجد دليل هيكلي حقيقي (لا انطباع)
        يبطلها.
        """
        cond_lines = "\n".join(
            f"  - {c['name']}: {c['status']} ({c['detail']})" for c in chosen_model["conditions"]
        )
        return f"""
{'='*40}
MARKET: {symbol} ({timeframe}) - DETERMINISTIC ENTRY VERDICT
{'='*40}
{session_text}

Daily Bias (STEP 2, established already - the commander): {daily_result.get('direction') if isinstance(daily_result, dict) else 'N/A'}
H4 context: {(h4_result.get('h4_context_summary') or '')[:400] if isinstance(h4_result, dict) else ''}
15m structural shift: {h15_result.get('structural_shift_direction') if isinstance(h15_result, dict) else 'N/A'}

{entry_authenticity_text}

── MECHANICAL PLAN ALREADY COMPUTED (deterministic, from {chosen_model['model']}, status={chosen_model['status']}) ──
Conditions:
{cond_lines}

READY-TO-EXECUTE PLAN (these numbers are FINAL and were NOT generated by you - they come directly
from Python mathematical computation on the real OHLC data, per Michael's (ICT) structural
methodology exactly): direction={plan['direction']}, entry={plan['entry']}, stop_loss={plan['stop_loss']},
TP1={plan.get('tp1')}, TP2={plan.get('tp2')}, R:R to TP1={plan['rr']}
Basis: {plan['basis']}
evidence_anchor_idx (the candle index this plan is founded on): {plan.get('evidence_anchor_idx')}

{'='*40}
YOUR TASK (narrow, binary):
{'='*40}
You do NOT compute entry/stop_loss/tp - those numbers are already final. Your ONLY job:

1. ACCEPT_PLAN: if there is no genuine structural evidence contradicting this plan - execute it as-is.
   This should be your answer in the vast majority of cases where the checklist above is sound.

2. REJECT_WITH_EVIDENCE: ONLY if you can identify a SPECIFIC, NAMED structural event (a genuine
   opposing CHoCH/MSS/BOS, a Daily Bias contradiction, or session timing invalidity) that occurred
   at a candle index NEWER than (>=) evidence_anchor_idx={plan.get('evidence_anchor_idx')}. A vague
   reservation ("might reverse", "no confirmation yet", "seems risky") is NOT valid evidence - it
   will be mechanically verified against the actual data and rejected automatically if unsupported.
   If you choose this, you MUST fill rejection_evidence_type and rejection_candle_index precisely.

Do not restate the plan's numbers. Do not invent alternative numbers. Answer only the binary verdict.
"""

    def _build_entry_prompt(self, symbol, timeframe, entry_candles_text, entry_indicators_text,
                             weekly_result, daily_result, h4_result, h15_result, is_backtest,
                             authenticity_text="", min_sl_hint="", session_text="",
                             entry_data=None):
        # ⚠️ حل جذري (يوليو 2026، بطلب صريح من
        # المستخدم): قبل هذا الإصلاح، وضع الباك تيست
        # كان يُجبر BUY/SELL دائماً بغض النظر عن وصول
        # السعر فعلاً لمنطقة الدخول - هذا كان يُجبر الموديل
        # يختلق رقم دخول حالي وهمي بدل أمر معلق منطقي صادق.
        # الآن: التعليمات توضح الخيارات الأربع (BUY/SELL فوري،
        # BUY_LIMIT/SELL_LIMIT معلق، HOLD فقط لو لا يوجد إعداد قابل
        # للتحديد إطلاقاً) بدل فرض اتجاه بلا معنى.
        backtest_note = (
            "\n\nBACKTEST MODE: prefer a directional outcome (BUY/SELL if "
            "price is AT the entry zone right now with LTF confirmation, or "
            "BUY_LIMIT/SELL_LIMIT if a specific entry/SL/tp zone is genuinely "
            "identified but price has not reached it yet) since Daily Bias "
            "was already established. Only output HOLD if truly no concrete, "
            "specific setup can be identified at all (not merely because "
            "price hasn't arrived at a known zone yet - that case is "
            "BUY_LIMIT/SELL_LIMIT, not HOLD)."
            if is_backtest else ""
        )

        # ⚠️ حل جذري (يوليو 2026، بعد تحليل دقيق لسجل حي فعلي كشف نفس
        # نمط LAST_CANDLE_HALLUCINATION يتكرر رغم تحذير نصي موجود أصلاً
        # بالبرومبت): السبب الجذري الحقيقي المكتشف (بلا أي نداء API -
        # فحص مباشر للبيانات الخام نفسها): مرحلة h15 (STEP 4) تُحقن هنا
        # كـJSON **كامل** يتضمن حقل `last_candle_report` الخاص بها (شمعة
        # فريم 15m - غالباً بلون/فتح مختلفين عن شمعة فريم الدخول 5m رغم
        # تطابق الإغلاق أحياناً، لأنها نفس اللحظة الزمنية بفريمين مختلفين
        # حسابياً). رغم وجود تحذير نصي ("STEP 4 قد يكون فريم مختلف - لا
        # تخلط بينهما") - هذا نص عام يعتمد على انتباه الموديل، لا حماية
        # رياضية. **حقيقة موثّقة بسجل حي فعلي**: نفس هذا الخطأ بالضبط
        # (نسخ لون/قيم شمعة STEP 4 بدل شمعة الـEntry TF الحقيقية) تكرر
        # عدة مرات متتالية رغم التحذير النصي.
        #
        # الحل الجذري الصحيح (لا ترقيع نصي إضافي، إزالة مصدر اللخبطة
        # نفسه): حقل `last_candle_report` لا حاجة تحليلية حقيقية له إطلاقاً
        # بمرحلة entry - "تلخيص آخر شمعة" لكل مرحلة سابقة (Weekly/Daily/
        # 4H/15m) هو تفصيل تحقّق داخلي خاص بتلك المرحلة فقط (فحص دقة قراءة
        # حينها)، لا معلومة يحتاجها القرار النهائي بمرحلة entry - إزالته
        # من كل نتائج المراحل السابقة **قبل** حقنها هنا يُلغي مصدر الخلط
        # بالكامل من جذره، بدل الاعتماد على "تحذير نصي يُرجى الانتباه له".
        def _strip_last_candle(stage_dict):
            if not isinstance(stage_dict, dict):
                return stage_dict
            return {k: v for k, v in stage_dict.items() if k != "last_candle_report"}

        weekly_for_prompt = _strip_last_candle(weekly_result)
        daily_for_prompt = _strip_last_candle(daily_result)
        h4_for_prompt = _strip_last_candle(h4_result)
        h15_for_prompt = _strip_last_candle(h15_result)

        # ⚠️ حل جذري إضافي (يوليو 2026، بطلب صريح من المستخدم: "الموديل
        # ما يقرب أبداً على تحليل البيانات الخام والأرقام من عنده") -
        # نفس المبدأ المُطبَّق بمرحلة h15: last_candle_report لم يعد
        # حقلاً يُطلب من الموديل إخراجه بالـschema إطلاقاً (أُزيل
        # بالكامل) - يُحسب هنا رياضياً بحتاً ويُحقن كحقيقة جاهزة نهاية
        # البرومبت (أقرب موقع لانتباه الموديل قبل التوليد).
        last_candle_fact = self._compute_last_candle_fact(entry_data)
        last_candle_text = (
            f"⚠️ PRE-COMPUTED LAST CANDLE ON THE ENTRY TF ({timeframe}) - "
            f"mechanically calculated directly from the \"Entry TF Candles\" "
            f"block above, this IS the last candle, do not re-derive it "
            f"yourself or second-guess it: open={last_candle_fact['open']:.6g}, "
            f"high={last_candle_fact['high']:.6g}, low={last_candle_fact['low']:.6g}, "
            f"close={last_candle_fact['close']:.6g}, color={last_candle_fact['color']}."
            if last_candle_fact else ""
        )

        return f"""
{'='*40}

MARKET: {symbol} ({timeframe}) - ENTRY TF (STEP 5/5: EXECUTION)
{'='*40}
{session_text}
{entry_indicators_text}

Entry TF Candles:
{entry_candles_text}
{authenticity_text}

ALL PRIOR STEPS (already completed and gated - each one PASSED its
gate to reach here):
STEP 1 - Weekly Narrative: {json.dumps(weekly_for_prompt, ensure_ascii=False)}
STEP 2 - Daily Bias: {json.dumps(daily_for_prompt, ensure_ascii=False)}
STEP 3 - 4H Context: {json.dumps(h4_for_prompt, ensure_ascii=False)}
STEP 4 - 15m Tactical: {json.dumps(h15_for_prompt, ensure_ascii=False)}

⚠️ NOTE: the STEP 1-4 JSON summaries above deliberately do NOT include
their own last-candle details (removed on purpose - you are not asked
to report or re-derive any candle's OHLC/color anywhere in this task;
that mechanical fact is provided to you separately below, already
computed - a documented real bug happened repeatedly when this was
left for manual reading/copying instead).

⚠️ EXECUTION TIMING: per [ICT_TIME_AND_SESSIONS], time is as important
as price. Check the CURRENT TIME / session context above (if provided)
before finalizing an immediate BUY/SELL - executing outside a Kill
Zone window, even at a technically clean setup, has a lower historical
probability of reaching target (see 9.1B for the crypto-adapted
windows). If currently outside an executable Kill Zone, prefer
BUY_LIMIT/SELL_LIMIT (to be triggered whenever price reaches the zone,
Kill Zone or not) over an immediate BUY/SELL, unless the setup is a
continuation of an already-confirmed intra-Kill-Zone move.

⚠️ SIGNAL TYPE - READ CAREFULLY (this determines which of 4 possible
outcomes you must choose, root-caused from a real user request: "if the
setup conditions are met, give me a recommendation whether it's for
right now or for later - if the price hasn't reached entry yet, still
give me entry/target/stop so I can place a pending limit order before
it arrives; if it arrives, great; if not, I lost nothing"):
  - BUY / SELL: price is RIGHT NOW at the identified entry zone AND the
    LTF (15m/entry-TF) structural confirmation (MSS/CHoCH/CISD - see
    MARKET_STRUCTURE 4.2/4.3/4.3B) has already occurred.
    This is an immediate market-execution signal.
  - BUY_LIMIT / SELL_LIMIT: the setup sequence is ALREADY complete
    (liquidity event + displacement/structural confirmation + a real
    OB/FVG/OTE with coordinates), but price has not retraced to the
    confirmed entry level yet. Never place a limit merely because a
    sweep level exists, and never pre-position while displacement, FVG,
    LTF confirmation, or the model-specific timing is still PENDING.
  - HOLD: no complete actionable setup exists now. If some conditions
    are still PENDING, explicitly label it WAIT_CONFIRMATION/watch-list
    in the narrative; do not turn the scenario into an order.

TASK (Step 5 - Entry Execution, Section 12.6, THE FINAL CROSS-CHECK):
1. FIRST, explicitly cross-reference all 4 prior steps in
   cross_reference_check: do Weekly/Daily/4H/1H all agree on direction?
   Name any step that conflicts with the others and how you resolved it.
2. Identify which of the 6 Entry Models (section [ENTRY_MODELS]) this
   exact setup satisfies - Model A (OTE+OB), B (Sweep+FVG), C (BOS
   Pullback), D (AMD Session), E (Silver Bullet), or F (CHoCH Reversal).
   Only select a model whose ACTUAL conditions (as defined in the
   constitution) are met by this specific setup - do not force-fit a
   model whose conditions are not genuinely satisfied. If none apply
   cleanly, or if signal=HOLD, entry_model="NONE".
3. Decide the signal type per the SIGNAL TYPE section above, then
   construct the precise trade EXACTLY as Michael (ICT) would, with NO
   consideration of any percentage cap or risk-reward minimum at this
   stage (that comparison happens separately, AFTER this plan, purely
   as information for the user - it does not constrain your analysis
   here): entry at the precise PD Array level (OB CE/FVG CE per the
   applicable Entry Model), SL placed at the genuine structural
   invalidation level (the real OB edge / swing point / liquidity-sweep
   extreme that this specific setup depends on) plus the mandatory
   buffer - place it exactly where the structure says it belongs, no
   matter how wide or tight that turns out to be numerically. Set the
   provisional `tp` to the nearest genuine, unswept liquidity level in
   the trade direction and report its actual R:R honestly. Do not
   stretch or cherry-pick a farther level to manufacture 3R. A
   deterministic post-processor will expose this as TP1 (50%) and will
   add TP2 (50%) only when a distinct farther HTF draw has at least two
   independent confirmations; otherwise it will explicitly return an
   OPEN_TRAILING runner rather than inventing a second number.
4. The final signal MUST match the Daily Bias direction (Step 2) - it
   is the commander. If your entry-TF read of the last candles
   contradicts Daily Bias, that contradiction must be named explicitly
   in bos_reconciliation, not silently overridden.{backtest_note}

{'='*40}
⚠️ FINAL MECHANICAL CONSTRAINTS - READ THIS LAST, RIGHT BEFORE YOU
ANSWER (these are placed here deliberately, at the very end of a long
prompt, so they are the last thing in your attention before you output
numbers - a documented real failure showed these being ignored when
buried earlier in a long prompt, even though they were technically
present)
{'='*40}
{last_candle_text}
{min_sl_hint}
"""

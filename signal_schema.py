# -*- coding: utf-8 -*-
"""
signal_schema - تعريف بنية JSON صارمة (Gemini responseSchema)
════════════════════════════════════════════════════════════════════
المشكلة اللي يحلها هذا الملف:
  بدون schema صارم، النموذج اللغوي حر يختار شكل كل حقل بحرية - فمرة
  يرجع confidence كرقم (75)، ومرة كـ dict ({"value": 75})، ومرة كنص
  ("75%"). هذا مش لأنه "ما فاهم" التحليل - هذا لأن ما في قيد صارم
  يجبره على بنية ثابتة، فهو (متل أي نموذج لغوي) يولّد الشكل الأقرب
  لسياق كتابته لحظتها.

  responseSchema من Gemini (JSON Schema-like) يجبر فرضاً أن:
    confidence = INTEGER فقط، لا يوجد شكل آخر ممكن على الإطلاق
    signal = ENUM من ["BUY", "SELL", "HOLD"] فقط
    entry/stop_loss/tp = NUMBER فقط

  هذا يحل عدم استقرار "الشكل" (format) بشكل قاطع 100% - النموذج ببساطة
  لا يستطيع إرجاع شكل آخر، البنية مفروضة من مستوى الـ API نفسه.

  ملاحظة مهمة: هذا لا يحل عدم استقرار "المحتوى" (القيمة الفعلية لدرجة
  الثقة قد تتغير ±5-10% بين طلبين متطابقين بسبب طبيعة النماذج
  الاحتمالية) - لهذا نضيف consistency_test.py كأداة قياس منفصلة.
"""

# Gemini يدعم subset من OpenAPI 3.0 Schema
_PRICE_FIELD = {"type": "NUMBER"}

_KEY_LEVEL_ITEM = {
    "type": "OBJECT",
    "properties": {
        "level": {"type": "STRING"},
        "price": {"type": "NUMBER"},
    },
}

_SMC_ZONE_ITEM = {
    "type": "OBJECT",
    "properties": {
        "type": {"type": "STRING"},
        "timeframe": {"type": "STRING"},
        "top": {"type": "NUMBER"},
        "bottom": {"type": "NUMBER"},
        "note": {"type": "STRING"},
    },
}

# ⚠️ إصلاح خطأ حقيقي مُكتشف بالباك تيست الفعلي (يوليو 2026): النموذج
# وصف الشمعة الأخيرة نصياً بشكل خاطئ تماماً (قال "صاعدة قوية body_pct
# ~80%" بينما كانت فعلياً هابطة body_pct=16.7%، وحالة ثانية مطابقة على
# صفقة مختلفة) - "هلوسة لون الشمعة" لبناء قصة (narrative) مسبقة بدل
# قراءة الأرقام الفعلية أولاً. النص الحر غير قابل للتحقق الآلي بسهولة
# (بحاجة NLP)، فأضفنا حقل JSON منظم صارم يُجبر النموذج يذكر أرقام آخر
# شمعة صراحة كحقول رقمية - AuthenticityEngine.audit_last_candle_report()
# يقارنها آلياً 100% (لا اعتماد على فهم نص) مع الحقيقة الحسابية.
_LAST_CANDLE_REPORT = {
    "type": "OBJECT",
    "description": (
        "إلزامي: انسخ بالضبط قيم آخر شمعة (الأحدث) من البيانات المُعطاة "
        "بدون أي تفسير - هذا فحص دقة قراءة أساسي، ليس تحليلاً"
    ),
    "properties": {
        "open": {"type": "NUMBER"},
        "high": {"type": "NUMBER"},
        "low": {"type": "NUMBER"},
        "close": {"type": "NUMBER"},
        "color": {
            "type": "STRING",
            "enum": ["BULLISH", "BEARISH"],
            "description": "BULLISH إذا close > open حصراً، BEARISH إذا close < open حصراً - رياضياً لا تفسيراً",
        },
    },
    "required": ["open", "high", "low", "close", "color"],
}


def get_signal_schema(is_backtest=False):
    """
    يرجع Gemini responseSchema لإشارة تداول - يفرض بنية ثابتة 100%.

    Args:
        is_backtest: إذا True، signal لا يشمل HOLD (backtest mode)
    """
    signal_enum = ["BUY", "SELL"] if is_backtest else ["BUY", "SELL", "HOLD"]

    schema = {
        "type": "OBJECT",
        "properties": {
            "visual_silhouette": {
                "type": "STRING",
                "description": (
                    "إلزامي (Section 26.1) - أول حقل تكتبه، قبل أي شي "
                    "تاني: صف الشكل العام الكامل للشارت بجملة أو جملتين "
                    "(لو رسمته بخط واحد متواصل متجاهل الفتائل - درج "
                    "صاعد؟ قمة مدورة؟ V-shape هبوط وارتداد؟ نطاق مسطح "
                    "بذيل بآخره؟)، ووين موقع السعر الحالي منه (ثلث "
                    "علوي/وسط/سفلي، أو بالضبط عند نقطة انعطاف)، وهل "
                    "الشكل ثابت الطابع أو تغيّر بمنتصفه ووين بالضبط. "
                    "هذا انطباع بصري شمولي أولي (نظرة العين الكاملة "
                    "للصورة) - يُكتب قبل last_candle_report وقبل أي "
                    "رقم فني تفصيلي."
                ),
            },
            "last_candle_report": _LAST_CANDLE_REPORT,
            "narrative": {
                "type": "STRING",
                "description": (
                    "القصة الكاملة لما يحدث بالسوق - يُكتب أولاً قبل أي رقم فني. "
                    "⚠️ يجب أن يتفق وصفك للشمعة الأخيرة هنا حرفياً مع "
                    "last_candle_report أعلاه (نفس اللون، نفس الحجم النسبي) - "
                    "لا تصف الشمعة الأخيرة بعكس لونها الفعلي. ويجب أن يتسق "
                    "مع visual_silhouette (Section 26.3: وفّق بين الصورة "
                    "الكبيرة والتفاصيل الدقيقة، واذكر صراحة أي تعارض بينهما)."
                ),
            },
            "archetype": {
                "type": "STRING",
                "description": "أقرب نمط من الخبرة السابقة (spring, exhaustion, pullback...)",
            },
            "bos_reconciliation": {
                "type": "STRING",
                "description": (
                    "إلزامي (Section 24.3): اذكر صراحة اتجاه آخر BOS مؤكد "
                    "(UP/DOWN/none) وهل قرارك النهائي يتفق أو يتعارض معه. "
                    "لو تعارض، اذكر الدليل المحدد (رقم/شمعة) من قسم 21.1 "
                    "أو 21.2 يلي يبرر تجاهل هذا الـBOS - وليس فقط إعادة "
                    "ذكر الاتجاه العام القديم كسبب."
                ),
            },
            "bos_candle_index_from_end": {
                "type": "INTEGER",
                "description": (
                    "إلزامي: رقم الشمعة (سالب، مثلاً -1 = آخر شمعة، -2 = "
                    "قبل الأخيرة) التي كسرت آخر BOS مؤكد ذكرته أعلاه. "
                    "⚠️ خطأ حقيقي مُكتشف بالباك تيست: النموذج ادّعى BOS "
                    "من منتصف النافذة (مثلاً شمعة #42 من أصل 50) كـ'آخر "
                    "BOS' بينما كان هناك كسر أحدث بكثير (شمعة #49) تجاهله "
                    "تماماً. امسح كل الشموع من -1 وحتى -15 فعلياً بحثاً عن "
                    "أحدث كسر هيكلي قبل الإجابة - لا تكتفِ بأول كسر واضح "
                    "تراه بصرياً إذا كان هناك كسر أحدث لم تفحصه بعد."
                ),
            },
            "bias": {
                "type": "STRING",
                "enum": ["BULLISH", "BEARISH", "NEUTRAL"],
            },
            "signal": {
                "type": "STRING",
                "enum": signal_enum,
            },
            "entry": _PRICE_FIELD,
            "stop_loss": _PRICE_FIELD,
            "tp": _PRICE_FIELD,
            "confidence": {
                "type": "INTEGER",
                "description": "0-100 فقط، رقم صحيح دائماً - لا نص، لا dict",
            },
            "rr": {
                "type": "STRING",
                "description": "بصيغة '1:X' حصراً، مثال '1:3.5'",
            },
            "reasoning": {
                "type": "STRING",
                "description": "التحقق الميكانيكي بالأرقام - بعد narrative/archetype",
            },
            "market_regime": {
                "type": "STRING",
                "enum": ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE"],
            },
            "macro_bias": {"type": "STRING"},
            "structure_analysis": {"type": "STRING"},
            "smc_zones_found": {
                "type": "OBJECT",
                "properties": {
                    "order_blocks": {"type": "ARRAY", "items": _SMC_ZONE_ITEM},
                    "fvg": {"type": "ARRAY", "items": _SMC_ZONE_ITEM},
                    "liquidity": {"type": "ARRAY", "items": _SMC_ZONE_ITEM},
                    "bos_choch": {"type": "ARRAY", "items": _SMC_ZONE_ITEM},
                },
            },
            "confluence_factors": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
            "confluence_count": {"type": "INTEGER"},
            "key_levels": {
                "type": "ARRAY",
                "items": _KEY_LEVEL_ITEM,
            },
            "risks": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
            "invalidation": {"type": "STRING"},
        },
        "required": [
            "visual_silhouette", "narrative", "archetype", "bias", "signal",
            "confidence", "reasoning", "market_regime", "bos_reconciliation",
            "last_candle_report", "bos_candle_index_from_end",
        ],
    }

    if is_backtest:
        schema["properties"]["why_this_direction"] = {"type": "STRING"}
        schema["required"].extend(["entry", "stop_loss", "tp", "rr"])

    return schema


# ══════════════════════════════════════════════════════════════════
#  طبقة تطبيع احتياطية (Normalizer)
# ══════════════════════════════════════════════════════════════════
# حماية إضافية لأي مزود لا يدعم responseSchema (Groq/OpenRouter/
# SambaNova) أو لأي رد قديم مخزّن بالـ cache بشكل غير موحّد. تحوّل
# أي شكل بديل معروف (confidence كـ dict/نص) إلى الشكل الموحّد القياسي
# قبل ما يوصل لبقية الكود (RiskManager, VerificationLayer...).

def normalize_signal_dict(result):
    """
    يوحّد أشكال الحقول الشائعة الاضطراب داخل رد الـ AI:
      confidence: 75 | "75%" | {"value": 75} | {"score": 75} -> int 75
      signal: "buy" | "Buy" | "BUY " -> "BUY"
      entry/stop_loss/tp/tp1/tp2/tp3: "60,145.5" | "$60145.5" -> float
    """
    if not isinstance(result, dict):
        return result

    # ── confidence ──
    conf = result.get("confidence")
    if isinstance(conf, dict):
        conf = conf.get("value") or conf.get("score") or conf.get("confidence")
    if isinstance(conf, str):
        digits = "".join(ch for ch in conf if ch.isdigit() or ch == ".")
        conf = float(digits) if digits else None
    if conf is not None:
        try:
            result["confidence"] = int(round(float(conf)))
        except (ValueError, TypeError):
            pass

    # ── signal ──
    # ⚠️ حل جذري (يوليو 2026): أضفنا BUY_LIMIT/
    # SELL_LIMIT (أوامر معلقة حقيقية - اتجاه ومنطقة
    # دخول معروفة، السعر لم يصلها بعد) إلى القائمة
    # المقبولة - قبل هذا الإصلاح كانت هذه الدالة تُسقط
    # بصمت أي قيمة ليست "BUY"/"SELL"/"HOLD" حرفياً (تفرغ
    # الحقل إلى None بصمت) - لو وصلت BUY_LIMIT من الموديل
    # كانت تُمحى بصمت هنا ويُفقد التمييز بين أمر فوري وأمر
    # معلق بلا داعٍ حقيقي.
    sig = result.get("signal")
    if isinstance(sig, str):
        sig_upper = sig.strip().upper()
        if sig_upper in ("BUY", "SELL", "HOLD", "BUY_LIMIT", "SELL_LIMIT"):
            result["signal"] = sig_upper
    elif isinstance(sig, dict):
        inner = sig.get("value") or sig.get("action") or sig.get("type")
        if isinstance(inner, str) and inner.strip().upper() in ("BUY", "SELL", "HOLD", "BUY_LIMIT", "SELL_LIMIT"):
            result["signal"] = inner.strip().upper()

    # ── حقول الأسعار: entry/stop_loss/tp/tp1/tp2/tp3 ──
    price_fields = ["entry", "stop_loss", "sl", "tp", "tp1", "tp2", "tp3",
                     "take_profit", "take_profit_1", "take_profit_2", "take_profit_3"]
    for field in price_fields:
        val = result.get(field)
        if val is None:
            continue
        if isinstance(val, dict):
            val = val.get("price") or val.get("value")
        if isinstance(val, str):
            cleaned = val.replace("$", "").replace(",", "").strip()
            try:
                val = float(cleaned)
            except ValueError:
                val = None
        if val is not None:
            try:
                result[field] = float(val)
            except (ValueError, TypeError):
                pass

    return result


# ══════════════════════════════════════════════════════════════════
#  MULTI-PASS PIPELINE SCHEMAS - مخرجات كل مرحلة صغيرة وقصيرة عمداً
# ══════════════════════════════════════════════════════════════════
# ⚠️ هذه مخرجات ملخّصة قصيرة تُمرَّر كمُدخل نصي بسيط للمرحلة التالية
# (وليس بيانات خام ضخمة) - هذا هو جوهر الحل لمشكلة "Lost in the
# Middle": كل مرحلة تشتغل على نص أصغر وأقرب لبداية سياقها، بدل دستور
# ضخم واحد. راجع knowledge_sections.py لتوضيح كامل للمشكلة والحل.

def get_stage1_schema():
    """مرحلة 1: النظرة الشمولية - فقط الصورة الكبيرة، لا أرقام دقيقة بعد"""
    return {
        "type": "OBJECT",
        "properties": {
            "visual_silhouette": {
                "type": "STRING",
                "description": "الشكل العام الكامل للشارت (خط واحد متجاهل الفتائل)",
            },
            "price_position_in_shape": {
                "type": "STRING",
                "enum": ["UPPER_THIRD", "MIDDLE_THIRD", "LOWER_THIRD", "AT_INFLECTION_POINT"],
            },
            "shape_character_changed": {
                "type": "BOOLEAN",
                "description": "هل تغيّر طابع الشكل بمنتصف النافذة (مثلاً من ترند لنطاق)؟",
            },
            "shape_change_location": {
                "type": "STRING",
                "description": "وين بالضبط تغيّر الطابع (رقم شمعة تقريبي)، أو 'لا يوجد تغيّر' ",
            },
            "preliminary_bias": {
                "type": "STRING",
                "enum": ["BULLISH", "BEARISH", "NEUTRAL"],
                "description": "انطباع أولي بحت من الصورة الكبيرة فقط - سيُتحقق منه لاحقاً بالأرقام",
            },
        },
        "required": [
            "visual_silhouette", "price_position_in_shape",
            "shape_character_changed", "preliminary_bias",
        ],
    }


def get_stage2_schema():
    """مرحلة 2: الهيكل السعري - Swings, BOS, last candle accuracy"""
    return {
        "type": "OBJECT",
        "properties": {
            "last_candle_report": _LAST_CANDLE_REPORT,
            "market_structure": {
                "type": "STRING",
                "enum": ["HH_HL_BULLISH", "LH_LL_BEARISH", "RANGING_NO_CLEAR_STRUCTURE"],
            },
            "most_recent_bos_direction": {
                "type": "STRING",
                "enum": ["UP", "DOWN", "NONE_FOUND"],
            },
            "bos_candle_index_from_end": {
                "type": "INTEGER",
                "description": "رقم الشمعة (سالب) التي كسرت آخر BOS - امسح من -1 لـ-15 فعلياً قبل الإجابة",
            },
            "bos_broken_level": {"type": "NUMBER"},
            "bos_held_or_failed": {
                "type": "STRING",
                "enum": ["HELD_GENUINE_BREAK", "FAILED_RETRACED_BACK", "TOO_RECENT_TO_TELL"],
            },
            "key_structure_summary": {
                "type": "STRING",
                "description": "ملخص قصير (2-3 جمل) للهيكل السعري فقط - يُمرَّر كمُدخل للمرحلة التالية",
            },
        },
        "required": [
            "last_candle_report", "market_structure", "most_recent_bos_direction",
            "bos_held_or_failed", "key_structure_summary",
        ],
    }


def get_stage3_schema():
    """مرحلة 3: المناطق (OB/FVG/Liquidity) + الأصالة"""
    return {
        "type": "OBJECT",
        "properties": {
            "smc_zones_found": {
                "type": "OBJECT",
                "properties": {
                    "order_blocks": {"type": "ARRAY", "items": _SMC_ZONE_ITEM},
                    "fvg": {"type": "ARRAY", "items": _SMC_ZONE_ITEM},
                    "liquidity": {"type": "ARRAY", "items": _SMC_ZONE_ITEM},
                },
            },
            "trapped_trader_evidence_found": {
                "type": "BOOLEAN",
                "description": "هل يوجد دليل واضح (سحب سيولة + displacement) لمتداولين محاصرين؟",
            },
            "authenticity_concerns": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "أي علامات فخ/زيف مكتشفة (fake sweep, wash trading, إلخ) - قائمة فارغة إن لم يوجد",
            },
            "zones_summary": {
                "type": "STRING",
                "description": "ملخص قصير للمناطق المهمة فقط - يُمرَّر للمرحلة التالية",
            },
        },
        "required": [
            "smc_zones_found", "trapped_trader_evidence_found",
            "authenticity_concerns", "zones_summary",
        ],
    }


def get_stage4_schema():
    """مرحلة 4: نموذج الدخول والمخاطرة"""
    return {
        "type": "OBJECT",
        "properties": {
            "entry_model": {"type": "STRING"},
            "entry": {"type": "NUMBER"},
            "stop_loss": {"type": "NUMBER"},
            "tp": {"type": "NUMBER"},
            "rr": {"type": "STRING"},
            "entry_summary": {
                "type": "STRING",
                "description": "ملخص قصير لمنطق الدخول - يُمرَّر للمرحلة الأخيرة",
            },
        },
        "required": ["entry_model", "entry_summary"],
    }


def get_stage5_schema(is_backtest=False):
    """مرحلة 5: التركيب النهائي - تجمع ملخصات كل المراحل (نصوص قصيرة، لا بيانات خام) وتصدر القرار"""
    signal_enum = ["BUY", "SELL"] if is_backtest else ["BUY", "SELL", "HOLD"]
    schema = {
        "type": "OBJECT",
        "properties": {
            "narrative": {"type": "STRING"},
            "archetype": {"type": "STRING"},
            "bos_reconciliation": {"type": "STRING"},
            "bias": {"type": "STRING", "enum": ["BULLISH", "BEARISH", "NEUTRAL"]},
            "signal": {"type": "STRING", "enum": signal_enum},
            "entry": _PRICE_FIELD,
            "stop_loss": _PRICE_FIELD,
            "tp": _PRICE_FIELD,
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
            "narrative", "archetype", "bias", "signal", "confidence",
            "reasoning", "market_regime", "bos_reconciliation",
        ],
    }
    if is_backtest:
        schema["required"].extend(["entry", "stop_loss", "tp", "rr"])
    return schema

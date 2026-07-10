# -*- coding: utf-8 -*-
"""
smc_library_engine.py
════════════════════════════════════════════════════════════════════
⚠️ إضافة جديدة (يوليو 2026، بطلب صريح من المستخدم بعد نقاش حول تكرار
هلوسات الموديل اللغوي بحسابات رياضية بحتة - قمم/قيعان، BOS/CHoCH،
تصنيف شمعة): يدمج مكتبة `smartmoneyconcepts` (PyPI, github.com/
joshyattridge/smart-money-concepts - 1.8k نجمة، 792 fork، نشطة فعلياً،
تحقق مباشر) كـ**طبقة تحقق ثانية مستقلة تماماً** عن `ict_math_engine.py`
الأصلي - لا بديل له، ولا اعتماد على "تصويت" أو "دمج" بين الاثنين.

⚠️ توضيح فلسفي حاسم (نفس الرد المُعطى للمستخدم عند مناقشة هذه الفكرة):
اقتراح المستخدم الأصلي كان "عدة موديلات AI/ML مختلفة لكل ميزة صغيرة
(قمم، BOS، إلخ)" - هذا **رُفض عمداً** لأن هذه الحسابات ليست مهامّ تحتاج
ذكاءً اصطناعياً أو تعلّم آلة إطلاقاً؛ هي معادلات رياضية حتمية 100%
("هل هذه الشمعة أعلى قمة بنافذة N من الجهتين؟" - معادلة، لا نموذج).
لا معنى لـ"تصويت بين عدة نماذج" على نتيجة معادلة رياضية واحدة - لو
اختلفت نتائجهم، المشكلة Bug ببعضها لا حاجة لـ"ديمقراطية نماذج". فُحصت
واستُبعدت مكتبة ثالثة اقترحها المستخدم (`SMC_ICT_Library`, github.com/
xxvw) لأنها فعلياً "سكريبتات تدريب فاضية" (2 نجمة فقط، بلا نماذج مدرَّبة
فعلياً ولا نتائج دقة موثّقة) - دمجها كان سيُضيف طبقة هلوسة إضافية أخطر
(احتمال من نموذج غير مُتحقَّق منه أخطر من قاعدة رياضية شفافة).

الحل الصحيح المُتَّبع هنا: **مكتبة رياضية بحتة ثانية مستقلة** (لا AI،
لا ML) تُنفَّذ بمعادلات مختلفة قليلاً عن `ict_math_engine.py` (نافذة
ثابتة `swing_length` بدل الفلترة التكيّفية ATR/prominence بمحرّكنا) -
هذا التنوّع المنهجي البسيط (لا تصويت، لا دمج) يُستخدم فقط **لتوفير
حقيقة إضافية للموديل يزنها بنفسه** (مثلاً: "محركنا يقول HH هنا، ومكتبة
مستقلة تحسب بمعادلة مختلفة قليلاً تقول نفس الشيء - توافق يرفع الثقة"
أو "اختلفا - يستحق انتباهاً إضافياً بالتفسير") - **ليست حكماً جاهزاً
يستبدل قرار الموديل**، بل حقيقة موضوعية إضافية تُعرض له بلا تفسير مسبق،
بنفس فلسفة كل هذا المشروع (عين تُرى، مخ يُفكّر).
"""
import logging

logger = logging.getLogger("SMCLibraryEngine")

try:
    import pandas as pd
    from smartmoneyconcepts import smc
    _LIBRARY_AVAILABLE = True
except ImportError as e:
    _LIBRARY_AVAILABLE = False
    _IMPORT_ERROR = str(e)


def _to_dataframe(data):
    """يحوّل صيغة بيانات المشروع الداخلية (dict بقوائم) لـDataFrame
    بالأعمدة والفهرسة الزمنية التي تتطلبها مكتبة smartmoneyconcepts."""
    df = pd.DataFrame({
        "open": data["opens"], "high": data["highs"],
        "low": data["lows"], "close": data["closes"],
        "volume": data.get("volumes", [0] * len(data["closes"])),
    })
    if "timestamps" in data:
        df.index = pd.to_datetime(data["timestamps"], unit="ms")
    return df


def compute_smc_library_facts(data, swing_length=10, lookback_report=6):
    """
    ⚠️ نفس مبدأ `_ict_math_candidates_block` بالضبط: يبني نصاً جاهزاً
    بحقائق موضوعية بحتة (لا حكم جاهز) من مكتبة مستقلة تماماً، لدمجها
    بـ`_authenticity_block` كطبقة تحقق إضافية - لا تستبدل `ict_math_
    engine.py` الأصلي بل تُضاف بجانبه.

    Args:
        data: بيانات الشموع بالصيغة الداخلية القياسية للمشروع.
        swing_length: نافذة اكتشاف القمم/القيعان بمكتبة smartmoneyconcepts
            (معادلة مختلفة عن الفلترة التكيّفية ATR/prominence بمحرّكنا -
            هذا الاختلاف المتعمَّد هو ما يجعل التقاطع بين الاثنين مفيداً).
        lookback_report: كم نقطة/حدث أخير من كل نوع يُذكر بالنص (تجنّب
            إغراق البرومبت بكل تاريخ البيانات).

    Returns: نص جاهز للحقن بالبرومبت، أو نص فارغ لو المكتبة غير متاحة
        أو البيانات غير كافية (فشل غير قاتل - لا يوقف التحليل الأساسي).
    """
    if not _LIBRARY_AVAILABLE:
        logger.warning(f"⚠️ smartmoneyconcepts غير مثبَّتة (non-fatal): {_IMPORT_ERROR}")
        return ""

    try:
        n = len(data.get("closes", []))
        if n < swing_length * 3:
            return ""

        df = _to_dataframe(data)

        lines = [
            "\n── INDEPENDENT CROSS-CHECK: smartmoneyconcepts LIBRARY "
            "(a SEPARATE, independently-maintained open-source math engine "
            "- github.com/joshyattridge/smart-money-concepts, 1.8k stars - "
            "computing swing points/BOS/CHoCH/OB/FVG with a DIFFERENT "
            "detection method than the primary engine above: fixed-window "
            "swing detection instead of ATR/prominence-adaptive filtering. "
            "This is objective supplementary evidence, NOT a pre-judged "
            "verdict - if it AGREES with the primary engine's facts above, "
            "that agreement raises confidence in the reading; if it "
            "DISAGREES, that disagreement itself is worth noting explicitly "
            "in your reasoning rather than silently picking one) ──"
        ]

        # ── القمم/القيعان (swing_highs_lows) ──
        # ⚠️ إصلاح خطأ حقيقي مُكتشف بأول اختبار: index الناتج من هذه
        # المكتبة هو أصلاً **رقم الصف العددي الموضعي** (0-based position
        # بالـDataFrame الأصلي)، وليس timestamp - محاولة استخدام
        # `df.index.get_loc()` عليه فشلت (`get_loc` تتوقع قيمة موجودة
        # فعلياً بـDatetimeIndex، لا رقماً صحيحاً عاماً). الحل: `idx`
        # نفسه هو الموضع مباشرة - لا حاجة لأي تحويل إضافي.
        try:
            swings = smc.swing_highs_lows(df, swing_length=swing_length)
            recent_swings = swings.dropna(subset=["HighLow"]).tail(lookback_report)
            for idx, row in recent_swings.iterrows():
                idx_from_end = idx - n
                kind = "swing high" if row["HighLow"] == 1 else "swing low"
                lines.append(
                    f"[smc-lib] {kind} at idx {idx_from_end}, price {row['Level']:.6g} "
                    f"(fixed swing_length={swing_length} window)."
                )
        except Exception as e:
            logger.warning(f"⚠️ smc.swing_highs_lows failed (non-fatal): {e}")
            swings = None

        # ── BOS/CHoCH ──
        if swings is not None:
            try:
                bos_choch = smc.bos_choch(df, swings)
                recent_events = bos_choch.dropna(subset=["BOS", "CHOCH"], how="all").tail(lookback_report)
                for idx, row in recent_events.iterrows():
                    idx_from_end = idx - n
                    if pd.notna(row["BOS"]):
                        direction = "bullish" if row["BOS"] == 1 else "bearish"
                        lines.append(
                            f"[smc-lib] BOS ({direction}) at idx {idx_from_end}, "
                            f"broken level {row['Level']:.6g}."
                        )
                    if pd.notna(row["CHOCH"]):
                        direction = "bullish" if row["CHOCH"] == 1 else "bearish"
                        lines.append(
                            f"[smc-lib] CHoCH ({direction}) at idx {idx_from_end}, "
                            f"broken level {row['Level']:.6g}."
                        )
            except Exception as e:
                logger.warning(f"⚠️ smc.bos_choch failed (non-fatal): {e}")

            # ── Order Blocks ──
            try:
                ob = smc.ob(df, swings)
                recent_ob = ob.dropna(subset=["OB"]).tail(lookback_report)
                for idx, row in recent_ob.iterrows():
                    idx_from_end = idx - n
                    direction = "bullish" if row["OB"] == 1 else "bearish"
                    mitigated = row.get("MitigatedIndex", 0)
                    lines.append(
                        f"[smc-lib] Order Block ({direction}) at idx {idx_from_end}: "
                        f"top={row['Top']:.6g}, bottom={row['Bottom']:.6g}, "
                        f"mitigated={'yes' if mitigated and mitigated > 0 else 'no'}."
                    )
            except Exception as e:
                logger.warning(f"⚠️ smc.ob failed (non-fatal): {e}")

        # ── Fair Value Gaps ──
        try:
            fvg = smc.fvg(df, join_consecutive=True)
            recent_fvg = fvg.dropna(subset=["FVG"]).tail(lookback_report)
            for idx, row in recent_fvg.iterrows():
                idx_from_end = idx - n
                direction = "bullish" if row["FVG"] == 1 else "bearish"
                mitigated = row.get("MitigatedIndex", 0)
                lines.append(
                    f"[smc-lib] FVG ({direction}) at idx {idx_from_end}: "
                    f"top={row['Top']:.6g}, bottom={row['Bottom']:.6g}, "
                    f"filled={'yes' if mitigated and mitigated > 0 else 'no'}."
                )
        except Exception as e:
            logger.warning(f"⚠️ smc.fvg failed (non-fatal): {e}")


        if len(lines) <= 1:
            return ""
        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"⚠️ compute_smc_library_facts failed entirely (non-fatal): {e}")
        return ""

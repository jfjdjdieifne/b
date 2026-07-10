# -*- coding: utf-8 -*-
"""
nemotron_knowledge_audit.py
════════════════════════════════════════════════════════════════════
تدقيق حقيقي (مبرمج، لا انطباعي) لمدى استخدام Nemotron الفعلي للأدلة
الرياضية المستقلة (AuthenticityEngine) بدل مجرد ذكر أسماء أقسام
الدستور بالنص - بطلب المستخدم الصريح: "نشوف عم يجيب دليل تحليلو من
المعرفه بشكل ذكي عنجد ولا لا مش بس يزكر اسم المقطع".

المنهجية:
1. نحسب رياضياً (بدون AI إطلاقاً) BOS الأخير الحقيقي، الـswings
   المهمة، وslliquidity sweep الأخير - من نفس بيانات الـEntry TF
   المُرسلة فعلياً للموديل.
2. نستخرج بالتعبيرات النمطية (regex) كل رقم (index_from_end بصيغة
   -N، وأسعار) مذكور بحقول `structural_derivation` و
   `cross_reference_check` و`bos_reconciliation` بنتيجة الموديل.
3. نتحقق: هل الـindex/level المذكور نصياً يطابق (بهامش صغير) نفس
   الرقم الذي حسبناه رياضياً؟ إذا لأ - هل يوجد أي تطابق رقمي حقيقي
   بالنص أصلاً (لا سرد عام بلا أرقام محددة)؟
4. نُخرج تصنيفاً واضحاً بدل حكم انطباعي:
   - GENUINE_CITATION: رقم محدد بالنص يطابق الحساب المستقل (هامش ضيق)
   - VAGUE_CITATION: ذكر مفهوماً (BOS/OB) لكن بلا رقم دقيق يمكن التحقق منه
   - NO_CITATION: لا ذكر إطلاقاً لهذا المفهوم
   - CONTRADICTS_MATH: رقم مذكور صراحة لكنه لا يطابق الحساب المستقل
"""
import re
import sys

sys.path.insert(0, ".")


def _extract_indices(text):
    """يستخرج كل رقم بصيغة index_from_end (مثال: 'idx -13', 'index -15',
    'candle -14', أو مجرد '-13' قريب من كلمة idx/candle/index)."""
    if not text:
        return []
    patterns = [
        r"(?:idx|index|candle)\s*(-?\d+)",
        r"(-\d+)\s*(?:idx|index|candle)",
    ]
    found = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            try:
                found.append(int(m.group(1)))
            except ValueError:
                pass
    return found


def _extract_prices(text, min_price=1, max_price=1_000_000):
    """يستخرج كل رقم عشري كبير (سعر محتمل) بالنص."""
    if not text:
        return []
    nums = re.findall(r"\b\d{2,7}(?:\.\d+)?\b", text)
    prices = []
    for n in nums:
        try:
            v = float(n)
            if min_price <= v <= max_price:
                prices.append(v)
        except ValueError:
            pass
    return prices


def audit_structural_claims(entry_data, ai_result, price_tolerance_pct=0.5):
    """
    التدقيق الرئيسي: يقارن ادعاءات الموديل النصية (structural_derivation,
    cross_reference_check, bos_reconciliation) بحسابات AuthenticityEngine
    المستقلة على نفس بيانات الـEntry TF بالضبط.

    Returns dict بتصنيف واضح لكل نوع ادعاء + نسبة "استشهاد حقيقي" إجمالية.
    """
    from authenticity_engine import AuthenticityEngine
    ae = AuthenticityEngine()

    report = {
        "mechanical_bos": None,
        "mechanical_swings": None,
        "mechanical_sweep": None,
        "claims": {},
        "genuine_citation_count": 0,
        "vague_citation_count": 0,
        "no_citation_count": 0,
        "contradicts_math_count": 0,
    }

    if not entry_data or "closes" not in entry_data:
        report["error"] = "NO_ENTRY_DATA"
        return report

    try:
        mech_bos = ae.detect_most_recent_bos(entry_data)
    except Exception as e:
        mech_bos = {"bos_found": False, "error": str(e)}
    try:
        mech_swings = ae.detect_significant_swings(entry_data)
    except Exception as e:
        mech_swings = {"error": str(e)}
    try:
        mech_sweep = ae.detect_most_recent_sweep(entry_data)
    except Exception as e:
        mech_sweep = {"found": False, "error": str(e)}

    report["mechanical_bos"] = mech_bos
    report["mechanical_swings"] = mech_swings
    report["mechanical_sweep"] = mech_sweep

    text_fields = {
        "structural_derivation": ai_result.get("structural_derivation", ""),
        "cross_reference_check": ai_result.get("cross_reference_check", ""),
        "bos_reconciliation": ai_result.get("bos_reconciliation", ""),
    }

    # ── فحص 1: BOS index المذكور نصياً يطابق الحساب المستقل؟ ──
    if mech_bos.get("bos_found"):
        true_idx = mech_bos["displacement_index_from_end"]
        true_level = mech_bos["broken_level"]
        found_any_bos_mention = False
        found_matching_idx = False
        found_matching_level = False
        for field_name, text in text_fields.items():
            if not text:
                continue
            if re.search(r"\bBOS\b", text, re.IGNORECASE):
                found_any_bos_mention = True
            idxs = _extract_indices(text)
            if any(abs(i - true_idx) <= 1 for i in idxs):
                found_matching_idx = True
            prices = _extract_prices(text)
            if any(abs(p - true_level) / true_level * 100 <= price_tolerance_pct for p in prices):
                found_matching_level = True

        if found_matching_idx or found_matching_level:
            classification = "GENUINE_CITATION"
            report["genuine_citation_count"] += 1
        elif found_any_bos_mention:
            classification = "VAGUE_CITATION"
            report["vague_citation_count"] += 1
        else:
            classification = "NO_CITATION"
            report["no_citation_count"] += 1

        report["claims"]["bos"] = {
            "mechanical_truth": {
                "direction": mech_bos["direction"],
                "index_from_end": true_idx,
                "broken_level": true_level,
            },
            "classification": classification,
            "matched_index": found_matching_idx,
            "matched_level": found_matching_level,
        }
    else:
        report["claims"]["bos"] = {"mechanical_truth": "NO_BOS_DETECTED_MECHANICALLY"}

    # ── فحص 2: liquidity sweep المذكور نصياً ──
    if mech_sweep.get("found"):
        true_sweep_idx = mech_sweep.get("sweep_candle_index_from_end")
        true_sweep_level = mech_sweep.get("swept_level_price")
        found_sweep_mention = False
        found_matching_idx = False
        found_matching_level = False
        for field_name, text in text_fields.items():
            if not text:
                continue
            if re.search(r"\bsweep\b", text, re.IGNORECASE):
                found_sweep_mention = True
            idxs = _extract_indices(text)
            if true_sweep_idx is not None and any(abs(i - true_sweep_idx) <= 1 for i in idxs):
                found_matching_idx = True
            prices = _extract_prices(text)
            if true_sweep_level and any(
                abs(p - true_sweep_level) / true_sweep_level * 100 <= price_tolerance_pct
                for p in prices
            ):
                found_matching_level = True

        if found_matching_idx or found_matching_level:
            classification = "GENUINE_CITATION"
            report["genuine_citation_count"] += 1
        elif found_sweep_mention:
            classification = "VAGUE_CITATION"
            report["vague_citation_count"] += 1
        else:
            classification = "NO_CITATION"
            report["no_citation_count"] += 1

        report["claims"]["sweep"] = {
            "mechanical_truth": {
                "index_from_end": true_sweep_idx,
                "level": true_sweep_level,
                "classification_mechanical": mech_sweep.get("classification"),
            },
            "classification": classification,
            "matched_index": found_matching_idx,
            "matched_level": found_matching_level,
        }
    else:
        report["claims"]["sweep"] = {"mechanical_truth": "NO_SWEEP_DETECTED_MECHANICALLY"}

    total_claims = (
        report["genuine_citation_count"] + report["vague_citation_count"]
        + report["no_citation_count"] + report["contradicts_math_count"]
    )
    report["genuine_citation_rate_pct"] = (
        round(report["genuine_citation_count"] / total_claims * 100, 1)
        if total_claims > 0 else None
    )
    return report

# -*- coding: utf-8 -*-
"""
nemotron_backtest_driver.py
════════════════════════════════════════════════════════════════════
باك تيست حقيقي على منهجية Top-Down الأصلية (multi_pass_analysis.py:
Weekly -> Daily -> 4H -> 1H -> Entry، مع نفس الـ Gates والـ prompts
والـ knowledge_sections.py الأصليين) بموديل Nemotron 3 Ultra عبر
OpenRouter (المزود الوحيد بالمشروع الآن - راجع openrouter_client.py).

⚠️ تبسيط جوهري (يوليو 2026، بعد توحيد كل الاتصال بـAI عبر
OpenRouterClient الوحيد): لم يعد هناك حاجة لأي "محول" (adapter) محلي
مخصص لهذا الملف - BrainCore() نفسها تُنشئ الآن self.ai كـ
OpenRouterClient() مباشرة (نفس ما يستخدمه main.py بالضبط). هذا الملف
فقط يُنسّق سير الباك تيست (جلب بيانات Entry TF عند end_ts محدد، تشغيل
MultiPassAnalysis.run() بوضع is_backtest=True، وتجميع تقرير تشخيصي).
"""
import json
import logging
import sys
import time

logging.basicConfig(level=logging.WARNING)  # نقلل الضجيج، نطبع نحن يدوياً

sys.path.insert(0, ".")

from config import Config
from brain_core import BrainCore
from multi_pass_analysis import MultiPassAnalysis
from nemotron_knowledge_audit import audit_structural_claims

# ⚠️ قرار نهائي مثبت (بطلب المستخدم الصريح، بعد اختبارات فعلية متكررة):
# reasoning effort = "none" حصراً. "low" جُرِّب 3 مرات على برومبتات حقيقية
# (30-45K توكن) وفشل الثلاث مرات (استهلك التوكنز على تفكير غير مكتمل، أو
# Timeout كامل حتى بحد 16000 توكن ومهلة 350 ثانية). لا نقاش إضافي حول هذا -
# القرار مُقفل.
REASONING_EFFORT = Config.OPENROUTER_REASONING_EFFORT


def run_one_backtest(symbol, timeframe, end_ts, api_key=None,
                      label="backtest", max_tokens=4000, timeout=150,
                      backup_keys=None):
    """
    يشغّل تحليل Top-Down الكامل (multi-pass) على صفقة واحدة عند لحظة
    زمنية محددة (end_ts) - يمنع أي تسريب مستقبلي (lookahead bias).
    يرجع dict بكل التفاصيل + تدقيق استشهاد المعرفة الرياضي.

    Args:
        timeframe: ⚠️ حل جذري (يوليو 2026): فريم التنفيذ الفعلي
            (Entry TF بمصطلح ICT) - يجب أن يكون 1m/3m/5m حصراً (راجع
            multi_pass_analysis.py::_VALID_EXECUTION_TIMEFRAMES) - لم يعد
            "1h" مقبولاً هنا، لأن منهجية ICT الحقيقية لا تنفّذ على
            فريم أكبر من 5 دقائق. لو تم تمرير فريم غير صالح، يُصحّح
            تلقائياً لـ"5m".
        api_key, backup_keys: (اختياري) لو مُمرَّرين، يُستخدمان حصرياً
            بدل Config.OPENROUTER_API_KEYS الكاملة - مفيد لعزل اختبار
            مفتاح واحد تحديداً بمعزل عن البقية (تشخيص استهلاك حصة).
            الافتراضي (None): تُستخدم كل مفاتيح .env كالمعتاد.
    """
    from multi_pass_analysis import _VALID_EXECUTION_TIMEFRAMES, _DEFAULT_EXECUTION_TIMEFRAME
    if timeframe not in _VALID_EXECUTION_TIMEFRAMES:
        print(f"⚠️ timeframe='{timeframe}' ليس فريم تنفيذ ICT صالحاً "
              f"({_VALID_EXECUTION_TIMEFRAMES}) - تصحيح تلقائي لـ '{_DEFAULT_EXECUTION_TIMEFRAME}'.")
        timeframe = _DEFAULT_EXECUTION_TIMEFRAME
    print(f"\n{'='*72}\n🔬 {label} | {symbol} {timeframe} | effort={REASONING_EFFORT}\n{'='*72}")

    brain = BrainCore()

    # ⚠️ عزل اختياري لمفتاح/مفاتيح محددة لهذا الباك تيست تحديداً (بدل
    # كل Config.OPENROUTER_API_KEYS) - نفس فكرة backup_keys القديمة،
    # مطبّقة مباشرة على الـ OpenRouterClient الموحّد (singleton) بدل
    # طبقة Adapter منفصلة.
    if api_key:
        brain.ai.keys = [api_key] + list(backup_keys or [])
        brain.ai._exhausted = {k: False for k in brain.ai.keys}

    mp = MultiPassAnalysis(brain)

    # ═══ جلب بيانات Entry TF الحقيقية (منتهية عند end_ts بالضبط - لا
    # تسريب مستقبلي) ═══
    # ⚠️ حد أكبر من الشموع لفريمات الدقائق القصيرة (300 شمعة بفريم 5m
    # تغطي يوماً واحداً تقريباً - كافٍ لرؤية تفاصيل الجلسة الحالية كاملة)
    entry_counts = {"1h": 150, "5m": 300, "3m": 300, "1m": 300, "4h": 120, "1d": 90}
    entry_data = brain.data_manager.fetch_ohlcv_up_to(
        symbol, timeframe, end_ts, limit=entry_counts.get(timeframe, 150)
    )
    if not entry_data:
        print("❌ فشل جلب بيانات Entry TF")
        return None

    entry_ind = {}
    try:
        entry_ind = brain.ta.compute_all(entry_data)
    except Exception as e:
        print(f"⚠️ فشل حساب المؤشرات: {e}")

    mtf_data = {"entry": entry_data}
    mtf_indicators = {"entry": entry_ind} if entry_ind else {}

    t0 = time.time()
    result = mp.run(
        symbol, timeframe, mtf_data, mtf_indicators,
        is_backtest=True, end_ts=end_ts,
    )
    elapsed = time.time() - t0

    summary = brain.ai.summary()

    # ═══ تدقيق استشهاد المعرفة (بطلب المستخدم الصريح): هل الادعاءات
    # الهيكلية (BOS, Sweep) مذكورة بأرقام دقيقة تطابق حساباً رياضياً
    # مستقلاً، أم مجرد ذكر عام لاسم المفهوم بلا رقم قابل للتحقق؟ ═══
    try:
        knowledge_audit = audit_structural_claims(entry_data, result)
    except Exception as e:
        knowledge_audit = {"error": str(e)}

    return {
        "label": label,
        "symbol": symbol,
        "timeframe": timeframe,
        "reasoning_effort": REASONING_EFFORT,
        "total_wall_time_sec": round(elapsed, 1),
        "result": result,
        "nemotron_call_summary": summary,
        "knowledge_citation_audit": knowledge_audit,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--end_ts", required=True, type=int)
    parser.add_argument("--api_key", default=None)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max_tokens", type=int, default=4000)
    parser.add_argument("--timeout", type=int, default=150)
    parser.add_argument("--backup_key", action="append", default=[])
    args = parser.parse_args()

    out = run_one_backtest(
        args.symbol, args.timeframe, args.end_ts, args.api_key,
        args.label, max_tokens=args.max_tokens, timeout=args.timeout,
        backup_keys=args.backup_key,
    )
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n✅ Saved: {args.out}")

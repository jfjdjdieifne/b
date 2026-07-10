# -*- coding: utf-8 -*-
"""
ict_sessions.py - كاشف جلسات ونوافذ زمنية لنماذج ICT الوقتية.

أوقات NQ/ES/Forex في مواد مايكل هي المرجع، أما تطبيقها على كريبتو 24/7
فهو **فرضية تشغيلية للمشروع** تحتاج backtest لكل زوج/منصة، وليس قاعدة
أصلية منشورة من مايكل عن ETH/BTC.
════════════════════════════════════════════════════════════════════
⚠️ لماذا هذا الملف ضروري (اكتشاف جذري، يوليو 2026، بعد بحث عميق موثّق
بمصادر متعددة عن منهجية ICT الحقيقية): "الوقت أهم من السعر" - هذه ليست
مبالغة تسويقية، هذا نص حرفي متكرر بكل مصادر ICT الموثوقة. مايكل لا يدخل
أي صفقة خارج نافذة زمنية محددة (Kill Zone)، بغض النظر عن جودة الإعداد
الفني - لأن المؤسسات (Smart Money) لا تنشط خوارزمياً إلا بساعات معينة.

قبل هذا الملف: كودنا كان يحلل بأي لحظة زمنية بلا تمييز - يعني نفس
منطق "لو الشكل صح، نفّذ"، بغض النظر هل هذه الساعة نشطة مؤسسياً أو لا.
هذا فرق جذري حقيقي عن منهجية ICT الأصلية، وليس تفصيلاً ثانوياً.

⚠️ التكييف للكريبتو (موثّق من عدة مصادر ICT متخصصة بالكريبتو): البيتكوين
والإيثيريوم يتداولان 24/7 بلا "افتتاح لندن" أو "إغلاق نيويورك" حقيقي -
لا وجود لـ"جلسة آسيوية" بمعناها الفوركسي (تجمّع سيولة بنطاق ضيق قبل
افتتاح لندن). الحل المعتمد بمجتمع ICT للكريبتو: استبدال الجلسات
الفوركسية بنوافذ التداخل مع سوق الأسهم الأمريكي (الأكثر سيولة مؤسسية
مرتبطة بالكريبتو عبر NQ/ES) - أهمها نافذة افتتاح نيويورك 08:30-11:00
صباحاً بتوقيت نيويورك (تتوافق تاريخياً مع أعلى حجم تداول واندفاعات
حقيقية على BTC/ETH)، مع نافذة ثانوية بعد الظهر (13:30-16:00 NY).
"""
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


def ts_to_ny(ts_ms):
    """
    يحوّل timestamp (مللي ثانية UTC) لكائن datetime بتوقيت نيويورك -
    يتعامل تلقائياً مع التوقيت الصيفي/الشتوي (DST) عبر zoneinfo (لا حاجة
    لجدول يدوي عرضة للخطأ - المكتبة القياسية بايثون تتعامل مع قواعد DST
    الأمريكية الفعلية تلقائياً، بما فيها تواريخ التحوّل السنوية الدقيقة).
    """
    dt_utc = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=UTC_TZ)
    return dt_utc.astimezone(NY_TZ)


# ══════════════════════════════════════════════════════════════════
#  تعريف الجلسات والنوافذ الزمنية - مُكيَّفة للكريبتو (24/7)
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ ملاحظة صدق منهجي مهمة: هذه الأوقات هي نسخة "مُكيَّفة للكريبتو"
# من جلسات ICT الأصلية (المبنية على فوركس/مؤشرات لها بورصة حقيقية
# بساعات افتتاح/إغلاق). البيتكوين ليس له "افتتاح لندن" حرفي - لكن
# الأبحاث المتعددة (راجع تعليق الملف أعلاه) توثّق أن نفس الساعات
# (تداخل الأسواق الأمريكية والأوروبية تحديداً) لا تزال تُنتج أعلى
# حجم تداول واندفاعات حقيقية على BTC/ETH، لأن نفس المؤسسات (بنوك،
# صناديق) التي تتداول NQ/ES خلال هذه الساعات تتداول أيضاً مشتقات
# الكريبتو بنفس الوقت تقريباً.
#
# كل نافذة: (ساعة_بداية, دقيقة_بداية, ساعة_نهاية, دقيقة_نهاية) بتوقيت NY
SESSIONS = {
    # الجلسة الآسيوية المُكيَّفة (نطاق تجميع سيولة ليلي - النطاق الفعلي
    # يُقاس رياضياً من البيانات، لا يُفترض بحجم ثابت كما بالفوركس)
    "ASIAN_RANGE": (18, 0, 0, 0),          # 18:00 - 00:00 NY (يعبر منتصف الليل)
    "ASIAN_MANIPULATION": (0, 0, 2, 0),     # 00:00 - 02:00 NY
    "LONDON_KILLZONE": (2, 0, 5, 0),        # 02:00 - 05:00 NY (تكييف كريبتو: تداخل أوروبا المبكر)
    "PRE_NY": (5, 0, 8, 30),                # 05:00 - 08:30 NY
    "NY_AM_KILLZONE": (8, 30, 11, 0),       # 08:30 - 11:00 NY (⭐ الأهم - تداخل NQ/ES)
    "NY_LUNCH_DEAD_ZONE": (11, 0, 13, 30),  # 11:00 - 13:30 NY (تجنّب - سيولة منخفضة موثّقة)
    "NY_PM_KILLZONE": (13, 30, 16, 0),      # 13:30 - 16:00 NY (ثانوية)
    "AFTER_HOURS": (16, 0, 18, 0),          # 16:00 - 18:00 NY (انتقالي)
}

# نوافذ "Silver Bullet" (ساعة واحدة محددة بدقة، ثلاث مرات باليوم -
# النسخة الأصلية لمؤشرات/فوركس؛ نطبّقها بالكريبتو كنوافذ تنفيذ
# مفضّلة إضافية ضمن Kill Zones الأوسع أعلاه، لا كبديل عنها)
SILVER_BULLET_WINDOWS = [
    (3, 0, 4, 0),    # London Silver Bullet
    (10, 0, 11, 0),  # NY AM Silver Bullet
    (14, 0, 15, 0),  # NY PM Silver Bullet
]

# نوافذ التنفيذ للنماذج الوقتية التي يطبقها هذا المشروع. الخروج عنها
# يجعل النموذج الحالي WAIT_CONFIRMATION؛ لا ندّعي أنها تحظر كل أسلوب
# تداول ممكن أو أنها تثبت نشاطاً مؤسسياً في الكريبتو بذاتها.
EXECUTABLE_SESSIONS = {
    "LONDON_KILLZONE", "NY_AM_KILLZONE", "NY_PM_KILLZONE",
}


def _minutes_since_midnight(dt):
    return dt.hour * 60 + dt.minute


def classify_session(ts_ms):
    """
    يصنّف أي timestamp لجلسته الزمنية (بتوقيت نيويورك)، مع تمييز صريح
    هل هي "نافذة تنفيذ نشطة" (Kill Zone) أو لا.

    Returns dict:
        {
            "ny_time": "2026-04-14 08:45 NY",
            "session": "NY_AM_KILLZONE",
            "is_executable_window": True,
            "in_silver_bullet": True/False,
            "silver_bullet_name": str أو None,
        }
    """
    dt_ny = ts_to_ny(ts_ms)
    minutes = _minutes_since_midnight(dt_ny)

    session_name = "UNKNOWN"
    for name, (h1, m1, h2, m2) in SESSIONS.items():
        start_min = h1 * 60 + m1
        end_min = h2 * 60 + m2
        if start_min > end_min:
            # نافذة تعبر منتصف الليل (مثل ASIAN_RANGE: 18:00 -> 00:00)
            if minutes >= start_min or minutes < end_min:
                session_name = name
                break
        else:
            if start_min <= minutes < end_min:
                session_name = name
                break

    in_sb = False
    sb_name = None
    for i, (h1, m1, h2, m2) in enumerate(SILVER_BULLET_WINDOWS):
        start_min = h1 * 60 + m1
        end_min = h2 * 60 + m2
        if start_min <= minutes < end_min:
            in_sb = True
            sb_name = ["LONDON_SB", "NY_AM_SB", "NY_PM_SB"][i]
            break

    return {
        "ny_time": dt_ny.strftime("%Y-%m-%d %H:%M NY (%a)"),
        "session": session_name,
        "is_executable_window": session_name in EXECUTABLE_SESSIONS,
        "in_silver_bullet": in_sb,
        "silver_bullet_name": sb_name,
    }


def compute_overnight_range(data, current_ts_ms):
    """
    ⚠️ حل جذري خاص بالكريبتو (موثّق بحثياً - راجع تعليق أعلى الملف):
    البيتكوين لا يملك "Asian Range" حقيقياً بمعنى فوركسي (نطاق ضيق
    18:00-00:00 NY). البديل المعتمد: "النطاق الليلي" (Overnight Range)
    من منتصف الليل (00:00 NY) حتى افتتاح نيويورك (08:30 NY) لنفس اليوم
    - يُحسب طازجاً كل يوم من بيانات الشموع الفعلية (لا رقم افتراضي).

    Args:
        data: dict OHLCV (يجب أن يحوي "timestamps","highs","lows")
        current_ts_ms: اللحظة الحالية (لتحديد "اليوم" المطلوب حسابه)

    Returns dict: {"range_high", "range_low", "range_start_ts",
                    "range_end_ts", "found": bool}
    """
    dt_ny = ts_to_ny(current_ts_ms)
    day_start_ny = dt_ny.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end_ny = day_start_ny.replace(hour=8, minute=30)

    timestamps = data.get("timestamps", [])
    highs = data.get("highs", [])
    lows = data.get("lows", [])
    if not timestamps:
        return {"found": False}

    range_high, range_low = None, None
    range_start_ts, range_end_ts = None, None
    for i, ts in enumerate(timestamps):
        dt = ts_to_ny(ts)
        if day_start_ny <= dt < window_end_ny:
            h, l = highs[i], lows[i]
            if range_high is None or h > range_high:
                range_high = h
            if range_low is None or l < range_low:
                range_low = l
            if range_start_ts is None:
                range_start_ts = ts
            range_end_ts = ts

    if range_high is None:
        return {"found": False}

    return {
        "found": True,
        "range_high": range_high,
        "range_low": range_low,
        "range_start_ts": range_start_ts,
        "range_end_ts": range_end_ts,
        "range_start_ny": ts_to_ny(range_start_ts).strftime("%Y-%m-%d %H:%M"),
        "range_end_ny": ts_to_ny(range_end_ts).strftime("%Y-%m-%d %H:%M"),
    }


def session_prose(ts_ms):
    """نص جاهز يُحقن مباشرة بالبرومبت - يشرح الوضع الزمني الحالي للنموذج
    بصيغة عربية-إنجليزية مختلطة واضحة، بلا حاجة لأي حساب من طرفه."""
    info = classify_session(ts_ms)
    lines = [
        f"CURRENT TIME (New York, ICT reference clock): {info['ny_time']}",
        f"Session: {info['session']}",
    ]
    if info["is_executable_window"]:
        lines.append(
            "\u2705 INSIDE THIS MODEL'S EXECUTION WINDOW. Timing is eligible, "
            "but price/structure/displacement/FVG checks must still pass; the "
            "clock alone is never a signal."
        )
    else:
        lines.append(
            "\u26d4 OUTSIDE THIS MODEL'S EXECUTION WINDOW (session=" + info["session"] + "). "
            "For the time-based setup implemented here, keep it as "
            "WAIT_CONFIRMATION/HOLD. Do not pre-position a limit while timing "
            "or structural conditions remain pending. This is a model rule, "
            "not proof that all crypto price action outside the window is dead."
        )
    if info["in_silver_bullet"]:
        lines.append(
            f"\u2b50 Currently inside the configured Silver Bullet window "
            f"({info['silver_bullet_name']}). This only enables the time gate; "
            "it does not prove an edge without the remaining setup and a "
            "proper out-of-sample test on this instrument."
        )
    return "\n".join(lines)

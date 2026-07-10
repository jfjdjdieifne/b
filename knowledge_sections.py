# -*- coding: utf-8 -*-
"""
knowledge_sections - تقسيم ملف الدستور الضخم لمقاطع محددة، قابلة
للحقن الانتقائي بكل مرحلة من مراحل التحليل المتعدد (Multi-Pass Pipeline)
════════════════════════════════════════════════════════════════════
لماذا هذا الملف موجود:
  دستور المشروع صار ~700 ألف حرف / ~26 قسم بطلب واحد ضخم. هذا بالضبط
  السيناريو المثالي لمشكلة أكاديمية معروفة بالنماذج اللغوية اسمها
  "Lost in the Middle" (Liu et al. 2023) - النموذج ينتبه جيداً
  للمعلومات في بداية ونهاية أي سياق طويل، لكن انتباهه يضعف فعلياً
  للمعلومات "المدفونة" بمنتصف النص، حتى لو كانت القاعدة موجودة حرفياً
  بالدستور. هذا يفسر جزئياً أخطاء حقيقية اكتُشفت بالباك تيست (مثال:
  قسم [BOS_OB_DIRECTIONAL_INTEGRITY] موجود بالدستور، لكن النموذج لم
  يطبّقه بأمانة بقرار فعلي رغم أنه "ذكره" لغوياً).

  الحل: بدل إرسال الدستور بالكامل بطلب واحد، نقسّم التحليل لمراحل
  متسلسلة (Multi-Pass)، كل مرحلة تستقبل فقط الأقسام المرتبطة بمهمتها
  + نتائج المراحل السابقة (ملخصة وقصيرة، وليس البيانات الخام الضخمة)
  - هذا يقلّص حجم "النافذة" التي يجب على النموذج الانتباه لكل جزء
  فيها بكل مرحلة، فتختفي مشكلة "الضياع بالمنتصف" عملياً.

⚠️ صدق تقني كامل: هذا يرفع عدد نداءات الـ API من نداء واحد لخمسة لكل
تحليل كامل (حصة يومية أقل بمقدار 5×) - مقايضة صريحة اختارها المستخدم
بوعي (دقة أعلى مقابل حصة أقل)، وليست "مجانية" بأي شكل.
"""
import re

SECTION_MARKERS = [
    "SYSTEM_CORE", "OHLC_PROCESSING", "SWING_DETECTION", "MARKET_STRUCTURE",
    "ORDER_BLOCKS", "FAIR_VALUE_GAPS", "LIQUIDITY_MAPPING", "PREMIUM_DISCOUNT",
    "ICT_TIME_AND_SESSIONS", "ICT_MARKET_MAKER_MODEL", "IPDA_DATA_RANGES",
    "TOP_DOWN_WORKFLOW", "ENTRY_MODELS", "DUAL_TARGET_MANAGEMENT",
    "RISK_ENGINE", "CONFIDENCE_SCORING", "SELF_LEARNING", "TRADE_JOURNAL",
    "CRYPTO_MARKET_DATA", "SIGNAL_OUTPUT", "AUTHENTICITY_ENGINE",
    "MASTER_TRADER_MINDSET", "HOLISTIC_MARKET_READING",
    "BOS_OB_DIRECTIONAL_INTEGRITY", "LAST_CANDLE_ACCURACY",
    "HOLISTIC_VISUAL_SCANNING",
]

# ═══ تجميع كل قسم لمرحلة التحليل التي يخدمها فعلياً ═══
# مبني على المحتوى الفعلي لكل قسم (راجعنا كل قسم قبل التصنيف) - وليس
# تخميناً بالاسم فقط.
# ═══ تجميع كل قسم لمرحلة التحليل التي يخدمها فعلياً ═══
# مبني على المحتوى الفعلي لكل قسم (راجعنا كل قسم قبل التصنيف)، مع
# موازنة الحجم بين المراحل (كل مرحلة ~25-37 ألف توكن بدل تفاوت كبير
# بين 17 ألف و56 ألف بالتوزيع الأول - توازن أفضل = فائدة أكبر ضد
# مشكلة "الضياع بالمنتصف"، لأنه حتى مرحلة "كبيرة" الآن تبقى أصغر
# بكثير من الدستور الكامل 159 ألف توكن دفعة واحدة).
STAGE_1_HOLISTIC = [
    "SYSTEM_CORE", "HOLISTIC_VISUAL_SCANNING", "HOLISTIC_MARKET_READING",
    "MASTER_TRADER_MINDSET", "TOP_DOWN_WORKFLOW",
]

STAGE_2_STRUCTURE = [
    "SWING_DETECTION", "MARKET_STRUCTURE", "PREMIUM_DISCOUNT",
    "BOS_OB_DIRECTIONAL_INTEGRITY", "LAST_CANDLE_ACCURACY",
    "ICT_TIME_AND_SESSIONS",
    # ⚠️ إصلاح جذري (يوليو 2026) - اكتُشف بباك تيست حقيقي على 10 صفقات
    # موضوعية (KnownSetupsFinder): 3 من 3 حالات فشل كامل بالاتجاه (Nemotron
    # 3 Ultra) كانت مصدرها مرحلة Daily تحديداً، وليس أي مرحلة لاحقة. السبب
    # الجذري المؤكد (مو تخمين):
    #  (أ) _build_daily_prompt() يشاور صراحة الموديل لـ"Section 12.3" لكن
    #      قسم [TOP_DOWN_WORKFLOW] (الذي يحوي 12.3 فعلياً - منهجية تحديد
    #      البياس بالتفصيل: Structure-based -> Context-based -> Level-based
    #      -> Weekly alignment check) لم يكن موجوداً إطلاقاً بمعرفة هذه
    #      المرحلة - الموديل يُحال لقسم لا يصله أبداً.
    #  (ب) [MASTER_TRADER_MINDST] (فيه تحديداً 22.1 ANTI-RECENCY BIAS: "لا
    #      تفترض أن آخر 3-5 شمعات تحدد المستقبل - افحص الهيكل الحقيقي") كان
    #      موجوداً فقط بمرحلة Weekly - غير متاح للموديل وقت تحليل Daily،
    #      رغم أن Daily هي "القائد" (COMMANDER) حسب الدستور نفسه وأكثر
    #      عرضة لهذا الخطأ تحديداً (بيانات تاريخية قصيرة نسبياً 60-90 يوم).
    # تحقق فعلي مباشر على 3 حالات الفشل الموثقة: بكل حالة، شمعة/شمعات
    # الأيام الأخيرة أظهرت انعكاساً أو تبايناً واضحاً عن الاتجاه الأقدم
    # بنفس النافذة، والموديل انحاز للأحدث (أو تجاهل تعارضاً صريحاً مع
    # Weekly سجّله بنفسه بحقل weekly_alignment=DIVERGENT) بدل تطبيق فحص
    # الهيكل الكامل الذي يطلبه قسم 22.1 صراحة.
    # الحل: إرجاع القسمين لمكانهما الصحيح منطقياً - هذا ليس "قاعدة حرفية
    # جديدة نحفظها للموديل"، بل إصلاح فجوة بنيوية كانت تمنع وصول تعليمات
    # الفهم العميق (لا الحفظ) للمرحلة التي تحتاجها أكثر من غيرها.
    "MASTER_TRADER_MINDSET", "TOP_DOWN_WORKFLOW",
]


# ⚠️ إعادة تصميم جذرية (يوليو 2026، بعد باك تيست 19 صفقة بشرية حقيقية
# كشف SL يخرق قاعدة الدستور نفسه [RISK_ENGINE] "SL >= 1.5xATR" بـ7 من
# 10 صفقات - راجع HUMAN_TRADES_BACKTEST_REPORT للتفاصيل الكاملة):
#
# المشكلة الجذرية المكتشفة لم تكن بالمنهجية نفسها بل بخطأين مركّبين:
#  (1) خطأ فصل الأقسام (راجع تعليق _load_and_split أعلاه) كان يبتلع
#      6 أقسام كاملة (منها RISK_ENGINE-المجاور وICT_MARKET_MAKER_MODEL)
#      داخل DUAL_TARGET_MANAGEMENT بالغلط - أصلحناه بالدالة نفسها.
#  (2) حتى بعد إصلاح (1)، التسمية "STAGE_4_ENTRY" هنا كانت **مضلّلة
#      اسمياً**: توحي أنها معرفة "مرحلة entry" لكنها فعلياً مربوطة
#      برقم 4 الذي يذهب لمرحلة "h1" (STEP 4/5 - تكتيكي: هل تشكّل
#      MSS/CHoCH فقط) وليس لمرحلة "entry" الحقيقية (STEP 5/5 - حيث
#      يُبنى SL/TP النهائي فعلياً). النتيجة المباشرة المؤكدة رياضياً:
#      [RISK_ENGINE] (يحوي قاعدة SL>=1.5xATR وطريقة حساب الـbuffer)
#      لم يكن يصل إطلاقاً لمرحلة بناء SL الفعلية - كان "يذهب" لمرحلة
#      h1 التي لا علاقة لمهمتها بحساب SL نهائي بتاتاً.
#      نفس الخطأ بالضبط أثّر على mmm_phase (Market Maker Model 1-5)
#      المطلوب من مرحلة h4 - قسم [ICT_MARKET_MAKER_MODEL] لم يكن
#      متاحاً لها (كان "مدفوناً" بخطأ (1) وحتى لو لم يكن، كان مصنّفاً
#      ضمن STAGE_4_ENTRY المتجهة لمرحلة أخرى غير h4).
#
# الحل: إعادة بناء التصنيف بالكامل حسب **المهمة الفعلية لكل مرحلة**
# (مقروءة من _build_*_prompt نفسها بـmulti_pass_analysis.py)، وليس حسب
# اسم متغير قد يكون مضلّلاً:
#   - h4  (STEP 3/5): "أين المناطق المُنقّحة + أي Phase من MMM؟"
#     يحتاج: OB/FVG/Liquidity (لتحديد المناطق) + MMM Model (لتحديد
#     الـPhase) + IPDA (نطاق البيانات الزمني ذو الصلة).
#   - h1  (STEP 4/5): "هل تشكّل تحوّل هيكلي (MSS/CHoCH) فعلاً الآن؟"
#     يحتاج: Market Structure + دقة قراءة آخر شمعة - لا علاقة له بإدارة
#     مخاطر أو نماذج دخول، هذه ليست مهمته.
#   - entry (STEP 5/5): "ابنِ Entry/SL/TP النهائي واحسب الثقة."
#     يحتاج: Entry Models (لاختيار نموذج الدخول) + Risk Engine (لحساب
#     SL الصحيح: الحد الأدنى بالنسبة/ATR + البفر) + Dual Target
#     Management (لاختيار TP بمنطق IRL/ERL) + Confidence Scoring +
#     Signal Output (شكل المخرجات النهائي).
STAGE_3_ZONES = [
    "ORDER_BLOCKS", "FAIR_VALUE_GAPS", "LIQUIDITY_MAPPING",
    "AUTHENTICITY_ENGINE", "ICT_MARKET_MAKER_MODEL", "IPDA_DATA_RANGES",
]

STAGE_4_ENTRY = [
    "BOS_OB_DIRECTIONAL_INTEGRITY", "LAST_CANDLE_ACCURACY", "SWING_DETECTION",
    # ⚠️ فجوة توجيه حقيقية اكتُشفت وأُصلحت (يوليو 2026، بعد إعادة بناء
    # _build_15m_prompt لمنهجية ICT الحرفية - راجع MARKET_STRUCTURE
    # المرحلة الآن): نص هذه المرحلة (STEP 4/5) يطلب من الموديل صراحة:
    # "Map liquidity... identify EQH/EQL... per section [ICT_TIME_AND_
    # SESSIONS] 9.1B and [LIQUIDITY_MAPPING]" و"Check for a Judas Swing
    # per [ICT_TIME_AND_SESSIONS] 9.3/9.1B" - لكن هذين القسمين لم يكونا
    # ضمن معرفة هذه المرحلة إطلاقاً قبل هذا الإصلاح (كانت المرحلة تُحال
    # لأقسام لا تصلها أبداً - نفس فئة الخطأ الجذري الموثّقة أعلاه بخصوص
    # Daily/TOP_DOWN_WORKFLOW). بلا LIQUIDITY_MAPPING، الموديل لا يملك
    # تعريفاً واحداً لما هو EQH/EQL أو IRL/ERL أو كيف يُميَّز Sweep حقيقي
    # عن استمرار حقيقي (7.3) - بالضبط الفهم الذي طلب المستخدم تعليمه
    # "كيف ومتى وشو أشكاله" بدل معادلة جامدة. وبلا ICT_TIME_AND_SESSIONS،
    # لا تعريف لـJudas Swing (9.3) ولا لنافذة تكييف الكريبتو (9.1B) التي
    # المرحلة نفسها تطلب فحصها. أُضيف القسمان كاملين (لا استخراج جراحي -
    # كل قسم 7.x/9.x مترابط ببعضه، وبالمقارنة مع حجم STAGE_2/STAGE_3
    # الحاليين (~50K توكن) هذا يبقى ضمن نفس النطاق المقبول من نافذة
    # 1M توكن الفعلية لـNemotron 3 Ultra).
    "LIQUIDITY_MAPPING", "ICT_TIME_AND_SESSIONS",
]
# ⚠️ إصلاح "حشو معرفي جامد" حقيقي (يوليو 2026، بطلب المستخدم: "زبط
# ملف المعرفة والبرومبت بطريقة أسطورية... هل البوت يعتمد عالفهم ولا
# معادلات جامدة؟"): كان القسم الكامل [MARKET_STRUCTURE] (42,706 حرف،
# يشمل 4.1 "كيف تحدد الاتجاه من الصفر بتحليل تسلسل swings كامل"، 4.4
# "Internal vs External"، 4.5-4.8 أمثلة/أخطاء شائعة إضافية، 4.11
# Railroad Tracks) يُرسَل بالكامل لمرحلة h1 - رغم أن مهمة h1 الفعلية
# (بنص _build_1h_prompt) هي سؤال واحد ضيق جداً: "هل تشكّل تحوّل هيكلي
# تكتيكي (MSS/CHoCH) الآن عند منطقة الـHTF المحدَّدة مسبقاً بمرحلة
# 4H؟" - الاتجاه العام نفسه محسوم أصلاً بمرحلة Daily ويصل لـh1 جاهزاً
# ضمن daily_result (JSON كامل بالبرومبت) - لا حاجة لإعادة "تعليم"
# النموذج من الصفر كيف يستنتج اتجاهاً هو ليس مسؤولاً عن استنتاجه بهذه
# المرحلة. تحقق مباشر: "MSS (Market Structure Shift) = CHoCH on Entry
# TF" مذكور صراحة بالدستور نفسه (قسم ENTRY_MODELS) - يعني القسمين
# الفعلياً ذوي الصلة بمهمة h1 هما 4.2 (BOS، للتمييز) و4.3 (CHoCH، جوهر
# المهمة، وأصبحت تشمل الآن 4.3B CISD أيضاً - راجع get_market_structure_
# choch_focus) فقط - وليس القسم بأكمله. الحل: دالة استخراج جراحية جديدة
# (get_market_structure_choch_focus) تسحب فقط PURPOSE + 4.1B + 4.2 +
# 4.3 + 4.3B من [MARKET_STRUCTURE] (~40K حرف بدل 66.4K الآن بعد إضافة
# CISD - توفير حقيقي، بلا أي فقدان معلومة فعلياً ذات صلة بالمهمة الضيقة).

STAGE_5_SYNTHESIS = [
    "ENTRY_MODELS", "RISK_ENGINE", "DUAL_TARGET_MANAGEMENT",
    "CONFIDENCE_SCORING", "SIGNAL_OUTPUT", "OHLC_PROCESSING",
    "CRYPTO_MARKET_DATA",
    # ⚠️ فجوة توجيه حقيقية أخطر من فجوة h15 أعلاه (يوليو 2026): مرحلة
    # Entry (STEP 5/5 - حيث يُبنى SL/TP/إشارة نهائية فعلياً، وأهم مرحلة
    # على الإطلاق) يطلب نصها الحرفي من الموديل:
    #   "structural confirmation (MSS/CHoCH/CISD - see MARKET_STRUCTURE
    #    4.2/4.3/4.3B) has already occurred" (لتقرير BUY/SELL مقابل
    #    BUY_LIMIT/SELL_LIMIT)
    #   "prefer an ERL level... see section 7.11" (لاختيار الـtp)
    #   "per [ICT_TIME_AND_SESSIONS], time is as important as price...
    #    see 9.1B for the crypto-adapted windows" (لتقرير فوري أم معلق)
    # لكن ولا واحد من هذه الأقسام الثلاثة كان يصل لهذه المرحلة إطلاقاً
    # قبل هذا الإصلاح - كانت المرحلة الأهم بالـpipeline (القرار النهائي
    # القابل للتنفيذ فعلياً) تُحال لتعريفات لا تملكها أبداً. هذا بالضبط
    # نوع الخطأ الجذري الذي طلب المستخدم تجنبه: "لازم يكون مشروح كيف
    # وشلون وامتى يطلع كذا من البيانات الخام" - يستحيل ذلك لو التعريف
    # نفسه غائب عن المرحلة التي تطبّقه لاتخاذ القرار الفعلي. الحل: نفس
    # المقتطف الجراحي المُستخدم لمرحلة h15 (get_market_structure_choch_
    # focus - لا حاجة لإعادة "تعليم" اتجاه من الصفر هنا أيضاً، فقط تمييز
    # BOS/CHoCH/CISD) + القسمان الكاملان LIQUIDITY_MAPPING (لـ7.11
    # IRL/ERL) وICT_TIME_AND_SESSIONS (لـ9.1B/9.5 Kill Zones) - نفس
    # الأقسام المُضافة أعلاه لمرحلة h15، بلا تكرار مُشكل (كل مرحلة
    # تستقبل الدستور كاملاً بشكل مستقل - الدستور نفسه مصمم ليُستخدم من
    # أكثر من زاوية بمراحل مختلفة، تماماً كما MASTER_TRADER_MINDSET و
    # TOP_DOWN_WORKFLOW مُكرَّرين أصلاً بين STAGE_1 وSTAGE_2 أعلاه).
    "LIQUIDITY_MAPPING", "ICT_TIME_AND_SESSIONS",
]
# ملاحظة: SELF_LEARNING و TRADE_JOURNAL أُزيلا نهائياً من كل مراحل
# التحليل الحي - محتواهما الفعلي (تحقق مباشر من النص الخام) عن نظام
# توثيق/تعلّم من صفقات تاريخية سابقة (محاسبة، سجلات، تحليل أنماط
# فشل قديمة) - لا علاقة تحليلية مباشرة لهما بقرار صفقة حالية قيد
# التنفيذ الآن، ووجودهما بمرحلة entry سابقاً كان يستهلك ~10,000 توكن
# بلا فائدة تحليلية فعلية (مجرد "كان موجوداً هناك" بلا تبرير محتوى).


_cache = {"content": None, "sections": None}


def _load_and_split():
    """يحمّل ملف الدستور مرة واحدة ويقسمه لقاموس {اسم القسم: نصه}

    ⚠️ إصلاح جذري (يوليو 2026، بعد باك تيست حقيقي على 19 صفقة بشرية
    كشف انحرافاً خطيراً بحساب SL - راجع HUMAN_TRADES_BACKTEST_REPORT):

    النسخة القديمة كانت تستخدم content.find(f"[{name}]") لإيجاد "بداية"
    كل قسم - لكن هذا يوقف عند **أول ظهور حرفي** للنص "[NAME]" بالملف
    كاملاً، بغض النظر إن كان هذا الظهور فعلاً رأس القسم أو مجرد **إشارة
    مرجعية عابرة** لاسم القسم داخل نص قسم آخر تماماً (مثال حقيقي موثّق:
    قسم [LIQUIDITY_MAPPING] يحتوي بمنتصفه جملة "...refines the existing
    [DUAL_TARGET_MANAGEMENT] section..." - وهذا الظهور العابر جاء *قبل*
    رأس القسم الحقيقي [DUAL_TARGET_MANAGEMENT] بآلاف الأسطر).

    الأثر الفعلي المكتشف: القسم "DUAL_TARGET_MANAGEMENT" المحمَّل فعلياً
    بالنسخة القديمة كان طوله 200,801 حرف (~50,200 توكن) بدل حجمه
    الحقيقي (28,001 حرف) - لأنه امتد خطأً من نقطة الإشارة العابرة حتى
    [RISK_ENGINE]، مبتلعاً بذلك أقسام [PREMIUM_DISCOUNT],
    [ICT_TIME_AND_SESSIONS], [ICT_MARKET_MAKER_MODEL],
    [IPDA_DATA_RANGES], [TOP_DOWN_WORKFLOW], [ENTRY_MODELS] بأكملها -
    فأصبحت هذه الأقسام الستة غير موجودة إطلاقاً كمفاتيح مستقلة بقاموس
    `sections` (يستحيل حقنها لأي مرحلة بشكلها الصحيح مهما كانت تسميتها
    صحيحة بقوائم STAGE_* أدناه، لأن المحتوى نفسه "مفقود" من القاموس).

    التصليح: بدل .find() الساذج، نبحث عن **رأس القسم الحقيقي** بنمط
    صارم "[NAME]\\n===...===\\n" (كل قسم بالدستور مؤكد يتبع اسمه مباشرة
    بخط فاصل من علامات '=' - تحقق فعلي على الـ26 قسم بدون استثناء)، مع
    استبعاد صريح لأي تطابق مسبوق بـ"END OF " (نهاية قسم سابق تذكر اسمه).
    تحقق مستقل بعد الإصلاح: كل قسم من الـ26 يبدأ ببداية صحيحة، ينتهي
    بـ"END OF [نفس الاسم]" الصحيح، ولا يحتوي بمنتصفه أي رأس قسم آخر -
    0 تلوث عبر كل الأقسام (مقابل تلوث كارثي بقسم واحد سابقاً).
    """
    if _cache["sections"] is not None:
        return _cache["sections"]

    from config import Config
    import re
    with open(Config.KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # نجمع كل "رأس قسم حقيقي" أولاً (موقعه + اسمه)، مرتبة حسب الموقع
    # الفعلي بالملف - هذا يضمن الترتيب الصحيح حتى لو SECTION_MARKERS
    # مرتبة بترتيب مختلف عرضاً.
    head_positions = []
    for name in SECTION_MARKERS:
        pattern = re.compile(r"(?<!END OF )\[" + re.escape(name) + r"\]\n=+\n")
        m = pattern.search(content)
        if m is None:
            continue  # قسم غير موجود بالملف فعلياً (يُسجَّل بـmissing_sections)
        head_positions.append((m.start(), name))
    head_positions.sort(key=lambda x: x[0])

    sections = {}
    for i, (start_idx, name) in enumerate(head_positions):
        end_idx = head_positions[i + 1][0] if i + 1 < len(head_positions) else len(content)
        sections[name] = content[start_idx:end_idx].strip()

    _cache["sections"] = sections
    return sections


def get_sections_text(section_names):
    """يرجع نص مجمّع لقائمة أسماء أقسام محددة (بترتيبها الأصلي بالملف)"""
    sections = _load_and_split()
    parts = []
    for name in SECTION_MARKERS:  # نحافظ على الترتيب الأصلي
        if name in section_names and name in sections:
            parts.append(sections[name])
    return "\n\n".join(parts)


def get_market_structure_choch_focus():
    """
    استخراج جراحي (لا حذف تعسفي) من قسم [MARKET_STRUCTURE] الكامل:
    PURPOSE (السياق العام الضروري لفهم أي شيء تالٍ) + 4.1B (كيف تقارن
    أي قمة/قاع بالمرجع الصحيح بدون تصنيف خاطئ - حرج جداً هنا لأن كشف
    MSS/CHoCH بمرحلة h1 هو بالضبط "قارن آخر قمة/قاع بالمرجع السابق
    الصحيح" - نفس العملية بالضبط التي تفشل بها الأخطاء الموثقة) + 4.2
    BREAK OF STRUCTURE (للتمييز - BOS مقابل CHoCH) + 4.3 CHANGE OF
    CHARACTER (هذا بالضبط تعريف MSS المطلوب فعلياً بمهمة مرحلة h1:
    "MSS = CHoCH on Entry TF"، مذكور صراحة بقسم [ENTRY_MODELS] الأصلي).

    ⚠️ لماذا لا نأخذ 4.1 (تحديد الاتجاه من الصفر - المحسوم أصلاً بمرحلة
    Daily)، 4.4-4.11 (Internal/External، أمثلة عبر فريمات متعددة،
    Railroad Tracks)؟ لأن مهمة h1 (بنص _build_1h_prompt الفعلي) ضيقة
    ومحددة: "هل تشكّل MSS/CHoCH عند منطقة الـHTF المحددة مسبقاً، بنفس
    اتجاه Daily Bias الممرَّر جاهزاً؟" - الاتجاه العام محسوم أصلاً
    بمرحلة Daily (نتيجتها الكاملة تصل لـh1 ضمن daily_result)، فإعادة
    "تعليم" النموذج من الصفر كيف يُشتق اتجاه عام (4.1) هو تكرار لعمل
    مرحلة مختلفة تماماً بالفعل قامت به، لا فائدة تحليلية إضافية - فقط
    استهلاك توكن (تحقق: نفس هذا القسم بالكامل يصل أصلاً لمرحلة Daily
    ضمن STAGE_2_STRUCTURE، فالمعرفة الكاملة "متوفرة" فعلاً بالنظام ولا
    "تضيع" - هنا فقط تفادي تكرارها الحرفي الكامل بمكان لا يحتاجها بهذا
    العمق). لكن 4.1B مختلفة جوهرياً عن 4.1: هي ليست "كيف تشتق اتجاهاً
    عاماً من الصفر" بل "كيف تقارن نقطتين محددتين بدون خطأ تصنيف" -
    مهارة تقنية عامة تنطبق تماماً على مهمة اكتشاف CHoCH بمرحلة h1
    بالضبط (يحتاج مقارنة آخر قمة/قاع بالمرجع الصحيح ليحدد إن كان
    التحول حقيقياً)، فتُضاف صراحة رغم أنها فنياً جزء من "منطقة 4.1".

    إذا تعذّر إيجاد الحدود الدقيقة لأي سبب (تغيّر بالملف مستقبلاً)، تعود
    الدالة للقسم الكامل تلقائياً (fallback آمن - لا فشل صامت بمعرفة أقل
    مما يجب، الأمان أولاً على التحسين).
    """
    sections = _load_and_split()
    full = sections.get("MARKET_STRUCTURE", "")
    if not full:
        return ""

    m_41 = re.search(r"\n4\.1\s+[A-Z][^\n]*\n=+\n", full)
    m_41b = re.search(r"\n4\.1B\s+[A-Z][^\n]*\n=+\n", full)
    m_42 = re.search(r"\n4\.2\s+[A-Z][^\n]*\n=+\n", full)
    m_44 = re.search(r"\n4\.4\s+[A-Z][^\n]*\n=+\n", full)
    if not (m_41 and m_42 and m_44):
        return full  # fallback آمن - القسم الكامل لو لم تُطابق الحدود المتوقعة

    purpose_block = full[: m_41.start()]
    # ⚠️ لو 4.1B موجودة (بين 4.1 و4.2)، نضمّها - وإلا نتجاهلها بأمان
    # (fallback ضمني: لو غابت لأي سبب، فقط BOS+CHoCH كما كان سابقاً)
    if m_41b and m_41.start() < m_41b.start() < m_42.start():
        labeling_block = full[m_41b.start(): m_42.start()]
    else:
        labeling_block = ""
    bos_and_choch_block = full[m_42.start(): m_44.start()]
    return (
        purpose_block
        + labeling_block
        + "\n[NOTE: Section 4.1 (trend identification from scratch) and "
        "4.4 onward (internal/external structure, multi-timeframe mapping, "
        "common mistakes, Railroad Tracks) are OMITTED here deliberately - "
        "not because they don't matter, but because the Daily Bias (trend "
        "direction) is ALREADY established and provided to you below as "
        "daily_result - your job here is narrower: detect whether a BOS or "
        "CHoCH is forming RIGHT NOW at the HTF zone. Sections 4.2 and 4.3 "
        "below are the ones directly relevant to that specific judgment.]\n"
        + bos_and_choch_block
        + "\nEND OF [MARKET_STRUCTURE] (partial extract: PURPOSE + 4.2 + 4.3 only)\n"
    )


def get_stage_knowledge(stage_number):
    """يرجع نص الدستور المخصص لمرحلة معينة (1-5) فقط"""
    mapping = {
        1: STAGE_1_HOLISTIC,
        2: STAGE_2_STRUCTURE,
        3: STAGE_3_ZONES,
        4: STAGE_4_ENTRY,
        5: STAGE_5_SYNTHESIS,
    }
    text = get_sections_text(mapping.get(stage_number, []))
    if stage_number in (4, 5):
        # ⚠️ حقن جراحي: مرحلة h15 (stage 4) ومرحلة entry (stage 5) كلتاهما
        # تحصلان على نفس المقتطف المركّز من MARKET_STRUCTURE (راجع
        # get_market_structure_choch_focus) بدل القسم الكامل - يُضاف هنا
        # بدل ضمن STAGE_4_ENTRY/STAGE_5_SYNTHESIS نفسها لأن هذا استخراج
        # ديناميكي (regex) وليس اسم قسم كامل بسيط مثل البقية.
        # ⚠️ توسيع (يوليو 2026): كان مقصوراً على stage 4 فقط - لكن نص
        # _build_entry_prompt (stage 5) يحيل الموديل صراحة لـ"MARKET_
        # STRUCTURE 4.2/4.3/4.3B" لتمييز BUY/SELL الفوري عن BUY_LIMIT/
        # SELL_LIMIT المعلق (بالضبط بحث "هل CISD/CHoCH/MSS تأكّد فعلاً
        # الآن؟") - وهذا القرار (فوري أم معلق) يُتخذ بمرحلة entry نفسها،
        # وليس بمرحلة h15 فقط. بلا هذا المقتطف بمرحلة entry، القسم
        # الوحيد المذكور بالبرومبت لم يكن يصل أبداً لمن يحتاجه فعلياً
        # لاتخاذ القرار النهائي.
        ms_focus = get_market_structure_choch_focus()
        if ms_focus:
            text = f"{ms_focus}\n\n{text}" if text else ms_focus
    return text


def get_knowledge_stats():
    """
    إحصائيات حجم كل مرحلة (للتشخيص والشفافية).

    ⚠️ إصلاح دقة حقيقي (يوليو 2026): كانت هذه الدالة تحسب الحجم عبر
    get_sections_text(names) مباشرة - يتجاهل أي استخراج جراحي إضافي
    (مثل get_market_structure_choch_focus لمرحلة h1) لأن ذاك الاستخراج
    يُطبَّق فقط داخل get_stage_knowledge نفسها، لا get_sections_text.
    النتيجة: الإحصائية كانت "تكذب" (تُظهر حجم مرحلة h1 كما لو كانت
    تستقبل MARKET_STRUCTURE الكامل، بينما فعلياً تستقبل المقتطف
    المُختصَر فقط) - هذا بالضبط نوع "عدم الدقة الصامت" الذي يجب تفاديه.
    الحل: نستدعي get_stage_knowledge(stage_num) نفسها (المسار الحقيقي
    المُستخدَم فعلياً وقت التشغيل) بدل إعادة تجميع النص يدوياً هنا.
    """
    sections = _load_and_split()
    stats = {}
    for stage_num, names in (
        (1, STAGE_1_HOLISTIC), (2, STAGE_2_STRUCTURE),
        (3, STAGE_3_ZONES), (4, STAGE_4_ENTRY), (5, STAGE_5_SYNTHESIS),
    ):
        text = get_stage_knowledge(stage_num)
        stats[f"stage_{stage_num}"] = {
            "sections": names,
            "chars": len(text),
            "tokens_est": len(text) // 4,
        }
    total_chars = sum(len(sections.get(n, "")) for n in SECTION_MARKERS)
    stats["full_document_chars"] = total_chars
    stats["missing_sections"] = [n for n in SECTION_MARKERS if n not in sections]
    return stats

# -*- coding: utf-8 -*-
"""
Config - الإعدادات المركزية للبوت
كل المفاتيح السرية تُقرأ من متغيرات البيئة (.env) - لا مفاتيح مكشوفة بالكود أبداً.
"""
import os

# مسار ملف .env دايماً بجانب هذا الملف (config.py) - بغض النظر عن مجلد
# التشغيل الحالي (cwd). هذا يحل مشكلة عدم إيجاد .env عند التشغيل من
# IDLE أو من محرر يبدأ بمجلد مختلف.
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _manual_load_env(path):
    """قراءة ملف .env يدوياً (بديل احتياطي إذا python-dotenv غير مثبت)"""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # لا تكتب فوق متغير بيئة موجود مسبقاً بالنظام
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)
except ImportError:
    # dotenv غير مثبت - نقرأ الملف يدوياً كبديل مضمون
    _manual_load_env(_ENV_PATH)


def _split_keys(raw):
    """يحول 'key1,key2,key3' إلى ['key1', 'key2', 'key3'] بدون فراغات/فاضي"""
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


class Config:


    # ══════════════════════════════════════════════════════════
    #  AI PROVIDER - OpenRouter فقط (nvidia/nemotron-3-ultra-550b-a55b:free)
    # ══════════════════════════════════════════════════════════
    # ⚠️ قرار نهائي صريح من المستخدم (يوليو 2026): "شيل الموديلات اللي
    # غير أوبن راوتر". كل مزودي AI الآخرين (Gemini, Cloudflare Workers
    # AI, Groq, Mistral, SiliconFlow, SambaNova) أُزيلوا نهائياً من
    # الكود بالكامل (لا فقط من الاستخدام - الكود الداعم لهم أُزيل من
    # ai_client.py القديم، الذي حُذف بالكامل واستُبدل بـ
    # openrouter_client.py الموحّد الوحيد لكل استدعاءات AI بالمشروع).
    #
    # السبب الإضافي (اكتُشف أثناء هذا التنظيف نفسه): ai_client.py
    # القديم كان أصلاً **مكسوراً فعلياً** لو استُخدم مع OpenRouter -
    # _dispatch() كانت تستدعي self._call_openai_compatible() وهي دالة
    # محذوفة فعلياً من الكود (فقط تعليق متبقٍ يقول إنها أُزيلت) - لم
    # يُكتشف هذا الكسر سابقاً لأن OpenRouter لم يكن يُستخدم فعلياً من
    # هذا المسار بأي اختبار حي سابق.
    OPENROUTER_API_KEYS = _split_keys(os.getenv("OPENROUTER_API_KEYS", ""))
    _single_or = os.getenv("OPENROUTER_API_KEY", "")
    if _single_or and _single_or not in OPENROUTER_API_KEYS:
        OPENROUTER_API_KEYS.insert(0, _single_or)

    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")

    # ⚠️ قرار نهائي مُقفَل (بطلب المستخدم الصريح، بعد اختبارات فعلية
    # متكررة موثّقة بـ nemotron_training_logs/SESSION_LOG_2026-07-05.md):
    # "none" حصراً. "low" جُرِّب 3 مرات على برومبتات حقيقية (30-45K
    # توكن) وفشل الثلاث مرات (استهلك التوكنز على تفكير غير مكتمل، أو
    # Timeout كامل حتى بحد 16000 توكن ومهلة 350 ثانية).
    OPENROUTER_REASONING_EFFORT = os.getenv("OPENROUTER_REASONING_EFFORT", "none")

    # مهلة الانتظار لكل طلب HTTP فردي (ثانية) - القيمة الافتراضية 150
    # ثانية أثبتت التوازن الأفضل فعلياً (هامش أمان كافٍ فوق أطول رد
    # ناجح موثّق ~124 ثانية، بلا انتظار مفرط على طلبات معلّقة فعلياً).
    OPENROUTER_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "150"))

    # للتوافق الخلفي مع كود قديم كان يستخدم Config.MODEL / Config.API_URL
    MODEL = OPENROUTER_MODEL
    API_URL = ""

    # ⚠️ رُفع من 16384 لـ24576 بعد اكتشاف فعلي بالباك تيست: بعض الردود
    # (خصوصاً backtest mode مع حقول narrative/reasoning/bos_reconciliation
    # الجديدة) وصلت لـ14K+ توكن مخرجات، قريبة جداً من الحد القديم.
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "24576"))
    # TEMPERATURE منخفض جداً (0.1) لتقليل العشوائية الطبيعية للنموذج
    # اللغوي قدر الإمكان.
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))

    # نطاق الثقة "الحرج" - لو وقع القرار بهذا النطاق، BrainCore يشغّل
    # تلقائياً محاولتين إضافيتين ويطلب إجماع (consensus) بدل الاكتفاء
    # بمحاولة واحدة.
    BORDERLINE_CONFIDENCE_LOW = int(os.getenv("BORDERLINE_CONFIDENCE_LOW", "60"))
    BORDERLINE_CONFIDENCE_HIGH = int(os.getenv("BORDERLINE_CONFIDENCE_HIGH", "78"))
    AUTO_CONSENSUS_ENABLED = os.getenv("AUTO_CONSENSUS_ENABLED", "true").lower() == "true"
    AUTO_CONSENSUS_EXTRA_RUNS = int(os.getenv("AUTO_CONSENSUS_EXTRA_RUNS", "2"))

    CACHE_TTL = int(os.getenv("CACHE_TTL", "600"))

    # ══════════════════════════════════════════════════════════
    #  إعدادات التداول
    # ══════════════════════════════════════════════════════════

    DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "BTC/USDT")
    # auto = try public feeds in order, then pin the successful exchange for
    # every timeframe in the same analysis. Users can explicitly select one.
    DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "auto").strip().lower()
    CANDLES_COUNT = 500

    # Telegram is optional and only controls the chat interface. Exchange
    # trading credentials are intentionally not accepted by this project.
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # ══════════════════════════════════════════════════════════
    #  MARKET SCANNER - قائمة العملات الممسوحة (Top by market cap)
    # ══════════════════════════════════════════════════════════
    SCAN_SYMBOLS = _split_keys(os.getenv("SCAN_SYMBOLS", "")) or [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
        "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "TON/USDT",
        "DOT/USDT", "TRX/USDT", "MATIC/USDT", "LTC/USDT", "SHIB/USDT",
        "BCH/USDT", "NEAR/USDT", "UNI/USDT", "ATOM/USDT", "ETC/USDT",
    ]

    # الحد الأدنى للثقة عشان صفقة تعتبر "توصية قوية" بالماسح الشامل
    SCANNER_MIN_CONFIDENCE = int(os.getenv("SCANNER_MIN_CONFIDENCE", "85"))
    # الحد الأدنى لنسبة النجاح التاريخية الموثقة (من signal_tracker) عشان
    # تُحسب الصفقة "مؤكدة إحصائياً" مو بس "الـ AI واثق منها"
    SCANNER_MIN_HISTORICAL_WINRATE = float(os.getenv("SCANNER_MIN_HISTORICAL_WINRATE", "0.0"))

    MAX_RISK_PER_TRADE = 0.02
    ACCOUNT_BALANCE = 10000.0
    # Optional execution-policy filters. Zero disables the filter. They never
    # move structural targets/stops; they only inform or decline execution.
    MIN_RR_POLICY = float(os.getenv("MIN_RR_POLICY", "0"))
    MAX_SL_POLICY_PCT = float(os.getenv("MAX_SL_POLICY_PCT", "0"))

    MTF_ENABLED = True

    # ═══ Entry Timeframes - حل جذري (يوليو 2026): مطابقة مع
    # multi_pass_analysis.py::HTF_CHAIN الجديد (Daily+4H للانحياز، 15m
    # للسيولة/الهيكل التكتيكي، 1-5m للتنفيذ) - يُستخدم فقط بالمسار
    # الحي القديم (get_multi_timeframe) - مسار multi_pass الأساسي يجلب
    # فريماته مباشرة عبر fetch_ohlcv_up_to لكل فريم على حدة.
    TF_CONTEXT_MAP = {
        "1m":  ["1m",  "15m", "4h"],
        "3m":  ["3m",  "15m", "4h"],
        "5m":  ["5m",  "15m", "4h"],
        "15m": ["15m", "4h",  "1d"],
        "30m": ["30m", "4h",  "1d"],
        "1h":  ["1h",  "4h",  "1d"],
    }

    # ⚠️ حل جذري (يوليو 2026، بطلب صريح من المستخدم): "15m" القديمة كانت
    # تُستخدم كـEntry TF مباشرة - هذا لا يطابق منهجية ICT الحقيقية بعد
    # التصحيح المعماري (multi_pass_analysis.py::HTF_CHAIN): 15m الآن هي فريم
    # المرحلة التكتيكية (سيولة/هيكل)، لا فريم التنفيذ الفعلي - التنفيذ
    # الحقيقي يجب أن يكون 1-5 دقائق (راجع multi_pass_analysis.py::
    # _VALID_EXECUTION_TIMEFRAMES).
    DEFAULT_TIMEFRAME = "5m"  # Entry TF الافتراضي

    TF_CANDLES = {
        "entry":   500,
        "context": 300,
        "macro":   200,
    }

    # ⚠️ إصلاح خطأ حقيقي مُكتشف بتدقيق شامل (يوليو 2026): كان المسار هنا
    # نسبياً بحتاً ("data/trading_knowledge.txt") - يعتمد كلياً على مجلد
    # التشغيل الحالي (cwd) وقت الاستيراد. لو تم تشغيل المشروع من أي مسار
    # آخر غير جذر المشروع (سيناريو حقيقي وارد: IDE بمجلد مختلف، سكربت
    # خارجي يستورد BrainCore من مكان آخر)، الملف "data/trading_knowledge.txt"
    # لا يُوجَد، وBrainCore._ensure_knowledge_file() تُنشئ **ملف معرفة فارغ
    # بديل بصمت تام** (67 حرف فقط: "# TRADING KNOWLEDGE BASE") بلا أي
    # استثناء أو خطأ صريح يوقف التشغيل - البوت يكمل العمل وكأن شيئاً لم
    # يحدث، لكن بلا أي معرفة ICT/SMC إطلاقاً (كل الأقسام الـ26 "مفقودة").
    # هذا خطر حقيقي جداً لبوت تداول فعلي (قرارات بلا أي أساس معرفي، بصمت).
    # الحل: نفس نمط _ENV_PATH أعلاه بالضبط (مسار مطلق دائماً، مبني من
    # موقع هذا الملف نفسه config.py - يعمل بغض النظر عن cwd وقت التشغيل).
    KNOWLEDGE_FILE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "trading_knowledge.txt"
    )
    KNOWLEDGE_MAX_CHARS = 200000

    AI_CANDLES_ENTRY = 50
    AI_CANDLES_CONTEXT = 30
    AI_CANDLES_MACRO = 20

    # ⚠️ نفس إصلاح KNOWLEDGE_FILE أعلاه (مسار مطلق دائماً، لا يعتمد على
    # cwd وقت التشغيل) - يُطبَّق هنا للاتساق الكامل عبر كل مسارات
    # الملفات بالمشروع (تدقيق شامل، يوليو 2026).
    _DATA_ROOT = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(_DATA_ROOT, "data")
    MEMORY_FILE = os.path.join(_DATA_ROOT, "data", "memory.json")
    TRADES_FILE = os.path.join(_DATA_ROOT, "data", "trades.json")

    # ═══════════════════════════════════════════════════
    #  SYSTEM PROMPT - شخصية + سلوك + طريقة تفكير فقط
    # ═══════════════════════════════════════════════════
    SYSTEM_PROMPT = """You are a living, breathing, elite institutional trader with decades of
experience across every market regime — bull runs, crashes, ranges, black swans.
You don't just analyze charts - you READ them like a story.
Every candle tells you who is in control: buyers or sellers.
Every wick tells you where orders were rejected.
Every gap tells you where institutions moved too fast.

HOW YOU THINK — UNDERSTANDING, NOT PATTERN-MATCHING:
- You do NOT think in a checklist of independent boxes to tick and sum.
  You think the way a veteran actually thinks: you SEE the whole picture
  first, then verify it with numbers - never the other way around.
- Your reasoning ALWAYS follows this order (see [HOLISTIC_MARKET_READING]
  in the knowledge base for the full methodology):
    1. NARRATIVE FIRST - build the plain-language story of what has been
       happening in this market and WHY, as if explaining it to another
       trader who hasn't seen the chart. Never start with indicator values.
    2. ARCHETYPE - recognize which FAMILY of setup this resembles (spring/
       stop-hunt reversal, exhaustion blow-off, healthy pullback in trend,
       accumulation/distribution range, trap continuation...) the way a
       trader with thousands of screen-hours recognizes a shape they've
       seen before, and reason from how that archetype typically resolves.
    3. EVOLUTION - compare the current swing/leg to the last 2-3 swings:
       are impulses getting bigger or smaller? Are pullbacks getting
       deeper or shallower? Is volume favoring trend or counter-trend
       legs? The DIRECTION OF CHANGE over time matters more than any
       single snapshot value.
    4. MECHANICAL VERIFICATION - only now apply the precise ICT/SMC rules
       (Order Blocks, FVGs, liquidity, confluence scoring, authenticity
       checks) to rigorously verify or falsify the narrative with hard,
       specific numbers. A compelling story with no mechanical
       confirmation is just a story. Mechanical confluence with no
       coherent narrative behind it is just noise that happens to check
       boxes. You need BOTH to agree before trusting a signal.
- You see the market through the eyes of banks and hedge funds
- You ask yourself: "Where would Goldman Sachs enter here?"
- You ask: "Where are retail traders trapped right now, and does the
  data actually PROVE they exist, or am I assuming it?"
- You ask: "Have I seen this exact shape before, and how did it usually end?"
- You think in probabilities, not certainties
- You would rather miss a trade than take a bad one
- You actively look for reasons your own thesis could be WRONG before
  committing - build the opposing narrative explicitly, using the same
  data, before finalizing any signal at 75%+ confidence
- You weigh confluence across timeframes; a single signal is never enough
- Generalize the underlying institutional LOGIC to whatever form the
  market presents it in - never rigidly pattern-match a textbook shape.
  A concept that technically matches a rule but doesn't fit the broader
  story you've built is treated with suspicion, not blind trust.

HOW YOU PROCESS DATA:
- You will receive a KNOWLEDGE BASE file - this is your trading bible.
  It contains both the mechanical rules (how to detect and validate
  OBs, FVGs, liquidity, confluence, authenticity) AND the reasoning
  methodology (how to build the narrative, recognize archetypes, and
  track evolution). Apply both - the mechanics ground your narrative
  in verifiable fact; the methodology is what makes you a trader
  instead of a rule-lookup table.
- You will receive RAW CANDLE DATA for multiple timeframes
- Read EVERY candle - don't just glance at indicators
- The indicators are pre-computed to help you, but candles are primary
- Start analysis from the HIGHEST timeframe, work DOWN to entry
- If you receive AUTHENTICITY PRE-CHECKS (pre-computed numeric flags for
  wash trading, breakout quality, etc.), treat them as hard evidence
  that must be reconciled with your narrative - never ignore a
  contradicting authenticity flag just because the story "feels" right.
- If you receive prior trade performance/track record, use it to calibrate
  your confidence (if past signals of a similar type failed often, be more
  conservative; if they worked well, you may lean in - but never blindly)

HOW YOU MAKE DECISIONS:
- You are brutally honest - if you don't see a clear setup, say HOLD
- You never force a trade to justify your analysis
- You never let ego override risk management
- When in doubt, the answer is always HOLD
- A great trader's skill is knowing when NOT to trade
- You adapt your playbook to the detected market regime (trend/range/volatile)
  rather than applying one strategy blindly everywhere
- When your narrative/archetype/evolution read CONTRADICTS what the
  mechanical confluence score suggests, surface that conflict explicitly
  in your reasoning rather than silently picking whichever side "wins"
  on point count - the contradiction itself is valuable information

HOW YOU COMMUNICATE:
- Think step by step, following the Narrative → Archetype → Evolution →
  Mechanical Verification sequence, but keep it under 1200 words
- Your "reasoning" must read like a trader explaining their read out
  loud - a coherent story verified by numbers - never a bare list of
  disconnected checklist items with no narrative thread connecting them
- After your thinking, output ONLY valid JSON
- Every price you give must be a real number from the data
- Never fabricate or hallucinate price levels
- Be specific: "Bullish OB at 104,200-104,500" not just "there's an OB"

ABSOLUTE RULES:
- You MUST follow the knowledge base rules - they are non-negotiable
- If the knowledge base says "don't trade" in some condition, you HOLD
- If data is unclear or conflicting, you HOLD
- You never output a signal you're not confident about
- Confidence below 60 = HOLD, no exceptions"""

    @classmethod
    def ensure_data_dir(cls):
        os.makedirs(cls.DATA_DIR, exist_ok=True)

    @classmethod
    def has_any_ai_key(cls):
        return bool(cls.OPENROUTER_API_KEYS)

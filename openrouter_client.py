# -*- coding: utf-8 -*-
"""
OpenRouterClient - عميل AI موحّد وحيد للمشروع بالكامل، عبر OpenRouter
فقط (nvidia/nemotron-3-ultra-550b-a55b:free).
════════════════════════════════════════════════════════════════════
⚠️ قرار نهائي صريح من المستخدم (يوليو 2026): "شيل الموديلات اللي غير
أوبن راوتر" - هذا الملف يحل محل كل من:
  1. ai_client.py (كان مبنياً حول Gemini + Cloudflare Workers AI،
     ومكسور فعلياً لو استُخدم مع OpenRouter - _dispatch() كانت تستدعي
     self._call_openai_compatible() وهي دالة محذوفة فعلياً من الكود،
     لم يُكتشف هذا الكسر سابقاً لأن OpenRouter لم يكن يُستخدم من هذا
     الملف أصلاً بأي مسار حي مُختبر).
  2. NemotronClient + AIClientAdapter المحليين اللذين كانا مكرّرين
     دقيقاً بـ nemotron_backtest_driver.py لغرض الباك تيست فقط.

الآن كل نقاط الدخول (main.py, nemotron_backtest_driver.py, وأي كود
آخر بالمشروع) تستخدم نفس هذا الملف الموحّد الوحيد - لا ازدواجية،
لا مسارات "حية" و"باك تيست" منفصلة لنفس الوظيفة بالضبط.

الواجهة العامة مطابقة تماماً لما كان AIClient القديم يوفره (query,
query_json, query_json_race, query_json_two_step,
query_json_split_parallel, status, providers, total_cost, clear_cache)
- بحيث كل الكود المستدعي (brain_core.py, multi_pass_analysis.py,
backtest_engine.py, learning_manager.py, main.py) يعمل بلا أي تعديل
إضافي على منطقه الداخلي، فقط طبقة الاتصال تغيّرت بالكامل من الداخل.

════════════════════════════════════════════════════════════════════
آلية تعدد المفاتيح: OpenRouter يحكم الحصة اليومية عالمياً على مستوى
الحساب (موثّق رسمياً: "we govern capacity globally" - راجع
nemotron_training_logs/SESSION_LOG_2026-07-05.md للتفاصيل والمصدر)،
لذا تعدد المفاتيح هنا مفيد فقط لو كانت المفاتيح من حسابات مختلفة
فعلياً. الكود يدعم أي عدد من المفاتيح المتاحة بـ.env
(OPENROUTER_API_KEYS) ويبدّل بينها تلقائياً عند فشل مؤقت (502/429
غير-يومي) - لكن يتوقف فوراً بلا أي محاولة إضافية عند اكتشاف "429
free-models-per-day" (حصة يومية عالمية مستنفدة فعلاً - لا فائدة من
تبديل المفتاح، كلها تتشارك نفس السقف).
"""
import json
import re
import time
import logging
import concurrent.futures
import requests

from config import Config


class _SoftFail(Exception):
    """خطأ عابر (502 ازدحام مؤقت من طرف نيفيديا، أو مشابه) - يستاهل
    إعادة محاولة على مفتاح آخر."""
    pass


class _DailyQuotaExhausted(Exception):
    """429 'free-models-per-day' - حصة يومية عالمية مستنفدة فعلياً.
    لا فائدة من إعادة المحاولة على أي مفتاح - كلها تتشارك نفس السقف."""
    pass


class OpenRouterClient:
    """
    عميل موحّد وحيد لكل استدعاءات AI بالمشروع - عبر OpenRouter فقط.

    يدعم عدة مفاتيح (Config.OPENROUTER_API_KEYS) مع تبديل تلقائي عند
    فشل مؤقت، وتوقف فوري عند اكتشاف استنفاد الحصة اليومية العالمية.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger("OpenRouterClient")

        self.keys = list(Config.OPENROUTER_API_KEYS)
        self.model = Config.OPENROUTER_MODEL
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.reasoning_effort = Config.OPENROUTER_REASONING_EFFORT

        if not self.keys:
            self.logger.error(
                "❌ لا يوجد أي مفتاح OpenRouter! أضف OPENROUTER_API_KEYS بملف .env"
            )

        # حالة كل مفتاح: منهك (يومياً) أم لا - نفس فكرة _Provider القديمة
        # لكن مبسّطة لمزود واحد فقط.
        self._exhausted = {k: False for k in self.keys}
        self._current_index = 0

        # ⚠️ إصلاح جذري (يوليو 2026، بعد كراش حقيقي بـmain.py -
        # KeyError: 'remaining'): main.py (نقطة التشغيل اليدوي التفاعلي)
        # ما زالت مكتوبة بافتراض النظام القديم متعدد المزودين (Gemini +
        # Cloudflare + إلخ)، وتتوقع من `status()` حقولاً مفصّلة لكل مفتاح
        # (`per_key`: طلبات/أخطاء/exhausted) ضمن `providers['openrouter']`
        # - لم تكن هذه الإحصائيات التفصيلية تُجمَع إطلاقاً بالنسخة
        # الموحَّدة الجديدة (فقط `request_count` الإجمالي). الحل الجذري
        # الصحيح: تتبّع حقيقي لكل مفتاح على حدة (لا قيمة وهمية)، ثم بناء
        # `status()` الآن ليرجع **نفس الشكل الكامل بالضبط** الذي يتوقعه
        # main.py (بدل ترقيع main.py بمكان واحد وترك بقية الاستدعاءات
        # الأربعة الأخرى بنفس الملف تنكسر لاحقاً بنفس الخطأ).
        self._key_requests = {k: 0 for k in self.keys}
        self._key_errors = {k: 0 for k in self.keys}

        self.cache = {}
        self.request_count = 0
        self.total_cost = 0.0  # OpenRouter موديل :free دائماً = $0.00
        self.total_completion_tokens = 0

        self.total_reasoning_tokens = 0
        self.session = requests.Session()

        # ⚠️ توافق خلفي: بعض الكود القديم (multi_pass_analysis.py::
        # _should_use_two_step) يفحص self.ai.providers.get("cloudflare")
        # - الآن providers فارغ دائماً (لا مزودين متعددين بعد الآن)،
        # ما يضمن أن _should_use_two_step() ترجع False دائماً (لا حاجة
        # فعلية لمسار Two-Step - كان مخصصاً لموديلات معينة عبر
        # Cloudflare فقط، Nemotron لم يُظهر هذا التناقض بأي اختبار).
        self.providers = {}

        self.logger.info(
            f"✅ OpenRouterClient جاهز | الموديل: {self.model} | "
            f"عدد المفاتيح: {len(self.keys)}"
        )

    # ══════════════════════════════════════════════════════════
    #  إدارة المفاتيح (تبديل تلقائي عند فشل مؤقت)
    # ══════════════════════════════════════════════════════════

    def _available_keys(self):
        return [k for k in self.keys if not self._exhausted[k]]

    def _next_key_cycle(self, start_index=0):
        """يرجع قائمة المفاتيح المتاحة بترتيب دائري ابتداءً من start_index."""
        available = self._available_keys()
        if not available:
            return []
        n = len(available)
        start_index = start_index % n
        return available[start_index:] + available[:start_index]

    def reset_exhausted_keys(self):
        """إعادة تفعيل كل المفاتيح (مثلاً بداية يوم جديد)"""
        for k in self._exhausted:
            self._exhausted[k] = False
        self.logger.info("🔄 تمت إعادة تفعيل كل مفاتيح OpenRouter")

    # ══════════════════════════════════════════════════════════
    #  استدعاء HTTP فعلي واحد (مفتاح واحد، محاولة واحدة)
    # ══════════════════════════════════════════════════════════

    def _single_call(self, prompt, key, max_tokens, temperature, timeout_seconds,
                      force_json=False, response_schema=None):
        """
        ⚠️ حل جذري (يوليو 2026، بعد اكتشاف موثّق فعلياً بأول نداء حي كامل
        على البنية الجديدة: 3 محاولات تصحيح كاملة لمرحلة entry، إحداها
        بسبب JSON_PARSE_FAILED_RAW_RESPONSE_ONLY - الموديل خلط نص خارج
        الـJSON رغم طلب صريح نصي "رد بالـJSON فقط"): قبل هذا الإصلاح،
        الاعتماد الوحيد على إجبار صيغة الرد كان "تعليمات نصية" ضمن
        البرومبت نفسه (`_schema_to_instructions` + "Reply with ONLY the
        JSON object") - وهذا غير مضمون أبداً (النموذج "يفهم" الطلب لكن
        أحياناً يُخطئ بتطبيقه حرفياً، تماماً كما تحدث أخطاء حسابية أخرى
        موثّقة بهذا المشروع).

        الحل الجذري الحقيقي: `nvidia/nemotron-3-ultra-550b-a55b:free`
        غير مُدرَج رسمياً بقائمة `supported_parameters` الخاصة بـ
        `response_format` (فقط النسخة المدفوعة مُدرَجة)، **لكن تحقق حي
        فعلي مباشر (نداءان تجريبيان منفصلان، أحدهما بسكيما متداخلة
        بحجم مقارب لواقع هذا المشروع) أثبت أن الموديل يقبل فعلياً
        `response_format: json_schema` ويُرجع JSON نظيفاً 100% بلا أي
        markdown أو نص محيط** - رغم عدم إدراجه رسمياً. بالإضافة، تفعيل
        بلاجن `response-healing` المجاني من OpenRouter (يعمل على مستوى
        الـ API نفسه لا الموديل - موثّق: يخفّض معدل أخطاء الـJSON
        المكسور 80-99.8% حسب الموديل، تكلفة زمنية <1ms) كطبقة حماية
        إضافية أخيرة لو أي خطأ تركيبي بسيط تسلّل رغم ذلك (فاصلة زائدة،
        قوس ناقص). النتيجة العملية: القضاء شبه الكامل على فئة كاملة من
        إعادات المحاولة المكلفة (JSON_PARSE_FAILED) من جذرها - لا حاجة
        بعد الآن للاعتماد على تعليمات نصية وحدها.

        `response_schema` هنا (لو مُمرَّرة) بصيغة الكود الداخلية
        Gemini-style (نفس صيغة كل `_*_schema()` بـ multi_pass_analysis.py)
        - تُحوَّل هنا لصيغة JSON Schema القياسية عبر `_gemini_to_json_schema`
        قبل إرسالها - لا تعديل مطلوب على أي كود مستدعٍ (الشكل الداخلي
        القديم يبقى كما هو تماماً بكل مكان آخر بالمشروع).
        """
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "reasoning": {"effort": self.reasoning_effort},
        }
        if force_json and response_schema:
            try:
                json_schema = self._gemini_to_json_schema(response_schema)
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "trading_analysis_output",
                        "strict": False,  # غير صارم عمداً: الموديل غير مُدرَج رسمياً
                                           # بدعم strict، وبعض حقولنا (enum ضمن
                                           # object متداخل) قد ترفضها صيغة strict
                                           # الصارمة على موديل غير مضمون التوافق -
                                           # non-strict + response-healing يعطي
                                           # نفس الفائدة العملية بمخاطرة أقل.
                        "schema": json_schema,
                    },
                }
                body["plugins"] = [{"id": "response-healing"}]
            except Exception as e:
                self.logger.warning(
                    f"⚠️ فشل بناء response_format من الـschema (غير قاتل - "
                    f"سيُعتمد على التعليمات النصية وحدها كما كان سابقاً): {e}"
                )
        # ⚠️ تتبّع طلب فعلي واحد لهذا المفتاح تحديداً (يُحسَب بغض النظر
        # عن نجاح/فشل الرد لاحقاً - "طلب" يعني محاولة اتصال فعلية حصلت،
        # نفس تعريف request_count الإجمالي أعلاه لكن مُقسَّم بالمفتاح).
        self._key_requests[key] = self._key_requests.get(key, 0) + 1

        t0 = time.time()
        try:
            r = self.session.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://localhost",
                    "X-Title": "ICT-SMC Trading Bot (OpenRouter/Nemotron)",
                },
                json=body, timeout=timeout_seconds,
            )
        except requests.Timeout:
            self._key_errors[key] = self._key_errors.get(key, 0) + 1
            raise _SoftFail(f"TIMEOUT after {timeout_seconds}s")
        except requests.RequestException as e:
            self._key_errors[key] = self._key_errors.get(key, 0) + 1
            raise _SoftFail(f"NETWORK_ERROR: {e}")

        elapsed = time.time() - t0

        if r.status_code == 429:
            body_text = r.text[:300]
            if "free-models-per-day" in body_text:
                self._exhausted[key] = True
                self._key_errors[key] = self._key_errors.get(key, 0) + 1
                raise _DailyQuotaExhausted(body_text)
            self._key_errors[key] = self._key_errors.get(key, 0) + 1
            raise _SoftFail(f"429 rate-limited (temporary): {body_text}")
        if r.status_code == 502:
            self._key_errors[key] = self._key_errors.get(key, 0) + 1
            raise _SoftFail(f"502 upstream error (temporary): {r.text[:300]}")
        if r.status_code in (401, 403):
            self._exhausted[key] = True
            self._key_errors[key] = self._key_errors.get(key, 0) + 1
            raise _SoftFail(f"KEY_INVALID {r.status_code}: {r.text[:200]}")
        if r.status_code != 200:
            # ⚠️ حماية إضافية: لو الموديل رفض response_format لسبب ما
            # (غير متوقع بالتحقق الحي، لكن الأمان أولاً) - نعيد المحاولة
            # فوراً بلا response_format بدل اعتبارها فشلاً كاملاً للمفتاح.
            if "response_format" in body and r.status_code in (400, 422):
                self.logger.warning(
                    f"⚠️ response_format رُفض ({r.status_code}) - إعادة محاولة فورية "
                    f"بلا response_format (تعليمات نصية فقط، كالسلوك القديم)."
                )
                body.pop("response_format", None)
                body.pop("plugins", None)
                r = self.session.post(
                    self.url,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://localhost",
                        "X-Title": "ICT-SMC Trading Bot (OpenRouter/Nemotron)",
                    },
                    json=body, timeout=timeout_seconds,
                )
                if r.status_code != 200:
                    self._key_errors[key] = self._key_errors.get(key, 0) + 1
                    raise _SoftFail(f"HTTP {r.status_code}: {r.text[:300]}")
            else:
                self._key_errors[key] = self._key_errors.get(key, 0) + 1
                raise _SoftFail(f"HTTP {r.status_code}: {r.text[:300]}")

        data = r.json()
        if "error" in data and data["error"]:
            err_text = str(data["error"])
            if "free-models-per-day" in err_text:
                self._exhausted[key] = True
                self._key_errors[key] = self._key_errors.get(key, 0) + 1
                raise _DailyQuotaExhausted(err_text)
            self._key_errors[key] = self._key_errors.get(key, 0) + 1
            raise _SoftFail(err_text[:300])

        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content", "")
        usage = data.get("usage", {})
        completion_tok = usage.get("completion_tokens", 0)
        reasoning_tok = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)

        self.total_completion_tokens += completion_tok
        self.total_reasoning_tokens += reasoning_tok
        self.request_count += 1

        return content, elapsed

    # ══════════════════════════════════════════════════════════
    #  تحويل Gemini-style schema (الصيغة الداخلية القديمة بكل هذا
    #  المشروع) → JSON Schema قياسي (المطلوب لـ response_format)
    # ══════════════════════════════════════════════════════════

    @classmethod
    def _gemini_to_json_schema(cls, schema):
        """
        يحوّل صيغة الـschema الداخلية (type: "OBJECT"/"STRING"/"NUMBER"/
        "INTEGER"/"BOOLEAN"/"ARRAY"، بأحرف كبيرة - أسلوب Gemini القديم
        المُستخدم بكل دوال `_*_schema()` عبر multi_pass_analysis.py)
        لصيغة JSON Schema القياسية (type بأحرف صغيرة: "object"/"string"/
        إلخ) التي يتطلبها `response_format.json_schema.schema` عبر
        OpenRouter/OpenAI-compatible APIs. تحويل بنيوي بحت (لا معنى
        جديد يُضاف) - يعالج enum وproperties وrequired وitems
        (للمصفوفات) وproperties المتداخلة (للكائنات) بشكل تكراري.
        """
        if not isinstance(schema, dict):
            return {"type": "string"}

        type_map = {
            "OBJECT": "object", "STRING": "string", "NUMBER": "number",
            "INTEGER": "integer", "BOOLEAN": "boolean", "ARRAY": "array",
        }
        raw_type = schema.get("type", "STRING")
        json_type = type_map.get(raw_type, raw_type.lower() if isinstance(raw_type, str) else "string")

        result = {"type": json_type}
        if "enum" in schema:
            result["enum"] = schema["enum"]
        if "description" in schema:
            result["description"] = schema["description"]

        if json_type == "object":
            props = schema.get("properties", {})
            if props:
                result["properties"] = {
                    k: cls._gemini_to_json_schema(v) for k, v in props.items()
                }
            if "required" in schema:
                result["required"] = schema["required"]
        elif json_type == "array":
            items_schema = schema.get("items", {"type": "STRING"})
            result["items"] = cls._gemini_to_json_schema(items_schema)

        return result



    # ══════════════════════════════════════════════════════════
    #  query() - الدالة الأساسية (نص حر، لا JSON مضمون)
    # ══════════════════════════════════════════════════════════

    def query(self, prompt, system_prompt=None, max_tokens=None, use_cache=True,
              force_json=False, response_schema=None, temperature=None):
        """
        إرسال طلب لـ Nemotron عبر OpenRouter - يجرب كل المفاتيح المتاحة
        بالتناوب حتى ينجح واحد أو تُستنفد كلها. يرجع نص الرد الخام
        (str) - نفس توقيع AIClient.query() القديم بالضبط.
        """
        max_tokens = max_tokens or Config.MAX_TOKENS
        temperature = temperature if temperature is not None else Config.TEMPERATURE
        timeout_seconds = Config.OPENROUTER_TIMEOUT_SECONDS

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        if response_schema:
            full_prompt += (
                f"\n\n{'='*40}\nOUTPUT FORMAT (STRICT)\n{'='*40}\n"
                f"{self._schema_to_instructions(response_schema)}\n\n"
                "Reply with ONLY the JSON object. No markdown code fences, "
                "no explanation before or after it."
            )

        cache_key = None
        if use_cache:
            import hashlib
            cache_key = hashlib.md5(
                (full_prompt + str(force_json)).encode()
            ).hexdigest()
            if cache_key in self.cache:
                ts, val = self.cache[cache_key]
                if time.time() - ts < Config.CACHE_TTL:
                    return val

        available = self._available_keys()
        if not available:
            return json.dumps({
                "error": "كل مفاتيح OpenRouter منهكة (حصة يومية مستنفدة) أو لا يوجد مفتاح إطلاقاً"
            })

        # ⚠️ إصلاح خطأ منطقي حقيقي مُكتشف (يوليو 2026، بعد اختبار حي
        # فعلي أظهر توقفاً فورياً بمجرد استنفاد أول مفتاح بينما 8 من
        # أصل 11 مفتاحاً كانت لا تزال تعمل فعلياً - تحقق مباشر عبر
        # طلبات HTTP حقيقية لكل مفتاح على حدة أثبت ذلك رقمياً): التعليق
        # القديم ("حصة يومية عالمية - كل المفاتيح تتشارك نفس السقف")
        # كان **صحيحاً فقط لمفاتيح من نفس الحساب** - لكن هذا المشروع
        # يستخدم فعلياً 11 مفتاحاً من 11 **حساب مستقل تماماً** (موثّق
        # ومؤكَّد رياضياً سابقاً عبر GET /api/v1/key: creator_user_id
        # مختلف لكل مفتاح - راجع ARCHIVE_MASTER_SUMMARY قسم الحصة
        # اليومية). حصة كل حساب مستقلة 100% عن البقية - استنفاد مفتاح
        # واحد لا يعني إطلاقاً استنفاد البقية. الحل: `continue` بدل
        # `break` (نفس معالجة _SoftFail بالضبط) - المفتاح المُستنفَد
        # نفسه لا يُعاد تجربته أبداً (self._exhausted[key]=True يُضبط
        # قبل رفع الاستثناء بالفعل، ونفس الشيء بمسار query_json_race
        # الذي كان يتعامل مع هذا صحيحاً من الأساس أصلاً - هذا الإصلاح
        # يوحّد سلوك كل المسارات).
        last_error = None
        any_quota_exhausted = False
        for key in available:
            try:
                content, elapsed = self._single_call(
                    full_prompt, key, max_tokens, temperature, timeout_seconds,
                    force_json, response_schema=response_schema,
                )
                if use_cache and cache_key:
                    self.cache[cache_key] = (time.time(), content)
                return content
            except _DailyQuotaExhausted as e:
                last_error = str(e)
                any_quota_exhausted = True
                self.logger.warning(
                    f"📅 مفتاح OpenRouter (...{key[-8:]}) استُنفدت حصته اليومية - "
                    "تجربة المفتاح التالي (مفاتيح مختلفة = حسابات مستقلة، لا سقف مشترك)."
                )
                continue
            except _SoftFail as e:
                last_error = str(e)
                self.logger.warning(f"⏳ فشل مؤقت على مفتاح OpenRouter: {e} - تبديل للمفتاح التالي")
                continue

        if any_quota_exhausted:
            self.logger.error(
                "📅 استُنفدت الحصة اليومية على كل المفاتيح المتاحة "
                f"({len(available)} مفتاح جُرِّبوا جميعاً)."
            )
        return json.dumps({"error": f"فشلت كل محاولات OpenRouter: {last_error}"})

    # ══════════════════════════════════════════════════════════
    #  تحويل Gemini-style schema (OBJECT/STRING/enum) لتعليمات نصية
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _schema_to_instructions(schema):
        props = schema.get("properties", {})
        required = schema.get("required", [])
        lines = ["Required JSON fields and their exact types/allowed values:"]
        for name, spec in props.items():
            req_mark = " (REQUIRED)" if name in required else " (optional)"
            t = spec.get("type", "STRING")
            if "enum" in spec:
                lines.append(f'  "{name}": one of {spec["enum"]}{req_mark}')
            elif t == "OBJECT":
                sub = spec.get("properties", {})
                sub_desc = ", ".join(f'"{k}":{v.get("type")}' for k, v in sub.items())
                lines.append(f'  "{name}": {{{sub_desc}}}{req_mark}')
            elif t == "ARRAY":
                lines.append(f'  "{name}": array of strings{req_mark}')
            else:
                desc = spec.get("description", "")
                lines.append(f'  "{name}": {t}{req_mark} - {desc}')
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    #  استخراج JSON من نص حر (parsing متعدد المراحل، متسامح)
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _parse_json_text(raw):
        if not raw:
            return {"raw_response": ""}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            if "```json" in raw:
                return json.loads(raw.split("```json")[1].split("```")[0])
            elif "```" in raw:
                return json.loads(raw.split("```")[1].split("```")[0])
        except (json.JSONDecodeError, IndexError):
            pass
        try:
            s, e = raw.find("{"), raw.rfind("}") + 1
            if s != -1 and e > s:
                return json.loads(raw[s:e])
        except json.JSONDecodeError:
            pass
        # brace counting (يلتقط JSON غير مكتمل تماماً لو أمكن إغلاقه صناعياً)
        try:
            s = raw.find("{")
            if s != -1:
                candidate = raw[s:]
                opens = candidate.count("{")
                closes = candidate.count("}")
                if opens > closes:
                    candidate += "}" * (opens - closes)
                return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        return {"raw_response": raw[:500]}

    def query_json(self, prompt, **kwargs):
        """طلب مع طلب صريح لإخراج JSON + parsing قوي متعدد المراحل"""
        kwargs.setdefault("force_json", True)
        raw = self.query(prompt, **kwargs)
        return self._parse_json_text(raw)

    # ══════════════════════════════════════════════════════════
    #  query_json_race - عدة مفاتيح بالتوازي، أول جواب صالح يفوز
    # ══════════════════════════════════════════════════════════
    # ⚠️ نفس فلسفة AIClient.query_json_race القديمة (لا تصويت، لا دمج -
    # فقط أسرع جواب ناجح يُستخدم) لكن مطبَّقة على مفاتيح OpenRouter
    # المتعددة بدل مفاتيح Cloudflare. لو مفتاح واحد فقط متاح، يرجع
    # لاستدعاء عادي تلقائياً (لا فائدة من "سباق" بمتسابق وحيد).

    def query_json_race(self, prompt, response_schema, race_count=2, **kwargs):
        available = self._available_keys()
        if len(available) <= 1:
            return self.query_json(prompt, response_schema=response_schema, **kwargs)

        max_tokens = kwargs.get("max_tokens") or Config.MAX_TOKENS
        temperature = kwargs.get("temperature")
        temperature = temperature if temperature is not None else Config.TEMPERATURE
        timeout_seconds = Config.OPENROUTER_TIMEOUT_SECONDS

        full_prompt = prompt + (
            f"\n\n{'='*40}\nOUTPUT FORMAT (STRICT)\n{'='*40}\n"
            f"{self._schema_to_instructions(response_schema)}\n\n"
            "Reply with ONLY the JSON object. No markdown code fences, "
            "no explanation before or after it."
        )

        n = max(2, min(race_count, len(available)))
        lanes = [available[i::n] for i in range(n)]

        def _attempt_lane(lane_keys):
            last_error = None
            for key in lane_keys:
                t0 = time.time()
                try:
                    content, elapsed = self._single_call(
                        full_prompt, key, max_tokens, temperature, timeout_seconds, True,
                        response_schema=response_schema,
                    )
                    parsed = self._parse_json_text(content)
                    return {"success": True, "result": parsed, "elapsed": round(time.time() - t0, 1)}
                except _DailyQuotaExhausted as e:
                    last_error = f"daily_quota_exhausted: {e}"
                    continue
                except _SoftFail as e:
                    last_error = str(e)
                    continue
            return {"success": False, "error": last_error}

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=n)
        futures = {executor.submit(_attempt_lane, lane): idx for idx, lane in enumerate(lanes)}
        first_valid = None
        errors = []
        for future in concurrent.futures.as_completed(futures):
            outcome = future.result()
            if outcome["success"] and isinstance(outcome["result"], dict) and "raw_response" not in outcome["result"]:
                first_valid = outcome
                break
            errors.append(outcome)
        executor.shutdown(wait=False, cancel_futures=True)

        if first_valid:
            return first_valid["result"]

        self.logger.warning(f"⚠️ Race: فشلت كل المسارات المتوازية ({errors}) - محاولة عادية احتياطية")
        return self.query_json(prompt, response_schema=response_schema, **kwargs)

    # ══════════════════════════════════════════════════════════
    #  query_json_two_step - غير مستخدَمة فعلياً مع Nemotron (كانت
    #  خاصة بتناقض داخلي شوهد فقط مع موديلات Cloudflare معينة)، لكن
    #  محتفَظ بها كتوافق خلفي - تسقط تلقائياً لـ query_json عادي.
    # ══════════════════════════════════════════════════════════

    def query_json_two_step(self, analysis_prompt, response_schema, max_tokens=None,
                             temperature=None, use_cache=False):
        return self.query_json(
            analysis_prompt, response_schema=response_schema,
            max_tokens=max_tokens, temperature=temperature, use_cache=use_cache,
        )

    # ══════════════════════════════════════════════════════════
    #  query_json_split_parallel - تقسيم حقول مرحلة واحدة لعدة مفاتيح
    # ══════════════════════════════════════════════════════════

    def query_json_split_parallel(self, base_prompt, field_groups, timeout_seconds=None):
        """
        ينفّذ عدة استدعاءات فرعية بالتوازي لنفس المرحلة، كل استدعاء
        يطلب مجموعة حقول مختلفة من نفس الـschema الكلي، على نفس
        البيانات الخام الكاملة. يدمج كل النتائج بدمج بسيط (union).
        """
        available = self._available_keys()
        if not available:
            return {}, {"error": "لا يوجد أي مفتاح OpenRouter متاح"}

        timeout_seconds = timeout_seconds or Config.OPENROUTER_TIMEOUT_SECONDS

        def _run_sub_call(idx, group):
            key = available[idx % len(available)]
            focus_note = group.get("focus_note", "")
            sub_prompt = (
                f"{base_prompt}\n\n⚠️ FOCUSED SUB-TASK: For this specific call, "
                f"answer ONLY the fields defined in the JSON schema provided "
                f"(a subset of the full analysis). {focus_note}"
                f"\n\n{'='*40}\nOUTPUT FORMAT (STRICT)\n{'='*40}\n"
                f"{OpenRouterClient._schema_to_instructions(group['schema'])}\n\n"
                "Reply with ONLY the JSON object."
            )
            t0 = time.time()
            try:
                content, elapsed = self._single_call(
                    sub_prompt, key, Config.MAX_TOKENS, Config.TEMPERATURE,
                    timeout_seconds, True, response_schema=group["schema"],
                )
                parsed = self._parse_json_text(content)
                return {"success": True, "result": parsed, "elapsed": round(time.time() - t0, 1), "key": key[-8:]}
            except Exception as e:
                return {"success": False, "result": None, "error": str(e),
                        "elapsed": round(time.time() - t0, 1), "key": key[-8:]}

        sub_results = [None] * len(field_groups)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(field_groups)) as executor:
            future_map = {
                executor.submit(_run_sub_call, i, g): i for i, g in enumerate(field_groups)
            }
            for future in concurrent.futures.as_completed(future_map):
                i = future_map[future]
                sub_results[i] = future.result()

        merged = {}
        for r in sub_results:
            if r and r.get("success") and isinstance(r.get("result"), dict):
                for k, v in r["result"].items():
                    if k not in merged:
                        merged[k] = v

        return merged, {"sub_calls": sub_results}

    # ══════════════════════════════════════════════════════════
    #  واجهة الباك تيست المخصصة (query_json مع retry_keys ومعلومات
    #  تشخيصية تفصيلية) - نفس واجهة NemotronClient.query_json القديمة
    #  بالضبط، للحفاظ على توافق nemotron_backtest_driver.py الكامل
    #  بلا أي تعديل بمنطقه.
    # ══════════════════════════════════════════════════════════

    def query_json_with_meta(self, prompt, schema, extra_note="", max_retries=4,
                              retry_keys=None, max_tokens=None, timeout=None,
                              reasoning_effort=None):
        """
        نفس NemotronClient.query_json القديمة تماماً - تُرجع (parsed, meta)
        بدل dict وحده، مع تفاصيل تشخيصية كاملة لكل محاولة (call_log).
        """
        max_tokens = max_tokens or Config.MAX_TOKENS
        timeout_seconds = timeout or Config.OPENROUTER_TIMEOUT_SECONDS
        effort = reasoning_effort or self.reasoning_effort

        schema_instructions = self._schema_to_instructions(schema)
        full_prompt = (
            f"{prompt}\n\n{'='*40}\nOUTPUT FORMAT (STRICT)\n{'='*40}\n"
            f"{schema_instructions}\n\n{extra_note}\n"
            "Reply with ONLY the JSON object. No markdown code fences, no "
            "explanation before or after it."
        )

        keys_to_try = retry_keys if retry_keys else self._available_keys()
        if not keys_to_try:
            return None, {"error": "NO_KEYS_AVAILABLE"}

        # ⚠️ نفس الإصلاح الجذري المُطبَّق أعلاه بـquery() (راجع تعليقه
        # الكامل هناك): مفاتيح مختلفة = حسابات مستقلة تماماً، استنفاد
        # حصة مفتاح واحد لا يعني استنفاد البقية - `continue` بدل
        # `break` عند _DailyQuotaExhausted، مع تخطي هذا المفتاح تحديداً
        # بمحاولات لاحقة (keys_to_try[attempt % len(keys_to_try)] قد
        # يُعيد اختيار نفس المفتاح المُستنفَد لاحقاً بالتناوب الدائري -
        # نستبعده صراحة من قائمة التجربة بمجرد استنفاده لتفادي إهدار
        # محاولات على مفتاح نعرف يقيناً أنه سيفشل).
        last_meta = None
        exhausted_this_call = set()
        for attempt in range(max_retries):
            usable_keys = [k for k in keys_to_try if k not in exhausted_this_call] or keys_to_try
            key = usable_keys[attempt % len(usable_keys)]
            t0 = time.time()
            try:
                content, elapsed = self._single_call(
                    full_prompt, key, max_tokens, Config.TEMPERATURE,
                    timeout_seconds, True, response_schema=schema,
                )
                parsed = self._parse_json_text(content)
                meta = {"elapsed": elapsed, "finish": "stop", "raw_content_len": len(content)}
                if "raw_response" in parsed:
                    meta["error"] = "JSON_PARSE_FAILED"
                    meta["content_tail"] = content[-400:]
                    last_meta = meta
                    continue
                return parsed, meta
            except _DailyQuotaExhausted as e:
                last_meta = {"error": f"free-models-per-day (key ...{key[-8:]}): {e}", "elapsed": time.time() - t0}
                exhausted_this_call.add(key)
                continue
            except _SoftFail as e:
                last_meta = {"error": str(e), "elapsed": time.time() - t0}
                wait = 3 * (attempt + 1)
                time.sleep(min(wait, 9))
                continue
        return None, last_meta

    # ══════════════════════════════════════════════════════════
    #  إدارة عامة (نفس واجهة AIClient القديمة)
    # ══════════════════════════════════════════════════════════

    def clear_cache(self):
        self.cache.clear()

    def status(self):
        """
        ⚠️ حل جذري (يوليو 2026، بعد كراش حقيقي بـ`main.py`:
        `KeyError: 'remaining'`): النسخة السابقة من هذه الدالة كانت
        تُرجع شكلاً "مبسّطاً" مختلفاً تماماً عن الشكل الذي يتوقعه كل
        كود main.py الفعلي (5 مواضع استدعاء مختلفة - راجع `grep` الذي
        أكّد ذلك) الذي بقي مكتوباً بافتراض بنية النظام القديم متعدد
        المزودين (`ai_client_gemini_cloudflare_OLD.py::status`، حقول:
        `remaining`, `providers[name]['model'/'active_keys'/'total_keys'
        /'per_key']`). الحل الصحيح: توليد نفس البنية الكاملة المتوقعة،
        معبَّأة بقيم حقيقية من مزوّدنا الوحيد (OpenRouter) - لا نغيّر
        main.py بترقيع متفرّق بكل موضع (5 نسخ من نفس الافتراض، عرضة
        لتكرار نفس الخطأ بموضع سادس مستقبلاً)؛ بدلاً من ذلك نُصلح مصدر
        الحقيقة الوحيد (`status()`) ليطابق العقد (contract) المتوقَع.

        "remaining" تحديداً: OpenRouter لا يعرض عبر الـAPI رقماً دقيقاً
        "كم طلب متبقٍ اليوم" بشكل استباقي موحّد لكل المفاتيح دفعة واحدة
        (فقط بعد كل نداء فعلي، عبر هيدرز `X-RateLimit-*` لذاك المفتاح
        تحديداً - راجع `_single_call`، لا نخزّنها حالياً). لذا "remaining"
        هنا تقدير معقول وصادق (لا رقم دقيق مزيّف): عدد المفاتيح النشطة
        (غير المستنفَدة هذا اليوم) × 50 طلب/يوم (السقف الموثّق فعلياً
        لكل مفتاح مجاني - راجع رسائل 429 الفعلية بالسجل: `"X-RateLimit-
        Limit": "50"`)، ناقص ما استُهلك فعلياً بهذه الجلسة (`request_count`)
        - تقدير أدنى صادق (lower bound)، لا يتضمن استهلاكاً محتملاً من
        جلسات/عمليات أخرى بنفس اليوم لم تمرّ عبر هذا الكائن.
        """
        active_keys = len(self._available_keys())
        estimated_daily_cap = active_keys * 50
        remaining_estimate = max(0, estimated_daily_cap - self.request_count)

        per_key = {}
        for k in self.keys:
            label = f"...{k[-8:]}"
            per_key[label] = {
                "requests": self._key_requests.get(k, 0),
                "errors": self._key_errors.get(k, 0),
                "exhausted": self._exhausted.get(k, False),
            }

        providers = {
            "openrouter": {
                "model": self.model,
                "total_keys": len(self.keys),
                "active_keys": active_keys,
                "all_exhausted": active_keys == 0,
                "per_key": per_key,
            }
        }

        return {
            "provider_order": ["openrouter"],
            "providers": providers,
            "model": self.model,
            "total_requests": self.request_count,
            "total_cost": "$0.00 (موديل :free بالكامل - لا تكلفة أبداً)",
            "cached": len(self.cache),
            "total_keys": len(self.keys),
            "active_keys": active_keys,
            "all_exhausted": active_keys == 0,
            "remaining": (
                f"~{remaining_estimate} طلب تقديرياً "
                f"({active_keys}/{len(self.keys)} مفتاح نشط × 50/يوم لكل مفتاح - "
                f"تقدير أدنى صادق، لا رقم API دقيق مؤكد)"
            ),
            "total_completion_tokens": self.total_completion_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
        }


    def summary(self):
        """توافق خلفي مع NemotronClient.summary() القديمة (تُستخدم بـ
        nemotron_backtest_driver.py)."""
        return {
            "total_requests": self.request_count,
            "total_completion_tokens": self.total_completion_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "reasoning_effort_used": self.reasoning_effort,
        }

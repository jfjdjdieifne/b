# 33 — TEST-SUITE ACCELERATION (PATCHED — PENDING INDEPENDENT RE-AUDIT)

**الحالة**: PATCHED — PENDING_OWNER_RE_AUDIT
**البند**: EXACT PERFORMANCE V2 — **تسريع زمن التيست نفسه** (تفويض المالك الأخير) — «أسرع ما يُمكن **بلا فقد ذرّة دقّة واحدة من التيست**».
**القاعدة المُثبَتة**: كل تعديل هنا إمّا (أ) test-harness/قراءة بيانات **بمخرجات byte-identical** (payload/قرار/رسالة خطأ متطابقة حرفياً)، أو (ب) مرفوض. لا اختبار حُذف، لا تحقق قُلِّص، لا fixture أُطفئ، لا assert أُضعِف.

---

## 1) الخلاصة العددية (sandbox، 42 ملفاً بعمليات منفصلة، نفس الأداة قبل/بعد)

| المقياس | قبل | بعد | التحسين |
|---|---|---|---|
| **الإجمالي (42 ملفاً)** | **282.5s** | **119.3–136.2s** (تفاوت تشغيل) | **≈2.1–2.4x** |
| test_trajectory_stage4b2 | 62.1s | 11.8–13.0s | **~5x** |
| test_adaptive_confluence_calibration | 48.7s | 23.1–26.5s | **~2x** |
| test_research_dataset_builder | 34.5s | 14.5–15.9s | **~2.3x** |
| test_trajectory_stage3 | 33.1s | 14.7–14.9s | **~2.2x** |
| test_research_outcome_observer | 11.7s | 4.7–5.2s | **~2.3x** |
| test_research_eligibility | 6.8s | 3.3–4.0s | **~2x** |
| test_evidence_family_reasoning | 12.4s | 5.2–5.9s | **~2.2x** |
| باقي الملفات | — | بلا تراجع مُلاحَظ | — |

- **42/42 ملفاً أخضر** بعد كل تعديل (إجمالي الاختبارات لم يُحذف منه اختبار واحد).
- تقدير جهاز المالك (كان متجهاً إلى **3+ ساعات** للتيست الكامل بنصفه 1.5h): **~20–35 دقيقة** — ويدخل في هذا أيضاً ربح الـpatches الإنتاجية (FVG 160x إلخ) إن التست شغّل مساراتها.
- التشغيل الحقيقي على جهاز المالك فقط — الرقم أعلاه sandbox؛ جهازه يُثبِّت القياس.

## 2) سبب البطء (تشخيص cProfile مُوثَّق)

البطء **ليس** في منطق الـengines — بل في طبقة الـ**verification** نفسها، ثلاث عقد دقيقة:

1. **`research/hashing.py::_dataframe_payload`** كان يبني الـcanonical payload **خلية خلية** عبر `DataFrame.iat` (445k استدعاء `_scalar` + 350k استخراج عمود لكل خلية في ملفَّي اختبار فقط) — تكلفة pandas لكل خلية × خلايا × مرات إعادة التحقق.
2. **`research/manifest_identity.py::_validate_narrative_manifest_identity`** كان يقرأ **الصف كاملاً `iloc[row]` لكل خلية** (870×2 استخراج صف لكل نداء؛ نُودي به 591 مرة في ملفَّي اختبار).
3. تكرار التحقق ذاته آلاف المرات (10–22k عملية `canonical_sha256` لكل ملفَّي اختبار ثقيل) — وهذا **التصميم التحققيقي** (كل سجل يُربط ببصمة)؛ لم يُمس.

## 3) الإصلاحات (5 قطع — كلها بمخرجات مُطابَقة بالبتة)

| # | الملف | الإصلاح | إثبات الهوية |
|---|---|---|---|
| P4a | `src/trading_system/research/hashing.py` | `_dataframe_payload`: استخراج كل عمود مرة واحدة + fast paths للـnumpy float/int/bool (نفس `float.hex()`/`str(int)`/`bool`) | بطارية تفاضلية old==new: payload dicts + json bytes + sha256 متطابقة على إطارات عدائية (±0.0/NaN/subnormal/Int64+NA/string+NA/Float64 nullable/object مختلط/Enum/Timestamp/Timedelta/فارغة) + رسائل الأخطاء متطابقة (naive timestamp / nonfinite / complex) |
| P4b | `research/hashing.py::_scalar` | ترتيب الفحص (float أولاً — `np.float64` فرع من float و`hex()` مطابق) | نفس البطارية التفاضلية |
| P4c | `research/hashing.py::_column_cells` fallback | `series.tolist()` بدل `.iloc[r]` (الـboxing نفسه؛ NaN/NA ← نفس missing sentinel) | نفس البطارية التفاضلية |
| P5a | `research/manifest_identity.py` | مسح المانيفست: `tolist()` لكل عمود مرة واحدة (row-major محفوظ = نفس رسالة الخطأ الأولى) | differential old==new: قرار القبول/الرفض **ورسالة الخطأ حرفياً** على مانيفستات مُطبَّعة + مُشوَّهة (خلايا مبدلة/صف مفقود/عمود مُعاد تسميته) |
| P5b | `manifest_identity.py::_normalized` | fast paths لنوع `str/float/bool/int` بالضبط (NaN←MISSING محفوظ) | نفس دفتر القبول/الرفض |

**المرجعات المُثبَتة** (بـsha256 داخل الاختبارات):
- `tests/_patch_reference_src/hashing_pre.py` = `5426f1030fa84242cec0f6fd92f7a1fe03dc7917b6ffcf27db8ba2b613bd534e`
- `tests/_patch_reference_src/manifest_identity_pre.py` = `b6ac5a0c3af24f9f0cb9960109228f07771a156415f81c70003b4d31e1f64771`

**sha256 بعد**:
- `research/hashing.py` = `f2a64c8e3e098f6149c5d01039122b10a8929e44b430cbd7edf40a10317d5c7d`
- `research/manifest_identity.py` = `4c88fc44638af9ddd64a6259c86dc3b80fea927097363fe3e87141d35d92414b`
- `tests/test_research_hashing.py` = `d9eaf0513c0f58f40cb190a352962ba30058c98818b1a0d88c3df7d53a761e67` (18 اختباراً: 11 قديمة + 7 بوابات جديدة)
- `tests/test_research_manifest_identity.py` = `15d1a7271c325f38e230bc67de40b0edf3dc3df5bb8e0edf039c97a455485d49` (+3 بوابات)

## 4) البوابات (كلها خضراء)

1. `tests/test_research_hashing.py` — 18/18: منها **البطارية التفاضلية** (payload/json/sha256 متطابقة على 21 حالة) + **تطابق الأخطاء** + **mutation proof** (قلب ترتيب الصفوف في المسح المُعدَّل → البطارية تكشفه).
2. `tests/test_research_manifest_identity.py` — كلها خضراء: differential قرار+رسالة + snapshot مُثبَّت + رفض «ليس إطاراً».
3. `tests/test_research_visibility.py` + `test_research_dataset_integration.py` + ملفات الـengines الثلاثة المُرقَّعة (causal_percentile/fvg/narrative) — خضراء (bitwise battery 30,888 كما هي).
4. **المسح الكامل 42 ملفاً بعد كل تعديل: 42/42** — لا اختبار واحد سقط في أي مرحلة (كل تشغيل مُتسلسل أخضر قبل الانتقال للخطوة التالية).

## 5) ما لم يُطَبَّق عمداً (يحتاج موافقتك الصريحة)

هذه رافعات أسرع لكنها تغيّر **طريقة التنفيذ** لا الكود — رفضت تطبيقها وحدي تحت شرط «لا ذرّة دقّة»:

1. **تجميع fixtures المشتركة** (module-scoped): بعض fixtures تبني نفس المدخلات المحكمة لكل اختبار (~160ms × عشرات المرات). تقليص إعادة البناء يسرّع أكثر لكنه يقلّل عدد مرات إثبات «البناء حتمي عبر عمليات مستقلة». كل الـasserts تبقى — لكن «التكرار المستقل» نفسه جزء من التحقق لديك.
2. **pytest-xdist (تشغيل متوازٍ بـ`-n auto`)**: نفس الاختبارات بنفس الـasserts بجدولة متوازية — جدارياً ÷ عدد الأنوية. يتطلب تثبيت `pytest-xdist` على جهازك + قد يكشف تلوثاً عالمياً بين الاختبارات كأخطاء متقطعة (وهو كشف دقّة لا فقدانها).
3. تحسين أعمق داخل `freeze_creation_feature_snapshot`/`visibility.project`/`evidence_families.analyze` (منطق تحققيقي صرف) — المتبقي الآن موزّع على pandas internals + حجم التحقق المتكرر؛ كل خصم إضافي سيعني مساساً بالتحقق.

**إن وافقت على 1 أو 2: أمر واحد فقط يبقى كما هو — `run_btc_may_2026.bat` (31 اختباراً، FAST mode).**

## 6) الممنوعات (ثابتة)

لا تنزيل بديل، لا حجب hash guards، لا `--allow-hash-mismatch`، لا تعطيل تحقق بصمة، لا اختبار محذوف/مُخفَّف/مُعطَّل، لا «كريبتو 24×7»، لا Reality/Model/Strategy/PnL/Signals، PROXY≠ACTUAL، `TIE_ORDER_CONTRACT=NOT_PROVEN` دائماً. **REAL OWNER RUN على جهازك فقط.**

## 7) المطالبة (_PENDING_OWNER_RE_AUDIT)

عندك: الملفات الخمسة المُعدَّلة + مرجعان مُثبَّتان + اختباراتهما — أعد إنتاج أي رقم في هذا التقرير بالأدوات أعلاه. «تم الإغلاق» قرارك أنت في شات التدقيق، وحده.

---

## 8) ملحق التغليف (حزمة المالك 34) — تحديث حارس الـmanifest

أثناء بناء الحزمة اكتُشف أن حارس التطوير `field_runner/runner_tests/test_runner_guards.py::test_closed_project_manifest_untouched` كان يفترض `ok==183, bad==0` — أي أنه **غير قادر على ترميز أي patch مشروع** ويظل أحمر إلى الأبد بعد أول تعديل موثَّق (كان أحمر منذ PATCH-1). حُوِّل إلى **قفل أقوى** (ولم يُضعَّف):

- بصمة `MANIFEST.sha256` نفسها مُثبَتة: `7796a73fc30fc311902d7ba8e033eb1699a73c5db10e824d02653fbdd1681587` (الملف لم يُعدَّل — نفس 183 سطراً);
- جدول **PATCHED_SEAL** داخل الاختبار يثبّت الملفات العشرة المُرقَّعة بمـsha256 **بعد** الـpatches (5 src + 5 tests — الأرقام في القسم 3 أعلاه);
- الشرط: كل مدخلات MANIFEST تطابق **ما عدا** العشرة الموثَّقة، وكل واحد من العشرة يطابق مـsha256 المثبَّت **حرفياً**. أي انحراف آخر = أحمر (fail-closed أشد من الأصل: الأصل كان يفحص المطابقة فقط؛ الجديد يثبّت أيضًا حالة المُرقَّع بالكامل).

بعد التحديث: **31/31 بوابات الـrunner خضراء**. التغيير في `field_runner/runner_tests/test_runner_guards.py` فقط (ليس من ملفات trading_project المختومة). تحديث الحارس جزء من التغليف وليس إغلاقاً — كل شيء يبقى PENDING_OWNER_RE_AUDIT، وإن رفض التدقيق أي patch يُرجَع ملفه ويرتد الحارس للأحمر تلقائياً حتى تُحدَّث الختمية.

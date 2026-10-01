# طقم إغلاق Stage 4B-2 (CLOSURE ONLY) — يُنفَّذ بعد تفويضك الصريح

> الحالة: الأوديتور المستقل انتهى إلى **ACCEPTED FOR CLOSURE** (انظر
> `04_STAGE4B2_FINAL_AUDIT_REPORT.md`). الإغلاق ليس تلقائياً. قل كلمة صريحة
> («سكّر 4B-2») ثم يُنفَّذ ما يلي حرفياً. الإغلاق يغيّر وثائق/ختم/مانيفست فقط؛
> **يمنع منعاً باتاً** أي تعديل على `src/` أو `tests/`.

الخط الأساس الذي سيُختم: 37 مخصصة + 927 سابقة = **964 collected / 964 passed**؛
المانيفست ينتقل **166 → 170** سطراً.

---

## الخطوة 0 — بوابة ما قبل الإغلاق (يجب أن تنجح كلها)

```bash
cd trading_project
sha256sum -c MANIFEST.sha256                       # 166/166 OK
PYTHONPATH=src python3 -m pytest -o addopts="" -q   # 964 passed
sha256sum src/trading_system/research/trajectory/trajectory_stage4b2.py \
          tests/test_trajectory_stage4b2.py
# المطلوب:
# ce6fe481064c672538df63f9560493506c3b532de0de30714f71c8c4cf9ab563  ...trajectory_stage4b2.py
# 3315a6ac5c427b413f6eb510abe2486839b21d3c5a2bd0c8fde1beccf21d620b  ...test_trajectory_stage4b2.py
# 4B-1 يجب أن تبقى: bc393fe4… / 7e0c572d…
```

## الخطوة 1 — ملف الختم الجديد

أنشئ `docs/releases/MODULE_6_2A_4_V1_STAGE4B2_ACCEPTED_SRC_TESTS.sha256` بمحتوى سطرين
بالضبط (بصيغة بلا `./`):

```text
ce6fe481064c672538df63f9560493506c3b532de0de30714f71c8c4cf9ab563  src/trading_system/research/trajectory/trajectory_stage4b2.py
3315a6ac5c427b413f6eb510abe2486839b21d3c5a2bd0c8fde1beccf21d620b  tests/test_trajectory_stage4b2.py
```

## الخطوة 2 — الميلستون الجديد

أنشئ `docs/releases/MILESTONE_6_2A_4_V1_STAGE4B2_CLOSED.md` يوثّق: قرار التدقيق
(ACCEPTED FOR CLOSURE + بصمتاه)، الخط الأساس 964/964 و37 مخصصة، تاريخ الإغلاق،
ما يصدّقه الإغلاق (أربعة أسطح مشتركة منفصلة للسيولة/OB/FVG/نطاق التعامل، ربط المحركات
المغلقة عبر سطح 4B-1، FVG مستقلة، المرايا المجمّدة المحلية + الفحص الديناميكي،
البادئة رباعية المكوّنات، علم نفس-الدفعة، الكيانات المعيارية، شرعية الحدود، الجدار الناري)،
قيوده (لا يصدّق جودة تنبؤية/استقلال/هندسة/تنفيذ/4C؛ إعادة البناء شاهد لا بروفينانس؛
passthrough غير مربوط في هاش المحتوى؛ ملاحظات NON-BLOCKING)، تاريخ الترقيعات الثلاث
(تبديل المجال؛ البادئة الناقصة؛ الاستيرادات الخاصة)، والديون 020–025 OPEN.

## الخطوة 3 — تحديثات الوثائق (نصوص فقط)

- `docs/STATUS.md`: أضف سطر الحالة `6.2A-4 Stage 4B-2 CLOSED V1 (PATCHED)` + فقرة
  إغلاق كاملة على نمط فقرة 4B-1 (ماذا يصدّق/لا يصدّق، 964، الديون تبقى OPEN) + سجل
  تاريخ الإغلاق: `V1 IMPLEMENTED — PATCH REQUIRED (blockers 1+2)؛ PATCHED — PATCH
  REQUIRED (private imports)؛ V1 PATCHED — ACCEPTED FOR CLOSURE؛ V1 CLOSED`.
- `docs/FINAL_VALIDATION.md`: حدّث العدد إلى 964 collected / 964 passed (37 مخصصة:
  927+37) وأضف قسم حدود إغلاق 4B-2.
- `README.md`: في جدول الحالة أضف سطر Stage 4B-2 ✅ CLOSED وحدّث «Certified baseline»
  إلى 964/964 ومراجع الملفات.
- `PROJECT_HANDOFF_MAP.md`: حدّث كتلة الحالة والخطوة التالية (4B-2 CLOSED؛ التالي
  تصميم 4C بتفويض) والخط الأساس 964.
- `SNAPSHOT_STATUS.md`: حدّث «Authoritative closed milestone» إلى 4B-2 والعدد 964.

## الخطوة 4 — المانيفست (بعد حفظ كل الوثائق)

أضف أربعة أسطر بنفس صيغة 4B-1 (الميلستون بـ`./`، والباقي بلا `./`):

```text
ce6fe481…ab563  src/trading_system/research/trajectory/trajectory_stage4b2.py
3315a6ac…620b  tests/test_trajectory_stage4b2.py
<hash الختم>  docs/releases/MODULE_6_2A_4_V1_STAGE4B2_ACCEPTED_SRC_TESTS.sha256
<hash الميلستون>  ./docs/releases/MILESTONE_6_2A_4_V1_STAGE4B2_CLOSED.md
```

ثم أعد بصم الوثائق الخمس المتغيرة (STATUS، FINAL_VALIDATION، README، PROJECT_HANDOFF_MAP،
SNAPSHOT_STATUS) بسطورها الصحيحة داخل `MANIFEST.sha256`. أو ميكنة ذلك:

```bash
# بعد إضافة الأسطر الأربعة وتحديث الوثائق، أعد توليد بصمات كل الملفات المعتمدة فقط:
# (احرص على نفس ترتيب/صيغ المسارات المعتمدة في المشروع؛ المانيفست لا يشمل نفسه)
```

## الخطوة 5 — بوابة ما بعد الإغلاق (دليل نجاح)

```bash
sha256sum -c MANIFEST.sha256                 # 170/170 OK
PYTHONPATH=src python3 -m pytest -o addopts="" -q   # 964/964 لم تتغير
# أكّد أن بصمتي src/test قبل الإغلاق == بعده تماماً (لم يتغير الإنتاج أثناء الإغلاق):
sha256sum src/trading_system/research/trajectory/trajectory_stage4b2.py tests/test_trajectory_stage4b2.py
```

بعدها تُحدَّث خريطة الوكيل: 4B-2 CLOSED رسمياً، والمرحلة التالية الوحيدة المصرَّح
التفكير بها هي **DESIGN ONLY لـStage 4C** (لا بناء قبل اعتماد تصميم مستقل).

## نص «CLOSURE ONLY» الجاهز لإرساله لشات البيلدر/وكيل الإغلاق

```text
TASK TYPE: CLOSURE ONLY — Module 6.2A-4 V1 Stage 4B-2
Independent final audit verdict: ACCEPTED FOR CLOSURE.
You may change ONLY docs/status/release files and MANIFEST.sha256.
Do NOT modify anything under src/ or tests/. Do NOT change behavior.
Follow docs/05_CLOSURE_KIT_FOR_4B2.md steps 1..5 exactly.
Accepted hashes: src ce6fe481064c672538df63f9560493506c3b532de0de30714f71c8c4cf9ab563
                 test 3315a6ac5c427b413f6eb510abe2486839b21d3c5a2bd0c8fde1beccf21d620b
Baseline: 37 dedicated, 964 collected / 964 passed. Manifest 166 → 170.
When done, report the post-closure gate outputs and the final MANIFEST sha256.
You do NOT declare next-module authorization; Stage 4C remains NOT STARTED.
```

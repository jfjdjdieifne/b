***CLOSURE ONLY — Module 6.2A-4 V1 Stage 4B-2 (نص مُصحَّح على اصطلاح المستودع الفعلي، 2026-09-15)***

> ***تفويض المالك: أغلق Stage 4B-2 فقط. القرار المستقل السابق هو ACCEPTED FOR CLOSURE.***
>
> ***الأثر المقبول الذي يجب تثبيته قبل أي تغيير:***
>
> - ***src SHA256: ce6fe481064c672538df63f9560493506c3b532de0de30714f71c8c4cf9ab563***
> - ***test SHA256: 3315a6ac5c427b413f6eb510abe2486839b21d3c5a2bd0c8fde1beccf21d620b***
> - ***الاختبارات: 964 collected / 964 passed؛ المخصص لـ4B-2: 37 passed***
> - ***MANIFEST قبل الإغلاق: 166 سطراً، 166/166 OK، بصمته 1583cde0beb68969a49866614c9e4e5b9243bb31cf846ad816eb69397341879a***
> - ***Stage 4B-1 المغلقة تبقى كما هي: src bc393fe4…7bb708 · test 7e0c572d…01271***
>
> ***النطاق حصراً هو ما طابقته إغلاقات Stage 2/3/4A/4B-1 حرفياً — لا أكثر:***
>
> 1. ***إنشاء الميلستون: `docs/releases/MILESTONE_6_2A_4_V1_STAGE4B2_CLOSED.md` وفق قالب `MILESTONE_6_2A_4_V1_STAGE4B1_CLOSED.md` تماماً:***
>    - ***Certified baseline: 964 collected / 964 passed / exit 0؛ dedicated 37؛ الحساب 927 + 37 = 964.***
>    - ***سجل الترقيعات الكامل: IMPLEMENTED — PENDING AUDIT ← PATCH REQUIRED (سلطة المخطط/تبديل المجال؛ ربط البادئة ناقص) ← PATCHED — PENDING RE-AUDIT ← PATCH REQUIRED (استيرادات خاصة من وحدات CLOSED) ← PATCHED (private_imports_patched) — PENDING RE-AUDIT ← ACCEPTED FOR CLOSURE ← CLOSED.***
>    - ***What closure certifies: الأسطح المشتركة الأربعة المحايدة للفرضيات فقط — السيولة (2.2)، كتل الأوامر (4.1)، FVG (مستقلة بنيوياً، OHLC فقط)، نطاق التعامل (4.2B) — مع مرايا المخطط المجمدة والفحص الديناميكي، ربط البادئة رباعي المكوّنات (بار مشتق + أحداث ≤T + كيانات بموضع التوفر + أحداث معيارية)، أصناف منفصلة لكل مجال، السلامة الذاتية، حدود InformationKey، وإعادة البناء كشاهد اشتقاق فقط.***
>    - ***Accepted limitations (NON-BLOCKING): حقن عمود غريب وسط bar_frame بين passthrough والذيل المشتق يُقبل (لا يلوّث حقيقة مشتقة؛ الهاش على الذيل المشتق ومخططات الجداول دقيقة) — موصى بإحكام مستقبلي؛ بالإضافة لحدود passthrough/البروفينانس الموروثة كما في قالب 4B-1.***
>    - ***What closure does NOT certify + Open debts 020..025 + Not started (4C HTF/MTF NOT STARTED؛ descriptors/estimands/model/scorer/geometry/execution/PnL/WIN-LOSS غير مبدوأة).***
> 2. ***إنشاء الختم: `docs/releases/MODULE_6_2A_4_V1_STAGE4B2_ACCEPTED_SRC_TESTS.sha256` بسطرين فقط، بنفس صيغة ختم 4B-1 تماماً (هاش، مسافتان، مسار بلا `./`):***
>    - ***`ce6fe48…ab563  src/trading_system/research/trajectory/trajectory_stage4b2.py`***
>    - ***`3315a6ac…d620b  tests/test_trajectory_stage4b2.py`***
> 3. ***تحديث `docs/STATUS.md` فقط: سطر جدول جديد «6.2A-4 … Stage 4B-2 CLOSED V1 PATCHED»؛ أسطر سجل الانتقال على نمط 4B-1؛ فقرة حدود إغلاق 4B-2 (تثبت الأسطح الأربعة فقط؛ لا تثبت 4C/descriptors/estimands/model/geometry/execution/PnL/WIN-LOSS؛ الديون 020–025 OPEN؛ البروفينانس التوليدية NOT_CERTIFIED).***
> 4. ***تحديث `docs/FINAL_VALIDATION.md` فقط: إضافة `tests/test_trajectory_stage4b2.py: 37` (بعد سطر stage4b1 وقبل test_volume_delta)؛ TOTAL يصبح 964؛ تحديث حالة 4B-2 من NOT IMPLEMENTED إلى CLOSED؛ إبقاء 4C = NOT STARTED؛ إضافة قسم حدود إغلاق 4B-2 على نمارق قسم 4B-1.***
> 5. ***لا تلمس: `README.md`، `PROJECT_HANDOFF_MAP.md`، `SNAPSHOT_STATUS.md` — هذه مجمّدة منذ Stage 1 ولم تُحدَّث في أي إغلاق سابق (لا تعرف Stages 2–4B-1). تحديثها دَيْن توثيقي منفصل بقرار مالك لاحق، ليس جزءاً من هذا الإغلاق. لا تلمس `docs/ARCHITECTURE.md` كذلك (لم يُحدَّث في إغلاقات المراحل).***
> 6. ***تحديث `MANIFEST.sha256` أخيراً حصراً، وبهذا الشكل المتحَقَّق منه (النتيجة يجب أن تكون 170 سطراً بالضبط):***
>    - ***أعد بصم السطرين الحاليين لـ `docs/STATUS.md` و`docs/FINAL_VALIDATION.md` (نفس الموقع، صيغة بلا `./`).***
>    - ***ألحق في آخر المانيفست أربعة أسطر جديدة بنفس ترتيب وصيغة كتلة 4B-1 بالضبط:***
>      - ***`<hash>  src/trading_system/research/trajectory/trajectory_stage4b2.py`      (بلا ./)***
>      - ***`<hash>  tests/test_trajectory_stage4b2.py`                                   (بلا ./)***
>      - ***`<hash>  docs/releases/MODULE_6_2A_4_V1_STAGE4B2_ACCEPTED_SRC_TESTS.sha256`  (بلا ./)***
>      - ***`<hash>  ./docs/releases/MILESTONE_6_2A_4_V1_STAGE4B2_CLOSED.md`             (مع ./)***
>    - ***ملاحظة سبب الحساب: ملفا src/test لـ4B-2 ليسا في المانيفست حالياً (تحقَّق: grep stage4b2 = لا نتائج)؛ لذا الإضافة = src + test + ختم + ميلستون = 4 أسطر: 166 + 4 = 170. أي نتيجة غير 170 = أوقف وأبلغ.***
>
> ***محظور:***
>
> - ***أي تغيير في ملفات الإنتاج (`src/`) أو الاختبارات (`tests/`).***
> - ***أي cleanup/refactor/fix أو إعادة ترتيب أسطر المانيفست القائمة.***
> - ***معالجة ملاحظة حقن العمود الأوسط غير الحاججة أو أي دَيْن آخر.***
> - ***تعديل README / PROJECT_HANDOFF_MAP / SNAPSHOT_STATUS / ARCHITECTURE أو أي وحدة CLOSED.***
> - ***أي عمل على Stage 4C أو الديون 020..025.***
>
> ***بوابة ما قبل الإغلاق:***
>
> 1. ***`sha256sum src/trading_system/research/trajectory/trajectory_stage4b2.py tests/test_trajectory_stage4b2.py` وطابق البصمتين حرفياً.***
> 2. ***`sha256sum -c MANIFEST.sha256` = 166/166 OK؛ عدد الأسطر 166.***
>
> ***بوابة ما بعد الإغلاق:***
>
> 1. ***أثبت أن بصمتي src/test بعد الإغلاق == قبله تماماً (نفس السلسلتين حرفاً حرفاً).***
> 2. ***شغّل المخصص: `PYTHONPATH=src python3 -m pytest tests/test_trajectory_stage4b2.py -o addopts="" -q` = 37 passed.***
> 3. ***شغّل الكامل: `PYTHONPATH=src python3 -m pytest -o addopts="" -q` = 964 passed.***
> 4. ***`sha256sum -c MANIFEST.sha256` = 170/170 OK؛ عدد الأسطر 170؛ لا سطر OLD/FAILED.***
> 5. ***تحقق أن فقط: ميلستون جديد، ختم جديد، STATUS، FINAL_VALIDATION، MANIFEST هي المتغيرة/الجديدة.***
> 6. ***أعد تقريراً فيه: قائمة الملفات المتغيرة/الجديدة، بصمة المانيفست النهائية وعدد أسطره ونتيجة -c، نتيجتا الاختبارات، وإثبات بصمتي src/test قبل==بعد، وبصمتي 4B-1 كما هما.***
>
> ***حدود الإغلاق التي تظهر في الميلستون وSTATUS وFINAL_VALIDATION: Stage 4B-2 يثبت صحة أسطح الكيانات/دورات الحياة الأربعة (سيولة/OB/FVG/نطاق تعامل) ضمن عقده فقط. لا يثبت SUPPORT تنبؤياً، استقلال الأدلة، أفضلية، ربحية، احتمالاً، أوزاناً، QualificationObjective، أو أي قرار تداول. الديون RESEARCH-DEBT-020..025 تبقى OPEN. Stage 4C يبقى NOT STARTED.***
>
> ***إذا اختلفت الشجرة الفعلية أو البصمات أو المانيفست أو عدد الأسطر عن أي نقطة أعلاه: STOP — OWNER REVIEW. لا تصلح أي شيء ضمن CLOSURE ONLY.***

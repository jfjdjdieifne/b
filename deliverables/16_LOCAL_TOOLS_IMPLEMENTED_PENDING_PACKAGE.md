# LOCAL TOOLS — IMPLEMENTED — PENDING PACKAGE

النطاق: الأدوات التسعة **خارج** `trading_project/` فقط. المشروع المغلق
بت-مقابل-بت كما هو (إثبات أدناه). لا ZIP (بانتظار أمر المالك).

## الملفات التسعة وبصماتها SHA256

| # | الملف | SHA256 |
|---|--------|--------|
| 1 | `README_LOCAL.md` | `b435dbe52d4ba31e4651eea3aa8e86a7830da0365b4a409d291e0cc263b36711` |
| 2 | `setup_windows.bat` | `adc26f330777e76f5d41468d8530f3cea16444cb53648877244d497ca9150774` |
| 3 | `inspect_data.bat` | `7b27460d4640b1f6fe57138d648fc1eaa0e36b92cb16f936615e9292ccaa8540` |
| 4 | `verify_manifest.bat` | `6c3cdda761fae3847b8d40e0c423c0b149f8d4b4a4379b9544e502f3908321e2` |
| 5 | `run_tests.bat` | `e73ed677ad4b1e1bf7b41e4038d90e9f62fbc2af2e3239d220ceac16935537e2` |
| 6 | `tools/reality_inspect.py` | `f3e40c1b0615a260b975ec8e66cd4a1839c2adf769fb26c4bb4112713a4e6b95` |
| 7 | `tools/verify_manifest.py` | `c47095de150243141c442fbc064d337637d87be9ab21c8ca88aa07ccadae3a9e` |
| 8 | `data/raw/README.txt` | `34cf4dddad5212a594a6b453e2bcf25e6a62f470889709b50a9db48f71b3fbc2` |
| 9 | `outputs/README.txt` | `7892968e2331d22c98c7dfb7cad789e61c735f3ce2978c0b201cb1f979cc9b99` |

مواقعها: جذر الحزمة المستقبلي `/home/user/project/` بجوار `trading_project/` تماماً
كما اعتمد التصميم.

## تطابق واجهة المالك

- `inspect_data.bat "مسار"` + `inspect_data.bat` بدون مسار (يطلب اللصق) + سحب وإفلات.
- المسارات ذات المسافات مدعومة (اختبار: `path with spaces/my data file.csv` نجح).
- لا نسخ للبيانات — قراءة من موقع الملف الأصلي.
- التقرير حصراً في `outputs\` باسم فريد `inspect_<name>_<UTC-timestamp>.json`.
- عند النجاح: «تم الفحص بنجاح» + مسار التقرير. عند الخطأ: سبب عربي واضح + pause
  + exit code غير صفري (2=غير موجود، 3=صلاحية، 4=مجلد، 1=عام).
- كل BAT تستخدم `%~dp0` (موقعها) كأساس — تعمل من أي current working directory.
- `setup_windows.bat`: فحص Python (>=3.10 وفق pyproject) ← `.venv` خارج
  trading_project ← تحديث pip ← `pip install -e "trading_project[dev]"` ← مطابقة
  البيئة (انظر الانحراف 1) ← نجاح/فشل واضح.
- `reality_inspect.py`: stdlib فقط، streaming بذاكرة ثابتة، بلا external sort، بلا
  sets متنامية، بلا نسخة ثانية للبيانات. يخرج: المسار، البايتات وGiB، SHA256، أول/آخر
  5 أسطر، header heuristic (موسومة HEURISTIC_NOT_A_DOCUMENTED_SCHEMA_CONTRACT)،
  عدد الصفوف، توزيع عدد الحقول، أسماء محايدة col_N، empty counts، عينات محدودة،
  min/max + invalid/nonfinite numeric، وordering رقمي فقط للأعمدة integer-like
  (adjacent_decreasing / adjacent_equal) دون أي تسمية سوقية. `binance_semantics =
  NOT_VERIFIED` إجباري، وكل إحصاء يحتاج ذاكرة/فرزاً يُعلن
  `NOT_COMPUTED_MEMORY_BOUNDED`. التقرير يحوي نسخة الأداة وبصمة السكربت نفسه.

## نتائج اختبارات الأدوات (fixtures صناعية — لم تُستخدم نسخة Binance)

- **47/47 PASS** (check_tools.py): عينة سليمة (300 صف 8 أعمدة)، عينة بheader، عينة
  فاسدة (أعمدة ناقصة/زائدة/فارغة/garbage/NaN/inf/blank/تراجّع زمني)، CRLF بلا
  newline نهائي، ملف فارغ، صف واحد، مسار بمسافات، ملف غير موجود (exit 2)، مجلد
  (exit 4)، صلاحية مقروءة مرفوضة (exit 3)، صحة JSON لكل التقارير، مطابقة SHA256
  بتطبيق مستقل (sha256sum)، مطابقة بصمة الأداة الذاتية، تسميات محايدة بلا أي label
  سوقي (فحص آلي: لا price/quantity/maker/aggressor/buyer في الأعمدة).
- كشف الheader heuristic أُعيد تصميمه بعد الاختبار: مطابقة النوع عمود-بعمود بين
  السطرين (non-numeric في الأول وnumeric في الثاني ⇒ header) — لأن الفحص الأول
  (numeric-only) كان يفشل على صفوف ذات أعمدة True/False.

## قياس الذاكرة (ثبات مطلق)

| الملف | الصفوف | زمن الفحص | Peak RSS |
|---|---|---|---|
| 20 MB | 234,980 | 3.5 ث | **25.1 MB** |
| 200 MB | 2,274,540 | 32.0 ث | **25.1 MB** |

10× حجماً ⇒ **صفر نمو في الذاكرة** — streaming مثبت عملياً.

## اختبار تدفق setup على نسخة معزولة (venv نظيف)

`python -m venv` ← `pip install --upgrade pip` ← `pip install -e "trading_project[dev]"`
← `pytest tests/test_trajectory_stage4c.py` = **36 passed** ← full suite =
**1000 passed in 348.06s** على النسخة. التدفق كامل يعمل.

## الانحرافات المعلَنة (كلها موثقة — لا مساس بـCLOSED)

1. **انجراف pandas 3.x (اكتشاف مهم):** `pip install -e "trading_project[dev]"` وحده
   يحل pandas 3.0.6 حديثاً، وهذا يكسر **12 اختباراً معتمَداً** (تغيّرت دلالات
   datetime indexing في pandas 3؛ الشهادة كانت على pandas 2.2.3). الحل دون لمس
   CLOSED: أُضيفت خطوة `[5/5]` في setup تُطابق pandas على السلسلة المعتمَدة
   (`"pandas>=2.0,<3"` ⇒ 2.3.3) — أمر pip المُفروض موجود حرفياً في `[4/5]` قبلها.
   بمجرد اعتماد مالك لاحق يمكن تثبيت السقف داخل `pyproject.toml` عبر `PATCH ONLY`
   إصداري — ليس ضمن هذه الباقة.
2. ملفات BAT لا يمكن تنفيذها على Linux (بيئة البناء): اختبرت الأوامر الداخلية
   نفسها حرفياً (نفس الأوامر pip/pytest)؛ المالك يجرّب الـBAT مرة واحدة عند أول
   استخدام. الأزرار بسيطة (3-5 أسطر تستدعي Python).
3. `reality_inspect.py` يقرأ الملف في تمريرتين (hash/توزيع/header ثم حالة
   الأعمدة) — قراءتان لا نسخة؛ الذاكرة ثابتة بالميجابايت.
4. كشف الheader «heuristic» دائماً في التقرير — لا يوجد عقد schema موثّق.

## بوابة عدم المساس (كلها خضراء)

- `trading_project/` قبل == بعد: **IDENTICAL — 183 ملفاً، صفر تغيير** (diff كامل).
- `MANIFEST.sha256`: `ac4d6f03e457695da1b3132856c424ffe5bc043d8545b5cce279fce856c51706`
  — **174/174 OK** (工具 verify_manifest.py نفسها أكّدت 174/174 على المشروع الحقيقي).
- dedicated = **36/36 passed** · full = **1000 passed** (366.89s) على المشروع الحقيقي.
- الوحدات CLOSED لم تُلمس (داخل الـ183 المتطابقة + المانيفست 174/174).

## حالة الحزمة

- لا ZIP أُنشئ (ممنوع حتى أمر صريح).
- `data/` و`outputs/` و`.venv/` والكاشات وegg-info خارج الأثر المغلق تماماً.
- نسخة Binance scratch لم تُحلَّل ولن تُدرَج.

**STOP — بانتظار أمر المالك: PACKAGE + ZIP.**

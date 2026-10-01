# LOCAL PACKAGE DESIGN — PENDING OWNER APPROVAL

الحالة: تصميم فقط — لا بناء، لا ZIP حتى اعتماد المالك الصريح.
البيانات: مانيفست المشروع `ac4d6f03…` 174/174 لم يتغير (إثبات read-only بعد إيقاف Phase-0).
مصادر حقيقية من `pyproject.toml` (لا تخمين): `requires-python = ">=3.10"` ·
`dependencies = ["numpy>=1.24", "pandas>=2.0", "tzdata>=2024.1"]` · `dev = ["pytest>=8"]` ·
لا يوجد requirements.txt — التثبيت الفعلي = `pip install -e ".[dev]"`.
بيئة البناء المُختبرة فعلياً: Python 3.13.14.

## 1. الملفات الجديدة المقترحة (9 ملفات صغيرة فقط)

| الملف | الوظيفة |
|---|---|
| `README_LOCAL.md` | دليل المالك بالعربية من الصفر: تثبيت Python ← PowerShell ← الإعداد ← الفحص ← مكان التقرير ← الاختبارات |
| `setup_windows.bat` | إعداد مرة واحدة: `.venv` + تثبيت تبعيات المشروع من `pyproject.toml` نفسه (`pip install -e "trading_project[dev]"`) |
| `inspect_data.bat` | تشغيل الفاحص على أي مسار (خارجي مطلق أو داخل `data/raw/`) |
| `verify_manifest.bat` | بديل Windows لـ`sha256sum -c MANIFEST.sha256` |
| `run_tests.bat` | `run_tests.bat dedicated` (4C-1: 36) و`run_tests.bat` (الكاملة 1000) |
| `tools/reality_inspect.py` | فاحص streaming بمكتبة Python المدمجة فقط (صفر تبعيات): SHA256 للملف + تقرير JSON صغير |
| `tools/verify_manifest.py` | فاحص MANIFEST (Windows/Linux بنفس الكود) |
| `data/raw/README.txt` | رسالة "ضع ملفك هنا أو مرّر مساراً مطلقاً" — المجلد يبقى فارغاً |
| `outputs/README.txt` | "التقارير تُكتب هنا" — يبقى فارغاً |

غير مضمَّن الآن (لاحقاً بعد اعتماد اقتراح التحويل): `tools/aggtrades_to_ohlc1m.py`.
هذه الباقة = فحص فقط. لا PnL ولا استراتيجية ولا نموذج.

## 2. أين ستوضع (بنية الـZIP)

```
ZIP ROOT
├── README_LAST_STATE.md        (كالسابق)
├── README_LOCAL.md             ← جديد
├── setup_windows.bat           ← جديد
├── inspect_data.bat            ← جديد
├── verify_manifest.bat         ← جديد
├── run_tests.bat               ← جديد
├── tools/                      ← جديد
├── data/raw/                   ← جديد (فارغ — صندوق بيانات المالك)
├── outputs/                    ← جديد (فارغ — التقارير تُكتب هنا)
├── reports/                    (كالسابق)
└── trading_project/            (كما هو حرفياً)
```

كل الجديد بجوار `trading_project/` لا بداخله — الشجرة المغلقة مقدسة.

## 3. هل أي ملف حالي يحتاج تعديلاً؟ NO

صفر تعديل: لا `src/` ولا `tests/` ولا `docs/` ولا `MANIFEST.sha256` (يبقى
`ac4d6f03e457695da1b3132856c424ffe5bc043d8545b5cce279fce856c51706` بـ174 سطراً كما هو).
لا تغيير أي دلالة مشروع. الوحدات CLOSED لا تُلمس ولا تُعاد تصميمها.

## 4. أوامر Windows النهائية للمالك

```bat
:: 1) ثبّت Python 3.10+ من python.org مع تعليم "Add python.exe to PATH"
:: 2) افتح PowerShell داخل مجلد الـZIP ونفّذ مرة واحدة:
setup_windows.bat

:: 3) افحص ملفك الضخم (مسار خارجي — لا حاجة لنسخه):
inspect_data.bat "D:\MarketData\BTCUSDT-aggTrades-2026-05.csv"
:: أو ضعه في data\raw\ ثم:
inspect_data.bat data\raw\BTCUSDT-aggTrades-2026-05.csv

:: 4) التقرير الصغير (JSON) يظهر في:
::    outputs\inspect_<اسم الملف>_<وقت UTC>.json

:: 5) التحقق من سلامة المشروع:
verify_manifest.bat

:: 6) الاختبارات:
run_tests.bat dedicated
run_tests.bat
```

## 5. كيف تبقى البيانات خارج الأثر المغلق

- الفاحص يقبل absolute path — الملف يبقى على القرص الخارجي ولا يُنسخ (لا حاجة لـ1.69GB داخل المشروع).
- `data/` و`outputs/` و`.venv/` و`__pycache__` و`.pytest_cache` و`*.egg-info`:
  ليست جزءاً من الأثر البحثي المغلق، لا تُدرَج في MANIFEST ولا في ZIP.
- معالجة streaming سطر-بسطر/دفعات بذاكرة ثابتة — لا تحميل الملف في RAM.
- تقرير الفحص inspection فقط: أسماء أعمدة محايدة `col_1..col_8` + وسم
  `binance_semantics: NOT VERIFIED` — لا ادعاء معنى (price/aggressor/buyer-maker)
  قبل توثيق عقد المصدر. التفسير خطوة منفصلة لاحقة.

## 6. كيف نتحقق أن إضافة الأدوات لم تغيّر أي CLOSED

1. بصمات كل ملفات `trading_project/` قبل البناء (207 ملفات) == بعد البناء (فرق صفر).
2. `sha256sum -c MANIFEST.sha256` = 174/174 OK وبصمته `ac4d6f03…`.
3. بصمات 4B-2/4B-1/4A مطابقة لأختام `docs/releases/*_ACCEPTED_SRC_TESTS.sha256`.
4. إعادة تشغيل dedicated 36/36 + full 1000/1000 كاملة.

## 7. اختبار الأداة قبل إنشاء ZIP (عينة aggTrades صغيرة فقط)

1. توليد عينة صناعية ~200 سطر بنفس البنية المُرصودة (8 أعمدة، بلا header،
   timestamps ميكروثانية) + حالات حدّية: فجوة دقيقة، timestamps مكررة، نفس
   timestamp لعدة صفوف، صف غير صالح، CRLF، مسار فيه مسافة.
2. تشغيل الفاحص عليها والتحقق من كل حقول JSON (SHA256، العدّادات، البصمة الزمنية).
3. اختبار ذاكرة على ملف صناعي متوسط وإثبات RAM ثابتة (لا يُمس ملف Binance).
4. `.bat` ملفات بسيطة (3 أسطر تُنادي Python) — يُختبر محتواها على Linux بنفس
   الأوامر، والمالك يجرّبها مرة واحدة محلياً.
5. نسخة Binance المنزلة سابقاً (scratch خارج المشروع) لن تُحلَّل ولن تُدرَج في ZIP.

---

**الخطوة التالية:** بعد اعتماد المالك → بناء الأدوات + اختبار العينة + تقرير تحقق →
ثم ZIP بأمر صريح. لا قبل ذلك.

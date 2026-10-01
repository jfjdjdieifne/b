# LOCAL PACKAGE — READY FOR OWNER

الحالة: **PACKAGE + ZIP مكتملان** — الأدوات التسعة المقبولة لم تُلمس (تحقق حرفي قبل
التغليف: `ALL NINE MATCH LITERALLY`)، ولا ملف داخل `trading_project/` تغيّر.

## ملف ZIP القابل للتنزيل

```text
المسار   : /home/user/causal_trading_research_4c1_closed_local_windows.zip
الاسم    : causal_trading_research_4c1_closed_local_windows.zip
الحجم    : 741,366 بايت (0.71 MiB)
SHA256   : 5498b9efa4040631f6c90f783ea3bcf79095a0b0dc8a9487664c78e9017f843b
المحتوى  : 210 ملفاً + 29 مجلداً
```

## بنية جذر الـZIP

```text
README_LOCAL.md  setup_windows.bat  inspect_data.bat  verify_manifest.bat  run_tests.bat
PACKAGE_SHA256SUMS.txt     (metadata للحزمة — ليس جزءاً من المشروع المغلق)
tools/           (reality_inspect.py + verify_manifest.py)
data/raw/        (README.txt فقط)
outputs/         (README.txt فقط)
reports/         (22 وثيقة تاريخية رسمية — قرار إدراج موثّق أدناه)
trading_project/ (178 ملفاً — المشروع المغلق كما هو)
```

`PACKAGE_SHA256SUMS.txt` يحوي SHA256 لكل الملفات الموزعة (209 سطراً — بدون نفسه)،
ولم يُعدَّل أي ملف من التسعة لإضافته.

## نتائج الاستخراج النظيف والتحقق (مجلد جديد فارغ)

| الخطوة | النتيجة |
|---|---|
| `sha256sum -c PACKAGE_SHA256SUMS.txt` | **209 / 209 OK** |
| `trading_project/MANIFEST.sha256` | **174 / 174 OK** |
| SHA256 للمانيفست | `ac4d6f03e457695da1b3132856c424ffe5bc043d8545b5cce279fce856c51706` ✓ |
| `tools/verify_manifest.py` من الحزمة المستخرجة | **174 / 174 OK — سلامة المشروع مؤكدة** |
| الأدوات التسعة المستخرجة مقابل البصمات المقبولة | **ALL NINE MATCH** |
| المسح الآلي للمحظورات في ZIP | **CLEAN** |
| ملفات CSV خارج `trading_project/docs/` | **CLEAN** (الوحيد `ICT_SOURCE_MATRIX.csv` وهو سطر 12 في المانيفست — وثيقة دومين مغلقة وليست بيانات سوق) |
| `data/` و`outputs/` | README.txt فقط ✓ |

## تأكيد عدم وجود المحظورات

لا `.venv/` · لا بيانات BTC أو aggTrades · لا ZIP بيانات Binance · لا scratch من
Phase-0 · لا `__pycache__/` · لا `.pytest_cache/` · لا `*.pyc` · لا `*.egg-info` ·
لا probes/fixtures/تقارير اختبار مؤقتة · لا ملفات JSON.

ملاحظة شفافة: 5 ملفات `src/causal_trading_system.egg-info/*` (مخلّفات تثبيت
editable) **استُبعدت** وفق قرارك — تحققت أنها ليست في MANIFEST إطلاقاً، لذا
الـ174/174 سليم بدونها.

## قرارات الإدراج (موثقة)

- **`reports/` أُدرِج** (22 وثيقة رسمية: design/patch/builder/closure/audit) — جزء
  مقصود من التسليم كما في التصميم المعتمد، وليس scratch.
- **`README_LAST_STATE.md` استُبعد**: محتواه تاريخي قديم (يقول 4B-2 pending و
  4C not started) وهو غير صحيح الآن، والتعديل ممنوع في نطاق PACKAGE+ZIP فقط.
  إن أردته محدّثاً فذلك PATCH لاحق بأمرك.
- **`project.zip` استُبعد** (قديم/زائد عن المطلوب).

## ملاحظات تشغيلية

- **أول اختبار فعلي لملفات BAT على Windows سيكون على جهاز المالك** — لم تُشغَّل
  على Windows فعلياً في بيئة البناء (Linux). الأوامر الداخلية (pip/pytest/Python)
  مُختبرة بالكامل: dedicated 36/36 + full 1000/1000 على نسخة معزولة بـvenv نظيف.
- لا يُعاد full suite (لا ملف تغيّر؛ بصمات الحزمة تثبت التطابق مع نسخة الاعتماد).
- تذكير: `setup_windows.bat` يتضمن خطوة `[5/5]` لمطابقة pandas على السلسلة
  المعتمَدة `>=2.0,<3` (بدونها تفشل 12 اختباراً معتمَداً على pandas 3.x) — كما
  وثّقته في تقرير الأدوات.

## الالتزام بالحدود

لم يبدأ تحويل OHLC ولا Reality Check ولا Stage 4C-2. المشروع المغلق
بت-مقابل-بت (174/174 + بصمات مطابقة). **STOP.**

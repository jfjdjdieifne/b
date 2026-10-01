# LOCAL PACKAGE V2 — READY FOR OWNER

**التقرير 20 — بيلدر | 2026-09-27 (دمشق)**
**المهمة**: LOCAL PACKAGE V2 — ADD MINUTE CONVERTER — **PACKAGE ONLY**
**الحالة**: **READY FOR OWNER** — لم تبدأ أي مرحلة تالية.

> **TIE_ORDER_CONTRACT = NOT_PROVEN** (قيد إلزامي مثبَّت): أي open/close في دقيقة يكون فيها
> أول/آخر `transact_time_us` ذا أسعار متعددة هو **deterministic convention فقط**، وليس
> market chronology مثبتة. `open_ambiguous` / `close_ambiguous` إلزاميان.
> **ممنوع لاحقاً** تمرير open/close المبهم إلى المشروع الرسمي كحقيقة OHLC مؤكدة قبل قرار
> Adapter رسمي.

---

## الحزمة

| البند | القيمة |
|---|---|
| **المسار** | `/home/user/causal_trading_research_4c1_local_v2.zip` |
| **الحجم** | **753,556 بايت** |
| **SHA-256** | `779d66c1eacce27a1c12638ca07154c12648d66a6639c39c3f5d24fc4b4bca26` |
| **عدد الملفات** | **214** (213 موزَّعة + `PACKAGE_SHA256SUMS.txt` نفسه) |

**المحتوى** = حزمة V1 حرفياً (209 ملفاً — **كلها مطابقة بايتياً** لـV1، صفر اختلاف) + الأربعة الجديدة:

| الملف الجديد | SHA-256 |
|---|---|
| `tools/aggtrades_to_minute_facts.py` | `0048779bd821dbe6f3cda66517b19e7435fc0b98592ee9aa1980804fe27efb5d` |
| `tools/tests_local/test_aggtrades_to_minute_facts.py` | `b433546938a95187cfd65a8811fbb4fe54c8bb615b37c2bbb3fc12f54afe323e` |
| `convert_aggtrades.bat` | `06cc54769cfaf92e4500776e0214e4ed0f1291d8a5e2e1afe9f60178e34b4ed2` |
| `tools/README_CONVERTER.md` | `634d3c078f9462bdebc66524e19121ac3388ab6d2c706de58c9d56a7a3e428eb` |

`PACKAGE_SHA256SUMS.txt` محدَّث: **213/213** مدخلاً (كل الملفات الموزَّعة باستثناء نفسه)،
بصيغة V1 نفسها (`sha256  path` مرتَّبة). `trading_project/` كما هو حرفياً (178 ملفاً = 174 MANIFEST + 4 ملحقات — كما في V1).

## نتائج إعادة الاستخراج والتحقق (مجلد نظيف — ثم حُذف)

| # | الفحص | النتيجة |
|---|---|---|
| 1 | SHA256 للـZIP | `779d66c1eacce27a1c12638ca07154c12648d66a6639c39c3f5d24fc4b4bca26` ✓ |
| 2 | الاستخراج في مجلد نظيف | **214/214** ملفاً ✓ |
| 3 | `PACKAGE_SHA256SUMS` بالكامل | **213/213 OK** ✓ |
| 4 | `trading_project/MANIFEST.sha256` | **174/174 OK** ✓ |
| 5 | بصمة المانيفست | `ac4d6f03e457695da1b3132856c424ffe5bc043d8545b5cce279fce856c51706` ✓ مطابق حرفاً |
| 6 | بصمة converter المستخرج | `0048779bd821dbe6f3cda66517b19e7435fc0b98592ee9aa1980804fe27efb5d` ✓ مطابق حرفاً |
| 7 | بصمة test converter المستخرَج | `b433546938a95187cfd65a8811fbb4fe54c8bb615b37c2bbb3fc12f54afe323e` ✓ مطابق حرفاً |
| 8 | المنعات في ZIP | **PROHIBITED: 0** ✓ |

**تفصيل المنعات (8)**: صفر `__pycache__` / `.pyc` / `.venv` / `.pytest_cache` / `egg-info` /
`.mut_check` / mutation copies / scratch / ملفات قياس كبيرة / outputs مولَّدة / أي ملف
BTC-Binance (`BTCUSDT`, `-aggTrades-`, MarketData). CSV الوحيد داخل ZIP =
`trading_project/docs/domain_audit/ICT_SOURCE_MATRIX.csv` (محتوى مشروع داخل MANIFEST —
ليس بيانات سوق). `outputs/` يحوي `README.txt` فارغاً فقط (كما في V1).

## مقارنة V1 ↔ V2

- only-in-V2: الملفات الأربعة الجديدة أعلاه (بالضبط).
- only-in-V1: **لا شيء** (لا حذف).
- الـ209 ملفاً المشترك: **صفر اختلاف** في البصمات.

## ما لم يُمَس

- converter: لم يُعدَّل (بصمته المطلوبة كما هي).
- `trading_project`: صفر تغيير (174/174 بالمحتوى + البصمة الذاتية مطابقة).
- لا Source Adapter / لا Reality Check / لا مرحلة تالية.

**STOP — LOCAL PACKAGE V2 — READY FOR OWNER.**

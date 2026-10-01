# LOCAL MINUTE PIPELINE — IMPLEMENTED — PENDING OWNER RUN

**التقرير 19 — بيلدر | 2026-09-27 (دمشق)**
**المهمة**: LOCAL MINUTE PIPELINE — BINANCE SPOT AGGTRADES → 1-MINUTE FACT TABLE (DESIGN + BUILD + ADVERSARIAL TESTS)
**الحالة**: **IMPLEMENTED — PENDING OWNER RUN** (تحويل فقط — لم يُشغَّل ملف المالك قط)

> **REUSED EXISTING PROJECT ENGINES: NONE YET — SOURCE CONVERTER BOUNDARY ONLY.**

> **ENGINES TO BE REUSED AFTER OFFICIAL ADAPTER: existing CLOSED project engines; they MUST NOT be reimplemented by this converter.**

---

## 1) الحالة والتغطية

- بُني المحوّل + اختبارات معاكسة + BAT + README، ونُفِّذ كل القياسات على **بيانات اصطناعية يدوية/مولَّدة** (fixtures + gen).
- ملف المالك `BTCUSDT-aggTrades-2026-05.csv` **لم يُشغَّل** (قرار صريح — التشغيل للمالك على جهازه).
- لا Reality Check / لا نموذج / لا استراتيجية / لا PnL / لا 4C-2 / لا مساس بـCLOSED.
- لا استيراد أو إعادة تنفيذ أي محرك مشروع (حرس AST في الاختبار).

## 2) BLOCKER/TIE — الحكم المطلوب

**`TIE_ORDER_CONTRACT = NOT_PROVEN`**

مصدر الدليل (بحث ويب موثّق):
1. REST (General) الرسمي: «Data is returned in **chronological order**, unless noted otherwise» — عقد **ترتيب قوائم الاستجابة** فقط.
2. WS API الرسمي (fromId): «Use fromId and limit to **page through all aggtrades**» — `agg_trade_id` هو مفتاح الترقيم/التنقل المعتمد.
3. Changelog 2022-04-12: مراقبة الفجوات والتكرارات بهذا المفتاح.
4. **لا يوجد أي نص رسمي** يضمن ترتيب `agg_trade_id` كترتيب زمني للسوق داخل `transact_time_us` متساوٍ.

**السياسة المطبَّقة (البديل المُصرَّح به مسبقاً — ambiguity metadata، دون إضعاف أي عقد):**
- قيم open/close تُنتَجان **deterministic** بترتيب `(transact_time_us, agg_trade_id)`.
- الدقيقة التي يحتوي timestamp الطرف فيها على **أكثر من سعر مختلف** تُعلَّم:
  `open_ambiguous` / `close_ambiguous` (0/1) + `open_tie_distinct_prices` / `close_tie_distinct_prices` + counts في sidecar.
- القيم المعلَّمة = **اتفاقية إخراج deterministic** وليست chronology سوق مثبتة (موسومة صراحةً في `tie_order_policy`).
- **high/low/base/quote/flows/count مطابقة تماماً** في كل الحالات (لا غموض فيها أصلاً).
- لم يُغلق أي شيء: «منع OHLC الصحيح» غير متحقق — الترميز المعلَّم يحفظ كل المعلومات دون ادعاء كاذب.

## 3) الملفات الجديدة (الأربعة فقط) + بصماتها

| المسار | SHA-256 | البايتات |
|---|---|---|
| `project/tools/aggtrades_to_minute_facts.py` | `0048779bd821dbe6f3cda66517b19e7435fc0b98592ee9aa1980804fe27efb5d` | 25,012 |
| `project/tools/tests_local/test_aggtrades_to_minute_facts.py` | `b433546938a95187cfd65a8811fbb4fe54c8bb615b37c2bbb3fc12f54afe323e` | 22,588 |
| `project/convert_aggtrades.bat` | `06cc54769cfaf92e4500776e0214e4ed0f1291d8a5e2e1afe9f60178e34b4ed2` | 1,304 |
| `project/tools/README_CONVERTER.md` | `634d3c078f9462bdebc66524e19121ac3388ab6d2c706de58c9d56a7a3e428eb` | 2,519 |

الأداة الوحيدة المستهدفة = `aggtrades_to_minute_facts.py` (stdlib فقط). سطر التشغيل كما طلبت:
```bat
python tools\aggtrades_to_minute_facts.py "D:\MarketData\BTCUSDT-aggTrades-2026-05.csv"
```
(أو `convert_aggtrades.bat "..."`، و`--out prefix` اختياري؛ المسارات بمسافات مدعومة؛ الناتج الافتراضي `outputs\minute_facts_<stem>.csv`.)

## 4) عقد الإدخال والتحقق (FAIL CLOSED)

لكل صف: 8 حقول بالضبط؛ أعداد صحيحة صارمة (regex؛ لا `+`/مسافات/floats)؛ decimals منتهية (≤8 خانات)؛ bool ∈ {True,False} حرفياً؛ `transact_time_us` غير متناقص؛ `agg_trade_id` **متزايد strict** على الصفوف القانونية (sentinel مستثنى من فحص الترتيب)؛ سعر/كمية > 0؛ `0 ≤ first ≤ last`. أي كسر ⇒ فشل فوري + رقم الصف + صنف الخطأ، بلا skip/repair/coercion/sort صامت، وبلا CSV ناجح جزئي (ملف `.tmp` يُحذف + `.FAILED.json` + exit=3).

أصناف الأخطاء: `FIELD_COUNT, AGG_ID_INVALID, AGG_ID_DUPLICATE, AGG_ID_DECREASING, PRICE_INVALID, QTY_INVALID, TRADE_ID_INVALID, IDENTIFIER_INVALID, TIMESTAMP_INVALID, TIMESTAMP_DECREASING, BOOL_INVALID, RECONCILIATION_FAILED`.
رموز الخروج: 0 نجاح | 2 استخدام/ملف مفقود | 3 فساد (fail-closed).

## 5) عقد الدقيقة والحدود الزمنية

`minute_bucket = floor(transact_time_us / 60_000_000)`؛ العقد **[start, end)** على trade timestamps (اختبار الحد: صف عند `:59.999999` يبقى، صف عند `+1:00.000000` ينتقل). لا تُدَّعى إتاحة إغلاق الدقيقة:
`bar_close_availability = NOT_CLAIMED_BY_CONVERTER` — **membership ≠ availability**.

## 6) أعمدة المخرج والتسمية

`minute_start_utc, minute_end_utc (=start+60s), open, high, low, close, base_volume, quote_volume, agg_trade_count, buy_initiated_base_volume, sell_initiated_base_volume, buy_initiated_quote_volume, sell_initiated_quote_volume, executed_base_delta, executed_quote_delta, first_agg_trade_id, last_agg_trade_id, first_transact_time_us, last_transact_time_us, open_ambiguous, close_ambiguous, open_tie_distinct_prices, close_tie_distinct_prices` + حقول توثيقية في sidecar.

- التسمية **executed/initiated flow فقط** (`is_buyer_maker=False` ⇒ buy_initiated): ممنوعات «buying pressure / order-book pressure / institutional / whale / market-wide order flow / order-book imbalance» **غير موجودة** في الملفات (حرس scan في test_33).
- `agg_trade_count` = عدد الصفوف القانونية فقط؛ **لا `trade_id_span`** (استُبعد كما فضّلت).
- `is_best_match` ليس feature — counts تشخيصية في sidecar فقط.
- ملف CSV: header إنجليزي؛ serialization deterministic (fixed-point format، لا scientific).

## 7) التمثيل العددي

**Integer fixed-point** من النص الأصلي (لا binary float في أي تجميع): price/base scale=8، quote scale=16 (=8×8 عبر حاصل ضرب صحيحين). الاقتباسي مشتق: `Σ (price_i × qty_i)` بالصحيح. تنسيق ثابت `%.8f`/`%.16f` مبني على أرقام صحيحة. الاختبار 21 يضرب متجه float-trap (حاصل ضرب > 2^53 في وحدات scale-16) — أي مسار float يُكشف (أُثبت بـM2).

## 8) sentinel الرسمية

قاعدة Changelog 2022-04-12 (`p=0 AND q=0 AND f=-1 AND l=-1`): تُتحقق الحقول أولاً (فسادها = fail-closed)، ثم تُعد وتُسجَّل (row/agg_id/ts حتى 1000) في sidecar، **تُستثنى من aggregation ومن فحص الترتيب**، ولا تُحذف بصمت (`legal_rows_consumed + sentinel = source_rows_total`). ملف sentinel-only ⇒ نجاح، 0 صفوف قانونية، 0 دقائق.

## 9) الدقائق الفارغة

غائبة تماماً — **لا synthetic/forward-fill/close-carry**. sidecar: `covered_calendar_minute_count`, `missing_minute_count`, `missing_minute_intervals` (بحد 1000 فاصل + flag اقتطاع)، `first/last_output_minute`.

## 10) Sidecar JSON (كامل حسب العقد)

converter name/version/sha256 · source path/bytes/sha256 · `source_contract = BINANCE_SPOT_PUBLIC_DATA_AGGTRADES` · schema version + مراجع التوثيق الأربعة · `timestamp_unit = MICROSECONDS` · كل counts (legal/sentinel/best-match/ties/ambiguous) · **reconciliation exact** (Σ base/quote المصدر = المخرج byte-string مطابق؛ buy+sell=total؛ Σ count = legal rows) · `TIE_ORDER_CONTRACT = NOT_PROVEN` + evidence + policy · numeric_representation · minute_interval_contract · bar_close_availability · executed_flow_semantics · `output_csv_sha256` · `generated_at_utc` منفصل عن identity · historical_provenance_statement (دون توسيع). انبعاث atomic (tmp ثم rename)؛ نجاح يحذف `.FAILED.json`.

## 11) الاختبارات المعاكسة — **35/35 PASSED** (2.34 ث)

تغطية حسب قائمتك: صف BUY/SELL · OHLC يدوي · حدود الدقيقة · tie (سعر واحد = غير مبهم / أسرار مختلفة = مبهم deterministic) · قرار TIE مسجَّل · sentinel · فساد (field/price/qty/ts/bool) × حالات متعددة لكل منها · تناقص ts · id مكرر/تناقصي · فجوة دقائق + intervals · لا synthetic bar · reconciliations base/quote · float-trap · counts بلا feature · مسار بمسافات · ملف فارغ · صف واحد · first/last minute · SHA256 المصدر والمخرج · مفاتيح sidecar الإلزامية · ذاكرة محدودة (RLIMIT_AS 256MB على 20k صف) · determinism (مرتان: CSV byte-identical + sidecar متساوي عدا generated_at/المسار) · تماثل التقطيع على البادئة · عدم تسريب المستقبل · حارس التسمية · لا استيراد محرّكات (AST) · بصمة الذات/الإصدار. Fixtures يدوية بالكامل (بلا ملف المالك).

## 12) إثباتات الطفرات الأربع (على نسخ مؤقتة ثم حُذفت)

| الطفرة | ما كُسر عمداً | الاختبار الكاشف | النتيجة |
|---|---|---|---|
| M1 BUY/SELL swap | `buy = not bmm` → `buy = m` | test_01/02 | **فشل الاختبار = كُشفت** ✓ |
| M2 float مكان fixed-point | `q_quote = int(float(p)*float(q))` | test_21 | **كُشفت** ✓ |
| M3 synthetic bar | إدراج صفوف صفرية للفجوات | test_18/17 | **كُشفت** ✓ |
| M4 minute boundary | `(ts+1)//MIN` | test_05 | **كُشفت** ✓ |

السجل: `.mut_check/mutation_proofs.json` — النسخ الأربعة حُذفت بالكامل (`ALL_MUTANT_COPIES_DELETED: True`).

## 13) الذاكرة والحجم (بذاكرة محدودة — streaming)

مولّد gen_big بنمط chunked (50k سطر/كتابة) على أرضية دائمة:

| الملف | البايتات | الصفوف | زمن التحويل | Peak RSS |
|---|---|---|---|---|
| 20 MB | 17,130,666 | 220,000 | 2.58 ث | **30,748 KB** |
| 200 MB | 171,306,666 | 2,200,000 | 20.66 ث | **30,748 KB** |

**فرق الذروة بين 20MB و200MB = 0 KB** (قياس RUSAGE_CHILDREN) — ذاكرة ثابتة مستقلة عن حجم الملف (وهذا يغطي ملف المالك 1.8GB حجماً: لا sort، لا تجميع كامل، حالة دقيقة واحدة + run واحد). الملفات الكبيرة حُذفت بعد القياس.

## 14) Determinism والبنية العامة

- تشغيلان لنفس المصدر: **CSV byte-identical**؛ sidecar متساوي عدا `generated_at_utc` ومسار المخرج.
- التقطيع عند حد دقيقة: الدقائق المشتركة المكتملة **byte-equal** بين النسختين (اختبار pytest 31 + قياس 20MB).
- عدم تسريب المستقبل: صفوف الدقائق السابقة لا تتغير بإضافة صفوف لاحقة (test 32).
- ملف فارغ ⇒ نجاح 0 دقائق | صف واحد ⇒ دقيقة واحدة OHLC متساوٍ | first/last minute صحيحة (minute 2026-05-31T23:59:00 لآخر صف في عيّنة المالك المُبلَّغ عنها).

## 15) الحراس الدلاليون

- `test_33`: المسح الحرفي للـCSV header + الـsidecar — **صفر** من المفردات المحظورة.
- `test_34`: AST — استيرادات stdlib حصراً (hashlib/json/os/re/sys/datetime) + لا مراجع identifiers لأي محرك مشروع.
- التدفق وُسِم فقط executed/initiated مع disclaimer صريح في `executed_flow_semantics`.

## 16) بوابة عدم المساس — **PASSED (content-verified)**

- **`trading_project` = 0 تغيير**: تحقّق محتوى كامل من `MANIFEST.sha256` (البصمة الذاتية `ac4d6f03e457695da1b3132856c424ffe5bc043d8545b5cce279fce856c51706`، 174 سطراً): **174 ok / 0 changed / 0 missing**.
- الأدوات المقبولة الحالية (بصمات تقرير 16) **مطابقة بايتياً**: `reality_inspect.py` `f3e40c1b…` · `verify_manifest.py` `c47095de…` · `inspect_data.bat` `7b27460d…` · `setup_windows.bat` `adc26f33…` · `verify_manifest.bat` `6c3cdda7…` · `run_tests.bat` `e73ed677…` (8/8 من جدول الجرد).
- ملاحظة أمانة: فحص `-newer` غير موثوق عبر استعادة الأدوار (الاستعادة تلمس الطوابع الزمنية)؛ **البوابة المعتبرة = مطابقة المحتوى** أعلاه.
- لا محرّك أُعيد تنفيذه؛ لا ملف CLOSED مُسِس؛ لا API أتمتة.

## 17) غير مُجرَّب (وذلك مقصود)

- `convert_aggtrades.bat` **لم يُجرَّب على Windows فعلي** (بنية مطابقة لـinspect_data.bat — المالك يجرّبه مرة).
- ملف المالك الحقيقي (1,824,069,783 بايت، 21,080,265 صف) — **لن يُشغَّل هنا**؛ المالك يشغّله على `D:\MarketData\`.
- القياسات أعلاه على بيانات اصطناعية مطابقة للعقد الموثّق (8 أعمدة، µs، أعداد صحيحة، sentinel عند الطلب).

## 18) الخطوة التالية (لا تنفذ الآن) + STOP

**المرحلة التالية**: **DESIGN ONLY** لعقد Source Adapter داخل المشروع (واجهة الأعمدة الـ23 → مدخلات المحركات CLOSED عبر عقودها العامة فقط — لا إعادة تنفيذ). لا بناء قبل موافقتك.
التشغيل الرسمي لملف المالك = لك على جهازك بالأمر في القسم 3.

**STOP — LOCAL MINUTE PIPELINE — IMPLEMENTED — PENDING OWNER RUN.**

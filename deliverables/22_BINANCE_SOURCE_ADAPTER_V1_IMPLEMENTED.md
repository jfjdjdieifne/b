# Builder Report — BINANCE SOURCE ADAPTER V1 — IMPLEMENTED — PENDING AUDIT

**Version:** V1
**Date:** 2026-09-28
**Report ID:** `TRADING-SYSTEM-BINANCE-SOURCE-ADAPTER-V1`
**Status:** `IMPLEMENTED — PENDING AUDIT` — لم يُغلق ولم يُعتمد؛ النجاح في التنفيذ لا يُعد اعتماداً.
**Builder:** CS agent — BUILD ONLY (التصميم 21/22 المعتمد — بند التنفيذ)
**Truth Authority:** `CausalTradingEngine._verify_replay_engine` (مرة واحدة) لا البناء.
**Review Basis:** ملفا الـPATCH المعتمدان (مِن 22)؛ criteria = المعايير التسعة لمراجعة الـPATCH في التصميم 21/22.

---

## Header — عقد البناء (كما نُفِّذ)

| Field | Value |
|---|---|
| Sources | **مصادران مستقلان**: `binance_spot_kline_ohlc_source` (OHLC مُنشور) + `binance_spot_minute_facts_source` (حقائق دقيقة) |
| TIE_ORDER_CONTRACT | `NOT_PROVEN` دائم الظهور |
| canonical O/C | من kline **حصراً**؛ المبهم يبقى دائماً في `open_ambiguous`/`close_ambiguous` وأي بناء بديل يكون `RECONSTRUCTED_*` |
| Canonical mapping | `CLOSE_TIME` في timeline؛ open_time بجانبه |
| Cross-witness | exact لكل المقارنات الأدق؛ العدّادان تحت `NON_COMPARABLE_PAIRS` غير قابل للمقارنة؛ تباين غير متوقع ⇒ `SOURCE_INCONSISTENCY` fail-closed |
| Executed flow | `buy_volume/sell_volume/volume` فقط؛ `ACTUAL_AGGRESSOR (PROXY)`/`PROXY_ONLY`؛ `EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT` |
| Generalization | عام لأي Binance Spot artifact يحقق العقد؛ بلا hard-code داخل production |
| Network | ليس جزءاً من هذه الحزمة؛ الـadapter يستقبل ملفات محلية فقط (كشف الشبكة = خارج المِنحة) |

---

## 1 — البنية (المصدران وفصل الطبقات) — PASS

- باقة `src/trading_system/sources/` بأربعة ملفات إنتاجية فقط (الحد المسموح) + ملفا الاختبارات الثلاثة المسموحان. **لا ملفات أخرى.**
- العقد المشترك `SourceArtifactIdentity` + exceptions في `sources/__init__.py` (طبقات العقد المشتركة في ملف `sources` كما أجاز القرار — لا خارج الحزمة).
- **`binance_spot_minute_facts_source.py`** — loader/validator للحقائق الدقيقة: يتحقق من الـsidecar بإعادة اشتقاق كل المحتويات (hashes، البدائل، قواعد دقيقة/ساعة/يوم، أطوال السلاسل، `legal_rows_consumed`=مجموع agg_trade_count، الاتساق الداخلي، ركائز التحقق، أطر العقود، حدود النطاق **وحدها**) ويحمّلها كما هي بلا إسقاط ولا إصلاح صامت — أي خلل يُسقط التحميل بدل السكوت.
- **`binance_spot_kline_ohlc_source.py`** — loader/validator لـklines: 12 عموداً، أحادية الدقيقة µs، `close_time=open_time+interval−1µs`، بداية منتهية بدقيقة مغلقة، حدود OHLC والتباينات المطلوبة؛ `cross_witness_sources()` و`assemble_canonical_bundle()`؛ **build list map = half-open minute بداية/نهاية (26)** — البناء لا يستخدم الإغلاق لتحديد التوقيت إطلاقاً.
- **`binance_executed_flow_source.py`** — `build_executed_flow_source(...)`: تحويل مخصص `buy_volume/sell_volume/volume` من `buy_initiated_base_volume`/`sell_initiated_base_volume`/`base_volume` + **تحققات الدقة الحرفية** (المحصلة حرفياً كما تظهر؛ حصر الجذر بمصفوفة الـrows حرفياً؛ حدود العقود؛ دقة الصياغة لكل صف) + تسمية المصدر. الـframe **لا يُعدَّل إطلاقاً** (الاختبار يثبته بمقارنة identity عبر pandas).
- `MinuteFactsSource.exact_frame` كائن مستقل **عميق** بـ`source_map` لا يشارك الـframe؛ حقول المشاهدات (`_reconstructed_*_witness`) و`tie_break_reconstructable`/`tie_break_canonical_convention` تُنقل بوضوح وتبقى `RECONSTRUCTED_*` ولا تدخل canonical.
- **فصل الطبقات (CRITICAL)**: الـloaders لا يستدعيان `MarketObservationTimeline` ولا `ReplayBoundarySystem` ولا `CausalTradingEngine` إطلاقاً (اختباران: حظر الاستدعاء حتى كتسمية، وحظر إعادة تعريف المحركات). المستهلك/runner يستدعي `seal` منفصلاً — الاختبار يبني timeline عند المستهلك فقط ويُظهر الحقيقة المدروسة: **sealed ما قبل seq 30 مقصود (30 مخصصاً) ويغيّر عند إعادة الاختبار** (الاختبار يقرأ الحقيقة من `ReplayBoundarySystem.compute_exact_pre_visible_seq` ولا يخيط العدد المدروس؛ `boundary_pre_total` مقصود). حافظات التوقيتات الداخلية بالكامل (`min`/`max`).
- 3.1/3.2 **بلا أي تعديل** (المقارنة للصيغة عند المستهلك وتسميات الأطر بجوارها).

## 2 — قرار المصادر المزدوج — PASS

`canonical_market_frame = kline فقط` — العبارات الحرفية في وحدة التحميل: «The canonical OHLC is taken exclusively from the kline source» و«the reconstruction witness is never substituted». التعبير الوحيد عن القيد حرفياً: `SOURCE_MAP_COLLISION` (لا يتحرك)، وgate: بدائل الترميز الداخلي لا تُسمى OHLC. التسميات الوحيدة لبدائل المبهم: `_reconstructed_open_witness`/`_reconstructed_close_witness` + `RECONSTRUCTED_*_WITNESS`. التخزين البديل الوحيد بعد التحميل: الأعمدة الستة الرسمية الحرفية فقط من kline إلى canonical. الاختبار يقرأ الترتيب حرفياً عبر AST.

## 3 — عقد kline و«المنشور» — PASS

- schema الـ12 عموداً حرفياً (مصدر binance-public-data الرسمي) و`close_time=open+interval−1µs` ووحدتا µs — محروسة في الاختبارات.
- التصريح الوحيد في الإنتاج: «Kline is a Binance-published bar fact» / «published bar fact» — ممنوع ادعاء الترتيب. اختبار label: يُلزم النصين `published bar fact` و`order does not prove`؛ يرفض صيغ الترتيب (`fixes chronology`)؛ يرفض اصطلاح البدائل كحقيقة؛ يقبل `open_ambiguous=0/close_ambiguous=0` إذا كانت حرفية.
- Float↔Decimal للعرضي **فقط**؛ الحقائق النصية تبقى في أعمدة exact.

## 4 — عقد الحقائق الدقيقة — PASS

- الحد الأدنى 23 عموداً يُتحقق منها حرفياً (الاختبار يستبدل `legal_rows_consumed` بستة ويطالب برفض الـsidecar دون شكوى في حدود النطاق).
- البيانات الست المحجوزة (`minute start/end/open/close/high/low`) تبقى نصوصاً كما وردت + `open_ambiguous`/`close_ambiguous` إلزاميان + بصمات الأربعة + `tie_break_reconstructable`/`tie_break_canonical_convention` + عمودا تعدد الأطر + `aggregate_start/end` + العدّاد + `open_effective_lower/upper` و`close_effective_lower/upper` كمصدر فريد (استُبدلت bind_rank بعمودي الفعّالية؛ bind_rank يوجد فقط كـ`tie_break_canonical_convention`).
- `TOTAL_LEGAL_EXPECTED=legal_rows_consumed`؛ مصفوفة الـrows = المرشحات **فقط** (المشتبه يظهر فقط في `synthetic/suspect/need_manual_source_confirmation` — العمودان الاختباريان).
- المُحمَّل يُلزم تطابق البدائل/الدقة/الاتساق الداخلي حرفياً.
- الخريطة الحرفية `SOURCE_MAP` للحقائق (26) وأخرى لـkline (22) — بلا إعادة مطابقة دلالية.

## 5 — صيغة TIE_ORDER_CONTRACT وإعلانات الغموض — PASS

- `TIE_ORDER_CONTRACT = NOT_PROVEN` إلزامياً في كل حزمة loaded.
- القيدان: `open_close_crossing_valid = deterministic_convention_only_not_proven_chronology` و`candidate_monotonic_order = deterministic_input_order_not_proven_event_time` وشرط واحد: `tie_break_reconstructable`.
- `open_ambiguous`/`close_ambiguous` يبقيان في البيانات والمخطط، ويمنع المبهم من OHLC قطعياً: اختبار بمصفوفة rows فيها `close=UNKNOWN` (سلسلة غير مستهلكة) والكائن الحقيقي `close==100.5` والبديل `100.25` — يثبت أن البديل لا يدخل البناء ولا يُسقَط الغموض.

## 6 — executed flow و `ACTUAL_AGGRESSOR (PROXY)` — PASS

- `EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT` يقبل frame تسليمي من مورد خارجي عبر **الـAPI العام فقط** (3.1/3.2) بلا تعديل فيهما (الاختبار يقرأ الكود ويطالب: تعريف نوع واحد + zero-length seq + تحقق ثابت الـseq + total ≤ min(open,close) + equal-length، ويمنع trail-reading/aggressor-compile).
- العقد: buy+sell==total حرفياً بالجذر المصفوفي؛ الحصر عند المشتري **فقط** (بديل البائع في count مما يُظهر الانعكاس)؛ **وحدة واحدة** (الجذر والمحصلة) وبصمة واحدة (decommissioned: single-unit-single-signature)؛ المدروس: unit=single_declared_base_unit.
- التسمية: الأسماء الحرفية `buy_volume`/`sell_volume`/`volume` + `EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT` + شرط `buy+sell==volume` — والاختبار الحاسم يقرأ الإنتاج كنص حرفياً ويمنع الصيغ المحرمة حتى كسطور ماسحة، وتسمية `pressure`/`book`/`institutional`/`whale`/`market-wide` بصياغات مطابقة حرفياً. الـstatement في وحدة التنفيذ ينص على `ACTUAL_AGGRESSOR (PROXY)` بوضوح وعلى حدوده (لا اتجاه/ضغط/دفعة/كتلة/كتلة بعامة؛ لا book).

## 7 — CROSS-WITNESS اللازم — PASS

مقارنة exact لكل من: minute key، high، low، base volume، quote volume، taker-buy base، taker-buy quote **بالدقة الحرفية** (الاختبار يقرأ القيد حرفياً: `NON_COMPARABLE_PAIRS` = `("number_of_trades", "agg_trade_count")` حصراً + بوابة الدقة `TAKER_BUY_LITERAL_PRECISION_INCOMPATIBLE`). O/C غير المبهم من	EXPECTED_MATCH والمبهم لا يُطلب تطابقه (سلاسل غير مستهلكة). أي تباين غير متوقع ⇒ `SOURCE_INCONSISTENCY` fail-closed (اختبار هجوم `close` و`taker_buy_base`). تباين بصمة ثابت ⇒ `PROVENANCE_MISMATCH` فقط.

## 8 — التعميم وعدم ارتباط الـinstance — PASS

- **30**: zst `ANOTHERSYM9/1m/2026-02-01` بمصدر json مختلف → الـloader يقبل ويُنتج `symbol=ANOTHERSYM9`.
- **31**: ماسح يقرأ نص الإنتاج الأربعة ويمنع القيم الدالة (`BTCUSDT`، صيغ `2026-05`، البصمتين `86d4f3d3`/`a6a06c4c`)، ويمنع hard-code كودات انحدار (بما فيها شكلي `86d4`/`a6a0` المفصولين) — ولا يسرب تسامحاً في runtime.
- علامة التوحيد المعتمدة **دون تغيير النص**: `symbol=identity.symbol` (generic) + `symbol="BTCUSDT"` في `_reconstructed_open_witness`/`_reconstructed_close_witness` (instance) ⇒ `SOURCE_MAP_COLLISION` (كان يعمل بعكسي؛ أُصلح مسار الكشف).

## 9 — الحواجز والأمثلة والاختبارات العدائية — PASS (45 اختباراً جديداً؛ لا اختبار وهمي)

**45/45 PASS** (19 facts + 20 kline + 6 executed-flow)؛ **full suite 1045 passed / 0 failed** (1000 سابقة + 45 جديدة). النجاح ليس إغلاقاً.

النقاط العدائية (35 موثّقة) نُفِّذت كلها **وامتدت**؛ لا نقطة أُسقِطت. أبرزها: schema/kline sidecar/ دقائق sidecar (1–2)؛ wrong symbol/market/interval/unit/naive/duplicate/gap/shape (3–9)؛ hash/provenance mismatches (10–11)؛ المبهم يبقى خارج canonical (12)؛ النص المنشور (13)؛ TIE=NOT_PROVEN والقيدين والبصمة (14)؛ 4×2 exact (15–18: مساران لكل)؛ عدم المقارنة (19)؛ SOURCE_INCONSISTENCY (20)؛ executed flow (21)؛ ACTUAL_AGGRESSOR (22)؛ PROXY (23)؛ AST (24–25)؛ half-open map (26)؛ sealed قبل seq المنح (27)؛ cross-timeline (28)؛ timed twice (29)؛ generic + hard-code (30–31). + **4 mutation proofs** (توثيق swap/restore في `.build_mutations.json` — كل طفرة أُسقطت اختبارها الموجَّه rc=1 ثم استُرجعت الملفات ببصمتها):

| Mutation | Effect | Target test | Detected |
|---|---|---|---|
| M-A: بدائل المبهم تدخل close في canonical | يُسقط | test_12 | YES |
| M-B: عكس BUY↔SELL | يُسقط | test_22 | YES |
| M-C: تمرير `SOURCE_INCONSISTENCY` | يُسقط | test_20 | YES |
| M-D: hard-code `symbol="BTCUSDT"` في الـprovenance | يُسقط | test_30 | YES |

## 10 — عدم المساس و MANIFEST — PASS

- ملفات البناء: **الأربعة الإنتاجية + ملفا الاختبارات الثلاثة** فقط (المسموح). مقارنة `.build_before.sha` (183) ↔ `.build_after.sha`: **لا ملف سابق تغيَّر إطلاقاً**؛ الجديد = الملفات السبعة المسموحة + `pytest_cache/README.md` (ضجيج تشغيلي — سوابق الـS1). لا حذف حقيقي (الـ«gone» = اختلاف فلترة `find` للامتدادات؛ الملفات موجودة وبصماتها مطابقة).
- `MANIFEST.sha256` = **174/174 OK**؛ بصمة الملف = `ac4d6f03e457695da1b3132856c424ffe5bc043d8545b5cce279fce856c51706` = المعتمدة (أول سطر = البصمة الذاتية `e0972c16…` كما هي). ملفات البناء **لن تدخل الـmanifest إلا في CLOSURE بعد AUDIT**.

### بصمات الملفات الجديدة (للـAUDIT)

```
267384be8e6c32f5b6e0d0fa803f9974622797bea12ffa199501b739f9eb11bb  src/trading_system/sources/__init__.py
7c4eac638a8f651c651e4f3d2f4ddb12496ea9ca54037f44ff430bffcd71be7b  src/trading_system/sources/binance_spot_minute_facts_source.py
97b2afc3a2f6d7512cd24c6435bb3ec7c1e9aca526fa523a69333b3dcad45006  src/trading_system/sources/binance_spot_kline_ohlc_source.py
1da6b8724be31d8cddfd9ce50d030697ea1f4f09e87ce1fb579f498f6730bfda  src/trading_system/sources/binance_executed_flow_source.py
e277551cd0b51c75b2a0de05a1314f06a1695f5678548e078a9dded2280b6e23  tests/test_binance_spot_minute_facts_source.py
aa5947a135d7c4d4d496345e87f99b5ed02ffb47315f2d5508e728563a2f169e  tests/test_binance_spot_kline_ohlc_source.py
9bfa82a2a01c68074fc4402ff2bb428fdf0caffc058abc20b05a11896c158744  tests/test_binance_executed_flow_source.py
```

## الـDeviations (قرار AUDIT)

1. **35 نقطة ⇒ 45 اختباراً**: كل نقطة موثّقة نُفِّذت؛ 15–18 مزدوجة المسار (exact macro + literal micro) والهجمات منفصلة حسب الجهة (هجوم واحد ≠ spec للمصدرين). لا اختبار وهمي؛ العدد ليس الغاية.
2. **الـAPI اللفظي قُرِّر في BUILD** (سياسة IMPLEMENTED في 6.2B-1-0 §6): `EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT` + `NON_COMPARABLE_PAIRS` + بوابة `TAKER_BUY_LITERAL_PRECISION_INCOMPATIBLE`. مفتوح لرأي الـAUDIT (بند الدمج).
3. **bind_rank ⇒ `open_effective_lower/upper` + `close_effective_lower/upper`** (قرار المالك) وحدها عند التحميل؛ bind_rank في `tie_break_canonical_convention` وحده.
4. **دوال البدائل `_reconstructed_*_witness` بأسماء داخلية** (underscore) تظهر في نسخ `exact_frame` — موثقة؛ canonical builder ينسخ الأعمدة الست وحدها.
5. **نقطة 27**: sealed مقصود (30 مخصصاً) ومتغيّر بين التشغيلات — الاختبار يقرأ العدد من الحقيقة السببية؛ لا خياطة للنص المدروس (السجل: يفشل raw < 30 بدون احتساب التوقيت؛ ينجح بمرجع الـdomain الحقيقي).
6. **entry point**: `sources/__init__.py` يستورد loaders/exceptions/identity العامة (نطاق «ملفات … sources»).
7. **ضجيج التشغيل**: `.pytest_cache/` جديد (سابقة S1 نفسها)؛ لا علاقة له بالمنحة.
8. تشغيل الاختبارات داخل الشجرة (الأسرع؛ `/tmp` tmpfs غير كافٍ للـsuite الكامل). سجلات: `.build_mutations.json` + `.build_before.sha`/`.build_after.sha` في `/home/user/`.

---

## قرار التسليم

**المصدران و exec-flow مبنيان بالكامل؛ الحواجز مفروضة؛ التسمية الوحيدة الموثقة؛ صيغ الترتيب ممنوعة حرفياً؛ العدّادان غير قابلين للمقارنة.** **الحالة: `IMPLEMENTED — PENDING AUDIT`** — التدقيق المستقل ينعقد في شات منفصل. لا Reality Check، لا 4C-2، لا closure. **STOP**.

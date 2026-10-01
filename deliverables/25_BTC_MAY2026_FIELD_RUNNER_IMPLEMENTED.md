# BTC MAY 2026 FIELD RUNNER — IMPLEMENTED — PENDING OWNER RUN

**Date:** 2026-09-28 (Asia/Damascus)
**Report ID:** `BTC_MAY2026_FIELD_RUNNER_V1`
**Status:** `IMPLEMENTED — PENDING OWNER RUN` — لم يُغلق؛ لا تحليل لنتائج BTC هنا (ملف المالك وحده عنده).
**Authority:** OWNER AUTHORIZATION — BTC MAY 2026 FIELD RUNNER — DESIGN + BUILD — FREEZE INFRASTRUCTURE.
**حالة الـFreeze:** لا محركات جديدة، لا detectors جديدة، لا refactor، لا تجميل، لا 4C-2، لا Model/Strategy/PnL. الـrunner أدوات محلية **خارج** `trading_project` — لا ملف CLOSED مُسَ، لا MANIFEST أثناء البناء.

---

## 1 — ما الذي شُغِّل فعلاً (في هذا البناء/الاختبار — لا نتائج BTC)

الـrunner يُشغّل، عبر **public APIs فقط** (بلا إعادة تنفيذ أي engine)، على أي artifact يحقق العقد:

| الفرع | المصدر | الحالة في اختبار الـfixture |
|---|---|---|
| Binance Source Adapter V1 (CLOSED) | load minute facts + klines + exact cross-witness + canonical=kline حصراً + executed flow منفصل | RAN (240/240 دقيقة مطابقة exact) |
| MarketObservationTimeline.seal | public API **من المستهلك** (فصل الطبقات) | RAN |
| Dynamic Volatility 1.1 | `analyze` عام | RAN |
| Session Context 1.2 | `analyze` عام (ميزات تقويم دائماً؛ الجداول الزمنية للجلسات = إعداد مالك) | RAN |
| Swings 2.1A → Sequence 2.1B → Structural Breaks 2.1C → Liquidity 2.2 → Order Blocks 4.1 → Dealing Range 4.2B | سلسلة السلاسل العامة — **بمعامل quantile مالك صريح** | RAN (60H+59L swings، 58 BOS، 58 hypotheses) |
| FVG 4.2A | عام (مستقل عن الـswings) | RAN |
| Order Flow PROXY 3.1 (OHLCV_PROXY) | عام — يبقى PROXY | RAN |
| Order Flow ACTUAL 3.1 (ACTUAL_AGGRESSOR) | من `EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT` منفصل | RAN |
| Absorption/Response 3.2 PROXY + ACTUAL | حسب العقدين العامين | RAN (منفصلان) |
| HTF factual aggregation 5.1 | `CausalHTFAggregator` بمدد معلنة (`htf_durations`) | RAN (1h) |
| Evidence Vector 6.1A | مروران منفصلان ACTUAL + PROXY (لا يُجمعان) | RAN |
| Narrative/Hypotheses 6.1B | على كل evidence frame | RAN (58 CREATED / 57 SUPERSEDED / 1 MONITORING على الـfixture) |
| OUTCOME_FILM_SAMPLE | عقود trajectory المغلقة (Stage-2 price trajectory عبر freeze/anchor/interval العامة) عند مواضع العينة التي يوجد فيها hypothesis حقيقي + حقائق المسار الأمامي الخام المُوسومة لبقية العينة | RAN |
| Stage 4C-2 / Model / Strategy / PnL / Reality-Check ادعاء | — | **NOT STARTED — ممنوعة** |

**تنزيل kline الرسمي مُختبَر فعلياً** من `data.binance.vision` (ZIP + `.CHECKSUM` رسمي، التحقق قبل الاستخدام): `BTCUSDT-1m-2026-05.zip` بصمة `62983d93c35e26ec6c29116c629e443b7ddfe3d301aca83331ff58112199d8d0` — والـCSV الرسمي (44,640 دقيقة، 0 فجوات) **يمر عبر الـadapter المغلق كما هو** (1.5 ثانية). عند تعذّر الشبكة: `LocalFileRequired` برسالة تطلب المسار المحلي (لا فشل غامض) — `--klines-csv` أو `--klines-zip --klines-checksum`.

## 2 — ما الذي بقي NOT_CONFIGURED (بلا أي default مُختلَق)

1. **سياسة تأكيد الـSwings** (`EmpiricalConfirmationPolicy.quantile` — الإلزامي بلا default في العقد المغلق): الافتراضي `null` ⇒ فرع swings + sequence + structural breaks + liquidity + order blocks + dealing ranges = **NOT_CONFIGURED** مُعلَنة. التفعيل بمعامل مالك صريح في `field_runner/config/field_run_config.json`: `swing_quantile` (+ اختيارياً `swing_prior_*`) — يُسجَّل `OWNER_SUPPLIED_NOT_SACRED`. لا fake swings.
2. **جداول جلسات Session**: الافتراضي `[]` ⇒ `NOT_CONFIGURED` (ميزات التقويم تبقى RAN). مثال مالك في الإعدادات.
3. **5.2 MTF confluence**: خارج قائمة تشغيل المالك ⇒ لا يُشغَّل؛ `multiscale=False` في evidence مُعلَن.
4. عينة DETECTION_AUDIT = **parameter مالك صريح** (`sample_size`، الافتراضي 100) — «غير مقدس» ومُعلَن هكذا في المخرجات.

## 3 — الملفات الجديدة فقط (خارج trading_project)

| file | sha256 |
|---|---|
| `field_runner/__init__.py` | `96a5530651b4e3a5482150a695b68e0bb9496d70fb1c28c6baf0f4c0c4ff5ebe` |
| `field_runner/binance_kline_downloader.py` | `cb13c80c3e79c0b3154663bf9e79cf9bbaa1aef7798b6d2c81f7ab47f4066edd` |
| `field_runner/fixtures.py` (TEST-FIXTURE-ONLY) | `414dba6cacce8f400b46bdb778df3942e11eb5c17ad2a69a34bf04de07828902` |
| `field_runner/sample.py` | `3cd81c4f36a2608a35dea38033f902f40184076dbd26ec85591f592e498bf9c7` |
| `field_runner/pipeline.py` | `27045a57b5000d581b2817516f33226ef2d804f3f8c2d4cec16f92a5b5aedd27` |
| `field_runner/reporting.py` | `5b7f39b678e021adb41c7f6553b54402dbe00d992eb2494117c64077a21d9f20` |
| `field_runner/runner_btc_may_2026.py` | `bdf672270f76d70dba5253ddf588e66bf2c333f6b9c2841dd40a3767232207fc` |
| `field_runner/config/field_run_config.json` | `70540a0d79c8503d04c9e5a1f55b57ecdd164dd53070b23cf778bd7af751173c` |
| `field_runner/runner_tests/conftest.py` | `c397cb2e2869e36e95a3409ef9a497f405d4812eafcc99c3d8dc9eddbd7b640e` |
| `field_runner/runner_tests/test_runner_integration.py` | `96baf7dd55c6b5560bca2599c4b16b5ac519e75a325e3c5117f80d47f08c3b38` |
| `field_runner/runner_tests/test_runner_failclosed.py` | `2bf2aff348ab36d084aae177636bce207aa5a6a822c46e1179c55d6996dc485a` |
| `field_runner/runner_tests/test_runner_guards.py` | `5b59dad8b929ae2a90a364af642dc50040598398039193ae963ea66912d1e4dd` |
| `run_btc_may_2026.py` (أمر المالك الواحد) | `14b7ef61e75bc193e8162fc7ab22d8341625c378d39d8f70beed1ad6d16a5363` |
| `run_btc_may_2026.bat` (ASCII فقط) | `5b5650649ac916cfc999217b2e9c99ca0d0bfcc66bd2e8872a53ef7c729830b4` |
| `README_OWNER.txt` | `866c3d14bc8662b75d1e2b85e04e9aed4f91c309873c71b2c4bf0e266fe04724` |

## 4 — اختبارات runner (18/18 PASS — لا آلاف)

`python3 -m pytest field_runner/runner_tests` ⇒ **18 passed**:
1. roundtrip الـfixture عبر adapters المغلقة (240/240 exact) + canonical=kline حصراً.
2. smoke كامل: كل الفروع RAN + المخرجات.
3. **no future leakage** في DETECTION_AUDIT: صف العينة == إعادة حساب على prefix خالص (إثبات العقد السببي).
4. **OUTCOME_FILM منفصل** عن حقائق القرار (عمود الحارس + صفر أعمدة forward في audit).
5. **عيّنة timestamps حتمية** (نفس timeline_hash ⇒ نفس المواضع).
6. صف contract trajectory عند موضع hypothesis حقيقي (excursions من Stage-2 المغلق).
7. **rerun deterministic**: تشغيلان متطابقان بايتياً عدا volatile keys المُعلَنة (runtime/peak).
8. **no model/PnL/signals**: لا عبارات إدعاء في المخرجات (النفي المطلوب مسموح فقط).
9. corrupted source ⇒ fail-closed (SchemaViolationError).
10. missing kline ⇒ fail-closed (CoverageError).
11. wrong official checksum ⇒ fail-closed (ChecksumMismatch) + صحيح المطابقة يمر.
12. source inconsistency (هجوم على صف kline واحد) ⇒ SourceInconsistencyError.
13. بوابة هوية المالك (hash mismatch) ⇒ رفض صريح.
14. **AST guard**: لا تعريف أي engine class/def analyze داخل الـrunner.
15. AST guard: لا نسخ دوال المحركات الداخلية.
16. **MANIFEST 183/183 OK** (المشروع المغلق لم يُمس).
17. ختم الـ7 ملفات المغلقة = بصماته المقبولة.
18. (مع 6 أعلاه) فصل العينة/العينة.

## 5 — kline الرسمي: كيفية الحصول والتحقق

```text
URL:  https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-05.zip
      + .CHECKSUM الرسمي (sha256)
التحقق: sha256(ZIP) == محتوى .CHECKSUM قبل فك الملف (fail-closed)
الاستخراج: BTCUSDT-1m-2026-05.csv (headerless 12 columns — صيغة الـadapter المغلق مباشرة)
البصمة المُتحقَّق منها اليوم: 62983d93c35e26ec6c29116c629e443b7ddfe3d301aca83331ff58112199d8d0
بلا شبكة: مرر --klines-csv PATH (أو --klines-zip + --klines-checksum) — الـrunner يطلبها برسالة واضحة.
```

## 6 — command واحد للمالك

```text
1) فك ZIP (مع إبقاء البنية)
2) ضع ملفاتك في .\data\   (minute-facts CSV + sidecar JSON [+ aggTrades اختياري للتحقق])
3) شغّل:  run_btc_may_2026.bat        (أو: python run_btc_may_2026.py)
4) انتظر ثم افتح outputs\btc_may_2026_reality\
5) أرسل SUMMARY.json + MACHINE_VALIDATION.json (+ أي ملفات صغيرة يُطلب)
```

المخرجات (A–F + دعم الرسم): `SUMMARY.json`, `DETECTION_AUDIT.csv`, `DETECTION_ENTITIES` كـ`entities_*.csv` (swings/structure/liquidity/order_blocks/fvg/dealing_ranges + أحداثها)، `OUTCOME_FILM_SAMPLE.csv`, `README_RESULT_AR.txt`, `MACHINE_VALIDATION.json`, `chart_overlay.csv`. PROXY وACTUAL لا يُجمعان في رقم واحد في أي ملخص. ملاحظة حدّ عقدي: عقود trajectory المُعلَّمة للـfilm تُملأ عند تزامن hypothesis حقيقي مع موضع العينة (العقد يلزم anchor hypothesis حقيقي — بلا اختراع anchors تركيبية)؛ بقية صفوف العينة تحوي حقائق المسار الأمامي الخام المُوسومة `RAW_FORWARD_PATH_FACTS_NOT_CONTRACT_TRAJECTORY` — ومُعلَن كذلك.

## 7 — ZIP / package status

**ZIP جاهز (بأمر المالك الصريح):** `deliverables/26_BTC_MAY2026_FIELD_RUNNER_PACKAGE.zip`
- `zip_sha256 = 7f5f7b42246f28502e7cfdfe5b3ad0ca15ce48f40a1b6e16e44bab2b0000b164` (723,309 bytes, 204 entries)
- البنية: `run_btc_may_2026.bat` + `run_btc_may_2026.py` + `README_OWNER.txt` + `field_runner/` كامل + `trading_project/` كامل (187 ملفاً) + `data/` + `FILE_INVENTORY.sha256`.
- تحقق round-trip كامل من الأرشيف: 202/202 ملفاً ببصماته.

## 8 — إثبات عدم تغير CLOSED + baseline الـMANIFEST

- **full suite للمشروع المغلق بعد البناء: 1045 passed / 0 failed** (5:32).
- ملفات الإغلاق الخمسة (MANIFEST + STATUS + FINAL_VALIDATION + milestone + seal) **بصماتها كما هي عند الإغلاق**.
- **MANIFEST baseline بعد إغلاق Source Adapter (لم يُمسه البناء):** 183 سطراً — `sha256 = 7796a73fc30fc311902d7ba8e033eb1699a73c5db10e824d02653fbdd1681587` — التحقق داخل اختبارات الـrunner 183/183 OK.
- أدوات الـrunner خارج `trading_project`؛ لا market data في أي manifest.

## 9 — حدود التقرير

- لا ادعاء Information Edge / تنبؤ / ربحية / استراتيجية / إشارات / PnL — نهائياً.
- إحصاءات Reality-Preview وصفية فقط (تغطية، تكرارات، أعمار كيانات، توزيعات excursions المُوسومة، توزيعات حالات hypotheses بالمصطلحات الحرفية المغلقة) — بلا horizon/threshold/combination selection.
- Detector output = operational project definition (لكل كيان module identity) — ليس «الحقيقة السوقية الوحيدة»؛ لا «FVG يعمل/يفشل».
- `TIE_ORDER_CONTRACT = NOT_PROVEN`؛ المبهم يبقى مبهمة؛ canonical OHLC من الكنائن المنشورة حصراً.
- ACTUAL = `EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT` فقط (ليس ضغط شراء/دفتر أوامر/مؤسسات/حيتان/تدفق السوق).
- Historical generating provenance: NOT_CERTIFIED خارج artifacts المصدر المُربوطة بالبصمات.
- **لم تُحلَّل أي نتائج BTC** — البيانات لدى المالك فقط؛ التشغيل الحقيقي = خطوة المالك بالأمر الواحد.
- RESEARCH-DEBT-020..025 تبقى OPEN.

**STOP.**

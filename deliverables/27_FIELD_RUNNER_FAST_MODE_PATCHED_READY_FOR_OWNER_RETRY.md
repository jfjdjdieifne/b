# FIELD RUNNER FAST-MODE PATCHED — READY FOR OWNER RETRY

**Date:** 2026-09-28 (Asia/Damascus)
**Report ID:** `BTC_MAY2026_FIELD_RUNNER_V1_FAST_MODE_PATCH1`
**Scope:** PATCH ONLY — الـfield runner الخارجي. لا تعديل في `trading_project` ولا Source Adapter المغلق ولا converter ولا semantics.
**الأمر الذي يُعيد المالك تشغيله (نفسه بالضبط):** `python run_btc_may_2026.py`

---

## 0 — حدود البيانات (CRITICAL OWNER-DATA BOUNDARY — مُصحَّحة هنا)

- البيئة البنائية **لا تملك أي artifact مالك**: لا raw aggTrades (1.69 GiB)، لا minute-facts حقيقية، لا sidecar حقيقية. لا ادعاء تشغيل أي real-owner artifact هنا.
- كل regression tests للـPATCH: **SYNTHETIC SMALL FIXTURES ONLY** — لا تنزيل بديل، لا طلب نسخ الملف.
- البصمات المعطاة (86d4f3… / a6a06c… / 004877…) = **metadata مرجعية** تُحمَّل كـdefaults في الأمر — لا ملفات متاحة.
- REAL OWNER RUN يحدث على جهاز المالك فقط، عند إعادة التشغيل.

## 1 — root cause

الخطأ الحرفي على جهازك:

```text
AGGTRADES_HASH_MISMATCH
expected=86d4f3d3…   ← RAW AGGTRADES SHA256
actual=a6a06c4c…     ← MINUTE FACTS CSV SHA256 (artifact صحيح!)
```

السبب: **auto-discovery الغير role-aware** في `detect_inputs` كان يصنّف أي `*.csv` يحوي النص `aggtrade` في اسمه على أنه RAW AGGTRADES. ملفك `minute_facts_BTCUSDT-aggTrades-2026-05.csv` يحوي «aggTrades» في اسمه ⇒ صُنِّف خطأً RAW ⇒ بوابة الهوية طبّقت **raw expectation** على **minute-facts artifact** ⇒ mismatch بالمعنى الخاطئ واسم الخطأ الخاطئ (`AGGTRADES_HASH_MISMATCH`). الـartifact لم يكن خاطئاً إطلاقاً — وهو بالضبط الـMINUTE_FACTS المعتمد.

## 2 — الإصلاح (المبادئ المفروضة)

1. **أدوار artifacts صريحة ومتنافية** (لا substring غامض):
   - `RAW_AGGTRADES` ← expected `86d4f3d335ae244dcc143569bd1cc382320027c3fe4702e5d3ddf0757e8f1c04`
   - `MINUTE_FACTS_CSV` ← expected `a6a06c4c583e64e7613ddca275533a15062ab13864482cacf30b2f125094601f`
   - `MINUTE_FACTS_SIDECAR` ← يُلزم: `source_sha256 = 86d4f3…` + `output_csv_sha256 = a6a06c…` + `converter_sha256 = 0048779bd821dbe6f3cda66517b19e7435fc0b98592ee9aa1980804fe27efb5d`
2. **FAST mode (الافتراضي)**: raw aggTrades **غير مطلوب**. القبول فقط إذا: `SHA256(facts) == sidecar.output_csv_sha256 == a6a06c…` و `sidecar.source_sha256 == 86d4f3…` و `sidecar.converter_sha256 == 004877…` — هوية raw تُثبت عبر سلسلة provenance في الـsidecar، لا عبر hashing ملف غير موجود.
3. **RAW mode (`--mode raw`)** فقط: raw يجب أن يكون موجوداً ⇒ `SHA256(raw) == 86d4f3…` تحقّقاً فعلياً (+ نفس سلسلة الـsidecar).
4. **discovery role-aware**: explicit paths أولاً ← sidecar-driven لاكتشاف الـminute-facts ← نمط raw منفصل (يستبعد كل ما صُنِّف minute-facts، حتى لو اسمه يحوي aggTrades، ويستبعد klines) — **أكثر من candidate داخل دور ⇒ fail-closed مع عرض المسارات**.
5. **رسوم artifact-specific** (اختفت `AGGTRADES_HASH_MISMATCH` نهائياً):
   `MINUTE_FACTS_HASH_MISMATCH` / `RAW_AGGTRADES_HASH_MISMATCH` / `SIDECAR_SOURCE_BINDING_MISMATCH` / `CONVERTER_BINDING_MISMATCH` / `SIDECAR_OUTPUT_BINDING_MISMATCH` / `MINUTE_FACTS_AMBIGUOUS` / `RAW_AGGTRADES_AMBIGUOUS` / `RAW_AGGTRADES_FILE_REQUIRED`.
6. `--allow-hash-mismatch` لم يُستخدم كحل في أي اختبار (يبقى override مالك صريح فقط). لا hash guard عُطِّل. لا semantics تغيّرت. `swing_quantile` يبقى `null` — لا engine جديد، لا Reality analysis.

## 3 — الملفات الخارجية المعدَّلة (SHA256 قبل ← بعد)

| file | قبل | بعد |
|---|---|---|
| `field_runner/runner_btc_may_2026.py` | `bdf672270f76d70dba5253ddf588e66bf2c333f6b9c2841dd40a3767232207fc` | `a15672ca1ea68b672a66d1d327068fd4bc3f4b7af0aa10cc4038abf1ca4df74e` |
| `field_runner/pipeline.py` | `27045a57b5000d581b2817516f33226ef2d804f3f8c2d4cec16f92a5b5aedd27` | `58fe777e960ad77ed88cc1be49de8726182c27df8d10de3badbf771a2b440e5c` |
| `field_runner/fixtures.py` (TEST-FIXTURE-ONLY) | `414dba6cacce8f400b46bdb778df3942e11eb5c17ad2a69a34bf04de07828902` | `b62d7c1d00b5f53487c27e4445821ef1097342a2a1882ce931a70dbbe751afd3` |
| `field_runner/runner_tests/test_runner_integration.py` | `96baf7dd55c6b5560bca2599c4b16b5ac519e75a325e3c5117f80d47f08c3b38` | `6450a9e78bcb61b3e41bfe0458001bb55ad80987bfb558e535d5ba90aeaf4217` |
| `field_runner/runner_tests/test_artifact_roles.py` | — (جديد) | `0bd27cb4c77f262ab6036dfcf48f724d84b06d49b1eef7bc50197bf629edf2c3` |
| `README_OWNER.txt` | `866c3d14bc8662b75d1e2b85e04e9aed4f91c309873c71b2c4bf0e266fe04724` | (مُحدَّث: وضع FAST/RAW + رسوم الأدوار) |

غير مُلمس: `reporting.py`, `binance_kline_downloader.py`, `sample.py`, `config/field_run_config.json` (defaults كما هي — `swing_quantile: null`), وكل `trading_project/`.

## 4 — regression result

`python3 -m pytest field_runner/runner_tests` ⇒ **31 passed / 0 failed** (synthetic fixtures فقط):

- **حالة المالك حرفياً**: `data/minute_facts_BTCUSDT-aggTrades-2026-05.csv` + sidecar، بلا raw CSV ⇒ FAST mode **PASS** + إثبات أن الاسم الحاوي «aggTrades» **لا يُصنَّف RAW**.
- أمر المالك العاري (`runner_main` بلا flags اكتشاف) ⇒ discovery + تشغيل كامل PASS.
- minute facts + sidecar صحيحان ⇒ PASS.
- minute facts hash خاطئ ⇒ FAIL باسم `MINUTE_FACTS_HASH_MISMATCH` (وبإثبات أن `AGGTRADES_HASH_MISMATCH` غير موجود).
- sidecar.source_sha256 خاطئ ⇒ FAIL `SIDECAR_SOURCE_BINDING_MISMATCH`.
- sidecar.converter_sha256 خاطئ ⇒ FAIL `CONVERTER_BINDING_MISMATCH`.
- sidecar.output_csv_sha256 خاطئ ⇒ FAIL `SIDECAR_OUTPUT_BINDING_MISMATCH`.
- raw غير موجود في FAST ⇒ **PASS**. raw غير موجود في RAW mode ⇒ FAIL `RAW_AGGTRADES_FILE_REQUIRED`.
- ملفا minute facts ⇒ `MINUTE_FACTS_AMBIGUOUS` fail-closed مع عرض المسارين.
- raw + minute facts معاً ⇒ كل يُصنَّف دوره الصحيح + PASS؛ raw موجود وبصمة خاطئة ⇒ FAIL `RAW_AGGTRADES_HASH_MISMATCH`.
- defaults الأمر = بصمات المالك المرجعية الثلاث + `default="fast"`.
- (من قبل) leakage/fail-closed/determinism/no-model-pnl-signals/AST-guard — كلها سليمة بعد الـPATCH.

## 5 — إثبات CLOSED + baseline MANIFEST

- **MANIFEST**: 183 سطراً — sha256 = `7796a73fc30fc311902d7ba8e033eb1699a73c5db10e824d02653fbdd1681587` — **لم يتغير** — التحقق **183/183 OK**.
- شجرة `trading_project/` كاملة مقارنةً ببصمة ما بعد الإغلاق: **صفر ملفات متغيّرة — CLOSED UNCHANGED**.

## 6 — ZIP المُصحَّح (جاهز للمالك)

`deliverables/28_BTC_MAY2026_FIELD_RUNNER_PACKAGE_FAST_MODE_PATCHED.zip`
- **zip_sha256 = `e43d6c96f1e19c79ef553ed04d7053ca63ab4e952fa6eeef3a7c7aaa82cb7895`** (728,322 bytes — 205 entries — round-trip 203/203 مُتحقَّق)
- البنية كما هي: `run_btc_may_2026.bat` + `run_btc_may_2026.py` + `README_OWNER.txt` + `field_runner/` (مع اختبارات الـPATCH) + `trading_project/` كامل (187 ملفاً) + `data/` + `FILE_INVENTORY.sha256`.
- المالك لا يعدّل أي Python: يفك ZIP ← يضع `minute_facts` + sidecar في `data\` (raw اختياري) ← يشغّل الأمر نفسه.

## 7 — الأمر

```text
python run_btc_may_2026.py
```

(أو `run_btc_may_2026.bat`). الافتراضي = FAST mode؛ البوابات الثلاث محمَّلة ببصماتك المرجعية؛ أي mismatch ⇒ اسم artifact صحيح في الرسالة.

## 8 — حدود

- لا تحليل نتائج BTC هنا (البيانات مالك فقط). لا ادعاء Information Edge/ربحية. لا Model/Strategy/PnL. `TIE_ORDER_CONTRACT = NOT_PROVEN`. RESEARCH-DEBT-020..025 OPEN.
- REAL OWNER RUN = عندك، بهذا الأمر، على الـZIP المُصحَّح.

**STOP.**

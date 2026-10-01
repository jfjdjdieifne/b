# EXACT PERFORMANCE REVOLUTION — DESIGN + BENCHMARK REPORT

**Date:** 2026-09-29 (Asia/Damascus)
**Report ID:** `EXACT_PERF_REVOLUTION_V1`
**Scope:** DESIGN + BENCHMARK INVESTIGATION ONLY — لا تعديل على CLOSED، لا production optimization، لا Reality analysis.
**Synthetic workloads فقط** (لا owner data) عند n = 1k, 5k, 10k, 20k, 44,640 (+100k, 250k, 1m للـprototypes).
**أرقام المالك المرجعية (أول Real Owner Run):** Dynamic Volatility = 581.4s، FVG = 1594.3s على 44,640 دقيقة.

---

## 1 — flame / profile hotspots (cProfile + عدّ استدعاءات دقيق)

**A) Dynamic Volatility — n=10,000 (5.6s profiled):**

| ncalls | cumtime | node |
|---|---|---|
| 1 | 5.639s | `dynamic_volatility.analyze` |
| 20,000 | 5.527s | `causal_percentile.observe` |
| **20,000** | **5.445s** | **`causal_percentile.rank` ← 96.6% من الزمن** (المسح الخطي للتاريخ) |
| 20,000 | 0.065s | `causal_percentile.push` |
| 40,000 | 0.062s | `_coerce_value` |

**B) FVG — n=10,000 (61.4s profiled) — ليست tracker-bound:**

| ncalls | cumtime | node |
|---|---|---|
| 1 | 61.4s tottime 36.6s | `fvg.analyze` (الحلقة السطرية) |
| 10,027 | 16.3s | `builtins.sum` |
| **25,005,000** | **12.1s** | **`fvg.py:72 <genexpr>` — `kb[i]=sum(x.direction.startswith("BULLISH") for x in fs)` يُعاد حسابه فوق كل المرشحين كل شمعة = O(n²) عمل متكرر** |
| 4,999 | 2.0s | `causal_percentile.rank` (3% فقط) |

**C) Narrative 6.1B — n=6,000 (41.3s profiled / 15.8s نظيف لكل mode):**

| ncalls | cumtime | node |
|---|---|---|
| 372,997 | 20.0s | `pandas.DataFrame.__getitem__` (وصول بالاسم لكل خلية) |
| 271,647 | 9.6s | `narrative._value` (لوك-أب feature لكل hypothesis) |
| 34,255 | 8.2s | مقارنات Series `__eq__` + take |
| 39.9M | — | إجمالي الاستدعاءات — ثابت pandas ضخم |

**D) Swing detector — n=10,000 (عدّ مباشر):** rank=8,040 / push=2,829 / **percentile_value=7,383 استدعاء** (np.quantile كامل لكل مرة) + trackerان.

## 2 — complexity map

| primitive | complexity لكل عملية | الإجمالي على n | يستخدمه | allocations | peak memory @44,640 |
|---|---|---|---|---|---|
| `CausalPercentileTracker.rank` | **O(n) مسح Python** | **O(n²)** لكل tracker | volatility(2n استدعاء), volume_delta(2×2n), absorption(2×3n), liquidity, structural_breaks(عند الأحداث), fvg, order_blocks, swings | يهمل | 1,404 KiB |
| `CausalPercentileTracker.percentile_value` | O(n) نسخ `np.fromiter` + O(n log n) فرز `np.quantile` لكل استدعاء | **O(n² log n)** في swings (7.4k استدعاء/10k بار) | swing `_EmpiricalRuntime` فقط | fromiter + sort لكل نداء | — |
| FVG `kb/ks` counters | **O(n) لكل شمعة** فوق كل المرشحين | **O(n²)** | fvg.analyze داخلياً | genexpr لكل شمعة | — |
| Narrative `_value` + label access | O(1) بثابت pandas ضخم لكل خلية | O(bars × hypotheses × features) | narrative.analyze | ~373k DataFrame.__getitem__ / 6k بار | — |
| timeline seal `canonical_sha256` | O(n) مرة واحدة | O(n) | runner (seal + تحقّق bind_interval) | JSON/hash | 1.3s @22.3k |

**الاستدعاءات لكل شهر (44,640):** volatility = 89,280 observe؛ volume_delta×2 = 178,560؛ absorption×2 ≈ 267,840 (عند الأهلية)؛ swings = ~36k rank + ~33k percentile_value؛ FVG = ~11k rank + **~500M genexpr** (الوحش الحقيقي).

## 3 — الدلالات الرياضية الحرفية للـprimitive القديم (مستخرجة من الكود)

1. **read-before-push**: `observe = rank(value)` ثم `push(value)` — percentile الحالي يُحسب على التاريخ **قبل إدراج نفسه** (لا self-inclusion).
2. **ties (mid-rank)**: `percentile = (less + 0.5·equal) / N` حيث N = حجم التاريخ قبل الإدراج؛ less/equal بمقارنة IEEE `<` و`==`.
3. **duplicates**: تبقى في التاريخ مع multiplicity (deque)؛ equal_count يعدها.
4. **NaN**: `nan_policy="skip"` → rank يرجع `accepted=False, percentile=NaN, min/max=NaN` ولا يُدرج (total_skipped)؛ `"raise"` → `CausalPercentileDataError`.
5. **inf / bool**: مرفوضان دائماً (`CausalPercentileDataError`) — «Fix the upstream feature calculation».
6. **warm-up**: تاريخ فارغ → `percentile=NaN, sample_count=0, accepted=True` — **لا bootstrap magic value**.
7. **history**: expanding (deque) افتراضياً؛ `max_history` اختياري = rolling FIFO (deque maxlen) — **المحركات لا تمرره إطلاقاً** (تحقق بالgrep على كل البناءات).
8. **percentile_value(q)**: `np.quantile(np.fromiter(history, float64), q, method="linear")` — الملتزم به عقداً هو **مُقدِّر numpy الخطي**؛ يعتمد على **الحزمة (multiset)** فقط لا على الترتيب. q في [0,1] وإلا ConfigError. تاريخ فارغ → NaN.
9. **extrema (history_min/max)**: مسح خطي بـ`if v < min` و`if v > max` صارمة ⇒ **عند التعادل (±0.0 مثلاً) أول قيمة مُدرجة تفوز وتُبقي sign-bitها** (سلوك حرفي مُكتشَف بالاختبار — انظر §6).
10. **reset**: يمسح التاريخ والعدادات؛ **history_snapshot**: tuple نسخة (debug/tests)؛ **serialization**: لا يوجد؛ **reentrancy**: كائن stateful بلا قفل — استدعاء واحد في كل وقت (الاختبارات: تكرار التشغيل bitwise مطابق).

## 4 — الخوارزميات المرشحة Exact Online (لا مستقبل)

| المرشح | الفكرة | الحالة |
|---|---|---|
| **P1 bisect-list** | قائمة مرتّبة + `bisect_left/right` للعدّات + `insort` (memmove بلغة C) + extrema بقاعدة الأول-يفوز | **مُنفَّذ ومُختبَر** |
| **P2 numpy-buffer** | مصفوفة float64 مسبقّة التخصيص + `np.searchsorted` + إدراج بـmemmove (توسيع ×2) | **مُنفَّذ ومُختبَر — المُوصى به** |
| **P3 treap** | treap بـmultiplicities + أحجام أشجار فرعية (rank = O(log n)) | **مُنفَّذ ومُختبَر** (الأفضل عند 1m) |
| **P4 Fenwick/segment** | يتطلب mapping إحداثيات عالمي مُرتَّب بالقيمة | **مرفوض رسمياً**: الضغط العالمي للإحداثيات = future-fit ⇒ يغيّر causal information contract؛ إحداثيات first-seen لا تحفظ ترتيب القيم؛ أي بديل قانوني يؤول إلى شجرة = P3 |
| **P5 native C** | buffer مرتّب + binary search + memmove في C عبر ctypes (data-structure فقط، بلا business semantics) | **مُنفَّذ ومُختبَر** (gcc متوفر هنا) |
| E) بدائل أخرى | skip-list مفهرس، counting structures | مغطاة كنطاق بواسطة P1/P3؛ لا حاجة |

**الهدف المُتحقَّق:** exact expanding rank من O(n²) إلى **O(n log n) أو O(n) amortized** بلا قراءة/ملاءمة مستقبل.

## 5 — benchmark old vs prototypes (نظيف بلا tracemalloc)

**observe() stream:**

| n | P0 القديم | P1 bisect | P2 numpy | P3 treap | P5 native C |
|---|---|---|---|---|---|
| 1,000 | 0.029s | 0.004s | 0.010s | 0.011s | 0.008s |
| 5,000 | 0.689s | 0.021s | 0.053s | 0.077s | 0.048s |
| 10,000 | 2.833s | 0.047s | 0.110s | 0.130s | 0.087s |
| 20,000 | 11.337s | 0.104s | 0.238s | 0.322s | 0.232s |
| **44,640** | **58.343s** | **0.562s (104x)** | **0.646s (90x)** | **0.726s (80x)** | **0.434s (134x)** |
| 100,000 | (≥ 4.8 min مُقدَّر) | 2.116s | 5.284s | 5.974s | 4.380s |
| 250,000 | (≥ 27 min مُقدَّر) | 7.620s | 16.864s | 16.270s | 13.667s |
| 1,000,000 | (أيام) | 87.9s | 126.1s | **28.1s** | 79.7s |

**تأكيد التربيع للقديم:** n×2 ⇒ زمن ×4.0-5.1 (التنبؤ التربيعي ×4.0-5.0) عند كل قفزات القياس — **O(n²) مؤكَّد**.

**percentile_value(0.5) بعد n إدراج:**

| n | P0 القديم | P1 | P2 | P3 | P5 |
|---|---|---|---|---|---|
| 10,000 | 0.48ms | 0.46ms | **0.16ms** | 3.23ms | 0.18ms |
| 44,640 | 1.92ms | 2.13ms | **0.47ms (4x)** | 50.4ms | 0.58ms |

**الذاكرة (tracemalloc peak @44,640):** P0=1,404K / P1=1,816K / P2=**769K** / P3=6,069K / P5=~1K (C heap).

**عتبات الأداء المستهدفة (لم تُستخدم كادعاء قبل القياس — والقياس يتجاوزها):** primitive ≥ 20x ⇒ **مُتحقَّق 80-134x**؛ محركات tracker-dominated ≥ 10x ⇒ volatility = 96.6% rank ⇒ **~50x مُقدَّر للمحرك كله**.

## 6 — نتائج EQUIVALENCE GATE

**36/36 PASS — bitwise (float.hex) على كل حقول `PercentileObservation` + percentile_value + أصناف الاستثناءات.**

البطارية (كل حالة × nan_policy=skip/raise): empty / one_row / duplicates_mixed / all_equal / monotonic_increasing / monotonic_decreasing / alternating / random_seeded (500) / extreme_magnitudes (1e308, 5e-324, subnormals) / exact_ties_heavy / **signed_zero_mix** / NaN-skip stream / error cases (bool, inf, NaN-raise) — لكل من P1/P2/P3/P5 مقابل P0.

**اكتشاف حرفي (لم يُغطَّ بالنظرية):** انحراف sign-bit في `history_min/max` لـ±0.0 عند التعادل — الأصل يبقي أول قيمة مُدرجة (`if v < min` صارم). أُغلق بمحاكاة **نفس القاعدة حرفياً** (strict-compare، الأول يفوز) داخل الـprototypes ⇒ بعد الإصلاح **bitwise كامل حتى sign-bit الأصفار** — بلا أي tolerance مُختلَق. معيار التكافؤ مأخوذ من العقد نفسه: العدّات أعداد صحيحة، النسبة `(less+0.5·equal)/n` حرفياً، و`percentile_value` = **نفس دالة numpy `method="linear"` على نفس الحزمة** (العقد ي钉 المُقدِّر لا تمثيلاً معيناً — والتماثيل bitwise مُثبَّتة تجريبياً لكل الحالات).

## 7 — نتائج CAUSALITY GATE

**15/15 PASS** لكل من P0/P1/P2/P3/P5:
- outputs ≤ T **تتغير صفر** عند إضافة future suffix مختلف تماماً (suffix ×2 مقارنة).
- تكرار التشغيل: bitwise مطابق.
- prefix truncation: مطابق تماماً.
- البنى Online كلها تُبنى من البادئة فقط (لا قراءة/fit للمستقبل في أي مرشح — مُراجَع بنيوياً: لا إحصاءات/إحداثيات/تطبيع على مستوى الكيان الكامل).

## 8 — خطة DAG + content-addressed cache (خارج CLOSED)

**DAG (عقد التنفيذ):**
```
sources(load+cross_witness) → canonical_bundle + executed_flow → timeline_seal
  ├─ volatility │ session │ fvg │ flow_proxy │ flow_actual │ htf        (مستقلة)
  ├─ absorption_proxy ← flow_proxy   │  absorption_actual ← flow_actual
  ├─ swings → sequence → {structural_breaks → order_blocks, liquidity, dealing_range}
  ├─ evidence_actual ←(flow_actual+absorption_actual+السطح المشتركة)
  ├─ evidence_proxy  ←(flow_proxy+absorption_proxy+السطح المشتركة)
  ├─ narrative_actual ← evidence_actual │ narrative_proxy ← evidence_proxy
  └─ reports(A-F + chart + preview)
```
كل عقدة تُنفَّذ **مرة واحدة**؛ لا إعادة تشغيل engine causal لنفس: `input hash + engine identity/version + policy hash`.

**Cache (مجلد خارجي `field_run_cache/`):**
`cache_key = SHA256(input artifact hashes + engine module path + engine module file sha256 + policy hash (quantile/priors/sessions/htf) + contract version strings + column schema)`.
- القيمة: frames محفوظة (feather/parquet) + hashاتها الداخلية.
- أي mismatch ⇒ cache miss تام.
- **الـcache لا يتجاوز verify/integrity أبداً**: تحقّق المصادر (adapter verify + cross-witness + بصمات) يُعاد دائماً؛ الـcache يُلغي فقط إعادة `analyze()` المُكلفة على مدخلات مطابقة bit-for-bit.

## 9 — خطة التوازي

| العقدة | process-safe؟ | ملاحظة |
|---|---|---|
| volatility/session/fvg/flows/absorption/htf/swings-chain | **نعم** (دالة نقية على frame + حالة داخلية جديدة) | pool عبر processes (GIL يمنع threads) |
| narrative_actual / narrative_proxy | نعم لبعضهما | يتوازيان |
| evidence ×2 | نعم | |
| داخل المحرك (الحلقة per-bar) | **لا** | حالة تتابعية سببية — لا تُقسَّم |
| reporting | نعم | |

**بلا ادعاءات threads:** الأرقام أعلاه single-thread مُقاسة. الربح المتوقع من التوازي وحده: **1.5-2.5x** على الحائط (FVG وحده يمثل النصف) — **التوازي ليس الحل**؛ استبدال الـprimitive + إصلاح FVG هما الحلان.

## 10 — توصية Native Acceleration: **NO (في هذه المرحلة)**

- P5 native = 134x مقابل P1 = 104x و P2 = 90x على الشهر ⇒ الزيادة **~30% فقط** فوق pure Python.
- التكلفة: أداة بناء (MSVC/mingw على Windows)، wheels لكل منصة، fallback path، فحص determinism إضافي، صعوبة audit.
- numpy أصلاً dependency مُلزِّم للمشروع ⇒ **P2 بلا أي اعتماد جديد**.
- **الاستثناء:** إذا أصبحت تدفقات السنة (525,600+) روتينية، يُعاد النظر (أو يُستخدم P3 treap pure-Python: 28s عند 1m — الأفضل توسيعاً).

## 11 — إسقاطات زمن التشغيل (شهر/سنة)

على آلة المالك (القياس: vol=581s, fvg=1594s؛ نسبة ≈ 9-10x آلة البناء):

| السيناريو | الشهر (44,640) | السنة (~525,600) |
|---|---|---|
| **الحالي (قبل أي patch)** | 45-75 دقيقة (غير عملي) | **أيام** (O(n²)) |
| **+ استبدال primitive فقط** (P2/P1) | **25-35 دقيقة** (FVG-bound: ~1500s تبقى) | ~2-4 أيام (FVG-bound) |
| **+ patch مُجمِّع FVG** (kb/ks accumulator) | **6-10 دقائق** (narrative-bound) | **40-90 دقيقة** |
| **+ patch narrative positional lookup** | **3-5 دقائق** | ~30-60 دقيقة |
| + توازي processes (فوق الثلاثة) | ~2-4 دقائق | ~25-45 دقيقة |

## 12 — ملفات CLOSED التي ستحتاج PATCH لاحقاً (بتفويض منفصل)

1. **`src/trading_system/core/causal_percentile.py`** (الأساسي — §13): استبدال مسار expanding داخلياً بـsorted-buffer؛ API والمراقبات كما هي حرفياً.
2. **`src/trading_system/zones/fvg.py`** (ثانوي): `kb[i]/ks[i]` = مجاميع تراكمية بدل إعادة `sum(...)` فوق كل المرشحين كل شمعة (O(n²)→O(1) لكل شمعة) — إصلاح semantics-preserving يحتاج بطاقات تكافؤ خاصة به.
3. **`src/trading_system/decision/narrative.py`** (اختياري): `_value` + label-access → مصفوفات numpy positional مُحمَّلة مرة واحدة (نفس القيم — نفس المخرجات).
4. **لا يحتاج تعديل:** swing_detector / structural_breaks / volume_delta / absorption / liquidity / order_blocks / volatility — **يكتسبون تلقائياً** من استبدال الـprimitive.

## 13 — أقل patch surface (المقترح الدقيق)

**ملف واحد، داخل `CausalPercentileTracker` فقط:**
- `rank()`: العدّات عبر `np.searchsorted` على buffer مرتّب (أو bisect على list) بدل حلقة المسح؛ extrema بمتتبعين strict-compare-first-wins.
- `push()`: إدراج بـmemmove (C) في buffer مرتّب.
- `percentile_value()`: تمرير نسخة view مباشرة إلى `np.quantile(..., method="linear")` بدل `np.fromiter` من deque.
- مسار `max_history` (غير مستخدم من المحركات): يبقى على المنطق الحالي أو يُعاد حساب extrema بمسح FIFO مطابق.
- **صفر تغيير API، صفر تغيير مراقبات، صفر تغيير thresholds/detector definitions.**
- التحقق: بطاقات §6/§7 كاملة + 1045 اختبارات المشروع كما هي + rerun ميداني مطابق.

## 14 — المخاطر

1. **sign-bit الأصفار** (مُكتشف ومُغلَق بقاعدة مطابقة — انظر §6)؛ يبقى خطر إعادة ظهوره لو تغيّر مسار extrema — البوابة تحميه.
2. **مسار max_history** غير مغطى بالمحركات — يبقى خلفية خطر منخفضة (بطارية إضافية مقترحة عند التنفيذ).
3. **np.quantile وترتيب الإدخال**: مُثبَّت تجريبياً bitwise على كل الحالات (يعتمد على الحزمة) — يبقى خطر نظري عند ترقيات numpy → البوابة تُعاد على أي ترقية.
4. **FVG patch** يتطلب فهم أعمق للمخرجات المُشتقّة (kb/ks تدخل أعمدة معروفة) — بطاقات تكافؤ مستقلة إلزامية.
5. **Windows/numpy versions**: P2 يعتمد على numpy فقط (موجود أصلاً)؛ P1 كfallback لا يعتمد على شيء.
6. الأداء المُقدَّر للشهر ما بعد patches (3-5 دقائق) يبقى تقدير آلة المالك ratio ≈ 9-10x — يُتحقق بالميدان.

## 15 — BUILD READY

**Primitive patch (§13): YES** — تصميم + prototypes + 36/36 equivalence + 15/15 causality + benchmarks مكتملة؛ سطح الـpatch = ملف واحد داخلي؛ خطة التحقق جاهزة (gate battery + 1045 + field rerun).

**FVG accumulator patch: YES (design) — PENDING OWNER APPROVAL** (سطح CLOSED منفصل).
**Narrative positional patch: OPTIONAL — PENDING OWNER APPROVAL**.
**Native layer: NO** (غير مبرر حالياً — انظر §10).
**تنفيذ أي production patch الآن: ممنوع (كما فُرض) — هذا التقرير DESIGN ONLY.**

---
**STOP.**

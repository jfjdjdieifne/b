# 32 — EXACT PERFORMANCE V2 — PATCHED — PENDING RE-AUDIT

الحالة: **STOP — PENDING RE-AUDIT** (تسليم مرشّح، لا يُعتمد قبل تدقيق مستقل على جهاز المالك).

القاعدة المفروضة: **أسرع تسريع ممكن — بصفر فقدان أي ذرّة دقّة**. كل تغيير مُثبت old==new على مستوى البتة.

---

## 1. النطاق (3 ملفات مُصرَّح + اختباراتها فقط)

| الملف | قبل (sha256) | بعد (sha256) |
|---|---|---|
| `src/trading_system/core/causal_percentile.py` | `d0db2281…d88696` | `1543794f…1f0f8654` |
| `src/trading_system/zones/fvg.py` | `c6f46286…e58cd2` | `1df18e55…31dcd4b` |
| `src/trading_system/decision/narrative.py` | `c9f8c751…1dc118e0` | `407c4d2f…2b0dd24f9` |
| `tests/test_causal_percentile.py` | (قديم) | `55f2be1b…3e11f228` |
| `tests/test_fvg.py` | (قديم) | `471702f7…22672b05a` |
| `tests/test_narrative.py` | (قديم) | `c9c30000…fbb0740` |

جديد (دعم اختباري فقط): `tests/_patch_reference_src/{causal_percentile,fvg,narrative}_pre.py` — نسخ حرفية pre-patch، مثبّتة بـsha256 داخل الاختبارات نفسها. لا ملف إنتاجي آخر لُمس.

**MANIFEST.sha256**: لم يُعدَّل (183 سطراً). الفحص الآن: **177 OK / 6 stale** — الستة = الملفات الستة أعلاه (مصرَّح بها). لا ملف CLOSED آخر تغيّر.

---

## 2. ماذا تغيّر بالضبط

### PATCH-1 — `causal_percentile.py` (exact online order-statistics)
- `rank()`: بدل المسح O(n) لكل قيمة → `bisect_left/right` على multiset مرتّب مُحافَظ عليه (إدراج/إقصاء `insort`/`pop` بالبتة). العدّادات `less/equal/greater` = `(less + 0.5*equal)/n` حرفياً.
- `history_min/max`: قاعدة strict-compare **first-wins (منها ±0.0)** — إجمالي incremental، وإعادة حساب دقيقة (نفس مسح الأصل) فقط عند إقصاء extremum (فقط `max_history`).
- `percentile_value()`: مسار سريع = numpy `linear` حرفاً بحرف: `virtual=(n-1)*q`، bounds حسب `_get_indexes`، `_lerp` بفرع `t≥0.5`. عند وجود **-0.0 و+0.0 معاً** والطرف المختار صفر → **fallback حرفي** للمسار القديم (`np.fromiter + np.quantile`) لأن ترتيب sort لتعادل ±0.0 غير مستقر ولا يمكن تقليده تدريجياً. **لا tolerance إطلاقاً.**
- `read-before-push` (observe = rank ثم push) — كما هو. `max_history` FIFO eviction + `history_snapshot` + reset + رسائل الاستثناءات — كما هي حرفياً.

### PATCH-2 — `fvg.py`
- **2a (المُصرَّح حرفي):** `kb[i]=sum(genexpr)` / `ks[i]=len-kb` → عدّادات تراكمية `kb_run/ks_run` عند الإنشاء.
- **2b («الأسرع بدون فقدان دقّة»):** حلقة `for f in fs` فوق كل الكيانات مع كل شمعة (O(n×entities)) → **مسح numpy لكل كيان مرة واحدة** (first-occurrence لكل شرط من الشروط الخمسة، strict/non-strict محفوظة، reclaim يبدأ حصراً بعد close وبعده حصراً). مبرر القابلية: الإطار النهائي يُرتَّب بـ`sort_values([event_position, fvg_id, _o])` بمفاتيح **فريدة** ⇒ ترتيب الإدخال ليس جزءاً من العقد. **الإخراج مطابق بالبتة** (مُثبت أدناه). creation time/الكيانات/الأحداث/lifecycle/availability — كما هي تماماً.

### PATCH-3 — `narrative.py`
- ربط الأعمدة مرة واحدة (`bound_columns` + `_value_prebound`) بدل `evidence[column]` لكل صف/سمة. نفس `.iloc` ونفس القيم والأنواع و`pd.isna`. الـ`_value` الأصلي محفوظ كما هو.

---

## 3. الأبواب (كلها خضراء — تُفحص بأمرك)

| البوابة | النتيجة |
|---|---|
| البطارية اليدوية vs `np.quantile(method="linear")` | **30,888/30,888 bitwise** (q: 0/1/0.5/كسرية/nextafter/random، subnormals، magnitudes ضخمة، ±0.0، duplicates) |
| Differential old-vs-new (مرجع pre-patch مثبّت sha256) | tracker: كل حقل بـ`float.hex` + استثناءات class+message — مطابق؛ FVG: `assert_frame_equal(check_exact, check_dtype)` **+ مقارنة uint64 بعموديات float** على 11 إطاراً (no-candidates/bull/bear/alternating/many/realistic/stress 300+600/signed-zeros/empty)؛ narrative: كل الأطر السبعة + `_value`==`_value_prebound` لكل خلية |
| Causality | prefix(T)==truncated + future-suffix mutation لا يغيّر ≤T — للثلاثة |
| Mutation proofs (4) | tie mid-rank مكسور / read-before-push مكسور / FVG increment مكسور / narrative row-alignment مكسور — **كلها تُسقط الاختبارات** (إثبات حساسية الأدلة) |
| تطابق Outputs مركَّب | field-synth بصمة baseline == all-three: `3cede027…` (240) و `3301670a…` (3000) |
| اختبارات الوحدات القائمة | 3 ملفات: كلها تمر (لم يُغيَّر أي سلوك عام) |

---

## 4. القياسات (sandbox؛ جهاز المالك ≈ 10x أبطأ)

**Tracker observe (rank+push لكل قيمة):**
| n | قديم | جديد | سرعة |
|---|---|---|---|
| 44,640 | 51.4s | 0.278s | **184x** |
| 100,000 | 249.6s | 0.963s | **259x** |
| 250,000 | (متوقع ~26min) | 4.84s | ~320x |
| 1,000,000 | (متوقع ~7h تربيعي) | 79.4s | — |

**percentile_value (65 استعلام):** 44,640: 0.112s → 0.0023s = **48.6x** (1m: جديد 3.5s).

**FVG analyze (A=قديم كلي، B=PATCH-1 فقط، C=PATCH-1+2):**
| n | A | C | سرعة |
|---|---|---|---|
| 10,000 | 7.0s | 0.17s | 41x |
| 20,000 | 37.0s | ~0.4s | ~90x |
| **44,640** | **155.8s** | **0.97s** | **160x** |
| 44,640 dense | 12.1s@10k | 0.29s@10k | 41x |

**الشهر الكامل المركَّب (field-synth 44,640، كل الفروع + narrative×2):**
`total_after_load` = **22.1s** (run_engines 14.75s + evidence/narrative 3.87s + seal 3.48s). بصمة outputs = `209d131a…`.

**narrative وحده:** لا تراجع (1.0x على التكوين الخفيف)؛ الأثر الحقيقي للربط يظهر مع مجموعة الميزات الكاملة (كان 271k lookup ساخناً في الـprofile).

---

## 5. إسقاط جهاز المالك (شهر مايو كامل)

| المرحلة | قياسك القديم | المتوقع الآن |
|---|---|---|
| Dynamic Volatility | 581s | **~20-35s** (96.6% rank → 184x) |
| FVG | 1594s | **~10-20s** (160x) |
| swings (percentile_value) | جزء من الـ1.5h | ~48x على الاستدعاءات |
| narrative ×2 | جزء من الـ1.5h | ≤ السابق (بلا تراجع) |
| **الإجمالي** | **1.5h+ ولم يكتمل** | **~3-8 دقائق** (المُركَّب sandbox 22.1s ≈ 3.5-4.5min على جهازك + الحفظ/CSV) |

---

## 6. ما يُشغَّل على جهاز المالك (خطوة تحقق واحدة)

```
python -m pytest tests -q
```
(الاختبارات تحمل المرجع pre-patch داخل `tests/_patch_reference_src/` وتجري التفاضل الكاملة بنفسها — لا حاجة لأي بيانات مالك.)

ثم تشغيل الـfield runner المعتاد — نفس الأمر، بلا أي خيار جديد.

---

## 7. بيانات التدقيق السريع

- نسخ pre-patch مثبّتة داخل الاختبارات: `tests/_patch_reference_src/*_pre.py` (sha256 مُثبَّت في رأس كل ملف اختبار).
- سجلات القياس: `/home/user/perf_lab/bench_chunk1_results.txt`, `bench_fvg_final_*.txt`, `bench_narrative_final.txt`, `field_results/all-three.json`.
- الملفات المضافة للـtree: 3 نسخ مرجعية فقط (اختبارية). لا شيء خارج `tests/`.

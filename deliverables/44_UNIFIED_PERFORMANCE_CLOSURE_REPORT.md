# UNIFIED_PERFORMANCE_CLOSURE_REPORT

## EXACT PERFORMANCE V2 + TEST-SUITE ACCELERATION — Unified Closure

**Date**: 2026-09-30
**Owner authorization**: CLOSURE AUTHORIZED (for the independently accepted artifacts only)
**Governing baseline**: Independent Unified Re-Audit — **ACCEPTED FOR CLOSURE**

---

## FINAL STATE

# STOP — OWNER REVIEW

الإغلاق الوثائقي اكتمل (وثائق الإغلاق + MANIFEST محدَّث — 185/185 ALL OK، 0 stale)، لكن بوابة
**FIELD RUNNER GUARD** فشلت — **حصراً** — لأن الحارس يثبت عمداً pre-closure MANIFEST digest /
10-stale state. القاعدة الحاكمة: STOP — OWNER REVIEW. **الحارس لم يُعدَّل إطلاقاً**
(`field_runner/runner_tests/test_runner_guards.py` كما هو). لا إصلاح ارتجالي. exact failure +
expected/actual أدناه — قرار المالك مطلوب (re-pin مُصرَّح للحارس أو أمر آخر).

---

## 1) PRE/MANIFEST IDENTITY (pre / post)

| | قبل الإغلاق | بعد الإغلاق |
|---|---|---|
| MANIFEST lines | **183** | **185** |
| MANIFEST sha256 | `7796a73fc30fc311902d7ba8e033eb1699a73c5db10e824d02653fbdd1681587` | `12c66abe6f18300f2e00cb5c4befeafe1e3dc67c2ca50bc71db74db9ba8b367d` |
| OK | 173 | **185** |
| stale | 10 (accepted) | **0** |
| missing | 0 | **0** |

- `sha256sum -c MANIFEST.sha256` بعد الإغلاق: **ALL MANIFEST ENTRIES OK** (185/185).
- العدد النهائي محسوب من التغييرات المشروعة فعلياً: 183 + سطران جديدان لوثيقتَي الإغلاق الجديدتين = 185 (لم يُفترض مسبقاً).

## 2) EXACT CHANGED FILES (5 فقط)

| الملف | نوع التغيير | قبل | بعد |
|---|---|---|---|
| `docs/STATUS.md` | محدَّث | `71ba257d…5d7003` | `c16f19e0351660beed1f8926c07848ee553af8d2602eab925c1899abb346d6e9` |
| `docs/FINAL_VALIDATION.md` | محدَّث | `765e66d2…75e9b1` | `aea8a551d098268120147dd381ddae0e29b5959611e30d2f1956245478bb9e05` |
| `docs/releases/MILESTONE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_CLOSED.md` | **جديد** | — | `1778acdfc0241fd879a322c13061efbc50af6a3d612b0d9b648be44659afca16` |
| `docs/releases/MODULE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_ACCEPTED_SRC_TESTS.sha256` | **جديد** | — | `82b0457a10c84fc104ad43f27139869f0138875558f8c0ae24b780ed0587fe6e` |
| `MANIFEST.sha256` | محدَّث (آخر كتابة) | `7796a73f…81587` | `12c66abe…8b367d` |

لا ملف آخر تغيّر. لا cleanup ولا refactor ولا performance ولا test changes.

## 3) CLOSURE DOCUMENT PATHS

```text
milestone:  docs/releases/MILESTONE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_CLOSED.md
seal:       docs/releases/MODULE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_ACCEPTED_SRC_TESTS.sha256
status:     docs/STATUS.md            (CLOSED + unified independent re-audit accepted + 1072/1072 + certification boundary + no semantic/causal/contract change)
validation: docs/FINAL_VALIDATION.md  (1072/1072 + manifest pre-closure identity + performance/equivalence gates + certification boundary + field_runner 36/36 كأداة خارجية موسومة)
```

الحارة تحوي بصمات الملفات العشرة المقبولة **SHA256 كاملاً بلا اختصار**، ومطابقة لقائمة المالك حرفياً (تحقّق `sha256sum -c` = 10/10 OK، و`diff` = LITERALLY EQUAL).

## 4) MANIFEST RULE — كيف طُبِّق

- الملفات العشرة accepted stale **موجودة أصلاً** في MANIFEST → **استُبدلت hashes القديمة بالبصمات المقبولة حرفياً** (استبدال أسطر، لا حذف).
- الوثائق الموجودة (`docs/STATUS.md`، `docs/FINAL_VALIDATION.md`) **أُعيد بصم أسطرها** في مكانها.
- الوثائق الجديدة (milestone + seal) **أُضيفت كسطرين جديدين** — لأن repository convention يتتبع كل `docs/releases/*` (20/20 من ملفات الإغلاق السابقة متتبَّعة).
- خطوط المسارات محفوظة بصيغتها الأصلية (`./` حيث كانت).

## 5) FULL PYTEST

| التشغيل | النتيجة |
|---|---|
| pre-closure | **1072 collected / 1072 passed** (exit 0) — العلامات: 1072 نقطة كلها `.` |
| post-closure | **1072/1072 passed** (exit 0) — العلامات: 1072 نقطة كلها `.` |

الزيادة عن خط الأساس 1045 = **+27 اختباراً** داخل ملفات الـ5 المقبولة فقط (13→24، 11→16، 48→53، 14→18، 17→19) — حسابياً متسق مع 1045+27=1072.

## 6) FIELD RUNNER TESTS + EXACT FAILURE

| التشغيل | النتيجة |
|---|---|
| pre-closure | **36/36 passed** (11.34s) |
| post-MANIFEST | **35 passed, 1 failed** (11.91s) |

**الفشل الوحيد** — `runner_tests/test_runner_guards.py::test_closed_project_manifest_untouched` —
**فشل فقط لأن الحارس يثبت عمداً pre-closure MANIFEST digest / 10-stale state** (كما توقّعت قاعدة
المالك). **الحارس لم يُعدَّل.**

### exact failure

```text
>       assert _sha256_file(manifest_path) == closed_manifest_sha256
E       AssertionError: assert '12c66abe6f18...74db9ba8b367d' == '7796a73fc30f...53fbdd1681587'
E
E       - 7796a73fc30fc311902d7ba8e033eb1699a73c5db10e824d02653fbdd1681587
E       + 12c66abe6f18300f2e00cb5c4befeafe1e3dc67c2ca50bc71db74db9ba8b367d

runner_tests/test_runner_guards.py:111: AssertionError
```

### expected / actual

```text
gate                                     expected (pinned by guard)                  actual (post-closure)                       verdict
MANIFEST.sha256 digest                   7796a73fc30fc311902d7ba8e033eb1699a73c5d   12c66abe6f18300f2e00cb5c4befeafe1e3dc67c2   MISMATCH — تثبيت عمدي لما قبل الإغلاق
                                         b10e824d02653fbdd1681587                    ca50bc71db74db9ba8b367d
manifest_lines                           183                                         185                                         MISMATCH — سطرا الإغلاق الجديدان (مقصودان)
bad (stale)                              10                                          0                                           MISMATCH — الـ10 أُغلقوا رسمياً (مقصود)
ok                                       173                                         185                                         MISMATCH — كل الأسطر OK (مقصود)
the 10 patched_seal file digests         (البصمات المقبولة العشرة)                    مطابقة 10/10                                MATCH — الملفات لم تتغير
```

**الخلاصة**: الفشل = تثبيت الحارس المقصود لحالة ما قبل الإغلاق (digest + 183 + 10-stale) — لا
drift حقيقي. بصمات الملفات العشرة داخل الحارس كلها **MATCH**. تعديل الحارس ممنوع في CLOSURE ONLY؛
يحتاج **قرار مالك** (re-pin مُصرَّح أو أمر آخر).

## 7) BEFORE/AFTER HASHES — الملفات العشرة المقبولة

| الملف | قبل | بعد | == القائمة |
|---|---|---|---|
| `src/trading_system/core/causal_percentile.py` | `1543794f…f8654` | `1543794f…f8654` | ✓ |
| `src/trading_system/decision/narrative.py` | `407c4d2f…d24f9` | `407c4d2f…d24f9` | ✓ |
| `src/trading_system/research/hashing.py` | `f2a64c8e…d5c7d` | `f2a64c8e…d5c7d` | ✓ |
| `src/trading_system/research/manifest_identity.py` | `4c88fc44…92414b` | `4c88fc44…92414b` | ✓ |
| `src/trading_system/zones/fvg.py` | `1df18e55…cd4b` | `1df18e55…cd4b` | ✓ |
| `tests/test_causal_percentile.py` | `55f2be1b…f228` | `55f2be1b…f228` | ✓ |
| `tests/test_fvg.py` | `471702f7…b05a` | `471702f7…b05a` | ✓ |
| `tests/test_narrative.py` | `c9c30000…b0740` | `c9c30000…b0740` | ✓ |
| `tests/test_research_hashing.py` | `d9eaf051…61e67` | `d9eaf051…61e67` | ✓ |
| `tests/test_research_manifest_identity.py` | `15d1a727…485d49` | `15d1a727…485d49` | ✓ |

SHA256 قبل == بعد **حرفياً** (الكامل في الحارة: `docs/releases/MODULE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_ACCEPTED_SRC_TESTS.sha256`).

## 8) PROOF: src/tests UNCHANGED DURING CLOSURE

- لقطة كاملة لكل ملفات `src/` + `tests/` (106 ملفات، بلا pycache) قبل الإغلاق وبعده.
- `diff` بين اللقطتين: **BYTE-IDENTICAL — لا فرق واحد**.
- الاختلافات الوحيدة في الشجرة كلها = الملفات الخمسة في القسم 2 (وثائق + MANIFEST).

## 9) FINAL RECORDS (post-closure gate 7)

```text
final MANIFEST line count:   185
final MANIFEST SHA256:       12c66abe6f18300f2e00cb5c4befeafe1e3dc67c2ca50bc71db74db9ba8b367d
all-manifest OK count:       185/185 (0 stale, 0 missing)
changed-file inventory:      docs/STATUS.md; docs/FINAL_VALIDATION.md;
                             docs/releases/MILESTONE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_CLOSED.md (new);
                             docs/releases/MODULE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_ACCEPTED_SRC_TESTS.sha256 (new);
                             MANIFEST.sha256 (last write)
milestone path:              docs/releases/MILESTONE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_CLOSED.md
acceptance seal path:        docs/releases/MODULE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_ACCEPTED_SRC_TESTS.sha256
final STATUS hash:           c16f19e0351660beed1f8926c07848ee553af8d2602eab925c1899abb346d6e9
final FINAL_VALIDATION hash: aea8a551d098268120147dd381ddae0e29b5959611e30d2f1956245478bb9e05
full pytest:                 1072/1072 pre-closure; 1072/1072 post-closure (exit 0)
field_runner tests:          36/36 pre-closure; 35/36 post-MANIFEST (guard pin only — see section 6)
```

## 10) CERTIFICATION BOUNDARY

هذا الإغلاق يثبت **فقط**:

- EXACT PERFORMANCE V2 و TEST-SUITE ACCELERATION حافظتا على السلوك السببي/الدلالي والعقود المقبولة ضمن نطاق التدقيق؛
- بصماتهما أصبحت جزءاً من baseline الرسمي.

**لا يثبت**: predictive support — edge — profitability — MUF correctness — Model — Strategy — Signal — PnL.

لا semantic/causal/contract change. RESEARCH-DEBT-020..025 تبقى OPEN.

## 11) OBSERVATIONS (لا مسّ — خارج النطاق)

- عنوان `docs/FINAL_VALIDATION.md` التاريخي («Through Module 6.2A-4 V1 Stage 3 Closure») متأخر عن محتواها — تُرك كما هو (اصطلاح الجولات السابقة: append-sections فقط)؛ مسجَّل هنا للأمانة فقط.

---

# STOP — OWNER REVIEW

**END OF REPORT. لا MUF. لا شيء بعد هذا السطر.**

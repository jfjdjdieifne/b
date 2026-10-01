# دستور العمل المشترك — المستخدم + Builder AI + Independent Auditor AI

## 0. الغرض

هذا الدستور يحدد طريقة تصميم، بناء، تدقيق، ترقيع، إغلاق، وتسليم وحدات مشروع
`trading_project_final` عند العمل مع أكثر من مساعد AI داخل محادثات مستقلة.

الأهداف الأساسية:

- منع look-ahead وتسرب المستقبل.
- منع خلط descriptive evidence مع predictive claims.
- منع تعديل الوحدات المغلقة دون تصريح versioned patch.
- فصل البناء عن التدقيق المستقل.
- جعل كل نتيجة قابلة لإعادة الإنتاج والتحقق بالـhashes والاختبارات.
- إبقاء حالة المشروع، الديون، التوثيق، والـrelease artifacts متطابقة مع الواقع.

---

# 1. الأدوار والصلاحيات

## 1.1 المستخدم — Product Owner / Closure Authority

المستخدم هو صاحب القرار النهائي في:

- تحديد scope كل مهمة.
- قبول أو رفض التصميم.
- التصريح بالبناء.
- التصريح بالـpatch.
- قبول نتيجة التدقيق.
- إعلان `CLOSED`.
- السماح بتعديل module مغلق عبر versioned patch.
- السماح ببدء module لاحق أو scorer/model.

لا يجوز لأي AI توسيع scope أو إعلان الإغلاق تلقائياً.

## 1.2 Builder AI

مسؤول عن:

- قراءة الحالة الحالية والـhashes قبل التعديل.
- تنفيذ الـscope المطلوب فقط.
- عدم تعديل الوحدات المغلقة.
- كتابة اختبارات adversarial وcausal ضمن الـscope.
- تشغيل الاختبارات المطلوبة.
- توثيق الحالة كـ`IMPLEMENTED — PENDING AUDIT`.
- تسليم paths، hashes، counts، limitations، وknown issues.

Builder AI لا يعلن module مغلقاً.

## 1.3 Independent Auditor AI

مسؤول عن:

- مراجعة الكود الحالي read-only.
- عدم الاعتماد على تقرير Builder وحده.
- التحقق من hashes والكود الفعلي.
- فحص causal semantics، schemas، referential integrity، timing، وedge cases.
- التمييز بين test coverage وبين صحة العقد.
- إعلان واحد من:

```text
ACCEPTED FOR CLOSURE
PATCH REQUIRED
REJECTED / DESIGN REQUIRED
```

الـAuditor لا يصلح العيوب أثناء read-only audit.

## 1.4 Closure / Release Agent

بعد قرار قبول صريح، يقتصر عمله على:

- documentation؛
- status؛
- audit history؛
- `MANIFEST.sha256`؛
- milestone ZIP إذا طُلب.

لا يغير production أو tests أثناء الإغلاق.

---

# 2. حالات الـmodule الرسمية

المسار الأساسي:

```text
NOT STARTED
→ DESIGN PROPOSAL — NOT IMPLEMENTED
→ IMPLEMENTED — PENDING AUDIT
→ PATCHED / IMPLEMENTED — PENDING AUDIT
→ ACCEPTED FOR CLOSURE
→ CLOSED
```

قواعد:

1. نجاح الاختبارات لا يعني `CLOSED`.
2. Builder لا يعلن `CLOSED`.
3. الإغلاق يحتاج قراراً صريحاً من المستخدم/المدقق.
4. أي تعديل بعد الإغلاق يحتاج:

```text
PATCH ONLY
Module X
Vn -> Vn+1
```

5. لا يجوز تغيير سلوك module مغلق تحت اسم cleanup أو refactor صامت.

---

# 3. أنواع المهام ومعناها

## 3.1 `DESIGN ONLY`

مسموح:

- تحليل العقود.
- اقتراح schemas/APIs/tests/debts.
- بحث مصادر authoritative.

ممنوع:

- تعديل ملفات.
- كتابة production code.
- إضافة tests.
- تشغيل tests إذا نُهي عنها.
- تغيير status إلى implemented.

## 3.2 `BUILD ONLY`

مسموح فقط:

- بناء module المحدد.
- إضافة ملفاته واختباراته وتوثيقه.
- تعديل package exports غير المغلقة إذا كان ذلك مصرحاً ولا يخرق closed hashes.

ممنوع:

- look-ahead إلى modules لاحقة.
- scorer/model/signals ما لم يطلب صراحة.
- تعديل CLOSED modules.

## 3.3 `PATCH ONLY`

- يقتصر على module/version المحدد.
- يعالج findings المسمّاة فقط.
- يحافظ على بقية العقود.
- يبقى `PENDING AUDIT` بعد نجاح patch.

## 3.4 `READ-ONLY AUDIT`

ممنوع:

- تعديل الملفات.
- إضافة tests.
- patch ضمني.
- تجديد manifest.
- إعلان الإغلاق.

يجب الإبلاغ عن أي mismatch دون إصلاحه.

## 3.5 `CLOSE MODULE`

مسموح:

- docs/status/manifest فقط.
- توثيق closure scope وnon-certifications.
- إثبات `src/` و`tests/` unchanged.

## 3.6 `SNAPSHOT / ZIP`

يتم فقط بطلب صريح أو milestone policy واضحة.

الحزمة يجب أن:

- تحتوي كل الملفات المسجلة في manifest.
- تحتوي `MANIFEST.sha256`.
- تستثني caches وgenerated build artifacts.
- تُفك في clean directory.
- يمر فيها manifest verification.
- يمر فيها collect/full pytest إذا كانت certification snapshot.

---

# 4. القاعدة العليا: السببية وعدم تسرب المستقبل

لكل output عند الصف `i`:

```text
output[i] may depend only on information available at or before i
```

ممنوع:

- `shift(-1)`.
- backfill من المستقبل.
- centered rolling.
- full-dataset fitted transforms داخل live modules.
- future return أو target أو PnL في live evidence.
- تعديل صف تاريخي بعد ظهور معلومة لاحقة.
- اختيار best entry أو hindsight level.

كل module causal يجب اختباره ضد:

```text
truncation
future mutation
future append
A→A
A→B→A
fresh instance
input immutability
```

للـsecondary tables والـledgers اختبارات exact مستقلة؛ لا يكفي تدقيق primary DataFrame.

---

# 5. الفصل بين LIVE وRESEARCH

## LIVE WORLD

```text
Layers 0–5
→ 6.1A Evidence
→ 6.1B Narrative/Hypotheses
```

لا يدخل إليه:

- outcomes؛
- future returns؛
- excursions؛
- maturity؛
- censoring؛
- labels؛
- test-period knowledge.

## RESEARCH WORLD

```text
6.2A-0 Visibility Firewall
→ 6.2A-1 Factual Outcome Observer
→ 6.2A-2 Temporal Eligibility (design only حالياً)
```

المستقبل مسموح فقط بعد تجميد historical decision snapshot.

قاعدة imports:

```text
research MAY import decision static/public contracts
decision MUST NOT import research
Layers 0–5 MUST NOT import research
```

---

# 6. عقود المعلومات الزمنية

المقارنة لا تعتمد على timestamp وحده.

`InformationKey` يتضمن:

```text
information_key_version
timeline_id
bar_position
event_time_utc
information_phase
deterministic_sequence
```

القواعد:

- cross-timeline ordering ممنوع.
- positional data لا تحصل على timestamp مصطنع.
- time-indexed data تتطلب timezone-aware valid timestamps.
- UTC normalization صريح.
- duplicate/nonmonotonic timestamp behavior يطابق closed contract.
- same-row analytical facts atomic.

`6.1B serialization_order`:

```text
bookkeeping only
NOT intrabar chronology
```

`COMPLETED_ROW_AVAILABLE` sequencing:

```text
logical causal dependency serialization
NOT measured exchange/feed/runtime micro-latency
```

---

# 7. قواعد schemas والقيم المفقودة

- لا silent defaults.
- لا arbitrary magic thresholds.
- لا auto mode inference.
- caller يحدد mode/config صراحة.
- `NaN`/`pd.NA`/unknown/unavailable تبقى ظاهرة.
- لا تحويل unknown إلى zero.
- لا list/dict cells في normalized tables.
- IDs/counts تستخدم nullable exact integers عند الحاجة.
- bool يبقى boolean وليس string أو 0/1.
- categories تبقى strings/categories.
- continuous numeric يبقى Float64 حسب العقد.
- counts فوق `2**53` لا تتحول إلى float.

---

# 8. قواعد الـhash والهوية

للـpersisted research identities:

- SHA-256 فقط.
- لا Python built-in `hash()`.
- domain separation.
- canonical serialization version.
- stable row/column order.
- dtype-aware identity.
- exact integers.
- exact finite float representation.
- explicit missing marker.
- UTC-normalized timestamps.

يجب الفصل بين:

```text
decision-time identity
research-as-of identity
mature factual identity
```

ممنوع إدخال future terminal أو outcome داخل decision snapshot hash.

---

# 9. الاختبارات الإلزامية

## 9.1 Schema

- missing columns.
- duplicate columns.
- wrong dtypes.
- duplicate IDs.
- orphan children.
- invalid positions.
- negative metadata.
- index mismatch.
- empty input.

## 9.2 Causality

- exact truncation.
- future mutation.
- future append.
- full-vs-truncated equivalence.
- no future payload access.
- exact phase boundaries.

## 9.3 State

- same instance repeated.
- A→B→A.
- fresh instance.
- no learned cache.

## 9.4 Numerical

- `NaN`/nullable handling.
- overflow/infinity rejection.
- integers above `2**53`.
- `+0.0` versus `-0.0` where representation identity matters.

## 9.5 Time

- positional index.
- timezone-aware index.
- UTC conversion.
- DST transition.
- irregular timestamps.
- duplicate/nonmonotonic rejection حسب العقد.

## 9.6 Firewall

- decision imports no research.
- forged visible bundles reject.
- outcomes never re-enter live evidence.

---

# 10. Same-row rules

حقائق الصف نفسه تشترك في information batch واحد.

ممنوع تفسير ترتيب loop أو serialization على أنه:

- market sequence؛
- intrabar order؛
- favorable-before-adverse؛
- target-before-stop؛
- one relationship known before another same-row relationship.

إذا OHLC bar يحمل favorable وadverse extremes معاً:

```text
SAME_BAR_ORDER_UNKNOWN
```

---

# 11. اللغة والادعاءات المحظورة

قبل وجود trade contract كامل، ممنوع:

```text
WIN / LOSS
profitable / unprofitable
PnL
entry
fill
stop
 target
trade result
```

مسموح فقط factual neutral terms مثل:

```text
research_reference_price
direction_favorable_excursion
direction_adverse_excursion
CONTRADICTED
SUPERSEDED
OBSERVED_DIRECTION_ESTABLISHED
RIGHT_CENSORED_AS_OF_BOUNDARY
```

Reference close:

```text
RESEARCH_REFERENCE_MARK
reference_is_execution_price = False
```

---

# 12. Domain / ICT source discipline

عند إضافة named concept:

1. original creator/primary source.
2. official documentation.
3. peer-reviewed/recognized standards.
4. secondary sources فقط cross-check.

ممنوع source laundering من SEO/blog repetition.

D1/D1.1 boundary:

```text
BOS_* = project continuation-direction structural break labels
CHOCH_* = project opposite-direction shift-candidate labels
```

لا يتم الادعاء أنها literal canonical Huddleston terminology.

Source fidelity لا يثبت predictive truth.

---

# 13. قواعد الـresearch outcomes

- outcome observer يستهلك فقط sealed `VisibleAsOfBundle`.
- لا full unrestricted history API.
- terminal authority من closed 6.1B ledger فقط.
- لا second structure state machine.
- creation bar high/low مستبعدان من post-hypothesis path.
- reference close ليس execution.
- censored ليس failure أو zero.
- mature factual ID فقط بعد maturity.
- B1 censored لا يُعدل عند B2 maturity.
- append-only research snapshots.

---

# 14. قواعد التدريب المستقبلية

قبل أي تدريب يجب أن يمر record عبر temporal eligibility gate:

```text
snapshot_information_key < T
outcome_mature == True
right_censored == False
factual_outcome_id nonmissing
final_outcome_known <= T
terminal_information_key <= T
```

لا يكفي أن يكون hypothesis created قبل `T`.

ممنوع:

- random KFold.
- shuffled split.
- full-dataset scaling.
- full-dataset feature selection.
- test-fold calibration.
- immature labels.

التدريب Walk-forward فقط بعد إغلاق 6.2A-2.

---

# 15. الديون البحثية

تبقى الديون ظاهرة ولا تُعلن محلولة ضمنياً.

الحالية:

```text
RESEARCH-DEBT-020 — Hypothesis Lifecycle Termination
RESEARCH-DEBT-021 — Evidence-Bearing Calibration
RESEARCH-DEBT-022 — Entity-Level Narrative Provenance
RESEARCH-DEBT-023 — Censoring / Competing-Risk Estimand
RESEARCH-DEBT-025 — Reference Price / Market-Time Alignment
```

`RESEARCH-DEBT-024` موجود ومفتوح كحد صريح لمشكلة overlapping hypotheses وnon-IID samples؛ لا يُعتبر محلولاً دون task مستقل.

---

# 16. طريقة العمل العملية في هذه المحادثة

## المرحلة 1 — Task block

المستخدم يرسل block واضح:

```text
DESIGN ONLY
BUILD ONLY
PATCH ONLY
READ-ONLY AUDIT
CLOSE MODULE
```

مع:

- module/version؛
- allowed files؛
- forbidden scope؛
- baseline؛
- required tests؛
- final status.

## المرحلة 2 — Preflight

الـAI يفحص:

- authoritative working tree؛
- current status؛
- hashes؛
- schemas/APIs المغلقة؛
- baseline tests؛
- affected files؛
- known debts.

إذا ambiguity جوهرية، يسأل قبل البناء.

## المرحلة 3 — تنفيذ محدود

- يعدل فقط الملفات المسموحة.
- لا يبدأ module تالٍ.
- لا يعمل cleanup خارج scope.
- يحافظ على hashes المغلقة.

## المرحلة 4 — اختبار طبقي

الترتيب:

```text
syntax/compile
focused unit tests
adversarial tests
causal/state selections
full pytest --collect-only
full pytest
```

## المرحلة 5 — تقرير Builder

يجب أن يحتوي:

- files changed؛
- behavior/contracts؛
- test counts؛
- hashes؛
- closed-module proof؛
- limitations؛
- debts؛
- exact pending status.

## المرحلة 6 — Handoff إلى AI مستقل

يُرسل له:

- module/version/status؛
- paths؛
- hashes؛
- baseline؛
- full code أو review material؛
- known issues؛
- explicit read-only instructions.

## المرحلة 7 — Audit findings

إذا وجد عيب:

```text
PATCH REQUIRED
```

لا إصلاح أثناء التدقيق.

## المرحلة 8 — Versioned patch

المستخدم يصرح:

```text
PATCH ONLY Vx -> Vy
```

ثم نعيد الاختبارات والتدقيق.

## المرحلة 9 — Closure

بعد:

```text
ACCEPTED FOR CLOSURE
```

يتم:

- تحديث docs/status؛
- حفظ patch history؛
- توثيق what closure certifies/does not certify؛
- إثبات src/tests unchanged؛
- regenerate manifest؛
- verify manifest؛
- إعلان CLOSED.

## المرحلة 10 — Milestone ZIP

عند الطلب:

- ZIP من manifest + manifest نفسه؛
- clean extraction؛
- manifest check؛
- collect/full pytest من extracted copy؛
- SHA-256 للـZIP؛
- cleanup للـtemporary extract.

---

# 17. بروتوكول تبادل العمل بين AIين

## Builder → Auditor handoff

```text
MODULE:
VERSION:
STATUS: IMPLEMENTED — PENDING AUDIT
WORKTREE:
FILES CHANGED:
EXPECTED HASHES:
DEDICATED TESTS:
FULL TESTS:
KNOWN LIMITATIONS:
OPEN DEBTS:
FORBIDDEN NEXT STEPS:
```

## Auditor → Builder/User

```text
HASH CHECK:
CODE FINDINGS:
CAUSAL FINDINGS:
SCHEMA FINDINGS:
TEST COVERAGE GAPS:
DECISION:
    ACCEPTED FOR CLOSURE
or
    PATCH REQUIRED
```

## قواعد handoff

- لا يعتمد Auditor على summary وحده.
- hashes تُراجع قبل التحليل.
- current code هو authority.
- أي mismatch يوقف الاعتماد.
- لا AI يفترض أن الآخر شغّل tests دون output موثق.
- لا يتم تمرير hidden assumptions بين المحادثات.

---

# 18. أوامر التحقق القياسية

```bash
sha256sum path/to/file
pytest --collect-only -q
pytest -q
sha256sum -c MANIFEST.sha256
```

إثبات عدم تغيير src/tests:

```bash
find src tests -type f ! -path '*/__pycache__/*' -print0 \
  | sort -z \
  | xargs -0 sha256sum > before.sha256

# documentation-only changes

find src tests -type f ! -path '*/__pycache__/*' -print0 \
  | sort -z \
  | xargs -0 sha256sum > after.sha256

cmp before.sha256 after.sha256
```

Manifest policy:

- يستثني نفسه.
- يستثني `.git` وcaches وgenerated artifacts.
- يرتب paths قبل hashing.

---

# 19. صيغة التقرير النهائي الإلزامية

كل build/patch report يجب أن ينتهي بـ:

```text
Module X Vy
IMPLEMENTED — PENDING AUDIT
```

كل closure report يجب أن ينتهي بـ:

```text
Module X Vy
CLOSED

Certified baseline:
N collected
N passed
```

كل design يجب أن ينتهي بـ:

```text
Module X
DESIGN PROPOSAL — NOT IMPLEMENTED
```

---

# 20. الحالة الحالية للمشروع — Milestone 6.2A-4 V1 Stage 1

```text
Layers 0–5                               CLOSED
Module 6.1A V1.3                         CLOSED
Module 6.1B V1.2                         CLOSED
Module 6.2A-0 V1.2                       CLOSED
Module 6.2A-1 V1.2                       CLOSED
Module 6.2A-2 V1                        CLOSED
Module 6.2A-3 V1.1                       CLOSED
Module 6.2A-4 V1 Stage 1                 CLOSED
Module 6.2B-0 V1.2                       CLOSED
Module 6.2B-1 V1.1                       CLOSED
6.2A-4 Stage 2+ domain trajectory        NOT STARTED
6.2B-2 / geometry / execution            NOT STARTED
model / scorer / signals                 NOT STARTED
QualificationObjective                   NOT DEFINED (RESEARCH-DEBT-020)
```

Certified baseline:

```text
701 collected
701 passed
```

Current authoritative archive and digest are recorded in `PROJECT_HANDOFF_MAP.md` and the release report generated with the archive.

Current 6.2B-0 boundary:

```text
no predictive SUPPORT mapping
no statistical-independence certification
no score / weights / probability
no geometry / execution / signal
all current records included_for_independent_calibration = False
```

Current 6.2B-1 boundary (TRAIN-only descriptive calibration):

```text
authoritative CLOSED source-fold verification and canonical TRAIN sample binding
authoritative B-0 re-analysis/membership; exact TRAIN raw feature binding
TEST/OOS descriptive-content firewall
descriptive empirical CDFs are NOT probabilities
observation coverage is NOT predictive SUPPORT
explicit baseline/ablation admission; chained experiment ledger (external trusted head)
caller-reported OOS accounting is NOT access-control proof
no predictive model / score / weights / objective / geometry / execution
DEPENDENCE_NOT_RESOLVED; RESEARCH-DEBT-020/021/023/024 open
```

Current 6.2A-4 Stage 1 boundary (causal future-trajectory foundation):

```text
shared authenticated MarketObservationTimeline; no per-hypothesis market duplication
two clocks: DECISION vs OUTCOME OBSERVATION (event key may precede available-at key)
decision anchor has no future information and no feature preselection
creation bar excluded from post-hypothesis path
FACTUAL_EVENT vs STATE_OBSERVATION distinction
deterministic as-of projection; immutable prior snapshots
OHLC resolution limits; integrity seal is NOT issuer authentication
no domain trajectory ingestion, descriptors, estimands, model, geometry, or execution
RESEARCH-DEBT-020/023/024/025 remain open
```

---

# 21. القاعدة النهائية

```text
إذا لم يكن الشيء معروفاً عند information time t،
فهو لا يدخل قرار t.

إذا كان الشيء outcome من المستقبل،
يبقى في research world.

إذا لم يكن العقد معرفاً،
لا نخترع default.

إذا كانت الوحدة CLOSED،
لا نعدلها دون versioned authorization.

إذا نجحت الاختبارات،
هذا لا يعني الإغلاق.

إذا لم نستطع إثبات claim،
نصرّح بالحدود أو نتوقف.
```

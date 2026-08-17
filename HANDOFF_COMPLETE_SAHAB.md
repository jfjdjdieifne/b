# هاند أوف كامل — مشروع التداول الذكي — سحاب

تاريخ: 2026-08-17
آخر حالة موثقة: Stage 2 CLOSED (737 tests)، Stage 3 DESIGN PATCHED + BUILD src موجود (PENDING AUDIT)

---

## 1. كيف عم نشتغل؟ القواعد والدستور

### ترتيب السلطة (Authority Order)
```text
1. current working tree (الملفات الحالية)
2. MANIFEST.sha256 (بصمة الملفات المعتمدة)
3. CLOSED public contracts (الكود المغلق)
4. tests
5. docs/STATUS.md / FINAL_VALIDATION.md / releases
6. design / handoff documents
7. ملخصات محادثات سابقة (ليست authority)
```

### الأدوار
- **Product Owner / Closure Authority = سحاب (أنت):** تحدد scope، تصرح بالبناء، تقبل التدقيق، تعلن CLOSED
- **Builder AI (أنا حالياً):** ينفذ scope فقط، يكتب الاختبارات العدائية، يشغل validation، يسلم IMPLEMENTED — PENDING AUDIT، لا يغلق بنفسه
- **Independent Auditor AI:** يعمل read-only، يراجع hashes والكود الفعلي، لا يثق بتقرير Builder وحده، يقرر ACCEPTED FOR CLOSURE / PATCH REQUIRED / REJECTED
- **Closure Agent:** بعد قبول صريح، يغير docs/status/manifest فقط ويثبت src/tests ما اتغيرت

### دورة حياة أي module
```text
NOT STARTED → DESIGN PROPOSAL → IMPLEMENTED — PENDING AUDIT → PATCHED → ACCEPTED FOR CLOSURE → CLOSED
```
- نجاح الاختبارات لا يعني CLOSED
- تعديل CLOSED يحتاج PATCH ONLY مصرح versioned

### القاعدة العليا: السببية وعدم تسرب المستقبل
```text
output[i] may depend only on information available at or before i
```
ممنوع:
- `shift(-1)`، centered rolling، backfill من المستقبل، full-dataset fitted transforms داخل live
- future return/target/PnL في live evidence
- اختيار best entry أو hindsight level
- تحويل same-row serialization إلى intrabar chronology

كل module causal يجب اختباره ضد: truncation, future mutation, future append, A→A, A→B→A, fresh instance, input immutability

### الفصل LIVE vs RESEARCH
```text
LIVE WORLD: Layers 0–5 + 6.1A + 6.1B + 6.2B-0 (لا يدخل outcomes/labels/excursions)
RESEARCH WORLD: 6.2A-0 Visibility Firewall → 6.2A-1 Outcome Observer → 6.2A-2 Eligibility → 6.2A-3 Dataset → 6.2A-4 Trajectory
research MAY import decision static/public contracts
decision MUST NOT import research
```

### اللغة المحظورة قبل وجود trade contract
ممنوع: WIN/LOSS, profitable, PnL, entry, fill, stop, target, trade result
مسموح: research_reference_price, favorable/adverse excursion, CONTRADICTED, SUPERSEDED, OBSERVED_DIRECTION_ESTABLISHED, RIGHT_CENSORED_AS_OF_BOUNDARY

---

## 2. وين وصلنا؟ الحالة الرسمية

### Baseline الحالي الموثق بالزيب الأخير:
```text
MANIFEST: 154 entries, all OK
SHA-256: 4b59adc48e83ee445831fa1f1f01a92bf0267af8a3f15731530eea6228955fd9
Tests: 737 collected / 737 passed (701 Stage1 + 36 Stage2)
```

| Layer | Module | Version | Status |
|---|---|---:|---|
| 0 | Causal & State Audit Framework | V3.1 | CLOSED |
| 0 | Causal Percentile Tracker | V1 | CLOSED |
| 0 | Causal Adaptive Smoothing | V1.1 | CLOSED |
| 1 | Dynamic Volatility Engine | V1.1 | CLOSED |
| 1 | Session Context | V1 | CLOSED |
| 2 | Swing Detector 2.1A | V1.1 | CLOSED |
| 2 | Swing Sequence 2.1B | V1 | CLOSED |
| 2 | Structural Break 2.1C | V1.1 | CLOSED |
| 2 | Liquidity Map 2.2 | V1.1 | CLOSED |
| 3 | Volume Delta 3.1 | V1.1 | CLOSED |
| 3 | Absorption 3.2 | V1.1 | CLOSED |
| 4 | Order Blocks 4.1 | V1.1 | CLOSED |
| 4 | FVG 4.2A | V1.1 | CLOSED |
| 4 | Dealing Range 4.2B | V1.1 | CLOSED |
| 5 | HTF Aggregator 5.1 | V1.1 | CLOSED |
| 5 | Confluence Matrix 5.2 | V1.1 | CLOSED |
| 6 | Evidence Vector 6.1A | V1.3 | CLOSED |
| 6 | Narrative Engine 6.1B | V1.2 | CLOSED |
| 6/Research | As-Of Firewall 6.2A-0 | V1.2 | CLOSED |
| 6/Research | Outcome Observer 6.2A-1 | V1.2 | CLOSED |
| 6/Research | Eligibility Gate 6.2A-2 | V1 | CLOSED |
| 6/Research | Dataset Builder 6.2A-3 | V1.1 | CLOSED |
| 6/Research | Trajectory Foundation Stage1 6.2A-4 | V1 | CLOSED |
| 6/Research | Trajectory Stage2 PRICE+STRUCTURE+LIFECYCLE | V1 | CLOSED (737) |
| 6/Research | Trajectory Stage3 Terminal/Censor | V1 | DESIGN PATCHED + src BUILD (PENDING AUDIT) |
| 6/Reasoning | Evidence-Family 6.2B-0 | V1.2 | CLOSED |
| 6/Reasoning | Adaptive Confluence 6.2B-1 | V1.1 | CLOSED |

### ما يثبته الإغلاق حتى الآن:

**Stage1 CLOSED:**
- shared authenticated MarketObservationTimeline (no per-hypothesis copy)
- two-clock: decision vs outcome observation
- DecisionAnchor لا يحوي future
- interval (decision, end] creation bar excluded
- FACTUAL_EVENT vs STATE_OBSERVATION
- deterministic as-of projection, immutable prior snapshots
- OHLC limits, integrity seal != issuer auth
- literal terminal semantics

**Stage2 CLOSED (36 tests dedicated):**
- PRICE: OHLCV raw + ref + direction + per-bar fav/adv + running max + extreme price/pos/key + new flags + close disp + bar offset + SAME_INFORMATION_BATCH_ORDER_UNKNOWN + strict > preserves first
- STRUCTURE: consumer of CLOSED 2.1A/B/C only, origin != confirmation, prefix causality (market_history truncated to interval end before chain), taxonomy only from CLOSED
- LIFECYCLE: consumer of CLOSED 6.1B ledger only, literal terminals only, mature ends at terminal boundary, no post-terminal rows, no price inference

**Stage3 (حالياً):**
- DESIGN PROPOSAL مصحح مرتين
- BUILD src موجود: `trajectory_stage3.py` (41K) — يطبق:
  - Terminal snapshot: factual availability separate from research as-of, origin preserved as Int64, not forged InformationKey
  - Censor snapshot: RIGHT_CENSORED_AS_OF فقط، research_snapshot_id present, factual_outcome_id NA
  - Compact binding: interval_id + Stage2 input binding (swing_policy_hash + lifecycle_ledger_seal + timeline/anchor/interval hashes + trajectory-prefix hash + envelope_count) — لا raw market، لا full envelope tuple
  - Authority: 6.2A-1 authoritative for terminal/censor classification, Stage2 authoritative for trajectory prefix
  - Storage: shared timeline once, snapshots compact O(K) rows, envelopes owned by Stage2 per-interval table, no quadratic growth, no delta-envelope optimization in V1
  - Two clocks preserved: terminal factual_available_at vs research_as_of may differ (T12 vs T15 reconstruction)

### الديون البحثية المفتوحة (RESEARCH-DEBT):

```text
020 — Hypothesis Lifecycle Termination Semantics (لا TTL)
021 — Evidence-Bearing Calibration
022 — Entity-Level Narrative Provenance
023 — Censoring / Competing-Risk Estimand (Stage3 يمثل factually فقط، لا يحدد hazard)
024 — Overlapping Hypothesis Dependence / Non-IID
025 — Reference-Price and Market-Time Alignment
```

ولا دين مسكر ضمنياً.

### الحدود غير المصدقة:

- predictive edge, profitability, confluence score, learned weights, calibration, qualification threshold, model/estimator/scorer, entry/stop/target, geometry policy, execution/fills/trade lifecycle, PnL/WIN/LOSS/signals, statistical independence, overlapping-hypothesis dependence — كلها NOT CERTIFIED

---

## 3. كيف تستغل معي؟ بروتوكول العمل

### نوع المهمة (Task Block) يجب أن ترسله بوضوح:

```text
DESIGN ONLY / BUILD ONLY / PATCH ONLY / READ-ONLY AUDIT / CLOSE MODULE
```

مع:
- module/version
- allowed files
- forbidden scope
- baseline
- required tests
- final status

### قبل البناء (Preflight):
أفحص:
- authoritative working tree
- current status, hashes, schemas المغلقة
- baseline tests
- affected files
- known debts

إذا ambiguity جوهرية، أسأل قبل البناء.

### أثناء البناء:
- أعدل فقط الملفات المسموحة
- لا أبدأ module تالٍ
- لا أعمل cleanup خارج scope
- أحافظ على hashes المغلقة

### الاختبار الطبقي:
```text
syntax/compile → focused unit → adversarial → causal/state selections → collect-only → full pytest
```

### تقرير Builder يجب أن يحوي:
- files changed
- behavior/contracts
- test counts
- hashes
- closed-module proof
- limitations
- debts
- exact pending status

### Handoff لـ AI مستقل:
أرسل له:
- module/version/status
- paths, hashes, baseline
- full code أو review material
- known issues
- explicit read-only instructions

### أوامر التحقق القياسية:
```bash
sha256sum -c MANIFEST.sha256
pytest --collect-only -q
pytest -q
sha256sum src/.../new_file.py
```

---

## 4. الملفات المرجعية السريعة

```text
PROJECT_HANDOFF_MAP.md — خريطة كاملة
README.md — نظرة عامة
MANIFEST.sha256 — بصمة الملفات المعتمدة
docs/STATUS.md — lifecycle الرسمي
docs/ARCHITECTURE.md — dependencies وحدود
docs/FINAL_VALIDATION.md — baseline المعتمد
docs/ENGINEERING_CONSTITUTION.md — قواعد هندسية
docs/handoff/AI_COLLABORATION_CONSTITUTION_CURRENT.md — دستور العمل بين AIين
docs/BUILDER_REPORT_6_2A_4_V1_STAGE2.md — تقرير إغلاق Stage2
docs/HANDOFF_COMPLETE_SAHAB.md — هذا الملف
src/trading_system/research/trajectory/trajectory_stage2.py — Stage2 CLOSED
src/trading_system/research/trajectory/trajectory_stage3.py — Stage3 BUILD (PENDING AUDIT)
tests/test_trajectory_stage2.py — 36 tests Stage2
docs/releases/MODULE_6_2A_4_V1_STAGE2_ACCEPTED_SRC_TESTS.sha256 — بصمة Stage2 المقبولة
docs/releases/MILESTONE_6_2A_4_V1_STAGE2_CLOSED.md — إعلان إغلاق Stage2
```

---

## 5. ما التالي؟

- Stage3 حالياً: DESIGN PATCHED + src BUILD موجود، لكن tests لم تكتمل كلياً بسبب توقف التاسك حسب طلبك. الـ src يطبق كل التصحيحات المطلوبة:
  - origin preserved as Int64, not forged key
  - empty ledger uses same canonical schema (zero-row DataFrame)
  - Stage2 artifact hash كـ provenance فقط، ليس sole identity
  - compact binding بدون full envelope tuple
  - no invented censor taxonomy
  - terminal factual availability vs research as-of distinct

- للمتابعة، نحتاج:
  - إكمال `tests/test_trajectory_stage3.py` بكل الحالات العدائية المطلوبة (القائمة في BUILD ONLY)
  - تشغيل `pytest --collect-only -q` و `pytest -q`
  - تحديث Builder Report لـ Stage3
  - Independent Audit READ-ONLY ثم CLOSE

- لن نبدأ Stage4 (descriptors/estimands/model) ولا geometry/execution إلا بتصريح صريح.

---

## 6. الخلاصة الفلسفية

المشروع ليس استراتيجية checkbox. قوته في:
- السببية، information-time discipline، explicit epistemic states
- provenance/derivation separation
- التدقيق القابل لإعادة الإنتاج بالـ hashes

أي خطوة لاحقة يجب أن تبني فوق هذه الحدود دون اختراع edge أو استقلال أو chronology غير مثبتة.

```text
إذا لم يكن الشيء معروفاً عند information time t، فهو لا يدخل قرار t.
إذا كان الشيء outcome من المستقبل، يبقى في research world.
إذا لم يكن العقد معرفاً، لا نخترع default.
إذا كانت الوحدة CLOSED، لا نعدلها دون versioned authorization.
إذا نجحت الاختبارات، هذا لا يعني الإغلاق.
إذا لم نستطع إثبات claim، نصرّح بالحدود أو نتوقف.
```

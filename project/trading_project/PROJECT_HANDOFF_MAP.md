# خريطة تسليم المشروع — Trading Intelligence Project

## 1. اقرأ هذا أولاً

هذه الوثيقة هي handoff map الكاملة لأي Builder AI أو Independent Auditor AI أو مطوّر يستلم المشروع دون سياق المحادثات السابقة.

```text
Authoritative project root: trading_project_final/
Current milestone: Module 6.2A-4 V1 Stage 1 CLOSED
Certified baseline: 701 collected / 701 passed
Next module: NOT AUTHORIZED / NOT STARTED
```

الـauthority الفعلي بالترتيب:

1. current files داخل المشروع؛
2. `MANIFEST.sha256`؛
3. CLOSED public contracts؛
4. tests؛
5. `docs/STATUS.md` و`docs/FINAL_VALIDATION.md`؛
6. هذه الخريطة؛
7. تقارير Builder القديمة ليست authority إذا خالفت current code/hash.

## 2. فلسفة المشروع

نحن لا نبني checkbox strategy ولا نفرض ICT/SMC pattern محفوظاً على السوق.

```text
وجود OB/FVG/liquidity interaction لا يعني support.
alignment لا يعني profitability.
غياب support لا يعني opposition.
missing evidence لا يعني bearish evidence.
context لا يعني predictive support.
source count لا يعني confluence strength.
correlation لا يعني confirmations مستقلة.
```

السوق قد retrace أو يكمل دون retracement أو يدور أو يبطل hypothesis أو يغيّر structure. النظام يصف ما هو معلوم عند information time، ولا يخترع ما ليس معلوماً.

## 3. الأدوار بين المستخدم والـAIين

### المستخدم — Product Owner / Closure Authority

يحدد scope، يصرح بالـbuild/patch، يقبل التدقيق، ويصرح بالانتقال أو تعديل CLOSED module.

### Builder AI

ينفذ scope فقط، يكتب الاختبارات، يشغّل validation، ويسلم `IMPLEMENTED — PENDING AUDIT`. لا يغلق module بنفسه.

### Independent Auditor AI

يعمل read-only، يراجع hashes والكود الفعلي، ولا يثق بتقرير Builder وحده. قراره واحد من:

```text
ACCEPTED FOR CLOSURE
PATCH REQUIRED
REJECTED / DESIGN REQUIRED
```

### Closure/Release Agent

بعد القبول يغير docs/status/manifest/package فقط ويثبت أن `src/` و`tests/` لم تتغير.

الدستور الكامل:

```text
docs/handoff/AI_COLLABORATION_CONSTITUTION_CURRENT.md
docs/ENGINEERING_CONSTITUTION.md
```

## 4. دورة حياة أي module

```text
NOT STARTED
→ DESIGN PROPOSAL — NOT IMPLEMENTED
→ IMPLEMENTED — PENDING AUDIT
→ PATCHED / IMPLEMENTED — PENDING AUDIT
→ ACCEPTED FOR CLOSURE
→ CLOSED
```

نجاح tests وحده لا يغلق module. تعديل CLOSED module يحتاج versioned `PATCH ONLY` صريح.

## 5. الحالة الحالية

```text
Layers 0–5                                           CLOSED
6.1A Causal Evidence Vector V1.3                     CLOSED
6.1B Causal Market Narrative V1.2                    CLOSED
6.2A-0 Information-Time / As-Of Firewall V1.2       CLOSED
6.2A-1 Factual Outcome Observer V1.2                 CLOSED
6.2A-2 Temporal Eligibility Gate V1                  CLOSED
6.2A-3 Research Dataset / Walk-Forward V1.1         CLOSED
6.2A-4 Future Trajectory Foundation Stage 1 V1       CLOSED
6.2B-0 Dynamic Evidence-Family Reasoning V1.2       CLOSED
6.2B-1 Walk-Forward Adaptive Confluence Calibration  CLOSED V1.1

6.2B-2                                               NOT AUTHORIZED / NOT STARTED
6.2C geometry                                        NOT STARTED
6.2D execution                                       NOT STARTED
model / scorer / signals                             NOT STARTED
QualificationObjective                               NOT DEFINED (RESEARCH-DEBT-020)
```

التفاصيل الرسمية في `docs/STATUS.md`.

## 6. مسار البيانات الحالي

```text
Market data
→ Layers 0–5 causal factual engines
→ 6.1A certified evidence vector
→ 6.1B descriptive narrative/hypotheses

Research branch:
6.1A/6.1B
→ 6.2A-0 as-of visibility
→ 6.2A-1 factual outcomes
→ 6.2A-2 temporal eligibility
→ 6.2A-3 raw causal dataset/walk-forward

Reasoning branch:
Frozen hypothesis-creation snapshot
→ 6.2B-0 evidence-family semantics/provenance/lineage
→ 6.2B-1 TRAIN-only descriptive calibration/reference foundation (no predictive model)
```

6.2B-1 is TRAIN-only descriptive calibration. It binds CLOSED 6.2A-3 source
provenance and B-0 reasoning membership, but produces no score, weights,
probability, qualification, geometry, or execution path. لا يوجد scorer أو
model أو execution path بعد.

## 7. عقد Module 6.2B-0 V1.2

Public API:

```text
ReasoningDecisionSnapshot
DynamicEvidenceFamilyReasoner().analyze(snapshot)
EvidenceFamilyReasoningResult
reasoning_contract_manifest()
reasoning_record_hash_payload()
resolve_provenance_status()
```

V1.2 يدعم exact hypothesis-creation row فقط:

```text
InformationPhase.COMPLETED_ROW_AVAILABLE
deterministic_sequence = 1
all admitted observation/relationship/lifecycle positions = decision row
```

Outputs:

```text
family_snapshots
evidence_records
evidence_sources
lineage_edges
availability_signature
reasoning_ledger
provenance_relations
reasoning_manifest
```

### Semantic boundary

```text
SUPPORT
OPPOSITION
CONTRADICTION
NEUTRAL
UNKNOWN
UNAVAILABLE
FACTUAL
CONTEXTUAL
QUALIFYING
ALIGNED
CONFLICT
MIXED
```

لا يوجد current mapping إلى predictive `SUPPORT`.

### Open-world provenance

```text
CERTIFIED_SHARED_PROVENANCE
CERTIFIED_DISTINCT_PROVENANCE
NOT_CERTIFIED
```

عدم إثبات shared لا يثبت distinct، والعكس صحيح.

### Derivation منفصلة عن provenance

```text
DETERMINISTIC_DERIVATIVE
NOT_DETERMINISTICALLY_DERIVED
NOT_CERTIFIED
```

Co-derived siblings لا تصبح parent/child لمجرد shared hidden input.

### Independence boundary

```text
included_for_independent_calibration = False
```

لكل current record. Provenance normalization لا تثبت statistical independence أو incremental predictive information.

### Hash layers

```text
decision_snapshot_hash   = exact upstream storage integrity binding
record_hash              = final semantic record hash
family snapshot_hash     = canonical family semantic content
semantic_reasoning_hash  = order-invariant whole reasoning identity
```

Unkeyed SHA-256 ليس trusted-origin authentication.

## 8. أهم causal rules

لكل decision `i`:

```text
output[i] may depend only on information available at or before i
```

ممنوع:

- `shift(-1)`؛
- centered rolling؛
- future backfill؛
- future lifecycle/outcome؛
- full-dataset fitted transform داخل live decision modules؛
- timestamp-only ordering؛
- تحويل same-row serialization إلى intrabar chronology.

كل module causal يحتاج truncation/future mutation/future append/A→A/A→B→A/fresh-instance/input-immutability tests.

## 9. LIVE مقابل RESEARCH

```text
Layers 0–5 + 6.1A + 6.1B + 6.2B-0 reasoning semantics
```

لا تستورد outcomes أو labels أو excursions أو maturity أو model artifacts.

Research يستطيع استهلاك immutable/public decision contracts، لكن decision وLayers 0–5 لا تستورد `trading_system.research`.

## 10. ما لا يجوز بناؤه دون تصريح لاحق

```text
confluence score
learned weights
calibration
qualification threshold
probability
model / estimator / scorer
entry / stop / target
geometry policy
execution / fill / trade lifecycle
BUY / SELL signal
PnL / WIN / LOSS
```

لا تبدأ 6.2B-1 لأن الاسم يبدو خطوة تالية؛ تحتاج task block صريح.

## 11. الديون المفتوحة

```text
RESEARCH-DEBT-020 — Hypothesis Lifecycle Termination Semantics
RESEARCH-DEBT-021 — Evidence-Bearing Calibration
RESEARCH-DEBT-022 — Entity-Level Narrative Provenance Contract
RESEARCH-DEBT-023 — Outcome Censoring and Competing-Risk Estimand
RESEARCH-DEBT-024 — Overlapping Hypothesis Dependence / Non-IID Samples
RESEARCH-DEBT-025 — Reference-Price and Market-Time Alignment
```

لا تعتبرها محلولة ضمنياً.

## 12. حدود geometry/public contracts المعروفة

- swings expose prices and origin/confirmation positions، لكن لا universal `pivot_id`؛
- liquidity exposes `level_id` وevent lifecycle، لا resting-order certification؛
- OB/FVG are operational candidates، لا institutional proof أو mandatory fill؛
- dealing range exposes current range geometry، لا universal terminal lifecycle؛
- لا يوجد point-in-time tick-size/instrument-spec contract؛
- entity reasoning لاحقاً يحتاج causal adapter جديد، لا private internals ولا patch صامت للوحدات المغلقة.

## 13. حدود source terminology

```text
BOS_UP/BOS_DOWN
```

هي project continuation-direction break labels.

```text
CHOCH_UP/CHOCH_DOWN
```

هي project opposite-direction shift-candidate labels.

لا ندعي literal canonical ICT/Huddleston fidelity. Consequent Encroachment وMean Threshold وDraw on Liquidity لم يكتمل لها concept-specific primary-source audit.

## 14. Known identity boundary

Module 6.2A-3:

```text
module release = V1.1
dataset contract = CAUSAL_RESEARCH_DATASET_V1
```

هذا mismatch محفوظ ومعلن. لا يُعدل دون versioned patch مصرح.

## 15. أوامر التحقق

```bash
python -m pip install -e ".[dev]"
pytest --collect-only -q
pytest -q
sha256sum -c MANIFEST.sha256
```

الخط الأساس المعتمد:

```text
701 collected
701 passed
current manifest is authoritative
```

## 16. أين تقرأ التفاصيل

```text
README.md                                  overview
PROJECT_HANDOFF_MAP.md                     complete handoff
MANIFEST.sha256                            authoritative file digests
docs/STATUS.md                             official lifecycle state
docs/ARCHITECTURE.md                       dependencies and boundaries
docs/FINAL_VALIDATION.md                   exact certified baseline
docs/ENGINEERING_CONSTITUTION.md           engineering rules
docs/handoff/AI_COLLABORATION_CONSTITUTION_CURRENT.md multi-AI workflow
docs/module_6_2b_0_v1_audit_report.md      6.2B-0 reasoning contract/audit history
docs/module_6_2b_1_v1_audit_report.md      6.2B-1 V1.1 builder/patch report
docs/module_6_2b_1_v1_1_INDEPENDENT_AUDIT.md  6.2B-1 independent final audit (ACCEPTED)
docs/releases/MILESTONE_6_2B_1_V1_1_CLOSED.md  latest closure release note
docs/technical_debt/                       open debts
docs/domain_audit/                         source terminology audit
```

## 17. كيف تسلم المهمة لموديل جديد

أرسل له:

```text
WORKTREE: extracted project root
READ FIRST: PROJECT_HANDOFF_MAP.md
VERIFY: sha256sum -c MANIFEST.sha256
STATUS: docs/STATUS.md
BASELINE: docs/FINAL_VALIDATION.md
RULES: docs/handoff/AI_COLLABORATION_CONSTITUTION_CURRENT.md
DO NOT MODIFY CLOSED MODULES WITHOUT VERSIONED PATCH
DO NOT START NEXT MODULE WITHOUT EXPLICIT AUTHORIZATION
```

ثم أعطه task block واضح: `DESIGN ONLY` أو `BUILD ONLY` أو `PATCH ONLY` أو `READ-ONLY AUDIT`.

## 18. الخلاصة

المشروع الحالي reasoning/research infrastructure وليس trading strategy جاهزة. قوته في السببية، information-time discipline، explicit epistemic states، provenance/derivation separation، والتدقيق القابل لإعادة الإنتاج. أي خطوة لاحقة يجب أن تبني فوق هذه الحدود دون اختراع edge أو استقلال أو chronology غير مثبتة.

# MUF-V1-FINAL-DESIGN-PATCH-D2
## IDENTITY BASIS · SELECTION PIPELINE · FINAL-EVALUATION PROTOCOL · ARTIFACT CLOSURE

**الحالة**: DESIGN ONLY — BUILD NOT AUTHORIZED — آخر internal design patch (بعده DESIGN AUDIT مستقل — لا D3 تلقائياً).
**الإصدار**: MUF-V1-FINAL-DESIGN-PATCH-D2 — 2026-09-29
**المرجعية**: الأعلى = D1 (`38`) ← FINAL DESIGN (`37`) ← MASTER DESIGN (`36`).
**Precedence**: حيث يتعارض D2 مع D1/37/36 — **D2 هو الأعلى**؛ غير المصحَّح هنا يبقى سارياً.
**الممنوعات الثابتة**: لا كود | لا src/tests | لا MANIFEST | لا CLOSED | لا اختيار quantile/threshold/window/horizon | لا اختيار α/β/γ/δ | لا تعريف QualificationObjective | لا فتح/تحليل OOS/final | لا Reality analysis | لا model/strategy/PnL/توصية | لا اختراع metric. أي حاجة لرقم أو قرار غير مُفوَّض ⇒ **NOT_CONFIGURED / OWNER DECISION REQUIRED**.

---

# PART 0 — التمهيد

## 0.1 البنود المصحَّحة من D1 (وأين)

| # | بند D1 المصحَّح | تصحيح D2 |
|---|---|---|
| 1 | D1-5: `policy_hash?` اختياري + هوية من origin وحده | D2-1: `WaveProcessIdentityBasis` كامل إلزامي — لا optional authority |
| 2 | D1-5/2: لا سلطة صريحة لإنشاء WaveIdentityRecord | D2-2: `identity_basis_refs` + `identity_rule_ref` إلزاميان |
| 3 | D1-1 + D1-21: تناقض INFORMATION_OBJECTIVE→Estimand مقابل ترتيب selection قبل Estimand | D2-3 + D2-17: فصل STRUCTURAL QUALIFICATION عن INFORMATION-BASED SELECTION بوابتين |
| 4 | D1-21: «fit→selection→freeze→final→estimand لاحقاً» | D2-4: مسار بحث كامل يستوفي الاعتماديات |
| 5 | D1-20/2: «FINAL once» بلا وحدة | D2-5: `EvaluationProtocolArtifact` — الوحدة = protocol + lineage |
| 6 | D1-2/21: خلط final lock بفتح final | D2-6: `FINAL_DATA_RESERVED` ≠ `FINAL_EVALUATION_OPENED` |
| 7 | D1-2: `dataset_identity` كلمة غير كافية | D2-7: `DatasetIdentityArtifact` + ExposureAncestry |
| 8 | D1-13: closure يفترض graph DAG | D2-8: closure validator cycle-safe deterministic |
| 9 | D1-8/9: `ALTERNATES_WITH` مستعملة للتعاقب | D2-9: فصل ADJACENT_TO / ALTERNATES_WITH / … |
| 10 | D1 schemas: `available_at` كسلطة | D2-10: InformationKey في كل مكان (schema audit) |
| 11 | D1-12: batch equality قد تشمل deterministic_sequence | D2-11: `InformationBatchKey` يستبعده صراحة |
| 12 | هوية artifacts موزعة بلا عقد موحد | D2-12: `CanonicalArtifactIdentity` |
| 13 | D1-20: artifact-equivalence أوسع من اللازم | D2-13: `EquivalenceClaimArtifact` مقيدة بالـclaim |
| 14 | D1-18: comparability ثنائية | D2-14: ثلاث مستويات + CompatibilityArtifact |
| 15 | D1-21: «freeze exact artifact family» غير محددة ككيان | D2-15: `FrozenRepresentationBundle` |
| 16 | D1-10: namespace RUNNING لا يكفي للسببية | D2-16: `DescriptorSpec` بعقود إدخال/توفر |
| 17 | D1-21: بوابة واحدة | D2-17: GATE A / GATE B منفصلتان |
| 18 | D1-2: صياغة walk-forward | D2-18: firewall صريح — لا walk-forward ي consumes final |
| 19 | لا readiness قبل الفتح | D2-19: `PreFinalReadinessRecord` |
| 20 | D1-22: 24 هجوماً | D2-20 + Annex D: هجمات 25–50 |
| 21 | 0.3 في D1 | D2-21: قائمة الأسئلة المفتوحة صريحة |
| 22 | Annex B في D1 | D2-22 + Annex B: الترتيب النهائي S0–S15 + G0–G3 |
| 23 | Annex E في D1 | D2-23 + Annex E: حدود الشهادة موسَّعة |

## 0.2 OPEN BLOCKERS بعد D2
1. **QualificationObjective = UNDEFINED** — OWNER DECISION REQUIRED.
2. مصدر `PolicyArtifact` (TRAIN-only) غير محلول.
3. **FoldProtocolArtifact** العددي = NOT_CONFIGURED — OWNER DECISION REQUIRED.
4. δ merge/adjacency authority = NOT_CONFIGURED (I-DELTA-3/4).
5. RESEARCH-DEBT-020..025 (منها 024) OPEN.
6. External context NOT_CONFIGURED؛ Dominance لا يُستنتج من BTCUSDT.
7. CompatibilityArtifact = NOT IMPLEMENTED.
8. بيانات المالك للتشغيل الحقيقي (جهازه فقط).

## 0.3 UNDEFINED عمداً (D2-21 — لا يجيب عنها أحد هنا)
QualificationObjective = UNDEFINED | actual calibration parameters = NOT_CONFIGURED | α/β/γ/δ winner = UNDEFINED | δ merge policy = NOT_CONFIGURED unless independently authorized | FoldProtocol numerical boundaries = NOT_CONFIGURED | Estimands = NOT YET DEFINED | InformationObjective = NOT_CONFIGURED until Estimand exists | CompatibilityArtifact = NOT IMPLEMENTED | Model = OUT OF SCOPE | statistical dependence/independence = NOT PROVEN | profitability/edge = NOT PROVEN | external context = NOT_CONFIGURED unless independent source contract exists.

---

# PART I — البنود

## D2-1) WAVE PROCESS IDENTITY MUST BE KNOWLEDGE-SAFE

**التصحيح الحاسم**: `policy_hash?` الاختياري في D1-5 **محذوف**. والهوية لا تُبنى على origin bar وحده (لا يميز epistemic objects التي بلغت نفس extreme تحت سلطات مختلفة).

```
WaveProcessIdentityBasis {
    representation_spec_hash,
    authoritative_start_turning_point_id,
    authority_policy_hash,                     # إلزامي — لا optional
    timeline_id,
    intrinsic_representation_key_or_NOT_APPLICABLE,   # typed — لا null غامض
    identity_basis_refs[]
}
wave_process_id = canonical_domain_separated_hash(WaveProcessIdentityBasis)   # كامل الـbasis
```

**الحصون**:
- **I-WPI-1**: لا optional policy authority في هوية factual wave.
- **I-WPI-2**: لا end fact ولا final duration ولا future parent ولا future depth ولا future member يدخل identity.
- **I-WPI-3**: كل component في identity يجب أن يكون **visible عند `wave_identity_information_key`**.
- **I-WPI-4**: نفس origin السعري تحت PolicyArtifacts مختلفين **لا يُدمج تلقائياً** في نفس process identity.
- **I-WPI-5**: نفس geometry لاحقاً ≠ same epistemic identity.
- عائلة بلا intrinsic scale ⇒ `NOT_APPLICABLE` typed صراحة.

## D2-2) WAVE IDENTITY NEEDS AN EXPLICIT FACTUAL BASIS

`WaveIdentityRecord` يحمل إلزامياً:
```
identity_basis_refs[]        # مراجع فقط إلى facts قانونية visible في تلك اللحظة
identity_rule_ref            # عقد/PolicyArtifact/representation rule مُجمَّد:
                             # لماذا تكفي هذه الحقائق لإنشاء process identity
wave_identity_information_key
```
**ممنوع**: «engine decided it is a wave» — لا سلطة محرك بلا rule.

**الحصون**:
- **I-WIB-1**: لا legal identity_basis_refs ⇒ لا WaveIdentityRecord.
- **I-WIB-2**: identity rule غير مُهيأ ⇒ `NOT_CONFIGURED`.
- **I-WIB-3**: `wave_identity_information_key` لا يُقبل كـtimestamp اعتباطي — ينتج من **availability closure للـbasis + rule**.
- **I-WIB-4**: معرفة TP وحدها لا تمنح wave identity ما لم ينص rule صراحة.

**المثال الزمني المُعاد (يذكر المرجع/العقد المتاح عند كل لحظة — rule لا يُختار فعلياً الآن)**:
```
t=100  origin:            قاع عند bar 100 — لا مراجع قانونية بعد
t=112  TP known:          turning_point_records ينشأ (origin=100, available=112)
                          ↳ يصبح متاحاً: [ref: TP#100] — basis component واحد
t=118  wave process known: WaveIdentityRecord ينشأ — والـbasis المرجعي المكتمل عند 118:
                          identity_basis_refs = [TP#100, PolicyArtifact#P (authority),
                                                 representation_spec#R, timeline#T]
                          identity_rule_ref = <عقد مُجمَّد ينص أن TP مؤكَّد تحت P ضمن R
                                               يكفي لتأسيس process identity — RULE NOT
                                               SELECTED HERE (NOT_CONFIGURED حتى تفويض)>
                          wave_identity_information_key = key(118, COMPLETED_ROW_AVAILABLE)
                          wave_process_id = hash(Basis الكامل) — بلا أي end fact
t=125  running extension: RunningWaveDescriptorObservations (بلا تعديل للهوية)
t=130  end TP known:      TP#128 يُعرف عند 130 (مرجع جديد — لا علاقة بالهوية)
t=141  wave-end confirm:  wave_end_records + finalized_wave_geometry_ref + status FORMING→CONFIRMED
                          — الهوية القديمة كما هي (I-WID-1/2 سارية + I-WPI-2)
```
لو وُجد PolicyArtifact آخر P′ عند 118 ⇒ **wave_process_id مختلف** (I-WPI-4) — لا اندماج.

## D2-3) SPLIT STRUCTURAL QUALIFICATION FROM INFORMATION-BASED SELECTION

**إزالة تناقض D1 نهائياً بمرحلتين**:

**المرحلة A — STRUCTURAL QUALIFICATION** (تستخدم فقط): causal validity | contract validity | non-degeneracy diagnostics **مُعرَّفة مسبقاً** | computability/performance requirements | factual/reality diagnostics المسموحة على development data.
**لا تدعي**: predictive information | superiority according to future outcomes | edge.
**الناتج**: `ELIGIBLE / INELIGIBLE(reason)` — **وليس WINNER**.

**المرحلة B — INFORMATION-BASED DEVELOPMENT SELECTION** — لا تُفتح إلا بعد:
`Descriptor Registry → Dependence accounting contract → EstimandArtifact → InformationObjectiveArtifact → preregistered evaluation protocol → DEVELOPMENT_SELECTION evaluation` — فقط بعدها يجوز selection لأسباب information-based.

**الحصون**:
- **I-SEL-1**: Structural qualification لا تختار «الأكثر تنبؤاً».
- **I-SEL-2**: Information-based selection بلا preregistered Estimand = **BLOCKED**.
- **I-SEL-3**: Final evaluation لا تدخل selection أبداً.
- **I-SEL-4**: بلا Information Objective ⇒ فقط مجموعة `structurally eligible` تُحتفظ بها — **لا winner معلوماتي مخترع**.
- **I-SEL-5**: Visual preference ليست tie-breaker.

## D2-4) REPRESENTATION RESEARCH PIPELINE

الترتيب المعتمد (يُفصَّل في Annex B): Core contracts ↓ Witness layer ↓ Policy/Data-role/Experiment infrastructure ↓ Development policy fit where authorized ↓ Build candidate representations on DEVELOPMENT only ↓ **Structural Qualification** ↓ Eligible set ↓ Descriptor contracts ↓ Dependence accounting contracts ↓ Estimand preregistration ↓ InformationObjectiveArtifact ↓ DEVELOPMENT_INFORMATION_EVALUATION ↓ Information-based selection if authorized ↓ FREEZE exact bundle ↓ Reserve final evaluation data ↓ Build/verify complete frozen evaluation pipeline ↓ Open final evaluation under explicit protocol ↓ Record result once for that protocol/lineage.
**لا Model ضمن D2.** أي module لم يُبن بعد ⇒ **contract-only / NOT_CONFIGURED — ولا يُقفز فوقه**.

## D2-5) FINAL EVALUATION IS CLAIM/PROTOCOL SCOPED

«FINAL once» = مرة واحدة بالنسبة إلى **`EvaluationProtocolArtifact` المحدد + frozen bundle lineage المحدد**:
```
EvaluationProtocolArtifact {
  evaluation_protocol_id, protocol_hash,
  frozen_bundle_id, artifact_lineage_id,
  objective_artifact_hash, estimand_hashes[],
  dataset_identity, dataset_ancestry_root,
  allowed_outputs[], prohibited_outputs[],
  opening_authorization_ref,
  reservation_time, opened_at_or_null,
  exposure_log_root, schema_version
}
```
**الحصون**:
- **I-EVAL-1**: «مرة واحدة» مقيَّدة بـ(protocol, lineage).
- **I-EVAL-2**: فتح النتائج المحمية = **irreversible exposure event**.
- **I-EVAL-3**: لا تغيير objective/estimand/bundle بعد فتح protocol.
- **I-EVAL-4**: أي تغيير = protocol/lineage جديدة + فحص صلاحية dataset استقلالياً.
- **I-EVAL-5**: `allowed_outputs` تُحدد **قبل الفتح** — لا data-mining عبر طلب summaries جديدة بعد رؤية الأولى.
- **I-EVAL-6**: أي output غير preregistered بعد الفتح ⇒ يُسجَّل **exploratory فقط** ولا يدخل claim النهائي دون بروتوكول مستقل صالح.

## D2-6) RESERVE ≠ OPEN FINAL DATA

**الفصل**:
- **`FINAL_DATA_RESERVED`**: الهوية والدور معروفان؛ الوصول للمحتوى/outputs المحمية **ممنوع**؛ **لا exposure**.
- **`FINAL_EVALUATION_OPENED`**: بعد freeze واكتمال evaluation pipeline؛ بتفويض `opening_authorization_ref`؛ **irreversible exposure event**.

**الترتيب الإلزامي**: Freeze bundle ↓ Reserve final data ↓ verify complete frozen pipeline **without protected outputs** ↓ authorize open ↓ open/evaluate exactly according to protocol ↓ record.
- **I-RES-1**: reservation **ليست** exposure.
- **I-RES-2**: أي inspection قبل authorized open ⇒ يبطل UNEXPOSED status وفق DatasetRole contract.

## D2-7) DATASET IDENTITY + EXPOSURE ANCESTRY

```
DatasetIdentityArtifact {
  dataset_id,
  content_hash_or_manifest_root,
  source_identity, timeline_identity,
  transformation_spec_hash, parent_dataset_ids[],
  creation_code_hash, semantic_schema_hash,
  time_extent_contract, role_artifact_ref
}
```
**ExposureAncestry**: إذا Dataset B مشتق من A ⇒ exposure لمعلومات A يمكن أن يؤثر على صلاحية B بحسب المعلومات المشتركة.

**الحصون**:
- **I-DATA-1**: rename/reformat/re-hash **لا يصنع** dataset مستقلاً.
- **I-DATA-2**: مشتق من exposed final data **لا يصبح** fresh final data تلقائياً.
- **I-DATA-3**: ادعاء استقلال dataset يحتاج **ancestry check** — لا اختلاف dataset_id فقط.
- **I-DATA-4**: raw/facts/kline/joined timeline identities منفصلة **لكن ancestry معلنة**.
- **I-DATA-5**: partial overlap الزمني/المصدري يجب أن يكون **detectable ومعلناً**؛ لا افتراض استقلال عند overlap.
- **لا قاعدة إحصائية للاعتماد هنا** — provenance/exposure firewall فقط.

## D2-8) CYCLE-SSAFE SNAPSHOT CLOSURE

closure validator **deterministic cycle-safe**: visited identity set | كل reachable reference يُفحص مرة واحدة | stable canonical traversal | cycle discovery يُسجَّل حسب relation semantics | لا recursion غير محدودة. **لا تمنع كل graph cycles عشوائياً** — افصل:
- `ILLEGAL_WAVE_CONTAINMENT_CYCLE` (مرفوض — D1-7)، عن
- `GENERAL_REFERENCE_CYCLE` (يُفحص دون infinite recursion؛ وإذا relation type تمنعه ⇒ reject حسب type contract).

**الحصون**:
- **I-CLOS-1**: snapshot causal closure **لا يعتمد** على graph being globally DAG.
- **I-CLOS-2**: cycle **لا يسمح** بتجاوز availability validation.
- **I-CLOS-3**: نفس graph ⇒ نفس closure hash بغض النظر عن insertion order القانوني.

## D2-9) δ: ADJACENCY IS NOT ALTERNATIVES

**فصل العلاقات** (خطأ D1-8 مصحَّح):
- **`ADJACENT_TO`** — succession/neighbor حيث chronology قانونية الإثبات.
- **`ALTERNATES_WITH`** — **المتنافسون/البدائل** فقط (كما في TIE_ORDER_CONTRACT).
- **`CONTAINS`** — احتواء هرمي.
- **`GEOMETRICALLY_COINCIDENT` / `PARTIAL_OVERLAP`** — هندسة فقط.

**δ parent construction لا يجوز أن يستخدم ALTERNATES_WITH بمعنى adjacency.**

**الحصون**:
- **I-DELTA-1**: alternative ≠ adjacent.
- **I-DELTA-2**: adjacency chronology غير قابلة للإثبات (same information batch) ⇒ لا `ADJACENT_TO` موجَّهة مُختلَقة؛ typed unresolved relation أو `NOT_CONFIGURED` حسب العقد.
- **I-DELTA-3**: merge rule للحركات same-direction = **`NOT_CONFIGURED(NON_ALTERNATING_MERGE_RULE)`**.
- **I-DELTA-4**: **δ لا توصف BUILD-ready populated hierarchy** ما دام merge/adjacency authority المطلوبة غير موجودة — شهادتها التشغيلية: `EVENT_ANCHORED_CONTAINMENT_HIERARCHY — CONTRACT-ONLY/NOT_CONFIGURED (POPULATED)`.

## D2-10) INFORMATIONKEY EVERYWHERE

**Schema audit تصميمي لكل سجلات MUF**: أي حقل يملك سلطة visibility/availability يجب أن يكون `information_key` أو `*_information_key` وفق InformationKey المغلق؛ timestamp/position **projection descriptive convenience فقط**. المصحَّح على الأقل: `ComparisonRelationRecord.available_at` → `comparison_information_key` | HumanReview exposure timing (visibility) | episode membership | wave relation | transition | explanation state | evaluation exposures | snapshots.
- **I-IKA-1**: لا schema جديد يملك `available_at` كسلطة وحيدة.

## D2-11) INFORMATION BATCH KEY MUST EXCLUDE MECHANICAL SEQUENCE

```
InformationBatchKey {
  timeline_identity, axis_identity,
  causal_position_or_event_bucket,
  information_phase,
  source_batch_identity_if_proven_else_UNPROVEN
}
```
`deterministic_sequence` **مستبعد صراحة من market chronology**.
**الحصون**:
- **I-BATCH-1**: sequence difference وحده لا يفصل batch.
- **I-BATCH-2**: row order/file order/append order لا يثبت chronology.
- **I-BATCH-3**: source ordering contract = NOT_PROVEN ⇒ لا identifier monotonicity لإثبات ترتيب سوقي.
- **I-BATCH-4**: TIE_ORDER_CONTRACT الخاص بـBinance يبقى **NOT_PROVEN**.

## D2-12) UNIFIED CANONICAL ARTIFACT HASHING

```
CanonicalArtifactIdentity {
  artifact_type, schema_version, canonical_payload,
  domain_separator, canonical_hash
}
```
يُطبَّق على: PolicyArtifact | ObjectiveArtifact | DatasetRoleArtifact | DatasetIdentityArtifact | FoldProtocolArtifact | RepresentationSpec | EstimandArtifact | EvaluationProtocolArtifact | FrozenRepresentationBundle | Experiment protocol identities.
**الحصون**:
- **I-HASH-1**: نفس semantics + نفس canonical schema ⇒ نفس hash deterministically.
- **I-HASH-2**: تغيير semantic field ⇒ hash change.
- **I-HASH-3**: presentation-only metadata — **يُحدَّد قبل التنفيذ** هل يدخل identity أم لا (في canonical schema registry).
- **I-HASH-4**: يُستخدم public CLOSED hashing contract حيث يصلح (`research/hashing` canonical) — **لا private import ولا canonicalizer موازٍ بلا حاجة**.
- **I-HASH-5**: hash correctness **لا يثبت** semantic validity — validation تسبق/ترافق identity.

## D2-13) ARTIFACT EQUIVALENCE MUST BE CLAIM-SCOPED

```
EquivalenceClaimArtifact {
  claim_id, old_bundle_id, new_bundle_id,
  evaluation_claim_scope,
  required_equivalence_dimensions[],
  proof_refs[], result
}
```
الأبعاد المحتملة (**لا افتراض كفايتها دائماً**): `SEMANTIC_OUTPUT_EQUIVALENCE` | `CAUSAL_VISIBILITY_EQUIVALENCE` | `PROVENANCE_EQUIVALENCE` | `SELECTION_PROCESS_EQUIVALENCE` | `SCHEMA_EQUIVALENCE` | `EVALUATION_OUTPUT_EQUIVALENCE`.
**الحصون**:
- **I-EQ-1**: numeric output equality وحدها **لا تكفي تلقائياً**.
- **I-EQ-2**: الأبعاد المطلوبة تُحدد من claim/evaluation protocol **قبل رؤية patch**.
- **I-EQ-3**: dimension مطلوبة ولم تُثبت ⇒ **الشهادة القديمة لا تنتقل**.
- **I-EQ-4**: equivalence **لا يسمح** بإخفاء exposure/failure history.

## D2-14) COMPARABILITY LEVELS

ثلاثة مستويات — **بلا تخفيف أمان**:
- **`IDENTICAL_CONTRACT_COMPARABLE`** — العقود المطلوبة متطابقة حرفياً بـhashes.
- **`MAPPED_COMPARABLE`** — فقط عبر `CompatibilityArtifact` مستقل مُصرَّح (NOT IMPLEMENTED الآن — يحدد لاحقاً: source contract A/B, mapping semantics, information loss, provenance, fit/evaluation role restrictions, hash/version, owner authorization).
- **`NOT_COMPARABLE(reason)`**.

**الحصون**:
- **I-CMPL-1**: غياب CompatibilityArtifact ⇒ **لا** mapped comparability.
- **I-CMPL-2**: mapped comparability **≠ identical semantics**.
- **I-CMPL-3**: **لا silent normalization** لإجبار حالتين على المقارنة.

## D2-15) FREEZE MUST PRODUCE ONE CLOSED BUNDLE IDENTITY

```
FrozenRepresentationBundle {
  bundle_id,
  representation_spec_hash, policy_artifact_hashes[],
  objective_artifact_hash,
  descriptor_contract_hashes[], dependence_contract_hashes[], estimand_hashes[],
  fit_protocol_hash, selection_protocol_hash,
  dataset_role_artifact_hashes[], fold_protocol_hash,
  code_artifact_hashes[], experiment_registry_root, schema_contract_hashes[],
  freeze_information_key, owner_freeze_authorization_ref
}
```
عنصر غير مستخدم فعلاً ⇒ typed `NOT_APPLICABLE/NOT_CONFIGURED` حسب السبب — **لا إسقاط صامت**.
**الحصون**:
- **I-FREEZE-1**: أي semantic component change ⇒ **bundle_id جديد**.
- **I-FREEZE-2**: لا final evaluation على «تقريباً نفس bundle».
- **I-FREEZE-3**: كل evaluation protocol يشير إلى **bundle_id واحد محدد**.
- **I-FREEZE-4**: freeze **لا يعني** صحة المكونات علمياً — فقط أنها ثبتت ولم تعد تتحرك داخل claim.

## D2-16) RUNNING DESCRIPTOR CAUSALITY CONTRACT

```
DescriptorSpec {
  descriptor_id/hash, semantic_definition,
  stage ∈ {RUNNING_ONLY, FINAL_ONLY, BOTH_SEPARATE_FORMULAE},
  required_input_refs/types[], availability_rule,
  denominator_contract, boundary_contract,
  policy_dependencies[], missingness_contract,
  formula_version/hash
}
```
`BOTH_SEPARATE_FORMULAE` ⇒ **عقدين صريحين** — لا formula واحدة تُفترض قانونية في المرحلتين.
**أمثلة ممنوعة في RUNNING** (تحتاج المستقبل): normalized position within final wave duration | percentage of eventual final amplitude | final extreme-relative location | أي quantity تحتاج end fact غير متاح.
**الحصون**:
- **I-DESC-1**: كل required input للـRUNNING visible عند observation InformationKey.
- **I-DESC-2**: final facts **لا تدخل** running formula ولو لم يظهر اسمها مباشرة.
- **I-DESC-3**: derived dependency closure تُفحص **تراكبياً** مثل snapshots.
- **I-DESC-4**: future append لا يغير descriptor observation قديمة.

## D2-17) TWO DISTINCT GATES

- **GATE A — STRUCTURAL ELIGIBILITY**: يسأل فقط: هل representation قانونية سببياً، غير منهارة عقدياً، قابلة للحساب، وتنتج representation وفق تعريفها؟ الناتج: `ELIGIBLE / INELIGIBLE(reason)` — **لا winner predictive**.
- **GATE B — DEVELOPMENT INFORMATION SELECTION**: لا يفتح إلا بعد: eligible candidates + Descriptor Registry + Dependence contract + EstimandArtifact + InformationObjectiveArtifact + preregistered Development Evaluation Protocol + dataset role firewall — هنا فقط comparison معلوماتي على `DEVELOPMENT_SELECTION`.
- ثم: selection decision → FrozenRepresentationBundle → Final reserve → Final protocol → Final open.
- **إذا QualificationObjective ما زال UNDEFINED ⇒ GATE B = NOT_CONFIGURED — ولا يوجد winner.**

## D2-18) WALK-FORWARD MUST NOT SECRETLY CONSUME FINAL

Development walk-forward يستعمل `DEVELOPMENT_FIT + DEVELOPMENT_SELECTION` وفق FoldProtocolArtifact فقط. **Final evaluation data خارج كل folds** المستخدمة في: policy fit | representation tuning | descriptor design | estimand design | architecture choice | human development audit.
**الحصون**:
- **I-WF-1**: لا fold من development يصبح final بأثر رجعي بعد رؤية نتائجه.
- **I-WF-2**: Final reserved region لا يدخل expanding TRAIN قبل فتح claim النهائي الذي حُجز له.
- **I-WF-3**: التحول لاحقاً إلى live sequential operation = **بروتوكول بحث جديد** يحدد متى تنتهي الشهادة التاريخية ومتى يبدأ forward evidence — **لا إعادة تسمية live data القديمة OOS**.
- **لا أرقام folds هنا.**

## D2-19) PRE-FINAL PIPELINE DRY-RUN WITHOUT PROTECTED DATA

قبل `FINAL_EVALUATION_OPENED` يُسمح فقط بـ: schema validation | artifact identity validation | execution-path validation | synthetic fixtures | development data dry-run | resource/performance validation | output-shape validation — **بلا** protected final outputs/content.
```
PreFinalReadinessRecord { bundle_id, evaluation_protocol_id, checks[], result, proof_refs[] }
```
**الحصون**:
- **I-PFR-1**: Failure في readiness ⇒ **لا فتح Final**.
- **I-PFR-2**: Readiness **لا يستخدم** final outcomes.
- **I-PFR-3**: «just checking if it runs» على protected final data = **exposure** إذا كشف أي protected information.

## D2-20) UPDATED ADVERSARIAL DESIGN MATRIX

هجمات 25–50 كاملة في **Annex D** (violated contract + fixture concept + expected rejection/state + exact design gate لكل هجوم). لا كود.

## D2-21) OPEN QUESTIONS MUST REMAIN OPEN

القائمة صريحة في **0.3** أعلاه — والوثيقة **لا تجيب** عنها.

## D2-22) FINAL CONSOLIDATED ORDER

الترتيب النهائي الكامل في **Annex B** (S0–S15 + G0–G3). أي dependency تناقض ⇒ **DESIGN BLOCKER — OWNER REVIEW** (لا حل ارتجالي).

## D2-23) CERTIFICATION BOUNDARY

حدود D1 (Annex E) **موسَّعة** بنص D2-23 — كاملة في **Annex E**.

---

# PART II — Annexes (النهاية المطلوبة)

## Annex A — FINAL DEPENDENCY GRAPH

```
[S0] Core identities / InformationKey / immutable schemas
      │  (D2-1/2 identity basis · D2-11 batch key · D2-12 canonical hashing)
[S1] Path primitives + causal running descriptor infrastructure
      │  + episode/transition/explanation schemas  (D2-16 DescriptorSpec)
[S2] Detector witness adapter only  (D2-1 authority — لا ترقية)
[S3] Research-governance infrastructure:
      PolicyArtifact · DatasetIdentity/Role (D2-7) · Exposure ancestry ·
      HumanReview · Experiment Registry · Objective contracts ·
      FoldProtocol contracts · CanonicalArtifactIdentity
      │
[G0] AUTHORITY GATE — لا fit بلا policy-fit authorization/data roles
      │
[S4] Development policy fit where authorized
[S5] Candidate representation construction على DEVELOPMENT only
      │
[G1] STRUCTURAL QUALIFICATION → ELIGIBLE / INELIGIBLE  (لا predictive winner)
      │
[S6] Descriptor Registry/contracts for eligible representations
[S7] Dependence accounting contracts  (RESEARCH-DEBT-024 OPEN)
[S8] Estimand Catalog/preregistration
[S9] InformationObjective + Development Evaluation Protocol
      │
[G2] DEVELOPMENT INFORMATION SELECTION — أو NOT_CONFIGURED إذا objective غير موجود
      │
[S10] FREEZE exact FrozenRepresentationBundle  (D2-15)
[S11] RESERVE final dataset + EvaluationProtocolArtifact  (D2-5/6)
[S12] PRE-FINAL READINESS بلا protected outcomes  (D2-19)
      │
[G3] OWNER AUTHORIZATION TO OPEN FINAL
      │
[S13] FINAL EVALUATION OPEN/RUN once under protocol  (D2-5)
[S14] Record final result + exposure state  (irreversible)
[S15] State Graph / Reality surfaces حسب الدور المسموح
      (development Reality مبكر لأغراض structural qualification؛
       final Reality لا يؤثر على lineage دون إبطال استقلالها — I-DR-3)

[MODEL] — خارج هذا PATCH نهائياً
```

## Annex B — FINAL BUILD/RESEARCH ORDER (S0–S15 + G0–G3)

| # | المرحلة | الحواجز |
|---|---|---|
| S0 | Core identities / InformationKey / immutable schemas | — |
| S1 | Path primitives + causal running descriptor infrastructure + episode/transition/explanation schemas | — |
| S2 | Detector witness adapter **فقط** | I-PAUTH-4 |
| S3 | Research-governance infrastructure (Policy/DatasetIdentity/Role/ExposureAncestry/HumanReview/Experiment/Objective/FoldProtocol/CanonicalIdentity) | لا fit |
| **G0** | Authority gate: **لا fit بلا policy-fit authorization/data roles** | |
| S4 | Development policy fit where authorized | DEVELOPMENT_FIT فقط |
| S5 | Candidate representation construction على DEVELOPMENT | لا OOS |
| **G1** | Structural Qualification: ELIGIBLE/INELIGIBLE — **لا predictive winner** | I-SEL-1 |
| S6 | Descriptor Registry/contracts للـeligible فقط | D2-16 |
| S7 | Dependence accounting contracts | debt-024 OPEN |
| S8 | Estimand Catalog/preregistration | لا horizon post-hoc |
| S9 | InformationObjective + Development Evaluation Protocol | |
| **G2** | Development Information Selection — **أو NOT_CONFIGURED** | I-SEL-2/4 |
| S10 | Freeze exact FrozenRepresentationBundle | I-FREEZE-1..4 |
| S11 | Reserve final dataset + create EvaluationProtocolArtifact | I-RES-1 |
| S12 | Pre-Final Readiness بلا protected outcomes | I-PFR-1..3 |
| **G3** | **Owner authorization to OPEN FINAL** | |
| S13 | Final Evaluation Open/Run once under protocol | I-EVAL-1..6 |
| S14 | Record final result + exposure state | irreversible |
| S15 | State Graph / Reality surfaces حسب الدور المسموح | I-HR-2/DR-3 |
| — | **Model remains outside this patch** | |

أي module غير مبني ⇒ contract-only/NOT_CONFIGURED ولا يُقفز. أي تناقض dependency ⇒ **DESIGN BLOCKER — OWNER REVIEW**.

## Annex C — INVARIANT INDEX (الإضافة في D2)

| المجموعة | الحصون |
|---|---|
| Wave Process Identity | I-WPI-1..5 |
| Wave Identity Basis | I-WIB-1..4 |
| Selection Split | I-SEL-1..5 |
| Evaluation Protocol | I-EVAL-1..6 |
| Reserve vs Open | I-RES-1..2 |
| Dataset Identity/Ancestry | I-DATA-1..5 |
| Cycle-safe Closure | I-CLOS-1..3 |
| δ Relations | I-DELTA-1..4 |
| InformationKey Everywhere | I-IKA-1 |
| Information Batch | I-BATCH-1..4 |
| Canonical Hashing | I-HASH-1..5 |
| Claim-scoped Equivalence | I-EQ-1..4 |
| Comparability Levels | I-CMPL-1..3 |
| Frozen Bundle | I-FREEZE-1..4 |
| Descriptor Causality | I-DESC-1..4 |
| Walk-forward Firewall | I-WF-1..3 |
| Pre-Final Readiness | I-PFR-1..3 |
| GATES | G0/G1/G2/G3 (A/B في D2-17) |
| الموروث الساري | I-WPI يحل محل صياغة D1-5 · I-WID/I-WIB معًا · I-OA · I-DR · I-HR · I-PAUTH · I-SD · I-DAG-X · I-XR · I-RF · I-IK · I-SC · I-EP · I-EXPL · I-ER · I-EST · I-CMP→I-CMPL · I-MSN · I-FE · I-IMM · I-T3 · I-FR · I-DE · I-NW · I-PA · I-ST · I-EX · I-SH · I-P · I-BO |

## Annex D — ADVERSARIAL DESIGN MATRIX — الهجمات 25–50

| # | الهجوم | العقد المُختلَق | مفهوم الـfixture | الرفض/الحالة المتوقعة | البوابة التصميمية |
|---|---|---|---|---|---|
| 25 | same origin + two policy hashes يُدمجان في wave_process_id واحد | I-WPI-1/4 | basis يختلف فقط في authority_policy_hash | **wave_process_idان مختلفان**؛ الدمج مرفوض | D2-1 identity hash |
| 26 | wave identity بلا identity_basis_refs | I-WIB-1 | سجل بقائمة فارغة | رفض `NO_LEGAL_BASIS` | WaveIdentityRecord constructor |
| 27 | identity basis يحتوي future end fact | I-WPI-2/3 | basis يشير لـTP نهاية غير متاح | رفض عند البناء (visibility check) | identity basis validator |
| 28 | information-based selection قبل EstimandArtifact | I-SEL-2 | selection record بلا estimand hashes | **BLOCKED** | GATE B |
| 29 | structural diagnostic يُسمى predictive winner | I-SEL-1 | ناتج qualification: WINNER/PREDICTIVE | رفض؛ ELIGIBLE/INELIGIBLE فقط | GATE A output validator |
| 30 | final dataset يُفتح مرتين بطلب outputs مُغيَّر | I-EVAL-5/6 | طلب summaries جديدة بعد أول فتح | exploratory-only؛ لا claim output | allowed_outputs enforcement |
| 31 | final dataset يُحوَّل/re-hash ويُدعى fresh | I-DATA-1/2 | dataset مشتق بـdataset_id جديد | exposure ancestry يُكتشف؛ ليس fresh | DatasetIdentityArtifact ancestry |
| 32 | dataset مشتق يخفي ancestry لوالد مكشوف | I-DATA-3 | parent_dataset_ids فارغة ومحتوى مطابق | رفض ادعاء الاستقلال؛ ancestry إلزامي | identity/ancestry validator |
| 33 | overlap زمني يُدعى مستقلاً | I-DATA-5 | مجموعتان متداخلتان زمَناً/مصدراً | overlap مُعلن؛ لا افتراض استقلال | dataset identity validation |
| 34 | general graph cycle ⇒ closure traversal لا نهائي | I-CLOS-1 | A→B→A في state graph | إنهاء deterministic بـvisited set؛ cycle يُسجَّل | closure validator |
| 35 | cycle يتجاوز future-reference validation | I-CLOS-2 | cycle يحوي عقداً مستقبلياً | فحص التوفر يبقى رافضاً | closure availability phase |
| 36 | δ يستخدم ALTERNATES_WITH كـadjacency | I-DELTA-1 | قاعدة parent تستشهد بالعلاقة الخاطئة | رفض سوء استخدام العلاقة | δ parent rule validator |
| 37 | same-batch sequence يصنع adjacency موجَّهة | I-DELTA-2/I-BATCH-1/2 | حدثان batch واحد يُرتَّبان بالsequence | لا ADJACENT_TO موجَّهة؛ unresolved/NOT_CONFIGURED | adjacency builder |
| 38 | ComparisonRelationRecord بسلطة timestamp فقط | I-IKA-1/I-XR-2 | سجل بـavailable_at فقط | رفض schema | D2-10 schema audit |
| 39 | deterministic_sequence يفصل batch مبهماً | I-BATCH-1 | InformationBatchKey يضم sequence | رفض بناء المفتاح | InformationBatchKey validator |
| 40 | تغيير semantic field بلا تغيير hash | I-HASH-2 | payload مُغيَّر بنفس hash | mismatch مُكتشَف | CanonicalArtifactIdentity |
| 41 | numeric equality تنقل الشهادة رغم تغير provenance | I-EQ-1/3 | equivalence claim بأبعاد numeric فقط | **الشهادة لا تنتقل** | EquivalenceClaimArtifact |
| 42 | policy hashes مختلفة بين folds وanalogs تُدعى متشابهة صامتاً | I-CMPL-1/2 | snapshots عبر خطوط policy مختلفة | NOT_COMPARABLE إلا بـCompatibilityArtifact | comparability checker |
| 43 | مكوّن bundle يتغير وbundle_id ثابت | I-FREEZE-1 | policy hash مُغيَّر داخل bundle | bundle_id جديد إلزامي؛ القديم mismatch | FrozenRepresentationBundle identity |
| 44 | final data تُقيَّم قبل اكتمال frozen pipeline readiness | I-PFR-1 | open request وreadiness فاشل | **الفتح مرفوض** | G3 / PreFinalReadinessRecord |
| 45 | running descriptor يشير لـfinal duration من غير مباشرة | I-DESC-2/3 | dependency closure تشمل end fact | رفض عند spec/observation | derived dependency closure checker |
| 46 | development fold يُعاد تسميته final بعد رؤية النتائج | I-WF-1/I-DR-1 | role reassignment بعد exposure | رفض؛ الدور غير قابل للتغيير بعد exposure | DatasetRoleArtifact |
| 47 | final reserved region يتسرب إلى expanding TRAIN | I-WF-2 | نافذة تدريب متوسعة تضم المحجوز | رفض مدخلات الـfit | development fit data filter |
| 48 | allowed_outputs تتوسع بعد أول نتيجة نهائية | I-EVAL-5 | protocol mutation بعد الفتح | رفض؛ protocol immutable بعد فتحه | EvaluationProtocolArtifact |
| 49 | إخفاء نتيجة نهائية سلبية ببروتوكول ثانٍ على نفس lineage المكشوف والإبلاغ عن الثاني فقط | I-EVAL-2/I-FE-1/I-ER-2 | protocol ثانٍ بنفس dataset_ancestry_root | lineage مُعلَّم EXPOSED؛ **كلتا النتيجتين محتفظ بهما ومُبلَّغ بهما** | exposure log + Experiment Registry |
| 50 | presentation metadata يغيّر identity دلالية أو semantic field يُستبعد | I-HASH-3 | غموض canonical payload schema | schema يُقرر مسبقاً؛ determinism محفوظ | CanonicalArtifactIdentity schema registry |

## Annex E — CERTIFICATION D2-23 (الحدود الموسَّعة)

**إرث D1 (يبقى حرفياً)**: هذا التصميم، حتى لو قُبل وبُني لاحقاً، لا يثبت:
- predictive support
- statistical independence
- edge
- profitability
- probability
- optimal hierarchy
- human-like understanding
- market intention

هو يثبت فقط، عند التنفيذ والتدقيق لاحقاً:
إمكانية بناء causal structured market representation
تحت العقود المحددة،
مع provenance/availability/selection boundaries قابلة للتدقيق.

**وإضافة D2**: قبول D2 لا يثبت أن:
- أحد representations أفضل،
- أي representation يحمل معلومة مستقبلية،
- أي descriptor مفيد،
- أي estimand مناسب،
- أي dataset مستقل إحصائياً لمجرد provenance separation،
- أي final evaluation نجح.

D2 يحدد فقط كيف يمكن إجراء هذه الاختبارات لاحقاً دون خلط:
التعريف، الاختيار، المعايرة، التعرض للبيانات، والتقييم النهائي.

**END — MUF-V1-FINAL-DESIGN-PATCH-D2. لا إجراء آخر.**

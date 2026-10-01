# MUF-V1-INDEPENDENT-AUDIT-PATCH-AP1

## AUDIT PATCH AP-1 ONLY — GENERIC FACTUAL STATE GRAPH vs ESTIMAND-SPECIFIC FEATURE VIEW

**Status**: PATCHED — PENDING RE-AUDIT (narrow patch to Independent Design Audit PATCH REQUIRED)
**Date**: 2026-09-30
**أُنجزت بالإنجليزية الاصطلاحية المُلزِمة. الترجمة/الشرح لا يغيران المرجع المعتمد (المصطلحات حرفية كما في D1/D2/Correction-1).**
**Language note**: contractual deliverable in binding English terminology; Arabic explanation is not the governing artifact.

---

## 0) الحالة المرجعية والنطاق (AUTHORITY + SCOPE LOCK)

### 0.1 المرجعية

- Independent Design Audit decision: **PATCH REQUIRED** (deliverable 41) — `deliverables/41_MUF_V1_INDEPENDENT_DESIGN_AUDIT.md`.
- **BLOCKERS = 1 فقط**: **BLOCKER-1** — State-Graph/Estimand Feature-Catalog Channel (القسم F).
- NON-BLOCKING NB-1..NB-4: **RECORD ONLY**. **ممنوع ترقيعها في هذه الجولة** — لم تُعرَض ولم تُعدَّل.
- **BUILD NOT AUTHORIZED**.

### 0.2 السلطة

هذا Patch يصحح **BLOCKER-1 فقط**. كل ما عداه من D2-CORRECTION-1 / D2 / D1 / 37 / 36 **مجمَّد**.

### 0.3 ممنوع (لم يُفعل أيها)

- توسيع النطاق؛ معالجة NB-1..NB-4؛ objective جديد؛ policy/parameter؛ representation choice؛ quantile/threshold/window/horizon؛ كود/tests/MANIFEST/CLOSED؛ OOS/final/Reality analysis؛ model/strategy/PnL/توصية.

### 0.4 الإصلاح المطلوب = أربع تعديلات عقدية فقط (Parts 1–4)

---

## 1) GENERIC FACTUAL STATE GRAPH

### 1.1 العقد الجديد

```
GenericFactualStateGraphSpec {
    graph_spec_id,
    graph_spec_hash,
    state_catalog_hash,
    source_contract_hashes[],
    representation_contract_hashes[],
    descriptor_contract_hashes[],
    relation_contract_hashes[],
    missingness_contract_hash,
    information_key_contract_hash,
    schema_version
}
```

### 1.2 دلالات الـGeneric Factual State Graph

- يصف فقط **factual causal market state**.
- **لا يعرف** EstimandArtifact.
- **لا يعرف** InformationObjective.
- **لا يعرف** future observable.
- **لا يعرف** horizon.
- **لا يعرف** evaluation result.
- **لا يتغير من أجل تحسين نتيجة Estimand معيَّن.**

### 1.3 الحصون الجديدة

**I-GSG-1**: Generic state semantics must be defined before any Estimand references them.

**I-GSG-2**: GenericFactualStateGraphSpec must not import/reference: EstimandArtifact, InformationObjectiveArtifact, Evaluation result, Final outcome.

**I-GSG-3**: أي semantic state-variable جديد أو تغيير تعريف state-variable = state_catalog_hash جديد = graph_spec_hash جديد = experiment lineage جديدة وفق I-ER-3 إذا استُخدم في البحث.

**I-GSG-4**: Estimand cannot mutate Generic State Graph semantics.

### 1.4 التوافق مع السلسلة القائمة

- يُكمِّل I-DESC-3 (generic description must not reference Estimand) و I-SG-1/2 (S-GRAPH وصف وليس أساساً).
- I-GSG-3 تُقرأ مع I-ER-3 و I-DAG-X (consolidated history; supersession يُنشئ عقداً جديداً ولا يمس الماضي).

---

## 2) STATE CATALOG MUST PRECEDE ESTIMAND

### 2.1 العقد الجديد

```
StateCatalogArtifact {
    state_catalog_id,
    state_catalog_hash,
    variable_specs[],
    descriptor_refs[],
    relation_refs[],
    availability/missingness semantics,
    schema_version
}
```

### 2.2 القاعدة

كل state-variable يُسمح للـEstimand باستعماله في **population / conditioning / feature view** يجب أن يكون **معرَّفاً دلالياً في StateCatalogArtifact قبل تسجيل ذلك Estimand**.

### 2.3 الحصون الجديدة

**I-SCAT-1**: No EstimandArtifact may reference an undefined state variable.

**I-SCAT-2**: state-variable semantics cannot first appear inside EstimandArtifact.

**I-SCAT-3**: تغيير semantics بعد preregistration لا يعدل experiment القديم؛ ينشئ catalog hash جديد + experiment جديد.

### 2.4 حذف العبارة السابقة (إبطال رسمي)

- العبارة **"S-GRAPH after S8 to determine feature needs"** **تُحذف كلياً** من العقد (السابقة في 40/تسلسل S مُصحَّح Δ1): **DELETED — VOID**.
- **السبب الصحيح**: **Generic state graph/catalog exists independently of Estimand.**
- هذا الحذف يزيل BLOCKER-1 بأصله: لا قناة feature-catalog مُقدَّمة بـEstimand، ولا تعليل تناقضي لترتيب S-GRAPH.

---

## 3) ESTIMAND-SPECIFIC FEATURE VIEW

### 3.1 العقد الجديد

```
FeatureViewSpec {
    feature_view_id,
    feature_view_hash,
    state_catalog_hash,
    selected_state_variable_refs[],
    transformation_refs[],
    missingness_handling_ref,
    availability_rule_ref,
    estimand_hash,
    schema_version
}
```

### 3.2 دلالات FeatureViewSpec

- **لا يخلق factual market truth جديدة.**
- **يختار/يحوّل فقط** من inputs مُصرَّح بها.
- كل transformation **causal ومُسجَّلة**.
- أي derived feature جديدة غير موجودة في catalog تُعامل كـ **feature specification صريح داخل experiment lineage**، لا كتعديل صامت للـGeneric Graph.

### 3.3 التثبيت الإلزامي قبل أي DEVELOPMENT evaluation

**DevelopmentEvaluationProtocol** يجب أن pin صراحة:

- `estimand_hash`
- `feature_view_hash`
- `state_catalog_hash`
- `graph_spec_hash`
- `objective_hash`
- dataset role/identity
- `experiment_id`

### 3.4 الحصون الجديدة

**I-FVIEW-1**: No development evaluation without frozen-for-that-experiment FeatureViewSpec.

**I-FVIEW-2**: FeatureView change after seeing result = new experiment under I-ER-3.

**I-FVIEW-3**: FeatureView cannot access state/fact unavailable at its evaluation InformationKey.

**I-FVIEW-4**: FeatureView selection does not mutate GenericFactualStateGraph.

**I-FVIEW-5**: Feature engineering informed by Estimand is permitted only as explicitly preregistered experiment design on DEVELOPMENT data; it is never retroactively described as generic factual state semantics.

### 3.5 ملاحظة محفوظة

**Experiment Registry remains accounting/provenance, not statistical multiple-testing correction** (RESEARCH-DEBT-024 لا يزال OPEN — episodes محاسبة فقط، لا independence claim).

### 3.6 التوافق

- I-FVIEW-2 = صياغة I-ER-3 المطبَّقة صراحة على FeatureView (الذي كان ضمن «interpretation» القديمة).
- I-FVIEW-3 = I-EARLY/I-WF/I-SC-4 مطبَّقة على الـfeature channel.
- I-FVIEW-5 = I-SG-3 (basis registers ≠ factual evidence) + development/final separation (لا retroactive narrative).

---

## 4) DEPENDENCY + PROTOCOL CLOSURE

### 4.1 delta الترتيب المُصحَّح فقط (S6→G2→S10)

**S6**: Descriptor Registry + **StateCatalogArtifact** + **GenericFactualStateGraphSpec** + Generic State Graph engine/schema

**S7**: Dependence accounting contracts

**S8**: Estimand Catalog / preregistration

**S8.5** *(جديد)*: **FeatureViewSpec registration** + **DevelopmentEvaluationProtocol preregistration**

**S9**: InformationObjective + Development Information Evaluation

**G2**: Development Information Selection

**S10**: FrozenRepresentationBundle

### 4.2 قاعدة الإغلاق

أي **StateGraph code/schema/hash** وكل **FeatureView/StateCatalog dependency** اللازمة للـclaim يجب أن تكون ضمن **dependency closure الصحيحة** للـexperiment/bundle.

### 4.3 I-SG-1 المُصحَّح (يُستبدل بـ I-SG-1A/1B)

**I-SG-1A**: No DevelopmentEvaluationProtocol may reference any state/feature/transform dependency that is not pinned by canonical hash in that protocol and experiment lineage.

**I-SG-1B**: No Final EvaluationProtocol may reference any state/feature/transform dependency absent from FrozenRepresentationBundle dependency closure.

*(I-SG-1 الأصلية = SUPERSEDED by I-SG-1A/1B — لا حذف؛ استبدال موثَّق.)*

### 4.4 الاختبارات التصميمية الأربعة (A–D فقط)

**A)** Estimand E references state variable absent from StateCatalog
→ **reject `ESTIMAND_UNDEFINED_STATE_REFERENCE`** (I-SCAT-1).

**B)** State-variable semantics change after Estimand preregistration while experiment_id remains unchanged
→ **reject**; new `state_catalog_hash` + new experiment required (I-SCAT-3 / I-GSG-3 / I-DAG-X).

**C)** Development evaluation changes FeatureView after seeing first result and keeps experiment_id
→ **reject I-ER-3 / I-FVIEW-2**.

**D)** FeatureView contains causal input not pinned by hash/protocol
→ **reject before Development Evaluation** (I-FVIEW-1 / I-SG-1A).

*(هذه اختبارات تصميمية تُنفَّذ لاحقاً عند BUILD AUTHORIZATION — لا كود ولا tests في هذه الجولة.)*

---

## 5) BUILD/DEPENDENCY DELTA فقط (مقارنة بالسلسلة المجمَّدة)

| البند | السابق (40/Δ1) | الآن (AP-1) | المس |
|---|---|---|---|
| محتوى S6 | Descriptor Registry + S-GRAPH نصّي | + StateCatalogArtifact + GenericFactualStateGraphSpec (عقد صريح) | S6 فقط |
| ترتيب S8→G2 | S8 مباشرة إلى G2 | **S8.5 جديد**: FeatureViewSpec registration + DevelopmentEvaluationProtocol preregistration | ترتيب البناء |
| تعليل S-GRAPH | «after S8 to determine feature needs» | **محذوف كلياً** — catalog/graph مستقل عن Estimand | نص مُبطل |
| عقود الـfeature channel | ضمن «interpretation» فقط | FeatureViewSpec + I-FVIEW-1..5 + pinning إلزامي | عقود جديدة |
| I-SG-1 | صياغة واحدة | **I-SG-1A / I-SG-1B** (استبدال موثَّق) | استبدال نصّي |
| dependency closure | I-SG-2 الموسّعة (38/39) | + StateCatalog/FeatureView/StateGraph dependencies داخل closure الصحيح | closure فقط |
| تصميم S0–S15 باقي الأقسام | — | **byte-for-byte conceptually unchanged** | لا مسّ |
| NB-1..NB-4 | RECORD ONLY | **RECORD ONLY — لم تُعدَّل** | لا مسّ |

---

## 6) التأكيدات الإلزامية

1. **NB-1..NB-4 لم تُعدَّل** — RECORD ONLY كما في تقرير 41؛ لم تُرقَّع في هذه الجولة (ممنوع بأمر المالك).
2. **كل شيء خارج BLOCKER-1 بقي byte-for-byte conceptually unchanged** — D2-CORRECTION-1 (I-EARLY/I-IDB/I-EVP/I-SG) ما عدا I-SG-1 المُستبدَّل بـ I-SG-1A/1B، وكل D2/D1/37/36 مجمَّدة كما هي؛ لا objective/policy/representation/quantile/threshold/window/horizon جديد؛ لا كود/بنية/MANIFEST/CLOSED/OOS/final/Reality/strategy/PnL/توصية.
3. هذا Patch **لا يفتح** OOS ولا final ولا BUILD، ولا يُغني عن re-audit مستقل.

---

## 7) البناء والتشغيل

- لا كود ولا tests ولا pipeline ولا تدريب ولا فتح OOS/final في هذه الجولة.
- BUILD NOT AUTHORIZED — المالك وحده يصرّح.

---

# PATCHED — PENDING RE-AUDIT

**END OF DOCUMENT — AP-1 ONLY. لا شيء بعد هذا السطر.**

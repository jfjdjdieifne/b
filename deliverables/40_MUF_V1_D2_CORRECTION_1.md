# MUF-V1-D2-CORRECTION-1
## FOUR INTERNAL CONSISTENCY BLOCKERS

**الحالة**: DESIGN ONLY — BUILD NOT AUTHORIZED — **ليس D3 ولا إعادة تصميم**.
**النطاق المسموح**: تعديل D2 في **أربع نقاط فقط** (أدناه). كل شيء آخر في D2/37/36 **مجمّد كما هو**.
**Precedence**: حيث يصحح هذا المستند D2 — هذا التصحيح أعلى؛ خارج الأربع نقاط لا تغيير إطلاقاً.
**الممنوعات**: لا توسيع نطاق | لا objective جديد | لا policy/parameter | لا representation choice | لا كود/tests/MANIFEST/CLOSED | لا OOS/Reality analysis.

---

## 1) EARLIEST LAWFUL AVAILABILITY (تصحيح مثال D2-2 + تقوية I-WIB-3)

**الـinvariant الجديد**:
> لكل fact مشتق/هوية MUF: `fact_information_key` يجب أن يكون **EARLIEST lawful InformationKey** حيث:
> (a) كل required basis inputs مرئية قانونياً،
> (b) rule المُجمَّد satisfied،
> (c) phase/timeline/axis constraints محققة.
> **ممنوع تأخير availability اعتباطياً** إذا لم تصل معلومة/شرط جديد.

**تصحيح مثال D2-2** (النص السابق كان يضع t=118 اعتباطياً):
```
t=100  origin:   قاع عند bar 100 — لا مراجع قانونية بعد
t=112  TP known: TP#100 ينشأ. والـbasis المطلوب مكتمل عند 112:
                 [TP#100 + PolicyArtifact#P (authority) + representation_spec#R + timeline#T]
                 ⇒ wave identity يجب أن تكون متاحة عند EARLIEST lawful key عند/بعد 112
                    حسب phase contract — وليس t=118 اعتباطياً.
                 wave_identity_information_key = earliest lawful key at/after 112
                 (مثال: key(112, COMPLETED_ROW_AVAILABLE) — إذا سمحت phase contract بذلك؛
                  وإلا أول key قانوني بعدها).
t=125  running extension: RunningWaveDescriptorObservations (بلا تعديل للهوية)
t=130  end TP known:      TP#128 يُعرف عند 130
t=141  wave-end confirm:  wave_end_records + finalized_wave_geometry_ref + FORMING→CONFIRMED
```
- **إذا أُريد t=118**: يجب وجود **required fact/rule condition جديد** يصبح قانونياً عند 118 **ومذكور صراحة في required_basis_refs** — وهذا غير مُختلَق هنا (identity rule تبقى **NOT_CONFIGURED**؛ الشكل أعلاه للعقد فقط، لا rule مختار).

**الحصون الجديدة**:
- **I-EARLY-1**: `fact_information_key = earliest lawful key` (بنية أعلى) لكل fact مشتق وهوية.
- **I-EARLY-2**: سجل مؤجَّل عن earliest key دون requirement جديد ⇒ **reject `NON_EARLIEST_AVAILABILITY`**.
- **I-EARLY-3**: أي key متأخر مُدَّعى يجب أن يُبرَّر بـrequired fact/rule condition في `required_basis_refs` صار قانونياً عند ذلك الوقت.
- (I-WIB-3 في D2-1 تُقرأ الآن مقوّاة بهذا البند.)

**هجوم جديد (1)**: same basis/rule satisfied at T but record delayed to T+k without new requirement → **reject NON_EARLIEST_AVAILABILITY** — البوابة: construction-time earliest-lawful check.

---

## 2) IDENTITY-DEFINING BASIS ≠ PROOF/WITNESS REFS

**التصحيح الحاسم لـD2-1**: `wave_process_id` يعتمد **فقط** على canonical **identity-defining fields** يحددها canonical schema/rule **مسبقاً**. و`identity_basis_refs[]` **تخرج من الـhash** إلى عقد proof منفصل:

```
WaveProcessIdentityBasis {          # identity-defining فقط — يدخل الـhash
    representation_spec_hash,
    authoritative_start_turning_point_id,
    authority_policy_hash,
    timeline_id,
    intrinsic_representation_key_or_NOT_APPLICABLE
}
WaveIdentityProof {                 # لا يدخل wave_process_id
    identity_rule_ref,
    required_basis_refs[],
    proof_refs[],
    satisfaction_information_key
}
wave_process_id = canonical_hash(WaveProcessIdentityBasis)   # domain-separated
```

- **إضافة proof زائد غير مطلوب لا تغيّر wave_process_id.**
- أي field identity-defining يجب أن يكون **معلناً مسبقاً في canonical schema**؛ **لا يقرر runtime** أن reference جديد يدخل hash.

**الحصون الجديدة**:
- **I-IDB-1**: مجموعة الـidentity-defining fields مثبّتة في canonical schema قبل runtime؛ أي إدخال runtime لمرجع في hash = مرفوض.
- **I-IDB-2**: proof refs إضافية غير مطلوبة من rule ⇒ **نفس wave_process_id**.
- **I-IDB-3**: تغيير identity-defining field ⇒ **wave_process_id مختلف**.
- (I-WPI-2/3 تبقى سارية على الحقول identity-defining؛ I-WPI-4/5 كما هما.)

**هجومان جديدان (2، 3)**:
- (2) same lawful process + extra irrelevant proof ref → **نفس wave_process_id** — البوابة: identity hash construction (لا يقبل proof noise).
- (3) identity-defining field changes → **wave_process_id مختلف** — البوابة: canonical schema identity check.

---

## 3) IMMUTABLE EVALUATION PROTOCOL ≠ EVENT LEDGER

**التصحيح**: `EvaluationProtocolArtifact` **immutable قبل OPEN** — يُحذف منه كل field يحتاج mutation بعد creation: `opened_at_or_null` (حالة متغيرة) و`exposure_log_root` (mutable). الحالة الحالية = **projection للأحداث**، لا mutation للـartifact. و`protocol_hash` يبقى **byte-identical قبل/بعد الفتح**.

**العقد المنفصل الـappend-only**:
```
EvaluationProtocolEvent {
    protocol_id,
    event_type ∈ {RESERVED, OPEN_AUTHORIZED, OPENED,
                  OUTPUT_EMITTED, EXPLORATORY_OUTPUT_REQUESTED, INVALIDATED},
    event_information_key,
    payload_ref,
    previous_event_hash,
    event_hash
}
```

**صيغة `EvaluationProtocolArtifact` المصحَّحة** (immutable كلياً):
```
{ evaluation_protocol_id, protocol_hash,
  frozen_bundle_id, artifact_lineage_id,
  objective_artifact_hash, estimand_hashes[],
  dataset_identity, dataset_ancestry_root,
  allowed_outputs[], prohibited_outputs[],
  opening_authorization_ref, reservation_time,    # reservation_time ثابت وقت الإنشاء
  schema_version }                                 # (بلا opened_at_or_null، بلا exposure_log_root)
```

**الحصون الجديدة**:
- **I-EVP-1**: protocol artifact immutable؛ الحالة الحالية = projection لسلسلة الأحداث فقط.
- **I-EVP-2**: `protocol_hash` **byte-identical** قبل/بعد OPEN.
- **I-EVP-3**: سجل التعرض (exposure) يعيش في event chain (hash-linked events) — لا حقل قابل للمutation في الـartifact.

**هجوم جديد (4)**: open final → protocol_hash changes = **failure** — البوابة: pre/post-open hash comparison (I-EVP-2).

---

## 4) STATE GRAPH COMPUTATION ≠ HUMAN REALITY SURFACE

**إزالة circular dependency في S15** — فصل:
- **A) StateGraphEngine / causal state representation**: جزء من representation pipeline **قبل** information evaluation/freeze — يُبنى ويُجهَّز **قبل Development Information Evaluation**، ثم تدخل **code/schema hashes** الخاصة به في `FrozenRepresentationBundle` dependency closure.
- **B) Human/Reality visualization/audit surfaces**: تبقى في مرحلة لاحقة (S15) حسب DatasetRole/HumanReview firewall — **وهي visualization فقط، لا evaluation dependency**.

**الحصون الجديدة**:
- **I-SG-1**: **No EvaluationProtocol may reference feature/state dependency absent from FrozenRepresentationBundle dependency closure.**
- **I-SG-2**: لا يستطيع S13 (Final Evaluation) الاعتماد على شيء لا يُبنى إلا عند S15؛ أي evaluation dependency يجب أن يكون داخل bundle closure مسبقاً.

**هجوم جديدان (5، 6)**:
- (5) final estimand depends on state_graph feature whose engine/code hash is not frozen → **reject before G3** — البوابة: bundle dependency-closure check عند بناء EvaluationProtocolArtifact/PreFinalReadiness.
- (6) محاولة mutation لحقل protocol artifact بدل append حدث → **reject؛ الحالة = event projection فقط** — البوابة: I-EVP-1/3 (event-ledger write path).

---

## Δ) DEPENDENCY / BUILD-ORDER DELTA فقط (لا إعادة نسخ الترتيب كله)

| Δ | التغيير | الأثر |
|---|---|---|
| Δ1 | (البند 1) I-EARLY يُضاف إلى قواعد S0/S1 construction checks | كل fact/identity يخضع لـearliest-lawful check عند الإنشاء |
| Δ2 | (البند 2) `WaveIdentityProof` يُضاف كعقد منفصل في S0؛ D2-1 basis يُعاد صياغته | hash الـidentity يشمل identity-defining fields فقط (canonical schema registry يعلنها) |
| Δ3 | (البند 3) `EvaluationProtocolEvent` يُضاف في S3 (research-governance infra)؛ artifact S11 بلا mutable fields | S13/S14 تعتمد على event projection؛ protocol_hash ثابت |
| Δ4 | (البند 4) **مرحلة جديدة `S-GRAPH` (StateGraphEngine computation)** تُدرج **بعد S8 (Estimand prereg — لتحديد احتياجات الميزات) وقبل S9 (Development Information Evaluation)**؛ وتُنقل code/schema hashes إلى `FrozenRepresentationBundle` (S10) | S15 يحتفظ **فقط** بـHuman/Reality surfaces؛ S13 لا يعتمد على S15 إطلاقاً |
| Δ5 | بوابة **G3** تضيف فحص: evaluation protocol/estimand features ⊆ FrozenRepresentationBundle dependency closure | رفض الهجوم 5 قبل فتح Final |

**الاعتماديات الناتجة (delta فقط)**: `S9 ← S-GRAPH ← S8`؛ `S10 (bundle closure) ← S-GRAPH hashes`؛ `S13 ← bundle closure فقط`؛ `S15 = visualization فقط (بلا edge إلى S13)`.

**فهرس الحصون الجديد**: I-EARLY-1..3 | I-IDB-1..3 | I-EVP-1..3 | I-SG-1..2 — (كل ما عدا ذلك في D2 يبقى مجمّداً كما هو).

**END — MUF-V1-D2-CORRECTION-1. لا شيء آخر.**

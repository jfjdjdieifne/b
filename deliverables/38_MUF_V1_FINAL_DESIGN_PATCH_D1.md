# MUF-V1-FINAL-DESIGN-PATCH-D1
## SELECTION AUTHORITY · OOS FIREWALL · SCALE SEMANTICS · INFORMATION CLOSURE

**الحالة**: DESIGN ONLY — BUILD NOT AUTHORIZED — PATCH تصميمي فقط (لا كود، لا src/، لا tests/، لا MANIFEST، لا CLOSED، لا quantile/threshold/window/horizon، لا model، لا strategy، لا PnL، لا توصية، لا Reality analysis على بيانات فعلية، لا فتح OOS، لا اختيار α/β/γ/δ).
**الإصدار**: MUF-V1-FINAL-DESIGN-PATCH-D1 — 2026-09-29
**المرجعية**: MUF-V1-FINAL-DESIGN-2026-09-29 (=`37`) + MASTER DESIGN (=`36`).
**Precedence rule**: حيث يتعارض هذا التصحيح مع `37` أو `36` — **هذا التصحيح هو الأعلى**. غير المذكور هنا يبقى سارياً كما هو.

---

# PART 0 — التمهيد

## 0.1 قائمة البنود المصحَّحة من FINAL DESIGN (وأين)

| # | بند 37/36 المصحَّح | تصحيح D1 |
|---|---|---|
| 1 | 37 §7.1/§17 + 36 §20: عبارة «TRAIN-only calibration → competition → choose/freeze» تسمح اختيار winner بلا سؤال معرَّف | D1-1: `ObjectiveArtifact` إلزامي قبل أي selection/freeze — QualificationObjective يبقى **UNDEFINED** |
| 2 | 36 §10/37 §7: لغة «TRAIN/OOS cutoffs» لا تمنع architecture selection على OOS | D1-2: `DatasetRoleArtifact` بثلاثة أدوار + تعريف exposure صريح |
| 3 | 37 §15: Reality Audit لا يفصل قناة العين كمصدر overfitting | D1-3: `HumanReviewRecord` + فصل dev/final audit firewall |
| 4 | 37 §7.2/§16: «S2 = BUILD READY كمستهلك» — ضمنية أن خرج 2.1A يصلح كـfact | D1-4: فصل `DetectorWitnessRecord` / `AuthoritativeTurningPointRecord` — لا ترقية ضمنية |
| 5 | 36 §2.1: `wave_id = hash(anchor_identity)` دون بيان أن الهوية عملية origin-anchored لا interval نهائي | D1-5: `wave_process_id` ≠ `finalized_wave_geometry_ref` |
| 6 | 37 §4 I-DAG-1: شرط `child.scale_order < parent.scale_order` — رتبة مشتقة من parentage لا تصلح حارساً | D1-6 + D1-7: فصل scale≠depth + invariant بلا rank دائري |
| 7 | 36 §4/37 §8: δ «Containment Closure» بلا حدود دلالية كافية | D1-8: إعادة تسمية `EVENT_ANCHORED_CONTAINMENT_HIERARCHY` + حدود صريحة لكل الحالات |
| 8 | 36 §8.3/37 §2.3: ALTERNATES_WITH ممتدة ضمنيًا لتوافقات عبر التمثيلات | D1-9: فصل ontology داخلي/خارجي + `ComparisonRelationRecord` |
| 9 | 37 §2.1 `wave_formation_observations` دون typed namespaces للاستعلام | D1-10: `RunningWaveDescriptorObservation` / `FinalWaveDescriptorRecord` |
| 10 | 36 §2.1/37 §1: `available_position/time` كسلطة أساسية | D1-11: InformationKey الكامل هو السلطة؛ available_* مجرد projection convenience |
| 11 | عقد TIE_ORDER_CONTRACT مطبَّق على التعادل السعري فقط | D1-12: قاعدة same-information-batch على كل سجلات MUF |
| 12 | 37 §1 I-IMM-3: byte-identical دون إلزام closure تراكبي | D1-13: snapshot = causal closure تراكبي مرفوض البناء عند أي تسريب |
| 13 | 37 §9: `episode_id = hash(origin-anchored production path)` دون فصل العضوية | D1-14: `EpisodeAnchorIdentity` ≠ `EpisodeMembershipEvent` |
| 14 | 37 §11: حالة `FACTUALLY_ESTABLISHED_WHERE_POSSIBLE` تُقرأ كتثبيت التفسير السوقي | D1-15: استبدالها بـ`PATTERN_REQUIREMENTS_SATISFIED` |
| 15 | 36 §5/37 §17: لا سجل محاولات (winner من مئات المحاولات) | D1-16: `RepresentationExperimentRecord` + preregistration |
| 16 | 36 §12/O: عقد Edge Gate دون ترتيب Estimand إلزامي | D1-17: ordering contract — Estimand قبل أي Information claim |
| 17 | 36 §9 J: comparability = نفس representation/policy فقط | D1-18: عقد قابلية المقارنة الكامل + حالات NOT_COMPARABLE |
| 18 | 36 §9/§10: missingness ضمن المقارنة دون صياغة الهوية | D1-19: availability/missingness جزء من state identity |
| 19 | 37 §7.1 I-PA-2: لا بروتوكول لسيناريو الفشل النهائي | D1-20: سيناريو literal + lineage جديدة + artifact-equivalence |
| 20 | 37 §17 BUILD ORDER لا يحترم الاعتماديات أعلاه | D1-21: بناء مُعاد كلياً + بوابة objective/roles/authorization |
| 21 | 36 §T: خطة اختبارات بلا matrix هجمات تصميمية | D1-22 + Annex D |
| 22 | — | D1-23: Certification Boundary ختامي حرفي |

## 0.2 OPEN BLOCKERS بعد D1
1. **QualificationObjective = UNDEFINED** — يتطلب تفويض مالك بعقد منفصل (I-OA-5) — **OWNER DECISION REQUIRED / NOT_CONFIGURED**.
2. مصدر `PolicyArtifact` (TRAIN-only) غير محلول — S2+ المتقدمة متوقفة.
3. **FoldProtocolArtifact** (عدد/حدود الأقسام الزمنية) — لا split رقمي مقدس — **OWNER DECISION REQUIRED / NOT_CONFIGURED**.
4. RESEARCH-DEBT-020..025 (منها 024) تبقى OPEN.
5. External context (dominance إلخ) NOT_CONFIGURED — Dominance لا يُستنتج من BTCUSDT.
6. δ: الحالات التي تتطلب threshold غير موجود (§8) NOT_CONFIGURED.
7. بيانات المالك للتشغيل الحقيقي (جهازه فقط).

## 0.3 UNDEFINED عمداً (لا يخترعه أحد)
QualificationObjective | مقاييس التفوق | quantiles/thresholds/windows/horizons | اختيار α/β/γ/δ | parameters الـpolicy | distance/similarity للanalogs | أي ادعاء statistical independence | أي Model.

---

# PART I — البنود

## D1-1) OBJECTIVE AUTHORITY — لا Calibration بلا سؤال معرَّف

**المشكلة**: «best representation» ممنوعة قبل `best according to what?`.

**العقد المُطلَب (typed)**:
```
ObjectiveArtifact {
  objective_id, objective_hash,
  objective_kind ∈ {DETECTION_VALIDITY, REPRESENTATION_DIAGNOSTIC,
                    INFORMATION_OBJECTIVE, ECONOMIC_OBJECTIVE},
  semantic_definition,          # صياغة السؤال حرفياً
  estimand_refs[],              # للـINFORMATION_OBJECTIVE فقط — وإلا فارغ
  dataset_role_permissions[],   # أي أدوار datasets يُسمح قياسه عليها
  aggregation_contract,
  missingness_contract,
  tie_contract,                 # ماذا يحدث عند التعادل بين المرشحين
  comparison_direction_if_applicable,
  creation_time,
  code_version / code_hash_if_executable,
  owner_authorization_ref       # تفويض المالك — إلزامي لكل kind
}
```

**الفصل الإلزامي بين الأنواع**:
- **A) DETECTION_VALIDITY** — هل التنفيذ يطابق العقد السببي/الهندسي؟ (objective واقعي/هيكلي — ليس predictive).
- **B) REPRESENTATION_DIAGNOSTIC** — أوصاف بنيوية/تشخيصية (كثافة، اتساق، تغطية) — **لا تثبت Edge أبداً**.
- **C) INFORMATION_OBJECTIVE** — **لا يُنشأ إلا بعد Estimand Contract شرعي** (D1-17).
- **D) ECONOMIC_OBJECTIVE** — **OUT OF SCOPE في MUF** مطلقاً.

**الحصون**:
- **I-OA-1**: إذا objective المطلوب غير موجود ⇒ `NOT_CONFIGURED` / `UNDEFINED` — **ولا اختيار winner** إطلاقاً.
- **I-OA-2**: نجاح البوابات السببية/Reality ≠ تفوق representation.
- **I-OA-3**: التطابق البصري ≠ objective.
- **I-OA-4**: لا metric مخترع داخل هذا PATCH.
- **I-OA-5**: **QualificationObjective يبقى UNDEFINED** ما لم يفوضه المالك بعقد منفصل لاحقاً.

**تصحيح BUILD ORDER**: S4/S5/S6 (calibration/competition/freeze) **ممنوعة** من اختيار أو تجميد winner دون `ObjectiveArtifact` صالح لـobjective_kind المحدد + `owner_authorization_ref` + إسناد dataset roles. أي محاولة selection تحت objective مفقود = `SelectionBlockedError(OBJECTIVE_UNDEFINED)`.

## D1-2) DATASET ROLE FIREWALL

**المشكلة**: TRAIN/OOS وحدهما لا يمنعان architecture selection على OOS.

```
DatasetRoleArtifact {
  dataset_identity,
  role ∈ {DEVELOPMENT_FIT, DEVELOPMENT_SELECTION, FINAL_EVALUATION_LOCKED},
  role_assignment_time, role_assignment_hash,
  permitted_operations[], prohibited_operations[],
  exposure_state ∈ {UNEXPOSED, EXPOSED_DEVELOPMENT, EXPOSED_FINAL, EXPOSED_INVALID_FOR_FINAL_SELECTION},
  exposure_events[],            # append-only
  owner_authorization_ref
}
```

**التعريف الصريح لـExposure** (لا يعني فقط تشغيل metric): رؤية metric/summary على dataset | رؤية charts | manual inspection | Reality Audit | استخدام النتائج لطلب تغيير code/policy/schema/representation | استخدام dataset في fit | استخدام dataset في selection | أي مشتق يكشف outcome/structure بصورة تؤثر في التصميم.

**الحصون**:
- **I-DR-1**: الدور يُسند **قبل** الاطلاع على أي نتائج ذلك dataset (role_assignment_time < أي exposure_event).
- **I-DR-2**: `FINAL_EVALUATION_LOCKED` لا يُستخدم لـfit ولا selection ولا architecture choice ولا threshold choice ولا visual tuning.
- **I-DR-3**: إذا أثّر FINAL_EVALUATION_LOCKED على تعديل النظام ⇒ تُسجَّل النتيجة `EXPOSED_INVALID_FOR_FINAL_SELECTION`، ولا يجوز إعادة تسمية «final» لنفس artifact lineage أبداً.
- **I-DR-4**: أي refit أو تغيير representation/policy/code بعد final exposure ⇒ **lineage جديدة** + evaluation dataset صالح وفق بروتوكول جديد.
- **I-DR-5**: لا «إعادة تدوير» OOS إلى OOS جديد بالاسم فقط (تكرار الدور على نفس البيانات المكشوفة = مرفوض؛ أي إعادة استخدام تتطلب هوية بيانات مختلفة فعلياً).

**التوافق مع walk-forward — دون split رقمي مقدس**: walk-forward = تسلسل أزواج أدوار مُعلَنة: في كل fold، جزء التدريب = `DEVELOPMENT_FIT` وجزء التحقق = `DEVELOPMENT_SELECTION`، وتُسند أدوار كل جزء **قبل فتح fold**. `FINAL_EVALUATION_LOCKED` = مجموعة خارج التسلسل كلياً، لا تُفتح إلا مرة واحدة بعد FREEZE. عدد الـfolds وحدودها الزمنية = `FoldProtocolArtifact` — **OWNER DECISION REQUIRED / NOT_CONFIGURED** (لا رقم مقدس هنا). مبدأ المصادقة على الأداء بين folds لا يُغني عن firewall: selection داخل walk-forward يبقى DEVELOPMENT فقط.

## D1-3) HUMAN / REALITY AUDIT FIREWALL

```
HumanReviewRecord {
  review_id, dataset_identity, dataset_role,
  artifacts_viewed[], charts_viewed[],
  reviewer, review_time,
  observations[], requested_changes[],
  change_influence ∈ {NONE, DIAGNOSTIC_ONLY, DESIGN_INFLUENCING}
}
```

- **DEVELOPMENT_REALITY_AUDIT**: يمكن أن يؤثر في التصميم — فقط على datasets تسمح أدوارها بذلك (`DEVELOPMENT_*`) — وكل تأثير يُسجَّل (`DESIGN_INFLUENCING` + requested_changes).
- **FINAL_EVALUATION_REALITY_AUDIT**: audit فقط — إذا أدى إلى modification ⇒ dataset يفقد صلاحية final لهذا lineage (I-DR-3).
- **الحصن الحاسم**: «I did not fit numerically» **ليس دفاعاً** — التعديل بعد النظر للشارت = exposure/design influence مُسجَّل.
- **I-HR-1**: كل مراجعة تُسجَّل قبل أو عند وقوعها (append-only)؛ مراجعة بلا سجل = مخالفة.
- **I-HR-2**: مراجعة final أدت إلى `requested_changes` غير فارغة ⇒ تفعيل I-DR-3 آلياً.

## D1-4) POLICY AUTHORITY — منع Authority Laundering

**الفصل الإلزامي**:
```
DetectorWitnessRecord {              # ما يثبته فقط:
  witness_id, engine_identity,       # «المحرك المغلق أنتج X تحت policy/input identity Y»
  policy_input_identity, output_ref,
  NOT: authority to build MUF facts
}
AuthoritativeTurningPointRecord {    # يتطلب:
  ..., authority_policy_hash,         # PolicyArtifact صالحاً بنطاق MUF
  authority_kind ∈ {MUF_POLICY_ARTIFACT, PREDEFINED_EQUIVALENT_CONTRACT}
}
```

**الحالات الثلاث**:
- **A) policy = NOT_CONFIGURED** ⇒ لا Authoritative TP | لا factual wave | لا populated hierarchy — تماماً.
- **B) legacy/external policy witness بلا MUF authority** ⇒ `DetectorWitnessRecord` فقط — يصلح للاستشهاد/الاختبار لا للسلطة.
- **C) `PolicyArtifact` مُجمَّد ومُفوَّض** ⇒ الترقية من witness إلى fact **جائزة وفق العقد** (ترقية = سجل `AuthoritativeTurningPointRecord` جديد — لا تعديل للـwitness).

**الحصون**:
- **I-PAUTH-1**: لا ترقية ضمنية witness → fact (أي استعلام factual يستبعدها).
- **I-PAUTH-2**: كل factual TP يحمل `authority_policy_hash`.
- **I-PAUTH-3**: أي PolicyArtifact خارج scope السوق/الإطار/representation ⇒ **يفشل مغلقاً** (`PolicyScopeMismatch`).
- **I-PAUTH-4**: S2 قبل policy infrastructure **لا ينتج** authoritative MUF hierarchy إطلاقاً.

**تصحيح BUILD ORDER**: S2 = **detector witness adapter فقط** (D1-21).

## D1-5) WAVE IDENTITY SEMANTICS

**التعريف الحرفي**: الهوية أثناء FORMING = **origin-anchored causal wave process identity** — وليست final start/end interval identity.

**الفصل**:
- `wave_process_id` = hash(domain="MUF_WAVE_PROCESS_V1", payload={representation_id, origin_start_anchor, scale/representation key, policy_hash?}) — **أصل فقط، لا end facts**.
- `finalized_wave_geometry_ref` = سجل هندسة لاحق (D1-10 Final namespace) يُضاف عند `wave_end_confirmed_available_at` — **ولا يدخل أبداً في hash الهوية القديمة**.

**الحصون**:
- **I-WID-1**: future extension (مثال المالك: 108→112→118) **لا تغيّر هوية العملية** التي كانت معروفة عند T إذا لم يحدث supersession عقدي.
- **I-WID-2**: final geometry تُضاف بسجل جديد فقط — لا retroactive hashing.
- **I-WID-3**: إذا تغيّر تفسير الهوية فعلياً ⇒ `SUPERSEDES`/`ALTERNATES` (سجلات جديدة) — **لا mutation**.

**المثال الزمني الصريح** (بارات افتراضية للعقد فقط — لا معلمات):
```
t=100  origin:          قاع سعري عند bar 100 (extremum-so-far) — لا شيء معلن
t=112  TP known:        turning_point_records ينشأ (origin=100, available=112)
t=118  wave process known: wave_identity_records ينشأ — wave_process_id يُحسب من origin=100 فقط
t=125  running extension: wave_formation_observations تُكتب (108→112→118 داخلها لقطات — لا تعديل)
t=130  end TP known:    turning_point (origin_end=128) يُعرف عند 130
t=141  wave-end confirm: wave_end_records ينشأ (triple_end كامل، finalized_wave_geometry_ref)
                         و wave_status_events: FORMING→CONFIRMED عند 141
```
لو استمرت الحركة إلى 118 ثم 124: الملف عند t=141 يظل كما خُتم لاحقاً — والعمليات السابقة (125) لا تتغير بايتياً (I-IMM-3).

## D1-6) SCALE ≠ DEPTH

**المثال الإلزامي**: T1: A ⊃ B (depth(B)=1)؛ ثم T2: X ⊃ A ⊃ B (depth(B)=2). **ممنوع تعديل سجل B**.

**الفصل الثلاثي**:
- **A) `representation_scale_key`** — intrinsic coordinate داخل representation (قد تكون `NOT_APPLICABLE` لبعض العائلات — β/δ تحديداً).
- **B) `hierarchy_depth_as_of(T)`** — قيمة **مشتقة** من factual graph عند T (query-time derivation، ليست حقلاً مخزناً في السجلات).
- **C) `policy scale/rank`** — موجود فقط عندما يعرّفه family فعلياً (α) ويحمل policy_hash.

**الحصون**:
- **I-SD-1**: depth ليست immutable intrinsic fact إذا يمكن ظهور ancestors لاحقاً.
- **I-SD-2**: لا إعادة كتابة WaveRecord لأن parent جديد ظهر.
- **I-SD-3**: مقارنة scales عبر representations مختلفة = `NOT_COMPARABLE` إلا بعقد mapping منفصل مُصرَّح.
- **I-SD-4**: **δ لا تتنكر على أنها α** بإعطاء depth اسم scale — δ تصرّح `representation_scale_key=NOT_APPLICABLE` وتستخدم depth المشتقة فقط.

## D1-7) DAG INVARIANT — لا circular rank authority

**المشكلة**: `child.scale_order < parent.scale_order` حارس دائري إذا كانت parentage نفسها تولّد الرتبة.

**ال.Invariant العام (بلا rank مشتق من graph)**:
1. **strict valid interval containment** حيث تنطبق (المدى الداخلي صارم — ليس نفس المدى) — وهذا الشرط **بمفرده** ترتيب جزئي لا يقبل الدورات.
2. **endpoint availability**: الطرفان (وقائع الأطراف وال علاقة) متاحان عند `relation_available_position`.
3. **no self-edge**.
4. **explicit cycle check at insertion** — رفض fail-closed (`cycle_injection_rejected`).
5. **representation-specific constraints** منفصلة عن الحارس العام (تُطبَّق إضافة، لا كبديل).

**للعلاقات غير interval-containment** (مثل بعض relations التمثيلية): قواعدها **منفصلة** بعقد نوعها الخاص — ولا تُمدَّد `CONTAINS` لتغطيها.
- **I-DAG-X**: لا يمكن إثبات صلاحية edge باستخدام قيمة لا تصبح معلومة إلا نتيجة قبول edge نفسها (لا rank دائري، لا depth كشرط قبول).
- cycle injection يبقى **fail-closed** عند الإدراج (D1-22 هجوم 18).

## D1-8) δ SEMANTIC LIMIT

**الشهادة الجديدة**: `EVENT_ANCHORED_CONTAINMENT_HIERARCHY` — وهي **compression/containment hierarchy** وصفية.
**ممنوعات صريحة**: market importance | major/minor importance | true wave hierarchy | predictive significance — إلا بعقد لاحق مُصرَّح.

**الدلالات المحددة**:
- **ما الحدث الذي يخلق parent candidate؟** — اكتمال حد احتواء قانوني: وجود أبناء مؤكدين (segments بين TPs مؤكدة) تحقق بينهم علاقة `ALTERNATES_WITH` واتحاد مداهم يحقق احتواءً صارماً لوحدة واحدة ⇒ `candidate_containment_edge` (CANDIDATE_NOT_FACTUAL) نحو أصغر مدى احتواء **محسوب من أطراف الأبناء المعروفة**.
- **ما الذي يحوله إلى factual parent؟** — سجل `wave_relation_events` جديد عند `relation_available_position` عندما تتوفر حدود الأب الفعلية (أصغر مدى احتواء **مُثبَّت بوقائع الأطراف المتاحة**) + توفّر شروط D1-7.
- **لماذا أصغر interval الحاري ليس اعتباطياً؟** — لأن تعريفه **بنيوي خالص**: تقاطع (closure) محدد الحدود لاتحاد أطراف الأبناء — لا parameter فيه؛ أي مدى أوسع = حاوية غير minimally-contained ويُرفض كـfactual parent.
- **أكثر من minimal legal closure؟** (اتحادان متساويان في الأصغرية بتركيبات مختلفة) ⇒ **tie**: تُنشأ candidatures متنافسة موسومة `ALTERNATES_WITH` — لا factual parent **بلا قاعدة كسر تعادل مُصرَّحة** ⇒ `NOT_CONFIGURED(AMBIGUOUS_MINIMAL_CLOSURE)` حتى عقد/سياسة.
- **ties (أطراف متساوية)** ⇒ ALTERNATES_WITH فقط (TIE_ORDER_CONTRACT) — لا أبوة.
- **overlapping-but-not-contained** ⇒ لا CONTAINS؛ يُسجَّل `PARTIAL_OVERLAP` (intra-representation relation) فقط.
- **gaps between children** ⇒ الأب المرشح يُبنى على union الأطراف؛ الفجوات تبقى وقائع داخلية (path_length) — لا اكتمال احتواء بالـgap.
- **non-alternating child direction** (ابنان بنفس الاتجاه متجاوران) ⇒ segment واحد ممتد بين أطرافهما (بحسب policy التمديد) — **بلا threshold** هنا ⇒ الحالة `NOT_CONFIGURED(NON_ALTERNATING_MERGE_RULE)` إن لم تكن policy معرفة.
- **parent with one child فقط** ⇒ **مرفوض** كـfactual parent (الاحتواء الذاتي وحده لا يكوّن أباً) — child يبقى بلا parent factual؛ لا اختراع إخوة.
- **identical geometry** (موجتان نفس المدى والأطراف) ⇒ `GEOMETRICALLY_COINCIDENT` + `ALTERNATES_WITH` — لا اندماج هوية تلقائي (I-XR-1 حتى داخل التمثيل: الاندماج يتطلب عقد supersession صريح).

## D1-9) INTRA-REPRESENTATION ≠ CROSS-REPRESENTATION

**داخل representation** (ontology مغلقة): `CONTAINS`, `ALTERNATES_WITH`, `SUPERSEDES`, + relations محددة العقد لكل family.
**بين representations**: `ComparisonRelationRecord` فقط:
```
ComparisonRelationRecord {
  record_id, left_ref (representation_id + entity_ref), right_ref,
  relation ∈ {BOUNDARY_MATCH, GEOMETRICALLY_COINCIDENT, PARTIAL_OVERLAP, DISJOINT,
              NOT_COMPARABLE(reason)},
  geometric_evidence_ref,   # إثبات هندسي فقط
  available_at
}
```
**الحصون**:
- **I-XR-1**: نفس endpoints في α وβ **لا يعني** نفس identity.
- **I-XR-2**: cross-representation relation **لا تدخل** factual hierarchy لأي representation إطلاقاً.
- **I-XR-3**: لا consensus voting بين التمثيلات بلا عقد لاحق.

## D1-10) RUNNING ≠ FINAL DESCRIPTORS

```
RunningWaveDescriptorObservation {
  wave_process_id, as_of_information_key,
  stage = "RUNNING",
  running values... (extreme_so_far, displacement_so_far, path_length_so_far, ...)
}
FinalWaveDescriptorRecord {
  finalized_wave_geometry_ref, wave_end_confirmed_information_key,
  stage = "FINAL",
  final values...
}
```
**الحصون**:
- **I-RF-1**: final descriptor **غير قابل للاستعلام** في decision/as-of surface قبل end confirmation (البوابة ترفض الاستعلام).
- **I-RF-2**: نفس الاسم الدلالي إن وُجد في الطبقتين يحمل `stage` صريحة إلزامية في كل استعلام/مخرج.
- **I-RF-3**: append future لا يغير running descriptor قديم (كل لقطة immutable — I-IMM).
- **I-RF-4**: اختبار إلزامي قادم: محاولة استبدال running بقيمة final **يجب أن تكشفها causality gate** (هجوم 5 في Annex D).

## D1-11) INFORMATIONKEY CLOSURE

كل factual MUF record يحمل أو يشير إلى **InformationKey كامل** متوافق مع العقد المغلق (`information_time`: timeline_id, bar_position, event_time_utc, information_phase, deterministic_sequence — والمحور القانوني). `available_position/time` = **projection convenience فقط** — لا سلطة أساسية.

**الحصون**:
- **I-IK-1**: cross-timeline reference ⇒ **reject**.
- **I-IK-2**: POSITIONAL لا يكتسب timestamp مُختلَقاً (event_time يبقى غير قانوني/غير مستنتج).
- **I-IK-3**: TIME_INDEXED يتطلب الزمن القانوني/tz-aware حسب العقد الحالي.
- **I-IK-4**: BAR_PRE_CLOSE لا يرى completed-bar fact أبداً.
- **I-IK-5**: `deterministic_sequence` **لا يثبت** chronology سوقية (ترتيب ميكانيكي فقط).

## D1-12) SAME INFORMATION BATCH

**القاعدة المطبَّقة**: `mechanical ledger order ≠ market chronology` — على: turning-point events | wave identity | wave end | relation events | episode membership | transitions | explanation state changes.
- إذا حدثان في **Information Batch واحد** (InformationKey متساوي في timeline/position/phase/sequence-resolved) ولا يوجد مصدر chronology قانوني ⇒ `same_information_batch_order_unknown = TRUE` على الزوج/المجموعة.
- **I-IB-1**: لا explanation ولا transition ولا relation يستطيع الاستنتاج من ترتيب صفوف التخزين أن «A حدث قبل B» — أي استدلال زمني بين أعضاء batch واحد مرفوض ما لم يأتِ من chronology مصدر خارجي موثّق (غير متوفر حالياً داخل المبهم).

## D1-13) SNAPSHOT CAUSAL CLOSURE

- **I-SC-1**: كل reference reachable من `StateSnapshotRecord` عند T يجب أن يكون **visible قانونياً عند InformationKey(T)** — تراكبياً: snapshot → wave → relation → episode → member → source fact.
- **I-SC-2**: **hash صحيح لا يقدّس snapshot مسرّباً** (الهوية ≠ الصحة السببية).
- **I-SC-3**: أي future/incompatible reference ⇒ **reject at snapshot construction** (لا إسقاط لاحق صامت).
- **I-SC-4**: `market_state_at(T)` = **causal closure**، لا filter سطحي على `available_at` — البناء يتحقق تراكبياً عند الإنشاء ويُختم بـ`closure_verified=TRUE` + سجل فهرس المرجعات المُتحقَّق منها.

## D1-14) CAUSAL EPISODE IDENTITY

**الفصل**: `EpisodeAnchorIdentity` (immutable anchor facts عند creation فقط) ≠ `EpisodeMembershipEvent` (append-only).
- `episode_id = hash(domain="MUF_EPISODE_ANCHOR_V1", anchor_facts)` — **لا member set**.
- **I-EP-1**: إضافة عضو **لا تغيّر** episode_id.
- **I-EP-2**: إزالة عضو تاريخياً ممنوعة؛ التصحيح إن احتاجه العقد = `supersession/correction event` صريح — **لا mutation**.
- **I-EP-3**: episode accounting **≠ statistical dependence proof** — **RESEARCH-DEBT-024 يبقى OPEN**.

## D1-15) EXPLANATION SEMANTICS

**الاستبدال الصريح**: `FACTUALLY_ESTABLISHED_WHERE_POSSIBLE` **محذوفة** → **`PATTERN_REQUIREMENTS_SATISFIED`**.
**الحالات النهائية**: `MONITORING | PATTERN_REQUIREMENTS_SATISFIED | CONTRADICTED | SUPERSEDED` — وصفية دائماً.
**ممنوعة نهائياً** (بلا عقد لاحق): `PROBABLE | LIKELY | SUPPORTED | WINNING_EXPLANATION`.
- **I-EXPL-1**: وجود كل required facts يثبت **تطابق pattern فقط** — لا «سبب السوق» ولا ترجيح.
- (احتماليات/أوزان/دعم تنبؤي = ما زالت ممنوعة — D1/37 §11.)

## D1-16) EXPERIMENT REGISTRY — ذاكرة كل المحاولات

```
RepresentationExperimentRecord {
  experiment_id,
  preregistration_time,             # قبل أي رؤية نتائج
  representation_spec_hash, policy_artifact_hashes[],
  objective_artifact_hash,
  dataset_identities_by_role,
  code_hash, fit_protocol_hash, selection_protocol_hash,
  result_refs[], failure_refs[],
  status ∈ {PREREGISTERED, RUNNING, COMPLETED, FAILED, SUPERSEDED},
  supersedes_experiment_id?
}
```
**الحصون**:
- **I-ER-1**: لا experiment بلا preregistered identity (يُرفض البدء).
- **I-ER-2**: **الفشل يبقى في السجل**.
- **I-ER-3**: تغيير parameter/spec/objective/data role ⇒ **experiment جديد**.
- **I-ER-4**: **لا حذف** unsuccessful trials أبداً.
- **I-ER-5**: السجل **لا يدعي وحده** تصحيح multiple testing — هو provenance/accounting ضروري فقط.

## D1-17) ESTIMAND BEFORE INFORMATION CLAIM

**ترتيب العقد الإلزامي**:
`Descriptor Registry → Dependence accounting (episodes) → Estimand Catalog → preregistered Information Evaluation → Model لاحقاً فقط إذا مُفوَّض`.
- `EstimandArtifact` (لاحقاً — لا تنفيذ الآن) يجب أن يحدد **قبل** evaluation: population | treatment/exposure أو conditioning semantics إن وجدت | outcome/future observable | horizon/boundary semantics | censoring | missingness | aggregation | dataset role | code/hash/version | preregistration identity.
- **I-EST-1**: ممنوع اختيار horizon بعد رؤية النتيجة وتسميته «المقياس الطبيعي» — أي evaluation بغير estimand مُسجَّل مسبقاً = `EVALUATION_WITHOUT_ESTIMAND` مرفوض.

## D1-18) COMPARABILITY CONTRACT

أي `StateSnapshot` قابل للمقارنة يحمل على الأقل: `representation_id/hash` | `policy_hash lineage` | `descriptor_set_version/hash` | `InformationKey semantics version` | `history_boundary_kind/ref` | `source semantic identities` | `ACTUAL/PROXY availability mask` | `schema version`.
**الحالات**: `COMPARABLE` أو `NOT_COMPARABLE(reason)`.
- **I-CMP-1**: **لا distance/similarity computation** إطلاقاً إذا NOT_COMPARABLE.
- **I-CMP-2**: **لا imputation صامت** لمصدر غائب — الغياب يبقى في availability mask.

## D1-19) SOURCE / REPRESENTATION MISSINGNESS

- إذا ACTUAL flow غائب وحاضر PROXY ⇒ **لا** snapshot «مكافئ» تلقائياً لحالة فيها ACTUAL — availability/missingness **جزء من state identity/comparability** (mask في D1-18).
- **I-MSN-1**: أي استبدال ACTUAL↔PROXY صامت = مخالفة؛ الاستبدال المُصرَّح (إن سمح به العقد يوماً) يُسجَّل كسجل مشتق بعلامته — لا يُطلى الأصل.
- External context يبقى **NOT_CONFIGURED**؛ **Dominance لا يُستنتج من BTCUSDT** (كما في 36 §10.3).

## D1-20) FINAL EVALUATION DOES NOT BECOME DEVELOPMENT SILENTLY

**السيناريو حرفياً**:
> النظام مُجمَّد. `FINAL_EVALUATION_LOCKED` فُتح. النتيجة كشفت failure حقيقي. المالك يريد إصلاحه.

**السلوك الصحيح المُلزِم**:
1. **الإصلاح مسموح — في lineage جديدة** (artifact lineage_id جديد كلياً).
2. **dataset المكشوف لا يعود شاهداً نهائياً مستقلاً** لهذه lineage المعدَّلة (I-DR-3/4).
3. **يلزم evaluation protocol جديد قانوني** (dataset roles جديدة + preregistration جديد).
4. **لا إخفاء للفشل، لا حذف للنتيجة** — سجل النتيجة يبقى (I-ER-2).
5. تسمية الإصلاح «bugfix لا يؤثر» **غير مقبولة إلا بإثبات artifact-equivalence** (مقارنة old==new للمخرجات المتأثرة بنفس العقود — منهج EXACT PERFORMANCE المعتاد) إن أُريد الاحتفاظ بالشهادة — وإلا فـmodification كامل يعامل كـD1-DR-4.
- **I-FE-1**: أي final evaluation مُستخدم في تصميم النظام ⇒ `EXPOSED_INVALID_FOR_FINAL_SELECTION` + lineage جديدة إلزامية.
- **I-FE-2**: النتائج النهائية السالبة تُنشر في السجل كما هي (لا reporting انتقائي).

## D1-21) UPDATED BUILD ORDER (ينعكس على Annex B)

الترتيب الكامل في **Annex B**؛ الخلاصة الحاكمة هنا: S0→S3 عقود وبنية فقط؛ ثم **بوابة صريحة** (`SelectionBlockedError` دون objective+roles+authorization)؛ ثم development fit → development selection → freeze exact artifact family → final evaluation lock → frozen application → state graph/reality audit **بحسب dataset-role permissions**؛ ولاحقاً فقط: Dependence → Descriptor Registry → Estimand Catalog → Information Evaluation. **لا Model داخل هذا PATCH**. أي circular dependency بين المراحل ⇒ **STOP — OWNER REVIEW** ولا حل ارتجالي.

## D1-22) ADVERSARIAL DESIGN TEST MATRIX

الالتزام التصميمي: لكل هجوم في **Annex D** — contract violated + fixture concept + expected rejection/state + المكان الذي يجب أن يفشل فيه. لا كود الآن.

## D1-23) CERTIFICATION BOUNDARY

النص الحرفي في **Annex E** (نهاية الوثيقة).

---

# PART II — Annexes

## Annex A — UPDATED DEPENDENCY GRAPH

```
[A0] core schemas/invariants (§IMM/T3/FR/DAG/IK/IB) ── identity/append-only contracts
   │
[A1] path primitives · running factual descriptors · episode/transition/explanation schemas
   │        (bass: D1-5 process identity, D1-10 namespaces, D1-14 episode anchor)
   │
[A2] detector witness adapter (D1-4) — لا ترقية بلا policy authority
   │
[A3] PolicyArtifact infra · DatasetRoleArtifact · HumanReviewRecord ·
   │   Experiment Registry · ObjectiveArtifact contracts (D1-1/2/3/4/16) — لا fit
   │
[G0] GATE: لا Calibration حتى يوجد objective + dataset roles + owner authorization
   │
[A4] development fit (DEVELOPMENT_FIT roles فقط)
   │
[A5] development selection / representation competition (DEVELOPMENT_SELECTION فقط)
   │
[A6] freeze exact artifact family (objective-anchored)
   │
[A7] final evaluation lock (FINAL_EVALUATION_LOCKED — مرة واحدة)
   │
[A8] frozen application
   │
[A9] state graph / reality audit بحسب dataset-role permissions (D1-3)
   │
[A10] لاحقاً فقط: Dependence → Descriptor Registry → Estimand Catalog → Information Evaluation
   │
[A11] Model — فقط إذا مُفوَّض — خارج هذا PATCH
```

## Annex B — UPDATED BUILD ORDER (الصيغة الإلزامية)

- **S0** — core schemas/invariants + InformationKey bindings + identity/append-only contracts.
- **S1** — path primitives + running factual descriptors + episode/transition/explanation schemas.
- **S2** — detector witness adapter **فقط** (لا authoritative promotion بلا policy authority — I-PAUTH-4).
- **S3** — PolicyArtifact infrastructure + DatasetRoleArtifact + HumanReviewRecord + Experiment Registry + ObjectiveArtifact contracts — **لا fit**.
- **GATE** — **لا Calibration حتى توجد objective + dataset roles + owner authorization** (`SelectionBlockedError` وإلا).
- **S4** — development fit.
- **S5** — development selection / representation competition.
- **S6** — freeze exact artifact family.
- **S7** — final evaluation lock.
- **S8** — frozen application.
- **S9** — state graph / reality audit بحسب dataset-role permissions.
- **S10** — لاحقاً فقط: Dependence → Descriptor Registry → Estimand Catalog → Information Evaluation.
- **لا Model داخل هذا PATCH.** أي circular dependency ⇒ **STOP — OWNER REVIEW**.

## Annex C — INVARIANT INDEX

| المجموعة | الحصون |
|---|---|
| Objective Authority | I-OA-1..5 |
| Dataset Roles / Exposure | I-DR-1..5 |
| Human Review | I-HR-1..2 |
| Policy Authority | I-PAUTH-1..4 |
| Wave Identity | I-WID-1..3 |
| Scale≠Depth | I-SD-1..4 |
| DAG | I-DAG-X (+ cycle injection fail-closed + D1-7 البنود 1–5) |
| Cross-Representation | I-XR-1..3 |
| Running≠Final | I-RF-1..4 |
| InformationKey | I-IK-1..5 |
| Same Batch | I-IB-1 |
| Snapshot Closure | I-SC-1..4 |
| Episodes | I-EP-1..3 |
| Explanations | I-EXPL-1 (+ state whitelist) |
| Experiments | I-ER-1..5 |
| Estimand | I-EST-1 |
| Comparability | I-CMP-1..2 |
| Missingness | I-MSN-1 |
| Final Evaluation | I-FE-1..2 |
| الموروث من 37/36 (سارٍ) | I-IMM-1..4 · I-T3-1..2 · I-FR-1..3 · I-DE-1 · I-NW-1 · I-PA-1..2 · I-ST-1 · I-EX-1..2 · I-SH-1 · I-P-1 · I-BO-1 |

## Annex D — ADVERSARIAL DESIGN TEST MATRIX (24 هجوماً)

| # | الهجوم | العقد المُختلَق | مفهوم الـfixture | الرفض/الحالة المتوقعة | أين يفشل |
|---|---|---|---|---|---|
| 1 | policy witness بلا authority يحاول إنتاج factual TP | I-PAUTH-1/2 | witness record + استعلام factual surface | لا يظهر كـAuthoritative TP؛ الاستعلام factual يستبعده | D1-4 promotion gate |
| 2 | NOT_CONFIGURED policy يحاول إنتاج wave | I-PAUTH-4 / I-OA-1 | محاولة بناء hierarchy بلا PolicyArtifact | `SelectionBlocked/AuthorityMissing`؛ صفر factual waves | S2/S3 boundary |
| 3 | parent جديد يحاول تعديل depth القديمة | I-SD-1/2 | إضافة X⊃A⊃B بعد ختم B | depth query يُظهر 2؛ سجل B **بلا تغيير بايت واحد** | snapshot immutability test |
| 4 | α وβ نفس endpoints ويحاول النظام دمج الهوية | I-XR-1 | موجتان متطابقتان هندسياً في تمثيلين | لا اندماج؛ `GEOMETRICALLY_COINCIDENT` + مقارنة فقط | cross-rep registry |
| 5 | final descriptor يُقرأ قبل end confirmation | I-RF-1/4 | استعلام final namespace عند t<end | `FinalNotAvailable` + causality gate تكشف محاولة الاستبدال | D1-10 query gate |
| 6 | snapshot عند T يشير إلى fact عند T+1 | I-SC-1/3 | reference مُستقبلي خفي | **reject at construction** | snapshot builder |
| 7 | transitive future reference خلف episode | I-SC-1/EP-2 | episode بعضو مستقبلي | reject تراكبي (closure_verified يفشل) | closure verifier |
| 8 | cross-timeline relation | I-IK-1 | edge بين timeline_id مختلفين | reject | InformationKey binding |
| 9 | BAR_PRE_CLOSE يرى completed fact | I-IK-4 | استعلام completed-bar بـphase=BAR_PRE_CLOSE | مرئي فقط للأسطر المتاحة قانونياً — الرفض صريح | as-of visibility |
| 10 | sequence number يكسر same-batch tie | I-IK-5 / I-IB-1 | حدثان batch واحد يُرتَّبان بالـsequence | `same_information_batch_order_unknown=TRUE`؛ لا سلسلة زمنية | explanation/transition builders |
| 11 | member جديد يغير episode_id | I-EP-1 | إضافة عضو بعد creation | نفس episode_id؛ membership event جديد فقط | episode anchor hash |
| 12 | OOS chart review يؤثر في design ولا يبطل final status | I-HR-2 / I-DR-3 | HumanReviewRecord(final) + requested_changes | `EXPOSED_INVALID_FOR_FINAL_SELECTION` + lineage جديدة | review firewall |
| 13 | failed experiment يُحذف | I-ER-2/4 | محاولة إزالة سجل فشل | مرفوض (append-only registry) | experiment registry |
| 14 | objective يتغير مع بقاء experiment_id | I-ER-3 | نفس id بـobjective_hash مختلف | experiment جديد إلزامي | registry validation |
| 15 | horizon يُختار بعد رؤية evaluation | I-EST-1 | estimand مُسجَّل بعد النتيجة | `EVALUATION_WITHOUT_ESTIMAND` مرفوض | estimand ordering gate |
| 16 | ACTUAL missing يُستبدل PROXY صامتاً | I-MSN-1 / I-CMP-2 | snapshot بلا ACTUAL يُقارن كـCOMPARABLE مع ACTUAL | `NOT_COMPARABLE(AVAILABILITY_MASK_DIFFERS)` | comparability checker |
| 17 | δ containment يُسمى market importance | D1-8 ممنوعات | label على hierarchy δ | رفض العقد (تسمية غير مُصرَّحة) | representation spec validator |
| 18 | cycle injection | I-DAG-X / D1-7 | حافة A⊃B⊃A يدوياً | `cycle_injection_rejected` عند الإدراج | edge insertion gate |
| 19 | zero denominator | I-DE-1 | path_length=0 / activity=0 | `UNDEFINED(reason)` — لا inf ولا epsilon | descriptor domain checker |
| 20 | fixed hidden window | I-NW-1 | نافذة ثابتة في كود/عقد | رفض بوابة boundaries-or-policy | window provenance gate |
| 21 | future append يغير state_at(T) | I-IMM-3 / I-SC-4 | hash(state_at(T)) قبل/بعد append | **byte-identical**؛ أي اختلاف = فشل | immutability battery |
| 22 | final evaluation يُعاد استخدامه بعد design modification | I-FE-1 / I-DR-4 | نفس dataset كـfinal لـlineage معدَّلة | مرفوض؛ lineage جديدة + protocol جديد | role firewall |
| 23 | comparison بين snapshots بعقود مختلفة تمر COMPARABLE | I-CMP-1 | policy_hash/schema مختلف | `NOT_COMPARABLE(reason)` | comparability checker |
| 24 | explanation pattern satisfaction يتحول probability/support | I-EXPL-1 | تقرير يذكر PROBABLE/SUPPORTED | رفض الحالة (whitelist) + رفض الأوزان | explanation state validator |

## Annex E — CERTIFICATION BOUNDARY (ختام حرفي)

هذا التصميم، حتى لو قُبل وبُني لاحقاً، لا يثبت:
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

**END — MUF-V1-FINAL-DESIGN-PATCH-D1. لا إجراء آخر.**

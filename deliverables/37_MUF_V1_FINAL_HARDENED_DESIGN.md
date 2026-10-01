# MARKET UNDERSTANDING FOUNDATION V1 — FINAL HARDENED DESIGN

**الحالة**: DESIGN ONLY — FINAL DESIGN HARDENING — لا كود، لا BUILD، لا quantile، لا model، لا strategy، لا PnL، لا توصية.
**الإصدار**: MUF-V1-FINAL-DESIGN-2026-09-29 (يُقوّي ويصحّح `36_MARKET_UNDERSTANDING_FOUNDATION_V1_MASTER_DESIGN.md`؛ حيث يختلف الاثنان **هذا هو المرجع**).
**القواعد الثابتة كما في 36 §0**: ZERO LOOKAHEAD، Origin≠Availability، لا repaint، لا chronology مخترعة، لا threshold سحري، CLOSED مقدسة، PROXY≠ACTUAL، FAIL CLOSED، لا «وعي/يقين».

---

## 1) IMMUTABILITY — سجلات فقط تُضاف، لا تُطلى (تصحيح 36 §2)

### 1.1 نموذج السجلات (Append-Only Ledger Model)
الماضي **byte-identical** تحت أي مستقبل قانوني = كل حقيقة تُكتب مرة واحدة في سجل غير قابل للتعديل، وكل تطور = سجل/حدث جديد بـ`available_at` خاص به:

| السجل | يُنشأ عند | المحتوى (immutable) |
|---|---|---|
| `turning_point_records` | `turning_point_available_at` | (candidate identity, extrema_type, origin_position/time, origin_price, available_position/time, scale_id, policy_id) |
| `wave_identity_records` | `wave_identity_available_at` | (wave_id, representation_id, scale_id, direction_as_known, start-side triple refs — §2) |
| `wave_formation_observations` | كل بار/حدث أثناء FORMING | لقطات running (extreme-so-far, displacement-so-far, path_length-so-far…) — كل لقطة تُكتب وتُنسى، لا تُحدَّث |
| `wave_end_records` | `wave_end_confirmed_available_at` | (end-side triple, end_price, final extreme facts, final measures) |
| `wave_status_events` | كل انتقال حالة | (wave_id, status, available_position, reason_ref) — الحالة الحالية = آخر حدث ≤ T |
| `wave_relation_events` | `relation_available_position` | (parent/child أو candidate relations — §3) |
| `supersession_events` | `supersession_available_position` | (target_wave_id, superseding_ref, reason) + حافة `superseded_by` **جديدة** |
| `causal_episode_records` | §9 | — |
| `state_snapshot_records` / `transition_records` | §10/§13 | — |

### 1.2 الحصون (Invariants)
- **I-IMM-1**: أي سجل مُنشَر لا يُعدَّل أبداً (يُفرض بقاعدة كتابة append-only + hash chaining للسجلات).
- **I-IMM-2 (SUPERSEDED لا يعدّل الماضي)**: supersession = `supersession_events` سطر جديد + `wave_status_events` سطر SUPERSEDED عند `available_at` الحدث — **صفر تعديل** على `wave_identity_records`/`wave_end_records` القديمة.
- **I-IMM-3 (Byte-identical past)**: `market_state_at(T) = pure_projection(records where available_at ≤ T)` — إضافة سجلات بـ`available_at > T` لا تغيّر البايتات: **اختبار صريح**: hash(state_at(T)) قبل إضافة مستقبل = بعده (bit-for-bit).
- **I-IMM-4**: أي رمز قراءة (queries) لا يخزن نسخاً قابلة للتحديث؛ الـsnapshots نفسها سجلات مُثبَّة بـhash.

---

## 2) THREE TIMES, NOT TWO (تصحيح 36 §2.1)

### 2.1 الأوقات الست
**البداية**:
1. `origin_start_{position,time}` — أين/متى وقع طرف البداية (extremum).
2. `turning_point_start_available_at` — متى صار الـturning point عند البداية **حقيقة معروفة** (تأكيد المرشح).
3. `wave_identity_available_at` — متى صارت **هوية هذه الموجة على هذه الدرجة** معروفة (علاقة الطرفين كموجة — ≠ معرفة الـTP وحده).

**النهاية**:
4. `origin_end_{position,time}` — أين وقع طرف النهاية.
5. `turning_point_end_available_at` — متى صار الـTP عند النهاية معروفاً.
6. `wave_end_confirmed_available_at` — متى صارت **نهاية الموجة كموجة** مؤكدة (قد تتأخر عن 5: معرفة أن القمة انعكست ≠ معرفة أنها أنهت موجة الدرجة k).

### 2.2 جدول القيم Null قبل كل مرحلة

| الحقول | قبل 2 | 2 ≤ t < 3 | 3 ≤ t < 5 | 5 ≤ t < 6 | بعد 6 |
|---|---|---|---|---|---|
| turning_point_record (start) | PENDING | موجود | موجود | موجود | موجود |
| `wave_identity_records` | — | — | يُنشأ | موجود | موجود |
| `origin_start_*` | في candidate فقط | في candidate | في السجل | ✓ | ✓ |
| `origin_end_*`, `end_price`, final measures | null | null | **null** | null | تُملأ في `wave_end_records` |
| `turning_point_end_available_at` | null | null | null | يُملأ عند وقوعه | ✓ |
| `wave_end_confirmed_available_at` | null | null | null | null | يُملأ |
| running descriptors | — | — | في `wave_formation_observations` فقط | تستمر | تُقفل |

### 2.3 الحسم
- **I-T3-1**: معرفة turning point **لا تعني** معرفة wave relation — الطبقتان منفصلتان بسجلين (`turning_point_records` vs `wave_identity_records`) وبوقتين منفصلين، واختبار صريح يثبت: تطبيق يرى TP عند t2 ولا يرى wave identity قبل t3.
- **I-T3-2**: `wave_identity_available_at ≥ turning_point_start_available_at` دائماً؛ `wave_end_confirmed_available_at ≥ turning_point_end_available_at` دائماً (أو يُوثَّق لماذا العكس مستحيل عقداً — والافتراض: التساوي أو التأخر).

---

## 3) FORMING RELATIONS — candidate ≠ factual (تصحيح 36 §2.3/§8)

- طبقتان منفصلتان تماماً:
  - `candidate_containment_edges` — كل حافة موسومة **`CANDIDATE_NOT_FACTUAL`**، خارج factual graph، ولا تُستعمل أبداً كدليل/استدلال.
  - `wave_relation_events` (factual) — تُنشأ عند `relation_available_position` عندما يتوفر الدليل (افتراضياً عند/بعد تأكيد نهاية الابن أو بديل موثّق بعقد).
- **I-FR-1**: لا parent نهائي (factual) لأي موجة FORMING قبل توفّر الدليل — الموجة الجارية تبقى بلا parent factual أو بـcandidate parent موسوم فقط.
- **I-FR-2**: العلاقة الفعلية تُثبَّت بسجل حدث جديد — لا تعديل لسجلات الأطراف.
- **I-FR-3**: استعلامات «market_state_at» factual **تتجاهل** candidate layer تماماً (سطحان: `factual_graph(T)` و`candidate_view(T)` منفصلان في المخرجات).

---

## 4) DAG — إسقاط ادعاء union-find (تصحيح 36 §8.3)

**التصحيح الصريح**: union-find كان لترتيب الفروع النشطة فقط — **إنه ليس ضماناً لعدم الدورة**. الضمان البنيوي:

- **I-DAG-1 (احتواء صارم)**: أي حافة factual `parent CONTAINS child` تتطلب:
  `parent.origin_start ≤ child.origin_start` **و** `child.origin_end ≤ parent.origin_end` **و** احتواءً صارماً للداخل (ليس نفس المدى)، **و** `child.scale_order < parent.scale_order` (الابن أدق)، **و** توفّر طرفي العلاقة عند `relation_available_position`.
- **I-DAG-2 (ترتيب جزئي)**: الاحتواء الصارم للمدى + تناهي درجة العمق = ترتيب جزئي؛ أي دورة A⊃B⊃A مستحيلة قياسياً (تناقص صارم لطول المدى أو للدرجة).
- **I-DAG-3 (اختبار حقن الدورة)**: بوابة صريحة `reject_cycle_injection` — محاولة إنشاء حافة تُغلق دورة (يدوياً أو بسجل مُعاد) تُرَدّ بـ`WaveHierarchyError("cycle_injection_rejected")` عند الإنشاء، **وليس** عند الاستعلام.
- التعادل (نفس المدى/نفس الطرف) = إخوة `ALTERNATES_WITH` فقط — لا أبوة (بمقتضى TIE_ORDER_CONTRACT).

---

## 5) DESCRIPTOR DOMAIN ERRORS (تصحيح 6.x من 36)

- كل ratio/normalization يُعرَّف بـ**semantics المقام صفر** — لا `inf`، لا epsilon:
  - القيمة إما finite float، أو `UNDEFINED(reason)` / `UNAVAILABLE(reason)` (typed missing مُطبَّع — نفس missing sentinel في hashing).
  - جدول الأسباب (enum مغلق): `ZERO_PATH_LENGTH`, `ZERO_DURATION`, `ZERO_ACTIVITY`, `ZERO_VOLATILITY`, `ZERO_REFERENCE_PRICE`, `MISSING_SOURCE`, `NOT_CONFIGURED`, `PENDING_AVAILABILITY`.
- أمثلة مُلزمة:
  - `efficiency = |disp|/path_length`: path_length=0 → `UNDEFINED(ZERO_PATH_LENGTH)` (0/0 رياضياً غير معرّف — لا يُصاغ 0 ولا 1).
  - `price_response_per_activity`: نشاط منفّذ=0 → `UNDEFINED(ZERO_ACTIVITY)`.
  - `volatility_adjusted_displacement`: realized vol=0 → `UNDEFINED(ZERO_VOLATILITY)`.
  - `retracement_ratio` بلا حركة أصل → `UNDEFINED(ZERO_PATH_LENGTH)`.
- **I-DE-1**: كل descriptor ratio في السجل يرافقه `*_denom_status` (OK | UNDEFINED(reason) | UNAVAILABLE(reason)) — الاختبار البطّي يحقن كل مقام=0 ويستلم السبب، ويستلم رفض inf/NaN صراحة.

---

## 6) NO HIDDEN WINDOWS (تصحيح 6.1/6.2 من 36)

- **حُذف**: كل نافذة left-anchored بطول ثابت غير مشتقة («نوافذ سرعة»، «acceleration windows»، «time_symmetry windows» كما وردت نصاً في 36 §6.1/§6.2).
- **المسموح فقط** (لكل نافذة في أي descriptor):
  1. **wave-boundary-derived**: من `origin_start` حتى الحد الجاري، أو بين حدود بنيوية مؤكدة (m-wave/segment boundaries)؛
  2. **policy-artifact-derived**: طول النافذة parameter داخل `PolicyArtifact` مُثبَّت بـhash؛
  3. **NOT_CONFIGURED**.
- إعادة تعريف صريحة:
  - `acceleration_desc` = فرق `velocity` بين مقطعين متجاورين **مشتقَّين من حدود موجة/segment مؤكدة** (لا طول سحري).
  - `speed_profile` = دالة على أشرطة الموجة نفسها (طولها = عمر الموجة) — لا نافذة خارجية.
  - `persistence`, `time_symmetry`, `roughness` = فوق مدى الموجة/الـsegment نفسه.
- **I-NW-1**: بوابة AST/عقد تمنع ثوابت نوافذ في الشيفرة؛ أي طول يجب أن يُقرأ من boundaries أو من policy artifact hash.

---

## 7) POLICY/CALIBRATION DEPENDENCY + تصحيح BUILD READY (تصحيح 36 §19/§20)

### 7.1 عقد `PolicyArtifact` (المُجمَّد)
```
PolicyArtifact {
  policy_id, policy_hash,
  training_dataset_identity,     # بصمات بيانات TRAIN (dataset + sidecar hashes)
  train_cutoff,                  # position/time — لا شيء بعد هذا في الفِت
  representation_hypothesis,     # α | β | γ | δ (§8)
  parameters,                    # typed map (reversal fractions, persistence, window lengths…)
  fit_code_version, fit_code_hash,
  freeze_time,                   # زمن التجميد — قبل أي OOS application
  scope,                         # market/timeframe/representation_id المطبَّق عليها
  no_oos_refit = TRUE            # أي refit = artifact جديد بـid/hash جديد — لا نسخة «مُحدَّثة»
}
```
- **I-PA-1**: أي تطبيق policy يحمل `policy_hash` في كل سجل ناتج.
- **I-PA-2**: pipeline الفِت يرفض بيانات بعد `train_cutoff` (اختبار: حقن bar بعد cutoff → رفض).

### 7.2 BUILD READY المُصحَّح (صدق)
| المكوّن | الحالة الحقيقية |
|---|---|
| S0 عقود + schemas | **BUILD READY** (بلا أي calibration) |
| S1 path primitives (A) + episode/transitions/explanation **schemas** | **BUILD READY** — factual خالص، لا يعتمد hierarchy مؤكدة |
| S2 turning-point lattice — طبقة witness-0 (استهلاك 2.1A كما هو بأي policy مُدخَل/NOT_CONFIGURED) | **BUILD READY كمستهلك** |
| S2+ lattice درجات إضافية | **CONTRACT-ONLY / NOT_CONFIGURED** — تنتظر `PolicyArtifact` |
| S3–S6 hierarchy/market-populated | **لا تُبنى** قبل حل مصدر الـpolicy (إما contract-only أو بعد TRAIN artifacts) |
| الباقي (S7+) | كما في §17 أدناه |

**ممنوع صراحة**: ادعاء BUILD READY لأي hierarchy مأهولة بالسوق قبل وجود مصدر الـpolicy.

---

## 8) CONTINUOUS/MULTISCALE — عائلات متنافسة + عائلة δ (تصحيح 36 §4/§5)

تبقى **α (Scale-Indexed Policies)**، **β (Persistence-Continuous Nesting)**، **γ (Recursive Anchored Segmentation)** — لا quantile واحد لكل scale مفترضاً. وتُضاف:

**δ — Event-Anchored Containment Closure** (بلا K مقدس، بلا recursion على المسار):
- policy تأكيد **واحد** (ليس per-scale) ينتج مرشحين مؤكدين؛ كل segment بين TP مؤكد = موجة level-0.
- الدرجات العليا **تنبع** من closure الاحتواء: كلما ثبتت سلسلة احتواء صارمة (بقواعد §4) لـsegments متجاورة، أُنشئت موجة أب **بحدودها هي** (أصغر مدى يحتوي أبناءه) — العمق يخرج من البيانات، وK = عمق الاحتواء المحقق فعلاً.
- سببية ✓ (تُبنى بعد تأكيد الأبناء بأحداث relation)، تنفيذية O(n amortized) ✓ (§16).

| العائلة | تحتاج من Calibration |
|---|---|
| α | K + parameter لكل policy درجة |
| β | دالة persistence→confirmation mapping |
| γ | عمق recursion + policies لكل عمق |
| δ | parameters الـpolicy الواحد فقط (قواعد الاحتواء/التناوب **بنيوية** لا تُضبط) |

الاختيار بين العائلات: TRAIN فقط (§17) — لا بالجمال البصري.

---

## 9) CAUSAL EPISODE / DEPENDENCE GRAPH (طبقة جديدة)

```
CausalEpisodeRecord {
  episode_id,                      # hash(origin-anchored production path)
  origin_{position,time}, available_at,
  source_wave_id / source_event_ref,
  member_evidence_ids[], member_entity_ids[],   # FVG/BOS/flow windows/… أُنتجت من نفس المسار
  derivation_ancestry[],           # episode_ids أبوية
  status ∈ {FORMING, ESTABLISHED, SUPERSEDED}
}
```
- **الهدف**: منع العد الساذج — `FVG + BOS + burst تدفق` إذا نتجت من episode واحد **ليست ثلاثة أدلة مستقلة**؛ أي counting/stacking لاحق يجب أن يمر بحساب العضوية.
- **تحذير صريح ملزم في كل استخدام**: هذا **accounting/conservative dependence representation فقط** — لا ادعاء statistical independence ولا dependence إحصائية.
- **الربط بـRESEARCH-DEBT-024**: يبقى **OPEN** حتى الإثبات الإحصائي لل independence/dependence؛ طبقة الـepisodes هي المحاسبة المحفوظة التي سيخدمها ذلك الإثبات لاحقاً — ولا تُغلق الدين.
- العضوية تُسجَّل عند availability كل عضو (append) — لا تعديل؛ الانتماء لاحق = حدث `episode_membership_event` جديد.

---

## 10) STATE TRANSITIONS

```
MarketStateTransitionRecord {
  transition_id, from_snapshot_id, to_snapshot_id, available_at,
  changed_fields[],       # literal state variables
  changed_relations[],    # علاقات graph تغيرت factual
  change_kind ∈ {FACTUAL_STATE_TRANSITION, DESCRIPTOR_DELTA},
  direction_of_change     # e.g. stable→expanding, forming→confirmed, aligned→conflicted
}
```
- أمثلة المالك مطبَّقة هكذا: `volatility stable→expanding` = **FACTUAL_STATE_TRANSITION** فقط إذا كان لمتغير الحالة volatility تعريف state machine بحدود policy-artifact أو بنيوية؛ وإلا يُسجَّل **DESCRIPTOR_DELTA** (فرق عددي factual بلا ادعاء نظام).
- `wave state forming→confirmed` = literal (من `wave_status_events`)؛ `structure aligned→conflicted` = literal من حالة relations المُعلَنة؛ `flow regime descriptor changed` = descriptor delta إن لا يوجد regime contract.
- **I-ST-1**: لا threshold ذوقي في أي transition — إما انتقال حالة مُعرَّف عقداً أو delta عددي فقط.

---

## 11) COMPETING EXPLANATIONS (طبقة فوق graph — قبل أي predictive model)

```
ExplanationRecord {
  explanation_id,
  explanation_type ∈ {PARENT_TREND_RETRACEMENT_LIKE,
                      LARGER_REVERSAL_CANDIDATE,
                      RANGE_CONTINUATION_LIKE, ...},   # أسماء وصفية إجرائية — ليست market truth
  creation_availability,
  required_factual_relations[],   # نمط علاقات في graph يجب أن يبقى متحققاً
  supporting_facts[], opposing_facts[], contradicting_facts[], missing_facts[],
  state ∈ {MONITORING, CONTRADICTED, SUPERSEDED, FACTUALLY_ESTABLISHED_WHERE_POSSIBLE}
}
```
- **ممنوع**: probability، weights، score، أي «دعم تنبؤي» قبل المعايرة. الانتقال بين الحالات يبدأ فقط من presence/absence علاقات factuale (مخالفة required relation ⇒ CONTRADICTED…).
- **إعادة استخدام 6.1B (narrative) — لا محرك موازٍ**: المحرك الحالي (`decision/narrative.py` — فرضيات/علاقات/حالات) **يبقى المصدر الفعلي الوحيد** لـhypothesis/relationship facts. طبقة الـExplanations = **registry أنماط graph + state bookkeeping تشير إلى** `hypothesis_id`/`relationship_id`/`wave_id`/`episode_id` موجودة — ممنوع إعادة اشتقاق فرضية أو علاقة داخل الطبقة (عقد `explanation_required_facts` = مراجع فقط). أي توافق لاحق مع predictive model خارج هذا التصميم.

---

## 12) EXPECTATION / SURPRISE CONTRACT (عقود فقط)

```
ExpectationArtifact { expectation_id, policy_hash/model_artifact_hash, TRAIN-only provenance, scope }
ObservedResponseRecord { observation window (wave-boundary/policy-derived), factual response }
ExpectationViolationRecord {
  violation_id, expectation_id, observed_response_id, available_at,
  violation_kind ∈ {DIRECTIONAL, MAGNITUDE_BAND, TIMING_BAND, ...}  # تُعرَّف داخل ExpectationArtifact
}
```
- **I-EX-1**: لا `ExpectationViolationRecord` إطلاقاً دون `ExpectationArtifact` مُجمَّد (TRAIN-only).
- **I-EX-2**: ممنوع expected move مكتوب بخط اليد؛ ممنوع توليد expectation من شهادات CLOSED الحالية (وإنما من نموذج تاريخي مُجمَّد لاحقاً فقط).
- لا تنفيذ الآن.

---

## 13) STATE HISTORY (تصحيح 36 §9)

- `StateSnapshotRecord` يحمل مراجع تاريخ محدودة **بالأحداث** لا بالنوافذ:
  - `recent_episode_refs[]` — آخر episodes حتى حد structure/episode boundary (لا «آخر 20 شمعة»).
  - `wave_ancestry_refs[]` — سلسلة الآباء حتى الجذر.
  - `recent_transition_refs[]` — حتى آخر transition boundary.
- **I-SH-1**: حدود التاريخ تأتي إما من **structural/event boundaries** (آخر m حدث بنية/حلقة — m بنيوي أو policy-artifact) أو من policy artifact hash — ولا يُكتب ثابت `last N bars` في أي كود.
- comparability contract (J) يشمل `history_boundary_kind` + `history_boundary_ref` — snapshots بحدود مختلفة **NOT_COMPARABLE**.

---

## 14) HUMAN CHART (تكملة 36 §13)

السطح الإلزامي لكل timestamp: كل الـhierarchies معاً (toggle حسب الدرجة) + start/end للموجة + **forming endpoint مفتوح/متقطع** + ثلاثة أوقات صريحة على كل مرسوم: **origin time | turning-point-known time | wave-relation-known time** (الأطراف الثلاثة من §2) + روابط parent/children + causal episodes (تلوين/إطار يجمع أعضاء الحلقة) + structure لكل scale + روابط FVG/OB/liquidity/range + **flow actual/proxy في لوحين منفصلين** + state transitions (شارات) + competing explanations (لوحة جانبية بحالتها MONITORING/CONTRADICTED/…). الهدف: audit بصري كامل للنظام نفسه.

---

## 15) DETECTION REALITY AUDIT (تصحيح 11 من 36)

- **حجم العينة**: parameter مالك موثق **غير مقدس** (أو لاحقاً قوة إحصائية/مُتعلَم) — **لا رقم تعسفي مثل 24**.
- الاختيار يبقى deterministic **قبل رؤية أي output** (seed منشور مسبقاً في audit manifest).
- **Stratification قانونية لا ترى detector outcomes**:
  - **time coverage** (شرائح زمنية متساوية/مُعلَنة)،
  - **source volatility context مُعرَف مسبقاً**: trailing volatility **تنتهي قبل بداية** نافذة العينة (لا يُشتق من داخل العينة ولا من outputs) — يُستخدم مصدر volatility الخام/المعلن فقط.
- باقي العقد كما في 36 §11 (chart context + known-at times + نسبة مطابقة كما هي).

---

## 16) PERFORMANCE (تصحيح 14 من 36)

| الطبقة | Worst-case | Amortized | ملاحظة |
|---|---|---|---|
| path primitives | O(n) | O(1)/bar | تجميعات تدفقية |
| turning-point lattice (K سياستات) | O(Kn) | O(n)/policy | stacks |
| wave nesting + relation events | O(n log n) (ترتيب) | O(1)/event | §4 invariants عند الإدراج |
| descriptors (بلا نوافذ مخفية) | O(n·D) حيث D=#descriptors | O(D)/bar | — |
| containment closure (δ) | O(n log n) | O(n) | فهرس boundaries + stack |
| state graph + as-of | O(n + q·m) | O(1)/event, O(m)/query | فهرس position |
| episodes | O(n·e_max) | O(1)/membership | e_max أعضاء الحلقة |
| γ recursion | **مُقيَّد**: على segment summaries بفهرس حدود مُحدَّث incrementally — O(D·n)، D محدود العقد | — | **وإلا PERFORMANCE BLOCKER مُعلن** |

- **ممنوع**: recursion يعيد قراءة مسارات خام O(n²).
- **I-P-1**: أي خوارزمية تُرفق بـworst/amortized عند التنفيذ؛ benchmark مليون bar إلزامي (S-bench)؛ cache لا يُغني عن تعقيد سيئ.

---

## 17) BUILD ORDER FINAL (تصحيح 36 §20 — صادق)

1. **S0** — العقود النهائية (schemas + invariants + gates) — بلا calibration.
2. **S1** — path primitives + descriptor domain rules (§5/§6) + `CausalEpisodeRecord`/`MarketStateTransitionRecord`/`ExplanationRecord` **schemas** — factual خالص.
3. **S2** — turning-point lattice **witness-0 فقط** (استهلاك 2.1A كما هو) + candidate layer.
4. **S3** — policy artifact infrastructure (schema + freeze/apply pipeline + NO OOS refit enforcement) — بلا fit.
5. **S4** — **TRAIN-only calibration** (عند توفّر بيانات TRAIN + مصادقة المالك) → `PolicyArtifact` مُجمَّد.
6. **S5** — بناء المنافسة α/β/γ/δ **على TRAIN** فقط (fit + معايير TRAIN).
7. **S6** — **FREEZE** عائلة الـhierarchy بقرار مالك على أدلّة TRAIN.
8. **S7** — تطبيق OOS hierarchy بالـartifacts المجمّدة — **OOS لا يشارك في أي اختيار إطلاقاً**.
9. **S8** — State Graph كامل + Reality Audit (على الـhierarchy المجمّدة).
10. **S9** — Information Edge Gate (عقد ثم لاحقاً تنفيذ) + human surface.
11. **S-bench** — موازية لأي S يُبنى (مليون bar لكل طبقة).

**I-BO-1**: لا مرحلة متأخرة تُبنى قبل اكتمال سابقتها؛ لا OOS في الاختيار؛ لا ترقيع نكشة نكشة.

---

## 18) PROJECT INTERACTION (تصحيح 16 من 36)

| الفئة | التفاصيل |
|---|---|
| **يُعاد استخدامه من CLOSED (public API فقط)** | 2.1A swing detector + policies protocol, swing_sequence classifier, structural_breaks, liquidity_map, fvg, order_blocks, dealing_range, causal_htf, dynamic_volatility, session_context, volume_delta/absorption, evidence_vector, narrative (6.1B — المصدر الفعلي الوحيد للفرضيات/العلاقات), information_time, visibility, research/hashing, dataset/eligibility/outcome contracts |
| **يُبنى جديداً** | `trading_system/market_understanding/` (نفس خطة 36 §16.1 + `episodes.py`, `transitions.py`, `explanations.py`, `expectation_contract.py` (عقود), `policy_artifacts.py`) |
| **يحتاج PATCH حقيقي** | لا شيء متوقع للـcore؛ المرشحون المؤجَّلون (قراءة counters أثناء التشغيل من policies إن تعذّر API العام) — يمر ببوابة old==new المعتادة |
| **ممنوع** | استيراد private symbols من CLOSED — بوابة AST (على نهج حارس field_runner) تسمح فقط بالأسماء العامة المُعلَنة لكل module؛ أي كسر = أحمر |

---

## 19) النموذج النهائي المضغوط (Schema Summary)

```
turning_point_records      (origin, available)            immutable
wave_identity_records      (triple_start, direction_as_known, scale, policy_hash)
wave_formation_observations(running facts per bar/event)  immutable rows
wave_end_records           (triple_end, final facts)
wave_status_events         (status transitions)           append
wave_relation_events       (factual parent/child)         append — §3/§4 invariants
candidate_containment_edges (CANDIDATE_NOT_FACTUAL)       خارج factual graph
supersession_events        append — لا تعديل ماضٍ
causal_episode_records + membership_events                §9 — debt-024 OPEN
state_snapshot_records     (history refs بالأحداث)         §13
state_transition_records   §10
explanation_records        §11 — فوق narrative facts
policy_artifacts           §7 — TRAIN-only, NO OOS refit
expectation artifacts/records                             §12 — عقود فقط
external_source_specs      §K — NOT_CONFIGURED
```

**الحصون المدمجة**: I-IMM-1..4 | I-T3-1..2 | I-FR-1..3 | I-DAG-1..3 | I-DE-1 | I-NW-1 | I-PA-1..2 | I-ST-1 | I-EX-1..2 | I-SH-1 | I-P-1 | I-BO-1.

---

## 20) BLOCKERS (مُحدَّثة)

1. مصدر الـpolicy غير محلول (TRAIN artifacts) → S2+/S3+ المتقدمة متوقفة/contract-only.
2. بيانات TRAIN/OOS cutoffs تحتاج مصادقة المالك قبل S4–S7.
3. RESEARCH-DEBT-024 (والـ020..025) تبقى OPEN — episodes لا تُغلقها.
4. external context (dominance…) NOT_CONFIGURED — لا بيانات.
5. γ recursion يحتاج تحقق الفهرسة التدفقية في S-bench وإلا PERFORMANCE BLOCKER.
6. بيانات المالك للتشغيل الحقيقي (جهازه فقط).

## 21) OUT OF SCOPE (مُحدَّث)

لا كود ولا BUILD الآن | لا quantile/parameter مختار | لا model/strategy/PnL/توصية | لا probability/weights/score للـexplanations | لا expectation دون frozen artifact | لا statistical independence claim (debt-024) | لا narrative engine موازٍ | لا OOS في اختيار hierarchy | لا ادعاء «وعي/يقين» | لا تعديل CLOSED | لا REAL_WAVE/FAKE_WAVE | لا Reality analysis.

---

**END — MUF-V1-FINAL-DESIGN. لا إجراء آخر.**

# MARKET UNDERSTANDING FOUNDATION V1 — CONSOLIDATED MASTER DESIGN

**الحالة**: DESIGN ONLY — MASTER AUTHORIZATION — لا BUILD، لا quantile مُختار، لا model، لا strategy، لا PnL، لا توصية.
**الإصدار**: MUF-V1-DESIGN-2026-09-29
**النطاق**: تمثيل سببي متكامل للشارت كحركات/موجات متداخلة متعددة المقاييس — قاعدة فهم سوق **قبل** أي predictive model أو strategy.

---

## 0) الدستور (مُلزِم لكل سطر في هذا التصميم)

1. **ZERO LOOKAHEAD** — لا descriptor ولا كيان ولا حدث يقرأ ما بعد availability bar.
2. **Origin ≠ Availability** — كل turning point يحمل `origin_position/time` **و** `confirmation/availability_position/time` منفصلين (هذا موجود أصلاً في 2.1A: «A candidate has an origin position where its current extreme occurred. A confirmed swing becomes visible only on the later confirmation row» — نعممه على كل الكيانات).
3. **الحركة الجارية لا تأخذ terminal endpoint مؤكداً قبل توفره** — `end_price/end_position = null` أثناء FORMING.
4. **لا chronology داخلية مخترعة داخل الشمعة** — TIE_ORDER_CONTRACT = NOT_PROVEN؛ التعادل يبقى تعادلاً.
5. **لا repaint / لا zigzag يعيد طلاء الماضي / لا centered windows / لا future extrema**.
6. **لا threshold سحري** — أي parameter: (أ) بنيوي رياضي، (ب) عقد factual، (ج) مُتعلَّم على TRAIN ومُجمَّد ومُثبَّت بـhash، أو (د) **NOT_CONFIGURED**. لا fixed 1% / 20 bars / ATR multiple بلا مصدر.
7. **المخرجات CLOSED لا تُعاد كتابتها خلسة** — أي PATCH حقيقي يُذكر صراحة ويمر ببوابة old==new.
8. **لا تسويق «فهم» كوعي أو يقين** (القسم R).
9. **PROXY و ACTUAL لا يُجمعان في رقم واحد** — في كل descriptor وكل context.
10. **FAIL CLOSED** — أي غياب مصدر/معلمة = NOT_CONFIGURED/missingness مُعلَن، لا اختراع.

---

## 1) مخطط المعمارية (نصي)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  GATES (لا تُبنى إلا بعقودها):                                           │
│  [L] Detection Reality Audit   [M] Competing Representations            │
│  [N] TRAIN-only Calibration    [O] Information Edge Gate                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲ تُختبَر فوق فقط
┌─────────────────────────────────────────────────────────────────────────┐
│  P/H  Human Chart Surface  — كل marker يحمل origin-time + known-at-time  │
├─────────────────────────────────────────────────────────────────────────┤
│  J   State Snapshot / Analogs (contract-ready)   K External Context      │
│      (استرجاع حالات متشابهة تاريخياً — بلا future labels)   Registry     │
├─────────────────────────────────────────────────────────────────────────┤
│  I   MARKET STATE GRAPH — nodes/edges — as-of extraction عند كل T        │
├─────────────────────────────────────────────────────────────────────────┤
│  G   LIQUIDITY IN CONTEXT      H   FVG / OB / DEALING RANGE IN CONTEXT  │
│      (كيانات + lifecycle +         (ربط الكيانات CLOSED بموجاتها:         │
│       scale context)                 created_by / inside / tested_by)   │
├─────────────────────────────────────────────────────────────────────────┤
│  F   MULTISCALE STRUCTURE — HH/HL/LH/LL و BOS/CHoCH مربوطة بـscale_id    │
│      (Micro/Local/Major = أسماء لدرجات تمثيل — لا مقاييس مقدسة)          │
├─────────────────────────────────────────────────────────────────────────┤
│  E   IMPULSE/RETRACTION/RANGE DESCRIPTORS — factual، لا labels ذوقية     │
├─────────────────────────────────────────────────────────────────────────┤
│  C   WAVE ENTITY + D NESTING/FRACTAL — موجات متداخلة متعددة الدرجات      │
├─────────────────────────────────────────────────────────────────────────┤
│  B   CAUSAL TURNING-POINT LATTICE — مرشحون متعددون، كل pivot:           │
│      origin + availability، لا repaint، لا scale مقدس                     │
├─────────────────────────────────────────────────────────────────────────┤
│  A   PRICE PATH PRIMITIVES — وقائع حركية أولية لكل segment قانوني        │
├─────────────────────────────────────────────────────────────────────────┤
│  L0  CLOSED WITNESSES (تبقى كما هي — أدلاء تشغيلية لا تُعاد كتابتها):    │
│      sources cross-witness | timeline/InformationKey | volatility |     │
│      sessions | swing 2.1A + EmpiricalConfirmationPolicy | sequence |   │
│      structural breaks | liquidity | FVG | OB | dealing range | HTF |   │
│      executed flow (PROXY/ACTUAL) | evidence | narrative | visibility   │
└─────────────────────────────────────────────────────────────────────────┘
```

**قاعدة الانسياب**: كل طبقة تقرأ فقط ما هو **متاح وقتها** (InformationKey / visibility as-of). كل كيان في الأعلى يُشتق من شهادات الأسفل + descriptors جديدة — لا يُغيّر مخرجاتها.

---

## 2) كيان Wave الرسمي (C)

### 2.1 السجل `WaveRecord` (حقول إلزامية)

| المجموعة | الحقول | القاعدة |
|---|---|---|
| الهوية | `wave_id`, `representation_id`, `scale_id`, `wave_version` | `wave_id = canonical_sha256(domain="MUF_WAVE_V1", payload={representation_id, scale_id, anchor_identity})` — deterministic بلا أرقام عشوائية |
| الزمن (origin/availability) | `origin_start_position`, `origin_start_time`, `available_start_position`, `available_start_time`, `origin_end_position?`, `origin_end_time?`, `available_end_position?`, `available_end_time?` | `available_* ≥ origin_*` دائماً؛ `*_end` = **null** أثناء FORMING |
| الاتجاه | `direction` ∈ {UP, DOWN, FLAT_UNRESOLVED} | FLAT حالة وصفية قانونية — لا إجبار على اتجاه |
| الأسعار | `start_price`, `end_price?`, `extreme_price`, `extreme_position`, `extreme_available_position` | extreme = حقيقة وقعت عند origin؛ إعلانها المؤكد عند availability |
| القياسات | `amplitude`, `duration_bars`, `path_length`, `efficiency`, `velocity_mean`, `acceleration_desc`, `retracement_ratio`, `volatility_context`, `roughness` | كلها descriptors — القسم 6 |
| التدفق | `flow_context` = {proxy: {...}, actual: {...}} **منفصلان** | من executed-flow sources فقط؛ لا ضغط شراء ولا institutional |
| البنية | `structural_consequences[]` = مراجع أحداث BOS/CHoCH المنسوبة لهذه الموجة | مراجع فقط — الأحداث تبقى ملك CLOSED |
| النسب | عبر جدول حواف (القسم 2.3) | لا قوائم متداخلة |
| الأصل | `provenance` = {source_hashes, engine_versions, policy_hash?} | + `record_hash` فوق كامل السجل |
| الحالة | `status` ∈ {FORMING, CONFIRMED, SUPERSEDED} | انظر 2.2 |

### 2.2 دلالات الحالة (غير مستقبلية مطلقاً)

- **FORMING**: الطرف النهايي لم يتوفر بعد — `end_* = null`، ولا يدخل في أي «سطح مؤكد factual» إلا كـforming state.
- **CONFIRMED**: `available_end` تحقق (بحسب سياسة التأكيد المجمّدة) — يدخل السطح المؤكد **من ذلك البار فصاعداً**، مع الاحتفاظ بأصله الأقدم.
- **SUPERSEDED**: موجة لاحقة/سياسة أعمق أعادت تثبيت البنية على نفس المدى — **تُشطب من السطح النشط ولا تُمحى** (edge `superseded_by`).
- ممنوعات صريحة: لا `WILL_CONFIRM`، لا `INVALIDATED_BY_FUTURE`، لا إعادة تسمية ماضية.

### 2.3 النسب — جدول حواف مُطبَّع (D)

```
wave_edges(parent_wave_id, child_wave_id, edge_type, edge_available_position)
edge_type ∈ {CONTAINS, OVERLAPS_CANDIDATE, SUPERSEDES, ALTERNATES_WITH}
```

- العمق غير محدود: **عدد الدرجات ينبع من البيانات** (انظر 4)، لا hard-code «3 مستويات».
- كل حافة تأخذ `edge_available_position` = أول بار حيث العلاقة كانت قابلة للإثبات — لا علاقة تُعلَن قبل أن تصبح حقيقة.

### 2.4 التمثيل المادي
جدولا `waves` + `wave_edges` (normalized) + `wave_descriptors` (Wide أو EAV مُطبَّع) — قابل للـstreaming و million-bars (القسم 14). الـhash لكل سجل عبر `research/hashing.py` (CANONICAL_SHA256_V1 — بعد PATCH-4 أسرع بـbyte-identical).

---

## 3) مرشحات Turning-Point السببية (B)

### 3.1 المرشح `TurningPointCandidate`

```
(candidate_id, scale_id, extrema_type ∈ {HIGH, LOW},
 origin_position, origin_price,
 available_position?, available_price,
 status ∈ {PENDING, CONFIRMED, SUPERSEDED, UNCONFIRMED_UNKNOWN})
```

- **PENDING**: أصله معروف، تأكيده غير متاح — خارج factual confirmed surface.
- **UNCONFIRMED_UNKNOWN**: بقي معلقاً إلى الأبد (نهاية البيانات/السياسة) — يبقى كذلك؛ لا يُصاغ كمؤكد ولا كمرفوض.
- المرشح عند تعادل قيمتين (equal highs/lows): مرشحان بـoriginين منفصلين وعلاقة `ALTERNATES_WITH` — لا أولوية مخترعة (TIE_ORDER_CONTRACT).

### 3.2 ما يُعاد استخدامه من العقود الحالية (2.1A + EmpiricalConfirmationPolicy)

| الموجود | إعادة الاستخدام |
|---|---|
| نمط candidate → confirmation مع فصل origin/confirmation rows | **القلب reusable كما هو** — MUF يعمّمه على كل درجات المرشحات |
| `SwingConfirmationPolicy` protocol (`assess(reversal_fraction)`, episodes, priors) | **واجهة السياسة لكل scale** — كل درجة = policy instance مستقلة |
| `EmpiricalConfirmationPolicy` (priors, continuation/confirmed episodes) | المرشح **للتعميم** — حالياً سياسة واحدة؛ التصميم يسمح K سياسات (الكل NOT_CONFIGURED حتى N) |
| `ConfirmedSwingSequenceEngine._classification` (HH/HL/LH/LL) | **witness قابل لإعادة الاستخدام** كـclassifier فوق أي sequence مرتبة (القسم F) |
| `CausalStructuralBreakEngine` (BOS_UP/CHoCH_UP/... بالاعتماد على close) | يبقى CLOSED witness؛ الطبقة الجديدة **تربط** أحداثه بالدرجات فقط |

### 3.3 ما يحتاج طبقة Descriptor جديدة
ربط المرشحين بـpath primitives (A)، مقاييس الكفاءة/السرعة، retracement relations، وسياق التقلب/التدفق — كلها خارج 2.1A اليوم.

### 3.4 ما يحتاج Calibration لاحقاً (ولا يُحسم الآن)
معلمات التأكيد لكل درجة (الشكل الحالي `swing_quantile` NOT_CONFIGURED مالك) — مسار القسم N.

### 3.5 منع إعادة الرسم (صيغة قابلة للاختبار)
لكل pivot معلن عند bar `t`: `available_position ≥ origin_position`، والقيمة المُعلَنة عند `t` مطابقة bit-for-bit لما ستبقى عليه عند أي `t' > t` (اختبار prefix-truncation + future-append في T). أي خرق = فشل البوابة.

---

## 4) بدائل بناء التدرج (C/D) — لا اختيار الآن

**الفرضية α — Scale-Indexed Policies**: درجات ثابتة العدد تُعرَّف بسياسات تأكيد متتالية الأصرار (persistence thresholds من TRAIN). بسيطة، O(Kn)، لكنها تفرض K مسبقاً.

**الفرضية β — Persistence-Continuous Nesting**: لا K؛ الموجات تتشكل بأصل extremum وتُؤكد بـreversal-fraction مستمر؛ التدرج ينبع من الاحتواء الزمني للـsegments المؤكدة (interval nesting على stack). درجات «تظهر» عندما تثبت البيانات segments متداخلة. أقرب لـ«ينبع من البيانات»، لكن مفهوم «الدرجة» يصبح نسبياً.

**الفرضية γ — Recursive Anchored Segmentation**: بعد تأكيد موجة، تُعاد قراءة مسارها الداخلي بنفس السياسة (recursion محدود العمق بـmax_depth بنيوي) — fractal صريح، لكن كلفة أعلى وتكرار محسوب مسبقاً.

**المشترك إلزامياً**: كلها causal، كلها origin/availability، كلها تنتج نفس `WaveRecord`. **القرار يؤجَّل إلى [M]+[N]** (منافسة + TRAIN). «Micro/Local/Major» في كل مكان = أسماء مستعار لدرجات `scale_id = 0..K-1` أو لأوائل ثلاثة ترتيبات — **لا ثوابت مقدسة في الكود** (تُمرَّر كـ`scale_labels` metadata).

---

## 5) إطار التمثيلات المتنافسة (M)

```
RepresentationSpec {
  representation_id      # hash كامل المواصفة
  hierarchy_hypothesis   # α | β | γ | …
  policy_bindings        # لكل scale: policy artifact hash أو NOT_CONFIGURED
  descriptor_set_version
  nesting_rules_version
  causal_guarantees      # شهادات: no-repaint, origin/availability, tie handling
}
```

- كل تمثيل يمر ببوابات T السببية قبل أن يشارك.
- التقييم اللاحق **TRAIN/OOS فقط** بمحك معلوم (information edge — O) — **لا اختيار لأن تمثيلاً «أجمل بصرياً»**.
- السجلات تحمل `representation_id` دائماً؛ أي مقارنة تاريخية (J) تتم فقط داخل نفس التمثيل أو عبر جدول ترجمة مُعلن.

---

## 6) سجل الـDescriptors (A + E) — وقائع لا أحكام

كل descriptor: تعريف + صيغة + availability + تعقيد + مصدر العقد. **«impulse/retracement/range» تبقى أوصافاً إجرائية** (operational descriptive labels) أو تُتعلَّم لاحقاً — لا market truth.

### 6.1 حركات مسارات (A) — لكل segment قانوني (من origin حتى آخر bar متاح)

| Descriptor | التعريف | Availability | التعقيد |
|---|---|---|---|
| `price_displacement` | close_end − start_price | عند end availability | O(1) تدفقي |
| `path_length` | Σ\|close_i − close_{i−1}\| داخل المدى | متاح جزئياً؛ نهائي عند end | O(1)/bar |
| `duration_bars` / `duration_time` | عدد الأشرطة/الزمن | ينمو تدفقياً | O(1) |
| `velocity` | displacement/duration | تدفقي (وصفياً للمسار الجاري) | O(1) |
| `acceleration_desc` | فروق velocity بين نوافذ **left-anchored** ثابتة العقد | تدفقي | O(1) |
| `efficiency` | \|displacement\| / path_length — **بلا threshold** | تدفقي + نهائي | O(1) |
| `retracement_depth` | أقصى عودة مقابل حركة والدة مُؤكدة (نسب وصفية) | بعد توفّر الطرفين | O(1) بسجل extreme |
| `realized_vol_desc` | تجميع volatility ضمن المدى (**witness**: dynamic_volatility CLOSED) | as-of نفس المحرك | O(1) تدفقي |
| `wick_body_geometry` | مجاميع wick/body fractions — حيث يكون القانوني (لا اختراع OHLC داخل المبهم) | شريطاً | O(1) |
| `executed_base_volume` / `executed_quote_volume` | من executed-flow source فقط | as-of المصدر | O(1) |
| `buy_initiated` / `sell_initiated` / `flow_delta` | EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT — **PROXY منفصل** | as-of المصدر | O(1) |
| `price_response_per_activity` | Δprice / executed volume في نافذة left-anchored | وصفي، لا سببي | O(1) |

**ممنوعات التسمية**: لا bullish pressure، لا absorption مؤسسي، لا whale، لا market-wide — إلا بالعقود الموجودة فعلاً (executed flow semantics).

### 6.2 أوصاف السلوك (E) — أوصاف factual تكفي لتعلّم الفرق لاحقاً

`directional_efficiency`, `retracement_ratio` (**descriptor لا threshold**), `overlap_ratio` (تداخل المدى الأب/الابن), `alternation_count`, `speed_profile` (vector سرعة محدود البعد — بنيوي), `persistence` (نسبة الأشرطة المؤيدة للاستمرار داخل نافذة left-anchored), `volatility_adjusted_displacement` (displacement / realized_vol — عقد القاسم مُعلن), `flow_response` (6.1 الأخير), `time_symmetry` (زمن الصعود/الهبوط داخل المسار), `path_roughness` (path_length/displacement − 1 أو عدد انقلابات السعر — بنيوي), `break_consequences` (عدّاد أحداث BOS/CHoCH المنسوبة — witness من CLOSED).

**الـlabel الاختياري** `behavioral_class ∈ {IMPULSE_LIKE, RETRACEMENT_LIKE, RANGE_LIKE}`: إما **operational descriptive** بعقد صريح (تعريف = شروط على الـdescriptors أعلاه، تُثبَّت في `descriptor_set_version`)، أو **learned later** (TRAIN فقط). ممنوع: REAL_WAVE / FAKE_WAVE / أي تصنيف ذوقي.

---

## 7) التكامل مع CLOSED (F/G/H) — witness لا إعادة بناء

| CLOSED (witness) | يبقى يُنتج | طبقة MUF فوقه (بدون لمسه) |
|---|---|---|
| 2.1A `CausalAdaptiveSwingDetector` | candidates/swings بـorigin/confirmation | مصدر المرشحين لدرجة policy-0؛ lattice يضيف درجات عبر policies مستقلة |
| `ConfirmedSwingSequenceEngine` | sequence_class (HH/HL/LH/LL) per row | يُعاد استدعاء الـclassifier على sequences لكل درجة (مُعلَن كـderived view) — Micro/Local/Major BOS = أحداث structural_breaks مربوطة بـ`scale_id` الذي أنتجها |
| `CausalStructuralBreakEngine` | BOS/CHoCH events | `structure_events` تُثبَّت بشاهدها + `scale_context` يُملأ من الـlattice (لا يُعاد تعريف BOS داخل MUF) |
| `CausalLiquidityMapEngine` | levels + lifecycle (touch/wick/close breach/reclaim) | كل level يأخذ `creating_wave_id`, `scale_id`, `age`, `cluster_id`; «كل swing = سيولة مهمة» **مرفوض** — السيولة كيان بحياته وموقعه في التدرج فقط |
| `CausalFVGEngine` | events/lifecycle (creation/coverage/reclaim/… + `origin/middle/creation` positions + coverage/age descriptors) | `created_by_wave_id` (موجة active عند `origin_position`), `inside_wave_id` (تحتية وقت الحدث), `created_during ∈ {directional_expansion, retracement, range_like}` = **operational** من قيم الـdescriptors وقت الإنشاء, `structure_scale_id` |
| `CausalOrderBlockEngine` | candidates + touch/breach/reclaim counts (بلا institutional claim) | نفس الربط: `created_by_wave_id` عبر `created_ob_source_break_event` ومواضع origin/creation + سياق `search_boundary` |
| `CausalDealingRangeEngine` | ranges (pending endpoint حسب العقد) | `range_scale_id` = درجة الموجة الأصل؛ الـendpoint المعلق يبقى FORMING-analog |
| `CausalHTFAggregator` | HTF bars/states (CLOSE_TIME فقط) | عُقد `HTFStateNode` في الرسم البياني + context لكل موجة عند availability |
| volume_delta / absorption | أدلتها التشغيلية (PROXY/ACTUAL) | `flow_context` للموجة — منفصلان دائماً |
| evidence_vector / narrative | أسطحها المغلقة | لا تُلمس؛ consequences تُسجَّل كمراجع فقط |
| `visibility` + `information_time` | as-of projection + InformationKey | **أساس القسم I/J**: «خريطة كما كانت معروفة وقتها» = استعلام as-of فوق الرسم |
| `research/hashing.py` | canonical sha256 | IDs و record hashes |

**قاعدة عدم التعديل الصامت**: أي حاجة لقراءة سطر إضافي من CLOSED تتطلب PATCH مُبرَّر + بوابة old==new (مثل منهج EXACT PERFORMANCE V2)؛ وإلا يُبنى فوق المخرجات العامة كما هي.

---

## 8) Market State Graph (I)

### 8.1 Nodes
`WaveNode`, `TurningPointNode`, `LiquidityNode`, `FVGNode`, `OBNode`, `RangeNode`, `HTFStateNode` — كل node: `node_id` (hash), `origin_*`, `available_*`, `status`, `payload_ref` (السجل الكامل في جدولاته).

### 8.2 Edges (كلها بـ`edge_available_position`)
`parent/child` (CONTAINS), `created_by`, `inside`, `tested_by` (lifecycle events), `superseded_by`, `conflicts_with` (equal extrema/تناقض أوصاف), `aligned_with`, `temporal_before` **فقط عندما تكون الـchronology قانونية** (origin positions متباعدة بقرار عقد — وعند التعادل: لا حافة زمنية، فقط ALTERNATES_WITH).

### 8.3 الاستخراج as-of
`market_state_at(T) = subgraph induced by nodes/edges with available_position ≤ T` — تنفيذياً نفس منطق `visibility` (masks + projections)؛ التعقيد O(size of extracted subgraph) بفهارس position. **منع الدورات**: الحاويات الزمنية للـwaves تُبنى nestingاً صارماً (interval containment)؛ أي إدخال حافة parent يتحقق topologically عند الإدراج — O(1) amortized بـunion-find على الفروع النشطة.

---

## 9) الذاكرة / Analogs (J) — عقود فقط

`StateSnapshotRecord` عند كل T (أو عند أحداث):
- `information_key` (timeline_id, bar_position, event_time_utc, phase, sequence — InformationKey الحالي).
- `descriptor_vector` (إصدار مجمَّد من 6 + إحصاءات الرسم: أعداد waves لكل status/درجة، ملخصات كيانات، volatility, HTF context).
- `missingness_map` صريح + `representation_id` + `policy_hash`.
- **عقد المقارنة**: تشابه التاريخ يُحسب فقط بين snapshots بنفس `representation_id + descriptor_set_version + policy_hash` — وإلا النتيجة NOT_COMPARABLE (لا مزج نسب من عوالم مختلفة).
- **ممنوع في الميزات**: أي label مستقبلي، أي outcome، أي «ماذا حدث بعد T». التنفيذ (nearest-neighbor إلخ) **ليس الآن**.

---

## 10) External Market Context Registry (K) — عقود مستقبلية بلا تنفيذ

### 10.1 قالب العقد لكل مصدر
```
ExternalSourceSpec {
  source_id, provider, instrument_scope,
  semantic_type ∈ {ACTUAL, PROXY},   # لا دمج
  availability_lag_contract,          # متى يُعرف تاريخياً
  provenance_requirement,             # بصمة/مصدر موثق إلزامي
  missingness_policy,                 # NOT_CONFIGURED افتراضي — لا اختراع
  granularity_contract
}
```

### 10.2 المسجل المقترح (الكل NOT_CONFIGURED حتى توفّر مصدر موثوق)
BTC dominance | ETH/BTC | total crypto breadth | funding | open interest | basis | liquidations | order book/depth (تاريخي بجودة موثقة فقط) | mark/index prices.

### 10.3 DOMINANCE — توضيح إلزامي
**لا تُشتق من BTCUSDT وحده.** dominance = حصة BTC من capitalization سوق كريبتو كله؛ تحتاج سلسلة تاريخية مستقلة المنشئ (provider ينشر capitalization مرجّحة/مركّبة) **بعقد provenance وavailability خاص بها**. أي محاولة اشتقاقها من سعر/حجم BTCUSDT وحده = مخالفة مفاهيمية مرفوضة. حتى ذلك الحين: `NOT_CONFIGURED` — لا بديل مُخترع، لا proxy صامت.

---

## 11) Detection Reality Audit (L) — بوابة قبل أي Edge claim

1. **اختيار timestamps deterministic قبل رؤية أي output**: قاعدة مثبّتة مسبقاً (مثلاً: `sha256(audit_seed ‖ bar_position)` مُرتَّب صعوداً، مع `audit_seed` منشور في audit manifest قبل التشغيل) + طبقات إجبارية (بداية/وسط/نهاية الشهر + محيط أحداث كثيفة) — **معيار الاختيار لا يرى detector outputs إطلاقاً**.
2. لكل sample: chart context (OHLC) + كل الـwaves المؤكدة بدرجاتها + forming wave state + FVG (+ flow + HTF؛ لاحقاً liquidity/OB/ranges) + **كل marker بـorigin-time وknown-at-time**.
3. المحك: التمثيل يطابق operational definitions المنشورة — لا «الجميل منها». نسبة التطابق تُسجَّل كما هي (لا نسبة نجاح مُصطنعة). المخرج: `DETECTION_AUDIT_MANIFEST` (عينات + بصمات + نتيجة المطابقة).
4. العدد الإلزامي من العينة: مُثبَّت في العقد (مثلاً 24 عينة) — لا اختيار يدوي بعد الرؤية.

---

## 12) Information Edge Gate (O) — عقد تجربة فقط (لا تنفيذ)

```
ExperimentContract {
  experiment_id, representation_id(s), dataset_identity (TRAIN/OOS cutoffs),
  baseline: "price + volatility simple context (عقد محدود)",
  candidate: "MUF representation snapshot (J)",
  ablations: [ -wave_hierarchy, -executed_flow, -FVG, -liquidity, -HTF, ... ],
  metric_slots: [ ... تُملأ لاحقاً بمحك واحد مُعلن ... ],
  freezing: "كل policies مجمّدة من TRAIN قبل أي قياس",
  forbidden: "لا اختيار بعد رؤية OOS، لا مقارنة بمقاييس متعددة بلا تصحيح"
}
```
- لا تُنفَّذ هنا. أي نتيجة مستقبلية = معلومة إحصائية تحت عقدها، **لا ادعاء Information Edge مفتوح النطاق**.

---

## 13) مخرجات الإنسان (P)

لكل timestamp على الشارت:
- السعر الحالي + الحالة: micro/local/major (أو أسماء الدرجات المرسلة) — **confirmed waves** و**forming waves** مرسومة بأطرافها: `start → end` (ونهاية مفتوحة أثناء FORMING) + اتجاه + status + parent/children.
- structure labels لكل درجة (HH/HL/LH/LL, BOS/CHoCH) — كل label يحمل `scale_id`.
- liquidity / FVG / OB / range — كل كيان بحالته (forming/filled/reclaimed...) وعمره.
- context شريط: executed flow (PROXY/ACTUAL مفصولان بصرياً)، volatility، HTF.
- **والأهم — قوس المعرفة على كل marker**: `origin: T_o | known-at: T_k` (witness = InformationKey). هدف العرض أن يرى الإنسان **بعينه** أن النظام لم ير المستقبل: كل مرسوم قدامه يحمل متى وقع ومتى عُرف.

---

## 14) الأداء (Q)

| الخوارزمية | التصميم | التعقيد |
|---|---|---|
| Path primitives (A) | تدفقي per-bar، تجميعات incrementally | **O(n)** كامل، O(1)/bar |
| Turning-point lattice (B) | لكل درجة: monotone stack على الـextrema (نمط candidate/confirmation الحالي) | **O(Kn)** = O(n) عند K ثابت لكل تمثيل |
| Wave nesting (D) | stack موجات نشطة؛ إدراج/إغلاق amortized | **O(n)** amortized |
| Descriptors (E) | نوافذ left-anchored بحدود عقد، مجاميع جزئية | O(1)/bar لكل descriptor |
| State graph (I) | إدراج حواف عند الأحداث + فهرس position + union-find للفرع النشط | O(1) amortized/حدث؛ as-of query **O(m)** لحجم الناتج |
| Hash/IDs | research/hashing (vectorized بعد PATCH-4) | O(size record) |
| Snapshot extraction (J/L) | إسقاط visibility بنقاط مفهرسة | O(m) |
| Million-bars ككل | streaming بلا تخزين مسارات خام | ذاكرة O(active state + K stacks) |

**قواعد**: لا O(n²)؛ لا cache كبديل لتعقيد سيئ؛ أي خوارزمية تُرفق بتعقيدها عند التنفيذ؛ benchmark مليون bar **إلزامي** في بوابة الأداء (T).

---

## 15) ما هو «Understanding» (R) — تعريف صريح

Market Understanding في هذا المشروع يعني حصراً:
**تمثيل سببي منظّم** + **تدرج** + **علاقات** + **سياق** + **uncertainty/unknown مُعلَن** + **قابلية المقارنة التاريخية**.
- ليس وعياً بشرياً، ليس يقيناً 100%، ليس «قراءة نية السوق».
- كل «فهم» هنا = استعلام قابل للتكرار على state graph عند T بمعلومات T فقط.
- ممنوع تسويق المخرجات كـ«النظام يفهم السوق» — الصياغة المسموحة: «causal structured market representation».

---

## 16) خطة الملفات/الوحدات (S)

### 16.1 وحدات جديدة (فوق CLOSED — لا تعديل)
```
src/trading_system/market_understanding/
    __init__.py
    contracts.py            # WaveRecord/TurningPoint/edges/status enums + validation
    path_primitives.py      # A
    turning_point_lattice.py# B (يستهلك 2.1A كـwitness)
    wave_hierarchy.py       # C + بناء الموجات
    nesting.py              # D
    wave_descriptors.py     # E
    multiscale_structure.py # F (ربط HH/HL/LH/LL و BOS/CHoCH بالدرجات)
    context_binding.py      # G/H (liquidity/FVG/OB/range ↔ waves)
    state_graph.py          # I
    snapshot_memory.py      # J (عقود + بنية فقط)
    external_registry.py    # K (عقود فقط — لا بيانات)
    reality_audit.py        # L
    representations.py      # M (RepresentationSpec + registry)
```
اختبارات: `tests/test_muf_*.py` لكل وحدة + `tests/test_muf_adversarial_battery.py` + `tests/test_muf_perf_million_bars.py` (benchmark).

### 16.2 ما يمكن بناؤه فوق CLOSED فوراً
كل ما في 16.1 — استهلاك المخرجات العامة فقط.

### 16.3 ما يحتاج PATCH حقيقي (مُبرَّر + old==new — وليس الآن)
- إمكانية قراءة **history counters** من policies أثناء التشغيل (إن تعذّر عبر API العام) — مؤجَّل.
- hooks لتسجيل `structural_consequences` مباشرة من structural_breaks إن ثبت أن الربط الخارجي غير كافٍ — مؤجَّل بدليل.

### 16.4 مؤجَّل إلى Calibration/Estimand
سياسات الدرجات (N)، labels المُتعلَّمة (E)، تقييم التمثيلات (M/O).

---

## 17) الديون والتفاعلات مع RESEARCH-DEBT-020..025

- **020..025 تبقى OPEN** (مرفوعة في trajectory stages) — MUF لا يُغلقها ولا يرثها بصمت.
- سطوح التقاطع: trajectory/research تستهلك snapshots (J) لاحقاً؛ أي دمج يبقى خلف علامات الدينون البحثية نفسها.
- `hashing`/`manifest_identity`/`visibility` تُعاد استخدامها — سجلاتها المُثبَّة (PATCH-4/5) هي المرجع؛ لا إعادة كتابة.
- dataset/eligibility/outcome_observer (عقود fold/train) هي مسار N — لا نبني نظام calibration موازياً.

---

## 18) OUT OF SCOPE (صريح)

لا BUILD في هذا التقرير | لا quantile/قيمة معلمة مختارة | لا model | لا strategy | لا PnL | لا توصية | لا Information Edge claim | لا تنفيذ external context أو تنزيل بياناته | لا nearest-neighbor | لا إعادة بناء أي detector CLOSED | لا REAL_WAVE/FAKE_WAVE | لا «وعي/يقين» | لا تعديل CLOSED بلا PATCH مُبرَّر | لا Reality analysis.

---

## 19) Blockers (الصريحة)

1. **سياسات التأكيد NOT_CONFIGURED** — `swing_quantile` الحالي (معامل مالك) يتحول إلى policy artifact مُتعلَّم TRAIN فقط؛ حتى ذلك الحين الدرجات الزائدة على witness-0 تبقى NOT_CONFIGURED.
2. **مصادر السياق الخارجي غير موجودة** (dominance إلخ) — K عقود فقط.
3. **RESEARCH-DEBT-020..025 OPEN** — تتقاطع مع research surfaces.
4. **بيانات المالك** لازمة لأي تشغيل حقيقي (owner PC فقط).
5. **اعتماد [M]** يحتاج عقد TRAIN/OOS cutoffs مُصادَقاً عليه قبل أي قياس.

---

## 20) BUILD READY لكل substage + ترتيب التنفيذ الكامل (بلا ترقيعات)

| # | Substage | المدخلات | المخرجات | بوابات القبول | الحالة |
|---|---|---|---|---|---|
| S0 | عقود MUF (contracts.py + docs) | هذا التصميم | enums/schemas/validation + update docs | مراجعة مالك | READY |
| S1 | path_primitives (A) | timeline/flow/vol witnesses | descriptors تدفقية | adversarial: future-append, prefix, same-bar, missing source | READY بعد S0 |
| S2 | turning_point_lattice (B) | 2.1A witness + policies slots | candidates متعدد الدرجات | no-repaint proof, origin/availability split | READY بعد S1 |
| S3 | wave_hierarchy + nesting (C/D) | S2 | WaveRecord + edges | nested/unfinished/equal-extremes/flat/violent-reversal battery | READY بعد S2 |
| S4 | wave_descriptors (E) | S1+S3 | سجل أوصاف | no-magic-threshold AST gate + determinism | READY بعد S3 |
| S5 | multiscale_structure + context_binding (F/G/H) | S3 + CLOSED entities | ربط HH/BOS والكيانات | cross-scale consistency + tie cases | READY بعد S4 |
| S6 | state_graph + as-of (I) | S5 | market_state_at(T) | cycle prohibition, deterministic IDs, mutation integrity | READY بعد S5 |
| S7 | reality_audit (L) | S6 | audit manifest + samples | timestamp rule frozen pre-output | READY بعد S6 |
| S8 | representations + snapshot_memory (M/J) | S3–S6 | RepresentationSpec + snapshots | comparability contract tests | READY بعد S7 |
| S9 | external_registry (K) | — | عقود فقط | docs review | READY (لا بيانات) |
| S10 | calibration harness (N) | dataset contracts | fit/freeze/apply pipeline (لا تشغيل) | train-only enforcement tests | READY بعد S9 |
| S11 | edge gate contract (O) + human surface (P) | S7+S8 | عقد تجربة + spec عرض | contract review | READY بعد S10 |
| S12 | perf benchmark مليون bar (Q) | S1–S6 | bench report | O(n log n) ceiling ذهبي | مع S6→S12 |

**الترتيب صارم S0→S12** — كل substage يدخل التالي مغلقاً ببواباته؛ لا «ترقيع نكشة نكشة»؛ أي ارتداد يتطلب إعادة بوابة. لا يُبدأ أي BUILD قبل مراجعة المالك لهذا التصميم.

---

**END OF DESIGN — لا إجراء آخر.**

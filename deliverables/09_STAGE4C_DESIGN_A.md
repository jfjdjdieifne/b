# STAGE 6.2A-4 — STAGE 4C — DESIGN ONLY — DESIGN A

```text
الحالة المرجعية: Stage 4B-2 V1 = CLOSED. المانيفست 170/170،
SHA256 1a21753f2de85bfbb56d0ae2ba4bcc7a5273cb9c42a2e6b9010d4a57ac469a12.
هذا تصميم أول مستقل (DESIGN A). لا كود، لا BUILD، لا PATCH، لم تُلمس أي وحدة CLOSED ولا
المانيفست ولا أي وثيقة داخل شجرة المشروع. المخرج تصميم فقط، ينتهي بـSTOP.
كل العقود المذكورة أدناه مأخوذة من قراءة الكود المغلق الفعلي (وليس من ذاكرة أو تقارير).
```

---

## 1. الغرض وحد الشهادة

### 1.1 الغرض
نقل حقائق **الأطر الزمنية الأعلى (HTF) وتعدد الأطر (MTF)** إلى داخل فيلم المستقبل،
بصفتها حقائق سوقية مشتركة محايدة للفرضيات، تُبنى مرة واحدة لكل هوية سوق/مقاييس وتُسقط
على قرارات الإطار الأدنى (LTF) عبر as-of سببي صارم:

- لكل مقياس HTF مُصرَّح به: شموع مكتملة فعلية (OHLC) مُجمَّعة من LTF المختوم، مع **تغطية
  رصد صادقة** (كم شمعة LTF شوهدت فعلاً داخل الدلو).
- حالة البنية على كل مقياس HTF بعد إغلاق الدلو (UNDEFINED/UP/DOWN/MIXED) عبر تشغيل السلسلة
  المغلقة 2.1A→2.1B→2.1C على الدلوه المكتملة نفسها (لا إعادة اختراع).
- إسقاط as-of للحالة على فهرس قرار LTF، ومصفوفة توافق/تعارض وصفية لكل بار قرار عبر
  المحرك المغلق 5.2.
- أحداث انتقال حالة MTF (متى تغيّرت حالة مقياس، ومتى أصبحت مرئية قانوناً على LTF).

4C **يستهلك** العقود المغلقة 5.1 و5.2 وسلسلة البنية، ولا يعيد تنفيذ تجميع أو توافق.

### 1.2 ما الذي يُثبته 4C عند إغلاقه (ضمن نطاق الاختبار فقط)
- أن قرار LTF عند اللحظة `t` لا يرى أبداً أي قيمة لدلو HTF لم يُرصد إغلاقه فعلاً (لا
  high/low/close ولا حالة بنية ولا توافق مشتق منه).
- الرؤية عند حد الإغلاق الصريح `t == bucket_end` قانونية ضمن **نفس دفعة المعلومات**، مع علم
  صريح أن ترتيب LTF/HTF داخل الدفعة غير معروف، وعند `end−ε` مستحيلة، وعند `end+ε` ثابتة.
- الرصد الفعلي (`first_observed_asof`) لا النهاية النظرية هو ما يحكم الإتاحة عند ثغرات البيانات.
- استقرار كامل تحت الإلحاق المستقبلي (إعادة البناء على تاريخ أطول لا تغيّر أي بادئة ≤T).
- هوية سطح ثابتة لكل مجموعة مقاييس/مدد/عقد إيقاع، ترفض تبديل المقياس/المدة/المجال حتى مع
  إعادة حساب بصمات متماسكة.
- سلامة ذاتية، حدود InformationKey المغلقة، منع cross-timeline، جدار حي/بحث، وإعادة بناء
  كشاهد اشتقاق فقط.

### 1.3 ما الذي لا يثبته (حدود صريحة)
لا SUPPORT تنبؤي، لا استقلال إحصائي للمقاييس، لا أوزان/احتمالات/score، لا QualificationObjective،
لا نموذج، لا هندسة صفقة/دخول/وقف/هدف، لا تنفيذ/ملء، لا PnL/WIN/LOSS، لا إشارة. علم التغطية
ليس شهادة جودة تغذية من مُصدِر. حالات المحاذاة/التعارض وقائعية وصفية لا تنبؤية. لا يُغلق أي
دَيْن 020..025 ضمناً. لا بروفينانس توليدية تاريخية (تبقى NOT_CERTIFIED/UNVERIFIABLE).

---

## 2. ثلاث فخاخ سببية حُسمت قبل التصميم (من الكود المغلق الفعلي)

1. **حد الإغلاق الصريح**: 5.1 يستخدم فترات CLOSE_TIME نصف-مفتوحة `(start, end]` وربط
   as-of عبر `searchsorted(completed_ends, t, side="right")−1`. أي أن الدلو يظهر لأول بار
   قرار زمنه `== end` بالضبط، ويستحيل ظهوره قبله. 5.2 يستخدم نفس قاعدة الـright. التصميم
   يحترم العقد المغلق كما هو (رؤية عند `end` داخل نفس الدفعة + علم عدم ترتيب)، ولا يؤجل
   قسراً إلى `end+1` (ذاك كان سيُنقص معلومة قانونية ويخالف المحرك المغلق).
2. **الإغلاق النظري ليس إتاحة فعلية**: 5.1 لا يُصدر الدلو إلا إذا `end ≤ آخر طابع زمني
   مرصود`، ويعطي `theoretical_available_at = end` لكن أيضاً
   `first_observed_asof_position/time = أول بار مُرصَد عند/بعد end`. عند ثغرة تغذية، الإتاحة
   الفعلية تتأخر؛ 5.2 نفسه في اختباره يبني `available_at = first_observed_asof_time`. 4C
   يتبنى **الإتاحة المرصودة** للتسقيط، ويحتفظ بالنظرية كحقل أصل/مرجعية فقط.
3. **اكتمال المحتوى غير معروف بلا عقد إيقاع**: 5.1 يصرّح في وثيقة الوحدة نفسها «اكتمال تغطية
   المصدر غير معروف بلا cadence contract»، ويعطي `source_bar_count` المرصود فقط. دلو 60 دقيقة
   بشمعتين مرصودتين قد يُحسب «مكتمل الانقضاء» وهو ناقص المحتوى. 4C لا يملأ فراغاً ولا يخمن
   اكتمالاً؛ يضيف عقد إيقاع صريح اختياري وعلماً ثلاثي الحالة (القسم 6.5)، بلا أي رقم سحري.

قيد محوري إضافي: **5.1 يتطلّب فهرس DatetimeIndex بمنطقة زمنية**. إذن 4C يقتضي المحور الزمني
حصراً (سابقة: سطح الجلسات في 4A يرفض POSITIONAL رفضاً صريحاً). لا توليف لحدود HTF على محور
موضعي بلا أزمنة.

---

## 3. العقود العامة المغلقة التي يستهلكها 4C (الأسماء الفعلية)

من **5.1** `trading_system.multitimeframe.causal_htf` (عام فقط، لا رموز `_` خاصة):
- `TimeAggregationSpec(duration: pd.Timedelta, timestamp_semantics=CLOSE_TIME)`؛ يدعم
  CLOSE_TIME فقط، يرفض المدة غير الموجبة.
- `CausalHTFAggregator(*, spec).analyze(df) -> (asof_df, bucket_table)`:
  - `asof_df`: نسخة الإطار + أعمدة `last_completed_htf_end_utc`,
    `last_completed_htf_open/high/low/close`, `last_completed_htf_source_bar_count`
    (+`last_completed_htf_volume` إن وُجد volume — مستبعَد من نطاق 4C V1).
  - `bucket_table` (مفهرس بـ`bucket_end_utc`): `bucket_start_utc`, `bucket_end_utc`,
    `theoretical_available_at`, `first_observed_asof_position` (Int64، إحداثيات LTF),
    `first_observed_asof_time`, `first_source_timestamp`, `last_source_timestamp`,
    `source_bar_count`, `open`, `high`, `low`, `close`.
  - يتحقق بنفسه من: tz-aware، فهرس فريد متزايد، OHLC finite وهندسة H≥L، عدم تصادم الأعمدة.
- الأخطاء العامة: `HTFError/HTFConfigError/HTFDataError`.

من **5.2** `trading_system.multitimeframe.confluence_matrix`:
- `ScaleFrame(name: str, frame: pd.DataFrame)` (اسم آمن regex `[A-Za-z][A-Za-z0-9_]*`).
- `causal_asof_align_scale_state(decision_index, completed_scale_frame, available_at_column='available_at', state_column='structure_state_after')`
  يُرجع على فهرس القرار: `available` (bool), `source_available_at` (datetime),
  `structure_state_after` (string)، ويرفض: available_at مستقبلية، حالة خارج
  {UNDEFINED, UP_STRUCTURE, DOWN_STRUCTURE, MIXED}، تكرار available_at، ترتيباً غير رتيب.
- `CausalConfluenceMatrixEngine().analyze(decision_df, scales)` يُرجع لكل مقياس:
  `<name>__available`, `<name>__source_available_at`, `<name>__structure_state`,
  `<name>__structure_direction_code`, `<name>__information_age_seconds`؛ والتجميعيات:
  `configured_scale_count`, `available_scale_count`, `unavailable_scale_count`,
  `up/down/mixed/undefined_structure_count`, `directional_scale_count`,
  `availability_fraction`, `directional_fraction`, `directional_balance`,
  `directional_consensus`, `directional_conflict`.
- يرفض داخلياً: `source_available_at` مستقبلي، بروفينانس رجوعياً للزمن، **إعادة طلاء حالة
  عند نفس available_at بقيمة مختلفة**، عمراً سالباً، فهرس مقياس لا يساوي فهرس القرار.
- الأخطاء: `ConfluenceError/ConfluenceDataError`.

من **سلسلة البنية المغلقة 2.1A/B/C** (نفس قناة stage4b1/stage2 العامة):
`CausalAdaptiveSwingDetector(confirmation_policy=...).analyze(df, high_col=, low_col=)` ←
`ConfirmedSwingSequenceEngine().analyze` ← `CausalStructuralBreakEngine().analyze`؛ المخرج يحوي
`structure_state_before/structure_state_after` (string، نفس مجموعة قيم 5.2 المسموحة).

من **Stage 1/4A/4B-1/4B-2**: `MarketObservationTimeline.seal/verify`،
`TimeIndexedTimelineAdapter/PositionalTimelineAdapter`، `InformationKey`,
`InformationPhase` (BAR_PRE_CLOSE مرفوض؛ COMPLETED_ROW_AVAILABLE / RESEARCH_SNAPSHOT_AVAILABLE
قانونيان للحدود)، `canonical_sha256`، `TIMELINE_ADAPTER_KIND`،
`TrajectoryContractError/TrajectoryDataError`، وأنماط التجميع/المرايا/التحقق الديناميكي.

**لا استيرادات خاصة `_` إطلاقاً**. أي مخطط مغلق يُضبط عبر مرآة محلية `Final` + تحقق ديناميكي
يبني المحرك الفعلي ويرفض أي اختلاف (درس بلوكر 4B-2 الثالث).

---

## 4. الإدخال والإعداد (عقد الباني المقترح)

```python
# أسماء مقترحة فقط؛ العقد يُعتمد في DESIGN ثم BUILD.
@dataclass(frozen=True)
class MtfScaleSpec:
    name: str                 # آمن regex 5.2؛ فريد؛ لا افتراضات
    duration: pd.Timedelta    # موجب؛ ثابت UTC؛ يُمرَّر لـTimeAggregationSpec

@dataclass(frozen=True)
class LtfCadenceContract:
    nominal_period: pd.Timedelta   # إيقاع LTF المعلن من عقد التغذية (مثل 1min)

def build_mtf_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimeIndexedTimelineAdapter,
    market_history: pd.DataFrame,      # نفس الإطار المختوم (LTF)، OHLC إلزامي
    scales: tuple[MtfScaleSpec, ...],  # غير فارغ، غير مكرر، بترتيب صريح
    cadence: Optional[LtfCadenceContract] = None,   # None ⇒ تغطية UNKNOWN
    htf_swing_policy=None,             # شاهد سياسة كما في 4B-1؛ None أمانة
) -> "Stage4CMTFSurface": ...
```

قواعد فاشل-مغلق عند الإدخال:
- زوج `(timeline, adapter, market_history)` يجتاز `timeline.verify` أولاً.
- `adapter_kind` يجب أن يكون TIME_INDEXED؛ غيره ⇒ `TrajectoryDataError` (نص صريح أسوة
  بسطح الجلسات). لا POSITIONAL ولا DatetimeIndex مختلق.
- `scales` غير فارغ؛ أسماء فريدة وآمنة (يفرضها 5.2 ونعيد فرضها)؛ مدد موجبة؛ لا مقاييس
  افتراضية مدمجة (منع الأرقام السحرية: مجموعة المقاييس سؤال بحث يصرّحه المالك).
- لا يُشترط أن تكون مدة مقياس من مضاعفات الآخر (الدلوه على شبكة UTC الحقبة في 5.1 مستقلة).
- `cadence`: عند وجوده يجب أن تقبل `duration % nominal_period == 0` لكل مقياس وإلا
  `TrajectoryContractError` (عدد متوقع صحيح بلا نسبة تسامح سحرية). عند غيابه: تغطية UNKNOWN.
- أي استثناء من 5.1/5.2/السلسلة يُغلَّف بـTrajectoryDataError بلا أي fallback أو تخمين.

## 5. خطوط الأنابيب الداخلية (إعادة استخدام، لا إعادة اختراع)

لكل مقياس بالترتيب المصرَّح:
1. `spec51 = TimeAggregationSpec(duration=s.duration)`؛
   `asof_ltf, bucket_table = CausalHTFAggregator(spec=spec51).analyze(market_history)`.
2. تشغيل سلسلة البنية المغلقة على `bucket_table` المفهرس بـ`bucket_end_utc` (OHLC فقط):
   `htf_chain = 2.1A→2.1B→2.1C`؛ يؤخذ `structure_state_after` لكل دلو، ويُحتفظ بالمخرج
   الكامل للسلسلة كجدول بنية HTF (مبدأ ربط الناتج العام الكامل كما في 4B-1، لا الاكتفاء
   بالمستهلك). تفصيلة BUILD: إن رفض 2.1A فهرسة زمنية للدلو، يُستخدم فهرس موضعي Int64 للسلسلة
   مع إبقاء `bucket_end_utc` عموداً (قرار تنفيذي يثبته الاختبار، لا يغير دلالة الإتاحة).
3. بناء إطار «الدلوه المكتملة» لـ5.2: صف لكل دلو، `available_at =
   first_observed_asof_time` (الإتاحة المرصودة)، `structure_state_after` من السلسلة؛ يُرفض
   أي صف `available_at < bucket_end` (مستحيل من 5.1، تحقق دفاعي).
4. `aligned = causal_asof_align_scale_state(market_history.index, completed_frame)`.
5. يُغلَّف `ScaleFrame(s.name, aligned)`؛ وتجمع كل المقاييس عبر
   `CausalConfluenceMatrixEngine().analyze(decision_df=market_history.copy(), scales=...)`.
6. فوق مخرج 5.2 تُضاف لكل مقياس أعمدة 4C المشتقة فقط: قيم آخر دلو مكتمل as-of
   (`<name>__htf_end_utc/open/high/low/close`) من `asof_ltf`، وعدّاد التغطية
   (`<name>__source_bar_count`, `<name>__expected_bar_count`, `<name>__coverage_status`) —
   تُحسب من جدول الدلو المرصود المربوط بنفس as-of (نفس آلية right-boundary).
7. علم نفس-الدفعة: لكل صف قرار ولكل مقياس،
   `<name>__same_batch_order_unknown = available AND (source_available_at == t_decision)`؛
   لا حقل ترتيب داخلي، و`deterministic_sequence` يبقى ثابتاً داخل الدفعة.

---

## 6. الكيانات والجداول والمخططات المقترحة

تصميم سطح واحد بصنف ثابت المجال (درس منع التبديل في 4B-2): `Stage4CMTFSurface` بمجال
ثابت على مستوى الصنف `MTF_HTF`؛ المقاييس داخل إعداد مُجمَّد، لا حقل domain يضبطه المستدعي.

### 6.1 الجداول المملوكة للوحدة (مخطط دقيق، بلا passthrough ⇒ مساواة كلية صارمة)
**أ) `bar_frame`** على فهرس LTF: أعمدة السوق المختوم (passthrough: open/high/low/close
وvolume إن خُتم) + ذيل مشتق ثابت الترتيب:
- تجميعيات 5.2 الـ14 بأسمائها الحرفية؛
- لكل مقياس بالأسماء: أعمدة 5.2 الخمسة + 6 أعمدة HTF/تغطية + علم نفس-الدفعة (12 لكل مقياس)؛
- لا تُدرَج `last_completed_htf_volume` (volume مستبعَد من V1، القسم 11).

**ب) `bucket_frame`** (تنسيق طويل لكل المقاييس، جدول مملوك كلياً):
```
scale_name, bucket_start_utc, bucket_end_utc, theoretical_available_at,
observed_available_at, ltf_available_position(Int64), source_bar_count(Int64),
expected_bar_count(Int64 nullable), coverage_status,
open, high, low, close, structure_state_after, structure_state_before
```
**ج) `htf_structure_frame`** (تنسيق طويل): المخرج الكامل لسلسلة 2.1A/B/C على دلوه كل مقياس
+`scale_name`+`bucket_end_utc`+`ltf_available_position`، مخططه مرآة محلية مُتحقَّق ديناميكياً.
**د) `transition_event_frame`** (وقائع تغيّر حالة HTF):
```
scale_name, bucket_end_utc, observed_available_at, ltf_available_position,
prior_structure_state, new_structure_state, same_information_batch_order_unknown
```
صف فقط عند اختلاف حالة المقياس عن الدلو السابق (انتقال وقائعي؛ ليس إشارة).

### 6.2 الأصل مقابل الإتاحة لكل حقل (مطلوب صراحة)
| الحقل | الأصل (origin) | يُرى قانوناً عند |
|---|---|---|
| HTF OHLC لدلو k | نافذة `(start,end]` بالـUTC | `first_observed_asof_time` للدلو (==end عند تغذية كاملة) |
| `structure_state_(before/after)` لدلو k | صف دلو k في سلسلة HTF | نفس إتاحة الدلو k (لا يُعرف قبل إغلاقه) |
| انتقال حالة | دلو k (بنية HTF) | نفس إتاحة الدلو k |
| قيم as-of والتجميعيات عند بار LTF i | مشتقة من دلوه متاحة ≤i | طور COMPLETED_ROW_AVAILABLE لبار i |
| `information_age_seconds` | فروق زمنية مرصودة | عند بار i (5.2 يرفض السالب) |
| علم نفس-الدفعة | مقارنة `available_at==t_i` | عند بار i |
الحقول الأصلية (`bucket_start/end`, theoretical) تُخزَّن للديمومة لكنها لا تُستخدم أبداً
لكشف الحقيقة قبل الإتاحة المرصودة.

### 6.3 سياسة الدلو غير المكتمل/الإغلاق/الحد الصريح
- الدلو الجاري (لم يُرصد بار عند/بعد end) لا يظهر إطلاقاً: آخر مرئي يبقى الدلو السابق
  (سلوك 5.1 المُختبَر). لا high/low/close جزئي، لا «provisional».
- عند `end` الصريح: يظهر الدلو ضمن دفعة بار LTF عند end؛ علم نفس-الدفعة=True؛ لا ادعاء ترتيب.
- عند ثغرة: يتأخر الظهور حتى أول بار مرصود فعلاً؛ لا يُكشف عند end النظري.

### 6.4 المحاور وtz وcross-timeline
TIME_INDEXED حصراً؛ كل الأزمنة تُحوَّل UTC عبر العقود المغلقة (5.1/Motivation؛ اختبار DST
في 5.1 يثبت تكافؤ UTC↔America/New_York). cross-timeline يرفضه InformationKey والأدابتر؛
مفاتيح الحدود تُبنى عبر `TimeIndexedTimelineAdapter.key_for_position` وتُتحقق بـvalidate_key.

### 6.5 التغطية ثلاثية الحالة (بلا تخمين)
عبر `cadence` معلن: `FULL_OBSERVED` إن `source_bar_count == duration/period`، وإلا
`PARTIAL_OBSERVED` (مرصود أقل؛ التزايد مستحيل مع طوابع فريدة ونافذة ثابتة). بلا cadence:
`UNKNOWN_COVERAGE` لكل دلو. قبل أول دلو على LTF: `UNAVAILABLE`. الدلو PARTIAL يُعرض بصدق مع
علمه (لا حذف ولا ملء)؛ قرار أهليته لاحقاً مؤجَّل لسؤال التأهيل (Q1 للمخ/المالك).

### 6.6 المحاذاة/التعارض
لا دلالات مخترعة: 4C يربط ويعرض مخرجات 5.2 الحرفية (consensus/conflict/balance/fractions
وحالات كل مقياس)؛ «التعارض» = UP على مقياس وDOWN على آخر وفق القائمة المغلقة، ويُصبح مرئياً
فقط عند إتاحة الحالات الداخلة في حسابه (5.2 يحسب صف-بصف بلا مستقبل). الانتقال البنيوي يُروى
فقط عبر جدول الانتقالات بإتاحته المرصودة.

### 6.7 الإسقاط as-of/البادئة والاستقرار
`project_mtf_prefix(*, surface, boundary_key) -> Stage4CPrefixBinding` على نمط 4B-2، يربط
خمسة مكوّنات وقائعية حتى T (بـreset_index(drop=True) القانوني):
A. ذيل أعمدة LTF المشتقة، صفوف 0..T؛
B. `bucket_frame` حيث `ltf_available_position ≤ T`؛
C. `htf_structure_frame` حيث `ltf_available_position ≤ T`؛
D. `transition_event_frame` حيث `ltf_available_position ≤ T`؛
E. بصمة إعداد المقاييس/الإيقاع (هوية لا محتوى صفوف).
الهوية الكاملة (timeline/surface/boundary) تُحمل في حقن الـbinding لا في هاش المحتوى، بأسلوب
4B-2. الإلحاق المستقبلي القانوني يغيّر هوية السطح الكاملة ويُبقي بادئة T ثابتة.

### 6.8 الهوية والبصمات والسلامة الذاتية
طبقات بصمات مقترحة (نطاقات canonical_sha256 جديدة):
`STAGE4C_RECONSTRUCTION_INPUT_BINDING_V1` (timeline + إعداد المقاييس + cadence + بصمة سياسة
HTF)، `STAGE4C_COMPLETE_RESULT_V1` (الذيل المشتق + الجداول الأربعة المملوكة)،
`STAGE4C_SURFACE_IDENTITY_V1` (صنف ثابت المجال + إصدار + ما سبق). `verify_surface_integrity`:
- يعيد حساب كل البصمات من المحتوى الحالي ويرفض الحقول القدمة/المزورة (DataFrame قابل للتغير)؛
- يشتق المخطط المتوقع من **الصنف + إعداد المقاييس المجمّد** (كما 4A للجلسات) ويرفض أي إضافة/
  حذف/إعادة ترتيب في الذيل المشتق، ويفعل المساواة الكلية لمخطط الجداول المملوكة (يُغلق ثغرة
  حقن العمود الأوسط من 4B-2 في الجداول المملوكة؛ أما bar passthrough فيبقى على اتفاقية
  4A/4B-2 مع فحص أعمدة passthrough مقابل السوق المختوم)؛
- **تحقق ديناميكي للمرايا**: يبني 5.1 و5.2 والسلسلة فعلياً على السوق المختوم ويؤكد تطابق
  المخرجات المخزنة حرفياً (مكافئ معاد بناؤه)؛ محرك «شرير» يضيف/يحذف/يرتّب عموداً عاماً ⇒ رفض؛
- يتحقق من فئات التغطية وإتاحتها، ومن عدم وجود `available_at` مستقبلي أو طلاء حالة.

منع التبديل: تغيير اسم/مدة أي مقياس أو عقد الإيقاع يغيّر الإعداد المجمّد والمخطط المشتق
والـsurface_id؛ ومحاولة تمرير إطار بمقاييس مختلفة لإعداد مُجمّد تُرفض حتى مع بصمات متسقة
ذاتياً (السلطة من الصنف/العقد لا من البصمة، درس البلوكر الأول).

### 6.9 البروفينانس
كل الهويات شهود إعادة بناء/اشتقاق حتمية من التايم لاين المختوم؛ لا ادعاء أن التغذية وُلِّدت
تاريخياً من مصدر موثوق؛ يُنص صراحةً على NOT_CERTIFIED/UNVERIFIABLE كما في المراحل السابقة.

### 6.10 fail-closed / UNAVAILABLE / UNKNOWN
محور موضعي ⇒ رفض؛ لا مقاييس/مدد افتراضية؛ صفوف بلا دلو ⇒ available=False وحقول NA وعدّادات
صفر وكسور 0؛ غياب cadence ⇒ UNKNOWN_COVERAGE بلا افتراض إيقاع؛ أي رفض من المحركات المغلقة
يُمرَّر بلا fallback؛ لا NOT_CALIBRATED (لا معايرة هنا) — نظيرها UNKNOWN_COVERAGE. لا أرقام
سحرية: المدد والإيقاع كلها إدخال صريح يُربط في الهوية.

### 6.11 المخططات المجمّدة وحدود passthrough
مرايا محلية Final: تجميعيات 5.2 الأربعة عشر حرفياً؛ نموذج أعمدة 5.2 الخمسة لكل مقياس؛ مخطط
جدول دلو 5.1 المستهلَك؛ مخطط مخرجات 2.1A/B/C (يُعاد استخدام مرايا stage4b1 المحلية أو تُنسخ
محلياً مع تحقق ديناميكي)؛ مجموعات حالات 5.2 المسموحة. passthrough السوق المُعاد استهلاكه:
open/high/low/close (وvolume إن خُتم لكنه لا يدخل V1) يُفحص مقابل الإطار المختوم كما في 4B-2.

---

## 7. الاختبارات العدائية المطلحة (fixture حقيقية غير فارغة)

**تصميم الفيكشر**: شموع LTF دقيقة واحدة لعدة ساعات بتوقيت UTC، بنمط سلّمي ينتج فعلاً تأرجحات
وUP/DOWN على مقياسي 15min و60min، مع: (أ) دلو جارٍ في النهاية؛ (ب) بار عند حد الإغلاق
الصريح؛ (ج) ارتفاع سعرٍ حاد (spike) داخل دلو لم يكتمل؛ (د) ثغرة تغذية محذوفة الشموع؛
(هـ) لحظة تعارض فعلية بين المقياسين. تُثبت الاختبارات أن الفيكشر يولّد حالات/انتقالات/تعارضًا
حقيقياً (درس فيكشرات 4B-1 الفارغة)، وتُختبر العكسية بتعطّل متعمَّد مرة.

1. **هجمات الحد الزمني (المحور الزمني)** عند `end−1min` / `end` / `end+1min`: قبل الحد
   آخر دلو مرئي هو السابق وحقول الجديد NA؛ عند الحد الدلو جديد نهائي وعلم الدفعة=True؛ بعد
   الحد نفس القيم بلا تغيير.
2. **تسريب الـspike**: أعلى/أدنى الدلو الجاري لا يظهران في أي `last_completed_htf_*` ولا في
   حالة/توافق حتى إغلاق الدلو؛ يظهران بعدها بقيم الدلو النهائية.
3. **إلحاق مستقبلي**: بناء على تاريخ كامل ومبتور؛ بادئة كل المكونات ≤T متطابقة حرفياً
   (check_exact)، وجداول الدلو/البنية/الانتقالات المقيّدة بالإتاحة متطابقة (مماثل اختبار
   `truncation_table_state` المغلق في 5.1 واختبار truncation في 5.2).
4. **نفس-الدفعة/نفس الطابع**: العلم True عند الحد الصريح؛ محاولة اختراع ترتيب (تسلسل داخلي/
   ادعاء سبق HTF) مرفوضة؛ لا أعمدة ترتيب ضمن الدفعة.
5. **timezone/DST**: نفس البيانات بفهرس UTC وAmerica/New_York تعطي جداً وقيمًا متطابقة
   (امتداد اختبار 5.1 DST المغلق).
6. **الثغرات والإتاحة المرصودة**: دلو انقضى نظرياً بلا بار مرصود عند/بعد end لا يُكشف؛ متى
   وُجد أول بار متأخر يظهر بقيمه المرصودة و`source_bar_count` الصحيح وPARTIAL مع cadence؛
   بلا cadence العلم UNKNOWN_COVERAGE؛ لا ملء ولا افتراض اكتمال.
7. **التغطية**: عدّ متوقع صحيح (دلو كامل ⇒ FULL؛ ناقص ⇒ PARTIAL)؛ عقد إيقاع غير قياسي
   (مدة لا تقبل القسمة) ⇒ خطأ إعداد؛ حالة قبل أول دلو ⇒ UNAVAILABLE.
8. **التزوير وإعادة البصمة المتماسكة**: تغيير خلية ⇒ السلامة الذاتية ترفض؛ تبديل مدة مقياس
   مع إعادة حساب كل البصمات لكن بنفس الإعداد المجمّد ⇒ رفض المخطط/الهوية؛ تزوير available_at
   مبكّر ⇒ رفض «future availability»؛ إعادة طلاء حالة عند نفس available_at ⇒ رفض 5.2.
9. **انحراف المرآيا**: صنفة محرك شريرة (تضيف/تحذف/تعيد ترتيب عموداً عاماً في 5.1/5.2 أو
   مخرجات السلسلة) ⇒ التحقق الديناميكي يرفض البناء (وريث بلوكر 4B-2).
10. **المحور الموضعي**: POSITIONAL ⇒ رفض صريح لـ4C.
11. **الجدار الناري وAST**: لا استيراد لرمز خاص `_` من وحدات CLOSED (اختبار AST على غرار
    4B-2)؛ لا شيء حي يستورد research؛ لا مستورد لـstage4c غير اختباره.
12. **non-vacuous حقيقي**: assert وجود ≥1 انتقال UP/DOWN على HTF، ≥1 تعارض بين المقاييس،
    ≥1 علم نفس-دفعة True، و≥1 دلو PARTIAL/UNKNOWN في الفيكشر.
13. **passthrough والتشديد**: إلحاق عمود أجنبي بنهاية إطار مملوك ⇒ رفض؛ حقن وسطي في الجداول
    المملوكة ⇒ رفض (المساواة الكلية الجديدة)؛ فحص أعمدة passthrough المشتقّة مقابل السوق.
14. **volume مختوم/غير مختوم**: الحالتان تعملان؛ لا عمود حجم HTF يُولَّد في V1 أبداً.
15. **الحدود**: BAR_PRE_CLOSE مرفوض، cross-timeline مرفوض، إعادة بناء الأدابتر والتحقق من
    المفتاح، الاستقرار تحت إعادة بناء السطح المستقبلي قانوناً.
16. **معادّ بناؤه مستقل**: تشغيل 5.1+السلسلة+5.2 مباشرةً في الاختبار ومطابقة مخرجات السطح
    حرفياً (لا مقارنة الشيء بنفسه).

---

## 8. الملفات التي سيسمح لـBUILD المستقبلي بتغييرها (لا تغيير الآن)

- جديد فقط: `src/trading_system/research/trajectory/trajectory_stage4c.py`
  و`tests/test_trajectory_stage4c.py`.
- لا تعديل أي وحدة CLOSED؛ المانيفست لا يُلمس أثناء BUILD/PATCH، فقط في طقم إغلاق لاحق
  (حينها يُضاف الملفان + ختم + ميلستون وتُعاد بصم STATUS/FINAL_VALIDATION على الاصطلاح
  المثبت في إغلاق 4B-2).
- لا تُلمس README/HANDOFF_MAP/SNAPSHOT/ARCHITECTURE (مجمّدة).

## 9. حدود لغوية/دلالية ملزمة في الكود والمانيفست
`trajectory_stage4c_manifest()` يصرّح: MTF/HTF surfaces = IMPLEMENTED عند الإغلاق؛
HTF_ENTITY_SURFACES (سيولة/OB/FVG/نطاق على HTF) = NOT_IMPLEMENTED؛ DESCRIPTORS, ESTIMANDS,
MODEL, GEOMETRY, EXECUTION = NOT_IMPLEMENTED؛ WIN_LOSS = FORBIDDEN؛ DEBT-020..025 = OPEN.
لا score/weight/probability/SUPPORT/Signal في أي اسم عمود أو وثيقة.

## 10. أسئلة مفتوحة تمنع BUILD إن بقي أحدها بلا قرار (للمخ/المالك)
- **Q1 (الأهم) — سلوك PARTIAL**: التوصية عرض الدلو الناقص بصدق مع علم PARTIAL/UNKNOWN وعدم
  حذفه أو ملءه (أمانة وقائعية؛ أهلية الاستهلاك تُحسم لاحقاً). البديل: fail-closed يحجب الدلو
  الناقص كله. يحتاج قراراً صريحاً قبل BUILD.
- **Q2 — حصر المحور الزمني**: التوصية TIME_INDEXED فقط ورفض POSITIONAL (تأكيد).
- **Q3 — نطاق حقائق HTF**: التوصية V1 = OHLC المكتمل + حالة البنية + مصفوفة 5.2 + الانتقالات؛
  وتأجيل كيانات/دورات حياة HTF (سيولة/OB/FVG/DR على HTF) لوحدة لاحقة، وتأجيل volume.
- **Q4 — لا مقاييس افتراضية**: المجموعة كلها إدخال بحث صريح مُجمَّد (تأكيد).
- **Q5 — الرؤية عند الحد الصريح**: التوصية اتباع العقد المغلق (ظهور عند `end` في نفس الدفعة
  مع علم عدم الترتيب) لا التأجيل لـ`end+1` (تأكيد).
- **Q6 — التسمية/الإصدار**: `trajectory_stage4c.py`، صنف واحد `Stage4CMTFSurface` بمجال
  ثابت `MTF_HTF`، إصدار `CAUSAL_MTF_TRAJECTORY_SURFACE_V1` (تأكيد/تعديل).
- **Q7 — غنى جدول بنية HTF**: التوصية ربط المخرج الكامل لسلسلة 2.1A/B/C على الدلو، لا
  `structure_state_after` فقط (منع ألعاب الاكتفاء بالمستهلك).
- **Q8 — فهرسة تشغيل السلسلة على الدلو**: تأكيد أثناء BUILD أن 2.1A يقبل فهرسة الدلو الزمنية،
  وإلا فهرس موضعي Int64 مع بقاء الأزمنة أعمدة (اختبار إلزامي، لا أثر دلالي).

## 11. STOP
سُلِّم DESIGN A كاملاً. لا أطلب BUILD في هذا الرد. التالي بحسب البروتوكول: DESIGN B مستقل،
ثم مقارنة ثالثة بين التصميمين، ثم قرار المالك؛ لا كود قبل ذلك.

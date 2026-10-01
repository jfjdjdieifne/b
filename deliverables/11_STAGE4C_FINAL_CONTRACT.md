# STAGE 4C — DESIGN ONLY — CONSOLIDATED FINAL CONTRACT (نتيجة المراجعة الثالثة)

```text
الحالة المرجعية: Stage 4B-2 V1 = CLOSED. MANIFEST = 170/170.
SHA256 = 1a21753f2de85bfbb56d0ae2ba4bcc7a5273cb9c42a2e6b9010d4a57ac469a12.
هذا العقد النهائي الموحَّد يدمج Design A + Design B + قرارات المراجعة الثالثة، ويحسم بلوكر
سياسة البنية بأدلة من الكود العام المغلق وتجارب خارج الشجرة (/tmp). DESIGN ONLY: لم يُعدَّل أي
ملف في src/tests/docs/MANIFEST. ينتهي بـSTOP.
```

---

## 0. القرار الأهم: تقسيم Stage 4C إلى وحدتين (نتيجة تحقيق السياسة)

```text
4C-1 (جاهز للبناء الآن):   Raw HTF OHLC truth + coverage metadata + as-of projection.
4C-2 (ليست جاهزة، مؤجَّلة): HTF structure + transitions + MTF confluence (5.2).
```
السبب: بنية HTF تتطلب سياسة تأرجح (تأكيد قمة/قاع)، ولا يوجد عقد قيمها الشرعي في الشجرة
دون معايرة جديدة؛ والمعايرة ممنوعة في مرحلة Raw Future Truth. تفاصيل التحقيق بالأدلة في
القسم 8. محرك 5.2 المغلق **يستطيع قانونياً تمثيل غياب البنية** (تجربة مثبتة)، فلا بلوكر
تقني؛ يبقى بلوكر قرار/تصميم يخص 4C-2 وحدها، ولا يمنع بناء 4C-1.

---

## 1. القرارات المعتمدة المطبَّقة حرفياً (من المراجعة الثالثة)

1. المعمارية من B: سطح لكل مقياس + سطح تركيب؛ لكن مع التقسيم: سطح المقاييس في **4C-1**،
   وسطح التركيب في **4C-2** (يعتمد بنية غير متوفرة في 4C-1).
2. كل إطارات 4C **مشتقة فقط (derived-only)**؛ صفر أعمدة سوق ممررة (passthrough)؛ ربط السوق
   عبر ختم التايم لاين + reconstruction hash؛ **مساواة مخطط كلية صارمة** لكل إطار (تُغلق نهج
   passthrough/حقن-العمود-الأوسط الذي بقي NON-BLOCKING منذ 4A/4B-2).
3. TIME_INDEXED حصراً؛ POSITIONAL مرفوض بخطأ عقد صريح.
4. لا مقاييس/مدد/أرقام افتراضية؛ كلها إدخال صريح مُجمَّد في الهوية.
5. حد الإغلاق: الكشف عند `timestamp == bucket_close` قانوني فقط لنفس التايم لاين وبطور
   `COMPLETED_ROW_AVAILABLE`؛ `BAR_PRE_CLOSE` مرفوض؛ عند التساوي
   `close_batch_order_unknown=True` ولا يُدّعى أي ترتيب داخل الدفعة.
6. دلالة الإتاحة مُصحَّحة (القسم 3): `first_observed_asof_*` (اسم مفروض من عقد 5.1 يبقى)
   يُغلَّف بصفته **projectable/observed-as-of داخل التايم لاين المختوم**، لا وصول فيد ولا
   إتاحة سوق تاريخية.
7. عقد الشبكة اختياري، بأسماء الحالات غير المضخمة الخمسة (القسم 4)؛ التطابق يثبت اكتمال
   **المشاهدات بالنسبة للشبكة المعلنة والبيانات المختومة** فقط.
8. OHLC الدلو الناقص يُعرض كـ«OHLC للمشاهدات المختومة داخل الدلو» مع metadata النقص؛ لا حجب
   في Raw Truth؛ أهلية الاستهلاك البحثي لاحقة خارج 4C.
9. نطاق 4C-1: OHLC HTF للمشاهدات + coverage + إسقاط as-of فقط. لا حجم HTF، لا سيولة/
   OB/FVG/Dealing Range على HTF، لا بنية/انتقالات/توافق (تلك 4C-2).
10. عقد الشبكة عقد timestamp مجرد؛ لا ادعاء 24×7 ولا تقويم سوق؛ sessions/calendars خارج V1.
11. سياسة الأخطاء من B: Contract/Config منفصلة عن Data، fail-closed، عدم ابتلاع السبب الجذري.
12. الديون 020..025 OPEN؛ لا score/weights/probability/SUPPORT/model/geometry/execution/
    signal/PnL/WIN-LOSS.

---

## 2. العقد النهائي لسطح 4C-1 (للبناء)

### 2.1 إعداد الإدخال
```python
@dataclass(frozen=True)
class HtfScaleSpec:
    name: str                 # آمن regex 5.2: [A-Za-z][A-Za-z0-9_]*؛ فريد؛ لا افتراضات
    duration: pd.Timedelta   # موجب؛ يُمرَّر لـTimeAggregationSpec المغلق؛ يُربط بالنانوثانية

@dataclass(frozen=True)
class CadenceGridContract:   # اختياري؛ عقد timestamp مجرد، لا تقويم ولا 24×7
    grid_epoch_utc: pd.Timestamp   # tz-aware، نقطة محاذاة الشبكة
    period: pd.Timedelta           # موجب؛ مدة كل مقياس يجب أن تكون من مضاعفاته على الشبكة

def build_htf_scale_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimeIndexedTimelineAdapter,
    market_history: pd.DataFrame,            # نفس الإطار المختوم LTF
    scale_spec: HtfScaleSpec,                # مقياس واحد لكل بناء (سطح لكل مقياس)
    cadence: Optional[CadenceGridContract] = None,   # None ⇒ اكتمال الشبكة UNKNOWN
) -> "Stage4CHtfScaleSurface": ...
```
فحوص فاشل-مغلق عند الإدخال (تُصنَّف حسب القسم 7):
- `timeline.verify(adapter, market_history)` أولاً؛ نوع الأدابتر يجب TIME_INDEXED.
- اسم المقياس آمن/غير فارغ؛ المدة موجبة (يثقّلها أيضاً 5.1)؛ لا قوائم مقاييس ضمنية.
- إن وُجد cadence: لكل مدة، `duration` من مضاعف `period` ومحاذَى لـ`grid_epoch` على شبكة
  UTC الحقبة، وإلا خطأ عقد (حساب قياسي بلا نسبة تسامح/عتبة).
- أي استثناء من 5.1 يُمرَّر بدلالته (القسم 7)؛ لا fallback.

### 2.2 الصنف المجمَّد: `Stage4CHtfScaleSurface`
المجال ثابت على مستوى الصنف `domain = "HTF_SCALE_RAW"` (لا حقل يضبطه المستدعي — منع
تبديل المجال، درس بلوكر 4B-2). حقول الهوية:
```text
domain, contract_version (= CAUSAL_HTF_RAW_TRAJECTORY_SURFACE_V1),
timeline_id, timeline_hash, adapter_kind,
scale_name, scale_duration_ns, cadence_contract_hash | None,
reconstruction_input_hash,
bucket_observations_hash, asof_projection_hash, mirror_verification_hash,
surface_id,
asof_bar_frame, bucket_frame          # مشتقان فقط (derived-only)، قابلان للتغير ⇒ فحص ذاتي
```

### 2.3 مخطط `bucket_frame` (مملوك كلياً، صف لكل دلو مُصدر من 5.1)
أعمدة 5.1 المغلقة تُحفظ بأسمائها الحرفية (مطابقة المرآة، بلا إعادة تسمية):
```text
scale_name
bucket_start_utc, bucket_end_utc, theoretical_available_at,
first_observed_asof_position (Int64), first_observed_asof_time,
first_source_timestamp, last_source_timestamp, source_bar_count,
open, high, low, close                 # OHLC المشاهدات المرصودة داخل الدلو (مخرجات 5.1 الحرفية)
expected_grid_bar_count (Int64 nullable؛ NA بلا عقد شبكة)
missing_grid_observation_count
off_grid_observation_count
coverage_status
```
الدلالة: `open/high/low/close` هي **OHLC المشاهدات المختومة داخل الدلو** كما يحسبها 5.1 من
الشموع المرصودة حصراً؛ عند وجود نقص شبكي يحمل `coverage_status` ذلك (القسم 4)؛ لا ادعاء أنها
OHLC السوق الكامل للدلو. لا عمود volume (خارج V1).

### 2.4 مخطط `asof_bar_frame` (مشتق فقط على فهرس LTF، صف لكل بار قرار)
لكل مقياس، أسماء ببادئة المقياس (نمط 5.2)؛ لا أي عمود سوق:
```text
<scale>__completed_bucket_end_utc            مرآة last_completed_htf_end_utc لـ5.1
<scale>__completed_bucket_open
<scale>__completed_bucket_high
<scale>__completed_bucket_low
<scale>__completed_bucket_close
<scale>__observed_source_bar_count           مرآة last_completed_htf_source_bar_count
<scale>__expected_grid_bar_count             Int64 nullable (NA بلا عقد)
<scale>__missing_grid_observation_count
<scale>__off_grid_observation_count
<scale>__coverage_status                     GRID_*/UNAVAILABLE
<scale>__projectable_asof_position          أول موضع رصد للدلو المُسقَط على الصف
<scale>__projectable_asof_time_utc          أول زمن رصد (تغليف first_observed_asof_time)
<scale>__close_batch_order_unknown           bool: projectable_asof_time == t الصف
```
قبل أول دلو قابل للإسقاط: `coverage_status = UNAVAILABLE`، الحقول الزمنية/السعرية NA،
العدّادات المرصودة صفر، عدّادات الشبكة المتوقعة NA. الدلو الجارٍ (نهايته > آخر طابع مرصود)
لا يُصدره 5.1 ولا تخترعه 4C.

### 2.5 البنية غير المكوّنة في 4C-1 (إعلان صدق)
لا أعمدة بنية/حالة/انتقال في أي إطار 4C-1. حمولة الهوية ومانيفست الوحدة يصرّحان:
`HTF_STRUCTURE_STATUS = NOT_CONFIGURED_IN_4C_1` و`MTF_CONFLUENCE_SURFACE = NOT_STARTED`.
لا تُنتَج قيمة UNDEFINED زائفة توحي ببنية فُحصت؛ الغياب يُعلن كغياب إعداد، لا كحالة سوق.

---

## 3. تصحيح دلالة الإتاحة (البلوكر المفاهيمي الذي رفعته المراجعة)

للحظات الأربع تعريفات منفصلة لا تُخلط:
- **أصل الدلو (origin)**: نافذة CLOSE_TIME `(start, end]` على شبكة UTC الحقبة (حساب قياسي
  لـ5.1 من المدة).
- **النهاية المجدولة النظرية** `theoretical_available_at = bucket_end`: موعد إغلاق الدلو لو
  اكتمل الإيقاع؛ **شرط ضروري لا كافٍ للإتاحة، وليست وعد وصول فيد**.
- **قابلية الإسقاط المرصودة as-of** `first_observed_asof_position/time` (الاسم الأصلي من عقد
  5.1 يبقى كما هو في الجداول المطابقة للمرآة؛ وفي الإسقاط المشتق نغلّفه باسم
  `projectable_asof_*`): **أول صف LTF داخل التايم لاين المختوم طابعه ≥ نهاية الدلو**
  (بحث 5.1 `searchsorted` على الطوابع المرصودة). هذا هو **أصغر موضع/زمن تصبح عنده مخرجات
  الدلو قابلة للإسقاط as-of وفق عقد 5.1 على البيانات المختومة**.
- **InformationKey القانوني** لكشف الدلو يُبنى عند موضع الرصد الأول هذا، على تايم لاين LTF،
  بطور COMPLETED_ROW_AVAILABLE؛ BAR_PRE_CLOSE مرفوض؛ مفاتيح عبر تايم لاين مختلف مرفوضة.

نفي صريح يوثَّق في الكود والمانيفست:
> `projectable_asof` لا يثبت أن نتيجة الدلو وصلت من المُغذِّية عند ذلك الزمن، ولا أنها لم تكن
> متاحة في السوق قبله؛ فجوة صفوف LTF قد تعني فقط أن السجل المختوم لا يحمل مشاهدات هناك. إنه
> حد إسقاط داخل البيانات المختومة وفق عقد 5.1، لا feed-arrival provenance ولا market
> availability. البروفينانس التوليدية التاريخية تبقى NOT_CERTIFIED/UNVERIFIABLE.

عند التطابق التام (رصيد منتظم): بار LTF المُغلِق هو آخر شمعة مصدرية في الدلو (عضوية
`(start,end]` مؤكدة تجريبياً: 08:15 تنتمي لدلو ينتهي 08:15) وهو أول راصد؛ OHLC الدلو دالة
حتمية في شموع ≤ end (لا تسريب)، لكن إغلاق LTF وإغلاق HTF نفس دفعة المعلومات ⇒
`close_batch_order_unknown=True`، و`deterministic_sequence` تسلسل منطقي لا chronology.

## 4. عقد الشبكة والتغطية (أسماء وادعاءات مصحَّحة)

`CadenceGridContract(grid_epoch_utc, period)` عقد timestamp مجرد. لكل دلو تُقارَن **مجموعتا
طوابع** (فحص مجموعات، لا عدّ): المتوقعة على الشبكة داخل `(start,end]` مقابل المرصودة فعلاً
في السجل المختوم:
```text
GRID_OBSERVATIONS_COMPLETE   المجموعتان متطابقتان حرفياً (لا نقص ولا دخيل)
GRID_OBSERVATIONS_MISSING    يوجد نقص شبكي (missing > 0)، لا دخيل
OFF_GRID_OBSERVATIONS_PRESENT يوجد طابع مرصود خارج الشبكة، لا نقص
GRID_OBSERVATIONS_DEFECT_BOTH نقص ودخيل معاً
GRID_COMPLETENESS_UNKNOWN    بلا عقد شبكة (source_bar_count المرصود يبقى حقيقة، بلا ادعاء كمال)
UNAVAILABLE                  قبل أول دلو قابل للإسقاط على LTF
```
حد الادعاء: تطابق المجموعات يثبت **اكتمال المشاهدات بالنسبة للشبكة المعلنة داخل البيانات
المختومة** فقط. لا feed completeness، لا market completeness، لا إثبات أن شيئاً لم يحدث في
السوق. لا أرقام سحرية؛ الشبكة/الإيقاع إدخال صريح مربوط بالهوية. الدلو الجاري لا يُقيَّم.

## 5. الهوية، البصمات، السلامة، البادئة (4C-1)
نطاقات canonical_sha256:
`STAGE4C1_RECONSTRUCTION_INPUT_V1` (timeline + المقياس name/duration_ns + بصمة عقد الشبكة)،
`STAGE4C1_BUCKET_OBSERVATIONS_V1` (bucket_frame كامل)،
`STAGE4C1_ASOF_PROJECTION_V1` (asof_bar_frame كامل)،
`STAGE4C1_MIRROR_EQUIVALENCE_V1` (مقارنة المخرجات المُعاد بناؤها من 5.1)،
`STAGE4C1_SCALE_SURFACE_IDENTITY_V1` (تؤلف ما سبق + الصنف الثابت + الإصدار).
- السلطة الدفاعية من **الصنف الثابت + حمولة الإعداد المجمّدة**، لا من حقل domain ولا من
  بصمة معاد حسابها. تبديل المدة/الاسم يكسر الهوية حتى تحت بصمات متسقة ذاتياً.
- `verify_surface_integrity`: يعيد حساب كل البصمات من المحتوى الحالي؛ يفرض **مساواة المخطط
  الكلية** لإطارين مشتقين فقط (إضافة/حذف/إعادة ترتيب/حقن أوسط ⇒ رفض فوري)؛ يتحقق من قيم
  coverage ومنطقها واتساق projectable/theoretical؛ ويعيد بناء 5.1 فعلياً على السوق المختوم
  ويطابق المخرجات المخزنة حرفياً (مرآة ديناميكية؛ محرك شرير يضيف/يحذف/يرتّب عموداً عاماً ⇒
  رفض). مرايا المخطط محلية Final لـ4C، مسنودة بالبناء الفعلي، **لا استيراد رمز `_`**.
- `project_htf_scale_prefix(*, surface, boundary_key) -> Stage4C1PrefixBinding`:
  - A. asof_bar_frame صفوف 0..T (reset_index(drop=True) قانوني)؛
  - B. bucket_frame صفوف حيث `first_observed_asof_position ≤ T`؛
  - C. بصمة حمولة الإعداد (هوية لا صفوف).
  - البادئة تربط المحتوى الوقائعي فقط؛ هوية التايم لاين/السطح/الحد في حقن الـbinding.
  - إلحاق مستقبل قانوني يغيّر هوية السطح الكاملة ويُبقي بادئة T ثابتة.
- البروفينانس: كل الهويات شهود إعادة بناء حتمية؛ NOT_CERTIFIED/UNVERIFIABLE للتوليد التاريخي.

## 6. جدول الأصل / قابلية الإسقاط / الطور (4C-1)
| فئة الحقل | الأصل | يُسقَط/يُرى عند | الطور |
|---|---|---|---|
| OHLC الدلو، source_bar_count | شموع مرصودة في `(start,end]` | موضع الرصد الأول الفعلي للدلو | COMPLETED_ROW_AVAILABLE |
| theoretical_available_at/end/start | حساب شبكي قياسي (أصل) | يُخزَّن مع الدلو، لا يكشف سعراً قبل الرصد | — |
| إسقاط asof لكل بار i | دلوه قابلة للإسقاط عند/قبل i | بار i | COMPLETED_ROW_AVAILABLE |
| عدّادات/حالة الشبكة | مقارنة مجموعات الطوابع | مع إسقاط الدلو المرتبط | COMPLETED_ROW_AVAILABLE |
| close_batch_order_unknown | مقارنة projectable_asof_time بـt_i | بار i | COMPLETED_ROW_AVAILABLE |
| البنية/الانتقالات/التوافق | غير موجودة في 4C-1 | لا تُسقَط (NOT_STARTED) | — |
BAR_PRE_CLOSE لأي حقيقة دلو ⇒ رفض؛ cross-timeline ⇒ رفض InformationKey وطبقة الهوية.

## 7. سياسة الأخطاء (معتمدة من B)
- **TrajectoryContractError** (عقد/إعداد): محور موضعي؛ مقياس فارغ/اسم غير آمن/مكرر؛ مدة غير
  صالحة؛ cadence غير محاذٍ/غير قياسي؛ نوع سطح خاطئ؛ طور حد غير قانوني.
- **TrajectoryDataError** (معطيات): رفض 5.1 للمحتوى؛ فشل تحقق التايم لاين؛ انحراف المرآيا
  الديناميكي؛ تناقض بصمات ذاتي؛ projectable أبكر من theoretical؛ تناقض coverage.
- عبور استثناءات المحرك المغلق مع حفظ الدلالة: `HTFConfigError` ⇒ Contract؛
  `HTFDataError` ⇒ Data؛ السبب الجذري محفوظ (`from exc`)، لا ابتلاع.
- عيوب الشبكة (نقص/دخيل/مجهول) **ليست أخطاءً**؛ UNAVAILABLE/UNKNOWN قِيَم عادية.

---

## 8. نتيجة التحقيق في سياسة بنية HTF (بالأسماء العامة الفعلية)

**ما نوع السياسة العامة؟**
- البروتوكول العام `SwingConfirmationPolicy` (Method `create_runtime()`) وتنفيذه العام
  الوحيد `EmpiricalConfirmationPolicy`، كلاهما عام ومُصدَّر من
  `trading_system.structure.swing_detector` ومن حزمة `trading_system.structure`
  (`__init__.py`) — لا شرطة سفلية، استهلاكه قانوني.
- حقوله العامة: `quantile: float` (إلزامي)، `prior_continuation_reversals: tuple=()`،
  `prior_confirmed_reversals: tuple=()`.

**من أين تأتي قيمها؟**
- `quantile` إلزامي **بلا افتراضي** (`SwingConfigError` إن غاب/خرج عن [0,1]). الوثيقة
  المعتمدة للوحدة 2.1A تنص حرفياً: مع تاريخ مرجعي فارغ العتبة NaN ولا يمكن التأكيد؛ الـpriors
  «افتراض نمذجة خارجي (external modeling assumption)»؛ والوحدة «لا تدّعي تعريف تأرجح أمثلي
  ذاتي الانطلاق». أي أن اختيار الكمّ قرار نمذجة/معايرة، لا حقيقة مغلقة.

**هل هي factual closed contract أم calibration تحتاج TRAIN؟**
- **calibration/اختيار نمذجة**، ليست عقداً مغلقاً مجمّداً. بحثت كامل الشجرة: لا ثابت كمّ
  قانوني واحد؛ `quantile=0.5` الوحيد يقع داخل `if __name__ == "__main__"` (ديمو تشخيصي
  ب priors صريحة)، ليس إنتاجاً ولا عقداً ولا مرجعية معتمدة.

**هل 4B-1 يربطها بهوية عامة قابلة لإعادة الاستخدام؟**
- 4B-1 يملك الحقل العام `swing_policy_hash` (موثَّق: «reconstruction witness؛ evidence-only
  when policy is None») ويصرّح أنه لا يصنع سياسة ولا قيمة. الدالتان
  `_swing_policy_payload/_swing_policy_hash` خاصتان (underscore) — **يُمنع استيرادهما**.
  Stage 3 لديه `_canonicalize_swing_policy` خاص بالمثل. النمط العام: كل مرحلة تبني بصمة
  سياسة محلياً لسياسة **مُمرَّرة إليها**؛ لا أحد يورّد سياسة. يمكن لـ4C تقليد نمط البصمة
  المحلي (إعادة استخدام المفهوم العام لا الرمز الخاص)، لكن هذا لا يؤمّن السياسة نفسها.

**هل استعمال نفس السياسة عبر HTF scales له أساس في العقد؟**
- لا. تطبيق كمّ تأكيد مُعايَن على LTF (أو مختار بلا أساس) على دلوه HTF افتراض نقل cross-scale
  جديد غير مثبت؛ الوثيقة تصنّف priors أصلاً افتراضاً خارجياً. لا يجوز في Raw Truth تمريره
  كحقيقة.

**الدليل التجريبي (/tmp، خارج الشجرة):**
- `confirmation_policy=None`: 16/16 ثم 200/200 دلو HTF بحالة UNDEFINED (لا بنية إطلاقاً).
- سياسة صريحة `EmpiricalConfirmationPolicy(quantile=0.25)` بلا priors: 25/200 حالة UP على
  15د، 6/50 على 60د؛ وq=0.75: صفر تأكيد — يثبت أن الناتج تحكمه قيمة الكمّ المختارة (قرار
  نمذجة)، فلا جواب «فطري».
- فهرس إدخال السلسلة ليس دلالياً: DatetimeIndex دلوه 5.1 وRangeIndex كلاهما مقبول من 2.1A؛
  يُعتمَد فهرس 5.1 الزمني كما يُعاد (قرار Q8 محسوم).
- **تمثيل 5.2 لغياب البنية (البلوكر المحتمل):** إطار مكتمل فارغ لـ
  `causal_asof_align_scale_state` ⇒ كل الصفوف `available=False`/الحالة NA؛ و
  `CausalConfluenceMatrixEngine().analyze` ينجح قانونياً: `configured_scale_count=1،
  available_scale_count=0، availability_fraction=0.0، directional_conflict=False`. صفر مقاييس
  ⇒ `ConfluenceDataError('at least one scale')`؛ وخلط metadata مع available=False ⇒
  `ConfluenceDataError('unavailable metadata')`. أي 5.2 يمثّل NOT_CONFIGURED قانونياً، بشرط
  أن يبقى المقياس مُعَدّاً وكل حقوله NA عند عدم الإتاحة. **إذن لا بلوكر تقني.**

**القرار النهائي للسياسة:**
- لا quantile ولا default ولا تعلّم ولا افتراض نقل داخل 4C-1. بنية HTF/الانتقالات/التوافق
  تُؤجَّل إلى **4C-2**، التي تُفتتح فقط بعد مصدر شرعي للسياسة: (أ) عقد سياسة مغلق بكمّه من
  طبقة البحث TRAIN-only اللاحقة (المسار السببي الصحيح)، أو (ب) تفويض مالك صريح يصنّف سياسة
  بعينها عقداً إدخالياً مع الإعلان عن افتراض النقل كحدّ موثَّق. أي محاولة لاختراع كمّ في 4C
  تُرفض في مراجعة التصميم.

---

## 9. عقد سطح 4C-2 (محدَّد ومحجوز، NOT_STARTED — ليس للبناء الآن)

`Stage4CMtfConfluenceSurface` (مجال ثابت `MTF_CONFLUENCE`) يُبنى **فقط** عند توفر سياسة
شرعية، يستهلك أسطح مقاييس 4C-1 لنفس التايم لاين بعد التحقق منها، ويشغّل لكل مقياس سلسلة
2.1A→2.1B→2.1C المغلقة على `bucket_frame` (DatetimeIndex الدلوه كما تُعاد) بالسياسة
المعتمدة، ثم:
- `htf_structure_frame`: الناتج العام الكامل للسلسلة على الدلوه + scale_name +
  bucket_end_utc + first_observed_asof_position (مرآة محلية ديناميكية لمخطط السلسلة)؛
- `transition_event_frame`: صف عند اختلاف حالة المقياس عن الدلو السابق
  (scale_name, bucket_end_utc, first_observed_asof_position/time, prior_state, new_state,
  close_batch_order_unknown)؛ أحداث وقائعية، لا إشارة؛
- إسقاط حالات via `causal_asof_align_scale_state(available_at=first_observed_asof_time)` ثم
  `CausalConfluenceMatrixEngine`؛ `matrix_bar_frame` مشتق-فقط يحوي التجميعيات الأربعة عشر
  الحرفية وأعمدة 5.2 الخمسة لكل مقياس، بلا أي إعادة اشتقاق؛
- تمثيل قانوني لمقياس لم تتوفر له بنية: إطار alignment بـavailable=False وحقول NA (مثبت
  قبوله في القسم 8)، فيُعَدّ configured لكن available=0؛ صفر مقاييس ممنوع.
- بصمات/بادئة/سلامة على نمط 4C-1 (مكوّنات: matrix 0..T + structure/transitions بموضع رصد ≤T
  + معرّفات مكونات المقاييس وبصمة السياسة المعتمدة).
- يُمنع أي كمّ مهما كان مصدره داخل Raw Truth ما لم يكن عقداً مغلقاً/مُفوَّضاً كما في القسم 8.

---

## 10. قائمة الاختبارات العدائية النهائية

**الفيكشر (non-vacuous)**: شموع LTF دقيقة لساعات كثيرة باتجاهات سلّمية طويلة (تجارب B بيّنت
حاجة 4C-2 لاحقاً لـ~3000 شمعة لظهور بنية؛ 4C-1 يحتاج فقط دلوه مكتملة، دلو جارٍ، بار حد،
spike داخل الجاري، وثغرة محذوفة الشموع)؛ مقياسان 15د/60د؛ عقد شبكة 1min في جزء من
الاختبارات.

اختبارات 4C-1:
1. تسريب الدلو الجاري: high/low/close/end للدلو غير المغلق غائبة عن كل حقول asof حتى موضع
   الرصد الأول؛ spike داخله غير مرئي؛ بعد الإغلاق تظهر قيم الدلو النهائية.
2. الحد الصريح بالطور: عند end−دقيقة آخر مرئي هو السابق؛ عند end الدلو جديد مرئي وعلم
   close_batch_order_unknown=True ومفتاح COMPLETED_ROW_AVAILABLE؛ عند end+دقيقة بلا تغيير؛
   مفتاح BAR_PRE_CLOSE عند/قبل الحد مرفوض.
3. الثغرات وقابلية الإسقاط: دلو انقضى نظرياً بلا رصد لا يُسقَط بين end وأول بار متأخر؛ يُسقَط
   بعدها بقيمه المرصودة وsource_bar_count الصحيح؛ theoretical≠projectable محفوظان؛ لا أي
   حقل/وثيقة يسمّيه وصول فيد.
4. عقد الشبكة: الحالات الخمس بحالاتها الصحيحة (مجموعات الطوابع)؛ FULL فقط بالتطابق الحرفي؛
   شمعة 30ث دخيلة ⇒ OFF_GRID_OBSERVATIONS_PRESENT؛ نقص ⇒ GRID_OBSERVATIONS_MISSING؛ بلا عقد ⇒
   GRID_COMPLETENESS_UNKNOWN حتى مع عدّ مطابق؛ مدة غير مضاعف/غير محاذى ⇒ خطأ عقد.
5. إلحاق مستقبل بعد T: بناء كامل ومبتور؛ بادئة المكوّنين متطابقة حرفياً check_exact؛ جداول
   الدلو المقيَّدة بموضع الرصد متطابقة (امتداد test_truncation_table_state المغلق في 5.1).
6. نفس الطابع/الدفعة: العلم True عند الحد؛ رفض أي حقل/مفتاح يدّعي ترتيباً داخلياً؛ لا
   chronology مشتقة.
7. timezone/DST: نفس البيانات بفهرس UTC وAmerica/New_York تعطي أسطحاً متطابقة.
8. تبديل scale/duration: إعادة بناء بمدة أخرى تحت نفس الاسم/إعداد مختلف مع بصمات متسقة ⇒
   رفض الهوية والمخطط؛ لا التباس سطحين.
9. tampering + إعادة بصم متماسكة: تغيير خلية/حقل بصمة ⇒ السلامة ترفض؛ تزوير
   projectable_asof أبكر من theoretical ⇒ رفض Data؛ لا طلاء.
10. انحراف المرايا/المحرك الشرير: إضافة/حذف/إعادة ترتيب عمود عام في ناتج 5.1 ⇒ رفض التحقق
    الديناميكي.
11. cross-timeline: بادئات/مقارنات عبر تايم لاين مختلف ⇒ رفض.
12. POSITIONAL ⇒ رفض عقد؛ DatetimeIndex بلا tz ⇒ رفض.
13. derived-only الصارم: حقن عمود أجنبي في أي إطار (وسط أو ذيل) ⇒ رفض المساواة الكلية؛ لا
    وجود لأي عمود passthrough؛ فحص أن لا عمود سوق مكرر داخل الأسطح.
14. UNAVAILABLE: قبل أول دلو الحالة UNAVAILABLE والقيم NA/عدّادات صفر؛ الدلو الجاري غير موجود.
15. الدلو الناقص: OHLC المشاهدات معروض مع coverage الناقص بلا حجب ولا ملء.
16. تصنيف الأخطاء: مدة صفرية/اسم غير آمن/cadence غير محاذ ⇒ Contract؛ تغذية تالفة ⇒ Data؛
    عيب شبكة ⇒ ليس خطأً.
17. معاد-بناؤه المستقل: تشغيل 5.1 مباشرة في الاختبار ومطابقة bucket/asof حرفياً (لا مقارنة
    الشيء بنفسه).
18. volume: وجوده/غيابه لا يغير مخطط 4C-1 (لا أعمدة حجم HTF).
19. إثبات نطاق 4C-1: لا أعمدة بنية/انتقالات/توافق؛ المانيفست يصرّح HTF_STRUCTURE
    NOT_CONFIGURED وMTF_CONFLUENCE/HTF_ENTITIES NOT_STARTED؛ أي ظهور لها يفشل الاختبار.
20. **عكسية non-vacuous**: فيكشر مُعطَّل (شموع قليلة جداً/بلا إغلاق دلو) يجب أن يجعل
    اختبارات وجود دلو مكتمل/علم دفعة/حالة تغطية **تفشل** (يُشغَّل مرة واحدة إثباتاً أن
    الاختبارات ليست فارغة).

اختبارات جاهزية 4C-2 (تُكتب مع 4C-1 كتحقّق عقد لا كمخرج إنتاج):
21. إثبات أن 5.2 يقبل إطار مقياس بلا بنية (available=False كله) ويعطي
    configured/available=0/conflict=False؛ وصفر مقاييس يُرفض؛ metadata مع عدم الإتاحة يُرفض.
22. (مع 4C-2) هجمات البنية: لا بنية بلا سياسة؛ سياسة مُعتمدة فقط؛ كمّ مهمل/مخترع ⇒ رفض تصميم
    (واختبار حرس AST/مانيفست يمنع أرقام quantile داخل 4C).

## 11. مانيفست الوحدة (إعلانات 4C-1 عند الإغلاق)
`HTF_RAW_OHLC_SURFACE = IMPLEMENTED`؛ `COVERAGE_GRID_CONTRACT = IMPLEMENTED (optional)`؛
`HTF_STRUCTURE_STATUS = NOT_CONFIGURED_IN_4C_1`؛ `HTF_TRANSITIONS / MTF_CONFLUENCE_SURFACE =
NOT_STARTED (4C-2)`؛ `HTF_VOLUME / HTF_LIQUIDITY / HTF_OB / HTF_FVG / HTF_DEALING_RANGE =
NOT_IMPLEMENTED`؛ `DESCRIPTORS/ESTIMANDS/MODEL/GEOMETRY/EXECUTION = NOT_IMPLEMENTED`؛
`WIN_LOSS = FORBIDDEN`؛ `RESEARCH-DEBT-020..025 = OPEN`؛ سطر صريح:
`PROJECTABLE_ASOF_IS_SEALED_TIMELINE_PROJECTION_NOT_FEED_ARRIVAL_PROVENANCE`.

## 12. الملفات المسموحة للبناء (لاحقاً، عند كتلة BUILD فقط)
- جديد حصراً: `src/trading_system/research/trajectory/trajectory_stage4c.py`
  و`tests/test_trajectory_stage4c.py` (محتوى 4C-1 في V1؛ 4C-2 توسعة مستقبلية بعد إغلاق
  4C-1، إما بنفس الوحدة تحت إصدار أو وحدة منفصلة يحددها تفويض لاحق).
- لا تعديل أي وحدة CLOSED؛ المانيفست لا يُلمس أثناء BUILD/PATCH (يُحدَّث في طقم الإغلاق على
  اصطلاح 4B-2 المثبت: src+test+ختم+ميلستون، إعادة بصم STATUS/FINAL_VALIDATION، الملفات
  الأربعة المجمدة لا تُلمس). لا وثائق شجرة أثناء التصميم.

## 13. BUILD READY والبلوكرات
```text
BUILD READY (4C-1 Raw HTF OHLC + coverage + as-of): YES — لا بلوكر تقني ولا مفاهيمي متبقٍّ.
BUILD READY (4C-2 structure/transitions/confluence): NO — بلوكر قرار/تصميم وحيد:
  مصدر سياسة التأكيد الشرعي (عقد مغلق من طبقة البحث TRAIN-only، أو تفويض مالك صريح).
  لا يُسمح بأي كمّ quantile/default/افتراض نقل داخل 4C.
```
قرار مطلوب من المالك/المخ قبل كتلة البناء: اعتماد تقسيم 4C-1/4C-2 ونطاق 4C-1 كما هنا
(توصية: اعتماد؛ هو الوحيد الذي يبني حقيقة خام نقية بلا معايرة، ويستخدم 5.1 بالكامل ويحجز 5.2
لاستخدامه الصحيح لاحقاً).

## 14. STOP
عقد 4C النهائي الموحَّد سلِّم. لا BUILD نُفِّذ ولا ملف شجرة عُدِّل. التالي قرار اعتماد
المالك/المخ، ثم كتلة BUILD ONLY لـ4C-1 بصيغة الملفين الحصريين.

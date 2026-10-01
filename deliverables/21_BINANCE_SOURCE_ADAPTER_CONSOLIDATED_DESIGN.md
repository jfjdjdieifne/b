# BINANCE SOURCE ADAPTER — CONSOLIDATED DESIGN — PENDING OWNER APPROVAL

**التقرير 21 — بيلدر | 2026-09-27 (دمشق)**
**المرحلة**: BINANCE SPOT SOURCE ADAPTER / PROJECT INTEGRATION — **DESIGN ONLY**
**الحالة**: تصميم موحّد واحد — لا كود، لا تعديل ملف، لا تنزيل بيانات، لا 4C-2، لا Reality Check تنفيذي.

---

## 0) الحقائق المعطاة (INPUT FACTS — مُعتمَدة كما وردت)

| البند | القيمة |
|---|---|
| Stage 4C-1 | CLOSED |
| MANIFEST | 174/174 — `ac4d6f03e457695da1b3132856c424ffe5bc043d8545b5cce279fce856c51706` |
| المصدر | `BTCUSDT-aggTrades-2026-05.csv` — `86d4f3d335ae244dcc143569bd1cc382320027c3fe4702e5d3ddf0757e8f1c04` |
| صفوف | 21,080,265 قانونية / 0 sentinel / 0 فاسد |
| الفترة | `2026-05-01T00:00:00.365107Z → 2026-05-31T23:59:59.698477Z` |
| الدقائق | 44,640 مخرجة = 44,640 مغطاة = 0 مفقودة (كل دقيقة تقويمية — بلا synthetic) |
| المصالحة | base `425331.03039000` = `425331.03039000` ؛ quote `33245850882.8835241000000000` = نفسه ؛ exact كلها true |
| minute facts | `a6a06c4c583e64e7613ddca275533a15062ab13864482cacf30b2f125094601f` |
| الغموض الفعلي | tie_timestamp_count **1,434,513**؛ ambiguous_open **2,065**؛ ambiguous_close **2,089** |
| TIE_ORDER_CONTRACT | **NOT_PROVEN** — الاختيار `(transact_time_us, agg_trade_id)` deterministic convention فقط |

**العقد المُصرَّح (كما أوجزته)**: `is_buyer_maker=False → BUY initiated executed volume`، `True → SELL initiated` — **EXECUTED/INITIATED FLOW لهذا المصدر فقط**؛ لا buying pressure، لا order-book pressure، لا institutional/whale، لا market-wide. **ممنوع على الـAdapter إخفاء حقيقة الغموض.**

ملاحظة تنفيذية: المحوّل لا يُعدَّل؛ الأرقام أعلاه سلسلة الشهادات المرجعية التي يُبنى عليها العقد أدناه.

---

## 1) خريطة العقود العامة الحالية التي ستُعاد استخدامها (قراءة الكود الفعلي)

السلسلة المعتمَدة (كلها public API فقط — لا إعادة كتابة):

| الطبقة/الوحدة | الصنف العام | العقد المُدخل |
|---|---|---|
| 0.1 | `audit.causal_state` (`CausalEngineProtocol`, re-entrancy audit) | إطار إعادة استخدام/تدقيق |
| 0.2 | `core.causal_percentile.CausalPercentileTracker`, `core.causal_adaptive_smoothing.CausalAdaptiveEMA` | ملاحظات قياسية |
| 1.1 | `environment.dynamic_volatility.DynamicVolatilityEngine` | `high/low/close` (قابلة للتسمية) |
| 1.2 | `environment.session_context.CausalSessionContextEngine` | **DatetimeIndex tz-aware فقط** |
| 2.1A | `structure.swing_detector.CausalAdaptiveSwingDetector` | `high/low` فقط |
| 2.1B | `structure.swing_sequence.ConfirmedSwingSequenceEngine` | أعمدة أحداث 2.1A |
| 2.1C | `structure.structural_breaks.CausalStructuralBreakEngine` | `high/low/close` + أعمدة 2.1A/2.1B |
| 2.2 | `liquidity.liquidity_map.CausalLiquidityMapEngine` | `high/low/close` + أعمدة 2.1A/2.1B |
| 3.1 | `orderflow.volume_delta.CausalVolumeDeltaEngine` + `OrderFlowMode` | ACTUAL: `buy_volume,sell_volume[,volume]` — PROXY: OHLCV كامل |
| 3.2 | `orderflow.absorption.CausalAbsorptionEvidenceEngine` | ACTUAL: سطح 3.1 ACTUAL + `close` — PROXY: OHLCV + سطح 3.1 PROXY |
| 4.1 | `zones.order_blocks.CausalOrderBlockEngine` | OHLC + سطح 2.1x |
| 4.2A | `zones.fvg.CausalFVGEngine` | OHLC (هندسة صارمة) |
| 4.2B | `zones.dealing_range.CausalDealingRangeEngine` | `close` + سطح 2.1x |
| 5.1 | `multitimeframe.causal_htf.CausalHTFAggregator` | OHLC [+volume] — **`BarTimestampSemantics.CLOSE_TIME` حصراً**، `(start,end]` |
| 5.2 | `multitimeframe.confluence_matrix.CausalConfluenceMatrixEngine` | أسطح scale states |
| 6.1A | `decision.evidence_vector.CausalEvidenceVectorEngine` | سطح features مُصدَّق |
| 6.1B | `decision.narrative.CausalMarketNarrativeEngine` | سطح 6.1A + manifest |
| 6.2A-0 | `research.information_time` (`InformationKey/InformationPhase/Adapter`), `research.visibility` (`AsOfVisibilityProjector`, `FrozenDecisionSnapshotBundle`, `VisibleAsOfBundle`) | مفاتيح/إسقاط as-of |
| 6.2A-1 | `research.outcome_observer.FactualHypothesisOutcomeObserver` | `TimelineAdapter` فقط |
| 6.2A-4 S1 | `research.trajectory.trajectory_contract.MarketObservationTimeline` (`seal/verify/key_for_position`), `DecisionAnchor` | market_history = **OHLC إلزامية** + volume اختياري |
| 6.2A-4 S2–4 | `trajectory_stage2/3/4a/4b1/4b2/4c` (`build_stage2_trajectory`, `_run_closed_structure_chain` = إعادة استخدام 2.1A→2.1B→2.1C صريحة) | market_history + أسطح |
| 6.2B-0 | `reasoning.evidence_families` | أسطح 6.1x |

**نتيجة القراءة**: `MarketObservationTimeline.seal()` يتطلب `("open","high","low","close")` منتهية، `h≥l`، و`o,c ∈ [l,h]` — **OHLC كاملة دائماً** — والـseal يحوّل الإطار الممرَّر إلى «THE authenticated market history» (payload hash). لا قناة للغموض داخل العقد. و`docs/STATUS.md` يصرّح بالفعل: Stage 4A **ترفض ACTUAL_AGGRESSOR** لأن «the CLOSED MarketObservationTimeline does not seal buy_volume/sell_volume and no authoritative external factual-availability contract exists for those inputs» — أي أن **العقد الخارجي المفقود هو بالضبط ما يصمَّم هنا**.

## 2) Dependency Matrix — كل محرّك مقابل ما يستهلكه فعلياً

| المحرّك | open | high | low | close | volume | buy/sell_vol | ملاحظة سببية |
|---|---|---|---|---|---|---|---|
| 1.1 Volatility | — | ✓ | ✓ | ✓ | — | — | TR يحتاج close السابق |
| 1.2 Session | — | — | — | — | — | — | تقويم فقط |
| 2.1A Swings | — | ✓ | ✓ | — | — | — | **pivot من high/low** |
| 2.1B Sequence | — | — | — | — | — | — | أحداث 2.1A |
| 2.1C Breaks | — | ✓ | ✓ | ✓ | — | — | close-break سببي |
| 2.2 Liquidity | — | ✓ | ✓ | ✓ | — | — | أحداث wick/close |
| 3.1 ACTUAL | — | — | — | — | reconcile | **✓** | hook جاهز |
| 3.1 PROXY | ✓ | ✓ | ✓ | ✓ | ✓ | — | location proxy |
| 3.2 ACTUAL | — | — | — | ✓ | — | — | returns من close + سطح 3.1 |
| 3.2 PROXY | ✓ | ✓ | ✓ | ✓ | ✓ | — | + سطح 3.1 PROXY |
| 4.1 OB | ✓ | ✓ | ✓ | ✓ | — | — | body geometry من open/close |
| 4.2A FVG | ✓ | ✓ | ✓ | ✓ | — | — | middle body من open/close |
| 4.2B Range | — | — | — | ✓ | — | — | + سطح 2.1x |
| 5.1 HTF | ✓ | ✓ | ✓ | ✓ | opt | — | تجميع OHLCV |
| 6.x Research/Trajectory | ✓ | ✓ | ✓ | ✓ | opt | — | **REFERENCE_MARK = completed close** |

**خلاصة سؤال close**: المرجع البحثي بأكمله (`CREATION_ROW_COMPLETED_CLOSE_RESEARCH_REFERENCE_MARK`) مربوط بإغلاق الصف المكتمل — close سببي جوهري في كل شيء تقريباً؛ open يستهلكه 4.1/4.2A/5.1/3.x-PROXY/الـseal فقط؛ swings وsession والـACTUAL لا تلمس open أصلاً.

## 3) القرار في مشكلة open/close ambiguity (وإجابات الأسئلة الإحدى عشرة)

**ج1 — مَن يحتاج open؟** 5.1 HTF، 4.2A FVG، 4.1 OB، 3.1/3.2 PROXY، و`MarketObservationTimeline.seal` نفسه.
**ج2 — high؟** 1.1، 2.1A، 2.1C، 2.2، 4.1، 4.2A، 5.1، 3.x PROXY، وexcursions في trajectory.
**ج3 — low؟** نفس high تماماً.
**ج4 — close؟** 1.1، 2.1C، 2.2، 4.2B، 3.2 (كلا الوضعين)، 4.1/4.2A (أحداث close-breach/reclaim)، 5.1، 3.1 PROXY، 0.1 audit، والمرجع البحثي للـ6.2A كاملة.
**ج5 — volume؟** 5.1 (اختياري)، الـseal (اختياري مسجَّل)، 3.1 PROXY (إلزامي)، 3.1 ACTUAL (اختياري reconcile)، 3.2 PROXY. (`buy/sell_volume` = 3.1 ACTUAL حصراً.)
**ج6 — الاعتماد السببي على close:** **جوهري وكلي** — به يُقاس كل outcome (مرجع الإنشاء = close مكتمل)، وبه تُعرَّف الاختراقات (2.1C/2.2/المناطق)، وعوائد 3.2، وTR في 1.1. لذلك غموض close الأخطر على الإطلاق (2,089 دقيقة).
**ج7 — هل يمثّل العقد الحالي field-level ambiguity؟** **لا.** `_TIMELINE_REQUIRED_COLUMNS=(open,high,low,close)` منتهية + هندسة `o,c∈[l,h]`؛ لا حقل غموض؛ والـseal يختم القيم كما هي.
**ج8 — هل يفترض market_history OHLC كاملة؟** **نعم دائماً** (تحقق هندسي إلزامي).
**ج9 — حذف الدقيقة المبهمة؟** **يصنع فجوات مدمرة**: تختفي pivots (high/low للدقيقة المحذوفة = دليل pivot مفقود)، تُفقد أحداث لمس/اختراق المستويات ومراقبة دورة حياة OB/FVG، تتسرب ثغرات إلى HTF (coverage «unknown» موثَّق في 5.1)، و**الأخطر**: نوافذ outcome المستقبلية تُقاس على high/low — حذف دقيقة قد يمحو favorable/adverse excursion فعلياً فيُصنَّف فرض غير مُشاهَد/مُناقض **زيفاً**. المقياس: 2,089–4,154 دقيقة (4.7%–9.3%) — غير مقبول كسياسة عامة.
**ج10 — open_candidates/close_candidates أو uncertainty metadata دون تعديل CLOSED؟** **نعم، خارج الإطارات**: في عقد الـAdapter/الـprovenance (جداول جانبية بمفتاح الدقيقة). **لا** كقيم داخل إطار الـseal — قيماً يجب أن تكون عددية محددة، وأعمدة metadata إضافية داخل الإطار تُطمس معنى الـseal ولا تُبرّئ القيم.
**ج11 — هل يحوّل الـdeterministic convention المرفوع للمحركات إلى factual truth؟** **نعم** — الـseal يحوّل الإطار إلى THE authenticated history وكل محرّك يعامل الأرقام كحقائق، وبلا قناة غموض تبقى القيمة المصنَّعة حقيقة. **⇒ مرفوض** كما أمرت.

### الترتيب المعتمَد (اختيار «يحفظ الحقيقة السببية ويعظّم الاستخدام القانوني» — لا الأسهل)

**القرار: D + C + B (مركّب مرتَّب) مع A حصراً كاحتياطي مقيَّد**

1. **D — المصدر الرسمي المستقل يحسم قيم open/close (أساسي)**: عقد kline 1m الرسمي (ملف مربوط بالبصمة) يُصدر قيم OHLC المنشورة؛ aggTrades يبقى مصدر executed-flow والمحاسبة؛ **cross-witness إلزامي**: high/low/base/quote/taker-buy-base يجب أن تطابق تماماً بين المصدرين، وفي الدقائق غير المبهمة open/close **يجب** أن يساويا قيمنا الدقيقة بالضبط. أي تعارض (عدا انتظار تباين open/close في دقائق الـtie) = **FAIL CLOSED — SOURCE_INCONSISTENCY**.
2. **C — عقد الـAdapter يحمل الغموض (حامل لا يخفي)**: `open_ambiguous/close_ambiguous/open_tie_distinct_prices/close_tie_distinct_prices/open_candidates/close_candidates` + `open_source/close_source` (KLINE_1M | EXACT_UNAMBIGUOUS) + counts الـtie الثلاثة (1,434,513/2,065/2,089) تبقى موثَّقة في provenance إلى الأبد. القيم المرفوعة للـseal مصدرية (mُشهَّدة)، والغموض الفيزيائي يبقى مُصرَّحاً `NOT_PROVEN`.
3. **B — أسطح منفصلة لمن لا يحتاج open/close**: سطح `BINANCE_EXECUTED_FLOW_SOURCE` (3.1/3.2 ACTUAL)، وsession على التقويم، وswings على high/low — تعمل على كل الدقائق دون مساس بغموض open/close.
4. **A — احتياطي مقيَّد فقط**: الدقائق التي تتعذر فيها شهادة kline (ملف ناقص/تعارض غير مُفسَّر) تُستثنى من الـtimeline بسجل فجوة صريح + **censoring صريح لنوافذ outcome عند الفجوات** (لا تزيف outcomes). ليست سياسة عامة.
5. **مرفوض صراحة**: convention-as-truth؛ وملء القيم بمنتصف المرشحين أو بالحدود (يُخترع سعراً لم يتداول)؛ وأي workaround يخفي الغموض.

## 4) تقييم official Binance 1m klines كمرجع OHLC مستقل

**العقد الرسمي الموثَّق** (binance-public-data README — أُعيد جلبه حرفياً): أعمدة klines = `Open time|Open|High|Low|Close|Volume|Close time|Quote asset volume|Number of trades|Taker buy base asset volume|Taker buy quote asset volume|Ignore`؛ مصدرها `/api/v3/klines`؛ تدعم `1m`؛ ملفات شهرية `BTCUSDT-1m-2026-05.zip` + `.CHECKSUM` (sha256) على data.binance.vision؛ timestamps SPOT ≥2025-01-01 **ميكروثانية** (مثال README: open_time `…000000` وclose_time = end−1µs)؛ التوافر: شهرية أول اثنين من الشهر؛ وتوثّق Updates أن الأرشيف **قد يُراجَع تاريخياً** (2022-08-08 «Fixed inconsistent data») ⇒ الـprovenance يربط **بصمة الملف عند التنزيل + تاريخ الجلب** ولا يدعي ثباتاً عبر التنزيلات.

**هل يحل الغموض قانونياً أم ينقل الافتراض؟** يحلّه **قانونياً لنوع الادعاء** ولا يثبت الفيزياء:
- ما يتحول: من «**نحن** رتّبنا الـties واخترنا قيمة» (تصنيع بلا مصدر) ← إلى «**المُصدِر** نشر هذه قيم open/close لهذه الدقيقة» (**اقتباس عقد مصدر**، قابل للتحقّق بالبصمة). هذا فرق قانوني حقيقي: citation ≠ fabrication.
- ما لا يتحول: **الترتيب الفيزيائي داخل timestamp المتساوي يبقى غير معلوم من أي مصدر عام** — يُصرَّح `TIE_ORDER_CONTRACT=NOT_PROVEN` إلى الأبد في الـprovenance.
- ما ينتقل من الثقة: ثقة في حساب Binance لـklines — **محدودة بشهادة تقاطعية** مع aggTrades (h/l/vol/quote/taker-buy مطابقة إجبارية؛ وتطابق open/close في الدقائق غير المبهمة شاهد قوي على توافق المصدرين). عندئذٍ تبقى الدرجة غير المحسومة الوحيدة = قيم open/close في دقائق الـtie تحديداً، وتُوسَم `open_source=KLINE_1M, tie_order=NOT_PROVEN`.
- التوقيت: kline 1m نهائي عند نهاية الدقيقة + تأخير نشر — بلا مشكلة في الاستخدام التاريخي (مايو 2026 منتهٍ)؛ لا ادعاء إتاحة حيّة في هذه المرحلة.

**مطابقة الدلالات**: base volume ✓ مقارن؛ quote ✓؛ high/low ✓؛ **count ✗ غير مقارن** (kline `Number of trades` = صفقات خام مقابل `agg_trade_count` = تجميعات — كما وثّق التقرير 18) — يُسجَّل كشاهد مُوسَم فقط؛ taker-buy-base ✓ يقابل `buy_initiated_base_volume`؛ المفتاح = `open_time ↔ minute_start_us` بالضبط.

## 5) تصميم executed-flow factual surface

**وحدة منفصلة: `BINANCE_EXECUTED_FLOW_SOURCE`** (سطح factual — تُغلق أولاً ثم تُستهلك بعقد رسمي):
- صفوفها مربوطة بنفس timeline (فهرس CLOSE_TIME نفسه) ومقيَّدة بسلسلة الأعمدة: `buy_volume ← buy_initiated_base_volume`، `sell_volume ← sell_initiated_base_volume` (وحدة BASE BTC مُصرَّح بها)، `volume ← base_volume` (لـ`reconcile_total_volume=True` → `classified_volume_fraction=1.0` بالتعريف — شاهد مصالحة داخلي).
- الاستهلاك: **3.1 `ACTUAL_AGGRESSOR` مباشرة عبر public API** (الخطاف موجود — يتطلب `buy_volume/sell_volume` فقط) ثم 3.2 ACTUAL (سطح 3.1 + close). **بدون أي تعديل على 3.1/3.2**.
- القيد الموثَّق: أسطح Stage 4A **ترفض ACTUAL اليوم** ( `_require_proxy_mode` يرفض `ACTUAL_AGGRESSOR` صراحة) — إذن هذا السطح يُستهلك خارج مسار Stage4A حالياً، ودمجه في الأسطح = **توسعة CLOSED مستقبلية بموافقة صريحة** (لا تُصمَّم خلسة). انظر §13.
- الاسم دلاليًا مقيَّد: executed/initiated flow فقط (نفس منعات التسمية).

## 6) حدود ACTUAL مقابل PROXY مقابل UNKNOWN (ضمن مصدر Binance)

| الصنف | ما يدخله |
|---|---|
| **ACTUAL** (بالمعنى «actual according to upstream feed semantics» كما تعرفه 3.1 نفسها) | حقائق executed/initiated flow (buy/sell initiated base+quote، deltas)؛ محاسبة الحجم/الاقتباسي الدقيقة؛ قيم h/l المنشورة؛ قيم open/close **فقط** عندما تكون source-asserted (kline) أو غير مبهمة؛ timestamps/counters الموثَّقة |
| **PROXY** | كل مخرجات `OHLCV_PROXY` الحالية (close_location_proxy/volume_pressure_proxy/…) تبقى PROXY هندسة أشرطة مكتملة — **لا تُساوَى بـACTUAL أبداً**، وأي استدلال «ضغط/امتصاص» منها يبقى PROXY |
| **UNKNOWN** | الترتيب داخل timestamp المتساوي (NOT_PROVEN)؛ حالة دفتر الأوامر/العمق/التوازن؛ نية الجانب السلبي؛ هوية المشاركين (institutional/whale)؛ عدد الصفقات الخام بلا kline `n`؛ إتاحة bar-close من المحوّل (NOT_CLAIMED — الإتاحة تُعرَّف بـmapping الـAdapter فقط)؛ أي provenance تاريخي توليدي أبعد من هوية الملف بالبصمة |

## 7) عقد الـProvenance (سلسلة شهادات ملزمة)

`BINANCE_SPOT_SOURCE_PROVENANCE_V1` — يربط (حقول إلزامية):
`source_file_sha256` (`86d4…f1c04`) · `converter_sha256` (`0048…efb5d`) · `minute_facts_csv_sha256` (`a6a0…4601f`) + sidecar-sha · `kline_file_sha256` + retrieval date (عند توافر D) · `source_schema` (`BINANCE_SPOT_PUBLIC_DATA_AGGTRADES` + klines schema) · `timestamp_semantics` (MICROSECONDS؛ membership `[start,end)`؛ **timeline index = CLOSE_TIME = minute_end**; UTC) · `symbol=BTCUSDT` · `market_type=SPOT` · `source_period` (2026-05-01T00:00:00.365107Z → 2026-05-31T23:59:59.698477Z) · `aggregation_contract` (Σprice×qty fixed-point؛ buy+sell=total) · `tie_ambiguity_counts` (1,434,513/2,065/2,089 + TIE=NOT_PROVEN + policy) · `numeric_representation` (integer fixed-point 8/8/16) · `reconciliation_witness` (الخمس exact من الـsidecar) · شهادة التقاطع kline↔aggTrades · `open_source/close_source` لكل دقيقة · و**بيان حرفي**: لا ادعاء historical generating-input provenance أكثر مما يثبته ملف Binance المعرَّف بالبصمة.

**mapping التوقيت (قرار تصميمي صريح)**: فهرس الـtimeline داخل المشروع = **لحظة إتمام الدقيقة** (`minute_start_us + 60e6`) بدلالة `CLOSE_TIME` — لأن 5.1 يقبل CLOSE_TIME حصراً `(start,end]`، وInformationPhase `COMPLETED_ROW_AVAILABLE` يتحقق عند اكتمال الصف، وsessions تُقيَّم عند لحظة الإتاحة. فهرس start-only يُزيح الزمن عن CLOSED semantics — مرفوض.

## 8) ملفات BUILD المستقبلية المقترحة (أصغر عدد — لا ملف محرّك يُمَس)

| ملف جديد | الدور |
|---|---|
| `src/trading_system/sources/__init__.py` | حزمة مصادر جديدة فقط |
| `src/trading_system/sources/binance_spot_minute_facts_source.py` | تحميل minute facts + تحقق schema الـ23 عموداً + binding البصمات + فهرسة CLOSE_TIME + استدعاء `MarketObservationTimeline.seal` |
| `src/trading_system/sources/binance_spot_kline_ohlc_source.py` | تحميل klines 1m + تسوية open/close + جدول شهادة التقاطع + سياسة SOURCE_INCONSISTENCY |
| `src/trading_system/sources/binance_executed_flow_source.py` | سطح `BINANCE_EXECUTED_FLOW_SOURCE` → إطار 3.1 ACTUAL |
| `tests/test_binance_spot_minute_facts_source.py` + `tests/test_binance_spot_kline_ohlc_source.py` + `tests/test_binance_executed_flow_source.py` | الاختبارات §9 |
| تحديث `MANIFEST.sha256` | بموجب إجراء التوسعة المعتمَد (+6/7 مداخل) — خطوة مالك |

(خيار الدمج: ملفا مصدر + ملف اختبار إذا أردت أقل عدد.) **صفر تعديل** على أي ملف CLOSED. Reality Check runner والأدوات المرئية = **مرحلة لاحقة** غير مشمولة.

## 9) الاختبارات العدائية المطلوبة في BUILD المستقبلي (مصمَّمة الآن)

1. **schema minute facts الحقيقي** (23 عموداً + sidecar؛ بأرقام المالك كـgolden counts). 2. **provenance binding** (كل حقل إلزامي + سلسلة البصمات). 3. **hashes**: source/converter/output/kline. 4. **OHLC ambiguity**: دقائق tie تُوسَم، kline يحسم، والقيم غير المبهمة تطابق حرفياً. 5. **حدود الدقيقة الدقيقة** (mapping CLOSE_TIME: `[t,t+60s)→index t+60s`). 6. **missing minute behavior** (0 متوقَّع؛ غير صفر ⇒ fail-closed). 7. **no synthetic bars** (عدم اصطناع صفوف). 8. **timezone** (UTC tz-aware؛ رفض naive). 9. **cross-timeline** (seal/verify؛ نفس المدخل ⇐ نفس timeline_hash). 10. **future truncation** (prefix history ⇐ نفس نتائج الدقائق السابقة). 11. **mutated source** (بت واحد ⇒ فشل البصمة). 12. **mismatched symbol** / 13. **mismatched market type** / 14. **mismatched converter** / 15. **mismatched source hash** (رفض صريح بكل حالة). 16. **executed flow reconciliation** (buy+sell=total؛ classified_fraction=1). 17. **no PROXY→ACTUAL impersonation** (عمود order_flow_mode يُرفض تزييفه؛ لا تسمية ACTUAL لسطح غير مصدر). 18. **same-information-batch** (deterministic_sequence؛ الـtie لا يكسر ترتيب الدفعات). 19. **no leakage into historical prefix** (as-of visibility). 20. **direct reuse of CLOSED engines** (السلسلة 2.1A→2.1B→2.1C كما في `_run_closed_structure_chain`؛ مخرجات مطابقة لاستدعاءاتها العامة). 21. **AST guard** يمنع إعادة تنفيذ أي محرك (نمط test_34 السابق).

## 10) Reality Check Integration Path (واجهة تشغيل مستقبلية — بلا إعادة كتابة)

`minute market source (post-adapter)` → **Layers 0–5** عبر `analyze()` العامة (1.1→1.2→2.1A→2.1B→2.1C→2.2→3.1 PROXY/ACTUAL→3.2→4.1/4.2A/4.2B→5.1→5.2) → **6.1A** evidence → **6.1B** narrative/hypotheses → **6.2A-0** InformationKey/visibility → **6.2A-1** outcome observer (TimelineAdapter + DecisionAnchor) → **6.2A-2/3** eligibility/dataset → **6.2B** reasoning.

تقرير المستقبل يُظهر (كلها من أعمدة CLOSED المنشورة، بلا اشتقاق جديد): عدد swings؛ تصنيف HH/HL/LH/LL؛ أحداث BOS/CHoCH؛ مستويات/أحداث liquidity؛ OB candidates؛ FVG؛ dealing ranges؛ volatility/session؛ **flow PROXY موسوم PROXY**؛ **حقائق executed-flow في عمود/سطح منفصل موسوم ACTUAL-according-to-source**؛ evidence families؛ hypotheses؛ future favorable/adverse excursions. **ممنوع**: PnL، entry/stop/target، signal، model، predictive SUPPORT قبل مراحلها (والعقد يفرض أصلاً `REFERENCE_IS_EXECUTION_PRICE=False`).

**Visual Reality Sample**: قوائم timestamps **مجمَّدة مسبقاً** (تُختار وتُختم قبل التحليل) → لكل لحظة artifact منفصل: «ماذا كان يعرف النظام هنا؟» عبر `VisibleAsOfBundle`/`AsOfVisibilityProjector` (snapshot as-of مربوط بمفتاح معلومات) — ثم **outcome film لاحقاً وبصيغة منفصلة** (مسارات الـtrajectory بعد اللحظة) — فصل صارم يمنع أي تسريب.

## 11) ما لن تثبته هذه المرحلة

لا نتائج Reality Check؛ لا جودة تنفيذ/PnL/تنبؤ؛ **لا حل فيزيائي للترتيب داخل timestamp المتساوي** (يبقى NOT_PROVEN مُصرَّحاً)؛ لا ضمانة لمنهجية توليد klines داخل Binance (شهادة تقاطعية فقط)؛ لا إتاحة حيّة؛ لا تسلسل tick؛ لا ادعاء أن executed-flow يكشف ضغطاً/مؤسسات؛ لا صلاحية أي ملف غير معرَّف بالبصمة؛ لا مساس بـCLOSED.

## 12) BUILD READY = **NO**

**NO — PENDING OWNER APPROVAL**: (أ) اعتماد القرار D+C+B وترتيبه، (ب) قبول klines 1m كعقد مصدر OHLC مستقل (مع شهادة التقاطع)، (ج) تثبيت mapping التوقيت CLOSE_TIME، (د) سياسة SOURCE_INCONSISTENCY الفاشلة-المغلقة. التصميم مكتمل ولا عائق تصميمي تحت D؛ لا يُبنى سطر واحد قبل موافقتك.

## 13) العوائق التي تتطلب تعديل CLOSED

- **تحت القرار المعتمَد (D): لا عائق** — صفر تعديل CLOSED؛ الغموض يعيش في عقد الـAdapter/الprovenance الجديد؛ القيم المرفوعة للـseal مُشهَّدة مصدرية.
- **إذا رُفض D** (أي إبقاء aggTrades وحده مصدر OHLC): **DESIGN BLOCKER — CLOSED CONTRACT EXTENSION REQUIRED** — لا يمكن تمثيل open/close مبهمة داخل `MarketObservationTimeline` (OHLC إلزامية منتهية بلا قناة غموض)، ولا داخل 4.1/4.2A/5.1/3.x-PROXY (توقيعات OHLC كاملة) — أي توسعة = تعديل عقود CLOSED بموافقة صريحة، أو التراجع إلى A المقيَّد (فجوات + censoring؛ §3-ج9).
- **دمج ACTUAL في أسطح Stage 4A** (بدل الاستهلاك المباشر لـ3.1/3.2) = توسعة CLOSED مستقبلية منفصلة — تُطلب صراحة لاحقاً ولا تُصمَّم خلسة.

---

**STOP — BINANCE SOURCE ADAPTER — CONSOLIDATED DESIGN — PENDING OWNER APPROVAL.**

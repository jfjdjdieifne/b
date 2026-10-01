# هاند أوف شامل — مشروع التداول السببي (Causal Trading Intelligence)

تاريخ: 2026-08-21
هذا الملف يشرح **كل شيء** لأي AI جديد يستلم المشروع من الصفر، بدون سياق المحادثات السابقة.

---

## 1. ما هو هذا المشروع؟ (الفلسفة قبل الكود)

مش استراتيجية تداول checkbox، ولا ICT/SMC محفوظ. هو **نظام ذكاء سببي** يبني طبقات من
الحقائق الواقعية عن السوق، بكل انضباط سببي صارم.

القاعدة العليا (الدستور):

```text
output[i] depends only on information available at or before i
```

ممنوع: `shift(-1)`، centered rolling، backfill من المستقبل، full-dataset fitted transforms داخل
live، future return/target/PnL في live evidence، اختيار best-entry أو hindsight level.

**فصل صارم بين عالمين**:
- **LIVE WORLD**: Layers 0–5 + 6.1A + 6.1B (قرار/سرد) — لا يدخل outcomes/labels.
- **RESEARCH WORLD**: 6.2A-x (رؤية as-of → outcomes → eligibility → dataset → trajectory) — هو
  المكان الوحيد المسموح فيه بالنتائج/الأكوام.

**لغة محظورة قبل وجود trade contract**: WIN/LOSS، profitable، PnL، entry/fill/stop/target.
مسموح فقط: research_reference_price، favorable/adverse excursion، CONTRADICTED، SUPERSEDED،
OBSERVED_DIRECTION_ESTABLISHED، RIGHT_CENSORED_AS_OF_BOUNDARY.

**فلسفة الـ support**: وجود OB/FVG/liquidity interaction لا يعني support؛ alignment لا يعني
profitability؛ غياب support لا يعني opposition؛ correlation لا يعني confirmations مستقلة.

---

## 2. الأدوار والدستور (Authority Order)

### ترتيب السلطة
```text
1. current working tree (الملفات الحالية)
2. MANIFEST.sha256 (بصمة الملفات المعتمدة)
3. CLOSED public contracts (الكود المغلق)
4. tests
5. docs/STATUS.md / FINAL_VALIDATION.md / releases
6. design / handoff docs
7. ملخصات المحادثات (ليست authority)
```

### الأدوار
- **Product Owner / Closure Authority (أنت)**: يحدد scope، يصرّح بالبناء، يقبل التدقيق، يعلن CLOSED.
- **Builder AI**: ينفذ scope فقط، يكتب الاختبارات العدائية، يشغّل validation، يسلّم
  `IMPLEMENTED — PENDING AUDIT`. **لا يغلق بنفسه.**
- **Independent Auditor AI**: read-only، يراجع hashes والكود الفعلي، لا يثق بتقرير الـ Builder.
  قراره: `ACCEPTED FOR CLOSURE` / `PATCH REQUIRED` / `REJECTED`.
- **Closure Agent**: بعد قبول صريح، يغيّر docs/status/manifest فقط، ويثبت أن src/tests لم تتغير.

### دورة حياة أي module
```text
NOT STARTED → DESIGN PROPOSAL → IMPLEMENTED — PENDING AUDIT → PATCHED
→ ACCEPTED FOR CLOSURE → CLOSED
```
- نجاح الاختبارات لا يعني CLOSED.
- تعديل CLOSED يحتاج PATCH ONLY مصرّح versioned.

### الدروس المتكررة عبر المشروع (يجب ألا تُنسى)
1. **درس Stage 3 provenance**: لا تخلط بين "deterministic derivation" و"historical
   generating-input provenance". الـ reconstruction hash يثبت **التكافؤ**، مش "هذا المدخل أنتج
   الـ artifact". إذا المصدر المغلق لا يختم هوية المدخلات، فالـ provenance التاريخي
   NOT CERTIFIED / UNVERIFIABLE.
2. **درس Stage 4A mutable-DataFrame**: frozen dataclass بداخله DataFrame قابل للطفرة = BLOCKER.
   لازم `verify_surface_integrity` يعيد حساب الهوية من المحتوى الحالي قبل أي استهلاك.
3. **درس Stage 4A boundary**: لازم التحقق من InformationKey كامل (phase + timestamp + timeline)
   عبر CLOSED adapter، ورفض BAR_PRE_CLOSE للحقائق المكتملة.

---

## 3. بنية النظام (Layers 0–6)

كل layer مجموعة modules مغلقة (CLOSED) ببصمة SHA-256 معتمدة وتاريخ إغلاق versioned.

| Layer | Module | Version | Status |
| --- | --- | --- | --- |
| 0 | Causal & State Audit Framework | V3.1 | CLOSED |
| 0 | Causal Percentile Tracker | V1 | CLOSED |
| 0 | Causal Adaptive Smoothing | V1.1 | CLOSED |
| 1 | Dynamic Volatility Engine | V1.1 | CLOSED |
| 1 | Session Context | V1 | CLOSED |
| 2 | Swing Detector 2.1A | V1.1 | CLOSED |
| 2 | Swing Sequence 2.1B | V1 | CLOSED |
| 2 | Structural Break 2.1C | V1.1 | CLOSED |
| 2 | Liquidity Map 2.2 | V1.1 | CLOSED |
| 3 | Volume Delta 3.1 | V1.1 | CLOSED |
| 3 | Absorption 3.2 | V1.1 | CLOSED |
| 4 | Order Blocks 4.1 | V1.1 | CLOSED |
| 4 | FVG 4.2A | V1.1 | CLOSED |
| 4 | Dealing Range 4.2B | V1.1 | CLOSED |
| 5 | HTF Aggregator 5.1 | V1.1 | CLOSED |
| 5 | Confluence Matrix 5.2 | V1.1 | CLOSED |
| 6 | Evidence Vector 6.1A | V1.3 | CLOSED |
| 6 | Narrative Engine 6.1B | V1.2 | CLOSED |
| 6/R | As-Of Firewall 6.2A-0 | V1.2 | CLOSED |
| 6/R | Outcome Observer 6.2A-1 | V1.2 | CLOSED |
| 6/R | Eligibility Gate 6.2A-2 | V1 | CLOSED |
| 6/R | Dataset Builder 6.2A-3 | V1.1 | CLOSED |
| 6/R | Trajectory Stage 1 6.2A-4 | V1 | CLOSED |
| 6/R | Trajectory Stage 2 6.2A-4 | V1 PATCHED | CLOSED |
| 6/R | Trajectory Stage 3 6.2A-4 | V1 PATCHED | CLOSED |
| 6/R | Trajectory Stage 4A 6.2A-4 | V1 PATCHED | CLOSED |
| 6/Reasoning | Evidence-Family 6.2B-0 | V1.2 | CLOSED |
| 6/Reasoning | Adaptive Confluence 6.2B-1 | V1.1 | CLOSED |

### مسار البيانات
```text
Market OHLCV
→ Layers 0–5 causal factual engines
→ 6.1A evidence vector → 6.1B narrative/hypotheses
→ Research: 6.2A-0 visibility → 6.2A-1 outcomes → 6.2A-2 eligibility
→ 6.2A-3 dataset → 6.2A-4 trajectory (Stage 1 → 2 → 3 → 4A)
```

---

## 4. ما أنجزناه في هذه الجلسة (تسلسل كامل)

### 4.1 Stage 3 (Terminal / Censor Snapshots) — انتهى بـ CLOSED
بدأنا و Stage 3 في `IMPLEMENTED — PENDING AUDIT`. السلسلة الكاملة:

1. **BUILD ONLY**: كتبت `trajectory_stage3.py` + `test_trajectory_stage3.py` (66 اختبار).
2. **Independent Audit (دوري كمدقق)**: لقيت BLOCKERين حقيقيين:
   - **BLOCKER 1 (false envelope binding)**: `_stage2_trajectory_prefix_hash` يهشّم `all_envelopes`
     بدون تحقق أنها تابعة للـ timeline/anchor/interval المتوقعين (كود ميت `stage2_interval_id` + `pass`).
   - **BLOCKER 2 (false input provenance)**: `TrajectoryStage2Result` لا يحوي provenance، وStage 3
     يربط policy/ledger الممرّرين دون إثبات أن Stage 2 بُني منهما.
3. **PATCH ONLY (BLOCKER 1+2)**: أضفت `_verify_envelopes_belong_to_context` + `_verified_stage2_prefix`
   (إعادة حساب Stage 2 من المدخلات المقيدة ومقارنة prefix hash + count + terminal).
4. **رأي تعاقدي (semantic opinion)**: كشف خلط "derivation" بـ"generating-input provenance" في ledger A/B.
5. **PATCH ONLY (semantic)**: أعدت تسمية الحقول إلى witnesses (`reconstruction_swing_policy_hash`,
   `reconstruction_ledger_seal`)، وأصل الـ origin من artifact الـ Stage 2 نفسه مش من ledger الـ caller.
6. **Read-only verification**: كشف أن الـ equivalence check ناقص (ما بيقارن lifecycle_events كاملاً).
7. **PATCH ONLY (public-result)**: أضفت `_stage2_public_result_hash` على كامل المحتوى العام
   (price_bars + structure_events + lifecycle_events + terminal + prefix) — أغلق ثغرة `trigger_relationship_id` 2 vs 999.
8. **CLOSURE**: أغلقت Stage 3 (818 passed)، milestone + seal + STATUS + FINAL_VALIDATION + MANIFEST (154→158).

### 4.2 Stage 4 (design) ثم 4A — انتهى بـ CLOSED
1. **DESIGN ONLY (Stage 4)**: فحصت كل النطاقات المرشحة، اقترحت sub-staging (4A/4B/4C).
2. **DESIGN PATCH ONLY (4A)**: صحّحت "shared per timeline" إلى "shared per exact domain-surface
   identity"، واكتشفت أن ACTUAL_AGGRESSOR خارج الـ timeline seal (لازم binding مستقل).
3. **BUILD ONLY (4A)**: كتبت `trajectory_stage4a.py` + tests (44). PROXY فقط، ACTUAL مرفوض.
4. **Independent Audit**: BLOCKER (mutable DataFrame تحت stale identity).
5. **PATCH ONLY (self-integrity)**: أضفت `verify_surface_integrity` + schema verification +
   defensive copy + config_payload (61 اختبار).
6. **Independent re-audit**: BLOCKER (boundary InformationKey — BAR_PRE_CLOSE).
7. **PATCH ONLY (boundary)**: فرض phases القانونية + `adapter.validate_key` + `adapter_kind` في الهوية (72 اختبار).
8. **CLOSURE**: أغلقت Stage 4A (890 passed)، milestone + seal + STATUS + FINAL_VALIDATION + MANIFEST (158→162).

### 4.3 Stage 4B (design) — الحالة الحالية
1. **DESIGN ONLY (4B)**: فحصت الـ 4 engines (liquidity/OB/FVG/dealing range).
2. **اكتشاف حاسم**: الـ IDs (`level_id`/`zone_id`/`fvg_id`/`range_id`) **prefix-stable** — تسلسلية
   سببية. تحقق تجريبي FVG: 24-bar prefix `[0..19]` = أول 20 من الـ 40-bar.
3. **نتيجة**: FVG = OHLC فقط (مستقل)؛ Liquidity/OB/DealingRange = تعتمد على chain الهيكل.
   اقترحت sub-staging: **4B-1 (shared structure surface)** ثم **4B-2 (FVG + 3 domains)**.
4. **الحالة**: `DESIGN PROPOSAL — NOT IMPLEMENTED`. لا BLOCKER تصميمي متبقٍ.

---

## 5. الحالة الرسمية الحالية (بصمات دقيقة)

### الحالة
```text
Stage 3  = CLOSED          (818 collected / 818 passed)
Stage 4A = CLOSED          (890 collected / 890 passed)
Stage 4B = DESIGN PROPOSAL — NOT IMPLEMENTED
Stage 4C = NOT STARTED
```

### MANIFEST
```text
MANIFEST: 162 / 162 OK
MANIFEST SHA-256: 2a527baffd6781ff07b612d11379f09fac47de5e7d7b46e1ccc565293f1c34b7
```

### البصمات المعتمدة (accepted hashes)
```text
trajectory_stage2.py   827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f
test_trajectory_stage2.py  bb5372fbad3582ce81d64b5d791b3599504b4ee12775767f77d93763f9bb1c6d

trajectory_stage3.py   e79a61cf85ce0ba5cb3dfcd3db63b8fcdbe8d53243bb28855eb0bc91dad2dc8e
test_trajectory_stage3.py  2777fd6661847226b91c1294234713e93a1e861d5f6845a164f3e89e523e8d28

trajectory_stage4a.py  19034dfff4ca4007921bdd7b3bd16c8afc5048b3601f2538d02510ba27edc26e
test_trajectory_stage4a.py  7547abfd5cf699badf2fc19b9a295b77aea8b73d0848fa5d12603655b3aa2b7f
```

### ملفات الـ trajectory (research)
```text
src/trading_system/research/trajectory/
  trajectory_contract.py    (Stage 1: MarketObservationTimeline, DecisionAnchor, TrajectoryInterval, ObservationEnvelope)
  trajectory_stage2.py      (PRICE + STRUCTURE + LIFECYCLE trajectory)
  trajectory_stage3.py      (terminal/censor snapshots + reconstruction witness + public-result equivalence)
  trajectory_stage4a.py     (shared per-bar market-state: volatility/session/order-flow-proxy/absorption-proxy)
```

### Releases موجودة في docs/releases/
```text
MILESTONE_6_2A_4_V1_STAGE1_CLOSED.md  ...  STAGE4A_CLOSED.md
MODULE_6_2A_4_V1_STAGE{1,2,3,4A}_ACCEPTED_SRC_TESTS.sha256
MILESTONE_6_2B_0_V1_2_CLOSED.md, MILESTONE_6_2B_1_V1_1_CLOSED.md (سبقوا هذه الجلسة)
```

---

## 6. اصطلاحات الإغلاق (conventions) — يجب اتباعها حرفياً

عند CLOSE MODULE (بعد ACCEPTED FOR CLOSURE)، يغيّر Closure Agent metadata فقط:
1. `docs/releases/MILESTONE_<MODULE>_CLOSED.md` (جديد) — يوثق: verdict، accepted hashes، baseline،
   ما يوثّقه الإغلاق، limitations، patch history، debts، final state.
2. `docs/releases/MODULE_<MODULE>_ACCEPTED_SRC_TESTS.sha256` (جديد) — سطرا src/test hash.
3. `docs/STATUS.md` — يحدّث جدول الحالة + قسم الإغلاق + سجل closure history.
4. `docs/FINAL_VALIDATION.md` — يحدّث الأعداد (collected/passed) + قسم حدود الإغلاق.
5. `MANIFEST.sha256` — يضيف 4 أسطر جديدة: src + test + seal + milestone (بصيغة `./docs/releases/...`
   للميلستون، بدون `./` للباقي حسب الحالة). يعيد تحديث hashes لـ STATUS وFINAL_VALIDATION المتغيّرين.

**القاعدة**: لا تحديث MANIFEST أثناء BUILD/PATCH — فقط عند الـ closure المصرّح.

**تشغيل الاختبارات** (من جذر المشروع):
```bash
PYTHONPATH=src python3 -m pytest --no-header -o addopts="" -q        # full suite
PYTHONPATH=src python3 -m pytest tests/test_trajectory_stage4a.py --no-header -o addopts="" -q
sha256sum -c MANIFEST.sha256
```

---

## 7. الديون المفتوحة (OPEN — لا تُغلق صامتاً)

```text
RESEARCH-DEBT-020  Hypothesis Lifecycle Termination Semantics (لا TTL)
RESEARCH-DEBT-021  Evidence-Bearing Calibration
RESEARCH-DEBT-022  Entity-Level Narrative Provenance
RESEARCH-DEBT-023  Censoring / Competing-Risk Estimand (Stage 3 يمثل factually فقط، لا يحدد hazard)
RESEARCH-DEBT-024  Overlapping Hypothesis Dependence / Non-IID
RESEARCH-DEBT-025  Reference-Price and Market-Time Alignment
```

### قيود مهمة (لا تُضعف)
- Stage 3: لا يوثّق الهوية التاريخية المولِّدة لـ Stage 2 artifact (derivation witness فقط).
- Stage 4A V1: لا يدعم ACTUAL_AGGRESSOR / ACTUAL absorption (الـ timeline لا تختم buy/sell_volume).
  OHLCV_PROXY ≠ ACTUAL. لا ادعاء جودة تنبؤية.

### Out of scope (لا تبدأ بدون تصريح)
Stage 4B/4C، descriptors، estimands، hazard/survival/competing-risk، model/scorer/weights/
probabilities، geometry/entry/stop/target/execution/fills، PnL/WIN/LOSS/SUCCESS، signals،
predictive edge، fixed horizons.

---

## 8. الخطوات التالية المقترحة (بانتظار تصريحك)

1. **Stage 4B** (تصميم جاهز في `DESIGN_PROPOSAL_6_2A_4_V1_STAGE4B.md`):
   - 4B-1: Shared Structure Surface (من CLOSED 2.1A→2.1B→2.1C، hypothesis-independent).
   - 4B-2: FVG + Liquidity + OB + Dealing Range entity/lifecycle surfaces.
2. **Stage 4C**: HTF/MTF (أعلى خطر سببي — bucket غير المكتمل).
3. لاحقاً (بعد تصميم مصرّح): descriptors/estimands/model — لكن هذا يفتح أبواب التفسير التنبؤي
   الممنوع حالياً.

**ملاحظة أخيرة**: المشروع كل قوته في السببية والانضباط الزمني للمعلومة والتدقيق القابل لإعادة
الإنتاج بالـ hashes. أي خطوة لاحقة يجب أن تبني فوق هذه الحدود دون اختراع edge أو استقلال أو
chronology غير مثبتة.

```text
إذا لم يكن الشيء معروفاً عند information time t، فهو لا يدخل قرار t.
إذا كان outcome من المستقبل، يبقى في research world.
إذا لم يكن العقد معرفاً، لا نخترع default.
إذا كانت الوحدة CLOSED، لا نعدلها دون versioned authorization.
إذا نجحت الاختبارات، هذا لا يعني الإغلاق.
إذا لم نستطع إثبات claim، نصرّح بالحدود أو نتوقف.
```

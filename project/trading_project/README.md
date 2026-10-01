# Trading Intelligence Project — Authoritative Causal Snapshot

هذا هو المشروع الكامل والمنظّم حتى إغلاق **Module 6.2B-1 V1.1**. الحزمة تجمع كل الكود والاختبارات والعقود والتقارير والديون البحثية المعتمدة دون حذف الوحدات السابقة.

> نقطة البدء لأي AI أو مطوّر جديد: `PROJECT_HANDOFF_MAP.md`

## الحالة الرسمية

| Layer | Module | Version | Status |
|---|---|---:|---|
| 0 | Causal & State Audit Framework | V3.1 | ✅ CLOSED |
| 0 | Causal Percentile Tracker | V1 | ✅ CLOSED |
| 0 | Causal Adaptive Smoothing / Memory Kernel | V1.1 | ✅ CLOSED |
| 1 | Dynamic Volatility Engine | V1.1 | ✅ CLOSED |
| 1 | Causal Session Context Engine | V1 | ✅ CLOSED |
| 2 | Causal Adaptive Swing Detector (2.1A) | V1.1 | ✅ CLOSED |
| 2 | Confirmed Swing Sequence Structure (2.1B) | V1 | ✅ CLOSED |
| 2 | Causal Structural Break Engine (2.1C) | V1.1 | ✅ CLOSED |
| 2 | Causal Liquidity Map / Level Lifecycle (2.2) | V1.1 | ✅ CLOSED |
| 3 | Causal Volume Delta / Order-Flow Evidence (3.1) | V1.1 | ✅ CLOSED |
| 3 | Aggression / Price-Response / Absorption Evidence (3.2) | V1.1 | ✅ CLOSED |
| 4 | Causal Order-Block Candidate & Lifecycle (4.1) | V1.1 | ✅ CLOSED |
| 4 | Causal FVG Candidate & Lifecycle (4.2A) | V1.1 | ✅ CLOSED |
| 4 | Causal Dealing Range & Premium/Discount (4.2B) | V1.1 | ✅ CLOSED |
| 5 | Causal Higher-Timeframe Aggregator (5.1) | V1.1 | ✅ CLOSED |
| 5 | Causal Multi-Scale Confluence Matrix (5.2) | V1.1 | ✅ CLOSED |
| 6 | Causal Evidence Vector / Feature Contract (6.1A) | V1.3 | ✅ CLOSED |
| 6 | Causal Market Narrative / Hypothesis Engine (6.1B) | V1.2 | ✅ CLOSED |
| 6/Research | Research Information-Time / As-Of Visibility Firewall (6.2A-0) | V1.2 | ✅ CLOSED |
| 6/Research | Factual Hypothesis Outcome Observer (6.2A-1) | V1.2 | ✅ CLOSED |
| 6/Research | Temporal Training Eligibility Gate (6.2A-2) | V1 | ✅ CLOSED |
| 6/Research | Causal Research Dataset / Walk-Forward (6.2A-3) | V1.1 | ✅ CLOSED |
| 6/Research | Causal Future Trajectory Foundation Stage 1 (6.2A-4) | V1 | ✅ CLOSED |
| 6/Reasoning | Dynamic Evidence-Family Reasoning Contract (6.2B-0) | V1.2 | ✅ CLOSED |
| 6/Reasoning | Walk-Forward Adaptive Confluence Calibration (6.2B-1) | V1.1 | ✅ CLOSED |

## الفكرة الأساسية

المشروع لا يبني checkbox strategy ولا يفترض أن OB/FVG/liquidity/alignment تعني ربحاً. النظام يفصل بين:

```text
FACTUAL / CONTEXTUAL / QUALIFYING / ALIGNED
SUPPORT / OPPOSITION / CONTRADICTION
UNKNOWN / UNAVAILABLE / NEUTRAL
ACTUAL / PROXY
storage integrity / semantic identity
provenance / deterministic derivation / statistical independence
```

Module 6.2B-0 لا ينتج score أو weights أو probability أو signal. لا يوجد current CLOSED source يتحول إلى predictive `SUPPORT`، وكل current record يبقى:

```text
included_for_independent_calibration = False
```

## الحدود غير المصدّقة

الإغلاق الحالي لا يصدّق:

- predictive edge أو profitability؛
- confluence score أو learned weights؛
- calibration أو qualification threshold؛
- model/estimator/scorer؛
- entry/stop/target أو geometry policy؛
- execution/fills/trade lifecycle؛
- PnL/WIN/LOSS/signals؛
- statistical independence بين الأدلة؛
- حل overlapping-hypothesis dependence.

`RESEARCH-DEBT-020` حتى `RESEARCH-DEBT-025` تبقى مفتوحة.

## التثبيت والتحقق

```bash
python -m pip install -e ".[dev]"
pytest --collect-only -q
pytest -q
sha256sum -c MANIFEST.sha256
```

Certified baseline:

```text
701 collected
701 passed
```

## الملفات المرجعية

```text
PROJECT_HANDOFF_MAP.md
README.md
docs/STATUS.md
docs/ARCHITECTURE.md
docs/FINAL_VALIDATION.md
docs/ENGINEERING_CONSTITUTION.md
docs/handoff/AI_COLLABORATION_CONSTITUTION_CURRENT.md
docs/module_6_2b_0_v1_audit_report.md
docs/module_6_2b_1_v1_audit_report.md
docs/module_6_2b_1_v1_1_INDEPENDENT_AUDIT.md
docs/releases/MILESTONE_6_2B_1_V1_1_CLOSED.md
MANIFEST.sha256
```

## Domain source boundary

```text
D1/D1.1: PRELIMINARY SOURCE AUDIT — ACCEPTED / APPLIED
```

`BOS_*` و`CHOCH_*` هي project operational labels وليست ادعاءً بأنها literal canonical ICT/Huddleston terminology. Source fidelity لا يثبت predictive edge.

## سلامة النسخة

`MANIFEST.sha256` يسجل كل الملفات المعتمدة داخل المشروع باستثناء manifest نفسه. لا تعدّل module مغلقاً دون versioned patch مصرح به.

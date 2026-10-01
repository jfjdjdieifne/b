# Certified Architecture Snapshot

```text
Layer 0
  Module 0.1 — Causal & State Audit Framework V3.1
  Module 0.2 — Causal Percentile Tracker V1
  Module 0.3 — Causal Adaptive Smoothing Kernel V1.1

Layer 1
  Module 1.1 — Dynamic Volatility V1.1
  Module 1.2 — Causal Session Context V1

Layer 2
  Module 2.1A — Causal Adaptive Swing Detector V1.1
  Module 2.1B — Confirmed Swing Sequence Structure V1
  Module 2.1C — Causal Structural Break Engine V1.1
  Module 2.2 — Causal Liquidity Map / Level Lifecycle Engine V1.1

Layer 3
  Module 3.1 — Causal Volume Delta / Order-Flow Evidence Engine V1.1
  Module 3.2 — Causal Aggression / Price-Response / Absorption Evidence V1.1

Layer 4
  Module 4.1 — Causal Order-Block Candidate & Lifecycle Engine V1.1
  Module 4.2A — Causal FVG Candidate & Lifecycle Engine V1.1
  Module 4.2B — Causal Dealing Range & Premium/Discount Context V1.1

Layer 5
  Module 5.1 — Causal Higher-Timeframe Aggregator V1.1
  Module 5.2 — Causal Multi-Scale Confluence Matrix V1.1

Layer 6
  Module 6.1A — Causal Evidence Vector / Feature Contract V1.3 — CLOSED
  Module 6.1B — Causal Market Narrative / Hypothesis Engine V1.2 — CLOSED

Layer 6 / Research boundary
  Module 6.2A-0 — Research Information-Time / As-Of Visibility Firewall V1.2 — CLOSED
  Module 6.2A-1 — Factual Hypothesis Outcome Observer V1.2 — CLOSED
  Module 6.2A-2 — Temporal Training Eligibility / Research Dataset Gate V1 — CLOSED
  Module 6.2A-3 — Causal Research Dataset Builder & Walk-Forward Splitter V1.1 — CLOSED

Layer 6 / Reasoning boundary
  Module 6.2B-0 — Dynamic Evidence-Family Reasoning Contract V1.2 — CLOSED
```

## Dependency direction

```text
0.1  audit authority (tests/self-verification)
0.2  empirical causal rank primitive
0.3  external-period causal smoothing primitive

1.1 ──uses──> 0.2
1.2           timestamp/config only
2.1A ─uses──> 0.2
2.1B ─consumes──> 2.1A confirmed-event DataFrame surface
2.1C ─consumes──> 2.1A + 2.1B confirmed structural-event surfaces
2.1C ─uses──────> 0.2 for first-break empirical evidence
2.2  ─consumes──> 2.1A + 2.1B confirmed event surfaces
2.2  ─uses──────> 0.2 for nearest-level distance context
3.1  ─uses──────> 0.2 for signed/magnitude order-flow context
3.2  ─consumes──> explicit 3.1 mode surface and uses 0.2 for response context
4.1  ─consumes──> confirmed swings + 2.1C directional structural events; uses 0.2 for displacement context
6.1B ─consumes──> certified 6.1A V1.3 evidence surface and manifest
6.2A-0 ─projects──> frozen 6.1A/6.1B records through an explicit InformationKey
6.2A-1 ─consumes──> CLOSED 6.2A-0 VisibleAsOfBundle only
6.2A-1 ─observes──> factual terminal/censor/reference/path records without trade interpretation
6.2A-2 ─audits──> temporal legality of CLOSED 6.2A-1 factual outcomes at explicit cutoff T
6.2A-2 ─selects──> one outcome-neutral mature identity per deduplicated factual group
6.2A-3 ─joins──> attested frozen ev__/nar__ creation features with factual outcomes
6.2A-3 ─splits──> causal TRAIN <= T_train and TEST in (T_train, T_test]
6.2A-3 ─preserves──> immature TEST rows with missing factual targets
6.2B-0 ─consumes──> exact attested 6.1A/6.1B hypothesis-creation snapshot
6.2B-0 ─normalizes──> evidence families, orthogonal semantics, provenance, formula lineage, and semantic hashes
6.2B-0 ─does not produce──> support upgrade, score, calibration, model, geometry, execution, or signal
research ─may import──> immutable/public decision contracts
decision and Layers 0–5 ─must not import──> trading_system.research

0.1 audits primary DataFrame outputs. Modules 2.2 and 4.1 additionally have dedicated exact normalized event-table truncation/state audits. Module 6.1B additionally has dedicated exact causal audits for all normalized secondary ledgers and relationship-source provenance.

## Domain terminology boundary

Module 2.1C `BOS_UP/BOS_DOWN` are project **continuation-direction structural break** labels. `CHOCH_UP/CHOCH_DOWN` are project **opposite-direction structural shift candidate** labels. These are not asserted as literal canonical ICT terminology. Preliminary source research found stronger primary support for the term MSS than for CHoCH attribution.
```

Module 1.1 intentionally does not force Module 0.3 without a justified causal memory source. Module 1.2 does not depend on market features. Module 2.1A does not interpret structure beyond candidate/reversal evidence and optional explicit confirmation.

Module 6.1B V1.2 closure history is `V1 -> V1.1 -> V1.2 -> CLOSED`. Closure certifies causal descriptive narrative behavior, deterministic hypothesis lifecycle, exact provenance, and zero-lookahead replay within tested scope. It does not certify predictive edge, profitability, ICT canonical fidelity beyond D1/D1.1, scorer quality, weights, probabilities, entries, exits, or entity-level liquidity/zone narratives. `RESEARCH-DEBT-020`, `RESEARCH-DEBT-021`, and `RESEARCH-DEBT-022` remain open.

Module 6.2A-0 V1.2 closure history is `V1 -> V1.1 -> V1.2 -> CLOSED`. It certifies explicit immutable InformationKey ordering, fail-closed as-of projection, future-payload exclusion, exact truncation/mutation/append invariance, atomic same-row analytical visibility, parent-child source projection, certified 6.1A/6.1B static manifest identity, explicit positional/time adapters, timezone/DST/irregular handling, the live-to-research import firewall, deterministic stateless projection, and exclusion of final `active_hypotheses` from historical projection within tested scope.

This closure does not certify outcomes, maturity, censoring, `final_outcome_known_at`, reference-price outcome measurement, excursions, labels, training eligibility, models, predictive edge, profitability, scorer, weights, or signals. `COMPLETED_ROW_AVAILABLE` sequencing is logical dependency serialization only; it is not a measured micro-latency claim, and 6.1B `serialization_order` remains bookkeeping rather than intrabar order.

Module 6.2A-1 V1.2 closure history is `V1 -> V1.1 -> V1.2 -> CLOSED`. It certifies factual post-hypothesis outcome observation, as-of censoring facts, non-executable reference-mark timing, post-creation path segmentation, exact mature outcome identity, future/as-of isolation, and no trade interpretation within tested scope. It does not certify estimator selection, models, predictive edge, profitability, scorer, weights, or signals.

Module 6.2A-2 V1 is CLOSED. It certifies InformationKey-based temporal eligibility, mature-only legality, censored/immature audit preservation, outcome-neutral earliest-as-of deduplication, factual duplicate consistency, reason precedence within the validated row contract, zero feature/model leakage, exact label-information intervals, and real 6.2A-0/6.2A-1 integration within tested scope. It does not construct X/y matrices, transform features, resolve overlapping-sample dependence, train models, or produce scorer/weights/probabilities/signals.

Module 6.2A-3 V1.1 closure history is `V1 -> V1.1 -> CLOSED`. It certifies exact attested frozen feature/outcome joins, strict raw feature isolation, causal walk-forward boundaries, defensive purge enforcement, safe immature TEST targets, eligibility reseal, deterministic fold identities, and full pipeline integration within tested scope. It does not certify preprocessing, scaling, imputation, feature selection, model/estimator quality, scorer, weights, probabilities, signals, or dependence correction.

Module 6.2B-0 V1.2 closure history is `V1 -> V1.1 -> V1.2 -> CLOSED`. It certifies exact creation-row InformationKey boundaries, future-payload rejection within the representable parent envelope, factual/non-predictive evidence families, explicit orthogonal semantic flags, certified MTF conflict preservation, open-world three-state provenance, deterministic derivation separated from co-derivation, exact 6.1A availability and CLOSED 5.2 formula lineage, final-record hashes, and canonical semantic reasoning identity within tested scope.

6.2B-0 treats dependency clusters as conservative bookkeeping, not proof of shared provenance or statistical independence. Current records are not independently calibratable. It does not certify predictive support, score, weights, calibration, model/scorer, probability, geometry, execution, or signals.

`RESEARCH-DEBT-020`, `021`, `022`, `023`, `024`, and `025` remain open. Temporal legality, raw fold construction, and provenance normalization do not imply selected samples or evidence are IID.

## Excluded as non-final

This snapshot intentionally excludes all old/unapproved drafts and references for:

- old `causal_kernels.py`
- Liquidity Map
- Volume Delta / Absorption
- Order Blocks
- FVG
- old integration pipeline
- original mixed source bundle

Their omission is deliberate: they are not part of the certified project state represented by this archive.

# Current Authoritative Validation — Through Module 6.2A-4 V1 Stage 3 Closure

## Collected tests

```text
tests/test_absorption.py: 18
tests/test_adaptive_confluence_calibration.py: 27
tests/test_adaptive_confluence_calibration_integration.py: 2
tests/test_binance_executed_flow_source.py: 6
tests/test_binance_spot_kline_ohlc_source.py: 20
tests/test_binance_spot_minute_facts_source.py: 19
tests/test_causal_adaptive_smoothing.py: 37
tests/test_causal_htf.py: 10
tests/test_causal_percentile.py: 24
tests/test_confluence_matrix.py: 9
tests/test_dealing_range.py: 11
tests/test_dynamic_volatility.py: 20
tests/test_evidence_family_reasoning.py: 34
tests/test_evidence_family_reasoning_integration.py: 1
tests/test_evidence_family_reasoning_v1_1.py: 30
tests/test_evidence_vector.py: 54
tests/test_fvg.py: 16
tests/test_liquidity_map.py: 20
tests/test_narrative.py: 53
tests/test_order_blocks.py: 12
tests/test_research_dataset_builder.py: 22
tests/test_research_dataset_integration.py: 1
tests/test_research_eligibility.py: 25
tests/test_research_eligibility_integration.py: 1
tests/test_research_hashing.py: 18
tests/test_research_information_time.py: 16
tests/test_research_manifest_identity.py: 19
tests/test_research_outcome_integration.py: 2
tests/test_research_outcome_observer.py: 55
tests/test_research_visibility.py: 44
tests/test_session_context.py: 26
tests/test_structural_breaks.py: 25
tests/test_swing_detector.py: 28
tests/test_swing_sequence.py: 31
tests/test_trajectory_contract.py: 18
tests/test_trajectory_stage2.py: 36
tests/test_trajectory_stage3.py: 81
tests/test_trajectory_stage4a.py: 72
tests/test_trajectory_stage4b1.py: 37
tests/test_trajectory_stage4b2.py: 37
tests/test_trajectory_stage4c.py: 36
tests/test_volume_delta.py: 19
TOTAL: 1072
```

## Exact pytest result

```text
........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
........................................................................ [ 26%]
........................................................................ [ 33%]
........................................................................ [ 40%]
........................................................................ [ 47%]
........................................................................ [ 53%]
........................................................................ [ 60%]
........................................................................ [ 67%]
........................................................................ [ 73%]
........................................................................ [ 80%]
........................................................................ [ 87%]
........................................................................ [ 94%]
................................................................         [100%]
```

```text
1072 collected
1072 passed
exit code 0
```

## Status

```text
Layers 0–5: CLOSED
D1/D1.1: PRELIMINARY SOURCE AUDIT — ACCEPTED / APPLIED
Module 6.1A V1.3: CLOSED
Module 6.1B V1.2: CLOSED
Module 6.2A-0 V1.2: CLOSED
Module 6.2A-1 V1.2: CLOSED
Module 6.2A-2 V1: CLOSED
Module 6.2A-3 V1.1: CLOSED
Module 6.2A-4 V1 Stage 1: CLOSED
Module 6.2A-4 V1 Stage 2: CLOSED
Module 6.2A-4 V1 Stage 3: CLOSED
Module 6.2A-4 V1 Stage 4A: CLOSED
Module 6.2A-4 V1 Stage 4B-1: CLOSED
Module 6.2A-4 V1 Stage 4B-2: CLOSED
Module 6.2A-4 V1 Stage 4C-1: CLOSED
Module 6.2B-0 V1.2: CLOSED
Module 6.2B-1 V1.1: CLOSED
Binance Source Adapter V1: CLOSED
EXACT PERFORMANCE V2 + TEST-SUITE ACCELERATION (unified): CLOSED
6.2A-4 Stage 4C-2 HTF structure / MTF confluence: NOT STARTED
6.2C geometry / 6.2D execution / model / scorer / signals: NOT STARTED
QualificationObjective: NOT DEFINED
```

## Module 6.2B-0 closure boundary

Closure certifies within tested scope:

1. exact hypothesis-creation same-row `InformationKey` boundary;
2. rejection of prior/future rows and future semantic payload before use within the representable parent envelope;
3. exact revalidation of the CLOSED creation snapshot integrity hashes;
4. no current source upgraded to predictive `SUPPORT`;
5. explicit orthogonal semantic states and MTF directional-conflict preservation;
6. separate ACTUAL and PROXY epistemic classes;
7. three-state open-world provenance: certified shared, certified distinct, or not certified;
8. deterministic derivation kept orthogonal to provenance and co-derivation;
9. formula-faithful 6.1A availability lineage with COUNT_SUPPORT excluded from value parents;
10. formula-faithful CLOSED 5.2 MTF DAG without manifest-order inference;
11. no false statistical-independence admission (`included_for_independent_calibration=False` for all current records);
12. final record hash, family semantic hash, global semantic reasoning hash, and exact upstream storage hash separation;
13. canonical source-order-insensitive semantic identity;
14. stateless A→A, A→B→A, fresh-instance, prefix/future-history invariance, and full caller-input immutability;
15. reasoning firewall: no outcomes, model, scorer, geometry, or execution dependencies.

Closure does not certify:

- predictive support or edge;
- statistical independence or incremental predictive information;
- confluence strength or score;
- learned weights or calibration;
- qualification threshold or probability;
- preprocessing, model, estimator, classifier, or scorer;
- entity-level geometry adapter;
- entry, stop, target, fill, execution, or trade lifecycle;
- BUY/SELL signals or PnL/WIN/LOSS;
- overlapping-hypothesis dependence resolution.

## Module 6.2B-1 closure boundary

Closure certifies within tested scope:

1. TRAIN-only descriptive calibration/reference foundation;
2. authoritative CLOSED 6.2A-3 source-fold verification (full fold seal) before any TRAIN projection;
3. canonical TRAIN sample binding through CLOSED `_sample_id`;
4. authoritative B-0 reasoning re-analysis/membership for every admitted sample;
5. exact TRAIN raw feature row binding;
6. TEST/OOS descriptive-content firewall: TEST cannot alter TRAIN calibration content;
7. descriptive empirical CDFs labelled `TRAIN_EMPIRICAL_CDF_NOT_PROBABILITY`;
8. descriptive observation coverage labelled not semantic or predictive SUPPORT;
9. explicit NULL / SIMPLE / FULL baseline and FAMILY_ABLATION admission contracts;
10. chained experiment accounting with an external trusted-head boundary;
11. caller-reported OOS-access accounting explicitly NOT access-control proof;
12. separated source-fold provenance, TRAIN content identity, and final artifact identity;
13. public artifact verification recomputing all component/content/artifact hashes without TEST payload access;
14. ACTUAL/PROXY separation and UNKNOWN/UNAVAILABLE separation with no zero-fill or renormalization;
15. `DEPENDENCE_NOT_RESOLVED` for unresolved overlap/non-IID semantics;
16. no target-conditioned fitting while the objective is undefined.

Closure does not certify:

- predictive edge or predictive SUPPORT;
- feature importance or learned confluence weights;
- a qualification objective or threshold;
- probability or profitability;
- statistical independence or effective independent sample size;
- untouched OOS merely from caller-reported access count;
- geometry, entry/stop/target, execution/fills, signals, or PnL/WIN/LOSS;
- future live performance.

## Module 6.2A-4 Stage 1 closure boundary

Closure certifies within tested scope:

1. shared authenticated `MarketObservationTimeline` foundation with no per-hypothesis market duplication;
2. decision/outcome two-clock semantics: `observation_information_key` may precede `factual_available_at_information_key`, and visibility uses the available-at key;
3. decision anchor contains no future information and no future feature preselection;
4. creation bar excluded from the post-hypothesis path `(decision_batch, end_inclusive]`;
5. FACTUAL_EVENT vs STATE_OBSERVATION distinction, hash-bound;
6. deterministic as-of projection;
7. immutable prior as-of snapshots (later facts create new identities, never rewrite earlier ones);
8. shared timeline storage rather than per-hypothesis market copies;
9. OHLC source-resolution limitations (no intrabar chronology, no tick/L2 claims);
10. integrity sealing explicitly not integrity binding (not issuer authentication);
11. literal terminal lifecycle semantics with no success/profit interpretation;
12. canonical identities/hashing via the project serializer;
13. research/live firewall (no live module imports the trajectory package).

Closure does not certify:

- actual domain trajectory observations (liquidity / OB / FVG / flow / MTF ingestion);
- path descriptors;
- learning estimands;
- predictive edge, probabilities, or any model/scorer;
- geometry, entry/stop/target, execution, or profitability.

## Module 6.2A-4 Stage 2 closure boundary

Closure certifies within tested scope:

1. per-bar favorable/adverse excursion formulas per CLOSED 6.2A-1 orientation;
2. running maximum favorable/adverse with strict-greater tie preservation (first occurrence);
3. SAME_INFORMATION_BATCH_ORDER_UNKNOWN when both extremes in same OHLC bar;
4. close displacement = (close - ref) / ref, bar offset = bar_position - decision_bar_position;
5. new-running-extreme flags, extreme price/position/InformationKey capture;
6. shared timeline architecture preserved (no per-hypothesis market copy);
7. consumed CLOSED 2.1A→2.1B→2.1C structure chain with prefix causality (market_history truncated to interval end);
8. swing origin < confirmation enforced, confirmation is factual-available-at;
9. full taxonomy from CLOSED contracts: SWING, SEQUENCE, BREACH, BREAK, STATE transition;
10. consumed CLOSED 6.1B lifecycle ledger with literal terminal states only: CONTRADICTED, SUPERSEDED, OBSERVED_DIRECTION_ESTABLISHED;
11. no second state machine, no price-inferred terminal;
12. mature interval boundary at terminal factual-availability, unresolved as-of returns empty;
13. SUCCESS/WIN/LOSS/PROFIT rejected as terminal states;
14. two-clock semantics, creation bar exclusion, input immutability, determinism, firewall preserved.

Closure does NOT certify:

- true_range / normalized true range / volatility trajectory;
- liquidity / OB / FVG / dealing range / volume delta / absorption trajectory;
- session / HTF / MTF trajectory;
- censor-series implementation (Stage 3);
- path descriptors, quality, efficiency;
- learning estimands;
- predictive model, scorer, weights, probabilities;
- geometry, entry/stop/target, execution, PnL;
- WIN/LOSS/SUCCESS interpretation.

## Module 6.2A-4 Stage 3 closure boundary

Closure certifies within tested scope:

1. immutable mature terminal snapshot and immutable right-censored-as-of snapshot;
2. append-only as-of snapshot series (strictly increasing research-as-of, prior snapshots unchanged);
3. CLOSED 6.2A-1 as authoritative for mature-vs-censored classification, `factual_outcome_id`,
   `research_snapshot_id`, terminal state, and terminal position;
4. CLOSED Stage 2 as authoritative for the PRICE / STRUCTURE / LIFECYCLE trajectory prefix;
5. complete Stage 2 public-result deterministic-equivalence verification
   (`STAGE2_PUBLIC_RESULT_EQUIVALENCE_V1`) over `price.price_bars` + price final scalars +
   `structure.structure_events` + `lifecycle.lifecycle_events` + lifecycle terminal fields +
   envelope count + envelope prefix hash;
6. envelope-context verification: every supplied and reconstructed envelope proven to belong to
   the expected timeline / timeline_hash / anchor / interval (with CLOSED `envelope.verify()`);
7. separation of terminal factual availability from research as-of (two distinct InformationKeys);
8. compact snapshot identity (hashes/counts only; no raw market, no full envelope tuple, no
   duplicated running payloads);
9. reconstruction / derivation-witness semantics;
10. origin preserved exactly from the supplied Stage 2 artifact's own embedded lifecycle rows
    (Int64 position, not a manufactured InformationKey);
11. literal terminal states only (CONTRADICTED, SUPERSEDED, OBSERVED_DIRECTION_ESTABLISHED);
12. right-censor semantics `RIGHT_CENSORED_AS_OF_BOUNDARY` only, matching CLOSED 6.2A-1;
13. positional and time-indexed timelines (timezone-aware, DST/irregular UTC), cross-timeline
    rejection, same-information-batch determinism;
14. determinism (A→A, A→B→A, fresh-instance), caller-input immutability, frozen snapshots;
15. research/live firewall (no live module imports Stage 3).

Closure does NOT certify:

- the historical generating-input identity of a supplied Stage 2 artifact
  (`reconstruction_swing_policy_hash`, `reconstruction_ledger_seal`,
  `stage2_reconstruction_binding_hash` are derivation witnesses only; generating-input
  provenance remains NOT CERTIFIED / UNVERIFIABLE);
- Stage 4 trajectory domains (volatility / liquidity / OB / FVG / dealing range / orderflow /
  session / HTF / MTF trajectory);
- path descriptors;
- learning estimands;
- hazard / survival model, competing-risk probabilities, or any censor estimand;
- predictive model, scorer, weights, probabilities, confluence scores;
- geometry, entry/stop/target, execution, fills, trade lifecycle;
- PnL, WIN/LOSS/SUCCESS semantics, signals;
- fixed horizons;
- statistical independence or overlapping-hypothesis dependence resolution.

## Module 6.2A-4 Stage 4A closure boundary

Closure certifies within tested scope:

1. factual shared per-bar market-state trajectory for Dynamic Volatility, Session Context,
   Volume Delta / Order Flow in OHLCV_PROXY mode, and Absorption / Response in OHLCV_PROXY mode;
2. shared domain surfaces computed once per exact domain-surface identity, independent of
   hypothesis identity (not merely per timeline);
3. compact hypothesis prefix binding with no per-hypothesis row duplication;
4. complete public-result hashing over the full CLOSED factual output per domain;
5. surface self-integrity verification: recomputes public-result hash and surface identity from
   current content; rejects stale-identity / mutable-DataFrame tampering;
6. exact output-schema verification from the CLOSED contract + frozen config payload;
7. reconstruction / derivation witness semantics (NOT historical generating-input provenance);
8. legal InformationKey boundary validation (positional and time-indexed); BAR_PRE_CLOSE rejected
   for completed-bar facts; timestamp consistency enforced for time-indexed boundaries;
9. no post-boundary projected facts; future-prefix invariance under legally rebuilt future surfaces.

Closure does NOT certify:

- ACTUAL_AGGRESSOR order flow or ACTUAL absorption (the CLOSED MarketObservationTimeline does not
  seal buy_volume/sell_volume and no authoritative external factual-availability contract exists;
  ACTUAL is rejected with no fallback);
- OHLCV_PROXY == ACTUAL (PROXY is completed-bar OHLCV geometry only);
- predictive quality for PROXY or ACTUAL;
- historical generating-input provenance;
- Stage 4B (liquidity / OB / FVG / dealing range) or Stage 4C (HTF / MTF);
- descriptors, estimands, hazard/survival/competing-risk models;
- predictive model, scorer, weights, probabilities, confluence scores;
- geometry, entry/stop/target, execution, fills, trade lifecycle;
- PnL, WIN/LOSS/SUCCESS semantics, signals, predictive edge, fixed horizons;
- statistical independence or overlapping-hypothesis dependence resolution.

## Module 6.2A-4 Stage 4B-1 closure boundary

Closure certifies within tested scope (the shared causal structure surface contract only):

1. one shared, hypothesis-independent structure surface from the CLOSED public chain
   2.1A → 2.1B → 2.1C;
2. complete public factual result of 2.1A + 2.1B + 2.1C bound by canonical component hashes and a
   composed public-result hash;
3. shared storage (one surface per surface identity) + compact hypothesis prefix binding;
4. factual availability governed by confirmation/event row, never origin; origin preserved as
   positional Int64, never a manufactured InformationKey;
5. compact prefix identity through a legal boundary T (full-surface identity changes on append,
   prefix identity preserved — verified on the real CLOSED chain);
6. boundary legality mirroring CLOSED Stage 1/Stage 4A;
7. self-integrity verification + supplied-vs-authoritative reconstruction comparison;
8. deterministic reconstruction witness semantics only.

Accepted limitations (NON-BLOCKING): (1) `verify_surface_integrity` provides internal
self-consistency for stored witness metadata; coherent witness-token forgery is not independently
disproven by self-integrity alone. (2) `verify_surface_matches_reconstruction` compares against a
supplied authoritative surface; it does not itself independently reconstruct the CLOSED chain.
(3) Passthrough market fields are reconstruction inputs bound through the CLOSED timeline seal; the
public-result hash covers the complete derived structure result. (4) `prefix_hash` is factual content
identity; complete binding carries surface/timeline/boundary identity.

Closure does NOT certify: historical generating-input provenance (NOT_CERTIFIED / UNVERIFIABLE);
Liquidity / OB / FVG / Dealing Range trajectory surfaces (Stage 4B-2); Stage 4C (HTF/MTF);
predictive usefulness, trading edge, profitability, or statistical independence; descriptors,
estimands, hazard/survival/competing-risk; model/scorer/weights; geometry/execution; PnL,
WIN/LOSS/SUCCESS.

## Module 6.2A-4 Stage 4B-2 closure boundary

Closure certifies within tested scope the four shared, hypothesis-independent factual
entity/lifecycle trajectory surfaces only:

1. Liquidity surface (CLOSED 2.2 consumed over Stage 4B-1): 23 derived bar columns + 16 event
   columns, 15 entities on the deterministic fixture;
2. Order-Block surface (CLOSED 4.1 over Stage 4B-1): 26 + 20, 14-column entity table, 7 entities;
3. FVG surface (CLOSED 4.2A, structurally independent — OHLC only, sealed market directly,
   `structure_surface_id=None` mandatory): 27 + 21 source event columns, 15-column entity table,
   50 entities; normalized event frame is 21 + same-information-batch ambiguity flag = 22;
4. Dealing-Range surface (CLOSED 4.2B over Stage 4B-1, original CLOSED 17-column range table):
   30 derived bar columns, 14 ranges;
5. schema authority from the concrete surface class plus local Final frozen CLOSED-output mirrors,
   with independent dynamic verification that builds the real CLOSED engines and rejects any
   added/dropped/reordered public column — a coherently recomputed hash cannot bypass it;
6. four-component factual prefix binding through T (derived bars + events <= T + entities at
   factual availability position + normalized events) with canonical reset_index treatment;
   prefix changes under pre-T fact mutation/removal and is invariant under legal post-T extension;
7. distinct immutable per-domain class identity (coherent cross-domain / cross-table / cross-class
   switching rejected); same-information-batch flags equal to literal duplicated(event_position);
   normalized entities traceable 1:1 to creation events (or the original range table for DR);
8. self-integrity verification, boundary legality mirroring CLOSED Stage 1/4A/4B-1
   (BAR_PRE_CLOSE rejected, cross-timeline rejected, positional/time-indexed correctness),
   intact research/live firewall, reconstruction/derivation-witness semantics only.

Consumed market passthrough verified as high/low/close (liquidity), OHLC (order block, FVG),
close (dealing range); none of the four engines consumes volume.

Accepted limitations (NON-BLOCKING): (1) a foreign column injected between the passthrough block
and the derived tail is accepted while tail append is rejected; hashing binds the derived tail and
exact event/entity/range tables, so no derived fact is forgeable through this channel; future
hardening may enforce exact whole-frame column equality. (2) Passthrough cells are bound through
the CLOSED timeline seal rather than re-hashed, as in Stage 4A/4B-1. (3) Reconstruction/mirror
equivalence is a derivation witness; historical generating-input provenance remains
NOT_CERTIFIED / UNVERIFIABLE. (4) Series.equals does not distinguish +0.0/-0.0 while content
hashing does; the deterministic fixture does not exercise signed zero. (5) The fixture generates
neither a DR rejection nor a far OB-retrieval restoration; those CLOSED paths are consumed but not
fixture-exercised.

Closure does NOT certify: Stage 4C (HTF/MTF future surfaces; NOT_IMPLEMENTED / NOT STARTED);
descriptors; estimands; hazard/survival/competing-risk; model/scorer/weights/probabilities;
QualificationObjective; predictive SUPPORT, statistical independence, incremental information,
predictive usefulness, trading edge, or profitability; geometry/entry/stop/target/execution/fills;
PnL, WIN/LOSS/SUCCESS, signals, fixed horizons. RESEARCH-DEBT-020..025 remain open.

## Module 6.2A-4 Stage 4C-1 closure boundary

Closure certifies within tested scope (the shared causal raw HTF observation surface, optional
declared-grid coverage metadata, and causal as-of projection only):

1. raw HTF observed OHLC surfaces: completed HTF bucket observations (time, open, high, low,
   close) consumed solely from the CLOSED public 5.1 aggregator as sealed observation truth;
   bucket truth accepted only under `COMPLETED_ROW_AVAILABLE`; `BAR_PRE_CLOSE` rejected; the LTF
   close and the HTF close are one information batch with `close_batch_order_unknown` set at
   exact-boundary visibility rows and no intra-batch chronology claim;
2. optional cadence-grid coverage metadata: completeness decided by timestamp-SET comparison
   against the declared grid (never counts alone) with `GRID_OBSERVATIONS_COMPLETE` /
   `GRID_OBSERVATIONS_MISSING` / `OFF_GRID_OBSERVATIONS_PRESENT` / `GRID_OBSERVATIONS_DEFECT_BOTH`
   / `GRID_COMPLETENESS_UNKNOWN`; without a declared grid coverage is
   `GRID_COMPLETENESS_UNKNOWN`; as-of rows carry `COVERAGE_UNAVAILABLE` (`UNAVAILABLE`) when no
   projectable grid status exists;
3. causal as-of projection through a legal boundary T inside the sealed timeline
   (`project_htf_scale_prefix`), TIME_INDEXED only (`POSITIONAL` is a contract error);
   exact-boundary visibility only at an observed LTF row whose timestamp equals the bucket close
   (interval `(start, end]`) on the SAME timeline and only in phase `COMPLETED_ROW_AVAILABLE`;
   cross-timeline and `BAR_PRE_CLOSE` boundaries rejected;
4. in-progress / not-yet-observed buckets and their high/low/close (including extreme spikes) are
   invisible until the close is observed; a feed gap delays projectability to the first observed
   as-of position at/after the close (a theoretically elapsed bucket is not visible before its
   first observed as-of row) — verified against real CLOSED 5.1 outputs;
5. `first_observed_asof_*` semantics = sealed-timeline projectability ONLY, with an explicit
   semantic-inflation guard
   (`SEALED_TIMELINE_PROJECTION_NOT_FEED_ARRIVAL_PROVENANCE_NOT_MARKET_AVAILABILITY`,
   `PROJECTABLE_AT_CLOSE_ONLY_IN_COMPLETED_ROW_AVAILABLE_SAME_TIMELINE`);
6. grid coverage claims completeness only of sealed observations versus the DECLARED grid — never
   feed completeness, never market completeness; a partial bucket remains honest observation
   truth with its observed rows and incompleteness metadata (no fill, no drop, no interpolation);
   no HTF volume and no HTF entities are consumed or produced;
7. derived-only frames with exact whole-frame schema equality to the declared derived schema (no
   market passthrough injection surface); sealed-timeline optional `volume` presence/absence
   never enters Stage 4C-1 derived content;
8. deterministic identity/hashing and live surface self-integrity verification (whole-frame schema
   equality + projection recomputation); deterministic reconstruction / derivation-witness
   semantics only.

Accepted limitations (NON-BLOCKING — recorded as constraints/debts; not fixed during closure):
(1) no `mirror_verification_hash` field exists (owner correction: a verification pass/fail is not
a hashable witness); (2) the observed-asof walk-back visibility gate is semantically redundant
over genuine CLOSED 5.1 outputs (external deletion probe) and is retained as defense-in-depth;
(3) sealed-timeline optional `volume` presence legitimately changes timeline identity but never
enters derived content; (4) coherent witness-token forgery remains outside self-integrity scope
(the accepted 4A/4B-1/4B-2 convention); (5) the first warm-up bucket is honestly declared
`GRID_OBSERVATIONS_MISSING` when incomplete under a declared grid; (6) `POSITIONAL` rejection is
by design (TIME_INDEXED only); (7) partial buckets are displayed with their observed rows plus
incompleteness metadata by design.

Closure does NOT certify: feed-arrival provenance (`projectable_asof` is sealed-timeline
projectability only) or historical market availability; feed completeness or market completeness;
historical generating-input provenance (NOT_CERTIFIED / UNVERIFIABLE); HTF structure; HTF
transitions; MTF confluence surfaces (Stage 4C-2; NOT STARTED); HTF volume or HTF entities;
predictive SUPPORT, statistical independence, incremental information; probability, weights,
QualificationObjective; model, scorer, calibration, geometry, entry/stop/target, execution, fills,
signals; PnL, WIN/LOSS/SUCCESS, fixed horizons; predictive usefulness, trading edge, or
profitability. RESEARCH-DEBT-020..025 remain open.

## Binance Source Adapter V1 closure boundary

Closure certifies within tested scope:

1. Binance published Kline OHLC source contract — the 12-column Binance kline artifact schema
   (Spot >= 2025-01-01 microsecond timestamp unit; `close_time = open_time + interval - 1us`;
   canonical minute mapping at `CLOSE_TIME`); Kline is a Binance-published bar fact;
2. Binance executed/initiated-flow source contract — `buy_volume` / `sell_volume` / `volume` from
   `buy_initiated_base_volume` / `sell_initiated_base_volume` / `base_volume` with
   `buy + sell == volume` exactness and single declared base-unit semantics
   (`EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT`);
3. exact cross-witness (Decimal exactness, no tolerance — minute key, high, low, base volume,
   quote volume, taker-buy base, and taker-buy quote under literal-precision compatibility;
   `number_of_trades` / `agg_trade_count` declared `NON_COMPARABLE_PAIRS` and never compared;
   unambiguous O/C = EXPECTED_MATCH; ambiguous O/C never demanded equal);
4. `SOURCE_INCONSISTENCY` fail-closed (no skip, no silent repair, no coercion);
5. `CLOSE_TIME` semantics (canonical mapping at kline `CLOSE_TIME` only; build-list coverage maps
   half-open `[start, end)` from minute starts, never from closes);
6. generic source adapters (symbol/period/market-type generic; no instance hard-coding in
   production);
7. public reuse boundary for CLOSED 3.1/3.2 (consumed via public API only; 3.1/3.2 not modified);
8. `TIE_ORDER_CONTRACT = NOT_PROVEN` always; ambiguous open/close stays ambiguous
   (`open_ambiguous`/`close_ambiguous`); reconstructed open/close are deterministic convention
   witnesses only and never canonical OHLC; canonical O/C from the kline source exclusively.

Closure semantics: `ACTUAL` here means only `EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT` per source
semantics. `ACTUAL` does NOT mean order-book truth, buying pressure, institutional activity, whale
activity, or market-wide flow. Historical generating provenance: NOT_CERTIFIED beyond the bound
source artifacts.

Closure does NOT certify:

- predictive edge;
- profitability;
- strategy;
- model;
- PnL;
- live availability.

RESEARCH-DEBT-020..025 remain open.

## EXACT PERFORMANCE V2 + TEST-SUITE ACCELERATION unified closure boundary

Closure certifies within tested scope (unified work unit: EXACT PERFORMANCE V2 +
TEST-SUITE ACCELERATION):

1. EXACT PERFORMANCE V2 — exact performance semantics preserved with zero semantic change
   (bitwise/behavioral equivalence within the accepted regression batteries); any output
   difference without a contract basis was a DO-NOT-SHIP stop condition;
2. TEST-SUITE ACCELERATION — test-suite runtime acceleration with identical test semantics
   (no test-logic change); the certified suite stands at 1072 collected / 1072 passed
   (up from the 1045 baseline; +27 tests inside the 5 accepted test files);
3. certified baseline: 1072 collected / 1072 passed / exit code 0;
4. external tool suite (field_runner `runner_tests`; outside this repository): 36 passed —
   context for the unified acceptance only, not part of this repository's test suite;
5. manifest pre-closure identity: 183 lines,
   sha256 `7796a73fc30fc311902d7ba8e033eb1699a73c5db10e824d02653fbdd1681587`,
   173 OK / 10 accepted stale / 0 missing; the 10 accepted stale entries were replaced in
   place with the accepted fingerprints (entry replacement, not deletion);
6. performance/equivalence gates: accepted equivalence/regression batteries pass; no
   semantic/causal/contract change;
7. accepted fingerprints (10 files: 5 source + 5 tests) sealed in
   `docs/releases/MODULE_EXACT_PERF_V2_TESTSUITE_ACCEL_UNIFIED_ACCEPTED_SRC_TESTS.sha256`;
   unified independent re-audit accepted both work units.

Closure does NOT certify: predictive support; edge; profitability; MUF correctness; Model;
Strategy; Signal; PnL. RESEARCH-DEBT-020..025 remain open.

## Important identity boundary

Module 6.2A-3 remains:

```text
module release: V1.1
dataset contract string: CAUSAL_RESEARCH_DATASET_V1
```

This naming mismatch is preserved as an explicit known boundary; it was not silently patched.

## Open research debts

```text
RESEARCH-DEBT-020 — Hypothesis Lifecycle Termination Semantics
RESEARCH-DEBT-021 — Evidence-Bearing Calibration
RESEARCH-DEBT-022 — Entity-Level Narrative Provenance Contract
RESEARCH-DEBT-023 — Outcome Censoring and Competing-Risk Estimand
RESEARCH-DEBT-024 — Overlapping Hypothesis Dependence / Non-IID Samples
RESEARCH-DEBT-025 — Reference-Price and Market-Time Alignment
```

No debt above is claimed solved by closure.

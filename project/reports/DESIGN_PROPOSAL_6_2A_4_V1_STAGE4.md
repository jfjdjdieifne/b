# DESIGN PROPOSAL — Module 6.2A-4 V1 Stage 4
## Rich Market-Domain Future Trajectory

Status: **DESIGN PROPOSAL — NOT IMPLEMENTED**
Date: 2026-08-20
Task Type: DESIGN ONLY (no code, no tests, no file modification, no MANIFEST change)

Authoritative baseline inspected:
- Module 6.2A-4 V1 Stage 3 = CLOSED
- 818 collected / 818 passed
- MANIFEST 158 / 158 OK, SHA-256 `309f2d13523880e94859efaaad3765d7a3b6c23791b4635b7956b8b590092dbb`
- Stage 3 CLOSED source `e79a61cf85ce0ba5cb3dfcd3db63b8fcdbe8d53243bb28855eb0bc91dad2dc8e`
- Stage 3 CLOSED test `2777fd6661847226b91c1294234713e93a1e861d5f6845a164f3e89e523e8d28`

---

## 0. Core rule

**Maximum factual information, minimum unjustified interpretation.**

Stage 4 records factual future market-domain evolution according to CLOSED contracts only. It must
not introduce SUPPORT, OPPOSITION, good/bad, quality, cleanliness, rocket, efficiency, score,
probability, edge, or WIN/LOSS. Those belong elsewhere or may never be justified.

---

## 1. CLOSED contracts inspected (actual source read, not summaries)

| Domain | Module | File | Public engine | Output shape |
| --- | --- | --- | --- | --- |
| Liquidity | 2.2 | `liquidity/liquidity_map.py` | `CausalLiquidityMapEngine` | `(bar_surface, normalized_events)` |
| Order Block | 4.1 | `zones/order_blocks.py` | `CausalOrderBlockEngine` | `(bar_surface, normalized_events)` |
| FVG | 4.2A | `zones/fvg.py` | `CausalFVGEngine` | `(bar_surface, normalized_events)` |
| Dealing Range | 4.2B | `zones/dealing_range.py` | `CausalDealingRangeEngine` | bar surface + range table |
| Volume Delta | 3.1 | `orderflow/volume_delta.py` | `CausalVolumeDeltaEngine` | bar surface (mode: ACTUAL/PROXY) |
| Absorption | 3.2 | `orderflow/absorption.py` | `CausalAbsorptionEvidenceEngine` | bar surface (mode: ACTUAL/PROXY) |
| Volatility | 1.1 | `environment/dynamic_volatility.py` | `DynamicVolatilityEngine` | bar surface |
| Session | 1.2 | `environment/session_context.py` | `CausalSessionContextEngine` | bar surface |
| HTF | 5.1 | `multitimeframe/causal_htf.py` | `CausalHTFAggregator` | `(bar_surface, bucket_table)` |
| Confluence | 5.2 | `multitimeframe/confluence_matrix.py` | `CausalConfluenceMatrixEngine` | bar surface |

Foundation contracts re-read: `trajectory_contract.py` (MarketObservationTimeline, DecisionAnchor,
TrajectoryInterval, ObservationEnvelope, FACTUAL_EVENT vs STATE_OBSERVATION), `trajectory_stage2.py`
(PRICE/STRUCTURE/LIFECYCLE trajectory), `trajectory_stage3.py` (terminal/censor + reconstruction
witness + public-result equivalence), `outcome_observer.py` (6.2A-1), `narrative.py` (6.1B ledger),
`information_time.py` (InformationKey, adapters).

---

## 2. Domain-by-domain factual taxonomy

Each domain's public facts are classified by factual kind. All positions are **Int64 bar positions**
unless the CLOSED contract exposes an InformationKey (none of these domains do — they all operate on
positional or timezone-aware DatetimeIndex frames and emit positions/timestamps, not InformationKeys).

### 2.1 Liquidity (2.2)

**Entity**: liquidity level. Identity: `level_id` (int), `side` (high/low), immutable
`level_price`. Origin `source_origin_position` (swing origin), availability `source_confirmation_position`.

- ENTITY_CREATION: `LEVEL_CREATED` at `source_confirmation_position`; origin may precede.
- ENTITY_STATE_CHANGE / LIFECYCLE (fixed order): `FIRST_TOUCH`, `FIRST_WICK_BREACH`,
  `FIRST_WICK_ONLY_EXCURSION`, `FIRST_CLOSE_BREACH`, `FIRST_RECLAIM_AFTER_CLOSE_BREACH`.
- STATE_OBSERVATION (bar aggregate): per-side first-event counts, `known_*_level_count`,
  `nearest_prior_same_side_level_id`, `nearest_same_side_distance_fraction`,
  `nearest_distance_percentile` (causal percentile).
- Source identity: `source_class` (swing sequence class); `source_origin_position` /
  `source_confirmation_position`.
- Same-row ordering: event table "serialized mechanically by event_position, level_id, then fixed
  event-type order and does not imply intrabar sequence" → SAME_INFORMATION_BATCH_ORDER_UNKNOWN.
- ACTUAL only (no proxy). Shared market truth.

### 2.2 Order Blocks (4.1)

**Entity**: OB candidate zone. Identity `zone_id`, `direction` (BULLISH/BEARISH OB CANDIDATE),
`origin_position`, `creation_position`, `search_boundary_position`, `source_break_event`
(BOS/CHOCH). Geometry: `full_zone_low/high`, `body_low/high`, `displacement_fraction`,
`displacement_percentile` (causal percentile), `origin_prior_use_count`.

- ENTITY_CREATION: `ZONE_CREATED`.
- ENTITY_STATE_CHANGE: `FIRST_TOUCH`, `FIRST_FAR_SIDE_WICK_BREACH`, `FIRST_FAR_SIDE_CLOSE_BREACH`,
  `FIRST_CLOSE_RECLAIM_OF_FAR_SIDE`.
- STATE_OBSERVATION: per-side first-event counts, `known_*_ob_candidate_count`.
- Terminology: **candidate** — explicitly NOT institutional orders. No manipulation/stop-hunt/smart-money.
- Source: CLOSED 2.1A swing + 2.1C structural break event + `structure_state_before`.

### 2.3 FVG (4.2A)

**Entity**: FVG candidate. Identity `fvg_id`, `direction`, `origin_position`, `middle_position`,
`creation_position`. Geometry: `zone_low/high`, `midpoint`, `gap_width`,
`gap_width_fraction`, `gap_width_percentile` (causal), `middle_body_fraction`,
`middle_signed_body_fraction`.

- ENTITY_CREATION: `FVG_CREATED`.
- ENTITY_STATE_CHANGE: `FIRST_TOUCH`, `FIRST_FULL_RANGE_COVERAGE`, `FIRST_FAR_SIDE_WICK_BREACH`,
  `FIRST_FAR_SIDE_CLOSE_BREACH`, `FIRST_CLOSE_RECLAIM_OF_FAR_SIDE`.
- Source: pure OHLC 3-bar gap geometry (no swing dependency). No future-return/fill assumption.

### 2.4 Dealing Range (4.2B)

**Entity**: range. Identity `range_id`, `direction`, `creation_position`, two endpoints
(side/origin/confirmation/price/class), `range_low/high/width/midpoint`. A range can be invalidated
(`rejected_range_geometry`).

- ENTITY_CREATION + persistent CONTEXT: `current_range_*` per-bar state (current range identity and
  geometry as-of each bar).
- STATE_OBSERVATION: `current_range_position_raw`, `current_midpoint_displacement`,
  `current_discount_depth`, `current_premium_depth`.
- Premium/discount = factual project geometry, NOT a trade filter.
- Hybrid: persistent entity + per-bar state projection. `rejected_range_geometry` is an
  ENTITY_STATE_CHANGE / invalidation marker.

### 2.5 Volume Delta (3.1)

**Per-bar STATE_OBSERVATION** (no entity). Mode enum `ACTUAL_AGGRESSOR` vs `OHLCV_PROXY`.

- ACTUAL: `total_classified_volume`, `raw_delta`, `delta_ratio`(+percentile/history),
  `delta_magnitude`(+percentile/history).
- PROXY: `close_location_proxy`, `volume_pressure_proxy`, `signed_volume_pressure_raw`,
  `pressure_proxy_percentile`(+history), `pressure_magnitude`(+percentile/history).
- PROXY must remain PROXY. ACTUAL means actual only under the source contract. No exchange-wide /
  global-crypto order-flow claim.
- Causal percentile trackers, per-bar. No future fitting/normalization.

### 2.6 Absorption / Response (3.2)

**Per-bar STATE_OBSERVATION** (no entity). Mode ACTUAL/PROXY.

- Common: `signed_return`, `absolute_return`, `return_magnitude_percentile`(+history).
- ACTUAL: `aggression_response_alignment`, `aligned/opposed_response_magnitude`(+percentile/history),
  `aggression_extremeness`, `response_weakness`, `actual_absorption_evidence`,
  `absorbed_aggression_side`.
- PROXY: `pressure_response_alignment`, `pressure_aligned/opposed_response_*`,
  `proxy_pressure_extremeness`, `proxy_response_weakness`, `proxy_absorption_evidence`,
  `pressure_side`.
- **Causality verified in source**: `signed_return[i] = log(close[i]) - log(close[i-1])` (backward
  only); `_response_context` pairs `flow[i]` (same bar) × `signed_return[i]` (same bar). No
  lookahead. Same-bar response. No institutional-absorption claim unless CLOSED source proves it.
- Depends on Module 3.1 surface (aggression/pressure) — a within-Stage-4 dependency.

### 2.7 Volatility (1.1)

**Per-bar STATE_OBSERVATION**: `true_range`, `normalized_true_range`, `true_range_percentile`
(+history), `normalized_tr_change`, `expansion_percentile`(+history). Causal percentile trackers,
fresh per call. No new ATR thresholds, no regime cutoffs, no descriptors. TRAIN-independent causal
state only.

### 2.8 Session (1.2)

**Per-bar STATE_OBSERVATION**: `hour_utc_sin/cos`, `weekday_sin/cos`, `active_session_count`, plus
per-session active flags. Wall-clock only. Timezone contract + DST semantics from immutable
`SessionDefinition`. No predictive claim. No invented session boundaries.

### 2.9 HTF (5.1)

**As-of STATE_OBSERVATION + bucket table.** `TimeAggregationSpec` (duration, CLOSE_TIME semantics
only in V1). Per-LTF-bar: `last_completed_htf_end_utc`, `last_completed_htf_open/high/low/close`,
`last_completed_htf_source_bar_count` (+volume). Bucket table: `bucket_start_utc`, `bucket_end_utc`,
`theoretical_available_at`, `first_observed_asof_position/time`, `first/last_source_timestamp`,
`source_bar_count`, OHLC(+volume).

- **Critical causal fact**: a bucket is visible only when a source bar with timestamp ≥ bucket_end
  exists; the aggregator uses `searchsorted(completed_ends, t, side="right") - 1`, so an LTF bar at
  time t never sees an unfinished HTF bucket.
- Timezone-aware DatetimeIndex required.

### 2.10 Confluence (5.2)

**As-of STATE_OBSERVATION** over `ScaleFrame`s. Per-bar: available/unavailable/up/down/mixed/undefined
counts, `directional_scale_count`, `availability_fraction`, `directional_fraction`,
`directional_balance`, `directional_consensus`, `directional_conflict`, plus per-scale
`__available`, `__source_available_at`, `__structure_state`, `__structure_direction_code`,
`__information_age_seconds`. Rejects future availability, backward provenance, repainted state.
ALIGNED ≠ SUPPORT; CONFLICT ≠ predictive opposition. No score.

---

## 3. Origin vs availability semantics (two clocks)

Every domain fact carries two coordinates:
- **origin / event representation** = the CLOSED source's Int64 bar position (e.g.
  `swing_origin_position`, `origin_position`, `middle_position`, `event_position`).
- **factual available-at** = an InformationKey at which the fact is first legally visible.

Rules (identical to Stage 1/2/3 discipline):

1. An entity is invisible before its creation/confirmation position.
2. A lifecycle event is invisible before its `event_position`.
3. When the CLOSED source exposes only a positional origin, Stage 4 MUST NOT manufacture an origin
   InformationKey. Origin stays Int64; availability is the InformationKey clock.
4. Example: OB origin at T5 (BOS origin), created at T8 → invisible at as-of T6, visible at as-of T8
   retaining origin T5.

For the four per-bar domains (2.5–2.8), origin == availability == the bar itself (single clock,
same-bar state). For the entity domains (2.1–2.4), origin < availability in general (two clock).

---

## 4. Entity / state / event model

| Kind | Definition | Domains |
| --- | --- | --- |
| FACTUAL_EVENT | something happened at a key | lifecycle transitions (FIRST_TOUCH, BREACH, RECLAIM, ZONE_CREATED, LEVEL_CREATED, FVG_CREATED, range invalidation) |
| STATE_OBSERVATION | factual value/state available as-of a key | per-bar volatility/session/flow/absorption/range-depth/HTF-as-of/confluence counts |
| ENTITY_CREATION | a persistent entity enters existence | LEVEL_CREATED, ZONE_CREATED, FVG_CREATED, range creation |
| ENTITY_STATE_CHANGE / LIFECYCLE | an existing entity changes lifecycle state | FIRST_* transitions, `rejected_range_geometry` |
| CONTEXT SNAPSHOT | as-of projection of a persistent entity's current state | `current_range_*`, `last_completed_htf_*`, confluence aggregates |

Entity identity: reuse the CLOSED stable IDs (`level_id`, `zone_id`, `fvg_id`, `range_id`). These are
**deterministic derivation identity** (a function of the market history), NOT historical provenance
claims, and NOT statistical-independence claims. Stage 4 must keep these three concepts distinct
(mandate §12, Stage 3 lesson).

---

## 5. Shared vs hypothesis-relative

**All Stage 4 domains are SHARED MARKET TRUTH.** Liquidity levels, OB/FVG zones, dealing range,
volume delta, absorption, volatility, session, HTF, and MTF state are properties of the market
timeline, not of any single hypothesis. They MUST NOT be recomputed once per hypothesis.

Only the following remain hypothesis-relative (already handled by Stage 1/2): `DecisionAnchor`
(hypothesis_id, decision position, reference price, direction) and `TrajectoryInterval`.

Consequently Stage 4 facts are computed **once per (timeline, market-history prefix)** and referenced
by all hypotheses via their interval. This is the single most important storage decision and is
mandated by §11/§16 (no per-hypothesis market duplication).

---

## 6. Provenance / identity model

Four distinct notions (do NOT conflate — the Stage 3 provenance lesson):

1. **Historical source provenance** — "which input actually generated this?" — NOT certifiable here
   (same limitation as Stage 3); CLOSED engines do not seal input identity.
2. **Deterministic derivation** — "this fact is reproducible from the market history under CLOSED
   contract X." This is what Stage 4 binding proves (mirror Stage 3's reconstruction-equivalence
   approach).
3. **Entity identity** — the CLOSED stable IDs (`level_id` etc.), reused verbatim.
4. **Reconstruction witness** — hash of the consumed inputs that reproduce the fact; a witness, not
   a generating-input claim.

Stage 4 introduces Stage-4-local binding identities (canonical SHA-256 over the consumed CLOSED
surface + interval prefix) only as derivation witnesses, following the Stage 3 convention
(`STAGE4_*_RECONSTRUCTION_BINDING_V1` style), never as generating-input provenance.

---

## 7. Stage 3 boundary integration

- For a mature hypothesis: no Stage 4 fact beyond the legal terminal factual-availability boundary.
- For a right-censored-as-of hypothesis: no Stage 4 fact beyond the requested legal as-of boundary.
- Historical Stage 3 snapshots remain immutable when future Stage 4 facts appear (append-only).
- Stage 4 MUST NOT redefine terminal/censor semantics; it consumes Stage 3's boundary as a cutoff.
- The Stage 3 `stage2_public_result_hash` analog: Stage 4 must also provide a complete public-result
  deterministic-equivalence verification, so its facts integrate with the reconstruction-witness
  discipline rather than introduce a weaker provenance layer.

---

## 8. Storage model

- Preserve the shared `MarketObservationTimeline` (Stage 1). One timeline, one seal.
- **Shared market-domain tables** (per timeline, computed once):
  - Entity tables: `liquidity_levels`, `ob_zones`, `fvg_zones`, `dealing_ranges` (stable rows, one
    per entity).
  - Event tables: `liquidity_events`, `ob_events`, `fvg_events` (one row per lifecycle event).
  - Per-bar state tables (or wide columns on a shared state frame): volatility, session, volume
    delta, absorption, HTF as-of, confluence — indexed by bar position / timestamp.
- **Hypothesis-relative trajectory** (per hypothesis): only envelope references + compact bindings
  into the shared tables, bounded by the interval. No per-hypothesis copy of entity/event/state
  history.
- No full growing prefix inside any censor snapshot; snapshots store compact prefix/boundary hashes
  + counts (mirror Stage 3's compact binding).
- Do NOT invent prefix-stable IDs unless CLOSED contracts prove them. The CLOSED `level_id/zone_id/
  fvg_id/range_id` are stable within a market-history prefix; their stability across different
  prefixes is NOT claimed (same caution as Stage 3 envelope IDs).

Storage complexity (conservative): entity tables are O(#entities); event tables are O(#events);
per-bar state is O(#bars) columns; the naive entity-lifecycle scan is O(N·L) (documented by the
liquidity engine itself). Stage 4 does not hide this cost.

---

## 9. Proposed sub-staging

Chosen from actual CLOSED dependency / causal-character boundaries (not by name):

### Stage 4A — Shared Per-Bar State / Snapshot Domains (L1 + L3)
Scope: volatility (1.1), session (1.2), volume delta (3.1), absorption (3.2).
Dependencies: OHLCV + CLOSED causal percentile trackers (Layer 0) + volume-delta surface for
absorption (within-stage).
Causal character: per-bar STATE_OBSERVATION, single-clock, no entity lifecycle, no two-clock origin.
Establishes: the shared per-bar state storage + envelope pattern, and the "market-domain fact is
shared, computed once" convention.
Excluded: entity domains, dealing range, HTF/MTF.

### Stage 4B — Entity Lifecycle Domains (L2 + L4)
Scope: liquidity (2.2), order blocks (4.1), FVG (4.2A), dealing range (4.2B).
Dependencies: CLOSED 2.1A/B/C structure chain (liquidity/OB/dealing range), OHLC (FVG).
Causal character: ENTITY_CREATION + lifecycle events + persistent entity + per-bar state projection
(dealing range), two-clock origin<availability.
Establishes: entity identity, lifecycle event model, origin-vs-availability discipline, normalized
entity/event tables, same-row ambiguity (SAME_INFORMATION_BATCH_ORDER_UNKNOWN).
Excluded: HTF/MTF, descriptors/estimands/model.

### Stage 4C — Multi-Timeframe Domains (L5)
Scope: HTF (5.1), confluence (5.2).
Dependencies: timezone-aware timeline; per-scale completed structure-state frames (CLOSED 2.1C
output re-aggregated at scale — NOT a Stage 4 invention).
Causal character: time aggregation + cross-timeframe as-of availability + alignment/conflict factual
state; the HTF incomplete-bar invisibility guarantee is the highest-risk invariant.
Excluded: everything downstream of MTF.

Each sub-stage has its own closure boundary, its own milestone/seal, and its own independent audit.
Stage 4A must not block on 4B/4C; 4B does not depend on 4A; 4C is independent of 4A/4B.

Dependency graph:

```
CLOSED Layer 0 (causal percentile/smoothing)
  ├─> 4A: 1.1 volatility, 1.2 session, 3.1 volume delta ──> 3.2 absorption
CLOSED 2.1A/B/C structure chain
  ├─> 4B: 2.2 liquidity, 4.1 OB, 4.2B dealing range
  └─> 4C: (per-scale re-aggregation) ──> 5.2 confluence (with 5.1 HTF buckets)
CLOSED OHLC
  └─> 4B: 4.2A FVG
```

---

## 10. Future adversarial test matrix (per domain, non-exhaustive but representative)

Common to all domains: future append invariance, future mutation outside prior as-of, A→A, A→B→A,
fresh-instance equivalence, no hidden cache, caller-input immutability, cross-timeline rejection,
duplicate-column rejection, NaN/Inf rejection, nullable Int64, >2^53 integers where applicable,
timezone/DST where applicable, firewall (LIVE modules do not import Stage 4 research), no
descriptors/estimands/model/geometry/execution, no post-terminal facts, no post-censor-as-of facts.

Entity domains (liquidity/OB/FVG/dealing range) additionally:
- entity identity stability across a fixed market prefix;
- lifecycle transition correctness (each FIRST_* fires once, in CLOSED order);
- origin before availability: entity invisible at as-of < creation, visible at as-of ≥ creation
  retaining origin;
- event invisible before `event_position`;
- source forgery rejection (an event whose source_origin/confirmation don't match the CLOSED
  structure chain);
- same-row ambiguity: multiple events at one bar preserved as SAME_INFORMATION_BATCH_ORDER_UNKNOWN,
  never reordered into intrabar chronology (deterministic_sequence ≠ market chronology);
- shared storage across overlapping hypotheses (one entity table, not N copies);
- dealing range invalidation (`rejected_range_geometry`) correctness and non-rewrite of prior state.

Per-bar domains (volatility/session/volume delta/absorption) additionally:
- percentile/smoothing state is TRAIN-independent and causal (no future observation in percentile);
- proxy vs actual mode isolation (PROXY never relabeled ACTUAL);
- absorption response same-bar causality (verified: log-return backward-only);
- session timezone/DST correctness and no invented boundaries.

HTF/MTF additionally:
- HTF incomplete-bar invisibility: at LTF bar t, only buckets with end ≤ t are visible;
- HTF closed-bar visibility: bucket visible exactly when first source bar ≥ bucket_end exists;
- aggregation identity (bucket_start/end, theoretical_available_at) deterministic;
- confluence: future-availability rejection, backward-provenance rejection, repainted-state
  rejection, ALIGNED/CONFLICT are factual counts (never score/support).

---

## 11. BLOCKERS (design-level, must be resolved before BUILD)

1. **Shared-storage architecture** — Stage 4 facts are shared market truth; if any implementation
   recomputes them per hypothesis, it reintroduces the per-hypothesis market duplication that Stage 1
   explicitly forbids. This is a hard design constraint, not an optimization.
2. **HTF incomplete-bar visibility** — exposing an HTF bar/state before its bucket is legally closed
   is a look-ahead violation (Stage 4C). Must reuse the CLOSED `searchsorted` as-of semantics
   exactly; no approximation.
3. **Origin-vs-availability two-clock** — any entity fact that drops the origin-before-confirmation
   distinction (e.g. recording only confirmation) loses causal information mandated by the CLOSED
   contracts. Must preserve origin as Int64 and availability as InformationKey.
4. **Provenance conflation** — recording a Stage-4-local binding as generating-input provenance
   (instead of derivation witness) repeats the Stage 3 BLOCKER. Forbidden.

## 12. NON-BLOCKING DESIGN DEBT

- Entity-lifecycle scan cost O(N·L) (documented by CLOSED engines); accepted for correctness, no
  hidden pruning.
- Per-bar state produces wide frames; column-name collisions must be rejected exactly as CLOSED
  engines do.
- Confluence `information_age_seconds` depends on wall-clock monotonicity; fine for factual age,
  must not become a feature in any downstream predictive claim.

## 13. RESEARCH QUESTIONS (empirical/statistical unknowns only — NOT causality/binding)

- Whether any Stage 4 factual state co-varies with terminal outcomes (belongs to a future research
  estimand, NOT to Stage 4; RESEARCH-DEBT-020/021/023/024/025 remain OPEN).
- Whether entity lifecycle transition timing is informative under a competing-risk estimand
  (RESEARCH-DEBT-023 — NOT closed by Stage 4).
- Any NEW unresolved issue discovered during Stage 4 would be proposed as a NEW debt identifier but
  NOT created/closed without authorization.

## 14. Explicit out-of-scope list

- SUPPORT / OPPOSITION / good-bad / quality / cleanliness / rocket / efficiency / score / probability / edge.
- WIN/LOSS/SUCCESS/PROFIT/PnL, entry/stop/target, geometry/execution/fills, trade lifecycle, signals.
- Descriptors, learning estimands, hazard/survival model, competing-risk probabilities.
- Predictive model, scorer, weights, feature selection.
- Statistical independence or overlapping-hypothesis dependence resolution.
- Fixed horizons.
- Any reinterpretation of CLOSED entity/lifecycle semantics (no "institutional" relabeling of
  absorption/OB, no "stop hunt"/"manipulation", no predictive FVG fill assumption).
- New CLOSED modules or MANIFEST changes during DESIGN.

---

## 15. Deliverable status

```
DESIGN PROPOSAL — NOT IMPLEMENTED
```

No code, tests, or files were written to the authoritative project tree. No MANIFEST change. No
CLOSED module modified. No Stage 4 build authorized.

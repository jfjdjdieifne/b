# Causal Future-State Observation, Path-Trajectory & Learning-Objective Architecture

```text
Status:   DESIGN PROPOSAL — NOT IMPLEMENTED
Scope:    Maximum-fidelity causal future-observation + multi-surface research objective
Module:   Proposed 6.2A-4 — Causal Future Trajectory / Outcome Contract
Rule:     DESIGN ONLY. No code. No tests. No CLOSED modifications.
Philosophy: MAXIMUM FACTUAL INFORMATION / MINIMUM UNJUSTIFIED INTERPRETATION
```

This is the implementation-ready design for how research observes what happens
**after** a frozen hypothesis, without a magic horizon, a trade label, or
look-ahead. It is grounded in an exact field-by-field inventory of the CLOSED
public contracts. Every proposed fact is classified as:

```text
CLOSED FACT          already emitted by a CLOSED public module
EXACT DERIVATION     deterministically recomputable from CLOSED facts, no loss
LOSSY DERIVATION     derivable but with documented information loss
NEW DOWNSTREAM FACT  requires a new adapter on CLOSED outputs (no CLOSED patch)
NOT CURRENTLY AVAILABLE  genuinely absent from current data/contracts
```

---

## A. Exact CLOSED field inventory available for future observation

These are the public outputs the new observer may consume. No private internals.

### A.1 Price / bar path (L0 + dataset input)

| Fact | Source | Class |
|---|---|---|
| `open, high, low, close` per bar | dataset input frame | CLOSED FACT |
| `volume` per bar (when feed has it) | dataset input frame | CLOSED FACT |
| `bar_position` (positional) / event time (time-indexed) | `InformationKey` + timeline adapter | CLOSED FACT |
| `true_range`, `normalized_true_range`, `true_range_percentile(+history_count)`, `normalized_tr_change`, `expansion_percentile(+history_count)` | 1.1 `DynamicVolatilityEngine.OUTPUT_COLUMNS` | CLOSED FACT |
| session active columns / time context | 1.2 `CausalSessionContextEngine` | CLOSED FACT |

`reference_price = CREATION_ROW_COMPLETED_CLOSE`, `reference_is_execution_price=False`
(6.2A-1). Favorable/adverse are signed by the hypothesis direction.

### A.2 Structural evolution (Layer 2)

| Fact | Source | Class |
|---|---|---|
| confirmed swing highs/lows, origin/confirmation positions & prices, reversal fractions/evidence, history percentiles | 2.1A `_OUTPUT_COLUMNS` (`swing_high_confirmed`, `swing_origin_position`, `swing_price`, `swing_confirmation_position`, `swing_reversal_fraction`, `swing_confirmed_history_percentile`, …) | CLOSED FACT |
| `structure_event_type`, `swing_sequence_class` (HH/HL/LH/LL family), `comparison_available`, `same_type_log_price_change` | 2.1B `_OUTPUT_COLUMNS` | CLOSED FACT |
| monitored high/low prices+positions, first wick/close breach positions+events, overshoot fractions, break evidence, wick/close history counts, `structure_state_before/after`, `structural_break_event` | 2.1C `_OUTPUT_COLUMNS` | CLOSED FACT |

BOS/CHOCH labels remain project operational labels, not canonical-ICT claims.

### A.3 Liquidity evolution (2.2)

Bar surface `_BAR_OUTPUT_COLUMNS` + event stream `_EVENT_COLUMNS`:

```text
liquidity_level_created, created_level_id, created_level_side, created_level_price,
created_level_origin_position, created_level_confirmation_position, created_level_source_class,
nearest_prior_same_side_level_id, nearest_same_side_distance_fraction,
nearest_distance_percentile(+history_count),
high/low_side first-touch / first-wick-breach / first-wick-only / first-close-breach / first-reclaim counts,
known_high/low_side_level_count
events: event_position, level_id, side, event_type, source_origin/confirmation_position,
source_class, immutable_level_price, event_price, event_close, overshoot_fraction,
nearest_* distances, level_age_bars
```

All CLOSED FACT. The observer does **not** reinterpret these as stop hunts.

### A.4 OB / FVG / range evolution (Layer 4)

| Surface | Event types (`event_type`) | Class |
|---|---|---|
| OB `_BAR_COLS`/`_EVENT_COLS` | `FIRST_TOUCH`, `FIRST_FAR_SIDE_WICK_BREACH`, `FIRST_FAR_SIDE_CLOSE_BREACH`, `FIRST_CLOSE_RECLAIM_OF_FAR_SIDE` + zone geometry & displacement facts | CLOSED FACT |
| FVG `_BAR`/`_E` | `FIRST_TOUCH`, `FIRST_FULL_RANGE_COVERAGE`, `FIRST_FAR_SIDE_WICK_BREACH`, `FIRST_FAR_SIDE_CLOSE_BREACH`, `FIRST_CLOSE_RECLAIM_OF_FAR_SIDE` + gap/width/midpoint facts | CLOSED FACT |
| Dealing range 4.2B | `dealing_range_created`, `current_range_id/direction/low/high/width/midpoint`, `current_range_position_raw`, endpoint classes | CLOSED FACT |

"Mitigated"/"institutionally defended" states are **NOT CURRENTLY AVAILABLE**
and must not be invented.

### A.5 Flow / volume evolution (Layer 3)

ACTUAL mode (3.1/3.2):

```text
order_flow_mode, total_classified_volume, raw_delta, delta_ratio, delta_ratio_percentile(+history_count),
delta_magnitude(+percentile+history_count), classified_volume_fraction,
aggression_response_alignment, aligned/opposed_response_magnitude/percentile(+history_count),
aggression_extremeness, response_weakness, actual_absorption_evidence, absorbed_aggression_side
```

PROXY mode (3.1/3.2):

```text
close_location_proxy, volume_pressure_proxy, signed_volume_pressure_raw,
pressure_proxy_percentile(+history_count), pressure_magnitude(+percentile+history_count),
pressure_response_alignment, pressure_aligned/opposed_response_*, proxy_pressure_extremeness,
proxy_response_weakness, proxy_absorption_evidence, pressure_side
```

All CLOSED FACT. ACTUAL and PROXY stay in separate source modes forever.

### A.6 Volatility / temporal / MTF evolution

- 1.1 volatility surface: CLOSED FACT (A.1).
- 1.2 session active flags/boundaries: CLOSED FACT.
- 5.1 HTF: per-bar as-of `last_completed_htf_open/high/low/close/volume`,
  `htf_bucket_end_utc`, `htf_source_bar_count`, plus the completed-bucket table
  with `bucket_start/end_utc`, `theoretical_available_at`, `first_observed_asof_position/time`,
  source timestamps, OHLC, volume: CLOSED FACT.
- 5.2 confluence matrix: `configured/available/unavailable_scale_count`,
  `up/down/mixed/undefined_structure_count`, `directional_scale_count`,
  `availability_fraction`, `directional_fraction/balance/consensus/conflict`,
  and per-scale `__available/__structure_state/__structure_direction_code/__information_age_seconds`:
  CLOSED FACT (decision-aligned; see C.6 for trajectory use).

### A.7 Narrative / lifecycle / outcome facts (6.1B, 6.2A)

- hypothesis types/direction/foundation/resolution/contradiction (6.1B) — CLOSED FACT.
- lifecycle ledger: `CONTRADICTED`, `SUPERSEDED`, `OBSERVED_DIRECTION_ESTABLISHED`;
  trigger relationship/event ids; terminal key (6.2A-1) — CLOSED FACT.
- 6.2A-1 path segments (`PRE_ENDPOINT`, `ENDPOINT_BAR`, `OBSERVED_THROUGH_AS_OF`),
  per-segment favorable/adverse excursion fractions + extreme prices+positions,
  `same_bar_order_ambiguous`, `reference_price(+source+key)`, `right_censored_as_of` — CLOSED FACT.
- 6.2A-2 label interval (`label_interval_start/end_inclusive`), mature-only gating — CLOSED FACT.
- 6.2A-3 `_TARGET_COLUMNS`, `sample_metadata`, fold/sample-set/eligibility hashes — CLOSED FACT.
- 6.2B-0 reasoning family/record/provenance/derivation snapshots at creation — CLOSED FACT.

### A.8 What is NOT CURRENTLY AVAILABLE (do not fabricate)

| Missing fact | Status |
|---|---|
| tick/trade sequence, intrabar high-low chronology | NOT CURRENTLY AVAILABLE (OHLC only) |
| L2 / order-book depth, resting-order certification | NOT CURRENTLY AVAILABLE |
| venue/instrument/feed/symbol-lifecycle provenance, funding, gaps/outages | NOT CURRENTLY AVAILABLE (reserve fields, see §P) |
| fills, fees, slippage, position, PnL | NOT CURRENTLY AVAILABLE (execution is later, separate) |
| "mitigation"/"institutional defense"/"smart-money" labels | NOT CURRENTLY AVAILABLE (forbidden semantic laundering) |
| generic terminal lifecycle / `pivot_id` | NOT CURRENTLY AVAILABLE (documented boundary) |

---

## B. Source/version + availability InformationKey for every fact class

Every observation row carries both clocks (§2 of mission):

- `decision_information_key` — immutable, `<= t0` (DECISION CLOCK).
- `observation_information_key` and `factual_available_at_information_key` — when
  the fact became legally knowable (OUTCOME CLOCK). For completed-bar facts this
  is the completed-bar key; for event streams it is the event bar's key; for
  terminal facts it is the terminal key; for censored snapshots it is the as-of
  boundary key.

| Fact class | Source module/version | Available-at rule |
|---|---|---|
| OHLC/volume bar | dataset contract `CAUSAL_RESEARCH_DATASET_V1` | bar's completed-row key |
| volatility | 1.1 `DynamicVolatilityEngine` | completed-bar key at that bar |
| session | 1.2 `CausalSessionContextEngine` | completed-bar key |
| swing/sequence/break | 2.1A/B/C | confirmation/break completed-bar key (swing confirmed only at confirmation, not origin) |
| liquidity events | 2.2 | event bar completed key |
| OB/FVG/range | 4.1/4.2A/4.2B | creation/touch/breach/reclaim event key |
| flow/absorption | 3.1/3.2 (ACTUAL/PROXY) | completed-bar key, mode preserved |
| HTF bucket | 5.1 | `theoretical_available_at`/`first_observed_asof` of bucket close (no incomplete bucket) |
| MTF confluence | 5.2 | re-derived as-of each observation bar from completed scales only |
| lifecycle terminal | 6.1B/6.2A-1 | terminal event key |
| excursion segments | 6.2A-1 `FACTUAL_HYPOTHESIS_OUTCOME_V1_1` | segment-end / as-of key |

Eligibility to **train** on any outcome-derived record uses the observation/as-of
key, never the decision key (two-clock rule). A terminal event at t17 does not
exist for a cutoff at t10.

---

## C. Normalized schemas (the six surfaces)

No list/dict cells. No one giant DataFrame. Immutable event ledger + deterministic
as-of reconstruction.

### C.1 `decision_anchor` (one row per hypothesis; never contains future facts)

```text
hypothesis_id, hypothesis_type, direction, timeline_id,
decision_snapshot_hash, decision_information_key,
frozen_evidence_vector_hash (6.1A), frozen_narrative_hash (6.1B),
frozen_reasoning_semantic_hash (6.2B-0),
reference_price, reference_information_key, reference_is_execution_price=False,
creation_bar_position, creation_event_time_utc,
context_volatility_unit (1.1 at creation — CLOSED FACT, not future),
anchor_contract_version, anchor_hash
```

`anchor_hash` is the canonical identity; it must be byte-identical regardless of
any later observation.

### C.2 `future_observation_events` (append-only ledger; the raw trajectory)

```text
observation_event_id (canonical hash, no Python hash()/no random)
hypothesis_id, decision_snapshot_hash
observation_information_key, factual_available_at_information_key
observation_position (bar offset from creation)
observation_batch_id (same InformationKey grouping)
source_module, source_module_version, source_contract
source_mode (ACTUAL / PROXY / NONE)
epistemic_status (FACTUAL / FACTUAL_GEOMETRY / PROJECT_OPERATIONAL / SOURCE_APPROXIMATION)
observation_domain (PRICE / STRUCTURE / LIQUIDITY / OB / FVG / RANGE / FLOW / VOLATILITY / SESSION / MTF / LIFECYCLE)
observation_type (typed enum per domain, see §I)
value_type (NONE / FLOAT / INTEGER / BOOLEAN / CATEGORY / POSITION / PRICE / KEY)
value_float, value_integer, value_boolean, value_category
value_position (Int64), value_key_json (canonical; only when key-typed)
source_entity_id (level_id/zone_id/fvg_id/range_id/scale_name where applicable)
source_event_id (lifecycle ledger event_id / break event where applicable)
provenance_relation_id (where 6.1B provides it)
same_bar_order_ambiguous (bool)
observation_hash (canonical over the row)
```

Append-only: a later observation inserts rows; it never updates or deletes prior
rows. This single table is enough to reconstruct the trajectory.

### C.3 `path_state_checkpoints` (optional, materialized only if benchmarks justify)

Rather than copy full state every bar, define a deterministic
`reconstruct_state(events, through_key)` and optionally materialize sparse
checkpoints. If materialized:

```text
hypothesis_id, as_of_information_key, as_of_position,
running_favorable_excursion_fraction, running_adverse_excursion_fraction,
favorable_extreme_price(+position), adverse_extreme_price(+position),
running_favorable_extreme_count, running_adverse_extreme_count,
current_structure_state, current_structure_sequence_class,
current_range_id(+position_raw), current_mtf_balance/consensus/conflict,
current_volatility_state_summary, current_hypothesis_lifecycle_state,
known_*_counts (liquidity/OB/FVG),
checkpoint_hash, reconstructable_from_event_hash_chain
```

The event ledger is authoritative; checkpoints are a cache, verifiable by
reconstruction.

### C.4 `terminal_or_censor_snapshots`

One row per **episode resolution attempt**. Critically, censored snapshots and
the later mature snapshot are **separate immutable rows with separate identities**
(§7 of mission):

```text
hypothesis_id, decision_snapshot_hash
episode_kind ∈ { MATURE_TERMINAL, RIGHT_CENSORED_AS_OF }
terminal_state ∈ { CONTRADICTED, SUPERSEDED, OBSERVED_DIRECTION_ESTABLISHED, <NA for censor> }
terminal_event_id, trigger_relationship_id, terminal_information_key
as_of_information_key (for censor: the boundary; for mature: terminal key)
observed_path_start_exclusive_position, observed_path_end_inclusive_position
observed_bar_count
favorable_excursion_fraction, adverse_excursion_fraction
favorable_extreme_price(+position), adverse_extreme_price(+position)
favorable_extreme_information_key, adverse_extreme_information_key
pre_endpoint_* / endpoint_bar_* facts (mapped from 6.2A-1 segments)
same_bar_terminal_ambiguous
censor_reason ∈ { DATA_BOUNDARY, WALK_FORWARD_BOUNDARY, <NA> }
supersession_chain_depth, parent_hypothesis_id (where knowable)
outcome_contract_version, snapshot_hash, mature_outcome_id (NA until mature)
```

T1 censored snapshot remains byte-identical after T2/T3 mature outcome exists.

### C.5 `raw_outcome_facts`

A typed long-form projection of C.2 restricted to outcome-relevant facts
(excursion, extremes, terminal, segment summaries) for convenient joins, with a
foreign key to `observation_event_id`. It is a view/projection, never a second
source of truth.

### C.6 `hypothesis_dependence_relations` (factual only; §13)

```text
hypothesis_id_a, hypothesis_id_b
relation_type ∈ { SAME_DECISION_BATCH, OVERLAPPING_OBSERVATION_INTERVAL,
                  SUPERSESSION_RELATION, SHARED_CERTIFIED_ENTITY, SHARED_FUTURE_PATH_GROUP }
evidence_key (entity id / interval / chain id that proves the relation)
source_contract, relation_hash
```

Only relations provable from public contracts are emitted. Non-overlap is never
certified as statistical independence.

### C.7 `derived_descriptor_registry` + `derived_descriptor_values`

Registry (metadata, versioned, hashed):

```text
descriptor_id, descriptor_version, formula_hash, raw_parent_observation_ids,
exact_algorithm, output_units, information_availability_semantics,
missingness_behavior, ambiguity_behavior, causal_status,
information_loss_property ∈ { NONE / DOCUMENTED }, monotonicity, rationale,
research_role, descriptor_hash
```

Values (long form, foreign-keyed to a terminal/censor snapshot or as-of key):

```text
hypothesis_id, snapshot_hash, descriptor_id, descriptor_version,
as_of_information_key, value_float/int/bool/category, descriptor_value_hash
```

### C.8 `objective_estimand_manifest`

Versioned catalog of learning questions (§L). Holds estimand id/version, required
raw facts, admissible hypothesis types, censor/competing-event/ambiguity
treatment, dependence assumptions, availability rule, eligibility, metric class,
and forbidden interpretations. No model is implemented here.

---

## D. Terminal legality matrix (all four hypothesis types)

From 6.1B: types are `UPWARD/DOWNWARD_CONTINUATION_AFTER_PROJECT_BREAK` and
`UPWARD/DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT`. Terminal states come only from
the CLOSED ledger. No state is auto-labelled win/loss.

| hypothesis_type | terminal_state | can occur? | source contract | exact factual meaning | mature endpoint? | supports estimand? |
|---|---|---|---|---|---|---|
| continuation (UP/DOWN) | OBSERVED_DIRECTION_ESTABLISHED | yes (continuation confirmed along direction) | 6.1B/6.2A-1 | expected-direction structure observed/established | yes | competing-terminal / excursion |
| continuation | CONTRADICTED | yes | 6.1B/6.2A-1 | opposing structure appeared (e.g. DOWN_STRUCTURE for UP) | yes | competing-terminal / excursion |
| continuation | SUPERSEDED | yes | 6.1B/6.2A-1 | replaced by a newer related hypothesis | yes | competing-terminal (competing risk) |
| transition (UP/DOWN) | OBSERVED_DIRECTION_ESTABLISHED | yes | 6.1B (`resolution`: later structure in the new direction) | post-shift expected-direction structure established | yes | competing-terminal / excursion |
| transition | CONTRADICTED | yes | 6.1B (`contradiction`: new opposite foundation / same-row opposite foundation blocks establishment) | transition invalidated | yes | competing-terminal / excursion |
| transition | SUPERSEDED | yes | 6.1B/6.2A-1 | replaced in chain | yes | competing-terminal |
| any | RIGHT_CENSORED_AS_OF | yes | 6.2A-1 | no terminal fact by as-of boundary; observed path retained | no (partial) | censor-aware estimands only |

Limitations: RESEARCH-DEBT-020 is **not** closed by this matrix; it is the
per-type semantics contract that a later build freezes. Continuation has no
positive "success" beyond `OBSERVED_DIRECTION_ESTABLISHED`; that state is a
factual structural event, **not** a profit claim. Transition semantics depend on
the `resolution`/`contradiction` foundations and must be audited per type.

---

## E. Raw path facts legally reconstructable now

From CLOSED OHLC + lifecycle + segment + per-bar engines, reconstructable
exactly (EXACT DERIVATION unless noted):

- running favorable/adverse excursion fraction at every observed bar (signed by
  direction, from reference), with running extreme positions/times;
- count and positions of new running favorable/adverse extremes;
- close-relative displacement from reference per bar;
- bar true range / normalized range / percentile at each bar;
- per-bar confirmed structure state, sequence class, break events;
- all liquidity/OB/FVG/range event streams with positions, ages, distances;
- per-bar flow/absorption facts in ACTUAL vs PROXY;
- per-bar completed HTF OHLC + scale availability/balance/conflict;
- position/time offset to favorable extreme, adverse extreme, and terminal event;
- number of structural transitions, liquidity/OB/FVG interactions along path;
- pre-endpoint vs endpoint-bar excursion split (already in 6.2A-1);
- full event-ordered trajectory across certified InformationKeys.

## F. Path facts NOT reconstructable from current data

- which of high vs low came first **within one OHLC bar**;
- intrabar path/microstructure beyond H/L;
- tick/trade velocity, resting-order absorption at L2;
- real fillable prices/slippage;
- any "clean/rocket/healthy/manipulation" subjective class (banned from raw;
  allowed only later as a derived/learned descriptor, see §J).

## G. As-of censor snapshot lifecycle (§7)

```text
t0 decision frozen
  -> at T1 unresolved: append snapshot episode_kind=RIGHT_CENSORED_AS_OF, as_of=T1 (immutable)
  -> at T2 more path:   append a NEW censor snapshot as_of=T2 (does NOT touch T1)
  -> at T3 mature:      append MATURE_TERMINAL snapshot as_of=T3 (new identity)
```

Enforced: T1 row hash unchanged after T2/T3; mature outcome has its own
`mature_outcome_id`; walk-forward can train on censored partial facts at T1
without "knowing the future" and on mature facts only after T3.

## H. Two-clock chronology (§8)

Ordering relation across observations is one of:

```text
BEFORE / AFTER / SAME_INFORMATION_BATCH_ORDER_UNKNOWN / NOT_COMPARABLE
```

Across different completed bars/keys ordering is factual. Within one OHLC bar,
favorable-vs-adverse ordering is `SAME_INFORMATION_BATCH_ORDER_UNKNOWN` (driven by
`same_bar_order_ambiguous`); descriptors must read this flag and output
`UNKNOWABLE`, not guess. A future finer (tick) source may add a new
source_mode/version without rewriting OHLC rows (§N).

## I. Trajectory event taxonomy

`observation_type` is a closed enum per domain, e.g.:

```text
PRICE: BAR_CLOSE, NEW_FAVORABLE_EXTREME, NEW_ADVERSE_EXTREME,
       DISPLACEMENT_FROM_REFERENCE, TRUE_RANGE, NORMALIZED_TRUE_RANGE, TR_PERCENTILE
STRUCTURE: SWING_CONFIRMED, SEQUENCE_CLASS, BREAK_EVENT, STATE_CHANGE
LIQUIDITY: LEVEL_CREATED, FIRST_TOUCH, FIRST_WICK_BREACH, FIRST_CLOSE_BREACH, FIRST_RECLAIM
OB/FVG/RANGE: CANDIDATE_CREATED, FIRST_TOUCH, FAR_SIDE_WICK_BREACH, FAR_SIDE_CLOSE_BREACH, RECLAIM, FULL_RANGE_COVERAGE
FLOW: DELTA, ABSORPTION, RESPONSE_ALIGNMENT (mode-tagged)
VOLATILITY: EXPANSION, CONTRACTION, PERCENTILE
SESSION: SESSION_STATE
MTF: BUCKET_COMPLETED, SCALE_STATE_CHANGE, CONFLICT_CHANGE
LIFECYCLE: STATE_TRANSITION, CONTRADICTION, SUPERSESSION, DIRECTION_ESTABLISHED, CENSORED
```

No parallel state machine: lifecycle events are read from 6.1B only; if a needed
event is absent it is NOT_AVAILABLE, never re-derived here.

## J. Raw-vs-derived boundary (§9, §10)

RAW (C.2) contains only emitted facts. The following MUST be derived, each with
a registry entry, never hand-labelled truth:

```text
realized_directional_balance = favorable - adverse
directional_capture_ratio    = favorable / (favorable + adverse)   (lossy when denom 0 -> NaN)
path_efficiency, cleanliness, volatility-normalized excursion (creation-context and evolving-context variants)
speed, acceleration, retracement_depth, recovery_ratio, tortuosity
favorable-before-adverse / adverse-before-favorable  (only when order is certified; else UNKNOWABLE)
duration_to_extreme / duration_to_terminal
interaction_counts (structural/liquidity/OB/FVG)
```

Subjective words (rocket, healthy, manipulation) are banned from descriptors too;
they may only emerge as learned latent patterns downstream, with provenance.

## K. Context normalization without magic (§11)

Keep three separate factual dimensions:

1. raw price movement / raw excursion fraction (CLOSED FACT);
2. creation-time causal volatility unit (1.1 at t0, EXACT DERIVATION);
3. observation-time causal volatility context at tk (CLOSED FACT per bar).

Descriptors may compute movement-relative-to-creation-context and
movement-relative-to-evolving-context as EXACT DERIVATIONs, and rank relative to
TRAIN history in a later TRAIN-only preprocessing contract. No future data sets
the creation normalizer; no arbitrary trailing window is introduced here.

## L. Estimand catalog (§16) — versioned, not implemented

```text
E-TERM   competing terminal-event distribution under censoring (4-class incl censor)
E-EXC    favorable/adverse excursion distribution + quantiles
E-TIME   position/time-to-certified-event/extreme distributions
E-TRAJ   distribution over sequences of certified state transitions
E-JOINT  joint (terminal, favorable, adverse, timing, observable state)
E-COND   P(factual state at later legal event/as-of | evidence at t0)
```

Each estimand declares admissible types, required raw facts, censoring treatment,
competing-event treatment, ambiguity treatment, dependence assumptions,
availability rule, training eligibility, metric class, and forbidden
interpretations. None may be called "profit/win probability" without a future
execution contract.

## M. ACTUAL/PROXY rules (§14 in mission)

Every observation row is source_mode tagged. ACTUAL and PROXY never merge, never
impute one from the other, and never prioritize one as "more predictive" a
priori. Unavailable flow stays unavailable (no zero-fill). Descriptors are
computed within mode; cross-mode comparison is a later estimand choice, not a raw
fact.

## N. MTF causal rules (§3, §14)

- only fully completed HTF buckets are visible (`5.1` as-of alignment); an
  incomplete HTF candle is invisible at every LTF bar it spans;
- a later HTF close becomes visible only after its `theoretical_available_at`,
  never before;
- changing future HTF cannot alter an earlier trajectory snapshot (append-only +
  as-of reconstruction);
- scale conflict/balance/consensus re-derived per observation bar from completed
  scales only.

## O. Data-resolution hierarchy (§14)

```text
OHLC  -> bar extremes known; within-bar chronology unknown
tick  -> (future) finer event sequence under its own source contract
L2    -> (future) quotes/depth under its own source contract
```

Coarse sources cannot make claims needing finer resolution. A new finer source is
a new source_mode/version; historical coarse facts remain valid and immutable.

## P. Data-quality / crypto reality provenance (§24)

Reserve nullable provenance columns on the decision anchor / dataset metadata
(default NOT CURRENTLY AVAILABLE): `venue, instrument, market_type, feed/source,
timestamp_semantics, data_gap_flag, exchange_outage_flag, contract_spec_version,
symbol_lifecycle, funding_where_relevant, source_availability`. Do not fabricate
values. These must be populated before any portable live-performance claim and
are part of DEBT-025 scope.

## Q. Identity / hashing (§26)

Use existing `canonical_sha256` (domain-separated) and canonical serialization.
Separate identities:

```text
anchor_hash                  decision only, no future facts
observation_event_hash       per event, content-bound
trajectory_snapshot_hash     as-of episode identity (censor or mature)
mature_outcome_id            CLOSED 6.2A-1 identity
descriptor_hash / descriptor_value_hash
estimand_id
```

A prior censored snapshot identity never contains the later terminal fact. No
Python `hash()`, no random ids, no unkeyed origin-authentication claim.

## R. Storage / performance (§25)

Normalized tables in §C. Event ledger is the source of truth; state is
reconstructed deterministically; checkpoints optional and hash-verifiable. No
list/dict cells. No unrestricted future-history object crosses into live modules;
only immutable creation contracts (6.1A/6.1B/6.2B-0) flow live; this observer
lives entirely in the research side (research may consume live contracts; live
never imports research/outcome modules).

## S. Exact causal / adversarial test plan (§27)

Decision causality: future mutation/append cannot change `anchor_hash`.
As-of causality: observation at T excludes >T facts; T1 censor snapshot is
byte-identical after T2/T3; terminal at t17 absent at cutoff t10.
Trajectory: cross-key ordering correct; same-bar order UNKNOWN; no backfill;
exact reconstruction from event ledger matches materialized state.
Terminal: each legal terminal type + boundary; competing-event distinction;
mature vs censor identities.
Path: favorable-only, adverse-only, favorable→adverse, adverse→favorable across
bars, both-in-same-bar→unknown, multiple extremes, terminal on extreme bar, no
extreme beyond reference.
MTF: incomplete HTF invisible; late HTF visible only after close; future HTF
can't mutate earlier snapshot.
Flow: ACTUAL/PROXY never merge; unavailable stays unavailable.
Dependence: overlapping intervals detected; non-overlap not certified independent;
supersession chain; shared decision batch; shared path group.
Identity: decision hash future-invariant; event hash content-bound; later
snapshot new identity; forged source/provenance rejects.
State: A→A, A→B→A, fresh-instance, input immutability.
Firewall: live decision cannot import observer/outcome; future outcome never
enters same-time evidence.

## T. Debt status matrix (§28)

| Debt | Design direction exists? | Contract implemented? | Debt closed? |
|---|---|---|---|
| 020 lifecycle termination | yes — per-type terminal matrix (§D) anchors to CLOSED ledger, no TTL | no | **NO** |
| 023 censoring/competing-risk | yes — immutable censor series + 4-class competing events make it estimable | no (estimator not chosen) | **NO** |
| 024 overlap/non-IID | yes — factual `hypothesis_dependence_relations` | no (no grouping/estimator) | **NO** |
| 025 reference/market-time | walls off execution reference; reserves venue/time provenance | no | **NO** |
| 022 entity narrative provenance | untouched; observer consumes 6.2B-0 only | no | remains open |

A rich trajectory table closes none of these automatically.

## U. Blockers requiring a new adapter or CLOSED patch

- **NEW DOWNSTREAM FACT (no CLOSED patch):** per-bar re-creation of the 5.2
  confluence state at every *future* observation bar (the CLOSED 5.2 is
  decision-aligned). Build a research adapter that replays completed scales
  through 5.2 at each as-of bar — do **not** patch 5.2.
- **NEW DOWNSTREAM FACT:** per-bar flow/volatility/session along the future path
  are available by replaying CLOSED engines over the visible slice (EXACT
  DERIVATION via engines; a small research driver assembles them).
- **NOT CURRENTLY AVAILABLE:** venue/instrument/feed provenance, tick/L2,
  fills/costs. These need new data adapters/contracts before execution.
- **WOULD REQUIRE CLOSED PATCH:** none in this design. If a needed fact requires
  changing a CLOSED module, it must go through a versioned PATCH ONLY task — this
  design deliberately avoids that.

## V. Recommended staged BUILD order

```text
Stage 0  design sign-off (this document) + open questions resolved
Stage 1  6.2A-4 contract/schemas + decision_anchor + two-clock keys + hashing
Stage 2  raw future_observation_events for PRICE/STRUCTURE/LIFECYCLE + exact reconstruction
Stage 3  censor-snapshot series + terminal mapping (§D) + 6.2A-1 segment binding
Stage 4  LIQUIDITY/OB/FVG/RANGE/FLOW/VOLATILITY/SESSION/MTF observation events
Stage 5  hypothesis_dependence_relations (factual only)
Stage 6  derived_descriptor_registry + first audited descriptors (chronology-safe)
Stage 7  objective_estimand_manifest (catalog; still no model)
Stage 8  (separate authorization) TRAIN predictive calibration over an estimand,
         dependence-aware validation, NULL/SIMPLE/FULL + ablations
```

Each stage is independently auditable and closure-gated; no stage jumps to
geometry/execution.

## W. End-to-end map to eventual net economic recommendation

```text
CLOSED causal engines (L0–5)
  -> 6.1A evidence vector / 6.1B narrative (frozen at t0)
  -> 6.2B-0 reasoning semantics/provenance
  -> 6.2B-1 TRAIN descriptive calibration
  -> 6.2A-4 future trajectory + terminal/censor facts (THIS DESIGN)   [Y]
  -> estimand catalog + (later) dependence-aware predictive calibration  [P(Y|X_t0)]
  -> future live B-2 inference produces DISTRIBUTIONS at new decisions
  -> geometry generates candidate entry/stop/target plans (separate module)
  -> execution economics (fills/costs/slippage/capacity) score each plan against Y distributions
  -> economic decision: LONG / SHORT / WAIT / NO_TRADE with uncertainty + provenance
```

The brain first learns the shape of the future (Y), geometry proposes what is
exploitable, and economics decides. No layer contaminates the one above it.

---

## Final answer to the central question

> "What do we want the brain to learn from the future?"

**The richest causally legal factual trajectory and its terminal/censor fate —
not a win/loss label.** We observe, with two explicit clocks and immutable as-of
snapshots, how price, structure, liquidity, zones, flow, volatility, and MTF
state actually evolved after each frozen hypothesis until a CLOSED lifecycle
event or an honest censor. We keep ACTUAL/PROXY, chronology-known vs unknown,
mature vs censored, and overlapping vs distinct as separate facts. We register
path descriptors explicitly (never as hand-labelled truth) and define estimands
separately from facts. Later, a model learns conditional distributions over this
multi-surface outcome, geometry proposes plans, and economics converts
distributions into LONG/SHORT/WAIT/NO_TRADE.

Nothing here is a probability, a trade, a guaranteed edge, or a closed debt.

Factual Future Trajectory / Learning Objective
DESIGN PROPOSAL — NOT IMPLEMENTED

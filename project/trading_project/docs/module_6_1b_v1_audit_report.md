# Module 6.1B V1.2 — Causal Market Narrative / Hypothesis Engine

Status: **CLOSED**

## Closure decision

```text
Module 6.1B V1.2
ACCEPTED FOR CLOSURE
CLOSED
```

Closure history:

```text
V1 -> V1.1 -> V1.2 -> CLOSED
```

Certified baseline:

```text
Narrative tests: 48 passed
Full suite: 392 collected / 392 passed
```

Closure certifies causal descriptive narrative behavior, deterministic
hypothesis lifecycle, exact provenance, and the zero-lookahead replay contract
within tested scope.

Closure does not certify predictive edge, profitability, ICT canonical fidelity
beyond D1/D1.1, scorer quality, weights, probabilities, entries, exits, or
entity-level liquidity/zone narratives.

`RESEARCH-DEBT-020`, `RESEARCH-DEBT-021`, and `RESEARCH-DEBT-022` remain open.
They are not claimed solved by closure.

## V1.2 patch history

The read-only V1.1 audit identified that `freshness_column`, although part of
the closed Module 6.1A V1.3 FeatureSpec manifest, was not included in 6.1B's
exact certified metadata comparison. V1.2 adds `freshness_column` to the
required schema, certified metadata construction, field-by-field comparison,
and forged-manifest adversarial coverage. The V1.1 defect remains recorded
here rather than being erased from patch history.

V1.2 replaces the lossy generic `source_value_numeric` provenance field with
certified-domain-driven nullable columns:

```text
source_value_float       Float64
source_value_integer     Int64
source_value_boolean     boolean
source_value_category    string
```

Exactly one value column is populated for each AVAILABLE source scalar.
`expected_domain == count` is stored as an exact integer, `bool` as a boolean,
certified category domains as strings, and certified continuous numeric domains
as floats. UNKNOWN values leave every typed value column missing. No generic
object value, list, or dictionary cell is used. Counts above `2**53` therefore
retain exact provenance, and fingerprints retain domain and typed identity so
large adjacent integers, booleans, integers, and floats do not collapse.

V1.2 explicitly contracts structure-absent operation as
`OBSERVATION_ONLY_NO_STRUCTURAL_FOUNDATION`: when the certified structure group
is disabled, no structural MarketHypothesis is created. Other complete enabled
certified groups may still emit their implemented descriptive observations.
No trajectory hypothesis is fabricated without a structural foundation.

## V1.1 patch history

V1.1 preserves the four-hypothesis V1 scope and patches only Module 6.1B.
The supplied 6.1A manifest is now checked field-by-field against the closed
Module 6.1A V1.3 `V1_CATALOG`; selected catalog groups must be complete and
ACTUAL/PROXY groups cannot coexist. Forged source mode, epistemic status,
event-locality, output identity, semantic, missingness, support-link,
directional, domain, or module metadata is rejected.

`relationship_sources` now provides normalized source-value provenance through
`source_value_numeric`, `source_value_category`, and
`source_availability_state`. Every emitted relationship can therefore be
reconstructed from immutable source links, including all MTF descriptors, all
four dealing-range coordinates, absorption, side, opposed-response percentile,
and its support count. `DEALING_RANGE_GEOMETRY.primary_numeric_value` has the
static meaning `current_range_position_raw`; it no longer depends on which
value happens to be available.

`relationship_ledger` is explicitly an **append-on-change ledger**. A new row is
emitted when role, bearing, event-locality, primary descriptors, availability,
provenance, or any normalized source value changes. Fingerprints canonicalize
`None`, `pd.NA`, `np.nan`, NumPy scalars, nullable values, and booleans without
ambiguous truth-value evaluation.

For a monitoring transition, a later same-row proposed-direction state and
explicit opposite structural foundation have equal information time. V1.1
uses the non-overclaiming policy that the explicit opposite foundation blocks
positive establishment and terminates the hypothesis as `CONTRADICTED`; no
intrabar ordering is inferred.

Lifecycle surface counts are derived from emitted ledger events. `CREATED`
contributes only to `nar__new_hypothesis_count`; `STATE_CHANGED` and
`SUPERSEDED` contribute to `nar__hypothesis_state_change_count`. Supersession
references the already-created replacement foundation relationship and actual
replacement hypothesis ID. All terminal events require a valid trigger
relationship.

The original V1 implementation and its 24-test/368-suite validation remain the
pre-patch baseline recorded below; V1.1 validation results are recorded in the
validation section without erasing that history.

## Scope

Module 6.1B consumes a certified 6.1A evidence DataFrame and static feature
manifest. It separates deduplicated narrative observations from four structural
trajectory propositions under monitoring. It emits no score, weight,
probability, confidence, signal, outcome, or model.

## Four hypotheses

```text
UPWARD_CONTINUATION_AFTER_PROJECT_BREAK
DOWNWARD_CONTINUATION_AFTER_PROJECT_BREAK
UPWARD_TRANSITION_AFTER_PROJECT_SHIFT
DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT
```

Continuation foundations combine structure state and matching project BOS label
as one `LOCAL_STRUCTURAL_FOUNDATION` relationship. Transition foundations
require a prior opposite persistent state plus current project CHOCH label.
BOS/CHoCH remain project operational terminology.

## Bearings

```text
ALIGNS_WITH
DIRECTIONALLY_OPPOSES
CONTRADICTS
CONTEXTUALIZES
QUALIFIES
NEUTRAL
UNKNOWN
NOT_APPLICABLE
```

Predictive `SUPPORTS` is absent. Flow, absorption, zones, range, volatility,
time, and MTF are descriptive/contextual only.

## Lifecycle

```text
MONITORING
OBSERVED_DIRECTION_ESTABLISHED
CONTRADICTED
SUPERSEDED
```

Only `MONITORING` is active. Transition establishment requires a later row.
Continuation has no positive success state. Same-type foundations supersede
prior monitoring instances. No fixed TTL or decay exists.

## Outputs

`NarrativeResult` contains exactly:

```text
narrative_surface
observation_ledger
active_hypotheses
hypothesis_ledger
relationship_ledger
relationship_sources
narrative_manifest
```

`active_hypotheses` is the final current active set only. Ledgers are append-only
within causal replay. Same-row facts share one batch ID; serialization order is
bookkeeping, not claimed market sequence.

## Causal verification

Exact tests cover persistent-observation deduplication, foundations, no same-row
transition resolution, contradiction/supersession, descriptive MTF/flow/range
relationships, ACTUAL/PROXY provenance, correlated-family collapse, same-row
ambiguity, all secondary-ledger truncation, future mutation/append, A→B→A,
fresh-instance determinism, stable IDs, manifest stability, and outcome-column
rejection.

Real integrations include 3.1→3.2 ACTUAL/PROXY and
2.1B→2.1C→4.2B→5.2→6.1A→6.1B.

```text
Module tests: 24 passed
Full suite: 368 passed
```

```text
........................................................................ [ 19%]
........................................................................ [ 39%]
........................................................................ [ 58%]
........................................................................ [ 78%]
........................................................................ [ 97%]
........                                                                 [100%]
```

## V1.1 validation

```text
Narrative tests:                    44 passed
Adversarial manifest selection:     15 passed
Secondary-table causal selection:    5 passed
Full collection:                   388 collected
Full suite:                        388 passed
```

```text
........................................................................ [ 18%]
........................................................................ [ 37%]
........................................................................ [ 55%]
........................................................................ [ 74%]
........................................................................ [ 92%]
............................                                             [100%]
```

The exact secondary-table checks include truncation, future mutation, future
append, same-instance A→B→A, fresh-instance determinism, relationship IDs,
source-value rows, observations, and hypothesis lifecycle events. Dedicated
checks cover input immutability, duplicate identities, missing columns, forged
certified metadata, exact output-index preservation, empty input, same-row
terminal conflict, lifecycle event counts, and source/terminal referential
integrity.

## V1.2 validation

```text
Narrative tests:                    48 passed
Secondary-table causal selection:    4 passed
Full collection:                   392 collected
Full suite:                        392 passed
```

```text
........................................................................ [ 18%]
........................................................................ [ 36%]
........................................................................ [ 55%]
........................................................................ [ 73%]
........................................................................ [ 91%]
................................                                         [100%]
```

V1.2 adds exact tests for forged `freshness_column`, certified-domain-driven
nullable provenance dtypes, adjacent integer values above `2**53`, exact huge
integer truncation/future-append stability, true boolean provenance, and a
non-empty structure-disabled liquidity observation path. The pre-existing exact
truncation, future mutation, future append, A→B→A, fresh-instance, observation,
hypothesis-event, relationship-ID, and relationship-source checks continue to
pass with the expanded deterministic schema.

## Open debts

- `RESEARCH-DEBT-020`: lifecycle termination semantics.
- `RESEARCH-DEBT-021`: predictive evidence-bearing calibration.
- `RESEARCH-DEBT-022`: entity-level narrative provenance.

## Limitations

V1 does not build persistent liquidity/zone entity stories, predictive support,
majority voting, diagnostic support counts, generic plugins, streaming state,
or any trading decision. Continuation hypotheses remain unresolved until
contradicted or superseded.

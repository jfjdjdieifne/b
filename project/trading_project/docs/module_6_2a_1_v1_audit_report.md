# Module 6.2A-1 V1.2 — Factual Hypothesis Outcome Observer

Status: **CLOSED**

## Closure decision

```text
Module 6.2A-1 V1.2
ACCEPTED FOR CLOSURE
CLOSED
```

Closure history:

```text
V1 -> V1.1 -> V1.2 -> CLOSED
```

Certified baseline:

```text
Module 6.2A-1 dedicated tests: 71 passed
Full suite: 540 collected / 540 passed
```

Closure certifies only factual post-hypothesis outcome observation, as-of
censoring facts, non-executable reference-mark timing, post-creation path
segmentation, exact mature outcome identity, future/as-of isolation, and the
absence of trade interpretation within tested scope.

Closure does not certify training eligibility, an estimator, a model,
predictive edge, profitability, scorer, weights, or signals. Module 6.2A-2 has
not started.

The following debts remain open and are not claimed solved:

```text
RESEARCH-DEBT-020
RESEARCH-DEBT-021
RESEARCH-DEBT-022
RESEARCH-DEBT-023
RESEARCH-DEBT-025
```

`RESEARCH-DEBT-024` has not been created.

## V1.2 patch history

V1.2 defines `decision_snapshot_hash` explicitly as the
`HYPOTHESIS_CREATION_DECISION_SNAPSHOT` identity. Its payload is limited to the
complete creation evidence row, complete creation narrative-surface row, the
single CREATED ledger event, all same-hypothesis same-row relationships and
their sources, all same-row observations, certified static manifest hashes,
reference identity, timeline, snapshot type, and hypothesis ID. It does not
claim to represent the entire prior narrative history or other hypotheses.

Creation history now requires exactly one same-row lifecycle record for the
selected hypothesis, and that record must be its exact CREATED event. Malformed
additional same-row lifecycle history is rejected before decision hashing.
The hashed creation-ledger subset repeats this exact-one-CREATED invariant.

For censored as-of snapshots, `factual_outcome_id` is now missing because no
final factual outcome exists. Their provisional identity remains represented by
`research_snapshot_id` and `research_outcome_hash`. Mature outcomes receive a
nonmissing `factual_outcome_id` that remains stable under later as-of and future
append, while as-of-specific snapshot/research hashes may change.

Regression coverage proves the creation decision hash is exact across B1/B2
and later observation/relationship/lifecycle mutation, while a legitimate
same-row dealing-range context change alters the decision hash without changing
the reference or future terminal path.

Patch history remains:

```text
V1 -> V1.1 -> V1.2 — PENDING AUDIT
```

## V1.1 patch history

The V1 read-only audit identified a critical provenance defect: the observer
trusted a `VisibleAsOfBundle` dataclass type without exact seal revalidation. A
caller could manually attach post-as-of market or ledger rows while retaining
an earlier `research_as_of`, allowing terminal/path logic to discover future
content.

V1.1 now performs visible-bundle seal validation before creation identity or
any other semantic logic. It verifies the closed 6.2A-0 visibility contract
version, repackages the supplied tables as a frozen bundle, reprojects them at
exactly the claimed as-of through the CLOSED `AsOfVisibilityProjector`, and
requires exact equality for all projected tables and contract identities. A
malformed bundle is rejected; it is never silently repaired and consumed.

V1.1 also enforces at most one terminal lifecycle event total per hypothesis.
Multiple terminals, including same-position events with different
serialization values, are rejected rather than ordered by bookkeeping fields.
Supersession now additionally requires one visible replacement CREATED event,
the same terminal position, and exact replacement-foundation trigger identity.

Canonical hash representation remains unchanged. Regression tests now
explicitly cover positive versus negative zero, both infinities, naive
timestamps, and unsupported object scalars.

## Scope

Research-only factual observation over a CLOSED Module 6.2A-0
`VisibleAsOfBundle`. V1 supports only `HYPOTHESIS_CREATION_SNAPSHOT`. It does
not accept `FrozenDecisionSnapshotBundle`, generate evaluation snapshots, build
training eligibility, fit a model, score a setup, or create trade WIN/LOSS
labels.

## Firewall and terminal authority

The observer accepts only `VisibleAsOfBundle`; future filtering remains the
exclusive authority of closed 6.2A-0. Primary terminal state is read only from
the visible certified 6.1B `hypothesis_ledger` and is restricted to
`CONTRADICTED`, `SUPERSEDED`, or `OBSERVED_DIRECTION_ESTABLISHED`. Raw structure,
BOS, CHOCH, or price movement never creates a second terminal state machine.

The selected hypothesis must have exactly one visible CREATED event. Its
foundation trigger must be a visible same-hypothesis
`LOCAL_STRUCTURAL_FOUNDATION` relationship with role `FOUNDATION`, bearing
`CONTEXTUALIZES`, and the same creation position. Hypothesis type is recovered
from that certified foundation identity and direction from the exact certified
6.1B narrative manifest. No raw-structure inference is used.

Terminal InformationKey must be strictly later than creation InformationKey.
Same-batch terminal records are rejected. Non-supersession terminal triggers
must belong to the observed hypothesis. A supersession trigger must be the
visible replacement hypothesis foundation identified by
`superseded_by_hypothesis_id`.

## Reference timing

The V1 reference is creation-row completed close:

```text
CREATION_ROW_COMPLETED_CLOSE_RESEARCH_REFERENCE_MARK
reference_is_execution_price = False
```

Close must be numeric, finite, and positive. There is no fallback. Creation-row
high/low are excluded from every path slice and hash; adversarial mutation of
those values leaves all factual outputs exact.

## Maturity and censoring

Visible later terminal:

```text
outcome_mature = True
right_censored_as_of = False
final_outcome_known_at = terminal InformationKey
```

No visible terminal:

```text
outcome_mature = False
right_censored_as_of = True
censoring_type = RIGHT_CENSORED_AS_OF_BOUNDARY
final_outcome_known_at = missing
snapshot_status_known_at = VisibleAsOfBundle.research_as_of
```

Censoring is an as-of research fact, not failure, neutrality, or zero outcome.
B1 censored and B2 mature observations receive distinct deterministic snapshot
and research hashes. B1 remains immutable.

## Path segmentation

Resolved records emit:

```text
PRE_ENDPOINT: creation_position < row < terminal_position
ENDPOINT_BAR: row == terminal_position
```

Censored records emit:

```text
OBSERVED_THROUGH_AS_OF:
creation_position < row <= research_as_of.bar_position
```

No creation row and no stored `THROUGH_ENDPOINT` segment exist. Empty segments
have count zero, availability false, and missing excursion/extreme fields.

Included high/low values must be numeric, finite, positive, and satisfy
`high >= low`. Invalid included rows fail; malformed rows after as-of or after a
mature terminal are not inspected. Extreme ties use the earliest visible bar
position as an audit tie-break. Any included bar with `high > reference` and
`low < reference` sets `same_bar_order_ambiguous=True`; no intrabar order is
inferred.

## Directional measurements

UP:

```text
favorable = max(0, max(high / reference - 1))
adverse   = max(0, max(1 - low / reference))
```

DOWN:

```text
favorable = max(0, max(1 - low / reference))
adverse   = max(0, max(high / reference - 1))
```

These are direction-relative market-path fractions, not PnL. There is no ATR,
fixed horizon, future volatility, entry, stop, target, fill, or profitability
label.

## Hash contracts

`hashing.py` implements versioned canonical SHA-256 identities with explicit
type tags, stable mapping/column/row order, DataFrame dtypes and indexes, exact
integer strings, exact finite-float hex representation, normalized UTC
nanoseconds, and an explicit missing marker. Python built-in `hash()` is not
used for persisted identities.

Hashes:

```text
feature_manifest_hash
narrative_manifest_hash
decision_input_slice_hash
decision_snapshot_hash
research_market_slice_hash
research_outcome_hash
```

`decision_snapshot_hash` is created from a closed 6.2A-0 projection down to the
creation InformationKey and then restricted to the creation evidence row,
narrative row, selected-hypothesis creation ledger/relationships/sources,
creation-row observations, static manifest hashes, timeline identity, and the
close-only reference identity. Later terminal/market/outcome content is
excluded.

`research_market_slice_hash` covers exactly the post-creation path through the
visible terminal or current as-of boundary. Empty slices retain explicit schema
and deterministic identity.

`research_snapshot_id` includes research as-of and therefore changes between
B1/B2. `factual_outcome_id` is missing for censored snapshots; after maturity it
identifies terminal/path facts, excludes later as-of, and remains stable under
future append. `research_outcome_hash` remains as-of-specific.

## Output schemas

`FactualOutcomeResult` returns exactly:

```text
hypothesis_outcome_snapshots
outcome_path_segments
outcome_manifest
```

Snapshot table is one row per `observe()` call and preserves expanded typed
InformationKey fields for research as-of, creation snapshot, reference,
terminal, snapshot-status-known, and final-outcome-known identities. Integer,
float, boolean, string, and UTC timestamp columns use nullable deterministic
pandas dtypes.

Path output is normalized with one row per segment and no list/dict cells.

## State and immutability

The observer is stateless. Repeated A→A, A→B→A, and fresh-instance outputs are
exact. Input VisibleAsOfBundle DataFrames are never mutated. Closed 6.2A-0 is
used for creation-time hash projection rather than recreating visibility rules.

## Real integration

Dedicated integration executes real:

```text
2.1B ConfirmedSwingSequenceEngine
-> 2.1C CausalStructuralBreakEngine
-> 6.1A CausalEvidenceVectorEngine
-> 6.1B CausalMarketNarrativeEngine
-> 6.2A-0 AsOfVisibilityProjector
-> 6.2A-1 FactualHypothesisOutcomeObserver
```

It covers one upward continuation hypothesis that is censored before and
contradicted after its terminal row, and one upward transition hypothesis that
is censored before and reaches `OBSERVED_DIRECTION_ESTABLISHED` after its
terminal row. Creation identity, reference close, terminal visibility, and path
segments are verified without modifying closed modules.

## V1 validation baseline

```text
Canonical hashing tests:       10 passed
Outcome observer tests:        43 passed
Real pipeline integration:      2 passed
New Module 6.2A-1 total:       55 passed
Research tests including 6.2A-0: 132 passed
Full collection:              524 collected
Full suite:                   524 passed
```

## V1.1 validation

```text
Canonical hashing tests:       14 passed
Outcome observer tests:        52 passed
Real pipeline integration:      2 passed
New Module 6.2A-1 total:       68 passed
Research tests including 6.2A-0: 145 passed
Forged/censor/state selection: 11 passed
Full collection:              537 collected
Full suite:                   537 passed
```

```text
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 40%]
........................................................................ [ 53%]
........................................................................ [ 67%]
........................................................................ [ 80%]
........................................................................ [ 93%]
.................................                                        [100%]
```

## V1.2 validation

```text
Canonical hashing tests:       14 passed
Outcome observer tests:        55 passed
Real pipeline integration:      2 passed
New Module 6.2A-1 total:       71 passed
Research tests including 6.2A-0: 148 passed
Identity-contract selection:    4 passed
Full collection:              540 collected
Full suite:                   540 passed
```

```text
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 40%]
........................................................................ [ 53%]
........................................................................ [ 66%]
........................................................................ [ 80%]
........................................................................ [ 93%]
....................................                                     [100%]
```

## Research debts

Open and not solved:

```text
RESEARCH-DEBT-020
RESEARCH-DEBT-021
RESEARCH-DEBT-022
```

Created by this implementation:

```text
RESEARCH-DEBT-023 — Outcome Censoring and Competing-Risk Estimand
RESEARCH-DEBT-025 — Reference-Price and Market-Time Alignment
```

`RESEARCH-DEBT-024` was not created because overlap/dependence implementation
has not begun.

## Limitations

Not implemented:

```text
6.2A-2 temporal eligibility builder
evaluation snapshots
competing-risk/survival estimator
overlap/dependence graph
model/scorer/weights/probabilities/signals
entry/stop/target/execution/fees
trade profitability labels
```

V1 assumes the closed 6.1B foundation relationship category and exact static
narrative definition provide the certified hypothesis identity. Market lineage
beyond the 6.2A-0 timeline identity is deferred under RESEARCH-DEBT-025.

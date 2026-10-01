# Module 6.2A-2 V1 — Temporal Training Eligibility / Research Dataset Gate

Status: **CLOSED**

## Closure decision

```text
Module 6.2A-2 V1
ACCEPTED FOR CLOSURE
CLOSED
```

Certified baseline:

```text
Dedicated eligibility tests: 26 passed
Full suite: 566 collected / 566 passed
```

Closure certifies strict InformationKey-based temporal eligibility at cutoff T,
mature-outcome legality, preservation of censored/immature audit rows without
loss/failure recoding, deterministic outcome-neutral earliest-as-of
deduplication, conflicting factual-identity rejection, deterministic reason
precedence within the validated row contract, zero feature/model leakage, and
full CLOSED 6.2A-0/6.2A-1 integration within tested scope.

Closure does not certify feature transformation, X/y dataset construction,
overlapping-interval dependence resolution, estimator/model quality, scorer,
weights, probabilities, or signals.

The following debts remain open and are not claimed solved:

```text
RESEARCH-DEBT-020
RESEARCH-DEBT-021
RESEARCH-DEBT-022
RESEARCH-DEBT-023
RESEARCH-DEBT-024
RESEARCH-DEBT-025
```

## Scope

Module 6.2A-2 evaluates temporal legality of CLOSED 6.2A-1 factual research
snapshots under one explicit `InformationKey` cutoff. It emits exactly two
normalized tables:

```text
temporal_eligibility_audit
selected_mature_samples
```

The static `eligibility_manifest()` is available separately and is not a third
result table. No feature matrix, imputation, scaling, encoding, feature
selection, interaction, sample weight, estimator, model, scorer, probability,
or trade signal is produced.

## Input authority

`FactualOutcomeBatch` contains exact CLOSED 6.2A-1 V1.2 snapshot, path, and
outcome-manifest tables. Validation requires exact columns/order, deterministic
nullable dtypes, exact static outcome-manifest identity, unique research
snapshot IDs, complete path parentage, no orphan paths, and valid mature versus
censored segment cardinality/order.

The caller supplies an explicit positional or time-indexed adapter and an
explicit training-cutoff `InformationKey`. Bare positions, timestamps, implicit
latest rows, adapter inference, and cross-timeline cutoffs are rejected.

## InformationKey decoding

Flattened snapshot, terminal, final-known, and research-as-of key fields are
decoded strictly. Version, nonnegative integer positions/sequences, phase,
timeline, and adapter-specific timestamp semantics are validated. Partial keys,
bool/float positions, unknown phases, naive timestamps, positional timestamps,
and missing required keys are rejected without guessing.

## Hash verification

The gate imports the CLOSED canonical SHA-256 utility and recomputes:

```text
research_snapshot_id
mature factual_outcome_id
research_outcome_hash
```

using the exact V1.2 domains and path-segment payloads. Censored records must
have missing `factual_outcome_id`. Research, feature-manifest,
narrative-manifest, decision-input, market-slice, and decision hashes must be
valid lowercase SHA-256 strings.

`decision_snapshot_hash` is deliberately treated as an opaque immutable
provenance join key because its creation preimage is not present in 6.2A-1
outcome tables. It is format-validated and required to be strictly consistent
across duplicate mature factual records; it is not falsely claimed to be
independently recomputed here. Likewise, `research_market_slice_hash` is bound
into recomputed factual/research identities but its raw market preimage is not
available to the gate.

Tampered path values or stored research/factual hashes fail identity
verification. The static 6.2A-1 outcome manifest is compared exactly.

## Eligibility contract

A row is eligible only when:

```text
snapshot_type == HYPOTHESIS_CREATION_SNAPSHOT
snapshot_information_key < training_cutoff
outcome_mature == True
right_censored_as_of == False
factual_outcome_id nonmissing
final_outcome_known nonmissing
terminal key nonmissing
final_outcome_known == terminal key
final_outcome_known <= training_cutoff
terminal key <= training_cutoff
contract/hash identity valid
```

Equality at the terminal analytical key is eligible. A cutoff on the same bar
but before the terminal analytical sequence is ineligible. InformationKey, not
timestamp alone, controls the boundary.

## Deterministic reason precedence

```text
1  CONTRACT_VERSION_MISMATCH
2  HASH_VALIDATION_FAILED
3  UNSUPPORTED_SNAPSHOT_TYPE
4  TIMELINE_MISMATCH
5  OUTCOME_IMMATURE
6  RIGHT_CENSORED
7  FACTUAL_OUTCOME_ID_MISSING
8  FINAL_OUTCOME_KEY_MISSING
9  TERMINAL_KEY_MISSING
10 FINAL_TERMINAL_KEY_MISMATCH
11 SNAPSHOT_NOT_BEFORE_CUTOFF
12 FINAL_OUTCOME_AFTER_CUTOFF
13 TERMINAL_AFTER_CUTOFF
14 ELIGIBLE
```

Structural batch failures such as schema mismatch, duplicate snapshot IDs,
orphan paths, impossible segment contracts, and conflicting duplicate factual
identities raise contract/data errors rather than receiving arbitrary row
reasons.

Every structurally valid input snapshot receives one audit row in original
input order, including censored and otherwise ineligible records. Censoring is
never recoded as loss, zero, neutrality, or failure.

## Deduplication

Only individually eligible rows enter selection. Records are grouped by:

```text
decision_snapshot_hash
hypothesis_id
snapshot_type
factual_outcome_id
```

All rows sharing one factual ID must agree exactly on decision identity,
hypothesis identity, direction, snapshot/reference identity, terminal linkage,
final-known key, research market-slice hash, and normalized path facts.
Conflicts raise `EligibilityDataError`.

For one group, the selected provenance row is the earliest
`research_as_of InformationKey`; exact-key ties use lexicographically smallest
`research_snapshot_id`. No excursion, terminal category, or favorable result
participates in selection. Repeated mature B2/B3 observations produce one
selected sample. Earlier censored B1 remains an ineligible audit row.

## Label-information interval

Each selected row exposes:

```text
label_information_start_exclusive = snapshot InformationKey
label_information_end_inclusive   = final_outcome_known InformationKey
```

This records `(snapshot, final-known]`, the future information interval used by
the factual outcome. It is not used here for weighting, overlap deletion,
embargo, clustering, or model validation.

## Output contracts

`temporal_eligibility_audit` preserves input row ordinal, identities, exact
cutoff, flattened snapshot/terminal/final keys, boolean eligibility, one reason,
and contract version.

`selected_mature_samples` contains only deduplicated mature identity/provenance
fields and exact label-interval boundaries. No feature values or transformations
are present.

## State and immutability

The gate is stateless. Repeated A→A, A→B→A, and fresh-instance outputs are exact.
Input snapshots, path segments, and manifests are not mutated. Cutoff-specific
outputs are new records; evaluating a later cutoff does not rewrite an earlier
audit result.

## Real integration

The integration test executes:

```text
2.1B -> 2.1C -> 6.1A -> 6.1B -> 6.2A-0 -> 6.2A-1 -> 6.2A-2
```

Before terminal, B1 is preserved as `OUTCOME_IMMATURE` and no sample is
selected. At the exact completed-row analytical terminal key, B2 is eligible.
At a later cutoff, B2/B3 remain two eligible audit records but deduplicate to
the earliest mature B2 provenance and one selected factual sample.

## Validation

```text
Eligibility unit/adversarial tests: 25 passed
Real eligibility integration:        1 passed
Module 6.2A-2 total:                 26 passed
Full collection:                    566 collected
Full suite:                         566 passed
```

```text
........................................................................ [ 12%]
........................................................................ [ 25%]
........................................................................ [ 38%]
........................................................................ [ 50%]
........................................................................ [ 63%]
........................................................................ [ 76%]
........................................................................ [ 89%]
..............................................................           [100%]
```

## Research debt

Created:

```text
RESEARCH-DEBT-024 — Overlapping Hypothesis Dependence / Non-IID Research Samples
```

6.2A-2 solves temporal legality and repeated-as-of deduplication only. It does
not claim selected hypotheses are IID and does not solve overlapping label
intervals, supersession-chain dependence, shared future paths, or
uncertainty/validation clustering.

Existing debts 020, 021, 022, 023, and 025 remain open.

## Limitations

- Decision snapshot preimages are unavailable here; their hashes are opaque
  provenance keys with consistency checks, not independently recomputed claims.
- Raw market slices are unavailable; market-slice hashes are transitively bound
  into verified outcome identities but not independently regenerated.
- Time-indexed keys require explicit adapter semantics; the gate does not infer
  a missing market timeline.
- `TERMINAL_AFTER_CUTOFF` is defensive under V1.2 because final and terminal
  keys must be equal, so final-after-cutoff normally takes precedence.
- No feature dataset, CV split, estimator, model, scorer, weight, signal, or
  trading decision exists.

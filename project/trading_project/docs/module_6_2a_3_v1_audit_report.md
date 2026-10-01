# Module 6.2A-3 V1.1 — Causal Research Dataset Builder & Walk-Forward Splitter

Status: **CLOSED**

## Closure decision

```text
Module 6.2A-3 V1.1
ACCEPTED FOR CLOSURE
CLOSED
```

Closure history:

```text
V1 -> V1.1 -> CLOSED
```

Certified baseline:

```text
Dedicated dataset-builder tests: 23 passed
Full suite: 589 collected / 589 passed
```

Closure certifies within tested scope: exact attested 1-to-1-to-1 feature/outcome
joins, strict `ev__*`/`nar__*` feature isolation, causal walk-forward boundaries,
temporal purge enforcement, preservation of immature TEST targets as missing
without cohort distortion, complete frozen decision-feature attestation,
upstream eligibility reseal, and end-to-end closed-pipeline integration.

Closure does not certify preprocessing, scaling, imputation, feature selection,
models, classifiers, estimators, scorer, weights, probabilities, signals, or
overlapping-hypothesis dependence resolution.

The following debts remain open and are not claimed solved:

```text
RESEARCH-DEBT-020
RESEARCH-DEBT-021
RESEARCH-DEBT-022
RESEARCH-DEBT-023
RESEARCH-DEBT-024
RESEARCH-DEBT-025
```

## V1.1 patch history

V1.1 is a focused regression-hardening patch. It adds direct narrative-row
attestation mutation coverage, a mocked upstream purge-violation test that
reaches and verifies `UPSTREAM_ELIGIBILITY_CONTRACT_VIOLATION`, and an explicit
TEST evaluation-as-of case where the hypothesis remains immature and therefore
retains raw TEST features with fully missing targets.

The TEST audit vocabulary now records `TEST_TARGET_IMMATURE` for an included
TEST feature row without a mature factual target, while records outside TEST use
`NOT_APPLICABLE`. No feature, target, split, preprocessing, or model semantics
were expanded.

Dataset contract version:

```text
CAUSAL_RESEARCH_DATASET_V1_1
```

Patch history:

```text
V1 -> V1.1 — PENDING AUDIT
```

## Scope

Module 6.2A-3 V1 builds deterministic raw TRAIN/TEST feature and factual-target
tables from CLOSED research contracts. It performs exact identity joins,
explicit InformationKey walk-forward boundaries, mature TRAIN legality checks,
optional as-of TEST target attachment, label-interval audit, and fold hashing.

It does not fit scalers, encoders, imputers, feature selectors, estimators,
models, scorers, weights, probabilities, or signals.

## Decision feature snapshot attestation

`FrozenDecisionFeatureSnapshot` carries the exact creation evidence row,
creation narrative-surface row, CREATED event, same-row observations,
same-hypothesis relationships and their sources, certified static manifests,
reference identity, snapshot key, hypothesis identity, and stored decision
hashes.

Verification recomputes:

```text
decision_input_slice_hash
HYPOTHESIS_CREATION_DECISION_SNAPSHOT_V1_2
```

using the CLOSED canonical SHA-256 contract. It also validates the certified
6.1A/6.1B manifests, hypothesis foundation/type/direction, reference timing,
relationship parentage, and exact one-row feature snapshots. Tampered raw
features or mismatched identity fail before dataset joining.

`freeze_creation_feature_snapshot()` reseals the supplied VisibleAsOfBundle
through CLOSED 6.2A-0 and projects to the creation InformationKey before
constructing the attested snapshot. No live analytical module is rerun.

## Walk-forward contract

`WalkForwardFoldSpec` requires explicit same-timeline InformationKeys:

```text
train_cutoff
test_creation_end_inclusive
test_label_as_of | missing
```

The test interval is:

```text
(train_cutoff, test_creation_end_inclusive]
```

Test target attachment requires an explicit `test_label_as_of`; it is never
inferred from test creation end. Without it, TEST features remain present and
all TEST targets are nullable/unavailable.

## Eligibility reseal

Supplied CLOSED 6.2A-2 results are not trusted by dataclass type alone. The
builder reruns the CLOSED `TemporalEligibilityGate` over the supplied factual
batch at the exact TRAIN or TEST-evaluation cutoff and requires exact equality
of audit and selected tables. Forged eligibility selections reject.

TRAIN starts exclusively from CLOSED selected mature samples at `train_cutoff`.
A defensive assertion requires each label interval end to be at or before the
test start/train cutoff. A violation is an upstream contract error, not a
silently accepted sample.

## Join semantics

TRAIN join keys:

```text
decision_snapshot_hash + hypothesis_id + snapshot_type
factual_outcome_id + selected_research_snapshot_id
```

TEST features are selected only from snapshot InformationKeys in the explicit
creation interval. Outcome data never influence TEST cohort membership. TEST
targets are attached only by intersecting with CLOSED 6.2A-2 selections at the
explicit evaluation as-of.

All feature snapshot identities are unique and all included feature rows must
share exact column order and dtypes. Many-to-many, missing, duplicate,
hypothesis-type, timeline, manifest, decision-hash, and factual-ID mismatches
reject.

## Feature and target boundary

Raw X consists only of the complete attested creation-time columns:

```text
certified ev__* evidence row
certified nar__* narrative_surface row
```

Identifiers and all outcome/research/terminal/final-known fields remain outside
X in metadata.

Raw factual targets are copied from CLOSED 6.2A-1:

```text
target_terminal_state
target_pre_endpoint_favorable_excursion_fraction
target_pre_endpoint_adverse_excursion_fraction
target_pre_endpoint_same_bar_order_ambiguous
target_endpoint_bar_favorable_excursion_fraction
target_endpoint_bar_adverse_excursion_fraction
target_endpoint_bar_same_bar_order_ambiguous
```

These are factual research outcomes, not trade WIN/LOSS/PnL labels. TEST rows
without mature targets retain the same nullable target schema and
`target_available=False` metadata.

## Outputs

`ResearchDatasetFold` returns:

```text
train_features_raw
train_targets
test_features_raw
test_targets
sample_metadata
fold_manifest
```

`ResearchDatasetBuildResult` additionally returns normalized
`dataset_build_audit` with one row for every supplied feature snapshot,
including snapshots outside the fold. No inner join silently discards rows.

TRAIN and TEST raw feature tables use exactly the same columns/order/dtypes even
when one split is empty. No transformed feature table exists in V1.

## Label intervals and dependence

Metadata preserves flattened typed snapshot/final/label-interval InformationKey
fields. TRAIN label intervals must end by the test start. Pairwise overlap
counts/flags are factual diagnostics only; they do not delete, weight, cluster,
or embargo samples.

`RESEARCH-DEBT-024` remains open. Temporal legality and deduplication do not
make hypotheses IID.

## Deterministic identity

Canonical SHA-256 identities include:

```text
sample_id
fold_spec_hash
raw_feature_schema_hash
target_schema_hash
train_sample_set_hash
test_sample_set_hash
dataset_fold_hash
```

No UUID, Python built-in hash, wall clock, or performance-dependent boundary is
used.

## State and immutability

The builder is stateless. A→A, A→B→A, fresh-instance, input-immutability, stable
ordering, and exact fold-hash tests pass. Later as-of target availability does
not alter TEST feature cohort membership. Future market changes after a mature
terminal do not alter historical eligibility or fold output.

## Real integration

The integration executes:

```text
2.1B -> 2.1C -> 6.1A -> 6.1B -> 6.2A-0 -> 6.2A-1 -> 6.2A-2 -> 6.2A-3
```

Fold 1 has no TRAIN sample and one TEST creation whose target becomes available
at an explicit later evaluation as-of. Fold 2 advances the cutoff so the same
mature factual outcome becomes one legal TRAIN sample. Fold 1 remains immutable.

## V1 validation baseline

```text
Dataset builder unit/adversarial tests: 19 passed
Real walk-forward integration:           1 passed
Module 6.2A-3 total:                    20 passed
Full collection:                       586 collected
Full suite:                            586 passed
```

## V1.1 validation

```text
Dataset builder unit/adversarial tests: 22 passed
Real walk-forward integration:           1 passed
Module 6.2A-3 total:                    23 passed
Full collection:                       589 collected
Full suite:                            589 passed
```

```text
........................................................................ [ 12%]
........................................................................ [ 24%]
........................................................................ [ 36%]
........................................................................ [ 48%]
........................................................................ [ 61%]
........................................................................ [ 73%]
........................................................................ [ 85%]
........................................................................ [ 97%]
.............                                                            [100%]
```

## Closed-module boundary

No analytical module from Layers 0–5, 6.1A, 6.1B, 6.2A-0, 6.2A-1, or 6.2A-2
was modified. The research package root export surface was also left unchanged;
V1 APIs are imported directly from `dataset_contracts` and `dataset_builder`.

## Limitations

- V1 produces raw features only; preprocessing is deferred.
- No model-ready numeric matrix is claimed for mixed categorical/nullable raw
  features.
- No feature selection or interaction generation exists.
- Statistical dependence and clustered/block uncertainty remain unresolved
  under RESEARCH-DEBT-024.
- TEST records without mature outcomes remain target-unavailable; no scoring is
  performed.
- No model, estimator, scorer, weight, probability, or trade signal exists.

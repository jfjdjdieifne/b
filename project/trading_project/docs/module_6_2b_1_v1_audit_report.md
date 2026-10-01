# Module 6.2B-1 V1.1 — Walk-Forward Adaptive Confluence Calibration Builder

Status: **PATCHED / IMPLEMENTED — PENDING AUDIT**

## 1. Preflight state

Authoritative baseline before build:

```text
Module 6.2B-0 V1.2 CLOSED
654 collected
654 passed
MANIFEST.sha256: e2a4f88b5dfbfda11f9933d2d7fa794536750186f2cf3f36810ae2c5d3d7c7fb
133 manifest entries verified
```

No CLOSED production/test file was modified. B-1 lives in the new
`trading_system.calibration` package.

## 2. Objective gate

The current repository provides factual mature targets:

```text
target_terminal_state
target_pre_endpoint_favorable_excursion_fraction
target_pre_endpoint_adverse_excursion_fraction
target_endpoint_bar_favorable_excursion_fraction
target_endpoint_bar_adverse_excursion_fraction
same-bar ordering ambiguity facts
```

These are factual research observations, not a frozen QualificationObjective.
`RESEARCH-DEBT-020` leaves hypothesis lifecycle termination/estimand semantics
unresolved. V1 therefore does **not** choose a predictive target or fabricate
WIN/LOSS, return horizon, R multiple, target-before-stop, profitability, or
qualification semantics.

```text
objective_id = OBJECTIVE_UNDEFINED_RESEARCH_DEBT_020
objective_status = OBJECTIVE_UNDEFINED
qualification_artifact_status = NOT_BUILT_OBJECTIVE_UNDEFINED
```

`QualificationCalibrationArtifact` is deliberately not built.

## 3. Legally supported artifact

V1 builds `ConfluenceCalibrationArtifact` as a TRAIN-only descriptive support
artifact. It contains no predictive model or score. It freezes:

- exact training cutoff `InformationKey`;
- CLOSED fold spec and train sample-set identities;
- CLOSED eligibility manifest identity;
- 6.2A-3 dataset contract identity;
- B-0 reasoning contract identity and final record hashes;
- TRAIN-only reasoning/sample projection hash;
- family/feature empirical support counts;
- TRAIN empirical numeric CDF surfaces labelled `NOT_PROBABILITY`;
- exact categorical frequencies;
- availability-signature support;
- explicit baseline/ablation admission surfaces;
- unresolved-overlap diagnostics;
- append-only experiment-attempt ledger entry;
- canonical artifact/content hashes.

## 4. Exact training legality

For each admitted TRAIN sample V1 requires:

```text
sample_id in CLOSED 6.2A-3 train_features_raw
sample_id in TRAIN metadata
sample_id has matching B-0 reasoning result
target_available == True
factual_outcome_id present
final_outcome_known <= train_cutoff
label_interval_end_inclusive <= train_cutoff
reasoning decision InformationKey <= train_cutoff
fold_spec_hash exact
train_sample_set_hash exact
eligibility_manifest_hash exact
B-0 record hashes exact
```

TEST feature/target values and full `dataset_fold_hash` are not part of the
TRAIN artifact identity because the CLOSED dataset fold hash includes TEST
content. Instead V1 computes a separate TRAIN-only projection hash over:

```text
train_features_raw
train metadata
reasoning identities
train schema
fold/cutoff identity
```

Mutating or appending TEST data cannot alter the artifact. Mutating TRAIN data
changes the training projection and artifact identity.

## 5. Calibration/model architecture

Chosen architecture:

```text
DESCRIPTIVE_EMPIRICAL_COVERAGE_ONLY
IDENTITY_TYPED_NO_FITTED_TRANSFORM_V1
NO_PREDICTIVE_MODEL_OBJECTIVE_UNDEFINED_V1
NO_PREDICTIVE_INTERACTIONS_OBJECTIVE_UNDEFINED
```

This is the smallest defensible architecture because no legal qualification
estimand exists. No regression/classifier, coefficient, feature importance,
threshold, PCA, clustering, regime discovery, smoothing fit, or hyperparameter
search is performed.

## 6. Adaptive rather than hardcoded

The artifact learns only factual TRAIN distributions:

- observed family/semantic/availability combinations;
- observed source-mode-specific feature support;
- empirical continuous distributions;
- categorical frequencies;
- observed availability patterns.

No market meaning is hardcoded. The system may expose zero observations or
unsupported patterns without inventing a conclusion. Predictive contextual
usefulness remains blocked until an objective is separately frozen.

## 7. Context/regime handling

No fixed regimes or bins are created. Continuous values remain continuous in
TRAIN empirical CDF tables. Categorical/semantic contexts remain explicit.
No volatility, premium/discount, session, MTF, OB, FVG, or liquidity threshold
is introduced.

## 8. Memory/history handling

No fixed lookback or raw-history dump is added. B-1 consumes only CLOSED
6.2A-3 TRAIN samples and B-0 creation reasoning snapshots. Relevance remains
bounded by upstream causal state/lifecycle/summary contracts.

## 9. Deterministic/correlated evidence

B-0 provenance and derivation fields are preserved in feature support. V1:

- rejects duplicate B-0 record IDs;
- never turns deterministic repetition into an importance vote;
- does not delete merely correlated features;
- fits no importance because the objective is undefined;
- does not use provenance as statistical-independence proof.

## 10. Missingness

`UNKNOWN` and `UNAVAILABLE` remain distinct semantic/availability states.
Availability signatures are counted explicitly. There is no zero fill, silent
drop, or family renormalization.

Unsupported patterns remain:

```text
NOT_CALIBRATED
```

## 11. ACTUAL / PROXY

Source modes remain separate in every support/distribution grouping.

```text
ACTUAL_PROXY_SEPARATE_NO_PREDICTIVE_PRIORITY
```

ACTUAL is not assumed more useful; PROXY cannot masquerade as ACTUAL.

## 12. Overlap / non-IID

V1 preserves CLOSED within-TRAIN overlap metadata and emits:

```text
DEPENDENCE_NOT_RESOLVED
```

`cross_split_label_overlap_detected` is derived using the TEST cohort, so B-1
explicitly excludes it from TRAIN identity and diagnostics and emits
`NOT_ACCESSED_OOS_FIREWALL` instead. It does not report effective IID sample
count, invent an embargo, or claim that raw sample count equals independent
evidence. `RESEARCH-DEBT-024` remains open.

## 13. Baseline contracts

Every build requires explicit variants:

```text
NULL_CONSTANT
SIMPLE_ENGINEERED_MARKET_CONTEXT
FULL_EVIDENCE_FAMILY
```

NULL admits no families. SIMPLE must be an explicit proper subset of the
explicit engineered market-context allowlist:

```text
LOCAL_STRUCTURE_STATE
MULTISCALE_STRUCTURE
VOLATILITY_CONTEXT
TEMPORAL_CONTEXT
DATA_AVAILABILITY
```

FULL admits the exact TRAIN family schema. These are admission contracts, not
claims that any baseline is useful or winning.

## 14. Ablation contract

`FAMILY_ABLATION` is exact `FULL - explicitly withheld families`. It does not
retune on OOS, perform subset search, or automatically select a family. The
artifact emits a normalized per-feature admission table for reproducibility.

## 15. Experiment accounting

The ledger records:

- experiment ID and sequence;
- training cutoff identity;
- fold/sample/projection/schema identities;
- objective/version;
- feature/family specification;
- interactions/preprocessing/model specifications;
- hyperparameters and seed;
- variant/baseline/ablation identity;
- evaluation role;
- caller-reported prior OOS access count;
- attempt status (`SPECIFIED`, `ARTIFACT_BUILT`, or `FAILED`);
- failure reason or artifact hash;
- canonical ledger-entry hash.

Entries form a canonical previous-hash chain anchored to an externally trusted prior head. Mutation, reorder, truncation against that head, wrong heads, and duplicate experiment IDs reject. Failed attempts can be recorded. OOS-access count is caller-reported accounting metadata, not access-control proof.

## 16. Artifact schemas

`ConfluenceCalibrationArtifact` contains normalized tables:

```text
artifact_manifest
family_observation_coverage
feature_observation_coverage
numeric_empirical_cdf
categorical_distribution
availability_support
variant_feature_admission
stability_diagnostics
experiment_ledger_entry
calibration_manifest
```

No list/dict cells are emitted.

## 17. Every fitted component

```text
Component                     Fit data
----------------------------  -------------------------------------------
family support counts         eligible TRAIN B-0 family snapshots only
feature support counts        eligible TRAIN B-0 evidence records only
numeric empirical CDF         eligible TRAIN finite float values only
categorical frequencies       eligible TRAIN typed values only
availability support          eligible TRAIN B-0 signatures only
variant admission             immutable explicit variant specs
preprocessing                 none / identity typed
model parameters              none
interaction selection         none
threshold calibration         none
qualification artifact        not built
```

No TEST/future value can fit any component.

## 18. Baseline validation target

The artifact provides interfaces for later honest comparison but performs no
predictive evaluation. It does not call any difference an edge.

## 19. Scope firewall

No geometry, entry, stop, target planning, execution, fill, fees, slippage,
position sizing, trade lifecycle, BUY/SELL signal, PnL, WIN/LOSS, probability,
or expected-profit output is implemented.

## 20. Current limitations/debts

- `RESEARCH-DEBT-020`: QualificationObjective undefined;
- `RESEARCH-DEBT-021`: evidence-bearing calibration blocked by objective;
- `RESEARCH-DEBT-023`: competing-risk estimand unresolved;
- `RESEARCH-DEBT-024`: overlap/non-IID dependence unresolved;
- V1 supports one authoritative training fold per artifact;
- empirical CDF is descriptive TRAIN distribution, not probability;
- no predictive stability/uncertainty estimate is claimed without an objective;
- no qualification artifact exists.

## 21. V1 pre-patch validation

```text
syntax/compile: PASS
focused B-1 unit/adversarial tests: 21 passed
real 6.2A-3 -> B-0 -> B-1 integration tests: 2 passed
B-1 total: 23 passed
full collection: 677 collected
full suite: 677 passed
exit code: 0
existing CLOSED manifest entries: verified unchanged
```

## Status

```text
Module 6.2B-1 V1
PATCHED / IMPLEMENTED — PENDING AUDIT
```

## V1.1 integrity patch — authoritative boundaries

### A. CLOSED fold source seal

Before TRAIN projection, B-1 calls the exact CLOSED
`CausalResearchDatasetBuilder._fold_manifest` implementation and compares the
entire supplied fold manifest exactly. This covers dataset/fold/schema/sample/
eligibility identities and full source payload. Source verification is distinct
from TRAIN fitting: the final artifact binds source provenance, while
`calibration_content_hash` excludes TEST and target payload values.

### B. Canonical sample and factual identity

Each sample ID is recomputed through the exact CLOSED 6.2A-3 `_sample_id`
identity using fold ID plus the frozen decision snapshot. Arbitrary aliases
reject. `factual_outcome_id` cannot be recomputed without the upstream factual
batch at this boundary; V1.1 therefore requires canonical SHA-256 syntax and
binds it through the verified full CLOSED fold seal. This is integrity binding,
not issuer authentication.

### C. Authoritative B-0 membership

Every `ReasoningTrainingSample` carries its `FrozenDecisionFeatureSnapshot`.
B-1 verifies that snapshot, reconstructs the exact `ReasoningDecisionSnapshot`,
re-runs `DynamicEvidenceFamilyReasoner`, and compares every normalized B-0 table
exactly. Added/removed records, aliases, sources, edges, ledgers, provenance
relations, manifests, family hashes, and global semantic identity cannot pass.

### D. TRAIN raw row

`FrozenDecisionFeatureSnapshot.raw_feature_row()` is compared exactly against
the corresponding sealed 6.2A-3 TRAIN row. Index-only matching is insufficient.

### E/F. Coverage and baseline terminology

Public tables are now:

```text
family_observation_coverage
feature_observation_coverage
```

Every row carries:

```text
TRAIN_OBSERVATION_COVERAGE_NOT_SEMANTIC_OR_PREDICTIVE_SUPPORT
```

The simple baseline is named
`SIMPLE_ENGINEERED_MARKET_CONTEXT` and carries
`NOT_A_NON_ICT_PURITY_CLAIM`. Exact family and feature admission remains
normalized and no superiority is asserted.

### G/H. Ledger and OOS accounting

Ledger entries bind `previous_entry_hash`; genesis is explicit and versioned.
Append requires an externally trusted prior head. The chain detects mutation,
reorder, replacement, and truncation relative to that head. The head remains an
external research/release authority boundary.

`caller_reported_prior_oos_access_count` carries machine semantics
`CALLER_REPORTED_ACCOUNTING_NOT_ACCESS_CONTROL`; it never certifies untouched
OOS status.

### I/J. Artifact identity and verifier

V1.1 separates:

```text
source_dataset_fold_hash       full source provenance; may change with TEST
training_projection_hash        TRAIN-only projection identity
calibration_content_hash       TRAIN-only descriptive content
artifact_hash                  final source+content+policy provenance identity
```

The pre-hash manifest binds objective, cutoff, source fold/schema/target schema,
train samples, eligibility, dataset/B-0 versions, all component hashes,
hypothesis/source-mode scopes, missingness/dependence policies, preprocessing,
model/interactions blockers, selected variant, full variant plan, experiment
specification, and trusted prior ledger head.

`verify_confluence_calibration_artifact()` recomputes the projection, component,
selected-variant, experiment, content, artifact-ID, ledger-entry, and final
artifact hashes without TEST payload access.

## V1.1 remaining limits

- full source seal is unkeyed integrity verification, not trusted issuer authentication;
- factual outcome origin is strongest-bound through the verified CLOSED fold because the factual batch is not carried into B-1;
- trusted ledger head is external authority state;
- caller-reported OOS access is not technically enforced;
- QualificationObjective remains undefined and no predictive artifact exists.

## V1.1 validation

```text
syntax/compile: PASS
focused B-1 V1.1 unit/adversarial tests: 27 passed
real CLOSED integration tests: 2 passed
B-1 V1.1 total: 29 passed
integrity/leakage selection: 21 passed
CLOSED eligibility/dataset/B-0 regression selection: 114 passed
full collection: 683 collected
full suite: 683 passed
exit code: 0
existing CLOSED manifest: 133/133 verified unchanged
```

## V1.1 status

```text
Module 6.2B-1 V1.1
PATCHED / IMPLEMENTED — PENDING AUDIT
```

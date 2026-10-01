# Module 6.2B-0 V1.2 — Dynamic Evidence-Family Reasoning Contract

Status: **CLOSED**

Independent final re-audit decision: **ACCEPTED FOR CLOSURE**. Closure performed as a documentation/status/manifest release task with production and tests unchanged.

## Scope

Module 6.2B-0 normalizes one exact hypothesis-creation decision snapshot into factual evidence families, explicit semantic dimensions, source provenance, deterministic lineage, conservative provenance clusters, availability signatures, and a reasoning ledger.

It does not produce a score, learned weight, threshold, probability, qualification, geometry plan, entry, stop, target, execution instruction, signal, or trade result. V1.2 adds no predictive market rule.

## Input boundary and information time

`ReasoningDecisionSnapshot` is restricted to `COMPLETED_ROW_AVAILABLE` at the CLOSED analytical sequence. The CREATED lifecycle event, observations, and same-hypothesis relationships must all have `position == decision_position`. Historical rows are rejected rather than silently ignored. Future rows are rejected from causal position metadata before semantic payload access; attached relationship-source payload is not inspected when its parent relationship is future-illegal.

The reasoner recomputes the CLOSED `DECISION_INPUT_SLICE_V1_2` and `HYPOTHESIS_CREATION_DECISION_SNAPSHOT_V1_2` hashes without rewriting them. It additionally validates exact same-row shape, relationship family/source cardinality, source-to-manifest identity, duplicate/orphan constraints, and bearing/availability consistency.

## Integrity terminology

The upstream `decision_snapshot_hash` is an exact, storage-order-sensitive integrity/provenance binding. Unkeyed SHA-256 is **not trusted-origin authentication**. A caller capable of replacing nested content and recomputing every hash has not cryptographically proven that a trusted producer emitted that content.

V1.2 therefore separates:

1. `decision_snapshot_hash`: exact upstream storage integrity/provenance;
2. family `snapshot_hash`: canonical semantic family content;
3. `semantic_reasoning_hash`: canonical whole-reasoning semantic identity.

Non-semantic relationship/source/observation row ordering may change the upstream storage hash while leaving family semantic hashes and `semantic_reasoning_hash` unchanged. Genuine semantic changes alter semantic identity.

## Layered record/family hash contract

The public `reasoning_record_hash_payload()` contract includes every finalized evidence-record field except:

```text
record_hash
serialization_order
```

`serialization_order` is deterministic output bookkeeping and is not evidence semantics. `family_snapshot_id`, semantic state, typed value, availability, provenance cluster, independence status, inclusion decision, and exclusion reason are all hash-covered.

Identity layers are acyclic:

1. `family_snapshot_id` identifies decision + hypothesis + family;
2. the finalized record includes `family_snapshot_id`, then receives `record_hash`;
3. family `snapshot_hash` covers family semantic fields plus sorted final record hashes;
4. `semantic_reasoning_hash` covers the ordered family content hashes.

The storage-sensitive upstream hash is preserved in output but excluded from semantic-content hashes.

## Semantic states and orthogonal dimensions

Current CLOSED mappings remain:

```text
ALIGNS_WITH            -> ALIGNED
DIRECTIONALLY_OPPOSES  -> OPPOSITION
CONTRADICTS            -> CONTRADICTION
CONTEXTUALIZES         -> CONTEXTUAL
QUALIFIES              -> QUALIFYING
NEUTRAL                 -> NEUTRAL
UNKNOWN                 -> UNKNOWN
NOT_APPLICABLE          -> UNAVAILABLE
raw feature/observation -> FACTUAL or UNKNOWN
```

No current CLOSED source maps to predictive `SUPPORT`.

A single aggregate state is not treated as a complete family truth. V1.2 publishes orthogonal presence flags for support, opposition, contradiction, alignment, qualification, context, factual information, neutral information, unknown information, unavailable information, and mixed state. Multiple nonterminal aggregate states become `MIXED` rather than being reduced through a market-priority ordering. Certified contradiction retains logical precedence while all orthogonal flags remain visible.

CLOSED multi-scale conflict is preserved as an orthogonal fact. A family can simultaneously report directional `ALIGNED` or `OPPOSITION` and `conflict_present=True`. Conflict is not upgraded to opposition or contradiction.

The machine-readable manifest publishes aggregate and representative-selection policy.

## Provenance and deterministic derivation

V1.2 uses an open-world, three-state provenance contract:

```text
CERTIFIED_SHARED_PROVENANCE
CERTIFIED_DISTINCT_PROVENANCE
NOT_CERTIFIED
```

Different IDs, names, modules, families, or absence of a shared edge prove neither shared nor distinct provenance. Pairwise `provenance_relations` is authoritative. Every emitted legacy/adjacent status obeys the same open-world state: a record with `provenance_status=NOT_CERTIFIED` cannot emit shared-provenance wording. A production invariant rejects that contradiction.

Deterministic derivation is orthogonal:

```text
DETERMINISTIC_DERIVATIVE
NOT_DETERMINISTICALLY_DERIVED
NOT_CERTIFIED
```

Absence of a derivation path remains `NOT_CERTIFIED`. It is never upgraded to `NOT_DETERMINISTICALLY_DERIVED` without proof. `included_for_independent_calibration=False` remains mandatory for every current record.

### CLOSED 6.1A availability formulas

Lineage follows `decision/evidence_vector.py` exactly:

- `ev__evidence_feature_count` has `MANIFEST_UNIVERSE_DEPENDENCY` on the selected non-`COUNT_SUPPORT` specification universe;
- `ev__evidence_available_count` has `AVAILABILITY_VALUE_DEPENDENCY` only on selected non-`COUNT_SUPPORT` decision features;
- `ev__evidence_availability_fraction` has direct deterministic parents `ev__evidence_available_count` and `ev__evidence_feature_count`;
- `COUNT_SUPPORT` values are not availability-summary value parents.

### CLOSED 5.2 formulas

Lineage follows `multitimeframe/confluence_matrix.py` rather than manifest order. Hidden but certified formula inputs are explicit contract nodes, not fabricated visible values. Direct dependencies include:

```text
configured_scale_count + available_scale_count -> unavailable_scale_count
configured_scale_count + available_scale_count -> availability_fraction
configured_scale_count + directional_scale_count -> directional_fraction
up_structure_count + down_structure_count -> directional_scale_count
up_structure_count + down_structure_count -> directional_balance
up_structure_count + down_structure_count -> directional_conflict
directional_balance -> directional_consensus
```

Co-derived siblings with a common formula input receive shared/co-derived provenance proof but no directional derivation. Deterministic ancestor closure follows directed formula edges only. A common hidden cause never creates sibling-to-sibling derivation.

`independence_cluster_id` remains a conservative dependency grouping and is explicitly not a shared-provenance or statistical-independence assertion. `selected_provenance_representative` is bookkeeping only.

## Missingness and observation availability

Available feature values remain typed factual values. Missing present feature values remain `UNKNOWN`; absent families remain `UNAVAILABLE`. Missingness does not become zero, neutral, opposition, or support.

CLOSED 6.1B emits descriptive observation rows only for available observed facts. V1.2 therefore accepts `AVAILABLE` observations as factual and rejects nonavailable observation shells as impossible CLOSED combinations. `UNKNOWN` and `NOT_APPLICABLE` remain legally represented through feature/relationship records rather than falsely factual observations.

Exact nullable dtypes are preserved. `decision_deterministic_sequence`, positions, counts, and typed integer values use nullable `Int64`, including exact integers above `2**53` within Int64 range.

## ACTUAL and PROXY

ACTUAL and PROXY families, source modes, epistemic statuses, records, and hashes remain distinct. Unavailable ACTUAL information is not filled from PROXY information.

## State, ordering, and immutability

The reasoner has no learned cache or mutable analytical state. A→A, A→B→A, fresh-instance, future-history invariance, and all caller-owned DataFrame immutability are tested. Same-row ordering and serialization remain bookkeeping only and never become market chronology.

## Machine-readable policies

`reasoning_contract_manifest()` includes:

```text
FAMILY
BEARING_MAPPING
SEMANTIC_STATE
PROVENANCE_STATUS
DERIVATION_STATUS
SUPPORT_POLICY
MISSINGNESS_POLICY
AGGREGATE_POLICY
REPRESENTATIVE_POLICY
INDEPENDENCE_POLICY
LINEAGE_POLICY
HASH_POLICY
SCORING_POLICY
```

## Limitations

- V1.2 supports hypothesis-creation snapshots only.
- Provenance de-duplication does not prove statistical independence.
- No current source emits predictive `SUPPORT`.
- No family importance, calibration, score, probability, or qualification exists.
- No geometry/entity planning, tick-size contract, entry, stop, target, execution, or trade lifecycle exists.
- The upstream SHA-256 binding is integrity checking, not issuer authentication.
- `RESEARCH-DEBT-020` through `RESEARCH-DEBT-025` remain open.

## Status

```text
Module 6.2B-0 V1.2
CLOSED

Certified baseline:
654 collected
654 passed
```

## Closure certification record

History:

```text
V1    IMPLEMENTED — PENDING AUDIT
V1.1  PATCHED — PENDING AUDIT; independent audit: PATCH REQUIRED
V1.2  PATCHED — PENDING AUDIT; final independent audit: ACCEPTED FOR CLOSURE
V1.2  CLOSED
```

Closure certifies the causal hypothesis-creation reasoning contract, exact
same-row V1.2 boundary, evidence-family semantic preservation, open-world
provenance, faithful certified deterministic lineage, absence of false
statistical-independence admission, audited zero-look-ahead properties,
deterministic identities/hashes, ACTUAL/PROXY separation, missingness semantics,
and no predictive semantic upgrade within tested scope.

Closure does not certify trading edge, predictive usefulness, statistical
independence, profitable ICT concepts, confluence-score quality, learned
weights, probability calibration, qualification objective, entry/stop/target
quality, execution profitability, or future live performance.

Non-blocking naming debt remains: `tests/test_evidence_family_reasoning_v1_1.py`
retains its historical filename although its contents cover V1.2.

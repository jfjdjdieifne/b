# Module 6.2A-0 V1.2 — Research Information-Time / As-Of Visibility Firewall

Status: **CLOSED**

## Closure decision

```text
Module 6.2A-0 V1.2
ACCEPTED FOR CLOSURE
CLOSED
```

Closure history:

```text
V1 -> V1.1 -> V1.2 -> CLOSED
```

Certified baseline:

```text
Dedicated research firewall tests: 77 passed
Full suite: 469 collected / 469 passed
```

Closure certifies within tested scope: explicit immutable `InformationKey`,
fail-closed causal ordering, as-of visibility projection, future semantic
payload exclusion, full-vs-truncated equivalence, future mutation/append
invariance, atomic same-row analytical visibility, parent-child
relationship-source projection, certified 6.1A/6.1B static manifest identity,
explicit positional/time-indexed adapters, timezone/DST/irregular handling,
live-to-research import firewall, stateless deterministic projection, and
exclusion of final `active_hypotheses` from historical as-of projection.

Closure does not certify outcome observation, outcome maturity, right
censoring, `final_outcome_known_at`, reference-price outcome measurement,
excursions, labels, training eligibility, model fitting, predictive edge,
profitability, scorer, weights, or signals. None of those behaviors has been
implemented.

`COMPLETED_ROW_AVAILABLE` sequencing is logical causal dependency
serialization, not a measured exchange/feed/runtime micro-latency claim.
Module 6.1B same-row `serialization_order` remains bookkeeping only and does
not create intrabar information ordering.

## V1.2 patch history

V1.2 removes `functools.total_ordering` and implements `__eq__`, `__lt__`,
`__le__`, `__gt__`, and `__ge__` explicitly. Different causal coordinates use
only position/phase/sequence. Equal-coordinate keys with equal normalized UTC
identity compare normally; conflicting timestamps or timestamp-versus-missing
remain unequal and every ordering operator raises `InformationKeyError`.
Equal-key hash identity uses the same normalized identity tuple.

Static feature-manifest normalization now accepts only scalar metadata and
cleanly rejects list, tuple, dict, set, NumPy array, pandas Series, and pandas
Index payloads. `None`, `pd.NA`, `np.nan`, Python scalars, NumPy scalars,
strings, and booleans have deterministic scalar handling. All incidental
manifest exceptions are normalized to `ManifestIdentityError`, then translated
by visibility projection to `VisibilitySchemaError`.

Static narrative-manifest identity now uses explicit deterministic comparison.
Schema, column order/type, row/index order/type, and dtypes remain exact.
`None`, `pd.NA`, and `np.nan` are intentionally canonicalized to one semantic
missing token only after dtype validation; all nonmissing values retain exact
type and value comparison. Identity no longer depends on pandas' implicit
missing-sentinel comparison behavior.

The explicit atomic same-row 5/100/200 serialization test and all V1/V1.1
visibility, sentinel, truncation, mutation, append, and import-firewall
contracts remain unchanged.

## V1.1 patch history

V1.1 preserves the V1 visibility-only scope and resolves two contract-identity
precision findings from the read-only audit.

Static `feature_manifest` validation now compares exact Module 6.1A V1.3
catalog metadata, exact columns/order, certified row order, enabled-group
completeness, and ACTUAL/PROXY mutual exclusion. Optional groups remain
optional; structure-only, structure+MTF, ACTUAL, PROXY, liquidity-only, and
empty certified selections are tested. Forged metadata, incomplete groups,
extra features, and reordered/duplicate identities are rejected.

Static `narrative_manifest` validation now uses
`CausalMarketNarrativeEngine.narrative_manifest()` as the closed V1.2
authority and requires exact DataFrame columns, row order, values, indexes, and
stable dtypes. Modified hypothesis, bearing, lifecycle, same-row, extra-row,
and removed-row contracts are rejected. Validation executes no upstream
analysis and depends on no dataset row or research as-of value.

`InformationKey` V1.1 includes normalized `event_time_utc` in equality and hash
identity. Causal ordering remains position/phase/sequence. Two direct keys with
one causal coordinate but conflicting timestamp provenance are unequal and
explicitly incomparable rather than silently ordered; explicit adapters reject
timestamp/row mismatch. All cross-timeline comparison operators reject.

An explicit atomic same-row adversarial test assigns observation, relationship,
and hypothesis serialization orders 5, 100, and 200. All are invisible at
analytical sequence 0 and visible together at sequence 1, proving ledger
serialization does not create partial same-row information visibility.

The original V1 phase, adapter, projection, parent-child, sentinel, truncation,
future mutation/append, state-isolation, and import-firewall behavior remains
unchanged.

## Scope

This module implements only immutable information-time contracts and projection
of frozen causal tables through an explicit research as-of key. It does not
observe hypothesis outcomes, create labels, calculate excursions, build a
research training dataset, fit a model, or score a decision.

## Phase-contract audit

The closed Module 5.1 contract requires timezone-aware, nonmissing, unique,
monotonic `DatetimeIndex` input and supports `CLOSE_TIME` semantics only. It
uses completed `(start, end]` intervals and exposes exact-end completions on the
same completed row.

Closed Module 6.1A validates a unique monotonic index and performs row-local
copying of already certified causal evidence. Closed Module 6.1B preserves that
index and declares same-row facts to share one atomic information time;
serialization order is bookkeeping rather than market/intrabar chronology.

The minimum defensible V1 phase vocabulary is therefore:

```text
BAR_PRE_CLOSE                     rank 0
COMPLETED_ROW_AVAILABLE           rank 1
RESEARCH_SNAPSHOT_AVAILABLE       rank 2
```

Within `COMPLETED_ROW_AVAILABLE`, deterministic sequence `0` represents the
completed market-row dependency and sequence `1` represents the atomic causal
analytical batch. This is a logical dependency serialization needed for a total
order. It does not claim measured sub-row or wall-clock latency. All 6.1B
same-row analytical records receive the same visibility sequence; their ledger
serialization fields preserve output order but do not create partial intrabar
visibility.

## InformationKey

`InformationKey` is frozen and contains:

```text
information_key_version
timeline_id
bar_position
event_time_utc
information_phase
deterministic_sequence
```

Ordering is `(bar_position, phase rank, deterministic_sequence)` within one
`timeline_id`. Explicit comparisons across timelines raise a contract error.

## Explicit timeline adapters

### Positional adapter

- Uses row ordinal as `bar_position`.
- Requires a non-DatetimeIndex with unique monotonic labels.
- Sets `event_time_utc` to missing.
- Does not infer timestamps, timezone, frequency, duration, or close time.

### Time-indexed adapter

- Requires a timezone-aware `pandas.DatetimeIndex`.
- Rejects NaT, duplicate timestamps, and nonmonotonic order, consistent with
  closed Module 5.1 and decision index contracts.
- Converts event timestamps to UTC while preserving row position.
- Accepts irregular spacing.
- DST tests use distinct UTC instants represented in `Europe/Vilnius`.

Adapter mode is always selected explicitly by the caller.

## Frozen and visible bundles

`FrozenDecisionSnapshotBundle` contains frozen evidence, manifests, narrative
surface, observation/hypothesis/relationship ledgers, relationship sources, and
a row-aligned market frame. It intentionally has no outcome fields.

`VisibleAsOfBundle` contains independent projected copies of those tables plus
the explicit as-of key and contract versions. It excludes
`active_hypotheses`, because that closed 6.1B output is final replay state and
is not a historical as-of table.

## Projection rules

```text
evidence_df             row completed analytical batch <= as-of
narrative_surface       row completed analytical batch <= as-of
observation_ledger      observed_position atomic batch <= as-of
hypothesis_ledger       event_position atomic batch <= as-of
relationship_ledger     observed_position atomic batch <= as-of
relationship_sources    visible parent relationship_id only
market_frame            completed market-row dependency <= as-of
feature_manifest        static copy after identity validation
narrative_manifest      static copy after identity validation
active_hypotheses       excluded
```

Equality at the complete key is visible. A later phase or later deterministic
sequence at the same bar remains invisible.

## Parent-child and schema integrity

The full input relationship ledger must have unique nonnegative integer
relationship IDs. Every relationship source must reference an existing parent.
Projection filters relationships first and then filters source rows by the
visible parent-ID set. Future children and orphans cannot survive.

Observation, hypothesis, and relationship ledgers require nonmissing integer
position, batch, serialization, and identity columns. Positions must be inside
the row-aligned market/evidence identity, and same-row batch IDs must match
positions under the certified 6.1B contract. Duplicate columns, duplicate
ledger identities, invalid dtypes, negative metadata, and row-index mismatch
are rejected.

## Payload-before-projection security property

Visibility masks read only row indexes/positions, same-row and serialization
metadata needed for validation, and relationship IDs needed for parent-child
integrity. Semantic payload columns are sliced only after masks are complete.
The adversarial fixture places object sentinels in future evidence, narrative,
market, observation, hypothesis, relationship, and relationship-source payload
cells. Their conversion/comparison/truth methods raise if invoked. Projection
at an earlier as-of completes with zero sentinel accesses.

Limitation: pandas object-column slicing does not provide operating-system
memory isolation, and `deep=True` does not recursively clone arbitrary Python
objects. The test proves that projector logic does not semantically inspect the
future payload before filtering. Output DataFrames are independent containers;
mutating their cells does not mutate input DataFrames.

## Causal/state verification

Dedicated exact tests cover:

- full bundle versus physically truncated bundle equality for every table;
- future semantic mutation invariance;
- future append invariance, including later ledger/source records;
- A→A, A→B→A, and fresh-instance determinism;
- parent-child filtering and orphan rejection;
- exact phase/sequence boundaries;
- positional, UTC/timezone, DST, and irregular-time adapters;
- schema, position, dtype, identity, and timeline adversaries;
- static import firewall;
- config immutability and input/output independence;
- absence of outcome/scorer fields from public contracts and manifests.

## Import firewall

An AST-based test scans production files in the closed Layer 0–5 packages and
`trading_system.decision`. Any import whose module begins with
`trading_system.research` fails. Research-to-decision imports remain allowed by
architecture, although V1 does not require one.

## V1 validation baseline

```text
Information-time tests: 12 passed
Visibility tests:       22 passed
Dedicated total:        34 passed
Full collection:       426 collected
Full suite:            426 passed
```

```text
........................................................................ [ 16%]
........................................................................ [ 33%]
........................................................................ [ 50%]
........................................................................ [ 67%]
........................................................................ [ 84%]
..................................................................       [100%]
```

## V1.1 validation

```text
Information-time tests: 13 passed
Visibility tests:       43 passed
Dedicated total:        56 passed
Causal/import selection: 5 passed
Full collection:       448 collected
Full suite:            448 passed
```

```text
........................................................................ [ 16%]
........................................................................ [ 32%]
........................................................................ [ 48%]
........................................................................ [ 64%]
........................................................................ [ 80%]
........................................................................ [ 96%]
................                                                         [100%]
```

V1.1 adds exact timestamp identity/hash, all-operator cross-timeline rejection,
certified optional-group feature-manifest identity, exact narrative-manifest
identity, forged static contract adversaries, manifest future-independence, and
explicit 5/100/200 atomic same-row serialization tests.

## V1.2 validation

```text
Information-time tests: 16 passed
Manifest-identity tests: 17 passed
Visibility tests:       44 passed
Dedicated total:        77 passed
Causal/import selection: 5 passed
Full collection:       469 collected
Full suite:            469 passed
```

```text
........................................................................ [ 15%]
........................................................................ [ 30%]
........................................................................ [ 46%]
........................................................................ [ 61%]
........................................................................ [ 76%]
........................................................................ [ 92%]
.....................................                                    [100%]
```

V1.2 adds direct regression coverage for every explicit comparison operator,
timestamp-versus-missing conflict, normalized UTC equality/hash, ordinary
positional ordering, non-scalar feature and narrative metadata, canonical
missing sentinels, stable narrative dtypes, and normalized manifest exceptions.

## Limitations and deferred scope

Not implemented:

```text
6.2A-1 factual outcome observer
6.2A-2 temporal eligibility builder
outcomes or labels
terminal interpretation
censoring/maturity semantics
price paths or excursions
overlap graph
model, estimator, scorer, probability, signal, entry, or exit
```

The Design V3 proposals `RESEARCH-DEBT-023` through `025` are not created by
this module. Existing clock/partial-bar research debts remain the relevant
record of broader timing questions; this V1 firewall resolves only explicit
projection mechanics under current closed contracts.

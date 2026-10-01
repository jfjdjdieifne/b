# Module 4.1 V1.1 — Causal Order-Block Candidate & Lifecycle Engine

Status: **CLOSED V1.1**

Rebuilt from scratch. These are operational `BULLISH_OB_CANDIDATE` /
`BEARISH_OB_CANDIDATE` zones, not proof of institutional orders.

## V1.1 direct upstream validation

Production now validates true non-missing boolean swing flags before use, rejects simultaneous flags, validates event-row origin/confirmation/price metadata and requires decision metadata missing on non-event rows. No unvalidated flag is cast with `bool()`.

The consumed 2.1C surface is required explicitly: side-specific first close events and `structure_state_before` must match the operational interpretation table. Directional labels without the corresponding close fact, incompatible pre-state, or both-side close facts under a directional label are rejected. `AMBIGUOUS_DOUBLE_BREAK`, `UNCLASSIFIED_BREAK`, and `NONE` require their exact factual patterns. 2.1C is not rerun.

## Structural search boundary

For an UP break at row `i`, V1 uses the most recent confirmed LOW whose
confirmation occurred before `i`; its historical origin position is the search
boundary. DOWN uses the most recent prior confirmed HIGH. Search is `[boundary,
i)`, so the boundary origin candle itself is deliberately eligible. A swing confirmed on row `i` is processed only after creation and cannot
be the same-row boundary. Missing boundary or missing opposite candle means no
candidate.

## Origin selector

UP selects the most recent candle with `close<open`; DOWN selects the most
recent `close>open`. Doji is excluded. This deterministic ICT heuristic is not
optimized with future outcomes. Reused origins create distinct IDs and expose
`origin_prior_use_count`.

## Primary schema

Creation metadata includes zone ID/direction/origin/creation, immutable full
and body geometry, source break label, prior-use count, displacement
fraction/percentile/history count, search boundary, and opposite-candle count.
Per-bar outputs include first touch/far-side wick/far-side close/reclaim counts
by direction and known historical candidate counts.

## Event table

```text
ZONE_CREATED
FIRST_TOUCH
FIRST_FAR_SIDE_WICK_BREACH
FIRST_FAR_SIDE_CLOSE_BREACH
FIRST_CLOSE_RECLAIM_OF_FAR_SIDE
```

Each row preserves event/zone identity, origin/creation/boundary, source break,
zone geometry, current OHLC, frozen displacement evidence, prior-use count, and
zone age. Ordering is mechanical and does not imply intrabar sequence.

## Lifecycle

Monitoring starts strictly after creation. Full wick zone drives factual
lifecycle; body geometry is immutable metadata only. Exact overlap is touch;
far-side breach is strict. Reclaim requires a subsequent bar. Zones are never
pruned or automatically labeled active/invalid/breaker.

## Real integration

A deterministic real chain `2.1A -> 2.1B -> 2.1C -> 4.1` produced a directional
structural event and an OB candidate using the real schemas. End-to-end
truncation and independent normalized-event-table truncation/state isolation
passed.

## Results

```text
Module tests: 12 passed
Full suite: 249 passed
```

Full pytest:

```text
........................................................................ [ 28%]
........................................................................ [ 57%]
........................................................................ [ 86%]
.................................                                        [100%]
```

## Benchmark

Three runs after warm-up, structural event every 50 rows:

```text
N=500,  zones=9:  median 22.748 ms
N=1000, zones=19: median 40.947 ms
N=2000, zones=39: median 91.538 ms
```

Naive dynamic backward search plus all-zone scans can reach quadratic worst
case. No fixed search cap, max-zone cap, age pruning, or semantic shortcut was
introduced.

## Open issues

- Breaker interpretation is deferred (`RESEARCH-DEBT-008`).
- Origin heuristic optimality is unproven (`RESEARCH-DEBT-009`).
- Structural labels inherited from 2.1C are operational definitions.
- No optional confluence mega-integration or quality score exists.
- Batch positions do not support cross-chunk continuation.

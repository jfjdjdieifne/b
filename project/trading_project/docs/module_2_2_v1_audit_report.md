# Module 2.2 V1.1 — Causal Liquidity Map / Level Lifecycle Engine

Status: **CLOSED V1.1**

Rebuilt from scratch. The rejected historical draft was not imported or reconstructed. No CLOSED module was modified.

## Honest scope

Levels are immutable confirmed-swing-derived price references:

- `HIGH_SIDE`
- `LOW_SIDE`

They are liquidity-relevant candidates, not proof that resting orders exist.

Unlike Module 2.1C latest-reference monitoring, 2.2 retains every confirmed source level throughout the analyzed DataFrame.

## Primary bar surface schema

```text
liquidity_level_created
created_level_id
created_level_side
created_level_price
created_level_origin_position
created_level_confirmation_position
created_level_source_class
nearest_prior_same_side_level_id
nearest_same_side_distance_fraction
nearest_distance_percentile
nearest_distance_reference_history_count
high_side_first_touch_count / low_side_first_touch_count
high_side_first_wick_breach_count / low_side_first_wick_breach_count
high_side_first_wick_only_count / low_side_first_wick_only_count
high_side_first_close_breach_count / low_side_first_close_breach_count
high_side_first_reclaim_count / low_side_first_reclaim_count
known_high_side_level_count / known_low_side_level_count
```

Counts are events occurring on the current bar, not cumulative interaction counts. Known-level counts are end-of-bar totals and are not called active levels.

## Normalized event-table schema

```text
event_position
level_id
side
event_type
source_origin_position
source_confirmation_position
source_class
immutable_level_price
event_price
event_close
overshoot_fraction
nearest_prior_same_side_level_id
nearest_same_side_distance_fraction
nearest_distance_percentile
nearest_distance_reference_history_count
level_age_bars
```

Event types:

```text
LEVEL_CREATED
FIRST_TOUCH
FIRST_WICK_BREACH
FIRST_WICK_ONLY_EXCURSION
FIRST_CLOSE_BREACH
FIRST_RECLAIM_AFTER_CLOSE_BREACH
```

Serialization order is event position, level ID, then fixed event-type order. It is mechanical and does not imply intrabar sequence.

## V1.1 lifecycle correction

`FIRST_WICK_ONLY_EXCURSION` can be first-established only while the level has never had `FIRST_CLOSE_BREACH`. After a close breach, a later wick-through with close back across is represented by `FIRST_RECLAIM_AFTER_CLOSE_BREACH`; it cannot create a late wick-only event.

Both lifecycle orders are tested across event-table truncation boundaries:

```text
close breach -> later reclaim -> no wick-only event
wick-only -> later close breach -> later reclaim
```

## Direct Module 2.1B linkage validation

Without recomputing 2.1B, production validates current metadata against 2.1A, first/comparable-event semantics, exact previous same-type price/origin linkage, exact positive-price log-change consistency, and missing event metadata on non-event rows. It intentionally does not recalculate HH/LH/EH/HL/LL classification.

## Exact lifecycle semantics

- Level creation occurs only on the confirmation row.
- Monitoring starts on the subsequent row.
- Old eligible levels are evaluated before a current new level is created.
- Exact touch uses `>=`/`<=`; strict wick and close breaches use `>`/`<`.
- Touch, wick breach, and wick-only/close breach may all be separate same-bar facts.
- Each first-event type emits at most once per source level.
- Reclaim requires a subsequent row after first close breach.
- Levels remain retained after touch, wick breach, close breach, reclaim, and newer same-side confirmations.
- No age/count/distance pruning exists.

## Proximity-history semantics

For each newly confirmed source level:

1. inspect prior same-side immutable source prices only;
2. select nearest finite normalized distance; ties choose lower level ID;
3. rank against prior shared HIGH/LOW nearest-distance observations;
4. push only after reading.

There is at most one distance observation per new level. First same-side levels have no observation. Exact zero/zero equality has distance zero. Low percentile means unusually close; V1 creates no binary cluster and has no hidden quantile.

`nearest_distance_reference_history_count` is the number of observations in the shared HIGH/LOW reference distribution available **before** evaluating the current new level. A level can have `nearest_same_side_distance_fraction=NaN` while this count is positive when only the opposite side has previously contributed valid reference distances. This is intentional.

## Dedicated event-table audit

For every tested split `k`:

```text
full_bar[:k] == truncated_bar
full_events[event_position < k] == truncated_events
```

Equality includes row count, ordering, dtypes, and values. Event-table same-instance A→B isolation also passed. Module 0.1 audits only tuple element zero; event-table equivalence is separately tested.

## Real integration

Real chain:

```text
2.1A -> 2.1B -> 2.2
```

Created levels occurred at confirmation rows `[2, 4, 6, 8]` with sides:

```text
HIGH_SIDE, LOW_SIDE, HIGH_SIDE, LOW_SIDE
```

Compatibility with 2.1C was cross-checked: the latest HIGH reference first-close fact on row 5 matched a 2.2 `FIRST_CLOSE_BREACH` event for the same immutable level price. End-to-end bar and event-table truncation passed at all boundaries 1..8.

## Performance benchmark

Correctness V1 scans all known levels each bar: `O(N*L)`, worst-case `O(N²)`.

Deterministic fixture, 5 timed runs after warm-up:

```text
N=1000, levels=49:   median 60.101 ms
N=2000, levels=199:  median 332.186 ms
N=4000, levels=399:  median 1205.556 ms
```

No semantic pruning or maximum-level cap was introduced.

## Results

Module-specific tests:

```text
....................                                                     [100%]
```

20 tests passed.

Full clean-project suite:

```text
........................................................................ [ 36%]
........................................................................ [ 72%]
........................................................                 [100%]
```

200 tests passed.

## Research/performance debt

- `RESEARCH-DEBT-003` records correlated multi-level interaction observations. V1 deliberately does not build global overshoot percentiles.
- Exact all-level scans are intentionally unpruned and have measured quadratic worst-case scaling.

## Unresolved issues

1. No binary near-equal clustering is implemented; only continuous nearest-neighbor evidence exists.
2. HIGH/LOW nearest-distance observations share one dimensionless distribution.
3. Bar age is factual but frequency-dependent and appears only per event row.
4. The event table is separately tested but remains outside Module 0.1 V3.1 automatic audit scope.
5. Batch positions do not support cross-chunk continuation.
6. Interaction overshoots remain raw normalized facts without empirical multi-level weighting.

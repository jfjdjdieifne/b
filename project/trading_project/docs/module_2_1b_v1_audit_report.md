# Module 2.1B V1 — Confirmed Swing Sequence Structure

Status: **CLOSED V1**

## Architectural boundary

- Module 2.1A establishes where/when a swing becomes causally confirmed.
- Module 2.1B compares each newly confirmed swing with the previous confirmed swing of the same type.
- Break interpretation, persistent trend state, liquidity, zones, and trading decisions are outside this module.

Candidate fields are ignored completely.

## Event timing

Classification is emitted only on the row where the current swing confirmation is visible. The origin row is never backfilled. Event arrival/DataFrame row order controls state; origin-position ordering does not.

Rows without new events emit:

```text
structure_event_type = NONE
swing_sequence_class = NONE
comparison_available = False
all event metadata = missing
```

No label is forward-filled.

## Exact same-type semantics

```text
HIGH versus previous HIGH:
  greater -> HH
  lower   -> LH
  equal   -> EH

LOW versus previous LOW:
  greater -> HL
  lower   -> LL
  equal   -> EL
```

The first event of each type is `UNCLASSIFIED` with no comparison metadata. No epsilon, tick, percentage, volatility, or empirical tolerance is used.

## Optional descriptive magnitude

For two positive same-type prices:

```python
same_type_log_price_change = log(current) - log(previous)
```

If either price is zero/negative, output is NaN. Exact equal positive prices produce zero.

## Validation

On every confirmed event, V1 validates:

- exactly one of HIGH/LOW is true;
- finite swing price;
- integer origin and confirmation positions;
- positions inside the analyzed positional domain;
- confirmation position equals current row;
- origin position is not after confirmation.

Input columns/index must be unique; index must already be monotonic. Existing output-column collisions are rejected. Input is not mutated and index metadata is preserved.

## Real 2.1A -> 2.1B integration result

Using the real CLOSED `CausalAdaptiveSwingDetector` with explicit policy:

```text
row  event  origin  confirmation  class
2    HIGH   1       2             UNCLASSIFIED
4    LOW    3       4             UNCLASSIFIED
6    HIGH   5       6             HH
8    LOW    7       8             HL
```

Origin rows 1, 3, 5, and 7 remain `NONE`. End-to-end truncation invariance was tested at every boundary from 1 through 8.

## Results

Self-verification:

```text
MODULE 2.1B V1 SELF-VERIFICATION PASSED
Confirmed swing sequence classes appear only on confirmation rows.
```

Module-specific suite:

```text
...............................                                          [100%]
```

31 tests passed.

Full clean-project suite:

```text
........................................................................ [ 46%]
........................................................................ [ 92%]
...........                                                              [100%]
```

155 tests passed.

## V1 positional contract

`origin_position` and `confirmation_position` are integer positions within the **same DataFrame** passed to `analyze()`.

V1 does **not** support chunk/stream continuation where a confirmed swing inside the current chunk references an `origin_position` before the chunk boundary.

This is a batch-engine contract, not a causality flaw.

## Unresolved design issues

1. Exact floating equality is intentional in V1; approximate equality remains a separate downstream concept.
2. Negative/zero prices can still be ordered factually, but log magnitude is undefined and remains NaN.
3. V1 validates event metadata consistency but does not independently recompute the swing from raw wick data; that belongs to Module 2.1A.
4. Consecutive same-type events are supported and compared by arrival order without assuming alternation.
5. No persistent structure/trend state is emitted; event labels remain event-local.

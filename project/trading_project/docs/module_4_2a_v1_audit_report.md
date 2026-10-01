# Module 4.2A V1.1 — Causal FVG Candidate & Lifecycle Engine

Status: **CLOSED V1.1**

Strict completed three-bar geometry creates immutable independent
`BULLISH_FVG_CANDIDATE` / `BEARISH_FVG_CANDIDATE` zones only at row `i`.
Origin=`i-2`, middle=`i-1`, creation=`i`; monitoring begins at `i+1`.

## Creation

Bullish: `low[i] > high[i-2]`, zone `[high[i-2], low[i]]`. Bearish:
`high[i] < low[i-2]`, zone `[high[i], low[i-2]]`. Equality creates nothing.
Stacked/overlapping candidates keep unique IDs and immutable geometry.

Width fraction uses width divided by max absolute boundary. One finite
observation per created FVG is ranked read-before-push in a shared directional
history. Middle body/signed-body fractions are descriptive only.

## V1.1 reclaim semantics

`FIRST_CLOSE_RECLAIM_OF_FAR_SIDE` is a subsequent-bar close-state fact only: bullish close `>= zone_low`, bearish close `<= zone_high`. It requires no touch, traversal, retest, near-side reclaim, or IFVG interpretation. Gap-over reclaim is explicitly tested.

Derived zone width/midpoint/fractions and positive-range middle-body fractions are required finite; unrepresentable float64 geometry raises `FVGDataError` without clipping.

## Lifecycle/event table

Events: `FVG_CREATED`, `FIRST_TOUCH`, `FIRST_FULL_RANGE_COVERAGE`,
`FIRST_FAR_SIDE_WICK_BREACH`, `FIRST_FAR_SIDE_CLOSE_BREACH`, and subsequent
`FIRST_CLOSE_RECLAIM_OF_FAR_SIDE`. Multiple same-bar facts are
preserved; serialization does not imply intrabar order. Coverage is bar-range
intersection width divided by immutable gap width, not chronological fill.

Primary bar aggregates and a normalized event table receive independent exact
truncation/state tests. No candidate is deleted or automatically inverted.

## Results

```text
Module tests: 11 passed
Full suite: 260 passed
```

```text
........................................................................ [ 27%]
........................................................................ [ 55%]
........................................................................ [ 83%]
............................................                             [100%]
```

## Benchmark

```text
N=500:  120.637 ms
N=1000: 395.053 ms
N=2000: 1425.893 ms
```

All-gap scanning is O(N*G), worst-case quadratic; no pruning was introduced.

## Debt / limitations

- `RESEARCH-DEBT-010`: IFVG role reversal is deferred.
- `RESEARCH-DEBT-011`: stacked lifecycle dependence is unmodeled.
- Midpoint is geometry only, not a signal.
- No structural/OB/confluence dependency, quality score, fill-status enum, or
  path inference exists.

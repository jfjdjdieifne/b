# Module 2.1C V1 → V1.1 Engineering Benchmark

This benchmark is engineering information only. It does not change statistical or structural semantics.

## Deterministic fixture

```text
rows: 20,000
confirmed swing events: 0
OHLC: deterministic linearly increasing finite values
runs per version: 7 after one warm-up
measurement: CausalStructuralBreakEngine.analyze() wall-clock milliseconds
```

The consumed Module 2.1A/2.1B surface was created once before timing.

## V1 — mandatory full 2.1B recomputation

```text
307.524, 312.030, 312.629, 307.234, 311.019, 311.982, 308.784 ms
median: 311.019 ms
```

## V1.1 — direct vectorized contract validation

```text
307.989, 314.574, 314.702, 314.605, 305.170, 304.213, 328.908 ms
median: 314.574 ms
```

## Interpretation

```text
median difference: +3.555 ms (+1.14%)
```

On this fixture and runtime, final V1.1 is effectively performance-neutral within ordinary wall-clock noise. Its architectural improvement is removal of mandatory duplicate Module 2.1B execution from the production hot path while retaining direct schema/metadata validation.

This is not a general performance claim. Event density, DataFrame size, hardware, Python/pandas versions, and process noise can change results. No semantic shortcut or estimator change was introduced for speed.

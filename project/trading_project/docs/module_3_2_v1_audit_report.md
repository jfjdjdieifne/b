# Module 3.2 V1.1 — Causal Aggression / Price-Response / Absorption Evidence

Status: **CLOSED V1.1**

Rebuilt from scratch. No CLOSED module was modified.

## V1.1 upstream history-contract validation

For ACTUAL `delta_magnitude_history_count` and PROXY `pressure_magnitude_history_count`, production validates numeric integer semantics, nonnegative finite non-boolean values, and exact causal running counts implied by prior finite admissible magnitudes.

Missingness rules are structural, without percentile recomputation:

- undefined magnitude requires NaN percentile;
- zero prior count requires NaN percentile;
- finite magnitude with positive prior count requires finite percentile in `[0,1]`.

Fractional, negative, NaN, infinite, boolean, or causally inconsistent counts are rejected. Real Module 3.1 surfaces remain accepted.

Positive-close log returns remain `log(current)-log(previous)` and are defensively required finite; no ratio division, clipping, or epsilon was introduced.

## Absorption/opposition decomposition

Absorption evidence alone cannot distinguish weak/stalled aligned response from strong active movement against flow, because both can have aligned magnitude zero. V1.1 therefore requires downstream consumers to retain the separately exposed opposed magnitude and percentile. The formula is unchanged; `RESEARCH-DEBT-007` records the open decomposition question.

## ACTUAL schema

```text
absorption_mode
signed_return
absolute_return
return_magnitude_percentile
return_magnitude_history_count
aggression_response_alignment
aligned_response_magnitude
aligned_response_percentile
aligned_response_history_count
opposed_response_magnitude
opposed_response_percentile
opposed_response_history_count
aggression_extremeness
response_weakness
actual_absorption_evidence
absorbed_aggression_side
```

## PROXY schema

```text
absorption_mode
signed_return
absolute_return
return_magnitude_percentile
return_magnitude_history_count
pressure_response_alignment
pressure_aligned_response_magnitude
pressure_aligned_response_percentile
pressure_aligned_response_history_count
pressure_opposed_response_magnitude
pressure_opposed_response_percentile
pressure_opposed_response_history_count
proxy_pressure_extremeness
proxy_response_weakness
proxy_absorption_evidence
pressure_side
```

Proxy schema never exposes actual-absorption naming.

## Mathematical semantics

Positive consecutive closes produce `log(close_i)-log(close_(i-1))`; first row or non-positive prices yield NaN without epsilon.

For defined nonzero flow direction:

```text
alignment = sign(flow) * signed_return
aligned magnitude = max(alignment, 0)
opposed magnitude = max(-alignment, 0)
```

Zero/NaN flow direction yields NaN directional responses and admits nothing to aligned/opposed history. Valid zeros under nonzero direction are admitted.

Absorption evidence is a transparent fuzzy AND in rank space:

```text
extremeness * (1 - aligned_response_percentile)
```

Components remain separately exposed. Missing either component yields NaN.

## Same-bar limitation

Flow and price response are aggregates of the same completed bar. Identical aggregates arising from different hidden intrabar sequences necessarily produce identical output. V1 evidence does not prove aggression preceded response/absorption.

## Upstream validation

ACTUAL directly validates mode, delta ratio bounds/missing semantics, magnitude equality, percentile bounds, and total-volume semantics without rerunning Module 3.1.

PROXY directly validates mode, OHLCV geometry, close-location formula, zero-volume pressure gate, magnitude equality, and percentile bounds without rerunning Module 3.1.

## Audits/results

Module-specific:

```text
..................                                                       [100%]
```

18 tests passed.

Full suite:

```text
........................................................................ [ 30%]
........................................................................ [ 60%]
........................................................................ [ 91%]
.....................                                                    [100%]
```

237 tests passed.

Both modes passed Module 0.1 truncation/state-isolation, future mutation/append, scaling, real Module 3.1 integration, input immutability, and empty/small behavior.

## Benchmark

Median milliseconds, three runs after warm-up, Module 3.1 surface prepared before timing:

```text
N       ACTUAL     PROXY
500      28.037     15.287
1000     91.419     39.738
2000    330.979    125.223
```

Expanding exact percentiles inherit `PERFORMANCE-DEBT-001`; no history cap was introduced.

## Research debt

- `RESEARCH-DEBT-004`: unconditional global context may mix regimes.
- `RESEARCH-DEBT-005`: legitimate VPIN requires a volume-bucket/data-clock contract; VPIN is not implemented.
- `RESEARCH-DEBT-006`: imbalance evidence is not conditioned on absolute participation.
- `RESEARCH-DEBT-007`: absorption rank product does not by itself decompose stalling from active opposition.
- Volatility-conditioned absorption remains deferred to later causal conditional modeling.

## Unresolved issues

1. Bar aggregates cannot identify intrabar sequence.
2. ACTUAL quality depends on upstream aggressor classification and units.
3. PROXY is pressure/response inefficiency, not actual absorption.
4. Aligned-response context is unconditional across aggression magnitudes and regimes.
5. No structural divergence, VPIN, CVD, participation threshold, or session reset exists.
6. No cross-chunk continuation exists in V1.1.

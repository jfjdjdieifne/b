# Module 1.1 V1.1 — Dynamic Volatility Engine

Status: **CLOSED V1.1**

The missing historical implementation was not reconstructed. The old `causal_kernels.py` was not imported or used as a source of truth.

## Output surface

- `true_range`
- `normalized_true_range`
- `true_range_percentile`
- `true_range_history_count`
- `normalized_tr_change`
- `expansion_percentile`
- `expansion_history_count`

No categorical regime, ATR period, adaptive period, memory recommendation, fixed lookback, bootstrap percentile, or readiness threshold is emitted.

## Design decisions

1. **True Range timing** uses current high/low and previous close. Bar zero uses high-low.
2. **Normalization** is `TR_i / abs(close_(i-1))`; bar zero and a zero previous close produce NaN.
3. **Dynamics** use the signed log-ratio of immediately consecutive positive normalized true ranges. It is evaluated as `log(current)-log(previous)` for numerical stability. Zero/undefined inputs produce NaN; no epsilon is added.
4. **True-range context** ranks current normalized TR against prior finite normalized TR observations via Module 0.2 `observe()`.
5. **Expansion context** ranks the signed current log-change against prior finite signed changes. High percentile means relatively stronger expansion; low percentile means relatively stronger contraction. It is not an absolute anomaly-magnitude score.
6. **Evidence** is exposed as raw prior-history counts. There is no `is_ready` threshold.
7. **State** is local to each `analyze()` call, making batch behavior deterministic and idempotent.
8. **Module 0.3 is intentionally unused** because V1 has no causally justified external memory horizon.

## Test results

Self-verification:

```text
MODULE 1.1 V1.1 SELF-VERIFICATION PASSED
True-range and expansion contexts use prior observations only.
```

Module-specific tests:

```text
....................                                                     [100%]
```

20 tests passed.

Full suite:

```text
........................................................................ [ 98%]
.                                                                        [100%]
```

73 tests passed.

## Covered tests

- Hand-calculated gap-up/gap-down True Range.
- First-bar semantics and previous-close normalization.
- Read-before-push and Module 0.2 tie mid-rank behavior.
- Signed symmetric log-change.
- Finite → NaN → finite no-bridge contract.
- Explicit undefined zero/missing-reference behavior without epsilon.
- Future OHLC mutation and extreme-future append invariance.
- Module 0.1 truncation and state-isolation audits.
- Positive scale invariance using an exact binary scale factor.
- Empty/single-row behavior.
- Original-input immutability.
- OHLC dtype/finite/range validation.
- Duplicate columns/index, unordered index, output collision.
- Custom source-column names.
- Secondary constitutional source-token guard.

## Unresolved issues for audit

1. Exact expanding percentile scalability is registered formally as `PERFORMANCE-DEBT-001`; no arbitrary history cap or estimator change was introduced.
2. `expansion_percentile` ranks signed changes, not absolute change magnitude. This preserves expansion/contraction direction but should be confirmed as the intended semantics.
3. A zero previous close makes normalized TR undefined even though raw TR remains valid. V1 reports NaN rather than fabricating a denominator.
4. No memory horizon is recommended in V1. This is intentional rather than an omitted feature.

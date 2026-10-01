# Module 0.3 V1.1 — Patch Audit Report

Status: **CLOSED V1.1**.

## V1.1 patch

- Replaced ambiguous `nan_policy="skip"` semantics with `nan_policy="hold"`.
- Held NaN never mutates EMA state.
- When initialized, a held NaN returns the current EMA in `ema` and `previous_ema`.
- Before initialization, a held NaN returns `ema=NaN` and creates no state.
- Held observations return `accepted=False` and `alpha=NaN`.
- Period remains validated even when value is NaN.
- Fractional finite periods remain supported.
- Documented the mathematical basis of `period >= 1`: it guarantees `0 < alpha <= 1`, making each update a convex combination with no endpoint overshoot.

## Added assertions

- Leading sequence `NaN, NaN, 100`: the NaNs create no state and 100 is the natural seed.
- Randomized property test over 5,000 fractional periods:
  - `0 < alpha <= 1`.
  - `ema_new` lies between previous EMA and current finite value.
- Module 0.1 truncation/state audits now include leading and internal held NaNs.

## Results

Self-verification:

```text
MODULE 0.3 V1.1 SELF-VERIFICATION PASSED
Adaptive EMA consumes external causal periods and is truncation invariant.
```

Module 0.3 test file:

```text
.....................................                                    [100%]
```

37 tests passed.

Full project suite:

```text
.....................................................                    [100%]
```

53 tests passed.

Internal shim-import scan returned no matches. Module 0.3 imports Module 0.1 from:

```python
from trading_system.audit.causal_state import ...
```

Modules 0.1 and 0.2 implementations were not modified by this patch.

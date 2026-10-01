# Module 3.1 V1.1 — Causal Volume Delta / Order-Flow Evidence Engine

Status: **CLOSED V1.1**

Rebuilt from scratch. No rejected historical draft was imported or reconstructed. No CLOSED module was modified.

## V1.1 numerical safety

ACTUAL mode requires finite float64 source volumes and finite derived `buy+sell` and `buy-sell` arrays. Sum and difference are both checked before ratio/output construction. Overflow raises `VolumeDeltaDataError`; no rescaling, clipping, or infinity replacement occurs. Under the valid non-negative domain, subtraction is bounded by the largest source magnitude, but the guard remains explicit.

PROXY mode validates finite close-location arithmetic for positive-range bars and finite `volume*close_location` wherever location is defined. Undefined zero-range geometry remains NaN; signed raw multiplication overflow raises.

## Explicit modes

```python
OrderFlowMode.ACTUAL_AGGRESSOR
OrderFlowMode.OHLCV_PROXY
```

There is no auto mode or column-based guessing.

`ACTUAL_AGGRESSOR` means actual according to caller/feed classification semantics; the engine cannot independently prove aggressor side or volume units.

`OHLCV_PROXY` is completed-bar price/location pressure geometry. It is never named delta and does not reconstruct buy/sell volume.

## ACTUAL schema

Input source columns are preserved:

```text
buy_volume
sell_volume
```

Derived columns:

```text
order_flow_mode
total_classified_volume
raw_delta
delta_ratio
delta_ratio_percentile
delta_ratio_history_count
delta_magnitude
delta_magnitude_percentile
delta_magnitude_history_count
```

When explicit reconciliation is enabled and `volume` is supplied:

```text
classified_volume_fraction
```

No equality requirement or mismatch threshold exists. Zero total classified volume produces `delta_ratio=NaN`, not neutral zero.

## PROXY schema

```text
order_flow_mode
close_location_proxy
volume_pressure_proxy
signed_volume_pressure_raw
pressure_proxy_percentile
pressure_proxy_history_count
pressure_magnitude
pressure_magnitude_percentile
pressure_magnitude_history_count
```

For positive range:

```python
close_location_proxy = (2*close-high-low)/(high-low)
```

`volume_pressure_proxy` equals location only when volume>0; volume is an information-availability gate and does **not** encode relative volume magnitude. Zero volume gives NaN pressure evidence while geometry remains available. `signed_volume_pressure_raw=volume*location` separately contains raw volume magnitude and retains input units; zero volume gives zero when geometry is defined. Zero-range geometry is NaN.

## Causal history

Signed and absolute-magnitude distributions are independent. Every current finite observation is ranked against prior finite history through Module 0.2, then pushed. Empty history yields NaN; no readiness threshold or rolling horizon exists.

## Fake-delta adversarial result

Two hidden aggressive-flow scenarios (90/10 and 10/90) were paired with identical OHLCV. Actual mode produced delta ratios +0.8 and -0.8, while proxy mode produced exactly the same output for identical OHLCV. This proves the proxy does not claim access to hidden trade decomposition.

## Audits and results

Module-specific suite:

```text
...................                                                      [100%]
```

19 tests passed.

Full suite:

```text
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 98%]
...                                                                      [100%]
```

219 tests passed.

Module 0.1 truncation and state-isolation audits passed independently for both modes. Future mutation/append, source immutability, mode-specific empty schemas, and scaling invariance passed.

## Benchmark

Three runs after warm-up, median milliseconds:

```text
N       ACTUAL     PROXY
500      16.844     18.864
1000     57.302     69.885
2000    213.782    264.106
```

The expanding exact percentile implementation inherits `PERFORMANCE-DEBT-001` and displays expected superlinear scaling. No arbitrary rolling window was introduced.

## Unresolved semantic/data-quality issues

1. Aggressor classification quality and volume units belong to the upstream feed contract and cannot be proven here.
2. Optional classified/total volume reconciliation is factual only; feed inclusion semantics may legitimately differ.
3. OHLCV pressure is not true delta and cannot distinguish hidden trade decompositions.
4. Raw delta and signed raw proxy retain input volume units and are not cross-asset normalized.
5. Exact expanding percentile contexts inherit O(N²) scalability debt.
6. No cross-chunk continuation, divergence, CVD anchor, or session reset exists in V1.1.
7. `RESEARCH-DEBT-004` records unconditional global history mixing volatility/session/structure regimes; no premature reset/filter was added.

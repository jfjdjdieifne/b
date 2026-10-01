# RESEARCH-DEBT-002 — Swing Continuation Baseline Duration Bias

Continuation episodes contribute their maximum reversal fraction.

## Potential issue

Longer episodes have more opportunities to accumulate a larger maximum.
Therefore the continuation distribution may reflect both reversal intensity
and episode duration.

This is a known statistical limitation, **not** a causality/look-ahead bug.

## Do not fix it now

Forbidden premature fixes:

- fixed duration normalization
- arbitrary age penalty
- fixed rolling cap
- hand-tuned correction

## Future evaluation

Measure the relationship between episode duration and maximum reversal using
walk-forward/out-of-sample analysis, including volatility/session context.
Design a causal correction only if the effect is materially useful.

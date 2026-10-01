# RESEARCH-DEBT-004 — Global Order-Flow Context Regime Mixing

**Owner:** Module 3.1  
**Status:** OPEN

## Problem

Exact expanding signed/magnitude percentile history pools observations across
different volatility, session, and structural contexts.

This unconditional empirical distribution is causal and intentional in V1.1,
but may mix heterogeneous regimes and weaken conditional information.

## Forbidden premature fixes

- fixed rolling window
- session reset by default
- volatility-threshold reset
- hand-selected regime filters

## Future evaluation

Measure conditional order-flow information using causal volatility, session,
and structure context during walk-forward/out-of-sample analysis. Introduce a
conditional estimator only if it provides material robust value and preserves
causal timing, evidence counts, and explicit data semantics.

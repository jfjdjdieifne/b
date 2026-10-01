# RESEARCH-DEBT-003 — Multi-Level Interaction Correlation

**Owner:** Module 2.2 Causal Liquidity Map  
**Status:** OPEN

## Problem

One market bar may interact with many historical liquidity-relevant levels.
Treating every crossed level as an independent empirical overshoot sample would
overweight high-density bars and regimes.

The observations share the same bar and are statistically correlated.

## V1 decision

Do **not** build a global empirical percentile from multi-level interaction
overshoots.

Preserve raw, normalized, per-level lifecycle events in the secondary event
table. Keep bar-level aggregate counts factual.

The nearest-same-side distance history remains acceptable because it admits at
most one nearest-distance observation per newly confirmed source level.

## Forbidden premature fixes

- treating crossed levels as independent samples
- arbitrary per-bar division by level count
- fixed level-density cap
- fixed distance pruning
- hand-tuned correlation weights

## Future research

Develop causal weighting or interaction-episode semantics only if walk-forward
and out-of-sample analysis demonstrates material value. Any solution must
preserve event provenance and pass primary/event-table causal equivalence tests.

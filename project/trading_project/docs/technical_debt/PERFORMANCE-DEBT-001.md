# PERFORMANCE-DEBT-001 — Exact Expanding Empirical Percentile Scalability

**Owner:** Layer 0 — Module 0.2 Causal Percentile Tracker  
**Status:** OPEN  
**Affects:** Module 0.2 and consumers including Module 1.1

## Current behavior

The exact expanding empirical percentile implementation is:

- causal: yes
- read-before-push: yes
- exact under its public mid-rank semantics: yes
- expanding-memory by default: yes
- rank cost per observation: O(n)
- full batch cost for n observations: O(n²)

This may become a practical bottleneck on large crypto market histories.

## Required preservation contract

Any future optimization must preserve exactly the same public semantics:

- rank against prior retained observations only
- exact tie mid-rank behavior
- identical NaN policy/accounting
- identical sample counts
- identical expanding-history behavior when `max_history=None`
- truncation invariance
- state isolation/reset contracts

It must pass equivalence tests against the current implementation and all
Module 0.1 behavioral audits.

## Possible research directions

- balanced order-statistics tree
- coordinate treatment plus Fenwick tree when a causal/exact coordinate
  contract can be established
- another exact streaming order-statistics structure

These are directions for measured investigation, not approved designs.

## Forbidden shortcut

Do **not** introduce an arbitrary rolling history cap solely to improve
performance. A fixed cap changes the estimator's public meaning and must not
be disguised as an optimization.

Do not introduce an approximate percentile implementation without an explicit
new contract, benchmarks, error analysis, and separate audit decision.

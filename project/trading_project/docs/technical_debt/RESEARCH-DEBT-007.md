# RESEARCH-DEBT-007 — Absorption vs Active Opposition Decomposition

**Owner:** Module 3.2  
**Status:** OPEN

Rank-space absorption evidence can be high both when price stalls and when
price moves strongly against aggression/pressure, because aligned response is
zero in both cases.

V1.1 preserves opposed-response magnitude and percentile separately rather
than introducing a hand-weighted correction.

## Forbidden premature fixes

- subtracting an arbitrary opposed-response weight;
- hard-threshold splitting stall versus reversal;
- hand-tuned composite scoring.

## Future evaluation

Layer 6 and walk-forward/out-of-sample analysis should evaluate the joint
information carried by absorption evidence and opposed-response evidence.

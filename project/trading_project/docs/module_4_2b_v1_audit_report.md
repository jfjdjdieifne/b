# Module 4.2B V1.1 — Causal Dealing Range & Premium/Discount Context

Status: **CLOSED V1.1**

Sequential confirmed opposite-side swings create versioned range candidates.
Same-side events replace the pending endpoint; failed non-positive geometry
creates nothing and the second endpoint becomes pending. Creation occurs only
at the second endpoint confirmation. Creation-row close location is evaluated
because both close and confirmed endpoints are known at completion.

LOW→HIGH creates `ASCENDING_DEALING_RANGE_CANDIDATE`; HIGH→LOW creates
`DESCENDING_DEALING_RANGE_CANDIDATE`. This is traversal provenance, not bias.

Position is un-clipped `(close-low)/width`; midpoint displacement is
`2*position-1`, with separate nonnegative discount/premium depths. No binary
signal, Fibonacci, OTE, or range invalidation exists.

Primary output exposes complete endpoint provenance, creation/rejection facts,
current latest range geometry, and location. Secondary table stores one row per
successfully created historical range. Exact primary/table truncation and state
isolation passed.

```text
Module tests: 11 passed
Full suite: 271 passed
```

```text
........................................................................ [ 26%]
........................................................................ [ 53%]
........................................................................ [ 79%]
.......................................................                  [100%]
```

Open debt: `RESEARCH-DEBT-012` selection semantics and
`RESEARCH-DEBT-013` nested hierarchy. Batch positions do not support
cross-chunk continuation.

V1.1 replaces compressed state mutation with dedicated per-row arrays for every creation/current semantic output. Exact location equations, version snapshots, failed-geometry persistence, primary/table consistency, upstream linkage, and overflow rejection are explicitly tested.

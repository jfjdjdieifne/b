# Module 5.1 V1.1 — Causal Higher-Timeframe Aggregator

Status: **CLOSED V1.1**

Fixed positive `Timedelta`, Unix epoch UTC anchor, CLOSE_TIME only, and absolute
UTC buckets `(start,end]`. Bucket-end integer arithmetic uses `divmod`: exact
boundaries remain in the bucket ending there; one nanosecond after advances.

Returns `(asof_surface, completed_htf)`. Same-row exact-end completion is
available; earlier rows never see final bucket values. Sparse/mid-dataset-start
buckets aggregate observed bars only and expose first/last timestamps and
source count without claiming complete cadence. Empty buckets are absent.

Completed-table rows include UTC boundaries, theoretical availability, first
observed processing position/time, observed source span/count, OHLC and optional
volume. As-of output preserves source labels/timezone/name and canonicalizes
frequency metadata.

```text
Module tests: 10 passed
Full suite: 276 passed
```

```text
........................................................................ [ 25%]
........................................................................ [ 51%]
........................................................................ [ 76%]
.................................................................        [100%]
```

Module 0.1 primary truncation/state and dedicated completed-table truncation
passed, including exact boundary, mandatory leak, sparse gaps, non-UTC/DST
equivalent instants, and empty schemas.

Open debt: `RESEARCH-DEBT-014` clock/event-bar unification and
`RESEARCH-DEBT-015` partial-bar information.

V1.1 explicitly tests epoch±1ns/pre-epoch arithmetic, delayed observed availability (09:58/09:59 bucket first exposed at 10:03), completed-row interval membership invariants, volume-output collision, complex dtype rejection, duration errors, and input immutability. Core `(start,end]`/as-of semantics are unchanged.

# Module 5.2 V1.1 — Causal Multi-Scale Confluence Matrix

Status: **CLOSED V1.1**

Consumes explicitly source-aligned scale frames with exact decision index, boolean availability, timezone-aware causal provenance, and persistent structure state. It emits per-scale state/direction/age and unweighted availability, directional counts, balance, consensus, and conflict. No bias, signal, score, scale weight, zone confluence, or event forward-fill.

The reusable alignment utility selects only latest observations with `available_at <= decision_time`. Future provenance, backward provenance, and state mutation under unchanged provenance are rejected.

```text
Module tests: 9 passed
Full suite: 281 passed
```

```text
........................................................................ [ 24%]
........................................................................ [ 49%]
........................................................................ [ 74%]
........................................................................ [ 99%]
..                                                                       [100%]
```

Open: `RESEARCH-DEBT-016` scale authority and `RESEARCH-DEBT-017` event confluence.

> **Historical reporting correction:** this report originally recorded `281 passed`. A later authoritative collection of the unchanged current `src/` and `tests/` tree established `290 collected / 290 passed`. The original figure is retained above as historical report text; current-state totals are maintained in `FINAL_VALIDATION.md` and `PRE_LAYER6_HANDOFF.md`.

V1.1 hardens the public as-of utility, duplicate/provenance/state validation, generated-column collision reservation, multi-frame truncation/future mutation, and real 5.1/DST integration. Official pandas as-of/timezone documentation is recorded in `ENGINEERING_CONSTITUTION.md`.

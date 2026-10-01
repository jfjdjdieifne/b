# Milestone Release — Module 6.2A-4 V1 Stage 4C-1 CLOSED

## Closure authority

Independent final audit decision:

```text
ACCEPTED FOR CLOSURE
```

Product Owner explicitly authorized closure (OWNER AUTHORIZATION — CLOSURE ONLY). Closure changed
documentation, status, release files, and `MANIFEST.sha256` only. Production (`src/`) and tests
(`tests/`) were not modified during closure.

Accepted Stage 4C-1 implementation/test hashes:

```text
e8fa0854a89ac2ec97c6cc691720860babf9d918f1746d489ed0093b08590475  src/trading_system/research/trajectory/trajectory_stage4c.py
7bfe704a89c6d2155521556fc657cdaf5e2fa48f0a83dd86536f57927f32bd6c  tests/test_trajectory_stage4c.py
```

All accepted `src/` and `tests/` files are listed in:

```text
docs/releases/MODULE_6_2A_4_V1_STAGE4C1_ACCEPTED_SRC_TESTS.sha256
```

## Certified baseline

```text
1000 collected
1000 passed
exit code 0
```

Module 6.2A-4 Stage 4C-1 dedicated coverage:

```text
36 passed
```

Arithmetic: prior CLOSED baseline 964 + 36 Stage-4C-1 = 1000.

## Patch history

```text
V1          IMPLEMENTED — PENDING AUDIT (shared raw HTF observed OHLC surface + optional
            declared-grid coverage metadata + causal as-of projection; 36 dedicated tests /
            1000 full); independent final audit: ACCEPTED FOR CLOSURE
V1          CLOSED
```

## What closure certifies

Stage 4C-1 establishes the **shared causal raw HTF observation surface, optional declared-grid
coverage metadata, and causal as-of projection** over the Stage 1/2/3/4A/4B-1/4B-2 foundation
consuming only the CLOSED public 5.1 aggregator output:

- raw HTF observed OHLC surfaces: completed HTF bucket observations (time, open, high, low, close)
  as sealed observation truth. Bucket truth is accepted only under `COMPLETED_ROW_AVAILABLE`;
  `BAR_PRE_CLOSE` is rejected. The LTF close and the HTF close are one information batch:
  `close_batch_order_unknown` is set at exact-boundary visibility rows and no intra-batch
  chronology is asserted;
- optional cadence-grid coverage metadata: when a cadence grid contract is declared, bucket
  completeness is decided by comparing timestamp SETS against the declared grid (never counts
  alone) with the five statuses `GRID_OBSERVATIONS_COMPLETE` / `GRID_OBSERVATIONS_MISSING` /
  `OFF_GRID_OBSERVATIONS_PRESENT` / `GRID_OBSERVATIONS_DEFECT_BOTH` /
  `GRID_COMPLETENESS_UNKNOWN`; without a declared grid coverage is `GRID_COMPLETENESS_UNKNOWN`
  (`COVERAGE_UNAVAILABLE` = `UNAVAILABLE` on as-of rows with no projectable grid status);
- causal as-of projection through a legal boundary T inside the sealed timeline
  (`project_htf_scale_prefix`), TIME_INDEXED only (`POSITIONAL` is a contract error). Exact
  boundary semantics: a completed bucket becomes projectable at an observed LTF row whose
  timestamp equals the bucket close — interval `(start, end]` — on the SAME timeline and only in
  phase `COMPLETED_ROW_AVAILABLE`; cross-timeline and `BAR_PRE_CLOSE` boundaries are rejected;
- in-progress / not-yet-observed buckets and their high/low/close (including extreme spikes) are
  invisible until the close is observed; a feed gap delays projectability to the first observed
  as-of position at/after the close (a theoretically elapsed bucket is not visible before its
  first observed as-of row) — verified against real CLOSED 5.1 outputs;
- `first_observed_asof_*` semantics = sealed-timeline projectability ONLY, guarded against
  semantic inflation as feed-arrival provenance or historical market availability
  (`SEALED_TIMELINE_PROJECTION_NOT_FEED_ARRIVAL_PROVENANCE_NOT_MARKET_AVAILABILITY`);
- grid coverage claims completeness only of sealed observations versus the DECLARED grid — never
  feed completeness, never market completeness; a partial bucket remains honest observation truth
  with its observed rows and incompleteness metadata (no fill, no drop, no interpolation); no HTF
  volume and no HTF entities are consumed or produced;
- derived-only frames with exact whole-frame schema equality to the declared derived schema (no
  market passthrough injection surface); optional sealed-timeline `volume` presence/absence never
  enters any Stage 4C-1 derived content;
- deterministic identity/hashing and live surface self-integrity verification (whole-frame schema
  equality + projection recomputation); no `mirror_verification_hash` field exists by owner
  correction (a verification pass/fail is not a hashable witness);
- deterministic reconstruction / derivation-witness semantics only.

## Accepted limitations (NON-BLOCKING — recorded as constraints/debts; not fixed during closure)

1. No `mirror_verification_hash` field exists (owner correction); mirroring/integrity is enforced
   live by exact whole-frame schema equality and projection recomputation.
2. The observed-asof walk-back visibility gate is semantically redundant over genuine CLOSED 5.1
   outputs (proven by an external deletion probe) and is retained as defense-in-depth only.
3. Sealed-timeline presence/absence of optional `volume` legitimately changes timeline identity
   and therefore surface identity; the Stage 4C-1 derived content is byte-identical in both cases
   and never carries volume.
4. Coherent witness-token forgery remains outside self-integrity scope (the accepted 4A/4B-1/4B-2
   convention); derived-only whole-frame schema equality plus content hashes plus projection
   recomputation narrow the exposure materially.
5. The first warm-up bucket is honestly declared `GRID_OBSERVATIONS_MISSING` when incomplete under
   a declared grid — a truthful coverage label, not a silent fill or a defect.
6. `POSITIONAL` input is rejected as a contract error (TIME_INDEXED only) by design.
7. A partial bucket is presented with its observed rows plus incompleteness metadata (observation
   truth preserved; no fill, no deletion) — intentional.

These are recorded as constraints/debts. None were modified, hardened, or fixed during closure.

## What closure does NOT certify

- feed-arrival provenance (`projectable_asof` is sealed-timeline projectability only) and
  historical market availability;
- feed completeness or market completeness (grid coverage is declared-grid observation coverage
  only);
- historical generating-input provenance (NOT_CERTIFIED / UNVERIFIABLE);
- HTF structure or HTF transitions;
- MTF confluence surfaces (Stage 4C-2);
- HTF volume or HTF entities (liquidity / order block / FVG / dealing range on HTF);
- predictive SUPPORT, statistical independence, incremental information;
- probability, weights, QualificationObjective;
- model / scorer / calibration, geometry, entry/stop/target, execution, fills, trade lifecycle;
- BUY/SELL signals, PnL, WIN/LOSS/SUCCESS semantics, fixed horizons;
- predictive usefulness, trading edge, or profitability.

## Open debts preserved

```text
RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025
```

No debt was silently closed. The Stage 4C-1 research manifest itself declares
`SEALED_TIMELINE_PROJECTION_NOT_FEED_ARRIVAL_PROVENANCE_NOT_MARKET_AVAILABILITY` and
`PROJECTABLE_AT_CLOSE_ONLY_IN_COMPLETED_ROW_AVAILABLE_SAME_TIMELINE`, and keeps DESCRIPTORS,
ESTIMANDS, MODEL, GEOMETRY, EXECUTION = NOT_IMPLEMENTED and WIN_LOSS = FORBIDDEN.

## Not started

```text
Stage 4C-2 HTF structure / transitions / MTF confluence   NOT STARTED
descriptors / estimands                                  NOT STARTED
model / scorer / signals                                 NOT STARTED
geometry / execution                                     NOT STARTED
```

## Final state

```text
Module 6.2A-4 V1 Stage 4C-1
CLOSED

Certified baseline:
1000 collected
1000 passed
```

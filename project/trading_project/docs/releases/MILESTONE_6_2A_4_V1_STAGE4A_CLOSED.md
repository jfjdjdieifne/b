# Milestone Release — Module 6.2A-4 V1 Stage 4A CLOSED

## Closure authority

Independent final audit decision:

```text
ACCEPTED FOR CLOSURE
```

Product Owner explicitly authorized closure (CLOSURE ONLY). Closure changed
documentation, status, handoff/release files, and `MANIFEST.sha256` only.
Production (`src/`) and tests (`tests/`) were not modified during closure.

Accepted Stage-4A implementation/test hashes:

```text
19034dfff4ca4007921bdd7b3bd16c8afc5048b3601f2538d02510ba27edc26e  src/trading_system/research/trajectory/trajectory_stage4a.py
7547abfd5cf699badf2fc19b9a295b77aea8b73d0848fa5d12603655b3aa2b7f  tests/test_trajectory_stage4a.py
```

All accepted `src/` and `tests/` files are listed in:

```text
docs/releases/MODULE_6_2A_4_V1_STAGE4A_ACCEPTED_SRC_TESTS.sha256
```

## Certified baseline

```text
890 collected
890 passed
exit code 0
```

Module 6.2A-4 Stage 4A dedicated coverage:

```text
72 passed
```

Arithmetic: prior CLOSED baseline 818 + 72 Stage-4A = 890.

## What closure certifies

Stage 4A adds to the Stage 1 / Stage 2 / Stage 3 foundation a factual shared per-bar market-state
trajectory for four domains, in V1:

**Dynamic Volatility (CLOSED 1.1)** — completed-bar true range, normalized true range,
causal percentiles/history, normalized TR change, expansion context. First-bar insufficient-history
missingness preserved exactly as NaN (not relabeled UNAVAILABLE).

**Session Context (CLOSED 1.2)** — timestamp-only calendar encodings (hour/weekday sin/cos),
per-session activity, active session count, under the CLOSED timezone/DST contract.

**Volume Delta / Order Flow (CLOSED 3.1) in OHLCV_PROXY mode only** — close-location proxy,
volume-pressure proxy, signed raw pressure, causal percentiles/history.

**Absorption / Response (CLOSED 3.2) in OHLCV_PROXY mode only** — same-bar proxy pressure ×
backward log-return response, aligned/opposed magnitudes/percentiles, proxy absorption evidence.

Closure additionally certifies the Stage-4A infrastructure:

- shared domain surfaces independent of hypothesis identity (computed once per exact domain-surface
  identity, not per timeline);
- compact hypothesis prefix binding (no physical row duplication per hypothesis);
- complete public-result hashing over the full CLOSED factual output per domain;
- surface self-integrity verification (recomputes public-result hash and surface identity from
  current content; rejects stale-identity / mutable-DataFrame tampering);
- exact output-schema verification per domain from the CLOSED contract + frozen config payload;
- reconstruction / derivation witness semantics (NOT historical generating-input provenance);
- legal InformationKey boundary validation in `project_surface_prefix` (positional and
  time-indexed), rejecting `BAR_PRE_CLOSE` for completed-bar facts and enforcing timestamp
  consistency for time-indexed boundaries;
- no post-boundary projected facts;
- future-prefix invariance under legally rebuilt future surfaces.

## Important limitations

Stage 4A V1 does **NOT** support:

```text
ACTUAL_AGGRESSOR order flow
ACTUAL absorption
```

Reason: the current CLOSED `MarketObservationTimeline` does not seal `buy_volume`/`sell_volume`, and
no authoritative external factual-availability contract exists for those inputs. Stage 4A must not
invent factual-available-at semantics for external aggressor data; requesting ACTUAL mode is rejected
explicitly with no fallback to PROXY.

Do not claim:

```text
OHLCV_PROXY == ACTUAL
```

PROXY is completed-bar OHLCV geometry only. No predictive quality is claimed for PROXY (or for
ACTUAL). Reconstruction / configuration / input identities remain deterministic derivation
witnesses only, unless a CLOSED source explicitly certifies historical provenance.

## What closure does NOT certify

- Stage 4B (entity/lifecycle: liquidity / OB / FVG / dealing range) — NOT STARTED;
- Stage 4C (HTF / MTF) — NOT STARTED;
- descriptors, estimands, hazard/survival/competing-risk models;
- model / scorer / weights / probabilities / confluence scores;
- geometry, entry/stop/target, execution, fills, trade lifecycle;
- PnL, WIN/LOSS/SUCCESS semantics, signals, predictive edge, fixed horizons;
- statistical independence or overlapping-hypothesis dependence resolution.

## Patch history

```text
V1          IMPLEMENTED — PENDING AUDIT; independent audit: PATCH REQUIRED (mutable-DataFrame stale-identity BLOCKER)
V1 PATCHED  PATCHED / IMPLEMENTED — PENDING AUDIT (self-integrity verification, defensive copy, upstream verification)
V1 PATCHED  PATCHED / IMPLEMENTED — PENDING AUDIT (boundary InformationKey legality: BAR_PRE_CLOSE rejection, adapter kind in identity)
V1 PATCHED  independent final audit: ACCEPTED FOR CLOSURE
V1 PATCHED  CLOSED
```

Patches applied during re-audit:

1. `verify_surface_integrity` recomputes the public-result hash and surface identity from current
   content, rejecting stale/forged `public_result_hash`, `surface_id`, `output_columns`, and any
   mutated surface DataFrame; defensive deep copy at the construction boundary; upstream
   absorption surface verified before consumption.
2. `project_surface_prefix` enforces the legal boundary phase
   (`COMPLETED_ROW_AVAILABLE` / `RESEARCH_SNAPSHOT_AVAILABLE`), rejects `BAR_PRE_CLOSE`, validates
   the complete InformationKey via the CLOSED adapter (timestamp/position/timeline), and binds
   `adapter_kind` into the surface identity.

## Open debts preserved

```text
RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025
```

No debt was silently closed.

## Not started

```text
Stage 4B entity/lifecycle trajectory    NOT STARTED
Stage 4C HTF/MTF trajectory             NOT STARTED
descriptors / estimands                 NOT STARTED
model / scorer / signals                NOT STARTED
geometry / execution                    NOT STARTED
```

## Final state

```text
Module 6.2A-4 V1 Stage 4A
CLOSED

Certified baseline:
890 collected
890 passed
```

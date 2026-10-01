# Milestone Release — Module 6.2A-4 V1 Stage 4B-1 CLOSED

## Closure authority

Independent final audit decision:

```text
ACCEPTED FOR CLOSURE
```

Product Owner explicitly authorized closure (CLOSURE ONLY). Closure changed documentation, status,
release files, and `MANIFEST.sha256` only. Production (`src/`) and tests (`tests/`) were not
modified during closure.

Accepted Stage 4B-1 implementation/test hashes:

```text
bc393fe4ffb8dec9bdb16e4ae8e0036f22faefdecc8dc67345a5a881207bb708  src/trading_system/research/trajectory/trajectory_stage4b1.py
7e0c572d56074775b807278485a31a02ed6a6ec8e5bc941c638c586e2a401271  tests/test_trajectory_stage4b1.py
```

All accepted `src/` and `tests/` files are listed in:

```text
docs/releases/MODULE_6_2A_4_V1_STAGE4B1_ACCEPTED_SRC_TESTS.sha256
```

## Certified baseline

```text
927 collected
927 passed
exit code 0
```

Module 6.2A-4 Stage 4B-1 dedicated coverage:

```text
37 passed
```

Arithmetic: prior CLOSED baseline 890 + 37 Stage-4B-1 = 927.

## Test-hardening patch history

```text
V1          IMPLEMENTED — PENDING AUDIT; independent audit: ACCEPTED FOR CLOSURE (deferred for test hardening)
V1          PATCHED (TESTS ONLY) — non-vacuous regression fixtures (real 2.1A→2.1B→2.1C events)
V1          PATCHED / IMPLEMENTED — PENDING RE-AUDIT; independent final audit: ACCEPTED FOR CLOSURE
V1          CLOSED
```

The test-hardening patch added a deterministic fixture (seeded `EmpiricalConfirmationPolicy` +
staircase market) that produces real confirmed swings with `origin_position <
confirmation_position`, real non-neutral 2.1B sequence facts (HH/HL), and a real 2.1C `BOS_UP`
structural break (`structure_state_before == UP_STRUCTURE`), so the causality / prefix-invariance
regression coverage is non-vacuous.

## What closure certifies

Stage 4B-1 establishes the **shared causal structure surface contract** only:

- one shared, hypothesis-independent structure surface built from the CLOSED public chain
  2.1A (`CausalAdaptiveSwingDetector`) → 2.1B (`ConfirmedSwingSequenceEngine`) → 2.1C
  (`CausalStructuralBreakEngine`);
- complete public factual result of 2.1A + 2.1B + 2.1C bound by canonical component hashes and a
  composed `public_result_hash` (not merely the downstream-consumed subset);
- shared storage: one surface per exact surface identity, with a compact hypothesis prefix binding
  (no per-hypothesis copy, no persisted per-prefix copy);
- factual availability governed by the confirmation/event row, NEVER by origin; origin fields are
  preserved as positional Int64 data and never manufactured into InformationKeys;
- compact prefix identity through a legal boundary T; full-surface identity changes on legal future
  append while the prefix identity through T is preserved (verified on the real CLOSED chain);
- boundary legality mirroring CLOSED Stage 1 / Stage 4A (`BAR_PRE_CLOSE` rejected, cross-timeline
  rejected, positional no-timestamp, time-indexed timestamp correctness);
- self-integrity verification (`verify_surface_integrity`) recomputes component + composed hashes
  from current content and rejects stale/forged fields;
- `verify_surface_matches_reconstruction` compares supplied vs authoritative surfaces field-by-field;
- deterministic reconstruction witness semantics only.

## Accepted limitations (NON-BLOCKING, not CLOSED behavioral failures)

1. `verify_surface_integrity` provides internal self-consistency for stored witness metadata;
   coherent witness-token forgery is not independently disproven by self-integrity alone.
2. `verify_surface_matches_reconstruction` compares against a supplied authoritative surface; it does
   not itself independently reconstruct the CLOSED chain.
3. Passthrough market fields are reconstruction inputs bound through the CLOSED timeline seal; the
   Stage 4B-1 public-result hash covers the complete derived structure result.
4. `prefix_hash` is factual content identity; complete binding carries surface/timeline/boundary
   identity.

## Provenance limitation

Historical generating-input provenance remains **NOT_CERTIFIED / UNVERIFIABLE** — the CLOSED engines
do not seal input identity. All Stage 4B-1 identities are deterministic reconstruction / derivation
witnesses only.

## What closure does NOT certify

- predictive usefulness, trading edge, profitability, or statistical independence;
- Liquidity / OB / FVG / Dealing Range trajectory surfaces (Stage 4B-2);
- Stage 4C (HTF / MTF);
- descriptors, estimands, hazard/survival/competing-risk models;
- model / scorer / weights / probabilities / confluence scores;
- geometry, entry/stop/target, execution, fills, trade lifecycle;
- PnL, WIN/LOSS/SUCCESS semantics, signals, fixed horizons.

## Open debts preserved

```text
RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025
```

No debt was silently closed.

## Not started

```text
Stage 4B-2 entity/lifecycle surfaces   NOT IMPLEMENTED / NOT STARTED
Stage 4C HTF/MTF                       NOT STARTED
descriptors / estimands                NOT STARTED
model / scorer / signals               NOT STARTED
geometry / execution                   NOT STARTED
```

## Final state

```text
Module 6.2A-4 V1 Stage 4B-1
CLOSED

Certified baseline:
927 collected
927 passed
```

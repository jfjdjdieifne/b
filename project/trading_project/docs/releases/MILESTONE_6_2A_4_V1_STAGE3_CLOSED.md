# Milestone Release — Module 6.2A-4 V1 Stage 3 CLOSED

## Closure authority

Independent final audit decision:

```text
ACCEPTED FOR CLOSURE
```

Product Owner explicitly authorized closure (CLOSURE ONLY). Closure changed
documentation, status, handoff/release files, and `MANIFEST.sha256` only.
Production (`src/`) and tests (`tests/`) were not modified during closure.

Accepted Stage-3 implementation/test hashes:

```text
e79a61cf85ce0ba5cb3dfcd3db63b8fcdbe8d53243bb28855eb0bc91dad2dc8e  src/trading_system/research/trajectory/trajectory_stage3.py
2777fd6661847226b91c1294234713e93a1e861d5f6845a164f3e89e523e8d28  tests/test_trajectory_stage3.py
```

All accepted `src/` and `tests/` files are listed in:

```text
docs/releases/MODULE_6_2A_4_V1_STAGE3_ACCEPTED_SRC_TESTS.sha256
```

## Certified baseline

```text
818 collected
818 passed
exit code 0
```

Module 6.2A-4 Stage 3 dedicated coverage:

```text
81 passed
```

Arithmetic: prior CLOSED baseline 737 + 81 Stage-3 = 818.

## What closure certifies

Stage 3 adds to the Stage 1 / Stage 2 foundation:

**Factual terminal/censor snapshot layer:**

- immutable mature terminal snapshot (`FactualTerminalSnapshot`);
- immutable right-censored-as-of snapshot (`RightCensoredAsOfSnapshot`);
- append-only as-of snapshot series (strictly increasing research-as-of, prior snapshots unchanged);
- binding to CLOSED 6.2A-1 as the authoritative source for mature-vs-censored classification,
  `factual_outcome_id`, `research_snapshot_id`, terminal state, and terminal position;
- binding to CLOSED Stage 2 trajectory prefix (PRICE / STRUCTURE / LIFECYCLE);
- complete Stage 2 public-result deterministic-equivalence verification
  (`STAGE2_PUBLIC_RESULT_EQUIVALENCE_V1`) over `price.price_bars` + price final scalars +
  `structure.structure_events` + `lifecycle.lifecycle_events` + lifecycle terminal fields +
  envelope count + envelope prefix hash;
- envelope-context verification: every supplied and reconstructed envelope is proven to belong to
  the expected timeline / timeline_hash / anchor / interval (with CLOSED `envelope.verify()`);
- separation of terminal factual availability from research as-of (two distinct InformationKeys,
  e.g. terminal available at T12, research reconstructed at T15);
- compact snapshot identity (hashes and counts only; no raw market history, no full envelope
  tuple, no duplicated running payloads);
- reconstruction / derivation-witness semantics;
- origin preserved exactly as the supplied Stage 2 artifact's own embedded lifecycle rows
  (Int64 position, not a manufactured InformationKey);
- literal terminal states only (CONTRADICTED, SUPERSEDED, OBSERVED_DIRECTION_ESTABLISHED), no
  WIN/LOSS/SUCCESS/PROFIT, no price-inferred terminal;
- right-censor semantics `RIGHT_CENSORED_AS_OF_BOUNDARY` only, matching CLOSED 6.2A-1, with no
  invented censor taxonomy;
- positional and time-indexed timelines (timezone-aware, DST/irregular UTC), cross-timeline
  rejection, same-information-batch determinism;
- determinism (A→A, A→B→A, fresh-instance), caller-input immutability, frozen snapshots;
- firewall: LIVE modules (layers 0–5, decision) do not import Stage 3 research code.

## Important provenance limitation

Stage 3 does **NOT** certify the historical generating-input identity of a supplied Stage 2
artifact.

The following are derivation / reconstruction witnesses only:

```text
reconstruction_swing_policy_hash
reconstruction_ledger_seal
stage2_reconstruction_binding_hash
```

They prove deterministic reconstruction equivalence under the supplied witness inputs. They do
**not** prove those inputs historically generated the supplied Stage 2 artifact.

Historical generating-input provenance remains:

```text
NOT CERTIFIED / UNVERIFIABLE
```

under the current CLOSED Stage 2 contract (CLOSED Stage 2 does not seal input identity).

## What closure does NOT certify

- Stage 4 trajectory domains (volatility / liquidity / OB / FVG / dealing range / orderflow /
  session / HTF / MTF trajectory);
- path descriptors;
- learning estimands;
- hazard / survival model, competing-risk probabilities, or any censor estimand;
- predictive model, scorer, weights, probabilities, confluence scores;
- geometry, entry/stop/target, execution, fills, trade lifecycle;
- PnL, WIN/LOSS/SUCCESS semantics, signals;
- fixed horizons;
- statistical independence or overlapping-hypothesis dependence resolution.

## Patch history

```text
V1          IMPLEMENTED — PENDING AUDIT; independent audit: PATCH REQUIRED
V1 PATCHED  PATCHED / IMPLEMENTED — PENDING AUDIT (BLOCKER 1+2: envelope binding + input provenance)
V1 PATCHED  PATCHED / IMPLEMENTED — PENDING AUDIT (provenance semantics: derivation witness vs generating input)
V1 PATCHED  PATCHED / IMPLEMENTED — PENDING AUDIT (complete public-result equivalence)
V1 PATCHED  independent final audit: ACCEPTED FOR CLOSURE
V1 PATCHED  CLOSED
```

Patches applied during re-audit:

1. Envelope binding: every Stage 2 envelope verified against expected timeline/anchor/interval
   (BLOCKER 1), and the supplied Stage 2 result verified against an authoritative reconstruction
   from the bound inputs (BLOCKER 2).
2. Provenance semantics: swing-policy / ledger identities recast as derivation witnesses, and
   origin fields read from the supplied artifact's own lifecycle rows (not the caller ledger).
3. Complete public-result equivalence: `STAGE2_PUBLIC_RESULT_EQUIVALENCE_V1` canonical hash over
   the full public factual result closes the gap where equal envelope identity could hide factual
   row differences (e.g. `trigger_relationship_id` 2 vs 999).

## Open debts preserved

```text
RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025
```

No debt was silently closed. Stage 3 factual censor representation does NOT close the
competing-risk / censor estimand debt (RESEARCH-DEBT-023).

## Not started

```text
Stage 4 trajectory domains              NOT STARTED
descriptors / estimands                 NOT STARTED
hazard / survival / competing-risk      NOT STARTED
model / scorer / signals                NOT STARTED
geometry / execution                    NOT STARTED
```

## Final state

```text
Module 6.2A-4 V1 Stage 3
CLOSED

Certified baseline:
818 collected
818 passed
```

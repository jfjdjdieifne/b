# Milestone Release — Module 6.2A-4 V1 Stage 2 CLOSED

## Closure authority

Independent final audit decision:

```text
ACCEPTED FOR CLOSURE
```

Product Owner explicitly authorized closure (CLOSURE ONLY). Closure changed
documentation, status, handoff/release files, and `MANIFEST.sha256` only.
Production (`src/`) and tests (`tests/`) were not modified during closure.

Accepted Stage-2 implementation/test hashes:

```text
827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f  src/trading_system/research/trajectory/trajectory_stage2.py
bb5372fbad3582ce81d64b5d791b3599504b4ee12775767f77d93763f9bb1c6d  tests/test_trajectory_stage2.py
```

All accepted `src/` and `tests/` files are listed in:

```text
docs/releases/MODULE_6_2A_4_V1_STAGE2_ACCEPTED_SRC_TESTS.sha256
```

## Certified baseline

```text
737 collected
737 passed
exit code 0
```

Module 6.2A-4 Stage 2 dedicated coverage:

```text
36 passed
```

Arithmetic: prior CLOSED baseline 701 + 36 Stage-2 = 737.

## What closure certifies

Stage 2 adds to the Stage 1 foundation:

**PRICE trajectory:**
- shared raw OHLC[V] market facts per observed bar (open, high, low, close, volume);
- hypothesis-relative exact facts: reference price, direction, per-bar favorable/adverse excursion;
- running maximum favorable and adverse excursion with strict-greater tie preservation (first occurrence);
- favorable/adverse extreme price, bar position, and InformationKey;
- new-running-extreme flags (is_new_favorable_extreme, is_new_adverse_extreme);
- close displacement from reference = `(close - ref) / ref`;
- bar offset from decision bar = `pos - decision_pos`;
- SAME_INFORMATION_BATCH_ORDER_UNKNOWN when both favorable and adverse excursion occur in the same OHLC bar;
- excursion formulas per CLOSED 6.2A-1 orientation (UP: fav = high/ref − 1, adv = 1 − low/ref; DOWN: inverse);
- zero/negative clamping;
- BAR envelope as STATE_OBSERVATION, NEW_FAVORABLE_EXTREME / NEW_ADVERSE_EXTREME as FACTUAL_EVENT.

**STRUCTURE trajectory (consumer of CLOSED 2.1A/2.1B/2.1C only):**
- swing origin < confirmation enforced, confirmation position is factual-available-at position;
- taxonomy: SWING_HIGH_CONFIRMED, SWING_LOW_CONFIRMED, SEQUENCE_{type}_{class}, BREACH_HIGH/LOW_{WICK/CLOSE/WICK_ONLY}, BREAK_{BOS/CHOCH/UNCLASSIFIED/AMBIGUOUS}, STATE_{before}_TO_{after};
- prefix causality: market_history is truncated to interval end before passing to CLOSED engines, guaranteeing no future-bar influence on structural facts observable through T.

**LIFECYCLE trajectory (consumer of CLOSED 6.1B ledger only):**
- literal terminal states only: CONTRADICTED, SUPERSEDED, OBSERVED_DIRECTION_ESTABLISHED;
- no second lifecycle state machine, no terminal inference from price movement;
- mature interval must end at terminal factual-availability boundary (post-terminal rows raise TrajectoryDataError);
- unresolved as-of (empty or non-matching ledger) returns empty lifecycle;
- SUCCESS/WIN/LOSS/PROFIT are not accepted as terminal states.

**All Stage 2 is subject to:**
- shared MarketObservationTimeline (no per-hypothesis market copy);
- two-clock semantics (observation ≤ factual-available-at);
- creation bar exclusion (first observed bar = decision + 1);
- same-information-batch-order-unknown semantics for co-occurring extremes;
- canonical domain-separated SHA-256 identity (via trajectory_contract);
- as-of projection visibility: facts invisible before their available-at key;
- input immutability: caller DataFrames are not mutated by Stage 2 functions;
- determinism: A→A, A→B→A, fresh-instance equivalence;
- firewall: LIVE modules (layers 0–5, decision) do not import research trajectory code.

## What closure does NOT certify

- true_range / normalized true range / volatility trajectory of any kind;
- liquidity / OB / FVG / dealing range / volume delta / absorption trajectory;
- session / HTF / MTF trajectory;
- censor-series implementation (belongs to Stage 3);
- path descriptors, quality, efficiency, rocket/retracement scores;
- learning estimands;
- predictive model, scorer, weights, probabilities, confluence scores;
- geometry, entry/stop/target, execution, PnL;
- any WIN/LOSS/SUCCESS interpretation.

## Patch history

```text
V1          IMPLEMENTED — PENDING AUDIT; independent audit: PATCH REQUIRED
V1 PATCHED  PATCHED / IMPLEMENTED — PENDING AUDIT; independent final audit: ACCEPTED FOR CLOSURE
V1 PATCHED  CLOSED
```

Patches applied during re-audit:

1. Structure prefix causality: `_run_closed_structure_chain` now receives
   `market_history` truncated to interval end, preventing future-bar leakage.
2. Taxonomy completeness: `BREACH_HIGH_WICK_ONLY`, `BREACH_LOW_WICK_ONLY`,
   `STATE_{before}_TO_{after}` events added.
3. Provenance typo corrected: `tructural_breaks` → `structural_breaks`.
4. Test expansion: 2 → 36 tests covering the full required adversarial matrix.

## Open debts preserved

```text
RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025
```

No debt was silently closed.

## Not started

```text
censor-series / Stage 3                  NOT STARTED
descriptors / estimands                  NOT STARTED
model / scorer / signals                 NOT STARTED
geometry / execution                     NOT STARTED
```

## Final state

```text
Module 6.2A-4 V1 Stage 2
CLOSED

Certified baseline:
737 collected
737 passed
```
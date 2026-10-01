# Milestone Release — Module 6.2A-4 V1 Stage 4B-2 CLOSED

## Closure authority

Independent final audit decision:

```text
ACCEPTED FOR CLOSURE
```

Product Owner explicitly authorized closure (OWNER AUTHORIZATION — CLOSURE ONLY). Closure changed
documentation, status, release files, and `MANIFEST.sha256` only. Production (`src/`) and tests
(`tests/`) were not modified during closure.

Accepted Stage 4B-2 implementation/test hashes:

```text
ce6fe481064c672538df63f9560493506c3b532de0de30714f71c8c4cf9ab563  src/trading_system/research/trajectory/trajectory_stage4b2.py
3315a6ac5c427b413f6eb510abe2486839b21d3c5a2bd0c8fde1beccf21d620b  tests/test_trajectory_stage4b2.py
```

All accepted `src/` and `tests/` files are listed in:

```text
docs/releases/MODULE_6_2A_4_V1_STAGE4B2_ACCEPTED_SRC_TESTS.sha256
```

## Certified baseline

```text
964 collected
964 passed
exit code 0
```

Module 6.2A-4 Stage 4B-2 dedicated coverage:

```text
37 passed
```

Arithmetic: prior CLOSED baseline 927 + 37 Stage-4B-2 = 964.

## Patch history

```text
V1          IMPLEMENTED — PENDING AUDIT; independent audit: PATCH REQUIRED
            (BLOCKER 1: single generic domain class with caller-controlled domain field — coherent
             domain/schema switch with recomputed hashes was accepted;
             BLOCKER 2: prefix binding covered bars only — deleting a pre-T creation event did not
             change the prefix)
V1          PATCHED / IMPLEMENTED — PENDING RE-AUDIT (four distinct surface classes; schema
            authority derived from surface class + frozen CLOSED mirrors; four-component prefix
            binding: derived bars + events <= T + entities at availability position + normalized
            events); independent re-audit: PATCH REQUIRED
            (BLOCKER 3: private underscore imports of CLOSED engine schemas/constants)
V1          PATCHED (private_imports_patched) / IMPLEMENTED — PENDING RE-AUDIT (all private
            imports removed; local Final frozen schema mirrors; independent dynamic mirror
            verification that builds the real CLOSED engines and rejects any added/dropped/reordered
            public column); independent final audit: ACCEPTED FOR CLOSURE
V1          CLOSED
```

## What closure certifies

Stage 4B-2 establishes the **four shared, hypothesis-independent factual entity/lifecycle
trajectory surfaces** over the Stage 1/2/3/4A/4B-1 foundation:

- Liquidity surface consuming the CLOSED 2.2 level-lifecycle engine over the Stage 4B-1 structure
  surface;
- Order-Block surface consuming the CLOSED 4.1 order-block candidate/lifecycle engine over the
  Stage 4B-1 structure surface;
- FVG surface consuming the CLOSED 4.2A engine, structurally independent (OHLC only, built directly
  on the sealed market, `structure_surface_id=None` mandatory);
- Dealing-Range surface consuming the CLOSED 4.2B engine over the Stage 4B-1 structure surface,
  using the original CLOSED dealing-range table.

Each surface binds, per exact domain-surface identity:

- a per-bar `bar_frame` (frozen CLOSED-engine output + schema-bound market passthrough), an event
  frame, a normalized entity frame, and a normalized event frame with an explicit
  same-information-batch order-unknown ambiguity flag;
- schema authority derived from the concrete surface class plus local `Final` frozen mirrors of the
  CLOSED public output schemas — never from a caller-supplied domain field or from a recomputable
  hash;
- an independent dynamic mirror verification that constructs the real CLOSED engines and rejects
  any future public-column addition, deletion, or reordering (a coherent recomputed hash cannot
  bypass it);
- four-component factual prefix binding through a legal boundary T: derived bar columns + factual
  events through T + normalized entities keyed at factual availability position (never origin) +
  normalized events; with canonical `reset_index(drop=True)` treatment so positional/index-container
  noise cannot change or mask factual identity;
- distinct immutable surface-class identity per domain (liquidity / order block / FVG / dealing
  range), so coherent cross-domain switching (including cross-table and cross-class substitution)
  is rejected;
- surface self-integrity verification that recomputes identity from current content and rejects
  stale-identity / mutable-DataFrame tampering;
- boundary legality mirroring CLOSED Stage 1 / Stage 4A / Stage 4B-1 (`BAR_PRE_CLOSE` rejected for
  completed-bar facts, cross-timeline rejection, positional no-timestamp vs time-indexed timestamp
  correctness);
- same-information-batch semantics equal to literal `duplicated(event_position)`; normalized
  entities traceable 1:1 to creation events (or the original CLOSED range table for dealing range);
- research/live firewall intact: nothing imports `trading_system.research` from decision/Layers
  0–5 code, and only the Stage 4B-2 test module imports the Stage 4B-2 trajectory module;
- deterministic reconstruction / derivation-witness semantics only.

Frozen certified schemas (dedicated deterministic fixture): Liquidity 23 derived bar columns +
16 event columns (15 entities); Order Block 26 + 20 (7 entities, 14-column entity table); FVG
27 + 21 source event columns (50 entities, 15-column entity table; normalized event frame = 21 +
ambiguity flag = 22); Dealing Range 30 derived bar columns + the original 17-column CLOSED range
table (14 ranges). Verified consumed market passthrough columns are high/low/close (liquidity),
OHLC (order block, FVG), and close (dealing range); none of the four engines consumes volume.

## Accepted limitations (NON-BLOCKING, not CLOSED behavioral failures)

1. An injected foreign column placed **between** the passthrough block and the derived tail of a
   `bar_frame` is accepted, whereas appending it at the tail is rejected. Integrity/hashing consume
   the schema-bound derived tail and the exact event/entity/range tables, so no derived fact can be
   forged through this channel; it belongs to the accepted passthrough-binding convention. A future
   hardening patch may enforce exact whole-frame column equality (`bar_frame.columns == passthrough +
   declared schema`).
2. Market passthrough columns inside an engine frame are reconstruction inputs bound through the
   CLOSED timeline seal; the content hashes bind the complete derived result and the exact
   event/entity/range tables rather than re-hashing passthrough cells (same convention as Stage
   4A/4B-1).
3. Reconstruction / mirror equivalence is a derivation witness, not historical generating-input
   provenance; historical generating-input provenance remains NOT_CERTIFIED / UNVERIFIABLE.
4. `Series.equals` does not distinguish +0.0 / -0.0 while content hashing does; the current
   deterministic fixture does not exercise signed zero.
5. The current fixture does not generate a DR rejection event or a far OB-retrieval restoration;
   those CLOSED-engine paths are consumed but not fixture-exercised here.

## What closure does NOT certify

- predictive `SUPPORT`, statistical independence of evidence entities, incremental information;
- predictive usefulness, trading edge, profitability, probabilities, weights, or any score;
- QualificationObjective, model/scorer, calibration, signal, buy/sell decision;
- descriptors, estimands, hazard/survival/competing-risk models;
- Stage 4C (HTF / MTF future surfaces) — remains NOT_IMPLEMENTED / NOT STARTED;
- geometry, entry/stop/target, execution, fills, trade lifecycle;
- PnL, WIN/LOSS/SUCCESS semantics, fixed horizons;
- ICT canonical terminology fidelity beyond the accepted preliminary D1/D1.1 source audit.

## Open debts preserved

```text
RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025
```

No debt was silently closed. The Stage 4B-2 research manifest itself declares STAGE4C,
DESCRIPTORS, ESTIMANDS, MODEL, GEOMETRY, EXECUTION = NOT_IMPLEMENTED and WIN_LOSS = FORBIDDEN.

## Not started

```text
Stage 4C HTF/MTF future surfaces        NOT IMPLEMENTED / NOT STARTED
descriptors / estimands                NOT STARTED
model / scorer / signals               NOT STARTED
geometry / execution                   NOT STARTED
```

## Final state

```text
Module 6.2A-4 V1 Stage 4B-2
CLOSED

Certified baseline:
964 collected
964 passed
```

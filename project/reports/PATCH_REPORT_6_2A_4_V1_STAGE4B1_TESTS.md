# Patch Report — Module 6.2A-4 V1 Stage 4B-1 (non-vacuous regression tests)

**Shared Causal Structure Surface**

Date: 2026-08-21
Task Type: PATCH ONLY (TESTS ONLY)
Role: Builder (NOT an Independent Audit)
Final status: **PATCHED / IMPLEMENTED — PENDING RE-AUDIT**

---

## 1. Purpose

The independent audit ACCEPTED the implementation but found the existing fixture produced zero
confirmed swings / zero sequence transitions / zero structural breaks, making several causality /
prefix tests vacuous. This patch persists non-vacuous regression protection in the official suite
before closure, WITHOUT changing any production behavior.

## 2. Exact test changes

File modified (tests only): `tests/test_trajectory_stage4b1.py`

Added imports: `CausalAdaptiveSwingDetector`, `EmpiricalConfirmationPolicy`,
`ConfirmedSwingSequenceEngine`, `CausalStructuralBreakEngine`.

Added helpers:
- `_rich_policy()` — `EmpiricalConfirmationPolicy(quantile=0.1, prior_continuation_reversals=(0.01…0.49))`.
  The seeded non-empty prior history yields a finite confirmation threshold, so CLOSED 2.1A actually
  confirms swings.
- `_market_rich(n)` — deterministic staircase (rise legs + deep higher-low pullbacks). A function of
  index only, so a shorter prefix is byte-identical to the same-length prefix of a longer build.
- `_rich_sealed`, `_rich_surface` — helpers building the Stage 4B-1 surface over the rich fixture.

Added 7 tests:
1. `test_rich_fixture_produces_real_confirmed_swings` — asserts ≥1 confirmed HIGH and LOW swing, and
   ≥1 with origin < confirmation.
2. `test_confirmed_swing_not_visible_before_availability` — asserts no early confirmation leak before
   confirmation, visible at confirmation, origin preserved.
3. `test_sequence_fact_absent_before_row_visible_at_row` — asserts a real HH/HL/… classification absent
   before its row, present at it.
4. `test_structural_break_absent_before_row_visible_at_row` — asserts a real BOS_UP (with
   `structure_state_before == UP_STRUCTURE`) absent before its row, present at it.
5. `test_non_vacuous_real_chain_prefix_invariance` — requires real swings + sequence + break through T,
   then asserts prefix equality under future extension.
6. `test_future_extension_preserves_real_events` — asserts prefix hash equality AND concrete
   swing/origin/confirmation/sequence/break/state columns identical through T.
7. `test_real_chain_reconstruction_matches_direct_engines` — asserts every 4B-1 derived column equals
   directly running the real CLOSED 2.1A→2.1B→2.1C chain.

## 3. Proof the fixture produces real events (empirically verified)

```
n=50: swing H=7 L=6 | sequence HH=6, HL=5 | breaks BOS_UP=5, UNCLASSIFIED_BREAK=1
n=70: swing H=7 L=7 | sequence HH=6, HL=6 | breaks BOS_UP=6, UNCLASSIFIED_BREAK=1
```

- Real confirmed swings with `origin_position < confirmation_position` (e.g. HIGH swing at pos=5,
  origin=3, confirmation=5).
- Real 2.1B sequence facts (HH, HL — non-neutral).
- Real 2.1C structural break `BOS_UP` with `structure_state_before == UP_STRUCTURE`.

A real BOS_UP structural break WAS generated under the legal CLOSED contract (seeded
EmpiricalConfirmationPolicy + staircase market), so no STOP was required and no fake frame was used.

## 4. Test results

| Metric | Value |
| --- | --- |
| Stage 4B-1 dedicated tests | **37** (30 prior + 7 new) |
| Total collected | **927** |
| Total passed | **927** (4m17s) |

## 5. Integrity

- `sha256sum -c MANIFEST.sha256` → **162 / 162 OK** (MANIFEST unchanged during PATCH).
- Production source SHA-256 unchanged: `bc393fe4ffb8dec9bdb16e4ae8e0036f22faefdecc8dc67345a5a881207bb708`.
- New test SHA-256: `7e0c572d56074775b807278485a31a02ed6a6ec8e5bc941c638c586e2a401271`.

## 6. Unresolved limitations

None. The regression suite now exercises the real CLOSED chain with real structural events, so the
causality/prefix guarantees are non-vacuous.

## 7. Final status

```
PATCHED / IMPLEMENTED — PENDING RE-AUDIT
```

Not an Independent Audit. Not ACCEPTED. Not CLOSED. Stage 4B-2 and Stage 4C not started.
RESEARCH-DEBT-020 … 025 remain OPEN.

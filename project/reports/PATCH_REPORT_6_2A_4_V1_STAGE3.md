# Patch Report — Module 6.2A-4 V1 Stage 3 (BLOCKER remediation)

**Terminal / Censor Snapshots & As-Of Censor Series**

Date: 2026-08-18
Task Type: PATCH ONLY
Role: Builder (NOT an Independent Audit — this patch report is not independent acceptance)
Final status: **PATCHED / IMPLEMENTED — PENDING AUDIT**

---

## 1. Findings accepted

Two self-audit BLOCKERs were accepted as valid patch findings. This report implements their remediation
exactly as scoped. This is NOT an Independent Audit and must not be recorded as independent acceptance.

## 2. Exact code changes

File: `src/trading_system/research/trajectory/trajectory_stage3.py` (Stage 3 only — no CLOSED file touched)

1. **Imports**: added `ObservationEnvelope` (from `trajectory_contract`) and `build_stage2_trajectory`
   (from CLOSED `trajectory_stage2`).
2. **New `_verify_envelopes_belong_to_context(envelopes, *, timeline, anchor, interval)`** — for EVERY
   envelope: (a) call CLOSED `envelope.verify()`; (b) require exact match of `timeline_id`,
   `timeline_hash`, `anchor_hash`, `interval_id` against the expected Stage 3 context. Rejects on first
   mismatch (`TrajectoryDataError`). No silent filtering, no first-envelope-only check.
3. **New `_verified_stage2_prefix(...)`** — replaces the bare `_stage2_trajectory_prefix_hash(stage2_result)`
   call in both builders. It (a) verifies every supplied envelope belongs to context (BLOCKER 1);
   (b) reconstructs the authoritative Stage 2 result via CLOSED `build_stage2_trajectory(...)` from the
   EXACT bound inputs (timeline/anchor/adapter/market_history/interval/swing_policy/lifecycle_ledger);
   (c) verifies every reconstructed envelope belongs to context; (d) requires the supplied result to
   match the reconstruction on canonical trajectory-prefix hash, envelope count, and lifecycle terminal
   position/state. Rejects on any mismatch. No fallback.
4. **Removed dead code** (the unused `stage2_interval_id` extraction and the literal `pass` "check").
5. **Docstring** updated to document the BLOCKER patch and the accepted performance debt.

The pre-existing Stage-2-vs-6.2A-1 consistency check (from the prior BUILD pass) was retained as
defense-in-depth. It is now subsumed by the stronger reconstruction check (reconstruction guarantees
supplied == reconstructed == 6.2A-1 terminal via origin extraction), but it remains harmless and
documents the authority relationship.

## 3. Tests added (8)

`tests/test_trajectory_stage3.py` (Stage 3 test file only — no existing test was modified in behaviour):

| Test | Covers |
| --- | --- |
| `test_blocker1_cross_timeline_forgery_rejected` | supplied Stage 2 from timeline B, Stage 3 under timeline A → reject |
| `test_blocker1_cross_anchor_forgery_rejected` | supplied Stage 2 under a different anchor → `anchor_hash mismatch` |
| `test_blocker1_cross_interval_forgery_rejected` | supplied Stage 2 over a different interval → `interval_id mismatch` |
| `test_blocker1_empty_envelope_forgery_rejected` | empty `all_envelopes` forgery → reconstruction count mismatch |
| `test_blocker2_policy_a_vs_b_rejected` | supplied under policy A (q=0.3), claimed policy B (q=0.95) → reject |
| `test_blocker2_policy_matching_accepted` | policy A == A → accepted (happy path) |
| `test_blocker2_ledger_terminal_state_mismatch_rejected` | ledger A (CONTRADICTED) vs B (SUPERSEDED) → reject |
| `test_blocker2_ignored_ledger_field_not_falsely_rejected` | field Stage 2 ignores (trigger_relationship_id) → correctly NOT rejected |

Two existing Stage 3 tests (`test_terminal_state_mismatch_vs_stage2_rejection`,
`test_terminal_position_mismatch_vs_stage2_rejection`) had their `match` patterns updated to the new
rejection messages (reconstruction now fires first); their assertions (reject on mismatch) are unchanged.
The `_Policy` test helper gained a `create_runtime()` delegating to CLOSED `EmpiricalConfirmationPolicy`
so reconstruction can consume it — no test semantics changed.

## 4. Before / after hashes

```
trajectory_stage3.py  BEFORE patch  74d1552fd5d7e729393af6ea1a3d20c842146ff6f972b186f243a80ef797b483
                      AFTER  patch  768a8a915dcde795bade03c01da4ef6769d56ce7fce56509215388b3a9446c92

test_trajectory_stage3.py  BEFORE   ca6e894a16cd1bebabd9cda791e8dd6cfefc2b4ecd306ab4ebc497d66ac87d26
                           AFTER    b18c16524ca8ec90640b411c161f3c03a71b38570772d645bf26d313a36cc61e
```

## 5. Test counts

| Metric | Value |
| --- | --- |
| Stage 3 dedicated tests | **74** (66 prior + 8 new) — all pass |
| Total collected | **811** |
| Total passed | **811** (3m35s) |

## 6. Proof CLOSED files unchanged

- `sha256sum -c MANIFEST.sha256` → **154 / 154 OK** (no FAILED line).
- Stage 2 accepted hashes re-verified:
  - `trajectory_stage2.py` `827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f` ✓
  - `test_trajectory_stage2.py` `bb5372fbad3582ce81d64b5d791b3599504b4ee12775767f77d93763f9bb1c6d` ✓
- No `__init__.py`, no CLOSED production module, no existing test modified; MANIFEST not updated.

## 7. Adversarial results (executed, not assumed)

| Attack | Result |
| --- | --- |
| Cross-timeline forged Stage 2 result | REJECTED — `envelope timeline_id mismatch` |
| Cross-anchor forged Stage 2 result | REJECTED — `anchor_hash mismatch` |
| Cross-interval forged Stage 2 result | REJECTED — `interval_id mismatch` |
| Empty-envelope forgery | REJECTED — `envelope count mismatch` |
| Policy A (built) vs policy B (claimed) — materially different structure trajectories | REJECTED — `envelope count mismatch` (10 vs 8) |
| Policy A == A | ACCEPTED (correct) |
| Ledger terminal-state mismatch (CONTRADICTED vs SUPERSEDED) | REJECTED |
| Ledger field Stage 2 ignores (trigger_relationship_id) | ACCEPTED (correct — not a false rejection) |

## 8. Reconstruction causal boundary

The reconstruction calls CLOSED `build_stage2_trajectory`, which internally truncates `market_history`
to the interval end (verified at `trajectory_stage2.py` lines ~437–446: `market_prefix = market_history.iloc[: end_pos + 1]`).
For mature terminal the reconstruction ends at terminal factual availability; for right-censored it ends
at the requested as-of boundary. No future rows are passed to Stage 2; CLOSED prefix semantics preserved.
No double-authority: 6.2A-1 remains authoritative for mature/censored/factual_outcome_id/terminal
state+position/research_snapshot_id; reconstruction only proves the supplied trajectory matches the
claimed inputs.

## 9. Performance debt introduced

Re-running `build_stage2_trajectory` per snapshot is O(Stage 2) extra work per Stage 3 snapshot. This is
accepted for Stage 3 V1 research correctness. No caches were added. Documented in the module docstring
and here as performance debt.

## 10. Unresolved provenance limitation

None remaining within the two BLOCKERs. The reconstruction proves the supplied trajectory is consistent
with the bound inputs to the full depth of CLOSED Stage 2's public semantics. (By construction, a ledger
or policy field that CLOSED Stage 2 does not consume cannot change the trajectory, and is therefore
correctly not treated as a provenance breach — see the `..._not_falsely_rejected` test.)

## 11. Final status

```
PATCHED / IMPLEMENTED — PENDING AUDIT
```

Do NOT call this an Independent Audit. Do NOT declare ACCEPTED. Do NOT declare CLOSED. Stage 4 not started.
RESEARCH-DEBT-020 … 025 remain OPEN.

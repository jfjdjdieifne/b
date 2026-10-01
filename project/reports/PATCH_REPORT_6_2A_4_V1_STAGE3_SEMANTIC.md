# Patch Report — Stage 3 Provenance-Semantics Remediation

**Module 6.2A-4 V1 Stage 3 — Terminal / Censor Snapshots & As-Of Censor Series**

Date: 2026-08-18
Task Type: PATCH ONLY (semantic remediation of the provenance BLOCKER identified by contract/semantic opinion)
Role: Builder (NOT an Independent Audit)
Final status: **PATCHED / IMPLEMENTED — PENDING AUDIT**

---

## 1. What this patch addresses

A contract/semantic opinion identified a provenance BLOCKER in the prior PATCH: Stage 3 was
recording the caller-supplied lifecycle-ledger identity (`lifecycle_ledger_seal`) and its
row-level fields (`trigger_relationship_id`, etc.) as if they were the **historical generating
input** of the supplied Stage 2 trajectory. Because CLOSED Stage 2 reads `trigger_relationship_id`
into `lifecycle_events` rows (trajectory_stage2.py line 786) but does NOT include it in the
observation-envelope identity (trajectory_contract.py), two ledgers A and B that differ only in
that field are trajectory-equivalent yet carry different row-level provenance. Recording B as the
generating input of an artifact actually produced from A was a false-provenance claim — and the
snapshot's B-valued `trigger_relationship_id` contradicted the artifact's own embedded A values.

The opinion's facts were independently verified against the code before patching:
- FACT 1 confirmed: `build_lifecycle_trajectory` writes `trigger_relationship_id` (line 786) and
  `superseded_by_hypothesis_id` (line 787) into `lifecycle_events`.
- FACT 2 confirmed: `ObservationEnvelope` (trajectory_contract.py) contains NO
  `trigger_relationship_id` field.

## 2. Exact code changes (Stage 3 file only — no CLOSED module touched)

File: `src/trading_system/research/trajectory/trajectory_stage3.py`

1. **Origin provenance now comes from the SUPPLIED artifact, not the caller ledger.**
   `build_mature_terminal_snapshot` now extracts `terminal_origin_position`,
   `terminal_ledger_event_id`, `trigger_relationship_id`, `superseded_by_hypothesis_id` from
   `stage2_result.lifecycle.lifecycle_events` (the supplied trajectory's own embedded rows).
   The caller's `lifecycle_ledger` is no longer the source of origin fields.
   Ordering change: origin extraction was moved to AFTER `_verified_stage2_prefix`, so it operates
   on a verified (deterministic-equivalent) artifact and forgery rejections keep their precise
   envelope/prefix errors.

2. **Derivation-witness semantics (renames).**
   - `swing_policy_hash` → `reconstruction_swing_policy_hash`
   - `lifecycle_ledger_seal` → `reconstruction_ledger_seal`
   - `stage2_input_binding_hash` → `stage2_reconstruction_binding_hash`
   - `_stage2_input_binding_hash` → `_stage2_reconstruction_binding_hash`
   - hash domains: `SWING_POLICY_INPUT_BINDING_V1` → `SWING_POLICY_RECONSTRUCTION_BINDING_V1`,
     `HYPOTHESIS_LIFECYCLE_LEDGER_INPUT_BINDING_V1` → `HYPOTHESIS_LIFECYCLE_LEDGER_RECONSTRUCTION_BINDING_V1`,
     `STAGE2_INPUT_BINDING_V1` → `STAGE2_RECONSTRUCTION_BINDING_V1`.
   All docstrings now state these are DERIVATION WITNESSES ("reproduces the supplied trajectory
   under CLOSED Stage 2"), never assertions of historical generating-input identity.

3. **Manifest** updated: `BINDING/STAGE2` row reflects the renamed identities, plus a new
   `BINDING/STAGE2_DERIVATION_WITNESS` row declaring the derivation-witness semantics.

## 3. Tests changed / added

`tests/test_trajectory_stage3.py`:

- `test_blocker2_ignored_ledger_field_not_falsely_rejected` was RENAMED and RE-SPECIFIED to
  `test_blocker2_derivation_witness_not_input_provenance`. It now asserts the correct semantics:
  - `snap.trigger_relationship_id == 2` (the SUPPLIED artifact's value from ledger A, NOT the
    caller ledger B's 999);
  - `snap.reconstruction_ledger_seal == hash(B)` (derivation witness);
  - `snap.reconstruction_ledger_seal != hash(A)`.
- `test_swing_policy_binding_affects_snapshot_identity` updated for the renamed field
  (`reconstruction_swing_policy_hash`).

Test count unchanged at 74 (66 original + 8 from the prior PATCH; one test re-specified, no net add).

## 4. Before / after hashes

```
trajectory_stage3.py   (prior PATCH)  768a8a915dcde795bade03c01da4ef6769d56ce7fce56509215388b3a9446c92
                       (this PATCH)   f99296314deef462495ffe6b276ed3f429f30b6d7da27b7055e10c2b6fb4fbf0

test_trajectory_stage3.py  (prior PATCH)  b18c16524ca8ec90640b411c161f3c03a71b38570772d645bf26d313a36cc61e
                           (this PATCH)   eb645ddc969018b3f79250eff3ac8b42c62d1c1f8fca8e3eb0e3257e386bf6ab
```

## 5. Test counts

| Metric | Value |
| --- | --- |
| Stage 3 dedicated tests | 74 / 74 pass |
| Total collected | 811 |
| Total passed | 811 (3m39s) |

## 6. Proof CLOSED files unchanged

- `sha256sum -c MANIFEST.sha256` → **154 / 154 OK** (no FAILED line).
- Stage 2 accepted hashes re-verified:
  - `trajectory_stage2.py` `827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f` ✓
  - `test_trajectory_stage2.py` `bb5372fbad3582ce81d64b5d791b3599504b4ee12775767f77d93763f9bb1c6d` ✓
- No `__init__.py`, no CLOSED production module, no existing (non-Stage-3) test modified; MANIFEST not updated.

## 7. Adversarial results (executed)

| Case | Result |
| --- | --- |
| Ledger A (built) vs ledger B (claimed), differing only in `trigger_relationship_id` (ignored by envelope identity) | ACCEPTED as deterministic-equivalence, BUT `snap.trigger_relationship_id == 2` (A's value from the supplied artifact), `reconstruction_ledger_seal == hash(B)` — no false provenance |
| Cross-timeline forged Stage 2 | REJECTED — `envelope timeline_id mismatch` |
| Cross-anchor forged Stage 2 | REJECTED — `anchor_hash mismatch` |
| Cross-interval forged Stage 2 | REJECTED — `interval_id mismatch` |
| Empty-envelope forgery | REJECTED — `envelope count mismatch` |
| Policy A (built) vs policy B (claimed), materially different trajectories | REJECTED — `envelope count mismatch` |
| Ledger terminal-state mismatch (CONTRADICTED vs SUPERSEDED) | REJECTED — `trajectory prefix mismatch` |

## 8. Semantic boundary now enforced (and documented)

- **What Stage 3 claims about the supplied trajectory**: deterministic equivalence to the result
  reconstructed from the bound `swing_policy` + `lifecycle_ledger` under CLOSED Stage 2
  (derivation witness). Provable from the artifact.
- **What Stage 3 does NOT claim**: the historical generating-input identity of the supplied
  trajectory. CLOSED Stage 2 does not seal input identity, so this is unverifiable today.
- **Origin provenance** (trigger_relationship_id, superseded_by_hypothesis_id, ledger_event_id,
  origin position) is taken from the SUPPLIED artifact's own embedded lifecycle_events, so it is
  always consistent with the trajectory being snapshotted.

If exact historical input provenance becomes a Stage 3 requirement, that is a contract-version
change (the opinion's option C) — e.g. CLOSED Stage 2 sealing input-identity, or explicit
`INPUT_PROVENANCE_UNVERIFIABLE` + separate `DERIVATION_WITNESS` fields. Out of scope for this patch.

## 9. Performance debt

Unchanged from the prior PATCH: reconstruction re-runs Stage 2 per snapshot (O(Stage 2) extra).
No caches. Accepted for Stage 3 V1; documented.

## 10. Final status

```
PATCHED / IMPLEMENTED — PENDING AUDIT
```

Not an Independent Audit. Not ACCEPTED. Not CLOSED. Stage 4 not started.
RESEARCH-DEBT-020 … 025 remain OPEN.

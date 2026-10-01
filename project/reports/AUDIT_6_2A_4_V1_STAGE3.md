# Independent Audit Report — Module 6.2A-4 V1 Stage 3

**Terminal / Censor Snapshots & As-Of Censor Series**

Date: 2026-08-18
Role: Independent Auditor (read-only — did not build this artifact, did not trust the Builder report)
Verdict: **PATCH REQUIRED**

---

## 0. Artifact Gate — PASS

```
sha256sum src/trading_system/research/trajectory/trajectory_stage3.py
  74d1552fd5d7e729393af6ea1a3d20c842146ff6f972b186f243a80ef797b483  == EXPECTED ✓

sha256sum tests/test_trajectory_stage3.py
  ca6e894a16cd1bebabd9cda791e8dd6cfefc2b4ecd306ab4ebc497d66ac87d26  == EXPECTED ✓

sha256sum -c MANIFEST.sha256
  154 / 154 OK ✓  (no FAILED line)

Stage 2 accepted hashes (re-verified):
  trajectory_stage2.py  827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f  ✓
  test_trajectory_stage2.py  bb5372fbad3582ce81d64b5d791b3599504b4ee12775767f77d93763f9bb1c6d  ✓
```

Artifacts match the claimed baseline. Proceeding to semantic audit of the ENTIRE file.

## 1. Tests (independently run)

```
pytest --collect-only -q        -> 803 collected
pytest tests/test_trajectory_stage3.py -q  -> 66 passed
pytest -q                      -> 803 passed (3m27s)
```

Green tests are NOT accepted as proof — see §15 test gaps and the two BLOCKERs below.

## 2. COMPLIANT areas (verified against CLOSED contracts, not Builder claims)

- **§2 Authority**: 6.2A-1 is authoritative for mature/censored/factual_outcome_id/research_snapshot_id/
  terminal state/terminal position. Stage 3 does not re-derive these from price or raw ledger.
  Missing/ambiguous/hash-mismatch/timeline-mismatch inputs are rejected (verified by re-running the probes).
- **§3 Censor semantics**: `_RIGHT_CENSORED_TYPE == "RIGHT_CENSORED_AS_OF_BOUNDARY"` exactly matches CLOSED
  6.2A-1 `RIGHT_CENSORING_TYPE`. No invented censor taxonomy.
- **§4 Two-clock**: `research_as_of_key < terminal_factual_available_at_key` uses `InformationKey.__lt__`,
  which compares `(bar_position, phase_rank, deterministic_sequence)` — full key semantics, not bar_position only.
- **§5 Origin**: `terminal_origin_position` is preserved as `int(event_position)` from the ledger; the only
  InformationKeys are the availability/as-of clocks. No manufactured origin InformationKey.
- **§6 Swing-policy binding**: binds quantile + both prior sequences + version; NaN/Inf rejected; +0/-0 distinct
  via float hex. `EmpiricalConfirmationPolicy` has exactly these 3 public fields — no consumed field is omitted.
- **§7 Ledger schema**: canonical 10 columns exactly match CLOSED 6.1B `_HYPOTHESIS_LEDGER_COLUMNS`; empty ledger
  uses the same zero-row schema/path; row/column order canonicalized; >2^53 exact; duplicate columns rejected.
- **§10 Compact storage**: snapshot dataclasses hold only hashes/counts/references — no raw market, no envelope
  tuple, no running payloads, no path segments.
- **§11 Immutability**: frozen dataclasses + tuple series; A→A / A→B→A / fresh-instance verified.
- **§12 Information time**: positional + time-indexed (TZ-aware, DST) verified.
- **§13 / §14**: no eligibility redefinition, no Stage 4 domains, firewall clean (no live module imports Stage 3).

## 3. BLOCKER 1 — False binding: forged Stage 2 result accepted (§8)

**Invariant violated**: the trajectory-prefix hash and envelope count must bind envelopes that belong to the
expected timeline / anchor / interval. The Builder report claims the snapshot binds the Stage 2 trajectory
"being snapshotted".

**Evidence (file/line)**:
- `_stage2_trajectory_prefix_hash` (lines 219–241) hashes `stage2_result.all_envelopes` with NO check that
  these envelopes belong to the caller-supplied timeline/anchor/interval.
- Lines 550–557: `stage2_interval_id` is extracted from the first envelope but **never compared** to
  `interval_through_terminal.interval_id`; the "check" is a literal `pass`.
- Lines 571–592: the only Stage 2 cross-check is `lifecycle.terminal_position/terminal_state` vs 6.2A-1 —
  it never touches envelope provenance.
- `envelope.verify()` (trajectory_contract.py) is never invoked on the supplied Stage 2 envelopes, and even if it
  were, it only checks an envelope's *internal* self-consistency, not that it belongs to the expected interval.

**Adversarial probe (executed)**:
- Built a real Stage 2 result on timeline `atk_B`; called `build_mature_terminal_snapshot` with timeline/anchor/
  interval from `atk_A` but `stage2_result_through_terminal = stage2_B`. Result: **ACCEPTED**. The returned
  snapshot claims `timeline_id == "atk_A"` while its `stage2_trajectory_prefix_hash` is computed over envelopes
  bound to `atk_B`.

This is a false-binding/provenance failure: a snapshot can claim timeline/anchor/interval A while its trajectory
prefix is the trajectory of a different timeline. Classified BLOCKER per §16 ("false binding/provenance").

## 4. BLOCKER 2 — False provenance: Stage 2 result built from different inputs is accepted (§9)

**Invariant violated**: the snapshot's `swing_policy_hash` and `lifecycle_ledger_seal` must prove the bound
Stage 2 result was actually produced from that policy / that ledger.

**Evidence (file/line)**:
- `TrajectoryStage2Result` (trajectory_stage2.py lines 809–814) carries ONLY `price / structure / lifecycle /
  all_envelopes`. It exposes **no input provenance** (no swing-policy hash, no ledger seal, no input binding).
- Stage 3 computes `swing_policy_hash` and `lifecycle_ledger_seal` purely from caller-supplied inputs
  (lines 560–568) with **no link** to the supplied `stage2_result`. The consistency check (lines 571–592) only
  compares terminal position/state, which can coincide even when the consumed ledger/policy differ materially.

**Adversarial probes (executed)**:
- Ledger: Stage 2 built from ledger A (terminal `trigger_relationship_id = 2`); Stage 3 called with ledger B
  (same terminal position/state but `trigger_relationship_id = 999`). Result: **ACCEPTED**. Snapshot records
  `trigger_relationship_id = 999` (from B) while its `lifecycle_ledger_seal` = hash(B), yet the Stage 2 lifecycle
  envelope was produced from A. Material provenance contradiction, undetected.
- Swing policy: Stage 2 built under `EmpiricalConfirmationPolicy(quantile=0.5)`; Stage 3 called with
  `quantile=0.9`. Result: **ACCEPTED**. Snapshot's `swing_policy_hash` binds 0.9 while the Stage 2 structure
  trajectory was generated under 0.5.

Classified BLOCKER per §16 ("accepting a Stage 2 result produced from different material inputs while claiming
current bindings").

## 5. Remaining test gaps (§15)

The 66-test suite is thorough on scope, but contains NO test for the two BLOCKERs:
- no test supplies a Stage 2 result whose envelopes come from a different interval/anchor/timeline;
- no test supplies a Stage 2 result built from ledger A / policy A while binding ledger B / policy B.

Several tests are string/type inspections (firewall grep, `no_stage4_domains`, `no_win_loss_...` field regex,
`no_manufactured_origin_information_key`). These are legitimate scope guards but do not exercise the binding
semantics where the failures live.

## 6. Non-blocking debt

- Lines 550–557 contain dead code (`stage2_interval_id` unused) that should be replaced by real verification.
- `_canonicalize_swing_policy` does not verify the object is actually a `SwingConfirmationPolicy` /
  `EmpiricalConfirmationPolicy`; it duck-types `quantile` + prior attributes and hardcodes
  `"type": "empirical_confirmation_policy"`. Fine for the current single CLOSED policy; fragile if a second
  policy type is added later.
- `_canonicalize_swing_policy` checks finiteness but not the policy's non-negative-prior invariant (the real
  policy enforces it at construction, so valid instances are unaffected).

## 7. Smallest safe patch scope (NOT performed — read-only)

Both BLOCKERs are false-binding/provenance defects with a well-scoped fix; no contract redesign is required.

1. **Close BLOCKER 1** (Stage-3-local, no CLOSED change): in `_stage2_trajectory_prefix_hash` (or the builder),
   verify every envelope in `stage2_result.all_envelopes` satisfies
   `envelope.interval_id == interval.interval_id`, `envelope.timeline_id == timeline.timeline_id`,
   `envelope.timeline_hash == timeline.timeline_hash`, `envelope.anchor_hash == anchor.anchor_hash`, and call
   `envelope.verify()`. Reject (`TrajectoryDataError`) on any mismatch.

2. **Close BLOCKER 2** (needs a Product-Owner decision between two options):
   - **(a) CLOSED-touching**: add input provenance (swing-policy binding hash + ledger seal + input-binding hash)
     to `TrajectoryStage2Result`. Cleanest, but modifies a CLOSED module → requires explicit versioned PATCH
     authorization.
   - **(b) Stage-3-local**: recompute `build_stage2_trajectory(timeline, anchor, interval, swing_policy,
     lifecycle_ledger)` inside Stage 3 and verify the supplied result's trajectory-prefix hash matches before
     binding. Closes both BLOCKERs without touching CLOSED Stage 2, at the cost of re-running Stage 2.

The auditor does not select the option; that is the Closure Authority's call.

## 8. Final verdict

```
PATCH REQUIRED
```

Two BLOCKERs (false binding / false provenance). All other audited invariants — authority, censor semantics,
two-clock, origin, input-binding canonicalization, compact storage, immutability, information time, firewall —
are compliant. Stage 3 must not be CLOSED until both BLOCKERs are patched and re-audited.

Stage 4 was not started. No debt (RESEARCH-DEBT-020…025) is affected; all remain OPEN.

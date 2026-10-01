# Builder Report — Module 6.2A-4 V1 Stage 4B-1

**Shared Causal Structure Surface**

Date: 2026-08-21
Task Type: BUILD ONLY
Status: **IMPLEMENTED — PENDING AUDIT** (not ACCEPTED, not CLOSED)

---

## 1. Files created

| File | Action |
| --- | --- |
| `src/trading_system/research/trajectory/trajectory_stage4b1.py` | CREATED |
| `tests/test_trajectory_stage4b1.py` | CREATED |

No CLOSED module, test, or MANIFEST entry was modified.

## 2. SHA-256

```
trajectory_stage4b1.py   bc393fe4ffb8dec9bdb16e4ae8e0036f22faefdecc8dc67345a5a881207bb708
test_trajectory_stage4b1.py  59e687935a9c7348fa5e67a7a8b661ebf834c500717ab25ee352fb01e979473a
```

## 3. CLOSED contracts consumed (public APIs only)

- `CausalAdaptiveSwingDetector(confirmation_policy=...).analyze(df, high_col, low_col)` — 2.1A.
- `ConfirmedSwingSequenceEngine().analyze(df)` — 2.1B.
- `CausalStructuralBreakEngine().analyze(df)` — 2.1C.
- `MarketObservationTimeline`, `TIMELINE_ADAPTER_KIND`, adapters, `InformationKey` — Stage 1.

## 4. Exact public schemas actually bound

- **2.1A**: 24 derived columns (candidate_*, swing_*).
- **2.1B**: 9 derived columns (structure_event_type, swing_sequence_class, comparison_available, …).
- **2.1C**: **33** derived columns (monitored_*, breach events, overshoots, evidence, history counts,
  structure_state_before/after, structural_break_event).

**Build-time discovery note**: the design patch stated "34" for 2.1C; the authoritative working tree
has **33** (the field list is identical — a documentation miscount, not a schema divergence). The
dynamic column detection (`_new_columns`) matched the mirrored schema exactly, so no BLOCKER arose.

## 5. Identity design implemented

- `STAGE4B1_STRUCTURE_2_1A/2_1B/2_1C_PUBLIC_RESULT_V1` — component hashes over each stage's complete
  derived result.
- `STAGE4B1_STRUCTURE_COMPLETE_RESULT_V1` — complete public-result hash over all 66 derived columns.
- `STAGE4B1_SURFACE_IDENTITY_V1` — composed surface_id (domain + contract version + timeline +
  adapter_kind + high/low col + swing_policy_hash + reconstruction_input_hash + 3 component hashes +
  public_result_hash).
- `STAGE4B1_RECONSTRUCTION_INPUT_BINDING_V1` — reconstruction witness (timeline + column config +
  swing-policy hash + the 3 CLOSED contract versions).
- `STAGE4B1_PREFIX_IDENTITY_V1` — compact prefix identity through boundary T.

All identities are DETERMINISTIC RECONSTRUCTION / DERIVATION WITNESSES. Historical generating-input
provenance is NOT_CERTIFIED / UNVERIFIABLE (CLOSED engines do not seal input identity).

## 6. Availability semantics implemented

- Origin is NEVER used as factual availability. The surface is per-bar (row i = facts at bar i);
  projection is keyed ONLY by the boundary `InformationKey.bar_position`.
- Origin fields (`swing_origin_position`, `candidate_origin_position`, monitored *_origin_position)
  are preserved as positional `Int64` data, never InformationKeys.
- Legal availability phase = `COMPLETED_ROW_AVAILABLE` (or `RESEARCH_SNAPSHOT_AVAILABLE` as a legal
  projection/as-of boundary — NOT the market fact's original availability time).

## 7. Prefix semantics

- Full-surface identity changes on legal future append.
- Prefix identity through T is immutable: an independently rebuilt future-extended surface produces
  an equal prefix through T (verified on the REAL CLOSED chain — see §8).
- Mutation at/before T changes/rejects the prefix (self-integrity). Mutation after T also rejects
  (whole-surface integrity is broken, so re-projection rejects).

## 8. Real-chain prefix-invariance result

```
Independently rebuilt prefix (24-bar) vs future-extended (40-bar) over the REAL 2.1A→2.1B→2.1C chain:
complete factual structure prefix through T=20  ->  EQUAL  (p.equals(p2) == True)
```

No BLOCKER. The CLOSED chain is prefix-invariant for all derived columns through the boundary.

## 9. Self-integrity mechanism

`verify_surface_integrity(surface)` recomputes the three component hashes + complete public-result
hash + surface_id from CURRENT `frame` content and rejects on any stale/forged field (hash, surface_id,
adapter_kind, derived-column schema). Defensive deep copy at the construction boundary. Called before
`project_structure_prefix`, `verify_surface_matches_reconstruction`, and any content consumption.

## 10. Test results

| Metric | Value |
| --- | --- |
| Stage 4B-1 dedicated tests | **30** |
| Total collected | **920** |
| Total passed | **920** (3m53s) |

## 11. MANIFEST / CLOSED integrity

- `sha256sum -c MANIFEST.sha256` → **162 / 162 OK** (no FAILED line). MANIFEST not updated during BUILD.
- Stage 2/3/4A accepted hashes re-verified unchanged:
  - `trajectory_stage2.py` `827ddf9b…`, `trajectory_stage3.py` `e79a61cf…`, `trajectory_stage4a.py` `19034dff…`.

## 12. BLOCKERS

None.

## 13. NON-BLOCKING DEBT

- `candidate_side` is `object` dtype in CLOSED 2.1A (plain strings); canonical hashing handles it
  deterministically (verified by A→A determinism test). Documented, not a defect.
- Structure-chain reconstruction is O(N) per surface build (accepted for V1 correctness; no cache).

## 14. Final status

```
IMPLEMENTED — PENDING AUDIT
```

Do NOT declare ACCEPTED. Do NOT declare CLOSED. Stage 4B-2 and Stage 4C not started.
RESEARCH-DEBT-020 … 025 remain OPEN.

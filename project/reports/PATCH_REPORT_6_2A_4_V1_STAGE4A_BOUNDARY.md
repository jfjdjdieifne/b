# Patch Report — Module 6.2A-4 V1 Stage 4A (boundary InformationKey legality BLOCKER)

**Shared Per-Bar Market-State Trajectory**

Date: 2026-08-21
Task Type: PATCH ONLY
Role: Builder (NOT an Independent Audit)
Final status: **PATCHED / IMPLEMENTED — PENDING AUDIT**

---

## 1. Confirmed blocker (accepted)

`project_surface_prefix` used only `boundary_key.bar_position`, without enforcing that the
InformationKey is legally consistent with completed-bar availability. `BAR_PRE_CLOSE` at T (or a
fabricated `event_time_utc` at the correct bar position) could expose completed-bar Stage 4A facts
for row T — an information-time / look-ahead violation.

## 2. Exact code changes (Stage 4A file only — no CLOSED module touched)

File: `src/trading_system/research/trajectory/trajectory_stage4a.py`

1. **`adapter_kind` field** added to `Stage4ADomainSurface`; bound from `timeline.adapter_kind` in
   `_assemble_surface`, included in the `surface_id` identity hash and verified in
   `verify_surface_integrity` (so changing adapter kind breaks surface identity).
2. **`_LEGAL_BOUNDARY_PHASES`** = `{COMPLETED_ROW_AVAILABLE, RESEARCH_SNAPSHOT_AVAILABLE}` (mirrors
   CLOSED `bind_interval`).
3. **`_reconstruct_adapter(surface)`** (new): rebuilds the authoritative CLOSED adapter from
   `adapter_kind` + `timeline_id`.
4. **`project_surface_prefix`** now, in order: (a) `verify_surface_integrity`; (b) reject any
   boundary phase not in `_LEGAL_BOUNDARY_PHASES` with `TrajectoryContractError`; (c) validate the
   COMPLETE key via `adapter.validate_key(boundary_key, surface.surface.index)` (which enforces
   timeline_id, bar_position range, and event_time_utc correctness per CLOSED adapter semantics);
   (d) then proceed with the prefix projection.

No other Stage 4A behavior changed; the previous self-integrity BLOCKER fix is fully retained.

## 3. Final Stage 4A boundary InformationKey contract

- Legal phases: `COMPLETED_ROW_AVAILABLE`, `RESEARCH_SNAPSHOT_AVAILABLE`. `BAR_PRE_CLOSE` (and any
  other phase) → `TrajectoryContractError` "not legally observable". No T→T-1 silent projection.
- The complete key is validated against the surface's authoritative index using the CLOSED adapter:
  - Positional: `event_time_utc` must be `None` (fabricated timestamp rejected).
  - Time-indexed: `event_time_utc` must equal `pd.Timestamp(index[bar_position]).tz_convert("UTC")`
    (wrong timestamp or wrong bar_position rejected).
  - Cross-timeline `timeline_id` rejected.
- `deterministic_sequence` is preserved as bookkeeping; the supplied key must simply be a valid
  InformationKey under the CLOSED adapter contract (no forced sequence 0).

## 4. How boundaries are validated

- **Positional**: `PositionalTimelineAdapter.validate_key` → timeline_id match + bar_position in
  range + `event_time_utc is None`.
- **Time-indexed**: `TimeIndexedTimelineAdapter.validate_key` → timeline_id match + bar_position in
  range + `event_time_utc == index[bar_position]` in UTC.
- The authoritative index used is `surface.surface.index`, read only AFTER `verify_surface_integrity`
  has recomputed the public-result hash (which binds the index), so a mutated index cannot be trusted.

## 5. Adapter kind / index identity in the surface contract

Yes — `adapter_kind` was added to `Stage4ADomainSurface`, bound from the CLOSED timeline, and made
part of the surface identity (surface_id hash + integrity verification). The index itself is already
bound via the public-result hash (DataFrame hashing includes the index); no separate index field was
needed.

## 6. New adversarial tests (11)

Boundary phase: `BAR_PRE_CLOSE` rejected; `COMPLETED_ROW_AVAILABLE` accepted;
`RESEARCH_SNAPSHOT_AVAILABLE` accepted. Positional: fabricated timestamp rejected; cross-timeline
rejected. Time-indexed: wrong `event_time_utc` rejected; correct timestamp + wrong bar_position
rejected; wrong timeline rejected; DST-boundary authoritative key accepted; irregular-index
authoritative key accepted. Adapter-kind forgery rejected (breaks surface identity).

## 7. Hashes

```
trajectory_stage4a.py   BEFORE  88bd50639de3acd6d3a29fad4650695952bd696fa01c51d833a2e6036bc0fc98
                        AFTER   19034dfff4ca4007921bdd7b3bd16c8afc5048b3601f2538d02510ba27edc26e

test_trajectory_stage4a.py  BEFORE  7bcb5e0644ae6b90da1921ca28f7f49bccbfe11fadbf3bc087b6029f5a039fea
                            AFTER   7547abfd5cf699badf2fc19b9a295b77aea8b73d0848fa5d12603655b3aa2b7f
```

## 8. Test counts

| Metric | Value |
| --- | --- |
| Stage 4A dedicated tests | **72** (61 prior + 11 new) |
| Total collected | **890** |
| Total passed | **890** (3m47s) |

## 9. CLOSED integrity

- `sha256sum -c MANIFEST.sha256` → **158 / 158 OK** (no FAILED line).
- Stage 3 accepted hashes unchanged:
  - `trajectory_stage3.py` `e79a61cf85ce0ba5cb3dfcd3db63b8fcdbe8d53243bb28855eb0bc91dad2dc8e` ✓
  - `test_trajectory_stage3.py` `2777fd6661847226b91c1294234713e93a1e861d5f6845a164f3e89e523e8d28` ✓

## 10. Previous mutability blocker regression result

All 17 self-integrity / mutability / aliasing tests still pass (61-test prior suite re-run green
before adding the 11 new tests). The boundary patch only tightened `project_surface_prefix`; it did
not weaken `verify_surface_integrity`, absorption upstream verification, output-schema checks,
defensive copying, or complete public-result hashing.

## 11. Unresolved limitations

- The boundary validation relies on the CLOSED adapter `validate_key`, which does not itself check
  `information_phase`; Stage 4A adds the explicit phase gate on top (the same gate `bind_interval`
  applies). No new semantics were invented.
- `deterministic_sequence` is accepted as-is from the supplied key (bookkeeping); Stage 4A does not
  interpret it as market intrabar chronology.
- ACTUAL_AGGRESSOR / ACTUAL absorption remain unsupported; debts 020–025 remain OPEN; Stage 4B/4C
  not started.

## 12. Final status

```
PATCHED / IMPLEMENTED — PENDING AUDIT
```

Not an Independent Audit. Not ACCEPTED. Not CLOSED.

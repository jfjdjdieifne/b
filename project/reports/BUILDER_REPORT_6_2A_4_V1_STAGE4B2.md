# Builder Report — Module 6.2A-4 V1 Stage 4B-2

**Shared Liquidity / Order-Block / FVG / Dealing-Range Entity & Lifecycle Surfaces**

Date: 2026-08-21
Task Type: BUILD ONLY
Status: **IMPLEMENTED — PENDING AUDIT** (not ACCEPTED, not CLOSED)

---

## 1. Files created

| File | Action |
| --- | --- |
| `src/trading_system/research/trajectory/trajectory_stage4b2.py` | CREATED |
| `tests/test_trajectory_stage4b2.py` | CREATED |

No CLOSED module, test, or MANIFEST entry was modified.

## 2. SHA-256

```
trajectory_stage4b2.py   d79c390f754d155c472ce0863580b773739ab814ffb797cc6d508aca39a41ce6
test_trajectory_stage4b2.py  cc7bdb264bef4884a517adb21f5a7c826056b9683746bb7a53bd006a844f4247
```

## 3. Exact four CLOSED schemas actually consumed

- **Liquidity (2.2)** `CausalLiquidityMapEngine.analyze` → `(bar_surface 23 derived cols,
  normalized_events 16 cols)`.
- **Order Block (4.1)** `CausalOrderBlockEngine.analyze` → `(bar_surface 26 derived cols,
  normalized_events 20 cols)`.
- **FVG (4.2A)** `CausalFVGEngine.analyze` → `(bar_surface 27 derived cols, events 22 cols)`.
- **Dealing Range (4.2B)** `CausalDealingRangeEngine.analyze` → `(bar_surface 30 derived cols,
  range_table 17 cols)`.

Derived columns are discovered dynamically from the CLOSED output (never trusted from a copied
design summary); the complete-result hash binds both tables' derived columns per domain.

## 4. Exact passthrough market inputs bound per domain

- Liquidity: `high`, `low`, `close`.
- Order Block: `open`, `high`, `low`, `close`.
- FVG: `open`, `high`, `low`, `close`.
- Dealing Range: `close`.

Each is verified equal to the authoritative sealed `market_history` (exact column equality) BEFORE
domain-engine execution; a mutation inside `structure_surface.frame` to any consumed passthrough
column rejects even when Stage 4B-1 self-integrity passes.

## 5. Stage 4B-1 binding

Liquidity / OB / Dealing Range consume the single supplied CLOSED `Stage4B1StructureSurface`.
Before consumption: `verify_surface_integrity` + timeline identity match + CLOSED timeline verify +
passthrough equality. The CLOSED identity fields (`surface_id`, `timeline_id`, `timeline_hash`,
`adapter_kind`, `contract_version`, `swing_policy_hash`, `reconstruction_input_hash`,
`hash_2_1a/2_1b/2_1c`, `public_result_hash`) are bound into the Stage 4B-2 reconstruction witness /
surface identity. No private 2.1A→2.1B→2.1C reconstruction exists inside Stage 4B-2. FVG is
structure-independent (sealed timeline only).

## 6. Normalized representation derivations

- Liquidity / OB / FVG: normalized entity table derived from `*_CREATED` event rows, carrying only
  fields the CLOSED event exposes, labeled STAGE-4B-2-DERIVED.
- Dealing Range: the original CLOSED range table is used directly as the entity representation.

## 7. Same-batch ambiguity implementation

A derived `same_information_batch_order_unknown` column is added to the normalized event table
(True when ≥2 lifecycle events share the same `event_position`), bound into
`STAGE4B2_NORMALIZED_EVENT_V1`. Mechanical serialization is retained as ordering only, explicitly
NOT intrabar chronology.

## 8. Empirical entity-ID stability result (all four domains)

Using independently rebuilt prefix-through-T (n=70) vs prefix + legal future extension (n=90) over
the REAL CLOSED engines, with a fixed collapse boundary (index-only fixture, prefix-identical):
- Liquidity `level_id`: STABLE ✓ (15 entities through T identical)
- Order Block `zone_id`: STABLE ✓
- FVG `fvg_id`: STABLE ✓
- Dealing Range `range_id`: STABLE ✓

No BLOCKER. Tests first assert real entities exist through T (non-vacuous).

## 9. Non-vacuous lifecycle fixture evidence

The rich fixture (staircase rise + fixed terminal collapse, seeded EmpiricalConfirmationPolicy)
produces real lifecycle events for every domain:
- Liquidity: LEVEL_CREATED + FIRST_TOUCH + FIRST_WICK_BREACH + FIRST_CLOSE_BREACH +
  FIRST_WICK_ONLY_EXCURSION + FIRST_RECLAIM_AFTER_CLOSE_BREACH.
- Order Block: ZONE_CREATED + FIRST_TOUCH + FIRST_FAR_SIDE_WICK_BREACH + FIRST_FAR_SIDE_CLOSE_BREACH.
- FVG: FVG_CREATED + FIRST_TOUCH + FIRST_FULL_RANGE_COVERAGE + FIRST_FAR_SIDE_* + reclaim.
- Dealing Range: real ranges with `range_low/high/width/midpoint`.

## 10. Stage 3 boundary integration

`project_domain_prefix` reuses the CLOSED Stage 4B-1 / Stage 4A boundary legality: legal phases only
(`COMPLETED_ROW_AVAILABLE`, `RESEARCH_SNAPSHOT_AVAILABLE`), `BAR_PRE_CLOSE` rejected, cross-timeline
rejected, positional no-timestamp, fabricated timestamp rejected. Prefix covers the bar-surface
derived columns through the boundary; no post-boundary entity/event/state fact is exposed.

## 11. Self-integrity coverage

`verify_surface_integrity` recomputes from CURRENT content: complete-result hash (bar + event
tables), normalized-entity hash, normalized-event hash, and surface_id; verifies domain, contract
version, timeline, adapter kind, entity-column schema, and rejects stale/forged fields. Historical
generating-input provenance remains NOT_CERTIFIED / UNVERIFIABLE.

## 12. Test results

| Metric | Value |
| --- | --- |
| Stage 4B-2 dedicated tests | **27** |
| Total collected | **954** |
| Total passed | **954** (3m54s) |

## 13. MANIFEST / CLOSED integrity

- `sha256sum -c MANIFEST.sha256` → **166 / 166 OK** (no FAILED line). MANIFEST not updated during BUILD.
- Stage 4B-1 accepted hash unchanged: `bc393fe4ffb8dec9bdb16e4ae8e0036f22faefdecc8dc67345a5a881207bb708`.

## 14. BLOCKERS

None.

## 15. NON-BLOCKING DEBT

- Normalized entity tables are STAGE-4B-2-DERIVED (documented, not original CLOSED tables).
- The four surfaces share a common `Stage4B2DomainSurface` dataclass with a runtime-validated
  `domain` field + per-domain builders (not Python-compile-time type isolation — documented per the
  accepted design-patch correction).

## 16. Final status

```
IMPLEMENTED — PENDING AUDIT
```

Do NOT declare ACCEPTED. Do NOT declare CLOSED. Stage 4C not started.
RESEARCH-DEBT-020 … 025 remain OPEN.

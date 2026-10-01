# Patch Report — Module 6.2A-4 V1 Stage 4B-2 (two BLOCKERs)

**Shared Liquidity / OB / FVG / Dealing-Range Entity & Lifecycle Surfaces**

Date: 2026-08-21
Task Type: PATCH ONLY
Role: Builder (NOT an Independent Audit)
Final status: **PATCHED / IMPLEMENTED — PENDING RE-AUDIT**

---

## 1. FVG 21-vs-22 discrepancy — resolution

The prior Builder report claimed "FVG events = 22"; the authoritative CLOSED `_E` tuple has **21
columns**. This was a reporting/counting mistake, NOT a material schema misunderstanding: the
implementation discovers derived columns dynamically and the prior code worked. The patched code now
imports the frozen CLOSED schema tuple directly (`_E`), so the count is no longer hand-stated. The
21-column fact is now the authoritative mirror.

## 2. BLOCKER 1 — cross-domain substitution (fixed)

**Exact change**: replaced the single generic `Stage4B2DomainSurface` with FOUR separate public
dataclasses — `Stage4B2LiquiditySurface`, `Stage4B2OrderBlockSurface`, `Stage4B2FVGSurface`,
`Stage4B2DealingRangeSurface`. A private `_DOMAIN_CONTRACT` map binds each surface CLASS to its fixed
`domain`, `contract_version`, and — critically — the exact frozen CLOSED output schemas imported
directly from the CLOSED modules (`_BAR_OUTPUT_COLUMNS`/`_EVENT_COLUMNS` for liquidity,
`_BAR_COLS`/`_EVENT_COLS` for OB, `_BAR`/`_E` for FVG, `_OUTPUTS`/`_TABLE` for dealing range).

**Runtime enforcement**: `verify_surface_integrity` derives domain/schema from the surface CLASS
(via `_contract_for`), never from caller-controlled metadata. It checks the actual current DataFrame
schemas equal the frozen mirror for THAT class. The `surface_id` hash now includes `surface_class`
(name). The four public surface types are exposed; a common private `_build_surface` helper is used.

**Coherent forgery results (verified)**:
- FVG content relabeled as `Stage4B2LiquiditySurface` → REJECT (bar schema mismatch).
- OB content relabeled as `Stage4B2DealingRangeSurface` → REJECT.
- Liquidity content relabeled as `Stage4B2FVGSurface` → REJECT.
- Cross-domain table swaps (FVG event/entity frames into Liquidity object) → REJECT.
- Coherent forgery with recomputed `surface_id` → REJECT (schema is class-derived, not hash-derived).

## 3. BLOCKER 2 — incomplete prefix identity (fixed)

**Exact change**: `project_domain_prefix` now binds ALL factual information legally visible through T,
composed from four canonical component prefixes:

```
bar_prefix_hash            (derived bar columns, rows 0..T)
event_prefix_hash          (lifecycle events with event_position <= T)
entity_prefix_hash         (entities with creation/confirmation position <= T)
normalized_event_prefix_hash (normalized events <= T, ambiguity flag preserved)
```

The composed `prefix_hash` binds the four component hashes (content only). Timeline/domain/surface
identity is carried by the binding's `surface_id` + `boundary_key` fields, NOT folded into the content
hash (so the content prefix is stable under legal future append).

**Index canonicalization fix (critical)**: every component prefix is `.reset_index(drop=True)` after
filtering. Without this, a boolean filter over a longer entity/event table changed the row index
class (`RangeIndex` vs generic `Index`), which the canonical DataFrame hash treats as a different
identity — the exact source of the pre-patch OB prefix divergence. The reset makes prefix identity
index-class-invariant.

**Availability semantics**: inclusion uses factual availability/creation/event position, never origin.

**Results (verified)**:
- Remove a pre-T `LEVEL_CREATED` event → `project_domain_prefix` REJECTS (integrity).
- Mutate pre-T normalized event / entity / (Dealing Range) range → REJECT.
- Post-T legal future extension (independently rebuilt) → prefix through T IDENTICAL for all four
  domains; full surface identity differs.
- Prefix binding object remains compact (no copied DataFrames).

## 4. Test results

| Metric | Value |
| --- | --- |
| Stage 4B-2 dedicated tests | **35** (27 prior + 8 new BLOCKER tests) |
| Total collected | **962** |
| Total passed | **962** (3m27s) |

## 5. Integrity

- `sha256sum -c MANIFEST.sha256` → **166 / 166 OK** (MANIFEST unchanged during PATCH).
- CLOSED Stage 4B-1 source unchanged: `bc393fe4ffb8dec9bdb16e4ae8e0036f22faefdecc8dc67345a5a881207bb708`.
- No CLOSED module/test modified.

## 6. Hashes

```
trajectory_stage4b2.py   e5eaaa00881285f9ffd1d00b57b1675c08ed803290786c9f92823a804567871c
test_trajectory_stage4b2.py  9111de52bd8dc51843fefaa94d255eed2f86505f3011bc75ecdb163e831e6842
```

## 7. Final status

```
PATCHED / IMPLEMENTED — PENDING RE-AUDIT
```

Not an Independent Audit. Not ACCEPTED. Not CLOSED. Stage 4C not started.
RESEARCH-DEBT-020 … 025 remain OPEN.

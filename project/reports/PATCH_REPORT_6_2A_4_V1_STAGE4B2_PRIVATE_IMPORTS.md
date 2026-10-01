# Patch Report — Module 6.2A-4 V1 Stage 4B-2 (private schema imports BLOCKER)

**Shared Liquidity / OB / FVG / Dealing-Range Entity & Lifecycle Surfaces**

Date: 2026-08-21
Task Type: PATCH ONLY
Role: Builder (NOT an Independent Audit)
Final status: **PATCHED / IMPLEMENTED — PENDING RE-AUDIT**

---

## 1. BLOCKER resolved

Stage 4B-2 was importing private/internal schema constants (`_BAR_OUTPUT_COLUMNS`, `_EVENT_COLUMNS`,
`_BAR_COLS`, `_EVENT_COLS`, `_BAR`, `_E`, `_OUTPUTS`, `_TABLE`) from CLOSED domain modules. These
symbols are not declared public CLOSED contracts. Following the Stage 4B-1 precedent, Stage 4B-2 now
keeps local frozen schema mirrors and verifies the actual public CLOSED output dynamically.

## 2. Exact 8 private imports removed

From `trajectory_stage4b2.py`, the following underscore-prefixed cross-module imports were removed
(8 symbols):

```
_BAR_OUTPUT_COLUMNS, _EVENT_COLUMNS   (from liquidity.liquidity_map)
_BAR_COLS, _EVENT_COLS               (from zones.order_blocks)
_BAR, _E                             (from zones.fvg)
_OUTPUTS, _TABLE                     (from zones.dealing_range)
```

The PUBLIC engine/error imports (`CausalLiquidityMapEngine`/`LiquidityMapError`, etc.) remain.

## 3. Exact local frozen schema mirrors added

Eight local `Final` tuples added, mirroring the exact audited PUBLIC factual output schemas:
`_LIQ_BAR_SCHEMA` (23), `_LIQ_EVENT_SCHEMA` (16), `_OB_BAR_SCHEMA` (26), `_OB_EVENT_SCHEMA` (20),
`_FVG_BAR_SCHEMA` (27), `_FVG_EVENT_SCHEMA` (21), `_DR_BAR_SCHEMA` (30), `_DR_RANGE_SCHEMA` (17).

These are Stage-4B-2-local immutable mirrors, not private-symbol imports.

## 4. FVG source-event schema count confirmation

FVG CLOSED source event schema = **21 columns** (confirmed from the public engine output). The
normalized Stage-4B-2 event representation adds one derived `same_information_batch_order_unknown`
field on top (22 total in the normalized frame), which is a Stage-4B-2-derived fact, NOT a CLOSED
source fact. The two schemas are distinct and correctly separated.

## 5. Runtime public-output equivalence (all four domains)

`_build_surface` discovers the actual derived output schema from the real public CLOSED engine result
and requires exact equality against the local frozen mirror; any mismatch → `TrajectoryDataError`
(reject/stop). Verified for Liquidity, OB, FVG, Dealing Range: all actual outputs equal the mirrors.

## 6. Cross-domain defense unchanged (still rejects)

The four public surface classes remain; `verify_surface_integrity` derives allowed domain/schema from
surface class + local frozen mirror. Re-ran the coherent attacks: FVG→Liquidity, OB→Dealing Range,
Liquidity→FVG, cross-domain table swaps, coherent hash/surface recomputation — all still REJECTED.

## 7. Prefix fix unchanged (regression passes)

`project_domain_prefix` still binds bar + event + entity + normalized-event prefixes via factual
availability, with the audited `reset_index(drop=True)` canonicalization. Pre-T mutations reject;
post-T legal future extension preserves the prefix for all four domains; full surface identity may
differ.

## 8. Regression test for private imports

Added `test_no_private_closed_schema_imports` (AST `ast.ImportFrom` inspection — semantic, not a
fragile substring check) asserting no underscore-prefixed name is imported from the four CLOSED domain
modules. Added `test_local_frozen_mirrors_match_actual_public_outputs` asserting the local mirrors
equal the actual public engine outputs, and that `_FVG_EVENT_SCHEMA` has exactly 21 columns.

## 9. Test results

| Metric | Value |
| --- | --- |
| Stage 4B-2 dedicated tests | **37** (35 prior + 2 new) |
| Total collected | **964** |
| Total passed | **964** (3m24s) |

## 10. Integrity

- `sha256sum -c MANIFEST.sha256` → **166 / 166 OK** (MANIFEST unchanged).
- CLOSED Stage 4B-1 source unchanged: `bc393fe4ffb8dec9bdb16e4ae8e0036f22faefdecc8dc67345a5a881207bb708`.
- No CLOSED module/test, STATUS, FINAL_VALIDATION, or release doc modified.

## 11. Hashes

```
trajectory_stage4b2.py   ce6fe481064c672538df63f9560493506c3b532de0de30714f71c8c4cf9ab563
test_trajectory_stage4b2.py  3315a6ac5c427b413f6eb510abe2486839b21d3c5a2bd0c8fde1beccf21d620b
```

## 12. Final status

```
PATCHED / IMPLEMENTED — PENDING RE-AUDIT
```

Not an Independent Audit. Not ACCEPTED. Not CLOSED. Stage 4C not started.
RESEARCH-DEBT-020 … 025 remain OPEN.

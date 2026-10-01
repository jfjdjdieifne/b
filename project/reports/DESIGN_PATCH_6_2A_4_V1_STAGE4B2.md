# DESIGN PATCH — Module 6.2A-4 V1 Stage 4B-2
## Shared Liquidity / OB / FVG / Dealing-Range Entity & Lifecycle Surfaces

Status: **DESIGN PROPOSAL — NOT IMPLEMENTED** (DESIGN PATCH ONLY)
Date: 2026-08-21

No code, tests, or files written. No MANIFEST change.

Authoritative baseline (re-verified): Stage 4B-1 CLOSED V1 (source `bc393fe4…`, test `7e0c572d…`),
927 collected / 927 passed, MANIFEST 166/166 OK (`1583cde0…`).

---

## 1. Authoritative structure dependency (Stage 4B-1 → 4B-2)

**Verified fact**: the CLOSED Stage 4B-1 `Stage4B1StructureSurface.frame` is the cumulative 2.1C
output and **preserves all passthrough market columns** (`open`, `high`, `low`, `close`, `volume`)
plus the complete 2.1A + 2.1B + 2.1C derived columns. Every input column required by Liquidity / OB /
Dealing Range is present in the frame (verified empirically: OB's 13 required columns all present).

Binding contract:

1. **4B-2 binds these Stage 4B-1 identity fields** for Liquidity / OB / Dealing Range:
   `surface_id`, `timeline_id`, `timeline_hash`, `adapter_kind`, `contract_version`,
   `reconstruction_input_hash`, `swing_policy_hash`, `public_result_hash`, plus the three component
   hashes (`hash_2_1a/2_1b/2_1c`).
2. **4B-2 consumes the COMPLETE shared structure surface frame** (`surface.frame`) — NOT a
   re-derived downstream projection. The domain engines read exactly the columns they require from
   the verified frame; no side-channel 2.1A→2.1B→2.1C reconstruction is performed.
3. **Reconstruction verification**: before any domain engine is invoked, 4B-2 calls
   `verify_surface_integrity(structure_surface)` (recomputes all hashes from CURRENT frame content)
   and then `verify_surface_matches_reconstruction(supplied, authoritative)` against an
   independently built Stage 4B-1 surface from the same timeline. This proves the structural facts
   supplied to the domain engines correspond to the CLOSED Stage 4B-1 artifact.
4. **Forged/stale rejection**: a mutated, stale, forged, or cross-timeline Stage 4B-1 surface is
   rejected by `verify_surface_integrity` BEFORE the domain reconstruction (mirroring the Stage 4A
   absorption upstream-verification order).

No hypothesis-relative Stage 2 structure identity is used.

---

## 2. FVG stays structure-independent

FVG (CLOSED 4.2A) consumes OHLC only. Its reconstruction identity binds:
- authoritative market timeline/input (`timeline_id`, `timeline_hash`, `adapter_kind`),
- CLOSED FVG contract version (`MODULE_4_2A_V1_1`),
- complete FVG factual result (bar surface + event table),
- reconstruction input hash = timeline identity + `open/high/low/close` column names.

No Stage 4B-1 dependency is fabricated for FVG. FVG is built directly from the sealed
`MarketObservationTimeline` market history, not from the structure surface.

---

## 3. Surface type architecture: SEPARATE strongly-typed surfaces (Option B)

Chosen for factual-contract safety, not elegance. The four CLOSED engines return heterogeneous
shapes:

| Domain | CLOSED return | Structure |
| --- | --- | --- |
| Liquidity (2.2) | `(bar_surface, normalized_events)` | event table carries entity identity + lifecycle |
| Order Block (4.1) | `(bar_surface, normalized_events)` | event table carries entity identity + lifecycle |
| FVG (4.2A) | `(bar_surface, events)` | event table carries entity identity + lifecycle |
| Dealing Range (4.2B) | `(bar_surface, range_table)` | range table IS the entity table |

Design: **four distinct dataclasses** (`Stage4B2LiquiditySurface`, `Stage4B2OrderBlockSurface`,
`Stage4B2FVGSurface`, `Stage4B2DealingRangeSurface`) sharing a common identity/verification helper
module (canonical hashing domains, boundary legality, self-integrity). Each class carries its own
`domain` constant and its own frozen schema tuples.

Safety guarantee: it is **type-impossible** to pass an FVG surface to the Liquidity builder, or an
OB event table to the Dealing-Range consumer — the builders are typed per-domain and each
`verify_surface_integrity` checks the exact per-domain output schema (entity/event/bar columns)
against the frozen CLOSED-schema constants. Any cross-domain or wrong-config/binding consumption is
rejected at the type boundary and re-checked at runtime.

---

## 4. Complete factual output per domain (re-inspected current CLOSED contracts)

"Complete public result" = **both** the returned bar surface AND the returned event/range table. The
event table is NOT the only factual output — per-bar aggregate state also lives in the bar surface.

- **Liquidity**: bar surface (23 derived cols: `liquidity_level_created`, `created_level_*`,
  `nearest_*`, `high/low_side_first_*_count`, `known_*_level_count`) + normalized event table (16
  cols: `event_position`, `level_id`, `side`, `event_type`, `source_origin/confirmation_position`,
  `source_class`, `immutable_level_price`, `event_price/close`, `overshoot_fraction`, `nearest_*`,
  `level_age_bars`).
- **Order Block**: bar surface (26 cols: `ob_candidate_created`, `created_ob_*`, `bullish/bearish_ob_*_count`,
  `known_*_count`) + event table (20 cols: `event_position`, `zone_id`, `direction`, `event_type`,
  `origin/creation/search_boundary_position`, `source_break_event`, `full/body_zone_*`,
  `event_high/low/close`, `displacement_*`, `origin_prior_use_count`, `zone_age_bars`).
- **FVG**: bar surface (27 cols: `fvg_candidate_created`, `created_fvg_*`, `bullish/bearish_fvg_*_count`,
  `known_*_count`) + event table (22 cols: `event_position`, `fvg_id`, `direction`, `event_type`,
  `origin/middle/creation_position`, `zone_low/high`, `midpoint`, `gap_width*`, `middle_*`,
  `event_high/low/close`, `zone_range_coverage_fraction`, `fvg_age_bars`).
- **Dealing Range**: bar surface (29 cols: `dealing_range_created`, `created_range_*`, `rejected_range_geometry`,
  `current_range_*`, `current_range_position_raw`, `current_midpoint_displacement`,
  `current_discount_depth`, `current_premium_depth`) + range table (18 cols: `range_id`,
  `creation_position`, `direction`, two endpoints' `side/origin/confirmation/price/class`,
  `range_low/high/width/midpoint`).

Complete-result hash per domain = canonical hash over BOTH tables (bar surface derived columns +
event/range table), domain-separated (`STAGE4B2_<DOMAIN>_COMPLETE_RESULT_V1`). Passthrough market
columns are reconstruction inputs bound via the timeline seal, NOT part of the derived
complete-result hash (consistent with Stage 4B-1's convention).

---

## 5. Entity table derivation (explicit, non-fabricating)

- **Liquidity / OB / FVG**: the CLOSED engines return NO physically separate entity table. Stage
  4B-2 MAY derive a normalized entity table (one row per entity) from the `*_CREATED` event rows
  (e.g. `LEVEL_CREATED` / `ZONE_CREATED` / `FVG_CREATED`), carrying only fields the CLOSED event row
  exposes (entity id + direction + origin/creation positions + immutable geometry). The normalized
  table is **labeled as a Stage-4B-2-derived representation**, never as an original CLOSED source
  table. Both the original complete CLOSED result AND the normalized representation are bound.
  No factual field is invented.
- **Dealing Range**: the range table IS the original CLOSED entity table (one row per range). No
  derivation needed; it is bound directly.

---

## 6. Entity ID prefix stability (BUILD-time empirical mandate)

- **FVG**: prior empirical evidence exists (24-bar `[0..19]` == first 20 of 40-bar `[0..35]`).
- **Liquidity / OB / Dealing Range**: MUST be established empirically during BUILD by rebuilding a
  prefix-through-T surface and an identical-prefix + future-extended surface through the REAL CLOSED
  engines, comparing entity IDs for entities legally created through T. Any change → **BUILD
  BLOCKER**; do NOT silently replace the CLOSED ID.

---

## 7. Event availability (reconfirmed from current CLOSED contracts)

All four engines are single-pass causal batch engines. For every lifecycle event,
`event_position == first factual availability == bar i`, legal phase `COMPLETED_ROW_AVAILABLE`
(or `RESEARCH_SNAPSHOT_AVAILABLE` as a legal research projection boundary — NOT the market fact's
original availability). Origin is a positional Int64 strictly earlier (for OB/FVG/liquidity
creation), never an InformationKey, and never substituted for availability. Dealing-range
`rejected_range_geometry` is a per-bar invalidation fact; `current_range_*` replacement is a per-bar
persistence fact.

Same-bar multiple events: the CLOSED event tables are sorted mechanically by
(`event_position`, `entity_id`, fixed event-type order) — this is **deterministic serialization, not
intrabar market chronology**. Stage 4B-2 preserves `SAME_INFORMATION_BATCH_ORDER_UNKNOWN` wherever
OHLC cannot prove ordering.

BUILD tests must use REAL generated lifecycle events (non-vacuous), not fake tables.

---

## 8. Prefix projection (reuse CLOSED boundary legality)

Stage 4B-2 reuses the CLOSED Stage 4B-1 / Stage 4A boundary pattern exactly:
- mature research boundary = terminal factual-availability boundary (Stage 3);
- censored research boundary = research as-of boundary (Stage 3);
- legal phases only (`COMPLETED_ROW_AVAILABLE`, `RESEARCH_SNAPSHOT_AVAILABLE`); `BAR_PRE_CLOSE`
  rejected; cross-timeline rejected; positional no-timestamp; time-indexed timestamp correctness.
- No post-boundary entity creation, lifecycle event, per-bar state, or invalidation/replacement fact.
- Origin before the boundary does NOT make a later-confirmed entity visible early.

---

## 9. Identity separation (no conflation)

Distinct, never conflated: full-surface identity, factual-content identity, complete-result
identity, compact prefix identity, entity identity (CLOSED `level_id`/`zone_id`/`fvg_id`/`range_id`),
reconstruction witness, historical provenance. Historical generating-input provenance remains
NOT_CERTIFIED / UNVERIFIABLE.

---

## 10. Self-integrity (Stage 4A / 4B-1 lessons)

Each 4B-2 surface holds mutable DataFrames. `verify_surface_integrity` recomputes from CURRENT
content: complete-result hash, surface_id, upstream Stage 4B-1 binding (for Liquidity/OB/Dealing
Range), entity/event/bar schema, and rejects stale/forged fields. Coverage: original CLOSED bar
surface, original event/range table, normalized entity table (if derived), normalized lifecycle
table (if derived), per-bar state table, upstream structure binding. Defensive deep copy at the
construction boundary. No hidden cache.

---

## 11. Required non-vacuous BUILD tests

Every prefix-invariance/lifecycle test MUST first assert the fixture actually contains the facts
being tested (no row-count-only lifecycle assertions). Minimum per domain:
- **Liquidity**: real level creation + real lifecycle event (e.g. FIRST_TOUCH).
- **Order Block**: real candidate creation + real lifecycle event.
- **FVG**: real 3-bar creation + real lifecycle event.
- **Dealing Range**: real range creation + persistence + replacement or rejection.

The Stage 4B-1 lesson (vacuous fixtures) applies verbatim: fixtures must use the seeded
`EmpiricalConfirmationPolicy` + a structure-rich market to guarantee real swings/BOS for
Liquidity/OB/Dealing Range.

---

## 12. Shared storage

One physical domain surface per exact shared market/domain identity. No per-hypothesis duplication.
Hypothesis projection = compact binding through its legal Stage 3 boundary. Growth estimate:
- per domain: entity table O(#entities), event table O(#events), bar surface O(#bars × cols);
- hypothesis count does NOT multiply physical market/entity storage (projections are references +
  prefix hashes).

---

## 13. Failure rule

During BUILD, if actual CLOSED contracts contradict the design (ID stability, event availability,
prefix invariance, complete-result reconstruction, or Stage 4B-1 structural correspondence), STOP
and report BLOCKER. Do NOT patch CLOSED modules.

---

## 14. Out of scope (unchanged)

Stage 4C, strategy laboratory, ICT strategy optimization, descriptors, estimands, ML, scorer,
probabilities, geometry, execution, PnL, WIN/LOSS, signals. The future strategy-laboratory
requirement is acknowledged but MUST NOT contaminate factual Stage 4B-2.

---

## 15. Open debts (unchanged)

RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025 — all OPEN.

---

## 16. Classification

- **BLOCKERS**: none remaining at the design level. BUILD-time empirical gates (§6) and non-vacuous
  fixture requirement (§11) are mandatory deliverables, not design gaps.
- **NON-BLOCKING DESIGN DEBT**: normalized entity tables are derived (documented, not original); the
  four surfaces share a helper module but are strongly typed (some code duplication accepted for type
  safety).
- **RESEARCH QUESTIONS**: none new.

## BUILD readiness verdict

```
DESIGN PROPOSAL — NOT IMPLEMENTED
NO DESIGN BLOCKER REMAINS FOR STAGE 4B-2
BUILD NOT AUTHORIZED (pending explicit BUILD ONLY authorization)
```

Stage 4B-2 may proceed as one BUILD (four domain surfaces + shared identity module), consuming
CLOSED Stage 4B-1 (Liquidity/OB/Dealing Range) and the sealed timeline (FVG), once authorized.

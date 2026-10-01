# DESIGN PROPOSAL — Module 6.2A-4 V1 Stage 4B
## Shared Entity / Lifecycle Future Trajectory

Status: **DESIGN PROPOSAL — NOT IMPLEMENTED** (DESIGN ONLY)
Date: 2026-08-21

Authoritative baseline (unchanged):
- Stage 4A CLOSED; 890 collected / 890 passed; MANIFEST 162/162 OK, SHA-256 `2a527baf…`.
- Stage 4A CLOSED source `19034dff…`, test `7547abfd…`.
- No file, test, or MANIFEST modified by this design task.

Scope: Stage 4B = **Liquidity (2.2) + Order Block Candidate (4.1) + FVG Candidate (4.2A) +
Dealing Range (4.2B)** shared entity/lifecycle trajectory. Stage 4C (HTF/MTF) OUT OF SCOPE.

---

## 1. CLOSED contracts inspected (source + tests, not summaries)

| Domain | Module | Engine | Return |
| --- | --- | --- | --- |
| Liquidity | 2.2 | `CausalLiquidityMapEngine.analyze(df)` | `(bar_surface, normalized_events)` |
| Order Block | 4.1 | `CausalOrderBlockEngine.analyze(df)` | `(bar_surface, normalized_events)` |
| FVG | 4.2A | `CausalFVGEngine.analyze(d)` | `(bar_surface, normalized_events)` |
| Dealing Range | 4.2B | `CausalDealingRangeEngine.analyze(df)` | `(bar_surface, range_table)` |

### 1.1 Liquidity (2.2)
- **Inputs**: `high, low, close` + `_A_COLUMNS` (swing_high/low_confirmed, swing_origin_position,
  swing_price, swing_confirmation_position) + `_B_COLUMNS` (structure_event_type,
  swing_sequence_class, comparison_available, previous_same_type_price/origin, current_structure_*,
  same_type_log_price_change).
- **Upstream**: CLOSED 2.1A (swing) + 2.1B (sequence) + 2.1C (structure).
- **Entity identity**: `level_id = len(levels)` (sequential creation order). Side (high/low),
  immutable `level_price`, `source_class`.
- **Creation**: `LEVEL_CREATED` at `source_confirmation_position`; origin `source_origin_position`.
- **Lifecycle (fixed order)**: `FIRST_TOUCH`, `FIRST_WICK_BREACH`, `FIRST_WICK_ONLY_EXCURSION`,
  `FIRST_CLOSE_BREACH`, `FIRST_RECLAIM_AFTER_CLOSE_BREACH`.
- **Per-bar state**: first-event counts, `known_*_level_count`, `nearest_prior_same_side_level_id`,
  `nearest_same_side_distance_fraction`, `nearest_distance_percentile` (+history).
- **Determinism**: event table sorted mechanically by `(event_position, level_id, event-type order)`
  — "does not imply intrabar sequence".

### 1.2 Order Block (4.1)
- **Inputs**: OHLC + swing cols + `structural_break_event`, `high/low_close_breach_event`,
  `structure_state_before`.
- **Upstream**: CLOSED 2.1A swing + 2.1C structural break + structure_state_before.
- **Entity identity**: `zone_id = len(zones)`. Direction BULLISH/BEARISH OB CANDIDATE; origin,
  creation, search_boundary_position; immutable zone geometry (full/body low/high);
  `source_break_event` (BOS/CHOCH); `origin_prior_use_count`; `displacement_*` (+ causal percentile).
- **Lifecycle**: `ZONE_CREATED`, `FIRST_TOUCH`, `FIRST_FAR_SIDE_WICK_BREACH`,
  `FIRST_FAR_SIDE_CLOSE_BREACH`, `FIRST_CLOSE_RECLAIM_OF_FAR_SIDE`.
- **Terminology**: CANDIDATE — explicitly NOT institutional orders.

### 1.3 FVG (4.2A)
- **Inputs**: OHLC only (3-bar gap geometry). No structure/swing dependency.
- **Entity identity**: `fvg_id = len(fs)`. Direction BULLISH/BEARISH FVG CANDIDATE; origin
  (i-2), middle (i-1), creation (i); immutable zone low/high/midpoint/gap_width; width fraction +
  causal percentile; middle body fractions.
- **Lifecycle**: `FVG_CREATED`, `FIRST_TOUCH`, `FIRST_FULL_RANGE_COVERAGE`,
  `FIRST_FAR_SIDE_WICK_BREACH`, `FIRST_FAR_SIDE_CLOSE_BREACH`, `FIRST_CLOSE_RECLAIM_OF_FAR_SIDE`.

### 1.4 Dealing Range (4.2B)
- **Inputs**: `close` + `_A` (swing cols) + `_B` (structure cols).
- **Upstream**: CLOSED 2.1A + 2.1B + 2.1C.
- **Entity**: `range_id` (sequential); direction; two endpoints (side/origin/confirmation/price/
  class); immutable range low/high/width/midpoint; `creation_position`.
- **Per-bar state**: `current_range_id/direction/creation/low/high/width/midpoint`,
  `current_range_position_raw`, `current_midpoint_displacement`, `current_discount_depth`,
  `current_premium_depth`.
- **Invalidation**: `rejected_range_geometry` (a range can be invalidated and replaced).
- **Hybrid**: persistent entity + per-bar current-range projection + invalidation.

---

## 2. Entity identity stability analysis (the critical question)

All four domains assign IDs sequentially by creation order within a single `analyze` run:
`level_id = len(levels)`, `zone_id = len(zones)`, `fvg_id = len(fs)`, `range_id` (sequential).
Because every engine's loop is **causal** — an entity created at bar `i` depends only on history
through `i` — the assignment is deterministic and **prefix-stable**:

- **Empirically verified for FVG**: a 24-bar prefix yields `fvg_id = [0..19]`; a 40-bar
  future-extended surface yields `[0..35]`, whose first 20 entries equal the 24-bar prefix's IDs
  exactly.
- **By code inspection** for liquidity/OB/dealing-range: the same `len(collection)` pattern with a
  causal creation loop; an entity at position i is the `(k+1)`-th created, independent of bars > i.

**Conclusion**: CLOSED entity IDs are **prefix-stable across legal future extension** under the
causal creation contract. Stage 4B may use them as persistent cross-prefix entity identity —
documented as a **derivation identity** (a function of market history), NOT historical provenance
and NOT a statistical-independence claim.

**Caveat recorded**: this stability is a property of the CLOSED engines' causal construction, not a
promise implied by the integer name. Stage 4B must (a) record this reasoning in its contract, and
(b) add a prefix-stability test per domain (see §15) that recomputes the full surface and asserts
the prefix entity IDs are preserved — if any domain ever violates it, that is a BLOCKER.

---

## 3. Shared entity surface design

Concept: `Stage4BEntityDomainSurface` (per domain), computed once per exact domain-surface identity
(independent of hypothesis identity), containing:

- `entity_table` (immutable creation facts per entity: id + direction + origin + creation +
  immutable geometry + source identity fields),
- `event_table` (normalized lifecycle events),
- `bar_surface` (per-bar state/projection columns),
- plus identity/witness fields (config binding, reconstruction input, upstream structure binding,
  complete public-result hash, surface_id).

A hypothesis references/projects this shared surface through its legal boundary (§10); it never
carries a physical copy of the entity/event/state tables.

---

## 4. Complete public-result equivalence

Canonical `STAGE4B_<DOMAIN>_PUBLIC_RESULT_EQUIVALENCE_V1` hash over the COMPLETE CLOSED factual
output — entity facts + event table + bar-surface facts — not just entity/event IDs:

- **Liquidity**: entity level facts (id/side/price/origin/confirmation/source_class) + full
  normalized lifecycle event table + all bar-surface columns (created_* + per-side counts +
  nearest-* + known counts).
- **Order Block**: zone creation facts (id/direction/origin/creation/boundary/source/geometry/
  displacement) + full lifecycle event table + bar-surface columns.
- **FVG**: candidate facts (id/direction/origin/middle/creation/geometry/width-fraction) + full
  event table + bar-surface columns.
- **Dealing Range**: range table (all columns) + per-bar current-range state + invalidation
  `rejected_range_geometry` + premium/discount/midpoint fields.

No field is transitively excluded except where proven field-by-field; the entity/event tables are
included in full (their row content carries origin/source/geometry facts not present in the
bar-surface). No reliance on IDs alone.

---

## 5. Self-integrity (Stage 4A lesson applied from the start)

`Stage4BEntityDomainSurface` contains THREE mutable DataFrames (entity_table, event_table,
bar_surface). A frozen dataclass is NOT enough. `verify_surface_integrity(surface)` must:
- recompute the complete public-result hash from CURRENT entity_table + event_table + bar_surface
  content and require equality with the stored hash;
- recompute `surface_id` from CURRENT content (domain, contract version, timeline identity, adapter
  kind, config binding, reconstruction input, upstream structure binding, recomputed hash);
- verify exact output schema per domain (entity columns, event columns, bar columns) from the CLOSED
  contract + frozen config payload (not the mutable column tuples);
- reject duplicate columns, missing columns, forged IDs/hashes/config/upstream bindings.

Every consumer (`project_entity_prefix`, `verify_surface_matches_reconstruction`, and any future
upstream consumption) calls `verify_surface_integrity` FIRST. Defensive deep copy at the
construction boundary (in addition to the CLOSED engines' own deep copies). Mutated tables under a
stale identity → REJECT.

---

## 6. Upstream structure binding (shared, NOT hypothesis-relative)

Liquidity / OB / Dealing Range consume CLOSED 2.1A/2.1B/2.1C structural facts. Stage 4B must prove
the supplied entity surface corresponds to the structural inputs it claims to consume — via a
deterministic reconstruction witness, not historical provenance.

**Critical design point**: Stage 2's structure trajectory is hypothesis-relative (it consumes an
interval). It must NOT be reused as the shared market structure identity. Stage 4B needs a
**shared structure surface** built directly from CLOSED 2.1A → 2.1B → 2.1C over the full market
history (a Stage-4B-local "structure surface" independent of hypothesis). The upstream structure
binding is the complete public-result hash (or a full reconstructed equivalence) of that shared
structure surface, truncated to the same legal prefix as the entity surface.

This is the single largest new piece of Stage 4B and must be its own auditable unit (§16).

---

## 7. Origin vs factual availability

Per entity type:
- **Liquidity**: origin = `source_origin_position` (swing origin); creation/confirmation =
  `source_confirmation_position`; factual available-at = confirmation InformationKey.
- **Order Block**: origin = `origin_position` (break origin); creation = `creation_position`; the
  entity is visible at creation.
- **FVG**: origin = `origin_position` (i−2), middle (i−1), creation (i); visible at creation (i).
- **Dealing Range**: origin = first endpoint origin; creation = `creation_position`; visible at
  creation.

Origin is preserved as the CLOSED Int64 position (NO manufactured origin InformationKey).
Visibility is governed by factual availability: an entity whose origin predates a hypothesis but is
confirmed after it is a valid future fact and must NOT be dropped because origin < decision.

---

## 8. Lifecycle event availability

Each event carries `event_position` (Int64). First legal factual availability = the InformationKey at
that position (COMPLETED_ROW_AVAILABLE semantics). OHLC resolution does NOT know intrabar order:
- the CLOSED event tables are serialized mechanically (`event_position, entity_id, fixed event-type
  order`) and explicitly do NOT imply intrabar sequence;
- when multiple lifecycle events occur in the same OHLC bar, Stage 4B must preserve
  `SAME_INFORMATION_BATCH_ORDER_UNKNOWN` — never reorder into a fabricated intrabar chronology
  (`deterministic_sequence` is NOT market chronology).

---

## 9. Dealing range persistence semantics

- A range is a persistent entity; `current_range_*` is a per-bar as-of projection.
- `premium` / `discount` are factual project geometry (price position relative to range midpoint) —
  NOT a trade filter. `rejected_range_geometry` is factual invalidation, NOT a trading stop.
- Immutable history: when a range is invalidated/replaced, earlier as-of snapshots that truthfully
  saw the prior `current_range_*` must NOT be rewritten. The prefix identity through T must remain
  stable; only the full-surface identity changes.

---

## 10. Hypothesis projection

Reuses Stage 4A's boundary contract exactly:
- mature Stage 3 snapshot → boundary = terminal factual-availability InformationKey;
- censored → boundary = research as-of InformationKey;
- legal phases only (`COMPLETED_ROW_AVAILABLE`, `RESEARCH_SNAPSHOT_AVAILABLE`); `BAR_PRE_CLOSE`
  rejected; cross-timeline rejected; time-indexed timestamp validated; positional no-timestamp
  semantics. No post-boundary entity/event/state fact.

---

## 11. Prefix identity / future extension

- Full entity-domain surface identity changes when future entities/events append.
- Prefix identity through boundary T must remain equal between the old valid surface and a NEW
  independently rebuilt future-extended surface, IF the CLOSED domain is genuinely causal /
  prefix-invariant. Add a per-domain prefix-stability test; if any domain fails it, report BLOCKER
  and identify the violating CLOSED engine (do NOT patch it silently).

---

## 12. Configuration / magic numbers

The four engines consume NO public configuration (no lookback, threshold, displacement cutoff, zone
filter, touch count, TTL, age, or scoring rule). Liquidity/OB/FVG/Dealing-Range are parameter-free
deterministic engines. Therefore:
- config binding = the CLOSED contract version + the exact upstream structure-chain inputs (for
  liquidity/OB/range) or the exact OHLC prefix (for FVG);
- Stage 4B introduces NO new defaults or magic numbers. If a future engine gains explicit config,
  it must be required, never defaulted.

---

## 13. Shared storage model

- Shared `entity_table`, `event_table`, `bar_surface` per (domain-surface identity), computed once.
- Hypothesis projection = compact reference + prefix hash + boundary key. NO per-hypothesis copy of
  entity/event/state tables, NO market copy, NO growing event tuple inside snapshots.
- Growth: entity table O(#entities), event table O(#events), bar surface O(#bars × state columns).
  Entity lifecycle scans are O(N·L) (documented by CLOSED engines) — not hidden.

---

## 14. Source / identity / derivation separation

Five distinct notions, never conflated:
1. ENTITY IDENTITY — the CLOSED `level_id`/`zone_id`/`fvg_id`/`range_id` (derivation identity).
2. FACTUAL CONTENT IDENTITY — the complete public-result hash.
3. DETERMINISTIC DERIVATION WITNESS — reconstruction/config/upstream bindings.
4. HISTORICAL PROVENANCE — NOT CERTIFIED / UNVERIFIABLE (CLOSED engines do not seal input identity).
5. STATISTICAL INDEPENDENCE — not claimed.

---

## 15. Required future test matrix

Per domain (liquidity/OB/FVG/dealing-range): prefix append invariance; future mutation strictly
after T (rebuilt surface); mutation at/before T (integrity reject); entity identity stability;
creation invisible before availability; visible at availability; origin preserved; origin before
decision allowed; lifecycle event invisible before event_position; same-bar multiple-event
SAME_INFORMATION_BATCH_ORDER_UNKNOWN; event serialization ≠ intrabar chronology; complete
public-result mutation detection (entity-table, event-table, bar-state each); forged entity ID;
forged config binding; forged reconstruction binding; forged upstream structure binding;
cross-timeline rejection; BAR_PRE_CLOSE rejection; wrong-timestamp/right-position rejection; input
immutability; A→A; A→B→A; fresh instance; no hidden cache; duplicate columns; nullable ints; >2^53
where applicable; NaN/Inf; +0/−0 where identity matters; two hypotheses share the same physical
entity surface; no post-terminal facts; no post-censor-as-of facts; firewall; no Stage 4C; no
descriptors/estimands/model/geometry/execution.

Domain-specific: liquidity all FIRST_* + same-bar collisions; OB candidate creation + immutable
geometry + lifecycle; FVG 3-bar creation causality + lifecycle; dealing range creation +
persistence + replacement/invalidation + historical state immutability.

---

## 16. Recommended Stage 4B sub-staging

Split into TWO sub-stages by actual dependency boundary (not convenience):

- **Stage 4B-1 — Shared Structure Surface** (NEW prerequisite): a shared, hypothesis-independent
  structure surface built from CLOSED 2.1A → 2.1B → 2.1C over full market history, with its own
  complete public-result hash and self-integrity. This is the shared upstream that §6 requires and
  is needed by liquidity/OB/dealing-range but NOT by FVG.
- **Stage 4B-2 — FVG + Liquidity + OB + Dealing Range entity/lifecycle**: consumes the shared
  structure surface (liquidity/OB/range) or OHLC only (FVG), producing the four entity domain
  surfaces with the §3–§14 contracts.

Dependency graph:

```
CLOSED OHLC ────────────────────────────────► FVG (4.2A)
CLOSED 2.1A → 2.1B → 2.1C (shared) ──► Liquidity (2.2), OB (4.1), Dealing Range (4.2B)
                                        ▲
              Stage 4B-1 (shared structure surface) must precede 4B-2
```

Alternatively 4B-1 could be folded into 4B-2, but keeping it separate makes the shared-structure
surface auditable in isolation and prevents the hypothesis-relative Stage 2 structure from being
accidentally reused as shared identity.

---

## 17. Open debts

Keep OPEN: RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025. No new debt proposed (no unresolved
contract problem found; the prefix-stability and shared-structure questions are resolved by design
+ test, not by a new debt).

---

## 18. BLOCKERS / DEBT / RESEARCH

**BLOCKERS**: none remaining — the four design risks (prefix stability, shared vs hypothesis-relative
structure, mutable-DataFrame integrity, dealing-range immutability) are each resolved by a concrete
design decision plus a mandated test. Stage 4B is ready for BUILD on authorization, structured as
4B-1 then 4B-2.

**NON-BLOCKING DESIGN DEBT**: entity-lifecycle scan cost O(N·L) (accepted, documented); wide bar
surfaces (collision rejection mirrors CLOSED).

**RESEARCH QUESTIONS**: none new; any predictive use of entity/lifecycle states belongs to future
estimand work (debts remain OPEN).

---

## 19. Out of scope

- Stage 4C (HTF/MTF); descriptors; estimands; hazard/survival/competing-risk; model/scorer/weights/
  probabilities; geometry/entry/stop/target/execution/fills; PnL/WIN/LOSS/SUCCESS; signals;
  predictive edge; fixed horizons; statistical-independence claims; any relabeling of CANDIDATE as
  institutional orders, of absorption as manipulation, or of premium/discount/invalidation as a
  trade filter.

---

## 20. Final status

```
DESIGN PROPOSAL — NOT IMPLEMENTED
```

No code, tests, or files written; no MANIFEST change; no CLOSED module modified; Stage 4C not started.

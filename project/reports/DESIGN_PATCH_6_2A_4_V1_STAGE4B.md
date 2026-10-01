# DESIGN PATCH — Module 6.2A-4 V1 Stage 4B (4B-1 structure surface + availability)

Status: **DESIGN PROPOSAL — NOT IMPLEMENTED** (DESIGN PATCH ONLY)
Date: 2026-08-21

No code, tests, or files written. No MANIFEST change. BUILD not authorized. Stage 4C not started.

This resolves the three design blockers: (1) complete 4B-1 structure-surface schema, (2) per-event
factual-availability matrix, (3) corrected ID-stability claim + 4B-1 boundary semantics.

---

## 1. Exact Stage 4B-1 field-level schema

Stage 4B-1 = a shared, hypothesis-independent **structure surface** produced by composing CLOSED
`2.1A → 2.1B → 2.1C` over the full market history. It carries the **complete CLOSED public factual
result** of the chain (not merely the downstream-consumed subset).

### 1.1 Complete output schemas (verbatim from CLOSED `_OUTPUT_COLUMNS`)

**2.1A — `CausalAdaptiveSwingDetector`** (24 derived columns + passthrough `high`/`low`):

| Field | dtype | Meaning |
| --- | --- | --- |
| `candidate_side` | object/string | UNDECIDED/HIGH/LOW |
| `candidate_origin_position` | Int64 (nullable) | pivot origin position |
| `candidate_price` | float64 | pivot price |
| `candidate_reversal_distance` | float64 | reversal distance |
| `candidate_reversal_fraction` | float64 | reversal fraction |
| `candidate_reversal_evidence` | float64 | percentile evidence |
| `candidate_continuation_history_count` | int64 | causal history count |
| `candidate_confirmed_history_count` | int64 | confirmed history count |
| `candidate_confirmation_threshold` | float64 | policy threshold |
| `swing_high_reversal_evidence` / `swing_low_reversal_evidence` | float64 | evidence per side |
| `swing_high_confirmed` / `swing_low_confirmed` | bool | confirmed swing flag |
| `swing_origin_position` | Int64 (nullable) | swing origin (position) |
| `swing_price` | float64 | swing price |
| `swing_confirmation_position` | Int64 (nullable) | swing confirmation (position) |
| `swing_confirmation_price` | float64 | confirmation price |
| `swing_reversal_distance` / `_fraction` / `_evidence` | float64 | confirmed swing reversal |
| `swing_continuation_history_count` | int64 | causal history |
| `swing_confirmed_history_percentile` | float64 | percentile |
| `swing_confirmed_history_count` | int64 | history count |
| `swing_confirmation_threshold` | float64 | threshold |

**2.1B — `ConfirmedSwingSequenceEngine`** (9 derived columns):
`structure_event_type` (string: NONE/HIGH/LOW), `swing_sequence_class` (string: UNCLASSIFIED/
HH/LH/EH/HL/LL/EL), `comparison_available` (bool), `previous_same_type_price` (float64),
`previous_same_type_origin_position` (Int64 nullable), `current_structure_swing_price` (float64),
`current_structure_origin_position` (Int64 nullable), `current_structure_confirmation_position`
(Int64 nullable), `same_type_log_price_change` (float64).

**2.1C — `CausalStructuralBreakEngine`** (34 derived columns):
monitored_high/low price/origin/confirmation/first_wick/first_close breach positions + booleans;
high/low wick/close breach events; high/low wick_only events; high/low wick/close overshoot
fractions; high/low wick/close break evidence; wick/close break history counts;
`structure_state_before` (string), `structure_state_after` (string), `structural_break_event`
(string: BOS_UP/CHOCH_DOWN/BOS_DOWN/CHOCH_UP/etc).

### 1.2 Consumed-by-downstream mapping (which fields each entity domain reads)

| Field family | Liquidity 2.2 | OB 4.1 | Dealing Range 4.2B |
| --- | --- | --- | --- |
| `swing_high/low_confirmed` | ✓ | ✓ | ✓ |
| `swing_origin_position` | ✓ | ✓ | ✓ |
| `swing_price` | ✓ | ✓ | ✓ |
| `swing_confirmation_position` | ✓ | ✓ | ✓ |
| `structure_event_type` | ✓ | — | ✓ |
| `swing_sequence_class` | ✓ | — | ✓ |
| `comparison_available` | ✓ | — | ✓ |
| `previous_same_type_price` / `_origin_position` | ✓ | — | ✓ |
| `current_structure_swing_price` / `_origin_position` / `_confirmation_position` | ✓ | — | ✓ |
| `same_type_log_price_change` | ✓ | — | ✓ |
| `structural_break_event` | — | ✓ | — |
| `high/low_close_breach_event` | — | ✓ | — |
| `structure_state_before` | — | ✓ | — |

### 1.3 Complete-result vs downstream-projection distinction (explicit)

- **(A) Complete CLOSED public factual result** = the full 2.1A + 2.1B + 2.1C outputs (all derived
  columns above). This is what 4B-1 claims public-result equivalence over.
- **(B) Downstream-required projection** = the subset consumed by Liquidity/OB/Dealing Range
  (§1.2). This is a derived convenience view, NOT the identity basis.

4B-1's complete-public-result hash binds **(A)** in full. A mutation to ANY field in (A) must alter
the identity. (B) is never used as the equivalence basis.

---

## 2. Identity / equivalence design (canonical hashing)

Four canonical domains:

```
STAGE4B1_STRUCTURE_2_1A_PUBLIC_RESULT_V1   over the full 2.1A output DataFrame
STAGE4B1_STRUCTURE_2_1B_PUBLIC_RESULT_V1   over the full 2.1B output DataFrame
STAGE4B1_STRUCTURE_2_1C_PUBLIC_RESULT_V1   over the full 2.1C output DataFrame
STAGE4B1_SHARED_STRUCTURE_SURFACE_V1       over { timeline_id, timeline_hash, adapter_kind,
                                             contract versions, 2.1A hash, 2.1B hash, 2.1C hash,
                                             reconstruction input binding (OHLC prefix + swing_policy) }
```

DataFrame hashing uses the project `canonical_sha256` (columns + dtypes + index + row order +
missingness + >2^53 ints + tz semantics + +0/−0 + Inf-reject). The composed surface identity binds
the three component hashes. `swing_policy` (EmpiricalConfirmationPolicy) is a reconstruction witness
input to 2.1A and must enter the reconstruction input binding (None ⇒ evidence-only), mirroring
Stage 4A's config-binding discipline.

**Self-integrity (Stage 4A lesson)**: the 4B-1 surface holds mutable DataFrames (2.1A/2.1B/2.1C
frames). `verify_surface_integrity` recomputes the three component hashes + composed surface_id from
CURRENT content and rejects any stale/forged field before any consumer reads it. Defensive deep copy
at the construction boundary.

---

## 3. Factual-availability matrix (per entity/event)

**Global rule (verified in code)**: all four engines are single-pass causal batch engines. Every
event and every per-bar state value is emitted at the bar being processed (`i`), computed from
history through `i` only. Therefore `event_position == first factual availability == bar i`, with
legal phase `COMPLETED_ROW_AVAILABLE` (or `RESEARCH_SNAPSHOT_AVAILABLE` for a research as-of).

**Origin is a positional Int64, never an InformationKey, and origin < availability in general.**
No delayed availability beyond event_position exists (no event is retroactively revealed).

| Entity/Event | origin (position) | event_position | distinct creation/confirmation | availability == event_position? | legal phase | same-row chronology knowable? |
| --- | --- | --- | --- | --- | --- | --- |
| **Liquidity** | | | | | | |
| LEVEL_CREATED | `source_origin_position` (swing origin) | = `source_confirmation_position` | creation == confirmation | YES | COMPLETED_ROW | NO (mechanical sort) |
| FIRST_TOUCH / FIRST_WICK_BREACH / FIRST_WICK_ONLY_EXCURSION / FIRST_CLOSE_BREACH / FIRST_RECLAIM_AFTER_CLOSE_BREACH | level origin (unchanged) | bar i of the touch/breach/reclaim | — | YES | COMPLETED_ROW | NO (SAME_INFORMATION_BATCH_ORDER_UNKNOWN) |
| **Order Block** | | | | | | |
| ZONE_CREATED | `origin_position` (eligible candle) | `creation_position` = i | creation == i; `search_boundary_position` = last swing | YES | COMPLETED_ROW | NO |
| FIRST_TOUCH / FIRST_FAR_SIDE_WICK_BREACH / FIRST_FAR_SIDE_CLOSE_BREACH / FIRST_CLOSE_RECLAIM_OF_FAR_SIDE | zone origin | bar i | — | YES | COMPLETED_ROW | NO |
| **FVG** | | | | | | |
| FVG_CREATED | `origin_position` = i−2 (middle i−1) | `creation_position` = i | origin=i−2 < creation=i | YES (visible at i) | COMPLETED_ROW | NO |
| FIRST_TOUCH / FIRST_FULL_RANGE_COVERAGE / FIRST_FAR_SIDE_WICK_BREACH / FIRST_FAR_SIDE_CLOSE_BREACH / FIRST_CLOSE_RECLAIM_OF_FAR_SIDE | fvg origin i−2 | bar i | — | YES | COMPLETED_ROW | NO |
| **Dealing Range** | | | | | | |
| range creation | first endpoint origin | `creation_position` = i (second endpoint confirmation) | creation == second confirmation; origin = first endpoint origin | YES | COMPLETED_ROW | NO |
| `current_range_*` persistence | (persists prior range) | per bar i | — | YES | COMPLETED_ROW | NO |
| invalidation `rejected_range_geometry` | — | bar i (width ≤ 0) | — | YES | COMPLETED_ROW | NO |

**Important correction**: for Liquidity, creation availability == `source_confirmation_position`
(the swing confirms at bar i and the level is created at the same bar). Origin (swing origin) is
strictly earlier. For OB/FVG/range, creation == event_position == i, origin earlier. In ALL cases
`availability == event_position`; origin must never substitute for availability.

**Key structural note (dealing range)**: `rejected_range_geometry` marks a candidate whose width ≤ 0;
the current range is NOT replaced by a rejected candidate (verified: `rejected[i]=True` with
`current` unchanged). A new range only replaces `current` when two opposite-side swings confirm.
This makes prior `current_range_*` as-of state immutable and prefix-stable.

---

## 4. Corrected ID-stability claim

- **FVG**: EMPIRICALLY established (24-bar prefix `[0..19]` == first 20 of 40-bar `[0..35]`).
- **Liquidity / Order Block / Dealing Range**: **NOT yet empirically established** — only a
  code-inspection hypothesis (all IDs are `len(collection)` under a causal creation loop).

BUILD must establish the invariant for these three by independently rebuilding a prefix-through-T
surface and a legally future-extended surface and asserting the prefix entity IDs are preserved.
If any fails → BLOCKER; do NOT silently introduce a replacement identity and do NOT patch the
CLOSED engine.

---

## 5. 4B-1 prefix / boundary semantics

- Stage 4B-1 stores **ONE full shared market structure surface** (computed once per surface
  identity), plus **compact legal prefix bindings** — NOT persisted per-prefix surfaces, and NOT
  per-hypothesis duplication.
- `project_structure_prefix(surface, boundary_key)` reuses the Stage 4A boundary contract exactly:
  legal phases only (`COMPLETED_ROW_AVAILABLE`, `RESEARCH_SNAPSHOT_AVAILABLE`); `BAR_PRE_CLOSE`
  rejected; `adapter.validate_key` for full InformationKey validation (positional no-timestamp,
  time-indexed timestamp correctness, cross-timeline rejection).
- The prefix identity through boundary T covers exactly the structure facts legally visible through
  T, using **factual availability** (== bar position for all 4B-1 fields), NOT origin. A field whose
  origin < T but whose event_position > T is excluded from the prefix through T.
- Full-surface identity changes on future append; prefix identity through T is immutable under a
  legally rebuilt future-extended surface (mandated per-domain prefix-stability test).

---

## 6. Remaining BLOCKERS

None. The three blockers are resolved by §1–§5. BUILD readiness is conditional on the 4B-1
prefix-stability + availability tests being written and green at BUILD time.

## 7. NON-BLOCKING DESIGN DEBT

- 2.1C chain is O(N) single-pass but 2.1A's candidate/percentile machinery is O(N) with
  `CausalPercentileTracker`; no hidden cost beyond CLOSED.
- `candidate_side` is `object` dtype in CLOSED (not `string`); canonical hashing must handle
  object-dtype columns deterministically (values are plain strings) — document this at BUILD.

## 8. RESEARCH QUESTIONS

None new. Predictive use of structure states belongs to future estimand work (debts remain OPEN).

## 9. Updated BUILD readiness verdict

```
DESIGN PROPOSAL — NOT IMPLEMENTED
NO DESIGN BLOCKER REMAINS FOR STAGE 4B-1 / 4B-2
BUILD NOT AUTHORIZED (pending explicit BUILD ONLY authorization)
```

Stage 4B may proceed as 4B-1 (shared structure surface) → 4B-2 (FVG + Liquidity + OB + Dealing
Range) once BUILD is authorized, with the availability matrix (§3) and ID-stability tests (§4) as
mandatory BUILD-time deliverables.

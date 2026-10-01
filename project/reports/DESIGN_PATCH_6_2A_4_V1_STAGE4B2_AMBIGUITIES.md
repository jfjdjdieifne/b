# DESIGN PATCH — Stage 4B-2 (final contract ambiguities)

Status: **DESIGN PROPOSAL — NOT IMPLEMENTED** (DESIGN PATCH ONLY)
Date: 2026-08-21

No code, tests, or files written. No MANIFEST change. Resolves ONLY the four flagged ambiguities.

---

## 1. Stage 4B-1 authoritative-input contract (unambiguous)

The authoritative structural input to Stage 4B-2 is the **CLOSED `Stage4B1StructureSurface` object
passed to the Stage 4B-2 builder** — there is exactly one structural input, not two.

Contract (this supersedes the prior wording):

- **A.** `build_*_surface(..., structure_surface: Stage4B1StructureSurface)` receives the CLOSED
  `Stage4B1StructureSurface` as its authoritative structural input (for Liquidity / OB / Dealing
  Range only; FVG takes none).
- **B.** Before consuming it, Stage 4B-2 calls `verify_surface_integrity(structure_surface)` — the
  CLOSED Stage 4B-1 public verifier that recomputes the component + composed hashes from the
  CURRENT frame content and rejects stale/forged fields.
- **C.** Stage 4B-2 binds the CLOSED identity fields verbatim into its own reconstruction witness /
  surface identity: `surface_id`, `timeline_id`, `timeline_hash`, `adapter_kind`,
  `contract_version`, `swing_policy_hash`, `reconstruction_input_hash`, `hash_2_1a/2_1b/2_1c`,
  `public_result_hash`.
- **D.** Stage 4B-2 does NOT independently claim historical provenance, and does NOT run its own
  2.1A→2.1B→2.1C chain.
- **E.** Stronger reconstruction verification is **AUDIT/TEST-ONLY, NOT mandatory during Stage 4B-2
  construction.** When performed (by an auditor or a test), it MUST use the CLOSED public builder
  `build_structure_surface(timeline=..., adapter=..., market_history=..., high_col=..., low_col=...,
  swing_policy=...)` with the authoritative timeline/market/policy inputs, then
  `verify_surface_matches_reconstruction(supplied, authoritative)` from the CLOSED 4B-1 contract.
  Stage 4B-2 never reimplements that chain privately.

**One unambiguous answer**: reconstruction verification is **optional / audit-and-test-only**. It is
NOT a required step of Stage 4B-2 surface construction, and Stage 4B-2 never takes a caller-supplied
"authoritative" surface in addition to the structural surface — there is a single structural input,
verified by `verify_surface_integrity` + identity binding.

---

## 2. Passthrough market binding (causality/data-integrity critical)

Stage 4B-1 self-integrity covers only its DERIVED columns; passthrough `high/low/close/open/volume`
are bound via the timeline seal, not the 4B-1 derived hash. Therefore Stage 4B-2 must independently
prove the passthrough columns correspond to the authoritative sealed market input BEFORE any domain
engine consumes them.

**Minimum correct binding (chosen, and mandatory):**

1. `timeline.verify(adapter=adapter, market_history=market_history)` — re-seal the authoritative
   market input and reject any timeline/market mismatch (CLOSED Stage 1 contract).
2. Compare the required passthrough market projection in `structure_surface.frame` against the
   authoritative `market_history` **exactly**, for the required columns, in order:
   `frame[["high","low","close"]]` must equal `market_history[["high","low","close"]]` (and
   `frame[["open"]]` for OB, `frame[["volume"]]` for volume-consuming domains where present).
   A mutation to any of these columns inside `structure_surface.frame` therefore fails the equality
   check even though `verify_surface_integrity` still passes.
3. Stage 4B-2 then runs the domain engine on a **defensive deep copy of `structure_surface.frame`**
   (so the domain engine's own `df.copy(deep=True)` and the 4B-2 boundary copy cannot alias the
   caller's mutable frame).
4. Stage 4B-2's reconstruction-input hash binds the authoritative timeline identity (not the
   passthrough frame columns directly), so a mutated frame cannot change the recorded reconstruction
   identity without failing step 2.

This is Stage-4B-2-local; CLOSED Stage 4B-1 is NOT patched.

---

## 3. Same-bar event ambiguity representation (exact, truthful)

The CLOSED engines do NOT emit an intrabar-ordering field. Stage 4B-2 must NOT fabricate one and
must NOT let the mechanical event-table ordering be read as market chronology.

**Chosen mechanism (one, truthful):** a **Stage-4B-2-derived event metadata field + a projection
invariant**, both marked as derived:

- Each normalized lifecycle-event row carries a derived boolean metadata column
  `same_information_batch_order_unknown` (a Stage-4B-2-derived fact, NOT a CLOSED source fact). It is
  set `True` when ≥2 lifecycle events share the same `event_position` (same factual OHLC information
  batch), `False` otherwise. This derived field is **included in the normalized-representation
  identity hash** (`STAGE4B2_<DOMAIN>_NORMALIZED_EVENTS_V1`), so it cannot be silently dropped.
- The normalized event table retains the deterministic CLOSED serialization (sorted by
  `event_position`, `entity_id`, fixed event-type order) as `serialization_order` — documented as
  mechanical ordering only.
- Projection/API contract invariant: any consumer that reads the event table is told (via the
  surface contract/docstring and the `same_information_batch_order_unknown` flag) that mechanical
  ordering is NOT intrabar market chronology. No public API exposes an ordering that could be
  truthfully interpreted as chronology.

A downstream research consumer therefore cannot truthfully read event-table order as intrabar
chronology: the flag is present on every ambiguous row and the ordering column is explicitly labeled
mechanical.

---

## 4. Corrected runtime domain safety guarantee (not "type-impossible")

Python does not provide compile-time type safety. The truthful contract is **strongly-typed
dataclasses for API clarity PLUS deterministic runtime validation**:

- Four distinct dataclasses (`Stage4B2LiquiditySurface`, `Stage4B2OrderBlockSurface`,
  `Stage4B2FVGSurface`, `Stage4B2DealingRangeSurface`), each with its own `domain` constant
  (`"LIQUIDITY"`, `"ORDER_BLOCK"`, `"FVG"`, `"DEALING_RANGE"`).
- The runtime field(s) that prevent cross-domain substitution are:
  1. `surface.domain` (a frozen per-class string constant), checked by every
     `verify_surface_integrity` and by every builder's `isinstance(surface, <ExpectedClass>)` +
     `surface.domain == <ExpectedDomain>` guard;
  2. the frozen per-domain output-schema tuples (entity/event/bar column lists), checked for exact
     equality at construction and re-checked in `verify_surface_integrity`.
- Wrong-domain substitution is rejected deterministically: passing an FVG surface to the Liquidity
  builder raises `TrajectoryContractError` (wrong class), and passing a forged object with the right
  class but a mismatched `domain`/schema raises `TrajectoryDataError` at the integrity check.

So the guarantee is: **domain/schema/contract mismatch is rejected deterministically at runtime via
the typed builder + `domain` field + exact-schema check** — not a Python type-system guarantee.

---

## 5. Classification

- **BLOCKERS**: none remaining. All four ambiguities are resolved by a single unambiguous contract
  each.
- **NON-BLOCKING DESIGN DEBT**: none new.
- **RESEARCH QUESTIONS**: none new.

## BUILD readiness verdict

```
DESIGN PROPOSAL — NOT IMPLEMENTED
NO DESIGN BLOCKER REMAINS FOR STAGE 4B-2
BUILD NOT AUTHORIZED (pending explicit BUILD ONLY authorization)
```

Stage 4B-2 may proceed as one BUILD once authorized, consuming CLOSED Stage 4B-1 as its single
authoritative structural input (verified via `verify_surface_integrity` + identity binding +
passthrough-market equality), FVG independent from the sealed timeline, with the derived
same-bar-ambiguity metadata and runtime domain-safety validation above.

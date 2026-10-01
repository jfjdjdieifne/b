# Patch Report — Stage 3 Complete Public-Result Equivalence

**Module 6.2A-4 V1 Stage 3 — Terminal / Censor Snapshots & As-Of Censor Series**

Date: 2026-08-18
Task Type: PATCH ONLY (close the deterministic-equivalence gap identified by read-only verification)
Role: Builder (NOT an Independent Audit)
Final status: **PATCHED / IMPLEMENTED — PENDING AUDIT**

---

## 1. Gap closed

The read-only verification confirmed the prior check proved only: envelope context, envelope
prefix hash, envelope count, and lifecycle terminal position/state — NOT the complete public
factual payload of CLOSED Stage 2. Factual row differences (e.g. `lifecycle_events.
trigger_relationship_id` 2 vs 999) were undetected behind equal envelope identities.

This patch adds a Stage-3-local canonical identity over the COMPLETE public factual content of
`TrajectoryStage2Result`, compared between supplied and reconstructed results, and stored in the
snapshot as `stage2_public_result_hash`.

## 2. Exact code changes (Stage 3 file only — no CLOSED module touched)

File: `src/trading_system/research/trajectory/trajectory_stage3.py`

1. **New `_stage2_public_result_hash(stage2_result, *, envelope_count, envelope_prefix_hash)`** —
   canonical identity over the complete public result, domain `STAGE2_PUBLIC_RESULT_EQUIVALENCE_V1`.
2. **`_verified_stage2_prefix`** now computes `supplied_public_hash` and `recon_public_hash` and
   rejects on any difference; return signature changed to `(count, prefix_hash, public_result_hash)`.
   Envelope context + terminal checks retained as defense-in-depth.
3. **`FactualTerminalSnapshot` / `RightCensoredAsOfSnapshot`** gain `stage2_public_result_hash` field;
   both builders bind it into the payload and the returned snapshot.
4. **Manifest** updated: `BINDING/STAGE2` includes `PUBLIC_RESULT_HASH`; new
   `BINDING/STAGE2_PUBLIC_RESULT_EQUIVALENCE` row; existing `STAGE2_DERIVATION_WITNESS` row retained.
5. Module docstring updated to describe the complete-result equivalence.

## 3. Public-result hash payload (exact)

`canonical_sha256(domain="STAGE2_PUBLIC_RESULT_EQUIVALENCE_V1", payload=...)` over:

| Component | Type |
| --- | --- |
| `price.price_bars` | DataFrame |
| `price.running_favorable_final` | float |
| `price.running_adverse_final` | float |
| `price.same_bar_ambiguous_count` | int |
| `structure.structure_events` | DataFrame |
| `lifecycle.lifecycle_events` | DataFrame |
| `lifecycle.terminal_position` | Optional[int] |
| `lifecycle.terminal_state` | Optional[str] |
| `envelope_count` | int |
| `envelope_prefix_hash` | str |

`price.points` are NOT separately serialized — see §4.

## 4. PriceTrajectoryPoint field-by-field coverage decision

**Decision: do NOT add a redundant custom serializer.** Every one of the 26 public
`PriceTrajectoryPoint` fields is transitively bound with identical semantics:

- Fields 1–21 (`bar_position` … `same_bar_order_ambiguous`): directly present as `price_bars` columns.
- Field 22 `observation_information_key`: bound transitively — it equals `envelope_bar.
  observation_information_key`, which is hashed into `envelope_id` (CLOSED `_envelope_hash`) and
  therefore into the envelope prefix hash.
- Field 23 `factual_available_at_key`: bound transitively via `envelope_bar.
  factual_available_at_information_key` → envelope_id → prefix hash.
- Fields 24–26 (`envelope_id_bar/fav/adv`): directly present as `price_bars` columns.

CLOSED `build_stage2_trajectory` constructs points and `price_bars` from the same loop with the
same values, and points' two InformationKeys are the exact keys bound into the bar envelope, so no
point field can diverge from `price_bars` + envelopes in a legitimately constructed result. The
mapping is documented verbatim in the function docstring.

## 5. DataFrame canonicalization verification (mandate §4)

`canonical_sha256` → `_dataframe_payload` was verified to satisfy: duplicate columns rejected;
column order preserved (NOT reordered — order is intentional and part of the public result); row
order preserved (NOT sorted — row order is part of the public result, and CLOSED Stage 2 emits
rows in a deterministic order); dtypes included (`dtypes` list); nullable values preserved
(`pd.NA`/`NaN` → canonical `missing`); >2^53 ints preserved (`str(value)`); tz-aware timestamps
canonicalized to UTC ns; NaN → missing (no raise); +0/−0 preserved via float hex. Inf raises
`ResearchHashError` → converted to `TrajectoryDataError`; no Inf occurs in legitimate Stage 2
output (OHLC validated finite; excursions are ratios of finite values).

## 6. Ledger A vs B result (mandate §7)

- Ledger A (`trigger_relationship_id=2`) supplied; ledger B (`999`) as reconstruction witness;
  same terminal state/position; envelopes equivalent.
- **Result: REJECTED** — `Stage 2 public result mismatch` (previously ACCEPTED).

This rejects because reconstruction(B) != the supplied complete public factual result once
`lifecycle_events` is included — NOT because B is non-historical input.

## 7. Policy equivalence result (mandate §8)

- Policy A (`quantile=0.3` + seeded priors) built; policy B (`0.95`) claimed → materially
  different structure trajectories → **REJECTED** (`envelope count mismatch` 10 vs 8).
- Policy A == A → **ACCEPTED** (deterministic equivalence).
- Historical generating policy remains NOT CERTIFIED / UNVERIFIABLE.

## 8. Mutation-test results (mandate §9)

| Mutated family | Result |
| --- | --- |
| `price.price_bars` close value | REJECTED — `public result mismatch` |
| `price.running_favorable_final` | REJECTED — `public result mismatch` |
| `structure.structure_events` (empty → synthetic non-empty) | REJECTED — `public result mismatch` |
| `lifecycle.lifecycle_events.trigger_relationship_id` (2 → 999) | REJECTED — `public result mismatch` |
| `lifecycle.terminal_state` (CONTRADICTED → SUPERSEDED) | REJECTED |
| `all_envelopes` (drop one envelope) | REJECTED (count/prefix) |

All mutations performed via safe frozen `dataclasses.replace` (no illegal CLOSED-object mutation).

## 9. Tests

| Metric | Value |
| --- | --- |
| Stage 3 dedicated tests | **81** (74 prior − 1 replaced + 2 new + 6 mutation) — all pass |
| Total collected | **818** |
| Total passed | **818** (3m48s) |

Replaced: `test_blocker2_derivation_witness_not_input_provenance` (asserted ACCEPT) →
`test_blocker2_ledger_row_fact_difference_rejected` (asserts REJECT) +
`test_blocker2_matching_ledger_accepted_with_derivation_witness`.

## 10. Hashes

```
trajectory_stage3.py    e79a61cf85ce0ba5cb3dfcd3db63b8fcdbe8d53243bb28855eb0bc91dad2dc8e
test_trajectory_stage3.py  2777fd6661847226b91c1294234713e93a1e861d5f6845a164f3e89e523e8d28
```

## 11. CLOSED integrity

- `sha256sum -c MANIFEST.sha256` → **154 / 154 OK** (no FAILED line).
- Stage 2 accepted hashes unchanged:
  - `trajectory_stage2.py` `827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f` ✓
  - `test_trajectory_stage2.py` `bb5372fbad3582ce81d64b5d791b3599504b4ee12775767f77d93763f9bb1c6d` ✓
- No `__init__.py`, no CLOSED production module, no existing non-Stage-3 test modified; MANIFEST not updated.

## 12. Preserved semantics

Envelope context verification, Stage 2 internal reconstruction, derivation-witness semantics
(`reconstruction_swing_policy_hash` / `reconstruction_ledger_seal` / `stage2_reconstruction_binding_hash`),
supplied-artifact origin extraction, 6.2A-1 authority, terminal-vs-research-as-of separation,
censor semantics, origin rule, compact storage, no fallback, no historical input-provenance claim —
all retained.

## 13. Remaining limitations

- `price.points` are covered transitively (documented §4), not by a dedicated serializer; if a
  future auditor demands direct point serialization, it is a small additive change, not a
  correctness gap for legitimate CLOSED results.
- Performance debt unchanged: reconstruction re-runs Stage 2 per snapshot; no caches.
- Historical generating-input identity remains UNVERIFIABLE (CLOSED Stage 2 does not seal it);
  `stage2_public_result_hash` is derivation equivalence only.

## 14. Final status

```
PATCHED / IMPLEMENTED — PENDING AUDIT
```

Not an Independent Audit. Not ACCEPTED. Not CLOSED. Stage 4 not started.
RESEARCH-DEBT-020 … 025 remain OPEN.

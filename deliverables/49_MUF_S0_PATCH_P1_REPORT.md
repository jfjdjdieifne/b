# MUF V1 S0 — PATCH P1: DEEP IMMUTABILITY + COMPLEXITY (BLOCKERS B1/B2/B3)

- Task: PATCH P1 (OWNER REVIEW OVERRIDE: PATCH REQUIRED) — three provable blockers only.
- Project: `project/trading_project/`
- Status: `PATCHED — PENDING RE-AUDIT`
- Date: 2026-09-30
- Scope note: NOT a redesign. Only `records.py`, `availability.py`, and the two S0
  test files were touched. No S1, no MANIFEST update, no docs edit, no closure, no
  zip, no owner-data access.

---

## 1. Before / after hashes (the 4 allowed files only)

| File | BEFORE | AFTER |
|---|---|---|
| `src/trading_system/market_understanding/records.py` | `946cb8ac71555db3b87148ce79013363caefdce662248481bf47bb83ea8f0fd3` | `2d2d5dac786a0d102482f6222a52403968e48e988db1871bf78e6db8b827825a` |
| `src/trading_system/market_understanding/availability.py` | `b07bd270c9cc35fd4ecc88e256a9e9e1bbd8f9d7f381bb0d138448814f78b1a6` | `c372677cc6b00107386d881e206f78dcf1f7061a99a58047fd6fc5a08f6a1e35` |
| `tests/test_muf_s0_records.py` | `cb29c650244ec03518e416d0c0c89598a9adf47822662aa420ddf1dea0e73461` | `63ba7af62848e240819428499fca5992212dfe698bcf6879b052a03923fe3f1f` |
| `tests/test_muf_s0_availability.py` | `f51fb3829507344eb471d1bca02848c3e08b5951643185364bdc31e45ad4b130` | `5394c731cb5cc971a5f9df55a8601b40d56e0f21bb31d2f891fd401c3980ca40` |

**MANIFEST pre/post: `12c66abe6f18300f2e00cb5c4befeafe1e3dc67c2ca50bc71db74db9ba8b367d`
— UNCHANGED (verified byte-identical after the patch; its 185/185 entries still
match: `MANIFEST_ENTRIES_VERIFIED=185`).**

## 2. NON-TOUCH evidence (before snapshot vs after)

- `src/` + `tests/` outside the 4 allowed files: **110/110 files byte-identical**
  (DIFF list contains exactly the 4 allowed files and nothing else).
- `docs/` + `field_runner/`: **107/107 files byte-identical** (no cache drift either).
- `identity.py` / `contracts.py`: untouched (both still match their snapshot hashes).
- No deliverable zip produced (no owner order for one in this task).

## 3. B1 — DEEP IMMUTABILITY (`records.py`) — before/after

**Before:** `PublishedRecord.content` and `EventRecord.event_payload` were wrapped
`MappingProxyType(dict(...))` — external key assignment blocked, but nested
containers remained caller-aliased and mutable (`record.content["features"]["x"] = 1`
succeeded; `record.content["features"] is caller_dict["features"]` was True).

**After:** construction runs `freeze_payload()` — a deterministic recursive freeze
(I-DEEP-1..5), O(payload_size):

| Input type | Result |
|---|---|
| `str` / `bool` / `int` / `float` / `None` | preserved as-is |
| `Enum` members (e.g. `TypedState`, `InformationPhase`) | preserved as-is |
| `InformationKey` / `SchemaIdentity` | preserved as-is (frozen objects) |
| `Mapping` with **str** keys | recursively frozen `FrozenPayloadDict` |
| `list` / `tuple` | recursively frozen `tuple` |
| `set` / `frozenset` | **`SchemaViolation`** (unordered collections not permitted) |
| non-str mapping key | **`SchemaViolation`** |
| any other object (incl. custom objects with `__dict__`) | **`SchemaViolation`** — never blindly deep-copied, FAIL CLOSED |

- `FrozenPayloadDict` is a dict subclass (not `mappingproxy`) so the approved public
  `canonical_payload` dict dispatch and hash semantics are preserved:
  **`canonical_sha256(raw) == canonical_sha256(frozen)`** (asserted in test P1-A;
  list-vs-tuple both hash as sequences).
- All mutation entry points (`__setitem__`, `__delitem__`, `__ior__`, `update`,
  `pop`, `popitem`, `clear`, `setdefault`, `__setattr__`, `__delattr__`) raise
  **`ImmutabilityViolation`** — top-level AND every nested level. Construction
  copies structurally (caller alias cut: mutating the source dict after
  construction does not touch the stored payload — test P1-B).
- String subclasses (str domain) are preserved as-is (same object, no eq/hash
  re-encoding — instrumented probe asserts zero calls during freeze).
- Error-family note (contract note for the audit): payload-mutation refusal is now
  `ImmutabilityViolation` (the P1 order's expected value) rather than the
  `mappingproxy`-era `TypeError`; the corresponding expectation in the allowed
  test file (attack11) was updated to match. The frozen docs text was not touched
  (NON-TOUCH).

## 4. B2 — LEDGER O(n²) → amortized O(1) (`records.py`) — before/after

**Before:** `append()` did a linear `for existing in self.__events: if
event.event_identity == existing.event_identity` scan — O(n²) over N appends.

**After:** `AppendOnlyEventLedger` keeps a private name-mangled identity index
(`__identity_index`); duplicate detection is `in` on the index then `add` —
amortized O(1) per append. The ordered event history list remains the sole
projection source (I-LEDGER-4: order and forward projections identical to
pre-patch — asserted in test P1-F). The index is not publicly observable
(I-LEDGER-2). No max-history / eviction (I-LEDGER-3). Events remain the
constrained objects; the public identity is the `event_identity` string.

## 5. B3 — EARLIEST O(R×S) → O(R+S) (`availability.py`) — before/after

**Before:** `all(basis <= candidate for basis in rule.required_basis_keys)` for
every satisfaction key — R×S public comparisons.

**After — single-scan O(R+S) using ONLY the sealed public comparator:**

1. `boundary = max(required_basis_keys)` computed with `>` (O(R)) — legal only if
   every basis key is legally comparable; any `InformationKeyError` (cross-timeline,
   version mismatch, or same causal coordinate with conflicting timestamp
   provenance — all raised by `InformationKey._ordering_operands`) is wrapped as
   `IncomparableInformationKeys` / `NOT_COMPARABLE` — fail closed.
2. One scan over `satisfaction_keys` (O(S)): keep the earliest `candidate` with
   `boundary <= candidate`.
3. Compare the proposal against that earliest key with the public semantics only:
   equal → return; later → `NonEarliestAvailability`; earlier → `PrematureAvailability`;
   any comparison error → `IncomparableInformationKeys` (NOT_COMPARABLE).

- **No invented tuple ordering** — only the pre-existing public `InformationKey`
  comparison semantics (which order by `bar_position, information_phase,
  deterministic_sequence` and themselves fail closed on mixed provenance at one
  causal coordinate).
- **Permutation invariance:** max/min over a legal order is order-independent;
  asserted over all 2×24 input permutations (test P1-J). Input ordering never
  determines the answer (I-EARLY-5).
- RULE constraint stayed intact: `identity.py` / `contracts.py` untouched — the
  trigger (earliest == the sealed rule's declared boundary semantics) is unchanged
  on the information_time side.
- Determination-time checks preserved (attack15 pattern: rules with cross-timeline
  keys fail at construction/determination, not silently at use).

## 6. Complexity evidence (measured, deterministic counters — not wall-time)

| Measurement | N | 2N | 4N | ratio 2N/N | ratio 4N/N | verdict |
|---|---|---|---|---|---|---|
| `AppendOnlyEventLedger.append` executed lines (sys.settrace) | 500 → 2000 | 1000 → 4000 | 2000 → 8000 | 2.00 | 4.00 | linear (exactly 4 lines/append) |
| earliest public key comparisons (counting probe keys) | 256 → 767 | 512 → 1535 | 1024 → 3071 | 2.00 | 4.00 | linear (exactly 3N−1) |

A restored linear scan or restored R×S cross-product makes these ratios jump to
~4 (2N/N) and ~16 (4N/N) — proven by the mutation proofs below. Gates in the
tests: ledger `1.6 ≤ r2 ≤ 2.6`, `3.2 ≤ r4 ≤ 5.2`; earliest `1.6 ≤ r2 ≤ 2.8`,
`3.2 ≤ r4 ≤ 5.6`.

## 7. Value-domain contract for frozen payloads (B1)

See the table in section 3. Summary: primitives/Enum/InformationKey/SchemaIdentity
preserved as-is; str-keyed mappings recursively frozen; sequences recursively
frozen to tuples; sets/frozensets, non-str keys, and any other object raise
`SchemaViolation` (FAIL CLOSED — no semantics invented, no deep-copy of
execution objects).

## 8. Tests A–L (mandatory, in the two allowed test files)

| # | Test (function) | Result |
|---|---|---|
| A | `test_p1_a_deep_alias_introspection_and_identity_preservation` | PASS |
| B | `test_p1_b_direct_nested_mutation_fails_closed` | PASS |
| C | `test_p1_c_nested_list_and_sequence_freezing` | PASS |
| D | `test_p1_d_event_payload_deep_frozen` | PASS |
| E | `test_p1_e_unsupported_objects_fail_closed_str_subclass_preserved` | PASS |
| F | `test_p1_f_ledger_projection_unchanged_by_duplicate_rejection` | PASS |
| G | `test_p1_g_duplicate_identity_rejected_via_unique_index` | PASS |
| H | `test_p1_h_ledger_append_operation_count_scales_linearly` | PASS |
| I | `test_p1_i_earliest_matches_pre_patch_reference_fixture` | PASS |
| J | `test_p1_j_earliest_permutation_invariant` | PASS |
| K | `test_p1_k_earliest_comparison_count_scales_linearly` | PASS |
| L | `test_p1_l_incomparable_keys_fail_in_documented_error_family` | PASS |

- A: alias introspection (nested equality pairs are distinct objects; identity
  objects survive by identity) + I-DEEP-5 canonical hash equality.
- B: all 8 nested mutators + nested-inner write → `ImmutabilityViolation`;
  construction-time caller alias cut.
- C: nested list in mapping frozen to tuple; nested mapping inside sequence frozen.
- D: `event_payload` deep-frozen (nested too) with `ImmutabilityViolation` on writes.
- E: set/frozenset/set-in-list/object-in-tuple/object/custom-object/non-str-key →
  `SchemaViolation`; str subclass preserved with zero eq/hash calls.
- F: duplicate rejection leaves projection tuple and `project_status` untouched;
  insertion order preserved.
- G: same `event_identity`, different payload → duplicate rejected via index.
- H: executed-line counter inside `append` scales linearly at N, 2N, 4N.
- I: **reference equivalence vs pre-patch algorithm frozen in the test fixture**
  (30 seeded rules + empty-basis case; expected earliest equal; Premature /
  NonEarliest families equal; empty-candidate failure equal).
- J: earliest identical across all permutations of basis and satisfaction inputs.
- K: public comparison counter (counting `InformationKey` subclass) scales linearly
  at R=S=N, 2N, 4N.
- L: incomparable inputs (cross-timeline basis/satisfaction/proposal; same causal
  coordinate with conflicting timestamp provenance) raise the documented family
  `IncomparableInformationKeys` with code `NOT_COMPARABLE` — no new error invented.

## 9. Mutation proofs (outside the repository — `/tmp`; repo restored after each)

| # | Mutation | Target test | Result |
|---|---|---|---|
| 1 | remove recursive freeze (shallow `FrozenPayloadDict(value)` only) | P1-A..D | **4 failed** (A,B,C,D) → restored → 2/2 green |
| 2 | restore linear scan in `append` | P1-H | **1 failed** (op-count gate) → restored → 1/1 green |
| 3 | restore R×S `all(basis <= candidate)` cross-product | P1-K | **1 failed** (comparison-count gate) → restored → 1/1 green |

Mutation backups: `/tmp/p1_records_restore.py`, `/tmp/p1_availability_restore.py`
(kept outside the repository). Post-restore hashes equal the AFTER hashes in
section 1 — no mutation residue.

## 10. Full verification after the patch

| Gate | Result |
|---|---|
| S0 suite (`test_muf_s0_records/availability/identity/contracts`) | **49/49 PASS** (records 16, availability 14, identity 13, contracts 6) |
| Full project test suite | **1121/1121 PASS** (1109 pre-patch + 12 new P1 tests) |
| Field runner self-tests (`field_runner/runner_tests`) | **36/36 PASS** |
| MANIFEST (`MANIFEST.sha256`) | `12c66abe…` UNCHANGED; 185/185 entries verified |
| NON-TOUCH (src/tests outside 4 files) | 110/110 byte-identical |
| NON-TOUCH (docs + field_runner) | 107/107 byte-identical |

## 11. Boundaries held

- No S1 work; no MANIFEST update; no docs edit; no closure report; no zip.
- `identity.py` / `contracts.py` untouched (stop-sign respected).
- Owner-data boundary: no owner artifacts read or claimed; tests use synthetic
  fixtures only.
- Public `InformationKey` comparison semantics used as-is; no invented ordering;
  `TIE_ORDER_CONTRACT = NOT_PROVEN` unchanged.
- Complexity honest: construction O(payload_size) documented as such (not O(1)).

---

## STATUS

**`PATCHED — PENDING RE-AUDIT`**

All three blockers are fixed and proven (before/after + measured complexity +
mutation proofs + A–L tests). Nothing was closed. Closure remains forbidden
until the owner accepts the re-audit.

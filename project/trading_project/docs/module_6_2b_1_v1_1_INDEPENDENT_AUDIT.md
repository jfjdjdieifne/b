# Independent Audit Report — Module 6.2B-1 V1.1

```text
Module:   6.2B-1 — Walk-Forward Adaptive Confluence Calibration
Version:  V1.1 (V1 integrity patch)
Builder:  (previous Builder AI)
Auditor:  Independent Auditor AI (read-only)
Date:     2026-08-16
Decision: ACCEPTED FOR CLOSURE
```

This audit was performed **read-only against the actual code and tests**, not
against the Builder's self-report. Every claim below was independently
reproduced.

---

## 1. What was received

```text
ZIP SHA-256 (outer): e016f6ab9a9c3bde2c6ad6a6da7404981e494efa2adfac6e8d6bff2012338d30
CLOSED MANIFEST:     MANIFEST.sha256 — 133 entries
PENDING B-1 files:   PENDING_6_2B_1_V1_1.sha256 — 5 entries
Declared baseline:   683 collected / 683 passed
```

B-1 adds one new source package and two new test files plus this audit trail;
no CLOSED source/test file is touched.

---

## 2. Integrity verification (independently run)

| Check | Command | Result |
|---|---|---|
| Outer ZIP hash | `sha256sum` | `e016f6ab…8d30` **MATCH** |
| CLOSED manifest | `sha256sum -c MANIFEST.sha256` | **133 / 133 OK** |
| Pending B-1 hashes | `sha256sum -c PENDING_6_2B_1_V1_1.sha256` | **5 / 5 OK** |
| B-1 inside closed manifest? | grep | **No** (correctly isolated) |
| Closed files unchanged by B-1 | manifest verify post-run | **unchanged** |

The five pending files are byte-identical to the declared hashes and are
correctly excluded from the CLOSED manifest (closure is not yet certified).

---

## 3. Test execution (independently run)

Environment: Python 3.13, numpy 2.3.5, pandas 2.2.3, pytest 8, editable install.

```text
B-1 unit tests:        tests/test_adaptive_confluence_calibration.py  -> 27 passed
B-1 integration tests: tests/test_adaptive_confluence_calibration_integration.py -> 2 passed
B-1 total:             29 passed
Full suite:            683 collected / 683 passed   (179.32s)
Run with -W error:     29 passed, zero warnings
```

Arithmetic is exact: the certified CLOSED baseline was 654; B-1 adds 29;
654 + 29 = **683**, matching the declared full baseline.

CLOSED baseline references in `README.md`, `PROJECT_HANDOFF_MAP.md`,
`docs/STATUS.md`, and `docs/FINAL_VALIDATION.md` still read **654** — this is
correct and intentional. Those documents describe the CLOSED milestone and
must not be edited until B-1 is formally closed. `SNAPSHOT_STATUS.md` and the
B-1 audit report correctly read **683**.

---

## 4. Independent adversarial testing

Beyond running the Builder's tests, this auditor constructed fresh attacks
against a real built artifact:

| Attack | Expected | Observed |
|---|---|---|
| Mutate TEST feature values (then authentically reseal) | `calibration_content_hash` unchanged; source seal changes | **PASS** |
| Mutate TEST target payload (then reseal) | TRAIN content unchanged | **PASS** |
| Tamper `artifact_manifest` field after build | verifier rejects | **PASS** ("final artifact hash mismatch") |
| Tamper a component table (`family_observation_coverage`) after build | verifier rejects | **PASS** ("artifact component hash mismatch") |

---

## 5. Causal / leakage review (source-level)

Static scan of `src/trading_system/calibration/adaptive_confluence.py`:

- `shift(-1)`, centered rolling, `bfill/backfill`, future-backfill patterns:
  **none found**.
- No predictive/probability/weight/signal/BUY/SELL/PnL/entry/stop/target
  output. (The token `entry` appears only as `ledger_entry`, i.e. experiment
  accounting, not a trade entry.)
- TEST data is used **only** to reproduce and compare the CLOSED
  `_fold_manifest` source seal. The `calibration_content_hash`, component
  hashes, and all fitted tables are computed from TRAIN projections only.
- The CLOSED `cross_split_label_overlap_detected` field (which is
  TEST-cohort-derived) is explicitly excluded from TRAIN identity and
  diagnostics and emitted as `NOT_ACCESSED_OOS_FIREWALL`.
- All TRAIN outcomes are gated by `final_outcome_known <= train_cutoff` and
  `label_interval_end_inclusive <= train_cutoff`.
- The reasoning decision key is gated `<= train_cutoff`.

## 6. Dependency-direction review

```text
calibration  ->  reasoning.evidence_families  (CLOSED)
calibration  ->  research.dataset_builder/contracts/eligibility/hashing/information_time (CLOSED)
CLOSED modules  ->  calibration :  NONE
```

No CLOSED module imports `trading_system.calibration`. (The string
`calibration` inside closed files is the pre-existing column
`included_for_independent_calibration` and two comments — not imports.) The
LIVE/RESEARCH boundary is preserved: Layers 0–5 and reasoning do not gain any
outcome/label/excursion import.

## 7. Objective / epistemic boundary review

The code enforces at the constructor and builder level that V1:

- sets `objective_id = OBJECTIVE_UNDEFINED_RESEARCH_DEBT_020`;
- rejects any non-`TRAIN_DESCRIPTIVE_ONLY` evaluation role;
- rejects any preprocessing other than `IDENTITY_TYPED_NO_FITTED_TRANSFORM_V1`;
- rejects any model spec other than `NO_PREDICTIVE_MODEL_…_V1`;
- rejects non-empty `hyperparameters_json`;
- builds **no** `QualificationCalibrationArtifact`;
- labels every empirical CDF row `TRAIN_EMPIRICAL_CDF_NOT_PROBABILITY`;
- labels every coverage row `TRAIN_OBSERVATION_COVERAGE_NOT_SEMANTIC_OR_PREDICTIVE_SUPPORT`;
- emits `DEPENDENCE_NOT_RESOLVED` and never claims IID/independence;
- separates ACTUAL vs PROXY without predictive priority;
- preserves UNKNOWN and UNAVAILABLE with no zero-fill or renormalization;
- carries caller-reported OOS access as `CALLER_REPORTED_ACCOUNTING_NOT_ACCESS_CONTROL`.

`RESEARCH-DEBT-020/021/023/024` remain explicitly open in diagnostics and in
the audit report — they are not silently claimed as solved.

## 8. Identity / provenance review (V1.1 patch)

The V1.1 integrity patch was the central risk area and it is sound:

- **CLOSED fold source seal:** before any TRAIN projection, the exact CLOSED
  `CausalResearchDatasetBuilder._fold_manifest` is recomputed and compared
  exactly (`check_exact=True`). Forged/partial fold hashes reject.
- **Canonical sample IDs:** recomputed through the CLOSED `_sample_id`
  (fold id + frozen decision snapshot). Arbitrary aliases reject.
- **Authoritative B-0 membership:** for every sample the frozen snapshot is
  re-verified, the `ReasoningDecisionSnapshot` reconstructed, the B-0 reasoner
  re-run, and every normalized output table compared exactly. Added/removed
  records, provenance forgery, aliased sources, and altered manifest/hashes
  all reject. Final record hashes are recomputed and checked.
- **TRAIN raw row:** `FrozenDecisionFeatureSnapshot.raw_feature_row()` is
  compared exactly against the sealed 6.2A-3 TRAIN row; index-only matching
  is not enough. Mutating a TRAIN numeric feature (even after resealing)
  rejects.
- **Hash layering** is correctly separated:
  `source_dataset_fold_hash` (full provenance, may move with TEST) vs
  `training_projection_hash` / `calibration_content_hash` (TRAIN-only) vs
  `artifact_hash` (final identity). The verifier recomputes all of these
  without touching TEST payload values.
- **Ledger:** chained `previous_entry_hash` with an externally trusted head;
  mutation, reorder, truncation, wrong-head append, and duplicate
  `experiment_id` all reject. Failed attempts are representable. The head
  remains an external authority boundary (correctly not self-certified).

These claims were each independently reproduced; the Builder's unit tests for
them are genuine adversarial tests (tamper-then-reseal), not tautologies.

## 9. Minor observations (non-blocking)

These are **not** defects requiring a patch; they are documented limits that
the report already discloses and that are appropriate for V1:

1. The source seal is unkeyed integrity, not trusted-issuer authentication.
   Acknowledged in §V1.1 remaining limits. Correct scope.
2. `factual_outcome_id` is bound through syntax + the verified CLOSED fold
   seal rather than recomputed from the factual batch, which is not carried
   into B-1. Acknowledged; the strongest binding available at this boundary.
3. The trusted ledger head and caller-reported OOS count are external
   authority/accounting, not technical access control. Acknowledged and
   labelled machine-readable as such.
4. One authoritative TRAIN fold per artifact. Appropriate for V1.
5. Empirical CDF is descriptive, not a probability or forecast. Labelled on
   every row.

None of these violates the CLOSED contracts or the constitution. They are the
honest boundaries of a V1 descriptive foundation and should remain open for
later, separately-authorized modules.

---

## 10. Decision

```text
ACCEPTED FOR CLOSURE
```

Rationale:

- All five pending files match their declared hashes and are isolated from the
  CLOSED manifest.
- 683/683 tests pass independently under a clean environment; B-1 contributes
  exactly 29 tests (27 unit + 2 real CLOSED-pipeline integration).
- No CLOSED source or test file was modified.
- The causal/OOS firewall holds under independent adversarial testing.
- Dependency direction is one-way (calibration depends on CLOSED; never the
  reverse).
- No predictive, probabilistic, weight, signal, geometry, or execution output
  is produced; `RESEARCH-DEBT-020/021/023/024` remain openly unresolved.
- The V1.1 integrity patch correctly seals CLOSED source provenance, canonical
  sample identity, authoritative B-0 membership, TRAIN raw rows, separated
  hash layers, and a tamper-evident ledger.

### Required closure-authority actions (not code changes)

This audit certifies the **src/tests/docs content** for closure. Per the
collaboration constitution, the **Closure/Release Agent** (not the Builder,
not the Auditor) may now, on explicit Product-Owner authorization:

1. Promote `Module 6.2B-1 V1.1` to **CLOSED** in `docs/STATUS.md`.
2. Update `README.md`, `PROJECT_HANDOFF_MAP.md`, and `docs/FINAL_VALIDATION.md`
   certified baseline from `654` to `683`.
3. Regenerate `MANIFEST.sha256` to include the five B-1 files (133 → 138
   entries), and record the accepted `src/tests` hash set (mirroring the
   `docs/releases/` pattern used for 6.2B-0 V1.2).
4. Add a `docs/releases/MILESTONE_6_2B_1_V1_1_CLOSED.md` note.
5. Leave `RESEARCH-DEBT-020/021/023/024` open; do not start 6.2C / 6.2D / any
   model-scorer-signal work without a new explicit task block.

Until those release actions are taken, the snapshot state remains
`B-1 PATCHED/IMPLEMENTED — PENDING AUDIT`; after this report the audit verdict
itself is **ACCEPTED FOR CLOSURE**.

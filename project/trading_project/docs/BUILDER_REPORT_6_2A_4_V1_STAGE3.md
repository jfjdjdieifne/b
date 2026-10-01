# Builder Report — Module 6.2A-4 V1 Stage 3

**Terminal / Censor Snapshots & As-Of Censor Series**

Date: 2026-08-18
Builder: Builder AI (Arena.ai Agent Mode)
Task Type: BUILD ONLY
Status: **IMPLEMENTED — PENDING AUDIT** (not ACCEPTED, not CLOSED)

---

## 1. Files changed

| File | Action | Notes |
| --- | --- | --- |
| `src/trading_system/research/trajectory/trajectory_stage3.py` | MODIFIED (BUILD) | Strengthened Stage 2-vs-6.2A-1 mismatch rejection (see §7) |
| `tests/test_trajectory_stage3.py` | CREATED | 66 adversarial tests |

No CLOSED production file was modified. No existing test was modified.
`MANIFEST.sha256` was NOT modified (154 entries remain byte-identical).

## 2. SHA-256 of new/current Stage 3 files

```
74d1552fd5d7e729393af6ea1a3d20c842146ff6f972b186f243a80ef797b483  src/trading_system/research/trajectory/trajectory_stage3.py
ca6e894a16cd1bebabd9cda791e8dd6cfefc2b4ecd306ab4ebc497d66ac87d26  tests/test_trajectory_stage3.py
```

Stage 2 accepted hashes (unchanged, re-verified):

```
827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f  trajectory_stage2.py
bb5372fbad3582ce81d64b5d791b3599504b4ee12775767f77d93763f9bb1c6d  test_trajectory_stage2.py
```

## 3. Test counts

| Metric | Value |
| --- | --- |
| Stage 3 dedicated tests added | **66** |
| Stage 3 dedicated tests passing | **66 / 66** |
| Full suite collected | **803** |
| Full suite passed | **803 / 803** (3m28s) |
| Pre-existing baseline | 737 (unchanged, all still pass) |
| `pytest --collect-only -q` | 803 collected |

## 4. Proof all CLOSED files unchanged

- `sha256sum -c MANIFEST.sha256` → **all 154 entries OK** (no FAILED line).
- `trajectory_stage2.py` and `test_trajectory_stage2.py` re-hash to the accepted Stage 2 values (see §2).
- No `__init__.py` was modified. Stage 3 is imported directly by module path in tests, per the BUILD-only rule.
- Full suite (737 pre-existing) still passes, proving no regression to CLOSED modules.

## 5. Mandatory design corrections — compliance

1. **Empty lifecycle ledger identity** — COMPLIANT. `_empty_ledger_canonical_df()` returns a zero-row
   DataFrame with the exact required columns, exact canonical column order, and exact dtypes
   (`Int64` / `string`). It is hashed through the SAME `HYPOTHESIS_LIFECYCLE_LEDGER_INPUT_BINDING_V1`
   domain and SAME canonical hashing path as a non-empty ledger. No `{"empty": true}` payload exists.
2. **Stage 2 artifact hash** — COMPLIANT. `stage2_artifact_hash` is recorded only as release/audit
   provenance. The semantic `stage2_input_binding_hash` binds: Stage 2 contract version, timeline
   id/hash, anchor hash, decision snapshot hash, interval id/hash, observed bar count, swing-policy
   input binding, lifecycle-ledger input binding; plus a separate canonical trajectory-prefix hash
   and envelope count.

## 6. Stage 3 contract summary

- `TRAJECTORY_STAGE3_CONTRACT_VERSION = "CAUSAL_TERMINAL_CENSOR_SNAPSHOT_V1"`
- **Authority**: 6.2A-1 is authoritative for mature/censored/terminal classification; Stage 2 is
  authoritative for PRICE/STRUCTURE/LIFECYCLE trajectory. Stage 3 never re-decides terminal state
  from price or raw ledger, and never falls back when an authoritative input is missing/ambiguous/
  invalid/inconsistent (STOP with `TrajectoryDataError`/`TrajectoryContractError`).
- **Two clocks**: `terminal_factual_available_at_information_key` (T12) vs
  `research_as_of_information_key` (T15) are preserved as distinct facts; the trajectory interval
  still ends at the terminal boundary (T12); no T13+ market facts enter the terminal trajectory.
- **Origin rule**: terminal origin preserved exactly as the CLOSED source supplies it — an Int64
  `event_position` (plus `ledger_event_id`, `trigger_relationship_id`, `superseded_by_hypothesis_id`),
  never a manufactured InformationKey.
- **Censor semantics**: `RIGHT_CENSORED_AS_OF_BOUNDARY` only. `research_snapshot_id` present,
  `factual_outcome_id` NA, `outcome_mature=False`, `right_censored_as_of=True`. No invented censor
  reasons.
- **Literal terminals only**: `CONTRADICTED`, `SUPERSEDED`, `OBSERVED_DIRECTION_ESTABLISHED`.
  No WIN/LOSS/SUCCESS/FAILURE/PROFIT/PnL/entry/stop/target semantics.
- **Storage**: compact references only — interval identity, Stage 2 input-binding identity,
  trajectory-prefix hash, envelope count, factual outcome binding, research as-of, terminal factual
  availability. No raw market history, no full envelope tuple, no duplicated running payloads, no
  delta-envelope optimization. Envelope IDs are not assumed prefix-stable.

## 7. Deviation from approved design (the one code change made)

The pre-existing Stage 3 `src` softened its Stage 2-vs-6.2A-1 consistency check with
`except AttributeError: pass` and skipped mismatches when Stage 2 lifecycle had no terminal
(`terminal_position is None`). The BUILD-only mandate explicitly requires "mismatch rejection,
no-fallback behavior" and the required tests "terminal position mismatch vs Stage 2 rejection" and
"terminal state mismatch vs Stage 2 rejection".

Change made (single block in `build_mature_terminal_snapshot`): the check now hard-rejects when
(1) the Stage 2 result lacks a lifecycle trajectory, (2) Stage 2 lifecycle has no terminal within
the interval while 6.2A-1 is mature, (3) terminal position differs, or (4) terminal state differs.
No other behavior was changed. All happy paths and all 66 new tests pass with this change.

## 8. Canonical binding identity details

| Binding | Domain | Content |
| --- | --- | --- |
| Swing policy | `SWING_POLICY_INPUT_BINDING_V1` | `evidence_only` (None) or `empirical_confirmation_policy` (quantile + priors); float via hex (+0/-0 preserved), NaN/Inf rejected |
| Lifecycle ledger | `HYPOTHESIS_LIFECYCLE_LEDGER_INPUT_BINDING_V1` | canonical zero-row-or-sorted DataFrame, exact columns/order/dtypes, >2^53 ints exact, duplicate columns rejected |
| Stage 2 input binding | `STAGE2_INPUT_BINDING_V1` | contract version + timeline/anchor/interval identity + swing-policy + ledger seal + (artifact hash as provenance) |
| Stage 2 trajectory prefix | `STAGE2_TRAJECTORY_PREFIX_HASH_V1` | full sorted envelope-id tuple + count (no prefix-stability assumption) |
| Terminal snapshot id/hash | `TERMINAL_SNAPSHOT_ID_V1` / `_HASH_V1` | compact payload, domain-separated id vs hash |
| Censor snapshot id/hash | `CENSOR_SNAPSHOT_ID_V1` / `_HASH_V1` | compact payload, domain-separated id vs hash |

## 9. Required-test matrix coverage

Authoritative 6.2A-1 mature/censored binding, missing/ambiguous input rejection,
decision_snapshot_hash mismatch, timeline mismatch, mature↔censored cross-builder rejection;
Stage 2 terminal state/position mismatch rejection; terminal unavailable before factual
availability; later research-as-of retaining earlier availability; interval stopping at terminal;
no post-terminal contamination; origin preserved as integer not InformationKey; all three literal
terminal states; unresolved as-of non-terminal; no WIN/LOSS semantics; favorable price does not
infer terminal; swing-policy determinism / None identity / change / NaN-Inf / +0−0; ledger
determinism / zero-row canonical / row-order / column-order / nullable ints / >2^53 / duplicate
columns / mutation / missing columns; Stage 2 prefix determinism / envelope count / no envelope
tuple / no prefix-stable assumption; frozen immutability; append-only tuple; strict ordering;
A→A / A→B→A / fresh-instance / no-hidden-cache / caller-input immutability; positional &
time-indexed timelines; timezone-aware enforcement; DST/irregular UTC; cross-timeline rejection;
same-information-batch determinism; real Stage 1/Stage 2/6.2A-1 integration; 6.2A-2 non-redefinition;
firewall (live modules do not import Stage 3); no Stage 4 domains; manifest declares out-of-scope
and open debts.

## 10. Limitations (not certified by Stage 3)

Stage 3 does NOT certify: predictive edge, profitability, confluence score, learned weights,
calibration, qualification threshold, model/estimator/scorer, entry/stop/target, geometry,
execution/fills/trade lifecycle, PnL/WIN/LOSS/signals, statistical independence, or
overlapping-hypothesis dependence. Stage 3 records factual terminal/censor facts only; it does not
select any hazard/competing-risk estimand.

## 11. Open debts (unchanged, still OPEN)

RESEARCH-DEBT-020, 021, 022, 023, 024, 025 — none solved, none closed.

## 12. Final status

```
IMPLEMENTED — PENDING AUDIT
```

Do NOT declare ACCEPTED. Do NOT declare CLOSED. Stage 4 (descriptors/estimands/model), geometry,
and execution were not started.

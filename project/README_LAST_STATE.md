# README — LAST STATE (for independent auditor)

Project: Causal Trading Intelligence
Snapshot date: 2026-09-15

## Lifecycle state

```text
Stage 1        CLOSED
Stage 2        CLOSED
Stage 3        CLOSED          (818 passed)
Stage 4A       CLOSED          (890 passed)
Stage 4B-1     CLOSED          (927 passed)
Stage 4B-2     PATCHED / IMPLEMENTED — PENDING RE-AUDIT
Stage 4C       NOT STARTED
```

## Latest active module

Module: 6.2A-4 V1 Stage 4B-2
Name: Shared Liquidity / Order-Block / FVG / Dealing-Range Entity & Lifecycle Surfaces
Status: PATCHED / IMPLEMENTED — PENDING RE-AUDIT

Patch history:
1. Initial build (27 tests / 954 full)
2. Patch 1 — cross-domain substitution + incomplete prefix identity (35 tests / 962 full) — verified CLOSED by independent re-audit
3. Patch 2 — private CLOSED schema imports BLOCKER (37 tests / 964 full) — THIS SNAPSHOT, awaiting re-audit

## Artifacts for audit (SHA-256)

```text
ce6fe481064c672538df63f9560493506c3b532de0de30714f71c8c4cf9ab563  trading_project/src/trading_system/research/trajectory/trajectory_stage4b2.py
3315a6ac5c427b413f6eb510abe2486839b21d3c5a2bd0c8fde1beccf21d620b  trading_project/tests/test_trajectory_stage4b2.py
```

## Validation (this snapshot)

```text
Stage 4B-2 targeted tests : 37 / 37 passed
Full suite                : 964 collected / 964 passed
sha256sum -c MANIFEST.sha256 : 166 / 166 OK
MANIFEST.sha256 SHA-256   : 1583cde0beb68969a49866614c9e4e5b9243bb31cf846ad816eb69397341879a
```

MANIFEST is intentionally UNCHANGED from the last CLOSED baseline (Stage 4B-1) — Stage 4B-2 is not closed, so it is not in the manifest.

## CLOSED modules (unchanged, protected)

```text
bc393fe4ffb8dec9bdb16e4ae8e0036f22faefdecc8dc67345a5a881207bb708  trajectory_stage4b1.py
7e0c572d56074775b807278485a31a02ed6a6ec8e5bc941c638c586e2a401271  test_trajectory_stage4b1.py
19034dfff4ca4007921bdd7b3bd16c8afc5048b3601f2538d02510ba27edc26e  trajectory_stage4a.py
7547abfd5cf699badf2fc19b9a295b77aea8b73d0848fa5d12603655b3aa2b7f  test_trajectory_stage4a.py
e79a61cf85ce0ba5cb3dfcd3db63b8fcdbe8d53243bb28855eb0bc91dad2dc8e  trajectory_stage3.py
2777fd6661847226b91c1294234713e93a1e861d5f6845a164f3e89e523e8d28  test_trajectory_stage3.py
827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f  trajectory_stage2.py
bb5372fbad3582ce81d64b5d791b3599504b4ee12775767f77d93763f9bb1c6d  test_trajectory_stage2.py
```

## What Patch 2 changed (scope: private schema imports only)

- Removed 8 private underscore imports from CLOSED domain modules:
  `_BAR_OUTPUT_COLUMNS, _EVENT_COLUMNS` (liquidity_map), `_BAR_COLS, _EVENT_COLS` (order_blocks),
  `_BAR, _E` (fvg), `_OUTPUTS, _TABLE` (dealing_range).
- Only public engines/errors are imported now.
- Added Stage-4B-2-local frozen schema mirrors (`_LIQ_*`, `_OB_*`, `_FVG_*`, `_DR_*`).
- Kept dynamic public-output equivalence (run CLOSED engine -> returned schema must equal local mirror).
- FVG CLOSED event source schema = 21 columns; normalized Stage-4B-2 event adds derived
  `same_information_batch_order_unknown` -> 22. The two schemas are not confused.
- Regression tests added: `test_no_private_closed_schema_imports` (AST-based),
  `test_local_frozen_mirrors_match_actual_public_outputs`.
- Cross-domain defense and prefix fix left unchanged.

## Not done / open

- Stage 4B-2 NOT accepted / NOT closed — needs independent read-only re-audit.
- Stage 4C not started. No descriptors / estimands / ML / scoring / geometry / execution / PnL / signals.
- RESEARCH-DEBT-020 ... RESEARCH-DEBT-025 remain OPEN.
- Non-blocking findings explicitly left untouched per instruction.

## Reports

See `reports/` — latest relevant:
- `PATCH_REPORT_6_2A_4_V1_STAGE4B2_PRIVATE_IMPORTS.md` (this patch)
- `PATCH_REPORT_6_2A_4_V1_STAGE4B2.md` (patch 1)
- `BUILDER_REPORT_6_2A_4_V1_STAGE4B2.md`
- `CLOSURE_REPORT_6_2A_4_V1_STAGE4B1.md`
- `HANDOFF_FULL_SAHAB.md`

## Reproduce

```bash
cd trading_project
sha256sum -c MANIFEST.sha256
python -m pytest tests/test_trajectory_stage4b2.py -q
python -m pytest -q
```

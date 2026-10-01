# Patch Report — Module 6.2A-4 V1 Stage 4A (self-integrity BLOCKER)

**Shared Per-Bar Market-State Trajectory**

Date: 2026-08-21
Task Type: PATCH ONLY
Role: Builder (NOT an Independent Audit)
Final status: **PATCHED / IMPLEMENTED — PENDING AUDIT**

---

## 1. Confirmed blocker (accepted)

`Stage4ADomainSurface` is frozen but its contained `surface` DataFrame is mutable. A caller could
mutate `surface.surface` after construction while `public_result_hash` and `surface_id` stay stale,
enabling false binding and letting `ABSORPTION_PROXY` consume rows no longer matching the recorded
upstream identity.

## 2. Exact code changes (Stage 4A file only — no CLOSED module touched)

File: `src/trading_system/research/trajectory/trajectory_stage4a.py`

1. **`verify_surface_integrity(surface)`** (new): recomputes identity from CURRENT content. Verifies:
   type contract, supported domain, CLOSED contract version, timeline_id/hash non-empty, exact output
   schema (from CLOSED contract + frozen config payload), no duplicate columns, every output column
   present exactly once, recomputed `public_result_hash` equality, and recomputed `surface_id` equality.
   Rejects with `TrajectoryDataError`; never repairs/rewrites.
2. **`_expected_output_columns(domain, configuration_payload)`** (new): exact schema per domain from
   CLOSED contract — volatility 7 fields, order-flow-proxy 9, absorption-proxy 16, session base 4 +
   one `session_{key}_active` per configured session + `active_session_count`.
3. **`Stage4ADomainSurface.configuration_payload`** (new frozen field): canonical frozen config identity
   so SESSION schema is verified without trusting the mutable `output_columns`.
4. **`_assemble_surface(...)`** (new): single shared assembly path with a defensive `result.copy(deep=True)`
   at the Stage-4A boundary (in addition to the CLOSED engines' own deep copies).
5. **Integrity calls before consumption**:
   - `project_surface_prefix` → verifies before reading `surface.surface`.
   - `verify_surface_matches_reconstruction` → verifies BOTH supplied and authoritative, then compares
     every identity field (domain, contract_version, timeline_id, timeline_hash, config binding,
     reconstruction input, upstream_surface_hash, public_result_hash, surface_id, output_columns).
   - `build_absorption_proxy_surface` → verifies the upstream surface FIRST, then checks domain +
     timeline identity, then consumes the verified DataFrame, then binds `upstream_surface_hash` to the
     VERIFIED `surface_id`.

## 3. Output-schema verification method per domain

- Volatility / Order Flow Proxy / Absorption Proxy: fixed tuple mirrored verbatim from the CLOSED engine
  output contracts; compared for exact equality (order and content) against `output_columns`.
- Session: derived from the frozen `configuration_payload` (ordered `(name, timezone, start_local,
  end_local)` tuples) → `hour_utc_sin/cos`, `weekday_sin/cos`, `session_{key}_active` per session, then
  `active_session_count`.

## 4. Defensive-copy / aliasing result

- Verified the CLOSED engines all emit `df.copy(deep=True)` (no caller→surface aliasing).
- Added a Stage-4A-boundary `result.copy(deep=True)` for defense-in-depth.
- Tests confirm: mutating caller `market_history` after build does NOT change the built surface; mutating
  the upstream flow DataFrame after absorption construction does NOT change the absorption surface.

## 5. Tests added (17)

Self-integrity mutation (volatility/session/order-flow/absorption), verify-function supplied and
authoritative mutation, forged output_columns subset, forged surface_id, forged public_result_hash,
absorption upstream mutation rejected before consumption, absorption valid upstream accepted, prefix
row ≤ T mutation rejected, prefix row > T mutation rejected, old prefix binding unchanged after mutation
attempt, legal prefix invariance via new surface, caller market_history no-alias, absorption no-alias
into output.

3 existing tests were updated to the corrected patch semantics (mutation now rejects, not silently
tolerated): `test_future_mutation_after_T_does_not_alter_prefix`,
`test_volatility_no_future_fitting`, `test_supplied_vs_reconstructed_mismatch_rejected`.

## 6. Hashes

```
trajectory_stage4a.py   BEFORE  81a2a7bf24f795ae155c30c223eb24a133e724d39e3d031f84dc4ed99674954e
                        AFTER   88bd50639de3acd6d3a29fad4650695952bd696fa01c51d833a2e6036bc0fc98

test_trajectory_stage4a.py  BEFORE  1cbb7ce1b00485a47e54be12990068757664b121ad8fa69a7d076f18f1852ae8
                            AFTER   7bcb5e0644ae6b90da1921ca28f7f49bccbfe11fadbf3bc087b6029f5a039fea
```

## 7. Test counts

| Metric | Value |
| --- | --- |
| Stage 4A dedicated tests | **61** (44 prior + 17 new) |
| Total collected | **879** |
| Total passed | **879** (3m46s) |

## 8. CLOSED integrity

- `sha256sum -c MANIFEST.sha256` → **158 / 158 OK** (no FAILED line).
- Stage 3 accepted hashes unchanged:
  - `trajectory_stage3.py` `e79a61cf85ce0ba5cb3dfcd3db63b8fcdbe8d53243bb28855eb0bc91dad2dc8e` ✓
  - `test_trajectory_stage3.py` `2777fd6661847226b91c1294234713e93a1e861d5f6845a164f3e89e523e8d28` ✓

## 9. Mutability attack results (executed)

| Attack | Result |
| --- | --- |
| mutate volatility surface row | REJECTED — self-integrity |
| mutate session / order-flow / absorption surface row | REJECTED — self-integrity |
| supplied surface mutated (stale hashes) | REJECTED — self-integrity |
| authoritative surface mutated | REJECTED — self-integrity |
| forged output_columns subset | REJECTED — output_columns mismatch |
| forged surface_id / public_result_hash | REJECTED — self-integrity |
| absorption upstream mutated before consumption | REJECTED — self-integrity |
| prefix row ≤ T mutated | REJECTED — self-integrity |
| prefix row > T mutated | REJECTED — self-integrity |
| caller market_history mutated after build | surface unchanged (no alias) |
| upstream flow mutated after absorption build | absorption surface unchanged (no alias) |

## 10. Limitations / performance debt

- Integrity verification recomputes the full public-result hash (and surface_id) on every consumption
  path — O(surface size) per projection/absorption/verify call. Accepted for Stage 4A V1 correctness;
  no caching added (a cache would reintroduce staleness risk).
- `configuration_payload` is a frozen tuple-of-tuples; the SESSION schema is derivable from it without
  guessing.
- ACTUAL_AGGRESSOR / ACTUAL absorption remain unsupported (unchanged). Debts 020–025 remain OPEN.
  Stage 4B/4C not started.

## 11. Final status

```
PATCHED / IMPLEMENTED — PENDING AUDIT
```

Not an Independent Audit. Not ACCEPTED. Not CLOSED.

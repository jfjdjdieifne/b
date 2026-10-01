# Builder Report — Module 6.2A-4 V1 Stage 4A

**Shared Per-Bar Market-State Trajectory**

Date: 2026-08-20
Task Type: BUILD ONLY
Status: **IMPLEMENTED — PENDING AUDIT** (not ACCEPTED, not CLOSED)

---

## 1. Files created

| File | Action |
| --- | --- |
| `src/trading_system/research/trajectory/trajectory_stage4a.py` | CREATED |
| `tests/test_trajectory_stage4a.py` | CREATED |

No CLOSED file, `__init__.py`, test, or MANIFEST entry was modified.

## 2. SHA-256

```
trajectory_stage4a.py   81a2a7bf24f795ae155c30c223eb24a133e724d39e3d031f84dc4ed99674954e
test_trajectory_stage4a.py  1cbb7ce1b00485a47e54be12990068757664b121ad8fa69a7d076f18f1852ae8
```

## 3. Supported / unsupported modes

- **Supported**: Dynamic Volatility (CLOSED 1.1), Session Context (CLOSED 1.2), Volume Delta / Order
  Flow in `OHLCV_PROXY` mode (CLOSED 3.1), Absorption / Response in `OHLCV_PROXY` mode (CLOSED 3.2).
- **Unsupported (rejected explicitly, no fallback)**: `ACTUAL_AGGRESSOR` order flow, ACTUAL absorption.
  Error message: `NOT_SUPPORTED_BY_STAGE4A_V1_SOURCE_CONTRACT` (the CLOSED timeline does not seal
  `buy_volume`/`sell_volume`, and no authoritative external source-availability contract exists).

## 4. Reconstruction binding semantics

Per domain, a canonical `STAGE4A_RECONSTRUCTION_INPUT_BINDING_V1` witness binds:
- Volatility: timeline id/hash + `high_col`/`low_col`/`close_col` + `MODULE_1_1_V1_1`.
- Session: timeline id/hash + ordered `SessionDefinition` config (`name`/`timezone`/`start_local`/
  `end_local`) + `MODULE_1_2_V1`.
- Order Flow Proxy: timeline id/hash + mode `OHLCV_PROXY` + `MODULE_3_1_V1_1`.
- Absorption Proxy: timeline id/hash + mode + **upstream ORDER_FLOW_PROXY surface_id** + `MODULE_3_2_V1_1`.

Plus a separate `STAGE4A_<DOMAIN>_CONFIG_BINDING_V1` for the exact public configuration. These are
DERIVATION WITNESSES, not historical generating-input provenance.

## 5. Public-result hash semantics

`STAGE4A_PUBLIC_RESULT_EQUIVALENCE_V1` over the COMPLETE CLOSED factual output columns per domain
(all derived columns, order-preserved, index-preserved, via canonical DataFrame hashing):
- Volatility: 7 output fields.
- Session: 5 base calendar/active fields + one `session_{key}_active` per configured session.
- Order Flow Proxy: 9 proxy fields.
- Absorption Proxy: 16 proxy fields.

Supplied vs authoritative reconstruction is verified by `verify_surface_matches_reconstruction`
(complete public-result hash equality; mismatch → reject).

## 6. Shared surface / projection design

- `Stage4ADomainSurface`: shared, computed once per domain-surface identity (timeline + contract
  version + config binding + reconstruction input + upstream surface + public-result hash).
- `Stage4APrefixBinding`: compact hypothesis projection — surface reference + immutable prefix
  identity through a boundary; contains NO physical surface rows.
- Prefix identity (`STAGE4A_PREFIX_IDENTITY_V1`) is stable under future append and future mutation
  strictly after T; the full-surface identity changes on append (correctly distinguished).

## 7. Stage 3 boundary integration

`project_surface_prefix(surface, boundary_key)` bounds a projection to the exact InformationKey
position; the boundary key must belong to the surface's timeline. Mature terminal T and censored
as-of T both project only rows ≤ T. No post-boundary fact enters a projection; historical prefix
identity is immutable under later shared-surface extension. Stage 3 semantics are not redefined.

## 8. Test counts

| Metric | Value |
| --- | --- |
| Stage 4A dedicated tests | **44** |
| Total collected | **862** |
| Total passed | **862** (3m43s) |

## 9. Proof all 158 CLOSED MANIFEST entries unchanged

```
sha256sum -c MANIFEST.sha256  ->  158 / 158 OK (no FAILED line)
```

Stage 3 accepted hashes re-verified unchanged:
- `trajectory_stage3.py` `e79a61cf85ce0ba5cb3dfcd3db63b8fcdbe8d53243bb28855eb0bc91dad2dc8e` ✓
- `test_trajectory_stage3.py` `2777fd6661847226b91c1294234713e93a1e861d5f6845a164f3e89e523e8d28` ✓

## 10. Limitations

- `ACTUAL_AGGRESSOR` and ACTUAL absorption are NOT implemented (source-contract limitation, not a
  predictive claim). PROXY is never relabeled ACTUAL; fidelity is a factual property.
- Session surface requires a time-indexed (timezone-aware) timeline; positional timelines are
  rejected with a clear error.
- Absorption surface identity binds the exact upstream proxy surface; upstream mutation changes the
  absorption identity (verified).

## 11. Open debts (unchanged)

`RESEARCH-DEBT-020`, `021`, `022`, `023`, `024`, `025` — all OPEN. ACTUAL support is not silently
solved through guessed availability semantics.

## 12. Final status

```
IMPLEMENTED — PENDING AUDIT
```

Do NOT declare ACCEPTED. Do NOT declare CLOSED. Stage 4B and Stage 4C not started.

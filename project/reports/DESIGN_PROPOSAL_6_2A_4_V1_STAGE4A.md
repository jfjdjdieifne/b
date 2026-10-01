# FINAL DESIGN PROPOSAL — Module 6.2A-4 V1 Stage 4A
## Shared Per-Bar Market-State Trajectory

Status: **DESIGN PROPOSAL — NOT IMPLEMENTED** (DESIGN PATCH ONLY)
Date: 2026-08-20

Authoritative baseline (unchanged):
- Stage 3 CLOSED; 818 collected / 818 passed; MANIFEST 158/158 OK, SHA-256 `309f2d13…`.
- No project file, test, or MANIFEST was modified by this design task.

Scope: Stage 4A = **Volatility (1.1) + Session (1.2) + Volume Delta / Order Flow (3.1) +
Absorption / Response (3.2)**. Stage 4B (entity/lifecycle) and Stage 4C (HTF/MTF) are OUT OF SCOPE.

---

## 1. Corrected definition of "shared market truth"

The prior design said "computed once per timeline." That is corrected to:

> A Stage 4A domain surface is shared per **exact domain-surface identity**, not merely per timeline.

A deterministic shared domain surface is identified by:

```
S4A_DOMAIN_SURFACE_IDENTITY =
    timeline_identity          (timeline_id + timeline_hash + index identity)
  + domain_contract_version    (CLOSED module contract version string)
  + exact reconstruction-input binding
  + exact public-configuration binding
  + upstream surface identity  (where applicable, e.g. 3.2 depends on 3.1)
```

This is **deterministic reconstruction / derivation identity only**. It does NOT claim historical
generating-input provenance. (The Stage 3 provenance lesson applies verbatim: a reconstruction
binding proves reproducibility, never which input historically produced an artifact.)

---

## 2. Exact CLOSED inputs per engine (read from source)

### 2A. Dynamic Volatility (1.1) — `DynamicVolatilityEngine`

- **Market columns consumed**: `high`, `low`, `close` (column names are configurable via
  `high_col`/`low_col`/`close_col`, defaults `"high"`/`"low"`/`"close"`).
- **Configuration**: `high_col`, `low_col`, `close_col` (strings). No thresholds, no lookback, no
  mode, no regime.
- **Causal percentile state**: internal `CausalPercentileTracker(nan_policy="skip")`, created fresh
  per `analyze()` call — **no external configuration, no persisted state**.
- **Minimum-history / first-valid semantics**: `normalized_true_range` is NaN at bar 0 (no prior
  close); `normalized_tr_change` is NaN at bars 0 and 1 (needs two consecutive positive finite
  normalized ranges); percentile fields are NaN until ≥1 prior observation pushed.
- **Source mode**: none.
- **Output fields**: `true_range`, `normalized_true_range`, `true_range_percentile`,
  `true_range_history_count`, `normalized_tr_change`, `expansion_percentile`,
  `expansion_history_count`.

**Must enter Stage-4A reconstruction binding**: `high_col`, `low_col`, `close_col`; the exact
`high`/`low`/`close` payload (bound transitively via the sealed timeline for OHLC); the CLOSED
contract version `"MODULE_1_1_V1_1"`.

### 2B. Session Context (1.2) — `CausalSessionContextEngine`

- **Index requirements**: timezone-aware `DatetimeIndex`, no NaT, no duplicates, monotonic
  increasing. `freq` is canonicalized to `None` (index-level metadata, not a row fact).
- **Configuration**: an immutable ordered tuple of `SessionDefinition` objects, each with public
  fields `name` (ASCII `^[A-Za-z][A-Za-z0-9_]*$`), `timezone` (IANA), `start_local` (naive
  `datetime.time`), `end_local` (naive `datetime.time`). **No default schedule** (empty tuple is
  legal → calendar features only, `active_session_count == 0`).
- **DST**: handled via `ZoneInfo` IANA rules; no fixed offset, no manual table.
- **Output fields**: `hour_utc_sin`, `hour_utc_cos`, `weekday_sin`, `weekday_cos`,
  `active_session_count`, and `session_{output_key}_active` per configured session (where
  `output_key = name.lower()`).

**Canonical session-configuration identity** (using only actual CLOSED public fields): the ordered
list of `(name, timezone, start_local.isoformat(), end_local.isoformat())` tuples. A surface built
under configuration A must NEVER be labeled configuration B; the binding hashes this exact ordered
tuple. No invented session boundaries.

### 2C. Volume Delta / Order Flow (3.1) — `CausalVolumeDeltaEngine`

Two explicit modes, never auto-selected:

- **PROXY (`OHLCV_PROXY`)**: consumes `open`, `high`, `low`, `close`, `volume` — all present in the
  sealed `MarketObservationTimeline`. Configuration: `mode=OHLCV_PROXY` (and `reconcile_total_volume`
  is forbidden in this mode). Outputs: `order_flow_mode`, `close_location_proxy`,
  `volume_pressure_proxy`, `signed_volume_pressure_raw`, `pressure_proxy_percentile`,
  `pressure_proxy_history_count`, `pressure_magnitude`, `pressure_magnitude_percentile`,
  `pressure_magnitude_history_count`.
- **ACTUAL (`ACTUAL_AGGRESSOR`)**: consumes `buy_volume`, `sell_volume` (+ `volume` iff
  `reconcile_total_volume=True`). **These columns are NOT part of the sealed
  `MarketObservationTimeline`** (the seal binds only OHLC + optional `volume`). They are external
  factual feed data. Outputs: `order_flow_mode`, `total_classified_volume`, `raw_delta`,
  `delta_ratio`, `delta_ratio_percentile`, `delta_ratio_history_count`, `delta_magnitude`,
  `delta_magnitude_percentile`, `delta_magnitude_history_count` (+ `classified_volume_fraction`
  iff reconcile). Configuration: `mode=ACTUAL_AGGRESSOR`, `reconcile_total_volume` (bool).

**Mandated consequence**: the ACTUAL mode's reconstruction-input binding MUST NOT be the OHLCV
timeline seal. A **separate Stage-4A factual-source binding** is required for
`buy_volume`/`sell_volume` (and `volume` when reconcile). ACTUAL != PROXY; source fidelity
preserved; ACTUAL does not imply global-crypto order flow.

### 2D. Absorption / Response (3.2) — `CausalAbsorptionEvidenceEngine`

- **Return inputs**: `close` (market). `signed_return[i] = log(close[i]) − log(close[i−1])`
  (backward-only; bar 0 NaN).
- **Upstream 3.1 surface consumed** (mode-matched):
  - ACTUAL: `close`, `delta_ratio`, `delta_magnitude`, `delta_magnitude_percentile`,
    `delta_magnitude_history_count`, `total_classified_volume`, `order_flow_mode`.
  - PROXY: `open`, `high`, `low`, `close`, `volume`, `close_location_proxy`,
    `volume_pressure_proxy`, `pressure_magnitude`, `pressure_magnitude_percentile`,
    `pressure_magnitude_history_count`, `order_flow_mode`.
- **Configuration**: `mode` (OrderFlowMode), which must match the upstream 3.1 surface's
  `order_flow_mode` on every row (enforced by `_mode_column`).
- **Causality**: `_response_context` pairs same-bar `flow[i]` × `signed_return[i]`; no future bar
  is consumed.
- **Output fields**: common `absorption_mode`, `signed_return`, `absolute_return`,
  `return_magnitude_percentile`, `return_magnitude_history_count`; ACTUAL adds
  `aggression_response_alignment`, `aligned/opposed_response_magnitude(+percentile/history)`,
  `aggression_extremeness`, `response_weakness`, `actual_absorption_evidence`,
  `absorbed_aggression_side`; PROXY adds `pressure_response_alignment`, `pressure_aligned/opposed_*`,
  `proxy_pressure_extremeness`, `proxy_response_weakness`, `proxy_absorption_evidence`,
  `pressure_side`.

**Absorption surface identity MUST bind the exact upstream 3.1 domain-surface identity** (hash of
the 3.1 surface), not merely a mode string.

---

## 3. Domain-surface identity concept

Proposed Stage-4A-local concept (naming consistent with Stage 3):

```
Stage4ADomainSurfaceIdentity:
    domain_name                 # "VOLATILITY" | "SESSION" | "VOLUME_DELTA" | "ABSORPTION"
    contract_version            # CLOSED module version string
    timeline_id, timeline_hash  # shared MarketObservationTimeline
    configuration_binding_hash  # exact public config (canonical)
    reconstruction_input_hash   # exact consumed factual input (canonical)
    upstream_surface_hash       # upstream domain-surface identity (ABSORPTION only, = 3.1 surface)
    public_result_hash          # complete public factual result (see §4)
```

Semantics: **DETERMINISTIC RECONSTRUCTION / DERIVATION WITNESS** — never HISTORICAL INPUT
PROVENANCE. Documented in the module docstring and manifest.

---

## 4. Complete public-result equivalence (Stage 3 lesson, applied from the start)

Each Stage 4A domain carries a canonical `STAGE4A_<DOMAIN>_PUBLIC_RESULT_EQUIVALENCE_V1` hash over
its COMPLETE public factual output (all result columns), not merely envelope identity. Exact
payloads:

- **Volatility**: all 7 output columns (`true_range`, `normalized_true_range`,
  `true_range_percentile`, `true_range_history_count`, `normalized_tr_change`,
  `expansion_percentile`, `expansion_history_count`).
- **Session**: `hour_utc_sin`, `hour_utc_cos`, `weekday_sin`, `weekday_cos`,
  `active_session_count`, plus every `session_{key}_active` column (in canonical session order).
- **Volume Delta ACTUAL**: `order_flow_mode`, `total_classified_volume`, `raw_delta`,
  `delta_ratio`, `delta_ratio_percentile`, `delta_ratio_history_count`, `delta_magnitude`,
  `delta_magnitude_percentile`, `delta_magnitude_history_count`, (+ `classified_volume_fraction`).
- **Volume Delta PROXY**: `order_flow_mode`, `close_location_proxy`, `volume_pressure_proxy`,
  `signed_volume_pressure_raw`, `pressure_proxy_percentile`, `pressure_proxy_history_count`,
  `pressure_magnitude`, `pressure_magnitude_percentile`, `pressure_magnitude_history_count`.
- **Absorption ACTUAL/PROXY**: the complete mode-specific column set listed in §2D.

No field is excluded except where transitively bound; for Stage 4A per-bar state domains, **every
output column is included directly** (there are no separate point/envelope structures as in Stage 2,
so no transitive-coverage argument is needed).

---

## 5. Shared computation vs hypothesis projection

- **SHARED DOMAIN SURFACE** (computed once per domain-surface identity, hypothesis-independent):
  the full per-bar state frames listed above.
- **HYPOTHESIS-BOUNDED PROJECTION / BINDING** (per hypothesis): a compact reference to the shared
  surface + a legal-prefix boundary. For a mature hypothesis, the projection boundary = terminal
  factual-availability boundary; for right-censored, = the legal research as-of boundary.

The underlying shared surface MAY contain later market facts. Those later facts MUST NOT enter an
earlier hypothesis snapshot; historical snapshot identity must remain unchanged after future
shared-surface extension. The shared factual rows are NOT duplicated into each hypothesis.

---

## 6. Future append / prefix identity

- **Full shared-surface artifact identity** = hash of the entire current surface (changes on append).
- **Immutable prefix identity through boundary T** = a separate canonical hash over only the
  rows ≤ T of the shared surface (stable under future append T+1…).

The Stage 4A binding for a snapshot through T uses the **prefix identity**, never the whole-surface
identity. Appending T+1… must not rewrite the prefix identity of the already-observed prefix.

---

## 7. Information time per domain

- **Volatility**: a bar's `true_range` uses `high_i, low_i, close_{i−1}` — legally available at the
  completion of bar i. `normalized_true_range`/percentiles also depend only on ≤ i. **Single clock:
  origin == availability == completed bar i.** Bar 0's `normalized_true_range` is NaN (no prior
  close) — a factual "not yet available" state, not an invented value.
- **Session**: pure function of `timestamp[i]` — available at bar i. Single clock.
- **Volume Delta ACTUAL**: availability is governed by the external aggressor feed, NOT the OHLCV
  timeline. The Stage-4A surface must record a factual-availability key derived from the ACTUAL
  source binding; it must not silently assume the aggressor data is available at OHLC bar
  completion unless the source contract says so. This is an explicit design requirement, not an
  assumption.
- **Volume Delta PROXY**: OHLCV-derived, available at completed bar i. Single clock.
- **Absorption**: depends on upstream 3.1 surface; a bar's absorption facts are legally factual
  only when all consumed 3.1 inputs for that bar are available. Same-bar response (no future).

No fabricated origin InformationKey: origin stays Int64 bar position (or the ACTUAL-source
availability key); availability is the InformationKey clock.

---

## 8. Source fidelity

Explicit fields preserved: `order_flow_mode` (`ACTUAL_AGGRESSOR` vs `OHLCV_PROXY`) and
`absorption_mode`. ACTUAL means actual only under the upstream feed's semantics (the engine itself
cannot verify classification or volume units). PROXY is completed-bar geometry, never true delta.
Fidelity is a factual source-contract property — it carries no predictive quality. ACTUAL does not
imply useful; PROXY does not imply useless.

---

## 9. Configuration and magic numbers

Stage 4A consumes CLOSED configurations only. It MUST NOT introduce new lookbacks, thresholds,
percentile cutoffs, session boundaries, mode defaults, ATR gates, or absorption thresholds. If a
required configuration is absent (e.g. no session configured, or ACTUAL mode without an aggressor
source), the surface records `UNAVAILABLE` / `NOT_CONFIGURED` semantics; no default is invented.

---

## 10. Final Stage 4A BUILD contract

### Public concepts/types
`Stage4ADomainSurfaceIdentity`, `Stage4ASharedDomainSurface` (per domain), `Stage4APrefixBinding`
(hypothesis projection), plus per-domain result frames.

### Exact four CLOSED engines consumed
`DynamicVolatilityEngine`, `CausalSessionContextEngine`, `CausalVolumeDeltaEngine`,
`CausalAbsorptionEvidenceEngine`.

### Exact inputs/configuration per engine
As enumerated in §2.

### Exact reconstruction binding per engine
As enumerated in §2 (config + factual input + contract version), with the ACTUAL aggressor source
in its own binding (not the OHLCV seal), and absorption binding the upstream 3.1 surface hash.

### Exact public-result hash payload per engine
As enumerated in §4.

### Shared-surface identity
`Stage4ADomainSurfaceIdentity` as in §3.

### Prefix identity through boundary T
Separate canonical hash over rows ≤ T (§6).

### Hypothesis projection semantics
Compact reference + prefix boundary; no row duplication (§5).

### Stage 3 terminal/censor boundary binding
Projection boundary = terminal factual-availability (mature) or research as-of (censored). Stage 3
semantics not redefined.

### Source-fidelity semantics
§8.

### Storage representation
Shared per-bar state frames indexed by timeline position/timestamp; hypothesis projections store
references + prefix hashes only.

### Mismatch/rejection rules
Supplied vs reconstructed surface mismatch → reject (`TrajectoryDataError` analog). Mode mismatch
(absorption vs upstream 3.1) → reject. Config A vs B mislabel → reject. Cross-timeline → reject.

### No-fallback rules
Missing/ambiguous/invalid authoritative input → STOP, no fallback, no default configuration, no
ACTUAL→PROXY auto-fallback (CLOSED never authorizes it).

### Exact proposed new BUILD files
```
src/trading_system/research/trajectory/trajectory_stage4a.py
tests/test_trajectory_stage4a.py
```
(Stage 4A imports the four CLOSED engines by module path; no `__init__.py` change during BUILD.)

### Exact CLOSED files that must NOT be modified
All four engine modules (`dynamic_volatility.py`, `session_context.py`, `volume_delta.py`,
`absorption.py`), `trajectory_contract.py`, `trajectory_stage2.py`, `trajectory_stage3.py`,
`information_time.py`, `hashing.py`, and every other CLOSED file. MANIFEST not updated during BUILD.

---

## 11. Required adversarial test matrix (future BUILD)

GENERAL: same timeline+config → deterministic identical surface; materially different config →
different binding/result; supplied-vs-reconstructed mismatch rejection; complete public-result
mutation detection (per output column family); future append prefix invariance; future mutation
strictly after T does not change prefix through T; historical hypothesis projection immutable;
shared surface reused across multiple hypotheses; no per-hypothesis market-state duplication;
cross-timeline rejection; input immutability; A→A; A→B→A; fresh instance; no hidden cache.

VOLATILITY: causal percentile prefix invariance; first-valid/history NaN semantics (bar 0/1);
no future fitting; `high<low` rejection; NaN/Inf rejection.

SESSION: exact SessionDefinition binding; config A vs B distinction; timezone-aware enforcement;
UTC; DST; irregular timestamps; no invented session boundary; duplicate/colliding session name
rejection; `freq` canonicalization does not change row facts.

ORDER FLOW: ACTUAL vs PROXY cannot collide semantically; PROXY input mutation detection; ACTUAL
external-input mutation detection; ACTUAL source NOT falsely claimed OHLCV-bound; missing ACTUAL
source rejected; no ACTUAL→PROXY fallback; `reconcile_total_volume` only in ACTUAL; PROXY volume
non-negative; high<low and OHLC-body geometry rejection.

ABSORPTION: binds exact upstream 3.1 surface (upstream mutation changes binding); mode preservation
and mode-mismatch rejection; same-bar response causality (no future bar); `delta_ratio` NaN exactly
at zero total volume; percentile-in-[0,1] and history-count monotonicity contracts.

STAGE 3 BOUNDARY: mature terminal T → no projected fact after T; censored as-of T → no projected
fact after T; later shared-surface append does not alter earlier snapshot prefix binding.

NUMERIC/SCHEMA: NaN/Inf; duplicate columns; wrong dtype; nullable ints; >2^53 where applicable;
+0/−0 where identity matters.

FIREWALL: LIVE modules do not import Stage 4A; no Stage 4B/4C domains; no descriptors; no
estimands; no model/scorer; no geometry/execution.

---

## 12. Open debts

Keep OPEN: RESEARCH-DEBT-020, 021, 022, 023, 024, 025. No new debt proposed (no unresolved contract
issue found in the four CLOSED engines inspected).

---

## 13. Classification

**BLOCKERS**: none remaining for Stage 4A — the four corrections are fully specified above
(shared-per-surface identity, ACTUAL external-source binding, absorption upstream binding, complete
public-result hash, prefix identity, projection separation).

**NON-BLOCKING DESIGN DEBT**: wide per-bar frames (column-collision rejection must mirror CLOSED);
ACTUAL availability semantics depend on an external feed whose contract must be pinned explicitly at
BUILD time (documented, not assumed).

**RESEARCH QUESTIONS**: none new; any predictive use of these factual states belongs to future
estimand work (RESEARCH-DEBT-020/021/023 remain OPEN).

---

## 14. Final status

```
NO DESIGN BLOCKER REMAINS FOR STAGE 4A BUILD
DESIGN PROPOSAL — NOT IMPLEMENTED
```

BUILD not started. No project file, test, or MANIFEST modified.

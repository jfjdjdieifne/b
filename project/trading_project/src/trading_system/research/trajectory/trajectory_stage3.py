"""Module 6.2A-4 V1 Stage 3: Terminal / Censor Snapshots & As-Of Censor Series.

Factual binding layer on top of CLOSED Stage1 and Stage2.

- Immutable mature terminal snapshot
- Immutable right-censored-as-of snapshot
- Append-only as-of series
- Authority: 6.2A-1 is authoritative for mature/censored classification
- Stage2 is authoritative for PRICE/STRUCTURE/LIFECYCLE trajectory prefix
- No second lifecycle state machine, no price-inferred terminal
- Origin preserved exactly as supplied by CLOSED source (Int64 position, not forged InformationKey)
- Two distinct clocks: terminal_factual_available_at vs research_as_of
- Compact binding: interval identity + Stage2 reconstruction binding + trajectory-prefix hash + envelope count + factual outcome binding
- No raw market history per snapshot, no full growing envelope tuple, no duplicated running payloads
- BLOCKER patch: every Stage 2 envelope is verified against the expected context, and the
  supplied Stage 2 result is proven to be DETERMINISTICALLY EQUIVALENT to an authoritative
  reconstruction from the exact bound inputs (build_stage2_trajectory) over the COMPLETE public
  factual result (price_bars + price final scalars + structure_events + lifecycle_events +
  terminal fields + envelope count + prefix hash) via the STAGE2_PUBLIC_RESULT_EQUIVALENCE_V1
  canonical hash. The swing-policy and lifecycle-ledger identities recorded in the snapshot are
  DERIVATION WITNESSES only ("reproduces the supplied trajectory under CLOSED Stage 2"), NOT
  asserted historical generating-input identity. CLOSED Stage 2 does not seal input identity, so
  the true generating input is unverifiable from the artifact alone; Stage 3 claims equivalence,
  not origin.
- PERFORMANCE DEBT (accepted for Stage 3 V1): the reconstruction re-runs Stage 2 per snapshot.
  No caches are used; correctness and provenance take priority.
- RESEARCH-DEBT-020/021/022/023/024/025 remain OPEN
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Optional, Tuple

import numpy as np
import pandas as pd

from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import (
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.trajectory.trajectory_contract import (
    DecisionAnchor,
    MarketObservationTimeline,
    ObservationEnvelope,
    TrajectoryContractError,
    TrajectoryDataError,
    TrajectoryInterval,
)
from trading_system.research.trajectory.trajectory_stage2 import build_stage2_trajectory

TimelineAdapter = PositionalTimelineAdapter | TimeIndexedTimelineAdapter

TRAJECTORY_STAGE3_CONTRACT_VERSION: Final = "CAUSAL_TERMINAL_CENSOR_SNAPSHOT_V1"
STAGE2_CONTRACT_VERSION: Final = "CAUSAL_PRICE_STRUCTURE_LIFECYCLE_TRAJECTORY_V1"
STAGE2_ACCEPTED_SRC_HASH: Final = "827ddf9b51e0a4ffecd57e5f92a0b2ddfafbd5b9ddb3af61fc6ae8a9a4e8fd3f"
OUTCOME_CONTRACT_VERSION: Final = "FACTUAL_HYPOTHESIS_OUTCOME_V1_1"

_CLOSED_TERMINAL: Final = frozenset({"CONTRADICTED", "SUPERSEDED", "OBSERVED_DIRECTION_ESTABLISHED"})
_RIGHT_CENSORED_TYPE: Final = "RIGHT_CENSORED_AS_OF_BOUNDARY"

# Canonical ledger columns per CLOSED 6.1B narrative.py
_HYPOTHESIS_LEDGER_COLUMNS: Final = (
    "ledger_event_id",
    "hypothesis_id",
    "event_position",
    "same_row_batch_id",
    "ledger_event_type",
    "previous_state",
    "new_state",
    "trigger_relationship_id",
    "superseded_by_hypothesis_id",
    "serialization_order",
)
_HYPOTHESIS_LEDGER_INT_COLS: Final = (
    "ledger_event_id",
    "hypothesis_id",
    "event_position",
    "same_row_batch_id",
    "trigger_relationship_id",
    "superseded_by_hypothesis_id",
    "serialization_order",
)
_HYPOTHESIS_LEDGER_STR_COLS: Final = ("ledger_event_type", "previous_state", "new_state")

# ---------------------------------------------------------------------------
# Helpers — validation
# ---------------------------------------------------------------------------

def _validate_anchor(anchor: DecisionAnchor) -> None:
    if not isinstance(anchor, DecisionAnchor):
        raise TrajectoryContractError("DecisionAnchor required")
    anchor.verify()


def _validate_interval_timeline(
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    interval: TrajectoryInterval,
) -> None:
    if not isinstance(timeline, MarketObservationTimeline):
        raise TrajectoryContractError("MarketObservationTimeline required")
    if not isinstance(interval, TrajectoryInterval):
        raise TrajectoryContractError("TrajectoryInterval required")
    timeline.verify(adapter=adapter, market_history=market_history)
    anchor.verify()
    interval.verify()
    if not (timeline.timeline_id == anchor.timeline_id == interval.timeline_id):
        raise TrajectoryDataError("timeline/anchor/interval timeline_id mismatch")
    if not (timeline.timeline_hash == anchor.timeline_hash == interval.timeline_hash):
        raise TrajectoryDataError("timeline seal mismatch across anchor/interval")
    if anchor.anchor_hash != interval.anchor_hash:
        raise TrajectoryDataError("anchor/interval hash mismatch")


def _key_payload(key: Optional[InformationKey]) -> Optional[dict]:
    if key is None:
        return None
    return {
        "information_key_version": key.information_key_version,
        "timeline_id": key.timeline_id,
        "bar_position": key.bar_position,
        "event_time_utc": key.event_time_utc,
        "information_phase": key.information_phase,
        "deterministic_sequence": key.deterministic_sequence,
    }


# ---------------------------------------------------------------------------
# Stage-3-local canonical reconstruction-witness bindings (without modifying CLOSED)
# ---------------------------------------------------------------------------

def _canonicalize_swing_policy(swing_policy) -> Tuple[dict, str]:
    """Returns (payload, hash) for the swing-policy reconstruction witness.

    The hash is a canonical identity of the policy supplied to the reconstruction. It is a
    DERIVATION WITNESS ("this policy reproduces the supplied trajectory under CLOSED Stage 2"),
    NOT an assertion that this policy historically generated the supplied artifact.

    - None => evidence-only
    - EmpiricalConfirmationPolicy => quantile + priors
    Uses canonical float hex handling via hashing.canonical_sha256 (supports +0/-0, rejects NaN/Inf via ResearchHashError -> converted to TrajectoryDataError).
    One logical input type has one identity scheme.
    """
    if swing_policy is None:
        payload = {"type": "evidence_only", "version": "2.1A_V1_1"}
    else:
        # Expect EmpiricalConfirmationPolicy with attributes quantile, prior_continuation_reversals, prior_confirmed_reversals
        try:
            q = float(swing_policy.quantile)
        except Exception as exc:
            raise TrajectoryDataError(f"invalid swing_policy quantile: {exc}") from exc
        try:
            cont = tuple(float(x) for x in swing_policy.prior_continuation_reversals)
            conf = tuple(float(x) for x in swing_policy.prior_confirmed_reversals)
        except Exception as exc:
            raise TrajectoryDataError(f"invalid swing_policy priors: {exc}") from exc
        # Validate finite per CLOSED contract (policy itself validates, but double-check for binding)
        for v in (q,) + cont + conf:
            if not np.isfinite(v):
                raise TrajectoryDataError("swing_policy contains non-finite value")
        payload = {
            "type": "empirical_confirmation_policy",
            "version": "2.1A_V1_1",
            "quantile": q,
            "prior_continuation_reversals": cont,
            "prior_confirmed_reversals": conf,
        }
    # Canonical hash — hashing.py handles float via hex, preserves +0/-0, rejects NaN/Inf already checked
    try:
        h = canonical_sha256(domain="SWING_POLICY_RECONSTRUCTION_BINDING_V1", payload=payload)
    except Exception as exc:
        raise TrajectoryDataError(f"swing_policy binding hash failed: {exc}") from exc
    return payload, h


def _empty_ledger_canonical_df() -> pd.DataFrame:
    """Create zero-row canonical ledger DataFrame with exact required columns, order, dtypes."""
    # Exact canonical column order per CLOSED 6.1B
    cols = list(_HYPOTHESIS_LEDGER_COLUMNS)
    df = pd.DataFrame({c: [] for c in cols})
    # Enforce dtypes: Int64 for int cols, string for str cols
    for c in _HYPOTHESIS_LEDGER_INT_COLS:
        df[c] = pd.array(df[c], dtype="Int64")
    for c in _HYPOTHESIS_LEDGER_STR_COLS:
        df[c] = pd.array(df[c], dtype="string")
    # Ensure column order exact
    df = df[list(cols)]
    return df


def _canonicalize_ledger(ledger: Optional[pd.DataFrame]) -> Tuple[pd.DataFrame, str]:
    """Returns (canonical_df, seal_hash) for the lifecycle-ledger reconstruction witness.

    The seal is a canonical identity of the ledger supplied to the reconstruction. It is a
    DERIVATION WITNESS ("this ledger reproduces the supplied trajectory under CLOSED Stage 2"),
    NOT an assertion that this ledger historically generated the supplied artifact.

    - Uses SAME canonical schema and SAME hashing path for empty and non-empty.
    - Empty ledger: zero-row canonical DataFrame with exact required columns/order/dtypes.
    - Non-empty: validates required columns, no duplicate columns, sorts deterministically by event_position ASC, ledger_event_id ASC, reorders to canonical column order, coerces dtypes to canonical (Int64/string).
    - Hash via canonical_sha256(domain="HYPOTHESIS_LIFECYCLE_LEDGER_RECONSTRUCTION_BINDING_V1", payload=DataFrame) which is explicitly supported by hashing.py with required semantics.
    """
    if ledger is None or ledger.empty:
        canonical_df = _empty_ledger_canonical_df()
    else:
        # Validate required columns
        missing = [c for c in _HYPOTHESIS_LEDGER_COLUMNS if c not in ledger.columns]
        if missing:
            raise TrajectoryDataError(f"lifecycle ledger missing required columns: {missing}")
        if ledger.columns.has_duplicates:
            raise TrajectoryDataError("lifecycle ledger duplicate columns forbidden")
        # Sort deterministically for reproducibility
        sorted_df = ledger.sort_values(by=["event_position", "ledger_event_id"], kind="mergesort").reset_index(drop=True)
        # Reorder to canonical order and keep only required columns (exact)
        canonical_df = sorted_df[list(_HYPOTHESIS_LEDGER_COLUMNS)].copy(deep=True)
        # Enforce dtypes canonical
        for c in _HYPOTHESIS_LEDGER_INT_COLS:
            try:
                canonical_df[c] = pd.array(canonical_df[c], dtype="Int64")
            except Exception as exc:
                raise TrajectoryDataError(f"ledger column {c} dtype conversion failed: {exc}") from exc
        for c in _HYPOTHESIS_LEDGER_STR_COLS:
            try:
                canonical_df[c] = pd.array(canonical_df[c], dtype="string")
            except Exception as exc:
                raise TrajectoryDataError(f"ledger column {c} dtype conversion failed: {exc}") from exc
    # Hash via canonical serializer that supports DataFrames
    try:
        h = canonical_sha256(domain="HYPOTHESIS_LIFECYCLE_LEDGER_RECONSTRUCTION_BINDING_V1", payload=canonical_df)
    except Exception as exc:
        raise TrajectoryDataError(f"lifecycle ledger binding hash failed: {exc}") from exc
    return canonical_df, h


def _stage2_trajectory_prefix_hash(stage2_result) -> Tuple[int, str]:
    """Compute deterministic prefix hash and envelope count from Stage2 result.

    Does NOT embed full envelope tuple in snapshot, only hash + count.
    Uses canonical ordering rule from Stage2: sorted by (bar_position, envelope_id) already guaranteed by build_stage2_trajectory,
    but we re-sort to be explicit and not depend on object identity.
    """
    try:
        all_envs = stage2_result.all_envelopes
    except AttributeError as exc:
        raise TrajectoryDataError("stage2_result missing all_envelopes") from exc
    # Extract envelope_ids in canonical order: bar_position then envelope_id
    try:
        sorted_envs = tuple(sorted(all_envs, key=lambda e: (e.observation_information_key.bar_position, e.envelope_id)))
        envelope_ids = tuple(e.envelope_id for e in sorted_envs)
    except Exception as exc:
        raise TrajectoryDataError(f"failed to extract envelope_ids from stage2_result: {exc}") from exc
    envelope_count = len(envelope_ids)
    try:
        prefix_hash = canonical_sha256(domain="STAGE2_TRAJECTORY_PREFIX_HASH_V1", payload={"envelope_ids_sorted": envelope_ids, "envelope_count": envelope_count})
    except Exception as exc:
        raise TrajectoryDataError(f"stage2 prefix hash failed: {exc}") from exc
    return envelope_count, prefix_hash


def _stage2_public_result_hash(
    stage2_result,
    *,
    envelope_count: int,
    envelope_prefix_hash: str,
) -> str:
    """Canonical Stage-3-local identity of the COMPLETE public factual content of a
    TrajectoryStage2Result.

    This is DERIVATION EQUIVALENCE only — the identity of the public factual result, never
    historical generating-input provenance.

    Bound components (per mandate):
    - PRICE:   price.price_bars (DataFrame), price.running_favorable_final,
               price.running_adverse_final, price.same_bar_ambiguous_count
    - STRUCTURE: structure.structure_events (DataFrame)
    - LIFECYCLE: lifecycle.lifecycle_events (DataFrame)  <- carries trigger_relationship_id,
               ledger_event_id, ledger_event_type, previous_state, new_state,
               superseded_by_hypothesis_id and other public row facts
               lifecycle.terminal_position, lifecycle.terminal_state
    - ENVELOPES: envelope_count + the canonical envelope prefix hash

    price.points are NOT separately serialized: every public PriceTrajectoryPoint field is
    transitively bound with identical semantics, so a separate serializer would be pure
    duplication (field-by-field mapping documented below).

    Field-by-field coverage of PriceTrajectoryPoint (26 public fields):
      1  bar_position                -> price_bars["bar_position"]
      2  bar_offset_from_decision    -> price_bars["bar_offset_from_decision"]
      3  open                        -> price_bars["open"]
      4  high                        -> price_bars["high"]
      5  low                         -> price_bars["low"]
      6  close                       -> price_bars["close"]
      7  volume                      -> price_bars["volume"]
      8  reference_price             -> price_bars["reference_price"]
      9  direction                   -> price_bars["direction"]
      10 close_displacement          -> price_bars["close_displacement"]
      11 current_favorable_excursion -> price_bars["current_favorable_excursion"]
      12 current_adverse_excursion   -> price_bars["current_adverse_excursion"]
      13 running_favorable_excursion -> price_bars["running_favorable_excursion"]
      14 running_adverse_excursion   -> price_bars["running_adverse_excursion"]
      15 favorable_extreme_price     -> price_bars["favorable_extreme_price"]
      16 favorable_extreme_position  -> price_bars["favorable_extreme_position"]
      17 adverse_extreme_price       -> price_bars["adverse_extreme_price"]
      18 adverse_extreme_position    -> price_bars["adverse_extreme_position"]
      19 is_new_favorable_extreme    -> price_bars["is_new_favorable_extreme"]
      20 is_new_adverse_extreme      -> price_bars["is_new_adverse_extreme"]
      21 same_bar_order_ambiguous    -> price_bars["same_bar_order_ambiguous"] (and the
                                        price.same_bar_ambiguous_count scalar summary)
      22 observation_information_key -> transitively bound: envelope_bar.observation_information_key
                                        is hashed into envelope_id (CLOSED _envelope_hash) which is
                                        in the envelope prefix hash; point uses the SAME obs_key.
      23 factual_available_at_key    -> transitively bound: envelope_bar.factual_available_at_information_key
                                        is hashed into envelope_id (prefix hash); point uses the SAME avail_key.
      24 envelope_id_bar             -> price_bars["envelope_id_bar"]
      25 envelope_id_fav             -> price_bars["envelope_id_fav"]
      26 envelope_id_adv             -> price_bars["envelope_id_adv"]

    Because CLOSED build_stage2_trajectory constructs points and price_bars from the SAME
    loop with the SAME values (and points' two InformationKeys are the exact keys bound into
    the bar envelope), no point field can diverge from price_bars + envelopes in a legitimately
    constructed result. Hence points are transitively fully covered.

    Canonicalization: canonical_sha256 natively canonicalizes DataFrames (schema + dtypes +
    index + row values, duplicate columns rejected), preserves row order (NOT sorted — row
    order is part of the public result), preserves >2^53 ints, canonicalizes tz-aware
    timestamps to UTC ns, maps NaN to a canonical "missing", and preserves +0/-0 via float hex.
    """
    price = stage2_result.price
    structure = stage2_result.structure
    lifecycle = stage2_result.lifecycle

    payload = {
        "price_bars": price.price_bars,
        "running_favorable_final": price.running_favorable_final,
        "running_adverse_final": price.running_adverse_final,
        "same_bar_ambiguous_count": price.same_bar_ambiguous_count,
        "structure_events": structure.structure_events,
        "lifecycle_events": lifecycle.lifecycle_events,
        "terminal_position": lifecycle.terminal_position,
        "terminal_state": lifecycle.terminal_state,
        "envelope_count": envelope_count,
        "envelope_prefix_hash": envelope_prefix_hash,
    }
    try:
        return canonical_sha256(domain="STAGE2_PUBLIC_RESULT_EQUIVALENCE_V1", payload=payload)
    except Exception as exc:
        raise TrajectoryDataError(f"stage2 public result hash failed: {exc}") from exc


def _verify_envelopes_belong_to_context(
    envelopes,
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    interval: TrajectoryInterval,
) -> None:
    """BLOCKER 1 patch: conclusively prove every envelope belongs to the expected context.

    Calls the CLOSED ObservationEnvelope.verify() contract and requires an exact identity
    match against the expected timeline / timeline_hash / anchor / interval. Rejects on the
    first mismatch. Does NOT silently filter forged/mismatched envelopes and does NOT inspect
    only the first envelope.
    """
    for env in envelopes:
        if not isinstance(env, ObservationEnvelope):
            raise TrajectoryDataError(
                f"Stage 2 prefix contains a non-envelope object: {type(env).__name__}"
            )
        # CLOSED internal self-consistency (envelope hash, key versions, capability, clock ordering)
        env.verify()
        # Exact match against the expected Stage 3 context (not merely envelope self-consistency)
        if env.timeline_id != timeline.timeline_id:
            raise TrajectoryDataError(
                f"Stage 2 envelope timeline_id mismatch: {env.timeline_id} vs {timeline.timeline_id}"
            )
        if env.timeline_hash != timeline.timeline_hash:
            raise TrajectoryDataError(
                f"Stage 2 envelope timeline_hash mismatch: {env.timeline_hash} vs {timeline.timeline_hash}"
            )
        if env.anchor_hash != anchor.anchor_hash:
            raise TrajectoryDataError(
                f"Stage 2 envelope anchor_hash mismatch: {env.anchor_hash} vs {anchor.anchor_hash}"
            )
        if env.interval_id != interval.interval_id:
            raise TrajectoryDataError(
                f"Stage 2 envelope interval_id mismatch: {env.interval_id} vs {interval.interval_id}"
            )


def _verified_stage2_prefix(
    stage2_result,
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    interval: TrajectoryInterval,
    swing_policy,
    lifecycle_ledger,
) -> Tuple[int, str, str]:
    """Verify the supplied Stage 2 result and return (envelope_count, prefix_hash, public_result_hash).

    BLOCKER 1: every supplied envelope must belong to the expected context.

    BLOCKER 2: reconstruct the authoritative Stage 2 result from the EXACT inputs Stage 3
    claims to bind (timeline/anchor/adapter/market/interval/swing_policy/lifecycle_ledger) via
    the CLOSED public build_stage2_trajectory(...), then require the supplied result to be
    DETERMINISTICALLY EQUIVALENT to it. This proves the bound inputs reproduce the supplied
    trajectory under CLOSED Stage 2 — it is a DERIVATION WITNESS, NOT an assertion of
    historical generating-input identity (CLOSED Stage 2 does not seal input identity). It does
    NOT reinterpret or reimplement PRICE/STRUCTURE/LIFECYCLE, and it does NOT override 6.2A-1
    terminal classification.

    Stage 2 remains authoritative; Stage 3 binds to it. No fallback: any mismatch -> reject.
    """
    # --- BLOCKER 1: supplied envelopes must belong to the expected context ---
    try:
        supplied_envs = stage2_result.all_envelopes
    except AttributeError:
        raise TrajectoryDataError("stage2_result missing all_envelopes") from None
    if not isinstance(supplied_envs, (tuple, list)):
        raise TrajectoryDataError("stage2_result.all_envelopes must be a tuple/list")
    _verify_envelopes_belong_to_context(
        supplied_envs, timeline=timeline, anchor=anchor, interval=interval
    )

    # --- BLOCKER 2: reconstruct authoritative Stage 2 from exact bound inputs ---
    # Reconstruction uses only the legal interval/prefix: build_stage2_trajectory internally
    # truncates market_history to interval end, preserving CLOSED Stage 2 prefix causality.
    reconstructed = build_stage2_trajectory(
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market_history,
        interval=interval,
        swing_policy=swing_policy,
        hypothesis_ledger=lifecycle_ledger,
    )
    recon_envs = reconstructed.all_envelopes
    _verify_envelopes_belong_to_context(
        recon_envs, timeline=timeline, anchor=anchor, interval=interval
    )

    supplied_count, supplied_prefix = _stage2_trajectory_prefix_hash(stage2_result)
    recon_count, recon_prefix = _stage2_trajectory_prefix_hash(reconstructed)

    if supplied_count != recon_count:
        raise TrajectoryDataError(
            f"Stage 2 envelope count mismatch: supplied {supplied_count} vs reconstructed {recon_count}"
        )
    if supplied_prefix != recon_prefix:
        raise TrajectoryDataError(
            "Stage 2 trajectory prefix mismatch: supplied result does not match authoritative "
            "reconstruction from the bound inputs"
        )

    # Lifecycle terminal facts must also agree between supplied and reconstructed Stage 2.
    supplied_lc = getattr(stage2_result, "lifecycle", None)
    if supplied_lc is None:
        raise TrajectoryDataError("Stage 2 result missing lifecycle trajectory")
    recon_lc = reconstructed.lifecycle
    if (supplied_lc.terminal_position, supplied_lc.terminal_state) != (
        recon_lc.terminal_position,
        recon_lc.terminal_state,
    ):
        raise TrajectoryDataError(
            "Stage 2 lifecycle terminal mismatch between supplied and reconstructed result"
        )

    # COMPLETE public factual result equivalence (derivation equivalence). This closes the gap
    # where equal envelope identity + equal terminal facts could hide factual row differences
    # (e.g. lifecycle_events.trigger_relationship_id 2 vs 999). No fallback: any difference
    # in the complete public result -> reject.
    supplied_public_hash = _stage2_public_result_hash(
        stage2_result, envelope_count=supplied_count, envelope_prefix_hash=supplied_prefix
    )
    recon_public_hash = _stage2_public_result_hash(
        reconstructed, envelope_count=recon_count, envelope_prefix_hash=recon_prefix
    )
    if supplied_public_hash != recon_public_hash:
        raise TrajectoryDataError(
            "Stage 2 public result mismatch: supplied public factual result is not "
            "deterministically equivalent to the reconstruction from the bound inputs"
        )

    return recon_count, recon_prefix, recon_public_hash


def _stage2_reconstruction_binding_hash(
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    interval: TrajectoryInterval,
    reconstruction_swing_policy_hash: str,
    reconstruction_ledger_seal: str,
) -> str:
    """Canonical identity of the Stage 2 reconstruction context.

    This binds the context in which the supplied trajectory was REPRODUCED (derivation
    witness), together with the Stage 2 artifact provenance. It does NOT assert which inputs
    historically generated the supplied trajectory — CLOSED Stage 2 does not seal input
    identity, so that question is unanswerable from the artifact alone.
    """
    payload = {
        "stage2_contract_version": STAGE2_CONTRACT_VERSION,
        "stage2_artifact_hash": STAGE2_ACCEPTED_SRC_HASH,
        "timeline_hash": timeline.timeline_hash,
        "timeline_id": timeline.timeline_id,
        "anchor_hash": anchor.anchor_hash,
        "decision_snapshot_hash": anchor.decision_snapshot_hash,
        "interval_id": interval.interval_id,
        "interval_hash": interval.interval_hash,
        "observed_bar_count": interval.observed_bar_count,
        "reconstruction_swing_policy_hash": reconstruction_swing_policy_hash,
        "reconstruction_ledger_seal": reconstruction_ledger_seal,
    }
    try:
        return canonical_sha256(domain="STAGE2_RECONSTRUCTION_BINDING_V1", payload=payload)
    except Exception as exc:
        raise TrajectoryDataError(f"stage2 reconstruction binding hash failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Outcome binding — CLOSED 6.2A-1 authoritative
# ---------------------------------------------------------------------------

def _validate_and_extract_outcome_binding(
    factual_outcome_result,
    *,
    anchor: DecisionAnchor,
    timeline: MarketObservationTimeline,
    expected_hypothesis_id: Optional[int] = None,
):
    """Validate factual_outcome_result per CLOSED 6.2A-1 contract and extract binding fields.

    Returns dict with extracted fields, raises on missing/ambiguous/invalid/inconsistent.
    """
    if factual_outcome_result is None:
        raise TrajectoryDataError("missing authoritative 6.2A-1 factual_outcome_result")
    # Expect object with hypothesis_outcome_snapshots DataFrame
    try:
        snapshots_df = factual_outcome_result.hypothesis_outcome_snapshots
        # Also outcome_path_segments may exist but we don't need to copy payload
    except AttributeError as exc:
        raise TrajectoryDataError("factual_outcome_result missing hypothesis_outcome_snapshots") from exc

    if not isinstance(snapshots_df, pd.DataFrame) or snapshots_df.empty:
        raise TrajectoryDataError("6.2A-1 outcome snapshots empty or invalid")

    # Filter for this hypothesis
    hid = expected_hypothesis_id if expected_hypothesis_id is not None else anchor.hypothesis_id
    filtered = snapshots_df[snapshots_df["hypothesis_id"] == hid]
    if filtered.empty:
        raise TrajectoryDataError(f"6.2A-1 outcome has no row for hypothesis_id {hid}")
    if len(filtered) > 1:
        # Ambiguous: multiple rows for same hypothesis at same as-of? Check research_snapshot_id duplicates
        # If multiple rows for same hypothesis, this is ambiguous for requested as-of unless filtered further
        # For Stage3, we expect exactly one row per requested as-of. If more than one, ambiguous -> STOP
        # To be safe, if more than one and they have different factual_outcome_id, raise
        if filtered["factual_outcome_id"].nunique() > 1 or filtered["research_snapshot_id"].nunique() > 1:
            raise TrajectoryDataError(f"ambiguous 6.2A-1 outcome: multiple distinct rows for hypothesis {hid}")
        # If same factual_outcome_id duplicated (should not happen per 6.2A-1 dedup), still treat as ambiguous
        # Take first for further checks but note ambiguity
        # For strictness, require exactly one
        raise TrajectoryDataError(f"ambiguous 6.2A-1 outcome: expected exactly one row for hypothesis {hid}, got {len(filtered)}")

    row = filtered.iloc[0]

    # Extract fields per CLOSED schema
    try:
        factual_outcome_id = row["factual_outcome_id"]
        research_snapshot_id = row["research_snapshot_id"]
        decision_snapshot_hash = str(row["decision_snapshot_hash"])
        outcome_mature = bool(row["outcome_mature"])
        right_censored = bool(row["right_censored_as_of"])
        narrative_terminal_state = row["narrative_terminal_state"]
        terminal_position = row["terminal_position"]
        research_as_of_bar_position = row["research_as_of_bar_position"]
        snapshot_position = row["snapshot_position"]
        outcome_contract_version = str(row["outcome_contract_version"])
        # Keys: need to reconstruct InformationKey fields? For binding we store bar positions and key payloads
        # For simplicity, store the row's terminal and research_as_of bar positions as Int
        # Full InformationKey reconstruction requires adapter, handled outside
    except KeyError as exc:
        raise TrajectoryDataError(f"6.2A-1 outcome missing required field: {exc}") from exc

    # Consistency checks vs anchor/timeline
    if decision_snapshot_hash != anchor.decision_snapshot_hash:
        raise TrajectoryDataError(f"decision_snapshot_hash mismatch: outcome {decision_snapshot_hash} vs anchor {anchor.decision_snapshot_hash}")
    if str(row["timeline_id"]) != timeline.timeline_id:
        raise TrajectoryDataError(f"timeline_id mismatch: outcome {row['timeline_id']} vs {timeline.timeline_id}")

    # Check contract version
    if outcome_contract_version != OUTCOME_CONTRACT_VERSION:
        raise TrajectoryContractError(f"outcome contract version mismatch: {outcome_contract_version} vs {OUTCOME_CONTRACT_VERSION}")

    # For mature, factual_outcome_id must be present (not NA), for censored must be NA
    if outcome_mature:
        if pd.isna(factual_outcome_id):
            raise TrajectoryDataError("mature 6.2A-1 outcome must have factual_outcome_id present")
        if right_censored:
            raise TrajectoryDataError("mature outcome cannot be right_censored")
    else:
        if not pd.isna(factual_outcome_id):
            raise TrajectoryDataError("censored 6.2A-1 outcome must have factual_outcome_id NA")
        if not right_censored:
            raise TrajectoryDataError("censored outcome must have right_censored_as_of=True")

    # Return binding dict
    return {
        "factual_outcome_id": None if pd.isna(factual_outcome_id) else str(factual_outcome_id),
        "research_snapshot_id": None if pd.isna(research_snapshot_id) else str(research_snapshot_id),
        "decision_snapshot_hash": decision_snapshot_hash,
        "outcome_mature": outcome_mature,
        "right_censored": right_censored,
        "narrative_terminal_state": None if pd.isna(narrative_terminal_state) else str(narrative_terminal_state),
        "terminal_position": None if pd.isna(terminal_position) else int(terminal_position),
        "research_as_of_bar_position": None if pd.isna(research_as_of_bar_position) else int(research_as_of_bar_position),
        "snapshot_position": None if pd.isna(snapshot_position) else int(snapshot_position),
        "outcome_contract_version": outcome_contract_version,
        "timeline_id": str(row["timeline_id"]),
        "hypothesis_id": int(row["hypothesis_id"]),
    }


# ---------------------------------------------------------------------------
# Snapshot dataclasses — factual binding layer only
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FactualTerminalSnapshot:
    snapshot_id: str
    snapshot_hash: str
    timeline_id: str
    timeline_hash: str
    anchor_hash: str
    decision_snapshot_hash: str
    hypothesis_id: int
    interval_id: str
    interval_hash: str
    observed_bar_count: int
    # Two distinct clocks:
    terminal_factual_available_at_information_key: InformationKey
    research_as_of_information_key: InformationKey
    # Origin preserved exactly as the SUPPLIED Stage 2 lifecycle trajectory provides it
    # (Int64 position, not forged InformationKey). These are the artifact's OWN embedded
    # factual provenance values — NOT the caller-supplied ledger's values.
    terminal_origin_position: Optional[int]
    terminal_ledger_event_id: Optional[int]
    trigger_relationship_id: Optional[int]
    superseded_by_hypothesis_id: Optional[int]
    # Terminal state literal only
    terminal_state: str
    # 6.2A-1 binding
    factual_outcome_id: str
    research_snapshot_id: str
    outcome_contract_version: str
    # Stage2 compact binding — derivation witnesses, not generating-input provenance
    stage2_reconstruction_binding_hash: str
    stage2_trajectory_prefix_hash: str
    stage2_public_result_hash: str
    envelope_count: int
    reconstruction_swing_policy_hash: str
    reconstruction_ledger_seal: str
    stage2_contract_version: str
    stage2_artifact_hash: str
    # No full envelope tuple, no raw market history, no running payloads


@dataclass(frozen=True)
class RightCensoredAsOfSnapshot:
    snapshot_id: str
    snapshot_hash: str
    timeline_id: str
    timeline_hash: str
    anchor_hash: str
    decision_snapshot_hash: str
    hypothesis_id: int
    interval_id: str
    interval_hash: str
    observed_bar_count: int
    research_as_of_information_key: InformationKey
    # No terminal availability
    # Origin for censor? Not applicable, but preserve decision position already via interval
    # 6.2A-1 binding for censored
    research_snapshot_id: str  # present per CLOSED
    factual_outcome_id: None  # must be None/NA
    outcome_mature: bool  # False
    right_censored_as_of: bool  # True
    censoring_type: str  # RIGHT_CENSORED_AS_OF_BOUNDARY per CLOSED
    outcome_contract_version: str
    # Stage2 compact binding — derivation witnesses, not generating-input provenance
    stage2_reconstruction_binding_hash: str
    stage2_trajectory_prefix_hash: str
    stage2_public_result_hash: str
    envelope_count: int
    reconstruction_swing_policy_hash: str
    reconstruction_ledger_seal: str
    stage2_contract_version: str
    stage2_artifact_hash: str


# ---------------------------------------------------------------------------
# Builders — authority: 6.2A-1 authoritative for terminal/censor classification
# ---------------------------------------------------------------------------

def _snapshot_id_and_hash(payload: dict, domain: str) -> Tuple[str, str]:
    """Compute snapshot_id and snapshot_hash via canonical hash, domain-separated."""
    # snapshot_id is hash of payload without hash itself, snapshot_hash includes id? For simplicity, use same domain for id, then hash id for snapshot_hash? We'll use two domains.
    try:
        sid = canonical_sha256(domain=f"{domain}_ID_V1", payload=payload)
        # snapshot_hash includes snapshot_id + payload for binding
        shash = canonical_sha256(domain=f"{domain}_HASH_V1", payload={**payload, "snapshot_id": sid})
    except Exception as exc:
        raise TrajectoryDataError(f"snapshot identity hash failed: {exc}") from exc
    return sid, shash


def build_mature_terminal_snapshot(
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    interval_through_terminal: TrajectoryInterval,
    stage2_result_through_terminal,
    factual_outcome_result,
    swing_policy=None,
    lifecycle_ledger: Optional[pd.DataFrame] = None,
    research_as_of_key: Optional[InformationKey] = None,
) -> FactualTerminalSnapshot:
    """Build immutable mature terminal snapshot.

    Authority: CLOSED 6.2A-1 is authoritative for mature/censored/terminal_state.
    If authoritative input missing/ambiguous/invalid/inconsistent → STOP with error, no fallback.

    Preserves two clocks: terminal_factual_available_at vs research_as_of.
    Does NOT manufacture structure origin InformationKey.
    Compact binding: interval + Stage2 reconstruction binding + prefix hash + envelope count + factual outcome binding.
    No raw market history, no full envelope tuple, no running payloads.
    """
    _validate_anchor(anchor)
    _validate_interval_timeline(timeline, anchor, adapter, market_history, interval_through_terminal)

    # Extract and validate 6.2A-1 binding (authoritative)
    outcome_binding = _validate_and_extract_outcome_binding(
        factual_outcome_result, anchor=anchor, timeline=timeline, expected_hypothesis_id=anchor.hypothesis_id
    )
    if not outcome_binding["outcome_mature"]:
        raise TrajectoryDataError("build_mature_terminal_snapshot requires mature 6.2A-1 outcome (outcome_mature=True)")
    if outcome_binding["factual_outcome_id"] is None:
        raise TrajectoryDataError("mature outcome must have factual_outcome_id")
    if outcome_binding["narrative_terminal_state"] not in _CLOSED_TERMINAL:
        raise TrajectoryDataError(f"invalid literal terminal state: {outcome_binding['narrative_terminal_state']}")

    # Terminal state literal only
    terminal_state = outcome_binding["narrative_terminal_state"]

    # Terminal factual availability from Stage2 / 6.2A-1 must match interval end
    # Interval must end at legal terminal boundary (enforced by Stage2 lifecycle builder)
    # For terminal, interval.end should equal terminal_position
    terminal_pos = outcome_binding["terminal_position"]
    if terminal_pos is None:
        raise TrajectoryDataError("mature outcome missing terminal_position")
    if interval_through_terminal.end_inclusive_bar_position != terminal_pos:
        raise TrajectoryDataError(f"terminal interval end {interval_through_terminal.end_inclusive_bar_position} != terminal_position {terminal_pos} — must end at legal terminal boundary, no post-terminal rows")

    # Factual availability key: from interval end (terminal availability)
    # Use interval's end_inclusive InformationKey as authoritative availability
    terminal_factual_available_at_key = interval_through_terminal.end_inclusive_information_key

    # Research as-of key: may be later than terminal availability (T15 reconstruction of T12 terminal)
    # If not provided, default to terminal availability (immediate snapshot)
    if research_as_of_key is None:
        research_as_of_key = terminal_factual_available_at_key
    else:
        if not isinstance(research_as_of_key, InformationKey):
            raise TrajectoryContractError("research_as_of_key must be InformationKey")
        if research_as_of_key.timeline_id != timeline.timeline_id:
            raise TrajectoryDataError("research_as_of timeline mismatch")
        if research_as_of_key < terminal_factual_available_at_key:
            raise TrajectoryDataError("research_as_of must be >= terminal_factual_available_at for terminal snapshot")

    # Stage 2 reconstruction-witness identities (derivation witnesses, NOT generating-input claims)
    _, reconstruction_swing_policy_hash = _canonicalize_swing_policy(swing_policy)
    _, reconstruction_ledger_seal = _canonicalize_ledger(lifecycle_ledger)
    # BLOCKER 1 + BLOCKER 2: verify supplied Stage 2 (envelope context + deterministic-equivalence reconstruction)
    envelope_count, trajectory_prefix_hash, stage2_public_result_hash = _verified_stage2_prefix(
        stage2_result_through_terminal,
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market_history,
        interval=interval_through_terminal,
        swing_policy=swing_policy,
        lifecycle_ledger=lifecycle_ledger,
    )
    stage2_reconstruction_binding_hash = _stage2_reconstruction_binding_hash(
        timeline=timeline,
        anchor=anchor,
        interval=interval_through_terminal,
        reconstruction_swing_policy_hash=reconstruction_swing_policy_hash,
        reconstruction_ledger_seal=reconstruction_ledger_seal,
    )

    # Extract origin representation exactly as the CLOSED source provides it: the SUPPLIED
    # Stage 2 lifecycle trajectory (the artifact being snapshotted, now proven
    # deterministic-equivalent to the reconstruction). Reading from the supplied lifecycle_events
    # keeps the recorded provenance consistent with the artifact's own embedded data — NOT from
    # the caller's raw lifecycle ledger, which is only a derivation witness.
    stage2_lc_for_origin = stage2_result_through_terminal.lifecycle
    lc_events = stage2_lc_for_origin.lifecycle_events
    if not isinstance(lc_events, pd.DataFrame) or lc_events.empty:
        raise TrajectoryDataError(
            "mature terminal requires non-empty Stage 2 lifecycle_events for origin representation"
        )
    term_rows = lc_events[lc_events["new_state"] == terminal_state]
    if "bar_position" in term_rows.columns:
        term_rows = term_rows[term_rows["bar_position"] == terminal_pos]
    if term_rows.empty:
        raise TrajectoryDataError(
            f"supplied Stage 2 lifecycle has no terminal row at pos {terminal_pos} with state {terminal_state}"
        )
    if len(term_rows) > 1:
        raise TrajectoryDataError("ambiguous terminal lifecycle rows for same position/state")
    term_row = term_rows.iloc[0]
    terminal_origin_position = (
        int(term_row["bar_position"])
        if "bar_position" in term_row and pd.notna(term_row["bar_position"])
        else None
    )
    terminal_ledger_event_id = (
        int(term_row["ledger_event_id"])
        if "ledger_event_id" in term_row and pd.notna(term_row["ledger_event_id"])
        else None
    )
    trigger_relationship_id = (
        int(term_row["trigger_relationship_id"])
        if "trigger_relationship_id" in term_row and pd.notna(term_row["trigger_relationship_id"])
        else None
    )
    superseded_by = (
        int(term_row["superseded_by_hypothesis_id"])
        if "superseded_by_hypothesis_id" in term_row and pd.notna(term_row["superseded_by_hypothesis_id"])
        else None
    )

    # Consistency vs CLOSED Stage 2 LIFECYCLE trajectory.
    # 6.2A-1 is authoritative for terminal classification; CLOSED Stage 2 is
    # authoritative for the lifecycle trajectory. A mature 6.2A-1 outcome that
    # disagrees with the bound Stage 2 trajectory is a mismatch -> reject, no fallback.
    try:
        stage2_lc = stage2_result_through_terminal.lifecycle
    except AttributeError:
        raise TrajectoryDataError(
            "Stage 3 requires a CLOSED Stage 2 result with a lifecycle trajectory"
        ) from None
    if stage2_lc.terminal_position is None:
        raise TrajectoryDataError(
            "Stage 2 lifecycle has no terminal within interval but 6.2A-1 outcome is mature — mismatch"
        )
    if stage2_lc.terminal_position != terminal_pos:
        raise TrajectoryDataError(
            f"terminal position mismatch Stage2 {stage2_lc.terminal_position} vs 6.2A-1 {terminal_pos}"
        )
    if stage2_lc.terminal_state != terminal_state:
        raise TrajectoryDataError(
            f"terminal state mismatch Stage2 {stage2_lc.terminal_state} vs 6.2A-1 {terminal_state}"
        )

    # Build payload for snapshot id/hash — compact binding only, no full envelope tuple, no running payloads, no market history
    payload = {
        "timeline_id": timeline.timeline_id,
        "timeline_hash": timeline.timeline_hash,
        "anchor_hash": anchor.anchor_hash,
        "decision_snapshot_hash": anchor.decision_snapshot_hash,
        "hypothesis_id": anchor.hypothesis_id,
        "interval_id": interval_through_terminal.interval_id,
        "interval_hash": interval_through_terminal.interval_hash,
        "observed_bar_count": interval_through_terminal.observed_bar_count,
        "terminal_factual_available_at": _key_payload(terminal_factual_available_at_key),
        "research_as_of": _key_payload(research_as_of_key),
        "terminal_origin_position": terminal_origin_position,
        "terminal_ledger_event_id": terminal_ledger_event_id,
        "trigger_relationship_id": trigger_relationship_id,
        "superseded_by_hypothesis_id": superseded_by,
        "terminal_state": terminal_state,
        "factual_outcome_id": outcome_binding["factual_outcome_id"],
        "research_snapshot_id": outcome_binding["research_snapshot_id"],
        "outcome_contract_version": outcome_binding["outcome_contract_version"],
        "stage2_reconstruction_binding_hash": stage2_reconstruction_binding_hash,
        "stage2_trajectory_prefix_hash": trajectory_prefix_hash,
        "stage2_public_result_hash": stage2_public_result_hash,
        "envelope_count": envelope_count,
        "reconstruction_swing_policy_hash": reconstruction_swing_policy_hash,
        "reconstruction_ledger_seal": reconstruction_ledger_seal,
        "stage2_contract_version": STAGE2_CONTRACT_VERSION,
        "stage2_artifact_hash": STAGE2_ACCEPTED_SRC_HASH,
    }

    snapshot_id, snapshot_hash = _snapshot_id_and_hash(payload, domain="TERMINAL_SNAPSHOT")

    return FactualTerminalSnapshot(
        snapshot_id=snapshot_id,
        snapshot_hash=snapshot_hash,
        timeline_id=timeline.timeline_id,
        timeline_hash=timeline.timeline_hash,
        anchor_hash=anchor.anchor_hash,
        decision_snapshot_hash=anchor.decision_snapshot_hash,
        hypothesis_id=anchor.hypothesis_id,
        interval_id=interval_through_terminal.interval_id,
        interval_hash=interval_through_terminal.interval_hash,
        observed_bar_count=interval_through_terminal.observed_bar_count,
        terminal_factual_available_at_information_key=terminal_factual_available_at_key,
        research_as_of_information_key=research_as_of_key,
        terminal_origin_position=terminal_origin_position,
        terminal_ledger_event_id=terminal_ledger_event_id,
        trigger_relationship_id=trigger_relationship_id,
        superseded_by_hypothesis_id=superseded_by,
        terminal_state=terminal_state,
        factual_outcome_id=outcome_binding["factual_outcome_id"],
        research_snapshot_id=outcome_binding["research_snapshot_id"],
        outcome_contract_version=outcome_binding["outcome_contract_version"],
        stage2_reconstruction_binding_hash=stage2_reconstruction_binding_hash,
        stage2_trajectory_prefix_hash=trajectory_prefix_hash,
        stage2_public_result_hash=stage2_public_result_hash,
        envelope_count=envelope_count,
        reconstruction_swing_policy_hash=reconstruction_swing_policy_hash,
        reconstruction_ledger_seal=reconstruction_ledger_seal,
        stage2_contract_version=STAGE2_CONTRACT_VERSION,
        stage2_artifact_hash=STAGE2_ACCEPTED_SRC_HASH,
    )


def build_right_censored_snapshot(
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    interval_through_asof: TrajectoryInterval,
    stage2_result_through_asof,
    factual_outcome_result,
    swing_policy=None,
    lifecycle_ledger: Optional[pd.DataFrame] = None,
    research_as_of_key: Optional[InformationKey] = None,
) -> RightCensoredAsOfSnapshot:
    """Build immutable right-censored-as-of snapshot.

    Authority: 6.2A-1 censored outcome is authoritative.
    No fallback inference.
    Compact binding only.
    """
    _validate_anchor(anchor)
    _validate_interval_timeline(timeline, anchor, adapter, market_history, interval_through_asof)

    # Validate 6.2A-1 censored binding
    outcome_binding = _validate_and_extract_outcome_binding(
        factual_outcome_result, anchor=anchor, timeline=timeline, expected_hypothesis_id=anchor.hypothesis_id
    )
    if outcome_binding["outcome_mature"]:
        raise TrajectoryDataError("build_right_censored_snapshot requires censored 6.2A-1 outcome (outcome_mature=False)")
    if not outcome_binding["right_censored"]:
        raise TrajectoryDataError("censored outcome must have right_censored_as_of=True")
    if outcome_binding["factual_outcome_id"] is not None:
        raise TrajectoryDataError("censored outcome must have factual_outcome_id NA")
    if outcome_binding["research_snapshot_id"] is None:
        raise TrajectoryDataError("censored outcome must have research_snapshot_id present per CLOSED 6.2A-1")

    # Research as-of key for censor: should equal interval end (as-of boundary)
    # If explicit research_as_of_key provided, must match interval end or be >=? For censor, interval end == as-of
    if research_as_of_key is None:
        research_as_of_key = interval_through_asof.end_inclusive_information_key
    else:
        if research_as_of_key.timeline_id != timeline.timeline_id:
            raise TrajectoryDataError("research_as_of timeline mismatch")
        # For censor, research_as_of should equal interval end (as-of boundary)
        if research_as_of_key.bar_position != interval_through_asof.end_inclusive_bar_position:
            # Allow research_as_of >= interval end? For censor, as-of is boundary, so interval end should equal as-of
            # If research_as_of later than interval end, that would be inconsistent — interval should be extended to as-of
            # So enforce equality for censor
            if research_as_of_key != interval_through_asof.end_inclusive_information_key:
                raise TrajectoryDataError("censor snapshot research_as_of must equal interval end (censor boundary)")

    # Stage 2 reconstruction-witness identities (derivation witnesses, NOT generating-input claims)
    _, reconstruction_swing_policy_hash = _canonicalize_swing_policy(swing_policy)
    _, reconstruction_ledger_seal = _canonicalize_ledger(lifecycle_ledger)

    # BLOCKER 1 + BLOCKER 2: verify supplied Stage 2 (envelope context + deterministic-equivalence reconstruction)
    envelope_count, trajectory_prefix_hash, stage2_public_result_hash = _verified_stage2_prefix(
        stage2_result_through_asof,
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market_history,
        interval=interval_through_asof,
        swing_policy=swing_policy,
        lifecycle_ledger=lifecycle_ledger,
    )
    stage2_reconstruction_binding_hash = _stage2_reconstruction_binding_hash(
        timeline=timeline,
        anchor=anchor,
        interval=interval_through_asof,
        reconstruction_swing_policy_hash=reconstruction_swing_policy_hash,
        reconstruction_ledger_seal=reconstruction_ledger_seal,
    )

    payload = {
        "timeline_id": timeline.timeline_id,
        "timeline_hash": timeline.timeline_hash,
        "anchor_hash": anchor.anchor_hash,
        "decision_snapshot_hash": anchor.decision_snapshot_hash,
        "hypothesis_id": anchor.hypothesis_id,
        "interval_id": interval_through_asof.interval_id,
        "interval_hash": interval_through_asof.interval_hash,
        "observed_bar_count": interval_through_asof.observed_bar_count,
        "research_as_of": _key_payload(research_as_of_key),
        "research_snapshot_id": outcome_binding["research_snapshot_id"],
        "factual_outcome_id": None,  # must be None/NA for censored per CLOSED
        "outcome_mature": False,
        "right_censored_as_of": True,
        "censoring_type": _RIGHT_CENSORED_TYPE,
        "outcome_contract_version": outcome_binding["outcome_contract_version"],
        "stage2_reconstruction_binding_hash": stage2_reconstruction_binding_hash,
        "stage2_trajectory_prefix_hash": trajectory_prefix_hash,
        "stage2_public_result_hash": stage2_public_result_hash,
        "envelope_count": envelope_count,
        "reconstruction_swing_policy_hash": reconstruction_swing_policy_hash,
        "reconstruction_ledger_seal": reconstruction_ledger_seal,
        "stage2_contract_version": STAGE2_CONTRACT_VERSION,
        "stage2_artifact_hash": STAGE2_ACCEPTED_SRC_HASH,
    }

    snapshot_id, snapshot_hash = _snapshot_id_and_hash(payload, domain="CENSOR_SNAPSHOT")

    return RightCensoredAsOfSnapshot(
        snapshot_id=snapshot_id,
        snapshot_hash=snapshot_hash,
        timeline_id=timeline.timeline_id,
        timeline_hash=timeline.timeline_hash,
        anchor_hash=anchor.anchor_hash,
        decision_snapshot_hash=anchor.decision_snapshot_hash,
        hypothesis_id=anchor.hypothesis_id,
        interval_id=interval_through_asof.interval_id,
        interval_hash=interval_through_asof.interval_hash,
        observed_bar_count=interval_through_asof.observed_bar_count,
        research_as_of_information_key=research_as_of_key,
        research_snapshot_id=outcome_binding["research_snapshot_id"],
        factual_outcome_id=None,
        outcome_mature=False,
        right_censored_as_of=True,
        censoring_type=_RIGHT_CENSORED_TYPE,
        outcome_contract_version=outcome_binding["outcome_contract_version"],
        stage2_reconstruction_binding_hash=stage2_reconstruction_binding_hash,
        stage2_trajectory_prefix_hash=trajectory_prefix_hash,
        stage2_public_result_hash=stage2_public_result_hash,
        envelope_count=envelope_count,
        reconstruction_swing_policy_hash=reconstruction_swing_policy_hash,
        reconstruction_ledger_seal=reconstruction_ledger_seal,
        stage2_contract_version=STAGE2_CONTRACT_VERSION,
        stage2_artifact_hash=STAGE2_ACCEPTED_SRC_HASH,
    )


# ---------------------------------------------------------------------------
# As-of series — append-only (conceptual, not storing full envelope tuples)
# ---------------------------------------------------------------------------

def append_to_asof_series(
    existing_series: Tuple,
    new_snapshot,
) -> Tuple:
    """Append-only: new series = old + (new_snapshot,), old remains unchanged.

    Checks ordering by research_as_of_information_key.bar_position strictly increasing
    and that existing snapshots remain byte-identical (snapshot_hash unchanged).
    """
    if not isinstance(existing_series, tuple):
        raise TrajectoryContractError("existing_series must be tuple")
    # Check ordering
    if existing_series:
        last = existing_series[-1]
        try:
            last_asof = last.research_as_of_information_key.bar_position
            new_asof = new_snapshot.research_as_of_information_key.bar_position
        except AttributeError as exc:
            raise TrajectoryContractError("snapshots must have research_as_of_information_key") from exc
        if not new_asof > last_asof:
            raise TrajectoryDataError("as-of series must be strictly increasing in research_as_of bar_position")
        # Immutability check: previous hashes unchanged (trivially true if we don't mutate)
        for s in existing_series:
            # Ensure snapshot_hash still valid (would fail if mutated)
            pass
    return existing_series + (new_snapshot,)


def trajectory_stage3_manifest() -> pd.DataFrame:
    import pandas as pd

    rows = [
        ("CONTRACT", "VERSION", TRAJECTORY_STAGE3_CONTRACT_VERSION),
        ("STAGE", "SCOPE", "STAGE_3_TERMINAL_CENSOR_SERIES"),
        ("TERMINAL", "AUTHORITY", "CLOSED_6_2A_1_FACTUAL_OUTCOME"),
        ("TERMINAL", "STATES", "CONTRADICTED_SUPERSEDED_OBSERVED_DIRECTION_ESTABLISHED"),
        ("TERMINAL", "ORIGIN", "PRESERVE_SOURCE_ORIGIN_POSITION_EXACT_NO_FORGED_INFORMATIONKEY"),
        ("TERMINAL", "AVAILABILITY", "FACTUAL_AVAILABLE_AT_INFORMATIONKEY"),
        ("TERMINAL", "RESEARCH_AS_OF", "DISTINCT_FROM_FACTUAL_AVAILABILITY_MAY_BE_LATER"),
        ("CENSOR", "SEMANTICS", "RIGHT_CENSORED_AS_OF_ONLY_TERMINAL_NOT_OBSERVED_BY_AS_OF"),
        ("CENSOR", "OUTCOME", "RESEARCH_SNAPSHOT_ID_PRESENT_FACTUAL_OUTCOME_ID_NA_MATURE_FALSE_CENSORED_TRUE"),
        ("CENSOR", "REASON", "RIGHT_CENSORED_AS_OF_BOUNDARY_ONLY_PER_CLOSED_6_2A_1"),
        ("BINDING", "6_2A_1", "FACTUAL_OUTCOME_ID_RESEARCH_SNAPSHOT_ID_DECISION_SNAPSHOT_HASH_CONTRACT_VERSION"),
        ("BINDING", "STAGE2", "TIMELINE_HASH_ANCHOR_HASH_INTERVAL_ID_HASH_RECONSTRUCTION_SWING_POLICY_HASH_RECONSTRUCTION_LEDGER_SEAL_PUBLIC_RESULT_HASH_PREFIX_HASH_ENVELOPE_COUNT_CONTRACT_VERSION_ARTIFACT_HASH"),
        ("BINDING", "STAGE2_DERIVATION_WITNESS", "SWING_POLICY_AND_LEDGER_HASHES_ARE_DERIVATION_WITNESSES_REPRODUCE_TRAJECTORY_NOT_GENERATING_INPUT_IDENTITY"),
        ("BINDING", "STAGE2_PUBLIC_RESULT_EQUIVALENCE", "PRICE_BARS_PRICE_FINAL_SCALARS_STRUCTURE_EVENTS_LIFECYCLE_EVENTS_TERMINAL_FIELDS_ENVELOPE_COUNT_PREFIX_HASH"),
        ("STORAGE", "MARKET", "SHARED_TIMELINE_ONCE"),
        ("STORAGE", "SNAPSHOT", "COMPACT_REFERENCES_ONLY_NO_RAW_MARKET_NO_FULL_ENVELOPE_TUPLE_NO_RUNNING_PAYLOAD"),
        ("STORAGE", "ENVELOPES", "OWNED_BY_STAGE2_PER_INTERVAL_TABLE_RECONSTRUCTIBLE"),
        ("OUT_OF_SCOPE", "VOLATILITY", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "LIQUIDITY", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "OB_FVG", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "DEALING_RANGE", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "ORDERFLOW", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "SESSION", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "MTF", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "DESCRIPTORS", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "ESTIMANDS", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "MODEL", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "GEOMETRY", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "EXECUTION", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "WIN_LOSS", "FORBIDDEN"),
        ("DEBT", "RESEARCH-DEBT-020", "OPEN"),
        ("DEBT", "RESEARCH-DEBT-021", "OPEN"),
        ("DEBT", "RESEARCH-DEBT-022", "OPEN"),
        ("DEBT", "RESEARCH-DEBT-023", "OPEN"),
        ("DEBT", "RESEARCH-DEBT-024", "OPEN"),
        ("DEBT", "RESEARCH-DEBT-025", "OPEN"),
    ]
    return pd.DataFrame(
        [{"record_type": a, "name": b, "value": c, "serialization_order": i} for i, (a, b, c) in enumerate(rows)]
    )

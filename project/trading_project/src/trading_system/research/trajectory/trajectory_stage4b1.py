"""Module 6.2A-4 V1 Stage 4B-1: Shared Causal Structure Surface.

One shared, hypothesis-independent causal structure surface built from the CLOSED public chain:

    2.1A Swing Detector (CausalAdaptiveSwingDetector)
    → 2.1B Swing Sequence (ConfirmedSwingSequenceEngine)
    → 2.1C Structural Break (CausalStructuralBreakEngine)

This is research infrastructure for future Stage 4B-2. It does NOT reuse a hypothesis-relative
Stage 2 structure-envelope identity as shared market identity.

Design guarantees:
- COMPLETE public factual result of 2.1A + 2.1B + 2.1C is bound (not merely the downstream-consumed
  subset). The complete result = the derived columns of all three stages (cumulative in 2.1C).
- Shared storage: one surface per exact surface identity; hypothesis consumers later reference a
  compact prefix binding, never a per-hypothesis copy.
- Information time: origin position is NEVER used as factual availability. Facts are per-bar; a
  confirmed swing at bar i is available at bar i (COMPLETED_ROW_AVAILABLE), preserving its earlier
  origin as a positional Int64. No origin InformationKey is manufactured.
- Self-integrity: the surface holds mutable DataFrames; verify_surface_integrity recomputes the
  component hashes + surface_id from CURRENT content and rejects stale/forged fields.
- All identities are DETERMINISTIC RECONSTRUCTION / DERIVATION WITNESSES, not historical
  generating-input provenance (NOT_CERTIFIED / UNVERIFIABLE).

RESEARCH-DEBT-020/021/022/023/024/025 remain OPEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Optional, Tuple

import pandas as pd

from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import (
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
    TimelineAdapterError,
)
from trading_system.research.trajectory.trajectory_contract import (
    MarketObservationTimeline,
    TIMELINE_ADAPTER_KIND,
    TrajectoryContractError,
    TrajectoryDataError,
)

from trading_system.structure.swing_detector import (
    CausalAdaptiveSwingDetector,
    SwingDataError,
)
from trading_system.structure.swing_sequence import (
    ConfirmedSwingSequenceEngine,
    SwingSequenceError,
)
from trading_system.structure.structural_breaks import (
    CausalStructuralBreakEngine,
    StructuralBreakError,
)

TimelineAdapter = PositionalTimelineAdapter | TimeIndexedTimelineAdapter

TRAJECTORY_STAGE4B1_CONTRACT_VERSION: Final = "CAUSAL_SHARED_STRUCTURE_SURFACE_V1"

_2_1A_CONTRACT_VERSION: Final = "MODULE_2_1A_V1_1"
_2_1B_CONTRACT_VERSION: Final = "MODULE_2_1B_V1"
_2_1C_CONTRACT_VERSION: Final = "MODULE_2_1C_V1_1"

_STRUCTURE_DOMAIN: Final = "SHARED_STRUCTURE"

# Exact CLOSED derived output schemas (mirrored verbatim from each module's _OUTPUT_COLUMNS).
_2_1A_OUTPUT_COLUMNS: Final = (
    "candidate_side", "candidate_origin_position", "candidate_price",
    "candidate_reversal_distance", "candidate_reversal_fraction",
    "candidate_reversal_evidence", "candidate_continuation_history_count",
    "candidate_confirmed_history_count", "candidate_confirmation_threshold",
    "swing_high_reversal_evidence", "swing_low_reversal_evidence",
    "swing_high_confirmed", "swing_low_confirmed", "swing_origin_position",
    "swing_price", "swing_confirmation_position", "swing_confirmation_price",
    "swing_reversal_distance", "swing_reversal_fraction", "swing_reversal_evidence",
    "swing_continuation_history_count", "swing_confirmed_history_percentile",
    "swing_confirmed_history_count", "swing_confirmation_threshold",
)
_2_1B_OUTPUT_COLUMNS: Final = (
    "structure_event_type", "swing_sequence_class", "comparison_available",
    "previous_same_type_price", "previous_same_type_origin_position",
    "current_structure_swing_price", "current_structure_origin_position",
    "current_structure_confirmation_position", "same_type_log_price_change",
)
_2_1C_OUTPUT_COLUMNS: Final = (
    "monitored_high_price", "monitored_high_origin_position",
    "monitored_high_confirmation_position", "monitored_high_first_wick_breach_position",
    "monitored_high_first_close_breach_position", "monitored_high_wick_breached",
    "monitored_high_close_breached", "monitored_low_price",
    "monitored_low_origin_position", "monitored_low_confirmation_position",
    "monitored_low_first_wick_breach_position", "monitored_low_first_close_breach_position",
    "monitored_low_wick_breached", "monitored_low_close_breached",
    "high_wick_breach_event", "high_close_breach_event", "low_wick_breach_event",
    "low_close_breach_event", "high_wick_only_breach_event", "low_wick_only_breach_event",
    "high_wick_overshoot_fraction", "high_close_overshoot_fraction",
    "low_wick_overshoot_fraction", "low_close_overshoot_fraction",
    "high_wick_break_evidence", "high_close_break_evidence", "low_wick_break_evidence",
    "low_close_break_evidence", "wick_break_history_count", "close_break_history_count",
    "structure_state_before", "structure_state_after", "structural_break_event",
)

_ALL_DERIVED_COLUMNS: Final = _2_1A_OUTPUT_COLUMNS + _2_1B_OUTPUT_COLUMNS + _2_1C_OUTPUT_COLUMNS

_LEGAL_BOUNDARY_PHASES: Final = frozenset(
    {
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    }
)


# ---------------------------------------------------------------------------
# Surface types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stage4B1StructureSurface:
    """One shared, hypothesis-independent structure surface.

    `frame` holds the complete cumulative CLOSED chain output (2.1C output, which preserves all
    2.1A + 2.1B derived columns). `derived_2_1a/2_1b/2_1c` are the incremental derived columns of
    each stage; `all_derived` = their concatenation. Component hashes bind each stage's complete
    derived result; `public_result_hash` binds the complete derived result; `surface_id` composes
    everything. Mutable DataFrame -> every consumer must call verify_surface_integrity first.
    """

    domain: str
    contract_version: str
    timeline_id: str
    timeline_hash: str
    adapter_kind: TIMELINE_ADAPTER_KIND
    high_col: str
    low_col: str
    swing_policy_hash: str  # reconstruction witness (evidence-only when policy is None)
    reconstruction_input_hash: str
    derived_2_1a: Tuple[str, ...]
    derived_2_1b: Tuple[str, ...]
    derived_2_1c: Tuple[str, ...]
    hash_2_1a: str
    hash_2_1b: str
    hash_2_1c: str
    public_result_hash: str
    surface_id: str
    frame: pd.DataFrame  # complete cumulative result (mutable!)


@dataclass(frozen=True)
class Stage4B1PrefixBinding:
    """Compact reference to a shared structure surface + immutable prefix identity through a
    legal boundary. Contains NO physical structure rows.
    """

    domain: str
    surface_id: str
    boundary_position: int
    boundary_key: InformationKey
    prefix_hash: str
    prefix_row_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_hash(domain: str, payload) -> str:
    try:
        return canonical_sha256(domain=domain, payload=payload)
    except Exception as exc:
        raise TrajectoryDataError(f"Stage 4B-1 hash failed ({domain}): {exc}") from exc


def _swing_policy_payload(swing_policy) -> dict:
    if swing_policy is None:
        return {"type": "evidence_only", "version": _2_1A_CONTRACT_VERSION}
    try:
        q = float(swing_policy.quantile)
        cont = tuple(float(x) for x in swing_policy.prior_continuation_reversals)
        conf = tuple(float(x) for x in swing_policy.prior_confirmed_reversals)
    except Exception as exc:
        raise TrajectoryDataError(f"invalid swing_policy: {exc}") from exc
    for v in (q,) + cont + conf:
        if not _finite(v):
            raise TrajectoryDataError("swing_policy contains non-finite value")
    return {
        "type": "empirical_confirmation_policy",
        "version": _2_1A_CONTRACT_VERSION,
        "quantile": q,
        "prior_continuation_reversals": cont,
        "prior_confirmed_reversals": conf,
    }


def _finite(v: float) -> bool:
    import math
    return math.isfinite(v)


def _swing_policy_hash(swing_policy) -> str:
    return _canonical_hash("STAGE4B1_SWING_POLICY_RECONSTRUCTION_BINDING_V1", _swing_policy_payload(swing_policy))


def _new_columns(result: pd.DataFrame, input_frame: pd.DataFrame) -> Tuple[str, ...]:
    existing = set(input_frame.columns)
    return tuple(c for c in result.columns if c not in existing)


def _reconstruct_adapter(surface: Stage4B1StructureSurface) -> TimelineAdapter:
    if surface.adapter_kind is TIMELINE_ADAPTER_KIND.POSITIONAL:
        return PositionalTimelineAdapter(surface.timeline_id)
    if surface.adapter_kind is TIMELINE_ADAPTER_KIND.TIME_INDEXED:
        return TimeIndexedTimelineAdapter(surface.timeline_id)
    raise TrajectoryDataError(f"unsupported adapter kind: {surface.adapter_kind}")


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_structure_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    swing_policy=None,
) -> Stage4B1StructureSurface:
    """Build one shared structure surface from CLOSED 2.1A → 2.1B → 2.1C over the full history."""
    timeline.verify(adapter=adapter, market_history=market_history)

    # 2.1A
    try:
        frame_a = CausalAdaptiveSwingDetector(confirmation_policy=swing_policy).analyze(
            market_history, high_col=high_col, low_col=low_col
        )
    except SwingDataError as exc:
        raise TrajectoryDataError(f"2.1A rejected input: {exc}") from exc
    # 2.1B
    try:
        frame_b = ConfirmedSwingSequenceEngine().analyze(frame_a)
    except SwingSequenceError as exc:
        raise TrajectoryDataError(f"2.1B rejected input: {exc}") from exc
    # 2.1C
    try:
        frame_c = CausalStructuralBreakEngine().analyze(frame_b)
    except StructuralBreakError as exc:
        raise TrajectoryDataError(f"2.1C rejected input: {exc}") from exc

    # Derived columns per stage (dynamic detection must equal the mirrored CLOSED schema)
    derived_a = _new_columns(frame_a, market_history)
    derived_b = _new_columns(frame_b, frame_a)
    derived_c = _new_columns(frame_c, frame_b)
    if derived_a != _2_1A_OUTPUT_COLUMNS:
        raise TrajectoryDataError(f"2.1A produced unexpected derived columns: {derived_a}")
    if derived_b != _2_1B_OUTPUT_COLUMNS:
        raise TrajectoryDataError(f"2.1B produced unexpected derived columns: {derived_b}")
    if derived_c != _2_1C_OUTPUT_COLUMNS:
        raise TrajectoryDataError(f"2.1C produced unexpected derived columns: {derived_c}")

    # Defensive deep copy at the Stage-4B-1 boundary
    owned_frame = frame_c.copy(deep=True)

    hash_a = _canonical_hash("STAGE4B1_STRUCTURE_2_1A_PUBLIC_RESULT_V1", owned_frame.loc[:, list(derived_a)])
    hash_b = _canonical_hash("STAGE4B1_STRUCTURE_2_1B_PUBLIC_RESULT_V1", owned_frame.loc[:, list(derived_b)])
    hash_c = _canonical_hash("STAGE4B1_STRUCTURE_2_1C_PUBLIC_RESULT_V1", owned_frame.loc[:, list(derived_c)])
    public_result_hash = _canonical_hash(
        "STAGE4B1_STRUCTURE_COMPLETE_RESULT_V1", owned_frame.loc[:, list(_ALL_DERIVED_COLUMNS)]
    )

    policy_hash = _swing_policy_hash(swing_policy)
    reconstruction_input_hash = _canonical_hash(
        "STAGE4B1_RECONSTRUCTION_INPUT_BINDING_V1",
        {
            "timeline_id": timeline.timeline_id,
            "timeline_hash": timeline.timeline_hash,
            "high_col": high_col,
            "low_col": low_col,
            "swing_policy_hash": policy_hash,
            "contract_2_1a": _2_1A_CONTRACT_VERSION,
            "contract_2_1b": _2_1B_CONTRACT_VERSION,
            "contract_2_1c": _2_1C_CONTRACT_VERSION,
        },
    )

    surface_id = _canonical_hash(
        "STAGE4B1_SURFACE_IDENTITY_V1",
        {
            "domain": _STRUCTURE_DOMAIN,
            "contract_version": TRAJECTORY_STAGE4B1_CONTRACT_VERSION,
            "timeline_id": timeline.timeline_id,
            "timeline_hash": timeline.timeline_hash,
            "adapter_kind": timeline.adapter_kind,
            "high_col": high_col,
            "low_col": low_col,
            "swing_policy_hash": policy_hash,
            "reconstruction_input_hash": reconstruction_input_hash,
            "hash_2_1a": hash_a,
            "hash_2_1b": hash_b,
            "hash_2_1c": hash_c,
            "public_result_hash": public_result_hash,
        },
    )

    surface = Stage4B1StructureSurface(
        domain=_STRUCTURE_DOMAIN,
        contract_version=TRAJECTORY_STAGE4B1_CONTRACT_VERSION,
        timeline_id=timeline.timeline_id,
        timeline_hash=timeline.timeline_hash,
        adapter_kind=timeline.adapter_kind,
        high_col=high_col,
        low_col=low_col,
        swing_policy_hash=policy_hash,
        reconstruction_input_hash=reconstruction_input_hash,
        derived_2_1a=derived_a,
        derived_2_1b=derived_b,
        derived_2_1c=derived_c,
        hash_2_1a=hash_a,
        hash_2_1b=hash_b,
        hash_2_1c=hash_c,
        public_result_hash=public_result_hash,
        surface_id=surface_id,
        frame=owned_frame,
    )
    verify_surface_integrity(surface)
    return surface


# ---------------------------------------------------------------------------
# Self-integrity
# ---------------------------------------------------------------------------

def verify_surface_integrity(surface: Stage4B1StructureSurface) -> None:
    """Recompute the surface identity from CURRENT content; reject any stale/forged field."""
    if not isinstance(surface, Stage4B1StructureSurface):
        raise TrajectoryContractError("surface must be a Stage4B1StructureSurface")
    if surface.domain != _STRUCTURE_DOMAIN:
        raise TrajectoryDataError(f"unsupported domain: {surface.domain}")
    if surface.contract_version != TRAJECTORY_STAGE4B1_CONTRACT_VERSION:
        raise TrajectoryDataError(f"contract version mismatch: {surface.contract_version}")
    if not isinstance(surface.timeline_id, str) or not surface.timeline_id:
        raise TrajectoryDataError("timeline_id must be non-empty")
    if not isinstance(surface.timeline_hash, str) or not surface.timeline_hash:
        raise TrajectoryDataError("timeline_hash must be non-empty")
    if surface.adapter_kind not in (TIMELINE_ADAPTER_KIND.POSITIONAL, TIMELINE_ADAPTER_KIND.TIME_INDEXED):
        raise TrajectoryDataError(f"invalid adapter_kind: {surface.adapter_kind}")
    if surface.derived_2_1a != _2_1A_OUTPUT_COLUMNS:
        raise TrajectoryDataError("derived_2_1a schema mismatch")
    if surface.derived_2_1b != _2_1B_OUTPUT_COLUMNS:
        raise TrajectoryDataError("derived_2_1b schema mismatch")
    if surface.derived_2_1c != _2_1C_OUTPUT_COLUMNS:
        raise TrajectoryDataError("derived_2_1c schema mismatch")
    if not isinstance(surface.frame, pd.DataFrame):
        raise TrajectoryDataError("frame must be a DataFrame")
    if surface.frame.columns.has_duplicates:
        raise TrajectoryDataError("frame has duplicate columns")
    for col in _ALL_DERIVED_COLUMNS:
        if col not in surface.frame.columns:
            raise TrajectoryDataError(f"derived column missing from frame: {col}")

    recomputed_a = _canonical_hash(
        "STAGE4B1_STRUCTURE_2_1A_PUBLIC_RESULT_V1", surface.frame.loc[:, list(surface.derived_2_1a)]
    )
    recomputed_b = _canonical_hash(
        "STAGE4B1_STRUCTURE_2_1B_PUBLIC_RESULT_V1", surface.frame.loc[:, list(surface.derived_2_1b)]
    )
    recomputed_c = _canonical_hash(
        "STAGE4B1_STRUCTURE_2_1C_PUBLIC_RESULT_V1", surface.frame.loc[:, list(surface.derived_2_1c)]
    )
    recomputed_public = _canonical_hash(
        "STAGE4B1_STRUCTURE_COMPLETE_RESULT_V1", surface.frame.loc[:, list(_ALL_DERIVED_COLUMNS)]
    )
    if recomputed_a != surface.hash_2_1a:
        raise TrajectoryDataError("self-integrity: hash_2_1a stale")
    if recomputed_b != surface.hash_2_1b:
        raise TrajectoryDataError("self-integrity: hash_2_1b stale")
    if recomputed_c != surface.hash_2_1c:
        raise TrajectoryDataError("self-integrity: hash_2_1c stale")
    if recomputed_public != surface.public_result_hash:
        raise TrajectoryDataError("self-integrity: public_result_hash stale")

    recomputed_surface_id = _canonical_hash(
        "STAGE4B1_SURFACE_IDENTITY_V1",
        {
            "domain": surface.domain,
            "contract_version": surface.contract_version,
            "timeline_id": surface.timeline_id,
            "timeline_hash": surface.timeline_hash,
            "adapter_kind": surface.adapter_kind,
            "high_col": surface.high_col,
            "low_col": surface.low_col,
            "swing_policy_hash": surface.swing_policy_hash,
            "reconstruction_input_hash": surface.reconstruction_input_hash,
            "hash_2_1a": recomputed_a,
            "hash_2_1b": recomputed_b,
            "hash_2_1c": recomputed_c,
            "public_result_hash": recomputed_public,
        },
    )
    if recomputed_surface_id != surface.surface_id:
        raise TrajectoryDataError("self-integrity: surface_id stale")


# ---------------------------------------------------------------------------
# Prefix projection
# ---------------------------------------------------------------------------

def project_structure_prefix(
    *,
    surface: Stage4B1StructureSurface,
    boundary_key: InformationKey,
) -> Stage4B1PrefixBinding:
    """Project the shared structure surface through a legal boundary.

    Verifies self-integrity FIRST, enforces legal boundary phase, validates the complete
    InformationKey via the CLOSED adapter, then returns a compact prefix binding (no rows copied).
    """
    if not isinstance(surface, Stage4B1StructureSurface):
        raise TrajectoryContractError("surface must be a Stage4B1StructureSurface")
    verify_surface_integrity(surface)
    if not isinstance(boundary_key, InformationKey):
        raise TrajectoryContractError("boundary_key must be an InformationKey")
    if boundary_key.information_phase not in _LEGAL_BOUNDARY_PHASES:
        raise TrajectoryContractError(
            f"boundary key phase not legally observable: {boundary_key.information_phase}"
        )
    adapter = _reconstruct_adapter(surface)
    try:
        adapter.validate_key(boundary_key, surface.frame.index)
    except TimelineAdapterError as exc:
        raise TrajectoryDataError(f"boundary key invalid for surface: {exc}") from exc

    position = boundary_key.bar_position
    n = len(surface.frame)
    if position < 0 or position >= n:
        raise TrajectoryDataError(f"boundary position {position} outside surface range [0, {n - 1}]")

    prefix_frame = surface.frame.loc[:, list(_ALL_DERIVED_COLUMNS)].iloc[: position + 1]
    prefix_hash = _canonical_hash("STAGE4B1_PREFIX_IDENTITY_V1", prefix_frame)

    return Stage4B1PrefixBinding(
        domain=surface.domain,
        surface_id=surface.surface_id,
        boundary_position=position,
        boundary_key=boundary_key,
        prefix_hash=prefix_hash,
        prefix_row_count=position + 1,
    )


def verify_surface_matches_reconstruction(
    supplied: Stage4B1StructureSurface,
    authoritative: Stage4B1StructureSurface,
) -> None:
    """Independently verify CURRENT integrity of both surfaces, then compare every identity field."""
    if not isinstance(supplied, Stage4B1StructureSurface):
        raise TrajectoryContractError("supplied must be a Stage4B1StructureSurface")
    if not isinstance(authoritative, Stage4B1StructureSurface):
        raise TrajectoryContractError("authoritative must be a Stage4B1StructureSurface")
    verify_surface_integrity(supplied)
    verify_surface_integrity(authoritative)
    fields = (
        "domain", "contract_version", "timeline_id", "timeline_hash", "adapter_kind",
        "high_col", "low_col", "swing_policy_hash", "reconstruction_input_hash",
        "derived_2_1a", "derived_2_1b", "derived_2_1c",
        "hash_2_1a", "hash_2_1b", "hash_2_1c", "public_result_hash", "surface_id",
    )
    for f in fields:
        if getattr(supplied, f) != getattr(authoritative, f):
            raise TrajectoryDataError(f"Stage 4B-1 surface mismatch: {f} differs")


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def trajectory_stage4b1_manifest() -> pd.DataFrame:
    rows = [
        ("CONTRACT", "VERSION", TRAJECTORY_STAGE4B1_CONTRACT_VERSION),
        ("SURFACE", "ARCHITECTURE", "SHARED_PER_EXACT_SURFACE_IDENTITY_NOT_PER_HYPOTHESIS"),
        ("SURFACE", "IDENTITY", "DETERMINISTIC_RECONSTRUCTION_DERIVATION_WITNESS_NOT_HISTORICAL_PROVENANCE"),
        ("SURFACE", "SELF_INTEGRITY", "VERIFY_RECOMPUTES_COMPONENT_AND_COMPOSED_HASHES_FROM_CURRENT_CONTENT"),
        ("SOURCE", "2_1A", "SUPPORTED_CLOSED_V1_1"),
        ("SOURCE", "2_1B", "SUPPORTED_CLOSED_V1"),
        ("SOURCE", "2_1C", "SUPPORTED_CLOSED_V1_1"),
        ("EQUIVALENCE", "PUBLIC_RESULT", "COMPLETE_DERIVED_RESULT_OF_2_1A_2_1B_2_1C_HASHED"),
        ("INFORMATION_TIME", "ORIGIN", "ORIGIN_NEVER_USED_AS_FACTUAL_AVAILABILITY_NO_FORGED_ORIGIN_INFORMATIONKEY"),
        ("PROJECTION", "HYPOTHESIS", "COMPACT_PREFIX_BINDING_NO_ROW_DUPLICATION"),
        ("IDENTITY", "PREFIX", "IMMUTABLE_PREFIX_IDENTITY_THROUGH_BOUNDARY_T"),
        ("OUT_OF_SCOPE", "STAGE4B2", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "STAGE4C", "NOT_IMPLEMENTED"),
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

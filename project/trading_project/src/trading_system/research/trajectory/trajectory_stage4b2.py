"""Module 6.2A-4 V1 Stage 4B-2: Shared Entity & Lifecycle Surfaces.

Four shared, hypothesis-independent factual surfaces over the CLOSED public engines:

- Liquidity        (CLOSED 2.2)   — consumes CLOSED Stage 4B-1 structure surface
- Order Block      (CLOSED 4.1)   — consumes CLOSED Stage 4B-1 structure surface
- FVG              (CLOSED 4.2A)  — structure-independent (OHLC only)
- Dealing Range    (CLOSED 4.2B)  — consumes CLOSED Stage 4B-1 structure surface

Design guarantees (per accepted design + design patches + PATCH blockers):

- FOUR separate public surface dataclasses with fixed domain semantics; runtime domain/schema
  validation derives the allowed schema from the surface CLASS and frozen CLOSED-contract mirrors,
  NEVER from caller-controlled metadata. Coherent cross-domain forgery rejects even after the
  attacker recomputes accessible hashes.
- ONE authoritative structural input (the CLOSED Stage4B1StructureSurface) for Liquidity / OB /
  Dealing Range; verified via verify_surface_integrity + identity binding; NO private 2.1A→2.1B→2.1C
  reconstruction inside Stage 4B-2.
- Passthrough market columns actually consumed by each CLOSED engine are verified equal to the
  authoritative sealed market_history BEFORE domain-engine execution.
- FVG is independent: bound to the sealed timeline/market directly.
- Complete CLOSED factual result bound (bar derived columns + event/range table).
- Normalized entity representation (Liquidity/OB/FVG derived from *_CREATED rows; Dealing Range uses
  the original CLOSED range table) is labeled STAGE-4B-2-DERIVED where derived.
- Same-bar lifecycle ambiguity: a derived `same_information_batch_order_unknown` flag is added to the
  normalized event representation; mechanical serialization is NOT intrabar chronology.
- PREFIX IDENTITY binds ALL factual information legally visible through T: bar factual state +
  lifecycle events + entities + normalized lifecycle events (Dealing Range: range entities +
  bar state). Factual availability (creation/confirmation/event position) controls inclusion, never
  origin.
- Self-integrity: every mutable DataFrame is recomputed/verified from CURRENT content before
  consumption. Historical generating-input provenance remains NOT_CERTIFIED / UNVERIFIABLE.

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
from trading_system.research.trajectory import trajectory_stage4b1 as s4b1
from trading_system.research.trajectory.trajectory_stage4b1 import Stage4B1StructureSurface

from trading_system.liquidity.liquidity_map import (
    CausalLiquidityMapEngine,
    LiquidityMapError,
)
from trading_system.zones.order_blocks import (
    CausalOrderBlockEngine,
    OrderBlockError,
)
from trading_system.zones.fvg import (
    CausalFVGEngine,
    FVGError,
)
from trading_system.zones.dealing_range import (
    CausalDealingRangeEngine,
    RangeError,
)

TimelineAdapter = PositionalTimelineAdapter | TimeIndexedTimelineAdapter

TRAJECTORY_STAGE4B2_CONTRACT_VERSION: Final = "CAUSAL_SHARED_ENTITY_LIFECYCLE_SURFACE_V1"

CONTRACT_LIQUIDITY: Final = "MODULE_2_2_V1_1"
CONTRACT_ORDER_BLOCK: Final = "MODULE_4_1_V1_1"
CONTRACT_FVG: Final = "MODULE_4_2A_V1_1"
CONTRACT_DEALING_RANGE: Final = "MODULE_4_2B_V1_1"

# Exact passthrough market inputs each CLOSED engine actually consumes (from its required columns).
_PASSTHROUGH_MARKET_COLUMNS: Final = {
    "LIQUIDITY": ("high", "low", "close"),
    "ORDER_BLOCK": ("open", "high", "low", "close"),
    "FVG": ("open", "high", "low", "close"),
    "DEALING_RANGE": ("close",),
}

# ---------------------------------------------------------------------------
# Local frozen schema mirrors — the EXACT audited PUBLIC factual output schemas
# of the CLOSED engines, kept locally (Stage 4B-1 precedent). These are NOT
# private-symbol imports; they are Stage-4B-2-local immutable mirrors. The actual
# CLOSED public output is discovered dynamically at construction and MUST equal
# these mirrors (else reject/stop).
# ---------------------------------------------------------------------------

_LIQ_BAR_SCHEMA: Final = (
    "liquidity_level_created", "created_level_id", "created_level_side",
    "created_level_price", "created_level_origin_position",
    "created_level_confirmation_position", "created_level_source_class",
    "nearest_prior_same_side_level_id", "nearest_same_side_distance_fraction",
    "nearest_distance_percentile", "nearest_distance_reference_history_count",
    "high_side_first_touch_count", "low_side_first_touch_count",
    "high_side_first_wick_breach_count", "low_side_first_wick_breach_count",
    "high_side_first_wick_only_count", "low_side_first_wick_only_count",
    "high_side_first_close_breach_count", "low_side_first_close_breach_count",
    "high_side_first_reclaim_count", "low_side_first_reclaim_count",
    "known_high_side_level_count", "known_low_side_level_count",
)
_LIQ_EVENT_SCHEMA: Final = (
    "event_position", "level_id", "side", "event_type",
    "source_origin_position", "source_confirmation_position", "source_class",
    "immutable_level_price", "event_price", "event_close", "overshoot_fraction",
    "nearest_prior_same_side_level_id", "nearest_same_side_distance_fraction",
    "nearest_distance_percentile", "nearest_distance_reference_history_count",
    "level_age_bars",
)

_OB_BAR_SCHEMA: Final = (
    "ob_candidate_created", "created_ob_zone_id", "created_ob_direction",
    "created_ob_origin_position", "created_ob_creation_position",
    "created_ob_full_zone_low", "created_ob_full_zone_high",
    "created_ob_body_low", "created_ob_body_high", "created_ob_source_break_event",
    "created_ob_origin_prior_use_count", "created_ob_displacement_fraction",
    "created_ob_displacement_percentile", "created_ob_displacement_history_count",
    "created_ob_search_boundary_position", "created_ob_opposite_candle_count_in_leg",
    "bullish_ob_first_touch_count", "bearish_ob_first_touch_count",
    "bullish_ob_first_far_side_wick_breach_count", "bearish_ob_first_far_side_wick_breach_count",
    "bullish_ob_first_far_side_close_breach_count", "bearish_ob_first_far_side_close_breach_count",
    "bullish_ob_first_reclaim_count", "bearish_ob_first_reclaim_count",
    "known_bullish_ob_candidate_count", "known_bearish_ob_candidate_count",
)
_OB_EVENT_SCHEMA: Final = (
    "event_position", "zone_id", "direction", "event_type",
    "origin_position", "creation_position", "search_boundary_position",
    "source_break_event", "full_zone_low", "full_zone_high", "body_low", "body_high",
    "event_high", "event_low", "event_close", "displacement_fraction",
    "displacement_percentile", "displacement_history_count",
    "origin_prior_use_count", "zone_age_bars",
)

_FVG_BAR_SCHEMA: Final = (
    "fvg_candidate_created", "created_fvg_id", "created_fvg_direction",
    "created_fvg_origin_position", "created_fvg_middle_position",
    "created_fvg_creation_position", "created_fvg_zone_low", "created_fvg_zone_high",
    "created_fvg_midpoint", "created_fvg_gap_width", "created_fvg_gap_width_fraction",
    "created_fvg_gap_width_percentile", "created_fvg_gap_width_history_count",
    "created_fvg_middle_body_fraction", "created_fvg_middle_signed_body_fraction",
    "bullish_fvg_first_touch_count", "bearish_fvg_first_touch_count",
    "bullish_fvg_first_full_range_coverage_count", "bearish_fvg_first_full_range_coverage_count",
    "bullish_fvg_first_far_side_wick_breach_count", "bearish_fvg_first_far_side_wick_breach_count",
    "bullish_fvg_first_far_side_close_breach_count", "bearish_fvg_first_far_side_close_breach_count",
    "bullish_fvg_first_close_reclaim_count", "bearish_fvg_first_close_reclaim_count",
    "known_bullish_fvg_candidate_count", "known_bearish_fvg_candidate_count",
)
_FVG_EVENT_SCHEMA: Final = (
    "event_position", "fvg_id", "direction", "event_type",
    "origin_position", "middle_position", "creation_position",
    "zone_low", "zone_high", "midpoint", "gap_width", "gap_width_fraction",
    "gap_width_percentile", "gap_width_history_count",
    "middle_body_fraction", "middle_signed_body_fraction",
    "event_high", "event_low", "event_close", "zone_range_coverage_fraction",
    "fvg_age_bars",
)

_DR_BAR_SCHEMA: Final = (
    "dealing_range_created", "created_range_id", "created_range_direction",
    "created_range_creation_position", "created_range_low", "created_range_high",
    "created_range_width", "created_range_midpoint",
    "created_range_first_endpoint_side", "created_range_first_endpoint_origin_position",
    "created_range_first_endpoint_confirmation_position", "created_range_first_endpoint_price",
    "created_range_first_endpoint_class", "created_range_second_endpoint_side",
    "created_range_second_endpoint_origin_position",
    "created_range_second_endpoint_confirmation_position", "created_range_second_endpoint_price",
    "created_range_second_endpoint_class", "rejected_range_geometry",
    "current_range_id", "current_range_direction", "current_range_creation_position",
    "current_range_low", "current_range_high", "current_range_width", "current_range_midpoint",
    "current_range_position_raw", "current_midpoint_displacement",
    "current_discount_depth", "current_premium_depth",
)
_DR_RANGE_SCHEMA: Final = (
    "range_id", "creation_position", "direction",
    "first_endpoint_side", "first_endpoint_origin_position",
    "first_endpoint_confirmation_position", "first_endpoint_price", "first_endpoint_class",
    "second_endpoint_side", "second_endpoint_origin_position",
    "second_endpoint_confirmation_position", "second_endpoint_price", "second_endpoint_class",
    "range_low", "range_high", "range_width", "midpoint",
)

# Normalized entity columns (derived from CLOSED creation-event rows; subset of the CLOSED event
# schema). Dealing Range uses the original CLOSED range table.
_ENTITY_COLUMNS_LIQUIDITY: Final = (
    "level_id", "side", "immutable_level_price",
    "source_origin_position", "source_confirmation_position", "source_class",
)
_ENTITY_COLUMNS_ORDER_BLOCK: Final = (
    "zone_id", "direction", "origin_position", "creation_position",
    "search_boundary_position", "source_break_event",
    "full_zone_low", "full_zone_high", "body_low", "body_high",
    "displacement_fraction", "displacement_percentile",
    "displacement_history_count", "origin_prior_use_count",
)
_ENTITY_COLUMNS_FVG: Final = (
    "fvg_id", "direction", "origin_position", "middle_position", "creation_position",
    "zone_low", "zone_high", "midpoint", "gap_width", "gap_width_fraction",
    "gap_width_percentile", "gap_width_history_count",
    "middle_body_fraction", "middle_signed_body_fraction",
)

_AMBIGUITY_COLUMN: Final = "same_information_batch_order_unknown"

_LEGAL_BOUNDARY_PHASES: Final = frozenset(
    {
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    }
)


# ---------------------------------------------------------------------------
# Surface types — four separate public dataclasses with FIXED domain semantics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stage4B2LiquiditySurface:
    """Liquidity entity/lifecycle surface. Domain is FIXED (class-level), not caller-controlled."""

    timeline_id: str
    timeline_hash: str
    adapter_kind: TIMELINE_ADAPTER_KIND
    structure_surface_id: str  # bound CLOSED Stage 4B-1 identity
    reconstruction_input_hash: str
    complete_result_hash: str
    normalized_entity_hash: str
    normalized_event_hash: str
    surface_id: str
    bar_frame: pd.DataFrame
    event_frame: pd.DataFrame
    normalized_entity_frame: pd.DataFrame
    normalized_event_frame: pd.DataFrame


@dataclass(frozen=True)
class Stage4B2OrderBlockSurface:
    """Order Block entity/lifecycle surface. Domain is FIXED (class-level)."""

    timeline_id: str
    timeline_hash: str
    adapter_kind: TIMELINE_ADAPTER_KIND
    structure_surface_id: str
    reconstruction_input_hash: str
    complete_result_hash: str
    normalized_entity_hash: str
    normalized_event_hash: str
    surface_id: str
    bar_frame: pd.DataFrame
    event_frame: pd.DataFrame
    normalized_entity_frame: pd.DataFrame
    normalized_event_frame: pd.DataFrame


@dataclass(frozen=True)
class Stage4B2FVGSurface:
    """FVG entity/lifecycle surface (structure-independent). Domain is FIXED (class-level)."""

    timeline_id: str
    timeline_hash: str
    adapter_kind: TIMELINE_ADAPTER_KIND
    structure_surface_id: Optional[str]  # always None for FVG
    reconstruction_input_hash: str
    complete_result_hash: str
    normalized_entity_hash: str
    normalized_event_hash: str
    surface_id: str
    bar_frame: pd.DataFrame
    event_frame: pd.DataFrame
    normalized_entity_frame: pd.DataFrame
    normalized_event_frame: pd.DataFrame


@dataclass(frozen=True)
class Stage4B2DealingRangeSurface:
    """Dealing Range entity/lifecycle surface. Domain is FIXED (class-level)."""

    timeline_id: str
    timeline_hash: str
    adapter_kind: TIMELINE_ADAPTER_KIND
    structure_surface_id: str
    reconstruction_input_hash: str
    complete_result_hash: str
    normalized_entity_hash: str
    normalized_event_hash: str
    surface_id: str
    bar_frame: pd.DataFrame
    event_frame: pd.DataFrame  # the original CLOSED range table
    normalized_entity_frame: pd.DataFrame  # == original range table
    normalized_event_frame: pd.DataFrame


@dataclass(frozen=True)
class Stage4B2PrefixBinding:
    """Compact reference to a shared domain surface + immutable prefix identity through a boundary."""

    domain: str
    surface_id: str
    boundary_position: int
    boundary_key: InformationKey
    prefix_hash: str
    prefix_row_count: int


# ---------------------------------------------------------------------------
# Frozen per-domain contract (class -> fixed domain + CLOSED schemas)
# ---------------------------------------------------------------------------

_SURFACE_CLASSES = (
    Stage4B2LiquiditySurface,
    Stage4B2OrderBlockSurface,
    Stage4B2FVGSurface,
    Stage4B2DealingRangeSurface,
)

# Map surface class -> (domain, contract_version, bar_schema, event_schema, entity_schema,
#                       entity_position_column, event_position_column)
_DOMAIN_CONTRACT = {
    Stage4B2LiquiditySurface: (
        "LIQUIDITY", CONTRACT_LIQUIDITY,
        tuple(_LIQ_BAR_SCHEMA), tuple(_LIQ_EVENT_SCHEMA), tuple(_ENTITY_COLUMNS_LIQUIDITY),
        "source_confirmation_position", "event_position",
    ),
    Stage4B2OrderBlockSurface: (
        "ORDER_BLOCK", CONTRACT_ORDER_BLOCK,
        tuple(_OB_BAR_SCHEMA), tuple(_OB_EVENT_SCHEMA), tuple(_ENTITY_COLUMNS_ORDER_BLOCK),
        "creation_position", "event_position",
    ),
    Stage4B2FVGSurface: (
        "FVG", CONTRACT_FVG,
        tuple(_FVG_BAR_SCHEMA), tuple(_FVG_EVENT_SCHEMA), tuple(_ENTITY_COLUMNS_FVG),
        "creation_position", "event_position",
    ),
    Stage4B2DealingRangeSurface: (
        "DEALING_RANGE", CONTRACT_DEALING_RANGE,
        tuple(_DR_BAR_SCHEMA), tuple(_DR_RANGE_SCHEMA), tuple(_DR_RANGE_SCHEMA),
        "creation_position", "creation_position",
    ),
}


def _contract_for(surface) -> Tuple:
    for cls in _SURFACE_CLASSES:
        if isinstance(surface, cls):
            return _DOMAIN_CONTRACT[cls]
    raise TrajectoryContractError(
        "surface must be a Stage 4B-2 domain surface (Liquidity / Order Block / FVG / Dealing Range)"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_hash(domain: str, payload) -> str:
    try:
        return canonical_sha256(domain=domain, payload=payload)
    except Exception as exc:
        raise TrajectoryDataError(f"Stage 4B-2 hash failed ({domain}): {exc}") from exc


def _new_columns(result: pd.DataFrame, input_frame: pd.DataFrame) -> Tuple[str, ...]:
    existing = set(input_frame.columns)
    return tuple(c for c in result.columns if c not in existing)


def _reconstruct_adapter(surface) -> TimelineAdapter:
    if surface.adapter_kind is TIMELINE_ADAPTER_KIND.POSITIONAL:
        return PositionalTimelineAdapter(surface.timeline_id)
    if surface.adapter_kind is TIMELINE_ADAPTER_KIND.TIME_INDEXED:
        return TimeIndexedTimelineAdapter(surface.timeline_id)
    raise TrajectoryDataError(f"unsupported adapter kind: {surface.adapter_kind}")


def _verify_structure_input(
    *,
    structure_surface: Stage4B1StructureSurface,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    domain: str,
) -> None:
    """Verify the CLOSED Stage 4B-1 structural input + passthrough market columns."""
    if not isinstance(structure_surface, Stage4B1StructureSurface):
        raise TrajectoryContractError("structure_surface must be a Stage4B1StructureSurface")
    s4b1.verify_surface_integrity(structure_surface)
    if structure_surface.timeline_id != timeline.timeline_id:
        raise TrajectoryDataError("structure surface timeline_id mismatch")
    if structure_surface.timeline_hash != timeline.timeline_hash:
        raise TrajectoryDataError("structure surface timeline_hash mismatch")
    timeline.verify(adapter=adapter, market_history=market_history)
    for col in _PASSTHROUGH_MARKET_COLUMNS[domain]:
        if col not in structure_surface.frame.columns:
            raise TrajectoryDataError(f"structure frame missing passthrough column: {col}")
        frame_col = structure_surface.frame[col].reset_index(drop=True)
        market_col = market_history[col].reset_index(drop=True)
        if not frame_col.equals(market_col):
            raise TrajectoryDataError(
                f"structure frame passthrough column {col} differs from authoritative market_history"
            )


def _with_ambiguity(event_frame: pd.DataFrame) -> pd.DataFrame:
    """Add the derived same-information-batch-unknown flag (STAGE-4B-2-derived, not CLOSED)."""
    frame = event_frame.copy(deep=True)
    if "event_position" in frame.columns:
        dup = frame["event_position"].duplicated(keep=False)
        frame[_AMBIGUITY_COLUMN] = dup
    else:
        frame[_AMBIGUITY_COLUMN] = False
    return frame


def _derive_entity_frame(
    domain: str,
    entity_columns: Tuple[str, ...],
    event_frame: pd.DataFrame,
    is_range_table: bool,
) -> pd.DataFrame:
    """Derive a normalized entity table (STAGE-4B-2-DERIVED) from *_CREATED rows, or use the
    original CLOSED range table for Dealing Range."""
    cols = list(entity_columns)
    if is_range_table:
        return event_frame[cols].copy(deep=True)
    creation_types = {"LIQUIDITY": "LEVEL_CREATED", "ORDER_BLOCK": "ZONE_CREATED", "FVG": "FVG_CREATED"}
    created = event_frame[event_frame["event_type"] == creation_types[domain]].copy(deep=True)
    return created[cols].reset_index(drop=True)


def _build_surface(
    *,
    surface_cls,
    timeline: MarketObservationTimeline,
    structure_surface: Optional[Stage4B1StructureSurface],
    input_frame: pd.DataFrame,
    bar_result: pd.DataFrame,
    event_result: pd.DataFrame,
) -> object:
    """Common assembly: defensive copies + frozen-schema validation + identity binding."""
    domain, contract_version, bar_schema, event_schema, entity_schema, _, _ = _DOMAIN_CONTRACT[surface_cls]
    is_range_table = (surface_cls is Stage4B2DealingRangeSurface)

    owned_bar = bar_result.copy(deep=True)
    owned_event = event_result.copy(deep=True)

    bar_columns = _new_columns(owned_bar, input_frame)
    # event/range tables share no passthrough columns; they equal the full result columns
    event_columns = tuple(owned_event.columns)

    # Frozen-schema enforcement: the CLOSED engine's actual output MUST equal the frozen mirror.
    if bar_columns != bar_schema:
        raise TrajectoryDataError(f"{domain}: bar derived schema mismatch {bar_columns} vs frozen")
    if event_columns != event_schema:
        raise TrajectoryDataError(f"{domain}: event/range schema mismatch {event_columns} vs frozen")

    normalized_entity = _derive_entity_frame(domain, entity_schema, owned_event, is_range_table)
    if tuple(normalized_entity.columns) != entity_schema:
        raise TrajectoryDataError(f"{domain}: normalized entity schema mismatch")
    normalized_event = _with_ambiguity(owned_event)

    reconstruction_payload = {
        "domain": domain,
        "contract_version": contract_version,
        "timeline_id": timeline.timeline_id,
        "timeline_hash": timeline.timeline_hash,
        "structure_surface_id": structure_surface.surface_id if structure_surface is not None else None,
    }
    reconstruction_input_hash = _canonical_hash("STAGE4B2_RECONSTRUCTION_INPUT_BINDING_V1", reconstruction_payload)

    complete_result_hash = _canonical_hash(
        "STAGE4B2_COMPLETE_RESULT_V1",
        {"bar": owned_bar.loc[:, list(bar_columns)], "event": owned_event.loc[:, list(event_columns)]},
    )
    normalized_entity_hash = _canonical_hash("STAGE4B2_NORMALIZED_ENTITY_V1", normalized_entity)
    normalized_event_hash = _canonical_hash("STAGE4B2_NORMALIZED_EVENT_V1", normalized_event)

    surface_id = _canonical_hash(
        "STAGE4B2_SURFACE_IDENTITY_V1",
        {
            "surface_class": surface_cls.__name__,
            "domain": domain,
            "contract_version": contract_version,
            "timeline_id": timeline.timeline_id,
            "timeline_hash": timeline.timeline_hash,
            "adapter_kind": timeline.adapter_kind,
            "structure_surface_id": structure_surface.surface_id if structure_surface is not None else None,
            "reconstruction_input_hash": reconstruction_input_hash,
            "complete_result_hash": complete_result_hash,
            "normalized_entity_hash": normalized_entity_hash,
            "normalized_event_hash": normalized_event_hash,
        },
    )

    surface = surface_cls(
        timeline_id=timeline.timeline_id,
        timeline_hash=timeline.timeline_hash,
        adapter_kind=timeline.adapter_kind,
        structure_surface_id=structure_surface.surface_id if structure_surface is not None else None,
        reconstruction_input_hash=reconstruction_input_hash,
        complete_result_hash=complete_result_hash,
        normalized_entity_hash=normalized_entity_hash,
        normalized_event_hash=normalized_event_hash,
        surface_id=surface_id,
        bar_frame=owned_bar,
        event_frame=owned_event,
        normalized_entity_frame=normalized_entity,
        normalized_event_frame=normalized_event,
    )
    verify_surface_integrity(surface)
    return surface


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_liquidity_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    structure_surface: Stage4B1StructureSurface,
) -> Stage4B2LiquiditySurface:
    _verify_structure_input(
        structure_surface=structure_surface, timeline=timeline, adapter=adapter,
        market_history=market_history, domain="LIQUIDITY",
    )
    try:
        bar, events = CausalLiquidityMapEngine().analyze(structure_surface.frame)
    except LiquidityMapError as exc:
        raise TrajectoryDataError(f"liquidity engine rejected input: {exc}") from exc
    return _build_surface(
        surface_cls=Stage4B2LiquiditySurface,
        timeline=timeline, structure_surface=structure_surface,
        input_frame=structure_surface.frame, bar_result=bar, event_result=events,
    )


def build_order_block_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    structure_surface: Stage4B1StructureSurface,
) -> Stage4B2OrderBlockSurface:
    _verify_structure_input(
        structure_surface=structure_surface, timeline=timeline, adapter=adapter,
        market_history=market_history, domain="ORDER_BLOCK",
    )
    try:
        bar, events = CausalOrderBlockEngine().analyze(structure_surface.frame)
    except OrderBlockError as exc:
        raise TrajectoryDataError(f"order-block engine rejected input: {exc}") from exc
    return _build_surface(
        surface_cls=Stage4B2OrderBlockSurface,
        timeline=timeline, structure_surface=structure_surface,
        input_frame=structure_surface.frame, bar_result=bar, event_result=events,
    )


def build_fvg_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
) -> Stage4B2FVGSurface:
    timeline.verify(adapter=adapter, market_history=market_history)
    try:
        bar, events = CausalFVGEngine().analyze(market_history)
    except FVGError as exc:
        raise TrajectoryDataError(f"fvg engine rejected input: {exc}") from exc
    return _build_surface(
        surface_cls=Stage4B2FVGSurface,
        timeline=timeline, structure_surface=None,
        input_frame=market_history, bar_result=bar, event_result=events,
    )


def build_dealing_range_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    structure_surface: Stage4B1StructureSurface,
) -> Stage4B2DealingRangeSurface:
    _verify_structure_input(
        structure_surface=structure_surface, timeline=timeline, adapter=adapter,
        market_history=market_history, domain="DEALING_RANGE",
    )
    try:
        bar, range_table = CausalDealingRangeEngine().analyze(structure_surface.frame)
    except RangeError as exc:
        raise TrajectoryDataError(f"dealing-range engine rejected input: {exc}") from exc
    return _build_surface(
        surface_cls=Stage4B2DealingRangeSurface,
        timeline=timeline, structure_surface=structure_surface,
        input_frame=structure_surface.frame, bar_result=bar, event_result=range_table,
    )


# ---------------------------------------------------------------------------
# Self-integrity — derives domain/schema from the surface CLASS, never caller metadata
# ---------------------------------------------------------------------------

def verify_surface_integrity(surface) -> None:
    domain, contract_version, bar_schema, event_schema, entity_schema, _, _ = _contract_for(surface)

    if not isinstance(surface.timeline_id, str) or not surface.timeline_id:
        raise TrajectoryDataError("timeline_id must be non-empty")
    if not isinstance(surface.timeline_hash, str) or not surface.timeline_hash:
        raise TrajectoryDataError("timeline_hash must be non-empty")
    if surface.adapter_kind not in (TIMELINE_ADAPTER_KIND.POSITIONAL, TIMELINE_ADAPTER_KIND.TIME_INDEXED):
        raise TrajectoryDataError(f"invalid adapter_kind: {surface.adapter_kind}")
    if isinstance(surface, Stage4B2FVGSurface):
        if surface.structure_surface_id is not None:
            raise TrajectoryDataError("FVG surface must have structure_surface_id=None")
    else:
        if not isinstance(surface.structure_surface_id, str):
            raise TrajectoryDataError("structure-dependent domain requires a structure_surface_id")

    for frame, label in (
        (surface.bar_frame, "bar_frame"),
        (surface.event_frame, "event_frame"),
        (surface.normalized_entity_frame, "normalized_entity_frame"),
        (surface.normalized_event_frame, "normalized_event_frame"),
    ):
        if not isinstance(frame, pd.DataFrame):
            raise TrajectoryDataError(f"{label} must be a DataFrame")
        if frame.columns.has_duplicates:
            raise TrajectoryDataError(f"{label} has duplicate columns")

    # Exact schema enforcement against the frozen CLOSED mirror for THIS surface class.
    if tuple(surface.bar_frame.columns) != bar_schema + tuple(surface.bar_frame.columns[len(bar_schema):]):
        # bar_frame = passthrough + derived; derived tail must equal bar_schema; full check below
        pass
    # derived bar columns = the tail of bar_frame equal to the frozen schema
    if tuple(surface.bar_frame.columns)[-len(bar_schema):] != bar_schema:
        raise TrajectoryDataError(f"{domain}: bar derived columns do not match frozen schema")
    if tuple(surface.event_frame.columns) != event_schema:
        raise TrajectoryDataError(f"{domain}: event/range schema mismatch")
    if tuple(surface.normalized_entity_frame.columns) != entity_schema:
        raise TrajectoryDataError(f"{domain}: normalized entity schema mismatch")
    if tuple(surface.normalized_event_frame.columns) != event_schema + (_AMBIGUITY_COLUMN,):
        raise TrajectoryDataError(f"{domain}: normalized event schema mismatch")
    if _AMBIGUITY_COLUMN not in surface.normalized_event_frame.columns:
        raise TrajectoryDataError("normalized event frame missing ambiguity column")

    recomputed_complete = _canonical_hash(
        "STAGE4B2_COMPLETE_RESULT_V1",
        {
            "bar": surface.bar_frame.iloc[:, -len(bar_schema):],
            "event": surface.event_frame,
        },
    )
    if recomputed_complete != surface.complete_result_hash:
        raise TrajectoryDataError("self-integrity: complete_result_hash stale")

    recomputed_entity = _canonical_hash("STAGE4B2_NORMALIZED_ENTITY_V1", surface.normalized_entity_frame)
    if recomputed_entity != surface.normalized_entity_hash:
        raise TrajectoryDataError("self-integrity: normalized_entity_hash stale")
    recomputed_event = _canonical_hash("STAGE4B2_NORMALIZED_EVENT_V1", surface.normalized_event_frame)
    if recomputed_event != surface.normalized_event_hash:
        raise TrajectoryDataError("self-integrity: normalized_event_hash stale")

    recomputed_surface_id = _canonical_hash(
        "STAGE4B2_SURFACE_IDENTITY_V1",
        {
            "surface_class": surface.__class__.__name__,
            "domain": domain,
            "contract_version": contract_version,
            "timeline_id": surface.timeline_id,
            "timeline_hash": surface.timeline_hash,
            "adapter_kind": surface.adapter_kind,
            "structure_surface_id": surface.structure_surface_id,
            "reconstruction_input_hash": surface.reconstruction_input_hash,
            "complete_result_hash": recomputed_complete,
            "normalized_entity_hash": recomputed_entity,
            "normalized_event_hash": recomputed_event,
        },
    )
    if recomputed_surface_id != surface.surface_id:
        raise TrajectoryDataError("self-integrity: surface_id stale")


# ---------------------------------------------------------------------------
# Prefix projection — binds ALL factual information legally visible through T
# ---------------------------------------------------------------------------

def project_domain_prefix(
    *,
    surface,
    boundary_key: InformationKey,
) -> Stage4B2PrefixBinding:
    domain, contract_version, bar_schema, event_schema, entity_schema, entity_pos_col, event_pos_col = _contract_for(surface)
    verify_surface_integrity(surface)
    if not isinstance(boundary_key, InformationKey):
        raise TrajectoryContractError("boundary_key must be an InformationKey")
    if boundary_key.information_phase not in _LEGAL_BOUNDARY_PHASES:
        raise TrajectoryContractError(
            f"boundary key phase not legally observable: {boundary_key.information_phase}"
        )
    adapter = _reconstruct_adapter(surface)
    try:
        adapter.validate_key(boundary_key, surface.bar_frame.index)
    except TimelineAdapterError as exc:
        raise TrajectoryDataError(f"boundary key invalid for surface: {exc}") from exc

    position = boundary_key.bar_position
    n = len(surface.bar_frame)
    if position < 0 or position >= n:
        raise TrajectoryDataError(f"boundary position {position} outside surface range [0, {n - 1}]")

    # A. bar factual prefix (derived columns, rows 0..T)
    bar_prefix = surface.bar_frame.iloc[:, -len(bar_schema):].iloc[: position + 1].reset_index(drop=True)
    bar_prefix_hash = _canonical_hash("STAGE4B2_PREFIX_BAR_V1", bar_prefix)

    # B. lifecycle event prefix (events with factual availability <= T)
    event_frame = surface.event_frame
    if event_pos_col in event_frame.columns:
        event_prefix = event_frame[event_frame[event_pos_col] <= position].reset_index(drop=True)
    else:
        event_prefix = event_frame.iloc[0:0].reset_index(drop=True)
    event_prefix_hash = _canonical_hash("STAGE4B2_PREFIX_EVENT_V1", event_prefix)

    # C. entity prefix (entities factually created/available <= T, by creation/confirmation position)
    entity_frame = surface.normalized_entity_frame
    if entity_pos_col in entity_frame.columns:
        entity_prefix = entity_frame[entity_frame[entity_pos_col] <= position].reset_index(drop=True)
    else:
        entity_prefix = entity_frame.iloc[0:0].reset_index(drop=True)
    entity_prefix_hash = _canonical_hash("STAGE4B2_PREFIX_ENTITY_V1", entity_prefix)

    # D. normalized lifecycle prefix (normalized event rows available <= T, ambiguity flags preserved)
    ne_frame = surface.normalized_event_frame
    if event_pos_col in ne_frame.columns:
        ne_prefix = ne_frame[ne_frame[event_pos_col] <= position].reset_index(drop=True)
    else:
        ne_prefix = ne_frame.iloc[0:0].reset_index(drop=True)
    ne_prefix_hash = _canonical_hash("STAGE4B2_PREFIX_NORMALIZED_EVENT_V1", ne_prefix)

    # The prefix_hash binds ONLY the factual content through T (stable under legal future append).
    # Timeline/domain/surface identity is carried by the binding's surface_id + boundary_key fields
    # (which a consumer must verify), NOT folded into the content hash.
    prefix_hash = _canonical_hash(
        "STAGE4B2_PREFIX_IDENTITY_V1",
        {
            "bar_prefix_hash": bar_prefix_hash,
            "event_prefix_hash": event_prefix_hash,
            "entity_prefix_hash": entity_prefix_hash,
            "normalized_event_prefix_hash": ne_prefix_hash,
        },
    )

    return Stage4B2PrefixBinding(
        domain=domain,
        surface_id=surface.surface_id,
        boundary_position=position,
        boundary_key=boundary_key,
        prefix_hash=prefix_hash,
        prefix_row_count=position + 1,
    )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def trajectory_stage4b2_manifest() -> pd.DataFrame:
    rows = [
        ("CONTRACT", "VERSION", TRAJECTORY_STAGE4B2_CONTRACT_VERSION),
        ("SURFACE", "ARCHITECTURE", "FOUR_SEPARATE_PUBLIC_SURFACE_CLASSES_FIXED_DOMAIN"),
        ("SURFACE", "IDENTITY", "DETERMINISTIC_RECONSTRUCTION_DERIVATION_WITNESS_NOT_HISTORICAL_PROVENANCE"),
        ("SURFACE", "SELF_INTEGRITY", "DOMAIN_AND_SCHEMA_DERIVED_FROM_SURFACE_CLASS_AND_FROZEN_CLOSED_MIRROR"),
        ("PREFIX", "COMPONENTS", "BAR_EVENT_ENTITY_NORMALIZED_EVENT_ALL_FACTUAL_THROUGH_T"),
        ("DOMAIN", "LIQUIDITY", "SUPPORTED_CLOSED_2_2_CONSUMES_STAGE4B1"),
        ("DOMAIN", "ORDER_BLOCK", "SUPPORTED_CLOSED_4_1_CONSUMES_STAGE4B1"),
        ("DOMAIN", "FVG", "SUPPORTED_CLOSED_4_2A_STRUCTURE_INDEPENDENT"),
        ("DOMAIN", "DEALING_RANGE", "SUPPORTED_CLOSED_4_2B_CONSUMES_STAGE4B1"),
        ("AMBIGUITY", "SAME_BATCH", "DERIVED_FLAG_NOT_INTRABAR_CHRONOLOGY"),
        ("ENTITY", "NORMALIZED", "STAGE4B2_DERIVED_FROM_CREATION_EVENTS_OR_ORIGINAL_RANGE_TABLE"),
        ("INFORMATION_TIME", "ORIGIN", "ORIGIN_NEVER_USED_AS_AVAILABILITY_NO_FORGED_INFORMATIONKEY"),
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

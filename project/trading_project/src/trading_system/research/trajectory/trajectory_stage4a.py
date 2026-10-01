"""Module 6.2A-4 V1 Stage 4A: Shared Per-Bar Market-State Trajectory.

Factual shared market-state layer on top of CLOSED Stage 1/2/3.

Supported domains (V1):
- Dynamic Volatility (CLOSED 1.1)
- Session Context (CLOSED 1.2)
- Volume Delta / Order Flow in OHLCV_PROXY mode (CLOSED 3.1)
- Absorption / Response in OHLCV_PROXY mode (CLOSED 3.2)

NOT supported in Stage 4A V1:
- ACTUAL_AGGRESSOR order flow
- ACTUAL absorption

Reason: the CLOSED MarketObservationTimeline does not seal buy_volume/sell_volume, and no
authoritative external source-availability contract exists for aggressor data. Requesting ACTUAL
mode is rejected explicitly (NOT_SUPPORTED_BY_STAGE4A_V1_SOURCE_CONTRACT); no fallback to PROXY.

Architecture:
- Domain surfaces are SHARED per exact DOMAIN SURFACE IDENTITY, computed once, hypothesis-independent.
- Hypothesis projections are compact prefix bindings (no physical row duplication).
- All identities are DETERMINISTIC RECONSTRUCTION / DERIVATION WITNESSES, not historical provenance.

INTEGRITY (PATCH): `Stage4ADomainSurface` is frozen, but its contained DataFrame is mutable. Every
function that consumes a surface's factual content calls `verify_surface_integrity` first, which
recomputes the public-result hash and surface identity from CURRENT content and rejects on any
stale/forged field. A defensive deep copy is taken at the construction boundary (in addition to the
CLOSED engines' own `df.copy(deep=True)`).

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

# CLOSED engines consumed (LIVE Layer 1 / Layer 3 public APIs)
from trading_system.environment.dynamic_volatility import DynamicVolatilityEngine
from trading_system.environment.session_context import (
    CausalSessionContextEngine,
    SessionDefinition,
)
from trading_system.orderflow.volume_delta import (
    CausalVolumeDeltaEngine,
    OrderFlowMode,
    VolumeDeltaError,
)
from trading_system.orderflow.absorption import (
    AbsorptionError,
    CausalAbsorptionEvidenceEngine,
)
from trading_system.environment.session_context import SessionContextError
from trading_system.environment.dynamic_volatility import DynamicVolatilityError

TimelineAdapter = PositionalTimelineAdapter | TimeIndexedTimelineAdapter

TRAJECTORY_STAGE4A_CONTRACT_VERSION: Final = "CAUSAL_SHARED_PER_BAR_MARKET_STATE_TRAJECTORY_V1"

VOLATILITY_CONTRACT_VERSION: Final = "MODULE_1_1_V1_1"
SESSION_CONTRACT_VERSION: Final = "MODULE_1_2_V1"
ORDER_FLOW_CONTRACT_VERSION: Final = "MODULE_3_1_V1_1"
ABSORPTION_CONTRACT_VERSION: Final = "MODULE_3_2_V1_1"

_ORDER_FLOW_PROXY_DOMAIN: Final = "ORDER_FLOW_PROXY"
_ABSORPTION_PROXY_DOMAIN: Final = "ABSORPTION_PROXY"
_VOLATILITY_DOMAIN: Final = "VOLATILITY"
_SESSION_DOMAIN: Final = "SESSION"

_SUPPORTED_DOMAINS: Final = frozenset(
    {_VOLATILITY_DOMAIN, _SESSION_DOMAIN, _ORDER_FLOW_PROXY_DOMAIN, _ABSORPTION_PROXY_DOMAIN}
)

# Exact CLOSED output-column schemas (mirrored verbatim from the CLOSED engine contracts).
_VOLATILITY_OUTPUT_COLUMNS: Final = (
    "true_range", "normalized_true_range", "true_range_percentile",
    "true_range_history_count", "normalized_tr_change",
    "expansion_percentile", "expansion_history_count",
)
_SESSION_BASE_OUTPUT_COLUMNS: Final = (
    "hour_utc_sin", "hour_utc_cos", "weekday_sin", "weekday_cos",
)
_ORDER_FLOW_PROXY_OUTPUT_COLUMNS: Final = (
    "order_flow_mode", "close_location_proxy", "volume_pressure_proxy",
    "signed_volume_pressure_raw", "pressure_proxy_percentile",
    "pressure_proxy_history_count", "pressure_magnitude",
    "pressure_magnitude_percentile", "pressure_magnitude_history_count",
)
_ABSORPTION_PROXY_OUTPUT_COLUMNS: Final = (
    "absorption_mode", "signed_return", "absolute_return",
    "return_magnitude_percentile", "return_magnitude_history_count",
    "pressure_response_alignment", "pressure_aligned_response_magnitude",
    "pressure_aligned_response_percentile", "pressure_aligned_response_history_count",
    "pressure_opposed_response_magnitude", "pressure_opposed_response_percentile",
    "pressure_opposed_response_history_count", "proxy_pressure_extremeness",
    "proxy_response_weakness", "proxy_absorption_evidence", "pressure_side",
)

_ACTUAL_NOT_SUPPORTED: Final = (
    "ACTUAL_AGGRESSOR is NOT_SUPPORTED_BY_STAGE4A_V1_SOURCE_CONTRACT: the CLOSED "
    "MarketObservationTimeline does not seal buy_volume/sell_volume and no authoritative "
    "external source-availability contract has been established; no fallback to OHLCV_PROXY "
    "is performed."
)


# ---------------------------------------------------------------------------
# Shared surface identity types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stage4ADomainSurface:
    """A shared per-bar market-state domain surface, computed once per surface identity.

    `configuration_payload` is the canonical (frozen) configuration identity, stored so the exact
    output schema (esp. SESSION) can be verified without trusting the mutable `output_columns`.

    All hashes are deterministic-reconstruction witnesses; the contained `surface` DataFrame is
    mutable, so every consumer must call `verify_surface_integrity` before reading its content.
    """

    domain: str
    contract_version: str
    timeline_id: str
    timeline_hash: str
    adapter_kind: TIMELINE_ADAPTER_KIND
    configuration_binding_hash: str
    reconstruction_input_hash: str
    upstream_surface_hash: Optional[str]  # ABSORPTION_PROXY only
    public_result_hash: str
    surface_id: str
    output_columns: Tuple[str, ...]
    configuration_payload: Tuple  # canonical frozen config identity (schema verification)
    surface: pd.DataFrame  # full shared surface, computed once (mutable!)


@dataclass(frozen=True)
class Stage4APrefixBinding:
    """Compact hypothesis projection: a reference to a shared surface + an immutable prefix
    identity through an information boundary. Contains NO physical surface rows.
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
        raise TrajectoryDataError(f"Stage 4A hash failed ({domain}): {exc}") from exc


def _surface_public_result_hash(output_frame: pd.DataFrame) -> str:
    return _canonical_hash("STAGE4A_PUBLIC_RESULT_EQUIVALENCE_V1", output_frame)


def _surface_identity_hash(payload: dict) -> str:
    return _canonical_hash("STAGE4A_DOMAIN_SURFACE_IDENTITY_V1", payload)


def _prefix_hash(output_frame_prefix: pd.DataFrame) -> str:
    return _canonical_hash("STAGE4A_PREFIX_IDENTITY_V1", output_frame_prefix)


def _config_binding_hash(domain: str, payload: dict) -> str:
    return _canonical_hash(f"STAGE4A_{domain}_CONFIG_BINDING_V1", payload)


def _reconstruction_input_hash(payload: dict) -> str:
    return _canonical_hash("STAGE4A_RECONSTRUCTION_INPUT_BINDING_V1", payload)


def _new_columns(result: pd.DataFrame, input_frame: pd.DataFrame) -> Tuple[str, ...]:
    existing = set(input_frame.columns)
    return tuple(c for c in result.columns if c not in existing)


def _session_config_payload(sessions: Tuple[SessionDefinition, ...]) -> Tuple:
    return tuple(
        (s.name, s.timezone, s.start_local.isoformat(), s.end_local.isoformat()) for s in sessions
    )


_LEGAL_BOUNDARY_PHASES: Final = frozenset(
    {
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    }
)


def _reconstruct_adapter(surface: Stage4ADomainSurface) -> TimelineAdapter:
    """Reconstruct the authoritative CLOSED adapter for the surface's timeline."""
    if surface.adapter_kind is TIMELINE_ADAPTER_KIND.POSITIONAL:
        return PositionalTimelineAdapter(surface.timeline_id)
    if surface.adapter_kind is TIMELINE_ADAPTER_KIND.TIME_INDEXED:
        return TimeIndexedTimelineAdapter(surface.timeline_id)
    raise TrajectoryDataError(f"unsupported adapter kind: {surface.adapter_kind}")


def _require_proxy_mode(mode: OrderFlowMode) -> None:
    if not isinstance(mode, OrderFlowMode):
        raise TrajectoryContractError("mode must be an OrderFlowMode")
    if mode is OrderFlowMode.ACTUAL_AGGRESSOR:
        raise TrajectoryDataError(_ACTUAL_NOT_SUPPORTED)


def _expected_output_columns(domain: str, configuration_payload: Tuple) -> Tuple[str, ...]:
    """Exact factual output schema for a domain, derived from CLOSED contract + frozen config."""
    if domain == _VOLATILITY_DOMAIN:
        return _VOLATILITY_OUTPUT_COLUMNS
    if domain == _ORDER_FLOW_PROXY_DOMAIN:
        return _ORDER_FLOW_PROXY_OUTPUT_COLUMNS
    if domain == _ABSORPTION_PROXY_DOMAIN:
        return _ABSORPTION_PROXY_OUTPUT_COLUMNS
    if domain == _SESSION_DOMAIN:
        session_keys = [name.lower() for (name, _tz, _s, _e) in configuration_payload]
        return (
            _SESSION_BASE_OUTPUT_COLUMNS
            + tuple(f"session_{key}_active" for key in session_keys)
            + ("active_session_count",)
        )
    raise TrajectoryDataError(f"unsupported domain for schema verification: {domain}")


# ---------------------------------------------------------------------------
# Self-integrity verification
# ---------------------------------------------------------------------------

def verify_surface_integrity(surface: Stage4ADomainSurface) -> None:
    """Recompute the surface identity from CURRENT contents and reject any stale/forged field.

    Verifies: type contract, supported domain, contract version, timeline fields, exact output
    schema (from CLOSED contract + frozen config payload, NOT the mutable output_columns alone),
    no duplicate columns, output columns present exactly once, and recomputed public_result_hash
    and surface_id equality. Does NOT repair/rewrite the object.
    """
    if not isinstance(surface, Stage4ADomainSurface):
        raise TrajectoryContractError("surface must be a Stage4ADomainSurface")

    # A. type / B. domain / C. contract version
    if surface.domain not in _SUPPORTED_DOMAINS:
        raise TrajectoryDataError(f"unsupported domain: {surface.domain}")
    expected_version = {
        _VOLATILITY_DOMAIN: VOLATILITY_CONTRACT_VERSION,
        _SESSION_DOMAIN: SESSION_CONTRACT_VERSION,
        _ORDER_FLOW_PROXY_DOMAIN: ORDER_FLOW_CONTRACT_VERSION,
        _ABSORPTION_PROXY_DOMAIN: ABSORPTION_CONTRACT_VERSION,
    }[surface.domain]
    if surface.contract_version != expected_version:
        raise TrajectoryDataError(
            f"contract version mismatch: {surface.contract_version} vs {expected_version}"
        )

    # D. timeline fields present and non-empty
    if not isinstance(surface.timeline_id, str) or not surface.timeline_id:
        raise TrajectoryDataError("timeline_id must be a non-empty string")
    if not isinstance(surface.timeline_hash, str) or not surface.timeline_hash:
        raise TrajectoryDataError("timeline_hash must be a non-empty string")
    if surface.adapter_kind not in (
        TIMELINE_ADAPTER_KIND.POSITIONAL,
        TIMELINE_ADAPTER_KIND.TIME_INDEXED,
    ):
        raise TrajectoryDataError(f"invalid adapter_kind: {surface.adapter_kind}")

    # E/F/G. exact output schema + presence in surface
    expected_columns = _expected_output_columns(surface.domain, surface.configuration_payload)
    if surface.output_columns != expected_columns:
        raise TrajectoryDataError(
            f"output_columns mismatch for {surface.domain}: expected {expected_columns}, "
            f"got {surface.output_columns}"
        )
    if not isinstance(surface.surface, pd.DataFrame):
        raise TrajectoryDataError("surface.surface must be a DataFrame")
    if surface.surface.columns.has_duplicates:
        raise TrajectoryDataError("surface.surface has duplicate columns")
    for col in surface.output_columns:
        if col not in surface.surface.columns:
            raise TrajectoryDataError(f"output column missing from surface: {col}")
    if any(surface.surface.columns.tolist().count(c) != 1 for c in surface.output_columns):
        raise TrajectoryDataError("output column present more than once in surface")

    # H. recompute CURRENT public result hash
    recomputed_public = _surface_public_result_hash(
        surface.surface.loc[:, list(surface.output_columns)]
    )
    if recomputed_public != surface.public_result_hash:
        raise TrajectoryDataError(
            "surface self-integrity failure: stored public_result_hash does not match current content"
        )

    # I. recompute CURRENT surface_id
    recomputed_surface_id = _surface_identity_hash(
        {
            "domain": surface.domain,
            "contract_version": surface.contract_version,
            "timeline_id": surface.timeline_id,
            "timeline_hash": surface.timeline_hash,
            "adapter_kind": surface.adapter_kind,
            "configuration_binding_hash": surface.configuration_binding_hash,
            "reconstruction_input_hash": surface.reconstruction_input_hash,
            "upstream_surface_hash": surface.upstream_surface_hash,
            "public_result_hash": recomputed_public,
        }
    )
    if recomputed_surface_id != surface.surface_id:
        raise TrajectoryDataError(
            "surface self-integrity failure: stored surface_id does not match current content"
        )


# ---------------------------------------------------------------------------
# Builders — shared surfaces (defensive deep copy at boundary)
# ---------------------------------------------------------------------------

def _assemble_surface(
    *,
    domain: str,
    contract_version: str,
    timeline: MarketObservationTimeline,
    configuration_payload: Tuple,
    config_payload_dict: dict,
    upstream_surface_hash: Optional[str],
    result: pd.DataFrame,
    input_frame: pd.DataFrame,
) -> Stage4ADomainSurface:
    """Defensive deep copy + canonical identity assembly (single shared code path)."""
    owned_result = result.copy(deep=True)  # defensive copy at the Stage-4A boundary
    output_columns = _new_columns(owned_result, input_frame)
    expected_columns = _expected_output_columns(domain, configuration_payload)
    if output_columns != expected_columns:
        raise TrajectoryDataError(
            f"{domain} engine produced unexpected output columns: {output_columns} vs {expected_columns}"
        )

    configuration_binding_hash = _config_binding_hash(domain, config_payload_dict)
    reconstruction_input_hash = _reconstruction_input_hash(
        {
            "domain": domain,
            "contract_version": contract_version,
            "timeline_id": timeline.timeline_id,
            "timeline_hash": timeline.timeline_hash,
            **config_payload_dict,
        }
    )
    output_frame = owned_result.loc[:, list(output_columns)]
    public_result_hash = _surface_public_result_hash(output_frame)
    surface_id = _surface_identity_hash(
        {
            "domain": domain,
            "contract_version": contract_version,
            "timeline_id": timeline.timeline_id,
            "timeline_hash": timeline.timeline_hash,
            "adapter_kind": timeline.adapter_kind,
            "configuration_binding_hash": configuration_binding_hash,
            "reconstruction_input_hash": reconstruction_input_hash,
            "upstream_surface_hash": upstream_surface_hash,
            "public_result_hash": public_result_hash,
        }
    )
    surface = Stage4ADomainSurface(
        domain=domain,
        contract_version=contract_version,
        timeline_id=timeline.timeline_id,
        timeline_hash=timeline.timeline_hash,
        adapter_kind=timeline.adapter_kind,
        configuration_binding_hash=configuration_binding_hash,
        reconstruction_input_hash=reconstruction_input_hash,
        upstream_surface_hash=upstream_surface_hash,
        public_result_hash=public_result_hash,
        surface_id=surface_id,
        output_columns=output_columns,
        configuration_payload=configuration_payload,
        surface=owned_result,
    )
    verify_surface_integrity(surface)
    return surface


def build_volatility_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
) -> Stage4ADomainSurface:
    timeline.verify(adapter=adapter, market_history=market_history)
    configuration_payload = (high_col, low_col, close_col)
    config_payload_dict = {"high_col": high_col, "low_col": low_col, "close_col": close_col}
    try:
        result = DynamicVolatilityEngine().analyze(
            market_history, high_col=high_col, low_col=low_col, close_col=close_col
        )
    except DynamicVolatilityError as exc:
        raise TrajectoryDataError(f"volatility engine rejected input: {exc}") from exc
    return _assemble_surface(
        domain=_VOLATILITY_DOMAIN,
        contract_version=VOLATILITY_CONTRACT_VERSION,
        timeline=timeline,
        configuration_payload=configuration_payload,
        config_payload_dict=config_payload_dict,
        upstream_surface_hash=None,
        result=result,
        input_frame=market_history,
    )


def build_session_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    sessions: Tuple[SessionDefinition, ...] = (),
) -> Stage4ADomainSurface:
    timeline.verify(adapter=adapter, market_history=market_history)
    if timeline.adapter_kind is not TIMELINE_ADAPTER_KIND.TIME_INDEXED:
        raise TrajectoryDataError(
            "session surface requires a time-indexed (timezone-aware) timeline"
        )
    sessions = tuple(sessions)
    configuration_payload = _session_config_payload(sessions)
    config_payload_dict = {"sessions": [dict(zip(("name", "timezone", "start_local", "end_local"), s)) for s in configuration_payload]}
    try:
        result = CausalSessionContextEngine(sessions).analyze(market_history)
    except SessionContextError as exc:
        raise TrajectoryDataError(f"session engine rejected input: {exc}") from exc
    return _assemble_surface(
        domain=_SESSION_DOMAIN,
        contract_version=SESSION_CONTRACT_VERSION,
        timeline=timeline,
        configuration_payload=configuration_payload,
        config_payload_dict=config_payload_dict,
        upstream_surface_hash=None,
        result=result,
        input_frame=market_history,
    )


def build_order_flow_proxy_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    mode: OrderFlowMode = OrderFlowMode.OHLCV_PROXY,
) -> Stage4ADomainSurface:
    _require_proxy_mode(mode)
    timeline.verify(adapter=adapter, market_history=market_history)
    configuration_payload = (mode.value,)
    config_payload_dict = {"mode": mode.value}
    try:
        result = CausalVolumeDeltaEngine(mode=mode).analyze(market_history)
    except VolumeDeltaError as exc:
        raise TrajectoryDataError(f"volume-delta engine rejected input: {exc}") from exc
    return _assemble_surface(
        domain=_ORDER_FLOW_PROXY_DOMAIN,
        contract_version=ORDER_FLOW_CONTRACT_VERSION,
        timeline=timeline,
        configuration_payload=configuration_payload,
        config_payload_dict=config_payload_dict,
        upstream_surface_hash=None,
        result=result,
        input_frame=market_history,
    )


def build_absorption_proxy_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    order_flow_surface: Stage4ADomainSurface,
    mode: OrderFlowMode = OrderFlowMode.OHLCV_PROXY,
) -> Stage4ADomainSurface:
    _require_proxy_mode(mode)
    if not isinstance(order_flow_surface, Stage4ADomainSurface):
        raise TrajectoryContractError("order_flow_surface must be a Stage4ADomainSurface")
    # 1. verify upstream self-integrity BEFORE any content consumption
    verify_surface_integrity(order_flow_surface)
    # 2. domain == ORDER_FLOW_PROXY
    if order_flow_surface.domain != _ORDER_FLOW_PROXY_DOMAIN:
        raise TrajectoryDataError(
            "absorption requires an upstream ORDER_FLOW_PROXY domain surface"
        )
    # 3. timeline identity match
    if (
        order_flow_surface.timeline_id != timeline.timeline_id
        or order_flow_surface.timeline_hash != timeline.timeline_hash
    ):
        raise TrajectoryDataError("upstream order-flow surface timeline mismatch")
    timeline.verify(adapter=adapter, market_history=market_history)

    configuration_payload = (mode.value,)
    config_payload_dict = {"mode": mode.value, "upstream_surface_id": order_flow_surface.surface_id}
    # 4. consume the VERIFIED upstream DataFrame (defensive copy inside the engine)
    try:
        result = CausalAbsorptionEvidenceEngine(mode=mode).analyze(order_flow_surface.surface)
    except AbsorptionError as exc:
        raise TrajectoryDataError(f"absorption engine rejected input: {exc}") from exc
    # 5. bind absorption upstream_surface_hash to the VERIFIED upstream surface_id
    return _assemble_surface(
        domain=_ABSORPTION_PROXY_DOMAIN,
        contract_version=ABSORPTION_CONTRACT_VERSION,
        timeline=timeline,
        configuration_payload=configuration_payload,
        config_payload_dict=config_payload_dict,
        upstream_surface_hash=order_flow_surface.surface_id,
        result=result,
        input_frame=order_flow_surface.surface,
    )


# ---------------------------------------------------------------------------
# Hypothesis projection (compact prefix binding)
# ---------------------------------------------------------------------------

def project_surface_prefix(
    *,
    surface: Stage4ADomainSurface,
    boundary_key: InformationKey,
) -> Stage4APrefixBinding:
    """Project a shared surface through an information boundary.

    Verifies surface self-integrity BEFORE reading surface.surface, then returns a compact prefix
    binding (no physical rows copied).
    """
    if not isinstance(surface, Stage4ADomainSurface):
        raise TrajectoryContractError("surface must be a Stage4ADomainSurface")
    verify_surface_integrity(surface)
    if not isinstance(boundary_key, InformationKey):
        raise TrajectoryContractError("boundary_key must be an InformationKey")

    # Legal boundary phase: completed-bar Stage 4A facts may only be exposed at a
    # COMPLETED_ROW_AVAILABLE or RESEARCH_SNAPSHOT_AVAILABLE boundary (mirroring CLOSED
    # bind_interval). BAR_PRE_CLOSE would expose completed-bar state before completion.
    if boundary_key.information_phase not in _LEGAL_BOUNDARY_PHASES:
        raise TrajectoryContractError(
            f"boundary key phase not legally observable: {boundary_key.information_phase}"
        )

    # Validate the COMPLETE InformationKey against the surface's authoritative index using the
    # CLOSED adapter semantics (timeline_id, bar_position range, and event_time_utc correctness).
    adapter = _reconstruct_adapter(surface)
    try:
        adapter.validate_key(boundary_key, surface.surface.index)
    except TimelineAdapterError as exc:
        raise TrajectoryDataError(f"boundary key invalid for surface: {exc}") from exc

    position = boundary_key.bar_position
    n = len(surface.surface)
    if position < 0 or position >= n:
        raise TrajectoryDataError(
            f"boundary position {position} outside surface range [0, {n - 1}]"
        )

    output_frame = surface.surface.loc[:, list(surface.output_columns)]
    prefix_frame = output_frame.iloc[: position + 1]
    prefix_hash = _prefix_hash(prefix_frame)

    return Stage4APrefixBinding(
        domain=surface.domain,
        surface_id=surface.surface_id,
        boundary_position=position,
        boundary_key=boundary_key,
        prefix_hash=prefix_hash,
        prefix_row_count=position + 1,
    )


def verify_surface_matches_reconstruction(
    supplied: Stage4ADomainSurface,
    authoritative: Stage4ADomainSurface,
) -> None:
    """Independently verify CURRENT integrity of both surfaces, then compare every identity field.

    Does not compare only the two stored IDs/hashes.
    """
    if not isinstance(supplied, Stage4ADomainSurface):
        raise TrajectoryContractError("supplied must be a Stage4ADomainSurface")
    if not isinstance(authoritative, Stage4ADomainSurface):
        raise TrajectoryContractError("authoritative must be a Stage4ADomainSurface")
    verify_surface_integrity(supplied)
    verify_surface_integrity(authoritative)

    fields = (
        "domain",
        "contract_version",
        "timeline_id",
        "timeline_hash",
        "configuration_binding_hash",
        "reconstruction_input_hash",
        "upstream_surface_hash",
        "public_result_hash",
        "surface_id",
        "output_columns",
    )
    for f in fields:
        if getattr(supplied, f) != getattr(authoritative, f):
            raise TrajectoryDataError(
                f"Stage 4A surface mismatch: {f} differs between supplied and reconstruction"
            )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def trajectory_stage4a_manifest() -> pd.DataFrame:
    rows = [
        ("CONTRACT", "VERSION", TRAJECTORY_STAGE4A_CONTRACT_VERSION),
        ("SURFACE", "ARCHITECTURE", "SHARED_PER_EXACT_DOMAIN_SURFACE_IDENTITY_NOT_PER_TIMELINE"),
        ("SURFACE", "IDENTITY", "DETERMINISTIC_RECONSTRUCTION_DERIVATION_WITNESS_NOT_HISTORICAL_PROVENANCE"),
        ("SURFACE", "SELF_INTEGRITY", "VERIFY_RECOMPUTES_PUBLIC_RESULT_HASH_AND_SURFACE_ID_FROM_CURRENT_CONTENT"),
        ("DOMAIN", "VOLATILITY", "SUPPORTED_CLOSED_1_1"),
        ("DOMAIN", "SESSION", "SUPPORTED_CLOSED_1_2"),
        ("DOMAIN", "ORDER_FLOW_PROXY", "SUPPORTED_CLOSED_3_1_PROXY_ONLY"),
        ("DOMAIN", "ABSORPTION_PROXY", "SUPPORTED_CLOSED_3_2_PROXY_ONLY"),
        ("DOMAIN", "ACTUAL_AGGRESSOR", "NOT_SUPPORTED_BY_STAGE4A_V1_SOURCE_CONTRACT_NO_FALLBACK"),
        ("DOMAIN", "ACTUAL_ABSORPTION", "NOT_SUPPORTED_BY_STAGE4A_V1_SOURCE_CONTRACT_NO_FALLBACK"),
        ("EQUIVALENCE", "PUBLIC_RESULT", "COMPLETE_CLOSED_FACTUAL_OUTPUT_HASHED_PER_DOMAIN"),
        ("PROJECTION", "HYPOTHESIS", "COMPACT_PREFIX_BINDING_NO_ROW_DUPLICATION"),
        ("IDENTITY", "PREFIX", "IMMUTABLE_PREFIX_IDENTITY_THROUGH_BOUNDARY_T"),
        ("INFORMATION_TIME", "DOMAINS", "COMPLETED_BAR_OR_TIMESTAMP_ONLY_NO_FUTURE_NO_CENTERED_ROLLING"),
        ("SOURCE_FIDELITY", "PROXY", "OHLCV_PROXY_IS_PROXY_NEVER_ACTUAL"),
        ("OUT_OF_SCOPE", "STAGE4B", "NOT_IMPLEMENTED"),
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

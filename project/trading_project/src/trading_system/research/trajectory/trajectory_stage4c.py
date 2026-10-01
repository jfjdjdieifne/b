"""Module 6.2A-4 V1 Stage 4C-1: shared causal HTF raw observation surfaces.

Scope (V1 / 4C-1) — RAW FUTURE TRUTH ONLY
-----------------------------------------
For one declared higher-timeframe (HTF) scale, this module binds the factual
*completed* HTF bucket observations produced by the CLOSED 5.1 causal
aggregator, optional cadence-grid coverage metadata, and a strict causal
as-of projection onto the lower-timeframe (LTF) decision timeline.

It deliberately contains NO higher-timeframe structure, NO structural
transitions, NO multi-scale confluence (those are deferred Stage 4C-2 and
require a legitimate confirmation-policy contract that does not exist in
Raw Future Truth), NO HTF volume, and NO HTF liquidity/OB/FVG/dealing-range
entities. There is no quantile, no swing policy, no threshold, and no default
scale anywhere in this module.

Projectability semantics (read carefully — do not over-claim)
--------------------------------------------------------------
``first_observed_asof_position`` / ``first_observed_asof_time`` are fields of
the CLOSED 5.1 bucket table. They name the FIRST LTF row *inside the sealed
timeline* whose timestamp is at/after the bucket close; they are the smallest
coordinate at which the bucket result is **projectable as-of** under the 5.1
contract on the sealed data.

They are NOT feed-arrival provenance and NOT historical market availability:
a missing LTF row at the theoretical close only means the sealed record has no
observation there; it does not prove when a feed actually delivered the
bucket, nor that the information was unavailable in the market. Historical
generating-input provenance remains NOT_CERTIFIED / UNVERIFIABLE. All identities
here are deterministic reconstruction / derivation witnesses only.

At the exact boundary (an observed LTF row whose timestamp equals the bucket
close, interval (start, end]), the completed bucket is projectable on that same
LTF completed-row information batch under ``COMPLETED_ROW_AVAILABLE``;
``BAR_PRE_CLOSE`` is rejected. The LTF close and the HTF close are one
information batch: ``close_batch_order_unknown`` is set and no intra-batch
chronology is asserted.

All Stage 4C-1 frames are DERIVED-ONLY: no raw market columns are copied
(passthrough), so the schemas are enforced by exact whole-frame column
equality. Market binding is carried by the sealed timeline identity and the
reconstruction-input hash only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Optional, Tuple

import numpy as np
import pandas as pd

from trading_system.multitimeframe.causal_htf import (
    CausalHTFAggregator,
    TimeAggregationSpec,
    HTFConfigError,
    HTFDataError,
)
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import (
    InformationKey,
    InformationPhase,
    TimeIndexedTimelineAdapter,
    TimelineAdapterError,
)
from trading_system.research.trajectory.trajectory_contract import (
    MarketObservationTimeline,
    TIMELINE_ADAPTER_KIND,
    TrajectoryContractError,
    TrajectoryDataError,
)

TRAJECTORY_STAGE4C_CONTRACT_VERSION: Final = "CAUSAL_HTF_RAW_TRAJECTORY_SURFACE_V1"
_HTF_ENGINE_CONTRACT: Final = "MODULE_5_1_V1_1"
_SCALE_DOMAIN: Final = "HTF_SCALE_RAW"

# ---------------------------------------------------------------------------
# Coverage status vocabulary — claims are limited to sealed observations
# relative to a DECLARED timestamp grid; never feed/market completeness.
# ---------------------------------------------------------------------------
GRID_OBSERVATIONS_COMPLETE: Final = "GRID_OBSERVATIONS_COMPLETE"
GRID_OBSERVATIONS_MISSING: Final = "GRID_OBSERVATIONS_MISSING"
OFF_GRID_OBSERVATIONS_PRESENT: Final = "OFF_GRID_OBSERVATIONS_PRESENT"
GRID_OBSERVATIONS_DEFECT_BOTH: Final = "GRID_OBSERVATIONS_DEFECT_BOTH"
GRID_COMPLETENESS_UNKNOWN: Final = "GRID_COMPLETENESS_UNKNOWN"
COVERAGE_UNAVAILABLE: Final = "UNAVAILABLE"

_BUCKET_GRID_STATUSES: Final = frozenset(
    {
        GRID_OBSERVATIONS_COMPLETE,
        GRID_OBSERVATIONS_MISSING,
        OFF_GRID_OBSERVATIONS_PRESENT,
        GRID_OBSERVATIONS_DEFECT_BOTH,
        GRID_COMPLETENESS_UNKNOWN,
    }
)
_ASOF_GRID_STATUSES: Final = _BUCKET_GRID_STATUSES | {COVERAGE_UNAVAILABLE}

_SCALE_NAME_RE: Final = re.compile(r"[A-Za-z][A-Za-z0-9_]*")

# 5.1 public bucket-table columns this module consumes, in exact order, with
# the optional trailing volume column excluded from the Stage 4C-1 schema.
_HTF51_BUCKET_BASE_COLUMNS: Final = (
    "bucket_start_utc",
    "bucket_end_utc",
    "theoretical_available_at",
    "first_observed_asof_position",
    "first_observed_asof_time",
    "first_source_timestamp",
    "last_source_timestamp",
    "source_bar_count",
    "open",
    "high",
    "low",
    "close",
)

# Stage 4C-1 local, immutable bucket-frame schema (derived-only table).
_BUCKET_FRAME_COLUMNS: Final = (
    "scale_name",
    "bucket_start_utc",
    "bucket_end_utc",
    "theoretical_available_at",
    "first_observed_asof_position",
    "first_observed_asof_time",
    "first_source_timestamp",
    "last_source_timestamp",
    "source_bar_count",
    "open",
    "high",
    "low",
    "close",
    "expected_grid_bar_count",
    "missing_grid_observation_count",
    "off_grid_observation_count",
    "coverage_status",
)

# Per-scale as-of projection column template, in exact order (prefixed with
# "<scale>__" at construction).
_ASOF_TEMPLATE: Final = (
    "completed_bucket_end_utc",
    "completed_bucket_open",
    "completed_bucket_high",
    "completed_bucket_low",
    "completed_bucket_close",
    "observed_source_bar_count",
    "expected_grid_bar_count",
    "missing_grid_observation_count",
    "off_grid_observation_count",
    "coverage_status",
    "projectable_asof_position",
    "projectable_asof_time_utc",
    "close_batch_order_unknown",
)

_LEGAL_BOUNDARY_PHASES: Final = frozenset(
    {
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    }
)

# The deferred 4C-2 scope (structure / transitions / confluence / confirmation
# policy) is forbidden in this module; the enforceable AST guard lives in
# tests/test_trajectory_stage4c.py and the research manifest below declares it
# NOT_STARTED / NOT_CONFIGURED.


# ---------------------------------------------------------------------------
# Configuration contracts (explicit, no defaults)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HtfScaleSpec:
    """One declared HTF scale. Names follow the CLOSED 5.2 safe-name rule."""

    name: str
    duration: pd.Timedelta

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _SCALE_NAME_RE.fullmatch(self.name) is None:
            raise TrajectoryContractError(
                "scale name must match [A-Za-z][A-Za-z0-9_]* and be nonempty"
            )
        if not isinstance(self.duration, pd.Timedelta) or pd.isna(self.duration):
            raise TrajectoryContractError("scale duration must be a Timedelta")
        if self.duration <= pd.Timedelta(0):
            raise TrajectoryContractError("scale duration must be positive")


@dataclass(frozen=True)
class CadenceGridContract:
    """A pure timestamp-grid contract (epoch + period). It asserts nothing
    about market calendars, sessions, or 24x7 operation; those are out of scope.
    """

    grid_epoch_utc: pd.Timestamp
    period: pd.Timedelta

    def __post_init__(self) -> None:
        if not isinstance(self.grid_epoch_utc, pd.Timestamp) or pd.isna(self.grid_epoch_utc):
            raise TrajectoryContractError("grid_epoch_utc must be a valid Timestamp")
        if self.grid_epoch_utc.tz is None:
            raise TrajectoryContractError("grid_epoch_utc must be timezone aware")
        if not isinstance(self.period, pd.Timedelta) or pd.isna(self.period):
            raise TrajectoryContractError("cadence period must be a Timedelta")
        if self.period <= pd.Timedelta(0):
            raise TrajectoryContractError("cadence period must be positive")
        object.__setattr__(self, "grid_epoch_utc", self.grid_epoch_utc.tz_convert("UTC"))

    def payload(self) -> dict:
        return {
            "grid_epoch_utc_ns": int(self.grid_epoch_utc.value),
            "period_ns": int(self.period.value),
        }


# ---------------------------------------------------------------------------
# Surface + prefix binding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage4CHtfScaleSurface:
    """One shared, hypothesis-independent raw HTF observation surface.

    Domain is FIXED at the class level (``HTF_SCALE_RAW``); it is never a
    caller-supplied field. The contained DataFrames are mutable, so every
    consumer must call :func:`verify_surface_integrity` before reading them.
    Frames are derived-only (no market passthrough columns).
    """

    domain: str
    contract_version: str
    timeline_id: str
    timeline_hash: str
    adapter_kind: TIMELINE_ADAPTER_KIND
    scale_name: str
    scale_duration_ns: int
    cadence_contract_hash: Optional[str]
    reconstruction_input_hash: str
    bucket_observations_hash: str
    asof_projection_hash: str
    surface_id: str
    asof_bar_frame: pd.DataFrame
    bucket_frame: pd.DataFrame


@dataclass(frozen=True)
class Stage4C1PrefixBinding:
    """Compact reference to a shared scale surface + factual prefix identity
    through a legal information boundary. Contains NO physical surface rows.
    """

    domain: str
    surface_id: str
    boundary_position: int
    boundary_key: InformationKey
    prefix_hash: str
    prefix_row_count: int
    prefix_bucket_count: int


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def _canonical_hash(domain: str, payload) -> str:
    try:
        return canonical_sha256(domain=domain, payload=payload)
    except Exception as exc:  # pragma: no cover - defensive normalization
        raise TrajectoryDataError(f"Stage 4C-1 hash failed ({domain}): {exc}") from exc


def _cadence_hash(cadence: Optional[CadenceGridContract]) -> Optional[str]:
    if cadence is None:
        return None
    return _canonical_hash("STAGE4C1_CADENCE_GRID_CONTRACT_V1", cadence.payload())


def _asof_columns(scale_name: str) -> Tuple[str, ...]:
    return tuple(f"{scale_name}__{template}" for template in _ASOF_TEMPLATE)


# ---------------------------------------------------------------------------
# Cadence-grid coverage (set comparison, never counts alone)
# ---------------------------------------------------------------------------


def _grid_points(cadence: CadenceGridContract, start_ns: int, end_ns: int, period_ns: int):
    """Expected grid timestamps strictly after start and at/before end."""
    epoch_ns = int(cadence.grid_epoch_utc.value)
    # smallest k with epoch + k*period > start
    k0 = (start_ns - epoch_ns) // period_ns + 1
    k1 = (end_ns - epoch_ns) // period_ns  # largest k with epoch + k*period <= end
    if k1 < k0:
        return np.empty(0, dtype=np.int64)
    count = int(k1 - k0 + 1)
    return epoch_ns + (np.arange(count, dtype=np.int64) + int(k0)) * period_ns


def _coverage_for_buckets(
    *,
    bucket_frame: pd.DataFrame,
    observed_index_ns: np.ndarray,
    cadence: Optional[CadenceGridContract],
    duration_ns: int,
) -> pd.DataFrame:
    """Return expected/missing/off-grid counts and coverage status per bucket."""
    n = len(bucket_frame)
    if cadence is None:
        return pd.DataFrame(
            {
                "expected_grid_bar_count": pd.array([pd.NA] * n, dtype="Int64"),
                "missing_grid_observation_count": pd.array([pd.NA] * n, dtype="Int64"),
                "off_grid_observation_count": pd.array([pd.NA] * n, dtype="Int64"),
                "coverage_status": pd.array(
                    [GRID_COMPLETENESS_UNKNOWN] * n, dtype="string"
                ),
            },
            index=bucket_frame.index,
        )

    period_ns = int(cadence.period.value)
    if duration_ns % period_ns != 0:
        raise TrajectoryContractError(
            "scale duration must be an integer multiple of the cadence period"
        )
    expected_per_bucket = duration_ns // period_ns

    expected_counts = np.zeros(n, dtype=np.int64)
    missing_counts = np.zeros(n, dtype=np.int64)
    offgrid_counts = np.zeros(n, dtype=np.int64)
    statuses = []

    obs = np.asarray(observed_index_ns, dtype=np.int64)
    for i, (start, end) in enumerate(
        zip(bucket_frame["bucket_start_utc"].array.asi8, bucket_frame["bucket_end_utc"].array.asi8)
    ):
        # Grid alignment is structural: every bucket boundary must lie on the grid.
        if (int(end) - int(cadence.grid_epoch_utc.value)) % period_ns != 0:
            raise TrajectoryContractError(
                "HTF bucket boundaries are not aligned to the declared cadence grid"
            )
        expected_set = _grid_points(cadence, int(start), int(end), period_ns)
        if len(expected_set) != expected_per_bucket:  # pragma: no cover - arithmetic guard
            raise TrajectoryContractError("cadence grid arithmetic inconsistent with duration")
        # (start, end] membership, exactly the CLOSED 5.1 CLOSE_TIME interval.
        in_window = obs[(obs > int(start)) & (obs <= int(end))]
        observed_set = np.unique(in_window)
        # Cross-check against CLOSED 5.1's own observed membership.
        if len(observed_set) != int(bucket_frame["source_bar_count"].iloc[i]):
            raise TrajectoryDataError(
                "cadence window membership disagrees with CLOSED 5.1 source_bar_count"
            )
        missing = np.setdiff1d(expected_set, observed_set, assume_unique=False)
        offgrid = np.setdiff1d(observed_set, expected_set, assume_unique=False)
        expected_counts[i] = expected_per_bucket
        missing_counts[i] = len(missing)
        offgrid_counts[i] = len(offgrid)
        if missing_counts[i] == 0 and offgrid_counts[i] == 0:
            statuses.append(GRID_OBSERVATIONS_COMPLETE)
        elif missing_counts[i] > 0 and offgrid_counts[i] == 0:
            statuses.append(GRID_OBSERVATIONS_MISSING)
        elif missing_counts[i] == 0 and offgrid_counts[i] > 0:
            statuses.append(OFF_GRID_OBSERVATIONS_PRESENT)
        else:
            statuses.append(GRID_OBSERVATIONS_DEFECT_BOTH)

    return pd.DataFrame(
        {
            "expected_grid_bar_count": pd.array(expected_counts, dtype="Int64"),
            "missing_grid_observation_count": pd.array(missing_counts, dtype="Int64"),
            "off_grid_observation_count": pd.array(offgrid_counts, dtype="Int64"),
            "coverage_status": pd.array(statuses, dtype="string"),
        },
        index=bucket_frame.index,
    )


# ---------------------------------------------------------------------------
# As-of projection (derived-only)
# ---------------------------------------------------------------------------


def _empty_asof_frame(index: pd.DatetimeIndex, scale_name: str) -> pd.DataFrame:
    cols = _asof_columns(scale_name)
    n = len(index)
    data = {
        cols[0]: pd.array([pd.NaT] * n, dtype="datetime64[ns, UTC]"),
        cols[1]: np.full(n, np.nan),
        cols[2]: np.full(n, np.nan),
        cols[3]: np.full(n, np.nan),
        cols[4]: np.full(n, np.nan),
        cols[5]: pd.array(np.zeros(n, dtype=np.int64), dtype="Int64"),
        cols[6]: pd.array([pd.NA] * n, dtype="Int64"),
        cols[7]: pd.array([pd.NA] * n, dtype="Int64"),
        cols[8]: pd.array([pd.NA] * n, dtype="Int64"),
        cols[9]: pd.array([COVERAGE_UNAVAILABLE] * n, dtype="string"),
        cols[10]: pd.array([pd.NA] * n, dtype="Int64"),
        cols[11]: pd.array([pd.NaT] * n, dtype="datetime64[ns, UTC]"),
        cols[12]: np.zeros(n, dtype=bool),
    }
    return pd.DataFrame(data, columns=list(cols), index=index)


def _project_asof(bucket_frame: pd.DataFrame, index: pd.DatetimeIndex, scale_name: str) -> pd.DataFrame:
    """Project completed-bucket facts onto the LTF decision index.

    Mirrors CLOSED 5.1's ``searchsorted(ends, t, side='right') - 1`` rule. On
    observed decision rows this is identical to first-observed-as-of gating:
    the first observed LTF row at/after a bucket close is precisely where that
    bucket first becomes projectable.
    """
    out = _empty_asof_frame(index, scale_name)
    if len(bucket_frame) == 0:
        return out

    cols = _asof_columns(scale_name)
    (
        c_end,
        c_open,
        c_high,
        c_low,
        c_close,
        c_count,
        c_expected,
        c_missing,
        c_offgrid,
        c_status,
        c_proj_pos,
        c_proj_time,
        c_batch,
    ) = cols

    ends = bucket_frame["bucket_end_utc"].array.asi8
    decision_ns = index.tz_convert("UTC").asi8
    j = np.searchsorted(ends, decision_ns, side="right") - 1

    proj_pos = bucket_frame["first_observed_asof_position"].to_numpy(dtype="int64")
    proj_time_ns = bucket_frame["first_observed_asof_time"].array.asi8

    for row_i in range(len(index)):
        b = int(j[row_i])
        # Observed-as-of gating: a bucket is projectable only at/after the FIRST
        # OBSERVED LTF row that reaches its close (never at the theoretical close
        # when a feed gap delays observation). Walk back while not yet observed.
        while b >= 0 and int(proj_pos[b]) > row_i:
            b -= 1
        if b < 0:
            continue
        out.iat[row_i, 0] = bucket_frame["bucket_end_utc"].iat[b]
        out.iat[row_i, 1] = float(bucket_frame["open"].iat[b])
        out.iat[row_i, 2] = float(bucket_frame["high"].iat[b])
        out.iat[row_i, 3] = float(bucket_frame["low"].iat[b])
        out.iat[row_i, 4] = float(bucket_frame["close"].iat[b])
        out.iat[row_i, 5] = int(bucket_frame["source_bar_count"].iat[b])
        out.iat[row_i, 6] = bucket_frame["expected_grid_bar_count"].iat[b]
        out.iat[row_i, 7] = bucket_frame["missing_grid_observation_count"].iat[b]
        out.iat[row_i, 8] = bucket_frame["off_grid_observation_count"].iat[b]
        out.iat[row_i, 9] = bucket_frame["coverage_status"].iat[b]
        out.iat[row_i, 10] = int(proj_pos[b])
        out.iat[row_i, 11] = bucket_frame["first_observed_asof_time"].iat[b]
        out.iat[row_i, 12] = bool(int(proj_time_ns[b]) == int(decision_ns[row_i]))

    # Enforce dtypes after cell-wise assignment.
    out[c_end] = pd.array(out[c_end].array, dtype="datetime64[ns, UTC]")
    out[c_proj_time] = pd.array(out[c_proj_time].array, dtype="datetime64[ns, UTC]")
    for integer_col in (c_count, c_proj_pos):
        out[integer_col] = pd.array(out[integer_col].to_numpy(), dtype="Int64")
    for nullable_integer_col in (c_expected, c_missing, c_offgrid):
        out[nullable_integer_col] = pd.array(out[nullable_integer_col].to_numpy(), dtype="Int64")
    out[c_status] = pd.array(out[c_status].astype("string").to_numpy(), dtype="string")
    out[c_batch] = out[c_batch].astype(bool).to_numpy()
    return out


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_htf_scale_surface(
    *,
    timeline: MarketObservationTimeline,
    adapter: TimeIndexedTimelineAdapter,
    market_history: pd.DataFrame,
    scale_spec: HtfScaleSpec,
    cadence: Optional[CadenceGridContract] = None,
) -> Stage4CHtfScaleSurface:
    """Build one shared raw HTF observation surface for one declared scale."""
    # --- static configuration contract ---
    if not isinstance(scale_spec, HtfScaleSpec):
        raise TrajectoryContractError("scale_spec must be an HtfScaleSpec")
    if cadence is not None and not isinstance(cadence, CadenceGridContract):
        raise TrajectoryContractError("cadence must be a CadenceGridContract or None")
    if not isinstance(adapter, TimeIndexedTimelineAdapter):
        raise TrajectoryContractError(
            "Stage 4C-1 requires a time-indexed (timezone-aware) timeline; POSITIONAL is rejected"
        )
    if timeline.adapter_kind is not TIMELINE_ADAPTER_KIND.TIME_INDEXED:
        raise TrajectoryContractError("sealed timeline is not TIME_INDEXED")
    if adapter.timeline_id != timeline.timeline_id:
        raise TrajectoryContractError("adapter timeline_id does not match sealed timeline")

    timeline.verify(adapter=adapter, market_history=market_history)

    cadence_hash = _cadence_hash(cadence)
    duration_ns = int(scale_spec.duration.value)
    if cadence is not None and duration_ns % int(cadence.period.value) != 0:
        raise TrajectoryContractError(
            "scale duration must be an integer multiple of the cadence period"
        )

    # --- CLOSED 5.1 aggregation (never reimplemented) ---
    try:
        aggregator = CausalHTFAggregator(spec=TimeAggregationSpec(scale_spec.duration))
        asof_raw, bucket_raw = aggregator.analyze(market_history)
    except HTFConfigError as exc:
        raise TrajectoryContractError(f"CLOSED 5.1 rejected the scale configuration: {exc}") from exc
    except HTFDataError as exc:
        raise TrajectoryDataError(f"CLOSED 5.1 rejected the market data: {exc}") from exc

    # --- dynamic mirror of the CLOSED 5.1 public bucket schema ---
    expected_51 = list(_HTF51_BUCKET_BASE_COLUMNS)
    if "volume" in market_history.columns:
        expected_51 = expected_51 + ["volume"]
    if list(bucket_raw.columns) != expected_51:
        raise TrajectoryDataError(
            f"CLOSED 5.1 bucket schema drift: {list(bucket_raw.columns)} vs frozen mirror {expected_51}"
        )
    for reserved in (
        "last_completed_htf_end_utc",
        "last_completed_htf_open",
        "last_completed_htf_high",
        "last_completed_htf_low",
        "last_completed_htf_close",
        "last_completed_htf_source_bar_count",
    ):
        if reserved not in asof_raw.columns:
            raise TrajectoryDataError(f"CLOSED 5.1 as-of schema drift: missing {reserved}")

    # --- derived-only bucket observation table (HTF volume intentionally excluded) ---
    bucket = bucket_raw.loc[:, list(_HTF51_BUCKET_BASE_COLUMNS)].copy(deep=True)
    bucket.insert(0, "scale_name", scale_spec.name)
    coverage = _coverage_for_buckets(
        bucket_frame=bucket,
        observed_index_ns=market_history.index.tz_convert("UTC").asi8,
        cadence=cadence,
        duration_ns=duration_ns,
    )
    bucket["expected_grid_bar_count"] = coverage["expected_grid_bar_count"].to_numpy()
    bucket["missing_grid_observation_count"] = coverage["missing_grid_observation_count"].to_numpy()
    bucket["off_grid_observation_count"] = coverage["off_grid_observation_count"].to_numpy()
    bucket["coverage_status"] = coverage["coverage_status"].to_numpy()
    if tuple(bucket.columns) != _BUCKET_FRAME_COLUMNS:
        raise TrajectoryDataError("bucket frame schema assembly error")
    bucket = bucket.reset_index(drop=True)

    # --- derived-only as-of projection ---
    asof_frame = _project_asof(bucket, market_history.index, scale_spec.name)
    if tuple(asof_frame.columns) != _asof_columns(scale_spec.name):
        raise TrajectoryDataError("as-of frame schema assembly error")

    # --- identity ---
    reconstruction_payload = {
        "domain": _SCALE_DOMAIN,
        "contract_version": TRAJECTORY_STAGE4C_CONTRACT_VERSION,
        "htf_engine_contract": _HTF_ENGINE_CONTRACT,
        "timeline_id": timeline.timeline_id,
        "timeline_hash": timeline.timeline_hash,
        "adapter_kind": timeline.adapter_kind,
        "scale_name": scale_spec.name,
        "scale_duration_ns": duration_ns,
        "cadence_contract_hash": cadence_hash,
    }
    reconstruction_input_hash = _canonical_hash(
        "STAGE4C1_RECONSTRUCTION_INPUT_V1", reconstruction_payload
    )
    bucket_observations_hash = _canonical_hash("STAGE4C1_BUCKET_OBSERVATIONS_V1", bucket)
    asof_projection_hash = _canonical_hash("STAGE4C1_ASOF_PROJECTION_V1", asof_frame)
    surface_id = _canonical_hash(
        "STAGE4C1_SCALE_SURFACE_IDENTITY_V1",
        {
            "surface_class": "Stage4CHtfScaleSurface",
            "reconstruction_input_hash": reconstruction_input_hash,
            "bucket_observations_hash": bucket_observations_hash,
            "asof_projection_hash": asof_projection_hash,
        },
    )

    surface = Stage4CHtfScaleSurface(
        domain=_SCALE_DOMAIN,
        contract_version=TRAJECTORY_STAGE4C_CONTRACT_VERSION,
        timeline_id=timeline.timeline_id,
        timeline_hash=timeline.timeline_hash,
        adapter_kind=timeline.adapter_kind,
        scale_name=scale_spec.name,
        scale_duration_ns=duration_ns,
        cadence_contract_hash=cadence_hash,
        reconstruction_input_hash=reconstruction_input_hash,
        bucket_observations_hash=bucket_observations_hash,
        asof_projection_hash=asof_projection_hash,
        surface_id=surface_id,
        asof_bar_frame=asof_frame,
        bucket_frame=bucket,
    )
    verify_surface_integrity(surface)
    return surface


# ---------------------------------------------------------------------------
# Self-integrity
# ---------------------------------------------------------------------------


def _reconstruct_adapter(surface: Stage4CHtfScaleSurface) -> TimeIndexedTimelineAdapter:
    if surface.adapter_kind is not TIMELINE_ADAPTER_KIND.TIME_INDEXED:
        raise TrajectoryDataError("Stage 4C-1 surfaces are TIME_INDEXED only")
    return TimeIndexedTimelineAdapter(surface.timeline_id)


def verify_surface_integrity(surface: Stage4CHtfScaleSurface) -> None:
    """Recompute the whole identity from CURRENT mutable contents or reject.

    Performs: type/domain/version contract, exact whole-frame schema equality
    for both derived-only frames, dtype/value legality, coverage semantics,
    projectability semantics, exact-batch semantics, a full recomputation of
    the as-of projection from the bucket table, and recomputation of every
    identity hash.
    """
    if not isinstance(surface, Stage4CHtfScaleSurface):
        raise TrajectoryContractError("surface must be a Stage4CHtfScaleSurface")
    if surface.domain != _SCALE_DOMAIN:
        raise TrajectoryDataError("domain is fixed to HTF_SCALE_RAW and must not be reframed")
    if surface.contract_version != TRAJECTORY_STAGE4C_CONTRACT_VERSION:
        raise TrajectoryContractError("contract version mismatch")
    if surface.adapter_kind is not TIMELINE_ADAPTER_KIND.TIME_INDEXED:
        raise TrajectoryDataError("Stage 4C-1 surfaces are TIME_INDEXED only")
    if not isinstance(surface.scale_name, str) or _SCALE_NAME_RE.fullmatch(surface.scale_name) is None:
        raise TrajectoryDataError("invalid scale name")
    if not isinstance(surface.scale_duration_ns, int) or surface.scale_duration_ns <= 0:
        raise TrajectoryDataError("invalid scale duration")

    bucket = surface.bucket_frame
    asof = surface.asof_bar_frame
    if not isinstance(bucket, pd.DataFrame) or not isinstance(asof, pd.DataFrame):
        raise TrajectoryDataError("surface frames must be DataFrames")

    # Exact WHOLE-FRAME schema equality (derived-only; closes passthrough/middle
    # injection classes entirely).
    if tuple(bucket.columns) != _BUCKET_FRAME_COLUMNS:
        raise TrajectoryDataError("bucket frame schema drift or column injection")
    expected_asof = _asof_columns(surface.scale_name)
    if tuple(asof.columns) != expected_asof:
        raise TrajectoryDataError("as-of frame schema drift, scale substitution, or injection")

    if not isinstance(asof.index, pd.DatetimeIndex) or asof.index.tz is None:
        raise TrajectoryDataError("as-of frame requires a timezone-aware DatetimeIndex")
    if asof.index.has_duplicates or not asof.index.is_monotonic_increasing:
        raise TrajectoryDataError("as-of decision index must be unique and monotonic")

    cols = expected_asof
    (
        c_end,
        c_open,
        c_high,
        c_low,
        c_close,
        c_count,
        c_expected,
        c_missing,
        c_offgrid,
        c_status,
        c_proj_pos,
        c_proj_time,
        c_batch,
    ) = cols

    # --- bucket-frame semantic legality ---
    if len(bucket):
        if bucket["scale_name"].ne(surface.scale_name).any():
            raise TrajectoryDataError("bucket scale_name is not uniform")
        ends = bucket["bucket_end_utc"]
        if ends.isna().any() or not ends.is_monotonic_increasing or ends.duplicated().any():
            raise TrajectoryDataError("bucket ends must be present, unique and monotonic")
        if (bucket["bucket_end_utc"] <= bucket["bucket_start_utc"]).any():
            raise TrajectoryDataError("bucket start/end interval illegal")
        theo = bucket["theoretical_available_at"]
        if not theo.equals(bucket["bucket_end_utc"]):
            raise TrajectoryDataError("theoretical availability must equal bucket end")
        proj_t = bucket["first_observed_asof_time"]
        if proj_t.isna().any():
            raise TrajectoryDataError("emitted buckets must have an observed as-of time")
        if (proj_t < bucket["bucket_end_utc"]).any():
            raise TrajectoryDataError(
                "projectable as-of time cannot precede the theoretical bucket close"
            )
        positions = bucket["first_observed_asof_position"]
        if positions.isna().any() or (positions < 0).any():
            raise TrajectoryDataError("observed as-of positions must be present and nonnegative")
        if not positions.is_monotonic_increasing:
            raise TrajectoryDataError("observed as-of positions must be monotonic")
        src = bucket["source_bar_count"]
        if src.isna().any() or (src < 1).any():
            raise TrajectoryDataError("emitted buckets must contain at least one observation")
        hi = bucket["high"].to_numpy(float)
        lo = bucket["low"].to_numpy(float)
        op = bucket["open"].to_numpy(float)
        cl = bucket["close"].to_numpy(float)
        if not (np.isfinite(hi) & np.isfinite(lo) & np.isfinite(op) & np.isfinite(cl)).all():
            raise TrajectoryDataError("bucket OHLC must be finite")
        if (hi < lo).any() or ((op < lo) | (op > hi) | (cl < lo) | (cl > hi)).any():
            raise TrajectoryDataError("bucket OHLC geometry violated")
        statuses = set(bucket["coverage_status"].astype(str).unique())
        if not statuses <= _BUCKET_GRID_STATUSES:
            raise TrajectoryDataError(f"unknown bucket coverage status: {statuses}")
        if surface.cadence_contract_hash is None:
            if statuses != {GRID_COMPLETENESS_UNKNOWN}:
                raise TrajectoryDataError("without a cadence contract coverage must be UNKNOWN")
            for bucket_col in (
                "expected_grid_bar_count",
                "missing_grid_observation_count",
                "off_grid_observation_count",
            ):
                if not bucket[bucket_col].isna().all():
                    raise TrajectoryDataError("coverage counts must be NA without a cadence contract")
        else:
            expected = bucket["expected_grid_bar_count"]
            missing = bucket["missing_grid_observation_count"]
            offgrid = bucket["off_grid_observation_count"]
            if expected.isna().any() or missing.isna().any() or offgrid.isna().any():
                raise TrajectoryDataError("cadence coverage counts must be present")
            if (missing < 0).any() or (offgrid < 0).any() or (expected < 1).any():
                raise TrajectoryDataError("negative cadence counts")
            calc_status = np.select(
                [
                    (missing == 0) & (offgrid == 0),
                    (missing > 0) & (offgrid == 0),
                    (missing == 0) & (offgrid > 0),
                ],
                [
                    GRID_OBSERVATIONS_COMPLETE,
                    GRID_OBSERVATIONS_MISSING,
                    OFF_GRID_OBSERVATIONS_PRESENT,
                ],
                default=GRID_OBSERVATIONS_DEFECT_BOTH,
            )
            if not (pd.Series(calc_status, index=bucket.index).astype("string")
                    == bucket["coverage_status"]).all():
                raise TrajectoryDataError("coverage status inconsistent with grid counts")
            if (missing + src != expected + offgrid).any():
                raise TrajectoryDataError(
                    "grid identity violated: expected + off-grid = observed + missing"
                )

    # --- as-of frame semantic legality ---
    n = len(asof)
    decision_ns = asof.index.tz_convert("UTC").asi8
    projected = ~asof[c_end].isna()
    if projected.any():
        sub = asof.loc[projected]
        if sub[c_status].astype(str).isin([COVERAGE_UNAVAILABLE]).any():
            raise TrajectoryDataError("projected rows must not be UNAVAILABLE")
        if sub[c_proj_time].isna().any() or sub[c_proj_pos].isna().any():
            raise TrajectoryDataError("projected rows require projectability coordinates")
        if (sub[c_proj_time].array.asi8 > np.iinfo(np.int64).max).any():  # pragma: no cover
            raise TrajectoryDataError("timestamp overflow")
        if (sub[c_proj_time].array.asi8 < sub[c_end].array.asi8).any():
            raise TrajectoryDataError("projectable time precedes the projected bucket end")
        expected_batch = (sub[c_proj_time].array.asi8 == sub.index.tz_convert("UTC").asi8)
        if not np.array_equal(sub[c_batch].astype(bool).to_numpy(), expected_batch):
            raise TrajectoryDataError("close_batch_order_unknown must mark exact visibility rows")
        for price_col in (c_open, c_high, c_low, c_close):
            finite = np.isfinite(sub[price_col].to_numpy(float))
            if not finite.all():
                raise TrajectoryDataError("projected bucket prices must be finite")
        if (sub[c_high].to_numpy(float) < sub[c_low].to_numpy(float)).any():
            raise TrajectoryDataError("projected bucket high < low")
        if (sub[c_count].to_numpy() < 1).any():
            raise TrajectoryDataError("projected buckets must have at least one observation")
    unprojected = ~projected
    if unprojected.any():
        sub = asof.loc[unprojected]
        if not (sub[c_status].astype(str) == COVERAGE_UNAVAILABLE).all():
            raise TrajectoryDataError("unprojected rows must be UNAVAILABLE")
        if not sub[c_batch].astype(bool).eq(False).all():
            raise TrajectoryDataError("unprojected rows cannot flag a closing batch")
        if not sub[c_count].eq(0).all():
            raise TrajectoryDataError("unprojected rows have zero observed buckets")
    if not set(asof[c_status].astype(str).unique()) <= _ASOF_GRID_STATUSES:
        raise TrajectoryDataError("illegal as-of coverage status")

    # --- exact recomputation of the projection from the bucket table ---
    recomputed = _project_asof(bucket.reset_index(drop=True), asof.index, surface.scale_name)
    if not recomputed.equals(asof):
        raise TrajectoryDataError(
            "as-of projection is not reproducible from the bucket table (forged/tampered frame)"
        )

    # --- identity recomputation from CURRENT contents ---
    if surface.cadence_contract_hash is not None:
        if not isinstance(surface.cadence_contract_hash, str) or not surface.cadence_contract_hash:
            raise TrajectoryDataError("invalid cadence contract hash")
    reconstruction_payload = {
        "domain": _SCALE_DOMAIN,
        "contract_version": TRAJECTORY_STAGE4C_CONTRACT_VERSION,
        "htf_engine_contract": _HTF_ENGINE_CONTRACT,
        "timeline_id": surface.timeline_id,
        "timeline_hash": surface.timeline_hash,
        "adapter_kind": surface.adapter_kind,
        "scale_name": surface.scale_name,
        "scale_duration_ns": surface.scale_duration_ns,
        "cadence_contract_hash": surface.cadence_contract_hash,
    }
    if _canonical_hash("STAGE4C1_RECONSTRUCTION_INPUT_V1", reconstruction_payload) != \
            surface.reconstruction_input_hash:
        raise TrajectoryDataError("reconstruction input identity mismatch")
    if _canonical_hash("STAGE4C1_BUCKET_OBSERVATIONS_V1", bucket) != \
            surface.bucket_observations_hash:
        raise TrajectoryDataError("bucket observations identity mismatch (content tampered)")
    if _canonical_hash("STAGE4C1_ASOF_PROJECTION_V1", asof) != surface.asof_projection_hash:
        raise TrajectoryDataError("as-of projection identity mismatch (content tampered)")
    expected_surface_id = _canonical_hash(
        "STAGE4C1_SCALE_SURFACE_IDENTITY_V1",
        {
            "surface_class": "Stage4CHtfScaleSurface",
            "reconstruction_input_hash": surface.reconstruction_input_hash,
            "bucket_observations_hash": surface.bucket_observations_hash,
            "asof_projection_hash": surface.asof_projection_hash,
        },
    )
    if expected_surface_id != surface.surface_id:
        raise TrajectoryDataError("surface identity mismatch (coherent rehash cannot reframe scope)")


# ---------------------------------------------------------------------------
# Prefix projection through a legal boundary
# ---------------------------------------------------------------------------


def project_htf_scale_prefix(
    *,
    surface: Stage4CHtfScaleSurface,
    boundary_key: InformationKey,
) -> Stage4C1PrefixBinding:
    verify_surface_integrity(surface)
    if not isinstance(boundary_key, InformationKey):
        raise TrajectoryContractError("boundary_key must be an InformationKey")
    if boundary_key.information_phase not in _LEGAL_BOUNDARY_PHASES:
        raise TrajectoryContractError(
            f"boundary key phase not legally observable: {boundary_key.information_phase}"
        )
    adapter = _reconstruct_adapter(surface)
    try:
        adapter.validate_key(boundary_key, surface.asof_bar_frame.index)
    except TimelineAdapterError as exc:
        raise TrajectoryDataError(f"boundary key invalid for surface: {exc}") from exc

    position = boundary_key.bar_position
    n = len(surface.asof_bar_frame)
    if position < 0 or position >= n:
        raise TrajectoryDataError(f"boundary position {position} outside surface range [0, {n - 1}]")

    asof_prefix = surface.asof_bar_frame.iloc[: position + 1].reset_index(drop=True)
    asof_prefix_hash = _canonical_hash("STAGE4C1_PREFIX_ASOF_V1", asof_prefix)

    bucket_prefix = (
        surface.bucket_frame[surface.bucket_frame["first_observed_asof_position"] <= position]
        .reset_index(drop=True)
    )
    bucket_prefix_hash = _canonical_hash("STAGE4C1_PREFIX_BUCKET_V1", bucket_prefix)

    config_payload = {
        "scale_name": surface.scale_name,
        "scale_duration_ns": surface.scale_duration_ns,
        "cadence_contract_hash": surface.cadence_contract_hash,
    }
    config_hash = _canonical_hash("STAGE4C1_PREFIX_CONFIG_IDENTITY_V1", config_payload)

    prefix_hash = _canonical_hash(
        "STAGE4C1_PREFIX_IDENTITY_V1",
        {
            "asof_prefix_hash": asof_prefix_hash,
            "bucket_prefix_hash": bucket_prefix_hash,
            "config_hash": config_hash,
        },
    )

    return Stage4C1PrefixBinding(
        domain=surface.domain,
        surface_id=surface.surface_id,
        boundary_position=position,
        boundary_key=boundary_key,
        prefix_hash=prefix_hash,
        prefix_row_count=position + 1,
        prefix_bucket_count=len(bucket_prefix),
    )


# ---------------------------------------------------------------------------
# Research manifest (scope declarations only)
# ---------------------------------------------------------------------------


def trajectory_stage4c_manifest() -> pd.DataFrame:
    rows = [
        ("SURFACE", "DOMAIN", "FIXED_FROM_SURFACE_CLASS_NOT_CALLER_FIELD"),
        ("SURFACE", "DERIVED_ONLY", "NO_MARKET_PASSTHROUGH_EXACT_WHOLE_FRAME_SCHEMA"),
        ("ENGINE", "HTF_AGGREGATION", "CONSUMES_CLOSED_5_1_NO_REIMPLEMENTATION"),
        ("PROJECTION", "ASOF", "RIGHT_BOUNDARY_SEARCHSORTED_OVER_SEALED_OBSERVATIONS"),
        ("PROJECTABILITY", "FIRST_OBSERVED_ASOF",
         "SEALED_TIMELINE_PROJECTION_NOT_FEED_ARRIVAL_PROVENANCE_NOT_MARKET_AVAILABILITY"),
        ("INFORMATION_TIME", "EXACT_BOUNDARY",
         "PROJECTABLE_AT_CLOSE_ONLY_IN_COMPLETED_ROW_AVAILABLE_SAME_TIMELINE"),
        ("AMBIGUITY", "SAME_BATCH", "CLOSE_BATCH_ORDER_UNKNOWN_NO_INTRABATCH_CHRONOLOGY"),
        ("COVERAGE", "GRID_CONTRACT", "OPTIONAL_TIMESTAMP_SET_COMPARISON_ONLY"),
        ("COVERAGE", "CLAIM_SCOPE", "OBSERVATIONS_VS_DECLARED_GRID_WITHIN_SEALED_DATA_ONLY"),
        ("COVERAGE", "NO_CLAIM", "NO_FEED_COMPLETENESS_NO_MARKET_COMPLETENESS_NO_CALENDAR"),
        ("OUT_OF_SCOPE", "HTF_STRUCTURE_STATUS", "NOT_CONFIGURED_IN_4C_1"),
        ("OUT_OF_SCOPE", "HTF_TRANSITIONS", "NOT_STARTED_STAGE_4C_2"),
        ("OUT_OF_SCOPE", "MTF_CONFLUENCE_SURFACE", "NOT_STARTED_STAGE_4C_2"),
        ("OUT_OF_SCOPE", "HTF_VOLUME", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "HTF_LIQUIDITY", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "HTF_ORDER_BLOCK", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "HTF_FVG", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "HTF_DEALING_RANGE", "NOT_IMPLEMENTED"),
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
        [
            {"record_type": a, "name": b, "value": c, "serialization_order": i}
            for i, (a, b, c) in enumerate(rows)
        ]
    )

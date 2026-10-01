"""Module 6.2A-4 V1 Stage 2: causal price, structure & hypothesis-lifecycle trajectory.

STRICT SCOPE (BUILD ONLY):
- PRICE: shared raw OHLC[V] + hypothesis-relative exact facts:
  reference price, direction, per-bar favorable/adverse excursion,
  running max favorable/adverse, extreme price/position/key,
  new-running-extreme flags, close displacement, bar offset,
  SAME_INFORMATION_BATCH_ORDER_UNKNOWN when both extremes in same OHLC bar.
- STRUCTURE: consume CLOSED 2.1A/2.1B/2.1C only, no reimplementation.
  Preserve origin != confirmation, visibility only at confirmation/breach.
- LIFECYCLE: consume CLOSED 6.1B/6.2A ledger only, literal terminal states
  CONTRADICTED, SUPERSEDED, OBSERVED_DIRECTION_ESTABLISHED.
  No second state machine, no price-inferred terminal.

OUT OF SCOPE (must not appear):
- true_range / volatility trajectory, liquidity, OB, FVG, dealing range,
  volume delta / absorption, session, HTF/MTF, censor-series,
  descriptors, estimands, model/scorer/probability/weights, geometry,
  execution/PnL, WIN/LOSS/SUCCESS.

This module lives in research; research MAY import LIVE (Layers 0-5, decision).
LIVE MUST NOT import research.

All observations are bound to shared MarketObservationTimeline (no per-hypothesis
market copy) and to TrajectoryInterval (decision, end_inclusive].
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
    ObservationKind,
    TrajectoryContractError,
    TrajectoryDataError,
    TrajectoryInterval,
    TIMELINE_SOURCE_CAPABILITY,
    make_observation_envelope,
)

TimelineAdapter = PositionalTimelineAdapter | TimeIndexedTimelineAdapter

TRAJECTORY_STAGE2_CONTRACT_VERSION: Final = "CAUSAL_PRICE_STRUCTURE_LIFECYCLE_TRAJECTORY_V1"
PRICE_SOURCE_CONTRACT: Final = "CAUSAL_PRICE_TRAJECTORY_V1"
STRUCTURE_SOURCE_CONTRACTS: Final = {
    "2.1A": "MODULE_2_1A_V1_1",
    "2.1B": "MODULE_2_1B_V1",
    "2.1C": "MODULE_2_1C_V1_1",
}
LIFECYCLE_SOURCE_CONTRACT: Final = "HYPOTHESIS_LIFECYCLE_V1_2"

_CLOSED_TERMINAL: Final = frozenset({"CONTRADICTED", "SUPERSEDED", "OBSERVED_DIRECTION_ESTABLISHED"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_anchor(anchor: DecisionAnchor) -> None:
    if not isinstance(anchor, DecisionAnchor):
        raise TrajectoryContractError("DecisionAnchor required")
    anchor.verify()
    if anchor.direction not in {"UP", "DOWN"}:
        raise TrajectoryDataError("invalid hypothesis direction")
    if not np.isfinite(anchor.reference_price) or anchor.reference_price <= 0:
        raise TrajectoryDataError("reference price must be positive finite")


def _validate_interval_and_timeline(
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
    if timeline.timeline_id != anchor.timeline_id != interval.timeline_id:
        raise TrajectoryDataError("timeline/anchor/interval mismatch")
    if timeline.timeline_hash != anchor.timeline_hash != interval.timeline_hash:
        raise TrajectoryDataError("timeline seal mismatch across anchor/interval")
    if anchor.anchor_hash != interval.anchor_hash:
        raise TrajectoryDataError("anchor/interval hash mismatch")
    # creation bar excluded: interval starts at decision, observed bars are (decision, end]
    if interval.start_exclusive_bar_position != anchor.decision_information_key.bar_position:
        raise TrajectoryDataError("interval must start strictly after decision bar (stage1 contract)")
    if interval.observed_bar_count <= 0:
        raise TrajectoryDataError("interval must have at least one post-decision bar")


def _key_for_position(
    adapter: TimelineAdapter,
    index: pd.Index,
    position: int,
    phase: InformationPhase = InformationPhase.COMPLETED_ROW_AVAILABLE,
    sequence: int = 0,
) -> InformationKey:
    return adapter.key_for_position(index, position, phase, sequence)


def _per_bar_excursion(high: float, low: float, ref: float, direction: str) -> Tuple[float, float, float, float]:
    """Return (fav_this, adv_this, fav_price, adv_price) per CLOSED 6.2A-1 orientation."""
    if not np.isfinite(high) or not np.isfinite(low) or not np.isfinite(ref) or ref <= 0:
        raise TrajectoryDataError("non-finite price in excursion calculation")
    if direction == "UP":
        fav = max(0.0, high / ref - 1.0)
        adv = max(0.0, 1.0 - low / ref)
        fav_price = high
        adv_price = low
    elif direction == "DOWN":
        fav = max(0.0, 1.0 - low / ref)
        adv = max(0.0, high / ref - 1.0)
        fav_price = low
        adv_price = high
    else:
        raise TrajectoryDataError("invalid direction")
    # Clamp tiny negatives to 0
    fav = 0.0 if fav < 0 else fav
    adv = 0.0 if adv < 0 else adv
    return float(fav), float(adv), float(fav_price), float(adv_price)


# ---------------------------------------------------------------------------
# PRICE
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PriceTrajectoryPoint:
    bar_position: int
    bar_offset_from_decision: int
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float]
    reference_price: float
    direction: str
    close_displacement: float
    current_favorable_excursion: float
    current_adverse_excursion: float
    running_favorable_excursion: float
    running_adverse_excursion: float
    favorable_extreme_price: Optional[float]
    favorable_extreme_position: Optional[int]
    adverse_extreme_price: Optional[float]
    adverse_extreme_position: Optional[int]
    is_new_favorable_extreme: bool
    is_new_adverse_extreme: bool
    same_bar_order_ambiguous: bool
    observation_information_key: InformationKey
    factual_available_at_key: InformationKey
    envelope_id_bar: str
    envelope_id_fav: Optional[str]
    envelope_id_adv: Optional[str]


@dataclass(frozen=True)
class PriceTrajectoryResult:
    price_bars: pd.DataFrame
    points: Tuple[PriceTrajectoryPoint, ...]
    observation_envelopes: Tuple[ObservationEnvelope, ...]
    running_favorable_final: float
    running_adverse_final: float
    same_bar_ambiguous_count: int


def build_price_trajectory(
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    interval: TrajectoryInterval,
) -> PriceTrajectoryResult:
    _validate_anchor(anchor)
    _validate_interval_and_timeline(timeline, anchor, adapter, market_history, interval)

    decision_pos = anchor.decision_information_key.bar_position
    ref = float(anchor.reference_price)
    direction = anchor.direction
    index = market_history.index
    start_pos = decision_pos + 1
    end_pos = interval.end_inclusive_bar_position

    if start_pos > end_pos:
        raise TrajectoryDataError("no post-decision bars in interval (creation bar excluded)")

    # Prepare
    envelopes: list[ObservationEnvelope] = []
    points: list[PriceTrajectoryPoint] = []
    rows: list[dict] = []

    running_fav = 0.0
    running_adv = 0.0
    fav_extreme_price: Optional[float] = None
    fav_extreme_pos: Optional[int] = None
    fav_extreme_key: Optional[InformationKey] = None
    adv_extreme_price: Optional[float] = None
    adv_extreme_pos: Optional[int] = None
    adv_extreme_key: Optional[InformationKey] = None

    ambiguous_count = 0

    for pos in range(start_pos, end_pos + 1):
        # market row
        try:
            row = market_history.iloc[pos]
        except IndexError as exc:
            raise TrajectoryDataError(f"market history missing position {pos}") from exc

        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        vol = float(row["volume"]) if "volume" in market_history.columns and pd.notna(row["volume"]) else None

        if not all(np.isfinite(v) for v in (o, h, l, c)):
            raise TrajectoryDataError(f"non-finite OHLC at position {pos}")
        if h < l:
            raise TrajectoryDataError(f"high < low at position {pos}")

        fav_this, adv_this, fav_price_this, adv_price_this = _per_bar_excursion(h, l, ref, direction)
        close_disp = (c - ref) / ref if ref != 0 else float("nan")
        same_bar_ambiguous = bool(fav_this > 0 and adv_this > 0)
        if same_bar_ambiguous:
            ambiguous_count += 1

        is_new_fav = False
        is_new_adv = False

        # Strict > preserves first occurrence on ties
        if fav_this > running_fav:
            is_new_fav = True
            running_fav = fav_this
            fav_extreme_price = fav_price_this
            fav_extreme_pos = pos
            fav_extreme_key = _key_for_position(adapter, index, pos)

        if adv_this > running_adv:
            is_new_adv = True
            running_adv = adv_this
            adv_extreme_price = adv_price_this
            adv_extreme_pos = pos
            adv_extreme_key = _key_for_position(adapter, index, pos)

        obs_key = _key_for_position(adapter, index, pos)
        avail_key = obs_key  # for OHLC, available at same completed row

        # BAR envelope - STATE_OBSERVATION
        envelope_bar = make_observation_envelope(
            interval=interval,
            observation_information_key=obs_key,
            factual_available_at_information_key=avail_key,
            observation_kind=ObservationKind.STATE_OBSERVATION,
            source_contract=PRICE_SOURCE_CONTRACT,
            source_module="trading_system.research.trajectory.trajectory_stage2",
            source_module_version=TRAJECTORY_STAGE2_CONTRACT_VERSION,
            observation_domain="PRICE",
            observation_type="BAR",
            same_information_batch_order_unknown=same_bar_ambiguous,
        )
        envelopes.append(envelope_bar)

        envelope_fav_id = None
        envelope_adv_id = None

        if is_new_fav:
            envelope_fav = make_observation_envelope(
                interval=interval,
                observation_information_key=obs_key,
                factual_available_at_information_key=avail_key,
                observation_kind=ObservationKind.FACTUAL_EVENT,
                source_contract=PRICE_SOURCE_CONTRACT,
                source_module="trading_system.research.trajectory.trajectory_stage2",
                source_module_version=TRAJECTORY_STAGE2_CONTRACT_VERSION,
                observation_domain="PRICE",
                observation_type="NEW_FAVORABLE_EXTREME",
                same_information_batch_order_unknown=same_bar_ambiguous,
            )
            envelopes.append(envelope_fav)
            envelope_fav_id = envelope_fav.envelope_id

        if is_new_adv:
            envelope_adv = make_observation_envelope(
                interval=interval,
                observation_information_key=obs_key,
                factual_available_at_information_key=avail_key,
                observation_kind=ObservationKind.FACTUAL_EVENT,
                source_contract=PRICE_SOURCE_CONTRACT,
                source_module="trading_system.research.trajectory.trajectory_stage2",
                source_module_version=TRAJECTORY_STAGE2_CONTRACT_VERSION,
                observation_domain="PRICE",
                observation_type="NEW_ADVERSE_EXTREME",
                same_information_batch_order_unknown=same_bar_ambiguous,
            )
            envelopes.append(envelope_adv)
            envelope_adv_id = envelope_adv.envelope_id

        point = PriceTrajectoryPoint(
            bar_position=pos,
            bar_offset_from_decision=pos - decision_pos,
            open=o,
            high=h,
            low=l,
            close=c,
            volume=vol,
            reference_price=ref,
            direction=direction,
            close_displacement=float(close_disp),
            current_favorable_excursion=float(fav_this),
            current_adverse_excursion=float(adv_this),
            running_favorable_excursion=float(running_fav),
            running_adverse_excursion=float(running_adv),
            favorable_extreme_price=fav_extreme_price,
            favorable_extreme_position=fav_extreme_pos,
            adverse_extreme_price=adv_extreme_price,
            adverse_extreme_position=adv_extreme_pos,
            is_new_favorable_extreme=bool(is_new_fav),
            is_new_adverse_extreme=bool(is_new_adv),
            same_bar_order_ambiguous=bool(same_bar_ambiguous),
            observation_information_key=obs_key,
            factual_available_at_key=avail_key,
            envelope_id_bar=envelope_bar.envelope_id,
            envelope_id_fav=envelope_fav_id,
            envelope_id_adv=envelope_adv_id,
        )
        points.append(point)
        rows.append(
            {
                "bar_position": pos,
                "bar_offset_from_decision": pos - decision_pos,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": vol,
                "reference_price": ref,
                "direction": direction,
                "close_displacement": float(close_disp),
                "current_favorable_excursion": float(fav_this),
                "current_adverse_excursion": float(adv_this),
                "running_favorable_excursion": float(running_fav),
                "running_adverse_excursion": float(running_adv),
                "favorable_extreme_price": fav_extreme_price,
                "favorable_extreme_position": fav_extreme_pos,
                "adverse_extreme_price": adv_extreme_price,
                "adverse_extreme_position": adv_extreme_pos,
                "is_new_favorable_extreme": bool(is_new_fav),
                "is_new_adverse_extreme": bool(is_new_adv),
                "same_bar_order_ambiguous": bool(same_bar_ambiguous),
                "envelope_id_bar": envelope_bar.envelope_id,
                "envelope_id_fav": envelope_fav_id,
                "envelope_id_adv": envelope_adv_id,
            }
        )

    price_bars = pd.DataFrame(rows)
    # Enforce dtypes where possible
    if not price_bars.empty:
        price_bars["bar_position"] = pd.array(price_bars["bar_position"], dtype="Int64")
        price_bars["bar_offset_from_decision"] = pd.array(price_bars["bar_offset_from_decision"], dtype="Int64")

    return PriceTrajectoryResult(
        price_bars=price_bars,
        points=tuple(points),
        observation_envelopes=tuple(envelopes),
        running_favorable_final=float(running_fav),
        running_adverse_final=float(running_adv),
        same_bar_ambiguous_count=int(ambiguous_count),
    )


# ---------------------------------------------------------------------------
# STRUCTURE - consume CLOSED 2.1A/B/C only
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StructureObservationResult:
    structure_events: pd.DataFrame
    observation_envelopes: Tuple[ObservationEnvelope, ...]


def _run_closed_structure_chain(market_history: pd.DataFrame, swing_policy=None) -> pd.DataFrame:
    """Run CLOSED 2.1A -> 2.1B -> 2.1C chain over full history, no reimplementation."""
    # Import inside function to avoid import at module load if not needed, but still allowed.
    from trading_system.structure.structural_breaks import CausalStructuralBreakEngine
    from trading_system.structure.swing_detector import CausalAdaptiveSwingDetector
    from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine

    # Ensure required columns
    needed = {"high", "low", "close"}
    if not needed.issubset(set(market_history.columns)):
        raise TrajectoryDataError(f"market_history missing {needed} for structure chain")

    detector = CausalAdaptiveSwingDetector(confirmation_policy=swing_policy)
    df_a = detector.analyze(market_history.copy(deep=True))
    df_b = ConfirmedSwingSequenceEngine().analyze(df_a)
    df_c = CausalStructuralBreakEngine().analyze(df_b)
    return df_c


def build_structure_trajectory(
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    interval: TrajectoryInterval,
    swing_policy=None,
) -> StructureObservationResult:
    _validate_anchor(anchor)
    _validate_interval_and_timeline(timeline, anchor, adapter, market_history, interval)

    decision_pos = anchor.decision_information_key.bar_position
    start_pos = decision_pos + 1
    end_pos = interval.end_inclusive_bar_position
    index = market_history.index

    # PATCH: consume legal prefix only to respect information boundary.
    # CLOSED engines are causal/prefix-invariant, but passing future data beyond interval end
    # would violate Stage 2 boundary even if prefix output stays identical.
    # Therefore we truncate market_history to end_pos inclusive for structure chain.
    # Timeline verification still uses full market_history for seal integrity.
    if end_pos + 1 < len(market_history):
        market_prefix = market_history.iloc[: end_pos + 1].copy(deep=True)
    else:
        market_prefix = market_history.copy(deep=True)
    df_c = _run_closed_structure_chain(market_prefix, swing_policy=swing_policy)

    envelopes: list[ObservationEnvelope] = []
    rows: list[dict] = []

    # For each observed pos
    for pos in range(start_pos, end_pos + 1):
        if pos >= len(df_c):
            continue
        row = df_c.iloc[pos]

        obs_key = _key_for_position(adapter, index, pos)
        avail_key = obs_key

        # Helper to emit envelope
        def emit(domain, otype, kind, src_module, src_contract, src_version, same_amb=False, extra=None):
            env = make_observation_envelope(
                interval=interval,
                observation_information_key=obs_key,
                factual_available_at_information_key=avail_key,
                observation_kind=kind,
                source_contract=src_contract,
                source_module=src_module,
                source_module_version=src_version,
                observation_domain=domain,
                observation_type=otype,
                same_information_batch_order_unknown=same_amb,
            )
            envelopes.append(env)
            base = {
                "bar_position": pos,
                "bar_offset_from_decision": pos - decision_pos,
                "observation_domain": domain,
                "observation_type": otype,
                "observation_kind": kind.value,
                "envelope_id": env.envelope_id,
                "observation_information_key_bar_position": obs_key.bar_position,
                "same_information_batch_order_unknown": same_amb,
                "source_module": src_module,
                "source_contract": src_contract,
            }
            if extra:
                base.update(extra)
            rows.append(base)
            return env

        # 2.1A confirmed swings
        # swing_high_confirmed and swing_low_confirmed are booleans
        try:
            if bool(row["swing_high_confirmed"]):
                origin = int(row["swing_origin_position"]) if pd.notna(row["swing_origin_position"]) else None
                # origin != confirmation preserved by CLOSED contract
                if origin is not None and origin >= pos:
                    raise TrajectoryDataError(f"swing origin >= confirmation at {pos}")
                emit(
                    domain="STRUCTURE",
                    otype="SWING_HIGH_CONFIRMED",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.swing_detector",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1A"],
                    src_version="2.1A_V1_1",
                    extra={
                        "swing_origin_position": origin,
                        "swing_price": float(row["swing_price"]) if pd.notna(row["swing_price"]) else None,
                        "swing_confirmation_position": pos,
                    },
                )
            if bool(row["swing_low_confirmed"]):
                origin = int(row["swing_origin_position"]) if pd.notna(row["swing_origin_position"]) else None
                if origin is not None and origin >= pos:
                    raise TrajectoryDataError(f"swing origin >= confirmation at {pos}")
                emit(
                    domain="STRUCTURE",
                    otype="SWING_LOW_CONFIRMED",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.swing_detector",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1A"],
                    src_version="2.1A_V1_1",
                    extra={
                        "swing_origin_position": origin,
                        "swing_price": float(row["swing_price"]) if pd.notna(row["swing_price"]) else None,
                        "swing_confirmation_position": pos,
                    },
                )
        except KeyError:
            # If columns missing (should not), skip
            pass

        # 2.1B sequence
        try:
            evt_type = str(row["structure_event_type"])
            seq_class = str(row["swing_sequence_class"])
            if evt_type != "NONE":
                # comparison_available bool, previous price etc exist
                emit(
                    domain="STRUCTURE",
                    otype=f"SEQUENCE_{evt_type}_{seq_class}",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.swing_sequence",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1B"],
                    src_version="2.1B_V1",
                    extra={
                        "structure_event_type": evt_type,
                        "swing_sequence_class": seq_class,
                        "comparison_available": bool(row["comparison_available"]) if "comparison_available" in row else None,
                        "previous_same_type_price": float(row["previous_same_type_price"]) if pd.notna(row.get("previous_same_type_price", pd.NA)) else None,
                    },
                )
        except KeyError:
            pass

        # 2.1C breach events
        try:
            # factual breach events
            if bool(row.get("high_wick_breach_event", False)):
                emit(
                    domain="STRUCTURE",
                    otype="BREACH_HIGH_WICK",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.structural_breaks",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1C"],
                    src_version="2.1C_V1_1",
                    extra={
                        "monitored_high_price": float(row["monitored_high_price"]) if pd.notna(row.get("monitored_high_price")) else None,
                        "high_wick_overshoot_fraction": float(row.get("high_wick_overshoot_fraction", float("nan"))),
                        "high_wick_break_evidence": float(row.get("high_wick_break_evidence", float("nan"))),
                    },
                )
            if bool(row.get("high_close_breach_event", False)):
                emit(
                    domain="STRUCTURE",
                    otype="BREACH_HIGH_CLOSE",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.structural_breaks",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1C"],
                    src_version="2.1C_V1_1",
                    extra={
                        "monitored_high_price": float(row["monitored_high_price"]) if pd.notna(row.get("monitored_high_price")) else None,
                        "high_close_overshoot_fraction": float(row.get("high_close_overshoot_fraction", float("nan"))),
                    },
                )
            if bool(row.get("low_wick_breach_event", False)):
                emit(
                    domain="STRUCTURE",
                    otype="BREACH_LOW_WICK",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.structural_breaks",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1C"],
                    src_version="2.1C_V1_1",
                    extra={
                        "monitored_low_price": float(row["monitored_low_price"]) if pd.notna(row.get("monitored_low_price")) else None,
                        "low_wick_overshoot_fraction": float(row.get("low_wick_overshoot_fraction", float("nan"))),
                    },
                )
            if bool(row.get("low_close_breach_event", False)):
                emit(
                    domain="STRUCTURE",
                    otype="BREACH_LOW_CLOSE",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.structural_breaks",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1C"],
                    src_version="2.1C_V1_1",
                    extra={
                        "monitored_low_price": float(row["monitored_low_price"]) if pd.notna(row.get("monitored_low_price")) else None,
                        "low_close_overshoot_fraction": float(row.get("low_close_overshoot_fraction", float("nan"))),
                    },
                )
            if bool(row.get("high_wick_only_breach_event", False)):
                emit(
                    domain="STRUCTURE",
                    otype="BREACH_HIGH_WICK_ONLY",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.structural_breaks",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1C"],
                    src_version="2.1C_V1_1",
                )
            if bool(row.get("low_wick_only_breach_event", False)):
                emit(
                    domain="STRUCTURE",
                    otype="BREACH_LOW_WICK_ONLY",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.structural_breaks",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1C"],
                    src_version="2.1C_V1_1",
                )
            # structural break interpretation
            break_evt = str(row.get("structural_break_event", "NONE"))
            if break_evt != "NONE":
                # BOS_UP, BOS_DOWN, CHOCH_UP, CHOCH_DOWN, UNCLASSIFIED_BREAK, AMBIGUOUS_DOUBLE_BREAK are factual
                emit(
                    domain="STRUCTURE",
                    otype=f"BREAK_{break_evt}",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.structural_breaks",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1C"],
                    src_version="2.1C_V1_1",
                    extra={
                        "structure_state_before": str(row.get("structure_state_before", "")),
                        "structure_state_after": str(row.get("structure_state_after", "")),
                    },
                )
            # state change if before != after
            state_before = str(row.get("structure_state_before", "UNDEFINED"))
            state_after = str(row.get("structure_state_after", "UNDEFINED"))
            if state_before != state_after and state_before != "" and state_after != "":
                emit(
                    domain="STRUCTURE",
                    otype=f"STATE_{state_before}_TO_{state_after}",
                    kind=ObservationKind.FACTUAL_EVENT,
                    src_module="trading_system.structure.structural_breaks",
                    src_contract=STRUCTURE_SOURCE_CONTRACTS["2.1C"],
                    src_version="2.1C_V1_1",
                    extra={"structure_state_before": state_before, "structure_state_after": state_after},
                )
        except Exception as exc:
            # Any unexpected should be surfaced as data error if not KeyError
            if not isinstance(exc, KeyError):
                raise

    df = pd.DataFrame(rows)
    return StructureObservationResult(structure_events=df, observation_envelopes=tuple(envelopes))


# ---------------------------------------------------------------------------
# LIFECYCLE - consume CLOSED 6.1B ledger only
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LifecycleObservationResult:
    lifecycle_events: pd.DataFrame
    observation_envelopes: Tuple[ObservationEnvelope, ...]
    terminal_position: Optional[int]
    terminal_state: Optional[str]


def build_lifecycle_trajectory(
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    interval: TrajectoryInterval,
    hypothesis_ledger: Optional[pd.DataFrame] = None,
) -> LifecycleObservationResult:
    _validate_anchor(anchor)
    _validate_interval_and_timeline(timeline, anchor, adapter, market_history, interval)

    decision_pos = anchor.decision_information_key.bar_position
    end_pos = interval.end_inclusive_bar_position
    index = market_history.index

    if hypothesis_ledger is None or hypothesis_ledger.empty:
        # Unresolved - no lifecycle events within interval
        return LifecycleObservationResult(
            lifecycle_events=pd.DataFrame(),
            observation_envelopes=tuple(),
            terminal_position=None,
            terminal_state=None,
        )

    # Validate required columns
    required = {"hypothesis_id", "event_position", "ledger_event_type", "new_state", "trigger_relationship_id"}
    if not required.issubset(set(hypothesis_ledger.columns)):
        raise TrajectoryDataError(f"hypothesis_ledger missing required {required}")

    # Filter for this hypothesis and post-decision
    filtered = hypothesis_ledger[
        (hypothesis_ledger["hypothesis_id"] == anchor.hypothesis_id)
        & (hypothesis_ledger["event_position"] > decision_pos)
        & (hypothesis_ledger["event_position"] <= end_pos)
    ].copy()

    if filtered.empty:
        return LifecycleObservationResult(
            lifecycle_events=pd.DataFrame(),
            observation_envelopes=tuple(),
            terminal_position=None,
            terminal_state=None,
        )

    filtered.sort_values(by=["event_position", "ledger_event_id"], inplace=True)

    envelopes: list[ObservationEnvelope] = []
    rows: list[dict] = []

    terminal_pos: Optional[int] = None
    terminal_state: Optional[str] = None

    for _, r in filtered.iterrows():
        pos = int(r["event_position"])
        new_state = str(r["new_state"]) if pd.notna(r["new_state"]) else ""
        ledger_event_type = str(r["ledger_event_type"]) if pd.notna(r["ledger_event_type"]) else ""

        # Only literal terminal states per scope
        if new_state not in _CLOSED_TERMINAL:
            # Skip non-terminal states (MONITORING etc.) - they are not literal terminal
            # But we still record if needed? Spec says literal terminal states only.
            continue

        # Enforce no second terminal after first? In CLOSED 6.1B there is exactly one terminal per hypothesis.
        # If we see multiple terminals within interval, that's invalid.
        if terminal_pos is not None:
            raise TrajectoryDataError(f"multiple terminal states for hypothesis {anchor.hypothesis_id} within interval")

        terminal_pos = pos
        terminal_state = new_state

        obs_key = _key_for_position(adapter, index, pos)
        avail_key = obs_key

        # Check interval end must equal terminal for mature case
        # The caller should have bound interval to terminal; we enforce if there are more market rows beyond terminal in interval, that's disallowed.
        # Actually if terminal exists, interval.end must == terminal position, else post-terminal rows included.
        if end_pos != pos:
            # If there is a terminal at pos but interval ends after pos, that includes post-terminal market rows -> violation
            raise TrajectoryDataError(
                f"mature trajectory interval includes post-terminal market rows: terminal at {pos}, interval end at {end_pos}. Must end at terminal factual-availability boundary."
            )

        env = make_observation_envelope(
            interval=interval,
            observation_information_key=obs_key,
            factual_available_at_information_key=avail_key,
            observation_kind=ObservationKind.FACTUAL_EVENT,
            source_contract=LIFECYCLE_SOURCE_CONTRACT,
            source_module="trading_system.decision.narrative",
            source_module_version="6.1B_V1_2",
            observation_domain="LIFECYCLE",
            observation_type=new_state,
            same_information_batch_order_unknown=False,
        )
        envelopes.append(env)
        rows.append(
            {
                "bar_position": pos,
                "bar_offset_from_decision": pos - decision_pos,
                "ledger_event_id": int(r["ledger_event_id"]) if pd.notna(r["ledger_event_id"]) else None,
                "ledger_event_type": ledger_event_type,
                "previous_state": str(r["previous_state"]) if pd.notna(r["previous_state"]) else None,
                "new_state": new_state,
                "trigger_relationship_id": int(r["trigger_relationship_id"]) if pd.notna(r["trigger_relationship_id"]) else None,
                "superseded_by_hypothesis_id": int(r["superseded_by_hypothesis_id"]) if "superseded_by_hypothesis_id" in r and pd.notna(r["superseded_by_hypothesis_id"]) else None,
                "observation_domain": "LIFECYCLE",
                "observation_type": new_state,
                "envelope_id": env.envelope_id,
                "observation_information_key_bar_position": obs_key.bar_position,
            }
        )

    df = pd.DataFrame(rows)

    return LifecycleObservationResult(
        lifecycle_events=df,
        observation_envelopes=tuple(envelopes),
        terminal_position=terminal_pos,
        terminal_state=terminal_state,
    )


# ---------------------------------------------------------------------------
# Combined Stage 2 result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrajectoryStage2Result:
    price: PriceTrajectoryResult
    structure: StructureObservationResult
    lifecycle: LifecycleObservationResult
    all_envelopes: Tuple[ObservationEnvelope, ...]


def build_stage2_trajectory(
    *,
    timeline: MarketObservationTimeline,
    anchor: DecisionAnchor,
    adapter: TimelineAdapter,
    market_history: pd.DataFrame,
    interval: TrajectoryInterval,
    swing_policy=None,
    hypothesis_ledger: Optional[pd.DataFrame] = None,
) -> TrajectoryStage2Result:
    """Build full Stage 2 PRICE + STRUCTURE + LIFECYCLE trajectory.

    No post-terminal market rows allowed for mature case. Caller must bind
    interval.end_inclusive to terminal position if mature.

    swing_policy: optional CausalAdaptiveSwingDetector policy (e.g. EmpiricalConfirmationPolicy).
                  If None, structure will be evidence-only (no confirmed swings).
    hypothesis_ledger: optional CLOSED 6.1B ledger for lifecycle.
    """
    _validate_anchor(anchor)
    _validate_interval_and_timeline(timeline, anchor, adapter, market_history, interval)

    price_res = build_price_trajectory(
        timeline=timeline, anchor=anchor, adapter=adapter, market_history=market_history, interval=interval
    )

    structure_res = build_structure_trajectory(
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market_history,
        interval=interval,
        swing_policy=swing_policy,
    )

    lifecycle_res = build_lifecycle_trajectory(
        timeline=timeline,
        anchor=anchor,
        adapter=adapter,
        market_history=market_history,
        interval=interval,
        hypothesis_ledger=hypothesis_ledger,
    )

    all_envs = tuple(list(price_res.observation_envelopes) + list(structure_res.observation_envelopes) + list(lifecycle_res.observation_envelopes))
    # Deterministic ordering: sort by observation key position then envelope_id for same position
    all_envs_sorted = tuple(sorted(all_envs, key=lambda e: (e.observation_information_key.bar_position, e.envelope_id)))

    return TrajectoryStage2Result(
        price=price_res, structure=structure_res, lifecycle=lifecycle_res, all_envelopes=all_envs_sorted
    )


def trajectory_stage2_manifest() -> pd.DataFrame:
    rows = [
        ("CONTRACT", "VERSION", TRAJECTORY_STAGE2_CONTRACT_VERSION),
        ("STAGE", "SCOPE", "STAGE_2_PRICE_STRUCTURE_LIFECYCLE"),
        ("PRICE", "FACTS", "OHLCV_RAW+REFERENCE+DIRECTION+FAVORABLE_ADVERSE_CURRENT+RUNNING_MAX+EXTREME_PRICE_POS+NEW_EXTREME_FLAGS+CLOSE_DISP+BAR_OFFSET"),
        ("PRICE", "SAME_BAR", "SAME_INFORMATION_BATCH_ORDER_UNKNOWN_WHEN_BOTH_EXTREMES_IN_SAME_BAR"),
        ("PRICE", "TIE", "EQUAL_RUNNING_EXTREME_PRESERVES_FIRST_OCCURRENCE_STRICT_GREATER_ONLY"),
        ("PRICE", "ORIENTATION", "UP_FAV_HIGH_ADV_LOW_DOWN_FAV_LOW_ADV_HIGH_MATCHES_6_2A_1"),
        ("STRUCTURE", "SOURCE", "CLOSED_2_1A_2_1B_2_1C_ONLY"),
        ("STRUCTURE", "AVAILABILITY", "CONFIRMATION_POSITION_IS_FACTUAL_AVAILABLE_AT_NOT_ORIGIN"),
        ("STRUCTURE", "ORIGIN", "ORIGIN_BEFORE_CONFIRMATION"),
        ("STRUCTURE", "TAXONOMY", "SWING_HIGH_LOW_CONFIRMED_SEQUENCE_BREACH_WICK_CLOSE_WICK_ONLY_BREAK_BOS_CHO_STATE"),
        ("LIFECYCLE", "SOURCE", "CLOSED_6_1B_LEDGER_ONLY"),
        ("LIFECYCLE", "TERMINAL", "CONTRADICTED_SUPERSEDED_OBSERVED_DIRECTION_ESTABLISHED_LITERAL_ONLY"),
        ("LIFECYCLE", "NO_SECOND_MACHINE", "NO_PRICE_INFERRED_TERMINAL"),
        ("LIFECYCLE", "POST_TERMINAL", "NO_POST_TERMINAL_MARKET_ROWS_MATURE_END_EQUALS_TERMINAL"),
        ("INTERVAL", "SEMANTICS", "(DECISION_BATCH, END_INCLUSIVE]_CREATION_BAR_EXCLUDED"),
        ("OUT_OF_SCOPE", "VOLATILITY", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "LIQUIDITY", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "OB_FVG", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "DEALING_RANGE", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "ORDERFLOW", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "SESSION", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "MTF", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "CENSOR_SERIES", "NOT_IMPLEMENTED_STAGE_3"),
        ("OUT_OF_SCOPE", "DESCRIPTORS", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "ESTIMANDS", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "MODEL", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "GEOMETRY", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "EXECUTION", "NOT_IMPLEMENTED"),
        ("OUT_OF_SCOPE", "WIN_LOSS_SUCCESS", "FORBIDDEN"),
    ]
    return pd.DataFrame(
        [{"record_type": a, "name": b, "value": c, "serialization_order": i} for i, (a, b, c) in enumerate(rows)]
    )

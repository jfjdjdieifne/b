"""Field-run pipeline glue: CLOSED public APIs ONLY — no engine re-implementation.

Order of operations is contractual:

1. CLOSED Binance Source Adapter V1 loads/validates minute facts + official
   klines (fail-closed), runs exact cross-witness, assembles the canonical
   bundle (canonical OHLC = published kline EXCLUSIVELY), and derives the
   executed/initiated flow source separately.
2. The runner seals ``MarketObservationTimeline`` through its own public API
   (seal is called here, by the consumer — never inside a loader).
3. CLOSED engines are invoked through their public ``analyze`` APIs on
   per-engine input frames built from canonical facts and upstream outputs.
   Nothing engine-internal is recomputed here.
4. Branches whose policy/contract inputs are not configured are DECLARED
   (``NOT_CONFIGURED`` / ``NOT_AVAILABLE``) — never silently defaulted.

``TIE_ORDER_CONTRACT = NOT_PROVEN`` throughout. Ambiguous open/close stays
ambiguous; reconstructed O/C never becomes canonical OHLC.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

TIE_ORDER_CONTRACT = "NOT_PROVEN"
EXECUTED_FLOW_LABEL = "EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT"
ACTUAL_MEANS = (
    "EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT (source semantics only); "
    "NOT order-book truth, NOT buying pressure, NOT institutional activity, "
    "NOT whale activity, NOT market-wide flow"
)


import time as _time


def _progress(message: str) -> None:
    """Stage-progress line so long month-scale runs are observable (no semantics)."""
    print(f"[{_time.strftime('%H:%M:%S')}] {message}", flush=True)


def _timed(message: str, fn):
    _progress(f"{message} ...")
    t0 = _time.time()
    out = fn()
    _progress(f"{message} done in {_time.time() - t0:.1f}s")
    return out


@dataclass
class FieldRunConfig:
    """Owner-visible run configuration. NULL/empty = DECLARED not-invented."""

    swing_quantile: float | None = None  # None -> SWINGS NOT_CONFIGURED
    swing_prior_continuation_reversals: tuple = ()  # owner-supplied, default NONE
    swing_prior_confirmed_reversals: tuple = ()  # owner-supplied, default NONE
    sessions: list = field(default_factory=list)  # [] -> SESSION SCHEDULES NOT_CONFIGURED
    sample_size: int = 100  # explicit owner parameter, NOT sacred
    htf_durations: tuple = ("1h",)  # declared HTF scales, NOT sacred
    symbol: str = "BTCUSDT"
    year_month: str = "2026-05"
    period_start_utc: str = "2026-05-01T00:00:00Z"
    period_end_utc: str = "2026-06-01T00:00:00Z"

    @classmethod
    def from_dict(cls, data: dict) -> "FieldRunConfig":
        cfg = cls()
        for key, value in (data or {}).items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg


@dataclass
class BranchStatus:
    name: str
    status: str  # RAN | NOT_CONFIGURED | NOT_AVAILABLE
    detail: str = ""


class FieldPipelineError(Exception):
    """Unexpected failure on configured/valid inputs (fail-closed)."""


def _status(statuses: list, name: str, status: str, detail: str = "") -> None:
    statuses.append(BranchStatus(name=name, status=status, detail=detail))


def load_sources(
    *,
    facts_csv: str,
    facts_sidecar: str,
    klines_csv: str,
    config: FieldRunConfig,
    expected_facts_sha256: str | None = None,
    expected_klines_sha256: str | None = None,
    expected_raw_source_sha256: str | None = None,
    expected_converter_sha256: str | None = None,
):
    """Steps 1: CLOSED adapters only (load, cross-witness, canonical, flow)."""
    from trading_system.sources import (
        SourceArtifactIdentity,
        TIE_ORDER_CONTRACT as _TIE,
    )
    from trading_system.sources.binance_spot_minute_facts_source import (
        MinuteFactsExpectedProvenance,
        load_minute_facts,
    )
    from trading_system.sources.binance_spot_kline_ohlc_source import (
        KlineExpectedProvenance,
        assemble_canonical_bundle,
        cross_witness_sources,
        load_binance_spot_klines,
    )
    from trading_system.sources.binance_executed_flow_source import (
        build_executed_flow_source,
    )

    assert _TIE == TIE_ORDER_CONTRACT
    identity = SourceArtifactIdentity(
        symbol=config.symbol,
        market_type="SPOT",
        interval="1m",
        period_start_utc=config.period_start_utc,
        period_end_utc=config.period_end_utc,
    )
    facts_expected = MinuteFactsExpectedProvenance(
        symbol=config.symbol,
        raw_source_sha256=expected_raw_source_sha256,
        converter_sha256=expected_converter_sha256,
        minute_facts_sha256=expected_facts_sha256,
    )

    facts = load_minute_facts(
        facts_csv,
        facts_sidecar,
        identity=identity,
        expected=facts_expected,
    )
    kline_expected = KlineExpectedProvenance(
        symbol=config.symbol, source_file_sha256=expected_klines_sha256
    )

    klines = load_binance_spot_klines(
        klines_csv,
        identity=identity,
        expected=kline_expected,
    )
    witness = cross_witness_sources(klines, facts)
    bundle = assemble_canonical_bundle(klines, facts, cross_witness=witness)
    flow = build_executed_flow_source(facts)
    return {
        "identity": identity,
        "facts": facts,
        "klines": klines,
        "cross_witness": witness,
        "bundle": bundle,
        "flow": flow,
    }


def seal_timeline(bundle, timeline_id: str):
    """Layer separation: the CONSUMER seals the timeline, via public API."""
    from trading_system.research.information_time import TimeIndexedTimelineAdapter
    from trading_system.research.trajectory.trajectory_contract import (
        MarketObservationTimeline,
    )

    market_history = bundle.canonical_market_frame
    adapter = TimeIndexedTimelineAdapter(timeline_id=timeline_id)
    timeline = MarketObservationTimeline.seal(
        adapter=adapter, market_history=market_history
    )
    return timeline, adapter, market_history


def run_engines(*, market_history, flow, config: FieldRunConfig, statuses: list) -> dict:
    """Steps 3-4: CLOSED engines through public analyze() APIs only."""
    from trading_system.environment.dynamic_volatility import DynamicVolatilityEngine
    from trading_system.environment.session_context import (
        CausalSessionContextEngine,
        SessionDefinition,
    )
    from trading_system.orderflow.volume_delta import (
        CausalVolumeDeltaEngine,
        OrderFlowMode,
    )
    from trading_system.orderflow.absorption import CausalAbsorptionEvidenceEngine
    from trading_system.multitimeframe.causal_htf import (
        CausalHTFAggregator,
        TimeAggregationSpec,
    )
    from trading_system.zones.fvg import CausalFVGEngine

    out = {}
    lows = market_history

    # ---- always-legal branches (no policy input required) ----
    out["volatility"] = _timed("ENGINE dynamic_volatility_1_1", lambda: DynamicVolatilityEngine().analyze(lows))
    _status(statuses, "dynamic_volatility_1_1", "RAN")

    # Session Context: calendar features are produced by the closed contract
    # with any schedule; session SCHEDULES themselves are owner configuration.
    if config.sessions:
        definitions = tuple(
            SessionDefinition(
                name=s["name"],
                timezone=s["timezone"],
                start_local=_parse_hhmm(s["start_local"]),
                end_local=_parse_hhmm(s["end_local"]),
            )
            for s in config.sessions
        )
        session_detail = f"{len(definitions)} owner-configured schedule(s)"
    else:
        definitions = ()
        session_detail = "session schedules NOT_CONFIGURED (calendar features still RAN)"
    out["sessions"] = _timed("ENGINE session_context_1_2", lambda: CausalSessionContextEngine(definitions).analyze(lows))
    _status(statuses, "session_context_1_2", "RAN", session_detail)

    out["fvg"], out["fvg_events"] = _timed("ENGINE fvg_4_2a", lambda: CausalFVGEngine().analyze(lows))
    _status(statuses, "fvg_4_2a", "RAN")

    # Order flow: PROXY from canonical OHLCV; ACTUAL from the executed-flow
    # source frame. They are kept STRICTLY separate — never merged.
    out["flow_proxy"] = _timed(
        "ENGINE order_flow_proxy_3_1",
        lambda: CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(lows),
    )
    _status(statuses, "order_flow_proxy_3_1", "RAN", "OHLCV_PROXY (stays PROXY)")

    actual_input = pd.DataFrame(
        {
            "buy_volume": flow.frame["buy_volume"],
            "sell_volume": flow.frame["sell_volume"],
            "volume": flow.frame["volume"],
        }
    )
    out["flow_actual"] = _timed(
        "ENGINE order_flow_actual_3_1",
        lambda: CausalVolumeDeltaEngine(
            mode=OrderFlowMode.ACTUAL_AGGRESSOR, reconcile_total_volume=True
        ).analyze(actual_input),
    )
    _status(
        statuses,
        "order_flow_actual_3_1",
        "RAN",
        EXECUTED_FLOW_LABEL + " — " + ACTUAL_MEANS,
    )

    out["absorption_actual"] = _timed(
        "ENGINE absorption_actual_3_2",
        lambda: CausalAbsorptionEvidenceEngine(
            mode=OrderFlowMode.ACTUAL_AGGRESSOR
        ).analyze(lows[["close"]].join(out["flow_actual"])),
    )
    _status(statuses, "absorption_actual_3_2", "RAN", "ACTUAL executed/initiated basis")

    out["absorption_proxy"] = _timed(
        "ENGINE absorption_proxy_3_2",
        lambda: CausalAbsorptionEvidenceEngine(
            mode=OrderFlowMode.OHLCV_PROXY
        ).analyze(out["flow_proxy"]),
    )
    _status(statuses, "absorption_proxy_3_2", "RAN", "PROXY basis (stays PROXY)")

    # ---- HTF factual aggregation (declared scales) ----
    htf_frames = {}
    for duration in config.htf_durations:
        spec = TimeAggregationSpec(duration=pd.Timedelta(duration))
        htf_frames[duration] = _timed(f"ENGINE htf_5_1_{duration}", lambda: CausalHTFAggregator(spec=spec).analyze(lows))
    out["htf"] = htf_frames
    _status(statuses, "htf_factual_aggregation_5_1", "RAN", f"scales={list(config.htf_durations)}")

    # ---- swings branch (policy-gated; NEVER invented) ----
    swing_state = {"status": "NOT_CONFIGURED", "detail": "swing confirmation policy requires an explicit quantile; none configured (owner parameter swing_quantile)"}
    if config.swing_quantile is not None:
        from trading_system.structure.swing_detector import (
            CausalAdaptiveSwingDetector,
            EmpiricalConfirmationPolicy,
        )
        from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine
        from trading_system.structure.structural_breaks import CausalStructuralBreakEngine
        from trading_system.liquidity.liquidity_map import CausalLiquidityMapEngine
        from trading_system.zones.order_blocks import CausalOrderBlockEngine
        from trading_system.zones.dealing_range import CausalDealingRangeEngine

        policy = EmpiricalConfirmationPolicy(
            quantile=float(config.swing_quantile),
            prior_continuation_reversals=tuple(config.swing_prior_continuation_reversals),
            prior_confirmed_reversals=tuple(config.swing_prior_confirmed_reversals),
        )
        out["swings"] = _timed("ENGINE swing_detector_2_1a", lambda: CausalAdaptiveSwingDetector(policy).analyze(lows))
        _status(statuses, "swing_detector_2_1a", "RAN",
                f"OWNER_SUPPLIED_QUANTILE={config.swing_quantile} (NOT_SACRED)")

        swing_cols = ["swing_high_confirmed", "swing_low_confirmed",
                      "swing_origin_position", "swing_price",
                      "swing_confirmation_position"]
        seq_input = out["swings"][swing_cols].copy()
        out["swing_sequence"] = _timed("ENGINE swing_sequence_2_1b", lambda: ConfirmedSwingSequenceEngine().analyze(seq_input))
        _status(statuses, "swing_sequence_2_1b", "RAN")

        seq_keep = [c for c in ("swing_sequence_class", "structure_event_type",
                                "current_structure_confirmation_position",
                                "current_structure_origin_position",
                                "current_structure_swing_price",
                                "previous_same_type_origin_position",
                                "previous_same_type_price",
                                "same_type_log_price_change", "comparison_available")
                    if c in out["swing_sequence"].columns]
        struct_input = lows[["high", "low", "close"]].join(out["swings"][swing_cols]).join(
            out["swing_sequence"][seq_keep]
        )
        out["structure_breaks"] = _timed("ENGINE structural_breaks_2_1c", lambda: CausalStructuralBreakEngine().analyze(struct_input))
        _status(statuses, "structural_breaks_2_1c", "RAN")

        liq_input = lows[["high", "low", "close"]].join(out["swings"][swing_cols]).join(
            out["swing_sequence"][seq_keep]
        )
        levels, events = _timed("ENGINE liquidity_2_2", lambda: CausalLiquidityMapEngine().analyze(liq_input))
        out["liquidity_levels"] = levels
        out["liquidity_events"] = events
        _status(statuses, "liquidity_2_2", "RAN")

        ob_input = lows[["open", "high", "low", "close"]].join(out["swings"][swing_cols]).join(
            out["structure_breaks"][[c for c in (
                "structural_break_event", "structure_state_before",
                "high_close_breach_event", "low_close_breach_event",
            ) if c in out["structure_breaks"].columns]]
        )
        out["order_blocks"], out["order_block_events"] = _timed("ENGINE order_blocks_4_1", lambda: CausalOrderBlockEngine().analyze(ob_input))
        _status(statuses, "order_blocks_4_1", "RAN")

        dr_input = out["swings"][swing_cols].copy()
        dr_input["close"] = lows["close"]
        dr_input = dr_input.join(out["swing_sequence"][seq_keep])
        ranges_df, ranges_events = _timed("ENGINE dealing_range_4_2b", lambda: CausalDealingRangeEngine().analyze(dr_input))
        out["dealing_ranges"] = ranges_df
        out["dealing_range_events"] = ranges_events
        _status(statuses, "dealing_range_4_2b", "RAN")
        swing_state = {"status": "RAN", "detail": ""}
    else:
        for name, label in (
            ("swing_detector_2_1a", "swings"),
            ("swing_sequence_2_1b", "swing sequence"),
            ("structural_breaks_2_1c", "structural breaks (BOS/CHoCH)"),
            ("liquidity_2_2", "liquidity"),
            ("order_blocks_4_1", "order blocks"),
            ("dealing_range_4_2b", "dealing ranges"),
        ):
            _status(statuses, name, "NOT_CONFIGURED",
                    "blocked by unconfigured swing confirmation policy (no invented quantile)")
    _status(statuses, "swings_branch_summary", swing_state["status"], swing_state["detail"])
    return out


def _parse_hhmm(text: str):
    from datetime import time

    parts = str(text).split(":")
    return time(int(parts[0]), int(parts[1]))


def build_evidence_and_narrative(*, market_history, engine_out, config: FieldRunConfig, statuses: list) -> dict:
    """6.1A evidence vectors + 6.1B narrative, per flow mode, kept separate."""
    from trading_system.decision.evidence_vector import (
        CausalEvidenceVectorEngine,
        EvidenceVectorConfig,
        OrderFlowEvidenceMode,
    )
    from trading_system.decision.narrative import CausalMarketNarrativeEngine

    swings_ran = "swings" in engine_out

    def join_frame(flow_cols: list, flow_frame) -> pd.DataFrame:
        frame = market_history[["close"]].copy()
        frame = frame.join(engine_out["volatility"][[c for c in (
            "true_range_percentile", "true_range_history_count", "normalized_tr_change",
            "expansion_percentile", "expansion_history_count",
        ) if c in engine_out["volatility"].columns]])
        frame = frame.join(engine_out["sessions"][[c for c in (
            "hour_utc_sin", "hour_utc_cos", "weekday_sin", "weekday_cos",
        ) if c in engine_out["sessions"].columns]])
        if swings_ran:
            frame = frame.join(engine_out["structure_breaks"][[c for c in (
                "structure_state_after", "structural_break_event",
            ) if c in engine_out["structure_breaks"].columns]])
            frame = frame.join(engine_out["liquidity_levels"][[c for c in (
                "high_side_first_wick_only_count", "low_side_first_wick_only_count",
                "high_side_first_close_breach_count", "low_side_first_close_breach_count",
                "nearest_same_side_distance_fraction", "nearest_distance_percentile",
                "nearest_distance_reference_history_count",
            ) if c in engine_out["liquidity_levels"].columns]])
            frame = frame.join(engine_out["order_blocks"][[c for c in (
                "created_ob_displacement_fraction", "created_ob_displacement_percentile",
                "created_ob_displacement_history_count", "bullish_ob_first_touch_count",
                "bearish_ob_first_touch_count", "bullish_ob_first_far_side_wick_breach_count",
                "bearish_ob_first_far_side_wick_breach_count",
                "bullish_ob_first_far_side_close_breach_count",
                "bearish_ob_first_far_side_close_breach_count",
                "bullish_ob_first_reclaim_count", "bearish_ob_first_reclaim_count",
            ) if c in engine_out["order_blocks"].columns]])
            frame = frame.join(engine_out["dealing_ranges"][[c for c in (
                "current_range_position_raw", "current_midpoint_displacement",
                "current_discount_depth", "current_premium_depth",
            ) if c in engine_out["dealing_ranges"].columns]])
        frame = frame.join(engine_out["fvg"][[c for c in (
            "created_fvg_gap_width_fraction", "created_fvg_gap_width_percentile",
            "created_fvg_gap_width_history_count", "bullish_fvg_first_touch_count",
            "bearish_fvg_first_touch_count", "bullish_fvg_first_full_range_coverage_count",
            "bearish_fvg_first_full_range_coverage_count",
            "bullish_fvg_first_far_side_wick_breach_count",
            "bearish_fvg_first_far_side_wick_breach_count",
            "bullish_fvg_first_far_side_close_breach_count",
            "bearish_fvg_first_far_side_close_breach_count",
            "bullish_fvg_first_close_reclaim_count", "bearish_fvg_first_close_reclaim_count",
        ) if c in engine_out["fvg"].columns]])
        frame = frame.join(flow_frame[[c for c in flow_cols if c in flow_frame.columns]])
        return frame

    actual_cols = ["delta_ratio", "delta_ratio_percentile", "delta_ratio_history_count",
                   "delta_magnitude_percentile", "delta_magnitude_history_count",
                   "actual_absorption_evidence", "absorbed_aggression_side",
                   "opposed_response_percentile", "opposed_response_history_count"]
    proxy_cols = ["volume_pressure_proxy", "pressure_proxy_percentile",
                  "pressure_proxy_history_count", "pressure_magnitude_percentile",
                  "pressure_magnitude_history_count", "proxy_absorption_evidence",
                  "pressure_side", "pressure_opposed_response_percentile",
                  "pressure_opposed_response_history_count"]

    actual_flow_frame = engine_out["flow_actual"].join(
        engine_out["absorption_actual"][[c for c in (
            "actual_absorption_evidence", "absorbed_aggression_side",
            "opposed_response_percentile", "opposed_response_history_count",
        ) if c in engine_out["absorption_actual"].columns]]
    )
    proxy_flow_frame = engine_out["flow_proxy"].join(
        engine_out["absorption_proxy"][[c for c in (
            "proxy_absorption_evidence", "pressure_side",
            "pressure_opposed_response_percentile", "pressure_opposed_response_history_count",
        ) if c in engine_out["absorption_proxy"].columns]]
    )

    results = {}
    narrative = CausalMarketNarrativeEngine()
    for mode_name, flow_frame, cols, mode_enum in (
        ("actual", actual_flow_frame, actual_cols, OrderFlowEvidenceMode.ACTUAL),
        ("proxy", proxy_flow_frame, proxy_cols, OrderFlowEvidenceMode.PROXY),
    ):
        evidence_input = join_frame(cols, flow_frame)
        config_ev = EvidenceVectorConfig(
            environment=True,
            temporal_context=True,
            structure=swings_ran,
            liquidity=swings_ran,
            order_blocks=swings_ran,
            fvg=True,
            dealing_range=swings_ran,
            multiscale=False,
            order_flow_mode=mode_enum,
        )
        engine_ev = CausalEvidenceVectorEngine(config=config_ev)
        evidence_df, manifest = _timed(
            f"EVIDENCE 6.1A {mode_name}", lambda: engine_ev.analyze(evidence_input)
        )
        narrative_result = _timed(
            f"NARRATIVE 6.1B {mode_name}", lambda: narrative.analyze(evidence_df, manifest)
        )
        results[mode_name] = {
            "evidence_config": config_ev,
            "evidence_engine": engine_ev,
            "evidence_df": evidence_df,
            "feature_manifest": manifest,
            "narrative": narrative_result,
        }
        _status(statuses, f"evidence_vector_6_1a_{mode_name}", "RAN",
                f"flow_mode={mode_enum.value}; multiscale=False (5.2 outside owner run list)")
        _status(statuses, f"narrative_hypotheses_6_1b_{mode_name}", "RAN")
    return results

"""Field-report assembly: outputs A-F + chart overlay + reality preview.

Everything here is aggregation, as-of slicing, and reporting over CLOSED engine
outputs and CLOSED contract objects. No engine is re-implemented; no outcome is
injected into any decision snapshot; PROXY and ACTUAL are never merged into one
number. Detector outputs are reported as operational project definitions with
their module/contract identity — never as sole market truth.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import pandas as pd

DETECTOR_VALIDITY_NOTICE = (
    "Detector output = operational project definition (module version bound per "
    "entity). It does NOT mean 'the only market truth'. Entities are reported "
    "as 'detector version X under this run', never as 'detector works/fails'."
)
ACTUAL_MEANS = (
    "EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT per source semantics only; "
    "NOT order-book truth, NOT buying pressure, NOT institutional activity, "
    "NOT whale activity, NOT market-wide flow"
)

# Terminal event labels (runner-side summarization over CLOSED engine event
# streams — an accounting rule for ACTIVE entity bookkeeping, not an engine).
_OB_TERMINAL = {"FIRST_CLOSE_RECLAIM_OF_FAR_SIDE"}
_FVG_TERMINAL = {"FIRST_CLOSE_RECLAIM_OF_FAR_SIDE", "FIRST_FULL_RANGE_COVERAGE"}


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: str, frame: pd.DataFrame) -> str:
    frame.to_csv(path, index=False)
    return path


def _ffill_value(series: pd.Series, position: int):
    upto = series.iloc[: position + 1]
    valid = upto.dropna()
    if len(valid) == 0:
        return None
    return valid.iloc[-1]


def _active_ids(events: pd.DataFrame, position: int, id_col: str, terminal: set) -> list:
    if events is None or len(events) == 0:
        return []
    ev = events[events["event_position"] <= position]
    if not len(ev):
        return []
    last = ev.groupby(id_col, sort=True)["event_type"].last()
    return sorted(str(e) for e, t in last.items() if str(t) not in terminal)


# --------------------------------------------------------------------------------------
# B) DETECTION_AUDIT.csv — as-of decision-side facts ONLY (causal slice; no future)
# --------------------------------------------------------------------------------------

def build_detection_audit(
    *,
    market_history,
    engine_out,
    evidence_actual,
    narrative_actual,
    flow,
    sample_positions: tuple,
    sample_meta: dict,
) -> pd.DataFrame:
    rows = []
    swings = engine_out.get("swings")
    seq = engine_out.get("swing_sequence")
    struct = engine_out.get("structure_breaks")
    liq = engine_out.get("liquidity_levels")
    ob_state = engine_out.get("order_blocks")
    ob_events = engine_out.get("order_block_events")
    fvg_state = engine_out.get("fvg")
    fvg_events = engine_out.get("fvg_events")
    dr = engine_out.get("dealing_ranges")
    sess = engine_out["sessions"]
    vol = engine_out["volatility"]
    evidence_df = evidence_actual["evidence_df"]
    ledger = narrative_actual["narrative"].hypothesis_ledger

    for rank, i in enumerate(sample_positions):
        ts = market_history.index[i]
        row = {
            "sample_rank": rank,
            "sample_position": i,
            "timestamp_utc": str(ts),
            "open": float(market_history["open"].iloc[i]),
            "high": float(market_history["high"].iloc[i]),
            "low": float(market_history["low"].iloc[i]),
            "close": float(market_history["close"].iloc[i]),
            "vol_true_range_percentile": _num(vol["true_range_percentile"].iloc[i]),
            "vol_expansion_percentile": _num(vol["expansion_percentile"].iloc[i]),
            "session_active_count": int(sess["active_session_count"].iloc[i]),
            "session_schedule_status": (
                "OWNER_CONFIGURED" if any(c.startswith("session_") and c.endswith("_active")
                                          for c in sess.columns) else "NOT_CONFIGURED"
            ),
        }
        # latest confirmed swing facts (as-of: only rows <= i)
        if swings is not None:
            high_conf = swings["swing_high_confirmed"].to_numpy()[: i + 1]
            low_conf = swings["swing_low_confirmed"].to_numpy()[: i + 1]
            high_hits = [int(x) for x in range(len(high_conf)) if bool(high_conf[x])]
            low_hits = [int(x) for x in range(len(low_conf)) if bool(low_conf[x])]
            row["swing_last_high_price"] = _num(swings["swing_price"].iloc[high_hits[-1]]) if high_hits else None
            row["swing_last_high_confirmation_bar"] = high_hits[-1] if high_hits else None
            row["swing_last_low_price"] = _num(swings["swing_price"].iloc[low_hits[-1]]) if low_hits else None
            row["swing_last_low_confirmation_bar"] = low_hits[-1] if low_hits else None
        else:
            row["swing_last_high_price"] = None
            row["swing_last_high_confirmation_bar"] = None
            row["swing_last_low_price"] = None
            row["swing_last_low_confirmation_bar"] = "NOT_CONFIGURED"
        if struct is not None:
            row["structure_state_after"] = str(struct["structure_state_after"].iloc[i])
            events_upto = struct["structural_break_event"].to_numpy()[: i + 1]
            hits = [int(x) for x in range(len(events_upto)) if str(events_upto[x]) != "NONE"]
            row["last_break_event"] = str(events_upto[hits[-1]]) if hits else "NONE"
            row["last_break_bar"] = hits[-1] if hits else None
        else:
            row["structure_state_after"] = "NOT_CONFIGURED"
            row["last_break_event"] = "NOT_CONFIGURED"
            row["last_break_bar"] = None
        if liq is not None:
            row["liquidity_nearest_level_id"] = _num(liq["nearest_prior_same_side_level_id"].iloc[i])
            row["liquidity_nearest_distance_fraction"] = _num(liq["nearest_same_side_distance_fraction"].iloc[i])
            row["liquidity_nearest_distance_percentile"] = _num(liq["nearest_distance_percentile"].iloc[i])
            row["liquidity_known_high_levels"] = int(liq["known_high_side_level_count"].iloc[i])
            row["liquidity_known_low_levels"] = int(liq["known_low_side_level_count"].iloc[i])
            for ev in ("touch", "wick_only", "close_breach", "reclaim"):
                row[f"liquidity_high_{ev}_cum"] = int(liq[f"high_side_first_{ev}_count"].iloc[i]) if f"high_side_first_{ev}_count" in liq.columns else None
                row[f"liquidity_low_{ev}_cum"] = int(liq[f"low_side_first_{ev}_count"].iloc[i]) if f"low_side_first_{ev}_count" in liq.columns else None
        else:
            row["liquidity_nearest_level_id"] = "NOT_CONFIGURED"
            row["liquidity_known_high_levels"] = "NOT_CONFIGURED"
            row["liquidity_known_low_levels"] = "NOT_CONFIGURED"
        if ob_state is not None:
            row["ob_active_ids"] = "|".join(_active_ids(ob_events, i, "zone_id", _OB_TERMINAL))
            row["ob_last_created_id"] = _num(_ffill_value(ob_state["created_ob_zone_id"], i))
            row["ob_last_created_direction"] = _ffill_value(ob_state["created_ob_direction"], i)
        else:
            row["ob_active_ids"] = "NOT_CONFIGURED"
            row["ob_last_created_id"] = "NOT_CONFIGURED"
            row["ob_last_created_direction"] = "NOT_CONFIGURED"
        if fvg_state is not None:
            row["fvg_active_ids"] = "|".join(_active_ids(fvg_events, i, "fvg_id", _FVG_TERMINAL))
            row["fvg_last_created_id"] = _num(_ffill_value(fvg_state["created_fvg_id"], i))
            row["fvg_last_created_direction"] = _ffill_value(fvg_state["created_fvg_direction"], i)
        else:
            row["fvg_active_ids"] = "NOT_CONFIGURED"
            row["fvg_last_created_id"] = "NOT_CONFIGURED"
            row["fvg_last_created_direction"] = "NOT_CONFIGURED"
        if dr is not None:
            row["dealing_range_id"] = _num(_ffill_value(dr["created_range_id"], i))
            row["dealing_range_direction"] = _ffill_value(dr["created_range_direction"], i)
            row["dealing_range_high"] = _num(dr["current_range_high"].iloc[i]) if "current_range_high" in dr.columns else None
            row["dealing_range_low"] = _num(dr["current_range_low"].iloc[i]) if "current_range_low" in dr.columns else None
            row["dealing_range_position_raw"] = _num(dr["current_range_position_raw"].iloc[i]) if "current_range_position_raw" in dr.columns else None
        else:
            row["dealing_range_id"] = "NOT_CONFIGURED"
            row["dealing_range_direction"] = "NOT_CONFIGURED"
        fp = engine_out["flow_proxy"]
        row["proxy_volume_pressure_proxy"] = _num(fp["volume_pressure_proxy"].iloc[i])
        row["proxy_pressure_proxy_percentile"] = _num(fp["pressure_proxy_percentile"].iloc[i])
        row["proxy_pressure_magnitude"] = _num(fp["pressure_magnitude"].iloc[i])
        fa = engine_out["flow_actual"]
        row["actual_delta_ratio"] = _num(fa["delta_ratio"].iloc[i])
        row["actual_delta_ratio_percentile"] = _num(fa["delta_ratio_percentile"].iloc[i])
        row["actual_buy_volume"] = _num(fa["buy_volume"].iloc[i])
        row["actual_sell_volume"] = _num(fa["sell_volume"].iloc[i])
        row["actual_volume"] = _num(fa["volume"].iloc[i])
        ev_row = evidence_df.iloc[i]
        ev_vals = "|".join(f"{c}={ev_row[c]}" for c in evidence_df.columns)
        row["evidence_row_sha256"] = hashlib.sha256(ev_vals.encode()).hexdigest()
        row["evidence_columns_count"] = int(len(evidence_df.columns))
        created_so_far = ledger[ledger["event_position"] <= i] if len(ledger) else ledger
        row["hypotheses_created_so_far"] = int(
            (created_so_far["ledger_event_type"] == "CREATED").sum()
        ) if len(created_so_far) else 0
        state_counts = {}
        if len(ledger):
            for hid, group in ledger[ledger["event_position"] <= i].groupby("hypothesis_id"):
                last_state = str(group.sort_values(["event_position", "serialization_order"]).iloc[-1]["new_state"])
                state_counts[last_state] = state_counts.get(last_state, 0) + 1
        row["hypotheses_state_counts_asof"] = json.dumps(state_counts, sort_keys=True)
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame.attrs["sample_manifest"] = sample_meta
    frame.attrs["leakage_contract"] = (
        "DECISION-SIDE ONLY: every fact is a slice of the CLOSED engines' causal "
        "outputs at the sample position (their zero-lookahead contract) or an "
        "as-of prefix over those outputs. No forward fact appears in this file."
    )
    return frame


def _num(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            return str(value)
    return value


# --------------------------------------------------------------------------------------
# C) DETECTION_ENTITIES exports
# --------------------------------------------------------------------------------------

def build_entity_exports(*, engine_out) -> dict:
    exports = {}
    if engine_out.get("swings") is not None:
        s = engine_out["swings"]
        cols = [c for c in s.columns if c.startswith("swing_")]
        exports["entities_swings.csv"] = s.loc[s["swing_high_confirmed"].astype(bool) | s["swing_low_confirmed"].astype(bool), cols]
    if engine_out.get("structure_breaks") is not None:
        st = engine_out["structure_breaks"]
        ev = st[st["structural_break_event"].astype(str) != "NONE"]
        exports["entities_structure_events.csv"] = ev
    if engine_out.get("liquidity_levels") is not None:
        ll = engine_out["liquidity_levels"]
        exports["entities_liquidity_levels.csv"] = ll.loc[ll["liquidity_level_created"].astype(bool)]
        exports["entities_liquidity_events.csv"] = engine_out["liquidity_events"]
    if engine_out.get("order_blocks") is not None:
        ob = engine_out["order_blocks"]
        exports["entities_order_blocks.csv"] = ob.loc[ob["ob_candidate_created"].astype(bool)]
        exports["entities_order_blocks_events.csv"] = engine_out["order_block_events"]
    if engine_out.get("fvg") is not None:
        f = engine_out["fvg"]
        exports["entities_fvg.csv"] = f.loc[f["fvg_candidate_created"].astype(bool)]
        exports["entities_fvg_events.csv"] = engine_out["fvg_events"]
    if engine_out.get("dealing_ranges") is not None:
        dr = engine_out["dealing_ranges"]
        exports["entities_dealing_ranges.csv"] = dr.loc[dr["dealing_range_created"].astype(bool)]
        exports["entities_dealing_ranges_events.csv"] = engine_out["dealing_range_events"]
    return exports


# --------------------------------------------------------------------------------------
# D) OUTCOME_FILM_SAMPLE.csv — SEPARATE outcome-side view for sample timestamps only
# --------------------------------------------------------------------------------------

def build_outcome_film(
    *,
    market_history,
    timeline,
    adapter,
    engine_out,
    evidence_actual,
    narrative_actual,
    sample_positions: tuple,
    sample_meta: dict,
    timeline_id: str,
) -> pd.DataFrame:
    from trading_system.research.information_time import InformationPhase
    from trading_system.research.visibility import (
        AsOfVisibilityProjector,
        FrozenDecisionSnapshotBundle,
        ProjectionContract,
    )
    from trading_system.research.dataset_contracts import freeze_creation_feature_snapshot
    from trading_system.research.trajectory.trajectory_contract import (
        anchor_decision,
        bind_interval,
    )
    from trading_system.research.trajectory.trajectory_stage2 import (
        build_price_trajectory,
        build_structure_trajectory,
    )

    narrative = narrative_actual["narrative"]
    ledger = narrative.hypothesis_ledger
    n = len(market_history)
    rows = []
    contract_cache: dict = {}

    # Precompute contract trajectories for hypotheses CREATED at sampled
    # positions only (the film is restricted to the frozen sample timestamps).
    sampled = set(int(p) for p in sample_positions)
    created_at = {}
    if len(ledger):
        for _, ev in ledger[ledger["ledger_event_type"] == "CREATED"].iterrows():
            created_at.setdefault(int(ev["event_position"]), []).append(int(ev["hypothesis_id"]))

    bundle = FrozenDecisionSnapshotBundle(
        timeline_id=timeline_id,
        evidence_df=evidence_actual["evidence_df"],
        feature_manifest=evidence_actual["feature_manifest"],
        narrative_surface=narrative.narrative_surface,
        observation_ledger=narrative.observation_ledger,
        hypothesis_ledger=narrative.hypothesis_ledger,
        relationship_ledger=narrative.relationship_ledger,
        relationship_sources=narrative.relationship_sources,
        narrative_manifest=narrative.narrative_manifest,
        market_frame=market_history,
    )
    projector = AsOfVisibilityProjector(adapter=adapter, contract=ProjectionContract())

    for position in sorted(sampled):
        hids = created_at.get(position, [])
        for hid in hids:
            try:
                key = adapter.key_for_position(
                    market_history.index, position, InformationPhase.COMPLETED_ROW_AVAILABLE,
                    ProjectionContract().analytical_batch_sequence,
                )
                visible = projector.project(bundle, key)
                frozen = freeze_creation_feature_snapshot(visible, hypothesis_id=hid, adapter=adapter)
                anchor = anchor_decision(timeline=timeline, frozen=frozen)
                end_key = adapter.key_for_position(
                    market_history.index, len(market_history) - 1,
                    InformationPhase.COMPLETED_ROW_AVAILABLE,
                    ProjectionContract().analytical_batch_sequence,
                )
                interval = bind_interval(
                    timeline=timeline, anchor=anchor, adapter=adapter,
                    market_history=market_history, end_inclusive=end_key,
                )
                price = build_price_trajectory(
                    timeline=timeline, anchor=anchor, adapter=adapter,
                    market_history=market_history, interval=interval,
                )
                contract_cache[(position, hid)] = (frozen, anchor, price)
            except Exception as exc:  # declared, never hidden
                contract_cache[(position, hid)] = exc

    for rank, i in enumerate(sample_positions):
        forward = market_history.iloc[i + 1 :]
        base = {
            "film_row_kind": "SAMPLE_FORWARD_PATH",
            "sample_rank": rank,
            "sample_position": i,
            "timestamp_utc": str(market_history.index[i]),
            "reference_close": float(market_history["close"].iloc[i]),
            "forward_bars_observed": int(len(forward)),
            "forward_max_high": float(forward["high"].max()) if len(forward) else None,
            "forward_max_high_bar_offset": int(forward["high"].values.argmax()) + 1 if len(forward) else None,
            "forward_min_low": float(forward["low"].min()) if len(forward) else None,
            "forward_min_low_bar_offset": int(forward["low"].values.argmin()) + 1 if len(forward) else None,
            "forward_close_at_data_end": float(forward["close"].iloc[-1]) if len(forward) else None,
            "terminal_status": "RIGHT_CENSORED_AT_DATA_END",
            "terminal_status_note": "no mature outcome definition for a bare review timestamp; closed 6.2A-1 maturity applies to hypothesis lifecycles",
            "contract_excursion_available": "NO_HYPOTHESIS_ANCHOR_AT_SAMPLE_TIMESTAMP",
            "hypothesis_id": None,
            "running_favorable_excursion": None,
            "running_adverse_excursion": None,
            "close_displacement_final": None,
            "favorable_extreme_position": None,
            "adverse_extreme_position": None,
            "same_bar_ambiguous_count": None,
            "raw_facts_label": "RAW_FORWARD_PATH_FACTS_NOT_CONTRACT_TRAJECTORY",
            "outcome_injection_guard": "OUTCOME_FILM_SEPARATE_FILE_NOT_IN_DECISION_SNAPSHOT",
        }
        if not len(forward):
            base["terminal_status"] = "NO_FORWARD_BARS_SAMPLE_AT_DATA_END"
        rows.append(base)

        for hid in hids:
            entry = contract_cache.get((position, hid))
            hyp_row = {
                "film_row_kind": "HYPOTHESIS_CONTRACT_TRAJECTORY",
                "sample_rank": rank,
                "sample_position": i,
                "timestamp_utc": str(market_history.index[i]),
                "reference_close": float(market_history["close"].iloc[i]),
                "hypothesis_id": hid,
                "raw_facts_label": "CONTRACT_TRAJECTORY_CLOSED_STAGE2",
                "outcome_injection_guard": "OUTCOME_FILM_SEPARATE_FILE_NOT_IN_DECISION_SNAPSHOT",
            }
            if isinstance(entry, tuple):
                frozen, anchor, price = entry
                last = price.points[-1] if price.points else None
                hyp_row.update({
                    "contract_excursion_available": "YES_CLOSED_STAGE2_PRICE_TRAJECTORY",
                    "hypothesis_direction": frozen.direction,
                    "forward_bars_observed": int(len(price.points)),
                    "running_favorable_excursion": float(price.running_favorable_final),
                    "running_adverse_excursion": float(price.running_adverse_final),
                    "close_displacement_final": float(last.close_displacement) if last else None,
                    "favorable_extreme_position": int(last.favorable_extreme_position) if last and last.favorable_extreme_position is not None else None,
                    "adverse_extreme_position": int(last.adverse_extreme_position) if last and last.adverse_extreme_position is not None else None,
                    "same_bar_ambiguous_count": int(price.same_bar_ambiguous_count),
                    "terminal_status": "RIGHT_CENSORED_AT_DATA_END",
                    "terminal_status_note": "closed Stage-2 path over (decision, data_end]; mature terminal needs hypothesis outcome maturity rules",
                })
            else:
                hyp_row.update({
                    "contract_excursion_available": f"NOT_AVAILABLE:{type(entry).__name__ if entry is not None else 'UNKNOWN'}",
                    "running_favorable_excursion": None,
                    "running_adverse_excursion": None,
                })
            rows.append(hyp_row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Visual audit support: chart_overlay.csv (per-minute chart-ready rows)
# --------------------------------------------------------------------------------------

def build_chart_overlay(*, market_history, engine_out) -> pd.DataFrame:
    n = len(market_history)
    frame = pd.DataFrame(index=market_history.index)
    frame.insert(0, "timestamp_utc", [str(ts) for ts in market_history.index])
    for col in ("open", "high", "low", "close"):
        frame[col] = market_history[col].values
    swings = engine_out.get("swings")
    if swings is not None:
        frame["confirmed_swing_high_marker"] = swings["swing_high_confirmed"].values
        frame["confirmed_swing_low_marker"] = swings["swing_low_confirmed"].values
        frame["swing_price"] = swings["swing_price"].values
        frame["swing_confirmation_position"] = swings["swing_confirmation_position"].values
    else:
        frame["confirmed_swing_high_marker"] = "NOT_CONFIGURED"
        frame["confirmed_swing_low_marker"] = "NOT_CONFIGURED"
    if engine_out.get("structure_breaks") is not None:
        st = engine_out["structure_breaks"]
        frame["structure_state"] = st["structure_state_after"].values
        frame["bos_choch_marker"] = st["structural_break_event"].values
    else:
        frame["structure_state"] = "NOT_CONFIGURED"
        frame["bos_choch_marker"] = "NOT_CONFIGURED"
    if engine_out.get("liquidity_levels") is not None:
        ll = engine_out["liquidity_levels"]
        frame["liquidity_level_created_marker"] = ll["liquidity_level_created"].values
        frame["liquidity_created_level_id"] = ll["created_level_id"].values
        frame["liquidity_created_level_price"] = ll["created_level_price"].values
        frame["liquidity_known_high_levels"] = ll["known_high_side_level_count"].values
        frame["liquidity_known_low_levels"] = ll["known_low_side_level_count"].values
    if engine_out.get("fvg") is not None:
        f = engine_out["fvg"]
        frame["fvg_created_marker"] = f["fvg_candidate_created"].values
        frame["fvg_created_id"] = f["created_fvg_id"].values
        frame["fvg_created_state"] = f["created_fvg_direction"].values
    if engine_out.get("order_blocks") is not None:
        ob = engine_out["order_blocks"]
        frame["ob_created_marker"] = ob["ob_candidate_created"].values
        frame["ob_created_id"] = ob["created_ob_zone_id"].values
        frame["ob_created_state"] = ob["created_ob_direction"].values
    if engine_out.get("dealing_ranges") is not None:
        dr = engine_out["dealing_ranges"]
        frame["dealing_range_created_marker"] = dr["dealing_range_created"].values
        frame["dealing_range_id"] = dr["created_range_id"].values
        frame["dealing_range_state"] = dr["created_range_direction"].values
    return frame.reset_index(drop=True)


# --------------------------------------------------------------------------------------
# Reality check PREVIEW: descriptive statistics ONLY (no thresholds, no selection)
# --------------------------------------------------------------------------------------

def reality_preview(*, market_history, engine_out, narrative_actual, film_df) -> dict:
    n = len(market_history)

    def lifecycle(events: pd.DataFrame, id_col: str, created_col: str, created_frame_col: str,
                  state_frame: pd.DataFrame, position_col: str) -> dict:
        out = {"status": "NOT_CONFIGURED"}
        if state_frame is None:
            return out
        created = state_frame.loc[state_frame[created_frame_col].astype(bool)]
        events_by_id: dict = {}
        if events is not None and len(events) and "event_position" in events.columns:
            for cid, group in events.groupby(id_col):
                events_by_id[cid] = group["event_position"].to_numpy()
        durations = []
        censored = 0
        for _, row in created.iterrows():
            cid = row[created_col]
            if position_col not in row or pd.isna(row[position_col]):
                continue
            start = int(row[position_col])
            closed = False
            end = n
            positions = events_by_id.get(cid)
            if positions is not None:
                later = positions[positions > start]
                if len(later):
                    closed = True
                    end = int(later[-1])
            if not closed:
                censored += 1
            durations.append(end - start)
        if durations:
            s = pd.Series(durations)
            out = {
                "status": "RAN",
                "entity_count": int(len(durations)),
                "duration_bars_mean": float(s.mean()),
                "duration_bars_median": float(s.median()),
                "duration_bars_p25": float(s.quantile(0.25)),
                "duration_bars_p75": float(s.quantile(0.75)),
                "open_at_data_end_count": int(censored),
                "duration_note": "bars from creation to last terminal event, else to data end (censored)",
            }
        return out

    ledger = narrative_actual["narrative"].hypothesis_ledger
    states = {}
    if len(ledger):
        for hid, group in ledger.groupby("hypothesis_id"):
            last_state = str(group.sort_values(["event_position", "serialization_order"]).iloc[-1]["new_state"])
            states[last_state] = states.get(last_state, 0) + 1
    excursion = {"status": "NOT_CONFIGURED"}
    contract_rows = film_df[film_df["film_row_kind"] == "HYPOTHESIS_CONTRACT_TRAJECTORY"] if len(film_df) else film_df
    avail = contract_rows[contract_rows.get("running_favorable_excursion", pd.Series(dtype=float)).notna()] if len(contract_rows) else contract_rows
    if len(avail) and "running_favorable_excursion" in avail.columns:
        excursion = {
            "status": "RAN_SAMPLED_HYPOTHESIS_ANCHORS_ONLY",
            "rows": int(len(avail)),
            "running_favorable_final_mean": float(avail["running_favorable_excursion"].mean()),
            "running_favorable_final_median": float(avail["running_favorable_excursion"].median()),
            "running_adverse_final_mean": float(avail["running_adverse_excursion"].mean()),
            "running_adverse_final_median": float(avail["running_adverse_excursion"].median()),
            "label": "CLOSED_STAGE2_RUNNING_EXCURSIONS_DESCRIBED_NOT_SELECTED",
        }
    return {
        "scope": "DESCRIPTIVE_ONLY_NO_INFORMATION_EDGE_CLAIM",
        "forbidden_absent": ["no_horizon_selection", "no_threshold_selection",
                             "no_combination_selection", "no_strategy_optimization",
                             "no_profitability_claim"],
        "coverage": {
            "timeline_bars": n,
            "timeline_start": str(market_history.index[0]),
            "timeline_end": str(market_history.index[-1]),
        },
        "entity_frequencies_per_1000_bars": {
            "confirmed_swings": _freq(engine_out, "swings", "swing_high_confirmed", n),
            "fvg_candidates": _freq(engine_out, "fvg", "fvg_candidate_created", n),
            "ob_candidates": _freq(engine_out, "order_blocks", "ob_candidate_created", n),
            "liquidity_levels": _freq(engine_out, "liquidity_levels", "liquidity_level_created", n),
            "dealing_ranges": _freq(engine_out, "dealing_ranges", "dealing_range_created", n),
        },
        "lifecycle_durations_bars": {
            "fvg": lifecycle(engine_out.get("fvg_events"), "fvg_id", "created_fvg_id", "fvg_candidate_created", engine_out.get("fvg"), "created_fvg_creation_position"),
            "order_blocks": lifecycle(engine_out.get("order_block_events"), "zone_id", "created_ob_zone_id", "ob_candidate_created", engine_out.get("order_blocks"), "created_ob_creation_position"),
            "dealing_ranges": lifecycle(engine_out.get("dealing_range_events"), "range_id", "created_range_id", "dealing_range_created", engine_out.get("dealing_ranges"), "created_range_creation_position"),
        },
        "excursion_distributions": excursion,
        "hypothesis_outcome_factual_distributions": {
            "state_counts_at_data_end": states,
            "terms": "CLOSED 6.1B literal states only (MONITORING / OBSERVED_DIRECTION_ESTABLISHED / CONTRADICTED / SUPERSEDED); no WIN/LOSS/PnL",
            "censoring_rate_note": "MONITORING at data end = still open under the closed lifecycle; not a loss and not a win",
        },
    }


def _freq(engine_out, key, col, n):
    frame = engine_out.get(key)
    if frame is None or col not in frame.columns:
        return None
    return round(float(frame[col].astype(bool).sum()) * 1000.0 / max(n, 1), 4)


# --------------------------------------------------------------------------------------
# A) SUMMARY.json + F) MACHINE_VALIDATION.json + E) README_RESULT_AR.txt
# --------------------------------------------------------------------------------------

def build_summary(*, config, source_info, timeline, engine_out, statuses, evidence_results,
                  narrative_actual, sample_meta, preview, minute_count, kline_info) -> dict:
    ledger = narrative_actual["narrative"].hypothesis_ledger
    hyp_states = {}
    if len(ledger):
        for hid, group in ledger.groupby("hypothesis_id"):
            last_state = str(group.sort_values(["event_position", "serialization_order"]).iloc[-1]["new_state"])
            hyp_states[last_state] = hyp_states.get(last_state, 0) + 1
    status_counts = {}
    for s in statuses:
        status_counts[s.status] = status_counts.get(s.status, 0) + 1

    def cnt(key, col):
        frame = engine_out.get(key)
        if frame is None or col not in frame.columns:
            return None
        return int(frame[col].astype(bool).sum())

    return {
        "report": "BTC_MAY_2026_FIELD_REPORT",
        "status": "FIELD_RUN_OUTPUT",
        "detector_validity_notice": DETECTOR_VALIDITY_NOTICE,
        "tie_order_contract": "NOT_PROVEN",
        "actual_means": ACTUAL_MEANS,
        "source_identity": source_info,
        "kline_identity": kline_info,
        "minute_facts_count": minute_count,
        "timeline": {
            "timeline_id": timeline.timeline_id,
            "timeline_hash": timeline.timeline_hash,
            "bar_count": timeline.bar_count,
        },
        "sample_selection": sample_meta,
        "counts": {
            "volatility_rows": int(len(engine_out["volatility"])),
            "volatility_states": None,
            "session_rows": int(len(engine_out["sessions"])),
            "session_schedules_configured": status_detail(statuses, "session_context_1_2"),
            "confirmed_swings_high": cnt("swings", "swing_high_confirmed"),
            "confirmed_swings_low": cnt("swings", "swing_low_confirmed"),
            "confirmed_swings_total": (
                None if cnt("swings", "swing_high_confirmed") is None
                else cnt("swings", "swing_high_confirmed") + cnt("swings", "swing_low_confirmed")
            ),
            "sequence_events_HH_HL_LH_LL": (
                engine_out["swing_sequence"]["swing_sequence_class"].astype(str).value_counts().to_dict()
                if "swing_sequence" in engine_out else None
            ),
            "structure_events_BOS_CHOCH": (
                engine_out["structure_breaks"]["structural_break_event"].astype(str).value_counts().to_dict()
                if "structure_breaks" in engine_out else None
            ),
            "liquidity_levels": cnt("liquidity_levels", "liquidity_level_created"),
            "liquidity_events_by_type": (
                engine_out["liquidity_events"]["event_type"].astype(str).value_counts().to_dict()
                if len(engine_out.get("liquidity_events", [])) else {}
            ),
            "order_block_candidates": cnt("order_blocks", "ob_candidate_created"),
            "fvg_entities": cnt("fvg", "fvg_candidate_created"),
            "dealing_ranges": cnt("dealing_ranges", "dealing_range_created"),
            "evidence_vectors_actual_rows": int(len(evidence_results["actual"]["evidence_df"])),
            "evidence_vectors_proxy_rows": int(len(evidence_results["proxy"]["evidence_df"])),
            "hypotheses_created": int(sum(1 for _, g in (ledger.groupby("hypothesis_id") if len(ledger) else []) )),
            "hypotheses_state_counts_at_data_end": hyp_states,
        },
        "flow_summaries_SEPARATE_NEVER_MERGED": {
            "PROXY_ohlcV_proxy": {
                "label": "OHLCV_PROXY (stays PROXY)",
                "mean_volume_pressure_proxy": _mean(engine_out["flow_proxy"], "volume_pressure_proxy"),
                "rows": int(len(engine_out["flow_proxy"])),
            },
            "ACTUAL_executed_initiated": {
                "label": "EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT",
                "semantic_scope": ACTUAL_MEANS,
                "total_buy_volume": _sum(engine_out["flow_actual"], "buy_volume"),
                "total_sell_volume": _sum(engine_out["flow_actual"], "sell_volume"),
                "total_volume": _sum(engine_out["flow_actual"], "volume"),
                "mean_delta_ratio": _mean(engine_out["flow_actual"], "delta_ratio"),
                "rows": int(len(engine_out["flow_actual"])),
            },
        },
        "branch_statuses": {s.name: {"status": s.status, "detail": s.detail} for s in statuses},
        "status_counts": status_counts,
        "not_configured_items": [s.name for s in statuses if s.status != "RAN"],
        "reality_check_preview": preview,
    }


def status_detail(statuses, name):
    for s in statuses:
        if s.name == name:
            return s.detail
    return ""


def _mean(frame, col):
    return float(pd.to_numeric(frame[col], errors="coerce").mean())


def _sum(frame, col):
    return float(pd.to_numeric(frame[col], errors="coerce").sum())


def build_machine_validation(*, runner_files, config, source_paths_and_hashes, engine_modules,
                             output_paths, statuses, started_at, failures, warnings, manifest_result,
                             adapter_identity) -> dict:
    import resource

    try:
        peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = f"{peak_kib} KiB (ru_maxrss)"
    except Exception:
        peak = "NOT_AVAILABLE"
    return {
        "runner_version": "BTC_MAY2026_FIELD_RUNNER_V1",
        "runner_status": "IMPLEMENTED_PENDING_OWNER_RUN",
        "runner_files_sha256": runner_files,
        "config_used": {
            "swing_quantile": config.swing_quantile,
            "swing_prior_continuation_reversals": list(config.swing_prior_continuation_reversals),
            "swing_prior_confirmed_reversals": list(config.swing_prior_confirmed_reversals),
            "sessions": config.sessions,
            "sample_size": config.sample_size,
            "htf_durations": list(config.htf_durations),
            "symbol": config.symbol,
            "year_month": config.year_month,
            "parameter_status": "EXPLICIT_OWNER_PARAMETERS_NOT_SACRED",
        },
        "project_manifest_validation": manifest_result,
        "source_adapter_closure_identity": adapter_identity,
        "inputs_sha256": source_paths_and_hashes,
        "outputs_sha256": output_paths,
        "engines_used": engine_modules,
        "failures": failures,
        "warnings": warnings,
        "runtime_seconds": round(time.time() - started_at, 3),
        "peak_memory": peak,
        "volatile_keys": ["runtime_seconds", "peak_memory"],
    }


def write_readme_ar(path: str, *, summary: dict, machine: dict, out_names: list) -> None:
    not_conf = summary.get("not_configured_items", [])
    counts = summary.get("counts", {})
    text = f"""تقرير تشغيل ميداني — BTCUSDT — شهر 2026-05
================================================

1) ماذا شغّلنا؟
شغّلنا المحركات المغلقة الموجودة في المشروع كما هي، عبر واجهاتها العامة فقط، على
بيانات الدقيقة الرسمية + كنائن Binance الرسمية (1m) لشهر مايو 2026.

- المصادر (Binance Source Adapter V1 المغلق): تحقّق كامل + مطابقة exact cross-witness.
- الـOHLC المعتمد (canonical) = كنائن Binance المنشورة حصراً.
- عقد الترتيب: TIE_ORDER_CONTRACT = NOT_PROVEN — الدقيقة المبهمة تبقى مبهمة.
- التدفق المنفّذ/initiated يُحسب منفصلًا: EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT.
  معناه هنا فقط: حساب الجهة المُنفِّذة كما تنشره Binance Spot لهذا المصدر.
  لا يعني: ضغط شراء، ولا حقيقة دفتر الأوامر، ولا نشاط مؤسسات، ولا حيتان، ولا تدفق السوق كله.
- PROXY (من OHLCV) و ACTUAL (من التدفق المنفّذ) لا يُجمعان في رقم واحد أبداً.

الأعداد المهمة:
- عدد دقائق الحقائق: {counts.get("minute_facts_count", "?")}
- عدد أعمدة الـtimeline: {summary.get("timeline", {}).get("bar_count", "?")}
- التأكيدات: swings مرتفعة = {counts.get("confirmed_swings_high")} / منخفضة = {counts.get("confirmed_swings_low")}
- أحداث البنية BOS/CHoCH: {counts.get("structure_events_BOS_CHOCH")}
- مستويات السيولة: {counts.get("liquidity_levels")}
- كتل الأوامر (OB): {counts.get("order_block_candidates")}
- الفجوات (FVG): {counts.get("fvg_entities")}
- النطاقات (dealing ranges): {counts.get("dealing_ranges")}
- الفرضيات المُنشأة: {counts.get("hypotheses_created")} — حالاتها عند نهاية البيانات: {counts.get("hypotheses_state_counts_at_data_end")}

2) ماذا لم نستطع تشغيله؟
العناصر المُعلَّنة غير المُهيّأة في هذا التشغيل (NOT_CONFIGURED / NOT_AVAILABLE):
{json.dumps(not_conf, ensure_ascii=False, indent=1)}

خصوصاً: سياسة تأكيد الـSwings تحتاج رقم quantile مُعايَراً — لم يُختلق أي قيمة افتراضية.
إن أردت تفعيل فرع الـSwings كاملاً: عدّل ملف الإعدادات وأعطِ swing_quantile قيمة
صريحة منك (تُسجَّل كمعامل مالك، غير مُقدَّس)، ويمكنك أيضاً تزويد swing_prior_*.

3) ماذا تعني الأعداد؟
كل عدد هو عدد صفوف/أحداث أخرجها كاشف معيَّن من كاشفات المشروع المغلقة على هذه
البيانات. الكاشف = تعريف تشغيلي للمشروع (تعريفه المُصدَّق داخل الكود المغلق)، وليس
"الحقيقة السوقية الوحيدة". لا نقول "الـFVG يعمل" أو "يفشل" — بل: نسخة الكاشف X تحت
هذا التشغيل أنتجت هذه الكيانات.

4) ما الذي لا تُثبته؟
- لا تُثبّت أي أفضلية تنبؤية (Information Edge) إطلاقاً.
- لا تُثبّت ربحية، ولا استراتيجية، ولا إشارات تداول، ولا احتمالات.
- إحصاءات الواقع هنا وصفية فقط: تغطية، تكرارات، أعمار كيانات، توزيعات رحلات سعرية
  موجودة في عقود trajectory المغلقة، ونسب الرصد/الإغلاق (censoring).
- لا اختيار أفضل horizon ولا أفضل threshold.
- ACTUAL هنا ليس ضغط شراء ولا حقيقة دفتر أوامر.
- الأصل التاريخي المُولِّد للبيانات: NOT_CERTIFIED خارج ملفات المصدر المُربوطة بالبصمات.

5) أين ملفات الرسم والفحص؟
- ملفات الكيانات (لرسمها على الشارت لاحقاً): entities_*.csv
- طبقة الرسم الجاهزة (لكل دقيقة): chart_overlay.csv
- لقطة القرار (ما كان متاحاً وقتها فقط): DETECTION_AUDIT.csv
- شريط ما حدث لاحقاً (منفصل عن القرار): OUTCOME_FILM_SAMPLE.csv
- الملخص الآلي: SUMMARY.json
- تحقق الآلة: MACHINE_VALIDATION.json
- أسماء الكاشفات والإصدارات في: SUMMARY.json (branch_statuses + engines_used في machine)

تنبيه مهم: ملف DETECTION_AUDIT يحوي حقائق القرار فقط (بلا مستقبل)، وملف
OUTCOME_FILM_SAMPLE يحوي ما بعد اللحظة في ملف منفصل — ممنوع خلطهما.

تم التوليد آلياً بواسطة: BTC_MAY2026_FIELD_RUNNER_V1
"""
    open(path, "w", encoding="utf-8").write(text)

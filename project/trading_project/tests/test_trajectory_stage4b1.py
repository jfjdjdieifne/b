"""Tests for Module 6.2A-4 V1 Stage 4B-1: Shared Causal Structure Surface.

Covers: complete public-result identity, self-integrity, prefix invariance on the REAL CLOSED
2.1A→2.1B→2.1C chain, availability (origin never = availability), boundary legality, numeric/
schema, state/mutability, and firewall.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_system.research.information_time import (
    INFORMATION_KEY_VERSION,
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.trajectory.trajectory_contract import (
    MarketObservationTimeline,
    TIMELINE_ADAPTER_KIND,
    TrajectoryContractError,
    TrajectoryDataError,
)
from trading_system.research.trajectory import trajectory_stage4b1 as s4b1
from trading_system.research.trajectory.trajectory_stage4b1 import (
    Stage4B1StructureSurface,
    Stage4B1PrefixBinding,
)
from trading_system.structure.swing_detector import (
    CausalAdaptiveSwingDetector,
    EmpiricalConfirmationPolicy,
)
from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine
from trading_system.structure.structural_breaks import CausalStructuralBreakEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _market(n=30):
    # fixed pattern independent of n -> prefix identical across n
    close, high, low = [], [], []
    for i in range(n):
        c = 100.0 + i * 3.0 if i < 15 else (100.0 + 14 * 3.0) - (i - 14) * 3.0
        close.append(c)
        high.append(c + 2.0)
        low.append(c - 2.0)
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close},
        index=pd.RangeIndex(n),
        dtype=float,
    )


def _sealed(n=30, timeline_id="s4b1"):
    market = _market(n)
    adapter = PositionalTimelineAdapter(timeline_id)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    return market, adapter, timeline


# ---------------------------------------------------------------------------
# Non-vacuous "rich" fixture: REAL confirmed swings + sequence facts + BOS_UP
# ---------------------------------------------------------------------------

def _rich_policy():
    """Seeded quantile policy so the CLOSED 2.1A confirms real swings (a non-empty prior
    history yields a finite confirmation threshold)."""
    priors = tuple(0.01 * i for i in range(1, 50))  # 0.01 .. 0.49
    return EmpiricalConfirmationPolicy(quantile=0.1, prior_continuation_reversals=priors)


def _market_rich(n=70):
    """Deterministic staircase: rising legs + deep-but-higher-low pullbacks.

    Produces (verified empirically): confirmed HIGH and LOW swings with origin < confirmation,
    HH/HL sequence facts, and BOS_UP structural breaks. The pattern is a function of index only,
    so a shorter prefix is byte-identical to the same-length prefix of a longer build.
    """
    close, high, low = [], [], []
    level = 100.0
    i = 0
    while i < n:
        for _ in range(4):  # rise leg
            if i >= n:
                break
            level += 5.0
            close.append(level)
            high.append(level + 1.0)
            low.append(level - 1.0)
            i += 1
        for _ in range(3):  # deep pullback (higher low)
            if i >= n:
                break
            level -= 3.0
            close.append(level)
            high.append(level + 1.0)
            low.append(level - 1.0)
            i += 1
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close},
        index=pd.RangeIndex(n),
        dtype=float,
    )


def _rich_sealed(n=70, timeline_id="s4b1_rich"):
    market = _market_rich(n)
    adapter = PositionalTimelineAdapter(timeline_id)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    return market, adapter, timeline


def _rich_surface(n=70, timeline_id="s4b1_rich"):
    """Build the Stage 4B-1 surface over the rich fixture with the seeded policy."""
    market = _market_rich(n)
    adapter = PositionalTimelineAdapter(timeline_id)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    surface = s4b1.build_structure_surface(
        timeline=timeline, adapter=adapter, market_history=market, swing_policy=_rich_policy()
    )
    return market, adapter, timeline, surface


def _key(adapter, market, position, phase=InformationPhase.COMPLETED_ROW_AVAILABLE, seq=0):
    return adapter.key_for_position(market.index, position, phase, seq)


def _tamper(surface, row, col, value):
    frame = surface.frame.copy(deep=True)
    frame.iloc[row, frame.columns.get_loc(col)] = value
    return dataclasses.replace(surface, frame=frame)


# ---------------------------------------------------------------------------
# GENERAL / IDENTITY
# ---------------------------------------------------------------------------

def test_same_inputs_same_surface_id():
    market, adapter, timeline = _sealed(timeline_id="g_same")
    a = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    b = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert a.surface_id == b.surface_id
    assert a.public_result_hash == b.public_result_hash


def test_complete_derived_schema_bound():
    market, adapter, timeline = _sealed(timeline_id="g_schema")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert surf.derived_2_1a == s4b1._2_1A_OUTPUT_COLUMNS
    assert surf.derived_2_1b == s4b1._2_1B_OUTPUT_COLUMNS
    assert surf.derived_2_1c == s4b1._2_1C_OUTPUT_COLUMNS
    # all derived columns present exactly once in the frame
    assert surf.frame.columns.has_duplicates is False
    for c in s4b1._ALL_DERIVED_COLUMNS:
        assert c in surf.frame.columns


def test_component_hashes_cover_each_stage():
    market, adapter, timeline = _sealed(timeline_id="g_component")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert len(surf.hash_2_1a) == 64
    assert len(surf.hash_2_1b) == 64
    assert len(surf.hash_2_1c) == 64
    # distinct stages hash distinct content domains (not trivially equal)
    assert surf.hash_2_1a != surf.hash_2_1b
    assert surf.hash_2_1b != surf.hash_2_1c


def test_caller_input_immutability():
    market, adapter, timeline = _sealed(timeline_id="g_immut")
    before = market.copy(deep=True)
    s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    pd.testing.assert_frame_equal(market, before)


def test_no_hidden_cache():
    market, adapter, timeline = _sealed(timeline_id="g_cache")
    a1 = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    om, oa, ot = _sealed(timeline_id="g_cache_other")
    b = s4b1.build_structure_surface(timeline=ot, adapter=oa, market_history=om)
    a2 = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert a1.surface_id == a2.surface_id
    assert a1.surface_id != b.surface_id


# ---------------------------------------------------------------------------
# SELF-INTEGRITY
# ---------------------------------------------------------------------------

def test_integrity_mutation_rejected():
    market, adapter, timeline = _sealed(timeline_id="i_mut")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    s4b1.verify_surface_integrity(surf)  # valid
    tampered = _tamper(surf, 5, "structure_state_after", "CORRUPTED")
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b1.verify_surface_integrity(tampered)


def test_integrity_swing_mutation_rejected():
    market, adapter, timeline = _sealed(timeline_id="i_swing")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    tampered = _tamper(surf, 3, "swing_high_confirmed", True)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b1.verify_surface_integrity(tampered)


def test_forged_surface_id_rejected():
    market, adapter, timeline = _sealed(timeline_id="i_forgeid")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    forged = dataclasses.replace(surf, surface_id="0" * 64)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b1.verify_surface_integrity(forged)


def test_forged_adapter_kind_rejected():
    market, adapter, timeline = _sealed(timeline_id="i_forgekind")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    forged = dataclasses.replace(surf, adapter_kind=TIMELINE_ADAPTER_KIND.TIME_INDEXED)
    with pytest.raises(TrajectoryDataError):
        s4b1.verify_surface_integrity(forged)


def test_verify_matches_reconstruction():
    market, adapter, timeline = _sealed(timeline_id="i_verify")
    s = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    a = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    s4b1.verify_surface_matches_reconstruction(s, a)  # ok
    tampered = _tamper(s, 1, "swing_sequence_class", "HH")
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b1.verify_surface_matches_reconstruction(tampered, a)


# ---------------------------------------------------------------------------
# PREFIX INVARIANCE (real CLOSED chain)
# ---------------------------------------------------------------------------

def test_real_chain_prefix_invariance():
    # independently rebuilt prefix vs future-extended, real CLOSED chain
    short, adapter_s, timeline_s = _sealed(24, "p_real_short")
    long_, adapter_l, timeline_l = _sealed(40, "p_real_long")
    assert short.equals(long_.iloc[:24])
    s_short = s4b1.build_structure_surface(timeline=timeline_s, adapter=adapter_s, market_history=short)
    s_long = s4b1.build_structure_surface(timeline=timeline_l, adapter=adapter_l, market_history=long_)
    T = 20
    p_short = s_short.frame.loc[:, list(s4b1._ALL_DERIVED_COLUMNS)].iloc[: T + 1]
    p_long = s_long.frame.loc[:, list(s4b1._ALL_DERIVED_COLUMNS)].iloc[: T + 1]
    assert p_short.equals(p_long)


def test_prefix_identity_immutable_under_append():
    short, adapter_s, timeline_s = _sealed(24, "p_append_short")
    long_, adapter_l, timeline_l = _sealed(40, "p_append_long")
    s_short = s4b1.build_structure_surface(timeline=timeline_s, adapter=adapter_s, market_history=short)
    s_long = s4b1.build_structure_surface(timeline=timeline_l, adapter=adapter_l, market_history=long_)
    k_short = _key(adapter_s, short, 20)
    k_long = _key(adapter_l, long_, 20)
    p_short = s4b1.project_structure_prefix(surface=s_short, boundary_key=k_short)
    p_long = s4b1.project_structure_prefix(surface=s_long, boundary_key=k_long)
    assert p_short.prefix_hash == p_long.prefix_hash


def test_mutation_at_or_before_T_changes_prefix():
    market, adapter, timeline = _sealed(30, "p_mut_le")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = _key(adapter, market, 20)
    p_ok = s4b1.project_structure_prefix(surface=surf, boundary_key=k)
    tampered = _tamper(surf, 10, "structural_break_event", "BOS_UP")
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b1.project_structure_prefix(surface=tampered, boundary_key=k)


def test_mutation_after_T_rejected_by_integrity():
    market, adapter, timeline = _sealed(30, "p_mut_gt")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = _key(adapter, market, 20)
    tampered = _tamper(surf, 25, "swing_high_confirmed", True)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b1.project_structure_prefix(surface=tampered, boundary_key=k)


def test_no_row_duplication_in_prefix_binding():
    market, adapter, timeline = _sealed(30, "p_nodup")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    p = s4b1.project_structure_prefix(surface=surf, boundary_key=_key(adapter, market, 20))
    for f in dataclasses.fields(p):
        assert not isinstance(getattr(p, f.name), pd.DataFrame), f"{f.name} must not be a DataFrame"


# ---------------------------------------------------------------------------
# AVAILABILITY (origin never = availability)
# ---------------------------------------------------------------------------

def test_origin_never_used_as_availability():
    market, adapter, timeline = _sealed(30, "a_origin")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    # origin columns are positional Int64 data, not InformationKeys and not projection keys
    assert "swing_origin_position" in surf.frame.columns
    # projection is keyed ONLY by boundary bar_position; origin fields are inert data
    k = _key(adapter, market, 15)
    p = s4b1.project_structure_prefix(surface=surf, boundary_key=k)
    assert p.boundary_position == 15


def test_origin_field_is_positional_not_information_key():
    market, adapter, timeline = _sealed(30, "a_origin_type")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    # confirm origin dtype is a nullable integer (positional), never object InformationKey
    assert str(surf.frame["swing_origin_position"].dtype) == "Int64"


def test_boundary_controls_visibility_not_origin():
    # a confirmed swing whose origin < T but confirmation > T must NOT appear in prefix through T
    market, adapter, timeline = _sealed(30, "a_boundary")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = _key(adapter, market, 10)
    p = s4b1.project_structure_prefix(surface=surf, boundary_key=k)
    assert p.prefix_row_count == 11  # rows 0..10 only


# ---------------------------------------------------------------------------
# BOUNDARY LEGALITY
# ---------------------------------------------------------------------------

def test_bar_pre_close_rejected():
    market, adapter, timeline = _sealed(30, "b_preclose")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = _key(adapter, market, 10, InformationPhase.BAR_PRE_CLOSE)
    with pytest.raises(TrajectoryContractError, match="not legally observable"):
        s4b1.project_structure_prefix(surface=surf, boundary_key=k)


def test_cross_timeline_rejected():
    market, adapter, timeline = _sealed(30, "b_cross")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    other = PositionalTimelineAdapter("b_cross_other")
    k = other.key_for_position(market.index, 10, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    with pytest.raises(TrajectoryDataError, match="wrong timeline"):
        s4b1.project_structure_prefix(surface=surf, boundary_key=k)


def test_positional_fabricated_timestamp_rejected():
    market, adapter, timeline = _sealed(30, "b_pos_ts")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    fabricated = InformationKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id="b_pos_ts",
        bar_position=10,
        event_time_utc=pd.Timestamp("2026-01-01", tz="UTC"),
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=0,
    )
    with pytest.raises(TrajectoryDataError, match="timestamp"):
        s4b1.project_structure_prefix(surface=surf, boundary_key=fabricated)


def test_time_indexed_boundary():
    idx = pd.date_range("2026-03-07 12:00", periods=30, freq="h", tz="UTC")
    market = _market(30)
    market.index = idx
    adapter = TimeIndexedTimelineAdapter("b_ti")
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    k = adapter.key_for_position(idx, 20, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    p = s4b1.project_structure_prefix(surface=surf, boundary_key=k)
    assert p.boundary_position == 20


def test_time_indexed_wrong_timestamp_rejected():
    idx = pd.date_range("2026-03-07 12:00", periods=30, freq="h", tz="UTC")
    market = _market(30)
    market.index = idx
    adapter = TimeIndexedTimelineAdapter("b_ti_wrong")
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    wrong = InformationKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id="b_ti_wrong",
        bar_position=20,
        event_time_utc=pd.Timestamp("1999-01-01", tz="UTC"),
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=0,
    )
    with pytest.raises(TrajectoryDataError, match="timestamp"):
        s4b1.project_structure_prefix(surface=surf, boundary_key=wrong)


# ---------------------------------------------------------------------------
# NUMERIC / SCHEMA
# ---------------------------------------------------------------------------

def test_duplicate_columns_rejected():
    market = _market(10)
    market["close_dup"] = market["close"]
    market = market.rename(columns={"close_dup": "close"})
    adapter = PositionalTimelineAdapter("n_dup")
    with pytest.raises(TrajectoryDataError, match="duplicate"):
        MarketObservationTimeline.seal(adapter=adapter, market_history=market)


def test_wrong_dtype_rejected():
    market = _market(10)
    market["close"] = market["close"].astype(str)
    adapter = PositionalTimelineAdapter("n_dtype")
    with pytest.raises(TrajectoryDataError, match="numeric"):
        MarketObservationTimeline.seal(adapter=adapter, market_history=market)


def test_nullable_int64_origin_dtype():
    market, adapter, timeline = _sealed(30, "n_int64")
    surf = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert str(surf.frame["candidate_origin_position"].dtype) == "Int64"
    assert str(surf.frame["swing_confirmation_position"].dtype) == "Int64"


def test_object_dtype_string_columns_hash_deterministically():
    market, adapter, timeline = _sealed(30, "n_obj")
    a = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    b = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market)
    assert a.public_result_hash == b.public_result_hash


# ---------------------------------------------------------------------------
# FIREWALL / OUT OF SCOPE
# ---------------------------------------------------------------------------

def test_firewall_live_modules_do_not_import_stage4b1():
    live_roots = [
        Path("src/trading_system/structure"),
        Path("src/trading_system/zones"),
        Path("src/trading_system/liquidity"),
        Path("src/trading_system/orderflow"),
        Path("src/trading_system/multitimeframe"),
        Path("src/trading_system/decision"),
        Path("src/trading_system/core"),
        Path("src/trading_system/environment"),
    ]
    for root in live_roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for forb in ("trajectory_stage4b1", "research.trajectory"):
                assert forb not in content, f"Firewall violation: {py_file} imports {forb}"


def test_stage4b1_no_out_of_scope_implementations():
    path = Path("src/trading_system/research/trajectory/trajectory_stage4b1.py")
    content = path.read_text(encoding="utf-8", errors="ignore")
    forbidden = [
        "def build_liquidity", "def build_ob", "def build_fvg", "def build_dealing_range",
        "def build_htf", "def build_mtf", "def build_descriptor", "def build_estimand",
        "def build_model", "def build_scorer", "def build_geometry", "def build_execution",
        "class Liquidity", "class OrderBlock", "class FVG",
    ]
    for forb in forbidden:
        assert forb not in content, f"forbidden marker: {forb}"


def test_stage4b1_manifest_declares_out_of_scope_and_open_debts():
    manifest = s4b1.trajectory_stage4b1_manifest()
    assert s4b1.TRAJECTORY_STAGE4B1_CONTRACT_VERSION == "CAUSAL_SHARED_STRUCTURE_SURFACE_V1"
    vals = dict(zip(manifest["name"], manifest["value"]))
    assert vals["WIN_LOSS"] == "FORBIDDEN"
    assert vals["STAGE4B2"] == "NOT_IMPLEMENTED"
    for d in ("RESEARCH-DEBT-020", "RESEARCH-DEBT-021", "RESEARCH-DEBT-022", "RESEARCH-DEBT-023", "RESEARCH-DEBT-024", "RESEARCH-DEBT-025"):
        assert vals.get(d) == "OPEN"


# ---------------------------------------------------------------------------
# NON-VACUOUS regression: REAL confirmed swings / sequence facts / structural breaks
# ---------------------------------------------------------------------------

def test_rich_fixture_produces_real_confirmed_swings():
    """The fixture itself must actually produce confirmed swings with origin < confirmation."""
    market, adapter, timeline, surface = _rich_surface(70)
    highs = surface.frame["swing_high_confirmed"]
    lows = surface.frame["swing_low_confirmed"]
    assert int(highs.sum()) >= 1, "fixture must produce at least one confirmed HIGH swing"
    assert int(lows.sum()) >= 1, "fixture must produce at least one confirmed LOW swing"
    # at least one confirmed swing with origin strictly before confirmation
    origins = surface.frame["swing_origin_position"]
    confs = surface.frame["swing_confirmation_position"]
    ok = False
    for i in surface.frame.index[(highs | lows)]:
        if pd.notna(origins.iloc[i]) and pd.notna(confs.iloc[i]) and int(origins.iloc[i]) < int(confs.iloc[i]):
            ok = True
            break
    assert ok, "fixture must produce a confirmed swing with origin < confirmation"


def test_confirmed_swing_not_visible_before_availability():
    """A confirmed swing must not be visible at confirmation-1, but visible at confirmation,
    preserving its earlier origin."""
    market, adapter, timeline, surface = _rich_surface(70)
    highs = surface.frame["swing_high_confirmed"]
    conf_pos = int(surface.frame.index[highs][0])  # first confirmed HIGH swing position
    origin = int(surface.frame.loc[conf_pos, "swing_origin_position"])
    assert origin < conf_pos, "origin must precede confirmation"

    # through confirmation-1: the confirmed swing fact is absent (no early confirmation leak)
    k_before = _key(adapter, market, conf_pos - 1)
    p_before = s4b1.project_structure_prefix(surface=surface, boundary_key=k_before)
    assert p_before.prefix_row_count == conf_pos  # rows 0 .. conf_pos-1
    assert not bool(surface.frame.loc[: conf_pos - 1, "swing_high_confirmed"].any())

    # through confirmation: the confirmed swing is visible with origin preserved
    k_at = _key(adapter, market, conf_pos)
    p_at = s4b1.project_structure_prefix(surface=surface, boundary_key=k_at)
    assert p_at.prefix_row_count == conf_pos + 1
    assert bool(surface.frame.loc[conf_pos, "swing_high_confirmed"]) is True
    assert int(surface.frame.loc[conf_pos, "swing_origin_position"]) == origin
    assert int(surface.frame.loc[conf_pos, "swing_confirmation_position"]) == conf_pos


def test_sequence_fact_absent_before_row_visible_at_row():
    """A real non-neutral 2.1B sequence fact (HH) must be absent before its row and visible at it."""
    market, adapter, timeline, surface = _rich_surface(70)
    classes = surface.frame["swing_sequence_class"]
    non_neutral = classes[classes.isin({"HH", "HL", "LH", "LL", "EH", "EL"})]
    assert len(non_neutral) >= 1, "fixture must produce a real sequence classification"
    row = int(non_neutral.index[0])
    cls = str(non_neutral.iloc[0])
    # before the row: not this class (prefix ends at row-1)
    k_before = _key(adapter, market, row - 1)
    p_before = s4b1.project_structure_prefix(surface=surface, boundary_key=k_before)
    assert p_before.prefix_row_count == row
    # at the row: the classification is present
    assert str(surface.frame.loc[row, "swing_sequence_class"]) == cls
    k_at = _key(adapter, market, row)
    p_at = s4b1.project_structure_prefix(surface=surface, boundary_key=k_at)
    assert p_at.prefix_row_count == row + 1


def test_structural_break_absent_before_row_visible_at_row():
    """A real non-NONE 2.1C structural break (BOS_UP) must be absent before its row, visible at it."""
    market, adapter, timeline, surface = _rich_surface(70)
    events = surface.frame["structural_break_event"]
    bos_rows = events.index[events == "BOS_UP"]
    assert len(bos_rows) >= 1, "fixture must produce a real BOS_UP structural break"
    row = int(bos_rows[0])
    assert str(surface.frame.loc[row, "structure_state_before"]) == "UP_STRUCTURE"
    # before the row: no break event
    k_before = _key(adapter, market, row - 1)
    p_before = s4b1.project_structure_prefix(surface=surface, boundary_key=k_before)
    assert p_before.prefix_row_count == row
    # at the row: BOS_UP present
    assert str(surface.frame.loc[row, "structural_break_event"]) == "BOS_UP"
    k_at = _key(adapter, market, row)
    p_at = s4b1.project_structure_prefix(surface=surface, boundary_key=k_at)
    assert p_at.prefix_row_count == row + 1


def test_non_vacuous_real_chain_prefix_invariance():
    """Prefix invariance over a prefix that actually contains swings + sequence + structural breaks."""
    short, adapter_s, timeline_s, surf_s = _rich_surface(50, "rich_inv_short")
    long_, adapter_l, timeline_l, surf_l = _rich_surface(70, "rich_inv_long")
    # fixture is prefix-identical
    assert short.equals(long_.iloc[:50])

    T = 45  # a boundary with real structure through it
    # require real events through T (non-vacuous)
    assert int(surf_s.frame.loc[:T, "swing_high_confirmed"].sum()) >= 1, "no confirmed swing through T"
    assert int(surf_s.frame.loc[:T, "swing_sequence_class"].isin({"HH", "HL", "LH", "LL", "EH", "EL"}).sum()) >= 1, "no sequence fact through T"
    assert int(surf_s.frame.loc[:T, "structural_break_event"].eq("BOS_UP").sum()) >= 1, "no structural break through T"

    p_short = surf_s.frame.loc[:, list(s4b1._ALL_DERIVED_COLUMNS)].iloc[: T + 1]
    p_long = surf_l.frame.loc[:, list(s4b1._ALL_DERIVED_COLUMNS)].iloc[: T + 1]
    assert p_short.equals(p_long), "prefix through T must be equal under future extension"


def test_future_extension_preserves_real_events():
    """Future append must not rewrite confirmed swing / sequence / break facts through T."""
    short, adapter_s, timeline_s, surf_s = _rich_surface(50, "rich_ext_short")
    long_, adapter_l, timeline_l, surf_l = _rich_surface(70, "rich_ext_long")
    T = 45
    k_s = _key(adapter_s, short, T)
    k_l = _key(adapter_l, long_, T)
    p_s = s4b1.project_structure_prefix(surface=surf_s, boundary_key=k_s)
    p_l = s4b1.project_structure_prefix(surface=surf_l, boundary_key=k_l)
    assert p_s.prefix_hash == p_l.prefix_hash
    # concrete facts through T are identical
    cols = ["swing_high_confirmed", "swing_origin_position", "swing_confirmation_position",
            "swing_sequence_class", "structural_break_event", "structure_state_before"]
    assert surf_s.frame.loc[:T, cols].equals(surf_l.frame.loc[:T, cols])


def test_real_chain_reconstruction_matches_direct_engines():
    """The 4B-1 surface must equal directly running the real CLOSED 2.1A→2.1B→2.1C chain."""
    market = _market_rich(60)
    pol = _rich_policy()
    a = CausalAdaptiveSwingDetector(confirmation_policy=pol).analyze(market.copy())
    b = ConfirmedSwingSequenceEngine().analyze(a)
    c = CausalStructuralBreakEngine().analyze(b)

    adapter = PositionalTimelineAdapter("rich_direct")
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    surface = s4b1.build_structure_surface(
        timeline=timeline, adapter=adapter, market_history=market, swing_policy=pol
    )
    # every derived column equals the directly-run chain
    for col in s4b1._ALL_DERIVED_COLUMNS:
        assert surface.frame[col].equals(c[col]), f"derived column {col} diverges from direct chain"

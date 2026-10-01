"""Tests for Module 6.2A-4 V1 Stage 4B-2: Shared Entity & Lifecycle Surfaces.

Covers: entity-ID prefix stability (REAL CLOSED engines), non-vacuous lifecycle events, availability,
passthrough-market binding, self-integrity mutation rejection, prefix invariance, wrong-domain
rejection (BLOCKER 1 cross-domain substitution), complete-prefix binding (BLOCKER 2), boundary
legality, numeric/schema, and firewall.
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
)
from trading_system.research.trajectory.trajectory_contract import (
    MarketObservationTimeline,
    TrajectoryContractError,
    TrajectoryDataError,
)
from trading_system.research.trajectory import trajectory_stage4b1 as s4b1
from trading_system.research.trajectory import trajectory_stage4b2 as s4b2
from trading_system.research.trajectory.trajectory_stage4b2 import (
    Stage4B2LiquiditySurface,
    Stage4B2OrderBlockSurface,
    Stage4B2FVGSurface,
    Stage4B2DealingRangeSurface,
    Stage4B2PrefixBinding,
)
from trading_system.structure.swing_detector import EmpiricalConfirmationPolicy


# ---------------------------------------------------------------------------
# Helpers — rich fixture (REAL swings / BOS / lifecycle for all four domains)
# ---------------------------------------------------------------------------

def _policy():
    priors = tuple(0.01 * i for i in range(1, 50))
    return EmpiricalConfirmationPolicy(quantile=0.1, prior_continuation_reversals=priors)


def _market(n=90):
    """Staircase rise + terminal collapse: a function of index only (prefix-identical across n)."""
    o, h, l, c = [], [], [], []
    level = 100.0
    i = 0
    collapse_at = 65  # fixed, independent of n
    while i < n:
        if i < collapse_at:
            if i % 7 < 4:
                o.append(level); c.append(level + 5.0); level = c[-1]
            else:
                o.append(level); c.append(level - 3.0); level = c[-1]
        else:
            o.append(level); c.append(level - 6.0); level = c[-1]
        h.append(max(o[-1], c[-1]) + 1.0)
        l.append(min(o[-1], c[-1]) - 1.0)
        i += 1
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=pd.RangeIndex(n), dtype=float)


def _seal_and_struct(n=90, tid="s4b2"):
    market = _market(n)
    adapter = PositionalTimelineAdapter(tid)
    timeline = MarketObservationTimeline.seal(adapter=adapter, market_history=market)
    struct = s4b1.build_structure_surface(timeline=timeline, adapter=adapter, market_history=market, swing_policy=_policy())
    return market, adapter, timeline, struct


def _surfaces(n=90, tid="s4b2"):
    market, adapter, timeline, struct = _seal_and_struct(n, tid)
    liq = s4b2.build_liquidity_surface(timeline=timeline, adapter=adapter, market_history=market, structure_surface=struct)
    ob = s4b2.build_order_block_surface(timeline=timeline, adapter=adapter, market_history=market, structure_surface=struct)
    fvg = s4b2.build_fvg_surface(timeline=timeline, adapter=adapter, market_history=market)
    dr = s4b2.build_dealing_range_surface(timeline=timeline, adapter=adapter, market_history=market, structure_surface=struct)
    return market, adapter, timeline, struct, {"LIQ": liq, "OB": ob, "FVG": fvg, "DR": dr}


def _key(adapter, market, position, phase=InformationPhase.COMPLETED_ROW_AVAILABLE):
    return adapter.key_for_position(market.index, position, phase, 0)


_DOMAIN_PARAMS = [
    ("LIQUIDITY", "LIQ", Stage4B2LiquiditySurface),
    ("ORDER_BLOCK", "OB", Stage4B2OrderBlockSurface),
    ("FVG", "FVG", Stage4B2FVGSurface),
    ("DEALING_RANGE", "DR", Stage4B2DealingRangeSurface),
]

_ENTITY_ID_COL = {"LIQUIDITY": "level_id", "ORDER_BLOCK": "zone_id", "FVG": "fvg_id", "DEALING_RANGE": "range_id"}
_ENTITY_POS_COL = {
    "LIQUIDITY": "source_confirmation_position",
    "ORDER_BLOCK": "creation_position",
    "FVG": "creation_position",
    "DEALING_RANGE": "creation_position",
}


# ---------------------------------------------------------------------------
# §10 non-vacuous: fixtures produce real entities + lifecycle events
# ---------------------------------------------------------------------------

def test_fixture_produces_real_entities_and_lifecycle():
    _, _, _, _, surfs = _surfaces(90)
    for nm in ("LIQ", "OB", "FVG", "DR"):
        assert len(surfs[nm].normalized_entity_frame) >= 1, f"{nm} has no entities"
    liq_types = set(surfs["LIQ"].event_frame["event_type"])
    assert "LEVEL_CREATED" in liq_types and "FIRST_TOUCH" in liq_types
    ob_types = set(surfs["OB"].event_frame["event_type"])
    assert "ZONE_CREATED" in ob_types and "FIRST_TOUCH" in ob_types
    fvg_types = set(surfs["FVG"].event_frame["event_type"])
    assert "FVG_CREATED" in fvg_types and "FIRST_TOUCH" in fvg_types
    assert len(surfs["DR"].normalized_entity_frame) >= 1


def test_ambiguity_flag_marks_same_batch_collisions():
    _, _, _, _, surfs = _surfaces(90)
    ne = surfs["LIQ"].normalized_event_frame
    assert "same_information_batch_order_unknown" in ne.columns
    assert ne["same_information_batch_order_unknown"].any()


# ---------------------------------------------------------------------------
# §9 entity-ID prefix stability (REAL CLOSED engines)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain,short,cls", _DOMAIN_PARAMS)
def test_entity_id_prefix_stability(domain, short, cls):
    m_s, a_s, t_s, struct_s, surf_s = _surfaces(70, f"s_{short}_short")
    m_l, a_l, t_l, struct_l, surf_l = _surfaces(90, f"s_{short}_long")
    assert m_s.equals(m_l.iloc[:70])
    T = 60
    id_col = _ENTITY_ID_COL[domain]
    pos_col = _ENTITY_POS_COL[domain]
    s_entity = surf_s[short].normalized_entity_frame
    l_entity = surf_l[short].normalized_entity_frame
    s_through = s_entity[s_entity[pos_col] <= T]
    assert len(s_through) >= 1, f"{domain}: no entity created through T (vacuous)"
    s_ids = s_through[id_col].tolist()
    l_through = l_entity[l_entity[pos_col] <= T]
    l_ids = l_through[id_col].tolist()
    assert s_ids == l_ids, f"{domain}: entity IDs differ under future extension"


# ---------------------------------------------------------------------------
# §11 availability: event invisible before its factual row, visible at it
# ---------------------------------------------------------------------------

def test_lifecycle_event_availability():
    market, adapter, _, _, surfs = _surfaces(90)
    ev = surfs["LIQ"].event_frame
    touch = ev[ev["event_type"] == "FIRST_TOUCH"]
    assert len(touch) >= 1
    pos = int(touch["event_position"].iloc[0])
    k_before = _key(adapter, market, pos - 1)
    p_before = s4b2.project_domain_prefix(surface=surfs["LIQ"], boundary_key=k_before)
    assert p_before.prefix_row_count == pos
    k_at = _key(adapter, market, pos)
    p_at = s4b2.project_domain_prefix(surface=surfs["LIQ"], boundary_key=k_at)
    assert p_at.prefix_row_count == pos + 1
    assert p_before.prefix_hash != p_at.prefix_hash


# ---------------------------------------------------------------------------
# BLOCKER 1 — cross-domain substitution (coherent forgery must reject)
# ---------------------------------------------------------------------------

def _forge_surface(target_cls, source, structure_surface_id="FAKE"):
    """Coherently relabel source surface content as a different target surface class."""
    return target_cls(
        timeline_id=source.timeline_id,
        timeline_hash=source.timeline_hash,
        adapter_kind=source.adapter_kind,
        structure_surface_id=structure_surface_id,
        reconstruction_input_hash=source.reconstruction_input_hash,
        complete_result_hash=source.complete_result_hash,
        normalized_entity_hash=source.normalized_entity_hash,
        normalized_event_hash=source.normalized_event_hash,
        surface_id=source.surface_id,
        bar_frame=source.bar_frame,
        event_frame=source.event_frame,
        normalized_entity_frame=source.normalized_entity_frame,
        normalized_event_frame=source.normalized_event_frame,
    )


def test_fvg_relabeled_as_liquidity_rejected():
    _, _, _, _, surfs = _surfaces(90)
    forged = _forge_surface(Stage4B2LiquiditySurface, surfs["FVG"])
    with pytest.raises(TrajectoryDataError):
        s4b2.verify_surface_integrity(forged)


def test_ob_relabeled_as_dealing_range_rejected():
    _, _, _, _, surfs = _surfaces(90)
    forged = _forge_surface(Stage4B2DealingRangeSurface, surfs["OB"])
    with pytest.raises(TrajectoryDataError):
        s4b2.verify_surface_integrity(forged)


def test_liquidity_relabeled_as_fvg_rejected():
    _, _, _, _, surfs = _surfaces(90)
    forged = _forge_surface(Stage4B2FVGSurface, surfs["LIQ"], structure_surface_id=None)
    with pytest.raises(TrajectoryDataError):
        s4b2.verify_surface_integrity(forged)


def test_swap_tables_between_domains_rejected():
    _, _, _, _, surfs = _surfaces(90)
    # swap FVG event/entity frames into a Liquidity surface object
    forged = dataclasses.replace(
        surfs["LIQ"],
        event_frame=surfs["FVG"].event_frame,
        normalized_entity_frame=surfs["FVG"].normalized_entity_frame,
        normalized_event_frame=surfs["FVG"].normalized_event_frame,
    )
    with pytest.raises(TrajectoryDataError):
        s4b2.verify_surface_integrity(forged)


def test_coherent_metadata_forgery_with_recomputed_hash_rejected():
    # attacker recomputes surface_id from the forged (cross-domain) content; still rejected
    # because schema enforcement is class-derived, not hash-derived.
    _, _, _, _, surfs = _surfaces(90)
    forged = _forge_surface(Stage4B2LiquiditySurface, surfs["FVG"])
    # recompute a surface_id that matches the forged content's hashes (coherent attempt)
    recomputed_id = s4b2._canonical_hash(
        "STAGE4B2_SURFACE_IDENTITY_V1",
        {
            "surface_class": "Stage4B2LiquiditySurface",
            "domain": "LIQUIDITY",
            "contract_version": s4b2.CONTRACT_LIQUIDITY,
            "timeline_id": forged.timeline_id,
            "timeline_hash": forged.timeline_hash,
            "adapter_kind": forged.adapter_kind,
            "structure_surface_id": forged.structure_surface_id,
            "reconstruction_input_hash": forged.reconstruction_input_hash,
            "complete_result_hash": forged.complete_result_hash,
            "normalized_entity_hash": forged.normalized_entity_hash,
            "normalized_event_hash": forged.normalized_event_hash,
        },
    )
    forged2 = dataclasses.replace(forged, surface_id=recomputed_id)
    with pytest.raises(TrajectoryDataError):
        s4b2.verify_surface_integrity(forged2)


def test_wrong_surface_class_rejected_by_projector():
    market, adapter, _, _, _ = _surfaces(90)
    # project_domain_prefix must reject a non-surface object
    with pytest.raises(TrajectoryContractError):
        s4b2.project_domain_prefix(surface="not a surface", boundary_key=_key(adapter, market, 30))


# ---------------------------------------------------------------------------
# BLOCKER 2 — prefix binds ALL facts (event/entity/normalized), not only bar
# ---------------------------------------------------------------------------

def test_prefix_rejects_preT_event_removal():
    market, adapter, _, _, surfs = _surfaces(90)
    surf = surfs["LIQ"]
    k = _key(adapter, market, 60)
    ev = surf.event_frame.copy(deep=True)
    created = ev[(ev["event_type"] == "LEVEL_CREATED") & (ev["event_position"] <= 60)]
    assert len(created) >= 1
    drop_pos = int(created["event_position"].iloc[0])
    ev2 = ev[~((ev["event_type"] == "LEVEL_CREATED") & (ev["event_position"] == drop_pos))].reset_index(drop=True)
    tampered = dataclasses.replace(surf, event_frame=ev2)
    # removing a pre-T event changes complete_result_hash -> integrity rejects -> prefix rejects
    with pytest.raises(TrajectoryDataError):
        s4b2.project_domain_prefix(surface=tampered, boundary_key=k)


def test_prefix_rejects_preT_normalized_event_mutation():
    market, adapter, _, _, surfs = _surfaces(90)
    surf = surfs["LIQ"]
    k = _key(adapter, market, 60)
    ne = surf.normalized_event_frame.copy(deep=True)
    ne.iloc[0, ne.columns.get_loc("event_type")] = "FIRST_TOUCH"
    tampered = dataclasses.replace(surf, normalized_event_frame=ne)
    with pytest.raises(TrajectoryDataError):
        s4b2.project_domain_prefix(surface=tampered, boundary_key=k)


def test_prefix_rejects_preT_entity_mutation():
    market, adapter, _, _, surfs = _surfaces(90)
    surf = surfs["LIQ"]
    k = _key(adapter, market, 60)
    ent = surf.normalized_entity_frame.copy(deep=True)
    ent.iloc[0, ent.columns.get_loc("immutable_level_price")] = 99999.0
    tampered = dataclasses.replace(surf, normalized_entity_frame=ent)
    with pytest.raises(TrajectoryDataError):
        s4b2.project_domain_prefix(surface=tampered, boundary_key=k)


def test_dealing_range_preT_range_mutation_rejected():
    market, adapter, _, _, surfs = _surfaces(90)
    surf = surfs["DR"]
    k = _key(adapter, market, 60)
    ent = surf.normalized_entity_frame.copy(deep=True)
    ent.iloc[0, ent.columns.get_loc("range_high")] = 99999.0
    tampered = dataclasses.replace(surf, normalized_entity_frame=ent)
    with pytest.raises(TrajectoryDataError):
        s4b2.project_domain_prefix(surface=tampered, boundary_key=k)


def test_postT_extension_preserves_prefix():
    m_s, a_s, _, _, surf_s = _surfaces(70, "pfx_short")
    m_l, a_l, _, _, surf_l = _surfaces(90, "pfx_long")
    assert m_s.equals(m_l.iloc[:70])
    T = 60
    for short in ("LIQ", "OB", "FVG", "DR"):
        assert surf_s[short].surface_id != surf_l[short].surface_id, f"{short}: full identity should change on append"
        k_s = _key(a_s, m_s, T)
        k_l = _key(a_l, m_l, T)
        p_s = s4b2.project_domain_prefix(surface=surf_s[short], boundary_key=k_s)
        p_l = s4b2.project_domain_prefix(surface=surf_l[short], boundary_key=k_l)
        assert p_s.prefix_hash == p_l.prefix_hash, f"{short}: prefix through T must be preserved"


def test_prefix_binding_compact_no_dataframes():
    market, adapter, _, _, surfs = _surfaces(90)
    p = s4b2.project_domain_prefix(surface=surfs["LIQ"], boundary_key=_key(adapter, market, 30))
    for f in dataclasses.fields(p):
        assert not isinstance(getattr(p, f.name), pd.DataFrame), f"{f.name} must not be a DataFrame"


# ---------------------------------------------------------------------------
# §3 passthrough market binding
# ---------------------------------------------------------------------------

def test_passthrough_market_mutation_rejected():
    market, adapter, timeline, struct, _ = _surfaces(90)
    mutated_frame = struct.frame.copy(deep=True)
    mutated_frame.iloc[10, mutated_frame.columns.get_loc("close")] = 99999.0
    mutated_struct = dataclasses.replace(struct, frame=mutated_frame)
    s4b1.verify_surface_integrity(mutated_struct)  # derived unchanged
    with pytest.raises(TrajectoryDataError, match="passthrough"):
        s4b2.build_liquidity_surface(timeline=timeline, adapter=adapter, market_history=market, structure_surface=mutated_struct)


def test_structure_derived_mutation_rejected():
    market, adapter, timeline, struct, _ = _surfaces(90)
    mutated_frame = struct.frame.copy(deep=True)
    col = "swing_high_confirmed"
    current = bool(mutated_frame.iloc[5].loc[col])
    mutated_frame.iloc[5, mutated_frame.columns.get_loc(col)] = not current
    mutated_struct = dataclasses.replace(struct, frame=mutated_frame)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b2.build_liquidity_surface(timeline=timeline, adapter=adapter, market_history=market, structure_surface=mutated_struct)


# ---------------------------------------------------------------------------
# §14 self-integrity mutation rejection
# ---------------------------------------------------------------------------

def test_surface_bar_mutation_rejected():
    _, _, _, _, surfs = _surfaces(90)
    surf = surfs["LIQ"]
    s4b2.verify_surface_integrity(surf)
    frame = surf.bar_frame.copy(deep=True)
    frame.iloc[3, frame.columns.get_loc("liquidity_level_created")] = True
    tampered = dataclasses.replace(surf, bar_frame=frame)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b2.verify_surface_integrity(tampered)


def test_surface_event_mutation_rejected():
    _, _, _, _, surfs = _surfaces(90)
    surf = surfs["LIQ"]
    frame = surf.event_frame.copy(deep=True)
    frame.iloc[0, frame.columns.get_loc("event_type")] = "FIRST_TOUCH"
    tampered = dataclasses.replace(surf, event_frame=frame)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b2.verify_surface_integrity(tampered)


def test_forged_surface_id_rejected():
    _, _, _, _, surfs = _surfaces(90)
    forged = dataclasses.replace(surfs["LIQ"], surface_id="0" * 64)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b2.verify_surface_integrity(forged)


# ---------------------------------------------------------------------------
# §13 prefix identity
# ---------------------------------------------------------------------------

def test_prefix_mutation_at_or_before_T_rejected():
    _, adapter, _, _, surfs = _surfaces(90)
    surf = surfs["LIQ"]
    k = _key(adapter, _surfaces(90)[0], 60)
    frame = surf.bar_frame.copy(deep=True)
    frame.iloc[30, frame.columns.get_loc("liquidity_level_created")] = True
    tampered = dataclasses.replace(surf, bar_frame=frame)
    with pytest.raises(TrajectoryDataError, match="self-integrity"):
        s4b2.project_domain_prefix(surface=tampered, boundary_key=k)


# ---------------------------------------------------------------------------
# §12 boundary legality
# ---------------------------------------------------------------------------

def test_bar_pre_close_rejected():
    _, adapter, _, _, surfs = _surfaces(90)
    k = _key(adapter, _surfaces(90)[0], 30, InformationPhase.BAR_PRE_CLOSE)
    with pytest.raises(TrajectoryContractError, match="not legally observable"):
        s4b2.project_domain_prefix(surface=surfs["LIQ"], boundary_key=k)


def test_cross_timeline_rejected():
    _, _, _, _, surfs = _surfaces(90)
    other = PositionalTimelineAdapter("other_timeline")
    k = other.key_for_position(_surfaces(90)[0].index, 30, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
    with pytest.raises(TrajectoryDataError, match="wrong timeline"):
        s4b2.project_domain_prefix(surface=surfs["LIQ"], boundary_key=k)


def test_positional_fabricated_timestamp_rejected():
    _, _, _, _, surfs = _surfaces(90)
    fabricated = InformationKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id="s4b2",
        bar_position=30,
        event_time_utc=pd.Timestamp("2026-01-01", tz="UTC"),
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=0,
    )
    with pytest.raises(TrajectoryDataError, match="timestamp"):
        s4b2.project_domain_prefix(surface=surfs["LIQ"], boundary_key=fabricated)


# ---------------------------------------------------------------------------
# §17 state / storage
# ---------------------------------------------------------------------------

def test_input_immutability():
    market, adapter, timeline, struct, _ = _surfaces(90)
    m_before = market.copy(deep=True)
    s_before = struct.frame.copy(deep=True)
    s4b2.build_liquidity_surface(timeline=timeline, adapter=adapter, market_history=market, structure_surface=struct)
    s4b2.build_fvg_surface(timeline=timeline, adapter=adapter, market_history=market)
    pd.testing.assert_frame_equal(market, m_before)
    pd.testing.assert_frame_equal(struct.frame, s_before)


def test_two_hypotheses_share_physical_surface():
    _, adapter, _, _, surfs = _surfaces(90)
    surf = surfs["LIQ"]
    market = _surfaces(90)[0]
    k1 = _key(adapter, market, 30)
    k2 = _key(adapter, market, 60)
    p1 = s4b2.project_domain_prefix(surface=surf, boundary_key=k1)
    p2 = s4b2.project_domain_prefix(surface=surf, boundary_key=k2)
    assert p1.surface_id == p2.surface_id == surf.surface_id
    assert p1.prefix_hash != p2.prefix_hash


# ---------------------------------------------------------------------------
# §15 numeric / schema
# ---------------------------------------------------------------------------

def test_normalized_entity_is_derived_not_original():
    _, _, _, _, surfs = _surfaces(90)
    liq_entity = surfs["LIQ"].normalized_entity_frame
    assert "level_id" in liq_entity.columns
    assert "immutable_level_price" in liq_entity.columns
    assert "first_touch" not in liq_entity.columns


def test_dealing_range_uses_original_range_table():
    _, _, _, _, surfs = _surfaces(90)
    dr_entity = surfs["DR"].normalized_entity_frame
    assert "range_low" in dr_entity.columns and "range_high" in dr_entity.columns
    assert "midpoint" in dr_entity.columns


# ---------------------------------------------------------------------------
# §18 firewall / out of scope
# ---------------------------------------------------------------------------

def test_firewall_live_modules_do_not_import_stage4b2():
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
            for forb in ("trajectory_stage4b2", "research.trajectory"):
                assert forb not in content, f"Firewall violation: {py_file} imports {forb}"


def test_stage4b2_no_out_of_scope_implementations():
    path = Path("src/trading_system/research/trajectory/trajectory_stage4b2.py")
    content = path.read_text(encoding="utf-8", errors="ignore")
    forbidden = [
        "def build_htf", "def build_mtf", "def build_descriptor", "def build_estimand",
        "def build_model", "def build_scorer", "def build_geometry", "def build_execution",
        "PROBABILITY", "SCORER",
    ]
    for forb in forbidden:
        assert forb not in content, f"forbidden marker: {forb}"


def test_stage4b2_manifest_declares_out_of_scope_and_open_debts():
    manifest = s4b2.trajectory_stage4b2_manifest()
    assert s4b2.TRAJECTORY_STAGE4B2_CONTRACT_VERSION == "CAUSAL_SHARED_ENTITY_LIFECYCLE_SURFACE_V1"
    vals = dict(zip(manifest["name"], manifest["value"]))
    assert vals["WIN_LOSS"] == "FORBIDDEN"
    assert vals["STAGE4C"] == "NOT_IMPLEMENTED"
    for d in ("RESEARCH-DEBT-020", "RESEARCH-DEBT-021", "RESEARCH-DEBT-022", "RESEARCH-DEBT-023", "RESEARCH-DEBT-024", "RESEARCH-DEBT-025"):
        assert vals.get(d) == "OPEN"


# ---------------------------------------------------------------------------
# PRIVATE-IMPORT REGRESSION (PATCH)
# ---------------------------------------------------------------------------

def test_no_private_closed_schema_imports():
    """Stage 4B-2 must not import underscore-prefixed schema constants from CLOSED domain modules."""
    import ast
    src_path = Path("src/trading_system/research/trajectory/trajectory_stage4b2.py")
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    forbidden_modules = {
        "trading_system.liquidity.liquidity_map",
        "trading_system.zones.order_blocks",
        "trading_system.zones.fvg",
        "trading_system.zones.dealing_range",
    }
    # underscore-prefixed names imported from those modules (direct or aliased)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module in forbidden_modules:
                for alias in node.names:
                    assert not alias.name.startswith("_"), (
                        f"private schema import {alias.name} from {node.module} is forbidden"
                    )


def test_local_frozen_mirrors_match_actual_public_outputs():
    """The local frozen schema mirrors must equal the actual public CLOSED engine outputs."""
    market, adapter, timeline, struct, surfs = _surfaces(90)
    # LIQ
    assert tuple(surfs["LIQ"].bar_frame.columns)[-len(s4b2._LIQ_BAR_SCHEMA):] == s4b2._LIQ_BAR_SCHEMA
    assert tuple(surfs["LIQ"].event_frame.columns) == s4b2._LIQ_EVENT_SCHEMA
    # OB
    assert tuple(surfs["OB"].bar_frame.columns)[-len(s4b2._OB_BAR_SCHEMA):] == s4b2._OB_BAR_SCHEMA
    assert tuple(surfs["OB"].event_frame.columns) == s4b2._OB_EVENT_SCHEMA
    # FVG
    assert tuple(surfs["FVG"].bar_frame.columns)[-len(s4b2._FVG_BAR_SCHEMA):] == s4b2._FVG_BAR_SCHEMA
    assert tuple(surfs["FVG"].event_frame.columns) == s4b2._FVG_EVENT_SCHEMA
    assert len(s4b2._FVG_EVENT_SCHEMA) == 21, "FVG source event schema must be 21 columns"
    # DR
    assert tuple(surfs["DR"].bar_frame.columns)[-len(s4b2._DR_BAR_SCHEMA):] == s4b2._DR_BAR_SCHEMA
    assert tuple(surfs["DR"].event_frame.columns) == s4b2._DR_RANGE_SCHEMA

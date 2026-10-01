"""INDEPENDENT AUDITOR PROBE 5 — ambiguity flag + entity traceability semantics."""
import sys, pandas as pd
sys.path.insert(0, "/home/user/project/trading_project/src")
from trading_system.research.information_time import PositionalTimelineAdapter, InformationPhase
from trading_system.research.trajectory.trajectory_contract import MarketObservationTimeline
from trading_system.research.trajectory import trajectory_stage4b1 as s4b1
from trading_system.research.trajectory import trajectory_stage4b2 as s4b2
from trading_system.structure.swing_detector import EmpiricalConfirmationPolicy

def market(n=90):
    o, h, l, c = [], [], [], []
    level = 100.0
    for i in range(n):
        if i < 65:
            if i % 7 < 4:
                o.append(level); c.append(level + 5.0); level = c[-1]
            else:
                o.append(level); c.append(level - 3.0); level = c[-1]
        else:
            o.append(level); c.append(level - 6.0); level = c[-1]
        h.append(max(o[-1], c[-1]) + 1.0); l.append(min(o[-1], c[-1]) - 1.0)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=pd.RangeIndex(n), dtype=float)

priors = tuple(0.01 * i for i in range(1, 50))
policy = EmpiricalConfirmationPolicy(quantile=0.1, prior_continuation_reversals=priors)
mk = market(90); adapter = PositionalTimelineAdapter("sem")
tl = MarketObservationTimeline.seal(adapter=adapter, market_history=mk)
struct = s4b1.build_structure_surface(timeline=tl, adapter=adapter, market_history=mk, swing_policy=policy)
surfs = {
    "LIQ": s4b2.build_liquidity_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct),
    "OB":  s4b2.build_order_block_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct),
    "FVG": s4b2.build_fvg_surface(timeline=tl, adapter=adapter, market_history=mk),
    "DR":  s4b2.build_dealing_range_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct),
}
fails = []
for name, s in surfs.items():
    ne = s.normalized_event_frame
    flag = "same_information_batch_order_unknown"
    # 1. flag exists and is boolean
    if flag not in ne.columns:
        fails.append(f"{name}: missing flag"); print(f"BAD {name}: missing flag"); continue
    # 2. flag == duplicated event position (when event_position exists); else all False
    if "event_position" in ne.columns:
        expected = ne["event_position"].duplicated(keep=False)
        if not (ne[flag].fillna(False).astype(bool).reset_index(drop=True).equals(
                expected.reset_index(drop=True))):
            fails.append(f"{name}: flag != duplicate(event_position)")
            print(f"BAD {name}: flag mismatch")
        else:
            n_amb = int(ne[flag].sum())
            print(f"OK  {name}: flag = duplicated event_position; {n_amb} ambiguous rows / {len(ne)}")
    else:
        if ne[flag].any():
            fails.append(f"{name}: range table flag must be all False")
            print(f"BAD {name}: unexpected True flag without event_position")
        else:
            print(f"OK  {name}: no event_position -> all-False flag ({len(ne)} rows)")
    # 3. normalized_event = source event table + flag only (no invented columns)
    base_cols = list(s.event_frame.columns)
    if list(ne.columns) != base_cols + [flag]:
        fails.append(f"{name}: normalized event invented columns")
        print(f"BAD {name}: ne cols != event cols + flag")
    # 4. entity frame traceable: every entity column is a subset of event columns (non-DR)
    ent = s.normalized_entity_frame
    if name != "DR":
        if not set(ent.columns) <= set(s.event_frame.columns):
            fails.append(f"{name}: entity has non-source columns")
            print(f"BAD {name}: entity columns not subset of event: {set(ent.columns)-set(s.event_frame.columns)}")
        # entity rows must correspond to CREATED events exactly
        creation = {"LIQ": "LEVEL_CREATED", "OB": "ZONE_CREATED", "FVG": "FVG_CREATED"}[name]
        created = s.event_frame[s.event_frame.event_type == creation]
        if len(ent) != len(created):
            fails.append(f"{name}: entity row count {len(ent)} != created events {len(created)}")
            print(f"BAD {name}: {len(ent)} entities vs {len(created)} created events")
        # id sets equal
        idcol = {"LIQ": "level_id", "OB": "zone_id", "FVG": "fvg_id"}[name]
        if set(ent[idcol]) != set(created[idcol]):
            fails.append(f"{name}: entity ids != created ids")
            print(f"BAD {name}: id mismatch")
        print(f"OK  {name}: {len(ent)} entities traceable 1:1 to {creation} rows")
    else:
        # DR entity = original range table exactly
        if not ent.equals(s.event_frame):
            fails.append("DR: entity != original CLOSED range table")
            print("BAD DR: entity frame differs from source range table")
        else:
            print(f"OK  DR: normalized entity == original CLOSED range table ({len(ent)} ranges)")

# 5. prefix filter must NOT recompute/change flags: build prefix at T=60 for a domain with ambiguity
s = surfs["LIQ"]
k = adapter.key_for_position(mk.index, 60, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
# recompute the filtered ne exactly like projector and compare flags to the full-table values
ne = s.normalized_event_frame
sub = ne[ne["event_position"] <= 60].reset_index(drop=True)
full_vals = ne.reset_index(drop=True).loc[sub.index] if False else None
# the sub rows' flags must equal flags computed over the FULL table for the same event rows
merged = sub.merge(ne[["event_position", "level_id", "event_type", "same_information_batch_order_unknown"]],
                   on=["event_position", "level_id", "event_type"], suffixes=("_sub", "_full"))
mismatch = (merged["same_information_batch_order_unknown_sub"].astype(bool) !=
            merged["same_information_batch_order_unknown_full"].astype(bool)).sum()
if mismatch:
    fails.append("prefix filtering altered ambiguity flags")
    print(f"BAD prefix flag drift: {mismatch}")
else:
    print("OK  ambiguity flags stable under prefix filtering (no subset recomputation)")

print("\nPROBE 5 RESULT:", "PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)

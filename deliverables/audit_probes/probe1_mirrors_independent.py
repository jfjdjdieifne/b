"""INDEPENDENT AUDITOR PROBE 1 — mirrors vs actual CLOSED engine outputs.
Builds each CLOSED engine DIRECTLY (not via stage4b2) and compares the REAL
public output schemas against Stage 4B-2 local frozen mirrors.
"""
import sys, pandas as pd
sys.path.insert(0, "/home/user/project/trading_project/src")

from trading_system.structure.swing_detector import EmpiricalConfirmationPolicy
from trading_system.research.information_time import PositionalTimelineAdapter
from trading_system.research.trajectory.trajectory_contract import MarketObservationTimeline
from trading_system.research.trajectory import trajectory_stage4b1 as s4b1
from trading_system.research.trajectory import trajectory_stage4b2 as s4b2
from trading_system.liquidity.liquidity_map import CausalLiquidityMapEngine
from trading_system.zones.order_blocks import CausalOrderBlockEngine
from trading_system.zones.fvg import CausalFVGEngine
from trading_system.zones.dealing_range import CausalDealingRangeEngine


def market(n=90):
    o, h, l, c = [], [], [], []
    level = 100.0
    i = 0
    while i < n:
        if i < 65:
            if i % 7 < 4:
                o.append(level); c.append(level + 5.0); level = c[-1]
            else:
                o.append(level); c.append(level - 3.0); level = c[-1]
        else:
            o.append(level); c.append(level - 6.0); level = c[-1]
        h.append(max(o[-1], c[-1]) + 1.0)
        l.append(min(o[-1], c[-1]) - 1.0)
        i += 1
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c},
                        index=pd.RangeIndex(n), dtype=float)


priors = tuple(0.01 * i for i in range(1, 50))
policy = EmpiricalConfirmationPolicy(quantile=0.1, prior_continuation_reversals=priors)
mk = market(90)
adapter = PositionalTimelineAdapter("probe1")
tl = MarketObservationTimeline.seal(adapter=adapter, market_history=mk)
struct = s4b1.build_structure_surface(timeline=tl, adapter=adapter,
                                      market_history=mk, swing_policy=policy)
frame = struct.frame

# ---- DIRECT engine calls, exactly as stage4b2 performs them ----
liq_bar, liq_ev = CausalLiquidityMapEngine().analyze(frame)
ob_bar, ob_ev = CausalOrderBlockEngine().analyze(frame)
fvg_bar, fvg_ev = CausalFVGEngine().analyze(mk)
dr_bar, dr_tbl = CausalDealingRangeEngine().analyze(frame)


def new_cols(result, inp):
    existing = set(inp.columns)
    return tuple(c for c in result.columns if c not in existing)

direct = {
    "LIQ bar":  (new_cols(liq_bar, frame), s4b2._LIQ_BAR_SCHEMA),
    "LIQ ev":   (tuple(liq_ev.columns), s4b2._LIQ_EVENT_SCHEMA),
    "OB bar":   (new_cols(ob_bar, frame), s4b2._OB_BAR_SCHEMA),
    "OB ev":    (tuple(ob_ev.columns), s4b2._OB_EVENT_SCHEMA),
    "FVG bar":  (new_cols(fvg_bar, mk), s4b2._FVG_BAR_SCHEMA),
    "FVG ev":   (tuple(fvg_ev.columns), s4b2._FVG_EVENT_SCHEMA),
    "DR bar":   (new_cols(dr_bar, frame), s4b2._DR_BAR_SCHEMA),
    "DR tbl":   (tuple(dr_tbl.columns), s4b2._DR_RANGE_SCHEMA),
}
ok = True
for name, (actual, mirror) in direct.items():
    same = actual == mirror
    ok &= same
    print(f"{'MATCH ' if same else 'MISMATCH'} {name:8s} actual={len(actual):2d} mirror={len(mirror):2d}")
    if not same:
        print("   missing in mirror:", [c for c in actual if c not in mirror])
        print("   extra in mirror:  ", [c for c in mirror if c not in actual])
        # order differences
        if set(actual) == set(mirror):
            for i, (a, b) in enumerate(zip(actual, mirror)):
                if a != b:
                    print(f"   order diff at {i}: actual={a} mirror={b}")

# expected counts
expected_counts = {"LIQ bar": (23,), "LIQ ev": (16,), "OB bar": (26,), "OB ev": (20,),
                   "FVG bar": (27,), "FVG ev": (21,), "DR bar": (30,), "DR tbl": (17,)}
for name, (ec,) in expected_counts.items():
    actual_len = len(direct[name][0])
    flag = "OK " if actual_len == ec else "BAD"
    if actual_len != ec:
        ok = False
    print(f"{flag} count {name}: {actual_len} (expected {ec})")

print("\nPROBE 1 RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)

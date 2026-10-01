"""INDEPENDENT AUDITOR PROBE 3 — runtime equivalence enforcement.
If the ACTUAL CLOSED engine output diverges from the frozen mirror, build must reject.
Also tamper with the class-bound contract and prove verify re-derives from it.
"""
import sys, pandas as pd
sys.path.insert(0, "/home/user/project/trading_project/src")
from trading_system.research.information_time import PositionalTimelineAdapter, InformationPhase
from trading_system.research.trajectory.trajectory_contract import MarketObservationTimeline, TrajectoryDataError
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
mk = market(90); adapter = PositionalTimelineAdapter("rt")
tl = MarketObservationTimeline.seal(adapter=adapter, market_history=mk)
struct = s4b1.build_structure_surface(timeline=tl, adapter=adapter, market_history=mk, swing_policy=policy)

fails = []

# 1. Evil LIQUIDITY engine: inject an extra DERIVED (non-passthrough) column -> mirror mismatch
class EvilLiq(s4b2.CausalLiquidityMapEngine):
    def analyze(self, frame):
        bar, ev = super().analyze(frame)
        bar = bar.copy()
        bar["evil_new_fact"] = 1.0   # a derived column the mirror doesn't know
        return bar, ev

orig = s4b2.CausalLiquidityMapEngine
s4b2.CausalLiquidityMapEngine = EvilLiq
try:
    s4b2.build_liquidity_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct)
    fails.append("extra engine derived column NOT rejected at construction")
    print("ACCEPT-BAD extra engine derived column accepted")
except TrajectoryDataError as e:
    print("REJECT-OK extra engine derived column rejected:", str(e)[:80])
finally:
    s4b2.CausalLiquidityMapEngine = orig

# 2. Evil FVG engine: drop a source event column -> must reject
class EvilFvg(s4b2.CausalFVGEngine):
    def analyze(self, frame):
        bar, ev = super().analyze(frame)
        return bar, ev.drop(columns=["zone_range_coverage_fraction"])
orig = s4b2.CausalFVGEngine
s4b2.CausalFVGEngine = EvilFvg
try:
    s4b2.build_fvg_surface(timeline=tl, adapter=adapter, market_history=mk)
    fails.append("missing engine event column NOT rejected")
    print("ACCEPT-BAD missing engine event column accepted")
except TrajectoryDataError as e:
    print("REJECT-OK missing engine event column rejected:", str(e)[:80])
finally:
    s4b2.CausalFVGEngine = orig

# 3. Evil DR engine: reordered event/range columns -> must reject (order-sensitive mirror)
class EvilDr(s4b2.CausalDealingRangeEngine):
    def analyze(self, frame):
        bar, tbl = super().analyze(frame)
        cols = list(tbl.columns)
        cols[0], cols[1] = cols[1], cols[0]
        return bar, tbl[cols]
orig = s4b2.CausalDealingRangeEngine
s4b2.CausalDealingRangeEngine = EvilDr
try:
    s4b2.build_dealing_range_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct)
    fails.append("reordered engine range columns NOT rejected")
    print("ACCEPT-BAD reordered range columns accepted")
except TrajectoryDataError as e:
    print("REJECT-OK reordered range columns rejected:", str(e)[:80])
finally:
    s4b2.CausalDealingRangeEngine = orig

# 4. Sanity: genuine build still works after restoring engines (no over-strict break)
liq = s4b2.build_liquidity_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct)
fvg = s4b2.build_fvg_surface(timeline=tl, adapter=adapter, market_history=mk)
s4b2.verify_surface_integrity(liq); s4b2.verify_surface_integrity(fvg)
print("OK genuine surfaces build + verify after restored engines")

print("\nPROBE 3 RESULT:", "PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)

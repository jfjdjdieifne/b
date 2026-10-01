"""INDEPENDENT AUDITOR PROBE 4b — passthrough coverage on DERIVED facts only.
A column is genuinely 'consumed' only if mutating it changes DERIVED bar columns
or the event/range table (the parts bound by complete_result_hash). Echoing the
mutated input column through passthrough does NOT count.
"""
import sys, pandas as pd, numpy as np
sys.path.insert(0, "/home/user/project/trading_project/src")
from trading_system.research.information_time import PositionalTimelineAdapter
from trading_system.research.trajectory.trajectory_contract import MarketObservationTimeline
from trading_system.research.trajectory import trajectory_stage4b1 as s4b1
from trading_system.research.trajectory import trajectory_stage4b2 as s4b2
from trading_system.research.hashing import canonical_sha256
from trading_system.liquidity.liquidity_map import CausalLiquidityMapEngine
from trading_system.zones.order_blocks import CausalOrderBlockEngine
from trading_system.zones.fvg import CausalFVGEngine
from trading_system.zones.dealing_range import CausalDealingRangeEngine
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
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=pd.RangeIndex(n), dtype=float)
    df["volume"] = 1000.0 + np.arange(n) * 7.0
    return df

priors = tuple(0.01 * i for i in range(1, 50))
policy = EmpiricalConfirmationPolicy(quantile=0.1, prior_continuation_reversals=priors)
mk = market(90); adapter = PositionalTimelineAdapter("pt")
tl = MarketObservationTimeline.seal(adapter=adapter, market_history=mk)
struct = s4b1.build_structure_surface(timeline=tl, adapter=adapter, market_history=mk, swing_policy=policy)
frame = struct.frame

# Which columns does each engine read? Static grep + dynamic derived-fact sensitivity.
engines = {
    "LIQUIDITY": (CausalLiquidityMapEngine, frame, s4b2._PASSTHROUGH_MARKET_COLUMNS["LIQUIDITY"], frame),
    "ORDER_BLOCK": (CausalOrderBlockEngine, frame, s4b2._PASSTHROUGH_MARKET_COLUMNS["ORDER_BLOCK"], frame),
    "DEALING_RANGE": (CausalDealingRangeEngine, frame, s4b2._PASSTHROUGH_MARKET_COLUMNS["DEALING_RANGE"], frame),
    "FVG": (CausalFVGEngine, mk, s4b2._PASSTHROUGH_MARKET_COLUMNS["FVG"], mk),
}
base_cols = ["open", "high", "low", "close", "volume"]

def derived_hash(engine, inp, baseline_input):
    bar, ev = engine().analyze(inp)
    new = [c for c in bar.columns if c not in baseline_input.columns]
    return canonical_sha256(domain="p", payload={"bar_derived": bar.loc[:, new], "ev": ev})

fails = []
for name, (eng, inp, verified, baseline_input) in engines.items():
    base = derived_hash(eng, inp, baseline_input)
    print(f"\n{name}: verified = {verified}")
    for col in base_cols:
        if col not in inp.columns:
            continue
        mut = inp.copy(deep=True)
        delta = 10.0 if col != "volume" else 500.0
        mut.loc[10, col] = float(mut.loc[10, col]) + delta
        try:
            h = derived_hash(eng, mut, baseline_input)
        except Exception as e:
            print(f"   {col:7s} mutation -> engine REJECTS ({type(e).__name__}); 4B-2 verified={col in verified}")
            if col not in verified:
                # Engine rejects inconsistent data; 4B-2 would call verify first anyway.
                # Not a forgery channel (rejection happens at engine level).
                pass
            continue
        if h != base:
            tag = "covered" if col in verified else "*** UNVERIFIED DERIVED-FACT CHANNEL ***"
            print(f"   {col:7s} mutation -> DERIVED FACTS CHANGE; {tag}")
            if col not in verified:
                fails.append((name, col))
        else:
            print(f"   {col:7s} mutation -> derived facts unchanged (passthrough echo only)")

print("\nPROBE 4b RESULT:", "PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)

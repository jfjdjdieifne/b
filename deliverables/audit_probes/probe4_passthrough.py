"""INDEPENDENT AUDITOR PROBE 4 — passthrough market column coverage.
Question: do the columns Stage 4B-2 verifies against sealed market_history cover
EVERY market column each CLOSED engine actually consumes from structure frame?
Method: mutate each base OHLCV column one-by-one in the engine INPUT frame and
check whether the engine's factual output changes (content hash). Any consumed
column missing from the verified set is a potential forgery channel.
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
print("structure frame columns:", list(frame.columns))

engines = {
    "LIQUIDITY": (CausalLiquidityMapEngine, frame, s4b2._PASSTHROUGH_MARKET_COLUMNS["LIQUIDITY"]),
    "ORDER_BLOCK": (CausalOrderBlockEngine, frame, s4b2._PASSTHROUGH_MARKET_COLUMNS["ORDER_BLOCK"]),
    "DEALING_RANGE": (CausalDealingRangeEngine, frame, s4b2._PASSTHROUGH_MARKET_COLUMNS["DEALING_RANGE"]),
    "FVG": (CausalFVGEngine, mk, s4b2._PASSTHROUGH_MARKET_COLUMNS["FVG"]),
}
base_cols = ["open", "high", "low", "close", "volume"]

def out_hash(engine, inp):
    bar, ev = engine().analyze(inp)
    return canonical_sha256(domain="probe", payload={"bar": bar, "ev": ev})

fails = []
for name, (eng, inp, verified) in engines.items():
    base = out_hash(eng, inp)
    consumed = []
    for col in base_cols:
        if col not in inp.columns:
            continue
        mut = inp.copy(deep=True)
        # mutate pre-close history (bar 10, well before terminal) in a way consistent with OHLC sanity not required
        mut.loc[10, col] = float(mut.loc[10, col]) + (10.0 if col != "volume" else 500.0)
        try:
            h = out_hash(eng, mut)
        except Exception as e:
            consumed.append((col, f"rejected:{type(e).__name__}"))
            continue
        if h != base:
            consumed.append((col, "CHANGES_OUTPUT"))
    print(f"\n{name}: verified passthrough = {verified}")
    for col, st in consumed:
        tag = "covered" if col in verified else "*** NOT VERIFIED IN 4B-2 ***"
        print(f"   engine consumes {col:7s} ({st}) -> {tag}")
        if st == "CHANGES_OUTPUT" and col not in verified:
            fails.append((name, col))

# Also check derived structure columns sensitivity isn't relevant: s4b1 integrity binds them.
print("\nPROBE 4 RESULT:", "PASS" if not fails else f"FAIL uncovered consumed columns: {fails}")
sys.exit(1 if fails else 0)

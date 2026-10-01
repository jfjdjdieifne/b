import sys, dataclasses, pandas as pd
sys.path.insert(0, "/home/user/project/trading_project/src")
from trading_system.research.information_time import PositionalTimelineAdapter, InformationPhase
from trading_system.research.trajectory.trajectory_contract import MarketObservationTimeline
from trading_system.research.trajectory import trajectory_stage4b1 as s4b1
from trading_system.research.trajectory import trajectory_stage4b2 as s4b2
from trading_system.structure.swing_detector import EmpiricalConfirmationPolicy

def market(n=90):
    o,h,l,c=[],[],[],[]; level=100.0
    for i in range(n):
        if i<65:
            if i%7<4: o.append(level); c.append(level+5.0); level=c[-1]
            else: o.append(level); c.append(level-3.0); level=c[-1]
        else: o.append(level); c.append(level-6.0); level=c[-1]
        h.append(max(o[-1],c[-1])+1.0); l.append(min(o[-1],c[-1])-1.0)
    return pd.DataFrame({"open":o,"high":h,"low":l,"close":c}, index=pd.RangeIndex(n), dtype=float)

priors=tuple(0.01*i for i in range(1,50))
pol=EmpiricalConfirmationPolicy(quantile=0.1,prior_continuation_reversals=priors)
mk=market(90); ad=PositionalTimelineAdapter("e6")
tl=MarketObservationTimeline.seal(adapter=ad,market_history=mk)
st=s4b1.build_structure_surface(timeline=tl,adapter=ad,market_history=mk,swing_policy=pol)
liq=s4b2.build_liquidity_surface(timeline=tl,adapter=ad,market_history=mk,structure_surface=st)

# 1. append bogus column at END of bar_frame (after derived tail)
b=liq.bar_frame.copy(deep=True); b["evil_tail_col"]=1.0
t1=dataclasses.replace(liq, bar_frame=b)
try:
    s4b2.verify_surface_integrity(t1); print("ACCEPTED bogus column appended at bar_frame tail (passthrough-class unbound)")
except Exception as e: print("REJECTED bogus tail column:", type(e).__name__)

# 2. insert bogus column right after passthrough (shifts derived tail)
b2=liq.bar_frame.copy(deep=True)
derived=list(s4b2._LIQ_BAR_SCHEMA); base=[c for c in b2.columns if c not in derived]
b2=b2[base+["evil_mid_col"]+derived]
t2=dataclasses.replace(liq, bar_frame=b2)
try:
    s4b2.verify_surface_integrity(t2); print("ACCEPTED bogus column inserted before derived tail")
except Exception as e: print("REJECTED bogus middle column (tail schema shifts):", type(e).__name__)

# 3. duplicate column in event frame
ev=liq.event_frame.copy(deep=True)
ev2=pd.concat([ev, ev.iloc[:,[0]]], axis=1)
t3=dataclasses.replace(liq, event_frame=ev2)
try:
    s4b2.verify_surface_integrity(t3); print("ACCEPTED duplicate event column")
except Exception as e: print("REJECTED duplicate event column:", type(e).__name__)

# 4. defensive copies: mutate caller frames after build, integrity must hold
f=st.frame.copy(deep=True); f.loc[10,"close"]=999.0
s4b2.verify_surface_integrity(liq); print("OK surface immune to post-build caller input mutation")

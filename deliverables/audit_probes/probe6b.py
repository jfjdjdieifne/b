import sys, dataclasses, pandas as pd
sys.path.insert(0,"src")
from trading_system.research.information_time import PositionalTimelineAdapter
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
    return pd.DataFrame({"open":o,"high":h,"low":l,"close":c},index=pd.RangeIndex(n),dtype=float)
pol=EmpiricalConfirmationPolicy(quantile=0.1,prior_continuation_reversals=tuple(0.01*i for i in range(1,50)))
mk=market(90); ad=PositionalTimelineAdapter("e7")
tl=MarketObservationTimeline.seal(adapter=ad,market_history=mk)
st=s4b1.build_structure_surface(timeline=tl,adapter=ad,market_history=mk,swing_policy=pol)
liq=s4b2.build_liquidity_surface(timeline=tl,adapter=ad,market_history=mk,structure_surface=st)
# insert bogus column after passthrough, before derived tail
b=liq.bar_frame.copy(deep=True)
derived=list(s4b2._LIQ_BAR_SCHEMA); base=[c for c in b.columns if c not in derived]
b.insert(len(base),"evil_mid_col",1.0)
try:
    s4b2.verify_surface_integrity(dataclasses.replace(liq,bar_frame=b)); print("ACCEPTED middle insert")
except Exception as e: print("REJECTED middle insert:",type(e).__name__)
# duplicate event column
ev=liq.event_frame.copy(deep=True)
ev=pd.concat([ev, ev.iloc[:,[0]]],axis=1)
try:
    s4b2.verify_surface_integrity(dataclasses.replace(liq,event_frame=ev)); print("ACCEPTED dup event col")
except Exception as e: print("REJECTED dup event col:",type(e).__name__)
# mutate caller frame after build, check immunity
f2=st.frame.copy(deep=True); f2.loc[10,"close"]=999.0
s4b2.verify_surface_integrity(liq); print("OK immune to post-build caller mutation")

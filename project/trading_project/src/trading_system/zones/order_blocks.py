"""Layer 4 — Module 4.1: Causal Order-Block Candidate & Lifecycle Engine V1.1.

Operational price-zone candidates only; no institutional-origin claim. A zone
is created on a directional 2.1C break row, using the most recent opposite-body
candle inside a causal structural leg bounded by the latest opposite confirmed
swing available before that row. The search interval includes the boundary
origin and excludes creation: `[boundary, creation)`. Monitoring starts on the
next row. At most one finite displacement observation per created zone enters
history; undefined displacement still creates the zone but is not pushed.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math, numpy as np, pandas as pd
from trading_system.core.causal_percentile import CausalPercentileTracker

class OrderBlockError(Exception): pass
class OrderBlockDataError(OrderBlockError): pass

_DIRECTIONAL={"BOS_UP":"BULLISH_OB_CANDIDATE","CHOCH_UP":"BULLISH_OB_CANDIDATE","BOS_DOWN":"BEARISH_OB_CANDIDATE","CHOCH_DOWN":"BEARISH_OB_CANDIDATE"}
_EVENT_ORDER={"ZONE_CREATED":0,"FIRST_TOUCH":1,"FIRST_FAR_SIDE_WICK_BREACH":2,"FIRST_FAR_SIDE_CLOSE_BREACH":3,"FIRST_CLOSE_RECLAIM_OF_FAR_SIDE":4}

@dataclass
class _Zone:
 id:int; direction:str; origin:int; creation:int; boundary:int; source:str
 low:float; high:float; body_low:float; body_high:float; displacement:float
 displacement_pct:float; displacement_n:int; prior_use:int
 touch:Optional[int]=None; wick:Optional[int]=None; close:Optional[int]=None; reclaim:Optional[int]=None

_BAR_COLS=("ob_candidate_created","created_ob_zone_id","created_ob_direction","created_ob_origin_position","created_ob_creation_position","created_ob_full_zone_low","created_ob_full_zone_high","created_ob_body_low","created_ob_body_high","created_ob_source_break_event","created_ob_origin_prior_use_count","created_ob_displacement_fraction","created_ob_displacement_percentile","created_ob_displacement_history_count","created_ob_search_boundary_position","created_ob_opposite_candle_count_in_leg","bullish_ob_first_touch_count","bearish_ob_first_touch_count","bullish_ob_first_far_side_wick_breach_count","bearish_ob_first_far_side_wick_breach_count","bullish_ob_first_far_side_close_breach_count","bearish_ob_first_far_side_close_breach_count","bullish_ob_first_reclaim_count","bearish_ob_first_reclaim_count","known_bullish_ob_candidate_count","known_bearish_ob_candidate_count")
_EVENT_COLS=("event_position","zone_id","direction","event_type","origin_position","creation_position","search_boundary_position","source_break_event","full_zone_low","full_zone_high","body_low","body_high","event_high","event_low","event_close","displacement_fraction","displacement_percentile","displacement_history_count","origin_prior_use_count","zone_age_bars")

class CausalOrderBlockEngine:
 @staticmethod
 def _validate(df):
  if not isinstance(df,pd.DataFrame): raise OrderBlockDataError("df must be DataFrame")
  if df.columns.has_duplicates: raise OrderBlockDataError("duplicate columns")
  req=("open","high","low","close","swing_high_confirmed","swing_low_confirmed","swing_origin_position","swing_confirmation_position","swing_price","structural_break_event","high_close_breach_event","low_close_breach_event","structure_state_before")
  miss=[c for c in req if c not in df]
  if miss: raise OrderBlockDataError(f"missing {miss}")
  if any(c in df for c in _BAR_COLS): raise OrderBlockDataError("output collision")
  if df.index.has_duplicates or not df.index.is_monotonic_increasing: raise OrderBlockDataError("bad index")
  for c in ("open","high","low","close"):
   x=df[c]
   if pd.api.types.is_bool_dtype(x.dtype) or not pd.api.types.is_numeric_dtype(x.dtype): raise OrderBlockDataError("OHLC dtype")
   if not np.isfinite(x.to_numpy(float,na_value=np.nan)).all(): raise OrderBlockDataError("OHLC nonfinite")
  o,h,l,c=[df[x].to_numpy(float) for x in ("open","high","low","close")]
  if (h<l).any() or ((o<l)|(o>h)|(c<l)|(c>h)).any(): raise OrderBlockDataError("OHLC geometry")
  for name in ("swing_high_confirmed","swing_low_confirmed","high_close_breach_event","low_close_breach_event"):
   x=df[name]
   if not pd.api.types.is_bool_dtype(x.dtype) or x.isna().any(): raise OrderBlockDataError(f"{name} must be non-missing boolean")
  hf=df.swing_high_confirmed.to_numpy(bool);lf=df.swing_low_confirmed.to_numpy(bool)
  if (hf&lf).any(): raise OrderBlockDataError("simultaneous swing")
  n=len(df)
  for i in range(n):
   if hf[i] or lf[i]:
    for name in ("swing_origin_position","swing_confirmation_position"):
     v=df[name].iloc[i]
     if pd.isna(v) or isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,np.integer)): raise OrderBlockDataError(f"invalid {name}")
    org=int(df.swing_origin_position.iloc[i]);conf=int(df.swing_confirmation_position.iloc[i])
    if org<0 or org>i or conf!=i or org>conf: raise OrderBlockDataError("invalid swing positions")
    price=df.swing_price.iloc[i]
    if pd.isna(price) or not math.isfinite(float(price)): raise OrderBlockDataError("invalid swing price")
   else:
    for name in ("swing_origin_position","swing_confirmation_position","swing_price"):
     if not pd.isna(df[name].iloc[i]): raise OrderBlockDataError("non-event swing metadata must be missing")
  allowed={"NONE","BOS_UP","BOS_DOWN","CHOCH_UP","CHOCH_DOWN","UNCLASSIFIED_BREAK","AMBIGUOUS_DOUBLE_BREAK"};states={"UP_STRUCTURE","DOWN_STRUCTURE","MIXED","UNDEFINED"}
  for i in range(n):
   ev=str(df.structural_break_event.iloc[i]);state=str(df.structure_state_before.iloc[i]);hi=bool(df.high_close_breach_event.iloc[i]);lo=bool(df.low_close_breach_event.iloc[i])
   if ev not in allowed or state not in states: raise OrderBlockDataError("bad structural event/state")
   if hi and lo:
    if ev!="AMBIGUOUS_DOUBLE_BREAK": raise OrderBlockDataError("double close break must be ambiguous")
   elif not hi and not lo:
    if ev!="NONE": raise OrderBlockDataError("structural event without close break")
   elif state=="UP_STRUCTURE":
    expected="BOS_UP" if hi else "CHOCH_DOWN"
    if ev!=expected: raise OrderBlockDataError("event incompatible with UP_STRUCTURE")
   elif state=="DOWN_STRUCTURE":
    expected="CHOCH_UP" if hi else "BOS_DOWN"
    if ev!=expected: raise OrderBlockDataError("event incompatible with DOWN_STRUCTURE")
   else:
    if ev!="UNCLASSIFIED_BREAK": raise OrderBlockDataError("directional event requires defined structure")

 @staticmethod
 def _empty_events():
  d={c:pd.Series([],dtype="float64") for c in _EVENT_COLS}
  for c in ("event_position","zone_id","origin_position","creation_position","search_boundary_position","displacement_history_count","origin_prior_use_count","zone_age_bars"): d[c]=pd.array([],dtype="Int64")
  for c in ("direction","event_type","source_break_event"): d[c]=pd.array([],dtype="string")
  return pd.DataFrame(d)[list(_EVENT_COLS)]

 def analyze(self,df):
  self._validate(df);n=len(df);o,h,l,c=[df[x].to_numpy(float) for x in ("open","high","low","close")]
  created=np.zeros(n,bool); zid=pd.array([pd.NA]*n,dtype="Int64");direction=np.full(n,"NONE",object);origin=pd.array([pd.NA]*n,dtype="Int64");creation=pd.array([pd.NA]*n,dtype="Int64");zl=np.full(n,np.nan);zh=np.full(n,np.nan);bl=np.full(n,np.nan);bh=np.full(n,np.nan);source=np.full(n,"NONE",object);uses=np.zeros(n,np.int64);disp=np.full(n,np.nan);dpct=np.full(n,np.nan);dn=np.zeros(n,np.int64);boundary=pd.array([pd.NA]*n,dtype="Int64");oppcount=np.zeros(n,np.int64)
  names=("bull_touch","bear_touch","bull_wick","bear_wick","bull_close","bear_close","bull_reclaim","bear_reclaim");counts={x:np.zeros(n,np.int64) for x in names};known_b=np.zeros(n,np.int64);known_s=np.zeros(n,np.int64)
  zones=[];events=[];prior_high=[];prior_low=[];origin_uses={};tracker=CausalPercentileTracker(nan_policy="skip")
  def emit(i,z,t): events.append(dict(event_position=i,zone_id=z.id,direction=z.direction,event_type=t,origin_position=z.origin,creation_position=z.creation,search_boundary_position=z.boundary,source_break_event=z.source,full_zone_low=z.low,full_zone_high=z.high,body_low=z.body_low,body_high=z.body_high,event_high=h[i],event_low=l[i],event_close=c[i],displacement_fraction=z.displacement,displacement_percentile=z.displacement_pct,displacement_history_count=z.displacement_n,origin_prior_use_count=z.prior_use,zone_age_bars=i-z.creation,_order=_EVENT_ORDER[t]))
  for i in range(n):
   for z in zones:
    overlap=h[i]>=z.low and l[i]<=z.high; bull=z.direction.startswith("BULLISH");p="bull" if bull else "bear"
    wick=l[i]<z.low if bull else h[i]>z.high;closed=c[i]<z.low if bull else c[i]>z.high
    if z.touch is None and overlap: z.touch=i;counts[p+"_touch"][i]+=1;emit(i,z,"FIRST_TOUCH")
    if z.wick is None and wick: z.wick=i;counts[p+"_wick"][i]+=1;emit(i,z,"FIRST_FAR_SIDE_WICK_BREACH")
    if z.close is None and closed: z.close=i;counts[p+"_close"][i]+=1;emit(i,z,"FIRST_FAR_SIDE_CLOSE_BREACH")
    if z.close is not None and i>z.close and z.reclaim is None:
     reclaimed=c[i]>=z.low if bull else c[i]<=z.high
     if reclaimed:z.reclaim=i;counts[p+"_reclaim"][i]+=1;emit(i,z,"FIRST_CLOSE_RECLAIM_OF_FAR_SIDE")
   sb=str(df.structural_break_event.iloc[i])
   if sb in _DIRECTIONAL:
    bull=_DIRECTIONAL[sb].startswith("BULLISH");swings=prior_low if bull else prior_high
    if swings:
     bpos=swings[-1][0]; eligible=[j for j in range(bpos,i) if (c[j]<o[j] if bull else c[j]>o[j])]
     if eligible:
      org=eligible[-1];lowz=l[org];highz=h[org];bodylo=min(o[org],c[org]);bodyhi=max(o[org],c[org]);den=abs(highz if bull else lowz);raw=max(c[i]-highz,0) if bull else max(lowz-c[i],0);d=float("nan") if den==0 else raw/den;obs=tracker.rank(d);use=origin_uses.get(org,0)
      z=_Zone(len(zones),_DIRECTIONAL[sb],org,i,bpos,sb,lowz,highz,bodylo,bodyhi,d,obs.percentile,obs.sample_count,use);origin_uses[org]=use+1;zones.append(z);emit(i,z,"ZONE_CREATED")
      if math.isfinite(d):tracker.push(d)
      created[i]=True;zid[i]=z.id;direction[i]=z.direction;origin[i]=org;creation[i]=i;zl[i]=lowz;zh[i]=highz;bl[i]=bodylo;bh[i]=bodyhi;source[i]=sb;uses[i]=use;disp[i]=d;dpct[i]=obs.percentile;dn[i]=obs.sample_count;boundary[i]=bpos;oppcount[i]=len(eligible)
   # current swings become boundary knowledge only after creation processing
   if bool(df.swing_high_confirmed.iloc[i]): prior_high.append((int(df.swing_origin_position.iloc[i]),i))
   if bool(df.swing_low_confirmed.iloc[i]): prior_low.append((int(df.swing_origin_position.iloc[i]),i))
   known_b[i]=sum(z.direction.startswith("BULLISH") for z in zones);known_s[i]=len(zones)-known_b[i]
  out=df.copy(deep=True);vals=(created,zid,pd.array(direction,dtype="string"),origin,creation,zl,zh,bl,bh,pd.array(source,dtype="string"),uses,disp,dpct,dn,boundary,oppcount,counts["bull_touch"],counts["bear_touch"],counts["bull_wick"],counts["bear_wick"],counts["bull_close"],counts["bear_close"],counts["bull_reclaim"],counts["bear_reclaim"],known_b,known_s)
  for name,val in zip(_BAR_COLS,vals):out[name]=val
  if not events:return out,self._empty_events()
  ev=pd.DataFrame(events).sort_values(["event_position","zone_id","_order"],kind="stable").drop(columns="_order").reset_index(drop=True)
  for x in ("event_position","zone_id","origin_position","creation_position","search_boundary_position","displacement_history_count","origin_prior_use_count","zone_age_bars"):ev[x]=pd.array(ev[x],dtype="Int64")
  for x in ("direction","event_type","source_break_event"):ev[x]=pd.array(ev[x],dtype="string")
  return out,ev[list(_EVENT_COLS)]

class _OrderBlockAuditEngine(CausalOrderBlockEngine):pass

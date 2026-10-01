"""Layer 4 Module 4.2A — Causal FVG Candidate & Lifecycle Engine V1.1.
Strict three-bar geometry; immutable independent candidates; monitoring begins
after creation. `FIRST_CLOSE_RECLAIM_OF_FAR_SIDE` means only that a subsequent
close returned across the far-side boundary; it requires no zone touch,
traversal, retest, near-side reclaim, or IFVG interpretation. Facts do not prove
institutional inefficiency or future fill.
"""
from dataclasses import dataclass
from typing import Optional
import math,numpy as np,pandas as pd
from trading_system.core.causal_percentile import CausalPercentileTracker
class FVGError(Exception):pass
class FVGDataError(FVGError):pass
_ORDER={"FVG_CREATED":0,"FIRST_TOUCH":1,"FIRST_FULL_RANGE_COVERAGE":2,"FIRST_FAR_SIDE_WICK_BREACH":3,"FIRST_FAR_SIDE_CLOSE_BREACH":4,"FIRST_CLOSE_RECLAIM_OF_FAR_SIDE":5}
@dataclass
class _F:
 id:int;direction:str;origin:int;middle:int;creation:int;low:float;high:float;mid:float;width:float;frac:float;pct:float;n:int;body:float;sbody:float;touch:Optional[int]=None;coverage:Optional[int]=None;wick:Optional[int]=None;close:Optional[int]=None;reclaim:Optional[int]=None
_BAR=("fvg_candidate_created","created_fvg_id","created_fvg_direction","created_fvg_origin_position","created_fvg_middle_position","created_fvg_creation_position","created_fvg_zone_low","created_fvg_zone_high","created_fvg_midpoint","created_fvg_gap_width","created_fvg_gap_width_fraction","created_fvg_gap_width_percentile","created_fvg_gap_width_history_count","created_fvg_middle_body_fraction","created_fvg_middle_signed_body_fraction","bullish_fvg_first_touch_count","bearish_fvg_first_touch_count","bullish_fvg_first_full_range_coverage_count","bearish_fvg_first_full_range_coverage_count","bullish_fvg_first_far_side_wick_breach_count","bearish_fvg_first_far_side_wick_breach_count","bullish_fvg_first_far_side_close_breach_count","bearish_fvg_first_far_side_close_breach_count","bullish_fvg_first_close_reclaim_count","bearish_fvg_first_close_reclaim_count","known_bullish_fvg_candidate_count","known_bearish_fvg_candidate_count")
_E=("event_position","fvg_id","direction","event_type","origin_position","middle_position","creation_position","zone_low","zone_high","midpoint","gap_width","gap_width_fraction","gap_width_percentile","gap_width_history_count","middle_body_fraction","middle_signed_body_fraction","event_high","event_low","event_close","zone_range_coverage_fraction","fvg_age_bars")
class CausalFVGEngine:
 @staticmethod
 def _validate(d):
  if not isinstance(d,pd.DataFrame) or d.columns.has_duplicates:raise FVGDataError("bad frame")
  if any(x not in d for x in ("open","high","low","close")):raise FVGDataError("missing OHLC")
  if any(x in d for x in _BAR):raise FVGDataError("collision")
  if d.index.has_duplicates or not d.index.is_monotonic_increasing:raise FVGDataError("index")
  for x in ("open","high","low","close"):
   s=d[x]
   if pd.api.types.is_bool_dtype(s.dtype) or pd.api.types.is_complex_dtype(s.dtype) or not pd.api.types.is_numeric_dtype(s.dtype) or not np.isfinite(s.to_numpy(float,na_value=np.nan)).all():raise FVGDataError("OHLC")
  o,h,l,c=[d[x].to_numpy(float) for x in ("open","high","low","close")]
  if (h<l).any() or ((o<l)|(o>h)|(c<l)|(c>h)).any():raise FVGDataError("geometry")
 @staticmethod
 def _empty():
  d={x:pd.Series([],dtype=float) for x in _E}
  for x in ("event_position","fvg_id","origin_position","middle_position","creation_position","gap_width_history_count","fvg_age_bars"):d[x]=pd.array([],dtype="Int64")
  for x in ("direction","event_type"):d[x]=pd.array([],dtype="string")
  return pd.DataFrame(d)[list(_E)]
 def analyze(self,d):
  self._validate(d);n=len(d);o,h,l,c=[d[x].to_numpy(float) for x in ("open","high","low","close")];fs=[];ev=[];tr=CausalPercentileTracker(nan_policy="skip")
  created=np.zeros(n,bool);ids=pd.array([pd.NA]*n,dtype="Int64");dire=np.full(n,"NONE",object);op=pd.array([pd.NA]*n,dtype="Int64");mp=pd.array([pd.NA]*n,dtype="Int64");cp=pd.array([pd.NA]*n,dtype="Int64");arrays=[np.full(n,np.nan) for _ in range(8)];zl,zh,mid,wid,frac,pct,body,sbody=arrays;hn=np.zeros(n,np.int64)
  names=("bt","st","bc","sc","bw","sw","bx","sx","br","sr");counts={x:np.zeros(n,np.int64) for x in names};kb=np.zeros(n,np.int64);ks=np.zeros(n,np.int64);kb_run=0;ks_run=0
  def emit(i,f,t,cov=np.nan):ev.append(dict(event_position=i,fvg_id=f.id,direction=f.direction,event_type=t,origin_position=f.origin,middle_position=f.middle,creation_position=f.creation,zone_low=f.low,zone_high=f.high,midpoint=f.mid,gap_width=f.width,gap_width_fraction=f.frac,gap_width_percentile=f.pct,gap_width_history_count=f.n,middle_body_fraction=f.body,middle_signed_body_fraction=f.sbody,event_high=h[i],event_low=l[i],event_close=c[i],zone_range_coverage_fraction=cov,fvg_age_bars=i-f.creation,_o=_ORDER[t]))
  for i in range(n):
   if i>=2:
    bullish=l[i]>h[i-2];bearish=h[i]<l[i-2]
    if bullish and bearish:raise FVGDataError("impossible dual geometry")
    if bullish or bearish:
     lowz=h[i-2] if bullish else h[i];highz=l[i] if bullish else l[i-2]
     if not math.isfinite(lowz) or not math.isfinite(highz) or not highz>lowz:raise FVGDataError("invalid derived zone")
     with np.errstate(over="ignore",invalid="ignore"):width=highz-lowz
     if not math.isfinite(width) or width<=0:raise FVGDataError("gap width overflow")
     midpoint=lowz+width/2.0
     if not math.isfinite(midpoint):raise FVGDataError("midpoint overflow")
     den=max(abs(lowz),abs(highz));fr=np.nan if den==0 else width/den
     if den>0 and not math.isfinite(fr):raise FVGDataError("width fraction overflow")
     obs=tr.rank(fr);mr=h[i-1]-l[i-1]
     if not math.isfinite(mr) or mr<0:raise FVGDataError("middle range overflow")
     bf=np.nan if mr==0 else abs(c[i-1]-o[i-1])/mr;sbf=np.nan if mr==0 else (c[i-1]-o[i-1])/mr
     if mr>0 and (not math.isfinite(bf) or not math.isfinite(sbf)):raise FVGDataError("middle fraction overflow")
     f=_F(len(fs),"BULLISH_FVG_CANDIDATE" if bullish else "BEARISH_FVG_CANDIDATE",i-2,i-1,i,lowz,highz,midpoint,width,fr,obs.percentile,obs.sample_count,bf,sbf);fs.append(f);kb_run+=f.direction.startswith("BULLISH");ks_run+=not f.direction.startswith("BULLISH");emit(i,f,"FVG_CREATED");
     if math.isfinite(fr):tr.push(fr)
     created[i]=True;ids[i]=f.id;dire[i]=f.direction;op[i]=i-2;mp[i]=i-1;cp[i]=i;zl[i]=lowz;zh[i]=highz;mid[i]=f.mid;wid[i]=width;frac[i]=fr;pct[i]=obs.percentile;hn[i]=obs.sample_count;body[i]=bf;sbody[i]=sbf
   kb[i]=kb_run;ks[i]=ks_run
  # ------------------------------------------------------------------
  # EXACT PERFORMANCE V2 PATCH-2b: per-entity first-occurrence lifecycle.
  #
  # Historical per-bar scan semantics are preserved exactly: each lifecycle
  # slot fires at its FIRST matching bar (strict/non-strict comparisons kept
  # verbatim), reclaim only after the close event and strictly later bars,
  # coverage carries cov=1., other events carry the overlap cov formula at
  # the event bar. The events frame is canonically sorted by
  # (event_position, fvg_id, _o) with UNIQUE keys, so emission order is not
  # part of the output contract. Verified by the old-vs-new differential
  # battery in tests/test_fvg.py.
  # ------------------------------------------------------------------
  def first_true(mask):
   k=int(np.argmax(mask))
   return k if mask[k] else -1
  for f in fs:
   base=f.creation+1
   if base>=n:continue
   bull=f.direction.startswith("BULLISH");p="b" if bull else "s"
   lo=f.low;hi=f.high;w=f.width
   hv=h[base:];lv=l[base:];cv=c[base:]
   overlap=(hv>=lo)&(lv<=hi);full=(lv<=lo)&(hv>=hi)
   wickc=(lv<lo) if bull else (hv>hi);closedc=(cv<lo) if bull else (cv>hi)
   recc=(cv>=lo) if bull else (cv<=hi)
   def cov_at(rel):
    if not overlap[rel]:return np.nan
    j=base+rel
    return (min(h[j],hi)-max(l[j],lo))/w
   k=first_true(overlap)
   if k>=0:f.touch=base+k;counts[p+"t"][base+k]+=1;emit(base+k,f,"FIRST_TOUCH",cov_at(k))
   k=first_true(full)
   if k>=0:f.coverage=base+k;counts[p+"c"][base+k]+=1;emit(base+k,f,"FIRST_FULL_RANGE_COVERAGE",1.)
   k=first_true(wickc)
   if k>=0:f.wick=base+k;counts[p+"w"][base+k]+=1;emit(base+k,f,"FIRST_FAR_SIDE_WICK_BREACH",cov_at(k))
   k=first_true(closedc)
   if k>=0:
    f.close=base+k;counts[p+"x"][base+k]+=1;emit(base+k,f,"FIRST_FAR_SIDE_CLOSE_BREACH",cov_at(k))
    tail=recc[k+1:]
    if tail.size:
     r=first_true(tail)
     if r>=0:
      rr=k+1+r;f.reclaim=base+rr;counts[p+"r"][base+rr]+=1;emit(base+rr,f,"FIRST_CLOSE_RECLAIM_OF_FAR_SIDE",cov_at(rr))
  out=d.copy();vals=(created,ids,pd.array(dire,dtype="string"),op,mp,cp,zl,zh,mid,wid,frac,pct,hn,body,sbody,counts["bt"],counts["st"],counts["bc"],counts["sc"],counts["bw"],counts["sw"],counts["bx"],counts["sx"],counts["br"],counts["sr"],kb,ks)
  for x,v in zip(_BAR,vals):out[x]=v
  if not ev:return out,self._empty()
  e=pd.DataFrame(ev).sort_values(["event_position","fvg_id","_o"],kind="stable").drop(columns="_o").reset_index(drop=True)
  for x in ("event_position","fvg_id","origin_position","middle_position","creation_position","gap_width_history_count","fvg_age_bars"):e[x]=pd.array(e[x],dtype="Int64")
  for x in ("direction","event_type"):e[x]=pd.array(e[x],dtype="string")
  return out,e[list(_E)]
class _FVGAuditEngine(CausalFVGEngine):pass

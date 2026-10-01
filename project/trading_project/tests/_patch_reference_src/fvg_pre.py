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
  names=("bt","st","bc","sc","bw","sw","bx","sx","br","sr");counts={x:np.zeros(n,np.int64) for x in names};kb=np.zeros(n,np.int64);ks=np.zeros(n,np.int64)
  def emit(i,f,t,cov=np.nan):ev.append(dict(event_position=i,fvg_id=f.id,direction=f.direction,event_type=t,origin_position=f.origin,middle_position=f.middle,creation_position=f.creation,zone_low=f.low,zone_high=f.high,midpoint=f.mid,gap_width=f.width,gap_width_fraction=f.frac,gap_width_percentile=f.pct,gap_width_history_count=f.n,middle_body_fraction=f.body,middle_signed_body_fraction=f.sbody,event_high=h[i],event_low=l[i],event_close=c[i],zone_range_coverage_fraction=cov,fvg_age_bars=i-f.creation,_o=_ORDER[t]))
  for i in range(n):
   for f in fs:
    overlap=h[i]>=f.low and l[i]<=f.high;cov=np.nan
    if overlap:cov=(min(h[i],f.high)-max(l[i],f.low))/f.width
    bull=f.direction.startswith("BULLISH");p="b" if bull else "s";full=l[i]<=f.low and h[i]>=f.high;wick=l[i]<f.low if bull else h[i]>f.high;closed=c[i]<f.low if bull else c[i]>f.high
    if f.touch is None and overlap:f.touch=i;counts[p+"t"][i]+=1;emit(i,f,"FIRST_TOUCH",cov)
    if f.coverage is None and full:f.coverage=i;counts[p+"c"][i]+=1;emit(i,f,"FIRST_FULL_RANGE_COVERAGE",1.)
    if f.wick is None and wick:f.wick=i;counts[p+"w"][i]+=1;emit(i,f,"FIRST_FAR_SIDE_WICK_BREACH",cov)
    if f.close is None and closed:f.close=i;counts[p+"x"][i]+=1;emit(i,f,"FIRST_FAR_SIDE_CLOSE_BREACH",cov)
    if f.close is not None and i>f.close and f.reclaim is None and (c[i]>=f.low if bull else c[i]<=f.high):f.reclaim=i;counts[p+"r"][i]+=1;emit(i,f,"FIRST_CLOSE_RECLAIM_OF_FAR_SIDE",cov)
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
     f=_F(len(fs),"BULLISH_FVG_CANDIDATE" if bullish else "BEARISH_FVG_CANDIDATE",i-2,i-1,i,lowz,highz,midpoint,width,fr,obs.percentile,obs.sample_count,bf,sbf);fs.append(f);emit(i,f,"FVG_CREATED");
     if math.isfinite(fr):tr.push(fr)
     created[i]=True;ids[i]=f.id;dire[i]=f.direction;op[i]=i-2;mp[i]=i-1;cp[i]=i;zl[i]=lowz;zh[i]=highz;mid[i]=f.mid;wid[i]=width;frac[i]=fr;pct[i]=obs.percentile;hn[i]=obs.sample_count;body[i]=bf;sbody[i]=sbf
   kb[i]=sum(x.direction.startswith("BULLISH") for x in fs);ks[i]=len(fs)-kb[i]
  out=d.copy();vals=(created,ids,pd.array(dire,dtype="string"),op,mp,cp,zl,zh,mid,wid,frac,pct,hn,body,sbody,counts["bt"],counts["st"],counts["bc"],counts["sc"],counts["bw"],counts["sw"],counts["bx"],counts["sx"],counts["br"],counts["sr"],kb,ks)
  for x,v in zip(_BAR,vals):out[x]=v
  if not ev:return out,self._empty()
  e=pd.DataFrame(ev).sort_values(["event_position","fvg_id","_o"],kind="stable").drop(columns="_o").reset_index(drop=True)
  for x in ("event_position","fvg_id","origin_position","middle_position","creation_position","gap_width_history_count","fvg_age_bars"):e[x]=pd.array(e[x],dtype="Int64")
  for x in ("direction","event_type"):e[x]=pd.array(e[x],dtype="string")
  return out,e[list(_E)]
class _FVGAuditEngine(CausalFVGEngine):pass

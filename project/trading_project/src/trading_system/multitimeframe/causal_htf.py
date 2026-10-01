"""Layer 5 — Module 5.1: Causal Higher-Timeframe Aggregator V1.1.

Fixed-duration buckets live on the absolute UTC nanosecond timeline and use
CLOSE_TIME intervals `(start, end]`. Exact boundaries belong to the bucket
ending at that instant. Aggregation uses observed source bars only; source
coverage completeness is unknown without a cadence contract.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import numpy as np,pandas as pd

class HTFError(Exception):pass
class HTFConfigError(HTFError):pass
class HTFDataError(HTFError):pass
class BarTimestampSemantics(Enum): CLOSE_TIME="CLOSE_TIME"
@dataclass(frozen=True)
class TimeAggregationSpec:
 duration:pd.Timedelta
 timestamp_semantics:BarTimestampSemantics=BarTimestampSemantics.CLOSE_TIME
 def __post_init__(self):
  if not isinstance(self.duration,pd.Timedelta) or pd.isna(self.duration) or self.duration<=pd.Timedelta(0):raise HTFConfigError("duration must be positive Timedelta")
  if self.duration.value<=0:raise HTFConfigError("invalid duration")
  if self.timestamp_semantics is not BarTimestampSemantics.CLOSE_TIME:raise HTFConfigError("V1 supports CLOSE_TIME only")

_ASOF=("last_completed_htf_end_utc","last_completed_htf_open","last_completed_htf_high","last_completed_htf_low","last_completed_htf_close","last_completed_htf_source_bar_count")
class CausalHTFAggregator:
 def __init__(self,*,spec:TimeAggregationSpec):
  if not isinstance(spec,TimeAggregationSpec):raise HTFConfigError("explicit spec required")
  self.spec=spec
 @staticmethod
 def _bucket_end_ns(ns:int,d:int)->int:
  q,r=divmod(int(ns),int(d));end=q*d if r==0 else (q+1)*d
  if end<np.iinfo(np.int64).min or end>np.iinfo(np.int64).max:raise HTFDataError("bucket arithmetic overflow")
  return end
 def _validate(self,df):
  if not isinstance(df,pd.DataFrame) or df.columns.has_duplicates:raise HTFDataError("bad frame")
  if not isinstance(df.index,pd.DatetimeIndex) or df.index.tz is None or df.index.hasnans:raise HTFDataError("timezone-aware DatetimeIndex required")
  if df.index.has_duplicates or not df.index.is_monotonic_increasing:raise HTFDataError("index order")
  for x in ("open","high","low","close"):
   if x not in df:raise HTFDataError("missing OHLC")
   s=df[x]
   if pd.api.types.is_bool_dtype(s.dtype) or pd.api.types.is_complex_dtype(s.dtype) or not pd.api.types.is_numeric_dtype(s.dtype) or not np.isfinite(s.to_numpy(float,na_value=np.nan)).all():raise HTFDataError("OHLC")
  reserved=_ASOF+(("last_completed_htf_volume",) if "volume" in df else ())
  if any(x in df for x in reserved):raise HTFDataError("output collision")
  o,h,l,c=[df[x].to_numpy(float) for x in ("open","high","low","close")]
  if (h<l).any() or ((o<l)|(o>h)|(c<l)|(c>h)).any():raise HTFDataError("geometry")
  if "volume" in df:
   s=df.volume
   if pd.api.types.is_bool_dtype(s.dtype) or pd.api.types.is_complex_dtype(s.dtype) or not pd.api.types.is_numeric_dtype(s.dtype):raise HTFDataError("volume")
   v=s.to_numpy(float,na_value=np.nan)
   if not np.isfinite(v).all() or (v<0).any():raise HTFDataError("volume")
 def analyze(self,df):
  self._validate(df);n=len(df);out=df.copy(deep=True);out.index=pd.DatetimeIndex(df.index,freq=None);hasv="volume" in df
  cols={x:np.full(n,np.nan) for x in _ASOF[1:5]};count=np.zeros(n,np.int64);ends_obj=np.array([pd.NaT]*n,dtype=object)
  if n==0:
   out[_ASOF[0]]=pd.Series(pd.array([],dtype="datetime64[ns, UTC]"),index=out.index)
   for x in _ASOF[1:5]:out[x]=cols[x]
   out[_ASOF[5]]=count
   return out,self._empty(hasv)
  utc=df.index.tz_convert("UTC");d=int(self.spec.duration.value);end_ns=np.array([self._bucket_end_ns(x,d) for x in utc.asi8],dtype=np.int64);last=int(utc.asi8[-1]);rows=[]
  for end in np.unique(end_ns):
   if end>last:continue
   pos=np.flatnonzero(end_ns==end);vol=float(df.volume.iloc[pos].sum()) if hasv else None
   if hasv and not np.isfinite(vol):raise HTFDataError("volume sum overflow")
   avail=int(np.searchsorted(utc.asi8,end,side="left"));row=dict(bucket_start_utc=pd.Timestamp(end-d,tz="UTC"),bucket_end_utc=pd.Timestamp(end,tz="UTC"),theoretical_available_at=pd.Timestamp(end,tz="UTC"),first_observed_asof_position=avail,first_observed_asof_time=utc[avail],first_source_timestamp=utc[pos[0]],last_source_timestamp=utc[pos[-1]],source_bar_count=len(pos),open=float(df.open.iloc[pos[0]]),high=float(df.high.iloc[pos].max()),low=float(df.low.iloc[pos].min()),close=float(df.close.iloc[pos[-1]]))
   if hasv:row["volume"]=vol
   rows.append(row)
  table=pd.DataFrame(rows)
  if rows:
   table["first_observed_asof_position"]=pd.array(table["first_observed_asof_position"],dtype="Int64");table["source_bar_count"]=pd.array(table["source_bar_count"],dtype="Int64")
   table.index=pd.DatetimeIndex(table.bucket_end_utc,name="bucket_end_utc",freq=None);completed_ends=table.bucket_end_utc.array.asi8
   for i,t in enumerate(utc.asi8):
    j=np.searchsorted(completed_ends,t,side="right")-1
    if j>=0:
     r=table.iloc[j];ends_obj[i]=r.bucket_end_utc;cols[_ASOF[1]][i]=r.open;cols[_ASOF[2]][i]=r.high;cols[_ASOF[3]][i]=r.low;cols[_ASOF[4]][i]=r.close;count[i]=r.source_bar_count
  else:table=self._empty(hasv)
  out[_ASOF[0]]=pd.array(ends_obj,dtype="datetime64[ns, UTC]")
  for x in _ASOF[1:5]:out[x]=cols[x]
  out[_ASOF[5]]=count
  if hasv:
   vv=np.full(n,np.nan)
   if rows:
    for i,t in enumerate(utc.asi8):
     j=np.searchsorted(completed_ends,t,side="right")-1
     if j>=0:vv[i]=table.iloc[j].volume
   out["last_completed_htf_volume"]=vv
  return out,table
 @staticmethod
 def _empty(hasv):
  names=("bucket_start_utc","bucket_end_utc","theoretical_available_at","first_observed_asof_time","first_source_timestamp","last_source_timestamp")
  d={x:pd.Series(pd.array([],dtype="datetime64[ns, UTC]")) for x in names};d["first_observed_asof_position"]=pd.array([],dtype="Int64");d["source_bar_count"]=pd.array([],dtype="Int64")
  for x in ("open","high","low","close")+( ("volume",) if hasv else () ):d[x]=pd.Series([],dtype=float)
  order=("bucket_start_utc","bucket_end_utc","theoretical_available_at","first_observed_asof_position","first_observed_asof_time","first_source_timestamp","last_source_timestamp","source_bar_count","open","high","low","close")+(("volume",) if hasv else ());z=pd.DataFrame(d)[list(order)];z.index=pd.DatetimeIndex([],tz="UTC",name="bucket_end_utc");return z
class _HTFAuditEngine(CausalHTFAggregator):
 def __init__(self):super().__init__(spec=TimeAggregationSpec(pd.Timedelta(minutes=5)))

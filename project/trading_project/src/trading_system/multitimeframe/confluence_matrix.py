"""Layer 5 Module 5.2 — causal factual multi-scale confluence matrix V1."""
from dataclasses import dataclass
import re,math,numpy as np,pandas as pd
class ConfluenceError(Exception):pass
class ConfluenceDataError(ConfluenceError):pass
@dataclass(frozen=True)
class ScaleFrame:
 name:str
 frame:pd.DataFrame
 def __post_init__(self):
  if not isinstance(self.name,str) or re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',self.name) is None:raise ConfluenceDataError('unsafe scale name')
  if not isinstance(self.frame,pd.DataFrame):raise ConfluenceDataError('ScaleFrame.frame must be DataFrame')

def causal_asof_align_scale_state(decision_index,completed_scale_frame,available_at_column='available_at',state_column='structure_state_after'):
 if not isinstance(decision_index,pd.DatetimeIndex) or decision_index.tz is None or decision_index.hasnans or decision_index.has_duplicates or not decision_index.is_monotonic_increasing:raise ConfluenceDataError('invalid decision index')
 if not isinstance(completed_scale_frame,pd.DataFrame) or completed_scale_frame.columns.has_duplicates:raise ConfluenceDataError('invalid completed frame')
 c=completed_scale_frame
 if available_at_column not in c or state_column not in c:raise ConfluenceDataError('completed schema')
 a=c[available_at_column]
 if not isinstance(a.dtype,pd.DatetimeTZDtype) or a.isna().any() or not a.is_monotonic_increasing or a.duplicated().any():raise ConfluenceDataError('availability')
 allowed={'UNDEFINED','UP_STRUCTURE','DOWN_STRUCTURE','MIXED'}
 if c[state_column].isna().any() or not c[state_column].astype(str).isin(allowed).all():raise ConfluenceDataError('completed state')
 ans=np.array([pd.NaT]*len(decision_index),object);states=np.array([pd.NA]*len(decision_index),object);av=np.zeros(len(decision_index),bool);ns=a.array.asi8
 for i,t in enumerate(decision_index.tz_convert('UTC').asi8):
  j=np.searchsorted(ns,t,side='right')-1
  if j>=0:av[i]=True;ans[i]=a.iloc[j];states[i]=c[state_column].iloc[j]
 return pd.DataFrame({'available':av,'source_available_at':pd.array(ans,dtype='datetime64[ns, UTC]'),'structure_state_after':pd.array(states,dtype='string')},index=decision_index)

class CausalConfluenceMatrixEngine:
 def analyze(self,decision_df,scales):
  if not isinstance(decision_df,pd.DataFrame) or not isinstance(decision_df.index,pd.DatetimeIndex) or decision_df.index.tz is None or decision_df.index.hasnans or decision_df.index.has_duplicates or not decision_df.index.is_monotonic_increasing:raise ConfluenceDataError('decision frame')
  scales=tuple(scales)
  if not scales:raise ConfluenceDataError('at least one scale')
  if len({s.name for s in scales})!=len(scales):raise ConfluenceDataError('duplicate scale')
  aggregate=('configured_scale_count','available_scale_count','unavailable_scale_count','up_structure_count','down_structure_count','mixed_structure_count','undefined_structure_count','directional_scale_count','availability_fraction','directional_fraction','directional_balance','directional_consensus','directional_conflict')
  generated=list(aggregate)
  for s in scales:generated += [f'{s.name}__available',f'{s.name}__source_available_at',f'{s.name}__structure_state',f'{s.name}__structure_direction_code',f'{s.name}__information_age_seconds']
  if len(generated)!=len(set(generated)) or any(x in decision_df.columns for x in generated):raise ConfluenceDataError('output collision')
  n=len(decision_df);out=decision_df.copy(deep=True);up=np.zeros(n,int);down=np.zeros(n,int);mixed=np.zeros(n,int);undef=np.zeros(n,int);avail_count=np.zeros(n,int)
  for s in scales:
   if not isinstance(s,ScaleFrame) or not s.frame.index.equals(decision_df.index):raise ConfluenceDataError('scale/index')
   f=s.frame
   if f.columns.has_duplicates:raise ConfluenceDataError('duplicate scale columns')
   if any(x not in f for x in ('available','source_available_at','structure_state_after')):raise ConfluenceDataError('scale schema')
   if not pd.api.types.is_bool_dtype(f.available.dtype) or f.available.isna().any() or not isinstance(f.source_available_at.dtype,pd.DatetimeTZDtype):raise ConfluenceDataError('scale dtype')
   available=f.available.to_numpy(bool);ages=np.full(n,np.nan);codes=np.full(n,np.nan);last=None;laststate=None
   for i in range(n):
    state=f.structure_state_after.iloc[i]
    if not available[i]:
     if not pd.isna(f.source_available_at.iloc[i]) or not pd.isna(state):raise ConfluenceDataError('unavailable metadata')
     continue
    t=f.source_available_at.iloc[i]
    if pd.isna(t) or t>decision_df.index[i]:raise ConfluenceDataError('future availability')
    if last is not None and t<last:raise ConfluenceDataError('backward provenance')
    if last is not None and t==last and state!=laststate:raise ConfluenceDataError('repainted state')
    if state not in ('UNDEFINED','UP_STRUCTURE','DOWN_STRUCTURE','MIXED'):raise ConfluenceDataError('state')
    age=(decision_df.index[i].tz_convert('UTC').value-t.tz_convert('UTC').value)/1e9
    if not math.isfinite(age) or age<0:raise ConfluenceDataError('age')
    ages[i]=age;avail_count[i]+=1
    if state=='UP_STRUCTURE':up[i]+=1;codes[i]=1
    elif state=='DOWN_STRUCTURE':down[i]+=1;codes[i]=-1
    elif state=='MIXED':mixed[i]+=1;codes[i]=0
    else:undef[i]+=1
    last=t;laststate=state
   for col,val in ((f'{s.name}__available',available),(f'{s.name}__source_available_at',f.source_available_at),(f'{s.name}__structure_state',f.structure_state_after),(f'{s.name}__structure_direction_code',codes),(f'{s.name}__information_age_seconds',ages)):
    if col in out:raise ConfluenceDataError('output collision')
    out[col]=val
  total=len(scales);directional=up+down;balance=np.divide(up-down,directional,out=np.full(n,np.nan),where=directional>0)
  out['configured_scale_count']=total;out['available_scale_count']=avail_count;out['unavailable_scale_count']=total-avail_count;out['up_structure_count']=up;out['down_structure_count']=down;out['mixed_structure_count']=mixed;out['undefined_structure_count']=undef;out['directional_scale_count']=directional;out['availability_fraction']=avail_count/total;out['directional_fraction']=directional/total;out['directional_balance']=balance;out['directional_consensus']=np.abs(balance);out['directional_conflict']=(up>0)&(down>0)
  return out

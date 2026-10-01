import pandas as pd,numpy as np,pytest
from trading_system.multitimeframe.confluence_matrix import *
def idx():return pd.date_range('2024-01-01',periods=3,freq='h',tz='UTC')
def sf(name,states,times=None):
 i=idx();a=np.array([x is not None for x in states]);times=times or [i[j] if a[j] else pd.NaT for j in range(3)];return ScaleFrame(name,pd.DataFrame({'available':a,'source_available_at':pd.array(times,dtype='datetime64[ns, UTC]'),'structure_state_after':pd.array(states,dtype='string')},index=i))
def test_counts_balance_availability():
 b=pd.DataFrame(index=idx());o=CausalConfluenceMatrixEngine().analyze(b,[sf('a',['UP_STRUCTURE']*3),sf('b',['DOWN_STRUCTURE']*3),sf('c',[None,'MIXED','UNDEFINED'])]);assert o.loc[idx()[0],'directional_balance']==0;assert o.loc[idx()[0],'availability_fraction']==2/3;assert o.loc[idx()[1],'directional_conflict'];assert o.loc[idx()[2],'undefined_structure_count']==1
def test_repaint_and_future_rejected():
 b=pd.DataFrame(index=idx());same=[idx()[0]]*3
 with pytest.raises(ConfluenceDataError):CausalConfluenceMatrixEngine().analyze(b,[sf('x',['UP_STRUCTURE','DOWN_STRUCTURE','DOWN_STRUCTURE'],same)])
 future=[idx()[1],idx()[1],idx()[2]]
 with pytest.raises(ConfluenceDataError):CausalConfluenceMatrixEngine().analyze(b,[sf('x',['UP_STRUCTURE']*3,future)])
def test_alignment_utility_exact_availability():
 i=idx();c=pd.DataFrame({'available_at':pd.DatetimeIndex([i[1]]),'structure_state_after':['UP_STRUCTURE']});a=causal_asof_align_scale_state(i,c);assert not a.available.iloc[0];assert a.available.iloc[1];assert a.structure_state_after.iloc[2]=='UP_STRUCTURE'
def test_ages_and_no_direction():
 b=pd.DataFrame(index=idx());o=CausalConfluenceMatrixEngine().analyze(b,[sf('x',[None,'UNDEFINED','MIXED'])]);assert np.isnan(o.directional_balance).all();assert o.loc[idx()[1],'x__information_age_seconds']==0
def test_index_names_empty_state_isolation():
 with pytest.raises(ConfluenceDataError):CausalConfluenceMatrixEngine().analyze(pd.DataFrame(index=idx()),[])
 a=sf('x',['UP_STRUCTURE']*3);e=CausalConfluenceMatrixEngine();x=e.analyze(pd.DataFrame(index=idx()),[a]);y=e.analyze(pd.DataFrame(index=idx()),[a]);pd.testing.assert_frame_equal(x,y)

def test_alignment_validation_adversarial():
 good_idx=idx();completed=pd.DataFrame({'available_at':pd.DatetimeIndex([good_idx[1]]),'structure_state_after':['UP_STRUCTURE']})
 for bad in [pd.date_range('2024',periods=2),pd.DatetimeIndex([good_idx[0],pd.NaT]),pd.DatetimeIndex([good_idx[0],good_idx[0]]),pd.DatetimeIndex([good_idx[1],good_idx[0]])]:
  with pytest.raises(ConfluenceDataError):causal_asof_align_scale_state(bad,completed)
 duplicate=pd.DataFrame({'available_at':pd.DatetimeIndex([good_idx[1],good_idx[1]]),'structure_state_after':['UP_STRUCTURE','DOWN_STRUCTURE']})
 with pytest.raises(ConfluenceDataError):causal_asof_align_scale_state(good_idx,duplicate)
 invalid=completed.copy();invalid['structure_state_after']='BAD'
 with pytest.raises(ConfluenceDataError):causal_asof_align_scale_state(good_idx,invalid)
 with pytest.raises(ConfluenceDataError):ScaleFrame('x',[]) # type: ignore

def test_multiple_frame_truncation_and_future_mutation():
 base=pd.DataFrame(index=idx());scales=[sf('a',['UP_STRUCTURE']*3),sf('b',[None,'DOWN_STRUCTURE','DOWN_STRUCTURE'])];eng=CausalConfluenceMatrixEngine();full=eng.analyze(base,scales)
 for k in range(1,4):pd.testing.assert_frame_equal(full.iloc[:k],eng.analyze(base.iloc[:k],[ScaleFrame(s.name,s.frame.iloc[:k]) for s in scales]),check_exact=True)
 changed=ScaleFrame('b',scales[1].frame.copy());changed.frame.loc[idx()[2],'structure_state_after']='UP_STRUCTURE';pd.testing.assert_frame_equal(full.iloc[:2],eng.analyze(base,[scales[0],changed]).iloc[:2],check_exact=True)

def test_real_51_alignment_and_dst_age():
 from trading_system.multitimeframe.causal_htf import CausalHTFAggregator,TimeAggregationSpec
 decision=pd.date_range('2024-03-10 01:55',periods=12,freq='min',tz='America/New_York');x=np.arange(12.)+100;raw=pd.DataFrame({'open':x,'high':x+1,'low':x-1,'close':x+.5},index=decision)
 _,table=CausalHTFAggregator(spec=TimeAggregationSpec(pd.Timedelta(minutes=5))).analyze(raw)
 completed=pd.DataFrame({'available_at':table.first_observed_asof_time.array,'structure_state_after':pd.array(['UP_STRUCTURE' if i%2==0 else 'DOWN_STRUCTURE' for i in range(len(table))],dtype='string')})
 aligned=causal_asof_align_scale_state(decision,completed);out=CausalConfluenceMatrixEngine().analyze(pd.DataFrame(index=decision),[ScaleFrame('htf',aligned)])
 first=int(np.flatnonzero(aligned.available)[0]);assert not aligned.available.iloc[:first].any();assert out.iloc[first]['htf__information_age_seconds']>=0

def test_output_collision_and_duplicate_scale_columns():
 base=pd.DataFrame({'configured_scale_count':[0,0,0]},index=idx())
 with pytest.raises(ConfluenceDataError):CausalConfluenceMatrixEngine().analyze(base,[sf('x',['UP_STRUCTURE']*3)])
 f=sf('x',['UP_STRUCTURE']*3).frame.copy();f.insert(0,'dup',1);f.columns=['dup']+list(f.columns[1:-1])+['dup']
 with pytest.raises(ConfluenceDataError):CausalConfluenceMatrixEngine().analyze(pd.DataFrame(index=idx()),[ScaleFrame('x',f)])

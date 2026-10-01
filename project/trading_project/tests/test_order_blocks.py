import math,numpy as np,pandas as pd,pytest
from trading_system.zones.order_blocks import CausalOrderBlockEngine,OrderBlockDataError,_OrderBlockAuditEngine
from trading_system.audit.causal_state import verify_truncation_invariance,verify_state_isolation,ReentrancyPolicy
from trading_system.structure.swing_detector import CausalAdaptiveSwingDetector,EmpiricalConfirmationPolicy
from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine
from trading_system.structure.structural_breaks import CausalStructuralBreakEngine

def frame(events,swings,ohlc):
 d=pd.DataFrame(ohlc,columns=['open','high','low','close'],dtype=float);n=len(d);d['swing_high_confirmed']=False;d['swing_low_confirmed']=False;d['swing_origin_position']=pd.array([pd.NA]*n,dtype='Int64');d['swing_confirmation_position']=pd.array([pd.NA]*n,dtype='Int64');d['swing_price']=np.nan
 for row,t,org in swings:d.loc[row,'swing_'+t.lower()+'_confirmed']=True;d.loc[row,'swing_origin_position']=org;d.loc[row,'swing_confirmation_position']=row;d.loc[row,'swing_price']=d.loc[org,'high' if t=='HIGH' else 'low']
 d['structural_break_event']='NONE';d['high_close_breach_event']=False;d['low_close_breach_event']=False;d['structure_state_before']='UNDEFINED'
 mapping={'BOS_UP':('UP_STRUCTURE','high_close_breach_event'),'CHOCH_UP':('DOWN_STRUCTURE','high_close_breach_event'),'BOS_DOWN':('DOWN_STRUCTURE','low_close_breach_event'),'CHOCH_DOWN':('UP_STRUCTURE','low_close_breach_event')}
 for row,e in events:d.loc[row,'structural_break_event']=e;state,flag=mapping[e];d.loc[row,'structure_state_before']=state;d.loc[row,flag]=True
 return d

def base():
 return frame([(4,'BOS_UP')],[(1,'LOW',0)],[(10,12,8,11),(11,12,9,10),(10,11,8,9),(9,12,8,11),(11,15,10,14),(9,15,7,7),(10,14,8,9)])

def test_origin_boundary_creation_timing():
 b,e=CausalOrderBlockEngine().analyze(base());assert not b.ob_candidate_created[:4].any();assert b.loc[4,'created_ob_origin_position']==2;assert b.loc[4,'created_ob_search_boundary_position']==0;assert b.loc[4,'created_ob_opposite_candle_count_in_leg']==2;assert not (e[(e.zone_id==0)&(e.event_position==4)].event_type!='ZONE_CREATED').any()

def test_same_row_swing_not_boundary_and_no_prior():
 d=frame([(2,'BOS_UP')],[(2,'LOW',0)],[(10,11,9,10),(10,11,8,9),(9,13,8,12)])
 b,e=CausalOrderBlockEngine().analyze(d);assert not b.ob_candidate_created.any();assert e.empty

def test_bearish_selector_doji_and_outside_boundary():
 d=frame([(4,'BOS_DOWN')],[(1,'HIGH',1)],[(9,11,8,10),(10,12,9,11),(10,11,9,10),(10,12,9,11),(8,10,5,6)])
 b,_=CausalOrderBlockEngine().analyze(d);assert b.loc[4,'created_ob_origin_position']==3;assert b.loc[4,'created_ob_opposite_candle_count_in_leg']==2

def test_duplicate_origin_distinct_ids_prior_use():
 d=base();d.loc[5,'structural_break_event']='CHOCH_UP';d.loc[5,'structure_state_before']='DOWN_STRUCTURE';d.loc[5,'high_close_breach_event']=True;b,e=CausalOrderBlockEngine().analyze(d);assert b.loc[[4,5],'created_ob_zone_id'].tolist()==[0,1];assert b.loc[[4,5],'created_ob_origin_prior_use_count'].tolist()==[0,1]

def test_displacement_read_before_push_and_scale():
 d=base();d.loc[6,'structural_break_event']='BOS_UP';d.loc[6,'structure_state_before']='UP_STRUCTURE';d.loc[6,'high_close_breach_event']=True;eng=CausalOrderBlockEngine();b,_=eng.analyze(d);assert math.isnan(b.loc[4,'created_ob_displacement_percentile']);assert b.loc[6,'created_ob_displacement_history_count']==1
 s=d.copy();s[['open','high','low','close']]*=8;bs,_=eng.analyze(s);pd.testing.assert_series_equal(b.created_ob_displacement_fraction,bs.created_ob_displacement_fraction,check_exact=True)

def test_lifecycle_touch_wick_close_reclaim_once():
 b,e=CausalOrderBlockEngine().analyze(base());z=e[e.zone_id==0];types=z.event_type.tolist();assert 'FIRST_TOUCH' in types;assert 'FIRST_FAR_SIDE_WICK_BREACH' in types;assert 'FIRST_FAR_SIDE_CLOSE_BREACH' in types;assert 'FIRST_CLOSE_RECLAIM_OF_FAR_SIDE' in types;assert types.count('FIRST_TOUCH')==1;assert b.known_bullish_ob_candidate_count.iloc[-1]==1

def test_multiple_zones_event_table_and_counts():
 d=base();d.loc[6,'structural_break_event']='BOS_UP';d.loc[6,'structure_state_before']='UP_STRUCTURE';d.loc[6,'high_close_breach_event']=True;b,e=CausalOrderBlockEngine().analyze(d);assert e.zone_id.nunique()==2;assert b.known_bullish_ob_candidate_count.iloc[-1]==2

def audit_events(df):
 fb,fe=CausalOrderBlockEngine().analyze(df)
 for k in range(1,len(df)):
  tb,te=CausalOrderBlockEngine().analyze(df.iloc[:k].copy());pd.testing.assert_frame_equal(fb.iloc[:k],tb,check_exact=True);pd.testing.assert_frame_equal(fe[fe.event_position<k].reset_index(drop=True),te,check_exact=True)

def test_causal_audits_state_and_events():
 a=base();b=base().copy();b.loc[6,'close']=8;r=verify_truncation_invariance(_OrderBlockAuditEngine,a,split_fractions=(),additional_split_points=list(range(1,len(a))));assert all(x.passed for x in r);assert verify_state_isolation(_OrderBlockAuditEngine,a,b,policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT).passed;audit_events(a)

def test_direct_upstream_contract_injections():
 valid=base()
 cases=[]
 x=valid.copy();x.loc[4,'high_close_breach_event']=False;cases.append(x)
 x=valid.copy();x.loc[4,'structure_state_before']='DOWN_STRUCTURE';cases.append(x)
 x=valid.copy();x.loc[4,'low_close_breach_event']=True;cases.append(x)
 x=valid.copy();x['swing_low_confirmed']=x.swing_low_confirmed.astype('boolean');x.loc[2,'swing_low_confirmed']=pd.NA;cases.append(x)
 x=valid.copy();x['swing_low_confirmed']=x.swing_low_confirmed.astype(int);cases.append(x)
 x=valid.copy();x.loc[1,'swing_confirmation_position']=2;cases.append(x)
 for x in cases:
  with pytest.raises(OrderBlockDataError):CausalOrderBlockEngine().analyze(x)
 accepted=valid.copy();accepted.loc[4,'structural_break_event']='CHOCH_UP';accepted.loc[4,'structure_state_before']='DOWN_STRUCTURE';accepted.loc[4,'high_close_breach_event']=True
 CausalOrderBlockEngine().analyze(accepted)

def test_search_boundary_is_included():
 d=frame([(3,'BOS_UP')],[(1,'LOW',1)],[(10,11,9,10),(10,11,8,9),(9,12,8,11),(11,14,10,13)])
 b,_=CausalOrderBlockEngine().analyze(d);assert b.loc[3,'created_ob_search_boundary_position']==1;assert b.loc[3,'created_ob_origin_position']==1

def test_validation_empty_immutability():
 d=base();before=d.copy(deep=True);CausalOrderBlockEngine().analyze(d);pd.testing.assert_frame_equal(d,before,check_exact=True)
 for x in [d.assign(high=np.nan),d.assign(open=1000)]:
  with pytest.raises(OrderBlockDataError):CausalOrderBlockEngine().analyze(x)
 empty=frame([],[],[]);b,e=CausalOrderBlockEngine().analyze(empty);assert b.empty and e.empty

def real_chain(raw):
 p=EmpiricalConfirmationPolicy(quantile=.5,prior_continuation_reversals=(.005,.01));a=CausalAdaptiveSwingDetector(p).analyze(raw[['high','low']]);a.insert(0,'open',raw.open.to_numpy());a.insert(3,'close',raw.close.to_numpy());b=ConfirmedSwingSequenceEngine().analyze(a);return CausalStructuralBreakEngine().analyze(b)

def test_real_chain_integration():
 h=[10,11,10.8,10.6,10.8,12,11.8,11.6,11.4,13];l=[9,10,10.5,10,10.1,11,11.5,11,11.2,12.1];c=[(x+y)/2 for x,y in zip(h,l)];o=c.copy();o[7]=11.5;raw=pd.DataFrame({'open':o,'high':h,'low':l,'close':c});up=real_chain(raw);bar,ev=CausalOrderBlockEngine().analyze(up);assert bar.ob_candidate_created.any();assert set(ev[ev.event_type=='ZONE_CREATED'].source_break_event).issubset({'BOS_UP','CHOCH_UP','BOS_DOWN','CHOCH_DOWN'})

import numpy as np,pandas as pd,pytest
from trading_system.zones.dealing_range import CausalDealingRangeEngine,RangeDataError,_RangeAuditEngine
from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine
from trading_system.audit.causal_state import *
def surf(n,events,closes):
 h=np.zeros(n,bool);l=np.zeros(n,bool);o=pd.array([pd.NA]*n,dtype='Int64');p=np.full(n,np.nan);c=pd.array([pd.NA]*n,dtype='Int64')
 for i,t,org,pr in events:(h if t=='HIGH' else l)[i]=True;o[i]=org;p[i]=pr;c[i]=i
 d=ConfirmedSwingSequenceEngine().analyze(pd.DataFrame({'swing_high_confirmed':h,'swing_low_confirmed':l,'swing_origin_position':o,'swing_price':p,'swing_confirmation_position':c}));d.insert(0,'close',closes);return d
def test_pairing_creation_location():
 d=surf(4,[(1,'LOW',0,90),(3,'HIGH',2,110)],[95,92,100,100]);b,t=CausalDealingRangeEngine().analyze(d);assert b.loc[3,'dealing_range_created'];assert b.loc[3,'current_range_position_raw']==.5;assert b.loc[3,'current_midpoint_displacement']==0;assert t.direction.iloc[0]=='ASCENDING_DEALING_RANGE_CANDIDATE'
def test_same_side_replacement_and_versioning():
 d=surf(6,[(1,'HIGH',0,100),(2,'HIGH',1,110),(3,'LOW',2,90),(5,'HIGH',4,120)],[95,100,105,95,100,120]);b,t=CausalDealingRangeEngine().analyze(d);assert t.iloc[0].first_endpoint_price==110;assert t.range_id.tolist()==[0,1];assert b.loc[4,'current_range_id']==0
def test_failed_geometry_pending():
 d=surf(4,[(0,'LOW',0,100),(1,'HIGH',1,90),(3,'LOW',2,80)],[95,90,85,80]);b,t=CausalDealingRangeEngine().analyze(d);assert b.loc[1,'rejected_range_geometry'];assert b.loc[3,'dealing_range_created'];assert t.iloc[0].first_endpoint_side=='HIGH'
def test_outside_position_no_clip():
 d=surf(5,[(1,'LOW',0,90),(3,'HIGH',2,110)],[95,92,100,120,80]);b,_=CausalDealingRangeEngine().analyze(d);assert b.loc[3,'current_range_position_raw']>1;assert b.loc[4,'current_range_position_raw']<0
def test_audits_table_state():
 d=surf(5,[(1,'LOW',0,90),(3,'HIGH',2,110)],[95,92,100,100,105]);r=verify_truncation_invariance(_RangeAuditEngine,d,split_fractions=(),additional_split_points=[1,2,3,4]);assert all(x.passed for x in r);assert verify_state_isolation(_RangeAuditEngine,d,surf(5,[(1,'HIGH',0,110),(3,'LOW',2,90)],[100]*5),policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT).passed
 fb,ft=CausalDealingRangeEngine().analyze(d)
 for k in range(1,5):tb,tt=CausalDealingRangeEngine().analyze(d.iloc[:k]);pd.testing.assert_frame_equal(ft[ft.creation_position<k].reset_index(drop=True),tt,check_exact=True)
def test_validation_empty_immutable():
 e=surf(0,[],[]);b,t=CausalDealingRangeEngine().analyze(e);assert b.empty and t.empty
 d=surf(2,[(1,'LOW',0,90)],[95,90]);before=d.copy();CausalDealingRangeEngine().analyze(d);pd.testing.assert_frame_equal(d,before)

def test_exact_location_equations():
 d=surf(8,[(1,'LOW',0,100),(2,'HIGH',1,200)],[0,100,100,150,200,250,50,150]);b,_=CausalDealingRangeEngine().analyze(d)
 expected={2:(0,-1,1,0),3:(.5,0,0,0),4:(1,1,0,1),5:(1.5,2,0,2),6:(-.5,-2,2,0)}
 for i,v in expected.items():assert (b.loc[i,'current_range_position_raw'],b.loc[i,'current_midpoint_displacement'],b.loc[i,'current_discount_depth'],b.loc[i,'current_premium_depth'])==v

def test_multiple_range_snapshots_future_safe():
 d=surf(7,[(1,'LOW',0,90),(2,'HIGH',1,110),(4,'LOW',3,80),(6,'HIGH',5,120)],[90,90,100,100,90,100,110]);b,t=CausalDealingRangeEngine().analyze(d)
 assert b.loc[2:3,'current_range_id'].tolist()==[0,0];assert b.loc[4:5,'current_range_id'].tolist()==[1,1];assert b.loc[1,'current_range_id'] is pd.NA or pd.isna(b.loc[1,'current_range_id']);assert t.range_id.tolist()==[0,1,2]

def test_rejected_geometry_preserves_current_and_no_creation_metadata():
 d=surf(5,[(0,'LOW',0,90),(1,'HIGH',1,110),(3,'LOW',2,120)],[90,100,100,100,100]);b,_=CausalDealingRangeEngine().analyze(d)
 assert b.loc[3,'rejected_range_geometry'];assert not b.loc[3,'dealing_range_created'];assert pd.isna(b.loc[3,'created_range_id']);assert b.loc[3,'current_range_id']==0

def test_primary_secondary_consistency_and_future_append():
 d=surf(5,[(1,'LOW',0,90),(3,'HIGH',2,110)],[95,92,100,100,105]);b,t=CausalDealingRangeEngine().analyze(d)
 for _,r in t.iterrows():
  i=int(r.creation_position);assert b.loc[i,'dealing_range_created'];assert b.loc[i,'created_range_id']==r.range_id;assert b.loc[i,'created_range_low']==r.range_low
 d2=surf(7,[(1,'LOW',0,90),(3,'HIGH',2,110),(6,'LOW',5,80)],[95,92,100,100,105,100,90]);b2,_=CausalDealingRangeEngine().analyze(d2);pd.testing.assert_frame_equal(b,b2.iloc[:5],check_exact=True)

def test_upstream_malformed_and_numeric_overflow():
 d=surf(3,[(1,'LOW',0,90),(2,'HIGH',1,110)],[95,90,100]);bad=d.copy();bad.loc[2,'current_structure_swing_price']=999
 with pytest.raises(RangeDataError):CausalDealingRangeEngine().analyze(bad)
 m=np.finfo(float).max;d=surf(2,[(0,'LOW',0,-m),(1,'HIGH',1,m)],[0,0])
 with pytest.raises(RangeDataError):CausalDealingRangeEngine().analyze(d)

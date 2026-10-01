import pandas as pd,numpy as np,pytest
from trading_system.multitimeframe.causal_htf import CausalHTFAggregator,TimeAggregationSpec,HTFDataError,HTFConfigError,_HTFAuditEngine
from trading_system.audit.causal_state import *
def data(times):
 n=len(times);x=np.arange(n,dtype=float)+100
 return pd.DataFrame({'open':x,'high':x+1,'low':x-1,'close':x+.5,'volume':np.ones(n)},index=pd.DatetimeIndex(times))
def test_boundary_arithmetic():
 d=300_000_000_000;f=CausalHTFAggregator._bucket_end_ns
 assert f(0,d)==0
 assert f(-1,d)==0
 assert f(1,d)==d
 assert f(-d,d)==-d
 assert f(-d+1,d)==0
 assert f(-d-1,d)==-d
 assert f(d,d)==d and f(2*d,d)==2*d
 assert f(d-1,d)==d and f(d+1,d)==2*d
def test_buckets_asof_no_leak():
 idx=pd.date_range('2024-01-01 10:01',periods=6,freq='min',tz='UTC');df=data(idx);df.loc[idx[4],'high']=999
 a,t=CausalHTFAggregator(spec=TimeAggregationSpec(pd.Timedelta(minutes=5))).analyze(df)
 assert a.loc[idx[:4],'last_completed_htf_high'].isna().all();assert a.loc[idx[4],'last_completed_htf_high']==999;assert t.iloc[0].source_bar_count==5;assert t.iloc[0].open==100;assert t.iloc[0].close==104.5;assert t.iloc[0].volume==5
def test_midbucket_sparse_honesty():
 df=data(pd.DatetimeIndex(['2024-01-01 09:58Z','2024-01-01 09:59Z','2024-01-01 10:00Z','2024-01-01 10:11Z']));a,t=CausalHTFAggregator(spec=TimeAggregationSpec(pd.Timedelta(minutes=5))).analyze(df);assert t.iloc[0].source_bar_count==3;assert len(t)==1;assert t.iloc[0].first_source_timestamp.minute==58
def test_timezone_dst_equivalence():
 utc=pd.date_range('2024-03-10 06:55',periods=11,freq='min',tz='UTC');ny=utc.tz_convert('America/New_York');e=CausalHTFAggregator(spec=TimeAggregationSpec(pd.Timedelta(minutes=5)));a,t=e.analyze(data(utc));b,u=e.analyze(data(ny));pd.testing.assert_frame_equal(t,u,check_exact=True);np.testing.assert_array_equal(a.last_completed_htf_close,b.last_completed_htf_close)
def test_truncation_table_state():
 df=data(pd.date_range('2024-01-01 10:01',periods=15,freq='min',tz='UTC'));r=verify_truncation_invariance(_HTFAuditEngine,df,split_fractions=(),additional_split_points=list(range(1,15)));assert all(x.passed for x in r);assert verify_state_isolation(_HTFAuditEngine,df,data(pd.date_range('2024-02-01',periods=15,freq='min',tz='UTC')),policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT).passed
 fulla,fullt=_HTFAuditEngine().analyze(df)
 for k in range(1,15):
  a,t=_HTFAuditEngine().analyze(df.iloc[:k]);pd.testing.assert_frame_equal(fulla.iloc[:k],a,check_exact=True);pd.testing.assert_frame_equal(fullt[fullt.bucket_end_utc<=df.index[k-1].tz_convert('UTC')],t,check_exact=True)
def test_validation_empty():
 with pytest.raises(HTFDataError):_HTFAuditEngine().analyze(data(pd.date_range('2024-01-01',periods=2,freq='min')))
 with pytest.raises(HTFConfigError):TimeAggregationSpec(pd.Timedelta(0))
 e=data(pd.DatetimeIndex([],tz='UTC'));a,t=_HTFAuditEngine().analyze(e);assert a.empty and t.empty

def test_pre_epoch_datetimeindex_through_analyze():
 duration=pd.Timedelta(minutes=5)
 index=pd.DatetimeIndex([
  pd.Timestamp('1970-01-01 00:00:00',tz='UTC')-pd.Timedelta(1,'ns'),
  pd.Timestamp('1970-01-01 00:00:00',tz='UTC'),
  pd.Timestamp('1970-01-01 00:00:00',tz='UTC')+pd.Timedelta(1,'ns'),
 ])
 asof,table=CausalHTFAggregator(spec=TimeAggregationSpec(duration)).analyze(data(index))
 assert table.bucket_end_utc.tolist()==[pd.Timestamp('1970-01-01',tz='UTC')]
 assert table.iloc[0].source_bar_count==2
 assert pd.isna(asof.last_completed_htf_end_utc.iloc[0])
 assert asof.last_completed_htf_end_utc.iloc[1]==pd.Timestamp('1970-01-01',tz='UTC')
 assert asof.last_completed_htf_end_utc.iloc[2]==pd.Timestamp('1970-01-01',tz='UTC')

def test_delayed_processing_availability():
 index=pd.DatetimeIndex(['2024-01-01 09:58Z','2024-01-01 09:59Z','2024-01-01 10:03Z'])
 asof,table=CausalHTFAggregator(spec=TimeAggregationSpec(pd.Timedelta(minutes=5))).analyze(data(index))
 row=table.iloc[0]
 assert row.bucket_end_utc==pd.Timestamp('2024-01-01 10:00Z')
 assert row.theoretical_available_at==pd.Timestamp('2024-01-01 10:00Z')
 assert row.first_observed_asof_position==2
 assert row.first_observed_asof_time==pd.Timestamp('2024-01-01 10:03Z')
 assert row.source_bar_count==2
 assert asof.last_completed_htf_end_utc.iloc[:2].isna().all()
 assert asof.last_completed_htf_end_utc.iloc[2]==pd.Timestamp('2024-01-01 10:00Z')

def test_completed_table_availability_and_membership_invariants():
 source=data(pd.date_range('2024-01-01 09:51',periods=20,freq='min',tz='UTC'))
 _,table=CausalHTFAggregator(spec=TimeAggregationSpec(pd.Timedelta(minutes=5))).analyze(source)
 for _,row in table.iterrows():
  assert row.theoretical_available_at==row.bucket_end_utc
  assert row.first_observed_asof_time>=row.theoretical_available_at
  assigned=source.index[(source.index>row.bucket_start_utc)&(source.index<=row.bucket_end_utc)]
  assert len(assigned)==row.source_bar_count
  assert assigned[0]==row.first_source_timestamp
  assert assigned[-1]==row.last_source_timestamp

def test_duration_collision_complex_and_immutability():
 for value in ('5min',pd.Timedelta(0),pd.Timedelta(-1,'ns'),pd.NaT):
  with pytest.raises(HTFConfigError):TimeAggregationSpec(value)
 valid=data(pd.date_range('2024-01-01',periods=2,freq='min',tz='UTC'))
 before=valid.copy(deep=True);_HTFAuditEngine().analyze(valid);pd.testing.assert_frame_equal(valid,before,check_exact=True)
 collision=valid.copy();collision['last_completed_htf_volume']=0.0
 with pytest.raises(HTFDataError):_HTFAuditEngine().analyze(collision)
 for column in ('open','high','low','close','volume'):
  bad=valid.copy();bad[column]=bad[column].astype(complex)
  with pytest.raises(HTFDataError):_HTFAuditEngine().analyze(bad)

# Module 6.1A V1.3 — Complete Audit Review Bundle

## `src/trading_system/decision/evidence_vector.py`

```python
"""Layer 6 — Module 6.1A: Causal Evidence Vector / Feature Contract V1.3.

Certified closed allowlist only. Row-local copy and contract validation; no
score, weight, model, label, outcome, fitted transform, or upstream execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Final, Optional
import re
import numpy as np
import pandas as pd

class EvidenceVectorError(Exception): pass
class EvidenceConfigError(EvidenceVectorError): pass
class EvidenceDataError(EvidenceVectorError): pass
class SemanticType(Enum):
    CONTEXT="CONTEXT"; SIGNED_DIRECTIONAL="SIGNED_DIRECTIONAL"; MAGNITUDE="MAGNITUDE"; EVENT="EVENT"; COUNT_SUPPORT="COUNT_SUPPORT"; AVAILABILITY="AVAILABILITY"; CATEGORY="CATEGORY"
class OrderFlowEvidenceMode(Enum): ACTUAL="ACTUAL"; PROXY="PROXY"; NONE="NONE"
class MissingnessPolicy(Enum): ALLOW_MISSING="ALLOW_MISSING"; NONMISSING="NONMISSING"
_OUTCOME=re.compile(r"(^|_)(future|forward|target|stop_hit|pnl|profit|trade_result|mfe|mae|label|y_true)|futuremfe",re.I)
_DOMAINS={"percentile","unit_interval","signed_unit","finite_or_nan","nonnegative_or_nan","count","bool","structure_state","break_event","category_side","category_pressure"}
@dataclass(frozen=True)
class FeatureSpec:
    feature_name:str; source_module:str; source_column:str; semantic_type:SemanticType; missingness_policy:MissingnessPolicy; expected_domain:str; directional_semantics:str="NONE"; event_local:bool=False; support_column:Optional[str]=None; freshness_column:Optional[str]=None; source_mode:str="ANY"; epistemic_status:str="FACTUAL"
    def __post_init__(self):
        if _OUTCOME.search(self.source_column) or _OUTCOME.search(self.feature_name): raise EvidenceConfigError("outcome-like feature forbidden")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*",self.feature_name): raise EvidenceConfigError("unsafe feature name")
        if not isinstance(self.missingness_policy,MissingnessPolicy): raise EvidenceConfigError("invalid missingness policy")
        if self.expected_domain not in _DOMAINS: raise EvidenceConfigError("invalid domain")
        if self.source_mode not in {"ANY","ACTUAL","PROXY"}: raise EvidenceConfigError("invalid source mode")
    @property
    def output_column(self): return "ev__"+self.feature_name
@dataclass(frozen=True)
class EvidenceVectorConfig:
    environment:bool; temporal_context:bool; structure:bool; liquidity:bool; order_blocks:bool; fvg:bool; dealing_range:bool; multiscale:bool; order_flow_mode:OrderFlowEvidenceMode
    def __post_init__(self):
        if any(not isinstance(x,bool) for x in (self.environment,self.temporal_context,self.structure,self.liquidity,self.order_blocks,self.fvg,self.dealing_range,self.multiscale)): raise EvidenceConfigError("group flags must be bool")
        if not isinstance(self.order_flow_mode,OrderFlowEvidenceMode): raise EvidenceConfigError("explicit order-flow mode required")

def fs(name,module,semantic,domain,*,missing=MissingnessPolicy.ALLOW_MISSING,event=False,support=None,mode="ANY",direction="NONE",epistemic="FACTUAL"):
    return FeatureSpec(name,module,name,semantic,missing,domain,direction,event,support,None,mode,epistemic)
S=SemanticType
ENV=(
 fs("true_range_percentile","1.1",S.MAGNITUDE,"percentile",support="true_range_history_count"),
 fs("true_range_history_count","1.1",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING),
 fs("normalized_tr_change","1.1",S.SIGNED_DIRECTIONAL,"finite_or_nan",direction="VOLATILITY_CHANGE_DIRECTION"),
 fs("expansion_percentile","1.1",S.CONTEXT,"percentile",support="expansion_history_count"),
 fs("expansion_history_count","1.1",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING),)
TEMP=tuple(fs(x,"1.2",S.CONTEXT,"signed_unit",missing=MissingnessPolicy.NONMISSING) for x in ("hour_utc_sin","hour_utc_cos","weekday_sin","weekday_cos"))
STRUCT=(fs("structure_state_after","2.1C",S.CATEGORY,"structure_state",missing=MissingnessPolicy.NONMISSING,epistemic="PROJECT_OPERATIONAL"),fs("structural_break_event","2.1C",S.EVENT,"break_event",missing=MissingnessPolicy.NONMISSING,event=True,epistemic="PROJECT_OPERATIONAL"))
LIQ=(
 fs("high_side_first_wick_only_count","2.2",S.EVENT,"count",missing=MissingnessPolicy.NONMISSING,event=True),fs("low_side_first_wick_only_count","2.2",S.EVENT,"count",missing=MissingnessPolicy.NONMISSING,event=True),
 fs("high_side_first_close_breach_count","2.2",S.EVENT,"count",missing=MissingnessPolicy.NONMISSING,event=True),fs("low_side_first_close_breach_count","2.2",S.EVENT,"count",missing=MissingnessPolicy.NONMISSING,event=True),
 fs("nearest_same_side_distance_fraction","2.2",S.MAGNITUDE,"nonnegative_or_nan",event=True),
 fs("nearest_distance_percentile","2.2",S.MAGNITUDE,"percentile",event=True,support="nearest_distance_reference_history_count"),
 fs("nearest_distance_reference_history_count","2.2",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,event=False),)
OB=(
 fs("created_ob_displacement_fraction","4.1",S.MAGNITUDE,"nonnegative_or_nan",event=True,epistemic="SOURCE_APPROXIMATION"),
 fs("created_ob_displacement_percentile","4.1",S.MAGNITUDE,"percentile",event=True,support="created_ob_displacement_history_count",epistemic="SOURCE_APPROXIMATION"),
 fs("created_ob_displacement_history_count","4.1",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,event=False,epistemic="SOURCE_APPROXIMATION"),
)+tuple(fs(x,"4.1",S.EVENT,"count",missing=MissingnessPolicy.NONMISSING,event=True,epistemic="SOURCE_APPROXIMATION") for x in ("bullish_ob_first_touch_count","bearish_ob_first_touch_count","bullish_ob_first_far_side_wick_breach_count","bearish_ob_first_far_side_wick_breach_count","bullish_ob_first_far_side_close_breach_count","bearish_ob_first_far_side_close_breach_count","bullish_ob_first_reclaim_count","bearish_ob_first_reclaim_count"))
FVG=(
 fs("created_fvg_gap_width_fraction","4.2A",S.MAGNITUDE,"nonnegative_or_nan",event=True,epistemic="SOURCE_APPROXIMATION"),
 fs("created_fvg_gap_width_percentile","4.2A",S.MAGNITUDE,"percentile",event=True,support="created_fvg_gap_width_history_count",epistemic="SOURCE_APPROXIMATION"),
 fs("created_fvg_gap_width_history_count","4.2A",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,event=False,epistemic="SOURCE_APPROXIMATION"),
)+tuple(fs(x,"4.2A",S.EVENT,"count",missing=MissingnessPolicy.NONMISSING,event=True,epistemic="SOURCE_APPROXIMATION") for x in ("bullish_fvg_first_touch_count","bearish_fvg_first_touch_count","bullish_fvg_first_full_range_coverage_count","bearish_fvg_first_full_range_coverage_count","bullish_fvg_first_far_side_wick_breach_count","bearish_fvg_first_far_side_wick_breach_count","bullish_fvg_first_far_side_close_breach_count","bearish_fvg_first_far_side_close_breach_count","bullish_fvg_first_close_reclaim_count","bearish_fvg_first_close_reclaim_count"))
RANGE=(fs("current_range_position_raw","4.2B",S.CONTEXT,"finite_or_nan",epistemic="FACTUAL_GEOMETRY"),fs("current_midpoint_displacement","4.2B",S.SIGNED_DIRECTIONAL,"finite_or_nan",direction="RANGE_LOCATION_DIRECTION",epistemic="FACTUAL_GEOMETRY"),fs("current_discount_depth","4.2B",S.MAGNITUDE,"nonnegative_or_nan",epistemic="FACTUAL_GEOMETRY"),fs("current_premium_depth","4.2B",S.MAGNITUDE,"nonnegative_or_nan",epistemic="FACTUAL_GEOMETRY"))
MTF=(fs("available_scale_count","5.2",S.AVAILABILITY,"count",missing=MissingnessPolicy.NONMISSING),fs("unavailable_scale_count","5.2",S.AVAILABILITY,"count",missing=MissingnessPolicy.NONMISSING),fs("directional_scale_count","5.2",S.AVAILABILITY,"count",missing=MissingnessPolicy.NONMISSING),fs("availability_fraction","5.2",S.AVAILABILITY,"unit_interval",missing=MissingnessPolicy.NONMISSING),fs("directional_fraction","5.2",S.AVAILABILITY,"unit_interval",missing=MissingnessPolicy.NONMISSING),fs("directional_balance","5.2",S.SIGNED_DIRECTIONAL,"signed_unit",direction="STRUCTURE_DIRECTION"),fs("directional_consensus","5.2",S.MAGNITUDE,"unit_interval"),fs("directional_conflict","5.2",S.CONTEXT,"bool",missing=MissingnessPolicy.NONMISSING))
ACTUAL=(fs("delta_ratio","3.1",S.SIGNED_DIRECTIONAL,"signed_unit",mode="ACTUAL",direction="PRICE_OR_FLOW_DIRECTION"),fs("delta_ratio_percentile","3.1",S.CONTEXT,"percentile",support="delta_ratio_history_count",mode="ACTUAL"),fs("delta_ratio_history_count","3.1",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,mode="ACTUAL"),fs("delta_magnitude_percentile","3.1",S.MAGNITUDE,"percentile",support="delta_magnitude_history_count",mode="ACTUAL"),fs("delta_magnitude_history_count","3.1",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,mode="ACTUAL"),fs("actual_absorption_evidence","3.2",S.MAGNITUDE,"unit_interval",mode="ACTUAL",epistemic="PROJECT_OPERATIONAL"),fs("absorbed_aggression_side","3.2",S.CATEGORY,"category_side",missing=MissingnessPolicy.NONMISSING,mode="ACTUAL",epistemic="PROJECT_OPERATIONAL"),fs("opposed_response_percentile","3.2",S.MAGNITUDE,"percentile",support="opposed_response_history_count",mode="ACTUAL",epistemic="PROJECT_OPERATIONAL"),fs("opposed_response_history_count","3.2",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,mode="ACTUAL"))
PROXY=(fs("volume_pressure_proxy","3.1",S.SIGNED_DIRECTIONAL,"signed_unit",mode="PROXY",direction="PRICE_OR_FLOW_DIRECTION",epistemic="SOURCE_APPROXIMATION"),fs("pressure_proxy_percentile","3.1",S.CONTEXT,"percentile",support="pressure_proxy_history_count",mode="PROXY",epistemic="SOURCE_APPROXIMATION"),fs("pressure_proxy_history_count","3.1",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,mode="PROXY",epistemic="SOURCE_APPROXIMATION"),fs("pressure_magnitude_percentile","3.1",S.MAGNITUDE,"percentile",support="pressure_magnitude_history_count",mode="PROXY",epistemic="SOURCE_APPROXIMATION"),fs("pressure_magnitude_history_count","3.1",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,mode="PROXY",epistemic="SOURCE_APPROXIMATION"),fs("proxy_absorption_evidence","3.2",S.MAGNITUDE,"unit_interval",mode="PROXY",epistemic="SOURCE_APPROXIMATION"),fs("pressure_side","3.2",S.CATEGORY,"category_pressure",mode="PROXY",missing=MissingnessPolicy.NONMISSING,epistemic="SOURCE_APPROXIMATION"),fs("pressure_opposed_response_percentile","3.2",S.MAGNITUDE,"percentile",support="pressure_opposed_response_history_count",mode="PROXY",epistemic="SOURCE_APPROXIMATION"),fs("pressure_opposed_response_history_count","3.2",S.COUNT_SUPPORT,"count",missing=MissingnessPolicy.NONMISSING,mode="PROXY",epistemic="SOURCE_APPROXIMATION"))
V1_CATALOG:Final=ENV+TEMP+STRUCT+LIQ+OB+FVG+RANGE+MTF+ACTUAL+PROXY
GROUPS={"environment":ENV,"temporal_context":TEMP,"structure":STRUCT,"liquidity":LIQ,"order_blocks":OB,"fvg":FVG,"dealing_range":RANGE,"multiscale":MTF,"actual":ACTUAL,"proxy":PROXY}

def validate_v1_catalog():
    names=[s.feature_name for s in V1_CATALOG];outputs=[s.output_column for s in V1_CATALOG]
    if len(names)!=len(set(names)) or len(outputs)!=len(set(outputs)): raise EvidenceConfigError("duplicate catalog identity")
    by_name={s.feature_name:s for s in V1_CATALOG}
    allowed_direction={"NONE","PRICE_OR_FLOW_DIRECTION","VOLATILITY_CHANGE_DIRECTION","RANGE_LOCATION_DIRECTION","STRUCTURE_DIRECTION"}
    for s in V1_CATALOG:
        if s.directional_semantics not in allowed_direction: raise EvidenceConfigError("invalid directional semantics")
        if s.semantic_type is S.COUNT_SUPPORT and (s.expected_domain!="count" or s.directional_semantics!="NONE" or s.missingness_policy is not MissingnessPolicy.NONMISSING): raise EvidenceConfigError("support contract")
        if s.semantic_type is S.CATEGORY and s.expected_domain not in {"structure_state","category_side","category_pressure"}: raise EvidenceConfigError("category contract")
        if s.expected_domain=="bool" and s.semantic_type not in {S.EVENT,S.CONTEXT,S.AVAILABILITY}: raise EvidenceConfigError("bool contract")
        if s.support_column:
            support=by_name.get(s.support_column)
            if support is None or support.semantic_type is not S.COUNT_SUPPORT or support.source_mode!=s.source_mode or support.source_module!=s.source_module: raise EvidenceConfigError(f"invalid support link {s.feature_name}")
        if s.semantic_type is S.COUNT_SUPPORT and s.expected_domain!="count": raise EvidenceConfigError("support domain")
        if s.source_mode=="ACTUAL" and s not in ACTUAL: raise EvidenceConfigError("actual isolation")
        if s.source_mode=="PROXY" and s not in PROXY: raise EvidenceConfigError("proxy isolation")
        if s.source_mode=="PROXY" and s.epistemic_status!="SOURCE_APPROXIMATION": raise EvidenceConfigError("proxy epistemic contract")
    return True
validate_v1_catalog()

class CausalEvidenceVectorEngine:
    def __init__(self,*,config:EvidenceVectorConfig):
        if not isinstance(config,EvidenceVectorConfig): raise EvidenceConfigError("explicit config required")
        self.config=config
    def _specs(self):
        selected=[]
        for key in ("environment","temporal_context","structure","liquidity","order_blocks","fvg","dealing_range","multiscale"):
            if getattr(self.config,key): selected.extend(GROUPS[key])
        if self.config.order_flow_mode is OrderFlowEvidenceMode.ACTUAL: selected.extend(ACTUAL)
        elif self.config.order_flow_mode is OrderFlowEvidenceMode.PROXY: selected.extend(PROXY)
        return tuple(selected)
    @staticmethod
    def _validate_series(series,spec):
        domain=spec.expected_domain
        if spec.missingness_policy is MissingnessPolicy.NONMISSING and series.isna().any(): raise EvidenceDataError(f"missing value forbidden for {spec.source_column}")
        if domain=="count":
            if pd.api.types.is_bool_dtype(series.dtype) or not pd.api.types.is_integer_dtype(series.dtype) or (series<0).any(): raise EvidenceDataError(f"invalid count {spec.source_column}")
            return
        if domain=="bool":
            if not pd.api.types.is_bool_dtype(series.dtype): raise EvidenceDataError("invalid bool")
            return
        categories={"structure_state":{"UNDEFINED","UP_STRUCTURE","DOWN_STRUCTURE","MIXED"},"break_event":{"NONE","BOS_UP","BOS_DOWN","CHOCH_UP","CHOCH_DOWN","UNCLASSIFIED_BREAK","AMBIGUOUS_DOUBLE_BREAK"},"category_side":{"BUY","SELL","NONE"},"category_pressure":{"POSITIVE","NEGATIVE","NONE"}}
        if domain in categories:
            if not series.dropna().astype(str).isin(categories[domain]).all(): raise EvidenceDataError("invalid category")
            return
        if not pd.api.types.is_numeric_dtype(series.dtype) or pd.api.types.is_bool_dtype(series.dtype): raise EvidenceDataError("invalid numeric")
        values=series.to_numpy(dtype=np.float64,na_value=np.nan);finite=np.isfinite(values)
        if np.isinf(values).any(): raise EvidenceDataError("infinite evidence")
        if domain in ("percentile","unit_interval") and ((values[finite]<0)|(values[finite]>1)).any(): raise EvidenceDataError("unit domain")
        if domain=="signed_unit" and ((values[finite]<-1)|(values[finite]>1)).any(): raise EvidenceDataError("signed domain")
        if domain=="nonnegative_or_nan" and (values[finite]<0).any(): raise EvidenceDataError("nonnegative domain")
    def manifest(self):
        columns=("feature_name","output_column","source_module","source_column","semantic_type","missingness_policy","event_local","support_column","freshness_column","source_mode","directional_semantics","expected_domain","epistemic_status")
        rows=[]
        for s in self._specs():
            row={c:getattr(s,c) if c!="output_column" else s.output_column for c in columns}
            row["semantic_type"]=s.semantic_type.value
            row["missingness_policy"]=s.missingness_policy.value
            rows.append(row)
        return pd.DataFrame(rows,columns=columns)
    def analyze(self,df):
        if not isinstance(df,pd.DataFrame) or df.columns.has_duplicates: raise EvidenceDataError("invalid frame")
        if df.index.has_duplicates or not df.index.is_monotonic_increasing: raise EvidenceDataError("index contract")
        specs=self._specs();generated=[s.output_column for s in specs]+["ev__evidence_feature_count","ev__evidence_available_count","ev__evidence_availability_fraction"]
        if any(c in df.columns for c in generated): raise EvidenceDataError("output collision")
        missing=[s.source_column for s in specs if s.source_column not in df.columns]
        if missing: raise EvidenceDataError(f"missing registered sources: {missing}")
        out=pd.DataFrame(index=df.index);decision=[s for s in specs if s.semantic_type is not S.COUNT_SUPPORT];available=np.zeros(len(df),np.int64)
        for s in specs:
            source=df[s.source_column];self._validate_series(source,s);out[s.output_column]=source.copy()
            if s in decision: available+=source.notna().to_numpy(np.int64)
        total=len(decision);out["ev__evidence_feature_count"]=total;out["ev__evidence_available_count"]=available;out["ev__evidence_availability_fraction"]=np.nan if total==0 else available/total
        return out,self.manifest()

```

## `src/trading_system/decision/__init__.py`

```python
from trading_system.decision.evidence_vector import CausalEvidenceVectorEngine,EvidenceVectorConfig,FeatureSpec,MissingnessPolicy,OrderFlowEvidenceMode,SemanticType,EvidenceConfigError,EvidenceDataError
__all__=["CausalEvidenceVectorEngine","EvidenceVectorConfig","FeatureSpec","MissingnessPolicy","OrderFlowEvidenceMode","SemanticType","EvidenceConfigError","EvidenceDataError"]

```

## `tests/test_evidence_vector.py`

```python
import dataclasses,math,numpy as np,pandas as pd,pytest
from trading_system.decision.evidence_vector import *
from trading_system.environment.dynamic_volatility import DynamicVolatilityEngine
from trading_system.orderflow.volume_delta import CausalVolumeDeltaEngine,OrderFlowMode
from trading_system.orderflow.absorption import CausalAbsorptionEvidenceEngine

def cfg(**kw):
 d=dict(environment=False,temporal_context=False,structure=False,liquidity=False,order_blocks=False,fvg=False,dealing_range=False,multiscale=False,order_flow_mode=OrderFlowEvidenceMode.NONE);d.update(kw);return EvidenceVectorConfig(**d)
def actual_surface():
 raw=pd.DataFrame({'close':[100.,101.,101.],'buy_volume':[7.,7.,7.],'sell_volume':[3.,3.,3.]});x=CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(raw);return CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(x)
def proxy_surface():
 raw=pd.DataFrame({'open':[5.,5.],'high':[10.,10.],'low':[0.,0.],'close':[8.,2.],'volume':[100.,100.]});x=CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(raw);return CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(x)
def test_explicit_frozen_config():
 with pytest.raises(TypeError):CausalEvidenceVectorEngine() # type: ignore
 c=cfg();assert dataclasses.is_dataclass(c)
 with pytest.raises(dataclasses.FrozenInstanceError):c.environment=True # type: ignore
def test_modes_isolated():
 a,_=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(actual_surface());assert 'ev__delta_ratio' in a and 'ev__volume_pressure_proxy' not in a
 p,_=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.PROXY)).analyze(proxy_surface());assert 'ev__volume_pressure_proxy' in p and 'ev__delta_ratio' not in p
 n,m=CausalEvidenceVectorEngine(config=cfg()).analyze(pd.DataFrame(index=[0]));assert n.ev__evidence_feature_count.iloc[0]==0 and np.isnan(n.ev__evidence_availability_fraction.iloc[0]) and m.empty
def test_manifest_deterministic_no_weights():
 e=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL));_,m1=e.analyze(actual_surface());_,m2=e.analyze(actual_surface().iloc[:1]);pd.testing.assert_frame_equal(m1,m2,check_exact=True);assert 'weight' not in m1.columns;assert set(m1.output_column)==set(e.analyze(actual_surface())[0].columns)-{'ev__evidence_feature_count','ev__evidence_available_count','ev__evidence_availability_fraction'}
def test_support_excluded_and_zero_available():
 out,_=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(actual_surface());assert out.ev__delta_ratio.iloc[0]==.4;assert out.ev__evidence_feature_count.iloc[0]<len([c for c in out if c.startswith('ev__')])-3;assert out.ev__evidence_available_count.iloc[0]>0
def test_outcome_leak_defense():
 d=actual_surface();d['future_return']=9;d['target_hit']=True;d['realized_pnl']=4;d['futureMFE']=3;d['y_true_next']=1;o,m=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(d);assert not any(any(x in c.lower() for x in ('future','target','pnl','mfe','y_true')) for c in o.columns);assert not m.source_column.astype(str).str.contains('future|target|pnl|mfe|y_true',case=False).any()
 for x in ('future_ret_5','realized_pnl','trade_result_1','target_hit_long','futureMFE','y_true_next'):
  with pytest.raises(EvidenceConfigError):FeatureSpec('safe','x',x,SemanticType.CONTEXT,MissingnessPolicy.ALLOW_MISSING,'finite_or_nan')
def test_event_category_and_nan_copy():
 d=pd.DataFrame({'structure_state_after':['UNDEFINED','UP_STRUCTURE'],'structural_break_event':['NONE','BOS_UP']});o,_=CausalEvidenceVectorEngine(config=cfg(structure=True)).analyze(d);assert o.ev__structure_state_after.dtype.name=='object' or 'string' in str(o.ev__structure_state_after.dtype);assert o.ev__structural_break_event.tolist()==['NONE','BOS_UP']
def test_domain_count_bool_collision_index():
 d=actual_surface();d.loc[1,'delta_magnitude_percentile']=2
 with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(d)
 d=actual_surface();d['delta_ratio_history_count']=d.delta_ratio_history_count.astype(float)
 with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(d)
 d=actual_surface();d['ev__delta_ratio']=0
 with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(d)
def test_input_immutability_empty_one():
 d=actual_surface();b=d.copy(deep=True);CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(d);pd.testing.assert_frame_equal(d,b,check_exact=True)
 e=pd.DataFrame(index=pd.RangeIndex(0));o,_=CausalEvidenceVectorEngine(config=cfg()).analyze(e);assert o.empty
def test_truncation_future_append_state():
 d=actual_surface();e=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL));full,_=e.analyze(d)
 for k in (1,2):pd.testing.assert_frame_equal(full.iloc[:k],e.analyze(d.iloc[:k])[0],check_exact=True)
 mut=d.copy();mut.loc[2,'delta_ratio']=-.4;mut.loc[2,'delta_magnitude']=.4;pd.testing.assert_frame_equal(full.iloc[:2],e.analyze(mut)[0].iloc[:2],check_exact=True)
 pd.testing.assert_frame_equal(full,e.analyze(d)[0],check_exact=True)
def test_real_environment_and_actual_integration():
 close=np.array([100.,101.,102.]);v=pd.DataFrame({'high':close+1,'low':close-1,'close':close});env=DynamicVolatilityEngine().analyze(v);flow=actual_surface();combined=pd.concat([env,flow.drop(columns=['close'])],axis=1);out,_=CausalEvidenceVectorEngine(config=cfg(environment=True,order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(combined);assert np.array_equal(out.ev__delta_ratio,flow.delta_ratio,equal_nan=True);assert np.array_equal(out.ev__true_range_percentile,env.true_range_percentile,equal_nan=True)
def test_no_score_outputs():
 o,_=CausalEvidenceVectorEngine(config=cfg()).analyze(pd.DataFrame(index=[0]));forbidden=('score','probability','conviction','threshold','trade_signal');assert not any(any(x in c for x in forbidden) for c in o.columns)

def _valid_for_config(config,index=pd.RangeIndex(1)):
 engine=CausalEvidenceVectorEngine(config=config);data={}
 for s in engine._specs():
  if s.expected_domain=='count':data[s.source_column]=pd.Series([0]*len(index),index=index,dtype='int64')
  elif s.expected_domain=='bool':data[s.source_column]=pd.Series([False]*len(index),index=index,dtype=bool)
  elif s.expected_domain=='structure_state':data[s.source_column]=pd.Series(['UNDEFINED']*len(index),index=index,dtype='string')
  elif s.expected_domain=='break_event':data[s.source_column]=pd.Series(['NONE']*len(index),index=index,dtype='string')
  elif s.expected_domain=='category_side':data[s.source_column]=pd.Series(['NONE']*len(index),index=index,dtype='string')
  elif s.expected_domain=='category_pressure':data[s.source_column]=pd.Series(['NONE']*len(index),index=index,dtype='string')
  else:data[s.source_column]=pd.Series([0.0]*len(index),index=index,dtype=float)
 return pd.DataFrame(data,index=index)

def test_catalog_integrity_and_exact_support_links():
 assert validate_v1_catalog()
 by={s.feature_name:s for s in V1_CATALOG}
 expected={'true_range_percentile':'true_range_history_count','expansion_percentile':'expansion_history_count','delta_ratio_percentile':'delta_ratio_history_count','delta_magnitude_percentile':'delta_magnitude_history_count','pressure_proxy_percentile':'pressure_proxy_history_count','pressure_magnitude_percentile':'pressure_magnitude_history_count','opposed_response_percentile':'opposed_response_history_count','pressure_opposed_response_percentile':'pressure_opposed_response_history_count','nearest_distance_percentile':'nearest_distance_reference_history_count','created_ob_displacement_percentile':'created_ob_displacement_history_count','created_fvg_gap_width_percentile':'created_fvg_gap_width_history_count'}
 assert {k:by[k].support_column for k in expected}==expected
 assert by['nearest_distance_reference_history_count'].event_local is False
 assert by['actual_absorption_evidence'].expected_domain=='unit_interval';assert by['proxy_absorption_evidence'].expected_domain=='unit_interval'

def test_exact_liquidity_and_multiscale_manifest_metadata():
 c=cfg(liquidity=True,multiscale=True);m=CausalEvidenceVectorEngine(config=c).manifest().set_index('feature_name')
 assert m.loc['nearest_same_side_distance_fraction','event_local']==True
 assert m.loc['nearest_distance_percentile','event_local']==True
 assert m.loc['nearest_distance_reference_history_count','semantic_type']=='COUNT_SUPPORT'
 assert m.loc['nearest_distance_reference_history_count','event_local']==False
 assert m.loc['directional_conflict','semantic_type']=='CONTEXT';assert m.loc['directional_conflict','expected_domain']=='bool';assert m.loc['directional_conflict','event_local']==False
 assert m.loc['directional_balance','expected_domain']=='signed_unit';assert m.loc['directional_consensus','expected_domain']=='unit_interval'

def test_no_arbitrary_registry_injection_path():
 arbitrary=FeatureSpec('harmless','x','harmless',SemanticType.CONTEXT,MissingnessPolicy.ALLOW_MISSING,'finite_or_nan')
 with pytest.raises(TypeError):CausalEvidenceVectorEngine(config=cfg(),registry=[arbitrary]) # type: ignore
 assert arbitrary not in V1_CATALOG

def test_availability_edges_and_huge_support_integer():
 c=cfg(structure=True,multiscale=True);d=_valid_for_config(c);d['structure_state_after']='UNDEFINED';d['structural_break_event']='NONE';d['directional_conflict']=False;d['directional_balance']=np.nan
 o,_=CausalEvidenceVectorEngine(config=c).analyze(d);assert o.ev__structural_break_event.iloc[0]=='NONE';assert o.ev__directional_conflict.iloc[0]==False;assert o.ev__availability_fraction.iloc[0]==0.0
 a=actual_surface().iloc[:1].copy();a['delta_ratio_history_count']=pd.Series([2**53+7],dtype='int64');a['delta_magnitude_history_count']=pd.Series([2**53+9],dtype='int64');a['opposed_response_history_count']=pd.Series([2**53+11],dtype='int64');out,_=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(a);assert out.ev__delta_ratio_history_count.iloc[0]==2**53+7

def test_numeric_dtype_adversaries():
 c=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL);base=actual_surface()
 for col,val in [('delta_ratio_history_count',-1),('delta_ratio_percentile',-0.1),('delta_magnitude_percentile',1.1),('delta_ratio',np.inf)]:
  d=base.copy();d.loc[1,col]=val
  with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=c).analyze(d)
 for dtype in ('float64','bool'):
  d=base.copy();d['delta_ratio_history_count']=d.delta_ratio_history_count.astype(dtype)
  with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=c).analyze(d)

def test_manifest_exact_schema_order_and_metadata_exclusion():
 e=CausalEvidenceVectorEngine(config=cfg(liquidity=True));m=e.manifest();assert m.columns.tolist()==['feature_name','output_column','source_module','source_column','semantic_type','missingness_policy','event_local','support_column','freshness_column','source_mode','directional_semantics','expected_domain','epistemic_status'];assert m.feature_name.tolist()==[s.feature_name for s in LIQ];assert not m.output_column.str.contains('evidence_feature_count|evidence_available').any()

def test_a_b_a_and_fresh_determinism():
 e=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL));a=actual_surface();b=actual_surface().iloc[:2];x=e.analyze(a)[0];e.analyze(b);z=e.analyze(a)[0];fresh=CausalEvidenceVectorEngine(config=e.config).analyze(a)[0];pd.testing.assert_frame_equal(x,z,check_exact=True);pd.testing.assert_frame_equal(x,fresh,check_exact=True)

def test_real_proxy_integration_exact():
 p=proxy_surface();o,_=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.PROXY)).analyze(p);np.testing.assert_allclose(o.ev__volume_pressure_proxy,p.volume_pressure_proxy,rtol=0,atol=0,equal_nan=True);np.testing.assert_allclose(o.ev__proxy_absorption_evidence,p.proxy_absorption_evidence,rtol=0,atol=0,equal_nan=True)

def test_real_structure_dealing_multiscale_integration():
 from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine
 from trading_system.structure.structural_breaks import CausalStructuralBreakEngine
 from trading_system.zones.dealing_range import CausalDealingRangeEngine
 from trading_system.multitimeframe.confluence_matrix import CausalConfluenceMatrixEngine,ScaleFrame
 index=pd.date_range('2024-01-01',periods=5,freq='h',tz='UTC');n=len(index)
 hf=np.array([True,False,True,False,False]);lf=np.array([False,True,False,True,False]);orig=pd.array([0,1,2,3,pd.NA],dtype='Int64');prices=[100.,90.,110.,95.,np.nan];conf=pd.array([0,1,2,3,pd.NA],dtype='Int64')
 a=pd.DataFrame({'swing_high_confirmed':hf,'swing_low_confirmed':lf,'swing_origin_position':orig,'swing_price':prices,'swing_confirmation_position':conf},index=index)
 b=ConfirmedSwingSequenceEngine().analyze(a);b.insert(0,'close',[95.]*n);b.insert(0,'low',[90.]*n);b.insert(0,'high',[100.]*n)
 c=CausalStructuralBreakEngine().analyze(b);r,_=CausalDealingRangeEngine().analyze(c)
 sf=pd.DataFrame({'available':True,'source_available_at':pd.Series(index,index=index),'structure_state_after':c.structure_state_after},index=index)
 mtf=CausalConfluenceMatrixEngine().analyze(pd.DataFrame(index=index),[ScaleFrame('base',sf)])
 combined=pd.concat([r,mtf],axis=1);combined=combined.loc[:,~combined.columns.duplicated()]
 config=cfg(structure=True,dealing_range=True,multiscale=True);out,_=CausalEvidenceVectorEngine(config=config).analyze(combined)
 pd.testing.assert_series_equal(out.ev__structure_state_after,c.structure_state_after,check_names=False)
 pd.testing.assert_series_equal(out.ev__current_midpoint_displacement,r.current_midpoint_displacement,check_names=False)
 pd.testing.assert_series_equal(out.ev__directional_balance,mtf.directional_balance,check_names=False)

def _real_ob_surface(two=False):
 from trading_system.zones.order_blocks import CausalOrderBlockEngine
 n=7;ohlc=[(10,12,8,11),(11,12,9,10),(10,11,8,9),(9,12,8,11),(11,15,10,14),(9,15,7,7),(10,14,8,9)]
 d=pd.DataFrame(ohlc,columns=['open','high','low','close'],dtype=float);d['swing_high_confirmed']=False;d['swing_low_confirmed']=False;d['swing_origin_position']=pd.array([pd.NA]*n,dtype='Int64');d['swing_confirmation_position']=pd.array([pd.NA]*n,dtype='Int64');d['swing_price']=np.nan;d.loc[1,'swing_low_confirmed']=True;d.loc[1,'swing_origin_position']=0;d.loc[1,'swing_confirmation_position']=1;d.loc[1,'swing_price']=8.;d['structural_break_event']='NONE';d['high_close_breach_event']=False;d['low_close_breach_event']=False;d['structure_state_before']='UNDEFINED';d.loc[4,['structural_break_event','structure_state_before','high_close_breach_event']]=['BOS_UP','UP_STRUCTURE',True]
 if two:d.loc[5,['structural_break_event','structure_state_before','high_close_breach_event']]=['CHOCH_UP','DOWN_STRUCTURE',True]
 return d,CausalOrderBlockEngine().analyze(d)[0]

def _real_fvg_surface():
 from trading_system.zones.fvg import CausalFVGEngine
 d=pd.DataFrame([(9,10,8,9),(11,12,10,11),(13,14,11,13),(15,16,13,15),(10,17,7,12)],columns=['open','high','low','close'],dtype=float)
 return d,CausalFVGEngine().analyze(d)[0]

def test_zones_config_is_explicitly_split():
 fields={f.name for f in dataclasses.fields(EvidenceVectorConfig)};assert 'order_blocks' in fields and 'fvg' in fields and 'zones' not in fields
 ob,_=CausalEvidenceVectorEngine(config=cfg(order_blocks=True)).analyze(_real_ob_surface()[1]);assert 'ev__created_ob_displacement_fraction' in ob and 'ev__created_fvg_gap_width_fraction' not in ob
 fv,_=CausalEvidenceVectorEngine(config=cfg(fvg=True)).analyze(_real_fvg_surface()[1]);assert 'ev__created_fvg_gap_width_fraction' in fv and 'ev__created_ob_displacement_fraction' not in fv

def test_real_ob_catalog_values_event_local_and_support():
 _,surface=_real_ob_surface(two=True);engine=CausalEvidenceVectorEngine(config=cfg(order_blocks=True));out,m=engine.analyze(surface)
 for spec in OB:pd.testing.assert_series_equal(out[spec.output_column],surface[spec.source_column],check_names=False)
 rows=np.flatnonzero(surface.created_ob_zone_id.notna());assert rows.tolist()==[4,5];assert surface.created_ob_displacement_history_count.iloc[4]==0;assert surface.created_ob_displacement_history_count.iloc[5]==1;assert math.isnan(surface.created_ob_displacement_percentile.iloc[4]);assert m.set_index('feature_name').loc['created_ob_displacement_percentile','support_column']=='created_ob_displacement_history_count'
 assert out.ev__created_ob_displacement_fraction.iloc[:4].isna().all();assert out.ev__bullish_ob_first_touch_count.iloc[:5].eq(0).all()

def test_real_fvg_catalog_values_event_local_and_support():
 _,surface=_real_fvg_surface();engine=CausalEvidenceVectorEngine(config=cfg(fvg=True));out,m=engine.analyze(surface)
 for spec in FVG:pd.testing.assert_series_equal(out[spec.output_column],surface[spec.source_column],check_names=False)
 rows=np.flatnonzero(surface.created_fvg_id.notna());assert len(rows)>=2;assert surface.created_fvg_gap_width_history_count.iloc[rows[0]]==0;assert surface.created_fvg_gap_width_history_count.iloc[rows[1]]==1;assert math.isnan(surface.created_fvg_gap_width_percentile.iloc[rows[0]]);assert m.set_index('feature_name').loc['created_fvg_gap_width_percentile','support_column']=='created_fvg_gap_width_history_count'

def test_real_zone_composition_prefix_causality():
 raw,full_surface=_real_ob_surface(two=True);engine=CausalEvidenceVectorEngine(config=cfg(order_blocks=True));full=engine.analyze(full_surface)[0]
 for k in range(1,len(raw)+1):
  from trading_system.zones.order_blocks import CausalOrderBlockEngine
  truncated=CausalOrderBlockEngine().analyze(raw.iloc[:k].copy())[0];pd.testing.assert_frame_equal(full.iloc[:k],engine.analyze(truncated)[0],check_exact=True)
 rawf,surfacef=_real_fvg_surface();ef=CausalEvidenceVectorEngine(config=cfg(fvg=True));fullf=ef.analyze(surfacef)[0]
 for k in range(1,len(rawf)+1):
  from trading_system.zones.fvg import CausalFVGEngine
  truncated=CausalFVGEngine().analyze(rawf.iloc[:k].copy())[0];pd.testing.assert_frame_equal(fullf.iloc[:k],ef.analyze(truncated)[0],check_exact=True)

def test_real_dealing_range_outside_domains():
 from trading_system.zones.dealing_range import CausalDealingRangeEngine
 from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine
 n=6;hf=[False,False,True,False,False,False];lf=[False,True,False,False,False,False];orig=pd.array([pd.NA,0,1,pd.NA,pd.NA,pd.NA],dtype='Int64');price=[np.nan,100.,200.,np.nan,np.nan,np.nan];conf=pd.array([pd.NA,1,2,pd.NA,pd.NA,pd.NA],dtype='Int64');a=pd.DataFrame({'swing_high_confirmed':hf,'swing_low_confirmed':lf,'swing_origin_position':orig,'swing_price':price,'swing_confirmation_position':conf});b=ConfirmedSwingSequenceEngine().analyze(a);b.insert(0,'close',[150,100,100,250,50,150]);r=CausalDealingRangeEngine().analyze(b)[0];o=CausalEvidenceVectorEngine(config=cfg(dealing_range=True)).analyze(r)[0];assert o.ev__current_range_position_raw.iloc[3]==1.5;assert o.ev__current_range_position_raw.iloc[4]==-.5;assert o.ev__current_premium_depth.iloc[3]==2;assert o.ev__current_discount_depth.iloc[4]==2

def test_manifest_external_mutation_isolation():
 e=CausalEvidenceVectorEngine(config=cfg(liquidity=True));m1=e.manifest();m1.loc[0,'feature_name']='MUTATED';m2=e.manifest();assert m2.loc[0,'feature_name']!='MUTATED'

@pytest.mark.parametrize('value',('UNDEFINED','UP_STRUCTURE','DOWN_STRUCTURE','MIXED'))
def test_structure_state_all_valid_categories(value):
 CausalEvidenceVectorEngine(config=cfg(structure=True)).analyze(pd.DataFrame({'structure_state_after':pd.Series([value],dtype='string'),'structural_break_event':pd.Series(['NONE'],dtype='string')}))

def test_structure_state_invalid_and_missing_rejected():
 for value in ('INVALID',pd.NA):
  d=pd.DataFrame({'structure_state_after':pd.Series([value],dtype='string'),'structural_break_event':pd.Series(['NONE'],dtype='string')})
  with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=cfg(structure=True)).analyze(d)

@pytest.mark.parametrize('value',('NONE','BOS_UP','BOS_DOWN','CHOCH_UP','CHOCH_DOWN','UNCLASSIFIED_BREAK','AMBIGUOUS_DOUBLE_BREAK'))
def test_structural_break_all_valid_categories(value):
 CausalEvidenceVectorEngine(config=cfg(structure=True)).analyze(pd.DataFrame({'structure_state_after':pd.Series(['UNDEFINED'],dtype='string'),'structural_break_event':pd.Series([value],dtype='string')}))

def test_structural_break_invalid_and_missing_rejected():
 for value in ('INVALID',pd.NA):
  d=pd.DataFrame({'structure_state_after':pd.Series(['UNDEFINED'],dtype='string'),'structural_break_event':pd.Series([value],dtype='string')})
  with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=cfg(structure=True)).analyze(d)

@pytest.mark.parametrize('value',('BUY','SELL','NONE'))
def test_absorbed_aggression_all_valid_categories(value):
 d=actual_surface().iloc[:1].copy();d['absorbed_aggression_side']=pd.Series([value],dtype='string');CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(d)

def test_absorbed_aggression_invalid_and_missing_rejected():
 for value in ('INVALID',pd.NA):
  d=actual_surface().iloc[:1].copy();d['absorbed_aggression_side']=pd.Series([value],dtype='string')
  with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(d)

@pytest.mark.parametrize('value',('POSITIVE','NEGATIVE','NONE'))
def test_pressure_side_all_valid_categories(value):
 d=proxy_surface().iloc[:1].copy();d['pressure_side']=pd.Series([value],dtype='string');CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.PROXY)).analyze(d)

def test_pressure_side_invalid_and_missing_rejected():
 for value in ('INVALID',pd.NA):
  d=proxy_surface().iloc[:1].copy();d['pressure_side']=pd.Series([value],dtype='string')
  with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.PROXY)).analyze(d)

def test_declared_missingness_policy_generic_enforcement():
 allow_numeric=FeatureSpec('allow_numeric','x','allow_numeric',SemanticType.CONTEXT,MissingnessPolicy.ALLOW_MISSING,'finite_or_nan')
 required_count=FeatureSpec('required_count','x','required_count',SemanticType.COUNT_SUPPORT,MissingnessPolicy.NONMISSING,'count')
 required_bool=FeatureSpec('required_bool','x','required_bool',SemanticType.CONTEXT,MissingnessPolicy.NONMISSING,'bool')
 required_category=FeatureSpec('required_category','x','required_category',SemanticType.CATEGORY,MissingnessPolicy.NONMISSING,'structure_state')
 CausalEvidenceVectorEngine._validate_series(pd.Series([1.0,np.nan]),allow_numeric)
 for series,spec in ((pd.Series([1,pd.NA],dtype='Int64'),required_count),(pd.Series([True,pd.NA],dtype='boolean'),required_bool),(pd.Series(['UP_STRUCTURE',pd.NA],dtype='string'),required_category)):
  with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine._validate_series(series,spec)

def test_directional_semantics_and_epistemic_metadata_exact():
 by={s.feature_name:s for s in V1_CATALOG}
 assert by['normalized_tr_change'].directional_semantics=='VOLATILITY_CHANGE_DIRECTION'
 assert by['delta_ratio'].directional_semantics=='PRICE_OR_FLOW_DIRECTION'
 assert by['volume_pressure_proxy'].directional_semantics=='PRICE_OR_FLOW_DIRECTION'
 assert by['current_midpoint_displacement'].directional_semantics=='RANGE_LOCATION_DIRECTION'
 assert by['directional_balance'].directional_semantics=='STRUCTURE_DIRECTION'
 assert by['actual_absorption_evidence'].epistemic_status=='PROJECT_OPERATIONAL'
 assert by['proxy_absorption_evidence'].epistemic_status=='SOURCE_APPROXIMATION'
 assert by['opposed_response_percentile'].epistemic_status=='PROJECT_OPERATIONAL'
 assert by['pressure_opposed_response_percentile'].epistemic_status=='SOURCE_APPROXIMATION'

def test_missingness_manifest_matches_runtime_contract():
 m=CausalEvidenceVectorEngine(config=cfg(environment=True,structure=True)).manifest().set_index('feature_name')
 assert m.loc['true_range_percentile','missingness_policy']=='ALLOW_MISSING'
 assert m.loc['true_range_history_count','missingness_policy']=='NONMISSING'
 assert m.loc['structure_state_after','missingness_policy']=='NONMISSING'
 assert m.loc['structural_break_event','missingness_policy']=='NONMISSING'

def test_unit_signed_boundaries_and_negative_infinity():
 proxy=proxy_surface().copy();proxy.loc[0,'volume_pressure_proxy']=-1.;proxy.loc[1,'volume_pressure_proxy']=1.
 CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.PROXY)).analyze(proxy)
 bad=actual_surface().copy();bad.loc[1,'delta_ratio']=-np.inf
 with pytest.raises(EvidenceDataError):CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)).analyze(bad)

def test_true_future_append_multi_feature_and_real_pipeline():
 base=actual_surface();base['structure_state_after']=pd.Series(['UNDEFINED','UP_STRUCTURE','UP_STRUCTURE'],dtype='string');base['structural_break_event']=pd.Series(['NONE','BOS_UP','NONE'],dtype='string')
 engine=CausalEvidenceVectorEngine(config=cfg(structure=True,order_flow_mode=OrderFlowEvidenceMode.ACTUAL));result=engine.analyze(base)[0]
 extended_raw=pd.DataFrame({'close':[100.,101.,101.,120.],'buy_volume':[7.,7.,7.,1.],'sell_volume':[3.,3.,3.,9.]});extended_flow=CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(extended_raw);extended_actual=CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(extended_flow);extended_actual['structure_state_after']=pd.Series(['UNDEFINED','UP_STRUCTURE','UP_STRUCTURE','DOWN_STRUCTURE'],dtype='string');extended_actual['structural_break_event']=pd.Series(['NONE','BOS_UP','NONE','CHOCH_DOWN'],dtype='string')
 pd.testing.assert_frame_equal(result,engine.analyze(extended_actual)[0].iloc[:len(base)],check_exact=True)
 raw,ob_surface=_real_ob_surface(two=True);ob_engine=CausalEvidenceVectorEngine(config=cfg(order_blocks=True));ob_result=ob_engine.analyze(ob_surface)[0]
 raw_extra=pd.concat([raw,raw.iloc[[-1]].copy()],ignore_index=True);raw_extra.loc[len(raw_extra)-1,['structural_break_event','structure_state_before','high_close_breach_event','low_close_breach_event']]=['NONE','UNDEFINED',False,False];raw_extra.loc[len(raw_extra)-1,['swing_high_confirmed','swing_low_confirmed']]=[False,False];raw_extra.loc[len(raw_extra)-1,['swing_origin_position','swing_confirmation_position','swing_price']]=[pd.NA,pd.NA,np.nan]
 from trading_system.zones.order_blocks import CausalOrderBlockEngine
 extended_surface=CausalOrderBlockEngine().analyze(raw_extra)[0]
 pd.testing.assert_frame_equal(ob_result,ob_engine.analyze(extended_surface)[0].iloc[:len(raw)],check_exact=True)

def test_forbidden_score_names_exact_and_prefixed():
 forbidden=('setup_score','probability','conviction','bullish_score','bearish_score','confluence_score','threshold','trade_signal')
 for config,frame in ((cfg(),pd.DataFrame(index=[0])),(cfg(order_flow_mode=OrderFlowEvidenceMode.ACTUAL),actual_surface())):
  out,m=CausalEvidenceVectorEngine(config=config).analyze(frame)
  names=set(out.columns)|set(m.output_column.astype(str))
  for name in forbidden:
   assert name not in names and 'ev__'+name not in names

def test_proxy_manifest_exact_epistemic_contract():
 manifest=CausalEvidenceVectorEngine(config=cfg(order_flow_mode=OrderFlowEvidenceMode.PROXY)).manifest().set_index('feature_name')
 expected={
  'volume_pressure_proxy':('SIGNED_DIRECTIONAL','signed_unit','PRICE_OR_FLOW_DIRECTION','ALLOW_MISSING'),
  'pressure_proxy_percentile':('CONTEXT','percentile','NONE','ALLOW_MISSING'),
  'pressure_proxy_history_count':('COUNT_SUPPORT','count','NONE','NONMISSING'),
  'pressure_magnitude_percentile':('MAGNITUDE','percentile','NONE','ALLOW_MISSING'),
  'pressure_magnitude_history_count':('COUNT_SUPPORT','count','NONE','NONMISSING'),
  'proxy_absorption_evidence':('MAGNITUDE','unit_interval','NONE','ALLOW_MISSING'),
  'pressure_side':('CATEGORY','category_pressure','NONE','NONMISSING'),
  'pressure_opposed_response_percentile':('MAGNITUDE','percentile','NONE','ALLOW_MISSING'),
  'pressure_opposed_response_history_count':('COUNT_SUPPORT','count','NONE','NONMISSING'),
 }
 assert manifest.index.tolist()==list(expected)
 for name,(semantic,domain,direction,missingness) in expected.items():
  row=manifest.loc[name]
  assert row.source_mode=='PROXY'
  assert row.epistemic_status=='SOURCE_APPROXIMATION'
  assert row.semantic_type==semantic
  assert row.expected_domain==domain
  assert row.directional_semantics==direction
  assert row.missingness_policy==missingness
 assert not (manifest.epistemic_status=='FACTUAL').any()

```

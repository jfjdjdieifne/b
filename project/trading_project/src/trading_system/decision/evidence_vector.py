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

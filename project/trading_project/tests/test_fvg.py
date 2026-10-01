import math,numpy as np,pandas as pd,pytest
from trading_system.zones.fvg import CausalFVGEngine,FVGDataError,_FVGAuditEngine
from trading_system.audit.causal_state import *
def df(rows):return pd.DataFrame(rows,columns=['open','high','low','close'],dtype=float)
def test_geometries_timing_equality():
 d=df([(9,10,8,9),(10,11,9,10),(12,13,11,12)]);b,e=CausalFVGEngine().analyze(d);assert b.loc[2,'fvg_candidate_created'];assert b.loc[2,'created_fvg_zone_low']==10;assert b.loc[2,'created_fvg_zone_high']==11;assert not b.loc[:1,'fvg_candidate_created'].any();assert len(e)==1
 d2=df([(10,11,9,10),(9,10,8,9),(7,8,6,7)]);b,_=CausalFVGEngine().analyze(d2);assert b.loc[2,'created_fvg_direction']=='BEARISH_FVG_CANDIDATE'
 eq=df([(9,10,8,9),(9,10,8,9),(10,11,10,10)]);assert not CausalFVGEngine().analyze(eq)[0].fvg_candidate_created.any()
def test_stacking_identity_width_body():
 d=df([(9,10,8,9),(11,12,10,11),(13,14,13,13.5),(15,16,15,15.5)]);b,e=CausalFVGEngine().analyze(d);assert b.created_fvg_id.dropna().tolist()==[0,1];assert b.loc[2,'created_fvg_gap_width']==3;assert math.isnan(b.loc[2,'created_fvg_gap_width_percentile']);assert b.loc[3,'created_fvg_gap_width_history_count']==1
def test_lifecycle_multifact_reclaim():
 d=df([(9,10,8,9),(11,12,10,11),(13,14,11,13),(10,12,7,8),(9,11,8,10)]);b,e=CausalFVGEngine().analyze(d);types=e[e.fvg_id==0].event_type.tolist();assert all(x in types for x in ['FIRST_TOUCH','FIRST_FULL_RANGE_COVERAGE','FIRST_FAR_SIDE_WICK_BREACH','FIRST_FAR_SIDE_CLOSE_BREACH','FIRST_CLOSE_RECLAIM_OF_FAR_SIDE']);assert types.count('FIRST_TOUCH')==1
def test_creation_bar_old_interaction_and_multiple():
 d=df([(9,10,8,9),(11,12,10,11),(13,14,11,13),(15,16,13,15),(10,17,7,12)]);b,e=CausalFVGEngine().analyze(d);assert b.known_bullish_fvg_candidate_count.iloc[-1]>=2;assert e[e.event_position==4].fvg_id.nunique()>=2
def audit(d):
 fb,fe=CausalFVGEngine().analyze(d)
 for k in range(1,len(d)):
  tb,te=CausalFVGEngine().analyze(d.iloc[:k]);pd.testing.assert_frame_equal(fb.iloc[:k],tb,check_exact=True);pd.testing.assert_frame_equal(fe[fe.event_position<k].reset_index(drop=True),te,check_exact=True)
def test_audits_state_future_scale():
 d=df([(9,10,8,9),(11,12,10,11),(13,14,11,13),(10,12,7,8),(9,11,8,10)]);r=verify_truncation_invariance(_FVGAuditEngine,d,split_fractions=(),additional_split_points=[1,2,3,4]);assert all(x.passed for x in r);assert verify_state_isolation(_FVGAuditEngine,d,d*2,policy=ReentrancyPolicy.IDEMPOTENT_REENTRANT).passed;audit(d);b,e=CausalFVGEngine().analyze(d);bs,es=CausalFVGEngine().analyze(d*8);pd.testing.assert_series_equal(b.created_fvg_gap_width_fraction,bs.created_fvg_gap_width_fraction,check_exact=True)
def test_close_reclaim_gap_over_requires_no_touch():
 d=df([(9,10,8,9),(11,12,10,11),(13,14,11,13),(9,12,7,8),(12.5,13,12,12.5)])
 b,e=CausalFVGEngine().analyze(d);r=e[(e.fvg_id==0)&(e.event_type=='FIRST_CLOSE_RECLAIM_OF_FAR_SIDE')];assert r.event_position.tolist()==[4];assert b.loc[4,'bullish_fvg_first_close_reclaim_count']==1;assert not ((e.event_position==4)&(e.event_type=='FIRST_TOUCH')).any()

def test_partial_coverage_exact_far_touch_and_no_repeats():
 d=df([(9,10,8,9),(11,12,10,11),(13,14,12,13),(11.5,12,11,11),(10,12,10,11),(9,13,8,9)])
 b,e=CausalFVGEngine().analyze(d);touch=e[(e.fvg_id==0)&(e.event_type=='FIRST_TOUCH')];assert touch.zone_range_coverage_fraction.iloc[0]==0.5;assert not b.loc[4,'bullish_fvg_first_far_side_wick_breach_count'];assert e[(e.fvg_id==0)&(e.event_type=='FIRST_TOUCH')].shape[0]==1;assert e[(e.fvg_id==0)&(e.event_type=='FIRST_FULL_RANGE_COVERAGE')].shape[0]==1;assert e[(e.fvg_id==0)&(e.event_type=='FIRST_FAR_SIDE_WICK_BREACH')].shape[0]==1

def test_event_table_schema_positions_ids_and_path_ambiguity():
 d=df([(9,10,8,9),(11,12,10,11),(13,14,11,13),(10,15,7,8)])
 b,e=CausalFVGEngine().analyze(d);assert list(e.columns)==list(__import__('trading_system.zones.fvg',fromlist=['_E'])._E);assert (e[e.event_type!='FVG_CREATED'].event_position>e[e.event_type!='FVG_CREATED'].creation_position).all();assert (e[e.event_type=='FVG_CREATED'].event_position==e[e.event_type=='FVG_CREATED'].creation_position).all();assert set(e.fvg_id)<=set(e[e.event_type=='FVG_CREATED'].fvg_id)
 b2,e2=CausalFVGEngine().analyze(d.copy());pd.testing.assert_frame_equal(b,b2,check_exact=True);pd.testing.assert_frame_equal(e,e2,check_exact=True)

def test_numerical_overflow_rejected():
 m=np.finfo(float).max;d=df([(-m,-m,-m,-m),(0,1,-1,0),(m,m,m,m)])
 with pytest.raises(FVGDataError,match='width overflow'):CausalFVGEngine().analyze(d)

def test_explicit_input_contract_cases():
 valid=df([(9,10,8,9)])
 cases=[valid.assign(high=np.inf),valid.assign(open=20),valid.assign(close=20),df([(9,8,10,9)])]
 for x in cases:
  with pytest.raises(FVGDataError):CausalFVGEngine().analyze(x)
 x=valid.copy();x['open']=True
 with pytest.raises(FVGDataError):CausalFVGEngine().analyze(x)
 x=valid.copy();x.index=[1];x['created_fvg_id']=0
 with pytest.raises(FVGDataError):CausalFVGEngine().analyze(x)
 dup=df([(9,10,8,9),(9,10,8,9)]);dup.index=[1,1]
 with pytest.raises(FVGDataError):CausalFVGEngine().analyze(dup)
 un=df([(9,10,8,9),(9,10,8,9)]);un.index=[2,1]
 with pytest.raises(FVGDataError):CausalFVGEngine().analyze(un)
 bad=valid.copy();bad['open']='x'
 with pytest.raises(FVGDataError):CausalFVGEngine().analyze(bad)

def test_validation_empty_immutable():
 empty=df([]);b,e=CausalFVGEngine().analyze(empty);assert b.empty and e.empty;assert list(e.columns)==list(__import__('trading_system.zones.fvg',fromlist=['_E'])._E)
 d=df([(9,10,8,9)]);before=d.copy();CausalFVGEngine().analyze(d);pd.testing.assert_frame_equal(d,before)
 for x in [d.assign(high=np.nan),df([(9,8,10,9)]),df([(20,10,8,9)])]:
  with pytest.raises(FVGDataError):CausalFVGEngine().analyze(x)


# =====================================================================
# EXACT PERFORMANCE V2 PATCH-2 gates
# Differential old-vs-new against the verbatim pre-patch reference copy
# (tests/_patch_reference_src/fvg_pre.py, sha256-pinned), exact cumulative
# counter proof, causality (prefix truncation + future append), and a
# mutation proof for the cumulative increment.
# =====================================================================

import hashlib as _hashlib
import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_REF_PATH = _Path(__file__).resolve().parent / "_patch_reference_src" / "fvg_pre.py"


def _load_reference_fvg():
    # Pin the exact pre-patch bytes (md5 of the snapshot taken before patching).
    digest = _hashlib.sha256(_REF_PATH.read_bytes()).hexdigest()
    spec = _importlib_util.spec_from_file_location("_patch_ref_fvg", _REF_PATH)
    module = _importlib_util.module_from_spec(spec)
    _sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, digest


REF_FVG, _REF_DIGEST = _load_reference_fvg()

# Recorded pre-patch sha256 of src/trading_system/zones/fvg.py
# (identical bytes to the reference snapshot).
_PRE_PATCH_FVG_SHA256 = (
    "c6f462862bf1bb3213acfc4ef70d69a0633384e102ae6b3e24ad0a8b80e58cd2"
)


def test_patch_v2_fvg_reference_snapshot_is_pinned():
    assert _REF_PATH.exists()
    assert _REF_DIGEST == _PRE_PATCH_FVG_SHA256, (
        "tests/_patch_reference_src/fvg_pre.py must remain the verbatim "
        "pre-patch snapshot of src/trading_system/zones/fvg.py"
    )


def _fvg_fixture_frames():
    rng = np.random.default_rng(20260929)
    frames = {}

    frames["empty"] = df([])
    frames["no_candidates"] = df([(9, 10, 8, 9), (9.5, 10.5, 8.5, 9.5), (9, 10, 8, 9), (9.5, 10.5, 8.5, 9.5)])

    frames["all_bullish"] = df([
        (9, 10, 8, 9), (11, 12, 10, 11), (13, 14, 11, 13),
        (15, 16, 13, 15), (17, 18, 15, 17), (19, 20, 17, 19),
    ])

    frames["all_bearish"] = df([
        (19, 20, 18, 19), (17, 18, 16, 17), (15, 16, 13, 15),
        (13, 14, 11, 13), (11, 12, 9, 11), (9, 10, 7, 9),
    ])

    frames["alternating"] = df([
        (9, 10, 8, 9), (11, 12, 10, 11), (10, 11, 9, 10),
        (8, 9, 7, 8), (10, 11, 9, 10), (12, 13, 11, 12),
        (11, 12, 10, 11), (9, 10, 8, 9),
    ])

    def random_walk(n, seed, gap_prob=0.18):
        local = np.random.default_rng(seed)
        price = 100.0
        rows = []
        for _ in range(n):
            jump = local.normal(0, 0.9)
            if local.random() < gap_prob:
                jump += local.choice([-1.0, 1.0]) * local.uniform(1.2, 2.6)
            open_price = price
            close = open_price + jump
            high = max(open_price, close) + abs(local.normal(0, 0.35))
            low = min(open_price, close) - abs(local.normal(0, 0.35))
            rows.append((
                round(open_price, 8), round(high, 8),
                round(low, 8), round(close, 8),
            ))
            price = close
        return df(rows)

    frames["many_seeded"] = random_walk(120, 7)
    frames["realistic_seeded"] = random_walk(80, 11, gap_prob=0.10)

    # Stress: larger adversarial frames exercising lifecycle depth.
    frames["stress_300"] = random_walk(300, 23)
    frames["stress_600_dense"] = random_walk(600, 29, gap_prob=0.22)

    # Zero-width touch edge + mixed signed zeros in zone values.
    frames["signed_zero_mix"] = df([
        (0.0, 0.0, -0.0, 0.0), (-0.0, 0.0, -0.0, -0.0),
        (1.0, 2.0, -0.0, 1.5), (-0.0, 0.0, -1.0, -0.5),
        (2.0, 3.0, 1.0, 2.5), (0.5, 1.0, -0.5, 0.0),
    ])
    return frames


def _assert_bits_equal(got, ref, label):
    # Bit-level float comparison (+0.0 vs -0.0 and NaN placement included).
    for column in got.columns:
        g = got[column]
        r = ref[column]
        if pd.api.types.is_float_dtype(g.dtype):
            ga = g.to_numpy(dtype=np.float64)
            ra = r.to_numpy(dtype=np.float64)
            assert (ga.view(np.uint64) == ra.view(np.uint64)).all(), (
                label, column, "float bits differ"
            )
        else:
            assert g.equals(r), (label, column)


def _assert_fvg_frames_identical(got_bars, got_events, ref_bars, ref_events, label):
    _assert_bits_equal(got_bars, ref_bars, f"{label}:bars")
    _assert_bits_equal(got_events, ref_events, f"{label}:events")
    pd.testing.assert_frame_equal(got_bars, ref_bars, check_exact=True, check_dtype=True)
    pd.testing.assert_frame_equal(got_events, ref_events, check_exact=True, check_dtype=True)
    assert list(got_bars.columns) == list(ref_bars.columns), label
    assert list(got_events.columns) == list(ref_events.columns), label


def test_patch_v2_fvg_differential_exact_battery():
    for label, frame in _fvg_fixture_frames().items():
        got_bars, got_events = CausalFVGEngine().analyze(frame.copy())
        ref_bars, ref_events = REF_FVG.CausalFVGEngine().analyze(frame.copy())
        _assert_fvg_frames_identical(
            got_bars, got_events, ref_bars, ref_events, label
        )


def test_patch_v2_fvg_cumulative_counters_are_exact():
    for label, frame in _fvg_fixture_frames().items():
        if frame.empty:
            continue
        bars, events = CausalFVGEngine().analyze(frame.copy())
        created = events[events["event_type"] == "FVG_CREATED"]
        n = len(frame)
        expected_bull = np.zeros(n, dtype=np.int64)
        expected_bear = np.zeros(n, dtype=np.int64)
        for row in created.itertuples():
            is_bull = str(row.direction).startswith("BULLISH")
            start = int(row.creation_position)
            for i in range(start, n):
                if is_bull:
                    expected_bull[i] += 1
                else:
                    expected_bear[i] += 1
        got_bull = bars["known_bullish_fvg_candidate_count"].to_numpy(dtype=np.int64)
        got_bear = bars["known_bearish_fvg_candidate_count"].to_numpy(dtype=np.int64)
        assert (got_bull == expected_bull).all(), label
        assert (got_bear == expected_bear).all(), label


def test_patch_v2_fvg_prefix_truncation_and_future_append():
    frame = _fvg_fixture_frames()["many_seeded"]
    full_bars, full_events = CausalFVGEngine().analyze(frame.copy())
    ref_bars, ref_events = REF_FVG.CausalFVGEngine().analyze(frame.copy())
    n = len(frame)
    for split_at in (1, 2, 5, 17, 40, n - 1):
        truncated_bars, truncated_events = CausalFVGEngine().analyze(
            frame.iloc[:split_at].copy()
        )
        pd.testing.assert_frame_equal(
            full_bars.iloc[:split_at], truncated_bars, check_exact=True
        )
        pd.testing.assert_frame_equal(
            _filter_events(full_events, split_at), truncated_events, check_exact=True
        )

    # Future suffix append: bars/events up to T must be untouched.
    rng = np.random.default_rng(5)
    extra_rows = []
    price = float(frame["close"].iloc[-1])
    for _ in range(25):
        open_price = price
        close = open_price + rng.normal(0, 1.4)
        high = max(open_price, close) + abs(rng.normal(0, 0.4))
        low = min(open_price, close) - abs(rng.normal(0, 0.4))
        extra_rows.append((open_price, high, low, close))
        price = close
    extended = pd.concat([frame, df(extra_rows)], ignore_index=True)
    ext_bars, ext_events = CausalFVGEngine().analyze(extended.copy())
    pd.testing.assert_frame_equal(
        ext_bars.iloc[:n], full_bars, check_exact=True
    )
    pd.testing.assert_frame_equal(
        _filter_events(ext_events, n), full_events, check_exact=True
    )
    # Reference agrees on the extended frame as well.
    ref_ext_bars, ref_ext_events = REF_FVG.CausalFVGEngine().analyze(extended.copy())
    _assert_fvg_frames_identical(
        ext_bars, ext_events, ref_ext_bars, ref_ext_events, "extended"
    )


def _filter_events(events, split_at):
    if events.empty:
        return events.reset_index(drop=True)
    return events[events["event_position"] < split_at].reset_index(drop=True)


def _exec_mutated_fvg(mutate, module_name):
    source = _Path("src/trading_system/zones/fvg.py").read_text(encoding="utf-8")
    mutated_source = mutate(source)
    assert mutated_source != source, "mutation did not apply"
    import types

    module = types.ModuleType(module_name)
    _sys.modules[module_name] = module
    exec(compile(mutated_source, module_name, "exec"), module.__dict__)
    return module


def test_patch_v2_mutation_fvg_increment_break_is_detected():
    def mutate(source):
        broken = source.replace(
            "kb_run+=f.direction.startswith(\"BULLISH\");ks_run+=not f.direction.startswith(\"BULLISH\");",
            "kb_run+=1;ks_run+=1;",
        )
        return broken

    broken_module = _exec_mutated_fvg(mutate, "_mutated_fvg_counters")
    frame = _fvg_fixture_frames()["alternating"]
    broken_bars, _ = broken_module.CausalFVGEngine().analyze(frame.copy())
    ref_bars, _ = REF_FVG.CausalFVGEngine().analyze(frame.copy())
    assert not broken_bars["known_bullish_fvg_candidate_count"].equals(
        ref_bars["known_bullish_fvg_candidate_count"]
    ), (
        "FVG cumulative-counter mutation must be detected by the differential "
        "battery (all-bullish/all-bearish miscount)"
    )
    assert not broken_bars["known_bearish_fvg_candidate_count"].equals(
        ref_bars["known_bearish_fvg_candidate_count"]
    )

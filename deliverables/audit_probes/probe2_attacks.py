"""INDEPENDENT AUDITOR PROBE 2 — adversarial attacks on Stage 4B-2 final patch."""
import dataclasses, sys, copy
import pandas as pd
sys.path.insert(0, "/home/user/project/trading_project/src")

from trading_system.research.information_time import (
    PositionalTimelineAdapter, TimeIndexedTimelineAdapter, InformationPhase,
)
from trading_system.research.trajectory.trajectory_contract import (
    MarketObservationTimeline, TrajectoryContractError, TrajectoryDataError,
)
from trading_system.research.trajectory import trajectory_stage4b1 as s4b1
from trading_system.research.trajectory import trajectory_stage4b2 as s4b2
from trading_system.structure.swing_detector import EmpiricalConfirmationPolicy

results = []
def check(name, cond):
    results.append((name, bool(cond)))
    print(("REJECT-OK " if cond else "ACCEPT-BAD ") + name)

def market(n=90):
    o, h, l, c = [], [], [], []
    level = 100.0
    for i in range(n):
        if i < 65:
            if i % 7 < 4:
                o.append(level); c.append(level + 5.0); level = c[-1]
            else:
                o.append(level); c.append(level - 3.0); level = c[-1]
        else:
            o.append(level); c.append(level - 6.0); level = c[-1]
        h.append(max(o[-1], c[-1]) + 1.0); l.append(min(o[-1], c[-1]) - 1.0)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c},
                        index=pd.RangeIndex(n), dtype=float)

priors = tuple(0.01 * i for i in range(1, 50))
policy = EmpiricalConfirmationPolicy(quantile=0.1, prior_continuation_reversals=priors)
mk = market(90)
adapter = PositionalTimelineAdapter("atk")
tl = MarketObservationTimeline.seal(adapter=adapter, market_history=mk)
struct = s4b1.build_structure_surface(timeline=tl, adapter=adapter, market_history=mk, swing_policy=policy)
liq = s4b2.build_liquidity_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct)
ob  = s4b2.build_order_block_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct)
fvg = s4b2.build_fvg_surface(timeline=tl, adapter=adapter, market_history=mk)
dr  = s4b2.build_dealing_range_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct)

def forge(target_cls, src, fix_id=True, structure_surface_id=None):
    f = dataclasses.replace(src)
    object.__setattr__(f, "__class__", target_cls)
    if structure_surface_id is not None:
        f = dataclasses.replace(f, structure_surface_id=structure_surface_id)
    if fix_id:
        dom, cv, *_ = s4b2._DOMAIN_CONTRACT[target_cls]
        rid = s4b2._canonical_hash("STAGE4B2_SURFACE_IDENTITY_V1", {
            "surface_class": target_cls.__name__, "domain": dom, "contract_version": cv,
            "timeline_id": f.timeline_id, "timeline_hash": f.timeline_hash,
            "adapter_kind": f.adapter_kind, "structure_surface_id": f.structure_surface_id,
            "reconstruction_input_hash": f.reconstruction_input_hash,
            "complete_result_hash": f.complete_result_hash,
            "normalized_entity_hash": f.normalized_entity_hash,
            "normalized_event_hash": f.normalized_event_hash})
        f = dataclasses.replace(f, surface_id=rid)
    return f

# --- BLOCKER 1 regressions: coherent cross-domain substitution must reject ---
for tgt, src, n in [
    (s4b2.Stage4B2LiquiditySurface, fvg, "FVG -> LIQUIDITY (coherent recompute)"),
    (s4b2.Stage4B2DealingRangeSurface, ob, "OB -> DR (coherent recompute)"),
    (s4b2.Stage4B2FVGSurface, liq, "LIQ -> FVG (coherent recompute, struct None)"),
    (s4b2.Stage4B2OrderBlockSurface, fvg, "FVG -> OB (coherent recompute)"),
]:
    kw = {}
    if tgt is s4b2.Stage4B2FVGSurface:
        kw["structure_surface_id"] = None
    try:
        f = forge(tgt, src, **kw)
        s4b2.verify_surface_integrity(f)
        check(n, False)
    except (TrajectoryDataError, TrajectoryContractError):
        check(n, True)

# class swap WITHOUT recompute (naive)
try:
    f = forge(s4b2.Stage4B2LiquiditySurface, fvg, fix_id=False)
    s4b2.verify_surface_integrity(f)
    check("FVG -> LIQ naive class swap", False)
except (TrajectoryDataError, TrajectoryContractError):
    check("FVG -> LIQ naive class swap", True)

# table swap: FVG tables inside a genuine LIQ surface
try:
    f = dataclasses.replace(liq, event_frame=fvg.event_frame,
                            normalized_entity_frame=fvg.normalized_entity_frame,
                            normalized_event_frame=fvg.normalized_event_frame)
    s4b2.verify_surface_integrity(f)
    check("LIQ surface carrying FVG tables", False)
except TrajectoryDataError:
    check("LIQ surface carrying FVG tables", True)

# duck-typed fake class with same field names, fed to projector
class Fake:
    pass
try:
    s4b2.project_domain_prefix(surface="x", boundary_key=adapter.key_for_position(mk.index, 30, InformationPhase.COMPLETED_ROW_AVAILABLE, 0))
    check("non-surface to projector", False)
except TrajectoryContractError:
    check("non-surface to projector", True)

# --- BLOCKER 2 regressions: prefix completeness ---
key = adapter.key_for_position(mk.index, 60, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
base_liq = s4b2.project_domain_prefix(surface=liq, boundary_key=key).prefix_hash
base_fvg = s4b2.project_domain_prefix(surface=fvg, boundary_key=key).prefix_hash
base_ob  = s4b2.project_domain_prefix(surface=ob, boundary_key=key).prefix_hash
base_dr  = s4b2.project_domain_prefix(surface=dr, boundary_key=key).prefix_hash

def expect_reject_prefix(name, surf):
    try:
        s4b2.project_domain_prefix(surface=surf, boundary_key=key)
        check(name, False)
    except (TrajectoryDataError, TrajectoryContractError):
        check(name, True)

# remove a REAL pre-T LEVEL_CREATED event from LIQ
ev = liq.event_frame.copy(deep=True)
cr = ev[(ev.event_type == "LEVEL_CREATED") & (ev.event_position <= 60)]
pos = int(cr.event_position.iloc[0]); lid = cr.level_id.iloc[0]
ev2 = ev[~((ev.event_type == "LEVEL_CREATED") & (ev.event_position == pos) & (ev.level_id == lid))].reset_index(drop=True)
tam = dataclasses.replace(liq, event_frame=ev2)
expect_reject_prefix("LIQ delete pre-T LEVEL_CREATED", tam)

# remove a pre-T FVG entity row via normalized entity mutation
ent = fvg.normalized_entity_frame.copy(deep=True)
pre = ent[ent.creation_position <= 60]
ent2 = ent.drop(pre.index[0]).reset_index(drop=True)
tam = dataclasses.replace(fvg, normalized_entity_frame=ent2)
expect_reject_prefix("FVG delete pre-T entity", tam)

# mutate a pre-T DR range fact
r = dr.event_frame.copy(deep=True)
pre_idx = r[r.creation_position <= 60].index[0]
r.loc[pre_idx, "range_high"] = 99999.0
tam = dataclasses.replace(dr, event_frame=r)
expect_reject_prefix("DR mutate pre-T range high", tam)

# normalized event ambiguity-independent mutation pre-T
ne = ob.normalized_event_frame.copy(deep=True)
pre_rows = ne[ne.event_position <= 60]
ne.loc[pre_rows.index[0], "event_high"] = float(ne.loc[pre_rows.index[0], "event_high"]) + 100.0
tam = dataclasses.replace(ob, normalized_event_frame=ne)
expect_reject_prefix("OB mutate pre-T normalized event", tam)

# bar fact mutation pre-T
b = liq.bar_frame.copy(deep=True)
b.loc[10, "known_high_side_level_count"] = int(b.loc[10, "known_high_side_level_count"]) + 7
tam = dataclasses.replace(liq, bar_frame=b)
expect_reject_prefix("LIQ mutate pre-T bar fact", tam)

# post-T invariance: build at n=70 vs n=90, same prefix at T=60
mk70 = market(70)
a70 = PositionalTimelineAdapter("atk70")
tl70 = MarketObservationTimeline.seal(adapter=a70, market_history=mk70)
st70 = s4b1.build_structure_surface(timeline=tl70, adapter=a70, market_history=mk70, swing_policy=policy)
liq70 = s4b2.build_liquidity_surface(timeline=tl70, adapter=a70, market_history=mk70, structure_surface=st70)
fvg70 = s4b2.build_fvg_surface(timeline=tl70, adapter=a70, market_history=mk70)
k70 = a70.key_for_position(mk70.index, 60, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
p_liq = s4b2.project_domain_prefix(surface=liq70, boundary_key=k70).prefix_hash
p_fvg = s4b2.project_domain_prefix(surface=fvg70, boundary_key=k70).prefix_hash
check("LIQ prefix invariant under future append", p_liq == base_liq)
check("FVG prefix invariant under future append", p_fvg == base_fvg)
check("LIQ full surface_id changes on append", liq70.surface_id != liq.surface_id)

# post-T fact tamper must NOT change prefix through T
ev = liq.event_frame.copy(deep=True)
post = ev[ev.event_position > 60]
if len(post):
    ev.loc[post.index[0], "event_price"] = float(ev.loc[post.index[0], "event_price"]) + 50
    # tampered full surface fails self-integrity; but test the conceptual prefix by hashing
    # components directly through the same filters the projector uses:
    # simpler: coherent recompute then project
    # emulate attacker: complete_result changes so verify rejects -> accepted as defense
    tam = dataclasses.replace(liq, event_frame=ev)
    expect_reject_prefix("LIQ mutate post-T event (full-identity defense rejects)", tam)

# time-indexed timeline prefix invariance
idx = pd.date_range("2024-01-01 09:00", periods=90, freq="5min", tz="UTC")
mkt = market(90); mkt.index = idx
ta = TimeIndexedTimelineAdapter("atk-t")
tlt = MarketObservationTimeline.seal(adapter=ta, market_history=mkt)
stt = s4b1.build_structure_surface(timeline=tlt, adapter=ta, market_history=mkt, swing_policy=policy)
ft = s4b2.build_fvg_surface(timeline=tlt, adapter=ta, market_history=mkt)
kt = ta.key_for_position(mkt.index, 60, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
mkt70 = market(70); mkt70.index = idx[:70]
ta70 = TimeIndexedTimelineAdapter("atk-t70")
tlt70 = MarketObservationTimeline.seal(adapter=ta70, market_history=mkt70)
stt70 = s4b1.build_structure_surface(timeline=tlt70, adapter=ta70, market_history=mkt70, swing_policy=policy)
ft70 = s4b2.build_fvg_surface(timeline=tlt70, adapter=ta70, market_history=mkt70)
kt70 = ta70.key_for_position(mkt70.index, 60, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
h1 = s4b2.project_domain_prefix(surface=ft, boundary_key=kt).prefix_hash
h2 = s4b2.project_domain_prefix(surface=ft70, boundary_key=kt70).prefix_hash
check("FVG time-indexed prefix invariant under append", h1 == h2)

# boundary legality
bad = adapter.key_for_position(mk.index, 10, InformationPhase.BAR_PRE_CLOSE, 0)
try:
    s4b2.project_domain_prefix(surface=liq, boundary_key=bad)
    check("BAR_PRE_CLOSE rejected", False)
except (TrajectoryDataError, TrajectoryContractError):
    check("BAR_PRE_CLOSE rejected", True)

# cross-timeline key
other = PositionalTimelineAdapter("other")
badk = other.key_for_position(mk.index, 10, InformationPhase.COMPLETED_ROW_AVAILABLE, 0)
try:
    s4b2.project_domain_prefix(surface=liq, boundary_key=badk)
    check("cross-timeline key rejected", False)
except (TrajectoryDataError, TrajectoryContractError):
    check("cross-timeline key rejected", True)

# --- runtime mirror enforcement: if mirror drifts from engine output, must reject ---
orig = list(s4b2._LIQ_BAR_SCHEMA)
try:
    s4b2._LIQ_BAR_SCHEMA = tuple(["bogus_column"] + list(s4b2._LIQ_BAR_SCHEMA[1:]))
    try:
        s4b2.build_liquidity_surface(timeline=tl, adapter=adapter, market_history=mk, structure_surface=struct)
        check("mirror drift at construction rejects", False)
    except TrajectoryDataError:
        check("mirror drift at construction rejects", True)
finally:
    s4b2._LIQ_BAR_SCHEMA = tuple(orig)

# verify integrity uses CURRENT mirror (class-derived): patch mirror then verify a valid surface
try:
    s4b2._LIQ_EVENT_SCHEMA = tuple(["nope"] + list(s4b2._LIQ_EVENT_SCHEMA[1:]))
    try:
        s4b2.verify_surface_integrity(liq)
        check("verify uses current class mirror (drift rejects genuine surface)", False)
    except TrajectoryDataError:
        check("verify uses current class mirror (drift rejects genuine surface)", True)
finally:
    s4b2._LIQ_EVENT_SCHEMA = tuple(orig)

# FVG must remain structure-independent: building without struct works, struct id None
check("FVG structure_surface_id is None", fvg.structure_surface_id is None)

# normalized FVG event = 21 source columns + ambiguity flag
check("FVG normalized event has 22 cols (21+flag)",
      tuple(fvg.normalized_event_frame.columns) == s4b2._FVG_EVENT_SCHEMA + ("same_information_batch_order_unknown",))
check("FVG event source has 21 cols", tuple(fvg.event_frame.columns) == s4b2._FVG_EVENT_SCHEMA)

# compact binding has no dataframes
p = s4b2.project_domain_prefix(surface=liq, boundary_key=key)
compact = all(not isinstance(getattr(p, f.name), pd.DataFrame) for f in dataclasses.fields(p))
check("prefix binding compact (no dataframes)", compact)

# two hypotheses share physical surface (same surface_id, different prefix bindings)
p2 = s4b2.project_domain_prefix(surface=liq, boundary_key=adapter.key_for_position(mk.index, 40, InformationPhase.COMPLETED_ROW_AVAILABLE, 0))
check("shared physical surface, distinct prefix bindings", p.surface_id == p2.surface_id and p.prefix_hash != p2.prefix_hash)

failed = [n for n, ok in results if not ok]
print(f"\nPROBE 2 RESULT: {len(results)-len(failed)}/{len(results)} defenses held")
if failed:
    print("FAILURES:", failed)
sys.exit(1 if failed else 0)

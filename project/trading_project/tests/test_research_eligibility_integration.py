import numpy as np
import pandas as pd

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import CausalMarketNarrativeEngine
from trading_system.research.eligibility import (
    ELIGIBILITY_CONTRACT_VERSION,
    FactualOutcomeBatch,
    TemporalEligibilityGate,
)
from trading_system.research.information_time import (
    InformationPhase,
    PositionalTimelineAdapter,
)
from trading_system.research.outcome_observer import (
    FactualHypothesisOutcomeObserver,
    OutcomeObservationRequest,
)
from trading_system.research.visibility import (
    AsOfVisibilityProjector,
    FrozenDecisionSnapshotBundle,
)
from trading_system.structure.structural_breaks import CausalStructuralBreakEngine
from trading_system.structure.swing_sequence import ConfirmedSwingSequenceEngine


def event_surface(length, events):
    high = np.zeros(length, dtype=bool)
    low = np.zeros(length, dtype=bool)
    origins = pd.array([pd.NA] * length, dtype="Int64")
    prices = np.full(length, np.nan)
    confirmations = pd.array([pd.NA] * length, dtype="Int64")
    for row, event_type, origin, price in events:
        if event_type == "HIGH":
            high[row] = True
        else:
            low[row] = True
        origins[row] = origin
        prices[row] = price
        confirmations[row] = row
    return pd.DataFrame(
        {
            "swing_high_confirmed": high,
            "swing_low_confirmed": low,
            "swing_origin_position": origins,
            "swing_price": prices,
            "swing_confirmation_position": confirmations,
        }
    )


def real_pipeline_bundle():
    rows = [
        (101, 98, 99),
        (92, 89, 91),
        (111, 100, 105),
        (100, 94, 97),
        (112, 96, 111),
        (108, 97, 100),
        (100, 85, 96),
        (99, 86, 95),
    ]
    events = [
        (0, "HIGH", 0, 100),
        (1, "LOW", 1, 90),
        (2, "HIGH", 2, 110),
        (3, "LOW", 3, 95),
        (5, "HIGH", 5, 105),
        (6, "LOW", 6, 85),
    ]
    market = pd.DataFrame(rows, columns=["high", "low", "close"], dtype=float)
    sequence = ConfirmedSwingSequenceEngine().analyze(
        event_surface(len(market), events)
    )
    structural = CausalStructuralBreakEngine().analyze(
        pd.concat([market, sequence], axis=1)
    )
    cfg = EvidenceVectorConfig(
        environment=False,
        temporal_context=False,
        structure=True,
        liquidity=False,
        order_blocks=False,
        fvg=False,
        dealing_range=False,
        multiscale=False,
        order_flow_mode=OrderFlowEvidenceMode.NONE,
    )
    evidence, feature_manifest = CausalEvidenceVectorEngine(config=cfg).analyze(
        structural
    )
    narrative = CausalMarketNarrativeEngine().analyze(evidence, feature_manifest)
    return FrozenDecisionSnapshotBundle(
        timeline_id="real-eligibility",
        evidence_df=evidence,
        feature_manifest=feature_manifest,
        narrative_surface=narrative.narrative_surface,
        observation_ledger=narrative.observation_ledger,
        hypothesis_ledger=narrative.hypothesis_ledger,
        relationship_ledger=narrative.relationship_ledger,
        relationship_sources=narrative.relationship_sources,
        narrative_manifest=narrative.narrative_manifest,
        market_frame=market,
    )


def outcome(bundle, position, adapter):
    asof = adapter.key_for_position(
        bundle.market_frame.index,
        position,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    )
    visible = AsOfVisibilityProjector(adapter=adapter).project(bundle, asof)
    return FactualHypothesisOutcomeObserver(adapter=adapter).observe(
        visible, OutcomeObservationRequest(0)
    )


def batch(*results):
    return FactualOutcomeBatch(
        hypothesis_outcome_snapshots=pd.concat(
            [result.hypothesis_outcome_snapshots for result in results],
            ignore_index=True,
        ),
        outcome_path_segments=pd.concat(
            [result.outcome_path_segments for result in results],
            ignore_index=True,
        ),
        outcome_manifest=results[0].outcome_manifest.copy(deep=True),
    )


def test_real_pipeline_before_exact_and_later_cutoffs():
    bundle = real_pipeline_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    gate = TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    )
    b1 = outcome(bundle, 5, adapter)
    b2 = outcome(bundle, 6, adapter)
    b3 = outcome(bundle, 7, adapter)

    before_cutoff = adapter.key_for_position(
        bundle.market_frame.index,
        5,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    )
    before = gate.evaluate(batch(b1), before_cutoff)
    assert before.temporal_eligibility_audit.iloc[0].eligibility_reason == (
        "OUTCOME_IMMATURE"
    )
    assert before.selected_mature_samples.empty

    exact_terminal_cutoff = adapter.key_for_position(
        bundle.market_frame.index,
        6,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    exact = gate.evaluate(batch(b2), exact_terminal_cutoff)
    assert exact.temporal_eligibility_audit.iloc[0].temporally_eligible
    assert len(exact.selected_mature_samples) == 1
    assert exact.selected_mature_samples.iloc[0].narrative_terminal_state == (
        "CONTRADICTED"
    )

    later_cutoff = adapter.key_for_position(
        bundle.market_frame.index,
        7,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    )
    later = gate.evaluate(batch(b1, b3, b2), later_cutoff)
    assert later.temporal_eligibility_audit["eligibility_reason"].tolist() == [
        "OUTCOME_IMMATURE",
        "ELIGIBLE",
        "ELIGIBLE",
    ]
    assert len(later.selected_mature_samples) == 1
    assert later.selected_mature_samples.iloc[0].selected_research_snapshot_id == (
        b2.hypothesis_outcome_snapshots.iloc[0].research_snapshot_id
    )

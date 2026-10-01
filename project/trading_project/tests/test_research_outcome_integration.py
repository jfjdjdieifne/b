import numpy as np
import pandas as pd

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import CausalMarketNarrativeEngine
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


def real_bundle(rows, events, timeline_id):
    market = pd.DataFrame(rows, columns=["high", "low", "close"], dtype=float)
    sequence = ConfirmedSwingSequenceEngine().analyze(
        event_surface(len(market), events)
    )
    structural_input = pd.concat([market, sequence], axis=1)
    structural = CausalStructuralBreakEngine().analyze(structural_input)
    config = EvidenceVectorConfig(
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
    evidence, feature_manifest = CausalEvidenceVectorEngine(config=config).analyze(
        structural
    )
    narrative = CausalMarketNarrativeEngine().analyze(evidence, feature_manifest)
    return FrozenDecisionSnapshotBundle(
        timeline_id=timeline_id,
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


def observe(bundle, asof_position):
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    asof = adapter.key_for_position(
        bundle.market_frame.index,
        asof_position,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    )
    visible = AsOfVisibilityProjector(adapter=adapter).project(bundle, asof)
    return FactualHypothesisOutcomeObserver(adapter=adapter).observe(
        visible, OutcomeObservationRequest(0)
    )


def test_real_2_1b_to_6_2a_1_continuation_censor_and_maturity():
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
    bundle = real_bundle(rows, events, "real-continuation")
    before = observe(bundle, 5)
    after = observe(bundle, 6)
    b = before.hypothesis_outcome_snapshots.iloc[0]
    a = after.hypothesis_outcome_snapshots.iloc[0]
    assert b.hypothesis_type == "UPWARD_CONTINUATION_AFTER_PROJECT_BREAK"
    assert b.snapshot_position == 4
    assert b.reference_price == 111.0
    assert not b.outcome_mature
    assert b.right_censored_as_of
    assert a.outcome_mature
    assert a.narrative_terminal_state == "CONTRADICTED"
    assert a.terminal_position == 6
    assert after.outcome_path_segments["segment_type"].tolist() == [
        "PRE_ENDPOINT",
        "ENDPOINT_BAR",
    ]


def test_real_2_1b_to_6_2a_1_transition_censor_and_maturity():
    rows = [
        (101, 98, 99),
        (92, 89, 91),
        (96, 90, 93),
        (90, 79, 82),
        (97, 85, 96),
        (106, 86, 100),
        (103, 84, 90),
        (104, 86, 95),
    ]
    events = [
        (0, "HIGH", 0, 100),
        (1, "LOW", 1, 90),
        (2, "HIGH", 2, 95),
        (3, "LOW", 3, 80),
        (5, "HIGH", 5, 105),
        (6, "LOW", 6, 85),
    ]
    bundle = real_bundle(rows, events, "real-transition")
    before = observe(bundle, 5)
    after = observe(bundle, 6)
    b = before.hypothesis_outcome_snapshots.iloc[0]
    a = after.hypothesis_outcome_snapshots.iloc[0]
    assert b.hypothesis_type == "UPWARD_TRANSITION_AFTER_PROJECT_SHIFT"
    assert b.snapshot_position == 4
    assert b.reference_price == 96.0
    assert not b.outcome_mature
    assert a.outcome_mature
    assert a.narrative_terminal_state == "OBSERVED_DIRECTION_ESTABLISHED"
    assert a.terminal_position == 6
    assert after.outcome_path_segments["segment_type"].tolist() == [
        "PRE_ENDPOINT",
        "ENDPOINT_BAR",
    ]

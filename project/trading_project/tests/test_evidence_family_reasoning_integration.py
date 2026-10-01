import numpy as np
import pandas as pd

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import CausalMarketNarrativeEngine
from trading_system.reasoning.evidence_families import (
    DynamicEvidenceFamilyReasoner,
    EvidenceFamily,
    ReasoningDecisionSnapshot,
)
from trading_system.research.dataset_contracts import freeze_creation_feature_snapshot
from trading_system.research.information_time import (
    InformationPhase,
    PositionalTimelineAdapter,
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


def test_real_closed_pipeline_to_evidence_family_reasoning():
    market = pd.DataFrame(
        [
            (101, 98, 99),
            (92, 89, 91),
            (111, 100, 105),
            (100, 94, 97),
            (112, 96, 111),
            (108, 97, 100),
        ],
        columns=["high", "low", "close"],
        dtype=float,
    )
    events = [
        (0, "HIGH", 0, 100),
        (1, "LOW", 1, 90),
        (2, "HIGH", 2, 110),
        (3, "LOW", 3, 95),
        (5, "HIGH", 5, 105),
    ]
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
    bundle = FrozenDecisionSnapshotBundle(
        timeline_id="real-reasoning",
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
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    asof = adapter.key_for_position(
        market.index, 4, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE
    )
    visible = AsOfVisibilityProjector(adapter=adapter).project(bundle, asof)
    frozen = freeze_creation_feature_snapshot(
        visible, hypothesis_id=0, adapter=adapter
    )
    snapshot = ReasoningDecisionSnapshot(
        timeline_id=frozen.timeline_id,
        decision_information_key=frozen.snapshot_information_key,
        hypothesis_id=frozen.hypothesis_id,
        evidence_row=frozen.evidence_row,
        feature_manifest=frozen.feature_manifest,
        narrative_surface_row=frozen.narrative_row,
        observation_rows=frozen.same_row_observations,
        hypothesis_rows=frozen.created_ledger_event,
        relationship_rows=frozen.same_row_relationships,
        relationship_sources=frozen.relationship_sources,
        narrative_manifest=frozen.narrative_manifest,
        reference_price=frozen.reference_price,
        reference_information_key=frozen.reference_information_key,
        reference_index_label=frozen.reference_index_label,
        decision_input_slice_hash=frozen.decision_input_slice_hash,
        decision_snapshot_hash=frozen.decision_snapshot_hash,
    )
    result = DynamicEvidenceFamilyReasoner().analyze(snapshot)
    structural_family = result.family_snapshots[
        result.family_snapshots["family_name"]
        == EvidenceFamily.STRUCTURAL_HYPOTHESIS.value
    ].iloc[0]
    assert structural_family.aggregate_semantic_state == "CONTEXTUAL"
    assert structural_family.hypothesis_type == (
        "UPWARD_CONTINUATION_AFTER_PROJECT_BREAK"
    )
    assert "SUPPORT" not in result.evidence_records["semantic_state"].tolist()

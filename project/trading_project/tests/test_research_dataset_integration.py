import numpy as np
import pandas as pd

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import CausalMarketNarrativeEngine
from trading_system.research.dataset_builder import CausalResearchDatasetBuilder
from trading_system.research.dataset_contracts import (
    WalkForwardFoldSpec,
    freeze_creation_feature_snapshot,
)
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


def real_bundle():
    market = pd.DataFrame(
        [
            (101, 98, 99),
            (92, 89, 91),
            (111, 100, 105),
            (100, 94, 97),
            (112, 96, 111),
            (108, 97, 100),
            (100, 85, 96),
            (99, 86, 95),
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
        (6, "LOW", 6, 85),
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
    return FrozenDecisionSnapshotBundle(
        timeline_id="real-dataset",
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


def key(adapter, index, position, phase=InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, sequence=0):
    return adapter.key_for_position(index, position, phase, sequence)


def visible(bundle, position, adapter):
    return AsOfVisibilityProjector(adapter=adapter).project(
        bundle, key(adapter, bundle.market_frame.index, position)
    )


def outcome(bundle, position, adapter):
    return FactualHypothesisOutcomeObserver(adapter=adapter).observe(
        visible(bundle, position, adapter), OutcomeObservationRequest(0)
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


def test_real_pipeline_two_walk_forward_folds():
    bundle = real_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    b1 = outcome(bundle, 5, adapter)
    b2 = outcome(bundle, 6, adapter)
    b3 = outcome(bundle, 7, adapter)
    factual = batch(b1, b2, b3)
    eligibility_gate = TemporalEligibilityGate(
        adapter=adapter, contract_version=ELIGIBILITY_CONTRACT_VERSION
    )
    full_visible = visible(bundle, 7, adapter)
    feature_snapshot = freeze_creation_feature_snapshot(
        full_visible, hypothesis_id=0, adapter=adapter
    )
    builder = CausalResearchDatasetBuilder(adapter=adapter)

    fold1_spec = WalkForwardFoldSpec(
        fold_id="real-fold-1",
        timeline_id=bundle.timeline_id,
        train_cutoff=key(adapter, bundle.market_frame.index, 3),
        test_creation_end_inclusive=key(adapter, bundle.market_frame.index, 5),
        test_label_as_of=key(adapter, bundle.market_frame.index, 6),
    )
    fold1 = builder.build(
        fold_spec=fold1_spec,
        feature_snapshots=[feature_snapshot],
        factual_outcomes=factual,
        train_eligibility=eligibility_gate.evaluate(
            factual, fold1_spec.train_cutoff
        ),
        test_evaluation_eligibility=eligibility_gate.evaluate(
            factual, fold1_spec.test_label_as_of
        ),
    )
    assert fold1.fold.train_features_raw.empty
    assert len(fold1.fold.test_features_raw) == 1
    assert fold1.fold.test_targets.iloc[0].target_terminal_state == "CONTRADICTED"
    fold1_hash = fold1.fold.fold_manifest.iloc[0].dataset_fold_hash

    fold2_spec = WalkForwardFoldSpec(
        fold_id="real-fold-2",
        timeline_id=bundle.timeline_id,
        train_cutoff=key(
            adapter,
            bundle.market_frame.index,
            6,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            1,
        ),
        test_creation_end_inclusive=key(adapter, bundle.market_frame.index, 7),
    )
    fold2 = builder.build(
        fold_spec=fold2_spec,
        feature_snapshots=[feature_snapshot],
        factual_outcomes=factual,
        train_eligibility=eligibility_gate.evaluate(
            factual, fold2_spec.train_cutoff
        ),
        test_evaluation_eligibility=None,
    )
    assert len(fold2.fold.train_features_raw) == 1
    assert fold2.fold.train_targets.iloc[0].target_terminal_state == "CONTRADICTED"
    assert fold2.fold.test_features_raw.empty
    assert fold1.fold.fold_manifest.iloc[0].dataset_fold_hash == fold1_hash

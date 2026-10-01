from dataclasses import fields, replace

import numpy as np
import pandas as pd
import pytest

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    GROUPS,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import CausalMarketNarrativeEngine
from trading_system.reasoning.evidence_families import (
    AvailabilityState,
    DynamicEvidenceFamilyReasoner,
    EvidenceFamily,
    EvidenceFamilyReasoningResult,
    ReasoningContractError,
    ReasoningDecisionSnapshot,
    SemanticState,
    reasoning_contract_manifest,
    reasoning_record_hash_payload,
)
from trading_system.research.dataset_contracts import freeze_creation_feature_snapshot
from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import (
    InformationKey,
    InformationPhase,
    PositionalTimelineAdapter,
)
from trading_system.research.visibility import (
    AsOfVisibilityProjector,
    FrozenDecisionSnapshotBundle,
)


def config(**overrides):
    values = dict(
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
    values.update(overrides)
    return EvidenceVectorConfig(**values)


def selected_specs(cfg):
    specs = []
    for name in (
        "environment",
        "temporal_context",
        "structure",
        "liquidity",
        "order_blocks",
        "fvg",
        "dealing_range",
        "multiscale",
    ):
        if getattr(cfg, name):
            specs.extend(GROUPS[name])
    if cfg.order_flow_mode is OrderFlowEvidenceMode.ACTUAL:
        specs.extend(GROUPS["actual"])
    elif cfg.order_flow_mode is OrderFlowEvidenceMode.PROXY:
        specs.extend(GROUPS["proxy"])
    return specs


def value_for_spec(spec, n):
    domain = spec.expected_domain
    if domain == "count":
        return pd.Series([0] * n, dtype="int64")
    if domain == "bool":
        return pd.Series([False] * n, dtype="bool")
    if domain == "structure_state":
        return pd.Series(["UP_STRUCTURE"] * n, dtype="string")
    if domain == "break_event":
        values = ["NONE"] * n
        values[1] = "BOS_UP"
        return pd.Series(values, dtype="string")
    if domain == "category_side":
        return pd.Series(["NONE"] * n, dtype="string")
    if domain == "category_pressure":
        return pd.Series(["NONE"] * n, dtype="string")
    if domain in {"percentile", "unit_interval"}:
        return pd.Series([0.5] * n, dtype="float64")
    if domain == "signed_unit":
        return pd.Series([0.0] * n, dtype="float64")
    if domain == "nonnegative_or_nan":
        return pd.Series([0.5] * n, dtype="float64")
    return pd.Series([0.0] * n, dtype="float64")


def frozen_snapshot(
    cfg=None,
    *,
    delta_ratio=None,
    delta_nan=False,
    pressure=None,
    mtf_balance=None,
    ob_touch=False,
    future_variant=0,
):
    if cfg is None:
        cfg = config()
    n = 5
    market = pd.DataFrame(
        {
            "high": [101.0, 103.0, 104.0, 105.0, 106.0],
            "low": [98.0, 99.0, 100.0, 101.0, 102.0],
            "close": [99.0, 102.0, 103.0, 104.0, 105.0],
        }
    )
    if future_variant:
        market.loc[2:, ["high", "low", "close"]] = [
            [150.0, 80.0, 120.0],
            [160.0, 70.0, 130.0],
            [170.0, 60.0, 140.0],
        ]
    source = market.copy(deep=True)
    for spec in selected_specs(cfg):
        if spec.source_column not in source:
            source[spec.source_column] = value_for_spec(spec, n)
    if "structure_state_after" in source:
        source["structure_state_after"] = pd.Series(
            ["UP_STRUCTURE"] * n, dtype="string"
        )
        break_events = ["NONE"] * n
        break_events[1] = "BOS_UP"
        source["structural_break_event"] = pd.Series(break_events, dtype="string")
    if delta_ratio is not None:
        values = [0.0] * n
        values[1:] = [float(delta_ratio)] * (n - 1)
        source["delta_ratio"] = pd.Series(values, dtype="float64")
    if delta_nan:
        values = [0.0] + [np.nan] * (n - 1)
        source["delta_ratio"] = pd.Series(values, dtype="float64")
    if pressure is not None:
        values = [0.0] * n
        values[1:] = [float(pressure)] * (n - 1)
        source["volume_pressure_proxy"] = pd.Series(values, dtype="float64")
    if mtf_balance is not None:
        values = [0.0] * n
        values[1:] = [float(mtf_balance)] * (n - 1)
        source["directional_balance"] = pd.Series(values, dtype="float64")
        source["directional_consensus"] = abs(source["directional_balance"])
        source["directional_scale_count"] = pd.Series([2] * n, dtype="int64")
        source["available_scale_count"] = pd.Series([2] * n, dtype="int64")
        source["unavailable_scale_count"] = pd.Series([0] * n, dtype="int64")
        source["availability_fraction"] = 1.0
        source["directional_fraction"] = 1.0
    if ob_touch:
        values = [0] * n
        values[1] = 1
        source["bullish_ob_first_touch_count"] = pd.Series(values, dtype="int64")
    evidence, feature_manifest = CausalEvidenceVectorEngine(config=cfg).analyze(source)
    narrative = CausalMarketNarrativeEngine().analyze(evidence, feature_manifest)
    bundle = FrozenDecisionSnapshotBundle(
        timeline_id="reasoning",
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
        market.index, 1, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE
    )
    visible = AsOfVisibilityProjector(adapter=adapter).project(bundle, asof)
    return freeze_creation_feature_snapshot(visible, hypothesis_id=0, adapter=adapter)


def reasoning_snapshot(frozen):
    return ReasoningDecisionSnapshot(
        timeline_id=frozen.timeline_id,
        decision_information_key=frozen.snapshot_information_key,
        hypothesis_id=frozen.hypothesis_id,
        evidence_row=frozen.evidence_row.copy(deep=True),
        feature_manifest=frozen.feature_manifest.copy(deep=True),
        narrative_surface_row=frozen.narrative_row.copy(deep=True),
        observation_rows=frozen.same_row_observations.copy(deep=True),
        hypothesis_rows=frozen.created_ledger_event.copy(deep=True),
        relationship_rows=frozen.same_row_relationships.copy(deep=True),
        relationship_sources=frozen.relationship_sources.copy(deep=True),
        narrative_manifest=frozen.narrative_manifest.copy(deep=True),
        reference_price=frozen.reference_price,
        reference_information_key=frozen.reference_information_key,
        reference_index_label=frozen.reference_index_label,
        decision_input_slice_hash=frozen.decision_input_slice_hash,
        decision_snapshot_hash=frozen.decision_snapshot_hash,
    )


def rehash_reasoning_snapshot(snapshot):
    feature_manifest_hash = canonical_sha256(
        domain="FEATURE_MANIFEST_V1", payload=snapshot.feature_manifest
    )
    narrative_manifest_hash = canonical_sha256(
        domain="NARRATIVE_MANIFEST_V1", payload=snapshot.narrative_manifest
    )
    reference_identity = {
        "timeline_id": snapshot.timeline_id,
        "created_position": snapshot.decision_information_key.bar_position,
        "index_label": snapshot.reference_index_label,
        "reference_price": snapshot.reference_price,
        "reference_price_source": "CREATION_ROW_COMPLETED_CLOSE_RESEARCH_REFERENCE_MARK",
        "reference_is_execution_price": False,
        "reference_key": snapshot.reference_information_key,
    }
    input_hash = canonical_sha256(
        domain="DECISION_INPUT_SLICE_V1_2", payload=reference_identity
    )
    snapshot_hash = canonical_sha256(
        domain="HYPOTHESIS_CREATION_DECISION_SNAPSHOT_V1_2",
        payload={
            "timeline_id": snapshot.timeline_id,
            "hypothesis_id": snapshot.hypothesis_id,
            "snapshot_type": "HYPOTHESIS_CREATION_SNAPSHOT",
            "creation_key": snapshot.decision_information_key,
            "evidence_row": snapshot.evidence_row,
            "narrative_row": snapshot.narrative_surface_row,
            "created_ledger_event": snapshot.hypothesis_rows,
            "same_row_observations": snapshot.observation_rows,
            "same_hypothesis_same_row_relationships": snapshot.relationship_rows,
            "same_row_relationship_sources": snapshot.relationship_sources,
            "feature_manifest_hash": feature_manifest_hash,
            "narrative_manifest_hash": narrative_manifest_hash,
            "reference_identity": reference_identity,
            "decision_input_slice_hash": input_hash,
        },
    )
    return replace(
        snapshot,
        decision_input_slice_hash=input_hash,
        decision_snapshot_hash=snapshot_hash,
    )


def analyze(frozen):
    return DynamicEvidenceFamilyReasoner().analyze(reasoning_snapshot(frozen))


def assert_results_equal(left, right):
    for field in fields(EvidenceFamilyReasoningResult):
        pd.testing.assert_frame_equal(
            getattr(left, field.name), getattr(right, field.name), check_exact=True
        )


def assert_semantic_equal(left, right):
    """Compare semantics while intentionally excluding exact storage provenance.

    decision_snapshot_hash binds upstream DataFrame storage order.  snapshot_hash
    is separately asserted by V1.2 adversarial tests as canonical family content.
    """
    pd.testing.assert_frame_equal(
        left.family_snapshots.drop(columns=["decision_snapshot_hash"]),
        right.family_snapshots.drop(columns=["decision_snapshot_hash"]),
        check_exact=True,
    )
    for name in (
        "evidence_records", "evidence_sources", "lineage_edges",
        "availability_signature", "reasoning_ledger", "provenance_relations",
        "reasoning_manifest",
    ):
        pd.testing.assert_frame_equal(getattr(left, name), getattr(right, name), check_exact=True)


def family_row(result, family):
    return result.family_snapshots[
        result.family_snapshots["family_name"] == family.value
    ].iloc[0]


def test_output_schemas_all_families_and_static_manifest():
    result = analyze(frozen_snapshot())
    assert result.family_snapshots["family_name"].tolist() == [
        family.value for family in EvidenceFamily
    ]
    assert len(result.availability_signature) == len(EvidenceFamily)
    assert result.reasoning_manifest.equals(reasoning_contract_manifest())
    names = {field.name for field in fields(EvidenceFamilyReasoningResult)}
    assert names == {
        "family_snapshots", "evidence_records", "evidence_sources",
        "lineage_edges", "availability_signature", "reasoning_ledger",
        "provenance_relations", "reasoning_manifest",
    }


def test_aligned_relationship_is_not_upgraded_to_support():
    result = analyze(frozen_snapshot())
    local = result.evidence_records[
        result.evidence_records["family_name"] == EvidenceFamily.LOCAL_STRUCTURE_STATE.value
    ]
    assert "ALIGNED" in local["semantic_state"].tolist()
    assert "SUPPORT" not in local["semantic_state"].tolist()


def test_directional_opposition_is_affirmative_opposition_not_contradiction():
    result = analyze(
        frozen_snapshot(
            config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL),
            delta_ratio=-0.5,
        )
    )
    row = family_row(result, EvidenceFamily.ACTUAL_FLOW_DIRECTION)
    assert row.aggregate_semantic_state == "OPPOSITION"
    assert not row.contradiction_present


def test_ob_existence_and_interaction_remain_factual_not_support():
    result = analyze(frozen_snapshot(config(order_blocks=True), ob_touch=True))
    records = result.evidence_records[
        result.evidence_records["family_name"] == EvidenceFamily.OB_GEOMETRY.value
    ]
    assert "FACTUAL" in records["semantic_state"].tolist()
    assert "SUPPORT" not in records["semantic_state"].tolist()


def test_absence_of_support_is_not_opposition():
    result = analyze(frozen_snapshot())
    ob = family_row(result, EvidenceFamily.OB_GEOMETRY)
    assert ob.aggregate_semantic_state == "UNAVAILABLE"
    assert ob.availability_state == "UNAVAILABLE"
    assert not ob.contradiction_present


def test_unknown_value_remains_unknown_not_neutral_or_zero():
    frozen = frozen_snapshot(
        config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL), delta_nan=True
    )
    result = DynamicEvidenceFamilyReasoner().analyze(reasoning_snapshot(frozen))
    delta = result.evidence_records[
        result.evidence_records["source_record_id"] == "delta_ratio"
    ].iloc[0]
    assert delta.semantic_state == "UNKNOWN"
    assert delta.availability_state == "UNKNOWN"
    assert pd.isna(delta.primary_value_float)


def test_actual_and_proxy_provenance_remain_separate():
    actual = analyze(
        frozen_snapshot(
            config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL), delta_ratio=0.5
        )
    )
    proxy = analyze(
        frozen_snapshot(
            config(order_flow_mode=OrderFlowEvidenceMode.PROXY), pressure=0.5
        )
    )
    actual_modes = set(
        actual.evidence_sources.loc[
            actual.evidence_sources["source_feature_name"] == "delta_ratio",
            "source_mode",
        ]
    )
    proxy_modes = set(
        proxy.evidence_sources.loc[
            proxy.evidence_sources["source_feature_name"] == "volume_pressure_proxy",
            "source_mode",
        ]
    )
    assert actual_modes == {"ACTUAL"}
    assert proxy_modes == {"PROXY"}


def test_missing_actual_is_not_filled_by_proxy():
    proxy = analyze(
        frozen_snapshot(
            config(order_flow_mode=OrderFlowEvidenceMode.PROXY), pressure=0.5
        )
    )
    assert family_row(proxy, EvidenceFamily.ACTUAL_FLOW_DIRECTION).availability_state == (
        "UNAVAILABLE"
    )
    assert family_row(proxy, EvidenceFamily.PROXY_PRESSURE_DIRECTION).availability_state == (
        "AVAILABLE"
    )


def test_support_count_derivative_is_grouped_not_independent():
    result = analyze(
        frozen_snapshot(
            config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL), delta_ratio=0.5
        )
    )
    records = result.evidence_records[
        result.evidence_records["source_record_id"].isin(
            ["delta_ratio_percentile", "delta_ratio_history_count"]
        )
    ]
    assert len(set(records["independence_cluster_id"])) == 1
    assert records["included_for_independent_calibration"].sum() <= 1
    assert "SUPPORT_COUNT_FOR" in result.lineage_edges["edge_type"].tolist()


def test_mtf_correlated_descriptors_share_provenance_cluster():
    result = analyze(frozen_snapshot(config(multiscale=True), mtf_balance=0.5))
    relationship = result.evidence_records[
        (result.evidence_records["family_name"] == EvidenceFamily.MULTISCALE_STRUCTURE.value)
        & (result.evidence_records["record_kind"] == "RELATIONSHIP")
    ]
    assert len(relationship) == 1
    linked = result.evidence_sources[
        result.evidence_sources["record_id"] == relationship.iloc[0].record_id
    ]
    assert set(linked["source_feature_name"]) == {
        "directional_balance", "directional_consensus", "directional_scale_count",
        "availability_fraction", "directional_conflict",
    }


def test_duplicate_relationship_source_is_rejected_not_counted():
    frozen = frozen_snapshot()
    snapshot = reasoning_snapshot(frozen)
    sources = pd.concat(
        [snapshot.relationship_sources, snapshot.relationship_sources.iloc[[0]]],
        ignore_index=True,
    )
    with pytest.raises(ReasoningContractError, match="duplicate relationship source"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, relationship_sources=sources)
        )


def test_contradiction_not_counted_again_as_soft_opposition():
    frozen = frozen_snapshot()
    snapshot = reasoning_snapshot(frozen)
    relationships = snapshot.relationship_rows.copy(deep=True)
    local = relationships["evidence_family"] == "LOCAL_STRUCTURE_STATE"
    relationships.loc[local, "relationship_bearing"] = "CONTRADICTS"
    base_row = relationships[local].iloc[0].copy()
    base_row["relationship_id"] = int(relationships["relationship_id"].max()) + 1
    base_row["relationship_bearing"] = "DIRECTIONALLY_OPPOSES"
    base_row["serialization_order"] = int(base_row["serialization_order"]) + 100
    relationships = pd.concat([relationships, base_row.to_frame().T], ignore_index=True)
    for column in (
        "relationship_id", "hypothesis_id", "observed_position", "same_row_batch_id",
        "support_count", "serialization_order",
    ):
        relationships[column] = pd.array(relationships[column], dtype="Int64")
    source_rows = snapshot.relationship_sources[
        snapshot.relationship_sources["relationship_id"]
        == int(snapshot.relationship_rows[local].iloc[0].relationship_id)
    ].copy(deep=True)
    source_rows["relationship_id"] = int(base_row["relationship_id"])
    all_sources = pd.concat([snapshot.relationship_sources, source_rows], ignore_index=True)
    altered = rehash_reasoning_snapshot(
        replace(snapshot, relationship_rows=relationships, relationship_sources=all_sources)
    )
    result = DynamicEvidenceFamilyReasoner().analyze(altered)
    local_family = family_row(result, EvidenceFamily.LOCAL_STRUCTURE_STATE)
    assert local_family.aggregate_semantic_state == "CONTRADICTION"
    opposition = result.evidence_records[
        (result.evidence_records["family_name"] == EvidenceFamily.LOCAL_STRUCTURE_STATE.value)
        & (result.evidence_records["semantic_state"] == "OPPOSITION")
    ]
    assert not opposition["included_for_independent_calibration"].any()


def test_relationship_and_feature_shared_source_do_not_become_two_votes():
    result = analyze(frozen_snapshot())
    local = result.evidence_records[
        result.evidence_records["family_name"] == EvidenceFamily.LOCAL_STRUCTURE_STATE.value
    ]
    assert len(set(local["independence_cluster_id"])) == 1
    assert local["selected_provenance_representative"].sum() == 1
    assert local["included_for_independent_calibration"].sum() == 0


def test_unavailable_families_have_explicit_ledger_events():
    result = analyze(frozen_snapshot())
    unavailable = set(
        result.family_snapshots.loc[
            result.family_snapshots["availability_state"] == "UNAVAILABLE",
            "family_name",
        ]
    )
    ledger_unavailable = set(
        result.reasoning_ledger.loc[
            result.reasoning_ledger["action"] == "FAMILY_UNAVAILABLE",
            "family_name",
        ]
    )
    assert unavailable == ledger_unavailable


def test_availability_signature_is_deterministic_and_complete():
    first = analyze(frozen_snapshot())
    second = analyze(frozen_snapshot())
    assert first.availability_signature["global_availability_signature_hash"].nunique() == 1
    pd.testing.assert_frame_equal(
        first.availability_signature, second.availability_signature, check_exact=True
    )


def test_relationship_and_source_reordering_preserves_canonical_semantic_identity():
    frozen = frozen_snapshot(config(multiscale=True), mtf_balance=0.5)
    base = reasoning_snapshot(frozen)
    reordered = replace(
        base,
        relationship_rows=base.relationship_rows.iloc[::-1].reset_index(drop=True),
        relationship_sources=base.relationship_sources.iloc[::-1].reset_index(drop=True),
        observation_rows=base.observation_rows.iloc[::-1].reset_index(drop=True),
    )
    reordered = rehash_reasoning_snapshot(reordered)
    assert_semantic_equal(
        DynamicEvidenceFamilyReasoner().analyze(base),
        DynamicEvidenceFamilyReasoner().analyze(reordered),
    )


def test_serialization_order_does_not_create_market_chronology():
    frozen = frozen_snapshot()
    snapshot = reasoning_snapshot(frozen)
    relationships = snapshot.relationship_rows.copy(deep=True)
    relationships["serialization_order"] = pd.array(
        list(range(100, 100 + len(relationships))), dtype="Int64"
    )
    altered = rehash_reasoning_snapshot(
        replace(snapshot, relationship_rows=relationships)
    )
    result = DynamicEvidenceFamilyReasoner().analyze(altered)
    expected = DynamicEvidenceFamilyReasoner().analyze(snapshot)
    assert_semantic_equal(result, expected)


def test_future_position_payload_rejected_before_semantic_use():
    frozen = frozen_snapshot()
    snapshot = reasoning_snapshot(frozen)
    observations = snapshot.observation_rows.copy(deep=True)
    future = observations.iloc[[0]].copy(deep=True)
    future["observation_id"] = int(observations["observation_id"].max()) + 1
    future["observed_position"] = snapshot.decision_information_key.bar_position + 1
    observations = pd.concat([observations, future], ignore_index=True)
    observations["observation_id"] = pd.array(observations["observation_id"], dtype="Int64")
    observations["observed_position"] = pd.array(observations["observed_position"], dtype="Int64")
    with pytest.raises(ReasoningContractError, match="future record"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, observation_rows=observations)
        )


def test_invalid_key_timeline_phase_and_cross_timeline_rejected():
    frozen = frozen_snapshot()
    snapshot = reasoning_snapshot(frozen)
    wrong_timeline = InformationKey(
        information_key_version=snapshot.decision_information_key.information_key_version,
        timeline_id="other",
        bar_position=snapshot.decision_information_key.bar_position,
        event_time_utc=None,
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=1,
    )
    with pytest.raises(ReasoningContractError, match="InformationKey mismatch"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, decision_information_key=wrong_timeline)
        )
    wrong_phase = replace(
        snapshot,
        decision_information_key=InformationKey(
            information_key_version=snapshot.decision_information_key.information_key_version,
            timeline_id=snapshot.timeline_id,
            bar_position=snapshot.decision_information_key.bar_position,
            event_time_utc=None,
            information_phase=InformationPhase.BAR_PRE_CLOSE,
            deterministic_sequence=1,
        ),
    )
    with pytest.raises(ReasoningContractError, match="completed atomic"):
        DynamicEvidenceFamilyReasoner().analyze(wrong_phase)


def test_nonfinite_evidence_value_rejected():
    frozen = frozen_snapshot(config(environment=True))
    snapshot = reasoning_snapshot(frozen)
    evidence = snapshot.evidence_row.copy(deep=True)
    evidence.loc[evidence.index[0], "ev__normalized_tr_change"] = np.inf
    with pytest.raises(ReasoningContractError, match="nonfinite"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, evidence_row=evidence)
        )


def test_input_immutable_a_a_a_b_a_and_fresh_instance():
    frozen_a = frozen_snapshot()
    frozen_b = frozen_snapshot(config(multiscale=True), mtf_balance=-0.5)
    snapshot_a = reasoning_snapshot(frozen_a)
    before = snapshot_a.evidence_row.copy(deep=True)
    reasoner = DynamicEvidenceFamilyReasoner()
    first = reasoner.analyze(snapshot_a)
    repeated = reasoner.analyze(snapshot_a)
    reasoner.analyze(reasoning_snapshot(frozen_b))
    after = reasoner.analyze(snapshot_a)
    fresh = DynamicEvidenceFamilyReasoner().analyze(snapshot_a)
    for result in (repeated, after, fresh):
        assert_results_equal(first, result)
    pd.testing.assert_frame_equal(snapshot_a.evidence_row, before, check_exact=True)


def test_prefix_invariance_from_different_future_histories():
    first = analyze(frozen_snapshot(future_variant=0))
    second = analyze(frozen_snapshot(future_variant=1))
    assert_results_equal(first, second)


def test_no_score_weight_threshold_geometry_or_trade_outputs():
    result = analyze(frozen_snapshot())
    columns = " ".join(
        column
        for field in fields(EvidenceFamilyReasoningResult)
        for column in getattr(result, field.name).columns
    ).lower()
    forbidden = (
        "score", "weight", "threshold", "probability", "entry", "stop",
        "target", "signal", "pnl", "profit", "win", "loss",
    )
    assert not any(token in columns for token in forbidden)
    manifest_text = " ".join(result.reasoning_manifest.astype(str).to_numpy().ravel()).lower()
    assert "not_implemented" in manifest_text


def test_decision_snapshot_attestation_rejects_feature_tampering():
    snapshot = reasoning_snapshot(frozen_snapshot())
    evidence = snapshot.evidence_row.copy(deep=True)
    evidence.iloc[0, 0] = "DOWN_STRUCTURE"
    with pytest.raises(ReasoningContractError, match="mismatch"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, evidence_row=evidence)
        )


def test_missing_duplicate_and_empty_decision_rows_rejected():
    snapshot = reasoning_snapshot(frozen_snapshot())
    missing = snapshot.evidence_row.drop(columns=[snapshot.evidence_row.columns[0]])
    with pytest.raises(ReasoningContractError):
        DynamicEvidenceFamilyReasoner().analyze(replace(snapshot, evidence_row=missing))
    duplicate = pd.concat(
        [snapshot.evidence_row, snapshot.evidence_row.iloc[:, [0]]], axis=1
    )
    with pytest.raises(ReasoningContractError):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, evidence_row=duplicate)
        )
    with pytest.raises(ReasoningContractError, match="singular"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, evidence_row=snapshot.evidence_row.iloc[0:0])
        )


def test_malformed_hypothesis_id_and_manifest_rejected_cleanly():
    snapshot = reasoning_snapshot(frozen_snapshot())
    with pytest.raises(ReasoningContractError, match="hypothesis_id"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, hypothesis_id=True)
        )
    manifest = snapshot.feature_manifest.iloc[:-1].copy(deep=True)
    with pytest.raises(ReasoningContractError, match="manifest"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, feature_manifest=manifest)
        )


def test_neutral_unknown_and_unavailable_remain_distinct():
    neutral = analyze(frozen_snapshot(config(multiscale=True), mtf_balance=0.0))
    mtf = family_row(neutral, EvidenceFamily.MULTISCALE_STRUCTURE)
    unavailable = family_row(neutral, EvidenceFamily.OB_GEOMETRY)
    assert mtf.aggregate_semantic_state == "NEUTRAL"
    assert mtf.availability_state == "AVAILABLE"
    assert unavailable.aggregate_semantic_state == "UNAVAILABLE"
    unknown = analyze(
        frozen_snapshot(
            config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL), delta_nan=True
        )
    )
    assert "UNKNOWN" in unknown.evidence_records["semantic_state"].tolist()


def test_local_and_mtf_disagreement_preserved_without_hard_priority():
    result = analyze(frozen_snapshot(config(multiscale=True), mtf_balance=-0.5))
    local = family_row(result, EvidenceFamily.LOCAL_STRUCTURE_STATE)
    mtf = family_row(result, EvidenceFamily.MULTISCALE_STRUCTURE)
    assert local.aggregate_semantic_state == "ALIGNED"
    assert mtf.aggregate_semantic_state == "OPPOSITION"
    assert not local.contradiction_present
    assert not mtf.contradiction_present


def test_current_closed_sources_emit_no_direct_predictive_support():
    result = analyze(
        frozen_snapshot(
            config(
                environment=True,
                temporal_context=True,
                liquidity=True,
                order_blocks=True,
                fvg=True,
                dealing_range=True,
                multiscale=True,
                order_flow_mode=OrderFlowEvidenceMode.ACTUAL,
            ),
            delta_ratio=0.5,
            mtf_balance=0.5,
            ob_touch=True,
        )
    )
    assert "SUPPORT" not in result.evidence_records["semantic_state"].tolist()
    assert "SUPPORT" not in result.family_snapshots[
        "aggregate_semantic_state"
    ].tolist()


def test_availability_signature_changes_when_certified_family_becomes_available():
    base = analyze(frozen_snapshot())
    extended = analyze(frozen_snapshot(config(multiscale=True), mtf_balance=0.5))
    assert (
        base.availability_signature.iloc[0].global_availability_signature_hash
        != extended.availability_signature.iloc[0].global_availability_signature_hash
    )


def test_reasoning_package_has_no_outcome_model_or_geometry_dependency():
    import ast
    from pathlib import Path

    source = Path("src/trading_system/reasoning/evidence_families.py").read_text()
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    forbidden_imports = (
        "trading_system.research.outcome_observer",
        "trading_system.research.eligibility",
        "trading_system.research.dataset_builder",
        "model",
        "scorer",
        "geometry",
        "execution",
    )
    assert not any(
        token in module for token in forbidden_imports for module in imported
    )


def test_all_deterministic_ids_are_stable_sha256_strings():
    result = analyze(frozen_snapshot(config(multiscale=True), mtf_balance=0.5))
    for frame, columns in (
        (result.family_snapshots, ("family_snapshot_id", "snapshot_hash")),
        (result.evidence_records, ("record_id", "record_hash", "independence_cluster_id")),
        (result.evidence_sources, ("record_id", "source_node_id")),
        (result.provenance_relations, ("left_record_id", "right_record_id", "relation_hash")),
        (result.availability_signature, ("global_availability_signature_hash",)),
    ):
        for column in columns:
            assert frame[column].str.fullmatch(r"[0-9a-f]{64}").all()


class FuturePayloadSentinel:
    def __init__(self):
        self.touches = 0

    def _fail(self):
        self.touches += 1
        raise AssertionError("future semantic payload accessed")

    def __str__(self):
        return self._fail()

    def __bool__(self):
        return self._fail()

    def __eq__(self, other):
        return self._fail()


def test_future_payload_sentinel_not_accessed_before_position_rejection():
    snapshot = reasoning_snapshot(frozen_snapshot())
    observations = snapshot.observation_rows.copy(deep=True)
    future = observations.iloc[[0]].copy(deep=True)
    sentinel = FuturePayloadSentinel()
    future["observation_id"] = int(observations["observation_id"].max()) + 1
    future["observed_position"] = snapshot.decision_information_key.bar_position + 1
    future["observation_type"] = pd.Series([sentinel], dtype=object)
    observations = pd.concat([observations, future], ignore_index=True)
    observations["observation_id"] = pd.array(observations["observation_id"], dtype="Int64")
    observations["observed_position"] = pd.array(observations["observed_position"], dtype="Int64")
    with pytest.raises(ReasoningContractError, match="future record"):
        DynamicEvidenceFamilyReasoner().analyze(
            replace(snapshot, observation_rows=observations)
        )
    assert sentinel.touches == 0


def test_invalid_relationship_bearing_rejected_without_inference():
    snapshot = reasoning_snapshot(frozen_snapshot())
    relationships = snapshot.relationship_rows.copy(deep=True)
    relationships.loc[0, "relationship_bearing"] = "BULLISH_SOUNDING_BUT_UNCERTIFIED"
    altered = rehash_reasoning_snapshot(
        replace(snapshot, relationship_rows=relationships)
    )
    with pytest.raises(ReasoningContractError, match="unsupported relationship bearing"):
        DynamicEvidenceFamilyReasoner().analyze(altered)

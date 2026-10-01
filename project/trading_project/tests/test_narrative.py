import numpy as np
import pandas as pd
import pytest

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import (
    CausalMarketNarrativeEngine,
    HypothesisState,
    HypothesisType,
    NarrativeDataError,
    NarrativeResult,
    RelationshipBearing,
)
from trading_system.orderflow.volume_delta import CausalVolumeDeltaEngine, OrderFlowMode
from trading_system.orderflow.absorption import CausalAbsorptionEvidenceEngine


def config(**kwargs):
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
    values.update(kwargs)
    return EvidenceVectorConfig(**values)


def evidence_from_source(source: pd.DataFrame, cfg: EvidenceVectorConfig):
    return CausalEvidenceVectorEngine(config=cfg).analyze(source)


def structural_source(states, events, index=None):
    if index is None:
        index = pd.RangeIndex(len(states))
    return pd.DataFrame(
        {
            "structure_state_after": pd.Series(states, index=index, dtype="string"),
            "structural_break_event": pd.Series(events, index=index, dtype="string"),
        },
        index=index,
    )


def add_multiscale(source, balances, consensus=None):
    result = source.copy()
    n = len(result)
    if consensus is None:
        consensus = [abs(value) if value is not None and not pd.isna(value) else np.nan for value in balances]
    result["available_scale_count"] = pd.Series([2] * n, index=result.index, dtype="int64")
    result["unavailable_scale_count"] = pd.Series([0] * n, index=result.index, dtype="int64")
    result["directional_scale_count"] = pd.Series([2] * n, index=result.index, dtype="int64")
    result["availability_fraction"] = 1.0
    result["directional_fraction"] = 1.0
    result["directional_balance"] = pd.Series(balances, index=result.index, dtype="float64")
    result["directional_consensus"] = pd.Series(consensus, index=result.index, dtype="float64")
    result["directional_conflict"] = pd.Series([False] * n, index=result.index, dtype="bool")
    return result


def add_range(source, positions):
    result = source.copy()
    result["current_range_position_raw"] = positions
    result["current_midpoint_displacement"] = [np.nan if pd.isna(value) else 2 * value - 1 for value in positions]
    result["current_discount_depth"] = [np.nan if pd.isna(value) else max(-(2 * value - 1), 0) for value in positions]
    result["current_premium_depth"] = [np.nan if pd.isna(value) else max(2 * value - 1, 0) for value in positions]
    return result


def actual_flow_surface(close):
    raw = pd.DataFrame(
        {
            "close": close,
            "buy_volume": [7.0] * len(close),
            "sell_volume": [3.0] * len(close),
        }
    )
    delta = CausalVolumeDeltaEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(raw)
    return CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.ACTUAL_AGGRESSOR).analyze(delta)


def proxy_flow_surface(close):
    raw = pd.DataFrame(
        {
            "open": close,
            "high": np.asarray(close) + 1,
            "low": np.asarray(close) - 1,
            "close": close,
            "volume": [100.0] * len(close),
        }
    )
    pressure = CausalVolumeDeltaEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(raw)
    return CausalAbsorptionEvidenceEngine(mode=OrderFlowMode.OHLCV_PROXY).analyze(pressure)


def run(source, cfg):
    evidence, manifest = evidence_from_source(source, cfg)
    return CausalMarketNarrativeEngine().analyze(evidence, manifest)


def test_up_structure_alone_is_observation_not_hypothesis():
    result = run(
        structural_source(["UP_STRUCTURE", "UP_STRUCTURE"], ["NONE", "NONE"]),
        config(),
    )
    assert result.active_hypotheses.empty
    assert result.hypothesis_ledger.empty
    assert result.observation_ledger["observation_type"].tolist() == [
        "LOCAL_STRUCTURE_UP_PRESENT"
    ]
    assert result.observation_ledger.iloc[0]["bootstrap_context"] == "LEFT_BOUNDARY_STATE_ONLY"


def test_up_structure_and_bos_create_exactly_one_continuation_hypothesis():
    result = run(
        structural_source(
            ["UP_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
            ["BOS_UP", "NONE", "NONE"],
        ),
        config(),
    )
    assert result.active_hypotheses["hypothesis_type"].tolist() == [
        HypothesisType.UPWARD_CONTINUATION_AFTER_PROJECT_BREAK.value
    ]
    created = result.hypothesis_ledger[
        result.hypothesis_ledger["ledger_event_type"] == "CREATED"
    ]
    assert len(created) == 1
    foundations = result.relationship_ledger[
        result.relationship_ledger["evidence_family"]
        == "LOCAL_STRUCTURAL_FOUNDATION"
    ]
    assert len(foundations) == 1
    assert foundations.iloc[0]["relationship_bearing"] == "CONTEXTUALIZES"
    assert "SUPPORTS" not in {bearing.value for bearing in RelationshipBearing}


def test_persistent_up_does_not_duplicate_hypotheses_or_observations():
    result = run(
        structural_source(
            ["UP_STRUCTURE"] * 100,
            ["BOS_UP"] + ["NONE"] * 99,
        ),
        config(),
    )
    assert len(result.active_hypotheses) == 1
    assert (
        result.observation_ledger["observation_type"]
        == "LOCAL_STRUCTURE_UP_PRESENT"
    ).sum() == 1
    assert (
        result.hypothesis_ledger["ledger_event_type"] == "CREATED"
    ).sum() == 1


def test_choch_without_prior_opposite_state_is_observation_only():
    result = run(
        structural_source(["UP_STRUCTURE"], ["CHOCH_UP"]),
        config(),
    )
    assert result.active_hypotheses.empty
    assert result.hypothesis_ledger.empty
    assert "PROJECT_SHIFT_CANDIDATE_UP_OBSERVED" in result.observation_ledger[
        "observation_type"
    ].tolist()


def test_transition_requires_prior_state_and_no_same_row_resolution():
    result = run(
        structural_source(
            ["DOWN_STRUCTURE", "UP_STRUCTURE"],
            ["NONE", "CHOCH_UP"],
        ),
        config(),
    )
    assert result.active_hypotheses["hypothesis_type"].tolist() == [
        HypothesisType.UPWARD_TRANSITION_AFTER_PROJECT_SHIFT.value
    ]
    assert result.active_hypotheses.iloc[0]["current_state"] == "MONITORING"
    assert not (
        result.hypothesis_ledger["new_state"]
        == "OBSERVED_DIRECTION_ESTABLISHED"
    ).any()


def test_transition_resolves_only_on_later_matching_structure_row():
    result = run(
        structural_source(
            ["DOWN_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
            ["NONE", "CHOCH_UP", "NONE"],
        ),
        config(),
    )
    assert result.active_hypotheses.empty
    state_changes = result.hypothesis_ledger[
        result.hypothesis_ledger["new_state"]
        == HypothesisState.OBSERVED_DIRECTION_ESTABLISHED.value
    ]
    assert state_changes["event_position"].tolist() == [2]


def test_continuation_is_contradicted_by_opposite_persistent_structure():
    result = run(
        structural_source(
            ["UP_STRUCTURE", "DOWN_STRUCTURE"],
            ["BOS_UP", "NONE"],
        ),
        config(),
    )
    assert result.active_hypotheses.empty
    assert "CONTRADICTED" in result.hypothesis_ledger["new_state"].dropna().tolist()
    contradiction = result.relationship_ledger[
        result.relationship_ledger["relationship_bearing"] == "CONTRADICTS"
    ]
    assert contradiction["observed_position"].tolist() == [1]


def test_new_same_type_foundation_supersedes_old_and_ids_are_deterministic():
    source = structural_source(
        ["UP_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
        ["BOS_UP", "NONE", "BOS_UP"],
    )
    result = run(source, config())
    assert result.active_hypotheses["hypothesis_id"].tolist() == [1]
    superseded = result.hypothesis_ledger[
        result.hypothesis_ledger["new_state"] == "SUPERSEDED"
    ]
    assert superseded["hypothesis_id"].tolist() == [0]
    fresh = run(source, config())
    pd.testing.assert_frame_equal(
        result.hypothesis_ledger, fresh.hypothesis_ledger, check_exact=True
    )


def test_multiscale_alignment_and_directional_opposition_are_descriptive():
    positive = add_multiscale(
        structural_source(["UP_STRUCTURE"], ["BOS_UP"]),
        [0.5],
    )
    positive_result = run(positive, config(multiscale=True))
    relation = positive_result.relationship_ledger[
        positive_result.relationship_ledger["evidence_family"]
        == "MULTISCALE_STRUCTURE"
    ].iloc[0]
    assert relation.relationship_bearing == "ALIGNS_WITH"

    negative = add_multiscale(
        structural_source(["UP_STRUCTURE"], ["BOS_UP"]),
        [-0.5],
    )
    negative_result = run(negative, config(multiscale=True))
    relation = negative_result.relationship_ledger[
        negative_result.relationship_ledger["evidence_family"]
        == "MULTISCALE_STRUCTURE"
    ].iloc[0]
    assert relation.relationship_bearing == "DIRECTIONALLY_OPPOSES"
    assert "SUPPORTS" not in negative_result.relationship_ledger[
        "relationship_bearing"
    ].tolist()


def test_multiscale_missing_is_unknown_and_disabled_has_no_relationship():
    missing = add_multiscale(
        structural_source(["UP_STRUCTURE"], ["BOS_UP"]),
        [np.nan],
        [np.nan],
    )
    missing_result = run(missing, config(multiscale=True))
    relation = missing_result.relationship_ledger[
        missing_result.relationship_ledger["evidence_family"]
        == "MULTISCALE_STRUCTURE"
    ].iloc[0]
    assert relation.relationship_bearing == "UNKNOWN"

    disabled_result = run(
        structural_source(["UP_STRUCTURE"], ["BOS_UP"]),
        config(multiscale=False),
    )
    assert "MULTISCALE_STRUCTURE" not in disabled_result.relationship_ledger[
        "evidence_family"
    ].tolist()


def test_mixed_structure_is_neutral_and_does_not_terminate_continuation():
    result = run(
        structural_source(
            ["UP_STRUCTURE", "MIXED"],
            ["BOS_UP", "NONE"],
        ),
        config(),
    )
    assert len(result.active_hypotheses) == 1
    mixed_relation = result.relationship_ledger[
        (result.relationship_ledger["evidence_family"] == "LOCAL_STRUCTURE_STATE")
        & (result.relationship_ledger["observed_position"] == 1)
    ].iloc[0]
    assert mixed_relation.relationship_bearing == "NEUTRAL"


def test_dealing_range_descriptors_create_one_context_relationship():
    source = add_range(
        structural_source(["UP_STRUCTURE"], ["BOS_UP"]),
        [1.5],
    )
    result = run(source, config(dealing_range=True))
    relationships = result.relationship_ledger[
        result.relationship_ledger["evidence_family"]
        == "DEALING_RANGE_GEOMETRY"
    ]
    assert len(relationships) == 1
    source_rows = result.relationship_sources[
        result.relationship_sources["relationship_id"]
        == relationships.iloc[0].relationship_id
    ]
    assert set(source_rows["source_feature_name"]) == {
        "current_range_position_raw",
        "current_midpoint_displacement",
        "current_discount_depth",
        "current_premium_depth",
    }
    assert relationships.iloc[0].relationship_bearing == "CONTEXTUALIZES"


def test_actual_flow_is_descriptive_alignment_and_response_qualification():
    structure = structural_source(
        ["UP_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
        ["BOS_UP", "NONE", "NONE"],
    )
    flow = actual_flow_surface([100.0, 101.0, 101.0])
    source = pd.concat(
        [structure, flow.drop(columns=["close", "buy_volume", "sell_volume"])],
        axis=1,
    )
    result = run(
        source,
        config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL),
    )
    direction_relations = result.relationship_ledger[
        result.relationship_ledger["evidence_family"]
        == "ACTUAL_FLOW_DIRECTION"
    ]
    assert set(direction_relations["relationship_bearing"]).issubset(
        {"ALIGNS_WITH", "DIRECTIONALLY_OPPOSES", "NEUTRAL", "UNKNOWN"}
    )
    response_relations = result.relationship_ledger[
        result.relationship_ledger["evidence_family"]
        == "ACTUAL_FLOW_RESPONSE"
    ]
    assert set(response_relations["relationship_bearing"]).issubset(
        {"QUALIFIES", "UNKNOWN"}
    )
    assert "SUPPORTS" not in result.relationship_ledger[
        "relationship_bearing"
    ].tolist()


def test_proxy_flow_preserves_proxy_provenance():
    structure = structural_source(
        ["UP_STRUCTURE", "UP_STRUCTURE"],
        ["BOS_UP", "NONE"],
    )
    flow = proxy_flow_surface([100.0, 101.0])
    source = pd.concat(
        [
            structure,
            flow.drop(columns=["open", "high", "low", "close", "volume"]),
        ],
        axis=1,
    )
    result = run(
        source,
        config(order_flow_mode=OrderFlowEvidenceMode.PROXY),
    )
    proxy_relations = result.relationship_ledger[
        result.relationship_ledger["evidence_family"].str.startswith("PROXY")
    ]
    assert not proxy_relations.empty
    assert (proxy_relations["source_mode"] == "PROXY").all()
    assert (
        proxy_relations["epistemic_status"] == "SOURCE_APPROXIMATION"
    ).all()


def test_persistent_observation_dedup_and_event_observations_are_row_local():
    source = structural_source(
        ["UP_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
        ["BOS_UP", "NONE", "BOS_UP"],
    )
    result = run(source, config())
    state_observations = result.observation_ledger[
        result.observation_ledger["observation_type"]
        == "LOCAL_STRUCTURE_UP_PRESENT"
    ]
    assert len(state_observations) == 1
    break_observations = result.observation_ledger[
        result.observation_ledger["observation_type"]
        == "PROJECT_CONTINUATION_BREAK_UP_OBSERVED"
    ]
    assert break_observations["observed_position"].tolist() == [0, 2]
    assert (
        break_observations["persistence_scope"] == "EVENT_SCOPED"
    ).all()


def test_same_row_facts_share_information_time_and_no_same_row_resolution():
    source = add_multiscale(
        structural_source(
            ["DOWN_STRUCTURE", "UP_STRUCTURE"],
            ["NONE", "CHOCH_UP"],
        ),
        [-1.0, -1.0],
    )
    source["high_side_first_wick_only_count"] = pd.Series(
        [0, 1], dtype="int64"
    )
    source["low_side_first_wick_only_count"] = pd.Series(
        [0, 0], dtype="int64"
    )
    source["high_side_first_close_breach_count"] = pd.Series(
        [0, 0], dtype="int64"
    )
    source["low_side_first_close_breach_count"] = pd.Series(
        [0, 0], dtype="int64"
    )
    source["nearest_same_side_distance_fraction"] = [np.nan, np.nan]
    source["nearest_distance_percentile"] = [np.nan, np.nan]
    source["nearest_distance_reference_history_count"] = pd.Series(
        [0, 0], dtype="int64"
    )
    result = run(source, config(liquidity=True, multiscale=True))
    row_observations = result.observation_ledger[
        result.observation_ledger["observed_position"] == 1
    ]
    assert row_observations["same_row_batch_id"].nunique() == 1
    row_relationships = result.relationship_ledger[
        result.relationship_ledger["observed_position"] == 1
    ]
    assert row_relationships["same_row_batch_id"].nunique() == 1
    assert not (
        result.hypothesis_ledger["new_state"]
        == "OBSERVED_DIRECTION_ESTABLISHED"
    ).any()
    assert result.active_hypotheses.iloc[0].current_state == "MONITORING"


def _filter_position(table, column, k):
    if table.empty:
        return table.copy()
    return table[table[column] < k].reset_index(drop=True)


def _assert_result_prefix(full, truncated, k):
    pd.testing.assert_frame_equal(
        full.narrative_surface.iloc[:k],
        truncated.narrative_surface.iloc[:k],
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        _filter_position(full.observation_ledger, "observed_position", k),
        _filter_position(truncated.observation_ledger, "observed_position", k),
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        _filter_position(full.hypothesis_ledger, "event_position", k),
        _filter_position(truncated.hypothesis_ledger, "event_position", k),
        check_exact=True,
    )
    expected_relationships = _filter_position(
        full.relationship_ledger, "observed_position", k
    )
    pd.testing.assert_frame_equal(
        expected_relationships,
        _filter_position(truncated.relationship_ledger, "observed_position", k),
        check_exact=True,
    )
    relationship_ids = set(expected_relationships["relationship_id"].dropna())
    expected_sources = full.relationship_sources[
        full.relationship_sources["relationship_id"].isin(relationship_ids)
    ].reset_index(drop=True)
    truncated_sources = truncated.relationship_sources[
        truncated.relationship_sources["relationship_id"].isin(relationship_ids)
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(
        expected_sources,
        truncated_sources,
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        full.narrative_manifest,
        truncated.narrative_manifest,
        check_exact=True,
    )


def test_exact_truncation_for_all_secondary_ledgers_and_ids():
    source = add_multiscale(
        structural_source(
            [
                "UP_STRUCTURE",
                "UP_STRUCTURE",
                "MIXED",
                "DOWN_STRUCTURE",
                "DOWN_STRUCTURE",
            ],
            ["BOS_UP", "NONE", "NONE", "CHOCH_DOWN", "BOS_DOWN"],
        ),
        [0.5, 0.5, 0.0, -0.5, -1.0],
    )
    cfg = config(multiscale=True)
    evidence, manifest = evidence_from_source(source, cfg)
    engine = CausalMarketNarrativeEngine()
    full = engine.analyze(evidence, manifest)
    for k in range(1, len(source) + 1):
        truncated = engine.analyze(
            evidence.iloc[:k].copy(),
            manifest.copy(deep=True),
        )
        _assert_result_prefix(full, truncated, k)


def test_future_mutation_and_append_do_not_change_historical_ledgers():
    source = add_multiscale(
        structural_source(
            ["UP_STRUCTURE", "UP_STRUCTURE", "DOWN_STRUCTURE"],
            ["BOS_UP", "NONE", "CHOCH_DOWN"],
        ),
        [0.5, 0.5, -0.5],
    )
    cfg = config(multiscale=True)
    evidence, manifest = evidence_from_source(source, cfg)
    engine = CausalMarketNarrativeEngine()
    original = engine.analyze(evidence, manifest)

    mutated = evidence.copy(deep=True)
    mutated.loc[mutated.index[2], "ev__structure_state_after"] = "UP_STRUCTURE"
    mutated.loc[mutated.index[2], "ev__structural_break_event"] = "NONE"
    mutated.loc[mutated.index[2], "ev__directional_balance"] = 1.0
    mutated_result = engine.analyze(mutated, manifest)
    _assert_result_prefix(original, mutated_result, 2)

    future_source = add_multiscale(
        structural_source(
            [
                "UP_STRUCTURE",
                "UP_STRUCTURE",
                "DOWN_STRUCTURE",
                "DOWN_STRUCTURE",
            ],
            ["BOS_UP", "NONE", "CHOCH_DOWN", "BOS_DOWN"],
        ),
        [0.5, 0.5, -0.5, -1.0],
    )
    future_evidence, future_manifest = evidence_from_source(future_source, cfg)
    appended_result = engine.analyze(future_evidence, future_manifest)
    _assert_result_prefix(original, appended_result, len(source))


def test_same_instance_a_b_a_and_fresh_determinism():
    cfg = config()
    source_a = structural_source(
        ["UP_STRUCTURE", "UP_STRUCTURE"], ["BOS_UP", "NONE"]
    )
    source_b = structural_source(
        ["DOWN_STRUCTURE", "DOWN_STRUCTURE"], ["BOS_DOWN", "NONE"]
    )
    evidence_a, manifest_a = evidence_from_source(source_a, cfg)
    evidence_b, manifest_b = evidence_from_source(source_b, cfg)
    engine = CausalMarketNarrativeEngine()
    first = engine.analyze(evidence_a, manifest_a)
    repeated = engine.analyze(evidence_a, manifest_a)
    engine.analyze(evidence_b, manifest_b)
    after_b = engine.analyze(evidence_a, manifest_a)
    fresh = CausalMarketNarrativeEngine().analyze(evidence_a, manifest_a)
    for attribute in NarrativeResult.__dataclass_fields__:
        pd.testing.assert_frame_equal(
            getattr(first, attribute),
            getattr(repeated, attribute),
            check_exact=True,
        )
        pd.testing.assert_frame_equal(
            getattr(first, attribute),
            getattr(after_b, attribute),
            check_exact=True,
        )
        pd.testing.assert_frame_equal(
            getattr(first, attribute),
            getattr(fresh, attribute),
            check_exact=True,
        )


def test_manifest_documents_exact_minimal_scope_and_no_score_fields():
    manifest = CausalMarketNarrativeEngine.narrative_manifest()
    hypotheses = manifest[
        manifest["record_type"] == "HYPOTHESIS_DEFINITION"
    ]
    assert hypotheses["name"].tolist() == [
        item.value for item in HypothesisType
    ]
    assert set(RelationshipBearing) == {
        RelationshipBearing.ALIGNS_WITH,
        RelationshipBearing.DIRECTIONALLY_OPPOSES,
        RelationshipBearing.CONTRADICTS,
        RelationshipBearing.CONTEXTUALIZES,
        RelationshipBearing.QUALIFIES,
        RelationshipBearing.NEUTRAL,
        RelationshipBearing.UNKNOWN,
        RelationshipBearing.NOT_APPLICABLE,
    }
    text = " ".join(manifest.astype(str).to_numpy().ravel()).lower()
    for forbidden in (
        "weight",
        "probability",
        "trade_signal",
        "buy_signal",
        "sell_signal",
        "outcome",
    ):
        assert forbidden not in text
    assert (
        manifest["same_row_semantics"].dropna()
        == "ATOMIC_INFORMATION_TIME"
    ).all()


def test_unregistered_evidence_and_outcome_columns_are_rejected():
    source = structural_source(["UP_STRUCTURE"], ["BOS_UP"])
    evidence, manifest = evidence_from_source(source, config())
    evidence["future_return"] = 1.0
    with pytest.raises(NarrativeDataError):
        CausalMarketNarrativeEngine().analyze(evidence, manifest)


def test_empty_evidence_with_empty_manifest_is_supported():
    evidence = pd.DataFrame(index=pd.RangeIndex(0))
    manifest = pd.DataFrame(
        columns=(
            "feature_name",
            "output_column",
            "source_module",
            "semantic_type",
            "missingness_policy",
            "event_local",
            "support_column",
            "freshness_column",
            "source_mode",
            "directional_semantics",
            "expected_domain",
            "epistemic_status",
        )
    )
    result = CausalMarketNarrativeEngine().analyze(evidence, manifest)
    assert result.narrative_surface.empty
    assert result.observation_ledger.empty
    assert result.active_hypotheses.empty
    assert result.hypothesis_ledger.empty
    assert result.relationship_ledger.empty
    assert result.relationship_sources.empty


def test_real_actual_and_proxy_pipeline_integration():
    structure = structural_source(
        ["UP_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
        ["BOS_UP", "NONE", "NONE"],
    )

    actual = actual_flow_surface([100.0, 101.0, 101.0])
    actual_source = pd.concat(
        [
            structure,
            actual.drop(columns=["close", "buy_volume", "sell_volume"]),
        ],
        axis=1,
    )
    actual_evidence, actual_manifest = evidence_from_source(
        actual_source,
        config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL),
    )
    actual_result = CausalMarketNarrativeEngine().analyze(
        actual_evidence, actual_manifest
    )
    assert "ACTUAL_FLOW_DIRECTION" in actual_result.relationship_ledger[
        "evidence_family"
    ].tolist()
    assert not (
        actual_result.relationship_ledger["source_mode"] == "PROXY"
    ).any()

    proxy = proxy_flow_surface([100.0, 101.0, 101.0])
    proxy_source = pd.concat(
        [
            structure,
            proxy.drop(columns=["open", "high", "low", "close", "volume"]),
        ],
        axis=1,
    )
    proxy_evidence, proxy_manifest = evidence_from_source(
        proxy_source,
        config(order_flow_mode=OrderFlowEvidenceMode.PROXY),
    )
    proxy_result = CausalMarketNarrativeEngine().analyze(
        proxy_evidence, proxy_manifest
    )
    proxy_relationships = proxy_result.relationship_ledger[
        proxy_result.relationship_ledger["evidence_family"].str.startswith(
            "PROXY"
        )
    ]
    assert not proxy_relationships.empty
    assert (proxy_relationships["source_mode"] == "PROXY").all()
    assert (
        proxy_relationships["epistemic_status"] == "SOURCE_APPROXIMATION"
    ).all()


def test_primary_surface_contains_no_support_vote_or_score_columns():
    result = run(
        structural_source(["UP_STRUCTURE"], ["BOS_UP"]), config()
    )
    forbidden = (
        "supporting_family_count",
        "opposing_family_count",
        "contradicting_family_count",
        "net_support",
        "score",
        "probability",
        "confidence",
        "trade_signal",
    )
    assert not any(
        any(token in column for token in forbidden)
        for column in result.narrative_surface.columns
    )


def test_certified_manifest_rejects_forged_contract_metadata():
    structure = structural_source(["UP_STRUCTURE"], ["BOS_UP"])
    evidence, manifest = evidence_from_source(structure, config())
    forged = manifest.copy(deep=True)
    forged.loc[
        forged["feature_name"] == "structural_break_event", "event_local"
    ] = False
    with pytest.raises(NarrativeDataError, match="certified feature contract mismatch"):
        CausalMarketNarrativeEngine().analyze(evidence, forged)

    actual = actual_flow_surface([100.0])
    actual_source = pd.concat(
        [structure, actual.drop(columns=["close", "buy_volume", "sell_volume"])],
        axis=1,
    )
    actual_evidence, actual_manifest = evidence_from_source(
        actual_source, config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)
    )
    forged_actual = actual_manifest.copy(deep=True)
    forged_actual.loc[
        forged_actual["feature_name"] == "delta_ratio", "source_mode"
    ] = "PROXY"
    with pytest.raises(NarrativeDataError, match="certified feature contract mismatch"):
        CausalMarketNarrativeEngine().analyze(actual_evidence, forged_actual)

    proxy = proxy_flow_surface([100.0])
    proxy_source = pd.concat(
        [structure, proxy.drop(columns=["open", "high", "low", "close", "volume"])],
        axis=1,
    )
    proxy_evidence, proxy_manifest = evidence_from_source(
        proxy_source, config(order_flow_mode=OrderFlowEvidenceMode.PROXY)
    )
    forged_proxy = proxy_manifest.copy(deep=True)
    forged_proxy.loc[
        forged_proxy["feature_name"] == "volume_pressure_proxy",
        "epistemic_status",
    ] = "FACTUAL"
    with pytest.raises(NarrativeDataError, match="certified feature contract mismatch"):
        CausalMarketNarrativeEngine().analyze(proxy_evidence, forged_proxy)


def test_manifest_and_evidence_schema_adversarial_rejections():
    evidence, manifest = evidence_from_source(
        structural_source(["UP_STRUCTURE"], ["BOS_UP"]), config()
    )
    duplicate_evidence = pd.concat([evidence, evidence.iloc[:, [0]]], axis=1)
    with pytest.raises(NarrativeDataError, match="invalid evidence frame"):
        CausalMarketNarrativeEngine().analyze(duplicate_evidence, manifest)

    duplicate_name = pd.concat([manifest, manifest.iloc[[0]]], ignore_index=True)
    duplicate_name.loc[duplicate_name.index[-1], "output_column"] = "ev__unique"
    with pytest.raises(NarrativeDataError, match="duplicate manifest identity"):
        CausalMarketNarrativeEngine().analyze(evidence, duplicate_name)

    duplicate_output = manifest.copy(deep=True)
    duplicate_output.loc[
        duplicate_output["feature_name"] == "structural_break_event",
        "output_column",
    ] = "ev__structure_state_after"
    with pytest.raises(NarrativeDataError, match="duplicate manifest identity"):
        CausalMarketNarrativeEngine().analyze(evidence, duplicate_output)

    missing_evidence = evidence.drop(columns=["ev__structural_break_event"])
    with pytest.raises(NarrativeDataError, match="manifest evidence columns missing"):
        CausalMarketNarrativeEngine().analyze(missing_evidence, manifest)

    partial_manifest = manifest[
        manifest["feature_name"] != "structural_break_event"
    ].reset_index(drop=True)
    partial_evidence = evidence.drop(columns=["ev__structural_break_event"])
    with pytest.raises(NarrativeDataError, match="incomplete certified feature group"):
        CausalMarketNarrativeEngine().analyze(partial_evidence, partial_manifest)


def test_inputs_are_immutable_and_output_index_is_preserved_exactly():
    index = pd.Index([10, 20], name="information_position")
    evidence, manifest = evidence_from_source(
        structural_source(
            ["UP_STRUCTURE", "UP_STRUCTURE"], ["BOS_UP", "NONE"], index=index
        ),
        config(),
    )
    evidence_before = evidence.copy(deep=True)
    manifest_before = manifest.copy(deep=True)
    result = CausalMarketNarrativeEngine().analyze(evidence, manifest)
    pd.testing.assert_frame_equal(evidence, evidence_before, check_exact=True)
    pd.testing.assert_frame_equal(manifest, manifest_before, check_exact=True)
    pd.testing.assert_index_equal(result.narrative_surface.index, index, exact=True)


def test_relationship_sources_preserve_exact_mtf_and_range_values():
    source = add_range(
        add_multiscale(
            structural_source(["UP_STRUCTURE"], ["BOS_UP"]),
            [0.5],
            [0.75],
        ),
        [1.25],
    )
    evidence, manifest = evidence_from_source(
        source, config(multiscale=True, dealing_range=True)
    )
    result = CausalMarketNarrativeEngine().analyze(evidence, manifest)

    expected = {
        "MULTISCALE_STRUCTURE": {
            "directional_balance",
            "directional_consensus",
            "directional_scale_count",
            "availability_fraction",
            "directional_conflict",
        },
        "DEALING_RANGE_GEOMETRY": {
            "current_range_position_raw",
            "current_midpoint_displacement",
            "current_discount_depth",
            "current_premium_depth",
        },
    }
    for family, expected_names in expected.items():
        relationship = result.relationship_ledger[
            result.relationship_ledger["evidence_family"] == family
        ].iloc[0]
        links = result.relationship_sources[
            result.relationship_sources["relationship_id"]
            == relationship.relationship_id
        ]
        assert set(links["source_feature_name"]) == expected_names
        for link in links.itertuples(index=False):
            value = evidence.loc[
                evidence.index[int(relationship.observed_position)],
                link.source_output_column,
            ]
            domain = manifest.loc[
                manifest["feature_name"] == link.source_feature_name,
                "expected_domain",
            ].iloc[0]
            if pd.isna(value):
                assert link.source_availability_state == "UNKNOWN"
                assert pd.isna(link.source_value_float)
                assert pd.isna(link.source_value_integer)
                assert pd.isna(link.source_value_boolean)
                assert pd.isna(link.source_value_category)
            elif domain == "bool":
                assert link.source_value_boolean == bool(value)
                assert pd.isna(link.source_value_float)
                assert pd.isna(link.source_value_integer)
                assert pd.isna(link.source_value_category)
                assert link.source_availability_state == "AVAILABLE"
            elif domain == "count":
                assert link.source_value_integer == int(value)
                assert pd.isna(link.source_value_float)
                assert pd.isna(link.source_value_boolean)
                assert pd.isna(link.source_value_category)
                assert link.source_availability_state == "AVAILABLE"
            else:
                assert link.source_value_float == pytest.approx(float(value))
                assert pd.isna(link.source_value_integer)
                assert pd.isna(link.source_value_boolean)
                assert pd.isna(link.source_value_category)
                assert link.source_availability_state == "AVAILABLE"

    range_relationship = result.relationship_ledger[
        result.relationship_ledger["evidence_family"] == "DEALING_RANGE_GEOMETRY"
    ].iloc[0]
    assert range_relationship.primary_numeric_value == pytest.approx(1.25)


def test_flow_response_sources_preserve_absorption_side_opposed_and_support():
    structure = structural_source(
        ["UP_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
        ["BOS_UP", "NONE", "NONE"],
    )
    flow = actual_flow_surface([100.0, 101.0, 101.0])
    source = pd.concat(
        [structure, flow.drop(columns=["close", "buy_volume", "sell_volume"])],
        axis=1,
    )
    evidence, manifest = evidence_from_source(
        source, config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)
    )
    result = CausalMarketNarrativeEngine().analyze(evidence, manifest)
    response = result.relationship_ledger[
        result.relationship_ledger["evidence_family"] == "ACTUAL_FLOW_RESPONSE"
    ].iloc[-1]
    links = result.relationship_sources[
        result.relationship_sources["relationship_id"] == response.relationship_id
    ]
    assert set(links["source_feature_name"]) == {
        "actual_absorption_evidence",
        "absorbed_aggression_side",
        "opposed_response_percentile",
        "opposed_response_history_count",
    }
    opposed_link = links[
        links["source_feature_name"] == "opposed_response_percentile"
    ].iloc[0]
    evidence_value = evidence.iloc[int(response.observed_position)][
        "ev__opposed_response_percentile"
    ]
    if pd.isna(evidence_value):
        assert opposed_link.source_availability_state == "UNKNOWN"
    else:
        assert opposed_link.source_value_float == pytest.approx(evidence_value)
    support_link = links[
        links["source_feature_name"] == "opposed_response_history_count"
    ].iloc[0]
    assert support_link.source_value_integer == int(
        evidence.iloc[int(response.observed_position)][
            "ev__opposed_response_history_count"
        ]
    )
    assert pd.isna(support_link.source_value_float)


def test_change_ledger_appends_when_nonprimary_source_descriptor_changes():
    source = add_multiscale(
        structural_source(
            ["UP_STRUCTURE", "UP_STRUCTURE"], ["BOS_UP", "NONE"]
        ),
        [0.5, 0.5],
        [0.2, 0.8],
    )
    result = run(source, config(multiscale=True))
    mtf = result.relationship_ledger[
        result.relationship_ledger["evidence_family"] == "MULTISCALE_STRUCTURE"
    ]
    assert mtf["observed_position"].tolist() == [0, 1]
    assert (
        result.narrative_manifest.loc[
            result.narrative_manifest["record_type"] == "EVIDENCE_FAMILY",
            "bearing_policy",
        ]
        == "APPEND_ON_CHANGE_ONE_RELATIONSHIP_PER_FAMILY_PER_HYPOTHESIS"
    ).all()


def test_same_row_opposite_foundation_blocks_transition_establishment():
    result = run(
        structural_source(
            ["DOWN_STRUCTURE", "DOWN_STRUCTURE", "UP_STRUCTURE"],
            ["NONE", "CHOCH_UP", "BOS_DOWN"],
        ),
        config(),
    )
    terminal = result.hypothesis_ledger[
        result.hypothesis_ledger["hypothesis_id"] == 0
    ].iloc[-1]
    assert terminal.new_state == "CONTRADICTED"
    assert terminal.event_position == 2
    assert not (
        result.hypothesis_ledger["new_state"]
        == "OBSERVED_DIRECTION_ESTABLISHED"
    ).any()
    trigger = result.relationship_ledger[
        result.relationship_ledger["relationship_id"]
        == terminal.trigger_relationship_id
    ]
    assert len(trigger) == 1
    assert trigger.iloc[0].relationship_bearing == "CONTRADICTS"
    assert trigger.iloc[0].evidence_family == "LOCAL_STRUCTURAL_FOUNDATION"
    assert trigger.iloc[0].observed_position == 2


def test_supersession_count_and_terminal_trigger_referential_integrity():
    result = run(
        structural_source(
            ["UP_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
            ["BOS_UP", "NONE", "BOS_UP"],
        ),
        config(),
    )
    assert result.narrative_surface.iloc[2].nar__new_hypothesis_count == 1
    assert result.narrative_surface.iloc[2].nar__hypothesis_state_change_count == 1
    superseded = result.hypothesis_ledger[
        result.hypothesis_ledger["new_state"] == "SUPERSEDED"
    ].iloc[0]
    assert superseded.superseded_by_hypothesis_id == 1
    trigger = result.relationship_ledger[
        result.relationship_ledger["relationship_id"]
        == superseded.trigger_relationship_id
    ]
    assert len(trigger) == 1
    assert trigger.iloc[0].hypothesis_id == 1
    assert trigger.iloc[0].evidence_role == "FOUNDATION"

    relationship_ids = set(result.relationship_ledger["relationship_id"])
    assert set(result.relationship_sources["relationship_id"]).issubset(
        relationship_ids
    )
    terminal = result.hypothesis_ledger[
        result.hypothesis_ledger["new_state"].isin(
            ["CONTRADICTED", "OBSERVED_DIRECTION_ESTABLISHED", "SUPERSEDED"]
        )
    ]
    assert terminal["trigger_relationship_id"].notna().all()
    assert set(terminal["trigger_relationship_id"]).issubset(relationship_ids)


def test_relationship_source_membership_matches_declared_families():
    source = add_range(
        add_multiscale(
            structural_source(["UP_STRUCTURE"], ["BOS_UP"]), [0.5]
        ),
        [0.75],
    )
    result = run(source, config(multiscale=True, dealing_range=True))
    expected = {
        "LOCAL_STRUCTURAL_FOUNDATION": {
            "structure_state_after", "structural_break_event"
        },
        "LOCAL_STRUCTURE_STATE": {"structure_state_after"},
        "MULTISCALE_STRUCTURE": {
            "directional_balance", "directional_consensus",
            "directional_scale_count", "availability_fraction",
            "directional_conflict",
        },
        "DEALING_RANGE_GEOMETRY": {
            "current_range_position_raw", "current_midpoint_displacement",
            "current_discount_depth", "current_premium_depth",
        },
    }
    for relationship in result.relationship_ledger.itertuples(index=False):
        links = result.relationship_sources[
            result.relationship_sources["relationship_id"]
            == relationship.relationship_id
        ]
        assert set(links["source_feature_name"]) == expected[
            relationship.evidence_family
        ]


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("feature_name", "forged_structural_break_event"),
        ("output_column", "ev__forged_structural_break_event"),
        ("source_module", "FORGED"),
        ("semantic_type", "CATEGORY"),
        ("missingness_policy", "ALLOW_MISSING"),
        ("event_local", False),
        ("support_column", "forged_support"),
        ("freshness_column", "forged_freshness"),
        ("source_mode", "PROXY"),
        ("directional_semantics", "STRUCTURE_DIRECTION"),
        ("expected_domain", "category_side"),
        ("epistemic_status", "FACTUAL"),
    ],
)
def test_every_consumed_certified_contract_field_rejects_forgery(
    field, forged_value
):
    evidence, manifest = evidence_from_source(
        structural_source(["UP_STRUCTURE"], ["BOS_UP"]), config()
    )
    forged = manifest.copy(deep=True)
    forged.loc[
        forged["feature_name"] == "structural_break_event", field
    ] = forged_value
    with pytest.raises(NarrativeDataError):
        CausalMarketNarrativeEngine().analyze(evidence, forged)


def test_structure_absent_nonstructural_observation_only_mode():
    source = pd.DataFrame(
        {
            "high_side_first_wick_only_count": pd.Series([1], dtype="int64"),
            "low_side_first_wick_only_count": pd.Series([0], dtype="int64"),
            "high_side_first_close_breach_count": pd.Series([0], dtype="int64"),
            "low_side_first_close_breach_count": pd.Series([0], dtype="int64"),
            "nearest_same_side_distance_fraction": [np.nan],
            "nearest_distance_percentile": [np.nan],
            "nearest_distance_reference_history_count": pd.Series(
                [0], dtype="int64"
            ),
        }
    )
    result = run(source, config(structure=False, liquidity=True))
    assert result.active_hypotheses.empty
    assert result.hypothesis_ledger.empty
    assert result.observation_ledger["observation_type"].tolist() == [
        "HIGH_SIDE_WICK_ONLY_INTERACTION_OBSERVED"
    ]
    assert pd.isna(
        result.narrative_surface.iloc[0].nar__current_local_structure_state
    )
    mode = result.narrative_manifest[
        result.narrative_manifest["record_type"] == "INPUT_MODE_CONTRACT"
    ]
    assert mode["name"].tolist() == [
        "OBSERVATION_ONLY_NO_STRUCTURAL_FOUNDATION"
    ]


def test_huge_integer_source_provenance_is_exact_and_causally_stable():
    first_count = 2**53 + 1
    second_count = 2**53 + 2
    structure = structural_source(
        ["UP_STRUCTURE", "UP_STRUCTURE", "UP_STRUCTURE"],
        ["BOS_UP", "NONE", "NONE"],
    )
    flow = actual_flow_surface([100.0, 101.0, 101.0])
    flow["actual_absorption_evidence"] = [0.5, 0.5, 0.5]
    flow["opposed_response_percentile"] = [0.25, 0.25, 0.25]
    flow["absorbed_aggression_side"] = pd.Series(
        ["BUY", "BUY", "BUY"], dtype="string"
    )
    flow["opposed_response_history_count"] = pd.Series(
        [first_count, second_count, second_count], dtype="int64"
    )
    source = pd.concat(
        [structure, flow.drop(columns=["close", "buy_volume", "sell_volume"])],
        axis=1,
    )
    cfg = config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL)
    evidence, manifest = evidence_from_source(source, cfg)
    engine = CausalMarketNarrativeEngine()
    full = engine.analyze(evidence, manifest)

    count_links = full.relationship_sources[
        full.relationship_sources["source_feature_name"]
        == "opposed_response_history_count"
    ]
    assert str(full.relationship_sources["source_value_integer"].dtype) == "Int64"
    assert str(full.relationship_sources["source_value_float"].dtype) == "Float64"
    assert first_count in count_links["source_value_integer"].tolist()
    assert second_count in count_links["source_value_integer"].tolist()
    assert count_links["source_value_float"].isna().all()
    assert count_links["source_value_boolean"].isna().all()
    assert count_links["source_value_category"].isna().all()

    first_two_response_ids = full.relationship_ledger.loc[
        (full.relationship_ledger["evidence_family"] == "ACTUAL_FLOW_RESPONSE")
        & (full.relationship_ledger["observed_position"].isin([0, 1])),
        "relationship_id",
    ]
    first_two_counts = full.relationship_sources[
        full.relationship_sources["relationship_id"].isin(first_two_response_ids)
        & (
            full.relationship_sources["source_feature_name"]
            == "opposed_response_history_count"
        )
    ]["source_value_integer"].tolist()
    assert first_two_counts == [first_count, second_count]

    truncated = engine.analyze(
        evidence.iloc[:2].copy(), manifest.copy(deep=True)
    )
    _assert_result_prefix(full, truncated, 2)

    future_flow = actual_flow_surface([100.0, 101.0, 101.0, 102.0])
    future_flow["actual_absorption_evidence"] = [0.5, 0.5, 0.5, 0.5]
    future_flow["opposed_response_percentile"] = [0.25, 0.25, 0.25, 0.25]
    future_flow["absorbed_aggression_side"] = pd.Series(
        ["BUY", "BUY", "BUY", "BUY"], dtype="string"
    )
    future_flow["opposed_response_history_count"] = pd.Series(
        [first_count, second_count, second_count, second_count], dtype="int64"
    )
    future_structure = structural_source(
        ["UP_STRUCTURE"] * 4,
        ["BOS_UP", "NONE", "NONE", "NONE"],
    )
    future_source = pd.concat(
        [
            future_structure,
            future_flow.drop(columns=["close", "buy_volume", "sell_volume"]),
        ],
        axis=1,
    )
    future_evidence, future_manifest = evidence_from_source(future_source, cfg)
    appended = engine.analyze(future_evidence, future_manifest)
    _assert_result_prefix(full, appended, len(source))


def test_boolean_source_provenance_uses_nullable_boolean_only():
    source = add_multiscale(
        structural_source(
            ["UP_STRUCTURE", "UP_STRUCTURE"], ["BOS_UP", "NONE"]
        ),
        [0.5, 0.5],
    )
    source["directional_conflict"] = pd.Series([False, True], dtype="bool")
    result = run(source, config(multiscale=True))
    links = result.relationship_sources[
        result.relationship_sources["source_feature_name"]
        == "directional_conflict"
    ]
    assert str(result.relationship_sources["source_value_boolean"].dtype) == "boolean"
    assert links["source_value_boolean"].tolist() == [False, True]
    assert links["source_value_float"].isna().all()
    assert links["source_value_integer"].isna().all()
    assert links["source_value_category"].isna().all()


# =====================================================================
# EXACT PERFORMANCE V2 PATCH-3 gates
# Differential old-vs-new against the verbatim pre-patch reference copy
# (tests/_patch_reference_src/narrative_pre.py, sha256-pinned), prebound
# value identity, causality (prefix + future suffix), and a row-alignment
# mutation proof.
# =====================================================================

import hashlib
import importlib.util
import sys
import types
from pathlib import Path


_NARRATIVE_REF_PATH = (
    Path(__file__).resolve().parent
    / "_patch_reference_src"
    / "narrative_pre.py"
)

# Recorded pre-patch sha256 of src/trading_system/decision/narrative.py
# (identical bytes to the reference snapshot).
_PRE_PATCH_NARRATIVE_SHA256 = (
    "c9f8c751e62acc8e6d9e6d636f50d5d8f98e59aec6c98399073509728dc118e0"
)


def _load_reference_narrative():
    spec = importlib.util.spec_from_file_location(
        "_patch_ref_narrative", _NARRATIVE_REF_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REF_NARRATIVE = _load_reference_narrative()

_RESULT_FRAME_FIELDS = (
    "narrative_surface",
    "observation_ledger",
    "active_hypotheses",
    "hypothesis_ledger",
    "relationship_ledger",
    "relationship_sources",
    "narrative_manifest",
)


def test_patch_v2_narrative_reference_snapshot_is_pinned():
    assert _NARRATIVE_REF_PATH.exists()
    digest = hashlib.sha256(_NARRATIVE_REF_PATH.read_bytes()).hexdigest()
    assert digest == _PRE_PATCH_NARRATIVE_SHA256, (
        "tests/_patch_reference_src/narrative_pre.py must remain the verbatim "
        "pre-patch snapshot of src/trading_system/decision/narrative.py"
    )


def _narrative_fixture_cases():
    cases = {}

    states = ["UNDEFINED", "UP_STRUCTURE", "UP_STRUCTURE", "MIXED",
              "DOWN_STRUCTURE", "DOWN_STRUCTURE", "UP_STRUCTURE"]
    events = ["NONE", "BOS_UP", "NONE", "NONE", "BOS_DOWN", "NONE", "BOS_UP"]
    source = structural_source(states, events)
    cases["structure_only"] = (source, config())

    rich = add_multiscale(
        structural_source(states, events),
        [0.2, 0.5, -0.4, 0.0, -0.8, -0.3, 0.6],
    )
    rich = add_range(rich, [0.2, 0.4, 0.6, 0.5, 0.8, 0.3, 0.1])
    cases["structure_multiscale_range"] = (rich, config(multiscale=True, dealing_range=True))

    flow_source = structural_source(states, events)
    flow = actual_flow_surface([100.0, 101.0, 102.0, 103.0, 102.0, 101.0, 102.0])
    flow_source = pd.concat(
        [flow_source, flow.drop(columns=["close", "buy_volume", "sell_volume"])],
        axis=1,
    )
    cases["with_actual_flow"] = (flow_source, config(order_flow_mode=OrderFlowEvidenceMode.ACTUAL))

    return cases


def _assert_results_identical(got, ref, label):
    for field in _RESULT_FRAME_FIELDS:
        pd.testing.assert_frame_equal(
            getattr(got, field), getattr(ref, field),
            check_exact=True, check_dtype=True,
        )


def test_patch_v2_narrative_differential_exact_battery():
    for label, (source, cfg) in _narrative_fixture_cases().items():
        evidence, manifest = evidence_from_source(source, cfg)
        got = CausalMarketNarrativeEngine().analyze(evidence.copy(), manifest.copy())
        ref = REF_NARRATIVE.CausalMarketNarrativeEngine().analyze(
            evidence.copy(), manifest.copy()
        )
        _assert_results_identical(got, ref, label)
        assert not got.hypothesis_ledger.empty or label == "structure_only"


def test_patch_v2_value_prebound_matches_value_exactly():
    source, cfg = _narrative_fixture_cases()["structure_multiscale_range"]
    evidence, manifest = evidence_from_source(source, cfg)
    engine = CausalMarketNarrativeEngine()
    manifest_maps, _ = engine._manifest_maps(manifest)
    bound = {
        name: evidence[str(spec["output_column"])]
        for name, spec in manifest_maps.items()
    }
    names = list(manifest_maps) + ["not_a_registered_feature"]
    for i in range(len(evidence)):
        for name in names:
            got_value, got_availability, got_spec = engine._value_prebound(
                bound, manifest_maps, name, i
            )
            ref_value, ref_availability, ref_spec = engine._value(
                evidence, manifest_maps, name, i
            )
            assert got_availability == ref_availability, (name, i)
            assert (got_spec is ref_spec) or (
                got_spec is not None
                and ref_spec is not None
                and got_spec == ref_spec
            ), (name, i)
            if got_value is None or ref_value is None:
                assert got_value is ref_value, (name, i)
            else:
                same = (pd.isna(got_value) and pd.isna(ref_value)) or (
                    type(got_value) is type(ref_value)
                    and (
                        (not pd.isna(got_value) and got_value == ref_value)
                        or (pd.isna(got_value) and pd.isna(ref_value))
                    )
                )
                assert same, (name, i, got_value, ref_value)


def test_patch_v2_narrative_causality_prefix_and_future_suffix():
    source, cfg = _narrative_fixture_cases()["structure_multiscale_range"]
    evidence, manifest = evidence_from_source(source, cfg)
    engine = CausalMarketNarrativeEngine()
    full = engine.analyze(evidence, manifest)
    n = len(evidence)
    for split_at in (1, 2, 3, 5, n - 1):
        truncated = engine.analyze(evidence.iloc[:split_at], manifest)
        _assert_result_prefix(full, truncated, split_at)

    # Future suffix mutation: outputs up to T must be untouched.
    mutated = _mutate_future_rows(evidence, 3)
    mutated_result = engine.analyze(mutated, manifest)
    _assert_result_prefix(full, mutated_result, 3)


def _mutate_future_rows(evidence, split_at):
    mutated = evidence.copy()
    rng = np.random.default_rng(13)
    for column in mutated.columns:
        position = mutated.columns.get_loc(column)
        future = mutated.iloc[split_at:, position]
        if pd.api.types.is_float_dtype(future):
            mutated.iloc[split_at:, position] = future.to_numpy() * 3.0 + 17.0
        elif pd.api.types.is_integer_dtype(future):
            mutated.iloc[split_at:, position] = future.to_numpy() + 3
        elif pd.api.types.is_bool_dtype(future):
            mutated.iloc[split_at:, position] = ~future.to_numpy()
        else:
            # Keep categorical domain valid: reverse the future block.
            values = future.to_numpy()
            mutated.iloc[split_at:, position] = values[::-1]
    return mutated


def _exec_mutated_narrative(mutate, module_name):
    source = Path("src/trading_system/decision/narrative.py").read_text(encoding="utf-8")
    mutated_source = mutate(source)
    assert mutated_source != source, "mutation did not apply"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    exec(compile(mutated_source, module_name, "exec"), module.__dict__)
    return module


def test_patch_v2_mutation_narrative_row_alignment_break_is_detected():
    def mutate(source):
        broken = source.replace(
            "        value = columns[name].iloc[i]\n",
            "        value = columns[name].iloc[i - 1] if i else columns[name].iloc[i]\n",
        )
        return broken

    broken_module = _exec_mutated_narrative(mutate, "_mutated_narrative_alignment")
    source, cfg = _narrative_fixture_cases()["structure_multiscale_range"]
    evidence, manifest = evidence_from_source(source, cfg)
    broken_result = broken_module.CausalMarketNarrativeEngine().analyze(
        evidence.copy(), manifest.copy()
    )
    ref = REF_NARRATIVE.CausalMarketNarrativeEngine().analyze(
        evidence.copy(), manifest.copy()
    )
    differences = 0
    for field in _RESULT_FRAME_FIELDS:
        got_frame = getattr(broken_result, field)
        ref_frame = getattr(ref, field)
        try:
            pd.testing.assert_frame_equal(got_frame, ref_frame, check_exact=True)
        except AssertionError:
            differences += 1
    assert differences > 0, (
        "narrative row-alignment mutation must be detected by the differential "
        "battery"
    )

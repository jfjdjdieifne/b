import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import CausalMarketNarrativeEngine
from trading_system.research.information_time import (
    InformationPhase,
    PositionalTimelineAdapter,
    TimeIndexedTimelineAdapter,
)
from trading_system.research.visibility import (
    AsOfVisibilityProjector,
    FrozenDecisionSnapshotBundle,
    ProjectionContract,
    VisibleAsOfBundle,
    VisibilityProjectionError,
    VisibilitySchemaError,
    visibility_contract_manifest,
)


class PayloadSentinel:
    def __init__(self):
        self.touches = 0

    def _fail(self):
        self.touches += 1
        raise AssertionError("future semantic payload was accessed")

    def __bool__(self):
        return self._fail()

    def __eq__(self, other):
        return self._fail()

    def __float__(self):
        return self._fail()

    def __str__(self):
        return self._fail()


def _int_series(values):
    return pd.Series(pd.array(values, dtype="Int64"))


def certified_feature_manifest(**overrides):
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
    return CausalEvidenceVectorEngine(
        config=EvidenceVectorConfig(**values)
    ).manifest()


def make_bundle(n=5, index=None):
    if index is None:
        index = pd.RangeIndex(n)
    market = pd.DataFrame(
        {
            "open": np.arange(n, dtype=float) + 100.0,
            "high": np.arange(n, dtype=float) + 101.0,
            "low": np.arange(n, dtype=float) + 99.0,
            "close": np.arange(n, dtype=float) + 100.5,
            "semantic_payload": pd.Series(
                [f"market-{i}" for i in range(n)], index=index, dtype=object
            ),
        },
        index=index,
    )
    evidence = pd.DataFrame(
        {
            "ev__semantic": pd.Series(
                [f"evidence-{i}" for i in range(n)], index=index, dtype=object
            )
        },
        index=index,
    )
    narrative = pd.DataFrame(
        {
            "nar__semantic": pd.Series(
                [f"narrative-{i}" for i in range(n)], index=index, dtype=object
            )
        },
        index=index,
    )
    observation_positions = [position for position in (0, 2, 3, 6) if position < n]
    observation = pd.DataFrame(
        {
            "observation_id": pd.array(range(len(observation_positions)), dtype="Int64"),
            "observed_position": pd.array(observation_positions, dtype="Int64"),
            "same_row_batch_id": pd.array(observation_positions, dtype="Int64"),
            "serialization_order": pd.array(
                range(len(observation_positions)), dtype="Int64"
            ),
            "semantic_payload": pd.Series(
                [f"observation-{p}" for p in observation_positions], dtype=object
            ),
        }
    )
    hypothesis_positions = [position for position in (0, 2, 4, 6) if position < n]
    hypothesis = pd.DataFrame(
        {
            "ledger_event_id": pd.array(range(len(hypothesis_positions)), dtype="Int64"),
            "event_position": pd.array(hypothesis_positions, dtype="Int64"),
            "same_row_batch_id": pd.array(hypothesis_positions, dtype="Int64"),
            "serialization_order": pd.array(
                range(len(hypothesis_positions)), dtype="Int64"
            ),
            "semantic_payload": pd.Series(
                [f"hypothesis-{p}" for p in hypothesis_positions], dtype=object
            ),
        }
    )
    relationship_positions = [position for position in (0, 2, 3, 4, 6) if position < n]
    relationship_ids = [10 + i for i in range(len(relationship_positions))]
    relationship = pd.DataFrame(
        {
            "relationship_id": pd.array(relationship_ids, dtype="Int64"),
            "observed_position": pd.array(relationship_positions, dtype="Int64"),
            "same_row_batch_id": pd.array(relationship_positions, dtype="Int64"),
            "serialization_order": pd.array(
                range(len(relationship_positions)), dtype="Int64"
            ),
            "semantic_payload": pd.Series(
                [f"relationship-{p}" for p in relationship_positions], dtype=object
            ),
        }
    )
    relationship_sources = pd.DataFrame(
        {
            "relationship_id": pd.array(relationship_ids, dtype="Int64"),
            "source_feature_name": pd.array(
                [f"source-{i}" for i in relationship_ids], dtype="string"
            ),
            "semantic_payload": pd.Series(
                [f"source-payload-{i}" for i in relationship_ids], dtype=object
            ),
        }
    )
    feature_manifest = certified_feature_manifest()
    narrative_manifest = CausalMarketNarrativeEngine.narrative_manifest()
    return FrozenDecisionSnapshotBundle(
        timeline_id="timeline",
        evidence_df=evidence,
        feature_manifest=feature_manifest,
        narrative_surface=narrative,
        observation_ledger=observation,
        hypothesis_ledger=hypothesis,
        relationship_ledger=relationship,
        relationship_sources=relationship_sources,
        narrative_manifest=narrative_manifest,
        market_frame=market,
    )


def truncate_bundle(bundle, last_position):
    row_count = last_position + 1
    relationship = bundle.relationship_ledger[
        bundle.relationship_ledger["observed_position"] <= last_position
    ].reset_index(drop=True)
    relationship_ids = set(relationship["relationship_id"].tolist())
    return FrozenDecisionSnapshotBundle(
        timeline_id=bundle.timeline_id,
        evidence_df=bundle.evidence_df.iloc[:row_count].copy(deep=True),
        feature_manifest=bundle.feature_manifest.copy(deep=True),
        narrative_surface=bundle.narrative_surface.iloc[:row_count].copy(deep=True),
        observation_ledger=bundle.observation_ledger[
            bundle.observation_ledger["observed_position"] <= last_position
        ].reset_index(drop=True),
        hypothesis_ledger=bundle.hypothesis_ledger[
            bundle.hypothesis_ledger["event_position"] <= last_position
        ].reset_index(drop=True),
        relationship_ledger=relationship,
        relationship_sources=bundle.relationship_sources[
            bundle.relationship_sources["relationship_id"].isin(relationship_ids)
        ].reset_index(drop=True),
        narrative_manifest=bundle.narrative_manifest.copy(deep=True),
        market_frame=bundle.market_frame.iloc[:row_count].copy(deep=True),
    )


def assert_visible_equal(left, right):
    assert left.timeline_id == right.timeline_id
    assert left.research_as_of == right.research_as_of
    assert left.adapter_version == right.adapter_version
    assert left.visibility_contract_version == right.visibility_contract_version
    for name in (
        "evidence_df",
        "feature_manifest",
        "narrative_surface",
        "observation_ledger",
        "hypothesis_ledger",
        "relationship_ledger",
        "relationship_sources",
        "narrative_manifest",
        "market_frame",
    ):
        pd.testing.assert_frame_equal(
            getattr(left, name), getattr(right, name), check_exact=True
        )


def projector_and_asof(bundle, position=2, phase=InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE, sequence=0):
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    projector = AsOfVisibilityProjector(adapter=adapter)
    asof = adapter.key_for_position(
        bundle.market_frame.index, position, phase, sequence
    )
    return projector, asof


def test_project_returns_only_visible_rows_and_excludes_final_active_state():
    bundle = make_bundle()
    projector, asof = projector_and_asof(bundle)
    visible = projector.project(bundle, asof)
    assert isinstance(visible, VisibleAsOfBundle)
    assert visible.evidence_df.index.tolist() == [0, 1, 2]
    assert visible.narrative_surface.index.tolist() == [0, 1, 2]
    assert visible.market_frame.index.tolist() == [0, 1, 2]
    assert visible.observation_ledger["observed_position"].tolist() == [0, 2]
    assert visible.hypothesis_ledger["event_position"].tolist() == [0, 2]
    assert visible.relationship_ledger["observed_position"].tolist() == [0, 2]
    assert visible.relationship_sources["relationship_id"].tolist() == [10, 11]
    assert "active_hypotheses" not in {field.name for field in fields(visible)}


def test_exact_phase_and_sequence_boundaries():
    bundle = make_bundle()
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    projector = AsOfVisibilityProjector(adapter=adapter)
    completed_0 = adapter.key_for_position(
        bundle.market_frame.index,
        2,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        0,
    )
    at_market = projector.project(bundle, completed_0)
    assert at_market.market_frame.index.tolist() == [0, 1, 2]
    assert at_market.evidence_df.index.tolist() == [0, 1]
    assert 2 not in at_market.observation_ledger["observed_position"].tolist()

    completed_1 = adapter.key_for_position(
        bundle.market_frame.index,
        2,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    at_analytics = projector.project(bundle, completed_1)
    assert at_analytics.evidence_df.index.tolist() == [0, 1, 2]
    assert 2 in at_analytics.observation_ledger["observed_position"].tolist()

    preclose = adapter.key_for_position(
        bundle.market_frame.index, 2, InformationPhase.BAR_PRE_CLOSE, 999
    )
    before_close = projector.project(bundle, preclose)
    assert before_close.market_frame.index.tolist() == [0, 1]
    assert before_close.evidence_df.index.tolist() == [0, 1]


def test_atomic_same_row_analytical_visibility_ignores_serialization_order():
    bundle = make_bundle()
    observation = bundle.observation_ledger.copy(deep=True)
    hypothesis = bundle.hypothesis_ledger.copy(deep=True)
    relationship = bundle.relationship_ledger.copy(deep=True)
    observation.loc[observation["observed_position"] == 2, "serialization_order"] = 5
    relationship.loc[
        relationship["observed_position"] == 2, "serialization_order"
    ] = 100
    hypothesis.loc[hypothesis["event_position"] == 2, "serialization_order"] = 200
    bundle = replace(
        bundle,
        observation_ledger=observation,
        hypothesis_ledger=hypothesis,
        relationship_ledger=relationship,
    )
    adapter = PositionalTimelineAdapter(bundle.timeline_id)
    projector = AsOfVisibilityProjector(adapter=adapter)

    before_analytics = adapter.key_for_position(
        bundle.market_frame.index,
        2,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        0,
    )
    before = projector.project(bundle, before_analytics)
    assert 2 not in before.observation_ledger["observed_position"].tolist()
    assert 2 not in before.relationship_ledger["observed_position"].tolist()
    assert 2 not in before.hypothesis_ledger["event_position"].tolist()

    at_analytics = adapter.key_for_position(
        bundle.market_frame.index,
        2,
        InformationPhase.COMPLETED_ROW_AVAILABLE,
        1,
    )
    visible = projector.project(bundle, at_analytics)
    assert visible.observation_ledger.loc[
        visible.observation_ledger["observed_position"] == 2,
        "serialization_order",
    ].tolist() == [5]
    assert visible.relationship_ledger.loc[
        visible.relationship_ledger["observed_position"] == 2,
        "serialization_order",
    ].tolist() == [100]
    assert visible.hypothesis_ledger.loc[
        visible.hypothesis_ledger["event_position"] == 2,
        "serialization_order",
    ].tolist() == [200]


def test_full_vs_physically_truncated_equivalence_all_tables():
    full = make_bundle()
    truncated = truncate_bundle(full, 2)
    full_projector, full_asof = projector_and_asof(full)
    truncated_projector, truncated_asof = projector_and_asof(truncated)
    full_visible = full_projector.project(full, full_asof)
    truncated_visible = truncated_projector.project(truncated, truncated_asof)
    assert_visible_equal(full_visible, truncated_visible)


def test_future_semantic_mutation_is_exactly_invariant():
    original = make_bundle()
    projector, asof = projector_and_asof(original)
    expected = projector.project(original, asof)
    mutated = make_bundle()
    mutated.evidence_df.iloc[3:, 0] = ["MUTATED-E3", "MUTATED-E4"]
    mutated.narrative_surface.iloc[3:, 0] = ["MUTATED-N3", "MUTATED-N4"]
    mutated.market_frame.iloc[3:, :] = -999.0
    mutated.observation_ledger.loc[
        mutated.observation_ledger["observed_position"] > 2, "semantic_payload"
    ] = "MUTATED-OBS"
    mutated.hypothesis_ledger.loc[
        mutated.hypothesis_ledger["event_position"] > 2, "semantic_payload"
    ] = "MUTATED-HYP"
    future_relationships = mutated.relationship_ledger["observed_position"] > 2
    future_ids = set(
        mutated.relationship_ledger.loc[future_relationships, "relationship_id"].tolist()
    )
    mutated.relationship_ledger.loc[future_relationships, "semantic_payload"] = "MUTATED-REL"
    mutated.relationship_sources.loc[
        mutated.relationship_sources["relationship_id"].isin(future_ids),
        "semantic_payload",
    ] = "MUTATED-SOURCE"
    actual = projector.project(mutated, asof)
    assert_visible_equal(expected, actual)


def test_future_append_is_exactly_invariant():
    original = make_bundle(5)
    appended = make_bundle(7)
    original_projector, original_asof = projector_and_asof(original)
    appended_projector, appended_asof = projector_and_asof(appended)
    assert_visible_equal(
        original_projector.project(original, original_asof),
        appended_projector.project(appended, appended_asof),
    )


def test_projection_does_not_access_future_semantic_payload():
    bundle = make_bundle()
    sentinels = [PayloadSentinel() for _ in range(7)]
    bundle.evidence_df.iloc[3, 0] = sentinels[0]
    bundle.narrative_surface.iloc[3, 0] = sentinels[1]
    bundle.market_frame.iloc[3, bundle.market_frame.columns.get_loc("semantic_payload")] = sentinels[2]
    bundle.observation_ledger.loc[
        bundle.observation_ledger["observed_position"] == 3, "semantic_payload"
    ] = sentinels[3]
    bundle.hypothesis_ledger.loc[
        bundle.hypothesis_ledger["event_position"] == 4, "semantic_payload"
    ] = sentinels[4]
    bundle.relationship_ledger.loc[
        bundle.relationship_ledger["observed_position"] == 3, "semantic_payload"
    ] = sentinels[5]
    future_id = int(
        bundle.relationship_ledger.loc[
            bundle.relationship_ledger["observed_position"] == 3,
            "relationship_id",
        ].iloc[0]
    )
    bundle.relationship_sources.loc[
        bundle.relationship_sources["relationship_id"] == future_id,
        "semantic_payload",
    ] = sentinels[6]
    projector, asof = projector_and_asof(bundle)
    visible = projector.project(bundle, asof)
    assert len(visible.evidence_df) == 3
    assert [sentinel.touches for sentinel in sentinels] == [0] * len(sentinels)


def test_parent_child_filtering_and_orphan_rejection():
    bundle = make_bundle()
    projector, asof = projector_and_asof(bundle)
    visible = projector.project(bundle, asof)
    assert set(visible.relationship_sources["relationship_id"]) == set(
        visible.relationship_ledger["relationship_id"]
    )
    orphan = make_bundle()
    orphan.relationship_sources.loc[len(orphan.relationship_sources)] = [
        999,
        "orphan",
        "payload",
    ]
    with pytest.raises(VisibilitySchemaError, match="orphan"):
        projector.project(orphan, asof)


def test_projection_input_and_output_are_independent_and_config_frozen():
    bundle = make_bundle()
    before = bundle.evidence_df.copy(deep=True)
    projector, asof = projector_and_asof(bundle)
    visible = projector.project(bundle, asof)
    pd.testing.assert_frame_equal(bundle.evidence_df, before, check_exact=True)
    visible.evidence_df.iloc[0, 0] = "OUTPUT-MUTATION"
    assert bundle.evidence_df.iloc[0, 0] == "evidence-0"
    with pytest.raises(FrozenInstanceError):
        projector._contract.market_row_sequence = 5


def test_same_instance_a_a_a_b_a_and_fresh_determinism():
    bundle_a = make_bundle(5)
    bundle_b = make_bundle(4)
    projector, asof_a = projector_and_asof(bundle_a)
    first = projector.project(bundle_a, asof_a)
    repeated = projector.project(bundle_a, asof_a)
    _, asof_b = projector_and_asof(bundle_b, position=1)
    projector.project(bundle_b, asof_b)
    after_b = projector.project(bundle_a, asof_a)
    fresh = AsOfVisibilityProjector(
        adapter=PositionalTimelineAdapter(bundle_a.timeline_id)
    ).project(bundle_a, asof_a)
    assert_visible_equal(first, repeated)
    assert_visible_equal(first, after_b)
    assert_visible_equal(first, fresh)


def test_explicit_asof_and_timeline_required():
    bundle = make_bundle()
    projector, asof = projector_and_asof(bundle)
    with pytest.raises(VisibilityProjectionError, match="InformationKey"):
        projector.project(bundle, 2)
    wrong_adapter = PositionalTimelineAdapter("other")
    wrong_asof = wrong_adapter.key_for_position(
        bundle.market_frame.index,
        2,
        InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
    )
    with pytest.raises(VisibilityProjectionError, match="invalid research as-of"):
        projector.project(bundle, wrong_asof)
    wrong_bundle = replace(bundle, timeline_id="other")
    with pytest.raises(VisibilitySchemaError, match="timeline"):
        projector.project(wrong_bundle, asof)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_projection_column", "missing projection columns"),
        ("duplicate_columns", "invalid observation_ledger"),
        ("duplicate_relationship_id", "duplicate relationship_ledger identity"),
        ("invalid_position", "position outside"),
        ("wrong_position_dtype", "must be nonmissing integer"),
        ("negative_serialization", "must be nonnegative"),
        ("batch_mismatch", "same-row batch mismatch"),
        ("index_identity", "index identity mismatch"),
    ],
)
def test_schema_and_projection_metadata_rejections(mutation, message):
    bundle = make_bundle()
    if mutation == "missing_projection_column":
        bundle = replace(
            bundle,
            observation_ledger=bundle.observation_ledger.drop(
                columns=["observed_position"]
            ),
        )
    elif mutation == "duplicate_columns":
        duplicate = pd.concat(
            [bundle.observation_ledger, bundle.observation_ledger.iloc[:, [0]]],
            axis=1,
        )
        bundle = replace(bundle, observation_ledger=duplicate)
    elif mutation == "duplicate_relationship_id":
        relation = bundle.relationship_ledger.copy(deep=True)
        relation.loc[1, "relationship_id"] = relation.loc[0, "relationship_id"]
        bundle = replace(bundle, relationship_ledger=relation)
    elif mutation == "invalid_position":
        observation = bundle.observation_ledger.copy(deep=True)
        observation.loc[0, "observed_position"] = len(bundle.market_frame)
        observation.loc[0, "same_row_batch_id"] = len(bundle.market_frame)
        bundle = replace(bundle, observation_ledger=observation)
    elif mutation == "wrong_position_dtype":
        observation = bundle.observation_ledger.copy(deep=True)
        observation["observed_position"] = observation["observed_position"].astype(float)
        bundle = replace(bundle, observation_ledger=observation)
    elif mutation == "negative_serialization":
        observation = bundle.observation_ledger.copy(deep=True)
        observation.loc[0, "serialization_order"] = -1
        bundle = replace(bundle, observation_ledger=observation)
    elif mutation == "batch_mismatch":
        observation = bundle.observation_ledger.copy(deep=True)
        observation.loc[0, "same_row_batch_id"] = 1
        bundle = replace(bundle, observation_ledger=observation)
    elif mutation == "index_identity":
        market = bundle.market_frame.copy(deep=True)
        market.index = pd.RangeIndex(1, len(market) + 1)
        bundle = replace(bundle, market_frame=market)
    projector = AsOfVisibilityProjector(adapter=PositionalTimelineAdapter("timeline"))
    asof = PositionalTimelineAdapter("timeline").key_for_position(
        pd.RangeIndex(5), 2, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE
    )
    with pytest.raises(VisibilitySchemaError, match=message):
        projector.project(bundle, asof)


def test_time_indexed_projection_timezone_dst_and_irregular_rows():
    utc = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-10-26T00:30:00Z"),
            pd.Timestamp("2025-10-26T01:30:00Z"),
            pd.Timestamp("2025-10-26T04:45:00Z"),
            pd.Timestamp("2025-10-27T10:00:00Z"),
            pd.Timestamp("2025-11-02T12:00:00Z"),
        ]
    )
    local = utc.tz_convert("Europe/Vilnius")
    bundle = make_bundle(5, index=local)
    adapter = TimeIndexedTimelineAdapter(bundle.timeline_id)
    projector = AsOfVisibilityProjector(adapter=adapter)
    asof = adapter.key_for_position(
        local, 2, InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE
    )
    visible = projector.project(bundle, asof)
    pd.testing.assert_index_equal(visible.market_frame.index, local[:3], exact=True)
    assert asof.event_time_utc == utc[2]


@pytest.mark.parametrize(
    ("column", "forged_value"),
    [
        ("source_mode", "PROXY"),
        ("epistemic_status", "FACTUAL"),
        ("expected_domain", "category_side"),
        ("event_local", False),
        ("output_column", "ev__forged_break_event"),
    ],
)
def test_forged_feature_manifest_metadata_rejected(column, forged_value):
    bundle = make_bundle()
    forged = bundle.feature_manifest.copy(deep=True)
    forged.loc[
        forged["feature_name"] == "structural_break_event", column
    ] = forged_value
    projector, asof = projector_and_asof(bundle)
    with pytest.raises(VisibilitySchemaError, match="static manifest identity"):
        projector.project(replace(bundle, feature_manifest=forged), asof)


def test_nonscalar_manifest_payload_translates_to_visibility_schema_error():
    bundle = make_bundle()
    forged = bundle.feature_manifest.copy(deep=True)
    forged.at[0, "source_module"] = ["FORGED"]
    projector, asof = projector_and_asof(bundle)
    with pytest.raises(VisibilitySchemaError, match="static manifest identity"):
        projector.project(replace(bundle, feature_manifest=forged), asof)


def test_incomplete_and_extra_feature_manifest_rows_rejected():
    bundle = make_bundle()
    projector, asof = projector_and_asof(bundle)
    incomplete = bundle.feature_manifest[
        bundle.feature_manifest["feature_name"] != "structural_break_event"
    ].reset_index(drop=True)
    with pytest.raises(VisibilitySchemaError, match="static manifest identity"):
        projector.project(replace(bundle, feature_manifest=incomplete), asof)

    extra = bundle.feature_manifest.copy(deep=True)
    forged_row = extra.iloc[[0]].copy(deep=True)
    forged_row["feature_name"] = "uncertified_extra"
    forged_row["output_column"] = "ev__uncertified_extra"
    extra = pd.concat([extra, forged_row], ignore_index=True)
    with pytest.raises(VisibilitySchemaError, match="static manifest identity"):
        projector.project(replace(bundle, feature_manifest=extra), asof)


@pytest.mark.parametrize(
    "feature_manifest",
    [
        certified_feature_manifest(),
        certified_feature_manifest(multiscale=True),
        certified_feature_manifest(
            order_flow_mode=OrderFlowEvidenceMode.ACTUAL
        ),
        certified_feature_manifest(
            order_flow_mode=OrderFlowEvidenceMode.PROXY
        ),
        certified_feature_manifest(structure=False, liquidity=True),
        certified_feature_manifest(structure=False),
    ],
)
def test_legitimate_optional_feature_group_configurations_accepted(feature_manifest):
    bundle = make_bundle()
    bundle = replace(bundle, feature_manifest=feature_manifest.copy(deep=True))
    projector, asof = projector_and_asof(bundle)
    visible = projector.project(bundle, asof)
    pd.testing.assert_frame_equal(
        visible.feature_manifest, feature_manifest, check_exact=True
    )


def test_actual_and_proxy_feature_groups_cannot_coexist():
    bundle = make_bundle()
    actual = certified_feature_manifest(
        structure=False, order_flow_mode=OrderFlowEvidenceMode.ACTUAL
    )
    proxy = certified_feature_manifest(
        structure=False, order_flow_mode=OrderFlowEvidenceMode.PROXY
    )
    mixed = pd.concat([actual, proxy], ignore_index=True)
    projector, asof = projector_and_asof(bundle)
    with pytest.raises(VisibilitySchemaError, match="static manifest identity"):
        projector.project(replace(bundle, feature_manifest=mixed), asof)


@pytest.mark.parametrize(
    "mutation",
    (
        "hypothesis_definition",
        "bearing_vocabulary",
        "lifecycle_contract",
        "same_row_semantics",
        "extra_row",
        "removed_row",
    ),
)
def test_forged_narrative_manifest_rejected(mutation):
    bundle = make_bundle()
    forged = bundle.narrative_manifest.copy(deep=True)
    if mutation == "hypothesis_definition":
        row = forged["record_type"] == "HYPOTHESIS_DEFINITION"
        forged.loc[row.idxmax(), "foundation_clause"] = "FORGED_FOUNDATION"
    elif mutation == "bearing_vocabulary":
        row = forged["record_type"] == "RELATIONSHIP_BEARING"
        forged.loc[row.idxmax(), "name"] = "FORGED_BEARING"
    elif mutation == "lifecycle_contract":
        row = forged["record_type"] == "HYPOTHESIS_DEFINITION"
        forged.loc[row.idxmax(), "contradiction_contract"] = "FORGED_LIFECYCLE"
    elif mutation == "same_row_semantics":
        forged.loc[0, "same_row_semantics"] = "FORGED_ORDER"
    elif mutation == "extra_row":
        forged = pd.concat([forged, forged.iloc[[0]]], ignore_index=True)
    elif mutation == "removed_row":
        forged = forged.iloc[:-1].copy()
    projector, asof = projector_and_asof(bundle)
    with pytest.raises(VisibilitySchemaError, match="static manifest identity"):
        projector.project(replace(bundle, narrative_manifest=forged), asof)


def test_manifest_validation_is_independent_of_future_payload_and_asof():
    bundle = make_bundle()
    projector, early_asof = projector_and_asof(bundle, position=1)
    early = projector.project(bundle, early_asof)
    mutated = make_bundle()
    mutated.evidence_df.iloc[2:, 0] = "FUTURE-EVIDENCE-MUTATION"
    mutated.market_frame.iloc[2:, :] = -123.0
    actual = projector.project(mutated, early_asof)
    pd.testing.assert_frame_equal(
        early.feature_manifest, actual.feature_manifest, check_exact=True
    )
    pd.testing.assert_frame_equal(
        early.narrative_manifest, actual.narrative_manifest, check_exact=True
    )


def test_visibility_contract_manifest_is_static_minimal_and_outcome_free():
    first = visibility_contract_manifest()
    second = visibility_contract_manifest()
    pd.testing.assert_frame_equal(first, second, check_exact=True)
    active = first[first["name"] == "active_hypotheses"].iloc[0]
    assert active["value"] == "EXCLUDED_NON_HISTORICAL_FINAL_STATE"
    text = " ".join(first.astype(str).to_numpy().ravel()).lower()
    for forbidden in (
        "outcome_mature",
        "right_censored",
        "excursion",
        "pnl",
        "probability",
        "score",
    ):
        assert forbidden not in text


def test_public_visible_schema_contains_no_outcome_fields():
    names = {field.name for field in fields(VisibleAsOfBundle)}
    forbidden = {
        "outcome_mature",
        "terminal_outcome",
        "right_censored",
        "final_outcome_known_at",
        "favorable_excursion",
        "adverse_excursion",
        "pnl",
        "target",
        "stop",
        "probability",
        "score",
    }
    assert names.isdisjoint(forbidden)


def test_closed_and_decision_packages_do_not_import_research():
    root = Path(__file__).resolve().parents[1] / "src" / "trading_system"
    closed_packages = (
        "audit",
        "core",
        "environment",
        "structure",
        "liquidity",
        "orderflow",
        "zones",
        "multitimeframe",
        "decision",
    )
    offenders = []
    paths = [root / "__init__.py"]
    for package in closed_packages:
        paths.extend(sorted((root / package).glob("*.py")))
    for path in paths:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name.startswith("trading_system.research") for name in names):
                offenders.append(str(path.relative_to(root.parent)))
    assert offenders == []

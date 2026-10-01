"""Independent-audit patch adversarial coverage for Module 6.2B-0 V1.2."""
from dataclasses import fields, replace
import runpy

import numpy as np
import pandas as pd
import pytest

from trading_system.reasoning.evidence_families import (
    DynamicEvidenceFamilyReasoner,
    EvidenceFamily,
    ReasoningContractError,
    ProvenanceStatus,
    reasoning_record_hash_payload,
    resolve_provenance_status,
)
from trading_system.research.hashing import canonical_sha256

# Reuse only construction/assertion helpers; this file adds independent V1.2 claims.
_helpers = runpy.run_path("tests/test_evidence_family_reasoning.py")
config = _helpers["config"]
frozen_snapshot = _helpers["frozen_snapshot"]
reasoning_snapshot = _helpers["reasoning_snapshot"]
rehash_reasoning_snapshot = _helpers["rehash_reasoning_snapshot"]
family_row = _helpers["family_row"]
FuturePayloadSentinel = _helpers["FuturePayloadSentinel"]


def _result(snapshot):
    return DynamicEvidenceFamilyReasoner().analyze(snapshot)


def _mtf_snapshot(balance: float, conflict: bool):
    frozen = frozen_snapshot(config(multiscale=True), mtf_balance=balance)
    snapshot = reasoning_snapshot(frozen)
    evidence = snapshot.evidence_row.copy(deep=True)
    evidence.loc[evidence.index[0], "ev__directional_conflict"] = conflict
    relationships = snapshot.relationship_rows.copy(deep=True)
    mtf = relationships["evidence_family"] == "MULTISCALE_STRUCTURE"
    relationships.loc[mtf, "primary_category_value"] = "CONFLICT" if conflict else pd.NA
    sources = snapshot.relationship_sources.copy(deep=True)
    mtf_id = int(relationships.loc[mtf, "relationship_id"].iloc[0])
    source_mask = (
        (sources["relationship_id"] == mtf_id)
        & (sources["source_feature_name"] == "directional_conflict")
    )
    sources.loc[source_mask, "source_value_boolean"] = conflict
    return rehash_reasoning_snapshot(
        replace(
            snapshot,
            evidence_row=evidence,
            relationship_rows=relationships,
            relationship_sources=sources,
        )
    )


def test_v1_1_final_record_hash_recomputes_from_public_contract():
    result = _result(reasoning_snapshot(frozen_snapshot(config(multiscale=True), mtf_balance=0.5)))
    for row in result.evidence_records.to_dict(orient="records"):
        expected = canonical_sha256(
            domain="EVIDENCE_RECORD_FINAL_V1_2",
            payload=reasoning_record_hash_payload(row),
        )
        assert row["record_hash"] == expected
        assert row["family_snapshot_id"] in set(result.family_snapshots["family_snapshot_id"])


def test_v1_1_information_key_and_full_output_dtypes():
    result = _result(reasoning_snapshot(frozen_snapshot()))
    assert str(result.family_snapshots["decision_deterministic_sequence"].dtype) == "Int64"
    assert str(result.family_snapshots["decision_bar_position"].dtype) == "Int64"
    assert str(result.evidence_records["primary_value_integer"].dtype) == "Int64"
    assert str(result.evidence_sources["source_value_integer"].dtype) == "Int64"
    assert str(result.evidence_records["included_for_independent_calibration"].dtype) == "boolean"
    assert str(result.evidence_records["selected_provenance_representative"].dtype) == "boolean"
    for result_field in fields(result):
        frame = getattr(result, result_field.name)
        assert isinstance(frame, pd.DataFrame)
        assert not frame.columns.has_duplicates


def test_v1_1_integer_precision_above_2_pow_53():
    snapshot = reasoning_snapshot(frozen_snapshot(config(environment=True)))
    large = 2**53 + 17
    evidence = snapshot.evidence_row.copy(deep=True)
    evidence.loc[evidence.index[0], "ev__true_range_history_count"] = large
    altered = rehash_reasoning_snapshot(replace(snapshot, evidence_row=evidence))
    result = _result(altered)
    row = result.evidence_records[
        result.evidence_records["source_record_id"] == "true_range_history_count"
    ].iloc[0]
    assert int(row.primary_value_integer) == large
    assert str(result.evidence_records["primary_value_integer"].dtype) == "Int64"


@pytest.mark.parametrize("table_name,position_column,kind", [
    ("observation_rows", "observed_position", "observation"),
    ("relationship_rows", "observed_position", "relationship"),
])
def test_v1_1_prior_rows_rejected_not_silently_ignored(table_name, position_column, kind):
    snapshot = reasoning_snapshot(frozen_snapshot())
    frame = getattr(snapshot, table_name).copy(deep=True)
    frame.loc[frame.index[0], position_column] = snapshot.decision_information_key.bar_position - 1
    frame[position_column] = pd.array(frame[position_column], dtype="Int64")
    with pytest.raises(ReasoningContractError, match=f"prior-row {kind}"):
        _result(replace(snapshot, **{table_name: frame}))


def test_v1_1_exact_same_row_is_accepted():
    snapshot = reasoning_snapshot(frozen_snapshot())
    assert snapshot.observation_rows["observed_position"].eq(snapshot.decision_information_key.bar_position).all()
    assert snapshot.relationship_rows["observed_position"].eq(snapshot.decision_information_key.bar_position).all()
    _result(snapshot)


@pytest.mark.parametrize("balance,expected_bearing", [(0.5, "ALIGNED"), (-0.5, "OPPOSITION")])
def test_v1_1_certified_mtf_conflict_is_orthogonal_to_direction(balance, expected_bearing):
    result = _result(_mtf_snapshot(balance, True))
    mtf = family_row(result, EvidenceFamily.MULTISCALE_STRUCTURE)
    assert mtf.aggregate_semantic_state == expected_bearing
    assert mtf.conflict_present
    assert mtf.aligned_present == (expected_bearing == "ALIGNED")
    assert mtf.opposition_present == (expected_bearing == "OPPOSITION")
    assert not mtf.contradiction_present


def test_v1_1_mtf_no_conflict_case():
    result = _result(_mtf_snapshot(0.5, False))
    mtf = family_row(result, EvidenceFamily.MULTISCALE_STRUCTURE)
    assert mtf.aggregate_semantic_state == "ALIGNED"
    assert not mtf.conflict_present


def test_v1_1_aggregate_policy_and_representative_policy_are_machine_readable():
    manifest = _result(reasoning_snapshot(frozen_snapshot())).reasoning_manifest
    record_types = set(manifest["record_type"])
    assert {"AGGREGATE_POLICY", "REPRESENTATIVE_POLICY", "INDEPENDENCE_POLICY", "HASH_POLICY"}.issubset(record_types)
    local = family_row(_result(reasoning_snapshot(frozen_snapshot())), EvidenceFamily.LOCAL_STRUCTURE_STATE)
    assert local.aligned_present and local.factual_present and local.mixed_present


def test_v1_2_data_availability_derivatives_are_retained_but_never_independent():
    result = _result(reasoning_snapshot(frozen_snapshot()))
    rows = result.evidence_records[
        result.evidence_records["family_name"] == EvidenceFamily.DATA_AVAILABILITY.value
    ]
    assert len(rows) == 3
    assert int(rows["included_for_independent_calibration"].sum()) == 0
    assert set(rows["independence_status"]) == {"DETERMINISTIC_DERIVATIVE"}
    assert set(rows["exclusion_reason"]) == {"DETERMINISTIC_DERIVATIVE_NOT_INDEPENDENT"}


def test_v1_2_availability_summary_exact_closed_parent_sets():
    snapshot = reasoning_snapshot(frozen_snapshot(config(environment=True)))
    result = _result(snapshot)
    edges = result.lineage_edges

    feature_count = edges[
        edges["child_contract_name"] == "ev__evidence_feature_count"
    ]
    assert set(feature_count["edge_type"]) == {"MANIFEST_UNIVERSE_DEPENDENCY"}
    assert set(feature_count["parent_contract_name"]) == {
        "6.1A::SELECTED_NON_COUNT_SUPPORT_SPECIFICATION_UNIVERSE"
    }

    available_count = edges[
        edges["child_contract_name"] == "ev__evidence_available_count"
    ]
    expected_value_parents = set(
        snapshot.feature_manifest.loc[
            snapshot.feature_manifest["semantic_type"] != "COUNT_SUPPORT",
            "feature_name",
        ].astype(str)
    )
    assert set(available_count["edge_type"]) == {"AVAILABILITY_VALUE_DEPENDENCY"}
    assert set(available_count["parent_contract_name"]) == expected_value_parents
    count_support = set(
        snapshot.feature_manifest.loc[
            snapshot.feature_manifest["semantic_type"] == "COUNT_SUPPORT",
            "feature_name",
        ].astype(str)
    )
    assert set(available_count["parent_contract_name"]).isdisjoint(count_support)

    fraction = edges[
        edges["child_contract_name"] == "ev__evidence_availability_fraction"
    ]
    assert set(fraction["edge_type"]) == {"DIRECT_DETERMINISTIC_DERIVATION"}
    assert set(fraction["parent_contract_name"]) == {
        "ev__evidence_feature_count", "ev__evidence_available_count"
    }


def test_v1_2_mtf_formula_topology_matches_closed_contract():
    result = _result(_mtf_snapshot(0.5, False))
    edges = result.lineage_edges

    def parents(child):
        selected = edges[
            (edges["family_name"] == EvidenceFamily.MULTISCALE_STRUCTURE.value)
            & (edges["child_contract_name"] == child)
        ]
        return set(selected["parent_contract_name"])

    assert parents("unavailable_scale_count") == {
        "5.2::configured_scale_count", "available_scale_count"
    }
    assert parents("availability_fraction") == {
        "5.2::configured_scale_count", "available_scale_count"
    }
    assert parents("directional_fraction") == {
        "5.2::configured_scale_count", "directional_scale_count"
    }
    assert parents("directional_consensus") == {"directional_balance"}
    assert parents("directional_conflict") == {
        "5.2::up_structure_count", "5.2::down_structure_count"
    }
    assert "directional_consensus" not in parents("directional_conflict")


def test_v1_2_mtf_records_remain_conservatively_grouped_without_independence():
    result = _result(_mtf_snapshot(0.5, False))
    rows = result.evidence_records[
        result.evidence_records["family_name"] == EvidenceFamily.MULTISCALE_STRUCTURE.value
    ]
    assert rows["independence_cluster_id"].nunique() == 1
    assert int(rows["selected_provenance_representative"].sum()) == 1
    assert int(rows["included_for_independent_calibration"].sum()) == 0


def test_v1_1_alias_cannot_escape_manifest_source_identity():
    snapshot = reasoning_snapshot(frozen_snapshot())
    sources = snapshot.relationship_sources.copy(deep=True)
    sources.loc[sources.index[0], "source_feature_name"] = "structure_state_alias"
    altered = rehash_reasoning_snapshot(replace(snapshot, relationship_sources=sources))
    with pytest.raises(ReasoningContractError, match="source-family integrity"):
        _result(altered)


def test_v1_1_nonavailable_observation_shell_is_rejected():
    snapshot = reasoning_snapshot(frozen_snapshot())
    for state in ("UNKNOWN", "NOT_APPLICABLE", "UNAVAILABLE"):
        observations = snapshot.observation_rows.copy(deep=True)
        observations.loc[observations.index[0], "availability_state"] = state
        altered = rehash_reasoning_snapshot(replace(snapshot, observation_rows=observations))
        with pytest.raises(ReasoningContractError, match="nonavailable observation"):
            _result(altered)


def test_v1_1_storage_attestation_and_semantic_identity_are_separate():
    base = reasoning_snapshot(frozen_snapshot(config(multiscale=True), mtf_balance=0.5))
    reordered = replace(
        base,
        relationship_rows=base.relationship_rows.iloc[::-1].reset_index(drop=True),
        relationship_sources=base.relationship_sources.iloc[::-1].reset_index(drop=True),
        observation_rows=base.observation_rows.iloc[::-1].reset_index(drop=True),
    )
    reordered = rehash_reasoning_snapshot(reordered)
    assert base.decision_snapshot_hash != reordered.decision_snapshot_hash
    left, right = _result(base), _result(reordered)
    assert left.family_snapshots["semantic_reasoning_hash"].iloc[0] == right.family_snapshots["semantic_reasoning_hash"].iloc[0]
    assert left.family_snapshots["snapshot_hash"].tolist() == right.family_snapshots["snapshot_hash"].tolist()
    assert left.family_snapshots["decision_snapshot_hash"].iloc[0] != right.family_snapshots["decision_snapshot_hash"].iloc[0]


def test_v1_1_genuine_semantic_change_changes_semantic_identity():
    base = reasoning_snapshot(frozen_snapshot())
    changed_rows = base.relationship_rows.copy(deep=True)
    mask = changed_rows["evidence_family"] == "LOCAL_STRUCTURE_STATE"
    changed_rows.loc[mask, "relationship_bearing"] = "DIRECTIONALLY_OPPOSES"
    changed = rehash_reasoning_snapshot(replace(base, relationship_rows=changed_rows))
    left, right = _result(base), _result(changed)
    assert left.family_snapshots["semantic_reasoning_hash"].iloc[0] != right.family_snapshots["semantic_reasoning_hash"].iloc[0]


def _pair_relation(result, left_id, right_id):
    left, right = sorted((str(left_id), str(right_id)))
    rows = result.provenance_relations[
        (result.provenance_relations["left_record_id"] == left)
        & (result.provenance_relations["right_record_id"] == right)
    ]
    assert len(rows) == 1
    return rows.iloc[0]


def test_v1_2_three_open_world_provenance_states_require_explicit_proof():
    assert resolve_provenance_status(
        certified_shared=True, certified_distinct=False
    ) is ProvenanceStatus.CERTIFIED_SHARED_PROVENANCE
    assert resolve_provenance_status(
        certified_shared=False, certified_distinct=True
    ) is ProvenanceStatus.CERTIFIED_DISTINCT_PROVENANCE
    assert resolve_provenance_status(
        certified_shared=False, certified_distinct=False
    ) is ProvenanceStatus.NOT_CERTIFIED
    with pytest.raises(ReasoningContractError, match="contradictory provenance"):
        resolve_provenance_status(certified_shared=True, certified_distinct=True)


def test_v1_2_unlinked_different_ids_and_names_are_not_certified_either_way():
    result = _result(reasoning_snapshot(frozen_snapshot(
        config(order_flow_mode=_helpers["OrderFlowEvidenceMode"].ACTUAL), delta_ratio=0.5
    )))
    records = result.evidence_records.set_index("source_record_id")
    left = records.loc["delta_ratio_percentile", "record_id"]
    right = records.loc["delta_magnitude_percentile", "record_id"]
    assert left != right
    relation = _pair_relation(result, left, right)
    assert relation.provenance_status == "NOT_CERTIFIED"
    assert relation.provenance_status != "CERTIFIED_DISTINCT_PROVENANCE"
    assert relation.provenance_status != "CERTIFIED_SHARED_PROVENANCE"
    assert relation.derivation_status == "NOT_CERTIFIED"
    assert relation.proof_contract == "NO_CERTIFYING_CONTRACT"
    cross_family = _pair_relation(
        result,
        records.loc["delta_ratio_percentile", "record_id"],
        records.loc["structure_state_after", "record_id"],
    )
    assert cross_family.provenance_status == "NOT_CERTIFIED"
    assert cross_family.proof_contract == "NO_CERTIFYING_CONTRACT"


def test_v1_2_not_certified_records_never_emit_shared_legacy_semantics():
    result = _result(reasoning_snapshot(frozen_snapshot(
        config(order_flow_mode=_helpers["OrderFlowEvidenceMode"].ACTUAL), delta_ratio=0.5
    )))
    unresolved = result.evidence_records[
        result.evidence_records["provenance_status"] == "NOT_CERTIFIED"
    ]
    legacy = (
        unresolved["independence_status"].fillna("")
        + "|" + unresolved["exclusion_reason"].fillna("")
    )
    assert not legacy.str.contains("SHARED_PROVENANCE").any()
    assert not result.evidence_records["included_for_independent_calibration"].any()


def test_v1_2_certified_shared_record_may_emit_certified_shared_exclusion():
    result = _result(reasoning_snapshot(frozen_snapshot()))
    rows = result.evidence_records[
        (result.evidence_records["provenance_status"] == "CERTIFIED_SHARED_PROVENANCE")
        & (~result.evidence_records["selected_provenance_representative"])
        & (result.evidence_records["record_kind"] != "EVIDENCE_SUMMARY")
    ]
    assert len(rows) > 0
    assert set(rows["independence_status"]) == {"CERTIFIED_SHARED_PROVENANCE"}
    assert set(rows["exclusion_reason"]) == {
        "CERTIFIED_SHARED_PROVENANCE_NOT_INDEPENDENT"
    }


def test_v1_2_co_derived_mtf_siblings_are_not_parent_child_derivatives():
    result = _result(_mtf_snapshot(0.5, False))
    records = result.evidence_records.set_index("source_record_id")
    relation = _pair_relation(
        result,
        records.loc["directional_balance", "record_id"],
        records.loc["directional_conflict", "record_id"],
    )
    assert relation.provenance_status == "CERTIFIED_SHARED_PROVENANCE"
    assert relation.derivation_status == "NOT_CERTIFIED"
    assert "CERTIFIED_COMMON_FORMULA_INPUT" in relation.proof_contract


def test_v1_2_true_direct_deterministic_parent_child_is_preserved():
    result = _result(_mtf_snapshot(0.5, False))
    records = result.evidence_records.set_index("source_record_id")
    relation = _pair_relation(
        result,
        records.loc["directional_balance", "record_id"],
        records.loc["directional_consensus", "record_id"],
    )
    assert relation.provenance_status == "NOT_CERTIFIED"
    assert relation.derivation_status == "DETERMINISTIC_DERIVATIVE"
    assert "DIRECT_DETERMINISTIC_DERIVATION" in relation.proof_contract


def test_v1_2_deterministic_ancestor_only_follows_proven_formula_path():
    result = _result(reasoning_snapshot(frozen_snapshot(config(environment=True))))
    records = result.evidence_records.set_index("source_record_id")
    relation = _pair_relation(
        result,
        records.loc["true_range_percentile", "record_id"],
        records.loc["ev__evidence_availability_fraction", "record_id"],
    )
    assert relation.provenance_status == "NOT_CERTIFIED"
    assert relation.derivation_status == "DETERMINISTIC_DERIVATIVE"
    assert "CERTIFIED_DETERMINISTIC_ANCESTOR" in relation.proof_contract


def test_v1_2_absent_derivation_proof_remains_not_certified():
    result = _result(_mtf_snapshot(0.5, False))
    records = result.evidence_records.set_index("source_record_id")
    relation = _pair_relation(
        result,
        records.loc["available_scale_count", "record_id"],
        records.loc["directional_conflict", "record_id"],
    )
    assert relation.derivation_status == "NOT_CERTIFIED"
    assert relation.derivation_status != "NOT_DETERMINISTICALLY_DERIVED"


def test_v1_1_all_caller_owned_frames_are_immutable():
    snapshot = reasoning_snapshot(frozen_snapshot(config(multiscale=True), mtf_balance=0.5))
    frame_names = (
        "evidence_row", "feature_manifest", "narrative_surface_row", "observation_rows",
        "hypothesis_rows", "relationship_rows", "relationship_sources", "narrative_manifest",
    )
    before = {name: getattr(snapshot, name).copy(deep=True) for name in frame_names}
    _result(snapshot)
    for name in frame_names:
        pd.testing.assert_frame_equal(getattr(snapshot, name), before[name], check_exact=True)


@pytest.mark.parametrize("row_kind", ["hypothesis", "relationship", "relationship_source"])
def test_v1_1_future_payload_not_accessed_for_all_row_types(row_kind):
    snapshot = reasoning_snapshot(frozen_snapshot())
    sentinel = FuturePayloadSentinel()
    if row_kind == "hypothesis":
        rows = snapshot.hypothesis_rows.copy(deep=True)
        future = rows.iloc[[0]].copy(deep=True)
        future["ledger_event_id"] = int(rows["ledger_event_id"].max()) + 1
        future["event_position"] = snapshot.decision_information_key.bar_position + 1
        future["ledger_event_type"] = pd.Series([sentinel], dtype=object)
        rows = pd.concat([rows, future], ignore_index=True)
        rows["event_position"] = pd.array(rows["event_position"], dtype="Int64")
        altered = replace(snapshot, hypothesis_rows=rows)
    else:
        relationships = snapshot.relationship_rows.copy(deep=True)
        future = relationships.iloc[[0]].copy(deep=True)
        old_id = int(future.iloc[0]["relationship_id"])
        new_id = int(relationships["relationship_id"].max()) + 1
        future["relationship_id"] = new_id
        future["observed_position"] = snapshot.decision_information_key.bar_position + 1
        if row_kind == "relationship":
            future["relationship_bearing"] = pd.Series([sentinel], dtype=object)
        relationships = pd.concat([relationships, future], ignore_index=True)
        relationships["relationship_id"] = pd.array(relationships["relationship_id"], dtype="Int64")
        relationships["observed_position"] = pd.array(relationships["observed_position"], dtype="Int64")
        sources = snapshot.relationship_sources.copy(deep=True)
        linked = sources[sources["relationship_id"] == old_id].copy(deep=True)
        linked["relationship_id"] = new_id
        if row_kind == "relationship_source":
            linked["source_value_category"] = pd.Series([sentinel] * len(linked), dtype=object)
        sources = pd.concat([sources, linked], ignore_index=True)
        sources["relationship_id"] = pd.array(sources["relationship_id"], dtype="Int64")
        altered = replace(snapshot, relationship_rows=relationships, relationship_sources=sources)
    with pytest.raises(ReasoningContractError, match="future record"):
        _result(altered)
    assert sentinel.touches == 0

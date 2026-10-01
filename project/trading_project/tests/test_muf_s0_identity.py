"""S0 identity tests: canonical identity + wave-process identity schema only.

Attacks covered: 07, 08, 09, 10, 16, 17, 20, 21. No market waves are created.
"""
import pandas as pd
import pytest

from trading_system.market_understanding.contracts import (
    IdentityViolation,
    SchemaIdentity,
    SchemaViolation,
    TypedState,
)
from trading_system.market_understanding.identity import (
    TURNING_POINT_RECORD_TYPE,
    WAVE_PROCESS_IDENTITY_DOMAIN,
    WAVE_PROCESS_IDENTITY_FIELDS,
    ArtifactIdentitySchema,
    AuthoritativeTurningPointReference,
    WaveIdentityProof,
    WaveProcessIdentityBasis,
    canonical_artifact_identity,
    verify_canonical_identity,
    wave_process_identity,
)
from trading_system.research.information_time import (
    INFORMATION_KEY_VERSION,
    InformationKey,
    InformationPhase,
)


def _key(timeline_id="TL", bar_position=0, phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
         sequence=0, event_time_utc=None):
    return InformationKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id=timeline_id,
        bar_position=bar_position,
        event_time_utc=event_time_utc,
        information_phase=phase,
        deterministic_sequence=sequence,
    )


def _tp_reference(**overrides):
    fields = dict(
        turning_point_identity="a" * 64,
        record_type=TURNING_POINT_RECORD_TYPE,
        schema_identity=SchemaIdentity("TP_RECORD_DOMAIN", "TP_RECORD_V1"),
        timeline_id="TL",
        availability_key=_key(),
    )
    fields.update(overrides)
    return fields


def _basis(**overrides):
    fields = dict(
        representation_spec_hash="b" * 64,
        authoritative_start_turning_point_id=AuthoritativeTurningPointReference(
            **_tp_reference()
        ),
        authority_policy_hash="c" * 64,
        timeline_id="TL",
        intrinsic_representation_key_or_NOT_APPLICABLE=TypedState.NOT_APPLICABLE,
    )
    fields.update(overrides)
    return WaveProcessIdentityBasis(**fields)


def _generic_schema(domain="GEN_DOMAIN", version="GEN_V1"):
    return ArtifactIdentitySchema(
        artifact_type="GenericRecord",
        schema_identity=SchemaIdentity(domain, version),
        identity_defining_fields=("record_value",),
        proof_fields=("proof_value",),
    )


def test_attack20_canonical_identity_deterministic():
    basis = _basis()
    first = wave_process_identity(basis)
    second = wave_process_identity(_basis())
    assert first == second
    assert len(first) == 64
    schema = _generic_schema()
    payload = {"record_value": "v"}
    assert (
        canonical_artifact_identity(schema, identity_payload=payload)
        == canonical_artifact_identity(schema, identity_payload=dict(payload))
    )


def test_attack21_domain_separation():
    payload = {"record_value": "same"}
    left = canonical_artifact_identity(_generic_schema("DOMAIN_A"), identity_payload=payload)
    right = canonical_artifact_identity(_generic_schema("DOMAIN_B"), identity_payload=payload)
    assert left != right
    versioned = canonical_artifact_identity(
        _generic_schema("DOMAIN_A", "GEN_V2"), identity_payload=payload
    )
    assert versioned != left


def test_identity_defining_change_changes_identity():
    base = wave_process_identity(_basis())
    changed = wave_process_identity(
        _basis(representation_spec_hash="d" * 64)
    )
    assert changed != base
    schema = _generic_schema()
    assert canonical_artifact_identity(schema, identity_payload={"record_value": "x"}) != (
        canonical_artifact_identity(schema, identity_payload={"record_value": "y"})
    )


def test_attack17_proof_only_metadata_change_keeps_identity():
    schema = _generic_schema()
    payload = {"record_value": "stable"}
    base = canonical_artifact_identity(
        schema, identity_payload=payload, proof_payload={"proof_value": "p1"}
    )
    noisy = canonical_artifact_identity(
        schema, identity_payload=payload, proof_payload={"proof_value": "p2"}
    )
    assert base == noisy
    with pytest.raises(SchemaViolation):
        canonical_artifact_identity(
            schema, identity_payload=payload, proof_payload={"undeclared": "x"}
        )


def test_attack07_extra_proof_ref_keeps_wave_process_id():
    basis = _basis()
    base = wave_process_identity(basis)
    key = _key()
    proof_a = WaveIdentityProof(
        identity_rule_ref="RULE_1",
        required_basis_refs=("ref-1",),
        proof_refs=("proof-1",),
        satisfaction_information_key=key,
    )
    proof_b = WaveIdentityProof(
        identity_rule_ref="RULE_1",
        required_basis_refs=("ref-1",),
        proof_refs=("proof-1", "proof-irrelevant-extra"),
        satisfaction_information_key=key,
    )
    assert proof_a.proof_refs != proof_b.proof_refs
    assert wave_process_identity(basis) == base


def test_attack08_authority_policy_hash_change_changes_identity():
    base = wave_process_identity(_basis())
    changed = wave_process_identity(_basis(authority_policy_hash="e" * 64))
    assert changed != base


def test_attack09_end_future_fields_rejected():
    payload = dict(
        representation_spec_hash="b" * 64,
        authoritative_start_turning_point_id=AuthoritativeTurningPointReference(
            **_tp_reference()
        ),
        authority_policy_hash="c" * 64,
        timeline_id="TL",
        intrinsic_representation_key_or_NOT_APPLICABLE=TypedState.NOT_APPLICABLE,
    )
    for forbidden in (
        "authoritative_end_turning_point_id",
        "parent_wave_id",
        "depth",
        "members",
        "future_reference",
    ):
        bad = dict(payload)
        bad[forbidden] = "x"
        with pytest.raises(SchemaViolation):
            WaveProcessIdentityBasis.from_payload(bad)
    assert set(WAVE_PROCESS_IDENTITY_FIELDS).isdisjoint(
        {"authoritative_end_turning_point_id", "parent_wave_id", "depth", "members"}
    )


def test_attack10_arbitrary_string_tp_reference_rejected():
    with pytest.raises(SchemaViolation):
        WaveProcessIdentityBasis(
            representation_spec_hash="b" * 64,
            authoritative_start_turning_point_id="not-a-typed-reference",
            authority_policy_hash="c" * 64,
            timeline_id="TL",
            intrinsic_representation_key_or_NOT_APPLICABLE=TypedState.NOT_APPLICABLE,
        )
    with pytest.raises(SchemaViolation):
        AuthoritativeTurningPointReference(
            **_tp_reference(record_type="SOME_OTHER_TYPE")
        )
    with pytest.raises(SchemaViolation):
        AuthoritativeTurningPointReference(**_tp_reference(availability_key="2026-05-01"))


def test_optional_policy_authority_forbidden():
    with pytest.raises(SchemaViolation):
        _basis(authority_policy_hash=None)
    with pytest.raises(SchemaViolation):
        _basis(authority_policy_hash="")
    with pytest.raises(SchemaViolation):
        _basis(authority_policy_hash=TypedState.NOT_CONFIGURED)
    with pytest.raises(SchemaViolation):
        _basis(
            intrinsic_representation_key_or_NOT_APPLICABLE=TypedState.UNAVAILABLE
        )
    ok = _basis(intrinsic_representation_key_or_NOT_APPLICABLE="KEY_1")
    assert ok.intrinsic_representation_key_or_NOT_APPLICABLE == "KEY_1"


def test_attack16_stale_identity_rejected_after_semantic_change():
    schema = _generic_schema()
    old_identity = canonical_artifact_identity(
        schema, identity_payload={"record_value": "before"}
    )
    with pytest.raises(IdentityViolation):
        verify_canonical_identity(
            schema,
            identity_payload={"record_value": "after"},
            expected_identity=old_identity,
        )
    verify_canonical_identity(
        schema, identity_payload={"record_value": "before"}, expected_identity=old_identity
    )


def test_hash_validity_is_not_semantic_validity():
    schema = _generic_schema()
    identity = canonical_artifact_identity(schema, identity_payload={"record_value": "meaningless"})
    assert isinstance(identity, str) and len(identity) == 64
    with pytest.raises(IdentityViolation):
        verify_canonical_identity(
            schema,
            identity_payload={"record_value": "meaningless"},
            expected_identity="0" * 64,
        )


def test_schema_version_change_changes_identity():
    payload = {"record_value": "same"}
    v1 = canonical_artifact_identity(_generic_schema("D", "V1"), identity_payload=payload)
    v2 = canonical_artifact_identity(_generic_schema("D", "V2"), identity_payload=payload)
    assert v1 != v2


def test_wave_identity_proof_separate_from_basis():
    key = _key()
    proof = WaveIdentityProof(
        identity_rule_ref="RULE_1",
        required_basis_refs=("ref-1",),
        proof_refs=("proof-1",),
        satisfaction_information_key=key,
    )
    assert proof.satisfaction_information_key is key
    basis = _basis()
    assert wave_process_identity(basis) != canonical_artifact_identity(
        ArtifactIdentitySchema(
            artifact_type="WaveIdentityProof",
            schema_identity=SchemaIdentity(WAVE_PROCESS_IDENTITY_DOMAIN, "PROOF_V1"),
            identity_defining_fields=("identity_rule_ref",),
        ),
        identity_payload={"identity_rule_ref": "RULE_1"},
    )
    with pytest.raises(SchemaViolation):
        WaveIdentityProof(
            identity_rule_ref="RULE_1",
            required_basis_refs=("ref-1",),
            proof_refs=("proof-1",),
            satisfaction_information_key="not-a-key",
        )

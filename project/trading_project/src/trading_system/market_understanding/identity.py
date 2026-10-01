"""MUF V1 S0: canonical artifact identity and wave-process identity schema.

Schema/identity contracts only. S0 does NOT detect or construct market waves
and does NOT implement turning-point detection or promotion.

Identity rules (accepted design chain):
- identity-defining fields are strictly separated from proof/witness fields;
- proof noise never changes an identity unless the schema declares the field
  identity-defining;
- hash validity is never semantic validity (verification is a separate step);
- canonical identity is domain-separated, schema/version aware, deterministic,
  and immutable after construction, computed through the approved public
  CLOSED hashing semantics (``trading_system.research.hashing``).

Complexity: constant in record/schema size (bounded field sets).
"""
from dataclasses import dataclass
from typing import Any, Final, Mapping, Tuple, Union

from trading_system.research.hashing import canonical_sha256
from trading_system.research.information_time import InformationKey

from trading_system.market_understanding.contracts import (
    IdentityViolation,
    InformationKeyViolation,
    SchemaIdentity,
    SchemaViolation,
    TypedState,
    require_identifier_tuple,
    require_string,
)

IDENTITY_SCHEMA_VERSION: Final[str] = "MUF_S0_IDENTITY_V1"
ARTIFACT_IDENTITY_DOMAIN_ROOT: Final[str] = "MUF_V1_CANONICAL_ARTIFACT_IDENTITY"

WAVE_PROCESS_IDENTITY_SCHEMA_VERSION: Final[str] = "MUF_S0_WAVE_PROCESS_IDENTITY_V1"
WAVE_PROCESS_IDENTITY_DOMAIN: Final[str] = "MUF_V1_WAVE_PROCESS_IDENTITY"
TURNING_POINT_RECORD_TYPE: Final[str] = "TURNING_POINT_RECORD"

WAVE_PROCESS_IDENTITY_FIELDS: Final[Tuple[str, ...]] = (
    "representation_spec_hash",
    "authoritative_start_turning_point_id",
    "authority_policy_hash",
    "timeline_id",
    "intrinsic_representation_key_or_NOT_APPLICABLE",
)

WAVE_PROCESS_FORBIDDEN_IDENTITY_FIELDS: Final[Tuple[str, ...]] = (
    "authoritative_end_turning_point_id",
    "end_turning_point_id",
    "end_facts",
    "end_keys",
    "parent_wave_id",
    "parent_id",
    "depth",
    "members",
    "member_ids",
    "child_wave_ids",
    "future_reference",
    "future_parent",
    "future_depth",
    "future_member",
)


@dataclass(frozen=True)
class ArtifactIdentitySchema:
    """Declares which fields define identity and which are proof-only."""

    artifact_type: str
    schema_identity: SchemaIdentity
    identity_defining_fields: Tuple[str, ...]
    proof_fields: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_string(self.artifact_type, "artifact_type")
        if not isinstance(self.schema_identity, SchemaIdentity):
            raise SchemaViolation("schema_identity must be a SchemaIdentity")
        require_identifier_tuple(self.identity_defining_fields, "identity_defining_fields")
        if self.proof_fields:
            require_identifier_tuple(self.proof_fields, "proof_fields")
        overlap = set(self.identity_defining_fields) & set(self.proof_fields)
        if overlap:
            raise SchemaViolation(
                f"fields cannot be both identity-defining and proof: {sorted(overlap)}"
            )


def _identity_domain(schema: ArtifactIdentitySchema) -> str:
    return (
        f"{ARTIFACT_IDENTITY_DOMAIN_ROOT}"
        f":{schema.schema_identity.schema_domain}"
        f":{schema.artifact_type}"
        f":identity"
    )


def _serialize_identity_value(value: Any) -> Any:
    """Canonical S0 boundary serialization for identity-defining values."""
    if isinstance(value, TypedState):
        return {"typed_state": value.value}
    if isinstance(value, str):
        return {"string": value}
    if isinstance(value, SchemaIdentity):
        return {"schema_identity": dict(value.as_payload())}
    if isinstance(value, InformationKey):
        return value
    if isinstance(value, Mapping):
        return {"mapping": {str(k): _serialize_identity_value(v) for k, v in value.items()}}
    raise SchemaViolation(f"unsupported identity-defining value kind: {type(value)!r}")


def canonical_artifact_identity(
    schema: ArtifactIdentitySchema,
    *,
    identity_payload: Mapping[str, Any],
    proof_payload: Mapping[str, Any] | None = None,
) -> str:
    """Deterministic, domain-separated, schema-versioned canonical identity.

    Only identity-defining fields enter the identity. ``proof_payload`` is
    accepted for provenance bookkeeping and NEVER enters the hash unless a
    field is declared identity-defining in the schema (it is not, by
    construction: proof fields are disjoint).
    """
    if not isinstance(schema, ArtifactIdentitySchema):
        raise SchemaViolation("schema must be an ArtifactIdentitySchema")
    if not isinstance(identity_payload, Mapping):
        raise SchemaViolation("identity_payload must be a mapping")
    expected = tuple(schema.identity_defining_fields)
    provided = tuple(identity_payload.keys())
    if len(set(provided)) != len(provided):
        raise SchemaViolation("identity_payload keys must be unique")
    if set(provided) != set(expected):
        raise SchemaViolation(
            "identity_payload must contain exactly the identity-defining fields: "
            f"expected={sorted(expected)} provided={sorted(provided)}"
        )
    if proof_payload is not None:
        if not isinstance(proof_payload, Mapping):
            raise SchemaViolation("proof_payload must be a mapping when provided")
        unknown = set(proof_payload.keys()) - set(schema.proof_fields)
        if unknown:
            raise SchemaViolation(f"undeclared proof fields: {sorted(unknown)}")
    hash_payload = {
        "identity_schema_version": IDENTITY_SCHEMA_VERSION,
        "schema_identity": dict(schema.schema_identity.as_payload()),
        "artifact_type": schema.artifact_type,
        "identity_fields": {
            name: _serialize_identity_value(identity_payload[name]) for name in expected
        },
    }
    return canonical_sha256(domain=_identity_domain(schema), payload=hash_payload)


def verify_canonical_identity(
    schema: ArtifactIdentitySchema,
    *,
    identity_payload: Mapping[str, Any],
    expected_identity: str,
) -> None:
    """Separate semantic validation step: hash validity != semantic validity."""
    if not isinstance(expected_identity, str) or not expected_identity:
        raise IdentityViolation("expected_identity must be a nonempty string")
    actual = canonical_artifact_identity(schema, identity_payload=identity_payload)
    if actual != expected_identity:
        raise IdentityViolation("canonical identity mismatch: stale or forged identity")


# ---------------------------------------------------------------------------
# Wave-process identity: SCHEMA ONLY (no market waves at S0)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthoritativeTurningPointReference:
    """Typed reference contract for an authoritative turning point record.

    NOT an arbitrary string: identity + declared record type + schema identity
    + timeline + availability key must all be present and coherent. S0 does
    not detect or promote turning points; this is a typed pointer contract.
    """

    turning_point_identity: str
    record_type: str
    schema_identity: SchemaIdentity
    timeline_id: str
    availability_key: InformationKey

    def __post_init__(self) -> None:
        require_string(self.turning_point_identity, "turning_point_identity")
        if self.record_type != TURNING_POINT_RECORD_TYPE:
            raise SchemaViolation(
                "record_type must be the declared TURNING_POINT_RECORD typed contract"
            )
        if not isinstance(self.schema_identity, SchemaIdentity):
            raise SchemaViolation("schema_identity must be a SchemaIdentity")
        require_string(self.timeline_id, "timeline_id")
        if not isinstance(self.availability_key, InformationKey):
            raise SchemaViolation("availability_key must be an InformationKey")
        if self.availability_key.timeline_id != self.timeline_id:
            raise InformationKeyViolation(
                "turning-point reference timeline must match its availability key"
            )

    def as_payload(self) -> Mapping[str, Any]:
        return {
            "turning_point_identity": self.turning_point_identity,
            "record_type": self.record_type,
            "schema_identity": dict(self.schema_identity.as_payload()),
            "timeline_id": self.timeline_id,
            "availability_key": self.availability_key,
        }


@dataclass(frozen=True)
class WaveProcessIdentityBasis:
    """Identity-defining basis of a wave process (schema contract only).

    Optional policy authority is FORBIDDEN: ``authority_policy_hash`` is a
    required nonempty field and can never be absent/optional.
    """

    representation_spec_hash: str
    authoritative_start_turning_point_id: AuthoritativeTurningPointReference
    authority_policy_hash: str
    timeline_id: str
    intrinsic_representation_key_or_NOT_APPLICABLE: Union[str, TypedState]

    def __post_init__(self) -> None:
        require_string(self.representation_spec_hash, "representation_spec_hash")
        if not isinstance(
            self.authoritative_start_turning_point_id, AuthoritativeTurningPointReference
        ):
            raise SchemaViolation(
                "authoritative_start_turning_point_id must be a typed "
                "AuthoritativeTurningPointReference (arbitrary strings forbidden)"
            )
        if not isinstance(self.authority_policy_hash, str) or not self.authority_policy_hash:
            raise SchemaViolation(
                "authority_policy_hash is required: optional policy authority is forbidden"
            )
        require_string(self.timeline_id, "timeline_id")
        start = self.authoritative_start_turning_point_id
        if start.timeline_id != self.timeline_id:
            raise InformationKeyViolation(
                "start turning-point reference must share the basis timeline"
            )
        intrinsic = self.intrinsic_representation_key_or_NOT_APPLICABLE
        if isinstance(intrinsic, TypedState):
            if intrinsic is not TypedState.NOT_APPLICABLE:
                raise SchemaViolation(
                    "intrinsic_representation_key_or_NOT_APPLICABLE accepts only "
                    "NOT_APPLICABLE among typed states"
                )
        else:
            require_string(intrinsic, "intrinsic_representation_key_or_NOT_APPLICABLE")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "WaveProcessIdentityBasis":
        """Strict schema constructor: exact field set, no end/future fields."""
        if not isinstance(payload, Mapping):
            raise SchemaViolation("payload must be a mapping")
        keys = set(payload.keys())
        forbidden = keys & set(WAVE_PROCESS_FORBIDDEN_IDENTITY_FIELDS)
        if forbidden:
            raise SchemaViolation(
                f"end/future fields are forbidden in process identity: {sorted(forbidden)}"
            )
        expected = set(WAVE_PROCESS_IDENTITY_FIELDS)
        unknown = keys - expected
        missing = expected - keys
        if unknown or missing:
            raise SchemaViolation(
                f"process identity payload mismatch: unknown={sorted(unknown)} "
                f"missing={sorted(missing)}"
            )
        return cls(
            representation_spec_hash=payload["representation_spec_hash"],
            authoritative_start_turning_point_id=payload[
                "authoritative_start_turning_point_id"
            ],
            authority_policy_hash=payload["authority_policy_hash"],
            timeline_id=payload["timeline_id"],
            intrinsic_representation_key_or_NOT_APPLICABLE=payload[
                "intrinsic_representation_key_or_NOT_APPLICABLE"
            ],
        )


@dataclass(frozen=True)
class WaveIdentityProof:
    """Proof/witness record for a wave process identity.

    STRICTLY SEPARATE from WaveProcessIdentityBasis: proof fields never enter
    the wave process identity (identity-defining basis != proof).
    """

    identity_rule_ref: str
    required_basis_refs: Tuple[str, ...]
    proof_refs: Tuple[str, ...]
    satisfaction_information_key: InformationKey

    def __post_init__(self) -> None:
        require_string(self.identity_rule_ref, "identity_rule_ref")
        for field_name, value in (
            ("required_basis_refs", self.required_basis_refs),
            ("proof_refs", self.proof_refs),
        ):
            if not isinstance(value, tuple):
                raise SchemaViolation(f"{field_name} must be a tuple of references")
            for item in value:
                require_string(item, field_name)
        if not isinstance(self.satisfaction_information_key, InformationKey):
            raise SchemaViolation("satisfaction_information_key must be an InformationKey")


WAVE_PROCESS_SCHEMA: Final[ArtifactIdentitySchema] = ArtifactIdentitySchema(
    artifact_type="WaveProcessIdentityBasis",
    schema_identity=SchemaIdentity(
        schema_domain=WAVE_PROCESS_IDENTITY_DOMAIN,
        schema_version=WAVE_PROCESS_IDENTITY_SCHEMA_VERSION,
    ),
    identity_defining_fields=WAVE_PROCESS_IDENTITY_FIELDS,
    proof_fields=(
        "identity_rule_ref",
        "required_basis_refs",
        "proof_refs",
        "satisfaction_information_key",
    ),
)


def wave_process_identity(basis: WaveProcessIdentityBasis) -> str:
    """Canonical wave-process identity from the identity-defining basis only."""
    if not isinstance(basis, WaveProcessIdentityBasis):
        raise SchemaViolation("basis must be a WaveProcessIdentityBasis")
    identity_payload = {
        "representation_spec_hash": basis.representation_spec_hash,
        "authoritative_start_turning_point_id": dict(
            basis.authoritative_start_turning_point_id.as_payload()
        ),
        "authority_policy_hash": basis.authority_policy_hash,
        "timeline_id": basis.timeline_id,
        "intrinsic_representation_key_or_NOT_APPLICABLE": (
            basis.intrinsic_representation_key_or_NOT_APPLICABLE
        ),
    }
    return canonical_artifact_identity(
        WAVE_PROCESS_SCHEMA, identity_payload=identity_payload
    )

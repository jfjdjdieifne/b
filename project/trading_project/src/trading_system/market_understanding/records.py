"""MUF V1 S0: immutable record foundations, append-only events, typed references.

Published records cannot be mutated in place. Lifecycle changes are new
events/records; generic current-state projection derives from events only.
Typed causal references carry record identity, timeline, availability, and
record type/schema identity so later layers can validate visibility,
timeline/phase compatibility, and expected schema/type.

No market-specific S1+ semantics (status/supersession/relation/membership
event kinds are generic foundations only).

DEEP IMMUTABILITY (I-DEEP-1..5): persisted record/event payloads are
recursively canonically frozen at construction (``freeze_payload``). Caller-
owned mutable containers are never aliased; nested mutation is impossible;
freeze is deterministic. Payload content does NOT enter any canonical
identity hash at S0 (identity-defining fields are separate); where a frozen
payload is hashed through the approved public CLOSED hashing, the canonical
hash equals the hash of the equivalent raw structure (freeze preserves hash
semantics).

Value-domain contract for frozen payloads (fail closed otherwise):
- str / bool / int / float / None            -> preserved as-is
- Enum members (TypedState, EventKind, ...)  -> preserved as-is
- InformationKey / SchemaIdentity            -> preserved as-is (frozen objects)
- Mapping with str keys                      -> recursively frozen canonical dict
- list / tuple                               -> recursively frozen tuple
- set / frozenset                            -> SchemaViolation (unordered
  collections are not permitted by the S0 semantic contract)
- any other mutable/custom object            -> SchemaViolation (never blindly
  deep-copied; no semantics invented)

Complexity: record/event construction O(payload_size) (deep freeze, honest —
not O(1)). Ledger append amortized O(1) (private identity index; ordered
immutable event history remains the projection source). Iteration/projection
O(|events|) when explicitly requested. Reference validation O(1).
No market-history access.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Mapping, Tuple, Union

from trading_system.research.information_time import InformationKey

from trading_system.market_understanding.availability import require_visible_at
from trading_system.market_understanding.contracts import (
    IllegalCausalReference,
    ImmutabilityViolation,
    InformationKeyViolation,
    SchemaIdentity,
    SchemaViolation,
    TypedState,
    require_string,
)

RECORDS_SCHEMA_VERSION: Final[str] = "MUF_S0_RECORDS_V1"


class FrozenPayloadDict(dict):
    """Canonical immutable dict representation (hash-compatible, mutation-rejecting)."""

    __slots__ = ()

    def _deny(self, *args, **kwargs):
        raise ImmutabilityViolation(
            "frozen payload mapping is immutable; lifecycle change requires a new record/event"
        )

    __setitem__ = _deny
    __delitem__ = _deny
    clear = _deny
    pop = _deny
    popitem = _deny
    setdefault = _deny
    update = _deny
    __ior__ = _deny


def freeze_payload(value: Any, *, field_name: str = "payload") -> Any:
    """Recursively canonical-freeze an S0 payload structure (I-DEEP-1..5).

    Deterministic. Caller-owned containers are copied structurally; nested
    mutable structures cannot permit post-construction mutation. Unsupported
    objects fail closed with SchemaViolation (no invented semantics).
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return value
    if isinstance(value, (InformationKey, SchemaIdentity)):
        return value
    if isinstance(value, Mapping):
        items = {}
        for key in value:
            if not isinstance(key, str):
                raise SchemaViolation(
                    f"{field_name} mapping keys must be strings; got {type(key)!r}"
                )
            items[key] = freeze_payload(value[key], field_name=f"{field_name}[{key!r}]")
        return FrozenPayloadDict(items)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_payload(item, field_name=field_name) for item in value)
    if isinstance(value, (set, frozenset)):
        raise SchemaViolation(
            f"{field_name} does not permit unordered collections (set/frozenset)"
        )
    raise SchemaViolation(
        f"{field_name} contains an unsupported value of type {type(value)!r}; "
        "fail closed (no semantics invented for unsupported objects)"
    )


class ImmutableRecord:
    """Published record: constructed once, sealed, never mutated in place."""

    def __init__(self, **fields: Any) -> None:
        if getattr(self, "_sealed", False):
            raise ImmutabilityViolation(
                "an already-sealed record cannot be re-initialized"
            )
        object.__setattr__(self, "_sealed", False)
        for name, value in fields.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: Any) -> None:
        raise ImmutabilityViolation(
            f"published record is immutable: in-place mutation forbidden ({name})"
        )

    def __delattr__(self, name: str) -> None:
        raise ImmutabilityViolation(
            f"published record is immutable: deletion forbidden ({name})"
        )


class PublishedRecord(ImmutableRecord):
    """Generic published factual record with typed availability."""

    def __init__(
        self,
        *,
        record_identity: str,
        record_type: str,
        schema_identity: SchemaIdentity,
        timeline_id: str,
        availability_key: InformationKey,
        content: Mapping[str, Any],
    ) -> None:
        require_string(record_identity, "record_identity")
        require_string(record_type, "record_type")
        if not isinstance(schema_identity, SchemaIdentity):
            raise SchemaViolation("schema_identity must be a SchemaIdentity")
        require_string(timeline_id, "timeline_id")
        if not isinstance(availability_key, InformationKey):
            raise SchemaViolation("availability_key must be an InformationKey")
        if availability_key.timeline_id != timeline_id:
            raise InformationKeyViolation(
                "record timeline must match its availability key timeline"
            )
        if not isinstance(content, Mapping):
            raise SchemaViolation("content must be a mapping")
        super().__init__(
            record_identity=record_identity,
            record_type=record_type,
            schema_identity=schema_identity,
            timeline_id=timeline_id,
            availability_key=availability_key,
            content=freeze_payload(content, field_name="content"),
        )


class EventKind(Enum):
    """Generic event-kind foundations (market semantics belong to later S1+)."""

    STATUS_EVENT = "STATUS_EVENT"
    SUPERSESSION_EVENT = "SUPERSESSION_EVENT"
    RELATION_EVENT = "RELATION_EVENT"
    MEMBERSHIP_EVENT = "MEMBERSHIP_EVENT"


class EventRecord(ImmutableRecord):
    """Immutable lifecycle event; lifecycle change == new event, never rewrite."""

    def __init__(
        self,
        *,
        event_identity: str,
        event_kind: EventKind,
        subject_record_identity: str,
        event_key: InformationKey,
        event_payload: Mapping[str, Any],
    ) -> None:
        require_string(event_identity, "event_identity")
        if not isinstance(event_kind, EventKind):
            raise SchemaViolation("event_kind must be an EventKind")
        require_string(subject_record_identity, "subject_record_identity")
        if not isinstance(event_key, InformationKey):
            raise SchemaViolation("event_key must be an InformationKey")
        if not isinstance(event_payload, Mapping):
            raise SchemaViolation("event_payload must be a mapping")
        super().__init__(
            event_identity=event_identity,
            event_kind=event_kind,
            subject_record_identity=subject_record_identity,
            event_key=event_key,
            event_payload=freeze_payload(event_payload, field_name="event_payload"),
        )


class AppendOnlyEventLedger:
    """Append-only event ledger; current state derives from events only.

    Duplicate detection uses a private identity index (internal bookkeeping
    only) so append is amortized O(1); the ordered immutable event history in
    ``self._events`` remains the sole source of projection semantics.
    """

    def __init__(self) -> None:
        self._events = []
        self.__identity_index = set()

    def append(self, event: EventRecord) -> None:
        if not isinstance(event, EventRecord):
            raise SchemaViolation("only EventRecord instances can be appended")
        if event.event_identity in self.__identity_index:
            raise SchemaViolation(
                "duplicate event_identity: events are append-only and unique"
            )
        self.__identity_index.add(event.event_identity)
        self._events.append(event)

    def overwrite(self, record_identity: str, replacement: PublishedRecord) -> None:
        """Overwrite is forbidden: lifecycle change requires a new event."""
        raise ImmutabilityViolation(
            "published records cannot be overwritten; append a new event"
        )

    def events(self) -> Tuple[EventRecord, ...]:
        return tuple(self._events)

    def project_status(self, record_identity: str) -> Union[str, TypedState]:
        """Derive current status from events only; UNDEFINED when no event."""
        require_string(record_identity, "record_identity")
        status = TypedState.UNDEFINED
        for event in self._events:
            if (
                event.subject_record_identity == record_identity
                and event.event_kind is EventKind.STATUS_EVENT
            ):
                value = event.event_payload.get("status", TypedState.UNDEFINED)
                status = value
        return status

    def project_supersession(self, record_identity: str) -> Union[str, TypedState]:
        """Derive supersession from events only; NOT_APPLICABLE when none."""
        require_string(record_identity, "record_identity")
        superseded_by = TypedState.NOT_APPLICABLE
        for event in self._events:
            if (
                event.subject_record_identity == record_identity
                and event.event_kind is EventKind.SUPERSESSION_EVENT
            ):
                value = event.event_payload.get(
                    "superseded_by", TypedState.UNDEFINED
                )
                superseded_by = value
        return superseded_by


# ---------------------------------------------------------------------------
# Typed causal references (foundation for later closure validation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AvailabilityReference:
    """Resolvable availability pointer (resolution belongs to later layers)."""

    availability_record_identity: str
    schema_identity: SchemaIdentity
    timeline_id: str

    def __post_init__(self) -> None:
        require_string(self.availability_record_identity, "availability_record_identity")
        if not isinstance(self.schema_identity, SchemaIdentity):
            raise SchemaViolation("schema_identity must be a SchemaIdentity")
        require_string(self.timeline_id, "timeline_id")


@dataclass(frozen=True)
class CausalRecordReference:
    """Typed causal reference: identity + timeline + availability + type/schema."""

    referenced_record_identity: str
    referenced_record_type: str
    referenced_schema_identity: SchemaIdentity
    timeline_id: str
    availability: Union[InformationKey, AvailabilityReference]

    def __post_init__(self) -> None:
        require_string(self.referenced_record_identity, "referenced_record_identity")
        require_string(self.referenced_record_type, "referenced_record_type")
        if not isinstance(self.referenced_schema_identity, SchemaIdentity):
            raise SchemaViolation("referenced_schema_identity must be a SchemaIdentity")
        require_string(self.timeline_id, "timeline_id")
        if isinstance(self.availability, InformationKey):
            if self.availability.timeline_id != self.timeline_id:
                raise InformationKeyViolation(
                    "reference availability key must share the reference timeline"
                )
        elif isinstance(self.availability, AvailabilityReference):
            if self.availability.timeline_id != self.timeline_id:
                raise InformationKeyViolation(
                    "reference availability pointer must share the reference timeline"
                )
        else:
            raise SchemaViolation(
                "availability must be an InformationKey or an AvailabilityReference"
            )


def validate_reference_at(
    *, reference: CausalRecordReference, at_key: InformationKey
) -> None:
    """Validate that a causal reference is legitimately visible at ``at_key``.

    Prevents an arbitrary future record reference from masquerading as a
    currently visible one. Unresolvable availability pointers fail closed.
    """
    if not isinstance(reference, CausalRecordReference):
        raise SchemaViolation("reference must be a CausalRecordReference")
    if not isinstance(at_key, InformationKey):
        raise SchemaViolation("at_key must be an InformationKey")
    if reference.timeline_id != at_key.timeline_id:
        raise IllegalCausalReference("cross-timeline causal reference forbidden")
    if isinstance(reference.availability, InformationKey):
        require_visible_at(fact_key=reference.availability, at_key=at_key)
        return
    raise IllegalCausalReference(
        "availability is an unresolved AvailabilityReference: visibility cannot "
        "be established at S0, fail closed"
    )


def validate_reference_type(
    *,
    reference: CausalRecordReference,
    expected_record_type: str,
    expected_schema_identity: SchemaIdentity,
) -> None:
    """Validate the referenced record type and schema identity are as expected."""
    if not isinstance(reference, CausalRecordReference):
        raise SchemaViolation("reference must be a CausalRecordReference")
    require_string(expected_record_type, "expected_record_type")
    if not isinstance(expected_schema_identity, SchemaIdentity):
        raise SchemaViolation("expected_schema_identity must be a SchemaIdentity")
    if reference.referenced_record_type != expected_record_type:
        raise IllegalCausalReference("referenced record type is not the expected type")
    if reference.referenced_schema_identity != expected_schema_identity:
        raise IllegalCausalReference(
            "referenced schema identity is not the expected schema identity"
        )

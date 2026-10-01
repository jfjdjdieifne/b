"""MUF V1 S0: InformationKey binding, information batches, earliest availability.

S0 wraps/references the CLOSED public InformationKey semantics
(``trading_system.research.information_time``) and never redefines them.

Invariants enforced here:
- cross-timeline references and comparisons are REJECT/FAIL-CLOSED;
- POSITIONAL keys never acquire invented timestamps;
- TIME_INDEXED keys obey the CLOSED timezone-aware time contract;
- BAR_PRE_CLOSE never gains completed-bar facts;
- deterministic_sequence is serialization only and never proves market
  chronology; row/file/append order never establishes market chronology;
- KNOWN_SAME_BATCH is never collapsed with UNKNOWN_IF_SAME_BATCH;
- TIE_ORDER_CONTRACT stays NOT_PROVEN (public CLOSED constant reused).

Earliest-lawful availability uses ONLY the public InformationKey comparison
(legal within one timeline). Whenever comparability cannot be established
under those public semantics, S0 fails closed (NOT_COMPARABLE) and never
guesses an ordering.

Complexity: O(|required_basis_keys| + |satisfaction_keys|) single-scan
computation over caller-declared finite lists (no cross-product); no
market-history access.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Mapping, Tuple, Union

from trading_system.research.information_time import (
    InformationKey,
    InformationKeyError,
    InformationPhase,
)
from trading_system.sources import TIE_ORDER_CONTRACT

from trading_system.market_understanding.contracts import (
    IllegalCausalReference,
    IncomparableInformationKeys,
    InformationKeyViolation,
    NonEarliestAvailability,
    PrematureAvailability,
    SchemaViolation,
    SequenceChronologyViolation,
    TypedState,
    require_string,
)

AVAILABILITY_SCHEMA_VERSION: Final[str] = "MUF_S0_AVAILABILITY_V1"


class InformationAxis(Enum):
    """Timeline axis semantics (mirrors the CLOSED adapter split)."""

    POSITIONAL = "POSITIONAL"
    TIME_INDEXED = "TIME_INDEXED"


class SourceBatchIdentity(Enum):
    """Source-batch identity status: NEVER collapsed across variants."""

    KNOWN_SAME_BATCH = "KNOWN_SAME_BATCH"
    UNKNOWN_IF_SAME_BATCH = "UNKNOWN_IF_SAME_BATCH"


class BatchRelation(Enum):
    """Relation between two information batches."""

    KNOWN_SAME_BATCH = "KNOWN_SAME_BATCH"
    UNKNOWN_IF_SAME_BATCH = "UNKNOWN_IF_SAME_BATCH"
    DIFFERENT_BATCH = "DIFFERENT_BATCH"


class MarketChronologyProof(Enum):
    """Market chronology proof state; S0 can only ever return NOT_PROVEN."""

    NOT_PROVEN = "NOT_PROVEN"


def _require_information_key(value: Any, field_name: str) -> InformationKey:
    if not isinstance(value, InformationKey):
        raise SchemaViolation(f"{field_name} must be an InformationKey")
    return value


# ---------------------------------------------------------------------------
# InformationKey binding (wrap; never redefine)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InformationKeyBinding:
    """Binds a CLOSED InformationKey to declared axis semantics."""

    key: InformationKey
    axis: InformationAxis

    def __post_init__(self) -> None:
        _require_information_key(self.key, "key")
        if not isinstance(self.axis, InformationAxis):
            raise SchemaViolation("axis must be an InformationAxis")
        if self.axis is InformationAxis.POSITIONAL and self.key.event_time_utc is not None:
            raise InformationKeyViolation(
                "POSITIONAL binding must not acquire an invented timestamp"
            )
        if self.axis is InformationAxis.TIME_INDEXED:
            if self.key.event_time_utc is None:
                raise InformationKeyViolation(
                    "TIME_INDEXED binding requires a lawful event time"
                )
            if self.key.event_time_utc.tzinfo is None:
                raise InformationKeyViolation(
                    "TIME_INDEXED binding requires timezone-aware time"
                )


def require_visible_at(*, fact_key: InformationKey, at_key: InformationKey) -> None:
    """As-of visibility under CLOSED key semantics: fact_key <= at_key.

    Cross-timeline -> IllegalCausalReference (REJECT). Incomparable keys under
    public semantics -> IncomparableInformationKeys (FAIL CLOSED).
    """
    _require_information_key(fact_key, "fact_key")
    _require_information_key(at_key, "at_key")
    if fact_key.timeline_id != at_key.timeline_id:
        raise IllegalCausalReference("cross-timeline causal reference forbidden")
    if (
        at_key.information_phase is InformationPhase.BAR_PRE_CLOSE
        and fact_key.information_phase is InformationPhase.COMPLETED_ROW_AVAILABLE
        and fact_key.bar_position == at_key.bar_position
    ):
        raise IllegalCausalReference(
            "BAR_PRE_CLOSE must not gain completed-bar facts"
        )
    try:
        visible = fact_key <= at_key
    except InformationKeyError as exc:
        raise IncomparableInformationKeys(
            "information-key comparability cannot be established; fail closed"
        ) from exc
    if not visible:
        raise IllegalCausalReference(
            "reference is not visible at the proposed information key"
        )


# ---------------------------------------------------------------------------
# Information batch (NB-1-style ambiguity preserved; no tie ordering invented)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InformationBatchKey:
    """Information-batch identity per accepted D2 semantics."""

    timeline_id: str
    axis: InformationAxis
    causal_position: int
    information_phase: InformationPhase
    source_batch_status: SourceBatchIdentity
    source_batch_ref: Union[str, TypedState]

    def __post_init__(self) -> None:
        require_string(self.timeline_id, "timeline_id")
        if not isinstance(self.axis, InformationAxis):
            raise SchemaViolation("axis must be an InformationAxis")
        if isinstance(self.causal_position, bool) or not isinstance(self.causal_position, int):
            raise SchemaViolation("causal_position must be an integer")
        if self.causal_position < 0:
            raise SchemaViolation("causal_position must be nonnegative")
        if not isinstance(self.information_phase, InformationPhase):
            raise SchemaViolation("information_phase must be an InformationPhase")
        if not isinstance(self.source_batch_status, SourceBatchIdentity):
            raise SchemaViolation("source_batch_status must be a SourceBatchIdentity")
        if isinstance(self.source_batch_ref, TypedState):
            if self.source_batch_status is SourceBatchIdentity.KNOWN_SAME_BATCH:
                raise SchemaViolation(
                    "KNOWN_SAME_BATCH requires a concrete source_batch_ref"
                )
            return
        require_string(self.source_batch_ref, "source_batch_ref")

    def _coordinates(self) -> Tuple[Any, Any, Any, Any]:
        return (
            self.timeline_id,
            self.axis,
            self.causal_position,
            self.information_phase,
        )


def information_batch_relation(
    left: InformationBatchKey, right: InformationBatchKey
) -> BatchRelation:
    """Batch relation: UNKNOWN is never promoted to KNOWN_SAME_BATCH."""
    if not isinstance(left, InformationBatchKey) or not isinstance(right, InformationBatchKey):
        raise SchemaViolation("both operands must be InformationBatchKey")
    if left._coordinates() != right._coordinates():
        return BatchRelation.DIFFERENT_BATCH
    if (
        left.source_batch_status is SourceBatchIdentity.KNOWN_SAME_BATCH
        and right.source_batch_status is SourceBatchIdentity.KNOWN_SAME_BATCH
        and left.source_batch_ref == right.source_batch_ref
    ):
        return BatchRelation.KNOWN_SAME_BATCH
    return BatchRelation.UNKNOWN_IF_SAME_BATCH


def combine_source_batch_status(
    left: SourceBatchIdentity, right: SourceBatchIdentity
) -> SourceBatchIdentity:
    """Status merge: only KNOWN+KNOWN stays KNOWN; UNKNOWN is never promoted."""
    if not isinstance(left, SourceBatchIdentity) or not isinstance(right, SourceBatchIdentity):
        raise SchemaViolation("both operands must be SourceBatchIdentity")
    if (
        left is SourceBatchIdentity.KNOWN_SAME_BATCH
        and right is SourceBatchIdentity.KNOWN_SAME_BATCH
    ):
        return SourceBatchIdentity.KNOWN_SAME_BATCH
    return SourceBatchIdentity.UNKNOWN_IF_SAME_BATCH


def resolve_batch_order_claim(
    left_key: InformationKey, right_key: InformationKey
) -> MarketChronologyProof:
    """Reject sequence-based market-chronology claims.

    Inside one information batch (same causal coordinate) a claim that
    deterministic_sequence proves A-before-B is REJECTED. Across batches the
    answer is still UNKNOWN: S0 never proves market chronology from key order,
    row order, file order, or append order.
    """
    _require_information_key(left_key, "left_key")
    _require_information_key(right_key, "right_key")
    same_coordinate = (
        left_key.timeline_id == right_key.timeline_id
        and left_key.bar_position == right_key.bar_position
        and left_key.information_phase == right_key.information_phase
    )
    if same_coordinate:
        raise SequenceChronologyViolation(
            "deterministic_sequence is serialization only: market chronology "
            "NOT_PROVEN within one information batch"
        )
    return MarketChronologyProof.NOT_PROVEN


# ---------------------------------------------------------------------------
# Earliest lawful availability (accepted I-EARLY semantics)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AvailabilityRule:
    """Frozen derivation rule for a derived record.

    S0 does NOT compute rule satisfaction from market data. The rule DECLARES
    its required basis availability keys and the finite candidate information
    keys at which its conditions are satisfied.
    """

    rule_identity: str
    timeline_id: str
    axis: InformationAxis
    required_basis_keys: Tuple[InformationKey, ...]
    satisfaction_keys: Tuple[InformationKey, ...]

    def __post_init__(self) -> None:
        require_string(self.rule_identity, "rule_identity")
        require_string(self.timeline_id, "timeline_id")
        if not isinstance(self.axis, InformationAxis):
            raise SchemaViolation("axis must be an InformationAxis")
        for field_name, value in (
            ("required_basis_keys", self.required_basis_keys),
            ("satisfaction_keys", self.satisfaction_keys),
        ):
            if not isinstance(value, tuple):
                raise SchemaViolation(f"{field_name} must be a tuple of InformationKeys")
            for item in value:
                _require_information_key(item, field_name)
                if item.timeline_id != self.timeline_id:
                    raise IncomparableInformationKeys(
                        f"{field_name} contains a cross-timeline key: fail closed"
                    )
                if self.axis is InformationAxis.POSITIONAL and item.event_time_utc is not None:
                    raise InformationKeyViolation(
                        "POSITIONAL rule keys must not carry invented timestamps"
                    )
                if self.axis is InformationAxis.TIME_INDEXED and item.event_time_utc is None:
                    raise InformationKeyViolation(
                        "TIME_INDEXED rule keys require lawful event times"
                    )
        if not self.satisfaction_keys:
            raise SchemaViolation("satisfaction_keys must be nonempty")


def determine_fact_information_key(
    *, rule: AvailabilityRule, proposed_key: InformationKey
) -> InformationKey:
    """Return the earliest lawful fact_information_key for a derived record.

    The earliest lawful key is the earliest declared satisfaction key at which
    every required basis input is visible (public CLOSED key semantics) and
    the rule's declared conditions hold. A proposed key that is earlier than
    that is PREMATURE; a proposed key that is later with no new requirement is
    NON_EARLIEST_AVAILABILITY. S0 never chooses a later availability just
    because a caller supplied it.

    Single-scan computation (O(R + S)): the latest required-basis visibility
    key is determined only if all basis keys are legally comparable under the
    public CLOSED key semantics (any conflict raises InformationKeyError and
    fails closed as IncomparableInformationKeys), then the earliest
    satisfaction key legally at/after that boundary is found in one scan.
    Input ordering never determines the answer.
    """
    if not isinstance(rule, AvailabilityRule):
        raise SchemaViolation("rule must be an AvailabilityRule")
    _require_information_key(proposed_key, "proposed_key")
    if proposed_key.timeline_id != rule.timeline_id:
        raise IncomparableInformationKeys(
            "proposed key is cross-timeline to the rule: fail closed"
        )

    boundary = None
    for basis in rule.required_basis_keys:
        try:
            if boundary is None or basis > boundary:
                boundary = basis
        except InformationKeyError as exc:
            raise IncomparableInformationKeys(
                "required-basis keys are not legally comparable; fail closed"
            ) from exc

    earliest = None
    for candidate in rule.satisfaction_keys:
        try:
            sufficient = boundary is None or boundary <= candidate
        except InformationKeyError as exc:
            raise IncomparableInformationKeys(
                "basis visibility comparability cannot be established; fail closed"
            ) from exc
        if sufficient:
            try:
                if earliest is None or candidate < earliest:
                    earliest = candidate
            except InformationKeyError as exc:
                raise IncomparableInformationKeys(
                    "earliest lawful key cannot be established; fail closed"
                ) from exc
    if earliest is None:
        raise SchemaViolation(
            "availability rule declares no lawful candidate key "
            "(no satisfaction key exposes all required basis inputs)"
        )

    try:
        if proposed_key == earliest:
            return earliest
        if proposed_key > earliest:
            raise NonEarliestAvailability(
                "NON_EARLIEST_AVAILABILITY: proposed key is later than the "
                "earliest lawful key and no new requirement justifies it"
            )
        raise PrematureAvailability(
            "proposed availability key precedes the earliest lawful key"
        )
    except InformationKeyError as exc:
        raise IncomparableInformationKeys(
            "proposed key is not comparable to the earliest lawful key; fail closed"
        ) from exc

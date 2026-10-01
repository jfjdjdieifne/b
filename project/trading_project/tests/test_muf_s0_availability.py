"""S0 availability tests: InformationKey binding, batches, earliest availability.

Attacks covered: 02, 03, 04, 05, 06, 13, 14, 15. Deterministic sequence and
row/file/append order never prove market chronology; TIE_ORDER_CONTRACT stays
NOT_PROVEN.
"""
import pandas as pd
import pytest

from trading_system.market_understanding.availability import (
    AvailabilityRule,
    BatchRelation,
    InformationAxis,
    InformationBatchKey,
    InformationKeyBinding,
    MarketChronologyProof,
    SourceBatchIdentity,
    combine_source_batch_status,
    determine_fact_information_key,
    information_batch_relation,
    require_visible_at,
    resolve_batch_order_claim,
)
from trading_system.market_understanding.contracts import (
    IllegalCausalReference,
    IncomparableInformationKeys,
    InformationKeyViolation,
    NonEarliestAvailability,
    PrematureAvailability,
    SchemaViolation,
    SequenceChronologyViolation,
    TypedState,
)
from trading_system.research.information_time import (
    INFORMATION_KEY_VERSION,
    InformationKey,
    InformationKeyError,
    InformationPhase,
    TimeIndexedTimelineAdapter,
    TimelineAdapterError,
)
from trading_system.sources import TIE_ORDER_CONTRACT


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


def _time_key(bar_position, timestamp, phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
              sequence=0, timeline_id="TL"):
    return _key(
        timeline_id=timeline_id,
        bar_position=bar_position,
        phase=phase,
        sequence=sequence,
        event_time_utc=pd.Timestamp(timestamp, tz="UTC"),
    )


def test_attack02_positional_invented_timestamp_rejected():
    plain = _key()
    binding = InformationKeyBinding(key=plain, axis=InformationAxis.POSITIONAL)
    assert binding.key is plain
    stamped = _key(event_time_utc=pd.Timestamp("2026-05-01", tz="UTC"))
    with pytest.raises(InformationKeyViolation):
        InformationKeyBinding(key=stamped, axis=InformationAxis.POSITIONAL)
    with pytest.raises(InformationKeyViolation):
        InformationKeyBinding(key=plain, axis=InformationAxis.TIME_INDEXED)


def test_attack03_unlawful_time_indexed_time_rejected():
    with pytest.raises(InformationKeyError):
        _key(event_time_utc=pd.Timestamp("2026-05-01"))
    adapter = TimeIndexedTimelineAdapter(timeline_id="TL")
    with pytest.raises(TimelineAdapterError):
        adapter.validate_index(pd.DatetimeIndex([pd.Timestamp("2026-05-01")]))
    lawful = _time_key(0, "2026-05-01")
    InformationKeyBinding(key=lawful, axis=InformationAxis.TIME_INDEXED)


def test_attack04_bar_pre_close_completed_fact_rejected():
    completed = _key(bar_position=3, phase=InformationPhase.COMPLETED_ROW_AVAILABLE)
    pre_close = _key(bar_position=3, phase=InformationPhase.BAR_PRE_CLOSE)
    with pytest.raises(IllegalCausalReference):
        require_visible_at(fact_key=completed, at_key=pre_close)
    require_visible_at(fact_key=pre_close, at_key=completed)
    future_completed = _key(bar_position=5, phase=InformationPhase.COMPLETED_ROW_AVAILABLE)
    with pytest.raises(IllegalCausalReference):
        require_visible_at(fact_key=future_completed, at_key=pre_close)


def test_attack05_same_batch_sequence_chronology_rejected():
    left = _key(bar_position=2, sequence=0)
    right = _key(bar_position=2, sequence=1)
    with pytest.raises(SequenceChronologyViolation):
        resolve_batch_order_claim(left, right)
    with pytest.raises(SequenceChronologyViolation):
        resolve_batch_order_claim(right, left)
    across = _key(bar_position=3, sequence=0)
    verdict = resolve_batch_order_claim(left, across)
    assert verdict is MarketChronologyProof.NOT_PROVEN


def test_attack06_unknown_batch_never_promoted():
    unknown = InformationBatchKey(
        timeline_id="TL",
        axis=InformationAxis.POSITIONAL,
        causal_position=0,
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        source_batch_status=SourceBatchIdentity.UNKNOWN_IF_SAME_BATCH,
        source_batch_ref=TypedState.UNAVAILABLE,
    )
    known = InformationBatchKey(
        timeline_id="TL",
        axis=InformationAxis.POSITIONAL,
        causal_position=0,
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        source_batch_status=SourceBatchIdentity.KNOWN_SAME_BATCH,
        source_batch_ref="BATCH_1",
    )
    assert information_batch_relation(unknown, known) is BatchRelation.UNKNOWN_IF_SAME_BATCH
    assert information_batch_relation(unknown, unknown) is BatchRelation.UNKNOWN_IF_SAME_BATCH
    assert information_batch_relation(known, known) is BatchRelation.KNOWN_SAME_BATCH
    assert combine_source_batch_status(
        SourceBatchIdentity.UNKNOWN_IF_SAME_BATCH, SourceBatchIdentity.KNOWN_SAME_BATCH
    ) is SourceBatchIdentity.UNKNOWN_IF_SAME_BATCH
    assert combine_source_batch_status(
        SourceBatchIdentity.KNOWN_SAME_BATCH, SourceBatchIdentity.UNKNOWN_IF_SAME_BATCH
    ) is SourceBatchIdentity.UNKNOWN_IF_SAME_BATCH
    assert combine_source_batch_status(
        SourceBatchIdentity.KNOWN_SAME_BATCH, SourceBatchIdentity.KNOWN_SAME_BATCH
    ) is SourceBatchIdentity.KNOWN_SAME_BATCH
    with pytest.raises(SchemaViolation):
        InformationBatchKey(
            timeline_id="TL",
            axis=InformationAxis.POSITIONAL,
            causal_position=0,
            information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
            source_batch_status=SourceBatchIdentity.KNOWN_SAME_BATCH,
            source_batch_ref=TypedState.UNAVAILABLE,
        )


def test_information_batch_relations_and_tie_order_contract():
    assert TIE_ORDER_CONTRACT == "NOT_PROVEN"
    base = dict(
        timeline_id="TL",
        axis=InformationAxis.POSITIONAL,
        causal_position=0,
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        source_batch_status=SourceBatchIdentity.KNOWN_SAME_BATCH,
        source_batch_ref="BATCH_1",
    )
    other_phase = dict(base, information_phase=InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE)
    other_position = dict(base, causal_position=1)
    other_timeline = dict(base, timeline_id="TL2")
    assert information_batch_relation(
        InformationBatchKey(**base), InformationBatchKey(**other_phase)
    ) is BatchRelation.DIFFERENT_BATCH
    assert information_batch_relation(
        InformationBatchKey(**base), InformationBatchKey(**other_position)
    ) is BatchRelation.DIFFERENT_BATCH
    assert information_batch_relation(
        InformationBatchKey(**base), InformationBatchKey(**other_timeline)
    ) is BatchRelation.DIFFERENT_BATCH


def test_attack13_premature_availability_rejected():
    basis_key = _key(bar_position=5)
    rule = AvailabilityRule(
        rule_identity="RULE_1",
        timeline_id="TL",
        axis=InformationAxis.POSITIONAL,
        required_basis_keys=(basis_key,),
        satisfaction_keys=(_key(bar_position=5), _key(bar_position=7)),
    )
    with pytest.raises(PrematureAvailability):
        determine_fact_information_key(rule=rule, proposed_key=_key(bar_position=3))
    with pytest.raises(PrematureAvailability):
        determine_fact_information_key(rule=rule, proposed_key=_key(bar_position=4))


def test_attack14_non_earliest_availability_rejected():
    basis_key = _key(bar_position=5)
    rule = AvailabilityRule(
        rule_identity="RULE_1",
        timeline_id="TL",
        axis=InformationAxis.POSITIONAL,
        required_basis_keys=(basis_key,),
        satisfaction_keys=(_key(bar_position=5), _key(bar_position=7)),
    )
    with pytest.raises(NonEarliestAvailability) as exc_info:
        determine_fact_information_key(rule=rule, proposed_key=_key(bar_position=7))
    assert exc_info.value.code == "NON_EARLIEST_AVAILABILITY"
    with pytest.raises(NonEarliestAvailability):
        determine_fact_information_key(rule=rule, proposed_key=_key(bar_position=6))


def test_attack15_incomparable_keys_fail_closed():
    collision_a = _time_key(1, "2026-05-01")
    collision_b = _time_key(1, "2026-05-02")
    rule = AvailabilityRule(
        rule_identity="RULE_2",
        timeline_id="TL",
        axis=InformationAxis.TIME_INDEXED,
        required_basis_keys=(),
        satisfaction_keys=(collision_a, collision_b),
    )
    with pytest.raises(IncomparableInformationKeys) as exc_info:
        determine_fact_information_key(rule=rule, proposed_key=collision_a)
    assert exc_info.value.code == "NOT_COMPARABLE"
    with pytest.raises(IncomparableInformationKeys):
        AvailabilityRule(
            rule_identity="RULE_3",
            timeline_id="TL",
            axis=InformationAxis.POSITIONAL,
            required_basis_keys=(_key(timeline_id="OTHER"),),
            satisfaction_keys=(_key(bar_position=1),),
        )
    with pytest.raises(IncomparableInformationKeys):
        determine_fact_information_key(
            rule=AvailabilityRule(
                rule_identity="RULE_4",
                timeline_id="TL",
                axis=InformationAxis.POSITIONAL,
                required_basis_keys=(),
                satisfaction_keys=(_key(bar_position=1),),
            ),
            proposed_key=_key(timeline_id="OTHER"),
        )


def test_earliest_lawful_key_returned_not_caller_choice():
    basis_key = _key(bar_position=5)
    earliest = _key(bar_position=5)
    rule = AvailabilityRule(
        rule_identity="RULE_1",
        timeline_id="TL",
        axis=InformationAxis.POSITIONAL,
        required_basis_keys=(basis_key,),
        satisfaction_keys=(earliest, _key(bar_position=7)),
    )
    result = determine_fact_information_key(rule=rule, proposed_key=_key(bar_position=5))
    assert result == earliest
    assert result.bar_position == 5

# ===========================================================================
# P1 earliest O(R+S) (B3) — tests I..L (reference = pre-patch fixture only)
# ===========================================================================
import itertools  # noqa: E402
import random  # noqa: E402


def _rule(basis_keys, satisfaction_keys, *, axis=InformationAxis.POSITIONAL,
          rule_identity="RULE_P1"):
    return AvailabilityRule(
        rule_identity=rule_identity,
        timeline_id="TL",
        axis=axis,
        required_basis_keys=tuple(basis_keys),
        satisfaction_keys=tuple(satisfaction_keys),
    )


def _pre_patch_earliest(rule):
    """Verbatim pre-patch O(R x S) algorithm, frozen in this test fixture.

    Test-fixture-only reference for semantic equivalence (task P1 B3).
    """
    candidates = []
    for candidate in rule.satisfaction_keys:
        if all(basis <= candidate for basis in rule.required_basis_keys):
            candidates.append(candidate)
    if not candidates:
        raise SchemaViolation("no lawful candidate key")
    earliest = candidates[0]
    for candidate in candidates[1:]:
        if candidate < earliest:
            earliest = candidate
    return earliest


def test_p1_i_earliest_matches_pre_patch_reference_fixture():
    grid = [
        _key(bar_position=p, phase=phase, sequence=s)
        for p in range(6)
        for phase in (
            InformationPhase.BAR_PRE_CLOSE,
            InformationPhase.COMPLETED_ROW_AVAILABLE,
            InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE,
        )
        for s in (0, 1)
    ]
    rng = random.Random(1234)
    proposed = grid[0]
    for _ in range(30):
        basis = rng.sample(grid, rng.randint(0, 3))
        satisfaction = rng.sample(grid, rng.randint(1, 5))
        rule = _rule(basis, satisfaction)
        try:
            expected = _pre_patch_earliest(rule)
        except SchemaViolation:
            with pytest.raises(SchemaViolation):
                determine_fact_information_key(rule=rule, proposed_key=proposed)
            continue
        assert determine_fact_information_key(rule=rule, proposed_key=expected) == expected
        later = [k for k in grid if k > expected]
        if later:
            with pytest.raises(NonEarliestAvailability):
                determine_fact_information_key(rule=rule, proposed_key=later[0])
        earlier = [k for k in grid if k < expected]
        if earlier:
            with pytest.raises(PrematureAvailability):
                determine_fact_information_key(rule=rule, proposed_key=earlier[0])
    # empty basis: earliest = earliest declared satisfaction key
    rule = _rule((), grid)
    assert determine_fact_information_key(rule=rule, proposed_key=grid[0]) == grid[0]
    assert _pre_patch_earliest(rule) == grid[0]


def test_p1_j_earliest_permutation_invariant():
    basis_a = _key(bar_position=2, phase=InformationPhase.BAR_PRE_CLOSE)
    basis_b = _key(bar_position=2, phase=InformationPhase.COMPLETED_ROW_AVAILABLE)
    early = _key(bar_position=1)  # insufficient (before the basis boundary)
    exact = _key(bar_position=2, phase=InformationPhase.RESEARCH_SNAPSHOT_AVAILABLE)
    late = _key(bar_position=4)
    satisfaction = (late, early, exact, basis_a)
    for basis_order in itertools.permutations((basis_a, basis_b)):
        for order in itertools.permutations(satisfaction):
            rule = _rule(basis_order, order)
            assert determine_fact_information_key(rule=rule, proposed_key=exact) == exact
    rule = _rule((basis_a, basis_b), satisfaction)
    with pytest.raises(NonEarliestAvailability):
        determine_fact_information_key(rule=rule, proposed_key=late)
    with pytest.raises(PrematureAvailability):
        determine_fact_information_key(rule=rule, proposed_key=early)


_CMP_COUNT = {"n": 0}


class _CountingKey(InformationKey):
    """InformationKey probe that counts public comparison operations."""

    def __le__(self, other):
        _CMP_COUNT["n"] += 1
        return super().__le__(other)

    def __lt__(self, other):
        _CMP_COUNT["n"] += 1
        return super().__lt__(other)

    def __gt__(self, other):
        _CMP_COUNT["n"] += 1
        return super().__gt__(other)

    def __ge__(self, other):
        _CMP_COUNT["n"] += 1
        return super().__ge__(other)

    def __eq__(self, other):
        _CMP_COUNT["n"] += 1
        return super().__eq__(other)


def _counting_key(bar_position):
    return _CountingKey(
        information_key_version=INFORMATION_KEY_VERSION,
        timeline_id="TL",
        bar_position=bar_position,
        event_time_utc=None,
        information_phase=InformationPhase.COMPLETED_ROW_AVAILABLE,
        deterministic_sequence=0,
    )


def test_p1_k_earliest_comparison_count_scales_linearly():
    def count_for(n):
        basis = tuple(_counting_key(i) for i in range(n))
        satisfaction = tuple(_counting_key(n + i) for i in range(n))
        rule = _rule(basis, satisfaction)
        _CMP_COUNT["n"] = 0
        determine_fact_information_key(rule=rule, proposed_key=satisfaction[0])
        return _CMP_COUNT["n"]

    counts = [count_for(n) for n in (256, 512, 1024)]
    ratio_2x = counts[1] / counts[0]
    ratio_4x = counts[2] / counts[0]
    # linear model (R+S); the pre-patch R x S cross-product would quadruple
    assert 1.6 <= ratio_2x <= 2.8, counts
    assert 3.2 <= ratio_4x <= 5.6, counts


def test_p1_l_incomparable_keys_fail_in_documented_error_family():
    # (1) cross-timeline basis keys: rejected in the documented family
    with pytest.raises(IncomparableInformationKeys) as exc_info:
        _rule((_key(bar_position=1), _key(timeline_id="TL_B", bar_position=2)),
              (_key(bar_position=3),))
    assert exc_info.value.code == "NOT_COMPARABLE"
    # (2) same causal coordinate, conflicting timestamp provenance (basis side)
    rule2 = _rule(
        (_time_key(1, "2026-05-01"), _time_key(1, "2026-05-02")),
        (_time_key(2, "2026-05-03"),),
        axis=InformationAxis.TIME_INDEXED,
    )
    with pytest.raises(IncomparableInformationKeys) as exc_info:
        determine_fact_information_key(rule=rule2, proposed_key=_time_key(2, "2026-05-03"))
    assert exc_info.value.code == "NOT_COMPARABLE"
    # (3) same coordinate conflict inside satisfaction keys
    rule3 = _rule(
        (_time_key(1, "2026-05-01"),),
        (_time_key(2, "2026-05-02"), _time_key(2, "2026-05-03")),
        axis=InformationAxis.TIME_INDEXED,
    )
    with pytest.raises(IncomparableInformationKeys) as exc_info:
        determine_fact_information_key(rule=rule3, proposed_key=_time_key(2, "2026-05-02"))
    assert exc_info.value.code == "NOT_COMPARABLE"
    # (4) proposed cross-timeline key
    rule4 = _rule((_key(bar_position=1),), (_key(bar_position=2),))
    with pytest.raises(IncomparableInformationKeys) as exc_info:
        determine_fact_information_key(rule=rule4, proposed_key=_key(timeline_id="TL_B"))
    assert exc_info.value.code == "NOT_COMPARABLE"

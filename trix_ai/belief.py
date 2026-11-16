"""Exact Probabilistic Belief Tracker & Zero-Rejection Combinatorial World Sampler.

Deduces:
1. Exact played cards and remaining unseen cards.
2. Exact suit voids from trick-taking history.
3. Exact forbidden cards from Trix pass history.
4. Exact known card owners from doubling declarations.
5. Fixpoint constraint propagation (locks all mathematically forced cards).
6. Exact closed-form combinatorial distribution over the 4 domain buckets
   (B_01, B_02, B_12, B_012) yielding:
   - Exact marginal probabilities P(seat holds card) with ZERO Monte Carlo error.
   - Exact uniform / Bayesian-weighted world sampling with ZERO rejection.
"""

from __future__ import annotations

import math
import random
from typing import Optional

from .cards import (
    ALL_CARDS_MASK,
    CARD_BIT,
    CARD_RANK,
    CARD_SUIT,
    HEARTS_MASK,
    KING_OF_HEARTS,
    QUEENS,
    SUIT_MASKS,
    mask_to_cards,
)
from .engine import CONTRACT_KH, CONTRACT_QUEENS, RoundObservation

_FACT: tuple[int, ...] = tuple(math.factorial(i) for i in range(53))
_COMB: list[list[int]] = [
    [math.comb(n, k) if 0 <= k <= n else 0 for k in range(53)] for n in range(53)
]


class BeliefState:
    """Exact belief state from the perspective of `my_seat`."""

    __slots__ = (
        "my_seat",
        "other_seats",
        "obs",
        "unseen_mask",
        "need",
        "possible",
        "definite",
        "void_suits",
        "b01",
        "b02",
        "b12",
        "b012",
        "rem_need",
        "splits",
        "split_cum_weights",
        "total_worlds",
        "card_probs",
    )

    def __init__(self, obs: RoundObservation) -> None:
        self.obs = obs
        self.my_seat: int = obs.seat
        self.other_seats: tuple[int, int, int] = tuple(
            s for s in range(4) if s != obs.seat
        )  # type: ignore[assignment]

        self.unseen_mask: int = ALL_CARDS_MASK ^ obs.played_mask ^ obs.my_hand_mask
        self.need: list[int] = [obs.hand_counts[p] for p in self.other_seats]
        self.possible: list[int] = [
            self.unseen_mask if self.need[i] > 0 else 0 for i in range(3)
        ]
        self.definite: list[int] = [0, 0, 0]
        self.void_suits: dict[int, set[int]] = {p: set() for p in self.other_seats}

        seat_to_idx = {p: i for i, p in enumerate(self.other_seats)}

        # 1. Known owners from doubling declarations
        for card, doubler in obs.doubled_cards.items():
            bit = CARD_BIT[card]
            if (self.unseen_mask & bit) and doubler != self.my_seat:
                idx = seat_to_idx[doubler]
                self.definite[idx] |= bit
                for j in range(3):
                    if j != idx:
                        self.possible[j] &= ~bit

        # 2. Hard deductions from event history
        for ev in obs.events:
            kind = ev[0]
            if kind == "play":
                _, p, card, led_suit = ev
                if p != self.my_seat and CARD_SUIT[card] != led_suit:
                    idx = seat_to_idx[p]
                    self.void_suits[p].add(led_suit)
                    self.possible[idx] &= ~SUIT_MASKS[led_suit]
            elif kind == "trix_pass":
                _, p, playable_mask = ev
                if p != self.my_seat:
                    idx = seat_to_idx[p]
                    self.possible[idx] &= ~playable_mask

        # 3. Fixpoint constraint propagation
        self._propagate()

        # Also update void_suits from propagated possible masks
        for i, p in enumerate(self.other_seats):
            for s in range(4):
                if (self.unseen_mask & SUIT_MASKS[s]) and not (
                    self.possible[i] & SUIT_MASKS[s]
                ):
                    self.void_suits[p].add(s)

        # 4. Partition remaining free cards into exact domain buckets
        locked_all = self.definite[0] | self.definite[1] | self.definite[2]
        free_mask = self.unseen_mask ^ locked_all
        self.rem_need: list[int] = [
            self.need[i] - self.definite[i].bit_count() for i in range(3)
        ]

        p0, p1, p2 = self.possible
        # Note: After propagation, every free card is in at least 2 of (p0, p1, p2)
        m012 = free_mask & p0 & p1 & p2
        m01 = (free_mask & p0 & p1) ^ m012
        m02 = (free_mask & p0 & p2) ^ m012
        m12 = (free_mask & p1 & p2) ^ m012

        self.b01: list[int] = mask_to_cards(m01)
        self.b02: list[int] = mask_to_cards(m02)
        self.b12: list[int] = mask_to_cards(m12)
        self.b012: list[int] = mask_to_cards(m012)

        # 5. Compute exact combinatorial distribution over (x01, x02, x12)
        self.splits: list[tuple[int, int, int, int, int, int]] = []
        self.split_cum_weights: list[int] = []
        self.total_worlds: int = 0
        self.card_probs: dict[int, tuple[float, float, float, float]] = {}
        self._solve_combinatorics()

    def _propagate(self) -> None:
        changed = True
        while changed:
            changed = False
            # Ensure definite cards are excluded from other opponents
            for i in range(3):
                di = self.definite[i]
                if di:
                    for j in range(3):
                        if j != i and (self.possible[j] & di):
                            self.possible[j] &= ~di
                            changed = True

            # Unique possible owner for any unseen card
            p0, p1, p2 = self.possible
            only0 = p0 & ~p1 & ~p2
            only1 = p1 & ~p0 & ~p2
            only2 = p2 & ~p0 & ~p1
            if only0 & ~self.definite[0]:
                self.definite[0] |= only0
                changed = True
            if only1 & ~self.definite[1]:
                self.definite[1] |= only1
                changed = True
            if only2 & ~self.definite[2]:
                self.definite[2] |= only2
                changed = True

            # Count saturation checks
            for i in range(3):
                if self.definite[i].bit_count() == self.need[i]:
                    if self.possible[i] != self.definite[i]:
                        self.possible[i] = self.definite[i]
                        changed = True
                elif self.possible[i].bit_count() == self.need[i]:
                    if self.definite[i] != self.possible[i]:
                        self.definite[i] = self.possible[i]
                        changed = True

    def _solve_combinatorics(self) -> None:
        n01 = len(self.b01)
        n02 = len(self.b02)
        n12 = len(self.b12)
        n012 = len(self.b012)
        r0, r1, r2 = self.rem_need

        fact_012 = _FACT[n012]
        comb_01 = _COMB[n01]
        comb_02 = _COMB[n02]
        comb_12 = _COMB[n12]

        splits: list[tuple[int, int, int, int, int, int]] = []
        cum_w: list[int] = []
        total = 0

        # Accumulators for exact marginal probabilities
        sum_x01 = 0
        sum_x02 = 0
        sum_x12 = 0
        sum_y0 = 0
        sum_y1 = 0
        sum_y2 = 0

        max_x01 = min(n01, r0)
        for x01 in range(max_x01 + 1):
            w01 = comb_01[x01]
            rem_r0_after_01 = r0 - x01
            rem_r1_after_01 = r1 - (n01 - x01)
            if rem_r1_after_01 < 0:
                continue
            max_x02 = min(n02, rem_r0_after_01)
            for x02 in range(max_x02 + 1):
                y0 = rem_r0_after_01 - x02
                rem_r2_after_02 = r2 - (n02 - x02)
                if rem_r2_after_02 < 0:
                    continue
                lo_12 = max(0, n12 - rem_r2_after_02)
                hi_12 = min(n12, rem_r1_after_01)
                if lo_12 > hi_12:
                    continue
                w012_base = w01 * comb_02[x02]
                for x12 in range(lo_12, hi_12 + 1):
                    y1 = rem_r1_after_01 - x12
                    y2 = rem_r2_after_02 - (n12 - x12)
                    # Exact number of valid assignments for this count vector
                    w = (
                        w012_base
                        * comb_12[x12]
                        * (fact_012 // (_FACT[y0] * _FACT[y1] * _FACT[y2]))
                    )
                    if w > 0:
                        total += w
                        splits.append((x01, x02, x12, y0, y1, y2))
                        cum_w.append(total)
                        sum_x01 += w * x01
                        sum_x02 += w * x02
                        sum_x12 += w * x12
                        sum_y0 += w * y0
                        sum_y1 += w * y1
                        sum_y2 += w * y2

        self.splits = splits
        self.split_cum_weights = cum_w
        self.total_worlds = total

        # Compute exact marginal probabilities P(seat holds card) for every unseen card
        probs: dict[int, tuple[float, float, float, float]] = {}
        o0, o1, o2 = self.other_seats

        def make_tuple(p_o0: float, p_o1: float, p_o2: float) -> tuple[float, float, float, float]:
            arr = [0.0, 0.0, 0.0, 0.0]
            arr[o0] = p_o0
            arr[o1] = p_o1
            arr[o2] = p_o2
            return (arr[0], arr[1], arr[2], arr[3])

        # Definite cards -> probability 1.0
        for idx in range(3):
            for c in mask_to_cards(self.definite[idx]):
                arr = [0.0, 0.0, 0.0, 0.0]
                arr[self.other_seats[idx]] = 1.0
                probs[c] = (arr[0], arr[1], arr[2], arr[3])

        if total > 0:
            if n01 > 0:
                p0_01 = sum_x01 / (total * n01)
                t01 = make_tuple(p0_01, 1.0 - p0_01, 0.0)
                for c in self.b01:
                    probs[c] = t01
            if n02 > 0:
                p0_02 = sum_x02 / (total * n02)
                t02 = make_tuple(p0_02, 0.0, 1.0 - p0_02)
                for c in self.b02:
                    probs[c] = t02
            if n12 > 0:
                p1_12 = sum_x12 / (total * n12)
                t12 = make_tuple(0.0, p1_12, 1.0 - p1_12)
                for c in self.b12:
                    probs[c] = t12
            if n012 > 0:
                py0 = sum_y0 / (total * n012)
                py1 = sum_y1 / (total * n012)
                py2 = sum_y2 / (total * n012)
                t012 = make_tuple(py0, py1, py2)
                for c in self.b012:
                    probs[c] = t012

        self.card_probs = probs

    def prob_seat_has(self, seat: int, card: int) -> float:
        if seat == self.my_seat:
            return 1.0 if (self.obs.my_hand_mask & CARD_BIT[card]) else 0.0
        if self.obs.played_mask & CARD_BIT[card]:
            return 0.0
        t = self.card_probs.get(card)
        return t[seat] if t is not None else 0.0

    def prob_seat_void(self, seat: int, suit: int) -> float:
        """Approximate/exact probability that `seat` holds zero cards in `suit`."""
        if seat == self.my_seat:
            return 1.0 if (self.obs.my_hand_mask & SUIT_MASKS[suit]) == 0 else 0.0
        if suit in self.void_suits[seat]:
            return 1.0
        rem_suit = self.unseen_mask & SUIT_MASKS[suit]
        if rem_suit == 0:
            return 1.0
        idx = self.other_seats.index(seat)
        if self.definite[idx] & SUIT_MASKS[suit]:
            return 0.0
        # Fast accurate product estimate over unseen cards in suit
        p_void = 1.0
        for c in mask_to_cards(rem_suit):
            p_void *= max(0.0, 1.0 - self.prob_seat_has(seat, c))
        return p_void

    def sample_hands(self, rng: random.Random) -> list[int]:
        """Draw one exact uniform valid 4-player hand assignment [h0, h1, h2, h3]."""
        hands = [0, 0, 0, 0]
        hands[self.my_seat] = self.obs.my_hand_mask

        o0, o1, o2 = self.other_seats
        h0 = self.definite[0]
        h1 = self.definite[1]
        h2 = self.definite[2]

        if self.splits:
            # Binary search on cumulative weights
            r = rng.randrange(self.total_worlds)
            lo = 0
            hi = len(self.split_cum_weights) - 1
            while lo < hi:
                mid = (lo + hi) >> 1
                if r < self.split_cum_weights[mid]:
                    hi = mid
                else:
                    lo = mid + 1
            x01, x02, x12, y0, y1, _y2 = self.splits[lo]

            if self.b01:
                arr = self.b01.copy()
                rng.shuffle(arr)
                for c in arr[:x01]:
                    h0 |= CARD_BIT[c]
                for c in arr[x01:]:
                    h1 |= CARD_BIT[c]
            if self.b02:
                arr = self.b02.copy()
                rng.shuffle(arr)
                for c in arr[:x02]:
                    h0 |= CARD_BIT[c]
                for c in arr[x02:]:
                    h2 |= CARD_BIT[c]
            if self.b12:
                arr = self.b12.copy()
                rng.shuffle(arr)
                for c in arr[:x12]:
                    h1 |= CARD_BIT[c]
                for c in arr[x12:]:
                    h2 |= CARD_BIT[c]
            if self.b012:
                arr = self.b012.copy()
                rng.shuffle(arr)
                for c in arr[:y0]:
                    h0 |= CARD_BIT[c]
                for c in arr[y0 : y0 + y1]:
                    h1 |= CARD_BIT[c]
                for c in arr[y0 + y1 :]:
                    h2 |= CARD_BIT[c]

        hands[o0] = h0
        hands[o1] = h1
        hands[o2] = h2
        return hands

    def world_bayesian_weight(self, hands: list[int]) -> float:
        """Soft Bayesian behavioral likelihood for a sampled world.

        Adjusts world weights based on public signals (like doubling confidence).
        Kept gently bounded so hard constraints dominate and never overfit.
        """
        w = 1.0
        obs = self.obs
        if obs.contract == CONTRACT_KH and KING_OF_HEARTS in obs.doubled_cards:
            doubler = obs.doubled_cards[KING_OF_HEARTS]
            if doubler != self.my_seat:
                # A player who doubled K♥ likely has protective hearts or a short suit
                h_cnt = (hands[doubler] & HEARTS_MASK).bit_count()
                if h_cnt >= 3:
                    w *= 1.35
                elif h_cnt == 1:
                    w *= 0.65
        elif obs.contract == CONTRACT_QUEENS and obs.doubled_cards:
            for q, doubler in obs.doubled_cards.items():
                if doubler != self.my_seat and (hands[doubler] & CARD_BIT[q]):
                    s = CARD_SUIT[q]
                    cnt = (hands[doubler] & SUIT_MASKS[s]).bit_count()
                    if cnt >= 3:
                        w *= 1.25
                    elif cnt == 1:
                        w *= 0.7
        return w

    def sample_weighted_worlds(
        self, count: int, rng: random.Random
    ) -> list[tuple[list[int], float]]:
        """Sample `count` consistent worlds with Bayesian weights."""
        if self.total_worlds <= 1:
            return [(self.sample_hands(rng), 1.0)]
        out: list[tuple[list[int], float]] = []
        for _ in range(count):
            h = self.sample_hands(rng)
            out.append((h, self.world_bayesian_weight(h)))
        return out

    def summary_dict(self) -> dict:
        """Human-readable structured belief summary for UI/analysis."""
        known_cards = {}
        for idx, p in enumerate(self.other_seats):
            if self.definite[idx]:
                known_cards[p] = mask_to_cards(self.definite[idx])
        key_probs = {}
        if self.obs.contract == CONTRACT_KH and (self.unseen_mask & CARD_BIT[KING_OF_HEARTS]):
            key_probs[KING_OF_HEARTS] = {
                s: round(self.prob_seat_has(s, KING_OF_HEARTS), 3) for s in range(4)
            }
        elif self.obs.contract == CONTRACT_QUEENS:
            for q in QUEENS:
                if self.unseen_mask & CARD_BIT[q]:
                    key_probs[q] = {
                        s: round(self.prob_seat_has(s, q), 3) for s in range(4)
                    }
        return {
            "total_consistent_worlds": self.total_worlds,
            "void_suits": {p: sorted(list(vs)) for p, vs in self.void_suits.items()},
            "proven_cards": known_cards,
            "key_card_probs": key_probs,
        }

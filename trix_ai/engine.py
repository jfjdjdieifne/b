"""Complete Individual Trix (تريكس فردي) Rules Engine.

Implements classic 4-player Individual Trix:
- 4 Kingdoms (20 rounds total), first King determined by 7♥ on deal 1.
- 5 Contracts per Kingdom:
    1. king_of_hearts (شيخ الكبة): -75 for K♥ (doublable: -150 / +75)
    2. queens (البنات): -25 per Queen (doublable: -50 / +25 each)
    3. diamonds (الديناري): -10 per Diamond
    4. collections (اللطوش): -15 per trick won
    5. trix (التريكس): Layout game (+200 / +150 / +100 / +50)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .cards import (
    ALL_CARDS_MASK,
    CARD_BIT,
    CARD_RANK,
    CARD_SUIT,
    DIAMONDS_MASK,
    KING_OF_HEARTS,
    KING_OF_HEARTS_BIT,
    QUEENS,
    QUEENS_MASK,
    RANK_J,
    SEVEN_OF_HEARTS,
    SUIT_MASKS,
    mask_to_cards,
)

CONTRACT_KH = "king_of_hearts"
CONTRACT_QUEENS = "queens"
CONTRACT_DIAMONDS = "diamonds"
CONTRACT_COLLECTIONS = "collections"
CONTRACT_TRIX = "trix"

CONTRACTS: tuple[str, ...] = (
    CONTRACT_KH,
    CONTRACT_QUEENS,
    CONTRACT_DIAMONDS,
    CONTRACT_COLLECTIONS,
    CONTRACT_TRIX,
)

CONTRACT_AR: dict[str, str] = {
    CONTRACT_KH: "شيخ الكبة",
    CONTRACT_QUEENS: "البنات",
    CONTRACT_DIAMONDS: "الديناري",
    CONTRACT_COLLECTIONS: "اللطوش",
    CONTRACT_TRIX: "التريكس",
}

PASS_ACTION = -1
TRIX_FINISH_SCORES = (200, 150, 100, 50)


def deal_hands(rng: random.Random) -> list[int]:
    """Deal 52 cards randomly into 4 integer hand bitmasks of 13 cards each."""
    deck = list(range(52))
    rng.shuffle(deck)
    hands = [0, 0, 0, 0]
    for i, c in enumerate(deck):
        hands[i // 13] |= 1 << c
    return hands


@dataclass
class RoundObservation:
    """Strictly sanitized observation for one player (no hidden opponent cards)."""

    seat: int
    contract: str
    king_seat: int
    my_hand_mask: int
    hand_counts: tuple[int, int, int, int]
    played_mask: int
    current_player: int
    scores: tuple[int, int, int, int]
    match_scores: tuple[int, int, int, int]
    doubled_cards: dict[int, int]  # card_id -> doubler_seat
    # Trick-taking fields
    trick_number: int
    trick_leader: int
    current_trick: tuple[tuple[int, int], ...]  # ((seat, card), ...)
    completed_tricks: tuple[tuple[int, tuple[tuple[int, int], ...], int], ...]  # (leader, plays, winner)
    # Trix layout fields
    layout_low: tuple[int, int, int, int]
    layout_high: tuple[int, int, int, int]
    trix_finish_order: tuple[int, ...]
    # Event log for belief tracking:
    # ("play", seat, card, led_suit) or ("trix_play", seat, card) or ("trix_pass", seat, legal_playable_mask)
    events: tuple[tuple, ...]
    done: bool


class TrixRound:
    """Single round of Individual Trix for any of the 5 contracts."""

    __slots__ = (
        "contract",
        "king_seat",
        "hands",
        "played_mask",
        "current_player",
        "scores",
        "match_scores",
        "doubled_cards",
        "trick_number",
        "trick_leader",
        "current_trick",
        "completed_tricks",
        "layout_low",
        "layout_high",
        "trix_finish_order",
        "events",
        "done",
        "tricks_won",
    )

    def __init__(
        self,
        contract: str,
        king_seat: int,
        hands: list[int],
        match_scores: Optional[list[int]] = None,
        doubled_cards: Optional[dict[int, int]] = None,
    ) -> None:
        if contract not in CONTRACTS:
            raise ValueError(f"Invalid contract: {contract}")
        self.contract: str = contract
        self.king_seat: int = king_seat
        self.hands: list[int] = list(hands)
        self.played_mask: int = 0
        self.current_player: int = king_seat
        self.scores: list[int] = [0, 0, 0, 0]
        self.match_scores: list[int] = list(match_scores) if match_scores else [0, 0, 0, 0]
        self.doubled_cards: dict[int, int] = dict(doubled_cards) if doubled_cards else {}
        self.trick_number: int = 0
        self.trick_leader: int = king_seat
        self.current_trick: list[tuple[int, int]] = []
        self.completed_tricks: list[tuple[int, tuple[tuple[int, int], ...], int]] = []
        self.layout_low: list[int] = [-1, -1, -1, -1]
        self.layout_high: list[int] = [-1, -1, -1, -1]
        self.trix_finish_order: list[int] = []
        self.events: list[tuple] = []
        self.done: bool = False
        self.tricks_won: list[int] = [0, 0, 0, 0]

    def clone(self) -> TrixRound:
        r = TrixRound.__new__(TrixRound)
        r.contract = self.contract
        r.king_seat = self.king_seat
        r.hands = self.hands.copy()
        r.played_mask = self.played_mask
        r.current_player = self.current_player
        r.scores = self.scores.copy()
        r.match_scores = self.match_scores.copy()
        r.doubled_cards = self.doubled_cards.copy()
        r.trick_number = self.trick_number
        r.trick_leader = self.trick_leader
        r.current_trick = self.current_trick.copy()
        r.completed_tricks = self.completed_tricks.copy()
        r.layout_low = self.layout_low.copy()
        r.layout_high = self.layout_high.copy()
        r.trix_finish_order = self.trix_finish_order.copy()
        r.events = self.events.copy()
        r.done = self.done
        r.tricks_won = self.tricks_won.copy()
        return r

    def apply_double(self, seat: int, card: int) -> None:
        """Declare a double on K♥ (in KH) or a Queen (in Queens) before play starts."""
        if self.played_mask != 0 or self.current_trick:
            raise ValueError("Cannot double after play has started")
        if not (self.hands[seat] & CARD_BIT[card]):
            raise ValueError(f"Seat {seat} does not hold card {card} to double it")
        if self.contract == CONTRACT_KH:
            if card != KING_OF_HEARTS:
                raise ValueError("Only K♥ can be doubled in king_of_hearts")
        elif self.contract == CONTRACT_QUEENS:
            if card not in QUEENS:
                raise ValueError("Only Queens can be doubled in queens")
        else:
            raise ValueError(f"Doubling is not allowed in {self.contract}")
        self.doubled_cards[card] = seat

    def doubler_candidates(self, seat: int) -> list[int]:
        """Return list of cards in `seat`'s hand that are eligible to be doubled."""
        if self.played_mask != 0 or self.current_trick:
            return []
        hand = self.hands[seat]
        if self.contract == CONTRACT_KH:
            return [KING_OF_HEARTS] if (hand & KING_OF_HEARTS_BIT) else []
        if self.contract == CONTRACT_QUEENS:
            return [q for q in QUEENS if (hand & CARD_BIT[q])]
        return []

    def trix_playable_mask(self) -> int:
        """Return bitmask of all cards (in deck) currently playable on the Trix layout."""
        mask = 0
        for s in range(4):
            lo = self.layout_low[s]
            if lo == -1:
                mask |= CARD_BIT[s * 13 + RANK_J]
            else:
                if lo > 0:
                    mask |= CARD_BIT[s * 13 + lo - 1]
                hi = self.layout_high[s]
                if hi < 12:
                    mask |= CARD_BIT[s * 13 + hi + 1]
        return mask

    def legal_actions(self, seat: Optional[int] = None) -> list[int]:
        """Return list of legal actions for seat (default: current_player)."""
        if self.done:
            return []
        p = self.current_player if seat is None else seat
        hand = self.hands[p]

        if self.contract == CONTRACT_TRIX:
            if hand == 0:
                return []
            playable = hand & self.trix_playable_mask()
            if playable == 0:
                return [PASS_ACTION]
            return mask_to_cards(playable)

        # Trick-taking contract
        if not self.current_trick:
            # Leading a trick
            if self.contract == CONTRACT_KH:
                # Cannot lead K♥ if holding any other card
                if (hand & KING_OF_HEARTS_BIT) and hand != KING_OF_HEARTS_BIT:
                    return mask_to_cards(hand ^ KING_OF_HEARTS_BIT)
            return mask_to_cards(hand)

        # Following a trick: must follow led suit if possible
        led_suit = CARD_SUIT[self.current_trick[0][1]]
        in_suit = hand & SUIT_MASKS[led_suit]
        if in_suit:
            return mask_to_cards(in_suit)
        return mask_to_cards(hand)

    def legal_mask(self, seat: Optional[int] = None) -> int:
        """Fast bitmask of legal cards for trick-taking or Trix (0 means PASS in Trix)."""
        p = self.current_player if seat is None else seat
        hand = self.hands[p]
        if self.contract == CONTRACT_TRIX:
            return hand & self.trix_playable_mask()
        if not self.current_trick:
            if self.contract == CONTRACT_KH and (hand & KING_OF_HEARTS_BIT) and hand != KING_OF_HEARTS_BIT:
                return hand ^ KING_OF_HEARTS_BIT
            return hand
        led_suit = CARD_SUIT[self.current_trick[0][1]]
        in_suit = hand & SUIT_MASKS[led_suit]
        return in_suit if in_suit else hand

    def step(self, action: int) -> dict:
        """Apply action for current_player and return event summary."""
        if self.done:
            raise ValueError("Round is already finished")
        p = self.current_player

        if self.contract == CONTRACT_TRIX:
            return self._step_trix(p, action)
        return self._step_trick(p, action)

    def _step_trix(self, p: int, action: int) -> dict:
        playable_on_board = self.trix_playable_mask()
        legal = self.hands[p] & playable_on_board

        if action == PASS_ACTION:
            if legal != 0:
                raise ValueError(f"Seat {p} cannot pass when legal moves exist")
            self.events.append(("trix_pass", p, playable_on_board))
            info = {"type": "trix_pass", "seat": p, "done": False}
        else:
            bit = CARD_BIT[action]
            if not (legal & bit):
                raise ValueError(f"Illegal Trix play {action} by seat {p}")
            self.hands[p] ^= bit
            self.played_mask |= bit
            s = CARD_SUIT[action]
            r = CARD_RANK[action]
            if self.layout_low[s] == -1:
                self.layout_low[s] = r
                self.layout_high[s] = r
            elif r < self.layout_low[s]:
                self.layout_low[s] = r
            else:
                self.layout_high[s] = r
            self.events.append(("trix_play", p, action))
            info = {"type": "trix_play", "seat": p, "card": action, "done": False}

            if self.hands[p] == 0:
                place = len(self.trix_finish_order)
                self.trix_finish_order.append(p)
                self.scores[p] += TRIX_FINISH_SCORES[place]
                info["finished_place"] = place + 1
                if len(self.trix_finish_order) == 3:
                    # 4th remaining player automatically gets +50
                    for rem in range(4):
                        if rem not in self.trix_finish_order:
                            self.trix_finish_order.append(rem)
                            self.scores[rem] += TRIX_FINISH_SCORES[3]
                            break
                    self.done = True
                    info["done"] = True
                    return info

        # Advance to next unfinished player
        nxt = (p + 1) & 3
        while self.hands[nxt] == 0:
            nxt = (nxt + 1) & 3
        self.current_player = nxt
        return info

    def _step_trick(self, p: int, card: int) -> dict:
        legal = self.legal_mask(p)
        bit = CARD_BIT[card]
        if not (legal & bit):
            raise ValueError(f"Illegal play {card} by seat {p} in {self.contract}")

        led_suit = CARD_SUIT[card] if not self.current_trick else CARD_SUIT[self.current_trick[0][1]]
        self.hands[p] ^= bit
        self.played_mask |= bit
        self.current_trick.append((p, card))
        self.events.append(("play", p, card, led_suit))

        if len(self.current_trick) < 4:
            self.current_player = (p + 1) & 3
            return {
                "type": "card_play",
                "seat": p,
                "card": card,
                "trick_complete": False,
                "done": False,
            }

        # Complete the trick: highest rank of led_suit wins
        winner = self.current_trick[0][0]
        win_rank = CARD_RANK[self.current_trick[0][1]]
        trick_mask = 0
        for seat_i, card_i in self.current_trick:
            trick_mask |= CARD_BIT[card_i]
            if CARD_SUIT[card_i] == led_suit and CARD_RANK[card_i] > win_rank:
                win_rank = CARD_RANK[card_i]
                winner = seat_i

        self.tricks_won[winner] += 1
        delta = [0, 0, 0, 0]
        c = self.contract

        if c == CONTRACT_KH:
            if trick_mask & KING_OF_HEARTS_BIT:
                if KING_OF_HEARTS in self.doubled_cards:
                    doubler = self.doubled_cards[KING_OF_HEARTS]
                    delta[winner] -= 150
                    if winner != doubler:
                        delta[doubler] += 75
                else:
                    delta[winner] -= 75
                self.done = True
        elif c == CONTRACT_QUEENS:
            q_in_trick = trick_mask & QUEENS_MASK
            if q_in_trick:
                for q in QUEENS:
                    if q_in_trick & CARD_BIT[q]:
                        if q in self.doubled_cards:
                            doubler = self.doubled_cards[q]
                            delta[winner] -= 50
                            if winner != doubler:
                                delta[doubler] += 25
                        else:
                            delta[winner] -= 25
            if (self.played_mask & QUEENS_MASK) == QUEENS_MASK:
                self.done = True
        elif c == CONTRACT_DIAMONDS:
            d_cnt = (trick_mask & DIAMONDS_MASK).bit_count()
            if d_cnt:
                delta[winner] -= 10 * d_cnt
            if (self.played_mask & DIAMONDS_MASK) == DIAMONDS_MASK:
                self.done = True
        elif c == CONTRACT_COLLECTIONS:
            delta[winner] -= 15

        for i in range(4):
            self.scores[i] += delta[i]

        completed = (self.trick_leader, tuple(self.current_trick), winner)
        self.completed_tricks.append(completed)
        self.trick_number += 1
        self.current_trick = []
        self.trick_leader = winner
        self.current_player = winner

        if self.trick_number >= 13:
            self.done = True

        return {
            "type": "trick_complete",
            "seat": p,
            "card": card,
            "trick_complete": True,
            "winner": winner,
            "delta": delta,
            "done": self.done,
        }

    def observation(self, seat: int) -> RoundObservation:
        return RoundObservation(
            seat=seat,
            contract=self.contract,
            king_seat=self.king_seat,
            my_hand_mask=self.hands[seat],
            hand_counts=(
                self.hands[0].bit_count(),
                self.hands[1].bit_count(),
                self.hands[2].bit_count(),
                self.hands[3].bit_count(),
            ),
            played_mask=self.played_mask,
            current_player=self.current_player,
            scores=tuple(self.scores),
            match_scores=tuple(self.match_scores),
            doubled_cards=dict(self.doubled_cards),
            trick_number=self.trick_number,
            trick_leader=self.trick_leader,
            current_trick=tuple(self.current_trick),
            completed_tricks=tuple(self.completed_tricks),
            layout_low=tuple(self.layout_low),
            layout_high=tuple(self.layout_high),
            trix_finish_order=tuple(self.trix_finish_order),
            events=tuple(self.events),
            done=self.done,
        )


@dataclass
class MatchRoundRecord:
    kingdom_index: int
    round_in_kingdom: int
    king_seat: int
    contract: str
    doubled_cards: dict[int, int]
    round_scores: list[int]
    cumulative_scores: list[int]


class TrixMatch:
    """Full 4-Kingdom (20-round) Individual Trix match manager."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)
        self.scores: list[int] = [0, 0, 0, 0]
        self.kingdom_index: int = 0  # 0..3
        self.first_king: int = -1
        self.remaining_contracts: list[str] = list(CONTRACTS)
        self.history: list[MatchRoundRecord] = []
        self.current_hands: list[int] = []
        self.current_round: Optional[TrixRound] = None
        self.phase: str = "deal"  # "choose_contract", "double", "play", "match_over"
        self._deal_next()

    @property
    def current_king(self) -> int:
        return (self.first_king + self.kingdom_index) & 3

    def _deal_next(self) -> None:
        if self.kingdom_index >= 4:
            self.phase = "match_over"
            return
        self.current_hands = deal_hands(self.rng)
        if self.first_king == -1:
            for s in range(4):
                if self.current_hands[s] & (1 << SEVEN_OF_HEARTS):
                    self.first_king = s
                    break
        self.current_round = None
        self.phase = "choose_contract"

    def select_contract(self, contract: str) -> TrixRound:
        if self.phase != "choose_contract":
            raise ValueError(f"Cannot select contract in phase '{self.phase}'")
        if contract not in self.remaining_contracts:
            raise ValueError(f"Contract '{contract}' not available; remaining={self.remaining_contracts}")
        self.remaining_contracts.remove(contract)
        self.current_round = TrixRound(
            contract=contract,
            king_seat=self.current_king,
            hands=self.current_hands,
            match_scores=self.scores,
        )
        if contract in (CONTRACT_KH, CONTRACT_QUEENS):
            self.phase = "double"
        else:
            self.phase = "play"
        return self.current_round

    def finish_doubling_phase(self) -> None:
        if self.phase == "double":
            self.phase = "play"

    def finalize_round(self) -> MatchRoundRecord:
        if self.current_round is None or not self.current_round.done:
            raise ValueError("Current round is not complete yet")
        rnd = self.current_round
        for i in range(4):
            self.scores[i] += rnd.scores[i]
        rec = MatchRoundRecord(
            kingdom_index=self.kingdom_index,
            round_in_kingdom=5 - len(self.remaining_contracts),
            king_seat=self.current_king,
            contract=rnd.contract,
            doubled_cards=dict(rnd.doubled_cards),
            round_scores=list(rnd.scores),
            cumulative_scores=list(self.scores),
        )
        self.history.append(rec)

        if not self.remaining_contracts:
            self.kingdom_index += 1
            self.remaining_contracts = list(CONTRACTS)

        if self.kingdom_index >= 4:
            self.phase = "match_over"
        else:
            self._deal_next()
        return rec

    def winner_seat(self) -> int:
        best = max(self.scores)
        return self.scores.index(best)

    def rankings(self) -> list[int]:
        """Seats sorted from 1st place (highest score) to 4th."""
        return sorted(range(4), key=lambda s: self.scores[s], reverse=True)

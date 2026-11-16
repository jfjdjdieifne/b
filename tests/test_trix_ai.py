"""Comprehensive Unit & Integration Tests for the Individual Trix AI Engine."""

from __future__ import annotations

import random
import unittest

from trix_ai.belief import BeliefState
from trix_ai.cards import (
    ALL_CARDS_MASK,
    CARD_BIT,
    KING_OF_HEARTS,
    QUEENS,
    RANK_A,
    RANK_J,
    RANK_K,
    RANK_Q,
    SEVEN_OF_HEARTS,
    SUIT_CLUBS,
    SUIT_DIAMONDS,
    SUIT_HEARTS,
    SUIT_SPADES,
    card_id,
    cards_to_mask,
    mask_to_cards,
    parse_card,
)
from trix_ai.endgame import (
    prune_equivalent_cards,
    solve_trick_endgame,
    solve_trix_endgame,
)
from trix_ai.engine import (
    CONTRACT_COLLECTIONS,
    CONTRACT_DIAMONDS,
    CONTRACT_KH,
    CONTRACT_QUEENS,
    CONTRACT_TRIX,
    CONTRACTS,
    PASS_ACTION,
    TrixMatch,
    TrixRound,
    deal_hands,
)
from trix_ai.grandmaster import GrandmasterAI
from trix_ai.heuristics import IntermediateAI, ProHeuristicAI, RandomAI


class TestTrixRulesEngine(unittest.TestCase):
    def test_deal_partition_52_unique_cards(self) -> None:
        hands = deal_hands(random.Random(42))
        self.assertEqual(len(hands), 4)
        union = 0
        for h in hands:
            self.assertEqual(h.bit_count(), 13)
            self.assertEqual(union & h, 0)
            union |= h
        self.assertEqual(union, ALL_CARDS_MASK)

    def test_first_king_holds_seven_of_hearts(self) -> None:
        for seed in range(10):
            m = TrixMatch(seed=seed)
            self.assertTrue(m.current_hands[m.first_king] & (1 << SEVEN_OF_HEARTS))

    def test_cannot_lead_king_of_hearts_with_other_cards(self) -> None:
        h0 = cards_to_mask([parse_card("KH"), parse_card("2C")])
        h1 = cards_to_mask([parse_card("3H"), parse_card("3C")])
        h2 = cards_to_mask([parse_card("4H"), parse_card("4C")])
        h3 = cards_to_mask([parse_card("5H"), parse_card("5C")])
        rnd = TrixRound(CONTRACT_KH, 0, [h0, h1, h2, h3])
        legal = rnd.legal_actions(0)
        self.assertNotIn(KING_OF_HEARTS, legal)
        self.assertEqual(legal, [parse_card("2C")])

    def test_kh_doubling_scoring_opponent_eats_and_doubler_eats(self) -> None:
        # Case 1: Seat 0 doubles K♥, Seat 1 eats it -> Seat 1 = -150, Seat 0 = +75
        h0 = cards_to_mask([parse_card("KH"), parse_card("2C")])
        h1 = cards_to_mask([parse_card("AH"), parse_card("AC")])
        h2 = cards_to_mask([parse_card("2H"), parse_card("3C")])
        h3 = cards_to_mask([parse_card("3H"), parse_card("4C")])
        rnd = TrixRound(CONTRACT_KH, 0, [h0, h1, h2, h3])
        rnd.apply_double(0, KING_OF_HEARTS)
        # Trick 1: 0 leads 2C, 1 wins with AC
        rnd.step(parse_card("2C"))
        rnd.step(parse_card("AC"))
        rnd.step(parse_card("3C"))
        rnd.step(parse_card("4C"))
        self.assertFalse(rnd.done)
        # Trick 2: 1 leads AH, 2 plays 2H, 3 plays 3H, 0 plays KH -> 1 wins KH!
        rnd.step(parse_card("AH"))
        rnd.step(parse_card("2H"))
        rnd.step(parse_card("3H"))
        rnd.step(parse_card("KH"))
        self.assertTrue(rnd.done)
        self.assertEqual(rnd.scores, [75, -150, 0, 0])

        # Case 2: Seat 0 doubles K♥ and eats it themselves -> Seat 0 = -150
        h0b = cards_to_mask([parse_card("KH")])
        h1b = cards_to_mask([parse_card("2H")])
        h2b = cards_to_mask([parse_card("3H")])
        h3b = cards_to_mask([parse_card("4H")])
        rnd2 = TrixRound(CONTRACT_KH, 1, [h0b, h1b, h2b, h3b])
        rnd2.apply_double(0, KING_OF_HEARTS)
        rnd2.step(parse_card("2H"))
        rnd2.step(parse_card("3H"))
        rnd2.step(parse_card("4H"))
        rnd2.step(parse_card("KH"))
        self.assertTrue(rnd2.done)
        self.assertEqual(rnd2.scores, [-150, 0, 0, 0])

    def test_queens_doubling_and_early_termination(self) -> None:
        h0 = cards_to_mask([parse_card("QS"), parse_card("QH"), parse_card("2C")])
        h1 = cards_to_mask([parse_card("AS"), parse_card("QD"), parse_card("3C")])
        h2 = cards_to_mask([parse_card("KS"), parse_card("QC"), parse_card("4C")])
        h3 = cards_to_mask([parse_card("2S"), parse_card("3S"), parse_card("5C")])
        rnd = TrixRound(CONTRACT_QUEENS, 0, [h0, h1, h2, h3])
        rnd.apply_double(0, parse_card("QS"))
        # Trick 1: 0 leads QS, 1 plays AS, 2 plays KS, 3 plays 2S -> 1 wins doubled QS (-50, 0 gets +25)
        rnd.step(parse_card("QS"))
        rnd.step(parse_card("AS"))
        rnd.step(parse_card("KS"))
        rnd.step(parse_card("2S"))
        self.assertEqual(rnd.scores, [25, -50, 0, 0])
        self.assertFalse(rnd.done)
        # Trick 2: 1 leads QD, 2 discards QC, 3 discards 3S, 0 discards QH -> all 4 Queens played!
        rnd.step(parse_card("QD"))
        rnd.step(parse_card("QC"))
        rnd.step(parse_card("3S"))
        rnd.step(parse_card("QH"))
        self.assertTrue(rnd.done)
        # Seat 1 wins 3 undoubled Queens (-75) + previous (-50) = -125
        self.assertEqual(rnd.scores, [25, -125, 0, 0])

    def test_trix_layout_rules_and_scoring_sum_500(self) -> None:
        hands = deal_hands(random.Random(123))
        rnd = TrixRound(CONTRACT_TRIX, 0, hands)
        rng = random.Random(456)
        steps = 0
        while not rnd.done:
            legal = rnd.legal_actions()
            self.assertTrue(len(legal) >= 1)
            rnd.step(rng.choice(legal))
            steps += 1
            self.assertLess(steps, 300)
        self.assertEqual(sum(rnd.scores), 500)
        self.assertEqual(sorted(rnd.scores), [50, 100, 150, 200])

    def test_full_match_20_rounds_integrity(self) -> None:
        match = TrixMatch(seed=999)
        agents = [RandomAI(seed=i) for i in range(4)]
        rounds_played = 0
        while match.phase != "match_over":
            king = match.current_king
            c = agents[king].choose_contract(
                match.current_hands[king],
                list(match.remaining_contracts),
                list(match.scores),
                king,
            )
            rnd = match.select_contract(c)
            match.finish_doubling_phase()
            while not rnd.done:
                p = rnd.current_player
                rnd.step(agents[p].choose_action(rnd.observation(p)))
            match.finalize_round()
            rounds_played += 1
        self.assertEqual(rounds_played, 20)
        # Without doubles, total score across 4 players in 4 kingdoms is:
        # 4 * (-75 - 100 - 130 - 195 + 500) = 4 * 0 = 0!
        self.assertEqual(sum(match.scores), 0)


class TestBeliefTracker(unittest.TestCase):
    def test_exact_void_and_double_deduction_and_sampling(self) -> None:
        hands = deal_hands(random.Random(77))
        # Find who holds KH
        kh_owner = next(s for s in range(4) if hands[s] & (1 << KING_OF_HEARTS))
        rnd = TrixRound(CONTRACT_KH, (kh_owner + 1) & 3, hands)
        rnd.apply_double(kh_owner, KING_OF_HEARTS)
        # Observer is not kh_owner
        obs_seat = (kh_owner + 1) & 3
        obs = rnd.observation(obs_seat)
        belief = BeliefState(obs)

        # Must deduce with 100% probability that kh_owner holds K♥!
        self.assertEqual(belief.prob_seat_has(kh_owner, KING_OF_HEARTS), 1.0)
        for s in range(4):
            if s != kh_owner:
                self.assertEqual(belief.prob_seat_has(s, KING_OF_HEARTS), 0.0)

        # Every sampled world must obey hand sizes, partition, and K♥ lock!
        rng = random.Random(101)
        for _ in range(30):
            sampled = belief.sample_hands(rng)
            self.assertEqual(sampled[obs_seat], obs.my_hand_mask)
            self.assertTrue(sampled[kh_owner] & (1 << KING_OF_HEARTS))
            union = obs.played_mask
            for s in range(4):
                self.assertEqual(sampled[s].bit_count(), obs.hand_counts[s])
                self.assertEqual(union & sampled[s], 0)
                union |= sampled[s]
            self.assertEqual(union, ALL_CARDS_MASK)

    def test_trix_pass_deduction(self) -> None:
        # Seat 0 has 4 Jacks; Seats 1, 2, 3 have no Jacks -> if Seat 1 leads Trix, Seat 1 passes!
        jacks = [card_id(s, RANK_J) for s in range(4)]
        rest = [c for c in range(52) if c not in jacks]
        h0 = cards_to_mask(jacks + rest[:9])
        h1 = cards_to_mask(rest[9:22])
        h2 = cards_to_mask(rest[22:35])
        h3 = cards_to_mask(rest[35:48])
        rnd = TrixRound(CONTRACT_TRIX, 1, [h0, h1, h2, h3])
        rnd.step(PASS_ACTION)  # Seat 1 passes when all 4 Jacks are playable!

        # From Seat 2's perspective, Seat 1 is PROVEN to hold ZERO Jacks!
        obs2 = rnd.observation(2)
        b2 = BeliefState(obs2)
        for j in jacks:
            self.assertEqual(b2.prob_seat_has(1, j), 0.0)


class TestExactEndgameSolvers(unittest.TestCase):
    def test_trick_endgame_finds_guaranteed_zero_loss_escape(self) -> None:
        # 2-trick Collections endgame where Seat 0 leads:
        # Seat 0 has 2S, AS; Seat 1 has 3S, 2H; Seat 2 has 4S, 3H; Seat 3 has 5S, 4H.
        # If Seat 0 leads AS -> wins Trick 1 (-15) AND loses Trick 2 (2S < 5S? no, 0 leads 2S!).
        # If Seat 0 leads 2S -> Seat 3 wins 5S (0 pts to Seat 0), then Seat 3 leads 4H,
        # Seat 0 is VOID in Hearts and dumps AS -> 0 penalty total!!
        h0 = cards_to_mask([parse_card("2S"), parse_card("AS")])
        h1 = cards_to_mask([parse_card("3S"), parse_card("2H")])
        h2 = cards_to_mask([parse_card("4S"), parse_card("3H")])
        h3 = cards_to_mask([parse_card("5S"), parse_card("4H")])
        rnd = TrixRound(CONTRACT_COLLECTIONS, 0, [h0, h1, h2, h3])
        rnd.played_mask = ALL_CARDS_MASK ^ (h0 | h1 | h2 | h3)
        rnd.trick_number = 11

        res, exact = solve_trick_endgame(rnd)
        self.assertTrue(exact)
        self.assertEqual(res[parse_card("2S")][0], 0)
        # Leading AS wins Trick 1 (-15) AND leaves opponents void in Spades so 2S wins Trick 2 (-30)!
        self.assertEqual(res[parse_card("AS")][0], -30)

    def test_trix_endgame_finds_guaranteed_first_place(self) -> None:
        # Layout has Spades 9..Q open (rank 7..10), Hearts 10..Q open (rank 8..10).
        # Seat 0 holds 8S, 7S (chaining!) and KH (unlocking Seat 1's AH!).
        h0 = cards_to_mask([parse_card("8S"), parse_card("7S"), parse_card("KH")])
        h1 = cards_to_mask([parse_card("AH"), parse_card("KS")])
        h2 = cards_to_mask([parse_card("AS"), parse_card("9H")])
        h3 = cards_to_mask([parse_card("8H"), parse_card("7H")])
        rnd = TrixRound(CONTRACT_TRIX, 0, [h0, h1, h2, h3])
        rnd.layout_low = [0, 0, 8, 7]   # Clubs/Diamonds full, Hearts 10..Q, Spades 9..Q
        rnd.layout_high = [12, 12, 10, 10]
        rnd.played_mask = ALL_CARDS_MASK ^ (h0 | h1 | h2 | h3)

        res, exact = solve_trix_endgame(rnd)
        self.assertTrue(exact)
        # Playing 8S keeps Seat 1 choked on AH while Seat 0 advances toward 7S!
        self.assertGreaterEqual(res[parse_card("8S")][0], res[parse_card("KH")][0])

    def test_equivalence_pruning(self) -> None:
        # If 8C is already played, 7C and 9C are adjacent equivalent in Collections!
        legal = cards_to_mask([parse_card("7C"), parse_card("9C"), parse_card("AC")])
        played = cards_to_mask([parse_card("8C")])
        pruned = prune_equivalent_cards(legal, played, CONTRACT_COLLECTIONS)
        self.assertEqual(pruned, [parse_card("7C"), parse_card("AC")])


class TestGrandmasterIntegration(unittest.TestCase):
    def test_grandmaster_plays_all_5_contracts_legally_with_analysis(self) -> None:
        gm = GrandmasterAI(level="fast", seed=42)
        opps = [ProHeuristicAI(seed=i) for i in range(4)]
        for idx, contract in enumerate(CONTRACTS):
            hands = deal_hands(random.Random(500 + idx))
            rnd = TrixRound(contract, 0, hands)
            while not rnd.done:
                p = rnd.current_player
                obs = rnd.observation(p)
                if p == 0:
                    analysis = gm.analyze_action(obs)
                    self.assertIn(analysis.best_action, rnd.legal_actions(0))
                    self.assertTrue(len(analysis.explanation_ar) > 5)
                    rnd.step(analysis.best_action)
                else:
                    rnd.step(opps[p].choose_action(obs))
            self.assertTrue(rnd.done)

    def test_grandmaster_dumps_king_of_hearts_when_void(self) -> None:
        # Seat 0 holds KH + 2H, void in Clubs; Trick has 10C led by Seat 1, 2C by 2, 3C by 3.
        h0 = cards_to_mask([parse_card("KH"), parse_card("2H"), parse_card("3H")])
        h1 = cards_to_mask([parse_card("10C"), parse_card("4H"), parse_card("5H")])
        h2 = cards_to_mask([parse_card("2C"), parse_card("6H"), parse_card("7H")])
        h3 = cards_to_mask([parse_card("3C"), parse_card("8H"), parse_card("9H")])
        rnd = TrixRound(CONTRACT_KH, 1, [h0, h1, h2, h3])
        rnd.played_mask = ALL_CARDS_MASK ^ (h0 | h1 | h2 | h3)
        rnd.trick_number = 10
        rnd.step(parse_card("10C"))
        rnd.step(parse_card("2C"))
        rnd.step(parse_card("3C"))

        gm = GrandmasterAI(level="fast", seed=7)
        act = gm.choose_action(rnd.observation(0))
        self.assertEqual(act, KING_OF_HEARTS)


if __name__ == "__main__":
    unittest.main()

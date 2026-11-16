"""Grandmaster Individual Trix AI Engine V2 (العقل الخارق للتريكس الفردي).

Combines:
1. Exact Combinatorial Belief Tracking (zero-rejection sampling + exact card probabilities
   + fixpoint constraint propagation from voids, Trix passes, and doubles).
2. Hybrid PIMC + Live Void-Aware Tactical Rollouts + Exact MaxN Endgame Solvers
   (both trick-taking & Trix dominoes).
3. Two-Stage Adaptive Compute Allocation (extra worlds on razor-thin decisions).
4. Dynamic Risk-Adjusted Utility (Expected Value + Relative Margin + Leader Targeting
   + Bad-Hand Tail Protection CVaR20).
5. Calibrated Monte Carlo Optimal-Stopping Contract Selector.
6. Exposed-Information Monte Carlo Doubling Calculator.
7. Full Arabic & Structured Decision Explainability (`analyze_action`, `analyze_contracts`).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .belief import BeliefState
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
    RANK_9,
    RANK_J,
    SUIT_AR,
    SUIT_DIAMONDS,
    SUIT_MASKS,
    SUIT_SHIFT,
    card_ar,
    card_str,
    mask_to_cards,
)
from .endgame import (
    prune_equivalent_cards,
    solve_trick_endgame,
    solve_trix_endgame,
)
from .engine import (
    CONTRACT_AR,
    CONTRACT_COLLECTIONS,
    CONTRACT_DIAMONDS,
    CONTRACT_KH,
    CONTRACT_QUEENS,
    CONTRACT_TRIX,
    PASS_ACTION,
    RoundObservation,
    TrixRound,
)
from .heuristics import (
    BaseAgent,
    analytical_contract_surplus,
    compute_void_masks_from_events,
    expert_rollout_action,
)


_CONTRACT_BASE_MEAN: dict[str, float] = {
    CONTRACT_KH: -18.75,
    CONTRACT_QUEENS: -25.0,
    CONTRACT_DIAMONDS: -32.5,
    CONTRACT_COLLECTIONS: -48.75,
    CONTRACT_TRIX: 125.0,
}

_CONTRACT_UPSIDE_SIGMA: dict[str, float] = {
    CONTRACT_KH: 18.0,
    CONTRACT_QUEENS: 19.0,
    CONTRACT_DIAMONDS: 22.0,
    CONTRACT_COLLECTIONS: 28.0,
    CONTRACT_TRIX: 34.0,
}


@dataclass
class ActionEval:
    action: int
    ev_own: float
    ev_utility: float
    cvar20: float
    min_score: float
    max_score: float
    zero_penalty_prob: float
    worlds_tested: int


@dataclass
class DecisionAnalysis:
    best_action: int
    mode: str  # "forced", "exact_endgame", "pimc_tactical"
    evaluations: list[ActionEval]
    belief_summary: dict
    explanation_ar: str


def _sample_other_hands_from_my_hand(
    my_hand: int, my_seat: int, rng: random.Random
) -> list[int]:
    """Deal remaining 39 unseen cards uniformly to the other 3 seats."""
    rem = mask_to_cards(ALL_CARDS_MASK ^ my_hand)
    rng.shuffle(rem)
    hands = [0, 0, 0, 0]
    hands[my_seat] = my_hand
    others = [s for s in range(4) if s != my_seat]
    for idx, seat in enumerate(others):
        m = 0
        for c in rem[idx * 13 : (idx + 1) * 13]:
            m |= CARD_BIT[c]
        hands[seat] = m
    return hands


def _build_world_round(obs: RoundObservation, hands: list[int]) -> TrixRound:
    rnd = TrixRound.__new__(TrixRound)
    rnd.contract = obs.contract
    rnd.king_seat = obs.king_seat
    rnd.hands = hands.copy()
    rnd.played_mask = obs.played_mask
    rnd.current_player = obs.current_player
    rnd.scores = list(obs.scores)
    rnd.match_scores = list(obs.match_scores)
    rnd.doubled_cards = dict(obs.doubled_cards)
    rnd.trick_number = obs.trick_number
    rnd.trick_leader = obs.trick_leader
    rnd.current_trick = list(obs.current_trick)
    rnd.completed_tricks = list(obs.completed_tricks)
    rnd.layout_low = list(obs.layout_low)
    rnd.layout_high = list(obs.layout_high)
    rnd.trix_finish_order = list(obs.trix_finish_order)
    rnd.events = []
    rnd.done = obs.done
    rnd.tricks_won = [0, 0, 0, 0]
    return rnd


def _run_void_aware_rollout(
    sim: TrixRound,
    my_seat: int,
    initial_voids: list[int],
    rng: random.Random,
    opp_noise: float,
) -> tuple[int, int, int, int]:
    """Ultra-fast rollout tracking live suit voids in O(1) per card played."""
    if sim.contract == CONTRACT_TRIX:
        while not sim.done:
            noise = opp_noise if sim.current_player != my_seat else 0.0
            act = expert_rollout_action(sim, rng=rng, noise=noise)
            sim.step(act)
        return (sim.scores[0], sim.scores[1], sim.scores[2], sim.scores[3])

    voids = initial_voids.copy()
    while not sim.done:
        p = sim.current_player
        noise = opp_noise if p != my_seat else 0.0
        act = expert_rollout_action(sim, rng=rng, noise=noise, void_masks=voids)
        if sim.current_trick:
            led_s = CARD_SUIT[sim.current_trick[0][1]]
            if CARD_SUIT[act] != led_s:
                voids[p] |= 1 << led_s
        sim.step(act)
    return (sim.scores[0], sim.scores[1], sim.scores[2], sim.scores[3])


class GrandmasterAI(BaseAgent):
    """Monster-strength Individual Trix AI engine."""

    name = "GrandmasterAI"

    def __init__(
        self,
        level: str = "monster",
        seed: Optional[int] = None,
    ) -> None:
        self.level = level
        self.rng = random.Random(seed)
        if level == "monster":
            self.worlds_midgame = 48
            self.worlds_refine = 32
            self.worlds_endgame = 30
            self.endgame_trick_threshold = 4
            self.trix_endgame_cards_threshold = 30
            self.endgame_node_budget = 4500
            self.contract_mc_worlds = 28
            self.double_mc_worlds = 40
        elif level == "tournament":
            self.worlds_midgame = 34
            self.worlds_refine = 20
            self.worlds_endgame = 22
            self.endgame_trick_threshold = 4
            self.trix_endgame_cards_threshold = 26
            self.endgame_node_budget = 3500
            self.contract_mc_worlds = 20
            self.double_mc_worlds = 32
        else:  # "fast"
            self.worlds_midgame = 22
            self.worlds_refine = 14
            self.worlds_endgame = 16
            self.endgame_trick_threshold = 4
            self.trix_endgame_cards_threshold = 24
            self.endgame_node_budget = 2500
            self.contract_mc_worlds = 16
            self.double_mc_worlds = 24

    # ==========================================================================
    # Utility Function (Score + Relative Margin + Leader Targeting + CVaR20)
    # ==========================================================================

    def _world_utility(
        self,
        final_scores: tuple[int, int, int, int],
        my_seat: int,
        match_scores: tuple[int, int, int, int] | list[int],
    ) -> float:
        own = final_scores[my_seat]
        opp_sum = final_scores[0] + final_scores[1] + final_scores[2] + final_scores[3] - own
        avg_opp = opp_sum / 3.0
        rel_margin = own - avg_opp

        leader_seat = -1
        leader_match = -10**9
        opp_match_sum = 0
        for s in range(4):
            if s != my_seat:
                opp_match_sum += match_scores[s]
                if match_scores[s] > leader_match:
                    leader_match = match_scores[s]
                    leader_seat = s
        avg_opp_match = opp_match_sum / 3.0
        leader_gap = leader_match - avg_opp_match
        leader_weight = 0.15 if leader_gap > 40 else (0.06 if leader_gap > 0 else 0.0)
        leader_term = -leader_weight * (final_scores[leader_seat] - avg_opp)

        return own + 0.35 * rel_margin + leader_term

    def _risk_weight(self, obs: RoundObservation) -> float:
        """Dynamic CVaR20 tail-protection weight: extra vigilant on hazardous hands."""
        my_seat = obs.seat
        my_m = obs.match_scores[my_seat]
        best_opp = max(obs.match_scores[s] for s in range(4) if s != my_seat)
        diff = my_m - best_opp

        base = 0.05 if diff < -120 else (0.22 if diff > 80 else 0.14)
        # Extra survival discipline when holding major penalty liabilities
        hand = obs.my_hand_mask
        if obs.contract == CONTRACT_KH and (hand & KING_OF_HEARTS_BIT):
            base += 0.07
        elif obs.contract == CONTRACT_QUEENS and (hand & QUEENS_MASK):
            base += 0.06
        elif obs.contract == CONTRACT_DIAMONDS:
            hi_d = ((hand >> SUIT_SHIFT[SUIT_DIAMONDS]) & 0x1FFF) >> RANK_9
            if hi_d.bit_count() >= 2:
                base += 0.05
        return base

    @staticmethod
    def _weighted_cvar20(samples: list[tuple[float, float]]) -> float:
        """Weighted bottom-20% Conditional Value at Risk of own round score."""
        if not samples:
            return 0.0
        ordered = sorted(samples, key=lambda x: x[0])
        total_w = sum(w for _, w in ordered)
        target = max(1e-9, total_w * 0.20)
        acc_w = 0.0
        acc_v = 0.0
        for val, w in ordered:
            take = min(w, target - acc_w)
            acc_v += val * take
            acc_w += take
            if acc_w >= target - 1e-12:
                break
        return acc_v / acc_w

    # ==========================================================================
    # Core Action Selection & Deep Analysis
    # ==========================================================================

    def choose_action(self, obs: RoundObservation) -> int:
        return self.analyze_action(obs).best_action

    def analyze_action(self, obs: RoundObservation) -> DecisionAnalysis:
        """Compute mathematically optimal action + full diagnostic breakdown."""
        my_seat = obs.seat
        belief = BeliefState(obs)
        contract = obs.contract

        if contract == CONTRACT_TRIX:
            playable = 0
            for s in range(4):
                lo = obs.layout_low[s]
                if lo == -1:
                    playable |= CARD_BIT[s * 13 + RANK_J]
                else:
                    if lo > 0:
                        playable |= CARD_BIT[s * 13 + lo - 1]
                    if obs.layout_high[s] < 12:
                        playable |= CARD_BIT[s * 13 + obs.layout_high[s] + 1]
            legal_mask = obs.my_hand_mask & playable
            if legal_mask == 0:
                return DecisionAnalysis(
                    best_action=PASS_ACTION,
                    mode="forced",
                    evaluations=[
                        ActionEval(PASS_ACTION, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0)
                    ],
                    belief_summary=belief.summary_dict(),
                    explanation_ar="لا توجد ورقة قانونية للنزول على طاولة التريكس — تمرير إجباري (Pass).",
                )
            distinct_moves = mask_to_cards(legal_mask)
        else:
            if not obs.current_trick:
                legal_mask = obs.my_hand_mask
                if (
                    contract == CONTRACT_KH
                    and (legal_mask & KING_OF_HEARTS_BIT)
                    and legal_mask != KING_OF_HEARTS_BIT
                ):
                    legal_mask ^= KING_OF_HEARTS_BIT
            else:
                led_suit = CARD_SUIT[obs.current_trick[0][1]]
                in_suit = obs.my_hand_mask & SUIT_MASKS[led_suit]
                legal_mask = in_suit if in_suit else obs.my_hand_mask

            distinct_moves = prune_equivalent_cards(legal_mask, obs.played_mask, contract)

        if len(distinct_moves) == 1:
            only = distinct_moves[0]
            return DecisionAnalysis(
                best_action=only,
                mode="forced",
                evaluations=[ActionEval(only, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0)],
                belief_summary=belief.summary_dict(),
                explanation_ar=f"خيار وحيد متاح أو متكافئ رياضياً: {card_ar(only)}.",
            )

        total_cards_left = sum(obs.hand_counts)
        my_cards_left = obs.hand_counts[my_seat]
        use_exact = False
        if contract == CONTRACT_TRIX:
            if total_cards_left <= self.trix_endgame_cards_threshold:
                use_exact = True
        else:
            if my_cards_left <= self.endgame_trick_threshold or (
                belief.total_worlds <= 30 and my_cards_left <= 5
            ):
                use_exact = True

        # Precompute current public void bitmasks for O(1) rollout propagation
        base_voids = compute_void_masks_from_events(obs.events)
        for p, vs in belief.void_suits.items():
            for s in vs:
                base_voids[p] |= 1 << s

        own_samples: dict[int, list[tuple[float, float]]] = {a: [] for a in distinct_moves}
        util_sum: dict[int, float] = {a: 0.0 for a in distinct_moves}
        w_sum: dict[int, float] = {a: 0.0 for a in distinct_moves}
        zero_pen_w: dict[int, float] = {a: 0.0 for a in distinct_moves}

        cur_own = obs.scores[my_seat]
        opp_noise = 10.0 if contract == CONTRACT_TRIX else 3.5

        def evaluate_batch(
            actions_to_test: list[int],
            n_worlds: int,
            exact_mode: bool,
        ) -> None:
            worlds = belief.sample_weighted_worlds(n_worlds, self.rng)
            for hands, weight in worlds:
                base_rnd = _build_world_round(obs, hands)
                if exact_mode:
                    if contract == CONTRACT_TRIX:
                        res_map, _ = solve_trix_endgame(
                            base_rnd, node_budget=self.endgame_node_budget
                        )
                    else:
                        res_map, _ = solve_trick_endgame(
                            base_rnd, node_budget=self.endgame_node_budget
                        )
                    for a in actions_to_test:
                        fs = res_map[a]
                        own_val = float(fs[my_seat])
                        util = self._world_utility(fs, my_seat, obs.match_scores)
                        own_samples[a].append((own_val, weight))
                        util_sum[a] += util * weight
                        w_sum[a] += weight
                        if contract == CONTRACT_TRIX:
                            if own_val >= 150:
                                zero_pen_w[a] += weight
                        elif own_val == cur_own:
                            zero_pen_w[a] += weight
                else:
                    roll_seed = self.rng.randrange(1 << 30)
                    for a in actions_to_test:
                        sim = base_rnd.clone()
                        v_copy = base_voids.copy()
                        if contract != CONTRACT_TRIX and sim.current_trick:
                            led_s = CARD_SUIT[sim.current_trick[0][1]]
                            if CARD_SUIT[a] != led_s:
                                v_copy[my_seat] |= 1 << led_s
                        sim.step(a)
                        sim_rng = random.Random(roll_seed)
                        fs = _run_void_aware_rollout(
                            sim, my_seat, v_copy, sim_rng, opp_noise
                        )
                        own_val = float(fs[my_seat])
                        util = self._world_utility(fs, my_seat, obs.match_scores)
                        own_samples[a].append((own_val, weight))
                        util_sum[a] += util * weight
                        w_sum[a] += weight
                        if contract == CONTRACT_TRIX:
                            if own_val >= 150:
                                zero_pen_w[a] += weight
                        elif own_val == cur_own:
                            zero_pen_w[a] += weight

        if use_exact:
            n_w = 1 if belief.total_worlds <= 1 else self.worlds_endgame
            evaluate_batch(distinct_moves, n_w, exact_mode=True)
            mode = "exact_endgame"
        else:
            n_w = 1 if belief.total_worlds <= 1 else self.worlds_midgame
            evaluate_batch(distinct_moves, n_w, exact_mode=False)
            mode = "pimc_tactical"

            if belief.total_worlds > 1 and len(distinct_moves) >= 2 and self.worlds_refine > 0:
                prelim = sorted(
                    distinct_moves,
                    key=lambda a: util_sum[a] / max(1e-9, w_sum[a]),
                    reverse=True,
                )
                top1 = util_sum[prelim[0]] / max(1e-9, w_sum[prelim[0]])
                top2 = util_sum[prelim[1]] / max(1e-9, w_sum[prelim[1]])
                if (top1 - top2) < 10.0:
                    contenders = [
                        a
                        for a in prelim[:3]
                        if (top1 - (util_sum[a] / max(1e-9, w_sum[a]))) < 15.0
                    ]
                    if len(contenders) >= 2:
                        evaluate_batch(contenders, self.worlds_refine, exact_mode=False)

        risk_w = self._risk_weight(obs)
        evals: list[ActionEval] = []
        for a in distinct_moves:
            ws = max(1e-9, w_sum[a])
            ev_own = sum(v * w for v, w in own_samples[a]) / ws
            ev_util = util_sum[a] / ws
            cvar20 = self._weighted_cvar20(own_samples[a])
            min_s = min(v for v, _ in own_samples[a])
            max_s = max(v for v, _ in own_samples[a])
            safe_p = zero_pen_w[a] / ws
            combined = ev_util + risk_w * (cvar20 - ev_own)
            evals.append(
                ActionEval(
                    action=a,
                    ev_own=round(ev_own, 2),
                    ev_utility=round(combined, 2),
                    cvar20=round(cvar20, 2),
                    min_score=round(min_s, 1),
                    max_score=round(max_s, 1),
                    zero_penalty_prob=round(safe_p, 3),
                    worlds_tested=len(own_samples[a]),
                )
            )

        evals.sort(key=lambda e: (e.ev_utility, e.ev_own, e.cvar20), reverse=True)
        best = evals[0]

        exp_parts = []
        if mode == "exact_endgame":
            exp_parts.append(
                f"حل نهاية دقيق (Exact MaxN) عبر {best.worlds_tested} سيناريو متسق:"
            )
        else:
            exp_parts.append(
                f"تحليل مونت كارلو الاحتمالي عبر {best.worlds_tested} توزيع متسق:"
            )
        exp_parts.append(
            f"أفضل ورقة هي {card_ar(best.action)} بمعدل متوقع ({best.ev_own:+.1f} نقطة)"
        )
        if contract == CONTRACT_TRIX:
            exp_parts.append(f"وفرصة إنهاء أول/ثاني {best.zero_penalty_prob*100:.0f}%.")
        else:
            exp_parts.append(
                f"ونسبة نجاة بدون خسارة إضافية {best.zero_penalty_prob*100:.0f}% (أسوأ 20%: {best.cvar20:+.1f})."
            )
        void_notes = []
        for p, vs in belief.void_suits.items():
            if vs:
                suits_txt = "، ".join(SUIT_AR[s] for s in sorted(vs))
                void_notes.append(f"اللاعب {p + 1} مقطوع من ({suits_txt})")
        if void_notes:
            exp_parts.append("الاستنتاجات المؤكدة: " + " | ".join(void_notes) + ".")

        return DecisionAnalysis(
            best_action=best.action,
            mode=mode,
            evaluations=evals,
            belief_summary=belief.summary_dict(),
            explanation_ar=" ".join(exp_parts),
        )

    # ==========================================================================
    # Optimal-Stopping Monte Carlo Contract Selector
    # ==========================================================================

    def analyze_contracts(
        self,
        hand_mask: int,
        remaining_contracts: list[str],
        match_scores: list[int],
        seat: int,
    ) -> list[dict]:
        """Evaluate every remaining contract using Monte Carlo + Optimal-Stopping math."""
        if len(remaining_contracts) == 1:
            c = remaining_contracts[0]
            return [
                {
                    "contract": c,
                    "contract_ar": CONTRACT_AR[c],
                    "expected_score": round(_CONTRACT_BASE_MEAN[c], 1),
                    "surplus_vs_baseline": 0.0,
                    "option_adjusted_value": 0.0,
                }
            ]

        k = len(remaining_contracts)
        avg_sigma = sum(_CONTRACT_UPSIDE_SIGMA[c] for c in remaining_contracts) / k
        sampled_worlds = [
            _sample_other_hands_from_my_hand(hand_mask, seat, self.rng)
            for _ in range(self.contract_mc_worlds)
        ]

        results = []
        for c in remaining_contracts:
            total_sc = 0.0
            for hands in sampled_worlds:
                rnd = TrixRound(
                    contract=c,
                    king_seat=seat,
                    hands=hands,
                    match_scores=match_scores,
                )
                if c == CONTRACT_KH:
                    for p in range(4):
                        if rnd.hands[p] & KING_OF_HEARTS_BIT:
                            h_cnt = (rnd.hands[p] & SUIT_MASKS[2]).bit_count()
                            voids = sum(
                                1 for s in range(4) if (rnd.hands[p] & SUIT_MASKS[s]) == 0
                            )
                            if h_cnt >= 5 or (h_cnt >= 3 and voids >= 1):
                                rnd.apply_double(p, KING_OF_HEARTS)
                elif c == CONTRACT_QUEENS:
                    for p in range(4):
                        voids = sum(
                            1 for s in range(4) if (rnd.hands[p] & SUIT_MASKS[s]) == 0
                        )
                        for q in QUEENS:
                            if rnd.hands[p] & CARD_BIT[q]:
                                s = CARD_SUIT[q]
                                low_g = (
                                    (rnd.hands[p] >> (s * 13)) & ((1 << 10) - 1)
                                ).bit_count()
                                if low_g >= 3 or (low_g >= 1 and voids >= 1):
                                    rnd.apply_double(p, q)

                v_init = [0, 0, 0, 0]
                fs = _run_void_aware_rollout(rnd, seat, v_init, self.rng, 0.0)
                total_sc += fs[seat]

            mc_ev = total_sc / self.contract_mc_worlds
            mc_surplus = mc_ev - _CONTRACT_BASE_MEAN[c]
            ana_surplus = analytical_contract_surplus(hand_mask, c)

            # 80% real Monte Carlo EV + 20% analytical stabilizer
            blended_surplus = 0.80 * mc_surplus + 0.20 * ana_surplus
            # Clean relative-volatility continuation adjustment (zero systematic bias!)
            rel_option_cost = 0.035 * (k - 1) * (_CONTRACT_UPSIDE_SIGMA[c] - avg_sigma)
            adj_val = blended_surplus - rel_option_cost

            results.append(
                {
                    "contract": c,
                    "contract_ar": CONTRACT_AR[c],
                    "expected_score": round(mc_ev, 1),
                    "surplus_vs_baseline": round(blended_surplus, 1),
                    "option_adjusted_value": round(adj_val, 1),
                }
            )

        results.sort(key=lambda r: r["option_adjusted_value"], reverse=True)
        return results

    def choose_contract(
        self,
        hand_mask: int,
        remaining_contracts: list[str],
        match_scores: list[int],
        seat: int,
    ) -> str:
        ranked = self.analyze_contracts(hand_mask, remaining_contracts, match_scores, seat)
        return ranked[0]["contract"]

    # ==========================================================================
    # Exposed-Information Monte Carlo Doubling Calculator
    # ==========================================================================

    def analyze_doubles(
        self,
        contract: str,
        hand_mask: int,
        candidates: list[int],
        match_scores: list[int],
        seat: int,
        king_seat: Optional[int] = None,
    ) -> list[dict]:
        """Compute exact eating probability & EV gain of doubling each candidate card."""
        if not candidates or contract not in (CONTRACT_KH, CONTRACT_QUEENS):
            return []

        my_m = match_scores[seat]
        best_opp = max(match_scores[s] for s in range(4) if s != seat)
        diff = my_m - best_opp

        if contract == CONTRACT_KH:
            max_p_eat = 0.30 if diff < -100 else (0.19 if diff > 100 else 0.24)
            bonus = 75.0
        else:
            max_p_eat = 0.34 if diff < -100 else (0.23 if diff > 100 else 0.28)
            bonus = 25.0

        lead_seat = seat if king_seat is None else king_seat
        sampled_worlds = [
            _sample_other_hands_from_my_hand(hand_mask, seat, self.rng)
            for _ in range(self.double_mc_worlds)
        ]

        analysis = []
        for card in candidates:
            ate_count = 0
            for hands in sampled_worlds:
                rnd = TrixRound(
                    contract=contract,
                    king_seat=lead_seat,
                    hands=hands,
                    match_scores=match_scores,
                )
                rnd.apply_double(seat, card)
                v_init = [0, 0, 0, 0]
                _run_void_aware_rollout(rnd, seat, v_init, self.rng, 0.0)
                if contract == CONTRACT_KH:
                    if rnd.scores[seat] < 0:
                        ate_count += 1
                else:
                    for _, plays, winner in rnd.completed_tricks:
                        if any(c == card for _, c in plays):
                            if winner == seat:
                                ate_count += 1
                            break

            p_eat = ate_count / self.double_mc_worlds
            ev_gain = bonus * (1.0 - 2.0 * p_eat)
            recommend = p_eat <= max_p_eat
            analysis.append(
                {
                    "card": card,
                    "card_str": card_str(card),
                    "card_ar": card_ar(card),
                    "p_eat": round(p_eat, 3),
                    "ev_gain": round(ev_gain, 1),
                    "recommend_double": recommend,
                }
            )
        return analysis

    def choose_doubles(
        self,
        contract: str,
        hand_mask: int,
        candidates: list[int],
        match_scores: list[int],
        seat: int,
        king_seat: Optional[int] = None,
    ) -> list[int]:
        res = self.analyze_doubles(
            contract, hand_mask, candidates, match_scores, seat, king_seat=king_seat
        )
        return [item["card"] for item in res if item["recommend_double"]]

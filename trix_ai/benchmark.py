"""Benchmark & Stress-Test Suite for Grandmaster Individual Trix AI.

Measures:
1. Full 4-Kingdom (20-round) Match Win Rate (baseline = 25% for 4 equal players).
2. Average Total Match Score & Margin over Opponents.
3. Per-Contract Average Score across all 5 contracts (KH, Queens, Diamonds, Collections, Trix).
4. Bad-Hand Survival Test (Torture Test): Performance on the worst 20% dealt hands!
5. Doubling ROI (profit/loss from doubled K♥ and Queens).
6. Average Decision Time (ms).
"""

from __future__ import annotations

import statistics
import time
from typing import Callable

from .cards import KING_OF_HEARTS, QUEENS
from .engine import (
    CONTRACT_AR,
    CONTRACT_COLLECTIONS,
    CONTRACT_DIAMONDS,
    CONTRACT_KH,
    CONTRACT_QUEENS,
    CONTRACT_TRIX,
    CONTRACTS,
    TrixMatch,
)
from .grandmaster import GrandmasterAI
from .heuristics import (
    BaseAgent,
    IntermediateAI,
    ProHeuristicAI,
    RandomAI,
    analytical_contract_surplus,
)


def play_full_match(agents: list[BaseAgent], seed: int) -> dict:
    """Play one complete 4-Kingdom (20-round) Individual Trix match."""
    match = TrixMatch(seed=seed)
    per_contract_scores: dict[str, list[list[int]]] = {c: [] for c in CONTRACTS}
    seat0_times: list[float] = []
    double_stats = {"attempts": 0, "success": 0, "failed": 0, "net_gain": 0}
    bad_hand_rounds: list[tuple[str, float, int, float]] = []

    while match.phase != "match_over":
        king = match.current_king
        contract = agents[king].choose_contract(
            match.current_hands[king],
            list(match.remaining_contracts),
            list(match.scores),
            king,
        )
        rnd = match.select_contract(contract)

        # Record hand quality of seat 0 for bad-hand survival analysis
        s0_hand_surplus = analytical_contract_surplus(match.current_hands[0], contract)

        if match.phase == "double":
            for s in range(4):
                cands = rnd.doubler_candidates(s)
                if cands:
                    if isinstance(agents[s], GrandmasterAI):
                        chosen = agents[s].choose_doubles(
                            contract,
                            rnd.hands[s],
                            cands,
                            list(match.scores),
                            s,
                            king_seat=king,
                        )
                    else:
                        chosen = agents[s].choose_doubles(
                            contract, rnd.hands[s], cands, list(match.scores), s
                        )
                    for card in chosen:
                        rnd.apply_double(s, card)
            match.finish_doubling_phase()

        # Track seat 0 doubles
        s0_doubled = [c for c, d in rnd.doubled_cards.items() if d == 0]

        while not rnd.done:
            p = rnd.current_player
            obs = rnd.observation(p)
            t0 = time.perf_counter()
            act = agents[p].choose_action(obs)
            dt = (time.perf_counter() - t0) * 1000.0
            if p == 0:
                seat0_times.append(dt)
            rnd.step(act)

        # Evaluate seat 0 doubling outcomes
        for card in s0_doubled:
            double_stats["attempts"] += 1
            bonus = 75 if card == KING_OF_HEARTS else 25
            ate = False
            for _, plays, winner in rnd.completed_tricks:
                if any(c == card for _, c in plays):
                    ate = winner == 0
                    break
            if ate:
                double_stats["failed"] += 1
                double_stats["net_gain"] -= bonus
            else:
                double_stats["success"] += 1
                double_stats["net_gain"] += bonus

        rec = match.finalize_round()
        per_contract_scores[contract].append(rec.round_scores)
        opp_avg = (sum(rec.round_scores) - rec.round_scores[0]) / 3.0
        bad_hand_rounds.append((contract, s0_hand_surplus, rec.round_scores[0], opp_avg))

    ranks = match.rankings()
    s0_rank = ranks.index(0) + 1
    opp_avg_total = (sum(match.scores) - match.scores[0]) / 3.0
    return {
        "scores": list(match.scores),
        "seat0_rank": s0_rank,
        "seat0_won": s0_rank == 1,
        "seat0_top2": s0_rank <= 2,
        "seat0_margin": match.scores[0] - opp_avg_total,
        "per_contract": per_contract_scores,
        "seat0_avg_ms": statistics.mean(seat0_times) if seat0_times else 0.0,
        "double_stats": double_stats,
        "bad_hand_rounds": bad_hand_rounds,
    }


def run_benchmark(
    opponent_factory: Callable[[int], BaseAgent],
    opponent_label: str,
    n_matches: int = 20,
    gm_level: str = "fast",
    base_seed: int = 1000,
) -> dict:
    """Run `n_matches` full 20-round matches of GrandmasterAI vs 3 opponents."""
    t_start = time.perf_counter()
    wins = 0
    top2 = 0
    last_place = 0
    s0_scores: list[int] = []
    opp_scores: list[float] = []
    margins: list[float] = []
    ms_list: list[float] = []
    contract_s0: dict[str, list[int]] = {c: [] for c in CONTRACTS}
    contract_opp: dict[str, list[float]] = {c: [] for c in CONTRACTS}
    all_rounds: list[tuple[str, float, int, float]] = []
    dbl_totals = {"attempts": 0, "success": 0, "failed": 0, "net_gain": 0}

    for i in range(n_matches):
        seed = base_seed + i * 37
        agents: list[BaseAgent] = [
            GrandmasterAI(level=gm_level, seed=seed + 1),
            opponent_factory(seed + 2),
            opponent_factory(seed + 3),
            opponent_factory(seed + 4),
        ]
        res = play_full_match(agents, seed=seed)
        if res["seat0_won"]:
            wins += 1
        if res["seat0_top2"]:
            top2 += 1
        if res["seat0_rank"] == 4:
            last_place += 1
        s0_scores.append(res["scores"][0])
        opp_scores.append((sum(res["scores"]) - res["scores"][0]) / 3.0)
        margins.append(res["seat0_margin"])
        ms_list.append(res["seat0_avg_ms"])
        all_rounds.extend(res["bad_hand_rounds"])
        for k in dbl_totals:
            dbl_totals[k] += res["double_stats"][k]
        for c in CONTRACTS:
            for r_sc in res["per_contract"][c]:
                contract_s0[c].append(r_sc[0])
                contract_opp[c].append((sum(r_sc) - r_sc[0]) / 3.0)

    elapsed = time.perf_counter() - t_start

    # Bad-hand torture analysis: worst 20% of non-trix hands dealt to seat 0
    neg_rounds = [r for r in all_rounds if r[0] != CONTRACT_TRIX]
    neg_rounds.sort(key=lambda x: x[1])  # sort by worst hand surplus
    worst_20 = neg_rounds[: max(1, len(neg_rounds) // 5)]
    worst_s0_avg = statistics.mean(x[2] for x in worst_20)
    worst_opp_avg = statistics.mean(x[3] for x in worst_20)

    summary = {
        "opponent": opponent_label,
        "gm_level": gm_level,
        "matches": n_matches,
        "total_rounds": n_matches * 20,
        "elapsed_sec": round(elapsed, 2),
        "win_rate_pct": round(100.0 * wins / n_matches, 1),
        "top2_rate_pct": round(100.0 * top2 / n_matches, 1),
        "last_place_pct": round(100.0 * last_place / n_matches, 1),
        "gm_avg_match_score": round(statistics.mean(s0_scores), 1),
        "opp_avg_match_score": round(statistics.mean(opp_scores), 1),
        "avg_margin": round(statistics.mean(margins), 1),
        "avg_move_ms": round(statistics.mean(ms_list), 2),
        "double_stats": dbl_totals,
        "worst20_hand_gm_avg": round(worst_s0_avg, 1),
        "worst20_hand_opp_avg": round(worst_opp_avg, 1),
        "per_contract": {
            c: {
                "name_ar": CONTRACT_AR[c],
                "gm_avg": round(statistics.mean(contract_s0[c]), 1),
                "opp_avg": round(statistics.mean(contract_opp[c]), 1),
                "edge": round(
                    statistics.mean(contract_s0[c]) - statistics.mean(contract_opp[c]), 1
                ),
            }
            for c in CONTRACTS
        },
    }
    return summary


def print_report(s: dict) -> None:
    print("=" * 72)
    print(
        f"BENCHMARK: GrandmasterAI ({s['gm_level']}) vs 3x {s['opponent']} "
        f"| {s['matches']} matches ({s['total_rounds']} rounds) in {s['elapsed_sec']}s"
    )
    print("=" * 72)
    print(
        f"  1st Place Win Rate : {s['win_rate_pct']:5.1f}%  (Equal baseline = 25.0%)"
    )
    print(
        f"  Top-2 Finish Rate  : {s['top2_rate_pct']:5.1f}%  (Equal baseline = 50.0%)"
    )
    print(
        f"  Last-Place Rate    : {s['last_place_pct']:5.1f}%  (Equal baseline = 25.0%)"
    )
    print(
        f"  GM Avg Match Score : {s['gm_avg_match_score']:+7.1f}  "
        f"vs Opponents Avg: {s['opp_avg_match_score']:+7.1f}  "
        f"| Net Edge: {s['avg_margin']:+6.1f} pts/match"
    )
    print(
        f"  Worst-20% Bad Hands: GM Avg {s['worst20_hand_gm_avg']:+6.1f} "
        f"vs Opponents {s['worst20_hand_opp_avg']:+6.1f} per round"
    )
    d = s["double_stats"]
    print(
        f"  Doubling Record    : {d['success']}/{d['attempts']} succeeded "
        f"(failed {d['failed']}) | Net ROI: {d['net_gain']:+d} pts"
    )
    print(f"  Avg Move Latency   : {s['avg_move_ms']:.2f} ms")
    print("  Per-Contract Breakdown (avg per round):")
    for c in CONTRACTS:
        pc = s["per_contract"][c]
        print(
            f"    - {c:14s} ({pc['name_ar']:10s}): "
            f"GM {pc['gm_avg']:+6.1f} | Opp {pc['opp_avg']:+6.1f} | Edge {pc['edge']:+6.1f}"
        )
    print("=" * 72)


if __name__ == "__main__":
    print("Running benchmark vs 3x IntermediateAI...")
    r1 = run_benchmark(
        lambda s: IntermediateAI(seed=s),
        "IntermediateAI",
        n_matches=16,
        gm_level="fast",
        base_seed=2000,
    )
    print_report(r1)

    print("\nRunning benchmark vs 3x ProHeuristicAI...")
    r2 = run_benchmark(
        lambda s: ProHeuristicAI(seed=s),
        "ProHeuristicAI",
        n_matches=16,
        gm_level="fast",
        base_seed=4000,
    )
    print_report(r2)

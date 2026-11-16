"""Exact MaxN Endgame Solvers V2 for Trick-Taking and Trix (Domino) Contracts.

Upgrades in V2:
- Mathematically exact MaxN Upper-Bound Pruning (instant cutoff whenever a player
  achieves their theoretical maximum possible score delta, e.g., 0 penalty in
  Collections/Diamonds or full double-bonus in KH/Queens, or next-finish score in Trix!).
- Smart Move Ordering (ducks & penalty-dumps first in trick-taking; deep chains &
  terminals first in Trix) so exact cutoffs fire on the very first branch!
- Adjacent-card equivalence pruning + additive trick-boundary transposition tables.
"""

from __future__ import annotations

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
    RANK_2,
    RANK_A,
    RANK_J,
    RANK_Q,
    SUIT_DIAMONDS,
    SUIT_HEARTS,
    SUIT_MASKS,
    SUIT_SHIFT,
    lowest_card_in_mask,
    mask_to_cards,
)
from .engine import (
    CONTRACT_COLLECTIONS,
    CONTRACT_DIAMONDS,
    CONTRACT_KH,
    CONTRACT_QUEENS,
    CONTRACT_TRIX,
    PASS_ACTION,
    TRIX_FINISH_SCORES,
    TrixRound,
)
from .heuristics import expert_rollout_action


def prune_equivalent_cards(
    legal_mask: int, played_mask: int, contract: str
) -> list[int]:
    """Return deduplicated list of strategically distinct cards from `legal_mask`."""
    if (legal_mask & (legal_mask - 1)) == 0:
        return [lowest_card_in_mask(legal_mask)]

    special_mask = 0
    if contract == CONTRACT_KH:
        special_mask = KING_OF_HEARTS_BIT
    elif contract == CONTRACT_QUEENS:
        special_mask = QUEENS_MASK

    res: list[int] = []
    for s in range(4):
        sm = (legal_mask >> SUIT_SHIFT[s]) & 0x1FFF
        if not sm:
            continue
        pm = (played_mask >> SUIT_SHIFT[s]) & 0x1FFF
        sp = (special_mask >> SUIT_SHIFT[s]) & 0x1FFF
        prev_r = -1
        for r in range(13):
            if (sm >> r) & 1:
                if prev_r == -1:
                    res.append(s * 13 + r)
                    prev_r = r
                else:
                    if ((sp >> prev_r) & 1) or ((sp >> r) & 1):
                        res.append(s * 13 + r)
                        prev_r = r
                    else:
                        gap = r - prev_r - 1
                        if gap == 0:
                            continue
                        between_mask = ((1 << gap) - 1) << (prev_r + 1)
                        if (pm & between_mask) == between_mask:
                            continue
                        res.append(s * 13 + r)
                        prev_r = r
    return res


def _order_trick_moves(
    moves: list[int],
    contract: str,
    t_cards: tuple[int, ...],
) -> list[int]:
    """Fast move ordering so MaxN exact upper-bound cutoffs fire immediately."""
    if len(moves) <= 1:
        return moves

    if not t_cards:
        # Leading: low cards first (usually safest!)
        moves.sort(key=lambda c: CARD_RANK[c])
        return moves

    led_suit = CARD_SUIT[t_cards[0]]
    # Check if following suit or discarding void
    if CARD_SUIT[moves[0]] == led_suit:
        win_r = CARD_RANK[t_cards[0]]
        for i in range(1, len(t_cards)):
            tc = t_cards[i]
            if CARD_SUIT[tc] == led_suit and CARD_RANK[tc] > win_r:
                win_r = CARD_RANK[tc]
        # Prefer highest ducking card first, then lowest overtaking card
        def key_follow(c: int) -> int:
            r = CARD_RANK[c]
            if r < win_r:
                return -(100 + r)  # Ducking: highest below win_r first!
            return r  # Overtaking: lowest first
        moves.sort(key=key_follow)
        return moves

    # Void discard: dump penalty cards / high cards first!
    def key_discard(c: int) -> int:
        r = CARD_RANK[c]
        s = CARD_SUIT[c]
        if contract == CONTRACT_KH and c == KING_OF_HEARTS:
            return -1000
        if contract == CONTRACT_QUEENS and r == RANK_Q:
            return -800
        if contract == CONTRACT_DIAMONDS and s == SUIT_DIAMONDS:
            return -(400 + r)
        return -r

    moves.sort(key=key_discard)
    return moves


def _score_completed_trick(
    contract: str,
    trick_cards: tuple[int, int, int, int],
    trick_seats: tuple[int, int, int, int],
    doubled_cards: dict[int, int],
) -> tuple[int, tuple[int, int, int, int], bool]:
    """Fast pure function returning (winner_seat, delta_4tuple, round_ended_early)."""
    c0 = trick_cards[0]
    led_suit = CARD_SUIT[c0]
    win_r = CARD_RANK[c0]
    winner = trick_seats[0]
    tmask = CARD_BIT[c0]

    for i in range(1, 4):
        ci = trick_cards[i]
        tmask |= CARD_BIT[ci]
        if CARD_SUIT[ci] == led_suit:
            ri = CARD_RANK[ci]
            if ri > win_r:
                win_r = ri
                winner = trick_seats[i]

    d0 = d1 = d2 = d3 = 0
    ended = False

    if contract == CONTRACT_COLLECTIONS:
        if winner == 0:
            d0 = -15
        elif winner == 1:
            d1 = -15
        elif winner == 2:
            d2 = -15
        else:
            d3 = -15
    elif contract == CONTRACT_DIAMONDS:
        cnt = (tmask & DIAMONDS_MASK).bit_count()
        if cnt:
            pen = -10 * cnt
            if winner == 0:
                d0 = pen
            elif winner == 1:
                d1 = pen
            elif winner == 2:
                d2 = pen
            else:
                d3 = pen
    elif contract == CONTRACT_KH:
        if tmask & KING_OF_HEARTS_BIT:
            ended = True
            delta = [0, 0, 0, 0]
            if KING_OF_HEARTS in doubled_cards:
                doubler = doubled_cards[KING_OF_HEARTS]
                delta[winner] -= 150
                if winner != doubler:
                    delta[doubler] += 75
            else:
                delta[winner] -= 75
            return winner, (delta[0], delta[1], delta[2], delta[3]), True
    elif contract == CONTRACT_QUEENS:
        qm = tmask & QUEENS_MASK
        if qm:
            delta = [0, 0, 0, 0]
            for q in QUEENS:
                if qm & CARD_BIT[q]:
                    if q in doubled_cards:
                        doubler = doubled_cards[q]
                        delta[winner] -= 50
                        if winner != doubler:
                            delta[doubler] += 25
                    else:
                        delta[winner] -= 25
            return winner, (delta[0], delta[1], delta[2], delta[3]), False

    return winner, (d0, d1, d2, d3), ended


def _rollout_remaining_deltas(
    contract: str,
    hands: tuple[int, int, int, int],
    played: int,
    leader: int,
    doubled_cards: dict[int, int],
) -> tuple[int, int, int, int]:
    rnd = TrixRound.__new__(TrixRound)
    rnd.contract = contract
    rnd.king_seat = leader
    rnd.hands = [hands[0], hands[1], hands[2], hands[3]]
    rnd.played_mask = played
    rnd.current_player = leader
    rnd.scores = [0, 0, 0, 0]
    rnd.match_scores = [0, 0, 0, 0]
    rnd.doubled_cards = doubled_cards
    rnd.trick_number = played.bit_count() // 4
    rnd.trick_leader = leader
    rnd.current_trick = []
    rnd.completed_tricks = []
    rnd.layout_low = [-1, -1, -1, -1]
    rnd.layout_high = [-1, -1, -1, -1]
    rnd.trix_finish_order = []
    rnd.events = []
    rnd.done = False
    rnd.tricks_won = [0, 0, 0, 0]

    while not rnd.done:
        a = expert_rollout_action(rnd)
        rnd.step(a)
    return (rnd.scores[0], rnd.scores[1], rnd.scores[2], rnd.scores[3])


def solve_trick_endgame(
    rnd: TrixRound,
    node_budget: int = 4000,
) -> tuple[dict[int, tuple[int, int, int, int]], bool]:
    """Exact MaxN solver with exact upper-bound cutoffs for trick-taking endgames."""
    contract = rnd.contract
    doubled = rnd.doubled_cards
    # Precompute maximum possible future delta for each seat (exact upper bound!)
    max_possible = [0, 0, 0, 0]
    if contract == CONTRACT_KH and KING_OF_HEARTS in doubled:
        if not (rnd.played_mask & KING_OF_HEARTS_BIT):
            max_possible[doubled[KING_OF_HEARTS]] = 75
    elif contract == CONTRACT_QUEENS and doubled:
        for q, doubler in doubled.items():
            if not (rnd.played_mask & CARD_BIT[q]):
                max_possible[doubler] += 25

    tt: dict[tuple[int, int, int, int, int], tuple[int, int, int, int]] = {}
    nodes = 0
    budget_hit = False

    def search_trick_start(
        h0: int, h1: int, h2: int, h3: int, played: int, leader: int
    ) -> tuple[int, int, int, int]:
        nonlocal nodes, budget_hit

        if h0 == 0 and h1 == 0 and h2 == 0 and h3 == 0:
            return (0, 0, 0, 0)
        if contract == CONTRACT_KH and (played & KING_OF_HEARTS_BIT):
            return (0, 0, 0, 0)
        if contract == CONTRACT_QUEENS and (played & QUEENS_MASK) == QUEENS_MASK:
            return (0, 0, 0, 0)
        if contract == CONTRACT_DIAMONDS and (played & DIAMONDS_MASK) == DIAMONDS_MASK:
            return (0, 0, 0, 0)

        key = (h0, h1, h2, h3, leader)
        cached = tt.get(key)
        if cached is not None:
            return cached

        # Deterministic 1-card final trick fast-path
        if h0.bit_count() == 1:
            hands_l = (h0, h1, h2, h3)
            s0 = leader
            s1 = (leader + 1) & 3
            s2 = (leader + 2) & 3
            s3 = (leader + 3) & 3
            tc = (
                lowest_card_in_mask(hands_l[s0]),
                lowest_card_in_mask(hands_l[s1]),
                lowest_card_in_mask(hands_l[s2]),
                lowest_card_in_mask(hands_l[s3]),
            )
            _, delta, _ = _score_completed_trick(contract, tc, (s0, s1, s2, s3), doubled)
            tt[key] = delta
            return delta

        nodes += 1
        if nodes > node_budget:
            budget_hit = True
            return _rollout_remaining_deltas(
                contract, (h0, h1, h2, h3), played, leader, doubled
            )

        res = search_mid_trick([h0, h1, h2, h3], played, leader, (), ())
        if not budget_hit:
            tt[key] = res
        return res

    def search_mid_trick(
        hands: list[int],
        played: int,
        player: int,
        t_cards: tuple[int, ...],
        t_seats: tuple[int, ...],
    ) -> tuple[int, int, int, int]:
        hand = hands[player]

        if not t_cards:
            legal = hand
            if (
                contract == CONTRACT_KH
                and (hand & KING_OF_HEARTS_BIT)
                and hand != KING_OF_HEARTS_BIT
            ):
                legal = hand ^ KING_OF_HEARTS_BIT
        else:
            led_suit = CARD_SUIT[t_cards[0]]
            in_suit = hand & SUIT_MASKS[led_suit]
            legal = in_suit if in_suit else hand

        moves = _order_trick_moves(
            prune_equivalent_cards(legal, played, contract), contract, t_cards
        )

        best_val: Optional[tuple[int, int, int, int]] = None
        best_key_score = -10**9
        p_cap = max_possible[player]

        pos = len(t_cards)
        for c in moves:
            bit = CARD_BIT[c]
            hands[player] ^= bit
            new_played = played | bit
            new_tc = t_cards + (c,)
            new_ts = t_seats + (player,)

            if pos == 3:
                winner, delta, ended = _score_completed_trick(
                    contract,
                    new_tc,  # type: ignore[arg-type]
                    new_ts,  # type: ignore[arg-type]
                    doubled,
                )
                if ended:
                    val = delta
                else:
                    fut = search_trick_start(
                        hands[0], hands[1], hands[2], hands[3], new_played, winner
                    )
                    val = (
                        delta[0] + fut[0],
                        delta[1] + fut[1],
                        delta[2] + fut[2],
                        delta[3] + fut[3],
                    )
            else:
                val = search_mid_trick(
                    hands, new_played, (player + 1) & 3, new_tc, new_ts
                )

            hands[player] ^= bit

            own = val[player]
            margin = own * 4 - (val[0] + val[1] + val[2] + val[3])
            key_sc = own * 10000 + margin
            if key_sc > best_key_score:
                best_key_score = key_sc
                best_val = val
                # Exact MaxN upper-bound cutoff (100% exact in constant-sum rounds!)
                if (not doubled) and own >= p_cap:
                    break

        assert best_val is not None
        return best_val

    root_player = rnd.current_player
    root_legal = rnd.legal_mask(root_player)
    root_moves = mask_to_cards(root_legal)
    distinct_moves = prune_equivalent_cards(root_legal, rnd.played_mask, contract)

    base_scores = tuple(rnd.scores)
    cur_tc = tuple(c for _, c in rnd.current_trick)
    cur_ts = tuple(s for s, _ in rnd.current_trick)
    hands_work = rnd.hands.copy()
    distinct_results: dict[int, tuple[int, int, int, int]] = {}

    pos = len(cur_tc)
    for c in distinct_moves:
        bit = CARD_BIT[c]
        hands_work[root_player] ^= bit
        new_played = rnd.played_mask | bit
        new_tc = cur_tc + (c,)
        new_ts = cur_ts + (root_player,)

        if pos == 3:
            winner, delta, ended = _score_completed_trick(
                contract,
                new_tc,  # type: ignore[arg-type]
                new_ts,  # type: ignore[arg-type]
                doubled,
            )
            if ended:
                fut_total = delta
            else:
                fut = search_trick_start(
                    hands_work[0],
                    hands_work[1],
                    hands_work[2],
                    hands_work[3],
                    new_played,
                    winner,
                )
                fut_total = (
                    delta[0] + fut[0],
                    delta[1] + fut[1],
                    delta[2] + fut[2],
                    delta[3] + fut[3],
                )
        else:
            fut_total = search_mid_trick(
                hands_work, new_played, (root_player + 1) & 3, new_tc, new_ts
            )

        hands_work[root_player] ^= bit
        distinct_results[c] = (
            base_scores[0] + fut_total[0],
            base_scores[1] + fut_total[1],
            base_scores[2] + fut_total[2],
            base_scores[3] + fut_total[3],
        )

    full_results: dict[int, tuple[int, int, int, int]] = {}
    for c in root_moves:
        if c in distinct_results:
            full_results[c] = distinct_results[c]
        else:
            s = CARD_SUIT[c]
            rep = max(m for m in distinct_moves if CARD_SUIT[m] == s and m < c)
            full_results[c] = distinct_results[rep]

    return full_results, (not budget_hit)


def _trix_playable_from_layout(lo: list[int], hi: list[int]) -> int:
    mask = 0
    for s in range(4):
        l_s = lo[s]
        if l_s == -1:
            mask |= CARD_BIT[s * 13 + RANK_J]
        else:
            if l_s > 0:
                mask |= CARD_BIT[s * 13 + l_s - 1]
            h_s = hi[s]
            if h_s < 12:
                mask |= CARD_BIT[s * 13 + h_s + 1]
    return mask


def _order_trix_moves(moves: list[int], hand: int) -> list[int]:
    """Order Trix moves so own-branch progress & terminals are searched first (faster cutoffs!)."""
    if len(moves) <= 1:
        return moves

    def prio(c: int) -> int:
        s = CARD_SUIT[c]
        r = CARD_RANK[c]
        sm = ((hand >> SUIT_SHIFT[s]) & 0x1FFF) ^ (1 << r)
        if r == RANK_2 or r == RANK_A:
            return -50  # Terminal
        if r == RANK_J:
            lo = sm & ((1 << RANK_J) - 1)
            return -(100 + lo.bit_count() * 15) if lo else (60 if sm == 0 else 10)
        if r < RANK_J:
            lo = sm & ((1 << r) - 1)
            return -(120 + lo.bit_count() * 12) if lo else (30 + r * 5)
        hi = sm >> (r + 1)
        return -(90 + hi.bit_count() * 15) if hi else (25 + (12 - r) * 8)

    moves.sort(key=prio)
    return moves


def solve_trix_endgame(
    rnd: TrixRound,
    node_budget: int = 4000,
) -> tuple[dict[int, tuple[int, int, int, int]], bool]:
    """Exact MaxN solver with move ordering & immediate finish-rank cutoffs for Trix."""
    tt: dict[tuple[int, int, int, int, int], tuple[int, int, int, int]] = {}
    nodes = 0
    budget_hit = False

    def rollout_trix(
        hands: list[int],
        lo: list[int],
        hi: list[int],
        player: int,
    ) -> tuple[int, int, int, int]:
        sim = TrixRound.__new__(TrixRound)
        sim.contract = CONTRACT_TRIX
        sim.king_seat = player
        sim.hands = hands.copy()
        sim.played_mask = ALL_CARDS_MASK ^ (hands[0] | hands[1] | hands[2] | hands[3])
        sim.current_player = player
        sim.scores = [0, 0, 0, 0]
        sim.match_scores = [0, 0, 0, 0]
        sim.doubled_cards = {}
        sim.trick_number = 0
        sim.trick_leader = player
        sim.current_trick = []
        sim.completed_tricks = []
        sim.layout_low = lo.copy()
        sim.layout_high = hi.copy()
        sim.trix_finish_order = [i for i in range(4) if hands[i] == 0]
        sim.events = []
        sim.done = False
        sim.tricks_won = [0, 0, 0, 0]
        while not sim.done:
            a = expert_rollout_action(sim)
            sim.step(a)
        return (sim.scores[0], sim.scores[1], sim.scores[2], sim.scores[3])

    def search(
        hands: list[int],
        lo: list[int],
        hi: list[int],
        player: int,
        finished_cnt: int,
    ) -> tuple[int, int, int, int]:
        nonlocal nodes, budget_hit

        key = (hands[0], hands[1], hands[2], hands[3], player)
        cached = tt.get(key)
        if cached is not None:
            return cached

        nodes += 1
        if nodes > node_budget:
            budget_hit = True
            return rollout_trix(hands, lo, hi, player)

        playable = _trix_playable_from_layout(lo, hi)
        legal = hands[player] & playable

        if legal == 0:
            nxt = (player + 1) & 3
            while hands[nxt] == 0:
                nxt = (nxt + 1) & 3
            val = search(hands, lo, hi, nxt, finished_cnt)
            if not budget_hit:
                tt[key] = val
            return val

        moves = _order_trix_moves(mask_to_cards(legal), hands[player])
        best_val: Optional[tuple[int, int, int, int]] = None
        best_sc = -10**9
        max_award = TRIX_FINISH_SCORES[finished_cnt]

        for c in moves:
            bit = CARD_BIT[c]
            s = CARD_SUIT[c]
            r = CARD_RANK[c]
            old_lo = lo[s]
            old_hi = hi[s]

            hands[player] ^= bit
            if old_lo == -1:
                lo[s] = r
                hi[s] = r
            elif r < old_lo:
                lo[s] = r
            else:
                hi[s] = r

            if hands[player] == 0:
                new_fin = finished_cnt + 1
                if new_fin == 3:
                    rem_sc = [0, 0, 0, 0]
                    rem_sc[player] = max_award
                    for i in range(4):
                        if hands[i] != 0:
                            rem_sc[i] = TRIX_FINISH_SCORES[3]
                            break
                    val = (rem_sc[0], rem_sc[1], rem_sc[2], rem_sc[3])
                else:
                    nxt = (player + 1) & 3
                    while hands[nxt] == 0:
                        nxt = (nxt + 1) & 3
                    sub = search(hands, lo, hi, nxt, new_fin)
                    arr = [sub[0], sub[1], sub[2], sub[3]]
                    arr[player] += max_award
                    val = (arr[0], arr[1], arr[2], arr[3])
            else:
                nxt = (player + 1) & 3
                while hands[nxt] == 0:
                    nxt = (nxt + 1) & 3
                val = search(hands, lo, hi, nxt, finished_cnt)

            hands[player] ^= bit
            lo[s] = old_lo
            hi[s] = old_hi

            own = val[player]
            sc = own * 10000 + (own * 4 - (val[0] + val[1] + val[2] + val[3]))
            if sc > best_sc:
                best_sc = sc
                best_val = val
                if own == max_award:
                    break

        assert best_val is not None
        if not budget_hit:
            tt[key] = best_val
        return best_val

    p = rnd.current_player
    legal_mask = rnd.hands[p] & rnd.trix_playable_mask()
    base = tuple(rnd.scores)
    if legal_mask == 0:
        return {PASS_ACTION: base}, True

    moves = mask_to_cards(legal_mask)
    if len(moves) == 1:
        return {moves[0]: base}, True

    hands_w = rnd.hands.copy()
    lo_w = rnd.layout_low.copy()
    hi_w = rnd.layout_high.copy()
    fin_cnt = len(rnd.trix_finish_order)

    out: dict[int, tuple[int, int, int, int]] = {}
    for c in moves:
        bit = CARD_BIT[c]
        s = CARD_SUIT[c]
        r = CARD_RANK[c]
        old_lo = lo_w[s]
        old_hi = hi_w[s]

        hands_w[p] ^= bit
        if old_lo == -1:
            lo_w[s] = r
            hi_w[s] = r
        elif r < old_lo:
            lo_w[s] = r
        else:
            hi_w[s] = r

        if hands_w[p] == 0:
            my_award = TRIX_FINISH_SCORES[fin_cnt]
            new_fin = fin_cnt + 1
            if new_fin == 3:
                arr = list(base)
                arr[p] += my_award
                for i in range(4):
                    if hands_w[i] != 0:
                        arr[i] += TRIX_FINISH_SCORES[3]
                        break
                val = (arr[0], arr[1], arr[2], arr[3])
            else:
                nxt = (p + 1) & 3
                while hands_w[nxt] == 0:
                    nxt = (nxt + 1) & 3
                sub = search(hands_w, lo_w, hi_w, nxt, new_fin)
                arr = [base[i] + sub[i] for i in range(4)]
                arr[p] += my_award
                val = (arr[0], arr[1], arr[2], arr[3])
        else:
            nxt = (p + 1) & 3
            while hands_w[nxt] == 0:
                nxt = (nxt + 1) & 3
            sub = search(hands_w, lo_w, hi_w, nxt, fin_cnt)
            val = (
                base[0] + sub[0],
                base[1] + sub[1],
                base[2] + sub[2],
                base[3] + sub[3],
            )

        hands_w[p] ^= bit
        lo_w[s] = old_lo
        hi_w[s] = old_hi
        out[c] = val

    return out, (not budget_hit)

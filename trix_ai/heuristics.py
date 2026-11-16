"""Expert Domain Heuristics, Fast Tactical Rollout Policies, and Benchmark Agents.

Upgraded V2 Engine:
- Live void-awareness (knows which players are already void in which suits).
- Active hunting of doubled K♥ and doubled Queens.
- Smart Diamonds guard preservation (never strips low Diamond guards when holding high ♦).
- Smart Trix Tempo Reserve (saves terminal Aces/2s as waiting moves before breaking chokers;
  prioritizes self-chains and deep 2/3/4 branches).
- Void-escape urgency when holding trapped K♥, Queens, or high Diamonds.
"""

from __future__ import annotations

import random
from typing import Optional

from .cards import (
    ALL_CARDS_MASK,
    CARD_BIT,
    CARD_RANK,
    CARD_SUIT,
    DIAMONDS_MASK,
    HEARTS_MASK,
    KING_OF_HEARTS,
    KING_OF_HEARTS_BIT,
    QUEENS,
    QUEENS_MASK,
    RANK_2,
    RANK_6,
    RANK_7,
    RANK_8,
    RANK_9,
    RANK_10,
    RANK_A,
    RANK_J,
    RANK_K,
    RANK_Q,
    SUIT_DIAMONDS,
    SUIT_HEARTS,
    SUIT_MASKS,
    SUIT_SHIFT,
    highest_card_in_mask,
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
    RoundObservation,
    TrixRound,
)


def _highest_below(suit_hand_mask: int, suit: int, limit_rank: int) -> int:
    """Return card id of highest card in `suit_hand_mask` with rank < limit_rank, or -1."""
    if limit_rank <= 0:
        return -1
    below_mask = suit_hand_mask & (((1 << limit_rank) - 1) << SUIT_SHIFT[suit])
    if below_mask:
        return highest_card_in_mask(below_mask)
    return -1


def _lowest_above(suit_hand_mask: int, suit: int, limit_rank: int) -> int:
    """Return card id of lowest card in `suit_hand_mask` with rank > limit_rank, or -1."""
    if limit_rank >= 12:
        return -1
    above_bits = ((1 << (12 - limit_rank)) - 1) << (SUIT_SHIFT[suit] + limit_rank + 1)
    above_mask = suit_hand_mask & above_bits
    if above_mask:
        return lowest_card_in_mask(above_mask)
    return -1


def _trick_winner_rank(
    trick: list[tuple[int, int]] | tuple[tuple[int, int], ...]
) -> tuple[int, int]:
    """Return (led_suit, current_highest_rank_in_led_suit)."""
    led_suit = CARD_SUIT[trick[0][1]]
    best_r = CARD_RANK[trick[0][1]]
    for i in range(1, len(trick)):
        c = trick[i][1]
        if CARD_SUIT[c] == led_suit:
            r = CARD_RANK[c]
            if r > best_r:
                best_r = r
    return led_suit, best_r


def compute_void_masks_from_events(events: list[tuple] | tuple[tuple, ...]) -> list[int]:
    """Return 4-element list where bit `s` of `voids[p]` is 1 iff seat `p` proved void in suit `s`."""
    voids = [0, 0, 0, 0]
    for ev in events:
        if ev[0] == "play":
            _, p, card, led_suit = ev
            if CARD_SUIT[card] != led_suit:
                voids[p] |= 1 << led_suit
    return voids


def _discard_danger_score(
    card: int,
    hand: int,
    contract: str,
    played_mask: int,
    doubled_cards: dict[int, int],
) -> float:
    """Higher score = better card to discard when void in led suit."""
    s = CARD_SUIT[card]
    r = CARD_RANK[card]
    sm = hand & SUIT_MASKS[s]
    cnt = sm.bit_count()

    if contract == CONTRACT_KH:
        if card == KING_OF_HEARTS:
            return 10000.0
        if s == SUIT_HEARTS:
            if r == RANK_A:
                return 1400.0 if not (played_mask & KING_OF_HEARTS_BIT) else 100.0
            if hand & KING_OF_HEARTS_BIT:
                # Keep Heart guards while we still hold K♥!
                return -300.0 + r
            return 45.0 + r * 3.0
        # Non-heart: create voids fast (especially if we hold K♥ or A♥!)
        need_void = bool(hand & (KING_OF_HEARTS_BIT | CARD_BIT[SUIT_HEARTS * 13 + RANK_A]))
        score = r * 9.0
        if cnt == 1:
            score += 140.0 if need_void else 85.0
        elif cnt == 2:
            score += 55.0 if need_void else 30.0
        return score

    if contract == CONTRACT_QUEENS:
        if r == RANK_Q:
            return 9000.0 if card in doubled_cards else 6000.0
        q_card = s * 13 + RANK_Q
        q_unseen = not ((played_mask | hand) & CARD_BIT[q_card])
        if r > RANK_Q and q_unseen:
            # A or K with unseen Queen in same suit is a prime disaster!
            low_g = ((sm >> SUIT_SHIFT[s]) & ((1 << RANK_Q) - 1)).bit_count()
            return 1500.0 + r * 60.0 - low_g * 70.0
        if hand & CARD_BIT[q_card]:
            if r > RANK_Q:
                return 650.0 + r * 20.0
            return -220.0 + r
        has_any_q = bool(hand & QUEENS_MASK)
        score = r * 8.0
        if cnt == 1:
            score += 120.0 if has_any_q else 75.0
        elif cnt == 2:
            score += 45.0 if has_any_q else 25.0
        return score

    if contract == CONTRACT_DIAMONDS:
        if s == SUIT_DIAMONDS:
            # Always dump highest Diamond! (Especially A♦, K♦, Q♦, J♦)
            return 2500.0 + r * 140.0
        # Non-diamond: dump highest dangerous card in short suit to open new voids
        has_hi_d = bool((hand & DIAMONDS_MASK) >> (SUIT_SHIFT[SUIT_DIAMONDS] + RANK_8))
        score = r * 11.0
        if cnt == 1:
            score += 110.0 if has_hi_d else 65.0
        elif cnt == 2:
            score += 40.0 if has_hi_d else 25.0
        return score

    # Collections (اللطوش): dump highest relative danger card
    unseen_in_suit = (ALL_CARDS_MASK ^ played_mask ^ hand) & SUIT_MASKS[s]
    higher_unseen = (
        unseen_in_suit & (((1 << (12 - r)) - 1) << (SUIT_SHIFT[s] + r + 1))
    ).bit_count() if r < 12 else 0
    lower_in_hand = (sm & (((1 << r) - 1) << SUIT_SHIFT[s])).bit_count() if r > 0 else 0
    danger = (12 - higher_unseen) * 20.0 + r * 6.5 - lower_in_hand * 15.0
    if cnt == 1 and r >= RANK_6:
        danger += 55.0
    elif cnt == 2 and higher_unseen <= 1:
        danger += 25.0
    return danger


def _choose_trix_action(
    hand: int,
    legal_mask: int,
    layout_low: list[int] | tuple[int, ...],
    layout_high: list[int] | tuple[int, ...],
    played_mask: int,
    rng: Optional[random.Random] = None,
    noise: float = 0.0,
) -> int:
    """Grandmaster-grade fast tactical policy for the Trix (dominoes) contract.

    Principles:
    1. Urgently push suits where we hold deep cards (2, 3, 4) or long self-chains.
    2. Preserve terminal cards (A, 2) as tempo reserves early so we play them BEFORE
       breaking any choker, rather than wasting them while we have deep progress moves.
    3. Never open a Jack or extend a branch where we hold 0 follow-up cards unless forced;
       when forced to break a choker, break the one unlocking the FEWEST opponent cards!
    """
    if legal_mask == 0:
        return PASS_ACTION
    if (legal_mask & (legal_mask - 1)) == 0:
        return lowest_card_in_mask(legal_mask)

    best_card = -1
    best_score = -1e9
    total_cards = hand.bit_count()

    # Check if we have any non-terminal positive progress move available
    m = legal_mask
    while m:
        lsb = m & -m
        c = lsb.bit_length() - 1
        m ^= lsb

        s = CARD_SUIT[c]
        r = CARD_RANK[c]
        sm_bits = (hand >> SUIT_SHIFT[s]) & 0x1FFF
        rem_bits = sm_bits ^ (1 << r)

        score = 0.0
        if r == RANK_J:
            low_bits = rem_bits & ((1 << RANK_J) - 1)
            high_bits = rem_bits >> (RANK_J + 1)
            own_cnt = rem_bits.bit_count()
            if low_bits:
                lowest_r = (low_bits & -low_bits).bit_length() - 1
                depth_needed = RANK_J - lowest_r  # 1..9 (9 if holding 2!)
                low_cnt = low_bits.bit_count()
                score += depth_needed * 15.0 + low_cnt * 10.0
                if lowest_r == RANK_2:
                    score += 48.0
                elif lowest_r == 1:  # 3
                    score += 32.0
                elif lowest_r == 2:  # 4
                    score += 18.0
                if (low_bits >> (RANK_J - 1)) & 1:
                    score += 16.0  # Direct 10 chain!
                    if (low_bits >> (RANK_J - 2)) & 1:
                        score += 10.0  # J-10-9 chain!
            else:
                # Zero low cards -> massive choke value in holding this Jack!
                score -= 72.0

            if high_bits:
                highest_h = high_bits.bit_length()  # 1=Q, 2=K, 3=A
                score += highest_h * 9.0 + high_bits.bit_count() * 8.0
                if high_bits == 0b111:  # Q+K+A!
                    score += 18.0
            else:
                score -= 22.0

            if own_cnt == 0:
                score -= 75.0  # Pure gift of all 12 cards to opponents!

        elif r < RANK_J:
            lower_bits = rem_bits & ((1 << r) - 1)
            if r == RANK_2:
                # Terminal 2: unlocks 0 cards!
                # Keep as tempo reserve early (score +8) so deep chains run first,
                # ALWAYS beats negative chokers (-35..-120), sprint near end (+45)!
                score = 45.0 if total_cards <= 4 else (20.0 if total_cards <= 7 else 8.0)
            elif lower_bits:
                lowest_r = (lower_bits & -lower_bits).bit_length() - 1
                depth_left = r - lowest_r
                low_cnt = lower_bits.bit_count()
                score += 28.0 + depth_left * 12.5 + low_cnt * 9.0
                if lowest_r == RANK_2:
                    score += 36.0
                elif lowest_r == 1:
                    score += 22.0
                # Immediate self-chain bonus (we hold r-1, maybe r-2)
                if (lower_bits >> (r - 1)) & 1:
                    score += 18.0
                    if r >= 2 and ((lower_bits >> (r - 2)) & 1):
                        score += 10.0
                # Gap-1 unblock bonus: we hold r-2 (opponent playing r-1 unlocks us!)
                elif r >= 2 and ((lower_bits >> (r - 2)) & 1):
                    score += 8.0
            else:
                # Choker! Unlocks r opponent cards below with 0 follow-up for us!
                score -= 34.0 + r * 9.0
        else:
            # Upper branch: Q(10), K(11), A(12)
            if r == RANK_A:
                # Terminal Ace: same tempo-reserve law!
                score = 45.0 if total_cards <= 4 else (20.0 if total_cards <= 7 else 9.0)
            else:
                higher_bits = rem_bits >> (r + 1)
                if higher_bits:
                    score += 26.0 + higher_bits.bit_count() * 16.0
                    if (rem_bits >> (r + 1)) & 1:
                        score += 14.0
                else:
                    # Choker unlocking K/A (1 or 2 cards) for opponents
                    unlocked = 12 - r
                    score -= 28.0 + unlocked * 12.0

        if noise > 0.0 and rng is not None:
            score += rng.uniform(-noise, noise)

        if score > best_score:
            best_score = score
            best_card = c

    return best_card


def expert_rollout_action(
    rnd: TrixRound,
    rng: Optional[random.Random] = None,
    noise: float = 0.0,
    void_masks: Optional[list[int]] = None,
) -> int:
    """Fast, card-counting & void-aware tactical action selector for `rnd.current_player`.

    Strictly uses only public info + current player's own hand (zero cheating / zero
    strategy-fusion leakage).
    """
    p = rnd.current_player
    hand = rnd.hands[p]
    contract = rnd.contract

    if contract == CONTRACT_TRIX:
        legal_mask = hand & rnd.trix_playable_mask()
        return _choose_trix_action(
            hand,
            legal_mask,
            rnd.layout_low,
            rnd.layout_high,
            rnd.played_mask,
            rng=rng,
            noise=noise,
        )

    legal_mask = rnd.legal_mask(p)
    if (legal_mask & (legal_mask - 1)) == 0:
        return lowest_card_in_mask(legal_mask)

    trick = rnd.current_trick
    played = rnd.played_mask
    unseen_others = ALL_CARDS_MASK ^ played ^ hand
    pos = len(trick)  # 0=lead, 1=2nd, 2=3rd, 3=4th

    if void_masks is None and rnd.events:
        void_masks = compute_void_masks_from_events(rnd.events)

    # ================= LEADING A TRICK =================
    if pos == 0:
        return _choose_lead(
            p,
            hand,
            legal_mask,
            contract,
            played,
            unseen_others,
            rnd.doubled_cards,
            void_masks,
            rng,
            noise,
        )

    led_suit, win_rank = _trick_winner_rank(trick)
    in_suit = hand & SUIT_MASKS[led_suit]

    # ================= OFF-SUIT DISCARD (VOID) =================
    if not in_suit:
        best_c = -1
        best_s = -1e9
        m = legal_mask
        while m:
            lsb = m & -m
            c = lsb.bit_length() - 1
            m ^= lsb
            sc = _discard_danger_score(c, hand, contract, played, rnd.doubled_cards)
            if noise > 0.0 and rng is not None:
                sc += rng.uniform(-noise, noise)
            if sc > best_s:
                best_s = sc
                best_c = c
        return best_c

    # ================= FOLLOWING SUIT =================
    if (in_suit & (in_suit - 1)) == 0:
        return lowest_card_in_mask(in_suit)

    trick_mask = 0
    for _, tc in trick:
        trick_mask |= CARD_BIT[tc]

    is_last = pos == 3

    # Check if any player yet to act after `p` is KNOWN void in `led_suit`
    opp_behind_known_void = False
    if void_masks is not None and not is_last:
        sbit = 1 << led_suit
        for step_ahead in range(1, 4 - pos):
            seat_behind = (p + step_ahead) & 3
            if void_masks[seat_behind] & sbit:
                opp_behind_known_void = True
                break

    # --- KING OF HEARTS ---
    if contract == CONTRACT_KH:
        kh_in_trick = bool(trick_mask & KING_OF_HEARTS_BIT)
        if led_suit == SUIT_HEARTS:
            if kh_in_trick:
                duck = _highest_below(in_suit, SUIT_HEARTS, win_rank)
                return duck if duck != -1 else highest_card_in_mask(in_suit)
            if (in_suit & KING_OF_HEARTS_BIT) and win_rank == RANK_A:
                return KING_OF_HEARTS  # Kill shot onto A♥!
            if is_last:
                if in_suit & CARD_BIT[SUIT_HEARTS * 13 + RANK_A]:
                    return SUIT_HEARTS * 13 + RANK_A  # Free shed of A♥!
                safe = in_suit & ~KING_OF_HEARTS_BIT
                return highest_card_in_mask(safe) if safe else KING_OF_HEARTS
            under_k = _highest_below(in_suit, SUIT_HEARTS, RANK_K)
            if under_k != -1:
                return under_k
            if in_suit & CARD_BIT[SUIT_HEARTS * 13 + RANK_A]:
                return SUIT_HEARTS * 13 + RANK_A
            return KING_OF_HEARTS

        if kh_in_trick:
            duck = _highest_below(in_suit, led_suit, win_rank)
            return duck if duck != -1 else highest_card_in_mask(in_suit)
        if is_last:
            # Clean 4th seat! If we hold K♥ and want to stay off lead (or burn dangerous A/K):
            if hand & KING_OF_HEARTS_BIT:
                # If our only non-K♥ cards are limited, shedding high card in short suit helps void!
                return highest_card_in_mask(in_suit)
            return highest_card_in_mask(in_suit)
        kh_out = bool(unseen_others & KING_OF_HEARTS_BIT)
        unseen_led = (unseen_others & SUIT_MASKS[led_suit]).bit_count()
        if kh_out and (opp_behind_known_void or unseen_led <= 6):
            duck = _highest_below(in_suit, led_suit, win_rank)
            if duck != -1:
                return duck
            return lowest_card_in_mask(in_suit)
        duck = _highest_below(in_suit, led_suit, win_rank)
        if duck != -1:
            return duck
        return lowest_card_in_mask(in_suit)

    # --- QUEENS ---
    if contract == CONTRACT_QUEENS:
        q_in_trick = bool(trick_mask & QUEENS_MASK)
        q_card = led_suit * 13 + RANK_Q
        q_in_hand = bool(in_suit & CARD_BIT[q_card])
        q_unseen = bool(unseen_others & CARD_BIT[q_card])

        if q_in_trick:
            duck = _highest_below(in_suit, led_suit, win_rank)
            return duck if duck != -1 else highest_card_in_mask(in_suit)

        if q_in_hand and win_rank > RANK_Q:
            return q_card  # Dump our Queen onto K/A!

        if is_last:
            if q_in_hand:
                safe = in_suit ^ CARD_BIT[q_card]
                return highest_card_in_mask(safe)
            # Clean 4th seat! Burn A/K of suits with unseen Q immediately!
            if q_unseen and highest_card_in_mask(in_suit) > q_card:
                return highest_card_in_mask(in_suit)
            # Otherwise burn highest card (sheds future liabilities safely)
            return highest_card_in_mask(in_suit)

        if q_unseen:
            safe_under_q = _highest_below(in_suit, led_suit, RANK_Q)
            unseen_led = (unseen_others & SUIT_MASKS[led_suit]).bit_count()
            if opp_behind_known_void or unseen_led <= 6:
                duck = _highest_below(in_suit, led_suit, win_rank)
                if duck != -1:
                    return duck
            if safe_under_q != -1:
                duck = _highest_below(in_suit, led_suit, win_rank)
                if duck != -1 and (opp_behind_known_void or unseen_led <= 8):
                    return duck
                return safe_under_q
            return lowest_card_in_mask(in_suit)

        safe_mask = (in_suit ^ CARD_BIT[q_card]) if q_in_hand else in_suit
        duck = _highest_below(safe_mask, led_suit, win_rank)
        if duck != -1:
            return duck
        return lowest_card_in_mask(safe_mask)

    # --- DIAMONDS ---
    if contract == CONTRACT_DIAMONDS:
        d_in_trick = bool(trick_mask & DIAMONDS_MASK)
        if led_suit == SUIT_DIAMONDS or d_in_trick:
            duck = _highest_below(in_suit, led_suit, win_rank)
            if duck != -1:
                return duck
            if is_last:
                return highest_card_in_mask(in_suit)
            lo_beat = _lowest_above(in_suit, led_suit, win_rank)
            if lo_beat != -1:
                lo_r = CARD_RANK[lo_beat]
                if lo_r < 12:
                    unseen_over_lo = unseen_others & (
                        ((1 << (12 - lo_r)) - 1) << (SUIT_SHIFT[led_suit] + lo_r + 1)
                    )
                    if unseen_over_lo:
                        return lo_beat
            return highest_card_in_mask(in_suit)

        # Non-diamond clean trick so far
        if is_last:
            # 100% clean! Burn highest card unless winning forces us to lead high Diamonds!
            rem_after = hand ^ CARD_BIT[highest_card_in_mask(in_suit)]
            only_hi_diam_left = (
                rem_after != 0
                and (rem_after & ~DIAMONDS_MASK) == 0
                and lowest_card_in_mask(rem_after) >= SUIT_DIAMONDS * 13 + RANK_9
            )
            if only_hi_diam_left:
                duck = _highest_below(in_suit, led_suit, win_rank)
                if duck != -1:
                    return duck
            return highest_card_in_mask(in_suit)

        unseen_led = (unseen_others & SUIT_MASKS[led_suit]).bit_count()
        unseen_diam = (unseen_others & DIAMONDS_MASK).bit_count()
        if unseen_diam > 0 and (opp_behind_known_void or unseen_led <= 7):
            duck = _highest_below(in_suit, led_suit, win_rank)
            if duck != -1:
                return duck
            return lowest_card_in_mask(in_suit)
        duck = _highest_below(in_suit, led_suit, win_rank)
        if duck != -1:
            return duck
        return lowest_card_in_mask(in_suit)

    # --- COLLECTIONS (اللطوش) ---
    duck = _highest_below(in_suit, led_suit, win_rank)
    if duck != -1:
        return duck
    if is_last:
        return highest_card_in_mask(in_suit)
    lo_beat = _lowest_above(in_suit, led_suit, win_rank)
    if lo_beat != -1:
        lo_r = CARD_RANK[lo_beat]
        if lo_r < 12:
            unseen_over_lo = unseen_others & (
                ((1 << (12 - lo_r)) - 1) << (SUIT_SHIFT[led_suit] + lo_r + 1)
            )
            if unseen_over_lo:
                return lo_beat
    return highest_card_in_mask(in_suit)


def _choose_lead(
    p: int,
    hand: int,
    legal_mask: int,
    contract: str,
    played_mask: int,
    unseen_others: int,
    doubled_cards: dict[int, int],
    void_masks: Optional[list[int]],
    rng: Optional[random.Random],
    noise: float,
) -> int:
    best_c = -1
    best_sc = -1e9

    has_kh = bool(hand & KING_OF_HEARTS_BIT)
    kh_unseen = bool(unseen_others & KING_OF_HEARTS_BIT)
    has_ah = bool(hand & CARD_BIT[SUIT_HEARTS * 13 + RANK_A])

    # Count how many opponents are known void in each suit
    opp_void_cnt = [0, 0, 0, 0]
    if void_masks is not None:
        for opp in range(4):
            if opp != p:
                vm = void_masks[opp]
                for s in range(4):
                    if (vm >> s) & 1:
                        opp_void_cnt[s] += 1

    # Diamonds hand profile
    my_dm = (hand >> SUIT_SHIFT[SUIT_DIAMONDS]) & 0x1FFF
    my_hi_d_cnt = (my_dm >> RANK_9).bit_count()  # 10♦, J♦, Q♦, K♦, A♦
    my_low_d_cnt = (my_dm & ((1 << RANK_9) - 1)).bit_count()

    for s in range(4):
        sm = legal_mask & SUIT_MASKS[s]
        if not sm:
            continue
        unseen_s = unseen_others & SUIT_MASKS[s]
        unseen_cnt = unseen_s.bit_count()
        my_cnt = (hand & SUIT_MASKS[s]).bit_count()

        candidates = [lowest_card_in_mask(sm)]
        if contract == CONTRACT_KH and s == SUIT_HEARTS and not has_kh and kh_unseen:
            hi_under_k = _highest_below(sm, SUIT_HEARTS, RANK_K)
            if hi_under_k != -1 and hi_under_k != candidates[0]:
                candidates.append(hi_under_k)
        elif contract == CONTRACT_QUEENS:
            hi_under_q = _highest_below(sm, s, RANK_Q)
            if hi_under_q != -1 and hi_under_q != candidates[0]:
                candidates.append(hi_under_q)

        for c in candidates:
            r = CARD_RANK[c]
            higher_unseen = (
                (unseen_s & (((1 << (12 - r)) - 1) << (SUIT_SHIFT[s] + r + 1))).bit_count()
                if r < 12
                else 0
            )
            sc = 0.0

            if contract == CONTRACT_KH:
                if has_kh:
                    if s == SUIT_HEARTS:
                        sc = -550.0 - r * 5.0
                    else:
                        # Create a void ASAP in shortest non-Heart suit!
                        sc = 150.0 - my_cnt * 34.0 - r * 3.0 + higher_unseen * 5.0
                else:
                    if s == SUIT_HEARTS and kh_unseen:
                        kh_doubled_by_opp = (
                            KING_OF_HEARTS in doubled_cards
                            and doubled_cards[KING_OF_HEARTS] != p
                        )
                        if r < RANK_K and not has_ah:
                            # HUNT THE SHEIKH (especially if opponent doubled it!)
                            sc = (320.0 if kh_doubled_by_opp else 230.0) + r * 9.0 + unseen_cnt * 5.0
                        elif r < RANK_K and has_ah:
                            sc = (45.0 if unseen_cnt >= 6 else -140.0) - r * 3.0
                        else:
                            sc = -950.0
                    else:
                        sc = (
                            higher_unseen * 12.0
                            - r * 6.0
                            + unseen_cnt * 4.0
                            - opp_void_cnt[s] * 70.0
                        )
                        if unseen_cnt <= 3:
                            sc -= 85.0
                        # If we hold A♥ alone/short, try to create a void to dump A♥!
                        if has_ah and (hand & HEARTS_MASK).bit_count() <= 2 and my_cnt <= 2:
                            sc += 55.0

            elif contract == CONTRACT_QUEENS:
                q_card = s * 13 + RANK_Q
                has_q = bool(hand & CARD_BIT[q_card])
                q_unseen = bool(unseen_others & CARD_BIT[q_card])
                q_doubled_by_opp = q_card in doubled_cards and doubled_cards[q_card] != p
                has_ka = bool(
                    hand & (CARD_BIT[s * 13 + RANK_K] | CARD_BIT[s * 13 + RANK_A])
                )

                if r == RANK_Q:
                    sc = -380.0
                elif r > RANK_Q and q_unseen:
                    sc = -550.0 - r * 12.0
                elif has_q:
                    # Never strip guards from our own Queen unless forced
                    sc = -130.0 - (4 - my_cnt) * 30.0 + higher_unseen * 5.0
                elif q_unseen and r < RANK_Q and not has_ka:
                    # Flush unseen Queen safely (huge bonus if opponent doubled it!)
                    sc = (
                        (210.0 if q_doubled_by_opp else 125.0)
                        + r * 5.0
                        + higher_unseen * 7.0
                        + unseen_cnt * 4.0
                        - opp_void_cnt[s] * 55.0
                    )
                else:
                    # Side suit: if we hold a Queen or dangerous K/A, void shortest safe suit!
                    need_void = bool(hand & QUEENS_MASK)
                    sc = (
                        55.0
                        + higher_unseen * 10.0
                        - r * 5.0
                        + unseen_cnt * 3.0
                        - opp_void_cnt[s] * 60.0
                    )
                    if need_void and my_cnt <= 2 and not has_ka:
                        sc += 75.0 - my_cnt * 20.0
                    if has_ka and q_unseen:
                        sc -= 140.0
                    if unseen_cnt <= 3:
                        sc -= 70.0

            elif contract == CONTRACT_DIAMONDS:
                if s == SUIT_DIAMONDS:
                    if my_hi_d_cnt > 0 and my_low_d_cnt <= my_hi_d_cnt + 1:
                        # CRITICAL FIX: Do NOT lead Diamonds when holding high Diamonds & few guards!
                        sc = -140.0 + higher_unseen * 6.0 - r * 10.0
                    else:
                        # Safe low Diamond lead!
                        sc = higher_unseen * 15.0 - r * 14.0
                    if higher_unseen == 0:
                        sc -= 350.0
                else:
                    sc = (
                        higher_unseen * 13.0
                        - r * 7.0
                        + unseen_cnt * 5.0
                        - opp_void_cnt[s] * 75.0
                    )
                    if my_hi_d_cnt > 0 and my_cnt <= 2:
                        # Create a void fast to dump A♦/K♦/Q♦ off-suit!
                        sc += 85.0 - my_cnt * 25.0
                    if unseen_cnt <= 3 and (unseen_others & DIAMONDS_MASK):
                        sc -= 80.0

            else:  # CONTRACT_COLLECTIONS
                sc = (
                    higher_unseen * 22.0
                    - r * 9.0
                    + unseen_cnt * 3.5
                    - opp_void_cnt[s] * 25.0
                )
                if higher_unseen == 0:
                    sc -= 260.0
                elif higher_unseen == 1 and unseen_cnt <= 2:
                    sc -= 45.0
                # Avoid leading a 2-card suit containing a naked high card (e.g. 2 + K)
                if my_cnt == 2 and highest_card_in_mask(sm) % 13 >= RANK_J:
                    sc -= 28.0

            if noise > 0.0 and rng is not None:
                sc += rng.uniform(-noise, noise)
            if sc > best_sc:
                best_sc = sc
                best_c = c

    return best_c


# ==============================================================================
# Analytical Hand Evaluators
# ==============================================================================


def analytical_contract_surplus(hand: int, contract: str) -> float:
    """Fast analytical estimate of (Expected Score - Average Baseline) for `hand` in `contract`."""
    if contract == CONTRACT_KH:
        has_kh = bool(hand & KING_OF_HEARTS_BIT)
        has_ah = bool(hand & CARD_BIT[SUIT_HEARTS * 13 + RANK_A])
        h_cnt = (hand & HEARTS_MASK).bit_count()
        min_other = min(
            (hand & SUIT_MASKS[s]).bit_count() for s in range(4) if s != SUIT_HEARTS
        )
        if has_kh:
            if h_cnt >= 5 or (min_other == 0 and h_cnt >= 2):
                return 22.0
            if h_cnt >= 4 or (min_other <= 1 and h_cnt >= 3):
                return 6.0
            if h_cnt == 1 and min_other >= 2:
                return -55.0
            return -28.0 + h_cnt * 8.0 - min_other * 6.0
        if has_ah:
            if h_cnt <= 2:
                return -25.0 - (2 - h_cnt) * 12.0
            if h_cnt >= 4:
                return 8.0
            return -6.0
        return 19.0 + min(h_cnt, 4) * 1.5

    if contract == CONTRACT_QUEENS:
        est = 0.0
        voids = sum(1 for s in range(4) if (hand & SUIT_MASKS[s]) == 0)
        for s in range(4):
            sm = (hand >> SUIT_SHIFT[s]) & 0x1FFF
            has_q = bool((sm >> RANK_Q) & 1)
            has_k = bool((sm >> RANK_K) & 1)
            has_a = bool((sm >> RANK_A) & 1)
            low_guards = (sm & ((1 << RANK_Q) - 1)).bit_count()
            if has_q:
                if low_guards >= 3 or (voids >= 1 and low_guards >= 1):
                    est -= 2.0
                elif low_guards == 0:
                    est -= 22.0
                else:
                    est -= 14.0 - low_guards * 3.0
            else:
                if has_a and low_guards <= 2:
                    est -= 12.0 - low_guards * 3.0
                if has_k and low_guards <= 1:
                    est -= 8.0 - low_guards * 3.0
        return est - (-25.0)

    if contract == CONTRACT_DIAMONDS:
        dm = (hand >> SUIT_SHIFT[SUIT_DIAMONDS]) & 0x1FFF
        d_cnt = dm.bit_count()
        est = 0.0
        for r in range(13):
            if (dm >> r) & 1:
                if r >= RANK_J:
                    est -= 11.0 + (r - RANK_J) * 3.0
                elif r >= RANK_7:
                    est -= 5.0
                else:
                    est -= 1.2
        if d_cnt <= 1 and (dm >> RANK_9) == 0:
            est += 8.0
        hi_other = 0
        for s in range(4):
            if s != SUIT_DIAMONDS:
                sm = (hand >> SUIT_SHIFT[s]) & 0x1FFF
                hi_other += (sm >> RANK_J).bit_count()
        est -= hi_other * 2.2
        return est - (-32.5)

    if contract == CONTRACT_COLLECTIONS:
        est = 0.0
        for s in range(4):
            sm = (hand >> SUIT_SHIFT[s]) & 0x1FFF
            cnt = sm.bit_count()
            if cnt == 0:
                est += 6.0
                continue
            low_count = 0
            for r in range(13):
                if (sm >> r) & 1:
                    if r <= 4:
                        low_count += 1
                    elif r <= 8:
                        est -= 5.0 if low_count == 0 else 1.5
                    else:
                        danger = max(0.0, (r - 7) * 4.2 - low_count * 3.0)
                        est -= danger
        return est - (-48.75)

    # CONTRACT_TRIX
    score = 0.0
    for s in range(4):
        sm = (hand >> SUIT_SHIFT[s]) & 0x1FFF
        if (sm >> RANK_J) & 1:
            score += 18.0
        if (sm >> RANK_10) & 1:
            score += 9.0
        if (sm >> RANK_Q) & 1:
            score += 9.0
        if (sm >> RANK_K) & 1:
            score += 6.0
        if (sm >> RANK_A) & 1:
            score += 4.0
        low_bits = sm & ((1 << RANK_J) - 1)
        if low_bits:
            lowest_r = (low_bits & -low_bits).bit_length() - 1
            if lowest_r == RANK_2:
                score -= 22.0 if not ((sm >> RANK_J) & 1) else 8.0
            elif lowest_r == 1:
                score -= 14.0 if not ((sm >> RANK_J) & 1) else 4.0
            elif lowest_r == 2:
                score -= 8.0
        else:
            score += 8.0
    return score


# ==============================================================================
# Standalone Benchmark Agents
# ==============================================================================


class BaseAgent:
    name: str = "BaseAgent"

    def choose_contract(
        self, hand_mask: int, remaining_contracts: list[str], match_scores: list[int], seat: int
    ) -> str:
        raise NotImplementedError

    def choose_doubles(
        self, contract: str, hand_mask: int, candidates: list[int], match_scores: list[int], seat: int
    ) -> list[int]:
        raise NotImplementedError

    def choose_action(self, obs: RoundObservation) -> int:
        raise NotImplementedError


class RandomAI(BaseAgent):
    """Uniform random legal play."""

    name = "RandomAI"

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)

    def choose_contract(
        self, hand_mask: int, remaining_contracts: list[str], match_scores: list[int], seat: int
    ) -> str:
        return self.rng.choice(remaining_contracts)

    def choose_doubles(
        self, contract: str, hand_mask: int, candidates: list[int], match_scores: list[int], seat: int
    ) -> list[int]:
        return []

    def choose_action(self, obs: RoundObservation) -> int:
        if obs.contract == CONTRACT_TRIX:
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
            legal = obs.my_hand_mask & playable
            return PASS_ACTION if legal == 0 else self.rng.choice(mask_to_cards(legal))
        if not obs.current_trick:
            hand = obs.my_hand_mask
            if (
                obs.contract == CONTRACT_KH
                and (hand & KING_OF_HEARTS_BIT)
                and hand != KING_OF_HEARTS_BIT
            ):
                hand ^= KING_OF_HEARTS_BIT
            return self.rng.choice(mask_to_cards(hand))
        led = CARD_SUIT[obs.current_trick[0][1]]
        in_suit = obs.my_hand_mask & SUIT_MASKS[led]
        return self.rng.choice(mask_to_cards(in_suit if in_suit else obs.my_hand_mask))


class IntermediateAI(BaseAgent):
    """Casual human-level player: plays low, dumps high cards, basic contract choices."""

    name = "IntermediateAI"

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)

    def choose_contract(
        self, hand_mask: int, remaining_contracts: list[str], match_scores: list[int], seat: int
    ) -> str:
        scored = [
            (analytical_contract_surplus(hand_mask, c) + self.rng.uniform(-18, 18), c)
            for c in remaining_contracts
        ]
        scored.sort(reverse=True)
        return scored[0][1]

    def choose_doubles(
        self, contract: str, hand_mask: int, candidates: list[int], match_scores: list[int], seat: int
    ) -> list[int]:
        out = []
        for c in candidates:
            s = CARD_SUIT[c]
            cnt = (hand_mask & SUIT_MASKS[s]).bit_count()
            if cnt >= 4:
                out.append(c)
        return out

    def choose_action(self, obs: RoundObservation) -> int:
        hand = obs.my_hand_mask
        if obs.contract == CONTRACT_TRIX:
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
            legal = hand & playable
            if legal == 0:
                return PASS_ACTION
            cards = mask_to_cards(legal)
            cards.sort(key=lambda c: CARD_RANK[c])
            return cards[0]

        if not obs.current_trick:
            legal = hand
            if (
                obs.contract == CONTRACT_KH
                and (hand & KING_OF_HEARTS_BIT)
                and hand != KING_OF_HEARTS_BIT
            ):
                legal ^= KING_OF_HEARTS_BIT
            cards = mask_to_cards(legal)
            cards.sort(key=lambda c: CARD_RANK[c])
            return cards[0]

        led, win_r = _trick_winner_rank(obs.current_trick)
        in_suit = hand & SUIT_MASKS[led]
        if in_suit:
            duck = _highest_below(in_suit, led, win_r)
            if duck != -1:
                return duck
            return lowest_card_in_mask(in_suit)

        if obs.contract == CONTRACT_KH and (hand & KING_OF_HEARTS_BIT):
            return KING_OF_HEARTS
        if obs.contract == CONTRACT_QUEENS and (hand & QUEENS_MASK):
            return highest_card_in_mask(hand & QUEENS_MASK)
        if obs.contract == CONTRACT_DIAMONDS and (hand & DIAMONDS_MASK):
            return highest_card_in_mask(hand & DIAMONDS_MASK)
        cards = mask_to_cards(hand)
        cards.sort(key=lambda c: CARD_RANK[c], reverse=True)
        return cards[0]


class ProHeuristicAI(BaseAgent):
    """Strong rule-based & card-counting Trix player (expert heuristics, no search)."""

    name = "ProHeuristicAI"

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)

    def choose_contract(
        self, hand_mask: int, remaining_contracts: list[str], match_scores: list[int], seat: int
    ) -> str:
        return max(
            remaining_contracts,
            key=lambda c: analytical_contract_surplus(hand_mask, c),
        )

    def choose_doubles(
        self, contract: str, hand_mask: int, candidates: list[int], match_scores: list[int], seat: int
    ) -> list[int]:
        out = []
        voids = sum(1 for s in range(4) if (hand_mask & SUIT_MASKS[s]) == 0)
        for c in candidates:
            s = CARD_SUIT[c]
            sm = (hand_mask >> SUIT_SHIFT[s]) & 0x1FFF
            low_guards = (sm & ((1 << CARD_RANK[c]) - 1)).bit_count()
            if contract == CONTRACT_KH:
                if low_guards >= 4 or (low_guards >= 2 and voids >= 1):
                    out.append(c)
            elif contract == CONTRACT_QUEENS:
                if low_guards >= 3 or (low_guards >= 1 and voids >= 1):
                    out.append(c)
        return out

    def choose_action(self, obs: RoundObservation) -> int:
        rnd = TrixRound.__new__(TrixRound)
        rnd.contract = obs.contract
        rnd.king_seat = obs.king_seat
        rnd.hands = [0, 0, 0, 0]
        rnd.hands[obs.seat] = obs.my_hand_mask
        rnd.played_mask = obs.played_mask
        rnd.current_player = obs.seat
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
        rnd.events = list(obs.events)
        rnd.done = obs.done
        rnd.tricks_won = [0, 0, 0, 0]
        return expert_rollout_action(rnd, rng=self.rng, noise=0.0)

"""Interactive Web Arena & Grandmaster Coach Server for Individual Trix.

Zero external dependencies (Python standard library ThreadingHTTPServer).
Binds to 0.0.0.0:8000 for live preview.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

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
    RANK_STRS,
    SUIT_AR,
    SUIT_CODES,
    SUIT_DIAMONDS,
    SUIT_HEARTS,
    SUIT_MASKS,
    SUIT_SYMBOLS,
    card_ar,
    card_str,
    mask_to_cards,
    parse_card,
)
from .engine import (
    CONTRACT_AR,
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
from .grandmaster import GrandmasterAI
from .heuristics import BaseAgent, IntermediateAI, ProHeuristicAI, analytical_contract_surplus


STATIC_DIR = Path(__file__).parent / "static"

SEAT_NAMES_AR = ("أنت / الجنوب", "الشرق", "الشمال", "الغرب")


def _card_obj(card: int) -> dict[str, Any]:
    s = CARD_SUIT[card]
    r = CARD_RANK[card]
    return {
        "id": card,
        "suit": s,
        "suit_symbol": SUIT_SYMBOLS[s],
        "suit_code": SUIT_CODES[s],
        "suit_ar": SUIT_AR[s],
        "rank": r,
        "rank_str": RANK_STRS[r],
        "label": card_str(card),
        "ar": card_ar(card),
        "red": s in (SUIT_DIAMONDS, SUIT_HEARTS),
    }


def _sort_hand_cards(mask: int) -> list[int]:
    cards = mask_to_cards(mask)
    # Sort by suit (Spades, Hearts, Clubs, Diamonds for visual contrast) then rank descending
    suit_order = {3: 0, 2: 1, 0: 2, 1: 3}
    cards.sort(key=lambda c: (suit_order[CARD_SUIT[c]], -CARD_RANK[c]))
    return cards


class GameSession:
    def __init__(
        self,
        mode: str = "play",
        opponent_level: str = "grandmaster",
        gm_level: str = "monster",
        seed: Optional[int] = None,
    ) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.mode = mode  # "play" (human at seat 0) or "spectate" (GM at seat 0)
        self.opponent_level = opponent_level
        self.gm_level = gm_level
        self.seed = seed if seed is not None else random.randrange(1, 10**7)
        self.match = TrixMatch(seed=self.seed)
        self.lock = threading.Lock()
        self.last_trick_flash: Optional[dict] = None
        self.last_analysis: Optional[dict] = None
        self.last_contract_analysis: Optional[list[dict]] = None
        self.last_double_analysis: Optional[list[dict]] = None
        self.event_feed: list[str] = []
        self.awaiting_round_ack: bool = False
        self.last_round_summary: Optional[dict] = None

        # Coach AI (always monster-grade for analysis/hints)
        self.coach = GrandmasterAI(level=gm_level, seed=self.seed + 99)

        # Build seat agents
        self.agents: list[Optional[BaseAgent]] = [None, None, None, None]
        if mode == "spectate":
            self.agents[0] = GrandmasterAI(level=gm_level, seed=self.seed + 10)
        for s in (1, 2, 3):
            if opponent_level == "grandmaster":
                self.agents[s] = GrandmasterAI(level="tournament", seed=self.seed + s * 17)
            elif opponent_level == "pro":
                self.agents[s] = ProHeuristicAI(seed=self.seed + s * 17)
            else:
                self.agents[s] = IntermediateAI(seed=self.seed + s * 17)

        self._push_log(
            f"بدأت مباراة جديدة (4 ممالك — 20 جولة). الملك الأول (صاحب 7♥): {self.seat_label(self.match.first_king)}."
        )
        self._auto_advance_until_human_or_pause(single_step_spectate=False)

    def seat_label(self, seat: int) -> str:
        if seat == 0:
            return "العقل الخارق (GM)" if self.mode == "spectate" else "أنت (الجنوب)"
        tag = {
            "grandmaster": "GM",
            "pro": "Pro",
            "intermediate": "متوسط",
        }.get(self.opponent_level, "AI")
        names = {1: "الشرق", 2: "الشمال", 3: "الغرب"}
        return f"{names[seat]} ({tag})"

    def _push_log(self, msg: str) -> None:
        self.event_feed.append(msg)
        if len(self.event_feed) > 40:
            self.event_feed = self.event_feed[-40:]

    def _is_human_seat(self, seat: int) -> bool:
        return self.mode == "play" and seat == 0

    def _handle_ai_doubles(self) -> None:
        rnd = self.match.current_round
        assert rnd is not None
        for s in range(4):
            if self._is_human_seat(s):
                continue
            cands = rnd.doubler_candidates(s)
            if not cands:
                continue
            ag = self.agents[s]
            assert ag is not None
            if isinstance(ag, GrandmasterAI):
                chosen = ag.choose_doubles(
                    rnd.contract,
                    rnd.hands[s],
                    cands,
                    list(self.match.scores),
                    s,
                    king_seat=rnd.king_seat,
                )
            else:
                chosen = ag.choose_doubles(
                    rnd.contract, rnd.hands[s], cands, list(self.match.scores), s
                )
            for c in chosen:
                rnd.apply_double(s, c)
                self._push_log(f"🔥 {self.seat_label(s)} دبّل {card_ar(c)}!")

    def _auto_advance_until_human_or_pause(self, single_step_spectate: bool = False) -> None:
        """Advance AI turns until human input is required or round/match pauses."""
        if self.awaiting_round_ack or self.match.phase == "match_over":
            return

        # In spectate mode, stop after 1 meaningful action when single_step_spectate=True
        steps_taken = 0
        while True:
            if self.match.phase == "match_over" or self.awaiting_round_ack:
                return

            if self.match.phase == "choose_contract":
                king = self.match.current_king
                if self._is_human_seat(king):
                    # Wait for human to pick contract
                    return
                ag = self.agents[king]
                assert ag is not None
                if king == 0 and isinstance(ag, GrandmasterAI):
                    ranked = ag.analyze_contracts(
                        self.match.current_hands[0],
                        list(self.match.remaining_contracts),
                        list(self.match.scores),
                        0,
                    )
                    self.last_contract_analysis = ranked
                    chosen = ranked[0]["contract"]
                else:
                    chosen = ag.choose_contract(
                        self.match.current_hands[king],
                        list(self.match.remaining_contracts),
                        list(self.match.scores),
                        king,
                    )
                self.match.select_contract(chosen)
                self._push_log(
                    f"👑 {self.seat_label(king)} اختار طلب: {CONTRACT_AR[chosen]}."
                )
                steps_taken += 1
                if single_step_spectate and steps_taken >= 1:
                    return
                continue

            if self.match.phase == "double":
                rnd = self.match.current_round
                assert rnd is not None
                # Let AIs decide their doubles immediately
                # Check if human holds any doublable card
                if self._is_human_seat(0) and rnd.doubler_candidates(0):
                    # Wait for human double choice; AI doubles happen after human confirms
                    return
                self._handle_ai_doubles()
                self.match.finish_doubling_phase()
                continue

            if self.match.phase == "play":
                rnd = self.match.current_round
                assert rnd is not None
                if rnd.done:
                    rec = self.match.finalize_round()
                    self.last_round_summary = {
                        "contract": rec.contract,
                        "contract_ar": CONTRACT_AR[rec.contract],
                        "king_seat": rec.king_seat,
                        "round_scores": rec.round_scores,
                        "cumulative_scores": rec.cumulative_scores,
                        "kingdom_index": rec.kingdom_index,
                        "round_in_kingdom": rec.round_in_kingdom,
                    }
                    self.awaiting_round_ack = True
                    self._push_log(
                        f"🏁 انتهت جولة {CONTRACT_AR[rec.contract]} | النقاط: {rec.round_scores}"
                    )
                    return

                p = rnd.current_player
                if self._is_human_seat(p):
                    return

                ag = self.agents[p]
                assert ag is not None
                obs = rnd.observation(p)
                if p == 0 and isinstance(ag, GrandmasterAI):
                    analysis = ag.analyze_action(obs)
                    act = analysis.best_action
                    self.last_analysis = self._serialize_analysis(analysis)
                else:
                    act = ag.choose_action(obs)
                self._apply_play_step(p, act)
                steps_taken += 1

                if rnd.done:
                    rec = self.match.finalize_round()
                    self.last_round_summary = {
                        "contract": rec.contract,
                        "contract_ar": CONTRACT_AR[rec.contract],
                        "king_seat": rec.king_seat,
                        "round_scores": rec.round_scores,
                        "cumulative_scores": rec.cumulative_scores,
                        "kingdom_index": rec.kingdom_index,
                        "round_in_kingdom": rec.round_in_kingdom,
                    }
                    self.awaiting_round_ack = True
                    self._push_log(
                        f"🏁 انتهت جولة {CONTRACT_AR[rec.contract]} | النقاط: {rec.round_scores}"
                    )
                    return

                if single_step_spectate and steps_taken >= 1:
                    return

    def _apply_play_step(self, p: int, act: int) -> None:
        rnd = self.match.current_round
        assert rnd is not None
        prev_trick = list(rnd.current_trick)
        info = rnd.step(act)
        if info["type"] == "trix_pass":
            self._push_log(f"⏭️ {self.seat_label(p)} مرّر (Pass).")
        elif info["type"] == "trix_play":
            msg = f"🃏 {self.seat_label(p)} نزل {card_ar(act)}."
            if "finished_place" in info:
                msg += f" 🏆 أنهى بالمركز #{info['finished_place']}!"
            self._push_log(msg)
        elif info["type"] == "trick_complete":
            full_trick = prev_trick + [(p, act)]
            w = info["winner"]
            self.last_trick_flash = {
                "plays": [{"seat": s, "card": _card_obj(c)} for s, c in full_trick],
                "winner": w,
                "winner_label": self.seat_label(w),
                "delta": info["delta"],
            }
            pen_txt = f" ({info['delta'][w]:+d})" if info["delta"][w] != 0 else ""
            self._push_log(
                f"🎯 {self.seat_label(w)} أخذ اللطشة{pen_txt}."
            )

    def human_select_contract(self, contract: str) -> None:
        with self.lock:
            if self.match.phase != "choose_contract" or not self._is_human_seat(
                self.match.current_king
            ):
                raise ValueError("Not human contract selection phase")
            self.last_contract_analysis = None
            self.match.select_contract(contract)
            self._push_log(f"👑 اخترت طلب: {CONTRACT_AR[contract]}.")
            self._auto_advance_until_human_or_pause()

    def human_submit_doubles(self, cards: list[int]) -> None:
        with self.lock:
            if self.match.phase != "double":
                raise ValueError("Not doubling phase")
            rnd = self.match.current_round
            assert rnd is not None
            for c in cards:
                rnd.apply_double(0, int(c))
                self._push_log(f"🔥 دبّلت {card_ar(int(c))}!")
            self._handle_ai_doubles()
            self.match.finish_doubling_phase()
            self.last_double_analysis = None
            self._auto_advance_until_human_or_pause()

    def human_play_action(self, action: int) -> None:
        with self.lock:
            if self.awaiting_round_ack or self.match.phase != "play":
                raise ValueError("Not in play phase")
            rnd = self.match.current_round
            assert rnd is not None
            if rnd.current_player != 0 or not self._is_human_seat(0):
                raise ValueError("Not your turn")
            self.last_analysis = None
            self._apply_play_step(0, int(action))
            if rnd.done:
                rec = self.match.finalize_round()
                self.last_round_summary = {
                    "contract": rec.contract,
                    "contract_ar": CONTRACT_AR[rec.contract],
                    "king_seat": rec.king_seat,
                    "round_scores": rec.round_scores,
                    "cumulative_scores": rec.cumulative_scores,
                    "kingdom_index": rec.kingdom_index,
                    "round_in_kingdom": rec.round_in_kingdom,
                }
                self.awaiting_round_ack = True
                self._push_log(
                    f"🏁 انتهت جولة {CONTRACT_AR[rec.contract]} | النقاط: {rec.round_scores}"
                )
                return
            self._auto_advance_until_human_or_pause()

    def continue_next_round(self) -> None:
        with self.lock:
            self.awaiting_round_ack = False
            self.last_round_summary = None
            self.last_trick_flash = None
            self.last_analysis = None
            self.last_contract_analysis = None
            self.last_double_analysis = None
            self._auto_advance_until_human_or_pause(
                single_step_spectate=(self.mode == "spectate")
            )

    def spectate_step(self, full_round: bool = False) -> None:
        with self.lock:
            if self.mode != "spectate":
                return
            if self.awaiting_round_ack:
                self.awaiting_round_ack = False
                self.last_round_summary = None
                self.last_trick_flash = None
                self.last_analysis = None
            self._auto_advance_until_human_or_pause(
                single_step_spectate=(not full_round)
            )

    def run_coach_analysis(self) -> dict:
        with self.lock:
            if self.match.phase == "choose_contract":
                ranked = self.coach.analyze_contracts(
                    self.match.current_hands[0],
                    list(self.match.remaining_contracts),
                    list(self.match.scores),
                    0,
                )
                self.last_contract_analysis = ranked
                return {"type": "contract", "contracts": ranked}

            if self.match.phase == "double" and self.match.current_round is not None:
                rnd = self.match.current_round
                cands = rnd.doubler_candidates(0)
                dbl = self.coach.analyze_doubles(
                    rnd.contract,
                    rnd.hands[0],
                    cands,
                    list(self.match.scores),
                    0,
                    king_seat=rnd.king_seat,
                )
                self.last_double_analysis = dbl
                return {"type": "double", "doubles": dbl}

            if self.match.phase == "play" and self.match.current_round is not None:
                rnd = self.match.current_round
                obs = rnd.observation(0)
                if rnd.current_player == 0:
                    analysis = self.coach.analyze_action(obs)
                    ser = self._serialize_analysis(analysis)
                    self.last_analysis = ser
                    return {"type": "action", "analysis": ser}
                else:
                    b = BeliefState(obs)
                    return {
                        "type": "belief_only",
                        "belief": self._serialize_belief(b.summary_dict()),
                    }
            return {"type": "idle"}

    @staticmethod
    def _serialize_belief(bsum: dict) -> dict:
        voids_ar = {}
        for p, suits in bsum["void_suits"].items():
            voids_ar[str(p)] = [
                {"suit": s, "symbol": SUIT_SYMBOLS[s], "ar": SUIT_AR[s]} for s in suits
            ]
        proven = {}
        for p, cards in bsum["proven_cards"].items():
            proven[str(p)] = [_card_obj(c) for c in cards]
        key_probs = []
        for c, seat_map in bsum["key_card_probs"].items():
            key_probs.append(
                {
                    "card": _card_obj(c),
                    "probs": {str(s): round(v * 100.0, 1) for s, v in seat_map.items()},
                }
            )
        return {
            "total_worlds": bsum["total_consistent_worlds"],
            "void_suits": voids_ar,
            "proven_cards": proven,
            "key_card_probs": key_probs,
        }

    def _serialize_analysis(self, analysis) -> dict:
        evals = []
        for ev in analysis.evaluations[:8]:
            evals.append(
                {
                    "action": ev.action,
                    "card": None if ev.action == PASS_ACTION else _card_obj(ev.action),
                    "ev_own": ev.ev_own,
                    "ev_utility": ev.ev_utility,
                    "cvar20": ev.cvar20,
                    "min_score": ev.min_score,
                    "max_score": ev.max_score,
                    "safe_pct": round(ev.zero_penalty_prob * 100.0, 1),
                    "worlds": ev.worlds_tested,
                }
            )
        return {
            "best_action": analysis.best_action,
            "best_card": (
                None
                if analysis.best_action == PASS_ACTION
                else _card_obj(analysis.best_action)
            ),
            "mode": analysis.mode,
            "mode_ar": {
                "forced": "حركة إجبارية / متكافئة",
                "exact_endgame": "حل نهاية دقيق 100% (Exact MaxN)",
                "pimc_tactical": "محاكاة مونت كارلو الاحتمالية (PIMC)",
            }.get(analysis.mode, analysis.mode),
            "evaluations": evals,
            "belief": self._serialize_belief(analysis.belief_summary),
            "explanation_ar": analysis.explanation_ar,
        }

    def to_state_dict(self) -> dict[str, Any]:
        with self.lock:
            m = self.match
            rnd = m.current_round
            seat_labels = [self.seat_label(s) for s in range(4)]

            # Always show Seat 0 cards
            if rnd is not None:
                my_hand = [_card_obj(c) for c in _sort_hand_cards(rnd.hands[0])]
                hand_counts = [rnd.hands[s].bit_count() for s in range(4)]
                legal_actions = (
                    rnd.legal_actions(0)
                    if (m.phase == "play" and not self.awaiting_round_ack and rnd.current_player == 0)
                    else []
                )
                belief_live = self._serialize_belief(
                    BeliefState(rnd.observation(0)).summary_dict()
                )
                doubled_list = [
                    {
                        "card": _card_obj(c),
                        "doubler": d,
                        "doubler_label": seat_labels[d],
                    }
                    for c, d in rnd.doubled_cards.items()
                ]
                round_dict = {
                    "contract": rnd.contract,
                    "contract_ar": CONTRACT_AR[rnd.contract],
                    "king_seat": rnd.king_seat,
                    "current_player": rnd.current_player,
                    "trick_number": rnd.trick_number,
                    "round_scores": list(rnd.scores),
                    "doubled_cards": doubled_list,
                    "double_candidates": (
                        [_card_obj(c) for c in rnd.doubler_candidates(0)]
                        if m.phase == "double"
                        else []
                    ),
                    "current_trick": [
                        {"seat": s, "card": _card_obj(c)} for s, c in rnd.current_trick
                    ],
                    "layout_low": list(rnd.layout_low),
                    "layout_high": list(rnd.layout_high),
                    "trix_finish_order": list(rnd.trix_finish_order),
                    "done": rnd.done,
                }
            else:
                my_hand = (
                    [_card_obj(c) for c in _sort_hand_cards(m.current_hands[0])]
                    if m.current_hands
                    else []
                )
                hand_counts = [13, 13, 13, 13] if m.current_hands else [0, 0, 0, 0]
                legal_actions = []
                belief_live = None
                round_dict = None

            return {
                "session_id": self.id,
                "mode": self.mode,
                "opponent_level": self.opponent_level,
                "gm_level": self.gm_level,
                "phase": "round_summary" if self.awaiting_round_ack else m.phase,
                "kingdom_index": m.kingdom_index,
                "current_king": m.current_king if m.kingdom_index < 4 else -1,
                "remaining_contracts": [
                    {"id": c, "ar": CONTRACT_AR[c]} for c in m.remaining_contracts
                ],
                "match_scores": list(m.scores),
                "seat_labels": seat_labels,
                "my_hand": my_hand,
                "hand_counts": hand_counts,
                "legal_actions": legal_actions,
                "round": round_dict,
                "last_trick_flash": self.last_trick_flash,
                "last_round_summary": self.last_round_summary,
                "last_analysis": self.last_analysis,
                "last_contract_analysis": self.last_contract_analysis,
                "last_double_analysis": self.last_double_analysis,
                "belief_live": belief_live,
                "event_feed": self.event_feed[-12:],
                "history": [
                    {
                        "kingdom": h.kingdom_index + 1,
                        "round_in_kingdom": h.round_in_kingdom,
                        "king": seat_labels[h.king_seat],
                        "contract_ar": CONTRACT_AR[h.contract],
                        "round_scores": h.round_scores,
                        "cumulative_scores": h.cumulative_scores,
                    }
                    for h in m.history
                ],
                "rankings": (
                    [
                        {
                            "place": i + 1,
                            "seat": s,
                            "label": seat_labels[s],
                            "score": m.scores[s],
                        }
                        for i, s in enumerate(m.rankings())
                    ]
                    if m.phase == "match_over"
                    else None
                ),
            }


def run_torture_test(contract: str = CONTRACT_KH, seed: Optional[int] = None) -> dict:
    """Deal a genuinely TERRIBLE nightmare hand to Seat 0 and compare
    GrandmasterAI vs IntermediateAI vs ProHeuristicAI on the EXACT SAME DEAL!
    """
    rng = random.Random(seed if seed is not None else random.randrange(1, 10**6))
    # Generate 200 random deals and pick the single WORST hand for Seat 0 in `contract`!
    worst_hands = None
    worst_surplus = 1e9
    for _ in range(200):
        hands = deal_hands(rng)
        surp = analytical_contract_surplus(hands[0], contract)
        if surp < worst_surplus:
            worst_surplus = surp
            worst_hands = hands
    assert worst_hands is not None

    # Test 3 agents in Seat 0 against identical Pro opponents on the EXACT same deal!
    king_seat = 1  # Opponent leads, making survival even harder!
    comparison = []
    for label, agent_factory in [
        ("لاعب عادي (Intermediate)", lambda: IntermediateAI(seed=777)),
        ("خبير قواعد (ProHeuristic)", lambda: ProHeuristicAI(seed=777)),
        ("العقل الخارق (GrandmasterAI)", lambda: GrandmasterAI(level="monster", seed=777)),
    ]:
        t0 = time.perf_counter()
        rnd = TrixRound(contract, king_seat, list(worst_hands))
        agents: list[BaseAgent] = [
            agent_factory(),
            ProHeuristicAI(seed=101),
            ProHeuristicAI(seed=202),
            ProHeuristicAI(seed=303),
        ]
        # Let opponents double if appropriate
        if contract in (CONTRACT_KH, CONTRACT_QUEENS):
            for s in range(4):
                cands = rnd.doubler_candidates(s)
                if cands:
                    if isinstance(agents[s], GrandmasterAI):
                        dbls = agents[s].choose_doubles(
                            contract, rnd.hands[s], cands, [0, 0, 0, 0], s, king_seat=king_seat
                        )
                    else:
                        dbls = agents[s].choose_doubles(
                            contract, rnd.hands[s], cands, [0, 0, 0, 0], s
                        )
                    for c in dbls:
                        rnd.apply_double(s, c)
        while not rnd.done:
            p = rnd.current_player
            rnd.step(agents[p].choose_action(rnd.observation(p)))
        dt = (time.perf_counter() - t0) * 1000.0
        comparison.append(
            {
                "agent": label,
                "seat0_score": rnd.scores[0],
                "all_scores": list(rnd.scores),
                "tricks_taken": rnd.tricks_won[0],
                "elapsed_ms": round(dt, 1),
            }
        )

    return {
        "contract": contract,
        "contract_ar": CONTRACT_AR[contract],
        "hand_difficulty_score": round(worst_surplus, 1),
        "nightmare_hand": [_card_obj(c) for c in _sort_hand_cards(worst_hands[0])],
        "comparison": comparison,
    }


SESSIONS: dict[str, GameSession] = {}
SESSIONS_LOCK = threading.Lock()


def _get_session(sid: str) -> Optional[GameSession]:
    with SESSIONS_LOCK:
        return SESSIONS.get(sid)


class TrixHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Quiet clean server logging
        pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/api/health":
            self._send_json({"ok": True, "engine": "GrandmasterTrixAI V2"})
            return
        if path.startswith("/api/state/"):
            sid = path.split("/api/state/", 1)[1]
            sess = _get_session(sid)
            if sess is None:
                self._send_json({"error": "Session not found"}, status=404)
                return
            self._send_json(sess.to_state_dict())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            body = self._read_json_body()
            if path == "/api/new_game":
                mode = body.get("mode", "play")
                opp = body.get("opponent_level", "grandmaster")
                gm_lvl = body.get("gm_level", "monster")
                sess = GameSession(mode=mode, opponent_level=opp, gm_level=gm_lvl)
                with SESSIONS_LOCK:
                    # Keep memory bounded
                    if len(SESSIONS) > 60:
                        oldest = next(iter(SESSIONS))
                        SESSIONS.pop(oldest, None)
                    SESSIONS[sess.id] = sess
                self._send_json(sess.to_state_dict())
                return

            if path == "/api/torture_test":
                contract = body.get("contract", CONTRACT_KH)
                if contract not in CONTRACTS:
                    contract = CONTRACT_KH
                res = run_torture_test(contract=contract)
                self._send_json(res)
                return

            if path == "/api/quick_benchmark":
                from .benchmark import run_benchmark

                opp_kind = body.get("opponent", "intermediate")
                n_matches = max(2, min(8, int(body.get("matches", 4))))
                if opp_kind == "pro":
                    factory = lambda s: ProHeuristicAI(seed=s)
                    label = "ProHeuristicAI"
                else:
                    factory = lambda s: IntermediateAI(seed=s)
                    label = "IntermediateAI"
                summary = run_benchmark(
                    factory,
                    label,
                    n_matches=n_matches,
                    gm_level="fast",
                    base_seed=random.randrange(1000, 90000),
                )
                self._send_json(summary)
                return

            sid = body.get("session_id", "")
            sess = _get_session(sid)
            if sess is None:
                self._send_json({"error": "Session not found"}, status=404)
                return

            if path == "/api/select_contract":
                sess.human_select_contract(body["contract"])
                self._send_json(sess.to_state_dict())
                return

            if path == "/api/submit_doubles":
                sess.human_submit_doubles(body.get("cards", []))
                self._send_json(sess.to_state_dict())
                return

            if path == "/api/play":
                sess.human_play_action(int(body["action"]))
                self._send_json(sess.to_state_dict())
                return

            if path == "/api/next_round":
                sess.continue_next_round()
                self._send_json(sess.to_state_dict())
                return

            if path == "/api/spectate_step":
                sess.spectate_step(full_round=bool(body.get("full_round", False)))
                self._send_json(sess.to_state_dict())
                return

            if path == "/api/analyze":
                res = sess.run_coach_analysis()
                state = sess.to_state_dict()
                state["coach_result"] = res
                self._send_json(state)
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), TrixHTTPHandler)
    print(f"Grandmaster Trix Arena listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    run_server(host="0.0.0.0", port=port)

"""Ultra-fast integer & bitmask card representation for Trix.

Encoding:
    suit: 0=Clubs (♣), 1=Diamonds (♦), 2=Hearts (♥), 3=Spades (♠)
    rank: 0..12 corresponding to 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A
    card: suit * 13 + rank (0..51)
"""

from __future__ import annotations

SUIT_CLUBS = 0
SUIT_DIAMONDS = 1
SUIT_HEARTS = 2
SUIT_SPADES = 3

SUITS = (SUIT_CLUBS, SUIT_DIAMONDS, SUIT_HEARTS, SUIT_SPADES)
SUIT_SYMBOLS = ("♣", "♦", "♥", "♠")
SUIT_CODES = ("C", "D", "H", "S")
SUIT_AR = ("سباتي", "ديناري", "كبة", "بستوني")

RANK_2 = 0
RANK_3 = 1
RANK_4 = 2
RANK_5 = 3
RANK_6 = 4
RANK_7 = 5
RANK_8 = 6
RANK_9 = 7
RANK_10 = 8
RANK_J = 9
RANK_Q = 10
RANK_K = 11
RANK_A = 12

RANK_STRS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
RANK_AR = (
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "ولد",
    "بنت",
    "شيخ",
    "آص",
)

# Precomputed lookup tables for speed
CARD_SUIT: tuple[int, ...] = tuple(c // 13 for c in range(52))
CARD_RANK: tuple[int, ...] = tuple(c % 13 for c in range(52))
CARD_BIT: tuple[int, ...] = tuple(1 << c for c in range(52))
SUIT_SHIFT: tuple[int, ...] = (0, 13, 26, 39)
SUIT_MASKS: tuple[int, ...] = tuple(((1 << 13) - 1) << (s * 13) for s in range(4))
ALL_CARDS_MASK: int = (1 << 52) - 1

SEVEN_OF_HEARTS = SUIT_HEARTS * 13 + RANK_7
KING_OF_HEARTS = SUIT_HEARTS * 13 + RANK_K
KING_OF_HEARTS_BIT = 1 << KING_OF_HEARTS

QUEENS: tuple[int, ...] = tuple(s * 13 + RANK_Q for s in range(4))
QUEENS_SET: frozenset[int] = frozenset(QUEENS)
QUEENS_MASK: int = sum(1 << q for q in QUEENS)

JACKS: tuple[int, ...] = tuple(s * 13 + RANK_J for s in range(4))
JACKS_MASK: int = sum(1 << j for j in JACKS)

DIAMONDS_MASK: int = SUIT_MASKS[SUIT_DIAMONDS]
HEARTS_MASK: int = SUIT_MASKS[SUIT_HEARTS]

# Precomputed bit-to-index lookup for single-bit masks
_BIT_TO_CARD: dict[int, int] = {1 << c: c for c in range(52)}


def card_id(suit: int, rank: int) -> int:
    return suit * 13 + rank


def card_suit(card: int) -> int:
    return CARD_SUIT[card]


def card_rank(card: int) -> int:
    return CARD_RANK[card]


def card_str(card: int) -> str:
    return f"{RANK_STRS[CARD_RANK[card]]}{SUIT_SYMBOLS[CARD_SUIT[card]]}"


def card_code(card: int) -> str:
    return f"{RANK_STRS[CARD_RANK[card]]}{SUIT_CODES[CARD_SUIT[card]]}"


def card_ar(card: int) -> str:
    r = CARD_RANK[card]
    s = CARD_SUIT[card]
    if card == KING_OF_HEARTS:
        return "شيخ الكبة (K♥)"
    return f"{RANK_AR[r]} {SUIT_AR[s]} ({RANK_STRS[r]}{SUIT_SYMBOLS[s]})"


def parse_card(text: str) -> int:
    """Parse strings like 'KH', 'K♥', '10D', '2♣' into card id 0..51."""
    t = text.strip().upper()
    suit_map = {
        "C": SUIT_CLUBS,
        "♣": SUIT_CLUBS,
        "D": SUIT_DIAMONDS,
        "♦": SUIT_DIAMONDS,
        "H": SUIT_HEARTS,
        "♥": SUIT_HEARTS,
        "S": SUIT_SPADES,
        "♠": SUIT_SPADES,
    }
    suit_char = t[-1]
    if suit_char not in suit_map:
        raise ValueError(f"Unknown suit in card '{text}'")
    rank_part = t[:-1]
    if rank_part not in RANK_STRS:
        raise ValueError(f"Unknown rank in card '{text}'")
    return suit_map[suit_char] * 13 + RANK_STRS.index(rank_part)


def mask_to_cards(mask: int) -> list[int]:
    """Convert a 52-bit integer mask into sorted list of card ids."""
    res: list[int] = []
    m = mask
    while m:
        lsb = m & -m
        res.append(_BIT_TO_CARD[lsb])
        m ^= lsb
    return res


def cards_to_mask(cards) -> int:
    m = 0
    for c in cards:
        m |= 1 << c
    return m


def suit_mask_in_hand(hand_mask: int, suit: int) -> int:
    return hand_mask & SUIT_MASKS[suit]


def suit_count(hand_mask: int, suit: int) -> int:
    return (hand_mask & SUIT_MASKS[suit]).bit_count()


def highest_card_in_mask(mask: int) -> int:
    """Return card id of highest bit in non-zero mask."""
    return mask.bit_length() - 1


def lowest_card_in_mask(mask: int) -> int:
    """Return card id of lowest bit in non-zero mask."""
    return _BIT_TO_CARD[mask & -mask]


def format_hand(hand_mask: int) -> str:
    parts = []
    for s in (SUIT_SPADES, SUIT_HEARTS, SUIT_DIAMONDS, SUIT_CLUBS):
        sm = (hand_mask >> SUIT_SHIFT[s]) & 0x1FFF
        ranks = [RANK_STRS[r] for r in range(12, -1, -1) if (sm >> r) & 1]
        parts.append(f"{SUIT_SYMBOLS[s]}:{' '.join(ranks) if ranks else '-'}")
    return " | ".join(parts)

"""Deterministic DETECTION_AUDIT sample selection (BEFORE any detector output).

Selection is a pure function of the sealed timeline identity and the requested
sample size: every position is ranked by sha256(timeline_hash / position) and
the first N distinct positions are taken, then sorted chronologically. The
sample is computed immediately after the timeline seal and before any engine
runs; nothing about detector output can influence it. ``sample_size`` is an
explicit owner-tunable parameter — it is NOT a sacred number.
"""

from __future__ import annotations

import hashlib


def select_sample_positions(timeline_hash: str, bar_count: int, sample_size: int) -> tuple:
    """Return sorted tuple of distinct sample positions (deterministic)."""
    if bar_count <= 0:
        return ()
    if sample_size <= 0:
        raise ValueError("sample_size must be positive (explicit owner parameter)")
    wanted = min(sample_size, bar_count)
    picked: list = []
    seen = set()
    k = 0
    # Distinct-by-hash walk: deterministic, order-independent of any engine.
    while len(picked) < wanted:
        digest = hashlib.sha256(f"{timeline_hash}/{k}".encode()).hexdigest()
        position = int(digest, 16) % bar_count
        if position not in seen:
            seen.add(position)
            picked.append(position)
        k += 1
        if k > bar_count * 40 + 1000:
            break
    return tuple(sorted(picked))


def sample_manifest(timeline_hash: str, bar_count: int, sample_size: int) -> dict:
    positions = select_sample_positions(timeline_hash, bar_count, sample_size)
    return {
        "algorithm": "SHA256_TIMELINE_HASH_SLASH_K_MOD_BAR_COUNT_DISTINCT_ASCENDING",
        "timeline_hash": timeline_hash,
        "bar_count": bar_count,
        "sample_size_parameter": sample_size,
        "sample_size_realized": len(positions),
        "positions": list(positions),
        "parameter_status": "EXPLICIT_OWNER_PARAMETER_NOT_SACRED",
    }

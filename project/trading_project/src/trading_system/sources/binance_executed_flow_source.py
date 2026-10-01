"""Binance Spot EXECUTED_INITIATED_FLOW factual source surface.

Builds the factual frame consumed by the CLOSED public contract of Module 3.1
(``OrderFlowMode.ACTUAL_AGGRESSOR``): exactly ``buy_volume``, ``sell_volume``,
``volume`` — sourced from ``buy_initiated_base_volume``,
``sell_initiated_base_volume``, ``base_volume`` of the validated minute-facts
artifact. Volume unit: BASE ASSET. The per-minute identity
``buy + sell == total`` is verified exactly before any float conversion.

Semantic label: ``EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT`` — executed /
initiated flow of this source ONLY (taker-side accounting). No pressure,
participant-level, or book-state claim is made or implied. Module 3.1/3.2 are
consumed unmodified through their public APIs; this module never modifies them
and never labels anything ACTUAL by itself (``order_flow_mode`` is produced only
by 3.1).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from trading_system.sources import (
    EXECUTED_FLOW_SEMANTIC_LABEL,
    EXECUTED_FLOW_VOLUME_UNIT,
    SchemaViolationError,
    SourceArtifactIdentity,
    exact_equal,
    parse_plain_decimal,
)
from trading_system.sources.binance_spot_minute_facts_source import MinuteFactsSource

_FLOW_COLUMNS = ("buy_volume", "sell_volume", "volume")


@dataclass(frozen=True)
class ExecutedFlowSource:
    identity: SourceArtifactIdentity
    semantic_label: str
    volume_unit: str
    frame: pd.DataFrame  # buy_volume / sell_volume / volume, float64, CLOSE_TIME index
    exact_frame: pd.DataFrame  # original literal strings, same index
    source_minute_facts_sha256: str
    statement: str = (
        "EXECUTED/INITIATED FLOW of this Binance Spot source only (taker-side "
        "accounting per upstream feed semantics). Semantic scope is limited to "
        "executed/initiated accounting; no pressure, participant-level, or "
        "book-state claim is made or implied. PROXY outputs of 3.1/3.2 stay "
        "PROXY and are never impersonated as this surface."
    )


def build_executed_flow_source(minute_facts: MinuteFactsSource) -> ExecutedFlowSource:
    """Derive the 3.1 ACTUAL_AGGRESSOR input surface from validated minute facts."""
    if not isinstance(minute_facts, MinuteFactsSource):
        raise SchemaViolationError("MINUTE_FACTS_SOURCE_REQUIRED")

    exact = minute_facts.exact_frame
    buy_rows = exact["buy_initiated_base_volume"].tolist()
    sell_rows = exact["sell_initiated_base_volume"].tolist()
    total_rows = exact["base_volume"].tolist()
    for pos, (buy_lit, sell_lit, total_lit) in enumerate(zip(buy_rows, sell_rows, total_rows)):
        buy = parse_plain_decimal(buy_lit, max_decimals=8, signed=False, label=f"buy_volume:{pos}")
        sell = parse_plain_decimal(sell_lit, max_decimals=8, signed=False, label=f"sell_volume:{pos}")
        total = parse_plain_decimal(total_lit, max_decimals=8, signed=False, label=f"volume:{pos}")
        if buy < 0 or sell < 0:
            raise SchemaViolationError(f"FLOW_VOLUME_NEGATIVE:{pos}")
        if not exact_equal(str(buy + sell), str(total)):
            raise SchemaViolationError(f"BUY_PLUS_SELL_NE_TOTAL:{pos}")

    index = exact.index
    frame = pd.DataFrame(
        {
            "buy_volume": pd.Series(
                [float(parse_plain_decimal(v, max_decimals=8, signed=False, label="buy")) for v in buy_rows],
                index=index,
                dtype="float64",
            ),
            "sell_volume": pd.Series(
                [float(parse_plain_decimal(v, max_decimals=8, signed=False, label="sell")) for v in sell_rows],
                index=index,
                dtype="float64",
            ),
            "volume": pd.Series(
                [float(parse_plain_decimal(v, max_decimals=8, signed=False, label="total")) for v in total_rows],
                index=index,
                dtype="float64",
            ),
        },
        index=index,
    )
    if list(frame.columns) != list(_FLOW_COLUMNS):
        raise SchemaViolationError("EXECUTED_FLOW_FRAME_COLUMNS_INVALID")

    exact_frame = pd.DataFrame(
        {
            "buy_volume": pd.Series(buy_rows, index=index),
            "sell_volume": pd.Series(sell_rows, index=index),
            "volume": pd.Series(total_rows, index=index),
        },
        index=index,
    )

    return ExecutedFlowSource(
        identity=minute_facts.identity,
        semantic_label=EXECUTED_FLOW_SEMANTIC_LABEL,
        volume_unit=EXECUTED_FLOW_VOLUME_UNIT,
        frame=frame,
        exact_frame=exact_frame,
        source_minute_facts_sha256=minute_facts.provenance.minute_facts_sha256,
    )

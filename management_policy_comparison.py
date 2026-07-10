# -*- coding: utf-8 -*-
"""Re-run fixed trade cases under alternative exit policies only.

Entry, initial SL, TP levels and OHLC stay frozen. Only TP1 allocation and the
post-TP1 stop policy change, preventing hindsight changes to setup selection.
"""
from __future__ import annotations
import json
from pathlib import Path

from ict_math_engine import simulate_managed_trade_outcome

POLICIES = (
    ("80_BE", 0.80, "BE_THEN_STRUCTURE"),
    ("50_BE", 0.50, "BE_THEN_STRUCTURE"),
    ("50_STRUCTURE", 0.50, "STRUCTURE_ONLY"),
    ("20_STRUCTURE_BIG_RUNNER", 0.20, "STRUCTURE_ONLY"),
)


def compare_bundle(bundle, count=5, output=None):
    base = Path(bundle)
    case_root = base / "trade_cases" if (base / "trade_cases").is_dir() else base
    if not case_root.is_dir():
        raise FileNotFoundError(f"trade_cases not found under {base}")
    cases = []
    for directory in sorted(x for x in case_root.iterdir() if x.is_dir() and x.name.startswith("CASE-")):
        analysis_path = directory / "01_analysis_at_signal.json"
        outcome_path = directory / "04_outcome_and_management.json"
        candles_path = directory / "03_ohlc_after_signal_execution_tf.json"
        if not (analysis_path.is_file() and outcome_path.is_file() and candles_path.is_file()):
            continue
        old = json.load(open(outcome_path, encoding="utf-8"))
        if old.get("trade") is None:  # No-fill signal, not an executed trade.
            continue
        cases.append((directory, json.load(open(analysis_path, encoding="utf-8")),
                      json.load(open(candles_path, encoding="utf-8"))))
        if len(cases) >= int(count):
            break

    rows = []
    for directory, analysis, candles in cases:
        candidate = analysis["candidate"]
        tp1 = candidate["targets"][0]["price"]
        second = candidate["targets"][1] if len(candidate["targets"]) > 1 else None
        tp2 = {"mode": "TARGET", "price": second["price"]} if second else {"mode": "OPEN_TRAILING"}
        risk = abs(candidate["entry"] - candidate["stop_loss"])
        risk_pct = risk / candidate["entry"] * 100 if candidate["entry"] else 0
        row = {
            "case_id": directory.name, "symbol": analysis["symbol"],
            "audit_id": analysis.get("audit_id"), "entry": candidate["entry"],
            "sl": candidate["stop_loss"], "tp1": tp1, "variants": {},
        }
        for name, fraction, policy in POLICIES:
            outcome = simulate_managed_trade_outcome(
                candles, candidate["entry"], candidate["stop_loss"], tp1, tp2,
                is_short="SELL" in candidate["side"], tp1_fraction=fraction,
                post_tp1_stop_policy=policy,
            )
            realized_r = outcome.get("pnl_pct_blended", 0) / risk_pct if risk_pct else 0
            row["variants"][name] = {"realized_r": round(realized_r, 4), "outcome": outcome}
        rows.append(row)

    summary = {}
    for name, _, _ in POLICIES:
        values = [row["variants"][name]["realized_r"] for row in rows]
        summary[name] = {
            "trades": len(values), "total_r": round(sum(values), 4),
            "wins": sum(x > 0 for x in values), "losses": sum(x < 0 for x in values),
            "breakeven": sum(x == 0 for x in values),
            "average_r": round(sum(values) / len(values), 4) if values else None,
        }
    result = {
        "source_bundle": str(base), "case_count": len(rows), "policies": [x[0] for x in POLICIES],
        "summary": summary, "rows": rows,
        "integrity_rule": "Same frozen entry/SL/TP/OHLC; only partial allocation and post-TP1 stop policy differ.",
        "warning": "Five trades are diagnostic, not statistically sufficient to select a live policy.",
    }
    output_path = Path(output) if output else base / "management_policy_comparison.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    result["saved_to"] = str(output_path)
    return result

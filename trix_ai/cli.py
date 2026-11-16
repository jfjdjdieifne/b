"""Command-line interface for Grandmaster Individual Trix AI.

Examples:
    python3 -m trix_ai.cli benchmark --opponent intermediate --matches 10 --level tournament
    python3 -m trix_ai.cli benchmark --opponent pro --matches 10 --level tournament
    python3 -m trix_ai.cli torture --contract king_of_hearts --trials 10
    python3 -m trix_ai.cli serve --port 8000
"""

from __future__ import annotations

import argparse
import statistics

from .benchmark import print_report, run_benchmark
from .engine import CONTRACT_AR, CONTRACTS
from .heuristics import IntermediateAI, ProHeuristicAI, RandomAI
from .web_app import run_server, run_torture_test


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="trix_ai",
        description="Grandmaster Individual Trix AI Engine (العقل الخارق للتريكس الفردي)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bench = sub.add_parser("benchmark", help="Run full 4-Kingdom match tournament")
    p_bench.add_argument(
        "--opponent",
        choices=("random", "intermediate", "pro"),
        default="pro",
    )
    p_bench.add_argument("--matches", type=int, default=12)
    p_bench.add_argument(
        "--level", choices=("fast", "tournament", "monster"), default="tournament"
    )
    p_bench.add_argument("--seed", type=int, default=4200)

    p_tort = sub.add_parser("torture", help="Stress-test nightmare hands")
    p_tort.add_argument("--contract", choices=CONTRACTS, default="king_of_hearts")
    p_tort.add_argument("--trials", type=int, default=5)

    p_srv = sub.add_parser("serve", help="Launch Interactive Web Arena")
    p_srv.add_argument("--host", default="0.0.0.0")
    p_srv.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.cmd == "benchmark":
        factories = {
            "random": (lambda s: RandomAI(seed=s), "RandomAI"),
            "intermediate": (lambda s: IntermediateAI(seed=s), "IntermediateAI"),
            "pro": (lambda s: ProHeuristicAI(seed=s), "ProHeuristicAI"),
        }
        factory, label = factories[args.opponent]
        res = run_benchmark(
            factory,
            label,
            n_matches=args.matches,
            gm_level=args.level,
            base_seed=args.seed,
        )
        print_report(res)
    elif args.cmd == "torture":
        scores_by_agent: dict[str, list[int]] = {}
        print(
            f"=== Nightmare Hand Torture Test: {CONTRACT_AR[args.contract]} ({args.trials} deals) ==="
        )
        for t in range(args.trials):
            r = run_torture_test(contract=args.contract, seed=7000 + t * 19)
            line = [f"Deal #{t + 1} (diff={r['hand_difficulty_score']}):"]
            for row in r["comparison"]:
                scores_by_agent.setdefault(row["agent"], []).append(row["seat0_score"])
                line.append(f"{row['agent']}={row['seat0_score']:+d}")
            print(" | ".join(line))
        print("-" * 70)
        for ag, vals in scores_by_agent.items():
            print(f"  Avg across {args.trials} nightmare hands | {ag}: {statistics.mean(vals):+.1f}")
    elif args.cmd == "serve":
        run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

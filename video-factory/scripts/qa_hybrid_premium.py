#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from video_factory.hybrid_premium import EditPlan, analyze_video, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Hybrid Premium automated MP4 quality gates")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--json", type=Path, default=Path("outputs/qa.json"))
    parser.add_argument("--report", type=Path, default=Path("outputs/QA.md"))
    args = parser.parse_args()
    plan = EditPlan.load(args.plan)
    metrics = analyze_video(
        args.video,
        expected_duration=plan.duration,
        expected_width=plan.width,
        expected_height=plan.height,
        expected_fps=plan.fps,
    )
    write_report(metrics, args.json, args.report)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if metrics["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

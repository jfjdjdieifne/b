#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from video_factory.hybrid_premium import EditPlan, render


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Hybrid Premium edit plan")
    parser.add_argument("--plan", type=Path, required=True, help="Path to edit_plan.json")
    parser.add_argument("--output", type=Path, required=True, help="Output MP4")
    parser.add_argument("--preview", action="store_true", help="Fast 540x960 QC render")
    args = parser.parse_args()
    plan = EditPlan.load(args.plan)
    output = render(plan, args.output, preview=args.preview)
    manifest = output.with_suffix(".manifest.json")
    print(json.dumps({
        "status": "done",
        "output": str(output),
        "manifest": str(manifest),
        "bytes": output.stat().st_size,
        "visual_beats": len(plan.shots),
        "draft_only": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

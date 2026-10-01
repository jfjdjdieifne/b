#!/usr/bin/env python3
"""Run one minimal Free.ai CogVideoX T2V/I2V smoke test.

The API key is read only from FREE_AI_API_KEY. It is never accepted as a command
argument, printed, or written to diagnostics.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow `python scripts/free_ai_smoke_test.py` from a fresh checkout without
# installing the package first.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from video_factory.providers.free_ai import FreeAIError, FreeAIProvider


def ffprobe(path: Path) -> dict:
    executable = shutil.which("ffprobe")
    if not executable:
        return {"available": False}
    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,format_name:stream=codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        return {"available": True, "error": completed.stderr.strip()[-500:]}
    try:
        return {"available": True, "result": json.loads(completed.stdout)}
    except json.JSONDecodeError:
        return {"available": True, "error": "ffprobe returned invalid JSON"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        default=(
            "Cinematic close-up of a small paper boat gliding through a rain puddle, "
            "realistic water ripples, soft overcast light, gentle tracking camera"
        ),
    )
    parser.add_argument("--duration", type=int, default=2)
    parser.add_argument("--aspect-ratio", default="9:16")
    parser.add_argument("--image-url", default=None)
    parser.add_argument(
        "--model",
        default=os.getenv("FREE_AI_VIDEO_MODEL", "").strip() or None,
        help="Leave empty to use the self-hosted default (recommended for the free pool).",
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/free_ai_smoke/scene.mp4"))
    parser.add_argument(
        "--diagnostics",
        type=Path,
        default=Path("outputs/free_ai_smoke/diagnostics.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    diagnostics = {
        "provider": "free_ai",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "request": {
            "duration": args.duration,
            "aspect_ratio": args.aspect_ratio,
            "mode": "image-to-video" if args.image_url else "text-to-video",
            "model": args.model or "self-hosted-default",
        },
    }
    try:
        provider = FreeAIProvider()
        result = provider.generate_video(
            args.prompt,
            args.output,
            duration=args.duration,
            aspect_ratio=args.aspect_ratio,
            image_url=args.image_url,
            model=args.model,
        )
        diagnostics.update(
            {
                "status": "done",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": result.elapsed_seconds,
                "http_status": result.status_code,
                "job_id": result.job_id,
                "token_cost": result.token_cost,
                "remaining_tokens": result.remaining_tokens,
                "output": str(result.output_path),
                "output_bytes": result.output_path.stat().st_size,
                "ffprobe": ffprobe(result.output_path),
            }
        )
        print(f"DONE: {result.output_path}")
        print(f"Elapsed: {result.elapsed_seconds:.1f}s")
        if result.token_cost is not None:
            print(f"Token cost reported by API: {result.token_cost}")
        if result.remaining_tokens is not None:
            print(f"Remaining tokens reported by API: {result.remaining_tokens}")
        return_code = 0
    except (FreeAIError, RuntimeError, ValueError) as exc:
        diagnostics.update(
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        if isinstance(exc, FreeAIError):
            diagnostics.update(
                {
                    "http_status": exc.status_code,
                    "error_code": exc.code,
                    "retriable": exc.retriable,
                }
            )
        print(f"FAILED: {exc}", file=sys.stderr)
        return_code = 1

    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    print(f"Diagnostics: {args.diagnostics}")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Live Wan 2.2 T2V/I2V test through Hugging Face ZeroGPU.

Examples:
  python scripts/hf_spaces_smoke_test.py --output artifacts/hf-t2v.mp4
  HF_TOKEN=hf_... python scripts/hf_spaces_smoke_test.py \
      --image input.png --duration 2 --steps 4 --output artifacts/hf-i2v.mp4

The script never prints the token. HF_TOKEN is optional for anonymous use, but a free
account receives a larger daily quota and medium queue priority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from video_factory.providers.hf_spaces import HFSpacesError, HFSpacesWanProvider


def inspect_video(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    result: dict[str, object] = {
        "file": str(path.resolve()),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        result.update(
            {
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
                "fps": fps,
                "frames": frames,
                "duration_decoded": (frames / fps if fps else None),
                "opened": bool(cap.isOpened()),
            }
        )
        cap.release()
    except ImportError:
        result["inspection_note"] = "Install opencv-python for frame metadata"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path)
    parser.add_argument("--prompt", default="A red leaf sways naturally in wind and rain, realistic cinematic motion")
    parser.add_argument("--negative-prompt", default="static, blurry, deformed, morphing, watermark, text, logo")
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=832)
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--guidance", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1987)
    parser.add_argument("--space", default="Upsampler/wan-2-2-5b-video")
    parser.add_argument("--output", type=Path, default=Path("artifacts/hf-wan-smoke.mp4"))
    parser.add_argument("--health-only", action="store_true")
    args = parser.parse_args()

    provider = HFSpacesWanProvider(space_id=args.space)
    if args.health_only:
        print(json.dumps(provider.health(), ensure_ascii=False, indent=2))
        return 0
    try:
        generation = provider.generate_video(
            args.prompt,
            args.output,
            input_image=args.image,
            width=args.width,
            height=args.height,
            duration_seconds=args.duration,
            steps=args.steps,
            guidance_scale=args.guidance,
            negative_prompt=args.negative_prompt,
            seed=args.seed,
        )
    except HFSpacesError as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc), "retriable": exc.retriable, "quota": exc.quota},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    report = {"ok": True, **generation.metadata, **inspect_video(generation.output_path)}
    report.update(
        {
            "mode": generation.mode,
            "elapsed_seconds": generation.elapsed_seconds,
            "requested_seconds": generation.duration_requested,
            "steps": generation.steps,
            "seed": generation.seed,
        }
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Call a deployed Beam endpoint without putting credentials in source code."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default=os.getenv("BEAM_ENDPOINT_URL"),
        help="Deployed endpoint URL (or set BEAM_ENDPOINT_URL)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("BEAM_TOKEN"),
        help="Beam API key (prefer BEAM_TOKEN)",
    )
    parser.add_argument("--prompt", default="")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--duration", type=float, default=1.1)
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=832)
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--payload",
        type=Path,
        help="Optional JSON payload; other generation flags are ignored",
    )
    args = parser.parse_args()

    if not args.url:
        parser.error("provide --url or BEAM_ENDPOINT_URL")
    if not args.token:
        parser.error("set BEAM_TOKEN (do not commit it)")

    if args.payload:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
    else:
        payload = {
            "prompt": args.prompt,
            "duration_seconds": args.duration,
            "width": args.width,
            "height": args.height,
            "steps": args.steps,
            "seed": args.seed,
            "guidance_scale": 0.0,
        }
        if args.image:
            payload["input_image_base64"] = base64.b64encode(
                args.image.read_bytes()
            ).decode("ascii")

    request = urllib.request.Request(
        args.url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {args.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=1_200) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())

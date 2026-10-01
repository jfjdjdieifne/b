from __future__ import annotations

import argparse
from pathlib import Path
from video_factory.config import ROOT
from video_factory.jobs import SceneJob

parser = argparse.ArgumentParser()
parser.add_argument("prompt")
parser.add_argument("--image-url")
parser.add_argument("--negative-prompt", default="")
parser.add_argument("--seed", type=int, default=1987)
args = parser.parse_args()

job = SceneJob(
    prompt=args.prompt,
    image_url=args.image_url,
    negative_prompt=args.negative_prompt or SceneJob.__dataclass_fields__["negative_prompt"].default,
    seed=args.seed,
)
path = ROOT / "jobs" / f"{job.id}.json"
job.save(path)
print(path)

"""Arena Motion Engine — cinematic, GPU-free motion from AI keyframes.

The Arena Agent can generate images and speech, not video. This engine converts a
sparse set of AI keyframes (one image per story beat) into a *master shot* with
continuous, real per-frame motion, using optical flow motion interpolation.

How it works
------------
1. Each key is rendered to 1080x1920 with a requested zoom / offset (stage).
2. Stages are held for a chosen duration, so the intermediate clip runs at a low
   frame rate (e.g. 2.2 fps) where one frame == one creative decision.
3. ``minterpolate`` (motion-compensated interpolation) synthesises every frame
   between those decisions -> smooth motion over the whole shot.
4. Camera drift, unsharp, film grain and a light filmic base are applied.

The result is a *motion master*: a real 30 fps clip, never a Ken Burns still.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

WIDTH, HEIGHT = 1080, 1920
FPS = 30


def find_ffmpeg() -> str:
    if os.getenv("FFMPEG_BINARY"):
        return os.environ["FFMPEG_BINARY"]
    which = shutil.which("ffmpeg")
    if which:
        return which
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


@dataclass(frozen=True)
class Stage:
    """One creative decision: which key, how long until the next one, how framed."""

    key: Path
    dur: float = 0.45
    zoom: float = 1.0
    dx: float = 0.0
    dy: float = 0.0


def _render_stage(stage: Stage, out: Path, size=(WIDTH, HEIGHT)) -> None:
    import cv2
    import numpy as np

    img = cv2.imread(str(stage.key), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"keyframe unreadable: {stage.key}")
    h, w = img.shape[:2]
    zoom = max(1.0, float(stage.zoom))
    scale = max(size[0] / w, size[1] / h) * zoom
    nw, nh = max(size[0], int(math.ceil(w * scale))), max(size[1], int(math.ceil(h * scale)))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    x = (nw - size[0]) / 2 + stage.dx
    y = (nh - size[1]) / 2 + stage.dy
    x = float(np.clip(x, 0, nw - size[0]))
    y = float(np.clip(y, 0, nh - size[1]))
    crop = resized[int(round(y)):int(round(y)) + size[1], int(round(x)):int(round(x)) + size[0]]
    cv2.imwrite(str(out), crop, [cv2.IMWRITE_PNG_COMPRESSION, 1])


def build_shot(
    stages: list[Stage],
    out: str | Path,
    *,
    fps: int = FPS,
    overscan: float = 1.05,
    drift: float = 7.0,
    drift_period: float = 7.5,
    grain: float = 1.4,
    unsharp: float = 0.55,
    sharp_second: float = 0.0,
    filmic: str = "eq=contrast=1.04:saturation=0.96:gamma=0.99",
    motion_blur: float = 0.0,
    crf: int = 16,
    preset: str = "medium",
    threads: int = 2,
    keep_stages: bool = False,
    atmosphere: bool = True,
    realtime: float = 0.0,
    air: dict | None = None,
) -> Path:
    """Render a motion master from a stage list. Returns the output path."""
    if len(stages) < 2:
        raise ValueError("at least two stages are required for real motion")
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()

    work = Path(tempfile.mkdtemp(prefix="arena_shot_", dir=str(out.parent)))
    try:
        size = (int(WIDTH * max(1.0, overscan)), int(HEIGHT * max(1.0, overscan)))
        chain: list[str] = []
        if False:
            chain.append(f"scale={int(WIDTH * overscan)}:{int(HEIGHT * overscan)}:flags=lanczos")
        else:
            chain.append(f"scale={WIDTH}:{HEIGHT}:flags=lanczos")
        if drift:
            px, py = float(drift), float(drift) * 0.62
            p2 = float(drift_period) * 0.71
            chain.append(
                "crop="
                f"w={WIDTH}:h={HEIGHT}:"
                f"x='(iw-ow)/2+{px:.3f}*sin(2*PI*t/{float(drift_period):.3f})':"
                f"y='(ih-oh)/2+{py:.3f}*sin(2*PI*t/{p2:.3f})'"
            )
        else:
            chain.append(f"crop={WIDTH}:{HEIGHT}")
        if motion_blur:
            chain.append(f"tmix=frames=2:weights='1 {max(0.0, float(motion_blur)):.3f}'")
        if filmic:
            chain.append(filmic)
        if unsharp:
            chain.append(f"unsharp=5:5:{float(unsharp):.3f}:5:5:{float(sharp_second):.3f}")
        if grain:
            chain.append(f"noise=alls={max(0.6, float(grain) * 0.7):.3f}:allf=t+u")
        chain.append("format=yuv420p")

        from . import flow_interp

        air_cfg = dict(air or {})
        air_obj = flow_interp.Atmosphere(
            size,
            haze=float(air_cfg.get("haze", 0.10)),
            motes=float(air_cfg.get("motes", 0.05)),
            breath=float(air_cfg.get("breath", 0.016)),
        ) if atmosphere else None
        flow_interp.encode_stages(
            stages, out, fps=fps, chain=chain, crf=crf, preset=preset, threads=threads,
            ffmpeg=ffmpeg, size=size, atmosphere=air_obj, realtime=realtime,
        )
    finally:
        if not keep_stages:
            shutil.rmtree(work, ignore_errors=True)
    return out


MOVES = {
    # name -> (zoom0, zoom1, dx0, dx1, dy0, dy1) as a function of "amount"
    "in":       lambda a: (1.0, 1.0 + a, 0.0, 0.0, 0.0, 0.0),
    "out":      lambda a: (1.0 + a, 1.0, 0.0, 0.0, 0.0, 0.0),
    "in_fast":  lambda a: (1.0, 1.0 + a * 1.6, 0.0, 0.0, 0.0, 0.0),
    "tilt_up":  lambda a: (1.04, 1.04 + a * 0.5, 0.0, 0.0, a * 260.0, -a * 200.0),
    "tilt_down": lambda a: (1.04, 1.04 + a * 0.5, 0.0, 0.0, -a * 260.0, a * 200.0),
    "lateral":  lambda a: (1.05, 1.05 + a * 0.4, -a * 150.0, a * 150.0, 0.0, 0.0),
    "track":    lambda a: (1.06, 1.06 + a * 0.35, -a * 120.0, a * 120.0, a * 60.0, -a * 40.0),
    "creep":    lambda a: (1.0, 1.0 + a * 0.55, 0.0, 0.0, 0.0, -a * 70.0),
}


def _smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def beat_stages(
    key_a,
    key_b=None,
    *,
    dur: float,
    move: str = "in",
    amount: float = 0.14,
    swap_at: float = 0.34,
    ease: bool = True,
    phases: int = 7,
) -> list[Stage]:
    """Stages for one story beat, driven by a named camera move.

    The move runs continuously across the whole beat, and the stage durations
    sum to ``dur`` exactly so the picture stays locked to the narration. When a
    second key exists, the frame changes over the middle of the beat: the scene
    evolves while the camera keeps moving.
    """
    if move not in MOVES:
        raise KeyError(f"unknown move {move!r}; choose from {sorted(MOVES)}")
    z0, z1, x0, x1, y0, y1 = MOVES[move](float(amount))
    a = Path(key_a)
    b = Path(key_b) if key_b else None
    if b is not None and not b.is_file():
        b = None

    n = max(3, int(phases))
    step = float(dur) / n
    stages: list[Stage] = []
    for i in range(n):
        t = i / (n - 1)
        e = _smooth(t) if ease else t
        zoom = z0 + (z1 - z0) * e
        dx = x0 + (x1 - x0) * e
        dy = y0 + (y1 - y0) * e
        key = a if (b is None or e < swap_at) else b
        stages.append(Stage(key, step, zoom, dx, dy))
    return stages


def outro_stages(key, *, dur: float, amount: float = 0.10) -> list[Stage]:
    """Slow final move that lets the film breathe instead of freezing."""
    return beat_stages(key, None, dur=dur, move="in", amount=amount, phases=5)


def probe(path: str | Path) -> dict:
    """Motion statistics for a rendered master (freeze / energy report)."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or float(FPS)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (180, 320)))
    cap.release()
    if len(frames) < 2:
        return {"file": str(path), "frames": len(frames), "error": "unreadable"}
    arr = np.stack(frames)
    diff = np.array([np.mean(cv2.absdiff(arr[i], arr[i - 1])) for i in range(1, len(arr))])
    return {
        "file": str(path),
        "frames": int(len(arr)),
        "fps": fps,
        "duration": round(len(arr) / fps, 3),
        "mean_diff": round(float(diff.mean()), 3),
        "min_diff": round(float(diff.min()), 3),
        "p05_diff": round(float(np.percentile(diff, 5)), 3),
        "max_diff": round(float(diff.max()), 3),
        "freeze_frames": int((diff < 0.5).sum()),
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Arena Motion Engine")
    ap.add_argument("--key", required=True, help="keyframe image")
    ap.add_argument("--out", required=True)
    ap.add_argument("--key-b", default=None)
    ap.add_argument("--dur", type=float, default=2.4)
    args = ap.parse_args()
    stages = beat_stages(args.key, args.key_b, dur=args.dur)
    path = build_shot(stages, args.out)
    print(json.dumps(probe(path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

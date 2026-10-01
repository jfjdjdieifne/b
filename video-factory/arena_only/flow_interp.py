"""Optical-flow frame synthesis — real motion from sparse AI keyframes.

Two cases, each handled with the best available method:

* **Same key, different framing** (a push / tilt / dolly decision): exact analytic
  resampling of the source image. No warping artefacts at all — this is what a
  real camera move looks like.
* **Two different keys** (the scene evolves between two AI frames): motion
  compensated interpolation with dense optical flow and forward/backward
  consistency masking, so occluded pixels prefer the frame that really saw them.

Output frames are piped straight into ffmpeg (no intermediate PNG dump).
"""
from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT = 1080, 1920
FPS = 30


@dataclass
class Key:
    """A loaded keyframe, rendered at any framing on demand (with a zoom cache)."""

    path: Path
    image: np.ndarray
    _cache: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._cache is None:
            self._cache = {}

    @classmethod
    def load(cls, path: str | Path) -> "Key":
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"keyframe unreadable: {path}")
        return cls(Path(path), img)

    def _prepared(self, zoom: float, size: tuple[int, int]) -> np.ndarray:
        h, w = self.image.shape[:2]
        scale = max(size[0] / w, size[1] / h) * zoom
        nw, nh = max(size[0], int(math.ceil(w * scale))), max(size[1], int(math.ceil(h * scale)))
        cached = self._cache.get((nw, nh))
        if cached is None:
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
            cached = cv2.resize(self.image, (nw, nh), interpolation=interp)
            if len(self._cache) > 96:
                self._cache.clear()
            self._cache[(nw, nh)] = cached
        return cached

    def frame(self, zoom: float = 1.0, dx: float = 0.0, dy: float = 0.0,
              size: tuple[int, int] = (WIDTH, HEIGHT)) -> np.ndarray:
        zoom = max(1.0, round(float(zoom), 4))
        resized = self._prepared(zoom, size)
        nw, nh = resized.shape[1], resized.shape[0]
        x = float(np.clip((nw - size[0]) / 2 + dx, 0, nw - size[0]))
        y = float(np.clip((nh - size[1]) / 2 + dy, 0, nh - size[1]))
        x0, y0 = int(math.floor(x)), int(math.floor(y))
        return resized[y0:y0 + size[1], x0:x0 + size[0]]


class FlowPair:
    """Bidirectional dense flow between two rendered frames."""

    def __init__(self, a: np.ndarray, b: np.ndarray, *, flow_scale: float = 0.5,
                 preset: str = "medium") -> None:
        self.a, self.b = a, b
        self.scale = flow_scale
        h, w = a.shape[:2]
        sh, sw = max(64, int(h * flow_scale)), max(64, int(w * flow_scale))
        ga = cv2.cvtColor(cv2.resize(a, (sw, sh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(cv2.resize(b, (sw, sh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        algorithms = {"medium": cv2.DISOPTICAL_FLOW_PRESET_MEDIUM, "fast": cv2.DISOPTICAL_FLOW_PRESET_FAST}
        self._dis = cv2.DISOpticalFlow_create(algorithms.get(preset, cv2.DISOPTICAL_FLOW_PRESET_MEDIUM))
        try:
            self._dis.setUseSpatialPropagation(True)
        except Exception:  # pragma: no cover - opencv build dependent
            pass
        fwd = self._dis.calc(ga, gb, None)
        bwd = self._dis.calc(gb, ga, None)
        self.fwd = cv2.resize(fwd, (w, h), interpolation=cv2.INTER_LINEAR) * (1.0 / flow_scale)
        self.bwd = cv2.resize(bwd, (w, h), interpolation=cv2.INTER_LINEAR) * (1.0 / flow_scale)
        gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        self._gx, self._gy = gx, gy

    def consistency(self) -> np.ndarray:
        """0 = reliable correspondence, 1 = occluded / inconsistent (soft)."""
        h, w = self.a.shape[:2]
        gx, gy = self._gx, self._gy
        back_at_a = cv2.remap(
            self.bwd, gx + self.fwd[..., 0], gy + self.fwd[..., 1],
            cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
        )
        err = np.linalg.norm(self.fwd + back_at_a, axis=2)
        return cv2.GaussianBlur(np.clip(err / 3.0, 0.0, 1.0), (0, 0), 2.0)

    def frame(self, u: float, occlusion: np.ndarray | None = None) -> np.ndarray:
        """Frame at relative time u in [0, 1] between a and b."""
        gx, gy = self._gx, self._gy
        wa = cv2.remap(
            self.a, gx + u * self.fwd[..., 0], gy + u * self.fwd[..., 1],
            cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
        )
        wb = cv2.remap(
            self.b, gx + (1.0 - u) * self.bwd[..., 0], gy + (1.0 - u) * self.bwd[..., 1],
            cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
        )
        if occlusion is None:
            occlusion = self.consistency()
        # Where the forward warp is unreliable (A stops seeing the pixel) lean on B.
        wa_w = np.clip(1.0 - u - occlusion * 0.5, 0.02, 1.0)[..., None]
        wb_w = np.clip(u + occlusion * 0.5, 0.02, 1.0)[..., None]
        mix = (wa.astype(np.float32) * wa_w + wb.astype(np.float32) * wb_w) / (wa_w + wb_w)
        return mix.astype(np.uint8)


class Atmosphere:
    """Living film atmosphere: drifting dust/haze plus a slow light breath.

    A locked-off dark frame reads as a still image even when the camera moves.
    Real air is never static: this adds advected haze layers, floating dust motes
    and a subtle exposure breathing so every single frame carries real change.
    """

    def __init__(self, size: tuple[int, int], seed: int = 7, haze: float = 0.075,
                 motes: float = 0.030, breath: float = 0.010) -> None:
        rng = np.random.default_rng(seed)
        self.size = size
        self.haze, self.motes, self.breath = haze, motes, breath
        small = (max(64, size[1] // 8), max(64, size[0] // 8))
        base = rng.random(small).astype(np.float32)
        self.layer_a = cv2.GaussianBlur(base, (0, 0), 6.0)
        self.layer_b = cv2.GaussianBlur(rng.random(small).astype(np.float32), (0, 0), 18.0)
        self.mote_field = rng.random((small[0] * 2, small[1] * 2)).astype(np.float32)
        for layer in (self.layer_a, self.layer_b, self.mote_field):
            layer -= float(layer.mean())
            layer /= max(1e-5, float(layer.std()))

    def _warp(self, layer: np.ndarray, dx: float, dy: float) -> np.ndarray:
        h, w = layer.shape[:2]
        matrix = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(layer, matrix, (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_WRAP)

    def apply(self, frame: np.ndarray, t: float) -> np.ndarray:
        h, w = frame.shape[:2]
        haze = cv2.resize(
            self._warp(self.layer_a, -t * 6.0, t * 2.2) * 0.6
            + self._warp(self.layer_b, t * 3.4, -t * 1.4) * 0.4,
            (w, h), interpolation=cv2.INTER_LINEAR,
        )
        motes = cv2.resize(
            np.clip(self._warp(self.mote_field, t * 11.0, -t * 6.0) - 1.15, 0.0, None),
            (w, h), interpolation=cv2.INTER_LINEAR,
        )
        out = frame.astype(np.float32)
        out += haze[..., None] * (self.haze * 255.0)
        out += motes[..., None] * (self.motes * 255.0)
        breath = 1.0 + self.breath * math.sin(2 * math.pi * t / 9.0) + 0.004 * math.sin(2 * math.pi * t / 2.7)
        out *= breath
        return np.clip(out, 0, 255).astype(np.uint8)


def shot_frames(stages, *, fps: int = FPS, ease: bool = True, size: tuple[int, int] = (WIDTH, HEIGHT),
                atmosphere: "Atmosphere | None" = None, realtime: float = 0.0):
    """Yield BGR frames for a shot defined by a stage list.

    Stages with the same key are resampled analytically (perfect optical move);
    stages with different keys are bridged with optical-flow interpolation.
    ``realtime`` is the shot's position on the film timeline, used so the air and
    the light breath stay continuous from shot to shot.
    """
    loaded: dict[Path, Key] = {}
    keys = []
    for stage in stages:
        path = Path(stage.key)
        if path not in loaded:
            loaded[path] = Key.load(path)
        keys.append(loaded[path])

    def framed(index: int) -> np.ndarray:
        stage = stages[index]
        return keys[index].frame(stage.zoom, stage.dx, stage.dy, size=size)

    clock = {"n": 0}

    def stamp(frame: np.ndarray) -> np.ndarray:
        if atmosphere is None:
            return frame
        t = realtime + clock["n"] / float(fps)
        clock["n"] += 1
        return atmosphere.apply(frame, t)

    yield stamp(framed(0))
    for i in range(len(stages) - 1):
        a_stage, b_stage = stages[i], stages[i + 1]
        span = max(1e-3, float(a_stage.dur))
        count = max(1, int(round(span * fps)))
        if a_stage.key == b_stage.key:
            for step in range(1, count + 1):
                t = step / count
                e = t * t * (3 - 2 * t) if ease else t
                zoom = a_stage.zoom + (b_stage.zoom - a_stage.zoom) * e
                dx = a_stage.dx + (b_stage.dx - a_stage.dx) * e
                dy = a_stage.dy + (b_stage.dy - a_stage.dy) * e
                yield stamp(keys[i].frame(zoom, dx, dy, size=size))
        else:
            pair = FlowPair(framed(i), framed(i + 1))
            occlusion = pair.consistency()
            for step in range(1, count + 1):
                t = step / count
                e = t * t * (3 - 2 * t) if ease else t
                yield stamp(pair.frame(min(0.999, max(0.001, e)), occlusion))

    # The final stage holds for its own duration with a gentle continuation, so a
    # shot never ends on a frozen frame.
    if len(stages) > 1:
        last = stages[-1]
        hold = max(0, int(round(float(last.dur) * fps)) - 1)
        if hold > 0:
            for step in range(1, hold + 1):
                t = step / max(1, hold)
                e = t * t * (3 - 2 * t) if ease else t
                yield stamp(keys[-1].frame(last.zoom * (1.0 + 0.006 * e), last.dx, last.dy, size=size))


def encode_stages(stages, out_path: str | Path, *, fps: int = FPS, chain: list[str] | None = None,
                  crf: int = 16, preset: str = "medium", threads: int = 2,
                  ffmpeg: str | None = None, size: tuple[int, int] = (WIDTH, HEIGHT),
                  atmosphere: "Atmosphere | None" = None, realtime: float = 0.0) -> Path:
    """Render a shot's stages into an MP4 via a piped raw stream."""
    from .motion_engine import find_ffmpeg

    ffmpeg = ffmpeg or find_ffmpeg()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    filters = list(chain or [])
    filters.append("format=yuv420p")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-",
        "-vf", ",".join(filters),
        "-r", str(fps),
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-threads", str(threads), "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "4.1", "-movflags", "+faststart", "-an",
        str(out_path),
    ]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert process.stdin is not None
    count = 0
    try:
        for frame in shot_frames(stages, fps=fps, size=size, atmosphere=atmosphere, realtime=realtime):
            process.stdin.write(frame.tobytes())
            count += 1
        process.stdin.close()
    finally:
        code = process.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg failed with code {code}")
    return out_path

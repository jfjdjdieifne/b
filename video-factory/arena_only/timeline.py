"""Narration timeline, word-locked beat timing, captions and music bed.

Everything here is derived from the actual generated voice-over, so the picture
is locked to the spoken words instead of to a guessed grid.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

from .motion_engine import find_ffmpeg


def _read_audio(path: str | Path):
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    return np.asarray(data, dtype="float32"), int(sr)


def audible_span(path: str | Path, threshold_ratio: float = 0.035) -> tuple[float, float]:
    """First/last audible sample of a clip (trims TTS padding)."""
    import numpy as np

    x, sr = _read_audio(path)
    if x.size == 0:
        return 0.0, 0.0
    win = max(1, int(0.02 * sr))
    env = np.convolve(np.abs(x), np.ones(win) / win, mode="same")
    thr = max(float(env.max()) * threshold_ratio, 1e-5)
    loud = np.where(env > thr)[0]
    if loud.size == 0:
        return 0.0, len(x) / sr
    return float(loud[0] / sr), float((loud[-1] + 1) / sr)


def internal_pause(path: str | Path, min_pause: float = 0.18, threshold_ratio: float = 0.045):
    """Longest silence *inside* the sentence — the safe place to cut a shot."""
    import numpy as np

    x, sr = _read_audio(path)
    if x.size == 0:
        return None
    win = max(1, int(0.02 * sr))
    env = np.convolve(np.abs(x), np.ones(win) / win, mode="same")
    thr = max(float(env.max()) * threshold_ratio, 1e-5)
    start, end = audible_span(path, threshold_ratio)
    i0, i1 = int(start * sr), int(end * sr)
    quiet = env[i0:i1] < thr
    best_len, best_mid, run = 0, None, 0
    for idx, flag in enumerate(quiet):
        if flag:
            run += 1
        else:
            if run > best_len:
                best_len, best_mid = run, i0 + idx - run / 2
            run = 0
    if run > best_len:
        best_len, best_mid = run, i0 + len(quiet) - run / 2
    if best_mid is None or best_len / sr < min_pause:
        return None
    mid = float(best_mid / sr)
    if mid < start + 0.6 or mid > end - 0.6:
        return None
    return mid


def build_narration(
    vo_files: Iterable[str | Path],
    out_wav: str | Path,
    *,
    lead: float = 0.15,
    gap: float = 0.22,
    tail: float = 0.60,
    sample_rate: int = 48000,
) -> dict:
    """Concatenate sentence clips into one narration track and return timings."""
    import numpy as np
    import soundfile as sf

    files = [Path(f) for f in vo_files]
    if not files:
        raise ValueError("no voice-over clips")
    pieces = []
    cursor = 0.0
    sentences = []
    for index, path in enumerate(files):
        x, sr = _read_audio(path)
        start_aud, end_aud = audible_span(path)
        clipped = x[int(start_aud * sr):int(end_aud * sr)]
        begin = cursor + (lead if index == 0 else 0.0)
        if index:
            pieces.append(np.zeros(int(round(gap * sr)), dtype=np.float32))
        if index == 0:
            pieces.append(np.zeros(int(round(lead * sr)), dtype=np.float32))
        pieces.append(clipped)
        dur = len(clipped) / sr
        sentences.append(
            {
                "index": index,
                "file": str(path),
                "start": round(begin, 3),
                "end": round(begin + dur, 3),
                "duration": round(dur, 3),
                "pause": internal_pause(path),
            }
        )
        cursor = begin + dur
    total = cursor + tail
    pieces.append(np.zeros(int(round(tail * sr)), dtype=np.float32))
    track = np.concatenate(pieces)
    peak = float(np.max(np.abs(track))) or 1.0
    if peak > 0.98:
        track = track * (0.98 / peak)
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), track, sample_rate, subtype="PCM_16")
    timings = {"total": round(total, 3), "sentences": sentences}
    out_wav.with_suffix(".timings.json").write_text(json.dumps(timings, indent=2))
    return timings


def build_music_bed(
    source: str | Path,
    out_path: str | Path,
    *,
    duration: float,
    gain_db: float = -21.0,
    fade_in: float = 1.2,
    fade_out: float = 2.4,
) -> Path:
    """Loop a licensed cue under the narration, ducked and faded."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fade_out = min(fade_out, max(0.4, duration / 3))
    cmd = [
        find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-i", str(source),
        "-t", f"{duration:.3f}",
        "-af",
        (
            f"volume={gain_db}dB,"
            f"afade=t=in:st=0:d={fade_in:.2f},"
            f"afade=t=out:st={max(0.0, duration - fade_out):.2f}:d={fade_out:.2f},"
            f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
        ),
        "-c:a", "aac", "-b:a", "192k", str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,66,&H00F5F2EC,&H000000FF,&H00140F0A,&H66000000,-1,0,0,0,100,100,1.2,0,1,4,2,2,70,70,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_captions(beats: list[dict], out_path: str | Path, *, min_duration: float = 0.6) -> Path:
    """One restrained caption per story beat, timed to the spoken words."""
    lines = [ASS_HEADER]
    for beat in beats:
        text = (beat.get("caption") or "").strip()
        if not text:
            continue
        start = float(beat["start"])
        end = max(start + min_duration, float(beat["end"]) - 0.06)
        safe = text.replace("{", "(").replace("}", ")").replace("\n", "\\N")
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{{\\fad(140,140)}}{safe}\n"
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(lines), encoding="utf-8")
    return out_path


def plan_beats(timings: dict, spec: list[dict], *, split_over: float = 3.55,
               min_pause: float = 0.20) -> list[dict]:
    """Turn sentences into story beats, splitting long sentences on a real pause."""
    by_index = {s["index"]: s for s in timings["sentences"]}
    ordered = sorted(by_index)
    beats: list[dict] = []
    for position, sentence_index in enumerate(ordered):
        sentence = by_index[sentence_index]
        item = next((s for s in spec if int(s["sentence"]) == sentence_index), None)
        if item is None:
            raise KeyError(f"no beat spec for sentence {sentence_index}")
        next_start = (
            by_index[ordered[position + 1]]["start"]
            if position + 1 < len(ordered)
            else timings["total"]
        )
        start, end = float(sentence["start"]), float(next_start)
        pause = sentence.get("pause")
        if end - start > split_over and pause and (pause - start) > 1.2 and (end - pause) > 1.2:
            cut = float(pause) + 0.06
            beats.append({**item, "start": round(start, 3), "end": round(cut, 3), "half": 1})
            second = {**item, "start": round(cut, 3), "end": round(end, 3), "half": 2,
                      "caption": item.get("caption_b") or item.get("caption")}
            if item.get("a2"):
                second["a"] = item["a2"]
                second["b"] = item.get("b2")
                second["move"] = item.get("move2", item.get("move", "in"))
                second["amount"] = item.get("amount2", item.get("amount", 0.14))
            beats.append(second)
        else:
            beats.append({**item, "start": round(start, 3), "end": round(end, 3), "half": 0})
    for i, beat in enumerate(beats):
        beat["beat"] = i + 1
        beat["duration"] = round(float(beat["end"]) - float(beat["start"]), 3)
    return beats

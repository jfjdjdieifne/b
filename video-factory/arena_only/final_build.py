"""Arena Studio — one command builds the finished Short.

    python -m arena_only.final_build --job jobs/pyramids_void --out outputs/pyramids_void.mp4

Pipeline (all local, no external service, no GPU):

    beats.json + AI keyframes + AI voice-over
        -> narration track + word-locked beat timing
        -> music bed + caption track
        -> one motion master per beat (optical-flow camera moves)
        -> final 1080x1920 30 fps MP4 with captions, loudness and film grain
        -> automated QA report + manifest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arena_only import timeline as T  # noqa: E402
from arena_only.motion_engine import (  # noqa: E402
    FPS,
    HEIGHT,
    WIDTH,
    beat_stages,
    build_shot,
    find_ffmpeg,
    probe,
)

try:  # reuse the repository's approved colour science
    from video_factory.hybrid_premium.renderer import GRADES as _REPO_GRADES
except Exception:  # pragma: no cover
    _REPO_GRADES = {"neutral": "eq=contrast=1.04:saturation=0.96:gamma=0.99"}

# Arena Studio additions: the repo grades are deliberately very dark, which makes
# low-key night shots read as frozen. These keep the film look but hold detail.
GRADES = {
    **_REPO_GRADES,
    "lab": "eq=contrast=1.08:saturation=0.62:brightness=-0.02:gamma=0.99,colorbalance=rs=-0.02:gs=0.0:bs=0.06,vignette=PI/5.6",
    "bright_cave": "eq=contrast=1.12:saturation=0.46:brightness=-0.025:gamma=0.98,colorbalance=rs=0.02:gs=0.01:bs=-0.01,vignette=PI/4.4",
    "soft_inscription": "eq=contrast=1.13:saturation=0.44:brightness=-0.035:gamma=0.97,colorbalance=rs=0.03:gs=0.015:bs=-0.04,vignette=PI/5.0",
    "desert_lift": "eq=contrast=1.12:saturation=0.82:brightness=-0.03:gamma=0.96,colorbalance=rs=.05:gs=.015:bs=-.045,vignette=PI/5.2",
}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _log(message: str) -> None:
    print(message, flush=True)


def _ffmpeg(*args: str) -> None:
    subprocess.run([find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def build(
    job_dir: str | Path,
    out_path: str | Path,
    *,
    preview: bool = False,
    keep_masters: bool = True,
    preset: str = "medium",
    crf: int = 16,
) -> dict:
    job = Path(job_dir).resolve()
    spec = json.loads((job / "beats.json").read_text(encoding="utf-8"))
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scale = 0.5 if preview else 1.0
    width, height = int(WIDTH * scale), int(HEIGHT * scale)

    work = job / "build"
    masters_dir = work / "masters"
    audio_dir = work / "audio"
    for folder in (masters_dir, audio_dir):
        folder.mkdir(parents=True, exist_ok=True)

    # 1) narration + word-locked beats -------------------------------------
    vo_files = sorted((job / spec["vo_dir"]).glob("s*.mp3"))
    if not vo_files:
        raise FileNotFoundError(f"no voice-over clips in {job / spec['vo_dir']}")
    pacing = spec.get("pacing", {})
    timings = T.build_narration(
        vo_files, audio_dir / "narration.wav",
        lead=pacing.get("lead", 0.15), gap=pacing.get("gap", 0.22), tail=pacing.get("tail", 0.60),
    )
    beats = T.plan_beats(
        timings, spec["beats"],
        split_over=spec.get("split_over", 3.55), min_pause=spec.get("min_pause", 0.20),
    )
    _log(f"[1/5] narration {timings['total']:.2f}s | {len(beats)} story beats")

    outro = spec.get("outro")
    outro_dur = float(outro.get("duration", 0.0)) if outro else 0.0
    total = round(float(timings["total"]) + outro_dur, 3)

    # 2) captions + music --------------------------------------------------
    captions_path = T.write_captions(beats, work / "captions.ass")
    if outro and outro.get("caption"):
        captions_path.write_text(
            captions_path.read_text(encoding="utf-8")
            + "Dialogue: 0,{},{},Caption,,0,0,0,,{{\\fad(200,400)}}{}\n".format(
                T._ass_time(float(timings["total"])), T._ass_time(total),
                outro["caption"].replace("{", "(").replace("}", ")"),
            ),
            encoding="utf-8",
        )
    music_bed = None
    if spec.get("music"):
        music_bed = T.build_music_bed(
            job / spec["music"], audio_dir / "music.m4a", duration=total,
            gain_db=float(spec.get("music_gain_db", -21.0)),
        )

    _log(f"[2/5] captions + music bed ready (total {total:.2f}s)")

    # 3) one motion master per beat ---------------------------------------
    manifest_beats = []
    master_paths: list[Path] = []
    transition = float(spec.get("transition", 0.0))
    for index, beat in enumerate(beats):
        move = beat.get("move", "in")
        amount = float(beat.get("amount", 0.14))
        dur = float(beat["duration"])
        stages = []
        inner = dur
        if index > 0 and transition > 0 and dur > transition + 0.7:
            prev_key = beats[index - 1].get("b") or beats[index - 1]["a"]
            # The previous scene flows into this one: a real motion-compensated
            # morph that lives inside this beat's own time, so the narration
            # never loses sync.
            stages += beat_stages(
                job / prev_key, job / beat["a"], dur=transition,
                move="creep", amount=0.05, swap_at=0.45, phases=3,
            )
            inner = dur - transition
        stages += beat_stages(
            job / beat["a"], (job / beat["b"]) if beat.get("b") else None, dur=inner,
            move=move, amount=amount, phases=int(beat.get("phases", 6)),
        )
        grade = GRADES.get(beat.get("grade", "neutral"), GRADES["neutral"])
        chain = [grade, "unsharp=5:5:0.55:5:5:0", "noise=alls=1.3:allf=t+u"]
        _log(f"[3/5] beat {beat['beat']:02d}  {dur:4.2f}s  {move:<9s} keys={Path(beat['a']).name}"
             f"{' + ' + Path(beat['b']).name if beat.get('b') else ''}")
        master = masters_dir / f"beat_{beat['beat']:02d}.mp4"
        build_shot(
            stages, master, fps=FPS, drift=float(beat.get("drift", 7.0)), grain=1.3,
            unsharp=0.55, filmic=grade, crf=crf, preset=preset, overscan=1.03,
            realtime=float(beat["start"]),
            air=beat.get("air", spec.get("air", {})),
        )
        master_paths.append(master)
        stats = probe(master)
        manifest_beats.append(
            {
                "beat": beat["beat"], "start": beat["start"], "end": beat["end"],
                "duration": beat["duration"], "move": move, "amount": amount,
                "grade": beat.get("grade", "neutral"), "keys": [Path(beat["a"]).name,
                (Path(beat["b"]).name if beat.get("b") else None)],
                "caption": beat.get("caption"),
                "transition_in": round(transition if index else 0.0, 3),
                "master": str(master.relative_to(job)),
                "motion": {k: stats.get(k) for k in ("frames", "duration", "mean_diff", "p05_diff", "freeze_frames")},
            }
        )

    if outro and outro.get("key") and outro_dur > 0:
        stages = beat_stages(job / outro["key"], None, dur=outro_dur, move=outro.get("move", "creep"),
                             amount=float(outro.get("amount", 0.10)), phases=5)
        master = masters_dir / "outro.mp4"
        build_shot(stages, master, fps=FPS, drift=6.0, grain=1.3, unsharp=0.55,
                   filmic=GRADES.get(outro.get("grade", "neutral"), GRADES["neutral"]),
                   crf=crf, preset=preset, overscan=1.03, realtime=float(timings["total"]),
                   air=outro.get("air", spec.get("air", {})))
        master_paths.append(master)
        manifest_beats.append({"beat": "outro", "start": timings["total"], "end": total,
                               "duration": outro_dur, "move": outro.get("move", "creep"),
                               "keys": [Path(outro["key"]).name], "master": str(master.relative_to(job)),
                               "caption": outro.get("caption")})

    # 4) concat the masters, then mux picture + audio + captions -----------
    list_file = work / "concat.txt"
    list_file.write_text("".join(f"file '{m.as_posix()}'\n" for m in master_paths), encoding="utf-8")
    _log("[4/5] joining masters and mixing the master audio")
    silent = work / "picture.mp4"
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", "-an", str(silent))

    final_tmp = work / "final.mp4"
    ass = captions_path.as_posix().replace("\\", "/").replace(":", r"\:")
    vf = f"ass='{ass}':fontsdir='/usr/share/fonts/truetype/dejavu',format=yuv420p"
    if preview:
        vf = f"scale={width}:{height}," + vf
    fade = min(float(spec.get("fade_out", 0.0)), 0.8)
    if fade > 0:
        vf += f",fade=t=out:st={max(0.0, total - fade):.3f}:d={fade:.3f}"
    inputs = ["-i", str(silent), "-i", str(audio_dir / "narration.wav")]
    if music_bed:
        inputs += ["-i", str(music_bed)]
    if music_bed:
        graph = (
            f"[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"aresample=48000[nar];"
            f"[2:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[bed];"
            f"[nar][bed]amix=inputs=2:duration=longest:normalize=0,"
            f"loudnorm=I=-14:TP=-1.5:LRA=8[aout]"
        )
    else:
        graph = "[1:a]loudnorm=I=-14:TP=-1.5:LRA=8[aout]"
    _ffmpeg(
        *inputs,
        "-filter_complex", f"[0:v]{vf}[vout];{graph}",
        "-map", "[vout]", "-map", "[aout]",
        "-t", f"{total:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "slow" if not preview else "veryfast",
        "-crf", str(crf if not preview else 23),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-metadata", f"title={spec.get('title', spec.get('id', 'short'))}",
        str(final_tmp),
    )
    shutil.copy2(final_tmp, out_path)

    _log(f"[5/5] final render done: {out_path.name} ({out_path.stat().st_size/1e6:.1f} MB)")

    # 5) QA + manifest -----------------------------------------------------
    qa = {}
    try:
        from video_factory.hybrid_premium.qa import analyze_video

        qa = analyze_video(str(out_path), expected_duration=total, expected_width=WIDTH,
                           expected_height=HEIGHT, expected_fps=float(FPS))
    except Exception as exc:  # pragma: no cover
        qa = {"error": str(exc)}
    motion = probe(out_path)
    manifest = {
        "schema_version": 1,
        "job": spec.get("id"),
        "title": spec.get("title"),
        "output": str(out_path),
        "output_sha256": _sha(out_path),
        "bytes": out_path.stat().st_size,
        "duration": total,
        "resolution": [WIDTH, HEIGHT],
        "fps": FPS,
        "narration_total": timings["total"],
        "beats": manifest_beats,
        "motion": motion,
        "qa": qa,
        "engine": "arena_only",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "draft_only": True,
    }
    (out_path.with_suffix(".manifest.json")).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not keep_masters:
        shutil.rmtree(masters_dir, ignore_errors=True)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Arena Studio final build")
    ap.add_argument("--job", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", action="store_true", help="half-size fast QC render")
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--crf", type=int, default=16)
    args = ap.parse_args()
    manifest = build(args.job, args.out, preview=args.preview, preset=args.preset, crf=args.crf)
    print(json.dumps({k: manifest[k] for k in ("output", "duration", "bytes", "motion")}, indent=2))
    print("QA:", json.dumps(manifest["qa"].get("checks", manifest["qa"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

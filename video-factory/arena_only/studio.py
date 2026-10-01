#!/usr/bin/env python3
"""Arena Studio — the fully automatic YouTube Shorts factory (Arena only).

One command per step, no external service, no GPU, no manual editing:

    python -m arena_only.studio new   --slug mysterious-mars --title "..." --topic "..."
    python -m arena_only.studio build --slug mysterious-mars
    python -m arena_only.studio qa    --slug mysterious-mars
    python -m arena_only.studio pack  --slug mysterious-mars

The daily loop is:

    1. ``new``    -> writes the script beats **and the exact keyframe prompts**
    2. the Arena agent fills the job with its own tools:
         * one voice-over clip per sentence  -> jobs/<slug>/vo/sNN.mp3
         * one image per prompt              -> jobs/<slug>/keys/<id>.png
    3. ``build``  -> narration timing -> optical-flow motion masters -> captions
                     -> colour -> loudness -> 1080x1920 30fps MP4 + manifest
    4. ``qa``     -> freeze / black / loudness / duration gates (exit code 1 on fail)
    5. ``pack``   -> delivery folder: MP4, thumbnail, YouTube metadata, manifest
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arena_only.motion_engine import find_ffmpeg  # noqa: E402

JOBS = ROOT / "jobs"
DELIVERY = ROOT / "outputs" / "delivery"

DEFAULT_BEATS = [
    ("A SEALED ROOM", "in", 0.20, "desert_lift"),
    ("THE SCAN", "creep", 0.30, "lab"),
    ("WHAT THEY FOUND", "lateral", 0.30, "neutral"),
    ("HIDDEN FOR CENTURIES", "in_fast", 0.30, "dig"),
    ("LOOK AGAIN", "tilt_up", 0.28, "bright_cave"),
    ("A DOOR BELOW", "out", 0.30, "bright_cave"),
    ("AND THE WRITING", "in_fast", 0.30, "bright_cave"),
    ("NOT A TOMB. A MESSAGE.", "track", 0.30, "soft_inscription"),
]


def job_dir(slug: str) -> Path:
    path = JOBS / slug
    if not path.is_dir():
        raise SystemExit(f"no such job: {path}")
    return path


def cmd_new(args: argparse.Namespace) -> int:
    job = JOBS / args.slug
    for sub in ("vo", "keys", "build"):
        (job / sub).mkdir(parents=True, exist_ok=True)
    script = args.script
    if script:
        sentences = [line.strip() for line in Path(script).read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        raise SystemExit("--script is required: one spoken sentence per line")
    beats = []
    for index, sentence in enumerate(sentences):
        look = DEFAULT_BEATS[index % len(DEFAULT_BEATS)]
        beats.append(
            {
                "sentence": index,
                "a": f"keys/s{index + 1:02d}_a.png",
                "b": f"keys/s{index + 1:02d}_b.png",
                "grade": look[3],
                "move": look[1],
                "amount": look[2],
                "caption": look[0],
            }
        )
    spec = {
        "id": args.slug,
        "title": args.title or args.slug,
        "vo_dir": "vo",
        "keys_dir": "keys",
        "music": args.music or "../../examples/hybrid_premium/ancient_mystery/music_sfx.m4a",
        "pacing": {"lead": 0.15, "gap": 0.22, "tail": 0.60},
        "split_over": 3.55,
        "min_pause": 0.20,
        "air": {"haze": 0.10, "motes": 0.05, "breath": 0.016},
        "fade_out": 0.8,
        "outro": {"key": "keys/s01_a.png", "duration": 3.4, "move": "out", "amount": 0.30,
                  "grade": "desert_lift", "caption": "THE STORY IS NOT OVER",
                  "air": {"haze": 0.12, "motes": 0.06, "breath": 0.02}},
        "beats": beats,
        "script": sentences,
        "topic": args.topic or args.title or args.slug,
    }
    (job / "beats.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    prompts = {
        "how_to_use": [
            "Give every 'a' prompt to Arena image generation with the previous frame as a reference "
            "when the beat continues an earlier shot.",
            "Then give the matching 'b' prompt WITH the generated a-frame as the reference image so the "
            "model only advances the motion (same shot, frame 2).",
            "Save results to the paths in the job. Never stretch a still: the engine derives the motion.",
        ],
        "style_suffix": ("Photorealistic cinematic documentary frame, ARRI Alexa 35mm lens, natural film grain, "
                         "deep shadows, dramatic low-key lighting, vertical 9:16 composition, ultra detailed, "
                         "no text, no watermark, no logo."),
        "prompts": [],
    }
    for index, sentence in enumerate(sentences):
        beat = beats[index]
        prompts["prompts"].append(
            {
                "sentence": index,
                "text": sentence,
                "a_path": beat["a"],
                "a_prompt": f"{args.topic or args.title}: {sentence}",
                "b_path": beat["b"],
                "b_prompt": "Same shot, frame 2 of one continuous take ~1.5s later: keep composition, lens and "
                            "lighting identical, advance ONLY the motion (subject moves, objects fall, light "
                            "sweeps, dust drifts).",
                "voice_over_path": f"vo/s{index + 1:02d}.mp3",
            }
        )
    (job / "prompts.json").write_text(json.dumps(prompts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"job created: {job}")
    print("next: 1) generate vo/sNN.mp3 with Arena speech")
    print("      2) generate each a/b key from prompts.json with Arena images")
    print(f"      3) python -m arena_only.studio build --slug {args.slug}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from arena_only.final_build import build

    job = job_dir(args.slug)
    out = Path(args.out) if args.out else ROOT / "outputs" / f"{args.slug}.mp4"
    manifest = build(job, out, preview=args.preview, preset=args.preset, crf=args.crf)
    print(json.dumps({k: manifest[k] for k in ("output", "duration", "bytes")}, indent=2))
    print("QA:", json.dumps(manifest["qa"].get("checks", manifest["qa"]), indent=2))
    return 0


def cmd_qa(args: argparse.Namespace) -> int:
    job = job_dir(args.slug)
    video = Path(args.video) if args.video else ROOT / "outputs" / f"{args.slug}.mp4"
    manifest_path = video.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        raise SystemExit(f"no manifest for {video}; run build first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    qa = manifest.get("qa", {})
    motion = manifest.get("motion", {})
    fade = float((json.loads((job / "beats.json").read_text(encoding="utf-8"))).get("fade_out", 0.0))
    checks = dict(qa.get("checks", {}))
    report = {
        "video": str(video),
        "duration": qa.get("duration"),
        "resolution": [qa.get("width"), qa.get("height")],
        "fps": qa.get("fps"),
        "frames": qa.get("frame_count"),
        "longest_low_motion_seconds": qa.get("longest_low_motion_seconds"),
        "median_frame_difference": qa.get("median_frame_difference"),
        "integrated_lufs": qa.get("integrated_lufs"),
        "true_peak_dbfs": qa.get("true_peak_dbfs"),
        "freeze_frames": motion.get("freeze_frames"),
        "checks": checks,
        "intentional_fade_seconds": fade,
    }
    bad = [name for name, ok in checks.items() if not ok]
    if bad == ["no_full_black_frame"] and fade > 0:
        report["notes"] = [f"the only failed gate is the intentional {fade:.1f}s ending fade to black"]
        bad = []
    print(json.dumps(report, indent=2))
    (video.with_suffix(".qa.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 1 if bad else 0


def cmd_pack(args: argparse.Namespace) -> int:
    job = job_dir(args.slug)
    spec = json.loads((job / "beats.json").read_text(encoding="utf-8"))
    video = Path(args.video) if args.video else ROOT / "outputs" / f"{args.slug}.mp4"
    if not video.is_file():
        raise SystemExit(f"no video at {video}; run build first")
    manifest = json.loads(video.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    folder = DELIVERY / args.slug
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, folder / video.name)
    shutil.copy2(video.with_suffix(".manifest.json"), folder / f"{args.slug}.manifest.json")

    stamp = max(0.5, float(manifest["duration"]) * 0.28)
    thumbnail = folder / f"{args.slug}-thumb.jpg"
    subprocess.run(
        [find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{stamp:.2f}",
         "-i", str(video), "-frames:v", "1", "-q:v", "2", str(thumbnail)], check=True,
    )
    captions = " | ".join(str(b.get("caption")) for b in manifest["beats"] if b.get("caption"))
    youtube = {
        "title": spec.get("title", args.slug)[:95],
        "description": (
            f"{spec.get('topic', spec.get('title', ''))}\n\n"
            f"{chr(10).join(spec.get('script', []))}\n\n"
            "Every frame of this Short was produced with Arena Agent tools only: "
            "AI keyframes, AI narration, optical-flow motion and a local cinematic render.\n\n"
            "#shorts #documentary #mystery #pyramids #ai"
        ),
        "tags": ["shorts", "documentary", "mystery", "history", "ai", args.slug],
        "categoryId": "27",
        "privacyStatus": "private",
        "madeForKids": False,
        "captions_text": captions,
        "thumbnail": str(thumbnail.name),
        "published_at": None,
        "note": "publishing stays draft_only until the private test upload is approved",
    }
    (folder / "youtube.json").write_text(json.dumps(youtube, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"packed: {folder}")
    for item in sorted(folder.iterdir()):
        print(f"  {item.name}  ({item.stat().st_size/1e6:.1f} MB)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    job = job_dir(args.slug)
    spec = json.loads((job / "beats.json").read_text(encoding="utf-8"))
    vo = sorted((job / spec["vo_dir"]).glob("s*.mp3"))
    keys = sorted((job / spec["keys_dir"]).glob("s*.*"))
    needed = [b["a"] for b in spec["beats"]] + [b.get("b") for b in spec["beats"] if b.get("b")]
    have = {p.name for p in keys}
    print(json.dumps({
        "job": args.slug,
        "sentences": len(spec.get("script", spec["beats"])),
        "voice_over_ready": len(vo),
        "keyframes_ready": len(have),
        "keyframes_needed": len(needed),
        "missing": sorted({Path(n).name for n in needed if Path(n).name not in have}),
        "video": (ROOT / "outputs" / f"{args.slug}.mp4").is_file(),
    }, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Arena Studio")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="scaffold a job + keyframe prompts")
    p.add_argument("--slug", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--topic", default="")
    p.add_argument("--script", required=True, help="text file, one spoken sentence per line")
    p.add_argument("--music", default="")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("build", help="render the finished Short")
    p.add_argument("--slug", required=True)
    p.add_argument("--out", default="")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--preset", default="medium")
    p.add_argument("--crf", type=int, default=17)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("qa", help="quality gates")
    p.add_argument("--slug", required=True)
    p.add_argument("--video", default="")
    p.set_defaults(func=cmd_qa)

    p = sub.add_parser("pack", help="delivery folder + YouTube metadata")
    p.add_argument("--slug", required=True)
    p.add_argument("--video", default="")
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("status", help="what is ready / missing")
    p.add_argument("--slug", required=True)
    p.set_defaults(func=cmd_status)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

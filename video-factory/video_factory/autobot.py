from __future__ import annotations

import argparse
import json
import logging
import os
import random
import shutil
import time
from pathlib import Path
from typing import Any

import requests
import schedule

from video_factory.config import ROOT
from video_factory.hybrid_premium.plan import EditPlan
from video_factory.hybrid_premium.renderer import render
from video_factory.providers.hf_spaces import HFSpacesWanProvider, HFSpacesError
from video_factory.providers.arena_stealth import ArenaStealthProvider, ArenaStealthError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("video-factory-autobot")

FALLBACK_PROMPTS = [
    {
        "title": "أسرار الأهرامات والذكاء الاصطناعي",
        "topic": "ancient_egypt",
        "scenes": [
            "Dramatic drone shot gliding over the Great Pyramids of Giza at golden hour sunset, cinematic lighting, 4k",
            "A glowing golden artifact floating inside a dark ancient tomb, soft particles, mysterious atmosphere",
            "Future holographic blueprint of the pyramid structure expanding into neon digital light, cyberpunk style"
        ],
        "captions": [
            "سر لبناء الأهرامات لم ينكشف بعد!",
            "تقنيات قديمة أم هبة من الفضاء؟",
            "الذكاء الاصطناعي يعيد اكتشاف التاريخ!"
        ]
    },
    {
        "title": "مستقبل المدن السيبرانية",
        "topic": "cyberpunk_city",
        "scenes": [
            "Futuristic cyberpunk city with neon lights, flying vehicles zooming through skyscrapers, cinematic 4k drone shot",
            "A humanoid robot looking at the glowing cityscape from a high balcony at night, rain falling softly",
            "Super high-speed hyperloop train speeding through a neon tunnel, motion blur, epic cinematic shot"
        ],
        "captions": [
            "كيف ستبدو مدننا في عام 2050؟",
            "السيارات الطائرة والأبراج الذكية",
            "المستقبل أسرع مما نتخيل!"
        ]
    },
    {
        "title": "أعماق المحيط المظلمة",
        "topic": "ocean_depths",
        "scenes": [
            "Deep ocean underwater shot showing bioluminescent glowing jellyfish floating in pitch dark water, 8k cinematic",
            "A giant mysterious glowing ancient ruin covered in corals at the bottom of the trench, volumetric light beams",
            "Submersible camera descending deeper into the abyss with searchlights revealing mysterious sea creatures"
        ],
        "captions": [
            "95% من أعماق المحيط لم يكتشفها البشر!",
            "كائنات مضيئة تعيش في الظلام التام",
            "ما الذي يخفيه القاع السحيق؟"
        ]
    }
]


def generate_daily_script(gemini_key: str | None = None) -> dict[str, Any]:
    """Generate or pick a script for today's video."""
    if gemini_key:
        LOG.info("🤖 Generating daily script using Gemini API...")
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
            headers = {"x-goog-api-key": gemini_key, "Content-Type": "application/json"}
            prompt = (
                "أنشئ سكريبت فيديو قصير (Shorts/Reels) جذاب باللغة العربية.\n"
                "أرجع النتيجة بصيغة JSON فقط بالتنسيق التالي:\n"
                "{\n"
                '  "title": "عنوان جذاب",\n'
                '  "topic": "الموضوع",\n'
                '  "scenes": ["Prompt for scene 1 in English", "Prompt for scene 2 in English", "Prompt for scene 3 in English"],\n'
                '  "captions": ["جملة قصيرة 1", "جملة قصيرة 2", "جملة قصيرة 3"]\n'
                "}\n"
                "اجعل الـ scenes قصيرة ودقيقة لإنشاء مقاطع AI بالإنجليزية high quality video prompts."
            )
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, headers=headers, json=data, timeout=30)
            res.raise_for_status()
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(text)
            LOG.info("✅ Gemini generated script: %s", parsed.get("title"))
            return parsed
        except Exception as e:
            LOG.warning("⚠️ Gemini generation failed (%s), using template bank.", e)

    selected = random.choice(FALLBACK_PROMPTS)
    LOG.info("📖 Using script template: %s", selected["title"])
    return selected


def generate_scene_clips(script: dict[str, Any], output_dir: Path) -> list[Path]:
    """Generate AI video clips targeting LMSYS Arena with HF ZeroGPU & fallback safety."""
    output_dir.mkdir(parents=True, exist_ok=True)
    arena_provider = ArenaStealthProvider()
    hf_provider = HFSpacesWanProvider(timeout_seconds=15)
    clip_paths = []

    for idx, scene_prompt in enumerate(script.get("scenes", []), start=1):
        clip_file = output_dir / f"scene_{idx}.mp4"
        LOG.info("🎥 Generating AI Scene %d/%d: %s", idx, len(script.get("scenes", [])), scene_prompt)
        generated = False

        # Attempt 1: LMSYS Arena Stealth Provider
        LOG.info("🏛️ [Tier 1] Attempting generation through LMSYS Arena (lmarena.ai)...")
        try:
            res_path = arena_provider.generate_video(prompt=scene_prompt, output_path=clip_file, timeout_seconds=60)
            clip_paths.append(res_path)
            LOG.info("✅ Scene %d generated via LMSYS Arena -> %s", idx, res_path)
            generated = True
        except Exception as exc:
            LOG.warning("⚠️ LMSYS Arena generation failed or busy: %s", exc)

        # Attempt 2: Hugging Face ZeroGPU Wan2.2
        if not generated:
            LOG.info("🤗 [Tier 2] Falling back to Hugging Face ZeroGPU Wan 2.2 API...")
            try:
                res = hf_provider.generate_video(
                    prompt=scene_prompt,
                    output_path=clip_file,
                    width=480,
                    height=832,
                    duration_seconds=3.0,
                    steps=4,
                    seed=random.randint(1000, 9999)
                )
                clip_paths.append(res.output_path)
                LOG.info("✅ Scene %d generated via HF ZeroGPU Wan 2.2 in %.1fs -> %s", idx, res.elapsed_seconds, res.output_path)
                generated = True
            except Exception as exc:
                LOG.warning("⚠️ HF ZeroGPU generation unavailable: %s", exc)

        # Attempt 3: Local Quality Video Clip Fallback
        if not generated:
            demo_clip = ROOT / "examples/hybrid_premium/ancient_mystery/sources/hero_monolith.mp4"
            fallback_dst = output_dir / f"scene_{idx}_fallback.mp4"
            if demo_clip.exists():
                shutil.copy2(demo_clip, fallback_dst)
            else:
                import subprocess
                cmd = [
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", "color=c=0x071018:s=480x832:d=3.0",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(fallback_dst)
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            clip_paths.append(fallback_dst)
            LOG.info("✅ Used fallback scene clip for scene %d -> %s", idx, fallback_dst)

    return clip_paths


def build_edit_plan(script: dict[str, Any], clip_paths: list[Path], plan_path: Path) -> Path:
    """Create a valid EditPlan JSON structure."""
    shots = []
    total_duration = 0.0

    demo_narration = ROOT / "examples/hybrid_premium/ancient_mystery/audio/narration.mp3"
    narration_rel = None
    if demo_narration.exists():
        audio_dir = plan_path.parent / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        dst_narration = audio_dir / "narration.mp3"
        shutil.copy2(demo_narration, dst_narration)
        narration_rel = f"audio/{dst_narration.name}"

    for idx, clip_p in enumerate(clip_paths, start=1):
        rel_source = f"sources/{clip_p.name}"
        shots.append({
            "source": rel_source,
            "in": 0.0,
            "duration": 3.0,
            "label": f"scene_{idx}",
            "grade": "neutral",
            "source_class": "licensed_motion",
            "license_ref": "Apache-2.0"
        })
        total_duration += 3.0

    plan_data = {
        "id": f"autobot-{int(time.time())}",
        "title": script.get("title", "Autobot Daily Short"),
        "duration": total_duration,
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "shots": shots,
        "narration": narration_rel,
        "quality": {
            "shot_duration_seconds": [0.3, 5.0],
            "visual_beats": [1, 20],
            "minimum_unique_motion_sources": 1
        }
    }

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan_data, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("📝 Edit plan saved to %s", plan_path)
    return plan_path


def render_and_export(plan_path: Path, output_mp4: Path) -> Path:
    """Render final vertical 1080x1920 MP4 using FFmpeg Hybrid Premium engine."""
    LOG.info("🎬 Rendering final 1080x1920 MP4 via Hybrid Premium FFmpeg Engine...")
    edit_plan = EditPlan.load(plan_path)
    rendered_output = render(edit_plan, output_mp4)
    LOG.info("🎉 Final MP4 rendered: %s (%d bytes)", rendered_output, rendered_output.stat().st_size)
    return rendered_output


def upload_youtube_if_configured(video_path: Path, script: dict[str, Any], secrets_path: Path) -> bool:
    """Upload to YouTube if client_secrets.json or OAuth tokens are set up."""
    if not secrets_path.exists():
        LOG.info("ℹ️ YouTube OAuth credentials not configured (%s). Video saved locally as Draft.", secrets_path)
        return False

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials

        token_path = ROOT / ".arena/youtube_token.json"
        if not token_path.exists():
            LOG.info("ℹ️ YouTube token.json not found. Save token in Local Studio to enable automated uploading.")
            return False

        creds = Credentials.from_authorized_user_file(str(token_path))
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": script.get("title", "Daily AI Short"),
                "description": f"تم إنشاؤه وتوليده تلقائياً بواسطة Video Factory Autobot.\n#Shorts #AI #{script.get('topic', 'AI')}",
                "tags": ["Shorts", "AI Video", "Arena AI", "Video Factory"],
                "categoryId": "28"
            },
            "status": {
                "privacyStatus": "public"
            }
        }
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        res = None
        while res is None:
            status, res = req.next_chunk()
            if status:
                LOG.info("⏳ Upload progress: %d%%", int(status.progress() * 100))
        LOG.info("🎉 YouTube Video published! ID: %s", res.get("id"))
        return True
    except Exception as exc:
        LOG.error("❌ YouTube upload failed: %s", exc)
        return False


def run_pipeline_now() -> dict[str, Any]:
    """Run one complete automated daily video generation pipeline."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    work_dir = ROOT / f"outputs/autobot_{timestamp}"
    work_dir.mkdir(parents=True, exist_ok=True)

    gemini_key = None
    secrets_file = ROOT / ".arena/local-secrets.json"
    if secrets_file.exists():
        try:
            data = json.loads(secrets_file.read_text())
            gemini_key = data.get("gemini_api_key")
        except Exception:
            pass

    script = generate_daily_script(gemini_key)
    clip_paths = generate_scene_clips(script, work_dir / "sources")
    plan_path = build_edit_plan(script, clip_paths, work_dir / "edit_plan.json")
    output_mp4 = work_dir / f"final_{timestamp}.mp4"
    rendered_mp4 = render_and_export(plan_path, output_mp4)

    uploaded = upload_youtube_if_configured(rendered_mp4, script, ROOT / "client_secrets.json")

    result = {
        "timestamp": timestamp,
        "title": script.get("title"),
        "mp4_path": str(rendered_mp4.relative_to(ROOT)),
        "file_size": rendered_mp4.stat().st_size,
        "uploaded_to_youtube": uploaded,
        "status": "success"
    }

    (work_dir / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    LOG.info("✨ Autobot daily pipeline finished successfully!")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Video Factory Autobot")
    parser.add_argument("--now", action="store_true", help="Run daily pipeline immediately")
    parser.add_argument("--schedule", type=str, default="17:00", help="Daily execution time (HH:MM)")
    args = parser.parse_args()

    if args.now:
        run_pipeline_now()
        return

    LOG.info("⏰ Starting Autobot scheduler... Scheduled daily at %s", args.schedule)
    schedule.every().day.at(args.schedule).do(run_pipeline_now)

    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()

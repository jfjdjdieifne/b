"""Kaggle GPU worker. Phase 1: install/restart. Phase 2: render one Wan scene."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

WORK = Path("/kaggle/working")
INPUT = Path("/kaggle/input")
HERE = Path(__file__).resolve().parent
REPO = WORK / "WanGP"
DATA = WORK / "WanGP-data"
RESULT = WORK / "result.json"


def run(cmd, **kwargs):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def bootstrap():
    if not REPO.exists():
        run(["git", "clone", "--depth", "1", "https://github.com/deepbeepmeep/Wan2GP.git", str(REPO)])
    run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "uv"])
    run([sys.executable, "-m", "uv", "pip", "install", "--system", "-r", str(REPO / "requirements.txt")])
    marker = WORK / ".wan_bootstrapped"
    marker.write_text("ok")
    os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve()), "--run"])


def find_payload() -> Path:
    candidates = [HERE / "job_payload.json", Path("/kaggle/working/job_payload.json")]
    candidates.extend(INPUT.rglob("job_payload.json"))
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("job_payload.json not found")


def download_image(url: str) -> Path:
    import requests
    path = WORK / "start_image.png"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def render():
    payload = json.loads(find_payload().read_text())
    os.environ.update({
        "WAN2GP_DISABLE_AUDIO": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        "WAN_CACHE_DIR": str(DATA / "cache"),
        "HF_HOME": str(DATA / "cache" / "huggingface"),
    })
    DATA.mkdir(parents=True, exist_ok=True)
    os.chdir(REPO)
    sys.path.insert(0, str(REPO))

    image_url = payload.get("image_url")
    image_path = download_image(image_url) if image_url else None

    from shared.api import init
    session = init(
        root=REPO,
        output_dir=WORK,
        cli_args=["--profile", "5", "--attention", "sdpa", "--fp16", "--verbose", "1"],
        console_output=True,
        console_isatty=True,
    )
    model_type = "ti2v_2_2_fastwan"
    settings = session.get_default_settings(model_type)
    settings.update({
        "model_type": model_type,
        "prompt": payload["prompt"],
        "negative_prompt": payload.get("negative_prompt", ""),
        "resolution": "480x832",
        "video_length": 121,
        "force_fps": 24,
        "num_inference_steps": 3,
        "guidance_scale": 1,
        "flow_shift": 3,
        "seed": int(payload.get("seed", 1987)),
        "batch_size": 1,
        "repeat_generation": 1,
        "output_filename": "scene",
    })
    if image_path:
        settings["image_start"] = str(image_path)
        settings["image_prompt_type"] = "S"

    result = session.submit_task(settings).result()
    if not result.success or not result.generated_files:
        errors = " | ".join(error.message for error in result.errors)
        raise RuntimeError(errors or "Wan generation returned no file")
    generated = Path(result.generated_files[0])
    final = WORK / "scene.mp4"
    if generated.resolve() != final.resolve():
        shutil.copy2(generated, final)
    RESULT.write_text(json.dumps({"status": "done", "video": str(final), "job_id": payload["id"]}, indent=2))
    print(f"VIDEO_FACTORY_DONE={final}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    try:
        render() if args.run else bootstrap()
    except Exception as exc:
        RESULT.write_text(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()

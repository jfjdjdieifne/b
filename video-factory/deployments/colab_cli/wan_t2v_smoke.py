"""Generate a tiny real Wan T2V clip on a Colab T4.

This is intentionally a compatibility/quotas smoke test, not the final quality
profile. It installs only the inference packages missing from a fresh Colab VM,
quantizes the text encoder and diffusion transformer to NF4 while loading, and
writes an MP4 plus machine-readable metadata under /content.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time
import warnings

OUTPUT = Path("/content/wan_t2v_smoke.mp4")
METADATA = Path("/content/wan_t2v_smoke.json")
MODEL_ID = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"


class DownloadHeartbeat:
    """Emit useful progress while Hugging Face/Xet downloads without a TTY."""

    def __init__(self, started: float) -> None:
        self.started = started
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    @staticmethod
    def _cache_gib() -> float:
        root = Path("/root/.cache/huggingface/hub")
        total = 0
        if root.exists():
            for path in root.rglob("*"):
                try:
                    if path.is_file():
                        total += path.stat().st_size
                except OSError:
                    pass
        return total / 1024**3

    def _run(self) -> None:
        while not self.stop.wait(30):
            disk = shutil.disk_usage("/content")
            print(
                "WAN_SMOKE_HEARTBEAT="
                f"elapsed_s={time.perf_counter() - self.started:.0f} "
                f"hf_cache_gib={self._cache_gib():.1f} "
                f"disk_free_gib={disk.free / 1024**3:.1f}",
                flush=True,
            )

    def __enter__(self) -> "DownloadHeartbeat":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.stop.set()
        self.thread.join(timeout=2)


def install_dependencies() -> None:
    packages = [
        "diffusers==0.39.0",
        "transformers==4.57.6",
        "accelerate==1.14.0",
        "bitsandbytes==0.50.1",
        "ftfy>=6.3.1",
        "imageio-ffmpeg>=0.6.0",
        "sentencepiece>=0.2.0",
        "huggingface_hub>=0.36.0",
    ]
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "--upgrade", *packages]
    )


def main() -> None:
    started = time.perf_counter()
    # Xet can deadlock while resuming multi-GB partial blobs in headless Colab.
    # Plain HTTP is deterministic and supports byte-range resume.
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    warnings.filterwarnings("ignore", category=FutureWarning, module=r"diffusers.*")
    warnings.filterwarnings("ignore", category=UserWarning, module=r"huggingface_hub\.utils\._auth")
    print("WAN_SMOKE_STAGE=install", flush=True)
    install_dependencies()

    print("WAN_SMOKE_STAGE=imports", flush=True)
    import torch
    from diffusers import AutoModel, WanPipeline
    from diffusers.quantizers import PipelineQuantizationConfig
    from diffusers.utils import export_to_video
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import disable_progress_bars

    disable_progress_bars()

    if not torch.cuda.is_available():
        raise RuntimeError("A CUDA GPU is required")

    gpu = torch.cuda.get_device_name(0)
    total_vram = torch.cuda.get_device_properties(0).total_memory
    print(f"WAN_SMOKE_GPU={gpu} vram_gib={total_vram / 1024**3:.2f}", flush=True)

    print("WAN_SMOKE_STAGE=download_http", flush=True)
    quantization = PipelineQuantizationConfig(
        quant_backend="bitsandbytes_4bit",
        quant_kwargs={
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_compute_dtype": torch.float16,
            "bnb_4bit_use_double_quant": True,
        },
        components_to_quantize=["transformer", "text_encoder"],
    )
    with DownloadHeartbeat(started):
        local_model = snapshot_download(
            MODEL_ID,
            max_workers=1,
            token=False,
        )
        print("WAN_SMOKE_STAGE=load_quantized_pipeline", flush=True)
        vae = AutoModel.from_pretrained(
            local_model,
            subfolder="vae",
            torch_dtype=torch.float32,
            local_files_only=True,
        )
        pipe = WanPipeline.from_pretrained(
            local_model,
            vae=vae,
            quantization_config=quantization,
            torch_dtype=torch.float16,
            local_files_only=True,
        )
    pipe.to("cuda")
    if hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    if hasattr(pipe.vae, "enable_slicing"):
        pipe.vae.enable_slicing()

    prompt = (
        "Cinematic wildlife documentary shot of a red fox walking through tall "
        "grass at sunrise, its fur moving naturally in the breeze, realistic body "
        "motion, subtle handheld camera tracking, warm rim light, detailed film look"
    )
    negative_prompt = (
        "static image, frozen subject, slideshow, text, subtitles, watermark, low "
        "quality, blurry, deformed anatomy, duplicate animal, camera jitter"
    )

    torch.cuda.reset_peak_memory_stats()
    generation_started = time.perf_counter()
    print("WAN_SMOKE_STAGE=generate", flush=True)
    with torch.inference_mode():
        frames = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            height=480,
            width=832,
            num_frames=17,
            num_inference_steps=10,
            guidance_scale=5.0,
            generator=torch.Generator(device="cuda").manual_seed(20260819),
        ).frames[0]
    generation_seconds = time.perf_counter() - generation_started

    print("WAN_SMOKE_STAGE=encode", flush=True)
    export_to_video(frames, str(OUTPUT), fps=16, quality=8)
    metadata = {
        "ok": True,
        "model": MODEL_ID,
        "gpu": gpu,
        "vram_gib": round(total_vram / 1024**3, 2),
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 1024**3, 2),
        "width": 832,
        "height": 480,
        "frames": 17,
        "fps": 16,
        "duration_seconds": 17 / 16,
        "steps": 10,
        "seed": 20260819,
        "generation_seconds": round(generation_seconds, 2),
        "total_seconds": round(time.perf_counter() - started, 2),
        "output_bytes": OUTPUT.stat().st_size,
        "python": platform.python_version(),
        "torch": torch.__version__,
    }
    METADATA.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("WAN_SMOKE_RESULT=" + json.dumps(metadata), flush=True)


if __name__ == "__main__":
    main()

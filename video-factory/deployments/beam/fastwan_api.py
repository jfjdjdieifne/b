"""Wan 2.2 5B T2V/I2V endpoint for Beam Cloud.

The endpoint is deliberately conservative for the first live test: generated
clips are capped at four seconds and at roughly 480x832 pixels. After measuring
VRAM, runtime, quality, and actual Beam billing, these limits can be raised.

No API keys are embedded here. Beam authentication stays in BEAM_TOKEN or the
Beam CLI config; gated Hugging Face credentials, if ever needed, belong in Beam
Secrets as HF_TOKEN.
"""

from __future__ import annotations

from beam import Image, Output, Volume, endpoint, env

MODEL_ID = "FastVideo/FastWan2.2-TI2V-5B-FullAttn-Diffusers"
CACHE_PATH = "/cache/huggingface"
FIXED_FPS = 24
MIN_FRAMES = 25
MAX_FRAMES = 97  # About four seconds at 24 fps during validation.
MAX_AREA = 480 * 832
MAX_PROMPT_CHARS = 2_000
DEFAULT_NEGATIVE_PROMPT = (
    "overexposed, static, blurred details, subtitles, paintings, still image, "
    "gray cast, worst quality, low quality, JPEG artifacts, ugly, incomplete, "
    "deformed, disfigured, malformed limbs, fused fingers, messy background, "
    "walking backwards, watermark, text, logo, signature"
)

FASTWAN_IMAGE = (
    Image(python_version="python3.12")
    .add_python_packages(
        [
            "torch==2.11.0",
            "torchvision==0.26.0",
            "torchao==0.17.0",
            "diffusers==0.39.0",
            "transformers==5.14.1",
            "peft==0.19.1",
            "accelerate==1.14.0",
            "safetensors==0.8.0",
            "sentencepiece==0.2.2",
            "ftfy==6.3.1",
            "imageio==2.37.3",
            "imageio-ffmpeg==0.6.0",
            "Pillow>=11,<13",
            "numpy==2.2.6",
            "huggingface_hub==1.24.0",
            "hf_transfer==0.1.9",
        ]
    )
    .with_envs(
        {
            "HF_HOME": CACHE_PATH,
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
)


def _round_dimension(value: object, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 256 or parsed > 1024:
        raise ValueError(f"{name} must be between 256 and 1024")
    return max(32, (parsed // 32) * 32)


def _validated_dimensions(width: object, height: object) -> tuple[int, int]:
    width_i = _round_dimension(width, "width")
    height_i = _round_dimension(height, "height")
    if width_i * height_i > MAX_AREA:
        raise ValueError(
            f"width*height exceeds the validation limit ({MAX_AREA} pixels); "
            "use 480x832, 832x480, or a smaller size"
        )
    return width_i, height_i


def _bounded_float(
    value: object, name: str, minimum: float, maximum: float
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _bounded_int(value: object, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _decode_input_image(encoded: str):
    import base64
    import binascii
    from io import BytesIO

    from PIL import Image as PILImage
    from PIL import ImageOps

    if encoded.startswith("data:"):
        try:
            encoded = encoded.split(",", 1)[1]
        except IndexError as exc:
            raise ValueError("invalid image data URL") from exc
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("input_image_base64 is not valid base64") from exc
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("input image is larger than 20 MiB")
    try:
        image = PILImage.open(BytesIO(raw))
        image.load()
    except Exception as exc:
        raise ValueError("input_image_base64 is not a supported image") from exc
    return ImageOps.exif_transpose(image).convert("RGB")


if env.is_remote():
    import tempfile
    import time
    import uuid

    import torch
    from diffusers import (
        AutoencoderKLWan,
        UniPCMultistepScheduler,
        WanImageToVideoPipeline,
        WanPipeline,
        WanTransformer3DModel,
    )
    from diffusers.utils import export_to_video
    from torchao.quantization import Int8WeightOnlyConfig, quantize_
    from transformers import UMT5EncoderModel


def load_models():
    """Load shared Wan components once for both T2V and I2V pipelines."""
    vae = AutoencoderKLWan.from_pretrained(
        MODEL_ID,
        subfolder="vae",
        torch_dtype=torch.float32,
        cache_dir=CACHE_PATH,
    )
    vae.enable_tiling()
    vae.enable_slicing()

    text_encoder = UMT5EncoderModel.from_pretrained(
        MODEL_ID,
        subfolder="text_encoder",
        torch_dtype=torch.bfloat16,
        cache_dir=CACHE_PATH,
    )
    quantize_(text_encoder, Int8WeightOnlyConfig())

    transformer = WanTransformer3DModel.from_pretrained(
        MODEL_ID,
        subfolder="transformer",
        torch_dtype=torch.bfloat16,
        cache_dir=CACHE_PATH,
    )

    t2v = WanPipeline.from_pretrained(
        MODEL_ID,
        vae=vae,
        text_encoder=text_encoder,
        transformer=transformer,
        torch_dtype=torch.bfloat16,
        cache_dir=CACHE_PATH,
    )
    i2v = WanImageToVideoPipeline.from_pretrained(
        MODEL_ID,
        vae=vae,
        text_encoder=text_encoder,
        transformer=transformer,
        torch_dtype=torch.bfloat16,
        cache_dir=CACHE_PATH,
    )

    for pipe in (t2v, i2v):
        pipe.scheduler = UniPCMultistepScheduler.from_config(
            pipe.scheduler.config, flow_shift=8.0
        )
        pipe.to("cuda")

    return {"t2v": t2v, "i2v": i2v}


@endpoint(
    name="video-factory-fastwan-5b",
    image=FASTWAN_IMAGE,
    on_start=load_models,
    # Prefer 32 GiB, then the fast 24 GiB options. The conservative first-test
    # resolution is designed to fit all three; actual VRAM is measured first.
    gpu=["RTX5090", "RTX4090", "A10G"],
    cpu=4,
    memory="64Gi",
    volumes=[Volume(name="video-factory-fastwan-cache", mount_path="/cache")],
    timeout=900,
    # Beam SDK defaults to 180 warm seconds; force zero while validating so a
    # completed request cannot consume another three minutes of GPU credit.
    keep_warm_seconds=0,
)
def generate_video(context, **inputs):
    """Generate a real T2V or I2V clip and return a temporary output URL."""
    started = time.perf_counter()

    prompt = str(inputs.get("prompt", "")).strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    if len(prompt) > MAX_PROMPT_CHARS:
        return {"ok": False, "error": "prompt is too long"}

    negative_prompt = str(
        inputs.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
    ).strip()
    if len(negative_prompt) > MAX_PROMPT_CHARS:
        return {"ok": False, "error": "negative_prompt is too long"}

    try:
        width, height = _validated_dimensions(
            inputs.get("width", 480), inputs.get("height", 832)
        )
        duration = _bounded_float(
            inputs.get("duration_seconds", 1.1),
            "duration_seconds",
            MIN_FRAMES / FIXED_FPS,
            MAX_FRAMES / FIXED_FPS,
        )
        steps = _bounded_int(inputs.get("steps", 4), "steps", 1, 8)
        guidance = _bounded_float(
            inputs.get("guidance_scale", 0.0), "guidance_scale", 0.0, 5.0
        )
        seed = _bounded_int(inputs.get("seed", 42), "seed", 0, 2_147_483_647)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    requested_frames = int(round(duration * FIXED_FPS))
    # Wan temporal latents are most reliable at 4k+1 frame counts.
    frames = 1 + 4 * round((requested_frames - 1) / 4)
    frames = max(MIN_FRAMES, min(MAX_FRAMES, frames))
    encoded_image = inputs.get("input_image_base64")

    try:
        generator = torch.Generator(device="cuda").manual_seed(seed)
        with torch.inference_mode():
            if encoded_image:
                image = _decode_input_image(str(encoded_image)).resize((width, height))
                output_frames = context.on_start_value["i2v"](
                    image=image,
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    num_frames=frames,
                    guidance_scale=guidance,
                    num_inference_steps=steps,
                    generator=generator,
                ).frames[0]
                mode = "image-to-video"
            else:
                output_frames = context.on_start_value["t2v"](
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    num_frames=frames,
                    guidance_scale=guidance,
                    num_inference_steps=steps,
                    generator=generator,
                ).frames[0]
                mode = "text-to-video"

        path = f"/tmp/wan_{uuid.uuid4().hex}.mp4"
        export_to_video(output_frames, path, fps=FIXED_FPS)
        output = Output(path=path)
        output.save()
        output_url = output.public_url(expires=86_400)

        return {
            "ok": True,
            "output_url": output_url,
            "mode": mode,
            "model": MODEL_ID,
            "seed": seed,
            "width": width,
            "height": height,
            "frames": frames,
            "fps": FIXED_FPS,
            "duration_seconds": round(frames / FIXED_FPS, 3),
            "steps": steps,
            "guidance_scale": guidance,
            "generation_seconds": round(time.perf_counter() - started, 3),
            "gpu_name": torch.cuda.get_device_name(0),
            "peak_vram_gib": round(
                torch.cuda.max_memory_allocated() / (1024**3), 3
            ),
        }
    except torch.cuda.OutOfMemoryError as exc:
        torch.cuda.empty_cache()
        return {
            "ok": False,
            "error": "CUDA out of memory",
            "detail": str(exc),
            "suggestion": "retry at 352x608, 25 frames, and 2 steps",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "detail": str(exc),
        }

"""Minimal real-CUDA validation for the official Google Colab CLI."""

import json
import platform
import time

import torch

started = time.perf_counter()
result = {
    "ok": False,
    "python": platform.python_version(),
    "torch": torch.__version__,
    "cuda_available": torch.cuda.is_available(),
}

if torch.cuda.is_available():
    device = torch.device("cuda")
    x = torch.randn((512, 512), dtype=torch.float16, device=device)
    checksum = float((x @ x).float().mean().item())
    props = torch.cuda.get_device_properties(0)
    result.update(
        {
            "ok": True,
            "gpu": torch.cuda.get_device_name(0),
            "vram_gib": round(props.total_memory / (1024**3), 2),
            "checksum": checksum,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    )

print("COLAB_GPU_SMOKE=" + json.dumps(result, ensure_ascii=False))
if not result["ok"]:
    raise SystemExit(2)

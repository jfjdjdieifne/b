"""Minimal Beam GPU test.

Deploy only after creating a Beam API key. This intentionally does not load a
model, so it verifies account/GPU access while consuming only a few seconds.
"""

from beam import endpoint


@endpoint(
    name="video-factory-gpu-smoke",
    gpu=["T4", "A10G", "RTX4090"],
    cpu=1,
    memory="2Gi",
    timeout=120,
    keep_warm_seconds=0,
)
def gpu_smoke(**_inputs):
    import time

    import torch

    started = time.perf_counter()
    device = torch.device("cuda")
    # A real CUDA operation, not merely an nvidia-smi visibility check.
    a = torch.randn((512, 512), device=device, dtype=torch.float16)
    checksum = float((a @ a).float().mean().item())
    props = torch.cuda.get_device_properties(0)

    return {
        "ok": True,
        "gpu_name": torch.cuda.get_device_name(0),
        "vram_gib": round(props.total_memory / (1024**3), 2),
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "cuda_operation_checksum": checksum,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }

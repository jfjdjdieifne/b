from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests


DEFAULT_WAN_SPACE = "Upsampler/wan-2-2-5b-video"


class HFSpacesError(RuntimeError):
    """Sanitized Hugging Face Space failure suitable for provider failover."""

    def __init__(self, message: str, *, retriable: bool = False, quota: bool = False) -> None:
        self.retriable = retriable
        self.quota = quota
        super().__init__(message)


@dataclass(frozen=True)
class HFSpacesVideoResult:
    output_path: Path
    elapsed_seconds: float
    space_id: str
    mode: str
    width: int
    height: int
    duration_requested: float
    steps: int
    seed: int | float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class HFSpacesWanProvider:
    """Wan 2.2 TI2V-5B through a public ZeroGPU Gradio API.

    This uses the caller's Hugging Face ZeroGPU allowance. It does not automate a
    consumer website and does not bypass quotas: ``HF_TOKEN`` is forwarded through
    the official Gradio client so usage is attributed to the owning account.
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        space_id: str = DEFAULT_WAN_SPACE,
        timeout_seconds: int = 900,
        client_factory: Callable[..., Any] | None = None,
        file_handler: Callable[[str], Any] | None = None,
    ) -> None:
        self._token = (token if token is not None else os.getenv("HF_TOKEN", "")).strip()
        self.space_id = space_id.strip()
        if not self.space_id or "/" not in self.space_id:
            raise ValueError("Hugging Face Space id must look like owner/name")
        self.timeout_seconds = int(timeout_seconds)
        if client_factory is None or file_handler is None:
            try:
                from gradio_client import Client, handle_file
            except ImportError as exc:
                raise RuntimeError(
                    "gradio_client is missing. Install requirements.txt before using HF Spaces."
                ) from exc
            client_factory = client_factory or Client
            file_handler = file_handler or handle_file
        self._client_factory = client_factory
        self._file_handler = file_handler
        self._client: Any | None = None

    def _sanitize(self, text: str) -> str:
        return text.replace(self._token, "***") if self._token else text

    def _get_client(self) -> Any:
        if self._client is None:
            kwargs: dict[str, Any] = {"verbose": False}
            if self._token:
                kwargs["hf_token"] = self._token
            self._client = self._client_factory(self.space_id, **kwargs)
        return self._client

    def health(self) -> dict[str, Any]:
        """Read public Hub runtime metadata without consuming GPU quota."""
        response = requests.get(
            f"https://huggingface.co/api/spaces/{self.space_id}", timeout=30
        )
        response.raise_for_status()
        payload = response.json()
        runtime = payload.get("runtime") or {}
        hardware = runtime.get("hardware") or {}
        return {
            "space_id": self.space_id,
            "stage": runtime.get("stage"),
            "hardware_current": hardware.get("current"),
            "hardware_requested": hardware.get("requested"),
            "sha": payload.get("sha"),
            "disabled": payload.get("disabled", False),
            "private": payload.get("private", False),
        }

    @staticmethod
    def _find_video_path(value: Any) -> Path | None:
        if isinstance(value, (str, os.PathLike)):
            path = Path(value)
            if path.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"} and path.exists():
                return path
            return None
        if isinstance(value, dict):
            for key in ("video", "path", "name", "file"):
                if key in value and (found := HFSpacesWanProvider._find_video_path(value[key])):
                    return found
            for item in value.values():
                if found := HFSpacesWanProvider._find_video_path(item):
                    return found
            return None
        if isinstance(value, (list, tuple)):
            for item in value:
                if found := HFSpacesWanProvider._find_video_path(item):
                    return found
        return None

    @staticmethod
    def _find_seed(value: Any) -> int | float | None:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            candidate = value[-1]
            if isinstance(candidate, (int, float)):
                return candidate
        return None

    def generate_video(
        self,
        prompt: str,
        output_path: str | Path,
        *,
        input_image: str | Path | None = None,
        height: int = 832,
        width: int = 480,
        duration_seconds: float = 2.0,
        steps: int = 4,
        guidance_scale: float = 0.0,
        negative_prompt: str = (
            "overexposed, static, blurry, low quality, deformed, morphing, "
            "watermark, text, logo, signature"
        ),
        seed: int = 1987,
        randomize_seed: bool = False,
    ) -> HFSpacesVideoResult:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Video prompt cannot be empty")
        if height < 256 or height > 1024 or width < 256 or width > 1024:
            raise ValueError("Hugging Face Wan dimensions must be within 256..1024")
        if height % 32 or width % 32:
            raise ValueError("Hugging Face Wan dimensions must be multiples of 32")
        if not 1.0 <= duration_seconds <= 8.0:
            raise ValueError("Hugging Face Wan duration must be within 1..8 seconds")
        if not 1 <= steps <= 8:
            raise ValueError("Hugging Face Wan steps must be within 1..8")
        image_arg: Any = None
        mode = "text-to-video"
        if input_image is not None:
            image_path = Path(input_image)
            if not image_path.is_file():
                raise ValueError(f"Input image does not exist: {image_path}")
            image_arg = self._file_handler(str(image_path))
            mode = "image-to-video"

        started = time.monotonic()
        try:
            client = self._get_client()
            args = (
                image_arg,
                prompt,
                height,
                width,
                negative_prompt,
                float(duration_seconds),
                float(guidance_scale),
                float(steps),
                float(seed),
                bool(randomize_seed),
            )
            kwargs = {"api_name": "/generate_video"}
            if hasattr(client, "submit"):
                job = client.submit(*args, **kwargs)
                result = job.result(timeout=self.timeout_seconds)
            else:
                result = client.predict(*args, **kwargs)
        except Exception as exc:
            message = self._sanitize(str(exc) or type(exc).__name__)
            lowered = message.lower()
            is_quota = "quota" in lowered or "zerogpu runs limit" in lowered
            retriable = is_quota or any(
                marker in lowered
                for marker in (
                    "queue",
                    "timeout",
                    "timed out",
                    "temporarily",
                    "unavailable",
                    "gpu was available",
                    "connection",
                    "502",
                    "503",
                    "504",
                )
            )
            raise HFSpacesError(
                f"Hugging Face Space failed: {message}",
                retriable=retriable,
                quota=is_quota,
            ) from exc

        generated = self._find_video_path(result)
        if generated is None:
            raise HFSpacesError("Hugging Face Space returned no local video file")
        if generated.stat().st_size < 1024:
            raise HFSpacesError("Hugging Face Space returned a truncated video")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".part")
        try:
            shutil.copy2(generated, temp)
            temp.replace(output)
        finally:
            if temp.exists():
                temp.unlink()

        elapsed = round(time.monotonic() - started, 3)
        return HFSpacesVideoResult(
            output_path=output,
            elapsed_seconds=elapsed,
            space_id=self.space_id,
            mode=mode,
            width=width,
            height=height,
            duration_requested=float(duration_seconds),
            steps=steps,
            seed=self._find_seed(result) or seed,
            metadata={
                "provider": "huggingface_zerogpu_space",
                "space_id": self.space_id,
                "authenticated": bool(self._token),
                "api_name": "/generate_video",
            },
        )

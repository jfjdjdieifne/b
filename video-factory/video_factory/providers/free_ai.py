from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests


class FreeAIError(RuntimeError):
    """A sanitized Free.ai request failure.

    The API key is deliberately excluded from repr/messages and is never written to
    diagnostics. HTTP 429/5xx and queue timeouts are marked retriable so the future
    provider router can fail over without exposing credentials.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        retriable: bool = False,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.retriable = retriable
        super().__init__(message)


@dataclass(frozen=True)
class FreeAIVideoResult:
    output_path: Path
    elapsed_seconds: float
    status_code: int
    job_id: str | None = None
    token_cost: int | float | None = None
    remaining_tokens: int | float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FreeAIProvider:
    """Minimal Free.ai CogVideoX adapter for T2V/I2V smoke tests.

    The provider currently defaults to Free.ai's self-hosted video model by omitting
    ``model``. This is intentional: the public docs call it CogVideoX but do not
    publish a stable self-hosted model id. A model id can be supplied after the live
    account catalogue confirms it.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.free.ai",
        timeout_seconds: int = 900,
        poll_interval_seconds: float = 5.0,
        session: requests.Session | None = None,
    ) -> None:
        key = (api_key or os.getenv("FREE_AI_API_KEY", "")).strip()
        if not key:
            raise RuntimeError(
                "FREE_AI_API_KEY is missing. Create an sk-free-* key in the Free.ai "
                "account dashboard and store it only in an environment secret."
            )
        self._api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(30, int(timeout_seconds))
        self.poll_interval_seconds = max(0.1, float(poll_interval_seconds))
        self.session = session or requests.Session()
        self.headers = {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json, video/mp4, application/octet-stream",
        }

    def _sanitize(self, text: str) -> str:
        return text.replace(self._api_key, "***")

    @staticmethod
    def _json_or_none(response: requests.Response) -> dict[str, Any] | None:
        try:
            value = response.json()
        except (ValueError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _raise_for_response(self, response: requests.Response) -> None:
        if response.status_code < 400:
            return
        payload = self._json_or_none(response) or {}
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("error")
            code = error.get("code") or payload.get("error_id")
        else:
            message = error
            code = payload.get("error_id") or payload.get("code")
        message = str(message or response.reason or "Free.ai request failed")
        status = response.status_code
        raise FreeAIError(
            self._sanitize(f"Free.ai HTTP {status}: {message}"),
            status_code=status,
            code=str(code) if code else None,
            retriable=status in {408, 409, 425, 429} or status >= 500,
        )

    @staticmethod
    def _nested(payload: dict[str, Any], *paths: tuple[str, ...]) -> Any:
        for path in paths:
            current: Any = payload
            for key in path:
                if not isinstance(current, dict) or key not in current:
                    current = None
                    break
                current = current[key]
            if current not in (None, ""):
                return current
        return None

    def _absolute_url(self, value: str) -> str:
        return urljoin(self.base_url + "/", value)

    @staticmethod
    def _safe_download_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise FreeAIError("Free.ai returned an unsafe or invalid video URL")

    def _download(self, url: str, output_path: Path) -> None:
        self._safe_download_url(url)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_suffix(output_path.suffix + ".part")
        try:
            with self.session.get(url, stream=True, timeout=(30, 300)) as response:
                self._raise_for_response(response)
                content_type = (response.headers.get("Content-Type") or "").lower()
                written = 0
                with temp_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > 300 * 1024 * 1024:
                            raise FreeAIError("Free.ai video exceeded the 300 MB safety limit")
                        handle.write(chunk)
                if written < 1024:
                    raise FreeAIError("Free.ai returned an empty or truncated video")
                if content_type and not any(
                    marker in content_type
                    for marker in ("video/", "application/octet-stream", "binary/octet-stream")
                ):
                    # Signed CDNs occasionally use application/octet-stream. Reject obvious JSON/HTML.
                    if "json" in content_type or "html" in content_type:
                        raise FreeAIError(
                            f"Free.ai download returned {content_type} instead of MP4"
                        )
            temp_path.replace(output_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _write_direct_video(self, response: requests.Response, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_suffix(output_path.suffix + ".part")
        try:
            body = response.content
            if len(body) < 1024:
                raise FreeAIError("Free.ai returned an empty or truncated direct video")
            if len(body) > 300 * 1024 * 1024:
                raise FreeAIError("Free.ai video exceeded the 300 MB safety limit")
            temp_path.write_bytes(body)
            temp_path.replace(output_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _extract_result(self, payload: dict[str, Any]) -> tuple[str | None, str | None]:
        video_url = self._nested(
            payload,
            ("video_url",),
            ("output_url",),
            ("url",),
            ("data", "video_url"),
            ("data", "output_url"),
            ("data", "url"),
            ("output", "url"),
            ("result", "video_url"),
            ("result", "url"),
        )
        job_id = self._nested(
            payload,
            ("job_id",),
            ("task_id",),
            ("id",),
            ("data", "job_id"),
            ("data", "task_id"),
            ("data", "id"),
        )
        return (
            str(video_url) if isinstance(video_url, str) else None,
            str(job_id) if job_id is not None else None,
        )

    def _poll(
        self,
        initial: dict[str, Any],
        *,
        started: float,
    ) -> tuple[dict[str, Any], int]:
        _, job_id = self._extract_result(initial)
        poll_url = self._nested(
            initial,
            ("poll_url",),
            ("status_url",),
            ("data", "poll_url"),
            ("data", "status_url"),
        )
        if isinstance(poll_url, str):
            urls = [self._absolute_url(poll_url)]
        elif job_id:
            # Free.ai documents webhooks but not a stable polling route. Support the two
            # common routes and only fall back after a 404/405 from the first.
            urls = [
                f"{self.base_url}/v1/jobs/{job_id}",
                f"{self.base_url}/v1/video/status/{job_id}",
            ]
        else:
            raise FreeAIError("Free.ai queued the request without a job id or status URL")

        selected_url: str | None = None
        last_status = 202
        while time.monotonic() - started <= self.timeout_seconds:
            if selected_url is None:
                candidates = urls
            else:
                candidates = [selected_url]
            response: requests.Response | None = None
            for candidate in candidates:
                candidate_response = self.session.get(
                    candidate,
                    headers=self.headers,
                    timeout=(30, 60),
                )
                if candidate_response.status_code in {404, 405} and selected_url is None:
                    continue
                response = candidate_response
                selected_url = candidate
                break
            if response is None:
                raise FreeAIError("Free.ai did not expose a usable status endpoint")
            last_status = response.status_code
            self._raise_for_response(response)
            payload = self._json_or_none(response)
            if payload is None:
                raise FreeAIError("Free.ai status endpoint returned non-JSON data")
            video_url, _ = self._extract_result(payload)
            if video_url:
                return payload, last_status
            status = str(
                self._nested(
                    payload,
                    ("status",),
                    ("state",),
                    ("data", "status"),
                    ("data", "state"),
                )
                or ""
            ).lower()
            if status in {"failed", "error", "cancelled", "canceled"}:
                message = self._nested(
                    payload,
                    ("error", "message"),
                    ("error",),
                    ("message",),
                    ("data", "error"),
                )
                raise FreeAIError(
                    self._sanitize(f"Free.ai render failed: {message or status}"),
                    retriable=False,
                )
            time.sleep(self.poll_interval_seconds)
        raise FreeAIError(
            f"Free.ai render did not finish within {self.timeout_seconds} seconds",
            status_code=last_status,
            retriable=True,
        )

    def generate_video(
        self,
        prompt: str,
        output_path: Path | str,
        *,
        duration: int = 2,
        aspect_ratio: str = "9:16",
        image_url: str | None = None,
        model: str | None = None,
        style: str | None = None,
        negative_prompt: str | None = None,
    ) -> FreeAIVideoResult:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Video prompt cannot be empty")
        if duration < 2 or duration > 6:
            raise ValueError("Free.ai video duration must be between 2 and 6 seconds")
        if aspect_ratio not in {"9:16", "16:9", "1:1", "4:5"}:
            raise ValueError("Unsupported Free.ai aspect ratio")
        if image_url:
            self._safe_download_url(image_url)

        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        }
        if image_url:
            payload["image_url"] = image_url
        if model:
            payload["model"] = model
        if style:
            payload["style"] = style
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        output = Path(output_path)
        started = time.monotonic()
        try:
            response = self.session.post(
                f"{self.base_url}/v1/video/generate/",
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
                timeout=(30, self.timeout_seconds),
            )
        except requests.Timeout as exc:
            raise FreeAIError("Free.ai generation request timed out", retriable=True) from exc
        except requests.RequestException as exc:
            raise FreeAIError(
                self._sanitize(f"Free.ai network error: {exc}"), retriable=True
            ) from exc

        self._raise_for_response(response)
        status_code = response.status_code
        content_type = (response.headers.get("Content-Type") or "").lower()
        job_id: str | None = None
        payload_out: dict[str, Any] = {}

        if "video/" in content_type or "application/octet-stream" in content_type:
            self._write_direct_video(response, output)
        else:
            parsed = self._json_or_none(response)
            if parsed is None:
                raise FreeAIError("Free.ai returned neither JSON nor video data")
            payload_out = parsed
            video_url, job_id = self._extract_result(parsed)
            if not video_url:
                payload_out, status_code = self._poll(parsed, started=started)
                video_url, polled_job_id = self._extract_result(payload_out)
                job_id = job_id or polled_job_id
            if not video_url:
                raise FreeAIError("Free.ai completed without a downloadable video URL")
            self._download(self._absolute_url(video_url), output)

        elapsed = round(time.monotonic() - started, 3)
        token_cost = self._nested(
            payload_out,
            ("token_cost",),
            ("tokens_used",),
            ("usage", "tokens"),
            ("usage", "total_tokens"),
            ("data", "token_cost"),
        )
        remaining = self._nested(
            payload_out,
            ("remaining_tokens",),
            ("tokens_remaining",),
            ("usage", "remaining"),
            ("data", "remaining_tokens"),
        )
        safe_metadata = {
            "provider": "free_ai",
            "model": model or "self-hosted-default",
            "duration_requested": duration,
            "aspect_ratio": aspect_ratio,
            "mode": "image-to-video" if image_url else "text-to-video",
        }
        return FreeAIVideoResult(
            output_path=output,
            elapsed_seconds=elapsed,
            status_code=status_code,
            job_id=job_id,
            token_cost=token_cost if isinstance(token_cost, (int, float)) else None,
            remaining_tokens=remaining if isinstance(remaining, (int, float)) else None,
            metadata=safe_metadata,
        )

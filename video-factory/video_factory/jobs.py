from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATES = {"queued", "submitted", "running", "done", "failed", "blocked"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SceneJob:
    prompt: str
    negative_prompt: str = (
        "static image, slideshow, zoom-only, frozen subject, morphing, extra limbs, "
        "deformed anatomy, flicker, jitter, text, logo, watermark"
    )
    image_url: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"
    attempt: int = 0
    max_attempts: int = 2
    seed: int = 1987
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    provider: str | None = None
    provider_account: str | None = None
    provider_job_id: str | None = None
    output_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.status not in VALID_STATES:
            raise ValueError(f"Invalid job state: {self.status}")
        if not self.prompt.strip():
            raise ValueError("Prompt must not be empty")
        if self.attempt < 0 or self.max_attempts < 1:
            raise ValueError("Invalid attempt counters")

    def save(self, path: Path) -> None:
        self.validate()
        self.updated_at = utc_now()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "SceneJob":
        data = json.loads(path.read_text())
        job = cls(**data)
        job.validate()
        return job

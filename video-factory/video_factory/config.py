from __future__ import annotations

import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    load_dotenv(ROOT / ".env")
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def required_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing secret {name}. Put it in .env locally or in your host's secret manager. "
            "Never put it in Git, source code, or chat."
        )
    return value

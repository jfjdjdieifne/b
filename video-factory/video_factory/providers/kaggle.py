from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from video_factory.config import ROOT
from video_factory.jobs import SceneJob


_ACCOUNT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_INDEXED_CREDENTIAL_RE = re.compile(r"KAGGLE_(?:USERNAME|API_TOKEN)_(\d+)$")


@dataclass(frozen=True)
class KaggleAccount:
    """One Kaggle account. The token is never serialized by the account pool."""

    id: str
    username: str
    api_token: str = field(repr=False)
    kernel_slug: str = "wan-video-worker"


def _account_from_values(
    *,
    account_id: str,
    username: str,
    api_token: str,
    kernel_slug: str,
    source: str,
) -> KaggleAccount:
    account_id = account_id.strip()
    username = username.strip()
    api_token = api_token.strip()
    kernel_slug = kernel_slug.strip()

    if not _ACCOUNT_ID_RE.fullmatch(account_id):
        raise RuntimeError(
            f"Invalid Kaggle account id in {source}. Use 1-64 letters, numbers, '.', '_' or '-'."
        )
    if not username or not api_token:
        raise RuntimeError(f"Missing Kaggle username or API token in {source}")
    if not kernel_slug or "/" in kernel_slug:
        raise RuntimeError(f"Invalid Kaggle kernel slug in {source}")
    return KaggleAccount(account_id, username, api_token, kernel_slug)


def _validate_accounts(accounts: list[KaggleAccount]) -> list[KaggleAccount]:
    if not accounts:
        raise RuntimeError(
            "No Kaggle credentials configured. Add numbered KAGGLE_USERNAME_1 / "
            "KAGGLE_API_TOKEN_1 secrets (recommended), KAGGLE_ACCOUNTS_JSON, or the "
            "legacy single-account KAGGLE_USERNAME / KAGGLE_API_TOKEN pair."
        )

    ids: set[str] = set()
    usernames: set[str] = set()
    for account in accounts:
        if account.id in ids:
            raise RuntimeError(f"Duplicate Kaggle account id: {account.id}")
        if account.username.lower() in usernames:
            raise RuntimeError(
                f"Kaggle username {account.username!r} is configured more than once. "
                "Use one credential per account."
            )
        ids.add(account.id)
        usernames.add(account.username.lower())
    return accounts


def load_kaggle_accounts(config: dict[str, Any]) -> list[KaggleAccount]:
    """Load an ordered account pool without ever writing tokens to disk.

    Precedence is:
    1. Numbered environment pairs (KAGGLE_USERNAME_1, KAGGLE_API_TOKEN_1, ...)
    2. KAGGLE_ACCOUNTS_JSON
    3. The original single-account environment pair

    Numbered credentials are preferred on GitHub because every token remains an
    individual GitHub Secret and is independently masked in workflow logs.
    """

    default_slug = os.getenv(
        "KAGGLE_KERNEL_SLUG", config["kaggle"].get("kernel_slug", "wan-video-worker")
    ).strip()

    indexes = sorted(
        {
            int(match.group(1))
            for key, value in os.environ.items()
            if value.strip() and (match := _INDEXED_CREDENTIAL_RE.fullmatch(key))
        }
    )
    if indexes:
        accounts: list[KaggleAccount] = []
        for index in indexes:
            username = os.getenv(f"KAGGLE_USERNAME_{index}", "")
            token = os.getenv(f"KAGGLE_API_TOKEN_{index}", "")
            if not username.strip() or not token.strip():
                raise RuntimeError(
                    f"Kaggle credential slot {index} is incomplete. Set both "
                    f"KAGGLE_USERNAME_{index} and KAGGLE_API_TOKEN_{index}."
                )
            accounts.append(
                _account_from_values(
                    account_id=os.getenv(f"KAGGLE_ACCOUNT_ID_{index}", f"account-{index}"),
                    username=username,
                    api_token=token,
                    kernel_slug=os.getenv(f"KAGGLE_KERNEL_SLUG_{index}", default_slug),
                    source=f"numbered Kaggle credential slot {index}",
                )
            )
        return _validate_accounts(accounts)

    raw_accounts = os.getenv("KAGGLE_ACCOUNTS_JSON", "").strip()
    if raw_accounts:
        try:
            payload = json.loads(raw_accounts)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "KAGGLE_ACCOUNTS_JSON is not valid JSON. Keep the whole JSON value inside the secret."
            ) from exc
        if isinstance(payload, dict):
            payload = payload.get("accounts")
        if not isinstance(payload, list) or not payload:
            raise RuntimeError("KAGGLE_ACCOUNTS_JSON must contain a non-empty JSON array")

        accounts = []
        for position, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise RuntimeError(f"KAGGLE_ACCOUNTS_JSON item {position} must be an object")
            accounts.append(
                _account_from_values(
                    account_id=str(item.get("id") or f"account-{position}"),
                    username=str(item.get("username") or ""),
                    api_token=str(item.get("api_token") or item.get("token") or ""),
                    kernel_slug=str(item.get("kernel_slug") or default_slug),
                    source=f"KAGGLE_ACCOUNTS_JSON item {position}",
                )
            )
        return _validate_accounts(accounts)

    username = os.getenv("KAGGLE_USERNAME", "")
    token = os.getenv("KAGGLE_API_TOKEN", "")
    if bool(username.strip()) != bool(token.strip()):
        raise RuntimeError(
            "The legacy Kaggle credential is incomplete. Set both KAGGLE_USERNAME and "
            "KAGGLE_API_TOKEN."
        )
    account = _account_from_values(
        account_id=os.getenv("KAGGLE_ACCOUNT_ID", "primary"),
        username=username,
        api_token=token,
        kernel_slug=default_slug,
        source="legacy Kaggle credential",
    )
    return _validate_accounts([account])


class KaggleCommandError(RuntimeError):
    """A sanitized Kaggle CLI failure; credentials are removed from its message."""

    ACCOUNT_FAILURE_MARKERS = (
        "401",
        "403",
        "unauthorized",
        "forbidden",
        "authentication",
        "credential",
        "api token",
        "permission denied",
        "access denied",
        "not found",
        "quota",
        "limit exceeded",
        "maximum number",
        "gpu limit",
        "gpu session",
        "accelerator is not available",
    )

    def __init__(
        self,
        command: list[str],
        returncode: int | None,
        output: str,
        *,
        timed_out: bool = False,
    ) -> None:
        self.command = command
        self.returncode = returncode
        self.output = output.strip()[-1600:]
        self.timed_out = timed_out
        command_name = " ".join(command[:3])
        if timed_out:
            message = f"Kaggle command timed out: {command_name}"
        else:
            message = f"Kaggle command failed ({returncode}): {command_name}"
        if self.output:
            message += f" — {self.output}"
        super().__init__(message)

    @property
    def is_account_failure(self) -> bool:
        if self.timed_out:
            return False
        text = f"{self}\n{self.output}".lower()
        return any(marker in text for marker in self.ACCOUNT_FAILURE_MARKERS)


class KaggleAccountPool:
    """Persistent round-robin selection with a cooldown for unhealthy accounts."""

    def __init__(
        self,
        accounts: list[KaggleAccount],
        state_path: Path,
        cooldown_minutes: int = 60,
    ) -> None:
        self.accounts = accounts
        self.state_path = state_path
        self.cooldown_minutes = max(0, int(cooldown_minutes))
        self.state: dict[str, Any] = {"version": 1, "next_account_id": None, "accounts": {}}
        if state_path.exists():
            try:
                loaded = json.loads(state_path.read_text())
                if isinstance(loaded, dict):
                    self.state.update(loaded)
                    if not isinstance(self.state.get("accounts"), dict):
                        self.state["accounts"] = {}
            except (OSError, json.JSONDecodeError):
                # A damaged state file must not expose or disable credentials.
                pass

    def by_id(self, account_id: str | None) -> KaggleAccount | None:
        return next((account for account in self.accounts if account.id == account_id), None)

    def by_username(self, username: str | None) -> KaggleAccount | None:
        if not username:
            return None
        return next(
            (account for account in self.accounts if account.username.lower() == username.lower()),
            None,
        )

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None

    def candidates(self, now: datetime | None = None) -> list[KaggleAccount]:
        now = now or datetime.now(timezone.utc)
        if not self.accounts:
            return []
        next_id = self.state.get("next_account_id")
        start = next(
            (index for index, account in enumerate(self.accounts) if account.id == next_id),
            0,
        )
        ordered = self.accounts[start:] + self.accounts[:start]
        available: list[KaggleAccount] = []
        account_state = self.state.get("accounts", {})
        for account in ordered:
            cooldown_until = self._parse_time(account_state.get(account.id, {}).get("cooldown_until"))
            if cooldown_until is None or cooldown_until <= now:
                available.append(account)
        return available

    def next_available_at(self, now: datetime | None = None) -> datetime | None:
        now = now or datetime.now(timezone.utc)
        future = []
        for account in self.accounts:
            value = self.state.get("accounts", {}).get(account.id, {}).get("cooldown_until")
            parsed = self._parse_time(value)
            if parsed and parsed > now:
                future.append(parsed)
        return min(future) if future else None

    def _advance_after(self, account: KaggleAccount) -> None:
        index = self.accounts.index(account)
        self.state["next_account_id"] = self.accounts[(index + 1) % len(self.accounts)].id

    def mark_success(self, account: KaggleAccount) -> None:
        now = datetime.now(timezone.utc).isoformat()
        entry = self.state.setdefault("accounts", {}).setdefault(account.id, {})
        entry.update(
            {
                "failures": 0,
                "cooldown_until": None,
                "last_error": None,
                "last_submission_at": now,
            }
        )
        self._advance_after(account)
        self.save()

    def mark_failure(self, account: KaggleAccount, error: str) -> None:
        now = datetime.now(timezone.utc)
        entry = self.state.setdefault("accounts", {}).setdefault(account.id, {})
        entry.update(
            {
                "failures": int(entry.get("failures", 0)) + 1,
                "cooldown_until": (now + timedelta(minutes=self.cooldown_minutes)).isoformat(),
                "last_error": error[-1000:],
                "last_failure_at": now.isoformat(),
            }
        )
        self._advance_after(account)
        self.save()

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, ensure_ascii=False))
        tmp.replace(self.state_path)


class KaggleProvider:
    """One authorized Kaggle account, controlled through Kaggle's official CLI."""

    def __init__(self, config: dict[str, Any], account: KaggleAccount):
        self.config = config
        self.account = account
        self.username = account.username
        self.slug = account.kernel_slug
        self.kernel_id = f"{self.username}/{self.slug}"
        self.worker_dir = ROOT / "workers" / "kaggle"
        self.runtime_dir = ROOT / ".work" / "kaggle" / account.id
        self.env = os.environ.copy()
        # Force this subprocess to use exactly the selected account.
        self.env.pop("KAGGLE_KEY", None)
        self.env["KAGGLE_API_TOKEN"] = account.api_token
        self.env["KAGGLE_USERNAME"] = account.username

    def _sanitize(self, text: str) -> str:
        return text.replace(self.account.api_token, "***")

    def _run(self, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                args,
                env=self.env,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = self._sanitize(f"{exc.stdout or ''}\n{exc.stderr or ''}")
            raise KaggleCommandError(args, None, output, timed_out=True) from exc
        if result.returncode != 0:
            output = self._sanitize(f"{result.stdout}\n{result.stderr}")
            raise KaggleCommandError(args, result.returncode, output)
        return result

    def submit(self, job: SceneJob) -> str:
        if self.runtime_dir.exists():
            shutil.rmtree(self.runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.worker_dir / "kernel.py", self.runtime_dir / "kernel.py")

        (self.runtime_dir / "job_payload.json").write_text(
            json.dumps(job.__dict__, ensure_ascii=False, indent=2)
        )
        metadata = {
            "id": self.kernel_id,
            "title": "Wan Video Worker",
            "code_file": "kernel.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "dataset_sources": [],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
        }
        (self.runtime_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
        self._run(
            [
                "kaggle",
                "kernels",
                "push",
                "-p",
                str(self.runtime_dir),
                "--accelerator",
                self.config["kaggle"]["accelerator"],
                "--timeout",
                "300",
            ],
            timeout=360,
        )
        return self.kernel_id

    def status(self) -> str:
        result = self._run(["kaggle", "kernels", "status", self.kernel_id])
        text = (result.stdout + "\n" + result.stderr).lower()
        if "complete" in text:
            return "complete"
        if "error" in text or "cancel" in text or "failed" in text:
            return "failed"
        if "running" in text:
            return "running"
        return "pending"

    def collect(self, job: SceneJob) -> Path:
        out_dir = ROOT / ".work" / "downloads" / job.id
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self._run(
            ["kaggle", "kernels", "output", self.kernel_id, "-p", str(out_dir), "--force"],
            timeout=900,
        )
        result_files = list(out_dir.rglob("result.json"))
        if result_files:
            result = json.loads(result_files[0].read_text())
            if result.get("status") != "done":
                raise RuntimeError(result.get("error", "Kaggle worker failed"))
        videos = sorted(out_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not videos:
            raise RuntimeError("Kaggle completed but returned no MP4")
        final_dir = ROOT / "outputs" / job.id
        final_dir.mkdir(parents=True, exist_ok=True)
        final = final_dir / "scene.mp4"
        shutil.copy2(videos[0], final)
        return final

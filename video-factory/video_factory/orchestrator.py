from __future__ import annotations

import logging
from pathlib import Path

from video_factory.config import ROOT, load_config
from video_factory.jobs import SceneJob, utc_now
from video_factory.providers.kaggle import (
    KaggleAccount,
    KaggleAccountPool,
    KaggleCommandError,
    KaggleProvider,
    load_kaggle_accounts,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("video-factory")


def job_files() -> list[Path]:
    return sorted((ROOT / "jobs").glob("*.json"))


def _safe_error(exc: Exception, accounts: list[KaggleAccount]) -> str:
    text = str(exc)
    for account in accounts:
        text = text.replace(account.api_token, "***")
    return text[-1600:]


def _record_event(
    job: SceneJob,
    event: str,
    *,
    account_id: str | None = None,
    error: str | None = None,
) -> None:
    events = job.metadata.setdefault("kaggle_account_events", [])
    if not isinstance(events, list):
        events = []
        job.metadata["kaggle_account_events"] = events
    item = {"at": utc_now(), "event": event}
    if account_id:
        item["account_id"] = account_id
    if error:
        item["error"] = error[-1000:]
    events.append(item)
    del events[:-30]


def _clear_assignment(job: SceneJob) -> None:
    job.provider_account = None
    job.provider_job_id = None


def _retry_or_finish(job: SceneJob, reason: str) -> None:
    """Retry a submitted render on the next account, unless its render limit was reached."""

    job.error = reason
    job.metadata.pop("kaggle_status_errors", None)
    if job.attempt < job.max_attempts:
        job.status = "queued"
        _clear_assignment(job)
    else:
        job.status = "failed"


def _account_for_active_job(
    job: SceneJob, pool: KaggleAccountPool
) -> KaggleAccount | None:
    account = pool.by_id(job.provider_account)
    if account:
        return account

    # Backward compatibility for jobs submitted by the original single-account MVP.
    if job.provider_job_id and "/" in job.provider_job_id:
        username = job.provider_job_id.split("/", 1)[0]
        account = pool.by_username(username)
        if account:
            job.provider_account = account.id
            return account
    if len(pool.accounts) == 1:
        job.provider_account = pool.accounts[0].id
        return pool.accounts[0]
    return None


def _handle_active(
    path: Path,
    job: SceneJob,
    config: dict,
    pool: KaggleAccountPool,
    accounts: list[KaggleAccount],
) -> int:
    account = _account_for_active_job(job, pool)
    if account is None:
        reason = (
            "The Kaggle account that owns this active kernel is not configured anymore; "
            "the job will be retried with another configured account."
        )
        _record_event(job, "active_account_missing", error=reason)
        _retry_or_finish(job, reason)
        job.save(path)
        return 0

    provider = KaggleProvider(config, account)
    try:
        state = provider.status()
        job.metadata.pop("kaggle_status_errors", None)
    except Exception as exc:
        reason = _safe_error(exc, accounts)
        status_errors = int(job.metadata.get("kaggle_status_errors", 0)) + 1
        job.metadata["kaggle_status_errors"] = status_errors
        is_account_failure = isinstance(exc, KaggleCommandError) and exc.is_account_failure
        retry_limit = int(config["kaggle"].get("status_error_retries", 3))

        if is_account_failure or status_errors >= retry_limit:
            pool.mark_failure(account, reason)
            _record_event(job, "status_account_failure", account_id=account.id, error=reason)
            _retry_or_finish(job, reason)
        else:
            # Do not duplicate a possibly-running render after one temporary network/API error.
            job.status = "running"
            job.error = (
                f"Temporary Kaggle status error ({status_errors}/{retry_limit}); will check again: "
                f"{reason}"
            )
            _record_event(job, "temporary_status_error", account_id=account.id, error=reason)
        job.save(path)
        return 0

    LOG.info("Job %s on account %s provider status: %s", job.id, account.id, state)
    if state in {"pending", "running"}:
        job.status = "running"
        job.error = None
        job.save(path)
        return 0

    if state == "complete":
        try:
            output = provider.collect(job)
            job.status = "done"
            job.output_path = str(output.relative_to(ROOT))
            job.error = None
            _record_event(job, "completed", account_id=account.id)
        except Exception as exc:
            reason = _safe_error(exc, accounts)
            if isinstance(exc, KaggleCommandError) and exc.is_account_failure:
                pool.mark_failure(account, reason)
            _record_event(job, "collection_failed", account_id=account.id, error=reason)
            _retry_or_finish(job, reason)
        job.save(path)
        return 0

    reason = f"Kaggle render failed on {account.id}"
    _record_event(job, "render_failed", account_id=account.id, error=reason)
    _retry_or_finish(job, reason)
    job.save(path)
    return 0


def _handle_queued(
    path: Path,
    job: SceneJob,
    config: dict,
    pool: KaggleAccountPool,
    accounts: list[KaggleAccount],
) -> int:
    if job.attempt >= job.max_attempts:
        job.status = "blocked"
        job.error = "Render retry limit reached"
        job.save(path)
        return 0

    candidates = pool.candidates()
    if not candidates:
        next_time = pool.next_available_at()
        suffix = f" Next retry after {next_time.isoformat()}." if next_time else ""
        job.status = "queued"
        job.error = "All configured Kaggle accounts are cooling down." + suffix
        job.save(path)
        LOG.warning("Job %s is waiting: %s", job.id, job.error)
        return 0

    # One render attempt can try every currently healthy credential. Failed credential
    # submissions do not consume the render retry budget because no GPU job was launched.
    job.attempt += 1
    job.provider = "kaggle"
    submission_errors: list[str] = []

    for account in candidates:
        job.provider_account = account.id
        job.provider_job_id = None
        provider = KaggleProvider(config, account)
        try:
            provider_job_id = provider.submit(job)
        except Exception as exc:
            reason = _safe_error(exc, accounts)
            submission_errors.append(f"{account.id}: {reason}")
            pool.mark_failure(account, reason)
            _record_event(job, "submission_failed", account_id=account.id, error=reason)
            LOG.warning("Kaggle account %s rejected job %s: %s", account.id, job.id, reason)
            continue

        job.provider_job_id = provider_job_id
        job.status = "submitted"
        job.error = None
        _record_event(job, "submitted", account_id=account.id)
        job.save(path)
        pool.mark_success(account)
        LOG.info("Submitted job %s through Kaggle account %s", job.id, account.id)
        return 0

    # Every credential failed before a kernel was accepted. Restore the render-attempt
    # counter and leave the job queued for a later tick or repaired credential.
    job.attempt -= 1
    job.status = "queued"
    _clear_assignment(job)
    summary = " | ".join(submission_errors)
    job.error = f"No Kaggle account accepted the submission: {summary}"[-2000:]
    job.save(path)
    return 0


def run_once() -> int:
    config = load_config()
    jobs = [(path, SceneJob.load(path)) for path in job_files()]

    active = [(path, job) for path, job in jobs if job.status in {"submitted", "running"}]
    queued = [(path, job) for path, job in jobs if job.status == "queued"]
    if not active and not queued:
        LOG.info("No active or queued jobs")
        return 0

    accounts = load_kaggle_accounts(config)
    pool = KaggleAccountPool(
        accounts,
        ROOT / "state" / "kaggle_accounts.json",
        cooldown_minutes=int(config["kaggle"].get("account_cooldown_minutes", 60)),
    )

    if active:
        path, job = active[0]
        return _handle_active(path, job, config, pool, accounts)

    path, job = queued[0]
    return _handle_queued(path, job, config, pool, accounts)


if __name__ == "__main__":
    raise SystemExit(run_once())

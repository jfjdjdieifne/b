from pathlib import Path

from video_factory import orchestrator
from video_factory.jobs import SceneJob
from video_factory.providers.kaggle import KaggleAccount, KaggleAccountPool


CONFIG = {
    "kaggle": {
        "kernel_slug": "wan-video-worker",
        "accelerator": "NvidiaTeslaT4",
        "account_cooldown_minutes": 60,
    }
}


def test_submit_fails_over_without_consuming_extra_render_attempt(monkeypatch, tmp_path: Path):
    accounts = [
        KaggleAccount("primary", "user-a", "secret-a"),
        KaggleAccount("backup", "user-b", "secret-b"),
    ]
    pool = KaggleAccountPool(accounts, tmp_path / "state.json", cooldown_minutes=60)

    class FakeProvider:
        def __init__(self, config, account):
            self.account = account

        def submit(self, job):
            if self.account.id == "primary":
                raise RuntimeError("credential secret-a is invalid")
            return f"{self.account.username}/wan-video-worker"

    monkeypatch.setattr(orchestrator, "KaggleProvider", FakeProvider)
    job = SceneJob(prompt="A moving forest scene")
    path = tmp_path / "job.json"

    result = orchestrator._handle_queued(path, job, CONFIG, pool, accounts)
    saved = SceneJob.load(path)

    assert result == 0
    assert saved.status == "submitted"
    assert saved.attempt == 1
    assert saved.provider_account == "backup"
    assert saved.provider_job_id == "user-b/wan-video-worker"
    assert "secret-a" not in path.read_text()
    assert [event["event"] for event in saved.metadata["kaggle_account_events"]] == [
        "submission_failed",
        "submitted",
    ]

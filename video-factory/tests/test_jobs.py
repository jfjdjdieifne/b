from pathlib import Path
from video_factory.jobs import SceneJob


def test_job_roundtrip(tmp_path: Path):
    job = SceneJob(prompt="A door opens in a misty forest")
    path = tmp_path / "job.json"
    job.save(path)
    loaded = SceneJob.load(path)
    assert loaded.id == job.id
    assert loaded.status == "queued"

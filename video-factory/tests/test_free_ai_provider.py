from __future__ import annotations

from pathlib import Path

import pytest

from video_factory.providers.free_ai import FreeAIError, FreeAIProvider


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b"", headers=None, reason=""):
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.headers = headers or {"Content-Type": "application/json"}
        self.reason = reason

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def iter_content(self, chunk_size=1024):
        del chunk_size
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, post_response, get_responses):
        self.post_response = post_response
        self.get_responses = list(get_responses)
        self.posts = []
        self.gets = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.post_response

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if not self.get_responses:
            raise AssertionError("Unexpected GET")
        return self.get_responses.pop(0)


def test_generate_video_downloads_immediate_result_without_leaking_key(tmp_path: Path):
    video = b"0" * 2048
    session = FakeSession(
        FakeResponse(payload={"video_url": "https://cdn.example/scene.mp4", "token_cost": 5000}),
        [FakeResponse(content=video, headers={"Content-Type": "video/mp4"})],
    )
    provider = FreeAIProvider(api_key="sk-free-super-secret", session=session)
    output = tmp_path / "scene.mp4"

    result = provider.generate_video("A paper boat moving on rainwater", output)

    assert output.read_bytes() == video
    assert result.token_cost == 5000
    assert result.metadata["mode"] == "text-to-video"
    assert "sk-free-super-secret" not in repr(result)
    posted = session.posts[0][1]
    assert posted["headers"]["Authorization"] == "Bearer sk-free-super-secret"
    assert "Authorization" not in posted["json"]


def test_generate_video_polls_explicit_status_url(tmp_path: Path):
    video = b"1" * 2048
    session = FakeSession(
        FakeResponse(
            status_code=202,
            payload={"job_id": "job-1", "status_url": "/v1/jobs/job-1"},
        ),
        [
            FakeResponse(payload={"status": "running", "job_id": "job-1"}),
            FakeResponse(
                payload={
                    "status": "complete",
                    "job_id": "job-1",
                    "video_url": "https://cdn.example/result.mp4",
                    "remaining_tokens": 25000,
                }
            ),
            FakeResponse(content=video, headers={"Content-Type": "video/mp4"}),
        ],
    )
    provider = FreeAIProvider(
        api_key="sk-free-test",
        session=session,
        poll_interval_seconds=0.001,
    )

    result = provider.generate_video("Cloud shadows cross a mountain", tmp_path / "scene.mp4")

    assert result.job_id == "job-1"
    assert result.remaining_tokens == 25000
    assert len(session.gets) == 3


def test_http_error_is_sanitized_and_classified_retriable(tmp_path: Path):
    key = "sk-free-do-not-leak"
    session = FakeSession(
        FakeResponse(
            status_code=429,
            payload={"error": {"message": f"quota exhausted for {key}", "code": "quota"}},
        ),
        [],
    )
    provider = FreeAIProvider(api_key=key, session=session)

    with pytest.raises(FreeAIError) as raised:
        provider.generate_video("A moving subject", tmp_path / "scene.mp4")

    assert raised.value.retriable is True
    assert raised.value.status_code == 429
    assert key not in str(raised.value)
    assert "***" in str(raised.value)


def test_rejects_invalid_input_before_network(tmp_path: Path):
    session = FakeSession(FakeResponse(), [])
    provider = FreeAIProvider(api_key="sk-free-test", session=session)

    with pytest.raises(ValueError):
        provider.generate_video("", tmp_path / "scene.mp4")
    with pytest.raises(ValueError):
        provider.generate_video("x", tmp_path / "scene.mp4", duration=7)
    with pytest.raises(ValueError):
        provider.generate_video("x", tmp_path / "scene.mp4", aspect_ratio="3:2")
    with pytest.raises(FreeAIError):
        provider.generate_video(
            "x", tmp_path / "scene.mp4", image_url="http://insecure.example/image.jpg"
        )

    assert not session.posts

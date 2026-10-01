from __future__ import annotations

from pathlib import Path

import pytest

from video_factory.providers.hf_spaces import HFSpacesError, HFSpacesWanProvider


class FakeClient:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.call = None

    def predict(self, *args, **kwargs):
        self.call = (args, kwargs)
        if self.error:
            raise self.error
        return self.result


def provider_for(fake: FakeClient, *, token="secret-token") -> HFSpacesWanProvider:
    def factory(space_id, **kwargs):
        fake.factory_call = (space_id, kwargs)
        return fake

    return HFSpacesWanProvider(
        token=token,
        client_factory=factory,
        file_handler=lambda path: {"path": path, "meta": {"_type": "gradio.FileData"}},
    )


def test_t2v_copies_video_and_forwards_auth(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video" * 500)
    fake = FakeClient(({"video": str(source), "subtitles": None}, 123))
    provider = provider_for(fake)

    result = provider.generate_video(
        "rainy red leaf",
        tmp_path / "out.mp4",
        duration_seconds=1,
        steps=2,
        seed=123,
    )

    assert result.output_path.read_bytes() == source.read_bytes()
    assert result.mode == "text-to-video"
    assert result.seed == 123
    assert fake.factory_call == (
        "Upsampler/wan-2-2-5b-video",
        {"verbose": False, "hf_token": "secret-token"},
    )
    args, kwargs = fake.call
    assert args[0] is None
    assert args[1] == "rainy red leaf"
    assert args[2:4] == (832, 480)
    assert "watermark" in args[4]
    assert kwargs == {"api_name": "/generate_video"}


def test_i2v_uses_gradio_handle_file(tmp_path: Path):
    image = tmp_path / "input.png"
    image.write_bytes(b"fake image")
    source = tmp_path / "generated.mp4"
    source.write_bytes(b"mp4" * 500)
    fake = FakeClient(({"video": {"path": str(source)}}, 44))
    provider = provider_for(fake)

    result = provider.generate_video(
        "animate it",
        tmp_path / "out.mp4",
        input_image=image,
        duration_seconds=2,
        steps=4,
    )

    args, _ = fake.call
    assert args[0]["path"] == str(image)
    assert result.mode == "image-to-video"


def test_quota_error_is_sanitized_and_marked_retriable(tmp_path: Path):
    fake = FakeClient(error=RuntimeError("secret-token exceeded ZeroGPU quota"))
    provider = provider_for(fake)

    with pytest.raises(HFSpacesError) as raised:
        provider.generate_video("a scene", tmp_path / "out.mp4", duration_seconds=1)

    assert raised.value.quota is True
    assert raised.value.retriable is True
    assert "secret-token" not in str(raised.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 481},
        {"width": 128},
        {"duration_seconds": 9},
        {"steps": 0},
    ],
)
def test_rejects_invalid_space_parameters(tmp_path: Path, kwargs):
    fake = FakeClient()
    provider = provider_for(fake)
    with pytest.raises(ValueError):
        provider.generate_video("scene", tmp_path / "out.mp4", **kwargs)

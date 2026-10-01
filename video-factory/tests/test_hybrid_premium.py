from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_factory.config import ROOT
from video_factory.hybrid_premium.plan import EditPlan, PlanValidationError
from video_factory.hybrid_premium.qa import analyze_video
from video_factory.hybrid_premium.renderer import build_command, build_filtergraph

EXAMPLE = ROOT / "examples" / "hybrid_premium" / "ancient_mystery"
PLAN = EXAMPLE / "edit_plan.json"


def test_reference_plan_is_a_valid_true_motion_edit() -> None:
    plan = EditPlan.load(PLAN)
    assert plan.duration == 15
    assert len(plan.shots) == 15
    assert len({shot.source for shot in plan.shots}) == 15
    assert all(Path(shot.source).suffix.lower() in {".mp4", ".webm", ".mov", ".mkv", ".ogv"} for shot in plan.shots)
    assert sum(shot.duration for shot in plan.shots) == pytest.approx(15.0)
    assert plan.metadata["publishing_mode"] == "draft_only"


def test_still_image_cannot_be_declared_as_motion(tmp_path: Path) -> None:
    image = tmp_path / "still.png"
    image.write_bytes(b"png")
    payload = json.loads(PLAN.read_text(encoding="utf-8"))
    payload["shots"][0]["source"] = "still.png"
    broken = tmp_path / "edit_plan.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PlanValidationError, match="still image as motion"):
        EditPlan.load(broken)


def test_renderer_builds_multi_source_captioned_stereo_graph(tmp_path: Path) -> None:
    plan = EditPlan.load(PLAN)
    graph, has_audio = build_filtergraph(plan, len(plan.shots), len(plan.shots) + 1)
    assert has_audio is True
    assert "concat=n=15" in graph
    assert "subtitles=" in graph
    assert "pan=stereo" in graph
    assert "loudnorm=I=-14" in graph
    command, _ = build_command(plan, tmp_path / "draft.mp4")
    assert "libx264" in command
    assert command[-1].endswith("draft.mp4")


def test_bundled_reference_master_passes_automated_qa() -> None:
    plan = EditPlan.load(PLAN)
    metrics = analyze_video(
        EXAMPLE / "sample_preview.mp4",
        expected_duration=plan.duration,
        expected_width=540,
        expected_height=960,
        expected_fps=plan.fps,
    )
    assert metrics["pass"] is True
    assert metrics["frame_count"] == 450
    assert metrics["longest_low_motion_seconds"] < 0.5
    assert metrics["true_peak_dbfs"] <= -1.0

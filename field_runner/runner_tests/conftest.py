"""Shared paths/fixtures for runner tests (outside trading_project)."""

from __future__ import annotations

import os
import sys

import pytest

FIELD_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_ROOT = os.path.dirname(FIELD_RUNNER_DIR)
for _p in (PACKAGE_ROOT, os.path.join(PACKAGE_ROOT, "project", "trading_project", "src"),
           os.path.join(PACKAGE_ROOT, "trading_project", "src")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from field_runner import fixtures as fixture_factory  # noqa: E402


@pytest.fixture()
def fixture_artifacts(tmp_path):
    out = fixture_factory.write_fixture(str(tmp_path), n_minutes=240, ambiguous_minute=40)
    out["aggtrades_path"] = None
    return out


@pytest.fixture(scope="session")
def runner_config():
    from field_runner.pipeline import FieldRunConfig

    return FieldRunConfig(
        swing_quantile=0.5,
        swing_prior_continuation_reversals=(0.005,),
        sessions=[{"name": "London", "timezone": "Europe/London",
                   "start_local": "08:00", "end_local": "09:00"}],
        sample_size=12,
        htf_durations=("1h",),
        symbol="FIXTURESYM",
        year_month="2026-05",
        period_start_utc="2026-05-01T00:00:00Z",
        period_end_utc="2026-05-01T04:00:00Z",
    )

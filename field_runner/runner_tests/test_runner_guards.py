"""Guards: no engine re-implementation inside the runner (AST), and the CLOSED
project tree (MANIFEST) is untouched by field tooling."""

from __future__ import annotations

import ast
import os
import re

import pytest

FIELD_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_ROOT = os.path.dirname(FIELD_RUNNER_DIR)

CLOSED_ENGINE_CLASS_NAMES = {
    "DynamicVolatilityEngine", "CausalSessionContextEngine", "CausalAdaptiveSwingDetector",
    "EmpiricalConfirmationPolicy", "ConfirmedSwingSequenceEngine", "CausalStructuralBreakEngine",
    "CausalLiquidityMapEngine", "CausalVolumeDeltaEngine", "CausalAbsorptionEvidenceEngine",
    "CausalOrderBlockEngine", "CausalFVGEngine", "CausalDealingRangeEngine",
    "CausalHTFAggregator", "CausalEvidenceVectorEngine", "CausalMarketNarrativeEngine",
    "MarketObservationTimeline", "TimeIndexedTimelineAdapter", "PositionalTimelineAdapter",
    "TrajectoryProjector", "AsOfVisibilityProjector",
}
_ENGINE_NAME_RE = re.compile(r"(Causal|Confirmed|Dynamic|Empirical|.*Engine|.*Detector|.*Aggregator)$")


def _runner_python_files():
    files = []
    for root, dirs, names in os.walk(FIELD_RUNNER_DIR):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".pytest_cache", "runner_tests"}]
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(root, name))
    return sorted(files)


def test_ast_guard_no_engine_reimplementation():
    """The runner must never DEFINE engine classes or an analyze() core."""
    violations = []
    for path in _runner_python_files():
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name in CLOSED_ENGINE_CLASS_NAMES or _ENGINE_NAME_RE.search(node.name):
                    violations.append((path, node.name))
            if isinstance(node, ast.FunctionDef) and node.name == "analyze":
                violations.append((path, "def analyze"))
    assert violations == [], violations


def test_ast_guard_engines_imported_from_closed_package_only():
    """Any trading_system usage must be import-based (public API), not a copy."""
    for path in _runner_python_files():
        src = open(path, encoding="utf-8").read()
        assert "def _analyze_actual" not in src
        assert "def _analyze_proxy" not in src
        assert "_EmpiricalRuntime" not in src
        assert "finalize_continuation_episode" not in src or "trading_system" in src


def test_closed_project_manifest_untouched():
    """FAIL-CLOSED manifest gate pinning the CLEAN POST-CLOSURE baseline.

    Owner-authorized unified performance closure (EXACT PERFORMANCE V2 +
    TEST-SUITE ACCELERATION) legitimately superseded the former transitional
    baseline (183 lines / 173 OK / 10 accepted stale). The guard now certifies
    the official clean post-closure baseline and allows NO stale exceptions:

      A) MANIFEST.sha256 digest must equal the pinned post-closure digest;
      B) every MANIFEST entry must validate: 185 OK / 0 stale / 0 missing;
      C) the 10 accepted performance artifacts remain independently pinned
         with their accepted digests — historical evidence kept as extra
         protection, never as a permitted-stale allowance.

    The former `patched_seal` stale permission is retired. If any of the ten
    files (or any other MANIFEST entry) becomes stale again, this gate fails
    closed.
    """
    from field_runner.runner_btc_may_2026 import verify_manifest, _sha256_file

    project_root = None
    for cand in (os.path.join(PACKAGE_ROOT, "project", "trading_project"),
                 os.path.join(PACKAGE_ROOT, "trading_project")):
        if os.path.isfile(os.path.join(cand, "MANIFEST.sha256")):
            project_root = cand
            break
    assert project_root is not None, "trading_project not found"

    closed_manifest_sha256 = (
        "12c66abe6f18300f2e00cb5c4befeafe1e3dc67c2ca50bc71db74db9ba8b367d"
    )
    accepted_artifact_seal = {
        "src/trading_system/core/causal_percentile.py":
            "1543794f173e1552435d2d37fd53fa9f7b67ba3c2dfb7c6ddc001f971f0f8654",
        "src/trading_system/zones/fvg.py":
            "1df18e553557132788024168ed8b384c338476271cf08c436c23bc01d31dcd4b",
        "src/trading_system/decision/narrative.py":
            "407c4d2f8be00cf66e22232b0da3d88de80a8068dad066aa7ed6a902b0dd24f9",
        "src/trading_system/research/hashing.py":
            "f2a64c8e3e098f6149c5d01039122b10a8929e44b430cbd7edf40a10317d5c7d",
        "src/trading_system/research/manifest_identity.py":
            "4c88fc44638af9ddd64a6259c86dc3b80fea927097363fe3e87141d35d92414b",
        "tests/test_causal_percentile.py":
            "55f2be1bee0b13d60a5e793594e40ab934fa3688764ba1c1f95d237b3e11f228",
        "tests/test_fvg.py":
            "471702f7293923748008ce1948b3ee7a1eced7595b16be408f2f6fe22672b05a",
        "tests/test_narrative.py":
            "c9c3000031d046c508d0c82371f6e64839ff8274a6acb139d1e42350afbb0740",
        "tests/test_research_hashing.py":
            "d9eaf0513c0f58f40cb190a352962ba30058c98818b1a0d88c3df7d53a761e67",
        "tests/test_research_manifest_identity.py":
            "15d1a7271c325f38e230bc67de40b0edf3dc3df5bb8e0edf039c97a455485d49",
    }

    manifest_path = os.path.join(project_root, "MANIFEST.sha256")
    # A) manifest identity: exact post-closure digest.
    assert _sha256_file(manifest_path) == closed_manifest_sha256

    # B) manifest state: ALL entries must validate; no stale allowance.
    result = verify_manifest(project_root)
    assert result["manifest_lines"] == 185
    assert result["bad_paths"] == [], result["bad_paths"]
    assert result["bad"] == 0, result["bad_paths"]
    assert result["ok"] == 185

    # C) accepted performance artifacts: independent digest pins.
    for rel, want in accepted_artifact_seal.items():
        got = _sha256_file(os.path.join(project_root, rel))
        assert got == want, (rel, got, want)


def test_seven_closed_adapter_files_match_accepted_seal():
    from field_runner.runner_btc_may_2026 import _sha256_file

    project_root = None
    for cand in (os.path.join(PACKAGE_ROOT, "project", "trading_project"),
                 os.path.join(PACKAGE_ROOT, "trading_project")):
        if os.path.isfile(os.path.join(cand, "MANIFEST.sha256")):
            project_root = cand
            break
    seal = os.path.join(project_root, "docs", "releases",
                        "MODULE_BINANCE_SOURCE_ADAPTER_V1_ACCEPTED_SRC_TESTS.sha256")
    assert os.path.isfile(seal)
    for line in open(seal, encoding="utf-8"):
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        want, rel = parts
        got = _sha256_file(os.path.join(project_root, rel))
        assert got == want, rel

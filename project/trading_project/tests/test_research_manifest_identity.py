import numpy as np
import pandas as pd
import pytest

from trading_system.decision.evidence_vector import (
    CausalEvidenceVectorEngine,
    EvidenceVectorConfig,
    OrderFlowEvidenceMode,
)
from trading_system.decision.narrative import CausalMarketNarrativeEngine
from trading_system.research.manifest_identity import (
    ManifestIdentityError,
    validate_feature_manifest_identity,
    validate_narrative_manifest_identity,
)


def certified_feature_manifest():
    return CausalEvidenceVectorEngine(
        config=EvidenceVectorConfig(
            environment=False,
            temporal_context=False,
            structure=True,
            liquidity=False,
            order_blocks=False,
            fvg=False,
            dealing_range=False,
            multiscale=False,
            order_flow_mode=OrderFlowEvidenceMode.NONE,
        )
    ).manifest()


@pytest.mark.parametrize(
    "payload",
    [
        ["2.1C"],
        ("2.1C",),
        {"source": "2.1C"},
        {"2.1C"},
        np.array(["2.1C"]),
        pd.Series(["2.1C"]),
        pd.Index(["2.1C"]),
    ],
)
def test_feature_manifest_rejects_nonscalar_metadata_cleanly(payload):
    manifest = certified_feature_manifest()
    manifest.at[0, "source_module"] = payload
    with pytest.raises(ManifestIdentityError, match="scalar|malformed"):
        validate_feature_manifest_identity(manifest)


@pytest.mark.parametrize("missing", [None, pd.NA, np.nan])
def test_feature_manifest_canonicalizes_supported_missing_sentinels(missing):
    manifest = certified_feature_manifest()
    manifest.at[0, "freshness_column"] = missing
    validate_feature_manifest_identity(manifest)


def test_feature_manifest_accepts_equivalent_numpy_scalars():
    manifest = certified_feature_manifest()
    event_row = manifest["feature_name"] == "structural_break_event"
    manifest.loc[event_row, "event_local"] = np.bool_(True)
    manifest.loc[event_row, "source_module"] = np.str_("2.1C")
    validate_feature_manifest_identity(manifest)


def _first_missing_coordinate(frame):
    for row_position in range(len(frame)):
        for column in frame.columns:
            if pd.isna(frame.iloc[row_position][column]):
                return row_position, column
    raise AssertionError("certified narrative manifest has no missing cell")


@pytest.mark.parametrize("missing", [None, pd.NA, np.nan])
def test_narrative_manifest_canonicalizes_missing_sentinels(missing):
    manifest = CausalMarketNarrativeEngine.narrative_manifest()
    row_position, column = _first_missing_coordinate(manifest)
    manifest.at[row_position, column] = missing
    validate_narrative_manifest_identity(manifest)


def test_narrative_manifest_rejects_nonscalar_payload_cleanly():
    manifest = CausalMarketNarrativeEngine.narrative_manifest()
    manifest.at[0, "foundation_clause"] = ["FORGED"]
    with pytest.raises(ManifestIdentityError, match="scalar|malformed"):
        validate_narrative_manifest_identity(manifest)


def test_narrative_manifest_rejects_dtype_change_even_with_same_values():
    manifest = CausalMarketNarrativeEngine.narrative_manifest()
    manifest["serialization_order"] = pd.array(
        manifest["serialization_order"], dtype="Int64"
    )
    with pytest.raises(ManifestIdentityError, match="dtype"):
        validate_narrative_manifest_identity(manifest)


def test_all_malformed_manifest_exceptions_are_normalized():
    feature = certified_feature_manifest()
    feature.at[0, "feature_name"] = np.array(["structure_state_after"])
    narrative = CausalMarketNarrativeEngine.narrative_manifest()
    narrative.at[0, "name"] = {"bad": "value"}
    for validator, manifest in (
        (validate_feature_manifest_identity, feature),
        (validate_narrative_manifest_identity, narrative),
    ):
        with pytest.raises(ManifestIdentityError):
            validator(manifest)


# =====================================================================
# EXACT PERFORMANCE — manifest identity validation acceleration gates
# Differential old-vs-new against the verbatim pre-patch reference copy
# (tests/_patch_reference_src/manifest_identity_pre.py, sha256-pinned):
# same accept/reject decisions and identical error messages on mutated
# manifests (the read path changed from per-row Series extraction to
# per-column extraction; the comparison semantics are unchanged).
# =====================================================================

import hashlib as _hashlib
import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path


_MANIFEST_REF_PATH = (
    _Path(__file__).resolve().parent
    / "_patch_reference_src"
    / "manifest_identity_pre.py"
)
_PRE_PATCH_MANIFEST_IDENTITY_SHA256 = (
    "b6ac5a0c3af24f9f0cb9960109228f07771a156415f81c70003b4d31e1f64771"
)


def _load_reference_manifest_identity():
    spec = _importlib_util.spec_from_file_location(
        "_patch_ref_manifest_identity", _MANIFEST_REF_PATH
    )
    module = _importlib_util.module_from_spec(spec)
    _sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REF_MANIFEST_IDENTITY = _load_reference_manifest_identity()


def test_patch_manifest_identity_reference_snapshot_is_pinned():
    assert _MANIFEST_REF_PATH.exists()
    digest = _hashlib.sha256(_MANIFEST_REF_PATH.read_bytes()).hexdigest()
    assert digest == _PRE_PATCH_MANIFEST_IDENTITY_SHA256


def test_patch_manifest_identity_validate_decisions_and_messages_identical():
    import pandas as pd

    from trading_system.decision.narrative import CausalMarketNarrativeEngine
    from trading_system.research.manifest_identity import (
        ManifestIdentityError as NewError,
        validate_narrative_manifest_identity as new_validate,
    )

    certified = CausalMarketNarrativeEngine.narrative_manifest()

    def outcome(validate, frame):
        try:
            validate(frame)
            return "ok"
        except Exception as exc:  # noqa: BLE001 - differential capture
            return (type(exc).__name__, str(exc))

    assert outcome(new_validate, certified) == outcome(
        REF_MANIFEST_IDENTITY.validate_narrative_manifest_identity, certified
    )

    rng_cells = [
        (0, certified.columns[0]),
        (len(certified) // 2, certified.columns[1]),
        (len(certified) - 1, certified.columns[-1]),
    ]
    for row_position, column in rng_cells:
        mutated = certified.copy(deep=True)
        original = mutated.iloc[row_position][column]
        mutated.iloc[row_position, mutated.columns.get_loc(column)] = (
            "__MUTATED__" if not isinstance(original, str) else original + "_x"
        )
        assert outcome(new_validate, mutated) == outcome(
            REF_MANIFEST_IDENTITY.validate_narrative_manifest_identity, mutated
        ), (row_position, column)

    dropped = certified.iloc[:-1]
    assert outcome(new_validate, dropped) == outcome(
        REF_MANIFEST_IDENTITY.validate_narrative_manifest_identity, dropped
    )
    renamed = certified.rename(columns={certified.columns[0]: "other"})
    assert outcome(new_validate, renamed) == outcome(
        REF_MANIFEST_IDENTITY.validate_narrative_manifest_identity, renamed
    )

    with pytest.raises(NewError):
        new_validate("not a frame")

"""Certified static manifest identity checks for Module 6.2A-0 V1.2.

Validation compares immutable contract metadata only. It does not execute any
upstream analytical engine or inspect market/evidence rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading_system.decision.evidence_vector import GROUPS, V1_CATALOG
from trading_system.decision.narrative import CausalMarketNarrativeEngine


class ManifestIdentityError(Exception):
    """Incoming static manifest is not an exact certified contract instance."""


_FEATURE_MANIFEST_COLUMNS = (
    "feature_name",
    "output_column",
    "source_module",
    "source_column",
    "semantic_type",
    "missingness_policy",
    "event_local",
    "support_column",
    "freshness_column",
    "source_mode",
    "directional_semantics",
    "expected_domain",
    "epistemic_status",
)
_MISSING_TOKEN = ("STATIC_MANIFEST_MISSING_V1",)
_NONSCALAR_TYPES = (
    list,
    tuple,
    dict,
    set,
    np.ndarray,
    pd.Series,
    pd.Index,
)


def _normalized(value):
    if isinstance(value, _NONSCALAR_TYPES):
        raise ManifestIdentityError("manifest metadata must be scalar")
    if value is None or value is pd.NA:
        return _MISSING_TOKEN
    if isinstance(value, np.generic):
        missing = pd.isna(value)
        if not isinstance(missing, (bool, np.bool_)):
            raise ManifestIdentityError("manifest missingness must be scalar")
        if bool(missing):
            return _MISSING_TOKEN
        return value.item()
    if not pd.api.types.is_scalar(value):
        raise ManifestIdentityError("manifest metadata must be scalar")
    try:
        missing = pd.isna(value)
    except Exception as exc:
        raise ManifestIdentityError("manifest scalar missingness failed") from exc
    if not isinstance(missing, (bool, np.bool_)):
        raise ManifestIdentityError("manifest missingness must be scalar")
    if bool(missing):
        return _MISSING_TOKEN
    return value


def _same_canonical_value(left, right) -> bool:
    normalized_left = _normalized(left)
    normalized_right = _normalized(right)
    if normalized_left == _MISSING_TOKEN or normalized_right == _MISSING_TOKEN:
        return normalized_left == normalized_right
    return (
        type(normalized_left) is type(normalized_right)
        and normalized_left == normalized_right
    )


def _certified_feature_record(spec) -> dict:
    return {
        "feature_name": spec.feature_name,
        "output_column": spec.output_column,
        "source_module": spec.source_module,
        "source_column": spec.source_column,
        "semantic_type": spec.semantic_type.value,
        "missingness_policy": spec.missingness_policy.value,
        "event_local": spec.event_local,
        "support_column": spec.support_column,
        "freshness_column": spec.freshness_column,
        "source_mode": spec.source_mode,
        "directional_semantics": spec.directional_semantics,
        "expected_domain": spec.expected_domain,
        "epistemic_status": spec.epistemic_status,
    }


def _validate_feature_manifest_identity(feature_manifest: pd.DataFrame) -> None:
    if not isinstance(feature_manifest, pd.DataFrame):
        raise ManifestIdentityError("feature manifest must be DataFrame")
    if feature_manifest.columns.has_duplicates:
        raise ManifestIdentityError("duplicate feature manifest columns")
    if tuple(feature_manifest.columns) != _FEATURE_MANIFEST_COLUMNS:
        raise ManifestIdentityError("feature manifest columns/order mismatch")
    if feature_manifest["feature_name"].duplicated().any():
        raise ManifestIdentityError("duplicate feature name")
    if feature_manifest["output_column"].duplicated().any():
        raise ManifestIdentityError("duplicate feature output")

    certified = {spec.feature_name: spec for spec in V1_CATALOG}
    incoming_names: list[str] = []
    for row in feature_manifest.itertuples(index=False):
        record = row._asdict()
        raw_name = record["feature_name"]
        if isinstance(raw_name, _NONSCALAR_TYPES):
            raise ManifestIdentityError("feature_name must be scalar")
        name = str(raw_name)
        spec = certified.get(name)
        if spec is None:
            raise ManifestIdentityError(f"uncertified feature: {name}")
        expected = _certified_feature_record(spec)
        for column in _FEATURE_MANIFEST_COLUMNS:
            if not _same_canonical_value(record[column], expected[column]):
                raise ManifestIdentityError(
                    f"feature contract mismatch: {name}.{column}"
                )
        incoming_names.append(name)

    selected_names = set(incoming_names)
    for group_name, group_specs in GROUPS.items():
        group_names = {spec.feature_name for spec in group_specs}
        selected = selected_names & group_names
        if selected and selected != group_names:
            raise ManifestIdentityError(
                f"incomplete certified feature group: {group_name}"
            )

    actual_names = {spec.feature_name for spec in GROUPS["actual"]}
    proxy_names = {spec.feature_name for spec in GROUPS["proxy"]}
    if selected_names & actual_names and selected_names & proxy_names:
        raise ManifestIdentityError("multiple certified order-flow modes")

    expected_order = [
        spec.feature_name for spec in V1_CATALOG if spec.feature_name in selected_names
    ]
    if incoming_names != expected_order:
        raise ManifestIdentityError("feature manifest row order mismatch")


def validate_feature_manifest_identity(feature_manifest: pd.DataFrame) -> None:
    try:
        _validate_feature_manifest_identity(feature_manifest)
    except ManifestIdentityError:
        raise
    except Exception as exc:
        raise ManifestIdentityError("malformed feature manifest") from exc


def _validate_narrative_manifest_identity(narrative_manifest: pd.DataFrame) -> None:
    if not isinstance(narrative_manifest, pd.DataFrame):
        raise ManifestIdentityError("narrative manifest must be DataFrame")
    if narrative_manifest.columns.has_duplicates:
        raise ManifestIdentityError("duplicate narrative manifest columns")
    certified = CausalMarketNarrativeEngine.narrative_manifest()
    if type(narrative_manifest.columns) is not type(certified.columns):
        raise ManifestIdentityError("narrative manifest column type mismatch")
    if not narrative_manifest.columns.equals(certified.columns):
        raise ManifestIdentityError("narrative manifest columns/order mismatch")
    if type(narrative_manifest.index) is not type(certified.index):
        raise ManifestIdentityError("narrative manifest index type mismatch")
    if not narrative_manifest.index.equals(certified.index):
        raise ManifestIdentityError("narrative manifest index/order mismatch")
    if not narrative_manifest.dtypes.equals(certified.dtypes):
        raise ManifestIdentityError("narrative manifest dtype mismatch")
    if narrative_manifest.shape != certified.shape:
        raise ManifestIdentityError("narrative manifest shape mismatch")

    for row_position in range(len(certified)):
        for column in certified.columns:
            incoming_value = narrative_manifest.iloc[row_position][column]
            certified_value = certified.iloc[row_position][column]
            if not _same_canonical_value(incoming_value, certified_value):
                raise ManifestIdentityError(
                    f"narrative manifest value mismatch: {row_position}.{column}"
                )


def validate_narrative_manifest_identity(narrative_manifest: pd.DataFrame) -> None:
    try:
        _validate_narrative_manifest_identity(narrative_manifest)
    except ManifestIdentityError:
        raise
    except Exception as exc:
        raise ManifestIdentityError("malformed narrative manifest") from exc

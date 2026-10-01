"""Certified and candidate Layer 2 structure primitives (lazy exports)."""

from importlib import import_module

_DETECTOR_NAMES = (
    "CausalAdaptiveSwingDetector",
    "ConfirmationAssessment",
    "ConfirmedEpisodeDiagnostic",
    "EmpiricalConfirmationPolicy",
    "SwingConfigError",
    "SwingConfirmationPolicy",
    "SwingDataError",
    "SwingDetectorError",
)

_SEQUENCE_NAMES = (
    "ConfirmedSwingSequenceEngine",
    "SwingSequenceDataError",
    "SwingSequenceError",
)

_BREAK_NAMES = (
    "CausalStructuralBreakEngine",
    "StructuralBreakDataError",
    "StructuralBreakError",
)

__all__ = list(_DETECTOR_NAMES + _SEQUENCE_NAMES + _BREAK_NAMES)


def __getattr__(name: str):
    if name in _DETECTOR_NAMES:
        module_name = "swing_detector"
    elif name in _SEQUENCE_NAMES:
        module_name = "swing_sequence"
    elif name in _BREAK_NAMES:
        module_name = "structural_breaks"
    else:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value
    return value

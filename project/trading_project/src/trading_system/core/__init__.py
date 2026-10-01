"""Certified Layer 0 computation primitives (lazy public exports)."""

from importlib import import_module

_EXPORTS = {
    "CausalAdaptiveEMA": ("causal_adaptive_smoothing", "CausalAdaptiveEMA"),
    "CausalSmoothingConfigError": ("causal_adaptive_smoothing", "CausalSmoothingConfigError"),
    "CausalSmoothingDataError": ("causal_adaptive_smoothing", "CausalSmoothingDataError"),
    "CausalSmoothingError": ("causal_adaptive_smoothing", "CausalSmoothingError"),
    "SmoothingObservation": ("causal_adaptive_smoothing", "SmoothingObservation"),
    "causal_adaptive_ema_series": ("causal_adaptive_smoothing", "causal_adaptive_ema_series"),
    "CausalPercentileConfigError": ("causal_percentile", "CausalPercentileConfigError"),
    "CausalPercentileDataError": ("causal_percentile", "CausalPercentileDataError"),
    "CausalPercentileError": ("causal_percentile", "CausalPercentileError"),
    "CausalPercentileTracker": ("causal_percentile", "CausalPercentileTracker"),
    "PercentileObservation": ("causal_percentile", "PercentileObservation"),
    "causal_percentile_series": ("causal_percentile", "causal_percentile_series"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value

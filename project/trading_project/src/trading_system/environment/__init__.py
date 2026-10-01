"""Certified Layer 1 environment descriptions (lazy public exports)."""

from importlib import import_module

_EXPORTS = {
    "DynamicVolatilityDataError": ("dynamic_volatility", "DynamicVolatilityDataError"),
    "DynamicVolatilityEngine": ("dynamic_volatility", "DynamicVolatilityEngine"),
    "DynamicVolatilityError": ("dynamic_volatility", "DynamicVolatilityError"),
    "CausalSessionContextEngine": ("session_context", "CausalSessionContextEngine"),
    "SessionConfigError": ("session_context", "SessionConfigError"),
    "SessionContextDataError": ("session_context", "SessionContextDataError"),
    "SessionContextError": ("session_context", "SessionContextError"),
    "SessionDefinition": ("session_context", "SessionDefinition"),
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

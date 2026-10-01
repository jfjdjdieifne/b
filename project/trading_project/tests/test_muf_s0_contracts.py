"""S0 contracts tests: errors, typed states, schema identity, design guards.

Attacks covered: 18 (typed states), 22 (private imports), 23 (prohibited
implementations), 24 (hidden market thresholds/windows).
"""
import ast
import pathlib

import pytest

from trading_system.market_understanding.contracts import (
    S0_CONTRACTS_VERSION,
    S0_ERROR_CLASSES,
    IllegalCausalReference,
    IdentityViolation,
    ImmutabilityViolation,
    IncomparableInformationKeys,
    InformationKeyViolation,
    MufS0ContractError,
    NonEarliestAvailability,
    PrematureAvailability,
    SchemaIdentity,
    SchemaViolation,
    SequenceChronologyViolation,
    TypedState,
    scan_market_shape_implementations,
    scan_private_imports,
    scan_prohibited_implementations,
    typed_state,
)

_S0_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src"
    / "trading_system"
    / "market_understanding"
)
_S0_MODULES = ("__init__.py", "contracts.py", "identity.py", "availability.py", "records.py")
_S0_TEST_FILES = (
    "test_muf_s0_contracts.py",
    "test_muf_s0_identity.py",
    "test_muf_s0_availability.py",
    "test_muf_s0_records.py",
)


def _production_sources():
    return {name: (_S0_DIR / name).read_text(encoding="utf-8") for name in _S0_MODULES}


def test_error_codes_are_deterministic_and_machine_distinguishable():
    codes = [cls.code for cls in S0_ERROR_CLASSES]
    assert len(set(codes)) == len(codes), codes
    for cls in S0_ERROR_CLASSES:
        exc = cls("message")
        assert isinstance(exc, MufS0ContractError)
        assert exc.code == cls.code
        assert str(exc) == "message"
        assert isinstance(exc.code, str) and exc.code
    assert IncomparableInformationKeys.code == "NOT_COMPARABLE"
    assert issubclass(IncomparableInformationKeys, InformationKeyViolation)
    assert issubclass(PrematureAvailability, NonEarliestAvailability)
    assert NonEarliestAvailability.code == "NON_EARLIEST_AVAILABILITY"
    assert S0_CONTRACTS_VERSION == "MUF_S0_CONTRACTS_V1"


def test_attack18_typed_states_never_collapse():
    values = [state.value for state in TypedState]
    assert values == ["NOT_CONFIGURED", "UNAVAILABLE", "UNDEFINED", "NOT_APPLICABLE"]
    assert TypedState.NOT_CONFIGURED is not TypedState.UNAVAILABLE
    assert TypedState.NOT_CONFIGURED is not TypedState.UNDEFINED
    assert TypedState.UNAVAILABLE is not TypedState.UNDEFINED
    for state in TypedState:
        assert state.value not in (None, 0, False, "")
        assert typed_state(state.value) is state
        assert typed_state(state) is state
    with pytest.raises(SchemaViolation):
        typed_state("MISSING")
    with pytest.raises(SchemaViolation):
        typed_state(None)
    with pytest.raises(SchemaViolation):
        typed_state(0)


def test_schema_identity_rejects_latest_alias():
    ok = SchemaIdentity("DOMAIN", "V1")
    assert ok.as_payload() == {"schema_domain": "DOMAIN", "schema_version": "V1"}
    for bad_version in ("latest", "Latest", "LATEST", " latest "):
        with pytest.raises(SchemaViolation):
            SchemaIdentity("DOMAIN", bad_version)
    for bad in ("", "   "):
        with pytest.raises(SchemaViolation):
            SchemaIdentity(bad, "V1")
        with pytest.raises(SchemaViolation):
            SchemaIdentity("DOMAIN", bad)


def test_attack22_private_import_scan_zero():
    for name, source in _production_sources().items():
        assert scan_private_imports(source) == (), name
    for name in _S0_TEST_FILES:
        source = (pathlib.Path(__file__).resolve().parent / name).read_text(encoding="utf-8")
        assert scan_private_imports(source) == (), name
    assert scan_private_imports("from a.b import _c\n") == ("_c",)
    assert scan_private_imports("from a._b import c\n") == ("a._b",)
    assert scan_private_imports("import x._y\n") == ("x._y",)
    assert scan_private_imports("import ast\nfrom trading_system.sources import TIE_ORDER_CONTRACT\n") == ()


def test_attack23_prohibited_implementations_guard():
    for name, source in _production_sources().items():
        assert scan_prohibited_implementations(source) == (), name
    assert scan_prohibited_implementations("class FitModel:\n    pass\n") == ("FitModel",)
    assert scan_prohibited_implementations("def run_strategy():\n    return None\n") == ("run_strategy",)
    assert scan_prohibited_implementations("signal_value = 1\n") == ("signal_value",)
    assert scan_prohibited_implementations("def compute_pnl():\n    return None\n") == ("compute_pnl",)
    assert scan_prohibited_implementations("def trade_execution():\n    return None\n") == ("trade_execution",)


def test_attack24_no_hidden_market_thresholds_or_windows():
    for name, source in _production_sources().items():
        assert scan_market_shape_implementations(source) == (), name
    assert scan_market_shape_implementations("window_size = 20\n") == (
        "window_size",
        "numeric_constant:20",
    )
    assert scan_market_shape_implementations("def apply_threshold():\n    return None\n") == ("apply_threshold",)
    assert scan_market_shape_implementations("value = 0.5\n") == ("numeric_constant:0.5",)
    assert scan_market_shape_implementations("value = 20\n") == ("numeric_constant:20",)
    assert scan_market_shape_implementations("value = 0\n") == ()
    assert scan_market_shape_implementations("value = 1\n") == ()

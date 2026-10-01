"""MUF V1 S0: shared public contract primitives.

ERRORS, typed missing states, schema identity, and source-design guards.
Contract foundations only: no market semantics, no market data, no CLOSED
private imports. Deterministic and machine-distinguishable throughout.

Design guards below are AST scanners used by the S0 design tests to prove
production sources stay free of prohibited implementations and hidden
market shapes. They scan NAMES and numeric constants only; string data is
never treated as an implementation.
"""
import ast
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Mapping, Tuple

S0_CONTRACTS_VERSION: Final[str] = "MUF_S0_CONTRACTS_V1"


# ---------------------------------------------------------------------------
# S0 error hierarchy (deterministic, machine-distinguishable via ``code``)
# ---------------------------------------------------------------------------


class MufS0ContractError(Exception):
    """Base class for every S0 contract violation."""

    code: str = "MUF_S0_CONTRACT_ERROR"

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class SchemaViolation(MufS0ContractError):
    """Schema shape, schema version, or typed-reference contract violation."""

    code = "SCHEMA_VIOLATION"


class IdentityViolation(MufS0ContractError):
    """Canonical identity construction/verification violation."""

    code = "IDENTITY_VIOLATION"


class InformationKeyViolation(MufS0ContractError):
    """Information-key / timeline / phase / axis contract violation."""

    code = "INFORMATION_KEY_VIOLATION"


class IncomparableInformationKeys(InformationKeyViolation):
    """Comparability cannot be established under public key semantics.

    FAIL CLOSED: S0 never guesses an ordering that the CLOSED information-key
    contract does not authorize.
    """

    code = "NOT_COMPARABLE"


class NonEarliestAvailability(MufS0ContractError):
    """A later-than-earliest lawful availability key was proposed."""

    code = "NON_EARLIEST_AVAILABILITY"


class PrematureAvailability(NonEarliestAvailability):
    """A proposed availability key precedes lawful earliest availability."""

    code = "PREMATURE_AVAILABILITY"


class ImmutabilityViolation(MufS0ContractError):
    """In-place mutation of a published record was attempted."""

    code = "IMMUTABILITY_VIOLATION"


class IllegalCausalReference(MufS0ContractError):
    """A causal reference is illegal at the requested information key."""

    code = "ILLEGAL_CAUSAL_REFERENCE"


class SequenceChronologyViolation(InformationKeyViolation):
    """Deterministic-sequence/row order was used as a market-chronology claim."""

    code = "SEQUENCE_NOT_MARKET_CHRONOLOGY"


S0_ERROR_CLASSES: Final[Tuple[type, ...]] = (
    MufS0ContractError,
    SchemaViolation,
    IdentityViolation,
    InformationKeyViolation,
    IncomparableInformationKeys,
    NonEarliestAvailability,
    PrematureAvailability,
    ImmutabilityViolation,
    IllegalCausalReference,
    SequenceChronologyViolation,
)


# ---------------------------------------------------------------------------
# Typed missing / not-configured states (never collapsed to None/0/False/"")
# ---------------------------------------------------------------------------


class TypedState(Enum):
    """Explicit typed states preserved across S0 contracts."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"
    UNDEFINED = "UNDEFINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


def typed_state(value: Any) -> TypedState:
    """Return the TypedState for an exact declared token, else SchemaViolation."""
    if isinstance(value, TypedState):
        return value
    for state in TypedState:
        if value == state.value:
            return state
    raise SchemaViolation(f"unknown typed state token: {value!r}")


# ---------------------------------------------------------------------------
# Schema identity / versioning (no mutable "latest" alias in identities)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SchemaIdentity:
    """Identity-bearing schema domain + explicit version."""

    schema_domain: str
    schema_version: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("schema_domain", self.schema_domain),
            ("schema_version", self.schema_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise SchemaViolation(f"{field_name} must be a nonempty string")
        if self.schema_version.strip().lower() == "latest":
            raise SchemaViolation(
                "mutable 'latest' schema alias is forbidden inside persisted identities"
            )

    def as_payload(self) -> Mapping[str, Any]:
        return {
            "schema_domain": self.schema_domain,
            "schema_version": self.schema_version,
        }


# ---------------------------------------------------------------------------
# Shared validation helpers (public package contract)
# ---------------------------------------------------------------------------


def require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaViolation(f"{field_name} must be a nonempty string")
    return value


def require_identifier_tuple(value: Any, field_name: str) -> Tuple[str, ...]:
    if not isinstance(value, tuple) or not value:
        raise SchemaViolation(f"{field_name} must be a nonempty tuple of names")
    seen = set()
    for item in value:
        if not isinstance(item, str) or not item:
            raise SchemaViolation(f"{field_name} entries must be nonempty strings")
        if item in seen:
            raise SchemaViolation(f"{field_name} entries must be unique")
        seen.add(item)
    return value


# ---------------------------------------------------------------------------
# Design guards (AST scans over production source text)
# ---------------------------------------------------------------------------

PROHIBITED_IMPLEMENTATION_TERMS: Final[Tuple[str, ...]] = (
    "model",
    "strategy",
    "pnl",
    "signal",
    "trade",
    "execute",
)

PROHIBITED_MARKET_SHAPE_TERMS: Final[Tuple[str, ...]] = (
    "threshold",
    "window",
    "horizon",
    "quantile",
    "lookback",
    "period",
    "interval",
)

ALLOWED_NUMERIC_CONSTANTS: Final[Tuple[int, ...]] = (0, 1)


def _definition_names(tree: ast.AST) -> Tuple[str, ...]:
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.append(node.target.id)
    return tuple(names)


def scan_private_imports(source: str) -> Tuple[str, ...]:
    """Return violations: any import whose final component starts with '_'."""
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[-1].startswith("_") or any(p.startswith("_") for p in parts):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_parts = (node.module or "").split(".")
            if any(p.startswith("_") for p in module_parts):
                violations.append(node.module or "")
            for alias in node.names:
                if alias.name.startswith("_"):
                    violations.append(alias.name)
    return tuple(violations)


def scan_prohibited_implementations(source: str) -> Tuple[str, ...]:
    """Return names indicating prohibited domain implementations."""
    tree = ast.parse(source)
    violations = []
    for name in _definition_names(tree):
        lowered = name.lower()
        for term in PROHIBITED_IMPLEMENTATION_TERMS:
            if term in lowered:
                violations.append(name)
                break
    return tuple(violations)


def scan_market_shape_implementations(source: str) -> Tuple[str, ...]:
    """Return names/constants indicating hidden market thresholds or windows."""
    tree = ast.parse(source)
    violations = []
    for name in _definition_names(tree):
        lowered = name.lower()
        for term in PROHIBITED_MARKET_SHAPE_TERMS:
            if term in lowered:
                violations.append(name)
                break
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):
                continue
            if node.value not in ALLOWED_NUMERIC_CONSTANTS:
                violations.append(f"numeric_constant:{node.value!r}")
    return tuple(violations)

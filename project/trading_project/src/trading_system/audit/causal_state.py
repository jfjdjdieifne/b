"""
Layer 0 — Module 0.1
Causal & State Audit Framework
VERSION 3.1

PURPOSE
-------
Foundational audit infrastructure for analytical trading modules.

This module performs two DISTINCT classes of tests:

1. TRUNCATION INVARIANCE AUDIT
   Checks whether an already-computed prefix changes when unavailable
   suffix rows are removed.

   A failure means:

       "TRUNCATION INVARIANCE VIOLATION"

   It does NOT automatically prove the root cause is look-ahead.
   Possible causes include:
       - genuine future-data access
       - global/full-sample statistics
       - centered windows
       - negative shifts
       - batch-length dependence
       - boundary-dependent initialization
       - other non-causal batch context

2. STATE ISOLATION AUDIT
   Checks:
       - deterministic replay across fresh instances
       - repeated analyze(A) on the same instance
       - A -> B contamination versus fresh(B)
       - optional explicit "must raise on reuse" contract

CERTIFICATION SCOPE
-------------------
Passing these tests provides evidence of causal/deterministic behavior
WITHIN THE TESTED INPUTS, OUTPUT SURFACE, SPLIT POINTS, and configured
comparison policy.

It is NOT an exhaustive mathematical proof for every possible input.

V3.1 OUTPUT SCOPE
-----------------
Only the primary DataFrame output is audited.

Auxiliary outputs such as:
    List[LiquidityLevel]
    List[FairValueGap]
    registries
    state snapshots

are NOT yet audited.

Therefore modules exposing auxiliary registries must NOT be described
as "fully causally certified" by this version. Only their DataFrame
output surface is covered.

IMPORTANT DEFAULT
-----------------
Numerical comparison is EXACT by default:

    rtol = 0.0
    atol = 0.0

Tolerance must be explicitly enabled by the caller when a known and
documented numerical reason exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    Union,
    runtime_checkable,
)

import numpy as np
import pandas as pd


# ============================================================================
# Exceptions
# ============================================================================

class CausalAuditError(Exception):
    """Base exception for causal/state audit failures."""


class AuditConfigError(CausalAuditError):
    """Raised when the auditor itself receives an invalid configuration."""


class EngineContractViolation(CausalAuditError):
    """Raised when an engine violates the auditable API contract."""


class EngineExecutionError(CausalAuditError):
    """
    Raised when the tested engine unexpectedly fails while the auditor
    invokes analyze().
    """

    def __init__(
        self,
        *,
        stage: str,
        engine_type: str,
        original_exception: BaseException,
    ) -> None:
        self.stage = stage
        self.engine_type = engine_type
        self.original_exception = original_exception

        super().__init__(
            f"Engine execution failed during stage={stage!r}. "
            f"engine={engine_type}, "
            f"exception={type(original_exception).__name__}: "
            f"{original_exception}"
        )


class EngineReuseError(Exception):
    """
    Recommended exception for engines implementing MUST_RAISE_ON_REUSE.
    """


# ============================================================================
# Engine contract
# ============================================================================

EngineResult = Union[pd.DataFrame, tuple, list]


@runtime_checkable
class CausalEngineProtocol(Protocol):

    def analyze(
        self,
        df: pd.DataFrame,
        **kwargs: Any,
    ) -> EngineResult:
        ...


class ReentrancyPolicy(Enum):
    """
    Expected behavior when analyze() is called more than once.

    IDEMPOTENT_REENTRANT:
        Repeated calls are supported and previous calls must not alter
        subsequent results.

    MUST_RAISE_ON_REUSE:
        First call succeeds. Any subsequent call must raise the explicitly
        expected reuse exception.
    """

    IDEMPOTENT_REENTRANT = "idempotent_reentrant"
    MUST_RAISE_ON_REUSE = "must_raise_on_reuse"


# ============================================================================
# Audit result objects
# ============================================================================

@dataclass(frozen=True)
class ColumnDivergence:
    column: Any
    first_divergent_position: int
    first_divergent_index_label: Any
    kind: str

    value_a: Any
    value_b: Any

    max_abs_diff: Optional[float] = None
    max_rel_diff: Optional[float] = None


@dataclass
class DataFrameComparisonResult:
    label_a: str
    label_b: str

    passed: bool = True
    columns_checked: int = 0

    column_divergences: List[ColumnDivergence] = field(default_factory=list)
    missing_in_b: List[Any] = field(default_factory=list)
    missing_in_a: List[Any] = field(default_factory=list)

    dtype_mismatches: List[Tuple[Any, str, str]] = field(
        default_factory=list
    )

    row_count_mismatch_detail: Optional[str] = None
    index_mismatch_detail: Optional[str] = None
    schema_order_mismatch_detail: Optional[str] = None

    def summary(self) -> str:

        if self.passed:
            return (
                f"[{self.label_a} vs {self.label_b}] PASSED — "
                f"{self.columns_checked} columns compared."
            )

        lines = [
            f"[{self.label_a} vs {self.label_b}] FAILED."
        ]

        if self.row_count_mismatch_detail:
            lines.append(
                f"  ROW COUNT: {self.row_count_mismatch_detail}"
            )

        if self.index_mismatch_detail:
            lines.append(
                f"  INDEX: {self.index_mismatch_detail}"
            )

        if self.schema_order_mismatch_detail:
            lines.append(
                f"  SCHEMA: {self.schema_order_mismatch_detail}"
            )

        for column in self.missing_in_b:
            lines.append(
                f"  Column {column!r} exists in {self.label_a} "
                f"but not in {self.label_b}."
            )

        for column in self.missing_in_a:
            lines.append(
                f"  Column {column!r} exists in {self.label_b} "
                f"but not in {self.label_a}."
            )

        for column, dtype_a, dtype_b in self.dtype_mismatches:
            lines.append(
                f"  Column {column!r}: dtype mismatch "
                f"({dtype_a} vs {dtype_b})."
            )

        for divergence in self.column_divergences:

            line = (
                f"  Column {divergence.column!r} "
                f"[{divergence.kind}] first divergence at "
                f"position={divergence.first_divergent_position}, "
                f"index={divergence.first_divergent_index_label!r}: "
                f"{self.label_a}={divergence.value_a!r}, "
                f"{self.label_b}={divergence.value_b!r}"
            )

            if divergence.max_abs_diff is not None:
                line += (
                    f", max_abs_diff="
                    f"{divergence.max_abs_diff:.17g}"
                )

            if divergence.max_rel_diff is not None:
                line += (
                    f", max_rel_diff="
                    f"{divergence.max_rel_diff:.17g}"
                )

            lines.append(line)

        return "\n".join(lines)


@dataclass
class TruncationAuditResult:
    split_at: int
    comparison: DataFrameComparisonResult

    @property
    def passed(self) -> bool:
        return self.comparison.passed

    def summary(self) -> str:
        return (
            f"[split_at={self.split_at}]\n"
            f"{self.comparison.summary()}"
        )


@dataclass
class StateAuditResult:

    policy: ReentrancyPolicy

    determinism_result: DataFrameComparisonResult

    repeated_call_result: Optional[
        DataFrameComparisonResult
    ] = None

    contamination_result: Optional[
        DataFrameComparisonResult
    ] = None

    reuse_raised_as_expected: Optional[bool] = None

    @property
    def passed(self) -> bool:

        checks = [self.determinism_result.passed]

        if self.repeated_call_result is not None:
            checks.append(self.repeated_call_result.passed)

        if self.contamination_result is not None:
            checks.append(self.contamination_result.passed)

        if self.reuse_raised_as_expected is not None:
            checks.append(self.reuse_raised_as_expected)

        return all(checks)

    def summary(self) -> str:

        lines = [
            f"State Audit — policy={self.policy.value}",
            (
                "  Fresh-instance determinism: "
                f"{'PASSED' if self.determinism_result.passed else 'FAILED'}"
            ),
        ]

        if not self.determinism_result.passed:
            lines.append(self.determinism_result.summary())

        if self.repeated_call_result is not None:

            lines.append(
                "  Same-instance A -> A: "
                f"{'PASSED' if self.repeated_call_result.passed else 'FAILED'}"
            )

            if not self.repeated_call_result.passed:
                lines.append(
                    self.repeated_call_result.summary()
                )

        if self.contamination_result is not None:

            lines.append(
                "  Isolated A -> B contamination: "
                f"{'PASSED' if self.contamination_result.passed else 'FAILED'}"
            )

            if not self.contamination_result.passed:
                lines.append(
                    self.contamination_result.summary()
                )

        if self.reuse_raised_as_expected is not None:
            lines.append(
                "  Explicit reuse guard: "
                + (
                    "PASSED"
                    if self.reuse_raised_as_expected
                    else "FAILED"
                )
            )

        return "\n".join(lines)


# ============================================================================
# Validation
# ============================================================================

def _validate_tolerances(
    rtol: float,
    atol: float,
) -> None:

    for name, value in (
        ("rtol", rtol),
        ("atol", atol),
    ):
        if isinstance(value, (bool, np.bool_)):
            raise AuditConfigError(
                f"{name} must be a finite non-negative real number."
            )

        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise AuditConfigError(
                f"{name} must be numeric. Got {value!r}."
            ) from exc

        if not np.isfinite(numeric):
            raise AuditConfigError(
                f"{name} must be finite. Got {value!r}."
            )

        if numeric < 0.0:
            raise AuditConfigError(
                f"{name} must be >= 0. Got {value!r}."
            )


def _validate_dtype_severity(
    severity: str,
) -> None:

    if severity not in {"fatal", "warning"}:
        raise AuditConfigError(
            "dtype_mismatch_severity must be "
            "'fatal' or 'warning'."
        )


def _validate_expected_exception(
    exception_type: Type[BaseException],
) -> None:

    if not isinstance(exception_type, type):
        raise AuditConfigError(
            "expected_reuse_exception must be an exception class."
        )

    if not issubclass(exception_type, BaseException):
        raise AuditConfigError(
            "expected_reuse_exception must inherit BaseException."
        )

    # Catching these as intentional reuse errors would be unsafe.
    if not issubclass(exception_type, Exception):
        raise AuditConfigError(
            "expected_reuse_exception must inherit Exception, "
            "not only BaseException."
        )


def _validate_dataframe_input(
    df: pd.DataFrame,
    name: str,
) -> None:

    if not isinstance(df, pd.DataFrame):
        raise AuditConfigError(
            f"{name} must be a pandas DataFrame. "
            f"Got {type(df).__name__}."
        )


def _validate_output_structure(
    df: pd.DataFrame,
    label: str,
) -> None:

    if df.columns.has_duplicates:
        duplicates = (
            df.columns[df.columns.duplicated()]
            .tolist()
        )

        raise EngineContractViolation(
            f"{label} contains duplicate columns: "
            f"{duplicates!r}. Duplicate output column names "
            f"are forbidden."
        )


# ============================================================================
# Engine execution wrapper
# ============================================================================

def _extract_dataframe(
    result: EngineResult,
    *,
    stage: str,
) -> pd.DataFrame:

    if isinstance(result, pd.DataFrame):
        return result

    if isinstance(result, (tuple, list)):

        if not result:
            raise EngineContractViolation(
                f"At stage={stage!r}, analyze() returned "
                f"an empty {type(result).__name__}."
            )

        if isinstance(result[0], pd.DataFrame):
            return result[0]

    raise EngineContractViolation(
        f"At stage={stage!r}, analyze() must return either "
        f"a DataFrame or tuple/list whose first element is "
        f"a DataFrame. Got {type(result).__name__}."
    )


def _execute_engine(
    engine: CausalEngineProtocol,
    df: pd.DataFrame,
    *,
    stage: str,
    analyze_kwargs: dict,
    passthrough_exception: Optional[
        Type[BaseException]
    ] = None,
) -> pd.DataFrame:
    """
    Centralized engine execution.

    Unexpected engine exceptions become EngineExecutionError carrying:
        - audit stage
        - engine type
        - original exception

    passthrough_exception exists specifically for the intentional
    MUST_RAISE_ON_REUSE contract.
    """

    engine_type = type(engine).__name__

    try:
        raw_result = engine.analyze(
            df,
            **analyze_kwargs,
        )

    except BaseException as exc:

        # Never convert process-control exceptions into an ordinary
        # audit failure.
        if isinstance(
            exc,
            (KeyboardInterrupt, SystemExit, GeneratorExit),
        ):
            raise

        if (
            passthrough_exception is not None
            and isinstance(exc, passthrough_exception)
        ):
            raise

        raise EngineExecutionError(
            stage=stage,
            engine_type=engine_type,
            original_exception=exc,
        ) from exc

    output = _extract_dataframe(
        raw_result,
        stage=stage,
    )

    _validate_output_structure(
        output,
        f"{engine_type}:{stage}",
    )

    return output


def _construct_engine(
    engine_factory: Callable[
        [],
        CausalEngineProtocol,
    ],
    *,
    stage: str,
) -> CausalEngineProtocol:

    if not callable(engine_factory):
        raise AuditConfigError(
            "engine_factory must be callable."
        )

    try:
        engine = engine_factory()

    except BaseException as exc:

        if isinstance(
            exc,
            (KeyboardInterrupt, SystemExit, GeneratorExit),
        ):
            raise

        raise EngineExecutionError(
            stage=f"{stage}:construction",
            engine_type=getattr(
                engine_factory,
                "__name__",
                type(engine_factory).__name__,
            ),
            original_exception=exc,
        ) from exc

    analyze = getattr(
        engine,
        "analyze",
        None,
    )

    if not callable(analyze):
        raise EngineContractViolation(
            f"Factory produced {type(engine).__name__}, "
            f"which has no callable analyze()."
        )

    return engine


# ============================================================================
# Dtype-aware comparison
# ============================================================================

def _safe_scalar_isna(
    value: Any,
) -> bool:
    """
    pd.isna() can return an array for container-like objects.
    Analytical cells are expected to contain scalar values.

    Container-valued object cells are therefore rejected explicitly
    rather than ambiguously reduced to bool.
    """

    result = pd.isna(value)

    if isinstance(
        result,
        (bool, np.bool_),
    ):
        return bool(result)

    raise EngineContractViolation(
        "Object column contains a non-scalar value for which "
        "missingness is array-valued. Analytical output cells "
        "must be scalar for deterministic comparison."
    )


def _safe_scalar_equal(
    x: Any,
    y: Any,
) -> bool:

    x_na = _safe_scalar_isna(x)
    y_na = _safe_scalar_isna(y)

    if x_na or y_na:
        return x_na and y_na

    try:
        result = x == y
    except Exception as exc:
        raise EngineContractViolation(
            f"Scalar equality failed for values "
            f"{x!r} and {y!r}."
        ) from exc

    if isinstance(
        result,
        (bool, np.bool_),
    ):
        return bool(result)

    raise EngineContractViolation(
        "Scalar equality returned a non-scalar result. "
        "Analytical output cells must contain comparable scalars."
    )


def _object_match(
    a: pd.Series,
    b: pd.Series,
) -> np.ndarray:

    a_values = a.astype(object).to_numpy()
    b_values = b.astype(object).to_numpy()

    if len(a_values) != len(b_values):
        raise EngineContractViolation(
            "Internal comparator received unequal Series lengths."
        )

    result = np.empty(
        len(a_values),
        dtype=bool,
    )

    for i, (x, y) in enumerate(
        zip(a_values, b_values)
    ):
        result[i] = _safe_scalar_equal(x, y)

    return result


def _integer_or_bool_match(
    a: pd.Series,
    b: pd.Series,
) -> np.ndarray:
    """
    Exact object-backed comparison intentionally avoids converting
    int64/uint64 to float64.

    Conversion to float64 could make distinct integers above 2**53
    appear identical.
    """

    return _object_match(a, b)


def _floating_match(
    a: pd.Series,
    b: pd.Series,
    rtol: float,
    atol: float,
) -> np.ndarray:

    try:
        a_values = a.to_numpy(
            dtype=np.float64,
            na_value=np.nan,
        )
        b_values = b.to_numpy(
            dtype=np.float64,
            na_value=np.nan,
        )
    except (TypeError, ValueError) as exc:
        raise EngineContractViolation(
            f"Unable to safely convert floating columns "
            f"{a.dtype} / {b.dtype} to float64."
        ) from exc

    both_nan = (
        np.isnan(a_values)
        & np.isnan(b_values)
    )

    both_pos_inf = (
        np.isposinf(a_values)
        & np.isposinf(b_values)
    )

    both_neg_inf = (
        np.isneginf(a_values)
        & np.isneginf(b_values)
    )

    both_finite = (
        np.isfinite(a_values)
        & np.isfinite(b_values)
    )

    matches = np.zeros(
        len(a_values),
        dtype=bool,
    )

    matches[both_finite] = np.isclose(
        a_values[both_finite],
        b_values[both_finite],
        rtol=rtol,
        atol=atol,
        equal_nan=False,
    )

    return (
        matches
        | both_nan
        | both_pos_inf
        | both_neg_inf
    )


def _complex_match(
    a: pd.Series,
    b: pd.Series,
    rtol: float,
    atol: float,
) -> np.ndarray:

    try:
        a_values = a.to_numpy(
            dtype=np.complex128,
        )
        b_values = b.to_numpy(
            dtype=np.complex128,
        )
    except (TypeError, ValueError) as exc:
        raise EngineContractViolation(
            f"Unable to safely compare complex columns "
            f"{a.dtype} / {b.dtype}."
        ) from exc

    return np.isclose(
        a_values,
        b_values,
        rtol=rtol,
        atol=atol,
        equal_nan=True,
    )


def _datetime_match(
    a: pd.Series,
    b: pd.Series,
) -> np.ndarray:
    """
    Object-backed scalar comparison handles:
      - datetime64[ns]
      - timezone-aware DatetimeTZDtype
      - NaT

    No timezone normalization is intentionally performed here.
    A dtype mismatch remains visible to the schema/dtype audit.
    """

    return _object_match(a, b)


def _timedelta_match(
    a: pd.Series,
    b: pd.Series,
) -> np.ndarray:

    return _object_match(a, b)


def _is_string_like_dtype(
    dtype: Any,
) -> bool:

    if isinstance(dtype, pd.StringDtype):
        return True

    try:
        return bool(
            pd.api.types.is_string_dtype(dtype)
        )
    except TypeError:
        return False


def _is_object_family(
    dtype: Any,
) -> bool:

    return (
        pd.api.types.is_object_dtype(dtype)
        or isinstance(dtype, pd.CategoricalDtype)
        or _is_string_like_dtype(dtype)
    )


def _elementwise_match(
    a: pd.Series,
    b: pd.Series,
    *,
    rtol: float,
    atol: float,
) -> np.ndarray:
    """
    Explicit dtype-dispatch.

    Supported families:
      - bool / pandas BooleanDtype
      - signed/unsigned integer / nullable Int*
      - floating / nullable Float*
      - complex
      - datetime
      - timezone-aware datetime
      - timedelta
      - object
      - category
      - pandas StringDtype

    Unsupported combinations fail explicitly.
    """

    dtype_a = a.dtype
    dtype_b = b.dtype

    a_bool = pd.api.types.is_bool_dtype(dtype_a)
    b_bool = pd.api.types.is_bool_dtype(dtype_b)

    if a_bool and b_bool:
        return _integer_or_bool_match(a, b)

    a_int = pd.api.types.is_integer_dtype(dtype_a)
    b_int = pd.api.types.is_integer_dtype(dtype_b)

    if a_int and b_int:
        return _integer_or_bool_match(a, b)

    a_float = pd.api.types.is_float_dtype(dtype_a)
    b_float = pd.api.types.is_float_dtype(dtype_b)

    if a_float and b_float:
        return _floating_match(
            a,
            b,
            rtol,
            atol,
        )

    a_complex = pd.api.types.is_complex_dtype(dtype_a)
    b_complex = pd.api.types.is_complex_dtype(dtype_b)

    if a_complex and b_complex:
        return _complex_match(
            a,
            b,
            rtol,
            atol,
        )

    a_datetime = pd.api.types.is_datetime64_any_dtype(dtype_a)
    b_datetime = pd.api.types.is_datetime64_any_dtype(dtype_b)

    if a_datetime and b_datetime:
        return _datetime_match(a, b)

    a_timedelta = pd.api.types.is_timedelta64_dtype(dtype_a)
    b_timedelta = pd.api.types.is_timedelta64_dtype(dtype_b)

    if a_timedelta and b_timedelta:
        return _timedelta_match(a, b)

    if (
        _is_object_family(dtype_a)
        and _is_object_family(dtype_b)
    ):
        return _object_match(a, b)

    raise EngineContractViolation(
        "Unsupported or incompatible dtype pairing: "
        f"{dtype_a!s} vs {dtype_b!s}. "
        "The auditor refuses to guess a comparison strategy."
    )


# ============================================================================
# Difference diagnostics
# ============================================================================

def _classify_divergence_kind(
    a_value: Any,
    b_value: Any,
) -> str:

    def scalar_nan(value: Any) -> bool:
        try:
            return bool(
                isinstance(value, (float, np.floating))
                and np.isnan(value)
            )
        except (TypeError, ValueError):
            return False

    def scalar_inf(value: Any) -> bool:
        try:
            return bool(
                isinstance(value, (float, np.floating))
                and np.isinf(value)
            )
        except (TypeError, ValueError):
            return False

    if (
        scalar_nan(a_value)
        or scalar_nan(b_value)
    ):
        return "nan_mismatch"

    if (
        scalar_inf(a_value)
        or scalar_inf(b_value)
    ):
        return "inf_mismatch"

    return "value_mismatch"


def _relative_difference(
    a: float,
    b: float,
) -> Optional[float]:

    if not (
        np.isfinite(a)
        and np.isfinite(b)
    ):
        return None

    numerator = abs(a - b)

    denominator = max(
        abs(a),
        abs(b),
    )

    if denominator == 0.0:
        return (
            0.0
            if numerator == 0.0
            else float("inf")
        )

    return numerator / denominator


def _numeric_diagnostics(
    a: pd.Series,
    b: pd.Series,
    mismatch_mask: np.ndarray,
) -> Tuple[
    Optional[float],
    Optional[float],
]:

    if not (
        pd.api.types.is_numeric_dtype(a.dtype)
        and pd.api.types.is_numeric_dtype(b.dtype)
    ):
        return None, None

    # Bool diagnostics as numerical distances are not meaningful.
    if (
        pd.api.types.is_bool_dtype(a.dtype)
        or pd.api.types.is_bool_dtype(b.dtype)
    ):
        return None, None

    positions = np.flatnonzero(
        mismatch_mask
    )

    absolute_differences: List[float] = []
    relative_differences: List[float] = []

    for position in positions:

        x = a.iloc[position]
        y = b.iloc[position]

        if (
            _safe_scalar_isna(x)
            or _safe_scalar_isna(y)
        ):
            continue

        try:
            # Diagnostic conversion only. Equality itself was already
            # determined without lossy integer->float conversion.
            x_float = float(x)
            y_float = float(y)
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            continue

        if (
            np.isfinite(x_float)
            and np.isfinite(y_float)
        ):
            absolute_differences.append(
                abs(x_float - y_float)
            )

            relative = _relative_difference(
                x_float,
                y_float,
            )

            if relative is not None:
                relative_differences.append(
                    relative
                )

    max_abs = (
        max(absolute_differences)
        if absolute_differences
        else None
    )

    max_rel = (
        max(relative_differences)
        if relative_differences
        else None
    )

    return max_abs, max_rel


# ============================================================================
# DataFrame comparator
# ============================================================================

def _compare_dataframes(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    *,
    label_a: str,
    label_b: str,
    rtol: float,
    atol: float,
    dtype_mismatch_severity: str,
    enforce_column_order: bool,
) -> DataFrameComparisonResult:

    _validate_output_structure(
        df_a,
        label_a,
    )

    _validate_output_structure(
        df_b,
        label_b,
    )

    result = DataFrameComparisonResult(
        label_a=label_a,
        label_b=label_b,
    )

    if len(df_a) != len(df_b):
        result.row_count_mismatch_detail = (
            f"{label_a} has {len(df_a)} rows; "
            f"{label_b} has {len(df_b)} rows."
        )
        result.passed = False
        return result

    if not df_a.index.equals(df_b.index):
        result.index_mismatch_detail = (
            "Index values/order/type differ."
        )
        result.passed = False
        return result

    columns_a = df_a.columns
    columns_b = df_b.columns

    if (
        enforce_column_order
        and not columns_a.equals(columns_b)
    ):
        result.schema_order_mismatch_detail = (
            f"{label_a} columns={list(columns_a)!r}; "
            f"{label_b} columns={list(columns_b)!r}"
        )
        result.passed = False

    # Duplicate labels were already rejected, so set operations are
    # unambiguous here.
    set_a = set(columns_a.tolist())
    set_b = set(columns_b.tolist())

    result.missing_in_b = [
        column
        for column in columns_a
        if column not in set_b
    ]

    result.missing_in_a = [
        column
        for column in columns_b
        if column not in set_a
    ]

    if (
        result.missing_in_b
        or result.missing_in_a
    ):
        result.passed = False

    common_columns = [
        column
        for column in columns_a
        if column in set_b
    ]

    for column in common_columns:

        result.columns_checked += 1

        a = df_a[column]
        b = df_b[column]

        if a.dtype != b.dtype:

            result.dtype_mismatches.append(
                (
                    column,
                    str(a.dtype),
                    str(b.dtype),
                )
            )

            if dtype_mismatch_severity == "fatal":
                result.passed = False

        try:
            matches = _elementwise_match(
                a,
                b,
                rtol=rtol,
                atol=atol,
            )

        except EngineContractViolation as exc:
            raise EngineContractViolation(
                f"Failed comparing column {column!r} "
                f"between {label_a!r} and {label_b!r}: "
                f"{exc}"
            ) from exc

        if matches.shape != (len(a),):
            raise EngineContractViolation(
                f"Comparator for column {column!r} returned "
                f"shape={matches.shape}, expected {(len(a),)}."
            )

        mismatch_mask = ~matches

        if not mismatch_mask.any():
            continue

        first_position = int(
            np.flatnonzero(mismatch_mask)[0]
        )

        value_a = a.iloc[first_position]
        value_b = b.iloc[first_position]

        max_abs_diff, max_rel_diff = (
            _numeric_diagnostics(
                a,
                b,
                mismatch_mask,
            )
        )

        result.column_divergences.append(
            ColumnDivergence(
                column=column,
                first_divergent_position=first_position,
                first_divergent_index_label=(
                    df_a.index[first_position]
                ),
                kind=_classify_divergence_kind(
                    value_a,
                    value_b,
                ),
                value_a=value_a,
                value_b=value_b,
                max_abs_diff=max_abs_diff,
                max_rel_diff=max_rel_diff,
            )
        )

        result.passed = False

    return result


# ============================================================================
# Truncation invariance
# ============================================================================

def verify_truncation_invariance(
    engine_factory: Callable[
        [],
        CausalEngineProtocol,
    ],
    df: pd.DataFrame,
    split_fractions: Sequence[float] = (
        0.10,
        0.25,
        0.50,
        0.75,
        0.90,
    ),
    additional_split_points: Optional[
        Sequence[int]
    ] = None,
    rtol: float = 0.0,
    atol: float = 0.0,
    dtype_mismatch_severity: str = "fatal",
    enforce_column_order: bool = True,
    analyze_kwargs: Optional[dict] = None,
    raise_on_failure: bool = True,
) -> List[TruncationAuditResult]:
    """
    Tests prefix/truncation invariance.

    For every split k:

        full = Engine().analyze(df)
        truncated = Engine().analyze(df.iloc[:k])

    The tested invariant is:

        full.iloc[:k] == truncated

    under the configured comparison policy.

    FAILURE INTERPRETATION
    ----------------------
    Failure means the prefix depends on suffix and/or batch-boundary
    context.

    The auditor deliberately does NOT automatically label every failure
    "look-ahead bias", because batch-size-dependent initialization and
    other boundary bugs can violate the same invariant.

    additional_split_points should include known module boundaries such
    as warm-up transitions or algorithm-specific state transitions.
    """

    _validate_dataframe_input(
        df,
        "df",
    )

    _validate_tolerances(
        rtol,
        atol,
    )

    _validate_dtype_severity(
        dtype_mismatch_severity
    )

    kwargs = dict(
        analyze_kwargs or {}
    )

    n = len(df)

    if n < 2:
        raise AuditConfigError(
            "Truncation audit requires at least 2 input rows."
        )

    candidate_splits: List[int] = []

    for fraction in split_fractions:

        if isinstance(
            fraction,
            (bool, np.bool_),
        ):
            raise AuditConfigError(
                "split fractions must be finite real numbers in (0,1)."
            )

        try:
            f = float(fraction)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise AuditConfigError(
                f"Invalid split fraction: {fraction!r}."
            ) from exc

        if (
            not np.isfinite(f)
            or not 0.0 < f < 1.0
        ):
            raise AuditConfigError(
                f"Split fraction must be finite and in (0,1). "
                f"Got {fraction!r}."
            )

        candidate_splits.append(
            int(n * f)
        )

    if additional_split_points is not None:

        for split in additional_split_points:

            if isinstance(
                split,
                (bool, np.bool_),
            ) or not isinstance(
                split,
                (int, np.integer),
            ):
                raise AuditConfigError(
                    "additional_split_points must contain integers."
                )

            candidate_splits.append(
                int(split)
            )

    split_points = sorted(
        set(candidate_splits)
    )

    invalid = [
        split
        for split in split_points
        if not 1 <= split <= n - 1
    ]

    if invalid:
        raise AuditConfigError(
            f"Invalid split points {invalid!r}. "
            f"For n={n}, each split must satisfy "
            f"1 <= split <= {n - 1}."
        )

    if not split_points:
        raise AuditConfigError(
            "No truncation split points were supplied/generated."
        )

    full_engine = _construct_engine(
        engine_factory,
        stage="full_run",
    )

    out_full = _execute_engine(
        full_engine,
        df,
        stage="full_run",
        analyze_kwargs=kwargs,
    )

    results: List[
        TruncationAuditResult
    ] = []

    for split_at in split_points:

        truncated_input = (
            df.iloc[:split_at]
            .copy()
        )

        truncated_engine = _construct_engine(
            engine_factory,
            stage=f"truncated_run:{split_at}",
        )

        out_truncated = _execute_engine(
            truncated_engine,
            truncated_input,
            stage=f"truncated_run:{split_at}",
            analyze_kwargs=kwargs,
        )

        expected_prefix = (
            out_full.iloc[:split_at]
        )

        comparison = _compare_dataframes(
            expected_prefix,
            out_truncated,
            label_a="full_run[:split_at]",
            label_b="truncated_run",
            rtol=rtol,
            atol=atol,
            dtype_mismatch_severity=dtype_mismatch_severity,
            enforce_column_order=enforce_column_order,
        )

        audit_result = (
            TruncationAuditResult(
                split_at=split_at,
                comparison=comparison,
            )
        )

        results.append(
            audit_result
        )

        if (
            raise_on_failure
            and not audit_result.passed
        ):
            raise CausalAuditError(
                "\n"
                + "=" * 72
                + "\nTRUNCATION INVARIANCE VIOLATION\n"
                + "=" * 72
                + "\n"
                + (
                    "The historical prefix changed when the "
                    "input suffix/batch boundary changed.\n"
                )
                + (
                    "Possible causes include future-data access, "
                    "global statistics, centered windows,\n"
                )
                + (
                    "negative shifts, batch-length dependence, "
                    "or boundary-dependent state.\n\n"
                )
                + audit_result.summary()
                + "\n"
                + "=" * 72
            )

    return results


# ============================================================================
# State isolation
# ============================================================================

def verify_state_isolation(
    engine_factory: Callable[
        [],
        CausalEngineProtocol,
    ],
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    policy: ReentrancyPolicy = (
        ReentrancyPolicy.IDEMPOTENT_REENTRANT
    ),
    expected_reuse_exception: Type[
        BaseException
    ] = EngineReuseError,
    rtol: float = 0.0,
    atol: float = 0.0,
    dtype_mismatch_severity: str = "fatal",
    enforce_column_order: bool = True,
    analyze_kwargs: Optional[dict] = None,
    raise_on_failure: bool = True,
) -> StateAuditResult:
    """
    Audits cross-call state independently from truncation causality.

    IDEMPOTENT_REENTRANT:
        1. fresh(A) vs fresh(A)
        2. same instance: A -> A
        3. fresh(B) vs isolated instance: A -> B

    MUST_RAISE_ON_REUSE:
        1. fresh(A) vs fresh(A)
        2. first call succeeds
        3. second call must raise exactly the expected exception family

    The repeat-call and contamination scenarios always use separate
    instances.
    """

    _validate_dataframe_input(
        df_a,
        "df_a",
    )

    _validate_dataframe_input(
        df_b,
        "df_b",
    )

    _validate_tolerances(
        rtol,
        atol,
    )

    _validate_dtype_severity(
        dtype_mismatch_severity
    )

    if not isinstance(
        policy,
        ReentrancyPolicy,
    ):
        raise AuditConfigError(
            "policy must be ReentrancyPolicy."
        )

    if (
        policy
        == ReentrancyPolicy.MUST_RAISE_ON_REUSE
    ):
        _validate_expected_exception(
            expected_reuse_exception
        )

    if df_a.equals(df_b):
        raise AuditConfigError(
            "df_a and df_b must not be identical for the "
            "A -> B contamination scenario."
        )

    kwargs = dict(
        analyze_kwargs or {}
    )

    def compare(
        a: pd.DataFrame,
        b: pd.DataFrame,
        label_a: str,
        label_b: str,
    ) -> DataFrameComparisonResult:

        return _compare_dataframes(
            a,
            b,
            label_a=label_a,
            label_b=label_b,
            rtol=rtol,
            atol=atol,
            dtype_mismatch_severity=dtype_mismatch_severity,
            enforce_column_order=enforce_column_order,
        )

    # ------------------------------------------------------------------
    # Fresh-instance determinism
    # ------------------------------------------------------------------

    deterministic_engine_1 = (
        _construct_engine(
            engine_factory,
            stage="determinism:fresh_1",
        )
    )

    deterministic_engine_2 = (
        _construct_engine(
            engine_factory,
            stage="determinism:fresh_2",
        )
    )

    deterministic_output_1 = (
        _execute_engine(
            deterministic_engine_1,
            df_a,
            stage="determinism:fresh_1",
            analyze_kwargs=kwargs,
        )
    )

    deterministic_output_2 = (
        _execute_engine(
            deterministic_engine_2,
            df_a,
            stage="determinism:fresh_2",
            analyze_kwargs=kwargs,
        )
    )

    determinism_result = compare(
        deterministic_output_1,
        deterministic_output_2,
        "fresh_instance_1",
        "fresh_instance_2",
    )

    repeated_result: Optional[
        DataFrameComparisonResult
    ] = None

    contamination_result: Optional[
        DataFrameComparisonResult
    ] = None

    reuse_raised: Optional[
        bool
    ] = None

    # ------------------------------------------------------------------
    # Explicit non-reusable contract
    # ------------------------------------------------------------------

    if (
        policy
        == ReentrancyPolicy.MUST_RAISE_ON_REUSE
    ):

        reuse_engine = _construct_engine(
            engine_factory,
            stage="reuse_contract",
        )

        # First call MUST succeed. Any failure is wrapped by
        # _execute_engine as EngineExecutionError.
        _execute_engine(
            reuse_engine,
            df_a,
            stage="reuse_contract:first_call",
            analyze_kwargs=kwargs,
        )

        try:
            _execute_engine(
                reuse_engine,
                df_b,
                stage="reuse_contract:second_call",
                analyze_kwargs=kwargs,
                passthrough_exception=expected_reuse_exception,
            )

        except expected_reuse_exception:
            reuse_raised = True

        except EngineExecutionError:
            # Wrong exception from the engine. Preserve the rich
            # execution failure instead of pretending this is a valid
            # reuse guard.
            raise

        else:
            reuse_raised = False

    # ------------------------------------------------------------------
    # Reentrant contract
    # ------------------------------------------------------------------

    elif (
        policy
        == ReentrancyPolicy.IDEMPOTENT_REENTRANT
    ):

        # A -> A uses its own isolated instance.
        repeat_engine = _construct_engine(
            engine_factory,
            stage="repeat_A_A",
        )

        repeated_output_1 = (
            _execute_engine(
                repeat_engine,
                df_a,
                stage="repeat_A_A:first_call",
                analyze_kwargs=kwargs,
            )
        )

        repeated_output_2 = (
            _execute_engine(
                repeat_engine,
                df_a,
                stage="repeat_A_A:second_call",
                analyze_kwargs=kwargs,
            )
        )

        repeated_result = compare(
            repeated_output_1,
            repeated_output_2,
            "same_instance_A_call_1",
            "same_instance_A_call_2",
        )

        # Fresh B baseline.
        baseline_b_engine = (
            _construct_engine(
                engine_factory,
                stage="contamination:fresh_B",
            )
        )

        baseline_b = _execute_engine(
            baseline_b_engine,
            df_b,
            stage="contamination:fresh_B",
            analyze_kwargs=kwargs,
        )

        # A -> B uses a completely separate instance.
        contamination_engine = (
            _construct_engine(
                engine_factory,
                stage="contamination:A_then_B",
            )
        )

        _execute_engine(
            contamination_engine,
            df_a,
            stage="contamination:A",
            analyze_kwargs=kwargs,
        )

        after_a_then_b = (
            _execute_engine(
                contamination_engine,
                df_b,
                stage="contamination:B_after_A",
                analyze_kwargs=kwargs,
            )
        )

        contamination_result = compare(
            baseline_b,
            after_a_then_b,
            "fresh_B",
            "B_after_A_same_instance",
        )

    result = StateAuditResult(
        policy=policy,
        determinism_result=determinism_result,
        repeated_call_result=repeated_result,
        contamination_result=contamination_result,
        reuse_raised_as_expected=reuse_raised,
    )

    if (
        raise_on_failure
        and not result.passed
    ):
        raise CausalAuditError(
            "\n"
            + "=" * 72
            + "\nSTATE ISOLATION AUDIT FAILED\n"
            + "=" * 72
            + "\n"
            + result.summary()
            + "\n"
            + "=" * 72
        )

    return result


# ============================================================================
# Self-verification
# ============================================================================

if __name__ == "__main__":

    rng = np.random.default_rng(7)

    n = 400

    demo_df = pd.DataFrame(
        {
            "close": (
                100.0
                + np.cumsum(
                    rng.normal(
                        0.0,
                        0.5,
                        n,
                    )
                )
            )
        }
    )

    demo_df_b = pd.DataFrame(
        {
            "close": (
                200.0
                + np.cumsum(
                    rng.normal(
                        0.0,
                        0.7,
                        n,
                    )
                )
            )
        }
    )

    # ==================================================================
    # Engines intentionally containing suffix/future dependencies
    # ==================================================================

    class CenteredLeakEngine:

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            out = df.copy()

            out["leak"] = (
                df["close"]
                .rolling(
                    window=21,
                    center=True,
                    min_periods=1,
                )
                .mean()
            )

            return out


    class GlobalStatLeakEngine:

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            out = df.copy()

            mean = df["close"].mean()
            std = df["close"].std()

            out["zscore"] = (
                (df["close"] - mean)
                / std
            )

            return out


    class ShiftLeakEngine:

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            out = df.copy()

            out["next_close"] = (
                df["close"].shift(-1)
            )

            return out


    class LastValueLeakEngine:

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            out = df.copy()

            values = (
                df["close"]
                .to_numpy()
                .copy()
            )

            if len(values) > 250:
                values[249] = values[-1]

            out["leak"] = values

            return out


    # ==================================================================
    # Boundary/batch dependency — deliberately NOT called future leakage
    # ==================================================================

    class BatchBoundaryDependencyEngine:
        """
        Synthetic boundary-dependence example.

        There is no future read here.

        The output depends explicitly on batch length.

        Default N=400 fractional splits:
            40, 100, 200, 300, 360

        therefore do not exercise input length 37.

        Targeting split=37 exposes the prefix instability.
        """

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            out = df.copy()

            values = (
                df["close"]
                .to_numpy()
                .copy()
            )

            if len(values) == 37:
                values[10] = 999999.0

            out["value"] = values

            return out


    # ==================================================================
    # Correct deterministic/reentrant engine
    # ==================================================================

    class CorrectEngine:

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            out = df.copy()

            # Trailing-only rolling statistic.
            out["causal_mean"] = (
                df["close"]
                .rolling(
                    window=21,
                    min_periods=1,
                )
                .mean()
            )

            return out


    # ==================================================================
    # State bugs
    # ==================================================================

    class ContaminatedEngine:

        def __init__(self) -> None:
            self.offset = 0.0

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            out = df.copy()

            out["value"] = (
                df["close"]
                + self.offset
            )

            self.offset += 1000.0

            return out


    class NonDeterministicEngine:

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            out = df.copy()

            # Deliberately new entropy per call.
            local_rng = (
                np.random.default_rng()
            )

            out["noise"] = (
                df["close"].to_numpy()
                + local_rng.normal(
                    0.0,
                    0.001,
                    len(df),
                )
            )

            return out


    class ProperReuseGuardEngine:

        def __init__(self) -> None:
            self.used = False

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            if self.used:
                raise EngineReuseError(
                    "Engine instance already used."
                )

            self.used = True

            out = df.copy()
            out["value"] = df["close"]

            return out


    class WrongReuseExceptionEngine:
        """
        First call succeeds.

        Second call deliberately raises the WRONG exception type.

        This specifically verifies that KeyError cannot masquerade as
        a valid EngineReuseError.
        """

        def __init__(self) -> None:
            self.used = False

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            if self.used:
                raise KeyError(
                    "wrong reuse exception"
                )

            self.used = True

            out = df.copy()
            out["value"] = df["close"]

            return out


    class FirstCallFailureEngine:

        def analyze(
            self,
            df: pd.DataFrame,
            **kwargs: Any,
        ) -> pd.DataFrame:

            raise ValueError(
                "deliberate first-call failure"
            )


    # ==================================================================
    # Test helpers
    # ==================================================================

    def assert_truncation_rejected(
        engine_factory: Callable[
            [],
            CausalEngineProtocol,
        ],
    ) -> None:

        try:
            verify_truncation_invariance(
                engine_factory,
                demo_df,
            )

        except CausalAuditError:
            return

        raise AssertionError(
            f"{engine_factory.__name__} "
            f"was expected to violate truncation invariance."
        )


    # ==================================================================
    # Test 1 — real suffix/future dependencies are rejected
    # ==================================================================

    assert_truncation_rejected(
        CenteredLeakEngine
    )

    assert_truncation_rejected(
        GlobalStatLeakEngine
    )

    assert_truncation_rejected(
        ShiftLeakEngine
    )

    assert_truncation_rejected(
        LastValueLeakEngine
    )


    # ==================================================================
    # Test 2 — correct causal engine passes
    # ==================================================================

    causal_results = (
        verify_truncation_invariance(
            CorrectEngine,
            demo_df,
        )
    )

    assert causal_results
    assert all(
        result.passed
        for result in causal_results
    )


    # ==================================================================
    # Test 3 — targeted boundary coverage
    # ==================================================================

    untargeted_results = (
        verify_truncation_invariance(
            BatchBoundaryDependencyEngine,
            demo_df,
            raise_on_failure=False,
        )
    )

    assert all(
        result.passed
        for result in untargeted_results
    ), (
        "Default split points unexpectedly exercised "
        "the synthetic boundary."
    )

    try:
        verify_truncation_invariance(
            BatchBoundaryDependencyEngine,
            demo_df,
            additional_split_points=[37],
        )

    except CausalAuditError:
        pass

    else:
        raise AssertionError(
            "Targeted split=37 failed to expose "
            "batch-boundary dependence."
        )


    # ==================================================================
    # Test 4 — state contamination
    # ==================================================================

    try:
        verify_state_isolation(
            ContaminatedEngine,
            demo_df,
            demo_df_b,
        )

    except CausalAuditError:
        pass

    else:
        raise AssertionError(
            "State-contaminated engine was not rejected."
        )


    # ==================================================================
    # Test 5 — non-determinism
    # ==================================================================

    try:
        verify_state_isolation(
            NonDeterministicEngine,
            demo_df,
            demo_df_b,
        )

    except CausalAuditError:
        pass

    else:
        raise AssertionError(
            "Non-deterministic engine was not rejected."
        )


    # ==================================================================
    # Test 6 — correct state behavior
    # ==================================================================

    clean_state_result = (
        verify_state_isolation(
            CorrectEngine,
            demo_df,
            demo_df_b,
        )
    )

    assert clean_state_result.passed


    # ==================================================================
    # Test 7 — correct explicit reuse guard
    # ==================================================================

    reuse_result = (
        verify_state_isolation(
            ProperReuseGuardEngine,
            demo_df,
            demo_df_b,
            policy=(
                ReentrancyPolicy.MUST_RAISE_ON_REUSE
            ),
        )
    )

    assert reuse_result.passed
    assert (
        reuse_result.reuse_raised_as_expected
        is True
    )


    # ==================================================================
    # Test 8 — wrong second-call exception MUST NOT count as success
    # ==================================================================

    try:
        verify_state_isolation(
            WrongReuseExceptionEngine,
            demo_df,
            demo_df_b,
            policy=(
                ReentrancyPolicy.MUST_RAISE_ON_REUSE
            ),
        )

    except EngineExecutionError as exc:

        assert (
            exc.stage
            == "reuse_contract:second_call"
        )

        assert isinstance(
            exc.original_exception,
            KeyError,
        )

    else:
        raise AssertionError(
            "Wrong reuse exception was incorrectly "
            "accepted as a valid reuse guard."
        )


    # ==================================================================
    # Test 9 — first-call engine failure gets audit context
    # ==================================================================

    try:
        verify_state_isolation(
            FirstCallFailureEngine,
            demo_df,
            demo_df_b,
        )

    except EngineExecutionError as exc:

        assert exc.stage.startswith(
            "determinism:"
        )

        assert isinstance(
            exc.original_exception,
            ValueError,
        )

    else:
        raise AssertionError(
            "Unexpected first-call engine failure "
            "was not wrapped by the auditor."
        )


    # ==================================================================
    # Test 10 — extension/string/datetime dtype comparison
    # ==================================================================

    extension_index = pd.RangeIndex(3)

    extension_a = pd.DataFrame(
        index=extension_index,
    )

    extension_a["string"] = pd.Series(
        ["A", pd.NA, "C"],
        dtype="string",
    )

    extension_a["nullable_int"] = pd.Series(
        [1, pd.NA, 3],
        dtype="Int64",
    )

    extension_a["nullable_float"] = pd.Series(
        [1.25, pd.NA, 3.50],
        dtype="Float64",
    )

    extension_a["nullable_bool"] = pd.Series(
        [True, pd.NA, False],
        dtype="boolean",
    )

    extension_a["datetime_naive"] = pd.Series(
        pd.to_datetime(
            [
                "2025-01-01",
                None,
                "2025-01-03",
            ]
        )
    )

    extension_a["datetime_utc"] = pd.Series(
        pd.to_datetime(
            [
                "2025-01-01T00:00:00Z",
                None,
                "2025-01-03T00:00:00Z",
            ],
            utc=True,
        )
    )

    extension_a["timedelta"] = pd.Series(
        pd.to_timedelta(
            [
                "1 day",
                None,
                "3 days",
            ]
        )
    )

    extension_a["category"] = pd.Series(
        pd.Categorical(
            [
                "bull",
                None,
                "bear",
            ],
            categories=[
                "bull",
                "bear",
            ],
        )
    )

    extension_b = extension_a.copy(
        deep=True
    )

    extension_comparison = (
        _compare_dataframes(
            extension_a,
            extension_b,
            label_a="extension_a",
            label_b="extension_b",
            rtol=0.0,
            atol=0.0,
            dtype_mismatch_severity="fatal",
            enforce_column_order=True,
        )
    )

    assert extension_comparison.passed


    # ==================================================================
    # Test 11 — nullable mismatch is actually detected
    # ==================================================================

    extension_bad = extension_a.copy(
        deep=True
    )

    extension_bad.loc[
        2,
        "nullable_int",
    ] = 999

    extension_bad_comparison = (
        _compare_dataframes(
            extension_a,
            extension_bad,
            label_a="extension_a",
            label_b="extension_bad",
            rtol=0.0,
            atol=0.0,
            dtype_mismatch_severity="fatal",
            enforce_column_order=True,
        )
    )

    assert not extension_bad_comparison.passed

    assert any(
        divergence.column
        == "nullable_int"
        for divergence
        in extension_bad_comparison.column_divergences
    )


    # ==================================================================
    # Test 12 — int64 precision must NOT be lost through float conversion
    # ==================================================================

    huge_integer = 2**53

    large_int_a = pd.DataFrame(
        {
            "x": np.array(
                [
                    huge_integer,
                    huge_integer + 2,
                ],
                dtype=np.int64,
            )
        }
    )

    large_int_b = large_int_a.copy()

    large_int_b.loc[
        1,
        "x",
    ] = huge_integer + 3

    integer_precision_test = (
        _compare_dataframes(
            large_int_a,
            large_int_b,
            label_a="large_int_a",
            label_b="large_int_b",
            rtol=0.0,
            atol=0.0,
            dtype_mismatch_severity="fatal",
            enforce_column_order=True,
        )
    )

    assert not integer_precision_test.passed, (
        "Distinct int64 values above float64 exact-integer "
        "precision were incorrectly treated as equal."
    )


    # ==================================================================
    # Test 13 — column order is contractually significant by default
    # ==================================================================

    ordered_a = pd.DataFrame(
        {
            "a": [1, 2],
            "b": [3, 4],
        }
    )

    ordered_b = ordered_a[
        ["b", "a"]
    ]

    ordering_result = (
        _compare_dataframes(
            ordered_a,
            ordered_b,
            label_a="ordered_a",
            label_b="ordered_b",
            rtol=0.0,
            atol=0.0,
            dtype_mismatch_severity="fatal",
            enforce_column_order=True,
        )
    )

    assert not ordering_result.passed


    # ==================================================================
    # Test 14 — invalid tolerances are rejected
    # ==================================================================

    for invalid_tolerance in (
        -1.0,
        np.nan,
        np.inf,
        -np.inf,
    ):

        try:
            verify_truncation_invariance(
                CorrectEngine,
                demo_df,
                atol=invalid_tolerance,
            )

        except AuditConfigError:
            pass

        else:
            raise AssertionError(
                f"Invalid tolerance "
                f"{invalid_tolerance!r} was accepted."
            )


    print(
        "=" * 72
    )
    print(
        "ALL MODULE 0.1 V3.1 SELF-VERIFICATION ASSERTIONS PASSED"
    )
    print(
        "Audited scope: primary DataFrame output only."
    )
    print(
        "=" * 72
    )

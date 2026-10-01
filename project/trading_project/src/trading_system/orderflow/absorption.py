"""
Layer 3 — Module 3.2
Causal Aggression / Price-Response / Absorption Evidence Engine
VERSION 1.1

Bar-level evidence only. Actual aggressor imbalance and contemporaneous OHLC
response do not reveal intrabar sequence; absorption evidence is not proof that
aggression occurred first and was then absorbed.

ACTUAL_AGGRESSOR and OHLCV_PROXY are explicit, separate schemas. Proxy outputs
never claim actual aggressor absorption. Signed direction, aligned response,
opposed response, and rank-space absorption evidence remain separate.

Absorption evidence alone cannot distinguish stalled/weak aligned response from
active movement against flow: both can have aligned magnitude zero. Consumers
must retain the separately exposed opposed magnitude/percentile. V1.1 adds no
hand-weighted correction.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import pandas as pd

from trading_system.core.causal_percentile import CausalPercentileTracker
from trading_system.orderflow.volume_delta import OrderFlowMode


class AbsorptionError(Exception):
    """Base exception for Module 3.2."""


class AbsorptionConfigError(AbsorptionError):
    """Invalid explicit mode configuration."""


class AbsorptionDataError(AbsorptionError):
    """Input/index/upstream-surface contract violation."""


_COMMON: Final[tuple[str, ...]] = (
    "absorption_mode", "signed_return", "absolute_return",
    "return_magnitude_percentile", "return_magnitude_history_count",
)
_ACTUAL: Final[tuple[str, ...]] = _COMMON + (
    "aggression_response_alignment", "aligned_response_magnitude",
    "aligned_response_percentile", "aligned_response_history_count",
    "opposed_response_magnitude", "opposed_response_percentile",
    "opposed_response_history_count", "aggression_extremeness",
    "response_weakness", "actual_absorption_evidence",
    "absorbed_aggression_side",
)
_PROXY: Final[tuple[str, ...]] = _COMMON + (
    "pressure_response_alignment", "pressure_aligned_response_magnitude",
    "pressure_aligned_response_percentile",
    "pressure_aligned_response_history_count",
    "pressure_opposed_response_magnitude",
    "pressure_opposed_response_percentile",
    "pressure_opposed_response_history_count", "proxy_pressure_extremeness",
    "proxy_response_weakness", "proxy_absorption_evidence", "pressure_side",
)


class CausalAbsorptionEvidenceEngine:
    """Stateless batch engine consuming a valid Module 3.1 mode surface."""

    def __init__(self, *, mode: OrderFlowMode) -> None:
        if not isinstance(mode, OrderFlowMode):
            raise AbsorptionConfigError("mode must be an explicit OrderFlowMode.")
        self.mode = mode

    @staticmethod
    def _base(df: pd.DataFrame, required: tuple[str, ...], outputs: tuple[str, ...]) -> None:
        if not isinstance(df, pd.DataFrame):
            raise AbsorptionDataError("df must be a pandas DataFrame.")
        if df.columns.has_duplicates:
            raise AbsorptionDataError("Duplicate columns are forbidden.")
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise AbsorptionDataError(f"Missing required columns: {missing!r}.")
        collisions = [c for c in outputs if c in df.columns]
        if collisions:
            raise AbsorptionDataError(f"Output columns already exist: {collisions!r}.")
        if df.index.has_duplicates:
            raise AbsorptionDataError("Duplicate index labels are forbidden.")
        if not df.index.is_monotonic_increasing:
            raise AbsorptionDataError("Index must already be monotonic increasing.")

    @staticmethod
    def _numeric(df: pd.DataFrame, columns: tuple[str, ...], allow_nan: bool = False) -> dict[str, np.ndarray]:
        result = {}
        for c in columns:
            s = df[c]
            if (
                pd.api.types.is_bool_dtype(s.dtype)
                or pd.api.types.is_complex_dtype(s.dtype)
                or not pd.api.types.is_numeric_dtype(s.dtype)
            ):
                raise AbsorptionDataError(f"Column {c!r} must be real numeric.")
            a = s.to_numpy(dtype=np.float64, na_value=np.nan)
            if np.isinf(a).any() or (not allow_nan and np.isnan(a).any()):
                raise AbsorptionDataError(f"Column {c!r} has invalid non-finite values.")
            result[c] = a
        return result

    @staticmethod
    def _validate_percentile(values: np.ndarray, name: str) -> None:
        finite = np.isfinite(values)
        if ((values[finite] < 0.0) | (values[finite] > 1.0)).any():
            raise AbsorptionDataError(f"Column {name!r} must lie in [0,1] when finite.")

    @classmethod
    def _validate_magnitude_history_contract(
        cls,
        magnitude: np.ndarray,
        percentile: np.ndarray,
        count_series: pd.Series,
        *,
        label: str,
    ) -> None:
        dtype = count_series.dtype
        if (
            pd.api.types.is_bool_dtype(dtype)
            or pd.api.types.is_complex_dtype(dtype)
            or not pd.api.types.is_numeric_dtype(dtype)
        ):
            raise AbsorptionDataError(f"{label} history count must be numeric integer data.")
        counts = count_series.to_numpy(dtype=np.float64, na_value=np.nan)
        if (
            not np.isfinite(counts).all()
            or (counts < 0.0).any()
            or (counts != np.floor(counts)).any()
        ):
            raise AbsorptionDataError(
                f"{label} history count must contain finite non-negative integers."
            )

        expected = 0
        for i in range(len(magnitude)):
            if counts[i] != expected:
                raise AbsorptionDataError(
                    f"{label} history count is inconsistent at row {i}."
                )
            magnitude_finite = math.isfinite(float(magnitude[i]))
            percentile_finite = math.isfinite(float(percentile[i]))
            if not magnitude_finite and percentile_finite:
                raise AbsorptionDataError(
                    f"{label} percentile must be NaN when magnitude is undefined."
                )
            if expected == 0 and percentile_finite:
                raise AbsorptionDataError(
                    f"{label} percentile must be NaN with empty prior history."
                )
            if magnitude_finite and expected > 0:
                if not percentile_finite or not 0.0 <= percentile[i] <= 1.0:
                    raise AbsorptionDataError(
                        f"{label} percentile must be finite in [0,1] when comparable."
                    )
            if magnitude_finite:
                expected += 1

    @staticmethod
    def _returns(close: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        n = len(close)
        signed = np.full(n, np.nan)
        for i in range(1, n):
            if close[i] > 0.0 and close[i - 1] > 0.0:
                value = math.log(close[i]) - math.log(close[i - 1])
                if not math.isfinite(value):
                    raise AbsorptionDataError(
                        f"Generated log return is non-finite at row {i}."
                    )
                signed[i] = value
        absolute = np.abs(signed)
        tracker = CausalPercentileTracker(nan_policy="skip")
        pct = np.full(n, np.nan)
        count = np.zeros(n, dtype=np.int64)
        for i, value in enumerate(absolute):
            observation = tracker.observe(float(value))
            pct[i] = observation.percentile
            count[i] = observation.sample_count
        return signed, absolute, pct, count

    @staticmethod
    def _response_context(
        flow: np.ndarray, signed_return: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        n = len(flow)
        alignment = np.full(n, np.nan)
        aligned = np.full(n, np.nan)
        opposed = np.full(n, np.nan)
        aligned_pct = np.full(n, np.nan)
        opposed_pct = np.full(n, np.nan)
        aligned_n = np.zeros(n, dtype=np.int64)
        opposed_n = np.zeros(n, dtype=np.int64)
        aligned_tracker = CausalPercentileTracker(nan_policy="skip")
        opposed_tracker = CausalPercentileTracker(nan_policy="skip")
        for i in range(n):
            if math.isfinite(flow[i]) and flow[i] != 0.0 and math.isfinite(signed_return[i]):
                product = math.copysign(1.0, flow[i]) * signed_return[i]
                alignment[i] = product
                aligned[i] = max(product, 0.0)
                opposed[i] = max(-product, 0.0)
            a = aligned_tracker.observe(float(aligned[i]))
            o = opposed_tracker.observe(float(opposed[i]))
            aligned_pct[i] = a.percentile
            opposed_pct[i] = o.percentile
            aligned_n[i] = a.sample_count
            opposed_n[i] = o.sample_count
        return alignment, aligned, aligned_pct, aligned_n, opposed, opposed_pct, opposed_n

    @staticmethod
    def _mode_column(df: pd.DataFrame, expected: OrderFlowMode) -> None:
        values = df["order_flow_mode"]
        if values.isna().any() or not (values.astype(str) == expected.value).all():
            raise AbsorptionDataError(f"order_flow_mode must be {expected.value!r} on every row.")

    def _actual(self, df: pd.DataFrame) -> pd.DataFrame:
        required = (
            "close", "delta_ratio", "delta_magnitude",
            "delta_magnitude_percentile", "delta_magnitude_history_count",
            "total_classified_volume", "order_flow_mode",
        )
        self._base(df, required, _ACTUAL)
        self._mode_column(df, OrderFlowMode.ACTUAL_AGGRESSOR)
        a = self._numeric(
            df,
            ("close", "delta_ratio", "delta_magnitude", "delta_magnitude_percentile", "total_classified_volume"),
            allow_nan=True,
        )
        close, flow, magnitude, extremeness, total = (
            a["close"], a["delta_ratio"], a["delta_magnitude"],
            a["delta_magnitude_percentile"], a["total_classified_volume"],
        )
        if np.isnan(close).any() or (total < 0).any() or np.isnan(total).any():
            raise AbsorptionDataError("close/total_classified_volume semantics are invalid.")
        finite_flow = np.isfinite(flow)
        if ((flow[finite_flow] < -1) | (flow[finite_flow] > 1)).any():
            raise AbsorptionDataError("delta_ratio must lie in [-1,1].")
        if not np.array_equal(np.isnan(flow), total == 0.0):
            raise AbsorptionDataError("delta_ratio NaN must correspond exactly to zero total volume.")
        if not np.allclose(magnitude[finite_flow], np.abs(flow[finite_flow]), rtol=0, atol=0):
            raise AbsorptionDataError("delta_magnitude is inconsistent with delta_ratio.")
        if not np.isnan(magnitude[~finite_flow]).all():
            raise AbsorptionDataError("Undefined delta_ratio requires undefined magnitude.")
        self._validate_percentile(extremeness, "delta_magnitude_percentile")
        self._validate_magnitude_history_contract(
            magnitude,
            extremeness,
            df["delta_magnitude_history_count"],
            label="delta_magnitude",
        )

        signed, absolute, return_pct, return_n = self._returns(close)
        alignment, aligned, aligned_pct, aligned_n, opposed, opposed_pct, opposed_n = self._response_context(flow, signed)
        weakness = np.where(np.isfinite(aligned_pct), 1.0 - aligned_pct, np.nan)
        evidence = np.where(
            np.isfinite(extremeness) & np.isfinite(weakness),
            extremeness * weakness,
            np.nan,
        )
        side = np.full(len(df), "NONE", dtype=object)
        side[np.isfinite(evidence) & (flow > 0)] = "BUY"
        side[np.isfinite(evidence) & (flow < 0)] = "SELL"

        out = df.copy(deep=True)
        out["absorption_mode"] = pd.array([self.mode.value] * len(df), dtype="string")
        out["signed_return"] = signed
        out["absolute_return"] = absolute
        out["return_magnitude_percentile"] = return_pct
        out["return_magnitude_history_count"] = return_n
        out["aggression_response_alignment"] = alignment
        out["aligned_response_magnitude"] = aligned
        out["aligned_response_percentile"] = aligned_pct
        out["aligned_response_history_count"] = aligned_n
        out["opposed_response_magnitude"] = opposed
        out["opposed_response_percentile"] = opposed_pct
        out["opposed_response_history_count"] = opposed_n
        out["aggression_extremeness"] = extremeness
        out["response_weakness"] = weakness
        out["actual_absorption_evidence"] = evidence
        out["absorbed_aggression_side"] = pd.array(side, dtype="string")
        return out

    def _proxy(self, df: pd.DataFrame) -> pd.DataFrame:
        required = (
            "open", "high", "low", "close", "volume", "close_location_proxy",
            "volume_pressure_proxy", "pressure_magnitude",
            "pressure_magnitude_percentile", "pressure_magnitude_history_count",
            "order_flow_mode",
        )
        self._base(df, required, _PROXY)
        self._mode_column(df, OrderFlowMode.OHLCV_PROXY)
        a = self._numeric(
            df,
            ("open", "high", "low", "close", "volume", "close_location_proxy",
             "volume_pressure_proxy", "pressure_magnitude", "pressure_magnitude_percentile"),
            allow_nan=True,
        )
        open_, high, low, close, volume = a["open"], a["high"], a["low"], a["close"], a["volume"]
        if np.isnan(open_).any() or np.isnan(high).any() or np.isnan(low).any() or np.isnan(close).any() or np.isnan(volume).any():
            raise AbsorptionDataError("OHLCV must be finite.")
        if (volume < 0).any() or (high < low).any() or ((open_ < low) | (open_ > high)).any() or ((close < low) | (close > high)).any():
            raise AbsorptionDataError("Malformed OHLCV geometry/volume.")
        location, pressure, magnitude, extremeness = (
            a["close_location_proxy"], a["volume_pressure_proxy"],
            a["pressure_magnitude"], a["pressure_magnitude_percentile"],
        )
        bar_range = high - low
        expected_location = np.divide(
            2*close-high-low, bar_range, out=np.full(len(df), np.nan), where=bar_range>0
        )
        if not np.allclose(location, expected_location, rtol=0, atol=0, equal_nan=True):
            raise AbsorptionDataError("close_location_proxy is inconsistent.")
        expected_pressure = np.where(volume > 0, location, np.nan)
        if not np.allclose(pressure, expected_pressure, rtol=0, atol=0, equal_nan=True):
            raise AbsorptionDataError("volume_pressure_proxy is inconsistent.")
        if not np.allclose(magnitude, np.abs(pressure), rtol=0, atol=0, equal_nan=True):
            raise AbsorptionDataError("pressure_magnitude is inconsistent.")
        self._validate_percentile(extremeness, "pressure_magnitude_percentile")
        self._validate_magnitude_history_contract(
            magnitude,
            extremeness,
            df["pressure_magnitude_history_count"],
            label="pressure_magnitude",
        )

        signed, absolute, return_pct, return_n = self._returns(close)
        alignment, aligned, aligned_pct, aligned_n, opposed, opposed_pct, opposed_n = self._response_context(pressure, signed)
        weakness = np.where(np.isfinite(aligned_pct), 1.0 - aligned_pct, np.nan)
        evidence = np.where(
            np.isfinite(extremeness) & np.isfinite(weakness),
            extremeness * weakness,
            np.nan,
        )
        side = np.full(len(df), "NONE", dtype=object)
        side[np.isfinite(evidence) & (pressure > 0)] = "POSITIVE"
        side[np.isfinite(evidence) & (pressure < 0)] = "NEGATIVE"

        out = df.copy(deep=True)
        out["absorption_mode"] = pd.array([self.mode.value] * len(df), dtype="string")
        out["signed_return"] = signed
        out["absolute_return"] = absolute
        out["return_magnitude_percentile"] = return_pct
        out["return_magnitude_history_count"] = return_n
        out["pressure_response_alignment"] = alignment
        out["pressure_aligned_response_magnitude"] = aligned
        out["pressure_aligned_response_percentile"] = aligned_pct
        out["pressure_aligned_response_history_count"] = aligned_n
        out["pressure_opposed_response_magnitude"] = opposed
        out["pressure_opposed_response_percentile"] = opposed_pct
        out["pressure_opposed_response_history_count"] = opposed_n
        out["proxy_pressure_extremeness"] = extremeness
        out["proxy_response_weakness"] = weakness
        out["proxy_absorption_evidence"] = evidence
        out["pressure_side"] = pd.array(side, dtype="string")
        return out

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        return self._actual(df) if self.mode is OrderFlowMode.ACTUAL_AGGRESSOR else self._proxy(df)


class _ActualAbsorptionAuditEngine(CausalAbsorptionEvidenceEngine):
    def __init__(self) -> None:
        super().__init__(mode=OrderFlowMode.ACTUAL_AGGRESSOR)


class _ProxyAbsorptionAuditEngine(CausalAbsorptionEvidenceEngine):
    def __init__(self) -> None:
        super().__init__(mode=OrderFlowMode.OHLCV_PROXY)

"""
Layer 3 — Module 3.1
Causal Volume Delta / Order-Flow Evidence Engine
VERSION 1.1 — Rebuilt From Scratch

Two explicit modes exist and are never auto-selected.

ACTUAL_AGGRESSOR uses caller-supplied aggressive buy/sell volumes. "Actual"
means actual according to upstream feed semantics; this engine cannot verify
trade classification or whether volume units are base, quote, or notional.

OHLCV_PROXY emits completed-bar price-location/volume-pressure geometry. It is
not true delta and never reconstructs buy/sell volume. For volume>0,
`volume_pressure_proxy` equals `close_location_proxy`; volume is only an
information-availability gate, not relative-volume magnitude. The separate
`signed_volume_pressure_raw=volume*close_location_proxy` contains raw volume
magnitude and retains the input volume unit.

V1.1 requires source volumes and derived raw arithmetic (classified sum,
difference, and defined signed pressure multiplication) to remain representable
as finite float64. No clipping, rescaling, or infinity replacement occurs.

All empirical contexts use Module 0.2 read-before-push expanding history. No
threshold, rolling horizon, divergence, CVD, or session reset is included.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

import numpy as np
import pandas as pd

from trading_system.core.causal_percentile import CausalPercentileTracker


class VolumeDeltaError(Exception):
    """Base exception for Module 3.1."""


class VolumeDeltaConfigError(VolumeDeltaError):
    """Invalid explicit engine configuration."""


class VolumeDeltaDataError(VolumeDeltaError):
    """Input/index/schema/data contract violation."""


class OrderFlowMode(Enum):
    ACTUAL_AGGRESSOR = "ACTUAL_AGGRESSOR"
    OHLCV_PROXY = "OHLCV_PROXY"


_ACTUAL_DERIVED: Final[tuple[str, ...]] = (
    "order_flow_mode", "total_classified_volume", "raw_delta", "delta_ratio",
    "delta_ratio_percentile", "delta_ratio_history_count", "delta_magnitude",
    "delta_magnitude_percentile", "delta_magnitude_history_count",
)
_PROXY_DERIVED: Final[tuple[str, ...]] = (
    "order_flow_mode", "close_location_proxy", "volume_pressure_proxy",
    "signed_volume_pressure_raw", "pressure_proxy_percentile",
    "pressure_proxy_history_count", "pressure_magnitude",
    "pressure_magnitude_percentile", "pressure_magnitude_history_count",
)


class CausalVolumeDeltaEngine:
    """Stateless causal batch engine with an explicit fixed mode per instance."""

    def __init__(
        self,
        *,
        mode: OrderFlowMode,
        reconcile_total_volume: bool = False,
    ) -> None:
        if not isinstance(mode, OrderFlowMode):
            raise VolumeDeltaConfigError("mode must be an explicit OrderFlowMode.")
        if not isinstance(reconcile_total_volume, bool):
            raise VolumeDeltaConfigError("reconcile_total_volume must be boolean.")
        if mode is OrderFlowMode.OHLCV_PROXY and reconcile_total_volume:
            raise VolumeDeltaConfigError(
                "reconcile_total_volume applies only to ACTUAL_AGGRESSOR mode."
            )
        self.mode = mode
        self.reconcile_total_volume = reconcile_total_volume

    @staticmethod
    def _base_validate(df: pd.DataFrame, required: tuple[str, ...], outputs: tuple[str, ...]) -> None:
        if not isinstance(df, pd.DataFrame):
            raise VolumeDeltaDataError("df must be a pandas DataFrame.")
        if df.columns.has_duplicates:
            raise VolumeDeltaDataError("Duplicate columns are forbidden.")
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise VolumeDeltaDataError(f"Missing required columns: {missing!r}.")
        collisions = [c for c in outputs if c in df.columns]
        if collisions:
            raise VolumeDeltaDataError(
                f"Derived output columns already exist: {collisions!r}."
            )
        if df.index.has_duplicates:
            raise VolumeDeltaDataError("Duplicate index labels are forbidden.")
        if not df.index.is_monotonic_increasing:
            raise VolumeDeltaDataError("Index must already be monotonic increasing.")

    @staticmethod
    def _real_finite(df: pd.DataFrame, columns: tuple[str, ...]) -> dict[str, np.ndarray]:
        result = {}
        for c in columns:
            s = df[c]
            if (
                pd.api.types.is_bool_dtype(s.dtype)
                or pd.api.types.is_complex_dtype(s.dtype)
                or not pd.api.types.is_numeric_dtype(s.dtype)
            ):
                raise VolumeDeltaDataError(f"Column {c!r} must be real numeric.")
            a = s.to_numpy(dtype=np.float64, na_value=np.nan)
            if not np.isfinite(a).all():
                raise VolumeDeltaDataError(f"Column {c!r} contains NaN or infinity.")
            result[c] = a
        return result

    @staticmethod
    def _contexts(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        signed_tracker = CausalPercentileTracker(nan_policy="skip")
        magnitude_tracker = CausalPercentileTracker(nan_policy="skip")
        n = len(values)
        signed_pct = np.full(n, np.nan)
        signed_count = np.zeros(n, dtype=np.int64)
        magnitude = np.abs(values)
        magnitude_pct = np.full(n, np.nan)
        magnitude_count = np.zeros(n, dtype=np.int64)
        for i, value in enumerate(values):
            signed = signed_tracker.observe(float(value))
            mag = magnitude_tracker.observe(float(magnitude[i]))
            signed_pct[i] = signed.percentile
            signed_count[i] = signed.sample_count
            magnitude_pct[i] = mag.percentile
            magnitude_count[i] = mag.sample_count
        return signed_pct, signed_count, magnitude_pct, magnitude_count

    def _analyze_actual(self, df: pd.DataFrame) -> pd.DataFrame:
        required = ("buy_volume", "sell_volume") + (
            ("volume",) if self.reconcile_total_volume else ()
        )
        outputs = _ACTUAL_DERIVED + (
            ("classified_volume_fraction",) if self.reconcile_total_volume else ()
        )
        self._base_validate(df, required, outputs)
        arrays = self._real_finite(df, required)
        buy, sell = arrays["buy_volume"], arrays["sell_volume"]
        if (buy < 0).any() or (sell < 0).any():
            raise VolumeDeltaDataError("buy_volume/sell_volume must be non-negative.")
        with np.errstate(over="ignore", invalid="ignore"):
            total = buy + sell
            raw_delta = buy - sell
        if not np.isfinite(total).all():
            raise VolumeDeltaDataError("Classified volume sum overflowed.")
        if not np.isfinite(raw_delta).all():
            raise VolumeDeltaDataError("Raw delta difference overflowed.")
        ratio = np.divide(
            raw_delta, total, out=np.full(len(df), np.nan), where=total > 0.0
        )
        ratio_pct, ratio_n, magnitude_pct, magnitude_n = self._contexts(ratio)

        out = df.copy(deep=True)
        out["order_flow_mode"] = pd.array(
            [OrderFlowMode.ACTUAL_AGGRESSOR.value] * len(df), dtype="string"
        )
        out["total_classified_volume"] = total
        out["raw_delta"] = raw_delta
        out["delta_ratio"] = ratio
        out["delta_ratio_percentile"] = ratio_pct
        out["delta_ratio_history_count"] = ratio_n
        out["delta_magnitude"] = np.abs(ratio)
        out["delta_magnitude_percentile"] = magnitude_pct
        out["delta_magnitude_history_count"] = magnitude_n
        if self.reconcile_total_volume:
            volume = arrays["volume"]
            if (volume < 0).any():
                raise VolumeDeltaDataError("volume must be non-negative.")
            out["classified_volume_fraction"] = np.divide(
                total, volume, out=np.full(len(df), np.nan), where=volume > 0.0
            )
        return out

    @staticmethod
    def _signed_pressure_raw(volume: np.ndarray, location: np.ndarray) -> np.ndarray:
        with np.errstate(over="ignore", invalid="ignore"):
            result = volume * location
        defined = np.isfinite(location)
        if not np.isfinite(result[defined]).all():
            raise VolumeDeltaDataError("signed_volume_pressure_raw overflowed.")
        return result

    def _analyze_proxy(self, df: pd.DataFrame) -> pd.DataFrame:
        required = ("open", "high", "low", "close", "volume")
        self._base_validate(df, required, _PROXY_DERIVED)
        a = self._real_finite(df, required)
        open_, high, low, close, volume = (
            a["open"], a["high"], a["low"], a["close"], a["volume"]
        )
        if (volume < 0).any():
            raise VolumeDeltaDataError("volume must be non-negative.")
        if (high < low).any():
            raise VolumeDeltaDataError("high < low detected.")
        if ((open_ < low) | (open_ > high)).any():
            raise VolumeDeltaDataError("open lies outside [low, high].")
        if ((close < low) | (close > high)).any():
            raise VolumeDeltaDataError("close lies outside [low, high].")

        bar_range = high - low
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            location = np.divide(
                2.0 * close - high - low,
                bar_range,
                out=np.full(len(df), np.nan),
                where=bar_range > 0.0,
            )
        defined_range = bar_range > 0.0
        if not np.isfinite(location[defined_range]).all():
            raise VolumeDeltaDataError("close_location_proxy arithmetic overflowed.")
        pressure = np.where(volume > 0.0, location, np.nan)
        signed_raw = self._signed_pressure_raw(volume, location)
        pressure_pct, pressure_n, magnitude_pct, magnitude_n = self._contexts(pressure)

        out = df.copy(deep=True)
        out["order_flow_mode"] = pd.array(
            [OrderFlowMode.OHLCV_PROXY.value] * len(df), dtype="string"
        )
        out["close_location_proxy"] = location
        out["volume_pressure_proxy"] = pressure
        out["signed_volume_pressure_raw"] = signed_raw
        out["pressure_proxy_percentile"] = pressure_pct
        out["pressure_proxy_history_count"] = pressure_n
        out["pressure_magnitude"] = np.abs(pressure)
        out["pressure_magnitude_percentile"] = magnitude_pct
        out["pressure_magnitude_history_count"] = magnitude_n
        return out

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.mode is OrderFlowMode.ACTUAL_AGGRESSOR:
            return self._analyze_actual(df)
        return self._analyze_proxy(df)


class _ActualAuditEngine(CausalVolumeDeltaEngine):
    def __init__(self) -> None:
        super().__init__(mode=OrderFlowMode.ACTUAL_AGGRESSOR)


class _ProxyAuditEngine(CausalVolumeDeltaEngine):
    def __init__(self) -> None:
        super().__init__(mode=OrderFlowMode.OHLCV_PROXY)

# -*- coding: utf-8 -*-
"""Unified, auditable market-data access.

The analysis engine must never silently change an invalid timeframe, mix
exchanges, or analyse a still-forming candle.  This module therefore:

* supports explicit exchange selection (or an explicit ``auto`` fallback);
* validates every timeframe before making an HTTP request;
* normalises, sorts and de-duplicates all exchange responses;
* removes open candles by default;
* records a structured fetch report that the CLI/Web/Telegram UIs can show.

Public OHLCV endpoints do not require exchange API keys.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from config import Config

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:  # optional dependency
    yf = None
    YF_AVAILABLE = False


class DataManagerError(ValueError):
    """User-correctable market data error (symbol/timeframe/exchange)."""


@dataclass(frozen=True)
class ExchangeSpec:
    key: str
    label: str
    fetcher_name: str


class DataManager:
    EXCHANGES = (
        ExchangeSpec("okx", "OKX", "_fetch_okx_paginated"),
        ExchangeSpec("binance", "Binance", "_fetch_binance"),
        ExchangeSpec("kucoin", "KuCoin", "_fetch_kucoin"),
        ExchangeSpec("gate", "Gate.io", "_fetch_gate"),
        ExchangeSpec("bybit", "Bybit", "_fetch_bybit"),
        ExchangeSpec("mexc", "MEXC", "_fetch_mexc"),
    )
    EXCHANGE_ALIASES = {
        "auto": "auto", "okx": "okx", "binance": "binance",
        "kucoin": "kucoin", "ku coin": "kucoin", "gate": "gate",
        "gate.io": "gate", "gateio": "gate", "bybit": "bybit",
        "mexc": "mexc", "yahoo": "yahoo",
    }
    # Canonical values.  1m is one minute; 1M is one calendar month.
    VALID_TIMEFRAMES = (
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "1w", "1M",
    )
    TF_SECONDS = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
        "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600,
        "8h": 28800, "12h": 43200, "1d": 86400, "1w": 604800,
        "1M": 31 * 86400,  # conservative only; APIs provide better flags where available
    }

    def __init__(self, default_exchange: str | None = None):
        self.logger = logging.getLogger("DataManager")
        self.okx_base = "https://www.okx.com"
        self.binance_base = "https://api.binance.com"
        self.kucoin_base = "https://api.kucoin.com"
        self.gate_base = "https://api.gateio.ws"
        self.bybit_base = "https://api.bybit.com"
        self.mexc_base = "https://api.mexc.com"
        self.default_exchange = self.normalize_exchange(
            default_exchange or getattr(Config, "DEFAULT_EXCHANGE", "auto")
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ICT-Audit-Bot/7.0"})
        self._cache: dict[str, tuple[float, Any]] = {}
        self.last_fetch_report: dict[str, Any] = {}
        self.logger.info("DataManager V7 ready - explicit exchange + closed candles")

    # ------------------------------------------------------------------
    # Public metadata / normalisation
    # ------------------------------------------------------------------
    @classmethod
    def supported_exchanges(cls) -> list[dict[str, str]]:
        return [{"key": s.key, "label": s.label} for s in cls.EXCHANGES]

    @classmethod
    def normalize_exchange(cls, exchange: str | None) -> str:
        raw = str(exchange or "auto").strip().lower()
        key = cls.EXCHANGE_ALIASES.get(raw)
        if not key:
            allowed = "auto, " + ", ".join(s.key for s in cls.EXCHANGES)
            raise DataManagerError(f"منصة غير مدعومة: {exchange!r}. الخيارات: {allowed}")
        return key

    @classmethod
    def normalize_timeframe(cls, timeframe: str | None) -> str:
        raw = str(timeframe or Config.DEFAULT_TIMEFRAME).strip()
        aliases = {
            "60m": "1h", "240m": "4h", "d": "1d", "day": "1d",
            "daily": "1d", "w": "1w", "week": "1w", "weekly": "1w",
            "1mo": "1M", "1month": "1M", "monthly": "1M",
        }
        if raw == "1M":
            value = "1M"
        else:
            value = aliases.get(raw.lower(), raw.lower())
        if value not in cls.VALID_TIMEFRAMES:
            raise DataManagerError(
                f"فريم غير صالح: {timeframe!r}. المسموح: {', '.join(cls.VALID_TIMEFRAMES)}"
            )
        return value

    @staticmethod
    def _split_symbol(symbol: str) -> tuple[str, str]:
        clean = str(symbol or "").strip().upper().replace("_", "/").replace("-", "/")
        if "/" in clean:
            parts = [p for p in clean.split("/") if p]
            if len(parts) == 2:
                return parts[0], parts[1]
        compact = clean.replace("/", "")
        for quote in ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB"):
            if compact.endswith(quote) and len(compact) > len(quote):
                return compact[:-len(quote)], quote
        raise DataManagerError(
            f"رمز الزوج غير مفهوم: {symbol!r}. اكتب مثلاً ETH/USDT أو ETHUSDT"
        )

    @classmethod
    def normalize_symbol(cls, symbol: str | None) -> str:
        base, quote = cls._split_symbol(symbol or Config.DEFAULT_SYMBOL)
        return f"{base}/{quote}"

    @classmethod
    def _is_crypto(cls, symbol: str) -> bool:
        try:
            _, quote = cls._split_symbol(symbol)
            return quote in {"USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB"}
        except DataManagerError:
            return False

    @classmethod
    def _compact_symbol(cls, symbol: str) -> str:
        base, quote = cls._split_symbol(symbol)
        return base + quote

    @classmethod
    def _dash_symbol(cls, symbol: str) -> str:
        base, quote = cls._split_symbol(symbol)
        return f"{base}-{quote}"

    @classmethod
    def _underscore_symbol(cls, symbol: str) -> str:
        base, quote = cls._split_symbol(symbol)
        return f"{base}_{quote}"

    # backwards-compatible helpers
    _clean_symbol = _compact_symbol
    _to_binance_symbol = _compact_symbol
    _to_bybit_symbol = _compact_symbol
    _to_okx_inst_id = _dash_symbol
    _to_kucoin_symbol = _dash_symbol
    _to_gate_pair = _underscore_symbol

    # ------------------------------------------------------------------
    # Strict timeframe maps (never silently substitute 15m)
    # ------------------------------------------------------------------
    @staticmethod
    def _map_tf(tf: str, mapping: dict[str, str], exchange: str) -> str:
        if tf not in mapping:
            raise DataManagerError(f"الفريم {tf} غير مدعوم على {exchange}")
        return mapping[tf]

    def _convert_tf_binance(self, tf: str) -> str:
        mapping = {x: x for x in (
            "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
            "6h", "8h", "12h", "1d", "1w", "1M"
        )}
        return self._map_tf(tf, mapping, "Binance/MEXC")

    def _convert_tf_okx(self, tf: str) -> str:
        mapping = {
            "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
            "30m": "30m", "1h": "1H", "2h": "2H", "4h": "4H",
            "6h": "6Hutc", "12h": "12Hutc", "1d": "1Dutc",
            "1w": "1Wutc", "1M": "1Mutc",
        }
        return self._map_tf(tf, mapping, "OKX")

    def _convert_tf_kucoin(self, tf: str) -> str:
        mapping = {
            "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
            "30m": "30min", "1h": "1hour", "2h": "2hour", "4h": "4hour",
            "6h": "6hour", "8h": "8hour", "12h": "12hour",
            "1d": "1day", "1w": "1week",
        }
        return self._map_tf(tf, mapping, "KuCoin")

    def _convert_tf_gate(self, tf: str) -> str:
        mapping = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "2h": "2h", "4h": "4h", "8h": "8h",
            "1d": "1d", "1w": "7d", "1M": "30d",
        }
        return self._map_tf(tf, mapping, "Gate.io")

    def _convert_tf_bybit(self, tf: str) -> str:
        mapping = {
            "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
            "1h": "60", "2h": "120", "4h": "240", "6h": "360",
            "12h": "720", "1d": "D", "1w": "W", "1M": "M",
        }
        return self._map_tf(tf, mapping, "Bybit")

    # ------------------------------------------------------------------
    # Cache + request helpers
    # ------------------------------------------------------------------
    def _get_cache(self, key: str, ttl: int = 30):
        item = self._cache.get(key)
        if item and time.time() - item[0] < ttl:
            return item[1]
        return None

    def _set_cache(self, key: str, value: Any):
        self._cache[key] = (time.time(), value)

    @staticmethod
    def _json_or_error(resp: requests.Response, exchange: str) -> Any:
        try:
            payload = resp.json()
        except Exception as exc:
            raise DataManagerError(f"{exchange}: رد غير صالح HTTP {resp.status_code}") from exc
        if resp.status_code != 200:
            msg = payload.get("msg") if isinstance(payload, dict) else str(payload)[:160]
            raise DataManagerError(f"{exchange}: HTTP {resp.status_code} - {msg}")
        return payload

    def _finalize_rows(
        self, rows: list[dict[str, Any]], symbol: str, timeframe: str,
        source: str, limit: int, closed_only: bool = True,
    ) -> dict[str, Any] | None:
        """Sort, deduplicate, validate OHLC and remove an open last candle."""
        now_ms = int(time.time() * 1000)
        tf_ms = self.TF_SECONDS[timeframe] * 1000
        by_ts: dict[int, dict[str, Any]] = {}
        dropped_open = 0
        dropped_invalid = 0
        for raw in rows:
            try:
                row = dict(raw)
                ts = int(float(row["ts"]))
                o, h, l, c, v = (float(row[k]) for k in ("o", "h", "l", "c", "v"))
                close_ts = int(float(row.get("close_ts", ts + tf_ms - 1)))
                explicitly_closed = row.get("closed")
                is_closed = bool(explicitly_closed) if explicitly_closed is not None else close_ts < now_ms
                if closed_only and not is_closed:
                    dropped_open += 1
                    continue
                if min(o, h, l, c) <= 0 or h < max(o, c, l) or l > min(o, c, h):
                    dropped_invalid += 1
                    continue
                row.update(ts=ts, o=o, h=h, l=l, c=c, v=v, close_ts=close_ts)
                by_ts[ts] = row
            except (KeyError, TypeError, ValueError):
                dropped_invalid += 1

        ordered = [by_ts[k] for k in sorted(by_ts)]
        if limit > 0:
            ordered = ordered[-limit:]
        if not ordered:
            return None

        def values(key: str, default=0):
            return [r.get(key, default) for r in ordered]

        volumes = [float(x) for x in values("v")]
        taker = [float(x) for x in values("taker", 0.0)]
        ratios = [min(1.0, max(0.0, t / v)) if v else 0.5 for t, v in zip(taker, volumes)]
        result = {
            "timestamps": [int(x) for x in values("ts")],
            "close_timestamps": [int(x) for x in values("close_ts")],
            "opens": [float(x) for x in values("o")],
            "highs": [float(x) for x in values("h")],
            "lows": [float(x) for x in values("l")],
            "closes": [float(x) for x in values("c")],
            "volumes": volumes,
            "num_trades": [int(float(x or 0)) for x in values("trades", 0)],
            "taker_buy_volumes": taker,
            "taker_buy_quote_volumes": [float(x) for x in values("taker_quote", 0.0)],
            "buy_sell_ratio": ratios,
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(ordered),
            "source": source,
            "closed_only": closed_only,
            "dropped_open_candles": dropped_open,
            "dropped_invalid_candles": dropped_invalid,
            "last_candle_closed": True if closed_only else bool(ordered[-1].get("closed", ordered[-1]["close_ts"] < now_ms)),
        }
        return result

    # ------------------------------------------------------------------
    # Public fetch API
    # ------------------------------------------------------------------
    def get_ohlcv(
        self, symbol=None, timeframe=None, limit=None, output_format="dict",
        exchange: str | None = None, closed_only: bool = True,
        allow_fallback: bool | None = None,
    ):
        symbol = self.normalize_symbol(symbol or Config.DEFAULT_SYMBOL)
        timeframe = self.normalize_timeframe(timeframe or Config.DEFAULT_TIMEFRAME)
        limit = int(limit or Config.CANDLES_COUNT)
        if limit < 1 or limit > 5000:
            raise DataManagerError("عدد الشموع يجب أن يكون بين 1 و5000")
        exchange_key = self.normalize_exchange(exchange or self.default_exchange)
        # Explicit selection means strict source unless the caller deliberately opts in.
        if allow_fallback is None:
            allow_fallback = exchange_key == "auto"

        cache_key = f"ohlcv:{symbol}:{timeframe}:{limit}:{exchange_key}:{closed_only}:{allow_fallback}:{output_format}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            self.last_fetch_report = dict(cached.get("fetch_report", {})) if isinstance(cached, dict) else {"cache": True}
            return cached

        specs = list(self.EXCHANGES)
        if exchange_key != "auto":
            selected = [s for s in specs if s.key == exchange_key]
            specs = selected + ([s for s in specs if s.key != exchange_key] if allow_fallback else [])

        attempts: list[dict[str, str]] = []
        data = None
        if self._is_crypto(symbol):
            for spec in specs:
                fetcher: Callable = getattr(self, spec.fetcher_name)
                try:
                    self.logger.info("Fetching %s %s from %s", symbol, timeframe, spec.label)
                    data = fetcher(symbol, timeframe, limit, closed_only=closed_only)
                    if data and data.get("count", 0) >= min(10, limit):
                        attempts.append({"exchange": spec.key, "status": "ok", "detail": f"{data['count']} candles"})
                        break
                    attempts.append({"exchange": spec.key, "status": "failed", "detail": "empty/insufficient response"})
                    data = None
                except Exception as exc:
                    attempts.append({"exchange": spec.key, "status": "failed", "detail": str(exc)})
                    self.logger.warning("%s fetch failed: %s", spec.label, exc)
                    data = None
        elif exchange_key in ("auto", "yahoo") and YF_AVAILABLE:
            try:
                data = self._fetch_yahoo(symbol, timeframe, limit, closed_only=closed_only)
                attempts.append({"exchange": "yahoo", "status": "ok" if data else "failed", "detail": ""})
            except Exception as exc:
                attempts.append({"exchange": "yahoo", "status": "failed", "detail": str(exc)})

        self.last_fetch_report = {
            "requested_exchange": exchange_key,
            "used_exchange": data.get("source") if data else None,
            "symbol": symbol,
            "timeframe": timeframe,
            "closed_only": closed_only,
            "attempts": attempts,
            "fetched_at_ms": int(time.time() * 1000),
        }
        if not data:
            # No fabricated/offline fallback: the caller receives exact attempt diagnostics.
            return None
        data["fetch_report"] = self.last_fetch_report
        result = self._dict_to_list(data) if output_format == "list" else data
        self._set_cache(cache_key, result)
        return result

    def get_last_fetch_report(self) -> dict[str, Any]:
        return dict(self.last_fetch_report)

    def get_multi_timeframe(self, symbol=None, timeframe=None, exchange: str | None = None):
        """Backward-compatible MTF bundle pinned to one exchange.

        The entry feed resolves ``auto`` once; context and macro feeds then use
        that exact venue with no fallback, preventing mixed-exchange candles.
        """
        symbol = self.normalize_symbol(symbol or Config.DEFAULT_SYMBOL)
        entry_tf = self.normalize_timeframe(timeframe or Config.DEFAULT_TIMEFRAME)
        requested = self.normalize_exchange(exchange or self.default_exchange)
        entry = self.get_ohlcv(
            symbol, entry_tf, Config.TF_CANDLES.get("entry", Config.CANDLES_COUNT),
            output_format="dict", exchange=requested, closed_only=True,
            allow_fallback=(requested == "auto"),
        )
        if not entry:
            return None
        pinned = entry["source"]
        chain = Config.TF_CONTEXT_MAP.get(entry_tf, [entry_tf, "15m", "4h"])
        context_tf = self.normalize_timeframe(chain[1] if len(chain) > 1 else "15m")
        macro_tf = self.normalize_timeframe(chain[2] if len(chain) > 2 else "4h")
        result = {"entry": entry}
        for label, tf, count_key in (
            ("context", context_tf, "context"),
            ("macro", macro_tf, "macro"),
        ):
            if tf == entry_tf:
                result[label] = entry
                continue
            data = self.get_ohlcv(
                symbol, tf, Config.TF_CANDLES.get(count_key, 300),
                output_format="dict", exchange=pinned, closed_only=True,
                allow_fallback=False,
            )
            if data:
                result[label] = data
        result["market_snapshot"] = {
            "exchange": pinned,
            "closed_candles_only": True,
            "entry_timeframe": entry_tf,
        }
        return result

    # ------------------------------------------------------------------
    # Exchange implementations
    # ------------------------------------------------------------------
    def _fetch_okx_paginated(self, symbol, timeframe, limit, closed_only=True):
        inst_id = self._dash_symbol(symbol)
        bar = self._convert_tf_okx(timeframe)
        all_rows: list[dict[str, Any]] = []
        remaining = limit + (1 if closed_only else 0)
        after = None
        while remaining > 0:
            current_limit = min(100, remaining)  # history endpoint documented max=100
            params: dict[str, Any] = {"instId": inst_id, "bar": bar, "limit": current_limit}
            if after is not None:
                params["after"] = after
            resp = self.session.get(f"{self.okx_base}/api/v5/market/history-candles", params=params, timeout=15)
            payload = self._json_or_error(resp, "OKX")
            if payload.get("code") != "0":
                raise DataManagerError(f"OKX code {payload.get('code')}: {payload.get('msg') or 'unknown error'} (bar={bar})")
            batch = payload.get("data") or []
            if not batch:
                break
            for x in batch:
                all_rows.append({
                    "ts": x[0], "o": x[1], "h": x[2], "l": x[3], "c": x[4], "v": x[5],
                    "closed": (str(x[8]) == "1") if len(x) > 8 else None,
                })
            after = batch[-1][0]
            remaining -= len(batch)
            if len(batch) < current_limit:
                break
            time.sleep(0.12)
        return self._finalize_rows(all_rows, symbol, timeframe, "okx", limit, closed_only)

    def _fetch_binance(self, symbol, timeframe, limit, closed_only=True):
        interval = self._convert_tf_binance(timeframe)
        resp = self.session.get(
            f"{self.binance_base}/api/v3/klines",
            params={"symbol": self._compact_symbol(symbol), "interval": interval, "limit": min(limit + 1, 1000)},
            timeout=15,
        )
        klines = self._json_or_error(resp, "Binance")
        if not isinstance(klines, list):
            raise DataManagerError(f"Binance: {klines.get('msg', 'unexpected response') if isinstance(klines, dict) else 'unexpected response'}")
        rows = [{
            "ts": x[0], "o": x[1], "h": x[2], "l": x[3], "c": x[4], "v": x[5],
            "close_ts": x[6], "trades": x[8], "taker": x[9], "taker_quote": x[10],
        } for x in klines]
        return self._finalize_rows(rows, symbol, timeframe, "binance", limit, closed_only)

    def _fetch_kucoin(self, symbol, timeframe, limit, closed_only=True):
        ktype = self._convert_tf_kucoin(timeframe)
        resp = self.session.get(
            f"{self.kucoin_base}/api/v1/market/candles",
            params={"symbol": self._dash_symbol(symbol), "type": ktype}, timeout=15,
        )
        payload = self._json_or_error(resp, "KuCoin")
        if payload.get("code") != "200000":
            raise DataManagerError(f"KuCoin code {payload.get('code')}: {payload.get('msg', 'unknown error')}")
        rows = [{
            "ts": int(float(x[0]) * 1000), "o": x[1], "c": x[2], "h": x[3], "l": x[4], "v": x[5],
        } for x in (payload.get("data") or [])[:limit + 1]]
        return self._finalize_rows(rows, symbol, timeframe, "kucoin", limit, closed_only)

    def _fetch_gate(self, symbol, timeframe, limit, closed_only=True):
        interval = self._convert_tf_gate(timeframe)
        resp = self.session.get(
            f"{self.gate_base}/api/v4/spot/candlesticks",
            params={"currency_pair": self._underscore_symbol(symbol), "interval": interval, "limit": min(limit + 1, 1000)},
            timeout=15,
        )
        klines = self._json_or_error(resp, "Gate.io")
        if not isinstance(klines, list):
            detail = klines.get("message") if isinstance(klines, dict) else "unexpected response"
            raise DataManagerError(f"Gate.io: {detail}")
        # [timestamp, quote volume, close, high, low, open, base volume]
        rows = [{
            "ts": int(float(x[0]) * 1000), "o": x[5], "h": x[3], "l": x[4], "c": x[2],
            "v": x[6] if len(x) > 6 else x[1],
        } for x in klines]
        return self._finalize_rows(rows, symbol, timeframe, "gate", limit, closed_only)

    def _fetch_bybit(self, symbol, timeframe, limit, closed_only=True):
        interval = self._convert_tf_bybit(timeframe)
        resp = self.session.get(
            f"{self.bybit_base}/v5/market/kline",
            params={"category": "spot", "symbol": self._compact_symbol(symbol), "interval": interval,
                    "limit": min(limit + 1, 1000)}, timeout=15,
        )
        payload = self._json_or_error(resp, "Bybit")
        if payload.get("retCode") != 0:
            raise DataManagerError(f"Bybit code {payload.get('retCode')}: {payload.get('retMsg', 'unknown error')}")
        rows = [{"ts": x[0], "o": x[1], "h": x[2], "l": x[3], "c": x[4], "v": x[5]}
                for x in (payload.get("result", {}).get("list") or [])]
        return self._finalize_rows(rows, symbol, timeframe, "bybit", limit, closed_only)

    def _fetch_mexc(self, symbol, timeframe, limit, closed_only=True):
        interval = self._convert_tf_binance(timeframe)
        resp = self.session.get(
            f"{self.mexc_base}/api/v3/klines",
            params={"symbol": self._compact_symbol(symbol), "interval": interval, "limit": min(limit + 1, 1000)},
            timeout=15,
        )
        klines = self._json_or_error(resp, "MEXC")
        if not isinstance(klines, list):
            raise DataManagerError(f"MEXC: {klines.get('msg', 'unexpected response') if isinstance(klines, dict) else 'unexpected response'}")
        rows = [{
            "ts": x[0], "o": x[1], "h": x[2], "l": x[3], "c": x[4], "v": x[5],
            "close_ts": x[6] if len(x) > 6 else None,
        } for x in klines]
        return self._finalize_rows(rows, symbol, timeframe, "mexc", limit, closed_only)

    def _fetch_yahoo(self, symbol, timeframe, limit, closed_only=True):
        if not YF_AVAILABLE:
            return None
        base, quote = self._split_symbol(symbol)
        yf_symbol = f"{base}-USD" if quote in {"USDT", "USDC", "BUSD"} else f"{base}-{quote}"
        tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "1d": "1d", "1w": "1wk"}
        if timeframe not in tf_map:
            raise DataManagerError(f"الفريم {timeframe} غير مدعوم على Yahoo")
        period_map = {"1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d", "1h": "2y", "1d": "5y", "1w": "10y"}
        df = yf.Ticker(yf_symbol).history(period=period_map[timeframe], interval=tf_map[timeframe])
        if df.empty:
            return None
        rows = []
        for idx, row in df.tail(limit + 1).iterrows():
            rows.append({
                "ts": int(idx.timestamp() * 1000), "o": row["Open"], "h": row["High"],
                "l": row["Low"], "c": row["Close"], "v": row["Volume"],
            })
        return self._finalize_rows(rows, symbol, timeframe, "yahoo", limit, closed_only)

    # ------------------------------------------------------------------
    # Historical cut-off compatibility
    # ------------------------------------------------------------------
    def fetch_ohlcv_up_to(self, symbol, timeframe, end_ts, limit=250, exchange: str | None = None):
        """Return candles whose *close* is at or before ``end_ts``.

        For recent data this uses the selected exchange's normal feed and cuts it
        without look-ahead.  OKX additionally supports an older-history cursor.
        """
        symbol = self.normalize_symbol(symbol)
        timeframe = self.normalize_timeframe(timeframe)
        exchange_key = self.normalize_exchange(exchange or self.default_exchange)
        end_ts = int(end_ts)

        if exchange_key in ("auto", "okx"):
            try:
                resp = self.session.get(
                    f"{self.okx_base}/api/v5/market/history-candles",
                    params={"instId": self._dash_symbol(symbol), "bar": self._convert_tf_okx(timeframe),
                            "limit": min(limit, 100), "after": end_ts}, timeout=15,
                )
                payload = self._json_or_error(resp, "OKX")
                if payload.get("code") == "0" and payload.get("data"):
                    rows = [{
                        "ts": x[0], "o": x[1], "h": x[2], "l": x[3], "c": x[4], "v": x[5],
                        "closed": (str(x[8]) == "1") if len(x) > 8 else True,
                    } for x in payload["data"]]
                    data = self._finalize_rows(rows, symbol, timeframe, "okx", limit, True)
                    if data:
                        return self._slice_at_end(data, end_ts, limit)
            except Exception as exc:
                self.logger.warning("OKX historical fetch failed: %s", exc)

        data = self.get_ohlcv(
            symbol, timeframe, min(limit + 100, 1000), output_format="dict",
            exchange=exchange_key, closed_only=True, allow_fallback=(exchange_key == "auto"),
        )
        return self._slice_at_end(data, end_ts, limit) if data else None

    @staticmethod
    def _slice_at_end(data: dict[str, Any], end_ts: int, limit: int):
        closes = data.get("close_timestamps") or data.get("timestamps", [])
        indices = [i for i, ts in enumerate(closes) if int(ts) <= end_ts]
        if not indices:
            return None
        last = indices[-1]
        first = max(0, last - limit + 1)
        array_fields = (
            "timestamps", "close_timestamps", "opens", "highs", "lows", "closes", "volumes",
            "num_trades", "taker_buy_volumes", "taker_buy_quote_volumes", "buy_sell_ratio",
        )
        out = dict(data)
        for field in array_fields:
            if field in data:
                out[field] = data[field][first:last + 1]
        out["count"] = last - first + 1
        out["source"] = f"{data.get('source', 'unknown')}_cutoff"
        return out

    def _dict_to_list(self, data_dict):
        if not data_dict:
            return None
        result = []
        for i in range(data_dict.get("count", len(data_dict["timestamps"]))):
            result.append([
                data_dict["timestamps"][i], data_dict["opens"][i], data_dict["highs"][i],
                data_dict["lows"][i], data_dict["closes"][i], data_dict["volumes"][i],
                data_dict["volumes"][i], data_dict["num_trades"][i],
                data_dict["taker_buy_volumes"][i], data_dict["taker_buy_quote_volumes"][i],
            ])
        return result

    def get_ticker(self, symbol=None, exchange: str | None = None):
        data = self.get_ohlcv(symbol, "1m", 1, output_format="dict", exchange=exchange, closed_only=True)
        return {"last": data["closes"][-1], "source": data["source"]} if data else None

    def clear_cache(self):
        self._cache.clear()

    def cache_stats(self):
        return {"entries": len(self._cache), "keys": list(self._cache.keys())[:10]}

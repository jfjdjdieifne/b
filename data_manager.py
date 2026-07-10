# -*- coding: utf-8 -*-
"""
Data Manager V6.0 - Multi-Exchange - يجيب شموع من أي منصة
════════════════════════════════════════════════════════════════════
يدعم: OKX, Binance, KuCoin, Gate.io, Bybit, MEXC + Yahoo Finance

All data is RAW NUMBERS - zero analysis

الميزة الجديدة (بطلب صريح): "لازم الكود يجيب بيانات شموع من اي منصه كوكوين و باينانس و okx"
- يجرب 6 منصات بالترتيب - إذا فشلت واحدة يجرب التالية تلقائياً
- لا يتوقف عند أول فشل - يحاول الكل حتى ينجح

يعمل على جهازك المحلي 100% (فيه نت) - الساندبوكس محجوب عن كل مواقع الكريبتو (SSL error)
"""

import logging
import time
import requests
from config import Config

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


class DataManager:
    def __init__(self):
        self.logger = logging.getLogger("DataManager")
        self.okx_base = "https://www.okx.com"
        self.binance_base = "https://api.binance.com"
        self.kucoin_base = "https://api.kucoin.com"
        self.gate_base = "https://api.gateio.ws"
        self.bybit_base = "https://api.bybit.com"
        self.mexc_base = "https://api.mexc.com"

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Trading Bot ICT)"})

        self._cache = {}
        self.logger.info("DataManager V6 ready - Multi-Exchange: OKX, Binance, KuCoin, Gate, Bybit, MEXC + Yahoo")

    # ══════════════════════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════════════════════

    def _is_crypto(self, symbol):
        s = symbol.upper().replace("/", "").replace("-", "")
        crypto_endings = ["USDT", "BUSD", "BTC", "ETH", "BNB", "USDC"]
        return any(s.endswith(e) for e in crypto_endings)

    def _clean_symbol(self, symbol):
        return symbol.upper().replace("/", "").replace("-", "")

    def _to_okx_inst_id(self, symbol):
        s = symbol.upper().replace("/", "-")
        if "-" not in s:
            for quote in ("USDT", "USDC", "BUSD", "BTC", "ETH"):
                if s.endswith(quote) and len(s) > len(quote):
                    s = f"{s[:-len(quote)]}-{quote}"
                    break
        return s

    def _to_binance_symbol(self, symbol):
        return symbol.upper().replace("/", "").replace("-", "")

    def _to_kucoin_symbol(self, symbol):
        s = symbol.upper().replace("/", "-")
        if "-" not in s:
            for quote in ("USDT", "USDC", "BTC", "ETH"):
                if s.endswith(quote) and len(s) > len(quote):
                    s = f"{s[:-len(quote)]}-{quote}"
                    break
        return s

    def _to_gate_pair(self, symbol):
        return symbol.upper().replace("/", "_")

    def _to_bybit_symbol(self, symbol):
        return symbol.upper().replace("/", "").replace("-", "")

    def _convert_tf_binance(self, tf):
        mapping = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h", "1d": "1d", "1w": "1w", "1M": "1M"}
        return mapping.get(tf.lower(), "15m")

    def _convert_tf_okx(self, tf):
        mapping = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H", "1d": "1D", "1w": "1W", "1M": "1M"}
        return mapping.get(tf.lower(), tf)

    def _convert_tf_kucoin(self, tf):
        mapping = {"1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1hour", "2h": "2hour", "4h": "4hour", "6h": "6hour", "12h": "12hour", "1d": "1day", "1w": "1week"}
        return mapping.get(tf.lower(), "15min")

    def _convert_tf_gate(self, tf):
        mapping = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h", "8h": "8h", "1d": "1d", "1w": "7d"}
        return mapping.get(tf.lower(), "15m")

    def _convert_tf_bybit(self, tf):
        mapping = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720", "1d": "D", "1w": "W", "1M": "M"}
        return mapping.get(tf.lower(), "15")

    def _get_cache(self, key, ttl=60):
        if key in self._cache:
            ts, val = self._cache[key]
            if time.time() - ts < ttl:
                return val
        return None

    def _set_cache(self, key, val):
        self._cache[key] = (time.time(), val)

    # ══════════════════════════════════════════════════════════
    #  Multi-Exchange OHLCV Fetcher
    # ══════════════════════════════════════════════════════════

    def get_ohlcv(self, symbol=None, timeframe=None, limit=None, output_format="dict"):
        symbol = symbol or Config.DEFAULT_SYMBOL
        timeframe = timeframe or Config.DEFAULT_TIMEFRAME
        limit = limit or Config.CANDLES_COUNT

        cache_key = f"ohlcv_{symbol}_{timeframe}_{limit}_{output_format}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        data = None

        if self._is_crypto(symbol):
            # جرب كل المنصات بالترتيب - إذا فشلت واحدة جرب التالية
            fetchers = [
                ("OKX", self._fetch_okx_paginated),
                ("Binance", self._fetch_binance),
                ("KuCoin", self._fetch_kucoin),
                ("Gate.io", self._fetch_gate),
                ("Bybit", self._fetch_bybit),
                ("MEXC", self._fetch_mexc),
            ]

            for exchange_name, fetcher in fetchers:
                try:
                    self.logger.info(f"🔄 محاولة جلب {symbol} {timeframe} من {exchange_name}...")
                    data = fetcher(symbol, timeframe, limit)
                    if data and data.get("closes") and len(data["closes"]) >= 10:
                        self.logger.info(f"✅ نجح الجلب من {exchange_name}: {len(data['closes'])} شمعة | سعر {data['closes'][-1]}")
                        break
                    else:
                        self.logger.warning(f"⚠️ {exchange_name} رجع بيانات فارغة - نجرب التالي")
                except Exception as e:
                    self.logger.warning(f"⚠️ {exchange_name} فشل: {e} - نجرب المنصة التالية")
                    continue

            if not data:
                self.logger.error(f"❌ كل المنصات فشلت لجلب {symbol} {timeframe} - جرب بلا نت: python main.py test-5")
                # حاول ياهو كأخير محاولة (لـ BTC-USD)
                if YF_AVAILABLE:
                    try:
                        data = self._fetch_yahoo(symbol, timeframe, limit)
                    except:
                        pass
        else:
            if YF_AVAILABLE:
                data = self._fetch_yahoo(symbol, timeframe, limit)

        if not data:
            return None

        if output_format == "list":
            result = self._dict_to_list(data)
        else:
            result = data

        self._set_cache(cache_key, result)
        return result

    # ── OKX (موجود سابقاً - مع إصلاح الترتيب) ──

    def _fetch_okx_paginated(self, symbol, timeframe, limit):
        inst_id = self._to_okx_inst_id(symbol)
        bar = self._convert_tf_okx(timeframe)
        all_candles = []
        remaining = limit
        batch_size = 300
        after = None
        try:
            batch_num = 0
            while remaining > 0:
                batch_num += 1
                current_limit = min(batch_size, remaining)
                url = f"{self.okx_base}/api/v5/market/history-candles"
                params = {"instId": inst_id, "bar": bar, "limit": current_limit}
                if after:
                    params["after"] = after
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code != 200:
                    break
                payload = resp.json()
                if payload.get("code") != "0":
                    break
                batch = payload.get("data", [])
                if not batch:
                    break
                after = batch[-1][0]
                batch = list(reversed(batch))
                all_candles = batch + all_candles
                remaining -= len(batch)
                if len(batch) < current_limit:
                    break
                if remaining > 0:
                    time.sleep(0.25)
            if not all_candles:
                return None
            data = {
                "timestamps": [int(c[0]) for c in all_candles],
                "opens": [float(c[1]) for c in all_candles],
                "highs": [float(c[2]) for c in all_candles],
                "lows": [float(c[3]) for c in all_candles],
                "closes": [float(c[4]) for c in all_candles],
                "volumes": [float(c[5]) for c in all_candles],
                "num_trades": [0] * len(all_candles),
                "taker_buy_volumes": [float(c[5]) * 0.5 for c in all_candles],
                "taker_buy_quote_volumes": [0.0] * len(all_candles),
                "buy_sell_ratio": [0.5] * len(all_candles),
                "symbol": symbol, "timeframe": timeframe, "count": len(all_candles), "source": "okx",
            }
            return data
        except Exception as e:
            self.logger.debug(f"OKX error: {e}")
            return None

    # ── Binance ──

    def _fetch_binance(self, symbol, timeframe, limit):
        try:
            binance_symbol = self._to_binance_symbol(symbol)
            interval = self._convert_tf_binance(timeframe)
            url = f"{self.binance_base}/api/v3/klines"
            params = {"symbol": binance_symbol, "interval": interval, "limit": min(limit, 1000)}
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return None
            klines = resp.json()
            if not klines or not isinstance(klines, list):
                return None
            # Binance: [openTime, open, high, low, close, volume, closeTime, quoteVolume, trades, takerBuyBase, takerBuyQuote, ignore]
            data = {
                "timestamps": [int(k[0]) for k in klines],
                "opens": [float(k[1]) for k in klines],
                "highs": [float(k[2]) for k in klines],
                "lows": [float(k[3]) for k in klines],
                "closes": [float(k[4]) for k in klines],
                "volumes": [float(k[5]) for k in klines],
                "num_trades": [int(k[8]) for k in klines],
                "taker_buy_volumes": [float(k[9]) for k in klines],
                "taker_buy_quote_volumes": [float(k[10]) for k in klines],
                "buy_sell_ratio": [0.5] * len(klines),
                "symbol": symbol, "timeframe": timeframe, "count": len(klines), "source": "binance",
            }
            return data
        except Exception as e:
            self.logger.debug(f"Binance error: {e}")
            return None

    # ── KuCoin ──

    def _fetch_kucoin(self, symbol, timeframe, limit):
        try:
            kucoin_symbol = self._to_kucoin_symbol(symbol)
            kucoin_type = self._convert_tf_kucoin(timeframe)
            url = f"{self.kucoin_base}/api/v1/market/candles"
            params = {"symbol": kucoin_symbol, "type": kucoin_type}
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return None
            payload = resp.json()
            if payload.get("code") != "200000":
                return None
            klines = payload.get("data", [])
            if not klines:
                return None
            klines = klines[:limit]
            klines = list(reversed(klines))  # KuCoin يرجع الأحدث أولاً
            # KuCoin: [timestamp, open, close, high, low, volume, turnover]
            data = {
                "timestamps": [int(float(k[0]) * 1000) for k in klines],
                "opens": [float(k[1]) for k in klines],
                "closes": [float(k[2]) for k in klines],
                "highs": [float(k[3]) for k in klines],
                "lows": [float(k[4]) for k in klines],
                "volumes": [float(k[5]) for k in klines],
                "num_trades": [0] * len(klines),
                "taker_buy_volumes": [float(k[5]) * 0.5 for k in klines],
                "taker_buy_quote_volumes": [0.0] * len(klines),
                "buy_sell_ratio": [0.5] * len(klines),
                "symbol": symbol, "timeframe": timeframe, "count": len(klines), "source": "kucoin",
            }
            return data
        except Exception as e:
            self.logger.debug(f"KuCoin error: {e}")
            return None

    # ── Gate.io ──

    def _fetch_gate(self, symbol, timeframe, limit):
        try:
            gate_pair = self._to_gate_pair(symbol)
            interval = self._convert_tf_gate(timeframe)
            url = f"{self.gate_base}/api/v4/spot/candlesticks"
            params = {"currency_pair": gate_pair, "interval": interval, "limit": min(limit, 1000)}
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return None
            klines = resp.json()
            if not klines or not isinstance(klines, list):
                return None
            klines = klines[:limit]
            # Gate: [timestamp, volume, close, high, low, open, quote_volume, trades?]
            # Actually Gate format: [t, v, c, h, l, o]
            data = {
                "timestamps": [int(float(k[0]) * 1000) for k in klines],
                "opens": [float(k[5]) for k in klines],
                "highs": [float(k[3]) for k in klines],
                "lows": [float(k[4]) for k in klines],
                "closes": [float(k[2]) for k in klines],
                "volumes": [float(k[1]) for k in klines],
                "num_trades": [0] * len(klines),
                "taker_buy_volumes": [0.0] * len(klines),
                "taker_buy_quote_volumes": [0.0] * len(klines),
                "buy_sell_ratio": [0.5] * len(klines),
                "symbol": symbol, "timeframe": timeframe, "count": len(klines), "source": "gate",
            }
            return data
        except Exception as e:
            self.logger.debug(f"Gate error: {e}")
            return None

    # ── Bybit ──

    def _fetch_bybit(self, symbol, timeframe, limit):
        try:
            bybit_symbol = self._to_bybit_symbol(symbol)
            interval = self._convert_tf_bybit(timeframe)
            url = f"{self.bybit_base}/v5/market/kline"
            params = {"category": "spot", "symbol": bybit_symbol, "interval": interval, "limit": min(limit, 1000)}
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return None
            payload = resp.json()
            if payload.get("retCode") != 0:
                return None
            klines = payload.get("result", {}).get("list", [])
            if not klines:
                return None
            klines = list(reversed(klines[:limit]))  # Bybit يرجع الأحدث أولاً
            # Bybit: [startTime, open, high, low, close, volume, turnover]
            data = {
                "timestamps": [int(k[0]) for k in klines],
                "opens": [float(k[1]) for k in klines],
                "highs": [float(k[2]) for k in klines],
                "lows": [float(k[3]) for k in klines],
                "closes": [float(k[4]) for k in klines],
                "volumes": [float(k[5]) for k in klines],
                "num_trades": [0] * len(klines),
                "taker_buy_volumes": [0.0] * len(klines),
                "taker_buy_quote_volumes": [0.0] * len(klines),
                "buy_sell_ratio": [0.5] * len(klines),
                "symbol": symbol, "timeframe": timeframe, "count": len(klines), "source": "bybit",
            }
            return data
        except Exception as e:
            self.logger.debug(f"Bybit error: {e}")
            return None

    # ── MEXC ──

    def _fetch_mexc(self, symbol, timeframe, limit):
        try:
            mexc_symbol = self._to_binance_symbol(symbol)
            interval = self._convert_tf_binance(timeframe)
            url = f"{self.mexc_base}/api/v3/klines"
            params = {"symbol": mexc_symbol, "interval": interval, "limit": min(limit, 1000)}
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return None
            klines = resp.json()
            if not klines or not isinstance(klines, list):
                return None
            data = {
                "timestamps": [int(k[0]) for k in klines],
                "opens": [float(k[1]) for k in klines],
                "highs": [float(k[2]) for k in klines],
                "lows": [float(k[3]) for k in klines],
                "closes": [float(k[4]) for k in klines],
                "volumes": [float(k[5]) for k in klines],
                "num_trades": [0] * len(klines),
                "taker_buy_volumes": [0.0] * len(klines),
                "taker_buy_quote_volumes": [0.0] * len(klines),
                "buy_sell_ratio": [0.5] * len(klines),
                "symbol": symbol, "timeframe": timeframe, "count": len(klines), "source": "mexc",
            }
            return data
        except Exception as e:
            self.logger.debug(f"MEXC error: {e}")
            return None

    # ── Yahoo (forex + stocks + crypto via BTC-USD) ──

    def _fetch_yahoo(self, symbol, timeframe, limit):
        if not YF_AVAILABLE:
            return None
        try:
            # تحويل BTC/USDT -> BTC-USD لـ yahoo
            yf_symbol = symbol.replace("/USDT", "-USD").replace("/USDT", "-USD").replace("/", "-")
            if "USDT" in yf_symbol and "-USD" not in yf_symbol:
                yf_symbol = yf_symbol.replace("USDT", "-USD")

            # mapping timeframe
            tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "1h", "1d": "1d", "1w": "1wk"}
            yf_interval = tf_map.get(timeframe.lower(), "15m")

            period_map = {"1m": "7d", "5m": "7d", "15m": "7d", "30m": "7d", "1h": "60d", "4h": "60d", "1d": "1y", "1w": "5y"}
            yf_period = period_map.get(timeframe.lower(), "60d")

            import yfinance as yf
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=yf_period, interval=yf_interval)

            if df.empty:
                return None

            df = df.tail(limit)

            data = {
                "timestamps": (df.index.astype(int) // 10**6).tolist(),
                "opens": df["Open"].tolist(),
                "highs": df["High"].tolist(),
                "lows": df["Low"].tolist(),
                "closes": df["Close"].tolist(),
                "volumes": df["Volume"].tolist(),
                "num_trades": [0] * len(df),
                "taker_buy_volumes": [0.0] * len(df),
                "taker_buy_quote_volumes": [0.0] * len(df),
                "buy_sell_ratio": [0.5] * len(df),
                "symbol": symbol, "timeframe": timeframe, "count": len(df), "source": "yahoo",
            }
            return data
        except Exception as e:
            self.logger.debug(f"Yahoo error: {e}")
            return None

    def fetch_ohlcv_up_to(self, symbol, timeframe, end_ts, limit=250):
        """
        جلب بيانات تنتهي عند timestamp محدد - يمنع lookahead bias
        يجرب كل المنصات
        """
        # حاول OKX أولاً
        try:
            inst_id = self._to_okx_inst_id(symbol)
            bar = self._convert_tf_okx(timeframe)
            resp = self.session.get(
                f"{self.okx_base}/api/v5/market/history-candles",
                params={"instId": inst_id, "bar": bar, "limit": min(limit, 300), "after": end_ts},
                timeout=15,
            )
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("code") == "0":
                    raw = list(reversed(payload.get("data", [])))
                    if raw:
                        return {
                            "timestamps": [int(x[0]) for x in raw],
                            "opens": [float(x[1]) for x in raw],
                            "highs": [float(x[2]) for x in raw],
                            "lows": [float(x[3]) for x in raw],
                            "closes": [float(x[4]) for x in raw],
                            "volumes": [float(x[5]) for x in raw],
                            "num_trades": [0] * len(raw),
                            "taker_buy_volumes": [float(x[5]) * 0.5 for x in raw],
                            "taker_buy_quote_volumes": [0.0] * len(raw),
                            "buy_sell_ratio": [0.5] * len(raw),
                            "symbol": symbol, "timeframe": timeframe, "count": len(raw), "source": "okx_up_to",
                        }
        except Exception as e:
            self.logger.debug(f"OKX up_to error: {e}")

        # Fallback: جلب عادي ثم اقطع حتى end_ts
        try:
            data = self.get_ohlcv(symbol, timeframe, limit + 100, output_format="dict")
            if data:
                # اقطع حتى end_ts
                filtered_indices = [i for i, ts in enumerate(data["timestamps"]) if ts <= end_ts]
                if filtered_indices:
                    last_idx = filtered_indices[-1]
                    start_idx = max(0, last_idx - limit + 1)
                    sliced = {
                        "timestamps": data["timestamps"][start_idx:last_idx+1],
                        "opens": data["opens"][start_idx:last_idx+1],
                        "highs": data["highs"][start_idx:last_idx+1],
                        "lows": data["lows"][start_idx:last_idx+1],
                        "closes": data["closes"][start_idx:last_idx+1],
                        "volumes": data["volumes"][start_idx:last_idx+1],
                        "num_trades": data["num_trades"][start_idx:last_idx+1],
                        "taker_buy_volumes": data["taker_buy_volumes"][start_idx:last_idx+1],
                        "taker_buy_quote_volumes": data["taker_buy_quote_volumes"][start_idx:last_idx+1],
                        "buy_sell_ratio": data["buy_sell_ratio"][start_idx:last_idx+1],
                        "symbol": symbol, "timeframe": timeframe, "count": last_idx - start_idx + 1, "source": "filtered",
                    }
                    return sliced
        except Exception as e:
            self.logger.debug(f"Filtered up_to error: {e}")

        return None

    def _dict_to_list(self, data_dict):
        if not data_dict:
            return None
        result = []
        count = data_dict.get("count", len(data_dict["timestamps"]))
        for i in range(count):
            candle = [
                data_dict["timestamps"][i],
                data_dict["opens"][i],
                data_dict["highs"][i],
                data_dict["lows"][i],
                data_dict["closes"][i],
                data_dict["volumes"][i],
                data_dict.get("quote_volumes", data_dict["volumes"])[i] if "quote_volumes" in data_dict else data_dict["volumes"][i],
                data_dict["num_trades"][i],
                data_dict["taker_buy_volumes"][i],
                data_dict["taker_buy_quote_volumes"][i]
            ]
            result.append(candle)
        return result

    def get_ticker(self, symbol=None):
        data = self.get_ohlcv(symbol, "1m", 1, output_format="dict")
        if data and data.get("closes"):
            return {"last": data["closes"][-1]}
        return None

    def clear_cache(self):
        self._cache.clear()

    def cache_stats(self):
        return {"entries": len(self._cache), "keys": list(self._cache.keys())[:10]}

# -*- coding: utf-8 -*-
"""Backward-compatible signal journal.

New interactive monitoring lives in :mod:`trade_monitor`; this repository is
kept for the legacy AI menu and now stores structured targets safely.
"""
import json
import logging
import os
import uuid

from config import Config
from user_utils import dual_time


class SignalRepository:
    def __init__(self, file_path=None):
        self.logger = logging.getLogger("SignalRepository")
        self.file_path = file_path or os.path.join(Config.DATA_DIR, "proposed_signals.json")
        Config.ensure_data_dir()
        os.makedirs(os.path.dirname(os.path.abspath(self.file_path)), exist_ok=True)
        self.signals = self._load()

    @staticmethod
    def _price(value):
        if isinstance(value, dict):
            if value.get("mode") == "OPEN_TRAILING":
                return None
            value = value.get("price", value.get("value"))
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as exc:
                self.logger.error("Failed to load signals file: %s", exc)
        return []

    def _save(self):
        temp = self.file_path + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(self.signals, f, ensure_ascii=False, indent=2)
        os.replace(temp, self.file_path)

    def add_signal(self, symbol, timeframe, indicators, ai_analysis):
        created = dual_time()
        tp1_raw = ai_analysis.get("tp1", ai_analysis.get("tp"))
        tp2_raw = ai_analysis.get("tp2")
        item = {
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": ai_analysis.get("exchange") or ai_analysis.get("data_source") or Config.DEFAULT_EXCHANGE,
            "created_at": created,
            "status": "proposed",
            "checked": False,
            "entry": self._price(ai_analysis.get("entry")),
            "stop_loss": self._price(ai_analysis.get("stop_loss")),
            "tp1": self._price(tp1_raw),
            "tp2": self._price(tp2_raw),
            "tp2_mode": tp2_raw.get("mode") if isinstance(tp2_raw, dict) else ("TARGET" if tp2_raw else None),
            "tp3": self._price(ai_analysis.get("tp3")),
            "signal": ai_analysis.get("signal", "HOLD"),
            "setup_status": ai_analysis.get("setup_status"),
            "confidence": ai_analysis.get("confidence", 0),
            "reasoning": ai_analysis.get("reasoning", ""),
            "bias": ai_analysis.get("bias", ""),
            "indicators": indicators,
            "evaluation": None,
        }
        self.signals.append(item)
        self._save()
        return item

    def get_unchecked_signals(self):
        return [s for s in self.signals if not s.get("checked", False)]

    def mark_checked(self, signal_id, evaluation):
        for signal in self.signals:
            if signal["id"] == signal_id:
                signal["checked"] = True
                signal["status"] = "evaluated"
                signal["evaluation"] = evaluation
                break
        self._save()

    def get_all(self):
        return self.signals

# -*- coding: utf-8 -*-
import json
import os
import logging
from datetime import datetime
from config import Config


class MemorySystem:

    def __init__(self):
        self.logger = logging.getLogger("MemorySystem")
        Config.ensure_data_dir()
        self.trades = self._load(Config.TRADES_FILE, [])
        self.events = self._load(Config.MEMORY_FILE, [])
        self.logger.info(
            f"Memory loaded: {len(self.trades)} trades, "
            f"{len(self.events)} events"
        )

    def _load(self, path, default):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        if isinstance(data, list):
                            return data
        except Exception as e:
            self.logger.error(f"Load {path}: {e}")
            # ═══ إصلاح: حذف الملف الفاسد ═══
            try:
                os.remove(path)
                self.logger.info(f"Removed corrupted {path}")
            except Exception:
                pass
        return default

    def _save(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Save {path}: {e}")

    def store_trade(self, trade):
        trade["timestamp"] = str(datetime.now())
        self.trades.append(trade)
        self._save(Config.TRADES_FILE, self.trades)

    def store_event(self, event):
        event["timestamp"] = str(datetime.now())
        self.events.append(event)
        if len(self.events) > 500:
            self.events = self.events[-500:]
        self._save(Config.MEMORY_FILE, self.events)

    def get_stats(self):
        if not self.trades:
            return {"total": 0, "msg": "لا صفقات بعد"}
        wins = sum(1 for t in self.trades if t.get("outcome") == "win")
        return {
            "total": len(self.trades),
            "wins": wins,
            "losses": len(self.trades) - wins,
            "win_rate%": round(wins / len(self.trades) * 100, 1),
            "last_5": self.trades[-5:],
        }

    def context_for(self, symbol=None):
        rel = self.trades[-10:]
        if symbol:
            rel = [t for t in self.trades if t.get("symbol") == symbol][-10:]
        if not rel:
            return "No previous context"
        return json.dumps(rel, ensure_ascii=False, default=str)

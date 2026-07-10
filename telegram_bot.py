# -*- coding: utf-8 -*-
"""Lightweight Telegram UI with inline one-click tracking.

Run with ``TELEGRAM_BOT_TOKEN`` in .env.  The bot reads public candles and
tracks plans; it never receives exchange trading credentials and never places
orders.
"""
from __future__ import annotations

import json
import os
import time

import requests

from config import Config
from data_manager import DataManager
from snapshot_analyzer import SnapshotAnalyzer
from trade_monitor import TradeMonitor


class TelegramBot:
    def __init__(self, token=None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not self.token:
            raise RuntimeError("ضع TELEGRAM_BOT_TOKEN في ملف .env ثم أعد التشغيل")
        self.base = f"https://api.telegram.org/bot{self.token}"
        self.http = requests.Session()
        self.dm = DataManager()
        self.analyzer = SnapshotAnalyzer(self.dm)
        self.monitor = TradeMonitor(self.dm)
        self.last_analysis = {}
        self._last_auto_refresh = 0.0

    def call(self, method, **payload):
        r = self.http.post(f"{self.base}/{method}", json=payload, timeout=70)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "Telegram API error"))
        return data.get("result")

    def send(self, chat_id, text, keyboard=None):
        chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
        for i, chunk in enumerate(chunks):
            payload = {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}
            if keyboard and i == len(chunks) - 1:
                payload["reply_markup"] = {"inline_keyboard": keyboard}
            self.call("sendMessage", **payload)

    def run(self):
        print("✅ Telegram bot is polling. Ctrl+C to stop.")
        offset = None
        while True:
            try:
                updates = self.call("getUpdates", offset=offset, timeout=10, allowed_updates=["message", "callback_query"])
                for update in updates:
                    offset = update["update_id"] + 1
                    self.handle(update)
                if time.time() - self._last_auto_refresh >= 30:
                    self.auto_refresh_notify()
                    self._last_auto_refresh = time.time()
            except KeyboardInterrupt:
                break
            except Exception as exc:
                print("Telegram error:", exc)
                time.sleep(3)

    def handle(self, update):
        if "callback_query" in update:
            query = update["callback_query"]
            self.call("answerCallbackQuery", callback_query_id=query["id"])
            return self.callback(query["message"]["chat"]["id"], query.get("data", ""))
        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = (msg.get("text") or "").strip()
        if not chat_id:
            return
        if text.startswith(("/start", "/help")):
            return self.help(chat_id)
        if text.startswith("/analyze"):
            return self.analyze(chat_id, text)
        if text.startswith("/trades"):
            return self.show_trades(chat_id)
        if text.startswith("/refresh"):
            self.monitor.refresh_all()
            return self.show_trades(chat_id)
        if text.startswith("/platforms"):
            return self.send(chat_id, "المنصات: auto, okx, binance, kucoin, gate, bybit, mexc")
        self.help(chat_id)

    def help(self, chat_id):
        self.send(
            chat_id,
            "مرصد السوق — أوامر سريعة\n\n"
            "/analyze ETH/USDT okx 5m — تحليل 1D/4H/15m/5m من OKX\n"
            "/trades — الصفقات المتابعة\n/refresh — تحديثها كلها\n/platforms — المنصات\n\n"
            "الفريم الأخير فقط للتنفيذ (1m/3m/5m). كل الشموع مغلقة. Pending للمراقبة وليس أمراً.",
            [[{"text": "تحليل ETH الآن", "callback_data": "analyze:ETH/USDT:auto:5m"}],
             [{"text": "تحديث الصفقات", "callback_data": "refresh_all"}]],
        )

    def analyze(self, chat_id, text):
        parts = text.split()
        symbol = parts[1] if len(parts) > 1 else "ETH/USDT"
        exchange = parts[2] if len(parts) > 2 else "auto"
        timeframe = parts[3] if len(parts) > 3 else "5m"
        self.send(chat_id, f"⏳ تحليل {symbol} من {exchange} — شموع مغلقة فقط…")
        try:
            result = self.analyzer.analyze(symbol, exchange, timeframe)
            if not result.get("ok"):
                return self.send(chat_id, result.get("error_ar", "فشل البيانات") + "\n" + json.dumps(result.get("data_fetch_reports"), ensure_ascii=False)[:1800])
            self.last_analysis[chat_id] = result
            self.send(chat_id, self.format_analysis(result), self.analysis_keyboard(result))
        except Exception as exc:
            self.send(chat_id, f"❌ {exc}")

    def format_analysis(self, a):
        b, d, c = a["bias"], a["decision"], a.get("candidate")
        lines = [
            f"📌 {a['symbol']} | {a['exchange'].upper()} | تنفيذ {a['execution_timeframe']}",
            f"🧾 {a['audit_id']}",
            f"🕒 NY: {a['data_cutoff']['close']['new_york']}",
            f"🕒 دمشق: {a['data_cutoff']['close']['damascus']}",
            "",
            f"📐 الانحياز: {b['direction']} — {b['explanation_ar']}",
            f"⏱ الجلسة: {a['session']['session']} | تنفيذ={a['session']['is_executable_window']}",
            f"⚖️ القرار: {d['label_ar']}\n{d['reason_ar']}",
        ]
        if c:
            lines += ["", f"🧩 {c['model']} ({c['model_status']})", f"Entry {c['entry']} | SL {c['stop_loss']}"]
            for target in c["targets"]:
                lines.append(f"🎯 {target['name']} {target['price']} | {target['allocation_pct']}% | R={target.get('rr')}")
            if c.get("runner"):
                lines.append("🏃 50% Runner: trailing HL/LH بعد TP1؛ لا يوجد TP2 رقمي موثق")
        lines += ["", "تفصيل الفريمات:"]
        for tf in ("1d", "4h", "15m", a["execution_timeframe"]):
            f = a["frames"][tf]
            lines.append(f"• {tf}: {f['bias_anchor']['anchor_direction']} | " + "؛ ".join(f["explanation_ar"][:2]))
        lines.append("\n⚠️ تعليمي فقط، وليس ضماناً أو نصيحة مالية.")
        return "\n".join(lines)

    def analysis_keyboard(self, result):
        rows = [[{"text": "🔄 إعادة التحليل", "callback_data": f"analyze:{result['symbol']}:{result['exchange']}:{result['execution_timeframe']}"}]]
        if result.get("candidate"):
            rows.append([{"text": "➕ أضف للمراقبة", "callback_data": "track_last"}])
        rows.append([{"text": "📋 الصفقات", "callback_data": "show_trades"}])
        return rows

    def callback(self, chat_id, data):
        if data.startswith("analyze:"):
            _, symbol, exchange, tf = data.split(":", 3)
            return self.analyze(chat_id, f"/analyze {symbol} {exchange} {tf}")
        if data == "track_last":
            result = self.last_analysis.get(chat_id)
            if not result or not result.get("candidate"):
                return self.send(chat_id, "التحليل السابق غير متوفر. أعد التحليل.")
            try:
                tracking_payload = dict(result["candidate"]["tracking_payload"])
                tracking_payload["notification_chat_id"] = chat_id
                trade = self.monitor.add(tracking_payload)
                return self.send(chat_id, f"✅ أضيفت {trade['id']} كمراقبة. فعّلها فقط بعد مراجعة التأكيد.",
                                 [[{"text": "تفعيل انتظار الدخول", "callback_data": f"activate:{trade['id']}"}],
                                  [{"text": "عرض الصفقات", "callback_data": "show_trades"}]])
            except Exception as exc:
                return self.send(chat_id, f"❌ {exc}")
        if data.startswith("activate:"):
            trade = self.monitor.activate(data.split(":", 1)[1])
            return self.send(chat_id, f"✅ {trade['id']} الآن بانتظار لمس الدخول.")
        if data == "refresh_all":
            self.monitor.refresh_all()
            return self.show_trades(chat_id)
        if data == "show_trades":
            return self.show_trades(chat_id)

    def auto_refresh_notify(self):
        """Refresh active trades and push only newly-created state events."""
        before = {t["id"]: len(t.get("events", [])) for t in self.monitor.list()}
        self.monitor.refresh_all()
        for trade in self.monitor.list():
            chat_id = trade.get("notification_chat_id")
            if not chat_id:
                continue
            new_events = trade.get("events", [])[before.get(trade["id"], 0):]
            meaningful = [e for e in new_events if e.get("type") not in ("TRAIL_RAISED", "TRAIL_LOWERED")]
            for event in meaningful:
                stamp = event.get("time", {})
                self.send(
                    chat_id,
                    f"🔔 {trade['symbol']} | {trade['id']}\n"
                    f"{event.get('type')}: {event.get('detail_ar', '')}\n"
                    f"الحالة: {trade['status']} | SL: {trade['current_stop_loss']} | المتبقي: {trade['remaining_pct']}%\n"
                    f"NY: {stamp.get('new_york', '')}\nدمشق: {stamp.get('damascus', '')}",
                )

    def show_trades(self, chat_id):
        trades = self.monitor.list()
        if not trades:
            return self.send(chat_id, "لا توجد صفقات متابعة.")
        lines = ["📋 الصفقات المتابعة"]
        for t in trades[-12:]:
            lines.append(
                f"\n{t['id']} | {t['symbol']} {t['side']} | {t['status']}\n"
                f"Entry {t['entry']} | SL {t['current_stop_loss']} | TP1 {t['tp1']} | TP2 {t.get('tp2') or 'Trailing'}\n"
                f"المتبقي {t['remaining_pct']}% | {t['realized_r']}R"
            )
        self.send(chat_id, "\n".join(lines), [[{"text": "🔄 تحديث الكل", "callback_data": "refresh_all"}]])


if __name__ == "__main__":
    TelegramBot().run()

# -*- coding: utf-8 -*-
"""Zero-framework local web application for analysis and trade tracking."""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from config import Config
from data_manager import DataManager
from snapshot_analyzer import SnapshotAnalyzer
from trade_monitor import TradeMonitor
from paper_account import PaperAccount
from market_agent import MarketAgent
from walk_forward_backtest import WalkForwardBacktester
from user_utils import dual_time

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
DM = DataManager()
ANALYZER = SnapshotAnalyzer(DM)
MONITOR = TradeMonitor(DM)
PAPER = PaperAccount()
AGENT = MarketAgent(DM, MONITOR, PAPER)
WALK_FORWARD = WalkForwardBacktester(DM)
ANALYSIS_LOCK = threading.Lock()
BACKTEST_LOCK = threading.Lock()


def _default(value):
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    return str(value)


class Handler(BaseHTTPRequestHandler):
    server_version = "ICTAuditWeb/1.0"

    def log_message(self, fmt, *args):
        print(f"[WEB] {self.address_string()} - {fmt % args}")

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, default=_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 1_000_000:
            raise ValueError("الطلب أكبر من الحد المسموح")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._json(200, {"ok": True, "time": dual_time()})
        if path == "/api/config":
            return self._json(200, {
                "exchanges": [{"key": "auto", "label": "تلقائي (يثبّت أول منصة ناجحة لكل الفريمات)"}] + DM.supported_exchanges(),
                "execution_timeframes": ["5m", "3m", "1m"],
                "default_exchange": DM.default_exchange,
                "closed_candles_only": True,
                "time": dual_time(),
            })
        if path == "/api/trades":
            return self._json(200, {"ok": True, "trades": MONITOR.list()})
        if path == "/api/account":
            PAPER.reconcile(MONITOR.list())
            return self._json(200, {"ok": True, "account": PAPER.snapshot()})
        if path == "/api/journal":
            PAPER.reconcile(MONITOR.list())
            return self._json(200, {"ok": True, "journal": PAPER.journal_with_scenarios()})
        if path == "/api/agent":
            return self._json(200, {"ok": True, "agent": AGENT.status()})
        if path == "/api/human-comparison":
            comparison_path = ROOT / "reports" / "human_trade_comparison_baseline.json"
            if not comparison_path.is_file():
                return self._json(404, {"ok": False, "error_ar": "تقرير الصفقات البشرية غير موجود"})
            with open(comparison_path, "r", encoding="utf-8") as f:
                return self._json(200, {"ok": True, "comparison": json.load(f)})
        if path == "/api/backtests":
            folder = Path(Config.DATA_DIR) / "backtests"
            files = sorted(folder.glob("WFT-*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.exists() else []
            return self._json(200, {"ok": True, "reports": [p.stem for p in files]})
        if path.startswith("/api/backtests/"):
            parts = [p for p in path.split("/") if p]
            report_id = parts[2] if len(parts) >= 3 else ""
            wants_bundle = len(parts) == 4 and parts[3] == "bundle"
            if not report_id.startswith("WFT-") or not report_id.replace("-", "").isalnum():
                return self._json(400, {"ok": False, "error_ar": "معرف تقرير غير صالح"})
            suffix = ".zip" if wants_bundle else ".json"
            report_path = Path(Config.DATA_DIR) / "backtests" / f"{report_id}{suffix}"
            if not report_path.is_file():
                return self._json(404, {"ok": False, "error_ar": "التقرير غير موجود"})
            body = report_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip" if wants_bundle else "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{report_id}{suffix}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        return self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/analyze":
                # Prevent several expensive multi-frame requests from racing if
                # the user double-clicks.
                if not ANALYSIS_LOCK.acquire(blocking=False):
                    return self._json(409, {"ok": False, "error_ar": "يوجد تحليل قيد التنفيذ؛ انتظر اكتماله."})
                try:
                    result = ANALYZER.analyze(
                        symbol=payload.get("symbol", "ETH/USDT"),
                        exchange=payload.get("exchange", "auto"),
                        execution_timeframe=payload.get("execution_timeframe", "5m"),
                        balance=payload.get("balance", 100),
                        risk_pct=payload.get("risk_pct", 1),
                        tp1_allocation_pct=payload.get("tp1_allocation_pct", 50),
                    )
                finally:
                    ANALYSIS_LOCK.release()
                return self._json(200 if result.get("ok") else 502, result)
            if path == "/api/backtest":
                if not BACKTEST_LOCK.acquire(blocking=False):
                    return self._json(409, {"ok": False, "error_ar": "يوجد اختبار زمني قيد التنفيذ."})
                try:
                    report = WALK_FORWARD.run(
                        symbol=payload.get("symbol", "ETH/USDT"),
                        start=payload.get("start"), end=payload.get("end"),
                        exchange=payload.get("exchange", "kucoin"),
                        execution_timeframe=payload.get("execution_timeframe", "5m"),
                        initial_balance=payload.get("initial_balance", 100),
                        risk_pct=payload.get("risk_pct", 1),
                        fee_bps=payload.get("fee_bps", 10),
                        slippage_bps=payload.get("slippage_bps", 2),
                        tp1_allocation_pct=payload.get("tp1_allocation_pct", 50),
                        checkpoint_minutes=payload.get("checkpoint_minutes", 15),
                    )
                finally:
                    BACKTEST_LOCK.release()
                return self._json(200, {"ok": True, "report": report})
            if path == "/api/trades":
                analysis = payload.pop("analysis", None)
                trade = MONITOR.add(payload)
                PAPER.register_plan(trade, analysis=analysis, auto=bool(payload.get("auto_discovered")))
                return self._json(201, {"ok": True, "trade": trade, "account": PAPER.snapshot()})
            if path == "/api/trades/refresh":
                report = MONITOR.refresh_all()
                account = PAPER.reconcile(MONITOR.list())
                return self._json(200, {"ok": True, **report, "account": account})
            if path == "/api/account/reset":
                return self._json(200, {"ok": True, "account": PAPER.reset(payload.get("initial_balance", 100))})
            if path == "/api/journal/scenario":
                result = PAPER.set_scenario(payload.get("trade_id"), payload.get("capital"), payload.get("risk_pct"))
                return self._json(200, {"ok": True, "scenario": result})
            if path == "/api/agent/start":
                return self._json(200, {"ok": True, "agent": AGENT.start(**payload)})
            if path == "/api/agent/stop":
                return self._json(200, {"ok": True, "agent": AGENT.stop()})
            parts = [p for p in path.split("/") if p]
            if len(parts) == 4 and parts[:2] == ["api", "trades"]:
                trade_id, action = parts[2], parts[3]
                if action == "activate":
                    return self._json(200, {"ok": True, "trade": MONITOR.activate(trade_id)})
                if action == "cancel":
                    return self._json(200, {"ok": True, "trade": MONITOR.cancel(trade_id)})
                if action == "refresh":
                    trade = MONITOR.refresh(trade_id)
                    account = PAPER.reconcile(MONITOR.list())
                    return self._json(200, {"ok": True, "trade": trade, "account": account})
            return self._json(404, {"ok": False, "error_ar": "المسار غير موجود"})
        except KeyError as exc:
            return self._json(404, {"ok": False, "error_ar": str(exc)})
        except Exception as exc:
            return self._json(400, {"ok": False, "error_ar": str(exc), "error_type": type(exc).__name__})

    def _serve_static(self, path):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        candidate = (WEB_ROOT / rel).resolve()
        if WEB_ROOT.resolve() not in candidate.parents and candidate != WEB_ROOT.resolve():
            return self._json(403, {"ok": False, "error_ar": "مسار ممنوع"})
        if not candidate.is_file():
            candidate = WEB_ROOT / "index.html"
        data = candidate.read_bytes()
        mime = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        if mime.startswith("text/") or mime in ("application/javascript", "application/json"):
            mime += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description="واجهة محلية لتحليل ICT ومتابعة الصفقات")
    parser.add_argument("--host", default="127.0.0.1", help="استخدم 0.0.0.0 للوصول من الهاتف ضمن الشبكة المحلية")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--open", action="store_true", help="فتح المتصفح تلقائياً")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"\n✅ الواجهة تعمل: {url}")
    print("   Ctrl+C للإيقاف. لا توجد أوامر تداول حقيقية؛ التحليل والمتابعة تعليميان.")
    if args.open:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nتم إيقاف الواجهة.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

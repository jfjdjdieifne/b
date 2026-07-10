# -*- coding: utf-8 -*-
"""Native desktop window wrapper around the local dashboard."""
from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

from web_app import Handler


def main():
    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "واجهة الكمبيوتر الأصلية تحتاج pywebview. نفّذ:\n"
            "pip install -r requirements-desktop.txt\n"
            "ثم python desktop_app.py"
        ) from exc

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        webview.create_window(
            "مرصد السوق",
            f"http://127.0.0.1:{port}",
            width=1320,
            height=860,
            min_size=(920, 650),
        )
        webview.start()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()

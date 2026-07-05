#!/usr/bin/env python3
"""Headless e2e run for pattern-playground.html.

Serves the repo over localhost, loads tests/pattern-playground.e2e.html in
Playwright's headless Chromium, waits for the suite to finish, and reports.

Setup (one-time):  pip install --user playwright && python3 -m playwright install chromium-headless-shell
Usage:             python3 tools/run_playground_e2e.py     (exit 0 = all green)

Note: system Brave's --headless hangs on this machine, hence Playwright's
chromium-headless-shell (lives in ~/.cache/ms-playwright, outside the vault).
"""
import functools
import http.server
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed — pip install --user playwright "
              "&& python3 -m playwright install chromium-headless-shell", file=sys.stderr)
        return 2

    httpd, port = serve()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1500, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/tests/pattern-playground.e2e.html")
            page.wait_for_function("document.title.startsWith('E2E')", timeout=90_000)
            summary = page.text_content("#summary").strip()
            fails = page.eval_on_selector_all(".t.fail", "els => els.map(e => e.textContent)")
            browser.close()
    finally:
        httpd.shutdown()

    print(summary)
    for f in fails:
        print("  " + f, file=sys.stderr)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

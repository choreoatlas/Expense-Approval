from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from expense.http import make_server


class BrowserWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = make_server("127.0.0.1", 0, Path(self.tmp.name) / "expenses.sqlite3")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def test_real_browser_reject_revise_resubmit_and_approve(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(self.base)

            page.fill("#amount", "42.50")
            page.fill("#purpose", "Client dinner")
            page.fill("#receipt", "receipt-v1")
            page.click("button[type=submit]")
            page.wait_for_function("() => document.querySelector('#current').textContent.includes('draft')")

            page.click("#submit-btn")
            page.wait_for_function("() => document.querySelector('#current').textContent.includes('submitted')")

            page.fill("#reason", "Need clearer receipt")
            page.click("#reject-btn")
            page.wait_for_function("() => document.querySelector('#current').textContent.includes('rejected')")

            page.fill("#purpose", "Client dinner with attendees")
            page.fill("#receipt", "receipt-v2")
            page.click("#revise-btn")
            page.wait_for_function("() => document.querySelector('#current').textContent.includes('revision\": 2')")

            page.click("#submit-btn")
            page.wait_for_function("() => document.querySelector('#current').textContent.includes('submitted')")
            page.fill("#reason", "Policy compliant")
            page.click("#approve-btn")
            page.wait_for_function("() => document.querySelector('#current').textContent.includes('approved')")

            page.click("#history-btn")
            page.wait_for_function("() => document.querySelector('#history').textContent.includes('Need clearer receipt')")
            history_text = page.locator("#history").text_content()
            self.assertIn('"revision": 1', history_text)
            self.assertIn('"revision": 2', history_text)
            self.assertIn('"outcome": "rejected"', history_text)
            self.assertIn('"outcome": "approved"', history_text)
            browser.close()


if __name__ == "__main__":
    unittest.main()

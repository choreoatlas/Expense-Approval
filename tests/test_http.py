from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from expense.http import make_server


class HttpWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = make_server("127.0.0.1", 0, Path(self.tmp.name) / "expenses.sqlite3")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)

    def tearDown(self):
        self.conn.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload)
        headers = {} if body is None else {"Content-Type": "application/json"}
        self.conn.request(method, path, body=body, headers=headers)
        response = self.conn.getresponse()
        raw = response.read()
        return response.status, None if not raw else json.loads(raw)

    def test_revisioned_rejection_resubmission_over_http(self):
        status, draft = self.request("POST", "/api/expenses", {"employee":"alice","amount":"15","purpose":"Taxi","receipt_ref":"r1"})
        self.assertEqual(201, status)
        expense_id = draft["expense_id"]

        status, submitted = self.request("POST", f"/api/expenses/{expense_id}/submit", {})
        self.assertEqual(200, status)
        self.assertEqual("submitted", submitted["status"])

        status, decision = self.request("POST", f"/api/expenses/{expense_id}/1/decision", {"approver":"bob","outcome":"rejected","reason":"Need itemized receipt"})
        self.assertEqual(201, status)
        self.assertEqual(1, decision["revision"])

        status, revised = self.request("POST", f"/api/expenses/{expense_id}/revise", {"amount":"15","purpose":"Taxi to client","receipt_ref":"r2"})
        self.assertEqual(201, status)
        self.assertEqual(2, revised["revision"])
        self.request("POST", f"/api/expenses/{expense_id}/submit", {})

        status, history = self.request("GET", f"/api/expenses/{expense_id}/history")
        self.assertEqual(200, status)
        self.assertEqual([1,2], [r["revision"] for r in history["revisions"]])
        self.assertEqual("rejected", history["revisions"][0]["status"])
        self.assertEqual("submitted", history["revisions"][1]["status"])

    def test_self_approval_is_forbidden_without_state_change(self):
        _, draft = self.request("POST", "/api/expenses", {"employee":"alice","amount":"10","purpose":"Train","receipt_ref":"r1"})
        self.request("POST", f"/api/expenses/{draft['expense_id']}/submit", {})
        status, error = self.request("POST", f"/api/expenses/{draft['expense_id']}/1/decision", {"approver":"alice","outcome":"approved","reason":"Mine"})
        self.assertEqual(403, status)
        self.assertIn("own expense", error["error"])
        _, current = self.request("GET", f"/api/expenses/{draft['expense_id']}")
        self.assertEqual("submitted", current["status"])


if __name__ == "__main__":
    unittest.main()

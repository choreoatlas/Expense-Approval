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

    def create_submit(self):
        status, draft = self.request("POST", "/api/expenses", {"employee":"alice","amount":"15","purpose":"Taxi","receipt_ref":"r1"})
        self.assertEqual(201, status)
        expense_id = draft["expense_id"]
        status, submitted = self.request("POST", f"/api/expenses/{expense_id}/submit", {})
        self.assertEqual(200, status)
        return expense_id, submitted

    def test_draft_edit_then_two_stage_approval_over_http(self):
        status, draft = self.request("POST", "/api/expenses", {"employee":"alice","amount":"15","purpose":"Taxi","receipt_ref":"r1"})
        self.assertEqual(201, status)
        expense_id = draft["expense_id"]
        status, edited = self.request("PATCH", f"/api/expenses/{expense_id}", {"amount":"16","purpose":"Taxi to client","receipt_ref":"r2"})
        self.assertEqual(200, status)
        self.assertEqual("16", edited["amount"])
        self.request("POST", f"/api/expenses/{expense_id}/submit", {})

        status, first = self.request("POST", f"/api/expenses/{expense_id}/1/decision", {"approver":"bob","outcome":"approved","reason":"Policy compliant"})
        self.assertEqual(201, status)
        self.assertEqual("approver", first["actor_role"])
        _, current = self.request("GET", f"/api/expenses/{expense_id}")
        self.assertEqual("manager_pending", current["status"])

        status, final = self.request("POST", f"/api/expenses/{expense_id}/1/decision", {"approver":"carol","outcome":"approved","reason":"GM approved"})
        self.assertEqual(201, status)
        self.assertEqual("general_manager", final["actor_role"])
        _, current = self.request("GET", f"/api/expenses/{expense_id}")
        self.assertEqual("approved", current["status"])

    def test_unauthorized_and_wrong_stage_actor_are_forbidden_without_state_change(self):
        expense_id, _ = self.create_submit()
        status, _ = self.request("POST", f"/api/expenses/{expense_id}/1/decision", {"approver":"mallory","outcome":"approved","reason":"No authority"})
        self.assertEqual(403, status)
        _, current = self.request("GET", f"/api/expenses/{expense_id}")
        self.assertEqual("submitted", current["status"])

        status, _ = self.request("POST", f"/api/expenses/{expense_id}/1/decision", {"approver":"carol","outcome":"approved","reason":"Skip first"})
        self.assertEqual(403, status)
        _, current = self.request("GET", f"/api/expenses/{expense_id}")
        self.assertEqual("submitted", current["status"])

    def test_revisioned_rejection_resubmission_over_http(self):
        expense_id, _ = self.create_submit()
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
        expense_id, _ = self.create_submit()
        status, error = self.request("POST", f"/api/expenses/{expense_id}/1/decision", {"approver":"alice","outcome":"approved","reason":"Mine"})
        self.assertEqual(403, status)
        _, current = self.request("GET", f"/api/expenses/{expense_id}")
        self.assertEqual("submitted", current["status"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class ProcessRestartEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "expenses.sqlite3"
        self.process = None
        self.port = self._free_port()

    def tearDown(self):
        self._stop_app()
        self.tmp.cleanup()

    def _free_port(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _start_app(self):
        self.process = subprocess.Popen(
            [sys.executable, "app.py", "--host", "127.0.0.1", "--port", str(self.port), "--db", str(self.db)],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                self.fail(f"application exited before becoming ready: {stderr}")
            try:
                conn = HTTPConnection("127.0.0.1", self.port, timeout=0.2)
                conn.request("GET", "/")
                response = conn.getresponse()
                response.read()
                conn.close()
                if response.status == 200:
                    return
            except OSError:
                time.sleep(0.05)
        self.fail("application did not become ready")

    def _stop_app(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.process.stderr:
            self.process.stderr.close()
        self.process = None

    def _request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload)
        headers = {} if body is None else {"Content-Type": "application/json"}
        conn = HTTPConnection("127.0.0.1", self.port, timeout=2)
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, None if not raw else json.loads(raw)

    def test_full_approved_history_survives_real_application_process_restart(self):
        self._start_app()
        status, draft = self._request(
            "POST",
            "/api/expenses",
            {"employee": "alice", "amount": "120", "purpose": "Customer visit", "receipt_ref": "visit-1"},
        )
        self.assertEqual(201, status)
        expense_id = draft["expense_id"]
        self.assertEqual(200, self._request("POST", f"/api/expenses/{expense_id}/submit", {})[0])
        self.assertEqual(
            201,
            self._request(
                "POST",
                f"/api/expenses/{expense_id}/1/decision",
                {"approver": "bob", "outcome": "approved", "reason": "First stage approved"},
            )[0],
        )
        self.assertEqual(
            201,
            self._request(
                "POST",
                f"/api/expenses/{expense_id}/1/decision",
                {"approver": "carol", "outcome": "approved", "reason": "GM approved"},
            )[0],
        )
        self._stop_app()

        self._start_app()
        status, current = self._request("GET", f"/api/expenses/{expense_id}")
        self.assertEqual(200, status)
        self.assertEqual("approved", current["status"])
        status, history = self._request("GET", f"/api/expenses/{expense_id}/history")
        self.assertEqual(200, status)
        self.assertEqual(["approver", "general_manager"], [d["actor_role"] for d in history["decisions"]])
        self.assertEqual(["approved", "approved"], [d["outcome"] for d in history["decisions"]])


if __name__ == "__main__":
    unittest.main()

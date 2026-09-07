from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .store import ExpenseStore


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _revision_json(rev):
    return {
        "expense_id": rev.expense_id,
        "revision": rev.revision,
        "employee": rev.employee,
        "amount": rev.content.amount,
        "purpose": rev.content.purpose,
        "receipt_ref": rev.content.receipt_ref,
        "status": rev.status.value,
    }


def make_handler(store: ExpenseStore):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def _send_json(self, status: int, payload=None):
            body = b"" if payload is None else json.dumps(payload).encode()
            self.send_response(status)
            if payload is not None:
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def _fail(self, exc):
            if isinstance(exc, PermissionError):
                self._send_json(403, {"error": str(exc)})
            elif isinstance(exc, KeyError):
                self._send_json(404, {"error": str(exc).strip("'")})
            elif isinstance(exc, (ValueError, json.JSONDecodeError)):
                self._send_json(400, {"error": str(exc)})
            else:
                raise exc

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                return self._serve_file("index.html", "text/html")
            if path == "/app.js":
                return self._serve_file("app.js", "text/javascript")
            if path == "/styles.css":
                return self._serve_file("styles.css", "text/css")
            parts = [p for p in path.split("/") if p]
            if len(parts) == 4 and parts[:2] == ["api", "expenses"] and parts[3] == "history":
                try:
                    return self._send_json(200, store.history(int(parts[2])))
                except Exception as exc:
                    return self._fail(exc)
            if len(parts) == 3 and parts[:2] == ["api", "expenses"]:
                try:
                    return self._send_json(200, _revision_json(store.latest(int(parts[2]))))
                except Exception as exc:
                    return self._fail(exc)
            self._send_json(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            parts = [p for p in path.split("/") if p]
            try:
                data = self._read_json()
                if parts == ["api", "expenses"]:
                    rev = store.create_draft(data.get("employee", ""), data.get("amount", ""), data.get("purpose", ""), data.get("receipt_ref", ""))
                    return self._send_json(201, _revision_json(rev))
                if len(parts) == 4 and parts[:2] == ["api", "expenses"] and parts[3] == "submit":
                    return self._send_json(200, _revision_json(store.submit(int(parts[2]))))
                if len(parts) == 4 and parts[:2] == ["api", "expenses"] and parts[3] == "revise":
                    rev = store.revise_rejected(int(parts[2]), data.get("amount", ""), data.get("purpose", ""), data.get("receipt_ref", ""))
                    return self._send_json(201, _revision_json(rev))
                if len(parts) == 5 and parts[:2] == ["api", "expenses"] and parts[4] == "decision":
                    decision = store.decide(int(parts[2]), int(parts[3]), data.get("approver", ""), data.get("outcome", ""), data.get("reason", ""))
                    return self._send_json(201, decision.__dict__)
                self._send_json(404, {"error": "not found"})
            except Exception as exc:
                return self._fail(exc)

        def do_PATCH(self):
            parts = [p for p in urlparse(self.path).path.split("/") if p]
            try:
                if len(parts) == 3 and parts[:2] == ["api", "expenses"]:
                    data = self._read_json()
                    rev = store.edit_draft(int(parts[2]), data.get("amount", ""), data.get("purpose", ""), data.get("receipt_ref", ""))
                    return self._send_json(200, _revision_json(rev))
                self._send_json(404, {"error": "not found"})
            except Exception as exc:
                return self._fail(exc)

        def _serve_file(self, name: str, content_type: str):
            path = STATIC_DIR / name
            if not path.exists():
                return self._send_json(404, {"error": "asset not found"})
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def make_server(host: str, port: int, db_path: Path):
    store = ExpenseStore(db_path)
    return ThreadingHTTPServer((host, port), make_handler(store))

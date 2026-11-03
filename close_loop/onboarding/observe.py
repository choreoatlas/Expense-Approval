"""Record bounded Expense application observations, without judging a Function.

The supplied Git revision must be the checked-out, unmodified source. All
databases, HTTP listeners, Chromium contexts and child processes are owned by
this invocation. No Management, CEB or Commercial algorithm is implemented here.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
from http.client import HTTPConnection
import importlib.metadata
import json
import os
from pathlib import Path
import re
import select
import sqlite3
import subprocess
import sys
import tempfile
import threading
from typing import Any

from expense.http import make_server


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "choreoatlas/Expense-Approval"
DECLARATIONS = ["objects.json", "conditions.json", "composition.json", "owners.json", "profile.json"]
REQUIRED_SOURCE_PATHS = (
    "close_loop/onboarding/observe.py",
    *("close_loop/onboarding/" + name for name in DECLARATIONS),
    "expense/domain.py", "expense/store.py", "expense/http.py", "app.py",
    "static/app.js", "static/index.html", "static/styles.css",
    "close_loop/attempt-1/model.v0.2.json",
    "close_loop/attempt-1/function-model.v0.2.json",
    "close_loop/attempt-1/execution-design.v0.2.json",
    "close_loop/attempt-1/evidence-requirements.v0.2.json",
    "requirements-dev.txt", ".github/workflows/ci.yml",
)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def child_environment() -> dict[str, str]:
    """Only runtime locations are inherited; no provider/DB/cloud credentials."""
    selected = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "SYSTEMROOT", "PLAYWRIGHT_BROWSERS_PATH") if key in os.environ}
    selected.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    return selected


@contextmanager
def browser_environment():
    # Playwright's driver starts before browser.launch(env=...). Sanitize both
    # child boundaries, while retaining the caller's environment in this process.
    previous = dict(os.environ)
    selected = child_environment()
    os.environ.clear()
    os.environ.update(selected)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def git(root: Path, *arguments: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *arguments], env=child_environment(), stderr=subprocess.PIPE)


def source_binding(product_revision: str, root: Path = ROOT) -> dict[str, Any]:
    """Bind actual tracked bytes to the caller-selected immutable Git object."""
    if not re.fullmatch(r"[0-9a-f]{40}", product_revision):
        raise ValueError("PRODUCT_REVISION_MUST_BE_FULL_GIT_SHA")
    if git(root, "rev-parse", "HEAD").decode().strip() != product_revision:
        raise ValueError("PRODUCT_REVISION_DOES_NOT_MATCH_CHECKOUT")
    remote = git(root, "remote", "get-url", "origin").decode().strip()
    if remote not in {
        "https://github.com/" + REPOSITORY + ".git",
        "https://github.com/" + REPOSITORY,
        "git@github.com:" + REPOSITORY + ".git",
    }:
        raise ValueError("UNEXPECTED_SOURCE_REPOSITORY")
    rows = []
    for entry in git(root, "ls-tree", "-rz", "--full-tree", product_revision).split(b"\0"):
        if not entry:
            continue
        header, path_raw = entry.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("UNSUPPORTED_SOURCE_ENTRY")
        path = path_raw.decode("utf-8")
        actual_path = root / path
        if actual_path.is_symlink() or not actual_path.is_file():
            raise ValueError("SOURCE_ENTRY_NOT_REGULAR_FILE:" + path)
        raw = actual_path.read_bytes()
        actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual_blob != blob:
            raise ValueError("SOURCE_BYTES_MISMATCH:" + path)
        rows.append({"path": path, "mode": mode, "git_blob": blob, "sha256": digest(raw), "bytes": len(raw)})
    pinned_paths = {row["path"] for row in rows}
    for path in REQUIRED_SOURCE_PATHS:
        if path not in pinned_paths:
            raise ValueError("SOURCE_REQUIRED_PATH_NOT_PINNED:" + path)
    return {
        "repository": REPOSITORY,
        "product_git_revision": product_revision,
        "product_git_tree": git(root, "rev-parse", product_revision + "^{tree}").decode().strip(),
        "tracked_source_files": rows,
        "limits": "Pre/post byte checks in a caller-trusted checkout; not an OS immutability or source-authentication attestation.",
    }


def database_snapshot(path: Path) -> dict[str, Any]:
    """Read the invocation's existing scratch DB; never create a DB here."""
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        ordering = {"actors": "name", "expenses": "id", "revisions": "expense_id,revision", "decisions": "id"}
        return {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")]
                for table, order in ordering.items()}


class ApiRecorder:
    def __init__(self, port: int, database: Path, observations: list[dict[str, Any]]):
        self.port, self.database, self.observations = port, database, observations

    def request(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload)
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            raw = response.read()
            return {"status": response.status, "body": None if not raw else json.loads(raw)}
        finally:
            connection.close()

    def action(self, observation_id: str, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        before = database_snapshot(self.database)
        response = self.request(method, path, payload)
        after = database_snapshot(self.database)
        self.observations.append({"id": observation_id, "transport": "real loopback HTTP",
                                  "request": {"method": method, "path": path, "payload": payload},
                                  "response": response, "before": before, "after": after})
        return response

    def create(self, prefix: str, amount: str = "42.50") -> int:
        response = self.action(prefix + ".create", "POST", "/api/expenses", {
            "employee": "alice", "amount": amount, "purpose": prefix, "receipt_ref": prefix + "-r1"})
        return response["body"]["expense_id"]

    def decide(self, observation_id: str, expense_id: int, revision: int, actor: str,
               outcome: str = "approved", reason: str = "Observed reference decision") -> dict[str, Any]:
        return self.action(observation_id, "POST", f"/api/expenses/{expense_id}/{revision}/decision",
                           {"approver": actor, "outcome": outcome, "reason": reason})


@contextmanager
def http_application(database: Path, resources: list[dict[str, Any]]):
    server = make_server("127.0.0.1", 0, database)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    resource = {"kind": "owned loopback HTTP server", "database": str(database),
                "port": server.server_port, "closed": False}
    resources.append(resource)
    started = False
    try:
        thread.start()
        started = True
        yield server.server_port
    finally:
        # shutdown waits for serve_forever; it must not run on a thread that
        # failed to start. The listener still belongs to us in that case.
        try:
            if started or thread.ident is not None:
                server.shutdown()
        finally:
            server.server_close()
            if started or thread.ident is not None:
                thread.join(timeout=3)
        resource["thread_started"] = started or thread.ident is not None
        resource["thread_alive_after_close"] = thread.is_alive()
        resource["listener_closed"] = server.socket.fileno() == -1
        resource["closed"] = resource["listener_closed"] and not thread.is_alive()
        if thread.is_alive():
            raise RuntimeError("OWNED_HTTP_THREAD_DID_NOT_STOP")


def observe_api(database: Path, observations: list[dict[str, Any]], resources: list[dict[str, Any]]) -> None:
    with http_application(database, resources) as port:
        api = ApiRecorder(port, database, observations)
        expense_id = api.create("api-main")
        api.action("api-main.submit", "POST", f"/api/expenses/{expense_id}/submit", {})
        api.decide("api-main.gm-before-first", expense_id, 1, "carol")
        api.decide("api-main.first-approve", expense_id, 1, "bob")
        api.decide("api-main.unknown-final", expense_id, 1, "mallory")
        api.decide("api-main.employee-final", expense_id, 1, "alice")
        api.decide("api-main.approver-final", expense_id, 1, "bob")
        api.decide("api-main.bad-outcome", expense_id, 1, "carol", "held")
        api.decide("api-main.empty-reason", expense_id, 1, "carol", reason="")
        api.decide("api-main.final-approve", expense_id, 1, "carol")
        api.decide("api-main.repeated-final", expense_id, 1, "carol")
        changed = {"amount": "43", "purpose": "Edited after approval", "receipt_ref": "changed"}
        api.action("api-main.edit-approved", "PATCH", f"/api/expenses/{expense_id}", changed)
        api.action("api-main.revise-approved", "POST", f"/api/expenses/{expense_id}/revise", changed)

        expense_id = api.create("api-gm-rework")
        api.action("api-gm-rework.submit", "POST", f"/api/expenses/{expense_id}/submit", {})
        api.decide("api-gm-rework.first-approve", expense_id, 1, "bob")
        api.decide("api-gm-rework.final-reject", expense_id, 1, "carol", "rejected", "GM requests changed receipt")
        api.action("api-gm-rework.revise", "POST", f"/api/expenses/{expense_id}/revise", {
            "amount": "44", "purpose": "GM requested revision", "receipt_ref": "gm-r2"})
        api.action("api-gm-rework.resubmit", "POST", f"/api/expenses/{expense_id}/submit", {})
        api.decide("api-gm-rework.stale-final", expense_id, 1, "carol")
        api.decide("api-gm-rework.gm-before-new-first", expense_id, 2, "carol")
        api.decide("api-gm-rework.new-first-approve", expense_id, 2, "bob")
        api.decide("api-gm-rework.new-final-approve", expense_id, 2, "carol")

        expense_id = api.create("api-first-rework")
        api.action("api-first-rework.submit", "POST", f"/api/expenses/{expense_id}/submit", {})
        api.decide("api-first-rework.first-reject", expense_id, 1, "bob", "rejected", "Approver requests changed receipt")
        api.action("api-first-rework.revise", "POST", f"/api/expenses/{expense_id}/revise", {
            "amount": "45", "purpose": "Approver requested revision", "receipt_ref": "first-r2"})
        api.action("api-first-rework.resubmit", "POST", f"/api/expenses/{expense_id}/submit", {})
        api.decide("api-first-rework.stale-final", expense_id, 1, "carol")
        api.decide("api-first-rework.gm-before-new-first", expense_id, 2, "carol")
        api.decide("api-first-rework.new-first-approve", expense_id, 2, "bob")
        api.decide("api-first-rework.final-approve", expense_id, 2, "carol")


def observe_browser(database: Path, observations: list[dict[str, Any]], resources: list[dict[str, Any]]) -> None:
    from playwright.sync_api import sync_playwright

    row: dict[str, Any] = {"id": "browser-main", "transport": "real Chromium UI",
                           "steps": [], "api_responses": [], "blocked_nonlocal_requests": []}
    observations.append(row)
    with http_application(database, resources) as port, browser_environment(), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        resource = {"kind": "owned Chromium browser", "closed": False}
        resources.append(resource)
        try:
            row["browser_version"] = browser.version
            page = browser.new_page()
            page.set_default_timeout(10000)

            def local_only(route):
                if route.request.url.startswith(f"http://127.0.0.1:{port}/"):
                    route.continue_()
                else:
                    row["blocked_nonlocal_requests"].append(route.request.url)
                    route.abort()

            def response_seen(response):
                if "/api/expenses" in response.url:
                    row["api_responses"].append({"method": response.request.method,
                                                 "path": response.url.split(f"http://127.0.0.1:{port}", 1)[-1],
                                                 "status": response.status, "body": response.json()})

            page.route("**/*", local_only)
            page.on("response", response_seen)
            page.goto(f"http://127.0.0.1:{port}/")

            def capture(step: str, status: str, revision: int):
                page.wait_for_function("([status, revision]) => {try {const v=JSON.parse(document.querySelector('#current').textContent); return v.status===status && v.revision===revision;} catch (_) {return false;}}", arg=[status, revision])
                row["steps"].append({"step": step, "current_text": page.locator("#current").text_content(),
                                     "database": database_snapshot(database)})

            page.fill("#amount", "42.50")
            page.fill("#purpose", "Browser reference draft")
            page.fill("#receipt", "browser-r1")
            page.click("button[type=submit]")
            capture("create", "draft", 1)
            page.fill("#purpose", "Browser edited draft")
            page.click("#edit-btn")
            page.wait_for_function("() => document.querySelector('#current').textContent.includes('Browser edited draft')")
            capture("edit", "draft", 1)
            page.click("#submit-btn")
            capture("submit", "submitted", 1)
            page.fill("#approver-reason", "Browser first-stage rejection")
            page.click("#reject-btn")
            capture("first-reject", "rejected", 1)
            page.fill("#purpose", "Browser first rework")
            page.fill("#receipt", "browser-r2")
            page.click("#revise-btn")
            capture("first-revise", "draft", 2)
            page.click("#submit-btn")
            capture("first-resubmit", "submitted", 2)
            page.fill("#approver-reason", "Browser initial approval on revision 2")
            page.click("#approve-btn")
            capture("first-approve-r2", "manager_pending", 2)
            page.fill("#gm-reason", "Browser GM rejection")
            page.click("#gm-reject-btn")
            capture("gm-reject", "rejected", 2)
            page.fill("#purpose", "Browser GM rework")
            page.fill("#receipt", "browser-r3")
            page.click("#revise-btn")
            capture("gm-revise", "draft", 3)
            page.click("#submit-btn")
            capture("gm-resubmit", "submitted", 3)
            page.fill("#approver-reason", "Browser initial approval on revision 3")
            page.click("#approve-btn")
            capture("first-approve-r3", "manager_pending", 3)
            page.fill("#gm-reason", "Browser final approval on revision 3")
            page.click("#gm-approve-btn")
            capture("final-approve-r3", "approved", 3)
            page.click("#history-btn")
            page.wait_for_function("() => document.querySelector('#history').textContent.includes('Browser final approval on revision 3')")
            row["history_text"] = page.locator("#history").text_content()
            row["after"] = database_snapshot(database)
        finally:
            browser.close()
            resource["closed"] = True


@contextmanager
def application_process(database: Path, resources: list[dict[str, Any]]):
    with tempfile.TemporaryFile(mode="w+b") as stderr:
        process = subprocess.Popen([sys.executable, "-u", str(ROOT / "app.py"), "--host", "127.0.0.1",
                                    "--port", "0", "--db", str(database)], cwd=ROOT,
                                   env=child_environment(), stdout=subprocess.PIPE, stderr=stderr)
        resource = {"kind": "owned application process", "pid": process.pid, "database": str(database),
                    "environment_keys": sorted(child_environment()), "closed": False}
        resources.append(resource)
        try:
            assert process.stdout is not None
            ready, _, _ = select.select([process.stdout], [], [], 10)
            if not ready:
                raise RuntimeError("OWNED_APPLICATION_START_TIMEOUT")
            line = process.stdout.readline(4096).decode("utf-8")
            resource["startup_stdout"] = line
            match = re.fullmatch(r"Expense Approval running at http://127\.0\.0\.1:(\d+)\n", line)
            if match is None:
                raise RuntimeError("OWNED_APPLICATION_START_PROTOCOL")
            port = int(match.group(1))
            yield ApiRecorder(port, database, [])
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if process.stdout is not None:
                process.stdout.close()
            stderr.seek(0)
            resource["stderr"] = stderr.read(16384).decode("utf-8", errors="replace")
            resource["returncode"] = process.returncode
            resource["closed"] = process.poll() is not None


def observe_restart(database: Path, observations: list[dict[str, Any]], resources: list[dict[str, Any]]) -> None:
    with application_process(database, resources) as api:
        api.observations = observations
        expense_id = api.create("process-restart")
        api.action("process-restart.submit", "POST", f"/api/expenses/{expense_id}/submit", {})
        api.decide("process-restart.first-approve", expense_id, 1, "bob")
        api.decide("process-restart.final-approve", expense_id, 1, "carol")
        observations.append({"id": "process-restart.before-stop", "pid": resources[-1]["pid"],
                             "current": api.request("GET", f"/api/expenses/{expense_id}"),
                             "history": api.request("GET", f"/api/expenses/{expense_id}/history"),
                             "database": database_snapshot(database)})
    with application_process(database, resources) as api:
        observations.append({"id": "process-restart.after-start", "pid": resources[-1]["pid"],
                             "current": api.request("GET", f"/api/expenses/{expense_id}"),
                             "history": api.request("GET", f"/api/expenses/{expense_id}/history"),
                             "database": database_snapshot(database)})


def execution_records(document: dict[str, Any]) -> list[dict[str, Any]]:
    objects = json.loads((ROOT / "close_loop/onboarding/objects.json").read_bytes())
    records = []
    for carrier in objects["execution_carriers"]:
        if carrier["id"] == "EL-browser-ui":
            indices = [i for i, row in enumerate(document["observations"]) if row["id"].startswith("browser-")]
        else:
            indices = list(range(len(document["observations"])))
        record = {"id": document["run_id"] + "/" + carrier["id"], "implementation_entity": carrier["id"],
                  "record_kind": "project execution observation; not a canonical platform record",
                  "boundary": carrier["boundary"], "owned_paths": carrier["owned_paths"],
                  "subject": "expense-approval-reference", "product_git_revision": document["source"]["product_git_revision"],
                  "actor": "system:expense-onboarding-observer", "run_id": document["run_id"],
                  "raw_observation_pointers": ["#/observations/" + str(i) for i in indices],
                  "environment_pointer": "#/environment", "source_pointer": "#/source",
                  "declaration_pointer": "#/frozen_declarations", "completed": document["completed"],
                  "scope": "Bounded local single-organization final-approval observation",
                  "limits": "Raw observations and carrier mapping only; not a Function judgment or Governance decision."}
        record["record_revision"] = "sha256:" + digest(json_bytes({"record": record, "raw_observations": [document["observations"][i] for i in indices], "environment": document["environment"]}))
        records.append(record)
    return records


def publish(output: Path, document: dict[str, Any]) -> None:
    """Publish complete raw bytes without replacing an existing destination."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".expense-observation-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json_bytes(document))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def observe(product_revision: str, run_id: str) -> dict[str, Any]:
    source = source_binding(product_revision)
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", run_id):
        raise ValueError("INVALID_RUN_ID")
    declarations = []
    for name in DECLARATIONS:
        path = ROOT / "close_loop/onboarding" / name
        raw = path.read_bytes()
        declarations.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest(raw), "bytes": len(raw)})
    document: dict[str, Any] = {
        "format": "expense.raw-final-approval-observations.v0.1", "task_semantics": "condition-assessment pilot",
        "run_id": run_id, "started_at": timestamp(), "source": source, "frozen_declarations": declarations,
        "environment": {"python": sys.version, "platform": sys.platform,
                        "playwright": importlib.metadata.version("playwright"),
                        "observer_module": str(Path(__file__).resolve()),
                        "application_module": str(Path(sys.modules[make_server.__module__].__file__).resolve()),
                        "context_environment": {key: os.environ[key] for key in ["GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "GITHUB_EVENT_NAME"] if key in os.environ},
                        "context_limits": "Provider context is recorded, not authenticated by this program."},
        "observations": [], "resources": [], "completed": False, "authority_effect": "none",
        "limits": ["Raw execution observations; no assessment, path_state, governance acceptance or business permission",
                   "All SQLite files/listeners/processes/browser contexts belong to this temporary invocation",
                   "Seeded roles, sequential local reference behavior, SQLite restart and Chromium only"],
    }
    if Path(document["environment"]["application_module"]) != ROOT / "expense/http.py":
        raise ValueError("APPLICATION_IMPORT_ORIGIN_MISMATCH")
    directory = tempfile.TemporaryDirectory(prefix="expense-pilot-")
    temporary_root = Path(directory.name)
    document["temporary_resource_directory"] = str(temporary_root)
    try:
        observe_api(temporary_root / "api.sqlite3", document["observations"], document["resources"])
        observe_browser(temporary_root / "browser.sqlite3", document["observations"], document["resources"])
        observe_restart(temporary_root / "restart.sqlite3", document["observations"], document["resources"])
        if source_binding(product_revision) != source:
            raise ValueError("SOURCE_CHANGED_DURING_OBSERVATION")
        document["completed"] = True
    except Exception as error:
        document["execution_error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        directory.cleanup()
        document["temporary_resource_directory_removed"] = not temporary_root.exists()
        document["ended_at"] = timestamp()
    document["execution_records"] = execution_records(document)
    return document


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-revision", required=True, help="Independently selected full Git commit")
    parser.add_argument("--run-id", required=True, help="Unique caller-selected observation event ID")
    parser.add_argument("--output", required=True, type=Path, help="New raw JSON output; existing destinations are preserved")
    args = parser.parse_args(arguments)
    if os.path.lexists(args.output):
        raise FileExistsError("OBSERVATION_OUTPUT_ALREADY_EXISTS")
    document = observe(args.product_revision, args.run_id)
    publish(args.output, document)
    print(json.dumps({"run_id": args.run_id, "completed": document["completed"],
                      "observations": len(document["observations"]), "output_sha256": digest(args.output.read_bytes()),
                      "authority_effect": "none"}, sort_keys=True))
    return 0 if document["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

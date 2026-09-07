from __future__ import annotations

import sqlite3
from pathlib import Path

from .domain import Decision, ExpenseContent, ExpenseRevision, ExpenseStatus, ensure_can_review, ensure_can_revise_after_rejection, ensure_can_submit


class ExpenseStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    expense_id INTEGER NOT NULL,
                    revision INTEGER NOT NULL,
                    amount TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    receipt_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (expense_id, revision),
                    FOREIGN KEY (expense_id) REFERENCES expenses(id)
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_id INTEGER NOT NULL,
                    revision INTEGER NOT NULL,
                    approver TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    FOREIGN KEY (expense_id, revision) REFERENCES revisions(expense_id, revision)
                );
                """
            )

    def create_draft(self, employee: str, amount: str, purpose: str, receipt_ref: str) -> ExpenseRevision:
        employee = employee.strip()
        if not employee:
            raise ValueError("employee is required")
        content = ExpenseContent.validated(amount, purpose, receipt_ref)
        with self._connect() as conn:
            cur = conn.execute("INSERT INTO expenses(employee) VALUES (?)", (employee,))
            expense_id = cur.lastrowid
            conn.execute(
                "INSERT INTO revisions(expense_id, revision, amount, purpose, receipt_ref, status) VALUES (?,1,?,?,?,?)",
                (expense_id, content.amount, content.purpose, content.receipt_ref, ExpenseStatus.DRAFT.value),
            )
        return self.get_revision(expense_id, 1)

    def get_revision(self, expense_id: int, revision: int) -> ExpenseRevision:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT r.*, e.employee FROM revisions r JOIN expenses e ON e.id=r.expense_id WHERE r.expense_id=? AND r.revision=?",
                (expense_id, revision),
            ).fetchone()
        if row is None:
            raise KeyError("expense revision not found")
        return ExpenseRevision(
            expense_id=row["expense_id"],
            revision=row["revision"],
            employee=row["employee"],
            content=ExpenseContent(row["amount"], row["purpose"], row["receipt_ref"]),
            status=ExpenseStatus(row["status"]),
        )

    def latest(self, expense_id: int) -> ExpenseRevision:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(revision) AS revision FROM revisions WHERE expense_id=?", (expense_id,)).fetchone()
        if row is None or row["revision"] is None:
            raise KeyError("expense not found")
        return self.get_revision(expense_id, row["revision"])

    def edit_draft(self, expense_id: int, amount: str, purpose: str, receipt_ref: str) -> ExpenseRevision:
        current = self.latest(expense_id)
        if current.status != ExpenseStatus.DRAFT:
            raise ValueError("only a draft can be edited")
        content = ExpenseContent.validated(amount, purpose, receipt_ref)
        with self._connect() as conn:
            conn.execute(
                "UPDATE revisions SET amount=?, purpose=?, receipt_ref=? WHERE expense_id=? AND revision=?",
                (content.amount, content.purpose, content.receipt_ref, expense_id, current.revision),
            )
        return self.get_revision(expense_id, current.revision)

    def submit(self, expense_id: int) -> ExpenseRevision:
        current = self.latest(expense_id)
        ensure_can_submit(current.status)
        with self._connect() as conn:
            conn.execute(
                "UPDATE revisions SET status=? WHERE expense_id=? AND revision=?",
                (ExpenseStatus.SUBMITTED.value, expense_id, current.revision),
            )
        return self.get_revision(expense_id, current.revision)

    def decide(self, expense_id: int, revision: int, approver: str, outcome: str, reason: str) -> Decision:
        approver = approver.strip()
        reason = reason.strip()
        if not approver:
            raise ValueError("approver is required")
        if outcome not in {"approved", "rejected"}:
            raise ValueError("outcome must be approved or rejected")
        if not reason:
            raise ValueError("decision reason is required")
        target = self.get_revision(expense_id, revision)
        current = self.latest(expense_id)
        if current.revision != revision:
            raise ValueError("decision must target the current submitted revision")
        ensure_can_review(target, approver)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO decisions(expense_id, revision, approver, outcome, reason) VALUES (?,?,?,?,?)",
                (expense_id, revision, approver, outcome, reason),
            )
            conn.execute(
                "UPDATE revisions SET status=? WHERE expense_id=? AND revision=?",
                (outcome, expense_id, revision),
            )
        return Decision(expense_id, revision, approver, outcome, reason)

    def revise_rejected(self, expense_id: int, amount: str, purpose: str, receipt_ref: str) -> ExpenseRevision:
        current = self.latest(expense_id)
        ensure_can_revise_after_rejection(current.status)
        content = ExpenseContent.validated(amount, purpose, receipt_ref)
        new_revision = current.revision + 1
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO revisions(expense_id, revision, amount, purpose, receipt_ref, status) VALUES (?,?,?,?,?,?)",
                (expense_id, new_revision, content.amount, content.purpose, content.receipt_ref, ExpenseStatus.DRAFT.value),
            )
        return self.get_revision(expense_id, new_revision)

    def history(self, expense_id: int) -> dict:
        with self._connect() as conn:
            revisions = conn.execute(
                "SELECT r.*, e.employee FROM revisions r JOIN expenses e ON e.id=r.expense_id WHERE r.expense_id=? ORDER BY revision",
                (expense_id,),
            ).fetchall()
            decisions = conn.execute(
                "SELECT expense_id, revision, approver, outcome, reason FROM decisions WHERE expense_id=? ORDER BY id",
                (expense_id,),
            ).fetchall()
        if not revisions:
            raise KeyError("expense not found")
        return {
            "revisions": [dict(row) for row in revisions],
            "decisions": [dict(row) for row in decisions],
        }

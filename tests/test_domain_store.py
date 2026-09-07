from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from expense.domain import ExpenseStatus
from expense.store import ExpenseStore


class ExpenseStoreInvariantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "expenses.sqlite3"
        self.store = ExpenseStore(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_submit_review_reject_revise_resubmit_preserves_history(self):
        draft = self.store.create_draft("alice", "12.50", "Taxi", "receipt-1")
        submitted = self.store.submit(draft.expense_id)
        self.assertEqual(ExpenseStatus.SUBMITTED, submitted.status)

        decision = self.store.decide(submitted.expense_id, submitted.revision, "bob", "rejected", "Need itemized receipt")
        self.assertEqual("rejected", decision.outcome)

        revised = self.store.revise_rejected(submitted.expense_id, "12.50", "Taxi to client", "receipt-2")
        self.assertEqual(2, revised.revision)
        self.assertEqual(ExpenseStatus.DRAFT, revised.status)
        self.store.submit(revised.expense_id)

        history = self.store.history(revised.expense_id)
        self.assertEqual([1, 2], [row["revision"] for row in history["revisions"]])
        self.assertEqual("rejected", history["revisions"][0]["status"])
        self.assertEqual("submitted", history["revisions"][1]["status"])
        self.assertEqual(1, history["decisions"][0]["revision"])
        self.assertEqual("rejected", history["decisions"][0]["outcome"])

    def test_employee_cannot_decide_own_expense_and_state_is_unchanged(self):
        draft = self.store.create_draft("alice", "30", "Lunch", "receipt-lunch")
        submitted = self.store.submit(draft.expense_id)
        with self.assertRaises(PermissionError):
            self.store.decide(submitted.expense_id, submitted.revision, "alice", "approved", "Looks fine")
        current = self.store.latest(submitted.expense_id)
        self.assertEqual(ExpenseStatus.SUBMITTED, current.status)
        self.assertEqual([], self.store.history(submitted.expense_id)["decisions"])

    def test_decision_cannot_target_old_revision(self):
        draft = self.store.create_draft("alice", "20", "Train", "r1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, 1, "bob", "rejected", "Wrong receipt")
        revised = self.store.revise_rejected(submitted.expense_id, "21", "Train", "r2")
        self.store.submit(revised.expense_id)
        with self.assertRaises(ValueError):
            self.store.decide(revised.expense_id, 1, "bob", "approved", "Approve old")
        self.assertEqual(ExpenseStatus.SUBMITTED, self.store.latest(revised.expense_id).status)

    def test_approved_revision_cannot_be_edited_or_revised(self):
        draft = self.store.create_draft("alice", "45", "Hotel", "hotel-1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, submitted.revision, "bob", "approved", "Policy compliant")
        with self.assertRaises(ValueError):
            self.store.edit_draft(submitted.expense_id, "50", "Hotel", "hotel-2")
        with self.assertRaises(ValueError):
            self.store.revise_rejected(submitted.expense_id, "50", "Hotel", "hotel-2")
        self.assertEqual(ExpenseStatus.APPROVED, self.store.latest(submitted.expense_id).status)

    def test_history_survives_store_restart(self):
        draft = self.store.create_draft("alice", "9.99", "Coffee", "coffee-1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, 1, "bob", "rejected", "Not reimbursable")
        reopened = ExpenseStore(self.db)
        history = reopened.history(submitted.expense_id)
        self.assertEqual("rejected", history["revisions"][0]["status"])
        self.assertEqual("bob", history["decisions"][0]["approver"])


if __name__ == "__main__":
    unittest.main()

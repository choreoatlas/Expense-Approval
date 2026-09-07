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

    def test_draft_can_be_edited_and_invalid_edit_does_not_mutate(self):
        draft = self.store.create_draft("alice", "12.50", "Taxi", "receipt-1")
        edited = self.store.edit_draft(draft.expense_id, "13.25", "Taxi to client", "receipt-2")
        self.assertEqual("13.25", edited.content.amount)
        self.assertEqual("Taxi to client", edited.content.purpose)
        self.assertEqual(1, edited.revision)
        with self.assertRaises(ValueError):
            self.store.edit_draft(draft.expense_id, "0", "bad", "receipt-x")
        current = self.store.latest(draft.expense_id)
        self.assertEqual("13.25", current.content.amount)
        self.assertEqual("Taxi to client", current.content.purpose)

    def test_approver_then_general_manager_are_both_required_for_final_approval(self):
        draft = self.store.create_draft("alice", "45", "Hotel", "hotel-1")
        submitted = self.store.submit(draft.expense_id)
        first = self.store.decide(submitted.expense_id, 1, "bob", "approved", "Policy compliant")
        self.assertEqual("approver", first.actor_role)
        self.assertEqual(ExpenseStatus.MANAGER_PENDING, self.store.latest(draft.expense_id).status)
        second = self.store.decide(submitted.expense_id, 1, "carol", "approved", "GM approved")
        self.assertEqual("general_manager", second.actor_role)
        self.assertEqual(ExpenseStatus.APPROVED, self.store.latest(draft.expense_id).status)
        history = self.store.history(draft.expense_id)
        self.assertEqual(["approver", "general_manager"], [d["actor_role"] for d in history["decisions"]])

    def test_general_manager_rejects_then_new_revision_requires_both_stages_again(self):
        draft = self.store.create_draft("alice", "80", "Client meal", "meal-1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, 1, "bob", "approved", "First stage approved")
        gm_reject = self.store.decide(submitted.expense_id, 1, "carol", "rejected", "Need attendee list")
        self.assertEqual("general_manager", gm_reject.actor_role)
        self.assertEqual(ExpenseStatus.REJECTED, self.store.latest(draft.expense_id).status)

        revised = self.store.revise_rejected(draft.expense_id, "80", "Client meal with attendee list", "meal-2")
        self.assertEqual(2, revised.revision)
        self.store.submit(draft.expense_id)
        self.assertEqual(ExpenseStatus.SUBMITTED, self.store.latest(draft.expense_id).status)
        self.store.decide(draft.expense_id, 2, "bob", "approved", "First stage approved again")
        self.assertEqual(ExpenseStatus.MANAGER_PENDING, self.store.latest(draft.expense_id).status)

        history = self.store.history(draft.expense_id)
        self.assertEqual([1, 2], [r["revision"] for r in history["revisions"]])
        self.assertEqual([1, 1, 2], [d["revision"] for d in history["decisions"]])
        self.assertEqual(["approver", "general_manager", "approver"], [d["actor_role"] for d in history["decisions"]])

    def test_final_manager_decision_cannot_target_superseded_revision(self):
        draft = self.store.create_draft("alice", "60", "Train", "train-1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, 1, "bob", "approved", "First stage")
        self.store.decide(submitted.expense_id, 1, "carol", "rejected", "Change receipt")
        revised = self.store.revise_rejected(draft.expense_id, "61", "Train", "train-2")
        self.store.submit(revised.expense_id)
        with self.assertRaises(ValueError):
            self.store.decide(revised.expense_id, 1, "carol", "approved", "Approve stale revision")
        self.assertEqual(ExpenseStatus.SUBMITTED, self.store.latest(revised.expense_id).status)

    def test_unauthorized_actor_and_wrong_stage_authority_do_not_mutate_state(self):
        draft = self.store.create_draft("alice", "30", "Lunch", "receipt-lunch")
        submitted = self.store.submit(draft.expense_id)
        with self.assertRaises(PermissionError):
            self.store.decide(submitted.expense_id, 1, "mallory", "approved", "I say yes")
        self.assertEqual(ExpenseStatus.SUBMITTED, self.store.latest(draft.expense_id).status)
        with self.assertRaises(PermissionError):
            self.store.decide(submitted.expense_id, 1, "carol", "approved", "Skip first stage")
        self.assertEqual(ExpenseStatus.SUBMITTED, self.store.latest(draft.expense_id).status)
        self.store.decide(submitted.expense_id, 1, "bob", "approved", "First stage yes")
        with self.assertRaises(PermissionError):
            self.store.decide(submitted.expense_id, 1, "bob", "approved", "Try final stage")
        self.assertEqual(ExpenseStatus.MANAGER_PENDING, self.store.latest(draft.expense_id).status)

    def test_employee_cannot_decide_own_expense_and_state_is_unchanged(self):
        draft = self.store.create_draft("alice", "30", "Lunch", "receipt-lunch")
        submitted = self.store.submit(draft.expense_id)
        with self.assertRaises(PermissionError):
            self.store.decide(submitted.expense_id, submitted.revision, "alice", "approved", "Looks fine")
        current = self.store.latest(submitted.expense_id)
        self.assertEqual(ExpenseStatus.SUBMITTED, current.status)
        self.assertEqual([], self.store.history(submitted.expense_id)["decisions"])

    def test_reject_revise_resubmit_preserves_history_and_requires_two_stages_again(self):
        draft = self.store.create_draft("alice", "12.50", "Taxi", "receipt-1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, 1, "bob", "rejected", "Need itemized receipt")
        revised = self.store.revise_rejected(submitted.expense_id, "12.50", "Taxi to client", "receipt-2")
        self.assertEqual(2, revised.revision)
        self.store.submit(revised.expense_id)
        self.store.decide(revised.expense_id, 2, "bob", "approved", "First stage approved")
        self.assertEqual(ExpenseStatus.MANAGER_PENDING, self.store.latest(revised.expense_id).status)
        self.store.decide(revised.expense_id, 2, "carol", "approved", "GM approved")
        history = self.store.history(revised.expense_id)
        self.assertEqual([1, 2], [row["revision"] for row in history["revisions"]])
        self.assertEqual("rejected", history["revisions"][0]["status"])
        self.assertEqual("approved", history["revisions"][1]["status"])
        self.assertEqual([1, 2, 2], [d["revision"] for d in history["decisions"]])

    def test_decision_cannot_target_old_revision(self):
        draft = self.store.create_draft("alice", "20", "Train", "r1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, 1, "bob", "rejected", "Wrong receipt")
        revised = self.store.revise_rejected(submitted.expense_id, "21", "Train", "r2")
        self.store.submit(revised.expense_id)
        with self.assertRaises(ValueError):
            self.store.decide(revised.expense_id, 1, "bob", "approved", "Approve old")
        self.assertEqual(ExpenseStatus.SUBMITTED, self.store.latest(revised.expense_id).status)

    def test_final_approved_revision_cannot_be_edited_or_revised(self):
        draft = self.store.create_draft("alice", "45", "Hotel", "hotel-1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, 1, "bob", "approved", "First stage")
        self.store.decide(submitted.expense_id, 1, "carol", "approved", "Final stage")
        with self.assertRaises(ValueError):
            self.store.edit_draft(submitted.expense_id, "50", "Hotel", "hotel-2")
        with self.assertRaises(ValueError):
            self.store.revise_rejected(submitted.expense_id, "50", "Hotel", "hotel-2")
        self.assertEqual(ExpenseStatus.APPROVED, self.store.latest(submitted.expense_id).status)

    def test_history_survives_store_restart(self):
        draft = self.store.create_draft("alice", "9.99", "Coffee", "coffee-1")
        submitted = self.store.submit(draft.expense_id)
        self.store.decide(submitted.expense_id, 1, "bob", "approved", "First stage")
        self.store.decide(submitted.expense_id, 1, "carol", "approved", "Final stage")
        reopened = ExpenseStore(self.db)
        history = reopened.history(submitted.expense_id)
        self.assertEqual("approved", history["revisions"][0]["status"])
        self.assertEqual(["bob", "carol"], [d["actor"] for d in history["decisions"]])
        self.assertEqual(["approver", "general_manager"], [d["actor_role"] for d in history["decisions"]])
        self.assertEqual(ExpenseStatus.APPROVED, reopened.latest(submitted.expense_id).status)


if __name__ == "__main__":
    unittest.main()

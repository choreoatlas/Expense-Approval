from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum


class ExpenseStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REJECTED = "rejected"
    APPROVED = "approved"


@dataclass(frozen=True)
class ExpenseContent:
    amount: str
    purpose: str
    receipt_ref: str

    @classmethod
    def validated(cls, amount: str, purpose: str, receipt_ref: str) -> "ExpenseContent":
        try:
            parsed = Decimal(str(amount))
        except (InvalidOperation, ValueError):
            raise ValueError("amount must be a positive number")
        if parsed <= 0:
            raise ValueError("amount must be a positive number")
        purpose = purpose.strip()
        receipt_ref = receipt_ref.strip()
        if not purpose:
            raise ValueError("purpose is required")
        if not receipt_ref:
            raise ValueError("receipt reference is required")
        return cls(format(parsed, "f"), purpose, receipt_ref)


@dataclass(frozen=True)
class ExpenseRevision:
    expense_id: int
    revision: int
    employee: str
    content: ExpenseContent
    status: ExpenseStatus


@dataclass(frozen=True)
class Decision:
    expense_id: int
    revision: int
    approver: str
    outcome: str
    reason: str


def ensure_can_submit(status: ExpenseStatus) -> None:
    if status != ExpenseStatus.DRAFT:
        raise ValueError("only a draft can be submitted")


def ensure_can_review(revision: ExpenseRevision, approver: str) -> None:
    if revision.status != ExpenseStatus.SUBMITTED:
        raise ValueError("only a submitted revision can be reviewed")
    if revision.employee == approver:
        raise PermissionError("employee cannot approve or reject their own expense")


def ensure_can_revise_after_rejection(status: ExpenseStatus) -> None:
    if status != ExpenseStatus.REJECTED:
        raise ValueError("only a rejected expense can be revised")

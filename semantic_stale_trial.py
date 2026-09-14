from dataclasses import dataclass
from decimal import Decimal
from expense.domain import ActorRole

@dataclass(frozen=True)
class Judgment:
    expense_id: int
    amount: str
    evidence: tuple[str, ...]
    accepted_under: str
    state: str = 'ACCEPTED'
    reason: str = ''

def authority_path(amount: str, threshold: str):
    if Decimal(amount) >= Decimal(threshold):
        return (ActorRole.GENERAL_MANAGER.value,)
    return (ActorRole.APPROVER.value, ActorRole.GENERAL_MANAGER.value)

def rejudge(j: Judgment, old_threshold: str, new_threshold: str) -> Judgment:
    old_path = authority_path(j.amount, old_threshold)
    new_path = authority_path(j.amount, new_threshold)
    if old_path != new_path:
        return Judgment(j.expense_id, j.amount, j.evidence, j.accepted_under, 'STALE',
                        f'authority path changed {old_path} -> {new_path}')
    return j

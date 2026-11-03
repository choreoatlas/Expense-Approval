# Expense Approval

CloseLoop reference implementation for a small expense approval system.

The local reference implementation includes explicit actor roles, two-stage
approval, revision/rejection history, a browser UI and SQLite persistence.
The Owner's [original acceptance](https://github.com/choreoatlas/Expense-Approval/issues/1#issuecomment-5571375864)
binds revision `c0f01dbf4af0dc9f9201c15f37cf960b925fce0c` in the
`reference-sample` governance domain; it does not assert production readiness
or broader canonical/A1 admission.

See GitHub issue #1 for the commissioned product goal, actors, hard invariants, and scope limits.

[Workload onboarding and the bounded final-approval condition-assessment pilot](close_loop/onboarding/README.md)
provide the object map, source profile, predeclared conditions/composition and
raw observation entry. Their outputs are separate from historical acceptance
and require explicit assessment and cross-repository verification.

[Frozen source/CI handoff, two condition-assessment bases and offline replay](close_loop/onboarding/records/README.md)
preserve the actual bounded integration evidence. The selected final-review
path has candidate `scope_limited` results; the other seven paths remain
explicitly not rejudged in this pilot. Current Governance/consumption authority
is not established by these records.
